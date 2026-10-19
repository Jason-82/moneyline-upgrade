"""
Controls of the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md, "Controls (run before primary
results are read)": engine known answer, inference known answer, look-ahead check, liquidation check, fill audit, grid
path check, indicator cross-check; and Addendum 2's "Inference control" ruling). "A failed control stops the study
until it is fixed": a failed (or crashed) control makes all_passed false, and bb_replica's `primary` reads it.
Contract: the scratchpad's bb_engine_spec.md, "Integration layer". Every simulation is done by the six build modules
(bb_data, bb_engine, bb_stats, bb_stocks, bb_grid, bb_bench); this module only feeds them known-answer or perturbed
inputs, compares their outputs and writes the verdicts.

    python3 -m analysis_2026.bb_controls run [--quick] [--workers 4] [--out DIR] [--only a,b] [--tmp DIR]
    python3 -m analysis_2026.bb_controls selftest

Outputs (analysis_2026/results_bb/controls/; a --quick run writes results_bb/controls_quick/ and is marked
"quick": true, "valid_gate": false, since its sizes are below the pre-registered ones)
  summary.json   {control: {passed, headline numbers}, all_passed, level95, level_noedge, quick, valid_gate, ...}
  summary.txt    the same in words
  inference.json level95 (the bootstrap-t level that every 95% NO EDGE-type bound uses) and level_noedge (the NO EDGE
                 level that replaces 1 - 0.05/12), plus the inference control's numbers
  <control>.json one file per control with every number it computed (no real-data strategy return is written: the
                 real-data controls record counts and equal / not-equal flags only)

Public API
  engine_known_answer(quick=False, workers=4)   inference_known_answer(quick=False, workers=4, n_paths=200, ...)
  lookahead_check(quick=False, workers=4, tmp=None)   liquidation_check()   fill_audit(quick=False, workers=4)
  grid_path_check()   indicator_crosscheck()   run(quick=False, out=None, workers=4, only=None, tmp=None)
  helpers: recompute_fees, size_rule, draw_cuts, perturb_data_dir, ic_hours, compare_frames, pending_decisions,
           bench_fill_audit

The controls and their pass rules (pre-registration text in quotes)
1. engine_known_answer.
   (a) "On a synthetic hourly series whose price is a martingale (zero mean simple return, i.e. log drift -sigma^2/2),
   S1's and R0's mean trade return per unit of M, before costs and funding, is within 2 SE of zero over at least
   20,000 trades. After costs it is about minus the round-trip cost." Generator: bb_engine._gbm_hours (hourly GBM,
   exact Brownian-bridge highs and lows), 160 coins x 50 years at 1%/h, seeds 20261018 + i, as bb_engine's self-test.
   Rows ROWS["S1"] and ROWS["R0"] with fees="zero" (before costs; the synthetic frames have no funding) and with the
   base fees. Pass: >= 20,000 trades and |mean| <= 2 SE (SE = SD / sqrt(n)) for each zero-fee row; for each base row
   |mean + mean recomputed fee| <= 2 SE ("about minus the round-trip cost": the gross mean is within sampling error
   of zero; no sign is required, unlike G-A's "negative after fees"), where the fee of every position is recomputed
   from its fills (recompute_fees: quantities rebuilt from the entry / add fills, taker 0.05% + slippage 0.07% per
   side on entries, adds and closes, the 0.02% maker fee on the TP half, nothing on a liquidation) and must equal the
   engine's `fees` to 1e-12; and ret_gross - ret - fees - funding = 0 to 1e-12; fill audit empty.
   (b) "The drift-adjusted mean is about zero both with and without a constant drift": bb_engine._drift_worker (S1,
   no fees, bb_stats.drift_adjust on the engine's exposure), 64 coins x 50 years, drift 0 and +0.01%/h. Pass:
   |drift-adjusted mean| <= 2 SE at both drifts, and the unadjusted mean > 2 SE at the positive drift (the drift is
   there to be removed).
   (c) "G-A's mean P&L is within 2 SE of zero before fees and negative after fees": bb_grid._mg_coin (1-minute GBM,
   R0 from bb_engine on the same data, G-A at zero and base fees), 240 coins x 730 days at 2%/day, as bb_grid's
   self-test. Pass: |mean| <= 2 SE per deployment at zero fees, mean < 0 at base fees, every fill audit empty.
   (d) "On a synthetic series with persistent trends, S1 is positive": bb_engine's regime-drift generator (drift
   +-0.08%/h in regimes of mean length 90 days, 12 coins x 20 years). Pass: ROWS["S1"] (base fees) mean > 2 SE; the
   zero-fee mean is reported beside it.
2. inference_known_answer (Addendum 2: "It runs on the engine's S1 at L = 1, with no fees (so the true mean is zero),
   on 200 synthetic three-coin paths"). Each path (ic_hours): hourly simple returns r = sigma z, z standardized Student
   t(4) (fat tails), cross-correlation 0.8, zero arithmetic drift (each price a martingale), sigma = 0.61 / 0.79 / 1.21
   a year (the realized hourly volatility of BTC / ETH / SOL 2020-01..2026-10, a benchmark statistic), intrahour
   highs and lows from a Brownian bridge; history from 2019-01-01 (warm-up), trades entered 2020-01-01..2026-10-16.
   ROWS["S1_L1"] with fees="zero" on each coin; bb_stats.drift_adjust per trade (H1's unit); then
   bb_stats.inference_control (month-clustered t, month-cluster bootstrap-t with 9,999 draws, the widening rule).
   Pass rule for the test's size ("rejects at most about 5% of the time at a nominal one-sided 5%"): the point
   rejection rate over the 200 paths is at most 5% (at most 10 of 200 rejections; bb_stats' ok_reject), the reading
   Addendum 2 gives the same phrase for the bound in the next sentence ("misses more than 5% of the time"); the
   exact (Clopper-Pearson) 95% interval and bb_stats' one-sided binomial flag (ok_reject_binomial) are reported
   beside it and decide nothing (coding choice 1). Bound: Addendum 2 is
   explicit ("If the bootstrap-t 95% bound misses more than 5% of the time, the level is widened to the smallest level
   at which it misses at most 5%. The NO EDGE level's tail (0.05/12) is then scaled by the same factor"), so the miss
   rate is the point rate against the true mean 0, and level95 / level_noedge are bb_stats' level_widened_at_0 /
   noedge_level_for(...) (0.95 and 1 - 0.05/12 when no widening is needed). The control fails only if the size rule
   fails or no level on bb_stats.LEVEL_GRID (to 0.999) brings the miss rate to 5%.
3. lookahead_check ("At least 50 cut times t are drawn at random minutes, never on an hour or day boundary: at least
   10 in 2025-06..2026-10, 10 on weekends and 10 within 2 h of an entry or exit window. For the stock engine, t falls
   inside a session. Every price after t is multiplied by 1.5 in the spot, perpetual, mark-price and 1-minute files
   (and in the stock files), and every volume after t by 0.5. Every order, fill, add, exit, liquidation, sizing,
   universe-rank and grid decision stamped before t must be unchanged, for R0, S1, S8, S11, S12, H4's touch arm, G-A
   and the stock version.")
   Crypto: 60 cuts (draw_cuts: 14 in 2025-06..2026-10, 12 on UTC weekends, 14 within 2 h of 06:00 / 10:00 / 13:00
   New York, 5 in the first three hours of a month (rank and daily-bar boundaries), 8 in the 1-minute era before W16,
   7 in 2020-2024; minute != 0). For each cut a temporary DATA directory is built (perturb_data_dir) holding the
   perturbed h1_spot / h1_um / h1_mark files of the 40 coins and of the S12 coins at the cut, the six m1_um files and
   every d1_um_all file (the funding files are linked unchanged: rates are not prices); bb_data.DATA / ALL_DIR are
   pointed at it and every bb_data / bb_engine cache is cleared, so bb_data.coin_hours, minutes, bars and
   volume_ranks and everything downstream are rebuilt from the perturbed files by the production code path. Bars
   that open after the bar containing t are scaled entirely; the bar straddling t keeps its open, has its high and
   close x 1.5 and its volumes x 0.5, except the perpetual hour of a 1-minute coin, which is rebuilt from its live
   perturbed minutes exactly as bb_data.minutes() returns them (high = max(live highs, open), low = min(live lows),
   close = last live close; bb_engine choice 22). Minutes from t on are scaled. Runs (loaded mode, 2020-01-01..
   2026-10-16): R0, S1, S1_L1, S8, S11 and H4's touch arm on BTC, ETH, SOL (1-minute), LINK (no 1-minute file) and EOS
   (delisted 2025-05: perp_end); S12_top3 / S12_top6 (pool 40), S12_top10 and S12_all_top3 (all perpetuals, crypto
   only) on every coin in that top k in the cut's month or the month before, with entry_allowed from
   bb_engine.s12_allowed (so from the perturbed ranks); G-A on BTC, ETH, SOL (R0 over the grid window as its input);
   bb_engine.assemble of R0 and S1_L1 on BTC/ETH/SOL (K = 3), of each S12 row on the coins in its top k in the cut's
   month or the month before (K = k), and of H10's overlay account, R0 + G-A on BTC/ETH/SOL through bb_grid.merge_ga
   (each deployment a pseudo-position sized at the slot's sleeve; grid window, idle T-bills, as bb_tests.test_h10);
   volume_ranks("40"), ("all", tradfi=False) and ("all", tradfi=True). Compared (compare_frames: exact equality,
   timestamps as int64): fills stamped before t (pos, kind, time, px, frac, cost, dir, cause), orders of positions
   entered before t (signal bar, entry, S, TP, L_used, L_max, liquidation price, flags), exits / liquidations stamped
   before t (exit time, price, reason, liquidated, tranche counts, net, gross, fees, funding), signals whose bar
   closed before t, each account's M and sizing equity of positions entered before t and its equity at every 00:00
   before t (exactly for the account rebuilt from the positions entered before t; to 1e-12 relative for the full
   runs' accounts, coding choice 7), rank rows of months starting before t, and G-A deployments started before t,
   ends before t, grid fills stamped before t and 00:00 marks before t. The perturbed runs' fill audits must be
   empty too, and the perturbation must change some later decision (it bites).
   Decisions pending at t (pending_decisions; controls review finding 2). The tables above select fills by their own
   stamps, so a decision taken at a close and filled later is invisible there while it is pending: R0, S11 and S12
   trend exits (decided at 00:00 UTC, filled at 13:00 New York, 17-18 h later), rules 6 and 15 (which decide whether
   such an exit is taken), S1's 01:00 fills, R0's entries (10-58 h after the signal close) and H4's resting buy-stop
   (placed at 00:00, filled 1-20 h later). Therefore every trend exit DECIDED before t (cause_time < t) is compared
   with its scheduled fill: the set of (position, decision time) must be equal, except a position the other run
   closed in full by a stop, take-profit, liquidation or delisting stamped between t and that fill (post-t prices
   legitimately pre-empt it); a rule 6 or rule 15 suppression that differs shows as an exit decided at that close in
   one run only. And every first tranche decided before t and filled after it that both runs take (same position
   and decision time; a post-t skip or re-check legitimately drops one) must have the same signal bar and stop bar,
   and the same S where the stop bar closed before t (H4's touch arm: "S comes from the same completed bar" as the
   resting level). Not compared, for want of a time-stamped decision log in bb_engine (known gap; the patch is in the
   build report): the level of H4's resting buy-stop itself, a rule 6 / rule 15 suppression whose exit the other run
   never reaches (pre-empted after t), and an add trigger whose fill an outage delays past t. A leak inside such a
   decision cannot move P&L relative to fill stamps: whatever it changes before its horizon is itself a fill and is
   compared. The selftest's planted leaks certify the fill-stamped tables for a one-day leak (longer than the
   17-18 h decision-to-fill lag of a trend exit, which they alone need) and exit_decisions for a 16-hour leak of rule
   6's mark inside that lag.
   Stocks: 50 cut times inside sessions (bb_stocks._cut_minutes: at least 14 within 2 h of the 09:30 open, the stock
   version's entry and exit time; none on an hour), on 26 random sessions 2001..2026, 12 in 2025-06..2026-10 and 12
   sessions on which a flat or close-only bar carries a pending entry or an open position. Names: 40 point-in-time
   members drawn with default_rng(20261019): 12 dead names, 12 of the 40 members with the most close-only sessions
   inside a pending entry or an open position of the full member run (a name whose whole history is close-only never
   has one), 16 others; the 14 ETFs; and TSLA, COIN, HOOD, CRCL. Perturbation: bb_stocks._perturb_after (bars after the cut session x 1.5; the session's own high,
   low and close x 1.5 with its open kept; the total-return index likewise; the flat / close_only flags kept from the
   source). Daily and weekly (S20) bars. Compared: tranches stamped before the cut, S / TP / price of entries before
   it, signals decided before the cut session, and (daily) the 20-slot member book's and the 14-slot ETF book's
   entries, M and equity before it (M and equity to 1e-12 relative, coding choice 7).
4. liquidation_check ("A hand-built path through the liquidation price liquidates exactly once, with the stated loss";
   R0 Liquidation row: "A liquidated position loses its isolated margin and nothing more"). Isolated margin, L = 3 and
   L = 5, long (R0) and short (S11): one tranche, and three tranches (both adds) with funding prints; every stop fails
   (the 2025-10-10 20:00-23:00 stress row) while the price crashes (spikes) through the liquidation price; plus a
   mark-price-only liquidation and the same crash with working stops (a stop, not a liquidation). Pass: exactly one
   'liq' fill and one liquidation in the log, no later fill or position, liquidation price = the hand computation
   avg x (1 -/+ (isolated margin - fees paid -/+ funding) / notional +/- mmr) to 1e-9, net = - posted margin to 1e-12,
   exit stamped at the crash hour's close, and bb_engine.assemble's account (K = 3) loses exactly M x posted margin.
5. fill_audit ("Every simulated fill is asserted, before costs, to lie within the [low, high] of the bar it fills
   in ... stamped after the bar close or order placement that caused it, and must never fall in a trades == 0 bar or
   a flat close-only stock bar. Any violation stops the run"): every engine's own audit (bb_engine._audit,
   bb_grid._audit, bb_stocks' audit) must be empty for R0, S1, S1_L1, S8, S11, S16 and H4's touch arm on all 40 coins
   2020-2026; G-A, G-B and G-0 (through and touch fills) on the six 1-minute coins with R0 over the grid window; the
   stock version (daily) on the members, the ETFs and the user's tickers 2001-2026, plus members on weekly bars (S20)
   and 1996-2000. H2's indicator benchmark (bb_bench.ml_coin, a simulator with its own fills whose fills_audit is
   empty by construction; controls review finding 3) is audited here by bench_fill_audit on all 40 coins: the
   perpetual vehicle over the Full window, the spot vehicle over the Full window and the pre-perpetual block. Each
   entry and signal exit must be an hour's open inside its [low, high], in a trades > 0, tradable hour, after the
   close of the daily bar whose state caused it (known at least 1 h before); a liquidation in a live hour whose mark
   (else last) low reached its price; a delisting close at a perp_end bar's close.
6. grid_path_check: bb_grid.path_check() ("matches the 1-second P&L to within 10% of gross grid profit").
7. indicator_crosscheck: bb_bench.indicator_crosscheck() ("reproduces HANDOFF 5.14's BTC 1x multiple to order of
   magnitude on the same window": |log10(multiple / 12.4)| < 1). A benchmark, not a strategy result.

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. Inference size rule: the point rate <= 5% (above), as Addendum 2 reads the identical "at most about 5%" of the
   bound's clause and as bb_stats.inference_control's ok_reject codes it. (The first build read "about" as "up to
   the sampling error of 200 paths" and passed while the Clopper-Pearson lower end was <= 0.05, i.e. up to 16 of 200
   rejections; a test of true size 9%, the date-cluster rate the pre-registration cites, then passed 37% of the
   time. Changed after the controls review, before any strategy result; the realized full run's 3 of 200 passes
   either rule.) At 200 paths a test of true size 3% (the pre-registration's synthetic month-cluster rate) passes
   96% of the time, one of exactly 5% 58%, one of 9% 2.5%. The bound's miss rate uses
   Addendum 2's point rule against the true mean 0 ("so the true mean is zero"). A pooled per-trade mean over 1,000
   further paths with disjoint seeds is reported as a diagnostic (true_mean_independent), with the rejection and miss
   rates centred on it; it decides nothing.
2. The look-ahead cuts are UTC minutes with minute != 0 (so never on an hour or a UTC / New York day boundary);
   "weekend" = a Saturday or Sunday UTC date; "within 2 h of an entry or exit window" = within 120 minutes of 06:00,
   10:00 or 13:00 New York local time on the cut's New York date. Cuts on 2025-01-14 and 2025-01-29 are not drawn (the
   six hours whose 1-minute and hourly bars disagree switch data source when rebuilt, bb_engine choice 22).
3. The hour (day, minute) bar that contains t is "after t" except for its open: its volume is halved whole, since a
   bar's volume is known only at its close. Funding rates and trade counts are not prices or volumes and are kept.
4. Stocks are perturbed in memory on the loaded frames (bb_stocks' own perturbation), not in data/universe_pit_all:
   the member files are divided by chart_factor() and flagged close-only from raw_pit at load time, and scaling one
   source file would change those derived columns before the cut, which the prices themselves do not.
5. The S12 look-ahead runs the coins in the top k in the cut's month or the month before (the coins that can hold a
   position or take a signal near the cut); every S12 coin's decisions depend only on its own prices and on rank rows
   of months up to its decisions, which are compared in full. Each S12 account (K = k) is assembled from the same
   coins: an account of a fixed coin set is a deterministic function of their positions, so its sizing and equity
   before t must be unchanged whichever coins it holds; the full row's account (every coin ever in the top k) would
   only repeat the same assembly over more coins.
6. An exception inside a control is recorded with its traceback and fails that control.
7. Account aggregates (bb_engine.assemble's M, sizing equity and daily equity; bb_stocks.portfolio's M and equity) are
   compared to a relative 1e-12 on the full runs; every per-position decision is compared exactly. assemble values the
   account each day as V[d] @ M over all positions of the run, those entered later contributing exact zeros; numpy's
   blocked summation rounds differently when the vector is longer, so a perturbed run with more positions after t
   moved earlier equity by under one ulp (the first full run: 2026-06-06 16:19, S1_L1, max relative 1.6e-16), while
   the account rebuilt from the positions entered before t was bit-identical. The exact comparison of that rebuilt
   account is kept beside the tolerance; a leak of post-cut prices (x 1.5) or positions would be ~12 orders larger.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
import time
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import stats as sps

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import bb_data as bd     # noqa: E402
from analysis_2026 import bb_engine as be   # noqa: E402
from analysis_2026 import bb_stats as bst   # noqa: E402
from analysis_2026 import bb_grid as bg     # noqa: E402

OUT = ROOT / "analysis_2026" / "results_bb" / "controls"
OUT_QUICK = ROOT / "analysis_2026" / "results_bb" / "controls_quick"
SEED = 20261018
LA_SEED = 20261019
FULL = ("2020-01-01", "2026-10-16")
H_NS = 3_600_000_000_000
MIN_NS = 60_000_000_000
DAY_NS = 24 * H_NS
CONTROLS = ("liquidation", "grid_path_check", "indicator_crosscheck", "engine_known_answer",
            "inference_known_answer", "fill_audit", "lookahead")


def _say(s: str) -> None:
    print(s, flush=True)


# ============================================================================ small utilities
def _pmap(fn, jobs, workers: int = 4):
    """Process-pool map (fork) that falls back to a serial loop only when no pool can be created; task errors
    propagate."""
    jobs = list(jobs)
    if workers <= 1 or len(jobs) <= 1:
        return [fn(j) for j in jobs]
    try:
        ex = cf.ProcessPoolExecutor(max_workers=min(workers, len(jobs)), mp_context=mp.get_context("fork"))
    except Exception as e:                                            # pragma: no cover
        _say(f"  (process pool unavailable: {e!r}; running serially)")
        return [fn(j) for j in jobs]
    with ex:
        return list(ex.map(fn, jobs, chunksize=1))


def _js(x):
    """JSON-safe copy: numpy scalars to Python, non-finite floats to None, timestamps to ISO strings, frames to records."""
    if isinstance(x, dict):
        return {str(k): _js(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_js(v) for v in x]
    if isinstance(x, pd.DataFrame):
        return [_js(r) for r in x.to_dict("records")]
    if isinstance(x, pd.Series):
        return {str(k): _js(v) for k, v in x.items()}
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(x))
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, np.ndarray):
        return [_js(v) for v in x.tolist()]
    if x is None or isinstance(x, str):
        return x
    return str(x)


def _mean_se(x) -> tuple[int, float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return n, float("nan"), float("nan")
    return n, float(x.mean()), float(x.std(ddof=1) / math.sqrt(n))


def _ns(col) -> np.ndarray:
    ix = pd.DatetimeIndex(col)
    if ix.tz is not None:
        ix = ix.tz_convert("UTC").tz_localize(None)
    return ix.as_unit("ns").asi8


def compare_frames(a: pd.DataFrame, b: pd.DataFrame, key: str | None = None, rtol: float = 0.0) -> tuple[bool, str]:
    """Equality of two decision tables (same rows in the same order; timestamps as int64 ns, NaT and NaN equal to
    themselves; floats exactly equal, or within rtol relative when rtol > 0: account aggregates only, coding choice 7).
    Returns (equal, a description of the first difference: column and row key, never values)."""
    a = a.reset_index(drop=True)
    b = b.reset_index(drop=True)
    if list(a.columns) != list(b.columns):
        return False, f"columns {list(a.columns)} vs {list(b.columns)}"
    if len(a) != len(b):
        return False, f"{len(a)} vs {len(b)} rows"
    for c in a.columns:
        x, y = a[c], b[c]
        if x.dtype.kind == "M" or y.dtype.kind == "M" or isinstance(x.dtype, pd.DatetimeTZDtype):
            u, v = _ns(x), _ns(y)
            eq = u == v
        elif x.dtype.kind in "fc" or y.dtype.kind in "fc":
            u, v = x.to_numpy(float), y.to_numpy(float)
            eq = (u == v) | (np.isnan(u) & np.isnan(v))
            if rtol > 0:
                with np.errstate(invalid="ignore"):
                    eq |= np.abs(u - v) <= rtol * np.maximum(np.abs(u), np.abs(v))
        else:
            u, v = x.to_numpy(object), y.to_numpy(object)
            na = pd.isna(x).to_numpy() & pd.isna(y).to_numpy()
            eq = na | np.array([p == q for p, q in zip(u, v)], dtype=bool)
        if not eq.all():
            i = int(np.flatnonzero(~eq)[0])
            k = f"{key}={a[key].iat[i]}" if key and key in a.columns else f"row {i}"
            return False, f"column {c} differs at {k}"
    return True, ""


def max_rel_diff(a: pd.DataFrame, b: pd.DataFrame) -> float:
    """Largest relative difference over the float columns of two equally long tables (0 if none)."""
    if len(a) != len(b) or not len(a):
        return 0.0
    out = 0.0
    for c in a.columns:
        if a[c].dtype.kind == "f" and c in b.columns:
            u, v = a[c].to_numpy(float), b[c].to_numpy(float)
            with np.errstate(invalid="ignore", divide="ignore"):
                r = np.abs(u - v) / np.maximum(np.abs(u), np.abs(v))
            r = r[np.isfinite(r)]
            if len(r):
                out = max(out, float(r.max()))
    return out


# ============================================================================ 1. engine known answer
def recompute_fees(tranches: pd.DataFrame, sym: str, fees: str = "base", tp_frac: float = 0.5) -> tuple[pd.Series, int]:
    """Fees per position recomputed from its fills (R0 Costs row; perpetual hours, no spot stand-in): quantities are
    rebuilt from the entry / add fills (notional frac of M at px), the TP sells tp_frac of the quantity at the maker
    fee, an exit / stop / delisting closes the rest at taker + slippage, a liquidation pays nothing (the isolated
    margin is lost). Returns (fee per position, number of closing fills whose notional disagrees with the engine's
    to 1e-9)."""
    rt = be.TAKER[fees] + (0.0 if fees == "zero" else (be.SLIP_MAJOR if sym in be.MAJORS else be.SLIP_OTHER))
    mk = be.MAKER[fees]
    out, bad = {}, 0
    t = tranches[tranches.kind != "end"]
    for pid, g in t.groupby("pos", sort=False):
        q, fee = 0.0, 0.0
        for kind, px, frac in zip(g.kind.to_numpy(), g.px.to_numpy(float), g.frac.to_numpy(float)):
            if kind in ("entry", "add"):
                q += frac / px
                fee += rt * frac
            elif kind == "tp":
                qt = tp_frac * q
                fee += mk * qt * px
                bad += abs(qt * px - frac) > 1e-9 * max(1.0, abs(frac))
                q -= qt
            elif kind in ("exit", "stop", "delist"):
                fee += rt * q * px
                bad += abs(q * px - frac) > 1e-9 * max(1.0, abs(frac))
                q = 0.0
            elif kind == "liq":
                q = 0.0
        out[pid] = fee
    return pd.Series(out, dtype=float), int(bad)


_MG_ROWS = {"S1_zero": replace(be.ROWS["S1"], fees="zero"), "R0_zero": replace(be.ROWS["R0"], fees="zero"),
            "S1_base": be.ROWS["S1"], "R0_base": be.ROWS["R0"]}


def _mg_job(args):
    """One martingale coin (bb_engine._gbm_hours, the engine self-test's generator and seeds) under the four rows."""
    i, n, sigma, seed = args
    df = be._gbm_hours(n, sigma, seed + i)
    sym = f"MG{i}"
    out = {}
    for k, cfg in _MG_ROWS.items():
        r = be.simulate_coin(sym, cfg, hours=df, mmr=0.005, detail=False)
        T = r["trades"]
        f_re, bad = recompute_fees(r["tranches"], sym, cfg.fees)
        f_re = f_re.reindex(T.pos.to_numpy()).fillna(0.0).to_numpy()
        out[k] = {"ret": T.ret.to_numpy(float), "gross": T.ret_gross.to_numpy(float), "fees": T.fees.to_numpy(float),
                  "fees_re": f_re, "funding": T.funding.to_numpy(float), "ntr": T.n_tranches.to_numpy(float),
                  "audit": len(r["fills_audit"]), "bad_notional": bad, "liq": int(T.liquidated.sum())}
    be.clear_cache()
    return out


def _trend_job(args):
    """bb_engine._trend's regime-drift path for coin i (drift +-0.08%/h, regimes of mean length 90 days), S1 at base
    and zero fees."""
    i, n, sigma, seed = args
    rng = np.random.default_rng(seed + i)
    lens = rng.geometric(1 / (90 * 24), size=n // (24 * 30) + 10)
    sgn = np.where(np.arange(len(lens)) % 2 == 0, 1.0, -1.0)
    drift = np.repeat(sgn * 0.0008, lens)[:n]
    df = be._gbm_hours(n, sigma, 1000 + seed + i, drift=drift)
    out = {}
    for k, cfg in (("S1_base", be.ROWS["S1"]), ("S1_zero", replace(be.ROWS["S1"], fees="zero"))):
        r = be.simulate_coin(f"TR{i}", cfg, hours=df, mmr=0.005, detail=False)
        out[k] = (r["trades"].ret.to_numpy(float), len(r["fills_audit"]))
    be.clear_cache()
    return out


def engine_known_answer(quick: bool = False, workers: int = 4, **_) -> dict:
    """Controls, "Engine known answer" (module docstring, control 1)."""
    t0 = time.time()
    res: dict = {"quick": quick}
    # (a) martingale, S1 and R0, before and after costs
    n_coins, years, sigma = (32, 50, 0.01) if quick else (160, 50, 0.01)
    n = int(years * 365 * 24)
    R = _pmap(_mg_job, [(i, n, sigma, SEED) for i in range(n_coins)], workers)
    mg = {}
    ok_a = True
    for k in _MG_ROWS:
        cat = {f: np.concatenate([r[k][f] for r in R]) for f in ("ret", "gross", "fees", "fees_re", "funding", "ntr")}
        nn, m, se = _mean_se(cat["ret"])
        d = {"trades": nn, "mean": m, "se": se, "t": m / se if se > 0 else float("nan"),
             "tranches_per_trade": float(cat["ntr"].mean()) if nn else float("nan"),
             "mean_fee_engine": float(cat["fees"].mean()) if nn else float("nan"),
             "mean_fee_recomputed": float(cat["fees_re"].mean()) if nn else float("nan"),
             "max_abs_fee_diff": float(np.max(np.abs(cat["fees_re"] - cat["fees"]))) if nn else 0.0,
             "max_abs_identity_diff": float(np.max(np.abs(cat["gross"] - cat["ret"] - cat["fees"] - cat["funding"])))
             if nn else 0.0,
             "bad_closing_notional": int(sum(r[k]["bad_notional"] for r in R)),
             "fill_audit_violations": int(sum(r[k]["audit"] for r in R)),
             "liquidations": int(sum(r[k]["liq"] for r in R)),
             "coins": n_coins, "years": years, "sigma_hourly": sigma}
        if k.endswith("zero"):
            d["rule"] = "trades >= 20,000 and |mean| <= 2 SE (before costs; no funding on the synthetic frames)"
            d["passed"] = bool((quick or nn >= 20_000) and abs(m) <= 2 * se and d["fill_audit_violations"] == 0)
        else:
            gap = m + d["mean_fee_recomputed"]
            d.update(mean_plus_recomputed_fee=gap,
                     rule="|mean + mean recomputed round-trip fee| <= 2 SE ('about minus the round-trip cost'), "
                          "recomputed fees = engine fees (1e-12), ret_gross - ret - fees - funding = 0 (1e-12)")
            d["passed"] = bool(abs(gap) <= 2 * se and d["max_abs_fee_diff"] <= 1e-12
                               and d["max_abs_identity_diff"] <= 1e-12 and d["bad_closing_notional"] == 0
                               and d["fill_audit_violations"] == 0)
        ok_a &= d["passed"]
        mg[k] = d
    res["martingale"] = mg
    _say(f"  (a) martingale: S1 {mg['S1_zero']['trades']:,} trades, mean {mg['S1_zero']['mean']:+.5f} "
         f"(t {mg['S1_zero']['t']:+.2f}); R0 {mg['R0_zero']['trades']:,}, mean {mg['R0_zero']['mean']:+.5f} "
         f"(t {mg['R0_zero']['t']:+.2f}); after costs S1 {mg['S1_base']['mean']:+.5f} vs fee "
         f"{-mg['S1_base']['mean_fee_recomputed']:+.5f}, R0 {mg['R0_base']['mean']:+.5f} vs fee "
         f"{-mg['R0_base']['mean_fee_recomputed']:+.5f}; {'ok' if ok_a else 'FAIL'}")
    # (b) drift-adjusted mean with and without a constant drift
    nd_coins = 16 if quick else 64
    nd = int(50 * 365 * 24)
    dr = {}
    ok_b = True
    for mu in (0.0, 1e-4):
        X = np.concatenate(_pmap(be._drift_worker, [(i, nd, 0.01, 99, mu) for i in range(nd_coins)], workers))
        n1, m_raw, se_raw = _mean_se(X[:, 0])
        n2, m_adj, se_adj = _mean_se(X[:, 1])
        ok = abs(m_adj) <= 2 * se_adj and (mu == 0 or m_raw > 2 * se_raw)
        ok_b &= ok
        dr[f"drift_{mu:g}"] = {"trades": n1, "mean_unadjusted": m_raw, "se_unadjusted": se_raw,
                               "t_unadjusted": m_raw / se_raw, "mean_adjusted": m_adj, "se_adjusted": se_adj,
                               "t_adjusted": m_adj / se_adj, "passed": bool(ok), "coins": nd_coins, "years": 50}
    res["drift_adjust"] = dict(dr, rule="|drift-adjusted mean| <= 2 SE at drift 0 and +1e-4/h; unadjusted mean > 2 SE "
                                        "at the positive drift")
    _say(f"  (b) drift-adjusted: t {dr['drift_0']['t_adjusted']:+.2f} (no drift), "
         f"{dr['drift_0.0001']['t_adjusted']:+.2f} (drift; unadjusted t {dr['drift_0.0001']['t_unadjusted']:+.1f}); "
         f"{'ok' if ok_b else 'FAIL'}")
    # (c) G-A martingale
    ga_coins = 60 if quick else 240
    G = _pmap(bg._mg_coin, [(i, 730, 100, 0.02, SEED) for i in range(ga_coins)], workers)
    z = np.concatenate([g["zero"] for g in G])
    b = np.concatenate([g["base"] for g in G])
    nz, mz, sz = _mean_se(z)
    nb, mb, sb = _mean_se(b)
    aud = int(sum(g["zero_audit"] + g["base_audit"] + g["audit_r0"] for g in G))
    reasons: dict = {}
    for g in G:
        for k_, v in g["zero_reasons"].items():
            reasons[k_] = reasons.get(k_, 0) + int(v)
    ok_c = bool(abs(mz) <= 2 * sz and mb < 0 and aud == 0)
    res["grid_ga"] = {"deployments": nz, "mean_zero_fees": mz, "se_zero_fees": sz, "t_zero_fees": mz / sz,
                      "mean_base_fees": mb, "se_base_fees": sb, "t_base_fees": mb / sb, "fill_audit_violations": aud,
                      "ends": reasons, "r0_positions": int(sum(g["n_r0"] for g in G)), "coins": ga_coins, "days": 730,
                      "sigma_day": 0.02, "passed": ok_c,
                      "rule": "|mean| <= 2 SE per deployment before fees, mean < 0 after fees, audits empty"}
    _say(f"  (c) G-A martingale: {nz:,} deployments, before fees t {mz / sz:+.2f}, after fees mean {mb:+.6f} "
         f"(t {mb / sb:+.1f}); {'ok' if ok_c else 'FAIL'}")
    # (d) persistent trends
    nt_coins = 12
    nt = int(20 * 365 * 24)
    Tr = _pmap(_trend_job, [(i, nt, 0.01, 7) for i in range(nt_coins)], workers)
    tr = {}
    for k in ("S1_base", "S1_zero"):
        x = np.concatenate([r[k][0] for r in Tr])
        nn, m, se = _mean_se(x)
        tr[k] = {"trades": nn, "mean": m, "se": se, "t": m / se, "fill_audit_violations": int(sum(r[k][1] for r in Tr))}
    ok_d = bool(tr["S1_base"]["mean"] > 2 * tr["S1_base"]["se"] and tr["S1_base"]["fill_audit_violations"] == 0
                and tr["S1_zero"]["fill_audit_violations"] == 0)
    res["trend"] = dict(tr, passed=ok_d, coins=nt_coins, years=20,
                        rule="ROWS['S1'] (base fees) mean trade return > 2 SE on regime-drift paths")
    _say(f"  (d) persistent trends: S1 {tr['S1_base']['trades']:,} trades, t {tr['S1_base']['t']:+.1f}; "
         f"{'ok' if ok_d else 'FAIL'}")
    res["passed"] = bool(ok_a and ok_b and ok_c and ok_d)
    res["summary"] = {
        "S1_trades": mg["S1_zero"]["trades"], "S1_t_before_costs": mg["S1_zero"]["t"],
        "R0_trades": mg["R0_zero"]["trades"], "R0_t_before_costs": mg["R0_zero"]["t"],
        "S1_after_costs_gap_over_se": mg["S1_base"]["mean_plus_recomputed_fee"] / mg["S1_base"]["se"],
        "R0_after_costs_gap_over_se": mg["R0_base"]["mean_plus_recomputed_fee"] / mg["R0_base"]["se"],
        "fee_recompute_max_diff": max(mg[k]["max_abs_fee_diff"] for k in mg),
        "drift_adjusted_t": [dr["drift_0"]["t_adjusted"], dr["drift_0.0001"]["t_adjusted"]],
        "GA_t_before_fees": mz / sz, "GA_mean_after_fees_negative": bool(mb < 0),
        "trend_S1_t": tr["S1_base"]["t"],
        "parts_passed": {"martingale": bool(ok_a), "drift_adjust": bool(ok_b), "grid_ga": ok_c, "trend": ok_d}}
    res["seconds_inner"] = round(time.time() - t0, 1)
    return res


# ============================================================================ 2. inference known answer
IC_VOLS = (0.61, 0.79, 1.21)        # annualized hourly-return volatility of BTC, ETH, SOL 2020-01..2026-10 (benchmark)
IC_RHO = 0.8
IC_DF = 4
IC_HIST = "2019-01-01"
IC_CFG = replace(be.ROWS["S1_L1"], fees="zero")


def ic_hours(seed: int, vols=IC_VOLS, rho: float = IC_RHO, df_t: int = IC_DF, start: str = IC_HIST,
             end: str = "2026-10-16 23:00") -> dict:
    """Three synthetic coins on one hourly grid: simple returns r = sigma z (z standardized Student t(df_t), clipped at
    +-30, cross-correlation rho), so each price is a martingale (zero arithmetic drift); intrahour high / low from a
    Brownian bridge in log space with the hour's sigma (bb_engine._gbm_hours' construction). Frames shaped like
    bb_data.coin_hours (traded = signal series, trades 10, no funding, no mark)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="h", tz="UTC").as_unit("ns")
    n, k = len(idx), len(vols)
    C = np.full((k, k), rho)
    np.fill_diagonal(C, 1.0)
    z = rng.standard_t(df_t, size=(n, k)) / math.sqrt(df_t / (df_t - 2)) @ np.linalg.cholesky(C).T
    z = np.clip(z, -30, 30)
    sig = np.asarray(vols, float) / math.sqrt(365 * 24)
    out = {}
    for c in range(k):
        cl = 100.0 * np.cumprod(1.0 + z[:, c] * sig[c])
        op = np.r_[100.0, cl[:-1]]
        lo_, lc = np.log(op), np.log(cl)
        d2 = (lc - lo_) ** 2
        s2 = sig[c] ** 2
        hi = np.exp(0.5 * (lo_ + lc + np.sqrt(d2 - 2 * s2 * np.log(rng.random(n)))))
        lw = np.exp(0.5 * (lo_ + lc - np.sqrt(d2 - 2 * s2 * np.log(rng.random(n)))))
        df = pd.DataFrame({"open": op, "high": hi, "low": lw, "close": cl, "trades": np.full(n, 10, np.int64)},
                          index=idx)
        df.index.name = "open_time"
        df["tradable"] = True
        df["funding"] = 0.0
        for a in bd.PX:
            df["sig_" + a] = df[a]
        df["live"] = df["sig_live"] = True
        df["seg"] = 0
        out[f"IC{c}"] = df
    return out


def _ic_sim(seed: int) -> pd.DataFrame:
    """One inference-control path: the engine's S1 at L = 1 without fees on each coin of ic_hours(seed), entries
    2020-01-01..2026-10-16, drift-adjusted per trade (bb_stats.drift_adjust, the whole synthetic history as the
    sample). Columns sym, entry1_time, month, ret, ret_adj, audit."""
    rows = []
    for s, df in ic_hours(seed).items():
        r = be.simulate_coin(s, IC_CFG, start=FULL[0], end=FULL[1], hours=df, mmr=0.005, detail=False)
        T = r["trades"]
        if not len(T):
            continue
        adj = bst.drift_adjust(T, r["expo"], {s: bst.returns_from_hours(df)}).to_numpy(float)
        rows.append(pd.DataFrame({"sym": s, "entry1_time": T.entry1_time.to_numpy(), "month": T.month.to_numpy(),
                                  "ret": T.ret.to_numpy(float), "ret_adj": adj, "audit": len(r["fills_audit"])}))
    be.clear_cache()
    if not rows:
        return pd.DataFrame(columns=["sym", "entry1_time", "month", "ret", "ret_adj", "audit"])
    return pd.concat(rows, ignore_index=True)


def size_rule(k: int, n: int, nominal: float = 0.05) -> dict:
    """The size rule (module docstring, control 2; coding choice 1): pass when the point rejection rate k / n is at
    most the nominal 5% (bb_stats.inference_control's ok_reject, the same arithmetic). The exact (Clopper-Pearson)
    95% interval and the one-sided binomial test of "size <= 5%" at 5% (bb_stats' ok_reject_binomial) are reported
    beside it."""
    k, n = int(k), int(n)
    lo, hi = bst._binom_ci(k, n)
    return {"k": k, "n": n, "rate": k / n if n else float("nan"), "ci95": [lo, hi],
            "binomial_5pct_ok": bool(n > 0 and sps.binom.sf(k - 1, n, nominal) > 0.05),
            "passed": bool(n > 0 and k / n <= nominal)}


def inference_known_answer(quick: bool = False, workers: int = 4, n_paths: int | None = None,
                           n_ref: int | None = None, B: int | None = None, seed: int = SEED, **_) -> dict:
    """Controls, "Inference known answer", with Addendum 2's ruling (module docstring, control 2)."""
    t0 = time.time()
    n_paths = n_paths or (40 if quick else 200)
    n_ref = n_ref if n_ref is not None else (40 if quick else 1000)
    B = B or (999 if quick else bst.B_TRADE)
    scored = {int(s) for s in np.random.default_rng(seed).integers(0, 2 ** 62, n_paths)}
    # diagnostic reference: pooled per-trade mean over further paths with disjoint seeds (decides nothing)
    ref_seeds = [int(s) for s in np.random.default_rng([seed, 7]).integers(0, 2 ** 62, n_ref) if int(s) not in scored]
    ref_mean, ref_se, ref_n, ref_audit = 0.0, float("nan"), 0, 0
    if ref_seeds:
        F = _pmap(_ic_sim, ref_seeds, workers)
        x = np.concatenate([f.ret_adj.to_numpy(float) for f in F])
        lab = np.concatenate([np.full(len(f), j) for j, f in enumerate(F)])
        ok = np.isfinite(x)
        ref_mean, ref_se = (float(v) for v in bst.cluster_t(x[ok], lab[ok])[:2])
        ref_n = int(ok.sum())
        ref_audit = int(sum(int(f.audit.max()) if len(f) else 0 for f in F))
    t1 = time.time()
    ic = bst.inference_control(sim_fn=_ic_sim, n_paths=n_paths, seed=seed, true_mean=float(ref_mean), B=B,
                               n_jobs=workers)
    n_ok = ic["n_paths"]
    k_rej = int(round(ic["reject_rate"] * n_ok))
    size = size_rule(k_rej, n_ok)
    if size["passed"] != bool(ic["ok_reject"]):                         # one rule, two implementations
        raise AssertionError(f"size rule {size['passed']} != bb_stats ok_reject {ic['ok_reject']} ({k_rej}/{n_ok})")
    miss0 = float(ic["miss_rate_95_at_0"])
    k_miss = int(round(miss0 * n_ok))
    wid = ic["level_widened_at_0"]
    widened = wid is not None
    level95 = float(wid) if widened else 0.95
    level_noedge = float(ic["level_noedge_widened_at_0"])
    bound_ok = bool(np.isfinite(level95) and np.isfinite(level_noedge))
    res = {"quick": quick, "n_paths": n_ok, "B": B, "seed": seed, "vols": list(IC_VOLS), "rho": IC_RHO,
           "student_t_df": IC_DF, "history_from": IC_HIST, "window": list(FULL), "row": "S1_L1, fees='zero'",
           "true_mean": 0.0, "true_mean_source": "Addendum 2: S1 at L = 1 with no fees on zero-drift paths",
           "mean_trades_per_path": ic["mean_trades_per_path"], "mean_months_per_path": ic["mean_G"],
           "reject_rate": ic["reject_rate"], "reject_k": k_rej, "reject_ci95": size["ci95"],
           "reject_rule": "pass if the point rejection rate <= 0.05 ('at most about 5%', read as Addendum 2 reads "
                          "the same phrase for the bound; bb_stats ok_reject); the Clopper-Pearson 95% interval and "
                          "the one-sided binomial flag are reported only",
           "reject_passed": size["passed"], "reject_point_le_5pct": bool(ic["reject_rate"] <= 0.05),
           "reject_binomial_5pct_ok": bool(ic["ok_reject_binomial"]),
           "miss_rate_95": miss0, "miss_k": k_miss, "miss_ci95": list(bst._binom_ci(k_miss, n_ok)),
           "miss_rate_by_level": ic["miss_rate_by_level_at_0"],
           "miss_rule": "Addendum 2: widen when the 95% miss rate (point, vs the true mean 0) exceeds 5%",
           "widened": widened, "level95": level95, "level_noedge": level_noedge, "bound_passed": bound_ok,
           "diagnostic_true_mean_independent": ref_mean, "diagnostic_true_mean_independent_se": ref_se,
           "diagnostic_independent_paths": len(ref_seeds), "diagnostic_independent_trades": ref_n,
           "diagnostic_reject_rate_centred": ic["reject_rate_centered"],
           "diagnostic_miss_rate_95_vs_independent": ic["miss_rate_95"],
           "diagnostic_level_widened_vs_independent": ic["level_widened"],
           "diagnostic_miss_rate_analytic_t_95": ic["miss_rate_analytic_95"],
           "diagnostic_scored_grand_mean": ic["scored_grand_mean"],
           "fill_audit_violations_reference_paths": ref_audit,
           "bb_stats_output": ic, "seconds_reference": round(t1 - t0, 1), "seconds_scored": round(time.time() - t1, 1)}
    res["passed"] = bool(size["passed"] and bound_ok and ref_audit == 0)
    res["summary"] = {"n_paths": n_ok, "reject_rate": ic["reject_rate"], "reject_ci95": size["ci95"],
                      "miss_rate_95": miss0, "widened": widened, "level95": level95, "level_noedge": level_noedge,
                      "true_mean_independent": ref_mean, "trades_per_path": ic["mean_trades_per_path"]}
    _say(f"  inference: {n_ok} paths, {ic['mean_trades_per_path']:.0f} trades / {ic['mean_G']:.0f} months each; "
         f"rejection {ic['reject_rate']:.3f} (CI {size['ci95'][0]:.3f}-{size['ci95'][1]:.3f}); 95% bound misses "
         f"{miss0:.3f}; level95 {level95:.4f}, level_noedge {level_noedge:.5f}; independent mean {ref_mean:+.5f} "
         f"(SE {ref_se:.5f}); {'ok' if res['passed'] else 'FAIL'}")
    return res


# ============================================================================ 3. look-ahead check
W_NY = (6, 10, 13)                    # entry windows 06:00 and 10:00, exit window 13:00 New York
EXCLUDE_DAYS = ("2025-01-14", "2025-01-29")
LA_CORE = ("BTC", "ETH", "SOL", "LINK", "EOS")
LA_ROWS = ("R0", "S1", "S1_L1", "S8", "S11", "H4_touch")
LA_S12 = ("S12_top3", "S12_top6", "S12_top10", "S12_all_top3")
LA_GA = ("BTC", "ETH", "SOL")
PRICE = ["open", "high", "low", "close"]
VOLS = ["volume", "quote_volume", "taker_buy_quote"]


def _cfg(row: str):
    return be.h4_touch_cfg() if row == "H4_touch" else be.ROWS[row]


def near_window(t: pd.Timestamp) -> bool:
    loc = pd.Timestamp(t).tz_convert(bd.NY)
    m = loc.hour * 60 + loc.minute
    return any(abs(m - 60 * w) <= 120 for w in W_NY)


def draw_cuts(n_scale: float = 1.0, seed: int = LA_SEED) -> pd.DataFrame:
    """The crypto cut times (module docstring, control 3, and coding choice 2)."""
    rng = np.random.default_rng(seed)
    U = lambda s: pd.Timestamp(s, tz="UTC")                                    # noqa: E731

    def ok(t):
        return t.minute != 0 and str(t.date()) not in EXCLUDE_DAYS

    def rand_minute(a, b, cond=lambda t: True):
        lo, hi = U(a).value // MIN_NS, U(b).value // MIN_NS
        while True:
            t = pd.Timestamp(int(rng.integers(lo, hi)) * MIN_NS, tz="UTC")
            if ok(t) and cond(t):
                return t

    def window():
        days = pd.date_range("2020-01-02", "2026-10-14", freq="D")
        while True:
            d = days[int(rng.integers(0, len(days)))]
            w = int(rng.choice(W_NY))
            k = int(rng.integers(-119, 120))
            if k % 60 == 0:
                continue
            t = (d + pd.Timedelta(hours=w, minutes=k)).tz_localize(bd.NY).tz_convert("UTC")
            if ok(t):
                return t

    def month_start():
        months = pd.date_range("2020-02-01", "2026-10-01", freq="MS", tz="UTC")
        while True:
            t = months[int(rng.integers(0, len(months)))] + pd.Timedelta(minutes=int(rng.integers(1, 180)))
            if ok(t):
                return t

    plan = [("w16", 14, lambda: rand_minute("2025-06-01", "2026-10-15 23:59")),
            ("weekend", 12, lambda: rand_minute("2020-01-02", "2026-10-15 23:59", lambda t: t.weekday() >= 5)),
            ("window", 14, window), ("month_start", 5, month_start),
            ("m1", 8, lambda: rand_minute("2024-07-01", "2025-05-31 23:59")),
            ("early", 7, lambda: rand_minute("2020-01-02", "2024-06-30 23:59"))]
    rows = []
    for cat, k, fn in plan:
        for _ in range(max(1, int(round(k * n_scale)))):
            rows.append({"t": fn(), "cat": cat})
    C = pd.DataFrame(rows)
    C["in_2025_06_2026_10"] = (C.t >= U("2025-06-01")) & (C.t <= U("2026-10-16 23:59"))
    C["weekend"] = C.t.map(lambda t: t.weekday() >= 5)
    C["near_window"] = C.t.map(near_window)
    C["m1_era"] = C.t >= U("2024-07-01")
    return C.sort_values("t").reset_index(drop=True)


def _perturb_parquet(src: Path, dst: Path, t: pd.Timestamp, period_ns: int, rebuild=None, keep_frame=False):
    """Copy one kline parquet with every price after t x 1.5 and every volume after t x 0.5 (module docstring,
    control 3; coding choice 3). period_ns: the bar length (hour, day or minute). rebuild: (high, low, close) for the
    bar containing t (a 1-minute coin's perpetual hour). Column types are kept (float32 minutes stay float32)."""
    tb = pq.read_table(src)
    unit = tb.schema.field("open_time").type.unit
    per = {"s": 10 ** 9, "ms": 10 ** 6, "us": 10 ** 3, "ns": 1}[unit]
    ot = tb.column("open_time").cast(pa.int64()).to_numpy() * per             # ns
    tn = int(t.value)
    if period_ns == MIN_NS:
        after = ot >= tn
        strad = np.zeros(len(ot), bool)
    else:
        b0 = tn - tn % period_ns
        after = ot > b0
        strad = ot == b0
    cols = {}
    for c in tb.column_names:
        if c in PRICE or c in VOLS:
            v = tb.column(c).to_numpy().copy()
            dt = v.dtype
            w = v.astype(np.float64)
            if c in PRICE:
                w[after] *= 1.5
                if strad.any():
                    if rebuild is not None and c in ("high", "low", "close"):
                        w[strad] = {"high": rebuild[0], "low": rebuild[1], "close": rebuild[2]}[c]
                    elif c in ("high", "close"):
                        w[strad] *= 1.5
            else:
                w[after | strad] *= 0.5
            cols[c] = pa.array(w.astype(dt), type=tb.schema.field(c).type)
    for c, arr in cols.items():
        tb = tb.set_column(tb.column_names.index(c), c, arr)
    pq.write_table(tb, dst)
    if keep_frame:
        return tb.to_pandas()
    return None


def _rebuild_hour(mframe: pd.DataFrame, sym: str, hs_ns: int, open_px: float):
    """(high, low, close) of the perpetual hour starting hs_ns from the perturbed minutes, as bb_data.minutes()
    rounds them and bb_engine.prepare() compares them (live minutes; high at least the hour's open), or None if the
    minute file does not cover the hour."""
    ot = _ns(mframe["open_time"])
    sel = (ot >= hs_ns) & (ot < hs_ns + H_NS)
    if not sel.any():
        return None
    d = bd._decimals(bd.M1_GRID[sym])
    mm = mframe.loc[sel]
    live = mm["trades"].to_numpy() > 0
    if live.any():
        mm = mm.loc[live]
    hi = np.round(mm["high"].to_numpy(np.float64), d).max()
    lo = np.round(mm["low"].to_numpy(np.float64), d).min()
    cl = np.round(mm["close"].to_numpy(np.float64), d)[-1]
    return float(max(hi, open_px)), float(lo), float(cl)


def _stems(coins) -> dict:
    """{coin: (spot stem or None, [perpetual stems])} under the real DATA directory."""
    out = {}
    for c in coins:
        sp = c if (bd.DATA / "h1_spot" / f"{c}USDT.parquet").exists() else None
        out[c] = (sp, bd.perp_files(c))
    return out


def perturb_data_dir(src: Path, dst: Path, t: pd.Timestamp, stems: dict, m1=tuple(bd.M1_COINS)) -> dict:
    """Build a perturbed copy of data/bbreplica under dst for the cut t (module docstring, control 3): h1_spot, h1_um
    and h1_mark of the coins in `stems`, m1_um of the coins in m1 (each 1-minute coin's straddling perpetual hour
    rebuilt from its perturbed minutes), every d1_um_all file (+ its json files), funding linked unchanged."""
    t0 = time.time()
    for k in ("h1_spot", "h1_um", "h1_mark", "m1_um", "d1_um_all"):
        (dst / k).mkdir(parents=True, exist_ok=True)
    os.symlink(src / "funding", dst / "funding")
    rb = {}
    for sym in m1:
        p = src / "m1_um" / f"{sym}USDT.parquet"
        if p.exists():
            rb[sym] = _perturb_parquet(p, dst / "m1_um" / p.name, t, MIN_NS, keep_frame=True)
    hs = int(t.value) - int(t.value) % H_NS
    n_files = len(rb)
    for coin, (sp, perps) in stems.items():
        if sp is not None:
            _perturb_parquet(src / "h1_spot" / f"{sp}USDT.parquet", dst / "h1_spot" / f"{sp}USDT.parquet", t, H_NS)
            n_files += 1
        for stem in perps:
            p = src / "h1_um" / f"{stem}USDT.parquet"
            rebuild = None
            if coin in rb:
                h = pq.read_table(p, columns=["open_time", "open"]).to_pandas()
                row = h[_ns(h.open_time) == hs]
                if len(row):
                    rebuild = _rebuild_hour(rb[coin], coin, hs, float(row.open.iloc[0]))
            _perturb_parquet(p, dst / "h1_um" / p.name, t, H_NS, rebuild=rebuild)
            pm = src / "h1_mark" / f"{stem}USDT.parquet"
            if pm.exists():
                _perturb_parquet(pm, dst / "h1_mark" / pm.name, t, H_NS)
            n_files += 2
    for p in (src / "d1_um_all").iterdir():
        if p.suffix == ".parquet":
            _perturb_parquet(p, dst / "d1_um_all" / p.name, t, DAY_NS)
            n_files += 1
        elif p.is_file():
            shutil.copy2(p, dst / "d1_um_all" / p.name)
    return {"files": n_files, "seconds": round(time.time() - t0, 1)}


def _clear_caches() -> None:
    for f in (bd._coin_hours_full, bd._bars_cached, bd._minutes_full, bd._pool40_daily, bd._poolall_daily):
        f.cache_clear()
    be.clear_cache()


class _DataDir:
    """Point bb_data at another data/bbreplica directory for the duration of a block (caches cleared both ways)."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def __enter__(self):
        self.old = (bd.DATA, bd.ALL_DIR)
        bd.DATA, bd.ALL_DIR = self.path, self.path / "d1_um_all"
        _clear_caches()
        return self

    def __exit__(self, *exc):
        bd.DATA, bd.ALL_DIR = self.old
        _clear_caches()
        return False


# ---------------------------------------------------------------- decision tables
_FILL_COLS = ["pos", "kind", "time", "px", "frac", "cost", "dir", "cause_time"]
_ORDER_COLS = ["pos", "side", "signal_day", "signal_known", "entry1_time", "entry1_px", "S", "TP", "L_used", "L_max",
               "liq_px0", "atH_only", "deferred", "reentry", "entry_bar", "l_capped", "near_r0", "touch"]
_EXIT_COLS = ["pos", "exit_time", "exit_px", "exit_reason", "liquidated", "n_tranches", "max_frac", "tp_filled",
              "n_adds_cancelled", "ret", "ret_gross", "fees", "funding"]
_SIG_COLS = ["signal_day", "dir", "atH_only", "reentry"]


def _engine_tables(r: dict, cfg, t: pd.Timestamp) -> dict:
    tr, T, S = r["tranches"], r["trades"], r["signals"]
    fills = tr[(tr.kind != "end") & (tr.time < t)][_FILL_COLS]
    orders = T[T.entry1_time < t][_ORDER_COLS]
    exits = T[(T.exit_time < t) & ~T.open_at_end.astype(bool)][_EXIT_COLS]
    per = bd.FREQ[cfg.bars]
    sig = S[(S.signal_day + per) < t][_SIG_COLS] if len(S) else S.reindex(columns=_SIG_COLS)
    return {"fills": fills, "orders": orders, "exits": exits, "signals": sig}


_FULL_CLOSE = ("stop", "tp_all", "liq", "delist")          # final exits that are not a trend exit


def _exit_decisions(r: dict, t: pd.Timestamp) -> dict:
    """{(pos, decision ns): fill ns} of the trend exits DECIDED before t (tranches of kind 'exit' whose cause_time,
    the close of the deciding bar, is before t), wherever their fills fall."""
    tr = r["tranches"]
    d = tr[(tr.kind == "exit") & (tr.cause_time < t)]
    return dict(zip(zip(d.pos.astype(np.int64).tolist(), _ns(d.cause_time).tolist()), _ns(d.time).tolist()))


def _closed_otherwise(r: dict, pos: int, lo_ns: int, hi_ns: int) -> bool:
    """True if run r closed position pos in full by a stop, a take-profit of the whole remainder, a liquidation or a
    delisting close (not a trend exit) stamped in [lo, hi]."""
    T = r["trades"]
    x = T[T.pos == pos]
    if len(x) != 1 or bool(x.open_at_end.iat[0]):
        return False
    xt = int(_ns(x.exit_time)[0])
    return str(x.exit_reason.iat[0]).split("+")[-1] in _FULL_CLOSE and lo_ns <= xt <= hi_ns


def pending_decisions(ra: dict, rb: dict, cfg, t: pd.Timestamp) -> tuple[dict, list]:
    """Decisions stamped before t whose fills fall at or after t (module docstring, control 3; controls review
    finding 2), which _engine_tables, selecting fills by their own stamps, does not see.
    exit_decisions: the set of (position, decision time) of the trend exits decided before t (filled before or after
      it) must be the same in both runs, with the same scheduled fill time, except that a position the other run
      closed in full by a stop, take-profit, liquidation or delisting stamped at or after t and no later than the
      pending exit's fill never reached that fill (the post-t prices legitimately pre-empt it). A rule 6 or rule 15
      decision that differs between the runs shows here as an exit decided at that close in one run only.
    pending_entries: positions whose first tranche was decided before t (cause_time: the signal bar's close, or for
      H4's touch arm the 00:00 close at which the resting buy-stop was placed) and fills at or after t, present in
      both runs under the same (pos, decision time) (a post-t skip or re-check legitimately removes one): the same
      signal bar and stop bar, and the same S where the stop bar closed before t (the touch arm's S "comes from the
      same completed bar" as its resting level).
    Returns ({part: decisions compared}, [mismatch descriptions: part and position, never values])."""
    tn = int(pd.Timestamp(t).value)
    bad: list = []
    ea, eb = _exit_decisions(ra, t), _exit_decisions(rb, t)
    for k in sorted(set(ea) | set(eb)):
        if k in ea and k in eb:
            if ea[k] != eb[k]:
                bad.append(f"exit_decisions: scheduled fill of the exit of pos={k[0]} decided before t differs")
        else:
            fill, other = (ea[k], rb) if k in ea else (eb[k], ra)
            if not _closed_otherwise(other, k[0], tn, fill):
                bad.append(f"exit_decisions: exit of pos={k[0]} decided before t in one run only")
    per = int(bd.FREQ[cfg.bars].value)

    def pend_entries(r):
        tr, T = r["tranches"], r["trades"]
        d = tr[(tr.kind == "entry") & (tr.cause_time < t) & (tr.time >= t)]
        x = T.set_index("pos").loc[d.pos.astype(np.int64).to_numpy(), ["signal_day", "entry_bar", "S"]]
        return {(int(p), int(c)): (int(sd), int(eb_), float(s))
                for p, c, sd, eb_, s in zip(d.pos, _ns(d.cause_time), _ns(x.signal_day), _ns(x.entry_bar), x.S)}

    pa_, pb_ = pend_entries(ra), pend_entries(rb)
    both = sorted(set(pa_) & set(pb_))
    for k in both:
        (sa, ja, Sa), (sb, jb, Sb) = pa_[k], pb_[k]
        if sa != sb or ja != jb:
            bad.append(f"pending_entries: signal or stop bar of pos={k[0]} decided before t differs")
        elif ja + per <= tn and not (Sa == Sb or (np.isnan(Sa) and np.isnan(Sb))):
            bad.append(f"pending_entries: S of pos={k[0]} (stop bar closed before t) differs")
    return {"exit_decisions": len(set(ea) | set(eb)), "pending_entries": len(both)}, bad


def _ga_tables(g: dict, t: pd.Timestamp) -> dict:
    D, F, M = g["deployments"], g["fills"], g["daily_by_dep"]
    return {"ga_deploy": D[D.start < t][["dep", "decided", "start", "lo", "hi", "n_int", "ratio", "q", "margin",
                                         "notional", "p_start"]],
            "ga_end": D[D.end < t][["dep", "end", "reason", "p_end", "grid_profit", "inventory_pnl", "fees", "funding",
                                    "net", "n_fills", "n_round_trips", "liquidated"]],
            "ga_fills": F[F.time < t][["dep", "time", "minute", "kind", "interval", "px", "qty", "fee", "open_through",
                                       "cause_time"]],
            "ga_marks": M[M.time < t]}


def _acct_tables(a: dict, t: pd.Timestamp) -> dict:
    T = a["trades"]
    eq = a["equity"]
    return {"sizing": T[T.entry1_time < t][["sym", "pos", "entry1_time", "M", "sizing_equity"]],
            "equity": eq[eq.index < t].rename("equity").reset_index()}


ACCT_RTOL = 1e-12        # coding choice 7: summation-order noise of a dot product over more positions (< 1 ulp seen)


def _entered_before(res: dict, t: pd.Timestamp) -> dict:
    """simulate_coin results cut to the positions entered before t (trades and their 00:00 marks)."""
    out = {}
    for s, r in res.items():
        T = r["trades"]
        keep = (T.entry1_time < t).to_numpy()
        out[s] = {"trades": T[keep], "daily_mtm": r["daily_mtm"][r["daily_mtm"].pos.isin(T.pos[keep])],
                  "expo": r["expo"]}
    return out


def _all_changed(ra: dict, rb: dict) -> bool:
    """True if any fill differs between the two full runs (the perturbation reached a later decision)."""
    fa = ra["tranches"][ra["tranches"].kind != "end"][["kind", "time", "px"]]
    fb = rb["tranches"][rb["tranches"].kind != "end"][["kind", "time", "px"]]
    return not compare_frames(fa, fb)[0]


def _s12_spec(row: str):
    _, pool, k, tradfi = be.ROW_UNIVERSE[row]
    return pool, k, tradfi


def _ranks():
    return {"40": bd.volume_ranks("40"), "all": bd.volume_ranks("all", tradfi=False),
            "all_tradfi": bd.volume_ranks("all", tradfi=True)}


def _s12_coins(ranks: dict, t: pd.Timestamp) -> dict:
    """{row: coins in that row's top k in the month of t or the month before} (coding choice 5)."""
    m0 = pd.Timestamp(year=t.year, month=t.month, day=1, tz="UTC")
    months = [m0, m0 - pd.DateOffset(months=1)]
    out = {}
    for row in LA_S12:
        pool, k, tradfi = _s12_spec(row)
        R = ranks["all_tradfi" if (pool == "all" and tradfi) else pool]
        names = set()
        for m in months:
            if m in R.index:
                names |= {x for x in R.loc[m].iloc[:k].tolist() if isinstance(x, str)}
        out[row] = sorted(names)
    return out


def _run_engine(sym: str, row: str, allowed=None) -> dict:
    return be.simulate_coin(sym, _cfg(row), start=FULL[0], end=FULL[1], entry_allowed=allowed, detail=False)


def _run_s12(sym: str, row: str) -> dict:
    pool, k, tradfi = _s12_spec(row)
    return be.simulate_coin(sym, be.ROWS[row], start=FULL[0], end=FULL[1],
                            entry_allowed=be.s12_allowed(sym, k, pool, tradfi), detail=False)


def _run_ga(sym: str) -> dict:
    r0g = be.simulate_coin(sym, be.ROWS["R0"], start=bg.GRID_START, end=bg.GRID_END, detail=False)
    return {"r0g": r0g, "ga": bg.grid_ga(sym, r0g["trades"])}


def _la_crypto_chunk(args) -> list:
    """Worker: the crypto look-ahead check for a chunk of cut times (original runs computed once per worker on the
    real files; each cut on its own temporary perturbed DATA directory)."""
    cuts, tmp_root, wid = args
    src = Path(bd.DATA)
    orig: dict = {}
    oranks = _ranks()
    stems40 = _stems(bd.COINS)
    out = []
    for t, cat in cuts:
        t = pd.Timestamp(t)
        t0 = time.time()
        s12 = _s12_coins(oranks, t)
        need_s12 = sorted({c for v in s12.values() for c in v})
        # ---- originals (real files), cached per worker
        for sym in LA_CORE:
            for row in LA_ROWS:
                if (sym, row) not in orig:
                    orig[(sym, row)] = _run_engine(sym, row)
        for row, coins in s12.items():
            for sym in coins:
                if (sym, row) not in orig:
                    orig[(sym, row)] = _run_s12(sym, row)
        for sym in LA_GA:
            if (sym, "GA") not in orig:
                orig[(sym, "GA")] = _run_ga(sym)
        for row in ("R0", "S1_L1"):
            if ("acct", row) not in orig:
                orig[("acct", row)] = be.assemble({s: orig[(s, row)] for s in bd.PRIMARY}, be.ROWS[row], *FULL)
        stems = dict(stems40)
        stems.update(_stems([c for c in set(LA_CORE) | set(need_s12) if c not in stems]))
        tmp = Path(tempfile.mkdtemp(prefix=f"bbla{wid}_", dir=tmp_root))
        rec = {"t": str(t), "cat": cat, "mismatches": [], "compared": {}, "runs": 0, "changed_after": 0,
               "runs_changed": 0, "audit_perturbed": 0, "acct_max_rel_diff": 0.0, "accounts": []}
        try:
            rec["perturb"] = perturb_data_dir(src, tmp, t, stems)
            with _DataDir(tmp):
                def cmp(name, ta, tb_, key=None, rtol=0.0):
                    for part in ta:
                        ok_, why = compare_frames(ta[part], tb_[part], key, rtol)
                        rec["compared"][part] = rec["compared"].get(part, 0) + len(ta[part])
                        if rtol > 0:
                            rec["acct_max_rel_diff"] = max(rec["acct_max_rel_diff"],
                                                           max_rel_diff(ta[part], tb_[part]))
                        if not ok_:
                            rec["mismatches"].append(f"{name} {part}: {why}")

                def cmp_engine(name, ra_, rb_, cfg_):
                    cmp(name, _engine_tables(ra_, cfg_, t), _engine_tables(rb_, cfg_, t), "pos")
                    n_, bad_ = pending_decisions(ra_, rb_, cfg_, t)
                    for part, v in n_.items():
                        rec["compared"][part] = rec["compared"].get(part, 0) + v
                    rec["mismatches"] += [f"{name} {b}" for b in bad_]

                def cmp_account(name, po, pp, cfg_, win, k, tbill):
                    key = (name, tuple(sorted(po)))
                    if key not in orig:
                        orig[key] = be.assemble(po, cfg_, *win, idle_tbill=tbill, k_slots=k)
                    acc = be.assemble(pp, cfg_, *win, idle_tbill=tbill, k_slots=k)
                    cmp(f"account {name}", _acct_tables(orig[key], t), _acct_tables(acc, t), rtol=ACCT_RTOL)
                    ea = be.assemble(_entered_before(po, t), cfg_, *win, idle_tbill=tbill, k_slots=k)
                    eb = be.assemble(_entered_before(pp, t), cfg_, *win, idle_tbill=tbill, k_slots=k)
                    cmp(f"account {name} (positions entered before t)", _acct_tables(ea, t), _acct_tables(eb, t))
                    rec["runs"] += 2
                    rec["accounts"].append(name)

                pranks = _ranks()
                for k, R in oranks.items():
                    ok_, why = compare_frames(R[R.index < t].reset_index(),
                                              pranks[k][pranks[k].index < t].reset_index())
                    rec["compared"]["rank_rows"] = rec["compared"].get("rank_rows", 0) + int((R.index < t).sum())
                    if not ok_:
                        rec["mismatches"].append(f"ranks {k}: {why}")
                pert = {}
                for sym in LA_CORE:
                    for row in LA_ROWS:
                        r = _run_engine(sym, row)
                        pert[(sym, row)] = r
                        a = orig[(sym, row)]
                        cmp_engine(f"{sym} {row}", a, r, _cfg(row))
                        rec["runs"] += 1
                        rec["runs_changed"] += _all_changed(a, r)
                        rec["audit_perturbed"] += len(r["fills_audit"])
                for row, coins in s12.items():
                    for sym in coins:
                        r = _run_s12(sym, row)
                        pert[(sym, row)] = r
                        a = orig[(sym, row)]
                        cmp_engine(f"{sym} {row}", a, r, be.ROWS[row])
                        rec["runs"] += 1
                        rec["runs_changed"] += _all_changed(a, r)
                        rec["audit_perturbed"] += len(r["fills_audit"])
                for sym in LA_GA:
                    g = _run_ga(sym)
                    pert[(sym, "GA")] = g
                    a = orig[(sym, "GA")]
                    cmp_engine(f"{sym} R0(grid window)", a["r0g"], g["r0g"], be.ROWS["R0"])
                    cmp(f"{sym} G-A", _ga_tables(a["ga"], t), _ga_tables(g["ga"], t), "dep")
                    rec["runs"] += 2
                    rec["runs_changed"] += int(not compare_frames(a["ga"]["fills"], g["ga"]["fills"])[0])
                    rec["audit_perturbed"] += len(g["ga"]["fills_audit"]) + len(g["r0g"]["fills_audit"])
                for row in ("R0", "S1_L1"):
                    po = {s: orig[(s, row)] for s in bd.PRIMARY}
                    pp = {s: pert[(s, row)] for s in bd.PRIMARY}
                    acc = be.assemble(pp, be.ROWS[row], *FULL)
                    cmp(f"account {row}", _acct_tables(orig[("acct", row)], t), _acct_tables(acc, t), rtol=ACCT_RTOL)
                    ea = be.assemble(_entered_before(po, t), be.ROWS[row], *FULL)
                    eb = be.assemble(_entered_before(pp, t), be.ROWS[row], *FULL)
                    cmp(f"account {row} (positions entered before t)", _acct_tables(ea, t), _acct_tables(eb, t))
                    rec["runs"] += 2
                    rec["accounts"].append(row)
                # S12 accounts (K = k slots of the point-in-time top k; controls review finding 4): sizing and 00:00
                # equity of the account of the coins in the row's top k in the cut's month or the month before
                for row, coins in s12.items():
                    if coins:
                        cmp_account(row, {s: orig[(s, row)] for s in coins}, {s: pert[(s, row)] for s in coins},
                                    be.ROWS[row], FULL, _s12_spec(row)[1], False)
                # H10's overlay account: R0 + G-A merged by bb_grid.merge_ga (each deployment a pseudo-position sized
                # at the slot's sleeve) and assembled over the grid window with idle T-bills, as bb_tests.test_h10
                cmp_account("R0 + G-A (H10 overlay)",
                            {s: bg.merge_ga(orig[(s, "GA")]["r0g"], orig[(s, "GA")]["ga"]) for s in LA_GA},
                            {s: bg.merge_ga(pert[(s, "GA")]["r0g"], pert[(s, "GA")]["ga"]) for s in LA_GA},
                            be.ROWS["R0"], (bg.GRID_START, bg.GRID_END), len(LA_GA), True)
        except Exception:
            rec["mismatches"].append("ERROR " + traceback.format_exc(limit=6))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        rec["changed_after"] = int(rec["runs_changed"] > 0)
        rec["s12_coins"] = s12
        rec["seconds"] = round(time.time() - t0, 1)
        out.append(rec)
        _say(f"    [w{wid}] cut {t} ({cat}): {rec['runs']} runs, {sum(rec['compared'].values()):,} decisions before "
             f"the cut compared, {len(rec['mismatches'])} mismatches, {rec['runs_changed']} runs changed after it, "
             f"{rec['seconds']}s")
    return out


# ---------------------------------------------------------------- stocks
STOCK_USER_EXTRA = ["TSLA", "COIN", "HOOD", "CRCL"]       # the user's tickers outside the 14 ETFs


def _stock_setup(n_cuts: int, quick: bool):
    """Deterministic member sample, groups and cut list for the stock look-ahead (module docstring, control 3)."""
    from analysis_2026 import bb_stocks as bk
    rng = np.random.default_rng(LA_SEED)
    mem = bk.universe_data("members")
    start, end = pd.Timestamp(bk.START), pd.Timestamp(bk.END)
    live = sorted(s for s, f in mem.items() if len(f) and f.index[-1] >= start + pd.Timedelta(days=400)
                  and f.index[0] <= end)
    dead = sorted(s for s in live if mem[s].attrs.get("dead"))
    co = {s: int(mem[s].close_only.to_numpy(bool)[mem[s].index >= start].sum()) for s in live}
    # close-only stretches that matter: close-only sessions inside a pending entry or an open position of the full
    # member run (a name whose whole history is close-only never has one)
    full = bk.stock_trades("members", bk.StockCfg(), bk.START, bk.END)
    span = {}
    for r in full["cand"].itertuples():
        c_ = full["data"][r.sym]["close_only"].to_numpy(bool)
        span[r.sym] = span.get(r.sym, 0) + int(c_[r.t + 1:r.e].sum() + c_[r.e + 1:r.x + 1].sum())
    del full
    k_dead, k_co, k_rand = (4, 4, 4) if quick else (12, 12, 16)
    pick_dead = list(rng.choice(dead, k_dead, replace=False))
    heavy = sorted((s for s in live if span.get(s, 0) > 0 and s not in pick_dead),
                   key=lambda s: (-span[s], s))[:40]
    pick_co = list(rng.choice(heavy, k_co, replace=False))
    rest = [s for s in live if s not in pick_dead and s not in pick_co]
    pick_rand = list(rng.choice(rest, k_rand, replace=False))
    sample = sorted(pick_dead + pick_co + pick_rand)
    groups = {"members": {s: mem[s] for s in sample},
              "etfs": bk.universe_data("etfs"),
              "user": {s: bk.ticker_data(s) for s in STOCK_USER_EXTRA}}
    meta = {"members_dead": sorted(pick_dead), "members_close_only": sorted(pick_co),
            "members_other": sorted(pick_rand), "close_only_rows_since_2001": {s: co[s] for s in sample},
            "close_only_sessions_in_pending_or_open_spans": {s: span.get(s, 0) for s in sample}}
    return groups, meta, rng


def _stock_cuts(groups, base_members, rng, n_cuts: int, quick: bool):
    from analysis_2026 import bb_stocks as bk
    cal = bk.calendar(groups["members"])
    cal = cal[(cal >= pd.Timestamp("2001-03-01")) & (cal <= pd.Timestamp(bk.END) - pd.Timedelta(days=5))]
    n_b = n_c = max(2, int(round(12 * n_cuts / 50)))
    n_a = n_cuts - n_b - n_c
    pool = np.arange(len(cal))
    g_a = rng.choice(pool, n_a, replace=False)
    recent = pool[(cal[pool] >= pd.Timestamp("2025-06-01")) & ~np.isin(pool, g_a)]
    g_b = rng.choice(recent, n_b, replace=False)
    r0 = base_members
    pend = set()
    for r in r0["cand"].itertuples():
        a = r0["arrs"][r.sym]
        fl = r0["data"][r.sym]["flat"].to_numpy(bool)
        dates = r0["data"][r.sym].index
        for d in list(range(r.t + 1, r.e)) + list(range(r.e + 1, r.x + 1)):
            if 0 <= d < len(fl) and fl[d]:
                pend.add(pd.Timestamp(dates[d]))
    taken = set(cal[g_a]) | set(cal[g_b])
    cand = sorted(d for d in pend if d in set(cal) and d not in taken)
    g_c = [cand[i] for i in rng.choice(len(cand), min(n_c, len(cand)), replace=False)] if cand else []
    sessions = list(cal[g_a]) + list(cal[g_b]) + list(g_c)
    cats = ["random"] * len(g_a) + ["2025-06..2026-10"] * len(g_b) + ["flat_bar_pending"] * len(g_c)
    mins = bk._cut_minutes(rng, len(sessions), max(1, int(round(14 * n_cuts / 50))))
    rng.shuffle(mins)
    out = []
    for s, c, m in zip(sessions, cats, mins):
        t_cut = (pd.Timestamp(s) + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(minutes=int(m))
                 ).tz_localize(bd.NY).tz_convert("UTC")
        out.append({"session": pd.Timestamp(s), "minute": int(m), "t": t_cut, "cat": c, "near_open": int(m) < 120,
                    "in_2025_06_2026_10": pd.Timestamp(s) >= pd.Timestamp("2025-06-01")})
    return out


def _la_stock_chunk(args) -> dict:
    """Worker: the stock look-ahead check for every n_chunks-th cut starting at chunk_idx."""
    chunk_idx, n_chunks, n_cuts, quick = args
    from analysis_2026 import bb_stocks as bk
    t0 = time.time()
    groups, meta, rng = _stock_setup(n_cuts, quick)
    cfgs = {"1d": bk.StockCfg(), "1w": bk.StockCfg(bars="1w")}
    slots = {"members": bk.N_SLOTS, "etfs": len(bk.ETFS)}
    base = {(g, b): bk.stock_trades(g, c, bk.START, bk.END, ohlc=d) for g, d in groups.items() for b, c in cfgs.items()}
    books = {g: bk.portfolio(base[(g, "1d")], n_slots=n) for g, n in slots.items()}
    cuts = _stock_cuts(groups, base[("members", "1d")], rng, n_cuts, quick)
    mine = cuts[chunk_idx::n_chunks]
    recs = []
    for c in mine:
        cut, t_cut = c["session"], c["t"]
        rec = {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in c.items()}
        rec.update(mismatches=[], compared={}, runs=0, runs_changed=0, audit_perturbed=0, acct_max_rel_diff=0.0)
        try:
            for g, d in groups.items():
                pert = bk._perturb_after(d, cut)
                for b, cfg in cfgs.items():
                    ra, rb = base[(g, b)], bk.stock_trades(g, cfg, bk.START, bk.END, ohlc=pert)
                    rec["runs"] += 1
                    rec["audit_perturbed"] += len(rb["fills_audit"])
                    ta, tb_ = ra["tranches"], rb["tranches"]
                    cols = ["sym", "signal_day", "time", "px", "notional", "kind"]
                    keys = ["sym", "signal_day", "time", "kind"]
                    ka = ta[(ta.time < t_cut) & (ta.kind != "mark")].merge(ra["trades"][["pos", "signal_day"]],
                                                                           on="pos")[cols].sort_values(keys)
                    kb = tb_[(tb_.time < t_cut) & (tb_.kind != "mark")].merge(rb["trades"][["pos", "signal_day"]],
                                                                              on="pos")[cols].sort_values(keys)
                    ea = ra["trades"][ra["trades"].entry1_time < t_cut][["sym", "signal_day", "entry1_time", "S", "TP",
                                                                         "entry1_px"]].sort_values(["sym",
                                                                                                    "signal_day"])
                    eb = rb["trades"][rb["trades"].entry1_time < t_cut][["sym", "signal_day", "entry1_time", "S", "TP",
                                                                         "entry1_px"]].sort_values(["sym",
                                                                                                    "signal_day"])
                    sa = ra["signals"][ra["signals"].signal_day < cut][["sym", "signal_day"]]
                    sb = rb["signals"][rb["signals"].signal_day < cut][["sym", "signal_day"]]
                    parts = {"fills": (ka, kb), "orders": (ea, eb), "signals": (sa, sb)}
                    if b == "1d" and g in slots:
                        p1 = bk.portfolio(rb, n_slots=slots[g])
                        gc = int(ra["calendar"].get_indexer([cut])[0])
                        pa_, pb_ = books[g]["positions"], p1["positions"]
                        parts["book_entries"] = (pa_[pa_.g_e <= gc][["sym", "signal_day", "M"]],
                                                 pb_[pb_.g_e <= gc][["sym", "signal_day", "M"]])
                        da, db = books[g]["daily"].equity, p1["daily"].equity
                        parts["book_equity"] = (da[da.index < cut].reset_index(), db[db.index < cut].reset_index())
                    for part, (x, y) in parts.items():
                        tol = ACCT_RTOL if part.startswith("book") else 0.0
                        ok_, why = compare_frames(x, y, rtol=tol)
                        if tol:
                            rec["acct_max_rel_diff"] = max(rec["acct_max_rel_diff"], max_rel_diff(x, y))
                        rec["compared"][part] = rec["compared"].get(part, 0) + len(x)
                        if not ok_:
                            rec["mismatches"].append(f"{g} {b} {part}: {why}")
                    fa = ta[ta.kind != "mark"][["sym", "time", "px", "kind"]].sort_values(["sym", "time", "kind"])
                    fb = tb_[tb_.kind != "mark"][["sym", "time", "px", "kind"]].sort_values(["sym", "time", "kind"])
                    rec["runs_changed"] += int(not compare_frames(fa, fb)[0])
        except Exception:
            rec["mismatches"].append("ERROR " + traceback.format_exc(limit=6))
        recs.append(rec)
    if chunk_idx == 0:
        _say(f"    [stocks] {len(cuts)} cuts in all; this worker {len(mine)} cuts, "
             f"{sum(len(r['mismatches']) for r in recs)} mismatches, {time.time() - t0:.0f}s")
    else:
        _say(f"    [stocks {chunk_idx}] {len(mine)} cuts, {sum(len(r['mismatches']) for r in recs)} mismatches, "
             f"{time.time() - t0:.0f}s")
    return {"cuts": recs, "meta": meta, "n_cuts_total": len(cuts),
            "base_audit": int(sum(len(r["fills_audit"]) for r in base.values()))}


def lookahead_check(quick: bool = False, workers: int = 4, tmp=None, **_) -> dict:
    """Controls, "Look-ahead check" (module docstring, control 3)."""
    t0 = time.time()
    C = draw_cuts(0.1 if quick else 1.0)
    n_stock = 12 if quick else 50
    tmp_root = Path(tmp) if tmp else Path(tempfile.gettempdir())
    tmp_root.mkdir(parents=True, exist_ok=True)
    n_crypto_w = max(1, min(len(C), workers if quick else 6))        # 6 chunks + 2 stock tasks balance 4 workers
    chunks = [list(zip(C.t.iloc[i::n_crypto_w], C.cat.iloc[i::n_crypto_w])) for i in range(n_crypto_w)]
    n_stock_w = 1 if quick else 2
    jobs = [("stock", (i, n_stock_w, n_stock, quick)) for i in range(n_stock_w)] + \
           [("crypto", (ch, str(tmp_root), i)) for i, ch in enumerate(chunks)]
    R = _pmap(_la_dispatch, jobs, workers)
    crypto = [r for kind, rr in R if kind == "crypto" for r in rr]
    stock_parts = [rr for kind, rr in R if kind == "stock"]
    stock = [r for p in stock_parts for r in p["cuts"]]
    crypto.sort(key=lambda r: r["t"])
    n_mis = sum(len(r["mismatches"]) for r in crypto)
    n_mis_s = sum(len(r["mismatches"]) for r in stock)
    cnt = {"cuts": len(C), "in_2025_06_2026_10": int(C.in_2025_06_2026_10.sum()), "weekend": int(C.weekend.sum()),
           "near_window": int(C.near_window.sum()), "m1_era": int(C.m1_era.sum()),
           "on_hour_boundary": int((C.t.map(lambda t: t.minute) == 0).sum())}
    scnt = {"cuts": len(stock), "near_open": int(sum(r["near_open"] for r in stock)),
            "in_2025_06_2026_10": int(sum(r["in_2025_06_2026_10"] for r in stock)),
            "flat_bar_pending": int(sum(r["cat"] == "flat_bar_pending" for r in stock))}
    need = 1 if quick else 10
    counts_ok = (cnt["cuts"] >= (1 if quick else 50) and cnt["in_2025_06_2026_10"] >= need and cnt["weekend"] >= need
                 and cnt["near_window"] >= need and cnt["on_hour_boundary"] == 0
                 and scnt["cuts"] >= (1 if quick else 50) and scnt["near_open"] >= need
                 and scnt["in_2025_06_2026_10"] >= need and scnt["flat_bar_pending"] >= need)
    bites = sum(r["changed_after"] for r in crypto)
    bites_s = sum(r["runs_changed"] > 0 for r in stock)
    audit_p = sum(r["audit_perturbed"] for r in crypto) + sum(r["audit_perturbed"] for r in stock)
    comp = {}
    for r in crypto:
        for k, v in r["compared"].items():
            comp[k] = comp.get(k, 0) + v
    comp_s = {}
    for r in stock:
        for k, v in r["compared"].items():
            comp_s[k] = comp_s.get(k, 0) + v
    acct_rel = max([r["acct_max_rel_diff"] for r in crypto + stock] or [0.0])
    passed = bool(n_mis == 0 and n_mis_s == 0 and counts_ok and bites > 0 and bites_s > 0 and audit_p == 0)
    res = {"quick": quick, "passed": passed, "crypto_cut_counts": cnt, "stock_cut_counts": scnt,
           "crypto_mismatches": n_mis, "stock_mismatches": n_mis_s, "crypto_decisions_compared": comp,
           "stock_decisions_compared": comp_s, "crypto_cuts_where_a_later_decision_changed": bites,
           "stock_cuts_where_a_later_decision_changed": int(bites_s), "fill_audit_violations_perturbed": audit_p,
           "stock_base_fill_audit_violations": int(sum(p["base_audit"] for p in stock_parts)),
           "crypto_runs": int(sum(r["runs"] for r in crypto)), "stock_runs": int(sum(r["runs"] for r in stock)),
           "account_rtol": ACCT_RTOL, "account_max_rel_diff_full_runs": acct_rel,
           "accounts_compared": {a: sum(a in r.get("accounts", []) for r in crypto)
                                 for a in sorted({a for r in crypto for a in r.get("accounts", [])})},
           "core_coins": list(LA_CORE), "rows": list(LA_ROWS) + list(LA_S12) + ["G-A", "account R0", "account S1_L1",
                                                                                 "accounts S12 (K = k) on the cut's "
                                                                                 "top-k coins", "account R0 + G-A "
                                                                                 "(H10 overlay, merge_ga)",
                                                                                 "volume_ranks 40/all/all_tradfi"],
           "stock_sample": stock_parts[0]["meta"] if stock_parts else {},
           "crypto_cuts": crypto, "stock_cuts": stock,
           "rule": "every decision stamped before each cut unchanged; cut-count minimums met; the perturbation "
                   "changes a later decision in some run; perturbed runs' fill audits empty"}
    res["summary"] = {"crypto_cuts": cnt["cuts"], "stock_cuts": scnt["cuts"], "crypto_runs": res["crypto_runs"],
                      "stock_runs": res["stock_runs"],
                      "decisions_compared": int(sum(comp.values()) + sum(comp_s.values())),
                      "mismatches": n_mis + n_mis_s, "counts_ok": bool(counts_ok), "cut_counts": cnt,
                      "stock_cut_counts": scnt, "bites": [bites, int(bites_s)], "audit_perturbed": audit_p,
                      "account_max_rel_diff_full_runs": acct_rel}
    res["seconds_inner"] = round(time.time() - t0, 1)
    _say(f"  look-ahead: {cnt['cuts']} crypto cuts ({cnt['in_2025_06_2026_10']} in 2025-06..2026-10, "
         f"{cnt['weekend']} weekend, {cnt['near_window']} near a window), {scnt['cuts']} stock cuts; "
         f"{res['crypto_runs'] + res['stock_runs']} runs, {res['summary']['decisions_compared']:,} decisions compared, "
         f"{n_mis + n_mis_s} mismatches; {'ok' if passed else 'FAIL'}")
    return res


def _la_dispatch(job):
    kind, args = job
    if kind == "crypto":
        return kind, _la_crypto_chunk(args)
    return kind, _la_stock_chunk(args)


# ============================================================================ 4. liquidation check
LIQ_DAY = "2025-10-08"               # Wednesday (EDT): the signal close; entry at the 2025-10-09 10:00 UTC open
LIQ_CRASH = "2025-10-10 20:00"       # inside the stress window (every stop fails 20:00-23:00 UTC)
LIQ_MMR = 0.005
LIQ_FUND = 0.0001                    # funding print at 00/08/16 UTC (longs pay, shorts receive)


def _liq_frame(side: int, adds: bool, funding: bool, mark_only: bool = False) -> pd.DataFrame:
    """Hand-built hours (bb_engine's self-test builders): flat 100 with a 1-point daily range, a signal close on
    LIQ_DAY (long: close 104 above the band near the 60-day high; short: close 96 below the band near the 60-day low),
    entry at the next 06:00 New York window, optional adds (hourly closes through 1.02 / 1.05 x entry1, or 0.98 /
    0.95 for a short), then a crash (spike) bar at LIQ_CRASH through the liquidation price. Mark = last price."""
    df = be._flat_hours("2025-07-01", 120)
    if side > 0:
        be._signal_day(df, LIQ_DAY, close=104.0, high=104.5)
        e1, a1, a2 = 104.0, 106.5, 109.5
    else:
        be._bar(df, f"{LIQ_DAY} 23:00", 100.0, 100.0, 95.5, 96.0)
        e1, a1, a2 = 96.0, 94.0, 91.0
    be._flat(df, "2025-10-09 00:00", "2025-10-10 19:00", e1)
    last = e1
    if adds:
        be._bar(df, "2025-10-09 12:00", e1, max(e1, a1), min(e1, a1), a1)
        be._flat(df, "2025-10-09 13:00", "2025-10-09 13:00", a1)
        be._bar(df, "2025-10-09 14:00", a1, max(a1, a2), min(a1, a2), a2)
        be._flat(df, "2025-10-09 15:00", "2025-10-10 19:00", a2)
        last = a2
    if mark_only:
        be._bar(df, LIQ_CRASH, last, last, last - 5.0 if side > 0 else last, last - 4.0 if side > 0 else last + 4.0)
        after = last - 4.0 if side > 0 else last + 4.0
    elif side > 0:
        be._bar(df, LIQ_CRASH, last, last, 50.0, 55.0)
        after = 55.0
    else:                                         # a spike that retraces: no fresh long breakout afterwards (S11)
        be._bar(df, LIQ_CRASH, last, 200.0, last, 100.0)
        after = 100.0
    be._flat(df, "2025-10-10 21:00", "2025-10-28 23:00", after)
    df = be._fin(df)
    for c in bd.PX:
        df["mark_" + c] = df[c]
    if mark_only:
        df.loc[pd.Timestamp(LIQ_CRASH, tz="UTC"), "mark_low" if side > 0 else "mark_high"] = 65.0 if side > 0 else 140.0
    if funding:
        df["funding"] = np.where(np.isin(df.index.hour, (0, 8, 16)), LIQ_FUND, 0.0)
    return df


def _liq_hand(df: pd.DataFrame, fills: pd.DataFrame, L: float, side: int, sym: str = "SYN") -> dict:
    """The R0 Liquidation row by hand: each tranche posts notional / L; isolated margin = posted - fees paid - funding
    paid (taker + slippage per entry / add; funding = rate x quantity held x mark open at each print the position
    was open before and still open at); liquidation price = avg x (1 - margin / notional + mmr) (long) or
    avg x (1 + margin / notional - mmr) (short), notional = quantity x average entry."""
    rt = be.TAKER["base"] + (be.SLIP_MAJOR if sym in be.MAJORS else be.SLIP_OTHER)
    tr = fills[fills.kind.isin(["entry", "add"])]
    times = _ns(tr.time)
    q = (tr.frac / tr.px).to_numpy(float)
    Q = q.sum()
    posted = float(tr.frac.sum() / L)
    fees = float(rt * tr.frac.sum())
    liq_t = _ns(fills[fills.kind == "liq"].time)[0]                   # stamped at the crash hour's close
    fund = 0.0
    ix = _ns(df.index)
    for h, rate, mo in zip(ix, df.funding.to_numpy(float), df.mark_open.to_numpy(float)):
        if rate != 0.0 and times[0] < h < liq_t:
            fund += side * rate * q[times < h].sum() * mo
    margin = posted - fees - fund
    avg = float(tr.frac.sum() / Q)
    liq = avg - margin / Q + LIQ_MMR * avg if side > 0 else avg + margin / Q - LIQ_MMR * avg
    return {"liq_px": liq, "posted": posted, "fees": fees, "funding_paid": fund, "avg": avg, "qty": Q,
            "isolated_margin": margin}


def liquidation_check(**_) -> dict:
    """Controls, "Liquidation check" (module docstring, control 4)."""
    cases = []
    stress = {1: be.ROWS["R0_stress"], -1: replace(be.ROWS["S11"], stress_20251010=True)}
    plain = {1: be.ROWS["R0"], -1: be.ROWS["S11"]}
    crash_close = pd.Timestamp(LIQ_CRASH, tz="UTC") + pd.Timedelta("1h")
    specs = [(side, L, adds, mo) for side in (1, -1) for L in (3.0, 5.0) for adds in (False, True)
             for mo in (False,)] + [(1, 3.0, False, True), (-1, 3.0, False, True)]
    for side, L, adds, mark_only in specs:
        df = _liq_frame(side, adds, funding=adds, mark_only=mark_only)
        cfg = replace(plain[side] if mark_only else stress[side], L=L)
        r = be.simulate_coin("SYN", cfg, hours=df, mmr=LIQ_MMR)
        T, F = r["trades"], r["tranches"]
        name = f"{'long' if side > 0 else 'short'} L={L:g} {'3 tranches + funding' if adds else '1 tranche'}" + \
               (" mark-price only" if mark_only else " (stops fail)")
        c = {"case": name, "side": side, "L": L, "positions": len(T), "audit": len(r["fills_audit"])}
        ok = len(T) == 1 and not r["fills_audit"]
        if ok:
            x = T.iloc[0]
            liqf = F[F.kind == "liq"]
            fills = F[F.kind != "end"]
            ok = bool(x.liquidated) and len(liqf) == 1 and r["log"]["liquidations"] == 1 and \
                (_ns(fills.time) <= _ns(liqf.time)[0]).all() and x.exit_reason.endswith("liq")
            if ok:
                hand = _liq_hand(df, fills, x.L_used, side)
                c.update(hand=hand, engine_liq_px=float(x.exit_px), engine_ret=float(x.ret),
                         engine_margin_posted=float(x.margin_posted), L_used=float(x.L_used),
                         n_tranches=int(x.n_tranches), exit_time=str(x.exit_time))
                acct = be.assemble({"SYN": r, "B": _empty_res(r), "C": _empty_res(r)}, cfg, "2025-10-01", "2025-10-20")
                M = float(acct["trades"].M.iat[0])
                c.update(account_M=M, account_final_equity=float(acct["equity"].iloc[-1]),
                         account_expected=1.0 - M * hand["posted"])
                ok = (abs(x.exit_px - hand["liq_px"]) <= 1e-9 * hand["liq_px"]
                      and abs(x.ret + hand["posted"]) <= 1e-12 and abs(x.margin_posted - hand["posted"]) <= 1e-12
                      and x.exit_time == crash_close and x.L_used == L
                      and int(x.n_tranches) == (3 if adds else 1)
                      and abs(c["account_final_equity"] - c["account_expected"]) <= 1e-12)
        c["passed"] = bool(ok)
        cases.append(c)
    # the same crashes with working stops: a stop, not a liquidation
    ctrl = []
    for side, adds in ((1, False), (1, True)):
        df = _liq_frame(side, adds, funding=adds)
        r = be.simulate_coin("SYN", plain[side], hours=df, mmr=LIQ_MMR)
        T = r["trades"]
        ok = len(T) == 1 and not T.liquidated.iat[0] and T.exit_reason.iat[0] == "stop" and \
            abs(T.exit_px.iat[0] - be.GAP_FILL * T.S.iat[0]) <= 1e-9 and r["log"]["liquidations"] == 0
        ctrl.append({"case": f"long {'3 tranches' if adds else '1 tranche'} L=3, stops working",
                     "exit_reason": str(T.exit_reason.iat[0]) if len(T) else None, "passed": bool(ok)})
    passed = all(c["passed"] for c in cases) and all(c["passed"] for c in ctrl)
    res = {"passed": bool(passed), "cases": cases, "stop_controls": ctrl, "mmr": LIQ_MMR,
           "rule": "exactly one liquidation, at the hand-computed price, net = - posted isolated margin, account loses "
                   "M x posted margin; working stops give a stop instead"}
    res["summary"] = {"cases": len(cases) + len(ctrl), "passed_cases": sum(c["passed"] for c in cases + ctrl),
                      "max_liq_px_rel_err": max((abs(c["engine_liq_px"] - c["hand"]["liq_px"]) / c["hand"]["liq_px"]
                                                 for c in cases if "hand" in c), default=float("nan"))}
    _say(f"  liquidation: {res['summary']['passed_cases']}/{res['summary']['cases']} cases ok "
         f"(L 3 and 5, long and short, 1 and 3 tranches, mark-only); {'ok' if passed else 'FAIL'}")
    return res


def _empty_res(r: dict) -> dict:
    return {"trades": r["trades"].iloc[:0], "daily_mtm": r["daily_mtm"].iloc[:0], "expo": r["expo"].iloc[:0]}


# ============================================================================ 5. fill audit
FA_ROWS = ("R0", "S1", "S1_L1", "S8", "S11", "S16", "H4_touch")
PRE_PERP = ("2017-08-17", "2019-12-31")          # the pre-perpetual block (Windows), bb_tests.PRE_PERP


def bench_fill_audit(res: dict, H: pd.DataFrame) -> list:
    """Fill audit of H2's indicator benchmark (bb_bench.ml_coin), whose own fills_audit is the empty list by
    construction (controls review finding 3). H: the frame the benchmark traded on (bb_bench._norm_hours(hours) for
    the perpetual vehicle, bb_bench.spot_hours(hours) for the spot vehicle). Every position's fills are checked from
    its trades row and the bars, independently of the benchmark's loop:
      entry, and an exit on the signal: stamped at an hour's open (the fill hour), price = that open, inside the hour's
        [low, high], trades > 0, tradable, and caused by a known close: the latest daily bar known at least 1 h
        before the fill (bb_bench choice 2: "the target at hour h is the state of the latest completed daily bar whose
        known_at is at least 1 h before h") is green (entry) / not green or of another segment (exit);
      liquidation: stamped at the close of a trades > 0, tradable hour whose mark low (last-price low where the mark
        is missing) reached the liquidation price (the price itself is a formula, not a bar price: bb_engine._audit's
        convention);
      delisting close: stamped at the close of a perp_end bar, price = that close, inside [low, high], tradable (a
        settlement: exempt from trades > 0, as bb_engine._audit);
      window-end marks are not fills. Returns violation strings (empty when clean)."""
    T = res["trades"]
    out: list = []
    if not len(T):
        return out
    D = res["green"]
    ix = _ns(H.index)
    o, hi, lo, c = (H[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    trd = H["trades"].to_numpy(float)
    tdb = H["tradable"].to_numpy(bool)
    pend = H["perp_end"].to_numpy(bool)
    mlo = H["mark_low"].to_numpy(float)
    hseg = H["seg"].to_numpy(np.int64)
    kn = _ns(D["known_at"])
    grn = D["green"].to_numpy(bool)
    dseg = D["seg"].to_numpy(np.int64)

    def hour(ns):
        i = int(np.searchsorted(ix, ns))
        return i if i < len(ix) and ix[i] == ns else -1

    def green_known(i):
        p = int(np.searchsorted(kn, ix[i] - H_NS, side="right")) - 1
        return p >= 0 and bool(grn[p]) and dseg[p] == hseg[i]

    def tol(px):
        return 1e-9 * abs(px) + 1e-12

    sym = res.get("sym", "?")
    for r in T.itertuples():
        legs = [("entry", int(pd.Timestamp(r.entry1_time).value), float(r.entry1_px), "signal_in")]
        if r.exit_reason != "window_end":
            legs.append(("exit", int(pd.Timestamp(r.exit_time).value), float(r.exit_px), str(r.exit_reason)))
        for leg, ns, px, why in legs:
            at_open = why in ("signal_in", "signal")
            i = hour(ns if at_open else ns - H_NS)
            tag = f"{sym} pos {r.pos} {leg} ({why}) at {pd.Timestamp(ns, tz='UTC')}"
            if i < 0:
                out.append(f"{tag}: not stamped at an hour of the frame")
                continue
            if why != "liq" and not (lo[i] - tol(px) <= px <= hi[i] + tol(px)):
                out.append(f"{tag}: price outside the bar's [low, high]")
            if why != "delist" and trd[i] <= 0:
                out.append(f"{tag}: fill in a trades == 0 bar")
            if not tdb[i]:
                out.append(f"{tag}: fill in a non-tradable hour")
            if at_open:
                if abs(px - o[i]) > tol(px):
                    out.append(f"{tag}: not at the hour's open")
                if green_known(i) != (why == "signal_in"):
                    out.append(f"{tag}: not caused by the state of the latest daily bar known 1 h before")
            elif why == "liq":
                low = mlo[i] if np.isfinite(mlo[i]) else lo[i]
                if low > px + tol(px):
                    out.append(f"{tag}: liquidation price not reached")
            elif why == "delist":
                if not pend[i] or abs(px - c[i]) > tol(px):
                    out.append(f"{tag}: delisting close not at a perp_end bar's close")
            else:
                out.append(f"{tag}: unknown exit reason")
        if r.exit_reason != "window_end" and pd.Timestamp(r.exit_time) < pd.Timestamp(r.entry1_time):
            out.append(f"{sym} pos {r.pos}: exit stamped before the entry")
    return out


def _bench_audit_runs(s: str) -> list:
    """bench_fill_audit on one coin: the perpetual vehicle over the Full window (H2 (b), the headline's indicator
    rows) and the spot vehicle over the Full window and the pre-perpetual block (bb_tests' pre-perpetual H2 rows)."""
    from analysis_2026 import bb_bench as bb
    H = bd.coin_hours(s)
    out = []
    for vehicle, (a, b) in (("perp", FULL), ("spot", FULL), ("spot", PRE_PERP)):
        if H.index[0] > pd.Timestamp(b, tz="UTC") or H.index[-1] < pd.Timestamp(a, tz="UTC"):
            continue
        Hv = bb.spot_hours(H) if vehicle == "spot" else bb._norm_hours(H)
        r = bb.ml_coin(s, a, b, vehicle=vehicle, hours=H)
        v = bench_fill_audit(r, Hv) + [str(x) for x in r["fills_audit"]]
        T = r["trades"]
        n_fills = int(len(T) + (T.exit_reason != "window_end").sum()) if len(T) else 0
        out.append({"kind": "bench", "what": f"{s} moneyline_ref benchmark {vehicle} {a}..{b}", "positions": len(T),
                    "fills": n_fills, "violations": len(v), "first": v[:3]})
    return out


def _fa_dispatch(job):
    kind, arg = job
    out = []
    if kind == "crypto":
        for s in arg:
            for row in FA_ROWS:
                r = be.simulate_coin(s, _cfg(row), start=FULL[0], end=FULL[1], detail=False)
                out.append({"kind": "crypto", "what": f"{s} {row}", "positions": len(r["trades"]),
                            "fills": int((r["tranches"].kind != "end").sum()), "violations": len(r["fills_audit"]),
                            "first": r["fills_audit"][:3]})
            out += _bench_audit_runs(s)
            be.clear_cache()
            bd._coin_hours_full.cache_clear()
            bd._bars_cached.cache_clear()
    elif kind == "grid":
        s = arg
        r0 = be.simulate_coin(s, be.ROWS["R0"], start=bg.GRID_START, end=bg.GRID_END, detail=False)
        out.append({"kind": "crypto", "what": f"{s} R0 (grid window)", "positions": len(r0["trades"]),
                    "fills": int((r0["tranches"].kind != "end").sum()), "violations": len(r0["fills_audit"]),
                    "first": r0["fills_audit"][:3]})
        for fill in ("through", "touch"):
            for name, fn in (("G-A", lambda f: bg.grid_ga(s, r0["trades"], fill=f)),
                             ("G-B", lambda f: bg.grid_gb(s, r0, fill=f)),
                             ("G-0", lambda f: bg.grid_g0(s, fill=f))):
                g = fn(fill)
                out.append({"kind": "grid", "what": f"{s} {name} {fill}", "positions": len(g["deployments"]),
                            "fills": len(g["fills"]), "violations": len(g["fills_audit"]),
                            "first": [str(v) for v in g["fills_audit"][:3]]})
    else:
        from analysis_2026 import bb_stocks as bk
        for which, cfg, a, b in arg:
            r = bk.stock_trades(which, cfg, a, b)
            out.append({"kind": "stocks", "what": f"stocks {which} {cfg.bars} {a}..{b}", "positions": len(r["trades"]),
                        "fills": int((r["tranches"].kind != "mark").sum()), "violations": len(r["fills_audit"]),
                        "first": [str(v) for v in r["fills_audit"][:3]], "names": len(r["names"])})
    return out


def fill_audit(quick: bool = False, workers: int = 4, **_) -> dict:
    """Controls, "Fill audit" (module docstring, control 5)."""
    from analysis_2026 import bb_stocks as bk
    coins = list(bd.COINS[:6]) if quick else list(bd.COINS)
    nw = max(1, workers)
    jobs = [("crypto", coins[i::nw]) for i in range(nw) if coins[i::nw]]
    jobs += [("grid", s) for s in (bd.M1_COINS[:2] if quick else bd.M1_COINS)]
    if quick:
        jobs += [("stocks", [("etfs", bk.StockCfg(), bk.START, bk.END), ("user", bk.StockCfg(), bk.START, bk.END)])]
    else:
        jobs += [("stocks", [("members", bk.StockCfg(), bk.START, bk.END),
                             ("members", bk.StockCfg(bars="1w"), bk.START, bk.END),
                             ("members", bk.StockCfg(), *bk.WINDOWS["1996-2000"])]),
                 ("stocks", [("etfs", bk.StockCfg(), bk.START, bk.END), ("user", bk.StockCfg(), bk.START, bk.END)])]
    R = _pmap(_fa_dispatch, jobs, workers)
    rows = [x for r in R for x in r]
    viol = sum(x["violations"] for x in rows)
    n_bench = sum(x["kind"] == "bench" for x in rows)
    res = {"quick": quick, "passed": bool(viol == 0 and len(rows) > 0 and n_bench > 0), "runs": rows,
           "crypto_rows": list(FA_ROWS), "coins": coins, "grid_coins": list(bd.M1_COINS),
           "bench_runs": "bb_bench.ml_coin (H2's moneyline_ref benchmark): perpetual Full, spot Full and spot "
                         "pre-perpetual block, audited by bench_fill_audit",
           "rule": "every engine's fills_audit empty, and bench_fill_audit empty on the indicator benchmark"}
    res["summary"] = {"runs": len(rows), "fills": int(sum(x["fills"] for x in rows)), "violations": int(viol),
                      "crypto_runs": sum(x["kind"] == "crypto" for x in rows),
                      "grid_runs": sum(x["kind"] == "grid" for x in rows),
                      "stock_runs": sum(x["kind"] == "stocks" for x in rows), "bench_runs": int(n_bench)}
    _say(f"  fill audit: {len(rows)} runs, {res['summary']['fills']:,} fills, {viol} violations; "
         f"{'ok' if res['passed'] else 'FAIL'}")
    return res


# ============================================================================ 6-7. grid path check, indicator cross-check
def grid_path_check(**_) -> dict:
    """Controls, "Grid path check": bb_grid.path_check()."""
    pc = bg.path_check(verbose=False)
    T = pc["table"]
    res = {"passed": bool(pc["passed"]), "tol": pc["tol"], "table": T,
           "rule": "|engine - 1-second P&L| <= 10% of the 1-second gross grid profit on every non-stress path"}
    res["summary"] = {"paths": int((~T.stress).sum()), "max_rel_to_grid_profit": float(T[~T.stress].rel_to_grid_profit.max()),
                      "stress_paths_ok": bool(T[T.stress].ok.all())}
    _say(f"  grid path check: max |diff| / grid profit {res['summary']['max_rel_to_grid_profit']:.5f} "
         f"(tol {pc['tol']}); {'ok' if res['passed'] else 'FAIL'}")
    return res


def indicator_crosscheck(**_) -> dict:
    """Controls, "Indicator cross-check": bb_bench.indicator_crosscheck() (a benchmark)."""
    from analysis_2026 import bb_bench as bb
    lines: list = []
    out = bb.indicator_crosscheck(say=lines.append)
    res = {"passed": bool(out["pass"]), "detail": out, "lines": lines,
           "rule": "|log10(benchmark multiple / 12.4)| < 1 (moneyline_ref BTC 1x, perpetual, 5.14's sizing)"}
    p = out["bench_perp_5.14cfg"]
    res["summary"] = {"multiple": p["multiple"], "log10_ratio_vs_12.4": p["log10_ratio_vs_12.4"],
                      "window": list(out["window"])}
    _say(f"  indicator cross-check (benchmark): {p['multiple']:.2f}x vs 12.4x (log10 ratio "
         f"{p['log10_ratio_vs_12.4']:+.2f}); {'ok' if res['passed'] else 'FAIL'}")
    return res


# ============================================================================ runner
FUNCS = {"engine_known_answer": engine_known_answer, "inference_known_answer": inference_known_answer,
         "lookahead": lookahead_check, "liquidation": liquidation_check, "fill_audit": fill_audit,
         "grid_path_check": grid_path_check, "indicator_crosscheck": indicator_crosscheck}


def _summary(results: dict, quick: bool, partial: bool, seconds: float) -> dict:
    inf = results.get("inference_known_answer")
    level95 = inf.get("level95") if inf and "level95" in inf else None
    level_noedge = inf.get("level_noedge") if inf and "level_noedge" in inf else None
    s = {}
    for name in CONTROLS:
        if name in results:
            r = results[name]
            s[name] = {"passed": bool(r.get("passed", False)), **(r.get("summary") or {}),
                       "seconds": r.get("seconds")}
            if "error" in r:
                s[name]["error"] = r["error"].strip().splitlines()[-1]
    all_passed = bool(not partial and all(n in results for n in CONTROLS)
                      and all(bool(results[n].get("passed")) for n in CONTROLS)
                      and level95 is not None and level_noedge is not None
                      and np.isfinite(level95) and np.isfinite(level_noedge))
    s.update(all_passed=all_passed, level95=level95, level_noedge=level_noedge, quick=quick,
             valid_gate=bool(not quick and not partial), partial=partial,
             generated=pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), seconds=round(seconds, 1),
             prereg="analysis_2026/BB_REPLICATION_PREREG.md, Controls; Addendum 2 (inference control)")
    return s


def _summary_txt(s: dict, results: dict) -> str:
    L = ["BB replication controls (pre-registration: Controls, run before primary results are read)",
         f"generated {s['generated']}; {'QUICK run (reduced sizes; not a valid gate)' if s['quick'] else 'full run'}"
         f"{'; PARTIAL (--only)' if s['partial'] else ''}; {s['seconds']}s", ""]
    for name in CONTROLS:
        if name not in s:
            L.append(f"{name:24s} not run")
            continue
        r = s[name]
        L.append(f"{name:24s} {'PASS' if r['passed'] else 'FAIL'}" + (f"  ERROR: {r['error']}" if "error" in r else ""))
        rule = results[name].get("rule") or results[name].get("reject_rule")
        if rule:
            L.append(f"  rule: {rule}")
        for k, v in r.items():
            if k in ("passed", "error", "seconds"):
                continue
            L.append(f"  {k}: {json.dumps(_js(v))}")
    L += ["", f"all_passed: {s['all_passed']}", f"level95 (bootstrap-t level for 95% bounds): {s['level95']}",
          f"level_noedge (NO EDGE bound level): {s['level_noedge']}"]
    return "\n".join(L) + "\n"


def run(quick: bool = False, out=None, workers: int = 4, only=None, tmp=None) -> dict:
    """Run the controls (all of them unless `only`), write the outputs, return the summary."""
    t0 = time.time()
    out_dir = Path(out) if out else (OUT_QUICK if quick else OUT)
    if isinstance(only, str):
        only = [x.strip() for x in only.split(",") if x.strip()]
    sel = [c for c in CONTROLS if (not only or c in only)]
    unknown = sorted(set(only or ()) - set(CONTROLS))
    if unknown:
        raise SystemExit(f"unknown controls {unknown}; choose from {list(CONTROLS)}")
    _say(f"bb_controls run ({'quick' if quick else 'full'}; {workers} workers) -> {out_dir}")
    results = {}
    for name in sel:
        t1 = time.time()
        _say(f"{name} ...")
        try:
            r = FUNCS[name](quick=quick, workers=workers, tmp=tmp)
        except Exception:
            r = {"passed": False, "error": traceback.format_exc()}
            _say(f"  ERROR in {name}:\n{r['error']}")
        r["seconds"] = round(time.time() - t1, 1)
        results[name] = r
        _say(f"{name}: {'PASS' if r['passed'] else 'FAIL'} ({r['seconds']}s)")
    partial = len(sel) < len(CONTROLS)
    s = _summary(results, quick, partial, time.time() - t0)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, r in results.items():
        (out_dir / f"{name}.json").write_text(json.dumps(_js(r), indent=1) + "\n")
    if "inference_known_answer" in results and "level95" in results["inference_known_answer"]:
        r = results["inference_known_answer"]
        inf = {"level95": r["level95"], "level_noedge": r["level_noedge"], "widened": r["widened"],
               "passed": r["passed"], "defaults": {"level95": 0.95, "level_noedge": bst.LEVEL_NOEDGE},
               "rule": "Addendum 2: if the bootstrap-t 95% bound misses the true mean more than 5% of the time, use "
                       "the smallest level at which it misses at most 5% (level95) and scale the NO EDGE tail "
                       "0.05/12 by the same factor (level_noedge)",
               **{k: v for k, v in r.items() if k not in ("bb_stats_output",)}}
        (out_dir / "inference.json").write_text(json.dumps(_js(inf), indent=1) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(_js(s), indent=1) + "\n")
    (out_dir / "summary.txt").write_text(_summary_txt(s, results))
    _say(f"all_passed: {s['all_passed']}; level95 {s['level95']}, level_noedge {s['level_noedge']}; "
         f"{time.time() - t0:.0f}s; wrote {out_dir}")
    return s


# ============================================================================ self-test
def _st_compare(say):
    a = pd.DataFrame({"pos": [0, 1], "time": pd.DatetimeIndex(["2025-01-01", None], tz="UTC"), "px": [1.0, np.nan],
                      "kind": ["entry", "stop"]})
    assert compare_frames(a, a.copy())[0]
    b = a.copy()
    b.loc[1, "px"] = 2.0
    ok, why = compare_frames(a, b, "pos")
    assert not ok and "px" in why and "pos=1" in why
    c = a.copy()
    c.loc[0, "time"] = pd.Timestamp("2025-01-02", tz="UTC")
    assert not compare_frames(a, c)[0] and not compare_frames(a, a.iloc[:1])[0]
    d = a.copy()
    d.loc[1, "kind"] = "liq"
    assert not compare_frames(a, d)[0]
    e = a.copy()
    e.loc[0, "px"] = 1.0 + 2e-16
    assert not compare_frames(a, e)[0] and compare_frames(a, e, rtol=1e-12)[0]
    e.loc[0, "px"] = 1.0 + 1e-9
    assert not compare_frames(a, e, rtol=1e-12)[0] and abs(max_rel_diff(a, e) - 1e-9) < 1e-15
    say("  compare_frames: equal tables equal (NaN / NaT included); a changed price, time, kind or row count is found; "
        "rtol 1e-12 absorbs a 1-ulp difference and not a 1e-9 one")


def _st_fees(say):
    tr = pd.DataFrame({"pos": [0] * 5, "kind": ["entry", "add", "add", "tp", "stop"],
                       "px": [100.0, 102.0, 105.0, 130.0, 90.0], "frac": [1 / 3, 1 / 3, 1 / 3, np.nan, np.nan]})
    q = (1 / 3) * (1 / 100 + 1 / 102 + 1 / 105)
    tr.loc[3, "frac"] = 0.5 * q * 130.0
    tr.loc[4, "frac"] = 0.5 * q * 90.0
    f, bad = recompute_fees(tr, "SYN")
    rt = 0.0005 + 0.0007
    want = rt * 1.0 + 0.0002 * 0.5 * q * 130.0 + rt * 0.5 * q * 90.0
    assert bad == 0 and abs(f.iloc[0] - want) < 1e-15, (f.iloc[0], want)
    tr2 = tr.copy()
    tr2.loc[4, "frac"] *= 1.01
    assert recompute_fees(tr2, "SYN")[1] == 1
    fb, _ = recompute_fees(tr, "BTC", "vip")
    assert abs(fb.iloc[0] - ((0.0003 + 0.0002) * (1.0 + 0.5 * q * 90.0) + 0.0001 * 0.5 * q * 130.0)) < 1e-15
    # on the engine: a short martingale coin, base fees
    out = _mg_job((0, 2 * 365 * 24, 0.01, SEED))
    for k in _MG_ROWS:
        d = out[k]
        assert d["audit"] == 0 and d["bad_notional"] == 0 and np.max(np.abs(d["fees_re"] - d["fees"]), initial=0) <= 1e-12
    say(f"  recompute_fees: hand case (entry, two adds, TP half at maker, stop) exact; a wrong closing notional is "
        f"flagged; on the engine ({sum(len(out[k]['ret']) for k in out)} positions, 4 rows) fees match to 1e-12")


def _st_size_rule(say):
    """The inference size rule is the point rule (coding choice 1; regression for the controls review's finding that
    the first build's Clopper-Pearson rule passed up to 16 of 200 rejections)."""
    passing = [k for k in range(201) if size_rule(k, 200)["passed"]]
    assert passing == list(range(11)), passing                                  # 10/200 = 5.0% passes, 11 fails
    for k in range(201):                                                        # = bb_stats' ok_reject / binomial
        s = size_rule(k, 200)
        assert s["passed"] == (k / 200 <= 0.05)
        assert s["binomial_5pct_ok"] == bool(sps.binom.sf(k - 1, 200, 0.05) > 0.05)
    a, b = size_rule(10, 200), size_rule(16, 200)
    assert a["passed"] and not b["passed"] and b["binomial_5pct_ok"] is False and b["ci95"][0] < 0.05
    assert not size_rule(0, 0)["passed"] and size_rule(2, 40)["passed"] and not size_rule(3, 40)["passed"]
    oc = {p: float(sps.binom.cdf(10, 200, p)) for p in (0.03, 0.05, 0.09)}     # P(pass | true size p)
    assert oc[0.09] < 0.05 and oc[0.03] > 0.95 and 0.5 < oc[0.05] < 0.65
    assert abs(bst.noedge_level_for(0.955) - 0.99625) < 1e-12 and bst.noedge_level_for(None) == bst.LEVEL_NOEDGE
    say(f"  size rule (point rate <= 5%): passes 0..10 of 200 and fails 11 and above (16/200, CI lower end "
        f"{b['ci95'][0]:.3f}, passed the first build's rule and fails now); P(pass) at a true size of 3% / 5% / 9%: "
        f"{oc[0.03]:.3f} / {oc[0.05]:.3f} / {oc[0.09]:.3f}; Addendum 2's example 95.5% -> 99.625% reproduced by "
        f"noedge_level_for")


def _st_cuts(say):
    C = draw_cuts()
    assert len(C) >= 50 and (C.t.map(lambda t: t.minute) != 0).all()
    assert C.in_2025_06_2026_10.sum() >= 10 and C.weekend.sum() >= 10 and C.near_window.sum() >= 10
    assert not C.t.map(lambda t: str(t.date()) in EXCLUDE_DAYS).any()
    assert near_window(pd.Timestamp("2025-07-01 11:59", tz="UTC")) and not near_window(
        pd.Timestamp("2025-07-01 21:01", tz="UTC"))                   # 07:59 / 17:01 New York (EDT)
    C2 = draw_cuts()
    assert C.t.equals(C2.t)
    say(f"  draw_cuts: {len(C)} cuts, none on an hour; {int(C.in_2025_06_2026_10.sum())} in 2025-06..2026-10, "
        f"{int(C.weekend.sum())} on weekends, {int(C.near_window.sum())} within 2 h of a window; reproducible")


def _synthetic_data_dir(root: Path, sym: str, days: int = 400, seed: int = 3) -> None:
    """A synthetic coin under root (spot, perpetual, mark, funding, 1-minute files) for the perturbation known
    answers: 1-minute GBM, hourly and daily bars aggregated from it."""
    rng = np.random.default_rng(seed)
    n = days * 1440
    idx = pd.date_range("2025-01-01", periods=n, freq="min", tz="UTC")
    lp = np.log(100.0) + np.cumsum(0.0008 * rng.standard_normal(n))
    c = np.round(np.exp(lp), 3)
    o = np.r_[100.0, c[:-1]]
    hi = np.round(np.maximum(o, c) * (1 + 0.0003 * rng.random(n)), 3)
    lo = np.round(np.minimum(o, c) * (1 - 0.0003 * rng.random(n)), 3)
    vol = rng.uniform(1, 5, n)
    tr = rng.integers(0, 30, n)
    tr[rng.random(n) < 0.002] = 0
    m = pd.DataFrame({"open_time": idx.as_unit("ms"), "open": o.astype(np.float32), "high": hi.astype(np.float32),
                      "low": lo.astype(np.float32), "close": c.astype(np.float32), "volume": vol.astype(np.float32),
                      "quote_volume": (vol * c).astype(np.float32), "trades": tr.astype(np.int32),
                      "taker_buy_quote": (0.5 * vol * c).astype(np.float32)})
    for k in ("h1_spot", "h1_um", "h1_mark", "m1_um", "funding", "d1_um_all"):
        (root / k).mkdir(parents=True, exist_ok=True)
    m.to_parquet(root / "m1_um" / f"{sym}USDT.parquet", index=False)
    d = bd._decimals(bd.M1_GRID.get(sym, 0.001))
    mm = pd.DataFrame({k: np.round(m[k].to_numpy(np.float64), d) for k in PRICE}, index=idx)
    mm["vol"], mm["qv"], mm["tr"] = vol, vol * c, tr
    live = mm[mm.tr > 0]
    g = live.groupby(live.index.floor("h"))
    h = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "volume": g.vol.sum(), "quote_volume": g.qv.sum(), "trades": g.tr.sum(),
                      "taker_buy_quote": 0.5 * g.qv.sum()})
    h.index.name = "open_time"
    h = h.reset_index()
    h["open_time"] = h.open_time.dt.as_unit("ms")
    h.to_parquet(root / "h1_um" / f"{sym}USDT.parquet", index=False)
    sp = h.copy()
    for k in PRICE:
        sp[k] = sp[k] * 1.0005
    sp.to_parquet(root / "h1_spot" / f"{sym}USDT.parquet", index=False)
    h[["open_time"] + PRICE].to_parquet(root / "h1_mark" / f"{sym}USDT.parquet", index=False)
    ft = pd.date_range("2025-01-01", periods=days * 3, freq="8h", tz="UTC").as_unit("ms")
    pd.DataFrame({"calc_time": ft, "rate": 0.0001, "interval_h": 8.0}).to_parquet(
        root / "funding" / f"{sym}USDT.parquet", index=False)
    dd = h.groupby(pd.DatetimeIndex(h.open_time).floor("D")).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"), quote_volume=("quote_volume", "sum"), trades=("trades", "sum"),
        taker_buy_quote=("taker_buy_quote", "sum"))
    dd.index.name = "open_time"
    dd = dd.reset_index()
    dd["open_time"] = dd.open_time.dt.as_unit("ms")
    dd.to_parquet(root / "d1_um_all" / f"{sym}USDT.parquet", index=False)
    (root / "d1_um_all" / "_status.json").write_text("{}")


def _st_perturb(say):
    """Perturbation known answers on a synthetic data directory, the engine's decisions before each cut unchanged
    through the production loaders, and a planted one-day look-ahead caught by the same comparison."""
    sym = "BTC"                                                       # a 1-minute coin name: minutes are loaded
    with tempfile.TemporaryDirectory(prefix="bbctl_st_") as tmpd:
        src = Path(tmpd) / "src"
        _synthetic_data_dir(src, sym)
        rng = np.random.default_rng(1)
        cuts = []
        while len(cuts) < 6:
            t = pd.Timestamp("2025-06-01", tz="UTC") + pd.Timedelta(minutes=int(rng.integers(0, 200 * 1440)))
            if t.minute != 0:
                cuts.append(t)
        cfgs = [be.ROWS["R0"], be.ROWS["S1"], be.ROWS["S8"], be.ROWS["S11"], be.h4_touch_cfg()]
        with _DataDir(src):
            base = {i: be.simulate_coin(sym, c, start="2025-04-01", end="2026-02-01", mmr=0.005, detail=False)
                    for i, c in enumerate(cfgs)}
            H0 = bd.coin_hours(sym)
            M0 = bd.minutes(sym, "2025-01-01", "2026-12-31")
            assert sum(len(b["trades"]) for b in base.values()) >= 15
        n_dec, n_changed, leak_caught = 0, 0, 0
        for j, t in enumerate(cuts):
            dst = Path(tmpd) / f"p{j}"
            perturb_data_dir(src, dst, t, {sym: (sym, [sym])}, m1=(sym,))
            # file-level known answers
            for kind, per, vol in (("h1_um", H_NS, True), ("h1_spot", H_NS, True), ("h1_mark", H_NS, False),
                                   ("m1_um", MIN_NS, True), ("d1_um_all", DAY_NS, True)):
                a = pd.read_parquet(src / kind / f"{sym}USDT.parquet")
                b = pd.read_parquet(dst / kind / f"{sym}USDT.parquet")
                ot = _ns(a.open_time)
                b0 = int(t.value) - int(t.value) % per
                aft = ot >= t.value if per == MIN_NS else ot > b0
                st = np.zeros(len(ot), bool) if per == MIN_NS else ot == b0
                bef = ~aft & ~st
                assert a.dtypes.equals(b.dtypes), kind
                for k in PRICE:
                    x, y = a[k].to_numpy(np.float64), b[k].to_numpy(np.float64)
                    assert np.array_equal(x[bef], y[bef]), (kind, k)
                    want = (x[aft] * 1.5).astype(a[k].dtype).astype(np.float64)
                    assert np.array_equal(y[aft], want), (kind, k)
                    if st.any() and k == "open":
                        assert np.array_equal(x[st], y[st])
                if vol:
                    for k in VOLS:
                        x, y = a[k].to_numpy(np.float64), b[k].to_numpy(np.float64)
                        assert np.array_equal(x[bef], y[bef])
                        assert np.array_equal(y[aft | st], (x[aft | st] * 0.5).astype(a[k].dtype).astype(np.float64))
                    assert np.array_equal(a.trades.to_numpy(), b.trades.to_numpy())
            assert (dst / "funding").is_symlink()
            with _DataDir(dst):
                H1 = bd.coin_hours(sym)
                M1 = bd.minutes(sym, "2025-01-01", "2026-12-31")
                hs = t.floor("h")
                mm = M1[(M1.index >= hs) & (M1.index < hs + pd.Timedelta("1h")) & (M1.trades > 0)]
                tick = bd.TICK[sym]
                assert abs(H1.at[hs, "high"] - max(mm.high.max(), H1.at[hs, "open"])) <= 0.5 * tick
                assert abs(H1.at[hs, "low"] - mm.low.min()) <= 0.5 * tick and H1.at[hs, "open"] == H0.at[hs, "open"]
                assert H1.loc[:hs - pd.Timedelta("1h")].equals(H0.loc[:hs - pd.Timedelta("1h")])
                assert M1.loc[:t - pd.Timedelta("1min")].equals(M0.loc[:t - pd.Timedelta("1min")])
                for i, c in enumerate(cfgs):
                    r = be.simulate_coin(sym, c, start="2025-04-01", end="2026-02-01", mmr=0.005, detail=False)
                    ta, tb = _engine_tables(base[i], c, t), _engine_tables(r, c, t)
                    for part in ta:
                        ok, why = compare_frames(ta[part], tb[part], "pos")
                        assert ok, (t, c, part, why)
                        n_dec += len(ta[part])
                    k_, bad = pending_decisions(base[i], r, c, t)
                    assert not bad, (t, c, bad)
                    n_dec += sum(k_.values())
                    assert not r["fills_audit"]
                    n_changed += _all_changed(base[i], r)
            # planted leak: the same comparison on a simulator that reads every hourly bar one day early
            for i, c in enumerate(cfgs[:3]):
                Ha = H0.copy()
                Hb = H1.copy()
                leak = lambda H: H.shift(-24).ffill()                  # noqa: E731
                ra = be.simulate_coin("LEAK", c, start="2025-04-01", end="2026-02-01", hours=leak(Ha), mmr=0.005,
                                      detail=False)
                rb = be.simulate_coin("LEAK", c, start="2025-04-01", end="2026-02-01", hours=leak(Hb), mmr=0.005,
                                      detail=False)
                ta, tb = _engine_tables(ra, c, t), _engine_tables(rb, c, t)
                leak_caught += any(not compare_frames(ta[p], tb[p])[0] for p in ta) or \
                    bool(pending_decisions(ra, rb, c, t)[1])
            shutil.rmtree(dst)
        assert n_changed > 0 and leak_caught > 0, (n_changed, leak_caught)
    say(f"  perturbation (synthetic data directory, {len(cuts)} cuts): prices after t x 1.5 and volumes x 0.5 in the "
        f"spot, perpetual, mark, 1-minute and daily files, earlier rows and opens unchanged, dtypes kept, funding "
        f"linked; the straddling perpetual hour equals its live perturbed minutes; R0 / S1 / S8 / S11 / H4 touch via "
        f"bb_data loaders: {n_dec:,} decisions before the cuts unchanged, later fills changed in {n_changed} runs; a "
        f"planted one-day look-ahead is caught at {leak_caught} of {3 * len(cuts)} cut x row checks")


def _st_stock_lookahead(say):
    """The stock comparison path on bb_stocks' synthetic universe: unchanged before the cut, and a planted leak (the
    perturbation started one session early) is caught."""
    from analysis_2026 import bb_stocks as bk
    base = bk._synthetic_universe(30, 900, mu=0.0005, seed=21, sub=24, member_frac=0.8, end=bk.END)
    for f in base.values():
        f["tr"] = f.close.to_numpy() * np.linspace(1.0, 1.02, len(f))      # a dividend stream
        f.attrs["cost"] = 0.0003
    cal = bk.calendar(base)
    win = (cal[250], bk.END)
    r0 = bk.stock_trades("syn", bk.StockCfg(), *win, ohlc=base)
    rng = np.random.default_rng(4)
    n_ok, caught = 0, 0
    for g in rng.choice(np.arange(300, len(cal) - 5), 6, replace=False):
        cut = cal[int(g)]
        t_cut = (pd.Timestamp(cut) + pd.Timedelta(hours=11)).tz_localize(bd.NY).tz_convert("UTC")
        for early, want_equal in ((0, True), (3, False)):
            pert = bk._perturb_after(base, cal[int(g) - early])
            rb = bk.stock_trades("syn", bk.StockCfg(), *win, ohlc=pert)
            ta, tb = r0["tranches"], rb["tranches"]
            ka = ta[(ta.time < t_cut) & (ta.kind != "mark")][["sym", "time", "px", "kind"]].sort_values(
                ["sym", "time", "kind"])
            kb = tb[(tb.time < t_cut) & (tb.kind != "mark")][["sym", "time", "px", "kind"]].sort_values(
                ["sym", "time", "kind"])
            eq = compare_frames(ka, kb)[0]
            if want_equal:
                assert eq, cut
                n_ok += 1
            else:
                caught += not eq
    assert caught > 0
    say(f"  stock comparison (bb_stocks' synthetic universe): {n_ok} cuts unchanged before the cut; a leak (prices "
        f"perturbed from 3 sessions before the cut) caught at {caught} of {n_ok} cuts")


def _perturb_hours(H: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """In-memory mirror of _perturb_parquet on a coin_hours-shaped frame (traded, signal and mark prices): the hours
    after the one containing t x 1.5; that hour's high and close x 1.5, its open and low kept."""
    H = H.copy()
    b0 = t.floor("h")
    aft, on = H.index > b0, H.index == b0
    for c in PRICE:
        for k in (c, "sig_" + c, "mark_" + c):
            if k in H.columns:
                H.loc[aft, k] = H.loc[aft, k] * 1.5
                if c in ("high", "close"):
                    H.loc[on, k] = H.loc[on, k] * 1.5
    return H


def _rule6_frame() -> pd.DataFrame:
    """bb_engine's rule-6 path (the controls review's r4): a signal close 2025-03-04 00:00, entry 2025-03-04 11:00 at
    101 (06:00 New York), closes at 101.05 then 100.9, so whether the trend exit decided at a close inside rule 6's
    72 h is acted on turns on the mark at that close; mark = last price."""
    df = be._flat_hours("2024-11-01", 140)
    be._bar(df, "2025-03-03 23:00", 100.0, 120.5, 100.0, 120.0)
    lin = np.linspace(120.0, 101.0, 11)
    for k, px in enumerate(lin):
        be._bar(df, f"2025-03-04 {k:02d}:00", 120.0 if k == 0 else float(lin[k - 1]), 120.0, px, px)
    be._flat(df, "2025-03-04 11:00", "2025-03-04 23:00", 101.0)
    be._bar(df, "2025-03-04 11:00", 101.0, 101.05, 101.0, 101.05)
    be._flat(df, "2025-03-04 12:00", "2025-03-04 23:00", 101.05)
    be._flat(df, "2025-03-05 00:00", "2025-03-20 23:00", 100.9)
    be._bar(df, "2025-03-06 18:00", 100.8, 100.8, 100.8, 100.8)
    be._bar(df, "2025-03-05 18:00", 100.85, 100.9, 100.85, 100.9)
    df = be._fin(df)
    for c in PRICE:
        df["mark_" + c] = df[c]
    return df


def _st_pending(say):
    """pending_decisions (controls review finding 2): (i) a planted 16-hour leak inside rule 6's decision (its "mark
    at that daily close" read 16 h ahead), which the fill-stamped tables never see, is caught by exit_decisions;
    (ii) no false failure on a correct engine at cuts placed between decisions and their fills, for the look-ahead
    rows, the pre-emption excuse exercised."""
    H0 = _rule6_frame()
    cfg = be.ROWS["R0"]

    def leak(H, hz):
        H = H.copy()
        fut = H["close"].shift(-hz)
        m = (H.index.hour == 23) & fut.notna().to_numpy()
        H.loc[m, "mark_close"] = fut[m]
        return H

    cuts = [t for t in pd.date_range("2025-03-04 12:07", "2025-03-07 23:59", freq="37min", tz="UTC") if t.minute != 0]
    ra = be.simulate_coin("SYN6", cfg, hours=leak(H0, 16), mmr=0.005)
    assert (ra["tranches"].kind == "exit").sum() == 1
    old = new = 0
    n_leak_cuts = len(cuts)
    for t in cuts:
        rb = be.simulate_coin("SYN6", cfg, hours=leak(_perturb_hours(H0, t), 16), mmr=0.005)
        ta, tb = _engine_tables(ra, cfg, t), _engine_tables(rb, cfg, t)
        o = any(not compare_frames(ta[p], tb[p], "pos")[0] for p in ta)
        old += o
        new += o or bool(pending_decisions(ra, rb, cfg, t)[1])
    be.clear_cache()
    assert new >= 10 and new > old, (old, new)
    # (ii) a correct engine: trending synthetic hours, cuts between decisions (cause_time) and fills
    n = int(3 * 365 * 24)
    rng = np.random.default_rng(11)
    lens = rng.geometric(1 / (40 * 24), size=200)
    drift = np.repeat(np.where(np.arange(200) % 2 == 0, 0.0006, -0.0004), lens)[:n]
    H1 = be._gbm_hours(n, 0.008, 5, start="2022-01-03", drift=drift)
    for c in PRICE:
        H1["mark_" + c] = H1[c]
    rows = {r: _cfg(r) for r in ("R0", "S1", "S8", "S11", "H4_touch")}
    base = {r: be.simulate_coin("SYN", c, hours=H1, mmr=0.005, detail=False) for r, c in rows.items()}
    spans = []
    for r in base.values():
        tr = r["tranches"]
        tr = tr[tr.kind.isin(["exit", "entry"]) & (tr.time - tr.cause_time > pd.Timedelta("2min"))]
        spans += list(zip(tr.cause_time, tr.time))
    cuts = []
    for j in rng.choice(len(spans), min(60, len(spans)), replace=False):
        c, f = spans[int(j)]
        t = c + pd.Timedelta(minutes=int(rng.integers(1, int((f - c).total_seconds() // 60))))
        if t.minute != 0:
            cuts.append(t)
    fails, cnt, naive = [], {}, 0
    for t in cuts:
        Hp = _perturb_hours(H1, t)
        for r, c in rows.items():
            rp = be.simulate_coin("SYN", c, hours=Hp, mmr=0.005, detail=False)
            ta, tb = _engine_tables(base[r], c, t), _engine_tables(rp, c, t)
            fails += [(r, p) for p in ta if not compare_frames(ta[p], tb[p], "pos")[0]]
            k_, bad = pending_decisions(base[r], rp, c, t)
            fails += bad
            for p, v in k_.items():
                cnt[p] = cnt.get(p, 0) + v
            naive += set(_exit_decisions(base[r], t)) != set(_exit_decisions(rp, t))
        be.clear_cache()
    assert not fails and cnt["pending_entries"] > 0 and cnt["exit_decisions"] > 0 and naive > 0, (fails[:3], cnt, naive)
    say(f"  pending decisions: a 16-h leak inside rule 6's decision is caught at {new} of {n_leak_cuts} cuts (the "
        f"fill-stamped tables alone: {old}); correct engine, {len(cuts)} cuts between decisions and fills x "
        f"{len(rows)} rows: 0 false failures ({cnt['exit_decisions']:,} exit decisions, "
        f"{cnt['pending_entries']} pending entries compared; {naive} exits pre-empted after t in one run and excused)")


def _st_bench_audit(say):
    """bench_fill_audit (controls review finding 3) on a synthetic coin: clean for both vehicles, every branch
    (entry, signal exit, liquidation, delisting close) exercised, and planted violations caught."""
    from analysis_2026 import bb_bench as bb
    n = int(4 * 365 * 24)
    rng = np.random.default_rng(2)
    lens = rng.geometric(1 / (60 * 24), size=200)
    drift = np.repeat(np.where(np.arange(200) % 2 == 0, 0.0004, -0.0003), lens)[:n]
    H = be._gbm_hours(n, 0.008, 9, start="2020-01-06", drift=drift)
    H["quote_volume"] = H["sig_quote_volume"] = 1e6
    a, b = "2021-01-01", "2023-12-31"
    for veh in ("perp", "spot"):
        r = bb.ml_coin("SYN", a, b, hours=H, vehicle=veh)
        assert len(r["trades"]) >= 10 and r["fills_audit"] == []
        assert bench_fill_audit(r, bb.spot_hours(H) if veh == "spot" else bb._norm_hours(H)) == []
    r = bb.ml_coin("SYN", a, b, hours=H)
    Hv = bb._norm_hours(H)
    T = r["trades"]
    e0 = pd.Timestamp(T.entry1_time.iat[1])                          # a state change (not the window start)
    i0 = int(np.searchsorted(_ns(Hv.index), (e0 - pd.Timedelta("1D")).value))
    planted = {
        "price outside the bar": dict(r, trades=T.assign(entry1_px=T.entry1_px * 1.5)),
        "entry an hour early": dict(r, trades=T.assign(entry1_time=T.entry1_time - pd.Timedelta("1h"))),
        "exit an hour early": dict(r, trades=T.assign(exit_time=T.exit_time - pd.Timedelta("1h"))),
        # a day early at that hour's own open: only the cause check (the state known 1 h before) can see it
        "entry a day early at its open": dict(r, trades=T.iloc[1:2].assign(entry1_time=Hv.index[i0],
                                                                            entry1_px=Hv.open.iat[i0])),
    }
    caught = {k: len(bench_fill_audit(v, Hv)) for k, v in planted.items()}
    assert all(v > 0 for v in caught.values()), caught
    assert any("caused" in x for x in bench_fill_audit(planted["entry a day early at its open"], Hv))
    Hz = Hv.copy()
    Hz.loc[pd.DatetimeIndex(T.entry1_time.iloc[:3]), "trades"] = 0
    assert len(bench_fill_audit(r, Hz)) >= 3
    # liquidation (mark low crashes while long) and delisting close (perp_end, in a trades == 0 bar)
    pos1 = T.iloc[1]
    hl = pd.Timestamp(pos1.entry1_time) + pd.Timedelta("5h")
    HL = H.copy()
    HL["mark_low"] = HL["low"]
    HL.loc[hl, "mark_low"] = 1e-6
    rl = bb.ml_coin("SYN", a, b, hours=HL)
    assert (rl["trades"].exit_reason == "liq").sum() == 1 and bench_fill_audit(rl, bb._norm_hours(HL)) == []
    HL2 = bb._norm_hours(HL)
    HL2.loc[hl, "mark_low"] = HL2.loc[hl, "low"]
    assert any("not reached" in x for x in bench_fill_audit(rl, HL2))
    HD = H.copy()
    HD["perp_end"] = False
    HD.loc[hl, ["perp_end"]] = True
    HD.loc[hl, "trades"] = 0
    rd = bb.ml_coin("SYN", a, b, hours=HD)
    assert (rd["trades"].exit_reason == "delist").sum() == 1 and bench_fill_audit(rd, bb._norm_hours(HD)) == []
    TD = rd["trades"]
    bad = dict(rd, trades=TD.assign(exit_px=np.where(TD.exit_reason == "delist", TD.exit_px * 1.01, TD.exit_px)))
    assert bench_fill_audit(bad, bb._norm_hours(HD))
    say(f"  bench_fill_audit (H2's indicator benchmark, synthetic): perp and spot vehicles clean ({len(T)} positions); "
        f"a liquidation and a delisting close (in a trades == 0 bar) pass; caught: "
        f"{', '.join(f'{k} ({v})' for k, v in caught.items())}, outages at entries, an unreached liquidation, a "
        f"delisting off the close")


def _st_overlay_account(say):
    """The H10 overlay account's look-ahead comparison (controls review finding 4) on synthetic 1-minute GBM: R0 +
    G-A merged by bb_grid.merge_ga and assembled (K = 3, idle T-bills); minutes from t on x 1.5 and the hours rebuilt
    from them. Unchanged before every cut; a planted leak in the overlay account (each grid pseudo-position's 00:00
    mark read one day ahead) is caught."""
    def run(M, sym, w0, w1):
        H = bg._hours_for(M)
        D = bd.bars_from_hours(H, "1d", "sig")
        r0 = be.simulate_coin(sym, be.ROWS["R0"], start=w0, end=w1, hours=H, minutes=M, mmr=0.005, detail=False)
        g = bg.grid_ga(sym, r0["trades"], daily_bars=D, start=w0, end=w1, minutes=M, hours=H, mmr=0.005, tick=0.001)
        be.clear_cache()
        return bg.merge_ga(r0, g), g

    def acct(mg, w0, w1, leak=False):
        if leak:
            dm = mg["daily_mtm"].copy()
            gp = dm.pos >= 1_000_000
            dm.loc[gp, "time"] = dm.loc[gp, "time"] - pd.Timedelta("1D")
            mg = dict(mg, daily_mtm=dm)
        e = _empty_res(mg)
        return be.assemble({"SY0": mg, "B": e, "C": e}, be.ROWS["R0"], w0, w1, idle_tbill=True, k_slots=3)

    warm, days = 100, 240
    start = pd.Timestamp("2010-01-04", tz="UTC")
    M = bg._gbm_minutes((warm + days) * 1440, 0.03 / np.sqrt(1440), 503, start)
    w0 = start + pd.Timedelta(days=warm)
    w1 = (start + pd.Timedelta(days=warm + days - 1)).strftime("%Y-%m-%d")
    mg, g = run(M, "SY0", w0, w1)
    n_dep = int((mg["trades"].pos >= 1_000_000).sum())
    assert n_dep >= 3 and len(mg["trades"]) > n_dep
    A, AL = acct(mg, w0, w1), acct(mg, w0, w1, leak=True)
    rng = np.random.default_rng(0)
    deps = g["deployments"]
    deps = deps[(deps.end - deps.start) > pd.Timedelta("2D")]
    n_ok = caught = n_cmp = 0
    for j in rng.choice(len(deps), min(6, len(deps)), replace=False):      # cuts inside a deployment
        s_, e_ = deps.start.iat[int(j)], deps.end.iat[int(j)]
        t = s_ + pd.Timedelta(minutes=int(rng.integers(1440, max(1441, int((e_ - s_).total_seconds() // 60)))))
        if t.minute == 0 or t >= e_:
            continue
        Mp = M.copy()
        aft = Mp.index >= t
        for c in PRICE:
            Mp.loc[aft, c] = np.round(Mp.loc[aft, c] * 1.5, 3)
        mp, gp_ = run(Mp, "SY0", w0, w1)
        for ta, tb in ((_acct_tables(A, t), _acct_tables(acct(mp, w0, w1), t)), (_ga_tables(g, t), _ga_tables(gp_, t))):
            for p in ta:
                ok, why = compare_frames(ta[p], tb[p], rtol=ACCT_RTOL if p in ("sizing", "equity") else 0.0)
                assert ok, (str(t), p, why)
                n_cmp += len(ta[p])
        n_ok += 1
        tl, tm = _acct_tables(AL, t), _acct_tables(acct(mp, w0, w1, leak=True), t)
        caught += any(not compare_frames(tl[p], tm[p], rtol=ACCT_RTOL)[0] for p in tl)
    assert n_ok >= 3 and caught >= 1, (n_ok, caught)
    say(f"  H10 overlay account (R0 + G-A via merge_ga, synthetic 1-minute GBM, {n_dep} deployments): {n_cmp:,} "
        f"account and G-A decisions before {n_ok} cuts unchanged; a grid mark read one day ahead caught at {caught} of "
        f"{n_ok} cuts")


def _st_summary(say):
    ok = {n: {"passed": True, "summary": {}} for n in CONTROLS}
    ok["inference_known_answer"].update(level95=0.95, level_noedge=bst.LEVEL_NOEDGE)
    assert _summary(ok, False, False, 1.0)["all_passed"]
    bad = {k: dict(v) for k, v in ok.items()}
    bad["fill_audit"] = {"passed": False, "summary": {}}
    assert not _summary(bad, False, False, 1.0)["all_passed"]
    miss = {k: v for k, v in ok.items() if k != "lookahead"}
    assert not _summary(miss, False, True, 1.0)["all_passed"]
    nan = {k: dict(v) for k, v in ok.items()}
    nan["inference_known_answer"] = dict(ok["inference_known_answer"], level95=float("nan"))
    assert not _summary(nan, False, False, 1.0)["all_passed"]
    err = {k: dict(v) for k, v in ok.items()}
    err["liquidation"] = {"passed": False, "error": "Traceback ...\nValueError: x"}
    s = _summary(err, False, False, 1.0)
    assert not s["all_passed"] and s["liquidation"]["error"] == "ValueError: x"
    assert _summary(ok, True, False, 1.0)["valid_gate"] is False
    say("  summary: all_passed only when every control passed and the levels are finite; a failed, missing or crashed "
        "control (or a NaN level) makes it false; a quick run is never a valid gate")


def _st_inference(say):
    r = inference_known_answer(quick=True, workers=4, n_paths=24, n_ref=12, B=299)
    for k in ("reject_rate", "reject_ci95", "miss_rate_95", "level95", "level_noedge", "widened",
              "diagnostic_true_mean_independent"):
        assert k in r, k
    rate = r["miss_rate_by_level"]
    ok_lv = [lv for lv in bst.LEVEL_GRID if rate[lv] <= 0.05]
    want = 0.95 if rate[0.95] <= 0.05 else (min(ok_lv) if ok_lv else float("nan"))
    assert r["n_paths"] == 24 and (r["level95"] == want or (np.isnan(want) and np.isnan(r["level95"])))
    assert r["widened"] == (rate[0.95] > 0.05)
    if r["widened"] and ok_lv:
        assert abs(r["level_noedge"] - (1 - (0.05 / 12) * (1 - want) / 0.05)) < 1e-12
    else:
        assert r["level95"] != 0.95 or r["level_noedge"] == bst.LEVEL_NOEDGE
    assert r["mean_trades_per_path"] > 40 and r["fill_audit_violations_reference_paths"] == 0
    p = _ic_sim(123)
    assert set(p.sym) == {"IC0", "IC1", "IC2"} and p.ret_adj.notna().all() and (p.audit == 0).all()
    assert (pd.DatetimeIndex(p.entry1_time) >= pd.Timestamp(FULL[0], tz="UTC")).all()
    H = ic_hours(5)
    rr = {s: np.log(h.close).diff().dropna() for s, h in H.items()}
    vol = {s: float(np.sqrt(((h.close / h.close.shift(1) - 1) ** 2).mean() * 8760)) for s, h in H.items()}
    cor = float(np.corrcoef(rr["IC0"], rr["IC1"])[0, 1])
    assert all(abs(vol[f"IC{i}"] / IC_VOLS[i] - 1) < 0.08 for i in range(3)) and abs(cor - IC_RHO) < 0.05
    assert all((h.high >= np.maximum(h.open, h.close)).all() and (h.low <= np.minimum(h.open, h.close)).all()
               for h in H.values())
    say(f"  inference machinery (24 paths, B 299): {r['mean_trades_per_path']:.0f} trades per path, rejection "
        f"{r['reject_rate']:.3f}, miss {r['miss_rate_95']:.3f}, level95 {r['level95']}; synthetic paths: vols "
        f"{', '.join(f'{vol[k]:.2f}' for k in sorted(vol))} (targets {IC_VOLS}), correlation {cor:.2f}, valid bars")


def _st_real(say):
    """Mechanics only on the real files (skipped when the data are absent): one look-ahead cut on BTC and LINK through
    a perturbed copy of data/bbreplica (counts and equal / not-equal flags only)."""
    if not (bd.DATA / "h1_um" / "BTCUSDT.parquet").exists():
        say("  real-data look-ahead mechanics: SKIPPED (no data/bbreplica)")
        return
    t = pd.Timestamp("2025-08-16 14:37", tz="UTC")                   # a Saturday, 10:37 New York
    rows = ("R0", "S8", "H4_touch")
    orig = {(s, r): _run_engine(s, r) for s in ("BTC", "LINK") for r in rows}
    with tempfile.TemporaryDirectory(prefix="bbctl_real_") as tmpd:
        info = perturb_data_dir(Path(bd.DATA), Path(tmpd), t, _stems(["BTC", "LINK"] + list(bd.COINS)))
        n = 0
        with _DataDir(Path(tmpd)):
            for (s, r), a in orig.items():
                b = _run_engine(s, r)
                ta, tb = _engine_tables(a, _cfg(r), t), _engine_tables(b, _cfg(r), t)
                for p in ta:
                    ok, why = compare_frames(ta[p], tb[p], "pos")
                    assert ok, (s, r, p, why)
                    n += len(ta[p])
                k_, bad = pending_decisions(a, b, _cfg(r), t)
                assert not bad, (s, r, bad)
                n += sum(k_.values())
                assert not b["fills_audit"]
            R = bd.volume_ranks("40")
        R0 = bd.volume_ranks("40")
        assert compare_frames(R[R.index < t].reset_index(), R0[R0.index < t].reset_index())[0]
    say(f"  real-data look-ahead mechanics (cut {t}, BTC with minutes and LINK without, R0 / S8 / H4 touch, ranks of "
        f"the 40): {info['files']} files perturbed in {info['seconds']}s; {n:,} decisions before the cut unchanged")


def _st_orchestrators(say):
    """The control functions end to end at quick sizes (mechanics: deterministic properties are asserted; the pass
    flags of the size-dependent rules are not, since the quick sizes are below the pre-registered ones)."""
    e = engine_known_answer(quick=True, workers=4)
    for k, d in e["martingale"].items():
        assert d["max_abs_fee_diff"] <= 1e-12 and d["max_abs_identity_diff"] <= 1e-12, k
        assert d["fill_audit_violations"] == 0 and d["bad_closing_notional"] == 0 and d["trades"] > 1000, k
    assert e["grid_ga"]["fill_audit_violations"] == 0 and e["trend"]["S1_base"]["fill_audit_violations"] == 0
    assert e["trend"]["passed"]                                        # t ~ 5 even at the reduced size
    say(f"  engine_known_answer (quick): {e['martingale']['S1_zero']['trades']:,} / "
        f"{e['martingale']['R0_zero']['trades']:,} martingale trades, fees recomputed exactly, audits empty")
    if not (bd.DATA / "h1_um" / "BTCUSDT.parquet").exists():
        say("  lookahead_check / fill_audit (quick): SKIPPED (no data/bbreplica)")
        return
    with tempfile.TemporaryDirectory(prefix="bbctl_la_") as tmpd:
        la = lookahead_check(quick=True, workers=4, tmp=tmpd)
    assert la["crypto_mismatches"] == 0 and la["stock_mismatches"] == 0 and la["fill_audit_violations_perturbed"] == 0
    assert la["crypto_cuts_where_a_later_decision_changed"] > 0 and la["passed"], la["summary"]
    acc = la["accounts_compared"]                     # findings 2 and 4: the new comparisons ran at every cut
    n_c = la["summary"]["crypto_cuts"]
    assert acc.get("R0 + G-A (H10 overlay)") == n_c and acc.get("S12_all_top3", 0) >= 1, acc
    assert la["crypto_decisions_compared"].get("exit_decisions", 0) > 0, la["crypto_decisions_compared"]
    fa = fill_audit(quick=True, workers=4)
    assert fa["passed"] and fa["summary"]["violations"] == 0 and fa["summary"]["bench_runs"] >= 12, fa["summary"]
    say(f"  lookahead_check (quick, real data): {la['summary']['crypto_cuts']} crypto + {la['summary']['stock_cuts']} "
        f"stock cuts, {la['summary']['decisions_compared']:,} decisions compared "
        f"({la['crypto_decisions_compared']['exit_decisions']:,} exit decisions; accounts {sorted(acc)}), 0 "
        f"mismatches; fill_audit (quick): {fa['summary']['runs']} runs ({fa['summary']['bench_runs']} of the indicator "
        f"benchmark), 0 violations")


def selftest() -> None:
    t0 = time.time()
    say = _say
    say("bb_controls selftest")
    _st_compare(say)
    _st_size_rule(say)
    _st_cuts(say)
    _st_summary(say)
    _st_fees(say)
    r = liquidation_check()
    assert r["passed"], [c for c in r["cases"] + r["stop_controls"] if not c["passed"]]
    _st_perturb(say)
    _st_stock_lookahead(say)
    _st_pending(say)
    _st_bench_audit(say)
    _st_overlay_account(say)
    _st_inference(say)
    _st_real(say)
    _st_orchestrators(say)
    say(f"bb_controls selftest passed in {time.time() - t0:.0f}s")


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m analysis_2026.bb_controls", description=__doc__.split("\n")[1])
    ap.add_argument("cmd", choices=["run", "selftest"])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default=None, help=f"comma-separated subset of {','.join(CONTROLS)}")
    ap.add_argument("--tmp", default=None, help="directory for the look-ahead's temporary data copies")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest()
        return
    s = run(quick=a.quick, out=a.out, workers=a.workers, only=a.only.split(",") if a.only else None, tmp=a.tmp)
    sys.exit(0 if s["all_passed"] or a.quick or a.only else 1)


if __name__ == "__main__":
    _main()
