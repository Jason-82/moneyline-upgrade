"""
Inference and descriptive statistics for the stink-bid study (analysis_2026/STINKBID_PREREG.md, FROZEN 2026-11-18,
commit 72ac2a4): §10.2 "Units, clusters and the p-value", §10.3 "The Holm family" and "Verdicts", §10.4
"Pre-registered descriptive estimands" (D-H2, D-H3, D-H5, T1, D5, D6, D7, D11, concentration, single events) and
§10.5 K3 "inference". Contract: research_notes/Stink bids/build_spec.md, "stinkbid_stats.py". Every p-value is
one-sided for "effect > 0". No market data is read by this module.

    python3 -m analysis_2026.stinkbid_stats selftest          # synthetic known-answer checks (~3 min on 4 CPUs)
    python3 -m analysis_2026.stinkbid_stats selftest --quick  # fewer replications (~40 s)

Public API
  Clusters, from fill timestamps (UTC)
    fill_days(t); episodes(t, gap_days=3) -> (ids, table); month_blocks(t) / quarter_blocks(t) -> (ids, table)
    month_key(t), quarter_key(t), year_key(t), week_key(t) (bid weeks from Monday 03:30 UTC), half_key(t)
    gstar(sizes), gstar_labels(labels), eff_clusters(sizes)
  The decisive tests (§10.2, §10.3)
    test_mean(y, clusters, E_=None, ...) -> dict    H1 (mean Δ_f), H2R (mean a_f); any per-fill mean
    test_coef(y, X, j, clusters, fe=None, ...) -> dict   the same machinery for one OLS coefficient (one-way FE
                                                    absorbed; D-H3 with episode fixed effects)
    test_h4(methods, ...) -> dict                   H4: stacked regression per method with coin-week FE and the depth
                                                    term, Romano-Wolf max-t, Bonferroni t(G*-1) companion;
                                                    out["clusters"] = the month-block partition it used, per method
    h4_clusters(methods)                            that partition without running the test
    h4_fit(frame, mask=None, clusters=), h4_drop_worst_block(frame, clusters=)   H4's gates (halves, worst block,
                                                    F3), on test_h4's partition (clusters= or a `cluster` column)
    cr1_mean(y, clusters), ols_fe(y, X, fe, clusters)             CR1 with the factor G/(G-1)
    webb_weights(B, G, rng), wild_t(y, X, j, clusters, W, ...)    the wild cluster bootstrap-t draws
    romano_wolf(t, tstar) -> step-down adjusted p-values
  Multiplicity and verdicts
    holm(p) (= scalp_stats.holm), holm_levels(p), bh(p) (= bb_stats.bh), E, E_SENS, e_h1(...), mde(se, gstar),
    verdict(p_holm, gates_ok, ub, E_), family_verdicts(rows, gates) -> DataFrame (always the three family tests)
  Gates and concentration (§10.3, §10.4)
    drop_worst_group_mean(y, g), drop_biggest_group_mean(y, g), top_k_share(y, g, k=3)
  Descriptive machinery (§10.4)
    ols_cluster2(y, X, g1, g2), mean_cluster2(y, g1, g2)   two-way CR1, Student t at min(G1, G2) - 1 df (D-H5)
    ibragimov_muller(estimates), im_ols(y, X, groups, j)   (D-H5 sensitivity over fill-years)
    p0_knife(sigma30), decile_dummies(x), dh5_fit(...), dh5_im(...), dh5_drop_worst_coin(...)
    kaplan_meier(time, event), km_survival(time, event, at), km_restricted_mean(time, event, horizon=365),
      km_median(time, event), waiting_summary(time, event, horizon=365)            (D6, the sheet)
    overdispersion_phi(x, n), wilson(x, n, level=0.95, phi=1)                      (the sheet's fill odds, S14)
    stationary_bootstrap(x, y=None, stat="mean"|"cagr"|"sharpe"|fn, mean_block=6, ...)   (D7: 6 and 12 months)
    ratio_cluster_bootstrap(num, den, clusters, ...), cluster_bootstrap(fn, arrays, clusters, ...),
      d5_calibration(realized, predicted, clusters, half, ...)           (episode-cluster bootstrap: D5, T1)
    mu_star(F, theta, W, theta_ci=None)                                            (D6 break-even)
  K3 (§10.5)
    inference_calibration(sim_fn, n_reps=2000, scenarios=("base", "high", "hetero"), ...) -> dict
    calibrated_p(test, stat_obs, calib), calibrated_bound(test, est, se, calib), apply_calibration(row, test, calib),
    d11_percentile(total_obs, calib)
    sim_fn(scenario, rep, rng) -> {"H1": {"y", "clusters", "truth"=0}, "H2R": {...},
                                   "H4": {"methods": {name: frame}, "truth"=0 or {name: value}}}   (any subset)

Statistics as the pre-registration fixes them
- Unit: the fill; each fill counts once (weights= gives the size-weighted sensitivity).
- Clusters: calendar months of the fill merged into month-blocks when an episode (a run of fill days at most 3 days
  apart) spans two months. CR1 with the factor G/(G-1). G* = (sum n_g^2)^2 / sum n_g^4 over the clusters with fills.
- p = max(p_WCR, p_G*): p_WCR is the wild cluster restricted bootstrap-t (null imposed, Webb six-point weights,
  B = 9,999, CR1-studentized); p_G* is the CR1 t referred to Student t with G* - 1 df.
- NO EDGE bound at one-sided 1 - 0.05/3 = 98.33%: the larger of the unrestricted wild bootstrap-t bound (same
  weights) and theta_hat + t_{1-0.05/3, G*-1} SE. NO EDGE if it is below E, NO EDGE (HARMS) if below 0.
- H4, per method j: Delta_f = alpha_cw + b_j real_f + c_j (delta_f - delta_real,cw) + e_f, coin-week fixed effects,
  month-block clusters. T = max_j t_j. p_WCR: Romano-Wolf max-t with wild (Webb) multipliers on the month-block score
  sums (recentred, each t*_j CR1-studentized); p_G* = 4 x the one-sided t(G* - 1) p of the largest t_j, capped at 1.
- One Holm family of three one-sided tests at 5% (H1, H2R, H4) on the decisive p-values; descriptive p-values are
  BH-adjusted within their table. MDE = (t_{1-0.05/3, G*-1} + t_{0.80, G*-1}) SE.
- E: H1 3.75% per fill (2.26% if reserved cash earns 3.35%, a sensitivity), H2R 2% per fill, H4 1% per fill.

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. Bootstrap p-values: p_WCR = (1 + #{b : t*_b >= t_hat}) / (B + 1), one-sided upper tail; ties and undefined draws
   (zero SE) count as exceedances, a tie being a draw within 1e-10 x max(1, |t_hat|) of t_hat (the all-ones multiplier
   draw reproduces the sample, and rounding must not drop it). Bootstrap quantiles use the (B + 1) alpha ("weibull")
   order statistic; undefined draws sit at the conservative end. The restricted (p) and unrestricted (bounds)
   bootstraps reuse the same multiplier draws. Multipliers are drawn per cluster from default_rng(seed) (seed 20261118
   unless given).
2. CR1 is the factor G/(G-1) only (no (N-1)/(N-K)). G* counts fills (n_g), also under size-weighting. p_G* uses Student
   t with the non-integer df G* - 1; it is NaN when G* <= 1 or G < 2, and a NaN p never passes (Holm treats it as 1).
   With one cluster (G < 2) the point estimate is still reported when identified (test_coef, describe, test_h4's
   per-method b and c); its SE, t, p-values, bounds, intervals and MDE are NaN.
3. The wild bootstrap is the exact wild cluster bootstrap of the whole model: every draw re-absorbs the fixed effects
   and re-estimates every coefficient, and its CR1 SE uses the draw's own residuals. It is computed from cluster-level
   quantities (scores X_g'u_g, cross-products X_g'X_g, and a correction for fixed-effect groups that straddle two
   clusters, e.g. a coin-week whose fills fall in two month-blocks); the selftest checks it against brute-force
   dummy-variable re-estimation (asserted to 1e-8; observed about 2e-13).
4. The reported 95% interval is the union of the unrestricted wild bootstrap-t equal-tailed interval and
   theta_hat +- t_{0.975, G*-1} SE: the interval analogue of the max rule (it is never narrower than either).
5. MDE = (t_{1-alpha_b, G*-1} + t_{0.80, G*-1}) SE with alpha_b = 0.05/3 (draft §12.1 with G* and the three-test
   family). For H4 it uses the argmax method's SE and G*; the version at alpha_b/4, which matches H4's Bonferroni
   companion, is reported beside it (mde_bonf). Descriptive rows use the same alpha_b unless told otherwise.
6. H4: coin-weeks with a single stacked fill are dropped before fitting (they are fitted exactly by their own fixed
   effect and carry no information; the reghdfe convention); n_g, G and G* count the remaining stacked fills of the
   method. Each frame must have y, real, depth and cw (ValueError otherwise: the coin-week fixed effects are part of
   the pre-registered model and are never dropped silently; other names via cols=). All four methods use ONE
   month-block partition (the frames' `cluster` columns, or month_blocks() on the union of all methods' stacked fill
   times when every frame has `time` and none has `cluster`; a mix is refused), so a block's multiplier is shared
   across methods and the bootstrap keeps their dependence. test_h4 returns that partition (out["clusters"], per
   method, aligned with the frame's rows; h4_clusters() computes it alone), and the gate helpers h4_fit and
   h4_drop_worst_block take it as clusters= (or a `cluster` column): they never rebuild month-blocks from one
   method's fills, which would be a different partition from the test's. The Romano-Wolf bootstrap is unrestricted
   and recentred, t*_j = (b*_j - b_j)/se*_j; the omnibus
   p_WCR = (1 + #{b : max_j t*_jb >= T}) / (B + 1) = the step-down adjusted p of the argmax method (Romano-Wolf 2016
   algorithm; the per-method adjusted p feeds the sheet rule of §13, which names it; the table also carries p_bonf =
   n_bonf x the method's one-sided t(G*-1) p and p_method = max(p_rw, p_bonf), the §10.2 max rule applied per method,
   as a conservative companion the sheet may prefer). n_bonf = 4 = len(H4_METHODS) by default, whatever is passed
   (§10.3: "Bonferroni over the four methods"); a warning names a pre-registered method that is absent, and an n_bonf
   below the number of methods passed is refused. H4's NO EDGE bound is simultaneous over methods at 1 - 0.05/3: per
   method max(b_j - q_a(min_j t*_j) se_j, b_j + t_{1-a/n_bonf, G*_j - 1} se_j), a = 0.05/3; H4's bound is the
   largest over methods (NO EDGE says no method beats plain levels by E or more). It exists only if every one of the
   n_bonf methods has a bound: a method that is absent, empty, has G < 2 or is not identified leaves H4's bound NaN
   (never NO EDGE; listed in out["unbounded"]), because §11's NO EDGE sentence speaks for all four chart methods. A
   K3 "miss" is any method's bound below its truth. A method's 95% interval is the union of the simultaneous
   bootstrap interval (the 95% quantile of max_j |t*_j|) and b_j +- t_{1-0.025/n_bonf, G*_j-1} se_j; H4's reported
   estimate, SE, G*, interval and MDE are the argmax method's. The depth regressor may be delta_f - delta_real,cw or
   delta_f: the coin-week effects absorb delta_real,cw, so b_j is identical.
7. E["H1"] = 3.75% and E_SENS["H1_gold"] = 2.26% as printed in §10.3; e_h1() reproduces the formula (3.745% and
   2.263% before rounding).
8. verdict(): NO EDGE (the 98.33% bound below E) takes precedence over PASS (Holm p < 0.05 and every gate True)
   when both hold (prereg Addendum 1, A1.8: E is the smallest effect worth acting on; §11's NO EDGE advice
   applies), and family_verdicts() flags that case (pass_and_noedge) so the report states both facts. A gate that is None/NaN/missing counts as not met. A NaN bound
   is never NO EDGE. family_verdicts() always runs Holm over the three family tests (§10.3: "Holm runs on all three
   p-values"): a test whose row is missing (or None) enters with p = NaN, counted as 1, is reported INCONCLUSIVE with
   row_given = False, and a warning is issued; a key outside the family is refused.
9. Holm: scalp_stats.holm (NaN = 1). "The Holm level at which H4 was rejected" (§13) = alpha/(m - r + 1) at H4's step
   r (holm_levels). BH: bb_stats.bh (NaN left out of m).
10. Episodes use UTC calendar days of the fills: consecutive distinct fill days at most 3 days apart are one episode.
   Month-blocks merge whole UTC calendar months (transitively) when one episode has fills in both; quarter-blocks
   (D-H2's "quarter-block clusters") do the same with calendar quarters. The biggest episode or block = the most fills
   (ties: the earliest). The worst month-block = the one whose removal lowers the estimate most. The top-three share
   ranks episodes by fill count. Halves split at 2023-01-01 00:00 UTC on the fill time. Week clusters are bid weeks
   that start Monday 03:30 UTC (2020-01-06 03:30 is week 0).
11. Two-way CR1 (D-H5): V = c1 V_coin + c2 V_quarter - c12 V_intersection, each c = G/(G-1); a V that is not positive
   semidefinite has its negative eigenvalues set to 0 (Cameron, Gelbach and Miller 2011), flagged psd_fixed. A
   coefficient whose own two-way variance V[j, j] is not positive uses the larger of its two one-way CR1 variances
   instead (the convention of scalp_stats.cluster2_se), flagged oneway_fallback: zeroing its eigenvalue would give an
   SE of 0 (t = +-inf, p = 0, an interval of zero width), e.g. for a mean. df = min(G1, G2) - 1 in both cases.
12. Ibragimov-Müller: the coefficient is estimated separately in each group (fill-year); groups where it is not
   identified are dropped and listed; Student t at q - 1 df on the q estimates.
13. Kaplan-Meier: right-censored product-limit; at tied times events precede censorings. The restricted mean is the
   exact integral of the step function to the horizon (365 days); its variance is the standard Klein-Moeschberger
   formula; S(t) variance by Greenwood. The median is the first time with S <= 0.5 (NaN if never).
14. phi = Pearson chi2 / (Y - 1) of yearly fill counts against one binomial rate. The sheet's interval is the Wilson
   interval with its half-width times sqrt(max(phi, 1)) (an interval is never narrowed), clipped to [0, 1].
15. Stationary bootstrap (Politis-Romano 1994): bb_stats.sb_indices (circular), blocks in months, strategy and
   benchmark resampled on the same months; percentile intervals (the basic interval is returned beside it).
16. Episode-cluster bootstrap: whole clusters resampled with replacement (multinomial counts), percentile interval.
   D5: per half, the ratio sum(realized)/sum(predicted) with a 90% interval; calibrated if both halves' intervals
   overlap [0.67, 1.5].
17. K3: a false PASS is p_decide < level in a null replication (the gates are not simulated); a NO EDGE miss is the
   98.33% bound below the truth (H4: any method's simultaneous bound below its truth); binomial intervals are
   Clopper-Pearson 95%; a test passes K3 if, in every scenario, every level's upper end is at most 1.5 x nominal.
   The simulation-calibrated p uses the studentized statistic (t for H1 and H2R; T = max_j t_j for H4) and the
   worst scenario (the largest tail share); an undefined statistic (NaN) has an undefined calibrated p. The
   calibrated bound is theta_hat - q_a(pivot) SE with the pivot (theta_hat - truth)/SE (H4: the minimum over
   methods), worst scenario = the smallest quantile. It only ever widens: §10.2 says the NO EDGE bound "is widened if
   K3 requires", so the bound used after a K3 failure is max(nominal bound, calibrated bound), per method for H4 and
   then the largest over methods (a K3 failure on the false-PASS side, with a nominal bound that over-covers, leaves
   the bound as it was). The null means are stored too, so a mean-based rule can be substituted. D11's null
   distribution is the sum of H1's per-fill values in each null replication.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import math
import multiprocessing as mp
import os
import pickle
import sys
import time
import warnings
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026.scalp_stats import holm, drop_worst  # noqa: E402
from analysis_2026.bb_stats import bh, sb_indices  # noqa: E402

# ============================================================================ constants (prereg §10.2-§10.5)

ALPHA = 0.05
N_FAMILY = 3                                    # H1 FLIP, H2R RESTING, H4 LEVELS
ALPHA_B = ALPHA / N_FAMILY                      # 0.016667: the Bonferroni level of the family
LEVEL_NOEDGE = 1 - ALPHA_B                      # 0.98333
B_BOOT = 9999
SEED = 20261118
WEBB = np.array([-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5)])
EPISODE_GAP_DAYS = 3
HALF_SPLIT = np.datetime64("2023-01-01T00:00:00", "ns")
WEEK_ANCHOR = np.datetime64("2020-01-06T03:30:00", "ns")       # the first Monday placement
H4_METHODS = ("M4", "M5b", "M6", "M7")
FAMILY = ("H1", "H2R", "H4")
REPORT_ORDER = ("H2R", "H1", "H4")                              # §11: H2R, then H1, then H4
TBILL = 0.0421                                  # 3-month T-bill, 2026-11-02 (§4)
C_RH = 0.0095                                   # Robinhood per side (§9)
F_P1 = 2.26                                     # P1 fills per rung-year (§10.3)
R_RES_GOLD = 0.0335                             # Gold sweep (§9)
KM_HORIZON = 365.0
K3_LEVELS = (ALPHA / 3, ALPHA / 2, ALPHA)       # 1.67%, 2.5%, 5%
K3_FACTOR = 1.5
D5_BAND = (0.67, 1.5)
_THREAD_VARS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


def e_h1(tbill: float = TBILL, r_res: float = 0.0, f: float = F_P1, c: float = C_RH) -> float:
    """E_H1 = c_rt + (T-bill - r_res)/f with c_rt = 1 - (1 - c)/(1 + c) (§10.3): 0.03745 at the defaults,
    0.02263 with r_res = 3.35%."""
    return (1.0 - (1.0 - c) / (1.0 + c)) + (tbill - r_res) / f


E = {"H1": 0.0375, "H2R": 0.02, "H4": 0.01}                   # as printed in §10.3
E_SENS = {"H1_gold": 0.0226}                                   # r_res = 3.35% (sensitivity row)


# ============================================================================ small helpers

def _q(x, prob):
    """Order-statistic quantile with the (B + 1) * prob convention (method 'weibull'). NaN entries are ignored; when
    infinite entries make the interpolation inf - inf the bracketing order statistic is returned."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return np.nan
    with np.errstate(invalid="ignore"):
        q = np.quantile(x, prob, method="weibull")
    if np.isnan(q):
        s = np.sort(x)
        q = s[int(np.clip(np.floor((len(s) + 1) * prob - 1), 0, len(s) - 1))]
    return float(q)


def _rng(seed):
    return seed if isinstance(seed, np.random.Generator) else np.random.default_rng(seed)


def _codes(x):
    """Integer codes 0..G-1 in order of first appearance and the unique labels; missing labels get -1. A 2-D input
    (e.g. (coin, week) pairs) is coded by row."""
    if isinstance(x, (pd.Series, pd.Index)):
        x = x.to_numpy()
    arr = np.asarray(x)
    if arr.ndim > 1:
        obj = np.empty(arr.shape[0], dtype=object)
        obj[:] = [tuple(r) for r in arr.tolist()]
        arr = obj
    codes, uniq = pd.factorize(arr)
    return codes.astype(np.int64), np.asarray(uniq)


def _f(x):
    """Plain float (NaN for None)."""
    return float("nan") if x is None else float(x)


def _tsf(t, df):
    """One-sided upper-tail Student-t p-value; NaN when df <= 0 or t is NaN."""
    if not (np.isfinite(df) and df > 0) or np.isnan(t):
        return np.nan
    return float(stats.t.sf(t, df))


def _tppf(p, df):
    if not (np.isfinite(df) and df > 0):
        return np.nan
    return float(stats.t.ppf(p, df))


def clopper_pearson(k: int, n: int, level: float = 0.95):
    """Exact (Clopper-Pearson) two-sided binomial interval for k successes in n."""
    if n <= 0:
        return (np.nan, np.nan)
    a = 1 - level
    lo = 0.0 if k <= 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k >= n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return (lo, hi)


# ============================================================================ time keys, episodes, month-blocks

def _utc_ns(t) -> np.ndarray:
    """Timestamps as naive-UTC datetime64[ns] (tz-aware input is converted; naive input is taken as UTC)."""
    if isinstance(t, np.ndarray) and np.issubdtype(t.dtype, np.datetime64):
        return t.astype("datetime64[ns]")
    s = t if isinstance(t, pd.Series) else pd.Series(t)
    s = pd.to_datetime(s, utc=True)
    return s.dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")


def fill_days(t) -> np.ndarray:
    """UTC calendar day of each fill (datetime64[D])."""
    return _utc_ns(t).astype("datetime64[D]")


def _months_since_1970(tt) -> np.ndarray:
    return tt.astype("datetime64[M]").astype(np.int64)


def month_key(t) -> np.ndarray:
    """Calendar-month label YYYYMM (UTC)."""
    m = _months_since_1970(_utc_ns(t))
    return (m // 12 + 1970) * 100 + m % 12 + 1


def quarter_key(t) -> np.ndarray:
    """Calendar-quarter label YYYYQ (UTC)."""
    m = _months_since_1970(_utc_ns(t))
    return (m // 12 + 1970) * 10 + (m % 12) // 3 + 1


def year_key(t) -> np.ndarray:
    return _months_since_1970(_utc_ns(t)) // 12 + 1970


def week_key(t, anchor=WEEK_ANCHOR) -> np.ndarray:
    """Bid-week index: weeks start Monday 03:30 UTC (the placement time, §6.1); 2020-01-06 03:30 UTC is week 0."""
    d = (_utc_ns(t) - anchor).astype(np.int64)
    return np.floor_divide(d, 7 * 86400 * 10 ** 9)


def half_key(t, split=HALF_SPLIT) -> np.ndarray:
    """0 for fills before 2023-01-01 00:00 UTC (2020-01..2022-12), 1 from then on (2023-01..)."""
    return (_utc_ns(t) >= split).astype(np.int64)


def episodes(t, gap_days: int = EPISODE_GAP_DAYS):
    """Event episodes (§10.2): runs of distinct UTC fill days at most `gap_days` apart. Returns (ids, table): ids are
    0.. in time order, one per fill; the table has episode, start, end, n_days, n_fills, months (YYYYMM tuple)."""
    tt = _utc_ns(t)
    cols = ["episode", "start", "end", "n_days", "n_fills", "months"]
    if len(tt) == 0:
        return np.zeros(0, np.int64), pd.DataFrame(columns=cols)
    if np.isnat(tt).any():
        raise ValueError("episodes: missing fill times")
    d = tt.astype("datetime64[D]")
    u = np.unique(d)
    new = np.r_[True, np.diff(u).astype(np.int64) > gap_days]
    ep_u = np.cumsum(new) - 1
    ids = ep_u[np.searchsorted(u, d)].astype(np.int64)
    mk = month_key(tt)
    rows = []
    for e in range(int(ep_u[-1]) + 1):
        sel = ids == e
        de = d[sel]
        rows.append((e, de.min(), de.max(), len(np.unique(de)), int(sel.sum()), tuple(sorted(set(mk[sel].tolist())))))
    return ids, pd.DataFrame(rows, columns=cols)


def _period_label(p: int, period: str) -> str:
    if period == "M":
        return f"{p // 12 + 1970}-{p % 12 + 1:02d}"
    if period == "Q":
        return f"{p // 4 + 1970}Q{p % 4 + 1}"
    return f"{p + 1970}"


def period_blocks(t, period: str = "M", gap_days: int = EPISODE_GAP_DAYS):
    """Calendar periods of the fills ('M' months, 'Q' quarters, 'Y' years, UTC), merged (transitively) into blocks
    when one episode has fills in both. Returns (ids, table): ids 0.. in time order, one per fill; the table has
    block, label (e.g. '2022-01+2022-02'), periods, n_fills."""
    tt = _utc_ns(t)
    cols = ["block", "label", "periods", "n_fills"]
    if len(tt) == 0:
        return np.zeros(0, np.int64), pd.DataFrame(columns=cols)
    ep, _ = episodes(tt, gap_days)
    m = _months_since_1970(tt)
    per = {"M": m, "Q": m // 3, "Y": m // 12}[period]
    up = np.unique(per)
    parent = {int(p): int(p) for p in up}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    order = np.argsort(ep, kind="stable")
    ep_s, per_s = ep[order], per[order]
    starts = np.r_[0, np.where(np.diff(ep_s) != 0)[0] + 1, len(ep_s)]
    for a, b in zip(starts[:-1], starts[1:]):
        ps = np.unique(per_s[a:b])
        for x, y in zip(ps[:-1], ps[1:]):
            rx, ry = find(int(x)), find(int(y))
            if rx != ry:
                parent[max(rx, ry)] = min(rx, ry)
    root = np.array([find(int(p)) for p in up])
    roots = np.unique(root)                      # sorted: block order = time order of the first period
    bid_of_period = dict(zip(up.tolist(), np.searchsorted(roots, root).tolist()))
    ids = np.array([bid_of_period[int(p)] for p in per], dtype=np.int64)
    rows = []
    for b in range(len(roots)):
        ps = up[np.searchsorted(roots, root) == b]
        rows.append((b, "+".join(_period_label(int(p), period) for p in ps), tuple(int(p) for p in ps),
                     int((ids == b).sum())))
    return ids, pd.DataFrame(rows, columns=cols)


def month_blocks(t, gap_days: int = EPISODE_GAP_DAYS):
    """The primary clusters (§10.2): calendar months of the fill merged into month-blocks when an episode spans two."""
    return period_blocks(t, "M", gap_days)


def quarter_blocks(t, gap_days: int = EPISODE_GAP_DAYS):
    """D-H2's quarter-block clusters: calendar quarters merged when an episode spans two."""
    return period_blocks(t, "Q", gap_days)


def gstar(sizes) -> float:
    """Effective number of clusters at full within-cluster correlation, G* = (sum n_g^2)^2 / sum n_g^4 (§10.2;
    Carter, Schnepel and Steigerwald 2017 at rho = 1), over clusters with n_g > 0."""
    n = np.asarray(sizes, float)
    n = n[np.isfinite(n) & (n > 0)]
    if len(n) == 0:
        return np.nan
    return float((n ** 2).sum() ** 2 / (n ** 4).sum())


def eff_clusters(sizes) -> float:
    """The zero-correlation effective number (sum n)^2 / sum n^2 = 1 / sum w^2 (the draft's measure; reported)."""
    n = np.asarray(sizes, float)
    n = n[np.isfinite(n) & (n > 0)]
    if len(n) == 0:
        return np.nan
    return float(n.sum() ** 2 / (n ** 2).sum())


def gstar_labels(labels) -> float:
    c, _ = _codes(labels)
    c = c[c >= 0]
    return gstar(np.bincount(c)) if len(c) else np.nan


# ============================================================================ OLS with one absorbed fixed effect
# A fit is a dict built by _prep. Model: y = alpha_fe + X theta + u (WLS with weights w), clusters g. Rows with
# missing values, non-positive weights or missing labels are dropped, then fixed-effect groups with one row.
# Everything is in the transformed space z = sqrt(w) (x - weighted fe-group mean of x).

def _prep(y, X=None, clusters=None, fe=None, weights=None):
    y = np.asarray(y, float).ravel()
    n0 = len(y)
    if X is None:
        X = np.ones((n0, 1))
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    if X.shape[0] != n0:
        raise ValueError("X and y have different lengths")
    w = np.ones(n0) if weights is None else np.asarray(weights, float).ravel()
    cl, cl_u = _codes(np.arange(n0) if clusters is None else clusters)
    ok = np.isfinite(y) & np.isfinite(X).all(1) & np.isfinite(w) & (w > 0) & (cl >= 0)
    if fe is not None:
        fc0, _ = _codes(fe)
        ok &= fc0 >= 0
    idx = np.where(ok)[0]
    fc = None
    if fe is not None:
        fc = fc0[idx]
        keep = np.bincount(fc)[fc] > 1                     # singletons carry no information under the FE
        idx = idx[keep]
        fc, _ = _codes(fc[keep])
    if len(idx) == 0:
        return None
    y, X, w, cl = y[idx], X[idx], w[idx], cl[idx]
    clc, clu_local = _codes(cl)
    G = len(clu_local)
    sw = np.sqrt(w)
    if fc is not None:
        Sw = np.bincount(fc, weights=w)

        def within(v):
            return sw * (v - (np.bincount(fc, weights=w * v) / Sw)[fc])
    else:
        Sw = None

        def within(v):
            return sw * v
    k = X.shape[1]
    Z = np.column_stack([within(X[:, a]) for a in range(k)])
    yt = within(y)
    Q = Z.T @ Z
    ident = bool(np.all(np.isfinite(Q)) and np.linalg.matrix_rank(Q) == k and np.all(np.diag(Q) > 0))
    if ident:
        Qinv = np.linalg.inv(Q)
        Qinv = (Qinv + Qinv.T) / 2
        theta = Qinv @ (Z.T @ yt)
        e = yt - Z @ theta
    else:
        Qinv = np.full((k, k), np.nan)
        theta = np.full(k, np.nan)
        e = np.full(len(y), np.nan)
    R = np.empty((G, k, k))
    for a in range(k):
        for b in range(a, k):
            R[:, a, b] = R[:, b, a] = np.bincount(clc, weights=Z[:, a] * Z[:, b], minlength=G)
    strad = None
    if fc is not None:
        nfe = int(fc.max()) + 1
        pairs = np.unique(fc * G + clc)
        strad = np.bincount(pairs // G, minlength=nfe) > 1  # FE groups whose rows sit in more than one cluster
    return dict(idx=idx, n=len(y), k=k, G=G, cl=clc, labels=cl_u[clu_local], sizes=np.bincount(clc, minlength=G),
                w=w, sw=sw, fe=fc, Sw=Sw, strad=strad, Z=Z, yt=yt, Q=Q, Qinv=Qinv, theta=theta, e=e, R=R,
                ident=ident)


def _scores(f, e) -> np.ndarray:
    """Cluster score sums h_g = Z_g' e_g, shape (G, k)."""
    return np.column_stack([np.bincount(f["cl"], weights=f["Z"][:, a] * e, minlength=f["G"]) for a in range(f["k"])])


def _kmat(f, e):
    """Correction for FE groups that straddle clusters: K[g, h] = sum_d A[d, g] c[d, h] / S_d with
    A[d, g] = sum_{d and g} z sqrt(w), c[d, h] = sum_{d and h} sqrt(w) e, S_d = sum_d w. The bootstrap score of
    cluster g is then w_g h_g - sum_h K[g, h] w_h - R_g delta*. None when no group straddles."""
    if f["fe"] is None or not f["strad"].any():
        return None
    rows = np.where(f["strad"][f["fe"]])[0]
    dc, du = _codes(f["fe"][rows])
    nd, G, k = len(du), f["G"], f["k"]
    cell = dc * G + f["cl"][rows]
    sw = f["sw"][rows]
    A = np.column_stack([np.bincount(cell, weights=f["Z"][rows, a] * sw, minlength=nd * G) for a in range(k)])
    A = A.reshape(nd, G, k)
    c = np.bincount(cell, weights=sw * e[rows], minlength=nd * G).reshape(nd, G)
    return np.einsum("dgk,dh->ghk", A / f["Sw"][du][:, None, None], c)


def _restricted_resid(f, j: int, theta0: float) -> np.ndarray:
    """Residuals of the model with theta_j = theta0 imposed (FE and the other coefficients re-estimated)."""
    yr = f["yt"] - theta0 * f["Z"][:, j]
    if f["k"] == 1:
        return yr
    Zo = np.delete(f["Z"], j, axis=1)
    coef = np.linalg.lstsq(Zo, yr, rcond=None)[0]
    return yr - Zo @ coef


def _cr1_se(f, j: int) -> float:
    G = f["G"]
    eta = _scores(f, f["e"]) @ f["Qinv"][j]
    return float(math.sqrt(G / (G - 1) * float(eta @ eta)))


def _boot_t(f, j: int, W: np.ndarray, e: np.ndarray, chunk: int = 2000) -> np.ndarray:
    """Wild cluster bootstrap-t draws for coefficient j: multipliers W (B, G) on residuals e (restricted: t* =
    (theta*_j - theta0)/se*; unrestricted: t* = (theta*_j - theta_hat_j)/se*). Exact re-estimation, CR1 (G/(G-1))."""
    G = f["G"]
    cG = G / (G - 1)
    H = _scores(f, e)
    a = f["Qinv"][j]
    eta = H @ a                                            # (G,)
    rho = f["R"] @ a                                       # (G, k)
    QH = H @ f["Qinv"]                                     # (G, k): row g = Qinv h_g
    K = _kmat(f, e)
    kap = None if K is None else K @ a                     # (G, G)
    B = W.shape[0]
    out = np.empty(B)
    for s in range(0, B, chunk):
        Wc = W[s:s + chunk]
        dstar = Wc @ QH                                    # (b, k): theta* - theta_base
        sc = Wc * eta - dstar @ rho.T                      # (b, G): bootstrap cluster scores (projected on a)
        if kap is not None:
            sc -= Wc @ kap.T
        se = np.sqrt(cG * np.einsum("bg,bg->b", sc, sc))
        with np.errstate(divide="ignore", invalid="ignore"):
            out[s:s + chunk] = dstar[:, j] / se
    return out


def webb_weights(B: int, G: int, rng) -> np.ndarray:
    """B x G Webb six-point multipliers (+-sqrt(1/2), +-1, +-sqrt(3/2), each 1/6; Webb 2023)."""
    return WEBB[_rng(rng).integers(0, 6, size=(B, G))]


def wild_t(y, X=None, j: int = 0, clusters=None, fe=None, weights=None, W=None, B: int = B_BOOT, seed=SEED,
           restricted: bool = True, null: float = 0.0):
    """Wild cluster bootstrap-t draws for coefficient j (restricted: null imposed; else unrestricted, recentred).
    Returns (t_hat, tstar, fit)."""
    f = _prep(y, X, clusters, fe, weights)
    if f is None or f["G"] < 2 or not f["ident"]:
        return np.nan, np.full(B if W is None else W.shape[0], np.nan), f
    if W is None:
        W = webb_weights(B, f["G"], seed)
    se = _cr1_se(f, j)
    t = (f["theta"][j] - (null if restricted else 0.0)) / se if se > 0 else np.nan
    e = _restricted_resid(f, j, null) if restricted else f["e"]
    return t, _boot_t(f, j, W, e), f


def ols_fe(y, X=None, fe=None, clusters=None, weights=None) -> dict:
    """OLS (WLS with weights) with one absorbed fixed effect and one-way CR1 (G/(G-1)) variance. clusters=None gives
    each row its own cluster (heteroskedasticity-robust). Returns coef, se, V, t, n, G, gstar, ident."""
    f = _prep(y, X, clusters, fe, weights)
    if f is None:
        return dict(coef=None, se=None, V=None, t=None, n=0, G=0, gstar=np.nan, ident=False)
    k, G = f["k"], f["G"]
    if not f["ident"] or G < 2:
        nan = np.full(k, np.nan)
        return dict(coef=f["theta"], se=nan, V=np.full((k, k), np.nan), t=nan, n=f["n"], G=G,
                    gstar=gstar(f["sizes"]), ident=f["ident"])
    H = _scores(f, f["e"])
    V = G / (G - 1) * f["Qinv"] @ (H.T @ H) @ f["Qinv"]
    se = np.sqrt(np.diag(V))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = f["theta"] / se
    return dict(coef=f["theta"], se=se, V=V, t=t, n=f["n"], G=G, gstar=gstar(f["sizes"]), ident=True)


def cr1_mean(y, clusters, weights=None) -> dict:
    """Mean (weighted mean) with its one-way CR1 SE (G/(G-1)). Returns mean, se, t, n, G, gstar."""
    r = ols_fe(y, None, None, clusters, weights)
    if r["coef"] is None:
        return dict(mean=np.nan, se=np.nan, t=np.nan, n=0, G=0, gstar=np.nan)
    return dict(mean=float(r["coef"][0]), se=float(r["se"][0]), t=float(r["t"][0]), n=r["n"], G=r["G"],
                gstar=r["gstar"])


# ============================================================================ the decisive p-value and bounds

def _empty_row(unit, E_, level, null, B):
    nan = np.nan
    return dict(n=0, G=0, gstar=nan, eff_n=nan, unit=unit, estimate=nan, se=nan, t=nan, df=nan, p_wcr=nan,
                p_gstar=nan, p_decide=nan, ub_boot=nan, ub_t=nan, ub=nan, level=level, ci95=(nan, nan),
                ci95_t=(nan, nan), ci95_boot=(nan, nan), mde=nan, alpha_b=ALPHA_B, E=_f(E_), noedge=False,
                harms=False, B=B, null=null)


def test_coef(y, X=None, j: int = 0, clusters=None, fe=None, weights=None, E_=None, null: float = 0.0,
              B: int = B_BOOT, seed=SEED, level: float = LEVEL_NOEDGE, alpha_b: float = ALPHA_B,
              unit: str = "month-block", W=None, return_draws: bool = False) -> dict:
    """§10.2 for coefficient j of y = alpha_fe + X theta + u (X=None: the mean). Returns n, G, gstar, eff_n, unit,
    estimate, se (CR1), t, df (= G* - 1), p_wcr, p_gstar, p_decide = max(p_wcr, p_gstar), ub_boot (unrestricted wild
    bootstrap-t bound at `level`), ub_t (estimate + t_{level, G*-1} se), ub = max of the two, ci95 (union of the two
    95% intervals; see coding choice 4), ci95_t, ci95_boot, mde, E, noedge (ub < E), harms (ub < 0)."""
    out = _empty_row(unit, E_, level, null, B)
    f = _prep(y, X, clusters, fe, weights)
    if f is None:
        return out
    gs = gstar(f["sizes"])
    out.update(n=int(f["n"]), G=int(f["G"]), gstar=gs, eff_n=eff_clusters(f["sizes"]), df=gs - 1)
    if f["ident"]:
        out["estimate"] = float(f["theta"][j])          # reported also with one cluster (coding choice 2)
    if f["G"] < 2 or not f["ident"]:
        return out
    est = float(f["theta"][j])
    se = _cr1_se(f, j)
    if se > 0:
        t = (est - null) / se
    else:
        t = np.inf if est > null else (-np.inf if est < null else np.nan)
    df = gs - 1
    p_g = _tsf(t, df)
    if W is None:
        W = webb_weights(B, f["G"], seed)
    tr = _boot_t(f, j, W, _restricted_resid(f, j, null))
    if np.isnan(t):
        p_w = np.nan
    else:
        tie = t - 1e-10 * max(1.0, abs(t)) if np.isfinite(t) else t     # ties count as exceedances (coding choice 1)
        p_w = float((1 + np.sum((tr >= tie) | np.isnan(tr))) / (len(tr) + 1))
    tu = _boot_t(f, j, W, f["e"])
    a = 1 - level
    lo_t = np.where(np.isnan(tu), -np.inf, tu)              # undefined draws at the conservative end
    hi_t = np.where(np.isnan(tu), np.inf, tu)
    ub_boot = est - _q(lo_t, a) * se
    ub_t = est + _tppf(level, df) * se
    ub = max(ub_boot, ub_t) if np.isfinite(ub_t) else np.nan
    q975 = _tppf(0.975, df)
    ci_t = (est - q975 * se, est + q975 * se)
    ci_b = (est - _q(hi_t, 0.975) * se, est - _q(lo_t, 0.025) * se)
    ci = (min(ci_t[0], ci_b[0]), max(ci_t[1], ci_b[1])) if np.isfinite(q975) else (np.nan, np.nan)
    p_dec = max(p_w, p_g) if not (np.isnan(p_w) or np.isnan(p_g)) else np.nan
    out.update(estimate=est, se=se, t=float(t), p_wcr=p_w, p_gstar=p_g, p_decide=p_dec, ub_boot=float(ub_boot),
               ub_t=float(ub_t), ub=float(ub), ci95=ci, ci95_t=ci_t, ci95_boot=ci_b, alpha_b=alpha_b,
               mde=mde(se, gs, alpha_b))
    if E_ is not None and np.isfinite(ub):
        out.update(noedge=bool(ub < E_), harms=bool(ub < 0))
    if return_draws:
        out.update(tstar_restricted=tr, tstar_unrestricted=tu)
    return out


def test_mean(y, clusters, E_=None, weights=None, null: float = 0.0, B: int = B_BOOT, seed=SEED,
              level: float = LEVEL_NOEDGE, alpha_b: float = ALPHA_B, unit: str = "month-block", W=None,
              return_draws: bool = False) -> dict:
    """§10.2 for a per-fill mean (H1: Delta_f, H2R: a_f; weights= for the size-weighted sensitivity). See test_coef."""
    return test_coef(y, None, 0, clusters, None, weights, E_, null, B, seed, level, alpha_b, unit, W, return_draws)


def describe(y, clusters, X=None, j: int = 0, fe=None, weights=None, B: int = B_BOOT, seed=SEED,
             alpha_b: float = ALPHA_B, unit: str = "month-block") -> dict:
    """A pre-registered descriptive estimand (§10.4): estimate, 95% interval (coding choice 4), G, G*, MDE and no
    p-value (p_* keys removed)."""
    r = test_coef(y, X, j, clusters, fe, weights, None, 0.0, B, seed, 0.975, alpha_b, unit)
    for k in ("p_wcr", "p_gstar", "p_decide", "t", "noedge", "harms", "ub", "ub_t", "ub_boot", "level", "E", "null"):
        r.pop(k, None)
    return r


def mde(se, gstar_: float, alpha: float = ALPHA_B, power: float = 0.80) -> float:
    """Minimum detectable effect (t_{1-alpha, G*-1} + t_{power, G*-1}) SE."""
    df = gstar_ - 1
    if not (np.isfinite(df) and df > 0) or not np.isfinite(se):
        return np.nan
    return float((stats.t.ppf(1 - alpha, df) + stats.t.ppf(power, df)) * se)


# ============================================================================ H4: the stacked regression

def romano_wolf(t, tstar) -> np.ndarray:
    """Romano-Wolf step-down adjusted p-values for one-sided max-t (Romano and Wolf 2005; the 2016 algorithm):
    order the observed t descending; at step r, p_r = (1 + #{b : max_{s >= r} t*_{b,(s)} >= t_(r)}) / (B + 1);
    adjusted p = running maximum. NaN statistics are left out (NaN p); NaN draws count as exceedances."""
    t = np.asarray(t, float)
    tstar = np.asarray(tstar, float)
    p = np.full(len(t), np.nan)
    idx = np.where(np.isfinite(t))[0]
    if len(idx) == 0:
        return p
    order = idx[np.argsort(-t[idx], kind="stable")]
    Ts = np.where(np.isnan(tstar[:, order]), np.inf, tstar[:, order])
    M = np.maximum.accumulate(Ts[:, ::-1], axis=1)[:, ::-1]
    raw = (1 + (M >= t[order][None, :]).sum(0)) / (Ts.shape[0] + 1)
    p[order] = np.minimum(np.maximum.accumulate(raw), 1.0)
    return p


_H4_COLS = dict(y="y", real="real", depth="depth", depth_real="depth_real", cw="cw", cluster="cluster",
                time="time", w="w")
_H4_REQUIRED = ("y", "real", "depth", "cw")


def _col(frame, name):
    if isinstance(frame, pd.DataFrame):
        return frame[name].to_numpy() if name in frame.columns else None
    return np.asarray(frame[name]) if name in frame else None


def _nrows(frame) -> int:
    if isinstance(frame, pd.DataFrame):
        return len(frame)
    return max([len(np.atleast_1d(np.asarray(v))) for v in frame.values()] or [0])


def _h4_arrays(frame, cols):
    """One method's columns. y, real, depth and cw are required (coding choice 6): the coin-week fixed effects are part
    of the pre-registered model (§10.3), so a frame without them is refused, never fitted without them. A frame with
    no rows may omit them."""
    g = {k: _col(frame, c) for k, c in cols.items()}
    miss = [cols[k] for k in _H4_REQUIRED if g[k] is None]
    if miss:
        if _nrows(frame) > 0:
            raise ValueError(f"H4 frame lacks required column(s) {miss}: y (Delta_f), real, depth and cw (the "
                             "coin-week id of the fixed effects, §10.3) are required; rename them or pass cols=")
        for k in _H4_REQUIRED:
            if g[k] is None:
                g[k] = np.zeros(0)
    if g["depth_real"] is not None:
        g["depth"] = np.asarray(g["depth"], float) - np.asarray(g["depth_real"], float)
    return g


def _h4_partition(arrs: dict) -> dict:
    """H4's one month-block partition (coding choice 6): the methods' `cluster` labels when every non-empty method has
    them, else month_blocks() on the union of all methods' stacked fill times. {name: labels aligned with its rows}."""
    names = list(arrs)
    live = [nm for nm in names if len(arrs[nm]["y"]) > 0]
    has = [arrs[nm]["cluster"] is not None for nm in live]
    if all(has):
        return {nm: (np.asarray(arrs[nm]["cluster"]) if arrs[nm]["cluster"] is not None else np.zeros(0, np.int64))
                for nm in names}
    if any(has):
        raise ValueError("H4: give a `cluster` column (one partition shared by the methods) for every method or for "
                         "none; with none, every method needs `time`, and month_blocks() runs on the union of their "
                         "fills")
    tms = {}
    for nm in names:
        if arrs[nm]["time"] is None:
            if len(arrs[nm]["y"]):
                raise ValueError(f"H4: method {nm!r} has neither a `cluster` nor a `time` column")
            tms[nm] = np.zeros(0, "datetime64[ns]")
        else:
            tms[nm] = _utc_ns(arrs[nm]["time"])
    ids = month_blocks(np.concatenate([tms[nm] for nm in names]) if names else np.zeros(0, "datetime64[ns]"))[0]
    out, pos = {}, 0
    for nm in names:
        out[nm] = ids[pos:pos + len(tms[nm])]
        pos += len(tms[nm])
    return out


def h4_clusters(methods: dict, cols=None) -> dict:
    """H4's month-block partition exactly as test_h4 builds it: {name: cluster labels aligned with that method's
    frame} (the frames' `cluster` columns, or month-blocks of the union of all methods' fill times). Pass a method's
    labels as clusters= to h4_fit / h4_drop_worst_block (test_h4 returns the same as out["clusters"])."""
    c = dict(_H4_COLS, **(cols or {}))
    return _h4_partition({nm: _h4_arrays(methods[nm], c) for nm in methods})


def _gate_clusters(g, clusters, who: str) -> np.ndarray:
    cl = g["cluster"] if clusters is None else clusters
    if cl is None:
        raise ValueError(f"{who}: pass clusters= (test_h4(...)['clusters'][method] or h4_clusters(methods)[method]) or "
                         "give the frame a `cluster` column; month-blocks are not rebuilt from one method's fills, "
                         "which would be a different partition from test_h4's (the union of all methods' fills)")
    cl = np.asarray(cl)
    if len(cl) != len(g["y"]):
        raise ValueError(f"{who}: {len(cl)} cluster labels for {len(g['y'])} rows")
    return cl


def h4_fit(frame, mask=None, cols=None, clusters=None) -> dict:
    """One method's stacked regression Delta = alpha_cw + b real + c depth + e (CR1, month-block clusters), for the
    gates (halves, without the worst month-block, under F3). clusters: labels aligned with the frame's rows from
    test_h4's partition (out["clusters"][method] or h4_clusters(methods)[method]); else the frame's `cluster` column
    (ValueError if neither). Returns b, se, t, c, se_c, n, G, gstar (b and c also when G < 2)."""
    c = dict(_H4_COLS, **(cols or {}))
    g = _h4_arrays(frame, c)
    cl = _gate_clusters(g, clusters, "h4_fit")
    y = np.asarray(g["y"], float)
    X = np.column_stack([np.asarray(g["real"], float), np.asarray(g["depth"], float)])
    m = np.ones(len(y), bool) if mask is None else np.asarray(mask, bool)
    w = None if g["w"] is None else np.asarray(g["w"], float)[m]
    r = ols_fe(y[m], X[m], np.asarray(g["cw"])[m], cl[m], w)
    if r["coef"] is None or not r["ident"]:
        return dict(b=np.nan, se=np.nan, t=np.nan, c=np.nan, se_c=np.nan, n=r["n"], G=r["G"], gstar=r["gstar"])
    return dict(b=float(r["coef"][0]), se=float(r["se"][0]), t=float(r["t"][0]), c=float(r["coef"][1]),
                se_c=float(r["se"][1]), n=r["n"], G=r["G"], gstar=r["gstar"])


def h4_drop_worst_block(frame, cols=None, clusters=None):
    """b of one method after removing the month-block whose removal lowers it most, on test_h4's partition (clusters=
    or a `cluster` column, as h4_fit). Returns (b_after, block)."""
    c = dict(_H4_COLS, **(cols or {}))
    g = _h4_arrays(frame, c)
    cl = _gate_clusters(g, clusters, "h4_drop_worst_block")
    best, which = np.inf, None
    for blk in pd.unique(cl):
        b = h4_fit(frame, mask=cl != blk, cols=cols, clusters=cl)["b"]
        if np.isfinite(b) and b < best:
            best, which = b, blk
    return (best if which is not None else np.nan), which


def test_h4(methods: dict, B: int = B_BOOT, seed=SEED, level: float = LEVEL_NOEDGE, E_: float = E["H4"],
            alpha_b: float = ALPHA_B, n_bonf=None, cols=None, unit: str = "month-block") -> dict:
    """H4 LEVELS (§10.3). methods: {name: frame} with columns y (Delta_f), real (1 = the chart level's own fill, 0 = a
    placebo's), depth (delta_f - delta_real,cw, or delta_f; or give depth_real too), cw (coin-week id; y, real, depth
    and cw are required), cluster (month-block label from ONE partition shared by the methods; else `time` in every
    frame and month_blocks() is run on the union), optional w (size weights). n_bonf defaults to 4 = len(H4_METHODS)
    whatever is passed (coding choice 6). Returns {"methods": DataFrame (per method: n, n_cw, G, gstar, b, se, t, c,
    p_t (one-sided t(G*-1)), p_rw (Romano-Wolf step-down adjusted: the p §13's sheet rule names), p_bonf (n_bonf x
    p_t, capped), p_method (max of the two: the §10.2 max rule per method, a conservative companion), ub_boot,
    ub_bonf, ub, ci95_lo, ci95_hi, mde, mde_bonf), "T", "argmax", "estimate", "se", "gstar", "G", "p_wcr", "p_gstar",
    "p_decide", "ub" (NaN unless all n_bonf methods have a bound), "unbounded" (methods without one), "E", "noedge",
    "harms", "mde", "mde_bonf", "ci95", "tstar", "clusters" ({name: the month-block labels used, aligned with the
    frame's rows}: pass them to h4_fit / h4_drop_worst_block for the gates), ...}."""
    c = dict(_H4_COLS, **(cols or {}))
    names = list(methods)
    J = len(names)
    if n_bonf is None:
        n_bonf = len(H4_METHODS)                       # §10.3: "Bonferroni over the four methods"
        absent = [m for m in H4_METHODS if m not in methods]
        if absent:
            warnings.warn(f"test_h4: pre-registered method(s) {absent} not among {names}; the Bonferroni factor stays "
                          f"{n_bonf} (§10.3), and H4's NO EDGE bound needs a bound for each of {n_bonf} methods",
                          stacklevel=2)
    if n_bonf < J:
        raise ValueError(f"test_h4: n_bonf = {n_bonf} is below the number of methods passed ({J}); the Bonferroni "
                         "companion would be anti-conservative")
    arrs = {nm: _h4_arrays(methods[nm], c) for nm in names}
    part = _h4_partition(arrs)
    allcl = np.concatenate([np.asarray(part[nm], dtype=object) for nm in names]) if J else np.zeros(0, dtype=object)
    gcodes, gu = _codes(allcl)
    Gu = len(gu)
    pos, fits = 0, {}
    for nm in names:
        a = arrs[nm]
        k = len(a["y"])
        X = np.column_stack([np.asarray(a["real"], float), np.asarray(a["depth"], float)]) if k else np.zeros((0, 2))
        fits[nm] = _prep(a["y"], X, gcodes[pos:pos + k], a["cw"], a["w"]) if k else None
        pos += k
    rng = _rng(seed)
    W_all = webb_weights(B, Gu, rng) if Gu else np.zeros((B, 0))
    rows, tstar = [], np.full((B, J), np.nan)
    for jj, nm in enumerate(names):
        f = fits[nm]
        r = dict(method=nm, n=0, n_cw=0, G=0, gstar=np.nan, b=np.nan, se=np.nan, t=np.nan, c=np.nan, p_t=np.nan)
        if f is not None:
            r.update(n=int(f["n"]), n_cw=int(len(np.unique(f["fe"]))), G=int(f["G"]), gstar=gstar(f["sizes"]))
            if f["ident"]:                             # the estimate also with one cluster (coding choice 2)
                r.update(b=float(f["theta"][0]), c=float(f["theta"][1]))
            if f["G"] >= 2 and f["ident"]:
                se = _cr1_se(f, 0)
                b = float(f["theta"][0])
                t = b / se if se > 0 else np.nan
                r.update(se=se, t=t, p_t=_tsf(t, r["gstar"] - 1))
                Wj = W_all[:, f["labels"].astype(np.int64)]
                tstar[:, jj] = _boot_t(f, 0, Wj, f["e"])
        rows.append(r)
    tab = pd.DataFrame(rows, columns=["method", "n", "n_cw", "G", "gstar", "b", "se", "t", "c", "p_t"])
    tvec = tab["t"].to_numpy(float)
    valid = np.isfinite(tvec)
    tab["p_rw"] = romano_wolf(tvec, tstar)
    tab["p_bonf"] = np.minimum(1.0, n_bonf * tab["p_t"].to_numpy(float))
    tab["p_method"] = np.fmax(tab["p_rw"].to_numpy(float), tab["p_bonf"].to_numpy(float))
    tab.loc[~(np.isfinite(tab["p_rw"].to_numpy(float)) & np.isfinite(tab["p_bonf"].to_numpy(float))), "p_method"] = \
        np.nan
    a = 1 - level
    if valid.any():
        tv = tstar[:, valid]
        qmin = _q(np.min(np.where(np.isnan(tv), -np.inf, tv), axis=1), a)            # simultaneous lower tail
        qabs = _q(np.max(np.where(np.isnan(tv), np.inf, np.abs(tv)), axis=1), 0.95)   # simultaneous two-sided
    else:
        qmin = qabs = np.nan
    tab["ub_boot"] = tab["b"] - qmin * tab["se"]
    tab["ub_bonf"] = [b + _tppf(1 - a / n_bonf, gs - 1) * s for b, s, gs in zip(tab["b"], tab["se"], tab["gstar"])]
    tab["ub"] = np.fmax(tab["ub_boot"].to_numpy(float), tab["ub_bonf"].to_numpy(float))
    tab.loc[~np.isfinite(tab["ub_bonf"].to_numpy(float)), "ub"] = np.nan
    q2 = np.array([_tppf(1 - 0.025 / n_bonf, gs - 1) for gs in tab["gstar"]], float)
    bb_, ss_ = tab["b"].to_numpy(float), tab["se"].to_numpy(float)
    tab["ci95_lo"] = np.minimum(bb_ - qabs * ss_, bb_ - q2 * ss_)                     # union, as in test_coef
    tab["ci95_hi"] = np.maximum(bb_ + qabs * ss_, bb_ + q2 * ss_)
    tab["mde"] = [mde(s, gs, alpha_b) for s, gs in zip(tab["se"], tab["gstar"])]
    tab["mde_bonf"] = [mde(s, gs, alpha_b / n_bonf) for s, gs in zip(tab["se"], tab["gstar"])]
    # H4's NO EDGE bound speaks for every chart method (§11), so it needs a bound for each of the n_bonf methods: an
    # absent method, or one that is empty, has G < 2 or is not identified, leaves it undefined (never NO EDGE).
    ubv = tab["ub"].to_numpy(float)
    unbounded = [nm for nm, u in zip(names, ubv) if np.isnan(u)]
    if n_bonf > J:
        unbounded.append(f"{n_bonf - J} method(s) not passed")
    out = dict(methods=tab, T=np.nan, argmax=None, estimate=np.nan, se=np.nan, t=np.nan, gstar=np.nan, G=0, n=0,
               p_wcr=np.nan, p_gstar=np.nan, p_decide=np.nan, ub=np.nan, level=level, E=_f(E_), noedge=False,
               harms=False, mde=np.nan, mde_bonf=np.nan, n_bonf=n_bonf, n_methods=J, unbounded=unbounded, B=B,
               G_union=Gu, unit=unit, ci95=(np.nan, np.nan), alpha_b=alpha_b, clusters=part)
    if not valid.any():
        return out
    jm = int(np.nanargmax(tvec))
    rm = tab.iloc[jm]
    T = float(tvec[jm])
    p_w = float(rm["p_rw"])
    p_g = min(1.0, n_bonf * _tsf(T, rm["gstar"] - 1)) if np.isfinite(_tsf(T, rm["gstar"] - 1)) else np.nan
    ub = float(np.max(ubv)) if J == n_bonf else np.nan                    # NaN if any method's bound is NaN
    out.update(T=T, argmax=rm["method"], estimate=float(rm["b"]), se=float(rm["se"]), t=T, gstar=float(rm["gstar"]),
               G=int(rm["G"]), n=int(rm["n"]), p_wcr=p_w, p_gstar=p_g,
               p_decide=max(p_w, p_g) if np.isfinite(p_g) else np.nan, ub=ub, mde=float(rm["mde"]),
               mde_bonf=float(rm["mde_bonf"]), ci95=(float(rm["ci95_lo"]), float(rm["ci95_hi"])))
    if np.isfinite(ub):
        out.update(noedge=bool(ub < E_), harms=bool(ub < 0))
    out["tstar"] = tstar
    return out


# ============================================================================ multiplicity and verdicts

def holm_levels(p, alpha: float = ALPHA):
    """Holm step-down detail: for each test, the level alpha/(m - r + 1) it is compared with at its step r (ranks by
    p, ties stable; NaN = 1) and whether it is rejected (every earlier step rejected and p < level). Returns
    (levels, rejected)."""
    p = np.asarray(p, float)
    q = np.where(np.isfinite(p), p, 1.0)
    m = len(q)
    order = np.argsort(q, kind="stable")
    levels = np.empty(m)
    rej = np.zeros(m, bool)
    going = True
    for r, i in enumerate(order):
        levels[i] = alpha / (m - r)
        going = going and q[i] < levels[i]
        rej[i] = going
    return levels, rej


def _gates_ok(g) -> bool:
    if g is None:
        return False
    if isinstance(g, dict):
        return len(g) > 0 and all(_gates_ok(v) for v in g.values())
    try:
        return bool(g is True or (isinstance(g, (bool, np.bool_)) and bool(g)))
    except Exception:
        return False


def verdict(p_holm, gates_ok, ub, E_) -> str:
    """NO EDGE if the 98.33% upper bound is below E ("NO EDGE (HARMS)" when below 0); else PASS if the Holm-adjusted
    p < 0.05 and every gate holds; else INCONCLUSIVE ("the data cannot tell"). When PASS's conditions and NO EDGE's
    both hold (an effect surely above zero and surely below E, the smallest effect worth acting on), the verdict is
    NO EDGE and family_verdicts() flags pass_and_noedge so the report states both facts (prereg Addendum 1, A1.8)."""
    if ub is not None and (np.isfinite(ub) or np.isneginf(ub)) and ub < E_:
        return "NO EDGE (HARMS)" if ub < 0 else "NO EDGE"
    if p_holm is not None and np.isfinite(p_holm) and p_holm < ALPHA and _gates_ok(gates_ok):
        return "PASS"
    return "INCONCLUSIVE"


def family_verdicts(rows: dict, gates: dict | None = None, E_: dict | None = None, alpha: float = ALPHA,
                    order=REPORT_ORDER) -> pd.DataFrame:
    """Holm on the three decisive p-values (whatever their gates) and the verdicts (§10.3), in the reporting order of
    §11. rows: {test: row from test_mean / test_h4 (possibly apply_calibration'd)}; gates: {test: bool or {gate: bool}}
    (a missing test's gates count as not met); E_: thresholds (default E). Holm always runs over the three family
    tests (§10.3): a test without a row (or with None) enters with p = NaN, which Holm counts as 1, and is reported
    INCONCLUSIVE with row_given = False (a warning names it); a key outside the family raises ValueError."""
    E_ = dict(E, **(E_ or {}))
    gates = gates or {}
    extra = [t for t in rows if t not in FAMILY]
    if extra:
        raise ValueError(f"family_verdicts: {extra} are not in the Holm family {FAMILY}")
    tests = list(FAMILY)
    given = {t: rows.get(t) is not None for t in tests}
    if not all(given.values()):
        warnings.warn(f"family_verdicts: no row for {[t for t in tests if not given[t]]}; Holm still runs over the "
                      f"three family tests {tests}, with p = 1 for a missing one (§10.3)", stacklevel=2)
    p = [_f(rows[t].get("p_decide", np.nan)) if given[t] else np.nan for t in tests]
    ph = holm(p)
    lv, rj = holm_levels(p, alpha)
    out = []
    for i, t in enumerate(tests):
        r = rows[t] if given[t] else {}
        g_ok = _gates_ok(gates.get(t))
        ub = _f(r.get("ub", np.nan))
        v = verdict(ph[i], g_ok, ub, E_[t])
        ne = bool((np.isfinite(ub) or np.isneginf(ub)) and ub < E_[t])          # the rule verdict() applies
        ci = r.get("ci95", (np.nan, np.nan))
        out.append(dict(test=t, row_given=given[t], estimate=r.get("estimate", np.nan), ci95_lo=ci[0],
                        ci95_hi=ci[1], se=r.get("se", np.nan), n=r.get("n", 0), G=r.get("G", 0),
                        gstar=r.get("gstar", np.nan), unit=r.get("unit", ""), argmax=r.get("argmax"),
                        p_wcr=r.get("p_wcr", np.nan), p_gstar=r.get("p_gstar", np.nan), p_decide=p[i], p_holm=ph[i],
                        holm_level=lv[i], holm_rejected=bool(rj[i]), gates_ok=g_ok, gates_given=t in gates,
                        ub=ub, level=r.get("level", LEVEL_NOEDGE), E=E_[t], noedge=ne, harms=bool(ne and ub < 0),
                        mde=r.get("mde", np.nan), verdict=v,
                        pass_and_noedge=bool(ne and np.isfinite(ph[i]) and ph[i] < alpha and g_ok),
                        calibrated=bool(r.get("calibrated", False))))
    df = pd.DataFrame(out)
    if len(df):
        df["_o"] = [list(order).index(t) if t in order else 99 for t in df["test"]]
        df = df.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    return df


# ============================================================================ gates, single events, concentration

def drop_worst_group_mean(y, groups):
    """Mean after removing the group (month-block) whose removal lowers it most: (mean_after, group)."""
    y = np.asarray(y, float)
    g = np.asarray(groups)
    k = np.isfinite(y)
    return drop_worst(y[k], g[k])


def _ranked_groups(y, groups):
    y = np.asarray(y, float)
    g = np.asarray(groups)
    k = np.isfinite(y)
    u, cnt = np.unique(g[k], return_counts=True)
    o = np.lexsort((np.arange(len(u)), -cnt))       # most fills first; ties: smallest label (earliest id) first
    return y[k], g[k], u[o], cnt[o]


def drop_biggest_group_mean(y, groups):
    """Mean without the group with the most fills (the biggest episode; ties: the smallest label, i.e. the earliest
    episode id from episodes()). Returns (mean_after, group)."""
    yy, gg, u, _ = _ranked_groups(y, groups)
    if len(u) < 2:
        return np.nan, (u[0] if len(u) else None)
    keep = gg != u[0]
    return float(yy[keep].mean()), u[0]


def top_k_share(y, groups, k: int = 3) -> dict:
    """Concentration (S16): the share of the total sum(y) from the k largest groups by fill count, the estimate
    (mean) without them, and their labels. A total <= 0 gives a share that is negative or above 1 (reported as is)."""
    yy, gg, u, cnt = _ranked_groups(y, groups)
    top = u[:k]
    sel = np.isin(gg, top)
    tot = yy.sum()
    return dict(share=float(yy[sel].sum() / tot) if tot != 0 else np.nan, total=float(tot),
                mean_without=float(yy[~sel].mean()) if (~sel).any() else np.nan, groups=top.tolist(),
                n_top=int(sel.sum()), above_half=bool(tot != 0 and yy[sel].sum() / tot > 0.5))


# ============================================================================ two-way clustering, Ibragimov-Müller

def ols_cluster2(y, X, g1, g2) -> dict:
    """OLS with two-way CR1 clustering (Cameron, Gelbach and Miller 2011): V = c1 V1 + c2 V2 - c12 V12, c = G/(G-1)
    each, negative eigenvalues set to 0 (flag psd_fixed); a coefficient whose own two-way variance V[j, j] is not
    positive takes the larger of its two one-way CR1 variances (flag oneway_fallback[j]; coding choice 11). Student t
    at min(G1, G2) - 1 df. Returns beta, se, t, p (one-sided > 0), p2 (two-sided), ci95 (k x 2), df, G1, G2, G12, n,
    psd_fixed, oneway_fallback (k booleans), V_raw."""
    y = np.asarray(y, float).ravel()
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    c1, _ = _codes(g1)
    c2, _ = _codes(g2)
    ok = np.isfinite(y) & np.isfinite(X).all(1) & (c1 >= 0) & (c2 >= 0)
    y, X, c1, c2 = y[ok], X[ok], c1[ok], c2[ok]
    c1, _ = _codes(c1)
    c2, _ = _codes(c2)
    c12, _ = _codes(c1 * (int(c2.max()) + 1) + c2) if len(y) else (c1, None)
    k = X.shape[1]
    nan = np.full(k, np.nan)
    out = dict(beta=nan, se=nan, t=nan, p=nan, p2=nan, ci95=np.full((k, 2), np.nan), df=np.nan, G1=0, G2=0, G12=0,
               n=len(y), psd_fixed=False, oneway_fallback=np.zeros(k, bool))
    if len(y) <= k or np.linalg.matrix_rank(X) < k:
        return out
    XtXi = np.linalg.inv(X.T @ X)
    beta = XtXi @ (X.T @ y)
    e = y - X @ beta

    def meat(c):
        G = int(c.max()) + 1
        S = np.column_stack([np.bincount(c, weights=X[:, a] * e, minlength=G) for a in range(k)])
        return S.T @ S, G

    M1, G1 = meat(c1)
    M2, G2 = meat(c2)
    M12, G12 = meat(c12)
    out.update(G1=G1, G2=G2, G12=G12)
    if min(G1, G2) < 2:
        out["beta"] = beta
        return out
    f12 = G12 / (G12 - 1) if G12 > 1 else 1.0
    V1 = XtXi @ (G1 / (G1 - 1) * M1) @ XtXi                  # the one-way CR1 variances
    V2 = XtXi @ (G2 / (G2 - 1) * M2) @ XtXi
    V = XtXi @ (G1 / (G1 - 1) * M1 + G2 / (G2 - 1) * M2 - f12 * M12) @ XtXi
    V = (V + V.T) / 2
    out["V_raw"] = V.copy()
    lam, vec = np.linalg.eigh(V)
    if lam.min() < 0:
        V = vec @ np.diag(np.maximum(lam, 0)) @ vec.T
        out["psd_fixed"] = True
    var = np.diag(V).copy()
    fb = ~(np.diag(out["V_raw"]) > 0)                        # this coefficient's two-way variance is not positive
    var[fb] = np.maximum(np.diag(V1), np.diag(V2))[fb]
    out["oneway_fallback"] = fb
    se = np.sqrt(np.maximum(var, 0))
    df = min(G1, G2) - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        t = beta / se
    q = stats.t.ppf(0.975, df)
    out.update(beta=beta, se=se, t=t, p=stats.t.sf(t, df), p2=2 * stats.t.sf(np.abs(t), df),
               ci95=np.column_stack([beta - q * se, beta + q * se]), df=df)
    return out


def mean_cluster2(y, g1, g2) -> dict:
    """Mean with two-way CR1 clustering (e.g. the coin x month sensitivity of §10.2), with ols_cluster2's flags
    psd_fixed and oneway_fallback (the two-way variance was not positive: the larger one-way CR1 variance is used)."""
    r = ols_cluster2(y, np.ones(len(np.asarray(y))), g1, g2)
    return dict(mean=float(r["beta"][0]), se=float(r["se"][0]), t=float(r["t"][0]), p=float(r["p"][0]),
                df=r["df"], G1=r["G1"], G2=r["G2"], ci95=tuple(r["ci95"][0]), psd_fixed=bool(r["psd_fixed"]),
                oneway_fallback=bool(r["oneway_fallback"][0]))


def ibragimov_muller(estimates) -> dict:
    """Ibragimov and Müller (2010): a Student t-test on q group estimates at q - 1 df. Returns mean, se, t, p
    (one-sided > 0), p2, df, q, ci95."""
    b = np.asarray(estimates, float)
    b = b[np.isfinite(b)]
    q = len(b)
    if q < 2:
        return dict(mean=float(b.mean()) if q else np.nan, se=np.nan, t=np.nan, p=np.nan, p2=np.nan, df=q - 1, q=q,
                    ci95=(np.nan, np.nan))
    m = float(b.mean())
    se = float(b.std(ddof=1) / math.sqrt(q))
    t = m / se if se > 0 else np.nan
    df = q - 1
    qq = stats.t.ppf(0.975, df)
    return dict(mean=m, se=se, t=t, p=_tsf(t, df), p2=float(2 * stats.t.sf(abs(t), df)) if np.isfinite(t) else np.nan,
                df=df, q=q, ci95=(m - qq * se, m + qq * se))


def im_ols(y, X, groups, j: int = 1) -> dict:
    """Coefficient j estimated by OLS separately in each group (e.g. fill-year), then ibragimov_muller. Groups where
    it is not identified are dropped (listed in `dropped`)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    g = np.asarray(groups)
    est, used, dropped = [], [], []
    for u in pd.unique(g):
        s = (g == u) & np.isfinite(y) & np.isfinite(X).all(1)
        Xs = X[s]
        if s.sum() <= X.shape[1] or np.linalg.matrix_rank(Xs) < X.shape[1]:
            dropped.append(u)
            continue
        est.append(float(np.linalg.lstsq(Xs, y[s], rcond=None)[0][j]))
        used.append(u)
    r = ibragimov_muller(est)
    r.update(estimates=dict(zip([str(u) for u in used], est)), dropped=[str(u) for u in dropped])
    return r


def p0_knife(sigma30) -> np.ndarray:
    """D-H5's covariate: the knife probability of a driftless lognormal coin, p0 = Phi((ln 0.5 + sigma_a^2/2) /
    sigma_a) with sigma_a = sigma30 sqrt(365)."""
    sa = np.asarray(sigma30, float) * math.sqrt(365.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return stats.norm.cdf((math.log(0.5) + 0.5 * sa ** 2) / sa)


def decile_dummies(x) -> np.ndarray:
    """Dummies for deciles 2..10 of x (decile 1 is the base): D-H5's sigma30-decile sensitivity."""
    x = np.asarray(x, float)
    cuts = np.nanquantile(x, np.arange(1, 10) / 10)
    d = np.searchsorted(cuts, x, side="right")
    return np.column_stack([(d == k).astype(float) for k in range(1, 10)])


def dh5_design(notq, rung, sigma30, vol_control: str = "p0"):
    """X for knife = a + b notQ + rung dummies + gamma p0 (or sigma30-decile dummies). Column 1 is notQ."""
    notq = np.asarray(notq, float)
    rung = np.asarray(rung)
    lev = sorted(pd.unique(rung))
    cols = [np.ones(len(notq)), notq] + [(rung == r).astype(float) for r in lev[1:]]
    names = ["const", "notQ"] + [f"rung_{r}" for r in lev[1:]]
    if vol_control == "p0":
        cols.append(p0_knife(sigma30))
        names.append("p0")
    else:
        D = decile_dummies(sigma30)
        cols += [D[:, i] for i in range(D.shape[1])]
        names += [f"sigma_dec{i + 2}" for i in range(D.shape[1])]
    return np.column_stack(cols), names


def dh5_fit(knife, notq, rung, sigma30, coin, quarter, vol_control: str = "p0") -> dict:
    """D-H5 KNIFE (§10.4): b on notQ with rung dummies and p0 (or sigma30 deciles), two-way coin x quarter CR1 at
    min(G_coin, G_q) - 1 df. Also each group's knife rate and the raw difference."""
    X, names = dh5_design(notq, rung, sigma30, vol_control)
    r = ols_cluster2(knife, X, coin, quarter)
    k = np.asarray(knife, float)
    nq = np.asarray(notq, float) == 1
    return dict(b=float(r["beta"][1]), se=float(r["se"][1]), t=float(r["t"][1]), df=r["df"],
                ci95=tuple(r["ci95"][1]), G_coin=r["G1"], G_quarter=r["G2"], n=r["n"], psd_fixed=r["psd_fixed"],
                oneway_fallback=bool(r["oneway_fallback"][1]),
                rate_q1=float(np.nanmean(k[~nq])), rate_rest=float(np.nanmean(k[nq])),
                raw_diff=float(np.nanmean(k[nq]) - np.nanmean(k[~nq])), names=names)


def dh5_im(knife, notq, rung, sigma30, year, vol_control: str = "p0") -> dict:
    """D-H5's Ibragimov-Müller sensitivity over fill-years."""
    X, _ = dh5_design(notq, rung, sigma30, vol_control)
    return im_ols(knife, X, year, j=1)


def dh5_drop_worst_coin(knife, notq, rung, sigma30, coin, quarter, vol_control: str = "p0"):
    """D-H5's removal check (S15): b after removing the coin whose removal lowers it most. Returns (b_after, coin)."""
    a = [np.asarray(v) for v in (knife, notq, rung, sigma30, coin, quarter)]
    best, which = np.inf, None
    for c in pd.unique(a[4]):
        m = a[4] != c
        b = dh5_fit(*[v[m] for v in a], vol_control=vol_control)["b"]
        if np.isfinite(b) and b < best:
            best, which = b, c
    return (best if which is not None else np.nan), which


# ============================================================================ Kaplan-Meier waiting times

def kaplan_meier(time, event) -> pd.DataFrame:
    """Product-limit estimate for right-censored waits. Rows: each distinct time with n_risk, n_event, n_censor,
    surv (S just after it) and var (Greenwood). At tied times events precede censorings."""
    t = np.asarray(time, float)
    e = np.asarray(event).astype(bool)
    k = np.isfinite(t)
    t, e = t[k], e[k]
    if len(t) == 0:
        return pd.DataFrame(columns=["time", "n_risk", "n_event", "n_censor", "surv", "var"])
    u, inv = np.unique(t, return_inverse=True)
    d = np.bincount(inv, weights=e.astype(float)).astype(np.int64)
    c = np.bincount(inv, weights=(~e).astype(float)).astype(np.int64)
    n_risk = len(t) - np.r_[0, np.cumsum(d + c)[:-1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        surv = np.cumprod(1.0 - d / n_risk)
        gw = np.cumsum(np.where(d > 0, d / (n_risk * (n_risk - d)), 0.0))
        var = np.where(surv > 0, surv ** 2 * gw, 0.0)
    return pd.DataFrame(dict(time=u, n_risk=n_risk, n_event=d, n_censor=c, surv=surv, var=var))


def _km_step(time, event):
    tab = kaplan_meier(time, event)
    ev = tab[tab["n_event"] > 0]
    return ev["time"].to_numpy(float), ev["surv"].to_numpy(float), ev


def km_survival(time, event, at) -> np.ndarray:
    """S(at) of the Kaplan-Meier step function (1 before the first event)."""
    te, se, _ = _km_step(time, event)
    at = np.atleast_1d(np.asarray(at, float))
    i = np.searchsorted(te, at, side="right") - 1
    return np.where(i >= 0, se[np.clip(i, 0, None)] if len(se) else 1.0, 1.0)


def km_median(time, event) -> float:
    """The first time at which S <= 0.5 (NaN if S never reaches 0.5)."""
    te, se, _ = _km_step(time, event)
    hit = np.where(se <= 0.5)[0]
    return float(te[hit[0]]) if len(hit) else np.nan


def km_restricted_mean(time, event, horizon: float = KM_HORIZON):
    """Restricted mean wait over [0, horizon]: the exact integral of the KM step function, and its SE (Klein and
    Moeschberger: var = sum over event times t_i <= horizon of A_i^2 d_i / (n_i (n_i - d_i)), A_i = integral of S
    from t_i to horizon). Returns (rmst, se)."""
    te, se_, ev = _km_step(time, event)
    keep = te <= horizon
    te, s, ev = te[keep], se_[keep], ev[keep]
    knots = np.r_[0.0, te, horizon]
    vals = np.r_[1.0, s]
    widths = np.diff(knots)
    rmst = float((vals * widths).sum())
    seg = vals[1:] * widths[1:]                          # integral of S over [t_i, t_{i+1}) for each event time
    A = np.cumsum(seg[::-1])[::-1]                       # integral from t_i to the horizon
    d = ev["n_event"].to_numpy(float)
    n = ev["n_risk"].to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(n > d, A ** 2 * d / (n * (n - d)), 0.0)
    return rmst, float(math.sqrt(terms.sum()))


def waiting_summary(time, event, horizon: float = KM_HORIZON) -> dict:
    """D6 inputs: W = restricted mean wait over the horizon as a share of it, F = P(fill within the horizon),
    p_no_fill = S(horizon), the median wait, and counts."""
    rm, rse = km_restricted_mean(time, event, horizon)
    s_h = float(km_survival(time, event, horizon)[0])
    e = np.asarray(event).astype(bool)
    return dict(W=rm / horizon, W_se=rse / horizon, rmst=rm, rmst_se=rse, F=1 - s_h, p_no_fill=s_h,
                median=km_median(time, event), n=int(len(e)), events=int(e.sum()), horizon=horizon)


def mu_star(F, theta, W, theta_ci=None) -> dict:
    """D6 break-even: mu*_k = F_k theta_k / W_k, with the interval carried from theta_k's interval."""
    m = F * theta / W if W > 0 else np.nan
    ci = None if theta_ci is None else (F * theta_ci[0] / W, F * theta_ci[1] / W)
    return dict(mu_star=m, ci=ci)


# ============================================================================ the sheet's fill odds (S14)

def overdispersion_phi(x, n) -> dict:
    """Pearson dispersion of yearly fill counts x out of n bid-weeks against one binomial rate:
    chi2 = sum (x - n p)^2 / (n p (1 - p)), df = Y - 1, phi = chi2 / df."""
    x = np.asarray(x, float)
    n = np.asarray(n, float)
    k = np.isfinite(x) & np.isfinite(n) & (n > 0)
    x, n = x[k], n[k]
    if len(x) < 2 or n.sum() <= 0:
        return dict(phi=np.nan, chi2=np.nan, df=len(x) - 1, p=np.nan)
    p = x.sum() / n.sum()
    if p <= 0 or p >= 1:
        return dict(phi=np.nan, chi2=np.nan, df=len(x) - 1, p=p)
    chi2 = float(((x - n * p) ** 2 / (n * p * (1 - p))).sum())
    return dict(phi=chi2 / (len(x) - 1), chi2=chi2, df=len(x) - 1, p=float(p))


def wilson(x, n, level: float = 0.95, phi: float = 1.0) -> tuple:
    """Wilson interval for x successes in n, with the half-width widened by sqrt(max(phi, 1)) (S14), clipped to
    [0, 1]. Returns (lo, hi, centre)."""
    if n <= 0:
        return (np.nan, np.nan, np.nan)
    z = stats.norm.ppf(1 - (1 - level) / 2)
    ph = x / n
    den = 1 + z * z / n
    centre = (ph + z * z / (2 * n)) / den
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    f = math.sqrt(max(phi, 1.0)) if np.isfinite(phi) else 1.0
    return (max(0.0, centre - f * half), min(1.0, centre + f * half), centre)


# ============================================================================ bootstraps for accounts and episodes

def _period_stat(stat, ppy):
    if callable(stat):
        return stat

    def mean_(X):
        return X.mean(axis=1)

    def cagr(X):
        with np.errstate(divide="ignore", invalid="ignore"):
            lg = np.log1p(X)
        ruin = ~(X > -1).all(axis=1)
        g = np.exp(lg.sum(axis=1) * ppy / X.shape[1]) - 1
        return np.where(ruin, -1.0, g)

    def sharpe(X):
        sd = X.std(axis=1, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            return X.mean(axis=1) / sd * math.sqrt(ppy)

    return {"mean": mean_, "cagr": cagr, "sharpe": sharpe}[stat]


def stationary_bootstrap(x, y=None, stat="mean", mean_block: float = 6.0, B: int = B_BOOT, seed=SEED,
                         level: float = 0.95, ppy: int = 12, return_draws: bool = False, chunk: int = 2000) -> dict:
    """D7 (§10.4, S12): stationary block bootstrap (Politis and Romano 1994) of a monthly return series, paired with a
    benchmark y when given (both resampled on the same months; the statistic is stat(x) - stat(y)). stat: "mean"
    (per month), "cagr" (annualized with ppy), "sharpe" (annualized), or fn(X) acting row-wise on an (n, T) array.
    mean_block in months: 6 (primary) or 12 (sensitivity and the gatekept sentence). Returns estimate, se (bootstrap
    SD), ci (percentile), ci_basic, p_le0 (share of draws <= 0), B, T."""
    x = np.asarray(x, float)
    if y is not None:
        y = np.asarray(y, float)
        k = np.isfinite(x) & np.isfinite(y)
        x, y = x[k], y[k]
    else:
        x = x[np.isfinite(x)]
    T = len(x)
    fn = _period_stat(stat, ppy)

    def evaluate(Xa, Ya):
        v = fn(Xa)
        return v - fn(Ya) if Ya is not None else v

    est = float(evaluate(x[None, :], None if y is None else y[None, :])[0])
    rng = _rng(seed)
    draws = np.empty(B)
    for s in range(0, B, chunk):
        b = min(chunk, B - s)
        idx, _ = sb_indices(T, mean_block, b, rng)
        draws[s:s + b] = evaluate(x[idx], None if y is None else y[idx])
    a = 1 - level
    lo, hi = _q(draws, a / 2), _q(draws, 1 - a / 2)
    out = dict(estimate=est, se=float(np.nanstd(draws, ddof=1)), ci=(lo, hi), ci_basic=(2 * est - hi, 2 * est - lo),
               p_le0=float(np.mean(draws <= 0)), B=B, T=T, mean_block=mean_block, level=level)
    if return_draws:
        out["draws"] = draws
    return out


def ratio_cluster_bootstrap(num, den, clusters, B: int = B_BOOT, seed=SEED, level: float = 0.95,
                            return_draws: bool = False, chunk: int = 2000) -> dict:
    """Pairs cluster bootstrap of R = sum(num)/sum(den): whole clusters (episodes) resampled with replacement,
    percentile interval. A mean is den = 1; an excess rate (fills minus twins, T1) is num = the per-fill difference.
    Returns estimate, se, ci, G, B."""
    num = np.asarray(num, float)
    den = np.asarray(den, float)
    c, _ = _codes(clusters)
    k = np.isfinite(num) & np.isfinite(den) & (c >= 0)
    num, den, c = num[k], den[k], c[k]
    c, _ = _codes(c)
    G = int(c.max()) + 1 if len(c) else 0
    if G == 0 or den.sum() == 0:
        return dict(estimate=np.nan, se=np.nan, ci=(np.nan, np.nan), G=G, B=B)
    Sn = np.bincount(c, weights=num, minlength=G)
    Sd = np.bincount(c, weights=den, minlength=G)
    rng = _rng(seed)
    draws = np.empty(B)
    pv = np.full(G, 1.0 / G)
    for s in range(0, B, chunk):
        b = min(chunk, B - s)
        cnt = rng.multinomial(G, pv, size=b).astype(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            draws[s:s + b] = (cnt @ Sn) / (cnt @ Sd)
    a = 1 - level
    out = dict(estimate=float(num.sum() / den.sum()), se=float(np.nanstd(draws, ddof=1)),
               ci=(_q(draws, a / 2), _q(draws, 1 - a / 2)), G=G, B=B, level=level)
    if return_draws:
        out["draws"] = draws
    return out


def cluster_bootstrap(fn, arrays, clusters, B: int = 1999, seed=SEED, level: float = 0.95) -> dict:
    """General pairs cluster bootstrap (slow path): fn(*arrays_subset) -> float on whole clusters resampled with
    replacement; percentile interval. Returns estimate, se, ci, G, B."""
    arrays = [np.asarray(a) for a in arrays]
    c, _ = _codes(clusters)
    G = int(c.max()) + 1
    rows = [np.where(c == g)[0] for g in range(G)]
    rng = _rng(seed)
    est = float(fn(*arrays))
    draws = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, G, G)
        ix = np.concatenate([rows[g] for g in pick])
        draws[b] = fn(*[a[ix] for a in arrays])
    a = 1 - level
    return dict(estimate=est, se=float(np.nanstd(draws, ddof=1)), ci=(_q(draws, a / 2), _q(draws, 1 - a / 2)), G=G,
                B=B, level=level)


def d5_calibration(realized, predicted, clusters, half, B: int = B_BOOT, seed=SEED, level: float = 0.90,
                   band=D5_BAND) -> dict:
    """D5 (S14): realized/predicted fill counts per half with an episode-cluster bootstrap interval (90%); calibrated
    if both halves' intervals overlap the band [0.67, 1.5]. Returns {half: {ratio, ci, overlaps, G}, calibrated}."""
    realized = np.asarray(realized, float)
    predicted = np.asarray(predicted, float)
    cl = np.asarray(clusters)
    h = np.asarray(half)
    rng = _rng(seed)
    out, ok = {}, []
    for hv in sorted(pd.unique(h)):
        s = h == hv
        r = ratio_cluster_bootstrap(realized[s], predicted[s], cl[s], B=B, seed=rng, level=level)
        ov = bool(np.isfinite(r["ci"][0]) and r["ci"][0] <= band[1] and r["ci"][1] >= band[0])
        out[str(hv)] = dict(ratio=r["estimate"], ci=r["ci"], overlaps=ov, G=r["G"])
        ok.append(ov)
    out["calibrated"] = bool(len(ok) == 2 and all(ok))
    return out


# ============================================================================ K3: inference calibration

def _run_tasks(fn, tasks, n_jobs: int = 1, mp_context: str = "spawn"):
    """Map fn over tasks, in worker processes when n_jobs > 1 (spawned with one BLAS thread each)."""
    if n_jobs <= 1 or len(tasks) <= 1:
        return [fn(t) for t in tasks]
    try:
        pickle.dumps(tasks[0])
    except Exception as exc:                                  # a lambda or closure cannot cross processes
        warnings.warn(f"tasks are not picklable ({exc!r}); running serially")
        return [fn(t) for t in tasks]
    old = {k: os.environ.get(k) for k in _THREAD_VARS}
    os.environ.update({k: "1" for k in _THREAD_VARS})
    try:
        with cf.ProcessPoolExecutor(n_jobs, mp_context=mp.get_context(mp_context)) as ex:
            return list(ex.map(fn, tasks))
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _k3_rep(data: dict, B: int, rng, level: float) -> dict:
    rec = {}
    for test in ("H1", "H2R"):
        if test not in data:
            continue
        d = data[test]
        y = np.asarray(d["y"], float)
        r = test_mean(y, d["clusters"], weights=d.get("weights"), B=B, seed=rng, level=level)
        truth = float(d.get("truth", 0.0))
        rec[test] = dict(est=r["estimate"], se=r["se"], stat=r["t"], gstar=r["gstar"], G=r["G"], p_wcr=r["p_wcr"],
                         p_gstar=r["p_gstar"], p_decide=r["p_decide"], ub=r["ub"], truth=truth,
                         miss=bool(np.isfinite(r["ub"]) and r["ub"] < truth),
                         pivot=(r["estimate"] - truth) / r["se"] if r["se"] > 0 else np.nan,
                         total=float(np.nansum(y)), mde=r["mde"])
    if "H4" in data:
        d = data["H4"]
        r = test_h4(d["methods"], B=B, seed=rng, level=level)
        tab = r["methods"]
        tr = d.get("truth", 0.0)
        truth = np.array([float(tr.get(m, 0.0)) if isinstance(tr, dict) else float(tr) for m in tab["method"]])
        b, se, ubm = (tab[c].to_numpy(float) for c in ("b", "se", "ub"))
        ok = np.isfinite(b) & np.isfinite(se) & (se > 0)
        piv = float(np.min((b[ok] - truth[ok]) / se[ok])) if ok.any() else np.nan
        miss = bool(np.any(np.isfinite(ubm) & (ubm < truth)))
        rec["H4"] = dict(est=r["estimate"], se=r["se"], stat=r["T"], gstar=r["gstar"], G=r["G"], p_wcr=r["p_wcr"],
                         p_gstar=r["p_gstar"], p_decide=r["p_decide"], ub=r["ub"], truth=float(np.max(truth)),
                         miss=miss, pivot=piv, argmax=r["argmax"], b=b.tolist(), se_m=se.tolist(),
                         methods=tab["method"].tolist(), mde=r["mde"])
    return rec


def _k3_task(args):
    sim_fn, scenario, s_idx, reps, B, seed, level = args
    out = []
    for rep in reps:
        rng = np.random.default_rng(np.random.SeedSequence([seed, s_idx, rep]))
        data = sim_fn(scenario, rep, rng)
        out.append((rep, _k3_rep(data, B, rng, level)))
    return scenario, out


def inference_calibration(sim_fn, n_reps: int = 2000, scenarios=("base", "high", "hetero"), B: int = B_BOOT,
                          seed=SEED, n_jobs: int = 4, levels=K3_LEVELS, level_noedge: float = LEVEL_NOEDGE,
                          factor: float = K3_FACTOR, chunk: int = 25, mp_context: str = "spawn",
                          keep_null: bool = True) -> dict:
    """K3 (§10.5): run the decisive machinery (test_mean for H1/H2R, test_h4 for H4, same B and level as the real
    tests) on n_reps synthetic replications per scenario. sim_fn(scenario, rep, rng) returns any of
      {"H1": {"y", "clusters", "truth": 0.0}, "H2R": {...}, "H4": {"methods": {name: frame}, "truth": 0.0}}
    (truth = the true value of the statistic; under the null 0; non-zero truths give power instead of size). With
    n_jobs > 1 the workers are spawned (one BLAS thread each): sim_fn must be a module-level function and its
    module's top level import-safe (work under `if __name__ == "__main__"`); mp_context="fork" is the alternative.
    Replication r of scenario i uses default_rng(SeedSequence([seed, i, r])) for both sim_fn and the bootstrap. At the
    minimum 2,000 replications, a test whose size is exactly nominal fails the rule at the 1.67% level about 28% of
    the time (11% at 3,000, 1.5% at 5,000), so more replications sharpen it. Returns a JSON-ready dict:
      tests[test]: by_scenario[s]: false_pass {level: rate, k, n, ci95, limit, ok}, noedge_miss {...},
        est_mean, est_sd, se_mean, gstar_median, mde_formula (median), mde_empirical, stat quantiles;
        k3_pass, needs_calibration (the simulation-calibrated rule applies when K3 fails);
      null[test][s]: stat, est, se, pivot (and H1's total, D11's null distribution) per replication.
    Apply with calibrated_p / calibrated_bound / apply_calibration; d11_percentile for D11."""
    t0 = time.time()
    tasks = [(sim_fn, s, i, list(range(r0, min(r0 + chunk, n_reps))), B, seed, level_noedge)
             for i, s in enumerate(scenarios) for r0 in range(0, n_reps, chunk)]
    res = _run_tasks(_k3_task, tasks, n_jobs, mp_context)
    recs = {s: {} for s in scenarios}
    for s, out in res:
        for rep, rec in out:
            recs[s][rep] = rec
    tests = sorted({t for s in scenarios for r in recs[s].values() for t in r}, key=lambda t: FAMILY.index(t))
    nominal_miss = 1 - level_noedge
    summary, null = {}, {}
    for test in tests:
        by, ok_all = {}, True
        null[test] = {}
        for s in scenarios:
            rs = [recs[s][r][test] for r in sorted(recs[s]) if test in recs[s][r]]
            n = len(rs)
            p = np.array([r["p_decide"] for r in rs], float)
            fp = {}
            for lv in levels:
                k = int(np.sum(np.isfinite(p) & (p < lv)))
                ci = clopper_pearson(k, n)
                fp[f"{lv:.4f}"] = dict(rate=k / n if n else np.nan, k=k, n=n, ci95=ci, limit=factor * lv,
                                       ok=bool(ci[1] <= factor * lv))
            km = int(np.sum([r["miss"] for r in rs]))
            ci = clopper_pearson(km, n)
            miss = dict(rate=km / n if n else np.nan, k=km, n=n, ci95=ci, nominal=nominal_miss,
                        limit=factor * nominal_miss, ok=bool(ci[1] <= factor * nominal_miss))
            est = np.array([r["est"] for r in rs], float)
            se = np.array([r["se"] for r in rs], float)
            gs = np.array([r["gstar"] for r in rs], float)
            st = np.array([r["stat"] for r in rs], float)
            piv = np.array([r["pivot"] for r in rs], float)
            gmed = float(np.nanmedian(gs)) if n else np.nan
            sd = float(np.nanstd(est, ddof=1)) if n > 1 else np.nan
            ok_s = all(v["ok"] for v in fp.values()) and miss["ok"]
            ok_all = ok_all and ok_s
            by[s] = dict(n=n, false_pass=fp, noedge_miss=miss, ok=ok_s, est_mean=float(np.nanmean(est)),
                         est_sd=sd, se_mean=float(np.nanmean(se)), gstar_median=gmed,
                         mde_formula=float(np.nanmedian([r["mde"] for r in rs])) if n else np.nan,
                         mde_empirical=mde(sd, gmed),
                         stat_q={str(qq): _q(st, qq) for qq in (0.9, 0.95, 0.975, 1 - ALPHA_B, 0.99)},
                         pivot_q=_q(piv, nominal_miss),
                         p_wcr_rate05=float(np.mean(np.array([r["p_wcr"] for r in rs], float) < 0.05)) if n else np.nan,
                         p_gstar_rate05=float(np.mean(np.array([r["p_gstar"] for r in rs], float) < 0.05))
                         if n else np.nan)
            if test == "H4" and n:
                am = pd.Series([r["argmax"] for r in rs]).value_counts(normalize=True)
                by[s]["argmax_share"] = {str(k): float(v) for k, v in am.items()}
            null[test][s] = dict(stat=st.tolist(), est=est.tolist(), se=se.tolist(), pivot=piv.tolist())
            if test == "H1":
                null[test][s]["total"] = [r["total"] for r in rs]
        worst = max(scenarios, key=lambda s_: tuple(by[s_]["false_pass"][f"{lv:.4f}"]["rate"] for lv in levels))
        summary[test] = dict(by_scenario=by, k3_pass=bool(ok_all), needs_calibration=not ok_all,
                             rule="nominal" if ok_all else "simulation-calibrated", worst_scenario=worst)
    out = dict(n_reps=n_reps, B=B, seed=seed, scenarios=list(scenarios), levels=list(levels),
               level_noedge=level_noedge, factor=factor, tests=summary,
               all_pass=bool(all(v["k3_pass"] for v in summary.values())), seconds=round(time.time() - t0, 1))
    if keep_null:
        out["null"] = null
    return out


def calibrated_p(test: str, stat_obs: float, calib: dict) -> float:
    """The simulation-calibrated p (§10.5): the largest over scenarios of (1 + #{null stat >= observed}) / (n + 1),
    with stat = t (H1, H2R) or T = max_j t_j (H4). `calib` must come from NULL replications (truth 0). An undefined
    observed statistic (NaN, e.g. one cluster) has an undefined p (NaN, which never passes), not 1/(n + 1)."""
    if stat_obs is None or np.isnan(stat_obs):
        return np.nan
    best = np.nan
    for s, d in calib["null"][test].items():
        st = np.asarray(d["stat"], float)
        st = st[np.isfinite(st)]
        if len(st) == 0:
            continue
        p = (1 + np.sum(st >= stat_obs)) / (len(st) + 1)
        best = p if np.isnan(best) else max(best, p)
    return float(best)


def _calib_q(test: str, calib: dict, level=None) -> float:
    """The simulated pivot quantile q_a, a = 1 - level, at the scenario with the smallest one (NaN if none)."""
    level = calib["level_noedge"] if level is None else level
    qs = [_q(np.asarray(d["pivot"], float), 1 - level) for d in calib["null"][test].values()]
    qs = [q for q in qs if np.isfinite(q)]
    return float(min(qs)) if qs else np.nan


def _calib_bounds(test: str, est, se, calib: dict, level=None, nominal=None) -> np.ndarray:
    """Per-element bounds est - q_a(pivot) se, floored at `nominal` when given (NaN propagates)."""
    ub = np.atleast_1d(np.asarray(est, float)) - _calib_q(test, calib, level) * np.atleast_1d(np.asarray(se, float))
    if nominal is not None:
        ub = np.maximum(ub, np.atleast_1d(np.asarray(nominal, float)))
    return ub


def calibrated_bound(test: str, est, se, calib: dict, level=None, nominal=None) -> float:
    """The NO EDGE bound with the simulated quantile (§10.5): est - q_a(pivot) se, a = 1 - level, at the scenario with
    the smallest quantile. Without `nominal` it is that bound alone, which can be NARROWER than the nominal one; the
    decision bound is max(nominal, it), because §10.2 says the bound "is widened if K3 requires" (pass nominal=, or
    use apply_calibration, which does). For H4, est, se (and nominal) are per-method arrays and the bound is the
    largest over methods, NaN if any method's is NaN (a method without a bound leaves H4 unbounded, coding choice 6)."""
    ub = _calib_bounds(test, est, se, calib, level, nominal)
    return float(np.max(ub)) if len(ub) else np.nan


def apply_calibration(row: dict, test: str, calib: dict) -> dict:
    """If K3 failed for `test` (§10.5), its p_decide becomes the simulation-calibrated p and its NO EDGE bound is
    widened with the simulated quantile: ub = max(nominal bound, est - q_a(pivot) se), per method for H4 and then the
    largest over methods (NaN if any method has none, or a pre-registered method is absent). §10.2: the bound "is
    widened if K3 requires", so K3 never narrows it; a K3 failure on the false-PASS side alone, with a nominal bound
    that over-covers, leaves the bound as it was. Keeps p_decide_nominal, ub_nominal and ub_calibrated (the
    simulated-quantile bound alone, for reference); recomputes noedge and harms from the widened bound. For H4 the
    methods table (a copy) gets ub_nominal, ub_calibrated and the widened ub. Else returns the row unchanged."""
    if not calib["tests"].get(test, {}).get("needs_calibration", False):
        return row
    r = dict(row)
    r["p_decide_nominal"], r["ub_nominal"] = r.get("p_decide"), r.get("ub")
    if test == "H4":
        tab = r["methods"].copy()
        b, se, ub_nom = (tab[k].to_numpy(float) for k in ("b", "se", "ub"))
        ub_cal = _calib_bounds(test, b, se, calib)
        tab["ub_nominal"], tab["ub_calibrated"] = ub_nom, ub_cal
        tab["ub"] = np.maximum(ub_nom, ub_cal)                            # widened, never narrowed (NaN propagates)
        complete = len(tab) > 0 and len(tab) >= r.get("n_bonf", len(tab))
        r["methods"] = tab
        r["p_decide"] = calibrated_p(test, r["T"], calib)
        r["ub_calibrated"] = float(np.max(ub_cal)) if complete else np.nan
        r["ub"] = float(np.max(tab["ub"].to_numpy(float))) if complete else np.nan
    else:
        r["p_decide"] = calibrated_p(test, r["t"], calib)
        r["ub_calibrated"] = calibrated_bound(test, r["estimate"], r["se"], calib)
        r["ub"] = calibrated_bound(test, r["estimate"], r["se"], calib, nominal=_f(r["ub_nominal"]))  # None -> NaN
    E_ = _f(r.get("E", np.nan))
    ub = r["ub"]
    r["noedge"] = bool((np.isfinite(ub) or np.isneginf(ub)) and np.isfinite(E_) and ub < E_)
    r["harms"] = bool((np.isfinite(ub) or np.isneginf(ub)) and ub < 0)
    r["calibrated"] = True
    return r


def d11_percentile(total_obs: float, calib: dict) -> dict:
    """D11 luck: P1's total Delta against the null totals of K3's synthetic panels, per scenario: the share of null
    totals at or above it, (1 + #)/(n + 1), and the null quantiles."""
    out = {}
    for s, d in calib["null"].get("H1", {}).items():
        tot = np.asarray(d.get("total", []), float)
        tot = tot[np.isfinite(tot)]
        if len(tot) == 0:
            continue
        out[s] = dict(p_upper=float((1 + np.sum(tot >= total_obs)) / (len(tot) + 1)), n=int(len(tot)),
                      q05=_q(tot, 0.05), q50=_q(tot, 0.5), q95=_q(tot, 0.95))
    return out


# ============================================================================ selftest: synthetic designs
# A calendar shaped like P1's draft month-block sizes (counts only: 58 blocks, 98 down to 1 fills, G* = 12.4).
SIZES_58 = np.array([98, 88, 87, 85, 75, 72, 69, 67, 63, 55, 41, 40, 39, 33, 25, 22, 22, 21, 19, 19, 18, 17, 17, 16,
                     15, 15, 14, 9, 8, 8, 7, 7, 6, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1,
                     1, 1, 1])


def _dgp_mean(kind: str, rng, effect: float = 0.0):
    """Synthetic per-fill values with clustered errors. 'balanced': 60 x 20, normal; 'crash': SIZES_58, Student-t(3)
    cluster shocks whose SD grows with cluster size (crash months), Student-t(4) fill noise; 'hetero': SIZES_58 with
    mean-zero t(3) cluster effects of SD 3% (K3's heterogeneous-effect null). Returns (y, clusters)."""
    if kind == "balanced":
        sizes = np.full(60, 20)
        mu = 0.01 * rng.standard_normal(60)
        g = np.repeat(np.arange(60), sizes)
        return effect + mu[g] + 0.05 * rng.standard_normal(len(g)), g
    sizes = SIZES_58
    G = len(sizes)
    g = np.repeat(np.arange(G), sizes)
    if kind == "crash":
        sd = 0.02 * (1 + sizes / 25.0)
    else:
        sd = np.full(G, 0.03)
    mu = sd * rng.standard_t(3, G) / math.sqrt(3)
    eps = 0.06 * rng.standard_t(4, len(g)) / math.sqrt(2)
    return effect + mu[g] + eps, g


def _dgp_h4(rng, b=(0.0, 0.0, 0.0, 0.0), s: float = 0.01, frac: float = 0.6, beta_sd: float = 0.01,
            slope_sd: float = 0.003, eps_sd: float = 0.04, cw_sd: float = 0.05, straddle: float = 0.0,
            sizes=SIZES_58) -> dict:
    """Stacked H4 frames for four methods on the crash calendar. Per coin-week: a real level and four placebos at
    depth offsets (-1, -0.5, 0, +0.5, +1) x ATR%/sigma (U(1.4, 2.0)); the wick depth is the shallowest level plus an
    exponential with P(real fills | shallowest fills) = 0.4; fills are nested (deeper only if shallower). Delta =
    coin-week shock + (s + slope_g) depth + (b_j + beta_g) real + t(4) noise; slope_g and beta_g (mean 0) are shared by
    the four methods within a month-block. `straddle`: share of coin-weeks whose deeper fills land in the next
    block."""
    G = len(sizes)
    beta_g = beta_sd * rng.standard_t(3, G) / math.sqrt(3)
    slope_g = slope_sd * rng.standard_t(3, G) / math.sqrt(3)
    offs = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
    out = {}
    for jm, name in enumerate(H4_METHODS):
        m_g = rng.poisson(frac * sizes)
        ncw = int(m_g.sum())
        gcw = np.repeat(np.arange(G), m_g)
        a = rng.uniform(1.4, 2.0, ncw)
        dr = rng.uniform(4.0, 14.0, ncw)
        lam = math.log(2.5) / a
        omega = -a + rng.exponential(1.0 / lam)
        dev = offs[None, :] * a[:, None]
        filled = dev <= omega[:, None]
        cw, lev = np.nonzero(filled)
        depth = dr[cw] + dev[cw, lev]
        real = (lev == 2).astype(float)
        g = gcw[cw]
        if straddle > 0:
            mv = (rng.random(ncw) < straddle)[cw] & (lev >= 2)
            g = np.where(mv, np.minimum(g + 1, G - 1), g)
        y = (cw_sd * rng.standard_normal(ncw))[cw] + (s + slope_g[g]) * depth + (b[jm] + beta_g[g]) * real \
            + eps_sd * rng.standard_t(4, len(cw)) / math.sqrt(2)
        out[name] = pd.DataFrame(dict(y=y, real=real, depth=depth, depth_real=dr[cw], cw=cw, cluster=g))
    return out


def _toy_k3_sim(scenario: str, rep: int, rng) -> dict:
    """K3 toy for the selftest: H1 and H2R on the crash calendar, H4 on a small stacked design. In 'fine' the H1
    clusters given to the test split each true block into four labels (dependence the inference cannot see)."""
    scale = 1.5 if scenario == "high" else 1.0
    y, g = _dgp_mean("crash", rng)
    y = y * scale
    cl = g * 4 + rng.integers(0, 4, len(g)) if scenario == "fine" else g
    y2, g2 = _dgp_mean("hetero", rng)
    meth = _dgp_h4(rng, frac=0.25)
    return {"H1": dict(y=y, clusters=cl, truth=0.0), "H2R": dict(y=0.5 * y2, clusters=g2, truth=0.0),
            "H4": dict(methods=meth, truth=0.0)}


def _w_mean_size(args):
    kind, seeds, B, effect = args
    out = []
    for s in seeds:
        rng = np.random.default_rng(s)
        y, g = _dgp_mean(kind, rng, effect)
        r = test_mean(y, g, B=B, seed=rng)
        c = cr1_mean(y, g)
        out.append((r["p_wcr"], r["p_gstar"], r["p_decide"], r["ub"], r["ci95"][0], r["ci95"][1],
                    _tsf(c["t"], c["G"] - 1), r["estimate"], r["se"], r["gstar"]))
    return out


def _w_h4(args):
    seeds, B, bvec, s = args
    out = []
    for sd in seeds:
        rng = np.random.default_rng(sd)
        meth = _dgp_h4(rng, b=bvec, s=s)
        r = test_h4(meth, B=B, seed=rng)
        tab = r["methods"]
        naive = [float(f.y[f.real == 1].mean() - f.y[f.real == 0].mean()) for f in meth.values()]
        out.append(dict(T=r["T"], argmax=r["argmax"], p_wcr=r["p_wcr"], p_gstar=r["p_gstar"], p_decide=r["p_decide"],
                        ub=r["ub"], b=tab["b"].tolist(), se=tab["se"].tolist(), p_rw=tab["p_rw"].tolist(),
                        ubm=tab["ub"].tolist(), naive=naive, gstar=tab["gstar"].tolist(), n=tab["n"].tolist()))
    return out


# ============================================================================ selftest: oracles (separate code)

def _oracle_lsdv(y, X, fe, w):
    """Design with explicit FE dummies (no singleton handling: the caller passes data without singletons)."""
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    if fe is None:
        return X
    u = sorted(set(fe.tolist()))
    D = np.column_stack([(fe == v).astype(float) for v in u])
    return np.column_stack([X, D])


def _oracle_wild(y, X, j, cl, fe, w, Wd, restricted, null):
    """Brute force: for each draw build y* from the restricted (or unrestricted) dummy-variable fit, re-estimate the
    whole model by WLS with explicit dummies, and form the CR1 sandwich with a loop over clusters."""
    A = _oracle_lsdv(y, X, fe, w)
    sw = np.sqrt(w)

    def wls(yv, Am):
        coef = np.linalg.lstsq(sw[:, None] * Am, sw * yv, rcond=None)[0]
        return coef, yv - Am @ coef

    full, _ = wls(y, A)
    if restricted:
        cols = [i for i in range(A.shape[1]) if i != j]
        yr = y - null * A[:, j]
        uR = wls(yr, A[:, cols])[1] if cols else yr
        base, resid, centre = y - uR, uR, null
    else:
        coef, u = wls(y, A)
        base, resid, centre = y - u, u, full[j]
    labs = sorted(set(cl.tolist()))
    G = len(labs)
    gi = np.array([labs.index(v) for v in cl])
    out = []
    As = sw[:, None] * A
    bread = np.linalg.pinv(As.T @ As)
    for b in range(Wd.shape[0]):
        ys = base + Wd[b, gi] * resid
        coef, u = wls(ys, A)
        es = sw * u
        meat = np.zeros((A.shape[1], A.shape[1]))
        for g in range(G):
            sg = As[gi == g].T @ es[gi == g]
            meat += np.outer(sg, sg)
        V = G / (G - 1) * bread @ meat @ bread
        out.append((coef[j] - centre) / math.sqrt(V[j, j]))
    return np.array(out), full, A


def _oracle_cr1(y, X, cl, fe, w, j):
    A = _oracle_lsdv(y, X, fe, w)
    sw = np.sqrt(w)
    As = sw[:, None] * A
    coef = np.linalg.lstsq(As, sw * y, rcond=None)[0]
    es = sw * (y - A @ coef)
    labs = sorted(set(cl.tolist()))
    bread = np.linalg.pinv(As.T @ As)
    meat = np.zeros((A.shape[1], A.shape[1]))
    for v in labs:
        sg = As[cl == v].T @ es[cl == v]
        meat += np.outer(sg, sg)
    G = len(labs)
    V = G / (G - 1) * bread @ meat @ bread
    return coef[j], math.sqrt(V[j, j])


def _oracle_twoway(y, X, g1, g2):
    """Two-way CR1 by explicit loops: V = c1 V1 + c2 V2 - c12 V12."""
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    bread = np.linalg.inv(X.T @ X)

    def part(lab):
        labs = sorted(set(lab))
        M = np.zeros((X.shape[1], X.shape[1]))
        for v in labs:
            m = np.array([a == v for a in lab])
            s = X[m].T @ e[m]
            M += np.outer(s, s)
        G = len(labs)
        return G / (G - 1) * M

    inter = [f"{a}|{b}" for a, b in zip(g1.tolist(), g2.tolist())]
    V = bread @ (part(g1.tolist()) + part(g2.tolist()) - part(inter)) @ bread
    return beta, V


def _oracle_oneway(y, X, g):
    """One-way CR1 variance of OLS by explicit loops."""
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    labs = sorted(set(g.tolist()))
    M = np.zeros((X.shape[1], X.shape[1]))
    for v in labs:
        s = X[g == v].T @ e[g == v]
        M += np.outer(s, s)
    return bread @ (len(labs) / (len(labs) - 1) * M) @ bread


def _weibull_q(x, p):
    """Oracle for the (n + 1) p order statistic with linear interpolation between neighbours (written out)."""
    s = np.sort(np.asarray(x, float))
    h = (len(s) + 1) * p
    lo = int(math.floor(h))
    if lo < 1:
        return float(s[0])
    if lo >= len(s):
        return float(s[-1])
    return float(s[lo - 1] + (h - lo) * (s[lo] - s[lo - 1]))


def _rw_oracle(t, tstar):
    """Romano-Wolf step-down adjusted p-values written out from the definition (loops; all t finite)."""
    order = sorted(range(len(t)), key=lambda i: -t[i])
    B = tstar.shape[0]
    p, run = np.empty(len(t)), 0.0
    for r, i in enumerate(order):
        rest = order[r:]
        cnt = sum(1 for b in range(B) if max(tstar[b, s] for s in rest) >= t[i])
        run = max(run, (1 + cnt) / (B + 1))
        p[i] = min(run, 1.0)
    return p


# ============================================================================ selftest: checks

def _check_clusters(say):
    t = pd.to_datetime(["2021-01-30 23:00", "2021-02-01 01:00", "2021-02-10 12:00", "2021-03-31 10:00",
                        "2021-04-04 10:00", "2021-04-30 08:00", "2021-05-03 09:00", "2021-05-03 21:00",
                        "2021-06-28 00:00", "2021-07-01 00:00", "2021-07-03 00:00", "2021-07-06 00:00",
                        "2021-08-31 00:00", "2021-09-02 00:00", "2021-10-01 00:00"], utc=True)
    ep, tab = episodes(t)
    # day gaps: 2, 9, 49, 4, 26, 3, 0, 56, 3, 2, 3, 56, 2, 29
    assert ep.tolist() == [0, 0, 1, 2, 3, 4, 4, 4, 5, 5, 5, 5, 6, 6, 7], ep
    assert tab["n_fills"].tolist() == [2, 1, 1, 1, 3, 4, 2, 1] and tab["months"][0] == (202101, 202102)
    mb, mtab = month_blocks(t)
    # months: Jan+Feb merged (episode 0); Mar alone; Apr+May merged (episode 4); Jun+Jul merged (episode 5);
    # Aug+Sep merged (episode 6); Oct alone
    assert mb.tolist() == [0, 0, 0, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 5], mb
    assert mtab["label"].tolist() == ["2021-01+2021-02", "2021-03", "2021-04+2021-05", "2021-06+2021-07",
                                      "2021-08+2021-09", "2021-10"], mtab
    # a chain of fill days 3 days apart across three months merges all three
    t2 = pd.to_datetime(["2022-01-30", "2022-02-02", "2022-02-05", "2022-02-08", "2022-02-11", "2022-02-14",
                         "2022-02-17", "2022-02-20", "2022-02-23", "2022-02-26", "2022-03-01", "2022-04-15"])
    mb2, mt2 = month_blocks(t2)
    assert mb2.tolist() == [0] * 11 + [1] and mt2["label"][0] == "2022-01+2022-02+2022-03"
    qb, qt = quarter_blocks(pd.to_datetime(["2022-03-30", "2022-04-01", "2022-05-15", "2022-12-31", "2023-01-02"]))
    assert qb.tolist() == [0, 0, 0, 1, 1] and qt["label"].tolist() == ["2022Q1+2022Q2", "2022Q4+2023Q1"]
    # tz-aware and naive inputs agree; New York times convert to UTC days
    ny = pd.to_datetime(["2021-01-30 20:00"]).tz_localize("America/New_York")    # = 2021-01-31 01:00 UTC
    assert fill_days(ny)[0] == np.datetime64("2021-01-31") and month_key(ny)[0] == 202101
    may3 = pd.to_datetime(["2021-05-03"])
    assert quarter_key(may3)[0] == 20212 and year_key(may3)[0] == 2021
    wk = week_key(pd.to_datetime(["2020-01-06 03:29", "2020-01-06 03:30", "2020-01-13 03:29", "2020-01-13 03:30"]))
    assert wk.tolist() == [-1, 0, 0, 1], wk
    assert half_key(pd.to_datetime(["2022-12-31 23:59", "2023-01-01 00:00"])).tolist() == [0, 1]
    # G*
    assert abs(gstar([5, 5, 5, 5]) - 4) < 1e-12 and abs(gstar([7, 0, 0]) - 1) < 1e-12
    assert abs(gstar([10, 1, 1]) - (102 ** 2) / 10002) < 1e-12 and abs(eff_clusters([10, 1, 1]) - 144 / 102) < 1e-12
    assert abs(gstar(SIZES_58) - 12.398) < 1e-3 and abs(gstar_labels(np.repeat([3, 1, 2], [2, 2, 2])) - 3) < 1e-12
    say("  episodes (gap <= 3 days), month-blocks (transitive merges), quarter-blocks, week/half keys, G*: known "
        f"answers; the crash calendar has G = 58, G* = {gstar(SIZES_58):.1f}")


def _check_cr1_and_wild_exact(say):
    rng = np.random.default_rng(5)
    # hand example: clusters {0: [1, 2], 1: [3], 2: [4, 5, 6]}; mean 3.5
    y = np.array([1.0, 2, 3, 4, 5, 6])
    g = np.array([0, 0, 1, 2, 2, 2])
    r = cr1_mean(y, g)
    S = np.array([1 + 2 - 7, 3 - 3.5, 4 + 5 + 6 - 10.5])
    se_h = math.sqrt(3 / 2 * (S ** 2).sum()) / 6
    assert abs(r["mean"] - 3.5) < 1e-15 and abs(r["se"] - se_h) < 1e-14 and r["G"] == 3
    assert abs(r["gstar"] - (4 + 1 + 9) ** 2 / (16 + 1 + 81)) < 1e-12
    # weighted mean, FE regressions (straddling coin-weeks), intercept models: fast vs brute force
    cases = []
    n = 160
    cl = rng.integers(0, 9, n)
    cases.append(("mean", rng.standard_normal(n) + 0.3, None, cl, None, np.ones(n), 0))
    cases.append(("weighted mean", rng.standard_normal(n), None, cl, None, rng.uniform(0.2, 3, n), 0))
    fe = np.repeat(np.arange(40), 4)                            # 40 groups of 4 rows
    clf = (fe // 5).copy()                                      # FE nested in clusters (8 clusters) ...
    mv = np.isin(fe, [3, 11, 22, 37]) & (np.arange(n) % 4 >= 2)
    clf[mv] = (clf[mv] + 1) % 8                                 # ... except four groups that straddle two clusters
    X2 = np.column_stack([(np.arange(n) % 4 == 1).astype(float), rng.uniform(4, 14, n)])
    y2 = 0.4 * X2[:, 0] + 0.1 * X2[:, 1] + rng.standard_normal(40)[fe] + 0.5 * rng.standard_normal(n)
    cases.append(("FE, straddling, j=0", y2, X2, clf, fe, np.ones(n), 0))
    cases.append(("FE, straddling, weighted, j=1", y2, X2, clf, fe, rng.uniform(0.5, 2, n), 1))
    X3 = np.column_stack([np.ones(n), rng.standard_normal(n)])
    cases.append(("intercept + slope, j=1", X3[:, 1] * 0.2 + rng.standard_normal(n), X3, cl, None, np.ones(n), 1))
    worst = 0.0
    for name, yy, XX, cc, ff, ww, j in cases:
        Xa = np.ones((n, 1)) if XX is None else XX
        f = _prep(yy, Xa, cc, ff, ww)
        assert f["n"] == n and f["ident"]
        b_o, se_o = _oracle_cr1(yy, Xa, cc, ff, ww, j)
        assert abs(f["theta"][j] - b_o) < 1e-10 and abs(_cr1_se(f, j) - se_o) < 1e-10 * max(1, se_o), name
        Wd = webb_weights(40, f["G"], rng)
        # the fast engine indexes clusters by first appearance, the oracle by sorted label
        lab_sorted = sorted(set(cc.tolist()))
        Wo = np.empty_like(Wd)
        for gi, lab in enumerate(f["labels"]):
            Wo[:, lab_sorted.index(lab)] = Wd[:, gi]
        for restricted in (True, False):                # restricted: null theta_j = 0.1 imposed
            e = _restricted_resid(f, j, 0.1) if restricted else f["e"]
            fast = _boot_t(f, j, Wd, e)
            slow, _, _ = _oracle_wild(yy, Xa, j, cc, ff, ww, Wo, restricted, 0.1)
            d = float(np.max(np.abs(fast - slow)))
            worst = max(worst, d)
            assert d < 1e-8, (name, restricted, d)
    assert _prep(y2, X2, clf, fe, None)["strad"].sum() == 4
    # singletons are dropped under FE; a regressor constant within every FE group is not identified
    fe_s = np.r_[fe, [99]]
    f_s = _prep(np.r_[y2, 1.0], np.vstack([X2, [[1.0, 5.0]]]), np.r_[clf, 0], fe_s, None)
    assert f_s["n"] == n
    assert not ols_fe(y2, np.column_stack([fe % 2, X2[:, 1]]).astype(float), fe, clf)["ident"]
    say(f"  CR1 (G/(G-1)) hand example; fast exact wild bootstrap-t = brute-force dummy-variable re-estimation for "
        f"means, weighted means, FE models with straddling coin-weeks (restricted and unrestricted): max |diff| "
        f"{worst:.1e}")


def _rates(p, levels=K3_LEVELS):
    p = np.asarray(p, float)
    return {lv: float(np.mean(np.isfinite(p) & (p < lv))) for lv in levels}


def _size_ok(rate: float, n: int, lv: float, factor: float = K3_FACTOR) -> bool:
    """The K3 pass rule (Clopper-Pearson upper end <= factor x nominal) when n >= 2,000; with fewer replications
    (--quick) the rate may not exceed nominal by more than 3.5 binomial SEs."""
    if n >= 2000:
        return clopper_pearson(int(round(rate * n)), n)[1] <= factor * lv
    return rate <= lv + 3.5 * math.sqrt(lv * (1 - lv) / n)


def _check_size_mean(say, reps, n_jobs, B=B_BOOT):
    seeds = np.arange(reps) + 1000
    out = {}
    for kind, eff in (("balanced", 0.0), ("crash", 0.0), ("hetero", 0.0), ("crash", 0.06)):
        tasks = [(kind, seeds[i::n_jobs * 4].tolist(), B, eff) for i in range(n_jobs * 4)]
        res = [r for chunk in _run_tasks(_w_mean_size, tasks, n_jobs) for r in chunk]
        A = np.array(res, float)
        out[(kind, eff)] = A
        rw, rg, rd = _rates(A[:, 0]), _rates(A[:, 1]), _rates(A[:, 2])
        r1 = _rates(A[:, 6])
        if eff == 0:
            miss = float(np.mean(A[:, 3] < 0))
            cov = float(np.mean((A[:, 4] <= 0) & (A[:, 5] >= 0)))
            say(f"  {kind:8s} null, {reps} reps (G* {np.median(A[:, 9]):.1f}): false PASS at 1.67/2.5/5%: "
                f"p_decide {rd[K3_LEVELS[0]]:.4f}/{rd[0.025]:.4f}/{rd[0.05]:.4f}; p_WCR {rw[K3_LEVELS[0]]:.4f}/"
                f"{rw[0.025]:.4f}/{rw[0.05]:.4f}; p_G* {rg[K3_LEVELS[0]]:.4f}/{rg[0.025]:.4f}/{rg[0.05]:.4f}; "
                f"CR1 t(G-1) {r1[K3_LEVELS[0]]:.4f}/{r1[0.025]:.4f}/{r1[0.05]:.4f}; 98.33% bound misses {miss:.4f} "
                f"(nominal {1 - LEVEL_NOEDGE:.4f}); 95% interval covers {cov:.3f}")
            for lv in K3_LEVELS:
                assert _size_ok(rd[lv], reps, lv), (kind, lv, rd[lv])        # the K3 pass rule
            assert _size_ok(miss, reps, 1 - LEVEL_NOEDGE), (kind, miss)
            assert rd[0.05] >= 0.015, (kind, rd)                           # alive, not a p that is always 1
            assert cov >= 0.93, (kind, cov)
            if kind == "balanced":                                         # theory is clean here: WCR near nominal
                for lv in (K3_LEVELS[0], 0.05):
                    tol = 3.5 * math.sqrt(lv * (1 - lv) / reps)
                    assert abs(rw[lv] - lv) <= tol, (lv, rw[lv], tol)
        else:
            say(f"  crash, effect +6% per fill: P(p_decide < 1.67%) {rd[K3_LEVELS[0]]:.3f}, < 5% {rd[0.05]:.3f}; "
                f"mean estimate {A[:, 7].mean():+.4f}, mean SE {A[:, 8].mean():.4f}")
            assert rd[0.05] >= 0.5 and abs(A[:, 7].mean() - eff) < 4 * A[:, 7].std() / math.sqrt(reps)
    return out


def _check_h4(say, reps, n_jobs, B=B_BOOT):
    # (a) exactness of the H4 bootstrap with straddling coin-weeks (one method, brute force, 30 draws)
    rng = np.random.default_rng(77)
    meth = _dgp_h4(rng, frac=0.08, straddle=0.3)
    fr = meth["M6"]
    f = _prep(fr.y, np.column_stack([fr.real, fr.depth]), fr.cluster, fr.cw, None)
    assert f["strad"].sum() > 0
    keep = f["idx"]
    Wd = webb_weights(30, f["G"], rng)
    lab_sorted = sorted(set(fr.cluster.to_numpy()[keep].tolist()))
    Wo = np.empty_like(Wd)
    for gi, lab in enumerate(f["labels"]):
        Wo[:, lab_sorted.index(lab)] = Wd[:, gi]
    fast = _boot_t(f, 0, Wd, f["e"])
    slow, _, _ = _oracle_wild(fr.y.to_numpy()[keep], np.column_stack([fr.real, fr.depth])[keep], 0,
                              fr.cluster.to_numpy()[keep], fr.cw.to_numpy()[keep], np.ones(len(keep)), Wo, False, 0.0)
    d = float(np.max(np.abs(fast - slow)))
    assert d < 1e-8, d
    # depth_real-relative or absolute depth: identical b (the coin-week FE absorbs delta_real)
    h_abs = h4_fit(fr.drop(columns="depth_real"))
    h_rel = h4_fit(fr)
    assert abs(h_abs["b"] - h_rel["b"]) < 1e-10 and abs(h_abs["se"] - h_rel["se"]) < 1e-10
    # (b) a planted depth gradient (s = 1% per sigma) and no level effect: no false effect
    seeds = np.arange(reps) + 50000
    tasks = [(seeds[i::n_jobs * 4].tolist(), B, (0.0, 0.0, 0.0, 0.0), 0.01) for i in range(n_jobs * 4)]
    R0 = [r for chunk in _run_tasks(_w_h4, tasks, n_jobs) for r in chunk]
    assert len(R0) == reps
    b = np.array([r["b"] for r in R0])
    naive = np.array([r["naive"] for r in R0])
    pd_ = np.array([r["p_decide"] for r in R0])
    pw = np.array([r["p_wcr"] for r in R0])
    pg = np.array([r["p_gstar"] for r in R0])
    ubm = np.array([r["ubm"] for r in R0])
    miss_any = float(np.mean((ubm < 0).any(1)))              # a simultaneous bound misses if any method's does
    rd, rw, rg = _rates(pd_), _rates(pw), _rates(pg)
    mc = b.std(0) / math.sqrt(reps)
    say(f"  H4 null with a depth gradient of +1%/sigma, {reps} reps: mean b (FE + depth term) "
        + ", ".join(f"{m} {v:+.5f}" for m, v in zip(H4_METHODS, b.mean(0)))
        + f" (MC SE ~{mc.mean():.5f}); naive real-minus-placebo mean "
        + ", ".join(f"{v:+.4f}" for v in naive.mean(0)))
    say(f"    false PASS at 1.67/2.5/5%: p_decide {rd[K3_LEVELS[0]]:.4f}/{rd[0.025]:.4f}/{rd[0.05]:.4f}; RW max-t "
        f"{rw[K3_LEVELS[0]]:.4f}/{rw[0.025]:.4f}/{rw[0.05]:.4f}; 4 x t(G*-1) {rg[K3_LEVELS[0]]:.4f}/"
        f"{rg[0.025]:.4f}/{rg[0.05]:.4f}; simultaneous 98.33% bounds: some method's below its truth {miss_any:.4f} "
        f"(nominal {1 - LEVEL_NOEDGE:.4f}); median G* {np.median([r['gstar'][0] for r in R0]):.1f}, mean SE "
        f"{np.mean([r['se'] for r in R0]):.4f}, MDE {np.median([mde(r['se'][0], r['gstar'][0]) for r in R0]):.4f}")
    assert np.all(np.abs(b.mean(0)) < 4 * mc), (b.mean(0), mc)
    nmc = naive.std(0) / math.sqrt(reps)
    assert np.all(naive.mean(0) > 6 * nmc) and naive.mean() > 0.005, naive.mean(0)     # the bias the estimator removes
    for lv in K3_LEVELS:
        assert _size_ok(rd[lv], reps, lv), (lv, rd[lv])
        tol = 3.5 * math.sqrt(lv * (1 - lv) / reps)
        assert abs(rw[lv] - lv) <= tol, ("Romano-Wolf max-t size", lv, rw[lv], tol)
    assert _size_ok(miss_any, reps, 1 - LEVEL_NOEDGE), miss_any
    # (c) a planted level effect (+1.5% in M6 only) on top of the gradient: detected, unbiased, the right method,
    # and Romano-Wolf's family-wise error over the three null methods held
    reps_a = reps
    seeds = np.arange(reps_a) + 190000
    tasks = [(seeds[i::n_jobs * 4].tolist(), B, (0.0, 0.0, 0.015, 0.0), 0.01) for i in range(n_jobs * 4)]
    R1 = [r for chunk in _run_tasks(_w_h4, tasks, n_jobs) for r in chunk]
    b1 = np.array([r["b"] for r in R1])
    pd1 = np.array([r["p_decide"] for r in R1])
    am = np.mean([r["argmax"] == "M6" for r in R1])
    prw = np.array([r["p_rw"] for r in R1])
    fw = np.mean((prw[:, [0, 1, 3]] < 0.05).any(1))
    miss1 = np.mean((np.array([r["ubm"] for r in R1]) < np.array([0, 0, 0.015, 0])[None, :]).any(1))
    say(f"  H4 with +1.5% planted in M6 (and the gradient), {reps_a} reps: mean b_M6 {b1[:, 2].mean():+.4f}, others "
        + ", ".join(f"{v:+.4f}" for v in b1[:, [0, 1, 3]].mean(0)) + f"; argmax = M6 in {am:.3f}; P(p_decide < "
        f"1.67%) {np.mean(pd1 < K3_LEVELS[0]):.3f}, < 5% {np.mean(pd1 < 0.05):.3f}; Romano-Wolf: a null method "
        f"rejected at 5% in {fw:.4f}; simultaneous bounds miss {miss1:.4f}")
    mc1 = b1[:, 2].std() / math.sqrt(reps_a)
    assert abs(b1[:, 2].mean() - 0.015) < 4 * mc1 and am >= 0.9 and np.mean(pd1 < K3_LEVELS[0]) >= 0.6
    assert fw <= 0.05 + 3.5 * math.sqrt(0.05 * 0.95 / reps_a) and _size_ok(miss1, reps_a, 1 - LEVEL_NOEDGE)
    # Romano-Wolf algebra on a fixed draw matrix
    tst = np.array([[0.1, 2.5, 1.0], [3.0, 0.2, -1], [-0.5, 1.9, 0.4], [1.2, 1.2, 2.2]])
    p = romano_wolf([2.0, 1.5, np.nan], tst[:, :3])
    # step 1 (t 2.0, method 0): max over methods 0,1 per draw = [2.5, 3.0, 1.9, 1.2] -> #>=2.0: 2 -> 3/5
    # step 2 (t 1.5, method 1): draws of method 1 = [2.5, 0.2, 1.9, 1.2] -> #>=1.5: 2 -> 3/5, monotone 3/5
    assert np.allclose(p[:2], [0.6, 0.6]) and np.isnan(p[2]), p
    return R0


def _check_multiplicity(say):
    assert np.allclose(holm([0.01, 0.02, 0.04]), [0.03, 0.04, 0.04])
    assert np.allclose(holm([0.04, 0.01, 0.02]), [0.04, 0.03, 0.04])
    assert np.allclose(holm([0.02, 0.03, 0.04]), [0.06, 0.06, 0.06])
    assert np.allclose(holm([0.001, 0.5, np.nan]), [0.003, 1.0, 1.0])
    lv, rj = holm_levels([0.02, 0.01, 0.2])
    assert np.allclose(lv, [0.025, 0.05 / 3, 0.05]) and rj.tolist() == [True, True, False]
    lv, rj = holm_levels([0.02, 0.03, 0.04])
    assert np.allclose(lv, [0.05 / 3, 0.025, 0.05]) and not rj.any()
    lv, rj = holm_levels([0.01, 0.02, 0.04])
    assert rj.all() and np.allclose(holm([0.01, 0.02, 0.04]) < 0.05, rj)
    rng = np.random.default_rng(3)
    for _ in range(200):                     # Holm adjusted p < alpha  <=>  the step-down rejects
        p = rng.uniform(0, 0.08, 3)
        assert ((holm(p) < 0.05) == holm_levels(p)[1]).all()

    def bh_oracle(p):
        p = np.asarray(p, float)
        m = len(p)
        o = np.argsort(p)
        rank = np.empty(m, int)
        rank[o] = np.arange(1, m + 1)
        return np.array([min(1.0, min(m * p[k] / rank[k] for k in range(m) if p[k] >= p[i])) for i in range(m)])

    for _ in range(200):
        p = rng.uniform(0, 1, rng.integers(1, 9)) ** 2
        assert np.allclose(bh(p), bh_oracle(p))
    assert np.allclose(bh([0.01, 0.04, 0.03, 0.005]), [0.02, 0.04, 0.04, 0.02])
    assert np.isnan(bh([0.01, np.nan])[1]) and abs(bh([0.01, np.nan])[0] - 0.01) < 1e-15
    # the verdict truth table (E = 2%): p_holm, gates, ub -> verdict
    tbl = [(0.01, True, 0.05, "PASS"), (0.01, True, 0.01, "NO EDGE"), (0.01, False, 0.01, "NO EDGE"),
           (0.01, None, 0.05, "INCONCLUSIVE"), (0.01, {"halves": True, "F3": True}, 0.05, "PASS"),
           (0.01, {"halves": True, "F3": False}, 0.05, "INCONCLUSIVE"), (0.01, {}, 0.05, "INCONCLUSIVE"),
           (0.2, True, 0.019, "NO EDGE"), (0.2, True, 0.02, "INCONCLUSIVE"), (0.2, True, -0.001, "NO EDGE (HARMS)"),
           (0.2, True, 0.0, "NO EDGE"), (np.nan, True, 0.05, "INCONCLUSIVE"), (0.2, True, np.nan, "INCONCLUSIVE"),
           (0.05, True, 0.05, "INCONCLUSIVE"), (0.0499, True, 0.05, "PASS"), (0.2, False, -np.inf, "NO EDGE (HARMS)"),
           (0.01, np.bool_(True), 0.05, "PASS"), (0.01, np.nan, 0.05, "INCONCLUSIVE")]
    for p, g, ub, want in tbl:
        got = verdict(p, g, ub, 0.02)
        assert got == want, (p, g, ub, got, want)
    # family: Holm over three, report order, PASS-and-NO-EDGE flag, missing gates
    rows = {"H1": dict(p_decide=0.004, ub=0.03, estimate=0.012, se=0.004, ci95=(0.004, 0.02), gstar=12, G=58,
                       unit="month-block", mde=0.013),
            "H2R": dict(p_decide=0.30, ub=-0.004, estimate=-0.02, se=0.01, gstar=12, G=58, mde=0.04),
            "H4": dict(p_decide=0.02, ub=0.03, estimate=0.01, se=0.004, gstar=10, G=55, argmax="M6", mde=0.014)}
    fv = family_verdicts(rows, gates={"H1": {"halves": True, "F3": True}, "H4": True})
    assert fv["test"].tolist() == ["H2R", "H1", "H4"]
    v = dict(zip(fv["test"], fv["verdict"]))
    ph = dict(zip(fv["test"], fv["p_holm"]))
    assert v == {"H2R": "NO EDGE (HARMS)", "H1": "NO EDGE", "H4": "PASS"}, v     # H1: Holm p 0.012, bound 3% < E
    assert abs(ph["H1"] - 0.012) < 1e-12 and abs(ph["H4"] - 0.04) < 1e-12 and abs(ph["H2R"] - 0.3) < 1e-12
    fvi = fv.set_index("test")
    assert bool(fvi.loc["H1", "pass_and_noedge"]) and not fvi.loc["H2R", "gates_given"]
    assert not bool(fvi.loc["H4", "pass_and_noedge"]) and not bool(fvi.loc["H2R", "pass_and_noedge"])
    assert abs(fv.set_index("test").loc["H4", "holm_level"] - 0.025) < 1e-12
    # E and MDE
    assert abs(e_h1() - 0.03745) < 5e-5 and abs(e_h1(r_res=R_RES_GOLD) - 0.02263) < 5e-5
    assert E["H1"] == 0.0375 and E["H2R"] == 0.02 and E["H4"] == 0.01 and E_SENS["H1_gold"] == 0.0226
    m_big = mde(0.01, 1e7)
    assert abs(m_big - (stats.norm.ppf(1 - 0.05 / 3) + stats.norm.ppf(0.8)) * 0.01) < 1e-6
    assert abs(mde(0.01, 12.4) - (stats.t.ppf(1 - 0.05 / 3, 11.4) + stats.t.ppf(0.8, 11.4)) * 0.01) < 1e-15
    assert np.isnan(mde(0.01, 1.0))
    # gates helpers
    yv = np.array([1.0, 1, 1, 5, 5, -10, 2, 2])
    gv = np.array([0, 0, 0, 1, 1, 2, 3, 3])
    assert drop_worst_group_mean(yv, gv) == drop_worst(yv, gv)
    m_after, gbig = drop_biggest_group_mean(yv, gv)
    assert gbig == 0 and abs(m_after - (5 + 5 - 10 + 2 + 2) / 5) < 1e-15
    ts = top_k_share(yv, gv, k=2)        # largest by count: group 0 (3 fills), then group 1 (ties broken by label)
    assert ts["groups"] == [0, 1] and abs(ts["share"] - 13 / 7) < 1e-12 and abs(ts["mean_without"] - (-6 / 3)) < 1e-12
    say("  Holm (3 tests) and its step levels, BH vs a brute-force oracle, the verdict truth table (PASS / NO EDGE / "
        "NO EDGE (HARMS) / INCONCLUSIVE), family ordering and flags, E_H1 = 3.75% (formula 3.745%), MDE, gate helpers")


def _check_twoway_im(say, reps):
    rng = np.random.default_rng(11)
    n = 300
    g1 = rng.integers(0, 12, n)
    g2 = rng.integers(0, 9, n)
    X = np.column_stack([np.ones(n), rng.standard_normal(n), (g1 % 2).astype(float)])
    y = X @ np.array([0.1, 0.3, -0.2]) + rng.standard_normal(12)[g1] + rng.standard_normal(9)[g2] \
        + rng.standard_normal(n)
    r = ols_cluster2(y, X, g1, g2)
    b_o, V_o = _oracle_twoway(y, X, g1, g2)
    assert np.allclose(r["V_raw"], V_o, rtol=1e-10, atol=1e-15) and np.allclose(r["beta"], b_o, rtol=1e-12)
    if np.linalg.eigvalsh(V_o).min() >= 0:
        assert np.allclose(r["se"], np.sqrt(np.diag(V_o)), rtol=1e-10) and not r["psd_fixed"]
    assert r["df"] == min(12, 9) - 1
    # a V that is not positive semidefinite is fixed by zeroing its negative eigenvalues
    Vn = np.array([[1.0, 2.0], [2.0, 1.0]])
    lam_, vec_ = np.linalg.eigh(Vn)
    assert np.all(np.linalg.eigvalsh(vec_ @ np.diag(np.maximum(lam_, 0)) @ vec_.T) > -1e-12)
    r_same = ols_cluster2(y, X, g1, g1)
    one = ols_fe(y, X, None, g1)
    assert np.allclose(r_same["se"], one["se"], rtol=1e-10)
    # size: a coin-level regressor with coin and quarter shocks (30 coins x 24 quarters)
    rej = {"two-way": 0, "quarter only": 0, "coin only": 0}
    for _ in range(reps):
        nc, nq = 30, 24
        coin = rng.integers(0, nc, 1500)
        q = rng.integers(0, nq, 1500)
        notq = (coin < 12).astype(float)
        p0 = 0.1 + 0.05 * rng.standard_normal(nc)[coin]
        yy = 0.3 * rng.standard_normal(nc)[coin] + 0.3 * rng.standard_normal(nq)[q] + 0.4 * p0 \
            + rng.standard_normal(1500)
        XX = np.column_stack([np.ones(1500), notq, p0])
        rej["two-way"] += ols_cluster2(yy, XX, coin, q)["p"][1] < 0.05
        rq = ols_fe(yy, XX, None, q)
        rej["quarter only"] += _tsf(rq["t"][1], rq["G"] - 1) < 0.05
        rc = ols_fe(yy, XX, None, coin)
        rej["coin only"] += _tsf(rc["t"][1], rc["G"] - 1) < 0.05
    rates = {k: v / reps for k, v in rej.items()}
    assert rates["two-way"] <= 0.09 and rates["quarter only"] > rates["two-way"], rates
    # Ibragimov-Müller vs scipy, and its size with heterogeneous group variances
    est = np.array([0.02, -0.01, 0.05, 0.03, 0.00, 0.04])
    im = ibragimov_muller(est)
    ref = stats.ttest_1samp(est, 0.0, alternative="greater")
    assert abs(im["t"] - ref.statistic) < 1e-12 and abs(im["p"] - ref.pvalue) < 1e-12 and im["df"] == 5
    sz = np.mean([ibragimov_muller(rng.standard_normal(6) * np.array([0.5, 1, 2, 4, 1, 0.3]))["p"] < 0.05
                  for _ in range(4000)])
    assert sz <= 0.065, sz
    yy = rng.standard_normal(600)
    gg = np.repeat(np.arange(6), 100)
    XX = np.column_stack([np.ones(600), rng.integers(0, 2, 600)])
    imo = im_ols(yy, XX, gg, j=1)
    direct = [np.linalg.lstsq(XX[gg == k], yy[gg == k], rcond=None)[0][1] for k in range(6)]
    assert np.allclose(list(imo["estimates"].values()), direct) and imo["q"] == 6
    # D-H5 pieces: p0 known answers (S5: 18% at 57% a year, 40% at 96%), design and fit run
    assert abs(p0_knife(0.57 / math.sqrt(365)) - 0.176) < 0.002 and abs(p0_knife(0.96 / math.sqrt(365)) - 0.404) < 0.002
    nn = 800
    coin = rng.integers(0, 40, nn)
    sig = rng.uniform(0.02, 0.08, nn)
    notq_ = (coin >= 25).astype(float)
    kn = (rng.random(nn) < p0_knife(sig)).astype(float)
    rung_ = rng.choice([6, 8, 10], nn)
    qtr = rng.integers(0, 20, nn)
    fit = dh5_fit(kn, notq_, rung_, sig, coin, qtr)
    assert np.isfinite(fit["b"]) and fit["names"][:2] == ["const", "notQ"] and fit["df"] == min(40, 20) - 1
    b_drop, c_drop = dh5_drop_worst_coin(kn, notq_, rung_, sig, coin, qtr)
    direct = {c: dh5_fit(kn[coin != c], notq_[coin != c], rung_[coin != c], sig[coin != c], coin[coin != c],
                         qtr[coin != c])["b"] for c in np.unique(coin)}
    assert c_drop == min(direct, key=direct.get) and abs(b_drop - min(direct.values())) < 1e-15
    assert decile_dummies(np.arange(100.0)).sum(0).tolist() == [10.0] * 9
    say(f"  two-way CR1 = explicit-loop oracle and = one-way when g1 = g2; size of a coin-level regressor at 5% "
        f"({reps} reps): two-way {rates['two-way']:.3f}, quarter-only {rates['quarter only']:.3f}, coin-only "
        f"{rates['coin only']:.3f}; Ibragimov-Müller = scipy t-test, size {sz:.3f} with unequal variances; p0 "
        "known answers")


def _check_km(say):
    t = np.array([1, 2, 2, 3, 4, 4, 5, 6, 8, 9], float)
    e = np.array([1, 1, 0, 1, 0, 1, 1, 0, 1, 0], bool)

    def oracle(tau):
        # product-limit and restricted mean in exact fractions, written out from the definition
        times = sorted(set(t[e].tolist()))
        S, pts = Fraction(1), []
        for u in times:
            nr = sum(1 for x in t if x >= u)
            d = sum(1 for x, ev in zip(t, e) if x == u and ev)
            S *= Fraction(nr - d, nr)
            pts.append((u, S, nr, d))
        area, prev_t, prev_S = Fraction(0), Fraction(0), Fraction(1)
        for u, s_, _, _ in pts:
            if u > tau:
                break
            area += prev_S * (Fraction(u) - prev_t)
            prev_t, prev_S = Fraction(u), s_
        area += prev_S * (Fraction(tau) - prev_t)
        return pts, area

    pts, area = oracle(7)
    assert [p[1] for p in pts] == [Fraction(9, 10), Fraction(8, 10), Fraction(24, 35), Fraction(4, 7), Fraction(3, 7),
                                   Fraction(3, 14)]
    assert area == Fraction(337, 70)
    rm, rse = km_restricted_mean(t, e, 7)
    assert abs(rm - 337 / 70) < 1e-12
    # SE of the restricted mean, written out: A_i = integral of S from t_i to 7
    A = {1: Fraction(337, 70) - 1, 2: Fraction(337, 70) - 1 - Fraction(9, 10),
         3: Fraction(337, 70) - 1 - Fraction(9, 10) - Fraction(8, 10),
         4: Fraction(4, 7) + Fraction(6, 7), 5: Fraction(6, 7)}
    var = sum(A[u] ** 2 * Fraction(d, nr * (nr - d)) for u, _, nr, d in pts if u <= 7)
    assert abs(rse - math.sqrt(var)) < 1e-12
    s = km_survival(t, e, [0.5, 1, 4.5, 8, 100])
    assert np.allclose(s, [1, 0.9, 4 / 7, 3 / 14, 3 / 14])
    assert km_median(t, e) == 5.0
    tab = kaplan_meier(t, e)
    gw = (3 / 7) ** 2 * (1 / 90 + 1 / 72 + 1 / 42 + 1 / 30 + 1 / 12)
    assert abs(tab.loc[tab.time == 5, "var"].iloc[0] - gw) < 1e-12
    ws = waiting_summary(t, e, 7)
    assert abs(ws["W"] - 337 / 70 / 7) < 1e-12 and abs(ws["F"] - 4 / 7) < 1e-12 and ws["events"] == 6
    # exponential waits, no censoring: restricted mean = (1 - exp(-lam tau)) / lam
    rng = np.random.default_rng(2)
    x = rng.exponential(1 / 0.01, 20000)
    rm2, se2 = km_restricted_mean(x, np.ones_like(x, bool), 365)
    assert abs(rm2 - (1 - math.exp(-3.65)) / 0.01) < 4 * se2
    # D6 break-even: theta = 4% at the critique's W and F gives 19%, 10% and 6% a year
    mus = [mu_star(F, 0.04, W)["mu_star"] for F, W in ((0.997, 0.21), (0.93, 0.37), (0.78, 0.52))]
    assert np.allclose(mus, [0.19, 0.1005, 0.06], atol=0.001)
    say("  Kaplan-Meier: S, Greenwood, restricted mean (337/70) and its SE against a hand computation in fractions; "
        "median; S(365); exponential check; mu* = F theta / W (19%/10%/6% at theta = 4%)")


def _check_phi_wilson(say):
    r = overdispersion_phi([10, 30, 50, 20], [500, 500, 500, 500])
    chi = 875 / (500 * 0.055 * 0.945)
    assert abs(r["chi2"] - chi) < 1e-9 and abs(r["phi"] - chi / 3) < 1e-9 and r["df"] == 3
    rng = np.random.default_rng(4)
    ph = [overdispersion_phi(rng.binomial(600, 0.03, 7), np.full(7, 600))["phi"] for _ in range(3000)]
    assert 0.9 < np.mean(ph) < 1.1, np.mean(ph)
    pb = rng.beta(2, 60, (3000, 7))
    ph2 = [overdispersion_phi(rng.binomial(600, pp), np.full(7, 600))["phi"] for pp in pb]
    assert np.mean(ph2) > 3
    lo, hi, c = wilson(5, 215)
    assert abs(lo - 0.00997) < 5e-5 and abs(hi - 0.05328) < 5e-5        # NEAR: 5 fills in 215 bid-weeks, 1.0-5.3%
    lo4, hi4, c4 = wilson(5, 215, phi=4.0)
    assert abs((hi4 - c4) - 2 * (hi - c)) < 1e-12 and lo4 == 0.0
    assert wilson(5, 215, phi=0.5)[:2] == wilson(5, 215)[:2]
    say("  phi: Pearson dispersion hand example (11.2 on 3 df), ~1 for binomial years, >3 for beta-binomial; Wilson "
        "1.0-5.3% for 5 fills in 215 weeks; widening by sqrt(phi), never narrowing")


def _check_bootstraps(say, reps):
    rng = np.random.default_rng(8)
    idx, blk = sb_indices(20000, 6.0, 1, rng)
    runs = np.bincount(blk[0])
    assert 5.5 < runs.mean() < 6.5
    runs12 = np.bincount(sb_indices(40000, 12.0, 1, rng)[1][0])
    assert 11.0 < runs12.mean() < 13.0                                   # the 12-month sensitivity block
    x = rng.normal(0.01, 0.05, 84)
    r0 = stationary_bootstrap(x, x - 0.002, stat="mean", B=999, seed=1)
    assert abs(r0["estimate"] - 0.002) < 1e-15 and r0["se"] < 1e-12
    c = np.full(24, 0.01)
    rc = stationary_bootstrap(c, None, stat="cagr", B=199, seed=1)
    assert abs(rc["estimate"] - (1.01 ** 12 - 1)) < 1e-12
    assert stationary_bootstrap(np.r_[c, -1.0], stat="cagr", B=99)["estimate"] == -1.0
    sh = stationary_bootstrap(x, stat="sharpe", B=199)
    assert abs(sh["estimate"] - x.mean() / x.std(ddof=1) * math.sqrt(12)) < 1e-12
    # i.i.d. months: the bootstrap SE of the mean matches sd / sqrt(T); AR(1) months (phi 0.3, T 84): the block
    # bootstrap's known small-sample shortfall is reported (coverage and SE against the long-run SE)
    r_iid = []
    for _ in range(reps):
        xx = rng.standard_normal(84)
        r_iid.append(stationary_bootstrap(xx, stat="mean", mean_block=6, B=999, seed=rng)["se"] / (1 / math.sqrt(84)))
    assert 0.9 < np.mean(r_iid) < 1.05, np.mean(r_iid)
    cover, ratio = 0, []
    for _ in range(reps):
        e = rng.standard_normal(200)
        z = np.zeros(200)
        for t_ in range(1, 200):
            z[t_] = 0.3 * z[t_ - 1] + e[t_]
        xx = 0.05 * z[-84:]
        rb = stationary_bootstrap(xx, stat="mean", mean_block=6, B=499, seed=rng)
        cover += rb["ci"][0] <= 0 <= rb["ci"][1]
        ratio.append(rb["se"] / (0.05 / math.sqrt(1 - 0.09) * math.sqrt((1 + 0.3) / (1 - 0.3)) / math.sqrt(84)))
    assert cover / reps >= 0.8 and 0.7 < np.mean(ratio) < 1.05, (cover / reps, np.mean(ratio))
    # episode-cluster bootstrap: ratio of sums, coverage of the true ratio, and the general slow path agrees
    cov_r = 0
    for _ in range(reps):
        G = 40
        sz = rng.integers(1, 30, G)
        g = np.repeat(np.arange(G), sz)
        pred = rng.uniform(0.01, 0.1, len(g))
        real = rng.binomial(1, np.clip(pred * np.exp(0.5 * rng.standard_normal(G)[g] - 0.125), 0, 1)).astype(float)
        rr = ratio_cluster_bootstrap(real, pred, g, B=499, seed=rng, level=0.90)
        cov_r += rr["ci"][0] <= 1.0 <= rr["ci"][1]
    assert cov_r / reps >= 0.8, cov_r / reps
    g = np.repeat(np.arange(15), 4)
    num = rng.standard_normal(60)
    den = np.ones(60)
    fast = ratio_cluster_bootstrap(num, den, g, B=3000, seed=9)
    slow = cluster_bootstrap(lambda a, b: a.sum() / b.sum(), [num, den], g, B=3000, seed=10)
    assert abs(fast["estimate"] - slow["estimate"]) < 1e-12 and abs(fast["se"] - slow["se"]) < 0.15 * slow["se"]
    # D5 logic: calibrated iff both halves' 90% intervals overlap [0.67, 1.5]
    h = np.repeat([0, 1], 300)
    gg = np.repeat(np.arange(60), 10)
    pred = np.full(600, 0.05)
    real = np.zeros(600)
    real[rng.choice(300, 15, replace=False)] = 1                       # half 0: ratio 1.0
    real[300 + rng.choice(300, 45, replace=False)] = 1                 # half 1: ratio 3.0
    d5 = d5_calibration(real, pred, gg, h, B=999)
    assert d5["0"]["overlaps"] and not d5["calibrated"] and abs(d5["1"]["ratio"] - 3.0) < 1e-12
    say(f"  stationary bootstrap: mean block {runs.mean():.2f} (6 asked), {runs12.mean():.2f} (12 asked); paired "
        f"difference exact; CAGR/Sharpe known "
        f"values; i.i.d. SE ratio {np.mean(r_iid):.3f}; AR(1, 0.3) 95% coverage {cover / reps:.3f}, SE ratio "
        f"{np.mean(ratio):.2f} (block-bootstrap shortfall at T = 84); episode-cluster bootstrap 90% coverage "
        f"{cov_r / reps:.3f}, fast = general path; D5 rule")


def _check_k3(say, reps, n_jobs, B):
    calib = inference_calibration(_toy_k3_sim, n_reps=reps, scenarios=("base", "high", "fine"), B=B, n_jobs=n_jobs,
                                  seed=31)
    t1 = calib["tests"]["H1"]
    fine = t1["by_scenario"]["fine"]["false_pass"]
    say(f"  K3 toy ({reps} reps x 3 scenarios, B {B}, {calib['seconds']:.0f}s): H1 false PASS at 5% base "
        f"{t1['by_scenario']['base']['false_pass']['0.0500']['rate']:.3f}, 'fine' (clusters split, dependence "
        f"hidden) {fine['0.0500']['rate']:.3f} -> K3 pass {t1['k3_pass']}; H2R pass {calib['tests']['H2R']['k3_pass']};"
        f" H4 pass {calib['tests']['H4']['k3_pass']} (5% rate base "
        f"{calib['tests']['H4']['by_scenario']['base']['false_pass']['0.0500']['rate']:.3f})")
    assert not t1["k3_pass"] and t1["needs_calibration"] and t1["rule"] == "simulation-calibrated"
    assert t1["worst_scenario"] == "fine"
    assert not calib["all_pass"] and len(calib["null"]["H1"]["base"]["total"]) == reps
    if reps >= 2000:      # fewer replications cannot pass a correctly sized test reliably at the 1.67% level
        assert calib["tests"]["H2R"]["k3_pass"] and calib["tests"]["H4"]["k3_pass"]
    for test in ("H1", "H2R", "H4"):
        for sc in ("base", "high", "fine"):
            d = calib["tests"][test]["by_scenario"][sc]
            assert d["n"] == reps and np.isfinite(d["mde_formula"]) and np.isfinite(d["pivot_q"])
    # the calibrated p restores the level on fresh replications of the worst scenario; the bound covers
    rej, miss, n_f = 0, 0, max(300, reps)
    for rep in range(n_f):
        rng = np.random.default_rng(np.random.SeedSequence([999, rep]))
        d = _toy_k3_sim("fine", rep, rng)["H1"]
        r = test_mean(d["y"], d["clusters"], B=199, seed=rng)
        rc = apply_calibration(dict(r), "H1", calib)
        rej += rc["p_decide"] < 0.05
        miss += rc["ub"] < 0
        assert rc["calibrated"] and rc["p_decide_nominal"] == r["p_decide"]
        assert rc["ub"] >= r["ub"] and rc["ub"] == max(r["ub"], rc["ub_calibrated"])        # widened, never narrowed
    ci = clopper_pearson(rej, n_f)
    say(f"    simulation-calibrated p on {n_f} fresh 'fine' replications: P(p < 5%) {rej / n_f:.3f} (95% CI "
        f"{ci[0]:.3f}-{ci[1]:.3f}); calibrated 98.33% bound misses {miss / n_f:.3f}")
    assert ci[0] <= 0.05 * K3_FACTOR and ci[1] >= 0.02 and miss / n_f <= 0.05
    # calibrated_p and the bound by hand on a tiny calibration object
    nul = {"a": dict(stat=[0, 1, 2, 3], pivot=[-3, -1, 0, 1]), "b": dict(stat=[0, 0, 0, 5], pivot=[-1, 0, 0, 1])}
    cal = dict(level_noedge=0.9, null={"H1": nul, "H4": nul})
    assert calibrated_p("H1", 2.5, cal) == 2 / 5                      # max over scenarios of (1 + #)/(n + 1)
    q_a = _q(np.array([-3, -1, 0, 1.0]), 0.1)
    assert abs(calibrated_bound("H1", 0.01, 0.02, cal) - (0.01 - q_a * 0.02)) < 1e-15
    assert abs(calibrated_bound("H4", [0.01, 0.03], [0.02, 0.01], cal) - max(0.01 - q_a * 0.02, 0.03 - q_a * 0.01)) \
        < 1e-15
    dd = d11_percentile(0.0, calib)
    assert set(dd) == {"base", "high", "fine"} and all(0 < v["p_upper"] <= 1 for v in dd.values())
    js = json.dumps(calib)
    assert len(js) > 1000
    return calib


def _check_api(say):
    rng = np.random.default_rng(21)
    meth = _dgp_h4(rng, frac=0.3)
    # fill times: each coin-week's fills on one day inside its month-block's month; a time-only call must equal a call
    # with month_blocks() computed on the union of the stacked fill times
    month0 = np.datetime64("2020-01-15T12:00:00", "ns")
    framed, union_t = {}, []
    for nm, fr in meth.items():
        tt = month0 + (fr["cluster"].to_numpy() * 61).astype("timedelta64[D]") \
            + (fr["cw"].to_numpy() % 5).astype("timedelta64[D]")
        framed[nm] = fr.drop(columns="cluster").assign(time=tt)
        union_t.append(tt)
    r_time = test_h4(framed, B=999, seed=5)
    ids = month_blocks(np.concatenate(union_t))[0]
    pos, man = 0, {}
    for nm, fr in framed.items():
        man[nm] = fr.assign(cluster=ids[pos:pos + len(fr)])
        pos += len(fr)
    r_man = test_h4(man, B=999, seed=5)
    assert np.allclose(r_time["methods"]["t"], r_man["methods"]["t"]) and r_time["p_wcr"] == r_man["p_wcr"]
    # an empty method still counts in the Bonferroni multiplier
    m3 = dict(meth)
    m3["M7"] = meth["M7"].iloc[0:0]
    r3 = test_h4(m3, B=999, seed=5)
    assert r3["n_bonf"] == 4 and np.isnan(r3["methods"].set_index("method").loc["M7", "t"])
    assert np.isnan(r3["methods"].set_index("method").loc["M7", "p_rw"]) and np.isfinite(r3["p_decide"])
    assert np.isnan(r3["ub"]) and not r3["noedge"] and r3["unbounded"] == ["M7"]      # ... and leaves H4 unbounded
    # the worst-block gate equals a direct loop over blocks (the frame's `cluster` column is test_h4's partition)
    fr = meth["M4"]
    b_after, blk = h4_drop_worst_block(fr)
    direct = {c: h4_fit(fr, mask=fr["cluster"].to_numpy() != c)["b"] for c in pd.unique(fr["cluster"])}
    assert blk == min(direct, key=direct.get) and abs(b_after - min(direct.values())) < 1e-15
    assert h4_fit(fr, mask=fr["cluster"].to_numpy() >= 0)["b"] == h4_fit(fr)["b"]
    # test_coef with fixed effects (D-H3 style, episode FE) agrees with ols_fe; describe() has no p-values
    n = 500
    ep = rng.integers(0, 40, n)
    fast = rng.integers(0, 2, n).astype(float)
    rung = rng.choice([6.0, 8.0, 10.0], n)
    X = np.column_stack([fast, rung == 8, rung == 10]).astype(float)
    yv = 0.01 * fast + rng.standard_normal(40)[ep] * 0.02 + 0.03 * rng.standard_normal(n)
    mb = ep // 3
    tc = test_coef(yv, X, 0, mb, fe=ep, B=999, seed=1, E_=0.02, return_draws=True)
    of = ols_fe(yv, X, ep, mb)
    assert abs(tc["estimate"] - of["coef"][0]) < 1e-14 and abs(tc["se"] - of["se"][0]) < 1e-14
    assert 0 < tc["p_decide"] <= 1 and tc["ci95"][0] < tc["estimate"] < tc["ci95"][1]
    # the bound is max(bootstrap-t bound, t(G*-1) bound), each computed from its own definition
    assert abs(tc["ub_t"] - (tc["estimate"] + stats.t.ppf(1 - ALPHA_B, of["gstar"] - 1) * tc["se"])) < 1e-14
    assert abs(tc["ub_boot"] - (tc["estimate"] - _weibull_q(tc["tstar_unrestricted"], ALPHA_B) * tc["se"])) < 1e-14
    assert tc["ub"] == max(tc["ub_boot"], tc["ub_t"])
    assert abs(tc["p_gstar"] - stats.t.sf(tc["t"], of["gstar"] - 1)) < 1e-14
    ds = describe(yv, mb, X, 0, fe=ep, B=999)
    assert "p_decide" not in ds and "ub" not in ds and abs(ds["estimate"] - tc["estimate"]) < 1e-15
    t_hat, ts, f = wild_t(yv, X, 0, mb, fe=ep, B=199, seed=3)
    assert len(ts) == 199 and np.isfinite(t_hat) and f["G"] == len(np.unique(mb))
    # family verdicts on real outputs, and an H4 row through apply_calibration
    h1 = test_mean(rng.standard_normal(300) * 0.05 + 0.02, rng.integers(0, 30, 300), E_=E["H1"], B=999)
    h2 = test_mean(rng.standard_normal(300) * 0.02, rng.integers(0, 30, 300), E_=E["H2R"], B=999)
    h4 = test_h4(meth, B=999)
    fv = family_verdicts({"H1": h1, "H2R": h2, "H4": h4}, gates={"H1": True, "H2R": True, "H4": True})
    assert np.allclose(fv.set_index("test").loc[list(FAMILY), "p_holm"],
                       holm([h1["p_decide"], h2["p_decide"], h4["p_decide"]]))
    cal = dict(level_noedge=LEVEL_NOEDGE, tests={"H4": dict(needs_calibration=True)},
               null={"H4": {"x": dict(stat=list(rng.standard_normal(999) + 1.5),
                                      pivot=list(rng.standard_normal(999)))}})
    h4c = apply_calibration(h4, "H4", cal)
    assert h4c["calibrated"] and h4c["p_decide_nominal"] == h4["p_decide"]
    assert abs(h4c["p_decide"] - calibrated_p("H4", h4["T"], cal)) < 1e-15
    tab = h4["methods"]
    assert np.allclose(tab["p_method"], np.fmax(tab["p_rw"], tab["p_bonf"]), equal_nan=True)
    assert abs(tab.set_index("method").loc[h4["argmax"], "p_method"] - h4["p_decide"]) < 1e-15
    # labels given as (coin, week) pairs; missing fill times are refused
    assert _codes(np.array([[1, 2], [1, 3], [1, 2]]))[0].tolist() == [0, 1, 0]
    assert gstar_labels(list(zip(["A", "A", "B"], [1, 1, 1]))) == gstar([2, 1])
    try:
        episodes(pd.to_datetime(["2021-01-01", None]))
        raise AssertionError("NaT accepted")
    except ValueError:
        pass
    say("  test_h4 from fill times = with explicit month-blocks; an empty method keeps n_bonf = 4; worst-block gate = "
        "direct loop; test_coef with FE = ols_fe; describe() has no p; wild_t; family_verdicts on real rows; "
        "apply_calibration on H4")


def _check_known_answers(say):
    """The decisive formulas of §10.2/§10.3 against hand computations on small fixed examples (exact; --quick too):
    test_mean (H1/H2R), test_coef with fixed effects (D-H3's shape) and test_h4 (H4)."""
    a = ALPHA_B
    # (a) test_mean: G = 6 unequal clusters (G* != G), B = 999; this example has the all-ones multiplier draw, which
    # reproduces the sample, so it also pins the tie convention of p_WCR
    rng = np.random.default_rng(3)
    sizes = np.array([7, 3, 1, 1, 5, 2])
    G = len(sizes)
    g = np.repeat(np.arange(G), sizes)
    y = 0.02 + 0.05 * rng.standard_normal(len(g))
    B = 999
    r = test_mean(y, g, E_=E["H1"], B=B, seed=1, return_draws=True)
    n, m = len(y), y.mean()

    def t_of(ys, centre):
        mb = ys.mean()
        s = np.array([(ys[g == k] - mb).sum() for k in range(G)])
        return (mb - centre) / (math.sqrt(G / (G - 1) * (s ** 2).sum()) / n)

    se = math.sqrt(G / (G - 1) * sum((y[g == k] - m).sum() ** 2 for k in range(G))) / n
    gs = float((sizes ** 2).sum() ** 2 / (sizes ** 4).sum())
    t = m / se
    assert abs(gs - G) > 1 and abs(r["estimate"] - m) < 1e-15 and abs(r["se"] - se) < 1e-15 and abs(r["t"] - t) < 1e-12
    assert abs(r["gstar"] - gs) < 1e-12 and abs(r["df"] - (gs - 1)) < 1e-12
    assert abs(r["p_gstar"] - stats.t.sf(t, gs - 1)) < 1e-14                                 # S2: t(G* - 1)
    assert abs(r["ub_t"] - (m + stats.t.ppf(1 - a, gs - 1) * se)) < 1e-14                   # at 1 - 0.05/3
    assert abs(r["mde"] - (stats.t.ppf(1 - a, gs - 1) + stats.t.ppf(0.8, gs - 1)) * se) < 1e-14
    W = WEBB[np.random.default_rng(1).integers(0, 6, size=(B, G))]          # the multipliers webb_weights draws
    tr = np.array([t_of(W[b, g] * y, 0.0) for b in range(B)])               # null 0 imposed
    tu = np.array([t_of(m + W[b, g] * (y - m), m) for b in range(B)])       # unrestricted, recentred
    assert np.allclose(r["tstar_restricted"], tr, rtol=1e-10, atol=1e-12)
    assert np.allclose(r["tstar_unrestricted"], tu, rtol=1e-10, atol=1e-12)
    ties = int(np.sum(np.abs(tr - t) <= 1e-12))
    p_w = (1 + np.sum(tr >= t - 1e-12)) / (B + 1)
    assert ties >= 1 and abs(r["p_wcr"] - p_w) < 1e-15, (ties, r["p_wcr"], p_w)
    assert abs(r["p_decide"] - max(p_w, stats.t.sf(t, gs - 1))) < 1e-15
    ub_boot = m - _weibull_q(tu, a) * se
    assert abs(r["ub_boot"] - ub_boot) < 1e-14 and abs(r["ub"] - max(ub_boot, r["ub_t"])) < 1e-15
    q975 = stats.t.ppf(0.975, gs - 1)
    ci_t = (m - q975 * se, m + q975 * se)
    ci_b = (m - _weibull_q(tu, 0.975) * se, m - _weibull_q(tu, 0.025) * se)
    assert np.allclose(r["ci95_t"], ci_t, rtol=0, atol=1e-14) and np.allclose(r["ci95_boot"], ci_b, rtol=0, atol=1e-14)
    assert np.allclose(r["ci95"], (min(ci_t[0], ci_b[0]), max(ci_t[1], ci_b[1])), rtol=0, atol=1e-14)
    assert r["noedge"] == (r["ub"] < E["H1"]) and r["harms"] == (r["ub"] < 0)
    # (b) test_coef with fixed effects (FE groups nested in 6 unequal clusters), coefficient 0
    rng = np.random.default_rng(23)
    fe = np.repeat(np.arange(30), 4)
    cl = np.repeat(np.arange(6), [9, 7, 6, 4, 3, 1])[fe]
    nn = len(fe)
    X = np.column_stack([(np.arange(nn) % 4 == 1).astype(float), rng.uniform(4, 14, nn)])
    yv = 0.01 * X[:, 0] + 0.002 * X[:, 1] + 0.02 * rng.standard_normal(30)[fe] + 0.03 * rng.standard_normal(nn)
    tc = test_coef(yv, X, 0, cl, fe=fe, B=499, seed=4, E_=0.02, return_draws=True)
    b_o, se_o = _oracle_cr1(yv, X, cl, fe, np.ones(nn), 0)
    sz = np.bincount(cl).astype(float)
    gs2 = float((sz ** 2).sum() ** 2 / (sz ** 4).sum())
    t2 = b_o / se_o
    assert abs(tc["estimate"] - b_o) < 1e-12 and abs(tc["se"] - se_o) < 1e-12 * se_o and abs(tc["gstar"] - gs2) < 1e-12
    assert abs(tc["p_gstar"] - stats.t.sf(t2, gs2 - 1)) < 1e-10
    assert abs(tc["ub_t"] - (b_o + stats.t.ppf(1 - a, gs2 - 1) * se_o)) < 1e-12
    assert abs(tc["ub_boot"] - (b_o - _weibull_q(tc["tstar_unrestricted"], a) * se_o)) < 1e-12
    assert abs(tc["ub"] - max(tc["ub_boot"], tc["ub_t"])) < 1e-15
    p_w2 = (1 + np.sum(tc["tstar_restricted"] >= tc["t"] - 1e-10 * max(1, abs(tc["t"])))) / 500
    assert abs(tc["p_wcr"] - p_w2) < 1e-15 and abs(tc["p_decide"] - max(p_w2, tc["p_gstar"])) < 1e-15
    # (c) test_h4 on a small fixed design: per-method b, se, G* (brute-force dummy-variable fits), the shared
    # multipliers, Romano-Wolf, Bonferroni, bounds, intervals and MDEs written out
    rng = np.random.default_rng(12)
    meth = _dgp_h4(rng, b=(0.0, 0.004, 0.0, -0.002), frac=1.0, sizes=np.array([6, 5, 4, 4, 3, 2, 2, 1]))
    B4, n_b = 199, 4
    r4 = test_h4(meth, B=B4, seed=7)
    tab = r4["methods"].set_index("method")
    allcl = np.concatenate([fr["cluster"].to_numpy() for fr in meth.values()])
    col = {lab: i for i, lab in enumerate(dict.fromkeys(allcl.tolist()))}          # first appearance, all methods
    W4 = WEBB[np.random.default_rng(7).integers(0, 6, size=(B4, len(col)))]
    names = list(meth)
    bj, sej, gsj, ts = (np.empty(len(names)) for _ in range(4))
    tst = np.empty((B4, len(names)))
    for jj, nm in enumerate(names):
        fr = meth[nm]
        keep = fr.groupby("cw")["y"].transform("size").to_numpy() > 1               # singleton coin-weeks dropped
        yy = fr["y"].to_numpy()[keep]
        XX = np.column_stack([fr["real"], fr["depth"] - fr["depth_real"]])[keep]
        cc, ff = fr["cluster"].to_numpy()[keep], fr["cw"].to_numpy()[keep]
        bj[jj], sej[jj] = _oracle_cr1(yy, XX, cc, ff, np.ones(len(yy)), 0)
        cnt = np.unique(cc, return_counts=True)[1].astype(float)
        gsj[jj] = (cnt ** 2).sum() ** 2 / (cnt ** 4).sum()
        labs = sorted(set(cc.tolist()))
        Wo = np.column_stack([W4[:, col[lab]] for lab in labs])
        tst[:, jj] = _oracle_wild(yy, XX, 0, cc, ff, np.ones(len(yy)), Wo, False, 0.0)[0]
        ts[jj] = bj[jj] / sej[jj]
        rw = tab.loc[nm]
        assert abs(rw["b"] - bj[jj]) < 1e-12 and abs(rw["se"] - sej[jj]) < 1e-12 * sej[jj], nm
        assert abs(rw["gstar"] - gsj[jj]) < 1e-12 and abs(gsj[jj] - rw["G"]) > 0.5, nm
        p_t = stats.t.sf(ts[jj], gsj[jj] - 1)
        assert abs(rw["p_t"] - p_t) < 1e-12 and abs(rw["p_bonf"] - min(1.0, n_b * p_t)) < 1e-12, nm
        assert abs(rw["ub_bonf"] - (bj[jj] + stats.t.ppf(1 - a / n_b, gsj[jj] - 1) * sej[jj])) < 1e-12, nm
        assert abs(rw["mde"] - (stats.t.ppf(1 - a, gsj[jj] - 1) + stats.t.ppf(0.8, gsj[jj] - 1)) * sej[jj]) < 1e-12
        assert abs(rw["mde_bonf"] - (stats.t.ppf(1 - a / n_b, gsj[jj] - 1) + stats.t.ppf(0.8, gsj[jj] - 1))
                   * sej[jj]) < 1e-12
    assert np.allclose(r4["tstar"], tst, rtol=1e-8, atol=1e-10)                 # shared multipliers, exact refits
    jm = int(np.argmax(ts))
    T = ts[jm]
    p_rw = _rw_oracle(ts, tst)
    assert r4["argmax"] == names[jm] and abs(r4["T"] - T) < 1e-12
    assert np.allclose(tab.loc[names, "p_rw"], p_rw, rtol=0, atol=1e-15)
    assert abs(r4["p_wcr"] - (1 + np.sum(tst.max(1) >= T)) / (B4 + 1)) < 1e-15
    p_g = min(1.0, n_b * stats.t.sf(T, gsj[jm] - 1))                            # 4 x t(G* - 1) of the largest t
    assert abs(r4["p_gstar"] - p_g) < 1e-12 and abs(r4["p_decide"] - max(r4["p_wcr"], p_g)) < 1e-15
    assert np.allclose(tab.loc[names, "p_method"], np.maximum(p_rw, np.minimum(1, n_b * stats.t.sf(ts, gsj - 1))))
    qmin = _weibull_q(tst.min(1), a)
    ub_m = np.maximum(bj - qmin * sej, bj + stats.t.ppf(1 - a / n_b, gsj - 1) * sej)
    assert np.allclose(tab.loc[names, "ub_boot"], bj - qmin * sej, rtol=0, atol=1e-12)
    assert np.allclose(tab.loc[names, "ub"], ub_m, rtol=0, atol=1e-12) and abs(r4["ub"] - ub_m.max()) < 1e-12
    qabs = _weibull_q(np.abs(tst).max(1), 0.95)
    q2 = stats.t.ppf(1 - 0.025 / n_b, gsj - 1)
    assert np.allclose(tab.loc[names, "ci95_lo"], np.minimum(bj - qabs * sej, bj - q2 * sej), rtol=0, atol=1e-12)
    assert np.allclose(tab.loc[names, "ci95_hi"], np.maximum(bj + qabs * sej, bj + q2 * sej), rtol=0, atol=1e-12)
    assert r4["noedge"] == (r4["ub"] < E["H4"]) and r4["unbounded"] == []
    say(f"  test_mean (G 6, G* {gs:.2f}), test_coef with FE (G* {gs2:.2f}) and test_h4 (4 methods, G* "
        f"{', '.join(f'{v:.1f}' for v in gsj)}) against hand formulas: p_G* = t(G*-1) sf, bounds at 1 - 0.05/3, "
        f"p_WCR and bootstrap bounds from brute-force draws ({ties} exact tie counted), Romano-Wolf, 4 x Bonferroni, "
        "intervals, MDE")


def _check_review_fixes(say):
    """One regression check per fixed finding of the stats review (F1-F8; F9 is _check_known_answers)."""
    # F1: K3's simulated quantile only widens the NO EDGE bound (§10.2 "It is widened if K3 requires")
    rng = np.random.default_rng(73)
    y, g = _dgp_mean("crash", rng)
    r0 = test_mean(y, g, E_=E["H1"], B=999, seed=1)
    r = test_mean(y + (E["H1"] + 0.001 - r0["ub"]), g, E_=E["H1"], B=999, seed=1)     # nominal bound just above E
    assert abs(r["ub"] - (E["H1"] + 0.001)) < 1e-12 and not r["noedge"]

    def cal_with(pivot):
        nul = {"s": dict(stat=list(np.linspace(-4, 4, 999)), pivot=list(pivot))}
        return dict(level_noedge=LEVEL_NOEDGE, tests={t_: dict(needs_calibration=True) for t_ in FAMILY},
                    null={"H1": nul, "H4": nul})

    piv_n, piv_w = np.linspace(-1.0, 1.0, 999), np.linspace(-10.0, 10.0, 999)
    narrow, wide = cal_with(piv_n), cal_with(piv_w)
    rn = apply_calibration(r, "H1", narrow)
    q_n = _weibull_q(piv_n, 1 - LEVEL_NOEDGE)
    assert abs(rn["ub_calibrated"] - (r["estimate"] - q_n * r["se"])) < 1e-15 and rn["ub_calibrated"] < E["H1"]
    assert rn["ub"] == r["ub"] == rn["ub_nominal"] and not rn["noedge"] and not rn["harms"] and rn["calibrated"]
    assert verdict(holm([rn["p_decide"], 1.0, 1.0])[0], True, rn["ub"], E["H1"]) == "INCONCLUSIVE"   # was NO EDGE
    rw_ = apply_calibration(r, "H1", wide)
    assert rw_["ub"] == rw_["ub_calibrated"] > r["ub"]
    assert calibrated_bound("H1", r["estimate"], r["se"], narrow, nominal=r["ub"]) == r["ub"]
    h4 = test_h4(_dgp_h4(np.random.default_rng(5), frac=0.3), B=499, seed=2)
    ub_before = h4["methods"]["ub"].to_numpy(float).copy()
    for cal, piv in ((narrow, piv_n), (wide, piv_w)):
        hc = apply_calibration(h4, "H4", cal)
        tb = hc["methods"]
        cal_m = tb["b"].to_numpy(float) - _weibull_q(piv, 1 - LEVEL_NOEDGE) * tb["se"].to_numpy(float)
        assert np.allclose(tb["ub_calibrated"], cal_m, rtol=0, atol=1e-15)
        assert np.allclose(tb["ub"], np.maximum(ub_before, cal_m), rtol=0, atol=1e-15)
        assert np.array_equal(tb["ub_nominal"].to_numpy(float), ub_before)
        assert abs(hc["ub"] - max(ub_before.max(), cal_m.max())) < 1e-15 and hc["ub"] >= h4["ub"]
    assert apply_calibration(h4, "H4", narrow)["ub"] == h4["ub"]
    assert np.array_equal(h4["methods"]["ub"].to_numpy(float), ub_before) and "ub_calibrated" not in h4["methods"]
    one = test_mean([0.02, 0.01, 0.03], [0, 0, 0], E_=E["H1"], B=99)          # an undefined statistic ...
    assert np.isnan(apply_calibration(one, "H1", narrow)["p_decide"])         # ... has no calibrated p (not 1/(n+1))
    assert np.isnan(calibrated_p("H1", np.nan, narrow))
    say(f"  F1: K3 calibration widens only: nominal {r['ub']:.4f} kept over the narrower simulated "
        f"{rn['ub_calibrated']:.4f} (< E {E['H1']}: INCONCLUSIVE stays INCONCLUSIVE); a wider simulated bound replaces "
        "it; per method for H4")
    # F2: H4's NO EDGE bound needs a bound for every method (M7 in one month-block, or empty, has none)
    rng = np.random.default_rng(11)
    meth = _dgp_h4(rng, b=(-0.004, -0.004, -0.004, 0.05), frac=1.0)
    m7 = meth["M7"]
    meth["M7"] = m7[m7["cluster"] == 0]
    r2 = test_h4(meth, B=499, seed=2)
    t2 = r2["methods"].set_index("method")
    assert t2.loc["M7", "G"] == 1 and np.isnan(t2.loc["M7", "ub"]) and np.isfinite(t2.loc["M7", "b"])    # (F8: b kept)
    assert t2.loc[["M4", "M5b", "M6"], "ub"].max() < E["H4"]                 # the old max over bounded ones: NO EDGE
    assert np.isnan(r2["ub"]) and not r2["noedge"] and r2["unbounded"] == ["M7"]
    assert verdict(1.0, False, r2["ub"], E["H4"]) == "INCONCLUSIVE"
    assert np.isnan(apply_calibration(r2, "H4", wide)["ub"])
    hf7 = h4_fit(meth["M7"], clusters=r2["clusters"]["M7"])
    assert abs(hf7["b"] - t2.loc["M7", "b"]) < 1e-12 and hf7["G"] == 1 and np.isnan(hf7["se"])
    meth["M7"] = m7.iloc[0:0]
    r2e = test_h4(meth, B=499, seed=2)
    assert np.isnan(r2e["ub"]) and r2e["unbounded"] == ["M7"] and r2e["n_bonf"] == 4 and np.isfinite(r2e["p_decide"])
    say(f"  F2: M7 in one month-block (b {t2.loc['M7', 'b']:+.3f}, no bound) or empty: H4's bound NaN, never NO EDGE "
        f"(other methods' bounds <= {t2.loc[['M4', 'M5b', 'M6'], 'ub'].max():.4f} < E)")
    # F3: Holm always runs over the three family tests
    h1 = dict(p_decide=0.02, ub=0.08, estimate=0.03, se=0.01, gstar=12, G=58, unit="month-block", mde=0.03)
    h2 = dict(p_decide=0.30, ub=0.03, estimate=0.00, se=0.01, gstar=12, G=58, unit="month-block", mde=0.03)
    gates = {"H1": True, "H2R": True, "H4": True}
    with warnings.catch_warnings(record=True) as wl:
        warnings.simplefilter("always")
        fv = family_verdicts({"H1": h1, "H2R": h2}, gates=gates)
        fvn = family_verdicts({"H1": h1, "H2R": h2, "H4": None}, gates=gates)
    assert sum("no row for ['H4']" in str(w_.message) for w_ in wl) == 2
    for f_ in (fv, fvn):
        fi = f_.set_index("test")
        assert len(f_) == 3 and not fi.loc["H4", "row_given"] and fi.loc["H4", "verdict"] == "INCONCLUSIVE"
        assert abs(fi.loc["H1", "p_holm"] - 0.06) < 1e-12 and fi.loc["H1", "verdict"] == "INCONCLUSIVE"   # m = 3
        assert abs(fi.loc["H1", "holm_level"] - 0.05 / 3) < 1e-15 and fi.loc["H1", "row_given"]
    try:
        family_verdicts({"H1": h1, "H2R": h2, "H4": h2, "H5": h1})
        raise AssertionError("a test outside the family was accepted")
    except ValueError:
        pass
    say("  F3: a missing family row enters Holm as p = 1 (H1 p 0.02 -> Holm 0.06, INCONCLUSIVE, not 0.04 PASS); "
        "keys outside the family refused")
    # F4: the Bonferroni factor is 4 whatever is passed
    meth = _dgp_h4(np.random.default_rng(3), frac=0.3)
    three = {k: meth[k] for k in ("M4", "M5b", "M6")}
    with warnings.catch_warnings(record=True) as wl:
        warnings.simplefilter("always")
        r3 = test_h4(three, B=499, seed=1)
    assert any("['M7']" in str(w_.message) for w_ in wl)
    t3 = r3["methods"].set_index("method")
    assert r3["n_bonf"] == 4 and np.isnan(r3["ub"]) and r3["unbounded"] == ["1 method(s) not passed"]
    assert abs(r3["p_gstar"] - min(1.0, 4 * stats.t.sf(r3["T"], t3.loc[r3["argmax"], "gstar"] - 1))) < 1e-15
    assert np.allclose(t3["p_bonf"], np.minimum(1.0, 4 * t3["p_t"]))
    r3x = test_h4(three, B=499, seed=1, n_bonf=3)
    assert r3x["n_bonf"] == 3 and np.isfinite(r3x["ub"]) and r3x["p_gstar"] < r3["p_gstar"]
    try:
        test_h4(meth, B=99, n_bonf=3)
        raise AssertionError("n_bonf below the number of methods accepted")
    except ValueError:
        pass
    say(f"  F4: three methods passed: n_bonf stays 4 (p_G* {r3['p_gstar']:.4f}, not {r3x['p_gstar']:.4f} at 3), a "
        "warning, H4 bound NaN; n_bonf below the number of methods refused")
    # F5: the gates use test_h4's partition (time-only frames: month-blocks of the UNION of the methods' fills)
    rng = np.random.default_rng(0)
    offs = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])

    def frame(days, effects, cw0):
        rows = [dict(cw=cw0 + i, real=float(o == 0), depth=8 + 1.8 * o,
                     y=0.01 * (8 + 1.8 * o) + eff * (o == 0) + 0.002 * rng.standard_normal(),
                     time=pd.Timestamp(d, tz="UTC")) for i, (d, eff) in enumerate(zip(days, effects)) for o in offs]
        return pd.DataFrame(rows)

    fa = frame(["2022-01-27", "2022-01-28", "2022-02-09", "2022-02-10"]
               + [f"2022-{mo:02d}-15" for mo in range(3, 13) for _ in (0, 1)], [0.06] * 4 + [-0.004] * 20, 0)
    fb = frame(["2022-01-31", "2022-02-01"] + [f"2022-{mo:02d}-15" for mo in range(3, 13)], [0.0] * 12, 1000)
    fc = frame([f"2022-{mo:02d}-20" for mo in range(1, 13)], [0.0] * 12, 2000)
    fd = frame([f"2022-{mo:02d}-22" for mo in range(1, 13)], [0.0] * 12, 3000)
    meth5 = {"M4": fa, "M5b": fb, "M6": fc, "M7": fd}
    r5 = test_h4(meth5, B=199, seed=1)
    union = month_blocks(np.concatenate([_utc_ns(f_["time"]) for f_ in meth5.values()]))[0]
    cla = r5["clusters"]["M4"]
    assert np.array_equal(cla, union[:len(fa)]) and np.array_equal(h4_clusters(meth5)["M4"], cla)
    for fn in (h4_fit, h4_drop_worst_block):
        try:
            fn(fa)
            raise AssertionError(f"{fn.__name__} rebuilt month-blocks from one method's fills")
        except ValueError:
            pass
    hf = h4_fit(fa, clusters=cla)
    ta = r5["methods"].set_index("method").loc["M4"]
    assert abs(hf["b"] - ta["b"]) < 1e-12 and abs(hf["se"] - ta["se"]) < 1e-12 and hf["G"] == ta["G"] == 11
    b_u, blk_u = h4_drop_worst_block(fa, clusters=cla)
    direct = {c_: h4_fit(fa, mask=cla != c_, clusters=cla)["b"] for c_ in pd.unique(cla)}
    assert blk_u == min(direct, key=direct.get) and abs(b_u - min(direct.values())) < 1e-15
    b_own, _ = h4_drop_worst_block(fa, clusters=month_blocks(fa["time"])[0])     # M4's own partition (old default)
    assert b_own > 0 > b_u, (b_own, b_u)
    say(f"  F5: test_h4 returns its partition (G 11 for M4: Jan+Feb merged by another method's episode); the gates "
        f"refuse to rebuild it from one method; worst-block gate on it: b {b_u:+.4f} (fails; M4's own partition gave "
        f"{b_own:+.4f})")
    # F6: the coin-week fixed effects are required
    meth = _dgp_h4(np.random.default_rng(5), s=0.01, frac=0.5)
    ren = {k: v.rename(columns={"cw": "coin_week"}) for k, v in meth.items()}
    for call in (lambda: test_h4(ren, B=99), lambda: h4_fit(ren["M4"]), lambda: h4_clusters(ren)):
        try:
            call()
            raise AssertionError("a frame without cw was fitted")
        except ValueError as exc:
            assert "cw" in str(exc)
    ok = test_h4(meth, B=199, seed=1)
    via = test_h4(ren, B=199, seed=1, cols={"cw": "coin_week"})
    assert np.allclose(ok["methods"]["t"], via["methods"]["t"]) and ok["p_decide"] == via["p_decide"]
    assert (ok["methods"]["n_cw"] > 1).all()
    assert test_h4({"M4": meth["M4"].iloc[0:0][[]], "M5b": meth["M5b"], "M6": meth["M6"], "M7": meth["M7"]},
                   B=99)["methods"].set_index("method").loc["M4", "n"] == 0     # a row-less frame may omit columns
    say("  F6: a frame without cw is refused by test_h4, h4_fit and h4_clusters (cols= maps a different name)")
    # F7: a two-way variance that is not positive falls back to the larger one-way CR1 variance (never SE 0)
    rng = np.random.default_rng(1)
    coin = np.repeat(np.arange(10), 6)
    month = np.tile(np.arange(6), 10)
    one_x = np.ones((60, 1))
    found = None
    for _ in range(500):
        yy = 0.01 + 0.05 * rng.standard_normal(60)
        if _oracle_twoway(yy, one_x, coin, month)[1][0, 0] < 0:
            found = yy
            break
    assert found is not None
    v_fb = max(_oracle_oneway(found, one_x, coin)[0, 0], _oracle_oneway(found, one_x, month)[0, 0])
    mc = mean_cluster2(found, coin, month)
    assert mc["oneway_fallback"] and mc["psd_fixed"] and abs(mc["se"] - math.sqrt(v_fb)) < 1e-12 * math.sqrt(v_fb)
    assert 0 < mc["p"] < 1 and mc["ci95"][1] - mc["ci95"][0] > 0 and mc["df"] == 5
    mixed = both = None
    for _ in range(3000):
        X2 = np.column_stack([np.ones(60), rng.standard_normal(60)])
        yy = 0.01 + 0.05 * rng.standard_normal(60)
        dV = np.diag(_oracle_twoway(yy, X2, coin, month)[1])
        lam = np.linalg.eigvalsh(_oracle_twoway(yy, X2, coin, month)[1])
        if lam.min() < 0 and (dV > 0).any() and (dV <= 0).any() and mixed is None:
            mixed = (yy, X2)
        if lam.min() < 0 and (dV > 0).all() and both is None:
            both = (yy, X2)
        if mixed is not None and both is not None:
            break
    assert mixed is not None and both is not None
    for yy, X2 in (mixed, both):
        rr = ols_cluster2(yy, X2, coin, month)
        Vo = _oracle_twoway(yy, X2, coin, month)[1]
        lam, vec = np.linalg.eigh((Vo + Vo.T) / 2)
        Vp = vec @ np.diag(np.maximum(lam, 0)) @ vec.T
        v1, v2 = _oracle_oneway(yy, X2, coin), _oracle_oneway(yy, X2, month)
        want = np.where(np.diag(Vo) > 0, np.diag(Vp), np.maximum(np.diag(v1), np.diag(v2)))
        assert rr["psd_fixed"] and np.array_equal(rr["oneway_fallback"], ~(np.diag(Vo) > 0))
        assert np.allclose(rr["se"], np.sqrt(want), rtol=1e-10, atol=0) and (rr["se"] > 0).all()
    fit = dh5_fit(rng.integers(0, 2, 200).astype(float), (np.arange(200) % 3 == 0).astype(float),
                  rng.choice([6, 8, 10], 200), rng.uniform(0.02, 0.08, 200), rng.integers(0, 12, 200),
                  rng.integers(0, 8, 200))
    assert "oneway_fallback" in fit and "psd_fixed" in fit
    say(f"  F7: two-way V < 0 for a mean: SE = the larger one-way CR1 SE ({mc['se']:.4f}, p {mc['p']:.3f}), not 0; "
        "two coefficients: the fallback only where V[j, j] <= 0, the eigen-fixed V elsewhere (explicit-loop oracle)")
    # F8: a point estimate is reported with one cluster
    t8 = pd.to_datetime(["2025-10-10 21:15", "2025-10-10 21:16", "2025-10-10 21:20"], utc=True)
    y8 = np.array([0.031, 0.012, -0.004])
    blk = month_blocks(t8)[0]
    d8 = describe(y8, blk, B=99)
    assert abs(d8["estimate"] - y8.mean()) < 1e-15 and d8["G"] == 1
    assert np.isnan(d8["se"]) and np.isnan(d8["mde"]) and np.isnan(d8["ci95"][0]) and np.isnan(d8["ci95"][1])
    m8 = test_mean(y8, blk, E_=E["H1"], B=99)
    assert abs(m8["estimate"] - y8.mean()) < 1e-15 and np.isnan(m8["p_decide"]) and np.isnan(m8["ub"])
    assert not m8["noedge"] and verdict(holm([m8["p_decide"], 0.5, 0.5])[0], True, m8["ub"], E["H1"]) == "INCONCLUSIVE"
    ep = np.repeat([0, 1, 2], 4)
    fast = np.tile([1.0, 0.0, 1.0, 0.0], 3)
    yv = 0.02 * fast + 0.01 * np.random.default_rng(8).standard_normal(12)
    tc8 = test_coef(yv, fast, 0, np.zeros(12), fe=ep, B=99)
    assert abs(tc8["estimate"] - ols_fe(yv, fast, ep, np.zeros(12))["coef"][0]) < 1e-15 and np.isnan(tc8["se"])
    say("  F8: one month-block: describe() / test_mean / test_coef (FE) keep the estimate; SE, p, bounds, interval "
        "and MDE NaN (INCONCLUSIVE); test_h4 keeps the method's b (F2 above)")


def selftest(quick: bool = False):
    t0 = time.time()

    def say(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    n_jobs = min(4, os.cpu_count() or 1)
    reps_size = 400 if quick else 2000
    reps_h4 = 300 if quick else 2000
    reps_light = 150 if quick else 600
    say("clusters: episodes, month-blocks, keys, G*")
    _check_clusters(say)
    say("CR1 and the exact wild cluster bootstrap against brute force")
    _check_cr1_and_wild_exact(say)
    say("known answers: p_G*, the 98.33% bounds, p_WCR, H4's per-method p, Romano-Wolf and Bonferroni by hand")
    _check_known_answers(say)
    say("regression checks for the stats review's findings F1-F8")
    _check_review_fixes(say)
    say(f"size and coverage of p_decide = max(p_WCR, p_G*) and the NO EDGE bound (B {B_BOOT})")
    _check_size_mean(say, reps_size, n_jobs)
    say(f"H4: stacked regression, Romano-Wolf max-t, Bonferroni companion (B {B_BOOT})")
    _check_h4(say, reps_h4, n_jobs)
    say("Holm, BH, verdicts, E, MDE, gate helpers")
    _check_multiplicity(say)
    say("two-way clustering, Ibragimov-Müller, D-H5 pieces")
    _check_twoway_im(say, reps_light)
    say("Kaplan-Meier and D6")
    _check_km(say)
    say("overdispersion and the sheet's intervals")
    _check_phi_wilson(say)
    say("stationary block bootstrap, episode-cluster bootstrap, D5")
    _check_bootstraps(say, reps_light // 2)
    say("API paths: H4 from fill times, empty method, gates, FE coefficient, describe, verdicts, calibration")
    _check_api(say)
    say("K3 inference_calibration on a toy simulator")
    _check_k3(say, 600 if quick else 2000, n_jobs, 499)
    say(f"selftest passed in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "selftest":
        selftest(quick="--quick" in sys.argv[2:])
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}")
