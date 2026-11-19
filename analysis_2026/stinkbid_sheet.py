"""
The level sheet of the stink-bid study: the deliverable of analysis_2026/STINKBID_PREREG.md §13 (FROZEN 2026-11-18,
commit 72ac2a4) with the fixed sentences of §11, the levels of §6.2 (M2: L = floor(P0 exp(-k sigma)) on the tick,
k = 6, 8, 10) and the adopted reviews that shaped it (R5 MoneyLine column, R8 fresh price / order diff / test order,
R9 column order and footer, R10 HYPE note, R14 depth trade-off, S11 chart levels by closed testing, S14 overdispersed
fill odds, V10 numbers from F3, V14 round-number advice on the exchange route only, V15 Robinhood ticks and order
sizes). Contract: research_notes/Stink bids/build_spec.md, "stinkbid_sheet.py". Levels come from stinkbid_levels,
data from stinkbid_data, the MoneyLine replica from moneyline_ref, and everything the study decided from the runner's
outputs in results_stinkbid/ (none of these modules is edited).

THE SHEET NEVER PLACES, PREVIEWS OR CANCELS ORDERS. It imports no broker library and calls no broker API: it is a list
for the user to enter by hand in the Robinhood app (Git Bash on Windows: ASCII output, comma-separated lists).

    python -m analysis_2026.stinkbid_sheet --coins HYPE,NEAR,SOL --price NEAR=2.41 --price SOL=148.2 --per-rung 1000
    python -m analysis_2026.stinkbid_sheet --coins NEAR,SOL --refresh          # yesterday's closes from the archive
    python -m analysis_2026.stinkbid_sheet --results OUT --cache CACHE         # the default U-C sheet (stage 8)
    python -m analysis_2026.stinkbid_sheet history                             # compact ladder history (run cache)
    python -m analysis_2026.stinkbid_sheet selftest [--no-real]                # synthetic known answers (< 1 min)
  (use `py -3 -m ...` or `python3 -m ...` where `python` is not on the PATH; with no argument at all the sheet prints
  this usage and writes nothing)
  options: --coins A,B,...   coins (default: U-C, the Robinhood-tradable coins with a Binance spot pair; hindsight)
           --price COIN=x    the app's current mid for COIN (repeatable, or COIN=x,COIN2=y); without it the sheet uses
                             the latest Binance daily close and refuses a coin whose close is more than 24 hours old
           --per-rung USD    dollars per rung (default 1,000)      --route mm|ex   market maker (default) | exchange
           --life 7          the weekly routine (the only life with per-coin fill odds, §13)
           --refresh         fetch daily klines after the cached data from the Binance archive (checksum-verified)
           --previous FILE   last week's sheet for the order diff (default: the latest earlier sheet_YYYY-MM-DD.csv)
           --results DIR     the study's results (default analysis_2026/results_stinkbid); the sheet writes DIR/sheet/
           --cache DIR       the runner's engine cache (default data/stinkbid/runs), for the ladder footer
           --catalog FILE    a Robinhood catalog JSON (default: the saved 2026-11-18 catalog, see below)
           --asof TIME       the sheet's clock (UTC; default now)    --force-price   accept a --price more than 2x
                             away from the last Binance close      --no-write   print only (nothing is written, not
                                                                                even the ladder history)

What it prints, per requested coin, and writes to <results>/sheet/sheet_YYYY-MM-DD.csv (one row per rung; columns
1-8 of §13 in this order, after the identification columns and before the order columns), with the text version
sheet_YYYY-MM-DD.txt and the order diff diff_YYYY-MM-DD.csv:
  1 limit_price         the M2 rungs k = 6, 8, 10 floored to Robinhood's min_order_price_increment, delta recomputed
  2 depth_pct, depth_sigma
  3 median_weeks_to_fill, no_fill_within_year   (weekly re-placement, Kaplan-Meier on the coin shrunk to the U-Q1
                        rung; F3, the Robinhood-route proxy)
  4 rh_fill_odds_week (F3, shrunk) with its 95% interval widened by sqrt(phi) and "N fills in E episodes";
    binance_fill_odds_week_upper_bound (F1)
  5 capacity_median_usd, capacity_p10_usd, q_max_usd (= 0.25 x the 10th percentile; "Binance spot book", context
                        only on the market-maker route)
  6 moneyline_now       the replicated pre-October-2026 MoneyLine at the latest close; red adds "a fill here buys
                        against your own trend signal"
  7 large_long_listed   U-Q1 membership this month ("large, long-listed (Binance volume)") with D-H5's descriptive
                        knife rates
  8 only when earned    flip_target R1/2 and "sell at market after 72 h" (H1 PASS under rule M); post-fill outcomes
                        (tests that PASSed); chart-level rows (H4 PASS and Romano-Wolf p below the Holm level, or
                        D10's fill-odds family: "better fill odds at this depth, not a better price"), each an
                        alternative to the M2 rung nearest in depth (replace it, do not add); round-number advice
                        (exchange route, D9); a best rung (depth gradient BH q < 0.10), otherwise the trade-off
                        theta_k and mu*_k of D6
Above the table: the answer (verdicts H2R, H1, H4 and the pre-registered recommendation lines, §11), or "not yet
computed". Below it: the footer of §13 (the ladder sentence, the total cash reserved, the route note, the fixed
sentences of §11 and the D-H5 sentence), the HYPE note when HYPE is requested, the first small test order, and the
order diff (keep / cancel / place for the M2 rungs; the earned chart levels listed apart as alternatives).

Inputs (the runner's output contract, stinkbid_run.py stages report / desc / explore; each file optional: a missing
or stale file makes the items it feeds "not yet computed", and nothing that depends on a verdict is shown; coding
choice 17 says when a file is current):
  <results>/answer.json            the report stage (§11): verdicts, flags (h1_bot_only, binance_only), h4 (methods
                                   with p_rw, holm_level), holm, the numbers of the tests (X, CI, N, G, G*, R),
                                   recommendation, fixed_sentences, descriptive_sentences (the D-H5 sentence)
  <results>/primary/primary.json   the rows beside each headline (F3_1 with its unit, G and G*; V10: post-fill
                                   outcomes shown from F3 first) and each test's cluster unit
  <results>/desc/sheet_coin_rung.csv  per coin (and pooled, coin ALL) and rung, F1 and F3_1: bids, fills, episodes,
                                   rate_shrunk, wilson_lo / wilson_hi (widened by sqrt(phi)), phi, median_wait_weeks,
                                   p_no_fill_year, km_starts, C_p50, C_p10, Q_max
  <results>/desc/d6.csv            D6 per rule and rung (theta_k, mu*_k, their intervals, theta_unit, theta_G,
                                   theta_gstar), read when sheet_inputs.json is not current
  <results>/sheet_inputs.json      the explore stage: d10_family (D10's fill-odds family with D9), depth_gradient_q,
                                   best_rung_allowed, d6, dh5; its copies of the answer (verdicts, flags, h4, ...) are
                                   only checked against answer.json, never used
  <results>/explore/depth_gradient.csv  the slope row (is_gradient) whose sign names the best rung
  <results>/stages/{report,desc,explore}.json  the runner's completion markers (coding choice 17)
  <cache>/fcount/P1__U_C (else outcomes/, else P1__U_Q1; else <results>/sheet/ladder_history.csv): the requested
                                   coins' weekly bids and their F1 / F3 fill minutes (counts only) for the footer
  Robinhood ticks and sizes: analysis_2026/stinkbid_ref/robinhood_pairs_2026-11-18.json (committed), falling back
  to data/stinkbid/ref/currency_pairs.json. Without a catalog the sheet refuses to print any price (exit code 2).
  Daily bars: stinkbid_data.d1 (cache through 2026-11-17), extended by --refresh into data/stinkbid/sheet/d1/.

Exit codes: 0 sheet written with at least one priced coin; 1 every requested coin refused (the sheet and its reasons
are still written); 2 refused as a whole (no catalog, bad arguments such as a malformed --asof, or no arguments at
all: usage only).

Coding choices the pre-registration leaves open (most literal reading; listed in the build report)
 1. Clock and freshness (§13 "or the sheet refuses levels from a close more than 24 hours old"). d0 = the latest UTC
    day with a traded bar on or before yesterday (as of the sheet's clock); the close of d0 is published at d0 + 1 day
    00:00 UTC and is "more than 24 hours old" when the clock is past d0 + 2 days 00:00. With --price COIN=x, P0 = x
    (taken as fresh at the sheet's clock) and sigma30 / ATR14 come from the bars through d0 (stinkbid_levels.inputs_at
    with price=x). Bars ending more than 7 days before yesterday are refused even with --price (sigma30 would belong to
    another placement; --refresh fetches newer bars). A --price more than a factor 2 away from the last close is
    refused as a probable typo (a limit buy above the market fills at once) unless --force-price is given.
 2. Robinhood's tick (§13 item 1, V15). The level is floored directly to the catalog's min_order_price_increment
    (inputs_at(tick=...), so L = floor(P0 exp(-k sigma)) on Robinhood's grid), and delta = ln(P0 / L) / sigma on the
    rounded level. V15 (adopted): when rounding moves the level by more than 0.05 sigma (delta - k > 0.05), the waits
    and fill odds are read at the rounded depth (at_depth): linear interpolation between the two rungs (6, 8, 10)
    that bracket delta, only when both have a value; beyond the outermost rungs, extrapolation with the slope of the
    two nearest rungs (both with a value) at most 1 sigma (EXTRAP); otherwise no value. Probabilities are clipped to
    [0, 1]. The median wait counts a rung whose Kaplan-Meier median is not reached as infinite: at or beyond it the
    wait stays "not reached"; between a rung with a median and a deeper rung without one, nothing is interpolated
    and only the lower bound is printed ("at least" the shallower rung's median: waits rise with depth). The row
    says so. On real ticks this moves 22 of the 222 U-C rungs of 2026-11-17 (e.g. RENDER and TRUMP on a 0.01 tick
    by 0.15-0.25 sigma). Earned chart levels get the same plain-level reading at their own depth, and none when their
    delta is more than 1 sigma outside 6..10.
 3. Fill odds (§13 item 4, S14, V10): the F3_1 rows of desc/sheet_coin_rung.csv: the shrunken estimate
    (n_fill + 52 p_pool) / (n_bids + 52) and its interval as computed there (Wilson on the coin's own bid-weeks with
    the half-width x sqrt(phi), phi = the Pearson dispersion of the rung's yearly counts), with "N fills in E
    episodes"; the F1 row's shrunken estimate is printed as "Binance (upper bound)". On the exchange route F3 is the
    market-maker proxy (a lower bound there) and F1 the upper bound; F4 has no per-coin row in the runner's outputs.
    A coin with no U-Q1 bids at the rung, and HYPE always (§13: "the U-Q1 pooled odds at the same depth"), gets the
    pooled row (coin ALL), labelled.
 4. "Kaplan-Meier, shrunk to the U-Q1 rung" (§13 item 3): w = n / (n + 52) with n the coin's KM starts (its weekly
    bids at the rung), the same 52-week prior as the fill odds; the no-fill chance within a year is
    w S_coin(1 y) + (1 - w) S_rung(1 y) (the one-year survival of the mixture of the two KM curves) and the median
    wait w m_coin + (1 - w) m_rung (an approximation of the mixture's median from the two medians, the only KM
    summaries the runner writes). A coin whose own KM median is not reached gets no shrunk median ("not reached";
    the rung's median is printed beside it); when the U-Q1 rung's median is not reached, a coin without its own
    history reads "not reached" and a coin with its own median "at least" that median. A median is "not reached"
    when its row has Kaplan-Meier starts but no median. Both from F3 (§7: "The sheet's numbers come from F3").
 5. Capacity (§13 item 5): the coin's own F1 fills at the rung (aggTrades where streamed, else C1, as desc computes
    them): median, 10th percentile, Q_max = 0.25 x p10; with no own fill there, the pooled rung's, labelled. On the
    market-maker route Q_max is context only (orders are not capped; a row above Q_max says so); on the exchange
    route the rung's order is capped at Q_max (draft §7.3 "at most Q_max per rung").
 6. Orders (§10.5 K7, V15): quantity = floor(Q / L) on the catalog's quantity increment; below the minimum order size
    there is no order (the row gives the smallest workable size); above the maximum the quantity is split into
    n = ceil(q / max) near-equal orders, each a multiple of the increment within [min, max] (the controls' reference
    coding, stinkbid_controls.rh_orders, uses the same even split, and K7(b) checks this module's rule directly; the
    even split never leaves a remainder below the minimum). Cash reserved = sum of quantity x limit.
 7. MoneyLine now (§13 item 6, R5): moneyline_ref.supertrend with MONEYLINE_PARAMS on the coin's Binance daily bars
    of d0's segment (new segment at a missing day or a > 25% open jump, as stinkbid_data / stinkbid_engine coding
    choice 7), read at d0's close; undefined before ATR10 exists or for a segment shorter than 10 bars; a segment
    shorter than 100 bars is flagged as warming up (moneyline_ref's docstring).
 8. Large, long-listed flag (§13 item 7): stinkbid_data.universes() U_Q1 in the sheet's month (the latest month of
    the table when the month is absent), named "large, long-listed (Binance volume)", never "solid" or "quality";
    D-H5's knife rates as §11's descriptive sentence printed by the runner (answer.json descriptive_sentences, built
    by stinkbid_desc.sentence_dh5: the U-Q1 and 12-month rows and, U-Q2 not being built, "The study did not test a
    real-revenue filter."), else built by stinkbid_desc.sentence_dh5 from sheet_inputs.json's dh5; in column 7 and
    in the footer.
 9. Earned items (§13 item 8; the runner's verdicts, recomputed here from the raw fields of answer.json; shown only
    when the runner's stages report, desc and explore are current and consistent, coding choice 17):
    - flip target: verdict H1 == PASS (rule M) -> R1/2 = ceil(L + (P0 - L) / 2) on Robinhood's tick and "sell at
      market after 72 h"; H1 not PASS with the runner's h1_bot_only flag -> no target and §11's bot sentence;
    - post-fill outcomes: one line per PASSed test, the Robinhood-route proxy (F3_1 beside, primary.json) first and
      the Binance headline beside it (V10), each interval with its cluster unit, G and G* (§12), labelled "a
      Binance-only result" when the runner flags it; H1's and H2R's on every row, H4's on the chart rows it earned
      (when only H4 passed, the M2 rows say so);
    - chart levels: H4 == PASS and the method's Romano-Wolf p_rw < answer h4.holm_level (the Holm level at which H4
      was tested; as stinkbid_run coding choice 11), or the method rejected in D10's family (labelled "better fill
      odds at this depth, not a better price"); each as its own row, an alternative to the M2 rung nearest in depth
      (replace it, do not add; not in the cash total), its waits and odds interpolated from the M2 rungs at its depth
      and labelled so; a method that abstains or lacks data says so;
    - round-number advice: --route ex and D9 rejected in D10's family; a rung whose limit is a multiple of M5's
      minor grid g = 10^(floor(log10 P0) - 1) is advised one tick higher;
    - best rung: the F1 depth gradient's BH q < 0.10 (sheet_inputs depth_gradient_q, with best_rung_allowed): the
      deepest rung (k = 10) when the slope of Delta on k is positive, the shallowest (k = 6) when negative; otherwise
      ("Otherwise each rung shows its trade-off") theta_k and mu*_k of D6 on F3 (F1 beside), their intervals with
      the cluster unit, G and G* of theta_k (mu*_k's interval is carried from theta_k's, stinkbid_stats.mu_star).
10. Order diff (R8): against the most recent sheet_YYYY-MM-DD.csv dated strictly before the sheet (or --previous),
    per coin and M2 row: keep (same limit and quantities), cancel then place (changed), place (new), cancel (gone or
    refused this week: "cancel or keep at your discretion"). A bid that filled during the week is not known to the
    sheet; the diff says "if still open". Earned chart levels are never "place" or "cancel" lines: they are listed
    apart (action "alternative") with the M2 rung each would replace, so the place lines commit exactly the footer's
    "Total cash reserved" (§11: "assume every rung fills on the same day"); last week's alternatives are listed with
    "if you placed it instead of its rung and it is still open, cancel it".
11. Ladder footer (§13 footer, R9): the requested coins' weekly k = 6/8/10 bids of P1 on U-C (Robinhood-tradable
    coins while in Binance's top 100: hindsight), counts only; days with a live bid define the span; N = distinct
    fill days / (span / 365.25); D = the longest run of consecutive live days without a fill; S = the largest share
    of the ladder's live order slots filled on one day (stinkbid_desc.worst_day, the §11 sentence's rule). F3 first,
    F1 beside. The compact history (chains of weekly bids and the fill minutes) is written to
    <results>/sheet/ladder_history.csv whenever the run cache is read (never with --no-write), so the footer also
    works where only the committed results exist.
12. Refresh (draft §15.1 "The sheet refreshes them itself, incrementally"; not required by §13): daily spot klines
    after the cached bars through yesterday, from the Binance archive via fetch_bb_data.klines (checksum-verified),
    cached in data/stinkbid/sheet/d1/; segments continue by the §4.1 rule. M6 / M7 chart levels need hourly and
    futures data through d0 and are reported as not computed on refreshed bars.
13. Life: only the weekly routine (P1, 7-day bids, §13 "if re-placed weekly"); R8's monthly routine has no per-coin
    fill odds in the runner's outputs.
14. Results written in a non-real mode (an injected world) are used for display but bannered as not the study's.
15. HYPE (§5, §13): its levels use its Binance spot daily bars (listed 2026-09-24; enough closes for sigma30), not the
    perpetual index the study's exploratory row uses; its fill odds, waits and capacity are always the U-Q1 pooled
    rung's ("the U-Q1 pooled odds at the same depth"), with the note of §13 printed in its block and in the footer.
16. The first small test order (§13, R8): the deepest rung of the first priced coin not halted for any region, sized
    at about $1 and at least Robinhood's minimum order size; the user cancels it after Robinhood shows it pending.
17. Current results (§14: the sheet is stage 8, after report, desc and explore). With the runner's markers
    (<results>/stages/): answer.json counts only while stages/report.json is complete; the desc outputs only while
    stages/desc.json is complete, in the report's mode and finished after it; the explore outputs (sheet_inputs.json,
    explore/) likewise after desc. A rerun moves the markers of the rerun stage and every later one to stages/stale/
    (stinkbid_run coding choice 1), so their files stop counting. sheet_inputs.json must also match answer.json (the
    same verdicts and mode, and its own "generated" stamp no earlier than answer.json's: the stamps inside the files,
    not file times, which a git checkout does not keep); without markers (a folder the runner did not lay out) only
    this check applies. The answer (verdicts, recommendation, fixed and descriptive sentences, the tests' numbers) comes
    from answer.json alone. Every earned item of §13 item 8 (flip target, post-fill outcomes, chart levels,
    round-number advice, best rung) needs the whole chain report -> desc -> explore current and consistent, so after
    a `report --rerun` they read "not shown" until desc and explore have run again; the sheet says why.
18. Stage 8 of stinkbid_run (§14). The sheet reads and writes the runner's folders: `--results OUT --cache CACHE`
    before the user's sheet arguments on the command line, or in-process run_stage(OUT, CACHE, args, world). A
    --results or --cache among the user's arguments that names other folders is refused (exit 2). Without --coins the
    stage makes the default U-C sheet. An injected world (stinkbid_engine's dict: universe, coins with their 1m / daily
    frames and tick, end; a synthetic world cannot reach the sheet through a subprocess) is priced in-process at its
    end + 12 h on a synthetic catalog of its own ticks, labelled as such; its results are bannered by their mode. A
    bare call with no argument at all prints the usage and writes nothing (exit 2), so the stage passes at least its
    folders.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import shutil
import sys
import time
import warnings
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import moneyline_ref as mlr  # noqa: E402
from analysis_2026 import stinkbid_data as sbd  # noqa: E402
from analysis_2026 import stinkbid_levels as sbl  # noqa: E402

# ============================================================================ constants (prereg section in brackets)
RES = ROOT / "analysis_2026" / "results_stinkbid"
CACHE = ROOT / "data" / "stinkbid" / "runs"
SHEET_DATA = ROOT / "data" / "stinkbid" / "sheet"
CATALOG_PATHS = (ROOT / "analysis_2026" / "stinkbid_ref" / "robinhood_pairs_2026-11-18.json",
                 ROOT / "data" / "stinkbid" / "ref" / "currency_pairs.json")
SCRATCH = Path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/sb_sheet")
HISTORY_FILE = "ladder_history.csv"
HISTORY_RUNS = ("fcount/P1__U_C", "outcomes/P1__U_C", "fcount/P1__U_Q1", "outcomes/P1__U_Q1")

RUNGS = (6.0, 8.0, 10.0)                       # §6.2 / §13: P1's M2 rungs
PRIOR = 52.0                                    # draft §15.1: (n_fill + 52 p_pool) / (n_bids + 52)
FRESH_H = 24.0                                  # §13: a close more than 24 hours old is refused
SIGMA_STALE_D = 7                               # coding choice 1
PRICE_JUMP = 2.0                                # coding choice 1: --price vs the last close (typo guard)
REROUND = 0.05                                  # V15: rounding moving the level by more than 0.05 sigma
EXTRAP = 1.0                                    # coding choice 2: read rung values at most 1 sigma beyond 6..10
LIFE_D = 7                                      # §13: weekly re-placement (P1)
DEFAULT_Q = 1000.0
DAY_M = 1440
WEEK_M = 7 * DAY_M
CHART = (("M4", {"N": 90, "buffer": 0.5}), ("M5b", {}), ("M6", {}), ("M7", {}))      # H4's four methods (§10.3)
CHART_NAMES = {"M4": "below the 90-day low, 0.5 ATR buffer", "M5b": "round number, 0.5 ATR beyond",
               "M6": "90-day volume-profile node", "M7": "estimated long-liquidation band (an estimate)"}
TESTS = ("H2R", "H1", "H4")                     # §11 order
TEST_NAMES = {"H2R": "Rest vs alert (H2R)", "H1": "Flip (H1)", "H4": "Levels (H4)"}
VERDICTS = ("PASS", "NO EDGE", "NO EDGE (HARMS)", "INCONCLUSIVE")
NAN = float("nan")

# ---- fixed texts, verbatim from STINKBID_PREREG.md (the selftest checks each against the file)
HYPE_NOTE = ("HYPE: about 17 months of Binance perpetual data and 2 months of Binance spot. Its only deep-wick day "
             "(2025-10-10) came 13 days before Robinhood listed it. HYPE is a venue token: its value depends on "
             "Hyperliquid's volume and solvency, a risk no price history here can measure (FTT, the token of FTX, fell "
             "97.6%). Not tradable on Robinhood for New York residents.")
ROUTE_NOTE = ("on the default route, the coin's mid must fall about 1% below your price before it fills; a chart touch "
              "is not a fill.")
LADDER = ("Across your whole ladder, expect fills on about {N} days a year; the longest stretch without any fill was "
          "{D} days; on the worst day, {S}% of the ladder filled.")
ML_RED = "a fill here buys against your own trend signal"
D10_LABEL = "better fill odds at this depth, not a better price"
FLIP_STOP = "sell at market after 72 h"
BOT_ONLY = ("the flip worked only for sell orders placed within a minute of the fill, which you cannot do by hand.")
S_DISCOUNT = ("A bid's discount is not a gain by itself. If prices are unpredictable, a bid 30% below the price buys "
              "the same expected value as buying now, minus what the coin earns while you wait; in a crash that gaps "
              "through your price, it buys less. Only a quick rebound after the wick can pay for the wait.")
S_TOGETHER = ("Bids fill together. On the worst day, {S}% of the live bids in the study's main universe filled the "
              "same day. Size the whole ladder as one position you are willing to hold through a further 50-80% "
              "fall.")
S_BOTTOM = ("A fill is not a bottom: {A}% of past fills were 50% or more below the fill price a year later, against "
            "{B}% for random buys of the same coins.")
S_NEWS = ("Coin-specific collapses (LUNA, FTT, OM) look like ordinary wicks on the first day; a resting order cannot "
          "read the news. Cancel a coin's bids on news about the coin itself (a hack, exploit, depeg, delisting or "
          "regulatory action).")
S_ML = ("Most past fills came when the coin's MoneyLine was already red; a fill buys against your own trend signal. "
        "Decide before the fill which rule governs the position.")
S_ML_NOTE = "The sheet uses the replicated pre-October-2026 MoneyLine."
S_CAP = "assume every rung fills on the same day"
TEST_ORDER = ("Before your first routine, place one small bid at the deepest rung and confirm that Robinhood accepts "
              "it and shows it as pending.")
NEVER = ("This sheet never places, previews or cancels orders: it is a list for you to enter by hand in the Robinhood "
         "app.")
RH_PROXY = ("Robinhood fidelity: no Robinhood crypto history exists here, so every Robinhood-route number (F3) is a "
            "proxy.")
NOT_COMPUTED = "not yet computed"


class SheetRefused(RuntimeError):
    """The sheet as a whole refuses (bad arguments, no catalog)."""


class CatalogMissing(SheetRefused):
    """§13: "The sheet refuses to print prices without the saved Robinhood catalog."""


# ============================================================================ small helpers
def _f(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return NAN
    return v


def _fin(x) -> bool:
    return math.isfinite(_f(x))


_UNI = {"σ": "sigma", "δ": "delta", "τ": "tick", "½": "1/2", "≤": "<=", "≥": ">=",
        "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "×": "x",
        "−": "-", "θ": "theta", "μ": "mu", "φ": "phi", "√": "sqrt", "≈": "~",
        "§": "section ", "…": "..."}


def _a(s) -> str:
    """ASCII only (Git Bash on Windows): known symbols spelled out, anything else replaced."""
    s = str(s)
    for k, v in _UNI.items():
        s = s.replace(k, v)
    return s.encode("ascii", "replace").decode("ascii")


def _pct(x, nd: int = 1, sign: bool = False) -> str:
    x = _f(x)
    if not math.isfinite(x):
        return "n/a"
    return f"{100 * x:+.{nd}f}%" if sign else f"{100 * x:.{nd}f}%"


def _pts(x, nd: int = 1) -> str:
    x = _f(x)
    return "n/a" if not math.isfinite(x) else f"{100 * x:+.{nd}f}"


def _usd(x) -> str:
    x = _f(x)
    if not math.isfinite(x):
        return "n/a"
    if abs(x) >= 1e9:
        return f"${x / 1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.2f}M"
    if abs(x) >= 1e4:
        return f"${x / 1e3:.0f}k"
    return f"${x:,.0f}" if abs(x) >= 100 else f"${x:,.2f}"


def _dstr(d: Decimal) -> str:
    """A Decimal as a plain string (no exponent, no trailing zeros)."""
    s = format(d.normalize(), "f")
    return s


def _pstr(d: Decimal, tick: str) -> str:
    """A price on its tick with the tick's decimals (e.g. 2.4270 on 0.0001)."""
    q = Decimal(tick)
    return format(d.quantize(q) if q.as_tuple().exponent < 0 else d, "f")


def _jload(path: Path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _csv(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path) if Path(path).exists() else None
    except (OSError, ValueError, pd.errors.ParserError):
        return None


def _rel(p) -> str:
    p = Path(p)
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def _utc(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _day(t) -> pd.Timestamp:
    """The tz-naive UTC midnight of a timestamp."""
    return _utc(t).tz_localize(None).normalize()


# ============================================================================ Robinhood catalog (§13, V15)
def load_catalog(paths=None) -> pd.DataFrame:
    """The saved read-only Robinhood catalog (2026-11-18): coin, symbol, tradability, tradable, the decimal strings
    price_tick_str, qty_increment_str, min_order_size_str, max_order_size_str, market_orders_only, halted,
    halted_regions. The committed copy first (analysis_2026/stinkbid_ref), then data/stinkbid/ref. Raises
    CatalogMissing when none can be read: the sheet refuses to print prices without Robinhood's tick."""
    paths = [Path(p) for p in (paths or CATALOG_PATHS)]
    path = next((p for p in paths if p.exists()), None)
    if path is None:
        raise CatalogMissing("the saved Robinhood catalog is missing (" + ", ".join(_rel(p) for p in paths) +
                             "): the sheet refuses to print prices without Robinhood's tick and sizes")
    d = _jload(path)
    try:
        rows = [dict(coin=str(x["asset_currency"]).upper(), symbol=x["symbol"], tradability=x["tradability"],
                     tradable=x["tradability"] == "tradable", price_tick_str=str(x["min_order_price_increment"]),
                     qty_increment_str=str(x["min_order_quantity_increment"]),
                     min_order_size_str=str(x["min_order_size"]), max_order_size_str=str(x["max_order_size"]),
                     market_orders_only=bool(x["market_orders_only"]), halted=bool(x["halted"]),
                     halted_regions=" ".join(x.get("halted_regions") or []))
                for x in d["results"]]
        for r in rows:
            for k in ("price_tick_str", "qty_increment_str", "min_order_size_str", "max_order_size_str"):
                if not Decimal(r[k]) > 0:
                    raise ValueError(f"{r['coin']}: {k} = {r[k]}")
    except (TypeError, KeyError, ValueError, InvalidOperation) as e:
        raise CatalogMissing(f"the Robinhood catalog {_rel(path)} cannot be read ({e!r}): the sheet refuses to print "
                             "prices") from None
    if not rows:
        raise CatalogMissing(f"the Robinhood catalog {_rel(path)} is empty: the sheet refuses to print prices")
    cat = pd.DataFrame(rows).sort_values("coin").reset_index(drop=True)
    cat.attrs["path"] = _rel(path)
    cat.attrs["source"] = str((d or {}).get("source", ""))
    return cat


def catalog_row(cat: pd.DataFrame, coin: str):
    """(catalog row, '') or (None, why the sheet does not price this coin on Robinhood)."""
    if coin in sbd.RH_REUSED:
        return None, f"ticker reuse: {sbd.RH_REUSED[coin]}"
    r = cat[cat["coin"] == coin]
    if r.empty:
        return None, "not in the saved Robinhood catalog (2026-11-18)"
    r = r.iloc[0]
    if not bool(r["tradable"]):
        return None, f"not tradable on Robinhood (catalog: {r['tradability']})"
    if bool(r["market_orders_only"]):
        return None, "Robinhood accepts only market orders for this coin (no limit bid is possible)"
    return r, ""


def rh_orders(L: Decimal, Q: float, row) -> tuple[list, str]:
    """The Robinhood orders of one rung (K7, coding choice 6): quantity floor(Q / L) on the quantity increment; below
    the minimum size no order; above the maximum, n = ceil(q / max) near-equal orders, each a multiple of the
    increment within [min, max]. Returns ([Decimal quantities], note)."""
    inc = Decimal(str(row["qty_increment_str"]))
    mn = Decimal(str(row["min_order_size_str"]))
    mx = Decimal(str(row["max_order_size_str"]))
    L = Decimal(L)
    if not (L > 0) or not (Q > 0):
        return [], "no order (no positive limit or size)"
    units = int((Decimal(repr(float(Q))) / L / inc).to_integral_value(rounding=ROUND_FLOOR))
    qty = inc * units
    if units <= 0 or qty < mn:
        need = (mn * L).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        return [], (f"no order: {_dstr(qty)} is below Robinhood's minimum order size {_dstr(mn)}; the smallest order "
                    f"at this limit costs about ${need}")
    mx_units = int((mx / inc).to_integral_value(rounding=ROUND_FLOOR))
    if mx_units < 1:
        return [], f"no order: the catalog's maximum size {_dstr(mx)} is below its quantity increment {_dstr(inc)}"
    n = -(-units // mx_units)
    base, extra = divmod(units, n)
    orders = [inc * (base + 1)] * extra + [inc * base] * (n - extra)
    if sum(orders) != qty or any(o < mn or o > mx for o in orders):          # cannot happen when max >= 2 min
        raise AssertionError(f"order split failed: {qty} into {orders} (min {mn}, max {mx})")
    note = f"split into {n} orders (Robinhood's maximum is {_dstr(mx)} per order)" if n > 1 else ""
    return orders, note


def k7_violations(orders: pd.DataFrame, cat: pd.DataFrame) -> list:
    """K7's order check (§10.5): every order on its coin's price tick and quantity increment, within [min, max]."""
    c = cat.set_index("coin")
    bad = []
    for r in orders.itertuples():
        x = c.loc[r.coin]
        lim, q = Decimal(str(r.limit)), Decimal(str(r.qty))
        if lim % Decimal(x.price_tick_str) != 0:
            bad.append((r.coin, str(lim), str(q), "price off the tick"))
        if q % Decimal(x.qty_increment_str) != 0:
            bad.append((r.coin, str(lim), str(q), "quantity off the increment"))
        if q < Decimal(x.min_order_size_str) or q > Decimal(x.max_order_size_str):
            bad.append((r.coin, str(lim), str(q), "size outside [min, max]"))
    return bad


# ============================================================================ arguments
def parse_prices(items) -> dict:
    """--price COIN=x (repeatable; COIN=x,COIN2=y also accepted) -> {COIN: 'x'} (the typed decimal string)."""
    out = {}
    for it in items or []:
        for part in str(it).split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise SheetRefused(f"--price expects COIN=x (the app's mid), got {part!r}")
            c, v = part.split("=", 1)
            c, v = c.strip().upper(), v.strip().replace("$", "")
            try:
                x = Decimal(v)
            except InvalidOperation:
                raise SheetRefused(f"--price {c}: {v!r} is not a number") from None
            if not c or not x.is_finite() or x <= 0:
                raise SheetRefused(f"--price {part!r}: the price must be a positive number")
            out[_a(c)] = str(x)
    return out


def parse_asof(asof) -> pd.Timestamp:
    """--asof (UTC; a time with an offset is converted; None = now). Anything that is not a date and time refuses
    the sheet as a whole (exit code 2)."""
    if asof is None:
        return pd.Timestamp.now(tz="UTC")
    try:
        t = _utc(asof)
    except (ValueError, TypeError, OverflowError):
        t = pd.NaT
    if pd.isna(t):
        raise SheetRefused(f"--asof {str(asof)!r} is not a date and time (UTC), e.g. '2026-11-18 12:00'")
    return t


def parse_coins(s) -> list:
    out = []
    for x in re.split(r"[,\s]+", str(s or "")):
        x = x.strip().upper()
        if x and x not in out:
            out.append(x)
    return out


REF_DIR = ROOT / "analysis_2026" / "stinkbid_ref"
U_C_FILE = REF_DIR / "u_c_2026-11-18.csv"                 # the U-C list (committed, for clones without data/)
UNIV_RECENT_FILE = REF_DIR / "universes_recent.csv"       # U-Q1 / U-B membership of the last 12 months (committed)


def default_coins(cat: pd.DataFrame) -> list:
    """U-C (§5: the sheet's default list): Robinhood-tradable coins with a Binance USDT spot pair (stinkbid_data);
    on a clone without data/stinkbid (the user's machine), the committed U-C list of the 2026-11-18 catalog
    (stinkbid_ref/u_c_2026-11-18.csv; A2.6); else the catalog's tradable limit-order coins without the excluded
    stablecoins / gold and reused tickers."""
    try:
        return list(sbd.u_c_coins())
    except Exception:
        pass
    try:
        lst = pd.read_csv(U_C_FILE, dtype=str)["coin"].tolist()
        if lst:
            return lst
    except (OSError, ValueError, KeyError):
        pass
    skip = {"USDC", "USDT", "USDG", "PAXG", "DAI", "PYUSD"} | set(sbd.RH_REUSED)
    return [c for c, t, m in zip(cat["coin"], cat["tradable"], cat["market_orders_only"])
            if t and not m and c not in skip]


# ============================================================================ the runner's outputs
CHAIN = ("report", "desc", "explore")           # coding choice 17: the stages whose outputs the sheet reads
EARNED_ITEMS = "flip target, post-fill outcomes, chart levels, round-number advice, best rung"


def _markers(rdir: Path) -> dict | None:
    """The runner's completion markers of report, desc and explore ({stage: marker or None}); None without a stages/
    folder (no stage information: the files are taken as found, coding choice 17)."""
    sd = Path(rdir) / "stages"
    if not sd.is_dir():
        return None
    out = {}
    for st in CHAIN:
        m = _jload(sd / f"{st}.json")
        out[st] = m if isinstance(m, dict) and m.get("complete") is True else None
    return out


def _after(m: dict | None, prev: dict | None) -> bool:
    """Marker m is complete, in prev's mode and finished no earlier than prev (coding choice 17)."""
    return (m is not None and prev is not None and m.get("mode") == prev.get("mode") and
            str(m.get("finished", "")) >= str(prev.get("finished", "")))


def load_results(results_dir) -> dict:
    """What the study decided, from the runner's output contract (module docstring), each file only while it is
    current (coding choice 17): the answer (verdicts, flags, h4, holm, numbers, recommendation, fixed and descriptive
    sentences) from answer.json alone; the desc outputs (fill odds, waits, capacity, D6) while desc is current; the
    explore outputs (sheet_inputs.json's d10_family / depth gradient / d6 / dh5, explore/depth_gradient.csv) only
    when explore is current and sheet_inputs.json was built from the current answer.json. `chain` says whether the
    earned items of §13 item 8 may be shown (and `chain_why` why not). Every file is optional."""
    rdir = Path(results_dir)
    where = _rel(rdir)
    mk = _markers(rdir)
    raw_si, raw_ans = _jload(rdir / "sheet_inputs.json"), _jload(rdir / "answer.json")
    raw_si = raw_si if isinstance(raw_si, dict) else None
    raw_ans = raw_ans if isinstance(raw_ans, dict) else None
    if mk is None:
        rep_ok = desc_ok = exp_ok = True
    else:
        rep_ok = mk["report"] is not None
        desc_ok = rep_ok and _after(mk["desc"], mk["report"])
        exp_ok = desc_ok and _after(mk["explore"], mk["desc"])
    warn = []
    ans = raw_ans if rep_ok else None
    v = (ans or {}).get("verdicts")
    v = v if isinstance(v, dict) and all(v.get(t) in VERDICTS for t in TESTS) else None
    if mk is not None and not (rep_ok and desc_ok and exp_ok):
        miss = [st for st, ok in (("report", rep_ok), ("desc", desc_ok), ("explore", exp_ok)) if not ok]
        warn.append(f"the study's stages {', '.join(miss)} are not complete in {where}"
                    + (" for the current answer" if rep_ok else "") + ": the items they feed read "
                    f"'{NOT_COMPUTED}' and no earned item ({EARNED_ITEMS}) is shown (section 14: the sheet is stage 8)"
                    + ("; answer.json is not used" if raw_ans is not None and not rep_ok else ""))
    # sheet_inputs.json: used only for the explore and desc items, and only when built from the current answer.json
    si, why = None, ""
    if v is None:
        why = f"verdicts {NOT_COMPUTED}"
    elif not (desc_ok and exp_ok):
        why = "the study's stages " + ", ".join(st for st, ok in (("desc", desc_ok), ("explore", exp_ok)) if not ok) \
            + " are not complete for the current answer (section 14: the sheet is stage 8)"
    elif raw_si is None:
        why = "sheet_inputs.json is missing (the explore stage has not run)"
    else:
        bad = []
        if raw_si.get("verdicts") != ans.get("verdicts"):
            bad.append(f"its verdicts {raw_si.get('verdicts')} differ from answer.json's {ans.get('verdicts')}")
        if raw_si.get("mode") and ans.get("mode") and raw_si["mode"] != ans["mode"]:
            bad.append(f"its mode {raw_si['mode']!r} differs from answer.json's {ans['mode']!r}")
        if raw_si.get("generated") and ans.get("generated") and str(raw_si["generated"]) < str(ans["generated"]):
            bad.append(f"it was generated ({raw_si['generated']}) before answer.json ({ans['generated']})")
        if bad:
            why = f"sheet_inputs.json was not built from the current answer.json ({'; '.join(bad)})"
        else:
            si = raw_si
    if v is not None and si is None and (mk is None or (desc_ok and exp_ok)):
        warn.append(f"{where}/{why}: no earned item ({EARNED_ITEMS}) is shown; run the explore stage again")
    chain = si is not None
    prim = _jload(rdir / "primary" / "primary.json") if v is not None else None
    prim = prim if isinstance(prim, dict) else None
    d6 = si.get("d6") if si is not None else None
    d6 = pd.DataFrame(d6) if isinstance(d6, list) and d6 else (_csv(rdir / "desc" / "d6.csv") if desc_ok else None)
    cr = _csv(rdir / "desc" / "sheet_coin_rung.csv") if desc_ok else None
    if cr is not None:
        need = {"coin", "rung", "rule", "bids", "fills", "rate_shrunk", "wilson_lo", "wilson_hi"}
        if not need <= set(cr.columns):
            cr = None
        else:
            cr = cr.assign(coin=cr["coin"].astype(str), rule=cr["rule"].astype(str),
                           rung=pd.to_numeric(cr["rung"], errors="coerce"))
    return dict(dir=rdir, si=si, answer=ans, primary=prim, coin_rung=cr, d6=d6 if d6 is not None and len(d6) else None,
                dg=_csv(rdir / "explore" / "depth_gradient.csv") if chain else None, verdicts=v,
                mode=(ans or raw_ans or raw_si or {}).get("mode"), chain=chain, chain_why=why, warnings=warn,
                stages=mk, desc_ok=desc_ok, explore_ok=exp_ok)


def _gradient(R: dict):
    """(q, slope) of the F1 depth gradient (explore/depth_gradient.csv's is_gradient row; q also from
    sheet_inputs.json)."""
    si = R.get("si") or {}
    q, slope = _f(si.get("depth_gradient_q")), NAN
    dg = R.get("dg")
    if dg is not None and len(dg) and "is_gradient" in dg:
        g = dg[dg["is_gradient"].astype(str).str.lower().isin(("true", "1", "1.0"))]
        if "rule" in g:
            g = g[g["rule"].astype(str) == "F1"]
        if len(g):
            slope = _f(g["estimate"].iloc[0])
            if not math.isfinite(q) and "q_bh" in g:
                q = _f(g["q_bh"].iloc[0])
    return q, slope


def earned(R: dict, route: str = "mm") -> dict:
    """What §13 item 8 shows, from the verdict files (coding choices 9 and 17): the verdicts, flags and H4's methods
    from answer.json, D10 / D9 and the depth gradient from the explore stage's outputs; nothing unless the chain
    report -> desc -> explore is current and consistent (R["chain"]). Pure: no market data."""
    si, ans = R.get("si") or {}, R.get("answer") or {}
    v = R.get("verdicts")
    out = dict(computed=v is not None, chain=bool(v is not None and R.get("chain")), verdicts=dict(v or {}),
               flip=False, bot_only=False, passed=[], binance_only={}, chart={}, d9=False, round_number=False,
               best_rung=None, gradient_q=NAN, gradient_slope=NAN, tradeoff=True, warnings=[],
               why=f"verdicts {NOT_COMPUTED}" if v is None else str(R.get("chain_why") or ""))
    if v is None or not out["chain"]:
        out["flip_text"] = f"not shown: {out['why'] or NOT_COMPUTED}"
        return out
    flags = ans.get("flags") or {}
    out["flip"] = v["H1"] == "PASS"
    out["bot_only"] = (not out["flip"]) and bool(flags.get("h1_bot_only"))
    out["passed"] = [t for t in TESTS if v[t] == "PASS"]
    out["binance_only"] = {t: bool((flags.get("binance_only") or {}).get(t)) for t in out["passed"]}
    if out["flip"]:
        out["flip_text"] = FLIP_STOP
    elif out["bot_only"]:
        out["flip_text"] = "no flip target: " + BOT_ONLY
    else:
        out["flip_text"] = f"not shown: H1 {v['H1']} (shown only if H1 PASSes under rule M)"
    # chart levels (S11): H4 PASS and Romano-Wolf p below the Holm level; or D10's fill-odds family
    h4 = ans.get("h4") or {}
    lvl = _f(h4.get("holm_level"))
    if not math.isfinite(lvl):
        lvl = _f(((ans.get("holm") or {}).get("H4") or {}).get("level"))
    if v["H4"] == "PASS":
        for m in h4.get("methods") or []:
            p = _f(m.get("p_rw"))
            if m.get("method") in CHART_NAMES and math.isfinite(p) and math.isfinite(lvl) and p < lvl:
                out["chart"][m["method"]] = dict(via="H4", p_rw=p, level=lvl,
                                                 label=f"H4 PASS: beat plain volatility-scaled levels at the same "
                                                       f"depth (Romano-Wolf p {p:.4f} < Holm level {lvl:.4f})")
    runner = h4.get("chart_methods_shown")
    if isinstance(runner, list) and sorted(runner) != sorted(m for m, c in out["chart"].items() if c["via"] == "H4"):
        out["warnings"].append(f"the runner's chart_methods_shown {runner} differs from the rule applied here")
    fam = si.get("d10_family") or []
    for r in fam:
        t = r.get("test")
        if t in CHART_NAMES and bool(r.get("rejected")) and t not in out["chart"]:
            out["chart"][t] = dict(via="D10", estimate=_f(r.get("estimate")), label=D10_LABEL)
        if t == "D9" and bool(r.get("rejected")):
            out["d9"] = True
    out["round_number"] = bool(route == "ex" and out["d9"])
    q, slope = _gradient(R)
    out["gradient_q"], out["gradient_slope"] = q, slope
    if math.isfinite(q) and q < 0.10 and math.isfinite(slope) and slope != 0:
        if "best_rung_allowed" in si and not bool(si.get("best_rung_allowed")):
            out["warnings"].append("best_rung_allowed is false in sheet_inputs.json although q < 0.10; no best rung")
        else:
            out["best_rung"] = max(RUNGS) if slope > 0 else min(RUNGS)
    out["tradeoff"] = out["best_rung"] is None
    return out


def _clusters(unit, G, gstar, n=None) -> str:
    """§12: "Every interval states its cluster unit, G and G*" (with the fills when known)."""
    if not unit and not _fin(G):
        return "cluster unit, G and G* not in the runner's output"
    return ((f"{int(_f(n))} fills, " if _fin(n) else "") + f"{unit or 'month-block'} clusters G = "
            + (f"{int(_f(G))}" if _fin(G) else "?") + ", G* = " + (f"{_f(gstar):.1f}" if _fin(gstar) else "n/a"))


def outcome_texts(R: dict, E: dict) -> dict:
    """Post-fill outcomes of the PASSed tests (§13 item 8; V10: the Robinhood-route proxy F3 first; §12: every
    interval with its cluster unit, G and G*)."""
    ans, prim = R.get("answer") or {}, R.get("primary") or {}
    nums = (ans.get("numbers") or {}).get("tests") or {}
    beside = prim.get("beside") or {}
    prows = prim.get("rows") or {}
    out = {}
    what = {"H1": "fills sold into the rebound by hand beat random buys of the same coin by {X} per fill",
            "H2R": "resting bids bought {X} more coin per dollar than an alert at the same level followed by a manual "
                   "buy",
            "H4": "method {j}'s levels beat plain volatility-scaled levels at the same depth by {X} per fill"}
    for t in E.get("passed") or []:
        n = nums.get(t) or {}
        f3 = (beside.get(t) or {}).get("F3_1") or {}
        unit = (prows.get(t) or {}).get("unit") or "month-block"         # §10.2: month-blocks for the three tests
        f3s = (what[t].format(X=_pct(f3.get("estimate"), 1), j=n.get("j", "?")) +
               f" (95% CI {_pct(f3.get('ci_lo'), 1, True)} to {_pct(f3.get('ci_hi'), 1, True)}; "
               f"{_clusters(f3.get('unit'), f3.get('G'), f3.get('gstar'), f3.get('n'))})"
               if _fin(f3.get("estimate")) else "F3 row not available")
        s = (f"{t} PASS. Robinhood-route proxy (F3): {f3s}. Binance spot with Robinhood costs: "
             + what[t].format(X=_pct(n.get("X"), 1), j=n.get("j", "?"))
             + f" (95% CI {_pct(n.get('lo'), 1, True)} to {_pct(n.get('hi'), 1, True)}; "
               f"{_clusters(unit, n.get('G'), n.get('gstar'), n.get('N'))})")
        if t == "H1" and _fin(n.get("R")):
            s += f"; after Robinhood costs a flip made {_pct(n.get('R'), 1, True)} on average"
        if E.get("binance_only", {}).get(t):
            s += "; a Binance-only result (it relies on events the Robinhood-route proxy removes)"
        out[t] = s + "."
    return out


# ============================================================================ per coin and rung: odds, waits, capacity
def _sel(cr: pd.DataFrame | None, coin: str, rung: float, rule: str):
    if cr is None:
        return None
    r = cr[(cr["coin"] == coin) & (np.isclose(cr["rung"].to_numpy(float), rung)) & (cr["rule"] == rule)]
    return None if r.empty else r.iloc[0]


INF = math.inf


def km_median(row) -> float:
    """A row's Kaplan-Meier median wait in weeks: finite; +inf when not reached (the row has Kaplan-Meier starts but
    no median, as stinkbid_desc.sheet_stats writes it); NaN when the row has no waits (coding choice 4)."""
    if row is None:
        return NAN
    m = _f(row.get("median_wait_weeks"))
    if math.isfinite(m):
        return m
    n = _f(row.get("km_starts"))
    n = n if math.isfinite(n) else _f(row.get("bids"))       # desc writes the waits for every row with bids
    return INF if math.isfinite(n) and n > 0 else NAN


def shrink_waits(own, pool) -> dict:
    """§13 item 3 (coding choice 4): the coin's KM median wait and no-fill chance shrunk to the U-Q1 rung with
    w = n / (n + 52). median: finite, +inf (not reached) or NaN with median_lb a lower bound when only that is
    known."""
    m_p, s_p = km_median(pool), (_f(pool.get("p_no_fill_year")) if pool is not None else NAN)
    n = _f(own.get("km_starts", own.get("bids"))) if own is not None else 0.0
    n = n if math.isfinite(n) and n > 0 else 0.0
    w = n / (n + PRIOR)
    if w == 0:
        return dict(median=m_p, median_lb=NAN, no_fill=s_p, w=0.0, pool_median=m_p, pool_no_fill=s_p,
                    median_note="the U-Q1 rung's Kaplan-Meier median is not reached" if m_p == INF else "")
    m_c, s_c = km_median(own), _f(own.get("p_no_fill_year"))
    lb, note = NAN, ""
    if m_c == INF:                                   # no shrunk median (coding choice 4)
        med, note = INF, "the coin's own Kaplan-Meier median is not reached"
    elif math.isfinite(m_c) and math.isfinite(m_p):
        med = w * m_c + (1 - w) * m_p
    elif math.isfinite(m_c) and m_p == INF:          # the mixture's median is at least the coin's own
        med, lb, note = NAN, m_c, "the U-Q1 rung's Kaplan-Meier median is not reached (at least the coin's own median)"
    else:
        med, note = NAN, "the rung's median is not available"
    nf = (w * s_c + (1 - w) * s_p if math.isfinite(s_c) and math.isfinite(s_p)
          else (s_c if math.isfinite(s_c) else s_p))
    return dict(median=med, median_lb=lb, no_fill=nf, w=w, median_note=note, pool_median=m_p, pool_no_fill=s_p)


def wait_cell(v, lb=NAN, computed: bool = True) -> str:
    """The median wait as printed: weeks, "not reached" (+inf), "at least X" (only a lower bound), else n/a."""
    v = _f(v)
    if math.isfinite(v):
        return f"{v:.1f}"
    if v == INF:
        return "not reached"
    if _fin(lb):
        return f"at least {_f(lb):.1f}"
    return "n/a" if computed else NOT_COMPUTED


STAT_COLS = ("rh_rate", "rh_lo", "rh_hi", "bn_rate", "wait_median", "no_fill")


def rung_stats(cr: pd.DataFrame | None, coin: str, pooled_only: bool = False) -> pd.DataFrame:
    """Per rung: F3 shrunk odds and interval, F1 shrunk odds, shrunk waits (F3), capacity (F1 fills), with bases."""
    rows = []
    for rung in RUNGS:
        row = dict(rung=rung)
        if cr is None:
            row.update({c: NAN for c in STAT_COLS}, basis=NOT_COMPUTED, rh_fills=NAN, rh_eps=NAN, w=NAN,
                       median_note="", wait_lb=NAN, cap_p50=NAN, cap_p10=NAN, q_max=NAN, cap_basis=NOT_COMPUTED,
                       pool_median=NAN)
            rows.append(row)
            continue
        own3 = None if pooled_only else _sel(cr, coin, rung, "F3_1")
        own3 = own3 if own3 is not None and _f(own3.get("bids")) > 0 else None
        pool3 = _sel(cr, "ALL", rung, "F3_1")
        src3 = own3 if own3 is not None else pool3
        basis = ("own history in U-Q1, shrunk to the U-Q1 rung" if own3 is not None else
                 ("U-Q1 pooled odds at the same depth" + (" (HYPE: no verdict)" if pooled_only else
                                                          " (no history of this coin in U-Q1)")))
        if src3 is None:
            basis = f"{NOT_COMPUTED} (no F3 row)"
        own1 = None if pooled_only else _sel(cr, coin, rung, "F1")
        own1 = own1 if own1 is not None and _f(own1.get("bids")) > 0 else None
        pool1 = _sel(cr, "ALL", rung, "F1")
        src1 = own1 if own1 is not None else pool1
        wt = shrink_waits(own3, pool3) if pool3 is not None or own3 is not None else \
            dict(median=NAN, median_lb=NAN, no_fill=NAN, w=NAN, median_note="", pool_median=NAN)
        row.update(rh_rate=_f(src3.get("rate_shrunk")) if src3 is not None else NAN,
                   rh_lo=_f(src3.get("wilson_lo")) if src3 is not None else NAN,
                   rh_hi=_f(src3.get("wilson_hi")) if src3 is not None else NAN,
                   rh_fills=_f(src3.get("fills")) if src3 is not None else NAN,
                   rh_eps=_f(src3.get("episodes")) if src3 is not None else NAN,
                   phi=_f(src3.get("phi")) if src3 is not None else NAN,
                   bn_rate=_f(src1.get("rate_shrunk")) if src1 is not None else NAN,
                   wait_median=wt["median"], wait_lb=wt.get("median_lb", NAN), no_fill=wt["no_fill"], w=wt["w"],
                   median_note=wt["median_note"], pool_median=wt.get("pool_median", NAN), basis=basis)
        # capacity: the coin's own F1 fills at the rung, else the pooled rung (labelled)
        cap_own = own1 if own1 is not None and _f(own1.get("fills")) > 0 and _fin(own1.get("C_p10")) else None
        cap = cap_own if cap_own is not None else pool1
        row.update(cap_p50=_f(cap.get("C_p50")) if cap is not None else NAN,
                   cap_p10=_f(cap.get("C_p10")) if cap is not None else NAN,
                   q_max=_f(cap.get("Q_max")) if cap is not None else NAN,
                   cap_basis=("own past fills" if cap_own is not None else
                              ("U-Q1 pooled fills at the rung (no own fill)" if cap is not None else NOT_COMPUTED)))
        rows.append(row)
    return pd.DataFrame(rows)


def _bracket(x: np.ndarray, delta: float):
    """(i, j, kind) of the rungs used at depth delta: kind 'at' (delta on rung i), 'in' (between rungs i < j),
    'deep' / 'shallow' (beyond the deepest / shallowest rung, with its nearest neighbour), or None outside the
    EXTRAP band."""
    if len(x) < 2 or not (x[0] - EXTRAP <= delta <= x[-1] + EXTRAP):
        return None
    hit = np.flatnonzero(np.abs(x - delta) < 1e-9)
    if len(hit):
        return int(hit[0]), int(hit[0]), "at"
    if delta > x[-1]:
        return len(x) - 2, len(x) - 1, "deep"
    if delta < x[0]:
        return 0, 1, "shallow"
    j = int(np.searchsorted(x, delta))
    return j - 1, j, "in"


def at_depth(tab: pd.DataFrame, delta: float) -> dict:
    """The rung statistics read at depth delta (V15; coding choice 2): linear interpolation between the two rungs
    that bracket delta, only when both values are finite; beyond the deepest or shallowest rung, extrapolation with
    the slope of the two nearest rungs (both finite) at most EXTRAP sigma; NaN otherwise. Probabilities are clipped to
    [0, 1]. The median wait (+inf = the Kaplan-Meier median is not reached) stays "not reached" at or beyond a rung
    where it is not reached; between a finite rung and a deeper one without a median only the lower bound is known
    (wait_lb; waits rise with depth); median_note says which."""
    o = np.argsort(tab["rung"].to_numpy(float), kind="stable")
    x = tab["rung"].to_numpy(float)[o]
    out = {c: NAN for c in STAT_COLS}
    out.update(wait_lb=NAN, median_note="")
    br = _bracket(x, delta)
    if br is None:
        out["median_note"] = f"delta {delta:.2f} is more than {EXTRAP:g} sigma outside the M2 rungs"
        return out
    i, j, kind = br

    def lin(y):
        if kind == "at":
            return y[i]
        if not (math.isfinite(y[i]) and math.isfinite(y[j])):
            return NAN
        return y[i] + (delta - x[i]) * (y[j] - y[i]) / (x[j] - x[i])
    for c in STAT_COLS:
        if c == "wait_median":
            continue
        v = lin(tab[c].to_numpy(float)[o])
        out[c] = float(min(max(v, 0.0), 1.0)) if math.isfinite(v) else NAN
    # the median wait: finite, +inf (not reached) or NaN with a lower bound
    y = tab["wait_median"].to_numpy(float)[o]
    lbs = (tab["wait_lb"].to_numpy(float)[o] if "wait_lb" in tab else np.full(len(x), NAN))
    sh = "shallower" if kind == "shallow" else None
    a = j if kind == "deep" else i                   # the rung at or just above delta (shallower side)
    if kind == "at":
        v, lb = y[i], lbs[i]
        note = "not reached at this depth" if v == INF else ""
    elif sh:                                         # above the shallowest rung: only a finite pair extrapolates
        v, lb = (max(lin(y), 0.0) if math.isfinite(lin(y)) else NAN), NAN
        note = "" if math.isfinite(v) else f"no median read {sh} than k = {x[0]:g}"
    elif y[a] == INF:                                # at or beyond a rung whose median is not reached
        v, lb, note = INF, NAN, f"the median is not reached at k = {x[a]:g}, so not at this depth either"
    elif kind == "in" and math.isfinite(y[i]) and math.isfinite(y[j]):
        v, lb, note = lin(y), NAN, ""
    elif kind == "deep" and math.isfinite(y[i]) and math.isfinite(y[j]):
        v, lb, note = max(lin(y), y[j]), NAN, ""
    elif math.isfinite(y[a]):                        # the deeper rung has no median: only the lower bound
        deeper = x[j] if kind == "in" else None
        v, lb = NAN, y[a]
        note = (f"not interpolated: the median is {'not reached' if y[j] == INF else 'not available'} at k = "
                f"{deeper:g}; at least the k = {x[a]:g} median" if deeper is not None else
                f"not extrapolated beyond k = {x[a]:g}; at least its median")
    elif _fin(lbs[a]):
        v, lb, note = NAN, lbs[a], f"at least the lower bound at k = {x[a]:g}"
    else:
        v, lb, note = NAN, NAN, f"no median at k = {x[a]:g}"
    out.update(wait_median=float(v), wait_lb=float(lb), median_note=note)
    return out


# ============================================================================ MoneyLine now (R5), U-Q1 flag (§5)
def _segments(k: pd.DataFrame) -> np.ndarray:
    """Segment ids of traded daily bars (sorted, one per day): seg changes or day gaps; without a seg column the §4.1
    rule (a missing day or a > 25% open jump)."""
    day = (_ns(k["open_time"]) // 86_400_000_000_000).astype(np.int64)
    n = len(k)
    new = np.ones(n, bool)
    if n > 1:
        brk = np.diff(day) != 1
        if "seg" in k:
            sg = k["seg"].to_numpy()
            brk |= sg[1:] != sg[:-1]
        else:
            o, c = k["open"].to_numpy(float), k["close"].to_numpy(float)
            with np.errstate(divide="ignore", invalid="ignore"):
                brk |= np.abs(o[1:] / c[:-1] - 1) > sbl.JUMP
        new[1:] = brk
    return np.cumsum(new) - 1


def _ns(s) -> np.ndarray:
    return pd.to_datetime(pd.Series(s), utc=True).dt.tz_localize(None).astype("datetime64[ns]").to_numpy().astype(
        np.int64)


def traded_daily(k: pd.DataFrame | None) -> pd.DataFrame | None:
    if k is None or not len(k):
        return None
    k = k.copy()
    k["open_time"] = pd.to_datetime(k["open_time"], utc=True)
    if "trades" in k:
        k = k[pd.to_numeric(k["trades"], errors="coerce").fillna(0).to_numpy() > 0]
    if "seg" in k:
        k = k[pd.to_numeric(k["seg"], errors="coerce").fillna(-1).to_numpy() >= 0]
    k = k.sort_values("open_time", kind="stable")
    k = k[~k["open_time"].dt.normalize().duplicated(keep="last")]
    return k.reset_index(drop=True) if len(k) else None


def moneyline_now(k: pd.DataFrame | None, d0: pd.Timestamp) -> dict:
    """The replicated MoneyLine state at d0's close (coding choice 7): green / red / undefined, with its note."""
    k = traded_daily(k)
    if k is None:
        return dict(state="undefined", note="no daily bars", bars=0)
    k = k[k["open_time"].dt.tz_localize(None).dt.normalize() <= d0].reset_index(drop=True)
    if not len(k) or k["open_time"].iloc[-1].tz_localize(None).normalize() != d0:
        return dict(state="undefined", note=f"no daily bar on {d0.date()}", bars=0)
    sid = _segments(k)
    g = k[sid == sid[-1]]
    n = len(g)
    if n < 10:
        return dict(state="undefined", note=f"the series has {n} daily bars since its last boundary (ATR10 needs 10)",
                    bars=n)
    st = mlr.supertrend(pd.DataFrame({c: g[c].to_numpy(float) for c in ("open", "high", "low", "close")}),
                        **mlr.MONEYLINE_PARAMS)
    if not math.isfinite(_f(st["line"].iloc[-1])):
        return dict(state="undefined", note="MoneyLine not yet defined", bars=n)
    state = "green" if bool(st["green"].iloc[-1]) else "red"
    note = ML_RED if state == "red" else ""
    if n < 100:
        note = (note + "; " if note else "") + f"only {n} daily bars since the series' last boundary: still warming up"
    return dict(state=state, note=note, bars=n, line=_f(st["line"].iloc[-1]))


def uq1_flag(univ: pd.DataFrame | None, coin: str, month: str) -> tuple[str, str | None]:
    """('yes' / 'no' / 'unknown', the universe month used) (coding choice 8)."""
    if univ is None or not len(univ) or "U_Q1" not in univ:
        return "unknown", None
    ms = univ["month"].astype(str).str[:7]
    months = sorted(ms.unique())
    m = month if month in months else max([x for x in months if x <= month] or [months[-1]])
    r = univ[(ms == m) & (univ["coin"].astype(str) == coin)]
    if r.empty:
        return "no", m
    return ("yes" if bool(r["U_Q1"].iloc[0]) else "no"), m


DH5_START = ("Descriptive only. A year after a fill,", "Descriptive only. D-H5 could not be estimated")


def dh5_sentence(R: dict) -> str | None:
    """§11's D-H5 descriptive sentence with its estimates (coding choice 8): as the runner printed it (answer.json
    descriptive_sentences, built by stinkbid_desc.sentence_dh5), else built by that function from sheet_inputs.json's
    dh5 with U-Q2 not built (§5: "later session"), so "The study did not test a real-revenue filter." stays; None when
    neither exists."""
    for s in (R.get("answer") or {}).get("descriptive_sentences") or []:
        if isinstance(s, str) and s.startswith(DH5_START):
            return s
    dh5 = (R.get("si") or {}).get("dh5")
    if isinstance(dh5, dict) and "U_Q1" in dh5:
        from analysis_2026 import stinkbid_desc as sbdesc
        return sbdesc.sentence_dh5(dh5, u_q2_built=False)
    return None


def _weeks(v) -> str:
    v = _f(v)
    return f"{v:.1f} weeks" if math.isfinite(v) else ("not reached" if v == INF else "n/a")


def pf_none(E: dict, via: str | None = None) -> str:
    """The post-fill outcomes cell of a row no PASSed outcome applies to (§13 item 8: "only for a test that
    PASSed"; H1's and H2R's outcomes apply to every bid, H4's to the chart levels it earned)."""
    if not E.get("computed"):
        return f"not shown: verdicts {NOT_COMPUTED}"
    if not E.get("chain"):
        return f"not shown: {E.get('why') or NOT_COMPUTED}"
    if not E.get("passed"):
        return "not shown: no test passed"
    if via == "D10":
        return ("not shown for this level: only H4 passed, and this method did not earn H4's chart rule (Romano-Wolf p "
                "below the Holm level); it is shown for D10's fill odds")
    return ("not shown on the M2 rungs: only H4 passed (its outcome belongs to the chart levels it earned: see their "
            "rows and the post-fill outcomes above the table)")


# ============================================================================ the ladder footer (§13, R9)
def _live_days(lf: np.ndarray, le: np.ndarray) -> np.ndarray:
    a = lf // DAY_M
    e = (le - 1) // DAY_M
    ln = np.maximum(e - a + 1, 0)
    if not ln.sum():
        return np.zeros(0, np.int64)
    off = np.arange(ln.sum()) - np.repeat(np.cumsum(ln) - ln, ln)
    return np.unique(np.repeat(a, ln) + off)


def _longest_dry(live: np.ndarray, fill_days: np.ndarray) -> int:
    dry = live[~np.isin(live, fill_days)]
    if not len(dry):
        return 0
    rid = np.cumsum(np.r_[True, np.diff(dry) != 1])
    return int(np.bincount(rid).max())


def ladder_stats(bids: pd.DataFrame | None, coins, rules=("F3_1", "F1")) -> dict | None:
    """N fill days a year, the longest dry stretch D and the worst day's share S of the requested coins' k = 6/8/10
    weekly bids (coding choice 11)."""
    if bids is None or not len(bids):
        return None
    b = bids[bids["coin"].astype(str).isin(list(coins)) & np.isin(bids["rung"].to_numpy(float), RUNGS)]
    if not len(b):
        return None
    from analysis_2026 import stinkbid_desc as sbdesc
    live = _live_days(b["live_from"].to_numpy(np.int64), b["life_end"].to_numpy(np.int64))
    years = len(live) / 365.25
    out = dict(coins=sorted(b["coin"].astype(str).unique()), missing=[c for c in coins if c not in set(b["coin"])],
               live_days=int(len(live)), years=years,
               first=str(pd.Timestamp(int(live[0]) * 86_400_000_000_000).date()) if len(live) else None,
               last=str(pd.Timestamp(int(live[-1]) * 86_400_000_000_000).date()) if len(live) else None)
    for rule in rules:
        tc = "t_" + rule
        if tc not in b:
            out[rule] = None
            continue
        t = b[tc].to_numpy(np.int64)
        fd = np.unique(t[t >= 0] // DAY_M)
        fd = fd[np.isin(fd, live)]
        wd = sbdesc.worst_day(b.assign(variant=b.get("variant", "M2")), tc)
        out[rule] = dict(N=len(fd) / years if years > 0 else NAN, D=_longest_dry(live, fd), fill_days=int(len(fd)),
                         S=_f(wd.get("share")), day=wd.get("day"), filled=wd.get("filled"), live=wd.get("live"))
    return out


def _cache_bids(path: Path) -> pd.DataFrame | None:
    """P1's real M2 bids with their F1 / F3 (s = 1%) fill minutes from one cached engine run (counts only)."""
    try:
        B = pd.read_parquet(path / "bids.parquet")
        F = pd.read_parquet(path / "fills.parquet")
    except (OSError, ValueError):
        return None
    keep = [c for c in ("bid_id", "coin", "rung", "method", "variant", "real", "t0", "live_from", "life_end")
            if c in B]
    B = B[keep]
    if "method" in B:
        B = B[B["method"].astype(str) == "M2"]
    if "real" in B:
        B = B[B["real"].astype(bool)]
    for r in ("F1", "F3_1"):
        tc = "t_" + r
        if len(F) and tc in F:
            B = B.merge(F[["bid_id", tc]], on="bid_id", how="left")
            B[tc] = B[tc].fillna(-1).astype(np.int64)
        else:
            B[tc] = -1
    B["coin"] = B["coin"].astype(str)
    return B.reset_index(drop=True)


def compact_history(bids: pd.DataFrame) -> pd.DataFrame:
    """The ladder history as chains of consecutive weekly bids (t0, n, step, live offset, last life end) plus one
    row per filled bid (coding choice 11)."""
    rows = []
    for (coin, rung), g in bids.sort_values(["coin", "rung", "t0"]).groupby(["coin", "rung"], sort=True):
        t0 = g["t0"].to_numpy(np.int64)
        lf = g["live_from"].to_numpy(np.int64)
        le = g["life_end"].to_numpy(np.int64)
        s = 0
        for i in range(1, len(g) + 1):
            end = i == len(g)
            if not end:
                step = t0[s + 1] - t0[s] if i > s + 1 else t0[i] - t0[s]
                cont = (t0[i] == le[i - 1] and t0[i] - t0[i - 1] == step and lf[i] - t0[i] == lf[s] - t0[s])
            if end or not cont:
                n = i - s
                st = int(t0[s + 1] - t0[s]) if n > 1 else int(le[s] - t0[s])
                rows.append(dict(kind="chain", coin=coin, rung=float(rung), t0=int(t0[s]), n=int(n), step=st,
                                 live_off=int(lf[s] - t0[s]), life_end=int(le[i - 1]), t_F1=-1, t_F3_1=-1))
                s = i
        f = g[(g["t_F1"].to_numpy() >= 0) | (g["t_F3_1"].to_numpy() >= 0)]
        for r in f.itertuples():
            rows.append(dict(kind="fill", coin=coin, rung=float(rung), t0=int(r.t0), n=1, step=0, live_off=0,
                             life_end=0, t_F1=int(r.t_F1), t_F3_1=int(r.t_F3_1)))
    return pd.DataFrame(rows, columns=["kind", "coin", "rung", "t0", "n", "step", "live_off", "life_end", "t_F1",
                                       "t_F3_1"])


def expand_history(h: pd.DataFrame) -> pd.DataFrame:
    """The bids table back from compact_history."""
    ch = h[h["kind"] == "chain"]
    parts = []
    for r in ch.itertuples():
        t0 = r.t0 + r.step * np.arange(r.n, dtype=np.int64)
        le = np.r_[t0[1:], r.life_end].astype(np.int64)
        parts.append(pd.DataFrame(dict(coin=str(r.coin), rung=float(r.rung), t0=t0, live_from=t0 + r.live_off,
                                       life_end=le)))
    b = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["coin", "rung", "t0", "live_from",
                                                                                 "life_end"])
    f = h[h["kind"] == "fill"][["coin", "rung", "t0", "t_F1", "t_F3_1"]].astype(dict(coin=str, rung=float))
    b = b.merge(f, on=["coin", "rung", "t0"], how="left")
    for c in ("t_F1", "t_F3_1"):
        b[c] = b[c].fillna(-1).astype(np.int64)
    b["variant"] = "M2 k=" + b["rung"].map(lambda x: f"{x:g}")
    return b


def load_history(cache_dir, results_dir, write: bool = True) -> tuple[pd.DataFrame | None, str]:
    """The ladder history: the runner's cache (fcount / outcomes run of P1 on U-C, else on U-Q1), else the compact
    file in <results>/sheet/. When read from the cache, the compact file is (re)written for later sheets."""
    cache_dir, results_dir = Path(cache_dir), Path(results_dir)
    for sub in HISTORY_RUNS:
        p = cache_dir / sub
        if (p / "done.json").exists() and (p / "bids.parquet").exists():
            b = _cache_bids(p)
            if b is None or not len(b):
                continue
            label = ("P1 on U-C (Robinhood-tradable coins while in Binance's top 100; hindsight)" if "U_C" in sub
                     else "P1 on U-Q1 (each coin while large and long-listed)")
            if write:
                try:
                    f = results_dir / "sheet" / HISTORY_FILE
                    f.parent.mkdir(parents=True, exist_ok=True)
                    h = compact_history(b)
                    tmp = f.with_suffix(f".{os.getpid()}.tmp")
                    h.assign(source=sub).to_csv(tmp, index=False)
                    os.replace(tmp, f)
                except OSError:
                    pass
            return b, f"{label}, run cache {_rel(p)}"
    f = results_dir / "sheet" / HISTORY_FILE
    h = _csv(f)
    if h is not None and len(h) and {"kind", "coin", "rung", "t0"} <= set(h.columns):
        src = str(h["source"].iloc[0]) if "source" in h else "?"
        label = ("P1 on U-C (Robinhood-tradable coins while in Binance's top 100; hindsight)" if "U_C" in src
                 else "P1 on U-Q1")
        return expand_history(h), f"{label}, compact history {_rel(f)}"
    return None, f"{NOT_COMPUTED} (no run cache in {_rel(cache_dir)} and no {_rel(f)})"


# ============================================================================ daily bars (cache, refresh, injection)
def refresh_daily(coin: str, end_day: pd.Timestamp, base: pd.DataFrame | None, fetch=None, log=None,
                  cache_dir=None):
    """Coding choice 12: daily spot klines after `base` through end_day from the Binance archive (fetch_bb_data.klines,
    checksum-verified), cached in data/stinkbid/sheet/d1/<SYM>.parquet; returns base extended (seg continued by the
    §4.1 rule) or None when nothing could be fetched."""
    sym = sbd.coin_sym(coin)[0]
    cache_f = Path(cache_dir or (SHEET_DATA / "d1")) / f"{sym}.parquet"
    old = None
    if cache_f.exists():
        try:
            old = pd.read_parquet(cache_f)
        except (OSError, ValueError):
            old = None
    last = None
    for fr in (base, old):
        if fr is not None and len(fr):
            t = pd.to_datetime(fr["open_time"], utc=True).max().tz_localize(None).normalize()
            last = t if last is None else max(last, t)
    if last is not None and last >= end_day:
        new = old
    else:
        start = (last - pd.Timedelta(days=31)) if last is not None else (end_day - pd.Timedelta(days=430))
        if fetch is None:
            from analysis_2026 import fetch_bb_data as bb

            def fetch(s, end, start_month):
                return bb.klines("spot", s, "1d", end, start_month=start_month, workers=8)[0]
        try:
            got = fetch(sym, str(end_day.date()), start.strftime("%Y-%m"))
        except Exception as e:                                   # network or archive error: keep what exists
            if log:
                log(f"  {coin}: refresh failed ({e!r:.120}); using the cached bars")
            got = None
        if got is not None and len(got):
            got = got.copy()
            got["open_time"] = pd.to_datetime(got["open_time"], utc=True)
            new = pd.concat([old, got], ignore_index=True) if old is not None else got
            new = new.sort_values("open_time").drop_duplicates("open_time", keep="last").reset_index(drop=True)
            try:
                cache_f.parent.mkdir(parents=True, exist_ok=True)
                new.drop(columns=["seg"], errors="ignore").to_parquet(cache_f)
            except OSError:
                pass
        else:
            new = old
    if new is None or not len(new):
        return base
    new = new.drop(columns=["seg"], errors="ignore")
    if base is None or not len(base):
        return new.reset_index(drop=True)
    b_last = pd.to_datetime(base["open_time"], utc=True).max()
    add = new[pd.to_datetime(new["open_time"], utc=True) > b_last]
    if not len(add):
        return base
    out = pd.concat([base, add], ignore_index=True)
    if "seg" in base:
        seg = out["seg"].to_numpy(float).copy()
        # continue the last segment by the §4.1 rule for the added rows
        i0 = len(base)
        prev_t = pd.to_datetime(base["open_time"], utc=True).max().tz_localize(None).normalize()
        prev_c = float(base["close"].iloc[-1])
        s = float(base["seg"].iloc[-1])
        for i in range(i0, len(out)):
            t = pd.Timestamp(out["open_time"].iloc[i]).tz_convert(None).normalize()
            if (t - prev_t).days != 1 or abs(float(out["open"].iloc[i]) / prev_c - 1) > sbl.JUMP:
                s += 1
            seg[i] = s
            prev_t, prev_c = t, float(out["close"].iloc[i])
        out["seg"] = seg.astype(np.int64)
    return out.reset_index(drop=True)


# ============================================================================ the sheet
@dataclass
class Sheet:
    asof: pd.Timestamp
    rows: pd.DataFrame
    lines: list
    diff: pd.DataFrame
    meta: dict = field(default_factory=dict)
    refused: dict = field(default_factory=dict)


ID_COLS = ["coin", "row", "as_of_utc", "ref_price", "ref_source", "sigma30", "sigma30_closes_to", "rh_tick"]
S13_COLS = ["limit_price", "depth_pct", "depth_sigma",                                                     # 1, 2
            "median_weeks_to_fill", "no_fill_within_year", "wait_basis",                                   # 3
            "rh_fill_odds_week", "rh_fill_odds_lo", "rh_fill_odds_hi", "rh_fill_odds_basis",               # 4
            "binance_fill_odds_week_upper_bound", "fill_odds_note",
            "capacity_median_usd", "capacity_p10_usd", "q_max_usd", "capacity_note",                       # 5
            "moneyline_now", "moneyline_note",                                                             # 6
            "large_long_listed", "knife_rates_dh5",                                                        # 7
            "flip_target", "flip_rule", "post_fill_outcomes", "chart_level", "round_number_advice",         # 8
            "best_rung", "theta_k", "theta_k_ci", "mu_star_k", "mu_star_k_ci", "tradeoff_binance"]
ORDER_COLS = ["route", "order_size_usd", "orders", "n_orders", "order_qty_total", "cash_reserved_usd", "order_note",
              "refused"]
COLS = ID_COLS + S13_COLS + ORDER_COLS


def _tradeoff(R: dict, E: dict, rung: float) -> dict:
    out = dict(theta_k="", theta_k_ci="", mu_star_k="", mu_star_k_ci="", tradeoff_binance="")
    if not E["tradeoff"]:
        out["theta_k"] = "not shown: a best rung is earned"
        return out
    d6 = R.get("d6")
    if d6 is None or "rule" not in d6 or "rung" not in d6:
        out["theta_k"] = NOT_COMPUTED
        return out
    for rule, tag in (("F3_1", ""), ("F1", "b")):
        g = d6[(d6["rule"].astype(str) == rule) & np.isclose(pd.to_numeric(d6["rung"], errors="coerce"), rung)]
        if not len(g):
            continue
        r = g.iloc[0]
        th, mu = _f(r.get("theta")), _f(r.get("mu_star"))
        if tag == "":
            # §12: the interval's cluster unit, G and G* (theta_k's; mu*_k's interval is carried from it)
            cl = _clusters(r.get("theta_unit") if isinstance(r.get("theta_unit"), str) else "", r.get("theta_G"),
                           r.get("theta_gstar"), r.get("theta_n"))
            out.update(theta_k=_pct(th, 2, True), theta_k_ci=f"{_pct(r.get('theta_lo'), 1, True)} to "
                                                             f"{_pct(r.get('theta_hi'), 1, True)}; {cl}",
                       mu_star_k=(_pct(mu, 1, True) + " a year") if math.isfinite(mu) else "n/a",
                       mu_star_k_ci=f"{_pct(r.get('mu_star_lo'), 1, True)} to {_pct(r.get('mu_star_hi'), 1, True)}"
                                    f"; from theta_k's interval ({cl})")
        else:
            out["tradeoff_binance"] = (f"Binance spot: theta {_pct(th, 2, True)}, mu* "
                                       f"{_pct(mu, 1, True) if math.isfinite(mu) else 'n/a'} a year")
    if out["theta_k"] == "":
        out["theta_k"] = NOT_COMPUTED
    return out


def _round_number(L: Decimal, P0: float, tick: str):
    """M5's minor grid g = 10^(floor(log10 P0) - 1); (is L a multiple of g, L + tick)."""
    e = math.floor(math.log10(P0))
    while 10.0 ** (e + 1) <= P0:
        e += 1
    while 10.0 ** e > P0:
        e -= 1
    g = Decimal(10) ** (e - 1)
    return (L % g == 0), L + Decimal(tick)


def _empty_row(coin: str, asof: pd.Timestamp) -> dict:
    r = {c: "" for c in COLS}
    r.update(coin=coin, as_of_utc=asof.strftime("%Y-%m-%d %H:%M"))
    return r


TABLE_HEAD = ("  row               limit   depth % / sigma   wait: median / none in 1y   Robinhood odds/wk [95%]"
              "   Binance   capacity: median / p10 / Q_max")


def _table_row(name: str, limit: str, dpct: float, delta: float, sv: dict) -> str:
    """One line of a coin's table (ASCII, about 120 characters)."""
    w, lb = _f(sv.get("wait_median")), _f(sv.get("wait_lb"))
    wait = (f"{w:.1f} wk" if math.isfinite(w) else "not reached" if w == INF else
            f">={lb:.1f} wk" if math.isfinite(lb) else "n/a")
    rh = f"{_pct(sv.get('rh_rate')):>6} [{_pct(sv.get('rh_lo')):>5}-{_pct(sv.get('rh_hi')):>6}]"
    cap = f"{_usd(sv.get('cap_p50'))} / {_usd(sv.get('cap_p10'))} / {_usd(sv.get('q_max'))}"
    return (f"  {name:<9}{limit:>15}  {dpct:5.1f}% {delta:6.2f}   {wait:>11} / {_pct(sv.get('no_fill')):>6}"
            f"      {rh:>22}   {_pct(sv.get('bn_rate')):>7}   {cap}")


def _flip(Ld: Decimal, P0: float, tick: str) -> str:
    """X-FLIP's target R1/2 = ceil(L + (P0 - L) / 2) on Robinhood's tick (prereg §8)."""
    nf = sbl.ceil_n(Ld + (Decimal(repr(float(P0))) - Ld) / 2, tick)
    return _pstr(Decimal(nf) * Decimal(tick), tick) if nf else ""


class _Ctx:
    pass


def _coin(coin: str, C: _Ctx):
    """Rows, text lines, refusal reason, cash and the deepest priced rung of one coin."""
    asof, R, E = C.asof, C.R, C.E
    rows, lines = [], []
    base = _empty_row(coin, asof)

    def refuse(why):
        r = dict(base, row="(refused)", refused=_a(why), route=C.route)
        lines.append(f"{coin}: REFUSED - {_a(why)}")
        return [r], lines, why, 0.0, None

    cat_r, why = catalog_row(C.cat, coin)
    if cat_r is None:
        return refuse(why)
    tick = str(cat_r["price_tick_str"])
    # daily bars
    dc = None
    if C.data is not None:
        dc = C.data.get(coin)
        if dc is None:
            return refuse("no daily bars for this coin (injected world)")
        k = dc.get("d1")
    else:
        try:
            k = sbd.d1(coin)
            k = k if len(k) else None
        except Exception:
            k = None
    if C.refresh:
        k2 = refresh_daily(coin, _day(asof) - pd.Timedelta(days=1), k, fetch=C.fetch, log=C.log,
                           cache_dir=C.refresh_dir)
        if k2 is not None and (k is None or len(k2) > len(k)):
            k = k2
            dc = {"d1": k}
    kt = traded_daily(k)
    if kt is None:
        return refuse("no Binance spot daily bars for this coin" + ("" if C.refresh else " (try --refresh)"))
    days = kt["open_time"].dt.tz_localize(None).dt.normalize()
    yday = _day(asof) - pd.Timedelta(days=1)
    ok_days = days[days <= yday]
    if not len(ok_days):
        return refuse("no completed daily bar before the sheet's clock")
    d0 = ok_days.iloc[-1]
    close_t = (d0 + pd.Timedelta(days=1)).tz_localize("UTC")
    age_h = (asof - close_t) / pd.Timedelta(hours=1)
    stale_d = int((yday - d0).days)
    pstr = C.prices.get(coin)
    if pstr is None and age_h > FRESH_H:
        return refuse(f"the latest close ({d0.date()}) is {age_h:.0f} hours old, more than 24 hours: pass "
                      f"--price {coin}=<the app's mid> or --refresh (STINKBID_PREREG.md section 13)")
    if stale_d > SIGMA_STALE_D:
        return refuse(f"the daily bars end {d0.date()}, {stale_d} days before yesterday: sigma30 would belong to "
                      "another week; run with --refresh")
    t0 = (d0 + pd.Timedelta(days=1, hours=3, minutes=30)).tz_localize("UTC")
    price = float(Decimal(pstr)) if pstr is not None else None
    I = sbl.inputs_at(coin, t0, data=dc, price=price, tick=tick)
    if not I["ok"]:
        return refuse(f"level inputs not valid at {d0.date()}: {I['why']}")
    P0, sig = float(I["P0"]), float(I["sigma30"])
    close = float(I["close"])
    if price is not None and not C.force_price and abs(math.log(price / close)) > math.log(PRICE_JUMP):
        return refuse(f"--price {coin}={pstr} is more than {PRICE_JUMP:g}x away from the last Binance close "
                      f"{close:g} ({d0.date()}): check for a typo (a limit buy above the market fills at once), or "
                      "pass --force-price")
    ref_src = (f"--price: the app's mid at {asof:%Y-%m-%d %H:%M} UTC" if price is not None else
               f"Binance spot close of {d0.date()}, {age_h:.0f} h old")
    ml = moneyline_now(k, d0)
    flag, fmonth = uq1_flag(C.univ, coin, f"{asof:%Y-%m}")
    flag_txt = {"yes": "yes", "no": "no", "unknown": "unknown (universes not built here)"}[flag]
    if fmonth and fmonth != f"{asof:%Y-%m}":
        flag_txt += f" (universe of {fmonth})"
    hype = coin == "HYPE"
    st = rung_stats(R["coin_rung"], coin, pooled_only=hype)
    base.update(ref_price=pstr if pstr is not None else repr(close), ref_source=ref_src,
                sigma30=f"{sig:.6f}", sigma30_closes_to=str(d0.date()), rh_tick=tick,
                moneyline_now=ml["state"], moneyline_note=_a(ml["note"]), large_long_listed=flag_txt,
                knife_rates_dh5=_a(C.knife), route=C.route)
    halted = str(cat_r.get("halted_regions") or "").strip()
    lines.append(_a(f"{coin}  reference {base['ref_price']} ({ref_src}); sigma30 {_pct(sig, 2)} (closes to "
                    f"{d0.date()}); Robinhood tick {tick}"))
    lines.append(_a(f"  MoneyLine now: {ml['state']}" + (f" - {ml['note']}" if ml["note"] else "")))
    lines.append(_a(f"  Large, long-listed (Binance volume): {flag_txt}"))
    if halted:
        lines.append(_a(f"  Robinhood: halted for {halted} residents (catalog of 2026-11-18)"))
    if hype:
        lines.append(_a("  " + HYPE_NOTE))
    lines.append(TABLE_HEAD)
    cash, deepest = 0.0, None
    texts = C.outcomes
    pf_all = "; ".join(texts[t] for t in ("H2R", "H1") if t in texts)
    flip_rule = E.get("flip_text", "")
    computed = R["coin_rung"] is not None
    order_lines, basis_lines, extra = [], [], []
    m2_at = {}                                       # rung -> (delta, limit, orders) for the chart alternatives
    for rung in RUNGS:
        r = dict(base, row=f"M2 k={rung:g}")
        info = sbl.level_info("M2", I, k=rung)
        if info["status"] != "ok":
            r.update(refused=_a(f"no level at k = {rung:g}: {info['status']} {info['detail']}"))
            rows.append(r)
            lines.append(_a(f"  M2 k={rung:<4g} no level ({info['status']}: {info['detail']})"))
            continue
        L, delta, n = float(info["L"]), float(info["delta"]), int(info["n_ticks"])
        Ld = Decimal(n) * Decimal(tick)
        srow = st[np.isclose(st["rung"].to_numpy(float), rung)].iloc[0].to_dict()
        note = srow["basis"]
        wnote = srow.get("median_note") or ""
        if wnote.startswith("the coin's own"):       # coding choice 4: the rung's median beside
            wnote += f" (U-Q1 rung: {_weeks(srow.get('pool_median'))})"
        if delta - rung > REROUND and computed:
            dv = at_depth(st, delta)
            srow.update(dv)
            note += (f"; Robinhood's tick moved the level {delta - rung:.2f} sigma deeper, so the waits and odds are "
                     f"read at delta {delta:.2f} (V15)")
            wnote = "; ".join(x for x in (wnote, f"read at delta {delta:.2f} (V15)" +
                                          (f": {dv['median_note']}" if dv["median_note"] else "")) if x)
        if math.isfinite(_f(srow.get("w"))) and srow["w"] > 0:
            note += f"; weight of the coin's own history {srow['w']:.2f}"
        Q = C.per_rung
        qcap = ""
        if C.route == "ex" and math.isfinite(srow["q_max"]) and srow["q_max"] > 0 and Q > srow["q_max"]:
            Q, qcap = srow["q_max"], f"capped at Q_max {_usd(srow['q_max'])} (exchange route)"
        orders, onote = rh_orders(Ld, Q, cat_r)
        qtot = sum(orders, Decimal(0))
        cash_r = float(qtot * Ld)
        cash += cash_r
        if C.route == "mm" and math.isfinite(srow["q_max"]) and C.per_rung > srow["q_max"]:
            onote = "; ".join(x for x in (onote, f"above Q_max {_usd(srow['q_max'])} (context only on the "
                                                 "market-maker route)") if x)
        flip = _flip(Ld, P0, tick) if E["flip"] else ""
        if E["round_number"]:
            is_r, up = _round_number(Ld, P0, tick)
            rn = (f"{_pstr(Ld, tick)} is a round number: bid one tick above it, at {_pstr(up, tick)} (D9, exchange "
                  "route)" if is_r else "not at a round number (D9 advice: bid one tick above round numbers)")
        else:
            rn = ("not shown: exchange route only (--route ex)" if C.route == "mm" else
                  ("not shown: D9 did not earn it" if E["chain"] else f"not shown: {E['why'] or NOT_COMPUTED}"))
        if E["best_rung"] is not None:
            best = (f"best rung (depth gradient BH q = {E['gradient_q']:.3f}; per-fill excess "
                    f"{'rises' if E['gradient_slope'] > 0 else 'falls'} with depth; exploratory)"
                    if rung == E["best_rung"] else "")
        else:
            best = ("none: the depth gradient's BH q = " + (f"{E['gradient_q']:.3f}" if _fin(E["gradient_q"]) else
                                                            NOT_COMPUTED) + " (a best rung needs q < 0.10); see "
                    "the trade-off" if E["chain"] else f"not shown: {E['why'] or NOT_COMPUTED}")
        tr = _tradeoff(R, E, rung)
        wait_basis = ("F3 (Robinhood-route proxy); Kaplan-Meier " +
                      ("on the coin shrunk to the U-Q1 rung" if _f(srow.get("w")) > 0 else "of the U-Q1 rung") +
                      (f"; {wnote}" if wnote else ""))
        if not computed:
            wait_basis = NOT_COMPUTED
        rh_basis = (f"{int(srow['rh_fills'])} fills in {int(srow['rh_eps'])} episodes"
                    if _fin(srow.get("rh_fills")) and _fin(srow.get("rh_eps")) else NOT_COMPUTED)
        if _fin(srow.get("rh_fills")) and srow["basis"].startswith("U-Q1 pooled"):
            rh_basis += " (U-Q1 pooled)"
        r.update(limit_price=_pstr(Ld, tick), depth_pct=f"{100 * (1 - L / P0):.2f}", depth_sigma=f"{delta:.3f}",
                 median_weeks_to_fill=wait_cell(srow["wait_median"], srow.get("wait_lb"), computed),
                 no_fill_within_year=f"{srow['no_fill']:.4f}" if _fin(srow["no_fill"]) else NOT_COMPUTED,
                 wait_basis=_a(wait_basis),
                 rh_fill_odds_week=f"{srow['rh_rate']:.5f}" if _fin(srow["rh_rate"]) else NOT_COMPUTED,
                 rh_fill_odds_lo=f"{srow['rh_lo']:.5f}" if _fin(srow["rh_lo"]) else "",
                 rh_fill_odds_hi=f"{srow['rh_hi']:.5f}" if _fin(srow["rh_hi"]) else "",
                 rh_fill_odds_basis=_a(rh_basis),
                 binance_fill_odds_week_upper_bound=f"{srow['bn_rate']:.5f}" if _fin(srow["bn_rate"]) else
                 NOT_COMPUTED,
                 fill_odds_note=_a(note + ("; F3 is the market-maker proxy (a lower bound on the exchange route)"
                                           if C.route == "ex" and computed else "")),
                 capacity_median_usd=f"{srow['cap_p50']:.0f}" if _fin(srow["cap_p50"]) else NOT_COMPUTED,
                 capacity_p10_usd=f"{srow['cap_p10']:.0f}" if _fin(srow["cap_p10"]) else NOT_COMPUTED,
                 q_max_usd=f"{srow['q_max']:.0f}" if _fin(srow["q_max"]) else NOT_COMPUTED,
                 capacity_note=_a("Binance spot book; " + srow["cap_basis"] +
                                  ("; context only on the market-maker route" if C.route == "mm" else "")),
                 flip_target=flip, flip_rule=_a(flip_rule),
                 post_fill_outcomes=_a(pf_all if pf_all else pf_none(E)), chart_level="",
                 round_number_advice=_a(rn), best_rung=_a(best), **{k_: _a(v) for k_, v in tr.items()},
                 order_size_usd=f"{Q:.2f}", orders=";".join(_dstr(o) for o in orders), n_orders=str(len(orders)),
                 order_qty_total=_dstr(qtot), cash_reserved_usd=f"{cash_r:.2f}",
                 order_note=_a("; ".join(x for x in (qcap, onote) if x)))
        rows.append(r)
        m2_at[rung] = (delta, r["limit_price"], " + ".join(_dstr(o) for o in orders))
        if deepest is None or rung > deepest["rung"]:
            inc, mn = Decimal(str(cat_r["qty_increment_str"])), Decimal(str(cat_r["min_order_size_str"]))
            q1 = max(mn, (Decimal(1) / Ld / inc).to_integral_value(rounding=ROUND_CEILING) * inc)
            deepest = dict(rung=rung, limit=_pstr(Ld, tick), qty=_dstr(q1), usd=float(q1 * Ld), coin=coin,
                           halted=bool(halted))
        lines.append(_a(_table_row(f"M2 k={rung:g}", r["limit_price"], 100 * (1 - L / P0), delta, srow)))
        qs = " + ".join(_dstr(o) for o in orders)
        order_lines.append(_a(f"    k={rung:g}: BUY {qs or 'nothing'} {coin} at limit {r['limit_price']} "
                              f"(${cash_r:,.2f})" + (f" - {r['order_note']}" if r["order_note"] else "")))
        if computed:
            basis_lines.append(_a(f"    k={rung:g}: {rh_basis}; {note}"))
        if flip:
            extra.append(f"    k={rung:g}: flip target {flip} ({FLIP_STOP})")
        if E["round_number"] and " is a round number" in rn:
            extra.append(f"    k={rung:g}: {rn}")
        if E["tradeoff"] and tr["theta_k"] != NOT_COMPUTED:
            extra.append(f"    k={rung:g} trade-off (F3): theta_k {tr['theta_k']} ({tr['theta_k_ci']}), mu*_k "
                         f"{tr['mu_star_k']} ({tr['mu_star_k_ci']})" + (f"; {tr['tradeoff_binance']}"
                                                                         if tr["tradeoff_binance"] else ""))
        elif E["best_rung"] is not None and best:
            extra.append(f"    k={rung:g}: {best}")
    # chart levels (earned only)
    chart_lines = []
    for m, params in CHART:
        if m not in E["chart"]:
            continue
        c = E["chart"][m]
        label = sbl.variant_label(m, params)
        r = dict(base, row=f"{label} (chart)")
        info = sbl.level_info(m, I, **params)
        pf = "; ".join(texts[t] for t in ("H2R", "H1", "H4") if t in texts and (t != "H4" or c["via"] == "H4"))
        pf = pf or pf_none(E, c["via"])
        if info["status"] != "ok":
            r.update(post_fill_outcomes=_a(pf), flip_rule=_a(flip_rule),
                     chart_level=_a(f"{c['label']}; {CHART_NAMES[m]}: no level this week ({info['status']}"
                                    + (", hourly / futures data through d0 are needed" if dc is not None and m in
                                       ("M6", "M7") else "") + ")"))
            rows.append(r)
            chart_lines.append(_a(f"    {label} ({CHART_NAMES[m]}): no level this week ({info['status']})"))
            continue
        L, delta, n = float(info["L"]), float(info["delta"]), int(info["n_ticks"])
        Ld = Decimal(n) * Decimal(tick)
        sv = at_depth(st, delta) if computed else dict({k_: NAN for k_ in STAT_COLS}, wait_lb=NAN, median_note="")
        orders, onote = rh_orders(Ld, C.per_rung, cat_r)
        qtot = sum(orders, Decimal(0))
        flip = _flip(Ld, P0, tick) if E["flip"] else ""
        # §13 item 8 / §11: an alternative to the M2 rung nearest in depth, never an extra order (coding choice 10)
        alt = min(m2_at, key=lambda k_: (abs(m2_at[k_][0] - delta), k_)) if m2_at else None
        alt_txt = (f"an alternative to the M2 k={alt:g} rung at {m2_at[alt][1]} (replace it, do not add; not in the "
                   "cash total)" if alt is not None else "an alternative to the M2 rungs (none priced this week; not "
                   "in the cash total)")
        inside = RUNGS[0] - EXTRAP <= delta <= RUNGS[-1] + EXTRAP
        r.update(limit_price=_pstr(Ld, tick), depth_pct=f"{100 * (1 - L / P0):.2f}", depth_sigma=f"{delta:.3f}",
                 median_weeks_to_fill=wait_cell(sv["wait_median"], sv.get("wait_lb"), computed),
                 no_fill_within_year=f"{sv['no_fill']:.4f}" if _fin(sv["no_fill"]) else NOT_COMPUTED,
                 wait_basis=(NOT_COMPUTED if not computed else
                             ("plain-level waits at this depth (interpolated from the M2 rungs), not the chart "
                              "level's own" + (f"; {sv['median_note']}" if sv.get("median_note") else "")) if inside
                             else f"{NOT_COMPUTED}: delta {delta:.2f} is more than {EXTRAP:g} sigma outside the M2 "
                                  "rungs (6-10)"),
                 rh_fill_odds_week=f"{sv['rh_rate']:.5f}" if _fin(sv["rh_rate"]) else NOT_COMPUTED,
                 rh_fill_odds_lo=f"{sv['rh_lo']:.5f}" if _fin(sv["rh_lo"]) else "",
                 rh_fill_odds_hi=f"{sv['rh_hi']:.5f}" if _fin(sv["rh_hi"]) else "",
                 rh_fill_odds_basis="plain-level odds at this depth (interpolated from the M2 rungs)",
                 binance_fill_odds_week_upper_bound=f"{sv['bn_rate']:.5f}" if _fin(sv["bn_rate"]) else NOT_COMPUTED,
                 fill_odds_note=_a(c["label"] + (f"; D10 estimate {_pts(c.get('estimate'), 2)} points of fill "
                                                 "probability per bid over depth-matched placebos"
                                                 if c["via"] == "D10" else "")),
                 capacity_note="no capacity history for chart levels",
                 flip_target=flip, flip_rule=_a(flip_rule), post_fill_outcomes=_a(pf),
                 chart_level=_a(f"{m}: {CHART_NAMES[m]}; {c['label']}"),
                 order_size_usd=f"{C.per_rung:.2f}", orders=";".join(_dstr(o) for o in orders),
                 n_orders=str(len(orders)), order_qty_total=_dstr(qtot), cash_reserved_usd=f"{float(qtot * Ld):.2f}",
                 order_note=_a("; ".join(x for x in (onote, alt_txt) if x)))
        rows.append(r)
        lines.append(_a(_table_row(f"{m} chart", r["limit_price"], 100 * (1 - L / P0), delta, sv)))
        buy = (f"; BUY {' + '.join(_dstr(o) for o in orders)} {coin} at {r['limit_price']} "
               + (f"instead of the k = {alt:g} rung (replace it, do not add)" if alt is not None else
                  "(an alternative, not an extra order)") if orders else "")
        chart_lines.append(_a(f"    {label} ({CHART_NAMES[m]}): {c['label']}; " +
                              ("waits and odds are the plain level's at this depth" if _fin(sv["rh_rate"]) else
                               "no plain-level odds this far outside the M2 rungs' depths") + buy +
                              (f"; flip target {flip}" if flip else "")))
    if not computed:
        lines.append(f"  Fill odds, waits and capacity: {NOT_COMPUTED} (no desc/sheet_coin_rung.csv in the results)")
    else:
        lines += ["  Basis of the odds (Robinhood-route proxy F3; Binance spot = an upper bound):"] + basis_lines
    if chart_lines:
        lines += ["  Chart levels (shown because they were earned; each replaces the M2 rung named, never an extra "
                  "order):"] + chart_lines
    lines += ["  Orders (" + ("market-maker route" if C.route == "mm" else "exchange route") +
              f", ${C.per_rung:,.0f} per rung, good till cancelled):"] + order_lines
    lines.append(_a("  Flip target (H1 PASS under rule M): a limit sell at the target below, and sell at market "
                    "after 72 h if it has not filled" if E["flip"] else f"  Flip target: {flip_rule}"))
    if E["tradeoff"] and not any("trade-off" in x for x in extra):
        lines.append(f"  Trade-off per rung (theta_k, mu*_k of D6): {NOT_COMPUTED}")
    lines += [_a(x) for x in extra]
    return rows, lines, None, cash, deepest


def _answer_lines(R: dict, E: dict) -> list:
    """§11: the verdicts H2R, H1, H4 and the recommendation lines, first, from answer.json (coding choice 17)."""
    v = R.get("verdicts")
    if v is None:
        return [f"The answer (STINKBID_PREREG.md section 11): {NOT_COMPUTED} ({_rel(R['dir'] / 'answer.json')} has no "
                "verdicts of a complete report stage). Nothing below is a verdict; no flip target, post-fill outcome, "
                "chart level, round-number advice or best rung is shown."]
    out = ["The answer (STINKBID_PREREG.md section 11; verdicts H2R, then H1, then H4):",
           "  " + "; ".join(f"{TEST_NAMES[t]}: {v[t]}" for t in TESTS)]
    rec = (R.get("answer") or {}).get("recommendation") or []
    out += [f"  - {x.get('text', '')}" for x in rec if isinstance(x, dict)]
    if not E.get("chain"):
        out.append(f"  (No earned item of section 13 item 8 is shown: {E.get('why')}.)")
    if R.get("mode") and R["mode"] != "real":
        out.insert(0, f"*** RESULTS FROM MODE {R['mode']!r}: NOT THE STUDY'S REAL RESULTS ***")
    return out


def _fixed_sentences(R: dict, C: _Ctx) -> list:
    """§11's sentences printed with every answer: the runner's (answer.json, with their numbers), else the fixed text
    with the numbers marked not yet computed."""
    fx = (R.get("answer") or {}).get("fixed_sentences")
    if isinstance(fx, list) and fx:
        return [str(x.get("text", "")) for x in fx if isinstance(x, dict)]
    nc = f"<{NOT_COMPUTED}>"
    return [S_DISCOUNT, S_TOGETHER.format(S=nc), S_BOTTOM.format(A=nc, B=nc), S_NEWS, S_ML + " " + S_ML_NOTE,
            f"Capacity: the size cap ({NOT_COMPUTED}) and \"{S_CAP}\"."]


LEGEND = _a("Columns: limit on Robinhood's tick; depth below the reference in % and in sigma30 units (delta, "
            "recomputed after rounding); wait = median weeks to a fill if re-placed weekly / chance of no fill within "
            "a year (Kaplan-Meier, shrunk to the U-Q1 rung); Robinhood odds = fill odds per weekly bid on the "
            "Robinhood-route proxy F3 with a 95% interval widened by sqrt(phi); Binance = the Binance spot figure, an "
            "upper bound; capacity = past seller-initiated dollars printed below the level on Binance spot (median / "
            "10th percentile / Q_max = 0.25 x p10; context only on the market-maker route).")
WRAP = 118


def _wrap(lines: list) -> list:
    """Wrap prose lines longer than WRAP characters (table rows are kept whole), indenting the continuation."""
    import textwrap
    out = []
    for x in lines:
        if len(x) <= WRAP or re.match(r"  M\d", x) or x == TABLE_HEAD:
            out.append(x)
            continue
        ind = len(x) - len(x.lstrip(" "))
        sub = " " * (ind + (2 if x.lstrip().startswith("- ") else 4))
        out += textwrap.wrap(x.lstrip(" "), WRAP, initial_indent=" " * ind, subsequent_indent=sub,
                             break_long_words=False, break_on_hyphens=False) or [x]
    return out


def find_previous(sheet_dir: Path, today: pd.Timestamp) -> Path | None:
    """The most recent sheet_YYYY-MM-DD.csv dated strictly before today that holds at least one order (coding choice
    10). A sheet on which every coin was refused (a forgotten --price, a stale close) holds no order and is skipped,
    so the orders still resting from the sheet before it keep their cancel lines (prereg Addendum 2, A2.6)."""
    if not Path(sheet_dir).exists():
        return None
    cands = []
    for p in Path(sheet_dir).glob("sheet_*.csv"):
        m = re.fullmatch(r"sheet_(\d{4}-\d{2}-\d{2})\.csv", p.name)
        if m and pd.Timestamp(m.group(1)) < today:
            cands.append((pd.Timestamp(m.group(1)), p))
    for _, p in sorted(cands, reverse=True):
        try:
            prev = pd.read_csv(p, dtype=str).fillna("")
        except (OSError, ValueError):
            continue
        if _orders_of(prev) or _orders_of(prev, chart=True):
            return p
    return None


def _is_chart(row) -> bool:
    return str(row).endswith("(chart)")


def _orders_of(df: pd.DataFrame, chart: bool = False) -> dict:
    """{(coin, row): (limit string, (quantities...))} of the priced M2 rows of a sheet (chart=True: of its earned
    chart rows, the alternatives; coding choice 10)."""
    out = {}
    if df is None or not len(df):
        return out
    for r in df.fillna("").astype(str).itertuples():
        if not r.limit_price or r.refused or not r.orders or _is_chart(r.row) != chart:
            continue
        out[(r.coin, r.row)] = (r.limit_price, tuple(q for q in r.orders.split(";") if q))
    return out


def _replaced_rung(df: pd.DataFrame, coin: str, row: str) -> str | None:
    """The M2 row of `coin` nearest in depth (sigma) to the chart row `row`: the rung that alternative replaces."""
    try:
        d = df.fillna("").astype(str)
        c = d[(d["coin"] == coin) & (d["row"] == row)]
        m2 = d[(d["coin"] == coin) & d["row"].str.match(r"M2 k=") & (d["limit_price"] != "") & (d["refused"] == "")]
        if c.empty or m2.empty:
            return None
        dist = (pd.to_numeric(m2["depth_sigma"], errors="coerce") - _f(c["depth_sigma"].iloc[0])).abs()
        return None if dist.isna().all() else str(m2.loc[dist.idxmin(), "row"])
    except (KeyError, ValueError, TypeError):
        return None


def order_diff(prev: pd.DataFrame | None, new: pd.DataFrame, prev_name: str = "last week's sheet") -> pd.DataFrame:
    """R8's order diff (coding choice 10): keep / cancel / place per coin and M2 row; the earned chart levels apart
    as "alternative" rows (replace the M2 rung named, do not add), so the place lines commit the footer's cash."""
    po, no = _orders_of(prev), _orders_of(new)
    pa, na = _orders_of(prev, chart=True), _orders_of(new, chart=True)
    refused = set(new.loc[new["row"] == "(refused)", "coin"]) if len(new) else set()
    rows = []

    def fmt(coin, lim, qs):
        return f"BUY {' + '.join(qs)} {coin} at {lim}"

    def order_key(key):
        coin, row = key
        m = re.match(r"M2 k=([0-9.]+)$", row)
        return (coin, 0 if m else 1, float(m.group(1)) if m else 0.0, row)
    for key in sorted(na, key=order_key):
        coin, row = key
        rr = _replaced_rung(new, coin, row)
        tgt = (f"instead of {coin} {rr} ({fmt(coin, *no[(coin, rr)])})" if rr and (coin, rr) in no else
               "instead of one of this week's M2 rungs")
        rows.append(dict(coin=coin, row=row, action="alternative",
                         detail=f"{fmt(coin, *na[key])} {tgt}: replace that rung, do not add (not in the cash total)"
                                + ("; unchanged from last week" if pa.get(key) == na[key] else "")))
    for key in sorted(k for k in pa if na.get(k) != pa[k]):
        coin, row = key
        rr = _replaced_rung(prev, coin, row)
        rows.append(dict(coin=coin, row=row, action="alternative",
                         detail=f"last week's alternative {fmt(coin, *pa[key])} (from {prev_name}"
                                + (f", instead of {rr}" if rr else "") + "): if you placed it instead of its rung and "
                                "it is still open, cancel it"))
    alt_rows = rows
    rows = []
    for key in sorted(set(po) | set(no), key=order_key):
        coin, row = key
        if key in po and key in no:
            if po[key][0] == no[key][0] and po[key][1] == no[key][1]:
                rows.append(dict(coin=coin, row=row, action="keep", detail=fmt(coin, *no[key])))
            else:
                rows.append(dict(coin=coin, row=row, action="cancel", detail=fmt(coin, *po[key]) +
                                 f" (from {prev_name}, if still open)"))
                rows.append(dict(coin=coin, row=row, action="place", detail=fmt(coin, *no[key])))
        elif key in po:
            why = ("no new level this week (refused: see the sheet); cancel or keep at your discretion"
                   if coin in refused else "not on this week's sheet")
            rows.append(dict(coin=coin, row=row, action="cancel", detail=fmt(coin, *po[key]) +
                             f" (from {prev_name}, if still open): {why}"))
        else:
            rows.append(dict(coin=coin, row=row, action="place", detail=fmt(coin, *no[key])))
    return pd.DataFrame(rows + alt_rows, columns=["coin", "row", "action", "detail"])


def build_sheet(coins=None, prices=None, asof=None, results_dir=RES, cache_dir=CACHE, catalog=None,
                catalog_paths=None, route: str = "mm", per_rung: float = DEFAULT_Q, life: int = LIFE_D,
                refresh: bool = False, previous=None, force_price: bool = False, data: dict | None = None,
                universe=None, history=None, fetch=None, log=None, write_history: bool = True,
                refresh_dir=None) -> Sheet:
    """The level sheet (§13). Injection for tests: catalog (a DataFrame like load_catalog's), data {coin: {"d1":
    frame}} (no real data are read then), universe (month, coin, U_Q1), history (bids with coin, rung, live_from,
    life_end, t_F1, t_F3_1) or False for none, fetch (the archive fetcher of --refresh)."""
    log = log or (lambda m: None)
    if route not in ("mm", "ex"):
        raise SheetRefused("--route must be mm (market maker, the default) or ex (exchange)")
    if int(life) != LIFE_D:
        raise SheetRefused("only the weekly routine (--life 7) has per-coin fill odds in the study's outputs "
                           "(section 13: 'if re-placed weekly')")
    if not (per_rung > 0 and math.isfinite(per_rung)):
        raise SheetRefused("--per-rung must be a positive dollar amount")
    cat = catalog if catalog is not None else load_catalog(catalog_paths)
    asof = parse_asof(asof)
    prices = dict(prices or {})
    coins = list(coins) if coins else default_coins(cat)
    R = load_results(results_dir)
    E = earned(R, route)
    C = _Ctx()
    C.asof, C.R, C.E, C.cat, C.route, C.per_rung, C.refresh, C.fetch, C.log = (asof, R, E, cat, route,
                                                                               float(per_rung), refresh, fetch, log)
    C.prices, C.force_price, C.data, C.refresh_dir = prices, force_price, data, refresh_dir
    if universe is None and data is None:
        try:
            universe = sbd.universes()
        except Exception:
            universe = None
        if universe is None:
            # a clone without data/stinkbid (the user's machine): the committed membership of the last 12 months
            # (stinkbid_ref/universes_recent.csv); the flag names the month it used (A2.6)
            try:
                universe = pd.read_csv(UNIV_RECENT_FILE, dtype={"month": str, "coin": str})
                universe["U_Q1"] = universe["U_Q1"].astype(str).str.lower().isin(("true", "1"))
            except (OSError, ValueError, KeyError):
                universe = None
    C.univ = universe if isinstance(universe, pd.DataFrame) else None
    dh5s = dh5_sentence(R)
    C.knife = dh5s or f"D-H5 knife rates {NOT_COMPUTED}"
    C.outcomes = outcome_texts(R, E)
    warn = list(R.get("warnings") or []) + list(E.get("warnings") or [])
    extra_p = [c for c in prices if c not in coins]
    if extra_p:
        warn.append(f"--price given for coins not on the sheet (ignored): {', '.join(extra_p)}")
    rows, body, refused, cash, deepest = [], [], {}, 0.0, None
    for coin in coins:
        r, ln, why, c_, dp = _coin(coin, C)
        rows += r
        body += ln + [""]
        cash += c_
        if why:
            refused[coin] = why
        if dp is not None and (deepest is None or (deepest["halted"] and not dp["halted"])):
            deepest = dp
    df = pd.DataFrame(rows, columns=COLS) if rows else pd.DataFrame(columns=COLS)
    # history and the ladder footer
    if history is None:
        hist, hsrc = load_history(cache_dir, results_dir, write=write_history)
    elif history is False:
        hist, hsrc = None, f"{NOT_COMPUTED} (no history given)"
    else:
        hist, hsrc = history, "injected history"
    priced = [c for c in coins if c not in refused]
    lad = ladder_stats(hist, priced) if priced else None
    if lad is not None and lad.get("F3_1"):
        a, b = lad["F3_1"], lad.get("F1") or {}
        ladder = LADDER.format(N=f"{a['N']:.0f}", D=f"{a['D']}", S=f"{100 * a['S']:.0f}" if _fin(a["S"]) else "n/a")
        ladder += (f" [Robinhood-route proxy (F3); Binance spot: {_f(b.get('N')):.0f} days a year, "
                   f"{b.get('D', '?')} days, {100 * _f(b.get('S')):.0f}%. Worst day {a.get('day')}: {a.get('filled')} "
                   f"of {a.get('live')} live orders. History of {', '.join(lad['coins'])}: weekly k = 6/8/10 bids, "
                   f"{lad['first']}..{lad['last']} ({lad['years']:.1f} years with a live bid); {hsrc}"
                   + (f"; no history for {', '.join(lad['missing'])}" if lad["missing"] else "") + "]")
    else:
        ladder = LADDER.format(N="<n/a>", D="<n/a>", S="<n/a>") + (f" [{hsrc}]" if hsrc.startswith(NOT_COMPUTED)
                                                                     else f" [{NOT_COMPUTED} for these coins: {hsrc}]")
    # the diff against last week's sheet
    sdir = Path(results_dir) / "sheet"
    pfile = Path(previous) if previous else find_previous(sdir, _day(asof))
    prev = None
    if pfile is not None and Path(pfile).exists():
        try:
            prev = pd.read_csv(pfile, dtype=str).fillna("")
        except (OSError, ValueError):
            prev = None
    pname = Path(pfile).name if pfile is not None else "last week's sheet"
    diff = order_diff(prev, df, pname)
    # text
    head = [f"Stink-bid level sheet, {asof:%Y-%m-%d %H:%M} UTC (STINKBID_PREREG.md section 13)",
            f"Route: {'market maker (the default)' if route == 'mm' else 'exchange'}; ${per_rung:,.0f} per rung; "
            "weekly routine (7-day bids, cancelled and re-placed every Monday after 03:30 UTC)",
            f"Robinhood catalog: {cat.attrs.get('path', 'injected')}; results: {_rel(R['dir'])}"
            + (f" (mode {R['mode']})" if R.get("mode") else f" ({NOT_COMPUTED})"), NEVER, ""]
    head += _answer_lines(R, E) + [""]
    if E["passed"]:
        head += ["Post-fill outcomes (shown only for the tests that passed; the Robinhood-route proxy F3 first):"]
        head += [f"  - {C.outcomes[t]}" for t in TESTS if t in C.outcomes] + [""]
    head += [LEGEND, ""]
    if warn:
        head += [f"Warning: {w}" for w in warn] + [""]
    foot = ["Footer (section 13):", "  " + ladder,
            f"  Total cash reserved: ${cash:,.2f} for the M2 rungs above ({S_CAP}).",
            f"  Route note: {ROUTE_NOTE}"]
    foot += ["  " + s for s in _fixed_sentences(R, C)]
    if dh5s:                                       # §11's D-H5 sentence as the runner printed it (coding choice 8)
        foot.append("  " + dh5s)
    if "HYPE" in coins:
        foot.append("  " + HYPE_NOTE)
    if E["chart"] and any(c["via"] == "D10" for c in E["chart"].values()):
        foot.append(f"  Chart rows labelled '{D10_LABEL}' passed D10's fill-odds family only.")
    if E["round_number"]:
        foot.append("  Exchange route: bid one tick above round numbers (D9 earned it).")
    foot.append("  " + RH_PROXY)
    instr = ["How to use it (manual orders only):",
             "  1. " + TEST_ORDER + (f" For example: BUY {deepest['qty']} {deepest['coin']} at limit "
                                     f"{deepest['limit']} (about ${deepest['usd']:,.2f}, at least Robinhood's minimum "
                                     f"size; the k = {deepest['rung']:g} rung). Cancel it after the check."
                                     if deepest else ""),
             "  2. In the app: coin -> Trade -> Buy -> order type Limit; enter the sheet's limit price and quantity "
             "(several orders where a rung is split). Crypto limit orders rest up to 90 days on Robinhood.",
             "  3. Each week (after Monday 03:30 UTC: Sunday 10:30 pm EST / 11:30 pm EDT): run the sheet with your "
             "app's mids (--price), cancel last week's unfilled bids and enter the new ones (the order diff below "
             "lists them).",
             "  4. After a fill: " + ("enter the flip target as a limit sell and sell at market after 72 h if it has "
                                       "not filled." if E["flip"] else
                                       "the sheet shows no flip target; decide before the fill which rule governs "
                                       "the position (MoneyLine sentence above)."),
             "  5. Keep enough cash for every bid at once: fills come on the same crash day across coins."]
    dl = [f"Order diff against {pname if prev is not None else 'last week (no earlier sheet found: place every order)'}"
          + " (the M2 rungs; the place lines add up to the total cash reserved):"]
    dm, da = diff[diff["action"] != "alternative"], diff[diff["action"] == "alternative"]
    dl += [f"  {r.action:6s} {r.coin} {r.row}: {r.detail}" for r in dm.itertuples()] or ["  (no orders)"]
    if len(da):
        dl += ["Alternatives (earned chart levels: each replaces the M2 rung named, never an extra order):"]
        dl += [f"  {r.coin} {r.row}: {r.detail}" for r in da.itertuples()]
    lines = _wrap([_a(x) for x in head + body + foot + [""] + instr + [""] + dl])
    meta = dict(results=_rel(R["dir"]), mode=R.get("mode"), computed=E["computed"], earned=E, ladder=lad,
                history_source=hsrc, cash=cash, previous=str(pfile) if prev is not None else None, warnings=warn,
                catalog=cat.attrs.get("path"))
    return Sheet(asof=asof, rows=df, lines=lines, diff=diff, meta=meta, refused=refused)


def write_sheet(sh: Sheet, results_dir=RES) -> list:
    """<results>/sheet/sheet_YYYY-MM-DD.csv, .txt and diff_YYYY-MM-DD.csv (same-day reruns overwrite)."""
    d = Path(results_dir) / "sheet"
    d.mkdir(parents=True, exist_ok=True)
    day = f"{sh.asof:%Y-%m-%d}"
    out = []
    for name, write in ((f"sheet_{day}.csv", lambda p: sh.rows.to_csv(p, index=False)),
                        (f"sheet_{day}.txt", lambda p: p.write_text("\n".join(sh.lines) + "\n", encoding="ascii")),
                        (f"diff_{day}.csv", lambda p: sh.diff.to_csv(p, index=False))):
        p = d / name
        tmp = p.with_suffix(p.suffix + f".{os.getpid()}.tmp")
        write(tmp)
        os.replace(tmp, p)
        out.append(p)
    return out


# ============================================================================ CLI
def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m analysis_2026.stinkbid_sheet", add_help=True,
                                 description="The stink-bid level sheet (STINKBID_PREREG.md section 13). Never places "
                                             "orders.")
    ap.add_argument("--coins", default="", help="comma-separated coins (default: U-C, the Robinhood-tradable coins)")
    ap.add_argument("--price", action="append", default=[], help="COIN=x, the app's current mid (repeatable)")
    ap.add_argument("--per-rung", type=float, default=DEFAULT_Q, help="dollars per rung (default 1000)")
    ap.add_argument("--route", default="mm", choices=("mm", "ex"))
    ap.add_argument("--life", type=int, default=LIFE_D)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--previous", default=None)
    ap.add_argument("--results", default=None, help=f"the study's results (default {_rel(RES)})")
    ap.add_argument("--cache", default=None, help=f"the runner's engine cache (default {_rel(CACHE)})")
    ap.add_argument("--catalog", default=None)
    ap.add_argument("--asof", default=None)
    ap.add_argument("--force-price", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    return ap


def _sheet_run(a, results_dir: Path, cache_dir: Path, inj: dict, echo: bool = True) -> dict:
    """Build, print and write one sheet from parsed arguments (main and run_stage)."""
    say = (lambda m: print(_a(m), file=sys.stderr)) if echo else (lambda m: None)
    try:
        sh = build_sheet(coins=parse_coins(a.coins) or None, prices=parse_prices(a.price),
                         asof=a.asof, results_dir=results_dir, cache_dir=cache_dir,
                         catalog=inj.get("catalog"), catalog_paths=[a.catalog] if a.catalog else None,
                         route=a.route, per_rung=a.per_rung, life=a.life, refresh=a.refresh, previous=a.previous,
                         force_price=a.force_price, data=inj.get("data"), universe=inj.get("universe"),
                         history=inj.get("history"), fetch=inj.get("fetch"), log=say,
                         write_history=not a.no_write)
    except SheetRefused as e:
        say(f"REFUSED: {e}")
        return dict(rc=2, outputs=[], refused={}, why=str(e), sheet=None)
    if echo:
        print("\n".join(sh.lines))
    paths = [] if a.no_write else write_sheet(sh, results_dir)
    if echo and paths:
        print("written:\n" + "\n".join(_a("  " + _rel(p)) for p in paths))
    priced = sh.rows[(sh.rows["row"] != "(refused)") & (sh.rows["limit_price"] != "")] if len(sh.rows) else sh.rows
    return dict(rc=0 if len(priced) else 1, outputs=[str(p) for p in paths], refused=dict(sh.refused), why="",
                sheet=sh)


def main(argv=None, _inject: dict | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(_a(__doc__.split("What it prints")[0].rstrip()))
        print("\nNo arguments: nothing was written. Name the coins (--coins A,B), or pass --price / --refresh / "
              "--results to make a sheet of the default list (U-C).", file=sys.stderr)
        return 2
    if argv and argv[0] == "selftest":
        return 0 if selftest(real="--no-real" not in argv) else 1
    if argv and argv[0] == "history":
        b, src = load_history(CACHE if "--cache" not in argv else argv[argv.index("--cache") + 1],
                              RES if "--results" not in argv else argv[argv.index("--results") + 1], write=True)
        print(_a(f"ladder history: {src}" + (f"; {len(b):,} bids" if b is not None else "")))
        return 0 if b is not None else 1
    ap = _parser()
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 2
    return _sheet_run(a, Path(a.results) if a.results else RES, Path(a.cache) if a.cache else CACHE,
                      _inject or {})["rc"]


# ============================================================================ stage 8 of stinkbid_run (§14)
def synthetic_catalog(ticks: dict) -> pd.DataFrame:
    """A catalog for an injected world's coins (coding choice 18): each coin's own tick; quantity increment and
    minimum 0.0001; maximum 1e9. Labelled, so a sheet never passes it off as Robinhood's catalog."""
    rows = [dict(coin=str(c), symbol=f"{c}-USD", tradability="tradable", tradable=True,
                 price_tick_str=format(Decimal(str(t)).normalize(), "f"), qty_increment_str="0.0001",
                 min_order_size_str="0.0001", max_order_size_str="1000000000", market_orders_only=False,
                 halted=False, halted_regions="") for c, t in sorted(ticks.items())]
    cat = pd.DataFrame(rows, columns=["coin", "symbol", "tradability", "tradable", "price_tick_str",
                                      "qty_increment_str", "min_order_size_str", "max_order_size_str",
                                      "market_orders_only", "halted", "halted_regions"])
    cat.attrs["path"] = "SYNTHETIC catalog of the injected world's own ticks (not Robinhood's)"
    cat.attrs["source"] = "injected world"
    return cat


def world_inputs(world: dict, coins=None) -> dict:
    """The sheet's injected inputs from the runner's injected world (stinkbid_engine's dict: universe, coins with m1
    / d1 / tick, end; coding choice 18): the daily bars and level inputs the engine itself gives the levels module
    (stinkbid_engine.World.levels_data), the universe table, a synthetic catalog of the world's ticks, the coins (the
    U_C members of the world's last month, else every coin) and the clock (the world's end + 12 h)."""
    from analysis_2026 import stinkbid_engine as sbe
    W = sbe.World(world)
    cs = world.get("coins") or {}
    u = world.get("universe")
    coins = list(coins or [])
    if not coins:
        if isinstance(u, pd.DataFrame) and len(u) and "U_C" in u:
            m = u["month"].astype(str).str[:7]
            last = u[m == m.max()]
            coins = sorted(last.loc[last["U_C"].astype(bool), "coin"].astype(str).unique())
        if not coins and isinstance(cs, dict):
            coins = sorted(cs)
    data = {c: dict(W.levels_data(c)) for c in coins if W.has_coin(c)}
    ticks = {c: str(((cs.get(c) if isinstance(cs, dict) else None) or {}).get("tick") or "0.0001") for c in coins}
    asof = (W.end_day + pd.Timedelta(days=1, hours=12)).tz_localize("UTC")
    return dict(data=data, universe=u if isinstance(u, pd.DataFrame) else None, catalog=synthetic_catalog(ticks),
                coins=coins, asof=asof)


def run_stage(out, cache, args=(), world: dict | None = None, echo: bool = True) -> dict:
    """Stage 8 of stinkbid_run (§14; coding choice 18), in-process: the sheet of `args` (the user's sheet arguments,
    the ones after `--`) on the runner's results OUT and run cache CACHE, written to OUT/sheet/. world: the runner's
    injected world (stinkbid_engine's dict), or None for real data. A --results / --cache in args that names other
    folders is refused. Returns dict(rc, outputs, refused, why, sheet): rc 0 = written with a priced coin, 1 = every
    coin refused (written), 2 = refused as a whole (nothing written)."""
    args = [str(x) for x in (args or [])]
    out, cache = Path(out), Path(cache)
    none = dict(outputs=[], refused={}, sheet=None)
    if args and args[0] in ("selftest", "history"):
        return dict(none, rc=2, why=f"{args[0]!r} is not a sheet argument (stage 8 makes the sheet)")
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            a = _parser().parse_args(args)
    except SystemExit:
        return dict(none, rc=2, why=f"bad sheet arguments {args}: {err.getvalue().strip()[-300:]}")
    for flag, given, want in (("--results", a.results, out), ("--cache", a.cache, cache)):
        if given is not None and Path(given).resolve() != want.resolve():
            return dict(none, rc=2, why=f"{flag} {given} is not the runner's {want}: stage 8 reads and writes the "
                                        "runner's folders (coding choice 18)")
    inj = {}
    if world is not None:
        inj = world_inputs(world, parse_coins(a.coins) or None)
        a.coins = a.coins or ",".join(inj["coins"])
        a.asof = a.asof if a.asof is not None else inj["asof"]
        a.refresh = False
    return _sheet_run(a, out, cache, inj, echo=echo)


# ============================================================================ selftest (synthetic known answers)
def _flat(lines) -> str:
    """The printed text with whitespace normalized (wrapped lines joined), for the selftest's text checks."""
    return " ".join(" ".join(lines).split())


def _syn_d1(end="2026-11-17", n=400, p_end=3.0, sigma=0.05, drift=0.0, seed=0, jump_at=None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, sigma, n - 1)
    c = np.exp(np.r_[0.0, np.cumsum(r)])
    o = np.r_[c[0], c[:-1]]
    if jump_at is not None:                                     # a > 25% open jump starts a new segment
        o[jump_at:] *= 1.6
        c[jump_at:] *= 1.6
    scale = p_end / c[-1]
    c, o = c * scale, o * scale
    hi = np.maximum(o, c) * 1.01
    lo = np.minimum(o, c) * 0.99
    t = pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=n, freq="D")
    return pd.DataFrame(dict(open_time=t, open=o, high=hi, low=lo, close=c, volume=1e6, quote_volume=1e6 * c,
                             trades=1000))


def _oracle_sigma(k: pd.DataFrame, d0) -> float:
    c = k[k["open_time"].dt.tz_localize(None).dt.normalize() <= d0]["close"].to_numpy(float)[-31:]
    return float(np.std(np.diff(np.log(c)), ddof=1))


def _oracle_floor(x: float, tick: str) -> Decimal:
    t = Decimal(tick)
    return (Decimal(x) / t).to_integral_value(rounding=ROUND_FLOOR) * t


STUB_DH5 = {"U_Q1": {"primary": dict(rate_q1=0.12, rate_rest=0.21, b=0.065, ci95=[-0.01, 0.14], n=500, G_coin=40,
                                      G_quarter=24, df=23)},
            "U_Q1_12": {"primary": dict(rate_q1=0.15, rate_rest=0.20, b=0.041, ci95=[-0.02, 0.10], n=520, G_coin=42,
                                         G_quarter=24, df=23)}}
STUB_T = ("2026-11-18 10:00:00 UTC", "2026-11-18 10:02:00 UTC", "2026-11-18 10:04:00 UTC")  # report, desc, explore


def _stub_markers(d: Path, mode: str = "real", stale=()):
    """The runner's stage markers (stinkbid_run.write_marker's fields) for data .. explore; the stages in `stale`
    moved to stages/stale/ as stinkbid_run.invalidate leaves them after a rerun."""
    sd = d / "stages"
    (sd / "stale").mkdir(parents=True, exist_ok=True)
    fin = dict(zip(("report", "desc", "explore"), STUB_T))
    for st in ("data", "controls", "fcount", "primary", "report", "desc", "explore"):
        m = dict(stage=st, complete=True, mode=mode, started="", finished=fin.get(st, "2026-11-18 09:00:00 UTC"))
        f = (sd / "stale" / f"{st}.20261118T120000.json") if st in stale else (sd / f"{st}.json")
        f.write_text(json.dumps(m))
        if st in stale and (sd / f"{st}.json").exists():
            (sd / f"{st}.json").unlink()


def _stub_results(d: Path, verdicts: dict | None = None, bot: bool = False, binance_only: dict | None = None,
                  prw: dict | None = None, level: float = 0.0167, d10: tuple = (), d9: bool = False,
                  q: float = 0.5, slope: float = 0.01, coin_rows: bool = True, mode: str = "real",
                  coins=("NEAR",), stages: bool = False) -> Path:
    """A results folder shaped like stinkbid_run's outputs, written in the runner's order: answer.json (report),
    primary/primary.json, desc/sheet_coin_rung.csv, sheet_inputs.json and explore/depth_gradient.csv (explore);
    stages=True adds the runner's completion markers (stages/<stage>.json)."""
    from analysis_2026 import stinkbid_desc as sbdesc
    if d.exists():
        shutil.rmtree(d)
    (d / "desc").mkdir(parents=True)
    (d / "explore").mkdir()
    (d / "primary").mkdir()
    v = verdicts or dict(H2R="INCONCLUSIVE", H1="INCONCLUSIVE", H4="INCONCLUSIVE")
    prw = prw or {"M4": 0.004, "M5b": 0.03, "M6": 0.5, "M7": 0.9}
    methods = [dict(method=m, p_rw=p, b=0.01, n=50) for m, p in prw.items()]
    fam = [dict(test=m, estimate=0.012, p=0.001 if m in d10 else 0.6, rejected=m in d10) for m in prw] + \
          [dict(test="D9", estimate=0.02, p=0.001 if d9 else 0.6, rejected=d9)]
    d6 = [dict(rule=rule, rung=k, theta=(0.01 if rule == "F3_1" else 0.02) * k / 8, theta_lo=-0.05, theta_hi=0.07,
               theta_n=120, theta_G=31, theta_gstar=9.4, theta_unit="month-block",
               mu_star=0.03 * k / 8, mu_star_lo=-0.2, mu_star_hi=0.3) for rule in ("F1", "F3_1") for k in RUNGS]
    flags = dict(show_flip_target=v["H1"] == "PASS", h1_bot_only=bot, binance_only=binance_only or {},
                 index_dips_only=False, run_on_robinhood=False)
    passed = [t for t in TESTS if v[t] == "PASS"]
    rec = [dict(key=f"{t}_{v[t]}", text=f"recommendation for {t} {v[t]}") for t in TESTS]
    fx = [dict(key="DISCOUNT", text=S_DISCOUNT), dict(key="TAIL_NEWS", text=S_NEWS)]
    h4 = dict(argmax="M4", holm_level=level, verdict=v["H4"], methods=methods,
              chart_methods_shown=[m for m, p in prw.items() if v["H4"] == "PASS" and p < level])
    nums = {t: dict(X=0.031, lo=0.004, hi=0.058, N=900, G=40, gstar=14.2, M=0.03) for t in TESTS}
    nums["H1"]["R"], nums["H4"]["j"] = 0.012, "M4"
    ans = dict(mode=mode, generated=STUB_T[0], verdicts=v, flags=flags, tests_passed=passed, h4=h4,
               numbers=dict(tests=nums), recommendation=rec, fixed_sentences=fx,
               descriptive_sentences=[sbdesc.sentence_dh5(STUB_DH5)], holm={t: dict(level=level) for t in TESTS})
    si = dict(mode=mode, generated=STUB_T[2], verdicts=v, flags=flags, tests_passed=passed, h4=h4, d10_family=fam,
              chart_methods_by_d10=[m for m in d10], round_number_advice=d9, depth_gradient_q=q,
              best_rung_allowed=q < 0.10, d6=d6, dh5=STUB_DH5, capacity=[], fixed_sentences=fx, recommendation=rec)
    prim = dict(rows={t: dict(unit="month-block") for t in TESTS},
                beside={t: dict(F3_1=dict(estimate=0.027, ci_lo=0.001, ci_hi=0.053, n=800, G=35, gstar=11.2,
                                          unit="month-block")) for t in TESTS})
    (d / "answer.json").write_text(json.dumps(ans))
    (d / "primary" / "primary.json").write_text(json.dumps(prim))
    (d / "sheet_inputs.json").write_text(json.dumps(si))
    if stages:
        _stub_markers(d, mode)
    pd.DataFrame([dict(table="depth gradient", row="slope", rule="F1", estimate=slope, q_bh=q, is_gradient=True),
                  dict(table="depth gradient", row="slope", rule="F3_1", estimate=-slope, q_bh=0.9,
                       is_gradient=False)]).to_csv(d / "explore" / "depth_gradient.csv", index=False)
    if coin_rows:
        _stub_coin_rung(coins).to_csv(d / "desc" / "sheet_coin_rung.csv", index=False)
    return d


POOL = {6.0: (0.07, 9.0, 0.003), 8.0: (0.036, 16.0, 0.07), 10.0: (0.024, 25.0, 0.22)}   # rate, median wk, no fill
OWN = {6.0: (20, 8.0, 0.0), 8.0: (10, 15.0, 0.05), 10.0: (6, float("nan"), 0.30)}       # fills, median, no fill


def _stub_coin_rung(coins=("NEAR",)) -> pd.DataFrame:
    rows = []
    for rule, bump in (("F3_1", 1.0), ("F1", 1.1)):
        for k in RUNGS:
            p, med, nf = POOL[k]
            rows.append(dict(coin="ALL", rung=k, rule=rule, bids=10000, fills=int(10000 * p * bump), episodes=60,
                             rate=p * bump, rate_shrunk=p * bump, wilson_lo=p * bump * 0.6, wilson_hi=p * bump * 1.5,
                             phi=7.7, p_pool=p * bump, median_wait_weeks=med, p_no_fill_year=nf, km_starts=10000,
                             C_p50=2e6, C_p10=2e5, Q_max=5e4))
            for coin in coins:
                x, mc, nfc = OWN[k]
                n = 300
                rows.append(dict(coin=coin, rung=k, rule=rule, bids=n, fills=x, episodes=x - 1, rate=x / n,
                                 rate_shrunk=(x + 52 * p * bump) / (n + 52), wilson_lo=0.5 * x / n, wilson_hi=2 * x / n,
                                 phi=7.7, p_pool=p * bump, median_wait_weeks=mc, p_no_fill_year=nfc, km_starts=n,
                                 C_p50=4e5, C_p10=4e4, Q_max=1e4))
    return pd.DataFrame(rows)


def _world(seed: int = 3) -> dict:
    """Synthetic coins on the real catalog's ticks: NEAR, SOL, AAVE, HYPE (short spot history), PEPE (a tick coarse
    against sigma: V15), RISE (a rising series), FALL (a falling one; not in the catalog)."""
    return {"NEAR": {"d1": _syn_d1(p_end=3.0, sigma=0.05, seed=seed)},
            "SOL": {"d1": _syn_d1(p_end=150.0, sigma=0.045, seed=seed + 1)},
            "AAVE": {"d1": _syn_d1(p_end=180.0, sigma=0.05, seed=seed + 2)},
            "HYPE": {"d1": _syn_d1(p_end=40.0, sigma=0.06, seed=seed + 3, n=55)},
            "PEPE": {"d1": _syn_d1(p_end=2.0e-6, sigma=0.01, seed=seed + 4)},
            "LINK": {"d1": _syn_d1(p_end=20.0, sigma=0.002, drift=0.01, seed=seed + 5)},
            "UNI": {"d1": _syn_d1(p_end=8.0, sigma=0.002, drift=-0.01, seed=seed + 6)}}


def _univ() -> pd.DataFrame:
    return pd.DataFrame([dict(month="2026-11", coin=c, U_Q1=c in ("NEAR", "SOL", "LINK")) for c in
                         ("NEAR", "SOL", "AAVE", "PEPE", "LINK", "UNI", "HYPE")])


def _syn_bids(coins=("NEAR", "SOL"), weeks=60, start="2025-01-06 03:30", fills=None) -> pd.DataFrame:
    """Weekly k = 6/8/10 bids (one chain per coin and rung) with fills {(coin, rung, week): (t_F1 offset minutes,
    t_F3_1 offset or None)}."""
    t00 = int(pd.Timestamp(start, tz="UTC").value // 60_000_000_000)
    rows = []
    for coin in coins:
        for k in RUNGS:
            for w in range(weeks):
                t0 = t00 + w * WEEK_M
                f = (fills or {}).get((coin, k, w))
                rows.append(dict(coin=coin, rung=k, variant=f"M2 k={k:g}", t0=t0, live_from=t0 + 1,
                                 life_end=t0 + WEEK_M, t_F1=t0 + f[0] if f else -1,
                                 t_F3_1=(t0 + f[1]) if f and f[1] is not None else -1))
    return pd.DataFrame(rows)


def _t_review(say, base: Path, cat: pd.DataFrame, W: dict, U: pd.DataFrame, asof: pd.Timestamp):
    """Regression checks for the nine findings of the sheet review (stale inputs, NaN rungs in the V15 re-read, the
    stage-8 contract, chart rows in the order diff, interval units, the D-H5 sentence, the H4-only wording,
    --no-write and a malformed --asof)."""
    from analysis_2026 import stinkbid_desc as sbdesc
    kw = dict(catalog=cat, data=W, universe=U, history=False)

    def m2(sh):
        return sh.rows[sh.rows["row"].str.startswith("M2")]

    def chart(sh):
        return sh.rows[sh.rows["row"].str.endswith("(chart)")]
    # ---- (1) stale inputs: only answer.json gives the answer; earned items need report -> desc -> explore current
    v_old = dict(H2R="INCONCLUSIVE", H1="PASS", H4="PASS")
    d = _stub_results(base / "rv_stale", verdicts=v_old, d10=("M6",), stages=True)
    sh = build_sheet(["NEAR"], {}, asof, d, base / "nocache", **kw)
    assert (m2(sh)["flip_target"] != "").all() and set(chart(sh)["row"]) == {"M4 N=90 buffer=0.5 (chart)", "M6 (chart)"}
    assert sh.meta["earned"]["chain"] and not sh.meta["warnings"], sh.meta["warnings"]
    ans = json.loads((d / "answer.json").read_text())        # `report --rerun`: a new answer, H1 no longer passes
    ans["verdicts"]["H1"], ans["flags"]["show_flip_target"] = "INCONCLUSIVE", False
    ans["tests_passed"], ans["generated"] = ["H4"], "2026-11-18 11:00:00 UTC"
    (d / "answer.json").write_text(json.dumps(ans))
    _stub_markers(d, stale=("desc", "explore"))             # stinkbid_run.invalidate: later markers to stages/stale/
    sh = build_sheet(["NEAR"], {}, asof, d, base / "nocache", **kw)
    e, ft = sh.meta["earned"], _flat(sh.lines)
    assert e["verdicts"] == ans["verdicts"] and not e["chain"] and not e["flip"] and not e["passed"], e
    assert (sh.rows["flip_target"] == "").all() and chart(sh).empty                  # H4 PASS: still no chart row
    assert m2(sh)["post_fill_outcomes"].str.startswith("not shown: the study's stages desc, explore are not "
                                                      "complete").all()
    assert (m2(sh)["rh_fill_odds_week"] == NOT_COMPUTED).all() and (m2(sh)["theta_k"] == NOT_COMPUTED).all()
    assert "Flip (H1): INCONCLUSIVE" in ft and "Flip (H1): PASS" not in ft and "Post-fill outcomes" not in ft
    assert any("desc, explore are not complete" in w and "for the current answer" in w for w in sh.meta["warnings"])
    assert m2(sh)["knife_rates_dh5"].str.startswith("Descriptive only. A year after a fill").all()  # report's own
    shutil.rmtree(d / "stages")                             # the same files without markers: the stamps decide
    sh = build_sheet(["NEAR"], {}, asof, d, base / "nocache", **kw)
    assert not sh.meta["earned"]["chain"] and "generated" in sh.meta["earned"]["why"] and \
        (sh.rows["flip_target"] == "").all()
    d2 = _stub_results(base / "rv_incons", verdicts=v_old, stages=True)
    si = json.loads((d2 / "sheet_inputs.json").read_text())
    si["verdicts"]["H1"] = "NO EDGE"                        # every marker complete, but the files disagree
    (d2 / "sheet_inputs.json").write_text(json.dumps(si))
    sh = build_sheet(["NEAR"], {}, asof, d2, base / "nocache", **kw)
    assert (sh.rows["flip_target"] == "").all() and chart(sh).empty and not sh.meta["earned"]["passed"]
    assert any("differ from answer.json's" in w for w in sh.meta["warnings"])
    d3 = _stub_results(base / "rv_mode", verdicts=v_old, stages=True)
    _stub_markers(d3, mode="real")
    m_ = json.loads((d3 / "stages" / "desc.json").read_text())
    (d3 / "stages" / "desc.json").write_text(json.dumps(dict(m_, mode="injected:other")))
    sh = build_sheet(["NEAR"], {}, asof, d3, base / "nocache", **kw)
    assert (sh.rows["flip_target"] == "").all() and (m2(sh)["rh_fill_odds_week"] == NOT_COMPUTED).all()
    say("  review (1) stale inputs: after a report rerun (desc / explore markers stale, sheet_inputs.json still saying "
        "H1 PASS) the answer is answer.json's, no flip target, outcome or chart row is shown, the desc items read "
        "'not yet computed' and the warning says so; without markers the generated stamps decide; files that "
        "disagree, or a desc marker of another mode, show nothing earned")

    # ---- (2) V15's re-read: a rung whose median is not reached stays not reached; no extrapolation past a NaN
    def tab(w, r=(0.07, 0.036, 0.024), lb=(NAN, NAN, NAN)):
        return pd.DataFrame(dict(rung=list(RUNGS), rh_rate=list(r), rh_lo=0.0, rh_hi=0.1, bn_rate=0.05,
                                 wait_median=list(w), wait_lb=list(lb), no_fill=[0.0, 0.05, 0.3]))
    cases = [((8, 15, INF), 6.5, ("v", 8 + 0.5 * 3.5)), ((8, 15, INF), 8.2, ("lb", 15)), ((8, 15, INF), 10.4, ("inf",)),
             ((8, 15, INF), 10.9, ("inf",)), ((8, NAN, NAN), 8.18, ("nan",)), ((8, NAN, NAN), 10.19, ("nan",)),
             ((8, 15, NAN), 9.0, ("lb", 15)), ((8, 15, 25), 10.5, ("v", 27.5)), ((8, 15, 25), 5.5, ("v", 6.25)),
             ((INF, INF, INF), 6.3, ("inf",)), ((INF, INF, INF), 5.5, ("nan",)), ((8, 15, 25), 11.2, ("nan",))]
    for w, dl_, want in cases:
        g = at_depth(tab(w), dl_)
        got = g["wait_median"]
        ok = {"v": lambda: abs(got - want[-1]) < 1e-12, "lb": lambda: math.isnan(got) and g["wait_lb"] == want[-1],
              "inf": lambda: got == INF, "nan": lambda: math.isnan(got) and math.isnan(g["wait_lb"])}[want[0]]()
        assert ok, (w, dl_, want, g)
    g = at_depth(tab((8, NAN, NAN), lb=(NAN, 15.0, NAN)), 8.5)
    assert math.isnan(g["wait_median"]) and g["wait_lb"] == 15.0
    assert math.isnan(at_depth(tab((8, 15, 25), r=(0.07, 0.036, NAN)), 8.5)["rh_rate"])        # NaN rung: no value
    assert math.isnan(at_depth(tab((8, 15, 25), r=(0.07, 0.036, NAN)), 10.5)["rh_rate"])
    assert abs(at_depth(tab((8, 15, 25)), 10.9)["rh_rate"] - (0.024 - 0.9 * 0.006)) < 1e-12        # 1-sigma cap
    sw = shrink_waits(None, dict(median_wait_weeks=NAN, km_starts=10000, p_no_fill_year=0.6))
    assert sw["median"] == INF and "U-Q1 rung" in sw["median_note"]
    sw = shrink_waits(dict(median_wait_weeks=8.0, km_starts=300, p_no_fill_year=0.2),
                      dict(median_wait_weeks=NAN, km_starts=10000, p_no_fill_year=0.6))
    assert math.isnan(sw["median"]) and sw["median_lb"] == 8.0
    d = _stub_results(base / "rv_reread", coins=("PEPE",))                         # PEPE's own k = 10 not reached
    sh = build_sheet(["PEPE"], {}, asof, d, base / "nocache", **kw)
    rr = sh.rows.set_index("row")
    w_ = 300 / 352
    y6, y8 = w_ * 8 + (1 - w_) * 9, w_ * 15 + (1 - w_) * 16
    d6_ = float(rr.loc["M2 k=6", "depth_sigma"])
    assert all("read at delta" in rr.loc[f"M2 k={k:g}", "fill_odds_note"] for k in RUNGS)
    assert abs(float(rr.loc["M2 k=6", "median_weeks_to_fill"]) - (y6 + (d6_ - 6) * (y8 - y6) / 2)) < 0.051
    assert rr.loc["M2 k=8", "median_weeks_to_fill"] == f"at least {y8:.1f}"
    assert rr.loc["M2 k=10", "median_weeks_to_fill"] == "not reached"
    assert "the coin's own Kaplan-Meier median is not reached" in rr.loc["M2 k=10", "wait_basis"] and \
        "not at this depth either" in rr.loc["M2 k=10", "wait_basis"]
    say(f"  review (2) V15 re-read: {len(cases) + 6} at_depth / shrinkage cases against hand values (interpolation "
        "only between two finite bracketing rungs, extrapolation only from a finite pair within 1 sigma, 'not "
        "reached' at or beyond a not-reached rung, 'at least' between); PEPE end to end: k = 6 interpolated, k = 8 "
        f"'at least {y8:.1f}', k = 10 'not reached' (was 23.6)")

    # ---- (3) stage 8 of stinkbid_run: the runner's folders, the default list, an injected engine world in-process
    from analysis_2026 import stinkbid_engine as sbe
    wd = sbe.synth_world(n_coins=2, days=60, start="2026-08-01", seed=7, index=False)
    out, cache = _stub_results(base / "rv_stage", coins=("SYN0", "SYN1")), base / "rv_stage_cache"
    r = run_stage(out, cache, [], world=wd, echo=False)
    day = (pd.Timestamp(wd["end"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    assert r["rc"] == 0 and sorted(Path(p).name for p in r["outputs"]) == [f"diff_{day}.csv", f"sheet_{day}.csv",
                                                                           f"sheet_{day}.txt"], r
    s = pd.read_csv(out / "sheet" / f"sheet_{day}.csv", dtype=str).fillna("")
    Wd = sbe.World(wd)
    for coin in ("SYN0", "SYN1"):
        k_ = Wd.d1(coin)
        c_ = k_["close"].to_numpy(float)[-31:]
        sig, P0 = float(np.std(np.diff(np.log(c_)), ddof=1)), float(c_[-1])
        for rung in RUNGS:
            row = s[(s.coin == coin) & (s.row == f"M2 k={rung:g}")].iloc[0]
            assert Decimal(row["limit_price"]) == _oracle_floor(P0 * math.exp(-rung * sig), "0.0001"), (coin, rung)
    assert "SYNTHETIC catalog" in (out / "sheet" / f"sheet_{day}.txt").read_text()
    n_files = len(list((out / "sheet").glob("*")))
    r = run_stage(out, cache, ["--results", str(base / "elsewhere")], world=wd, echo=False)
    assert r["rc"] == 2 and "is not the runner's" in r["why"] and len(list((out / "sheet").glob("*"))) == n_files
    assert run_stage(out, cache, ["--coins", "SYN1", "--results", str(out)], world=wd, echo=False)["rc"] == 0
    assert run_stage(out, cache, ["selftest"], echo=False)["rc"] == 2
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = main(["--results", str(base / "rv_folders"), "--cache", str(base / "nocache"), "--asof", str(asof),
                   "--no-write"], _inject=kw)                # only the folders: the default list, a sheet
    assert rc == 0 and not (base / "rv_folders").exists()
    say("  review (3) stage 8: run_stage(OUT, CACHE, args, world) prices an injected engine world in-process (levels "
        "= oracle on World.d1, synthetic catalog labelled, files in OUT/sheet), refuses a --results naming another "
        "folder (exit 2, nothing written); the CLI with only --results / --cache makes the default-list sheet")

    # ---- (4) the order diff: chart levels are alternatives, never place / cancel; the place lines = the cash total
    d = _stub_results(base / "rv_diff", verdicts=dict(H2R="INCONCLUSIVE", H1="INCONCLUSIVE", H4="PASS"),
                      d10=("M5b",), coins=("NEAR", "SOL", "AAVE"))
    sh = build_sheet(["NEAR", "SOL", "AAVE"], {}, asof, d, base / "nocache", catalog=cat, data=W, universe=U,
                     history=False, per_rung=1000.0)
    dd, rows = sh.diff, sh.rows
    ch = chart(sh)
    ch = ch[ch["limit_price"] != ""]                          # a method that abstains this week has no order
    assert len(ch) >= 3 and not dd[dd["row"].str.endswith("(chart)")]["action"].isin(["place", "cancel"]).any()
    pl = dd[dd["action"] == "place"]
    cash_pl = sum(float(sum(Decimal(q) for q in r_.detail.split("BUY ", 1)[1].rsplit(f" {r_.coin} at", 1)[0]
                            .split(" + ")) * Decimal(r_.detail.rsplit(" at ", 1)[1])) for r_ in pl.itertuples())
    assert abs(cash_pl - sh.meta["cash"]) < 0.005 and len(pl) == 9, (cash_pl, sh.meta["cash"])
    for r_ in ch.itertuples():
        mm = rows[(rows.coin == r_.coin) & rows.row.str.startswith("M2")]
        near = mm.iloc[(mm["depth_sigma"].astype(float) - float(r_.depth_sigma)).abs().argmin()]
        alt = dd[(dd.coin == r_.coin) & (dd.row == r_.row)].iloc[0]
        assert alt.action == "alternative" and f"instead of {r_.coin} {near.row} " in alt.detail, alt.detail
        assert f"an alternative to the {near.row} rung" in r_.order_note
    prev = rows.copy()
    i_ = prev.index[prev["row"].str.endswith("(chart)")][0]
    prev.loc[i_, "limit_price"] = "0.5"                      # last week's alternative at another price
    (d / "sheet").mkdir(exist_ok=True)
    prev.to_csv(d / "sheet" / "sheet_2026-11-11.csv", index=False)
    sh2 = build_sheet(["NEAR", "SOL", "AAVE"], {}, asof, d, base / "nocache", catalog=cat, data=W, universe=U,
                      history=False, per_rung=1000.0)
    d2_ = sh2.diff
    assert (d2_[d2_["action"] != "alternative"]["action"] == "keep").all() and len(d2_[d2_["action"] == "keep"]) == 9
    lw = d2_[d2_["detail"].str.startswith("last week's alternative")]
    assert len(lw) == 1 and "at 0.5" in lw["detail"].iloc[0] and "cancel it" in lw["detail"].iloc[0]
    assert "Alternatives (earned chart levels" in _flat(sh2.lines)
    say(f"  review (4) order diff: {len(ch)} earned chart rows listed as alternatives naming the M2 rung nearest in "
        f"depth (oracle), none as place / cancel; the place lines commit ${cash_pl:,.2f} = the footer's total; last "
        "week's changed alternative -> 'cancel it if you placed it'")

    # ---- (5) every interval states its cluster unit, G and G* (§12)
    d = _stub_results(base / "rv_units", verdicts=dict(H2R="PASS", H1="INCONCLUSIVE", H4="INCONCLUSIVE"))
    sh = build_sheet(["NEAR"], {}, asof, d, base / "nocache", **kw)
    r0 = m2(sh).iloc[0]
    assert r0["theta_k_ci"].endswith("120 fills, month-block clusters G = 31, G* = 9.4")
    assert r0["mu_star_k_ci"].endswith("from theta_k's interval (120 fills, month-block clusters G = 31, G* = 9.4)")
    cis = re.findall(r"\(95% CI [^()]*\)", r0["post_fill_outcomes"])
    assert len(cis) == 2 and all(re.search(r"clusters G = \d+, G\* = \d", x) for x in cis), cis
    assert "800 fills, month-block clusters G = 35, G* = 11.2" in cis[0] and "G = 40, G* = 14.2" in cis[1]
    dh5s = dh5_sentence(load_results(d))                     # the runner's sentence: its clusters close the sentence
    assert "two-way coin x quarter clusters, G_coin = 40, G_quarter = 24" in dh5s
    ft = _flat(sh.lines).replace(dh5s, "")
    ends = [m_.end() for m_ in re.finditer(r"[-+]?[0-9.]+% to [-+]?[0-9.]+%", ft)]
    segs = [ft[e_:(ends[i + 1] if i + 1 < len(ends) else len(ft))][:110] for i, e_ in enumerate(ends)]
    assert len(ends) == 8 and all("G =" in x and "G* =" in x for x in segs), segs   # 2 post-fill + 3 x (theta, mu*)
    say("  review (5) intervals: theta_k and mu*_k (carried from theta_k) and both post-fill intervals (F3 and "
        "Binance) state their cluster unit, G and G*, in the CSV and in the printed text")

    # ---- (6) §11's D-H5 sentence in full (12-month row; the real-revenue clause while U-Q2 is not built)
    d = _stub_results(base / "rv_dh5")
    sh = build_sheet(["NEAR"], {}, asof, d, base / "nocache", **kw)
    want = sbdesc.sentence_dh5(STUB_DH5)
    pre = " ".join((ROOT / "analysis_2026" / "STINKBID_PREREG.md").read_text().split())
    for frag in ("Descriptive only. A year after a fill,", "Neither LUNA (kept out by listing age) nor FTT (kept out "
                 "by Binance volume rank) was in the large, long-listed group, so this says nothing about fraud "
                 "collapses of large coins.", "In the 12-month row, where LUNA is included, the gap was",
                 "The study did not test a real-revenue filter."):
        assert frag in pre and frag in want, frag
    assert want in _flat(sh.lines) and (sh.rows["knife_rates_dh5"] == want).all()
    ans = json.loads((d / "answer.json").read_text())
    ans["descriptive_sentences"] = []                        # the fallback: built from sheet_inputs.json's dh5
    (d / "answer.json").write_text(json.dumps(ans))
    sh = build_sheet(["NEAR"], {}, asof, d, base / "nocache", **kw)
    assert want in _flat(sh.lines) and (sh.rows["knife_rates_dh5"] == want).all()
    say("  review (6) D-H5: the footer and column 7 print the runner's sentence verbatim (U-Q1 and 12-month rows, "
        "'The study did not test a real-revenue filter.'; every fixed clause verbatim in section 11), also when "
        "rebuilt from sheet_inputs.json")

    # ---- (7) only H4 passed: the M2 rows say so; a D10-only chart row too
    d = _stub_results(base / "rv_h4", verdicts=dict(H2R="INCONCLUSIVE", H1="NO EDGE", H4="PASS"), d10=("M6",))
    sh = build_sheet(["NEAR"], {}, asof, d, base / "nocache", **kw)
    assert m2(sh)["post_fill_outcomes"].str.startswith("not shown on the M2 rungs: only H4 passed").all()
    c4 = chart(sh).set_index("row")
    assert c4.loc["M4 N=90 buffer=0.5 (chart)", "post_fill_outcomes"].startswith("H4 PASS")
    assert c4.loc["M6 (chart)", "post_fill_outcomes"].startswith("not shown for this level: only H4 passed")
    assert "no test passed" not in " ".join(sh.rows["post_fill_outcomes"])
    say("  review (7) only H4 passed: the M2 rows say its outcome belongs to the chart levels it earned (not 'no test "
        "passed'); the H4 chart row shows it; a D10-only chart row says why it does not")

    # ---- (8) --no-write writes nothing, not even the ladder history (a run cache present)
    run = base / "rv_cache" / "fcount" / "P1__U_C"
    run.mkdir(parents=True)
    Bc = _syn_bids(fills={("NEAR", 6.0, 3): (100, 200)}).assign(program="P1", universe="U_C", method="M2", real=True)
    Bc["bid_id"] = np.arange(len(Bc))
    Bc.drop(columns=["t_F1", "t_F3_1"]).to_parquet(run / "bids.parquet")
    Bc[Bc.t_F1 >= 0][["bid_id", "coin", "rung", "t_F1", "t_F3_1"]].to_parquet(run / "fills.parquet")
    (run / "done.json").write_text("{}")
    d = _stub_results(base / "rv_nowrite")
    before = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
    argv = ["--coins", "NEAR", "--results", str(d), "--cache", str(base / "rv_cache"), "--asof", str(asof)]
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = main(argv + ["--no-write"], _inject=dict(catalog=cat, data=W, universe=U))
    after = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
    assert rc == 0 and after == before, sorted(set(after) - set(before))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = main(argv, _inject=dict(catalog=cat, data=W, universe=U))
    assert rc == 0 and (d / "sheet" / HISTORY_FILE).exists()                  # positive control
    say("  review (8) --no-write: nothing written under --results with a run cache present (without it the sheet and "
        "the ladder history are written)")

    # ---- (9) a malformed --asof is a bad argument: exit 2, no traceback, nothing written
    for bad in ("notadate", "", "2026-13-45"):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = main(["--coins", "NEAR", "--price", "NEAR=3.0", "--asof", bad, "--results", str(base / "rv_asof")],
                      _inject=kw)
        assert rc == 2 and "REFUSED: --asof" in err.getvalue() and not (base / "rv_asof").exists(), (bad, rc)
    say("  review (9) --asof 'notadate', '' and '2026-13-45': refused as bad arguments (exit 2), nothing written")


def selftest(real: bool = True) -> bool:
    t_all = time.time()
    say = lambda m: print(m, flush=True)
    timings = {}
    base = SCRATCH / "selftest"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    cat = load_catalog()
    W, U = _world(), _univ()
    asof = pd.Timestamp("2026-11-18 12:00", tz="UTC")
    d0 = pd.Timestamp("2026-11-17")

    # ---- 1. fixed texts verbatim in the frozen pre-registration
    t = time.time()
    pre = " ".join((ROOT / "analysis_2026" / "STINKBID_PREREG.md").read_text().split())
    for name, s in (("HYPE note", HYPE_NOTE), ("route note", ROUTE_NOTE), ("red MoneyLine", ML_RED),
                    ("D10 label", D10_LABEL), ("flip time stop", FLIP_STOP), ("bot sentence", BOT_ONLY),
                    ("discount", S_DISCOUNT), ("news", S_NEWS), ("MoneyLine", S_ML), ("capacity", S_CAP),
                    ("ladder", LADDER.format(N="N", D="D", S="S")), ("together", S_TOGETHER.format(S="S")),
                    ("bottom", S_BOTTOM.format(A="A", B="B"))):
        assert " ".join(s.split()) in pre, f"{name} is not verbatim in STINKBID_PREREG.md"
    say("  texts: 13 fixed sentences verbatim in STINKBID_PREREG.md (HYPE note, route note, footer, section 11)")
    timings["texts"] = time.time() - t

    # ---- 2. catalog: order of the saved copies, refusal without it, coins it does not price
    t = time.time()
    assert cat.attrs["path"].startswith("analysis_2026/stinkbid_ref/"), cat.attrs["path"]
    alt = load_catalog([base / "none.json", CATALOG_PATHS[1]]) if CATALOG_PATHS[1].exists() else cat
    assert alt[["coin", "price_tick_str"]].equals(cat[["coin", "price_tick_str"]])
    try:
        load_catalog([base / "none.json", base / "none2.json"])
        raise AssertionError("no catalog must refuse")
    except CatalogMissing:
        pass
    (base / "bad.json").write_text('{"results": [{"asset_currency": "X"}]}')
    try:
        load_catalog([base / "bad.json"])
        raise AssertionError("an unreadable catalog must refuse")
    except CatalogMissing:
        pass
    for c, frag in (("LIT", "ticker reuse"), ("POL", "not tradable"), ("USDC", "only market orders"),
                    ("FAKECOIN", "not in the saved Robinhood catalog")):
        r, why = catalog_row(cat, c)
        assert r is None and frag in why, (c, why)
    rdir = _stub_results(base / "res_cat")
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        rc = main(["--coins", "NEAR", "--price", "NEAR=3.0", "--catalog", str(base / "none.json"), "--results",
                   str(rdir), "--asof", str(asof)], _inject=dict(data=W, universe=U, history=False))
    assert rc == 2 and "REFUSED" in err.getvalue() and not (rdir / "sheet").exists(), (rc, err.getvalue())
    say("  catalog: committed copy first (data/stinkbid/ref identical); no catalog / unreadable catalog -> refused, "
        "CLI exit 2, nothing written; LIT (ticker reuse), POL (untradable), USDC (market orders only), unknown -> "
        "not priced")
    # (A2.6) a clone without data/stinkbid (the user's machine): the committed U-C list and recent membership
    real_uc = sbd.u_c_coins

    def _no_data():
        raise FileNotFoundError("data/stinkbid is not on this machine")
    try:
        sbd.u_c_coins = _no_data
        dc = default_coins(cat)
    finally:
        sbd.u_c_coins = real_uc
    committed = pd.read_csv(U_C_FILE, dtype=str)["coin"].tolist()
    assert dc == committed and len(dc) == 74 and "LIT" not in dc and "USDC" not in dc, dc[:5]
    ur = pd.read_csv(UNIV_RECENT_FILE, dtype={"month": str, "coin": str})
    ur["U_Q1"] = ur["U_Q1"].astype(str).str.lower().isin(("true", "1"))
    last_m = max(ur["month"])
    some_q1 = ur[(ur["month"] == last_m) & ur["U_Q1"]]["coin"].iloc[0]
    assert uq1_flag(ur, some_q1, "2027-01") == ("yes", last_m) and uq1_flag(ur, "NOSUCHCOIN", last_m)[0] == "no"
    say(f"  clone without data/: default list = the committed U-C list ({len(dc)} coins), the U-Q1 flag from the "
        f"committed membership (latest month {last_m})")
    timings["catalog"] = time.time() - t

    # ---- 3. orders: HYPE 0.001 / 7,000, increments, the split above the maximum, below the minimum
    t = time.time()
    hy = cat.set_index("coin").loc["HYPE"]
    assert (hy.price_tick_str, hy.qty_increment_str, hy.min_order_size_str, hy.max_order_size_str) == \
        ("0.001", "0.0001", "0.001", "7000"), hy
    L = Decimal("29.632")
    o, note = rh_orders(L, 1000.0, hy)
    q1 = (Decimal(1000) / L / Decimal("0.0001")).to_integral_value(rounding=ROUND_FLOOR) * Decimal("0.0001")
    assert o == [q1] and q1 == Decimal("33.7473") and q1 * L <= 1000 < (q1 + Decimal("0.0001")) * L, (o, note)
    o, note = rh_orders(L, 1_000_000.0, hy)                                 # 33,747.2327 HYPE > 7,000: split
    units = int((Decimal(1_000_000) / L / Decimal("0.0001")).to_integral_value(rounding=ROUND_FLOOR))
    assert len(o) == 5 and sum(o) == Decimal(units) * Decimal("0.0001"), o
    assert all(Decimal("0.001") <= x <= Decimal(7000) and x % Decimal("0.0001") == 0 for x in o)
    assert max(o) - min(o) <= Decimal("0.0001") and "split into 5 orders" in note, (o, note)
    o, note = rh_orders(L, 0.02, hy)                                        # 0.0006 HYPE < 0.001
    assert o == [] and "below Robinhood's minimum order size 0.001" in note, note
    o, _ = rh_orders(L, 207424.0, hy)                                       # 7000 x 29.632: the maximum, one order
    assert o == [Decimal("7000.0000")], o
    o, _ = rh_orders(L, 207424.01, hy)                                      # 7000.0003 HYPE: two orders
    assert o == [Decimal("3500.0002"), Decimal("3500.0001")], o
    o, _ = rh_orders(L, 7000.0001 * 29.632, hy)                             # just above: two orders, none tiny
    assert len(o) == 2 and min(o) >= Decimal("3500"), o
    btc = cat.set_index("coin").loc["BTC"]
    o, note = rh_orders(Decimal("60000.00"), 2_000_000.0, btc)              # 33.333 BTC > 20: two orders
    assert len(o) == 2 and sum(o) == Decimal("33.33333333") and max(o) <= 20, o
    pepe = cat.set_index("coin").loc["PEPE"]
    o, _ = rh_orders(Decimal("0.00000163"), 1000.0, pepe)
    assert o == [Decimal(613496932)], o
    od = pd.DataFrame([dict(coin="HYPE", limit="29.632", qty=str(x)) for x in rh_orders(L, 1e6, hy)[0]] +
                      [dict(coin="PEPE", limit="0.00000163", qty="613496932")])
    assert k7_violations(od, cat) == []
    assert len(k7_violations(pd.DataFrame([dict(coin="HYPE", limit="29.6325", qty="7000.00005")]), cat)) == 3
    try:                                                    # cross-check with the controls' K7 check, if importable
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            from analysis_2026 import stinkbid_controls as sbc
        chk = sbc.k7_check_orders(od.assign(limit=od["limit"].astype(float)), sbd.rh_pairs())
        assert chk["n_violations"] == 0, chk
        k7x = "(own check and stinkbid_controls.k7_check_orders)"
    except Exception as e:                                  # another agent's module: never fail this selftest on it
        k7x = f"(stinkbid_controls cross-check unavailable: {type(e).__name__}; own check only)"
    say(f"  orders: HYPE tick 0.001 / increment 0.0001 / min 0.001 / max 7,000; $1M at 29.632 -> 5 near-equal orders "
        f"of the increment within [min, max]; $0.02 -> no order (below the minimum); BTC and PEPE sizes; K7's order "
        f"check passes {k7x}")
    timings["orders"] = time.time() - t

    # ---- 4. levels on Robinhood's tick (oracle), delta recomputed, V15's re-read, flip target
    t = time.time()
    rdir = _stub_results(base / "res_round", verdicts=dict(H2R="INCONCLUSIVE", H1="PASS", H4="INCONCLUSIVE"),
                         coins=("NEAR", "SOL"))
    sh = build_sheet(["NEAR", "SOL", "PEPE"], {"NEAR": "3.1"}, asof, rdir, base / "nocache", catalog=cat, data=W,
                     universe=U, history=False)
    rows = sh.rows.set_index(["coin", "row"])
    n_reread = 0
    for coin, P0s in (("NEAR", "3.1"), ("SOL", None), ("PEPE", None)):
        k_ = W[coin]["d1"]
        sig = _oracle_sigma(k_, d0)
        P0 = float(P0s) if P0s else float(k_["close"].iloc[-1])
        tick = cat.set_index("coin").loc[coin, "price_tick_str"]
        for rung in RUNGS:
            r = rows.loc[(coin, f"M2 k={rung:g}")]
            Lo = _oracle_floor(P0 * math.exp(-rung * sig), tick)
            assert Decimal(r["limit_price"]) == Lo, (coin, rung, r["limit_price"], Lo)
            assert abs(float(r["depth_sigma"]) - math.log(P0 / float(Lo)) / sig) < 5e-4, (coin, rung)
            assert abs(float(r["sigma30"]) - sig) < 1e-6
            moved = math.log(P0 / float(Lo)) / sig - rung
            assert ("read at delta" in r["fill_odds_note"]) == (moved > REROUND), (coin, rung, moved)
            if moved > REROUND:                                 # PEPE: tick 1e-8 at 2e-6 moves the level > 0.05 sigma
                n_reread += 1
                tab = rung_stats(_stub_coin_rung(), "PEPE")
                exp_ = at_depth(tab, math.log(P0 / float(Lo)) / sig)
                xs = np.array(RUNGS)
                ys = tab["rh_rate"].to_numpy(float)
                dd = math.log(P0 / float(Lo)) / sig
                orc = (np.interp(dd, xs, ys) if dd <= xs[-1] else ys[-1] + (dd - xs[-1]) * (ys[-1] - ys[-2]) /
                       (xs[-1] - xs[-2]))
                assert abs(float(r["rh_fill_odds_week"]) - orc) < 1e-5 and abs(exp_["rh_rate"] - orc) < 1e-12
            # flip target (H1 PASS): ceil(L + (P0 - L) / 2) on the tick
            half = Lo + (Decimal(repr(P0)) - Lo) / 2
            tq = Decimal(tick)
            fo = (half / tq).to_integral_value(rounding=ROUND_CEILING) * tq
            assert Decimal(r["flip_target"]) == fo and r["flip_rule"] == FLIP_STOP, (coin, rung, r["flip_target"], fo)
    assert n_reread >= 2 and all("read at delta" not in x for x in sh.rows.loc[sh.rows.coin != "PEPE",
                                                                                "fill_odds_note"]), n_reread
    assert rows.loc[("NEAR", "M2 k=6"), "ref_source"].startswith("--price")
    assert rows.loc[("SOL", "M2 k=6"), "ref_source"].startswith("Binance spot close of 2026-11-17")
    say(f"  levels: NEAR (--price), SOL and PEPE floored to Robinhood's tick = oracle floor(P0 exp(-k sigma30)); delta "
        f"recomputed after rounding; the odds are re-read at the rounded depth exactly when rounding moved the level "
        f"> 0.05 sigma ({n_reread} of PEPE's 3 rungs on its 1e-8 tick; = oracle interpolation; none for NEAR / SOL); "
        "flip target = oracle ceil(L + (P0 - L)/2) under H1 PASS")
    timings["levels"] = time.time() - t

    # ---- 5. fresh price or refusal of a stale close; sigma staleness; typo guard
    t = time.time()
    rdir = _stub_results(base / "res_fresh")
    close_t = pd.Timestamp("2026-11-18 00:00", tz="UTC")
    for when, price, ok in ((close_t + pd.Timedelta(hours=24), None, True),
                            (close_t + pd.Timedelta(hours=24, minutes=1), None, False),
                            (close_t + pd.Timedelta(hours=30), "3.05", True),
                            (close_t + pd.Timedelta(days=7, hours=23), "3.05", True),
                            (close_t + pd.Timedelta(days=8), "3.05", False)):
        sh = build_sheet(["NEAR"], {"NEAR": price} if price else {}, when, rdir, base / "nocache", catalog=cat,
                         data=W, universe=U, history=False)
        got = "NEAR" not in sh.refused
        assert got == ok, (when, price, sh.refused)
        if not ok and price is None:
            assert "more than 24 hours" in sh.refused["NEAR"] and "--price NEAR=" in sh.refused["NEAR"]
        if not ok and price:
            assert "--refresh" in sh.refused["NEAR"]
    sh = build_sheet(["NEAR"], {"NEAR": "31"}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U,
                     history=False)
    assert "check for a typo" in sh.refused["NEAR"], sh.refused
    sh = build_sheet(["NEAR"], {"NEAR": "31"}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U,
                     history=False, force_price=True)
    assert "NEAR" not in sh.refused
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = main(["--coins", "NEAR,SOL", "--results", str(rdir), "--cache", str(base / "nocache"), "--asof",
                   str(close_t + pd.Timedelta(hours=30))], _inject=dict(catalog=cat, data=W, universe=U,
                                                                         history=False))
    assert rc == 1                                           # every coin refused -> exit 1, sheet still written
    s = pd.read_csv(rdir / "sheet" / "sheet_2026-11-19.csv", dtype=str).fillna("")
    assert (s["row"] == "(refused)").all() and s["refused"].str.contains("more than 24 hours").all()
    for bad in (["--price", "NEAR"], ["--price", "NEAR=-1"], ["--price", "NEAR=abc"], ["--life", "30"],
                ["--per-rung", "0"]):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = main(["--coins", "NEAR", "--results", str(rdir), "--asof", str(asof)] + bad,
                      _inject=dict(catalog=cat, data=W, universe=U, history=False))
        assert rc == 2, bad
    say("  freshness: a close exactly 24 h old is used, 24 h 1 min refused (asks for --price or --refresh); --price "
        "accepted 30 h and 7 days 23 h later, refused 8 days later (sigma30's bars more than 7 days old); a 10x "
        "--price refused as a typo unless --force-price; all-refused CLI exits 1 with the reasons written; bad "
        "arguments exit 2")
    timings["freshness"] = time.time() - t

    # ---- 6. waits and odds: KM shrinkage oracle, pooled rows for HYPE and coins without history, capacity basis
    t = time.time()
    rdir = _stub_results(base / "res_stats", coins=("NEAR",))
    sh = build_sheet(["NEAR", "HYPE", "AAVE"], {}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U,
                     history=False, route="mm", per_rung=60000.0)
    rows = sh.rows.set_index(["coin", "row"])
    cr = _stub_coin_rung()
    for rung in RUNGS:
        r = rows.loc[("NEAR", f"M2 k={rung:g}")]
        w = 300 / 352
        p, mp, sp = POOL[rung]
        x, mc, sc = OWN[rung]
        if math.isfinite(mc):
            assert abs(float(r["median_weeks_to_fill"]) - (w * mc + (1 - w) * mp)) < 0.051, (rung, r)
        else:
            assert r["median_weeks_to_fill"] == "not reached" and "not reached" in r["wait_basis"]
        assert abs(float(r["no_fill_within_year"]) - (w * sc + (1 - w) * sp)) < 5e-5
        own = cr[(cr.coin == "NEAR") & (cr.rung == rung) & (cr.rule == "F3_1")].iloc[0]
        assert abs(float(r["rh_fill_odds_week"]) - own.rate_shrunk) < 5e-6
        assert abs(float(r["rh_fill_odds_lo"]) - own.wilson_lo) < 5e-6 and \
            r["rh_fill_odds_basis"] == f"{x} fills in {x - 1} episodes"
        own1 = cr[(cr.coin == "NEAR") & (cr.rung == rung) & (cr.rule == "F1")].iloc[0]
        assert abs(float(r["binance_fill_odds_week_upper_bound"]) - own1.rate_shrunk) < 5e-6
        assert float(r["q_max_usd"]) == 1e4 and "own past fills" in r["capacity_note"]
        assert "above Q_max" in r["order_note"] and "context only" in r["order_note"]          # $60k > Q_max, mm
        for coin in ("HYPE", "AAVE"):                        # HYPE always pooled; AAVE has no U-Q1 row
            h = rows.loc[(coin, f"M2 k={rung:g}")]
            if "read at delta" in h["fill_odds_note"]:
                continue
            assert abs(float(h["rh_fill_odds_week"]) - p) < 5e-6 and abs(float(h["median_weeks_to_fill"]) - mp) < .051
            assert "U-Q1 pooled" in h["rh_fill_odds_basis"] and "pooled fills" in h["capacity_note"]
    assert "HYPE: no verdict" in rows.loc[("HYPE", "M2 k=6"), "fill_odds_note"]
    assert HYPE_NOTE in _flat(sh.lines)
    sh = build_sheet(["NEAR"], {}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U, history=False,
                     route="ex", per_rung=60000.0)
    r = sh.rows.iloc[0]
    assert float(r["order_size_usd"]) == 1e4 and "capped at Q_max" in r["order_note"], r
    rdir2 = _stub_results(base / "res_none", coin_rows=False)
    shutil.rmtree(rdir2 / "explore")
    (rdir2 / "sheet_inputs.json").unlink()
    (rdir2 / "answer.json").unlink()
    sh = build_sheet(["NEAR"], {}, asof, rdir2, base / "nocache", catalog=cat, data=W, universe=U, history=False)
    r = sh.rows.iloc[0]
    assert r["rh_fill_odds_week"] == NOT_COMPUTED and r["median_weeks_to_fill"] == NOT_COMPUTED and \
        r["limit_price"] and NOT_COMPUTED in r["post_fill_outcomes"] and r["flip_target"] == ""
    assert f"The answer (STINKBID_PREREG.md section 11): {NOT_COMPUTED}" in _flat(sh.lines)
    say("  waits and odds: NEAR's median wait and no-fill chance = oracle w m_coin + (1 - w) m_rung, w = 300/352 "
        "(k = 10: own median not reached -> 'not reached'); F3 odds and interval as desc wrote them, F1 as the upper "
        "bound; HYPE and AAVE -> the U-Q1 pooled rung, labelled; capacity from own fills, Q_max context only on mm "
        "and a cap on ex; without results every item reads 'not yet computed' and the levels still print")
    timings["waits"] = time.time() - t

    # ---- 7. earned / not earned for every verdict combination (and the bot, D10, D9, route, gradient switches)
    t = time.time()
    n_combo = 0
    for h2r in VERDICTS:
        for h1 in VERDICTS:
            for h4 in VERDICTS:
                for bot in (False, True):
                    if bot and h1 == "PASS":
                        continue
                    v = dict(H2R=h2r, H1=h1, H4=h4)
                    R = load_results(_stub_results(base / "res_e", verdicts=v, bot=bot, d10=("M6",), d9=True,
                                                   q=0.04, slope=-0.02, coin_rows=False, stages=bool(bot)))
                    assert R["verdicts"] == v and R["chain"], (R["verdicts"], R["chain_why"])
                    for route in ("mm", "ex"):
                        e = earned(R, route)
                        assert e["flip"] == (h1 == "PASS")
                        assert e["bot_only"] == (bot and h1 != "PASS")
                        assert e["passed"] == [t_ for t_ in TESTS if v[t_] == "PASS"]
                        exp_chart = ({"M4"} if h4 == "PASS" else set()) | {"M6"}      # M4 p_rw .004 < .0167
                        assert set(e["chart"]) == exp_chart, (v, e["chart"])
                        assert e["chart"]["M6"]["label"] == D10_LABEL
                        assert e["round_number"] == (route == "ex")
                        assert e["best_rung"] == 6.0 and not e["tradeoff"]
                        n_combo += 1
    # rendered rows for every verdict combination (one coin), checked column by column
    for h2r in VERDICTS:
        for h1 in VERDICTS:
            for h4 in VERDICTS:
                v = dict(H2R=h2r, H1=h1, H4=h4)
                bot = h1 == "INCONCLUSIVE"
                rdir = _stub_results(base / "res_v", verdicts=v, bot=bot, binance_only={"H1": True}, q=0.5)
                sh = build_sheet(["NEAR"], {}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U,
                                 history=False, route="mm")
                m2 = sh.rows[sh.rows["row"].str.startswith("M2")]
                ch = sh.rows[sh.rows["row"].str.endswith("(chart)")]
                assert len(m2) == 3
                assert (m2["flip_target"] != "").all() == (h1 == "PASS") and (m2["flip_target"] == "").all() == \
                    (h1 != "PASS")
                if h1 != "PASS":
                    assert m2["flip_rule"].str.contains("the flip worked only" if bot else "not shown").all()
                for t_ in TESTS:
                    shown = m2["post_fill_outcomes"].str.contains(f"{t_} PASS").all() if t_ != "H4" else \
                        (ch["post_fill_outcomes"].str.contains("H4 PASS").all() if len(ch) else False)
                    assert shown == (v[t_] == "PASS"), (v, t_)
                if h1 == "PASS":
                    assert m2["post_fill_outcomes"].str.contains("a Binance-only result").all()
                assert (len(ch) > 0) == (h4 == "PASS") and (not len(ch) or set(ch["row"]) == {"M4 N=90 buffer=0.5 "
                                                                                                  "(chart)"})
                assert m2["round_number_advice"].str.startswith("not shown: exchange route only").all()
                assert m2["best_rung"].str.startswith("none: the depth gradient's BH q = 0.500").all()
                assert (m2["theta_k"] != "").all() and not m2["theta_k"].str.contains("not shown").any()
                if not any(t_ == "PASS" for t_ in v.values()):
                    assert m2["post_fill_outcomes"].str.contains("not shown: no test passed").all()
                n_combo += 1
    # D10-only chart rows, D9 advice on ex only, the best rung (and no trade-off) under q < 0.10
    rdir = _stub_results(base / "res_d10", d10=("M5b",), d9=True, q=0.03, slope=0.02)
    for route in ("mm", "ex"):
        sh = build_sheet(["NEAR"], {}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U, history=False,
                         route=route)
        ch = sh.rows[sh.rows["row"].str.endswith("(chart)")]
        m2 = sh.rows[sh.rows["row"].str.startswith("M2")]
        assert list(ch["row"]) == ["M5b (chart)"] and ch["chart_level"].str.contains(D10_LABEL).all()
        assert ch["post_fill_outcomes"].str.contains("not shown").all()
        assert m2["round_number_advice"].str.startswith("not shown").all() == (route == "mm")
        assert list(m2["best_rung"] != "") == [False, False, True]           # slope > 0 -> k = 10
        assert m2["theta_k"].str.contains("not shown: a best rung is earned").all()
    # a planted round number gets one tick of advice (exchange route, D9)
    is_r, up = _round_number(Decimal("2.0000"), 3.1, "0.0001")
    assert is_r and up == Decimal("2.0001") and not _round_number(Decimal("2.1699"), 3.1, "0.0001")[0]
    say(f"  earned: {n_combo} combinations (4 x 4 x 4 verdicts x bot latency x route; then every verdict triple "
        "rendered): flip target iff H1 PASS (bot-only sentence otherwise), post-fill outcomes exactly for the "
        "passed tests (H1 Binance-only label), chart rows iff H4 PASS with Romano-Wolf p < Holm level or D10 "
        "(labelled), round-number advice only on ex with D9, best rung iff q < 0.10 (slope sign) else theta_k / "
        "mu*_k")
    timings["earned"] = time.time() - t

    # ---- 8. MoneyLine now: rising -> green, falling -> red, a jump restarts the line, short series undefined
    t = time.time()
    assert moneyline_now(W["LINK"]["d1"], d0)["state"] == "green"
    m = moneyline_now(W["UNI"]["d1"], d0)
    assert m["state"] == "red" and ML_RED in m["note"]
    kj = _syn_d1(p_end=5.0, sigma=0.03, seed=11, jump_at=380)                 # 20 bars after a 60% open jump
    mj = moneyline_now(kj, d0)
    tail = kj.iloc[380:]
    st = mlr.supertrend(tail[["open", "high", "low", "close"]].reset_index(drop=True), **mlr.MONEYLINE_PARAMS)
    assert mj["bars"] == 20 and mj["state"] == ("green" if st["green"].iloc[-1] else "red") and "warming" in mj["note"]
    assert moneyline_now(_syn_d1(n=8), d0)["state"] == "undefined"
    sh = build_sheet(["UNI"], {}, asof, _stub_results(base / "res_ml"), base / "nocache", catalog=cat, data=W,
                     universe=U, history=False)
    assert (sh.rows["moneyline_now"] == "red").all() and sh.rows["moneyline_note"].str.contains(ML_RED).all()
    assert (sh.rows["large_long_listed"] == "no").all()
    say("  MoneyLine now: a rising series green, a falling one red ('a fill here buys against your own trend "
        "signal'), a 60% jump restarts the line (state = moneyline_ref on the 20 bars after it, flagged warming up), "
        "8 bars undefined; U-Q1 flag from the universe table")
    timings["moneyline"] = time.time() - t

    # ---- 9. ladder footer: N, D, S against a brute-force oracle; compact history round trip
    t = time.time()
    fills = {("NEAR", 6.0, 3): (100, 200), ("NEAR", 8.0, 3): (300, None), ("SOL", 6.0, 3): (5000, 5000),
             ("SOL", 10.0, 40): (9000, 9100), ("NEAR", 10.0, 41): (60, 70)}
    B = _syn_bids(fills=fills)
    lad = ladder_stats(B, ["NEAR", "SOL"])
    for rule in ("F3_1", "F1"):
        tc = "t_" + rule
        days_live = set()
        for r in B.itertuples():
            days_live.update(range(r.live_from // DAY_M, (r.life_end - 1) // DAY_M + 1))
        fd = sorted({int(x) // DAY_M for x in B[tc] if x >= 0})
        best, cur = 0, 0
        for dd in range(min(days_live), max(days_live) + 1):
            if dd in days_live and dd not in fd:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        worst = 0.0
        for dd in fd:
            live = filled = 0
            for (c, k), g in B.groupby(["coin", "rung"]):
                rest = [(r.live_from // DAY_M <= dd <= (r.life_end - 1) // DAY_M) and
                        (getattr(r, tc) < 0 or getattr(r, tc) >= dd * DAY_M) for r in g.itertuples()]
                live += any(rest)
                filled += any(getattr(r, tc) >= 0 and getattr(r, tc) // DAY_M == dd for r in g.itertuples())
            worst = max(worst, filled / live)
        assert lad[rule]["D"] == best and lad[rule]["fill_days"] == len(fd), (rule, lad[rule], best, fd)
        assert abs(lad[rule]["N"] - len(fd) / (len(days_live) / 365.25)) < 1e-9
        assert abs(lad[rule]["S"] - worst) < 1e-12, (rule, lad[rule]["S"], worst)
    hc = compact_history(B.drop(columns=["variant"]))
    back = expand_history(hc)
    key = ["coin", "rung", "t0"]
    a_ = B.sort_values(key).reset_index(drop=True)[key + ["live_from", "life_end", "t_F1", "t_F3_1"]]
    b_ = back.sort_values(key).reset_index(drop=True)[key + ["live_from", "life_end", "t_F1", "t_F3_1"]]
    pd.testing.assert_frame_equal(a_, b_, check_dtype=False)
    assert (hc["kind"] == "chain").sum() == 6
    B2 = B[~((B.coin == "SOL") & (B.rung == 6.0) & (B.t0 == B.t0.min() + 10 * WEEK_M))]   # a gap splits a chain
    assert (compact_history(B2.drop(columns=["variant"]))["kind"] == "chain").sum() == 7
    rdir = _stub_results(base / "res_lad", coins=("NEAR", "SOL"))
    (rdir / "sheet").mkdir(exist_ok=True)
    hc.assign(source="fcount/P1__U_C").to_csv(rdir / "sheet" / HISTORY_FILE, index=False)
    sh = build_sheet(["NEAR", "SOL"], {}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U)
    ft = _flat(sh.lines)
    assert LADDER.format(N=f"{lad['F3_1']['N']:.0f}", D=lad["F3_1"]["D"], S=f"{100 * lad['F3_1']['S']:.0f}") in ft
    say(f"  footer: N = {lad['F3_1']['N']:.1f} fill days a year, D = {lad['F3_1']['D']} days, S = "
        f"{100 * lad['F3_1']['S']:.0f}% (F3) equal a brute-force oracle (F1 too); the compact history round-trips "
        "and a gap splits a chain; the footer reads it when no run cache exists")
    timings["footer"] = time.time() - t

    # ---- 10. order diff against last week's sheet
    t = time.time()
    rdir = _stub_results(base / "res_diff", coins=("NEAR", "SOL"))
    new = build_sheet(["NEAR", "SOL", "HYPE"], {}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U,
                      history=False).rows
    prev = new[new["coin"].isin(["NEAR", "SOL"])].copy()
    sol8 = (prev["coin"] == "SOL") & (prev["row"] == "M2 k=8")
    prev.loc[sol8, "limit_price"] = "99.99"
    prev = pd.concat([prev, prev[prev["coin"] == "NEAR"].assign(coin="AAVE")], ignore_index=True)
    (rdir / "sheet").mkdir(exist_ok=True)
    prev.to_csv(rdir / "sheet" / "sheet_2026-11-11.csv", index=False)
    prev.assign(limit_price="1.0").to_csv(rdir / "sheet" / "sheet_2026-11-04.csv", index=False)   # older: ignored
    new.to_csv(rdir / "sheet" / "sheet_2026-11-25.csv", index=False)                              # later: ignored
    pd.DataFrame().to_csv(rdir / "sheet" / "diff_2026-11-17.csv", index=False)                    # not a sheet
    assert find_previous(rdir / "sheet", _day(asof)).name == "sheet_2026-11-11.csv"
    # (A2.6) a sheet on which every coin was refused holds no order: it is skipped, the one before it is "last week's"
    allref = prev.assign(row="(refused)", limit_price="", orders="", refused="the latest close is 32 hours old")
    allref.to_csv(rdir / "sheet" / "sheet_2026-11-16.csv", index=False)
    assert find_previous(rdir / "sheet", _day(asof)).name == "sheet_2026-11-11.csv"
    (rdir / "sheet" / "sheet_2026-11-16.csv").unlink()
    sh = build_sheet(["NEAR", "SOL", "HYPE"], {}, asof, rdir, base / "nocache", catalog=cat, data=W, universe=U,
                     history=False)
    dd = sh.diff
    act = {(r.coin, r.row): [] for r in dd.itertuples()}
    for r in dd.itertuples():
        act[(r.coin, r.row)].append(r.action)
    for k_ in RUNGS:
        row = f"M2 k={k_:g}"
        assert act[("NEAR", row)] == ["keep"]
        assert act[("SOL", row)] == (["cancel", "place"] if k_ == 8 else ["keep"])
        assert act[("HYPE", row)] == ["place"] and act[("AAVE", row)] == ["cancel"]
    assert dd[(dd.coin == "SOL") & (dd.action == "cancel")]["detail"].str.contains("at 99.99").all()
    sh2 = build_sheet(["NEAR", "SOL", "HYPE"], {}, asof + pd.Timedelta(hours=13), rdir, base / "nocache",
                      catalog=cat, data=W, universe=U, history=False)     # NEAR, SOL, HYPE refused (stale close)
    d2 = sh2.diff
    assert (d2["action"] == "cancel").all() and len(d2) == 9
    assert d2[d2.coin != "AAVE"]["detail"].str.contains("no new level this week").all()
    assert d2[d2.coin == "AAVE"]["detail"].str.contains("not on this week's sheet").all()
    say("  order diff: unchanged rows keep, a changed limit -> cancel (with last week's price) then place, a new coin "
        "-> place, a dropped coin -> cancel, a refused coin -> cancel or keep at your discretion; the previous sheet "
        "is the latest one dated before today (later sheets and diff files ignored)")
    timings["diff"] = time.time() - t

    # ---- 10b. --refresh (injected fetcher): newer closes are fetched, cached, joined; a jump restarts sigma30
    t = time.time()
    rdir = _stub_results(base / "res_refresh")
    later = pd.Timestamp("2026-11-21 10:00", tz="UTC")
    calls = []

    def tail_bars(jump: float = 1.0):
        t_ = pd.date_range("2026-11-18", periods=3, freq="D", tz="UTC")
        c = np.array([3.05, 3.10, 3.30]) * jump
        o = np.r_[3.0 * jump, c[:-1]]
        return pd.DataFrame(dict(open_time=t_, open=o, high=np.maximum(o, c) * 1.01, low=np.minimum(o, c) * 0.99,
                                 close=c, volume=1e6, quote_volume=1e6, trades=1000))

    def fake_fetch(sym, end, start_month):
        calls.append((sym, end, start_month))
        return tail_bars()
    Wr = {"NEAR": {"d1": W["NEAR"]["d1"].assign(seg=0)}}
    sh = build_sheet(["NEAR"], {}, later, rdir, base / "nocache", catalog=cat, data=Wr, universe=U, history=False)
    assert "more than 24 hours" in sh.refused.get("NEAR", ""), sh.refused
    sh = build_sheet(["NEAR"], {}, later, rdir, base / "nocache", catalog=cat, data=Wr, universe=U, history=False,
                     refresh=True, fetch=fake_fetch, refresh_dir=base / "d1cache")
    r = sh.rows.iloc[0]
    assert "NEAR" not in sh.refused and r["sigma30_closes_to"] == "2026-11-20" and r["ref_price"] == "3.3", r
    k_ = pd.concat([W["NEAR"]["d1"], tail_bars()], ignore_index=True)
    assert abs(float(r["sigma30"]) - _oracle_sigma(k_, pd.Timestamp("2026-11-20"))) < 1e-6
    assert calls == [("NEARUSDT", "2026-11-20", "2026-10")], calls
    assert (base / "d1cache" / "NEARUSDT.parquet").exists()

    def broken_fetch(sym, end, start_month):
        raise OSError("network down")
    sh = build_sheet(["NEAR"], {}, later, rdir, base / "nocache", catalog=cat, data=Wr, universe=U, history=False,
                     refresh=True, fetch=broken_fetch, refresh_dir=base / "d1cache")
    assert "NEAR" not in sh.refused and sh.rows.iloc[0]["sigma30_closes_to"] == "2026-11-20"   # from the cache
    jumped = refresh_daily("NEAR", pd.Timestamp("2026-11-20"), Wr["NEAR"]["d1"], fetch=lambda *a: tail_bars(1.6),
                           cache_dir=base / "d1cache_j")
    assert list(jumped["seg"].iloc[-4:]) == [0, 1, 1, 1], jumped["seg"].iloc[-4:]
    sh = build_sheet(["NEAR"], {}, later, rdir, base / "nocache", catalog=cat, data=Wr, universe=U, history=False,
                     refresh=True, fetch=lambda *a: tail_bars(1.6), refresh_dir=base / "d1cache_j2")
    assert "sigma30 needs" in sh.refused.get("NEAR", ""), sh.refused
    say("  refresh: a 3-day-old close is refused, --refresh fetches the newer bars (one archive call from the month "
        "before the cache ends), sigma30 = oracle on the joined closes, the bars are cached (a failed fetch then uses "
        "the cache); a 60% open jump in the new bars starts a new segment, so sigma30 has too few returns and the "
        "coin is refused")
    timings["refresh"] = time.time() - t

    # ---- 10c. the ladder history from a run cache laid out like the engine's; zero arguments write nothing
    t = time.time()
    run = base / "cache" / "fcount" / "P1__U_C"
    run.mkdir(parents=True)
    Bc = _syn_bids(fills=fills).assign(program="P1", universe="U_C", method="M2", real=True)
    Bc["bid_id"] = np.arange(len(Bc))
    Bc.drop(columns=["t_F1", "t_F3_1"]).to_parquet(run / "bids.parquet")
    Bc[(Bc.t_F1 >= 0) | (Bc.t_F3_1 >= 0)][["bid_id", "coin", "rung", "t_F1", "t_F3_1"]].to_parquet(
        run / "fills.parquet")
    (run / "done.json").write_text("{}")
    rdir = _stub_results(base / "res_hist")
    hb, hsrc = load_history(base / "cache", rdir)
    assert "run cache" in hsrc and "U-C" in hsrc and len(hb) == len(Bc)
    lad2 = ladder_stats(hb, ["NEAR", "SOL"])
    assert (rdir / "sheet" / HISTORY_FILE).exists()
    hb3, hsrc3 = load_history(base / "nocache", rdir)
    lad3 = ladder_stats(hb3, ["NEAR", "SOL"])
    for rule in ("F3_1", "F1"):
        for key_ in ("N", "D", "S", "fill_days"):
            assert lad2[rule][key_] == lad[rule][key_] == lad3[rule][key_], (rule, key_)
    assert "compact history" in hsrc3
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = main([])
    assert rc == 2 and "nothing was written" in err.getvalue()
    say("  history: the engine-format run cache (fcount/P1__U_C) gives the same N, D and S as the oracle and writes "
        "the compact file, which gives them again without the cache; no arguments -> usage, exit 2, nothing written")
    timings["history"] = time.time() - t

    # ---- 11. text: ASCII only, wording, CLI writes the three files, never an order call in this module
    t = time.time()
    rdir = _stub_results(base / "res_cli", verdicts=dict(H2R="PASS", H1="PASS", H4="PASS"), d10=("M6",), d9=True,
                         q=0.01, slope=0.05, mode="injected:selftest")
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = main(["--coins", "NEAR,HYPE,PEPE,LIT", "--price", "NEAR=3.05,HYPE=41.5", "--route", "ex",
                   "--per-rung", "2500", "--results", str(rdir), "--asof", str(asof)],
                  _inject=dict(catalog=cat, data=W, universe=U, history=_syn_bids(("NEAR", "HYPE"))))
    txt = out.getvalue()
    assert rc == 0, txt[-2000:]
    files = sorted(p.name for p in (rdir / "sheet").glob("*"))
    assert files == ["diff_2026-11-18.csv", "sheet_2026-11-18.csv", "sheet_2026-11-18.txt"], files
    s = pd.read_csv(rdir / "sheet" / "sheet_2026-11-18.csv", dtype=str).fillna("")
    assert list(s.columns) == COLS
    assert S13_COLS == [c for c in s.columns if c in S13_COLS]
    txt.encode("ascii")
    (rdir / "sheet" / "sheet_2026-11-18.txt").read_text(encoding="ascii")
    low = txt.lower()
    for w_ in ("solid", "quality", "made no difference", "is just", " works"):
        assert w_ not in low, w_
    ft = _flat([txt])
    assert "NOT THE STUDY'S REAL RESULTS" in ft and "LIT: REFUSED" in ft and HYPE_NOTE in ft and ROUTE_NOTE in ft
    assert "Total cash reserved" in ft and TEST_ORDER in ft and "Order diff" in ft
    sheet_txt = (rdir / "sheet" / "sheet_2026-11-18.txt").read_text(encoding="ascii").splitlines()
    assert all(len(x) <= WRAP or re.match(r"  M\d", x) or x == TABLE_HEAD or " " not in x.strip()
               for x in sheet_txt), [x for x in sheet_txt if len(x) > WRAP][:3]
    assert set(s[s["row"].str.endswith("(chart)")]["row"]) == {"M4 N=90 buffer=0.5 (chart)", "M6 (chart)"}
    m4 = s[s["row"] == "M4 N=90 buffer=0.5 (chart)"]
    m6 = s[s["row"] == "M6 (chart)"]
    assert m4["post_fill_outcomes"].str.contains("H4 PASS").all() and m4["chart_level"].str.contains("H4 PASS").all()
    assert not m6["post_fill_outcomes"].str.contains("H4 PASS").any()
    assert m6["chart_level"].str.contains(D10_LABEL).all()
    assert m6["post_fill_outcomes"].str.contains("H1 PASS").all()                # H1 / H2R outcomes apply to any bid
    src = Path(__file__).read_text()
    for tok in ("place_" + "crypto_order", "preview_" + "crypto_order", "cancel_" + "crypto_order", "mcp" + "__",
                "robin" + "_stocks", "api." + "robinhood", "requests" + ".post"):
        assert tok not in src, tok
    say("  text and CLI: exit 0, sheet_*.csv (columns in section 13's order) + .txt + diff_*.csv written, ASCII "
        "only, no 'solid' / 'quality' / forbidden wording, non-real results bannered, LIT refused, HYPE note, route "
        "note, cash total, test order and diff printed; no order-placing call or broker library in this module")
    timings["cli"] = time.time() - t

    # ---- 11b. regressions for the review's nine findings
    t = time.time()
    _t_review(say, base, cat, W, U, asof)
    timings["review"] = time.time() - t

    # ---- 12. real data (counts and levels only; no outcome is read): the CLI on the cached bars
    if real:
        t = time.time()
        try:
            sbd.d1("NEAR")
            have = True
        except Exception:
            have = False
        if have:
            rdir = base / "res_real"
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc = main(["--coins", "NEAR,BTC,HYPE,RENDER,PEPE", "--price", "NEAR=3.40", "--results", str(rdir),
                           "--cache", str(base / "nocache"), "--asof", "2026-11-18 12:00"])
            assert rc == 0, out.getvalue()[-3000:]
            s = pd.read_csv(rdir / "sheet" / "sheet_2026-11-18.csv", dtype=str).fillna("")
            priced = s[s["limit_price"] != ""]
            assert set(priced["coin"]) == {"NEAR", "BTC", "HYPE", "RENDER", "PEPE"}, s[["coin", "row", "refused"]]
            orders = pd.DataFrame([dict(coin=r.coin, limit=r.limit_price, qty=q) for r in priced.itertuples()
                                   for q in r.orders.split(";") if q])
            assert k7_violations(orders, cat) == []
            assert (priced["rh_fill_odds_week"] == NOT_COMPUTED).all()     # no study results yet: nothing earned
            assert (priced["flip_target"] == "").all()
            mv = (priced["depth_sigma"].astype(float) -
                  priced["row"].str.extract(r"k=([0-9.]+)")[0].astype(float))
            nmv = int((mv > REROUND).sum())
            assert (mv >= -1e-9).all() and nmv >= 1                  # flooring only deepens; RENDER's 0.01 tick
            say(f"  real data: NEAR (--price 3.40), BTC, HYPE, RENDER and PEPE priced from the cache (closes to "
                f"2026-11-17), every order passes K7; Robinhood's tick moved {nmv} of {len(priced)} rungs more than "
                "0.05 sigma (V15's re-read applies once fill odds exist); fill odds read 'not yet computed' (no study "
                "results yet)")
        else:
            say("  real data: not available here (skipped)")
        timings["real"] = time.time() - t
    say("timings: " + ", ".join(f"{k} {v:.1f}s" for k, v in timings.items()))
    say(f"stinkbid_sheet selftest: all passed ({time.time() - t_all:.1f}s)")
    return True


if __name__ == "__main__":
    sys.exit(main())
