"""
F's frequency-matched counts, the H11 consistency check, the H11b labelled fit, H12 (shorts) and the luck and
tautology benchmark of the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md: the Sensitivity
grid's "F 'frequency-matched'", "H11 consistency check (descriptive; no tuning)", "H11b closest match to the post
(labelled fit; exploratory)", "H12 shorts (exploratory)", "Luck and tautology benchmark (descriptive)", the Windows'
edge rules, S3's cross margin, "Multiplicity" (descriptive p-values are exploratory and Benjamini-Hochberg adjusted
within their table) and "Reporting rules" (results including ZEC always beside results without it); the Addendum
and Addendum 2 bind). Contract: the scratchpad's bb_engine_spec.md, "Integration layer".
Every simulation, account, statistic and grid comes from bb_engine, bb_stats, bb_grid and bb_data; this module
chooses the inputs, counts, tabulates and compares. Nothing here is a Holm-family test.

    python3 -m analysis_2026.bb_fit run --out DIR [--which fcount,luck,h12,h11b,h11] [--jobs 4] [--force]
    python3 -m analysis_2026.bb_fit selftest       # synthetic known answers + a tiny end-to-end run on injected data
    python3 -m analysis_2026.bb_replica fit         # the runner (controls gate; primary/tests.json gate)

DIR is the results root (analysis_2026/results_bb). Parts run in the order fcount -> luck -> h12 -> h11b -> h11
(H11 reads the luck benchmark's distribution and H11b's decoys). Ordering: F's counts come before any return ("the
engine writes the nine counts to results_bb/ before any return is read"): run() runs fcount first whenever
DIR/fcount/F.json is missing, and run_luck / run_h12 / run_h11b refuse without it. h11b refuses unless every primary
result is written ("Run only after every primary result has been written to results_bb/"): primary_written(), i.e.
bb_replica.primary_status (DIR/primary/tests.json holds all 12 bb_tests.TESTS and none errored), unless --force
(self-tests only). Nothing is printed but counts, shapes, timings and fill-audit status. Every engine and grid run
asserts an empty fill audit (RuntimeError otherwise).

Public API
  run(out_dir, which=None, jobs=4, force=False, conf=None, src=None, say=print) -> dict
  Conf(...)  sizes (luck versions, decoys, bootstrap draws, synthetic reference, H11 rows, H11b cell subset)
  Src(...)   injected data (hours, minutes, universes, windows) for the self-test; None = the data on disk
  h11b_cells() -> DataFrame      the 648 cells in their fixed order (cell index = row number)
  cell_cfg(cell) -> Cfg, cell_ukey(universe) -> universe key
  tranche_units(trades, tranches) -> DataFrame   one row per tranche ("bot"): net P&L per M of its position
  unit_stats(units), unit_intervals(units, ...), acct_stats(acct, units, ...)   H11 statistics
  consistency(st, iv, acct, n_tranches, hit_target) -> dict      H11's consistency rule
  z_scores(st, iv, acct, n_tranches, hit_target) -> dict, distance(z) -> float   H11b's D
  identified_set(D, k) -> (mask, D_min, threshold), reading_rule(...) -> dict   H11b's set and fixed reading
  candidate_table(sym, cfg, start, end, times, side, mask) -> DataFrame   valid random-entry decision times
  draw_entries(cands, quota, rng, max_tries) -> (DataFrame, shortfall)    the sequential flat-day sampler
  months_needed(sd_month, mult=4.3, months=16) -> dict           months of record for t >= 2
  primary_written(out_dir) -> (ok, why)                          H11b's gate (bb_replica.primary_status)
  selftest()

Outputs (under DIR)
  fcount/  counts.csv (the nine W16 tranche counts; is_F; beside them zec_in_universe and the counts without ZEC),
           F.json ({"F": {"bars", "row", "universe", ...}, "F_without_ZEC": ...}), written from the engine's tranche
           table only, before any return of the study is computed or read
  luck/    versions.csv (every random-entry version), summary.csv, distribution.csv (random-entry distribution of
           every H11 statistic, R0's value and percentile), months_needed.csv, meta.json
  h12/     rows.csv (R0 and S11 on W16 and Full), diff.csv (S11 - R0: per-signal and account, exploratory p, BH),
           meta.json
  h11b/    cells.csv (648 cells x {W16, W16b}: per-tranche statistics, z-scores, D, identified set, consistency,
           out-of-window results; beside them the values without ZEC: *_exZEC, in_set_exZEC), decoys.csv,
           set_extras.csv (identified-set cells at L = 5 and with G-A / G-B), spearman.csv (D vs out-of-window
           log growth: rho, exploratory p, BH within the table), summary.json (best cell, identified set, shares,
           agreement, the fixed reading, out-of-window vs the median cell, Spearman; exZEC), meta.json
  h11/     h11.csv (row x window x group x unit: every H11 statistic with intervals, targets, flags, status, the
           driftless synthetic value, the luck distribution; group "all", and "exZEC" beside each row-window whose
           universe holds ZEC), oow.csv (out-of-window results of every row, groups likewise), synthetic.csv,
           summary.json (consistent variant-windows vs the number expected by chance; exZEC), meta.json

Definitions (pre-registration text in quotes where it decides)
- Units. "A tranche is each first entry and each add, counted as one 'bot'". Per position: one row per engine
  position the account held (choice 22). Per tranche: tranche_units() splits a position's net P&L across its
  tranches (choice 3). Grid overlays:
  each G-A deployment is one position and one bot (its net P&L per sleeve); each G-B tranche grid is one bot (its net
  P&L per M of the position), each wrapped position one position (choices 4, 19).
- Statistics (as bb_desc's coding choice 3, the headline's definitions): hit rate = share of closed units (not open
  at the window end: "not in hit rate, win/loss or the holding-time shares") with net return > 0; average win /
  average loss = mean dollar P&L (bb_engine.assemble's M x return per M) of closed winners over |mean| of closed
  losers; > 7-day won share = closed units held more than 168 h that won; >= 3-day profit share = net dollar P&L of
  closed units held >= 72 h over the net P&L of all closed units (reported as is, flagged ge3_defined = total > 0;
  the winners-only share, bb_desc's gross version, beside it); multiple = account equity at the window's end
  (equity 1 at its start, idle cash at 0%: the R0 Costs row's primary); turnover = traded notional in dollars
  (every fill: entries, adds, TP, exits, stops, liquidations, forced closes, grid fills) / mean daily equity.
- Intervals: hit rate, Wilson 95% (binomial, as the consistency rule) and month-cluster percentile bootstrap
  (bb_stats.cluster_boot_ci, clusters = the unit's entry month, 9,999 draws); win/loss and the holding shares,
  month-cluster bootstrap; multiple, month-block stationary bootstrap of daily account returns
  (bb_stats.block_boot_ci, mean block 365/12 days, 10,000 draws).
- Consistency ("A row is consistent with the post only if all of these hold"): |hit - 48.7%| <= 2 SE and
  |share > 7 d won - 75%| <= 2 SE with SE = sqrt(p0 (1 - p0) / n) at the post's p0 and the row's own count (closed
  units; > 7-day closed units); ">80%": profit share >= 80% - 2 SE (n = closed units; undefined when the closed
  units' total P&L is <= 0, which fails); 1.4 inside the row's 95% win/loss interval; 4.3 inside the row's 95%
  multiple interval; per-tranche count in [731, 2,924]. Status "consistent"; "different trading frequency" when
  the count fails; else "inconsistent" (choices 4-6).
- D ("the sum of squared z-scores of the H11 statistics, in per-tranche units. Count and multiple enter as log
  ratios scaled by their H11 bands"): k = 6 statistics, every z scaled so that the edge of its H11 band sits at
  |z| = 2 (1.96 for the two bootstrap intervals): z_count = 2 ln(n / 1,462) / ln 2; z_hit = (hit - p0) / SE;
  z_wl = 1.96 (wl - 1.4) / h_wl and z_mult = 1.96 (ln m - ln 4.3) / h_m, where h is the distance from the estimate
  to the interval end on the post's side (in logs for the multiple); z_gt7 = (s - 0.75) / SE; z_ge3 = min(0, s -
  0.80) / SE. A row is therefore consistent exactly when every |z| is inside its band. An undefined statistic
  (no closed unit, no > 7-day unit, no loss, total P&L <= 0, no interval) makes D infinite (choice 7). Identified
  set: D <= D_min + chi2_0.95(6) = D_min + 12.59, per window over the 648 cells.

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. Rows of H11: R0, every sensitivity-grid row of bb_engine.ROWS (S1 and S1W at L = 3 as the grid rows, Addendum
   2; S2 .. S20 with every S6 / S7 / S9 / S10 variant; S12 top 3 / top 6 / top 10 and the Addendum's TradFi top 10;
   S17 labelled hindsight), F, R0 + G-A and R0 + G-B. Not included: the route rows, the pre-perpetual rows, R0's
   stress and at-S rows (reported beside R0 by bb_desc, not sensitivity rows), S1_L1 / S1W_L1 (the headline's L = 1
   versions) and H1's S12 gate universe. Each row's account has K slots (BTC/ETH/SOL 3, S12 top k: k, S17 4).
2. Windows: each window and each out-of-window span is its own run starting flat with equity 1 (Windows); W16 rows'
   out-of-window span is 2020-01-01..2025-06-16, W16b rows' are 2020-01-01..2024-06-29 and 2025-11-01..2026-10-16,
   each its own account, pooled as log growth per year over both spans. Grid rows exist only where 1-minute data
   exist: their windows start at max(window start, 2024-07-01) for the grid (R0's positions from the window start)
   and their out-of-window spans are clipped to 2024-07-01..2026-10-16 (W16b's first span is not available).
3. Per-tranche P&L: in one-way mode a position is fungible and no add can fill after its TP (the R0 table), so every
   close (TP half, exit, stop, liquidation, forced close, window-end mark) closes the same fraction of every
   tranche. Tranche i (quantity q_i = notional / fill price) gets side x q_i x (average close price - its fill
   price), minus its own entry cost, its quantity share of the closing costs, and a share of the position's
   funding proportional to q_i x its hours held; the residual to the engine's position return (zero to rounding
   except for liquidations, where the margin rather than the price closes the position) is spread by quantity
   share, so the tranches of a position sum exactly to its net return. A tranche is held from its fill to the
   position's final close. Tranche dollars = its return per M x the position's M.
4. Consistency is decided in per-tranche units (the likeliest reading of "1,462 bots", and H11b's unit); the
   per-position flags are reported beside it with the same rule (the count condition is always the per-tranche
   count). Grid overlay rows use the post's 51.7% ("51.7% with the grid") as their hit-rate target, with the flag
   against 48.7% beside it, and report the change from R0 without the grid against +3.0 points.
5. "within 2 binomial SEs at the row's own count": SE at the post's value p0 (the null that the row's true value
   equals the post's) and n = the row's closed units for the hit rate and the profit share, the row's closed
   > 7-day units for the > 7-day share. ">80%" is one-sided: any share above 80% is consistent.
6. "A row that fails on count alone is reported as 'different trading frequency' ... whatever its hit rate": every
   row failing the count band is labelled so; fails_only_on_count says whether it fails on nothing else.
7. D: as stated above. The count band 0.5x-2x is read as the count's 2-SE band and the two 95% bootstrap intervals
   as 1.96-SE bands on the post's side, so that D's components are on the consistency rule's scale; the identified
   set uses chi2 with k = 6 as pre-registered. Turnover and the per-position count are reported, not in D (turnover
   "reported only"; D is "in per-tranche units"). Grid versions of identified-set cells use 51.7% and count their
   deployments / tranche grids as bots.
8. H11b cells: bars x BB(n, k) (signal band only, Addendum 2) x near-high {off, r0} x adds {price, roe, none} x
   exits {TP half, no TP} x universe {BTC/ETH/SOL, S12 top 6 (pool 40), S12 top 10 (all perpetuals, crypto only)}
   x direction {long, longshort}, index = itertools.product in that order. Daily cells are R0 with those changes,
   4-hour cells S8, 1-hour cells S16 (bar-size convention). The 50 decoy cells: numpy.random.default_rng(20261018)
   .choice(648, 50, replace=False) on that index (the same cells for both windows).
9. Decoys and the luck benchmark ("random flat days inside the cell's entry rules, with the same count per coin";
   "R0's number of first entries per coin, drawn from days the coin was flat, inside R0's entry windows"): decision
   times on the cell's bar grid (daily cells and the luck benchmark: each 00:00 UTC day; 4-hour cells: each 4-hour
   close; 1-hour cells: each hour, since a 1-hour cell can hold several positions a day), restricted to the window
   and, for S12 universes, to member months. The engine's entry_mode "given" applies the row's windows, rule 12
   block, ban, skip-if-at-or-below-S, adds, stops, exits, sizing, costs and funding from each decision time.
   candidate_table() finds each decision time's own position by "peeling" (repeated engine runs on the times still
   undecided; given-entry positions do not interact except that a decision while a position is open or pending is
   dropped), and drops decision times whose entry the engine skips (no position). draw_entries() then walks a
   seeded random permutation of the valid times and accepts a time when the coin is flat there and its position
   does not overlap an accepted one (intervals [decision hour, final close hour]), until the coin's count (per side
   for longshort cells: the cell's longs and shorts) is reached; up to 20 permutations, keeping the fullest draw;
   a shortfall is recorded, never filled with overlapping entries. Every version is then simulated by the engine
   with its accepted times, and the run is checked to reproduce exactly the drawn positions (count and entry /
   exit times). Seeds: default_rng([20261018, L x 10, window, coin]) for the luck benchmark,
   default_rng([20261018, cell, window, coin]) for decoys.
10. Decoys in the identified set: a decoy's D is compared with its window's threshold (D_min of the cells + 12.59).
   The share of decoys in the set pools the 50 random cells' twins and the set cells' twins of that window (each
   group reported; a cell that is both has its 20 twins drawn once and counted once). The reading ("identifies only
   if fewer than 5% of cells and fewer than 5% of decoys fall in the identified set, and those cells share bars and
   universe") is applied per window. Agreement on grid: the best of {no grid, G-A, G-B} by D for each set cell (G-A
   / G-B on the cell's coins with 1-minute data).
11. Out-of-window net return of a cell (Spearman with D): log growth per year of the cell's K-slot account over its
   out-of-window span(s); the mean net trade return per M is reported beside it. Spearman over every cell of the
   window (D = inf ranks last) and over the cells with finite D, with ZEC and, in a window where some cell's account
   held ZEC in or out of the window, without it (D_exZEC vs the out-of-window log growth without ZEC). H11b is
   descriptive, so these two-sided p-values are labelled exploratory and Benjamini-Hochberg adjusted within their
   table (Multiplicity), h11b/spearman.csv (both windows x {all cells, finite D} x {with, without ZEC}); summary.json
   repeats them as {rho, p_exploratory, p_bh, n}.
12. "the same variant's value on the driftless synthetic series of the controls": the controls' engine series
   (bb_engine._gbm_hours, martingale, 1% per hour, seeds 20261018 + i, 160 coins x 50 years as bb_controls' engine
   known answer) for every row (S12 / S17 / S19 rows take R0's rules, since universe and assembly do not exist there;
   on these decaying martingale paths an ATH-only rule fires rarely, and a statistic without units is NaN), and the
   controls' grid series (bb_grid's martingale G-A control: 1-minute GBM at 2% a day, seeds 20261018 + 7919 i, 100
   warm-up days + 730 days, 240 coins) for R0 + G-A and R0 + G-B. Synthetic P&L is in units of the slot's sleeve at
   constant size (position return x L_used; grid net per sleeve). The luck benchmark's distribution shown beside
   each row is R0's at L = 3 on the same window.
13. Expected consistent variant-windows by chance = (share of all H11b decoys, both windows, consistent under the
   same per-tranche rule) x (number of H11 variant-windows); the per-window version is beside it.
14. Months of record (SCALPING_PREREG's formula at monthly frequency): t = mu sqrt(n) / sigma >= 2 needs
   n = (2 sigma / mu)^2 months, mu = 4.3^(1/16) - 1 = 9.55% a month (the post's implied mean monthly return) and
   sigma = the SD (ddof 1) of R0's complete calendar months' simple account returns; reported for each luck window
   and L and for R0 on the full sample at L = 3 and 5; the log-return version (mu = ln 4.3 / 16) beside it.
15. H12: R0 vs S11 on BTC/ETH/SOL (three slots, L = 3) on W16 and the full sample. Per-signal paired difference
   (bb_stats.paired_signal_diff, signal_day key, a signal one row skips counts 0) of net and drift-adjusted return
   per M, month-clustered (bb_stats.cluster_t); account log growth difference and Sharpe difference (idle cash at
   the T-bill, excess returns) by bb_stats.block_boot with 1-month blocks. p-values are exploratory, BH-adjusted
   within diff.csv.
16. F's counts read only the engine's tranche table (kinds entry / add) of each W16 run; the engine's per-position
   output (bb_engine has no count-only mode, so simulate_coin computes it internally) is discarded unread, no account
   is assembled and no statistic is computed before counts.csv and F.json are on disk. Ties in |count - 1,462| go to
   the first cell in the order R0, S8, S16 x BTC/ETH/SOL, S12 top 6, S12 top 10. A later run of fcount recounts and
   keeps the first files (their time stamp is the ordering evidence) when the counts agree, and stops when they
   differ. F is chosen on the pre-registered counts (with ZEC); the counts without ZEC are beside them (choice 21).
17. Parallelism: joblib is not installed, so fork process pools (concurrent.futures) are used; engine work is done
   coin-major (each worker prepares a coin once and runs every configuration and span of it), with intermediate
   results pickled to a temporary work directory that is deleted afterwards.
18. Luck: "the share that reaches >= 4.3x" (and 2x) is read on the final multiple at the window's end (the post's
   4.3x is an end result); the share whose peak equity reaches it is beside it. "With a liquidation": any isolated
   liquidation in the version (or an S3 cross-margin account liquidation, which the luck rows cannot have).
19. Mean trade returns per M (mean_ret, the out-of-window mean_ret and the decoy / cell trade means) leave out G-A
   deployments, whose returns are per sleeve; G-B's wrapped positions stay in (their grids' net per M of the
   position). Grid P&L has no drift-adjusted return (NaN). Account statistics include everything.
20. The driftless reference's net profit share divides by a total net P&L close to zero (no skill, costs), so it is
   unstable; the winners-only share beside it is the readable no-skill value. Both are reported, not compared.
21. ZEC ("Results including ZEC are always shown next to results without it"; bb_desc's choice 4 and bb_tests'
   choice 17 do the same). The twin without ZEC is the same account with ZEC's positions removed and K unchanged
   (ZEC's slot holds cash), with the same statistics, intervals, consistency rule and D. Where it exists: H11 rows
   whose universe holds ZEC in the window (S12 top 6 / top 10 / TradFi top 10 in W16, S17 always, F when it is such
   an S12 cell) get a row with group "exZEC" beside the row with ZEC (group "all"; zec_in_universe and the ZEC unit
   counts on both), and their out-of-window rows likewise; every H11b cell, decoy and set extra carries its values
   without ZEC (*_exZEC; equal to its own values when ZEC is not in its universe or its account held no ZEC unit),
   in_set_exZEC = D_exZEC within the window's pre-registered threshold (D_min of the cells with ZEC + 12.59), and
   the out-of-window results without ZEC; F's counts without ZEC sit beside the nine counts. The pre-registered rows,
   F's choice, the identified set, the decoy shares, the chance count and the reading are those with ZEC. The luck
   benchmark and H12 (BTC/ETH/SOL) never hold ZEC.
22. Units are what the account held. A position the account never held (M = 0 in bb_engine.assemble: entered after
   an S3 cross-margin liquidation, or after the equity reached 0) is not a unit, so it is in no count, hit rate,
   win / loss, holding share, mean return or volume. S3 cross margin: the positions open at the account's
   liquidation are closed at the breach hour (open_at_end False, liquidated, held to the breach) with the account's
   dollar P&L; assemble books each at M x (pnl_lo - mm), whose sum can exceed what the account lost (it keeps
   max(0, equity - maintenance margin)), so they are scaled to make all held positions' P&L sum to the account's
   equity change (pro rata to assemble's values; by M if they are not both losses). Their tranches filled after the
   breach are dropped and the others share the position's P&L by quantity, held from their fill to the breach;
   their volume is the account's fills to the breach plus the liquidation's close at the position's notional in the
   breach hour, and their drift adjustment covers the hours to the breach. Without a cross liquidation the units
   are the engine's positions and tranches at M, as before (their P&L sums to the account's change exactly).
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import pickle
import shutil
import sys
import tempfile
import time
import warnings
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import bb_data as bd  # noqa: E402
from analysis_2026 import bb_engine as be  # noqa: E402
from analysis_2026 import bb_grid as bg  # noqa: E402
from analysis_2026 import bb_stats as bs  # noqa: E402

RES = ROOT / "analysis_2026" / "results_bb"
SEED = 20261018
H_NS = 3_600_000_000_000
PARTS = ("fcount", "luck", "h12", "h11b", "h11")            # run order: H11 reads luck/ and h11b/

# the post's statistics (rules_and_evidence.md section 2.3; pre-registration "The question" and H11)
POST = {"positions": 490, "tranches": 1462, "hit": 0.487, "hit_grid": 0.517, "uplift": 0.030, "winloss": 1.4,
        "multiple": 4.3, "gt7_won": 0.75, "ge3_profit": 0.80, "turnover_lo": 950.0, "turnover_hi": 19000.0,
        "months": 16}
COUNT_LO, COUNT_HI = 0.5 * POST["tranches"], 2.0 * POST["tranches"]
Z_COUNT_EDGE = 2.0                                           # the count band's edge on D's scale (choice 7)
Z_IV = float(sps.norm.ppf(0.975))                            # 1.96: a 95% interval's edge
D_STATS = ("count", "hit", "winloss", "multiple", "gt7_won", "ge3_profit")
K_D = len(D_STATS)
CHI2_95 = float(sps.chi2.ppf(0.95, K_D))                     # 12.59

WINDOWS = {"W16": ("2025-06-17", "2026-10-16"), "W16b": ("2024-06-30", "2025-10-31")}
OOW = {"W16": (("2020-01-01", "2025-06-16"),),
       "W16b": (("2020-01-01", "2024-06-29"), ("2025-11-01", "2026-10-16"))}
FULL = ("2020-01-01", "2026-10-16")
GRID_FROM = bg.GRID_START                                    # 1-minute data: 2024-07-01

H11_ROWS = ("R0", "S1", "S1W", "S2", "S3_L5", "S3_cross", "S4", "S5", "S6_bb20_2.5", "S6_bb50_2", "S6_bb10_1.9",
            "S6_bb50_2.1", "S6_bb10_1.5", "S6_bb50_2.5", "S7_off", "S7_20d2", "S7_365d10", "S7_ath10", "S8",
            "S9_lower_band", "S9_sma_2p5atr", "S10_tp_all", "S10_no_tp", "S11", "S12_top3", "S12_top6", "S12_top10",
            "S12_top10_tradfi", "S13", "S14", "S15", "S16", "S17", "S18", "S19", "S20")
GRID_ROWS = {"R0+G-A": "GA", "R0+G-B": "GB"}
F_BARS = {"1d": "R0", "4h": "S8", "1h": "S16"}
F_UNIVERSES = ("BTC/ETH/SOL", "S12 top 6", "S12 top 10")
CELL_BARS = ("1d", "4h", "1h")
CELL_BB = ((20, 2.0), (20, 2.5), (10, 1.9))
CELL_NH = ("off", "r0")
CELL_ADDS = ("price", "roe", "none")
CELL_EXITS = ("half", "none")
CELL_DIR = ("long", "longshort")
N_CELLS = len(CELL_BARS) * len(CELL_BB) * len(CELL_NH) * len(CELL_ADDS) * len(CELL_EXITS) * len(F_UNIVERSES) * \
    len(CELL_DIR)                                            # 648
OPEN_KINDS = ("entry", "add")
CLOSE_KINDS = ("tp", "exit", "stop", "liq", "delist", "end")
T_COLS = ["pos", "sym", "side", "signal_day", "entry1_time", "exit_time", "ret", "L_used", "liquidated", "hold_h",
          "open_at_end", "n_tranches", "exit_reason", "funding"]
U_COLS = ["pos", "k", "time", "ret", "hold_h", "open_at_end", "grid"]
DM_COLS = ["pos", "time", "mtm", "margin", "notional"]
NOT_THEIRS = ("descriptive; a match is never evidence that a variant works, and no row is their strategy, their "
              "exact rules or the replication")
ZEC = "ZEC"                                                  # Reporting rules: with ZEC beside without it (choice 21)
EXZEC = "exZEC"
EXZEC_KEYS = ("n_positions", "n_tranches", "hit", "winloss", "winloss_lo", "winloss_hi", "multiple", "multiple_lo",
              "multiple_hi", "gt7_won", "ge3_profit", "turnover", "D", "consistent", "status", "mean_ret_all")
OOW_EXZEC_KEYS = ("oow_log_growth_yr", "oow_mean_ret", "oow_mean_ret_adj", "oow_n_positions")
ZEC_NOTE = ("results without ZEC beside the results with it (Reporting rules; choice 21): the same account without "
            "ZEC's positions, K unchanged (ZEC's slot holds cash); the pre-registered rows, the F choice, the "
            "identified set and the reading are the ones with ZEC")
SPEARMAN_LABEL = ("exploratory (H11b is descriptive): two-sided scipy Spearman p-values, Benjamini-Hochberg adjusted "
                  "within the H11b Spearman table (h11b/spearman.csv: both windows x {all cells, finite D} x {with "
                  "ZEC, without ZEC where ZEC traded})")


# ============================================================================ configuration and injection
@dataclass
class Conf:
    """Sizes. Defaults are the pre-registration's (quick=True marks a reduced mechanics run in every meta.json)."""
    n_luck: int = 1000
    luck_L: tuple = (3.0, 5.0)
    n_decoy_cells: int = 50
    n_twins: int = 20
    B_trade: int = bs.B_TRADE
    B_port: int = bs.B_PORT
    h11_rows: tuple = H11_ROWS
    h11b_cells: tuple | None = None          # subset of cell indices (None = all 648)
    syn_coins: int = 160                     # the controls' engine series: 160 coins x 50 years at 1% an hour
    syn_years: int = 50
    syn_sigma: float = 0.01
    syn_grid_coins: int = 240                # the controls' grid series: 240 coins x 730 days at 2% a day
    syn_grid_days: int = 730
    syn_grid_warm: int = 100
    syn_grid_sigma_day: float = 0.02
    max_tries: int = 20
    tmp: str | None = None
    keep_work: bool = False
    quick: bool = False


@dataclass
class Src:
    """Injected data (self-test). hours / minutes: {sym: frame} (bb_data.coin_hours- / minutes-shaped); universes:
    {universe key: (coins, K, {sym: month-start bool Series or None})} for the S12 keys and S17; windows, oow, full,
    grid_from override the pre-registered dates; tick / mmr per synthetic symbol."""
    hours: dict | None = None
    minutes: dict | None = None
    universes: dict | None = None
    primary: tuple = tuple(bd.PRIMARY)
    windows: dict | None = None
    oow: dict | None = None
    full: tuple | None = None
    grid_from: str | None = None
    tick: dict | None = None
    mmr: dict | None = None

    @property
    def injected(self) -> bool:
        return self.hours is not None


_CTX: dict = {"src": Src(), "conf": Conf(), "work": None, "ranks": {}, "masks": {}, "univ": {}, "cret": {}}


def _src() -> Src:
    return _CTX["src"]


def _conf() -> Conf:
    return _CTX["conf"]


def _win(w: str) -> tuple:
    s = _src()
    return tuple((s.windows or {}).get(w) or WINDOWS[w])


def _oow(w: str) -> tuple:
    s = _src()
    return tuple((s.oow or {}).get(w) or OOW[w])


def _full() -> tuple:
    return tuple(_src().full or FULL)


def _grid_from() -> str:
    return _src().grid_from or GRID_FROM


def _hours(sym):
    s = _src()
    return s.hours[sym] if s.injected else None


def _minutes(sym):
    s = _src()
    return (s.minutes or {}).get(sym) if s.injected else None


def _has_m1(sym) -> bool:
    s = _src()
    return sym in (s.minutes or {}) if s.injected else sym in bd.M1_COINS


def _mmr(sym):
    s = _src()
    return (s.mmr or {}).get(sym) if s.mmr else None


def _tick(sym):
    s = _src()
    return (s.tick or {}).get(sym) if s.tick else None


def _say_default(s: str) -> None:
    print(s, flush=True)


# ============================================================================ small helpers
def _ns(x) -> np.ndarray:
    ix = pd.DatetimeIndex(x)
    if ix.tz is None:
        ix = ix.tz_localize("UTC")
    return ix.tz_convert("UTC").as_unit("ns").asi8


def _ts(v) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(np.asarray(v, np.int64), tz="UTC")


def _audit_ok(audit, what: str) -> None:
    if audit:
        raise RuntimeError(f"bb_fit: fill audit violation in {what}: {len(audit)} - {list(audit)[:3]}")


def _js(x):
    """JSON-safe conversion (numpy scalars, NaN / inf as strings, timestamps as ISO strings)."""
    if isinstance(x, dict):
        return {str(k): _js(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_js(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return v if math.isfinite(v) else str(v)
    if isinstance(x, (pd.Timestamp,)):
        return str(x)
    if isinstance(x, np.ndarray):
        return [_js(v) for v in x.tolist()]
    return x


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_js(obj), indent=1))


def _pmap(fn, jobs, workers: int = 4) -> list:
    """fn over jobs in a fork process pool (choice 17: joblib is not installed; with joblib present, its
    multiprocessing backend, which also forks, is used). Workers inherit the module context (_CTX). Results are
    returned in job order; an exception in a worker is raised here."""
    jobs = list(jobs)
    if not jobs:
        return []
    if workers <= 1 or len(jobs) == 1:
        return [fn(j) for j in jobs]
    try:
        import joblib                                         # noqa: F401
        return list(joblib.Parallel(n_jobs=workers, backend="multiprocessing")(joblib.delayed(fn)(j) for j in jobs))
    except ImportError:
        pass
    import concurrent.futures as cf
    import multiprocessing as mp
    out = [None] * len(jobs)
    with cf.ProcessPoolExecutor(max_workers=min(workers, len(jobs)), mp_context=mp.get_context("fork")) as ex:
        futs = {ex.submit(fn, j): i for i, j in enumerate(jobs)}
        for f in cf.as_completed(futs):
            out[futs[f]] = f.result()
    return out


def _wpath(group: str, sym: str) -> Path:
    return Path(_CTX["work"]) / group / f"{sym}.pkl"


def _put(group: str, sym: str, obj) -> None:
    p = _wpath(group, sym)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        pickle.dump(obj, f, protocol=5)


def _get(group: str, sym: str):
    with open(_wpath(group, sym), "rb") as f:
        return pickle.load(f)


def _gname(*parts) -> str:
    return "_".join(str(p).replace("+", "p").replace("/", "_").replace(" ", "") for p in parts)


# ============================================================================ universes
def _ranks(pool: str, tradfi: bool) -> pd.DataFrame:
    key = (pool, bool(tradfi))
    R = _CTX["ranks"].get(key)
    if R is None:
        R = bd.volume_ranks(pool, tradfi=tradfi) if pool == "all" else bd.volume_ranks(pool)
        _CTX["ranks"][key] = R
    return R


def _mask(sym: str, mkey):
    """Month-start membership Series of sym in universe mkey (bb_engine.s12_allowed's expression on cached ranks),
    or None (no membership rule)."""
    if mkey is None:
        return None
    s = _src()
    if s.universes and mkey in s.universes:
        return s.universes[mkey][2].get(sym)
    key = (sym, mkey)
    m = _CTX["masks"].get(key)
    if m is None:
        _, pool, k, tradfi = be.ROW_UNIVERSE[mkey]
        R = _ranks(pool, tradfi)
        m = (R.iloc[:, :k] == sym).any(axis=1).astype(bool)
        _CTX["masks"][key] = m
    return m


def _months(start, end) -> pd.DatetimeIndex:
    a, b = bd._utc(start), bd._utc_end(end)
    return pd.date_range(a.tz_convert("UTC").normalize().replace(day=1), b, freq="MS")


def _member_values(m: pd.Series, when: pd.DatetimeIndex) -> np.ndarray:
    """Step-function value of a month-start membership Series at the given times (False before its first row)."""
    tm = _ns(m.index)                                      # ns whatever the index's unit (pandas 3: often us)
    o = np.argsort(tm, kind="stable")
    t = tm[o]
    v = m.to_numpy(bool)[o]
    pos = np.searchsorted(t, _ns(when), side="right") - 1
    return np.where(pos >= 0, v[np.clip(pos, 0, max(len(v) - 1, 0))] if len(v) else False, False)


def universe(ukey, start, end) -> tuple:
    """(coins that can take a first entry in [start, end], K slots, {sym: canonical membership key}): None = no
    membership rule (BTC/ETH/SOL, S17, or an S12 coin that is a member in every month of the span, where the mask
    cannot bind); ukey = an S12 coin with partial membership. S12 coins never members in the span are left out."""
    key = (ukey, str(start), str(end))
    hit = _CTX["univ"].get(key)
    if hit is not None:
        return hit
    s = _src()
    if ukey is None:
        out = (list(s.primary), len(s.primary), {c: None for c in s.primary})
    elif s.universes and ukey in s.universes:
        coins, K, masks = s.universes[ukey]
        mm = {}
        for c in coins:
            m = masks.get(c)
            if m is None:
                mm[c] = None
                continue
            v = _member_values(m, _months(start, end))
            if v.all():
                mm[c] = None
            elif v.any():
                mm[c] = ukey
        out = (list(mm), int(K), mm)
    else:
        u = be.ROW_UNIVERSE[ukey]
        if isinstance(u, list):
            out = (list(u), len(u), {c: None for c in u})
        else:
            _, pool, k, tradfi = u
            R = _ranks(pool, tradfi)
            mons = _months(start, end)
            cand = sorted({x for x in R.iloc[:, :k].to_numpy().ravel() if isinstance(x, str)})
            mm = {}
            for c in cand:
                v = _member_values(_mask(c, ukey), mons)
                if v.all():
                    mm[c] = None
                elif v.any():
                    mm[c] = ukey
            out = (list(mm), int(k), mm)
    _CTX["univ"][key] = out
    return out


def _row_ukey(row: str):
    """Universe key of a ROWS entry: the key itself when bb_engine.ROW_UNIVERSE lists it, else None (BTC/ETH/SOL)."""
    return row if row in be.ROW_UNIVERSE else None


def cell_ukey(universe_name: str):
    k = be.S12_UNIVERSES[universe_name]
    return None if k == "R0" else k


# ============================================================================ H11b cells
def h11b_cells() -> pd.DataFrame:
    """The 648 cells in their fixed order (choice 8): index = itertools.product(bars, BB, near-high, adds, exits,
    universe, direction)."""
    rows = []
    for i, (bars, bb, nh, adds, ex, univ, dirn) in enumerate(itertools.product(
            CELL_BARS, CELL_BB, CELL_NH, CELL_ADDS, CELL_EXITS, F_UNIVERSES, CELL_DIR)):
        rows.append({"cell": i, "bars": bars, "bb_n": bb[0], "bb_k": bb[1], "near_high": nh, "adds": adds,
                     "exits": ex, "universe": univ, "direction": dirn})
    return pd.DataFrame(rows)


def cell_cfg(c, L: float | None = None) -> be.Cfg:
    """Cfg of a cell: R0 (daily), S8 (4-hour) or S16 (1-hour) with the cell's band, near-high rule, adds, exits and
    direction (L = 3 unless given)."""
    g = c if isinstance(c, dict) else dict(c)
    cfg = replace(be.ROWS[F_BARS[g["bars"]]], bb_n=int(g["bb_n"]), bb_k=float(g["bb_k"]), near_high=g["near_high"],
                  adds=g["adds"], tp=g["exits"], direction=g["direction"])
    return replace(cfg, L=float(L)) if L is not None else cfg


def _cfg_key(c) -> tuple:
    return (c["bars"], int(c["bb_n"]), float(c["bb_k"]), c["near_high"], c["direction"], c["adds"], c["exits"])


def decoy_cells(cells: pd.DataFrame | None = None, n: int = 50) -> np.ndarray:
    """The decoy cells (choice 8): default_rng(20261018).choice over the cell index (or over a subset)."""
    rng = np.random.default_rng(SEED)
    if cells is None:
        return np.sort(rng.choice(N_CELLS, size=min(n, N_CELLS), replace=False))
    idx = np.asarray(cells, int)
    return np.sort(rng.choice(idx, size=min(n, len(idx)), replace=False))


# ============================================================================ per-tranche units
def _fill_table(T: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    """The fills of T's positions with base quantities per M: q_open for entries / adds (notional / price), q_close
    for closes (a liquidation's or window-end mark's zero `frac` closes the remaining quantity)."""
    f = tr[tr.pos.isin(T.pos)].reset_index(drop=True)
    if not len(f):
        return f.assign(q_open=[], q_close=[])
    is_open = f.kind.isin(OPEN_KINDS).to_numpy()
    px = f.px.to_numpy(float)
    fr = f.frac.to_numpy(float)
    q = np.where(px > 0, fr / np.where(px > 0, px, 1.0), 0.0)
    codes, uniq = pd.factorize(f.pos.to_numpy())
    nu = len(uniq)
    Q = np.bincount(codes, weights=np.where(is_open, q, 0.0), minlength=nu)
    known = ~is_open & (fr > 0)
    zero = ~is_open & ~(fr > 0)
    Qk = np.bincount(codes, weights=np.where(known, q, 0.0), minlength=nu)
    nz = np.bincount(codes, weights=zero.astype(float), minlength=nu)
    rem = np.maximum(Q - Qk, 0.0)
    f["q_open"] = np.where(is_open, q, 0.0)
    f["q_close"] = np.where(known, q, np.where(zero, rem[codes] / np.maximum(nz[codes], 1.0), 0.0))
    return f


def _fill_volumes(T: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    """Per fill of T's positions: pos, time, kind, v = traded notional per M (an entry / add: its notional; a close:
    its quantity x price; a window-end mark: 0, not a trade)."""
    f = _fill_table(T, tr) if len(T) else tr.iloc[0:0]
    if not len(f):
        return pd.DataFrame({"pos": np.zeros(0, np.int64), "time": pd.DatetimeIndex([], tz="UTC"),
                             "kind": np.zeros(0, object), "v": np.zeros(0)})
    v = np.where(f.kind.isin(OPEN_KINDS), f.frac.to_numpy(float), f.q_close.to_numpy(float) * f.px.to_numpy(float))
    v = np.where(f.kind.to_numpy() == "end", 0.0, v)
    return pd.DataFrame({"pos": f.pos.to_numpy(), "time": pd.DatetimeIndex(f.time), "kind": f.kind.to_numpy(object),
                         "v": v})


def position_volume(T: pd.DataFrame, tr: pd.DataFrame) -> np.ndarray:
    """Traded notional per M of each position of T: every entry / add notional and every close's quantity x price
    (window-end marks are not trades)."""
    if not len(T):
        return np.zeros(0)
    FL = _fill_volumes(T, tr)
    if not len(FL):
        return np.zeros(len(T))
    s = pd.Series(FL.v.to_numpy(float)).groupby(FL.pos.to_numpy()).sum()
    return s.reindex(T.pos.to_numpy()).fillna(0.0).to_numpy()


def tranche_units(T: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    """One row per tranche ("each first entry and each add, counted as one 'bot'") of T's positions (choice 3):
    pos, k (0 = first entry), time (fill stamp), px, q, ret (net P&L per M of the position; the tranches of a
    position sum to its ret exactly), hold_h (fill to the position's final close), open_at_end, grid (False).
    attrs["max_resid_nonliq"]: largest |residual| spread over a non-liquidated position (rounding only)."""
    cols = ["pos", "k", "time", "px", "q", "ret", "hold_h", "open_at_end", "grid"]
    if not len(T):
        out = pd.DataFrame({c: [] for c in cols})
        out.attrs["max_resid_nonliq"] = 0.0
        return out
    f = _fill_table(T, tr)
    o = f[f.kind.isin(OPEN_KINDS)].copy()
    c = f[~f.kind.isin(OPEN_KINDS)]
    Tp = T.set_index("pos")
    pos_o = o.pos.to_numpy()
    q = o.q_open.to_numpy(float)
    px = o.px.to_numpy(float)
    Qs = pd.Series(q).groupby(pos_o).sum()
    pbar = (pd.Series(c.q_close.to_numpy(float) * c.px.to_numpy(float)).groupby(c.pos.to_numpy()).sum()
            .reindex(Qs.index).fillna(0.0) / Qs).fillna(0.0)
    ccl = pd.Series(c.cost.to_numpy(float)).groupby(c.pos.to_numpy()).sum().reindex(Qs.index).fillna(0.0)
    Qi = Qs.reindex(pos_o).to_numpy()
    share = np.where(Qi > 0, q / np.where(Qi > 0, Qi, 1.0), 0.0)
    side = Tp.side.reindex(pos_o).to_numpy(float)
    ret = Tp.ret.reindex(pos_o).to_numpy(float)
    fund = Tp.funding.reindex(pos_o).fillna(0.0).to_numpy(float)
    xt = _ns(Tp.exit_time.reindex(pos_o))
    ft = _ns(o.time)
    hold = np.maximum((xt - ft) / H_NS, 0.0)
    qh = q * hold
    qh_sum = pd.Series(qh).groupby(pos_o).transform("sum").to_numpy()
    w = np.where(qh_sum > 0, qh / np.where(qh_sum > 0, qh_sum, 1.0), share)
    gross = side * q * (pbar.reindex(pos_o).to_numpy() - px)
    net = gross - o.cost.to_numpy(float) - share * ccl.reindex(pos_o).to_numpy() - fund * w
    resid = ret - pd.Series(net).groupby(pos_o).transform("sum").to_numpy()
    net = net + share * resid
    liq = Tp.liquidated.reindex(pos_o).astype(bool).to_numpy()
    out = pd.DataFrame({"pos": pos_o, "k": o.groupby("pos").cumcount().to_numpy(), "time": _ts(ft),
                        "px": px, "q": q, "ret": net, "hold_h": hold,
                        "open_at_end": Tp.open_at_end.reindex(pos_o).astype(bool).to_numpy(), "grid": False})
    nl = ~liq
    out.attrs["max_resid_nonliq"] = float(np.max(np.abs(resid[nl]))) if nl.any() else 0.0
    return out


# ============================================================================ compact engine / grid results
def _empty_T() -> pd.DataFrame:
    T = pd.DataFrame({c: [] for c in T_COLS + ["vol", "grid", "ret_adj"]})
    for c in ("signal_day", "entry1_time", "exit_time"):
        T[c] = pd.DatetimeIndex([], tz="UTC")
    return T


def _empty_comp() -> dict:
    return {"T": _empty_T(), "U": pd.DataFrame({c: [] for c in U_COLS}),
            "DM": pd.DataFrame({c: [] for c in DM_COLS}), "n_dep": 0}


def _cret(sym: str) -> pd.Series:
    r = _CTX["cret"].get(sym)
    if r is None:
        r = bs.returns_from_hours(_hours(sym)) if _src().injected else bs.coin_returns(sym)
        _CTX["cret"][sym] = r
    return r


def _compact(sym: str, res: dict, units: bool = True, adj: bool = False, expo: bool = False) -> dict:
    """What the accounts and statistics need from one simulate_coin result: T (positions: T_COLS, vol = traded
    notional per M, grid False, ret_adj when adj), U (tranche units) and DM (00:00 marks); with expo (cross margin):
    EX = expo and FL = the fills' traded notional per M (_fill_volumes), for an account-level liquidation (choice 22)."""
    T = res["trades"]
    tr = res["tranches"]
    if not len(T):
        out = _empty_comp()
        if expo:
            out["EX"] = res["expo"]
            out["FL"] = _fill_volumes(T, tr)
        return out
    Tc = T[T_COLS].copy()
    Tc["vol"] = position_volume(T, tr)
    Tc["grid"] = False
    Tc["ret_adj"] = bs.drift_adjust(T, res["expo"], {sym: _cret(sym)}).to_numpy(float) if adj else np.nan
    out = {"T": Tc.reset_index(drop=True), "U": tranche_units(T, tr) if units else None,
           "DM": res["daily_mtm"][DM_COLS].copy(), "n_dep": 0}
    if expo:
        out["EX"] = res["expo"]
        out["FL"] = _fill_volumes(T, tr)
    return out


def _ga_compact(sym: str, res: dict, ga: dict, units: bool, adj: bool) -> dict:
    """R0 + G-A on one coin (bb_grid.merge_ga): each deployment one position (L_used 1, ret = net per sleeve) and
    one bot; vol = its fills' notional per sleeve."""
    base = _compact(sym, res, units=units, adj=adj)
    D = ga["deployments"]
    if not len(D):
        return base
    merged = bg.merge_ga(res, ga)
    T = merged["trades"]
    ps = T[T["grid"].astype(bool)].reset_index(drop=True)
    sl = float(ga["log"].get("sleeve", 1.0))
    F = ga["fills"]
    vol = (F.qty.abs() * F.px).groupby(F.dep).sum() / sl if len(F) else pd.Series(dtype=float)
    dep = ps.pos.to_numpy(np.int64) - 1_000_000
    e1 = _ns(ps.entry1_time)
    x1 = _ns(ps.exit_time)
    P = pd.DataFrame({"pos": ps.pos.to_numpy(np.int64), "sym": sym, "side": 1, "signal_day": pd.NaT,
                      "entry1_time": _ts(e1), "exit_time": _ts(x1), "ret": ps.ret.to_numpy(float), "L_used": 1.0,
                      "liquidated": ps.liquidated.astype(bool).to_numpy(), "hold_h": (x1 - e1) / H_NS,
                      "open_at_end": ps.open_at_end.astype(bool).to_numpy(), "n_tranches": 0,
                      "exit_reason": ps.exit_reason.astype(str).to_numpy(), "funding": ps.funding.to_numpy(float),
                      "vol": vol.reindex(dep).fillna(0.0).to_numpy(), "grid": True, "ret_adj": np.nan})
    P["signal_day"] = pd.DatetimeIndex([pd.NaT] * len(P), tz="UTC")
    base["T"] = pd.concat([base["T"], P], ignore_index=True) if len(base["T"]) else P
    if units:
        Ug = pd.DataFrame({"pos": P.pos, "k": 0, "time": P.entry1_time, "px": np.nan, "q": np.nan, "ret": P.ret,
                           "hold_h": P.hold_h, "open_at_end": P.open_at_end, "grid": True})
        base["U"] = pd.concat([base["U"], Ug], ignore_index=True) if len(base["U"]) else Ug
    base["DM"] = merged["daily_mtm"][DM_COLS].copy()
    base["n_dep"] = len(D)
    return base


def _gb_compact(sym: str, res: dict, gb: dict, units: bool, adj: bool) -> dict:
    """R0 + G-B on one coin: wrapped positions take the grids' net per M (bb_grid.grid_gb's trades) and each tranche
    grid is one bot; unwrapped positions pass through with R0's units."""
    base = _compact(sym, res, units=units, adj=adj)
    G = gb["trades"]
    D = gb["deployments"]
    if not len(G) or not len(base["T"]):
        return base
    Tc = base["T"].set_index("pos")
    g = G.set_index("pos")
    wr = g.index[g.gb_wrapped.astype(bool).to_numpy()]
    if len(wr):
        for col in ("ret", "funding"):
            Tc.loc[wr, col] = g.loc[wr, col].astype(float).to_numpy()
        Tc.loc[wr, "liquidated"] = g.loc[wr, "liquidated"].astype(bool).to_numpy()
        Tc.loc[wr, "open_at_end"] = g.loc[wr, "open_at_end"].astype(bool).to_numpy()
        Tc.loc[wr, "exit_time"] = pd.DatetimeIndex(g.loc[wr, "exit_time"]).tz_convert("UTC")
        Tc.loc[wr, "exit_reason"] = g.loc[wr, "exit_reason"].astype(str).to_numpy()
        Tc.loc[wr, "hold_h"] = (_ns(Tc.loc[wr, "exit_time"]) - _ns(Tc.loc[wr, "entry1_time"])) / H_NS
        Tc.loc[wr, "ret_adj"] = np.nan                     # the grids' P&L has no drift adjustment
        F = gb["fills"]
        if len(F) and len(D):
            v = (F.qty.abs() * F.px).groupby(F.dep).sum()
            vp = v.groupby(D.set_index("dep").pos.reindex(v.index).to_numpy()).sum()
            Tc.loc[wr, "vol"] = vp.reindex(wr).fillna(0.0).to_numpy()
    base["T"] = Tc.reset_index()
    if units and len(D):
        keep = base["U"][~base["U"].pos.isin(wr)]
        e1 = _ns(D.start)
        x1 = _ns(D.end)
        Ug = pd.DataFrame({"pos": D.pos.to_numpy(np.int64), "k": D.tranche.to_numpy(np.int64), "time": _ts(e1),
                           "px": D.p_start.to_numpy(float), "q": np.nan, "ret": D.net.to_numpy(float),
                           "hold_h": (x1 - e1) / H_NS, "open_at_end": D.open_at_end.astype(bool).to_numpy(),
                           "grid": True})
        base["U"] = pd.concat([keep, Ug], ignore_index=True) if len(keep) else Ug
    base["DM"] = gb["daily_mtm"][DM_COLS].copy()
    base["n_dep"] = len(D)
    return base


def _run_spec(sym: str, sp: dict):
    """One engine (and grid) run of a spec -> compact result (or counts only for F). Asserts the fill audits."""
    cfg = sp["cfg"]
    a, b = sp["start"], sp["end"]
    hours, minutes = _hours(sym), _minutes(sym)
    P = be.prepare(sym, hours, minutes)
    if P["t"][-1] < bd._utc(a).value or P["t"][0] > bd._utc_end(b).value:
        return {"n_pos": 0, "n_tr": 0} if sp.get("count_only") else _empty_comp()
    res = be.simulate_coin(sym, cfg, start=a, end=b, given_entries=sp.get("given"), hours=hours, minutes=minutes,
                           entry_allowed=_mask(sym, sp.get("mkey")), mmr=_mmr(sym), detail=bool(sp.get("detail")))
    _audit_ok(res["fills_audit"], f"{sym} {sp.get('group')} {sp.get('id')}")
    if sp.get("count_only"):
        kinds = res["tranches"]["kind"].to_numpy(object) if len(res["tranches"]) else np.zeros(0, object)
        npos = int(np.sum(kinds == "entry"))
        del res                                              # choice 16: nothing but the tranche kinds is read
        return {"n_pos": npos, "n_tr": int(np.isin(kinds, OPEN_KINDS).sum())}
    grid = sp.get("grid")
    units, adj = bool(sp.get("units", True)), bool(sp.get("adj", False))
    if grid in ("GA", "GB") and _has_m1(sym):
        g0 = max(bd._utc(a), bd._utc(_grid_from()))
        if g0 <= bd._utc_end(b):
            kw = dict(minutes=minutes, hours=hours, mmr=_mmr(sym), tick=_tick(sym))
            if grid == "GA":
                g = bg.grid_ga(sym, res["trades"], start=g0, end=b, **kw)
                _audit_ok(g["fills_audit"], f"{sym} G-A {sp.get('id')}")
                return _ga_compact(sym, res, g, units, adj)
            g = bg.grid_gb(sym, res, start=g0, end=b, **kw)
            _audit_ok(g["fills_audit"], f"{sym} G-B {sp.get('id')}")
            return _gb_compact(sym, res, g, units, adj)
    return _compact(sym, res, units=units, adj=adj, expo=bool(sp.get("detail")))


def _spec_job(args) -> dict:
    """Stage 1 (coin-major): every spec of one coin, in order; results grouped by spec['group'] and pickled to the
    work directory as <group>/<sym>.pkl = {spec id: compact} (or kept in memory when there is no work directory)."""
    sym, specs = args
    t0 = time.time()
    specs = sorted(specs, key=lambda s: (s["group"], s["order"]))           # each group's specs contiguous
    cur, buf, mem = None, {}, {}
    n_pos = 0
    for sp in specs:
        if sp["group"] != cur:
            if cur is not None:
                _flush(cur, sym, buf, mem)
            cur, buf = sp["group"], {}
        r = _run_spec(sym, sp)
        buf[sp["id"]] = r
        n_pos += int(r.get("n_pos", 0)) if sp.get("count_only") else len(r["T"])
    if cur is not None:
        _flush(cur, sym, buf, mem)
    be.clear_cache()
    return {"sym": sym, "n_specs": len(specs), "n_pos": n_pos, "seconds": time.time() - t0, "mem": mem}


def _flush(group, sym, buf, mem) -> None:
    if _CTX["work"] is None:
        mem[group] = buf
    else:
        _put(group, sym, buf)


def run_specs(specs: list, jobs: int, say=None, label: str = "") -> dict:
    """Run specs coin-major in a process pool. Each spec: group, id, cfg, start, end, mkey, grid, detail, adj,
    units[, given, count_only]. Returns {group: {sym: {id: compact}}} when kept in memory, else {} (pickled)."""
    by = {}
    for i, sp in enumerate(specs):
        sp.setdefault("order", (sp["group"], i))
        by.setdefault(sp["sym"], []).append(sp)
    jobl = sorted(by.items(), key=lambda kv: -len(kv[1]))
    t0 = time.time()
    res = _pmap(_spec_job, jobl, jobs)
    if say:
        say(f"  {label}: {len(specs)} engine runs on {len(by)} coins, {sum(r['n_pos'] for r in res)} positions, "
            f"fill audits empty ({time.time() - t0:.0f} s)")
    out = {}
    for r in res:
        for g, d in r["mem"].items():
            out.setdefault(g, {})[r["sym"]] = d
    return out


def _load(group: str, sym: str, mem: dict | None = None) -> dict:
    if mem is not None and group in mem:
        return mem[group][sym]
    return _get(group, sym)


def _loader(group: str, mem: dict | None = None):
    """_load with a per-job cache (a stage-2 job reads each coin's file once for all its spans)."""
    cache = {}

    def get(sym):
        if sym not in cache:
            cache[sym] = _load(group, sym, mem)
        return cache[sym]
    return get


# ============================================================================ accounts and statistics
def _account(parts: dict, cfg, start, end, K: int, idle_tbill: bool = False) -> dict:
    rbc = {}
    for s, c in parts.items():
        d = {"trades": c["T"], "daily_mtm": c["DM"]}
        if "EX" in c:
            d["expo"] = c["EX"]
        rbc[s] = d
    return be.assemble(rbc, cfg, start, end, idle_tbill=idle_tbill, k_slots=K)


def _cross_pnl(acct: dict) -> dict:
    """S3 cross margin (choice 22): {(sym, pos): the account's dollar P&L} of the positions open when
    bb_engine.assemble liquidated the cross account. assemble books each at M x (pnl_lo - mm), which can sum to more
    than the account lost (it keeps max(0, equity - maintenance)); they are scaled so that every held position's P&L
    sums to the account's equity change: target = E_end - E_start - interest to the breach - the P&L of the held
    positions closed before it (pro rata to assemble's values when both are losses, else by M)."""
    ct = acct.get("cross_liquidation")
    A = acct["trades"]
    if ct is None or not len(A) or "exit_reason" not in A:
        return {}
    isb = (A.exit_reason.astype(str) == "cross_liq").to_numpy()
    if not isb.any():
        return {}
    M = A.M.to_numpy(float)
    pnl = A.pnl_usd.to_numpy(float)
    held = M > 0
    E = acct["equity"]
    INT = acct.get("interest")
    int_b = 0.0
    if INT is not None and len(INT):
        sel = INT[INT.index <= ct]
        int_b = float(sel.iloc[-1]) if len(sel) else 0.0
    target = float(E.iloc[-1]) - float(E.iloc[0]) - int_b - float(pnl[held & ~isb].sum())
    pb = pnl[isb]
    eng = float(pb.sum())
    if eng < 0 and target <= 0:
        pb = pb * (target / eng)
    else:
        mb = M[isb]
        pb = target * mb / mb.sum() if mb.sum() > 0 else np.full(len(mb), target / max(len(mb), 1))
    keys = zip(A.sym.astype(str).to_numpy()[isb], A.pos.to_numpy(np.int64)[isb])
    return {(s, int(p)): float(v) for (s, p), v in zip(keys, pb)}


def _cross_close(pu: pd.DataFrame, tu: pd.DataFrame, parts: dict, brk: dict, ct) -> tuple:
    """Positions closed by the cross account's liquidation (choice 22): closed at the breach hour with the account's
    P&L (ret = P&L / M; liquidated; not open at the end; held to the breach), traded volume = the account's fills (opens
    to the breach hour, closes before it) plus the liquidation's close at the position's notional in the breach hour,
    drift adjustment over the hours to the breach; tranche units filled after the breach are dropped (the account
    never placed them) and the rest share the position's P&L by quantity, held from their fill to the breach."""
    ct = pd.Timestamp(ct)
    ct = ct.tz_localize("UTC") if ct.tzinfo is None else ct.tz_convert("UTC")
    ctn = int(ct.value)
    pu = pu.copy()
    tu = tu.copy()
    drop = np.zeros(len(tu), bool)
    psym, ppos = pu.sym.to_numpy(object), pu.pos.to_numpy(np.int64)
    tsym, tpos = (tu.sym.to_numpy(object), tu.pos.to_numpy(np.int64)) if len(tu) else (np.zeros(0, object),
                                                                                      np.zeros(0, np.int64))
    for (s, p), pnl_b in brk.items():
        mi = np.flatnonzero((psym == s) & (ppos == p))
        if not len(mi):
            continue
        li = pu.index[mi[0]]
        M = float(pu.at[li, "M"])
        e1 = int(_ns(pu.time.iloc[[mi[0]]])[0])
        ret_b = pnl_b / M
        c = parts[s]
        FL, EX, T = c.get("FL"), c.get("EX"), c["T"]
        vol = float(pu.at[li, "vol"])
        if FL is not None:
            f = FL[FL.pos.to_numpy() == p]
            ft = _ns(f.time)
            op = f.kind.isin(OPEN_KINDS).to_numpy()
            vol = float(f.v.to_numpy(float)[(op & (ft <= ctn)) | (~op & (ft < ctn))].sum())
        ra = np.nan
        if EX is not None and len(EX):
            ex_t = _ns(EX.time)
            mine = EX.pos.to_numpy() == p
            vol += float(np.abs(EX.notional.to_numpy(float)[mine & (ex_t == ctn)]).sum())
            row = T[T.pos.to_numpy() == p]
            if "ret_adj" in T and len(row) and np.isfinite(row.ret_adj.to_numpy(float)).any():
                t1 = pd.DataFrame({"sym": [s], "pos": [p], "entry1_time": pd.DatetimeIndex(row.entry1_time.iloc[:1]),
                                   "exit_time": pd.DatetimeIndex([ct]), "ret": [ret_b], "hold_h": [(ctn - e1) / H_NS]})
                ra = float(bs.drift_adjust(t1, EX[mine & (ex_t <= ctn)], {s: _cret(s)}).iloc[0])
        pu.loc[li, ["ret", "pnl", "hold_h", "vol", "ret_adj"]] = [ret_b, pnl_b, (ctn - e1) / H_NS, vol, ra]
        pu.loc[li, "open_at_end"] = False
        pu.loc[li, "liquidated"] = True
        tj = np.flatnonzero((tsym == s) & (tpos == p))
        if not len(tj):
            continue
        tt = _ns(tu.time.iloc[tj])
        kept, gone = tj[tt <= ctn], tj[tt > ctn]
        drop[gone] = True
        if not len(kept):
            continue
        q = tu.q.to_numpy(float)[kept] if "q" in tu else np.full(len(kept), np.nan)
        w = q / q.sum() if np.isfinite(q).all() and q.sum() > 0 else np.full(len(kept), 1.0 / len(kept))
        lk = tu.index[kept]
        tu.loc[lk, "pnl"] = pnl_b * w
        tu.loc[lk, "ret"] = pnl_b * w / M
        tu.loc[lk, "hold_h"] = (ctn - tt[tt <= ctn]) / H_NS
        tu.loc[lk, "open_at_end"] = False
    return pu, tu[~drop].reset_index(drop=True)


def _unit_frames(acct: dict, parts: dict) -> tuple:
    """(position units, tranche units) of the positions the account held, with dollar P&L = return per M x the
    position's M from the account (choice 22): positions outside the account's window (no M) and positions it never
    held (M = 0: entered after an S3 cross-margin liquidation or after the equity reached 0) are left out; positions
    closed by an S3 cross-margin liquidation are closed at the breach with the account's P&L (_cross_close)."""
    A = acct["trades"]
    if len(A):
        Mk = pd.Series(A["M"].to_numpy(float), index=pd.MultiIndex.from_arrays([A.sym.astype(str).to_numpy(),
                                                                                 A.pos.to_numpy(np.int64)]))
    else:
        Mk = pd.Series(dtype=float)
    pos_l, tr_l = [], []
    for s, c in parts.items():
        T = c["T"]
        if len(T):
            m = Mk.reindex(pd.MultiIndex.from_arrays([np.full(len(T), s), T.pos.to_numpy(np.int64)])).to_numpy()
            pos_l.append(pd.DataFrame({"sym": s, "pos": T.pos.to_numpy(np.int64), "side": T.side.to_numpy(int),
                                       "ret": T.ret.to_numpy(float), "M": m, "pnl": T.ret.to_numpy(float) * m,
                                       "hold_h": T.hold_h.to_numpy(float),
                                       "open_at_end": T.open_at_end.astype(bool).to_numpy(),
                                       "time": pd.DatetimeIndex(T.entry1_time), "vol": T.vol.to_numpy(float),
                                       "grid": T.grid.astype(bool).to_numpy(),
                                       "ret_adj": T.ret_adj.to_numpy(float) if "ret_adj" in T else np.nan,
                                       "liquidated": T.liquidated.astype(bool).to_numpy()}))
        U = c.get("U")
        if U is not None and len(U):
            m = Mk.reindex(pd.MultiIndex.from_arrays([np.full(len(U), s), U.pos.to_numpy(np.int64)])).to_numpy()
            tr_l.append(pd.DataFrame({"sym": s, "pos": U.pos.to_numpy(np.int64), "ret": U.ret.to_numpy(float),
                                      "M": m, "pnl": U.ret.to_numpy(float) * m, "hold_h": U.hold_h.to_numpy(float),
                                      "open_at_end": U.open_at_end.astype(bool).to_numpy(),
                                      "time": pd.DatetimeIndex(U.time), "grid": U.grid.astype(bool).to_numpy(),
                                      "q": U.q.to_numpy(float) if "q" in U else np.nan}))
    cols_p = ["sym", "pos", "side", "ret", "M", "pnl", "hold_h", "open_at_end", "time", "vol", "grid", "ret_adj",
              "liquidated"]
    cols_t = ["sym", "pos", "ret", "M", "pnl", "hold_h", "open_at_end", "time", "grid", "q"]
    pu = pd.concat(pos_l, ignore_index=True) if pos_l else pd.DataFrame({c: [] for c in cols_p})
    tu = pd.concat(tr_l, ignore_index=True) if tr_l else pd.DataFrame({c: [] for c in cols_t})

    def _held(F):                       # outside the account's window (no M) or never held by it (M = 0)
        m = F.M.to_numpy(float)
        return F[np.isfinite(m) & (m > 0)].reset_index(drop=True) if len(F) else F.reset_index(drop=True)
    pu, tu = _held(pu), _held(tu)
    brk = _cross_pnl(acct)
    if brk and len(pu):
        pu, tu = _cross_close(pu, tu, parts, brk, acct["cross_liquidation"])
    return pu, tu


def _winloss(p: np.ndarray) -> float:
    w = p[p > 0]
    lo = p[p < 0]
    return float(w.mean() / -lo.mean()) if len(w) and len(lo) else np.nan


def unit_stats(U: pd.DataFrame) -> dict:
    """H11 statistics of a unit table (columns ret, pnl, hold_h, open_at_end): see the module docstring."""
    n = len(U)
    out = {"n": int(n)}
    if n == 0:
        out.update(n_closed=0, n_open_at_end=0, hit=np.nan, winloss=np.nan, n_wins=0, n_losses=0, n_gt7=0,
                   gt7_won=np.nan, n_ge3=0, ge3_profit=np.nan, total_pnl_closed=0.0, ge3_defined=False,
                   ge3_profit_gross=np.nan, mean_ret=np.nan)
        return out
    oe = U.open_at_end.astype(bool).to_numpy()
    r = U.ret.to_numpy(float)
    p = U.pnl.to_numpy(float)
    h = U.hold_h.to_numpy(float)
    cl = ~oe
    rc, pc, hc = r[cl], p[cl], h[cl]
    out["n_closed"] = int(cl.sum())
    out["n_open_at_end"] = int(oe.sum())
    out["hit"] = float((rc > 0).mean()) if len(rc) else np.nan
    out["winloss"] = _winloss(pc)
    out["n_wins"] = int((pc > 0).sum())
    out["n_losses"] = int((pc < 0).sum())
    g7 = hc > 168.0
    out["n_gt7"] = int(g7.sum())
    out["gt7_won"] = float((rc[g7] > 0).mean()) if g7.any() else np.nan
    g3 = hc >= 72.0
    out["n_ge3"] = int(g3.sum())
    tot = float(pc.sum())
    out["total_pnl_closed"] = tot
    out["ge3_defined"] = bool(tot > 0)
    out["ge3_profit"] = float(pc[g3].sum() / tot) if len(pc) and tot != 0 else np.nan
    gp = float(pc[pc > 0].sum())
    out["ge3_profit_gross"] = float(pc[g3 & (pc > 0)].sum() / gp) if gp > 0 else np.nan   # winners only (beside)
    out["mean_ret"] = float(np.mean(r))
    return out


def _wilson(k: int, n: int, z: float = Z_IV) -> tuple:
    if n <= 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - hw, c + hw


def unit_intervals(U: pd.DataFrame, B: int, seed: int = SEED, which=("hit", "winloss", "gt7_won", "ge3_profit")):
    """95% intervals of a unit table: hit rate (Wilson; and month-cluster percentile bootstrap), win / loss and the
    holding shares (month-cluster percentile bootstrap over the units' entry months, bb_stats.cluster_boot_ci)."""
    out = {f"{k}_{e}": np.nan for k in which for e in ("lo", "hi")}
    if "hit" in which:
        out["hit_wlo"] = out["hit_whi"] = np.nan
    if not len(U):
        return out
    cl = ~U.open_at_end.astype(bool).to_numpy()
    rc = U.ret.to_numpy(float)[cl]
    pc = U.pnl.to_numpy(float)[cl]
    hc = U.hold_h.to_numpy(float)[cl]
    g = bs.month_key(pd.DatetimeIndex(U.time)[cl]) if cl.any() else np.zeros(0, int)
    n = len(rc)
    if "hit" in which and n:
        out["hit_wlo"], out["hit_whi"] = _wilson(int((rc > 0).sum()), n)

    def _gt7(r):
        m = hc[r] > 168.0
        return (rc[r][m] > 0).mean() if m.any() else np.nan

    def _ge3(r):
        t = pc[r].sum()
        return pc[r][hc[r] >= 72.0].sum() / t if t > 0 else np.nan

    fns = {"hit": lambda r: (rc[r] > 0).mean(), "winloss": lambda r: _winloss(pc[r]), "gt7_won": _gt7,
           "ge3_profit": _ge3}
    if n >= 2 and len(np.unique(g)) >= 2 and B > 0:
        for k in which:
            _, lo, hi, nv = bs.cluster_boot_ci(n, g, fns[k], B=B, seed=seed)
            if nv:
                out[f"{k}_lo"], out[f"{k}_hi"] = lo, hi
    return out


def acct_stats(acct: dict, pos_units: pd.DataFrame | None = None, B: int = 0, seed: int = SEED) -> dict:
    """Account-level statistics: multiple (with its month-block bootstrap 95% interval when B > 0), CAGR, log growth
    a year, Sharpe of daily returns (idle cash at 0%), max drawdown, mean equity, traded volume (in units of the
    starting equity) and turnover = volume / mean equity, liquidations."""
    E = acct["equity"].to_numpy(float)
    r = acct["ret"].to_numpy(float)
    out = {"days": int(len(r))}
    mult = float(E[-1] / E[0]) if len(E) and E[0] > 0 else np.nan
    yrs = len(r) / 365.25 if len(r) else np.nan
    out["multiple"] = mult
    out["years"] = yrs
    out["cagr"] = float(mult ** (1 / yrs) - 1) if mult > 0 and yrs > 0 else (-1.0 if mult == 0 else np.nan)
    out["log_growth_yr"] = float(np.log(mult) / yrs) if mult > 0 and yrs > 0 else (-np.inf if mult == 0 else np.nan)
    sd = float(np.std(r, ddof=1)) if len(r) > 1 else np.nan
    out["sharpe"] = float(np.mean(r) / sd * math.sqrt(365)) if sd and sd > 0 else np.nan
    out["max_dd"] = float(bs.maxdd_fn(r[None, :])[0]) if len(r) else np.nan
    out["mean_equity"] = float(E[:-1].mean()) if len(E) > 1 else (float(E[0]) if len(E) else np.nan)
    vol = float(np.nansum(pos_units.vol.to_numpy(float) * pos_units.M.to_numpy(float))) \
        if pos_units is not None and len(pos_units) else 0.0
    out["volume"] = vol
    out["turnover"] = vol / out["mean_equity"] if out["mean_equity"] and out["mean_equity"] > 0 else np.nan
    out["liquidations"] = int(len(acct["liquidations"])) if acct.get("liquidations") is not None else 0
    out["cross_liquidation"] = acct.get("cross_liquidation") is not None
    out["any_liquidation"] = bool(out["liquidations"] > 0 or out["cross_liquidation"])
    out["peak_multiple"] = float(np.max(E) / E[0]) if len(E) and E[0] > 0 else np.nan
    out["dead"] = bool(acct.get("dead", False))
    out["multiple_lo"] = out["multiple_hi"] = np.nan
    if B > 0 and len(r) >= 2:
        _, lo, hi = bs.block_boot_ci(r, bs.multiple_fn, bs.MONTH_DAYS, B=B, seed=seed)
        out["multiple_lo"], out["multiple_hi"] = lo, hi
    return out


# ============================================================================ consistency and distance
def _se(p0: float, n) -> float:
    return math.sqrt(p0 * (1 - p0) / n) if n and n > 0 else np.nan


def consistency(st: dict, iv: dict, acct: dict, n_tranches: int, hit_target: float = POST["hit"]) -> dict:
    """H11's consistency rule (module docstring; choices 4-6) on one unit's statistics st / intervals iv and the
    account's multiple interval. n_tranches: the row's per-tranche count."""
    se_h = _se(hit_target, st.get("n_closed", 0))
    ok_hit = bool(np.isfinite(st["hit"]) and np.isfinite(se_h) and abs(st["hit"] - hit_target) <= 2 * se_h + 1e-15)
    se_7 = _se(POST["gt7_won"], st.get("n_gt7", 0))
    ok_gt7 = bool(np.isfinite(st["gt7_won"]) and np.isfinite(se_7)
                  and abs(st["gt7_won"] - POST["gt7_won"]) <= 2 * se_7 + 1e-15)
    se_3 = _se(POST["ge3_profit"], st.get("n_closed", 0))
    ok_ge3 = bool(st.get("ge3_defined", False) and np.isfinite(st["ge3_profit"]) and np.isfinite(se_3)
                  and st["ge3_profit"] >= POST["ge3_profit"] - 2 * se_3 - 1e-15)
    lo, hi = iv.get("winloss_lo", np.nan), iv.get("winloss_hi", np.nan)
    ok_wl = bool(np.isfinite(lo) and np.isfinite(hi) and lo <= POST["winloss"] <= hi)
    mlo, mhi = acct.get("multiple_lo", np.nan), acct.get("multiple_hi", np.nan)
    ok_m = bool(np.isfinite(mlo) and np.isfinite(mhi) and mlo <= POST["multiple"] <= mhi)
    ok_c = bool(COUNT_LO <= n_tranches <= COUNT_HI)
    others = ok_hit and ok_gt7 and ok_ge3 and ok_wl and ok_m
    cons = others and ok_c
    # literal reading (audit): 'different trading frequency' only for a row that fails on count alone
    status = "consistent" if cons else ("different trading frequency" if (others and not ok_c) else (
        "inconsistent (also different trading frequency)" if not ok_c else "inconsistent"))
    return {"ok_hit": ok_hit, "ok_gt7": ok_gt7, "ok_ge3": ok_ge3, "ok_winloss": ok_wl, "ok_multiple": ok_m,
            "ok_count": ok_c, "consistent": cons, "status": status, "fails_only_on_count": bool(others and not ok_c),
            "hit_target": hit_target, "se_hit": se_h, "se_gt7": se_7, "se_ge3": se_3}


def _z_iv(est, target, lo, hi, log=False) -> float:
    """z of an estimate against the post's value on a 95% interval's scale: 1.96 x distance / (distance from the
    estimate to the interval end on the target's side) (in logs when log=True)."""
    if not (np.isfinite(est) and np.isfinite(lo) and np.isfinite(hi)):
        return np.nan
    if log:
        if est <= 0 or lo <= 0 or hi <= 0:
            return -np.inf if est <= 0 else np.nan
        est, target, lo, hi = math.log(est), math.log(target), math.log(lo), math.log(hi)
    d = est - target
    if d == 0:
        return 0.0
    hw = (hi - est) if target > est else (est - lo)
    if hw <= 0:
        return math.copysign(np.inf, d)
    return Z_IV * d / hw


def z_scores(st: dict, iv: dict, acct: dict, n_tranches: int, hit_target: float = POST["hit"]) -> dict:
    """The six z-scores of D (per-tranche statistics st and intervals iv; choice 7)."""
    z = {}
    z["count"] = Z_COUNT_EDGE * math.log(n_tranches / POST["tranches"]) / math.log(2.0) if n_tranches > 0 \
        else -np.inf
    se_h = _se(hit_target, st.get("n_closed", 0))
    z["hit"] = (st["hit"] - hit_target) / se_h if np.isfinite(st["hit"]) and np.isfinite(se_h) else np.nan
    z["winloss"] = _z_iv(st["winloss"], POST["winloss"], iv.get("winloss_lo", np.nan), iv.get("winloss_hi", np.nan))
    z["multiple"] = _z_iv(acct["multiple"], POST["multiple"], acct.get("multiple_lo", np.nan),
                          acct.get("multiple_hi", np.nan), log=True)
    se_7 = _se(POST["gt7_won"], st.get("n_gt7", 0))
    z["gt7_won"] = (st["gt7_won"] - POST["gt7_won"]) / se_7 if np.isfinite(st["gt7_won"]) and np.isfinite(se_7) \
        else np.nan
    se_3 = _se(POST["ge3_profit"], st.get("n_closed", 0))
    z["ge3_profit"] = min(0.0, st["ge3_profit"] - POST["ge3_profit"]) / se_3 \
        if st.get("ge3_defined", False) and np.isfinite(st["ge3_profit"]) and np.isfinite(se_3) else np.nan
    return z


def distance(z: dict) -> float:
    """D = sum of the squared z-scores; an undefined z makes D infinite."""
    v = np.array([z[k] for k in D_STATS], float)
    if np.isnan(v).any():
        return np.inf
    return float(np.sum(v * v))


def identified_set(D, k: int = K_D, level: float = 0.95) -> tuple:
    """(mask of cells with D <= D_min + chi2_level(k), D_min, threshold); empty when no D is finite."""
    D = np.asarray(D, float)
    fin = np.isfinite(D)
    if not fin.any():
        return np.zeros(len(D), bool), np.nan, np.nan
    dmin = float(D[fin].min())
    thr = dmin + float(sps.chi2.ppf(level, k))
    return D <= thr, dmin, thr


def reading_rule(share_cells: float, share_decoys: float, set_cells: pd.DataFrame) -> dict:
    """The fixed reading: the post identifies a strategy only if fewer than 5% of cells and fewer than 5% of decoys
    fall in the identified set and the set's cells share bars and universe."""
    n = len(set_cells)
    same_bars = bool(n > 0 and set_cells["bars"].nunique() == 1)
    same_univ = bool(n > 0 and set_cells["universe"].nunique() == 1)
    ok = bool(n > 0 and np.isfinite(share_cells) and np.isfinite(share_decoys) and share_cells < 0.05
              and share_decoys < 0.05 and same_bars and same_univ)
    return {"identifies": ok, "same_bars": same_bars, "same_universe": same_univ, "share_cells": share_cells,
            "share_decoys": share_decoys, "n_set": n,
            "text": ("the post's statistics identify a rule set (called 'a rule set consistent with the post', never "
                     "'their strategy')") if ok else "the post's statistics do not identify the strategy"}


def months_needed(sd_month: float, mult: float = POST["multiple"], months: int = POST["months"]) -> dict:
    """Months of record for t >= 2 at the post's implied return (choice 14): n = (2 sigma / mu)^2 with mu = mult^(1 /
    months) - 1 (simple) and, beside it, mu = ln(mult) / months (log)."""
    mu = mult ** (1.0 / months) - 1.0
    mul = math.log(mult) / months
    n = (2 * sd_month / mu) ** 2 if np.isfinite(sd_month) else np.nan
    nl = (2 * sd_month / mul) ** 2 if np.isfinite(sd_month) else np.nan
    return {"sd_month": sd_month, "mu_month": mu, "months_needed": n, "mu_month_log": mul, "months_needed_log": nl,
            "formula": "t = mu * sqrt(n) / sigma >= 2  <=>  n >= (2 * sigma / mu)^2, mu = 4.3^(1/16) - 1 per month"}


def _monthly_sd(acct: dict) -> tuple:
    """SD (ddof 1) of the account's complete calendar months' simple returns, and their count."""
    E = acct["equity"]
    if len(E) < 2:
        return np.nan, 0
    idx = pd.DatetimeIndex(E.index)
    vals = E.reindex(idx[idx.day == 1]).to_numpy(float)
    rets = vals[1:] / vals[:-1] - 1.0 if len(vals) > 1 else np.zeros(0)
    rets = rets[np.isfinite(rets)]
    return (float(np.std(rets, ddof=1)) if len(rets) > 1 else np.nan), int(len(rets))


# ============================================================================ random entries
def _decision_times(bars: str, start, end) -> pd.DatetimeIndex:
    """Decision times on the bar grid inside [start, end] (choice 9)."""
    a, b = bd._utc(start), bd._utc_end(end)
    f = {"1d": "D", "4h": "4h", "1h": "h"}[bars]
    return pd.date_range(a.ceil(f), b.floor(f), freq=f).as_unit("ns")


def candidate_table(sym: str, cfg: be.Cfg, start, end, times, side: int = 1, mask=None) -> pd.DataFrame:
    """Every decision time's own position under entry_mode "given" (choice 9), found by peeling: run the engine on
    the times still undecided; each run settles the times met while flat (a position, or a skip / no fill), and the
    times dropped because a position was open or pending go to the next run. Returns the valid times: time, side,
    a (decision hour index), b (hour index of the position's final close), entry1_time, exit_time, n_tranches;
    attrs n_times, n_valid, n_runs."""
    if cfg.entry_mode != "given":
        raise ValueError("candidate_table needs entry_mode='given'")
    hours, minutes = _hours(sym), _minutes(sym)
    P = be.prepare(sym, hours, minutes)
    t0 = int(P["t"][0])
    period = bd.FREQ[cfg.bars].value
    rem = pd.DatetimeIndex(times)
    if mask is not None and len(rem):
        rem = rem[_member_values(mask, rem)]
    n_times = len(rem)
    rows = []
    runs = 0
    while len(rem):
        g = pd.DataFrame({"time": rem, "side": np.full(len(rem), int(side))})
        r = be.simulate_coin(sym, cfg, start=start, end=end, given_entries=g, hours=hours, minutes=minutes,
                             entry_allowed=mask, mmr=_mmr(sym), detail=False)
        runs += 1
        _audit_ok(r["fills_audit"], f"{sym} candidates")
        S = r["signals"]
        S = S[S.given.astype(bool)] if len(S) else S
        T = r["trades"]
        if len(T):
            Tg = T[T.given.astype(bool)]
            tr = r["tranches"]
            bh = tr[tr.kind.isin(CLOSE_KINDS)].groupby("pos").hour.max()
            rows.append(pd.DataFrame({"time": pd.DatetimeIndex(Tg.signal_known), "side": Tg.side.to_numpy(int),
                                      "a": (_ns(Tg.signal_known) - t0) // H_NS,
                                      "b": bh.reindex(Tg.pos).to_numpy(np.int64),
                                      "entry1_time": pd.DatetimeIndex(Tg.entry1_time),
                                      "exit_time": pd.DatetimeIndex(Tg.exit_time),
                                      "n_tranches": Tg.n_tranches.to_numpy(int)}))
        drop = S.fate.astype(str).to_numpy() == "given_dropped" if len(S) else np.zeros(0, bool)
        new = pd.DatetimeIndex(_ns(S.signal_day)[drop] + period, tz="UTC") if drop.any() else pd.DatetimeIndex(
            [], tz="UTC")
        if len(new) >= len(rem):
            raise RuntimeError(f"bb_fit.candidate_table({sym}): no progress ({len(new)} of {len(rem)} undecided)")
        rem = new
    C = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        {"time": pd.DatetimeIndex([], tz="UTC"), "side": [], "a": [], "b": [], "entry1_time": pd.DatetimeIndex(
            [], tz="UTC"), "exit_time": pd.DatetimeIndex([], tz="UTC"), "n_tranches": []})
    C = C.sort_values("time", kind="stable").reset_index(drop=True)
    C.attrs.update(n_times=int(n_times), n_valid=int(len(C)), n_runs=int(runs))
    return C


def draw_entries(cands: pd.DataFrame, quota: dict, rng, max_tries: int = 20) -> tuple:
    """Sequential flat-day sampler (choice 9): walk a random permutation of the valid candidates, accept one when its
    side's quota is open and its interval [a, b] overlaps no accepted interval (the coin is flat there and stays
    free of the accepted positions), until every quota is met; up to max_tries permutations, keeping the fullest.
    Returns (accepted rows in time order, shortfall = entries the quotas could not place)."""
    need0 = {int(k): int(v) for k, v in quota.items() if int(v) > 0}
    if not need0 or not len(cands):
        return cands.iloc[0:0].copy(), int(sum(need0.values()))
    a = cands.a.to_numpy(np.int64)
    b = cands.b.to_numpy(np.int64)
    s = cands.side.to_numpy(np.int64)
    off = int(a.min())
    span = int(max(b.max(), a.max())) - off + 2
    best = None
    for _ in range(max(1, int(max_tries))):
        occ = np.zeros(span, bool)
        need = dict(need0)
        left = sum(need.values())
        acc = []
        for i in rng.permutation(len(a)):
            si = int(s[i])
            if need.get(si, 0) <= 0:
                continue
            lo, hi = a[i] - off, b[i] - off + 1
            if occ[lo:hi].any():
                continue
            occ[lo:hi] = True
            need[si] -= 1
            left -= 1
            acc.append(i)
            if left == 0:
                break
        if best is None or left < best[1]:
            best = (acc, left)
        if left == 0:
            break
    acc, short = best
    sel = cands.iloc[sorted(acc, key=lambda i: a[i])].reset_index(drop=True)
    return sel, int(short)


def _given_frame(sel: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"time": pd.DatetimeIndex(sel.time), "side": sel.side.to_numpy(int)})


def _check_twin(res: dict, sel: pd.DataFrame, what: str) -> None:
    """The engine run of a drawn version must reproduce exactly the drawn positions (given-entry independence)."""
    T = res["trades"]
    if len(T) != len(sel):
        raise RuntimeError(f"bb_fit: {what}: {len(T)} positions from {len(sel)} drawn entries")
    if len(T):
        a = np.sort(_ns(T.entry1_time))
        b = np.sort(_ns(sel.entry1_time))
        xa = np.sort(_ns(T.exit_time))
        xb = np.sort(_ns(sel.exit_time))
        if not (np.array_equal(a, b) and np.array_equal(xa, xb)):
            raise RuntimeError(f"bb_fit: {what}: the run's entry / exit times differ from the drawn positions")


def _twins_job(args) -> dict:
    """Stage 1 of random-entry versions for one coin: candidate tables (per side), n draws, the engine run of each
    draw (checked), compacts pickled as <group>/<sym>.pkl = {"versions": [...], "short": [...], ...}."""
    sym, task = args
    t0 = time.time()
    cfg_g, a, b, mkey = task["cfg"], task["start"], task["end"], task.get("mkey")
    quota = {int(k): int(v) for k, v in task["quota"].items() if int(v) > 0}
    mask = _mask(sym, mkey)
    times = _decision_times(cfg_g.bars, a, b)
    tabs = [candidate_table(sym, cfg_g, a, b, times, side=sd, mask=mask) for sd in sorted(quota)]
    cands = pd.concat(tabs, ignore_index=True) if tabs else pd.DataFrame()
    rng = np.random.default_rng(task["seed"])
    hours, minutes = _hours(sym), _minutes(sym)
    vers, shorts = [], []
    for v in range(int(task["n"])):
        sel, short = draw_entries(cands, quota, rng, task.get("max_tries", 20))
        if len(sel):
            res = be.simulate_coin(sym, cfg_g, start=a, end=b, given_entries=_given_frame(sel), hours=hours,
                                   minutes=minutes, entry_allowed=mask, mmr=_mmr(sym), detail=False)
            _audit_ok(res["fills_audit"], f"{sym} {task['group']} version {v}")
            _check_twin(res, sel, f"{sym} {task['group']} version {v}")
            comp = _compact(sym, res, units=True, adj=False)
        else:
            comp = _empty_comp()
        vers.append(comp)
        shorts.append(short)
    out = {"versions": vers, "short": shorts, "n_times": int(sum(t.attrs.get("n_times", 0) for t in tabs)),
           "n_valid": int(len(cands)), "n_runs": int(sum(t.attrs.get("n_runs", 0) for t in tabs)), "quota": quota}
    if _CTX["work"] is None:
        res_mem = {task["group"]: out}
    else:
        _put(task["group"], sym, out)
        res_mem = {}
    be.clear_cache()
    return {"sym": sym, "group": task["group"], "n": len(vers), "short": int(np.sum(shorts)),
            "n_valid": out["n_valid"], "n_runs": out["n_runs"], "seconds": time.time() - t0, "mem": res_mem}


def run_twins(tasks: list, jobs: int, say=None, label: str = "") -> dict:
    """tasks: (sym, task) pairs; returns {group: {sym: out}} when kept in memory."""
    t0 = time.time()
    res = _pmap(_twins_job, tasks, jobs)
    if say:
        say(f"  {label}: {len(tasks)} coin tasks, {sum(r['n'] for r in res)} drawn versions, shortfall "
            f"{sum(r['short'] for r in res)} entries, fill audits empty ({time.time() - t0:.0f} s)")
    out = {}
    for r in res:
        for g, d in r["mem"].items():
            out.setdefault(g, {})[r["sym"]] = d
    return out


# ============================================================================ evaluation of one row / cell
def _eval_window(parts: dict, cfg, a, b, K: int, B_trade: int, B_port: int, hit_target: float,
                 full: bool = True) -> dict:
    """Account and H11 statistics of one window: per tranche always (with the win / loss interval, z, D and the
    consistency flags), per position with intervals when full."""
    acct = _account(parts, cfg, a, b, K)
    pu, tu = _unit_frames(acct, parts)
    A = acct_stats(acct, pu, B=B_port)
    n_tr = len(tu)
    out = {"acct": A, "n_positions": len(pu), "n_tranches": n_tr, "n_grid_units": int(tu.grid.sum()) if n_tr else 0,
           "zec_in_universe": ZEC in parts, "n_zec_positions": int((pu.sym == ZEC).sum()) if len(pu) else 0,
           "n_zec_tranches": int((tu.sym == ZEC).sum()) if n_tr else 0}
    for unit, U in (("tranche", tu), ("position", pu)):
        st = unit_stats(U)
        if unit == "tranche" or full:
            which = ("hit", "winloss", "gt7_won", "ge3_profit") if full else ("winloss",)
            iv = unit_intervals(U, B_trade, which=which)
        else:
            iv = {}
        cons = consistency(st, iv, A, n_tr, hit_target) if iv else {}
        z = z_scores(st, iv, A, n_tr, hit_target) if iv else {}
        out[unit] = {"st": st, "iv": iv, "cons": cons, "z": z, "D": distance(z) if z else np.nan}
    bp = pu[~pu.grid] if len(pu) else pu                  # positions per M (not G-A deployments, per sleeve)
    if len(bp):
        out["by_coin_side"] = bp.groupby(["sym", "side"]).size().to_dict()
        adj = bp.ret_adj.to_numpy(float)
        out["mean_ret"] = float(bp.ret.mean())
        out["mean_ret_adj"] = float(np.nanmean(adj)) if np.isfinite(adj).any() else np.nan
    else:
        out["by_coin_side"] = {}
        out["mean_ret"] = out["mean_ret_adj"] = np.nan
    return out


def _ex_zec(parts: dict) -> dict:
    """The same coins without ZEC (choice 21; the account keeps K, so ZEC's slot holds cash)."""
    return {s: c for s, c in parts.items() if s != ZEC}


def _eval_pair(parts: dict, cfg, a, b, K: int, B_trade: int, B_port: int, hit_target: float,
               full: bool = True) -> tuple:
    """(ev, ev without ZEC, ZEC info) of one window (choice 21): the twin is evaluated when ZEC is in the universe and
    the account held a ZEC unit, else it is ev itself (the same account)."""
    ev = _eval_window(parts, cfg, a, b, K, B_trade, B_port, hit_target, full=full)
    zi = {k: ev[k] for k in ("zec_in_universe", "n_zec_positions", "n_zec_tranches")}
    if zi["zec_in_universe"] and (zi["n_zec_positions"] or zi["n_zec_tranches"]):
        evx = _eval_window(_ex_zec(parts), cfg, a, b, K, B_trade, B_port, hit_target, full=full)
    else:
        evx = ev
    return ev, evx, zi


def _exzec_cols(evx: dict, unit: str = "tranche") -> dict:
    """The without-ZEC twin's columns beside a row (choice 21)."""
    r = _window_row(evx, unit)
    return {f"{k}_{EXZEC}": r.get(k, np.nan) for k in EXZEC_KEYS}


def _oow_pair(span_parts: list, cfg) -> tuple:
    """(out-of-window results, the same without ZEC) (choice 21); the twin is the same object when no span's account
    held a ZEC position. The twin's rows keep the ZEC flags of the results with ZEC (n_zec_positions = removed)."""
    o = _oow_eval(span_parts, cfg)
    if not o["pooled"]["oow_n_zec_positions"]:
        return o, o
    ox = _oow_eval([(n, _ex_zec(p), a, b, K) for (n, p, a, b, K) in span_parts], cfg)
    for rx, r in zip(ox["spans"], o["spans"]):
        rx.update(zec_in_universe=r["zec_in_universe"], n_zec_positions=r["n_zec_positions"])
    ox["pooled"].update(oow_zec_in_universe=o["pooled"]["oow_zec_in_universe"],
                        oow_n_zec_positions=o["pooled"]["oow_n_zec_positions"])
    return o, ox


def _oow_eval(span_parts: list, cfg) -> dict:
    """Out-of-window results: per span account and trade results, and their pooled summary (choice 2 / 11)."""
    rows = []
    lg, yrs, rets, adj, months = 0.0, 0.0, [], [], []
    nz_all, zin_all = 0, False
    for name, parts, a, b, K in span_parts:
        acct = _account(parts, cfg, a, b, K)
        pu, tu = _unit_frames(acct, parts)
        A = acct_stats(acct, pu, B=0)
        st = unit_stats(pu)
        n_ga = int(pu.grid.sum()) if len(pu) else 0
        nz = int((pu.sym == ZEC).sum()) if len(pu) else 0
        nz_all += nz
        zin_all |= ZEC in parts
        pu = pu[~pu.grid] if len(pu) else pu                 # per-M means: not the G-A deployments (per sleeve)
        r = {"span": name, "start": a, "end": b, "zec_in_universe": ZEC in parts, "n_zec_positions": nz,
             "n_positions": len(pu), "n_ga_deployments": n_ga,
             "n_tranches": len(tu), "multiple": A["multiple"], "cagr": A["cagr"], "log_growth_yr": A["log_growth_yr"],
             "sharpe": A["sharpe"], "max_dd": A["max_dd"], "years": A["years"], "liquidations": A["liquidations"],
             "hit_position": st["hit"], "winloss_position": st["winloss"],
             "mean_ret": float(pu.ret.mean()) if len(pu) else np.nan}
        ra = pu.ret_adj.to_numpy(float) if len(pu) else np.zeros(0)
        if np.isfinite(ra).any():
            mk = bs.month_key(pd.DatetimeIndex(pu.time))
            m, se, _, p, df = bs.cluster_t(ra, mk)
            q = sps.t.ppf(0.975, df) if df and df > 0 else np.nan
            r.update(mean_ret_adj=m, mean_ret_adj_lo=m - q * se, mean_ret_adj_hi=m + q * se)
            adj.append(ra)
            months.append(mk)
        else:
            r.update(mean_ret_adj=np.nan, mean_ret_adj_lo=np.nan, mean_ret_adj_hi=np.nan)
        rows.append(r)
        if np.isfinite(A["years"]):
            lg += math.log(A["multiple"]) if A["multiple"] > 0 else -np.inf
            yrs += A["years"]
        if len(pu):
            rets.append(pu.ret.to_numpy(float))
    allr = np.concatenate(rets) if rets else np.zeros(0)
    pooled = {"oow_log_growth_yr": lg / yrs if yrs > 0 else np.nan,
              "oow_mean_ret": float(allr.mean()) if len(allr) else np.nan, "oow_n_positions": int(len(allr)),
              "oow_years": yrs, "oow_zec_in_universe": bool(zin_all), "oow_n_zec_positions": int(nz_all)}
    if adj:
        m, se, _, p, df = bs.cluster_t(np.concatenate(adj), np.concatenate(months))
        pooled["oow_mean_ret_adj"] = m
    else:
        pooled["oow_mean_ret_adj"] = np.nan
    return {"spans": rows, "pooled": pooled}


def _flat(prefix: str, d: dict) -> dict:
    return {f"{prefix}{k}": v for k, v in d.items()}


def _window_row(ev: dict, unit: str) -> dict:
    """One output row's statistics for a unit of an evaluated window."""
    u = ev[unit]
    A = ev["acct"]
    r = {"n_positions": ev["n_positions"], "n_tranches": ev["n_tranches"], "n_grid_units": ev["n_grid_units"],
         "positions_ratio_490": ev["n_positions"] / POST["positions"],
         "tranches_ratio_1462": ev["n_tranches"] / POST["tranches"]}
    r.update(_flat("", u["st"]))
    r.update(_flat("", u["iv"]))
    r.update({k: A[k] for k in ("multiple", "multiple_lo", "multiple_hi", "peak_multiple", "cagr", "log_growth_yr",
                                "sharpe", "max_dd", "mean_equity", "volume", "turnover", "liquidations",
                                "cross_liquidation", "dead")})
    r["turnover_in_post_range"] = bool(np.isfinite(A["turnover"]) and
                                       POST["turnover_lo"] <= A["turnover"] <= POST["turnover_hi"])
    r.update(_flat("", u["cons"]))
    r.update(_flat("z_", u["z"]))
    r["D"] = u["D"]
    r["mean_ret_all"] = ev["mean_ret"]
    r["mean_ret_adj_all"] = ev["mean_ret_adj"]
    return r


# ============================================================================ F: frequency-matched counts
def run_fcount(out: Path, jobs: int = 4, say=_say_default) -> dict:
    """F's nine W16 tranche counts (choice 16) -> fcount/counts.csv and fcount/F.json, before any return."""
    t0 = time.time()
    a, b = _win("W16")
    cells = [(bars, F_BARS[bars], u) for bars in ("1d", "4h", "1h") for u in F_UNIVERSES]
    specs = []
    for i, (bars, row, u) in enumerate(cells):
        coins, K, masks = universe(cell_ukey(u), a, b)
        for s in coins:
            specs.append({"sym": s, "group": "fcount", "id": f"{i}", "cfg": be.ROWS[row], "start": a, "end": b,
                          "mkey": masks[s], "count_only": True, "order": (i,)})
    mem_before = _CTX["work"]
    _CTX["work"] = None                                     # counts are tiny: keep them in memory
    try:
        R = run_specs(specs, jobs, say, "F counts (tranche table only)")
    finally:
        _CTX["work"] = mem_before
    got = R.get("fcount", {})
    rows = []
    for i, (bars, row, u) in enumerate(cells):
        coins, K, masks = universe(cell_ukey(u), a, b)
        npos = sum(int(got[s][f"{i}"]["n_pos"]) for s in coins)
        ntr = sum(int(got[s][f"{i}"]["n_tr"]) for s in coins)
        rows.append({"cell": i, "bars": bars, "row": row, "universe": u, "universe_key": cell_ukey(u) or "R0",
                     "K": K, "n_coins": len(coins), "n_positions": npos, "n_tranches": ntr,
                     "abs_diff_1462": abs(ntr - POST["tranches"]), "zec_in_universe": ZEC in coins,
                     "n_positions_exZEC": sum(int(got[s][f"{i}"]["n_pos"]) for s in coins if s != ZEC),
                     "n_tranches_exZEC": sum(int(got[s][f"{i}"]["n_tr"]) for s in coins if s != ZEC)})
    C = pd.DataFrame(rows)
    j = int(np.argmin(C.abs_diff_1462.to_numpy()))          # first minimum: the listed order breaks ties
    C["is_F"] = np.arange(len(C)) == j
    d = out / "fcount"
    old = d / "counts.csv"
    if (d / "F.json").exists() and old.exists():               # keep the first write (its time stamp is the evidence)
        P = pd.read_csv(old)
        same = len(P) == len(C) and (P.n_tranches.to_numpy() == C.n_tranches.to_numpy()).all() and \
            (P.row.astype(str).to_numpy() == C.row.astype(str).to_numpy()).all() and \
            (P.universe.astype(str).to_numpy() == C.universe.astype(str).to_numpy()).all()
        if not same:
            raise RuntimeError(f"bb_fit fcount: the W16 tranche counts differ from {old} written earlier; F is fixed "
                               f"by its first write (move the old fcount/ away deliberately to recount)")
        say(f"fcount: counts re-checked, identical to the existing {old} (kept, not rewritten) "
            f"({time.time() - t0:.0f} s)")
        return json.loads((d / "F.json").read_text())
    d.mkdir(parents=True, exist_ok=True)
    C.to_csv(d / "counts.csv", index=False)
    f = C.iloc[j]
    J = {"F": {"bars": f.bars, "row": f.row, "universe": f.universe, "universe_key": f.universe_key,
               "n_tranches": int(f.n_tranches), "n_positions": int(f.n_positions)},
         "F_without_ZEC": {"zec_in_universe": bool(f.zec_in_universe), "n_tranches": int(f.n_tranches_exZEC),
                           "n_positions": int(f.n_positions_exZEC), "note": "beside F only: " + ZEC_NOTE},
         "target_tranches": POST["tranches"], "window": list((a, b)), "rule": "closest W16 tranche count to 1,462; "
         "ties to the first cell in the order R0, S8, S16 x BTC/ETH/SOL, S12 top 6, S12 top 10",
         "written_before_returns": True, "written_at": pd.Timestamp.now(tz="UTC").isoformat(),
         "source": "bb_engine tranche tables (kinds entry, add) of each cell's W16 runs; no return was read",
         "quick": _conf().quick}
    _write_json(d / "F.json", J)
    say(f"fcount: 9 cells counted, F written ({time.time() - t0:.0f} s)")
    return J


def read_f(out: Path) -> dict | None:
    p = out / "fcount" / "F.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("F")


# ============================================================================ luck benchmark
def _luck_unit_row(ev: dict, unit: str) -> dict:
    u = ev[unit]["st"]
    A = ev["acct"]
    return {"n": u["n"], "n_closed": u["n_closed"], "hit": u["hit"], "winloss": u["winloss"], "gt7_won": u["gt7_won"],
            "n_gt7": u["n_gt7"], "ge3_profit": u["ge3_profit"], "ge3_defined": u["ge3_defined"],
            "ge3_profit_gross": u["ge3_profit_gross"],
            "multiple": A["multiple"], "peak_multiple": A["peak_multiple"], "turnover": A["turnover"],
            "liquidations": A["liquidations"], "any_liquidation": A["any_liquidation"]}


def _luck_eval_job(args) -> list:
    """Stage 2 of the luck benchmark: accounts and point statistics of a chunk of versions (and R0 itself)."""
    group, coins, L, a, b, idx, with_r0 = args
    cfg = be.luck_cfg(L)
    files = {s: _get(group, s) for s in coins}
    rows = []
    for v in idx:
        parts = {s: files[s]["versions"][v] for s in coins}
        ev = _eval_window(parts, cfg, a, b, len(coins), 0, 0, POST["hit"], full=False)
        for unit in ("position", "tranche"):
            r = {"version": v, "unit": unit, "shortfall": int(sum(files[s]["short"][v] for s in coins))}
            r.update(_luck_unit_row(ev, unit))
            rows.append(r)
    if with_r0:
        parts = {s: files[s]["r0"] for s in coins}
        ev = _eval_window(parts, replace(be.ROWS["R0"], L=L), a, b, len(coins), 0, 0, POST["hit"], full=False)
        for unit in ("position", "tranche"):
            r = {"version": -1, "unit": unit, "shortfall": 0}
            r.update(_luck_unit_row(ev, unit))
            rows.append(r)
    return rows


def _r0_coin_job(args):
    """R0 at L on one coin and window: its compact and its positions per coin (the luck quota)."""
    sym, L, a, b, group = args
    res = be.simulate_coin(sym, replace(be.ROWS["R0"], L=L), start=a, end=b, hours=_hours(sym),
                           minutes=_minutes(sym), mmr=_mmr(sym), detail=False)
    _audit_ok(res["fills_audit"], f"{sym} R0 L{L}")
    return sym, _compact(sym, res, units=True), int(len(res["trades"]))


def run_luck(out: Path, jobs: int = 4, say=_say_default) -> dict:
    """Luck and tautology benchmark (choices 9, 14)."""
    _require_f(out, "luck")
    t0 = time.time()
    conf, src = _conf(), _src()
    coins = list(src.primary)
    configs = [(L, w) for L in conf.luck_L for w in ("W16", "W16b")]
    # R0 per coin and config (quota and R0's own statistics)
    r0 = {}
    jl = [(s, L, *_win(w), _gname("luck", L, w)) for (L, w) in configs for s in coins]
    for (s, L, a, b, g), (sym, comp, n) in zip(jl, _pmap(_r0_coin_job, jl, jobs)):
        r0[(L, b, sym)] = (comp, n)
    tasks = []
    for (L, w) in configs:
        a, b = _win(w)
        for ci, s in enumerate(coins):
            comp, n = r0[(L, b, s)]
            tasks.append((s, {"group": _gname("luck", L, w), "cfg": be.luck_cfg(L), "start": a, "end": b,
                              "mkey": None, "quota": {1: n}, "n": conf.n_luck, "max_tries": conf.max_tries,
                              "seed": [SEED, int(round(L * 10)), ("W16", "W16b").index(w), ci]}))
    if _CTX["work"] is None:
        raise RuntimeError("run_luck needs a work directory (run() creates one)")
    run_twins(tasks, jobs, say, "luck versions")
    for (L, w) in configs:                                   # R0's own compact beside its random versions
        a, b = _win(w)
        g = _gname("luck", L, w)
        for s in coins:
            d = _get(g, s)
            d["r0"] = r0[(L, b, s)][0]
            _put(g, s, d)
    # stage 2
    jobs2 = []
    for (L, w) in configs:
        a, b = _win(w)
        g = _gname("luck", L, w)
        n = conf.n_luck
        step = max(1, int(math.ceil(n / max(4 * jobs, 1))))
        for k, i0 in enumerate(range(0, n, step)):
            jobs2.append((g, coins, L, a, b, list(range(i0, min(n, i0 + step))), k == 0))
    res2 = _pmap(_luck_eval_job, jobs2, jobs)
    rows = []
    for (g, cs, L, a, b, idx, wr0), rr in zip(jobs2, res2):
        w = "W16" if (a, b) == _win("W16") else "W16b"
        for r in rr:
            r.update(L=L, window=w)
            rows.append(r)
    V = pd.DataFrame(rows)
    d = out / "luck"
    d.mkdir(parents=True, exist_ok=True)
    stats_ = ("n", "hit", "winloss", "multiple", "gt7_won", "ge3_profit", "ge3_profit_gross", "turnover")
    post_val = {"n": None, "hit": POST["hit"], "winloss": POST["winloss"], "multiple": POST["multiple"],
                "gt7_won": POST["gt7_won"], "ge3_profit": POST["ge3_profit"], "ge3_profit_gross": POST["ge3_profit"],
                "turnover": POST["turnover_lo"]}
    summ, dist = [], []
    for (L, w), G in V.groupby(["L", "window"], sort=False):
        ver = G[G.version >= 0]
        r0r = G[G.version < 0]
        vp = ver[ver.unit == "position"]
        s = {"L": L, "window": w, "n_versions": int(vp.version.nunique()),
             "versions_with_shortfall": int((vp.shortfall > 0).sum()), "entries_short": int(vp.shortfall.sum()),
             "share_ge_4.3x": float((vp.multiple >= POST["multiple"]).mean()),
             "share_ge_2x": float((vp.multiple >= 2.0).mean()),
             "share_peak_ge_4.3x": float((vp.peak_multiple >= POST["multiple"]).mean()),
             "share_peak_ge_2x": float((vp.peak_multiple >= 2.0).mean()),
             "share_with_liquidation": float(vp.any_liquidation.astype(bool).mean())}
        r0p = r0r[r0r.unit == "position"]
        if len(r0p):
            s["r0_multiple"] = float(r0p.multiple.iloc[0])
            s["r0_multiple_percentile"] = float((vp.multiple <= s["r0_multiple"]).mean())
            s["r0_liquidations"] = int(r0p.liquidations.iloc[0])
        summ.append(s)
        for unit in ("position", "tranche"):
            vu = ver[ver.unit == unit]
            ru = r0r[r0r.unit == unit]
            for st in stats_:
                x = vu[st].to_numpy(float)
                x = x[np.isfinite(x)]
                rv = float(ru[st].iloc[0]) if len(ru) else np.nan
                pv = post_val[st]
                dist.append({"L": L, "window": w, "unit": unit, "stat": st, "n_defined": int(len(x)),
                             "mean": float(x.mean()) if len(x) else np.nan,
                             "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
                             **{f"p{q:02d}": (float(np.quantile(x, q / 100)) if len(x) else np.nan)
                                for q in (5, 25, 50, 75, 95)},
                             "post": pv if pv is not None else POST["tranches" if unit == "tranche" else "positions"],
                             "share_ge_post": float((x >= (pv if pv is not None else
                                                           POST["tranches" if unit == "tranche" else "positions"]))
                                                    .mean()) if len(x) else np.nan,
                             "r0": rv, "r0_percentile": float((x <= rv).mean()) if len(x) and np.isfinite(rv)
                             else np.nan})
    # months of record: R0's monthly SD per config and on the full sample
    mrows = []
    for (L, w) in configs:
        a, b = _win(w)
        parts = {s: r0[(L, b, s)][0] for s in coins}
        acct = _account(parts, replace(be.ROWS["R0"], L=L), a, b, len(coins))
        sd, nm = _monthly_sd(acct)
        mrows.append({"L": L, "span": w, "start": a, "end": b, "n_months": nm, **months_needed(sd)})
    fa, fb = _full()
    fspecs = [{"sym": s, "group": _gname("luck_full", L), "id": "full", "cfg": replace(be.ROWS["R0"], L=L),
               "start": fa, "end": fb, "mkey": None, "units": False} for L in conf.luck_L for s in coins]
    memf = run_specs(fspecs, jobs, say, "luck: R0 full sample")
    for L in conf.luck_L:
        g = _gname("luck_full", L)
        parts = {s: _load(g, s, memf)["full"] for s in coins}
        acct = _account(parts, replace(be.ROWS["R0"], L=L), fa, fb, len(coins))
        sd, nm = _monthly_sd(acct)
        mrows.append({"L": L, "span": "Full", "start": fa, "end": fb, "n_months": nm, **months_needed(sd)})
    V.to_csv(d / "versions.csv", index=False)
    pd.DataFrame(summ).to_csv(d / "summary.csv", index=False)
    pd.DataFrame(dist).to_csv(d / "distribution.csv", index=False)
    pd.DataFrame(mrows).to_csv(d / "months_needed.csv", index=False)
    _write_json(d / "meta.json", {
        "part": "luck", "n_versions": conf.n_luck, "L": list(conf.luck_L), "windows": {w: _win(w) for w in
                                                                                      ("W16", "W16b")},
        "coins": coins, "rules": "R0's rules with entry_mode='given' (bb_engine.luck_cfg): adds, stops, exits, sizing, "
        "costs and funding are R0's; first entries per coin = R0's count in the window; decision days drawn "
        "sequentially from days the coin was flat (module doc, choice 9)", "seed": SEED,
        "months_needed_formula": months_needed(1.0)["formula"], "quick": conf.quick, "descriptive": NOT_THEIRS})
    say(f"luck: {len(V)} version-unit rows written ({time.time() - t0:.0f} s)")
    return {"summary": summ}


# ============================================================================ H12
def run_h12(out: Path, jobs: int = 4, say=_say_default) -> dict:
    """H12 (choice 15): S11 vs R0 on W16 and the full sample."""
    _require_f(out, "h12")
    t0 = time.time()
    conf, src = _conf(), _src()
    coins = list(src.primary)
    spans = {"W16": _win("W16"), "Full": _full()}
    specs = []
    for w, (a, b) in spans.items():
        for row in ("R0", "S11"):
            for s in coins:
                specs.append({"sym": s, "group": _gname("h12", row), "id": w, "cfg": be.ROWS[row], "start": a,
                              "end": b, "mkey": None, "units": False, "adj": True})
    mem = run_specs(specs, jobs, say, "H12 engine runs")
    rows, diffs = [], []
    for w, (a, b) in spans.items():
        acc, tr = {}, {}
        for row in ("R0", "S11"):
            parts = {s: _load(_gname("h12", row), s, mem)[w] for s in coins}
            cfg = be.ROWS[row]
            a0 = _account(parts, cfg, a, b, len(coins))
            a1 = _account(parts, cfg, a, b, len(coins), idle_tbill=True)
            pu, _ = _unit_frames(a0, parts)
            A = acct_stats(a0, pu, B=0)
            st = unit_stats(pu)
            exc = a1["excess"].to_numpy(float)
            r = {"window": w, "row": row, "start": a, "end": b, "n_positions": len(pu),
                 "n_short": int((pu.side < 0).sum()) if len(pu) else 0, "multiple": A["multiple"], "cagr": A["cagr"],
                 "log_growth_yr": A["log_growth_yr"], "max_dd": A["max_dd"], "liquidations": A["liquidations"],
                 "sharpe_excess_tbill": float(exc.mean() / exc.std(ddof=1) * math.sqrt(365))
                 if len(exc) > 1 and exc.std(ddof=1) > 0 else np.nan,
                 "hit_position": st["hit"], "winloss_position": st["winloss"],
                 "mean_ret": float(pu.ret.mean()) if len(pu) else np.nan}
            if len(pu):
                mk = bs.month_key(pd.DatetimeIndex(pu.time))
                for col in ("ret", "ret_adj"):
                    m, se, _, p, df = bs.cluster_t(pu[col].to_numpy(float), mk)
                    q = sps.t.ppf(0.975, df) if df and df > 0 else np.nan
                    r[f"mean_{col}_cl"], r[f"mean_{col}_lo"], r[f"mean_{col}_hi"] = m, m - q * se, m + q * se
                sh = pu[pu.side < 0]
                r["short_mean_ret"] = float(sh.ret.mean()) if len(sh) else np.nan
                r["short_hit"] = unit_stats(sh)["hit"] if len(sh) else np.nan
            rows.append(r)
            acc[row] = (a0, a1)
            T = pd.concat([p["T"].assign(sym=s) for s, p in parts.items() if len(p["T"])], ignore_index=True) \
                if any(len(p["T"]) for p in parts.values()) else _empty_T()
            tr[row] = T
        for col in ("ret", "ret_adj"):
            D = bs.paired_signal_diff(tr["R0"], tr["S11"], key="signal_day", col=col)
            m, se, t_, p, df = bs.cluster_t(D["diff"].to_numpy(float), D["month"].to_numpy())
            q = sps.t.ppf(0.975, df) if df and df > 0 else np.nan
            diffs.append({"window": w, "comparison": f"per-signal paired diff of {col} (S11 - R0)",
                          "n": int(len(D)), "estimate": m, "se": se, "lo": m - q * se, "hi": m + q * se,
                          "p_one_sided": p})
        ra, rb = acc["S11"][0]["ret"], acc["R0"][0]["ret"]
        bb = bs.block_boot(ra, rb, stat="logdiff", mean_block_days=bs.MONTH_DAYS, B=conf.B_port)
        diffs.append({"window": w, "comparison": "account log growth a year (S11 - R0), idle cash 0%",
                      "n": int(bb["T"]), "estimate": bb["estimate"], "se": bb["se"], "lo": bb["ci95"][0],
                      "hi": bb["ci95"][1], "p_one_sided": bb["p"]})
        ea, eb = acc["S11"][1]["excess"], acc["R0"][1]["excess"]
        bb = bs.block_boot(ea, eb, stat="sharpe_diff", mean_block_days=bs.MONTH_DAYS, B=conf.B_port)
        diffs.append({"window": w, "comparison": "Sharpe difference (S11 - R0), excess over the T-bill",
                      "n": int(bb["T"]), "estimate": bb["estimate"], "se": bb["se"],
                      "lo": bb["ci95"][0] if bb.get("ci95") is not None else np.nan,
                      "hi": bb["ci95"][1] if bb.get("ci95") is not None else np.nan, "p_one_sided": bb["p"]})
    Df = pd.DataFrame(diffs)
    Df["p_expl_bh"] = bs.bh(Df.p_one_sided.to_numpy(float))
    d = out / "h12"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(d / "rows.csv", index=False)
    Df.to_csv(d / "diff.csv", index=False)
    _write_json(d / "meta.json", {"part": "h12", "spans": spans, "coins": coins, "rows": ["R0", "S11"],
                                  "p_values": "exploratory, one-sided for S11 - R0 > 0, BH-adjusted within diff.csv",
                                  "quick": conf.quick, "descriptive": NOT_THEIRS})
    say(f"h12: {len(rows)} rows and {len(Df)} comparisons written ({time.time() - t0:.0f} s)")
    return {"rows": len(rows)}


# ============================================================================ H11b
def _cell_specs(cells: pd.DataFrame, windows=("W16", "W16b")) -> tuple:
    """Stage-1 specs of the cells: every distinct Cfg (cfg id) x span x canonical membership key per coin."""
    keys = sorted({_cfg_key(c) for c in cells.to_dict("records")})
    cid = {k: i for i, k in enumerate(keys)}
    spans = []
    for w in windows:
        a, b = _win(w)
        spans.append((w, a, b, True))
        for i, (oa, ob) in enumerate(_oow(w)):
            spans.append((f"{w}_oow{i}", oa, ob, False))
    need = {}                                            # (cfg id, span) -> {sym: {mkeys}}
    for c in cells.to_dict("records"):
        k = cid[_cfg_key(c)]
        uk = cell_ukey(c["universe"])
        for (sp, a, b, units) in spans:
            coins, K, masks = universe(uk, a, b)
            for s in coins:
                need.setdefault((k, sp), {}).setdefault(s, set()).add(masks[s])
    cfgs = {cid[k]: cell_cfg(dict(zip(("bars", "bb_n", "bb_k", "near_high", "direction", "adds", "exits"), k)))
            for k in keys}
    spd = {sp: (a, b, units) for (sp, a, b, units) in spans}
    specs = []
    for (k, sp), by in need.items():
        a, b, units = spd[sp]
        for s, mks in by.items():
            for mk in mks:
                specs.append({"sym": s, "group": f"h11b_c{k:03d}", "id": f"{sp}|{mk}", "cfg": cfgs[k], "start": a,
                              "end": b, "mkey": mk, "units": units, "adj": False, "order": (k, sp, str(mk))})
    return specs, cid, cfgs


def _cell_job(args) -> list:
    """Stage 2 of H11b for one cell (and of a set cell's L = 5 / grid variants): per window the per-tranche
    statistics, z, D, consistency, per-coin side counts and the out-of-window results."""
    cell, group, cfg, windows, B_trade, B_port, hit_target, mem, oow = args
    uk = cell_ukey(cell["universe"])
    get = _loader(group, mem)
    out = []
    for w in windows:
        a, b = _win(w)
        coins, K, masks = universe(uk, a, b)
        parts = {s: get(s)[f"{w}|{masks[s]}"] for s in coins}
        ev, evx, zi = _eval_pair(parts, cfg, a, b, K, B_trade, B_port, hit_target, full=False)
        r = dict(cell)
        r.update(window=w, K=K, n_coins=len(coins))
        r.update(_window_row(ev, "tranche"))
        pst = ev["position"]["st"]
        r.update(hit_position=pst["hit"], winloss_position=pst["winloss"], gt7_won_position=pst["gt7_won"],
                 ge3_profit_position=pst["ge3_profit"])
        r["by_coin_side"] = json.dumps({f"{s}|{sd}": int(n) for (s, sd), n in ev["by_coin_side"].items()})
        r.update(zi)
        r.update(_exzec_cols(evx))
        if oow:
            sp = []
            for i, (oa, ob) in enumerate(_oow(w)):
                cs, Ko, mo = universe(uk, oa, ob)
                sp.append((f"{w}_oow{i}", {s: get(s)[f"{w}_oow{i}|{mo[s]}"] for s in cs}, oa, ob, Ko))
            o, ox = _oow_pair(sp, cfg)
            r.update(o["pooled"])
            r["oow_spans"] = json.dumps(_js(o["spans"]))
            r.update({f"{k}_{EXZEC}": ox["pooled"][k] for k in OOW_EXZEC_KEYS})
        out.append(r)
    return out


def _twin_eval_job(args) -> list:
    """Stage 2 of the decoys of one (cell, window): accounts, per-tranche statistics, D and consistency of each twin."""
    cell, group, cfg, w, n, B_trade, B_port, kind, mem = args
    uk = cell_ukey(cell["universe"])
    a, b = _win(w)
    coins, K, masks = universe(uk, a, b)
    files = {}
    for s in coins:
        try:
            files[s] = _load(group, s, mem)
        except (FileNotFoundError, KeyError):
            continue                                     # a coin without positions in the cell has no twins
    rows = []
    for v in range(n):
        parts = {s: files[s]["versions"][v] if s in files else _empty_comp() for s in coins}
        ev, evx, zi = _eval_pair(parts, replace(cfg, entry_mode="given"), a, b, K, B_trade, B_port, POST["hit"],
                                 full=False)
        r = {"cell": cell["cell"], "window": w, "twin": v, "group": kind, "of_random_cell": "random" in kind,
             "of_set_cell": "set" in kind, "shortfall": int(sum(files[s]["short"][v] for s in files))}
        r.update(_window_row(ev, "tranche"))
        r.update(zi)
        r.update(_exzec_cols(evx))
        rows.append(r)
    return rows


def _spearman_rows(C: pd.DataFrame, windows) -> pd.DataFrame:
    """The H11b Spearman table (choice 11): rank correlation between D and out-of-window log growth per window, over
    every cell (D = inf ranks last) and over the cells with finite D, with ZEC and (where a cell's account held ZEC
    in the window or out of it) without ZEC; two-sided p-values labelled exploratory and Benjamini-Hochberg adjusted
    within this table (Multiplicity)."""
    rows = []
    for w in windows:
        Cw = C[C.window == w]
        zec = bool(len(Cw) and (("n_zec_tranches" in Cw and (Cw.n_zec_tranches > 0).any())
                                or ("oow_n_zec_positions" in Cw and (Cw.oow_n_zec_positions > 0).any())))
        groups = [("all", "D", "oow_log_growth_yr")] + ([(EXZEC, f"D_{EXZEC}", f"oow_log_growth_yr_{EXZEC}")]
                                                          if zec else [])
        for grp, dc, oc in groups:
            Dv = Cw[dc].to_numpy(float) if dc in Cw else np.full(len(Cw), np.nan)
            oo = Cw[oc].to_numpy(float) if oc in Cw else np.full(len(Cw), np.nan)
            for subset, sel in (("all_cells", np.ones(len(Cw), bool)), ("finite_D", np.isfinite(Dv))):
                x, y = Dv[sel], oo[sel]
                ok = ~np.isnan(x) & ~np.isnan(y)
                rho = p = np.nan
                if ok.sum() > 2:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")      # a constant input gives NaN, reported as such
                        res = sps.spearmanr(x[ok], y[ok])
                    rho, p = float(res.statistic), float(res.pvalue)
                rows.append({"window": w, "group": grp, "subset": subset, "n": int(ok.sum()), "rho": rho,
                             "p_exploratory": p})
    SP = pd.DataFrame(rows, columns=["window", "group", "subset", "n", "rho", "p_exploratory"])
    SP["p_bh"] = bs.bh(SP.p_exploratory.to_numpy(float)) if len(SP) else []
    SP["label"] = SPEARMAN_LABEL
    return SP


def primary_written(out) -> tuple:
    """(ok, why): every primary result is written ("H11b: Run only after every primary result has been written to
    results_bb/"), by bb_replica.primary_status, the runner's and the report's own check: primary/tests.json holds
    all 12 bb_tests.TESTS and none carries an error."""
    from analysis_2026 import bb_replica                     # lazy: bb_replica imports bb_fit lazily too
    st = bb_replica.primary_status(Path(out))
    return bool(st.get("ok")), str(st.get("why", ""))


def _require_f(out: Path, part: str) -> None:
    """F's nine counts must be on disk before this part reads any return (F: "the engine writes the nine counts to
    results_bb/ before any return is read"); run() runs fcount first when they are missing."""
    if read_f(out) is None:
        raise PermissionError(f"bb_fit {part}: {out / 'fcount' / 'F.json'} not found; F's counts are written before "
                              f"any return is read (bb_fit.run runs fcount first)")


def run_h11b(out: Path, jobs: int = 4, force: bool = False, say=_say_default) -> dict:
    """H11b: the 648-cell labelled fit (choices 7-11, 21)."""
    if not force:
        ok, why = primary_written(out)
        if not ok:
            raise PermissionError(f"bb_fit h11b: refused - {why}. H11b runs only after every primary result has been "
                                  f"written (use --force for self-tests only)")
    _require_f(out, "h11b")
    t0 = time.time()
    conf = _conf()
    allc = h11b_cells()
    cells = allc if conf.h11b_cells is None else allc[allc.cell.isin(list(conf.h11b_cells))].reset_index(drop=True)
    windows = ("W16", "W16b")
    specs, cid, cfgs = _cell_specs(cells, windows)
    mem = run_specs(specs, jobs, say, "H11b engine runs")
    memv = mem or None
    jl = []
    for c in cells.to_dict("records"):
        k = cid[_cfg_key(c)]
        jl.append((c, f"h11b_c{k:03d}", cfgs[k], windows, conf.B_trade, conf.B_port, POST["hit"], memv, True))
    t1 = time.time()
    res = _pmap(_cell_job, jl, jobs)
    C = pd.DataFrame([r for rr in res for r in rr])
    say(f"  H11b cells evaluated: {len(C)} cell-windows ({time.time() - t1:.0f} s)")
    # identified set per window
    summ = {}
    C["in_set"] = False
    C[f"in_set_{EXZEC}"] = False
    thr = {}
    for w in windows:
        m = C.window == w
        mask, dmin, th = identified_set(C.loc[m, "D"].to_numpy(float))
        C.loc[m, "in_set"] = mask
        thr[w] = (dmin, th)                                  # the twin without ZEC is judged on the same threshold
        C.loc[m, f"in_set_{EXZEC}"] = bool(np.isfinite(th)) & (C.loc[m, f"D_{EXZEC}"].to_numpy(float) <= th)
    # decoys: 50 random cells + every set cell, per window
    rnd = decoy_cells(None if conf.h11b_cells is None else cells.cell.to_numpy(), conf.n_decoy_cells)
    dtasks, dkeys = [], []
    for w in windows:
        a, b = _win(w)
        setc = set(C.loc[(C.window == w) & C.in_set, "cell"].astype(int))
        rset = {int(x) for x in rnd}
        for c_ in sorted(rset | setc):                        # each (cell, window) gets its twins once (choice 10)
            kind = ("random+set" if c_ in setc else "random") if c_ in rset else "set"
            c = cells[cells.cell == c_].iloc[0].to_dict()
            row = C[(C.window == w) & (C.cell == c_)].iloc[0]
            bcs = json.loads(row.by_coin_side)
            coins, K, masks = universe(cell_ukey(c["universe"]), a, b)
            k = cid[_cfg_key(c)]
            g = f"dec_c{c_}_{w}"
            dkeys.append((c, g, cfgs[k], w, kind))
            for ci, s in enumerate(coins):
                q = {sd: int(bcs.get(f"{s}|{sd}", 0)) for sd in (1, -1)}
                if sum(q.values()) == 0:
                    continue
                dtasks.append((s, {"group": g, "cfg": replace(cfgs[k], entry_mode="given"), "start": a, "end": b,
                                   "mkey": masks[s], "quota": q, "n": conf.n_twins, "max_tries": conf.max_tries,
                                   "seed": [SEED, int(c_), windows.index(w), ci]}))
    dtasks.sort(key=lambda t: t[0])
    memd = run_twins(dtasks, jobs, say, "H11b decoys") or None
    t2 = time.time()
    dres = _pmap(_twin_eval_job, [(c, g, cfg, w, conf.n_twins, conf.B_trade, conf.B_port, kind, memd)
                                  for (c, g, cfg, w, kind) in dkeys], jobs)
    Dc = pd.DataFrame([r for rr in dres for r in rr])
    say(f"  H11b decoys evaluated: {len(Dc)} twins ({time.time() - t2:.0f} s)")
    if len(Dc):
        Dc["in_set"] = [bool(np.isfinite(thr[w][1]) and d <= thr[w][1]) for w, d in zip(Dc.window, Dc.D)]
        Dc[f"in_set_{EXZEC}"] = [bool(np.isfinite(thr[w][1]) and d <= thr[w][1])
                                 for w, d in zip(Dc.window, Dc[f"D_{EXZEC}"])]
    # identified-set cells at L = 5 and with G-A / G-B
    xspecs, xjobs = [], []
    for w in windows:
        a, b = _win(w)
        for c_ in sorted(set(C.loc[(C.window == w) & C.in_set, "cell"].astype(int))):
            c = cells[cells.cell == c_].iloc[0].to_dict()
            coins, K, masks = universe(cell_ukey(c["universe"]), a, b)
            base = cell_cfg(c)
            for var, cfg, grid in (("L5", cell_cfg(c, L=5.0), None), ("G-A", base, "GA"), ("G-B", base, "GB")):
                g = f"ext_c{c_}_{var}_{w}"
                for s in coins:
                    xspecs.append({"sym": s, "group": g, "id": f"{w}|{masks[s]}", "cfg": cfg, "start": a, "end": b,
                                   "mkey": masks[s], "units": True, "adj": False, "grid": grid})
                xjobs.append(({**c, "variant": var}, g, cfg, (w,), conf.B_trade, conf.B_port,
                              POST["hit_grid"] if grid else POST["hit"], None, False))
    X = pd.DataFrame()
    if xspecs:
        memx = run_specs(xspecs, jobs, say, "H11b set extras") or None
        xjobs = [j[:7] + (memx,) + j[8:] for j in xjobs]
        X = pd.DataFrame([r for rr in _pmap(_cell_job, xjobs, jobs) for r in rr])
    # summaries per window
    SP = _spearman_rows(C, windows)

    def _sp(w, grp):
        G = SP[(SP.window == w) & (SP.group == grp)]
        if not len(G):
            return None
        return {r.subset: {"rho": r.rho, "p_exploratory": r.p_exploratory, "p_bh": r.p_bh, "n": int(r.n)}
                for r in G.itertuples()}
    for w in windows:
        Cw = C[C.window == w]
        dmin, th = thr[w]
        S = Cw[Cw.in_set]
        dw = Dc[Dc.window == w] if len(Dc) else Dc
        share_c = float(Cw.in_set.mean()) if len(Cw) else np.nan
        share_d = float(dw.in_set.mean()) if len(dw) else np.nan
        rd = reading_rule(share_c, share_d, S)
        best = Cw.loc[Cw.D.idxmin()] if np.isfinite(Cw.D).any() else None
        grid_best = {}
        if len(X):
            for c_ in S.cell.astype(int):
                Dn = float(Cw.loc[Cw.cell == c_, "D"].iloc[0])
                xa = X[(X.cell == c_) & (X.window == w) & (X.variant == "G-A")]
                xb = X[(X.cell == c_) & (X.window == w) & (X.variant == "G-B")]
                cand = {"none": Dn, "G-A": float(xa.D.iloc[0]) if len(xa) else np.inf,
                        "G-B": float(xb.D.iloc[0]) if len(xb) else np.inf}
                grid_best[int(c_)] = min(cand, key=lambda k: cand[k])
        oo = Cw.oow_log_growth_yr.to_numpy(float) if "oow_log_growth_yr" in Cw else np.full(len(Cw), np.nan)
        med = float(np.nanmedian(oo)) if np.isfinite(oo).any() else np.nan
        fin = np.isfinite(Cw.D.to_numpy(float))
        Sx = Cw[Cw[f"in_set_{EXZEC}"].astype(bool)]
        dx = Cw[f"D_{EXZEC}"].to_numpy(float)
        bx = Cw.iloc[int(np.argmin(np.where(np.isfinite(dx), dx, np.inf)))] if np.isfinite(dx).any() else None
        ox = Cw[f"oow_log_growth_yr_{EXZEC}"].to_numpy(float) if f"oow_log_growth_yr_{EXZEC}" in Cw else \
            np.full(len(Cw), np.nan)
        zec_summary = {
            "note": ZEC_NOTE + "; a cell's twin without ZEC is in_set_exZEC when its D_exZEC is within this window's "
                               "threshold (D_min of the cells with ZEC + chi2_0.95(6))",
            "n_cells_zec_in_universe": int(Cw.zec_in_universe.astype(bool).sum()),
            "n_cells_zec_traded": int((Cw.n_zec_tranches > 0).sum()),
            "best_cell_exZEC": None if bx is None else {**{k: bx[k] for k in ("cell", "bars", "bb_n", "bb_k",
                                                                               "near_high", "adds", "exits",
                                                                               "universe", "direction")},
                                                         "D_exZEC": bx[f"D_{EXZEC}"]},
            "set_cells_exZEC": [int(x) for x in Sx.cell], "share_cells_in_set_exZEC": float(Sx.shape[0] / len(Cw))
            if len(Cw) else np.nan,
            "share_decoys_in_set_exZEC": float(dw[f"in_set_{EXZEC}"].mean()) if len(dw) else np.nan,
            "set_cells_not_in_set_without_zec": [int(x) for x in S.cell[~S[f"in_set_{EXZEC}"].astype(bool)]],
            "set_oow_log_growth_yr_exZEC": [float(x) for x in S[f"oow_log_growth_yr_{EXZEC}"]]
            if len(S) and f"oow_log_growth_yr_{EXZEC}" in S else [],
            "median_cell_oow_log_growth_yr_exZEC": float(np.nanmedian(ox)) if np.isfinite(ox).any() else np.nan}
        summ[w] = {
            "D_min": dmin, "threshold": th, "chi2_95_k": CHI2_95, "k": K_D, "n_cells": int(len(Cw)),
            "n_cells_finite_D": int(fin.sum()),
            "best_cell": None if best is None else {k: best[k] for k in ("cell", "bars", "bb_n", "bb_k", "near_high",
                                                                          "adds", "exits", "universe", "direction",
                                                                          "D")},
            "set_cells": [int(x) for x in S.cell], "share_cells_in_set": share_c,
            "share_decoys_in_set": share_d,
            "share_decoys_in_set_random": float(dw[dw.of_random_cell].in_set.mean())
            if len(dw) and dw.of_random_cell.any() else np.nan,
            "share_decoys_in_set_setcells": float(dw[dw.of_set_cell].in_set.mean())
            if len(dw) and dw.of_set_cell.any() else np.nan,
            "n_decoys": int(len(dw)),
            "agreement": {"bars": bool(len(S) and S.bars.nunique() == 1),
                          "universe": bool(len(S) and S.universe.nunique() == 1),
                          "direction": bool(len(S) and S.direction.nunique() == 1),
                          "grid": bool(len(grid_best) and len(set(grid_best.values())) == 1),
                          "grid_best_by_cell": grid_best},
            "reading": rd,
            "oow": {"median_cell_log_growth_yr": med,
                    "set_log_growth_yr": [float(x) for x in S.oow_log_growth_yr] if len(S) and
                    "oow_log_growth_yr" in S else [],
                    "set_median_log_growth_yr": float(np.nanmedian(S.oow_log_growth_yr)) if len(S) else np.nan,
                    "median_cell_mean_ret": float(np.nanmedian(Cw.oow_mean_ret)) if "oow_mean_ret" in Cw else np.nan,
                    "set_mean_ret": [float(x) for x in S.oow_mean_ret] if len(S) else []},
            "spearman_D_vs_oow_log_growth": _sp(w, "all"),
            "spearman_D_vs_oow_log_growth_exZEC": _sp(w, EXZEC),
            "spearman_p_values": SPEARMAN_LABEL,
            "exZEC": zec_summary}
    d = out / "h11b"
    d.mkdir(parents=True, exist_ok=True)
    C.to_csv(d / "cells.csv", index=False)
    Dc.to_csv(d / "decoys.csv", index=False)
    X.to_csv(d / "set_extras.csv", index=False)
    SP.to_csv(d / "spearman.csv", index=False)
    _write_json(d / "summary.json", summ)
    _write_json(d / "meta.json", {
        "part": "h11b", "n_cells": int(len(cells)), "subset": conf.h11b_cells is not None, "decoy_cells": rnd,
        "n_twins": conf.n_twins, "D_stats": D_STATS, "k": K_D, "chi2_95": CHI2_95, "windows": {w: _win(w)
                                                                                         for w in windows},
        "oow": {w: _oow(w) for w in windows}, "post": POST, "label": "a rule set consistent with the post (never "
        "their strategy)", "p_values": SPEARMAN_LABEL, "zec": ZEC_NOTE + " (cells.csv, decoys.csv and "
        "set_extras.csv: zec_in_universe, n_zec_*, *_exZEC, in_set_exZEC; summary.json: exZEC)",
        "quick": conf.quick, "descriptive": NOT_THEIRS})
    say(f"h11b: {len(C)} cell-windows, {len(Dc)} decoys, {len(X)} set extras written ({time.time() - t0:.0f} s)")
    return summ


# ============================================================================ H11
def _row_defs(rows, F: dict | None) -> dict:
    """name -> (Cfg, universe key, grid kind)."""
    out = {}
    for r in rows:
        out[r] = (be.ROWS[r], _row_ukey(r), None)
    if F:
        out["F"] = (be.ROWS[F_BARS[F["bars"]]], cell_ukey(F["universe"]), None)
    for name, g in GRID_ROWS.items():
        out[name] = (be.ROWS["R0"], None, g)
    return out


def _row_spans(name: str, w: str, grid) -> list:
    """(span name, start, end, units) of a row's window and out-of-window spans (grid rows clipped, choice 2)."""
    a, b = _win(w)
    out = [(w, a, b, True)]
    gf = bd._utc(_grid_from())
    for i, (oa, ob) in enumerate(_oow(w)):
        if grid:
            if bd._utc_end(ob) < gf:
                out.append((f"{w}_oow{i}", oa, ob, None))         # no 1-minute data: not available
                continue
            oa = max(oa, _grid_from()) if bd._utc(oa) < gf else oa
        out.append((f"{w}_oow{i}", oa, ob, False))
    return out


def _h11_row_job(args) -> dict:
    name, cfg, uk, grid, B_trade, B_port, mem = args
    group = _gname("h11", name)
    get = _loader(group, mem)
    res = {"rows": [], "oow": []}
    for w in ("W16", "W16b"):
        spans = _row_spans(name, w, grid)
        sp0, a, b, _ = spans[0]
        coins, K, masks = universe(uk, a, b)
        parts = {s: get(s)[f"{sp0}|{masks[s]}"] for s in coins}
        tgt = POST["hit_grid"] if grid else POST["hit"]
        ev, evx, zi = _eval_pair(parts, cfg, a, b, K, B_trade, B_port, tgt, full=True)
        groups = [("all", ev, len(coins))] + ([(EXZEC, evx, len(coins) - 1)] if zi["zec_in_universe"] else [])
        for gname, e, nc in groups:                           # the row with ZEC, and beside it the row without
            for unit in ("tranche", "position"):
                r = {"row": name, "window": w, "group": gname, "unit": unit, "K": K, "n_coins": nc,
                     "grid": grid or "", **zi}
                r.update(_window_row(e, unit))
                if grid:
                    c48 = consistency(e[unit]["st"], e[unit]["iv"], e["acct"], e["n_tranches"], POST["hit"])
                    r["consistent_vs_48.7"] = c48["consistent"]
                    r["ok_hit_vs_48.7"] = c48["ok_hit"]
                res["rows"].append(r)
        sp = []
        for (spn, oa, ob, units) in spans[1:]:
            if units is None:
                res["oow"].append({"row": name, "window": w, "group": "all", "span": spn, "start": oa, "end": ob,
                                   "note": "not available: no 1-minute data for the grid in this span"})
                continue
            cs, Ko, mo = universe(uk, oa, ob)
            sp.append((spn, {s: get(s)[f"{spn}|{mo[s]}"] for s in cs}, oa, ob, Ko))
        if sp:
            o, ox = _oow_pair(sp, cfg)
            ogroups = [("all", o)] + ([(EXZEC, ox)] if o["pooled"]["oow_zec_in_universe"] else [])
            for gname, oo in ogroups:
                for r in oo["spans"]:
                    res["oow"].append({"row": name, "window": w, "group": gname, **r})
                res["oow"].append({"row": name, "window": w, "group": gname, "span": "pooled", **oo["pooled"]})
        else:
            res["oow"].append({"row": name, "window": w, "group": "all", "span": "not available (no 1-minute data)"})
    return res


def _syn_units(T: pd.DataFrame, tr: pd.DataFrame, grid_rows: pd.DataFrame | None = None) -> tuple:
    """Synthetic units in sleeve units at constant size (choice 12): (positions, tranches) frames with ret, pnl,
    hold_h, open_at_end."""
    if len(T):
        U = tranche_units(T, tr)
        L = T.set_index("pos").L_used
        pu = pd.DataFrame({"ret": T.ret.to_numpy(float), "pnl": T.ret.to_numpy(float) * T.L_used.to_numpy(float),
                           "hold_h": T.hold_h.to_numpy(float), "open_at_end": T.open_at_end.astype(bool).to_numpy()})
        tu = pd.DataFrame({"ret": U.ret.to_numpy(float),
                           "pnl": U.ret.to_numpy(float) * L.reindex(U.pos).to_numpy(float),
                           "hold_h": U.hold_h.to_numpy(float), "open_at_end": U.open_at_end.astype(bool).to_numpy()})
    else:
        pu = tu = pd.DataFrame({"ret": [], "pnl": [], "hold_h": [], "open_at_end": []})
    return pu, tu


def _syn_job(args) -> dict:
    """One martingale coin of the controls' engine series under every distinct H11 row Cfg."""
    i, cfgs, n_hours, sigma = args
    df = be._gbm_hours(n_hours, sigma, SEED + i)
    sym = f"SYN{i}"
    out = {}
    for name, cfg in cfgs.items():
        r = be.simulate_coin(sym, cfg, hours=df, mmr=0.005, detail=False)
        _audit_ok(r["fills_audit"], f"synthetic {sym} {name}")
        out[name] = _syn_units(r["trades"], r["tranches"])
    be.clear_cache()
    return out


def _syn_grid_job(args) -> dict:
    """One coin of the controls' grid series (bb_grid's martingale G-A control): R0, R0 + G-A, R0 + G-B units."""
    i, days, warm, sigma_day = args
    n = (warm + days) * 1440
    start = pd.Timestamp("2010-01-04", tz="UTC")
    M = bg._gbm_minutes(n, sigma_day / math.sqrt(1440.0), SEED + 7919 * i, start)
    H = bg._hours_for(M)
    Dd = bd.bars_from_hours(H, "1d", "sig")
    w0 = start + pd.Timedelta(days=warm)
    w1 = (start + pd.Timedelta(days=warm + days - 1)).strftime("%Y-%m-%d")
    sym = f"SYNG{i}"
    r0 = be.simulate_coin(sym, be.ROWS["R0"], start=w0, end=w1, hours=H, minutes=M, mmr=0.005, detail=False)
    _audit_ok(r0["fills_audit"], f"synthetic grid {sym} R0")
    ga = bg.grid_ga(sym, r0["trades"], daily_bars=Dd, start=w0, end=w1, minutes=M, hours=H, mmr=0.005, tick=0.001)
    _audit_ok(ga["fills_audit"], f"synthetic {sym} G-A")
    gb = bg.grid_gb(sym, r0, start=w0, end=w1, minutes=M, hours=H, mmr=0.005, tick=0.001)
    _audit_ok(gb["fills_audit"], f"synthetic {sym} G-B")
    out = {}
    for name, comp in (("R0+G-A", _ga_compact(sym, r0, ga, True, False)),
                       ("R0+G-B", _gb_compact(sym, r0, gb, True, False))):
        T, U = comp["T"], comp["U"]
        L = T.set_index("pos").L_used.astype(float)
        pu = pd.DataFrame({"ret": T.ret.to_numpy(float), "pnl": T.ret.to_numpy(float) * T.L_used.to_numpy(float),
                           "hold_h": T.hold_h.to_numpy(float), "open_at_end": T.open_at_end.astype(bool).to_numpy()})
        tu = pd.DataFrame({"ret": U.ret.to_numpy(float),
                           "pnl": U.ret.to_numpy(float) * L.reindex(U.pos).to_numpy(float),
                           "hold_h": U.hold_h.to_numpy(float), "open_at_end": U.open_at_end.astype(bool).to_numpy()})
        out[name] = (pu, tu)
    be.clear_cache()
    return out


def _synthetic(rows: dict, jobs: int, say) -> pd.DataFrame:
    """Driftless synthetic values of every H11 row (choice 12)."""
    conf = _conf()
    t0 = time.time()
    syn_cfg = {}
    for name, (cfg, uk, grid) in rows.items():
        if grid:
            continue
        c = cfg
        if name in ("S19",) or uk is not None:
            c = be.ROWS["R0"] if name not in ("F",) else cfg
        syn_cfg[name] = replace(c, rule11=True)
    distinct = {}
    for name, c in syn_cfg.items():
        distinct.setdefault(c, []).append(name)
    cfgs = {f"c{i}": c for i, c in enumerate(distinct)}
    n_hours = int(conf.syn_years * 365 * 24)                 # as bb_engine._martingale / bb_controls
    res = _pmap(_syn_job, [(i, cfgs, n_hours, conf.syn_sigma) for i in range(conf.syn_coins)], jobs)
    grid_res = []
    if any(g for (_, _, g) in rows.values()) and conf.syn_grid_coins > 0:
        grid_res = _pmap(_syn_grid_job, [(i, conf.syn_grid_days, conf.syn_grid_warm, conf.syn_grid_sigma_day)
                                         for i in range(conf.syn_grid_coins)], jobs)
    out = []

    def _row(name, pu, tu, series):
        for unit, U in (("position", pu), ("tranche", tu)):
            st = unit_stats(U)
            out.append({"row": name, "unit": unit, "series": series, "n": st["n"], "n_closed": st["n_closed"],
                        "hit": st["hit"], "winloss_sleeve": st["winloss"], "n_gt7": st["n_gt7"],
                        "gt7_won": st["gt7_won"], "ge3_profit": st["ge3_profit"], "ge3_defined": st["ge3_defined"],
                        "ge3_profit_gross": st["ge3_profit_gross"], "total_pnl_closed": st["total_pnl_closed"]})

    for key, c in cfgs.items():
        pu = pd.concat([r[key][0] for r in res], ignore_index=True)
        tu = pd.concat([r[key][1] for r in res], ignore_index=True)
        for name in distinct[c]:
            _row(name, pu, tu, f"bb_engine._gbm_hours martingale, sigma {conf.syn_sigma}/h, {conf.syn_coins} coins x "
                               f"{conf.syn_years} y, seeds {SEED}+i")
    for name in GRID_ROWS:
        if grid_res and name in rows:
            pu = pd.concat([r[name][0] for r in grid_res], ignore_index=True)
            tu = pd.concat([r[name][1] for r in grid_res], ignore_index=True)
            _row(name, pu, tu, f"bb_grid martingale 1-minute GBM, {conf.syn_grid_sigma_day}/day, "
                               f"{conf.syn_grid_coins} coins x {conf.syn_grid_days} d, seeds {SEED}+7919i")
    say(f"  H11 driftless synthetic reference: {len(cfgs)} rule sets on {conf.syn_coins} coins, grid rows on "
        f"{conf.syn_grid_coins if grid_res else 0} coins ({time.time() - t0:.0f} s)")
    return pd.DataFrame(out)


def run_h11(out: Path, jobs: int = 4, say=_say_default) -> dict:
    """H11 consistency check (choices 1-6, 12, 13)."""
    t0 = time.time()
    conf = _conf()
    F = read_f(out)
    if F is None:
        say("h11: fcount/F.json not found; running F's counts first")
        run_fcount(out, jobs, say)
        F = read_f(out)
    rows = _row_defs(conf.h11_rows, F)
    specs = []
    for name, (cfg, uk, grid) in rows.items():
        for w in ("W16", "W16b"):
            for (spn, a, b, units) in _row_spans(name, w, grid):
                if units is None:
                    continue
                coins, K, masks = universe(uk, a, b)
                for s in coins:
                    specs.append({"sym": s, "group": _gname("h11", name), "id": f"{spn}|{masks[s]}", "cfg": cfg,
                                  "start": a, "end": b, "mkey": masks[s], "grid": grid,
                                  "detail": cfg.margin == "cross", "adj": True, "units": units})
    mem = run_specs(specs, jobs, say, "H11 engine runs") or None
    t1 = time.time()
    res = _pmap(_h11_row_job, [(n, c, u, g, conf.B_trade, conf.B_port, mem) for n, (c, u, g) in rows.items()], jobs)
    H = pd.DataFrame([r for x in res for r in x["rows"]])
    O = pd.DataFrame([r for x in res for r in x["oow"]])
    say(f"  H11 rows evaluated: {len(H)} row-window-units ({time.time() - t1:.0f} s)")
    # uplift of the grid overlays vs R0 alone
    H["hit_uplift_vs_R0"] = np.nan
    for (w, unit), G in H.groupby(["window", "unit"]):
        base = G[(G.row == "R0") & (G.group == "all")]
        if len(base):
            for name in GRID_ROWS:
                m = (H.window == w) & (H.unit == unit) & (H.row == name) & (H.group == "all")
                H.loc[m, "hit_uplift_vs_R0"] = H.loc[m, "hit"] - float(base.hit.iloc[0])
    H["uplift_target"] = np.where(H.row.isin(list(GRID_ROWS)), POST["uplift"], np.nan)
    # driftless synthetic reference
    Syn = _synthetic(rows, jobs, say)
    for col in ("gt7_won", "ge3_profit", "ge3_profit_gross", "hit"):
        mp = {(r.row, r.unit): getattr(r, col) for r in Syn.itertuples()}
        H[f"syn_{col}"] = [mp.get((r, u), np.nan) for r, u in zip(H.row, H.unit)]
    # the luck benchmark's random-entry distribution (R0, L = 3, same window)
    lp = out / "luck" / "distribution.csv"
    if lp.exists():
        Ld = pd.read_csv(lp)
        Ld = Ld[np.isclose(Ld.L.astype(float), 3.0)]
        for col in ("gt7_won", "ge3_profit", "ge3_profit_gross"):
            for q in ("p05", "p50", "p95"):
                mp = {(r.window, r.unit): getattr(r, q) for r in Ld[Ld.stat == col].itertuples()}
                H[f"luck_{col}_{q}"] = [mp.get((w, u), np.nan) for w, u in zip(H.window, H.unit)]
        luck_note = "R0 at L = 3, same window (luck/distribution.csv)"
    else:
        luck_note = "luck/distribution.csv not found: run the luck part first"
    # consistent variant-windows vs chance (the pre-registered rows, with ZEC; the twins without ZEC beside)
    Ht = H[(H.unit == "tranche") & (H.group == "all")]
    Hx = H[(H.unit == "tranche") & (H.group == EXZEC)]
    n_vw = int(len(Ht))
    n_cons = int(Ht.consistent.sum())
    n_cons_pos = int(H[(H.unit == "position") & (H.group == "all")].consistent.sum())
    dp = out / "h11b" / "decoys.csv"
    chance = {"note": "h11b/decoys.csv not found: run h11b first"}
    if dp.exists():
        Dd = pd.read_csv(dp)
        if len(Dd) and "consistent" in Dd:
            sh = float(Dd.consistent.astype(bool).mean())
            chance = {"share_decoys_consistent": sh, "n_decoys": int(len(Dd)), "expected_consistent": sh * n_vw,
                      "by_window": {w: {"share": float(G.consistent.astype(bool).mean()),
                                        "expected": float(G.consistent.astype(bool).mean())
                                        * int((Ht.window == w).sum())} for w, G in Dd.groupby("window")}}
    H["label"] = np.where(H.consistent.astype(bool), "consistent: a fitted subset; its out-of-window results are the "
                          "only evidence about it (never 'their strategy')", "")
    d = out / "h11"
    d.mkdir(parents=True, exist_ok=True)
    H.to_csv(d / "h11.csv", index=False)
    O.to_csv(d / "oow.csv", index=False)
    Syn.to_csv(d / "synthetic.csv", index=False)
    summ = {"n_variant_windows": n_vw, "n_consistent_tranche_rule": n_cons, "n_consistent_position_rule": n_cons_pos,
            "consistent": [f"{r.row} {r.window}" for r in Ht[Ht.consistent.astype(bool)].itertuples()],
            "different_trading_frequency": int((Ht.status == "different trading frequency").sum()),
            "inconsistent_and_different_frequency": int((Ht.status == "inconsistent (also different trading frequency)").sum()),
            "expected_by_chance": chance, "F": F, "luck_beside": luck_note,
            "consistent_rows_note": "consistent rows are a fitted subset whose out-of-window results are the only "
                                    "evidence about them; a match is never cited as evidence that a variant works",
            "exZEC": {"note": ZEC_NOTE + "; h11.csv / oow.csv rows with group 'exZEC' sit beside the row-windows "
                              "whose universe holds ZEC (zec_in_universe); the counts above are on the rows with ZEC",
                      "row_windows_with_zec": [f"{r.row} {r.window}" for r in Hx.itertuples()],
                      "n_consistent_tranche_rule_exZEC": int(Hx.consistent.sum()),
                      "consistent_exZEC": [f"{r.row} {r.window}" for r in Hx[Hx.consistent.astype(bool)].itertuples()]}}
    _write_json(d / "summary.json", summ)
    _write_json(d / "meta.json", {
        "part": "h11", "rows": list(rows), "windows": {w: _win(w) for w in ("W16", "W16b")},
        "oow": {w: _oow(w) for w in ("W16", "W16b")}, "post": POST, "count_band": [COUNT_LO, COUNT_HI],
        "deciding_unit": "tranche (choice 4)", "B_trade": conf.B_trade, "B_port": conf.B_port, "quick": conf.quick,
        "synthetic": {"coins": conf.syn_coins, "years": conf.syn_years, "sigma_h": conf.syn_sigma,
                      "grid_coins": conf.syn_grid_coins, "grid_days": conf.syn_grid_days},
        "zec": ZEC_NOTE, "units": "positions and tranches the account held (choice 22)", "descriptive": NOT_THEIRS})
    say(f"h11: {len(H)} rows, {len(O)} out-of-window rows written ({time.time() - t0:.0f} s)")
    return summ


# ============================================================================ runner
def _prep_universes(say) -> None:
    """Rank tables (and membership masks) in the parent, so that forked workers inherit them."""
    s = _src()
    if s.injected:
        return
    t0 = time.time()
    for key in ("S12_top3", "S12_top6", "S12_top10", "S12_top10_tradfi"):
        _, pool, k, tradfi = be.ROW_UNIVERSE[key]
        R = _ranks(pool, tradfi)
        for c in sorted({x for x in R.iloc[:, :k].to_numpy().ravel() if isinstance(x, str)}):
            _mask(c, key)
    say(f"  S12 ranks and membership prepared ({time.time() - t0:.0f} s)")


def run(out_dir=RES, which=None, jobs: int = 4, force: bool = False, conf: Conf | None = None, src: Src | None = None,
        say=_say_default) -> dict:
    """Run the parts (default all, in the order fcount -> luck -> h12 -> h11b -> h11). which: list or comma string
    of part names. Ordering (F; H11b): every part that reads a return runs after F's counts are on disk (fcount runs
    first when <out_dir>/fcount/F.json is missing); h11b refuses unless every primary result is written
    (primary_written: all 12 tests in primary/tests.json, none errored), unless force (self-tests only)."""
    out = Path(out_dir)
    if which is None:
        parts = list(PARTS)
    else:
        w = which.split(",") if isinstance(which, str) else list(which)
        w = [x.strip().lower() for x in w if str(x).strip()]
        bad = [x for x in w if x not in PARTS]
        if bad:
            raise ValueError(f"bb_fit: unknown part(s) {bad}; parts are {PARTS}")
        parts = [p for p in PARTS if p in w]
    if "h11b" in parts and not force:
        ok, why = primary_written(out)
        if not ok:
            raise PermissionError(f"bb_fit: refused - {why}. H11b runs only after every primary result has been "
                                  f"written (--force for self-tests only)")
    if "fcount" not in parts and any(p != "fcount" for p in parts) and read_f(out) is None:
        say(f"bb_fit: {out / 'fcount' / 'F.json'} not found; F's nine W16 counts run first (written before any "
            f"return is read)")
        parts = ["fcount"] + parts
    old = dict(_CTX)
    _CTX.update(src=src or Src(), conf=conf or Conf(), ranks={}, masks={}, univ={}, cret={})
    work = Path(tempfile.mkdtemp(prefix="bb_fit_", dir=_conf().tmp))
    _CTX["work"] = work
    t0 = time.time()
    done = {}
    try:
        say(f"bb_fit: parts {parts} -> {out} (jobs {jobs}{', quick sizes' if _conf().quick else ''})")
        _prep_universes(say)
        for p in parts:
            if p == "fcount":
                done[p] = run_fcount(out, jobs, say)
            elif p == "luck":
                done[p] = run_luck(out, jobs, say)
            elif p == "h12":
                done[p] = run_h12(out, jobs, say)
            elif p == "h11b":
                done[p] = run_h11b(out, jobs, force, say)
            elif p == "h11":
                done[p] = run_h11(out, jobs, say)
        say(f"bb_fit: done in {time.time() - t0:.0f} s")
    finally:
        if not _conf().keep_work:
            shutil.rmtree(work, ignore_errors=True)
        _CTX.clear()
        _CTX.update(old)
    return {p: True for p in done}


# ============================================================================ self-test
def _close(a, b, tol=1e-12) -> bool:
    return bool(abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b))))


def _st_units(say) -> None:
    """Per-tranche split: a hand-built three-tranche position (TP half, then a trend exit; funding) against the hand
    computation; engine positions on a synthetic path sum exactly to their returns."""
    t0 = pd.Timestamp("2025-03-03 10:00", tz="UTC")
    p = np.array([100.0, 102.0, 105.0])
    q = (1 / 3) / p
    Q = q.sum()
    cost_open = 0.0007 * (1 / 3) * np.ones(3)
    n_tp, n_x = 0.5 * Q * 115.0, 0.5 * Q * 110.0
    c_tp, c_x = 0.0002 * n_tp, 0.0007 * n_x
    F = 0.001
    hours = np.array([100.0, 90.0, 80.0])
    pbar = 112.5
    gross = q * (pbar - p)
    ret = gross.sum() - cost_open.sum() - c_tp - c_x - F
    times = [t0, t0 + pd.Timedelta("10h"), t0 + pd.Timedelta("20h"), t0 + pd.Timedelta("50h"),
             t0 + pd.Timedelta("100h")]
    tr = pd.DataFrame({"pos": 0, "kind": ["entry", "add", "add", "tp", "exit"], "time": pd.DatetimeIndex(times),
                       "px": [100.0, 102.0, 105.0, 115.0, 110.0], "frac": [1 / 3, 1 / 3, 1 / 3, n_tp, n_x],
                       "cost": [*cost_open, c_tp, c_x]})
    T = pd.DataFrame({"pos": [0], "side": [1], "ret": [ret], "funding": [F], "exit_time": [times[-1]],
                      "open_at_end": [False], "liquidated": [False]})
    U = tranche_units(T, tr)
    w = q * hours / (q * hours).sum()
    want = gross - cost_open - (q / Q) * (c_tp + c_x) - F * w
    assert len(U) == 3 and list(U.k) == [0, 1, 2], U
    assert all(_close(a, b) for a, b in zip(U.ret, want)), (U.ret.tolist(), want)
    assert _close(U.ret.sum(), ret) and U.attrs["max_resid_nonliq"] < 1e-15
    assert np.allclose(U.hold_h, hours)
    vol = position_volume(T, tr)
    assert _close(vol[0], 1.0 + n_tp + n_x), vol
    # a liquidation (zero frac close of the remaining quantity) and a short: tranches still sum to the return
    tr2 = tr.copy()
    tr2.loc[4, ["kind", "frac", "cost", "px"]] = ["liq", 0.0, 0.0, 70.0]
    T2 = T.assign(ret=-0.3, liquidated=True)
    U2 = tranche_units(T2, tr2)
    assert _close(U2.ret.sum(), -0.3)
    assert _close(position_volume(T2, tr2)[0], 1.0 + n_tp + 0.5 * Q * 70.0)
    T3 = T.assign(side=-1, ret=-ret - 2 * (cost_open.sum() + c_tp + c_x + F))
    U3 = tranche_units(T3, tr)
    want3 = -gross - cost_open - (q / Q) * (c_tp + c_x) - F * w
    assert all(_close(a, b) for a, b in zip(U3.ret, want3))
    # engine positions on a synthetic martingale path
    H = be._gbm_hours(6 * 8760, 0.01, SEED)
    for cfg in (be.ROWS["R0"], be.ROWS["S5"], be.ROWS["S10_tp_all"], be.ROWS["S11"], be.ROWS["S16"]):
        r = be.simulate_coin("STU", cfg, hours=H, mmr=0.005, detail=False)
        _audit_ok(r["fills_audit"], "self-test units")
        Tt, trt = r["trades"], r["tranches"]
        Ut = tranche_units(Tt, trt)
        assert len(Ut) == int(Tt.n_tranches.sum()) == int(trt.kind.isin(OPEN_KINDS).sum())
        s = Ut.groupby("pos").ret.sum().reindex(Tt.pos).to_numpy()
        assert np.allclose(s, Tt.ret.to_numpy(), atol=1e-13, rtol=0), np.max(np.abs(s - Tt.ret.to_numpy()))
        assert Ut.attrs["max_resid_nonliq"] < 1e-12, Ut.attrs["max_resid_nonliq"]
        assert (Ut.hold_h >= 0).all() and (position_volume(Tt, trt) > 0).all()
    be.clear_cache()
    say(f"  per-tranche split: hand case exact (3 tranches, TP half, funding; liquidation; short); engine positions "
        f"of R0, S5, S10 all, S11, S16 on a 6-year martingale path sum exactly (max residual "
        f"{Ut.attrs['max_resid_nonliq']:.1e})")


def _st_cross(say) -> None:
    """S3 cross margin and units the account never held (choice 22): a one-hour 45% wick while a full-size position
    is open liquidates the K = 1 cross account. The H11 units then hold only what the account held (the position
    open at the breach, closed there with the account's loss and its pre-breach tranches; nothing entered after the
    breach), and their dollar P&L sums to the account's equity change. Without the wick the units are the engine's
    positions and tranches, unchanged."""
    cfg = be.ROWS["S3_cross"]
    H = be._gbm_hours(3 * 8760, 0.008, 5, start="2021-01-04", drift=2e-4)
    a, b = "2022-01-01", "2023-12-31"
    old = dict(_CTX)
    try:
        _CTX.update(src=Src(hours={"SYX": H}, primary=("SYX",)), conf=Conf(), univ={}, cret={})
        r = be.simulate_coin("SYX", cfg, start=a, end=b, hours=H, mmr=0.005, detail=True)
        _audit_ok(r["fills_audit"], "self-test cross")
        parts = {"SYX": _compact("SYX", r, units=True, adj=True, expo=True)}
        acct = _account(parts, cfg, a, b, 1)
        assert acct["cross_liquidation"] is None
        pu, tu = _unit_frames(acct, parts)
        A = acct["trades"].set_index("pos")
        dE = float(acct["equity"].iloc[-1] - acct["equity"].iloc[0])
        assert len(pu) == len(A) and len(tu) == int(A.n_tranches.sum()) and (pu.M > 0).all()
        assert np.allclose(pu.set_index("pos").pnl.reindex(A.index), A.M * A.ret, rtol=0, atol=1e-12)
        assert _close(pu.pnl.sum(), dE, 1e-9) and _close(tu.pnl.sum(), dE, 1e-9)
        T = r["trades"]
        full = T[(T.n_tranches == 3) & ~T.open_at_end].iloc[0]
        h = H.index.get_indexer([full.exit_time.floor("h") - pd.Timedelta("30h")])[0]
        H2 = H.copy()
        for c in ("low", "sig_low"):
            H2.iloc[h, H2.columns.get_loc(c)] = 0.55 * H2.iloc[h, H2.columns.get_loc("open")]
        be.clear_cache()
        _CTX.update(src=Src(hours={"SYX": H2}, primary=("SYX",)), cret={})
        r2 = be.simulate_coin("SYX", cfg, start=a, end=b, hours=H2, mmr=0.005, detail=True)
        _audit_ok(r2["fills_audit"], "self-test cross (wick)")
        parts2 = {"SYX": _compact("SYX", r2, units=True, adj=True, expo=True)}
        acct2 = _account(parts2, cfg, a, b, 1)
        ct = acct2["cross_liquidation"]
        assert ct is not None and acct2["dead"]
        A2 = acct2["trades"]
        dE2 = float(acct2["equity"].iloc[-1] - acct2["equity"].iloc[0])
        eng_sum = float(A2.pnl_usd[A2.M > 0].sum())
        pu2, tu2 = _unit_frames(acct2, parts2)
        held = A2[A2.M > 0]
        assert len(pu2) == len(held) < len(A2) and (pu2.M > 0).all() and (tu2.M > 0).all()
        assert _close(pu2.pnl.sum(), dE2, 1e-9) and _close(tu2.pnl.sum(), dE2, 1e-9), (pu2.pnl.sum(), dE2)
        assert (pd.DatetimeIndex(pu2.time) <= ct).all() and (pd.DatetimeIndex(tu2.time) <= ct).all()
        bpos = A2.pos[A2.exit_reason.astype(str) == "cross_liq"].to_numpy()
        Bp = pu2[pu2.pos.isin(bpos)]
        assert len(Bp) == len(bpos) >= 1 and Bp.liquidated.all() and not Bp.open_at_end.any()
        assert np.allclose(Bp.hold_h, (ct - pd.DatetimeIndex(Bp.time)) / pd.Timedelta("1h"))
        assert np.allclose(Bp.ret * Bp.M, Bp.pnl) and np.isfinite(Bp.ret_adj).all() and (Bp.vol > 0).all()
        Tb = tu2[tu2.pos.isin(bpos)]
        assert np.allclose(Tb.groupby("pos").pnl.sum().reindex(Bp.pos).to_numpy(), Bp.pnl.to_numpy())
        assert np.allclose(Tb.hold_h, (ct - pd.DatetimeIndex(Tb.time)) / pd.Timedelta("1h"))
        st = unit_stats(pu2)
        assert st["n"] == len(held) and _close(st["hit"], float((pu2.ret > 0).mean()))
    finally:
        be.clear_cache()
        _CTX.clear()
        _CTX.update(old)
    say(f"  S3 cross margin: without a breach the units are the engine's (P&L sums to the account change); with a "
        f"one-hour 45% wick the account is liquidated at {ct:%Y-%m-%d %H:%M} and the units keep the {len(held)} "
        f"position(s) it held ({len(A2) - len(held)} entered after the breach left out), closed at the breach; unit "
        f"P&L = account change {dE2:+.3f} (assemble's per-position P&L {eng_sum:+.3f}, scaled)")


def _st_stats(say) -> None:
    """unit_stats / Wilson / acct_stats on hand tables."""
    U = pd.DataFrame({"ret": [0.1, -0.05, 0.2, -0.1, 0.0, 0.3, -0.2, 0.05],
                      "pnl": [10.0, -5.0, 20.0, -10.0, 0.0, 30.0, -20.0, 5.0],
                      "hold_h": [200.0, 10.0, 80.0, 170.0, 168.0, 72.0, 71.9, 500.0],
                      "open_at_end": [False] * 7 + [True], "time": pd.date_range("2025-01-01", periods=8, freq="10D",
                                                                                tz="UTC")})
    st = unit_stats(U)
    assert st["n"] == 8 and st["n_closed"] == 7 and st["n_open_at_end"] == 1
    assert _close(st["hit"], 3 / 7)
    assert _close(st["winloss"], (60 / 3) / (35 / 3))
    assert st["n_gt7"] == 2 and _close(st["gt7_won"], 0.5)                 # 200 h won, 170 h lost (168 h is not > 168)
    assert st["n_ge3"] == 5 and _close(st["ge3_profit"], (10 + 20 - 10 + 0 + 30) / 25.0)     # 72 h counts, 71.9 h not
    lo, hi = _wilson(5, 10)
    assert abs(lo - 0.236593) < 1e-5 and abs(hi - 0.763407) < 1e-5, (lo, hi)
    idx = pd.date_range("2025-01-01", periods=5, freq="D", tz="UTC")
    acct = {"equity": pd.Series([1.0, 1.1, 1.21, 1.1, 1.32], index=idx),
            "ret": pd.Series([0.1, 0.1, -1 / 11, 0.2], index=idx[:-1]), "liquidations": pd.DataFrame()}
    pu = pd.DataFrame({"vol": [2.0, 3.0], "M": [0.5, 1.0]})
    A = acct_stats(acct, pu, B=0)
    assert _close(A["multiple"], 1.32) and _close(A["mean_equity"], (1 + 1.1 + 1.21 + 1.1) / 4)
    assert _close(A["volume"], 4.0) and _close(A["turnover"], 4.0 / A["mean_equity"])
    assert _close(A["max_dd"], 1 - 1.1 / 1.21)
    # S12 membership as a step function, whatever the index's unit (pandas 3's date_range gives us, the ranks ns)
    m = pd.Series([True, False, True], index=pd.date_range("2024-01-01", periods=3, freq="MS", tz="UTC"))
    when = pd.DatetimeIndex(["2023-12-15", "2024-01-10", "2024-02-29 23:00", "2024-03-02"], tz="UTC")
    for mm in (m, m.set_axis(m.index.as_unit("ns")), m.set_axis(m.index.as_unit("s"))):
        assert _member_values(mm, when).tolist() == [False, True, False, True]
    say("  statistics: hit, win / loss in dollars, > 7-day won share (> 168 h), >= 3-day profit share, Wilson "
        "interval, multiple, turnover and drawdown match hand values; S12 membership steps in any time unit")


def _base_st(n_closed=1000, n_gt7=200, hit=POST["hit"], gt7=POST["gt7_won"], ge3=0.9, defined=True):
    return {"n": n_closed, "n_closed": n_closed, "hit": hit, "winloss": 1.4, "n_gt7": n_gt7, "gt7_won": gt7,
            "ge3_profit": ge3, "ge3_defined": defined}


def _st_consistency(say) -> None:
    """The consistency rule's truth table (choices 4-6)."""
    iv = {"winloss_lo": 1.2, "winloss_hi": 1.6}
    A = {"multiple": 3.0, "multiple_lo": 1.5, "multiple_hi": 6.0}
    se_h = math.sqrt(0.487 * 0.513 / 1000)
    se_7 = math.sqrt(0.75 * 0.25 / 200)
    se_3 = math.sqrt(0.8 * 0.2 / 1000)
    eps = 1e-9
    cases = [  # (description, st, iv, A, n_tranches, expected consistent, expected status, fails_only_on_count)
        ("all at the post", _base_st(), iv, A, 1462, True, "consistent", False),
        ("hit at +2 SE (inside)", _base_st(hit=0.487 + 2 * se_h - eps), iv, A, 1462, True, "consistent", False),
        ("hit beyond +2 SE", _base_st(hit=0.487 + 2 * se_h + 1e-6), iv, A, 1462, False, "inconsistent", False),
        ("hit beyond -2 SE", _base_st(hit=0.487 - 2 * se_h - 1e-6), iv, A, 1462, False, "inconsistent", False),
        ("> 7 d share at -2 SE (inside)", _base_st(gt7=0.75 - 2 * se_7 + eps), iv, A, 1462, True, "consistent",
         False),
        ("> 7 d share beyond -2 SE", _base_st(gt7=0.75 - 2 * se_7 - 1e-6), iv, A, 1462, False, "inconsistent",
         False),
        ("no > 7 d unit", _base_st(n_gt7=0, gt7=np.nan), iv, A, 1462, False, "inconsistent", False),
        ("profit share 99% (one-sided '>80%')", _base_st(ge3=0.99), iv, A, 1462, True, "consistent", False),
        ("profit share at 80% - 2 SE (inside)", _base_st(ge3=0.8 - 2 * se_3 + eps), iv, A, 1462, True,
         "consistent", False),
        ("profit share below 80% - 2 SE", _base_st(ge3=0.8 - 2 * se_3 - 1e-6), iv, A, 1462, False, "inconsistent",
         False),
        ("total P&L <= 0 (share undefined)", _base_st(defined=False), iv, A, 1462, False, "inconsistent", False),
        ("1.4 outside the win / loss interval", _base_st(), {"winloss_lo": 1.41, "winloss_hi": 2.0}, A, 1462, False,
         "inconsistent", False),
        ("no win / loss interval", _base_st(), {"winloss_lo": np.nan, "winloss_hi": np.nan}, A, 1462, False,
         "inconsistent", False),
        ("4.3 outside the multiple interval", _base_st(), iv, {**A, "multiple_hi": 4.29}, 1462, False,
         "inconsistent", False),
        ("count 731 (0.5x, inside)", _base_st(), iv, A, 731, True, "consistent", False),
        ("count 730", _base_st(), iv, A, 730, False, "different trading frequency", True),
        ("count 2924 (2x, inside)", _base_st(), iv, A, 2924, True, "consistent", False),
        ("count 2925", _base_st(), iv, A, 2925, False, "different trading frequency", True),
        ("count 40 and hit off", _base_st(hit=0.2), iv, A, 40, False, "inconsistent (also different trading frequency)",
         False),
    ]
    for name, st, ivv, AA, n, cons, status, only in cases:
        c = consistency(st, ivv, AA, n)
        assert c["consistent"] is cons and c["status"] == status and c["fails_only_on_count"] is only, (name, c)
    c = consistency(_base_st(hit=0.517), iv, A, 1462, hit_target=POST["hit_grid"])
    assert c["consistent"] and not consistency(_base_st(hit=0.517 + 2 * se_h + 0.01), iv, A, 1462,
                                               hit_target=POST["hit_grid"])["consistent"]
    say(f"  consistency rule: {len(cases) + 2} truth-table cases (binomial bands at the row's count, one-sided '>80%', "
        f"intervals, the 0.5x-2x count band, 'different trading frequency', the 51.7% grid target)")


def _st_distance(say) -> None:
    """D's z-scores on planted values, the consistency <=> |z| inside the bands equivalence, the identified set and
    the fixed reading on planted cells."""
    iv = {"winloss_lo": 1.0, "winloss_hi": 1.4}
    A = {"multiple": 2.0, "multiple_lo": 1.0, "multiple_hi": 4.3}
    se_h = math.sqrt(0.487 * 0.513 / 1000)
    z = z_scores(_base_st(hit=0.487 + 2 * se_h, ge3=0.95), {**iv}, {**A}, 2924)
    st = _base_st(hit=0.487 + 2 * se_h, ge3=0.95)
    st["winloss"] = 1.2
    z = z_scores(st, iv, A, 2924)
    assert _close(z["count"], 2.0) and _close(z["hit"], 2.0) and _close(z["winloss"], -Z_IV) \
        and _close(z["multiple"], -Z_IV) and z["gt7_won"] == 0.0 and z["ge3_profit"] == 0.0, z
    assert _close(distance(z), 8.0 + 2 * Z_IV ** 2)
    z0 = z_scores(_base_st(), {"winloss_lo": 1.0, "winloss_hi": 2.0}, {"multiple": 4.3, "multiple_lo": 2.0,
                                                                       "multiple_hi": 9.0}, 1462)
    assert distance(z0) == 0.0, z0
    assert distance(z_scores(_base_st(n_gt7=0, gt7=np.nan), iv, A, 1462)) == np.inf
    assert distance(z_scores(_base_st(defined=False), iv, A, 1462)) == np.inf
    assert z_scores(_base_st(), iv, A, 0)["count"] == -np.inf
    # property: consistent <=> every |z| inside its band (2 for count / binomial; 1.96 for the intervals)
    rng = np.random.default_rng(1)
    agree = 0
    for _ in range(3000):
        n = int(rng.integers(20, 3000))
        n7 = int(rng.integers(0, 300))
        st = {"n": n, "n_closed": n, "hit": float(rng.uniform(0.3, 0.7)), "winloss": float(rng.uniform(0.8, 2.2)),
              "n_gt7": n7, "gt7_won": float(rng.uniform(0.5, 1.0)) if n7 else np.nan,
              "ge3_profit": float(rng.uniform(0.5, 1.1)), "ge3_defined": bool(rng.random() < 0.9)}
        wl0 = st["winloss"]
        ivr = {"winloss_lo": wl0 - float(rng.uniform(0.01, 0.8)), "winloss_hi": wl0 + float(rng.uniform(0.01, 0.8))}
        m = float(np.exp(rng.uniform(-1, 2.5)))
        Ar = {"multiple": m, "multiple_lo": m * float(np.exp(-rng.uniform(0.05, 1.5))),
              "multiple_hi": m * float(np.exp(rng.uniform(0.05, 1.5)))}
        ntr = int(np.exp(rng.uniform(np.log(300), np.log(6000))))
        c = consistency(st, ivr, Ar, ntr)
        zz = z_scores(st, ivr, Ar, ntr)
        edge = {"count": 2.0, "hit": 2.0, "winloss": Z_IV, "multiple": Z_IV, "gt7_won": 2.0, "ge3_profit": 2.0}
        inside = all(np.isfinite(zz[k]) and abs(zz[k]) <= edge[k] + 1e-12 for k in D_STATS)
        assert inside == c["consistent"], (st, ivr, Ar, ntr, zz, c)
        agree += 1
    # identified set and the reading on planted cells
    cells = h11b_cells()
    assert len(cells) == N_CELLS == 648 and cells.cell.tolist() == list(range(648))
    assert len(decoy_cells()) == 50 and len(set(decoy_cells())) == 50
    assert np.array_equal(decoy_cells(), np.sort(np.random.default_rng(SEED).choice(648, 50, replace=False)))
    D = np.full(648, 50.0) + np.arange(648) * 0.01
    planted = [5, 6, 7, 8, 9, 10]
    D[planted] = [0.0, 1.0, 4.0, 8.0, 12.0, 12.5]
    D[[100, 200]] = np.inf
    mask, dmin, thr = identified_set(D)
    assert dmin == 0.0 and _close(thr, CHI2_95) and sorted(np.flatnonzero(mask)) == planted
    S = cells.iloc[planted].copy()
    S["bars"] = "4h"
    S["universe"] = "S12 top 6"
    r = reading_rule(mask.mean(), 0.02, S)
    assert r["identifies"] and r["n_set"] == 6
    assert not reading_rule(mask.mean(), 0.06, S)["identifies"]                        # decoys in the set too often
    S2 = S.copy()
    S2.iloc[0, S2.columns.get_loc("universe")] = "S12 top 10"
    assert not reading_rule(mask.mean(), 0.02, S2)["identifies"]                       # universes disagree
    S3 = S.copy()
    S3.iloc[1, S3.columns.get_loc("bars")] = "1h"
    assert not reading_rule(mask.mean(), 0.02, S3)["identifies"]                       # bars disagree
    D2 = D.copy()
    D2[300:340] = 5.0                                                                  # 46 cells in the set: > 5%
    m2, _, _ = identified_set(D2)
    assert m2.sum() == 46 and not reading_rule(m2.mean(), 0.0, cells[m2].assign(bars="4h", universe="S12 top 6"))[
        "identifies"]
    m3, d3, t3 = identified_set(np.full(10, np.inf))
    assert not m3.any() and np.isnan(d3) and not reading_rule(0.0, 0.0, cells.iloc[[]])["identifies"]
    # planted statistics: a cell exactly at the post has D = 0; one at hit + 1 SE has D = 1 and joins the set
    ivp = {"winloss_lo": 1.0, "winloss_hi": 2.0}
    Ap = {"multiple": 4.3, "multiple_lo": 2.0, "multiple_hi": 9.0}
    Dp = [distance(z_scores(_base_st(hit=0.487 + j * se_h), ivp, Ap, 1462)) for j in (0, 1, 3, 4)]
    assert np.allclose(Dp, [0, 1, 9, 16])
    mp, _, _ = identified_set(np.r_[Dp, 30.0])
    assert mp.tolist() == [True, True, True, False, False]
    say(f"  distance: z-scores and D on planted values; consistent <=> every |z| inside its band on {agree} random "
        f"draws; identified set D <= D_min + {CHI2_95:.2f} and the fixed reading on planted cells (set share, decoy "
        f"share, bars / universe agreement, empty set); the 648 cells and the 50 seeded decoy cells")


def _st_sampler(say) -> None:
    """The flat-day sampler: counts kept, only flat days, R0's entry windows, independence of given entries."""
    H = be._gbm_hours(5 * 8760, 0.008, SEED + 5, start="2019-01-07")
    old = dict(_CTX)
    _CTX.update(src=Src(hours={"SYA": H}, primary=("SYA",)), conf=Conf(), univ={}, cret={})
    try:
        a, b = "2021-01-01", "2023-06-30"
        r0 = be.simulate_coin("SYA", be.ROWS["R0"], start=a, end=b, hours=H, detail=False)
        n = len(r0["trades"])
        assert n >= 5, n
        cfg = be.luck_cfg(3.0)
        times = _decision_times("1d", a, b)
        assert (times.hour == 0).all() and times[0] >= bd._utc(a) and times[-1] <= bd._utc_end(b)
        C = candidate_table("SYA", cfg, a, b, times)
        assert C.attrs["n_runs"] >= 2 and 0 < len(C) <= len(times)
        # each candidate's position equals its own single-entry run
        rng = np.random.default_rng(3)
        for i in rng.choice(len(C), size=min(12, len(C)), replace=False):
            r1 = be.simulate_coin("SYA", cfg, start=a, end=b, given_entries=[C.time.iloc[i]], hours=H, detail=False)
            T1 = r1["trades"]
            assert len(T1) == 1 and T1.entry1_time.iloc[0] == C.entry1_time.iloc[i] and \
                T1.exit_time.iloc[0] == C.exit_time.iloc[i], i
        # draws: count kept, flat at every decision, R0's windows and rule 12
        ny = None
        for v in range(30):
            sel, short = draw_entries(C, {1: n}, rng, 20)
            assert short == 0 and len(sel) == n
            r = be.simulate_coin("SYA", cfg, start=a, end=b, given_entries=_given_frame(sel), hours=H, detail=False)
            _audit_ok(r["fills_audit"], "sampler")
            _check_twin(r, sel, f"version {v}")
            T = r["trades"].sort_values("entry1_time")
            tr = r["tranches"]
            last = tr[tr.kind.isin(CLOSE_KINDS)].groupby("pos").time.max()
            dec = pd.DatetimeIndex(T.signal_known)
            assert (dec.hour == 0).all() and dec.isin(times).all()
            prev_close = last.reindex(T.pos).to_numpy()[:-1]
            assert (_ns(dec[1:]) > _ns(prev_close)).all()                      # flat at each later decision
            assert r["log"]["given_dropped"] == 0
            ny = bd.ny_clock(pd.DatetimeIndex(T.entry1_time))
            assert ny.ny_hour.isin([6, 10]).all() and not ny.ny_weekday.isin([4, 5]).any()
        # an impossible quota: a shortfall, never an overlap
        sel, short = draw_entries(C, {1: 10 * len(C)}, rng, 3)
        assert short > 0 and len(sel) + short == 10 * len(C)
        a_, b_ = sel.a.to_numpy(), sel.b.to_numpy()
        assert (a_[1:] > b_[:-1]).all()
        # long / short quotas (S11-type cell) and a 1-hour cell (bar-size convention)
        cfg_ls = replace(be.ROWS["S11"], entry_mode="given")
        CL = pd.concat([candidate_table("SYA", cfg_ls, a, b, times, side=sd) for sd in (1, -1)], ignore_index=True)
        sel, short = draw_entries(CL, {1: 4, -1: 3}, rng, 20)
        assert short == 0 and (sel.side == 1).sum() == 4 and (sel.side == -1).sum() == 3
        r = be.simulate_coin("SYA", cfg_ls, start=a, end=b, given_entries=_given_frame(sel), hours=H, detail=False)
        _check_twin(r, sel, "long/short version")
        assert sorted(r["trades"].side.tolist()) == sorted(sel.side.tolist())
        cfg_h = replace(be.ROWS["S16"], entry_mode="given")
        a2, b2 = "2022-03-01", "2022-04-30"
        th = _decision_times("1h", a2, b2)
        CH = candidate_table("SYA", cfg_h, a2, b2, th)
        assert CH.attrs["n_runs"] >= 2 and len(CH) > 50
        sel, short = draw_entries(CH, {1: 20}, rng, 20)
        r = be.simulate_coin("SYA", cfg_h, start=a2, end=b2, given_entries=_given_frame(sel), hours=H, detail=False)
        _check_twin(r, sel, "1-hour version")
        assert short == 0 and len(r["trades"]) == 20
    finally:
        be.clear_cache()
        _CTX.clear()
        _CTX.update(old)
    say(f"  sampler: {len(C)} valid of {len(times)} daily decision times ({C.attrs['n_runs']} peeling runs); each "
        f"candidate equals its own single-entry run; 30 draws keep R0's {n} first entries, decide only on flat days "
        f"(no given entry dropped), fill only in the 06:00 / 10:00 New York windows outside Fri / Sat, and the "
        f"engine reproduces each draw; long / short quotas and a 1-hour cell work; an impossible quota leaves a "
        f"shortfall, never an overlap")


def _syn_src(days: int = 520, seed: int = 11) -> Src:
    """Injected synthetic data for the end-to-end self-test: three 1-minute coins (grid overlays) and three hourly
    coins, one of them named ZEC (so that the results without ZEC beside the results with it are exercised), S12
    universes with partial membership, and windows inside the synthetic dates."""
    start = pd.Timestamp("2023-01-02", tz="UTC")
    hours, minutes = {}, {}
    for i, s in enumerate(("SYA", "SYB", "SYC")):
        M = bg._gbm_minutes(days * 1440, 0.03 / math.sqrt(1440.0), seed + i, start)
        minutes[s] = M
        hours[s] = bg._hours_for(M)
    for i, s in enumerate(("SYD", ZEC, "SYF")):            # "ZEC": a path that trades in both windows
        hours[s] = be._gbm_hours(days * 24, 0.01, seed + 10 + i, start=str(start.date()))
    mons = pd.date_range("2023-01-01", periods=days // 28 + 2, freq="MS", tz="UTC")
    alt = pd.Series(np.arange(len(mons)) % 2 == 0, index=mons)
    late = pd.Series(mons >= pd.Timestamp("2024-01-01", tz="UTC"), index=mons)
    allm = pd.Series(True, index=mons)
    unis = {"S12_top3": (["SYA", "SYB", "SYC"], 3, {c: None for c in ("SYA", "SYB", "SYC")}),
            "S12_top6": (["SYA", "SYB", "SYC", "SYD", ZEC], 6, {"SYA": allm, "SYB": allm, "SYC": allm, "SYD": alt,
                                                                 ZEC: late}),
            "S12_top10": (["SYA", "SYB", "SYC", "SYD", ZEC, "SYF"], 10,
                          {"SYA": None, "SYB": None, "SYC": None, "SYD": allm, ZEC: late, "SYF": alt}),
            "S17": (["SYA", "SYB", "SYC", ZEC], 4, {c: None for c in ("SYA", "SYB", "SYC", ZEC)})}
    unis["S12_top10_tradfi"] = unis["S12_top10"]
    return Src(hours=hours, minutes=minutes, universes=unis, primary=("SYA", "SYB", "SYC"),
               windows={"W16": ("2024-02-01", "2024-06-03"), "W16b": ("2023-10-01", "2024-01-31")},
               oow={"W16": (("2023-04-01", "2024-01-31"),),
                    "W16b": (("2023-04-01", "2023-09-30"), ("2024-02-01", "2024-06-03"))},
               full=("2023-04-01", "2024-06-03"), grid_from="2023-04-01",
               tick={s: 0.001 for s in ("SYA", "SYB", "SYC")}, mmr={s: 0.005 for s in hours})


def _st_end_to_end(say, jobs: int = 4) -> None:
    """A tiny run() of every part on injected synthetic data: F's counts are on disk before any account is built
    (bb_engine.assemble is wrapped to check it, in every worker; a part run alone on an empty directory writes them
    first, and a part function called without them refuses) and equal an independent count; every output file is
    written with the expected shapes; h11b refuses without every primary result (no tests.json, a subset, an error);
    results without ZEC sit beside the results with ZEC (F's counts, H11 rows and out-of-window rows, H11b cells,
    decoys and set extras; S17 without ZEC = R0's trades in a four-slot account); H11b's Spearman p-values are
    labelled exploratory and BH-adjusted within their table."""
    src = _syn_src()
    conf = Conf(n_luck=12, n_decoy_cells=3, n_twins=3, B_trade=99, B_port=99,
                h11_rows=("R0", "S8", "S11", "S3_cross", "S12_top6", "S17", "S20"),
                h11b_cells=(0, 1, 155, 235, 255, 365, 431, 647), syn_coins=2, syn_years=3, syn_grid_coins=1,
                syn_grid_days=60, syn_grid_warm=70, quick=True)
    tmp = Path(tempfile.mkdtemp(prefix="bb_fit_st_"))
    real_assemble = be.assemble
    seen = {"root": tmp}

    def guarded(*a, **k):
        root = seen["root"]
        if not (root / "fcount" / "F.json").exists() or not (root / "fcount" / "counts.csv").exists():
            raise AssertionError("an account was assembled before F's counts were written")
        (root / "assemble_called").touch()                                  # proves the guard ran (any process)
        return real_assemble(*a, **k)
    quiet = lambda s: None                                                    # noqa: E731
    try:
        try:
            run(tmp, which=["h11b"], jobs=jobs, conf=conf, src=src, say=quiet)
            raise AssertionError("h11b ran without primary/tests.json")
        except PermissionError:
            pass
        # finding 3 (gates): a subset or errored primary run does not open h11b; all 12 tests do
        from analysis_2026.bb_tests import TESTS
        stub = tmp / "stub"
        (stub / "primary").mkdir(parents=True)
        tj = stub / "primary" / "tests.json"
        tj.write_text(json.dumps({"meta": {}, "tests": {"H1": {"p": 0.5}}}))
        try:
            run(stub, which=["h11b"], jobs=jobs, conf=conf, src=src, say=quiet)
            raise AssertionError("h11b ran after a subset primary run")
        except PermissionError:
            pass
        assert not (stub / "h11b").exists() and not (stub / "fcount").exists()
        tj.write_text(json.dumps({"tests": {**{t: {"p": 0.5} for t in TESTS}, "H3": {"error": "failed"}}}))
        assert not primary_written(stub)[0]
        tj.write_text(json.dumps({"tests": {t: {"p": 0.5} for t in TESTS}}))
        assert primary_written(stub)[0]
        for part, fn in (("luck", run_luck), ("h12", run_h12), ("h11b", lambda o: run_h11b(o, force=True))):
            try:                                                             # part functions refuse without F
                fn(tmp / "nof")
                raise AssertionError(f"{part} ran without F's counts")
            except PermissionError:
                pass
        be.assemble = guarded
        neg = tmp / "neg"                       # h12 alone on an empty directory: F's counts are written first
        seen["root"] = neg
        run(neg, which=["h12"], jobs=jobs, conf=conf, src=src, say=quiet)
        assert (neg / "assemble_called").exists() and (neg / "fcount" / "F.json").exists() and \
            (neg / "h12" / "diff.csv").exists() and not (neg / "luck").exists()
        auto = tmp / "auto"                                                  # h11 alone runs F's counts first
        seen["root"] = auto
        run(auto, which=["h11"], jobs=jobs, conf=replace(conf, h11_rows=("R0",), syn_grid_coins=0), src=src,
            say=quiet)
        assert (auto / "assemble_called").exists() and (auto / "fcount" / "F.json").exists()
        seen["root"] = tmp
        t0 = time.time()
        run(tmp, which=None, jobs=jobs, force=True, conf=conf, src=src, say=quiet)
        secs = time.time() - t0
        be.assemble = real_assemble
        assert (tmp / "assemble_called").exists()
        C = pd.read_csv(tmp / "fcount" / "counts.csv")
        J = json.loads((tmp / "fcount" / "F.json").read_text())
        assert len(C) == 9 and C.is_F.sum() == 1 and J["F"]["n_tranches"] == int(C.n_tranches[C.is_F].iloc[0])
        assert int(C.abs_diff_1462[C.is_F].iloc[0]) == int(C.abs_diff_1462.min())
        # independent count of one cell (S8 x BTC/ETH/SOL)
        a, b = src.windows["W16"]
        n = 0
        for s in src.primary:
            r = be.simulate_coin(s, be.ROWS["S8"], start=a, end=b, hours=src.hours[s], minutes=src.minutes[s],
                                 mmr=0.005, detail=False)
            n += int(r["trades"].n_tranches.sum())
        assert n == int(C[(C.row == "S8") & (C.universe == "BTC/ETH/SOL")].n_tranches.iloc[0])
        # bb_desc reads F's cell from these files
        try:
            from analysis_2026 import bb_desc
            cell, _ = bb_desc.read_f_cell(tmp)
            assert cell == {"bars": J["F"]["bars"], "universe": J["F"]["universe"]}, cell
        except ImportError:
            pass
        H = pd.read_csv(tmp / "h11" / "h11.csv")
        rows = set(H.row)
        assert {"R0", "S8", "S11", "S3_cross", "S12_top6", "S17", "S20", "F", "R0+G-A", "R0+G-B"} <= rows, rows
        Ha, Hz = H[H.group == "all"], H[H.group == EXZEC]
        assert set(H.group) == {"all", EXZEC} and set(H.unit) == {"position", "tranche"}
        assert len(Ha) == len(rows) * 2 * 2 and not Ha.duplicated(["row", "window", "unit"]).any()
        assert H.status.isin(["consistent", "inconsistent", "different trading frequency",
                             "inconsistent (also different trading frequency)"]).all()
        assert H[H.row == "R0+G-A"].n_grid_units.sum() > 0 and H[H.row == "R0+G-B"].n_grid_units.sum() > 0
        O = pd.read_csv(tmp / "h11" / "oow.csv")
        assert set(O.row) == rows and (O[O.group == "all"].span == "pooled").sum() >= len(rows)
        Syn = pd.read_csv(tmp / "h11" / "synthetic.csv")
        assert set(Syn.row) == rows
        S = json.loads((tmp / "h11" / "summary.json").read_text())
        assert S["n_variant_windows"] == len(rows) * 2 and "share_decoys_consistent" in S["expected_by_chance"]
        # finding 1 (ZEC): twins exactly where the row's universe holds ZEC in the window, with the same columns
        zr = {(r.row, r.window) for r in Ha[Ha.zec_in_universe.astype(bool)].itertuples()}
        assert {(r.row, r.window) for r in Hz.itertuples()} == zr and len(Hz) == 2 * len(zr)
        assert {"S12_top6", "S17"} <= {r for r, _ in zr} <= {"S12_top6", "S17", "F"}
        assert not Ha[Ha.row.isin(["R0", "S8", "S11", "S3_cross", "S20", "R0+G-A", "R0+G-B"])].zec_in_universe.any()
        mz = Ha.merge(Hz, on=["row", "window", "unit"], suffixes=("", "_x"))
        assert len(mz) == len(Hz) and (mz.n_tranches_x == mz.n_tranches - mz.n_zec_tranches).all()
        assert (mz.n_zec_tranches > 0).any() and not np.allclose(mz.multiple[mz.n_zec_tranches > 0],
                                                                 mz.multiple_x[mz.n_zec_tranches > 0])
        assert (mz.multiple_x[mz.n_zec_tranches == 0] == mz.multiple[mz.n_zec_tranches == 0]).all()
        a, b = src.windows["W16"]                    # S17 without ZEC = R0's trades on the three in four slots
        rr = {s: be.simulate_coin(s, be.ROWS["R0"], start=a, end=b, hours=src.hours[s], minutes=src.minutes[s],
                                  mmr=0.005, detail=False) for s in src.primary}
        acc = be.assemble({s: {"trades": r["trades"], "daily_mtm": r["daily_mtm"]} for s, r in rr.items()},
                          be.ROWS["R0"], a, b, k_slots=4)
        x17 = Hz[(Hz.row == "S17") & (Hz.window == "W16") & (Hz.unit == "tranche")].iloc[0]
        assert _close(x17.multiple, float(acc["equity"].iloc[-1] / acc["equity"].iloc[0]), 1e-12)
        assert int(x17.n_tranches) == int(acc["trades"].n_tranches.sum()) and int(x17.n_coins) == 3
        Oz = O[O.group == EXZEC]
        assert len(Oz) and Oz.zec_in_universe.astype(bool).any() and set(Oz.row) <= {"S12_top6", "S17", "F"}
        assert "row_windows_with_zec" in S["exZEC"] and len(S["exZEC"]["row_windows_with_zec"]) == len(zr)
        assert {"zec_in_universe", "n_tranches_exZEC"} <= set(C.columns)
        assert C.zec_in_universe[C.universe != "BTC/ETH/SOL"].all() and not C.zec_in_universe[
            C.universe == "BTC/ETH/SOL"].any()
        assert (C.n_tranches_exZEC[C.universe == "BTC/ETH/SOL"] == C.n_tranches[C.universe == "BTC/ETH/SOL"]).all()
        assert (C.n_tranches_exZEC <= C.n_tranches).all() and (C.n_tranches_exZEC < C.n_tranches).any()
        assert J["F"]["n_tranches"] == int(C.n_tranches[C.is_F].iloc[0]) and "F_without_ZEC" in J
        Cb = pd.read_csv(tmp / "h11b" / "cells.csv")
        assert len(Cb) == len(conf.h11b_cells) * 2 and Cb.in_set.any()
        Dc = pd.read_csv(tmp / "h11b" / "decoys.csv")
        assert len(Dc) > 0 and set(Dc.group) <= {"random", "set", "random+set"} and Dc.twin.max() == conf.n_twins - 1
        assert not Dc.duplicated(["cell", "window", "twin"]).any()           # each cell's twins drawn once
        Sb = json.loads((tmp / "h11b" / "summary.json").read_text())
        for w in ("W16", "W16b"):
            assert 0 <= Sb[w]["share_cells_in_set"] <= 1 and isinstance(Sb[w]["reading"]["identifies"], bool)
        X = pd.read_csv(tmp / "h11b" / "set_extras.csv")
        assert set(X.variant) <= {"L5", "G-A", "G-B"} and len(X) > 0
        # finding 1 (ZEC) in H11b: every cell, decoy and set extra carries its value without ZEC, judged on the
        # window's pre-registered threshold; cells without ZEC in the universe are their own twin
        for F_ in (Cb, Dc, X):
            for col in ("zec_in_universe", "n_zec_tranches", f"D_{EXZEC}", f"consistent_{EXZEC}",
                        f"n_tranches_{EXZEC}", f"multiple_{EXZEC}"):
                assert col in F_, col
        assert {f"in_set_{EXZEC}", f"oow_log_growth_yr_{EXZEC}", "oow_n_zec_positions"} <= set(Cb.columns)
        b3 = Cb[Cb.universe == "BTC/ETH/SOL"]
        assert not b3.zec_in_universe.any() and np.array_equal(b3.D.to_numpy(float), b3[f"D_{EXZEC}"].to_numpy(float))
        t10 = Cb[Cb.universe == "S12 top 10"]
        assert t10.zec_in_universe.all() and (t10.n_zec_tranches > 0).any()
        assert (t10[f"n_tranches_{EXZEC}"] == t10.n_tranches - t10.n_zec_tranches).all()
        assert (Cb.oow_n_zec_positions > 0).any()
        for w in ("W16", "W16b"):
            th = float(Sb[w]["threshold"])
            cw, dw_ = Cb[Cb.window == w], Dc[Dc.window == w]
            assert (cw[f"in_set_{EXZEC}"].astype(bool) == (cw[f"D_{EXZEC}"] <= th)).all()
            assert (dw_[f"in_set_{EXZEC}"].astype(bool) == (dw_[f"D_{EXZEC}"] <= th)).all()
            assert "set_cells_exZEC" in Sb[w]["exZEC"] and "exploratory" in Sb[w]["spearman_p_values"]
        # finding 4 (Spearman): exploratory, BH-adjusted within the H11b Spearman table
        SPc = pd.read_csv(tmp / "h11b" / "spearman.csv")
        assert len(SPc) >= 4 and set(SPc.group) == {"all", EXZEC} and SPc.p_exploratory.notna().any()
        assert np.allclose(SPc.p_bh.to_numpy(float), bs.bh(SPc.p_exploratory.to_numpy(float)), equal_nan=True)
        assert SPc.label.str.contains("exploratory").all() and SPc.label.str.contains("Benjamini-Hochberg").all()
        spw = Sb["W16"]["spearman_D_vs_oow_log_growth"]["all_cells"]
        r_ = SPc[(SPc.window == "W16") & (SPc.group == "all") & (SPc.subset == "all_cells")].iloc[0]
        assert set(spw) == {"rho", "p_exploratory", "p_bh", "n"} and _close(float(spw["p_bh"]), r_.p_bh, 1e-12)
        assert "exploratory" in json.loads((tmp / "h11b" / "meta.json").read_text())["p_values"]
        L = pd.read_csv(tmp / "luck" / "versions.csv")
        assert len(L) == 2 * 2 * 2 * (conf.n_luck + 1)                         # L x window x unit x (versions + R0)
        Ls = pd.read_csv(tmp / "luck" / "summary.csv")
        assert len(Ls) == 4 and (Ls.entries_short == 0).all()
        assert (Ls["share_peak_ge_2x"] >= Ls["share_ge_2x"]).all()
        lp = L[(L.unit == "position") & (L.version >= 0)]
        r0p = L[(L.unit == "position") & (L.version < 0)]
        for (Lv, w), G in lp.groupby(["L", "window"]):
            n0 = int(r0p[(r0p.L == Lv) & (r0p.window == w)].n.iloc[0])
            assert (G.n == n0).all(), (Lv, w)                                  # every version keeps R0's count
        Mn = pd.read_csv(tmp / "luck" / "months_needed.csv")
        assert len(Mn) == 6
        H12 = pd.read_csv(tmp / "h12" / "diff.csv")
        assert len(H12) == 8 and "p_expl_bh" in H12
        # a later fcount re-checks and keeps the first write; changed counts stop it
        mt = (tmp / "fcount" / "F.json").stat().st_mtime_ns
        run(tmp, which=["fcount"], jobs=jobs, conf=conf, src=src, say=quiet)
        assert (tmp / "fcount" / "F.json").stat().st_mtime_ns == mt
        C2 = C.copy()
        C2.loc[0, "n_tranches"] += 1
        C2.to_csv(tmp / "fcount" / "counts.csv", index=False)
        try:
            run(tmp, which=["fcount"], jobs=jobs, conf=conf, src=src, say=quiet)
            raise AssertionError("changed F counts were not detected")
        except RuntimeError:
            pass
    finally:
        be.assemble = real_assemble
        shutil.rmtree(tmp, ignore_errors=True)
    say(f"  end to end on injected synthetic data ({secs:.0f} s, {jobs} workers): F's counts written before any "
        f"account (assemble guarded in every worker; h12 alone writes them first; part functions refuse without "
        f"them) and equal to an independent count; bb_desc reads F; h11 ({len(Ha)} rows incl. F and both grid "
        f"overlays, {len(Hz)} without-ZEC twins beside the {len(zr)} row-windows holding ZEC; S17 without ZEC = R0's "
        f"trades in four slots), h11b (cells, decoys, set extras with their without-ZEC values; Spearman table "
        f"exploratory and BH-adjusted), luck (every version keeps R0's count), h12 written; h11b refused without "
        f"tests.json, after a subset primary run and with an errored test")


def selftest(jobs: int = 4) -> None:
    t0 = time.time()
    say = _say_default
    say("bb_fit self-test")
    _st_stats(say)
    _st_units(say)
    _st_cross(say)
    _st_consistency(say)
    _st_distance(say)
    _st_sampler(say)
    _st_end_to_end(say, jobs)
    say(f"bb_fit self-test passed in {time.time() - t0:.0f} s")


# ============================================================================ CLI
def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m analysis_2026.bb_fit", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "selftest"])
    ap.add_argument("--out", default=str(RES), help="results root (default analysis_2026/results_bb)")
    ap.add_argument("--which", default=None, help=f"comma-separated subset of {','.join(PARTS)}")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="run h11b before every primary result is written (self-tests "
                                                         "only)")
    ap.add_argument("--tmp", default=None, help="parent directory of the temporary work directory")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest(a.jobs)
        return 0
    try:
        run(a.out, which=a.which, jobs=a.jobs, force=a.force, conf=Conf(tmp=a.tmp))
    except PermissionError as e:
        print(f"bb_fit: REFUSED - {e}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
