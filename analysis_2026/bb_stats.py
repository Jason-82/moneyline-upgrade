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
    coin_returns(sym)                           returns_from_hours(bb_data.coin_hours(sym)): the whole history
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
    verdict(p_holm, conds_ok, ub, E, force_inconclusive=False) -> "PASS" | "NO EDGE" | "NO EDGE (HARMS)" |
      "INCONCLUSIVE";  E = the pre-registered thresholds by test;  pass_label(v, month_dropped_mean)
  Reporting
    drop_worst_month(x, months) -> (mean_after, month), top_share(pnl, q=0.05) -> float
    cluster_boot_ci(n_rows, clusters, fn, ...)  month-cluster percentile interval of any trade statistic (H11)
    block_boot_ci(x, fn, mean_block_days, ...)  month-block percentile interval of any daily-series statistic
      (headline / H11 multiple, CAGR, drawdown); multiple_fn, maxdd_fn
  Controls
    inference_control(sim_fn=None, n_paths=200, seed=20261018, true_mean=None, ...) -> dict
    noedge_level_for(level_widened) -> float      the NO EDGE level implied by a widened 95% level
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
   for crypto the default is `coin_returns(sym)`: the TRADED series of bb_data.coin_hours over the coin's whole
   history, spot stand-in hours included, since trade P&L is on that series; outage hours count 0 and the gap's
   move lands on the next live hour; a return is NaN across a series break (`seg` change), into or out of a
   non-tradable hour (filler after a perpetual ended or a `perp_end`), and at the spot->perpetual switch hour
   (`is_perp` change: a basis, not a move)). If the leave-out sample is empty the drift-adjusted return is NaN
   (fallback_full=True uses the whole-sample mean instead); the count is in attrs["n_nan_mu"]. A trade whose
   (sym, position id) has no exposure row is an error when it held a position (hold_h > 0) or has a nonzero
   return (a key mismatch would silently zero its drift charge); missing_expo="warn" keeps a 0 charge and warns.
   The count is in attrs["n_no_expo"].
2. paired_signal_diff: the pairing key is (sym, key) when both frames carry `sym` (a signal day alone does not
   identify a signal across coins). Several trades of one variant with the same key are summed (total return
   per signal). diff = var - base; a signal missing from one variant counts 0 for it. The cluster month is the
   entry calendar month of the base trade, or of the variant's trade when the base skipped the signal. A signal
   where a variant has a trade with an undefined value (NaN ret_adj: empty leave-out sample) is NaN, not 0, so
   the paired tests drop it exactly as the trade-level tests drop that trade (count in attrs["n_nan"]).
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
   bootstrap (H9's rule). A Sharpe difference that is undefined (a constant series, a == b, or no finite t*)
   returns p, ub and ci95 = NaN (INCONCLUSIVE under verdict), as does cluster_ols for a coefficient the design
   does not identify (H5's indicator when every or no trade meets the near-high condition).
4. portfolio_test: the NO EDGE bound is the larger of the 1- and 3-month bounds (the conservative choice, mirroring
   the max of the two p-values).
5. verdict: PASS takes precedence over NO EDGE when both hold (an effect significantly above 0 whose bound is
   below E); ub and E may be sequences (one per component of a compound test): NO EDGE if any component's bound is
   below its E, "(HARMS)" if any component's bound is below 0. A NaN p never passes; a NaN bound is never NO EDGE.
   The pre-registration's "is INCONCLUSIVE" rules (H3's sign disagreement between units; HS1's primary seed
   passing while the median seed does not) override both, via force_inconclusive. H5's E is the per-signal
   +0.25% of M (the Verdicts list puts H3-H8 together), applied to the near-high coefficient.
6. mde uses the normal quantile 2.638 (= the pre-registration's 2.64) unless df is given, and z_{0.80} = 0.8416.
7. top_share uses the ceil(q * n) largest P&Ls over the sum of all P&Ls (no sign guard: a total <= 0 gives a
   share that is negative or above 1, reported as is).
8. bh: NaN p-values are left out of m and returned as NaN; holm treats NaN as 1 (scalp_stats.holm).
9. inference_control: the "true mean" is the analytic 0 for the built-in generator (zero arithmetic drift, no
   costs, every fill at a path price: E[gross] = 0; the drift charge's mean is 0 to within +0.0004 +- 0.0002 on
   2,000 independent paths, and 0 is the conservative side of it). A custom sim_fn must give it (a float, or
   "independent": estimated on separate paths with disjoint seeds). It is never the grand mean of the scored
   paths, which moves with the bounds it scores (on the built-in generator that reference sat at -0.0018 and
   turned a 6.0% miss rate into 4.5%). The rejection rate is of the pre-registered test (p < 0.05 for mean > 0)
   and also the rate centred at the true mean; the miss rate is the share of paths whose month-cluster
   bootstrap-t bound at 95% lies below the true mean. The criterion is the point rate ("at most about 5%" read
   as <= 5%; the binomial test is reported beside it). If it fails, `level_widened` is the smallest level on a
   grid at which it does not (the pre-registration's widening rule; the orchestrator applies it), and
   `level_noedge_widened` carries the widening to the NO EDGE level by scaling its tail 0.05/12 by the same
   factor as the 95% tail: 1 - (0.05/12) (1 - level_widened) / 0.05 (the pre-registration says only that "the
   bound's level is widened"; 200 paths cannot measure a 0.4% tail directly). Rates are also given against 0.
10. Descriptive intervals (H11 win/loss and multiple, headline CAGR / multiple / Sharpe / drawdown) are percentile
   intervals: month-cluster resampling of trades (cluster_boot_ci) or month-block stationary resampling of daily
   account returns (block_boot_ci). They enter no verdict.
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
    mean is per calendar hour, matching an exposure path that counts calendar hours. A return is NaN (left out
    of mu) unless it runs between two rows of one market of one asset: NaN across a series break (`seg`
    changes), into or out of a non-tradable row (`tradable` False: filler after a perpetual ended, carried at
    the dead contract's last close), and at the hour the traded series switches market (`is_perp` changes,
    spot stand-in -> perpetual: a spot-perpetual basis, not a price move)."""
    c = hours[col].astype(float)
    r = c / c.shift(1) - 1.0
    bad = np.zeros(len(r), bool)
    for k in ("seg", "is_perp"):
        if k in hours:
            v = hours[k].to_numpy()
            bad[1:] |= v[1:] != v[:-1]
    if "tradable" in hours:
        t = hours["tradable"].to_numpy(bool)
        bad |= ~t
        bad[1:] |= ~t[:-1]
    r[bad] = np.nan
    r.iloc[0] = np.nan
    return r


def coin_returns(sym: str, col: str = "close") -> pd.Series:
    """The traded series' hourly returns over the coin's whole history in bb_data.coin_hours (first spot or
    perpetual hour to 2026-10-16 23:00): the default 'whole sample' for drift_adjust's mu (returns_from_hours)."""
    from analysis_2026 import bb_data            # lazy: the stats module itself reads no market data
    return returns_from_hours(bb_data.coin_hours(sym), col)


def drift_adjust(trades: pd.DataFrame, expo, hourly_ret_by_sym: dict, leave_out_days: int = LEAVE_OUT_DAYS,
                 ret_col: str = "ret", id_col: str | None = None, fallback_full: bool = False,
                 parts: bool = False, missing_expo: str = "raise"):
    """Drift-adjusted trade return (prereg "Units and statistics"):
        ret_adj = ret - mu * sum_h notional_h,   mu = leave-out mean of the asset's per-period arithmetic return,
    excluding [entry1_time - leave_out_days, exit_time + leave_out_days].
    trades: one row per position with sym, entry1_time, exit_time (NaT if open) and ret_col; the position id is
      id_col, else the first of pos/pid/position/position_id/id present, else the index.
    expo: DataFrame (pos, time|hour, notional[, sym]), a (pos, hour, notional) tuple of arrays, or a dict
      {sym: such a frame}. Times are timestamps or integer positions into the sym's return series. Notional is
      signed (shorts negative), per unit of M.
    hourly_ret_by_sym: {sym: Series of arithmetic returns indexed by period start (hours; sessions for stocks)}.
    missing_expo: a trade whose (sym, position id) key has no exposure row gets a drift charge of 0 and is counted
      in attrs["n_no_expo"]. "raise" (default) raises when any such trade held a position (hold_h > 0) or has a
      finite nonzero ret_col, which only a key mismatch between trades and expo can produce (a symbol label such
      as 'BTCUSDT' vs 'BTC', position ids of another dtype); "warn" warns and keeps the 0 charge.
    Returns a Series aligned to trades.index (parts=True: a DataFrame with mu, expo_sum, drift, ret, ret_adj)."""
    if missing_expo not in ("raise", "warn"):
        raise ValueError(f"missing_expo must be 'raise' or 'warn', not {missing_expo!r}")
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
    has_expo = esum.index.get_indexer(keyT) >= 0 if len(esum) else np.zeros(len(T), bool)
    n_expo = esum.reindex(keyT).fillna(0.0).to_numpy()
    if not has_expo.all():
        miss = ~has_expo
        r_ = T[ret_col].to_numpy(float)
        bad = miss & np.isfinite(r_) & (r_ != 0)
        if "hold_h" in T.columns:
            bad |= miss & (pd.to_numeric(T["hold_h"], errors="coerce").to_numpy(float) > 0)
        if bad.any():
            i = int(np.flatnonzero(bad)[0])
            xs = X["sym"].iloc[0] if use_sym and len(X) else None
            msg = (f"drift_adjust: {int(bad.sum())} of {len(T)} trades have no exposure rows although they held a "
                   f"position or have a nonzero {ret_col}, e.g. sym {syms[i]!r} position {pid[i]!r} "
                   f"({type(pid[i]).__name__}); expo keys look like sym {xs!r} position "
                   f"{(X['pos'].iloc[0] if len(X) else None)!r} ({X['pos'].dtype}). Their drift charge would be 0.")
            if missing_expo == "raise":
                raise ValueError(msg + " Fix the keys, or pass missing_expo='warn'.")
            import warnings
            warnings.warn(msg, stacklevel=2)

    nT = len(T)

    def _ns(col):                                   # int64 ns (no float round trip) and a validity mask
        if col not in T:
            return np.zeros(nT, np.int64), np.zeros(nT, bool)
        idx = _naive_utc(T[col])
        ok_ = ~np.asarray(idx.isna())
        return np.where(ok_, idx.asi8, 0), ok_

    e_ns, e_ok = _ns("entry1_time")
    x_ns, x_ok = _ns("exit_time")
    # holding window per position: entry1_time .. exit_time, falling back to the exposure path's first/last hour
    if not (e_ok.all() and x_ok.all()):
        tt = X["time"].to_numpy()
        xsym = (X["sym"].to_numpy() if use_sym
                else pd.Series(syms, index=pd.Index(pid)).reindex(X["pos"].to_numpy()).to_numpy())
        if np.issubdtype(np.asarray(tt).dtype, np.integer):
            tv = np.zeros(len(X), np.int64)
            for s, ii in pd.Series(np.arange(len(X))).groupby(xsym).indices.items():
                tv[ii] = _naive_utc(hourly_ret_by_sym[s].index[np.asarray(tt[ii], np.int64)]).asi8
        else:
            tv = _naive_utc(tt).asi8
        g = pd.Series(tv, index=keyX).groupby(level=list(range(keyX.nlevels)))
        gmin, gmax = g.min(), g.max()
        j_ = gmin.index.get_indexer(keyT)
        f_ok = j_ >= 0
        f_ns = gmin.to_numpy()[np.maximum(j_, 0)] if len(gmin) else np.zeros(nT, np.int64)
        l_ns = gmax.to_numpy()[np.maximum(j_, 0)] if len(gmax) else np.zeros(nT, np.int64)
    else:
        f_ok = np.zeros(nT, bool)
        f_ns = l_ns = np.zeros(nT, np.int64)
    if not (e_ok | f_ok).all():
        i = int(np.flatnonzero(~(e_ok | f_ok))[0])
        raise ValueError(f"position {pid[i]} ({syms[i]}) has neither entry1_time nor exposure rows")
    lo_ns = np.where(e_ok, e_ns, f_ns)
    hi_ns = np.where(x_ok, x_ns, np.where(f_ok, l_ns, lo_ns))
    lo_all = lo_ns - leave_out_days * 86_400_000_000_000
    hi_all = hi_ns + leave_out_days * 86_400_000_000_000
    mu = np.full(nT, np.nan)
    for s, rows in pd.Series(np.arange(nT)).groupby(syms).indices.items():
        r = hourly_ret_by_sym[s]
        rt = _naive_utc(r.index).asi8
        order = np.argsort(rt, kind="stable")
        rt = rt[order]
        rv = r.to_numpy(float)[order]
        ok = np.isfinite(rv)
        cs = np.r_[0.0, np.cumsum(np.where(ok, rv, 0.0))]
        cn = np.r_[0, np.cumsum(ok)]
        n = len(rv)
        lo = np.searchsorted(rt, lo_all[rows], "left")
        hi = np.searchsorted(rt, hi_all[rows], "right")
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
    out.attrs["n_no_expo"] = int((~has_expo).sum())
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
    Returns (beta, se, t, one-sided p for beta > 0, df = G - 1), arrays over the columns.
    Degenerate designs return NaN instead of raising (so verdict() reads INCONCLUSIVE): a coefficient that X does
    not identify (e.g. H5's near-high indicator when every, or no, trade meets the condition: collinear with the
    intercept) gets beta = se = t = p = NaN, the identified ones are estimated as usual (pseudo-inverse); with
    fewer than 2 clusters every se, t and p is NaN and df = 0."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = np.column_stack([np.ones(len(X)), X])
    g = np.asarray(clusters)
    k = np.isfinite(y) & np.isfinite(X).all(1)
    y, X, g = y[k], X[k], g[k]
    kx = X.shape[1]
    nan = np.full(kx, np.nan)
    if len(y) == 0:
        return nan.copy(), nan.copy(), nan.copy(), nan.copy(), 0
    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    # a coefficient is identified iff its unit vector lies in the row space of X: P e_j = e_j, P = pinv(XtX) XtX
    ident = np.abs(np.diag(XtX_inv @ XtX) - 1.0) < 1e-8
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    _, inv = np.unique(g, return_inverse=True)
    G = int(inv.max()) + 1
    if G < 2:
        return np.where(ident, beta, np.nan), nan.copy(), nan.copy(), nan.copy(), 0
    sc = np.zeros((G, kx))
    np.add.at(sc, inv, X * e[:, None])
    meat = sc.T @ sc
    V = (G / (G - 1)) * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    df = G - 1
    beta = np.where(ident, beta, np.nan)
    se = np.where(ident, se, np.nan)
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
      variant's; the cluster label).
    An undefined value is not a 0 return: a signal where a variant HAS a trade whose value is NaN (e.g. ret_adj
    with an empty leave-out sample) gets NaN for that variant and for diff, so the paired tests drop it as
    cluster_t / trade_test drop that trade; the count of such signals is in attrs["n_nan"] (per column:
    attrs["n_nan_by_col"])."""
    cols = [col] if isinstance(col, str) else list(col)
    if isinstance(key, str):
        keys = (["sym", key] if "sym" in base_trades.columns and "sym" in var_trades.columns else [key])
    else:
        keys = list(key)

    def agg(t):
        f = t[keys + cols].copy()
        f["_n"] = 1
        for c in cols:                              # 1 where the trade's value is undefined
            f[c] = f[c].astype(float)
            f[f"_nan_{c}"] = (~np.isfinite(f[c].to_numpy())).astype(np.int64)
        if time_col in t.columns:
            f["_t"] = _naive_utc(t[time_col])
        a = {c: "sum" for c in cols}
        a.update({f"_nan_{c}": "sum" for c in cols})
        a["_n"] = "sum"
        if "_t" in f:
            a["_t"] = "min"
        g = f.groupby(keys, sort=False, dropna=False).agg(a)
        for c in cols:                              # a present trade's NaN stays NaN (groupby-sum would give 0)
            g.loc[g[f"_nan_{c}"] > 0, c] = np.nan
        return g.drop(columns=[f"_nan_{c}" for c in cols])

    A, Bv = agg(base_trades), agg(var_trades)
    U = A.join(Bv, how="outer", lsuffix="_b", rsuffix="_v").sort_index()
    out = pd.DataFrame(index=U.index)
    in_b = U["_n_b"].notna().to_numpy()
    in_v = U["_n_v"].notna().to_numpy()
    n_nan = {}
    for c in cols:
        b = U[f"{c}_b"].to_numpy(float)
        v = U[f"{c}_v"].to_numpy(float)
        b = np.where(in_b, b, 0.0)                  # a skipped signal counts 0; a present NaN stays NaN
        v = np.where(in_v, v, 0.0)
        sfx = "" if len(cols) == 1 else f"_{c}"
        out["base" + sfx] = b
        out["var" + sfx] = v
        out["diff" + sfx] = v - b
        n_nan[c] = int((~np.isfinite(v - b)).sum())
    out["in_base"] = in_b
    out["in_var"] = in_v
    if "_t_b" in U and "_t_v" in U:
        t = U["_t_b"].where(U["_t_b"].notna(), U["_t_v"])
        out["month"] = month_key(t)
    else:
        lvl = U.index.get_level_values(keys[-1]) if isinstance(U.index, pd.MultiIndex) else U.index
        out["month"] = month_key(lvl)
    out = out.reset_index()
    dcols = ["diff"] if len(cols) == 1 else [f"diff_{c}" for c in cols]
    out.attrs["n_nan"] = int((~np.isfinite(out[dcols].to_numpy(float))).any(axis=1).sum())   # signals dropped
    out.attrs["n_nan_by_col"] = n_nan
    return out


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
    _, g_ = _clean(x, clusters)
    return {"n": int(len(g_)), "G": int(len(np.unique(g_))), "mean": m, "se": se,
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
    if se_method not in ("qs", "sb"):
        raise ValueError(se_method)
    ann = math.sqrt(ppy)

    def _undefined(th_=np.nan, se_=np.nan, why=""):
        # a Sharpe ratio or its SE is undefined (a constant series, or a == b): no test, no bound, so verdict()
        # reads INCONCLUSIVE (a NaN p never passes, a NaN bound is never NO EDGE)
        res.update(estimate=th_ * ann, daily_estimate=th_, se=se_ * ann, t_hat=np.nan, p=np.nan, ub=np.nan,
                   ub95=np.nan, ci95=(np.nan, np.nan), se_boot=np.nan, se_method=se_method, B_valid=0,
                   degenerate=why)
        return res

    def _flat(x):                                   # the variance as _sharpe_parts computes it is ~0 or below
        g2 = float((x * x).mean())
        return not (g2 - float(x.mean()) ** 2 > 1e-12 * g2)

    if T < 3 or _flat(a) or (b is not None and _flat(b)):
        return _undefined(why="constant series")
    with np.errstate(all="ignore"):
        th, grad = _sharpe_parts(a, b)
        V = _moments(a, b)
        if se_method == "qs":
            Psi = hac_qs_prewhitened(V)
            se = math.sqrt(max(float(grad @ Psi @ grad), 0.0) / T)
        else:
            se = math.sqrt(max(_sb_kernel_var(V @ grad, mean_block_days), 0.0) / T)
    if not (np.isfinite(th) and np.isfinite(se) and se > 0):
        return _undefined(th, se, "zero or undefined SE")
    t_hat = th / se
    tstar = np.empty(B)
    dstar = np.empty(B)
    with np.errstate(divide="ignore", invalid="ignore"):   # a draw with zero variance gives a non-finite t*
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
    if len(tstar) == 0:
        return _undefined(th, se, "no finite bootstrap t*")
    p = (1 + np.sum(tstar >= t_hat)) / (len(tstar) + 1)
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
    mx = lambda k: float(np.max([r[k] for r in dec]))          # a NaN in either block length propagates
    return {"by_block": by, "p": mx("p"), "ub": mx("ub"), "estimate": r1["estimate"], "se": mx("se"),
            "ci95": r1["ci95"], "ub95": mx("ub95")}


# ============================================================================ descriptive intervals (H11, headline)

def cluster_boot_ci(n_rows: int, clusters, fn, B: int = B_TRADE, seed: int = SEED, level: float = 0.95):
    """Month-cluster percentile bootstrap interval of an arbitrary trade statistic (H11: average win / average
    loss in dollars, hit rate). fn(rows: int array) -> float is evaluated on the original rows and on each draw
    (clusters resampled with replacement; a duplicated cluster's rows appear twice). Draws where fn is not
    finite are dropped. Returns (estimate, lo, hi, n_valid_draws)."""
    g = np.asarray(clusters)
    if len(g) != n_rows:
        raise ValueError("clusters must have one label per row")
    _, inv = np.unique(g, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    cnt = np.bincount(inv)
    starts = np.r_[0, np.cumsum(cnt)[:-1]]
    G = len(cnt)
    rng = np.random.default_rng(seed)
    est = float(fn(np.arange(n_rows)))
    vals = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, G, G)
        rows = np.concatenate([order[starts[c]:starts[c] + cnt[c]] for c in pick])
        vals[b] = fn(rows)
    vals = vals[np.isfinite(vals)]
    a = 1 - level
    if len(vals) == 0:
        return est, np.nan, np.nan, 0
    return est, float(_q(vals, a / 2)), float(_q(vals, 1 - a / 2)), len(vals)


def block_boot_ci(x, fn, mean_block_days: float = MONTH_DAYS, B: int = B_PORT, seed: int = SEED,
                  level: float = 0.95):
    """Stationary-block (month-block) percentile bootstrap interval of a statistic of one daily series (headline
    CAGR, multiple, Sharpe, max drawdown; H11's account multiple). fn(R) maps a (n, T) array of resampled paths
    to n values (row-wise) and is also applied to x[None, :]. Returns (estimate, lo, hi)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    T = len(x)
    rng = np.random.default_rng(seed)
    chunk = max(1, int(2_000_000 // max(T, 1)))
    vals = np.empty(B)
    for k0 in range(0, B, chunk):
        nb = min(chunk, B - k0)
        idx, _ = sb_indices(T, mean_block_days, nb, rng)
        vals[k0:k0 + nb] = np.asarray(fn(x[idx]), float)
    a = 1 - level
    v = vals[np.isfinite(vals)]
    return float(np.asarray(fn(x[None, :]), float)[0]), float(_q(v, a / 2)), float(_q(v, 1 - a / 2))


def multiple_fn(R):
    """Row-wise account multiple prod(1 + r) (for block_boot_ci)."""
    return np.prod(1.0 + R, axis=1)


def maxdd_fn(R):
    """Row-wise maximum drawdown of the equity path prod(1 + r) (a positive fraction; for block_boot_ci)."""
    eq = np.cumprod(1.0 + R, axis=1)
    peak = np.maximum.accumulate(np.maximum(eq, 1.0), axis=1)
    return (1.0 - eq / peak).max(axis=1)


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


def verdict(p_holm, conds_ok: bool, ub, E_, force_inconclusive: bool = False) -> str:
    """PASS if the Holm-adjusted p < 0.05 and every other condition holds; else NO EDGE if a component's one-sided
    upper bound (level 1 - 0.05/12) is below its threshold E, reported as "NO EDGE (HARMS)" when a bound is below
    0; else INCONCLUSIVE. ub and E may be scalars or equal-length sequences (one per component).
    force_inconclusive: a pre-registered rule that makes the test INCONCLUSIVE outright (H3: the per-signal and
    exposure-time units disagree in sign; HS1: the primary seed passes and the median seed does not)."""
    if force_inconclusive:
        return "INCONCLUSIVE"
    if p_holm is not None and np.isfinite(p_holm) and p_holm < ALPHA and bool(conds_ok):
        return "PASS"
    ubs = np.atleast_1d(np.asarray(ub, float))
    Es = np.broadcast_to(np.atleast_1d(np.asarray(E_, float)), ubs.shape)
    below = np.isfinite(ubs) | np.isneginf(ubs)
    below = below & (ubs < Es)
    if below.any():
        return "NO EDGE (HARMS)" if (below & (ubs < 0)).any() else "NO EDGE"
    return "INCONCLUSIVE"


def pass_label(v: str, month_dropped_mean=None) -> str:
    """Reporting rules (H1, HS1, HS2): a PASS whose month-dropped mean is <= 0 is reported as
    "PASS, carried by one month"; any other verdict is returned unchanged."""
    if v == "PASS" and month_dropped_mean is not None and not (month_dropped_mean > 0):
        return "PASS, carried by one month"
    return v


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


def _ic_frames(sim_fn, seeds, n_jobs):
    if n_jobs > 1:
        with cf.ProcessPoolExecutor(n_jobs) as ex:
            return list(ex.map(sim_fn, seeds))
    return [sim_fn(s) for s in seeds]


def _ic_path(f, col):
    """(values, month clusters) of one synthetic path; a {"trades", "expo", "rets"} dict is drift-adjusted here."""
    if isinstance(f, dict):
        tr = f["trades"].copy()
        if "ret_adj" not in tr.columns:
            tr["ret_adj"] = drift_adjust(tr, f["expo"], f["rets"]).to_numpy()
        f = tr
    c = col or ("ret_adj" if "ret_adj" in f.columns else "ret")
    g = f["month"].to_numpy() if "month" in f.columns else month_key(f["entry1_time"])
    x = f[c].to_numpy(float)
    k = np.isfinite(x)
    return x[k], g[k]


def _widen(rate, level_grid):
    """The pre-registered widening rule on the miss rates by level: None if the 95% miss rate is <= 5%, else the
    smallest grid level whose miss rate is <= 5% (NaN if no grid level meets it)."""
    if rate[0.95] <= 0.05:
        return None
    return next((lv for lv in level_grid if lv >= 0.95 and rate[lv] <= 0.05), np.nan)


def noedge_level_for(level_widened) -> float:
    """The NO EDGE level after widening (coding choice 9): the tail 0.05/12 is scaled by the same factor as the 95%
    level's tail, 1 - (0.05/12) * (1 - level_widened) / 0.05; LEVEL_NOEDGE when no widening is needed."""
    if level_widened is None:
        return LEVEL_NOEDGE
    if not np.isfinite(level_widened):
        return np.nan
    return 1.0 - (1.0 - LEVEL_NOEDGE) * (1.0 - float(level_widened)) / 0.05


def inference_control(sim_fn=None, n_paths: int = 200, seed: int = SEED, col: str | None = None,
                      true_mean: float | str | None = None, B: int = B_TRADE, alpha: float = ALPHA,
                      n_jobs: int = 1, level_grid=LEVEL_GRID, n_ref_paths: int = 1000) -> dict:
    """The pre-registration's "Inference known answer" control. sim_fn(seed: int) -> trades DataFrame for one
    synthetic three-coin path with zero arithmetic drift and cross-correlation 0.8 (the orchestrator wires it to
    the engine; default: builtin_sim), or a dict {"trades", "expo", "rets"} (engine-shaped trades and exposure
    paths plus {sym: hourly return Series}), which is drift-adjusted here. Each frame needs the value column (col;
    default ret_adj, else ret) and entry1_time (or a `month` column). With n_jobs > 1, sim_fn must be a
    module-level (picklable) function.
    true_mean: the mean the bounds are scored against. Never the mean of the scored paths themselves (that
      reference moves with the bounds it scores). None with the built-in generator (sim_fn None or builtin_sim)
      means 0.0, the analytic value: zero arithmetic drift, no costs and every fill at a path price give E[gross]
      = 0, and the drift charge's mean is 0 to within the independent check (+0.0004 +- 0.0002 on 2,000 paths;
      if real, 0 is the conservative reference). Any other sim_fn needs it explicitly: a float (analytic, e.g. 0.0
      for zero-drift paths before costs) or "independent", the pooled per-trade mean over n_ref_paths further paths
      whose seeds are disjoint from the scored ones (path-clustered SE in true_mean_se).
    Reports H1's month-clustered rejection rate at a nominal one-sided 5% (vs 0 and centred at the true mean),
    the rate at which the month-cluster bootstrap-t bound at each grid level falls below the true mean, and the
    pre-registered point criterion: ok_miss = (95% miss rate <= 5%); if it fails, level_widened is the smallest
    grid level whose miss rate is <= 5% (the widening rule) and level_noedge_widened the NO EDGE level it implies
    (noedge_level_for). The same three are also given against 0 (*_at_0). The binomial flags are supplementary."""
    builtin = sim_fn is None or sim_fn is builtin_sim
    sim_fn = sim_fn or builtin_sim
    if true_mean is None:
        if not builtin:
            raise ValueError("inference_control: give true_mean for a custom sim_fn: a float (analytic, e.g. 0.0 for "
                             "zero-drift paths with zero costs) or 'independent' (estimated on separate paths)")
        true_mean, src = 0.0, "analytic 0 (built-in generator: zero arithmetic drift, no costs)"
    elif isinstance(true_mean, str):
        if true_mean != "independent":
            raise ValueError(f"true_mean must be a float, None or 'independent', not {true_mean!r}")
        src = None
    else:
        true_mean, src = float(true_mean), "given"
    seeds = [int(s) for s in np.random.default_rng(seed).integers(0, 2 ** 62, n_paths)]
    paths = [_ic_path(f, col) for f in _ic_frames(sim_fn, seeds, n_jobs)]
    mu_se = np.nan
    if src is None:                                # independent reference paths, seeds disjoint from the scored
        used = set(seeds)
        ref_seeds = [int(s) for s in np.random.default_rng([seed, 1]).integers(0, 2 ** 62, n_ref_paths)
                     if int(s) not in used]
        ref = [_ic_path(f, col) for f in _ic_frames(sim_fn, ref_seeds, n_jobs)]
        xr = np.concatenate([x for x, _ in ref])
        lab = np.concatenate([np.full(len(x), j) for j, (x, _) in enumerate(ref)])
        true_mean, mu_se = cluster_t(xr, lab)[:2]
        src = f"independent ({len(ref_seeds)} paths, seeds disjoint from the scored ones)"
    mu = float(true_mean)
    refs = {"ref": mu, "0": 0.0}
    rej0 = rejc = 0
    miss = {r: {lv: 0 for lv in level_grid} for r in refs}
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
        for r, v in refs.items():
            for lv in level_grid:
                miss[r][lv] += bb["ub"][lv] < v
        miss_an += upper_bound_t(m, se, df, 0.95) < mu
    rate = {r: {lv: miss[r][lv] / n_ok for lv in level_grid} for r in refs}
    wid, wid0 = _widen(rate["ref"], level_grid), _widen(rate["0"], level_grid)
    k95 = miss["ref"][0.95]
    allx = np.concatenate([x for x, _ in paths])
    return {"n_paths": n_ok, "true_mean": mu, "true_mean_source": src, "true_mean_se": float(mu_se),
            "scored_grand_mean": float(allx.mean()),            # diagnostic only: never the reference
            "mean_trades_per_path": float(np.mean(ns)), "mean_G": float(np.mean(Gs)),
            "reject_rate": rej0 / n_ok, "reject_ci": _binom_ci(rej0, n_ok),
            "reject_rate_centered": rejc / n_ok,
            "miss_rate_95": rate["ref"][0.95], "miss_ci_95": _binom_ci(k95, n_ok),
            "miss_rate_analytic_95": miss_an / n_ok, "miss_rate_noedge": rate["ref"][LEVEL_NOEDGE],
            "miss_rate_by_level": rate["ref"],
            "ok_reject": rej0 / n_ok <= 0.05, "ok_miss": rate["ref"][0.95] <= 0.05,
            "ok_reject_binomial": stats.binom.sf(rej0 - 1, n_ok, 0.05) > 0.05,
            "ok_miss_binomial": stats.binom.sf(k95 - 1, n_ok, 0.05) > 0.05,
            "level_widened": wid, "level_noedge_widened": noedge_level_for(wid),
            "miss_rate_95_at_0": rate["0"][0.95], "miss_rate_by_level_at_0": rate["0"],
            "ok_miss_at_0": rate["0"][0.95] <= 0.05, "level_widened_at_0": wid0,
            "level_noedge_widened_at_0": noedge_level_for(wid0)}


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
    # degenerate designs give NaN, not an exception: H5's indicator constant (every trade, or none, near the high)
    for dd in (np.ones(n), np.zeros(n)):
        b1, s1, t1, p1, df1 = cluster_ols(y, dd, g)
        assert np.isnan([b1[1], s1[1], t1[1], p1[1]]).all() and df1 == G - 1
        assert verdict(holm(np.r_[p1[1], np.full(11, 0.5)])[0], True, b1[1] + 2.6 * s1[1], E["H5"]) == "INCONCLUSIVE"
        if dd[0] == 1:                                   # all ones: the intercept is not identified either
            assert np.isnan(b1[0]) and np.isnan(s1[0])
        else:                                            # all zeros: the intercept is the mean, as cluster_t
            assert abs(b1[0] - m) < 1e-14 and abs(s1[0] - se1) < 1e-14
    # a collinear extra column: the identified coefficient (intercept) is estimated as before, the others are NaN
    b2, s2, t2, p2, _ = cluster_ols(y, np.column_stack([np.ones(n), d, 2 * d]), g)
    assert abs(b2[0] - beta[0]) < 1e-12 and abs(s2[0] - se[0]) < 1e-12 and np.isnan(b2[1:]).all()
    b3, s3, t3, p3, df3 = cluster_ols(y, d, np.zeros(n))                  # one cluster: no SE
    assert np.isnan(s3).all() and np.isnan(p3).all() and df3 == 0 and abs(b3[1] - beta[1]) < 1e-12
    say(f"  cluster_ols: intercept-only = cluster_t; dummy coefficient = difference of group means; sandwich "
        f"matches an explicit loop (se {se[1]:.5f}, df {df}); a constant indicator or one cluster gives NaN "
        f"(INCONCLUSIVE), a collinear column leaves the identified intercept unchanged")


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


def _check_trade_test_labels(say):
    rng = np.random.default_rng(12)
    x = rng.normal(0.01, 0.05, 60); g = np.repeat(np.arange(20), 3)
    x[[5, 17]] = np.nan                                         # dropped, as cluster_t drops them
    r = trade_test(x, g, E["H1"], B=999, seed=4)
    m, se, t, p, df = cluster_t(x, g)
    bb = boot_t_bounds(x, g, (0.95, LEVEL_NOEDGE), 999, 4)
    q = stats.t.ppf(0.975, 19)
    assert r["n"] == 58 and r["G"] == 20 and r["df"] == 19 and (r["mean"], r["se"], r["t"], r["p"]) == (m, se, t, p)
    assert np.allclose(r["ci95"], (m - q * se, m + q * se), rtol=0, atol=1e-15) and r["ci95_boot"] == bb["ci"]
    assert r["ub95"] == bb["ub"][0.95] and r["ub_noedge"] == bb["ub"][LEVEL_NOEDGE] and r["ub95"] < r["ub_noedge"]
    assert abs(r["mde"] / se - (Z_NOEDGE + Z_POWER)) < 1e-12 and r["noedge"] == (r["ub_noedge"] < E["H1"])
    r1 = trade_test([0.01, 0.02, 0.03], [202101] * 3, E["H1"], B=99)       # one cluster: G 1, no SE, no verdict
    assert r1["n"] == 3 and r1["G"] == 1 and np.isnan(r1["se"]) and np.isnan(r1["p"]) and not r1["noedge"]
    # cluster labels: quarters; overlap episodes (A [1,5] and B [3,8] overlap; C [9,10] and D [10,12] touch at 10;
    # E opens on 20 and never closes, so F on Feb 1 joins it)
    D = lambda s_: pd.Timestamp(s_, tz="UTC")
    assert quarter_key(pd.Series([D("2021-03-31 23:00"), D("2021-04-01"), D("2021-12-31 23:59")])).tolist() == \
        [20211, 20212, 20214]
    ent = pd.Series([D("2021-01-01"), D("2021-01-03"), D("2021-01-09"), D("2021-01-10"), D("2021-01-20"),
                     D("2021-02-01")])
    ext = pd.Series([D("2021-01-05"), D("2021-01-08"), D("2021-01-10"), D("2021-01-12"), pd.NaT, D("2021-02-02")])
    assert overlap_episodes(ent, ext).tolist() == [0, 0, 1, 1, 2, 2]
    sh = np.array([5, 2, 0, 4, 3, 1])                           # order-free: the same episodes in any row order
    assert overlap_episodes(ent.iloc[sh].reset_index(drop=True), ext.iloc[sh].reset_index(drop=True)).tolist() == \
        [2, 1, 0, 2, 1, 0]
    assert month_key(pd.Series([D("2021-01-31 23:59")]).dt.tz_convert("America/New_York"))[0] == 202101   # UTC month
    say("  trade_test: fields = cluster_t / boot_t_bounds / mde, NaN dropped, G counted from the data (1 cluster -> "
        "G 1, NaN SE); quarter_key and overlap_episodes hand cases (touching holdings join; an open one absorbs "
        "later ones); month_key in UTC")


def _check_portfolio_test(say):
    rng = np.random.default_rng(13)
    a = 0.0004 + 0.01 * rng.standard_normal(1500); b = 0.0003 + 0.01 * rng.standard_normal(1500)
    for kind, unit in (("stock", 21.0), ("crypto", 365 / 12)):
        for stat in ("mean", "sharpe_diff"):
            P = portfolio_test(a, b, stat, kind, B=499, seed=2)
            by = P["by_block"]
            assert list(by) == [1, 3, 12] and all(abs(by[m]["mean_block"] - m * unit) < 1e-12 for m in by)
            assert P["p"] == max(by[1]["p"], by[3]["p"]) and P["ub"] == max(by[1]["ub"], by[3]["ub"])
            assert P["ub95"] == max(by[1]["ub95"], by[3]["ub95"]) and P["estimate"] == by[1]["estimate"]
            assert by[1]["ppy"] == PPY[kind]
            one = block_boot(a, b, stat, unit, 499, 2, LEVEL_NOEDGE, PPY[kind])
            assert one["p"] == by[1]["p"] and one["ub"] == by[1]["ub"]
    P = portfolio_test(a, b, "mean", "crypto", B=499, block_days=28)       # H10: one 28-day block length decides
    assert list(P["by_block"]) == [28] and P["p"] == P["by_block"][28]["p"] and P["by_block"][28]["mean_block"] == 28
    # degenerate Sharpe inputs (a == b; a constant series) give NaN, not an exception, and verdict INCONCLUSIVE;
    # NaN propagates through portfolio_test's max
    for A_, B_ in ((a, a), (np.zeros(500), None), (np.zeros(500), b[:500]), (a[:500], np.full(500, 0.001))):
        r = block_boot(A_, B_, "sharpe_diff", 30, B=199, seed=1)
        assert np.isnan(r["p"]) and np.isnan(r["ub"]) and np.isnan(r["ci95"][0]) and r["degenerate"]
        assert verdict(holm(np.r_[r["p"], np.full(11, 0.5)])[0], True, r["ub"], E["H2"]) == "INCONCLUSIVE"
    Pd = portfolio_test(a, a, "sharpe_diff", "crypto", B=199)
    assert np.isnan(Pd["p"]) and np.isnan(Pd["ub"])
    say("  portfolio_test: blocks 1/3/12 months of 21 sessions (stocks) or 365/12 days (crypto), verdict p and "
        "bounds = max over 1 and 3 months, the 1-month run = block_boot; block_days=28 alone decides (H10); "
        "a == b or a constant series -> NaN p and bound (INCONCLUSIVE), no exception")


def _check_sharpe_se(say):
    """Known answers for the Sharpe-difference SE: the QS-HAC long-run variance of an AR(1) (1/(1-phi)^2 = 4 at
    phi 0.5) and the iid-normal closed form of the Sharpe-difference variance (Memmel 2003, JKM 1981)."""
    rng = np.random.default_rng(14)
    T = 200_000
    e = rng.standard_normal(T)
    y = np.empty(T); y[0] = e[0]
    for t in range(1, T):
        y[t] = 0.5 * y[t - 1] + e[t]
    lrv = hac_qs_prewhitened((y - y.mean())[:, None])[0, 0]
    assert abs(lrv / 4.0 - 1) < 0.05, lrv
    lrv0 = hac_qs_prewhitened((e - e.mean())[:, None])[0, 0]                # white noise: 1
    assert abs(lrv0 - 1) < 0.03, lrv0
    T = 20_000; rho = 0.6; sa, sb_ = 0.02, 0.03; ma, mb = 0.001, 0.0012
    z = rng.standard_normal((T, 2)) @ np.linalg.cholesky(np.array([[1, rho], [rho, 1]])).T
    a = ma + sa * z[:, 0]; b = mb + sb_ * z[:, 1]
    SRa, SRb = ma / sa, mb / sb_
    se_m = math.sqrt((2 - 2 * rho + 0.5 * (SRa ** 2 + SRb ** 2 - 2 * SRa * SRb * rho ** 2)) / T)
    r = block_boot(a, b, "sharpe_diff", 30.4, B=999, seed=3)
    se_q, se_b = r["se"] / math.sqrt(365), r["se_boot"] / math.sqrt(365)
    assert abs(se_q / se_m - 1) < 0.05 and abs(se_b / se_m - 1) < 0.08, (se_q, se_b, se_m)
    # the one-sample Sharpe SE: sqrt((1 + SR^2 / 2) / T) under iid normality
    r1 = block_boot(a, None, "sharpe_diff", 30.4, B=199, seed=3)
    se1 = math.sqrt((1 + 0.5 * SRa ** 2) / T)
    assert abs(r1["se"] / math.sqrt(365) / se1 - 1) < 0.05
    say(f"  QS-HAC long-run variance: AR(1) phi 0.5 {lrv:.3f} (true 4), white noise {lrv0:.3f} (true 1); "
        f"Sharpe-difference SE (iid normal, rho 0.6, T 20,000): QS-HAC {se_q:.5f}, bootstrap SD {se_b:.5f}, "
        f"closed form {se_m:.5f}; one-sample Sharpe SE {r1['se'] / math.sqrt(365):.5f} vs {se1:.5f}")


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
    cov = {"ub95_below": 0, "ci95_miss": 0}      # the studentized bounds at the true difference 0 (QS-HAC)
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
            if m_ == "qs":
                cov["ub95_below"] += rr["ub95"] < 0
                cov["ci95_miss"] += not (rr["ci95"][0] <= 0 <= rr["ci95"][1])
                assert rr["ub95"] < rr["ub"] and rr["ci95"][0] < rr["estimate"] < rr["ci95"][1]
        rr = block_boot(a - b + 0.05 * (sb_ - sa), None, "mean", 30, B=B, seed=rp)   # population mean 0
        rej_mean += rr["p"] < 0.05
    return rej, rej_mean, cov


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
    # an undefined value (NaN ret_adj: empty leave-out sample) is not a 0 return: that signal is NaN (dropped by
    # the tests, as cluster_t drops the trade) and counted; a skipped signal still counts 0
    bn = base.copy(); bn.loc[1, "ret_adj"] = np.nan                  # BTC 2021-02-01, present in both variants
    vn = var.copy(); vn.loc[2, "ret_adj"] = np.nan                   # one of the two BTC 2021-03-01 variant trades
    Pn0 = paired_signal_diff(bn, vn)
    assert Pn0.attrs["n_nan"] == 2 and Pn0.attrs["n_nan_by_col"] == {"ret_adj": 2}
    Pn = Pn0.set_index(["sym", "signal_day"])
    k1, k2 = ("BTC", D("2021-02-01")), ("BTC", D("2021-03-01"))
    assert np.isnan(Pn.loc[k1, "base"]) and np.isnan(Pn.loc[k1, "diff"]) and Pn.loc[k1, "in_base"]
    assert np.isnan(Pn.loc[k2, "var"]) and np.isnan(Pn.loc[k2, "diff"]) and abs(Pn.loc[k2, "base"] - 0.02) < 1e-15
    assert Pn.loc[("BTC", D("2021-04-01")), "base"] == 0.0 and Pn.loc[("BTC", D("2021-01-05")), "var"] == 0.0
    ok_ = np.isfinite(Pn["diff"].to_numpy())
    assert abs(cluster_t(Pn["diff"], Pn["month"])[0] - Pn["diff"].to_numpy()[ok_].mean()) < 1e-15
    Pn2 = paired_signal_diff(bn, vn, col=["ret_adj", "ret"])
    assert Pn2.attrs["n_nan_by_col"] == {"ret_adj": 2, "ret": 0} and np.isfinite(Pn2["diff_ret"]).all()
    say("  paired_signal_diff: union of signals, skipped = 0, duplicates summed, (sym, day) keys, entry-month "
        "clusters; mean over the union = total-return difference / union size; a present trade's NaN value "
        "makes its signal NaN (dropped and counted), not 0")


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
    # (iii) alternative expo formats: integer hour positions, a tuple, a dict per sym. The exposure times are read
    # only for a trade without entry1_time or exit_time, so some are blanked: the integer positions then decide
    # those trades' windows, and wrong positions must change exactly those trades
    pos_h = np.concatenate([np.arange(r["_h0"], r["_h0"] + r["_L"]) for _, r in tr.iterrows()])
    t8 = tr.copy()
    t8.loc[[1, 4, 30], "exit_time"] = pd.NaT
    t8.loc[[2, 30], "entry1_time"] = pd.NaT
    a4 = drift_adjust(t8, (expo["pos"].to_numpy(), pos_h, expo["notional"].to_numpy()), rets)
    assert np.allclose(a4.to_numpy(), adj["ret_adj"].to_numpy(), atol=1e-15, rtol=0)
    a4b = drift_adjust(t8, (expo["pos"].to_numpy(), (pos_h + 24 * 400) % len(hours), expo["notional"].to_numpy()),
                       rets)
    changed = np.flatnonzero(np.abs(a4b.to_numpy() - adj["ret_adj"].to_numpy()) > 1e-12)
    assert set(changed.tolist()) == {1, 2, 4, 30}, changed
    ed = {s: expo[expo["pos"].str.startswith(s)] for s in ("AAA", "BBB")}
    a5 = drift_adjust(tr, ed, rets)
    assert np.allclose(a5.to_numpy(), adj["ret_adj"].to_numpy(), atol=1e-15, rtol=0)
    assert a5.attrs["n_no_expo"] == 0
    # (vi) a key mismatch between trades and expo (symbol label, position-id spelling) is an error, not a silent
    # zero drift charge; missing_expo="warn" keeps the 0 charge, warns and counts
    import warnings
    bad_sym = {s + "USDT": v for s, v in ed.items()}
    bad_pos = expo.assign(pos=expo["pos"].str.replace("AAA", "AAA_", regex=False))
    for bad in (bad_sym, bad_pos):
        try:
            drift_adjust(tr, bad, rets)
            raise AssertionError("a trades/expo key mismatch must raise")
        except ValueError as ex_:
            assert "no exposure rows" in str(ex_)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            aw = drift_adjust(tr, bad, rets, parts=True, missing_expo="warn")
        n_bad = 50 if bad is bad_sym else 25
        assert len(w) == 1 and aw.attrs["n_no_expo"] == n_bad and (aw["expo_sum"] == 0).sum() == n_bad
    t9 = tr.iloc[:3].copy(); t9["pid"] = ["X1", "X2", "X3"]; t9["ret"] = 0.0     # no exposure, no return: allowed
    a9 = drift_adjust(t9, expo, rets)
    assert a9.attrs["n_no_expo"] == 3 and (a9 == 0).all()
    t9["hold_h"] = [0, 5, 0]
    try:
        drift_adjust(t9, expo, rets)
        raise AssertionError("a held position without exposure rows must raise")
    except ValueError:
        pass
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
        "constant returns -> 0 exactly, shorts included; tuple / dict / integer-hour expo formats agree, and wrong "
        "integer hours change exactly the 4 trades whose window they set; a sym or position-id mismatch raises "
        "(warn mode counts it in n_no_expo)")


def _check_misc(say):
    # returns_from_hours on a coin_hours-shaped frame: outage carried flat (0, then the gap's move), market switch,
    # perpetual end, non-tradable filler and a series break
    idx = pd.date_range("2022-01-01", periods=10, freq="h", tz="UTC")
    h = pd.DataFrame({"close": [100.0, 101, 101, 103, 104, 110, 110, 110, 2.0, 2.2],
                      "is_perp": [False, False, False, False, True, True, False, False, False, False],
                      "tradable": [True, True, True, True, True, True, False, False, True, True],
                      "seg": [0, 0, 0, 0, 0, 0, 0, 0, 1, 1]}, index=idx)
    r = returns_from_hours(h)
    want = [np.nan, 0.01, 0.0, 103 / 101 - 1, np.nan, 110 / 104 - 1, np.nan, np.nan, np.nan, 0.1]
    assert np.allclose(r.to_numpy(), want, equal_nan=True, atol=1e-15), r.to_numpy()
    # force_inconclusive and the "carried by one month" label
    assert verdict(0.001, True, 0.10, 0.0025, force_inconclusive=True) == "INCONCLUSIVE"
    assert verdict(0.5, True, -0.01, 0.0025, force_inconclusive=True) == "INCONCLUSIVE"
    assert pass_label("PASS", -0.001) == "PASS, carried by one month" and pass_label("PASS", 0.002) == "PASS"
    assert pass_label("PASS", 0.0) == "PASS, carried by one month" and pass_label("NO EDGE", -1) == "NO EDGE"
    # descriptive intervals: the cluster bootstrap of a mean brackets it and matches the analytic interval roughly;
    # the block-bootstrap multiple of a constant series is exact
    rng = np.random.default_rng(6)
    g = rng.integers(0, 50, 400); x = rng.normal(0.01, 0.05, 400) + rng.normal(0, 0.02, 50)[g]
    est, lo, hi, nv = cluster_boot_ci(len(x), g, lambda rows: x[rows].mean(), B=1999, seed=1)
    m, se, *_ = cluster_t(x, g)
    assert est == m and lo < m < hi and nv == 1999 and abs((hi - lo) / (2 * 1.96 * se) - 1) < 0.15, (lo, hi, se)
    est, lo, hi = block_boot_ci(np.full(300, 0.001), multiple_fn, 30, B=199)
    assert abs(est - 1.001 ** 300) < 1e-12 and abs(lo - est) < 1e-12 and abs(hi - est) < 1e-12
    assert abs(maxdd_fn(np.array([[0.1, -0.5, 0.2, -0.1]]))[0] - 0.5) < 1e-12      # 1.1 -> 0.55 is the worst
    assert abs(maxdd_fn(np.array([[-0.2, 0.1]]))[0] - 0.2) < 1e-12                  # from the starting equity 1
    # coin_returns on a frame shaped like bb_data.coin_hours, through a stand-in for bb_data.coin_hours (no market
    # data is read): a 2-hour outage gap (trades 0, OHLC carried), the spot -> perpetual switch, then perp_end and
    # non-tradable filler after the perpetual ended
    from analysis_2026 import bb_data
    ix = pd.date_range("2023-03-01", periods=12, freq="h", tz="UTC")
    cl = [10.0, 10.5, 10.5, 10.5, 11.0, 11.1, 11.0, 12.0, 12.0, 12.0, 12.0, 12.0]
    fake = pd.DataFrame({"open": cl, "high": cl, "low": cl, "close": cl,
                         "trades": [5, 5, 0, 0, 7, 7, 9, 9, 9, 0, 0, 0],
                         "is_perp": [False] * 6 + [True] * 6, "spot_only": [True] * 6 + [False] * 6,
                         "tradable": [True] * 9 + [False] * 3, "perp_end": [False] * 8 + [True] + [False] * 3,
                         "seg": 0}, index=ix)
    want = [np.nan, 0.05, 0.0, 0.0, 11 / 10.5 - 1, 11.1 / 11 - 1, np.nan, 12 / 11 - 1, 0.0, np.nan, np.nan, np.nan]
    orig = bb_data.coin_hours
    try:
        bb_data.coin_hours = lambda sym, start=None, end=None: fake
        rc = coin_returns("FAKE")
    finally:
        bb_data.coin_hours = orig
    assert np.allclose(rc.to_numpy(), want, equal_nan=True, atol=1e-15) and rc.index.equals(ix), rc.to_numpy()
    # inference_control: the reference is never the mean of the scored paths. Built-in generator: the analytic 0;
    # a custom sim_fn must give it; "independent" estimates it on separate paths with disjoint seeds. It accepts
    # the engine's {"trades", "expo", "rets"} and drift-adjusts it itself
    a = inference_control(_sim_dict, n_paths=3, B=199, seed=3, true_mean=0.0)
    b = inference_control(builtin_sim, n_paths=3, B=199, seed=3)
    c = inference_control(None, n_paths=3, B=199, seed=3)
    assert a["true_mean"] == b["true_mean"] == c["true_mean"] == 0.0 and b["true_mean_source"].startswith("analytic")
    assert a["reject_rate"] == b["reject_rate"] and a["miss_rate_by_level"] == b["miss_rate_by_level"] == \
        c["miss_rate_by_level"] == b["miss_rate_by_level_at_0"] and b["scored_grand_mean"] != 0.0
    try:
        inference_control(_sim_dict, n_paths=1, B=99)
        raise AssertionError("a custom sim_fn without true_mean must raise")
    except ValueError:
        pass
    d = inference_control(builtin_sim, n_paths=2, B=99, seed=3, true_mean="independent", n_ref_paths=3)
    sc = {int(v) for v in np.random.default_rng(3).integers(0, 2 ** 62, 2)}
    rs = [int(v) for v in np.random.default_rng([3, 1]).integers(0, 2 ** 62, 3)]
    xr = np.concatenate([_ic_path(builtin_sim(v), None)[0] for v in rs])
    assert not (sc & set(rs)) and abs(d["true_mean"] - xr.mean()) < 1e-15 and d["true_mean"] != d["scored_grand_mean"]
    assert d["true_mean_source"].startswith("independent") and np.isfinite(d["true_mean_se"])
    # the widening rule and the NO EDGE level it implies
    gr = (0.95, 0.955, 0.96)
    assert _widen({0.95: 0.06, 0.955: 0.05, 0.96: 0.03}, gr) == 0.955 and _widen({0.95: 0.05}, (0.95,)) is None
    assert np.isnan(_widen({0.95: 0.07, 0.955: 0.06, 0.96: 0.055}, gr))
    assert noedge_level_for(None) == LEVEL_NOEDGE and abs(noedge_level_for(0.955) - (1 - 0.05 / 12 * 0.9)) < 1e-15
    assert noedge_level_for(0.95) == LEVEL_NOEDGE or abs(noedge_level_for(0.95) - LEVEL_NOEDGE) < 1e-15
    say("  returns_from_hours / coin_returns (stand-in coin_hours): NaN at market switch / non-tradable / series "
        "break, outages carried and the gap's move on the next live hour; force_inconclusive; 'PASS, carried by "
        "one month'; cluster/block percentile intervals; inference_control: built-in reference = analytic 0, a "
        "custom sim_fn must give one, 'independent' uses disjoint seeds, engine-shaped dict accepted; widening "
        "rule and its NO EDGE level")


def _sim_dict(seed: int) -> dict:
    return simple_three_coin_trades(seed)


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
    say("trade_test, cluster labels")
    _check_trade_test_labels(say)
    say("drift_adjust")
    _check_drift_adjust(say)
    say("returns_from_hours, verdict extras, descriptive intervals")
    _check_misc(say)
    say("bootstrap-t coverage")
    _check_boot_t(say)
    say("block bootstrap")
    reps = 400
    rej, rej_mean, cov = _check_block_boot(say, reps)
    say("  stationary bootstrap: mean block ~ requested; p formula reproduced; logdiff ruin -> -inf, NO EDGE "
        "(HARMS)")
    say(f"  Sharpe-difference size under the null (correlated 0.7, GARCH vol, T 1500, block 30, B 499, {reps} reps):"
        f" QS-HAC {rej['qs'] / reps:.3f}, SB-kernel {rej['sb'] / reps:.3f}; mean-difference size "
        f"{rej_mean / reps:.3f}; nominal 0.050")
    say(f"  studentized Sharpe-difference bounds at the true difference 0: 95% upper bound below it "
        f"{cov['ub95_below'] / reps:.3f} (nominal 0.050), 95% interval misses it {cov['ci95_miss'] / reps:.3f} "
        f"(nominal 0.050)")
    assert 0.015 <= rej["qs"] / reps <= 0.09 and 0.015 <= rej["sb"] / reps <= 0.09 and rej_mean / reps <= 0.09
    assert 0.015 <= cov["ub95_below"] / reps <= 0.09 and 0.015 <= cov["ci95_miss"] / reps <= 0.10, cov
    say("Sharpe-difference SE known answers")
    _check_sharpe_se(say)
    say("portfolio_test")
    _check_portfolio_test(say)
    say("built-in trade generator")
    _check_generator(say)
    say("inference control (built-in generator, 200 paths, B 9999)")
    ic = inference_control(n_paths=200)
    say(f"  {ic['n_paths']} paths, {ic['mean_trades_per_path']:.0f} trades and {ic['mean_G']:.0f} months each; "
        f"true mean {ic['true_mean']:+.5f} ({ic['true_mean_source']}); the scored paths' own grand mean "
        f"{ic['scored_grand_mean']:+.5f} is not used")
    say(f"  month-clustered t rejects at nominal 5%: {ic['reject_rate']:.3f} (95% CI {ic['reject_ci'][0]:.3f}-"
        f"{ic['reject_ci'][1]:.3f}); centred at the true mean {ic['reject_rate_centered']:.3f}")
    say(f"  95% bound below the true mean: bootstrap-t {ic['miss_rate_95']:.3f} (CI {ic['miss_ci_95'][0]:.3f}-"
        f"{ic['miss_ci_95'][1]:.3f}), analytic {ic['miss_rate_analytic_95']:.3f}; at the NO EDGE level "
        f"{ic['miss_rate_noedge']:.3f}")
    rate = ic["miss_rate_by_level"]
    say("  miss rate by level: " + ", ".join(f"{lv:.4g} {v:.3f}" for lv, v in rate.items()))
    # the pre-registered point criterion and the widening rule (the binomial test is supplementary)
    lw = ic["level_widened"]
    say(f"  CONTROL OUTCOME: rejection rate {ic['reject_rate']:.3f} <= 0.05: {ic['ok_reject']}; 95% miss rate "
        f"{ic['miss_rate_95']:.3f} <= 0.05: {ic['ok_miss']} -> "
        + ("no widening" if lw is None else
           f"the widening rule applies: 95% level -> {lw}, NO EDGE level {LEVEL_NOEDGE:.5f} -> "
           f"{ic['level_noedge_widened']:.5f} (proportional tail; the orchestrator applies it before primary "
           f"results are read)"))
    assert ic["true_mean"] == 0.0 and ic["true_mean_source"].startswith("analytic")       # finding 1 regression
    assert ic["miss_rate_95_at_0"] == ic["miss_rate_95"] and ic["level_widened_at_0"] == lw
    if ic["ok_miss"]:
        assert lw is None and ic["level_noedge_widened"] == LEVEL_NOEDGE
    else:
        assert lw is not None and np.isfinite(lw) and rate[lw] <= 0.05, (lw, rate)
        assert all(rate[v] > 0.05 for v in rate if v < lw) and ic["level_noedge_widened"] > LEVEL_NOEDGE
    # neither rate significantly above 5% (binomial, 200 paths): the bound is not grossly miscalibrated
    assert ic["ok_reject"] and ic["ok_reject_binomial"] and ic["ok_miss_binomial"], ic
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
