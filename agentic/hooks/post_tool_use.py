#!/usr/bin/env python3
"""PostToolUse / PostToolUseFailure hook: save raw Robinhood MCP results to the inbox, journal place/cancel calls,
check approvals (SPEC sections 8 and 10).

Never blocks: always exits 0 and logs its own errors to hook.log. If an agent order went live while approvals are
required (in a place result or in a later order listing), or a tool outside the allowlist ran, it writes STOP (the
file, and a "decision": "STOP" record in hook.log that keeps STOP active if the file is deleted; after every
Robinhood call, even one whose handling failed, a STOP record in force that is about to leave the window the
PreToolUse check reads is carried forward) and warns on stderr and through the hook's JSON output. A failed or
timed-out place is journaled as failed_or_unknown and counted against the daily cap. Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import timedelta
from pathlib import Path

RH_TOOL = re.compile(r"^mcp__.*robinhood.*__", re.IGNORECASE)     # = agentic.hooks.RH_TOOL
H = None                                                          # agentic.hooks, imported lazily
ORDER_KEYS = ("id", "state", "placed_agent", "agent_initiated", "cumulative_quantity", "ref_id", "quantity", "side",
              "symbol", "currency_code")                         # order fields: a response with these is no proposal
FAILED = "failed_or_unknown"
RECENT_H = 24                                                     # read-back: how recent a direct agent order counts
STOP_ADVICE = ("No new orders. Check this order in the Robinhood app, cancel it if unwanted, and confirm Trade "
               "approvals are ON before the user runs `resume`.")


def _estimate_notional(ti: dict, order: dict | None) -> float:
    """Best-effort notional of a place call that matched no plan order."""
    try:
        if ti.get("dollar_amount") not in (None, ""):
            return float(ti["dollar_amount"])
        price = ti.get("limit_price") or (order or {}).get("price") or ti.get("stop_price")
        return float(ti["quantity"]) * float(price)
    except (KeyError, TypeError, ValueError):
        return 0.0


def _guarded(label: str, tool: str, secrets: list, fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        H.log("post", tool, "error", f"{label}: {type(e).__name__}: {e}", None, secrets)
        return None


def _stop(p: dict, tool: str, reason: str, now, ref, secrets: list, warnings: list) -> None:
    """Write STOP and warn. The warning is added first, so a failed write is still reported loudly. The hook.log
    "STOP" record is written even when the STOP file cannot be: it makes STOP sticky (hooks.sticky_stop), so the
    PreToolUse hook blocks place calls until `resume` clears it, with or without the file."""
    warnings.append(f"AGENTIC STOP: {reason}. {STOP_ADVICE}")
    try:
        H.write_stop(p, reason, now)
    except Exception as e:
        warnings.append(f"the STOP file could NOT be written ({type(e).__name__}): place nothing more and tell the "
                        "user now")
        H.log("post", tool, "error", f"stop: {type(e).__name__}: {e}", ref, secrets)
    H.log("post", tool, "STOP", reason, ref, secrets)


def _approvals(cfg) -> bool:
    return True if cfg is None else cfg["account"].get("approvals_required", True) is not False


def _place(cfg, p: dict, tool: str, ti: dict, resp, now, secrets: list, failure: str | None = None) -> list[str]:
    short = H.short_name(tool)
    try:
        plan = H.read_json(p["plan_current"])
    except ValueError:
        plan = None
    order = H.find_plan_order(plan, short, ti)
    warnings = []
    ref = ti.get("ref_id")
    if failure is not None:                       # PostToolUseFailure: the order may or may not exist
        err, data, o, state = f"{FAILED}: {failure}", None, None, FAILED
    else:
        obj, err = H.unwrap(resp)
        data = obj.get("data") if isinstance(obj, dict) else None
        o = data.get("order") if isinstance(data, dict) else None
        o = o if isinstance(o, dict) and o else None
        if err:
            state = "error"
        elif not isinstance(data, dict):
            state = "unknown_response"
        elif o is None:
            state = "unrecognised_response" if any(k in data for k in ORDER_KEYS) else H.PROPOSAL_STATE
        else:
            state = str(o.get("state"))
        if not err:
            if _approvals(cfg):
                if not isinstance(data, dict):
                    _stop(p, tool, "unreadable place response: approval cannot be confirmed", now, ref, secrets,
                          warnings)
                elif o is not None:                # a place result never carries an order the user approved
                    _stop(p, tool, f"an agent order went live without approval (placed_agent="
                          f"{o.get('placed_agent') or o.get('initiator_type')}, state={state})", now, ref, secrets,
                          warnings)
                elif state == "unrecognised_response":
                    _stop(p, tool, "unrecognised place response (order fields without data.order): approval "
                          "cannot be confirmed", now, ref, secrets, warnings)
            if order is None:
                _stop(p, tool, "a place call succeeded that matches no plan order", now, ref, secrets, warnings)

    try:
        notional = float(order["notional_usd"])
    except (TypeError, KeyError, ValueError):
        notional = _estimate_notional(ti, o)
    entry = {"ts": H.iso_z(now), "event": "place", "tool": short,
             "plan_id": plan.get("plan_id") if order and isinstance(plan, dict) else None,
             "key": order.get("key") if order else None, "ref_id": ref, "params": H.strip_accounts(ti),
             "notional_usd": notional, "order_id": o.get("id") if o else None, "state": state,
             "placed_agent": o.get("placed_agent") if o else None,
             "agent_initiated": o.get("agent_initiated") if o else None,
             "error": H.scrub(err, secrets) if err else None}
    for k in ("initiator_type", "cumulative_quantity", "average_price"):
        if o and o.get(k) is not None:
            entry[k] = o[k]
    _guarded("journal", tool, secrets, H.append_jsonl, p["journal"], entry)
    if not err or failure is not None:            # an unknown outcome counts against the daily cap, to be safe
        _guarded("ledger", tool, secrets, H.ledger_add, p["ledger"], H.et_date(now), notional, ref)
    if failure is not None:
        warnings.append(f"agentic hook: {short} failed or timed out ({H.scrub(failure, secrets)[:200]}); the order "
                        "may still exist. Do not retry: read the orders back and report.")
    H.log("post", tool, "journaled", f"place {state}", ref, secrets)
    return warnings


def _cancel(cfg, p: dict, tool: str, ti: dict, resp, now, secrets: list, failure: str | None = None) -> list[str]:
    short = H.short_name(tool)
    if failure is not None:
        err, acc = f"{FAILED}: {failure}", None
    else:
        obj, err = H.unwrap(resp)
        data = obj.get("data") if isinstance(obj, dict) else None
        acc = data.get("accepted") if isinstance(data, dict) else None
    state = (FAILED if failure is not None else "cancel_requested" if acc is True else "cancel_rejected"
             if acc is False else "error" if err else "unknown_response")
    oid = H.norm(ti.get("order_id")) if isinstance(ti.get("order_id"), str) else None
    placed = (H.journaled_order(H.read_journal(p["journal"], strict=False), oid) if oid else None) or {}
    plan_id = placed.get("plan_id")
    if plan_id is None:
        try:
            plan = H.read_json(p["plan_current"]) or {}
            if any(isinstance(c, dict) and H.norm((c.get("params") or {}).get("order_id")) == oid
                   for c in plan.get("cancels") or []):
                plan_id = plan.get("plan_id")
        except (ValueError, AttributeError):
            pass
    entry = {"ts": H.iso_z(now), "event": "cancel", "tool": short, "plan_id": plan_id, "key": placed.get("key"),
             "ref_id": placed.get("ref_id"), "params": H.strip_accounts(ti), "order_id": oid, "state": state,
             "placed_agent": None, "agent_initiated": None, "error": H.scrub(err, secrets) if err else None}
    _guarded("journal", tool, secrets, H.append_jsonl, p["journal"], entry)
    H.log("post", tool, "journaled", f"cancel {state}", None, secrets)
    return []


def _readback(cfg, p: dict, tool: str, resp, now, secrets: list) -> list[str]:
    """With approvals required, an order listing must never show an order this system placed directly: approved
    proposals carry the approval's id (not our ref_id) and read placed_agent 'user'. Writes STOP once per order."""
    warnings = []
    if not _approvals(cfg):
        return warnings
    obj, err = H.unwrap(resp)
    rows = [] if err else H.order_rows(obj)
    if not rows:
        return warnings
    entries = H.read_journal(p["journal"], strict=False)
    ours = {H.norm(e["ref_id"]) for e in entries
            if e.get("event") == "place" and e.get("ref_id") and e.get("state") in (H.PROPOSAL_STATE, FAILED)}
    try:
        plan = H.read_json(p["plan_current"]) or {}
        ours |= {H.norm((o.get("params") or {}).get("ref_id")) for o in plan.get("orders") or []
                 if isinstance(o, dict) and isinstance(o.get("params"), dict) and o["params"].get("ref_id")}
    except (ValueError, AttributeError):
        pass
    flagged = {H.norm(e.get("order_id")) for e in entries if e.get("event") == "approval_bypass"}
    for r in rows:
        oid = H.norm(r.get("id")) if r.get("id") else ""
        if not oid or oid in flagged:
            continue
        ref = H.norm(r.get("ref_id")) if isinstance(r.get("ref_id"), str) and r["ref_id"].strip() else None
        agent = H.norm(r.get("placed_agent") or r.get("initiator_type") or "").lower()
        try:
            created = H.parse_ts(r["created_at"]) if r.get("created_at") else None
        except (ValueError, TypeError):
            created = None
        recent = created is None or created >= now - timedelta(hours=RECENT_H)
        why = None
        if ref and ref in ours:
            why = "an order carries this system's own ref_id, so it was placed without a trade approval"
        elif agent in ("agentic", "agentic_trading") and r.get("agent_initiated") is not False and recent:
            why = f"an agent order was submitted directly (placed_agent={agent}), not approved in the app"
        if why:
            flagged.add(oid)
            _guarded("journal", tool, secrets, H.append_jsonl, p["journal"], {
                "ts": H.iso_z(now), "event": "approval_bypass", "tool": H.short_name(tool), "order_id": oid,
                "ref_id": ref, "state": r.get("state"), "placed_agent": agent or None})
            _stop(p, tool, f"{why} (order {oid[:8]}, state {r.get('state')})", now, ref, secrets, warnings)
    return warnings


def handle(event: dict, now=None) -> list[str]:
    """Capture, journal and approval-check one Robinhood tool result (PostToolUse) or failure (PostToolUseFailure);
    returns warnings for the user. Then, whatever happened (an early return, an exception), carry a STOP in force
    forward in hook.log when needed (hooks.carry_stop_forward)."""
    try:
        return _handle(event, now)
    finally:
        _carry(event.get("tool_name"))


def _carry(tool) -> None:
    """hooks.carry_stop_forward, so a STOP in force stays in the window the PreToolUse check reads. Never raises."""
    try:
        from agentic.config import paths
        H.carry_stop_forward(paths()["hook_log"], tool)
    except Exception as e:
        H.log("post", tool, "error", f"carry stop: {type(e).__name__}: {e}", None, H.account_secrets())


def _handle(event: dict, now=None) -> list[str]:
    from agentic.config import load_config, paths
    now = now or H.utc_now()
    tool = event["tool_name"]
    short = H.short_name(tool)
    kind = H.classify(short)
    raw_ti = event.get("tool_input")
    ti = raw_ti if isinstance(raw_ti, dict) else {}
    failed = event.get("hook_event_name") == "PostToolUseFailure"
    failure = str(event.get("error") or "the tool call failed") if failed else None
    resp = event.get("tool_response")
    p = paths()
    secrets = H.account_secrets(ti)
    ref = ti.get("ref_id") if isinstance(ti.get("ref_id"), str) else None
    warnings = []
    if not failed:
        f = _guarded("capture", tool, secrets, H.save_capture, p["inbox"], tool, raw_ti, resp, now)
        prob = _guarded("capture", tool, secrets, H.capture_problem, resp)
        if f is not None:
            H.log("post", tool, "captured", "saved to the inbox" + (f" ({prob[0]})" if prob else ""), ref, secrets)
        if prob and prob[0] == "response_too_large":
            warnings.append(f"agentic hook: the {short} result holds no data. {H.TOO_LARGE_HELP}")
    else:
        H.log("post", tool, "failure", H.scrub(failure, secrets)[:300], ref, secrets)
    if kind == "other":
        warnings.append(f"agentic hook: {short} ran although it is outside the allowlist")
        if not failed:
            _stop(p, tool, f"{short} ran although it is outside the allowlist", now, ref, secrets, warnings)
        return warnings
    cfg = None
    if kind in ("trade", "cancel") or short in ("get_equity_orders", "get_crypto_orders"):
        try:
            cfg = load_config()
        except Exception as e:
            H.log("post", tool, "error", f"config: {type(e).__name__}: {e}", ref, secrets)
    if kind in ("trade", "cancel"):
        warnings += (_place if kind == "trade" else _cancel)(cfg, p, tool, ti, resp, now, secrets, failure)
    elif short in ("get_equity_orders", "get_crypto_orders") and not failed:
        warnings += _readback(cfg, p, tool, resp, now, secrets)
    return warnings


def main() -> int:
    global H
    tool = None
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        tool = event.get("tool_name")
        if not isinstance(tool, str) or not RH_TOOL.match(tool):
            return 0
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from agentic import hooks
        H = hooks
        warnings = handle(event)
    except BaseException as e:
        if H is not None:
            H.log("post", tool, "error", f"{type(e).__name__}: {e}", None, H.account_secrets())
        return 0
    if warnings:
        msg = " | ".join(warnings)
        name = event.get("hook_event_name") if event.get("hook_event_name") == "PostToolUseFailure" else "PostToolUse"
        for line in (msg, json.dumps({"systemMessage": msg,
                                      "hookSpecificOutput": {"hookEventName": name, "additionalContext": msg}})):
            try:
                print(line, file=sys.stderr if line is msg else sys.stdout)
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
