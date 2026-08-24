"""
Backtest the ACTUAL indicator state from the TradingView exports, and compare
it head-to-head against the two models this repo has been using (Moneyline
HMA/EMA crossover, and close>kijun) computed on the same bars over the same
window.

Only `close` is available in the exports, so fills are at close. Two fill
conventions are reported:
  same : act on the bar that prints the flip (24/7 crypto - the weekly bar
         closes Sunday 00:00 UTC and you can trade it immediately)
  next : act on the following bar's close (fully conservative)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analysis_2026.tv import ASSETS, load_tv, flips  # noqa: E402
from indicators import compute_moneyline, compute_donchian  # noqa: E402

FEE = 0.001      # 0.1% per side
SLIP = 0.0005    # 5 bps


def synth_ohlc(close: pd.Series) -> pd.DataFrame:
    o = close.shift(1).fillna(close)
    return pd.DataFrame({
        "open": o, "close": close,
        "high": pd.concat([o, close], axis=1).max(axis=1),
        "low": pd.concat([o, close], axis=1).min(axis=1),
    })


def bt_state(close: pd.Series, green: pd.Series, fill: str = "same", ppy: int = 52):
    """Long while green, flat while red. Returns metrics + equity curve."""
    c = close.to_numpy(float)
    g = green.to_numpy(bool)
    n = len(c)

    # desired position per bar, with the chosen execution lag
    want = g.copy()
    if fill == "next":
        want = np.concatenate([[False], g[:-1]])

    equity = 1.0
    shares = 0.0
    curve = np.empty(n)
    pnls, entry_eq = [], None

    for i in range(n):
        if want[i] and shares == 0.0:                      # enter
            px = c[i] * (1 + SLIP)
            shares = equity * (1 - FEE) / px
            entry_eq = equity
            equity = 0.0
        elif not want[i] and shares > 0.0:                 # exit
            px = c[i] * (1 - SLIP)
            equity = shares * px * (1 - FEE)
            shares = 0.0
            pnls.append((equity / entry_eq - 1) * 100)
        curve[i] = equity + shares * c[i]

    eq = pd.Series(curve, index=close.index)
    pnls = pd.Series(pnls, dtype=float)
    wins, losses = pnls[pnls > 0], pnls[pnls <= 0]
    rets = eq.pct_change().dropna()
    yrs = (close.index[-1] - close.index[0]).days / 365.25

    return {
        "return_pct": (eq.iloc[-1] - 1) * 100,
        "cagr_pct": (eq.iloc[-1] ** (1 / yrs) - 1) * 100 if yrs > 0 else np.nan,
        "max_dd_pct": ((eq / eq.cummax()) - 1).min() * 100,
        "sharpe": rets.mean() / rets.std() * np.sqrt(ppy) if rets.std() > 0 else 0.0,
        "trades": len(pnls),
        "win_rate": len(wins) / len(pnls) * 100 if len(pnls) else np.nan,
        "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() else np.inf,
        "exposure_pct": want.mean() * 100,
    }, eq


def model_states(close: pd.Series):
    """The two models this repo has used, on the same bars."""
    ohlc = synth_ohlc(close)
    ml = compute_moneyline(ohlc, conv_period=9, base_period=26,
                           fast_hma_period=5, slow_ema_period=13, exit_percent=2.0)
    # Moneyline as a persistent state: long from long_cross until exit_cross
    state = np.zeros(len(close), dtype=bool)
    on = False
    lc = ml["long_cross"].to_numpy(bool)
    xc = ml["exit_cross"].to_numpy(bool)
    for i in range(len(close)):
        if not on and lc[i]:
            on = True
        elif on and xc[i]:
            on = False
        state[i] = on
    return {
        "Moneyline cross": pd.Series(state, index=close.index),
        "close > kijun": ml["close"] > ml["kijun"],
        "trend_green (fast>slow)": ml["trend_green"].fillna(False),
    }


def main():
    all_rows, agree_rows = [], []

    for tf, ppy in (("1W", 52), ("1D", 365)):
        for s in ASSETS:
            d = load_tv(s, tf).dropna(subset=["stop_line"])
            close, green = d["close"], d["green"]

            bh = (close.iloc[-1] / close.iloc[0] - 1) * 100
            bh_dd = ((close / close.cummax()) - 1).min() * 100
            all_rows.append({"tf": tf, "asset": s, "strategy": "Buy & Hold",
                             "return_pct": bh, "max_dd_pct": bh_dd, "trades": 1,
                             "exposure_pct": 100.0, "sharpe": np.nan,
                             "win_rate": np.nan, "profit_factor": np.nan,
                             "cagr_pct": np.nan})

            for fill in ("same", "next"):
                m, _ = bt_state(close, green, fill=fill, ppy=ppy)
                all_rows.append({"tf": tf, "asset": s,
                                 "strategy": f"TV indicator ({fill}-bar fill)", **m})

            for name, st in model_states(close).items():
                m, _ = bt_state(close, st, fill="same", ppy=ppy)
                all_rows.append({"tf": tf, "asset": s, "strategy": name, **m})
                agree_rows.append({"tf": tf, "asset": s, "model": name,
                                   "agree_pct": (st.to_numpy(bool) == green.to_numpy(bool)).mean() * 100})

    res = pd.DataFrame(all_rows)
    agree = pd.DataFrame(agree_rows)
    out = Path(__file__).resolve().parent
    res.to_csv(out / "results_tv.csv", index=False)
    agree.to_csv(out / "agreement_tv.csv", index=False)

    cols = ["strategy", "return_pct", "cagr_pct", "max_dd_pct", "sharpe",
            "trades", "win_rate", "profit_factor", "exposure_pct"]
    for tf in ("1W", "1D"):
        print(f"\n{'='*104}\n  {tf} — actual TradingView signal vs the models this repo used\n{'='*104}")
        for s in ASSETS:
            sub = res[(res.tf == tf) & (res.asset == s)]
            print(f"\n--- {s} {tf} ---")
            print(sub[cols].to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    print(f"\n\n{'='*104}\n  How often does each model's state MATCH the real indicator?\n{'='*104}")
    piv = agree.pivot_table(index=["tf", "asset"], columns="model", values="agree_pct")
    print(piv.to_string(float_format=lambda x: f"{x:,.1f}"))


if __name__ == "__main__":
    main()
