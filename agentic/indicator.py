"""N-confirmed MoneyLine with separate entry/exit N, tranche targets, and the TradingView export reader (SPEC section 2).

`computed` source: the old MoneyLine replicated from OHLC (analysis_2026/moneyline_ref.py, reset-on-flip ATR10 x 2.0 on
hl2), generalised to flip only after N consecutive closes beyond the still-trailing line (flip_delay.moneyline_delay).
`tv_export` source: the new October 2026 TradingView MoneyLine, read from the user's CSV export.
"""
from __future__ import annotations

import glob
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026.moneyline_ref import atr as _atr

REPO = Path(__file__).resolve().parent.parent
TV_COLUMNS = {"Direction": "direction", "ConfirmCount": "confirmcount", "MoneyLine Level": "moneyline level"}
TV_MODES = {"immediate": (1.0, 0.0), "split": (0.5, 0.5), "confirm5": (0.0, 1.0)}   # (immediate, confirm) weights
TV_CONFIRM_N = 5


def _cols(df: pd.DataFrame, names) -> list[np.ndarray]:
    low = {str(c).lower(): c for c in df.columns}
    missing = [n for n in names if n not in low]
    if missing:
        raise KeyError(f"OHLC frame needs columns {missing}")
    return [df[low[n]].to_numpy(dtype=float) for n in names]


def moneyline_confirmed(df: pd.DataFrame, n_entry: int = 1, n_exit: int = 1, period: int = 10,
                        factor: float = 2.0) -> pd.DataFrame:
    """Reset-on-flip ATR stop that flips only after N consecutive closes beyond the trailing line.

    n_entry is the threshold while red (red -> green), n_exit while green. The line keeps trailing while a flip is
    pending; a close back inside resets the count; on the N-th close the line restarts at that bar's fresh band.
    n_entry = n_exit = 1 is moneyline_ref.moneyline exactly. Columns: green, line (NaN in warm-up), pending (0..N-1),
    flip (+1/-1/0), atr.
    """
    n_entry, n_exit = int(n_entry), int(n_exit)
    if n_entry < 1 or n_exit < 1:
        raise ValueError("n_entry and n_exit must be >= 1")
    h, l, c = _cols(df, ("high", "low", "close"))
    s = (h + l) / 2.0
    a = _atr(h, l, c, period, "rma")
    lo_raw, hi_raw = s - factor * a, s + factor * a
    m = len(c)
    green = np.zeros(m, bool)
    line = np.full(m, np.nan)
    pending = np.zeros(m, int)
    flip = np.zeros(m, int)
    started, is_green, stop, count = False, True, np.nan, 0
    for i in range(m):
        if np.isnan(a[i]):
            continue
        if not started:
            is_green = c[i] >= s[i]
            stop = lo_raw[i] if is_green else hi_raw[i]
            started = True
        else:
            if is_green:
                stop = max(stop, lo_raw[i])
                beyond, need = c[i] < stop, n_exit
            else:
                stop = min(stop, hi_raw[i])
                beyond, need = c[i] > stop, n_entry
            if beyond:
                count += 1
                if count >= need:
                    is_green = not is_green
                    stop = lo_raw[i] if is_green else hi_raw[i]
                    count = 0
                    flip[i] = 1 if is_green else -1
            else:
                count = 0
        line[i], green[i], pending[i] = stop, is_green, count
    return pd.DataFrame({"green": green, "line": line, "pending": pending, "flip": flip, "atr": a}, index=df.index)


def _tranche(t) -> tuple[float, int, int]:
    if isinstance(t, dict):
        return float(t["weight"]), int(t["n_entry"]), int(t["n_exit"])
    w, ne, nx = t
    return float(w), int(ne), int(nx)


def tranche_targets(df: pd.DataFrame, tranches, period: int = 10, factor: float = 2.0) -> pd.DataFrame:
    """Per-tranche N-confirmed state and target_frac = sum(weight_k * green_k).

    `tranches`: dicts {weight, n_entry, n_exit} (config.tranches_for) or (weight, n_entry, n_exit) tuples; weights
    must sum to 1. Columns: g0.., target_frac, pending0.., line0.., flip0...
    """
    ts = [_tranche(t) for t in tranches]
    if not ts or abs(sum(w for w, _, _ in ts) - 1.0) > 1e-9 or any(not 0 < w <= 1 for w, _, _ in ts):
        raise ValueError(f"tranche weights must be in (0, 1] and sum to 1: {ts}")
    cache: dict[tuple[int, int], pd.DataFrame] = {}
    g, pend, line, flip = {}, {}, {}, {}
    frac = np.zeros(len(df))
    for k, (w, ne, nx) in enumerate(ts):
        if (ne, nx) not in cache:
            cache[(ne, nx)] = moneyline_confirmed(df, ne, nx, period, factor)
        r = cache[(ne, nx)]
        g[f"g{k}"] = r["green"].to_numpy()
        pend[f"pending{k}"] = r["pending"].to_numpy()
        line[f"line{k}"] = r["line"].to_numpy()
        flip[f"flip{k}"] = r["flip"].to_numpy()
        frac = frac + w * g[f"g{k}"]
    return pd.DataFrame({**g, "target_frac": frac, **pend, **line, **flip}, index=df.index)


# ------------------------------------------------------------------ tv_export

def _key(name) -> str:
    return re.sub(r"\.\d+$", "", str(name)).strip().lower()


def _find(columns, prefix: str, exact: bool = False):
    for c in columns:
        k = _key(c)
        if (k == prefix) if exact else k.startswith(prefix):
            return c
    return None


def _bar_dates(t: pd.Series, tz: str) -> pd.DatetimeIndex:
    num = pd.to_numeric(t, errors="coerce")
    if num.notna().all():
        ts = pd.to_datetime(num, unit="ms" if num.abs().max() > 1e11 else "s", utc=True)
    else:
        ts = pd.to_datetime(t.astype(str), utc=True, format="ISO8601")
    if tz == "auto":
        tz = "UTC" if (ts == ts.dt.normalize()).all() else "America/New_York"
    return pd.DatetimeIndex(ts.dt.tz_convert(tz).dt.tz_localize(None).dt.normalize())


def read_tv_export(path_glob: str | Path, tz: str = "auto") -> pd.DataFrame:
    """Newest file (by mtime) matching the glob, parsed into a date-indexed frame.

    Relative globs resolve against the repo root. `time` may be unix seconds/ms or ISO. Bar dates: tz='auto' uses
    the UTC date when every bar opens at 00:00 UTC (crypto, labelled by the open) and the New York date otherwise
    (stocks); pass a zone name to force one. Columns: close (+ open/high/low if present), Direction, ConfirmCount,
    MoneyLine Level (matched case-insensitively on the prefix; suffixes like `.1` ignored). Direction -1 = bull.
    The last row of an export is the live, forming bar; the caller drops it. attrs['path'] names the file read.
    """
    p = Path(os.path.expanduser(str(path_glob)))
    files = glob.glob(str(p if p.is_absolute() else REPO / p))
    if not files:
        raise FileNotFoundError(f"no TradingView export matches {path_glob}")
    f = max(files, key=os.path.getmtime)
    raw = pd.read_csv(f)
    cols = list(raw.columns)
    tcol = _find(cols, "time", exact=True) or _find(cols, "date", exact=True)
    pick = {k: _find(cols, k, exact=True) for k in ("open", "high", "low", "close")}
    pick.update({name: _find(cols, pre) for name, pre in TV_COLUMNS.items()})
    missing = [k for k in ("close", *TV_COLUMNS) if pick[k] is None] + ([] if tcol else ["time"])
    if missing:
        raise ValueError(f"{Path(f).name}: missing TradingView columns {missing}")
    out = pd.DataFrame({k: pd.to_numeric(raw[c], errors="coerce").to_numpy() for k, c in pick.items() if c is not None},
                       index=_bar_dates(raw[tcol], tz))
    out.index.name = "date"
    out = out[out["close"].notna()].sort_index(kind="stable")
    out = out[~out.index.duplicated(keep="last")]
    out.attrs["path"] = f
    return out


def tv_export_targets(df: pd.DataFrame, mode_name: str) -> pd.DataFrame:
    """Targets from the new indicator's export (read_tv_export frame).

    immediate_green = (D == -1 & cnt == 0) | (D == 1 & cnt >= 1), i.e. on the bull side of the level from the first
    close beyond it. confirm_green = (D == -1). target_frac: immediate / confirm5 / split = 0.5 each; NaN where
    Direction or ConfirmCount is missing. Also: level, pending (= cnt), direction, and confirm_green_early: the
    confirmed state from the close on which ConfirmCount reaches 5 (Direction itself shows the flip one bar later).
    """
    if mode_name not in TV_MODES:
        raise ValueError(f"tv_export supports modes {sorted(TV_MODES)}, not {mode_name!r}")
    d, cnt = df["Direction"], df["ConfirmCount"]
    ok = d.notna() & cnt.notna()
    imm = ok & (((d == -1) & (cnt == 0)) | ((d == 1) & (cnt >= 1)))
    conf = ok & (d == -1)
    early = ok & ((d == -1) != (cnt >= TV_CONFIRM_N))
    wi, wc = TV_MODES[mode_name]
    frac = (wi * imm.astype(float) + wc * conf.astype(float)).where(ok)
    return pd.DataFrame({"immediate_green": imm, "confirm_green": conf, "target_frac": frac,
                         "level": df["MoneyLine Level"], "pending": cnt, "direction": d,
                         "confirm_green_early": early}, index=df.index)
