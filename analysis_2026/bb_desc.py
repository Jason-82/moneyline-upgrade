"""
Descriptive outputs of the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md): every
pre-registered row and table that is not one of the 12 Holm-family tests (bb_tests.py) and not H11 / H11b / H12 /
the luck benchmark / F's counts (bb_fit.py). Sections implemented:
  "Windows" (Full, W16, W16b, the crypto halves, the pre-perpetual block; window edges), "Sensitivity grid"
  (S1-S20, S1W, the bar-size rows, the S3 cross and S12 universes incl. the Addendum's TradFi sensitivity, S17's
  hindsight universe), the R0 table's "Hard stop" (the at_S row, the 2025-10-10 stress row and the list of trades
  stopped on 2025-10-10/11) and "Fee scenarios" (R0, S1, F), "Headline replication" (R0 at L = 3, S1 at L = 1 and F
  on each window and asset group with 95% month-block bootstrap intervals, after-tax CAGR next to SPY's, buy-and-hold
  and the repo indicator beside them; W16 / W16b labelled single 16-month paths), "The answer to the user"'s
  "beats holding the coins" statistic, "What the user could run" (bb_bench.routes), the TV cross-check, the "Rule
  scorecard", "Grid overlays" (G-B, G-0, the six-slot G-A run, touch-fill bounds; H10's fee scenarios when the
  primary run lacks them), "Stocks and ETFs" extras (2x Reg-T, double costs, 1996-2000, S20 weekly, the user's
  tickers with the 20-trade floor, ETFs individually), "Multiplicity" (exploratory p-values, Benjamini-Hochberg
  within each table) and "Reporting rules" (results with ZEC beside results without it). Addendum and Addendum 2
  bind (S12 crypto-only pool primary; spot routes on the longest spot history with the Full window beside; HS2's
  14 slots; H3-H8 comparisons at L = 3). Contract: the scratchpad's bb_engine_spec.md, "Integration layer".
  Nothing here re-implements the engine, statistics, grid, stock or benchmark modules (bb_engine, bb_stats,
  bb_grid, bb_stocks, bb_bench): it calls them and tabulates.

    python3 -m analysis_2026.bb_desc run --out DIR [--which rows,headline,routes,tv,scorecard,explore] [--jobs 4]
    python3 -m analysis_2026.bb_desc selftest      # synthetic known answers + a tiny end-to-end run (injected data)
    python3 -m analysis_2026.bb_replica desc        # the runner (refuses unless every control passed)

DIR is the results root (analysis_2026/results_bb); each part writes its own subdirectory. Nothing is printed but
counts, shapes, timings and fill-audit status.

Public API
  run(out_dir, which=None, jobs=4, src=None, conf=None, say=print) -> dict     the parts, written as CSV / JSON
  Conf(...)                    windows, row subset, bootstrap sizes, placebo count, coin lists (defaults = the
                               pre-registration; the self-test shrinks them)
  Src(hours=, minutes=, universes=, mmr=, stocks=, tv=)   injected data (None = the data on disk)
  trade_stats(T, pnl_col)      trade-level statistics of a position table (headline / H11 definitions)
  trade_intervals(T, ...)      month-cluster bootstrap intervals of those statistics
  account_stats(ret, excess, ppy, years), account_intervals(...)   multiple, CAGR, Sharpe, max drawdown (+ 95%
                               month-block bootstrap intervals, bb_stats.block_boot_ci)
  count_interval(times, start, end, ...)   month-block bootstrap interval of a count (trades, liquidations)
  account_record(a0, a1, T, start=None, end=None)   a table row's account and trade statistics (a half: the slice)
  slice_record(a0, a1, T, start, end) -> (row, trades)   a half of the Full run (coding choice 1)
  win_split(conf) -> (run windows, half slices, separate-run halves)
  beats_holding(a, b, kind, halves)        the answer map's mean log growth difference with its 95% interval
  read_f_cell(out_dir) -> (cell | None, note)    F's identity from results_bb/fcount/
  ensure_f_cell(out_dir, conf, src, jobs)  F's counts by bb_fit.run(which="fcount") when they are missing
  scorecard_verdict(...)       the scorecard's verdict category of one comparison
  selftest()

Outputs (under DIR)
  rows/      rows.csv (every ROWS entry except the route rows, on Full, W16, W16b and both halves, groups "all" and
             "exZEC" where ZEC can be in the universe; fee scenario rows; F), pre_perpetual.csv (L = 1 rows on
             Binance spot 2017-08-17 .. 2019-12-31), per_coin.csv (R0 and S1 at L = 1 on each of the 40 coins, and
             pooled with and without ZEC), trades.csv, stops_2025-10-10.csv, meta.json
  headline/  headline.csv (R0 L = 3, S1 L = 1, F; stocks 20-slot and ETFs 14-slot), benchmarks.csv, equity.csv,
             answer_map.csv, meta.json
  routes/    gate.csv, summary.csv, groups.csv (expected false-pass counts; RH's 24-coin pool also without ZEC),
             accounts.csv, meta.json
  tv/        stats.csv, s1_trades.csv, indicator_trades.csv, meta.json
  scorecard/ scorecard.csv (one row per rule 1-15), scorecard_detail.csv (one row per comparison), meta.json
  explore/   grids.csv, grid_summary.csv, grid_deployments.csv, stocks.csv, stock_tickers.csv, meta.json
  (fcount/   only when F's counts are missing: bb_fit.run(which="fcount") writes them before any engine run here)

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. Windows and halves. Full, W16, W16b (and the pre-perpetual block) are runs that start flat with equity 1, with
   indicators from the full history (bb_engine's start / end): "Each window starts flat with equity 1". The halves
   are halves of the Full sample, not runs ("A trade belongs to the window or half in which entry1 filled"; "A trade
   still open at a window's end is marked"; "its point estimate > 0 in both halves of its sample"): primary half
   rows (half_method "slice of the Full run (primary)") take the Full run's trades whose entry1 falls in the half,
   with their full-run return, exit and open_at_end, and the Full account's daily returns between the half's
   dates (no restart at the boundary), as bb_tests does for every "both halves" condition and for the answer map.
   The engine logs (signals, suppressed exits, ...) are per run and blank on a slice; so is the after-tax CAGR of a
   strategy or indicator account (bb_bench's tax model needs a whole account; buy-and-hold's single-sale tax and
   SPY's are given). Each half is also run on its own, starting flat, as a labelled sensitivity (window
   "<half> (separate run)", half_method "separate run starting flat (sensitivity)"; Conf.half_runs). Stocks: the
   same, on the 2001-2026 run and its own 2001-2013 / 2014-2026 runs.
2. Accounts. Each row's account is bb_engine.assemble with K slots (BTC/ETH/SOL 3; S12 top k: k; S17 4; F its
   universe's K). The primary account has idle cash and margin at 0% (R0 Costs row: "Idle margin earns nothing in
   the primary run (T-bill version reported)"): multiple, CAGR, max drawdown, after-tax CAGR. The Sharpe ratio is
   of daily excess returns of the T-bill account (the portfolio tests' convention: idle cash at the T-bill), with
   the zero-interest Sharpe beside it: the Sharpe of the 0%-cash account's raw daily returns (revision log: "raw
   returns with 0% cash (fidelity 8) are reported"; bb_tests' H2 raw version); the T-bill account's multiple and
   CAGR are reported too. CAGR = multiple^(1 / years) - 1, years = days / 365.25 (crypto: UTC days; stocks:
   calendar days from the session before the first to the last), the convention of bb_bench's after-tax CAGR.
   Sharpe = mean / SD (ddof 1) x sqrt(365) for crypto days, sqrt(252) for sessions.
3. Trade statistics. Hit rate = share of closed positions (not open at the window end) whose net return is > 0 (a
   zero is not a win). Average win / average loss = mean dollar P&L (bb_engine.assemble's pnl_usd; per M for the
   every-signal stock tables) of closed winners over |mean of closed losers|, also per M. The share of > 7-day
   positions that won = closed positions with hold_h > 168 that won. The profit share of >= 3-day positions =
   sum of the net dollar P&L of closed positions with hold_h >= 72 / the sum over all closed positions (reported as
   is when that sum is <= 0); the gross version (winners only) is beside it. Mean trade return and the drift-
   adjusted mean (bb_stats.drift_adjust on the coin's whole-history traded series; the spot series for the spot
   vehicle) use every position, those open at the end included ("counts in P&L"), with the month-clustered
   (entry month, G/(G-1), t at G-1 df) 95% interval and one-sided p for drift-adjusted mean > 0 (p_expl), and the
   one-sided p of the unadjusted mean (p_ret). Every such p is exploratory and Benjamini-Hochberg adjusted within
   its table (p_expl_bh, p_ret_bh; label column p_label), headline.csv and the scorecard's included.
4. ZEC. "exZEC" = the same account with ZEC's positions removed and K unchanged (ZEC's slot holds cash), and the
   trade statistics without ZEC's trades; it is shown for every row whose universe can hold ZEC (S12, S17, F, the
   40-coin pools, the pre-perpetual pool), with zec_in_universe saying whether ZEC was ever in it. S17 without ZEC
   is therefore R0's three coins in a four-slot account (R0 itself is the three-slot version). The scorecard's
   S12 comparisons (rule 5) get the same exZEC twin wherever the universe holds ZEC. The RH route's 24-coin pool
   gets "RH24 exZEC": bb_bench.routes on the 23 coins (a 23-slot pool, as bb_bench builds every group; see 13).
5. Rows. rows/ holds every bb_engine.ROWS entry except the route rows RH_* and CB_* (routes/, priced on spot by
   bb_bench) and PRE_* (pre_perpetual.csv). S12_all_top3(_tradfi) (H1's S12 gate universe at R0's rules) is listed
   too. Fee scenario rows (vip, zero) are run for R0, S1 (the grid row, L = 3), S1_L1 (the headline's S1 at L = 1)
   and F. S19 differs from R0 only in assembly, so it reuses R0's simulations. S3_cross's trade statistics are per
   position before the account-level cross liquidation; its account includes it (cross_liquidation column).
   Engine log counts (signals, ATH-only signals, rule-6 suppressed exits, rule-15 deferrals, deferred entries, L
   caps) are summed over the row's coins. stops_2025-10-10.csv lists the positions of R0, R0_at_S and R0_stress on
   the Full window whose final exit (a stop or a liquidation, also after the TP half) is stamped on 2025-10-10 or
   2025-10-11 UTC. Per-coin results ("per-coin and per-ticker results are descriptive"): R0 and S1 at L = 1 on each
   of the 40 coins as a one-slot account, and pooled over the 40 (trade statistics per M) with and without ZEC.
6. Pre-perpetual block ("L = 1 rows only ... Binance spot 2017-08-17..2019-12-31 for every coin listed then, at spot
   costs, no funding"): PRE_R0_L1, PRE_S1_L1 and the spot-cost versions of S1W_L1 and S20 (the other L = 1 rows), on
   bb_bench.spot_hours frames, for "BTC/ETH/SOL" (three slots; SOL listed in 2020, so its slot is cash) and for every
   coin with a live spot hour in the block (one slot each), with and without ZEC.
7. Headline intervals: multiple, CAGR, Sharpe and max drawdown by bb_stats.block_boot_ci (month blocks, 10,000
   draws); trade count and liquidations by the same month-block bootstrap of the calendar months' counts (months
   without a trade count 0); hit rate, win/loss, the holding shares and the mean returns by bb_stats.cluster_boot_ci
   (entry-month clusters). After-tax CAGR (35% short-term, 20% long-term) by bb_bench's gate conventions
   (bb_bench._acct_tax / _stock_tax on the primary account; buy-and-hold bb_bench.bh_after_tax), SPY's after-tax CAGR
   by bb_bench.spy_hurdle over the same first and last close. Benchmarks: bb_bench.bh_crypto (1/K sleeves, Addendum
   2) and bb_bench.moneyline_perp (K slots) on the same coins and window. For F on an S12 universe (whose coins
   change monthly) bb_bench has no point-in-time benchmark, so its bh_ / ml_ columns are BTC/ETH/SOL's: a stated
   deviation from "the same coins", flagged in headline.csv itself (bench_same_coins False, bench_note). Stocks: the
   20-slot member book and the 14-slot ETF book (seed 20261018, idle cash at the T-bill) against bb_stocks'
   equal-weight benchmarks; trade statistics over every signal (per M).
8. Answer map ("Their full strategy beats holding the coins"): bb_stats.block_boot(stat="logdiff", 1-month blocks,
   10,000 draws) of R0 at L = 3 (three slots) against bb_bench.bh_crypto at 1x on BTC/ETH/SOL, both with idle cash at
   the T-bill (the portfolio tests' convention); stocks: the 20-slot member book against the equal-weight members,
   ETFs: the 14-slot book against the equal-weight ETFs (sessions, 21-session blocks). Full sample and both halves,
   the halves as slices of the full run (choice 1; the same series, slices and bootstrap as bb_tests.beats_holding,
   so the same numbers as verdicts.txt's answer map); above_zero_full_and_both_halves of that method
   (decides_sentence True) is the sentence's condition. The separate-run halves are a labelled sensitivity.
9. F ("F is then reported with every headline ... statistic"): read from results_bb/fcount/ (read_f_cell: the first
   JSON with a key F / chosen / selected naming the cell's bars (R0 daily / S8 4-hour / S16 1-hour, or 1d / 4h / 1h)
   and universe (BTC/ETH/SOL, S12 top 6, S12 top 10), or a CSV with a true is_F / chosen / selected column). When
   the counts are missing, run() first calls bb_fit.run(which="fcount") (the nine W16 tranche counts, "written ...
   before any return is read"), before any engine run of its own, and reads F from what it wrote (Conf.
   fcount_if_missing; with it off, F is skipped loudly: say() and every meta.json).
10. Rule scorecard. Effect of a rule = the rule as coded minus its comparison arm, over BTC/ETH/SOL on the Full window
   (S12: the S12 universe). Trade effect: per-signal paired difference of net return per M (bb_stats.
   paired_signal_diff, union of signals, a skipped signal counts 0; H4: per episode, as bb_tests) with the month-
   clustered 95% interval; the drift-adjusted version beside it. S12 changes the coins, so its effect is the
   difference of the two means with a normal interval from the two clustered SEs (independence assumed). Sleeve
   Sharpe effect: Sharpe of the K-slot account's daily excess returns (idle cash at the T-bill), difference by
   bb_stats.block_boot(stat="sharpe_diff", 1-month blocks), its 95% interval. Verdict of a non-Holm comparison:
   "no-op as coded" if both arms' trades and account returns are identical; else "helps" if the 95% interval of the
   trade effect lies above 0, "hurts" if below, else "no detectable effect" (rule 11, which acts at account level
   only, by the Sharpe interval). A rule with several comparisons is "helps" / "hurts" / "no-op as coded" only if
   every comparison is; else "no detectable effect" (the detail table has each). S12 comparisons whose universe holds
   ZEC also run without ZEC (choice 4); the rule's verdict is from the pre-registered comparisons, the exZEC twins'
   combined verdict is beside it (verdict_descriptive_exZEC). Rules in the Holm family (2 H3, 4 H9, 6 and 15 H8, 7 H4,
   12 H7, 13-14 H6) take the test's verdict (its reporting label) verbatim: from results_bb/verdicts.csv when it is
   at least as new as primary/tests.json, else computed by bb_tests.report itself on a temporary copy of
   primary/tests.json (and controls/inference.json) when tests.json holds all 12 tests without error (nothing is
   written to results_bb by this), else "pending", which meta.json flags (holm_verdicts_pending) and say() reports;
   re-run `--which scorecard` after the report. Their descriptive effects are the tests'
   comparisons (H3: R0 vs S4; H9: R0 vs S2; H8(a): S1W + 72 h minimum hold vs S1W; H8(b): S1W + rule 15 vs S1W; H4:
   S1 close vs touch arm; H7: S1W + rule 12 vs S1W; H6: R0's pair (06:00, 13:00 New York) vs S1; all at L = 3,
   Addendum 2). Rule 9 is "not testable" (built in). Rule 6's row also gives R0's count of suppressed exits.
11. Grids (2024-07-01 .. 2026-10-16, idle cash at the T-bill in every arm as H10): G-B = bb_grid.grid_gb on R0's
   tranches (BTC/ETH/SOL), R0 + G-B account by bb_engine.assemble; G-0 = bb_grid.grid_g0 alone (a benchmark: one
   always-on grid per slot, sized at the slot's sleeve through bb_grid.merge_ga, no R0 positions); the six-slot G-A
   run = R0 on BTC/ETH/SOL/BNB/XRP/DOGE (K = 6) + bb_grid.grid_ga per coin (merge_ga). Each at fee scenarios base,
   vip, zero (R0 and the grid at the same scenario) and with the optimistic touch fill at base. Overlay vs R0 alone:
   mean daily difference of account returns, block bootstrap with H10's 28-day mean block (exploratory p, BH within
   grids.csv); G-0 vs the T-bill: its mean daily excess return. H10's own three-slot G-A rows are added only when
   results_bb/primary/tests.json lacks H10's vip, zero and touch results.
12. Stock extras (bb_stocks): 2x Reg-T = trade-level returns of StockCfg(lev=2) (financing on the borrowed half at
   the T-bill + 2.5 points) and the 20-slot (ETFs 14-slot) book at lev = 2 on the primary candidates (the book
   charges its own borrowed cash); double costs = StockCfg(cost_mult=2); S20 = StockCfg(bars="1w"); 1996-2000 = the
   primary rules on 1996-01-01 .. 2000-12-31 (reported outside every pass rule, with the close-only caveat). The
   user's seven tickers and the 14 ETFs individually: trade statistics of each name (every signal), a one-slot book
   and the name's buy-and-hold (bb_stocks.benchmark_ew_etfs on that name, 60-session warm-up); a user ticker with
   fewer than 20 trades is flagged "not interpreted".
13. Routes: bb_bench.routes with placebo 100: RH, ETF, CB and Stocks with the spot routes (RH, ETF) on the longest
   Binance spot history (spot_route_start 2017-08-17, Addendum 2) and, beside them, RH and ETF on the Full window;
   CB on the Full window (it cannot be extended); Stocks 2001-01-01 .. 2026-10-16. "Results including ZEC are always
   shown next to results without it": bb_bench.ROUTES["RH"] pools ZEC in "RH24", so the RH route is run again on its
   coins without ZEC (on both bases) and that call's RH24 group is kept as "RH24 exZEC" (summary.csv, groups.csv,
   accounts.csv); its per-coin gate rows duplicate the first call's (meta.json checks they are identical) and are
   dropped. bb_bench's engine cache keys spot runs by frame identity, so this second call re-runs the RH engine
   runs and gates (a one-line group in bb_bench.ROUTES would avoid it; run() skips the extra call once that group
   exists).
14. Parallelism: engine runs are grouped by coin and run in a fork process pool (concurrent.futures; joblib is not
   installed), so each worker prepares a coin once; every simulate_coin result is cached for the run (keyed by
   coin, Cfg, window, membership mask, vehicle). Stock runs, grid runs and headline bootstraps are pooled the same
   way. Every engine, grid, stock, benchmark and route run asserts an empty fill audit (RuntimeError otherwise);
   bb_bench's indicator benchmark and the close-only TV cross-check carry no fill audit of their own (bb_bench
   returns an empty list for the former; the latter fills on closes by construction).
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analysis_2026.bb_data as bd          # noqa: E402
import analysis_2026.bb_engine as be        # noqa: E402
import analysis_2026.bb_stats as bs         # noqa: E402

RES = ROOT / "analysis_2026" / "results_bb"
PARTS = ("rows", "headline", "routes", "tv", "scorecard", "explore")
SEED = bs.SEED
ZEC = "ZEC"
EXZEC = " exZEC"                                    # arm-name suffix of a scorecard twin without ZEC (choice 4)
FULL_NAME = "Full"
FULL = ("2020-01-01", "2026-10-16")
SEP_TAG = "(separate run)"                          # window label suffix of a half run on its own (choice 1)
HALF_SLICE = "slice of the Full run (primary)"
HALF_SEP = "separate run starting flat (sensitivity)"
WINDOWS = {"Full": FULL, "W16": ("2025-06-17", "2026-10-16"), "W16b": ("2024-06-30", "2025-10-31"),
           "H2020-2022": ("2020-01-01", "2022-12-31"), "H2023-2026": ("2023-01-01", "2026-10-16")}
HALVES = ("H2020-2022", "H2023-2026")
SINGLE_PATH = ("W16", "W16b")
PRE_WIN = ("2017-08-17", "2019-12-31")
GRID_WIN = ("2024-07-01", "2026-10-16")
GRID_BLOCK = 28.0                                   # H10's mean block (days)
STOCK_WIN = ("2001-01-01", "2026-10-16")
STOCK_HALVES = {"2001-2013": ("2001-01-01", "2013-12-31"), "2014-2026": ("2014-01-01", "2026-10-16")}
STOCK_EARLY = ("1996-01-01", "2000-12-31")
FEES = ("base", "vip", "zero")
FEE_ROWS = ("R0", "S1", "S1_L1")
TICKER_FLOOR = 20                                   # "fewer than 20 trades is reported but not interpreted"
P_LABEL = "exploratory (Benjamini-Hochberg within this table)"
F_BARS = {"1d": "R0", "4h": "S8", "1h": "S16"}
F_UNIV = {"BTC/ETH/SOL": None, "S12 top 6": "S12_top6", "S12 top 10": "S12_top10"}
HOLM_RULES = {2: "H3", 4: "H9", 6: "H8", 7: "H4", 12: "H7", 13: "H6", 14: "H6", 15: "H8"}


# ============================================================================ configuration and data sources
@dataclass
class Conf:
    """What to run (defaults = the pre-registration). The self-test shrinks windows, rows and bootstrap sizes."""
    windows: dict = field(default_factory=lambda: dict(WINDOWS))
    halves: tuple = HALVES
    pre_win: tuple = PRE_WIN
    grid_win: tuple = GRID_WIN
    stock_win: tuple = STOCK_WIN
    stock_halves: dict = field(default_factory=lambda: dict(STOCK_HALVES))
    stock_early: tuple = STOCK_EARLY
    rows: tuple | None = None                       # None = every ROWS entry except route / PRE rows
    fee_rows: tuple = FEE_ROWS
    primary: tuple = tuple(bd.PRIMARY)
    six: tuple = tuple(bd.M1_COINS)
    per_coin: tuple | None = None                   # None = bd.COINS
    pre_coins: tuple | None = None                  # None = every coin with a live spot hour in the block
    B_trade: int = bs.B_TRADE
    B_port: int = bs.B_PORT
    placebo_n: int = 100
    spot_route_start: str = "2017-08-17"
    route_coins: dict | None = None
    stock_route: bool = True
    stock_univ: tuple = ("members", "etfs")
    stock_variants: tuple = ("costs2x", "lev2", "S20", "early")
    tv_syms: tuple | None = None                    # None = bb_bench.TV_SYMS
    f_cell: dict | None = None                      # override of results_bb/fcount (tests)
    fcount_if_missing: bool = True                  # run bb_fit's F counts first when fcount/ lacks them (choice 9)
    half_runs: bool = True                          # also run each half on its own (sensitivity; choice 1)


class Src:
    """Data sources: None = bb_data on disk. hours / minutes: {sym: frame} injected into every engine, grid and
    benchmark call; universes: {row: (coins, K, {sym: month-start membership Series})} for S12-type rows (needed
    when hours are injected); stocks: {"members"|"etfs"|"user": {name: frame}}; tv: {sym: tv_load-shaped frame}."""

    def __init__(self, hours=None, minutes=None, universes=None, mmr=None, stocks=None, tv=None):
        self.hours = hours
        self.minutes = minutes
        self.universes = universes or {}
        self.mmr = mmr
        self.stocks = stocks
        self.tv = tv

    @property
    def injected(self) -> bool:
        return self.hours is not None


_CTX: dict = {"src": Src(), "conf": Conf(), "masks": {}, "univ": {}, "sims": None}   # set before forking
_W: dict = {"frames": {}, "rets": {}, "allowed": {}}   # per-process caches


# ============================================================================ small helpers
def _f(x):
    """JSON-safe float."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return _f(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    return o


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(_jsonable(obj), indent=1, default=str))


def _utc(t) -> pd.Timestamp:
    return bd._utc(t)


def _pool_map(fn, items: list, jobs: int) -> list:
    """fn over items in a fork process pool (inherits _CTX), or in-process for jobs <= 1."""
    if jobs <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ProcessPoolExecutor(max_workers=min(jobs, len(items)), mp_context=mp.get_context("fork")) as ex:
        return list(ex.map(fn, items, chunksize=1))


def _cfg_change(cfg: be.Cfg, base: be.Cfg | None = None) -> str:
    base = base or be.ROWS["R0"]
    d = [f"{f.name}={getattr(cfg, f.name)}" for f in fields(cfg) if getattr(cfg, f.name) != getattr(base, f.name)]
    return "; ".join(d) if d else "(R0)"


P_COLS = {"p_expl": "p_expl_bh", "p_ret": "p_ret_bh"}     # every exploratory p of a trade table (choice 3)


def _bh_col(df: pd.DataFrame, cols: dict | None = None) -> pd.DataFrame:
    """Benjamini-Hochberg within the table for every p column present ({p column: adjusted column}), and the
    exploratory label ("Multiplicity": any p shown for a descriptive row)."""
    hit = False
    for col, out in (cols or P_COLS).items():
        if len(df) and col in df:
            df[out] = bs.bh(pd.to_numeric(df[col], errors="coerce").to_numpy(float))
            hit = True
    if hit:
        df["p_label"] = P_LABEL
    return df


def _between_mask(times, a, b) -> np.ndarray:
    """times within [a, b] (a date-only b covers that day); tz-naive times (stock sessions) are read as UTC."""
    ix = pd.DatetimeIndex(times)
    ix = ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")
    return np.asarray((ix >= _utc(a)) & (ix <= bd._utc_end(b)), bool)


def _between(s: pd.Series, a, b) -> pd.Series:
    return s[_between_mask(s.index, a, b)] if len(s) else s


def win_split(conf: "Conf") -> tuple:
    """(run windows, half slices of the Full run, separate-run halves) as {name: (start, end)} (coding choice 1).
    Without a Full window or halves every window is a run."""
    halves = {h: tuple(conf.windows[h]) for h in conf.halves if h in conf.windows}
    if FULL_NAME not in conf.windows or not halves:
        return dict(conf.windows), {}, {}
    runs = {w: tuple(ab) for w, ab in conf.windows.items() if w not in halves}
    sep = {f"{h} {SEP_TAG}": ab for h, ab in halves.items()} if conf.half_runs else {}
    return runs, halves, sep


def _half_method(wname: str, sl: dict, sep: dict) -> str:
    return HALF_SLICE if wname in sl else HALF_SEP if wname in sep else ""


def _check_audit(audit, what: str) -> None:
    if audit:
        raise RuntimeError(f"fill audit violated ({what}): {len(audit)} violations, e.g. {audit[0]}")


# ============================================================================ statistics on positions and accounts
def _winloss(x: np.ndarray) -> float:
    w, l_ = x[x > 0], x[x < 0]
    return float(w.mean() / abs(l_.mean())) if len(w) and len(l_) else np.nan


def _ci_t(m, se, df):
    if not (np.isfinite(se) and df and df > 0):
        return np.nan, np.nan
    q = float(stats.t.ppf(0.975, df))
    return m - q * se, m + q * se


def trade_stats(T: pd.DataFrame, pnl_col: str | None = "pnl_usd") -> dict:
    """Trade-level statistics of a position table (columns ret, hold_h, open_at_end, n_tranches, entry1_time, and
    optionally ret_adj, liquidated, pnl_col). Definitions: module doc, coding choice 3."""
    n = len(T)
    out = {"n_positions": int(n)}
    keys = ["n_tranches", "n_closed", "n_open_at_end", "liquidations", "hit_rate", "avg_win_loss", "avg_win_loss_m",
            "n_gt7d", "share_gt7d_won", "n_ge3d", "profit_share_ge3d", "profit_share_ge3d_gross", "mean_ret",
            "mean_ret_lo", "mean_ret_hi", "p_ret", "mean_adj", "mean_adj_se", "mean_adj_lo", "mean_adj_hi",
            "p_expl", "G_months", "df"]
    if n == 0:
        out.update({k: (0 if k.startswith("n_") or k in ("liquidations", "G_months", "df") else np.nan)
                    for k in keys})
        return out
    ret = pd.to_numeric(T["ret"], errors="coerce").to_numpy(float)
    adj = pd.to_numeric(T["ret_adj"], errors="coerce").to_numpy(float) if "ret_adj" in T else np.full(n, np.nan)
    oe = T["open_at_end"].astype(bool).to_numpy() if "open_at_end" in T else np.zeros(n, bool)
    hold = pd.to_numeric(T["hold_h"], errors="coerce").to_numpy(float)
    pnl = pd.to_numeric(T[pnl_col], errors="coerce").to_numpy(float) if pnl_col and pnl_col in T else ret
    cl = ~oe
    rc, pc, hc = ret[cl], pnl[cl], hold[cl]
    out["n_tranches"] = int(pd.to_numeric(T["n_tranches"], errors="coerce").fillna(0).sum()) \
        if "n_tranches" in T else 0
    out["n_closed"] = int(cl.sum())
    out["n_open_at_end"] = int(oe.sum())
    out["liquidations"] = int(T["liquidated"].astype(bool).sum()) if "liquidated" in T else 0
    out["hit_rate"] = float((rc > 0).mean()) if len(rc) else np.nan
    out["avg_win_loss"] = _winloss(pc)
    out["avg_win_loss_m"] = _winloss(rc)
    g7 = hc > 168
    out["n_gt7d"] = int(g7.sum())
    out["share_gt7d_won"] = float((rc[g7] > 0).mean()) if g7.any() else np.nan
    g3 = hc >= 72
    out["n_ge3d"] = int(g3.sum())
    tot = float(pc.sum())
    out["profit_share_ge3d"] = float(pc[g3].sum() / tot) if len(pc) and tot != 0 else np.nan
    pos = pc > 0
    gp = float(pc[pos].sum())
    out["profit_share_ge3d_gross"] = float(pc[g3 & pos].sum() / gp) if gp > 0 else np.nan
    months = bs.month_key(T["entry1_time"])
    m, se, _, p, df = bs.cluster_t(ret, months)
    out["mean_ret"] = m
    out["mean_ret_lo"], out["mean_ret_hi"] = _ci_t(m, se, df)
    out["p_ret"] = p
    m, se, _, p, df = bs.cluster_t(adj, months)
    out["mean_adj"], out["mean_adj_se"] = m, se
    out["mean_adj_lo"], out["mean_adj_hi"] = _ci_t(m, se, df)
    out["p_expl"] = p
    out["G_months"] = int(len(np.unique(months[np.isfinite(adj)]))) if np.isfinite(adj).any() else 0
    out["df"] = int(df)
    return out


def trade_intervals(T: pd.DataFrame, pnl_col: str | None = "pnl_usd", B: int = bs.B_TRADE, seed: int = SEED) -> dict:
    """Month-cluster percentile bootstrap intervals (bb_stats.cluster_boot_ci) of the hit rate, average win / loss,
    the share of > 7-day positions that won, the profit share of >= 3-day positions and the mean returns."""
    out = {}
    names = ("hit_rate", "avg_win_loss", "share_gt7d_won", "profit_share_ge3d", "mean_ret", "mean_adj")
    for k in names:
        out[k + "_blo"] = out[k + "_bhi"] = np.nan
    if len(T) == 0 or B <= 0:
        return out
    oe = T["open_at_end"].astype(bool).to_numpy() if "open_at_end" in T else np.zeros(len(T), bool)
    ret = pd.to_numeric(T["ret"], errors="coerce").to_numpy(float)
    pnl = pd.to_numeric(T[pnl_col], errors="coerce").to_numpy(float) if pnl_col and pnl_col in T else ret
    adj = pd.to_numeric(T["ret_adj"], errors="coerce").to_numpy(float) if "ret_adj" in T else np.full(len(T), np.nan)
    hold = pd.to_numeric(T["hold_h"], errors="coerce").to_numpy(float)
    months = bs.month_key(T["entry1_time"])
    cl = ~oe
    rc, pc, hc, mc = ret[cl], pnl[cl], hold[cl], months[cl]

    def _ci(n_rows, clusters, fn):
        if n_rows < 2 or len(np.unique(clusters)) < 2:
            return np.nan, np.nan
        _, lo, hi, nv = bs.cluster_boot_ci(n_rows, clusters, fn, B=B, seed=seed)
        return (lo, hi) if nv else (np.nan, np.nan)

    def _share3(r):
        t = pc[r].sum()
        return pc[r][hc[r] >= 72].sum() / t if t != 0 else np.nan

    def _gt7(r):
        g = hc[r] > 168
        return (rc[r][g] > 0).mean() if g.any() else np.nan

    def _wl(r):
        return _winloss(pc[r])

    fins = {"hit_rate": (len(rc), mc, lambda r: (rc[r] > 0).mean()),
            "avg_win_loss": (len(rc), mc, _wl), "share_gt7d_won": (len(rc), mc, _gt7),
            "profit_share_ge3d": (len(rc), mc, _share3),
            "mean_ret": (len(ret), months, lambda r: np.nanmean(ret[r])),
            "mean_adj": (len(adj), months, lambda r: np.nanmean(adj[r]) if np.isfinite(adj[r]).any() else np.nan)}
    for k, (nr, cls, fn) in fins.items():
        out[k + "_blo"], out[k + "_bhi"] = _ci(nr, cls, fn)
    return out


def _years(ret: pd.Series, kind: str) -> float:
    if kind == "crypto":
        return len(ret) / 365.25
    idx = pd.DatetimeIndex(ret.index)
    return ((idx[-1] - idx[0]).days + 1) / 365.25 if len(idx) else np.nan


def _cagr_from(mult, years):
    m = np.asarray(mult, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(m > 0, 100.0 * (np.maximum(m, 1e-300) ** (1.0 / years) - 1.0), -100.0)


def _sharpe_rows(R, ppy):
    with np.errstate(invalid="ignore", divide="ignore"):
        sd = R.std(axis=1, ddof=1)
        return np.where(sd > 0, R.mean(axis=1) / np.where(sd > 0, sd, 1.0) * math.sqrt(ppy), np.nan)


def account_stats(ret, excess=None, ppy: int = 365, years: float | None = None) -> dict:
    """Multiple, CAGR (%), Sharpe of `excess` (annualized, ddof 1) and max drawdown (%, negative) of a daily simple
    return series (equity floored at 0 upstream)."""
    r = np.asarray(ret, float)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return {"multiple": np.nan, "cagr_pct": np.nan, "sharpe": np.nan, "max_dd_pct": np.nan, "days": 0}
    yrs = years if years is not None else len(r) / 365.25
    mult = float(np.prod(1.0 + r))
    out = {"multiple": mult, "cagr_pct": float(_cagr_from(mult, yrs)) if yrs > 0 else np.nan,
           "max_dd_pct": float(-100.0 * bs.maxdd_fn(r[None, :])[0]), "days": int(len(r))}
    if excess is not None:
        x = np.asarray(excess, float)
        x = x[np.isfinite(x)]
        out["sharpe"] = float(_sharpe_rows(x[None, :], ppy)[0]) if len(x) > 2 else np.nan
    else:
        out["sharpe"] = np.nan
    return out


def account_intervals(ret, excess=None, ppy: int = 365, years: float | None = None, B: int = bs.B_PORT,
                      seed: int = SEED, mean_block: float | None = None) -> dict:
    """95% month-block (stationary, bb_stats.block_boot_ci) percentile intervals of the multiple, CAGR, max drawdown
    (on ret) and Sharpe (on excess)."""
    out = {k: np.nan for k in ("multiple_lo", "multiple_hi", "cagr_pct_lo", "cagr_pct_hi", "max_dd_pct_lo",
                               "max_dd_pct_hi", "sharpe_lo", "sharpe_hi")}
    r = np.asarray(ret, float)
    r = r[np.isfinite(r)]
    if len(r) < 3 or B <= 0:
        return out
    blk = mean_block if mean_block is not None else (bs.MONTH_DAYS if ppy == 365 else bs.MONTH_SESSIONS)
    yrs = years if years is not None else len(r) / 365.25
    for k, fn in (("multiple", bs.multiple_fn), ("cagr_pct", lambda R: _cagr_from(np.prod(1.0 + R, axis=1), yrs)),
                  ("max_dd_pct", lambda R: -100.0 * bs.maxdd_fn(R))):
        _, lo, hi = bs.block_boot_ci(r, fn, blk, B=B, seed=seed)
        out[k + "_lo"], out[k + "_hi"] = lo, hi
    if excess is not None:
        x = np.asarray(excess, float)
        x = x[np.isfinite(x)]
        if len(x) > 2:
            _, lo, hi = bs.block_boot_ci(x, lambda R: _sharpe_rows(R, ppy), blk, B=B, seed=seed)
            out["sharpe_lo"], out["sharpe_hi"] = lo, hi
    return out


def count_interval(times, start, end, B: int = bs.B_PORT, seed: int = SEED) -> tuple:
    """Month-block bootstrap of a count: the calendar months of [start, end] (a month without an event counts 0)
    resampled with replacement (bb_stats.block_boot_ci, one observation per month, mean block 1). Returns
    (count, lo, hi)."""
    months = pd.period_range(pd.Timestamp(_utc(start)).tz_localize(None), pd.Timestamp(_utc(end)).tz_localize(None),
                             freq="M")
    key = months.year * 100 + months.month
    t = pd.DatetimeIndex(pd.to_datetime(times)) if len(times) else pd.DatetimeIndex([])
    if len(t) and t.tz is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    k = pd.Series(t.year * 100 + t.month).value_counts() if len(t) else pd.Series(dtype=float)
    x = np.array([float(k.get(int(m), 0.0)) for m in key])
    if len(x) < 2 or B <= 0:
        return float(x.sum()), np.nan, np.nan
    est, lo, hi = bs.block_boot_ci(x, lambda R: R.sum(axis=1), 1.0, B=B, seed=seed)
    return est, lo, hi


def beats_holding(a: pd.Series, b: pd.Series, kind: str, halves: dict | None = None, B: int = bs.B_PORT,
                  seed: int = SEED) -> dict:
    """The answer map's statistic: mean log growth of a minus b (annualized) with its 95% month-block bootstrap
    interval (bb_stats.block_boot logdiff), on the full sample and on each half {label: (a_half, b_half)}."""
    ppy = 365 if kind == "crypto" else 252
    blk = bs.MONTH_DAYS if kind == "crypto" else bs.MONTH_SESSIONS
    spans = {"full": (a, b)}
    spans.update(halves or {})
    out, ok = {}, True
    for lab, (u, v) in spans.items():
        r = bs.block_boot(u, v, "logdiff", blk, B=B, seed=seed, ppy=ppy)
        lo, hi = r["ci95"]
        out[lab] = {"estimate": r["estimate"], "ci95_lo": lo, "ci95_hi": hi, "T": r["T"], "ruin": r["ruin"]}
        ok = ok and bool(np.isfinite(lo) and lo > 0)
    out["above_zero_full_and_both_halves"] = bool(ok)
    return out


# ============================================================================ F's identity (results_bb/fcount)
_F_KEYS = ("F", "f", "chosen", "selected", "F_cell", "f_cell", "cell_F", "F_choice")
_F_FLAG = ("is_F", "is_f", "F", "chosen", "selected")


def _parse_bars(s: str) -> str | None:
    t = s.lower().replace("_", " ")
    if re.search(r"\bs16\b|\b1h\b|1-hour|1 hour|hourly", t):
        return "1h"
    if re.search(r"\bs8\b|\b4h\b|4-hour|4 hour", t):
        return "4h"
    if re.search(r"\br0\b|\b1d\b|daily|1-day", t):
        return "1d"
    return None


def _parse_univ(s: str) -> str | None:
    t = s.lower().replace("_", " ")
    if re.search(r"top ?10", t):
        return "S12 top 10"
    if re.search(r"top ?6", t):
        return "S12 top 6"
    if re.search(r"btc ?[/-] ?eth ?[/-] ?sol|primary|\bbtc eth sol\b", t):
        return "BTC/ETH/SOL"
    return None


def _parse_cell(v) -> dict | None:
    if isinstance(v, str):
        b, u = _parse_bars(v), _parse_univ(v)
        return {"bars": b, "universe": u or "BTC/ETH/SOL"} if b else None
    if isinstance(v, dict):
        bars = next((v[k] for k in ("bars", "row", "signal_bars", "bar", "freq") if isinstance(v.get(k), str)), None)
        univ = next((v[k] for k in ("universe", "univ", "coins") if isinstance(v.get(k), str)), None)
        if bars is not None:
            b = _parse_bars(bars)
            u = _parse_univ(univ) if univ else "BTC/ETH/SOL"
            if b and u:
                return {"bars": b, "universe": u}
        for k in ("cell", "name", "label", "id"):
            if isinstance(v.get(k), str):
                c = _parse_cell(v[k])
                if c:
                    return c
    return None


def _find_f(obj, depth: int = 0) -> dict | None:
    if depth > 6:
        return None
    if isinstance(obj, dict):
        for k in _F_KEYS:
            if k in obj and not isinstance(obj[k], bool):
                c = _parse_cell(obj[k])
                if c:
                    return c
        if any(obj.get(k) is True for k in _F_FLAG):
            c = _parse_cell(obj)
            if c:
                return c
        for v in obj.values():
            if isinstance(v, (dict, list)):
                c = _find_f(v, depth + 1)
                if c:
                    return c
    elif isinstance(obj, list):
        for v in obj:
            c = _find_f(v, depth + 1)
            if c:
                return c
    return None


def read_f_cell(out_dir) -> tuple:
    """F's cell {"bars": "1d"|"4h"|"1h", "universe": "BTC/ETH/SOL"|"S12 top 6"|"S12 top 10"} from
    <out_dir>/fcount/ (coding choice 9), or (None, why)."""
    d = Path(out_dir) / "fcount"
    if not d.exists():
        return None, f"{d} not found: F skipped (bb_fit writes F's counts there)"
    for p in sorted(d.glob("*.json")):
        try:
            J = json.loads(p.read_text())
        except (ValueError, OSError):
            continue
        c = _find_f(J)
        if c:
            return c, f"F from {p.name}"
    for p in sorted(d.glob("*.csv")):
        try:
            C = pd.read_csv(p)
        except (ValueError, OSError):
            continue
        for k in _F_FLAG:
            if k in C.columns:
                sel = C[C[k].astype(str).str.lower().isin(["true", "1", "yes"])]
                if len(sel) == 1:
                    c = _parse_cell({kk: str(vv) for kk, vv in sel.iloc[0].items()})
                    if c:
                        return c, f"F from {p.name}"
    return None, f"{d} holds no F cell in a readable form: F skipped"


def ensure_f_cell(out_dir, conf: "Conf", src: "Src", jobs: int = 4, say=print) -> tuple:
    """F's nine W16 tranche counts by bb_fit.run(which="fcount") (the pre-registration: "the engine writes the nine
    counts to results_bb/ before any return is read"), then F's cell as read_f_cell reads it (coding choice 9). With
    injected data the same frames, S12 universes and W16 window go to bb_fit. Raises if no F can be read after it."""
    from analysis_2026 import bb_fit
    fsrc = None
    if src.injected:
        fsrc = bb_fit.Src(hours=src.hours, minutes=src.minutes, universes=dict(src.universes),
                          primary=tuple(conf.primary),
                          windows={"W16": tuple(conf.windows["W16"])} if "W16" in conf.windows else None,
                          mmr=None if src.mmr is None else {s: src.mmr for s in src.hours})
    say("bb_desc: F's counts not found; running bb_fit's fcount first (no return is read)")
    bb_fit.run(out_dir, which="fcount", jobs=jobs, src=fsrc, say=say)
    cell, note = read_f_cell(out_dir)
    if cell is None:
        raise RuntimeError(f"bb_desc: bb_fit's fcount ran but F is still unreadable: {note}")
    return cell, f"{note} (written by bb_fit.run_fcount before this run's engine runs)"


def f_spec(cell: dict) -> tuple:
    """(name, Cfg, universe row key or None) of F's cell."""
    cfg = be.ROWS[F_BARS[cell["bars"]]]
    return f"F ({F_BARS[cell['bars']]} {cell['bars']} x {cell['universe']})", cfg, F_UNIV[cell["universe"]]


# ============================================================================ universes and simulation jobs
def universe(row: str | None, conf: Conf, src: Src) -> tuple:
    """(coins, K, {sym: membership key or None}) of a ROWS entry (None / absent = BTC/ETH/SOL)."""
    memo = _CTX["univ"]
    if row in memo:
        return memo[row]
    memo[row] = _universe(row, conf, src)
    return memo[row]


def _universe(row: str | None, conf: Conf, src: Src) -> tuple:
    if row is not None and row in src.universes:
        coins, K, masks = src.universes[row]
        return list(coins), int(K), {s: (("inj", row) if s in masks else None) for s in coins}
    u = be.ROW_UNIVERSE.get(row) if row is not None else None
    if isinstance(u, tuple) and u[0] == "s12":
        if src.injected:
            raise KeyError(f"{row}: injected hours need Src.universes[{row!r}]")
        _, pool, k, tradfi = u
        coins = be.row_coins(row)
        return coins, int(k), {s: ("s12", pool, int(k), bool(tradfi)) for s in coins}
    if isinstance(u, list):
        return list(u), len(u), {s: None for s in u}
    return list(conf.primary), len(conf.primary), {s: None for s in conf.primary}


def _sim_cfg(cfg: be.Cfg) -> be.Cfg:
    """rule11 acts in assembly only (bb_engine Cfg), so simulations share R0's when only it differs."""
    return replace(cfg, rule11=True) if not cfg.rule11 else cfg


def sim_key(sym, cfg, start, end, akey=None, vehicle="perp") -> tuple:
    c = _sim_cfg(cfg)
    return (sym, c, str(start), str(end), akey, vehicle, c.margin == "cross")


def _frame(sym: str, vehicle: str):
    """Worker-cached frame: None (disk perpetual) or the injected / spot frame."""
    k = (sym, vehicle)
    if k not in _W["frames"]:
        src = _CTX["src"]
        base = None if src.hours is None else src.hours[sym]
        if vehicle == "spot":
            from analysis_2026.bb_bench import spot_hours
            base = spot_hours(bd.coin_hours(sym) if base is None else base)
        _W["frames"][k] = base
    return _W["frames"][k]


def _rets(sym: str, vehicle: str) -> pd.Series:
    k = (sym, vehicle)
    if k not in _W["rets"]:
        H = _frame(sym, vehicle)
        _W["rets"][k] = bs.coin_returns(sym) if H is None else bs.returns_from_hours(H)
    return _W["rets"][k]


def _allowed(sym: str, akey):
    if akey is None:
        return None
    if akey not in _W["allowed"]:
        _W["allowed"][akey] = {}
    cache = _W["allowed"][akey]
    if sym not in cache:
        if (akey, sym) in _CTX["masks"]:                      # computed once in the parent (Sims.need)
            cache[sym] = _CTX["masks"][(akey, sym)]
        elif akey[0] == "s12":
            _, pool, k, tradfi = akey
            cache[sym] = be.s12_allowed(sym, k, pool, tradfi=tradfi)
        else:
            cache[sym] = _CTX["src"].universes[akey[1]][2][sym]
    return cache[sym]


_LOG_KEYS = ("signals", "ath_only_signals", "rule6_suppressed", "rule15_not_acted", "deferred_entries", "l_capped",
             "liquidations", "positions", "tranches", "recheck_failed", "skipped_open_at_or_below_S")


def _empty_sim(sym: str) -> dict:
    return {"sym": sym, "trades": pd.DataFrame(columns=["sym", "pos", "signal_day", "entry1_time", "exit_time", "ret",
                                                        "ret_adj", "drift", "hold_h", "open_at_end", "n_tranches",
                                                        "liquidated", "side", "L_used"]),
            "daily_mtm": pd.DataFrame(columns=["pos", "time", "mtm", "margin", "notional", "sym"]),
            "expo": pd.DataFrame(columns=["pos", "time", "notional", "sym", "pnl_lo", "mm"]), "log": {"empty": 1}}


def _sim_one(key: tuple) -> dict:
    sym, cfg, start, end, akey, vehicle, detail = key
    src = _CTX["src"]
    kw = {}
    H = _frame(sym, vehicle)
    if H is not None:
        kw["hours"] = H
        if vehicle == "perp" and src.minutes is not None and sym in src.minutes:
            kw["minutes"] = src.minutes[sym]
    if src.mmr is not None:
        kw["mmr"] = src.mmr
    try:
        r = be.simulate_coin(sym, cfg, start, end, entry_allowed=_allowed(sym, akey), detail=detail, **kw)
    except ValueError as e:                    # a coin with no hour in the window holds no position
        if "empty window" not in str(e):
            raise
        return _empty_sim(sym)
    _check_audit(r["fills_audit"], f"{sym} {_cfg_change(cfg)} {start}..{end} {vehicle}")
    T = r["trades"].copy()
    if len(T):
        adj = bs.drift_adjust(T, r["expo"], {sym: _rets(sym, vehicle)}, parts=True)
        T["ret_adj"] = adj["ret_adj"].to_numpy(float)
        T["drift"] = adj["drift"].to_numpy(float)
    else:
        T["ret_adj"] = pd.Series(dtype=float)
        T["drift"] = pd.Series(dtype=float)
    out = {"sym": sym, "trades": T, "daily_mtm": r["daily_mtm"],
           "log": {k: int(r["log"].get(k, 0)) for k in _LOG_KEYS}}
    if detail:
        out["expo"] = r["expo"]
    return out


def _sig_order(key) -> tuple:
    c = key[1]
    return (c.bars, c.bb_n, c.bb_k, c.near_high, c.squeeze, c.direction, c.entry_mode, str(c), key[2])


def _coin_task(args) -> list:
    sym, vehicle, keys = args
    return [(k, _sim_one(k)) for k in sorted(keys, key=_sig_order)]


class Sims:
    """The run's simulate_coin cache (coding choice 14)."""

    def __init__(self, jobs: int):
        self.jobs = jobs
        self.cache: dict = {}
        self.n_runs = 0

    def need(self, keys) -> None:
        todo = sorted({k for k in keys if k not in self.cache}, key=lambda k: (k[0], k[5]))
        if not todo:
            return
        for k in todo:                                       # S12 membership masks, once, before forking
            ak = k[4]
            if ak is not None and ak[0] == "s12" and (ak, k[0]) not in _CTX["masks"]:
                _CTX["masks"][(ak, k[0])] = be.s12_allowed(k[0], ak[2], ak[1], tradfi=ak[3])
        groups: dict = {}
        for k in todo:
            groups.setdefault((k[0], k[5]), []).append(k)
        # heavy coins first: hourly bars cost the most, then the number of runs
        items = sorted(((s, v, ks) for (s, v), ks in groups.items()),
                       key=lambda x: -sum({"1h": 20, "4h": 5}.get(k[1].bars, 1) for k in x[2]))
        for res in _pool_map(_coin_task, items, self.jobs):
            for k, r in res:
                self.cache[k] = r
                self.n_runs += 1

    def get(self, key) -> dict:
        if key not in self.cache:
            self.need([key])
        return self.cache[key]


@dataclass
class Spec:
    """A crypto account: name, Cfg, coins, K, membership keys, vehicle."""
    name: str
    cfg: be.Cfg
    coins: list
    K: int
    akeys: dict
    vehicle: str = "perp"
    universe_row: str | None = None

    def keys(self, start, end) -> list:
        return [sim_key(s, self.cfg, start, end, self.akeys.get(s), self.vehicle) for s in self.coins]

    def results(self, sims: Sims, start, end, drop=()) -> dict:
        return {s: sims.get(k) for s, k in zip(self.coins, self.keys(start, end)) if s not in drop}


def account(res: dict, cfg: be.Cfg, start, end, K: int, idle_tbill: bool) -> dict:
    """bb_engine.assemble over the given per-coin results with K slots."""
    return be.assemble(res, cfg, start, end, idle_tbill=idle_tbill, k_slots=K)


def _trades_of(acct: dict) -> pd.DataFrame:
    T = acct["trades"]
    return T if len(T) else T.reindex(columns=list(T.columns) + ["pnl_usd", "ret", "ret_adj", "hold_h", "open_at_end",
                                                                  "n_tranches", "entry1_time", "liquidated"])


def _log_sum(res: dict) -> dict:
    out = {k: 0 for k in _LOG_KEYS}
    for r in res.values():
        for k in _LOG_KEYS:
            out[k] += int(r.get("log", {}).get(k, 0))
    return out


def account_record(a0: dict, a1: dict, T: pd.DataFrame, start=None, end=None) -> dict:
    """A table row's account and trade statistics (coding choices 2, 3) from the 0%-cash account a0, the T-bill
    account a1 and the position table T; with start / end, of the half [start, end] as a slice of that run (choice
    1): the daily returns between the dates and the positions whose entry1 falls in them."""
    cl = a0["cross_liquidation"]
    if start is None:
        r0, r1, x1, Tw = a0["ret"], a1["ret"], a1["excess"], T
        e_avg, e_pk = a0["exposure_avg"], a0["exposure_peak"]
    else:
        r0, r1, x1 = (_between(s, start, end) for s in (a0["ret"], a1["ret"], a1["excess"]))
        Tw = T[_between_mask(T["entry1_time"], start, end)] if len(T) else T
        e = _between(a0["exposure"], start, end)
        e_avg, e_pk = (float(e.mean()), float(e.max())) if len(e) else (np.nan, np.nan)
        if cl is not None and not _between_mask([cl], start, end)[0]:
            cl = None
    s0 = account_stats(r0, r0)                          # zero-interest Sharpe: raw 0%-cash returns (choice 2)
    s1 = account_stats(r1, x1)
    rec = {"multiple": s0["multiple"], "cagr_pct": s0["cagr_pct"], "max_dd_pct": s0["max_dd_pct"],
           "sharpe": s1["sharpe"], "sharpe_zero_interest": s0["sharpe"], "multiple_tbill": s1["multiple"],
           "cagr_tbill_pct": s1["cagr_pct"], "exposure_avg": e_avg, "exposure_peak": e_pk,
           "cross_liquidation": str(cl) if cl is not None else "", "days": s0["days"]}
    rec.update(trade_stats(Tw, "pnl_usd"))
    return rec


def slice_record(a0: dict, a1: dict, T: pd.DataFrame, start, end) -> tuple:
    """(row, positions) of the half [start, end] of a run (coding choice 1): account_record on the slice; engine
    logs and after-tax figures are per run and left blank."""
    Tw = T[_between_mask(T["entry1_time"], start, end)] if len(T) else T
    return account_record(a0, a1, T, start, end), Tw


def crypto_record(spec: Spec, res: dict, start, end) -> tuple:
    """One table row (account + trade statistics) and the primary account and trades."""
    a0 = account(res, spec.cfg, start, end, spec.K, False)
    a1 = account(res, spec.cfg, start, end, spec.K, True)
    T = _trades_of(a0)
    rec = account_record(a0, a1, T)
    rec.update({"log_" + k: v for k, v in _log_sum(res).items()})
    return rec, a0, a1, T


# ============================================================================ part: rows
def _row_names(conf: Conf) -> list:
    if conf.rows is not None:
        return list(conf.rows)
    return [k for k in be.ROWS if not k.startswith(("RH_", "CB_", "PRE_"))]


def _row_specs(conf: Conf, src: Src, f_cell: dict | None) -> list:
    """(label, Spec) for every row of rows.csv."""
    out = []
    for name in _row_names(conf):
        cfg = be.ROWS[name]
        try:
            coins, K, ak = universe(name, conf, src)
        except KeyError:
            continue
        out.append((name, Spec(name, cfg, coins, K, ak, universe_row=name)))
    for name in conf.fee_rows:
        for fee in FEES[1:]:
            cfg = replace(be.ROWS[name], fees=fee)
            coins, K, ak = universe(name, conf, src)
            out.append((f"{name}@{fee}", Spec(f"{name}@{fee}", cfg, coins, K, ak, universe_row=name)))
    if f_cell:
        nm, cfg, urow = f_spec(f_cell)
        try:
            coins, K, ak = universe(urow, conf, src)
            for fee in FEES:
                lab = "F" if fee == "base" else f"F@{fee}"
                out.append((lab, Spec(lab, replace(cfg, fees=fee), coins, K, ak, universe_row=urow)))
        except KeyError:
            pass
    return out


def _zec_row(spec: Spec) -> bool:
    r = spec.universe_row or ""
    return r.startswith("S12") or r == "S17" or ZEC in spec.coins


def _pre_coins(conf: Conf, src: Src) -> list:
    if conf.pre_coins is not None:
        return list(conf.pre_coins)
    from analysis_2026.bb_bench import spot_hours
    a, b = _utc(conf.pre_win[0]), bd._utc_end(conf.pre_win[1])
    out = []
    for s in bd.COINS:
        H = spot_hours(bd.coin_hours(s) if src.hours is None else src.hours[s])
        m = (H.index >= a) & (H.index <= b) & (H["trades"].to_numpy() > 0)
        if m.any():
            out.append(s)
    return out


PRE_ROWS = {"PRE_R0_L1": be.ROWS["PRE_R0_L1"], "PRE_S1_L1": be.ROWS["PRE_S1_L1"],
            "PRE_S1W_L1": replace(be.ROWS["S1W_L1"], spot_costs=True),
            "PRE_S20": replace(be.ROWS["S20"], spot_costs=True)}


def _pre_specs(conf: Conf, src: Src) -> list:
    pc = _pre_coins(conf, src)
    out = []
    for name, cfg in PRE_ROWS.items():
        out.append((name, "BTC/ETH/SOL", Spec(name, cfg, list(conf.primary), len(conf.primary),
                                              {s: None for s in conf.primary}, vehicle="spot")))
        if pc:
            out.append((name, "all listed", Spec(name, cfg, pc, len(pc), {s: None for s in pc}, vehicle="spot",
                                                 universe_row="pool")))
    return out


def _per_coin_specs(conf: Conf) -> list:
    coins = list(conf.per_coin) if conf.per_coin is not None else list(bd.COINS)
    out = []
    for name in ("R0", "S1_L1"):
        for s in coins:
            out.append((name, s, Spec(name, be.ROWS[name], [s], 1, {s: None})))
    return out


def _run_windows(conf: Conf) -> dict:
    """The windows that are engine runs: Full, W16, W16b and the separate-run halves (choice 1)."""
    runs, _, sep = win_split(conf)
    return {**runs, **sep}


def rows_keys(conf: Conf, src: Src, f_cell) -> list:
    keys = []
    wins = _run_windows(conf)
    for _, sp in _row_specs(conf, src, f_cell):
        for a, b in wins.values():
            keys += sp.keys(a, b)
    for _, _, sp in _pre_specs(conf, src):
        keys += sp.keys(*conf.pre_win)
    for _, _, sp in _per_coin_specs(conf):
        for a, b in wins.values():
            keys += sp.keys(a, b)
    return keys


_TRADE_COLS = ["sym", "pos", "signal_day", "entry1_time", "exit_time", "exit_reason", "side", "n_tranches", "L_used",
               "ret", "ret_adj", "M", "pnl_usd", "hold_h", "open_at_end", "liquidated", "atH_only"]


def _record_job(job: tuple) -> tuple:
    """crypto_record of one (spec, window, dropped coins) in a worker, and the half slices of that run
    ({half: (start, end)}; choice 1); the simulation cache is inherited (fork)."""
    sp, a, b, drop, keep, halves = job
    sims = _CTX["sims"]
    res = {s: v for s, v in sp.results(sims, a, b).items() if s not in drop}
    rec, a0, a1, T = crypto_record(sp, res, a, b)
    sl = []
    for h, (x, y) in halves.items():
        rh, Th = slice_record(a0, a1, T, x, y)
        sl.append((h, x, y, rh, Th.reindex(columns=_TRADE_COLS) if keep and len(Th) else None))
    return rec, (T.reindex(columns=_TRADE_COLS) if keep and len(T) else None), len(res), sl


def _records(jobs_: list, sims: Sims, jobs: int) -> list:
    _CTX["sims"] = sims
    try:
        return _pool_map(_record_job, jobs_, jobs)
    finally:
        _CTX["sims"] = None


def part_rows(out: Path, sims: Sims, conf: Conf, src: Src, f_cell, f_note: str, say=print, jobs: int = 1) -> dict:
    t0 = time.time()
    d = out / "rows"
    d.mkdir(parents=True, exist_ok=True)
    _, sl, sep = win_split(conf)
    wins = _run_windows(conf)
    first_w = next(iter(wins))
    # sensitivity rows on every window, with and without ZEC; the halves as slices of the Full run (choice 1)
    meta_, jobs_ = [], []
    for label, sp in _row_specs(conf, src, f_cell):
        for wname, (a, b) in wins.items():
            groups = [("all", ())] + ([("exZEC", (ZEC,))] if _zec_row(sp) else [])
            for gname, drop in groups:
                meta_.append((label, sp, wname, a, b, gname))
                jobs_.append((sp, a, b, drop, gname == "all", sl if wname == FULL_NAME else {}))
    recs, trades, stops = [], [], []
    for (label, sp, wname, a, b, gname), (rec, T, n, slices) in zip(meta_, _records(jobs_, sims, jobs)):
        head = {"row": label, "cfg_change": _cfg_change(sp.cfg)}
        tail = {"group": gname, "K": sp.K, "n_coins": n, "zec_in_universe": ZEC in sp.coins}
        recs.append({**head, "window": wname, "start": a, "end": b, "single_path": wname in SINGLE_PATH,
                     "half_method": _half_method(wname, sl, sep), **tail, **rec})
        for h, x, y, rh, _ in slices:
            recs.append({**head, "window": h, "start": x, "end": y, "single_path": False, "half_method": HALF_SLICE,
                         **tail, **rh})
        if T is not None:
            trades.append(T.assign(row=label, window=wname))
            if label in ("R0", "R0_at_S", "R0_stress") and wname == first_w:
                x = T[T["exit_reason"].astype(str).str.contains("stop|liq") &
                      pd.DatetimeIndex(T["exit_time"]).tz_convert("UTC").normalize().isin(
                          pd.DatetimeIndex(["2025-10-10", "2025-10-11"], tz="UTC"))]
                if len(x):
                    stops.append(x.assign(row=label, window=wname))
    R = _bh_col(pd.DataFrame(recs))
    R.to_csv(d / "rows.csv", index=False)
    (pd.concat(trades, ignore_index=True) if trades else pd.DataFrame(columns=_TRADE_COLS)).to_csv(
        d / "trades.csv", index=False)
    (pd.concat(stops, ignore_index=True) if stops else pd.DataFrame(columns=_TRADE_COLS + ["row", "window"])).to_csv(
        d / "stops_2025-10-10.csv", index=False)
    # pre-perpetual block
    a, b = conf.pre_win
    meta_, jobs_ = [], []
    for name, gname, sp in _pre_specs(conf, src):
        groups = [(gname, ())] + ([(gname + " exZEC", (ZEC,))] if sp.universe_row == "pool" else [])
        for g2, drop in groups:
            meta_.append((name, g2, sp, drop))
            jobs_.append((sp, a, b, drop, False, {}))
    precs = []
    for (name, g2, sp, drop), (rec, _, n, _) in zip(meta_, _records(jobs_, sims, jobs)):
        precs.append({"row": name, "cfg_change": _cfg_change(sp.cfg), "window": "pre-perpetual", "start": a,
                      "end": b, "group": g2, "K": sp.K, "n_coins": n,
                      "coins": " ".join(sorted(c for c in sp.coins if c not in drop)),
                      "zec_in_universe": ZEC in sp.coins, "vehicle": "Binance spot (bb_bench.spot_hours)", **rec})
    P = _bh_col(pd.DataFrame(precs))
    P.to_csv(d / "pre_perpetual.csv", index=False)
    # per coin (each coin its own one-slot account) and the 40-coin pool with and without ZEC
    meta_, jobs_ = [], []
    for name, s_, sp in _per_coin_specs(conf):
        for wname, (a, b) in wins.items():
            meta_.append((name, s_, wname))
            jobs_.append((sp, a, b, (), True, sl if wname == FULL_NAME else {}))
    crecs, pools = [], {}
    for (name, s_, wname), (rec, T, _, slices) in zip(meta_, _records(jobs_, sims, jobs)):
        crecs.append({"row": name, "sym": s_, "window": wname, "single_path": wname in SINGLE_PATH,
                      "half_method": _half_method(wname, sl, sep), **rec})
        if T is not None:
            pools.setdefault((name, wname), []).append(T)
        for h, _, _, rh, Th in slices:
            crecs.append({"row": name, "sym": s_, "window": h, "single_path": False, "half_method": HALF_SLICE, **rh})
            if Th is not None:
                pools.setdefault((name, h), []).append(Th)
    for (name, wname), Ts in pools.items():
        T = pd.concat(Ts, ignore_index=True)
        for g, TT in (("pool", T), ("pool exZEC", T[T["sym"] != ZEC])):
            crecs.append({"row": name, "sym": g, "window": wname, "single_path": wname in SINGLE_PATH,
                          "half_method": _half_method(wname, sl, sep), **trade_stats(TT, None)})
    C = _bh_col(pd.DataFrame(crecs))
    C.to_csv(d / "per_coin.csv", index=False)
    meta = {"seconds": round(time.time() - t0, 1), "rows": int(len(R)), "pre_perpetual_rows": int(len(P)),
            "per_coin_rows": int(len(C)), "windows": conf.windows, "run_windows": wins, "half_slices": sl,
            "half_methods": {HALF_SLICE: "the Full run's positions with entry1 in the half and its daily returns "
                                         "between the half's dates (bb_tests' halves)",
                             HALF_SEP: "the half run on its own, starting flat (sensitivity)"},
            "F": f_note, "F_included": f_cell is not None, "fill_audit_violations": 0,
            "pre_coins": sorted({s for _, _, sp in _pre_specs(conf, src) for s in sp.coins}),
            "p_label": P_LABEL}
    _write_json(d / "meta.json", meta)
    say(f"  rows: {len(R)} rows x windows x groups, {len(P)} pre-perpetual, {len(C)} per-coin rows "
        f"[{meta['seconds']:.0f}s]")
    return meta


# ============================================================================ part: headline
def _headline_specs(conf: Conf, src: Src, f_cell) -> list:
    out = [("R0 (L=3)", Spec("R0", be.ROWS["R0"], list(conf.primary), len(conf.primary),
                             {s: None for s in conf.primary})),
           ("S1 (L=1)", Spec("S1_L1", be.ROWS["S1_L1"], list(conf.primary), len(conf.primary),
                             {s: None for s in conf.primary}))]
    if f_cell:
        nm, cfg, urow = f_spec(f_cell)
        try:
            coins, K, ak = universe(urow, conf, src)
            out.append((nm, Spec("F", cfg, coins, K, ak, universe_row=urow)))
        except KeyError:
            pass
    return out


def headline_keys(conf: Conf, src: Src, f_cell) -> list:
    keys = []
    wins = _run_windows(conf)
    for _, sp in _headline_specs(conf, src, f_cell):
        for a, b in wins.values():
            keys += sp.keys(a, b)
    return keys


def _hl_item(p: dict) -> dict:
    """Intervals of one headline item (runs in a worker): multiple, CAGR and max drawdown of the primary account, the
    Sharpe of the T-bill account's excess returns and, for crypto, the zero-interest Sharpe of the 0%-cash account's
    raw returns (choice 2); counts; trade statistics."""
    c = _CTX["conf"]
    ppy = p["ppy"]
    blk = bs.MONTH_DAYS if ppy == 365 else bs.MONTH_SESSIONS
    out = {}
    iv0 = account_intervals(p["ret0"], p["ret0"] if p["zero"] else None, ppy, p["years"], B=c.B_port, mean_block=blk)
    out.update({k: v for k, v in iv0.items() if not k.startswith("sharpe")})
    iv1 = account_intervals(p["ret1"], p["ex1"], ppy, p["years"], B=c.B_port, mean_block=blk)
    out.update({"sharpe_lo": iv1["sharpe_lo"], "sharpe_hi": iv1["sharpe_hi"],
                "sharpe_zero_interest_lo": iv0["sharpe_lo"], "sharpe_zero_interest_hi": iv0["sharpe_hi"],
                "multiple_tbill_lo": iv1["multiple_lo"], "multiple_tbill_hi": iv1["multiple_hi"]})
    T = p["T"]
    _, lo, hi = count_interval(T["entry1_time"] if len(T) else [], p["start"], p["end"], B=c.B_port)
    out["n_positions_lo"], out["n_positions_hi"] = lo, hi
    liq = T[T["liquidated"].astype(bool)] if len(T) and "liquidated" in T else T.iloc[:0]
    _, lo, hi = count_interval(liq["exit_time"] if len(liq) else [], p["start"], p["end"], B=c.B_port)
    out["liquidations_lo"], out["liquidations_hi"] = lo, hi
    out.update(trade_intervals(T, p["pnl_col"], B=c.B_trade))
    return out


def _bench_stats(ret, excess, kind="crypto", years=None) -> dict:
    s = account_stats(ret, excess, 365 if kind == "crypto" else 252, years)
    return {k: s[k] for k in ("multiple", "cagr_pct", "sharpe", "max_dd_pct")}


def _spy_cagr_tax(first, last) -> float:
    from analysis_2026.bb_bench import spy_hurdle, _naive
    try:
        c, _ = spy_hurdle(_naive(pd.DatetimeIndex([pd.Timestamp(first), pd.Timestamp(last)])))
        return float(c)
    except Exception:                          # noqa: BLE001  (outside the SPX series' dates)
        return np.nan


BENCH_NOTE = ("not the same coins: BTC/ETH/SOL's buy-and-hold and indicator (bb_bench has no point-in-time S12 "
              "benchmark; coding choice 7)")
SLICE_NOTE = ("half as a slice of the Full run: after-tax CAGR of the strategy and the indicator need a whole account "
              "(bb_bench's tax model), see the separate-run half")


def _crypto_bench(bb, bcoins: list, a, b, src: Src) -> dict:
    """bb_bench.bh_crypto (1/K sleeves) and moneyline_perp (K slots) on bcoins over [a, b], at 0% and T-bill cash."""
    bh0 = bb.bh_crypto(bcoins, a, b, idle_tbill=False, hours=src.hours)
    bh1 = bb.bh_crypto(bcoins, a, b, idle_tbill=True, hours=src.hours)
    ml0 = bb.moneyline_perp(bcoins, a, b, k_slots=len(bcoins), idle_tbill=False, hours=src.hours)
    ml1 = bb.moneyline_perp(bcoins, a, b, k_slots=len(bcoins), idle_tbill=True, hours=src.hours)
    for s_, rr in ml0.get("coins", {}).items():
        _check_audit(rr.get("fills_audit", []), f"moneyline {s_} {a}..{b}")
    return {"bh0": bh0["ret"], "bh1": bh1["ret"], "bh1x": bh1["excess"], "ml0": ml0["ret"], "ml1x": ml1["excess"],
            "ml_tax": bb._acct_tax(ml0)["cagr_tax"], "eq_bh": bh0["equity"], "eq_ml": ml0["equity"]}


def _bench_cols(bb, bc: dict, first, last, slc=None) -> dict:
    """bh_ / ml_ statistics of a window's benchmarks, or of the slice slc = (start, end) of the Full window's."""
    f = (lambda s: s) if slc is None else (lambda s: _between(s, *slc))
    bh = _bench_stats(f(bc["bh0"]), f(bc["bh1x"]))
    bm = bh["multiple"]
    bh["cagr_tax_pct"] = bb._cagr(bb.bh_after_tax(bm), first, last) if np.isfinite(bm) else np.nan
    ml = _bench_stats(f(bc["ml0"]), f(bc["ml1x"]))
    ml["cagr_tax_pct"] = bc["ml_tax"] if slc is None else np.nan
    return {"bh": bh, "ml": ml}


def part_headline(out: Path, sims: Sims, conf: Conf, src: Src, f_cell, f_note, stock_res: dict, jobs: int,
                  say=print) -> dict:
    from analysis_2026 import bb_bench as bb
    t0 = time.time()
    d = out / "headline"
    d.mkdir(parents=True, exist_ok=True)
    _, sl, sep = win_split(conf)
    wins = _run_windows(conf)
    day = pd.Timedelta("1D")
    items, base, eq_rows, bench_rows = [], [], [], []
    bench_cache: dict = {}
    bench_done: set = set()
    accts1: dict = {}
    for strat, sp in _headline_specs(conf, src, f_cell):
        same = not (sp.universe_row and sp.universe_row.startswith("S12"))
        bcoins = list(sp.coins) if same else list(conf.primary)
        for wname, (a, b) in wins.items():
            res = sp.results(sims, a, b)
            bkey = (tuple(bcoins), wname)
            if bkey not in bench_cache:
                bench_cache[bkey] = _crypto_bench(bb, bcoins, a, b, src)
                for nm_, e_ in (("buy-and-hold", bench_cache[bkey]["eq_bh"]),
                                ("moneyline_ref", bench_cache[bkey]["eq_ml"])):
                    eq_rows.append(pd.DataFrame({"series": nm_, "group": "/".join(bcoins), "window": wname,
                                                 "day": e_.index, "equity": e_.to_numpy()}))
            bc = bench_cache[bkey]
            groups = [("all", ())] + ([("exZEC", (ZEC,))] if _zec_row(sp) else [])
            for gname, drop in groups:
                r = {s: v for s, v in res.items() if s not in drop}
                rec, a0, a1, T = crypto_record(sp, r, a, b)
                spans = [(wname, a, b, None, rec, T, a0["ret"], a1["ret"], a1["excess"],
                          a0["equity"].index[0] - day, a0["equity"].index[-1], bb._acct_tax(a0)["cagr_tax"])]
                if wname == FULL_NAME:                 # the halves: slices of the Full run (choice 1)
                    for h, (x, y) in sl.items():
                        rh, Th = slice_record(a0, a1, T, x, y)
                        r0h = _between(a0["ret"], x, y)
                        if len(r0h):
                            spans.append((h, x, y, (x, y), rh, Th, r0h, _between(a1["ret"], x, y),
                                          _between(a1["excess"], x, y), r0h.index[0] - day, r0h.index[-1] + day,
                                          np.nan))
                for wn, x, y, slc, rr, TT, r0_, r1_, x1_, first, last, tax in spans:
                    bcols = _bench_cols(bb, bc, first, last, slc)
                    if (tuple(bcoins), wn) not in bench_done:
                        bench_done.add((tuple(bcoins), wn))
                        for nm_, key_ in (("buy-and-hold (bb_bench.bh_crypto, 1/K sleeves)", "bh"),
                                          ("moneyline_ref (bb_bench.moneyline_perp)", "ml")):
                            bench_rows.append({"benchmark": nm_, "coins": "/".join(bcoins), "window": wn, "start": x,
                                               "end": y, "single_path": wn in SINGLE_PATH,
                                               "half_method": _half_method(wn, sl, sep), **bcols[key_]})
                    base.append({"asset_group": "crypto", "strategy": strat, "window": wn, "start": x, "end": y,
                                 "single_path": wn in SINGLE_PATH,
                                 "label": "single 16-month path" if wn in SINGLE_PATH else "",
                                 "half_method": _half_method(wn, sl, sep), "group": gname,
                                 "coins": "/".join(sp.coins) if len(sp.coins) <= 6 else
                                 f"{sp.universe_row} ({len(sp.coins)} coins)", "K": sp.K, **rr,
                                 "cagr_tax_pct": tax, "spy_cagr_tax_pct": _spy_cagr_tax(first, last),
                                 "note": SLICE_NOTE if slc is not None else "",
                                 "bench_coins": "/".join(bcoins), "bench_same_coins": same,
                                 "bench_note": "" if same else BENCH_NOTE,
                                 **{f"bh_{k}": v for k, v in bcols["bh"].items()},
                                 **{f"ml_{k}": v for k, v in bcols["ml"].items()}})
                    items.append({"ppy": 365, "years": len(r0_) / 365.25, "ret0": r0_.to_numpy(), "zero": True,
                                  "ret1": r1_.to_numpy(), "ex1": x1_.to_numpy(), "T": TT, "pnl_col": "pnl_usd",
                                  "start": x, "end": y})
                eq_rows.append(pd.DataFrame({"series": strat, "group": gname, "window": wname, "day": a0["equity"].index,
                                             "equity": a0["equity"].to_numpy(),
                                             "equity_tbill": a1["equity"].to_numpy()}))
                if strat == "R0 (L=3)" and gname == "all":
                    accts1[wname] = (a1["ret"], bc["bh1"])
    # stocks: 20-slot member book, 14-slot ETF book (headline at 1x); halves as slices of the 2001-2026 run, and the
    # halves' own runs as a sensitivity (choice 1)
    for univ in conf.stock_univ:
        sr_full = stock_res.get((univ, "primary", *conf.stock_win))
        spans = []
        if sr_full is not None:
            spans.append(("primary", tuple(conf.stock_win), sr_full, None, ""))
            spans += [(h, (x, y), sr_full, (x, y), HALF_SLICE) for h, (x, y) in conf.stock_halves.items()]
        if conf.half_runs:
            spans += [(f"{h} {SEP_TAG}", (x, y), stock_res[(univ, "primary", x, y)], None, HALF_SEP)
                      for h, (x, y) in conf.stock_halves.items() if (univ, "primary", x, y) in stock_res]
        for wname, (a, b), sr, slc, hm in spans:
            bk_ = sr["books"]["1x"]
            dly = bk_["daily"] if slc is None else _between(bk_["daily"], *slc)
            if not len(dly):
                continue
            T = sr["trades"]
            if slc is not None and len(T):
                T = T[_between_mask(T["entry1_date"] if "entry1_date" in T else T["entry1_time"], *slc)]
            ben = sr["bench"] if (sr["bench"] is None or slc is None) else _between(sr["bench"], *slc)
            years = _years(dly["ret"], "stock")
            s0 = account_stats(dly["ret"], dly["excess"], 252, years)
            bstats = _bench_stats(ben["ret"], ben["excess"], "stock", years) if ben is not None and len(ben) else {}
            bmult = bstats.get("multiple", np.nan)
            first = pd.Timestamp(dly.index[0]) - day
            last = pd.Timestamp(dly.index[-1])
            row = {"asset_group": "stocks" if univ == "members" else "ETFs",
                   "strategy": f"stock version 1x ({bk_['n_slots']}-slot book)", "window": wname, "start": a, "end": b,
                   "single_path": False, "label": "", "half_method": hm, "group": univ, "coins": univ,
                   "K": bk_["n_slots"], "multiple": s0["multiple"], "cagr_pct": s0["cagr_pct"],
                   "max_dd_pct": s0["max_dd_pct"], "sharpe": s0["sharpe"], "days": s0["days"],
                   "n_positions_book": int(len(bk_["positions"])) if slc is None else np.nan,
                   **trade_stats(T, None), "cagr_tax_pct": bk_["tax"].get("cagr_tax") if slc is None else np.nan,
                   "spy_cagr_tax_pct": _spy_cagr_tax(first, last), "note": SLICE_NOTE if slc is not None else "",
                   "bench_coins": f"equal-weight {univ}", "bench_same_coins": True, "bench_note": "",
                   **{f"bh_{k}": v for k, v in bstats.items()},
                   "bh_cagr_tax_pct": bb._cagr(bb.bh_after_tax(bmult), first, last) if np.isfinite(bmult) else np.nan}
            base.append(row)
            items.append({"ppy": 252, "years": years, "ret0": dly["ret"].to_numpy(), "zero": False,
                          "ret1": dly["ret"].to_numpy(), "ex1": dly["excess"].to_numpy(), "T": T, "pnl_col": None,
                          "start": a, "end": b})
            if slc is None:
                eq_rows.append(pd.DataFrame({"series": row["strategy"], "group": univ, "window": wname,
                                             "day": dly.index, "equity": dly["equity"].to_numpy()}))
                if ben is not None:
                    eq_rows.append(pd.DataFrame({"series": f"equal-weight {univ}", "group": univ, "window": wname,
                                                 "day": ben.index, "equity": np.cumprod(1.0 + ben["ret"].to_numpy())}))
    ivs = _pool_map(_hl_item, items, jobs)
    H = _bh_col(pd.DataFrame([{**r, **iv} for r, iv in zip(base, ivs)]))
    H.to_csv(d / "headline.csv", index=False)
    pd.DataFrame(bench_rows).to_csv(d / "benchmarks.csv", index=False)
    (pd.concat(eq_rows, ignore_index=True) if eq_rows else pd.DataFrame()).to_csv(d / "equity.csv", index=False)
    # answer map: the halves as slices of the full run decide (bb_tests' method); separate runs are a sensitivity
    am = []
    if FULL_NAME in accts1:
        a_full, b_full = accts1[FULL_NAME]
        slices = {h: (_between(a_full, x, y), _between(b_full, x, y)) for h, (x, y) in sl.items()}
        seps = {h: accts1[f"{h} {SEP_TAG}"] for h in sl if f"{h} {SEP_TAG}" in accts1}
        for method, hv, decides in ((AM_SLICE, slices, True), (AM_SEP, seps, False)):
            if decides or hv:
                r = beats_holding(a_full, b_full, "crypto", hv, B=conf.B_port)
                am.append(_am_rows("crypto (BTC/ETH/SOL)", "R0 (L=3) three-slot account vs 1x buy-and-hold "
                                                           "(bb_bench.bh_crypto), idle cash at the T-bill", method, r,
                                   decides))
    for univ in conf.stock_univ:
        key = (univ, "primary", *conf.stock_win)
        if key not in stock_res or stock_res[key]["bench"] is None:
            continue
        sr = stock_res[key]
        a_full = sr["books"]["1x"]["daily"]["ret"]
        b_full = sr["bench"]["ret"]
        slices = {h: (_between(a_full, x, y), _between(b_full, x, y)) for h, (x, y) in conf.stock_halves.items()}
        seps = {}
        for h, (x, y) in conf.stock_halves.items():
            k2 = (univ, "primary", x, y)
            if conf.half_runs and k2 in stock_res and stock_res[k2]["bench"] is not None:
                seps[h] = (stock_res[k2]["books"]["1x"]["daily"]["ret"], stock_res[k2]["bench"]["ret"])
        nsl = sr["books"]["1x"]["n_slots"]
        for method, hv, decides in ((AM_SLICE, slices, True), (AM_SEP, seps, False)):
            if decides or hv:
                r = beats_holding(a_full, b_full, "stock", hv, B=conf.B_port)
                am.append(_am_rows("stocks (point-in-time members)" if univ == "members" else "ETFs (14)",
                                   f"{nsl}-slot book at 1x vs equal-weight {univ}", method, r, decides))
    A = pd.concat(am, ignore_index=True) if am else pd.DataFrame()
    A.to_csv(d / "answer_map.csv", index=False)
    meta = {"seconds": round(time.time() - t0, 1), "rows": int(len(H)), "answer_map_rows": int(len(A)), "F": f_note,
            "F_included": f_cell is not None, "fill_audit_violations": 0, "single_path_windows": list(SINGLE_PATH),
            "half_slices": sl, "answer_map_primary_half_method": AM_SLICE, "p_label": P_LABEL,
            "note_benchmarks": "F on an S12 universe is compared with BTC/ETH/SOL's buy-and-hold and indicator "
                               "(bench_same_coins False in headline.csv): bb_bench has no point-in-time S12 benchmark"}
    _write_json(d / "meta.json", meta)
    say(f"  headline: {len(H)} rows, {len(bench_rows)} benchmark rows, answer map {len(A)} rows "
        f"[{meta['seconds']:.0f}s]")
    return meta


AM_SLICE = "slices of the full run (primary; bb_tests' halves)"
AM_SEP = "separate runs starting flat (sensitivity)"


def _am_rows(group: str, what: str, method: str, r: dict, decides: bool) -> pd.DataFrame:
    rows = []
    for span, v in r.items():
        if not isinstance(v, dict):
            continue
        rows.append({"asset_group": group, "comparison": what, "half_method": method, "decides_sentence": decides,
                     "span": span, "mean_log_growth_diff_ann": v["estimate"], "ci95_lo": v["ci95_lo"],
                     "ci95_hi": v["ci95_hi"], "days": v["T"], "ruin": v["ruin"],
                     "above_zero_full_and_both_halves": r["above_zero_full_and_both_halves"]})
    return pd.DataFrame(rows)


# ============================================================================ stock runs (headline + explore)
def _stock_ohlc(which: str, src: Src):
    if src.stocks is None:
        return None
    if which in src.stocks:
        return src.stocks[which]
    for grp in ("user", "etfs", "members"):
        if grp in src.stocks and which in src.stocks[grp]:
            return {which: src.stocks[grp][which]}
    raise KeyError(f"no injected stock data for {which!r}")


def _stock_task(spec: dict) -> tuple:
    """One bb_stocks.stock_trades run with its books, benchmark and drift-adjusted trades (runs in a worker)."""
    from analysis_2026 import bb_stocks as bk
    from analysis_2026.bb_bench import _stock_tax
    src = _CTX["src"]
    which, row, a, b = spec["key"]
    res = bk.stock_trades(which, bk.ROWS[row], start=a, end=b, ohlc=_stock_ohlc(which, src))
    _check_audit(res["fills_audit"], f"stocks {which} {row} {a}..{b}")
    T = res["trades"].copy()
    if len(T):
        adj = bs.drift_adjust(T, res["expo"], bk.session_returns(res["data"]), parts=True)
        T["ret_adj"] = adj["ret_adj"].to_numpy(float)
    else:
        T["ret_adj"] = pd.Series(dtype=float)
    books = {}
    for lab, n_slots, lev in spec.get("books", ()):
        p = bk.portfolio(res, n_slots=n_slots, lev=lev, idle_tbill=True)
        books[lab] = {"daily": p["daily"][["equity", "ret", "rf", "excess", "gross_lev", "n_pos"]].copy(),
                      "positions": p["positions"][["sym", "M", "pnl", "open_at_end", "exit_date"]].copy(),
                      "tax": _stock_tax(p), "n_slots": n_slots, "lev": lev, "log": dict(p["log"])}
    bench = None
    if spec.get("bench"):
        bench = (bk.benchmark_ew_members(a, b, data=res["data"]) if which == "members"
                 else bk.benchmark_ew_etfs(a, b, data=res["data"]))
    names = {}
    for nm in spec.get("single", ()):
        r1 = bk.stock_trades(nm, bk.ROWS["primary"], start=a, end=b, ohlc=_stock_ohlc(nm, src))
        _check_audit(r1["fills_audit"], f"stocks {nm} {a}..{b}")
        p1 = bk.portfolio(r1, n_slots=1, lev=1.0, idle_tbill=True)
        bh = bk.benchmark_ew_etfs(a, b, data={nm: r1["data"][nm]}, min_history=bk.WARMUP)
        names[nm] = {"daily": p1["daily"][["equity", "ret", "excess"]].copy(), "bh": bh[["ret", "excess", "n"]].copy()}
    keep = ["sym", "pos", "signal_day", "entry1_date", "entry1_time", "exit_time", "exit_reason", "n_tranches", "ret",
            "ret_1x", "fin", "ret_adj", "hold_h", "open_at_end", "liquidated", "member", "half"]
    return spec["key"], {"trades": T.reindex(columns=[c for c in keep if c in T.columns]), "books": books,
                         "bench": bench, "single": names, "n_signals": int(res["log"].get("signals", 0))}


def stock_specs(conf: Conf, parts: set) -> list:
    """The stock runs the requested parts need (deduplicated)."""
    specs: dict = {}

    def add(key, books=(), bench=False, single=()):
        s = specs.setdefault(key, {"key": key, "books": [], "bench": False, "single": []})
        for bk_ in books:
            if bk_ not in s["books"]:
                s["books"].append(bk_)
        s["bench"] = s["bench"] or bench
        s["single"] = list(dict.fromkeys(list(s["single"]) + list(single)))

    nsl = {"members": 20, "etfs": 14}
    for univ in conf.stock_univ:
        n = nsl.get(univ, 20)
        if "headline" in parts:
            add((univ, "primary", *conf.stock_win), [("1x", n, 1.0)], True)
            if conf.half_runs:                         # the halves' own runs: a sensitivity (choice 1)
                for x, y in conf.stock_halves.values():
                    add((univ, "primary", x, y), [("1x", n, 1.0)], True)
        if "explore" in parts:
            add((univ, "primary", *conf.stock_win), [("1x", n, 1.0), ("2x", n, 2.0)], True)
            for v in conf.stock_variants:
                if v == "early":
                    add((univ, "primary", *conf.stock_early), [("1x", n, 1.0)], True)
                elif v == "lev2":
                    add((univ, "lev2", *conf.stock_win))
                else:
                    add((univ, v, *conf.stock_win), [("1x", n, 1.0)])
    if "explore" in parts:
        from analysis_2026 import bb_stocks as bk
        add(("user", "primary", *conf.stock_win), single=tuple(bk.USER))
        if "etfs" in conf.stock_univ:
            add(("etfs", "primary", *conf.stock_win), single=tuple(bk.ETFS))
    order = {"members": 0, "etfs": 1, "user": 2}
    return sorted(specs.values(), key=lambda s: (order.get(s["key"][0], 3), s["key"][1]))


# ============================================================================ part: routes, tv
def part_routes(out: Path, conf: Conf, src: Src, jobs: int, say=print) -> dict:
    from analysis_2026 import bb_bench as bb
    t0 = time.time()
    d = out / "routes"
    d.mkdir(parents=True, exist_ok=True)
    full = conf.windows.get("Full", FULL)
    kw = dict(placebo_n=conf.placebo_n, n_jobs=jobs, say=lambda *a: None, start=full[0], end=full[1],
              stocks_start=conf.stock_win[0], stocks_end=conf.stock_win[1])
    if src.hours is not None:
        kw["hours"] = src.hours
    if conf.route_coins:
        kw["coins"] = conf.route_coins
    cache: dict = {}
    which = ("RH", "ETF", "CB", "Stocks") if conf.stock_route else ("RH", "ETF", "CB")
    A = bb.routes(which=which, spot_route_start=conf.spot_route_start, engine_cache=cache, **kw)
    Bf = bb.routes(which=("RH", "ETF"), spot_route_start=None, engine_cache=cache, **kw)
    # results with ZEC beside results without it (Reporting rules; choice 13): RH's pooled group without ZEC
    rh_coins = list((conf.route_coins or {}).get("RH", bb.ROUTES["RH"]["coins"]))
    rh_groups = bb.ROUTES["RH"]["groups"]
    ex_coins = [c for c in rh_coins if c != ZEC]
    zec_pools = [g for g, gc in rh_groups.items() if ZEC in gc and ZEC in rh_coins]
    has_twin = bool(zec_pools) and all(g + EXZEC in rh_groups for g in zec_pools)   # bb_bench already has them
    exz = {"needed": bool(zec_pools), "groups": zec_pools, "coins": ex_coins, "skipped_bb_bench_has_group": has_twin}
    ex_runs = []
    if zec_pools and not has_twin and ex_coins:
        kw2 = dict(kw, coins={**(kw.get("coins") or {}), "RH": ex_coins})
        ex_runs = [(A, bb.routes(which=("RH",), spot_route_start=conf.spot_route_start, engine_cache=cache, **kw2)),
                   (Bf, bb.routes(which=("RH",), spot_route_start=None, engine_cache=cache, **kw2))]
    for r_, lab in [(A, "longest spot history"), (Bf, "Full window")] + [(x, "RH without ZEC") for _, x in ex_runs]:
        if r_["log"]["fills_audit_violations"]:
            raise RuntimeError(f"fill audit violated in routes ({lab}): {r_['log']['fills_audit_violations']}")
    same_gate = []
    for r_, x in ex_runs:                          # keep only the pooled groups, relabelled; the rest duplicates r_
        gk = ["route", "row", "sym", "verdict", "placebo_trade_p", "placebo_prob_p"]
        g0 = r_["gate"][(r_["gate"]["route"] == "RH") & r_["gate"]["sym"].isin(ex_coins)].reindex(columns=gk)
        g1 = x["gate"].reindex(columns=gk)
        same_gate.append(bool(len(g0) == len(g1) and g0.reset_index(drop=True).astype(str).equals(
            g1.reset_index(drop=True).astype(str))))
        sx = x["summary"][(x["summary"]["route"] == "RH") & x["summary"]["group"].isin(zec_pools)].copy()
        sx["group"] = sx["group"] + EXZEC
        r_["summary"] = pd.concat([r_["summary"], sx], ignore_index=True)
        for (route, row, grp), e in x["accounts"].items():
            if route == "RH" and grp in zec_pools:
                r_["accounts"][(route, row, grp + EXZEC)] = e
    exz["gate_rows_identical"] = all(same_gate) if same_gate else None
    basis_a = {"RH": f"longest Binance spot history (from {conf.spot_route_start}; Addendum 2)",
               "ETF": f"longest Binance spot history (from {conf.spot_route_start}; Addendum 2)",
               "CB": "Full window (perpetual data start 2019-09: T1 caps it at PROBATION)",
               "Stocks": f"{conf.stock_win[0]}..{conf.stock_win[1]}"}
    G = pd.concat([A["gate"].assign(basis=A["gate"]["route"].map(basis_a)),
                   Bf["gate"].assign(basis="Full window (beside the longest-history spot routes)")], ignore_index=True)
    S = pd.concat([A["summary"].assign(basis=A["summary"]["route"].map(basis_a)),
                   Bf["summary"].assign(basis="Full window (beside the longest-history spot routes)")],
                  ignore_index=True)
    G.to_csv(d / "gate.csv", index=False)
    S.to_csv(d / "summary.csv", index=False)
    gcols = ["route", "row", "group", "basis", "K", "start", "end", "n_assets", "n_TRADE", "n_PROBATION", "n_NO_SIGNAL",
             "expected_false_TRADE", "expected_false_PROBATION", "n_placebo_undefined", "n_T1_years_ok",
             "fm_cagr_pre", "fm_cagr_tax", "fm_max_dd", "bh_cagr_tax", "spy_cagr_tax"]
    S.reindex(columns=gcols).to_csv(d / "groups.csv", index=False)
    acc = []
    for lab, r_ in (("longest spot history", A), ("Full window", Bf)):
        for (route, row, grp), e in r_["accounts"].items():
            acc.append(pd.DataFrame({"route": route, "row": row, "group": grp, "basis": lab, "day": e.index,
                                     "equity": np.asarray(e, float)}))
    (pd.concat(acc, ignore_index=True) if acc else pd.DataFrame()).to_csv(d / "accounts.csv", index=False)
    meta = {"seconds": round(time.time() - t0, 1), "gate_rows": int(len(G)), "summary_rows": int(len(S)),
            "placebo_n": conf.placebo_n, "log_longest": A["log"], "log_full": Bf["log"], "fill_audit_violations": 0,
            "exZEC": exz, "note_placebo_columns": "gate.csv's placebo_trade_p / placebo_prob_p are gate.placebo's "
                                                  "false-pass rates (the expected false-pass counts' terms), not "
                                                  "p-values of a test"}
    _write_json(d / "meta.json", meta)
    say(f"  routes: {len(G)} gate rows, {len(S)} group rows, fill audits empty [{meta['seconds']:.0f}s]")
    return meta


def part_tv(out: Path, conf: Conf, src: Src, say=print) -> dict:
    from analysis_2026 import bb_bench as bb
    t0 = time.time()
    d = out / "tv"
    d.mkdir(parents=True, exist_ok=True)
    syms = list(conf.tv_syms) if conf.tv_syms is not None else list(bb.TV_SYMS)
    res = bb.tv_crosscheck(syms=syms, data=src.tv)
    pd.concat([v["stats"] for v in res.values()], ignore_index=True).to_csv(d / "stats.csv", index=False)
    pd.concat([v["s1"]["trades"].assign(sym=s) for s, v in res.items()], ignore_index=True).to_csv(
        d / "s1_trades.csv", index=False)
    pd.concat([v["indicator"]["trades"].assign(sym=s) for s, v in res.items()], ignore_index=True).to_csv(
        d / "indicator_trades.csv", index=False)
    meta = {"seconds": round(time.time() - t0, 1), "syms": syms,
            "positions": {s: int(len(v["s1"]["trades"])) for s, v in res.items()},
            "note": "close-only exports: no fills to audit (bb_bench choice 12)"}
    _write_json(d / "meta.json", meta)
    say(f"  tv: {len(syms)} coins [{meta['seconds']:.0f}s]")
    return meta


# ============================================================================ part: scorecard
RULES = {
    1: ("Set the max size before entry and start with about a third", "max notional M = L x sleeve; first tranche M/3",
        [("R0", "S4")]),
    2: ("Add only when the trade is 2-5% in profit", "adds of M/3 at hourly closes >= 1.02 / 1.05 x entry1",
        [("R0", "S4"), ("R0", "S5")]),
    3: ("Never average down or top up a loser", "re-entry needs a fresh signal; an add is cancelled below the average "
        "entry", [("R0", "S18")]),
    4: ("Keep leverage at 3-5x", "L = 3 isolated, capped so S sits 2 points above liquidation", [("R0", "S2")]),
    5: ("Stick to a few liquid coins", "BTC/ETH/SOL, one slot each",
        [("R0", "S12_top3"), ("R0", "S12_top6"), ("R0", "S12_top10")]),
    6: ("Hold winners at least 3 days", "R0: a midline exit within 72 h of entry1 is not acted on while the mark is at "
        "or above the average entry; H8(a): a 72-h minimum hold", [("H8a", "S1W")]),
    7: ("Wait for the breakout to confirm; cut on the trend breaking", "entry on a daily close above the upper band",
        [("S1", "H4touch")]),
    8: ("Exit in one go or two pieces at most", "50% at the 3R take-profit, the rest on the midline",
        [("R0", "S10_tp_all"), ("R0", "S10_no_tp")]),
    9: ("When wrong, cut all of it", "the stop and the midline exit close every tranche", []),
    10: ("Every position gets a wide stop and a take-profit of at least 3x the risk",
         "S = SMA20 - 1 x ATR14; TP = entry1 + 3 x (entry1 - S)",
         [("R0", "S9_lower_band"), ("R0", "S9_sma_2p5atr"), ("R0", "S10_tp_all"), ("R0", "S10_no_tp")]),
    11: ("Don't size up after a big month", "sizing equity frozen for the month after a month above +25%",
         [("R0", "S19")]),
    12: ("Don't open trades on a Friday or Saturday", "no first-tranche fill on a New York-date Fri / Sat (deferred, "
         "re-checked)", [("H7", "S1W")]),
    13: ("Never open in the 90 min before the US open; enter 3.5 h before or 30 min after it",
         "entries at the 06:00 or 10:00 New York window", [("H6", "S1")]),
    14: ("Close 3.5-5.5 h after the US open", "trend exits at the 13:00 New York window", [("H6", "S1")]),
    15: ("Don't cut on Monday because of the weekend", "midline exits of the Sat / Sun closes deferred to Monday's "
         "close", [("H8b", "S1W")]),
}
ARM_CFG = {"H8a": lambda: be.h8a_cfg(72), "H7": lambda: be.h7_cfg((4, 5)), "H6": lambda: be.h6_cfg(6, 13),
           "H8b": lambda: be.h8b_cfg((5, 6)), "H4touch": lambda: be.h4_touch_cfg(be.ROWS["S1"])}
ARM_LABEL = {"H8a": "S1W + 72-h minimum hold (H8a)", "H7": "S1W + rule 12 (H7)", "H6": "R0's pair 06:00/13:00 NY (H6)",
             "H8b": "S1W + rule 15 (H8b)", "H4touch": "touch arm (H4)"}
ACCOUNT_ONLY = {11}


def _arm(name: str, conf: Conf, src: Src) -> Spec:
    if name.endswith(EXZEC):                   # the same arm without ZEC's positions, K unchanged (choice 4)
        sp = _arm(name[:-len(EXZEC)], conf, src)
        return Spec(name, sp.cfg, [c for c in sp.coins if c != ZEC], sp.K, {c: k for c, k in sp.akeys.items()
                                                                              if c != ZEC}, sp.vehicle, sp.universe_row)
    if name in ARM_CFG:
        return Spec(name, ARM_CFG[name](), list(conf.primary), len(conf.primary), {s: None for s in conf.primary})
    coins, K, ak = universe(name, conf, src)
    return Spec(name, be.ROWS[name], coins, K, ak, universe_row=name)


def scorecard_keys(conf: Conf, src: Src) -> list:
    a, b = conf.windows.get("Full", FULL)
    keys = []
    for _, _, comps in RULES.values():
        for x, y in comps:
            for nm in (x, y):
                try:
                    keys += _arm(nm, conf, src).keys(a, b)
                except KeyError:
                    pass
    keys += _arm("R0", conf, src).keys(a, b)
    return keys


def scorecard_verdict(trade_ci: tuple, sharpe_ci: tuple, noop: bool, account_only: bool = False) -> tuple:
    """(verdict, basis) of one non-Holm comparison (coding choice 10)."""
    if noop:
        return "no-op as coded", "identical trades and account returns"
    lo, hi = sharpe_ci if account_only else trade_ci
    basis = "sleeve Sharpe 95% interval" if account_only else "trade-effect 95% interval"
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return "no detectable effect", basis + " undefined"
    if lo > 0:
        return "helps", basis
    if hi < 0:
        return "hurts", basis
    return "no detectable effect", basis


def combine_verdicts(vs: list) -> str:
    if not vs:
        return "not testable"
    if all(v == vs[0] for v in vs) and vs[0] in ("helps", "hurts", "no-op as coded"):
        return vs[0]
    return "no detectable effect"


def _verdict_map(V: pd.DataFrame, source: str) -> dict:
    col = "label" if "label" in V.columns else "verdict"
    return {str(t): (str(x), source) for t, x in zip(V["test_id"], V[col])}


def test_verdicts(out_dir) -> tuple:
    """({test_id: (verdict label, source)}, note) of the 12 Holm-family tests (coding choice 10): verdicts.csv when it
    is at least as new as primary/tests.json; else bb_tests.report run on a temporary copy of primary/tests.json and
    controls/inference.json when tests.json holds all 12 tests without error (results_bb is not written); else
    ({}, why) - the scorecard then says "pending"."""
    import shutil
    import tempfile
    from analysis_2026 import bb_replica as br
    from analysis_2026 import bb_tests as bt
    out = Path(out_dir)
    tj, vc = out / "primary" / "tests.json", out / "verdicts.csv"
    v = {}
    if vc.exists() and (not tj.exists() or vc.stat().st_mtime >= tj.stat().st_mtime):
        try:
            v = _verdict_map(pd.read_csv(vc), "results_bb/verdicts.csv")
        except (ValueError, OSError, KeyError):
            v = {}
        if all(t in v for t in set(HOLM_RULES.values())):
            return v, "results_bb/verdicts.csv"
    st = br.primary_status(out)
    if not st["ok"]:
        return v, f"pending: {st['why']}"
    tmp = Path(tempfile.mkdtemp(prefix="bb_desc_verdicts_"))
    try:
        (tmp / "primary").mkdir()
        shutil.copy2(tj, tmp / "primary" / "tests.json")
        ij = out / "controls" / "inference.json"
        if ij.exists():
            (tmp / "controls").mkdir()
            shutil.copy2(ij, tmp / "controls" / "inference.json")
        try:
            V = bt.report(tmp, say=lambda *a, **k: None)
        except SystemExit as e:
            return {}, f"pending: bb_tests.report refused ({e})"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src_ = "bb_tests.report on results_bb/primary/tests.json (verdicts.csv absent or older)"
    return _verdict_map(V, src_), src_


def _episode_key(T: pd.DataFrame, ep: pd.DataFrame, tag: str) -> pd.DataFrame:
    T = T.copy()
    if not len(T):
        T["episode"] = pd.Series(dtype=object)
        T["ep_start"] = pd.Series(dtype="datetime64[ns, UTC]")
        return T
    ids = be.assign_episodes(T, ep).to_numpy()
    eps = set(ep["ep"].astype(int).tolist()) if len(ep) else set()
    known = np.array([int(i) in eps for i in ids], bool)
    smap = dict(zip(ep["ep"].astype(int), pd.DatetimeIndex(ep["start"]))) if len(ep) else {}
    T["episode"] = np.where(known, ids.astype(str), np.char.add(f"{tag}_own_", T["pos"].astype(str).to_numpy(str)))
    et = pd.DatetimeIndex(T["entry1_time"])
    T["ep_start"] = pd.DatetimeIndex([smap[int(i)] if k else e for i, k, e in zip(ids, known, et)])
    return T


def _comparison(rule: int, x: str, y: str, sims: Sims, conf: Conf, src: Src) -> dict:
    a, b = conf.windows.get("Full", FULL)
    A, C = _arm(x, conf, src), _arm(y, conf, src)
    ra, rc = A.results(sims, a, b), C.results(sims, a, b)
    Ta = pd.concat([r["trades"] for r in ra.values() if len(r["trades"])] or [_empty_sim("")["trades"]],
                   ignore_index=True)
    Tc = pd.concat([r["trades"] for r in rc.values() if len(r["trades"])] or [_empty_sim("")["trades"]],
                   ignore_index=True)
    out = {"rule": rule, "rule_arm": ARM_LABEL.get(x, x), "comparison_arm": ARM_LABEL.get(y, y),
           "n_rule_arm": int(len(Ta)), "n_comparison_arm": int(len(Tc))}
    unpaired = (A.universe_row or "").startswith("S12") or (C.universe_row or "").startswith("S12")
    if unpaired:
        out["unit"] = "difference of means (different coins; normal interval, independence assumed)"
        for col, pre in (("ret", "trade"), ("ret_adj", "trade_adj")):
            ma, sa, *_ = bs.cluster_t(Ta[col].to_numpy(float), bs.month_key(Ta["entry1_time"])) if len(Ta) else \
                (np.nan, np.nan)
            mc, sc, *_ = bs.cluster_t(Tc[col].to_numpy(float), bs.month_key(Tc["entry1_time"])) if len(Tc) else \
                (np.nan, np.nan)
            dlt, se = ma - mc, math.sqrt(sa ** 2 + sc ** 2) if np.isfinite(sa) and np.isfinite(sc) else np.nan
            out[f"{pre}_effect"] = dlt
            out[f"{pre}_lo"], out[f"{pre}_hi"] = (dlt - 1.96 * se, dlt + 1.96 * se) if np.isfinite(se) else \
                (np.nan, np.nan)
            out[f"{pre}_p"] = float(stats.norm.sf(dlt / se)) if np.isfinite(se) and se > 0 else np.nan
        noop_tr = False
        out["n_units"] = int(len(Ta) + len(Tc))
    else:
        if x == "H4touch" or y == "H4touch":
            eps = {s: be.h4_episodes(s, a, b, cfg=be.h4_touch_cfg(be.ROWS["S1"]),
                                     **({"hours": src.hours[s]} if src.hours is not None else {}),
                                     **({"minutes": src.minutes[s]} if src.minutes is not None and s in src.minutes
                                        else {}))
                   for s in conf.primary}
            Ta = pd.concat([_episode_key(ra[s]["trades"], eps[s], "a") for s in conf.primary], ignore_index=True)
            Tc = pd.concat([_episode_key(rc[s]["trades"], eps[s], "c") for s in conf.primary], ignore_index=True)
            dd = bs.paired_signal_diff(Tc, Ta, key=["sym", "episode"], col=["ret", "ret_adj"], time_col="ep_start")
            out["unit"] = "per episode (H4's unit), rule arm minus comparison"
        else:
            dd = bs.paired_signal_diff(Tc, Ta, key="signal_day", col=["ret", "ret_adj"])
            out["unit"] = "per signal (union; a skipped signal counts 0), rule arm minus comparison"
        out["n_units"] = int(len(dd))
        for col, pre in (("ret", "trade"), ("ret_adj", "trade_adj")):
            dv = dd[f"diff_{col}"].to_numpy(float) if len(dd) else np.zeros(0)
            m, se, _, p, df = bs.cluster_t(dv, dd["month"].to_numpy()) if len(dd) else (np.nan, np.nan, 0, np.nan, 0)
            out[f"{pre}_effect"] = m
            out[f"{pre}_lo"], out[f"{pre}_hi"] = _ci_t(m, se, df)
            if len(dd) and np.all(dv[np.isfinite(dv)] == 0):
                out[f"{pre}_lo"] = out[f"{pre}_hi"] = 0.0
            out[f"{pre}_p"] = p
        dv = dd["diff_ret"].to_numpy(float) if len(dd) else np.zeros(0)
        noop_tr = bool(len(dd) and np.all(np.nan_to_num(dv) == 0))
    acA = account(ra, A.cfg, a, b, A.K, True)
    acC = account(rc, C.cfg, a, b, C.K, True)
    same = bool(len(acA["ret"]) == len(acC["ret"]) and np.allclose(acA["ret"].to_numpy(), acC["ret"].to_numpy(),
                                                                    rtol=0, atol=1e-15))
    if same:
        out.update(sharpe_effect=0.0, sharpe_lo=0.0, sharpe_hi=0.0, sharpe_p=np.nan)
    else:
        r = bs.block_boot(acA["excess"], acC["excess"], "sharpe_diff", bs.MONTH_DAYS, B=conf.B_port, seed=SEED,
                          ppy=365)
        out.update(sharpe_effect=r["estimate"], sharpe_lo=r["ci95"][0], sharpe_hi=r["ci95"][1], sharpe_p=r["p"])
    out["sharpe_rule_arm"] = account_stats(acA["ret"], acA["excess"])["sharpe"]
    out["sharpe_comparison_arm"] = account_stats(acC["ret"], acC["excess"])["sharpe"]
    v, basis = scorecard_verdict((out["trade_lo"], out["trade_hi"]), (out["sharpe_lo"], out["sharpe_hi"]),
                                 noop_tr and same, rule in ACCOUNT_ONLY)
    out["verdict_descriptive"], out["verdict_basis"] = v, basis
    return out


def _comparison_job(job: tuple) -> dict:
    rule, x, y = job
    try:
        return _comparison(rule, x, y, _CTX["sims"], _CTX["conf"], _CTX["src"])
    except KeyError as e:                      # an S12 arm without an injected universe (tests)
        return {"rule": rule, "rule_arm": x, "comparison_arm": y, "verdict_descriptive": "not run",
                "verdict_basis": str(e)}


def _has_zec(name: str, conf: Conf, src: Src) -> bool:
    """An S12 arm whose universe holds ZEC (its comparison gets an exZEC twin; choice 4)."""
    try:
        sp = _arm(name, conf, src)
    except KeyError:
        return False
    return bool((sp.universe_row or "").startswith("S12") and ZEC in sp.coins)


def scorecard_jobs(conf: Conf, src: Src) -> list:
    """(rule, rule arm, comparison arm, exZEC twin?) of every comparison: the pre-registered ones and, after each S12
    comparison whose universe holds ZEC, the same comparison without ZEC."""
    out = []
    for rule, (_, _, comps) in RULES.items():
        for x, y in comps:
            out.append((rule, x, y, False))
            zx, zy = _has_zec(x, conf, src), _has_zec(y, conf, src)
            if zx or zy:
                out.append((rule, x + EXZEC if zx else x, y + EXZEC if zy else y, True))
    return out


def part_scorecard(out: Path, sims: Sims, conf: Conf, src: Src, say=print, jobs: int = 1) -> dict:
    t0 = time.time()
    d = out / "scorecard"
    d.mkdir(parents=True, exist_ok=True)
    tv, tv_note = test_verdicts(out)
    jl = scorecard_jobs(conf, src)
    _CTX["sims"] = sims
    try:
        det = _pool_map(_comparison_job, [(rule, x, y) for rule, x, y, _ in jl], jobs)
    finally:
        _CTX["sims"] = None
    D = pd.DataFrame(det)
    if len(D):
        D.insert(3, "exZEC", [z for *_, z in jl])
        D = _bh_col(D, {c: c + "_bh" for c in ("trade_p", "trade_adj_p", "sharpe_p")})
    D.to_csv(d / "scorecard_detail.csv", index=False)
    a, b = conf.windows.get("Full", FULL)
    r0 = _arm("R0", conf, src).results(sims, a, b)
    supp = int(sum(int(r.get("log", {}).get("rule6_suppressed", 0)) for r in r0.values()))
    rows, pending = [], []
    fmt = lambda r_, p_: (f"{r_[p_ + '_effect']:+.4f} [{r_[p_ + '_lo']:+.4f}, {r_[p_ + '_hi']:+.4f}]"   # noqa: E731
                          if np.isfinite(r_.get(p_ + "_effect", np.nan)) else "n/a")
    for rule, (text, coded, comps) in RULES.items():
        sub = D[D["rule"] == rule] if len(D) else D
        main = sub[~sub["exZEC"].astype(bool)] if len(sub) else sub
        twin = sub[sub["exZEC"].astype(bool)] if len(sub) else sub
        eff_t = "; ".join(f"{r_['rule_arm']} vs {r_['comparison_arm']}: {fmt(r_, 'trade')}" for _, r_ in sub.iterrows())
        eff_s = "; ".join(f"{r_['rule_arm']} vs {r_['comparison_arm']}: {fmt(r_, 'sharpe')}" for _, r_ in sub.iterrows())
        desc = combine_verdicts(list(main["verdict_descriptive"])) if len(main) else "not testable"
        desc_x = combine_verdicts(list(twin["verdict_descriptive"])) if len(twin) else ""
        holm = HOLM_RULES.get(rule)
        if rule == 9:
            verdict, source = "not testable", "built in: every exit closes all tranches (no variant)"
        elif holm:
            verdict, source = tv.get(holm, ("pending", tv_note))
            if verdict == "pending":
                pending.append(rule)
        else:
            verdict, source = desc, "descriptive (coding choice 10)"
        first = main.iloc[0] if len(main) else {}
        rows.append({"rule": rule, "rule_text": text, "coded_form": coded,
                     "comparisons": "; ".join(f"{ARM_LABEL.get(x, x)} vs {ARM_LABEL.get(y, y)}" for x, y in comps) or
                     "none (built in)", "holm_test": holm or "", "effect_trade_mean_net_per_M": eff_t,
                     "effect_sleeve_sharpe": eff_s,
                     **{k: first.get(k, np.nan) for k in ("trade_effect", "trade_lo", "trade_hi", "sharpe_effect",
                                                          "sharpe_lo", "sharpe_hi")},
                     "verdict": verdict, "verdict_source": source, "verdict_descriptive": desc,
                     "verdict_descriptive_exZEC": desc_x,
                     "note": (f"R0 suppressed {supp} midline exits under the literal rule 6 (Full window)"
                              if rule == 6 else "")})
    S = pd.DataFrame(rows)
    S.to_csv(d / "scorecard.csv", index=False)
    meta = {"seconds": round(time.time() - t0, 1), "rules": int(len(S)), "comparisons": int(len(D)),
            "exZEC_comparisons": int(sum(z for *_, z in jl)), "holm_verdicts_found": sorted(tv),
            "holm_verdicts_source": tv_note, "holm_verdicts_pending": bool(pending), "pending_rules": pending,
            "window": (a, b), "p_label": P_LABEL, "fill_audit_violations": 0}
    _write_json(d / "meta.json", meta)
    say(f"  scorecard: {len(S)} rules, {len(D)} comparisons [{meta['seconds']:.0f}s]")
    if pending:
        say(f"  scorecard: WARNING Holm-family verdicts pending for rules {pending} ({tv_note}); re-run "
            f"`--which scorecard` after `bb_replica report`")
    return meta


# ============================================================================ part: explore (grids, stock extras)
def _h10_in_primary(out_dir: Path) -> bool:
    p = out_dir / "primary" / "tests.json"
    if not p.exists():
        return False
    try:
        J = json.loads(p.read_text())
        ex = J.get("tests", {}).get("H10", {}).get("extra", {})
        return all(k in ex for k in ("fees_vip", "fees_zero", "touch_fills_optimistic"))
    except (ValueError, OSError, AttributeError):
        return False


def _grid_task(args) -> tuple:
    """R0 and every grid overlay on one coin over the grid window (runs in a worker)."""
    from analysis_2026 import bb_grid as bgr
    sym, plan = args
    src, conf = _CTX["src"], _CTX["conf"]
    a, b = conf.grid_win
    kw_e, kw_g = {}, {}
    if src.hours is not None:
        kw_e["hours"] = kw_g["hours"] = src.hours[sym]
    if src.minutes is not None and sym in src.minutes:
        kw_e["minutes"] = kw_g["minutes"] = src.minutes[sym]
    if src.mmr is not None:
        kw_e["mmr"] = kw_g["mmr"] = src.mmr
    out = {}
    for fee in FEES:
        cfg = replace(be.ROWS["R0"], fees=fee)
        r0 = be.simulate_coin(sym, cfg, a, b, detail=False, **kw_e)
        _check_audit(r0["fills_audit"], f"grid-window R0 {sym} {fee}")
        out[("R0", fee)] = {"trades": r0["trades"], "daily_mtm": r0["daily_mtm"]}
        for fill in (("through", "touch") if fee == "base" else ("through",)):
            if "GA" in plan:
                g = bgr.grid_ga(sym, r0["trades"], cfg_fees=fee, start=a, end=b, sleeve=1.0, fill=fill, **kw_g)
                _check_audit(g["fills_audit"], f"G-A {sym} {fee} {fill}")
                out[("GA", fee, fill)] = {k: g[k] for k in ("deployments", "daily_by_dep", "log")}
            if "GB" in plan:
                g = bgr.grid_gb(sym, r0, cfg_fees=fee, start=a, end=b, fill=fill, **kw_g)
                _check_audit(g["fills_audit"], f"G-B {sym} {fee} {fill}")
                out[("GB", fee, fill)] = {k: g[k] for k in ("trades", "daily_mtm", "deployments", "log")}
            if "G0" in plan:
                g = bgr.grid_g0(sym, cfg_fees=fee, start=a, end=b, sleeve=1.0, fill=fill, **kw_g)
                _check_audit(g["fills_audit"], f"G-0 {sym} {fee} {fill}")
                out[("G0", fee, fill)] = {k: g[k] for k in ("deployments", "daily_by_dep", "log")}
    return sym, out


def _grid_rows(G: dict, conf: Conf, include_h10: bool) -> tuple:
    from analysis_2026.bb_grid import merge_ga
    a, b = conf.grid_win
    prim, six = list(conf.primary), list(conf.six)
    rows, deps = [], []
    empty = {"trades": pd.DataFrame(), "daily_mtm": pd.DataFrame()}
    overlays = [("G-B (R0 + G-B)", "GB", prim), ("G-0 (always-on grid alone)", "G0", prim),
                ("six-slot G-A (R0 + G-A)", "GA", six)]
    if include_h10:
        overlays.append(("G-A three-slot (H10 universe; fee scenarios not in primary)", "GA", prim))
    for label, kind, coins in overlays:
        coins = [s for s in coins if s in G]
        if not coins:
            continue
        K = len(coins)
        for fee in FEES:
            cfg = replace(be.ROWS["R0"], fees=fee)
            r0 = {s: G[s][("R0", fee)] for s in coins}
            base = account(r0, cfg, a, b, K, True)
            for fill in (("through", "touch") if fee == "base" else ("through",)):
                if kind == "GB":
                    res = {s: G[s][("GB", fee, fill)] for s in coins}
                elif kind == "GA":
                    res = {s: merge_ga(G[s][("R0", fee)], G[s][("GA", fee, fill)]) for s in coins}
                else:
                    res = {s: merge_ga(empty, G[s][("G0", fee, fill)]) for s in coins}
                acc = account(res, cfg, a, b, K, True)
                s1 = account_stats(acc["ret"], acc["excess"])
                s0 = account_stats(base["ret"], base["excess"])
                if kind == "G0":
                    r = bs.block_boot(acc["excess"], None, "mean", GRID_BLOCK, B=conf.B_port, seed=SEED, ppy=365)
                    vs = "mean daily excess return over the T-bill (annualized)"
                else:
                    r = bs.block_boot(acc["ret"], base["ret"], "mean", GRID_BLOCK, B=conf.B_port, seed=SEED, ppy=365)
                    vs = "mean daily account-return difference vs R0 alone (annualized)"
                for s in coins:
                    D = G[s][(kind, fee, fill)]["deployments"]
                    if len(D):
                        deps.append(D.assign(overlay=label, fee_scenario=fee, fill=fill))
                rows.append({"overlay": label, "coins": "/".join(coins), "K": K, "fee_scenario": fee, "fill": fill,
                             "start": a, "end": b, **{f"overlay_{k}": v for k, v in s1.items()},
                             **{f"r0_alone_{k}": v for k, v in s0.items()}, "comparison": vs,
                             "diff_ann": r["estimate"], "diff_lo": r["ci95"][0], "diff_hi": r["ci95"][1],
                             "p_expl": r["p"], "block_days": GRID_BLOCK,
                             "label": "optimistic bound (touch fills)" if fill == "touch" else ""})
    return rows, deps


def part_explore(out: Path, conf: Conf, src: Src, stock_res: dict, jobs: int, say=print) -> dict:
    t0 = time.time()
    d = out / "explore"
    d.mkdir(parents=True, exist_ok=True)
    include_h10 = not _h10_in_primary(out)
    plan = {}
    for s in conf.six:
        p = {"GA"}
        if s in conf.primary:
            p |= {"GB", "G0"}
        plan[s] = p
    G = dict(_pool_map(_grid_task, [(s, plan[s]) for s in conf.six], jobs))
    rows, deps = _grid_rows(G, conf, include_h10)
    GR = _bh_col(pd.DataFrame(rows))
    GR.to_csv(d / "grids.csv", index=False)
    DEP = pd.concat(deps, ignore_index=True) if deps else pd.DataFrame()
    DEP.to_csv(d / "grid_deployments.csv", index=False)
    if len(DEP):
        cols = [c for c in ("grid_profit", "inventory_pnl", "fees", "funding", "net", "n_fills", "n_round_trips")
                if c in DEP.columns]
        by = ["overlay", "fee_scenario", "fill", "sym"]
        gs = DEP.groupby(by)[cols].sum()
        gs["n_deployments"] = DEP.groupby(by).size()
        gs["n_liquidated"] = DEP.groupby(by)["liquidated"].sum()
        gs.reset_index().to_csv(d / "grid_summary.csv", index=False)
    else:
        pd.DataFrame().to_csv(d / "grid_summary.csv", index=False)
    # stock extras
    srecs, trecs = [], []
    for univ in conf.stock_univ:
        prim = stock_res.get((univ, "primary", *conf.stock_win))
        variants = [("primary 1x", prim, "1x", conf.stock_win)]
        if prim is not None and "2x" in prim["books"]:
            lev2 = stock_res.get((univ, "lev2", *conf.stock_win))
            variants.append(("2x Reg-T (financing T-bill + 2.5 pts)", lev2, None, conf.stock_win))
            variants.append(("2x Reg-T book", prim, "2x", conf.stock_win))
        for v in conf.stock_variants:
            if v == "early":
                variants.append(("1996-2000 block (outside every pass rule; close-only caveat)",
                                 stock_res.get((univ, "primary", *conf.stock_early)), "1x", conf.stock_early))
            elif v in ("costs2x", "S20"):
                lab = {"costs2x": "double costs", "S20": "S20 weekly bars"}[v]
                variants.append((lab, stock_res.get((univ, v, *conf.stock_win)), "1x", conf.stock_win))
        for lab, sr, book, (a, b) in variants:
            if sr is None:
                continue
            rec = {"universe": univ, "variant": lab, "start": a, "end": b, "n_signals": sr["n_signals"],
                   **trade_stats(sr["trades"], None)}
            if book and book in sr["books"]:
                bk_ = sr["books"][book]
                dly = bk_["daily"]
                yrs = _years(dly["ret"], "stock")
                s0 = account_stats(dly["ret"], dly["excess"], 252, yrs)
                rec.update({f"book_{k}": v for k, v in s0.items()})
                rec.update(book_slots=bk_["n_slots"], book_lev=bk_["lev"], book_positions=int(len(bk_["positions"])),
                           book_cagr_tax_pct=bk_["tax"].get("cagr_tax"),
                           book_max_gross_lev=float(dly["gross_lev"].max()) if len(dly) else np.nan)
                ben = sr["bench"]
                if ben is None and prim is not None and (a, b) == tuple(conf.stock_win):
                    ben = prim["bench"]                  # same window, same names: the primary run's benchmark
                if ben is not None:
                    bst = _bench_stats(ben["ret"], ben["excess"], "stock", yrs)
                    rec.update({f"bench_{k}": v for k, v in bst.items()})
            srecs.append(rec)
    # tickers: the user's seven and the 14 ETFs individually
    for grp in ("user", "etfs"):
        sr = stock_res.get((grp, "primary", *conf.stock_win))
        if sr is None or not sr["single"]:
            continue
        T = sr["trades"]
        for nm, one in sr["single"].items():
            Tn = T[T["sym"] == nm] if len(T) else T
            ts = trade_stats(Tn, None)
            dly = one["daily"]
            yrs = _years(dly["ret"], "stock") if len(dly) else np.nan
            s0 = account_stats(dly["ret"], dly["excess"], 252, yrs) if len(dly) else {}
            bh = one["bh"]
            bst = _bench_stats(bh["ret"], bh["excess"], "stock", yrs) if len(bh) else {}
            trecs.append({"group": "user's tickers" if grp == "user" else "ETFs individually", "ticker": nm,
                          "n_trades": ts["n_positions"],
                          "not_interpreted": bool(grp == "user" and ts["n_positions"] < TICKER_FLOOR),
                          **ts, **{f"book1_{k}": v for k, v in s0.items()}, **{f"bh_{k}": v for k, v in bst.items()}})
    SR = _bh_col(pd.DataFrame(srecs))
    SR.to_csv(d / "stocks.csv", index=False)
    TR = _bh_col(pd.DataFrame(trecs))
    TR.to_csv(d / "stock_tickers.csv", index=False)
    meta = {"seconds": round(time.time() - t0, 1), "grid_rows": int(len(GR)), "grid_deployments": int(len(DEP)),
            "stock_rows": int(len(SR)), "ticker_rows": int(len(TR)), "h10_fee_rows_added": include_h10,
            "grid_window": conf.grid_win, "fill_audit_violations": 0, "p_label": P_LABEL,
            "grid_logs": {f"{s}/{'/'.join(k)}": {kk: vv for kk, vv in v.get("log", {}).items()
                                                  if isinstance(vv, (int, float, str))}
                          for s, gg in G.items() for k, v in gg.items() if k[0] != "R0"}}
    _write_json(d / "meta.json", meta)
    say(f"  explore: {len(GR)} grid rows, {len(DEP)} deployments, {len(SR)} stock rows, {len(TR)} ticker rows "
        f"[{meta['seconds']:.0f}s]")
    return meta


# ============================================================================ run
def run(out_dir=RES, which=None, jobs: int = 4, src: Src | None = None, conf: Conf | None = None,
        say=print) -> dict:
    """Write the descriptive outputs under out_dir (results_bb root). which: a subset of PARTS (list or a
    comma-separated string); jobs: worker processes."""
    t0 = time.time()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = src or Src()
    conf = conf or Conf()
    if which is None:
        parts = set(PARTS)
    else:
        parts = set(which.split(",") if isinstance(which, str) else which)
    bad = parts - set(PARTS)
    if bad:
        raise ValueError(f"unknown parts {sorted(bad)}; choose from {PARTS}")
    jobs = max(1, int(jobs))
    _CTX["src"], _CTX["conf"] = src, conf
    _CTX["masks"], _CTX["univ"] = {}, {}
    _W["frames"].clear(), _W["rets"].clear(), _W["allowed"].clear()
    if conf.f_cell is not None:
        f_cell, f_note = conf.f_cell, "F from Conf.f_cell"
    else:
        f_cell, f_note = read_f_cell(out)
        if f_cell is None and parts & {"rows", "headline"}:
            if conf.fcount_if_missing:                 # F's counts first, before any engine run here (choice 9)
                f_cell, f_note = ensure_f_cell(out, conf, src, jobs, say)
            else:
                f_note = f"F SKIPPED: {f_note}"
                say(f"bb_desc: WARNING {f_note}")
    say(f"bb_desc: parts {sorted(parts)}, {jobs} workers; {f_note}")
    sims = Sims(jobs)
    keys = []
    if "rows" in parts:
        keys += rows_keys(conf, src, f_cell)
    if "headline" in parts:
        keys += headline_keys(conf, src, f_cell)
    if "scorecard" in parts:
        keys += scorecard_keys(conf, src)
    t1 = time.time()
    sims.need(keys)
    say(f"  engine: {sims.n_runs} simulate_coin runs ({len(set(k[0] for k in sims.cache))} coins), fill audits "
        f"empty [{time.time() - t1:.0f}s]")
    stock_res = {}
    if parts & {"headline", "explore"} and conf.stock_univ:
        t1 = time.time()
        sp = stock_specs(conf, parts)
        stock_res = dict(_pool_map(_stock_task, sp, min(jobs, 2)))       # ~2 GB per member run
        say(f"  stocks: {len(sp)} bb_stocks runs, fill audits empty [{time.time() - t1:.0f}s]")
    metas = {}
    if "rows" in parts:
        metas["rows"] = part_rows(out, sims, conf, src, f_cell, f_note, say, jobs)
    if "headline" in parts:
        metas["headline"] = part_headline(out, sims, conf, src, f_cell, f_note, stock_res, jobs, say)
    if "scorecard" in parts:
        metas["scorecard"] = part_scorecard(out, sims, conf, src, say, jobs)
    if "explore" in parts:
        metas["explore"] = part_explore(out, conf, src, stock_res, jobs, say)
    if "routes" in parts:
        metas["routes"] = part_routes(out, conf, src, jobs, say)
    if "tv" in parts:
        metas["tv"] = part_tv(out, conf, src, say)
    say(f"bb_desc: wrote {sorted(metas)} under {out} in {time.time() - t0:.0f}s; engine runs {sims.n_runs}; "
        f"fill-audit violations 0")
    return {"parts": sorted(metas), "meta": metas, "engine_runs": sims.n_runs, "seconds": round(time.time() - t0, 1)}


# ============================================================================ self-test: synthetic data
def _bridge(lc0: float, mu: np.ndarray, sigma: float, rng) -> tuple:
    """A log-price path with exact Brownian-bridge highs and lows per step (open, high, low, close)."""
    n = len(mu)
    dlog = np.log1p(mu) - 0.5 * sigma ** 2 + sigma * rng.standard_normal(n)
    lc = lc0 + np.cumsum(dlog)
    lo_ = np.r_[lc0, lc[:-1]]
    d2 = (lc - lo_) ** 2
    mx = 0.5 * (lo_ + lc + np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    mn = 0.5 * (lo_ + lc - np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    return np.exp(lo_), np.exp(mx), np.exp(mn), np.exp(lc)


def _st_frame(idx, o, h, l_, c, trades=10) -> pd.DataFrame:
    df = pd.DataFrame({"open": o, "high": h, "low": l_, "close": c}, index=idx)
    df.index.name = "open_time"
    n = len(df)
    df["trades"] = np.full(n, trades, np.int64)
    df["tradable"], df["spot_only"], df["is_perp"], df["perp_end"] = True, False, True, False
    df["funding"] = 0.0
    for a in ("mark_open", "mark_high", "mark_low", "mark_close"):
        df[a] = np.nan
    for a in bd.PX:
        df["sig_" + a] = df[a]
    df["live"] = df["sig_live"] = True
    df["seg"] = 0
    df["quote_volume"] = df["sig_quote_volume"] = 1.0
    return df


def _st_hours(start, end, sigma, seed, delta=0.0003, reg_days=25.0) -> pd.DataFrame:
    """Synthetic coin_hours-shaped frame: hourly bridge path with regime-switching (+/- delta per hour) trends."""
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"), freq="h").as_unit("ns")
    rng = np.random.default_rng(seed)
    sw = rng.random(len(idx)) < 1.0 / (reg_days * 24)
    sign = rng.choice([-1.0, 1.0], int(sw.sum()) + 1)
    mu = delta * sign[np.cumsum(sw)]
    return _st_frame(idx, *_bridge(math.log(100.0), mu, sigma, rng))


def _st_with_minutes(H: pd.DataFrame, start, sigma_h: float, seed: int) -> tuple:
    """Replace H's hours from `start` by hours aggregated from a 1-minute bridge path. Returns (hours, minutes)."""
    a = pd.Timestamp(start, tz="UTC")
    pre = H[H.index < a]
    hix = H.index[H.index >= a]
    n = len(hix) * 60
    rng = np.random.default_rng(seed)
    o, h, l_, c = _bridge(math.log(float(pre["close"].iloc[-1])), np.zeros(n), sigma_h / math.sqrt(60), rng)
    M = pd.DataFrame({"open": o, "high": h, "low": l_, "close": c, "trades": np.full(n, 5, np.int64)},
                     index=pd.date_range(a, periods=n, freq="min").as_unit("ns"))
    M.index.name = "open_time"
    st = np.arange(0, n, 60)
    Hm = _st_frame(hix, o[st], np.maximum.reduceat(h, st), np.minimum.reduceat(l_, st), c[st + 59], trades=300)
    return pd.concat([pre, Hm]), M


def _st_stocks(names, seed, start="1998-01-02", end="2004-12-31", sigma=0.018, member_gap=False) -> dict:
    ses = pd.bdate_range(start, end).as_unit("ns")
    out = {}
    for i, nm in enumerate(names):
        rng = np.random.default_rng(seed + i)
        sw = rng.random(len(ses)) < 1 / 60
        mu = 0.002 * rng.choice([-1.0, 1.0], int(sw.sum()) + 1)[np.cumsum(sw)]
        c = 50.0 * np.exp(np.cumsum(np.log1p(mu) - 0.5 * sigma ** 2 + sigma * rng.standard_normal(len(ses))))
        o = np.r_[50.0, c[:-1]] * np.exp(0.25 * sigma * rng.standard_normal(len(ses)))
        h = np.maximum(o, c) * np.exp(0.5 * sigma * np.abs(rng.standard_normal(len(ses))))
        l_ = np.minimum(o, c) * np.exp(-0.5 * sigma * np.abs(rng.standard_normal(len(ses))))
        f = pd.DataFrame({"open": o, "high": h, "low": l_, "close": c, "tr": c}, index=ses)
        m = np.ones(len(ses), bool)
        if member_gap and i % 3 == 0:
            m[len(ses) // 3: len(ses) // 2] = False
        f["member"] = m
        out[nm] = f
    return out


def _st_tv(seed: int, n: int = 900) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(0.0015 * np.sign(np.sin(np.arange(n) / 40.0)) + 0.03 * rng.standard_normal(n)))
    idx = pd.date_range("2019-01-01", periods=n, freq="D")
    s = pd.Series(c, index=idx)
    atr = s.diff().abs().rolling(14, min_periods=1).mean().bfill()
    green = (s > s.rolling(50, min_periods=1).mean()).to_numpy()
    return pd.DataFrame({"close": c, "atr": atr.to_numpy(), "green": green, "state": np.ones(n, bool)}, index=idx)


def synthetic_setup() -> tuple:
    """(Src, Conf) of the self-test's tiny end-to-end run: seven synthetic coins under real names (so that
    bb_bench's route groups apply), 1-minute bars in the grid window for the six M1 coins, injected S12
    universes, synthetic stocks / ETFs / user tickers and TV exports; short windows and small bootstraps."""
    hours, minutes = {}, {}
    coins = ["BTC", "ETH", "SOL", "ZEC", "BNB", "XRP", "DOGE"]
    for i, s in enumerate(coins):
        start = "2020-03-01" if s == "SOL" else "2019-06-01"         # SOL lists after the pre-perpetual block
        H = _st_hours(start, "2021-12-31 23:00", 0.007 + 0.001 * i, 100 + i)
        if s in bd.M1_COINS:
            H, M = _st_with_minutes(H, "2021-11-01", 0.007 + 0.001 * i, 200 + i)
            minutes[s] = M
        hours[s] = H
    ms = pd.date_range("2019-06-01", "2021-12-01", freq="MS", tz="UTC")
    k = np.arange(len(ms))
    alt = pd.Series(k % 2 == 0, index=ms)
    allm = pd.Series(np.ones(len(ms), bool), index=ms)
    universes = {"S12_top3": (["BTC", "ETH", "SOL", "BNB"], 3, {"BTC": allm, "ETH": allm, "SOL": alt, "BNB": ~alt}),
                 "S12_top6": (["BTC", "ETH", "SOL", "ZEC", "BNB", "XRP"], 6,
                              {"BTC": allm, "ETH": allm, "SOL": allm, "ZEC": alt, "BNB": allm, "XRP": ~alt}),
                 "S12_top10": (coins, 10, {s: allm for s in coins})}
    from analysis_2026 import bb_stocks as bk
    stocks = {"members": _st_stocks([f"M{i:02d}" for i in range(24)], 500, member_gap=True),
              "etfs": _st_stocks(list(bk.ETFS), 700, sigma=0.012),
              "user": _st_stocks(list(bk.USER), 900, sigma=0.025)}
    src = Src(hours=hours, minutes=minutes, universes=universes, stocks=stocks,
              tv={"BTC": _st_tv(1), "ETH": _st_tv(2)})
    conf = Conf(windows={"Full": ("2020-01-01", "2021-12-31"), "W16": ("2021-03-01", "2021-12-31"),
                         "W16b": ("2020-06-01", "2021-03-31"), "H2020": ("2020-01-01", "2020-12-31"),
                         "H2021": ("2021-01-01", "2021-12-31")},
                halves=("H2020", "H2021"), pre_win=("2019-08-01", "2019-12-31"), grid_win=("2021-11-01", "2021-12-31"),
                stock_win=("2001-01-01", "2004-12-31"),
                stock_halves={"2001-2002": ("2001-01-01", "2002-12-31"), "2003-2004": ("2003-01-01", "2004-12-31")},
                stock_early=("1999-01-01", "2000-12-31"),
                rows=("R0", "S1", "S1_L1", "S2", "S3_cross", "S4", "S12_top6", "S16", "S17", "S19", "R0_stress",
                      "R0_at_S"),
                per_coin=("BTC", "ETH", "SOL", "ZEC"), pre_coins=("BTC", "ETH", "ZEC"), B_trade=199, B_port=199,
                placebo_n=2, spot_route_start="2019-08-01",
                route_coins={"RH": ["BTC", "ETH", "SOL", "ZEC"], "ETF": ["BTC", "ETH"], "CB": ["BTC", "ETH"]},
                stock_route=False, tv_syms=("BTC", "ETH"), f_cell={"bars": "4h", "universe": "S12 top 6"})
    return src, conf


# ============================================================================ self-test: known answers
def _close(a, b, tol=1e-10) -> bool:
    a, b = float(a), float(b)
    return (np.isnan(a) and np.isnan(b)) or abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _st_trade_stats(say) -> None:
    t = pd.to_datetime(["2021-01-05", "2021-01-20", "2021-02-03", "2021-02-25", "2021-03-02", "2021-03-30"],
                       utc=True)
    T = pd.DataFrame({"sym": "X", "pos": range(6), "entry1_time": t,
                      "ret": [0.10, -0.05, 0.02, -0.01, 0.00, 0.30], "ret_adj": [0.09, -0.06, 0.01, -0.02, -0.01, 0.28],
                      "hold_h": [200, 50, 80, 300, 10, 500], "open_at_end": [False] * 5 + [True],
                      "pnl_usd": [100.0, -50, 20, -10, 0, 300], "n_tranches": [3, 1, 2, 1, 1, 3],
                      "liquidated": [False, True, False, False, False, False]})
    s = trade_stats(T, "pnl_usd")
    assert s["n_positions"] == 6 and s["n_tranches"] == 11 and s["n_closed"] == 5 and s["n_open_at_end"] == 1
    assert s["liquidations"] == 1
    assert _close(s["hit_rate"], 0.4)                                   # 0.00 is not a win; open trade excluded
    assert _close(s["avg_win_loss"], 60.0 / 30.0) and _close(s["avg_win_loss_m"], 0.06 / 0.03)
    assert s["n_gt7d"] == 2 and _close(s["share_gt7d_won"], 0.5)
    assert s["n_ge3d"] == 3 and _close(s["profit_share_ge3d"], 110.0 / 60.0)
    assert _close(s["profit_share_ge3d_gross"], 1.0)
    # month-clustered mean: hand computation (clusters Jan, Feb, Mar; G/(G-1); t at G-1 = 2 df)
    m = 0.36 / 6
    se = math.sqrt(1.5 * (0.07 ** 2 + 0.11 ** 2 + 0.18 ** 2) / 36)
    q = stats.t.ppf(0.975, 2)
    assert _close(s["mean_ret"], m) and _close(s["mean_ret_lo"], m - q * se, 1e-9) and _close(s["mean_ret_hi"],
                                                                                               m + q * se, 1e-9)
    adj = np.array([0.09, -0.06, 0.01, -0.02, -0.01, 0.28])
    ma = adj.mean()
    e = adj - ma
    sea = math.sqrt(1.5 * ((e[0] + e[1]) ** 2 + (e[2] + e[3]) ** 2 + (e[4] + e[5]) ** 2) / 36)
    assert _close(s["mean_adj"], ma) and _close(s["mean_adj_se"], sea, 1e-9)
    assert _close(s["p_expl"], stats.t.sf(ma / sea, 2), 1e-9) and s["G_months"] == 3 and s["df"] == 2
    # per-M fallback and an empty table
    s2 = trade_stats(T.drop(columns=["pnl_usd"]), "pnl_usd")
    assert _close(s2["avg_win_loss"], 2.0) and _close(s2["profit_share_ge3d"], 0.11 / 0.06)
    s0 = trade_stats(T.iloc[:0])
    assert s0["n_positions"] == 0 and np.isnan(s0["hit_rate"]) and s0["n_tranches"] == 0
    # bootstrap intervals bracket the estimates on a larger table
    rng = np.random.default_rng(3)
    n = 400
    TT = pd.DataFrame({"entry1_time": pd.Timestamp("2020-01-01", tz="UTC") + pd.to_timedelta(
        np.sort(rng.integers(0, 900, n)), unit="D"), "ret": rng.normal(0.01, 0.05, n),
        "hold_h": rng.integers(1, 400, n), "open_at_end": False, "n_tranches": 1})
    TT["ret_adj"] = TT["ret"] - 0.005
    TT["pnl_usd"] = TT["ret"] * 100
    st_, iv = trade_stats(TT), trade_intervals(TT, "pnl_usd", B=299)
    for k in ("hit_rate", "avg_win_loss", "share_gt7d_won", "mean_ret", "mean_adj"):
        assert iv[k + "_blo"] <= st_[k] <= iv[k + "_bhi"], (k, iv[k + "_blo"], st_[k], iv[k + "_bhi"])
    say("  trade statistics = hand computation (hit rate, win/loss, >7-day and >=3-day shares, tranches, "
        "month-clustered mean and drift-adjusted mean, p); bootstrap intervals bracket the estimates")


def _st_account_stats(say) -> None:
    s = account_stats([0.10, -0.50, 0.20], [0.01, 0.02, 0.03])
    assert _close(s["multiple"], 0.66) and _close(s["max_dd_pct"], -50.0)
    assert _close(s["cagr_pct"], 100 * (0.66 ** (365.25 / 3) - 1))
    assert _close(s["sharpe"], 0.02 / 0.01 * math.sqrt(365))
    r = np.full(400, 0.001)
    iv = account_intervals(r, r + np.r_[0.0, 0.0001] .repeat(200), B=199)
    m = 1.001 ** 400
    assert _close(iv["multiple_lo"], m, 1e-9) and _close(iv["multiple_hi"], m, 1e-9)
    assert _close(iv["max_dd_pct_lo"], 0.0) and _close(iv["max_dd_pct_hi"], 0.0)
    st_ = account_stats(r, ppy=252, years=2.0)
    assert _close(st_["cagr_pct"], 100 * (m ** 0.5 - 1))
    # month-block count interval: equal monthly counts give a degenerate interval at the total
    t = [pd.Timestamp(f"2021-{mo:02d}-{d:02d}", tz="UTC") for mo in range(1, 7) for d in (3, 17)]
    c, lo, hi = count_interval(t, "2021-01-01", "2021-06-30", B=199)
    assert c == 12 and lo == 12 and hi == 12
    c, lo, hi = count_interval(t[:5], "2021-01-01", "2021-06-30", B=199)
    assert c == 5 and lo <= 5 <= hi and hi > lo
    say("  account statistics = hand computation (multiple, CAGR, Sharpe, max drawdown); block intervals of a "
        "constant path collapse; month-block count interval")


def _st_answer_map(say) -> None:
    rng = np.random.default_rng(9)
    idx = pd.date_range("2020-01-01", periods=730, freq="D", tz="UTC")
    b = pd.Series(rng.normal(0.0005, 0.03, len(idx)), index=idx)
    a = (1 + b) * 1.0002 - 1
    hv = {"h1": (a.iloc[:365], b.iloc[:365]), "h2": (a.iloc[365:], b.iloc[365:])}
    r = beats_holding(a, b, "crypto", hv, B=199)
    g = 365 * math.log(1.0002)
    for span in ("full", "h1", "h2"):
        assert _close(r[span]["estimate"], g, 1e-9) and _close(r[span]["ci95_lo"], g, 1e-9)
    assert r["above_zero_full_and_both_halves"]
    r2 = beats_holding(b, a, "crypto", hv, B=199)
    assert not r2["above_zero_full_and_both_halves"] and _close(r2["full"]["estimate"], -g, 1e-9)
    a3 = a.copy()
    a3.iloc[10] = -1.0                                                # ruin: log growth -inf, never above zero
    assert not beats_holding(a3, b, "crypto", None, B=99)["above_zero_full_and_both_halves"]
    say("  answer-map statistic: a constant log-growth gap gives that gap (annualized) with a degenerate interval in "
        "the full sample and both halves; reversed and ruined accounts are not above zero")


def _st_f_reader(say) -> None:
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="bb_desc_f_"))
    try:
        assert read_f_cell(tmp)[0] is None
        (tmp / "fcount").mkdir()
        assert read_f_cell(tmp)[0] is None
        cases = [({"F": {"bars": "4h", "universe": "S12 top 6"}}, {"bars": "4h", "universe": "S12 top 6"}),
                 ({"chosen": "S16 1-hour x S12 top 10"}, {"bars": "1h", "universe": "S12 top 10"}),
                 ({"counts": [{"row": "S8", "universe": "S12 top 10", "is_F": False, "tranches": 900},
                              {"row": "R0", "universe": "BTC/ETH/SOL", "is_F": True, "tranches": 40}]},
                  {"bars": "1d", "universe": "BTC/ETH/SOL"}),
                 ({"meta": {"x": 1}, "selection": {"F": {"cell": "R0 daily, S12_top6"}}},
                  {"bars": "1d", "universe": "S12 top 6"})]
        for J, want in cases:
            (tmp / "fcount" / "f.json").write_text(json.dumps(J))
            got, _ = read_f_cell(tmp)
            assert got == want, (J, got)
        (tmp / "fcount" / "f.json").unlink()
        pd.DataFrame({"bars": ["1d", "4h", "1h"], "universe": ["S12 top 6"] * 3, "is_F": [False, True, False]}).to_csv(
            tmp / "fcount" / "counts.csv", index=False)
        assert read_f_cell(tmp)[0] == {"bars": "4h", "universe": "S12 top 6"}
        nm, cfg, urow = f_spec({"bars": "4h", "universe": "S12 top 6"})
        assert cfg == be.ROWS["S8"] and urow == "S12_top6"
        assert f_spec({"bars": "1d", "universe": "BTC/ETH/SOL"})[2] is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    say("  F's identity read from results_bb/fcount/ (JSON forms and a CSV flag); absent -> skipped")


def _st_scorecard_logic(say) -> None:
    v = scorecard_verdict
    assert v((0.01, 0.02), (-1, 1), False)[0] == "helps"
    assert v((-0.02, -0.01), (-1, 1), False)[0] == "hurts"
    assert v((-0.01, 0.02), (0.1, 0.2), False)[0] == "no detectable effect"
    assert v((0.0, 0.0), (0.0, 0.0), True)[0] == "no-op as coded"
    assert v((0.0, 0.0), (0.1, 0.3), False, account_only=True)[0] == "helps"
    assert v((np.nan, np.nan), (0.1, 0.3), False)[0] == "no detectable effect"
    c = combine_verdicts
    assert c(["helps", "helps"]) == "helps" and c(["hurts"]) == "hurts" and c(["helps", "hurts"]) == \
        "no detectable effect" and c(["no-op as coded"] * 2) == "no-op as coded" and c([]) == "not testable"
    assert c(["helps", "no detectable effect"]) == "no detectable effect"
    assert set(RULES) == set(range(1, 16)) and all(HOLM_RULES[r] for r in (2, 4, 6, 7, 12, 13, 14, 15))
    p = np.array([0.01, 0.04, np.nan, 0.03, 0.5])
    D = _bh_col(pd.DataFrame({"p_expl": p}))
    assert np.allclose(D["p_expl_bh"].to_numpy(), bs.bh(p), equal_nan=True) and (D["p_label"] == P_LABEL).all()
    try:
        _check_audit([{"x": 1}], "test")
        raise AssertionError("fill audit not enforced")
    except RuntimeError:
        pass
    _check_audit([], "test")
    say("  scorecard verdict categories, multi-comparison rule, Benjamini-Hochberg column, fill-audit guard")


def _st_end_to_end(say) -> None:
    """Every part through run() (4 processes, fork) on synthetic injected hours, minutes, stocks and TV exports."""
    import shutil
    import tempfile
    from types import SimpleNamespace
    from analysis_2026 import bb_bench as bb
    from analysis_2026 import bb_tests as bt
    tmp = Path(tempfile.mkdtemp(prefix="bb_desc_e2e_"))
    t0 = time.time()
    try:
        src, conf = synthetic_setup()
        res = run(tmp, jobs=4, src=src, conf=conf, say=lambda s: None)
        assert res["parts"] == sorted(PARTS), res["parts"]
        for p_ in PARTS:
            m = json.loads((tmp / p_ / "meta.json").read_text())
            assert m.get("fill_audit_violations", 0) == 0
        R = pd.read_csv(tmp / "rows" / "rows.csv")
        runs, sl, sep = win_split(conf)
        assert set(sl) == set(conf.halves) and set(sep) == {f"{h} {SEP_TAG}" for h in conf.halves}
        allw = set(runs) | set(sl) | set(sep)
        labels = list(conf.rows) + [f"{r}@{f}" for r in FEE_ROWS for f in FEES[1:]] + ["F", "F@vip", "F@zero"]
        assert set(R["row"]) == set(labels), set(labels) ^ set(R["row"])
        assert all(set(g) == allw for _, g in R.groupby("row")["window"])
        zx = R[R["group"] == "exZEC"]
        assert set(zx["row"]) == {"S12_top6", "S17", "F", "F@vip", "F@zero"}
        assert R["n_positions"].sum() > 0
        # S17 without ZEC holds R0's trades in a four-slot account; S19 = R0's trades (assembly-only change)
        for w in allw:
            r0 = R[(R.row == "R0") & (R.window == w)].iloc[0]
            s17x = R[(R.row == "S17") & (R.window == w) & (R.group == "exZEC")].iloc[0]
            s19 = R[(R.row == "S19") & (R.window == w)].iloc[0]
            assert s17x["n_positions"] == r0["n_positions"] and s17x["K"] == 4 and r0["K"] == 3
            assert _close(s17x["mean_ret"], r0["mean_ret"]) or (np.isnan(s17x["mean_ret"]) and np.isnan(r0["mean_ret"]))
            assert s19["n_positions"] == r0["n_positions"]
        # independent recomputation of R0 on the Full window (engine + assemble + drift adjustment directly)
        fa, fb = conf.windows["Full"]
        direct = {s_: be.simulate_coin(s_, be.ROWS["R0"], fa, fb, hours=src.hours[s_], minutes=src.minutes.get(s_),
                                       detail=False) for s_ in conf.primary}
        a0 = be.assemble(direct, be.ROWS["R0"], fa, fb, idle_tbill=False, k_slots=len(conf.primary))
        a1 = be.assemble(direct, be.ROWS["R0"], fa, fb, idle_tbill=True, k_slots=len(conf.primary))
        r0 = R[(R.row == "R0") & (R.window == "Full")].iloc[0]
        assert _close(r0["multiple"], a0["equity"].iloc[-1] / a0["equity"].iloc[0], 1e-9)
        assert r0["n_positions"] == sum(len(v["trades"]) for v in direct.values())
        adj = np.concatenate([bs.drift_adjust(v["trades"], v["expo"], {s_: bs.returns_from_hours(src.hours[s_])})
                              .to_numpy(float) for s_, v in direct.items() if len(v["trades"])])
        assert _close(r0["mean_adj"], np.nanmean(adj), 1e-9)
        # finding 4: the zero-interest Sharpe is the Sharpe of the 0%-cash account's raw daily returns
        x0 = a0["ret"].to_numpy(float)
        sh_raw = x0.mean() / x0.std(ddof=1) * math.sqrt(365)
        x0e = a0["excess"].to_numpy(float)
        assert _close(r0["sharpe_zero_interest"], sh_raw, 1e-9) and not _close(sh_raw, x0e.mean() / x0e.std(ddof=1) *
                                                                               math.sqrt(365), 1e-6)
        # finding 2: a half is a slice of the Full run - the Full run's positions with entry1 in the half (their
        # full-run return, exit and open flag) and the Full account's daily returns between the half's dates
        TT = pd.concat([v["trades"] for v in direct.values()], ignore_index=True)
        for h, (x, y) in sl.items():
            rh = R[(R.row == "R0") & (R.window == h) & (R.group == "all")]
            assert len(rh) == 1 and rh["half_method"].iloc[0] == HALF_SLICE
            rh = rh.iloc[0]
            m = _between_mask(TT["entry1_time"], x, y)
            assert rh["n_positions"] == int(m.sum()) and _close(rh["mean_ret"], TT["ret"][m].mean(), 1e-9)
            cl = m & ~TT["open_at_end"].astype(bool).to_numpy()
            assert rh["n_closed"] == int(cl.sum()) and _close(rh["hit_rate"], float((TT["ret"][cl] > 0).mean()), 1e-12)
            rr = _between(a0["ret"], x, y).to_numpy(float)
            assert len(rr) == (pd.Timestamp(y) - pd.Timestamp(x)).days + 1
            assert _close(rh["multiple"], np.prod(1.0 + rr), 1e-9) and _close(rh["days"], len(rr))
            rs = R[(R.row == "R0") & (R.window == f"{h} {SEP_TAG}")].iloc[0]
            assert rs["half_method"] == HALF_SEP
        # straddling positions: a position entered in the first half and closed in the second is closed in the slice
        x1, y1 = sl[conf.halves[0]]
        strad = _between_mask(TT["entry1_time"], x1, y1) & ~_between_mask(TT["exit_time"], x1, y1)
        assert strad.any(), "the synthetic paths should hold a position across the half boundary"
        H0 = pd.read_csv(tmp / "headline" / "headline.csv")
        h0 = H0[(H0.strategy == "R0 (L=3)") & (H0.window == "Full") & (H0.group == "all")].iloc[0]
        assert _close(h0["multiple"], r0["multiple"]) and h0["n_positions"] == r0["n_positions"]
        assert _close(h0["sharpe_zero_interest"], sh_raw, 1e-9)
        for h in sl:
            hh = H0[(H0.strategy == "R0 (L=3)") & (H0.window == h) & (H0.group == "all")].iloc[0]
            rh = R[(R.row == "R0") & (R.window == h) & (R.group == "all")].iloc[0]
            assert hh["half_method"] == HALF_SLICE and _close(hh["multiple"], rh["multiple"]) and \
                hh["n_positions"] == rh["n_positions"] and np.isnan(hh["cagr_tax_pct"])
        # the answer map's primary halves = bb_tests.beats_holding on the same series (verdicts.txt's numbers)
        A = pd.read_csv(tmp / "headline" / "answer_map.csv")
        bh1 = bb.bh_crypto(list(conf.primary), fa, fb, idle_tbill=True, hours=src.hours)["ret"]
        ref = bt.beats_holding(a1["ret"], bh1, SimpleNamespace(B_port=conf.B_port), 365, sl, "x")
        ac = A[(A.asset_group == "crypto (BTC/ETH/SOL)") & (A.half_method == AM_SLICE)].set_index("span")
        assert ac["decides_sentence"].all() and not A[A.half_method == AM_SEP]["decides_sentence"].any()
        for span in ["full"] + list(sl):
            assert _close(ac.loc[span, "mean_log_growth_diff_ann"], ref[span]["estimate"], 1e-9)
            assert _close(ac.loc[span, "ci95_lo"], ref[span]["ci95"][0], 1e-9) and \
                _close(ac.loc[span, "ci95_hi"], ref[span]["ci95"][1], 1e-9)
        assert bool(ac["above_zero_full_and_both_halves"].iloc[0]) == ref["interval_above_zero_full_and_both_halves"]
        assert (A.groupby(["asset_group", "half_method"]).size() == 3).all() and (A["days"] > 0).all()
        assert set(A["asset_group"]) == {"crypto (BTC/ETH/SOL)", "stocks (point-in-time members)", "ETFs (14)"}
        hs = H0[(H0.asset_group != "crypto") & (H0.half_method == HALF_SLICE)]
        assert len(hs) == 2 * len(conf.stock_halves) and (hs["days"] > 0).all() and (hs["n_positions"] > 0).all()
        P = pd.read_csv(tmp / "rows" / "pre_perpetual.csv")
        assert set(P["row"]) == set(PRE_ROWS) and set(P["group"]) == {"BTC/ETH/SOL", "all listed", "all listed exZEC"}
        C = pd.read_csv(tmp / "rows" / "per_coin.csv")
        assert {"pool", "pool exZEC"} <= set(C["sym"]) and set(conf.per_coin) <= set(C["sym"])
        assert set(C[C.sym == "pool"]["window"]) == allw
        H = H0
        assert {"R0 (L=3)", "S1 (L=1)"} <= set(H["strategy"]) and H["strategy"].str.startswith("F (").any()
        assert set(H["asset_group"]) == {"crypto", "stocks", "ETFs"}
        assert H[H.window.isin(SINGLE_PATH)]["label"].eq("single 16-month path").all()
        cr = H[H.asset_group == "crypto"]
        assert cr["multiple_lo"].notna().all() and (cr["multiple_lo"] <= cr["multiple"] + 1e-9).all() and \
            (cr["multiple"] <= cr["multiple_hi"] + 1e-9).all()
        assert cr["bh_multiple"].notna().all() and cr["ml_multiple"].notna().all()
        assert cr[cr.half_method != HALF_SLICE]["cagr_tax_pct"].notna().all()
        assert cr["sharpe_zero_interest_lo"].notna().all()
        assert H[H.asset_group != "crypto"]["sharpe_zero_interest_lo"].isna().all()
        # finding 6: F on an S12 universe is flagged in headline.csv itself (not the same coins)
        fr = cr[cr.strategy.str.startswith("F (")]
        assert (~fr["bench_same_coins"].astype(bool)).all() and fr["bench_note"].str.startswith("not the same").all()
        assert cr[~cr.strategy.str.startswith("F (")]["bench_same_coins"].astype(bool).all()
        # finding 5: every exploratory p in a table is Benjamini-Hochberg adjusted within it, and labelled
        for f_, cols in (("headline/headline.csv", ("p_expl", "p_ret")), ("rows/rows.csv", ("p_expl", "p_ret")),
                         ("rows/per_coin.csv", ("p_expl", "p_ret")), ("rows/pre_perpetual.csv", ("p_expl", "p_ret")),
                         ("explore/stocks.csv", ("p_expl", "p_ret")), ("explore/stock_tickers.csv", ("p_expl", "p_ret")),
                         ("scorecard/scorecard_detail.csv", ("trade_p", "trade_adj_p", "sharpe_p"))):
            X = pd.read_csv(tmp / f_)
            for c in cols:
                assert np.allclose(X[c + "_bh"].to_numpy(float), bs.bh(X[c].to_numpy(float)), equal_nan=True), (f_, c)
            assert (X["p_label"] == P_LABEL).all(), f_
        S = pd.read_csv(tmp / "scorecard" / "scorecard.csv")
        assert list(S["rule"]) == list(range(1, 16))
        v = dict(zip(S["rule"], S["verdict"]))
        sm = json.loads((tmp / "scorecard" / "meta.json").read_text())
        # no primary results in this directory: the Holm-family rules are pending, and say so (finding 1)
        assert v[9] == "not testable" and all(v[r] == "pending" for r in HOLM_RULES)
        assert sm["holm_verdicts_pending"] and sm["pending_rules"] == sorted(HOLM_RULES)
        assert all(v[r] in ("helps", "hurts", "no detectable effect", "no-op as coded") for r in (1, 3, 5, 8, 10, 11))
        Dd = pd.read_csv(tmp / "scorecard" / "scorecard_detail.csv")
        r11 = Dd[Dd.rule == 11].iloc[0]
        assert r11["trade_effect"] == 0 and r11["verdict_basis"].startswith("sleeve Sharpe")
        assert (Dd["verdict_descriptive"] != "not run").all()
        # finding 3: S12 comparisons whose universe holds ZEC have an exZEC twin (top 6 and top 10, not top 3)
        tw = Dd[Dd.exZEC.astype(bool)]
        assert set(tw["rule"]) == {5} and set(tw["comparison_arm"]) == {"S12_top6" + EXZEC, "S12_top10" + EXZEC}
        for nm in ("S12_top6", "S12_top10"):
            b_ = Dd[(Dd.rule == 5) & (Dd.comparison_arm == nm)].iloc[0]
            x_ = tw[tw.comparison_arm == nm + EXZEC].iloc[0]
            nz = len(_st_zec_trades(src, conf, nm))
            assert nz > 0 and x_["n_comparison_arm"] == b_["n_comparison_arm"] - nz
            assert x_["n_rule_arm"] == b_["n_rule_arm"]
        assert S[S.rule == 5]["verdict_descriptive_exZEC"].iloc[0] in ("helps", "hurts", "no detectable effect",
                                                                       "no-op as coded")
        GR = pd.read_csv(tmp / "explore" / "grids.csv")
        assert len(GR) == 16 and set(GR["fill"]) == {"through", "touch"} and GR["diff_ann"].notna().all()
        SR = pd.read_csv(tmp / "explore" / "stocks.csv")
        assert len(SR) == 2 * 6 and SR["n_positions"].gt(0).all() and SR["book_multiple"].notna().sum() == 2 * 5
        TR = pd.read_csv(tmp / "explore" / "stock_tickers.csv")
        assert len(TR) == 7 + 14 and set(TR[TR.not_interpreted].ticker) <= set(TR.ticker)
        assert (TR[TR.group == "user's tickers"]["not_interpreted"] == (TR[TR.group == "user's tickers"]["n_trades"]
                                                                        < TICKER_FLOOR)).all()
        G = pd.read_csv(tmp / "routes" / "gate.csv")
        assert len(G) > 0 and set(G["route"]) == {"RH", "ETF", "CB"}
        assert G["basis"].str.startswith("Full window").any() and G["basis"].str.startswith("longest").any()
        # finding 3: RH's pool with ZEC (RH24) beside the same pool without it, on both bases; with these route coins
        # the pool without ZEC is BTC/ETH/SOL, so its row equals bb_bench's own BTC/ETH/SOL group row
        Sg = pd.read_csv(tmp / "routes" / "summary.csv")
        rh = Sg[Sg.route == "RH"]
        assert set(rh["group"]) == {"BTC/ETH/SOL", "RH24", "RH24" + EXZEC}
        for (row, basis), g in rh.groupby(["row", "basis"]):
            gi = g.set_index("group")
            assert gi.loc["RH24", "K"] == 4 and gi.loc["RH24" + EXZEC, "K"] == 3
            for c in ("fm_cagr_pre", "fm_cagr_tax", "bh_cagr_tax", "expected_false_TRADE", "n_TRADE"):
                assert _close(gi.loc["RH24" + EXZEC, c], gi.loc["BTC/ETH/SOL", c], 1e-12), (row, basis, c)
        rm = json.loads((tmp / "routes" / "meta.json").read_text())["exZEC"]
        # bb_bench now carries the RH24 exZEC group itself, so the extra calls are skipped; otherwise they must agree
        assert rm["needed"] and (rm["skipped_bb_bench_has_group"] or rm["gate_rows_identical"] is True)
        Ac = pd.read_csv(tmp / "routes" / "accounts.csv")
        assert ("RH24" + EXZEC) in set(Ac["group"])
        T = pd.read_csv(tmp / "tv" / "stats.csv")
        assert len(T) == 2 * 3
        # a subset re-run writes only its part
        run(tmp, which="tv", jobs=1, src=src, conf=conf, say=lambda s: None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    say(f"  end to end on synthetic injected data: {res['engine_runs']} engine runs, every part written, fill audits "
        f"empty; R0's row = a direct engine + assemble + drift_adjust recomputation; halves = slices of the Full run "
        f"(positions by entry1, full-run returns, the Full account's days) with separate runs as a labelled "
        f"sensitivity; the answer map = bb_tests.beats_holding; zero-interest Sharpe = raw 0%-cash Sharpe; BH on every "
        f"p column; ZEC twins in routes (RH24 exZEC) and the scorecard (S12 top 6 / top 10); F flagged 'not the same "
        f"coins'; Holm rules pending without primary results [{time.time() - t0:.0f}s]")


def _st_zec_trades(src: Src, conf: Conf, row: str) -> pd.DataFrame:
    """ZEC's positions in an S12 arm on the Full window (the exZEC twin's known answer), simulated directly."""
    coins, K, masks = src.universes[row]
    if ZEC not in coins:
        return pd.DataFrame()
    a, b = conf.windows["Full"]
    r = be.simulate_coin(ZEC, be.ROWS[row], a, b, hours=src.hours[ZEC], minutes=src.minutes.get(ZEC), detail=False,
                         entry_allowed=masks.get(ZEC))
    return r["trades"]


def _fake_tests(level: float = bs.LEVEL_NOEDGE) -> tuple:
    """The 12 tests in bb_tests' own record format (bb_tests._result) with known verdicts for the scorecard's Holm
    rules: H3 forced INCONCLUSIVE, H4 NO EDGE (HARMS), H6 INCONCLUSIVE (conditions fail), H7 PASS, H8 NO EDGE, H9
    INCONCLUSIVE."""
    from analysis_2026 import bb_tests as bt

    def comp(name, p, ub, E_):
        return {"name": name, "p": p, "estimate": 0.01, "se": 0.004, "ci95": [-0.01, 0.03], "ub95": ub,
                "ub_noedge": ub, "E": E_, "mde": 0.014, "level_noedge": level, "level95": 0.95}

    def rec(tid, comps, conds=True, force=False, flags=None):
        return bt._result(tid, comps, {"g": conds}, {comps[0]["name"]: {"h1": 0.01, "h2": 0.02}}, flags or {}, force)

    T = {"H1": rec("H1", [comp("c", 0.3, 0.02, 0.005)], flags={"month_dropped_mean": 0.001}),
         "H2": rec("H2", [comp("vs_buy_and_hold", 0.4, 0.5, 0.1), comp("vs_moneyline", 0.3, 0.5, 0.1)]),
         "H3": rec("H3", [comp("c", 1e-4, 0.02, 0.0025)], force=True),
         "H4": rec("H4", [comp("c", 0.6, -0.01, 0.0025)]),
         "H5": rec("H5", [comp("c", 0.2, 0.05, 0.0025)]),
         "H6": rec("H6", [comp("c", 2e-4, 0.01, 0.0025)], conds=False),
         "H7": rec("H7", [comp("c", 1e-4, 0.02, 0.0025)]),
         "H8": rec("H8", [comp("a", 0.3, 0.001, 0.0025), comp("b", 0.2, 0.01, 0.0025)]),
         "H9": rec("H9", [comp("c", 0.5, 0.5, 0.02)]),
         "H10": rec("H10", [comp("c", 0.6, 0.05, 0.01)]),
         "HS1": rec("HS1", [comp("trade_drift_adjusted_mean", 0.3, 0.02, 0.005),
                            comp("sharpe_vs_benchmark", 0.4, 0.5, 0.1)], flags={"month_dropped_mean": 0.001}),
         "HS2": rec("HS2", [comp("trade_drift_adjusted_mean", 0.3, 0.02, 0.005),
                            comp("sharpe_vs_benchmark", 0.4, 0.5, 0.1)], flags={"month_dropped_mean": 0.001})}
    want = {"H3": "INCONCLUSIVE", "H4": "NO EDGE (HARMS)", "H6": "INCONCLUSIVE", "H7": "PASS", "H8": "NO EDGE",
            "H9": "INCONCLUSIVE"}
    return {"meta": {"level_noedge": level, "written": "bb_desc selftest"}, "tests": T}, want


def _st_order(say) -> None:
    """Finding 1 (the pipeline's own order): desc run with primary/tests.json in bb_tests' format, no verdicts.csv and
    no fcount/. F's counts are written by bb_fit before any engine run here, F is reported in rows and the headline,
    and the Holm-family rules take bb_tests.report's verdicts, without writing results_bb's report files."""
    import os
    import shutil
    import tempfile
    from analysis_2026 import bb_tests as bt
    tmp = Path(tempfile.mkdtemp(prefix="bb_desc_order_"))
    t0 = time.time()
    try:
        J, want = _fake_tests()
        (tmp / "primary").mkdir()
        (tmp / "primary" / "tests.json").write_text(json.dumps(J))
        # the known answers, independently: bb_tests.report on a separate copy
        ref = Path(tempfile.mkdtemp(prefix="bb_desc_order_ref_"))
        (ref / "primary").mkdir()
        shutil.copy2(tmp / "primary" / "tests.json", ref / "primary" / "tests.json")
        V = bt.report(ref, say=lambda *a, **k: None).set_index("test_id")
        shutil.rmtree(ref, ignore_errors=True)
        assert all(V.loc[t, "label"] == w for t, w in want.items()), V["label"].to_dict()
        src, conf = synthetic_setup()
        conf = replace(conf, f_cell=None, windows={k: conf.windows[k] for k in ("Full", "W16")}, halves=(),
                       rows=("R0",), fee_rows=(), per_coin=("BTC",), pre_coins=("BTC",), stock_univ=())
        seen = {}
        real_need = Sims.need

        def need(self, keys):                  # the F counts must already be on disk at the first engine run
            seen.setdefault("fcount_at_first_engine_run", (tmp / "fcount" / "F.json").exists())
            return real_need(self, keys)

        Sims.need = need
        try:
            run(tmp, which="rows,headline,scorecard", jobs=4, src=src, conf=conf, say=lambda s: None)
        finally:
            Sims.need = real_need
        assert seen["fcount_at_first_engine_run"] is True
        F = json.loads((tmp / "fcount" / "F.json").read_text())
        assert F["written_before_returns"] is True and (tmp / "fcount" / "counts.csv").exists()
        cell, _ = read_f_cell(tmp)
        assert cell == {"bars": F["F"]["bars"], "universe": F["F"]["universe"]}
        C = pd.read_csv(tmp / "fcount" / "counts.csv")
        assert int(C["is_F"].sum()) == 1 and C.loc[C["is_F"], "abs_diff_1462"].iloc[0] == C["abs_diff_1462"].min()
        R = pd.read_csv(tmp / "rows" / "rows.csv")
        assert {"F", "F@vip", "F@zero"} <= set(R["row"]) and json.loads((tmp / "rows" / "meta.json").read_text())[
            "F_included"]
        H = pd.read_csv(tmp / "headline" / "headline.csv")
        assert H["strategy"].eq(f_spec(cell)[0]).any()
        S = pd.read_csv(tmp / "scorecard" / "scorecard.csv").set_index("rule")
        for rule, tid in HOLM_RULES.items():
            assert S.loc[rule, "verdict"] == V.loc[tid, "label"] == want[tid], (rule, S.loc[rule, "verdict"])
            assert S.loc[rule, "verdict_source"].startswith("bb_tests.report")
        assert not json.loads((tmp / "scorecard" / "meta.json").read_text())["holm_verdicts_pending"]
        assert not (tmp / "verdicts.csv").exists() and not (tmp / "verdicts.txt").exists()
        # sources: a verdicts.csv at least as new as tests.json is read; an older one is not; incomplete -> pending
        Vw = V.reset_index()
        Vw.loc[Vw.test_id == "H7", "label"] = "NO EDGE"              # marks which source was used
        Vw.to_csv(tmp / "verdicts.csv", index=False)
        tjs = (tmp / "primary" / "tests.json").stat().st_mtime
        os.utime(tmp / "verdicts.csv", (tjs + 10, tjs + 10))
        v, src_ = test_verdicts(tmp)
        assert v["H7"][0] == "NO EDGE" and src_ == "results_bb/verdicts.csv"
        os.utime(tmp / "verdicts.csv", (tjs - 10, tjs - 10))
        v, src_ = test_verdicts(tmp)
        assert v["H7"][0] == "PASS" and src_.startswith("bb_tests.report")
        (tmp / "verdicts.csv").unlink()
        del J["tests"]["H10"]
        (tmp / "primary" / "tests.json").write_text(json.dumps(J))
        v, src_ = test_verdicts(tmp)
        assert v == {} and src_.startswith("pending") and "H10" in src_
        # an existing F is read, never recounted (bb_fit keeps the first write)
        mt = (tmp / "fcount" / "F.json").stat().st_mtime
        run(tmp, which="rows", jobs=1, src=src, conf=replace(conf, rows=(), per_coin=(), pre_coins=()),
            say=lambda s: None)
        assert read_f_cell(tmp)[0] == cell and (tmp / "fcount" / "F.json").stat().st_mtime == mt
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    say(f"  pipeline order (finding 1): no fcount/ -> bb_fit's F counts written before the first engine run, F in "
        f"rows and headline; no verdicts.csv -> the Holm rules take bb_tests.report's verdicts on tests.json (nothing "
        f"written to results_bb); a newer verdicts.csv is read, an older one is not; incomplete tests -> pending "
        f"[{time.time() - t0:.0f}s]")


def selftest() -> None:
    t0 = time.time()
    say = print
    say("bb_desc selftest")
    _st_trade_stats(say)
    _st_account_stats(say)
    _st_answer_map(say)
    _st_f_reader(say)
    _st_scorecard_logic(say)
    _st_end_to_end(say)
    _st_order(say)
    say(f"bb_desc selftest passed in {time.time() - t0:.0f}s")


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m analysis_2026.bb_desc")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="write the descriptive outputs (prints counts only)")
    r.add_argument("--out", default=str(RES), help="results root (default analysis_2026/results_bb)")
    r.add_argument("--which", default=None, help=f"comma-separated subset of {','.join(PARTS)}")
    r.add_argument("--jobs", type=int, default=4)
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest()
    else:
        run(a.out, which=a.which, jobs=a.jobs)


if __name__ == "__main__":
    _main()
