"""Shared helpers for the H1 fairness audit (independent code; no import of stinkbid_stats / engine functions)."""
import math
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats as st

ROOT = "/home/user/moneyline-upgrade"
RUN = f"{ROOT}/data/stinkbid/runs/outcomes"
RES = f"{ROOT}/analysis_2026/results_stinkbid"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair"


def load_out(run="P1__U_Q1", rule="F1", exit="FLIP", lat="M", cost="C-RH", cols=None):
    f = f"{RUN}/{run}/outcomes.parquet"
    filt = [("rule", "=", rule), ("exit", "=", exit), ("lat", "=", lat), ("cost", "=", cost)]
    return pd.read_parquet(f, filters=filt, columns=cols)


def load_fills(run="P1__U_Q1", cols=None):
    return pd.read_parquet(f"{RUN}/{run}/fills.parquet", columns=cols)


def min2ts(m):
    return pd.to_datetime(np.asarray(m, np.int64) * 60, unit="s", utc=True)


def episodes_from_times(tmin):
    """Episode = run of fill days at most 3 days apart (prereg §10.2). Returns episode id per fill (input order)."""
    d = np.asarray(tmin, np.int64) // 1440
    o = np.argsort(d, kind="stable")
    ds = d[o]
    ud = np.unique(ds)
    brk = np.r_[True, np.diff(ud) > 3]
    epi_of_day = np.cumsum(brk) - 1
    e = epi_of_day[np.searchsorted(ud, ds)]
    out = np.empty(len(d), np.int64)
    out[o] = e
    return out


def month_blocks_from_times(tmin):
    """Calendar months of the fill merged into blocks when an episode spans two months (my reading of §10.2):
    union-find over months linked by episodes."""
    tmin = np.asarray(tmin, np.int64)
    ep = episodes_from_times(tmin)
    ts = min2ts(tmin)
    mon = (ts.year * 12 + ts.month - 1).to_numpy()
    um = np.unique(mon)
    parent = {m: m for m in um}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in np.unique(ep):
        ms = np.unique(mon[ep == e])
        for a in ms[1:]:
            ra, rb = find(ms[0]), find(a)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    root = np.array([find(m) for m in mon])
    _, blk = np.unique(root, return_inverse=True)
    return blk, ep


def cr1(y, g):
    """Mean with one-way CR1 SE (G/(G-1)), G*, and t-test p (one-sided, G*-1 df)."""
    y = np.asarray(y, float)
    g = np.asarray(g)
    ok = np.isfinite(y)
    y, g = y[ok], g[ok]
    n = len(y)
    if n < 2:
        return dict(n=n, mean=np.nan, se=np.nan, G=0, gstar=np.nan, t=np.nan, p=np.nan, lo=np.nan, hi=np.nan)
    mu = y.mean()
    e = y - mu
    ug, gi = np.unique(g, return_inverse=True)
    G = len(ug)
    S = np.bincount(gi, weights=e)
    se = math.sqrt(G / (G - 1) * (S ** 2).sum()) / n if G > 1 else np.nan
    ng = np.bincount(gi).astype(float)
    gs = (ng ** 2).sum() ** 2 / (ng ** 4).sum()
    t = mu / se if se and se > 0 else np.nan
    df = max(gs - 1, 1e-9)
    p = 1 - st.t.cdf(t, df) if np.isfinite(t) else np.nan
    q = st.t.ppf(0.975, df)
    return dict(n=n, mean=mu, se=se, G=G, gstar=gs, t=t, p=p, lo=mu - q * se, hi=mu + q * se)


def fmt(d, pct=True):
    k = 100 if pct else 1
    return (f"n={d['n']:5d} mean={k*d['mean']:+7.2f}% se={k*d['se']:5.2f} t={d['t']:5.2f} p1={d['p']:.4f} "
            f"G={d['G']} G*={d['gstar']:.1f} CI[{k*d['lo']:+.2f},{k*d['hi']:+.2f}]")
