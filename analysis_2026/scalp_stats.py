"""
Shared inference for the scalping study (analysis_2026/SCALPING_PREREG.md, "General rules").

- nw_t(x, lags)                     Newey-West t of the mean of a series (Bartlett kernel)
- cluster2_t(x, g1, g2)             mean of x with Cameron-Gelbach-Miller two-way cluster-robust SE,
                                    Student t at min(G1, G2) - 1 df (falls back to the larger one-way
                                    variance if the two-way variance is not positive)
- ratio_cluster2(num, den, g1, g2)  sum(num)/sum(den) with a two-way clustered delta-method SE
- holm(p)                           Holm-adjusted p-values
- verdict(...)                      PASS / NO EDGE / INCONCLUSIVE
All p-values are one-sided for "mean > 0".
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

N_PRIMARY = 36            # study-wide Holm family: A 12, B 16, E 4, C 4
ALPHA = 0.05


def nw_t(x, lags: int = 10):
    """Return (mean, se, t, one-sided p) with a Newey-West (Bartlett) long-run variance."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return np.nan, np.nan, np.nan, np.nan
    m = x.mean(); e = x - m
    v = e @ e / n
    for L in range(1, min(lags, n - 1) + 1):
        w = 1 - L / (lags + 1)
        v += 2 * w * (e[L:] @ e[:-L]) / n
    se = math.sqrt(max(v, 0) / n)
    t = m / se if se > 0 else np.nan
    return m, se, t, (1 - stats.norm.cdf(t)) if np.isfinite(t) else np.nan


def _cluster_var(e, g):
    """Variance of sum(e)/n with clusters g (sum of squared cluster sums / n^2, with small-G correction)."""
    _, inv = np.unique(g, return_inverse=True)
    s = np.bincount(inv, weights=e)
    G = len(s); n = len(e)
    if G < 2:
        return np.nan, G
    return (G / (G - 1)) * (s @ s) / n ** 2, G


def cluster2_se(e, g1, g2):
    """Two-way cluster-robust variance of the mean of residuals e. Returns (se, G)."""
    e = np.asarray(e, float)
    v1, G1 = _cluster_var(e, g1)
    v2, G2 = _cluster_var(e, g2)
    g12 = np.char.add(np.asarray(g1).astype(str), np.char.add("|", np.asarray(g2).astype(str)))
    v12, _ = _cluster_var(e, g12)
    v = v1 + v2 - v12
    if not (v > 0):
        v = max(v1, v2)
    return math.sqrt(v), min(G1, G2)


def cluster2_t(x, g1, g2):
    """Return (mean, se, t, one-sided p, df) for the mean of x, clustered two ways."""
    x = np.asarray(x, float)
    k = np.isfinite(x)
    x, g1, g2 = x[k], np.asarray(g1)[k], np.asarray(g2)[k]
    if len(x) < 3:
        return np.nan, np.nan, np.nan, np.nan, 0
    m = x.mean()
    se, G = cluster2_se(x - m, g1, g2)
    df = max(G - 1, 1)
    t = m / se if se > 0 else np.nan
    return m, se, t, (1 - stats.t.cdf(t, df)) if np.isfinite(t) else np.nan, df


def ratio_cluster2(num, den, g1, g2):
    """R = sum(num)/sum(den) with a two-way clustered delta-method SE. Returns (R, se, df)."""
    num = np.asarray(num, float); den = np.asarray(den, float)
    if den.sum() <= 0:
        return np.nan, np.nan, 0
    R = num.sum() / den.sum()
    # linearisation: z_i = (num_i - R den_i) / mean(den); mean(z) = 0; var(R) = var(mean z)
    z = (num - R * den) / den.mean()
    se, G = cluster2_se(z, g1, g2)
    return R, se, max(G - 1, 1)


def holm(p):
    """Holm step-down adjusted p-values (NaN treated as 1)."""
    p = np.asarray(p, float)
    q = np.where(np.isfinite(p), p, 1.0)
    n = len(q); o = np.argsort(q)
    adj = np.empty(n); run = 0.0
    for r, i in enumerate(o):
        run = max(run, (n - r) * q[i])
        adj[i] = min(run, 1.0)
    return adj


def upper_bound(m, se, df=None, level=1 - ALPHA / N_PRIMARY):
    """One-sided upper confidence bound of the mean."""
    q = stats.t.ppf(level, df) if df else stats.norm.ppf(level)
    return m + q * se


def mde(se, df=None, alpha=ALPHA / N_PRIMARY, power=0.80):
    q = stats.t.ppf(1 - alpha, df) if df else stats.norm.ppf(1 - alpha)
    return (q + stats.norm.ppf(power)) * se


def verdict(p_holm, other_conditions_ok: bool, ub_edge, threshold):
    """PASS if Holm p < 0.05 and every other condition holds; NO EDGE if the (1 - 0.05/36) upper bound of the
    edge is below the economic threshold E; else INCONCLUSIVE."""
    if np.isfinite(p_holm) and p_holm < ALPHA and other_conditions_ok:
        return "PASS"
    if np.isfinite(ub_edge) and ub_edge < threshold:
        return "NO EDGE"
    return "INCONCLUSIVE"


def boot_p(stat_hat, boot_stats):
    """One-sided bootstrap p for stat > 0 from centred resamples: (1 + #{b: s*_b - s_hat >= s_hat}) / (B + 1)."""
    b = np.asarray(boot_stats, float)
    return (1 + np.sum(b - stat_hat >= stat_hat)) / (len(b) + 1)


def drop_worst(values, groups):
    """Mean after removing the single group whose removal lowers the mean most (values aligned with groups).
    Returns (mean_after, dropped_group)."""
    v = np.asarray(values, float); g = np.asarray(groups)
    tot, n = v.sum(), len(v)
    u, inv = np.unique(g, return_inverse=True)
    s = np.bincount(inv, weights=v); c = np.bincount(inv)
    means = (tot - s) / np.maximum(n - c, 1)
    j = int(np.argmin(means))
    return float(means[j]), u[j]
