"""
Daily OHLC loaders for the stock screener and selection study.

All sources are normalised to a DataFrame indexed by date with columns
open, high, low, close (floats), sorted ascending, one row per trading day.

Price adjustment matters (see HANDOFF.md section 2): the indicator matches
TradingView only on SPLIT-adjusted, NOT dividend-adjusted prices.
  - yfinance:   download(..., auto_adjust=False) -> Open/High/Low/Close are
                split-adjusted; 'Adj Close' (ignored here) carries dividends.
  - Robinhood:  get_equity_historicals with interval='day', adjustment_type='split'.
  - CSV folder: whatever you put there (TradingView candle-mode exports are fine).

Only CLOSED sessions belong in a scan: a bar that is still forming can show a flip that
is gone by the close. fetch_yfinance and from_robinhood_json drop it.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.calendar import last_completed_session

_NY = "America/New_York"

_ALIASES = {
    "open": ("open", "open_price", "o"),
    "high": ("high", "high_price", "h"),
    "low": ("low", "low_price", "l"),
    "close": ("close", "close_price", "c"),
    "date": ("date", "time", "datetime", "timestamp", "begins_at", "price"),
    "volume": ("volume", "v"),
    "dividends": ("dividends", "dividend", "cash_dividend", "cash_per_share"),
    "stock_splits": ("stock_splits", "stock splits", "split_ratio"),
}


def last_closed_session(now=None) -> pd.Timestamp:
    """Latest actual NYSE session closed plus the 20-minute settlement buffer."""
    return last_completed_session(now=now, settlement_minutes=20)


def drop_unclosed(df: pd.DataFrame, asof=None) -> pd.DataFrame:
    asof = last_closed_session() if asof is None else pd.Timestamp(asof)
    if asof.tzinfo is not None:
        asof = asof.tz_convert(_NY).tz_localize(None)
    return df[df.index <= asof.normalize()].copy()


def _parse_dates(d: pd.Series) -> pd.DatetimeIndex:
    if pd.api.types.is_numeric_dtype(d):
        v = pd.to_numeric(d)
        if v.between(19000101, 21001231).all():
            return pd.to_datetime(v.astype("int64").astype(str), format="%Y%m%d")
        return pd.to_datetime(v, unit="ms" if v.max() > 1e11 else "s")
    parsed = pd.to_datetime(d, format="mixed", errors="coerce")
    if isinstance(parsed.dtype, pd.DatetimeTZDtype):
        return parsed.dt.tz_localize(None)        # keep the local calendar date as written
    if parsed.dtype == object:                    # mixed offsets
        return pd.to_datetime(d, utc=True, format="mixed").dt.tz_localize(None)
    return parsed


def valid_ohlc_mask(df: pd.DataFrame, float32_ulps: int = 0) -> pd.Series:
    """Valid prices and candle ordering, with optional declared float32 precision.

    A maximum of two source float32 ULPs accommodates binary rounding in diagnostic
    data only. Actual OHLC values are never clipped, rounded, replaced or repaired.
    Decimal broker and licensed data callers use the default exact range check.
    """
    if isinstance(float32_ulps, bool) or not isinstance(float32_ulps, (int, np.integer)) or not 0 <= float32_ulps <= 2:
        raise ValueError("float32_ulps must be an integer from 0 through 2")
    values = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    finite_positive = np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)
    tolerance = np.zeros(len(df), dtype=float)
    if float32_ulps:
        # Invalid infinities must not acquire an infinite tolerance through a cast.
        magnitude = np.max(np.abs(np.where(np.isfinite(values), values, 0)), axis=1)
        with np.errstate(over="ignore", invalid="ignore"):
            source_scale = magnitude.astype(np.float32)
            tolerance = float32_ulps * np.spacing(source_scale).astype(float)
        finite_positive &= np.isfinite(tolerance)
    valid = (finite_positive & (values[:, 1] + tolerance >= values.max(axis=1))
             & (values[:, 2] - tolerance <= values.min(axis=1)))
    return pd.Series(valid, index=df.index)


def normalise(df: pd.DataFrame, *, float32_ulps: int = 0) -> pd.DataFrame:
    """Map common column names to open/high/low/close + date and clean the frame."""
    if isinstance(df.columns, pd.MultiIndex):
        raise ValueError("MultiIndex columns (raw yfinance download?) - select one ticker first")
    cols = {str(c).lower().strip(): c for c in df.columns}
    out = {}
    for key, names in _ALIASES.items():
        for n in names:
            if n in cols:
                out[key] = df[cols[n]]
                break
    missing = [k for k in ("open", "high", "low", "close") if k not in out]
    if missing:
        raise ValueError(f"missing OHLC columns: {missing}")
    frame = pd.DataFrame({k: pd.to_numeric(v, errors="coerce") for k, v in out.items() if k != "date"})
    if "date" in out:
        frame.index = pd.DatetimeIndex(_parse_dates(out["date"])).normalize()
    elif isinstance(df.index, pd.DatetimeIndex):
        idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
        frame.index = idx.normalize()
    else:
        raise ValueError("no date column or DatetimeIndex")
    if frame.index.hasnans:
        raise ValueError("invalid or missing bar date")
    values = frame[["open", "high", "low", "close"]]
    if not np.isfinite(values.to_numpy()).all() or (values <= 0).any().any():
        raise ValueError("OHLC must be finite and strictly positive")
    if not valid_ohlc_mask(frame, float32_ulps=float32_ulps).all():
        raise ValueError("invalid OHLC ordering: low <= open,close <= high required")
    for field in ("volume", "dividends", "stock_splits"):
        if field in frame and (not np.isfinite(frame[field].to_numpy()).all() or (frame[field] < 0).any()):
            raise ValueError(f"{field} must be finite and nonnegative when supplied")
    frame = frame.sort_index(kind="stable")
    if frame.index.has_duplicates:
        for date, group in frame[frame.index.duplicated(keep=False)].groupby(level=0):
            if not group.eq(group.iloc[0]).all().all():
                raise ValueError(f"conflicting duplicate bars on {date.date()}")
        frame = frame[~frame.index.duplicated(keep="last")]
    frame.index.name = "date"
    frame.attrs.update(df.attrs)
    return frame


def from_csv_folder(folder: str | Path, symbols=None, *, drop_open_session=True,
                    asof=None, strict=False) -> dict[str, pd.DataFrame]:
    """One CSV per symbol. Live scans reject forming bars through the same cutoff as API data.

    Historical callers must explicitly use drop_open_session=False. Strict ingestion
    raises on any malformed file instead of silently producing a partial universe.
    """
    out = {}
    cutoff = last_closed_session() if drop_open_session and asof is None else asof
    for f in sorted(Path(folder).glob("*.csv")):
        sym = f.stem.upper()
        if symbols and sym not in symbols:
            continue
        try:
            df = normalise(pd.read_csv(f, float_precision="round_trip"))
            out[sym] = drop_unclosed(df, cutoff) if drop_open_session else df
        except Exception as exc:
            if strict:
                raise ValueError(f"invalid {f.name}: {exc}") from exc
            print(f"skip {f.name}: {exc}")
    return out


def from_robinhood_json(path: str | Path, drop_open_session: bool = True, *,
                        asof=None, require_complete=False) -> dict[str, pd.DataFrame]:
    """
    Parse a saved get_equity_historicals tool result (raw JSON, unedited). Accepts the
    documented {"data": {"results": [{symbol, interval, bars: [{begins_at, open_price,
    high_price, low_price, close_price, volume, session, interpolated}]}]}} shape, the MCP
    {"content": [{"type": "text", "text": ...}]} wrapper, a single-symbol object, a list,
    or {symbol: [bars]}. Field names come from a third-party schema capture - check against
    a real response. Request interval='day' explicitly: without it the server picks an
    interval targeting ~2,500 bars, which is intraday for short ranges.
    """
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, dict) and raw.get("isError"):
        raise ValueError(f"broker tool returned an error in {path}")
    if isinstance(raw, dict) and isinstance(raw.get("structuredContent"), (dict, list)):
        raw = raw["structuredContent"]
    if isinstance(raw, dict) and isinstance(raw.get("content"), list):
        texts = [c.get("text", "") for c in raw["content"] if isinstance(c, dict) and c.get("type") == "text"]
        if texts:
            raw = json.loads("".join(texts))
    if isinstance(raw, dict) and isinstance(raw.get("data"), (dict, list)):
        raw = raw["data"]
    if isinstance(raw, dict) and raw.get("not_found"):
        if require_complete:
            raise ValueError(f"incomplete response: not_found={raw['not_found']}")
        print(f"not found: {', '.join(map(str, raw['not_found']))}")
    if isinstance(raw, dict) and raw.get("symbol") and isinstance(raw.get("historicals") or raw.get("bars"), list):
        items = [raw]
    elif isinstance(raw, dict):
        items = raw.get("results") or raw.get("historicals") or raw
    else:
        items = raw
    if isinstance(items, dict):
        items = [{"symbol": k, "bars": v} for k, v in items.items() if isinstance(v, list)]
    if not isinstance(items, list):
        raise ValueError(f"unrecognised JSON shape in {path}")
    if items and all(isinstance(it, dict) and "begins_at" in it for it in items):   # flat bars
        grouped: dict[str, list] = {}
        for b in items:
            grouped.setdefault(str(b.get("symbol", "")).upper(), []).append(b)
        items = [{"symbol": k, "bars": v} for k, v in grouped.items()]
    asof = (last_closed_session() if asof is None else pd.Timestamp(asof)) if drop_open_session else None
    out = {}
    for it in items:
        sym = str(it.get("symbol") or "").upper()
        bars = it.get("historicals") or it.get("bars") or []
        interval = str(it.get("interval", "day")).lower()
        if interval not in ("day", "1d", "daily"):
            raise ValueError(f"{sym}: interval '{interval}' is not daily - request interval='day'")
        if str(it.get("bounds", "regular")).lower() not in ("regular", "reg"):
            raise ValueError(f"{sym}: regular-session daily bars required")
        adjustment = it.get("adjustment_type") or it.get("adjustment")
        if adjustment is not None and str(adjustment).lower() not in ("split", "split_only", "split_adjusted"):
            raise ValueError(f"{sym}: indicator requires split-only prices, got {adjustment}")
        if not sym or not bars:
            raise ValueError("response contains an empty symbol or no bars")
        b = pd.DataFrame(bars)
        if "interpolated" in b.columns:
            interpolated = b["interpolated"].map(lambda x: str(x).lower() in ("true", "1"))
            if require_complete and interpolated.any():
                raise ValueError(f"{sym}: interpolated bars prevent a complete merge")
            b = b[~interpolated]
        df = normalise(b)
        if sym in out:
            raise ValueError(f"duplicate response symbol: {sym}")
        out[sym] = df[df.index <= asof] if asof is not None else df
    if not out:
        raise ValueError(f"no daily bars parsed from {path}")
    return out


def fetch_yfinance(symbols, start="1993-01-01", out_folder: str | Path | None = None, include_today=False):
    """
    Download split-adjusted (not dividend-adjusted) daily OHLC with yfinance. Needs network
    access to Yahoo (blocked in the default Claude cloud sandbox; works locally or in an
    environment whose network policy allows it). Yahoo has no delisted tickers, so
    histories built this way are survivorship-biased. A still-forming bar is dropped unless
    include_today=True.
    """
    import yfinance as yf  # pip install yfinance

    asof = None if include_today else last_closed_session()
    out = {}
    for i in range(0, len(symbols), 50):
        chunk = symbols[i:i + 50]
        raw = yf.download(chunk, start=start, auto_adjust=False, actions=True,
                          group_by="ticker", progress=False, threads=True)
        for s in chunk:
            try:
                sub = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
                sub = sub.dropna(subset=["Open", "High", "Low", "Close"], how="all")
                df = normalise(sub.reset_index().rename(columns={"Date": "date"}))
                if asof is not None:
                    df = df[df.index <= asof]
                if len(df) > 50:
                    out[s] = df
                    if out_folder:
                        Path(out_folder).mkdir(parents=True, exist_ok=True)
                        df.to_csv(Path(out_folder) / f"{s}.csv")
                else:
                    print(f"skip {s}: only {len(df)} rows")
            except Exception as exc:
                print(f"skip {s}: {exc}")
    return out


def sp500_symbols() -> list[str]:
    """Current S&P 500 constituents from github.com/datasets (reachable from the sandbox).
    Current members only: using them for history introduces survivorship bias."""
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    return pd.read_csv(url)["Symbol"].str.replace(".", "-", regex=False).tolist()


def from_qlib(root: str | Path, symbols=None, out_folder: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """
    Read Microsoft qlib's US daily dataset (qlib_data_us_1d, a GitHub release download).
    Layout: calendars/day.txt plus features/<symbol>/<field>.day.bin, each a little-endian
    float32 array whose first value is the start index into the calendar.

    The prices are split- AND dividend-adjusted (total return) and rescaled. They
    cannot validate this split-only indicator: historical adjustment can change flips.
    Returned frames are explicitly marked legacy/incomplete and deployment-blocked.
    Coverage stops at the dataset's last update. Names delisted before its first
    collection (~2020) are absent, so it is survivorship-biased like Yahoo.
    """
    root = Path(root)
    cal = pd.DatetimeIndex(pd.to_datetime((root / "calendars" / "day.txt").read_text().split()))
    want = None if symbols is None else {s.lower().replace(".", "-") for s in symbols}
    out = {}
    for d in sorted((root / "features").iterdir()):
        if want is not None and d.name not in want:
            continue
        cols = {}
        for f in ("open", "high", "low", "close"):
            p = d / f"{f}.day.bin"
            if not p.exists():
                break
            a = np.fromfile(p, dtype="<f4")
            if len(a) < 2:
                break
            s = int(a[0]); v = a[1:][:max(0, len(cal) - s)]
            cols[f] = pd.Series(v.astype(float), index=cal[s:s + len(v)])
        if len(cols) < 4:
            continue
        df = pd.DataFrame(cols).dropna()
        df = df[(df > 0).all(axis=1)]
        if len(df) < 50:
            continue
        sym = d.name.upper().replace("-", ".")
        df.index.name = "date"
        df.attrs.update({"price_basis": "total_return", "mode": "legacy_qlib",
                         "validated": False, "deployment_blocked": True,
                         "dividends_complete": False, "terminal_complete": False,
                         "point_in_time_ids": False, "universe_complete": False})
        out[sym] = df
        if out_folder:
            Path(out_folder).mkdir(parents=True, exist_ok=True)
            df.to_csv(Path(out_folder) / f"{sym}.csv", float_format="%.6g")
    return out


def from_long_parquet(path: str | Path, symbols=None, out_folder: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """A long table (date, ticker, open, high, low, close, ...) in one parquet file, e.g.
    the daily-updated github.com/q100423gg-coder/us-stock-data release (split-adjusted
    OHLC for ~2,300 US stocks and ETFs, rolling ~2 years). Needs pyarrow."""
    d = pd.read_parquet(path)
    if symbols is not None:
        d = d[d.ticker.isin(set(symbols))]
    out = {}
    for sym, g in d.groupby("ticker"):
        df = normalise(g.drop(columns=["ticker"]))
        sym = str(sym).upper().replace("-", ".")
        out[sym] = df
        if out_folder:
            Path(out_folder).mkdir(parents=True, exist_ok=True)
            df.to_csv(Path(out_folder) / f"{sym}.csv", float_format="%.6g")
    return out


def quality_filter(data: dict[str, pd.DataFrame], max_bad_ohlc=0.01, jump=0.6, max_jumps=3, *, asof=None):
    """Drop series that look broken or spliced from two companies (recycled tickers):
    more than 1% of bars with high/low outside open/close, or more than 3 one-day
    moves above 60%. Single extreme days (AIG 2008, GME 2021) are real and stay."""
    keep, dropped = {}, {}
    for s, full in data.items():
        d = full if asof is None else full.loc[:pd.Timestamp(asof)]
        if d.empty:
            dropped[s] = "no history available as of selection date"
            continue
        lo, hi = d[["open", "close"]].min(axis=1), d[["open", "close"]].max(axis=1)
        bad = ((d.high < hi * 0.999) | (d.low > lo * 1.001)).mean()
        n_jump = int((d.close.pct_change().abs() > jump).sum())
        if bad > max_bad_ohlc or n_jump > max_jumps:
            dropped[s] = f"{bad:.1%} bad bars, {n_jump} jumps"
        else:
            keep[s] = full
    return keep, dropped


def sp500_members(out: str | Path | None = None) -> pd.DataFrame:
    """Point-in-time S&P 500 membership (symbol, start, end; end blank = still a member)
    from github.com/fja05680/sp500, one row per membership spell. Prices for members
    that were later delisted are still missing from Yahoo/Robinhood."""
    url = "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"
    m = pd.read_csv(url).rename(columns={"ticker": "symbol", "start_date": "start", "end_date": "end"})
    m["symbol"] = m.symbol.str.upper().str.replace("-", ".", regex=False)
    if out:
        m.to_csv(out, index=False)
    return m


if __name__ == "__main__":
    # python -m screener.data --sp500 --out data/universe          (needs Yahoo access)
    # python -m screener.data --symbols NVDA,PLTR,MSTR --out data/universe
    import argparse
    ap = argparse.ArgumentParser(description="Fetch split-adjusted daily OHLC with yfinance")
    ap.add_argument("--sp500", action="store_true", help="current S&P 500 members (survivorship-biased)")
    ap.add_argument("--symbols", help="comma-separated tickers")
    ap.add_argument("--start", default="1993-01-01", help="1993 puts 2000-02 and 2008 inside test windows")
    ap.add_argument("--out", default="data/universe")
    a = ap.parse_args()
    syms = sp500_symbols() if a.sp500 else []
    if a.symbols:
        syms += [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    got = fetch_yfinance(sorted(set(syms)), start=a.start, out_folder=a.out)
    print(f"saved {len(got)} of {len(set(syms))} symbols to {a.out}")
