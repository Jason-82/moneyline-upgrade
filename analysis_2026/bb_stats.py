"""
Inference for the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md, "Hypotheses and pass
rules": "Units and statistics", "Multiplicity", "Verdicts"; and "Controls": "Inference known answer"). Contract:
the scratchpad's bb_engine_spec.md, "bb_stats.py". Every p-value is one-sided for "effect > 0".

    python3 -m analysis_2026.bb_stats selftest            # synthetic known-answer checks (no market data is read)
    python3 -m analysis_2026.bb_stats inference-control   # the "Inference known answer" control on the built-in
                                                          #   trade generator (the orchestrator wires the engine)

Public API
  Units
    drift_adjust(trades, expo, hourly_ret_by_sym, leave_out_days=182, ...) -> Series   drift-adjusted trade return
    returns_from_hours(hours, col="close")      close-to-close arithmetic return per hour of a coin_hours frame
    month_key(t), quarter_key(t), overlap_episodes(entry, exit)   cluster labels (primary month; sensitivities)
  Trade-level and paired tests
    cluster_t(x, clusters) -> (mean, se, t, p_one_sided, df)      one-way, G/(G-1), Student t at G-1 df
    boot_t_upper(x, clusters, level, B=9999, seed=20261018) -> float   month-cluster bootstrap-t upper bound
    boot_t_bounds(x, clusters, levels, B, seed) -> dict           the same draws at several levels + 95% interval
    ratio_cluster(num, den, clusters) -> (R, se, df)              sum(num)/sum(den), delta method (H3)
    ratio_diff_cluster(num_a, den_a, cl_a, num_b, den_b, cl_b) -> (dR, se, df)
    cluster_ols(y, X, clusters) -> (beta, se, t, p, df)           H5
    paired_signal_diff(base_trades, var_trades, key="signal_day", col="ret_adj") -> DataFrame
    trade_test(x, clusters, E, ...) -> dict                       everything a trade-level / paired row reports
  Portfolio-level tests
    block_boot(a, b=None, stat="mean"|"sharpe_diff"|"logdiff", mean_block_days, B=10000, seed, ...) -> dict
    portfolio_test(a, b, stat, kind="crypto"|"stock", ...) -> dict  1-, 3- and 12-month blocks; verdict p = max(1, 3)
    sb_indices(T, mean_block, n, rng)                             stationary-bootstrap index paths
  Multiplicity and verdicts
    holm(p) (= analysis_2026.scalp_stats.holm), bh(p), iu_p(ps), mde(se, df=None), upper_bound_t(m, se, df, level)
    verdict(p_holm, conds_ok, ub, E) -> "PASS" | "NO EDGE" | "NO EDGE (HARMS)" | "INCONCLUSIVE"
  Reporting
    drop_worst_month(x, months) -> (mean_after, month), top_share(pnl, q=0.05) -> float
  Controls
    inference_control(sim_fn=None, n_paths=200, seed=20261018, ...) -> dict
    simple_three_coin_trades(seed, ...) -> dict      built-in synthetic trade generator (numba), used by default

Statistics as the pre-registration fixes them
- Drift-adjusted trade return = ret - sum over the hours h held of (notional_h / M) * mu, mu = the asset's mean
  hourly arithmetic return (daily for stocks) over its whole sample excluding the holding period and the 182 days
  on either side. Shorts carry a negative notional, so their drift charge has the opposite sign.
- Trade-level and paired SEs: one-way clusters by entry calendar month, variance factor G/(G-1), t compared with
  Student t at G-1 df, G = the number of months with a trade.
- NO EDGE bounds for trade-level and paired tests: month-cluster bootstrap-t (9,999 draws): clusters resampled
  with replacement, t*_b = (mean*_b - mean) / se*_b with se*_b the same clustered SE on the draw, and
  UB(level) = mean - q_{1-level}(t*) * se.
- Portfolio tests: paired stationary block bootstrap (Politis and Romano 1994; strategy and benchmark resampled on
  the same days), 10,000 draws, mean block 1 month (also 3 and 12), the verdict p is the larger of the 1- and
  3-month p. Sharpe differences are studentized (Ledoit and Wolf 2008).
- Bootstrap p-values: p = (1 + #{b : theta*_b - theta_hat >= theta_hat}) / (B + 1); for the Sharpe difference on the
  studentized scale, p = (1 + #{b : (theta*_b - theta_hat) / se*_b >= theta_hat / se}) / (B + 1).
- One Holm family of 12 (H1-H10, HS1, HS2); a compound test enters with the largest of its one-sided p-values
  (intersection-union); descriptive tables are Benjamini-Hochberg adjusted within the table.
- Verdicts: PASS = Holm p < 0.05 and every other condition; NO EDGE = the one-sided upper bound at level
  1 - 0.05/12 is below E ("NO EDGE (HARMS)" when below 0; for a compound test one component is enough);
  else INCONCLUSIVE. MDE = (z_{1-0.05/12} + z_{0.80}) * SE = (2.638 + 0.842) * SE.

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. drift_adjust: the hours "held" are the rows of the engine's exposure path for the position (expo: position id,
   hour, signed notional / M of the hour's opening position, so that a position's gross P&L is
   sum_h notional_h * r_h with r_h = close_h / close_{h-1} - 1 of the hour labelled h). The leave-out window is
   [entry1_time - 182 days, exit_time + 182 days] in calendar days, inclusive, on the timestamps of the return
   series (hours for crypto, sessions for stocks). A position still open at the end uses its last exposure hour
   as exit. mu averages every finite value of the series the caller passes (the caller defines "whole sample";
   `returns_from_hours` gives the traded close-to-close series with outage hours at 0 and returns across a
   series break (`seg` change) or into a non-tradable hour set to NaN). If the leave-out sample is empty the
   drift-adjusted return is NaN (fallback_full=True uses the whole-sample mean instead); the count is in
   attrs["n_nan_mu"].
2. paired_signal_diff: the pairing key is (sym, key) when both frames carry `sym` (a signal day alone does not
   identify a signal across coins). Several trades of one variant with the same key are summed (total return
   per signal). diff = var - base; a signal missing from one variant counts 0 for it. The cluster month is the
   entry calendar month of the base trade, or of the variant's trade when the base skipped the signal.
3. block_boot: blocks are in observations (UTC days for crypto, sessions for stocks); portfolio_test converts
   months with 365/12 days or 252/12 sessions. Indices wrap around (circular), as in Politis-Romano. For "mean"
   and "logdiff" the p-value uses the raw scale (as written) and the bounds are basic-bootstrap bounds,
   UB = 2 theta_hat - q_{1-level}(theta*), the inversion of the same p-value; the deciding SE is the bootstrap SD.
   For "sharpe_diff" the original-sample SE is Ledoit-Wolf's HAC (VAR(1)-prewhitened quadratic-spectral kernel,
   Andrews-Monahan automatic bandwidth, small-sample factor T/(T-4)) of the delta-method gradient on
   (mu_a, mu_b, E a^2, E b^2), and each draw's SE is the block-adjusted one natural to the bootstrap
   (sum over the draw's resampled blocks of the squared block sums of the draw's own influence series),
   the stationary-bootstrap analogue of LW 2008's circular-block formula; se_method="sb" uses instead the
   kernel the stationary bootstrap implies (Politis-Romano 1994) for the original SE. The bound is
   UB = theta_hat - q_{1-level}(t*) * se. Estimates are returned annualized (mean and logdiff * ppy; Sharpe
   * sqrt(ppy); ppy = 365 crypto, 252 stocks), as every portfolio E is per year. "logdiff" takes simple returns
   and uses log(1 + r); if any 1 + r <= 0 (equity reaches 0) growth is -inf, p = 1 and the bound is -inf with no
   bootstrap (H9's rule).
4. portfolio_test: the NO EDGE bound is the larger of the 1- and 3-month bounds (the conservative choice, mirroring
   the max of the two p-values).
5. verdict: PASS takes precedence over NO EDGE when both hold (an effect significantly above 0 whose bound is
   below E); ub and E may be sequences (one per component of a compound test): NO EDGE if any component's bound is
   below its E, "(HARMS)" if any component's bound is below 0. A NaN p never passes; a NaN bound is never NO EDGE.
6. mde uses the normal quantile 2.638 (= the pre-registration's 2.64) unless df is given, and z_{0.80} = 0.8416.
7. top_share uses the ceil(q * n) largest P&Ls over the sum of all P&Ls (no sign guard: a total <= 0 gives a
   share that is negative or above 1, reported as is).
8. bh: NaN p-values are left out of m and returned as NaN; holm treats NaN as 1 (scalp_stats.holm).
9. inference_control: the "true mean" is the pooled grand mean of every synthetic trade across the paths unless
   true_mean is given; the rejection rate is of the pre-registered test (p < 0.05 for mean > 0) and also the
   rate centred at the true mean; the miss rate is the share of paths whose month-cluster bootstrap-t bound at
   95% lies below the true mean. If that exceeds 5%, `level_widened` is the smallest level on a grid at which it
   does not (the pre-registration's widening rule; the orchestrator applies it).
"""
from __future__ import annotations

import concurrent.futures as cf
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026.scalp_stats import holm, drop_worst  # noqa: E402

ALPHA = 0.05
N_FAMILY = 12                                   # H1-H10, HS1, HS2
LEVEL_NOEDGE = 1 - ALPHA / N_FAMILY             # 0.995833...
Z_NOEDGE = float(stats.norm.ppf(LEVEL_NOEDGE))  # 2.638 (the pre-registration's 2.64)
Z_POWER = float(stats.norm.ppf(0.80))           # 0.8416
B_TRADE = 9999
B_PORT = 10000
SEED = 20261018
LEAVE_OUT_DAYS = 182
MONTH_DAYS = 365 / 12                           # crypto: UTC calendar days
MONTH_SESSIONS = 252 / 12                       # stocks: sessions
PPY = {"crypto": 365, "stock": 252}
# economic thresholds E (Verdicts)
E = {"H1": 0.005, "HS_trade": 0.005,                       # +0.5% of M per trade, drift-adjusted
     "H3": 0.0025, "H4": 0.0025, "H5": 0.0025, "H6": 0.0025, "H7": 0.0025, "H8": 0.0025,  # +0.25% of M per signal
     "H2": 0.10, "HS_sharpe": 0.10,                        # +0.10 annualized Sharpe
     "H9": 0.02,                                           # +2 log points a year
     "H10": 0.01}                                          # +1% of account equity a year


def _q(x, prob):
    """Order-statistic quantile with the (B + 1) * alpha convention (method 'weibull')."""
    return np.quantile(x, prob, method="weibull")


# ============================================================================ cluster labels

def _naive_utc(t) -> pd.DatetimeIndex:
    """Timestamps as a tz-naive UTC DatetimeIndex in nanoseconds (pandas 3 infers s/ms/us units otherwise)."""
    if isinstance(t, pd.DatetimeIndex):
        idx = t
    elif isinstance(t, (pd.Series, pd.Index)):
        idx = pd.DatetimeIndex(t)
    else:
        idx = pd.DatetimeIndex(pd.to_datetime(t))
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return idx.as_unit("ns")


def month_key(t) -> np.ndarray:
    """Calendar-month cluster label (UTC for timestamps; the session date for stocks) as an int YYYYMM."""
    idx = _naive_utc(t)
    return (idx.year * 100 + idx.month).to_numpy()


def quarter_key(t) -> np.ndarray:
    """Calendar-quarter label YYYYQ (sensitivity clusters)."""
    idx = _naive_utc(t)
    return (idx.year * 10 + idx.quarter).to_numpy()


def overlap_episodes(entry, exit_) -> np.ndarray:
    """Overlap-episode clusters: connected runs of overlapping holdings [entry, exit] across coins (sensitivity).
    A missing exit (still open) runs to +infinity."""
    e = _naive_utc(entry).asi8.astype(np.int64)
    x = _naive_utc(exit_)
    xv = np.where(x.isna(), np.iinfo(np.int64).max, x.asi8)
    order = np.argsort(e, kind="stable")
    lab = np.empty(len(e), np.int64)
    cur, end = -1, np.iinfo(np.int64).min
    for i in order:
        if e[i] > end:
            cur += 1
            end = xv[i]
        else:
            end = max(end, xv[i])
        lab[i] = cur
    return lab


# ============================================================================ drift adjustment

_ID = ("pos", "pid", "position", "position_id", "id")
_TIME = ("time", "hour", "open_time", "t", "h", "date")
_NOTIONAL = ("notional", "notional_m", "expo", "frac", "n")


def _pick(cols, names, what):
    for n in names:
        if n in cols:
            return n
    raise KeyError(f"no {what} column among {names} in {list(cols)}")


def _expo_frame(expo) -> pd.DataFrame:
    """Normalize the engine's exposure path to columns [pos, time, notional] (+ sym when given)."""
    if isinstance(expo, dict):
        parts = []
        for s, v in expo.items():
            f = _expo_frame(v)
            if "sym" not in f:
                f["sym"] = s
            parts.append(f)
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["pos", "time", "notional"])
    if isinstance(expo, (tuple, list)) and len(expo) == 3 and not isinstance(expo, pd.DataFrame):
        return pd.DataFrame({"pos": np.asarray(expo[0]), "time": np.asarray(expo[1]),
                             "notional": np.asarray(expo[2], float)})
    f = pd.DataFrame(expo)
    if isinstance(f.index, pd.MultiIndex) and len(f.columns) == 1:
        f = f.reset_index()
    out = pd.DataFrame({"pos": f[_pick(f.columns, _ID, "position id")].to_numpy(),
                        "time": f[_pick(f.columns, _TIME, "hour")].to_numpy(),
                        "notional": f[_pick(f.columns, _NOTIONAL, "notional")].to_numpy(float)})
    if "sym" in f.columns:
        out["sym"] = f["sym"].to_numpy()
    return out


def returns_from_hours(hours: pd.DataFrame, col: str = "close") -> pd.Series:
    """Hourly close-to-close arithmetic return of a coin_hours-shaped frame (index = hour open time).
    Outage rows (trades == 0, OHLC carried) contribute 0 and the gap's move lands on the next live hour, so the
    mean is per calendar hour, matching an exposure path that counts calendar hours. Returns across a series
    break (`seg` changes) or into a non-tradable row (`tradable` False) are NaN."""
    c = hours[col].astype(float)
    r = c / c.shift(1) - 1.0
    if "seg" in hours:
        r[hours["seg"].ne(hours["seg"].shift(1))] = np.nan
    if "tradable" in hours:
        r[~hours["tradable"].astype(bool)] = np.nan
    r.iloc[0] = np.nan
    return r


def drift_adjust(trades: pd.DataFrame, expo, hourly_ret_by_sym: dict, leave_out_days: int = LEAVE_OUT_DAYS,
                 ret_col: str = "ret", id_col: str | None = None, fallback_full: bool = False,
                 parts: bool = False):
    """Drift-adjusted trade return (prereg "Units and statistics"):
        ret_adj = ret - mu * sum_h notional_h,   mu = leave-out mean of the asset's per-period arithmetic return,
    excluding [entry1_time - leave_out_days, exit_time + leave_out_days].
    trades: one row per position with sym, entry1_time, exit_time (NaT if open) and ret_col; the position id is
      id_col, else the first of pos/pid/position/position_id/id present, else the index.
    expo: DataFrame (pos, time|hour, notional[, sym]), a (pos, hour, notional) tuple of arrays, or a dict
      {sym: such a frame}. Times are timestamps or integer positions into the sym's return series. Notional is
      signed (shorts negative), per unit of M.
    hourly_ret_by_sym: {sym: Series of arithmetic returns indexed by period start (hours; sessions for stocks)}.
    Returns a Series aligned to trades.index (parts=True: a DataFrame with mu, expo_sum, drift, ret, ret_adj)."""
    T = trades
    if id_col is None:
        id_col = next((c for c in _ID if c in T.columns), None)
    pid = T[id_col].to_numpy() if id_col is not None else T.index.to_numpy()
    syms = T["sym"].to_numpy()
    X = _expo_frame(expo)
    use_sym = "sym" in X.columns
    if not use_sym and len(pd.unique(pid)) != len(pid):
        raise ValueError("position ids are not unique across coins: give expo a sym column")
    keyT = pd.MultiIndex.from_arrays([syms, pid]) if use_sym else pd.Index(pid)
    keyX = pd.MultiIndex.from_arrays([X["sym"].to_numpy(), X["pos"].to_numpy()]) if use_sym else pd.Index(X["pos"])
    esum = pd.Series(X["notional"].to_numpy(float), index=keyX).groupby(level=list(range(keyX.nlevels))).sum()
    n_expo = esum.reindex(keyT).fillna(0.0).to_numpy()

    entry = _naive_utc(T["entry1_time"]) if "entry1_time" in T else None
    exit_ = _naive_utc(T["exit_time"]) if "exit_time" in T else None
    mu = np.full(len(T), np.nan)
    for s in pd.unique(syms):
        r = hourly_ret_by_sym[s]
        rt = _naive_utc(r.index).asi8
        order = np.argsort(rt, kind="stable")
        rt = rt[order]
        rv = r.to_numpy(float)[order]
        ok = np.isfinite(rv)
        cs = np.r_[0.0, np.cumsum(np.where(ok, rv, 0.0))]
        cn = np.r_[0, np.cumsum(ok)]
        n = len(rv)
        rows = np.where(syms == s)[0]
        # holding window per position: entry1_time .. exit_time, falling back to the exposure path's first/last hour
        xs = X[X["sym"] == s] if use_sym else X[X["pos"].isin(pid[rows])]
        if len(xs):
            tt = xs["time"].to_numpy()
            if np.issubdtype(np.asarray(tt).dtype, np.integer):
                tt = r.index[np.asarray(tt, np.int64)]
            tv = _naive_utc(tt).asi8
            g = pd.Series(tv).groupby(xs["pos"].to_numpy())
            first, last = g.min(), g.max()
        else:
            first = last = pd.Series(dtype=np.int64)
        lo_t = np.empty(len(rows), np.int64)
        hi_t = np.empty(len(rows), np.int64)
        for j, i in enumerate(rows):
            e0 = entry[i].value if entry is not None and not pd.isna(entry[i]) else first.get(pid[i], np.nan)
            x0 = exit_[i].value if exit_ is not None and not pd.isna(exit_[i]) else last.get(pid[i], np.nan)
            if pd.isna(x0):
                x0 = last.get(pid[i], e0)
            if pd.isna(e0):
                raise ValueError(f"position {pid[i]} ({s}) has neither entry1_time nor exposure rows")
            lo_t[j] = int(e0) - leave_out_days * 86_400_000_000_000
            hi_t[j] = int(x0) + leave_out_days * 86_400_000_000_000
        lo = np.searchsorted(rt, lo_t, "left")
        hi = np.searchsorted(rt, hi_t, "right")
        s_out = cs[n] - (cs[hi] - cs[lo])
        c_out = cn[n] - (cn[hi] - cn[lo])
        m = np.where(c_out > 0, s_out / np.maximum(c_out, 1), np.nan)
        if fallback_full and cn[n] > 0:
            m = np.where(c_out > 0, m, cs[n] / cn[n])
        mu[rows] = m
    ret = T[ret_col].to_numpy(float)
    drift = mu * n_expo
    adj = ret - drift
    if parts:
        out = pd.DataFrame({"mu": mu, "expo_sum": n_expo, "drift": drift, "ret": ret, "ret_adj": adj},
                           index=T.index)
    else:
        out = pd.Series(adj, index=T.index, name="ret_adj")
    out.attrs["n_nan_mu"] = int(np.isnan(mu).sum())
    return out


# ============================================================================ trade-level and paired tests

def _clean(x, *others):
    x = np.asarray(x, float)
    k = np.isfinite(x)
    return (x[k],) + tuple(np.asarray(o)[k] for o in others)


def _cl_var(e, g):
    """Clustered variance of mean(e): G/(G-1) * sum_g (sum_{i in g} e_i)^2 / n^2. Returns (var, G)."""
    _, inv = np.unique(g, return_inverse=True)
    s = np.bincount(inv, weights=e)
    G, n = len(s), len(e)
    if G < 2:
        return np.nan, G
    return (G / (G - 1)) * float(s @ s) / n ** 2, G


def cluster_t(x, clusters):
    """Mean of x with a one-way clustered SE (factor G/(G-1)); t compared with Student t at G-1 df.
    Returns (mean, se, t, one-sided p for mean > 0, df). Non-finite x are dropped."""
    x, g = _clean(x, clusters)
    if len(x) == 0:
        return np.nan, np.nan, np.nan, np.nan, 0
    m = float(x.mean())
    v, G = _cl_var(x - m, g)
    if not np.isfinite(v):
        return m, np.nan, np.nan, np.nan, 0
    se = math.sqrt(v)
    df = G - 1
    if se > 0:
        t = m / se
    else:
        t = np.inf if m > 0 else (-np.inf if m < 0 else np.nan)
    p = float(stats.t.sf(t, df)) if not np.isnan(t) else np.nan
    return m, se, t, p, df


def upper_bound_t(m, se, df=None, level=LEVEL_NOEDGE):
    """Analytic one-sided upper bound m + q_level * se (Student t at df, normal if df is None)."""
    q = stats.t.ppf(level, df) if df else stats.norm.ppf(level)
    return m + q * se


def _cluster_boot_t(x, g, B, seed, chunk=2000):
    """Month-cluster bootstrap-t draws t*_b = (mean*_b - mean) / se*_b (clusters resampled with replacement;
    duplicated clusters count as distinct). Returns (mean, se, G, t_star)."""
    _, inv = np.unique(g, return_inverse=True)
    s = np.bincount(inv, weights=x)
    c = np.bincount(inv).astype(float)
    G = len(s)
    m = float(x.mean())
    v, _ = _cl_var(x - m, g)
    se = math.sqrt(v) if np.isfinite(v) else np.nan
    rng = np.random.default_rng(seed)
    out = np.empty(B)
    f = G / (G - 1)
    for k0 in range(0, B, chunk):
        nb = min(chunk, B - k0)
        idx = rng.integers(0, G, size=(nb, G))
        S, N = s[idx], c[idx]
        mb = S.sum(1) / N.sum(1)
        dev = S - N * mb[:, None]
        seb = np.sqrt(f * (dev * dev).sum(1)) / N.sum(1)
        d = mb - m
        with np.errstate(divide="ignore", invalid="ignore"):
            tb = np.where(seb > 0, d / np.where(seb > 0, seb, 1.0), np.where(d > 0, np.inf, np.where(d < 0, -np.inf, 0.0)))
        out[k0:k0 + nb] = tb
    return m, se, G, out


def boot_t_bounds(x, clusters, levels=(0.95, LEVEL_NOEDGE), B: int = B_TRADE, seed: int = SEED,
                  two_sided: float = 0.95) -> dict:
    """Month-cluster bootstrap-t: one-sided upper bounds at each level, UB = mean - q_{1-level}(t*) * se, and the
    two-sided interval [mean - q_{1-a/2}(t*) se, mean - q_{a/2}(t*) se]."""
    x, g = _clean(x, clusters)
    if len(x) < 2 or len(np.unique(g)) < 2:
        return {"mean": float(x.mean()) if len(x) else np.nan, "se": np.nan, "G": len(np.unique(g)),
                "ub": {lv: np.nan for lv in levels}, "ci": (np.nan, np.nan)}
    m, se, G, tb = _cluster_boot_t(x, g, B, seed)
    ub = {lv: float(m - _q(tb, 1 - lv) * se) for lv in levels}
    a = 1 - two_sided
    ci = (float(m - _q(tb, 1 - a / 2) * se), float(m - _q(tb, a / 2) * se))
    return {"mean": m, "se": se, "G": G, "ub": ub, "ci": ci}


def boot_t_upper(x, clusters, level: float = LEVEL_NOEDGE, B: int = B_TRADE, seed: int = SEED) -> float:
    """Month-cluster bootstrap-t one-sided upper confidence bound of the mean at `level` (NO EDGE bounds)."""
    return boot_t_bounds(x, clusters, (level,), B, seed)["ub"][level]


def ratio_cluster(num, den, clusters):
    """R = sum(num) / sum(den) with a one-way clustered delta-method SE (H3's exposure-time unit).
    Linearisation z_i = (num_i - R den_i) / mean(den). Returns (R, se, df)."""
    num = np.asarray(num, float); den = np.asarray(den, float); g = np.asarray(clusters)
    k = np.isfinite(num) & np.isfinite(den)
    num, den, g = num[k], den[k], g[k]
    if len(num) == 0 or den.sum() == 0:
        return np.nan, np.nan, 0
    R = num.sum() / den.sum()
    z = (num - R * den) / den.mean()
    v, G = _cl_var(z, g)
    return float(R), (math.sqrt(v) if np.isfinite(v) else np.nan), max(G - 1, 0)


def ratio_diff_cluster(num_a, den_a, cl_a, num_b, den_b, cl_b):
    """R_a - R_b for two trade sets sharing month clusters (delta method; covariance through common months).
    Returns (dR, se, df), df = G - 1 with G = months with a trade in either set."""
    pa = [np.asarray(v) for v in (num_a, den_a, cl_a)]
    pb = [np.asarray(v) for v in (num_b, den_b, cl_b)]
    out = []
    for num, den, g in (pa, pb):
        num = num.astype(float); den = den.astype(float)
        k = np.isfinite(num) & np.isfinite(den)
        num, den, g = num[k], den[k], g[k]
        R = num.sum() / den.sum()
        out.append((R, (num - R * den) / den.sum(), g))   # contribution to R_hat - R
    (Ra, za, ga), (Rb, zb, gb) = out
    g = np.r_[ga, gb]
    e = np.r_[za, -zb]
    _, inv = np.unique(g, return_inverse=True)
    s = np.bincount(inv, weights=e)
    G = len(s)
    if G < 2:
        return float(Ra - Rb), np.nan, 0
    return float(Ra - Rb), math.sqrt(G / (G - 1) * float(s @ s)), G - 1


def cluster_ols(y, X, clusters):
    """OLS of y on X with one-way clustered SEs (CR1 with the factor G/(G-1) only, so an intercept-only fit equals
    cluster_t). A 1-D X gets an intercept column prepended; a 2-D X is used as given.
    Returns (beta, se, t, one-sided p for beta > 0, df = G - 1), arrays over the columns."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = np.column_stack([np.ones(len(X)), X])
    g = np.asarray(clusters)
    k = np.isfinite(y) & np.isfinite(X).all(1)
    y, X, g = y[k], X[k], g[k]
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    _, inv = np.unique(g, return_inverse=True)
    G = inv.max() + 1
    sc = np.zeros((G, X.shape[1]))
    np.add.at(sc, inv, X * e[:, None])
    meat = sc.T @ sc
    V = (G / (G - 1)) * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    df = G - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        t = beta / se
    p = stats.t.sf(t, df)
    return beta, se, t, p, df


def paired_signal_diff(base_trades: pd.DataFrame, var_trades: pd.DataFrame, key="signal_day",
                       col="ret_adj", time_col: str = "entry1_time") -> pd.DataFrame:
    """Per-signal paired difference over the UNION of both variants' signals (prereg "Per-signal paired tests").
    A signal one variant skips counts 0 for it; several trades with the same key are summed.
    key: a column name (paired as (sym, key) when both frames have sym) or a list of columns.
    col: value column(s); with one column the output has base, var, diff (= var - base); with a list,
      base_<c>, var_<c>, diff_<c>. Also in_base, in_var and month (entry month of the base trade, else the
      variant's; the cluster label)."""
    cols = [col] if isinstance(col, str) else list(col)
    if isinstance(key, str):
        keys = (["sym", key] if "sym" in base_trades.columns and "sym" in var_trades.columns else [key])
    else:
        keys = list(key)

    def agg(t):
        f = t[keys + cols].copy()
        f["_n"] = 1
        if time_col in t.columns:
            f["_t"] = _naive_utc(t[time_col])
        a = {c: "sum" for c in cols}
        a["_n"] = "sum"
        if "_t" in f:
            a["_t"] = "min"
        return f.groupby(keys, sort=False, dropna=False).agg(a)

    A, Bv = agg(base_trades), agg(var_trades)
    U = A.join(Bv, how="outer", lsuffix="_b", rsuffix="_v").sort_index()
    out = pd.DataFrame(index=U.index)
    for c in cols:
        b = U[f"{c}_b"].fillna(0.0).to_numpy(float) if f"{c}_b" in U else U[c].fillna(0.0).to_numpy(float)
        v = U[f"{c}_v"].fillna(0.0).to_numpy(float)
        sfx = "" if len(cols) == 1 else f"_{c}"
        out["base" + sfx] = b
        out["var" + sfx] = v
        out["diff" + sfx] = v - b
    out["in_base"] = U["_n_b"].notna().to_numpy()
    out["in_var"] = U["_n_v"].notna().to_numpy()
    if "_t_b" in U and "_t_v" in U:
        t = U["_t_b"].where(U["_t_b"].notna(), U["_t_v"])
        out["month"] = month_key(t)
    else:
        lvl = U.index.get_level_values(keys[-1]) if isinstance(U.index, pd.MultiIndex) else U.index
        out["month"] = month_key(lvl)
    return out.reset_index()


def mde(se, df=None, alpha: float = ALPHA / N_FAMILY, power: float = 0.80):
    """Minimum detectable effect (z_{1-alpha} + z_{power}) * SE; (2.638 + 0.842) * SE at the Holm level."""
    q = stats.t.ppf(1 - alpha, df) if df else stats.norm.ppf(1 - alpha)
    return (q + stats.norm.ppf(power)) * np.asarray(se, float)


def trade_test(x, clusters, E_: float, B: int = B_TRADE, seed: int = SEED, level_noedge: float = LEVEL_NOEDGE,
               mde_df=None) -> dict:
    """Everything a trade-level or paired row reports: the month-clustered mean, SE, t, one-sided p at G-1 df,
    the analytic 95% interval, the bootstrap-t bounds (95% = the largest effect ruled out; level_noedge = the
    NO EDGE bound) and interval, the MDE and whether the NO EDGE bound is below E."""
    m, se, t, p, df = cluster_t(x, clusters)
    bb = boot_t_bounds(x, clusters, (0.95, level_noedge), B, seed)
    q975 = stats.t.ppf(0.975, df) if df else np.nan
    return {"n": int(np.isfinite(np.asarray(x, float)).sum()), "G": df + 1 if df else 0, "mean": m, "se": se,
            "t": t, "p": p, "df": df, "ci95": (m - q975 * se, m + q975 * se), "ci95_boot": bb["ci"],
            "ub95": bb["ub"][0.95], "ub_noedge": bb["ub"][level_noedge], "level_noedge": level_noedge,
            "mde": float(mde(se, mde_df)), "E": E_, "noedge": bool(bb["ub"][level_noedge] < E_)}


# ============================================================================ portfolio-level tests

def sb_indices(T: int, mean_block: float, n: int, rng):
    """n stationary-bootstrap index paths of length T (Politis-Romano 1994): a new block starts with probability
    1/mean_block at each step, at a uniform random start; indices wrap around. Returns (idx, block_id), both
    (n, T); block_id numbers the blocks within each row from 0."""
    p = min(1.0, 1.0 / max(mean_block, 1.0))
    new = rng.random((n, T)) < p
    new[:, 0] = True
    starts = rng.integers(0, T, size=(n, T))
    tt = np.arange(T)
    last = np.where(new, tt, 0)
    np.maximum.accumulate(last, axis=1, out=last)
    idx = (np.take_along_axis(starts, last, axis=1) + (tt - last)) % T
    blk = np.cumsum(new, axis=1) - 1
    return idx, blk


def _align(a, b):
    if b is None:
        if isinstance(a, pd.Series):
            a = a.to_numpy(float)
        a = np.asarray(a, float)
        return a[np.isfinite(a)], None
    if isinstance(a, pd.Series) and isinstance(b, pd.Series):
        j = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
        return j["a"].to_numpy(float), j["b"].to_numpy(float)
    a = np.asarray(a, float); b = np.asarray(b, float)
    if len(a) != len(b):
        raise ValueError("a and b must be aligned (same days)")
    k = np.isfinite(a) & np.isfinite(b)
    return a[k], b[k]


def _sharpe_parts(a, b):
    """Sharpe difference (per period) and the delta-method gradient on (mu_a, mu_b, g_a, g_b), g = E r^2
    (Ledoit-Wolf 2008, eq. 2-3). With b None, the Sharpe of a alone."""
    mu_a, g_a = a.mean(), (a * a).mean()
    va = g_a - mu_a ** 2
    if b is None:
        return mu_a / math.sqrt(va), np.array([g_a / va ** 1.5, -0.5 * mu_a / va ** 1.5])
    mu_b, g_b = b.mean(), (b * b).mean()
    vb = g_b - mu_b ** 2
    d = mu_a / math.sqrt(va) - mu_b / math.sqrt(vb)
    grad = np.array([g_a / va ** 1.5, -g_b / vb ** 1.5, -0.5 * mu_a / va ** 1.5, 0.5 * mu_b / vb ** 1.5])
    return d, grad


def _moments(a, b):
    if b is None:
        return np.column_stack([a - a.mean(), a * a - (a * a).mean()])
    return np.column_stack([a - a.mean(), b - b.mean(), a * a - (a * a).mean(), b * b - (b * b).mean()])


def _autocov_all(E_):
    """Gamma_j[a, b] = (1/T) sum_t e_{t,a} e_{t-j,b} for j = 0..T-1 by FFT. Returns (T, k, k)."""
    T, k = E_.shape
    nf = 1 << int(math.ceil(math.log2(2 * T)))
    F = np.fft.rfft(E_, n=nf, axis=0)
    out = np.empty((T, k, k))
    for i in range(k):
        for j in range(k):
            cc = np.fft.irfft(F[:, i] * np.conj(F[:, j]), n=nf)[:T]
            out[:, i, j] = cc / T
    return out


def _qs(x):
    x = np.asarray(x, float)
    out = np.ones_like(x)
    nz = x != 0
    z = 6 * np.pi * x[nz] / 5
    out[nz] = 25 / (12 * np.pi ** 2 * x[nz] ** 2) * (np.sin(z) / z - np.cos(z))
    return out


def hac_qs_prewhitened(V):
    """Ledoit-Wolf (2008) HAC long-run covariance of the moment series V (T x k, centred): VAR(1) prewhitening,
    quadratic-spectral kernel with the Andrews (1991) AR(1) plug-in bandwidth 1.3221 (alpha(2) T)^(1/5) on the
    whitened residuals, recoloured by (I - A)^-1, times the small-sample factor T / (T - k) (LW's T / (T - 4) for
    the four moments of a Sharpe difference)."""
    T, k = V.shape
    X, Y = V[:-1], V[1:]
    A = np.linalg.lstsq(X, Y, rcond=None)[0].T          # Y_t = A Y_{t-1} + e_t
    # Andrews-Monahan: shrink A if it is close to non-stationary (singular values capped at 0.97)
    U_, sv, Vt = np.linalg.svd(A)
    if sv.max() > 0.97:
        A = U_ @ np.diag(np.minimum(sv, 0.97)) @ Vt
    Er = Y - X @ A.T
    n = len(Er)
    num = den = 0.0
    for j in range(k):
        e = Er[:, j]
        rho = float(e[1:] @ e[:-1] / (e[:-1] @ e[:-1])) if (e[:-1] @ e[:-1]) > 0 else 0.0
        rho = max(min(rho, 0.97), -0.97)
        s2 = float(((e[1:] - rho * e[:-1]) ** 2).mean())
        num += 4 * rho ** 2 * s2 ** 2 / (1 - rho) ** 8
        den += s2 ** 2 / (1 - rho) ** 4
    alpha2 = num / den if den > 0 else 0.0
    S = 1.3221 * (alpha2 * n) ** 0.2 if alpha2 > 0 else 0.0
    G = _autocov_all(Er)
    Psi_e = G[0].copy()
    if S > 0:
        w = _qs(np.arange(1, n) / S)
        Psi_e += np.einsum("j,jab->ab", w, G[1:]) + np.einsum("j,jba->ab", w, G[1:])
    D = np.linalg.inv(np.eye(k) - A)
    Psi = D @ Psi_e @ D.T
    return Psi * T / (T - k)


def _sb_kernel_var(u, mean_block):
    """Long-run variance of a scalar series with the kernel the stationary bootstrap implies (Politis-Romano
    1994): R(0) + 2 sum_k [(1 - k/T)(1-p)^k + (k/T)(1-p)^(T-k)] R(k), p = 1/mean_block."""
    u = np.asarray(u, float) - np.mean(u)
    T = len(u)
    R = _autocov_all(u[:, None])[:, 0, 0]
    p = min(1.0, 1.0 / max(mean_block, 1.0))
    kk = np.arange(1, T)
    w = (1 - kk / T) * (1 - p) ** kk + (kk / T) * (1 - p) ** (T - kk)
    return float(R[0] + 2 * (w * R[1:]).sum())


def block_boot(a, b=None, stat: str = "mean", mean_block_days: float = MONTH_DAYS, B: int = B_PORT,
               seed: int = SEED, level: float = LEVEL_NOEDGE, ppy: int = 365, se_method: str = "qs",
               chunk: int | None = None) -> dict:
    """Paired stationary block bootstrap of a daily statistic (prereg "Portfolio-level tests").
    stat: "mean"        mean daily a (or a - b);
          "logdiff"     mean daily log(1 + a) - log(1 + b) (or log(1 + a)); a, b simple returns;
          "sharpe_diff" Sharpe(a) - Sharpe(b) (or Sharpe(a)) on excess returns, studentized (Ledoit-Wolf 2008).
    a and b: arrays on the same days, or Series aligned on their common index (rows with a NaN dropped).
    Returns estimate, se (the deciding SE), one-sided p for > 0, ub at `level`, ub95, ci95 (all annualized:
    mean/logdiff * ppy, Sharpe * sqrt(ppy)), daily estimate, t_hat (Sharpe), T, B, mean_block, ruin flag."""
    a, b = _align(a, b)
    T = len(a)
    rng = np.random.default_rng(seed)
    chunk = chunk or max(1, int(2_000_000 // max(T, 1)))
    res = {"stat": stat, "T": T, "B": B, "mean_block": float(mean_block_days), "level": level, "ppy": ppy,
           "ruin": False}
    if stat in ("mean", "logdiff"):
        if stat == "logdiff":
            if (1 + a <= 0).any() or (b is not None and (1 + b <= 0).any()):
                ruin_a = bool((1 + a <= 0).any())
                est = -np.inf if ruin_a else np.inf
                res.update(estimate=est, daily_estimate=est, se=np.nan, p=1.0 if ruin_a else 0.0, ub=est, ub95=est,
                           ci95=(est, est), ruin=True, se_hac=np.nan)
                return res
            d = np.log1p(a) - (np.log1p(b) if b is not None else 0.0)
        else:
            d = a - (b if b is not None else 0.0)
        th = float(d.mean())
        draws = np.empty(B)
        for k0 in range(0, B, chunk):
            nb = min(chunk, B - k0)
            idx, _ = sb_indices(T, mean_block_days, nb, rng)
            draws[k0:k0 + nb] = d[idx].mean(1)
        p = (1 + np.sum(draws - th >= th)) / (B + 1)
        ann = ppy
        res.update(estimate=th * ann, daily_estimate=th, se=float(draws.std(ddof=1)) * ann, p=float(p),
                   ub=float(2 * th - _q(draws, 1 - level)) * ann, ub95=float(2 * th - _q(draws, 0.05)) * ann,
                   ci95=(float(2 * th - _q(draws, 0.975)) * ann, float(2 * th - _q(draws, 0.025)) * ann),
                   se_hac=math.sqrt(max(_sb_kernel_var(d, mean_block_days), 0) / T) * ann)
        return res
    if stat != "sharpe_diff":
        raise ValueError(f"unknown stat {stat}")
    th, grad = _sharpe_parts(a, b)
    V = _moments(a, b)
    if se_method == "qs":
        Psi = hac_qs_prewhitened(V)
        se = math.sqrt(max(float(grad @ Psi @ grad), 0.0) / T)
    elif se_method == "sb":
        se = math.sqrt(max(_sb_kernel_var(V @ grad, mean_block_days), 0.0) / T)
    else:
        raise ValueError(se_method)
    t_hat = th / se if se > 0 else np.nan
    tstar = np.empty(B)
    dstar = np.empty(B)
    for k0 in range(0, B, chunk):
        nb = min(chunk, B - k0)
        idx, blk = sb_indices(T, mean_block_days, nb, rng)
        A_ = a[idx]
        mu_a, g_a = A_.mean(1), (A_ * A_).mean(1)
        va = g_a - mu_a ** 2
        if b is not None:
            B_ = b[idx]
            mu_b, g_b = B_.mean(1), (B_ * B_).mean(1)
            vb = g_b - mu_b ** 2
            d = mu_a / np.sqrt(va) - mu_b / np.sqrt(vb)
            u = ((g_a / va ** 1.5)[:, None] * (A_ - mu_a[:, None])
                 - (g_b / vb ** 1.5)[:, None] * (B_ - mu_b[:, None])
                 - (0.5 * mu_a / va ** 1.5)[:, None] * (A_ * A_ - g_a[:, None])
                 + (0.5 * mu_b / vb ** 1.5)[:, None] * (B_ * B_ - g_b[:, None]))
        else:
            d = mu_a / np.sqrt(va)
            u = ((g_a / va ** 1.5)[:, None] * (A_ - mu_a[:, None])
                 - (0.5 * mu_a / va ** 1.5)[:, None] * (A_ * A_ - g_a[:, None]))
        gid = (blk + (np.arange(nb) * T)[:, None]).ravel()
        Z = np.bincount(gid, weights=u.ravel(), minlength=nb * T).reshape(nb, T)
        seb = np.sqrt((Z * Z).sum(1)) / T
        tstar[k0:k0 + nb] = (d - th) / seb
        dstar[k0:k0 + nb] = d
    tstar = tstar[np.isfinite(tstar)]
    p = (1 + np.sum(tstar >= t_hat)) / (len(tstar) + 1)
    ann = math.sqrt(ppy)
    res.update(estimate=th * ann, daily_estimate=th, se=se * ann, t_hat=t_hat, p=float(p),
               ub=float(th - _q(tstar, 1 - level) * se) * ann, ub95=float(th - _q(tstar, 0.05) * se) * ann,
               ci95=(float(th - _q(tstar, 0.975) * se) * ann, float(th - _q(tstar, 0.025) * se) * ann),
               se_boot=float(dstar.std(ddof=1)) * ann, se_method=se_method, B_valid=len(tstar))
    return res


def portfolio_test(a, b=None, stat: str = "sharpe_diff", kind: str = "crypto", months=(1, 3, 12),
                   B: int = B_PORT, seed: int = SEED, level: float = LEVEL_NOEDGE, block_days: float | None = None,
                   **kw) -> dict:
    """block_boot at mean blocks of 1, 3 and 12 months (365/12 days crypto, 252/12 sessions stocks); the verdict
    p is the larger of the 1- and 3-month p and the NO EDGE bound the larger of their bounds. block_days
    overrides with one block length (H10: 28 days), whose p and bound then decide."""
    ppy = PPY[kind]
    unit = MONTH_DAYS if kind == "crypto" else MONTH_SESSIONS
    if block_days is not None:
        r = block_boot(a, b, stat, block_days, B, seed, level, ppy, **kw)
        return {"by_block": {block_days: r}, "p": r["p"], "ub": r["ub"], "estimate": r["estimate"],
                "se": r["se"], "ci95": r["ci95"], "ub95": r["ub95"]}
    by = {m: block_boot(a, b, stat, m * unit, B, seed, level, ppy, **kw) for m in months}
    dec = [by[m] for m in (1, 3) if m in by]
    r1 = by[months[0]]
    return {"by_block": by, "p": max(r["p"] for r in dec), "ub": max(r["ub"] for r in dec),
            "estimate": r1["estimate"], "se": max(r["se"] for r in dec), "ci95": r1["ci95"],
            "ub95": max(r["ub95"] for r in dec)}


# ============================================================================ multiplicity and verdicts

def bh(p):
    """Benjamini-Hochberg adjusted p-values (step-up); NaN entries are left out of m and stay NaN."""
    p = np.asarray(p, float)
    out = np.full(len(p), np.nan)
    ok = np.where(np.isfinite(p))[0]
    m = len(ok)
    if m == 0:
        return out
    q = p[ok]
    o = np.argsort(q, kind="stable")
    adj = q[o] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    res = np.empty(m)
    res[o] = np.minimum(adj, 1.0)
    out[ok] = res
    return out


def iu_p(ps) -> float:
    """Intersection-union p of a compound test: the largest component p (NaN counts as 1)."""
    ps = np.asarray(ps, float)
    return float(np.max(np.where(np.isfinite(ps), ps, 1.0)))


def verdict(p_holm, conds_ok: bool, ub, E_) -> str:
    """PASS if the Holm-adjusted p < 0.05 and every other condition holds; else NO EDGE if a component's one-sided
    upper bound (level 1 - 0.05/12) is below its threshold E, reported as "NO EDGE (HARMS)" when a bound is below
    0; else INCONCLUSIVE. ub and E may be scalars or equal-length sequences (one per component)."""
    if p_holm is not None and np.isfinite(p_holm) and p_holm < ALPHA and bool(conds_ok):
        return "PASS"
    ubs = np.atleast_1d(np.asarray(ub, float))
    Es = np.broadcast_to(np.atleast_1d(np.asarray(E_, float)), ubs.shape)
    below = np.isfinite(ubs) | np.isneginf(ubs)
    below = below & (ubs < Es)
    if below.any():
        return "NO EDGE (HARMS)" if (below & (ubs < 0)).any() else "NO EDGE"
    return "INCONCLUSIVE"


# ============================================================================ reporting helpers

def drop_worst_month(x, months):
    """Mean after removing the single entry month whose removal lowers it most. Returns (mean_after, month)."""
    x, g = _clean(x, months)
    return drop_worst(x, g)


def top_share(pnl, q: float = 0.05) -> float:
    """Share of total P&L from the top q of trades (the ceil(q n) largest P&Ls over the sum of all P&Ls)."""
    v = np.asarray(pnl, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.nan
    k = max(1, int(math.ceil(q * len(v))))
    tot = v.sum()
    return float(np.sort(v)[::-1][:k].sum() / tot) if tot != 0 else np.nan


# ============================================================================ built-in synthetic trade generator

@njit(cache=True)
def _indicators(Pf, nd, n_bb, k_bb):
    """Daily bars of an hourly close path Pf (Pf[0] = start, Pf[1 + h] = close of hour h) and S1's indicators."""
    O = np.empty(nd); H = np.empty(nd); L = np.empty(nd); C = np.empty(nd)
    for d in range(nd):
        O[d] = Pf[d * 24]
        hi = O[d]; lo = O[d]
        for h in range(d * 24 + 1, (d + 1) * 24 + 1):
            if Pf[h] > hi:
                hi = Pf[h]
            if Pf[h] < lo:
                lo = Pf[h]
        H[d] = hi; L[d] = lo; C[d] = Pf[(d + 1) * 24]
    sma = np.full(nd, np.nan); ub = np.full(nd, np.nan); atr = np.full(nd, np.nan)
    hi60 = np.empty(nd); ath = np.empty(nd)
    for t in range(n_bb - 1, nd):
        s = 0.0
        for i in range(t - n_bb + 1, t + 1):
            s += C[i]
        m = s / n_bb
        v = 0.0
        for i in range(t - n_bb + 1, t + 1):
            v += (C[i] - m) ** 2
        sma[t] = m; ub[t] = m + k_bb * math.sqrt(v / n_bb)
    tr = np.empty(nd); tr[0] = H[0] - L[0]
    for d in range(1, nd):
        tr[d] = max(H[d] - L[d], abs(H[d] - C[d - 1]), abs(L[d] - C[d - 1]))
    if nd > 15:
        s = 0.0
        for d in range(1, 15):
            s += tr[d]
        atr[14] = s / 14
        for d in range(15, nd):
            atr[d] = (atr[d - 1] * 13 + tr[d]) / 14
    mx = -1.0
    for d in range(nd):
        if H[d] > mx:
            mx = H[d]
        ath[d] = mx
        h60 = H[d]
        for i in range(max(0, d - 59), d + 1):
            if H[i] > h60:
                h60 = H[i]
        hi60[d] = h60
    return C, sma, ub, atr, hi60, ath


@njit(cache=True)
def _sim_s1(Pf, nd, sma, ub, atr, hi60, ath, cost_side, warm):
    """A simplified S1 on hourly closes: fresh close above BB(20,2) near the 60-day high or 0.9 ATH; entry at the
    01:00 UTC open after the signal (M/3), adds of M/3 at hourly closes >= 1.02 / 1.05 x entry1 (filled at that
    close = the next open), stop S = SMA20 - ATR14 and 3R TP on half checked on hourly closes and filled there,
    midline exit at the next 01:00 UTC open. Every fill is at a path price, so on a martingale E[gross] = 0.
    Exposure: expo_n[h] = units held through hour h * open of hour h (notional / M), expo_id[h] = trade id."""
    nh = nd * 24
    mt = nd
    sig = np.empty(mt, np.int64); eh = np.empty(mt, np.int64); xh = np.empty(mt, np.int64)
    ret = np.empty(mt); gross = np.empty(mt); ntr = np.empty(mt, np.int64); mfr = np.empty(mt)
    oend = np.zeros(mt, np.bool_)
    expo_n = np.zeros(nh); expo_id = np.full(nh, -1, np.int64)
    k = 0
    t = warm
    while t < nd - 1:
        Ct = Pf[(t + 1) * 24]
        Cp = Pf[t * 24]
        if not (Ct > ub[t] and Cp <= ub[t - 1] and (Ct >= 0.95 * hi60[t] or (t >= 364 and Ct >= 0.9 * ath[t]))):
            t += 1
            continue
        he = (t + 1) * 24 + 1
        if he >= nh:
            break
        e1 = Pf[he]
        S = sma[t] - atr[t]
        if not (e1 > S):
            t += 1
            continue
        TP = e1 + 3.0 * (e1 - S)
        u = (1.0 / 3.0) / e1
        bought = 1.0 / 3.0
        cash = -bought
        cost = cost_side * bought
        nadd = 0; tp = False; pend = -1; n_t = 1; frac = 1.0 / 3.0
        h = he
        done = False
        while h < nh:
            expo_n[h] = u * Pf[h]
            expo_id[h] = k
            c = Pf[h + 1]
            if c <= S:
                cash += u * c; cost += cost_side * u * c; u = 0.0; done = True
                break
            if (not tp) and c >= TP:
                cash += 0.5 * u * c; cost += cost_side * 0.5 * u * c; u *= 0.5; tp = True
            if h == pend:
                cash += u * c; cost += cost_side * u * c; u = 0.0; done = True
                break
            if (not tp) and pend < 0 and nadd < 2:
                want = 2 if c >= 1.05 * e1 else (1 if c >= 1.02 * e1 else 0)
                if want > nadd and c >= bought / u:
                    f = (want - nadd) / 3.0
                    u += f / c; bought += f; cash -= f; cost += cost_side * f
                    n_t += want - nadd; nadd = want; frac = bought
            if (h + 1) % 24 == 0 and pend < 0:
                d = h // 24
                if Pf[h + 1] < sma[d]:
                    pend = h + 1
            h += 1
        if not done:
            cash += u * Pf[nh]
            h = nh - 1
            oend[k] = True
        sig[k] = t; eh[k] = he; xh[k] = h
        gross[k] = cash; ret[k] = cash - cost; ntr[k] = n_t; mfr[k] = frac
        k += 1
        t = max(t + 1, h // 24)
    return (sig[:k], eh[:k], xh[:k], ret[:k], gross[:k], ntr[:k], mfr[:k], oend[:k], expo_n, expo_id)


def simple_three_coin_trades(seed: int, years: float = 6.8, vols=(0.57, 0.75, 0.95), rho: float = 0.8,
                             df_t: int = 4, cost_side: float = 0.0, drift_hourly: float = 0.0,
                             start: str = "2020-01-01") -> dict:
    """Synthetic three-coin path with zero ARITHMETIC drift (simple hourly returns r = sigma z with z standardized
    Student t(df_t), cross-correlation rho, so each price is a martingale; drift_hourly adds a constant) and the
    simplified S1 run on each coin. Returns {"trades", "expo", "rets"} shaped like the engine's output (trades:
    sym, signal_day, entry1_time, exit_time, ret, ret_gross, side, n_tranches, max_frac, open_at_end, pos;
    expo: pos, time, notional, sym; rets: {sym: hourly Series})."""
    rng = np.random.default_rng(seed)
    nd = int(years * 365)
    nh = nd * 24
    k = len(vols)
    Cm = np.full((k, k), rho); np.fill_diagonal(Cm, 1.0)
    z = rng.standard_t(df_t, size=(nh, k)) / math.sqrt(df_t / (df_t - 2)) @ np.linalg.cholesky(Cm).T
    z = np.clip(z, -40, 40)
    r = z * (np.asarray(vols) / math.sqrt(365 * 24)) + drift_hourly
    hours = pd.date_range(start, periods=nh, freq="h", tz="UTC")
    days = pd.date_range(start, periods=nd, freq="D", tz="UTC")
    trades, expos, rets = [], [], {}
    for c in range(k):
        sym = f"C{c}"
        Pf = np.r_[100.0, 100.0 * np.cumprod(1.0 + r[:, c])]
        C, sma, ub, atr, hi60, ath = _indicators(Pf, nd, 20, 2.0)
        sg, eh, xh, ret, gross, ntr, mfr, oend, en, eid = _sim_s1(Pf, nd, sma, ub, atr, hi60, ath, cost_side, 60)
        trades.append(pd.DataFrame({"sym": sym, "pos": np.arange(len(sg)), "signal_day": days[sg],
                                    "entry1_time": hours[eh], "exit_time": hours[xh] + pd.Timedelta("1h"),
                                    "ret": ret, "ret_gross": gross, "side": 1, "n_tranches": ntr,
                                    "max_frac": mfr, "open_at_end": oend}))
        m = eid >= 0
        expos.append(pd.DataFrame({"pos": eid[m], "time": hours[m], "notional": en[m], "sym": sym}))
        rets[sym] = pd.Series(Pf[1:] / Pf[:-1] - 1.0, index=hours)
    return {"trades": pd.concat(trades, ignore_index=True), "expo": pd.concat(expos, ignore_index=True),
            "rets": rets}


def builtin_sim(seed: int) -> pd.DataFrame:
    """Default sim_fn of inference_control: the built-in three-coin path (zero arithmetic drift, rho 0.8, no costs)
    with drift-adjusted returns."""
    out = simple_three_coin_trades(seed)
    tr = out["trades"]
    tr["ret_adj"] = drift_adjust(tr, out["expo"], out["rets"]).to_numpy()
    return tr


# ============================================================================ inference control

LEVEL_GRID = (0.95, 0.955, 0.96, 0.965, 0.97, 0.975, 0.98, 0.985, 0.99, 0.995, LEVEL_NOEDGE, 0.9975, 0.999)


def _binom_ci(k, n):
    lo = stats.beta.ppf(0.025, k, n - k + 1) if k > 0 else 0.0
    hi = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return float(lo), float(hi)


def inference_control(sim_fn=None, n_paths: int = 200, seed: int = SEED, col: str | None = None,
                      true_mean: float | None = None, B: int = B_TRADE, alpha: float = ALPHA,
                      n_jobs: int = 1, level_grid=LEVEL_GRID) -> dict:
    """The pre-registration's "Inference known answer" control. sim_fn(seed: int) -> trades DataFrame for one
    synthetic three-coin path with zero arithmetic drift and cross-correlation 0.8 (the orchestrator wires it to
    the engine; default: builtin_sim). Each frame needs the value column (col; default ret_adj, else ret) and
    entry1_time (or a `month` column). Reports H1's month-clustered rejection rate at a nominal one-sided 5%
    (vs 0 and centred at the true mean) and the rate at which the month-cluster bootstrap-t bound at each level
    falls below the true mean; level_widened is the smallest grid level whose miss rate is <= 5%."""
    sim_fn = sim_fn or builtin_sim
    seeds = [int(s) for s in np.random.default_rng(seed).integers(0, 2 ** 62, n_paths)]
    if n_jobs > 1:
        with cf.ProcessPoolExecutor(n_jobs) as ex:
            frames = list(ex.map(sim_fn, seeds))
    else:
        frames = [sim_fn(s) for s in seeds]
    paths = []
    for f in frames:
        c = col or ("ret_adj" if "ret_adj" in f.columns else "ret")
        g = f["month"].to_numpy() if "month" in f.columns else month_key(f["entry1_time"])
        x = f[c].to_numpy(float)
        k = np.isfinite(x)
        paths.append((x[k], g[k]))
    allx = np.concatenate([x for x, _ in paths])
    mu = float(allx.mean()) if true_mean is None else float(true_mean)
    rej0 = rejc = 0
    miss = {lv: 0 for lv in level_grid}
    miss_an = 0
    n_ok = 0
    ns, Gs = [], []
    for i, (x, g) in enumerate(paths):
        m, se, t, p, df = cluster_t(x, g)
        if not np.isfinite(se):
            continue
        n_ok += 1
        ns.append(len(x)); Gs.append(df + 1)
        rej0 += p < alpha
        rejc += stats.t.sf((m - mu) / se, df) < alpha
        bb = boot_t_bounds(x, g, level_grid, B, seed + i)
        for lv in level_grid:
            miss[lv] += bb["ub"][lv] < mu
        miss_an += upper_bound_t(m, se, df, 0.95) < mu
    rate = {lv: miss[lv] / n_ok for lv in level_grid}
    widened = next((lv for lv in level_grid if rate[lv] <= 0.05), None)
    k95 = miss[0.95]
    return {"n_paths": n_ok, "true_mean": mu, "true_mean_source": "given" if true_mean is not None else "grand mean",
            "mean_trades_per_path": float(np.mean(ns)), "mean_G": float(np.mean(Gs)),
            "reject_rate": rej0 / n_ok, "reject_ci": _binom_ci(rej0, n_ok),
            "reject_rate_centered": rejc / n_ok,
            "miss_rate_95": rate[0.95], "miss_ci_95": _binom_ci(k95, n_ok),
            "miss_rate_analytic_95": miss_an / n_ok, "miss_rate_noedge": rate[LEVEL_NOEDGE],
            "miss_rate_by_level": rate,
            "ok_reject": rej0 / n_ok <= 0.05, "ok_miss": rate[0.95] <= 0.05,
            "ok_reject_binomial": stats.binom.sf(rej0 - 1, n_ok, 0.05) > 0.05,
            "ok_miss_binomial": stats.binom.sf(k95 - 1, n_ok, 0.05) > 0.05,
            "level_widened": None if rate[0.95] <= 0.05 else widened}


# ============================================================================ selftest

def _check_cluster_t(say):
    x = np.array([1.0, 2, 3, 4, 5, 6]); g = np.array(["a", "a", "b", "b", "c", "c"])
    # hand: mean 3.5, deviations -2.5 -1.5 | -0.5 0.5 | 1.5 2.5 -> cluster sums -4, 0, 4; sum sq 32;
    # var = 3/2 * 32 / 36 = 4/3; se = 1.154700538; t = 3.031088913; df 2
    m, se, t, p, df = cluster_t(x, g)
    se_hand = se
    assert m == 3.5 and df == 2 and abs(se - math.sqrt(4 / 3)) < 1e-12 and abs(t - 3.5 / math.sqrt(4 / 3)) < 1e-12
    p_hand = 0.5 - 0.5 * (t / math.sqrt(2 + t * t))           # Student t(2) survival function in closed form
    assert abs(p - p_hand) < 1e-12, (p, p_hand)
    # NaN dropped; one cluster -> no SE
    m2, se2, *_ = cluster_t(np.append(x, np.nan), np.append(g, "d"))
    assert m2 == 3.5 and abs(se2 - se) < 1e-15
    assert np.isnan(cluster_t([1.0, 2.0], [0, 0])[1])
    # a second hand case with unequal clusters
    x = np.array([0.10, -0.05, 0.02, 0.30, -0.20]); g = np.array([1, 1, 2, 3, 3])
    mm = x.mean(); s = np.array([x[:2].sum() - 2 * mm, x[2] - mm, x[3:].sum() - 2 * mm])
    se_h = math.sqrt(1.5 * (s ** 2).sum() / 25)
    m, se, t, p, df = cluster_t(x, g)
    assert abs(m - mm) < 1e-15 and abs(se - se_h) < 1e-15 and abs(p - stats.t.sf(mm / se_h, 2)) < 1e-15
    say(f"  cluster_t: hand case mean 3.5, se {se_hand:.9f} = sqrt(4/3), df 2, p {p_hand:.6f} (t(2) closed form); "
        "an unequal-cluster case matches the formula term by term")
    # ratio_cluster vs cluster_t on the linearisation; ratio_diff with b empty-of-overlap
    rng = np.random.default_rng(1)
    den = rng.uniform(1, 3, 40); num = rng.normal(0.1, 1, 40) * den; gg = rng.integers(0, 12, 40)
    R, se_r, dfr = ratio_cluster(num, den, gg)
    z = (num - R * den) / den.mean()
    assert abs(R - num.sum() / den.sum()) < 1e-15 and abs(se_r - cluster_t(z, gg)[1]) < 1e-12
    d, se_d, _ = ratio_diff_cluster(num, den, gg, num, den, gg)
    assert abs(d) < 1e-15 and se_d < 1e-12                      # identical sets: zero difference, zero SE
    d2, se_d2, _ = ratio_diff_cluster(num, den, gg, num[:20], den[:20] * 2, gg[:20] + 100)
    R2 = num[:20].sum() / (2 * den[:20]).sum()
    se_b = ratio_cluster(num[:20], den[:20] * 2, gg[:20])[1]
    G1, G2 = len(np.unique(gg)), len(np.unique(gg[:20]))
    Gt = G1 + G2
    v_ind = (Gt / (Gt - 1)) * ((G1 - 1) / G1 * se_r ** 2 + (G2 - 1) / G2 * se_b ** 2)  # disjoint months
    assert abs(d2 - (R - R2)) < 1e-14 and abs(se_d2 - math.sqrt(v_ind)) < 1e-12
    say("  ratio_cluster = clustered SE of the linearisation; ratio_diff_cluster: identical sets give 0 +- 0, "
        "disjoint months give the independent-sum variance")


def _check_cluster_ols(say):
    rng = np.random.default_rng(2)
    n = 300
    g = rng.integers(0, 40, n)
    d = (rng.random(n) < 0.4).astype(float)
    y = 0.01 + 0.02 * d + rng.normal(0, 0.05, n) + rng.normal(0, 0.03, 40)[g]
    beta, se, t, p, df = cluster_ols(y, np.ones(n)[:, None], g)
    m, se1, t1, p1, df1 = cluster_t(y, g)
    assert abs(beta[0] - m) < 1e-14 and abs(se[0] - se1) < 1e-14 and abs(p[0] - p1) < 1e-12 and df == df1
    beta, se, t, p, df = cluster_ols(y, d, g)
    assert abs(beta[1] - (y[d == 1].mean() - y[d == 0].mean())) < 1e-14 and abs(beta[0] - y[d == 0].mean()) < 1e-14
    # sandwich by explicit loops
    X = np.column_stack([np.ones(n), d]); e = y - X @ beta
    XtXi = np.linalg.inv(X.T @ X); meat = np.zeros((2, 2))
    for c in np.unique(g):
        sc = X[g == c].T @ e[g == c]; meat += np.outer(sc, sc)
    G = len(np.unique(g))
    se_h = np.sqrt(np.diag(G / (G - 1) * XtXi @ meat @ XtXi))
    assert np.allclose(se, se_h, rtol=1e-12) and df == G - 1
    say(f"  cluster_ols: intercept-only = cluster_t; dummy coefficient = difference of group means; sandwich "
        f"matches an explicit loop (se {se[1]:.5f}, df {df})")


def _check_boot_t(say, reps=1000, B=999):
    """Coverage of one-sided 95% upper bounds on clustered data with a known mean (0): symmetric, trade-like
    right skew (lognormal sigma 0.8: skewness 3.5, close to the built-in S1 generator's 2.9) and a heavy-skew
    stress case (sigma 1.1: skewness 8)."""
    rates = {}
    for lab, sg in (("symmetric", 0.0), ("trade-like skew", 0.8), ("heavy skew", 1.1)):
        rng = np.random.default_rng(3)
        miss_b = miss_a = 0
        for r in range(reps):
            G = 48
            sizes = rng.poisson(1.2, G) + 1
            g = np.repeat(np.arange(G), sizes)
            n = len(g)
            x = (np.exp(rng.normal(0, sg, n)) - math.exp(sg ** 2 / 2)) if sg > 0 else rng.normal(0, 1, n)
            x = 0.03 * x + rng.normal(0, 0.01, G)[g]               # plus a common month shock
            ub = boot_t_bounds(x, g, (0.95,), B, seed=r)["ub"][0.95]
            m, se, t, p, df = cluster_t(x, g)
            miss_b += ub < 0
            miss_a += upper_bound_t(m, se, df, 0.95) < 0
        rates[lab] = (miss_b / reps, miss_a / reps)
    say("  share of 95% upper bounds below the true mean (" + str(reps) + " reps, G 48, B " + str(B) + "; nominal "
        "0.050): " + "; ".join(f"{k} {v[0]:.3f} bootstrap-t vs {v[1]:.3f} analytic t(G-1)" for k, v in rates.items()))
    rb, ra = rates["symmetric"]
    assert 0.03 <= rb <= 0.07, rb
    rb, ra = rates["trade-like skew"]
    assert rb <= 0.08 and rb < ra, (rb, ra)
    rb, ra = rates["heavy skew"]
    assert rb < ra, (rb, ra)
    # singleton clusters: se* is the iid se (sd ddof=1 / sqrt n), i.e. the textbook bootstrap-t
    x = np.random.default_rng(9).normal(size=30)
    assert abs(cluster_t(x, np.arange(30))[1] - x.std(ddof=1) / math.sqrt(30)) < 1e-15
    # B = 9999 path and the ordering of the bounds
    bb = boot_t_bounds(x, np.arange(30) // 2, (0.9, 0.95, LEVEL_NOEDGE), 9999, SEED)
    assert bb["ub"][0.9] < bb["ub"][0.95] < bb["ub"][LEVEL_NOEDGE] and bb["ci"][0] < bb["mean"] < bb["ci"][1]
    assert boot_t_upper(x, np.arange(30) // 2, LEVEL_NOEDGE) == bb["ub"][LEVEL_NOEDGE]


def _check_block_boot(say, reps=400, B=499):
    rng = np.random.default_rng(4)
    # stationary-bootstrap index generator: mean block length and wrap-around
    idx, blk = sb_indices(500, 20.0, 400, rng)
    nblk = blk[:, -1] + 1
    assert abs(500 / nblk.mean() - 20.0) < 1.5, 500 / nblk.mean()
    cont = (np.diff(idx, axis=1) % 500 == 1)
    assert ((np.diff(blk, axis=1) == 0) <= cont).all()            # inside a block the index advances by one
    # p-value formula on a fixed draw set: p = (1 + #{theta* - theta >= theta}) / (B + 1)
    x = rng.normal(0.001, 0.02, 400)
    r = block_boot(x, None, "mean", 10, B=999, seed=7)
    rr = np.random.default_rng(7); dr = np.empty(999)
    for k0 in range(0, 999, max(1, int(2_000_000 // 400))):
        nb = min(max(1, int(2_000_000 // 400)), 999 - k0)
        ii, _ = sb_indices(400, 10, nb, rr); dr[k0:k0 + nb] = x[ii].mean(1)
    th = x.mean()
    assert abs(r["p"] - (1 + np.sum(dr - th >= th)) / 1000) < 1e-15 and abs(r["daily_estimate"] - th) < 1e-15
    # logdiff ruin rule
    rz = block_boot(np.r_[x, -1.0], np.r_[x, 0.0], "logdiff", 10, B=99)
    assert rz["ruin"] and rz["estimate"] == -np.inf and rz["p"] == 1.0 and rz["ub"] == -np.inf
    assert verdict(holm([rz["p"]] + [0.5] * 11)[0], True, rz["ub"], E["H9"]) == "NO EDGE (HARMS)"
    # size of the studentized Sharpe-difference test under a null with correlated, volatility-clustered series
    T = 1500
    rej = {"qs": 0, "sb": 0}
    rej_mean = 0
    for rp in range(reps):
        e = rng.standard_normal((T, 2)) @ np.linalg.cholesky(np.array([[1, 0.7], [0.7, 1]])).T
        h = np.ones(T)                       # common GARCH(1,1) variance with unconditional mean 1
        e2 = (e * e).mean(1)
        for t in range(1, T):
            h[t] = 0.05 + (0.10 * e2[t - 1] + 0.85) * h[t - 1]
        e = e * np.sqrt(h)[:, None]
        sa, sb_ = 0.020, 0.035               # different vols, the same POPULATION Sharpe (0.05 a day)
        a = 0.05 * sa + sa * e[:, 0]
        b = 0.05 * sb_ + sb_ * e[:, 1]
        for m_ in rej:
            rr = block_boot(a, b, "sharpe_diff", 30, B=B, seed=rp, se_method=m_)
            rej[m_] += rr["p"] < 0.05
        rr = block_boot(a - b + 0.05 * (sb_ - sa), None, "mean", 30, B=B, seed=rp)   # population mean 0
        rej_mean += rr["p"] < 0.05
    return rej, rej_mean


def _check_holm_bh_verdict(say):
    p = [0.01, 0.04, 0.03, 0.005]
    assert np.allclose(holm(p), [0.03, 0.06, 0.06, 0.02])
    assert np.allclose(bh(p), [0.02, 0.04, 0.04, 0.02])
    # BH with ties and a NaN; Holm with NaN as 1
    assert np.allclose(bh([0.02, 0.02, np.nan, 0.5])[[0, 1, 3]], [0.03, 0.03, 0.5]) and np.isnan(bh([np.nan])[0])
    assert np.allclose(holm([0.01, np.nan]), [0.02, 1.0])
    # the 12-test family: smallest p * 12
    q = np.r_[0.001, np.full(11, 0.5)]
    assert abs(holm(q)[0] - 0.012) < 1e-15 and iu_p([0.01, 0.2, np.nan]) == 1.0 and iu_p([0.01, 0.2]) == 0.2
    T = [((0.01, True, 0.10, 0.005), "PASS"),
         ((0.01, False, 0.10, 0.005), "INCONCLUSIVE"),
         ((0.01, False, 0.003, 0.005), "NO EDGE"),
         ((0.30, True, 0.003, 0.005), "NO EDGE"),
         ((0.30, True, -0.001, 0.005), "NO EDGE (HARMS)"),
         ((0.30, True, 0.006, 0.005), "INCONCLUSIVE"),
         ((0.30, True, 0.005, 0.005), "INCONCLUSIVE"),          # equal to E is not below it
         ((0.05, True, 0.10, 0.005), "INCONCLUSIVE"),           # p must be < 0.05
         ((0.01, True, 0.003, 0.005), "PASS"),                  # PASS takes precedence
         ((np.nan, True, np.nan, 0.005), "INCONCLUSIVE"),
         ((1.0, True, -np.inf, 0.02), "NO EDGE (HARMS)"),       # H9 ruin
         ((0.30, True, [0.004, 0.30], [0.005, 0.10]), "NO EDGE"),       # HS1: the trade part alone
         ((0.30, True, [0.006, -0.20], [0.005, 0.10]), "NO EDGE (HARMS)"),
         ((0.30, True, [0.006, 0.20], [0.005, 0.10]), "INCONCLUSIVE")]
    for args, want in T:
        got = verdict(*args)
        assert got == want, (args, got, want)
    assert abs(mde(1.0) - (2.638257 + 0.841621)) < 1e-5 and abs(Z_NOEDGE - 2.6383) < 1e-4
    assert abs(mde(0.02) - 0.0696) < 1e-4                      # (2.64 + 0.84) * 2% ~ 7.0% of M
    say(f"  holm/bh hand examples; iu_p; verdict truth table ({len(T)} rows); mde(1) = {mde(1.0):.4f}")
    # drop_worst_month and top_share
    x = np.array([0.1, -0.2, 0.05, 0.3, 0.0]); mth = np.array([1, 1, 2, 3, 3])
    mm, worst = drop_worst_month(x, mth)
    assert worst == 3 and abs(mm - (-0.05) / 3) < 1e-15
    assert abs(top_share(np.r_[np.full(19, 1.0), 81.0]) - 0.81) < 1e-15
    assert abs(top_share(np.r_[np.full(21, 1.0), 79.0], 0.05) - 80 / 100) < 1e-15   # ceil(0.05 * 22) = 2


def _check_paired(say):
    D = lambda s: pd.Timestamp(s, tz="UTC")
    base = pd.DataFrame({"sym": ["BTC", "BTC", "BTC", "ETH"],
                         "signal_day": [D("2021-01-05"), D("2021-02-01"), D("2021-03-01"), D("2021-01-05")],
                         "entry1_time": [D("2021-01-06 01:00"), D("2021-02-02 01:00"), D("2021-03-31 01:00"),
                                         D("2021-01-06 01:00")],
                         "ret_adj": [0.10, -0.05, 0.02, 0.07], "ret": [0.11, -0.04, 0.03, 0.08]})
    var = pd.DataFrame({"sym": ["BTC", "BTC", "BTC", "BTC", "ETH"],
                        "signal_day": [D("2021-02-01"), D("2021-03-01"), D("2021-03-01"), D("2021-04-01"),
                                       D("2021-01-07")],
                        "entry1_time": [D("2021-02-03 10:00"), D("2021-04-01 10:00"), D("2021-04-05 10:00"),
                                        D("2021-04-02 10:00"), D("2021-01-08 10:00")],
                        "ret_adj": [-0.01, 0.04, 0.01, 0.03, 0.02], "ret": [0.0, 0.05, 0.02, 0.04, 0.03]})
    P = paired_signal_diff(base, var)
    P = P.set_index(["sym", "signal_day"])
    assert len(P) == 6                                          # union: 4 base keys + BTC 04-01 + ETH 01-07
    assert abs(P.loc[("BTC", D("2021-01-05")), "diff"] + 0.10) < 1e-15    # skipped by the variant: counts 0
    assert abs(P.loc[("BTC", D("2021-02-01")), "diff"] - 0.04) < 1e-15
    assert abs(P.loc[("BTC", D("2021-03-01")), "var"] - 0.05) < 1e-15     # two variant trades summed
    assert abs(P.loc[("BTC", D("2021-04-01")), "diff"] - 0.03) < 1e-15    # base skipped: base counts 0
    assert abs(P.loc[("ETH", D("2021-01-05")), "diff"] + 0.07) < 1e-15    # same day, other coin: distinct
    assert P.loc[("BTC", D("2021-03-01")), "month"] == 202103             # base's entry month
    assert P.loc[("BTC", D("2021-04-01")), "month"] == 202104             # variant's when base skipped
    assert P["in_base"].sum() == 4 and P["in_var"].sum() == 4
    assert abs(P["diff"].sum() - (var["ret_adj"].sum() - base["ret_adj"].sum())) < 1e-15
    P2 = paired_signal_diff(base, var, col=["ret_adj", "ret"])
    assert {"diff_ret_adj", "diff_ret", "base_ret"} <= set(P2.columns) and len(P2) == 6
    say("  paired_signal_diff: union of signals, skipped = 0, duplicates summed, (sym, day) keys, entry-month "
        "clusters; mean over the union = total-return difference / union size")


def _check_drift_adjust(say):
    rng = np.random.default_rng(5)
    hours = pd.date_range("2019-01-01", periods=24 * 365 * 4, freq="h", tz="UTC")
    rets = {s: pd.Series(rng.normal(0, 0.01, len(hours)), index=hours) for s in ("AAA", "BBB")}
    rows, ex = [], []
    for s in ("AAA", "BBB"):
        for j in range(25):
            h0 = int(rng.integers(0, len(hours) - 2000)); L = int(rng.integers(5, 1500))
            side = 1 if rng.random() < 0.7 else -1
            n = side * np.cumsum(rng.uniform(0, 0.4, L)).clip(0, 1)       # varying (pyramided) notional
            pid = f"{s}{j}"
            ex.append(pd.DataFrame({"pos": pid, "time": hours[h0:h0 + L], "notional": n}))
            rows.append({"pid": pid, "sym": s, "entry1_time": hours[h0], "exit_time": hours[h0 + L - 1],
                         "_h0": h0, "_L": L, "_n": n})
    tr = pd.DataFrame(rows)
    expo = pd.concat(ex, ignore_index=True)
    gross = lambda R: np.array([(r["_n"] * R[r["sym"]].to_numpy()[r["_h0"]:r["_h0"] + r["_L"]]).sum()
                                for _, r in tr.iterrows()])
    tr["ret"] = gross(rets)
    adj = drift_adjust(tr, expo, rets, parts=True)
    # brute-force leave-out mean
    for i in (0, 7, 30):
        r = tr.iloc[i]; s = rets[r["sym"]]
        keep = (s.index < r["entry1_time"] - pd.Timedelta(days=182)) | (s.index > r["exit_time"] + pd.Timedelta(days=182))
        assert abs(adj["mu"].iloc[i] - s[keep].mean()) < 1e-15
        assert abs(adj["expo_sum"].iloc[i] - r["_n"].sum()) < 1e-12
    # (i) a constant drift added to every return (and therefore to every trade's gross) is removed exactly
    for c in (0.0005, -0.0003):
        r2 = {s: v + c for s, v in rets.items()}
        t2 = tr.copy(); t2["ret"] = gross(r2)
        a2 = drift_adjust(t2, expo, r2)
        assert np.max(np.abs(a2.to_numpy() - adj["ret_adj"].to_numpy())) < 1e-12
    # (ii) pure constant returns: the drift-adjusted return is exactly 0 (shorts included)
    r3 = {s: pd.Series(0.0004, index=hours) for s in rets}
    t3 = tr.copy(); t3["ret"] = gross(r3)
    a3 = drift_adjust(t3, expo, r3)
    assert np.max(np.abs(a3.to_numpy())) < 1e-12                  # floating-point rounding only
    assert (tr["_n"].map(lambda n: n.sum() < 0)).any() and (t3["ret"] < 0).any()     # shorts lose to +drift
    # (iii) alternative expo formats: integer hour positions, a tuple, a dict per sym
    pos_h = np.concatenate([np.arange(r["_h0"], r["_h0"] + r["_L"]) for _, r in tr.iterrows()])
    a4 = drift_adjust(tr, (expo["pos"].to_numpy(), pos_h, expo["notional"].to_numpy()), rets)
    assert np.allclose(a4.to_numpy(), adj["ret_adj"].to_numpy(), atol=1e-15, rtol=0)
    ed = {s: expo[expo["pos"].str.startswith(s)] for s in ("AAA", "BBB")}
    a5 = drift_adjust(tr, ed, rets)
    assert np.allclose(a5.to_numpy(), adj["ret_adj"].to_numpy(), atol=1e-15, rtol=0)
    # (iv) open at the end (exit NaT) uses the last exposure hour
    t6 = tr.copy(); t6.loc[3, "exit_time"] = pd.NaT
    assert abs(drift_adjust(t6, expo, rets).iloc[3] - adj["ret_adj"].iloc[3]) < 1e-15
    # (v) empty leave-out sample -> NaN, counted
    short = {s: v.iloc[:24 * 150] for s, v in rets.items()}
    t7 = tr.iloc[:5].copy()
    t7["entry1_time"], t7["exit_time"] = hours[10], hours[20]      # +-182 days covers the whole 150-day series
    a7 = drift_adjust(t7, expo, short)
    assert a7.isna().all() and a7.attrs["n_nan_mu"] == len(t7)
    assert drift_adjust(t7, expo, short, fallback_full=True).notna().all()
    say("  drift_adjust: leave-out mean = brute force; a constant drift is removed exactly (|diff| < 1e-12); "
        "constant returns -> 0 exactly, shorts included; tuple / dict / integer-hour expo formats agree")


def _check_generator(say):
    out = simple_three_coin_trades(11)
    tr, ex, R = out["trades"], out["expo"], out["rets"]
    for s in R:
        t = tr[tr["sym"] == s]; e = ex[ex["sym"] == s]
        r = R[s].reindex(e["time"]).to_numpy()
        g = pd.Series(e["notional"].to_numpy() * r).groupby(e["pos"].to_numpy()).sum()
        assert np.allclose(g.reindex(t["pos"]).to_numpy(), t["ret_gross"].to_numpy(), atol=1e-12, rtol=0)
    assert len(tr) > 40 and (tr["n_tranches"] <= 3).all() and (tr["max_frac"] <= 1 + 1e-12).all()
    # drift adjustment on a drifting martingale + drift path: raw mean > 0 with a large t, adjusted ~ 0
    xs, ys, gs = [], [], []
    for sd in range(8):
        o = simple_three_coin_trades(100 + sd, drift_hourly=1.5 / 8760)
        t = o["trades"]
        xs.append(t["ret_gross"].to_numpy()); ys.append(drift_adjust(t, o["expo"], o["rets"]).to_numpy())
        gs.append(month_key(t["entry1_time"]) + sd * 10_000_000)
    x, y, g = np.concatenate(xs), np.concatenate(ys), np.concatenate(gs)
    tr_raw, tr_adj = cluster_t(x, g)[2], cluster_t(y, g)[2]
    say(f"  generator: gross = sum_h notional_h * r_h exactly; with +150%/yr arithmetic drift ({len(x)} trades) "
        f"raw t = {tr_raw:.1f}, drift-adjusted t = {tr_adj:.2f}")
    assert tr_raw > 4 and abs(tr_adj) < 3


def selftest() -> None:
    t0 = time.time()

    def say(s):
        print(s, flush=True)

    say("cluster_t, ratio_cluster (hand computations)")
    _check_cluster_t(say)
    say("cluster_ols")
    _check_cluster_ols(say)
    say("holm, bh, verdicts, mde, drop_worst_month, top_share")
    _check_holm_bh_verdict(say)
    say("paired_signal_diff")
    _check_paired(say)
    say("drift_adjust")
    _check_drift_adjust(say)
    say("bootstrap-t coverage")
    _check_boot_t(say)
    say("block bootstrap")
    reps = 400
    rej, rej_mean = _check_block_boot(say, reps)
    say(f"  stationary bootstrap: mean block ~ requested; p formula reproduced; logdiff ruin -> -inf, NO EDGE "
        f"(HARMS)")
    say(f"  Sharpe-difference size under the null (correlated 0.7, GARCH vol, T 1500, block 30, B 499, {reps} reps):"
        f" QS-HAC {rej['qs'] / reps:.3f}, SB-kernel {rej['sb'] / reps:.3f}; mean-difference size "
        f"{rej_mean / reps:.3f}; nominal 0.050")
    assert 0.015 <= rej["qs"] / reps <= 0.09 and 0.015 <= rej["sb"] / reps <= 0.09 and rej_mean / reps <= 0.09
    say("built-in trade generator")
    _check_generator(say)
    say("inference control (built-in generator, 200 paths, B 9999)")
    ic = inference_control(n_paths=200)
    say(f"  {ic['n_paths']} paths, {ic['mean_trades_per_path']:.0f} trades and {ic['mean_G']:.0f} months each; "
        f"true mean {ic['true_mean']:+.5f} ({ic['true_mean_source']})")
    say(f"  month-clustered t rejects at nominal 5%: {ic['reject_rate']:.3f} (95% CI {ic['reject_ci'][0]:.3f}-"
        f"{ic['reject_ci'][1]:.3f}); centred at the true mean {ic['reject_rate_centered']:.3f}")
    say(f"  95% bound below the true mean: bootstrap-t {ic['miss_rate_95']:.3f} (CI {ic['miss_ci_95'][0]:.3f}-"
        f"{ic['miss_ci_95'][1]:.3f}), analytic {ic['miss_rate_analytic_95']:.3f}; at the NO EDGE level "
        f"{ic['miss_rate_noedge']:.3f}; level widened: {ic['level_widened']}")
    assert 0 <= ic["reject_rate"] <= 0.12 and 0 <= ic["miss_rate_95"] <= 0.15
    say(f"selftest passed in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    if sys.argv[1] == "selftest":
        selftest()
    elif sys.argv[1] == "inference-control":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        r = inference_control(n_paths=n, n_jobs=4)
        for k, v in r.items():
            print(f"{k}: {v}")
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}")
