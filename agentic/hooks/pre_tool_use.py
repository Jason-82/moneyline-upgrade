#!/usr/bin/env python3
"""PreToolUse hook: guard every Robinhood MCP call (SPEC section 9).

Claude Code passes the event JSON on stdin. Exit 0 lets the call proceed (normal permission flow); exit 2 blocks it
and stderr is shown to Claude. Fails closed: any error while handling a trade, cancel, simulate or unknown Robinhood
tool blocks the call. Standard library only.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import timedelta
from pathlib import Path

RH_TOOL = re.compile(r"^mcp__.*robinhood.*__", re.IGNORECASE)     # = agentic.hooks.RH_TOOL (fast path, no imports)
BLOCK = 2
H = None                                                          # agentic.hooks, imported lazily


def _account_problem(cfg: dict, ti: dict) -> str | None:
    """None if every account field in the call is the configured agentic account."""
    keys = [k for k in H.ACCOUNT_KEYS if k in ti]
    if not keys:
        return "the call names no account"
    for k in keys:
        want = str(cfg["account"].get(k) or "").strip()
        if not want or want.upper().startswith("FILL-IN"):
            return f"account.{k} is not set in the private config"
        if H.norm(ti[k]) != want:
            return f"{k} is not the configured agentic account"
    return None


MAX_PLAN_LIFE_H = 24
CLOCK_SKEW_MIN = 5
NEVER_KEYS = ("dollar_amount", "tax_lots", "stop_price")


def _shape_problem(short: str, prm: dict) -> str | None:
    """Plan orders may only take the shapes the planner makes (SPEC 7); anything else is refused even if a plan
    file lists it."""
    if any(k in prm for k in NEVER_KEYS):
        return "plan orders never use dollar_amount, tax_lots or stop_price"
    typ, tif = H.norm(prm.get("type")).lower(), H.norm(prm.get("time_in_force")).lower()
    if H.norm(prm.get("side")).lower() not in ("buy", "sell"):
        return "side must be buy or sell"
    qty = H.num(prm.get("quantity"))
    if qty is None or qty <= 0:
        return "quantity must be a positive number"
    if short == "place_crypto_order":
        if typ != "limit" or tif != "gtc":
            return "crypto plan orders are gtc limit orders only"
        return None
    if H.norm(prm.get("market_hours")).lower() != "regular_hours" or tif != "gfd":
        return "equity plan orders are gfd and regular_hours only"
    if typ == "limit":
        return None
    if typ == "market" and "limit_price" not in prm:
        return None
    return "equity plan orders are limit orders, or market orders in regular hours"


def _plan_problem(plan: dict, now) -> str | None:
    if plan.get("live") is not True:
        return "the current plan was not made in live mode (live=true): re-run the plan"
    if not plan.get("valid_until") or not plan.get("created_at"):
        return "the plan has no valid_until / created_at"
    vu, ca = H.parse_ts(plan["valid_until"]), H.parse_ts(plan["created_at"])
    if now >= vu:
        return f"the plan expired at {vu:%Y-%m-%d %H:%M}Z: re-run the plan, never re-send an old one"
    if ca > now + timedelta(minutes=CLOCK_SKEW_MIN):
        return "the plan's created_at is in the future"
    if vu - ca > timedelta(hours=MAX_PLAN_LIFE_H):
        return f"the plan claims a validity of more than {MAX_PLAN_LIFE_H} h"
    pid, sdate = str(plan.get("plan_id") or ""), str(plan.get("signals_date") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[0-9a-f]{8}", pid) or (sdate and not pid.startswith(sdate + "-")):
        return "the plan_id is not one the planner makes"
    return None


def _market_problem(now) -> str | None:
    try:
        from agentic import calendar as cal
        if cal.market_open(now) and cal.execution_session(now) == cal.et_date(now):
            return None
    except Exception as e:                                       # no tz database: fail closed for market orders
        return f"cannot check market hours ({type(e).__name__})"
    return "market orders are placed only in regular hours before 15:45 ET: re-run the plan in the session"


def _call_notional(p: dict, short: str, ti: dict) -> tuple[float | None, str]:
    """The notional of the call itself: quantity x limit_price, or for a market order quantity x the newest captured
    quote. (None, why) when it cannot be bounded."""
    qty = H.num(ti.get("quantity"))
    if qty is None or qty <= 0:
        return None, "quantity is not a positive number"
    if H.norm(ti.get("type")).lower() == "limit":
        px = H.num(ti.get("limit_price"))
        if px is None or px <= 0:
            return None, "limit_price is not a positive number"
        return qty * px, "quantity x limit_price"
    kind = "crypto" if short == "place_crypto_order" else "equity"
    q = H.latest_quote(p["inbox"], H.norm(ti.get("symbol")), kind)
    if q is None:
        return None, "no captured quote to bound a market order"
    return qty * q[0], f"quantity x captured quote ({q[1].split('_', 1)[0]})"


def _check_trade(cfg: dict, p: dict, short: str, ti: dict, now) -> tuple[bool, str]:
    if p["STOP"].exists():
        return False, "STOP file present: no new orders (cancels are still allowed)"
    if cfg["live"] is not True:
        return False, "config live=false (shadow mode): place calls are blocked; use the review/preview tool"
    bad = _account_problem(cfg, ti)
    if bad:
        return False, bad
    if not isinstance(ti.get("ref_id"), str) or not ti["ref_id"].strip():
        return False, "missing ref_id: copy the plan params verbatim"
    plan = H.read_json(p["plan_current"])
    if not isinstance(plan, dict):
        return False, "no plan_current.json: run `python3 -m agentic plan`"
    bad = _plan_problem(plan, now)
    if bad:
        return False, bad
    if any(H.norm(plan.get(k)) != H.norm(cfg["account"].get(k)) for k in H.ACCOUNT_KEYS):
        return False, "the plan's account numbers do not match the config"
    order = H.find_plan_order(plan, short, ti)
    if order is None:
        return False, f"no plan order matches these params exactly ({H.closest_mismatch(plan, short, ti)})"
    if H.norm(ti["ref_id"]) != H.ref_id_for(plan.get("plan_id"), order.get("key"), plan.get("attempt")):
        return False, "the ref_id is not the one the planner derives for this plan order (edited plan?)"
    bad = _shape_problem(short, order["params"])
    if bad:
        return False, bad
    side = H.norm(ti.get("side")).lower()
    for flag in ("FLATTEN", "BLOCK_BUYS"):
        if p[flag].exists() and side != "sell":
            return False, f"{flag} present: sells only"
    if H.norm(ti.get("type")).lower() == "market":
        bad = _market_problem(now)
        if bad:
            return False, bad
    try:
        planned = float(order["notional_usd"])
    except (KeyError, TypeError, ValueError):
        planned = float("nan")
    if not math.isfinite(planned) or planned < 0:
        return False, "the plan order's notional_usd is invalid"
    computed, how = _call_notional(p, short, ti)
    if computed is None:
        return False, how
    notional = max(planned, computed)
    lim = cfg["limits"]
    if notional > float(lim["max_order_usd"]) + 1e-9:
        return False, f"order notional {notional:.2f} ({how}) > max_order_usd {float(lim['max_order_usd']):.2f}"
    today = H.ledger_get(p["ledger"], H.et_date(now))
    if today + notional > float(lim["max_day_usd"]) + 1e-9:
        return False, (f"daily cap: placed today {today:.2f} + this {notional:.2f} > "
                       f"max_day_usd {float(lim['max_day_usd']):.2f}")
    if H.placed_ok(H.read_journal(p["journal"]), H.norm(ti["ref_id"])):
        return False, "this ref_id was already placed: read the order status instead of re-sending"
    return True, f"matches plan {plan.get('plan_id')} order {order.get('key')}"


def _check_cancel(cfg: dict, p: dict, short: str, ti: dict) -> tuple[bool, str]:
    bad = _account_problem(cfg, ti)
    if bad:
        return False, bad
    oid = H.norm(ti["order_id"]) if isinstance(ti.get("order_id"), str) else ""
    if not oid:
        return False, "cancel without an order_id"
    try:
        plan = H.read_json(p["plan_current"])
    except ValueError:
        plan = None                                   # a corrupt plan must not stop the kill switch
    for c in (plan.get("cancels") or []) if isinstance(plan, dict) else []:
        if (isinstance(c, dict) and isinstance(c.get("params"), dict) and H.norm(c["params"].get("order_id")) == oid
                and H.short_name(c.get("tool") or short) == short):
            return True, "the order is in plan.cancels"
    if H.journaled_order(H.read_journal(p["journal"], strict=False), oid):
        return True, "the order was placed by this system (journal)"
    return False, "the order is neither in plan.cancels nor in the journal of orders this system placed"


def decide(event: dict, now=None) -> tuple[bool, str]:
    """(allow, reason) for one Robinhood tool call. Raises on unexpected input; the caller fails closed."""
    from agentic.config import load_config, paths
    short = H.short_name(event["tool_name"])
    kind = H.classify(short)
    if kind == "read":
        return True, "read"
    if kind == "other":
        return False, f"{short} is not allowed: only reads, previews and plan orders/cancels may run"
    ti = event.get("tool_input")
    if not isinstance(ti, dict):
        return False, "tool_input is not an object"
    cfg, p = load_config(), paths()
    if kind == "simulate":
        bad = _account_problem(cfg, ti)
        return (False, bad) if bad else (True, "preview on the configured account")
    if kind == "cancel":
        return _check_cancel(cfg, p, short, ti)
    return _check_trade(cfg, p, short, ti, now or H.utc_now())


def _load_helpers():
    global H
    if H is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from agentic import hooks
        H = hooks
    return H


def _block_unreadable(why: str) -> int:
    try:
        _load_helpers().log("pre", None, "block", why)
    except BaseException:
        pass
    print(f"BLOCKED by agentic hook: {why} (fail closed)", file=sys.stderr)
    return BLOCK


def main() -> int:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        tool = event.get("tool_name")
    except Exception:
        return _block_unreadable("unreadable PreToolUse input")
    if isinstance(tool, str) and not RH_TOOL.match(tool):
        return 0
    if not isinstance(tool, str):
        return _block_unreadable("no tool_name in the PreToolUse input")
    short = tool.rsplit("__", 1)[-1]
    try:
        _load_helpers()
        kind = H.classify(short)
        ti = event.get("tool_input")
        ref = ti.get("ref_id") if isinstance(ti, dict) and isinstance(ti.get("ref_id"), str) else None
        secrets = H.account_secrets(ti)
    except BaseException as e:
        print(f"BLOCKED by agentic hook: cannot load agentic.hooks ({type(e).__name__}; fail closed)", file=sys.stderr)
        return BLOCK
    try:
        allow, reason = decide(event)
    except BaseException as e:
        allow, reason = kind == "read", f"hook error ({type(e).__name__}: {e})"
    H.log("pre", tool, "allow" if allow else "block", reason, ref, secrets)
    if allow:
        return 0
    print(f"BLOCKED by agentic hook ({short}): {H.scrub(reason, secrets)}. Do not edit or retry the call; "
          f"stop and report this to the user.", file=sys.stderr)
    return BLOCK


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        code = BLOCK
    sys.exit(code)
