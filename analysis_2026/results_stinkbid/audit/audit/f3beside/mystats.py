"""Independent statistics for the audit (written from STINKBID_PREREG.md §10.2; nothing imported from stinkbid_stats).

- clusters: month-blocks = calendar months (UTC) of the fills, merged (transitively) when an episode has fills in
  both; an episode = a run of distinct UTC fill days at most 3 days apart.
- mean, CR1 SE (G/(G-1)), G* = (sum n_g^2)^2 / sum n_g^4, t referred to Student t with G* - 1 df.
- wild cluster bootstrap-t with Webb six-point weights, restricted (null 0 imposed) for p_WCR and unrestricted for
  the bound and the bootstrap interval; B = 9,999; my own seed.
"""
import numpy as np
import pandas as pd
from scipy import stats

WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])


def month_blocks(times) -> np.ndarray:
    t = pd.to_datetime(pd.Series(times), utc=True).dt.tz_localize(None)
    day = t.dt.floor("D").to_numpy("datetime64[D]")
    ud = np.unique(day)
    gaps = np.diff(ud).astype(np.int64)
    ep_of_ud = np.cumsum(np.r_[True, gaps > 3]) - 1
    ep = ep_of_ud[np.searchsorted(ud, day)]
    mon = (t.dt.year * 12 + t.dt.month - 1).to_numpy()
    # union-find over months
    parent = {m: m for m in np.unique(mon)}

    def root(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e in np.unique(ep):
        ms = np.unique(mon[ep == e])
        for a, b in zip(ms[:-1], ms[1:]):
            ra, rb = root(a), root(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    r = np.array([root(m) for m in mon])
    _, ids = np.unique(r, return_inverse=True)
    return ids


def episodes(times) -> np.ndarray:
    t = pd.to_datetime(pd.Series(times), utc=True).dt.tz_localize(None)
    day = t.dt.floor("D").to_numpy("datetime64[D]")
    ud = np.unique(day)
    ep_of_ud = np.cumsum(np.r_[True, np.diff(ud).astype(np.int64) > 3]) - 1
    return ep_of_ud[np.searchsorted(ud, day)]


def cr1(y, g):
    y = np.asarray(y, float)
    g = np.asarray(g)
    _, gi = np.unique(g, return_inverse=True)
    G = gi.max() + 1
    n = len(y)
    m = y.mean()
    h = np.bincount(gi, weights=y - m, minlength=G)
    se = np.sqrt(G / (G - 1) * (h ** 2).sum()) / n
    sizes = np.bincount(gi, minlength=G).astype(float)
    gs = (sizes ** 2).sum() ** 2 / (sizes ** 4).sum()
    return m, se, G, gs, gi


def wild_t(y, gi, G, centre, resid, B, rng):
    """t* = (theta* - centre) / se* with y* = centre + w_g resid (one cluster weight per draw)."""
    n = len(y)
    W = WEBB[rng.integers(0, 6, size=(B, G))]                  # (B, G)
    S = np.bincount(gi, weights=resid, minlength=G)            # cluster sums of resid
    N = np.bincount(gi, minlength=G).astype(float)
    # theta* = centre + (W @ S) / n ; residual sums of y* about theta*: W_g S_g - N_g (theta* - centre)
    d = (W @ S) / n
    H = W * S[None, :] - d[:, None] * N[None, :]
    se = np.sqrt(G / (G - 1) * (H ** 2).sum(axis=1)) / n
    return d / se


def full_test(y, g, B=9999, seed=777, level=1 - 0.05 / 3):
    y = np.asarray(y, float)
    m, se, G, gs, gi = cr1(y, g)
    df = gs - 1
    t = m / se
    p_g = float(stats.t.sf(t, df))
    rng = np.random.default_rng(seed)
    tr = wild_t(y, gi, G, 0.0, y - 0.0, B, rng)                 # restricted: null 0, residual = y
    p_w = float((1 + np.sum(tr >= t - 1e-10 * max(1, abs(t)))) / (B + 1))
    tu = wild_t(y, gi, G, m, y - m, B, rng)                     # unrestricted
    ub_boot = m - np.quantile(tu, 1 - level) * se
    ub_t = m + stats.t.ppf(level, df) * se
    q = stats.t.ppf(0.975, df)
    ci_t = (m - q * se, m + q * se)
    ci_b = (m - np.quantile(tu, 0.975) * se, m - np.quantile(tu, 0.025) * se)
    ci = (min(ci_t[0], ci_b[0]), max(ci_t[1], ci_b[1]))
    mde = (stats.t.ppf(1 - 0.05 / 3, df) + stats.t.ppf(0.80, df)) * se
    return dict(n=len(y), estimate=m, se=se, G=int(G), gstar=gs, t=t, p_gstar=p_g, p_wcr=p_w, p_decide=max(p_g, p_w),
                ub_t=ub_t, ub_boot=ub_boot, ub=max(ub_t, ub_boot), ci_t=ci_t, ci_b=ci_b, ci95=ci, mde=mde)
