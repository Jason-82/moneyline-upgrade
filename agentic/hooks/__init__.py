"""Shared rules for the Claude Code hooks that guard the Robinhood MCP tools (SPEC sections 8-11).

Standard library only. pre_tool_use.py and post_tool_use.py put the repo root on sys.path and import this module, so
both hooks classify tools, match plan orders and read the journal and ledger the same way.
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from agentic.config import paths

UTC = timezone.utc
RH_TOOL = re.compile(r"^mcp__.*robinhood.*__", re.IGNORECASE)
READ_EXACT = frozenset({"search", "preview_scan", "run_scan"})
SIMULATE = frozenset({"review_equity_order", "preview_crypto_order"})
TRADE = frozenset({"place_equity_order", "place_crypto_order"})
CANCEL = frozenset({"cancel_equity_order", "cancel_crypto_order"})
ACCOUNT_KEYS = ("account_number", "rhs_account_number")
PROPOSAL_STATE = "proposal_pending_approval?"
_LONG_DIGITS = re.compile(r"\d{6,}")


# ------------------------------------------------------------------ tools

def is_robinhood(tool_name) -> bool:
    return isinstance(tool_name, str) and bool(RH_TOOL.match(tool_name))


def short_name(tool_name) -> str:
    """The part after the last '__': mcp__robinhood-trading__get_portfolio -> get_portfolio."""
    return str(tool_name).rsplit("__", 1)[-1]


def classify(short: str) -> str:
    """'read', 'simulate', 'trade', 'cancel', or 'other' (always blocked)."""
    if short.startswith("get_") or short in READ_EXACT:
        return "read"
    if short in SIMULATE:
        return "simulate"
    if short in TRADE:
        return "trade"
    if short in CANCEL:
        return "cancel"
    return "other"


# ------------------------------------------------------------------ time

def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_ts(s) -> datetime:
    """An ISO timestamp ('...Z', an offset, or naive = UTC) as an aware datetime."""
    dt = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00").replace("z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _et_offset_manual(now: datetime) -> timedelta:
    """US Eastern UTC offset from the 2007+ DST rule, for systems without the tz database."""
    y = now.year
    mar8, nov1 = datetime(y, 3, 8, 7, tzinfo=UTC), datetime(y, 11, 1, 6, tzinfo=UTC)
    start = mar8 + timedelta(days=(6 - mar8.weekday()) % 7)      # 2nd Sunday of March, 2:00 EST
    end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)        # 1st Sunday of November, 2:00 EDT
    return timedelta(hours=-4 if start <= now.astimezone(UTC) < end else -5)


def et_date(now: datetime) -> date:
    """The America/New_York calendar date: the ledger's day."""
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("America/New_York")).date()
    except Exception:
        return (now.astimezone(UTC) + _et_offset_manual(now)).date()


# ------------------------------------------------------------------ plan matching

def norm(v) -> str:
    """A JSON value as the hook compares it: strings stripped, anything else as compact JSON."""
    return v.strip() if isinstance(v, str) else json.dumps(v, sort_keys=True, separators=(",", ":"))


def param_diff(expected: dict, got: dict) -> list[str]:
    """Keys missing, extra or different between plan params and a tool_input."""
    return sorted(k for k in set(expected) | set(got)
                  if k not in expected or k not in got or norm(expected[k]) != norm(got[k]))


def find_plan_order(plan, short: str, tool_input) -> dict | None:
    """The plan order whose tool is `short` and whose params equal tool_input exactly (same keys), else None."""
    if not isinstance(plan, dict) or not isinstance(tool_input, dict):
        return None
    for o in plan.get("orders") or []:
        if (isinstance(o, dict) and short_name(o.get("tool", "")) == short and isinstance(o.get("params"), dict)
                and not param_diff(o["params"], tool_input)):
            return o
    return None


def closest_mismatch(plan, short: str, tool_input: dict) -> str:
    """Why no plan order matched, naming fields only, never values."""
    best = None
    for o in (plan.get("orders") or []) if isinstance(plan, dict) else []:
        if isinstance(o, dict) and isinstance(o.get("params"), dict):
            d = (["tool"] if short_name(o.get("tool", "")) != short else []) + param_diff(o["params"], tool_input)
            if best is None or len(d) < len(best[1]):
                best = (o, d)
    if best is None:
        return "the plan has no orders"
    return f"closest plan order {best[0].get('key')} differs in: {', '.join(best[1])}"


def strip_accounts(params) -> dict | None:
    return {k: v for k, v in params.items() if "account" not in str(k).lower()} if isinstance(params, dict) else None


# ------------------------------------------------------------------ files

def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:      # a UTF-8 BOM (Windows Notepad) is skipped, not an error
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json_atomic(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f)                         # ASCII escapes: lone surrogates cannot break the write
        for i in range(10):                           # Windows: the replace fails while another process has the
            try:                                      # file open (the CLI, an antivirus scan); retry briefly
                os.replace(tmp, path)
                break
            except PermissionError:
                if i == 9:
                    raise
                time.sleep(0.05 * (i + 1))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def append_line(path, line: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (line if line.endswith("\n") else line + "\n").encode("utf-8", "backslashreplace")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)   # Windows: no \r\n
    with os.fdopen(fd, "ab") as f:
        f.write(data)


def append_jsonl(path, obj) -> None:
    append_line(path, json.dumps(obj))


def save_capture(inbox, tool: str, tool_input, response, now: datetime) -> Path:
    """Write inbox/<YYYYMMDDTHHMMSS.ffffffZ>_<short_tool>.json with the response exactly as received (SPEC 8)."""
    inbox = Path(inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    short = re.sub(r"[^A-Za-z0-9_.-]", "_", short_name(tool)) or "tool"
    t = now.astimezone(UTC)
    while (inbox / f"{t:%Y%m%dT%H%M%S.%f}Z_{short}.json").exists():
        t += timedelta(microseconds=1)
    f = inbox / f"{t:%Y%m%dT%H%M%S.%f}Z_{short}.json"
    write_json_atomic(f, {"captured_at": iso_z(t), "tool": tool, "tool_input": tool_input, "response": response})
    return f


# ------------------------------------------------------------------ journal, ledger, flags

def read_journal(path, strict: bool = True) -> list[dict]:
    """journal.jsonl entries. strict: a corrupt line raises (the pre hook then fails closed)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            if strict:
                raise ValueError(f"journal.jsonl line {i} is not valid JSON") from None
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def placed_ok(entries: list[dict], ref_id: str) -> bool:
    """A place with this ref_id already returned without an error (an order or a pending proposal)."""
    return any(e.get("event") == "place" and e.get("ref_id") is not None and norm(e.get("ref_id")) == ref_id
               and not e.get("error") for e in entries)


def journaled_order(entries: list[dict], order_id: str) -> dict | None:
    """The journal's place entry for an order id this system placed."""
    for e in reversed(entries):
        if e.get("event") == "place" and e.get("order_id") and norm(e["order_id"]) == order_id:
            return e
    return None


def _usd(x) -> float:
    f = float(x)
    if isinstance(x, bool) or not math.isfinite(f) or f < 0:
        raise ValueError(f"ledger.json holds an invalid amount {x!r}")
    return f


def day_total(v) -> float:
    """A ledger day's placed notional, in any format agentic/ledger.py reads ({"placed_usd", "refs"}, a number, a
    list). Strict: a malformed, negative or non-finite value raises, so the pre hook fails closed instead of reading
    a number that disables the daily cap."""
    if v is None:
        return 0.0
    if isinstance(v, dict):
        refs = sum(_usd(x) for x in (v.get("refs") or {}).values()) if isinstance(v.get("refs"), dict) else 0.0
        for k in ("placed_usd", "notional_usd", "total"):
            if v.get(k) is not None:
                return max(_usd(v[k]), refs)
        return refs
    if isinstance(v, list):
        return float(sum(_usd(x.get("notional_usd") or 0.0) if isinstance(x, dict) else _usd(x) for x in v))
    return _usd(v)


def _read_ledger(path) -> dict:
    led = read_json(path, {})
    if not isinstance(led, dict):
        raise ValueError("ledger.json is not a JSON object")
    return led


def ledger_get(path, day: date) -> float:
    return day_total(_read_ledger(path).get(day.isoformat()))


def ledger_add(path, day: date, usd: float, ref_id=None) -> float:
    """Record a successful place in ledger.json[ET date] in agentic/ledger.py's format
    {"placed_usd": total, "refs": {ref_id: notional_usd}}; a ref_id counts once. Returns the day total."""
    led = _read_ledger(path)
    k = day.isoformat()
    cur = led.get(k)
    if not isinstance(cur, dict) or not isinstance(cur.get("refs"), dict):
        prior = day_total(cur)
        cur = {"refs": {"_prior": round(prior, 2)} if prior else {}}
    refs = cur["refs"]
    rid = str(ref_id) if ref_id else f"_anon{len(refs)}"
    if rid not in refs:
        refs[rid] = round(float(usd), 2)
    cur["placed_usd"] = round(sum(float(x) for x in refs.values()), 2)
    led[k] = cur
    write_json_atomic(path, led)
    return cur["placed_usd"]


def write_stop(p: dict, reason: str, now: datetime) -> None:
    append_line(p["STOP"], f"{iso_z(now)} {reason}")


# ------------------------------------------------------------------ plan integrity, quotes, orders

def ref_id_for(plan_id, key, attempt) -> str:
    """= agentic.planner.ref_id: the ref_id a genuine plan gives order `key` at `attempt`."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"moneyline|{plan_id}|{key}|{attempt}"))


def num(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _quote_symbol(sym) -> str:
    s = str(sym or "").upper().strip()
    return s.replace("-", "")


def latest_quote(inbox, symbol: str, kind: str):
    """(highest of bid/ask/last, capture file) from the newest captured quote for `symbol`, or None. Used to bound
    the notional of a market order, which has no limit price."""
    short = "get_crypto_quotes" if kind == "crypto" else "get_equity_quotes"
    want = _quote_symbol(symbol if kind != "crypto" or "-" in str(symbol) else f"{symbol}-USD")
    try:
        files = sorted(Path(inbox).glob(f"*_{short}.json"), reverse=True)
    except OSError:
        return None
    for f in files:
        cap = read_json(f, None)
        if not isinstance(cap, dict):
            continue
        obj, err = unwrap(cap.get("response"))
        if err or not isinstance(obj, dict):
            continue
        data = obj.get("data") if isinstance(obj.get("data"), (dict, list)) else obj
        rows = data if isinstance(data, list) else (data.get("results") or data.get("quotes") or [])
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            q = r.get("quote") if isinstance(r.get("quote"), dict) else r
            if _quote_symbol(q.get("symbol") or r.get("symbol")) != want:
                continue
            px = [v for v in (num(q.get(k)) for k in ("bid_price", "ask_price", "last_trade_price", "mark_price"))
                  if v is not None and v > 0]
            if px:
                return max(px), f.name
    return None


def order_rows(obj) -> list[dict]:
    """The orders in a get_equity_orders / get_crypto_orders / place result payload."""
    data = obj.get("data") if isinstance(obj, dict) and isinstance(obj.get("data"), (dict, list)) else obj
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if not isinstance(data, dict):
        return []
    for k in ("orders", "results"):
        if isinstance(data.get(k), list):
            return [r for r in data[k] if isinstance(r, dict)]
    return [data["order"]] if isinstance(data.get("order"), dict) else []


# ------------------------------------------------------------------ responses

def _is_content(c) -> bool:
    return isinstance(c, list) and bool(c) and all(isinstance(x, dict) and "type" in x for x in c)


def _content_text(c) -> str:
    if not isinstance(c, list):
        return ""
    return "".join(str(x.get("text", "")) for x in c if isinstance(x, dict) and x.get("type") == "text")


def unwrap(resp):
    """(structured result, error text or None) from a tool_response: the object itself, {"structuredContent": ...},
    {"content": [{"type": "text", "text": "<json>"}]}, a bare content list, or a JSON string."""
    r = resp
    for _ in range(6):
        if isinstance(r, str):
            s = r.strip()
            try:
                r = json.loads(s)
                continue
            except ValueError:
                return None, (s[:300] if s.lower().startswith("error") else None)
        if isinstance(r, dict):
            if r.get("isError"):
                return None, _content_text(r.get("content"))[:300] or "the tool returned isError"
            if isinstance(r.get("structuredContent"), (dict, list)):
                r = r["structuredContent"]
                continue
            if _is_content(r.get("content")):
                r = _content_text(r["content"])
                continue
            if r.get("error") and not isinstance(r.get("data"), dict):
                return None, str(r["error"])[:300]
            return r, None
        if _is_content(r):
            r = _content_text(r)
            continue
        return r, None
    return r, None


# ------------------------------------------------------------------ logging

def account_secrets(tool_input=None) -> list[str]:
    """Account numbers to keep out of logs: from the call and from the private config (read raw, no validation)."""
    out = []
    if isinstance(tool_input, dict):
        out += [str(v) for k, v in tool_input.items() if "account" in str(k).lower() and v]
    try:
        acct = (read_json(paths()["config"], {}) or {}).get("account") or {}
        out += [v for k, v in acct.items() if "account" in str(k).lower() and isinstance(v, str) and v]
    except Exception:
        pass
    return out


def scrub(text, secrets=(), digits: bool = True) -> str:
    """Mask known account numbers and (digits=True) any run of 6+ digits."""
    s = str(text)
    for sec in secrets:
        sec = str(sec or "").strip()
        if len(sec) >= 4:
            s = s.replace(sec, "***")
    return _LONG_DIGITS.sub("***", s) if digits else s


def log(hook: str, tool, decision: str, reason: str, ref_id=None, secrets=()) -> None:
    """Append one JSON line to hook.log. Never raises."""
    try:
        append_jsonl(paths()["hook_log"], {
            "ts": iso_z(utc_now()), "hook": hook, "tool": scrub(tool, secrets, digits=False), "decision": decision,
            "reason": scrub(reason, secrets), "ref_id": scrub(ref_id, secrets, digits=False) if ref_id else None})
    except Exception:
        pass
