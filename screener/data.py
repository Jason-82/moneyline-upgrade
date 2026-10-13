"""
Daily OHLC loaders for the stock screener and selection study.

All sources are normalised to a DataFrame indexed by date with columns
open, high, low, close (floats), sorted ascending, one row per trading day.

Price adjustment matters (see HANDOFF.md section 2): the indicator matches
TradingView only on SPLIT-adjusted, NOT dividend-adjusted prices.
  - yfinance:   download(..., auto_adjust=False) -> Open/High/Low/Close are
                split-adjusted; 'Adj Close' (ignored here) carries dividends.
  - Robinhood:  get_equity_historicals with adjustment_type='split' (default).
  - CSV folder: whatever you put there (TradingView candle-mode exports are fine).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

_ALIASES = {
    "open": ("open", "open_price", "o"),
    "high": ("high", "high_price", "h"),
    "low": ("low", "low_price", "l"),
    "close": ("close", "close_price", "c"),
    "date": ("date", "time", "datetime", "timestamp", "begins_at", "price"),
}


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Map common column names to date/open/high/low/close and clean the frame."""
    cols = {c.lower().strip(): c for c in df.columns}
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
        d = out["date"]
        if pd.api.types.is_numeric_dtype(d):
            d = pd.to_datetime(d, unit="s")
        else:
            d = pd.to_datetime(d, utc=True, format="mixed").dt.tz_localize(None)
        frame.index = d.dt.normalize().values
    elif isinstance(df.index, pd.DatetimeIndex):
        frame.index = df.index.normalize()
    else:
        raise ValueError("no date column or DatetimeIndex")
    frame = frame.dropna().sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
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
        except Exception as exc:  # keep going; report bad files
            print(f"skip {f.name}: {exc}")
    return out


def from_robinhood_json(path: str | Path) -> dict[str, pd.DataFrame]:
    """
    Parse a saved get_equity_historicals tool result (raw JSON, unedited).
    Accepts {symbol: [bars]} or {"results"/"historicals": [{symbol, historicals/bars: [...]}]}.
    Field names follow Robinhood's API (begins_at, open_price, ...); verify against a real
    response before relying on it.
    """
    raw = json.loads(Path(path).read_text())
    items = raw.get("results") or raw.get("historicals") or raw.get("data") or raw
    out = {}
    if isinstance(items, dict):
        items = [{"symbol": k, "bars": v} for k, v in items.items()]
    for it in items:
        sym = (it.get("symbol") or "").upper()
        bars = it.get("historicals") or it.get("bars") or []
        if sym and bars:
            df = normalise(pd.DataFrame(bars))
            if "session" in pd.DataFrame(bars).columns:
                pass  # interday bars carry no session split
            out[sym] = df
    return out


def fetch_yfinance(symbols, start="2005-01-01", out_folder: str | Path | None = None):
    """
    Download split-adjusted (not dividend-adjusted) daily OHLC with yfinance.
    Needs network access to Yahoo (blocked in the default Claude cloud sandbox; works
    locally or in an environment whose network policy allows it).
    """
    import yfinance as yf  # pip install yfinance

    out = {}
    for i in range(0, len(symbols), 50):
        chunk = symbols[i:i + 50]
        raw = yf.download(chunk, start=start, auto_adjust=False, actions=False,
                          group_by="ticker", progress=False, threads=True)
        for s in chunk:
            try:
                sub = raw[s] if len(chunk) > 1 else raw
                df = normalise(sub.reset_index().rename(columns={"Date": "date"}))
                if len(df) > 50:
                    out[s] = df
                    if out_folder:
                        Path(out_folder).mkdir(parents=True, exist_ok=True)
                        df.to_csv(Path(out_folder) / f"{s}.csv")
            except Exception as exc:
                print(f"skip {s}: {exc}")
    return out


def sp500_symbols() -> list[str]:
    """Current S&P 500 constituents from github.com/datasets (reachable from the sandbox).
    Current members only: using them for history introduces survivorship bias."""
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    return pd.read_csv(url)["Symbol"].str.replace(".", "-", regex=False).tolist()


if __name__ == "__main__":
    # python -m screener.data --sp500 --out data/universe          (needs Yahoo access)
    # python -m screener.data --symbols NVDA,PLTR,MSTR --out data/universe
    import argparse
    ap = argparse.ArgumentParser(description="Fetch split-adjusted daily OHLC with yfinance")
    ap.add_argument("--sp500", action="store_true", help="current S&P 500 members (survivorship-biased)")
    ap.add_argument("--symbols", help="comma-separated tickers")
    ap.add_argument("--start", default="2005-01-01")
    ap.add_argument("--out", default="data/universe")
    a = ap.parse_args()
    syms = sp500_symbols() if a.sp500 else []
    if a.symbols:
        syms += [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    got = fetch_yfinance(sorted(set(syms)), start=a.start, out_folder=a.out)
    print(f"saved {len(got)} of {len(set(syms))} symbols to {a.out}")
