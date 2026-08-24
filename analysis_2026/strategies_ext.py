"""
Extended strategies that need custom position handling:
  - trail + reentry  (trailing stop exit, re-enter while trend still green)
  - scaled entry     (partial size on cross, scale up on contraction+breakout)

Both use next-bar-open fills and the same fee/slippage model as run_backtest.
"""

import numpy as np
import pandas as pd

from .common import COSTS, max_drawdown


FEE = COSTS["fee_percent"] / 100
SLIP = COSTS["slippage_bps"] / 10000


def _summarize(equity_curve, trade_pnls, exposure, df, periods_per_year):
    eq = pd.Series(equity_curve, index=df.index).dropna()
    total_ret = (eq.iloc[-1] / COSTS["initial_capital"] - 1) * 100
    pnls = pd.Series(trade_pnls, dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    rets = eq.pct_change().dropna()
    years = (df.index[-1] - df.index[0]).days / 365.25
    return {
        "return_pct": total_ret,
        "cagr_pct": ((eq.iloc[-1] / COSTS["initial_capital"]) ** (1 / years) - 1) * 100 if years > 0 else 0.0,
        "max_dd_pct": max_drawdown(eq),
        "sharpe": (rets.mean() / rets.std() * np.sqrt(periods_per_year)) if rets.std() > 0 else 0.0,
        "trades": len(pnls),
        "win_rate": len(wins) / len(pnls) * 100 if len(pnls) else 0.0,
        "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else float("inf"),
        "avg_win": wins.mean() if len(wins) else 0.0,
        "avg_loss": losses.mean() if len(losses) else 0.0,
        "chop_pct": (pnls.abs() < 2.0).sum() / len(pnls) * 100 if len(pnls) else 0.0,
        "exposure_pct": np.mean(exposure) * 100,
    }, eq


def trail_reentry(df, entry_sig, exit_sig, trend_green, trail_pct=20.0,
                  allow_reentry=True, periods_per_year=365):
    """
    Baseline entries, but exit early if price falls `trail_pct` from the
    in-trade peak. If stopped out while the trend is still green, re-enter on
    the next bar rather than waiting for a fresh crossover.
    """
    entry_sig = entry_sig.reindex(df.index).fillna(False).to_numpy(dtype=bool)
    exit_sig = exit_sig.reindex(df.index).fillna(False).to_numpy(dtype=bool)
    trend = trend_green.reindex(df.index).fillna(False).to_numpy(dtype=bool)

    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)

    equity = COSTS["initial_capital"]
    curve, exposure, pnls = [], [], []
    in_pos = False
    shares = entry_price = peak = 0.0
    pending_entry = pending_exit = False
    stopped_out = False  # blocks re-entry until trend resets

    for i in range(len(df)):
        if pending_entry and not in_pos:
            fill = o[i] * (1 + SLIP)
            shares = (equity * (1 - FEE)) / fill
            entry_price = fill
            peak = h[i]
            in_pos = True
            pending_entry = False

        if pending_exit and in_pos:
            fill = o[i] * (1 - SLIP)
            proceeds = shares * fill * (1 - FEE)
            pnls.append((proceeds / equity - 1) * 100)
            equity = proceeds
            in_pos = False
            shares = 0.0
            pending_exit = False

        if in_pos:
            peak = max(peak, h[i])
            equity_now = shares * c[i]
            # trailing stop is checked intrabar against the low
            if lo[i] <= peak * (1 - trail_pct / 100):
                pending_exit = True
                stopped_out = True
            elif exit_sig[i]:
                pending_exit = True
                stopped_out = False
        else:
            equity_now = equity
            if not trend[i]:
                stopped_out = False  # trend reset — a fresh cross may enter again
            if entry_sig[i]:
                pending_entry = True
                stopped_out = False
            elif allow_reentry and stopped_out and trend[i]:
                pending_entry = True

        curve.append(equity_now)
        exposure.append(1.0 if in_pos else 0.0)

    return _summarize(curve, pnls, exposure, df, periods_per_year)


def scaled_entry(df, entry_sig, exit_sig, add_sig, initial_frac=0.25,
                 periods_per_year=365):
    """
    Enter with `initial_frac` of capital on the Moneyline cross, then scale the
    rest in when contraction+breakout confirms. Exit everything on the
    Moneyline exit. Uncommitted capital sits in cash.
    """
    entry_sig = entry_sig.reindex(df.index).fillna(False).to_numpy(dtype=bool)
    exit_sig = exit_sig.reindex(df.index).fillna(False).to_numpy(dtype=bool)
    add_sig = add_sig.reindex(df.index).fillna(False).to_numpy(dtype=bool)

    o = df["open"].to_numpy(float)
    c = df["close"].to_numpy(float)

    cash = COSTS["initial_capital"]
    shares = 0.0
    curve, exposure, pnls = [], [], []
    pending_entry = pending_add = pending_exit = False
    trade_start_equity = None

    for i in range(len(df)):
        if pending_entry and shares == 0.0:
            fill = o[i] * (1 + SLIP)
            spend = cash * initial_frac
            shares = spend * (1 - FEE) / fill
            cash -= spend
            trade_start_equity = cash + shares * fill
            pending_entry = False

        if pending_add and shares > 0.0 and cash > 0:
            fill = o[i] * (1 + SLIP)
            shares += cash * (1 - FEE) / fill
            cash = 0.0
            pending_add = False

        if pending_exit and shares > 0.0:
            fill = o[i] * (1 - SLIP)
            cash += shares * fill * (1 - FEE)
            shares = 0.0
            if trade_start_equity:
                pnls.append((cash / trade_start_equity - 1) * 100)
            pending_exit = False

        equity_now = cash + shares * c[i]

        if shares > 0.0:
            if exit_sig[i]:
                pending_exit = True
            elif add_sig[i] and cash > 0:
                pending_add = True
        else:
            if entry_sig[i]:
                pending_entry = True

        curve.append(equity_now)
        exposure.append((shares * c[i]) / equity_now if equity_now > 0 else 0.0)

    return _summarize(curve, pnls, exposure, df, periods_per_year)
