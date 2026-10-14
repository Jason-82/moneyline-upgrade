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

_NY = "America/New_York"
_CLOSE_ET = pd.Timedelta(hours=16)
_CLOSE_BUFFER = pd.Timedelta(minutes=20)   # closing prints settle a little after 16:00

_ALIASES = {
    "open": ("open", "open_price", "o"),
    "high": ("high", "high_price", "h"),
    "low": ("low", "low_price", "l"),
    "close": ("close", "close_price", "c"),
    "date": ("date", "time", "datetime", "timestamp", "begins_at", "price"),
}


def last_closed_session(now=None) -> pd.Timestamp:
    """Latest calendar date whose regular US session has surely closed (half-days are
    treated as 16:00: a complete bar may be held back a few hours, never a partial one
    let through)."""
    now = pd.Timestamp.now(tz=_NY) if now is None else pd.Timestamp(now)
    now = (now.tz_localize(_NY) if now.tzinfo is None else now).tz_convert(_NY)
    closed = now >= now.normalize() + _CLOSE_ET + _CLOSE_BUFFER
    return now.normalize().tz_localize(None) - pd.Timedelta(days=0 if closed else 1)


def drop_unclosed(df: pd.DataFrame, asof=None) -> pd.DataFrame:
    asof = last_closed_session() if asof is None else pd.Timestamp(asof)
    return df[df.index <= asof]


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


def normalise(df: pd.DataFrame) -> pd.DataFrame:
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
    frame = frame[frame.index.notna()].dropna()
    frame = frame.sort_index(kind="stable")
    frame = frame[~frame.index.duplicated(keep="last")]   # later row in the file wins
    frame.index.name = "date"
    return frame


def from_csv_folder(folder: str | Path, symbols=None) -> dict[str, pd.DataFrame]:
    """One CSV per symbol, file name = symbol (e.g. AAPL.csv)."""
    out = {}
    for f in sorted(Path(folder).glob("*.csv")):
        sym = f.stem.upper()
        if symbols and sym not in symbols:
            continue
        try:
            out[sym] = normalise(pd.read_csv(f))
        except Exception as exc:
            print(f"skip {f.name}: {exc}")
    return out


def from_robinhood_json(path: str | Path, drop_open_session: bool = True) -> dict[str, pd.DataFrame]:
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
    if isinstance(raw, dict) and isinstance(raw.get("content"), list):
        texts = [c.get("text", "") for c in raw["content"] if isinstance(c, dict) and c.get("type") == "text"]
        if texts:
            raw = json.loads("".join(texts))
    if isinstance(raw, dict) and isinstance(raw.get("data"), (dict, list)):
        raw = raw["data"]
    if isinstance(raw, dict) and raw.get("not_found"):
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
    asof = last_closed_session() if drop_open_session else None
    out = {}
    for it in items:
        sym = str(it.get("symbol") or "").upper()
        bars = it.get("historicals") or it.get("bars") or []
        interval = str(it.get("interval", "day")).lower()
        if interval not in ("day", "1d", "daily"):
            print(f"skip {sym}: interval '{interval}' is not daily - request interval='day'")
            continue
        if not sym or not bars:
            continue
        b = pd.DataFrame(bars)
        if "interpolated" in b.columns:
            b = b[~b["interpolated"].fillna(False).astype(bool)]      # gap-fill bars
        df = normalise(b)
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
        raw = yf.download(chunk, start=start, auto_adjust=False, actions=False,
                          group_by="ticker", progress=False, threads=True)
        for s in chunk:
            try:
                sub = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
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

    The prices are split- AND dividend-adjusted (total return) and rescaled. That's fine
    for research: the indicator is scale-free and dividend adjustment moves only a few
    borderline flips. Live scans still need split-only data (see the top of this file).
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


def from_sp500_pit(prices_path: str | Path, members_path: str | Path | None = None,
                   out_folder: str | Path | None = None, max_close_only: float = 1.0):
    """
    github.com/Johnbrick123/sp500-data release: point-in-time S&P 500 members since 1995,
    including ~400 dead or acquired companies (IDs like 'LEHMQ-201203'), plus SPY.

    Sources are mixed. Yahoo rows are split-adjusted; Tiingo, WIKI and CRSP rows are raw.
    adj_close is split+dividend adjusted throughout, so O/H/L/C are scaled by
    adj_close/close for one consistent total-return series (use --prices total).

    CRSP rows are close-only, and that covers many of the big failures (Lehman, WaMu,
    Bear, Countrywide). Their bars are approximated as open = previous close,
    high/low = max/min(open, close), so the indicator runs on close-to-close ranges
    there. Those signals are only an approximation (60-72% agreement with real bars).
    Tickers whose close-only share is above max_close_only are skipped. Returns
    (data, members) and writes CSVs plus members.csv if out_folder is given.
    """
    p = pd.read_parquet(prices_path)
    out = {}
    for sym, g in p.groupby("ticker", sort=True):
        g = g.sort_values("date").drop_duplicates("date", keep="last")
        g = g[(g.close > 0) & g.close.notna()]
        if len(g) < 50:
            continue
        close_only = g.open.isna() | g.high.isna() | g.low.isna()
        if close_only.mean() > max_close_only:
            continue
        scale = (g.adj_close / g.close).where(g.adj_close > 0).ffill().bfill().fillna(1.0)
        c = g.close * scale
        o = (g.open * scale).where(~close_only, c.shift(1)).fillna(c)
        h = (g.high * scale).where(~close_only, np.maximum(o, c))
        lo = (g.low * scale).where(~close_only, np.minimum(o, c))
        df = pd.DataFrame({"open": o.values, "high": h.values, "low": lo.values, "close": c.values},
                          index=pd.DatetimeIndex(g.date.values).normalize())
        df.index.name = "date"
        df = df[(df > 0).all(axis=1)].dropna()
        if len(df) < 50:
            continue
        sym = str(sym).upper()
        out[sym] = df
        if out_folder:
            Path(out_folder).mkdir(parents=True, exist_ok=True)
            df.to_csv(Path(out_folder) / f"{sym}.csv", float_format="%.6g")
    members = None
    if members_path:
        members = pd.read_parquet(members_path).rename(columns={"ticker": "symbol"})
        members["symbol"] = members.symbol.str.upper()
        if out_folder:
            members.to_csv(Path(out_folder) / "members.csv", index=False)
    return out, members


def quality_filter(data: dict[str, pd.DataFrame], max_bad_ohlc=0.01, jump=0.6, max_jumps=3, keep_collapsed=False):
    """Drop series that look broken or spliced from two companies (recycled tickers):
    more than 1% of bars with high/low outside open/close, or more than 3 one-day
    moves above 60%. Single extreme days (AIG 2008) are real and stay.

    keep_collapsed=True keeps a failed company whose only problem is junk prints after
    it collapsed (e.g. SIVB, FRC, SBNY in 2023 trading OTC). Such a series is cut 20 bars
    after its close first falls below 10% of its running peak; the slot is then sold at
    that last price, which is close to the real wipe-out. Dropping these names instead
    flatters the baskets (survivorship)."""
    keep, dropped = {}, {}
    for s, d in data.items():
        lo, hi = d[["open", "close"]].min(axis=1), d[["open", "close"]].max(axis=1)
        badm = (d.high < hi * 0.999) | (d.low > lo * 1.001)
        jumps = d.close.pct_change().abs() > jump
        if badm.mean() <= max_bad_ohlc and int(jumps.sum()) <= max_jumps:
            keep[s] = d
            continue
        if keep_collapsed:
            dead = d.close < 0.1 * d.close.cummax()
            if dead.any():
                cut = int(np.argmax(dead.to_numpy()))
                pre = slice(0, cut + 1)
                if badm.iloc[pre].mean() <= max_bad_ohlc and int(jumps.iloc[pre].sum()) <= max_jumps:
                    keep[s] = d.iloc[:cut + 21]
                    dropped[s] = f"kept, cut at collapse {d.index[cut].date()}"
                    continue
        dropped[s] = f"{badm.mean():.1%} bad bars, {int(jumps.sum())} jumps"
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
