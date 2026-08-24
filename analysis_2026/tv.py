"""
Loader for the TradingView indicator exports.

Column layout: time, close, Up Trend, Down Trend, Macro Score Heatmap,
               Rate Hike, Rate Cut, ATR

'Up Trend' and 'Down Trend' are mutually exclusive - exactly one carries a
value on any given bar. That IS the green/red state, taken straight from the
user's chart, so nothing has to be reverse-engineered to backtest it.
"""

from pathlib import Path

import numpy as np
import pandas as pd

TV_DIR = Path(__file__).resolve().parent.parent / "data" / "tv_export"
ASSETS = ["BTC", "ETH", "SOL", "BNB", "ZEC"]


def load_tv(symbol: str, tf: str) -> pd.DataFrame:
    """Load one export. tf is '1D' or '1W'."""
    df = pd.read_csv(TV_DIR / f"{symbol}_{tf}.csv")
    df["date"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("date").sort_index()

    up = pd.to_numeric(df["Up Trend"], errors="coerce")
    dn = pd.to_numeric(df["Down Trend"], errors="coerce")

    out = pd.DataFrame(index=df.index)
    out["close"] = pd.to_numeric(df["close"], errors="coerce")
    out["up_line"] = up
    out["dn_line"] = dn
    out["atr"] = pd.to_numeric(df["ATR"], errors="coerce")
    out["green"] = up.notna()
    out["stop_line"] = up.where(up.notna(), dn)  # the active trailing line

    # both-populated or both-blank would mean the state is ambiguous
    out.attrs["ambiguous"] = int((up.notna() & dn.notna()).sum() + (up.isna() & dn.isna()).sum())

    for col in ("Macro Score Heatmap", "Rate Hike", "Rate Cut"):
        if col in df.columns:
            out[col.lower().replace(" ", "_")] = pd.to_numeric(df[col], errors="coerce")
    return out


def flips(green: pd.Series) -> pd.Series:
    """+1 where state turns green, -1 where it turns red, 0 otherwise."""
    g = green.to_numpy(dtype=bool)
    out = np.zeros(len(g), dtype=int)
    out[1:] = np.where(g[1:] & ~g[:-1], 1, np.where(~g[1:] & g[:-1], -1, 0))
    return pd.Series(out, index=green.index)
