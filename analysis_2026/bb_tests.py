"""
The twelve Holm-family tests of the Bollinger-breakout replication and the verdict report
(analysis_2026/BB_REPLICATION_PREREG.md: "Hypotheses and pass rules" -> "Units and statistics", "Multiplicity",
"Verdicts", "The tests" H1-H10, HS1, HS2; "The answer to the user (fixed now)"; "Reporting rules"; the Windows'
halves and pre-perpetual block; "Stocks and ETFs"; Addendum and Addendum 2). Contract: the scratchpad's
bb_engine_spec.md, "Integration layer". The trade engine, statistics, grid, stocks and benchmarks are
analysis_2026/bb_engine.py, bb_stats.py, bb_grid.py, bb_stocks.py and bb_bench.py; nothing here re-implements them.

    python3 -m analysis_2026.bb_tests selftest     # synthetic known answers (no market data is read)
    python3 -m analysis_2026.bb_replica primary    # the runner (refuses unless every control passed)
    python3 -m analysis_2026.bb_replica report     # Holm, gates, verdicts, answer map -> results_bb/verdicts.*

Public API
  Env(...)                     the tests' data sources: bb_data / bb_engine / bb_bench / bb_grid / bb_stocks on disk
                               by default; injected hourly, 1-minute and stock frames for the self-test; the levels
                               of the bounds (level_noedge and level95 from results_bb/controls/inference.json)
  test_h1(env) .. test_h10(env), test_hs1(env), test_hs2(env) -> (result, details)
                               one function per test: runs the engine and computes the test (result: a JSON-able
                               dict; details: {name: DataFrame} written as CSVs)
  h1_stats .. h10_stats, hs_stats, trade_comp, port_comp, ols_boot_t, h6_delays, beats_holding
                               the statistics of each test on given trades / account returns (the self-test feeds
                               them constructed inputs with known answers)
  seed_jobs(res, env), seed_finalize(res, outs)   HS1's 100 further seeds (bootstrapped in run()'s second pool pass)
  answer_map(V, tests, out)    the answer to the user (fixed now) from the verdict table
  run(out_dir, which=None, jobs=4, level_noedge=None, level95=None, env=None) -> dict
                               runs the tests in a process pool, writes <out_dir>/primary/{tests.json, tests.csv,
                               <test>_*.csv}; every engine, grid and stock run asserts an empty fill audit; a subset
                               (which=) merges only into a tests.json computed at the same levels
  report(out_dir, level_noedge=None, level95=None) -> DataFrame
                               Holm across the 12 one-sided p-values (whatever their other conditions), every gate,
                               the both-halves rule, verdicts (bb_stats.verdict with each test's E and its NO EDGE
                               bound), MDE, "PASS, carried by one month", HS1's seed rule and the answer map ->
                               <out_dir>/verdicts.csv and verdicts.txt (H1, H2, HS1, HS2 first); refuses unless every
                               bound is at one level, the controls' (choice 1)
  selftest()

Each test (pre-registration row, "Units and statistics" and Addendum 2's rulings)
  H1   S1 at L = 1 (ROWS["S1_L1"]) on BTC/ETH/SOL, Full window: month-clustered t of the drift-adjusted mean per
       trade (bootstrap-t NO EDGE bound); gates: unadjusted mean > 0, drift-adjusted mean > 0 in both halves, > 0
       pooled over the other 37 coins (month-clustered 95% interval reported), > 0 on the S12 crypto-only
       all-contract top-3 universe (bb_engine.H1_S12_GATE); month-dropped mean, top-5% share; the pre-perpetual
       block beside it (exploratory); the other-37, S12 and pre-perpetual pools also without ZEC (choice 17).
  H2   S1 at L = 1 three-slot account (bb_engine.assemble, rule 11, idle cash at the T-bill) vs (a)
       bb_bench.bh_crypto (1/K sleeves; Addendum 2) and (b) bb_bench.moneyline_perp: studentized Sharpe difference
       of daily excess returns (bb_stats.portfolio_test: verdict p = max of the 1- and 3-month block p; 12 months
       reported); p = max(p_BH, p_ML). The raw 0%-cash version, H2(a) with equal weights among joined coins, and
       the pre-perpetual block are reported.
  H3   R0 vs S4 (L = 3, Addendum 2): per-signal paired drift-adjusted difference per M (R0 - S4); exposure-time
       unit sum(ret_adj) / sum(notional x days) of R0 above S4's (delta method); sign disagreement -> INCONCLUSIVE.
  H4   S1 (L = 3) close arm vs bb_engine.h4_touch_cfg(): per-episode paired difference (S1 - touch) over
       bb_engine.h4_episodes, clustered by episode start month.
  H5   S1 with near_high="off" (L = 3): drift-adjusted ret on [1, near-high indicator] (bb_engine's near_r0),
       month-clustered OLS; totals with and without the filter.
  H6   all 576 (entry, exit) New York hour pairs (bb_engine.h6_cfg) paired per signal vs S1; R0's pair (06, 13):
       Holm p of its paired difference, rank <= 28 on the raw per-signal mean and on its residual after OLS on
       entry / exit delay (linear + quadratic).
  H7   S1W + rule 12 vs S1W per signal; rule 12 (Fri, Sat) ranks first among the 7 consecutive-day-pair blocks.
  H8   (a) S1W + 72 h minimum hold and (b) S1W + rule 15 (Sat, Sun bars) each vs S1W per signal; p = max(p_a,
       p_b); Sat+Sun ranks first among the 7 consecutive-day-pair deferrals; dose-response 0-168 h (exploratory).
  H9   R0 three-slot account at L = 3 vs L = 1: mean daily log-return difference (bb_stats logdiff; equity floored
       at 0, ruin -> -inf -> NO EDGE (HARMS)); growth at L = 1..5, the growth-optimal L with a 90% bootstrap
       interval, m/s^2 of L = 1, exposure, liquidations, drawdowns. Also the answer map's "full strategy beats
       holding the coins" interval (R0 L = 3 vs 1x buy-and-hold).
  H10  R0 + G-A vs R0 on BTC/ETH/SOL 2024-07-01..2026-10-16 (bb_grid.grid_ga + merge_ga + bb_engine.assemble):
       mean daily difference of account returns, block 28 days; fee scenario base decides, vip and zero (and the
       optimistic touch fill) reported; the zero-interest version and the 1-, 3- and 12-month blocks reported
       (choice 10); grid profit, inventory P&L, fees, per deployment.
  HS1  bb_stocks on point-in-time members 2001-01..2026-10: p_trade = month-clustered t of the drift-adjusted mean
       over every signal; p_Sharpe = block bootstrap of the 20-slot portfolio's (seed 20261018) daily excess
       returns vs benchmark_ew_members; p = max; both > 0 in both halves; 100 further seeds (median, 5-95%);
       atr_dist ranking, matched random-entry book, zero-interest version and 1996-2000 reported.
  HS2  the same on the 14 ETFs with a 14-slot portfolio (Addendum 2) vs benchmark_ew_etfs.

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. Every NO EDGE bound is at results_bb/controls/inference.json's level_noedge (the controls' widened level; the
   spec: "to be used by every NO EDGE bound"), portfolio tests included. "The largest effect ruled out at 95%"
   of a trade-level or paired test is the month-cluster bootstrap-t bound at inference.json's level95 (the
   nominal 95% bound is reported beside it); for portfolio tests it is block_boot's 95% bound (the inference
   control does not measure block-bootstrap coverage). The two-sided 95% interval of a trade-level or paired
   test is the analytic month-clustered t interval (the test's own statistic; the bootstrap-t interval is in
   tests.json); of a portfolio test, block_boot's 1-month interval. MDE = bb_stats.mde(SE) with the SE of the
   component that decides the test (the larger p). One level for the whole family: report() refuses unless every
   component's level_noedge (and level95, where a component has one) is the same and equals controls/inference.json's
   (the runner passes the controls' levels); run() refuses to merge a subset run (which=...) into a tests.json
   computed at another level (re-run every test instead).
2. "Both halves" for a compound test (H2, H8, HS1, HS2) requires every component's point estimate > 0 in both
   halves. Portfolio halves split the full run's daily returns by day (no restart at the half boundary); trade
   and paired halves assign a trade by its entry1 time and a signal by its paired month (the base trade's entry
   month, else the variant's, as bb_stats.paired_signal_diff).
3. H1's S12 gate runs H1's strategy (ROWS["S1_L1"]) on the universe of bb_engine.H1_S12_GATE (coins from
   row_coins, membership from s12_allowed(sym, 3, "all", tradfi=False)); ROWS["S12_all_top3"] itself is R0's
   cfg, but the gate is a condition on H1's own statistic. The other 37 coins and the S12 universe each run
   every coin as its own slot over the Full window, pooled, month-clustered.
4. H3's exposure-time condition is the point estimate dR = R(R0) - R(S4) > 0 (its delta-method SE and one-sided
   p are reported, not in Holm); notional x days = expo_sum / 24 (expo_sum: the engine's sum over held hours of
   notional / M). A sign disagreement between dR and the per-signal mean forces INCONCLUSIVE (a zero or NaN
   either side does not force it).
5. H4's statistic is over the union of episodes in which at least one arm traded (bb_stats.paired_signal_diff on
   (sym, episode), the per-signal convention); episodes with no trade in either arm are counted, not averaged.
   An S1 trade outside every episode is its own episode (bb_engine.assign_episodes), unmatched by the touch arm;
   its cluster month is its entry month.
6. H5's NO EDGE bound is a month-cluster bootstrap-t of the indicator's coefficient (ols_boot_t: clusters
   resampled with replacement, the coefficient and its CR1 SE recomputed on each draw in closed form for the
   binary regressor; bb_stats has the bootstrap-t only for a mean). E is H5's per-signal 0.25% of M (bb_stats.E).
   "Total drift-adjusted P&L with and without the filter": the near_high="off" run's total and ROWS["S1"]'s.
7. H6's ranks: per-signal mean of (pair - S1) over the union, largest first; a tie counts against the pair (rank =
   number of pairs with a mean >= its own). Delays are hours from the deciding 00:00 UTC close to the first hour
   at or after it whose New York hour is the pair's (bb_engine choice 4), averaged over every UTC day of the Full
   window (so over DST as it occurs). The residual is from OLS of the 576 means on [1, d_e, d_e^2, d_x, d_x^2].
   R0's pair is h6_cfg(6, 13); S1W vs S1 is reported beside it.
8. H7 / H8 placebo ranks: first = strictly the largest of the 7 (a tie is not first). Every per-row p of the
   descriptive tables (H6's 576 pairs, H7's 7 blocks, H8's 7 deferrals and its dose-response) is exploratory
   ("Multiplicity"): column p_one_sided_exploratory, with p_bh_exploratory = Benjamini-Hochberg within that table. The
   Holm-family p of each test is its component's p in tests.json.
9. H9 compares account returns with idle cash and idle margin at the T-bill in both arms (the portfolio-test rule;
   a log difference of excess returns is not a growth rate); the zero-interest growth is reported. The growth-
   optimal L: the argmax over L = 1..5 and the vertex of a quadratic fit of growth on L (clipped to [1, 5]), each
   with a 90% stationary-bootstrap (1-month blocks) percentile interval. m/s^2 uses daily excess returns of the
   L = 1 account.
10. H10 uses account returns with idle cash at the T-bill in both arms; fee scenario s runs R0 and the grid at s.
   Reported only ("Portfolio-level tests": "the zero-interest version is also reported"; "also reported at 3 and 12
   months"): the base-fee difference with idle cash at 0% in both arms (28-day block), and the base-fee difference
   at mean blocks of 1, 3 and 12 months. The 28-day block of the H10 row decides.
11. HS1 / HS2: p_trade over every trade of bb_stocks.stock_trades (each name its own slot; the chained book);
   drift adjustment on bb_stocks.session_returns. The 100 further seeds (bb_stocks.SEEDS_FURTHER) are block-
   bootstrapped at 1 and 3 months for HS1. "The median seed does not pass": the Holm-adjusted p of HS1, recomputed
   with max(p_trade, the median of the 100 seeds' Sharpe p) in its place, is >= 0.05, or the median over seeds of
   either half's Sharpe difference is <= 0. The rule is HS1's (the pre-registration states it under the members
   universe); HS2's seeds (point estimates) are reported with a flag, since 14 slots for 14 ETFs never ration.
12. A test with a missing or errored result stops the report (Holm needs all 12). JSON keeps NaN and +-Infinity
   (Python's json; H9's ruin is -Infinity).
13. The answer map: "It does not work" only for NO EDGE / NO EDGE (HARMS) of the group's test (H1 crypto, HS1
   stocks, HS2 ETFs); INCONCLUSIVE reads "not shown: the data cannot tell". Every sentence carries the reporting
   label ("PASS, carried by one month"), not the bare verdict. "The core has an edge, but not over what
   you already use": H1 PASS and H2's moneyline_ref component not passing (its p substituted for H2's in the Holm
   family, plus its own halves). "Their full strategy beats holding the coins": the 95% month-block interval of
   the mean log growth difference above 0 in the full sample and both halves (crypto: R0 at L = 3 vs 1x
   buy-and-hold; stocks / ETFs: the 1x portfolio vs its equal-weight benchmark). "You can trade it": only rows
   with a TRADE gate verdict in results_bb/routes/ (with their expected false-pass counts); without routes/ it
   is undecided (applies None, "routes not run"), never "no TRADE gate verdict".
14. The pre-perpetual block (H1 trade-level, H2 account-level; exploratory) runs PRE_S1_L1 on bb_bench.spot_hours()
   (Binance spot prices throughout, as "Binance spot 2017-08-17..2019-12-31"; the perpetual lists from 2019-09) for
   every coin with spot hours before 2020.
15. "The unadjusted value is reported beside it" (H1, H3-H8, HS1, HS2): every trade-level and paired component
   carries `unadjusted` (the same month-clustered statistic on ret; H5: the OLS coefficient on ret) and
   `estimate_unadjusted`; the deciding component's is in tests.csv and verdicts.csv beside the estimate. Paired units
   come from bb_stats.paired_signal_diff on [ret_adj, ret] (_pair: diff = drift-adjusted, diff_unadj = unadjusted).
   H3's exposure-time difference on ret is reported beside the drift-adjusted one.
16. Sensitivity clusters ("Quarter clusters and overlap-episode clusters ... are reported as sensitivities"): every
   trade-level and paired component reports p_quarter_clusters and p_overlap_episode_clusters (bb_stats.
   overlap_episodes) with G_overlap_episodes. A trade's span is [entry1, exit]; a paired unit's (signal or episode)
   is the union of both arms' trades in it, earliest entry1 to latest exit (an open trade runs to +infinity). H5
   reports both for its coefficient.
17. ZEC ("Results including ZEC are always shown next to results without it"): H1's other-37 pool, its S12 top-3
   pool and its pre-perpetual block are also reported without ZEC (extra.*_ex_ZEC, with ZEC's trade count). The
   gates stay on the pre-registered pools (ZEC included).
"""
from __future__ import annotations

import json
import math
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analysis_2026.bb_data as bd        # noqa: E402
import analysis_2026.bb_engine as be      # noqa: E402
import analysis_2026.bb_stats as bs       # noqa: E402

RES = ROOT / "analysis_2026" / "results_bb"
FULL = ("2020-01-01", "2026-10-16")
HALVES_CRYPTO = {"2020-01..2022-12": ("2020-01-01", "2022-12-31"), "2023-01..2026-10": ("2023-01-01", "2026-10-16")}
H10_WIN = ("2024-07-01", "2026-10-16")
HALVES_H10 = {"2024-07..2025-08": ("2024-07-01", "2025-08-31"), "2025-09..2026-10": ("2025-09-01", "2026-10-16")}
STOCK_WIN = ("2001-01-01", "2026-10-16")
HALVES_STOCK = {"2001-2013": ("2001-01-01", "2013-12-31"), "2014-2026": ("2014-01-01", "2026-10-16")}
EARLY_STOCK = ("1996-01-01", "2000-12-31")
PRE_PERP = ("2017-08-17", "2019-12-31")
TESTS = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "HS1", "HS2"]
HEADLINE = ["H1", "H2", "HS1", "HS2"]
NAMES = {"H1": "core edge", "H2": "vs benchmarks", "H3": "pyramiding", "H4": "confirmation", "H5": "near-high filter",
         "H6": "hour rules (13-14)", "H7": "weekday rule (12)", "H8": "hold and Monday rules (6, 15)",
         "H9": "leverage (rule 4)", "H10": "grid overlay", "HS1": "stocks", "HS2": "ETFs"}
GROUP = {"H1": "crypto", "HS1": "stocks", "HS2": "ETFs"}
E = bs.E
H6_R0_PAIR = (6, 13)
H6_TOP = 28                                        # top 5% of 576
H7_RULE = (4, 5)                                   # New York Fri, Sat (Mon = 0)
H8_RULE15 = (5, 6)                                 # daily bars labelled Sat, Sun (UTC weekdays)
H8_MINHOLD = 72
H8_DOSES = (0, 24, 48, 72, 96, 120, 168)
PAIRS7 = [(d, (d + 1) % 7) for d in range(7)]
FEES = ("base", "vip", "zero")
H10_BLOCK = 28
MONTH_DAYS = bs.MONTH_DAYS
TRADE_COLS = ["sym", "pos", "signal_day", "entry1_time", "exit_time", "exit_reason", "n_tranches", "L_used", "ret",
              "ret_adj", "drift", "expo_sum", "hold_h", "open_at_end", "liquidated", "near_r0", "atH_only",
              "deferred", "episode", "ep_start"]


# ============================================================================ small helpers
def _naive(t) -> pd.DatetimeIndex:
    ix = pd.DatetimeIndex(t)
    if ix.tz is not None:
        ix = ix.tz_convert("UTC").tz_localize(None)
    return ix.as_unit("ns")


def _lo(a) -> pd.Timestamp:
    return pd.Timestamp(a).tz_localize(None) if pd.Timestamp(a).tz is not None else pd.Timestamp(a)


def _hi(b) -> pd.Timestamp:
    """Inclusive end: a date-only bound covers the whole day."""
    t = pd.Timestamp(b)
    t = t.tz_convert("UTC").tz_localize(None) if t.tz is not None else t
    if isinstance(b, str) and len(b) == 10:
        t = t + pd.Timedelta("1D") - pd.Timedelta("1ns")
    return t


def _in(times, a, b) -> np.ndarray:
    ix = _naive(times)
    return np.asarray((ix >= _lo(a)) & (ix <= _hi(b)), bool)


def _months(T: pd.DataFrame, col: str = "entry1_time") -> np.ndarray:
    return bs.month_key(T[col]) if len(T) else np.zeros(0, np.int64)


def _month_range(a, b) -> tuple:
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    return a.year * 100 + a.month, b.year * 100 + b.month


def _f(x):
    """A float (NaN for None)."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _gt0(x) -> bool:
    x = _f(x)
    return bool(np.isfinite(x) and x > 0) or x == math.inf


def _cat(res: dict) -> pd.DataFrame:
    """Concatenate the trades of {sym: result}."""
    fr = [r["trades"] for r in res.values()]
    ne = [f for f in fr if len(f)]
    if ne:
        return pd.concat(ne, ignore_index=True)
    return fr[0].copy() if fr else pd.DataFrame(columns=["sym", "pos", "signal_day", "entry1_time", "exit_time",
                                                         "ret", "ret_adj", "expo_sum", "near_r0"])


def _cols(T: pd.DataFrame, cols=TRADE_COLS) -> pd.DataFrame:
    return T[[c for c in cols if c in T.columns]].copy()


def _simple(x, g) -> dict:
    """Month-clustered mean, SE, one-sided p, df and analytic 95% interval (descriptive rows and gates)."""
    x = np.asarray(x, float)
    g = np.asarray(g)
    m, se, t, p, df = bs.cluster_t(x, g)
    q = stats.t.ppf(0.975, df) if df else np.nan
    k = np.isfinite(x)
    return {"n": int(k.sum()), "G": int(len(np.unique(g[k]))) if k.any() else 0, "mean": _f(m), "se": _f(se),
            "t": _f(t), "p": _f(p), "df": int(df), "ci95": [_f(m - q * se), _f(m + q * se)]}


def _rank_desc(v) -> np.ndarray:
    """Rank (1 = largest). A tie counts against each tied value: rank = number of values >= own (NaN last)."""
    v = np.asarray(v, float)
    w = np.where(np.isfinite(v), v, -np.inf)
    return np.array([int(np.sum(w >= x)) if np.isfinite(x) else len(v) for x in v], np.int64)


def _quarter(months) -> np.ndarray:
    g = np.asarray(months, np.int64)
    return (g // 100) * 10 + ((g % 100) - 1) // 3 + 1


def _sharpe_diff_est(a: pd.Series, b: pd.Series, ppy: int) -> float:
    """Annualized Sharpe(a) - Sharpe(b) with bb_stats' population moments (point estimate only)."""
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()

    def sh(x):
        x = x.to_numpy(float)
        if len(x) < 3:
            return np.nan
        mu = x.mean()
        v = (x * x).mean() - mu * mu
        return mu / math.sqrt(v) if v > 1e-12 * (x * x).mean() else np.nan
    return float((sh(j["a"]) - sh(j["b"])) * math.sqrt(ppy))


def _slice(s: pd.Series, a, b) -> pd.Series:
    return s[_in(s.index, a, b)]


def _logdiff_ann(a: pd.Series, b: pd.Series, ppy: int = 365) -> float:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    if not len(j):
        return np.nan
    if (1 + j["a"] <= 0).any():
        return -np.inf
    if (1 + j["b"] <= 0).any():
        return np.inf
    return float((np.log1p(j["a"]) - np.log1p(j["b"])).mean() * ppy)


def _meandiff_ann(a: pd.Series, b: pd.Series, ppy: int = 365) -> float:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    return float((j["a"] - j["b"]).mean() * ppy) if len(j) else np.nan


def _halves_trade(x, times, halves) -> dict:
    x = np.asarray(x, float)
    out = {}
    for lab, (a, b) in halves.items():
        m = _in(times, a, b) & np.isfinite(x)
        out[lab] = float(x[m].mean()) if m.any() else np.nan
    return out


def _halves_month(x, months, halves) -> dict:
    x = np.asarray(x, float)
    g = np.asarray(months, np.int64)
    out = {}
    for lab, (a, b) in halves.items():
        ma, mb = _month_range(a, b)
        m = (g >= ma) & (g <= mb) & np.isfinite(x)
        out[lab] = float(x[m].mean()) if m.any() else np.nan
    return out


def _halves_series(fn, a: pd.Series, b: pd.Series, halves) -> dict:
    return {lab: fn(_slice(a, x, y), _slice(b, x, y)) for lab, (x, y) in halves.items()}


def _maxdd(eq: pd.Series) -> float:
    e = eq.to_numpy(float)
    if not len(e):
        return np.nan
    pk = np.maximum.accumulate(np.maximum(e, e[0]))
    with np.errstate(invalid="ignore", divide="ignore"):
        dd = np.where(pk > 0, 1.0 - e / pk, 0.0)
    return float(np.nanmax(dd))


# ============================================================================ components
def trade_comp(name: str, x, months, E_: float, env, quarter: bool = True, spans=None, unadj=None) -> dict:
    """A trade-level or paired component (prereg "Units and statistics"): month-clustered mean, SE, t and one-sided
    p at G - 1 df (bb_stats.cluster_t); the analytic 95% interval; month-cluster bootstrap-t bounds at the
    nominal 95%, at level95 and at level_noedge (bb_stats.boot_t_bounds, 9,999 draws) and the bootstrap-t
    interval; MDE = bb_stats.mde(SE); quarter-cluster p and, with spans = (start, end) of each unit, the
    overlap-episode-cluster p as sensitivities (choice 16); with unadj = the same units' unadjusted values, the
    unadjusted statistic beside it (choice 15)."""
    x = np.asarray(x, float)
    g = np.asarray(months)
    s = _simple(x, g)
    lv = tuple(sorted({0.95, float(env.level95), float(env.level_noedge)}))
    with np.errstate(invalid="ignore"):            # t* = +-inf on draws with a zero clustered SE (sparse diffs)
        bb = bs.boot_t_bounds(x, g, levels=lv, B=env.B_trade, seed=bs.SEED)
    out = {"name": name, "kind": "trade", "n": s["n"], "G": s["G"], "estimate": s["mean"], "se": s["se"],
           "t": s["t"], "p": s["p"], "df": s["df"], "ci95": s["ci95"], "ci95_boot": [_f(v) for v in bb["ci"]],
           "ub95_nominal": _f(bb["ub"][0.95]), "ub95": _f(bb["ub"][float(env.level95)]),
           "ub_noedge": _f(bb["ub"][float(env.level_noedge)]), "level95": float(env.level95),
           "level_noedge": float(env.level_noedge), "E": float(E_), "mde": _f(bs.mde(s["se"]))}
    if quarter and len(g):
        out["p_quarter_clusters"] = _f(bs.cluster_t(x, _quarter(g))[3])
    if spans is not None and len(x):
        ep = bs.overlap_episodes(spans[0], spans[1])
        k = np.isfinite(x)
        out["p_overlap_episode_clusters"] = _f(bs.cluster_t(x, ep)[3])
        out["G_overlap_episodes"] = int(len(np.unique(ep[k]))) if k.any() else 0
    if unadj is not None:
        u = _simple(np.asarray(unadj, float), g)
        out["unadjusted"] = u
        out["estimate_unadjusted"] = u["mean"]
    if s["n"] >= 2 and not np.isfinite(out["ub_noedge"]):
        k = np.isfinite(x)
        out["note"] = (f"bootstrap-t NO EDGE bound undefined: {int((x[k] == 0).sum())} of {s['n']} values are exactly "
                       f"0, so some draws have a zero clustered SE (t* infinite); the bound cannot certify NO EDGE")
    return out


def _keys(base: pd.DataFrame, var: pd.DataFrame, key) -> list:
    """bb_stats.paired_signal_diff's pairing keys: (sym, key) when both frames have sym, else the given column(s)."""
    if isinstance(key, str):
        return ["sym", key] if "sym" in base.columns and "sym" in var.columns else [key]
    return list(key)


def _spans(T: pd.DataFrame, keys: list):
    """Per unit (keys): earliest entry1_time, latest exit_time and whether a trade is still open (NaT exit)."""
    if not {"entry1_time", "exit_time"} <= set(T.columns) or not set(keys) <= set(T.columns):
        return None
    f = T[keys].copy()
    f["_e"] = _naive(T["entry1_time"]).to_numpy()
    x = _naive(T["exit_time"])
    f["_x"] = x.to_numpy()
    f["_open"] = np.asarray(x.isna(), bool)
    return f.groupby(keys, sort=False, dropna=False).agg(_e=("_e", "min"), _x=("_x", "max"), _open=("_open", "any"))


def _pair(base: pd.DataFrame, var: pd.DataFrame, key="signal_day", time_col: str = "entry1_time") -> pd.DataFrame:
    """bb_stats.paired_signal_diff (union of both arms' units, a skipped unit counts 0) on ret_adj and, when both
    frames carry it, on ret (choice 15). Columns: keys, base, var, diff (drift-adjusted, the test), base_unadj,
    var_unadj, diff_unadj, in_base, in_var, month, and the unit's union span unit_start / unit_end (choice 16; NaT
    end when a trade in it is open). attrs["n_nan"] = units whose drift-adjusted diff is undefined."""
    both = "ret" in base.columns and "ret" in var.columns
    d = bs.paired_signal_diff(base, var, key=key, col=["ret_adj", "ret"] if both else "ret_adj", time_col=time_col)
    attrs = dict(d.attrs)
    keys = _keys(base, var, key)
    if both:
        d = d.rename(columns={"base_ret_adj": "base", "var_ret_adj": "var", "diff_ret_adj": "diff",
                              "base_ret": "base_unadj", "var_ret": "var_unadj", "diff_ret": "diff_unadj"})
        d = d[keys + ["base", "var", "diff", "base_unadj", "var_unadj", "diff_unadj", "in_base", "in_var", "month"]]
        attrs["n_nan"] = int((~np.isfinite(d["diff"].to_numpy(float))).sum())
    sa, sv = _spans(base, keys), _spans(var, keys)
    if sa is not None and sv is not None and len(d):
        U = sa.join(sv, how="outer", lsuffix="_b", rsuffix="_v")
        op = U["_open_b"].eq(True) | U["_open_v"].eq(True)
        S = pd.DataFrame({"unit_start": U[["_e_b", "_e_v"]].min(axis=1),
                          "unit_end": U[["_x_b", "_x_v"]].max(axis=1).where(~op)}).reset_index()
        d = d.merge(S, on=keys, how="left")
    d.attrs = attrs
    return d


def _uspans(d: pd.DataFrame):
    """(unit_start, unit_end) of paired units, or None when the trades carried no times."""
    return (d["unit_start"], d["unit_end"]) if {"unit_start", "unit_end"} <= set(d.columns) and len(d) else None


def _tspans(T: pd.DataFrame, a: str = "entry1_time", b: str = "exit_time"):
    """(entry, exit) of trades, or None."""
    return (T[a], T[b]) if {a, b} <= set(T.columns) and len(T) else None


def port_comp(name: str, a, b, stat: str, E_: float, env, kind: str = "crypto", block_days=None,
              months=(1, 3, 12)) -> dict:
    """A portfolio-level component (bb_stats.portfolio_test: paired stationary block bootstrap, 10,000 draws;
    verdict p and NO EDGE bound = the larger of the 1- and 3-month blocks, or the given block length)."""
    r = bs.portfolio_test(a, b, stat=stat, kind=kind, months=months, B=env.B_port, seed=bs.SEED,
                          level=float(env.level_noedge), block_days=block_days)
    by = {}
    T = None
    ruin = False
    for k, v in r["by_block"].items():
        by[str(round(float(k), 4))] = {"p": _f(v["p"]), "estimate": _f(v["estimate"]), "se": _f(v["se"]),
                                       "ub_noedge": _f(v["ub"]), "ub95": _f(v["ub95"]),
                                       "ci95": [_f(c) for c in v["ci95"]], "mean_block": _f(v["mean_block"])}
        T = int(v["T"])
        ruin = ruin or bool(v.get("ruin", False))
    return {"name": name, "kind": "portfolio", "stat": stat, "T": T, "estimate": _f(r["estimate"]),
            "se": _f(r["se"]), "p": _f(r["p"]), "ci95": [_f(c) for c in r["ci95"]], "ub95": _f(r["ub95"]),
            "ub_noedge": _f(r["ub"]), "level_noedge": float(env.level_noedge), "E": float(E_),
            "mde": _f(bs.mde(r["se"])), "by_block": by, "ruin": ruin,
            "block_unit": "days" if kind == "crypto" else "sessions"}


def ols_boot_t(y, d, clusters, levels=(0.95, bs.LEVEL_NOEDGE), B: int = bs.B_TRADE, seed: int = bs.SEED,
               chunk: int = 1000, return_draws: bool = False) -> dict:
    """Month-cluster bootstrap-t of the coefficient on a binary regressor d in y = b0 + b1 d (H5): clusters
    resampled with replacement (a duplicated cluster counts as distinct), b1* and its CR1 SE (factor G/(G-1), as
    bb_stats.cluster_ols) recomputed on each draw from per-cluster sums, t* = (b1* - b1) / se*, UB(level) = b1 -
    q_{1-level}(t*) se, interval [b1 - q_.975 se, b1 - q_.025 se]. Draws without both groups are dropped."""
    y = np.asarray(y, float)
    d = np.asarray(d, float)
    g = np.asarray(clusters)
    k = np.isfinite(y) & np.isfinite(d)
    y, d, g = y[k], d[k], g[k]
    if not len(y) or not set(np.unique(d)) <= {0.0, 1.0}:
        raise ValueError("ols_boot_t needs a binary regressor")
    beta, se, _, _, _ = bs.cluster_ols(y, d, g)
    b1, s1 = float(beta[1]), float(se[1])
    _, inv = np.unique(g, return_inverse=True)
    G = int(inv.max()) + 1
    n_c = np.bincount(inv, minlength=G).astype(float)
    n1_c = np.bincount(inv, weights=d, minlength=G)
    sy_c = np.bincount(inv, weights=y, minlength=G)
    sy1_c = np.bincount(inv, weights=y * d, minlength=G)
    out = {"estimate": b1, "se": s1, "G": G, "ub": {lv: np.nan for lv in levels}, "ci": (np.nan, np.nan),
           "B_valid": 0}
    if G < 2 or not np.isfinite(s1) or s1 <= 0:
        return out
    rng = np.random.default_rng(seed)
    f = G / (G - 1)
    tb = []
    for k0 in range(0, B, chunk):
        nb = min(chunk, B - k0)
        idx = rng.integers(0, G, size=(nb, G))
        w = np.zeros((nb, G))
        np.add.at(w, (np.repeat(np.arange(nb), G), idx.ravel()), 1.0)
        N, N1, SY, SY1 = w @ n_c, w @ n1_c, w @ sy_c, w @ sy1_c
        N0 = N - N1
        with np.errstate(divide="ignore", invalid="ignore"):
            b0 = (SY - SY1) / N0
            bb1 = SY1 / N1 - b0
            s0c = sy_c[None, :] - b0[:, None] * n_c[None, :] - bb1[:, None] * n1_c[None, :]
            s1c = sy1_c[None, :] - (b0 + bb1)[:, None] * n1_c[None, :]
            m00 = (w * s0c * s0c).sum(1)
            m01 = (w * s0c * s1c).sum(1)
            m11 = (w * s1c * s1c).sum(1)
            det = N * N1 - N1 * N1
            # inverse of [[N, N1], [N1, N1]] = [[N1, -N1], [-N1, N]] / det; V11 = f * (A M A')_{11}
            a10, a11 = -N1 / det, N / det
            v11 = f * (a10 * a10 * m00 + 2 * a10 * a11 * m01 + a11 * a11 * m11)
            t_ = (bb1 - b1) / np.sqrt(v11)
        ok = (N1 > 0) & (N0 > 0) & np.isfinite(t_)
        tb.append(t_[ok])
    tb = np.concatenate(tb) if tb else np.zeros(0)
    if not len(tb):
        return out
    q = lambda p_: float(np.quantile(tb, p_, method="weibull"))       # noqa: E731
    out["ub"] = {lv: b1 - q(1 - lv) * s1 for lv in levels}
    out["ci"] = (b1 - q(0.975) * s1, b1 - q(0.025) * s1)
    out["B_valid"] = int(len(tb))
    if return_draws:
        out["t_star"] = tb
    return out


def _result(test_id: str, comps: list, gates: dict, halves: dict, flags: dict | None = None,
            force_inconclusive: bool = False, extra: dict | None = None) -> dict:
    """A test's JSON-able record. p_one_sided = the intersection-union max of the components' one-sided p (NaN
    counts 1); the estimate, SE, intervals and MDE are those of the deciding component (the larger p)."""
    ps = [c["p"] for c in comps]
    p = bs.iu_p(ps)
    dec = comps[int(np.argmax([x if np.isfinite(x) else 1.0 for x in ps]))]
    gates = {k: bool(v) for k, v in gates.items()}
    halves_ok = all(_gt0(v) for comp in halves.values() for v in comp.values()) if halves else True
    return {"test_id": test_id, "name": NAMES[test_id], "components": comps,
            "p_components": {c["name"]: c["p"] for c in comps}, "p_one_sided": float(p), "deciding": dec["name"],
            "estimate": dec["estimate"], "estimate_unadjusted": dec.get("estimate_unadjusted"),
            "se": dec["se"], "ci95": dec["ci95"], "ub95": dec.get("ub95"),
            "ub_noedge": [c["ub_noedge"] for c in comps], "E": [c["E"] for c in comps], "mde": dec["mde"],
            "gates": gates, "gates_ok": all(gates.values()), "halves": halves, "halves_ok": bool(halves_ok),
            "conds_ok": bool(all(gates.values()) and halves_ok), "force_inconclusive": bool(force_inconclusive),
            "flags": flags or {}, "extra": extra or {}}


# ============================================================================ data sources
class Env:
    """Data sources of the tests. Defaults read the data on disk through bb_data / bb_engine / bb_bench / bb_grid /
    bb_stocks. Injection (self-test): hours = {sym: coin_hours-shaped frame}, minutes = {sym: 1-minute frame},
    primary / others / pre_coins = coin lists, s12 = {sym: entry_allowed mask} (H1's S12 gate universe), stocks =
    {"members": {name: frame}, "etfs": {name: frame}}, cfg_tweak = fields replaced in every ROWS entry (e.g. a
    zero-fee null), mmr = maintenance margin for synthetic symbols, seeds = HS1's further seeds."""

    def __init__(self, hours: dict | None = None, minutes: dict | None = None, primary=None, others=None,
                 s12: dict | None = None, pre_coins=None, stocks: dict | None = None, cfg_tweak: dict | None = None,
                 level_noedge: float = bs.LEVEL_NOEDGE, level95: float = 0.95, B_trade: int = bs.B_TRADE,
                 B_port: int = bs.B_PORT, mmr: float | None = None, seeds=None):
        self.hours = hours
        self.minutes = minutes
        self.primary = list(primary) if primary is not None else list(bd.PRIMARY)
        self.others = list(others) if others is not None else [c for c in bd.COINS if c not in bd.PRIMARY]
        self._s12 = s12
        self._pre = list(pre_coins) if pre_coins is not None else None
        self.stocks = stocks
        self.cfg_tweak = dict(cfg_tweak or {})
        self.level_noedge = float(level_noedge)
        self.level95 = float(level95)
        self.B_trade = int(B_trade)
        self.B_port = int(B_port)
        self.mmr = mmr
        if seeds is None:
            from analysis_2026.bb_stocks import SEEDS_FURTHER
            seeds = SEEDS_FURTHER
        self.seeds = tuple(seeds)
        self._ret: dict = {}
        self._memo: dict = {}
        self._frames: dict = {}
        self._s12_cache = None
        self.audit = {"engine_runs": 0, "grid_runs": 0, "stock_runs": 0, "violations": 0}

    def __getstate__(self):                          # pool workers receive a fresh cache
        st = dict(self.__dict__)
        st["_memo"], st["_ret"], st["_frames"] = {}, {}, {}
        return st

    # ---------------------------------------------------------------- rows
    def row(self, name: str) -> be.Cfg:
        c = be.ROWS[name]
        return replace(c, **self.cfg_tweak) if self.cfg_tweak else c

    # ---------------------------------------------------------------- frames
    def _hours(self, sym: str, vehicle: str = "perp"):
        key = (sym, vehicle)
        if key in self._frames:
            return self._frames[key]
        if vehicle == "perp":
            h = None if self.hours is None else self.hours[sym]
        else:
            from analysis_2026.bb_bench import spot_hours
            base = bd.coin_hours(sym) if self.hours is None else self.hours[sym]
            h = spot_hours(base)
        self._frames[key] = h
        return h

    def coin_frame(self, sym: str) -> pd.DataFrame:
        return bd.coin_hours(sym) if self.hours is None else self.hours[sym]

    def returns(self, sym: str, vehicle: str = "perp") -> pd.Series:
        key = (sym, vehicle)
        if key not in self._ret:
            h = self._hours(sym, vehicle)
            self._ret[key] = bs.coin_returns(sym) if h is None else bs.returns_from_hours(h)
        return self._ret[key]

    def _check(self, audit, what: str):
        if audit:
            self.audit["violations"] += len(audit)
            raise RuntimeError(f"fill audit violated ({what}): {len(audit)} violations, e.g. {audit[0]}")

    # ---------------------------------------------------------------- engine
    def sim(self, sym: str, cfg: be.Cfg, start, end, allowed=None, memo: bool = True, vehicle: str = "perp") -> dict:
        """bb_engine.simulate_coin (detail=False) with the drift-adjusted return (bb_stats.drift_adjust on the
        coin's whole-history traded series) added as ret_adj; asserts an empty fill audit."""
        key = (sym, cfg, str(start), str(end), None if allowed is None else id(allowed), vehicle)
        if memo and key in self._memo:
            return self._memo[key]
        kw = {}
        h = self._hours(sym, vehicle)
        if h is not None:
            kw["hours"] = h
            if vehicle == "perp" and self.minutes is not None and sym in self.minutes:
                kw["minutes"] = self.minutes[sym]
        if self.mmr is not None:
            kw["mmr"] = self.mmr
        try:
            r = be.simulate_coin(sym, cfg, start, end, entry_allowed=allowed, detail=False, **kw)
        except ValueError as e:                    # a coin with no hour in the window holds no position
            if "empty window" not in str(e):
                raise
            out = {"sym": sym, "trades": pd.DataFrame(columns=["sym", "pos", "signal_day", "entry1_time", "exit_time",
                                                               "ret", "ret_adj", "drift", "expo_sum", "near_r0"]),
                   "daily_mtm": pd.DataFrame(columns=["pos", "time", "mtm", "margin", "notional", "sym"]),
                   "log": {"empty_window": True}}
            if memo:
                self._memo[key] = out
            return out
        self.audit["engine_runs"] += 1
        self._check(r["fills_audit"], f"{sym} {cfg} {start}..{end}")
        T = r["trades"].copy()
        if len(T):
            adj = bs.drift_adjust(T, r["expo"], {sym: self.returns(sym, vehicle)}, parts=True)
            T["ret_adj"] = adj["ret_adj"].to_numpy(float)
            T["drift"] = adj["drift"].to_numpy(float)
        else:
            T["ret_adj"] = pd.Series(dtype=float)
            T["drift"] = pd.Series(dtype=float)
        out = {"sym": sym, "trades": T, "daily_mtm": r["daily_mtm"], "log": r["log"]}
        if memo:
            self._memo[key] = out
        return out

    def sims(self, syms, cfg, start, end, allowed: dict | None = None, memo: bool = True,
             vehicle: str = "perp") -> dict:
        return {s: self.sim(s, cfg, start, end, None if allowed is None else allowed[s], memo, vehicle)
                for s in syms}

    def s12_gate(self) -> tuple:
        """H1's S12 gate universe: (coins, {sym: entry_allowed}) of bb_engine.H1_S12_GATE (crypto-only all-contract
        top 3, Addendum) unless injected."""
        if self._s12 is not None:
            return list(self._s12), dict(self._s12)
        if self._s12_cache is None:
            u = be.ROW_UNIVERSE[be.H1_S12_GATE]
            _, pool, k, tradfi = u
            coins = be.row_coins(be.H1_S12_GATE)
            self._s12_cache = (coins, {s: be.s12_allowed(s, k, pool, tradfi=tradfi) for s in coins})
        return self._s12_cache

    def pre_coins(self) -> list:
        """Coins with a live hour before 2020 (the pre-perpetual block: "every coin listed then")."""
        if self._pre is not None:
            return list(self._pre)
        out = []
        for s in list(dict.fromkeys(self.primary + list(bd.COINS))):
            h = self.coin_frame(s)
            m = (h.index < pd.Timestamp("2020-01-01", tz="UTC")) & (h["trades"].to_numpy() > 0)
            if m.any():
                out.append(s)
        self._pre = out
        return out

    def episodes(self, sym: str, start, end) -> pd.DataFrame:
        kw = {}
        h = self._hours(sym)
        if h is not None:
            kw["hours"] = h
            if self.minutes is not None and sym in self.minutes:
                kw["minutes"] = self.minutes[sym]
        return be.h4_episodes(sym, start, end, cfg=be.h4_touch_cfg(self.row("S1")), **kw)

    # ---------------------------------------------------------------- benchmarks
    def bh(self, syms, start, end, idle_tbill: bool = True, weights: str = "sleeve") -> pd.DataFrame:
        from analysis_2026.bb_bench import bh_crypto
        return bh_crypto(list(syms), start, end, idle_tbill=idle_tbill, hours=self.hours, weights=weights)

    def ml(self, syms, start, end, idle_tbill: bool = True, vehicle: str = "perp", k_slots=None) -> dict:
        from analysis_2026.bb_bench import moneyline_perp
        a = moneyline_perp(list(syms), start, end, k_slots=k_slots, idle_tbill=idle_tbill, vehicle=vehicle,
                           hours=self.hours)
        for s, r in a.get("coins", {}).items():
            self._check(r.get("fills_audit", []), f"moneyline {s}")
        return a

    def grid(self, sym: str, r0: dict, fee: str, start, end, fill: str = "through") -> dict:
        from analysis_2026.bb_grid import grid_ga
        kw = {"hours": self.coin_frame(sym)}
        if self.minutes is not None:
            kw["minutes"] = self.minutes[sym]
        ga = grid_ga(sym, r0["trades"], cfg_fees=fee, start=start, end=end, sleeve=1.0, fill=fill, mmr=self.mmr, **kw)
        self.audit["grid_runs"] += 1
        self._check(ga["fills_audit"], f"grid {sym} {fee} {fill}")
        return ga

    # ---------------------------------------------------------------- stocks
    def stock_run(self, which: str, start, end) -> dict:
        """bb_stocks.stock_trades (every signal) with ret_adj (bb_stats.drift_adjust on session_returns)."""
        from analysis_2026 import bb_stocks as bk
        ohlc = None if self.stocks is None else self.stocks[which]
        res = bk.stock_trades(which, bk.StockCfg(), start=start, end=end, ohlc=ohlc)
        self.audit["stock_runs"] += 1
        self._check(res["fills_audit"], f"stocks {which} {start}..{end}")
        T = res["trades"].copy()
        if len(T):
            adj = bs.drift_adjust(T, res["expo"], bk.session_returns(res["data"]), parts=True)
            T["ret_adj"] = adj["ret_adj"].to_numpy(float)
            T["drift"] = adj["drift"].to_numpy(float)
        else:
            T["ret_adj"] = pd.Series(dtype=float)
            T["drift"] = pd.Series(dtype=float)
        res = dict(res)
        res["trades"] = T
        return res

    def stock_bench(self, which: str, start, end) -> pd.DataFrame:
        from analysis_2026 import bb_stocks as bk
        data = None if self.stocks is None else self.stocks[which]
        if which == "members":
            return bk.benchmark_ew_members(start, end, data=data)
        return bk.benchmark_ew_etfs(start, end, data=data)


# ============================================================================ H1
def test_h1(env: Env):
    cfg = env.row("S1_L1")
    T = _cat(env.sims(env.primary, cfg, *FULL))
    To = _cat(env.sims(env.others, cfg, *FULL))
    coins, allowed = env.s12_gate()
    Ts = _cat({s: env.sim(s, cfg, *FULL, allowed=allowed[s]) for s in coins})
    pre = env.pre_coins()
    Tp = _cat(env.sims(pre, env.row("PRE_S1_L1"), *PRE_PERP, vehicle="spot"))
    res, det = h1_stats(T, To, Ts, Tp, env)
    res["extra"].update(other_coins=list(env.others), s12_coins=list(coins), pre_perp_coins=list(pre))
    for nm, pool in (("other37", env.others), ("s12_top3", coins), ("pre_perpetual", pre)):
        res["extra"][f"{nm}_ex_ZEC"]["zec_in_pool"] = "ZEC" in pool
    return res, det


def h1_stats(T, To, Ts, Tp, env):
    """H1 on S1-at-L=1 trades (BTC/ETH/SOL), the other 37 coins, the S12 gate universe and the pre-perpetual block
    (each pool also without ZEC, choice 17)."""
    mo = _months(T)
    x = T["ret_adj"].to_numpy(float) if len(T) else np.zeros(0)
    main = trade_comp("drift_adjusted_mean", x, mo, E["H1"], env, spans=_tspans(T),
                      unadj=T["ret"].to_numpy(float) if len(T) else None)
    unadj = _simple(T["ret"].to_numpy(float) if len(T) else [], mo)
    halves = _halves_trade(x, T["entry1_time"] if len(T) else [], HALVES_CRYPTO)
    oth = _simple(To["ret_adj"].to_numpy(float) if len(To) else [], _months(To))
    oth["n_coins_traded"] = int(To["sym"].nunique()) if len(To) else 0
    s12 = _simple(Ts["ret_adj"].to_numpy(float) if len(Ts) else [], _months(Ts))
    s12["n_coins_traded"] = int(Ts["sym"].nunique()) if len(Ts) else 0
    pre = _simple(Tp["ret_adj"].to_numpy(float) if len(Tp) else [], _months(Tp))
    pre["label"] = "exploratory (pre-perpetual block, Binance spot, not a pass condition)"
    gates = {"unadjusted_mean_gt0": _gt0(unadj["mean"]),
             "drift_adjusted_mean_gt0_both_halves": all(_gt0(v) for v in halves.values()),
             "other37_drift_adjusted_mean_gt0": _gt0(oth["mean"]),
             "s12_top3_drift_adjusted_mean_gt0": _gt0(s12["mean"])}
    mdm, mm = bs.drop_worst_month(x, mo) if len(x) else (np.nan, None)
    flags = {"month_dropped_mean": _f(mdm), "month_dropped": None if mm is None else int(mm),
             "top5_share": _f(bs.top_share(T["ret"].to_numpy(float))) if len(T) else np.nan,
             "top5_share_drift_adjusted": _f(bs.top_share(x)) if len(x) else np.nan,
             "n_ret_adj_nan": int((~np.isfinite(x)).sum())}
    extra = {"unadjusted": unadj, "other37": oth, "s12_top3": s12, "pre_perpetual": pre}
    for nm, F_ in (("other37", To), ("s12_top3", Ts), ("pre_perpetual", Tp)):
        sym = F_["sym"].astype(str).to_numpy() if len(F_) else np.zeros(0, str)
        X = F_[sym != "ZEC"] if len(F_) else F_
        s = _simple(X["ret_adj"].to_numpy(float) if len(X) else [], _months(X))
        s["n_coins_traded"] = int(X["sym"].nunique()) if len(X) else 0
        s["zec_trades_removed"] = int((sym == "ZEC").sum())
        s["label"] = "without ZEC, beside the pool with it (Reporting rules); the gate uses the pre-registered pool"
        extra[f"{nm}_ex_ZEC"] = s
    res = _result("H1", [main], gates, {"drift_adjusted_mean": halves}, flags, extra=extra)
    det = {"H1_trades": _cols(T), "H1_other37_trades": _cols(To), "H1_s12_trades": _cols(Ts),
           "H1_pre_perpetual_trades": _cols(Tp)}
    return res, det


# ============================================================================ H2
def test_h2(env: Env):
    cfg = env.row("S1_L1")
    K = len(env.primary)
    res = env.sims(env.primary, cfg, *FULL)
    acct = be.assemble(res, cfg, *FULL, idle_tbill=True, k_slots=K)
    acct0 = be.assemble(res, cfg, *FULL, idle_tbill=False, k_slots=K)
    bh = env.bh(env.primary, *FULL, idle_tbill=True)
    bh0 = env.bh(env.primary, *FULL, idle_tbill=False)
    bhj = env.bh(env.primary, *FULL, idle_tbill=True, weights="joined")
    ml = env.ml(env.primary, *FULL, idle_tbill=True)
    ml0 = env.ml(env.primary, *FULL, idle_tbill=False)
    # pre-perpetual block (exploratory): the coins of the three listed then, on Binance spot; unlisted sleeves cash
    pre = [s for s in env.primary if s in env.pre_coins()]
    pre_in = None
    if pre:
        rp = env.sims(pre, env.row("PRE_S1_L1"), *PRE_PERP, vehicle="spot")
        ap = be.assemble(rp, env.row("PRE_S1_L1"), *PRE_PERP, idle_tbill=True, k_slots=K)
        bp = env.bh(env.primary, *PRE_PERP, idle_tbill=True)
        mp = env.ml(pre, *PRE_PERP, idle_tbill=True, vehicle="spot", k_slots=K)
        pre_in = {"s1": ap["excess"], "bh": bp["excess"], "ml": mp["excess"], "coins": pre}
    r, det = h2_stats(acct["excess"], bh["excess"], ml["excess"],
                      raw={"s1": acct0["ret"], "bh": bh0["ret"], "ml": ml0["ret"]},
                      bh_joined=bhj["excess"], pre=pre_in, env=env)
    r["extra"].update(n_trades=int(len(acct["trades"])), exposure_avg=acct["exposure_avg"],
                      exposure_peak=acct["exposure_peak"], frozen_months=acct["frozen_months"])
    return r, det


def h2_stats(s1_ex: pd.Series, bh_ex: pd.Series, ml_ex: pd.Series, raw: dict | None = None,
             bh_joined: pd.Series | None = None, pre: dict | None = None, env=None):
    """H2: studentized Sharpe differences of daily excess returns vs buy-and-hold and vs moneyline_ref."""
    ca = port_comp("vs_buy_and_hold", s1_ex, bh_ex, "sharpe_diff", E["H2"], env)
    cb = port_comp("vs_moneyline", s1_ex, ml_ex, "sharpe_diff", E["H2"], env)
    fn = lambda a, b: _sharpe_diff_est(a, b, 365)     # noqa: E731
    halves = {"vs_buy_and_hold": _halves_series(fn, s1_ex, bh_ex, HALVES_CRYPTO),
              "vs_moneyline": _halves_series(fn, s1_ex, ml_ex, HALVES_CRYPTO)}
    extra = {}
    if raw is not None:
        for nm, b in (("vs_buy_and_hold", raw["bh"]), ("vs_moneyline", raw["ml"])):
            c = port_comp(nm + "_raw_0pct_cash", raw["s1"], b, "sharpe_diff", E["H2"], env)
            extra[nm + "_raw_0pct_cash"] = {k: c[k] for k in ("estimate", "se", "p", "ci95", "by_block")}
    if bh_joined is not None:
        c = port_comp("vs_buy_and_hold_joined_weights", s1_ex, bh_joined, "sharpe_diff", E["H2"], env)
        extra["vs_buy_and_hold_joined_weights"] = {k: c[k] for k in ("estimate", "se", "p", "ci95", "by_block")}
    if pre is not None:
        out = {"coins": pre["coins"], "label": "exploratory (pre-perpetual block, Binance spot)"}
        for nm, b in (("vs_buy_and_hold", pre["bh"]), ("vs_moneyline", pre["ml"])):
            c = port_comp(nm, pre["s1"], b, "sharpe_diff", E["H2"], env)
            out[nm] = {k: c[k] for k in ("estimate", "se", "p", "ci95")}
        extra["pre_perpetual"] = out
    res = _result("H2", [ca, cb], {}, halves, {}, extra=extra)
    daily = pd.concat([s1_ex.rename("s1_excess"), bh_ex.rename("bh_excess"), ml_ex.rename("ml_excess")], axis=1)
    if raw is not None:
        daily = daily.join(pd.concat([raw["s1"].rename("s1_raw"), raw["bh"].rename("bh_raw"),
                                      raw["ml"].rename("ml_raw")], axis=1), how="outer")
    return res, {"H2_daily": daily.reset_index(names="day")}


# ============================================================================ H3
def test_h3(env: Env):
    r0 = _cat(env.sims(env.primary, env.row("R0"), *FULL))
    s4 = _cat(env.sims(env.primary, env.row("S4"), *FULL))
    return h3_stats(r0, s4, env)


def h3_stats(r0: pd.DataFrame, s4: pd.DataFrame, env):
    """H3: per-signal paired R0 - S4 (drift-adjusted, per M) and the exposure-time unit (delta method); the
    unadjusted versions beside them."""
    d = _pair(s4, r0, key="signal_day")
    comp = trade_comp("per_signal_R0_minus_S4", d["diff"], d["month"], E["H3"], env, spans=_uspans(d),
                      unadj=d.get("diff_unadj"))
    den_a = r0["expo_sum"].to_numpy(float) / 24.0
    den_b = s4["expo_sum"].to_numpy(float) / 24.0
    ma, mb = _months(r0), _months(s4)
    dR, se, df = bs.ratio_diff_cluster(r0["ret_adj"].to_numpy(float), den_a, ma,
                                       s4["ret_adj"].to_numpy(float), den_b, mb)
    dRu = np.nan
    if "ret" in r0.columns and "ret" in s4.columns:
        dRu = bs.ratio_diff_cluster(r0["ret"].to_numpy(float), den_a, ma, s4["ret"].to_numpy(float), den_b, mb)[0]
    Ra = bs.ratio_cluster(r0["ret_adj"].to_numpy(float), den_a, ma)
    Rb = bs.ratio_cluster(s4["ret_adj"].to_numpy(float), den_b, mb)
    p_et = _f(stats.t.sf(dR / se, df)) if (df and np.isfinite(se) and se > 0) else np.nan
    m = comp["estimate"]
    disagree = bool(np.isfinite(m) and np.isfinite(dR) and m != 0 and dR != 0 and np.sign(m) != np.sign(dR))
    gates = {"exposure_time_R0_above_S4": _gt0(dR)}
    halves = {"per_signal_R0_minus_S4": _halves_month(d["diff"], d["month"], HALVES_CRYPTO)}
    extra = {"exposure_time": {"R_R0": _f(Ra[0]), "se_R0": _f(Ra[1]), "R_S4": _f(Rb[0]), "se_S4": _f(Rb[1]),
                               "diff": _f(dR), "se": _f(se), "df": int(df), "p_one_sided": p_et,
                               "diff_unadjusted": _f(dRu),
                               "unit": "drift-adjusted net P&L per M per (notional/M x day held)"},
             "units_disagree_in_sign": disagree, "n_signals": int(len(d)), "n_nan_signals": int(d.attrs.get("n_nan", 0)),
             "n_r0_only": int((d["in_var"] & ~d["in_base"]).sum()), "n_s4_only": int((d["in_base"] & ~d["in_var"]).sum())}
    res = _result("H3", [comp], gates, halves, {}, force_inconclusive=disagree, extra=extra)
    return res, {"H3_signals": d}


# ============================================================================ H4
def _key_episodes(T: pd.DataFrame, ep: pd.DataFrame, tag: str) -> pd.DataFrame:
    T = T.copy()
    if not len(T):
        T["episode"] = pd.Series(dtype=object)
        T["ep_start"] = pd.Series(dtype="datetime64[ns, UTC]")
        T["episode_own"] = pd.Series(dtype=bool)
        return T
    ids = be.assign_episodes(T, ep).to_numpy()
    eps = set(ep["ep"].astype(int).tolist()) if len(ep) else set()
    known = np.array([int(i) in eps for i in ids], bool)
    smap = dict(zip(ep["ep"].astype(int), pd.DatetimeIndex(ep["start"]))) if len(ep) else {}
    T["episode"] = np.where(known, ids.astype(str), np.char.add(f"{tag}_own_", T["pos"].astype(str).to_numpy(str)))
    et = pd.DatetimeIndex(T["entry1_time"])
    T["ep_start"] = pd.DatetimeIndex([smap[int(i)] if k else e for i, k, e in zip(ids, known, et)])
    T["episode_own"] = ~known
    return T


def test_h4(env: Env):
    cfg_c = env.row("S1")
    cfg_t = be.h4_touch_cfg(cfg_c)
    rc, rt, eps = [], [], []
    for s in env.primary:
        ep = env.episodes(s, *FULL)
        rc.append(_key_episodes(env.sim(s, cfg_c, *FULL)["trades"], ep, "close"))
        rt.append(_key_episodes(env.sim(s, cfg_t, *FULL)["trades"], ep, "touch"))
        eps.append(ep.assign(sym=s))
    Tc = pd.concat([x for x in rc if len(x)] or rc[:1], ignore_index=True)
    Tt = pd.concat([x for x in rt if len(x)] or rt[:1], ignore_index=True)
    EP = pd.concat([x for x in eps if len(x)] or eps[:1], ignore_index=True)
    return h4_stats(Tc, Tt, EP, env)


def h4_stats(Tc: pd.DataFrame, Tt: pd.DataFrame, episodes: pd.DataFrame, env):
    """H4: per-episode S1 - touch (sum of drift-adjusted ret per M of each arm's trades in the episode)."""
    d = _pair(Tt, Tc, key=["sym", "episode"], time_col="ep_start")
    comp = trade_comp("per_episode_S1_minus_touch", d["diff"], d["month"], E["H4"], env, spans=_uspans(d),
                      unadj=d.get("diff_unadj"))
    halves = {"per_episode_S1_minus_touch": _halves_month(d["diff"], d["month"], HALVES_CRYPTO)}
    n_ep = int(len(episodes))
    used = set(zip(d["sym"].astype(str), d["episode"].astype(str)))
    eps_keys = set(zip(episodes["sym"].astype(str), episodes["ep"].astype(int).astype(str))) if n_ep else set()
    extra = {"n_episodes": n_ep, "n_paired_units": int(len(d)), "n_episodes_without_trades": len(eps_keys - used),
             "n_touch_only": int((d["in_base"] & ~d["in_var"]).sum()), "n_s1_only": int((d["in_var"] & ~d["in_base"]).sum()),
             "n_s1_trades_outside_episodes": int(Tc["episode_own"].sum()) if len(Tc) else 0,
             "n_touch_trades_outside_episodes": int(Tt["episode_own"].sum()) if len(Tt) else 0,
             "n_nan_units": int(d.attrs.get("n_nan", 0))}
    res = _result("H4", [comp], {}, halves, {}, extra=extra)
    return res, {"H4_episodes": d, "H4_close_trades": _cols(Tc), "H4_touch_trades": _cols(Tt)}


# ============================================================================ H5
def test_h5(env: Env):
    off = _cat(env.sims(env.primary, replace(env.row("S1"), near_high="off"), *FULL))
    on = _cat(env.sims(env.primary, env.row("S1"), *FULL))
    return h5_stats(off, on, env)


def h5_stats(off: pd.DataFrame, on: pd.DataFrame, env):
    """H5: OLS of drift-adjusted ret on [1, near-high] within S1 near_high="off" (month-clustered)."""
    y = off["ret_adj"].to_numpy(float)
    dd = off["near_r0"].to_numpy(bool).astype(float)
    g = _months(off)
    beta, se, t, p, df = bs.cluster_ols(y, dd, g)
    b1, s1, t1, p1 = _f(beta[1]), _f(se[1]), _f(t[1]), _f(p[1])
    lv = tuple(sorted({0.95, float(env.level95), float(env.level_noedge)}))
    try:
        bb = ols_boot_t(y, dd, g, levels=lv, B=env.B_trade)
    except ValueError:
        bb = {"ub": {k: np.nan for k in lv}, "ci": (np.nan, np.nan), "B_valid": 0}
    q = stats.t.ppf(0.975, df) if df else np.nan
    k = np.isfinite(y)
    comp = {"name": "near_high_coefficient", "kind": "trade_ols", "n": int(k.sum()),
            "G": int(len(np.unique(g[k]))) if k.any() else 0, "estimate": b1, "se": s1, "t": t1, "p": p1,
            "df": int(df), "ci95": [b1 - q * s1, b1 + q * s1], "ci95_boot": [_f(v) for v in bb["ci"]],
            "ub95_nominal": _f(bb["ub"][0.95]), "ub95": _f(bb["ub"][float(env.level95)]),
            "ub_noedge": _f(bb["ub"][float(env.level_noedge)]), "level95": float(env.level95),
            "level_noedge": float(env.level_noedge), "E": float(E["H5"]), "mde": _f(bs.mde(s1)),
            "intercept": _f(beta[0]), "boot_valid_draws": int(bb.get("B_valid", 0))}
    if len(off):                                  # sensitivity clusters (choice 16)
        comp["p_quarter_clusters"] = _f(bs.cluster_ols(y, dd, _quarter(g))[3][1])
        sp = _tspans(off)
        if sp is not None:
            ep = bs.overlap_episodes(*sp)
            comp["p_overlap_episode_clusters"] = _f(bs.cluster_ols(y, dd, ep)[3][1])
            comp["G_overlap_episodes"] = int(len(np.unique(ep[k]))) if k.any() else 0
    if "ret" in off.columns:                      # the unadjusted coefficient beside it (choice 15)
        bu, su, tu, pu, dfu = bs.cluster_ols(off["ret"].to_numpy(float), dd, g)
        comp["unadjusted"] = {"estimate": _f(bu[1]), "se": _f(su[1]), "t": _f(tu[1]), "p": _f(pu[1]), "df": int(dfu),
                              "intercept": _f(bu[0])}
        comp["estimate_unadjusted"] = _f(bu[1])
    halves = {}
    hv = {}
    for lab, (a, b_) in HALVES_CRYPTO.items():
        m = _in(off["entry1_time"], a, b_) if len(off) else np.zeros(0, bool)
        hv[lab] = _f(bs.cluster_ols(y[m], dd[m], g[m])[0][1]) if m.sum() >= 2 else np.nan
    halves["near_high_coefficient"] = hv
    near = dd == 1
    extra = {"n_near": int((near & k).sum()), "n_not_near": int((~near & k).sum()),
             "total_ret_adj_filter_off": _f(np.nansum(y)),
             "total_ret_adj_filter_on_S1": _f(np.nansum(on["ret_adj"].to_numpy(float))) if len(on) else 0.0,
             "total_ret_adj_off_near": _f(np.nansum(y[near])), "total_ret_adj_off_not_near": _f(np.nansum(y[~near])),
             "n_trades_filter_off": int(len(off)), "n_trades_filter_on": int(len(on))}
    res = _result("H5", [comp], {}, halves, {}, extra=extra)
    return res, {"H5_trades": _cols(off)}


# ============================================================================ H6
def h6_delays(start=FULL[0], end=FULL[1]) -> tuple:
    """(entry_delay, exit_delay) by New York hour 0..23: hours from each UTC day's 00:00 close to the first hour at
    or after it whose New York hour is h (bb_engine choice 4), averaged over every UTC day of the window."""
    days = pd.date_range(pd.Timestamp(start, tz="UTC").floor("D"), _hi(end).floor("D").tz_localize("UTC"),
                         freq="D").as_unit("ns")
    hrs = pd.date_range(days[0], days[-1] + pd.Timedelta("3D"), freq="h").as_unit("ns")
    nyh = bd.ny_clock(hrs)["ny_hour"].to_numpy()
    t = hrs.asi8
    dv = days.asi8
    out = np.zeros(24)
    for h in range(24):
        th = t[nyh == h]
        j = np.searchsorted(th, dv, side="left")
        out[h] = float(((th[j] - dv) / 3.6e12).mean())
    return out.copy(), out.copy()


def test_h6(env: Env):
    base_cfg = env.row("S1")
    base = _cat(env.sims(env.primary, base_cfg, *FULL))
    diffs = {}
    for e in range(24):
        for x in range(24):
            var = _cat(env.sims(env.primary, be.h6_cfg(e, x, base_cfg), *FULL, memo=False))
            diffs[(e, x)] = _pair(base, var, key="signal_day")
    s1w = _cat(env.sims(env.primary, env.row("S1W"), *FULL))
    d_w = _pair(base, s1w, key="signal_day")
    return h6_stats(diffs, h6_delays(*FULL), env, s1w_diff=d_w)


def _mean_finite(d: pd.DataFrame, col: str) -> float:
    if col not in d.columns:
        return np.nan
    v = d[col].to_numpy(float)
    v = v[np.isfinite(v)]
    return float(v.mean()) if len(v) else np.nan


def _p_exploratory(tab: pd.DataFrame) -> pd.DataFrame:
    """A descriptive table's per-row p: labelled exploratory, Benjamini-Hochberg adjusted within the table (choice 8)."""
    tab = tab.rename(columns={"p_one_sided": "p_one_sided_exploratory"})
    tab["p_bh_exploratory"] = bs.bh(tab["p_one_sided_exploratory"].to_numpy(float))
    return tab


def h6_stats(diffs: dict, delays: tuple, env, s1w_diff: pd.DataFrame | None = None):
    """H6: R0's pair's paired difference vs S1, its raw and residual rank among the 576 pairs."""
    de, dx = np.asarray(delays[0], float), np.asarray(delays[1], float)
    rows = []
    for (e, x), d in diffs.items():
        s = _simple(d["diff"], d["month"])
        rows.append({"entry_ny_hour": e, "exit_ny_hour": x, "n_signals": s["n"], "mean": s["mean"], "se": s["se"],
                     "p_one_sided": s["p"], "mean_unadjusted": _mean_finite(d, "diff_unadj"),
                     "entry_delay_h": de[e], "exit_delay_h": dx[x]})
    tab = _p_exploratory(pd.DataFrame(rows).sort_values(["entry_ny_hour", "exit_ny_hour"]).reset_index(drop=True))
    y = tab["mean"].to_numpy(float)
    X = np.column_stack([np.ones(len(tab)), tab.entry_delay_h, tab.entry_delay_h ** 2, tab.exit_delay_h,
                         tab.exit_delay_h ** 2])
    ok = np.isfinite(y)
    beta = np.linalg.lstsq(X[ok], y[ok], rcond=None)[0] if ok.sum() >= X.shape[1] else np.full(X.shape[1], np.nan)
    tab["fitted"] = X @ beta
    tab["residual"] = y - tab["fitted"].to_numpy()
    tab["rank_raw"] = _rank_desc(y)
    tab["rank_residual"] = _rank_desc(tab["residual"].to_numpy(float))
    tab["is_R0_pair"] = (tab.entry_ny_hour == H6_R0_PAIR[0]) & (tab.exit_ny_hour == H6_R0_PAIR[1])
    r0 = tab[tab.is_R0_pair].iloc[0]
    d0 = diffs[H6_R0_PAIR]
    comp = trade_comp("per_signal_R0pair_minus_S1", d0["diff"], d0["month"], E["H6"], env, spans=_uspans(d0),
                      unadj=d0.get("diff_unadj"))
    gates = {"rank_raw_top5pct": int(r0.rank_raw) <= H6_TOP, "rank_residual_top5pct": int(r0.rank_residual) <= H6_TOP}
    halves = {"per_signal_R0pair_minus_S1": _halves_month(d0["diff"], d0["month"], HALVES_CRYPTO)}
    extra = {"rank_raw": int(r0.rank_raw), "rank_residual": int(r0.rank_residual), "n_pairs": int(len(tab)),
             "top_cut": H6_TOP, "delay_fit_beta": [_f(b) for b in beta],
             "R0_pair_entry_delay_h": _f(r0.entry_delay_h), "R0_pair_exit_delay_h": _f(r0.exit_delay_h)}
    if s1w_diff is not None:
        extra["S1W_minus_S1"] = _simple(s1w_diff["diff"], s1w_diff["month"])
        if "diff_unadj" in s1w_diff.columns:
            extra["S1W_minus_S1_unadjusted"] = _simple(s1w_diff["diff_unadj"], s1w_diff["month"])
    res = _result("H6", [comp], gates, halves, {}, extra=extra)
    return res, {"H6_pairs576": tab, "H6_R0pair_signals": d0}


# ============================================================================ H7
def test_h7(env: Env):
    base_cfg = env.row("S1W")
    base = _cat(env.sims(env.primary, base_cfg, *FULL))
    diffs = {blk: _pair(base, _cat(env.sims(env.primary, be.h7_cfg(blk, base_cfg), *FULL)), key="signal_day")
             for blk in PAIRS7}
    return h7_stats(diffs, env)


def _placebo_table(diffs: dict, label: str) -> pd.DataFrame:
    rows = []
    for k, d in diffs.items():
        s = _simple(d["diff"], d["month"])
        rows.append({label: f"{k[0]}-{k[1]}", "days": list(k), "n_signals": s["n"], "mean": s["mean"], "se": s["se"],
                     "p_one_sided": s["p"], "mean_unadjusted": _mean_finite(d, "diff_unadj")})
    tab = _p_exploratory(pd.DataFrame(rows))
    tab["rank"] = _rank_desc(tab["mean"].to_numpy(float))
    return tab


def h7_stats(diffs: dict, env):
    """H7: rule 12 (Fri, Sat New York) vs S1W per signal; its rank among the 7 consecutive-day-pair blocks."""
    tab = _placebo_table(diffs, "block_ny_weekdays")
    d0 = diffs[H7_RULE]
    comp = trade_comp("per_signal_rule12_minus_S1W", d0["diff"], d0["month"], E["H7"], env, spans=_uspans(d0),
                      unadj=d0.get("diff_unadj"))
    rk = int(tab.loc[[tuple(v) == H7_RULE for v in tab["days"]], "rank"].iloc[0])
    gates = {"rule12_ranks_first_of_7": rk == 1}
    halves = {"per_signal_rule12_minus_S1W": _halves_month(d0["diff"], d0["month"], HALVES_CRYPTO)}
    extra = {"rank": rk, "n_blocks": int(len(tab)), "skipped": int((d0["in_base"] & ~d0["in_var"]).sum())}
    res = _result("H7", [comp], gates, halves, {}, extra=extra)
    tab = tab.assign(days=tab["days"].astype(str))
    return res, {"H7_blocks": tab, "H7_signals": d0}


# ============================================================================ H8
def test_h8(env: Env):
    base_cfg = env.row("S1W")
    base = _cat(env.sims(env.primary, base_cfg, *FULL))
    pd_ = lambda c: _pair(base, _cat(env.sims(env.primary, c, *FULL)), key="signal_day")      # noqa: E731
    d_a = pd_(be.h8a_cfg(H8_MINHOLD, base_cfg))
    defer = {dd: pd_(be.h8b_cfg(dd, base_cfg)) for dd in PAIRS7}
    dose = {h: pd_(be.h8a_cfg(h, base_cfg)) for h in H8_DOSES}
    return h8_stats(d_a, defer, dose, env)


def h8_stats(d_a: pd.DataFrame, defer: dict, dose: dict, env):
    """H8: (a) 72 h minimum hold and (b) rule 15 (Sat, Sun bars), each vs S1W per signal; p = max(p_a, p_b); rank of
    Sat+Sun among the 7 consecutive-day-pair deferrals; the minimum-hold dose-response (exploratory)."""
    d_b = defer[H8_RULE15]
    ca = trade_comp("per_signal_minhold72_minus_S1W", d_a["diff"], d_a["month"], E["H8"], env, spans=_uspans(d_a),
                    unadj=d_a.get("diff_unadj"))
    cb = trade_comp("per_signal_rule15_minus_S1W", d_b["diff"], d_b["month"], E["H8"], env, spans=_uspans(d_b),
                    unadj=d_b.get("diff_unadj"))
    tab = _placebo_table(defer, "defer_utc_bar_weekdays")
    rk = int(tab.loc[[tuple(v) == H8_RULE15 for v in tab["days"]], "rank"].iloc[0])
    gates = {"rule15_ranks_first_of_7": rk == 1}
    halves = {"per_signal_minhold72_minus_S1W": _halves_month(d_a["diff"], d_a["month"], HALVES_CRYPTO),
              "per_signal_rule15_minus_S1W": _halves_month(d_b["diff"], d_b["month"], HALVES_CRYPTO)}
    drows = []
    for h, d in dose.items():
        s = _simple(d["diff"], d["month"])
        drows.append({"min_hold_h": h, "n_signals": s["n"], "mean": s["mean"], "se": s["se"], "p_one_sided": s["p"],
                      "mean_unadjusted": _mean_finite(d, "diff_unadj")})
    dtab = _p_exploratory(pd.DataFrame(drows))
    extra = {"rank": rk, "dose_response": dtab.to_dict(orient="records"),
             "n_signals_a": int(len(d_a)), "n_signals_b": int(len(d_b))}
    res = _result("H8", [ca, cb], gates, halves, {}, extra=extra)
    tab = tab.assign(days=tab["days"].astype(str))
    return res, {"H8_deferrals": tab, "H8_dose": dtab, "H8a_signals": d_a, "H8b_signals": d_b}


# ============================================================================ H9
def test_h9(env: Env):
    K = len(env.primary)
    accts = {}
    for L in (1, 2, 3, 4, 5):
        cfg = env.row("R0") if L == 3 else replace(env.row("R0"), L=float(L))
        res = env.sims(env.primary, cfg, *FULL)
        a = be.assemble(res, cfg, *FULL, idle_tbill=True, k_slots=K)
        a0 = be.assemble(res, cfg, *FULL, idle_tbill=False, k_slots=K)
        accts[L] = {"ret": a["ret"], "excess": a["excess"], "ret_zero_interest": a0["ret"], "equity": a["equity"],
                    "exposure_avg": a["exposure_avg"], "exposure_peak": a["exposure_peak"],
                    "liquidations": int(len(a["liquidations"])), "dead": bool(a["dead"]),
                    "n_trades": int(len(a["trades"])),
                    "l_capped": int(a["trades"]["l_capped"].sum()) if "l_capped" in a["trades"] else 0}
    bh = env.bh(env.primary, *FULL, idle_tbill=True)["ret"]
    return h9_stats(accts, bh, env)


def _growth(r: np.ndarray, ppy: int = 365) -> float:
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    if not len(r):
        return np.nan
    if (1 + r <= 0).any():
        return -np.inf
    return float(np.log1p(r).mean() * ppy)


def _vertex(Ls: np.ndarray, g: np.ndarray) -> np.ndarray:
    """Row-wise vertex of the least-squares quadratic of growth on L, clipped to [min L, max L] (NaN with -inf)."""
    g = np.atleast_2d(g)
    X = np.column_stack([np.ones(len(Ls)), Ls, Ls ** 2])
    P = np.linalg.pinv(X)                               # (3, nL)
    ok = np.isfinite(g).all(1)
    c = np.where(ok[:, None], np.where(np.isfinite(g), g, 0.0) @ P.T, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        v = np.where(c[:, 2] < 0, -c[:, 1] / (2 * c[:, 2]), np.nan)
    end = np.where((c[:, 0] + c[:, 1] * Ls[-1] + c[:, 2] * Ls[-1] ** 2) >=
                   (c[:, 0] + c[:, 1] * Ls[0] + c[:, 2] * Ls[0] ** 2), Ls[-1], Ls[0])
    v = np.where(np.isfinite(v), np.clip(v, Ls[0], Ls[-1]), end)
    return np.where(ok, v, np.nan)


def h9_stats(accts: dict, bh_ret: pd.Series | None, env):
    """H9: logdiff L3 - L1 (block bootstrap, ruin = -inf), growth by L, growth-optimal L (90% interval), m/s^2, exposure,
    liquidations, drawdowns; and the answer map's R0 (L = 3) vs 1x buy-and-hold log growth intervals."""
    comp = port_comp("logdiff_L3_minus_L1", accts[3]["ret"], accts[1]["ret"], "logdiff", E["H9"], env)
    halves = {"logdiff_L3_minus_L1": _halves_series(_logdiff_ann, accts[3]["ret"], accts[1]["ret"], HALVES_CRYPTO)}
    Ls = np.array(sorted(accts), float)
    R = pd.concat([accts[int(L)]["ret"].rename(int(L)) for L in Ls], axis=1, join="inner").dropna()
    gr = np.array([_growth(R[int(L)].to_numpy()) for L in Ls])
    lr = np.log1p(np.where(R.to_numpy() > -1, R.to_numpy(), np.nan))
    lr = np.where(R.to_numpy() <= -1, -np.inf, lr)
    T = len(R)
    rng = np.random.default_rng(bs.SEED)
    B = env.B_port
    am, vx = np.empty(B), np.empty(B)
    chunk = max(1, int(2_000_000 // max(T, 1)))
    for k0 in range(0, B, chunk):
        nb = min(chunk, B - k0)
        idx, _ = bs.sb_indices(T, MONTH_DAYS, nb, rng)
        with np.errstate(invalid="ignore"):
            G = lr[idx].mean(1) * 365                  # (nb, nL)
        am[k0:k0 + nb] = Ls[np.argmax(np.where(np.isfinite(G) | np.isneginf(G), G, -np.inf), axis=1)]
        vx[k0:k0 + nb] = _vertex(Ls, G)
    q = lambda v, p_: _f(np.nanquantile(v, p_)) if np.isfinite(v).any() else np.nan     # noqa: E731
    gopt = {"argmax_L": _f(Ls[int(np.argmax(np.where(np.isfinite(gr) | np.isneginf(gr), gr, -np.inf)))]),
            "argmax_L_90": [q(am, 0.05), q(am, 0.95)], "vertex_L": _f(_vertex(Ls, gr[None, :])[0]),
            "vertex_L_90": [q(vx, 0.05), q(vx, 0.95)], "B": B}
    x1 = accts[1]["excess"].to_numpy(float)
    x1 = x1[np.isfinite(x1)]
    m_s2 = _f(x1.mean() / x1.var()) if len(x1) > 1 and x1.var() > 0 else np.nan
    byL = []
    for L in Ls:
        a = accts[int(L)]
        byL.append({"L": int(L), "growth_log_per_year": _growth(a["ret"].to_numpy()),
                    "growth_log_per_year_zero_interest": _growth(a["ret_zero_interest"].to_numpy()),
                    "exposure_avg": _f(a["exposure_avg"]), "exposure_peak": _f(a["exposure_peak"]),
                    "liquidations": a["liquidations"], "dead": a["dead"], "worst_drawdown": _maxdd(a["equity"]),
                    "n_trades": a["n_trades"], "l_capped_trades": a.get("l_capped", 0)})
    extra = {"growth_optimal": gopt, "m_over_s2_L1_daily_excess": m_s2, "by_L": byL}
    if bh_ret is not None:
        extra["answer_full_strategy_vs_holding"] = beats_holding(accts[3]["ret"], bh_ret, env, 365, HALVES_CRYPTO,
                                                                 "R0 (L = 3) vs 1x equal-weight buy-and-hold")
    res = _result("H9", [comp], {}, halves, {}, extra=extra)
    daily = pd.concat([accts[int(L)]["ret"].rename(f"ret_L{int(L)}") for L in Ls], axis=1)
    return res, {"H9_by_L": pd.DataFrame(byL), "H9_daily": daily.reset_index(names="day")}


def beats_holding(a: pd.Series, b: pd.Series, env, ppy: int, halves: dict, label: str) -> dict:
    """The answer map's "full strategy beats holding": mean log growth difference with its 95% month-block bootstrap
    interval (bb_stats.block_boot logdiff, 1-month blocks), over the full sample and each half."""
    blk = MONTH_DAYS if ppy == 365 else bs.MONTH_SESSIONS
    out = {"label": label}
    spans = {"full": (a, b)}
    for lab, (x, y) in halves.items():
        spans[lab] = (_slice(a, x, y), _slice(b, x, y))
    ok = True
    for lab, (u, v) in spans.items():
        r = bs.block_boot(u, v, "logdiff", blk, B=env.B_port, seed=bs.SEED, ppy=ppy)
        ci = [_f(c) for c in r["ci95"]]
        out[lab] = {"estimate": _f(r["estimate"]), "ci95": ci}
        ok = ok and _gt0(ci[0])
    out["interval_above_zero_full_and_both_halves"] = bool(ok)
    return out


# ============================================================================ H10
def test_h10(env: Env):
    from analysis_2026.bb_grid import merge_ga
    K = len(env.primary)
    rets, deps, dollars, logs = {}, [], {}, {}
    for fee in FEES:
        cfg = replace(env.row("R0"), fees=fee)
        r0 = env.sims(env.primary, cfg, *H10_WIN)
        ga = {s: env.grid(s, r0[s], fee, *H10_WIN) for s in env.primary}
        merged = {s: merge_ga(r0[s], ga[s]) for s in env.primary}
        a_ga = be.assemble(merged, cfg, *H10_WIN, idle_tbill=True, k_slots=K)
        a_r0 = be.assemble(r0, cfg, *H10_WIN, idle_tbill=True, k_slots=K)
        rets[fee] = (a_ga["ret"], a_r0["ret"])
        if fee == "base":                          # zero-interest version (choice 10), reported only
            zero = (be.assemble(merged, cfg, *H10_WIN, idle_tbill=False, k_slots=K)["ret"],
                    be.assemble(r0, cfg, *H10_WIN, idle_tbill=False, k_slots=K)["ret"])
        for s in env.primary:
            if len(ga[s]["deployments"]):
                deps.append(ga[s]["deployments"].assign(fees_scenario=fee))
            logs[f"{fee}/{s}"] = {k: v for k, v in ga[s]["log"].items() if isinstance(v, (int, float, str, dict))}
        gt = a_ga["trades"]
        gm = gt["grid"].fillna(False).astype(bool) if "grid" in gt else np.zeros(len(gt), bool)
        dollars[fee] = {"grid_pnl_usd": _f(gt.loc[gm, "pnl_usd"].sum()), "r0_pnl_usd_with_grid": _f(gt.loc[~gm, "pnl_usd"].sum()),
                        "r0_pnl_usd_alone": _f(a_r0["trades"]["pnl_usd"].sum()) if len(a_r0["trades"]) else 0.0,
                        "equity_end_with_grid": _f(a_ga["equity"].iloc[-1]), "equity_end_alone": _f(a_r0["equity"].iloc[-1])}
    # optimistic touch fills (base fees), reported only
    cfg = env.row("R0")
    r0 = env.sims(env.primary, cfg, *H10_WIN)
    gt_ = {s: merge_ga(r0[s], env.grid(s, r0[s], "base", *H10_WIN, fill="touch")) for s in env.primary}
    a_t = be.assemble(gt_, cfg, *H10_WIN, idle_tbill=True, k_slots=K)
    D = pd.concat(deps, ignore_index=True) if deps else pd.DataFrame()
    res, det = h10_stats(rets, D, env, touch=(a_t["ret"], rets["base"][1]), zero_interest=zero)
    res["extra"].update(dollars=dollars, grid_logs=logs)
    return res, det


def h10_stats(rets: dict, deployments: pd.DataFrame, env, touch: tuple | None = None,
              zero_interest: tuple | None = None):
    """H10: mean daily account-return difference R0 + G-A minus R0 (block 28 days), fee scenario base decides; the
    zero-interest version (idle cash at 0% in both arms) and mean blocks of 1, 3 and 12 months reported (choice 10)."""
    a, b = rets["base"]
    comp = port_comp("mean_daily_diff_base_fees", a, b, "mean", E["H10"], env, block_days=H10_BLOCK)
    halves = {"mean_daily_diff_base_fees": _halves_series(_meandiff_ann, a, b, HALVES_H10)}
    extra = {}
    c = port_comp("mean_daily_diff_base_fees_months", a, b, "mean", E["H10"], env, months=(1, 3, 12))
    extra["blocks_1_3_12_months"] = {"label": "reported only; the H10 row's 28-day block decides",
                                     "by_block_months": {str(m): v for m, v in zip((1, 3, 12), c["by_block"].values())},
                                     "p_larger_of_1_3": c["p"]}
    if zero_interest is not None:
        c = port_comp("mean_daily_diff_base_fees_zero_interest", *zero_interest, "mean", E["H10"], env,
                      block_days=H10_BLOCK)
        extra["zero_interest"] = {"label": "idle cash and idle margin at 0% in both arms (reported only)",
                                  **{k: c[k] for k in ("estimate", "se", "p", "ci95", "ub_noedge")}}
    for fee in [f for f in rets if f != "base"]:
        c = port_comp(f"mean_daily_diff_{fee}_fees", *rets[fee], "mean", E["H10"], env, block_days=H10_BLOCK)
        extra[f"fees_{fee}"] = {k: c[k] for k in ("estimate", "se", "p", "ci95", "ub_noedge")}
    if touch is not None:
        c = port_comp("mean_daily_diff_touch_fills", *touch, "mean", E["H10"], env, block_days=H10_BLOCK)
        extra["touch_fills_optimistic"] = {k: c[k] for k in ("estimate", "se", "p", "ci95")}
    if len(deployments):
        g = deployments.groupby(["fees_scenario", "sym"])[["grid_profit", "inventory_pnl", "fees", "funding", "net"]].sum()
        g["n_deployments"] = deployments.groupby(["fees_scenario", "sym"]).size()
        g["n_liquidated"] = deployments.groupby(["fees_scenario", "sym"])["liquidated"].sum()
        extra["grid_by_coin_sleeve_units"] = {f"{i[0]}/{i[1]}": {k: _f(v) for k, v in r.items()}
                                              for i, r in g.iterrows()}
    res = _result("H10", [comp], {}, halves, {}, extra=extra)
    daily = pd.concat([a.rename("ret_r0_plus_ga"), b.rename("ret_r0")], axis=1)
    det = {"H10_daily": daily.reset_index(names="day")}
    if len(deployments):
        det["H10_deployments"] = deployments
    return res, det


# ============================================================================ HS1 / HS2
def test_hs1(env: Env):
    return test_hs(env, "HS1")


def test_hs2(env: Env):
    return test_hs(env, "HS2")


def test_hs(env: Env, tid: str):
    from analysis_2026 import bb_stocks as bk
    which, n_slots = ("members", 20) if tid == "HS1" else ("etfs", 14)
    res = env.stock_run(which, *STOCK_WIN)
    port = bk.portfolio(res, n_slots=n_slots, seed=bk.SEED, rank="random", idle_tbill=True)
    port0 = bk.portfolio(res, n_slots=n_slots, seed=bk.SEED, rank="random", idle_tbill=False)
    atr = bk.portfolio(res, n_slots=n_slots, seed=bk.SEED, rank="atr_dist", idle_tbill=True)
    bench = env.stock_bench(which, *STOCK_WIN)
    rnd = bk.random_entry_book(res, port, seed=bk.SEED, n_slots=n_slots, idle_tbill=True) if tid == "HS1" else None
    seeds = bk.portfolio_seeds(res, seeds=env.seeds, n_slots=n_slots, idle_tbill=True)
    early = None
    if tid == "HS1":
        r96 = env.stock_run(which, *EARLY_STOCK)
        p96 = bk.portfolio(r96, n_slots=n_slots, seed=bk.SEED, rank="random", idle_tbill=True)
        b96 = env.stock_bench(which, *EARLY_STOCK)
        early = {"trades": r96["trades"], "port_ex": p96["daily"]["excess"], "bench_ex": b96["excess"]}
    out, det = hs_stats(tid, res["trades"], port["daily"]["excess"], bench["excess"], env,
                        port_zero=port0["daily"]["ret"], bench_ret=bench["ret"], atr_ex=atr["daily"]["excess"],
                        rnd_ex=None if rnd is None else rnd["daily"]["excess"], seeds_ex=seeds, early=early,
                        port_ret=port["daily"]["ret"])
    out["extra"]["log"] = {k: v for k, v in res["log"].items() if isinstance(v, (int, float, str))}
    out["extra"]["n_slots"] = n_slots
    return out, det


def hs_stats(tid: str, T: pd.DataFrame, port_ex: pd.Series, bench_ex: pd.Series, env, port_zero=None,
             bench_ret=None, atr_ex=None, rnd_ex=None, seeds_ex: pd.DataFrame | None = None, early: dict | None = None,
             port_ret: pd.Series | None = None):
    """HS1 / HS2: p = max(p_trade, p_Sharpe); both > 0 in both halves; seeds, atr_dist, random-entry book, the
    zero-interest version and 1996-2000 reported."""
    mo = _months(T, "entry1_date") if len(T) else np.zeros(0, np.int64)
    x = T["ret_adj"].to_numpy(float) if len(T) else np.zeros(0)
    ct = trade_comp("trade_drift_adjusted_mean", x, mo, E["HS_trade"], env, spans=_tspans(T, "entry1_date", "exit_date"),
                    unadj=T["ret"].to_numpy(float) if len(T) else None)
    cs = port_comp("sharpe_vs_benchmark", port_ex, bench_ex, "sharpe_diff", E["HS_sharpe"], env, kind="stock")
    fn = lambda a, b: _sharpe_diff_est(a, b, 252)          # noqa: E731
    halves = {"trade_drift_adjusted_mean": _halves_trade(x, T["entry1_date"] if len(T) else [], HALVES_STOCK),
              "sharpe_vs_benchmark": _halves_series(fn, port_ex, bench_ex, HALVES_STOCK)}
    mdm, mm = bs.drop_worst_month(x, mo) if len(x) else (np.nan, None)
    flags = {"month_dropped_mean": _f(mdm), "month_dropped": None if mm is None else int(mm),
             "top5_share": _f(bs.top_share(T["ret"].to_numpy(float))) if len(T) else np.nan,
             "top5_share_drift_adjusted": _f(bs.top_share(x)) if len(x) else np.nan,
             "n_ret_adj_nan": int((~np.isfinite(x)).sum())}
    extra = {"unadjusted_trade_mean": _simple(T["ret"].to_numpy(float) if len(T) else [], mo)}
    pend = None
    if seeds_ex is not None and seeds_ex.shape[1]:
        est = {int(s): _sharpe_diff_est(seeds_ex[s], bench_ex, 252) for s in seeds_ex.columns}
        hv = {int(s): _halves_series(fn, seeds_ex[s], bench_ex, HALVES_STOCK) for s in seeds_ex.columns}
        ev = np.array(list(est.values()), float)
        flags["seeds"] = {"n": int(len(ev)), "estimate_median": _f(np.nanmedian(ev)),
                          "estimate_q05": _f(np.nanquantile(ev, 0.05)), "estimate_q95": _f(np.nanquantile(ev, 0.95)),
                          "halves_median": {lab: _f(np.nanmedian([hv[s][lab] for s in hv])) for lab in HALVES_STOCK},
                          "estimates": {str(k): v for k, v in est.items()}}
        if tid == "HS1":
            pend = {"bench_ex": bench_ex, "seeds_ex": seeds_ex}
        else:
            flags["seeds"]["rule"] = ("reported only: the seed rule is HS1's; with one slot per ETF the random order "
                                      "never rations")
            flags["seeds"]["invariant_to_seed"] = bool(np.nanmax(ev) - np.nanmin(ev) < 1e-12) if len(ev) else True
    for nm, s in (("atr_dist_ranking", atr_ex), ("random_entry_book", rnd_ex)):
        if s is not None:
            c = port_comp(nm, s, bench_ex, "sharpe_diff", E["HS_sharpe"], env, kind="stock")
            extra[nm + "_vs_benchmark"] = {k: c[k] for k in ("estimate", "se", "p", "ci95")}
    if rnd_ex is not None:
        c = port_comp("strategy_vs_random_entry_book", port_ex, rnd_ex, "sharpe_diff", E["HS_sharpe"], env, kind="stock")
        extra["strategy_vs_random_entry_book"] = {k: c[k] for k in ("estimate", "se", "p", "ci95")}
    if port_zero is not None and bench_ret is not None:
        c = port_comp("sharpe_zero_interest", port_zero, bench_ret, "sharpe_diff", E["HS_sharpe"], env, kind="stock")
        extra["zero_interest_raw_returns"] = {k: c[k] for k in ("estimate", "se", "p", "ci95")}
    if early is not None:
        Te = early["trades"]
        me = _months(Te, "entry1_date") if len(Te) else np.zeros(0, np.int64)
        se_ = _simple(Te["ret_adj"].to_numpy(float) if len(Te) else [], me)
        c = port_comp("sharpe_1996_2000", early["port_ex"], early["bench_ex"], "sharpe_diff", E["HS_sharpe"], env,
                      kind="stock")
        extra["block_1996_2000"] = {"label": "reported separately, outside every pass rule (about 80% coverage of "
                                             "member-days; 33% close-only rows)",
                                    "trade_drift_adjusted_mean": se_,
                                    "sharpe_vs_benchmark": {k: c[k] for k in ("estimate", "se", "p", "ci95")}}
    if port_ret is not None and bench_ret is not None:
        extra["answer_full_strategy_vs_holding"] = beats_holding(port_ret, bench_ret, env, 252, HALVES_STOCK,
                                                                 "1x portfolio vs equal-weight benchmark")
    res = _result(tid, [ct, cs], {}, halves, flags, extra=extra)
    det = {f"{tid}_trades": _cols(T, ["sym", "pos", "member", "signal_day", "entry1_date", "exit_date", "exit_reason",
                                      "n_tranches", "ret", "ret_adj", "drift", "hold_days", "open_at_end", "half"]),
           f"{tid}_daily": pd.concat([port_ex.rename("port_excess"), bench_ex.rename("bench_excess")],
                                     axis=1).reset_index(names="session")}
    if pend is not None:
        res["_pending_seeds"] = pend
    return res, det


def seed_jobs(res: dict, env) -> list:
    """HS1's 100 further seeds as block-bootstrap jobs (1- and 3-month blocks)."""
    pend = res.get("_pending_seeds")
    if not pend:
        return []
    b = pend["bench_ex"]
    out = []
    for s in pend["seeds_ex"].columns:
        a = pend["seeds_ex"][s]
        out.append((res["test_id"], int(s), a, b, env.B_port, env.level_noedge))
    return out


def _seed_job(job) -> dict:
    tid, seed, a, b, B, level = job
    r = bs.portfolio_test(a, b, stat="sharpe_diff", kind="stock", months=(1, 3), B=B, seed=bs.SEED, level=level)
    return {"test_id": tid, "seed": seed, "p": _f(r["p"]), "estimate": _f(r["estimate"])}


def seed_finalize(res: dict, outs: list) -> dict:
    """Fold the seeds' bootstrap p-values into HS1's flags (median p and estimate; 5-95%)."""
    res.pop("_pending_seeds", None)
    if not outs:
        return res
    p = np.array([o["p"] for o in outs], float)
    s = res["flags"].setdefault("seeds", {})
    s["p_median"] = _f(np.nanmedian(p))
    s["p_q05"] = _f(np.nanquantile(p, 0.05))
    s["p_q95"] = _f(np.nanquantile(p, 0.95))
    s["p"] = {str(o["seed"]): o["p"] for o in outs}
    s["rule"] = "primary seed passes and the median seed does not -> INCONCLUSIVE (applied in report)"
    return res


TEST_FUNCS = {"H1": test_h1, "H2": test_h2, "H3": test_h3, "H4": test_h4, "H5": test_h5, "H6": test_h6,
              "H7": test_h7, "H8": test_h8, "H9": test_h9, "H10": test_h10, "HS1": test_hs1, "HS2": test_hs2}
HEAVY_FIRST = ["HS1", "HS2", "H6", "H1", "H10", "H2", "H9", "H8", "H4", "H7", "H3", "H5"]


# ============================================================================ runner
_TASK_ENV: Env | None = None


def _task(tid: str):
    env = _TASK_ENV
    t0 = time.time()
    a0 = dict(env.audit)
    try:
        res, det = TEST_FUNCS[tid](env)
        err = None
    except Exception:                                  # noqa: BLE001 - recorded, re-raised after the run
        res, det, err = None, {}, traceback.format_exc()
    au = {k: env.audit[k] - a0.get(k, 0) for k in env.audit}
    return tid, res, det, au, round(time.time() - t0, 1), err


def _pool_map(fn, items, jobs: int):
    if jobs <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    import concurrent.futures as cf
    import multiprocessing as mp
    with cf.ProcessPoolExecutor(max_workers=min(jobs, len(items)), mp_context=mp.get_context("fork")) as ex:
        return list(ex.map(fn, items, chunksize=1))


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_jsonable(v) for v in o.tolist()]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return float(o)
    if isinstance(o, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(o))
    if isinstance(o, pd.Period):
        return str(o)
    if o is None or isinstance(o, (int, str)):
        return o
    return str(o)


def _csv_row(r: dict) -> dict:
    j = lambda v: json.dumps(_jsonable(v))                # noqa: E731
    fl = {k: v for k, v in r.get("flags", {}).items() if not isinstance(v, dict)}
    return {"test_id": r["test_id"], "name": r["name"], "p_components": j(r["p_components"]),
            "p_one_sided": r["p_one_sided"], "deciding": r["deciding"], "estimate": r["estimate"],
            "estimate_unadjusted": r.get("estimate_unadjusted"), "se": r["se"],
            "ci95": j(r["ci95"]), "ub95": r.get("ub95"), "ub_noedge": j(r["ub_noedge"]), "E": j(r["E"]),
            "mde": r["mde"], "gates": j(r["gates"]), "halves": j(r["halves"]), "conds_ok": r["conds_ok"],
            "force_inconclusive": r["force_inconclusive"], "flags": j(fl)}


def run(out_dir=RES, which=None, jobs: int = 4, level_noedge: float | None = None, level95: float | None = None,
        env: Env | None = None, say=print) -> dict:
    """Run the tests (default all 12) and write <out_dir>/primary/: tests.json (every number), tests.csv (one row per
    test) and the per-test detail CSVs. A test that raises (a fill audit violation included) is recorded with its
    traceback and the run raises after writing the others. which: a subset merges into an existing tests.json."""
    global _TASK_ENV
    out = Path(out_dir) / "primary"
    out.mkdir(parents=True, exist_ok=True)
    if env is None:
        env = Env(level_noedge=bs.LEVEL_NOEDGE if level_noedge is None else level_noedge,
                  level95=0.95 if level95 is None else level95)
    tests = list(TESTS if which is None else which)
    bad = [t for t in tests if t not in TEST_FUNCS]
    if bad:
        raise ValueError(f"unknown tests {bad}; choose from {TESTS}")
    order = [t for t in HEAVY_FIRST if t in tests]
    tj = out / "tests.json"
    prev = {}
    if which is not None and tj.exists():
        prev = json.loads(tj.read_text()).get("tests", {})
        probs = _level_problems({t: r for t, r in prev.items() if t not in tests}, env.level_noedge, env.level95,
                                ref="this run's")
        if probs:
            raise SystemExit(f"bb_tests run: refusing to merge {tests} into {tj}: " + " | ".join(probs) +
                             ". Re-run every test (no which=) so that one level covers the family")
    t0 = time.time()
    _TASK_ENV = env
    try:
        outs = _pool_map(_task, order, jobs)
        results, errors, timing, audits = {}, {}, {}, {}
        details = {}
        for tid, res, det, au, sec, err in outs:
            timing[tid] = sec
            audits[tid] = au
            if err:
                errors[tid] = err
                continue
            results[tid] = res
            details[tid] = det
        sj = [j for tid in results for j in seed_jobs(results[tid], env)]
        if sj:
            ts = time.time()
            so = _pool_map(_seed_job, sj, jobs)
            for tid in list(results):
                if results[tid].get("_pending_seeds") is not None:
                    seed_finalize(results[tid], [o for o in so if o["test_id"] == tid])
            timing["HS1_seeds"] = round(time.time() - ts, 1)
    finally:
        _TASK_ENV = None
    for tid, res in results.items():
        res.pop("_pending_seeds", None)
        res["fill_audit"] = audits.get(tid, {})
        res["seconds"] = timing.get(tid)
        files = []
        for name, df in details.get(tid, {}).items():
            if isinstance(df, pd.DataFrame):
                p = out / f"{name}.csv"
                df.to_csv(p, index=False)
                files.append(p.name)
        res["detail_files"] = files
    allr = dict(prev)
    allr.update(results)
    for tid, err in errors.items():
        allr[tid] = {"test_id": tid, "name": NAMES[tid], "error": err}
    meta = {"written": pd.Timestamp.now(tz="UTC").isoformat(), "level_noedge": env.level_noedge,
            "level95": env.level95, "B_trade": env.B_trade, "B_port": env.B_port, "n_seeds": len(env.seeds),
            "jobs": jobs, "seconds": round(time.time() - t0, 1), "timing": timing,
            "fill_audit_violations": int(sum(a.get("violations", 0) for a in audits.values())),
            "windows": {"full": FULL, "halves_crypto": HALVES_CRYPTO, "h10": H10_WIN, "halves_h10": HALVES_H10,
                        "stocks": STOCK_WIN, "halves_stocks": HALVES_STOCK, "pre_perpetual": PRE_PERP}}
    tj.write_text(json.dumps(_jsonable({"meta": meta, "tests": {t: allr[t] for t in TESTS if t in allr}}), indent=1))
    rows = [_csv_row(allr[t]) for t in TESTS if t in allr and "error" not in allr[t]]
    pd.DataFrame(rows).to_csv(out / "tests.csv", index=False)
    say(f"bb_tests: wrote {tj} ({len(results)} tests run, {len(errors)} errors) in {meta['seconds']} s; "
        f"engine runs {sum(a.get('engine_runs', 0) for a in audits.values())}, grid runs "
        f"{sum(a.get('grid_runs', 0) for a in audits.values())}, stock runs "
        f"{sum(a.get('stock_runs', 0) for a in audits.values())}, fill-audit violations "
        f"{meta['fill_audit_violations']}")
    if errors:
        raise RuntimeError("tests failed: " + "; ".join(f"{t}: {e.strip().splitlines()[-1]}" for t, e in errors.items()))
    return {"meta": meta, "tests": results}


# ============================================================================ report
def _levels(tests: dict, key: str) -> tuple:
    """({level: [test ids]} over the components that carry `key`, [test/component without it]) for tests without an
    error."""
    by, missing = {}, []
    for t, r in tests.items():
        if not isinstance(r, dict) or "error" in r:
            continue
        for c in r.get("components", []):
            v = c.get(key)
            if v is None or not np.isfinite(_f(v)):
                missing.append(f"{t}/{c.get('name')}")
                continue
            by.setdefault(round(float(v), 12), set()).add(t)
    return {k: sorted(v) for k, v in by.items()}, missing


def _level_problems(tests: dict, level_noedge=None, level95=None,
                    ref: str = "the controls' (controls/inference.json)") -> list:
    """Why the tests' bounds are not at one level (choice 1): every component must carry level_noedge, one value
    across the family, equal to the controls' level_noedge when given; level95 likewise where components carry it
    (trade-level and paired ones; portfolio components use block_boot's 95% bound)."""
    probs = []
    for key, want, required in (("level_noedge", level_noedge, True), ("level95", level95, False)):
        by, missing = _levels(tests, key)
        if required and missing:
            probs.append(f"components without {key}: {missing}")
        if len(by) > 1:
            probs.append(f"{key} differs across tests: " + "; ".join(f"{lv} {ts}" for lv, ts in sorted(by.items())))
        if want is not None and any(abs(lv - float(want)) > 1e-9 for lv in by):
            probs.append(f"{key} {sorted(by)} differs from {ref} {float(want)}")
    return probs


def _p_vec(tests: dict) -> np.ndarray:
    return np.array([_f(tests[t]["p_one_sided"]) for t in TESTS], float)


def _holm_with(tests: dict, tid: str, p_new: float) -> float:
    p = _p_vec(tests)
    p[TESTS.index(tid)] = p_new
    return float(bs.holm(p)[TESTS.index(tid)])


def _failed(r: dict) -> list:
    out = [f"gate {k}" for k, v in r["gates"].items() if not v]
    for comp, hv in r["halves"].items():
        for lab, v in hv.items():
            if not _gt0(v):
                out.append(f"half {lab} of {comp} not > 0")
    return out


def _median_seed_passes(tests: dict) -> tuple:
    r = tests["HS1"]
    s = r.get("flags", {}).get("seeds", {})
    pm = _f(s.get("p_median"))
    if not np.isfinite(pm):
        return False, "median seed p unavailable"
    p_trade = _f(r["p_components"].get("trade_drift_adjusted_mean"))
    ph = _holm_with(tests, "HS1", bs.iu_p([p_trade, pm]))
    hm = s.get("halves_median", {})
    halves_ok = all(_gt0(v) for v in hm.values()) and bool(hm)
    trade_ok = r["gates_ok"] and all(_gt0(v) for v in r["halves"].get("trade_drift_adjusted_mean", {}).values())
    ok = ph < bs.ALPHA and halves_ok and trade_ok
    return ok, f"median seed: Holm p {ph:.4g}, Sharpe halves median {hm}"


def _component_passes(tests: dict, tid: str, comp: str) -> tuple:
    r = tests[tid]
    p = _f(r["p_components"].get(comp))
    ph = _holm_with(tests, tid, p)
    hv = r["halves"].get(comp, {})
    ok = ph < bs.ALPHA and all(_gt0(v) for v in hv.values()) and r["gates_ok"]
    return bool(ok), ph


def _routes_trade(out: Path) -> list:
    """TRADE gate rows from results_bb/routes/*.csv (bb_desc's bb_bench.routes output), with placebo rates."""
    rows = []
    d = out / "routes"
    if not d.exists():
        return rows
    for f in sorted(d.glob("*.csv")):
        try:
            g = pd.read_csv(f)
        except Exception:                              # noqa: BLE001
            continue
        if "verdict" not in g.columns or "route" not in g.columns:
            continue
        sel = g[g["verdict"].astype(str) == "TRADE"]
        for _, x in sel.iterrows():
            rows.append({"file": f.name, "route": x.get("route"), "row": x.get("row"), "asset": x.get("sym", x.get("group")),
                         "basis": x.get("basis"),
                         "expected_false_pass": x.get("placebo_trade_p", x.get("expected_false_TRADE"))})
    return rows


def _sentence(tid: str, label: str) -> str:
    """The answer map's sentence for a group's test, from its reporting label ("PASS, carried by one month" kept)."""
    g = GROUP.get(tid)
    if label.startswith("PASS"):
        return f"{g}: an edge is shown ({tid} {label})"
    if label.startswith("NO EDGE"):
        return f"{g}: it does not work ({tid} {label})"
    return f"{g}: not shown - the data cannot tell ({tid} {label})"


def report(out_dir=RES, say=print, level_noedge: float | None = None, level95: float | None = None) -> pd.DataFrame:
    """Holm across the 12 one-sided p-values (whatever their other conditions), every gate and the both-halves rule,
    verdicts (bb_stats.verdict with each test's E and its NO EDGE bounds at level_noedge), MDE, "PASS, carried by one
    month" (H1, HS1, HS2), HS1's seed rule and the answer map. Writes <out_dir>/verdicts.csv and verdicts.txt (the
    four headline verdicts first). Prints only where it wrote. Refuses (SystemExit) unless every component's bound
    is at one level, equal to level_noedge / level95 when given (the runner passes the controls'), else to
    <out_dir>/controls/inference.json's when that file exists (choice 1)."""
    out = Path(out_dir)
    tj = out / "primary" / "tests.json"
    if not tj.exists():
        raise SystemExit(f"report: {tj} not found (run primary first)")
    J = json.loads(tj.read_text())
    tests = J["tests"]
    missing = [t for t in TESTS if t not in tests or "error" in tests[t]]
    if missing:
        raise SystemExit(f"report: tests missing or errored: {missing} (Holm needs all 12)")
    ij = out / "controls" / "inference.json"
    if level_noedge is None and ij.exists():
        try:
            I = json.loads(ij.read_text())
        except ValueError as e:
            raise SystemExit(f"report: {ij} unreadable: {e}")
        level_noedge = I.get("level_noedge")
        level95 = I.get("level95", 0.95) if level95 is None else level95
    tests = {t: tests[t] for t in TESTS}
    probs = _level_problems(tests, level_noedge, level95)
    by, _ = _levels(tests, "level_noedge")
    lv = next(iter(by)) if len(by) == 1 else None          # the components' level (meta's is bookkeeping only)
    if probs:
        raise SystemExit("report: the NO EDGE bounds are not at one level: " + " | ".join(probs) +
                         ". Re-run primary for every test at the controls' level")
    J["meta"] = dict(J["meta"], level_noedge=lv)
    p = _p_vec(tests)
    ph = bs.holm(p)
    rows = []
    for i, t in enumerate(TESTS):
        r = tests[t]
        ub = [_f(u) for u in r["ub_noedge"]]
        Es = [_f(e) for e in r["E"]]
        v = bs.verdict(ph[i], r["conds_ok"], ub, Es, force_inconclusive=r["force_inconclusive"])
        notes = []
        if r["force_inconclusive"]:
            notes.append("forced INCONCLUSIVE: the per-signal and exposure-time units disagree in sign" if t == "H3"
                         else "forced INCONCLUSIVE")
        if t == "HS1" and v == "PASS":
            ok, why = _median_seed_passes(tests)
            if not ok:
                v = "INCONCLUSIVE"
                notes.append("primary seed passes but the median of the 100 further seeds does not (" + why + ")")
        if v != "PASS" and ph[i] < bs.ALPHA and not r["conds_ok"]:
            notes.append("Holm p < 0.05 but conditions fail: " + "; ".join(_failed(r)))
        label = v
        if t in GROUP:
            label = bs.pass_label(v, r["flags"].get("month_dropped_mean"))
        rows.append({"test_id": t, "name": r["name"], "verdict": v, "label": label, "p_one_sided": p[i],
                     "p_holm": float(ph[i]), "p_components": json.dumps(r["p_components"]), "deciding": r["deciding"],
                     "estimate": r["estimate"], "estimate_unadjusted": _f(r.get("estimate_unadjusted")),
                     "ci95_lo": r["ci95"][0], "ci95_hi": r["ci95"][1],
                     "largest_effect_ruled_out_95": r.get("ub95"), "ub_noedge": json.dumps(ub), "E": json.dumps(Es),
                     "level_noedge": lv, "mde": r["mde"], "conds_ok": r["conds_ok"],
                     "failed_conditions": "; ".join(_failed(r)), "notes": " | ".join(notes),
                     "month_dropped_mean": r["flags"].get("month_dropped_mean"),
                     "top5_share": r["flags"].get("top5_share")})
    V = pd.DataFrame(rows).set_index("test_id")
    order = HEADLINE + [t for t in TESTS if t not in HEADLINE]
    V = V.loc[order].reset_index()
    amap = answer_map(V.set_index("test_id"), tests, out)
    V.to_csv(out / "verdicts.csv", index=False)
    (out / "verdicts.txt").write_text(_verdicts_text(V, amap, J["meta"]))
    (out / "answer_map.json").write_text(json.dumps(_jsonable(amap), indent=1))
    say(f"bb_tests report: wrote {out / 'verdicts.csv'}, {out / 'verdicts.txt'} and answer_map.json "
        f"({len(V)} tests)")
    return V


def answer_map(V: pd.DataFrame, tests: dict, out: Path | None = None) -> dict:
    """The answer to the user (fixed now): H1, H2, HS1, HS2 first; the sentence map (sentences carry the reporting
    label, e.g. "PASS, carried by one month")."""
    head = [{"test_id": t, "verdict": V.loc[t, "label"], "sentence": (_sentence(t, V.loc[t, "label"]) if t in GROUP
                                                                      else f"vs benchmarks: {V.loc[t, 'label']}")}
            for t in HEADLINE]
    groups = {GROUP[t]: _sentence(t, V.loc[t, "label"]) for t in GROUP}
    ml_ok, ml_ph = _component_passes(tests, "H2", "vs_moneyline")
    core_not_over = bool(V.loc["H1", "verdict"] == "PASS" and not ml_ok)
    beats = {}
    for t, grp in (("H9", "crypto"), ("HS1", "stocks"), ("HS2", "ETFs")):
        b = tests[t].get("extra", {}).get("answer_full_strategy_vs_holding")
        if b is not None:
            beats[grp] = {"may_say_full_strategy_beats_holding": bool(b.get("interval_above_zero_full_and_both_halves")),
                          "detail": b}
    if out is None or not (Path(out) / "routes").exists():
        trade_it = {"rows": [], "applies": None,
                    "note": "routes not run (run desc first): 'You can trade it' is undecided until results_bb/routes/ "
                            "holds the gate verdicts of 'What the user could run'"}
    else:
        trade = _routes_trade(Path(out))
        trade_it = {"rows": trade, "applies": bool(trade),
                    "note": "only TRADE gate verdicts in 'What the user could run' (results_bb/routes/), each beside "
                            "its expected false-pass count"}
    return {"headline": head, "does_it_work_by_group": groups,
            "core_edge_but_not_over_what_you_use": {"applies": core_not_over, "H1": V.loc["H1", "label"],
                                                   "H2_moneyline_component_passes": ml_ok,
                                                   "H2_moneyline_component_holm_p": ml_ph},
            "full_strategy_beats_holding": beats,
            "you_can_trade_it": trade_it}


def _fmt(x, nd=4):
    x = _f(x)
    return "nan" if not np.isfinite(x) and not np.isinf(x) else (f"{x:+.{nd}g}" if np.isfinite(x) else str(x))


def _verdicts_text(V: pd.DataFrame, amap: dict, meta: dict) -> str:
    L = ["BB-breakout replication: verdicts (analysis_2026/BB_REPLICATION_PREREG.md, 'Verdicts' and 'The answer to "
         "the user')", f"One Holm family of 12 tests, one-sided 5%. NO EDGE bounds at level {meta.get('level_noedge')} "
         f"(results_bb/controls/inference.json); written {meta.get('written')}.", "",
         "THE ANSWER (H1 crypto, H2 vs benchmarks, HS1 stocks, HS2 ETFs; in that order, before any table):"]
    for h in amap["headline"]:
        r = V.set_index("test_id").loc[h["test_id"]]
        L.append(f"  {h['test_id']:4s} {r['name']:28s} {h['verdict']:28s} estimate {_fmt(r['estimate'])} "
                 f"[95% {_fmt(r['ci95_lo'])}, {_fmt(r['ci95_hi'])}]  Holm p {_fmt(r['p_holm'], 3)}")
    L += ["", "Answer map:"]
    for g, s in amap["does_it_work_by_group"].items():
        L.append(f"  - {s}")
    c = amap["core_edge_but_not_over_what_you_use"]
    L.append(f"  - 'The core has an edge, but not over what you already use': "
             f"{'applies' if c['applies'] else 'does not apply'} (H1 {c['H1']}; H2 moneyline component passes: "
             f"{c['H2_moneyline_component_passes']})")
    for g, b in amap["full_strategy_beats_holding"].items():
        d = b["detail"]
        L.append(f"  - 'Their full strategy beats holding' ({g}, {d.get('label')}): "
                 f"{'may be said' if b['may_say_full_strategy_beats_holding'] else 'may not be said'}; full "
                 f"{_fmt(d['full']['estimate'])} [{_fmt(d['full']['ci95'][0])}, {_fmt(d['full']['ci95'][1])}] log/yr")
    t = amap["you_can_trade_it"]
    tt = ("routes not run (run desc first); undecided" if t["applies"] is None else
          "TRADE rows: " + str(t["rows"]) if t["applies"] else "no TRADE gate verdict found")
    L.append(f"  - 'You can trade it': {tt}")
    L += ["", "All 12 tests:"]
    L.append(f"  {'test':5s} {'verdict':28s} {'p':>9s} {'Holm p':>9s} {'estimate':>10s} {'unadjusted':>10s} "
             f"{'95% CI':>24s} {'ruled out@95':>12s} {'UB noedge':>22s} {'E':>14s} {'MDE':>9s}  conditions")
    for _, r in V.iterrows():
        un = _fmt(r["estimate_unadjusted"]) if np.isfinite(_f(r["estimate_unadjusted"])) else "-"
        L.append(f"  {r['test_id']:5s} {r['label']:28s} {_fmt(r['p_one_sided'], 3):>9s} {_fmt(r['p_holm'], 3):>9s} "
                 f"{_fmt(r['estimate']):>10s} {un:>10s} "
                 f"{('[' + _fmt(r['ci95_lo']) + ', ' + _fmt(r['ci95_hi']) + ']'):>24s} "
                 f"{_fmt(r['largest_effect_ruled_out_95']):>12s} {r['ub_noedge']:>22s} {r['E']:>14s} "
                 f"{_fmt(r['mde']):>9s}  {'ok' if r['conds_ok'] else 'FAILED: ' + r['failed_conditions']}"
                 + (f"  [{r['notes']}]" if r['notes'] else ""))
    L += ["", "Units: H1, HS trade parts per trade per M (drift-adjusted; 'unadjusted' = the same statistic before the "
          "drift adjustment); H3-H8 per signal / episode per M; H2, HS Sharpe parts annualized Sharpe; H9 log points a "
          "year; H10 account return a year.",
          "A summary may say the strategy 'does not work' on an asset group only if that group's H1 / HS1 / HS2 is "
          "NO EDGE."]
    return "\n".join(L) + "\n"


# ============================================================================ self-test: synthetic data
def _bridge(l0: float, mu, sigma: float, rng) -> tuple:
    """A log-price path with exact Brownian-bridge highs and lows per bar (as bb_engine's synthetic control).
    mu: per-bar expected simple return (array); sigma: per-bar log volatility. Returns (open, high, low, close)."""
    n = len(mu)
    dlog = np.log1p(mu) - 0.5 * sigma ** 2 + sigma * rng.standard_normal(n)
    lc = l0 + np.cumsum(dlog)
    lo_ = np.r_[l0, lc[:-1]]
    d2 = (lc - lo_) ** 2
    mx = 0.5 * (lo_ + lc + np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    mn = 0.5 * (lo_ + lc - np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    return np.exp(lo_), np.exp(mx), np.exp(mn), np.exp(lc)


def _regimes(n: int, per_day: int, delta: float, reg_days: float, rng) -> np.ndarray:
    """Alternating +-delta drift regimes of geometric length (mean reg_days), zero on average."""
    if not delta:
        return np.zeros(n)
    lens = rng.geometric(1 / (reg_days * per_day), size=n // per_day + 10)
    sgn = np.where(np.arange(len(lens)) % 2 == 0, 1.0, -1.0) * rng.choice([-1.0, 1.0])
    return np.repeat(sgn * delta, lens)[:n]


def _frame(idx, o, h, l, c, trades=10) -> pd.DataFrame:
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c,
                       "trades": np.full(len(idx), trades, np.int64)}, index=idx)
    df.index.name = "open_time"
    df["tradable"] = True
    df["funding"] = 0.0
    for a in bd.PX:
        df["sig_" + a] = df[a]
    df["live"] = df["sig_live"] = True
    df["seg"] = 0
    return df


def _syn_hours(start, end, sigma, seed, delta=0.0, reg_days=60.0, drift=0.0, p0=100.0) -> pd.DataFrame:
    """A coin_hours-shaped synthetic coin: hourly bridge path with regime-switching (zero-mean) trends plus a
    constant drift (per-hour simple return)."""
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"), freq="h").as_unit("ns")
    rng = np.random.default_rng(seed)
    mu = _regimes(len(idx), 24, delta, reg_days, rng) + drift
    return _frame(idx, *_bridge(math.log(p0), mu, sigma, rng))


def _with_minutes(H: pd.DataFrame, start, sigma_h: float, seed: int) -> tuple:
    """Replace H's hours from `start` by hours aggregated from a 1-minute bridge path (so the engine resolves stops on
    the minutes and bb_grid's hours-vs-minutes check holds). Returns (hours, minutes)."""
    a = pd.Timestamp(start, tz="UTC")
    pre = H[H.index < a]
    hix = H.index[H.index >= a]
    n = len(hix) * 60
    rng = np.random.default_rng(seed)
    o, h, l, c = _bridge(math.log(float(pre["close"].iloc[-1])), np.zeros(n), sigma_h / math.sqrt(60), rng)
    M = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "trades": np.full(n, 5, np.int64)},
                     index=pd.date_range(a, periods=n, freq="min").as_unit("ns"))
    M.index.name = "open_time"
    st = np.arange(0, n, 60)
    Hm = _frame(hix, o[st], np.maximum.reduceat(h, st), np.minimum.reduceat(l, st), c[st + 59], trades=300)
    return pd.concat([pre, Hm]), M


def _syn_stocks(names, seed, start="1995-01-02", end="2026-10-16", sigma=0.018, delta=0.002, reg_days=80.0) -> dict:
    """Daily OHLC (split-adjusted = total return: no dividends) on business days for synthetic names."""
    ses = pd.bdate_range(start, end).as_unit("ns")
    out = {}
    for i, nm in enumerate(names):
        rng = np.random.default_rng(seed + i)
        mu = _regimes(len(ses), 1, delta, reg_days, rng)
        lc = math.log(50.0) + np.cumsum(np.log1p(mu) - 0.5 * sigma ** 2 + sigma * rng.standard_normal(len(ses)))
        c = np.exp(lc)
        o = np.r_[50.0, c[:-1]] * np.exp(0.25 * sigma * rng.standard_normal(len(ses)))
        h = np.maximum(o, c) * np.exp(0.5 * sigma * np.abs(rng.standard_normal(len(ses))))
        l = np.minimum(o, c) * np.exp(-0.5 * sigma * np.abs(rng.standard_normal(len(ses))))
        f = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=ses)
        f["tr"] = f["close"]
        f["member"] = True
        out[nm] = f
    return out


def _mk_signals(rng, syms, n_sig, start="2020-01-05", end="2026-10-10") -> pd.DataFrame:
    """A per-signal trade frame: n_sig distinct signal days per symbol, entry the next day, ret_adj ~ N(0, 0.03)."""
    days = pd.date_range(start, end, freq="D", tz="UTC")
    rows = []
    for s in syms:
        d = np.sort(rng.choice(len(days), n_sig, replace=False))
        sd = days[d]
        rows.append(pd.DataFrame({"sym": s, "pos": np.arange(n_sig), "signal_day": sd,
                                  "entry1_time": sd + pd.Timedelta("25h"), "exit_time": sd + pd.Timedelta("12D"),
                                  "ret_adj": rng.normal(0.0, 0.03, n_sig), "expo_sum": rng.uniform(100, 400, n_sig)}))
    T = pd.concat(rows, ignore_index=True)
    T["ret"] = T["ret_adj"]
    return T


def _close(a, b, tol=1e-10) -> bool:
    a, b = float(a), float(b)
    return (np.isnan(a) and np.isnan(b)) or abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _env_stats(B_trade=999, B_port=499, level_noedge=bs.LEVEL_NOEDGE, level95=0.95) -> Env:
    return Env(primary=[], others=[], s12={}, pre_coins=[], level_noedge=level_noedge, level95=level95,
               B_trade=B_trade, B_port=B_port, seeds=())


# ============================================================================ self-test: statistics layer
def _st_trade_comp(say):
    rng = np.random.default_rng(1)
    x = rng.normal(0.01, 0.05, 240)
    g = 202001 + rng.integers(0, 12, 240) + 100 * rng.integers(0, 5, 240)
    env = _env_stats(level95=0.955, level_noedge=0.997)
    c = trade_comp("x", x, g, 0.005, env)
    m, se, t, p, df = bs.cluster_t(x, g)
    assert _close(c["estimate"], m) and _close(c["se"], se) and _close(c["p"], p) and c["df"] == df
    bb = bs.boot_t_bounds(x, g, levels=(0.95, 0.955, 0.997), B=999, seed=bs.SEED)
    assert _close(c["ub_noedge"], bb["ub"][0.997]) and _close(c["ub95"], bb["ub"][0.955])
    assert c["ub95_nominal"] <= c["ub95"] <= c["ub_noedge"]
    assert _close(c["mde"], (stats.norm.ppf(1 - 0.05 / 12) + stats.norm.ppf(0.8)) * se)
    q = stats.t.ppf(0.975, df)
    assert _close(c["ci95"][0], m - q * se)
    say(f"  trade_comp: mean / SE / p / bounds equal bb_stats' (mean {m:+.4f}, p {p:.2g}, UB {c['ub_noedge']:+.4f})")


def _st_paired(say):
    rng = np.random.default_rng(2)
    env = _env_stats(B_trade=199)
    base = _mk_signals(rng, ["A", "B", "C"], 40)
    var = base.copy()
    var["ret_adj"] = var["ret_adj"] + 0.02
    var["ret"] = var["ret_adj"]
    drop = rng.choice(len(var), 12, replace=False)            # the variant skips these signals (counts 0)
    var = var.drop(index=drop).reset_index(drop=True)
    extra = _mk_signals(np.random.default_rng(3), ["A"], 5, start="2021-03-01", end="2021-06-01")
    extra = extra[~extra.signal_day.isin(base[base.sym == "A"].signal_day)]
    var = pd.concat([var, extra], ignore_index=True)           # signals only the variant takes (base counts 0)
    r, det = h3_stats(var, base, env)                          # h3_stats(r0, s4): diff = var - base
    keep = np.setdiff1d(np.arange(len(base)), drop)
    expect = (0.02 * len(keep) - base["ret_adj"].to_numpy()[drop].sum() + extra["ret_adj"].sum()) / \
        (len(base) + len(extra))
    assert _close(r["estimate"], expect, 1e-9), (r["estimate"], expect)
    assert r["p_one_sided"] < 1e-3 and r["extra"]["n_r0_only"] == len(extra) and r["extra"]["n_s4_only"] == len(drop)
    ps = []
    for k in range(300):                                       # the null: independent values on the same signals
        rr = np.random.default_rng(1000 + k)
        b0 = _mk_signals(rr, ["A", "B", "C"], 37)
        v0 = b0.copy()
        v0["ret_adj"] = rr.normal(0.0, 0.03, len(v0))
        ps.append(h3_stats(v0, b0, env)[0]["p_one_sided"])
    ps = np.array(ps)
    rej = float((ps < 0.05).mean())
    ks = stats.kstest(ps, "uniform").pvalue
    assert 0.015 <= rej <= 0.10 and ks > 1e-3 and 0.40 <= ps.mean() <= 0.60, (rej, ks, ps.mean())
    say(f"  per-signal paired (H3 path): planted +0.02 with skips -> mean {r['estimate']:+.5f} = {expect:+.5f}, "
        f"p {r['p_one_sided']:.1e}; null over 300 data sets: rejection {rej:.3f}, KS p {ks:.2f}, mean p {ps.mean():.2f}")


def _st_h3_units(say):
    rng = np.random.default_rng(4)
    env = _env_stats(B_trade=199)
    s4 = _mk_signals(rng, ["A", "B"], 50)
    r0 = s4.copy()
    r0["ret_adj"] = r0["ret_adj"] + 0.01                       # per-signal: R0 better
    r0["expo_sum"] = r0["expo_sum"] * 20.0                     # but far more exposure-time
    s4["ret_adj"] = s4["ret_adj"] + 0.05
    r0["ret_adj"] = r0["ret_adj"] + 0.05
    r, _ = h3_stats(r0, s4, env)
    et = r["extra"]["exposure_time"]
    Ra = r0["ret_adj"].sum() / (r0["expo_sum"].sum() / 24)
    Rb = s4["ret_adj"].sum() / (s4["expo_sum"].sum() / 24)
    assert _close(et["R_R0"], Ra) and _close(et["R_S4"], Rb) and _close(et["diff"], Ra - Rb)
    assert r["estimate"] > 0 and et["diff"] < 0 and r["force_inconclusive"] and not r["gates"]["exposure_time_R0_above_S4"]
    r2, _ = h3_stats(s4.assign(ret_adj=s4.ret_adj + 0.02), s4, env)
    assert not r2["force_inconclusive"] and r2["gates"]["exposure_time_R0_above_S4"]
    say(f"  H3 units: exposure-time ratios equal sum/sum ({Ra:+.5f} vs {Rb:+.5f}); per-signal +, exposure-time - -> "
        f"forced INCONCLUSIVE; agreeing signs -> not forced")


def _st_h4(say):
    env = _env_stats(B_trade=199)
    U = lambda s: pd.Timestamp(s, tz="UTC")                   # noqa: E731
    ep = pd.DataFrame({"ep": [0, 1, 2, 3], "start": [U("2021-01-05 10:00"), U("2021-03-02 03:00"),
                                                     U("2021-06-10 00:00"), U("2022-02-01 05:00")],
                       "end": [U("2021-01-20"), U("2021-03-25"), U("2021-07-01"), U("2022-02-10")]})
    ep["start_day"] = ep["start"].dt.floor("D")
    ep["month"] = ep["start"].dt.tz_localize(None).dt.to_period("M").astype(str)
    Tc = pd.DataFrame({"sym": "A", "pos": [0, 1, 2, 3],
                       "entry1_time": [U("2021-01-06 01:00"), U("2021-03-03 01:00"), U("2021-03-10 01:00"),
                                       U("2021-09-01 01:00")],
                       "ret_adj": [0.05, 0.01, 0.01, 0.03]})
    Tt = pd.DataFrame({"sym": "A", "pos": [0, 1], "entry1_time": [U("2021-01-05 10:00"), U("2021-06-10 00:00")],
                       "ret_adj": [-0.01, 0.04]})
    kc, kt = _key_episodes(Tc, ep, "close"), _key_episodes(Tt, ep, "touch")
    r, det = h4_stats(kc, kt, ep.assign(sym="A"), env)
    # units: ep0 0.05 - (-0.01); ep1 0.02 - 0; ep2 0 - 0.04; S1's own episode 0.03 - 0  -> mean 0.07 / 4
    assert _close(r["estimate"], 0.07 / 4) and r["extra"]["n_paired_units"] == 4
    assert r["extra"]["n_episodes_without_trades"] == 1 and r["extra"]["n_s1_trades_outside_episodes"] == 1
    d = det["H4_episodes"].set_index("episode")
    assert d.loc["close_own_3", "month"] == 202109 and d.loc["0", "month"] == 202101
    say(f"  H4 episodes: union of traded episodes, S1's outside trade its own episode, empty episode counted -> "
        f"mean {r['estimate']:+.4f} = 0.0175")


def _st_h5(say):
    rng = np.random.default_rng(5)
    n = 160
    g = 202001 + (rng.integers(0, 60, n) // 12) * 100 + rng.integers(0, 12, n)
    near = rng.random(n) < 0.6
    y = 0.01 + 0.03 * near + rng.normal(0, 0.05, n)
    beta, se, t, p, df = bs.cluster_ols(y, near.astype(float), g)
    bb = ols_boot_t(y, near.astype(float), g, levels=(0.95,), B=200, seed=7, return_draws=True)
    # brute force: the same draws through bb_stats.cluster_ols on the resampled data (clusters relabelled per copy)
    uq, inv = np.unique(g, return_inverse=True)
    G = len(uq)
    idx = np.random.default_rng(7).integers(0, G, size=(200, G))
    ts = []
    for row in idx:
        rows = [np.flatnonzero(inv == c) for c in row]
        yy = np.concatenate([y[r_] for r_ in rows])
        dd = np.concatenate([near[r_].astype(float) for r_ in rows])
        gg = np.concatenate([np.full(len(r_), k) for k, r_ in enumerate(rows)])
        b_, s_, _, _, _ = bs.cluster_ols(yy, dd, gg)
        if np.isfinite(s_[1]) and s_[1] > 0:
            ts.append((b_[1] - beta[1]) / s_[1])
    assert len(ts) == len(bb["t_star"]) and np.allclose(np.sort(ts), np.sort(bb["t_star"]), atol=1e-9)
    env = _env_stats(B_trade=999)
    off = pd.DataFrame({"sym": "A", "entry1_time": pd.to_datetime([f"{m // 100}-{m % 100:02d}-15" for m in g], utc=True),
                        "ret_adj": y, "ret": y, "near_r0": near})
    r, _ = h5_stats(off, off[off.near_r0], env)
    assert _close(r["estimate"], beta[1]) and _close(r["components"][0]["p"], p[1]) and r["p_one_sided"] < 0.01
    assert _close(r["extra"]["total_ret_adj_filter_off"], y.sum())
    say(f"  H5: closed-form cluster bootstrap-t equals brute force on 200 draws; planted +0.03 -> coefficient "
        f"{beta[1]:+.4f}, p {p[1]:.1e}")


def _st_h6(say):
    env = _env_stats(B_trade=199)
    de, dx = h6_delays(*FULL)
    assert (de >= 0).all() and (de <= 24).all()
    # New York 06:00 is 10:00 UTC in EDT and 11:00 in EST: its average delay lies strictly between
    assert 10 < de[6] < 11 and 17 < dx[13] < 18, (de[6], dx[13])
    rng = np.random.default_rng(6)
    months = 202001 + (np.arange(90) // 12) * 100 + np.arange(90) % 12
    nu = rng.normal(0, 0.01, 90)

    def diffs(bump):
        out = {}
        for e in range(24):
            for x in range(24):
                f = -0.01 * ((de[e] - de[6]) ** 2 + (dx[x] - dx[13]) ** 2) + (bump if (e, x) == H6_R0_PAIR else 0.0)
                out[(e, x)] = pd.DataFrame({"diff": f + nu, "month": months})
        return out
    r1, det = h6_stats(diffs(+0.005), (de, dx), env)
    assert r1["extra"]["rank_raw"] == 1 and r1["extra"]["rank_residual"] == 1 and r1["gates_ok"]
    assert len(det["H6_pairs576"]) == 576
    r2, _ = h6_stats(diffs(-0.005), (de, dx), env)             # top raw (delay structure) but worst residual
    assert r2["extra"]["rank_raw"] <= H6_TOP and r2["extra"]["rank_residual"] == 576
    assert r2["gates"]["rank_raw_top5pct"] and not r2["gates"]["rank_residual_top5pct"]
    say(f"  H6: delays NY06 {de[6]:.2f} h, NY13 {dx[13]:.2f} h; a bump at (06, 13) ranks 1 / 1; a dip under a "
        f"quadratic delay effect ranks {r2['extra']['rank_raw']} raw but 576 on the residual -> gate fails")


def _st_h7_h8(say):
    env = _env_stats(B_trade=199)
    rng = np.random.default_rng(8)
    months = 202001 + (np.arange(80) // 12) * 100 + np.arange(80) % 12
    nu = rng.normal(0.0, 0.02, 80)
    mk = lambda m: pd.DataFrame({"diff": nu - nu.mean() + m, "month": months, "in_base": True, "in_var": True})  # noqa
    blocks = {k: mk(0.001 * k[0]) for k in PAIRS7}             # (6, 0) largest: rule 12 (4, 5) ranks 3rd
    r, det = h7_stats(blocks, env)
    assert r["extra"]["rank"] == 3 and not r["gates"]["rule12_ranks_first_of_7"]
    blocks[H7_RULE] = mk(0.02)
    r, _ = h7_stats(blocks, env)
    assert r["extra"]["rank"] == 1 and r["gates_ok"] and r["p_one_sided"] < 1e-3
    blocks[(0, 1)] = mk(0.02)                                  # a tie at the top is not "first"
    assert h7_stats(blocks, env)[0]["extra"]["rank"] == 2
    defer = {k: mk(0.001 * k[0]) for k in PAIRS7}              # Sat+Sun = (5, 6) ranks 2nd behind (6, 0)
    dose = {h: mk(0.0001 * h) for h in H8_DOSES}
    ra, _ = h8_stats(mk(0.01), defer, dose, env)
    assert ra["extra"]["rank"] == 2 and not ra["gates_ok"]
    pa = trade_comp("a", mk(0.01)["diff"], months, 0.0025, env)["p"]
    pb = trade_comp("b", defer[H8_RULE15]["diff"], months, 0.0025, env)["p"]
    assert _close(ra["p_one_sided"], max(pa, pb)) and ra["deciding"] == "per_signal_rule15_minus_S1W"
    assert len(ra["extra"]["dose_response"]) == 7
    say(f"  H7 / H8: placebo ranks (3rd; 1st; tie at the top -> 2nd), H8 p = max(p_a, p_b) = {ra['p_one_sided']:.3g}")


def _st_portfolio(say):
    env = _env_stats(B_port=499)
    rng = np.random.default_rng(9)
    days = pd.date_range("2020-01-01", "2026-10-16", freq="D", tz="UTC")
    T = len(days)
    bh = pd.Series(rng.normal(0.0003, 0.02, T), index=days)
    ml = pd.Series(rng.normal(0.0002, 0.015, T), index=days)
    s1 = pd.Series(0.3 * bh.to_numpy() + rng.normal(0.0015, 0.01, T), index=days)
    r, _ = h2_stats(s1, bh, ml, env=env)
    assert r["p_one_sided"] < 0.02 and len(r["components"]) == 2 and r["halves_ok"]
    assert _close(r["halves"]["vs_moneyline"]["2020-01..2022-12"],
                  _sharpe_diff_est(_slice(s1, "2020-01-01", "2022-12-31"), _slice(ml, "2020-01-01", "2022-12-31"), 365))
    r_, _ = h2_stats(bh, s1, ml, env=env)
    assert r_["p_one_sided"] > 0.5
    # H10: planted +0.0004 a day (about +0.146 a year)
    hd = pd.date_range(H10_WIN[0], H10_WIN[1], freq="D", tz="UTC")
    b = pd.Series(rng.normal(0.0, 0.01, len(hd)), index=hd)
    a = b + 0.0004 + rng.normal(0, 0.001, len(hd))
    r10, _ = h10_stats({"base": (a, b), "vip": (a, b), "zero": (a, b)}, pd.DataFrame(), env)
    assert r10["p_one_sided"] < 0.01 and abs(r10["estimate"] - 365 * (a - b).mean()) < 1e-9 and r10["halves_ok"]
    assert r10["components"][0]["by_block"].keys() == {"28.0"}
    # H9: r_L = L (m + s z): growth L m - L^2 s^2 / 2 a day, optimum m / s^2 = 3
    z = rng.standard_normal(T)
    m_, s_ = 0.0012, 0.02
    z = (z - z.mean()) / z.std()
    accts = {}
    for L in (1, 2, 3, 4, 5):
        rr = pd.Series(L * (m_ + s_ * z), index=days)
        accts[L] = {"ret": rr, "excess": rr, "ret_zero_interest": rr, "equity": (1 + rr).cumprod(),
                    "exposure_avg": L / 3, "exposure_peak": L, "liquidations": 0, "dead": False, "n_trades": 10}
    r9, det = h9_stats(accts, accts[1]["ret"], env)
    g = r9["extra"]["growth_optimal"]
    assert g["argmax_L"] == 3.0 and 2.5 < g["vertex_L"] < 3.5 and g["vertex_L_90"][0] <= g["vertex_L"] <= g["vertex_L_90"][1]
    assert r9["estimate"] > 0 and abs(r9["extra"]["m_over_s2_L1_daily_excess"] - (m_ / s_ ** 2)) < 0.3
    ruin = dict(accts)
    rr = accts[3]["ret"].copy()
    rr.iloc[500] = -1.0
    rr.iloc[501:] = 0.0
    ruin[3] = dict(accts[3], ret=rr)
    r9b, _ = h9_stats(ruin, None, env)
    assert r9b["estimate"] == -np.inf and r9b["p_one_sided"] == 1.0 and r9b["ub_noedge"][0] == -np.inf
    assert bs.verdict(1.0, True, r9b["ub_noedge"], r9b["E"]) == "NO EDGE (HARMS)"
    say(f"  portfolio: H2 planted Sharpe gap p {r['p_one_sided']:.3g} (reversed {r_['p_one_sided']:.2f}); H10 planted "
        f"+0.146/yr p {r10['p_one_sided']:.3g}; H9 optimum L 3 (vertex {g['vertex_L']:.2f}, 90% "
        f"[{g['vertex_L_90'][0]:.2f}, {g['vertex_L_90'][1]:.2f}]); ruin -> -inf -> NO EDGE (HARMS)")


def _st_hs(say):
    env = _env_stats(B_trade=499, B_port=299)
    rng = np.random.default_rng(10)
    ses = pd.bdate_range("2001-01-02", "2026-10-16")
    n = 900
    ed = pd.DatetimeIndex(np.sort(rng.choice(ses, n)))
    T = pd.DataFrame({"sym": rng.choice(list("ABCDEFGH"), n), "pos": np.arange(n), "entry1_date": ed,
                      "ret": rng.normal(0.01, 0.05, n)})
    T["ret_adj"] = T["ret"] - 0.002
    bench = pd.Series(rng.normal(0.0003, 0.01, len(ses)), index=ses)
    port = pd.Series(0.5 * bench.to_numpy() + rng.normal(0.0006, 0.006, len(ses)), index=ses)
    seeds = pd.DataFrame({s: port + rng.normal(0, 0.001, len(ses)) for s in (11, 12, 13)})
    r, det = hs_stats("HS1", T, port, bench, env, seeds_ex=seeds, port_ret=port, bench_ret=bench)
    assert r["p_one_sided"] < 0.01 and r["conds_ok"] and set(r["p_components"]) == {"trade_drift_adjusted_mean",
                                                                                    "sharpe_vs_benchmark"}
    mo = bs.month_key(T["entry1_date"])
    assert _close(r["flags"]["month_dropped_mean"], bs.drop_worst_month(T["ret_adj"], mo)[0])
    jobs = seed_jobs(r, env)
    assert len(jobs) == 3
    r = seed_finalize(r, [_seed_job(j) for j in jobs])
    s = r["flags"]["seeds"]
    assert s["n"] == 3 and np.isfinite(s["p_median"]) and "_pending_seeds" not in r
    assert r["extra"]["answer_full_strategy_vs_holding"]["full"]["ci95"][0] > 0
    say(f"  HS: p = max(p_trade, p_Sharpe) = {r['p_one_sided']:.2g}; seeds median p {s['p_median']:.3g}; month-dropped "
        f"mean equals bb_stats'")


def _st_review_fixes(say):
    """Regression checks of the adversarial review: the unadjusted value beside every trade-level and paired test
    (H1, H3-H8, HS), overlap-episode (and quarter) cluster sensitivities on every such component, ZEC shown beside
    ex-ZEC in H1's pools, exploratory BH within the descriptive p tables (H6, H7, H8), and H10's zero-interest version
    and 1-, 3- and 12-month blocks."""
    env = _env_stats(B_trade=199, B_port=199)
    rng = np.random.default_rng(12)
    # H3: R0 carries a larger drift charge, so the unadjusted difference exceeds the drift-adjusted one by 0.03
    s4 = _mk_signals(rng, ["A", "B", "C"], 40)
    r0 = s4.copy()
    r0["ret_adj"] = s4["ret_adj"] + rng.normal(0.0, 0.01, len(s4))
    r0["ret"] = r0["ret_adj"] + 0.03
    r0["exit_time"] = s4["exit_time"] + pd.to_timedelta(np.where(np.arange(len(s4)) % 2 == 0, 5, -3), unit="D")
    r3, d3 = h3_stats(r0, s4, env)
    c3 = r3["components"][0]
    ea, eu = float((r0.ret_adj - s4.ret_adj).mean()), float((r0.ret - s4.ret).mean())
    assert _close(r3["estimate"], ea) and _close(c3["estimate_unadjusted"], eu) and _close(r3["estimate_unadjusted"], eu)
    assert abs(eu - ea - 0.03) < 1e-12
    assert _close(c3["unadjusted"]["p"], bs.cluster_t((r0.ret - s4.ret).to_numpy(float), bs.month_key(s4.entry1_time))[3])
    assert np.isfinite(r3["extra"]["exposure_time"]["diff_unadjusted"])
    D = d3["H3_signals"]
    want = s4[["sym", "signal_day"]].assign(
        w_start=_naive(s4.entry1_time).to_numpy(),
        w_end=np.maximum(_naive(r0.exit_time).to_numpy(), _naive(s4.exit_time).to_numpy()))
    M_ = D.merge(want, on=["sym", "signal_day"], how="inner", validate="one_to_one")
    assert len(M_) == len(D) == len(s4)
    assert (M_["unit_start"] == M_["w_start"]).all() and (M_["unit_end"] == M_["w_end"]).all()
    ep = bs.overlap_episodes(D["unit_start"], D["unit_end"])
    assert 1 < c3["G_overlap_episodes"] == len(np.unique(ep)) < len(D)
    assert _close(c3["p_overlap_episode_clusters"], bs.cluster_t(D["diff"].to_numpy(float), ep)[3])
    # H4: S1's trades carry +0.01 each in ret over ret_adj -> unadjusted = adjusted + 0.01 x 4 trades / 4 units
    U = lambda s: pd.Timestamp(s, tz="UTC")                   # noqa: E731
    ep4 = pd.DataFrame({"ep": [0, 1, 2], "start": [U("2021-01-05 10:00"), U("2021-03-02 03:00"), U("2021-06-10")],
                        "end": [U("2021-01-20"), U("2021-03-25"), U("2021-07-01")]})
    Tc = pd.DataFrame({"sym": "A", "pos": [0, 1, 2, 3], "ret_adj": [0.05, 0.01, 0.01, 0.03],
                       "entry1_time": [U("2021-01-06 01:00"), U("2021-03-03 01:00"), U("2021-03-10 01:00"),
                                       U("2021-09-01 01:00")]})
    Tc["exit_time"], Tc["ret"] = Tc["entry1_time"] + pd.Timedelta("6D"), Tc["ret_adj"] + 0.01
    Tt = pd.DataFrame({"sym": "A", "pos": [0, 1], "ret_adj": [-0.01, 0.04],
                       "entry1_time": [U("2021-01-05 10:00"), U("2021-06-10 00:00")]})
    Tt["exit_time"], Tt["ret"] = Tt["entry1_time"] + pd.Timedelta("9D"), Tt["ret_adj"]
    r4, d4 = h4_stats(_key_episodes(Tc, ep4, "close"), _key_episodes(Tt, ep4, "touch"), ep4.assign(sym="A"), env)
    assert _close(r4["estimate"], 0.07 / 4) and _close(r4["estimate_unadjusted"], 0.07 / 4 + 0.01)
    e0 = d4["H4_episodes"].set_index("episode").loc["0"]
    assert e0["unit_start"] == _naive([U("2021-01-05 10:00")])[0] and e0["unit_end"] == _naive([U("2021-01-14 10:00")])[0]
    assert "p_overlap_episode_clusters" in r4["components"][0]
    # H5: ret = ret_adj + 0.02 x near -> the unadjusted coefficient is the adjusted one + 0.02 (OLS is linear)
    off = s4.assign(near_r0=rng.random(len(s4)) < 0.5)
    off["ret"] = off["ret_adj"] + 0.02 * off["near_r0"]
    c5 = h5_stats(off, off[off.near_r0], env)[0]["components"][0]
    assert _close(c5["estimate_unadjusted"], c5["estimate"] + 0.02, 1e-9)
    assert np.isfinite(c5["p_quarter_clusters"]) and "p_overlap_episode_clusters" in c5
    # H6 / H7 / H8 through _pair: the variant's ret exceeds its ret_adj by 0.02 -> unadjusted = adjusted + 0.02;
    # the descriptive tables' p are labelled exploratory and BH-adjusted within the table
    base = _mk_signals(rng, ["A", "B", "C"], 30)
    var = base.assign(ret_adj=base.ret_adj + 0.01 + rng.normal(0, 0.005, len(base)))
    var["ret"] = var["ret_adj"] + 0.02
    dv = _pair(base, var)
    nulls = [_pair(base, base.assign(ret_adj=base.ret_adj + rng.normal(0, 0.01, len(base)))) for _ in range(6)]
    de, dx = h6_delays(*FULL)
    dif6 = {(e, x): nulls[(e * 24 + x) % 6] for e in range(24) for x in range(24)}
    dif6[H6_R0_PAIR] = dv
    r6, t6 = h6_stats(dif6, (de, dx), env)
    r7, t7 = h7_stats({k: (dv if k == H7_RULE else nulls[k[0] % 6]) for k in PAIRS7}, env)
    r8, t8 = h8_stats(dv, {k: (dv if k == H8_RULE15 else nulls[k[0] % 6]) for k in PAIRS7},
                      {h: nulls[i % 6] for i, h in enumerate(H8_DOSES)}, env)
    for r in (r6, r7, r8):
        for c in r["components"]:
            assert _close(c["estimate_unadjusted"] - c["estimate"], 0.02, 1e-9), (r["test_id"], c["name"])
            assert "p_overlap_episode_clusters" in c and "p_quarter_clusters" in c
    for tab in (t6["H6_pairs576"], t7["H7_blocks"], t8["H8_deferrals"], t8["H8_dose"]):
        assert "p_one_sided" not in tab.columns and {"p_one_sided_exploratory", "p_bh_exploratory"} <= set(tab.columns)
        assert np.allclose(tab["p_bh_exploratory"], bs.bh(tab["p_one_sided_exploratory"].to_numpy(float)), equal_nan=True)
    assert (t6["H6_pairs576"]["p_bh_exploratory"] >= t6["H6_pairs576"]["p_one_sided_exploratory"]).all()
    # H1: ZEC carries the other-37 pool; the ex-ZEC pools are reported beside, the gate stays on the full pool
    oth = _mk_signals(rng, ["ZEC", "ADA", "XRP"], 30)
    oth.loc[oth.sym == "ZEC", "ret_adj"] += 0.30
    pre = _mk_signals(rng, ["ZEC", "LTC"], 10, start="2017-10-01", end="2019-12-01")
    r1, _ = h1_stats(base, oth, base.iloc[:0], pre, env)
    x = r1["extra"]["other37_ex_ZEC"]
    assert _close(x["mean"], oth.loc[oth.sym != "ZEC", "ret_adj"].mean()) and x["n_coins_traded"] == 2
    assert x["zec_trades_removed"] == 30 and r1["gates"]["other37_drift_adjusted_mean_gt0"] == (oth.ret_adj.mean() > 0)
    assert _close(r1["extra"]["pre_perpetual_ex_ZEC"]["mean"], pre.loc[pre.sym == "LTC", "ret_adj"].mean())
    assert r1["extra"]["s12_top3_ex_ZEC"]["n"] == 0
    c1 = r1["components"][0]
    assert _close(c1["p_overlap_episode_clusters"], bs.cluster_t(base.ret_adj, bs.overlap_episodes(base.entry1_time,
                                                                                                   base.exit_time))[3])
    assert _close(c1["estimate_unadjusted"], base["ret"].mean())
    # HS trade part: overlap-episode clusters on [entry1_date, exit_date] and the unadjusted mean
    ses = pd.bdate_range("2001-01-02", "2026-10-16")
    ed = pd.DatetimeIndex(np.sort(rng.choice(ses, 300)))
    Ts = pd.DataFrame({"sym": rng.choice(list("ABCD"), 300), "pos": np.arange(300), "entry1_date": ed,
                       "exit_date": ed + pd.Timedelta("15D"), "ret": rng.normal(0.01, 0.05, 300)})
    Ts["ret_adj"] = Ts["ret"] - 0.004
    bench = pd.Series(rng.normal(0.0003, 0.01, len(ses)), index=ses)
    rs, _ = hs_stats("HS2", Ts, bench + rng.normal(0, 0.003, len(ses)), bench, env)
    ct = rs["components"][0]
    assert _close(ct["estimate_unadjusted"] - ct["estimate"], 0.004, 1e-9) and ct["G_overlap_episodes"] > 1
    # H10: zero-interest version and the 1-, 3- and 12-month blocks reported; the 28-day block still decides
    hd = pd.date_range(H10_WIN[0], H10_WIN[1], freq="D", tz="UTC")
    b = pd.Series(rng.normal(0.0, 0.01, len(hd)), index=hd)
    a = b + 0.0004 + rng.normal(0, 0.001, len(hd))
    a0, b0 = a - 0.0001, b + 0.0001
    r10, _ = h10_stats({"base": (a, b), "vip": (a, b), "zero": (a, b)}, pd.DataFrame(), env, zero_interest=(a0, b0))
    z = r10["extra"]["zero_interest"]
    assert _close(z["estimate"], 365 * (a0 - b0).mean(), 1e-9) and r10["components"][0]["by_block"].keys() == {"28.0"}
    bm = r10["extra"]["blocks_1_3_12_months"]["by_block_months"]
    assert set(bm) == {"1", "3", "12"} and all(_close(bm[m]["mean_block"], int(m) * MONTH_DAYS, 1e-9) for m in bm)
    say(f"  review fixes: unadjusted beside drift-adjusted in H1, H3-H8, HS (H3 +{eu - ea:.2f}, H5 +0.02); union spans and "
        f"overlap-episode clusters ({c3['G_overlap_episodes']} episodes for {len(D)} H3 signals); ex-ZEC pools beside "
        f"(other-37 {oth.ret_adj.mean():+.3f} with ZEC, {x['mean']:+.3f} without); exploratory BH in the H6 / H7 / H8 "
        f"tables; H10 zero-interest and 1 / 3 / 12-month blocks")


def _fake(tid, ps, ub, E_, conds=True, force=False, flags=None, extra=None, names=None):
    names = names or [f"c{i}" for i in range(len(ps))]
    comps = [{"name": n, "p": p, "estimate": 0.01, "se": 0.004, "ci95": [-0.01, 0.03], "ub95": u, "ub_noedge": u,
              "E": e, "mde": 0.014, "level_noedge": bs.LEVEL_NOEDGE} for n, p, u, e in zip(names, ps, ub, E_)]
    gates = {"g": conds}
    return _result(tid, comps, gates, {names[0]: {"h1": 0.01, "h2": 0.02}}, flags or {}, force, extra)


def _st_report(say):
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="bb_tests_report_"))
    (tmp / "primary").mkdir()
    (tmp / "routes").mkdir()
    bh_ok = {"label": "x", "full": {"estimate": 0.1, "ci95": [0.02, 0.2]}, "interval_above_zero_full_and_both_halves": True}
    bh_no = dict(bh_ok, interval_above_zero_full_and_both_halves=False)
    T = {"H1": _fake("H1", [1e-4], [0.02], [0.005], flags={"month_dropped_mean": -0.001}),
         "H2": _fake("H2", [1e-3, 0.3], [0.5, 0.05], [0.1, 0.1], names=["vs_buy_and_hold", "vs_moneyline"]),
         "H3": _fake("H3", [1e-4], [0.02], [0.0025], force=True),
         "H4": _fake("H4", [0.5], [-0.01], [0.0025]),
         "H5": _fake("H5", [0.2], [0.05], [0.0025]),
         "H6": _fake("H6", [2e-4], [0.01], [0.0025], conds=False),
         "H7": _fake("H7", [3e-3], [0.02], [0.0025]),
         "H8": _fake("H8", [0.04, 0.01], [0.1, 0.1], [0.0025, 0.0025]),
         "H9": _fake("H9", [1.0], [-np.inf], [0.02], extra={"answer_full_strategy_vs_holding": bh_no}),
         "H10": _fake("H10", [0.6], [0.005], [0.01]),
         "HS1": _fake("HS1", [1e-5, 1e-4], [0.02, 0.5], [0.005, 0.1], names=["trade_drift_adjusted_mean",
                                                                            "sharpe_vs_benchmark"],
                      flags={"month_dropped_mean": 0.003, "seeds": {"p_median": 0.2, "halves_median": {"a": 0.1}}},
                      extra={"answer_full_strategy_vs_holding": bh_no}),
         "HS2": _fake("HS2", [1e-4, 3e-4], [0.02, 0.5], [0.005, 0.1], names=["trade_drift_adjusted_mean",
                                                                            "sharpe_vs_benchmark"],
                      flags={"month_dropped_mean": 0.002}, extra={"answer_full_strategy_vs_holding": bh_ok})}
    meta = {"level_noedge": bs.LEVEL_NOEDGE, "written": "selftest"}
    (tmp / "primary" / "tests.json").write_text(json.dumps(_jsonable({"meta": meta, "tests": T})))
    pd.DataFrame([{"route": "RH", "row": "S1", "sym": "BTC", "verdict": "TRADE", "placebo_trade_p": 0.07},
                  {"route": "RH", "row": "S1", "sym": "ETH", "verdict": "NO-SIGNAL", "placebo_trade_p": 0.05}]
                 ).to_csv(tmp / "routes" / "gate.csv", index=False)
    V = report(tmp, say=lambda s: None).set_index("test_id")
    ph = bs.holm(np.array([T[t]["p_one_sided"] for t in TESTS]))
    assert np.allclose(V.loc[TESTS, "p_holm"].to_numpy(float), ph)
    want = {"H1": "PASS", "H2": "NO EDGE", "H3": "INCONCLUSIVE", "H4": "NO EDGE (HARMS)", "H5": "INCONCLUSIVE",
            "H6": "INCONCLUSIVE", "H7": "PASS", "H8": "INCONCLUSIVE", "H9": "NO EDGE (HARMS)", "H10": "NO EDGE",
            "HS1": "INCONCLUSIVE", "HS2": "PASS"}
    got = V["verdict"].to_dict()
    assert got == want, got
    assert V.loc["H1", "label"] == "PASS, carried by one month" and V.loc["HS2", "label"] == "PASS"
    assert "median" in V.loc["HS1", "notes"] and "conditions fail" in V.loc["H6", "notes"]
    v = pd.read_csv(tmp / "verdicts.csv")
    assert list(v["test_id"][:4]) == HEADLINE and len(v) == 12
    A = json.loads((tmp / "answer_map.json").read_text())
    assert A["core_edge_but_not_over_what_you_use"]["applies"] is True
    assert "does not work" not in A["does_it_work_by_group"]["crypto"] and "cannot tell" in A["does_it_work_by_group"]["stocks"]
    assert A["full_strategy_beats_holding"]["ETFs"]["may_say_full_strategy_beats_holding"] is True
    assert A["full_strategy_beats_holding"]["crypto"]["may_say_full_strategy_beats_holding"] is False
    assert A["you_can_trade_it"]["applies"] and len(A["you_can_trade_it"]["rows"]) == 1
    lines = (tmp / "verdicts.txt").read_text().splitlines()
    k = next(i for i, ln in enumerate(lines) if ln.startswith("THE ANSWER"))
    assert [lines[k + 1 + j].split()[0] for j in range(4)] == HEADLINE
    # review fix: the answer map's sentences carry the reporting label, not the bare verdict
    lab = "PASS, carried by one month"
    assert lab in A["does_it_work_by_group"]["crypto"] and lab in A["headline"][0]["sentence"], A["headline"][0]
    assert any(ln.strip().startswith("- crypto") and lab in ln for ln in lines)
    assert A["core_edge_but_not_over_what_you_use"]["H1"] == lab
    # review fix: without routes/ "You can trade it" is undecided ("routes not run"), not "no TRADE gate verdict"
    import shutil
    shutil.rmtree(tmp / "routes")
    report(tmp, say=lambda s: None)
    A = json.loads((tmp / "answer_map.json").read_text())
    assert A["you_can_trade_it"]["applies"] is None and "routes not run" in A["you_can_trade_it"]["note"]
    txt = (tmp / "verdicts.txt").read_text()
    assert "routes not run" in txt and "no TRADE gate verdict" not in txt
    # review fix: one NO EDGE level across the family, equal to the controls' (mixed levels / another level refuse)
    tj = tmp / "primary" / "tests.json"
    T["H5"]["components"][0]["level_noedge"] = 0.999            # a subset re-run at a widened level
    tj.write_text(json.dumps(_jsonable({"meta": dict(meta, level_noedge=0.999), "tests": T})))
    for kw in ({}, {"level_noedge": 0.999}):
        try:
            report(tmp, say=lambda s: None, **kw)
            raise AssertionError(f"report ran with mixed NO EDGE levels {kw}")
        except SystemExit as e:
            assert "not at one level" in str(e) and "H5" in str(e), e
    T["H5"]["components"][0]["level_noedge"] = bs.LEVEL_NOEDGE
    tj.write_text(json.dumps(_jsonable({"meta": meta, "tests": T})))
    (tmp / "controls").mkdir()
    (tmp / "controls" / "inference.json").write_text(json.dumps({"level_noedge": 0.997, "level95": 0.955}))
    for kw in ({}, {"level_noedge": 0.997, "level95": 0.955}):
        try:
            report(tmp, say=lambda s: None, **kw)
            raise AssertionError("report ran at a level other than the controls'")
        except SystemExit as e:
            assert "controls" in str(e), e
    (tmp / "controls" / "inference.json").write_text(json.dumps({"level_noedge": bs.LEVEL_NOEDGE, "level95": 0.95}))
    report(tmp, say=lambda s: None)
    assert pd.read_csv(tmp / "verdicts.csv")["level_noedge"].nunique() == 1
    # a NO EDGE for the crypto group reads "does not work"; a missing test stops the report
    T["H1"] = _fake("H1", [0.3], [0.001], [0.005], flags={"month_dropped_mean": 0.001})
    (tmp / "primary" / "tests.json").write_text(json.dumps(_jsonable({"meta": meta, "tests": T})))
    report(tmp, say=lambda s: None)
    A = json.loads((tmp / "answer_map.json").read_text())
    assert "does not work" in A["does_it_work_by_group"]["crypto"] and not A["core_edge_but_not_over_what_you_use"]["applies"]
    del T["H5"]
    (tmp / "primary" / "tests.json").write_text(json.dumps(_jsonable({"meta": meta, "tests": T})))
    try:
        report(tmp, say=lambda s: None)
        raise AssertionError("report ran with a missing test")
    except SystemExit:
        pass
    shutil.rmtree(tmp, ignore_errors=True)
    say("  report truth table: Holm = bb_stats.holm; PASS / carried by one month / NO EDGE / HARMS / forced and "
        "gated INCONCLUSIVE / HS1 seed rule; answer map (sentences carry the label; no routes/ -> undecided); "
        "headline order; a missing test, mixed NO EDGE levels or a level other than the controls' stop the report")


def _st_replica(say):
    from analysis_2026 import bb_replica
    bb_replica.check_gate(say)


# ============================================================================ self-test: engine integration
def _st_detect(say):
    """The planted trend is detected through the real engine (8 trending synthetic coins, S1 at L = 1)."""
    hrs = {f"D{i}": _syn_hours("2019-06-01", "2026-10-16 23:00", 0.006, 300 + i, delta=0.0006) for i in range(8)}
    env = Env(hours=hrs, primary=list(hrs), others=[], s12={}, pre_coins=[], mmr=0.005, B_trade=999, seeds=())
    r, det = test_h1(env)
    assert r["estimate"] > 0 and r["p_one_sided"] < 0.01 and env.audit["violations"] == 0, r["p_one_sided"]
    assert r["components"][0]["n"] == len(det["H1_trades"]) > 80
    be.clear_cache()
    say(f"  engine: planted trends on 8 coins -> H1 {r['components'][0]['n']} trades, drift-adjusted mean "
        f"{r['estimate']:+.4f}, p {r['p_one_sided']:.1e}; {env.audit['engine_runs']} engine runs, fill audit empty")


def _st_drift(say):
    """Drift wiring: under a constant drift and no timing skill (zero fees), the unadjusted mean is far above 0 and
    the drift-adjusted mean is not."""
    hrs = {f"C{i}": _syn_hours("2019-06-01", "2026-10-16 23:00", 0.006, 400 + i, drift=2e-4) for i in range(6)}
    env = Env(hours=hrs, primary=list(hrs), others=[], s12={}, pre_coins=[], mmr=0.005, B_trade=499, seeds=(),
              cfg_tweak={"fees": "zero"})
    r, det = test_h1(env)
    un = r["extra"]["unadjusted"]
    t_adj = r["estimate"] / r["se"]
    assert un["p"] < 1e-3 and abs(t_adj) < 3, (un, t_adj)
    T = det["H1_trades"]
    # the drift charge of a few trades recomputed from its definition: mu = the coin's mean hourly return outside
    # [entry1 - 182 d, exit + 182 d], times the position's summed notional / M
    for _, tr in T.groupby("sym").head(2).iterrows():
        rr = bs.returns_from_hours(hrs[tr["sym"]])
        out_ = (rr.index < tr["entry1_time"] - pd.Timedelta("182D")) | (rr.index > tr["exit_time"] + pd.Timedelta("182D"))
        assert _close(tr["drift"], rr[out_].mean() * tr["expo_sum"], 1e-9), (tr["drift"], rr[out_].mean() * tr["expo_sum"])
    be.clear_cache()
    say(f"  engine: constant drift, zero fees -> unadjusted mean {un['mean']:+.4f} (p {un['p']:.1e}), drift-adjusted "
        f"{r['estimate']:+.4f} (t {t_adj:+.2f}); drift charge = mu x expo_sum")


def _syn_env(seeds=3) -> Env:
    hours, minutes = {}, {}
    for i, s in enumerate(["SA", "SB", "SC"]):
        H = _syn_hours("2017-06-01", "2026-10-16 23:00", 0.006, 11 + i, delta=0.0006)
        hours[s], minutes[s] = _with_minutes(H, "2024-07-01", 0.006, 21 + i)
    for i, s in enumerate(["SD", "SE"]):
        hours[s] = _syn_hours("2018-03-01", "2026-10-16 23:00", 0.008, 31 + i, delta=0.0005)
    ms = pd.date_range("2020-01-01", "2026-10-01", freq="MS", tz="UTC")
    s12 = {"SD": pd.Series(np.arange(len(ms)) % 2 == 0, index=ms), "SA": pd.Series(np.arange(len(ms)) % 3 != 0, index=ms)}
    stocks = {"members": _syn_stocks([f"M{i:02d}" for i in range(30)], 500),
              "etfs": _syn_stocks([f"E{i:02d}" for i in range(14)], 700, sigma=0.012)}
    return Env(hours=hours, minutes=minutes, primary=["SA", "SB", "SC"], others=["SD", "SE"], s12=s12,
               pre_coins=["SA", "SB", "SC"], stocks=stocks, mmr=0.005, B_trade=999, B_port=199,
               seeds=tuple(range(bs.SEED + 1, bs.SEED + 1 + seeds)))


def _st_end_to_end(say):
    """All 12 tests through run() (process pool, fork) on synthetic coins, minutes and stocks, then report()."""
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="bb_tests_e2e_"))
    env = _syn_env()
    t0 = time.time()
    run(tmp, jobs=4, env=env, say=lambda s: None)
    J = json.loads((tmp / "primary" / "tests.json").read_text())
    assert set(J["tests"]) == set(TESTS) and J["meta"]["fill_audit_violations"] == 0
    for t in TESTS:
        r = J["tests"][t]
        assert "error" not in r, (t, r.get("error"))
        p = _f(r["p_one_sided"])
        assert 0 <= p <= 1, (t, p)
        assert len(r["ub_noedge"]) == len(r["E"]) == len(r["components"]) >= 1
        assert r["fill_audit"]["violations"] == 0
    runs = {t: J["tests"][t]["fill_audit"] for t in TESTS}
    assert runs["H6"]["engine_runs"] >= 576 * 3 and runs["H10"]["grid_runs"] == 3 * 3 + 3
    assert runs["HS1"]["stock_runs"] == 2 and runs["HS2"]["stock_runs"] == 1
    tab = pd.read_csv(tmp / "primary" / "H6_pairs576.csv")
    assert len(tab) == 576 and tab["is_R0_pair"].sum() == 1
    assert set(J["tests"]["H1"]["gates"]) == {"unadjusted_mean_gt0", "drift_adjusted_mean_gt0_both_halves",
                                               "other37_drift_adjusted_mean_gt0", "s12_top3_drift_adjusted_mean_gt0"}
    assert J["tests"]["H1"]["extra"]["s12_top3"]["n"] > 0 and J["tests"]["H1"]["extra"]["pre_perpetual"]["n"] > 0
    assert len(J["tests"]["HS1"]["flags"]["seeds"]["p"]) == len(env.seeds)
    assert J["tests"]["HS2"]["extra"]["n_slots"] == 14 and J["tests"]["HS1"]["extra"]["n_slots"] == 20
    assert "block_1996_2000" in J["tests"]["HS1"]["extra"]
    assert set(J["tests"]["H10"]["extra"]) >= {"fees_vip", "fees_zero", "touch_fills_optimistic", "dollars",
                                                "zero_interest", "blocks_1_3_12_months"}
    for t in ("H1", "H3", "H4", "H5", "H6", "H7", "H8", "HS1", "HS2"):     # review fixes on real engine output
        for comp in J["tests"][t]["components"]:
            if comp["kind"] in ("trade", "trade_ols"):
                assert {"estimate_unadjusted", "p_quarter_clusters", "p_overlap_episode_clusters"} <= set(comp), \
                    (t, comp["name"])
        dec = next(c_ for c_ in J["tests"][t]["components"] if c_["name"] == J["tests"][t]["deciding"])
        if dec["kind"] in ("trade", "trade_ols"):         # a compound test may be decided by its portfolio part
            assert _close(_f(J["tests"][t]["estimate_unadjusted"]), _f(dec["estimate_unadjusted"])), t
    assert {"other37_ex_ZEC", "s12_top3_ex_ZEC", "pre_perpetual_ex_ZEC"} <= set(J["tests"]["H1"]["extra"])
    assert {"p_one_sided_exploratory", "p_bh_exploratory", "mean_unadjusted"} <= set(tab.columns)
    assert "unit_start" in pd.read_csv(tmp / "primary" / "H3_signals.csv").columns
    c = pd.read_csv(tmp / "primary" / "tests.csv")
    assert list(c["test_id"]) == TESTS and "estimate_unadjusted" in c.columns
    V = report(tmp, say=lambda s: None)
    assert list(V["test_id"][:4]) == HEADLINE
    assert set(V["verdict"]) <= {"PASS", "NO EDGE", "NO EDGE (HARMS)", "INCONCLUSIVE"}
    # a subset re-run merges into tests.json
    run(tmp, which=["H5"], jobs=1, env=env, say=lambda s: None)
    J2 = json.loads((tmp / "primary" / "tests.json").read_text())
    assert set(J2["tests"]) == set(TESTS)
    # review fix: a subset re-run at another NO EDGE level (the controls widened it) refuses before running
    lv0, n0 = env.level_noedge, env.audit["engine_runs"]
    env.level_noedge = 0.999
    try:
        run(tmp, which=["H5"], jobs=1, env=env, say=lambda s: None)
        raise AssertionError("a subset run at another level merged into tests.json")
    except SystemExit as e:
        assert "refusing to merge" in str(e) and env.audit["engine_runs"] == n0, e
    env.level_noedge = lv0
    assert json.loads((tmp / "primary" / "tests.json").read_text())["meta"]["level_noedge"] == lv0
    shutil.rmtree(tmp, ignore_errors=True)
    say(f"  end to end: 12 tests through run() (4 processes) and report() in {time.time() - t0:.0f} s; "
        f"{sum(v['engine_runs'] for v in runs.values())} engine, {runs['H10']['grid_runs']} grid, "
        f"{runs['HS1']['stock_runs'] + runs['HS2']['stock_runs']} stock runs; fill audits empty; 576-pair table; "
        f"unadjusted values, sensitivity clusters, ex-ZEC pools and H10 extras present; subset re-run merges; a "
        f"subset at another level refuses")


def _st_fill_audit_stops(say):
    """A fill-audit violation raises (and run() records it and raises after writing the others)."""
    env = _env_stats()
    try:
        env._check(["BTC price outside bar range: ..."], "selftest")
        raise AssertionError("a fill audit violation did not raise")
    except RuntimeError:
        pass
    assert env.audit["violations"] == 1
    say("  fill audit: a violation raises")


def selftest() -> None:
    """Synthetic known answers (statistics layer, report truth table, runner refusal) and engine integration on
    synthetic coins, minutes and stocks. No market data is read."""
    t0 = time.time()

    def say(s):
        print(s, flush=True)
    say("bb_tests selftest")
    for fn in (_st_trade_comp, _st_paired, _st_h3_units, _st_h4, _st_h5, _st_h6, _st_h7_h8, _st_portfolio, _st_hs,
               _st_review_fixes, _st_report, _st_replica, _st_fill_audit_stops, _st_detect, _st_drift, _st_end_to_end):
        t1 = time.time()
        fn(say)
        say(f"    ({fn.__name__} {time.time() - t1:.1f} s)")
    say(f"bb_tests selftest: all passed in {time.time() - t0:.0f} s")




if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "selftest":
        selftest()
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}; use python3 -m analysis_2026.bb_replica")
