"""Signals + account snapshot + config -> plan: orders, cancels, ref_ids, collars, caps (SPEC section 7).

The plan is the only source of order parameters. Every param is a string, named exactly as in the official
place_equity_order / place_crypto_order input schemas; Claude copies them verbatim and the PreToolUse hook compares
them exactly. Pure function of its inputs: the same signals, snapshot, config, time, attempt, flags, ledger and
journal give the same plan, plan_id and ref_ids.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from agentic import calendar as cal
from agentic import entry, ledger
from agentic.config import STOCK_SUFFIX, VALID_CLASSES, cli_command, crosscheck_applies, paths
from agentic.snapshot import code_for, mid, pair_for, quote_problem

EQUITY_PARAMS = ("account_number", "symbol", "side", "type", "quantity", "dollar_amount", "limit_price", "stop_price",
                 "time_in_force", "market_hours", "tax_lots", "ref_id")
CRYPTO_PARAMS = ("rhs_account_number", "symbol", "side", "type", "quantity", "dollar_amount", "limit_price",
                 "stop_price", "time_in_force", "tax_lots", "ref_id")
TOOLS = {"equity": ("place_equity_order", "review_equity_order", "cancel_equity_order", "account_number"),
         "crypto": ("place_crypto_order", "preview_crypto_order", "cancel_crypto_order", "rhs_account_number")}
FRACTIONAL_MSG = "fractional orders are market orders: re-run the plan in regular hours before 15:45 ET"
CANCEL_MSG = "re-run plan after the cancel settles"
REFETCH_MSG = "exact call under RE-FETCH QUOTES"
QUOTE_CHUNK = 20
WHOLE_MISS_FRAC = 0.10
ONE = Decimal(1)
CENT = Decimal("0.01")
STEP6 = Decimal("0.000001")


# ------------------------------------------------------------------ small helpers

def _d(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(repr(float(x)))


def _floor(x, step: Decimal) -> Decimal:
    return ((_d(x) / step).to_integral_value(rounding=ROUND_FLOOR) * step).quantize(step)


def _round(x, step: Decimal) -> Decimal:
    return ((_d(x) / step).to_integral_value(rounding=ROUND_HALF_UP) * step).quantize(step)


def _collared(q: dict, side: str, c: float) -> Decimal:
    """ask x (1 + collar) for buys, bid x (1 - collar) for sells, in exact decimal arithmetic."""
    return _d(q["ask"]) * (1 + _d(c)) if side == "buy" else _d(q["bid"]) * (1 - _d(c))


def _cents_up(q: Decimal, px: Decimal) -> Decimal:
    """An order's notional as the plan records it: rounded up to the cent, so caps hold on the recorded values."""
    return (q * px).quantize(CENT, rounding=ROUND_CEILING)


def _cents_down(x) -> Decimal:
    return _d(max(float(x), 0.0)).quantize(CENT, rounding=ROUND_FLOOR)


def _tick(price) -> Decimal:
    return Decimal("0.01") if price >= 1 else Decimal("0.0001")


def _fmt_qty(q: Decimal) -> str:
    s = format(q.normalize(), "f")
    return s if s != "-0" else "0"


def collar(frac: float, limits: dict, attempt: int) -> float:
    """frac x collar_ladder[attempt - 1] (the last rung for later attempts), capped at max_collar_frac."""
    ladder = list(limits.get("collar_ladder") or [1])
    return min(float(frac) * float(ladder[min(attempt, len(ladder)) - 1]), float(limits["max_collar_frac"]))


def ref_id(plan_id: str, key: str, attempt: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"moneyline|{plan_id}|{key}|{attempt}"))


def _plan_id(signals_date: str, core: list) -> str:
    return f"{signals_date}-{hashlib.sha1(json.dumps(core, sort_keys=True).encode()).hexdigest()[:8]}"


def _flags(flags) -> dict[str, str]:
    if flags is None:
        return ledger.read_flags()
    if isinstance(flags, dict):
        return {k: ("" if v is True else str(v)) for k, v in flags.items()
                if k in ledger.FLAGS and v not in (None, False)}
    return {k: "" for k in flags if k in ledger.FLAGS}


def _signals_by_name(signals) -> dict[str, dict]:
    a = signals.get("assets", signals) if isinstance(signals, dict) else signals
    if isinstance(a, dict):
        return {str(v.get("name", k)): v for k, v in a.items() if isinstance(v, dict) and "target_frac" in v}
    return {str(s["name"]): s for s in a or [] if isinstance(s, dict) and s.get("name")}


def _signals_date(signals, now) -> str:
    s = signals if isinstance(signals, dict) else {}
    for k in ("date", "signals_date", "run_date"):
        if s.get(k):
            return str(s[k])[:10]
    gen = ledger.parse_ts(s.get("generated_at"))
    return (gen or now).date().isoformat()


def _expected_bar(asset_class: str, now) -> date:
    return cal.last_closed_crypto_bar(now) if asset_class == "crypto" else cal.last_closed_equity_session(now)


def _signal_problem(sig: dict | None, asset: dict, now) -> str | None:
    if sig is None:
        return "no signal for this asset in the signals file"
    if sig.get("errors"):
        return "signal errors: " + "; ".join(map(str, sig["errors"]))
    tf = ledger.num(sig.get("target_frac"))
    if tf is None or not -1e-9 <= tf <= 1 + 1e-9:
        return f"invalid target_frac {sig.get('target_frac')!r}"
    try:
        bar = date.fromisoformat(str(sig.get("bar_date"))[:10]) if sig.get("bar_date") else None
    except ValueError:
        return f"unreadable bar_date {sig.get('bar_date')!r}"
    if bar is not None:
        exp = _expected_bar(asset["class"], now)
        if bar < exp:
            return f"signal is for bar {bar} but bar {exp} has closed: re-run signals"
        if bar > exp:
            return f"signal bar {bar} is after the last closed bar {exp} (forming bar?)"
    return None


def _tranche_text(sig: dict | None) -> str:
    parts = []
    for k, t in enumerate((sig or {}).get("tranches") or [], 1):
        if not isinstance(t, dict):
            continue
        green = bool(t.get("green"))
        n = int(t.get("n_entry" if green else "n_exit") or 1)
        s = f"tranche {k}: {'green' if green else 'red'}"
        if n > 1:
            s += f", {n}/{n} closes {'above' if green else 'below'} the line"
        pend, n_next = int(t.get("pending") or 0), int(t.get("n_exit" if green else "n_entry") or 1)
        if pend:
            s += f", {pend}/{n_next} toward a flip"
        parts.append(s)
    return "; ".join(parts)


def _cancel(o: dict, acct: dict, reason: str) -> dict:
    tool, acct_key = TOOLS[o["kind"]][2], TOOLS[o["kind"]][3]
    return dict(tool=tool, params={acct_key: str(acct.get(acct_key) or ""), "order_id": str(o["id"])},
                symbol=o.get("symbol"), side=o.get("side"), reason=reason)


def _same_symbol(kind: str, a, b) -> bool:
    if kind == "crypto":
        return code_for(a or "") == code_for(b or "")
    return str(a or "").upper() == str(b or "").upper()


def _matches(o: dict, po: dict) -> bool:
    """An open order is this plan order: same ref_id, or (approved proposals carry another id) same params."""
    p = po["params"]
    if o.get("ref_id") and o["ref_id"] == p["ref_id"]:
        return True
    if o["kind"] != po["kind"] or not _same_symbol(o["kind"], o.get("symbol"), p["symbol"]):
        return False
    if o.get("side") != p["side"] or (o.get("type") or p["type"]) != p["type"] or o.get("qty") is None:
        return False
    if _d(o["qty"]) != Decimal(p["quantity"]):
        return False
    return "limit_price" not in p or (o.get("price") is not None and _d(o["price"]) == Decimal(p["limit_price"]))


# ------------------------------------------------------------------ the plan

class _Ctx:
    """Mutable state while sizing one plan: caps left, the plan lists, the shared settings."""

    def __init__(self, plan, snapshot, cfg, now, attempt, day_left):
        self.plan, self.snap, self.cfg, self.now, self.attempt = plan, snapshot, cfg, now, attempt
        self.lim = cfg["limits"]
        self.day_left = day_left
        bp = snapshot.get("buying_power")
        cbp = snapshot.get("crypto_buying_power")
        if cbp is None:
            vals = [v for v in (bp, snapshot.get("cash")) if v is not None]
            cbp = min(vals) if vals else None
        self.bp = {"equity": bp or 0.0, "crypto": cbp or 0.0}
        self.market_open = cal.market_open(now) and cal.execution_session(now) == cal.et_date(now)

    def skip(self, it, reason: str, warn: bool = False):
        self.plan["skipped"].append(dict(asset=it["name"], reason=reason))
        if warn:
            self.plan["warnings"].append(f"{it['name']}: {reason}")


def _need_quote(plan: dict, it: dict, prob: str, error: bool) -> None:
    """A quote this plan needs is missing, stale or unusable: skip the asset with the exact call to repeat (collected
    in plan["refetch"]); an error too unless it is a universe coin's new entry (one candidate's quote must not block
    the plan)."""
    plan.setdefault("_need", {"equity": set(), "crypto": set()})[it["vtype"]].add(it["qkey"])
    if error:
        plan["errors"].append(f"{it['name']}: {prob}")
    plan["skipped"].append(dict(asset=it["name"], reason=(
        f"{prob}; re-fetch: get_{it['vtype']}_quotes for {it['qkey']} ({REFETCH_MSG}) once, then re-plan with the "
        f"same attempt (`{cli_command()} plan --attempt {plan['attempt']}`)")))


def _refetch_calls(plan: dict) -> list[dict]:
    need = plan.pop("_need", None) or {}
    out = []
    for kind in ("equity", "crypto"):
        syms = sorted(need.get(kind) or ())
        for i in range(0, len(syms), QUOTE_CHUNK):
            params = {"symbols": syms[i:i + QUOTE_CHUNK]}
            if kind == "crypto":
                params["rhs_account_number"] = plan["rhs_account_number"]
            out.append(dict(tool=f"get_{kind}_quotes", params=params, why="quotes this plan needs (missing or stale)"))
    return out


def _chunks(ctx: _Ctx, it: dict, qty: Decimal, per: Decimal, lpx: Decimal, step: Decimal, room: Decimal,
            min_size: Decimal = Decimal(0)) -> list[tuple[Decimal, Decimal]]:
    """Split `qty` into orders of at most `per`, keeping the cent-rounded notionals within `room`."""
    out, left = [], qty
    while left > 0:
        q = min(per, left)
        if _cents_up(q, lpx) > room:
            q = _floor(room / lpx, step)
        if q <= 0 or q < min_size:
            ctx.plan["warnings"].append(f"{it['name']}: last {_fmt_qty(left)} not ordered (max_day_usd / buying "
                                        "power, or below the minimum size)")
            break
        left -= q
        n = _cents_up(q, lpx)
        room -= n
        out.append((q, n))
    return out


def _equity_specs(ctx: _Ctx, it: dict, side: str, qty: Decimal, lpx: Decimal, full: bool,
                  want_usd: float, room: Decimal) -> list[dict]:
    """Equity orders for `qty` shares (6 dp) at the collared price `lpx`: whole-share limits, or one fractional
    market order (SPEC rules); notionals within `room`."""
    px = float(lpx)
    frac_ok = bool(it["asset"]["vehicle"].get("fractional")) or (full and qty != _floor(qty, ONE))
    whole = _floor(qty, ONE)
    rem = qty - whole
    fractional = False
    if rem > 0:
        wants = full or whole == 0 or float(rem) * px > WHOLE_MISS_FRAC * want_usd
        if wants and frac_ok:
            if ctx.market_open:
                fractional = True
            elif full and whole > 0:
                ctx.plan["warnings"].append(f"{it['name']}: {_fmt_qty(rem)} sh fractional remainder left; "
                                            f"{FRACTIONAL_MSG}")
            else:
                ctx.skip(it, FRACTIONAL_MSG, warn=full)
                return []
    if not fractional:
        qty = whole
        if qty <= 0:
            ctx.skip(it, f"{side} of ${want_usd:.2f} is less than one share at {px:.2f} and the vehicle is not "
                         "fractional", warn=full)
            return []
    cap = _cents_down(ctx.lim["max_order_usd"])
    per = _floor(cap / lpx, STEP6 if fractional else ONE)
    if per <= 0 and not fractional and frac_ok and ctx.market_open:
        fractional, per = True, _floor(cap / lpx, STEP6)
    if per <= 0:
        ctx.skip(it, f"one share costs more than max_order_usd ({ctx.lim['max_order_usd']})", warn=True)
        return []
    out = []
    for q, n in _chunks(ctx, it, qty, per, lpx, STEP6 if fractional else ONE, room):
        params = dict(symbol=it["vsym"], side=side, type="market" if fractional else "limit", quantity=_fmt_qty(q))
        if not fractional:
            params["limit_price"] = format(lpx, "f")
        params.update(time_in_force="gfd", market_hours="regular_hours")
        out.append(dict(params=params, notional=float(n)))
    return out


def _crypto_specs(ctx: _Ctx, it: dict, side: str, qty: Decimal, lpx: Decimal, inc: Decimal, pair: dict,
                  room: Decimal) -> list[dict]:
    min_size = _d(pair.get("min_order_size") or 0)
    min_usd = ledger.num(pair.get("min_order_quote_amount")) or 0.0
    if qty <= 0 or qty < min_size or float(qty * lpx) < min_usd:
        ctx.skip(it, f"{side} {_fmt_qty(qty)} {it['code']} is below the pair's minimum order size", warn=True)
        return []
    per = _floor(_cents_down(ctx.lim["max_order_usd"]) / lpx, inc)
    if per <= 0 or per < min_size:
        ctx.skip(it, "max_order_usd is below the pair's minimum order size", warn=True)
        return []
    out = []
    for q, n in _chunks(ctx, it, qty, per, lpx, inc, room, min_size):
        params = dict(symbol=it["vsym"], side=side, type="limit", quantity=_fmt_qty(q), limit_price=format(lpx, "f"),
                      time_in_force="gtc")
        out.append(dict(params=params, notional=float(n)))
    return out


def _pair_problem(pair: dict, side: str) -> str | None:
    if not pair:
        return None
    if pair.get("halted") or pair.get("display_only") or pair.get("tradability") == "untradable":
        return "pair is halted or not tradable"
    if pair.get("market_orders_only"):
        return "pair accepts market orders only; the plan uses limits"
    if (side, pair.get("tradability")) in (("buy", "sell_only"), ("sell", "buy_only")):
        return f"pair is {pair['tradability']}"
    return None


def _orders_for(ctx: _Ctx, it: dict, side: str) -> list[dict]:
    """Size one asset's trade on `side` within sellable, max_day_usd and (buys) buying power; returns specs."""
    lim, q = ctx.lim, it["quote"]
    prob = quote_problem(q, it["qkey"], ctx.now, lim["quote_max_age_min"])
    if prob:
        _need_quote(ctx.plan, it, prob, error=not (side == "buy" and it.get("candidate")))
        return []
    delta, m = abs(it["delta"]), it["mid"]
    if it["vtype"] == "equity":
        raw = _collared(q, side, collar(lim["equity_collar_frac"], lim, ctx.attempt))
        lpx = _round(raw, _tick(raw))
        px, step = float(lpx), STEP6
    else:
        pair = ctx.snap.get("pairs", {}).get(it["qkey"]) or {}
        if not pair.get("asset_increment") or not pair.get("quote_increment"):
            msg = f"no get_currency_pairs metadata for {it['qkey']} (size and price increments): capture it"
            ctx.plan["errors"].append(f"{it['name']}: {msg}")
            ctx.skip(it, msg)
            return []
        why = _pair_problem(pair, side)
        if why:
            ctx.skip(it, why, warn=True)
            return []
        step = Decimal(str(pair["asset_increment"]))
        tick = Decimal(str(pair["quote_increment"]))
        lpx = _round(_collared(q, side, collar(lim["crypto_collar_frac"], lim, ctx.attempt)), tick)
        px = float(lpx)
    if lpx <= 0 or step <= 0:
        msg = f"{it['qkey']}: price {format(lpx, 'f')} rounds to zero at its tick; cannot size an order"
        ctx.plan["errors"].append(f"{it['name']}: {msg}")
        ctx.skip(it, msg)
        return []
    if side == "sell":
        sellable = _floor(max(it["sellable"], 0.0), step)
        if sellable <= 0:
            ctx.skip(it, "nothing sellable now (shares held for other orders or unsettled)", warn=True)
            return []
        qty = sellable if it["full"] else min(_floor(delta / m, step), sellable)
    else:
        budget = min(delta, ctx.bp[it["vtype"]], ctx.day_left)
        if budget < float(lim["min_order_usd"]):
            ctx.skip(it, f"buy of ${delta:.2f} capped to ${max(budget, 0):.2f} by buying power / max_day_usd "
                         f"(below min_order_usd)", warn=True)
            return []
        if budget < delta - 0.005:
            ctx.plan["warnings"].append(f"{it['name']}: buy capped from ${delta:.2f} to ${budget:.2f} "
                                        "by buying power / max_day_usd")
        qty = _floor(budget / px, step)
        delta = budget
    cap_qty = _floor(max(ctx.day_left, 0.0) / px, step)
    if side == "sell" and qty > cap_qty:
        ctx.plan["warnings"].append(f"{it['name']}: sell capped from {_fmt_qty(qty)} to {_fmt_qty(cap_qty)} by "
                                    "max_day_usd (the hook would block the rest); raise the cap or sell in the app")
        qty = cap_qty
        if qty <= 0:
            ctx.skip(it, "max_day_usd reached: exit not placed", warn=True)
            return []
    room = _cents_down(min(ctx.day_left, ctx.bp[it["vtype"]]) if side == "buy" else ctx.day_left)
    if it["vtype"] == "equity":
        specs = _equity_specs(ctx, it, side, qty, lpx, it["full"] and side == "sell", delta, room)
    else:
        specs = _crypto_specs(ctx, it, side, qty, lpx, step, ctx.snap.get("pairs", {}).get(it["qkey"]) or {}, room)
    spent = sum(s["notional"] for s in specs)
    ctx.day_left -= spent
    if side == "buy":
        for k in ctx.bp:
            ctx.bp[k] -= spent
    return specs


def _vkey(kind: str, symbol) -> tuple[str, str]:
    return (kind, code_for(symbol or "") if kind == "crypto" else str(symbol or "").upper())


def _is_ours(o: dict, idx: dict, managed: set) -> bool:
    """This system's order: journaled (id, ref_id or an approved proposal's params), or agent-initiated on a vehicle
    an enabled asset trades. Anything else is the user's and is never cancelled by a plan."""
    return ledger.is_own_order(o, idx) or (o.get("agent_initiated") is True and _vkey(o["kind"], o.get("symbol"))
                                           in managed)


# ------------------------------------------------------------------ allocation

def _after_close(ts: list, asset_class: str, day) -> list:
    """The times in `ts` after the daily bar `day` (ISO) closed; [] for an unreadable day."""
    try:
        close = cal.bar_close(asset_class, date.fromisoformat(str(day)[:10]))
    except ValueError:
        return []
    return [t for t in ts if t >= close]


def _bought_after(ts: list, asset_class: str):
    """entry.entry_frac's bought_after(day): this system placed a buy of the vehicle after bar `day` closed."""
    return lambda day: bool(_after_close(ts, asset_class, day))


def _opened(sig: dict | None, ts: list, asset_class: str) -> str:
    """When this system first bought into the current green run (its earliest green flip), ISO; "" if it did not
    (held from before, or handed in): the order in which holdings keep their slots."""
    days = [t["last_green_flip_date"] for t in (sig or {}).get("tranches") or []
            if isinstance(t, dict) and t.get("green") and t.get("last_green_flip_date")]
    after = _after_close(ts, asset_class, min(days)) if days else []
    return ledger.iso_z(min(after)) if after else ""


def _class_caps(cfg: dict) -> dict[str, float]:
    caps = (cfg.get("allocation") or {}).get("class_max_frac")
    return dict(caps) if caps else {"crypto": float(cfg["limits"]["max_crypto_frac"]), "equity": 1.0}


def _liquidity(it: dict) -> float:
    """The signal's median daily dollar volume (close x volume over 30 bars; 0 without one)."""
    return ledger.num((it.get("sig") or {}).get("dollar_volume_usd")) or 0.0


def _favorites(cfg: dict) -> dict[str, int]:
    """allocation.favorites as {NAME: rank from 1}."""
    return {str(n).upper(): k for k, n in enumerate((cfg.get("allocation") or {}).get("favorites") or [], 1)}


def _fav_rank(it: dict, fav: dict | None) -> int | None:
    """The item's place in allocation.favorites (None if it is not one): by its asset name, and a stock universe stock
    also as TICKER-STOCK whatever its name (it is TICKER on a run where the crypto universe has no coin TICKER), so that
    spelling favors the stock in the scan and here alike. A bare name matches the asset of that name only: the coin,
    while the crypto universe has a coin of that name (README section 9)."""
    a = it["asset"]
    names, u = [str(it["name"]).upper()], a.get("universe")
    if isinstance(u, dict) and u.get("kind") == "equity":
        names.append(str((a.get("vehicle") or {}).get("symbol") or "").upper() + STOCK_SUFFIX)
    ks = [(fav or {})[n] for n in names if n in (fav or {})]
    return min(ks) if ks else None


def _tie(it: dict, order: dict, fav: dict | None = None) -> tuple:
    """Favorites first (earlier in allocation.favorites first), then config order, in which the universe's assets
    follow the explicit ones, the more liquid first, then by name (explicit assets keep their own order, whatever their
    class or liquidity)."""
    k = _fav_rank(it, fav) or 10**6
    if isinstance(it["asset"].get("universe"), dict):
        return k, 1, 0.0, -_liquidity(it), it["name"]
    return k, 0, float(order[it["name"]]), 0.0, ""


def _ranked(its: list[dict], priority: str, order: dict, fav: dict | None = None) -> list[dict]:
    """Slot priority: crypto_first / equity_first (that class first, then the newest green flip, then _tie: favorites,
    config order, liquidity, name), newest_flip (newest flip, then _tie), or config_order (config order only)."""
    if priority == "config_order":
        return sorted(its, key=lambda it: order[it["name"]])
    out = sorted(its, key=lambda it: _tie(it, order, fav))
    out.sort(key=lambda it: it.get("flip") or "", reverse=True)          # stable: ties keep _tie order
    if priority in ("crypto_first", "equity_first"):
        first = priority.split("_")[0]
        out.sort(key=lambda it: it["asset"]["class"] != first)
    return out


def _fixed_alloc(intents: list[dict], capital: float, caps: dict, warnings: list) -> dict:
    """Per-asset alloc_frac; a class over its cap is scaled down proportionally. Each asset counts at what the plan
    will hold: its target, but a green tranche the entry policy will not buy only as far as the position holds it."""
    def held_tf(it):
        if it.get("mid") is None:                        # a holding without a price counts at its target
            return it["tf"] if it["qty"] > 0 else 0.0
        return min(it["tf"], max(it["etf"], it["current_usd"] / it["nominal"] if it["nominal"] > 0 else 0.0))
    for cls in VALID_CLASSES:
        group = [it for it in intents if it["asset"]["class"] == cls]
        tot, cap = sum(it["nominal"] * held_tf(it) for it in group), float(caps.get(cls, 1.0)) * capital
        if tot > cap + 1e-9:
            for it in group:
                it["scale"] = cap / tot
            warnings.append(f"{cls} targets ${tot:.2f} scaled to the {cls} class cap ${cap:.2f}")
    return {"method": "fixed", "class_max_frac": caps}


def _slot_alloc(its: list[dict], reserved: list[tuple], capital: float, cfg: dict, order: dict, skip,
                blocked: tuple | None = None) -> dict:
    """Slots: each position is slot_frac x capital; room is handed out in this order, each class within its cap:
    1. what the sleeve holds counts at its value until it is sold (an exit or a trim frees room once the positions
       show it), and an enabled asset skipped this run whose sleeve holds shares counts at max(slot, value);
    2. green holdings, earliest first into their run (the journal's first buy since the run's first flip), keep
       their whole slot (a split position can add its second half later): the last one in gets what is left, so a
       holding that got a partial slot tops up only when capital frees up;
    3. new entries in priority order: a full slot, or a partial one if at least half a slot is left; otherwise the
       entry waits. A new entry buys only its entry_tf share of the slot.
    A position worth less than min_order_usd is dust: not a holding, it may compete as a new entry.
    `blocked` (flag, reason): BLOCK_BUYS / FLATTEN hand out no new slots."""
    al, lim = cfg["allocation"], cfg["limits"]
    slot, prio = float(al["slot_frac"]) * capital, al["priority"]
    room = {"*": capital, **{c: float(f) * capital for c, f in _class_caps(cfg).items()}}
    info = {"method": "slots", "priority": prio, "slot_frac": float(al["slot_frac"]), "slot_usd": round(slot, 2),
            "held": [], "new": [], "waiting": []}
    if blocked:
        info["blocked"] = blocked[0]

    def take(cls, usd):
        room["*"] -= usd
        room[cls] -= usd

    for a, value in reserved:                            # skipped assets whose sleeve still holds shares
        take(a["class"], max(slot, value or 0.0))
        info["held"].append(a["name"])
    fav = _favorites(cfg)
    ranked = _ranked(its, prio, order, fav)
    held = sorted((it for it in ranked if it["qty"] > 0 and it["current_usd"] >= float(lim["min_order_usd"])),
                  key=lambda it: (it.get("opened") or "", order[it["name"]]))
    for it in ranked:
        it["slot_usd"] = slot if it["qty"] > 0 else 0.0
    for it in held:                                      # 1. positions count until sold
        take(it["asset"]["class"], it["current_usd"])
        info["held"].append(it["name"])
    for it in held:                                      # 2. holdings keep their slot, earliest in first
        cls, cur = it["asset"]["class"], it["current_usd"]
        if it["tf"] <= 0:
            continue
        extra = max(min(slot - cur, room["*"], room[cls]), 0.0)
        take(cls, extra)
        it["cap_usd"] = cur + extra
        it["slot_note"] = f"held slot ${slot:.2f}" + (f", up to ${cur + extra:.2f} (the room left)"
                                                      if cur + extra < slot - 0.005 else "")
    held_ids, exiting = {id(it) for it in held}, any(it["tf"] <= 0 for it in held)
    wash = {str(x).upper() for x in cfg.get("wash_sale_block_symbols") or []}
    for it in ranked:                                    # 3. new entries
        cls = it["asset"]["class"]
        if id(it) in held_ids or it["etf"] <= 0 or (it.get("mid") is None and not it.get("no_quote")):
            continue
        it["slot_usd"] = 0.0                             # (a dust holding too) no buy unless it gets a slot
        if blocked:
            skip(it, blocked[1])
            continue
        if it.get("hold_only"):
            skip(it, f"hold only ({it['hold_only']}): no new buys")
            continue
        if it.get("no_buy"):
            skip(it, f"{it['no_buy']}: no buys")
            continue
        if it["vsym"] in wash:
            skip(it, f"{it['vsym']} is in wash_sale_block_symbols: no buys")
            continue
        avail = min(room["*"], room[cls])
        size = slot if avail >= slot - 0.005 else avail if avail >= slot / 2 - 0.005 else 0.0
        if size <= 0:
            capped = room[cls] < room["*"] - 0.005
            left = (f"the {cls} class cap leaves ${max(room[cls], 0):.2f}" if capped
                    else f"${max(room['*'], 0):.2f} of capital is free")
            why = (f"no free slot: {left} (< half a slot, ${slot / 2:.2f}; {prio}): waiting for a slot to free up"
                   + ("; an exit frees its room once the positions show it sold" if exiting else ""))
            info["waiting"].append({"asset": it["name"], "reason": why})
            skip(it, why)
            continue
        take(cls, size)
        it["slot_usd"] = size
        n = len(info["new"]) + 1
        fk = _fav_rank(it, fav) if prio != "config_order" else None
        why = f"#{n} by {prio}" + (f"; favorite #{fk}" if fk else "")
        it["slot_note"] = (f"new slot ${size:.2f} ({why})" if size >= slot - 0.005 else
                           f"partial slot ${size:.2f} of ${slot:.2f} ({why}; the room left)")
        info["new"].append({"asset": it["name"], "usd": round(size, 2), "partial": size < slot - 0.005})
    return info


def make_plan(signals, snapshot: dict, cfg: dict, now_utc=None, attempt: int = 1, flags=None, *,
              placed_today_usd: float | None = None, journal: list | None = None, sleeve: dict | None = None,
              strategy_start: str | None = None, crosscheck: dict | None = None) -> dict:
    """The plan for this run (SPEC section 7). `flags` None reads STOP / FLATTEN / BLOCK_BUYS from the state dir;
    `placed_today_usd` None reads the ledger; `journal` None reads journal.jsonl; `sleeve` None runs
    ledger.sleeve_status (the sleeve's own quantities and any position the orders do not explain); `strategy_start`
    None reads strategy_start.json (entry policy fresh_only); `crosscheck` {asset name: problem or None} from
    stocks.cross_check: a yfinance stock (config.crosscheck_applies) with a problem, or without an entry, is not bought
    (its exits still go through).

    Only the sleeve's own quantity of a vehicle is ever sold, and only this system's open orders are cancelled.
    Buys raise a position only up to the entry policy's share of the target; sells cut it only down to the target."""
    now = cal.as_utc(now_utc)
    attempt = int(attempt)
    if attempt < 1:
        raise ValueError("attempt starts at 1")
    lim = cfg["limits"]
    acct = cfg.get("account") or {}
    fl = _flags(flags)
    sdate = _signals_date(signals, now)
    sfile = (signals.get("signals_file") or signals.get("file")) if isinstance(signals, dict) else None
    plan = {"plan_id": None, "created_at": ledger.iso_z(now), "valid_until": None, "live": bool(cfg.get("live")),
            "attempt": attempt, "account_number": str(acct.get("account_number") or ""),
            "rhs_account_number": str(acct.get("rhs_account_number") or ""), "capital_usd": 0.0,
            "signals_file": sfile or f"signals/signals_{sdate}.json", "signals_date": sdate, "flags": sorted(fl),
            "orders": [], "cancels": [], "skipped": [], "warnings": [], "errors": [], "refetch": []}
    errors, warnings, skipped = plan["errors"], plan["warnings"], plan["skipped"]
    enabled = [a for a in cfg.get("assets", []) if a.get("enabled")]
    managed_v = {_vkey(a["vehicle"]["type"], a["vehicle"]["symbol"]) for a in enabled}
    vtypes = sorted({a["vehicle"]["type"] for a in enabled}) or ["equity"]
    plan["valid_until"] = ledger.iso_z(min(cal.valid_until(t, now, lim) for t in vtypes))
    plan["plan_id"] = _plan_id(sdate, [])

    errors.extend(snapshot.get("errors") or [])
    warnings.extend(snapshot.get("warnings") or [])
    for k in ("account_number", "rhs_account_number"):
        v = plan[k]
        if (not v or v.startswith("FILL-IN")) and (k == "account_number" or "crypto" in vtypes):
            errors.append(f"config account.{k} is not filled in")
        if snapshot.get(k) not in (None, "") and str(snapshot[k]) != v:
            errors.append(f"snapshot {k} differs from the config account")
    if snapshot.get("total_value") is None and not errors:
        errors.append("snapshot has no total_value")
    if errors:
        skipped.append(dict(asset="*", reason="plan blocked by errors: no orders or cancels"))
        return plan

    open_orders = list(snapshot.get("open_orders") or [])
    journal = ledger.read_journal() if journal is None else journal
    idx = ledger.journal_index(journal)

    if "STOP" in fl:
        why = f" ({fl['STOP']})" if fl["STOP"] else ""
        skipped.append(dict(asset="*", reason=f"STOP flag present{why}: no orders; this system's open orders are "
                                              "cancelled"))
        plan["cancels"] = [_cancel(o, acct, "STOP: pull this system's open orders") for o in open_orders
                           if not o.get("cancel_pending") and _is_ours(o, idx, managed_v)]
        for o in open_orders:
            if not o.get("cancel_pending") and not _is_ours(o, idx, managed_v):
                warnings.append(f"open {o['kind']} order {str(o['id'])[:8]} on {o.get('symbol') or '?'} was not "
                                "placed by this system: not cancelled (cancel it in the app if needed)")
        return plan

    status = ledger.sleeve_status(snapshot, journal=journal) if sleeve is None else sleeve
    mism = {_vkey(m["kind"], m["symbol"]): m for m in status.get("mismatches") or []}
    own_qty = status.get("sleeve") or {}

    flatten, block_buys = "FLATTEN" in fl, "BLOCK_BUYS" in fl
    capital = max(min(float(snapshot["total_value"]), float(cfg["capital"]["max_usd"])), 0.0)
    plan["capital_usd"] = round(capital, 2)
    placed = ledger.placed_usd(now) if placed_today_usd is None else float(placed_today_usd)
    ctx = _Ctx(plan, snapshot, cfg, now, attempt, float(lim["max_day_usd"]) - placed)
    sigs = _signals_by_name(signals)
    seen: dict[tuple, list[str]] = {}
    for a in enabled:
        v = a["vehicle"]
        key = (v["type"], code_for(v["symbol"]) if v["type"] == "crypto" else v["symbol"].upper())
        seen.setdefault(key, []).append(a["name"])

    recorded = entry.recorded_start() if strategy_start is None else (strategy_start or None)
    plan["strategy_start"] = entry.start_for(cfg.get("entry") or {}, recorded, sdate)    # the start used
    slots = (cfg.get("allocation") or {}).get("method") == "slots"
    buy_times: dict[tuple, list] = {}                    # vehicle -> when this system placed buys (journal)
    for p in idx["places"]:
        if p["side"] == "buy" and p["ts"] is not None:
            buy_times.setdefault(_vkey(p["kind"], p["symbol"]), []).append(p["ts"])
    intents = []
    for a in enabled:
        v, name = a["vehicle"], a["name"]
        crypto = v["type"] == "crypto"
        it = dict(asset=a, name=name, vtype=v["type"], vsym=str(v["symbol"]).upper(),
                  code=code_for(v["symbol"]) if crypto else None,
                  qkey=pair_for(v["symbol"]) if crypto else str(v["symbol"]).upper(), sig=sigs.get(name), scale=1.0,
                  notes=[], flip=None, slot_note="",
                  nominal=capital * float(cfg["allocation"]["slot_frac"] if slots else a["alloc_frac"]))
        it["slot_usd"] = it["nominal"]                   # fixed; slots hands out slots in _slot_alloc
        vkey = it["vkey"] = (v["type"], it["code"] if crypto else it["qkey"])
        if len(seen[vkey]) > 1:
            msg = f"enabled assets {', '.join(seen[vkey])} trade the same vehicle {it['vsym']}: enable one"
            errors.append(msg)
            skipped.append(dict(asset=name, reason=msg))
            continue
        if flatten:
            it["tf"] = it["etf"] = 0.0
        else:
            prob = _signal_problem(it["sig"], a, now)
            if prob:
                skipped.append(dict(asset=name, reason=prob))
                warnings.append(f"ALERT {name}: {prob}; asset skipped")
                continue
            it["tf"] = min(max(float(it["sig"]["target_frac"]), 0.0), 1.0)
            ecfg = it["ecfg"] = entry.effective(a, cfg)
            start = it["start"] = entry.start_for(ecfg, recorded, sdate)
            if ecfg["policy"] == "fresh_only" and start != plan["strategy_start"]:
                plan.setdefault("strategy_start_assets", {})[name] = start
            etf, it["notes"] = entry.entry_frac(it["sig"], ecfg, start)
            it["etf"], it["flip"] = min(etf, it["tf"]), entry.newest_flip(it["sig"], ecfg, start)
        if not status.get("baseline"):
            msg = f"no reconciled positions baseline: run `{cli_command()} run` (it reconciles first)"
            if msg not in errors:
                errors.append(msg)
            skipped.append(dict(asset=name, reason=msg))
            continue
        m = mism.get(vkey)
        if m is not None:
            msg = (f"{it['vsym']} position {m['captured']:g} differs from the {m['expected']:g} expected from the "
                   "baseline and this system's fills (positions captured before orders, a manual trade or an unknown "
                   "order): re-fetch orders, then positions; if it persists check the app and `reconcile --accept`")
            errors.append(f"{name}: {msg}")
            skipped.append(dict(asset=name, reason=msg))
            continue
        pos = snapshot.get("crypto_positions" if crypto else "equity_positions") or {}
        p = pos.get(it["code"] if crypto else it["qkey"]) or {}
        held, sell = float(p.get("qty") or 0.0), float(p.get("sellable") or 0.0)
        mine = float((own_qty.get(v["type"]) or {}).get(vkey[1]) or 0.0)
        it["qty"], it["sellable"] = min(held, mine), min(sell, mine)
        if held - mine > 1e-6:
            warnings.append(f"{name}: {held - mine:g} {it['vsym']} held outside this sleeve (the sleeve owns "
                            f"{mine:g}); the plan never sells them")
            big = ("the account is worth more than capital.max_usd and a managed vehicle holds shares outside the "
                   "sleeve: only the sleeve's own shares are traded")
            if float(snapshot.get("total_value") or 0) > float(cfg["capital"]["max_usd"]) + 1 and big not in warnings:
                warnings.append(big)
        it["quote"] = (snapshot.get("quotes") or {}).get(it["qkey"])
        uinfo = a.get("universe") if isinstance(a.get("universe"), dict) else {}
        it["hold_only"], it["uni"] = uinfo.get("hold_only"), bool(uinfo)
        if crosscheck_applies(a) and not flatten:
            cc = (crosscheck or {}).get(name, "not cross-checked against Robinhood's previous_close (plan through the "
                                              "CLI, which checks it)")
            if cc:
                it["no_buy"] = f"cross-check failed: {cc}"
                if it["qty"] > 0 or it["etf"] > 0:
                    warnings.append(f"ALERT {name}: {it['no_buy']}; buys blocked, exits allowed")
        it["candidate"] = bool(uinfo) and slots and it["qty"] <= 0       # a universe coin's possible new entry
        intents.append(it)

    def skip(it, reason):
        skipped.append(dict(asset=it["name"], reason=reason))

    order = {a["name"]: i for i, a in enumerate(cfg.get("assets", []))}
    in_plan = {it["name"] for it in intents}
    reserved = []                                        # (asset, sleeve value or None) of skipped holdings
    for a in enabled:
        vt, vs = a["vehicle"]["type"], a["vehicle"]["symbol"]
        q = float((own_qty.get(vt) or {}).get(_vkey(vt, vs)[1]) or 0)
        if a["name"] not in in_plan and q > 0:
            m = mid((snapshot.get("quotes") or {}).get(pair_for(vs) if vt == "crypto" else str(vs).upper()))
            reserved.append((a, None if m is None else q * m))
    caps = _class_caps(cfg)
    live = []
    for it in intents:
        name = it["name"]
        it["mid"], it["current_usd"] = None, 0.0
        if it["qty"] < 0:
            skipped.append(dict(asset=name, reason="short position: not handled"))
            warnings.append(f"{name}: short position in {it['vsym']}")
            continue
        nominal = it.get("nominal", 1.0)
        if it["qty"] == 0 and (it["etf"] <= 0 or nominal <= 0):     # nothing to buy now, nothing to sell
            live.append(it)
            continue
        it["mid"] = mid(it["quote"])
        if it["mid"] is None:
            prob = quote_problem(it["quote"], it["qkey"], now, lim["quote_max_age_min"]) or f"{it['qkey']}: no price"
            if it["candidate"]:                          # needs a quote only if it gets a slot (below)
                it["no_quote"] = prob
                live.append(it)
                continue
            _need_quote(plan, it, prob, error=True)
            if it["qty"] > 0:
                reserved.append((it["asset"], None))
            continue
        it["current_usd"] = it["qty"] * it["mid"]
        if it.get("ecfg") and it["nominal"] > 0 and it["current_usd"] >= float(lim["min_order_usd"]):
            ts, cls = buy_times.get(it["vkey"], []), it["asset"]["class"]     # tranches it already holds (not dust)
            etf, it["notes"] = entry.entry_frac(it["sig"], it["ecfg"], it["start"], it["current_usd"] / it["nominal"],
                                                _bought_after(ts, cls))
            it["etf"], it["opened"] = min(etf, it["tf"]), _opened(it["sig"], ts, cls)
        live.append(it)
    buy_flag = "FLATTEN" if flatten else "BLOCK_BUYS" if block_buys else None
    buy_block = (buy_flag, f"{buy_flag}: buys blocked" + (f" ({fl[buy_flag]})" if fl.get(buy_flag) else "")) \
        if buy_flag else None
    if slots:
        plan["allocation"] = _slot_alloc(live, reserved, capital, cfg, order, skip, buy_block)
    else:
        plan["allocation"] = _fixed_alloc(intents, capital, caps, warnings)

    sells, buys = [], []
    for it in live:
        name, slot, sc = it["name"], it["slot_usd"], it["scale"]
        band = max(float(lim["min_order_usd"]), float(lim["rebalance_band_frac"]) * slot)
        if it.get("no_quote") and slot > 0:              # a slot is held for it: fetch its quote and re-plan
            _need_quote(plan, it, it["no_quote"], error=False)
            continue
        if it["mid"] is None or (it["qty"] == 0 and slot <= 0):
            want = it["nominal"] * it["tf"] * sc
            if it["notes"] and want > max(float(lim["min_order_usd"]), float(lim["rebalance_band_frac"]) *
                                          it["nominal"]):
                skip(it, "; ".join(it["notes"]))
            continue
        full_usd, entry_usd, cur = slot * it["tf"] * sc, slot * it["etf"] * sc, it["current_usd"]
        entry_usd = min(entry_usd, it.get("cap_usd", entry_usd))       # slots: what the room lets it reach
        it["full"] = it["tf"] == 0 and it["qty"] > 0
        if it["uni"] and not slots and not it["full"]:   # fixed: a universe coin has no allocation of its own
            skip(it, "allocation.method fixed: universe coins have alloc_frac 0, so a held one is only sold on a red "
                     "flip or FLATTEN (no trims, no buys); use allocation.method slots")
            continue
        side = ("sell" if it["full"] or cur > full_usd + band else "buy" if cur < entry_usd - band else None)
        if side is None:
            if it.get("cap_usd") is not None and cur < slot * it["etf"] * sc - band:
                skip(it, f"no free capital: {it['slot_note']}; other holdings keep their slots")
            elif it["notes"] and cur < full_usd - band:                # only the entry policy holds this back
                skip(it, "; ".join(it["notes"]))
            continue
        if side == "buy" and it.get("hold_only"):
            skip(it, f"hold only ({it['hold_only']}): no new buys")
            continue
        if side == "buy" and it.get("no_buy"):
            skip(it, f"{it['no_buy']}: no buys")
            continue
        it["delta"] = -cur if it["full"] else (full_usd if side == "sell" else entry_usd) - cur
        reason = ("FLATTEN: " if flatten else "") + (f"target {cur / slot:.2f} -> " if slot > 0 else
                                                     "no allocation of its own (alloc_frac 0): target -> ") + \
            f"{it['etf'] if side == 'buy' else it['tf']:.2f}"
        detail = "" if flatten else _tranche_text(it["sig"])
        reason += f" ({detail})" if detail else ""
        reason += f"; {it['asset']['class']} cap x{sc:.2f}" if sc < 1 else ""
        if side == "buy":
            reason += "".join(f"; {x}" for x in it["notes"])
            reason += f"; {it['slot_note']}" if it["slot_note"] else ""
        reason += "; full exit of the sellable quantity" if it["full"] else ""
        it["reason"] = reason
        (sells if side == "sell" else buys).append(it)

    if slots:                                # buys never lift the sleeve above capital or a class above its cap
        prio = _ranked(buys, plan["allocation"]["priority"], order, _favorites(cfg))
        buys = [it for it in prio if it["qty"] > 0] + [it for it in prio if it["qty"] <= 0]
        slot = float(cfg["allocation"]["slot_frac"]) * capital
        used = {c: sum(slot if v is None else v for a, v in reserved if a["class"] == c) for c in VALID_CLASSES}
        for it in live:                      # positions count at their value until sold, whether or not a sell fills
            if it["mid"] is not None:
                used[it["asset"]["class"]] += it["current_usd"]
        kept_buys = []
        for it in buys:
            cls = it["asset"]["class"]
            free = min(capital - sum(used.values()), float(caps.get(cls, 1.0)) * capital - used[cls])
            if it["delta"] > free + 0.005:
                if free < float(lim["min_order_usd"]):
                    skip(it, f"no free capital: positions and earlier buys already fill capital ${capital:.2f} or "
                             f"the {cls} class cap")
                    continue
                it["delta"] = free
                it["reason"] += f"; capped at the free capital ${free:.2f}"
            used[cls] += it["delta"]
            kept_buys.append(it)
        buys = kept_buys

    specs = []
    for side, group in (("sell", sells), ("buy", buys)):
        for it in group:
            if side == "buy":
                if buy_block:
                    skipped.append(dict(asset=it["name"], reason=buy_block[1]))
                    continue
                if it["vsym"] in {str(s).upper() for s in cfg.get("wash_sale_block_symbols") or []}:
                    skipped.append(dict(asset=it["name"],
                                        reason=f"{it['vsym']} is in wash_sale_block_symbols: no buys"))
                    continue
            for i, s in enumerate(_orders_for(ctx, it, side)):
                specs.append(dict(it=it, side=side, i=i, **s))

    orders = []
    for s in specs:
        it = s["it"]
        tool, preview, _, acct_key = TOOLS[it["vtype"]]
        orders.append(dict(key=f"{it['name']}|{it['vsym']}|{s['side']}|{s['i']}", asset=it["name"], kind=it["vtype"],
                           tool=tool, preview_tool=preview, params=dict(s["params"]),
                           notional_usd=round(s["notional"], 2), reason=it["reason"], acct_key=acct_key))
    core = [dict(key=o["key"], tool=o["tool"], params=o["params"]) for o in orders]
    plan["plan_id"] = pid = _plan_id(sdate, core)
    for o in orders:
        acct_key = o.pop("acct_key")
        o["params"] = {acct_key: plan[acct_key], **o["params"], "ref_id": ref_id(pid, o["key"], attempt)}
        allowed = EQUITY_PARAMS if o["kind"] == "equity" else CRYPTO_PARAMS
        if not set(o["params"]) <= set(allowed) or not all(isinstance(x, str) for x in o["params"].values()):
            raise RuntimeError(f"plan order {o['key']}: params must be strings named as in {o['tool']}")
        o["preview_params"] = {k: x for k, x in o["params"].items() if k != "ref_id"}

    blocked, foreign, kept = set(), set(), list(orders)
    for o in open_orders:
        match = next((po for po in kept if _matches(o, po)), None)
        if match is not None:
            kept.remove(match)
            skipped.append(dict(asset=match["asset"], reason=f"{match['key']}: already open ({o.get('state')}); "
                                                             "waiting for the fill or the approval"))
            continue
        ok = _vkey(o["kind"], o.get("symbol"))
        blocked.add(ok)
        if not _is_ours(o, idx, managed_v):
            if ok in managed_v:
                foreign.add(ok)
                warnings.append(f"open {o['kind']} order {str(o['id'])[:8]} on {o.get('symbol') or '?'} was not "
                                "placed by this system: cancel it in the Robinhood app; no new orders on that symbol "
                                "until it is gone")
            continue
        if not o.get("cancel_pending"):
            plan["cancels"].append(_cancel(o, acct, "stale order from an earlier plan"))
    used = {o.get("ref_id"): o for o in snapshot.get("orders") or [] if o.get("ref_id") and not o.get("open")}
    for po in list(kept):
        vk = _vkey(po["kind"], po["params"]["symbol"])
        if vk in foreign:
            kept.remove(po)
            skipped.append(dict(asset=po["asset"], reason=f"{po['key']}: {po['params']['symbol']} has an open order "
                                                          "this system did not place: cancel it in the app"))
        elif vk in blocked:
            kept.remove(po)
            skipped.append(dict(asset=po["asset"], reason=f"{po['key']}: {po['params']['symbol']} has an open order; "
                                                          f"cancel first, {CANCEL_MSG} (`{cli_command()} plan "
                                                          f"--attempt {attempt}`)"))
        elif po["params"]["ref_id"] in used:
            kept.remove(po)
            skipped.append(dict(asset=po["asset"], reason=f"{po['key']}: ref_id already used (order "
                                                          f"{used[po['params']['ref_id']].get('state')}); re-run "
                                                          f"with --attempt {attempt + 1} for a new order"))
    for po in kept:
        if po["kind"] == "equity" and po["params"]["side"] == "buy":
            losses = ledger.loss_sales(po["params"]["symbol"], now, journal)
            if losses:
                warnings.append(f"wash sale: {po['params']['symbol']} was sold at a loss on "
                                f"{str(losses[-1].get('ts'))[:10]} (within 30 days); this buy may disallow the loss")
    managed = {it["qkey"] for it in intents} | {pair_for(a["vehicle"]["symbol"]) if a["vehicle"]["type"] == "crypto"
                                                else a["vehicle"]["symbol"].upper() for a in enabled}
    for sym, p in sorted((snapshot.get("equity_positions") or {}).items()):
        if p.get("qty") and sym not in managed:
            warnings.append(f"position in {sym} is not managed by any enabled asset")
    for code, p in sorted((snapshot.get("crypto_positions") or {}).items()):
        if p.get("qty") and pair_for(code) not in managed:
            warnings.append(f"crypto position in {code} is not managed by any enabled asset")

    plan["orders"] = [{k: o[k] for k in ("key", "asset", "tool", "preview_tool", "params", "preview_params",
                                         "notional_usd", "reason")} for o in kept]
    plan["refetch"] = _refetch_calls(plan)
    kinds = sorted({o["kind"] for o in kept}) or vtypes
    plan["valid_until"] = ledger.iso_z(min(cal.valid_until(t, now, lim) for t in kinds))
    return plan


def write_plan(plan: dict, base=None):
    """Write plans/plan_<plan_id>.json and copy it to plan_current.json. Returns the plan file path. The first live
    plan records its signals date as the strategy start (strategy_start.json; entry policy fresh_only)."""
    p = paths(base)
    f = p["plans"] / f"plan_{plan['plan_id']}.json"
    ledger.write_json(f, plan)
    ledger.write_json(p["plan_current"], plan)
    if plan.get("live") is True:
        entry.record_start(plan["signals_date"], base)       # keeps an earlier recorded date
    return f


def format_plan(plan: dict, mask_accounts: bool = True) -> str:
    """Human summary and the tool calls in execution order: cancels, then sells, then buys (preview before place)."""
    def show(params):
        return json.dumps({k: ("<from plan>" if mask_accounts and k in ledger.ACCOUNT_KEYS else v)
                           for k, v in params.items()}, sort_keys=False)
    mode = "LIVE" if plan.get("live") else "SHADOW (place calls are blocked)"
    lines = [f"PLAN {plan['plan_id']}  attempt {plan['attempt']}  {mode}",
             f"created {plan['created_at']}  valid until {plan['valid_until']}  capital ${plan['capital_usd']:.2f}"]
    al = plan.get("allocation") or {}
    if al.get("method") == "slots":
        new = ", ".join(f"{x['asset']} ${x['usd']:.2f}{' (partial)' if x['partial'] else ''}" for x in al["new"])
        new = f"- ({al['blocked']})" if al.get("blocked") else new
        lines.append(f"SLOTS ${al['slot_usd']:.2f} each ({al['slot_frac']:.2f} x capital, {al['priority']}): held "
                     f"{', '.join(al['held']) or '-'}; new {new or '-'}; waiting "
                     f"{', '.join(x['asset'] for x in al['waiting']) or '-'}")
    n = 0
    for c in plan.get("cancels", []):
        n += 1
        lines.append(f"{n:>2}. {c['tool']} {show(c['params'])}  # {c.get('symbol')} {c.get('side')}: {c['reason']}")
    for o in plan.get("orders", []):
        n += 1
        lines.append(f"{n:>2}. {o['preview_tool']} {show(o['preview_params'])}")
        lines.append(f"    {o['tool']} {show(o['params'])}  # ${o['notional_usd']:.2f} {o['key']}: {o['reason']}")
    if not n:
        lines.append("no tool calls")
    for c in plan.get("refetch") or []:
        lines.append(f"RE-FETCH QUOTES: {c['tool']} {show(c['params'])} (exact params under EXACT TOOL CALLS)")
    for title, key in (("SKIPPED", "skipped"), ("WARNINGS", "warnings"), ("ERRORS", "errors")):
        for x in plan.get(key, []):
            lines.append(f"{title}: " + (f"{x['asset']}: {x['reason']}" if isinstance(x, dict) else str(x)))
    return "\n".join(lines)
