"""Independent re-implementation (auditor's own code) of the prereg §10.2 machinery for a per-fill mean:
CR1 SE (G/(G-1)), G* = (sum n_g^2)^2 / sum n_g^4, p_G* (one-sided t with G*-1 df), wild cluster restricted
bootstrap-t (Webb six-point weights), unrestricted bootstrap-t bound, t bound, Holm, verdicts, month-blocks, episodes.
Written from the prereg text; nothing is imported from analysis_2026.stinkbid_stats."""
import math
import numpy as np
import pandas as pd
from scipy import stats

WEBB = np.array([-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5)])
LEVEL = 1 - 0.05 / 3


def first_appearance_codes(labels):
    labels = np.asarray(labels)
    seen = {}
    out = np.empty(len(labels), np.int64)
    for i, v in enumerate(labels.tolist()):
        if v not in seen:
            seen[v] = len(seen)
        out[i] = seen[v]
    return out, len(seen)


def gstar(sizes):
    n = np.asarray(sizes, float)
    n = n[n > 0]
    return (n ** 2).sum() ** 2 / (n ** 4).sum()


def cr1(y, cl):
    y = np.asarray(y, float)
    c, G = first_appearance_codes(cl)
    n = len(y)
    m = y.mean()
    u = y - m
    U = np.bincount(c, weights=u, minlength=G)
    se = math.sqrt(G / (G - 1) * (U ** 2).sum()) / n
    sizes = np.bincount(c, minlength=G)
    return m, se, G, sizes, c


def weibull_q(x, p):
    """(B+1)p order statistic with linear interpolation (Hyndman-Fan type 6)."""
    x = np.sort(np.asarray(x, float))
    B = len(x)
    h = (B + 1) * p
    if h <= 1:
        return x[0]
    if h >= B:
        return x[-1]
    lo = int(math.floor(h))
    return x[lo - 1] + (h - lo) * (x[lo] - x[lo - 1])


def wild_draws(y, c, G, W):
    """Restricted (null 0) and unrestricted wild cluster bootstrap-t draws for the mean.
    W: (B, G) multipliers, one per cluster code."""
    y = np.asarray(y, float)
    n = len(y)
    cG = G / (G - 1)
    nsz = np.bincount(c, minlength=G).astype(float)
    # restricted: residuals under H0 (theta=0) are y itself
    S = np.bincount(c, weights=y, minlength=G)                     # cluster sums of restricted residuals
    th_r = (W @ S) / n                                             # theta* per draw (B,)
    sums_r = W * S[None, :] - th_r[:, None] * nsz[None, :]          # cluster sums of u* (B, G)
    se_r = np.sqrt(cG * (sums_r ** 2).sum(1)) / n
    t_r = th_r / se_r
    # unrestricted: residuals u = y - mean
    m = y.mean()
    U = np.bincount(c, weights=y - m, minlength=G)
    d = (W @ U) / n                                                # theta* - theta_hat
    sums_u = W * U[None, :] - d[:, None] * nsz[None, :]
    se_u = np.sqrt(cG * (sums_u ** 2).sum(1)) / n
    t_u = d / se_u
    return t_r, t_u


def test_mean(y, cl, E=None, B=9999, seed=20261118, W=None, ptie=True):
    m, se, G, sizes, c = cr1(y, cl)
    gs = gstar(sizes)
    df = gs - 1
    t = m / se
    p_g = float(stats.t.sf(t, df))
    if W is None:
        W = WEBB[np.random.default_rng(seed).integers(0, 6, size=(B, G))]
    t_r, t_u = wild_draws(y, c, G, W)
    Bn = W.shape[0]
    k = int(np.sum(t_r >= t - (1e-10 * max(1, abs(t)) if ptie else 0)))
    p_w = (1 + k) / (Bn + 1)
    p_w_alt = k / Bn
    a = 1 - LEVEL
    ub_boot = m - weibull_q(t_u, a) * se
    ub_t = m + stats.t.ppf(LEVEL, df) * se
    q975 = stats.t.ppf(0.975, df)
    ci_t = (m - q975 * se, m + q975 * se)
    ci_b = (m - weibull_q(t_u, 0.975) * se, m - weibull_q(t_u, 0.025) * se)
    ci = (min(ci_t[0], ci_b[0]), max(ci_t[1], ci_b[1]))
    mde = (stats.t.ppf(LEVEL, df) + stats.t.ppf(0.80, df)) * se
    return dict(n=len(y), G=G, gstar=gs, est=m, se=se, t=t, df=df, p_gstar=p_g, p_wcr=p_w, p_wcr_kB=p_w_alt,
                k_exceed=k, ub_boot=ub_boot, ub_t=ub_t, ub=max(ub_boot, ub_t), p_decide=max(p_w, p_g),
                ci95=ci, ci95_t=ci_t, ci95_boot=ci_b, mde=mde, E=E)


def holm(p):
    p = np.asarray(p, float)
    m = len(p)
    o = np.argsort(p, kind="stable")
    adj = np.empty(m)
    run = 0.0
    levels = np.empty(m)
    rej = np.zeros(m, bool)
    going = True
    for r, i in enumerate(o):
        run = max(run, (m - r) * p[i])
        adj[i] = min(run, 1.0)
        levels[i] = 0.05 / (m - r)
        going = going and p[i] < levels[i]
        rej[i] = going
    return adj, levels, rej


def verdict(p_holm, gates_ok, ub, E):
    """§10.3 with A1.8/A2.3: NO EDGE takes precedence over PASS."""
    if ub < E:
        return "NO EDGE (HARMS)" if ub < 0 else "NO EDGE"
    if p_holm < 0.05 and gates_ok:
        return "PASS"
    return "INCONCLUSIVE"


# ----------------------------------------------------------------------- clusters from fill times (my own code)
def utc_days(times):
    t = pd.to_datetime(pd.Series(times), utc=True)
    return t.dt.tz_localize(None).dt.floor("D").to_numpy()


def my_episodes(times, gap=3):
    """Runs of distinct UTC fill days at most `gap` days apart."""
    d = utc_days(times)
    u = np.unique(d)
    ep_of_day = {}
    e = 0
    prev = None
    for day in u:
        if prev is not None and (day - prev) / np.timedelta64(1, "D") > gap:
            e += 1
        ep_of_day[day] = e
        prev = day
    return np.array([ep_of_day[x] for x in d])


def my_month_blocks(times, gap=3):
    """Calendar months (UTC) merged when an episode has fills in two months (transitively)."""
    t = pd.to_datetime(pd.Series(times), utc=True).dt.tz_localize(None)
    mon = (t.dt.year * 12 + t.dt.month - 1).to_numpy()
    ep = my_episodes(times, gap)
    months = sorted(set(mon.tolist()))
    parent = {m: m for m in months}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e in np.unique(ep):
        ms = sorted(set(mon[ep == e].tolist()))
        for a, b in zip(ms[:-1], ms[1:]):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    roots = sorted(set(find(m) for m in months))
    rid = {r: i for i, r in enumerate(roots)}
    return np.array([rid[find(m)] for m in mon]), ep
