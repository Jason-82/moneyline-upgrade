"""Shared rules for the Claude Code hooks that guard the Robinhood MCP tools (SPEC sections 8-11).

Standard library only. pre_tool_use.py and post_tool_use.py put the repo root on sys.path and import this module, so
both hooks classify tools, match plan orders and read the journal and ledger the same way.
"""
from __future__ import annotations

import hashlib
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
FAILED_STATE = "failed_or_unknown"                 # = post_tool_use.FAILED: a place that failed or timed out
# order states after which an order (or an approved proposal's order) is finished: it no longer waits for anything
SETTLED_STATES = frozenset({"filled", "cancelled", "canceled", "rejected", "failed", "expired", "voided"})
MATCH_SKEW = timedelta(minutes=5)                  # an approved proposal's order is created after the place call
LISTING_TAIL = 500                                 # newest order-listing captures read per tool by the pending check
# how far back the pending-proposal guard counts unresolved place calls: a rolling window, not the ET date, so a
# proposal made before midnight (or the evening before) still counts; gtc crypto proposals may wait for days
PENDING_LOOKBACK = timedelta(days=7)
RESOLVED_EVENT = "proposals_resolved"              # journal event of `resume --proposals`: the user's acknowledgement
_LONG_DIGITS = re.compile(r"\d{6,}")
# Claude Code saves an MCP text result over 50,000 characters (whatever MAX_MCP_OUTPUT_TOKENS says) to a file and
# passes on a notice instead, which is then all the PostToolUse hook receives: such a capture holds no data.
_TOO_LARGE = re.compile(r"too large|too long|exceed(s|ed)?\b.{0,40}\b(maximum|limit)|maximum allowed tokens|"
                        r"saved to (a )?file|output (was )?truncated|MAX_MCP_OUTPUT_TOKENS", re.IGNORECASE)
TOO_LARGE_HELP = ("Robinhood result too large for Claude Code (it saves a result over 50,000 characters to a file): "
                  "re-run fetch-list, which asks for that data again in smaller calls")


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
        with open(path, encoding="utf-8-sig") as f:      # a UTF-8 BOM (some Windows editors add one) is skipped
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


def capture_problem(response) -> tuple[str, str] | None:
    """(code, first 300 characters) when a tool_response is not the tool's JSON: "response_too_large" for Claude Code's
    notice that the result was too large (or saved to a file instead), else "not_json". None for a JSON result or a
    tool error (isError)."""
    r = response
    for _ in range(6):
        if isinstance(r, str):
            try:
                r = json.loads(r)
                continue
            except ValueError:
                text = r.strip()
                return ("response_too_large" if _TOO_LARGE.search(text) else "not_json"), text[:300]
        if isinstance(r, dict):
            if r.get("isError"):
                return None
            if isinstance(r.get("structuredContent"), (dict, list)):
                return None
            if _is_content(r.get("content")):
                r = _content_text(r["content"])
                continue
            return None
        if _is_content(r):
            r = _content_text(r)
            continue
        return None
    return None


def capture_message(code: str | None, head: str = "") -> str:
    """What a reader of the inbox says about a capture that holds no tool JSON."""
    if code == "response_too_large":
        return TOO_LARGE_HELP
    return f"not the tool's JSON result ({str(head)[:120]!r})"


def save_capture(inbox, tool: str, tool_input, response, now: datetime) -> Path:
    """Write inbox/<YYYYMMDDTHHMMSS.ffffffZ>_<short_tool>.json with the response exactly as received (SPEC 8). A
    response that is not the tool's JSON (capture_problem) also gets "capture_error" and "response_head" (its first
    300 characters)."""
    inbox = Path(inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    short = re.sub(r"[^A-Za-z0-9_.-]", "_", short_name(tool)) or "tool"
    t = now.astimezone(UTC)
    while (inbox / f"{t:%Y%m%dT%H%M%S.%f}Z_{short}.json").exists():
        t += timedelta(microseconds=1)
    f = inbox / f"{t:%Y%m%dT%H%M%S.%f}Z_{short}.json"
    obj = {"captured_at": iso_z(t), "tool": tool, "tool_input": tool_input, "response": response}
    prob = capture_problem(response)
    if prob:
        obj["capture_error"], obj["response_head"] = prob
    write_json_atomic(f, obj)
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
        except (ValueError, RecursionError):        # RecursionError: deeply nested brackets on a damaged line
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


# ------------------------------------------------------------------ sticky STOP (hook.log)

STOP_LOG_TAIL = 2 << 20                            # bytes of hook.log the sticky-STOP check reads (the newest 2 MB)
STOP_LOG_HEADS = ("STOP is active per hook.log", "STOP is treated as active")   # sticky_stop_message's openings
_STOP_TEXT = re.compile(r'"decision"\s*:\s*"STOP"')
_CARRIED = re.compile(r"^(?:carried forward from (.+?): )+")   # the nested prefixes of a carry without "origin"
FUTURE_SKEW = timedelta(minutes=5)                 # a STOP dated further ahead than this was written by a fast clock


def clears_stop(e: dict) -> bool:
    """Is hook.log record `e` a `resume` CLEAR that cleared STOP? Its "flags" list names STOP; a CLEAR written before
    records had "flags" counts when its reason starts with "cleared STOP (" (resume always names STOP first)."""
    if (e.get("hook"), e.get("tool"), e.get("decision")) != ("cli", "resume", "CLEAR"):
        return False
    fl = e.get("flags")
    if isinstance(fl, list):
        return "STOP" in fl
    return str(e.get("reason") or "").startswith("cleared STOP (")


def stop_record_id(raw: bytes) -> str:
    """A hook.log STOP record's identity: the first 16 hex digits of the SHA-256 of its line (surrounding whitespace,
    such as a Windows \\r, stripped). Append-only, so a record's line never changes."""
    return hashlib.sha256(raw.strip()).hexdigest()[:16]


def _stop_origin(raw: bytes, e) -> dict:
    """{"id", "ts", "reason"} of the STOP a STOP record stands for: a carried record's "origin" (carry_stop_forward
    copies it, so every carry of one STOP has the same id), else the record itself. A carry written before records had
    "origin" ("carried forward from <ts>: ..." prefixes, possibly nested) gives its innermost ts and reason."""
    if not isinstance(e, dict):                    # a damaged line that still reads "decision": "STOP"
        return {"id": stop_record_id(raw), "ts": None, "reason": "a damaged hook.log line that records a STOP"}
    o = e.get("origin")
    if isinstance(o, dict) and isinstance(o.get("id"), str) and o["id"]:
        return {"id": o["id"], "ts": o.get("ts"), "reason": o.get("reason")}
    ts, reason = e.get("ts"), str(e.get("reason") or "")
    m = _CARRIED.match(reason)
    if m:
        ts, reason = (None if m.group(1) == "an unknown time" else m.group(1)), reason[m.end():]
    return {"id": stop_record_id(raw), "ts": ts, "reason": reason}


def stop_state(path, tail: int = STOP_LOG_TAIL) -> tuple[dict | None, dict | None]:
    """(sticky_stop's result, the newest STOP record in the window as {"id", "ts", "reason"} of its origin, cleared or
    not, or None). `resume` names that id in its CLEAR record ("through"), so the clear covers exactly the STOP the
    user was shown. Never raises."""
    try:
        with open(path, "rb") as fh:
            size = fh.seek(0, os.SEEK_END)
            fh.seek(max(0, size - tail))
            data = fh.read()
    except FileNotFoundError:
        return None, None
    except Exception as e:                         # exists but unreadable (a directory, no permission): fail closed
        return {"ts": None, "reason": f"hook.log cannot be read ({type(e).__name__})", "why": "unreadable"}, None
    cur = newest = None                            # the STOP in force (file order), the newest STOP record
    pos = 0
    for k, raw in enumerate(data.split(b"\n")):
        at, pos = pos, pos + len(raw) + 1
        if (k == 0 and size > tail) or b"STOP" not in raw:     # the cut's partial line; a STOP record and a
            continue                                           # STOP-clearing CLEAR both name STOP
        line = raw.decode("utf-8", "replace")
        try:
            e = json.loads(line)
        except (ValueError, RecursionError):       # RecursionError: a damaged line of deeply nested brackets
            e = None
        if not isinstance(e, dict):
            if _STOP_TEXT.search(line):            # a damaged STOP record: a STOP of unknown time
                newest = _stop_origin(raw, None)
                cur = {**newest, "at": at, "rec_ts": None, "why": "active"}
            continue
        if e.get("decision") == "STOP":
            newest = _stop_origin(raw, e)
            cur = {**newest, "at": at, "rec_ts": e.get("ts"), "why": "active"}
        elif cur is not None and clears_stop(e):
            if "through" in e:                     # resume names the STOP it clears: only that one, whatever the dates
                if isinstance(e["through"], str) and e["through"] == cur["id"]:
                    cur = None                     # (a STOP recorded after the user's prompt stays in force)
                continue
            sts, cts = _ts_or_none(cur["rec_ts"]), _ts_or_none(e.get("ts"))   # a CLEAR without "through": by date
            if cts is not None and (sts is None or cts >= sts):
                cur = None
            else:
                cur.update(why="unordered", clear_ts=str(e.get("ts")))
    if cur is None:
        return None, newest
    out = {"ts": str(cur["ts"]) if cur["ts"] else None, "reason": str(cur["reason"] or "no reason recorded")[:300],
           "why": cur["why"], "id": cur["id"], "behind": len(data) - cur["at"]}    # bytes from the record to the end
    if cur["why"] == "unordered":
        out["clear_ts"] = cur["clear_ts"]
    return out, newest


def sticky_stop(path, tail: int = STOP_LOG_TAIL) -> dict | None:
    """STOP as hook.log records it, whatever the STOP file says: None when hook.log does not exist, holds no STOP
    record, or every STOP record is cleared. A STOP record is any line with "decision": "STOP" (the PostToolUse
    hook's, `stop`'s with hook "cli", and carry_stop_forward's). Records count in file order (append-only): a STOP is
    in force until a later `resume` CLEAR that clears STOP (clears_stop) clears it. A CLEAR with "through" (every
    resume since 2026-10-20) clears only the STOP whose origin id (stop_record_id) it names, whatever the dates: a STOP
    recorded after the user's prompt stays in force. A CLEAR without "through" clears it when dated at or after the
    STOP record; dated before it, or without a readable date, the two cannot be ordered.

    Else {"ts", "reason", "why", "id", "behind"}: ts and reason of the STOP's origin (a carried record's first STOP),
    why "active", "unordered" (that undatable or earlier-dated clear; also "clear_ts") or "unreadable" (hook.log exists
    but cannot be read). The last two fail closed: STOP counts as active. "id": the origin's id; "behind": the bytes
    from the STOP record to the end of the file (carry_stop_forward).

    Reads only the last `tail` bytes (the first, partial line of a cut is dropped). Lines that are not JSON objects
    are skipped, except one that still reads "decision": "STOP" (a damaged STOP record): it counts as a STOP of
    unknown time, which a later clear in the file still clears. Never raises."""
    return stop_state(path, tail)[0]


def _ts_text(ts) -> str:
    """A STOP's time for a carried record's reason: to the second, so the digit scrub of hook.log reasons leaves it
    readable."""
    t = _ts_or_none(ts)
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if t is not None else str(ts or "an unknown time")


def carry_stop_forward(path, tool=None, tail: int = STOP_LOG_TAIL, hook: str = "post") -> bool:
    """Re-append the STOP in force before it leaves the window sticky_stop reads: once its record lies more than half
    the tail back, log a new "decision": "STOP" record with "origin" {"id", "ts", "reason"} (the first STOP's, so
    carries never nest) and "reason" "carried forward from <origin time>: <origin reason>". An "unordered" STOP is
    carried too (after the clear, so it becomes an ordinary active STOP that one resume clears); an unreadable
    hook.log is not. The PostToolUse hook calls this after each Robinhood call and the PreToolUse hook after each call
    it blocks (no PostToolUse follows those), so neither the reads a run keeps making under STOP nor repeated blocked
    place calls push it out. A small hook.log is not read at all. Returns whether it wrote one."""
    try:
        if os.path.getsize(path) <= tail // 2:
            return False
    except OSError:
        return False
    s = sticky_stop(path, tail)
    if s is None or s["why"] == "unreadable" or s["behind"] <= tail // 2:
        return False
    reason = scrub(s["reason"])
    log(hook, tool, "STOP", f"carried forward from {_ts_text(s['ts'])}: {reason}"[:300],
        extra={"origin": {"id": s["id"], "ts": s["ts"], "reason": reason}})
    return True


def sticky_stop_message(s: dict) -> str:
    """What the PreToolUse hook, `status`, `doctor` and the digest say about a sticky_stop() result."""
    if s.get("why") == "unreadable":
        return (f"STOP is treated as active: {s['reason']}, so a STOP recorded there cannot be ruled out (fail "
                "closed); make hook.log readable again")
    msg = (f"STOP is active per hook.log (written {s.get('ts') or 'at an unknown time'}: {s.get('reason')}) although "
           "the STOP file is missing; only resume in your own terminal clears it")
    if s.get("why") == "unordered":
        msg += (f" (the newest clear in hook.log, dated {s.get('clear_ts')}, cannot be ordered after this STOP: check "
                "the PC clock, then run resume again)")
    return msg


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


# ------------------------------------------------------------------ proposals still waiting for approval

def _kind(tool) -> str:
    return "crypto" if "crypto" in str(tool or "") else "equity"


def _crypto_code(sym) -> str:
    """'SOL', 'SOL-USD' or 'SOLUSD' -> 'SOL'."""
    s = str(sym or "").upper().strip()
    if "-" in s:
        return s.split("-")[0]
    return s[:-3] if s.endswith("USD") and len(s) > 3 else s


def _row_symbol(r: dict, kind: str) -> str:
    if kind == "crypto":
        return _crypto_code(r.get("currency_code") or r.get("symbol"))
    return str(r.get("symbol") or "").upper().strip()


def _row_state(r: dict) -> str:
    return str(r.get("state") or "").lower().strip()


def _ts_or_none(s) -> datetime | None:
    try:
        return parse_ts(s)
    except (TypeError, ValueError):
        return None


def same_order(entry: dict, row: dict, kind: str, price: bool = True) -> bool:
    """Is order row `row` (an order listing's, or a journal fill's) the order of journal place entry `entry`? The same
    ref_id, or (an approved proposal's order carries the approval's id, not ours) the same symbol, side, quantity and
    (`price`, for a limit order) limit price, created no earlier than MATCH_SKEW before the place call."""
    prm = entry.get("params") if isinstance(entry.get("params"), dict) else {}
    ref = entry.get("ref_id")
    if ref and row.get("ref_id") and norm(row["ref_id"]) == norm(ref):
        return True
    sym = str(prm.get("symbol") or "").upper().strip()
    sym = _crypto_code(sym) if kind == "crypto" else sym
    if not sym or _row_symbol(row, kind) != sym:
        return False
    if str(row.get("side") or "").lower().strip() != str(prm.get("side") or "").lower().strip():
        return False
    q, rq = num(prm.get("quantity")), num(row.get("quantity"))
    if q is None or rq is None or abs(q - rq) > 1e-9 * max(1.0, abs(q)):
        return False
    lp = num(prm.get("limit_price"))
    if price and lp is not None:
        rp = num(row.get("limit_price") if row.get("limit_price") not in (None, "") else row.get("price"))
        if rp is None or abs(lp - rp) > 1e-9 * max(1.0, abs(lp)):
            return False
    created, placed = _ts_or_none(row.get("created_at")), _ts_or_none(entry.get("ts"))
    return created is None or placed is None or created >= placed - MATCH_SKEW


def _listing_rows(inbox, kinds, since: datetime) -> dict[str, tuple]:
    """{order id: (captured_at, kind, row, price_known)} from the get_equity_orders / get_crypto_orders captures taken
    at or after `since` (the newest LISTING_TAIL per tool), the newest capture's row per order. A capture that cannot
    be read is skipped: it settles nothing."""
    out: dict[str, tuple] = {}
    stamp = since.astimezone(UTC).strftime("%Y%m%dT%H%M%S")
    for kind in sorted(kinds):
        short = "get_crypto_orders" if kind == "crypto" else "get_equity_orders"
        try:
            files = sorted(f for f in Path(inbox).glob(f"*_{short}.json") if f.name[:15] >= stamp)[-LISTING_TAIL:]
        except OSError:
            continue
        for f in files:                              # named by capture time: older captures cannot settle anything
            try:
                cap = read_json(f, None)
                at = parse_ts(cap["captured_at"])
                obj, err = unwrap(cap.get("response"))
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue
            if err or at < since:
                continue
            for r in order_rows(obj):
                oid = norm(r.get("id")) if r.get("id") else ""
                if oid and (oid not in out or out[oid][0] <= at):
                    out[oid] = (at, kind, r, True)
    return out


def place_id(entry: dict) -> str:
    """A journal place entry's identity in a `resume --proposals` acknowledgement: its ts and ref_id as journaled (a
    failed_or_unknown place may be retried with the same ref_id, so the ref_id alone is not unique)."""
    return f"{norm(entry.get('ts'))}|{norm(entry.get('ref_id'))}"


def resolved_ids(entries: list[dict]) -> set[str]:
    """place_id()s the user acknowledged as no longer waiting in the Robinhood app (journal RESOLVED_EVENT entries,
    written only by `resume --proposals`, which needs a terminal)."""
    out: set[str] = set()
    for e in entries:
        if e.get("event") == RESOLVED_EVENT and isinstance(e.get("places"), list):
            out |= {x for x in e["places"] if isinstance(x, str)}
    return out


def unsettled(places: list[dict], entries: list[dict], inbox) -> list[dict]:
    """The journal place entries in `places` not yet seen finished: no order listing captured after the call (and no
    journal fill event after it, from reconcile) shows their order filled, cancelled or rejected (SETTLED_STATES), and
    the user has not acknowledged them as resolved (`resume --proposals`: resolved_ids). A live order is matched by
    its order id; a proposal (no order id) by same_order, each listing order settling at most one place.
    Conservative: a place nothing matches, or with an unreadable timestamp, stays unsettled."""
    done = resolved_ids(entries)
    places = [e for e in places if place_id(e) not in done]
    if not places:
        return []
    stamps = [t for t in (_ts_or_none(e.get("ts")) for e in places) if t is not None]
    rows = _listing_rows(inbox, {_kind(e.get("tool")) for e in places}, min(stamps)) if stamps else {}
    for e in entries:                                # reconcile's fills, for orders no capture shows any more
        if e.get("event") == "fill" and e.get("order_id") and norm(e["order_id"]) not in rows:
            at = _ts_or_none(e.get("ts"))
            if at is not None:
                kind = "crypto" if e.get("kind") == "crypto" else "equity"
                rows[norm(e["order_id"])] = (at, kind, {
                    "id": e["order_id"], "ref_id": e.get("ref_id"), "symbol": e.get("symbol"), "side": e.get("side"),
                    "quantity": e.get("cumulative_quantity"), "state": e.get("state")}, False)
    used, out = set(), []
    for e in sorted(places, key=lambda x: str(x.get("ts") or "")):
        ts, kind = _ts_or_none(e.get("ts")), _kind(e.get("tool"))
        hit = None
        if ts is not None and e.get("order_id"):
            oid = norm(e["order_id"])
            v = rows.get(oid)
            if v and v[0] >= ts and _row_state(v[2]) in SETTLED_STATES:
                hit = oid
        elif ts is not None:
            for oid, (at, k, r, priced) in rows.items():
                if (oid not in used and k == kind and at >= ts and _row_state(r) in SETTLED_STATES
                        and same_order(e, r, kind, price=priced)):
                    hit = oid
                    break
        if hit is None:
            out.append(e)
        else:
            used.add(hit)
    return out


def awaiting_approval(entries: list[dict], inbox, now: datetime) -> list[dict]:
    """This system's place calls of the last PENDING_LOOKBACK (7 days, rolling: an ET date change never resets it)
    that may still wait for the user's approval in the Robinhood app: journal state proposal_pending_approval? or
    failed_or_unknown (the call may have created one), not since seen settled and not acknowledged by the user
    (unsettled). Conservative: a rejected proposal that no order listing shows counts until the user acknowledges it
    with `resume --proposals` (or it is 7 days old), and a place with an unreadable timestamp counts until
    acknowledged."""
    since = now - PENDING_LOOKBACK
    cands = []
    for e in entries:
        if e.get("event") != "place" or e.get("state") not in (PROPOSAL_STATE, FAILED_STATE) or e.get("order_id"):
            continue
        ts = _ts_or_none(e.get("ts"))
        if ts is None or ts >= since:
            cands.append(e)
    return unsettled(cands, entries, inbox)


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


def log(hook: str, tool, decision: str, reason: str, ref_id=None, secrets=(), extra: dict | None = None) -> None:
    """Append one JSON line to hook.log: ts, hook, tool, decision, reason (scrubbed), ref_id, then `extra`'s fields as
    given (the caller scrubs them). Never raises."""
    try:
        append_jsonl(paths()["hook_log"], {
            "ts": iso_z(utc_now()), "hook": hook, "tool": scrub(tool, secrets, digits=False), "decision": decision,
            "reason": scrub(reason, secrets), "ref_id": scrub(ref_id, secrets, digits=False) if ref_id else None,
            **(extra or {})})
    except Exception:
        pass
