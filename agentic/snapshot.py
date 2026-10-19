"""Account snapshot from the raw Robinhood MCP captures in the inbox (SPEC sections 6 and 8).

Field names follow the official tool output schemas (tools/list capture, 2026-10-12): every result is
{"data": {...}, "guide": "..."}; equity quotes are data.results[].quote{...}; crypto quote symbols come back
unhyphenated ('ETHUSD'); equity orders are data.orders[], crypto orders data.results[]. Wrappers and a few
alternative shapes (data.quotes[], flat quote rows, no "data" level) are accepted too.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentic import calendar as cal
from agentic.config import direct_crypto_possible
from agentic.data import unwrap_mcp
from agentic.hooks import capture_message, capture_problem
from agentic.ledger import ET, iso_z, num, parse_ts

UTC = timezone.utc
EQUITY_OPEN_STATES = {"new", "queued", "unconfirmed", "confirmed", "partially_filled", "pending_cancelled",
                      "locating"}
CRYPTO_OPEN_STATES = {"new", "queued", "unconfirmed", "confirmed", "partially_filled"}
CANCEL_PENDING_STATES = {"pending_cancelled", "pending_canceled"}
ORDER_LISTING_INPUTS = {"account_number", "rhs_account_number", "cursor", "created_at_gte", "state_group"}
EQUITY_ACCOUNT_TOOLS = ("get_portfolio", "get_equity_positions", "get_equity_orders")
CRYPTO_ACCOUNT_TOOLS = ("get_crypto_positions", "get_crypto_orders")
DEFAULT_ASSET_INCREMENT = "0.000001"
DEFAULT_QUOTE_INCREMENT = "0.01"


def short_tool(name: str) -> str:
    return str(name or "").rsplit("__", 1)[-1]


def pair_for(symbol: str) -> str:
    """Pair key of a crypto vehicle symbol: 'SOL' or 'SOL-USD' -> 'SOL-USD'."""
    s = str(symbol).upper().strip()
    return s if "-" in s else f"{s}-USD"


def code_for(symbol: str) -> str:
    """Asset code of a crypto vehicle symbol: 'SOL-USD' -> 'SOL'."""
    return str(symbol).upper().strip().split("-")[0]


def _pair_from_quote(sym: str) -> str:
    s = str(sym or "").upper().strip()
    if "-" in s:
        return s
    return f"{s[:-3]}-USD" if s.endswith("USD") and len(s) > 3 else f"{s}-USD"


def payload(response):
    """The tool's result payload: unwraps the MCP envelope, then the official {"data": ...} level."""
    r = unwrap_mcp(response)
    if isinstance(r, dict) and isinstance(r.get("data"), (dict, list)):
        return r["data"]
    return r


def _rows(data, *keys) -> list[dict]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for k in keys:
            if isinstance(data.get(k), list):
                return [r for r in data[k] if isinstance(r, dict)]
    return []


def _stamp(name: str) -> datetime | None:
    try:
        return datetime.strptime(name.split("_", 1)[0], "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def load_captures(inbox_dir, pattern: str = "*.json") -> list[dict]:
    """Inbox captures oldest first: {file, short, tool, at, input, data, error}. A capture that holds no tool JSON
    (Claude Code's 'too large' notice, or other text) has `error` set to a message that says what to do. `pattern`:
    only these files (e.g. "*_get_equity_tradability.json")."""
    out = []
    d = Path(inbox_dir)
    if not d.is_dir():
        return out
    for f in sorted(d.glob(pattern)):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(c, dict) or "tool" not in c:
            continue
        cap = dict(file=f.name, tool=c.get("tool"), short=short_tool(c.get("tool")),
                   at=parse_ts(c.get("captured_at")) or _stamp(f.name),
                   input=c.get("tool_input") if isinstance(c.get("tool_input"), dict) else {}, data=None, error=None)
        prob = (c["capture_error"], c.get("response_head") or "") if c.get("capture_error") else \
            capture_problem(c.get("response"))
        try:
            if prob:
                raise ValueError(capture_message(*prob))
            cap["data"] = payload(c.get("response"))
        except (ValueError, TypeError, AttributeError) as exc:
            cap["error"] = str(exc) if prob else f"{exc.__class__.__name__}: {exc}"
        if cap["at"] is not None:
            out.append(cap)
    out.sort(key=lambda c: (c["at"], c["file"]))
    return out


# ------------------------------------------------------------------ parsers (one result payload each)

def parse_portfolio(data) -> dict:
    d = data if isinstance(data, dict) else {}
    bp = d.get("buying_power")
    if isinstance(bp, dict):
        vals = [v for v in (num(bp.get("buying_power")), num(bp.get("unleveraged_buying_power"))) if v is not None]
        bp = min(vals) if vals else None     # never plan on margin leverage
    else:
        bp = num(bp)
    cbp = d.get("crypto_buying_power")
    cbp = num(cbp.get("buying_power")) if isinstance(cbp, dict) else num(cbp)
    return dict(total_value=num(d.get("total_value")), cash=num(d.get("cash")), buying_power=bp,
                crypto_buying_power=cbp)


def parse_equity_positions(data) -> dict:
    out = {}
    for r in _rows(data, "positions", "results"):
        sym = str(r.get("symbol") or "").upper()
        q = num(r.get("quantity"))
        if not sym or q is None:
            continue
        sell = num(r.get("shares_available_for_sells"))
        out[sym] = dict(qty=q, sellable=q if sell is None else sell, avg_buy_price=num(r.get("average_buy_price")))
    return out


def parse_crypto_positions(data) -> dict:
    out = {}
    for r in _rows(data, "results", "positions"):
        cur = r.get("currency") if isinstance(r.get("currency"), dict) else {}
        if str(cur.get("type") or "").lower() == "fiat":
            continue
        code = str(cur.get("code") or r.get("currency_code") or r.get("symbol") or "").upper()
        q = num(r.get("quantity"))
        if not code or q is None:
            continue
        sell = num(r.get("quantity_transferable"))
        out[code_for(code)] = dict(qty=q, sellable=q if sell is None else sell, pair_id=r.get("currency_pair_id"))
    return out


def _quote_ts(row: dict, keys_primary, keys_fallback, tz, captured: datetime) -> datetime:
    ts = [t for t in (parse_ts(row.get(k), tz) for k in keys_primary) if t is not None]
    if not ts:
        ts = [t for t in (parse_ts(row.get(k), tz) for k in keys_fallback) if t is not None]
    t = max(ts) if ts else captured
    return min(t, captured) if captured else t


def parse_equity_quotes(data, captured: datetime) -> dict:
    out = {}
    for r in _rows(data, "results", "quotes"):
        q = r.get("quote") if isinstance(r.get("quote"), dict) else r
        sym = str(q.get("symbol") or r.get("symbol") or "").upper()
        if not sym:
            continue
        ts = _quote_ts(q, ("venue_bid_time", "venue_ask_time", "updated_at"), ("venue_last_trade_time",), UTC, captured)
        problem = None
        if q.get("has_traded") is False:
            problem = "has never traded"
        elif q.get("state") not in (None, "", "active"):
            problem = f"instrument state is {q.get('state')!r}"
        pcd = q.get("previous_close_date")
        out[sym] = dict(bid=num(q.get("bid_price")), ask=num(q.get("ask_price")), last=num(q.get("last_trade_price")),
                        ts=iso_z(ts), captured_at=iso_z(captured), kind="equity", problem=problem,
                        previous_close=num(q.get("previous_close")),
                        previous_close_date=str(pcd)[:10] if pcd else None)
    return out


def parse_crypto_quotes(data, captured: datetime) -> dict:
    out = {}
    for r in _rows(data, "results", "quotes"):
        sym = r.get("symbol") or r.get("pair") or r.get("currency_pair")
        if not sym:
            continue
        mark = num(r.get("mark_price"))
        ts = _quote_ts(r, ("updated_at",), ("bid_time", "ask_time"), ET, captured)
        out[_pair_from_quote(sym)] = dict(bid=num(r.get("bid_price")), ask=num(r.get("ask_price")),
                                          last=mark if mark else None, ts=iso_z(ts), captured_at=iso_z(captured),
                                          kind="crypto", problem=None)
    return out


def parse_currency_pairs(data) -> dict:
    out = {}
    for r in _rows(data, "results", "pairs"):
        sym = str(r.get("symbol") or "").upper()
        if not sym:
            continue
        ac = r.get("asset_currency") if isinstance(r.get("asset_currency"), dict) else {}
        out[pair_for(sym)] = dict(
            id=r.get("id"), code=str(ac.get("code") or code_for(sym)).upper(),
            min_order_size=str(r.get("min_order_size") or "0"),
            asset_increment=str(r.get("min_order_quantity_increment") or r.get("asset_increment")
                                or DEFAULT_ASSET_INCREMENT),
            quote_increment=str(r.get("min_order_price_increment") or r.get("quote_increment")
                                or DEFAULT_QUOTE_INCREMENT),
            min_order_quote_amount=r.get("min_order_quote_amount"), tradability=r.get("tradability"),
            halted=bool(r.get("halted")), market_orders_only=bool(r.get("market_orders_only")),
            display_only=bool(r.get("display_only")))
    return out


def _open(r: dict, kind: str) -> bool:
    state = str(r.get("state") or "").lower()
    if kind == "crypto":
        grp = str(r.get("state_group") or r.get("derived_state") or "").lower()
        if grp in ("open", "closed"):
            return grp == "open"
        return state in CRYPTO_OPEN_STATES
    return state in EQUITY_OPEN_STATES


def parse_orders(data, kind: str, pair_codes: dict | None = None) -> list[dict]:
    """Orders of one get_equity_orders / get_crypto_orders payload in SPEC shape plus type, open, created_at."""
    out = []
    for r in _rows(data, "orders", "results"):
        if not r.get("id"):
            continue
        if kind == "crypto":
            sym = r.get("currency_code") or (pair_codes or {}).get(r.get("currency_pair_id")) or r.get("symbol")
            sym = code_for(sym) if sym else None
        else:
            sym = str(r.get("symbol") or "").upper() or None
        state = str(r.get("state") or "").lower()
        price = r.get("limit_price") if r.get("limit_price") not in (None, "") else r.get("price")
        out.append(dict(
            id=str(r["id"]), ref_id=r.get("ref_id"), symbol=sym, side=str(r.get("side") or "").lower(), state=state,
            qty=num(r.get("quantity")), filled=num(r.get("cumulative_quantity")) or 0.0, price=num(price),
            kind=kind, type=str(r.get("type") or "").lower(), open=_open(r, kind),
            cancel_pending=state in CANCEL_PENDING_STATES, created_at=r.get("created_at"),
            average_price=num(r.get("average_price")), agent_initiated=r.get("agent_initiated"),
            placed_agent=r.get("placed_agent") or r.get("initiator_type")))
    return out


# ------------------------------------------------------------------ capture selection

def _base_input(c: dict) -> dict:
    return {k: v for k, v in c["input"].items() if k != "cursor" and v not in (None, "")}


def _next(c: dict):
    return c["data"].get("next") if isinstance(c["data"], dict) else None


def _is_listing(c: dict) -> bool:
    if c["short"] not in ("get_equity_orders", "get_crypto_orders"):
        return True
    inp = _base_input(c)
    return set(inp) <= ORDER_LISTING_INPUTS and str(inp.get("state_group", "open")).lower() == "open"


def _sig(c: dict) -> str:
    return json.dumps(_base_input(c), sort_keys=True, default=str)


def _pages(caps: list[dict], short: str, sig: str | None = None) -> tuple[list[dict], bool]:
    """Newest complete fetch of a listing tool (with these base inputs, if `sig`): its newest first page plus the
    cursor pages captured after it."""
    cands = [c for c in caps if c["short"] == short and _is_listing(c) and (sig is None or _sig(c) == sig)]
    if not cands:
        return [], True
    firsts = [c for c in cands if not c["input"].get("cursor")]
    if not firsts:
        return [cands[-1]], False
    start = firsts[-1]
    pages, cur = [start], start
    while _next(cur) and len(pages) < 100:
        nxt = [c for c in cands if c["at"] >= start["at"] and c["input"].get("cursor") == _next(cur)
               and _base_input(c) == _base_input(start)]
        if not nxt:
            return pages, False
        cur = nxt[-1]
        pages.append(cur)
    return pages, True


def _account_problem(c: dict, acct: dict) -> str | None:
    """Mismatch text (no account numbers in it) or None."""
    needs = ("account_number" if c["short"] in EQUITY_ACCOUNT_TOOLS else
             "rhs_account_number" if c["short"] in CRYPTO_ACCOUNT_TOOLS else None)
    for k in ("account_number", "rhs_account_number"):
        v = c["input"].get(k)
        if v not in (None, "") and str(v).strip() != str(acct.get(k) or "").strip():
            return f"{c['short']} capture {c['file']}: {k} differs from the configured agentic account"
    if needs and c["input"].get(needs) in (None, ""):
        return f"{c['short']} capture {c['file']}: no {needs} in tool_input, cannot verify the account"
    if c["short"] == "get_crypto_orders" and isinstance(c["data"], dict):
        echo = c["data"].get("rhs_account_number")
        if echo not in (None, "") and str(echo).strip() != str(acct.get("rhs_account_number") or "").strip():
            return f"get_crypto_orders capture {c['file']}: response belongs to a different account"
    return None


def quote_problem(quote: dict | None, symbol: str, now_utc, max_age_min: float) -> str | None:
    """Why `quote` cannot price an order now (missing, bid/ask <= 0, stale, not tradable), or None."""
    if not quote:
        return f"{symbol}: no quote captured; call get_{'crypto' if '-' in symbol else 'equity'}_quotes"
    if quote.get("problem"):
        return f"{symbol}: {quote['problem']}"
    if not (quote.get("bid") or 0) > 0 or not (quote.get("ask") or 0) > 0:
        return f"{symbol}: quote has bid/ask <= 0 (book closed or unavailable)"
    ts = parse_ts(quote.get("ts"))
    age = (cal.as_utc(now_utc) - ts).total_seconds() / 60 if ts else None
    if age is None or age > float(max_age_min):
        return (f"{symbol}: quote is {age:.0f} min old (max {float(max_age_min):g}); re-fetch quotes"
                if age is not None else f"{symbol}: quote has no usable timestamp")
    return None


def mid(quote: dict | None) -> float | None:
    """(bid + ask) / 2 when both are positive, else last."""
    if not quote:
        return None
    b, a = quote.get("bid") or 0, quote.get("ask") or 0
    if b > 0 and a > 0:
        return (b + a) / 2
    last = quote.get("last")
    return last if last and last > 0 else None


# ------------------------------------------------------------------ snapshot

def build_snapshot(inbox_dir, cfg: dict, now_utc=None, crypto: bool | None = None) -> dict:
    """Validated account snapshot (SPEC section 6) from the newest captures. Quote freshness is judged per planned
    order by the planner (quote_problem); everything else that is wrong is in `errors` / `warnings`. `crypto`: are
    crypto positions and orders required (None: config.direct_crypto_possible; the CLI also requires them while the
    account holds a coin, as fetch-list does)?"""
    now = cal.as_utc(now_utc)
    lim = cfg["limits"]
    acct = cfg.get("account") or {}
    caps = load_captures(inbox_dir)
    crypto_on = direct_crypto_possible(cfg) if crypto is None else crypto
    errors, warnings, info = [], [], {}
    snap = dict(as_of=None, total_value=None, cash=None, buying_power=None, crypto_buying_power=None,
                equity_positions={}, crypto_positions={}, quotes={}, open_orders=[], orders=[], pairs={},
                account_number=None, rhs_account_number=None, captures=info, errors=errors, warnings=warnings)
    used_at = []

    def listing(short: str, required: bool, max_age: float | None = None, sig: str | None = None):
        pages, complete = _pages(caps, short, sig)
        if not pages:
            if required:
                errors.append(f"missing capture: {short} (call it for the agentic account)")
            return None
        start = pages[0]
        age = (now - start["at"]).total_seconds() / 60
        info.setdefault(short, dict(file=start["file"], captured_at=iso_z(start["at"]), age_min=round(age, 1),
                                    pages=len(pages)))
        bad = [p for p in pages if p["error"]]
        mism = [m for m in (_account_problem(p, acct) for p in pages) if m]
        if mism:
            errors.extend(mism)
            return None
        if bad:
            msg = f"{short} capture {bad[0]['file']}: unreadable ({bad[0]['error']})"
            (errors if required else warnings).append(msg)
            return None
        if max_age is not None and age > max_age:
            if required:
                errors.append(f"{short} capture is {age:.0f} min old (max {max_age:g}); fetch it again")
            else:
                warnings.append(f"{short} capture is {age:.0f} min old; ignored")
            return None
        if age < -5:
            warnings.append(f"{short} capture is dated {-age:.0f} min in the future (clock?)")
        if not complete:
            msg = f"{short}: more pages exist (next cursor) but were not captured"
            (errors if short.endswith("_positions") else warnings).append(msg)
        used_at.append(start["at"])
        for k in ("account_number", "rhs_account_number"):
            if start["input"].get(k) not in (None, "") and snap[k] is None:
                snap[k] = str(start["input"][k])
        return pages

    snap_age = float(lim["snapshot_max_age_min"])
    pages = listing("get_portfolio", True, snap_age)
    if pages:
        snap.update(parse_portfolio(pages[0]["data"]))
        if snap["total_value"] is None:
            errors.append("get_portfolio: no total_value in the response")
    pages = listing("get_equity_positions", True, snap_age)
    for p in pages or []:
        snap["equity_positions"].update(parse_equity_positions(p["data"]))
    pages = listing("get_crypto_positions", crypto_on, snap_age)
    for p in pages or []:
        snap["crypto_positions"].update(parse_crypto_positions(p["data"]))

    for c in caps:
        if c["short"] == "get_currency_pairs" and not c["error"]:
            snap["pairs"].update(parse_currency_pairs(c["data"]))
    pair_codes = {v["id"]: v["code"] for v in snap["pairs"].values() if v.get("id")}
    pair_codes.update({v["pair_id"]: k for k, v in snap["crypto_positions"].items() if v.get("pair_id")})

    for short, kind, required in (("get_equity_orders", "equity", True), ("get_crypto_orders", "crypto", crypto_on)):
        sigs = []                                   # distinct listings (e.g. recent orders, open orders), newest first
        for c in reversed(caps):
            if c["short"] == short and _is_listing(c) and not c["input"].get("cursor") and _sig(c) not in sigs:
                sigs.append(_sig(c))
        pages = listing(short, required, snap_age, sigs[0] if sigs else None)
        if pages is None:
            continue
        groups = [pages]
        for sg in sigs[1:]:                         # other fresh listings are merged in (older ones are ignored)
            more, _ = _pages(caps, short, sg)
            if more and (now - more[0]["at"]).total_seconds() / 60 <= snap_age:
                got = listing(short, False, snap_age, sg)
                if got:
                    groups.append(got)
        start = min(g[0]["at"] for g in groups)
        page_ids = {id(p) for g in groups for p in g}
        latest = {}
        for g in reversed(groups):                  # the newest listing's view of an order wins
            for p in g:
                for o in parse_orders(p["data"], kind, pair_codes):
                    latest[o["id"]] = o
        for c in caps:                              # single-order lookups newer than the listing win
            if c["short"] != short or c["error"] or id(c) in page_ids or c["at"] < start or _is_listing(c):
                continue
            if _account_problem(c, acct):
                warnings.append(f"{short} capture {c['file']} is for another account; ignored")
                continue
            for o in parse_orders(c["data"], kind, pair_codes):
                latest[o["id"]] = o
        snap["orders"].extend(latest.values())
        snap["open_orders"].extend(o for o in latest.values() if o["open"])
        for o in latest.values():
            if o["open"] and not o["symbol"]:
                warnings.append(f"open {kind} order {o['id'][:8]}: unknown symbol (capture get_currency_pairs)")

    for c in caps:                                  # oldest first, so the newest quote per symbol wins
        if c["short"] not in ("get_equity_quotes", "get_crypto_quotes") or c["error"]:
            continue
        m = _account_problem(c, acct)
        if m:
            errors.append(m)
            continue
        parse = parse_equity_quotes if c["short"] == "get_equity_quotes" else parse_crypto_quotes
        snap["quotes"].update(parse(c["data"], c["at"]))

    if used_at:
        snap["as_of"] = iso_z(min(used_at))

    if snap["total_value"] is not None and not errors:
        tot, missing = snap["cash"] or 0.0, []
        for key, pos in list(snap["equity_positions"].items()) + [
                (pair_for(k), v) for k, v in snap["crypto_positions"].items()]:
            m = mid(snap["quotes"].get(key))
            if pos["qty"] and m is None:
                missing.append(key)
            tot += pos["qty"] * (m or 0.0)
        if missing:
            warnings.append(f"cannot cross-check total_value: no quote for {', '.join(sorted(missing))}")
        elif abs(tot - snap["total_value"]) > 0.02 * abs(snap["total_value"]) + 1.0:
            warnings.append(f"positions x mid + cash = {tot:.2f} differs from total_value {snap['total_value']:.2f} "
                            "by more than 2% + $1")
    for sym, pos in snap["equity_positions"].items():
        if pos["qty"] < 0:
            warnings.append(f"{sym}: short position ({pos['qty']:g})")
    return snap
