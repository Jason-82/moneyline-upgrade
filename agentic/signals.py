"""Phase 1 signal job (SPEC section 12): bar feeds -> data checks -> MoneyLine tranche targets -> signals + digest.

Runs without Robinhood access for Coinbase / yfinance / csv / tv_export signals. Robinhood-feed (stock) signals read
the get_equity_historicals captures that the PostToolUse hook saved to the inbox (through the Robinhood cache). With
the crypto universe (universe.py) or the stock universe (stocks.py) enabled, the generated assets are scanned too, and
the signals file stores them and the universe reports. Output goes to the private state dir only:
signals/signals_<run date UTC>.json and digests/digest_<run date UTC>.txt.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from agentic import calendar as cal
from agentic import data as feeds
from agentic import entry, stocks, universe
from agentic.config import crosscheck_applies, crypto_universe, equity_universe, paths, tranches_for
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
                 offline=False) -> dict:
    """One asset's signal record (SPEC section 12). Feed and data problems go to `errors`; the planner skips such an
    asset entirely. Never raises for data problems. `strategy_start`: the recorded first live plan date (None reads
    the state dir). `offline` (True, or a set of feed names): those bars from their caches only (the universe scan
    found Coinbase unreachable, or yfinance was already downloaded in one batch)."""
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
            raw = feeds.get_bars(asset, cfg, now, inbox_dir, offline=offline) if offline else \
                feeds.get_bars(asset, cfg, now, inbox_dir)
        src_file = raw.attrs.get("path")
        out["warnings"] += [n if n.startswith(feeds.SPLIT_NOTE) else f"skipped capture: {n}"
                            for n in raw.attrs.get("notes") or []]
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
        if "volume" in df.columns:                 # coinbase, yfinance, robinhood: slot ties by liquidity
            dv = feeds.median_dollar_volume(df, universe.DV_BARS)
            out["dollar_volume_usd"] = None if dv is None or dv <= 0 else round(dv, 2)
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


def _feed(asset: dict) -> str:
    s = asset.get("signal") or {}
    return "tv_export" if s.get("source", "computed") == "tv_export" else str(s.get("feed"))


def compute_signals(cfg: dict, now_utc=None, inbox_dir=None, include_disabled: bool = False,
                    classes=None, build=None, build_equity=None, skip_feeds=None) -> dict:
    """Signals for every enabled asset (all assets with include_disabled; only `classes` if given; none whose feed is
    in `skip_feeds`, e.g. the scheduled job skips robinhood), plus the crypto universe's coins and the stock universe's
    tickers when enabled (watch-only ones too), or, when off, the assets of their last scan that the sleeve still holds
    (hold only). yfinance stocks are downloaded in one batch first. `build` / `build_equity`: the universe builders
    (tests)."""
    now = cal.as_utc(now_utc)
    inbox = Path(inbox_dir) if inbox_dir is not None else paths()["inbox"]
    keep = set(classes) if classes else None
    skip = set(skip_feeds or ())
    every = [a for a in cfg.get("assets", []) if (include_disabled or a.get("enabled"))
             and (keep is None or a["class"] in keep)]
    assets = [a for a in every if _feed(a) not in skip]
    skipped = [a["name"] for a in every if _feed(a) in skip]
    run_date = now.date().isoformat()
    recorded = entry.recorded_start() or ""
    uni, uni_eq, offline, gen = None, None, set(), []
    if (keep is None or "crypto" in keep) and "coinbase" not in skip:
        gen, report = (build or universe.build_universe)(cfg, now, inbox)
        if crypto_universe(cfg)["enabled"] or gen:
            uni = dict(assets=gen, report=report)
            assets = assets + gen
        if report.get("coinbase_down"):
            offline.add("coinbase")                                     # no more Coinbase requests this run
    if (keep is None or "equity" in keep) and equity_universe(cfg)["feed"] not in skip:
        gen_eq, report_eq = (build_equity or stocks.build_equity_universe)(cfg, now, inbox, crypto_assets=gen)
        if equity_universe(cfg)["enabled"] or gen_eq:
            uni_eq = dict(assets=gen_eq, report=report_eq)
            assets = assets + gen_eq
            if equity_universe(cfg)["feed"] == "yfinance":
                offline.add("yfinance")                                 # downloaded in one batch just now
    yf = [a for a in assets if _feed(a) == "yfinance" and a["class"] == "equity" and not a.get("universe")]
    if yf:                                                              # explicit yfinance stocks: one batch too
        start = now.date() - timedelta(days=max(feeds.history_days(a, cfg) for a in yf))
        feeds.yfinance_daily_cached(sorted({str(a["signal"]["symbol"]).upper() for a in yf}), start, now)
        offline.add("yfinance")
    held = universe.sleeve_vehicles()
    recs = [asset_signal(a, cfg, now, inbox, recorded, offline=offline) for a in assets]
    quotes = None
    for r, a in zip(recs, assets):
        r["held"] = r["vehicle_symbol"] in held["crypto" if r["vehicle_type"] == "crypto" else "equity"]
        if crosscheck_applies(a) and not r["errors"]:
            quotes = stocks.latest_equity_quotes(inbox) if quotes is None else quotes
            stocks.signal_crosscheck(r, a, quotes)
    return dict(date=run_date, generated_at=iso_z(now), live=bool(cfg.get("live")),
                crypto_bar_date=cal.last_closed_crypto_bar(now).isoformat(),
                equity_bar_date=cal.last_closed_equity_session(now).isoformat(),
                classes=sorted(keep) if keep else None, skipped_feeds=sorted(skip) or None, skipped_assets=skipped,
                signals_file=f"signals/signals_{run_date}.json", strategy_start=recorded or None, assets=recs,
                universe=uni, universe_equity=uni_eq)


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


SIGNAL_NOTE = "SIGNAL is the indicator target, not an order; the plan lists orders"


def _signal(a: dict) -> str:
    """The indicator target's change since the previous bar, stated neutrally ('1.00->0.50', 'new 0.50', '-')."""
    if a["errors"]:
        return "ERROR: no trade"
    t, p, e = a["target_frac"], a["prev_target_frac"], a.get("entry_frac")
    if p is None or abs(t - p) < 1e-9:
        out = "-"
    elif p <= 1e-9:
        out = f"new {t:.2f}"
    else:
        out = f"{p:.2f}->{t:.2f}"
    if p is not None and t > p + 1e-9 and e is not None and e < t - 1e-9:
        out += f" (entry-eligible {e:.2f})"
    if not a["enabled"]:
        u = a.get("universe") or {}
        out += f" (watch: {u['reason'].split(':')[0]})" if u.get("outcome") == "watch" else " (disabled)"
    return out


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
             f"{_signal(a)}"]
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
    """Text digest (plan section 9 style). Indicator targets only (the SIGNAL column); the plan sizes orders against
    positions.

    Readable with many assets: a SCAN summary line, the universe summaries, then a table of the explicit assets and of
    every universe coin or stock that is held (*), changed today, eligible to buy today or in error, then one line with
    the rest by state. `full` (signals --all): every asset in the table and every universe asset's outcome."""
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
    if sig.get("skipped_feeds"):
        names = sig.get("skipped_assets") or []
        lines.append(f"SKIPPED feed {', '.join(sig['skipped_feeds'])} (needs Claude's captures; computed in /moneyline)"
                     + (f": {', '.join(names)}" if names else ""))
    lines += universe.summary_lines((sig.get("universe") or {}).get("report"), full)
    lines += stocks.summary_lines((sig.get("universe_equity") or {}).get("report"), full)
    shown = [a for a in assets if full or not a.get("universe") or a.get("held") or a["changed"] or _eligible(a)
             or a["errors"]]
    lines.append(f"{'ASSET':<9}{'VEHICLE':<9}{'MODE':<11}{'SRC':<10}{'STATE':<8}{'BARS':>5}  {'FLIP':<5}{'LINE':>14}  "
                 f"{'DIST':>8}  {'TARGET':>6}  {'PREV':>5}  {'ALLOC':>5}  SIGNAL")
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
        lines.append("OTHERS (no change today): " + "; ".join(f"{k} ({len(groups[k])}): {', '.join(groups[k])}"
                                                             for k in order if k in groups))
    if assets:
        lines.append(SIGNAL_NOTE)
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
    parts = list(sig.get("classes") or []) + [f"no-{f}" for f in sig.get("skipped_feeds") or []]
    suffix = "_" + "_".join(parts) if parts else ""
    f = paths(base)["digests"] / f"digest_{sig['date']}{suffix}.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text + "\n", encoding="utf-8")
    return f
