"""
Indicator exit vs indicator + ATR stop ("sell at whichever hits first").

The indicator is itself an ATR trailing stop: on a flip the line sits a median
~2.4 daily ATR below close, and ~1.7 ATR below during a run. So adding an ATR
stop is not adding a new kind of exit - it is adding a second, usually tighter,
copy of the same one. What matters is its shape:

  fixed   stop = entry_close - k * ATR_at_entry, never moves. Only bites early in
          a trade, before the indicator line ratchets up past it.
  trail   stop = highest close since entry - k * ATR (ratchets up). Competes with
          the indicator for the whole life of the trade.

ATR source:
  daily   the daily ATR column from the daily export
  weekly  the weekly ATR of the last COMPLETED week (shift 1, forward-filled), so
          a stop set mid-week never sees the week still forming

Stop detection (close-only data, so two conventions):
  wick = 0     "stop on daily close": exit when close <= stop, fill at that close
  wick = w>0   intraday stop-order proxy: assume the bar's low reaches
               close - w*ATR; if that touches the stop, fill AT the stop price.
               w=0.3-0.6 brackets a typical crypto lower wick. This triggers more
               often than close-based stops (wicks that recover) - the realistic
               cost of a resting stop order.

Re-entry after a stop-out while the indicator is still green:
  none   stay flat until the next green flip (the rule as Ivan describes it)
  entry  re-enter on the first close back above the stopped trade's entry
  high   re-enter on the first close above the pre-stop high-water close

All fills at close (same-bar), 0.1% fee + 5bp slippage per side, matching every
other crypto result in this project.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis_2026.run_full import load, ASSETS  # noqa: E402

FEE, SLIP = 0.001, 0.0005


def weekly_atr_on_daily(sym, idx):
    w = load(sym, "1W")
    return w["atr"].shift(1).reindex(idx, method="ffill")


def simulate(sym, mode="none", k=1.5, atr_src="daily", reentry="none", wick=0.0,
             start=None, end=None):
    """
    Bar-by-bar simulation. Returns (metrics dict, trades DataFrame, equity Series).

    mode: "none" (indicator only) | "fixed" | "trail"
    """
    d = load(sym, "1D")
    d = d.assign(watr=weekly_atr_on_daily(sym, d.index))
    if start is not None:
        d = d[d.index >= start]
    if end is not None:
        d = d[d.index <= end]
    d = d.dropna(subset=["atr"])

    c = d["close"].to_numpy(float)
    g = d["green"].to_numpy(bool)
    datr = d["atr"].to_numpy(float)
    watr = d["watr"].to_numpy(float)
    A = watr if atr_src == "weekly" else datr
    n = len(c)

    run_id = np.full(n, -1)
    rid = -1
    for i in range(n):
        if g[i] and (i == 0 or not g[i - 1]):
            rid += 1
        if g[i]:
            run_id[i] = rid

    cash = 1.0
    shares = 0.0
    curve = np.empty(n)
    trades = []

    in_pos = False
    stop = np.nan            # stop level known at the end of the previous bar
    hw = np.nan              # high-water close since entry
    entry_px = np.nan
    entry_cash = np.nan
    entry_i = -1
    stopped_this_run = False # a stop-out happened in the current green run
    reentry_level = np.nan

    def open_pos(i):
        nonlocal cash, shares, in_pos, stop, hw, entry_px, entry_cash, entry_i
        px = c[i] * (1 + SLIP)
        shares = cash * (1 - FEE) / px
        entry_cash = cash
        cash = 0.0
        in_pos = True
        entry_px = c[i]
        entry_i = i
        hw = c[i]
        if mode == "none" or np.isnan(A[i]):
            stop = -np.inf
        else:
            stop = c[i] - k * A[i]

    def close_pos(i, fill, reason):
        nonlocal cash, shares, in_pos
        px = fill * (1 - SLIP)
        cash = shares * px * (1 - FEE)
        shares = 0.0
        in_pos = False
        trades.append({
            "asset": sym, "entry": d.index[entry_i], "exit": d.index[i],
            "entry_px": entry_px, "exit_px": fill, "ret": (cash / entry_cash - 1) * 100,
            "reason": reason, "run": run_id[entry_i], "bars": i - entry_i,
        })

    for i in range(n):
        flip_up = g[i] and (i == 0 or not g[i - 1])
        if flip_up:
            stopped_this_run = False

        if in_pos:
            # 1) stop, checked against the level set at the end of the prior bar
            low_proxy = c[i] - wick * datr[i]
            stop_hit = mode != "none" and low_proxy <= stop
            # A close-based stop that fires on the same close as the indicator flip
            # is redundant: same bar, same fill. Credit it to the indicator so the
            # stop-exit count only reflects exits the stop actually caused.
            if stop_hit and wick == 0 and not g[i]:
                stop_hit = False
            if stop_hit:
                fill = stop if wick > 0 else c[i]
                reentry_level = entry_px if reentry == "entry" else hw
                close_pos(i, fill, "stop")
                stopped_this_run = g[i]
            # 2) indicator flip to red
            elif not g[i]:
                close_pos(i, c[i], "indicator")
            else:
                # 3) carry the trade: update trailing stop for the NEXT bar
                hw = max(hw, c[i])
                if mode == "trail" and not np.isnan(A[i]):
                    stop = max(stop, hw - k * A[i])

        if not in_pos:
            if mode == "none":
                if g[i]:
                    open_pos(i)
            elif flip_up:
                open_pos(i)
            elif (g[i] and stopped_this_run and reentry != "none"
                  and c[i] > reentry_level and (len(trades) == 0 or trades[-1]["exit"] != d.index[i])):
                open_pos(i)

        curve[i] = cash + shares * c[i]

    eq = pd.Series(curve, index=d.index)
    tr = pd.DataFrame(trades)
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    r = eq.pct_change().dropna()
    wins = tr[tr.ret > 0] if len(tr) else tr
    loss = tr[tr.ret <= 0] if len(tr) else tr
    m = {
        "return_pct": (eq.iloc[-1] - 1) * 100,
        "cagr_pct": (eq.iloc[-1] ** (1 / yrs) - 1) * 100 if eq.iloc[-1] > 0 else np.nan,
        "max_dd_pct": ((eq / eq.cummax()) - 1).min() * 100,
        "sharpe": r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else 0.0,
        "trades": len(tr),
        "stop_exits": int((tr.reason == "stop").sum()) if len(tr) else 0,
        "win_rate": len(wins) / len(tr) * 100 if len(tr) else np.nan,
        "avg_win": wins.ret.mean() if len(wins) else np.nan,
        "avg_loss": loss.ret.mean() if len(loss) else np.nan,
        "exposure_pct": float(np.mean(np.diff(np.r_[0, curve]) != 0)) * 0 + 0,  # filled below
    }
    held = np.zeros(n, dtype=bool)
    for t in trades:
        a = d.index.get_loc(t["entry"]); b = d.index.get_loc(t["exit"])
        held[a:b] = True
    m["exposure_pct"] = held.mean() * 100
    return m, tr, eq


def run_attribution(sym, **kw):
    """
    Per green run: indicator-only P&L vs stop-strategy P&L over the same run.
    Tells you whether the stop helped by cutting a loser or hurt by cutting a
    winner, and by how much.
    """
    _, base, _ = simulate(sym, mode="none")
    _, alt, _ = simulate(sym, **kw)
    if base.empty:
        return pd.DataFrame()
    b = base.groupby("run")["ret"].apply(lambda x: (np.prod(1 + x / 100) - 1) * 100)
    a = alt.groupby("run")["ret"].apply(lambda x: (np.prod(1 + x / 100) - 1) * 100) if len(alt) else pd.Series(dtype=float)
    stopped = alt[alt.reason == "stop"]["run"].unique() if len(alt) else []
    out = pd.DataFrame({"base": b}).join(pd.DataFrame({"alt": a}), how="left")
    out["alt"] = out["alt"].fillna(0.0)
    out["stopped"] = out.index.isin(stopped)
    out["asset"] = sym
    return out
