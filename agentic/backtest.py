"""Tranche modes vs buy & hold on any OHLC history, with fractional weights (SPEC section 3)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from agentic.indicator import TV_MODES, read_tv_export, tranche_targets, tv_export_targets
from analysis_2026.flip_delay import load_crypto_daily, load_etf, stats as _stats
from screener.strictness import TBILL

REPO = Path(__file__).resolve().parent.parent
WARMUP = 120
COLUMNS = ["CAGR_%", "CAGR_tax_%", "Sharpe", "maxDD_%", "trades_per_yr", "exposure_%", "years"]
BH = "BUY & HOLD"


def _cash_returns(idx: pd.DatetimeIndex, cash_rate_annual=None) -> np.ndarray:
    days = np.r_[1, np.diff(idx.values).astype("timedelta64[D]").astype(int)]
    if cash_rate_annual is None:
        return np.array([(1 + TBILL.get(d.year, 2.0) / 100 / 365) ** k - 1 for d, k in zip(idx, days)])
    return (1 + float(cash_rate_annual) / 365) ** days - 1.0


def _weights(w, index: pd.DatetimeIndex) -> np.ndarray:
    if isinstance(w, pd.Series):
        w = w.reindex(index)
    w = np.nan_to_num(np.asarray(w, dtype=float), nan=0.0)
    if len(w) != len(index):
        raise ValueError(f"weights have {len(w)} rows, prices {len(index)}")
    if (w < -1e-12).any() or (w > 1 + 1e-12).any():
        raise ValueError("weights must lie in [0, 1]")
    return np.clip(w, 0.0, 1.0)


def _ohlc_names(df, names):
    low = {str(c).lower(): c for c in df.columns}
    return [low[n] for n in names]


def _path(df, w, cost, cash_rate_annual=None):
    o, c = (df[k].to_numpy(float) for k in _ohlc_names(df, ("open", "close")))
    tb = _cash_returns(df.index, cash_rate_annual)
    held = np.r_[0.0, _weights(w, df.index)[:-1]]
    prev = np.r_[0.0, held[:-1]]
    cp = np.r_[np.nan, c[:-1]]
    with np.errstate(invalid="ignore", divide="ignore"):
        same = prev * (c / cp - 1) + (1 - prev) * tb
        chg = ((prev * (o / cp) + (1 - prev)) * (1 - cost * np.abs(held - prev))
               * (held * (c / o) + (1 - held) * (1 + tb)) - 1)
    changed = held != prev
    r = np.where(changed, chg, same)
    r[0] = 0.0
    return pd.Series(r, index=df.index), changed, held


def weights_returns(df: pd.DataFrame, w, cost: float, cash_rate_annual: float | None = None) -> tuple[pd.Series, int]:
    """Daily returns of holding weight w[t] (decided at close t) from the next open, the rest in cash.

    On a change day the old weight earns prior close -> open, `cost x |dw|` is paid at the open, then the new weight
    earns open -> close and the cash share earns the day's interest. Cash earns T-bills by year (screener.strictness
    TBILL, calendar-day compounding) or `cash_rate_annual` (a fraction, e.g. 0.04; 0 for none). Equals
    flip_delay.strat_returns for 0/1 weights. Returns (returns, number of weight changes).
    """
    r, changed, _ = _path(df, w, cost, cash_rate_annual)
    return r, int(changed.sum())


def _tax_yearly(r: pd.Series, rate: float) -> float:
    """Final wealth after taxing each calendar year's growth, losses carried forward (as flip_delay.stats)."""
    v, carry = 1.0, 0.0
    for _, x in r.groupby(r.index.year):
        g = v * ((1 + x).prod() - 1)
        net = g + carry
        tax = rate * net if net > 0 else 0.0
        carry = 0.0 if net > 0 else net
        v += g - tax
    return v


def _cagr(v: float, yrs: float) -> float:
    return (v ** (1 / yrs) - 1) * 100 if v > 0 else -100.0


def _row(r: pd.Series, ppy: int, after_tax: float, changes: int, exposure: float) -> dict:
    s, yrs = _stats(r, ppy), len(r) / ppy
    return {"CAGR_%": s.get("CAGR_%", np.nan), "CAGR_tax_%": _cagr(after_tax, yrs) if s else np.nan,
            "Sharpe": s.get("Sharpe", np.nan), "maxDD_%": s.get("maxDD_%", np.nan),
            "trades_per_yr": changes / yrs if yrs else np.nan, "exposure_%": exposure, "years": yrs}


def _compare(px: pd.DataFrame, weights: dict, cost, ppy, start, st_rate, lt_rate, cash_rate_annual=None):
    if len(px) <= WARMUP:
        raise ValueError(f"need more than {WARMUP} bars, got {len(px)}")
    first = px.index[WARMUP]
    win = px.index >= (max(pd.Timestamp(start), first) if start is not None else first)
    if not win.any():
        raise ValueError(f"no bars on or after start {start}")
    rows = {}
    for name, w in weights.items():
        r, changed, held = _path(px, w, cost, cash_rate_annual)
        rw = r[win]
        rows[name] = _row(rw, ppy, _tax_yearly(rw, st_rate), int(changed[win].sum()), float(held[win].mean() * 100))
    c = px[_ohlc_names(px, ("close",))[0]]
    bh = c.pct_change().fillna(0.0)[win]
    end = float((1 + bh).prod())
    rows[BH] = _row(bh, ppy, 1 + (end - 1) * (1 - lt_rate) if end > 1 else end, 0, 100.0)
    out = pd.DataFrame.from_dict(rows, orient="index")[COLUMNS]
    out.index.name = "mode"
    out.attrs.update(start=px.index[win][0], end=px.index[win][-1], cost=cost)
    return out


def compare_modes(df: pd.DataFrame, cfg_modes: dict, cost: float, ppy: int, start=None, st_rate: float = 0.35,
                  lt_rate: float = 0.20) -> pd.DataFrame:
    """One row per mode ({name: tranches}, e.g. cfg['modes']) plus BUY & HOLD, on the computed MoneyLine.

    Columns: CAGR_%, CAGR_tax_% (strategies: st_rate on each year's growth with loss carry; B&H: lt_rate once at the
    end), Sharpe, maxDD_%, trades_per_yr (weight changes, i.e. orders, per year), exposure_% (mean weight held),
    years. The first 120 bars are warm-up and excluded; `start` can only move the window later.
    """
    weights = {name: tranche_targets(df, tr)["target_frac"] for name, tr in cfg_modes.items()
               if not str(name).startswith("_")}
    return _compare(df, weights, cost, ppy, start, st_rate, lt_rate)


def tv_target_frac(tv: pd.DataFrame, mode: str, tv_confirm: str = "count") -> pd.Series:
    """target_frac of a tv_export mode as signals.py trades it: the 5-close tranche reads ConfirmCount reaching 5
    ('count') or Direction (= -1, 'direction', one bar later)."""
    t = tv_export_targets(tv, mode)
    wi, wc = TV_MODES[mode]
    conf = t["confirm_green_early"] if tv_confirm == "count" else t["confirm_green"]
    ok = t["direction"].notna() & t["pending"].notna()
    return (wi * t["immediate_green"].astype(float) + wc * conf.astype(float)).where(ok)


def compare_tv_modes(tv: pd.DataFrame, cost: float, ppy: int, modes=("immediate", "split", "confirm5"), start=None,
                     st_rate: float = 0.35, lt_rate: float = 0.20, tv_confirm: str = "count") -> pd.DataFrame:
    """compare_modes for a read_tv_export frame (the new indicator's own states), with the asset's tv_confirm.

    Exports are usually close-only: without an open column, a change fills at the close of the bar after the signal.
    Bars with no Direction/ConfirmCount count as out of the market.
    """
    if tv_confirm not in ("count", "direction"):
        raise ValueError(f"tv_confirm must be 'count' or 'direction', not {tv_confirm!r}")
    px = pd.DataFrame({"open": tv["open"] if "open" in tv else tv["close"], "close": tv["close"]}, index=tv.index)
    weights = {m: tv_target_frac(tv, m, tv_confirm).fillna(0.0) for m in modes}
    out = _compare(px, weights, cost, ppy, start, st_rate, lt_rate)
    out.attrs["tv_confirm"] = tv_confirm
    return out


def _base_symbol(sym: str) -> str:
    s = sym.upper().split("-")[0].split("/")[0]
    for q in ("USDT", "USDC", "USD"):
        if s.endswith(q) and len(s) > len(q):
            return s[: -len(q)]
    return s


def load_history(asset: dict, cfg: dict, csv: str | Path | None = None, now_utc: datetime | None = None,
                 inbox_dir: str | Path | None = None) -> pd.DataFrame:
    """OHLC history for `backtest`: a local CSV, else repo data, else the asset's live feed (agentic.data).

    Repo data: flip_delay.load_crypto_daily for crypto signals, flip_delay.load_etf for data/etf symbols (the 13 ETFs
    and the others stored there), data/universe_pit_all/<SYM>.csv for other stocks. These folders are gitignored
    downloads: on a fresh clone pass `csv`. A tv_export asset returns its export frame (use compare_tv_modes). A
    fallback to the live feed sets attrs['note'] (Coinbase gives about 2 years). Raises FileNotFoundError with a
    one-line reason when nothing is available.
    """
    from screener.data import from_csv_folder, normalise
    if csv:
        return normalise(pd.read_csv(csv))
    sig = asset["signal"]
    if sig.get("source") == "tv_export":
        return read_tv_export(sig["path"])
    sym = str(sig.get("symbol") or "").upper()
    if asset["class"] == "crypto":
        try:
            return load_crypto_daily(_base_symbol(sym))
        except (FileNotFoundError, KeyError):
            pass
    elif sym:
        etf = REPO / "data" / "etf"
        if (etf / f"{sym}.csv").exists() or (etf / f"O_{sym}.csv").exists():
            return load_etf(sym)
        got = from_csv_folder(REPO / "data" / "universe_pit_all", symbols={sym})
        if sym in got:
            return got[sym]
    from agentic import data as feeds
    from agentic.config import paths
    feed = sig.get("feed")
    hint = f"no local history for {sym or asset['name']} (data/ downloads are not in the public repo): pass --csv FILE"
    try:
        df = feeds.get_bars(asset, cfg, now_utc or datetime.now(timezone.utc), inbox_dir or paths()["inbox"])
    except (getattr(feeds, "DataError", ValueError), OSError) as exc:
        raise FileNotFoundError(f"{hint} (live {feed} feed: {exc})") from exc
    if isinstance(df, pd.DataFrame) and len(df):
        df.attrs["note"] = (f"no local history for {sym or asset['name']}: using the live {feed} feed, {len(df)} bars "
                            f"({df.index[0].date()} to {df.index[-1].date()}); results cover only that window")
    return df
