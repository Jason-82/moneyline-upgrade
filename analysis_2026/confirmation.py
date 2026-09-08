"""
Decomposing the confirmation-filter tradeoff.

The question: a confirmation filter (breakout / retest / momentum / squeeze)
delays entry after the daily green flip. Prior runs showed it LOWERS total
return. But total return conflates two separate things:

    P(the run turns out to be a real uptrend)      <- confirmation may RAISE this
    E[remaining gain | you are in it]              <- confirmation likely LOWERS this

Those matter differently under leverage. Leverage is punished by the drawdown
distribution (liquidation) and rewarded by consistency, not by raw magnitude.
So a filter that trades magnitude for hit-rate can be inferior unlevered and
superior levered. This measures both halves, then tests the leverage claim.

Every entry is evaluated over the SAME horizon: from the entry bar to the end
of that green run (exit on the red flip). Runs where a confirmation never
triggers are simply not traded - that lost optionality is part of its cost.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DIR = Path(__file__).resolve().parent.parent / "data" / "tv_full"
ASSETS = ["BTC", "ETH", "SOL", "BNB", "ZEC"]


def load(sym):
    df = pd.read_csv(DIR / f"{sym}_1D.csv")
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
    first = int(np.argmax((up.notna() | dn.notna()).to_numpy()))
    return out.iloc[first:]


def runs_of_green(g):
    """[(start_idx, end_idx_inclusive)] for each green run that has closed."""
    g = np.asarray(g, dtype=bool)
    out, i = [], 0
    while i < len(g):
        if g[i] and (i == 0 or not g[i - 1]):
            j = i + 1
            while j < len(g) and g[j]:
                j += 1
            if j < len(g):          # only closed runs
                out.append((i, j - 1))
            i = j
        else:
            i += 1
    return out


# ---------------------------------------------------------------- confirmations
# Each returns the index to enter at, or None if it never confirms in the run.

def c_none(a, b, c, line, bbw, **kw):
    return a


def c_wait(n):
    def f(a, b, c, line, bbw, **kw):
        return a + n if a + n <= b else None
    f.__name__ = f"wait_{n}d"
    return f


def c_momentum(n):
    """Enter n bars later only if price is above the flip price - the run is working."""
    def f(a, b, c, line, bbw, **kw):
        i = a + n
        return i if i <= b and c[i] > c[a] else None
    f.__name__ = f"momo_{n}d"
    return f


def c_breakout(n):
    """Donchian: first close above the highest close of the prior n bars."""
    def f(a, b, c, line, bbw, **kw):
        for i in range(a, b + 1):
            if i - n >= 0 and c[i] > c[i - n:i].max():
                return i
        return None
    f.__name__ = f"breakout_{n}"
    return f


def c_retest(pct):
    """
    Retest-and-hold: price pulls back to within `pct` of the trailing line,
    then closes up. The classic 'wait for the retest' entry.
    """
    def f(a, b, c, line, bbw, **kw):
        touched = False
        for i in range(a, b + 1):
            if not touched and (c[i] / line[i] - 1) <= pct:
                touched = True
            elif touched and c[i] > c[i - 1]:
                return i
        return None
    f.__name__ = f"retest_{int(pct*100)}pct"
    return f


def c_squeeze(a, b, c, line, bbw, **kw):
    """Volatility squeeze: BBW in the 20 bars before the flip was in its bottom quintile."""
    lo = max(0, a - 20)
    win = bbw[lo:a]
    thr = kw["bbw_q20"][a]
    return a if len(win) and np.nanmin(win) < thr else None


def c_weekly(a, b, c, line, bbw, **kw):
    wk = kw["weekly"]
    for i in range(a, b + 1):
        if wk[i]:
            return i
    return None


# ---------------------------------------------------------------- evaluation

def evaluate(sym, conf, weekly=None):
    """Return one row per confirmed entry: remaining gain, MAE, duration."""
    d = load(sym)
    c = d["close"].to_numpy(float)
    line = d["line"].to_numpy(float)
    g = d["green"].to_numpy(bool)

    s = d["close"]
    bbw = ((2 * 2 * s.rolling(20).std()) / s.rolling(20).mean()).to_numpy(float)
    bbw_q20 = pd.Series(bbw).shift(1).rolling(252, min_periods=50).quantile(0.20).to_numpy(float)

    kw = {"bbw_q20": bbw_q20, "weekly": weekly if weekly is not None else np.zeros(len(c), bool)}

    rows = []
    for a, b in runs_of_green(g):
        i = conf(a, b, c, line, bbw, **kw)
        if i is None or i > b:
            continue
        path = c[i:b + 2]                      # include the exit bar
        entry, exit_px = c[i], c[b + 1] if b + 1 < len(c) else c[b]
        mae = (path.min() / entry - 1) * 100   # worst close-to-close drawdown in-trade
        rows.append({
            "asset": sym, "entry_i": i, "run_start": a,
            "delay": i - a, "ret": (exit_px / entry - 1) * 100,
            "mae": mae, "bars": b - i + 1,
        })
    return pd.DataFrame(rows)


def levered_outcome(ret_pct, mae_pct, L, maint=0.0):
    """
    Per-trade outcome at leverage L. Liquidated if the in-trade drawdown
    exhausts the margin: MAE <= -(1/L) * (1 - maint). Then the position is a
    total loss of the capital committed.
    """
    if mae_pct / 100.0 <= -(1.0 / L) * (1 - maint):
        return -1.0
    return L * ret_pct / 100.0


def growth_and_ruin(df, L):
    """Geometric growth per trade and share of trades liquidated."""
    outs = np.array([levered_outcome(r, m, L) for r, m in zip(df["ret"], df["mae"])])
    wiped = (outs <= -1.0)
    if wiped.any():
        return -1.0, wiped.mean() * 100, np.nan
    g = np.log1p(outs)
    return float(np.exp(g.mean()) - 1) * 100, 0.0, float(np.exp(g.sum()) - 1) * 100
