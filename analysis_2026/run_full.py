"""
Definitive re-run on the REAL indicator state from the full-history
TradingView exports (data/tv_full).

The exports carry only `close`, so fills are at close. Primary convention is
same-bar (24/7 crypto: the bar closes and you can act on it); next-bar is
reported as a sensitivity.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ASSETS = ["BTC", "ETH", "SOL", "BNB", "ZEC"]
DIR = Path(__file__).resolve().parent.parent / "data" / "tv_full"
FEE, SLIP = 0.001, 0.0005


def load(sym, tf):
    df = pd.read_csv(DIR / f"{sym}_{tf}.csv")
    df["date"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("date").sort_index()
    up = pd.to_numeric(df["Up Trend"], errors="coerce")
    dn = pd.to_numeric(df["Down Trend"], errors="coerce")
    out = pd.DataFrame({
        "close": pd.to_numeric(df["close"], errors="coerce"),
        "green": up.notna(),
        "line": up.where(up.notna(), dn),
        "atr": pd.to_numeric(df["ATR"], errors="coerce"),
    }, index=df.index)
    # drop the warmup bars where neither line has printed yet
    first = np.argmax((up.notna() | dn.notna()).to_numpy())
    return out.iloc[first:]


def flips_up(green):
    g = np.asarray(green, dtype=bool)
    o = np.zeros(len(g), dtype=bool)
    o[1:] = g[1:] & ~g[:-1]
    return o


def bt(close, want, ppy):
    """Long while `want`, flat otherwise. Fills at close with fee+slippage."""
    c = close.to_numpy(float)
    w = np.asarray(want, dtype=bool)
    eq, sh, entry = 1.0, 0.0, None
    curve, pnls = np.empty(len(c)), []
    for i in range(len(c)):
        if w[i] and sh == 0.0:
            px = c[i] * (1 + SLIP); sh = eq * (1 - FEE) / px; entry = eq; eq = 0.0
        elif not w[i] and sh > 0.0:
            px = c[i] * (1 - SLIP); eq = sh * px * (1 - FEE); sh = 0.0
            pnls.append((eq / entry - 1) * 100)
        curve[i] = eq + sh * c[i]
    e = pd.Series(curve, index=close.index)
    p = pd.Series(pnls, dtype=float)
    wins, loss = p[p > 0], p[p <= 0]
    r = e.pct_change().dropna()
    yrs = (close.index[-1] - close.index[0]).days / 365.25
    return {
        "return_pct": (e.iloc[-1] - 1) * 100,
        "cagr_pct": (e.iloc[-1] ** (1 / yrs) - 1) * 100 if yrs > 0 and e.iloc[-1] > 0 else np.nan,
        "max_dd_pct": ((e / e.cummax()) - 1).min() * 100,
        "sharpe": r.mean() / r.std() * np.sqrt(ppy) if r.std() > 0 else 0.0,
        "trades": len(p),
        "win_rate": len(wins) / len(p) * 100 if len(p) else np.nan,
        "profit_factor": wins.sum() / abs(loss.sum()) if len(loss) and loss.sum() else np.inf,
        "avg_win": wins.mean() if len(wins) else np.nan,
        "avg_loss": loss.mean() if len(loss) else np.nan,
        "exposure_pct": w.mean() * 100,
    }, e


def bh(close):
    return {
        "return_pct": (close.iloc[-1] / close.iloc[0] - 1) * 100,
        "cagr_pct": ((close.iloc[-1] / close.iloc[0]) ** (365.25 / (close.index[-1] - close.index[0]).days) - 1) * 100,
        "max_dd_pct": ((close / close.cummax()) - 1).min() * 100,
        "sharpe": np.nan, "trades": 1, "win_rate": np.nan, "profit_factor": np.nan,
        "avg_win": np.nan, "avg_loss": np.nan, "exposure_pct": 100.0,
    }


def weekly_on_daily(sym, daily_idx):
    """Weekly green state mapped to daily bars, shifted so no unclosed week leaks."""
    w = load(sym, "1W")
    return w["green"].shift(1).reindex(daily_idx, method="ffill").fillna(False).astype(bool)


def main():
    rows = []
    for sym in ASSETS:
        for tf, ppy in (("1D", 365), ("1W", 52)):
            d = load(sym, tf)
            rows.append({"tf": tf, "asset": sym, "strategy": "Buy & Hold", **bh(d.close)})
            m, _ = bt(d.close, d.green.to_numpy(bool), ppy)
            rows.append({"tf": tf, "asset": sym, "strategy": "Signal", **m})
            m, _ = bt(d.close, np.concatenate([[False], d.green.to_numpy(bool)[:-1]]), ppy)
            rows.append({"tf": tf, "asset": sym, "strategy": "Signal (next-bar fill)", **m})

        # daily signal gated by the weekly state
        d = load(sym, "1D")
        wk = weekly_on_daily(sym, d.index)
        m, _ = bt(d.close, d.green.to_numpy(bool) & wk.to_numpy(bool), 365)
        rows.append({"tf": "1D", "asset": sym, "strategy": "Daily AND Weekly green", **m})
        m, _ = bt(d.close, d.green.to_numpy(bool) | wk.to_numpy(bool), 365)
        rows.append({"tf": "1D", "asset": sym, "strategy": "Daily OR Weekly green", **m})
        # weekly state traded on daily bars (weekly signal, daily execution)
        m, _ = bt(d.close, wk.to_numpy(bool), 365)
        rows.append({"tf": "1D", "asset": sym, "strategy": "Weekly state only", **m})

    res = pd.DataFrame(rows)
    res.to_csv(Path(__file__).resolve().parent / "results_full.csv", index=False)

    cols = ["strategy", "return_pct", "cagr_pct", "max_dd_pct", "sharpe", "trades",
            "win_rate", "profit_factor", "exposure_pct"]
    for tf in ("1D", "1W"):
        print(f"\n{'='*106}\n  {tf}\n{'='*106}")
        for sym in ASSETS:
            sub = res[(res.tf == tf) & (res.asset == sym)]
            yrs = (load(sym, tf).index[-1] - load(sym, tf).index[0]).days / 365.25
            print(f"\n--- {sym} {tf}  ({yrs:.1f} yrs) ---")
            print(sub[cols].to_string(index=False, float_format=lambda x: f"{x:,.1f}"))


if __name__ == "__main__":
    main()
