"""
Same analysis as the crypto run, applied to SPX / NDX / IWM / COIN.

Two things differ from crypto and both matter:

1. Costs are far lower. Liquid ETF execution is ~1bp commission-equivalent
   plus ~2bp spread, not the 10bp+5bp used for crypto.

2. These are PRICE series with no dividends. Buy & hold would collect the
   dividend stream in full; the signal only collects it while exposed
   (~50-60% of the time). Ignoring dividends therefore penalises buy & hold
   more than the signal. Being flat would also earn cash interest, which cuts
   the other way. Both are estimated in the `adjusted` view.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DIR = Path(__file__).resolve().parent.parent / "data" / "tv_stocks"
TICKERS = ["SPX", "NDX", "IWM", "COIN"]

FEE, SLIP = 0.0001, 0.0002          # 1bp + 2bp — liquid ETF execution

# Rough long-run annual yields used only for the sensitivity view.
DIV_YIELD = {"SPX": 0.020, "NDX": 0.008, "IWM": 0.013, "COIN": 0.0}
CASH_YIELD = {"SPX": 0.040, "NDX": 0.030, "IWM": 0.020, "COIN": 0.020}


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
    }, index=df.index)
    first = int(np.argmax((up.notna() | dn.notna()).to_numpy()))
    return out.iloc[first:]


def flips_up(green):
    g = np.asarray(green, dtype=bool)
    o = np.zeros(len(g), dtype=bool)
    o[1:] = g[1:] & ~g[:-1]
    return o


def stats(eq, pnls, exposure, index, ppy):
    p = pd.Series(pnls, dtype=float)
    wins, loss = p[p > 0], p[p <= 0]
    r = eq.pct_change().dropna()
    yrs = (index[-1] - index[0]).days / 365.25
    return {
        "return_pct": (eq.iloc[-1] - 1) * 100,
        "cagr_pct": (eq.iloc[-1] ** (1 / yrs) - 1) * 100 if yrs > 0 and eq.iloc[-1] > 0 else np.nan,
        "max_dd_pct": ((eq / eq.cummax()) - 1).min() * 100,
        "sharpe": r.mean() / r.std() * np.sqrt(ppy) if r.std() > 0 else 0.0,
        "trades": len(p),
        "win_rate": len(wins) / len(p) * 100 if len(p) else np.nan,
        "profit_factor": wins.sum() / abs(loss.sum()) if len(loss) and loss.sum() else np.inf,
        "exposure_pct": exposure * 100,
        "years": yrs,
    }


def bt(close, want, ppy, div=0.0, cash=0.0):
    """Long while `want`. div/cash are annual rates accrued per bar."""
    c = close.to_numpy(float)
    w = np.asarray(want, dtype=bool)
    dt = np.diff(close.index.values).astype("timedelta64[D]").astype(float)
    dt = np.concatenate([[0.0], dt]) / 365.25

    eq, sh, entry = 1.0, 0.0, None
    curve, pnls = np.empty(len(c)), []
    for i in range(len(c)):
        if sh > 0.0 and div:                       # dividends while invested
            sh *= (1 + div * dt[i])
        if sh == 0.0 and cash:                     # interest while flat
            eq *= (1 + cash * dt[i])
        if w[i] and sh == 0.0:
            px = c[i] * (1 + SLIP); sh = eq * (1 - FEE) / px; entry = eq; eq = 0.0
        elif not w[i] and sh > 0.0:
            px = c[i] * (1 - SLIP); eq = sh * px * (1 - FEE); sh = 0.0
            pnls.append((eq / entry - 1) * 100)
        curve[i] = eq + sh * c[i]
    return stats(pd.Series(curve, index=close.index), pnls, w.mean(), close.index, ppy)


def bh(close, div=0.0):
    c = close.to_numpy(float)
    dt = np.diff(close.index.values).astype("timedelta64[D]").astype(float)
    dt = np.concatenate([[0.0], dt]) / 365.25
    units = np.cumprod(1 + div * dt) if div else np.ones(len(c))
    eq = pd.Series(c * units / c[0], index=close.index)
    yrs = (close.index[-1] - close.index[0]).days / 365.25
    return {
        "return_pct": (eq.iloc[-1] - 1) * 100,
        "cagr_pct": (eq.iloc[-1] ** (1 / yrs) - 1) * 100,
        "max_dd_pct": ((eq / eq.cummax()) - 1).min() * 100,
        "sharpe": np.nan, "trades": 1, "win_rate": np.nan, "profit_factor": np.nan,
        "exposure_pct": 100.0, "years": yrs,
    }


def weekly_on_daily(sym, idx):
    w = load(sym, "1W")
    return w["green"].shift(1).reindex(idx, method="ffill").fillna(False).astype(bool)


def main():
    rows = []
    for sym in TICKERS:
        for tf, ppy in (("1D", 252), ("1W", 52)):
            d = load(sym, tf)
            rows.append({"tf": tf, "asset": sym, "view": "raw", "strategy": "Buy & Hold", **bh(d.close)})
            rows.append({"tf": tf, "asset": sym, "view": "raw", "strategy": "Signal",
                         **bt(d.close, d.green.to_numpy(bool), ppy)})
            rows.append({"tf": tf, "asset": sym, "view": "raw", "strategy": "Signal (next-bar fill)",
                         **bt(d.close, np.concatenate([[False], d.green.to_numpy(bool)[:-1]]), ppy)})
            # dividends + cash-while-flat
            rows.append({"tf": tf, "asset": sym, "view": "adjusted", "strategy": "Buy & Hold",
                         **bh(d.close, div=DIV_YIELD[sym])})
            rows.append({"tf": tf, "asset": sym, "view": "adjusted", "strategy": "Signal",
                         **bt(d.close, d.green.to_numpy(bool), ppy,
                              div=DIV_YIELD[sym], cash=CASH_YIELD[sym])})

        d = load(sym, "1D")
        wk = weekly_on_daily(sym, d.index).to_numpy(bool)
        g = d.green.to_numpy(bool)
        rows.append({"tf": "1D", "asset": sym, "view": "raw", "strategy": "Daily AND Weekly",
                     **bt(d.close, g & wk, 252)})
        rows.append({"tf": "1D", "asset": sym, "view": "raw", "strategy": "Daily OR Weekly",
                     **bt(d.close, g | wk, 252)})
        rows.append({"tf": "1D", "asset": sym, "view": "raw", "strategy": "Weekly state only",
                     **bt(d.close, wk, 252)})

    res = pd.DataFrame(rows)
    res.to_csv(Path(__file__).resolve().parent / "results_stocks.csv", index=False)

    cols = ["strategy", "return_pct", "cagr_pct", "max_dd_pct", "sharpe",
            "trades", "win_rate", "profit_factor", "exposure_pct"]
    for tf in ("1D", "1W"):
        print(f"\n{'#'*104}\n#  {tf}\n{'#'*104}")
        for sym in TICKERS:
            sub = res[(res.tf == tf) & (res.asset == sym) & (res.view == "raw")]
            if sub.empty:
                continue
            print(f"\n--- {sym} {tf}  ({sub.iloc[0].years:.1f} yrs, price-only) ---")
            print(sub[cols].to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    print(f"\n\n{'#'*104}\n#  DIVIDEND + CASH-YIELD ADJUSTED (estimated rates)\n{'#'*104}")
    adj = res[res.view == "adjusted"]
    for tf in ("1D", "1W"):
        print(f"\n--- {tf} ---")
        sub = adj[adj.tf == tf].pivot_table(index="asset", columns="strategy",
                                            values=["return_pct", "cagr_pct", "max_dd_pct"])
        print(sub.to_string(float_format=lambda x: f"{x:,.1f}"))


if __name__ == "__main__":
    main()
