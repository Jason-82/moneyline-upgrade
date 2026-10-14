"""Fixed schedules for C3-C5; see THEORY_LAB_PREREG.md."""
from __future__ import annotations

import numpy as np
import pandas as pd

GLOBAL = ("SPY", "IWM", "EFA", "EEM", "VNQ", "GLD", "IEF", "TLT")


def completed_month_ends(index):
    """Omit the final input month, which may be incomplete.

    If it is complete, its order would mature after the available input anyway.
    This avoids treating October13 as an October31 signal.
    """
    index = pd.DatetimeIndex(index)
    periods = index.to_period("M")
    last = periods[-1]
    return pd.DatetimeIndex(pd.Series(index, index=periods).groupby(level=0).max().loc[lambda s: s.index < last])


def global_momentum(close, slots=3):
    if tuple(close.columns) != GLOBAL:
        close = close.loc[:, GLOBAL]
    scores = sum(close / close.shift(n) - 1 for n in (21, 63, 126, 252)) / 4
    rows = []
    for day in completed_month_ends(close.index):
        s = scores.loc[day]
        if s.isna().any():
            continue
        # Stable symbol ordering breaks exact equal-score ties without future data.
        ranked = s.sort_values(ascending=False, kind="stable")
        names = ranked[ranked > 0].index[:slots]
        w = pd.Series(0.0, index=GLOBAL)
        w.loc[names] = 1 / slots
        rows.append(w.rename(day))
    return pd.DataFrame(rows, columns=GLOBAL)


def quarterly_balanced(close, equity_weight=.5, equity_symbol="SSO"):
    names = [equity_symbol, "GLD"]
    ends = completed_month_ends(close.index)
    ends = ends[ends.month.isin((3, 6, 9, 12))]
    return pd.DataFrame({names[0]: equity_weight, names[1]: 1-equity_weight}, index=ends)


def monthly_equal(close):
    return pd.DataFrame(1 / len(close.columns), index=completed_month_ends(close.index), columns=close.columns)


def crypto_leadership(close, horizon=63, threshold=.05):
    close = close.loc[:, ["BTC", "ETH"]]
    score = close / close.shift(horizon) - 1
    absolute = close / close.shift(90) - 1
    incumbent = None
    rows = []
    for day in completed_month_ends(close.index):
        s, a = score.loc[day], absolute.loc[day]
        if s.isna().any() or a.isna().any():
            continue
        eligible = a[a > 0].index
        if not len(eligible):
            incumbent = None
        else:
            best = s.loc[eligible].sort_values(ascending=False, kind="stable").index[0]
            if incumbent not in eligible or s[best] > s[incumbent] + threshold:
                incumbent = best
        w = pd.Series(0.0, index=close.columns, name=day)
        if incumbent is not None:
            w[incumbent] = 1
        rows.append(w)
    return pd.DataFrame(rows, columns=close.columns)


def hold_schedule(index, names, weights, start, lag=1):
    """Buy passive controls on the common first session, including delay stresses."""
    index = pd.DatetimeIndex(index)
    i = index.get_indexer([pd.Timestamp(start)])[0]
    if i < lag:
        raise ValueError("Passive control lacks prior scheduling dates")
    return pd.DataFrame([weights], index=[index[i-lag]], columns=names)


def flip_schedule(green, start, lag=1):
    """One fixed sleeve: rebalance only when its green/red state changes."""
    start = pd.Timestamp(start)
    g = green.astype(bool)
    i = g.index.get_indexer([start])[0]
    if i < lag:
        raise ValueError("Moneyline control lacks prior signal dates")
    initial_signal = g.index[i-lag]
    selected = g.loc[initial_signal:]
    change = selected.ne(selected.shift(1))
    return pd.DataFrame({green.name: selected[change].astype(float)})


def matched_dates(index, start, end):
    ix = index[(index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))]
    if len(ix) < 2:
        raise ValueError("No common period")
    return ix[0], ix[-1]
