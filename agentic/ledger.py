"""Journal (jsonl), daily placed-notional ledger, flags (files, and the sticky STOP that hook.log records) and position
reconciliation.

Standard library only: the Claude Code hooks import this module. Everything here lives in the private state dir
(agentic.config.state_dir()); nothing it writes may be committed.

Formats:
- journal.jsonl: one JSON object per line, `ts` in UTC ("...Z"). Account numbers are stripped on append.
- ledger.json: {"YYYY-MM-DD" (ET date): {"placed_usd": float, "refs": {ref_id: notional_usd}}}. Adding the same
  ref_id twice counts once. Readers also accept a bare number or a list of {notional_usd} per day.
- positions_reconciled.json: {"as_of", "equity": {SYM: {qty, avg_buy_price}}, "crypto": {CODE: {qty}},
  "sleeve": {"equity": {SYM: qty}, "crypto": {CODE: qty}},
  "orders": {order_id: {kind, symbol, side, filled, state, created_at}}}. `sleeve` is the part of each position this
  system owns: config `sleeve_initial_qty` at the first baseline, then plus/minus the fills of its own orders.
  Anything else in the account (the user's own shares) is never sold by the plan.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentic import calendar as cal
from agentic import hooks
from agentic.config import paths
from agentic.hooks import STOP_LOG_HEADS

UTC = timezone.utc
ET = cal.ET                   # zoneinfo America/New_York, or the built-in US Eastern rule without a tz database
FLAGS = ("STOP", "FLATTEN", "BLOCK_BUYS")
ACCOUNT_KEYS = ("account_number", "rhs_account_number")
QTY_TOL = 1e-6
WASH_DAYS = 30


# ------------------------------------------------------------------ helpers

def iso_z(dt=None) -> str:
    return cal.as_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(x, default_tz=UTC) -> datetime | None:
    """Aware UTC datetime from ISO text ('Z', offset or naive in `default_tz`), epoch seconds, or a datetime."""
    if x is None or x == "":
        return None
    try:
        if isinstance(x, (int, float)):
            return datetime.fromtimestamp(float(x), UTC)
        if isinstance(x, datetime):
            dt = x
        else:
            dt = datetime.fromisoformat(str(x).strip().replace(" ", "T", 1))
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt.astimezone(UTC)


def num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def replace_file(src, dst, tries: int = 10) -> None:
    """os.replace, retried briefly on PermissionError: on Windows a replace fails while another process (a hook, an
    antivirus or search-indexer scan) has the destination open."""
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.05 * (i + 1))


def write_json(path: Path, obj) -> None:
    """Atomic write (a unique temp file in the same directory, then replace), UTF-8, '\\n' line endings."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(obj, indent=1, sort_keys=True, default=str))
        replace_file(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))      # with or without a UTF-8 BOM
    except (OSError, ValueError):
        return default


def redact(d: dict) -> dict:
    """Copy of `d` without account numbers (top level and in `params`)."""
    out = {k: v for k, v in d.items() if k not in ACCOUNT_KEYS}
    if isinstance(out.get("params"), dict):
        out["params"] = {k: v for k, v in out["params"].items() if k not in ACCOUNT_KEYS}
    return out


# ------------------------------------------------------------------ journal

def append_journal(entry: dict, base=None, now_utc=None) -> dict:
    """Append one event to journal.jsonl (adds `ts`, strips account numbers). Returns what was written."""
    e = redact(dict(entry))
    e.setdefault("ts", iso_z(now_utc))
    p = paths(base)["journal"]
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as fh:      # \n endings, like the hooks' binary appends
        fh.write(json.dumps(e, sort_keys=True, default=str) + "\n")
    return e


def read_journal(base=None, since=None) -> list[dict]:
    """Journal events oldest first; unreadable lines are skipped. `since` (datetime) keeps events at or after it."""
    p = paths(base)["journal"]
    if not p.exists():
        return []
    cut = cal.as_utc(since) if since is not None else None
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except (ValueError, RecursionError):        # RecursionError: deeply nested brackets on a damaged line
            continue
        if not isinstance(e, dict):
            continue
        if cut is not None:
            t = parse_ts(e.get("ts"))
            if t is None or t < cut:
                continue
        out.append(e)
    return out


def _field(e: dict, k: str):
    v = e.get(k)
    if v is None and isinstance(e.get("params"), dict):
        v = e["params"].get(k)
    if v is None and isinstance(e.get("fill"), dict):
        v = e["fill"].get(k)
    return v


FAILED = "failed_or_unknown"       # a place call that failed or timed out: the order may exist


def _is_place(e: dict) -> bool:
    tool = str(e.get("tool") or "")
    ev = str(e.get("event") or "")
    placed = tool.endswith(("place_equity_order", "place_crypto_order")) or ev.startswith("place")
    return placed and (not e.get("error") or e.get("state") == FAILED)


def loss_sales(symbol: str, now_utc=None, journal=None, base=None, days: int = WASH_DAYS) -> list[dict]:
    """Journaled equity sells of `symbol` in the last `days` whose average_price was below the avg_buy_price
    recorded at the time (wash-sale candidates). Crypto events are ignored."""
    now = cal.as_utc(now_utc)
    js = read_journal(base) if journal is None else journal
    sym = str(symbol).upper()
    out = []
    for e in js:
        if str(_field(e, "kind") or "equity") == "crypto" or str(_field(e, "side") or "").lower() != "sell":
            continue
        if str(_field(e, "symbol") or "").upper() != sym:
            continue
        t = parse_ts(e.get("ts"))
        px, basis = num(_field(e, "average_price")), num(_field(e, "avg_buy_price"))
        if t is None or px is None or basis is None or not (now - timedelta(days=days) <= t <= now):
            continue
        if px < basis:
            out.append(e)
    return out


# ------------------------------------------------------------------ daily notional ledger

def day_key(now_utc=None) -> str:
    """The ledger's day: the ET calendar date."""
    return cal.et_date(now_utc).isoformat()


def load_ledger(base=None) -> dict:
    d = read_json(paths(base)["ledger"], {})
    return d if isinstance(d, dict) else {}


def _day_total(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for k in ("placed_usd", "notional_usd", "total"):
            if num(v.get(k)) is not None:
                return float(v[k])
        if isinstance(v.get("refs"), dict):
            return float(sum(num(x) or 0.0 for x in v["refs"].values()))
        return 0.0
    if isinstance(v, list):
        return float(sum(num(x.get("notional_usd") if isinstance(x, dict) else x) or 0.0 for x in v))
    return num(v) or 0.0


def placed_usd(now_utc=None, base=None, day: str | None = None) -> float:
    """Notional placed on the ET date of `now_utc` (or `day`, 'YYYY-MM-DD')."""
    return _day_total(load_ledger(base).get(day or day_key(now_utc)))


def add_placed(notional_usd: float, ref_id: str | None = None, now_utc=None, base=None) -> float:
    """Record a successful place on today's ET date; the same ref_id is counted once. Returns the day's total."""
    led = load_ledger(base)
    k = day_key(now_utc)
    cur = led.get(k)
    if not isinstance(cur, dict) or not isinstance(cur.get("refs"), dict):
        prior = _day_total(cur)
        cur = {"refs": {"_prior": round(prior, 2)} if prior else {}}
    refs = cur["refs"]
    rid = str(ref_id) if ref_id else f"_anon{len(refs)}"
    if rid not in refs:
        refs[rid] = round(float(notional_usd), 2)
    cur["placed_usd"] = round(sum(num(v) or 0.0 for v in refs.values()), 2)
    led[k] = cur
    write_json(paths(base)["ledger"], led)
    return cur["placed_usd"]


# ------------------------------------------------------------------ flags

def read_flags(base=None, log: bool = True) -> dict[str, str]:
    """Active flags -> their text, e.g. {"BLOCK_BUYS": "reconcile: ETHA expected 10 got 12"}: the flag files, and
    (`log`) STOP while hook.log says it is active although the STOP file is missing (sticky STOP,
    hooks.sticky_stop; its text is hooks.sticky_stop_message). `log=False`: the files only."""
    p = paths(base)
    out = {}
    for f in FLAGS:
        if p[f].exists():
            try:
                out[f] = p[f].read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                out[f] = ""
    if log and "STOP" not in out:
        s = hooks.sticky_stop(p["hook_log"])
        if s is not None:
            out = {"STOP": hooks.sticky_stop_message(s), **out}
    return out


# Phrases of the PostToolUse hook's STOP reasons when an agent order went live without the user's approval.
BYPASS_MARKERS = ("without approval", "without a trade approval", "not approved in the app",
                  "approval cannot be confirmed")
BYPASS_ADVICE = ("APPROVAL BYPASS: an agent order went live without your approval in the Robinhood app (first live "
                 "day: Robinhood executed an order that came after 5 pending proposals). In the app's account "
                 "activity such an order shows a robot icon instead of 'you'. Check it, cancel it if it is still open "
                 "and unwanted, report it to Robinhood, confirm Trade approvals are ON, then run `resume` in your own "
                 "terminal.")


def flag_banner(flags: dict | None = None, base=None) -> list[str]:
    """Lines that `status`, `doctor` and the digest put first while a flag is set: STOP with its newest reasons (or,
    with the STOP file missing, that hook.log keeps STOP active and only `resume` clears it), and the APPROVAL BYPASS
    advice when a STOP reason is the hook's 'went live without approval' (shown until `resume`)."""
    fl = read_flags(base) if flags is None else flags
    out = []
    if "STOP" in fl:
        reasons = [x.strip() for x in str(fl["STOP"] or "").splitlines() if x.strip()]
        if reasons and reasons[0].startswith(STOP_LOG_HEADS):     # held by hook.log alone: the STOP file is missing
            out.append(f"!!! {reasons[0][:700]}. The hook blocks every place call (cancels still work).")
        else:
            out.append("!!! STOP is set: the hook blocks every place call (cancels still work). "
                       + ("Reason: " + " | ".join(r[:200] for r in reasons[-3:]) if reasons else "No reason recorded."))
        if any(m in r.lower() for r in reasons for m in BYPASS_MARKERS):
            out.append("!!! " + BYPASS_ADVICE)
    for name, what in (("FLATTEN", "sells toward 0 only"), ("BLOCK_BUYS", "buys blocked, exits allowed")):
        if name in fl:
            last = [x.strip() for x in str(fl[name] or "").splitlines() if x.strip()][-1:]
            out.append(f"!!! {name} is set: {what}" + (f". Reason: {last[0][:200]}" if last else ""))
    return out


def set_flag(name: str, reason: str = "", base=None) -> Path:
    if name not in FLAGS:
        raise ValueError(f"unknown flag {name!r}; one of {FLAGS}")
    f = paths(base)[name]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(reason.strip() + "\n", encoding="utf-8")
    return f


def clear_flag(name: str, base=None) -> bool:
    if name not in FLAGS:
        raise ValueError(f"unknown flag {name!r}; one of {FLAGS}")
    f = paths(base)[name]
    if f.exists():
        f.unlink()
        return True
    return False


# ------------------------------------------------------------------ reconcile

def _qtys(positions) -> dict[str, float]:
    out = {}
    for k, v in (positions or {}).items():
        q = num(v.get("qty") if isinstance(v, dict) else v)
        if q is not None:
            out[str(k).upper()] = q
    return out


def reconcile(expected: dict, captured: dict, tol: float = QTY_TOL) -> dict:
    """Compare expected with captured positions, both {"equity": {SYM: qty or {qty}}, "crypto": {CODE: ...}}.

    Any difference beyond `tol` is unexplained (manual trade, unknown order, corporate action): BLOCK_BUYS.
    Returns {ok, block_buys, mismatches[{kind, symbol, expected, captured, diff}], report[str]}."""
    mism, report = [], []
    for kind in ("equity", "crypto"):
        e, c = _qtys((expected or {}).get(kind)), _qtys((captured or {}).get(kind))
        for sym in sorted(set(e) | set(c)):
            ev, cv = e.get(sym, 0.0), c.get(sym, 0.0)
            if abs(cv - ev) > tol + 1e-9 * max(abs(ev), abs(cv)):
                mism.append(dict(kind=kind, symbol=sym, expected=ev, captured=cv, diff=cv - ev))
                report.append(f"{kind} {sym}: expected {ev:g}, captured {cv:g} (diff {cv - ev:+g})")
            elif ev or cv:
                report.append(f"{kind} {sym}: {cv:g} ok")
    if mism:
        report.append("unexplained position change: buys blocked until checked (exits stay allowed)")
    return dict(ok=not mism, block_buys=bool(mism), mismatches=mism, report=report)


def journal_index(journal: list[dict]) -> dict:
    """Order ids, ref_ids and place params this system journaled (successful places only)."""
    ids, refs, places = set(), set(), []
    for e in journal:
        if not _is_place(e):
            continue
        if e.get("order_id"):
            ids.add(str(e["order_id"]))
        if _field(e, "ref_id"):
            refs.add(str(_field(e, "ref_id")))
        places.append(dict(
            ts=parse_ts(e.get("ts")), symbol=str(_field(e, "symbol") or "").upper(),
            side=str(_field(e, "side") or "").lower(), quantity=num(_field(e, "quantity")),
            limit_price=num(_field(e, "limit_price")),
            kind="crypto" if "crypto" in str(e.get("tool") or "") else "equity"))
    return dict(order_ids=ids, ref_ids=refs, places=places)


def _base_symbol(sym: str) -> str:
    s = str(sym or "").upper()
    return s[:-4] if s.endswith("-USD") else s


def is_own_order(order: dict, index: dict) -> bool:
    """True if the journal shows this system placed `order` (by id, ref_id, or - for an approved proposal, which
    carries the approval's id - the same symbol/side/quantity/price placed shortly before it was created)."""
    if str(order.get("id")) in index["order_ids"] or (order.get("ref_id") and str(order["ref_id"]) in index["ref_ids"]):
        return True
    if order.get("agent_initiated") is False:
        return False
    created = parse_ts(order.get("created_at"))
    q, px = num(order.get("qty")), num(order.get("price"))
    for p in index["places"]:
        if p["kind"] != order.get("kind") or _base_symbol(p["symbol"]) != _base_symbol(order.get("symbol")):
            continue
        if p["side"] != str(order.get("side") or "").lower() or p["quantity"] is None or q is None:
            continue
        if abs(p["quantity"] - q) > QTY_TOL or (p["limit_price"] is not None and px is not None
                                               and abs(p["limit_price"] - px) > 1e-9 * max(1.0, px)):
            continue
        if created is None or p["ts"] is None or created >= p["ts"] - timedelta(minutes=10):
            return True
    return False


def _signed(o: dict, q: float) -> float:
    return q if str(o.get("side")).lower() == "buy" else -q


def _qty_of(captured: dict, kind: str) -> dict[str, float]:
    return _qtys(captured.get(kind))


def _initial_sleeve(initial: dict | None, captured: dict) -> dict:
    """config sleeve_initial_qty ({VEHICLE_SYMBOL: qty}) clamped to the captured positions."""
    out = {"equity": {}, "crypto": {}}
    for k, q in (initial or {}).items():
        k = str(k).upper()
        for kind, key in (("equity", k), ("crypto", _base_symbol(k))):
            have = _qty_of(captured, kind).get(key)
            if have:
                out[kind][key] = min(float(q), have)
    return out


def _expected(ref: dict, orders: list[dict], journal: list[dict], idx: dict, notes: list, fills: list):
    """Expected positions and sleeve quantities: the baseline plus fills of this system's orders since it."""
    ref_as_of = parse_ts(ref.get("as_of"))
    ref_orders = ref.get("orders") or {}
    exp = {k: dict(_qtys(ref.get(k))) for k in ("equity", "crypto")}
    sleeve = {k: dict(_qtys((ref.get("sleeve") or {}).get(k))) for k in ("equity", "crypto")}
    for o in orders:
        filled = num(o.get("filled")) or 0.0
        oid = str(o.get("id"))
        prev = ref_orders.get(oid)
        created = parse_ts(o.get("created_at"))
        if prev is not None:
            before = num(prev.get("filled")) or 0.0
        elif ref_as_of is None or created is None or created >= ref_as_of:
            before = 0.0
        else:
            if filled:
                notes.append(f"order {oid[:8]} predates the baseline and is not on record; ignored")
            continue
        delta = filled - before
        if abs(delta) <= QTY_TOL:
            continue
        sym = str(o.get("symbol") or "").upper()
        if not is_own_order(o, idx):
            notes.append(f"{o.get('kind')} {sym or '?'}: order {oid[:8]} not placed by this system filled "
                         f"{delta:g} ({o.get('side')})")
            continue
        kind = o.get("kind") or "equity"
        key = _base_symbol(sym) if kind == "crypto" else sym
        exp[kind][key] = exp[kind].get(key, 0.0) + _signed(o, delta)
        sleeve[kind][key] = max(sleeve[kind].get(key, 0.0) + _signed(o, delta), 0.0)
        fill = dict(event="fill", kind=kind, symbol=key, side=o.get("side"), order_id=oid,
                    ref_id=o.get("ref_id"), filled_delta=delta, cumulative_quantity=o.get("filled"),
                    average_price=o.get("average_price"), state=o.get("state"))
        basis = ((ref.get("equity") or {}).get(key) or {}) if kind == "equity" else {}
        if isinstance(basis, dict) and basis.get("avg_buy_price") is not None:
            fill["avg_buy_price"] = basis["avg_buy_price"]
        fills.append(fill)
    return exp, sleeve


def sleeve_status(snapshot: dict, base=None, journal=None) -> dict:
    """Read-only check the planner makes before trading (the same arithmetic as `reconcile`, nothing written).

    Returns {baseline, sleeve{equity, crypto}, mismatches[{kind, symbol, expected, captured, diff}]}: expected
    positions = positions_reconciled.json + fills of this system's orders since; a mismatch means positions and
    orders disagree (a capture race, a manual trade, an unknown order). `sleeve` caps what the plan may sell."""
    ref = read_json(paths(base)["positions_ref"], None)
    if not isinstance(ref, dict):
        return dict(baseline=False, sleeve={"equity": {}, "crypto": {}}, mismatches=[])
    js = read_journal(base) if journal is None else journal
    orders = snapshot.get("orders") or snapshot.get("open_orders") or []
    captured = {"equity": snapshot.get("equity_positions") or {}, "crypto": snapshot.get("crypto_positions") or {}}
    exp, sleeve = _expected(ref, orders, js, journal_index(js), [], [])
    return dict(baseline=True, sleeve=sleeve, mismatches=reconcile(exp, captured)["mismatches"])


def holds_crypto(base=None) -> bool:
    """The reconciled positions hold a coin, or this system placed a crypto order since that baseline. Crypto
    positions and orders must then be captured whatever the config says (reconcile compares them, and a held coin
    needs its exit), e.g. after direct_crypto or the crypto universe is turned off."""
    ref = read_json(paths(base)["positions_ref"], None)
    as_of = None
    if isinstance(ref, dict):
        own = (ref.get("sleeve") or {}).get("crypto")
        if any(q > QTY_TOL for q in list(_qtys(ref.get("crypto")).values()) + list(_qtys(own).values())):
            return True
        as_of = parse_ts(ref.get("as_of"))
    return any(p["kind"] == "crypto" and (as_of is None or p["ts"] is None or p["ts"] >= as_of - timedelta(days=1))
               for p in journal_index(read_journal(base))["places"])


def reconcile_snapshot(snapshot: dict, base=None, now_utc=None, write: bool = True, accept: bool = False,
                       initial_sleeve: dict | None = None) -> dict:
    """The `reconcile` command: expected = positions_reconciled.json + fills of this system's orders since then.

    On an unexplained change it writes BLOCK_BUYS (if `write`). New fills of own orders are journaled once (with
    the avg_buy_price on record, for the wash-sale check). When clean, or with `accept`, the captured positions
    become the new baseline. Without a baseline, the captured positions are adopted if the journal has no orders;
    the sleeve then starts at `initial_sleeve` (config sleeve_initial_qty), so shares already held are not the
    plan's to sell. Returns reconcile()'s dict plus `notes`, `fills`, `baseline_written` and `sleeve`."""
    now = cal.as_utc(now_utc)
    if snapshot.get("errors"):
        return dict(ok=False, block_buys=False, mismatches=[], fills=[], baseline_written=False, skipped=True,
                    sleeve=None, report=["snapshot has errors; nothing reconciled"] + list(snapshot["errors"]),
                    notes=[])
    p = paths(base)
    ref = read_json(p["positions_ref"], None)
    journal = read_journal(base)
    idx = journal_index(journal)
    orders = snapshot.get("orders") or snapshot.get("open_orders") or []
    captured = {"equity": snapshot.get("equity_positions") or {}, "crypto": snapshot.get("crypto_positions") or {}}
    notes, fills = [], []
    if not isinstance(ref, dict):
        sleeve = _initial_sleeve(initial_sleeve, captured)
        if accept or not (idx["order_ids"] or idx["ref_ids"] or idx["places"]):
            res = reconcile(captured, captured)
            notes.append("no baseline yet: captured positions adopted as the baseline")
            for kind in ("equity", "crypto"):
                for k, q in sorted(_qty_of(captured, kind).items()):
                    out = q - sleeve[kind].get(k, 0.0)
                    if out > QTY_TOL:
                        notes.append(f"{kind} {k}: {out:g} held before the first baseline are outside the sleeve: "
                                     "the plan never sells them (list them in sleeve_initial_qty to manage them)")
        else:
            res = dict(ok=False, block_buys=True, mismatches=[], report=[
                "no reconciled baseline but the journal has orders: check positions in the app, then run "
                "reconcile with accept to adopt them"])
        ref = {"as_of": None, "equity": {}, "crypto": {}, "orders": {}}
    else:
        exp, sleeve = _expected(ref, orders, journal, idx, notes, fills)
        if write:
            seen_fill = {(str(e.get("order_id")), str(e.get("cumulative_quantity")))
                         for e in journal if e.get("event") == "fill"}
            for fill in fills:
                if (fill["order_id"], str(fill["cumulative_quantity"])) not in seen_fill:
                    append_journal(fill, base, now)
        res = reconcile(exp, captured)
    if not res["ok"] and not accept:
        if write:
            set_flag("BLOCK_BUYS", "reconcile: " + "; ".join(res["report"][-3:]), base)
    written = False
    new_sleeve = {kind: {k: round(min(v, _qty_of(captured, kind).get(k, 0.0)), 9)
                         for k, v in sorted(sleeve[kind].items())
                         if min(v, _qty_of(captured, kind).get(k, 0.0)) > QTY_TOL} for kind in ("equity", "crypto")}
    if write and (res["ok"] or accept):
        new_orders = dict(ref.get("orders") or {})
        for o in orders:
            new_orders[str(o.get("id"))] = dict(kind=o.get("kind"), symbol=o.get("symbol"), side=o.get("side"),
                                                filled=o.get("filled"), state=o.get("state"),
                                                created_at=o.get("created_at"))
        cut = now - timedelta(days=120)
        new_orders = {k: v for k, v in new_orders.items()
                      if (parse_ts(v.get("created_at")) or now) >= cut}
        write_json(p["positions_ref"], {
            "as_of": snapshot.get("as_of") or iso_z(now),
            "equity": {k: {"qty": v.get("qty"), "avg_buy_price": v.get("avg_buy_price")}
                       for k, v in (snapshot.get("equity_positions") or {}).items()},
            "crypto": {k: {"qty": v.get("qty")} for k, v in (snapshot.get("crypto_positions") or {}).items()},
            "sleeve": new_sleeve, "orders": new_orders})
        written = True
    if write:
        append_journal(dict(event="reconcile", ok=res["ok"], block_buys=res["block_buys"] and not accept,
                            mismatches=len(res["mismatches"]), accepted=accept), base, now)
    return dict(res, block_buys=res["block_buys"] and not accept, notes=notes, fills=fills, baseline_written=written,
                skipped=False, sleeve=new_sleeve)
