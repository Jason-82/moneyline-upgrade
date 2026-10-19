"""Phase 1 signal job (SPEC section 12): bar feeds -> data checks -> MoneyLine tranche targets -> signals + digest.

Runs without Robinhood access for Coinbase / yfinance / csv / tv_export signals. Robinhood-feed (stock) signals read
the get_equity_historicals captures that the PostToolUse hook saved to the inbox. With the crypto universe enabled
(universe.py) the generated coins are scanned too, and the signals file stores them and the universe report. Output
goes to the private state dir only: signals/signals_<run date UTC>.json and digests/digest_<run date UTC>.txt.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from agentic import calendar as cal
from agentic import data as feeds
from agentic import entry, universe
from agentic.config import crypto_universe, paths, tranches_for
from agentic.indicator import (TV_CONFIRM_N, TV_MODES, moneyline_confirmed, read_tv_export, tranche_targets,
                               tv_export_targets)
from agentic.ledger import iso_z, write_json
from analysis_2026.moneyline_ref import atr as _atr

TV_CONFIRM = ("count", "direction")    # signal.tv_confirm: ConfirmCount reaching 5 (default) or Direction == -1


def expected_bar_date(asset: dict, now_utc=None) -> date:
    """The bar a signal must end on: the last closed crypto bar (UTC) or the last closed NYSE session."""
    if asset["class"] == "crypto":
        return cal.last_closed_crypto_bar(now_utc)
    return cal.last_closed_equity_session(now_utc)


def _f(x):
    """JSON-safe float (NaN/inf -> None)."""
    if x is None:
        return None
    v = float(x)
    return v if math.isfinite(v) else None


def _day(ts) -> str:
    return pd.Timestamp(ts).date().isoformat()


def _last_change(s: pd.Series) -> tuple[str | None, int]:
    """Date the current value of `s` began (None if it never changed) and the number of bars since."""
    v = s.to_numpy()
    ch = np.flatnonzero(v[1:] != v[:-1]) + 1
    if not len(ch):
        return None, len(v) - 1
    return _day(s.index[ch[-1]]), int(len(v) - 1 - ch[-1])


def _green_flip(up: np.ndarray, close: pd.Series) -> dict:
    """The last confirmed red -> green flip in `up` (bool per bar): its date, bars since (in this series) and close."""
    i = np.flatnonzero(up)
    if not len(i):
        return dict(last_green_flip_date=None, bars_since_green_flip=None, flip_close=None)
    j = int(i[-1])
    return dict(last_green_flip_date=_day(close.index[j]), bars_since_green_flip=int(len(close) - 1 - j),
                flip_close=_f(close.iloc[j]))


bar_close_time = cal.bar_close


def _check_tv(df: pd.DataFrame, expected: date, asset_class: str, saved_at: datetime | None = None) -> dict:
    """Data checks for a TradingView export (the indicator already ran on TradingView's bars). `saved_at`: the
    file's modification time; an export saved before the expected bar closed holds that bar half-formed."""
    errors, warnings = [], []
    if df.empty:
        return dict(errors=[f"no export rows on or before {expected}"], warnings=warnings)
    last = df.index[-1].date()
    if last != expected:
        errors.append(f"last closed bar in the export is {last}, expected {expected}: export a fresh CSV from "
                      "TradingView after the bar closes")
    elif saved_at is not None and saved_at < bar_close_time(asset_class, expected):
        errors.append(f"the export was saved at {iso_z(saved_at)}, before bar {expected} closed: its last row was "
                      "still forming; export again after the close")
    row = df.iloc[-1]
    for col in ("close", "Direction", "ConfirmCount", "MoneyLine Level"):
        if pd.isna(row.get(col)):
            errors.append(f"{col} is missing on the last bar")
    if not pd.isna(row.get("close")) and row["close"] <= 0:
        errors.append("non-positive close on the last bar")
    if len(df) >= 2 and not errors:
        prev_level, d, cnt = df["MoneyLine Level"].iloc[-2], row["Direction"], row["ConfirmCount"]
        imm = (d == -1 and cnt == 0) or (d == 1 and cnt >= 1)
        if not pd.isna(prev_level) and imm != bool(row["close"] > prev_level):
            warnings.append("Direction/ConfirmCount disagree with close vs the previous level on the last bar: "
                            "check the export settings")
    if {"open", "high", "low"} <= set(df.columns):
        warnings += feeds.check_bars(df, expected, 0, asset_class)["warnings"]
    return dict(errors=errors, warnings=warnings)


def _base(asset: dict, exp: date, cfg: dict) -> dict:
    s, v = asset["signal"], asset["vehicle"]
    al = cfg.get("allocation") or {}
    return dict(name=asset["name"], enabled=bool(asset.get("enabled")), alloc_frac=float(asset.get("alloc_frac", 0)),
                slot_frac=float(al["slot_frac"]) if al.get("method") == "slots" else None,   # slots ignore alloc_frac
                **{"class": asset["class"]}, mode=asset["mode"], source=s.get("source", "computed"),
                feed=s.get("feed") if s.get("source", "computed") == "computed" else "tv_export",
                signal_symbol=s.get("symbol") or (Path(str(s.get("path"))).name if s.get("path") else None),
                vehicle_type=v["type"], vehicle_symbol=str(v["symbol"]).upper(), bar_date=None,
                expected_bar_date=exp.isoformat(), bars=0, close=None, tranches=[], target_frac=None,
                prev_target_frac=None, changed=False, target_since=None, bars_in_state=None, line_n1=None,
                dist_to_line_pct=None, atr10=None, entry_policy=None, entry_frac=None, entry_notes=[], errors=[],
                warnings=[], dollar_volume_usd=None, held=False, universe=dict(asset["universe"])
                if isinstance(asset.get("universe"), dict) else None)


def _computed(out: dict, df: pd.DataFrame, asset: dict, cfg: dict) -> None:
    tr = tranches_for(asset, cfg)
    tt = tranche_targets(df, tr)
    n1 = moneyline_confirmed(df)
    close = float(df["close"].iloc[-1])
    for k, t in enumerate(tr):
        flips = tt.index[tt[f"flip{k}"].to_numpy() != 0]
        out["tranches"].append(dict(weight=t["weight"], n_entry=t["n_entry"], n_exit=t["n_exit"],
                                    green=bool(tt[f"g{k}"].iloc[-1]), pending=int(tt[f"pending{k}"].iloc[-1]),
                                    line=_f(tt[f"line{k}"].iloc[-1]),
                                    last_flip_date=_day(flips[-1]) if len(flips) else None,
                                    **_green_flip(tt[f"flip{k}"].to_numpy() == 1, df["close"])))
    out["close"] = close
    out["line_n1"] = _f(n1["line"].iloc[-1])
    out["atr10"] = _f(n1["atr"].iloc[-1])
    if out["line_n1"] is None:
        out["errors"].append("the MoneyLine is still in warm-up on the last bar")
    _targets(out, tt["target_frac"])


def _tv(out: dict, df: pd.DataFrame, asset: dict) -> None:
    how = str(asset["signal"].get("tv_confirm", "count")).lower()
    if how not in TV_CONFIRM:
        out["errors"].append(f"signal.tv_confirm must be one of {TV_CONFIRM}, not {how!r}")
        return
    t = tv_export_targets(df, asset["mode"])
    wi, wc = TV_MODES[asset["mode"]]
    conf = t["confirm_green_early"] if how == "count" else t["confirm_green"]
    ok = t["direction"].notna() & t["pending"].notna()
    frac = (wi * t["immediate_green"].astype(float) + wc * conf.astype(float)).where(ok)
    level = _f(t["level"].iloc[-1])
    for w, n, green in ((wi, 1, t["immediate_green"]), (wc, TV_CONFIRM_N, conf)):
        if w <= 0:
            continue
        since, _ = _last_change(green[ok])
        g = green[ok].to_numpy(bool)
        up = np.r_[False, g[1:] & ~g[:-1]]
        out["tranches"].append(dict(weight=w, n_entry=n, n_exit=n, green=bool(green.iloc[-1]),
                                    pending=0 if n == 1 or pd.isna(t["pending"].iloc[-1]) else
                                    int(t["pending"].iloc[-1]), line=level, last_flip_date=since,
                                    **_green_flip(up, df["close"][ok])))
    out["tv_confirm"] = how
    out["close"] = float(df["close"].iloc[-1])
    out["line_n1"] = level
    if {"high", "low"} <= set(df.columns):
        out["atr10"] = _f(_atr(df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float),
                               10, "rma")[-1])
    _targets(out, frac)


def _targets(out: dict, frac: pd.Series) -> None:
    cur = frac.iloc[-1]
    if pd.isna(cur):
        out["errors"].append("no target on the last bar (missing indicator values)")
        return
    out["target_frac"] = round(float(cur), 6)
    if len(frac) >= 2 and not pd.isna(frac.iloc[-2]):
        out["prev_target_frac"] = round(float(frac.iloc[-2]), 6)
        out["changed"] = abs(out["target_frac"] - out["prev_target_frac"]) > 1e-9
    out["target_since"], out["bars_in_state"] = _last_change(frac.dropna().round(9))
    if out["close"] and out["line_n1"]:
        out["dist_to_line_pct"] = round((out["line_n1"] / out["close"] - 1) * 100, 3)


def _entry(out: dict, asset: dict, cfg: dict, recorded: str | None, run_date: str) -> None:
    """entry_frac: the share of target_frac the entry policy lets a plan buy now (the planner recomputes it)."""
    e = entry.effective(asset, cfg)
    out["entry_policy"] = e["policy"]
    if out["target_frac"] is not None:
        out["entry_frac"], out["entry_notes"] = entry.entry_frac(out, e, entry.start_for(e, recorded, run_date))


def asset_signal(asset: dict, cfg: dict, now_utc=None, inbox_dir=None, strategy_start: str | None = None,
                 offline: bool = False) -> dict:
    """One asset's signal record (SPEC section 12). Feed and data problems go to `errors`; the planner skips such an
    asset entirely. Never raises for data problems. `strategy_start`: the recorded first live plan date (None reads
    the state dir). `offline`: Coinbase bars from the cache only (the universe scan found Coinbase unreachable)."""
    now = cal.as_utc(now_utc)
    recorded = entry.recorded_start() if strategy_start is None else strategy_start
    exp = expected_bar_date(asset, now)
    out = _base(asset, exp, cfg)
    s = asset["signal"]
    try:
        if out["source"] == "tv_export":
            raw = read_tv_export(s["path"])
            out["signal_file"] = Path(raw.attrs["path"]).name
        else:
            raw = feeds.get_bars(asset, cfg, now, inbox_dir, offline=True) if offline else \
                feeds.get_bars(asset, cfg, now, inbox_dir)
        src_file = raw.attrs.get("path")
    except Exception as exc:                       # one broken feed must not stop the other assets
        out["errors"].append(f"data: {type(exc).__name__}: {exc}")
        return out
    df = raw[raw.index <= pd.Timestamp(exp)]
    out["bars"] = int(len(df))
    if df.empty:
        out["errors"].append(f"no bars on or before the expected bar {exp}")
        return out
    out["bar_date"] = _day(df.index[-1])
    if out["source"] == "tv_export":
        saved = datetime.fromtimestamp(os.path.getmtime(raw.attrs["path"]), timezone.utc)
        chk = _check_tv(df, exp, asset["class"], saved)
    else:
        chk = feeds.check_bars(df, exp, int(asset.get("min_bars") or cfg["limits"]["min_bars"]), asset["class"])
        if s.get("feed") == "coinbase":
            dv = feeds.median_dollar_volume(df, universe.DV_BARS)
            out["dollar_volume_usd"] = None if dv is None else round(dv, 2)      # universe slot ties
        if s.get("feed") == "csv" and src_file and out["bar_date"] == exp.isoformat():
            saved = datetime.fromtimestamp(os.path.getmtime(src_file), timezone.utc)
            if saved < bar_close_time(asset["class"], exp, settled=True):
                chk["errors"].append(f"the CSV was saved at {iso_z(saved)}, before bar {exp} closed: its last row was "
                                     "still forming; save it again after the close")
    out["errors"] += chk["errors"]
    out["warnings"] += chk["warnings"]
    try:
        (_tv(out, df, asset) if out["source"] == "tv_export" else _computed(out, df, asset, cfg))
        _entry(out, asset, cfg, recorded, now.date().isoformat())
    except Exception as exc:
        out["errors"].append(f"indicator: {type(exc).__name__}: {exc}")
    return out


def compute_signals(cfg: dict, now_utc=None, inbox_dir=None, include_disabled: bool = False,
                    classes=None, build=None) -> dict:
    """Signals for every enabled asset (all assets with include_disabled; only `classes` if given), plus the crypto
    universe's coins when it is enabled (watch-only ones too), or, when it is off, the coins of its last scan that the
    sleeve still holds (hold only). `build`: universe.build_universe (tests)."""
    now = cal.as_utc(now_utc)
    inbox = Path(inbox_dir) if inbox_dir is not None else paths()["inbox"]
    keep = set(classes) if classes else None
    assets = [a for a in cfg.get("assets", []) if (include_disabled or a.get("enabled"))
              and (keep is None or a["class"] in keep)]
    run_date = now.date().isoformat()
    recorded = entry.recorded_start() or ""
    uni, offline = None, False
    if keep is None or "crypto" in keep:
        gen, report = (build or universe.build_universe)(cfg, now, inbox)
        if crypto_universe(cfg)["enabled"] or gen:
            uni = dict(assets=gen, report=report)
            assets = assets + gen
        offline = bool(report.get("coinbase_down"))                    # no more Coinbase requests this run
    held = universe.sleeve_vehicles()
    recs = [asset_signal(a, cfg, now, inbox, recorded, offline=offline) for a in assets]
    for r in recs:
        r["held"] = r["vehicle_symbol"] in held["crypto" if r["vehicle_type"] == "crypto" else "equity"]
    return dict(date=run_date, generated_at=iso_z(now), live=bool(cfg.get("live")),
                crypto_bar_date=cal.last_closed_crypto_bar(now).isoformat(),
                equity_bar_date=cal.last_closed_equity_session(now).isoformat(),
                classes=sorted(keep) if keep else None, signals_file=f"signals/signals_{run_date}.json",
                strategy_start=recorded or None, assets=recs, universe=uni)


def write_signals(sig: dict, base=None) -> Path:
    f = paths(base)["base"] / sig["signals_file"]
    write_json(f, sig)
    return f


def latest_signals(base=None) -> tuple[dict | None, Path | None]:
    """The newest signals_<date>.json (by date in the name), or (None, None)."""
    files = sorted(paths(base)["signals"].glob("signals_*.json"))
    for f in reversed(files):
        try:
            return json.loads(f.read_text(encoding="utf-8")), f
        except (OSError, ValueError):
            continue
    return None, None


# ------------------------------------------------------------------ digest

def _state(a: dict) -> str:
    gs = [t["green"] for t in a["tranches"]]
    if not gs:
        return "-"
    return "GREEN" if all(gs) else "RED" if not any(gs) else "PARTIAL"


def _action(a: dict) -> str:
    if a["errors"]:
        return "ERROR: no trade"
    if not a["enabled"]:
        u = a.get("universe") or {}
        return f"(watch: {u['reason'].split(':')[0]})" if u.get("outcome") == "watch" else "(disabled)"
    t, p, e = a["target_frac"], a["prev_target_frac"], a.get("entry_frac")
    if p is None or abs(t - p) < 1e-9:
        return "HOLD"
    if t == 0:
        return "EXIT"
    late = f" (may buy {e:.2f})" if t > p and e is not None and e < t - 1e-9 else ""
    return f"{'BUY' if t > p else 'SELL'} to {t:.2f}{late}"


def _fmt(x, spec: str, empty: str = "-") -> str:
    return empty if x is None else format(x, spec)


def _eligible(a: dict) -> bool:
    """May a plan buy into it today (enabled, not hold only, no errors, green, and the entry policy allows some)?"""
    return bool(a["enabled"] and not (a.get("universe") or {}).get("hold_only") and not a["errors"]
                and (a.get("target_frac") or 0) > 0 and (a.get("entry_frac") or 0) > 0)


def _asset_lines(a: dict) -> list[str]:
    src = "tv" if a["source"] == "tv_export" else a.get("feed") or "?"
    alloc = f"{(a['alloc_frac'] if a.get('slot_frac') is None else a['slot_frac']) * 100:.0f}%"
    dist = "-" if a["dist_to_line_pct"] is None else f"{a['dist_to_line_pct']:+.1f}%"
    name = a["name"] + ("*" if a.get("held") else "")
    lines = [f"{name:<9}{a['vehicle_symbol']:<9}{a['mode']:<11}{src:<10}{_state(a):<8}"
             f"{_fmt(a['bars_in_state'], 'd'):>5}  {'NEW' if a['changed'] else '-':<5}"
             f"{_fmt(a['line_n1'], '.4f'):>14}  {dist:>8}  "
             f"{_fmt(a['target_frac'], '.2f'):>6}  {_fmt(a['prev_target_frac'], '.2f'):>5}  {alloc:>5}  "
             f"{_action(a)}"]
    if len(a["tranches"]) > 1:
        for k, t in enumerate(a["tranches"], 1):
            n = t["n_exit"] if t["green"] else t["n_entry"]
            pend = f", {t['pending']}/{n} closes toward a flip" if t["pending"] else ""
            lines.append(f"    tranche {k} (w {t['weight']:.2f}, N {t['n_entry']}/{t['n_exit']}): "
                         f"{'green' if t['green'] else 'red'} since {t['last_flip_date'] or '?'}, "
                         f"line {_fmt(t['line'], '.4f')}{pend}")
    elif a["tranches"] and a["tranches"][0]["pending"]:
        t = a["tranches"][0]
        n = t["n_exit"] if t["green"] else t["n_entry"]
        lines.append(f"    {t['pending']}/{n} closes beyond the line toward a flip")
    if a.get("entry_notes") and not a["errors"]:
        lines += [f"    entry {a['entry_policy']}: {x}" for x in a["entry_notes"]]
    if (a.get("universe") or {}).get("hold_only"):
        lines.append(f"    hold only: {a['universe']['hold_only']}")
    lines += [f"    WARNING: {w}" for w in a["warnings"]]
    lines += [f"    ERROR: {e}" for e in a["errors"]]
    return lines


def format_digest(sig: dict, full: bool = False) -> str:
    """Text digest (plan section 9 style). Signal-level actions only; the plan sizes orders against positions.

    Readable with many assets: a SCAN summary line, the universe summary, then a table of the explicit assets and of
    every universe coin that is held (*), changed today, eligible to buy today or in error, then one line with the
    rest by state. `full` (signals --all): every asset in the table and every universe coin's outcome."""
    mode = "LIVE" if sig.get("live") else "SHADOW (live=false)"
    cb, eb = sig["crypto_bar_date"], sig["equity_bar_date"]
    assets = sig["assets"]
    gen = [a for a in assets if a.get("universe")]
    green = sum(1 for a in assets if not a["errors"] and _state(a) == "GREEN")
    partial = sum(1 for a in assets if not a["errors"] and _state(a) == "PARTIAL")
    lines = [f"MONEYLINE DIGEST {sig['date']}  generated {sig['generated_at']}  {mode}",
             f"crypto bar {cb} (closed 00:00 UTC next day) / stocks bar {eb} (closed 16:00 ET)",
             f"SCAN {len(assets)} assets ({len(assets) - len(gen)} explicit, {len(gen)} universe): {green} green, "
             f"{partial} partial, {sum(map(_eligible, assets))} eligible to buy today, "
             f"{sum(1 for a in assets if a.get('held'))} held (*), {sum(1 for a in assets if a['changed'])} changed "
             f"today, {sum(1 for a in assets if a['errors'])} with errors"]
    lines += universe.summary_lines((sig.get("universe") or {}).get("report"), full)
    shown = [a for a in assets if full or not a.get("universe") or a.get("held") or a["changed"] or _eligible(a)
             or a["errors"]]
    lines.append(f"{'ASSET':<9}{'VEHICLE':<9}{'MODE':<11}{'SRC':<10}{'STATE':<8}{'BARS':>5}  {'FLIP':<5}{'LINE':>14}  "
                 f"{'DIST':>8}  {'TARGET':>6}  {'PREV':>5}  {'ALLOC':>5}  ACTION")
    for a in shown:
        lines += _asset_lines(a)
    if not assets:
        lines.append("(no assets: enable some in config.json, or use --all)")
    rest = [a for a in assets if a not in shown]
    if rest:
        groups: dict[str, list[str]] = {}
        for a in rest:
            key = ("watch-only" if not a["enabled"] else
                   "GREEN, not eligible" if _state(a) == "GREEN" else "PARTIAL, not eligible"
                   if _state(a) == "PARTIAL" else _state(a))
            groups.setdefault(key, []).append(a["name"] + (f" ({_state(a)})" if key == "watch-only" else ""))
        order = ("GREEN, not eligible", "PARTIAL, not eligible", "RED", "watch-only", "-")
        lines.append("OTHERS (no action today): " + "; ".join(f"{k} ({len(groups[k])}): {', '.join(groups[k])}"
                                                             for k in order if k in groups))
    notes = []
    for a in shown:
        src = "tv" if a["source"] == "tv_export" else a.get("feed") or "?"
        notes.append(f"{a['name']}: {src} last bar {a['bar_date'] or '-'} ({a['bars']} bars)"
                     + (" OK" if not a["errors"] else ""))
    if rest:
        notes.append(f"{len(rest)} more OK")
    lines.append("Data: " + "; ".join(notes) if notes else "Data: -")
    lines.append("Check LINE against TradingView's closed daily bar (within 0.05%) before approving any order.")
    return "\n".join(lines)


def write_digest(sig: dict, text: str, base=None) -> Path:
    suffix = "_" + "_".join(sig["classes"]) if sig.get("classes") else ""
    f = paths(base)["digests"] / f"digest_{sig['date']}{suffix}.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text + "\n", encoding="utf-8")
    return f
