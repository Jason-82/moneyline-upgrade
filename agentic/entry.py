"""Entry policy: may a green tranche be bought now, or did its run start too long ago (HANDOFF 5.4)?

Standard library only. signals.py and planner.py share this one implementation.

- `join`: any green tranche may be bought at any time.
- `join_recent`: only a tranche whose own confirmed green flip was at most `max_join_bars` bars ago (in the asset's
  own bar series) and, with `max_join_rise_frac`, whose last close is at most flip close x (1 + rise).
- `fresh_only`: join_recent, and the flip is on or after the strategy start date.

full_tf = sum(w_k * green_k) is the signal target; entry_tf = sum(w_k * green_k * eligible_k), plus the old tranches
a held position already covers (`entry_frac`). Buys raise a position only up to entry_tf; sells cut it only down to
full_tf, so a held position is never sold because its run is old.
"""
from __future__ import annotations

from agentic.config import DEFAULT_ENTRY, paths
from agentic.ledger import read_json, write_json

WAIT = "waiting for the next flip"


def effective(asset: dict, cfg: dict) -> dict:
    """The asset's entry config: defaults, then the global `entry` block, then the asset's own `entry`."""
    out = dict(DEFAULT_ENTRY)
    for d in (cfg.get("entry"), asset.get("entry")):
        out.update({k: v for k, v in (d or {}).items() if not str(k).startswith("_")})
    return out


def recorded_start(base=None) -> str | None:
    """The strategy start recorded by the first live plan (strategy_start.json), or None."""
    d = read_json(paths(base)["strategy_start"], None)
    return str(d["date"])[:10] if isinstance(d, dict) and d.get("date") else None


def record_start(day: str, base=None) -> str:
    """Record `day` as the strategy start unless one is already recorded; returns the recorded date."""
    have = recorded_start(base)
    if have:
        return have
    write_json(paths(base)["strategy_start"], {"date": str(day)[:10], "note": "first live plan (entry fresh_only)"})
    return str(day)[:10]


def start_for(ecfg: dict, recorded: str | None, signals_date: str) -> str:
    """fresh_only's start: entry.start_date, else the recorded first live plan, else today's signals date (shadow
    mode before any live plan: nothing pre-existing qualifies)."""
    return str(ecfg.get("start_date") or recorded or signals_date)[:10]


def tranche_entry(t: dict, close, ecfg: dict, start: str | None) -> str | None:
    """None if this green tranche may be bought now, else why not (one line)."""
    policy = ecfg.get("policy", "join_recent")
    if policy == "join":
        return None
    n = int(ecfg.get("max_join_bars", 20))
    if "bars_since_green_flip" not in t:
        return "the signals file has no flip ages (written before the entry policy): re-run signals"
    bars, day = t.get("bars_since_green_flip"), t.get("last_green_flip_date")
    if bars is None or not day:
        return f"green with no flip in the available history, too late to join (max {n}): {WAIT}"
    if int(bars) > n:
        return f"green {int(bars)} bars, too late to join (max {n}): {WAIT}"
    rise, fc = ecfg.get("max_join_rise_frac"), t.get("flip_close")
    if rise is not None:
        if not fc or close is None:
            return "no flip close to check max_join_rise_frac against"
        if float(close) > float(fc) * (1 + float(rise)) + 1e-12:
            return (f"up {float(close) / float(fc) - 1:.1%} since the green flip {day} (max {float(rise):.0%}): "
                    f"{WAIT}")
    if policy == "fresh_only" and str(day)[:10] < str(start or "9999-12-31"):
        return f"flipped green {day}, before the strategy start {start} (fresh_only): {WAIT}"
    return None


def entry_frac(sig: dict, ecfg: dict, start: str | None, held: float = 0.0,
               bought_after=None) -> tuple[float, list[str]]:
    """(entry_tf, notes): the share of the signal target buys may raise a position to now, capped at target_frac, and
    one note per green tranche that may not be bought.

    With no position this is the sum of the eligible green weights. `held` (the sleeve's position as a share of the
    slot) covers, first, the eligible tranches the sleeve bought after their flip (`bought_after(flip_date)`), then
    the green tranches that may not be bought: an old tranche the sleeve already holds stays held and a fresh one is
    added on top, while the day after a fresh-tranche buy the old tranche is not bought instead."""
    tf = float(sig.get("target_frac") or 0.0)
    if ecfg.get("policy", "join_recent") == "join":
        return tf, []
    tranches = [t for t in sig.get("tranches") or [] if isinstance(t, dict)]
    elig = bought = 0.0
    old = []
    for k, t in enumerate(tranches, 1):
        if not t.get("green"):
            continue
        w, why = float(t.get("weight") or 0.0), tranche_entry(t, sig.get("close"), ecfg, start)
        if why is None:
            elig += w
            day = t.get("last_green_flip_date")
            bought += w if bought_after is not None and day and bought_after(str(day)[:10]) else 0.0
        else:
            old.append((k, w, why))
    left = min(max(float(held) - bought, 0.0), sum(w for _, w, _ in old))   # old tranches the position holds
    total, notes = elig + left, []
    for k, w, why in old:
        if left >= 0.9 * w:                     # held (within whole-share rounding): nothing to wait for
            left -= w
            continue
        left = 0.0
        notes.append(f"tranche {k} {why}" if len(tranches) > 1 else why)
    if tf > 0 and not tranches:
        notes.append("no tranche data in the signal: cannot check the entry policy")
    return round(min(total, tf), 6), notes


def newest_flip(sig: dict, ecfg: dict, start: str | None) -> str | None:
    """The most recent green flip date among the tranches that may be bought now (slot priority), or None."""
    days = [str(t.get("last_green_flip_date")) for t in (sig or {}).get("tranches") or []
            if isinstance(t, dict) and t.get("green") and t.get("last_green_flip_date")
            and tranche_entry(t, sig.get("close"), ecfg, start) is None]
    return max(days) if days else None
