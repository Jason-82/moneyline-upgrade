"""
Fill and exit engine of the stink-bid study, as frozen in analysis_2026/STINKBID_PREREG.md (FROZEN 2026-11-18, commit
72ac2a4): §4.1 integrity rules (causal segments, redenominations, swaps, delistings, outages), §6.3 programs, lives
and size, §7 fill model (F1-F5, gap-through fills, capacity), §8 exits and the manual clock (rule M, X-FLIP and its
marketable-limit rule, X-FLIP-bot, the flip grid, X-HOLD-h, X-OWN, X-ML, route-specific exits), §9 costs and carry,
§10.1 benchmarks (B-TWIN, B-ALERT, B-POST, B-ML, B-MKT, B-MIX, B-TBILL, B-DCA, B-HOLD, B-ALERT-DCA, B-ML-DCA, leave-out
drift), the per-fill fields of §10.4 (D12 recovery curve, T1 / D-H5 knife and lowest-price fields, D-ML, D6, D7 and
D7-OWN accounts) and §10.5 K5 (fill audit), with the capacity window of research_notes/Stink bids/design_draft.md §8.3
and the fidelity critique's V1-V5, V7, V9, V11, V13. Contract: research_notes/Stink bids/build_spec.md,
"stinkbid_engine.py". Data: analysis_2026/stinkbid_data.py; levels: stinkbid_levels.py; clusters: stinkbid_stats.py;
the MoneyLine replica: moneyline_ref.py (none is edited). On real data this module was only run for counts, fill
audits and timings (counts_only); every outcome check is on synthetic data against separately coded oracles.

    python3 -m analysis_2026.stinkbid_engine selftest [--no-real]     # hand-built paths, oracle, wrong engines,
                                                                      # twins, accounts, H4, causality; real-data
                                                                      # counts and fill audit unless --no-real
    python3 -m analysis_2026.stinkbid_engine counts P1 U_Q1 [--coins A,B] [--rules F1,F2]   # counts only

Public API
  run_program(program, universe="U_Q1", coins=None, data=None, cfg=None) -> dict
      program: a key of PROGRAMS (P1, P1-k5-12, P1-30, P1-90, P1-1, P1-lazy, P1-G, P1-1330, M1, M2a, M3, M8, H4,
      H4-all) or a Program; universe: a column of the universes table (U_Q1, U_B, U_Q1_12, U_Q1_xm, U_A, U_C);
      data: None (real) or an injected world (World's docstring; synth_world builds one); cfg: DEFAULT_CFG keys
      (rules, counts_only, capacity, exits, twin_sens, drift, audit, stream, fill_price, keep_twins, usd, mw, ml).
      Returns
        bids        one row per bid: bid_id, program, universe, coin, method, params, rung, variant, shift (H4
                    placebo shift in ATR%; 0 = the real level), real, cw (coin-week id), t0, d0, P0, sigma30,
                    atr_pct, tick, tick_str, L, L_tau (L - tau), n_ticks, delta, sidx / seg (segment), live_from,
                    life_end (minutes since 1970 UTC), month, ml_d0 (MoneyLine at d0: 1 green, 0 red, -1
                    undefined), order_weeks (P1-lazy); with outcomes also B-MKT: mkt_entry, mkt_r365, bid_r365,
                    r365_complete, exit365_kind
        bid_status  placements without a bid (inputs not ok, abstentions, not green, placebo none)
        fills       one row per bid that filled under any rule: the bid's fields, fill_id (the seed index), per
                    rule i_<rule> / t_<rule> (bar index / minute, -1 = no fill) for F1, F2, F3_1..F3_5 (index low
                    <= L / (1 + s)), F3d_1..F3d_5 (dwell), F4, F5 and the K8 USD rows F3usd_1 / F3usd_3; for F1
                    fills gap_through (L above the minute's high), open_below, prev_close_above, H24, s24 / s6 / s1,
                    idx_missing (F3-unverifiable) / idx_outage / idx_low_rel, rh_outage, mw / mw_share
                    (market-wide), ml_fill (outcome runs only), capacity (n_windows, c1_first, c1_life, agg_first,
                    agg_life, agg_missing, cap_src, share_<Q>_<theta> and t_full_<Q>_<theta> for Q = 1k / 10k /
                    100k, theta = 1 / 0.25; c1_m0 / agg_m0: the fill minute alone, §4.1's bad-print rule),
                    episode and month_block (F1 fills, stinkbid_stats), half, in_U_Q1
        outcomes    one row per (fill, rule, exit, cost): r (§10.2 net return), r_dl_last / r_dl0 / r_dl100
                    (delisting sensitivities), exit_kind (target | marketable | stop | delist | censored), exit_t,
                    exit_px, target, horizon_t, complete (the whole horizon observed), hold_h, twin_mean, twin_n,
                    twin_pooled, delta (= r - twin_mean); on (F1, FLIP) also *_x30 (+-30-day twins), *_pool (pooled
                    twins), drift_mu and delta_drift (leave-out drift)
        bench       one row per (fill, rule): alert_<M|2h|8h|24h|72h> (B-ALERT a_f), alert_t_* and alert_px_*;
                    on F1 and F3_1: rec_<R|P0|dn10>_<15m..30d> and rec_dn10_first (D12) with twin_rec_* (twin
                    shares), ml_a / ml_days (B-ML), post_mean_<cost> / post_n (B-POST); on F1: ml_fill,
                    red_close_1d / 7d (D-ML), xml_r_<C-RH|C-0> / xml_t / xml_px (X-ML), own_r_C-RH (X-OWN), low30 /
                    low90 / low365, delisted30 / 90 / 365, knife, knife_dl_last / dl0 / dl100 and their twin_*
                    means (T1, D-H5)
        audit       K5 records: violations (the run raises AuditError unless cfg audit='report'), gap listings
                    (resting orders filled at their limit outside the minute's range), counts per check
        meta        cfg, the exit plan, timings, pooled-twin needs
        cap_curve   per F1 fill (bid_id) the capacity accumulated minute by minute (minute, cum: dollars through
                    the end of that minute, on the fill's cap_src); accounts() sizes D7 positions from it
        twins       (cfg keep_twins) per-twin entries, exits and returns (own and pooled)
  accounts(res, data=None, route="F1", r_res=0.0, Q=10_000, theta=1.0, m_contrib=1_000, tbill=True) -> dict
      D7 flip account and D7-OWN (§10.4) with B-MIX, B-TBILL, B-DCA, B-HOLD, B-ALERT, B-ML and B-ALERT-DCA,
      B-ML-DCA, B-MIX-OWN, B-DCA-OWN, B-HOLD-OWN, B-TBILL-OWN: monthly returns (time-weighted) and
      monthly_after_tax, values (D7, D7_after_tax), summary (CAGR, Sharpe, max drawdown, after-tax CAGR, end values
      before and after tax, tax paid, invested fraction) for every account, positions, lots. Monthly returns feed
      stinkbid_stats.stationary_bootstrap (6- and 12-month blocks).
  h4_frames(res, rule="F1", exit="FLIP", cost=None) -> {method: DataFrame(y, real, depth, cw, time, coin, shift,
      fill_id)} for stinkbid_stats.test_h4 (H4's stacked real-and-placebo samples with coin-week ids; fills whose
      whole exit horizon is observed; cost None = the rule's route label, e.g. RH for the F3 gate)
  rule_m(t) / rule_m_ts(ts)        the manual-action clock on minutes / timestamps
  World(data, stream)              data access (real or injected); synth_world / synth_coin (synthetic markets)
  PROGRAMS, DEFAULT_CFG, EXIT_SPECS (FLIP, FLIP_bot, G_<target>_<h>h, HOLD7..HOLD365, TH72), default_exits(rules)
  build_spot / build_index / coin_fills / capacity / run_exits / simulate_twins: the building blocks (numba
      kernels on two-level block maxima / minima for first-hit and range queries)

Mechanics (prereg text decides; the draft where the prereg incorporates it)
- Bids (§6.1, §6.3): levels from stinkbid_levels at each placement whose month the coin is a universe member; live
  from t0 + 1 minute until the next placement of the program (the previous week's bids stay live until the new ones
  are placed); every bid-week is an independent order (V7). H4 programs add the four placebos of every real level.
- F1 (§7): the first live spot minute (trades > 0) of the life with low <= L - tau (L - tau as the double nearest the
  decimal (n - 1) tau), filled at L, also when the minute gapped wholly below L (listed); F2 low <= L; F3 / F3d / F4
  on live index minutes (updates >= 30, outside the Robinhood outage windows); F5 the perpetual (trades > 0) with
  F1's rule. Minutes missing or with trades = 0 never fill and never trigger an exit (§4.1).
- Capacity (§7, draft §8.3): causal windows over the order's life; aggTrades (stinkbid_data.agg_capacity) or C1.
- X-FLIP (§8): target R1/2 = ceil(L + (P0 - L) / 2) on the tick, live from M(fill); marketable at the open of the
  first live minute at or after it when that open is at or above R1/2; else filled at R1/2 in the first live minute
  (from that one on) with high >= R1/2 + tau (the decimal next tick, coding choice 25), before the time stop; else
  sold at the open of the first live minute at or after M(fill + 72 h), in whichever segment of the chain it falls.
  F3 rows: target when index high >= R1/2 / (1 - 0.0095), market sells (and the marketable check) at index
  x (1 - 0.0095), spread s instead within 24 h of the fill in the crash-spread rows; F4
  rows: index high >= R1/2, C-EX costs. Positions follow their segment chain; a delisting ends a chain at the §4.1
  value (VWAP of the last full day x 0.70; last trade x 0.70, 0% and 100% as sensitivities) at the end of trading;
  the data end censors.
- B-TWIN (§10.1): 100 entries drawn uniformly from the coin's eligible minutes (live, a member month, outside
  [tau_f - 182 d, tau_f + 182 d], a complete exit window; windows cut by a delisting or segment end are kept and
  closed by §4.1), each entering at its minute's open and exiting by the fill's rule with the same relative target,
  clock, route and costs; fewer than 182 eligible days -> pooled twins from all U-Q1 coins' eligible minutes outside
  +-182 days; seeds default_rng(20261118 + fill index).
- B-ALERT (§8, §10.1): a market buy at the open of the first live minute at or after M(tau_f) (and tau_f + 2, 8, 24,
  72 h) on the fill's route: a_f = open / L - 1 on spot (C-RH both sides), index open x (1 + spread) / L - 1 on F3.

Coding choices the pre-registration leaves open (most literal reading; listed in the build report)
 1. Times are minutes since 1970 UTC, bars labelled by their open. A fill in minute m is stamped at the end of m;
    the clock of rule M is applied to the event's minute t = m (a twin's: its entry minute; a time stop's: m + h).
    Rule M: t + 60 if t's New York clock time is 07:00-22:59 (inclusive), else the next 07:00 New York (zoneinfo).
 2. X-FLIP-bot changes only the sell's live time (fill + 1 minute); its time stop stays M(fill + 72 h) (the prereg's
    row: "the same with the sell live 1 minute after the fill"). The flip grid's stops are M(fill + 24 h / 72 h /
    7 d); flip-grid targets are rounded up to the tick; H24 = the highest live high in the 24 h before the fill
    minute inside its segment.
 3. Schedules: weekly Mondays 03:30 UTC 2020-01-06..2026-11-09 (13:30 for P1-1330); P1-1 daily 03:30 through
    2026-11-16; P1-30 / P1-90 every 30 / 90 days from 2020-01-06. A life ends at the next placement (so a weekly
    bid is live on minutes [t0 + 1, t0 + 7 d) and Monday's 03:30 minute belongs to no bid); lives are censored at
    the data end. Universe membership is the placement's UTC month.
 4. P1-lazy: F1 decides whether the resting order filled; a kept order keeps its placement inputs (t0, P0, sigma,
    L) and its life grows a week at a time; it is cancelled when the coin leaves the universe, the inputs are not
    ok, the new level is more than 5% away, or it has filled. Other rules use the same lives.
 5. A bid belongs to the segment of d0 (stinkbid_data's seg): it fills only on that segment's bars and is cancelled
    at the first bar of another segment; index and perpetual fills also stop at the segment's end of trading (its
    last live spot minute + 1). A placement whose segment ended before it never fills.
 6. Lineages: a swap successor's 1m bars after the predecessor's last trade are appended; a position's prices are
    per unit of its entry segment's asset through the segment units (redenominations at 1/ratio, swaps at the
    frozen ratio, jumps at 1; a successor's units continue from the predecessor's last segment, its joined
    redenominations included); a target's trade-through tick is converted at the same units. Go-live minutes, time
    stops, hold horizons and alert times may fall any number of segments after the entry: the search starts at that
    minute in whichever segment of the chain holds it. A swap whose successor has no bars is valued as a delisting.
    Bars on days without a daily kline (seg -1) are dropped.
 7. MoneyLine: moneyline_ref's replica (ATR10 x 2, hl2, reset) run per segment of the daily series (restarted at
    every boundary, like the sigma windows of §4.1); undefined (-1) before ATR10 exists. P1-G places a week's bids
    only when the state at d0 is green.
 8. B-ML: the open of the next daily bar of the chain after the first green close at or after the fill (the fill
    day's close counts), the green close within 365 days. X-ML: the open of the first live minute of the day after
    the first red close that follows a green close; the last close before the fill counts as a preceding close.
    D-ML red closes: daily closes (day end) within (fill, fill + 1 d] and (fill, fill + 7 d].
 9. Robinhood outage windows (§7): the hours are not documented, so each listed date's whole New York calendar day,
    padded by one hour on each side. They block F3 / F4 fills and exits (and index-route alert buys and twins).
10. F3-unverifiable: an F1 fill whose minute has no index minute (idx_missing; no contract yet or an archive gap); an
    index minute with fewer than 30 updates at that minute is flagged idx_outage. F3 itself is evaluated per bid on
    live index minutes only, with no spot fallback.
11. Twins apply the fill's relative target (its rounded target / L) to their paid entry price (spot and F4: the
    open; F3: the ask, open x (1 + spread)) without rounding, with the trade-through tick of the coin's most recent
    Monday placement inputs. The same holds for D12's twin levels.
12. Market sells, marketable limits and delisting values pay the scenario's market cost on spot routes (C-EX: 0.95%
    taker), resting targets its limit cost; on the F3 route delisting values get the market spread (x (1 - 0.0095)).
13. Capacity windows start at each live trigger minute (low <= L - tau) while the order rests and end at the first
    later live minute with low > L, or after 60 minutes, inside the life and the segment. C1's share below L is
    clip((L - low) / (high - low), 0, 1) (1 for a flat minute below L). capacity='auto' uses aggTrades on real U-Q1
    programs and C1 otherwise (U-B's U-Q1 coins included). Shares are at the end of the life; t_full_* is the minute
    the order completed. Capacity is measured for F1 fills (the Binance spot book).
14. Index and perpetual months are read through stinkbid_data's month cache (its _fut_load: read only); the fill
    stage reads the candidate months of V4's fetch rule (stinkbid_data.index_fetch_days); outcome runs read the
    whole index history (twins on the F3 route need it).
15. Pooled twins use whole UTC days: days touching [tau_f - 182 d, tau_f + 182 d] and days ending after the horizon
    cutoff are left out; the draw is uniform over the remaining eligible minutes of every U-Q1 coin (the fill's own
    coin included), resolved minute-exactly on each coin.
16. The fill index of the seed: the program's F1 fills ranked by (F1 fill minute, coin, method, rung, placebo shift,
    bid id) are 0 .. N1 - 1 (F1 is evaluated for this even when it is not a configured rule); a bid filled only under
    other rules gets N1 + its bid id. No index depends on which other rules a run evaluates. Its first 100
    uniforms place the B-TWIN entries of every route and exit (and D12's and T1's twins); the next 100 the B-POST
    entries. (The fills table stays sorted by the first fill minute.)
17. Twin eligibility uses the coin's own segments (not its successors'). A complete window means the exit's horizon
    is at or before the data end: M(entry + stop) for flips, M(entry + h) for holds, M(entry) + 72 h for TH72,
    entry + 30 d for D12, entry + 365 d for T1. Fills report `complete` with the same horizon.
18. The default outcome plan: F1 every exit (FLIP, FLIP_bot, the 23 other grid cells, HOLD7 / 30 / 90 / 365, TH72);
    F3_1 FLIP, FLIP_bot and HOLD90; every other rule FLIP. Spot routes in C-RH, C-EX, C-0 and C-BUS; F2 and F5 rows
    exit on spot (F5's fill minute comes from the perpetual).
19. D12: fills count hits from the minute after the fill (bars m + 1 ..), twins from the entry minute; "within h" =
    hit minute - m <= h (twins: - (entry - 1)); on F3 the up levels count when index high >= level / (1 - 0.0095);
    "first trading a further 10% below L" = 0.9 L before R1/2 within 30 days. Lowest prices: live lows after the
    fill (a delisting at its §4.1 value); knife: the VWAP (quote volume / volume) of the 365th day after the fill day
    along the chain, or the §4.1 value after a delisting.
20. Leave-out drift: mu_i = the mean hourly simple return of the coin's own bars (calendar hours, closes carried over
    hours without trades, NaN across segments; bb_stats.returns_from_hours' convention) outside +-182 days of the
    fill; delta_drift = r - mu_i x holding hours. B-MKT: a market buy at the first live minute at or after t0 + 1,
    held 365 days (C-RH); bid_r365: the F1 fill held to t0 + 365 d.
21. Accounts: D7's capital = 3 Q x the most coins bidding in one week; a bid is taken only when its (coin, rung)
    position has exited by t0; on F1 the position is min(Q, theta x the capacity accumulated minute by minute before
    the exit minute) (§7, V13), each day's partial fills booked on that day, the unfilled remainder reserved until
    the order's life ends; F3 positions are Q (capacity is context on the market-maker route); daily marks at the
    lineage daily close; reserved cash earns r_res, free cash the T-bill. After-tax (§10.4), every account: interest
    and gains on lots held at most 365 days are short-term (35%), longer long-term (20%); lots are FIFO per coin;
    every open lot is sold at the last marks on the last day; each calendar year nets the two kinds (a net loss of
    one offsets a net gain of the other; the $3,000 ordinary-income limit is ignored) and carries net losses forward
    with their kind; the tax is paid on the year's last day out of cash that would otherwise have earned the T-bill
    (after tax); the after-tax CAGR compounds the after-tax values' monthly returns like the pre-tax CAGR. B-HOLD
    (D7): the capital split equally across every coin that ever joins, each bought at its first member day's open;
    B-DCA (D7): weekly buys of capital / weeks across that week's coins; B-ALERT (D7): the flip positions bought at
    the alert price under rule M; B-MIX rebalances on each month's first day at the previous close (its implied
    trades are its tax lots). D7-OWN: contributions at each month's first placement; Q_max = 0.25 x the 10th
    percentile of earlier fills' capacity at the rung (at least 10 fills, else no cap); a held order's filled
    dollars over its life are booked on its first fill day; interest in a separate bucket that is not re-bid.
22. The market-wide flag of a fill is data_inventory §6.1's leave-one-out rule on the fill's UTC day (at least 10% of
    the other active U-B coins with a daily low <= 0.85 x the previous close); the MoneyLine state at the fill day's
    close is never computed in counts_only mode (it is read after the fill).
23. K5 is written separately from the kernels (a pandas clock, its own outage mask, brute-force scans) and checks
    every bid fill (validity and first-ness), every fill exit, every alert buy (first 200) and every twin exit's
    validity, with first-hit checks on 400 sampled twins per batch.
24. cfg fill_price 'close' / 'low' (the two wrong engines K1b must reject) rebook F1 fills' entry price only.
25. Trade-through on decimal prices (§8 'high >= R1/2 + tau', K5 'high >= limit + tau'): a fill's target is on its
    tick grid, so its spot trigger is the double nearest the decimal next tick (n_T + 1) tau (the float sum
    dbl(n tau) + dbl(tau) can lie above it and miss a one-tick trade-through); a twin's unrounded target uses the
    float sum T + tau. In a later segment whose units differ from the entry segment's, the converted target and
    trigger (price / units) are compared with a relative tolerance of 1e-12 (stinkbid_data's capacity convention),
    so a print exactly at the converted price counts.
26. Streaming (cfg stream=True, real U-B coins without a cached 1m file): a streamed frame is kept as a temporary
    zstd parquet under data/stinkbid/m1_stream_tmp/ while at least 4 GB of disk stay free, so pass 2 reads it
    instead of downloading the coin again; a coin's file is deleted after pass 1 when it has no fill, after the last
    pass-2 coin whose lineage needs it otherwise, and every file when the run ends.
27. Index months on the outcome stage (real data; prereg Addendum 1, A1.6): a coin's index series is read for its
    program-universe and U-Q1 member months and the IDX_BUFFER_M = 12 months after each (index_months_for), not for
    its whole history, so the 1m index archive fits on disk. Bids live in member months (at most 90 days), twins
    enter in member months and the longest index-route reach (a 90-day life, B-POST's 30 days and a 90-day hold) is
    about 7 months; _pass2_coin raises if any index-route fill's horizon touches a month that was not read.
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import time
import warnings
from collections import OrderedDict, deque
from dataclasses import dataclass, replace
from pathlib import Path
from zoneinfo import ZoneInfo

import numba as nb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import moneyline_ref as mlr  # noqa: E402
from analysis_2026 import stinkbid_data as sbd  # noqa: E402
from analysis_2026 import stinkbid_levels as sbl  # noqa: E402
from analysis_2026 import stinkbid_stats as sbs  # noqa: E402

# ============================================================================ constants (prereg section in brackets)
MIN_NS = 60_000_000_000
DAY_M = 1440
NY = ZoneInfo("America/New_York")
END = sbd.END                                     # 2026-11-17: the data end (§4 windows)
FIRST_T0, LAST_T0 = "2020-01-06 03:30", "2026-11-09 03:30"     # placements (§4, §6.1)
LAST_T0_DAILY = "2026-11-16 03:30"                # P1-1 (coding choice 3)
PLACE_HM, PLACE_HM_SENS = (3, 30), (13, 30)        # §6.1 and its sensitivity
SEED = 20261118                                   # §10.1 B-TWIN seed base
R_TWINS = 100                                     # §10.1
EXCL_DAYS, EXCL_DAYS_SENS = 182, 30               # §10.1 (b); ±30-day twins (§10.4 sensitivity rows)
POOL_MIN_DAYS = 182                               # §10.1 pooled twins
FLIP_STOP_H = 72                                  # §8 X-FLIP
C_RH = 0.0095                                     # §8, §9
F3_SPREAD = 0.0095                                # §8 route-specific exits
F3_S = (0.01, 0.02, 0.03, 0.05)                   # §7 F3 s values (1% primary)
CRASH_SPREAD_H = 24                               # §8: crash-spread rows, exit spread s within 24 h of the fill
IDX_MIN_UPDATES = 30                              # §7 index outages
RH_OUTAGE_DATES = ("2021-04-15", "2021-05-04", "2022-02-25", "2025-10-06", "2025-10-20")   # §7 (coding choice 9)
RH_OUTAGE_PAD_M = 60
F4_BUY = 0.005                                    # §7 F4 at C-EX costs
# cost scenarios (§9): (buy, sell at a resting limit, sell at market / marketable / delisting)
COSTS = {"C-RH": (0.0095, 0.0095, 0.0095), "C-EX": (0.0050, 0.0050, 0.0095), "C-0": (0.0, 0.0, 0.0),
         "C-BUS": (0.0, 0.0002, 0.0002)}
Q_SIZES = (1_000.0, 10_000.0, 100_000.0)          # §6.3 size per rung
THETAS = (1.0, 0.25)                              # §7 capacity theta
CAP_WIN_M = 60                                    # draft §8.3
CONV_REL = 1e-12                                  # converted targets in a later segment (coding choice 25)
IDX_BUFFER_M = 12                                 # outcome stage, real data: index months read = the coin's
                                                  # member months + 12 (prereg Addendum 1, A1.6; coding choice 27)
HAIRCUT = sbd.HAIRCUT                             # §4.1 delisting haircut 0.30
REC_H_M = (15, 60, 240, 1440, 4320, 10080, 43200)  # D12 horizons
REC_LABELS = ("15m", "1h", "4h", "24h", "72h", "7d", "30d")
ALERT_DELAYS_H = (2, 8, 24, 72)                   # §10.1 B-ALERT fixed delays
HOLD_DAYS = (7, 30, 90, 365)                      # §8 X-HOLD-h
GRID_TARGETS = ("g5", "g10", "g20", "sig1", "sig2", "R", "H24", "P0")   # §8 flip grid
GRID_STOPS_H = (24, 72, 168)
LOWEST_D = (30, 90, 365)                          # T1
SPEED_H = (24, 6, 1)                              # s24, s6, s1
POST_FROM_D, POST_TO_D, POST_HOLD_D = 1, 30, 90   # §10.1 B-POST
ML_REENTRY_D = 365                                # §10.1 B-ML
KNIFE_FRAC, DOWN_FRAC = 0.5, 0.9                  # D-H5 / T1; D12 "a further 10% below L"
MW_DROP, MW_SHARE = 0.15, 0.10                    # market-wide day (data_inventory §6.1, leave-one-out)
TAX_ST, TAX_LT = 0.35, 0.20                       # D7 after-tax
R_RES_GOLD = 0.0335                               # §9
NEG_INF, POS_INF = -np.inf, np.inf
# exit kinds
EK_TARGET, EK_MARKETABLE, EK_STOP, EK_DELIST, EK_CENSORED, EK_NONE = 0, 1, 2, 3, 4, 5
EK_NAMES = np.array(["target", "marketable", "stop", "delist", "censored", "none"])
# routes of the exit kernel
RT_SPOT, RT_IDX3, RT_IDX4 = 0, 1, 2


# ============================================================================ time helpers
def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _tmin(x):
    """Minutes since 1970-01-01 UTC: an int for a scalar, an int64 array for a sequence (naive input = UTC)."""
    if isinstance(x, (str, pd.Timestamp, np.datetime64)) or (hasattr(x, "tzinfo") and not hasattr(x, "__len__")):
        return int(_ts(x).as_unit("ns").value // MIN_NS)
    idx = pd.DatetimeIndex(x)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return idx.tz_localize(None).as_unit("ns").asi8 // MIN_NS


def _mts(m):
    """Minutes since 1970 -> Timestamp (scalar) or DatetimeIndex (array), UTC; negative / NaN -> NaT."""
    if np.ndim(m) == 0:
        if m is None or (isinstance(m, float) and not math.isfinite(m)) or int(m) < 0:
            return pd.NaT
        return pd.Timestamp(int(m) * MIN_NS, tz="UTC")
    a = np.asarray(m, dtype=float)
    ns = np.where(np.isfinite(a) & (a >= 0), a, np.nan) * MIN_NS
    out = pd.to_datetime(pd.Series(ns), utc=True)
    return pd.DatetimeIndex(out).as_unit("ns")


def _month_of_min(m) -> np.ndarray:
    """Months since 1970-01 of minute times."""
    d = (np.asarray(m, dtype=np.int64) // DAY_M).astype("datetime64[D]")
    return d.astype("datetime64[M]").astype(np.int64)


def _month_int(s: str) -> int:
    return int(np.datetime64(s[:7], "M").astype(np.int64))


def _ny_transitions(y0: int = 2015, y1: int = 2032):
    """(UTC minute of every America/New_York offset change, offset in minutes from then on) from zoneinfo."""
    h = pd.date_range(f"{y0}-01-01", f"{y1}-01-01", freq="h", tz="UTC")
    loc = h.tz_convert(NY).tz_localize(None)
    naive = h.tz_localize(None)
    off = ((loc - naive) // pd.Timedelta("1min")).to_numpy(np.int64)
    hm = naive.as_unit("ns").asi8 // MIN_NS
    chg = np.r_[True, off[1:] != off[:-1]]
    return hm[chg].astype(np.int64), off[chg].astype(np.int64)


_TR_T, _TR_OFF = _ny_transitions()


@nb.njit(cache=True)
def _rule_m1(t, tr_t, tr_off):
    """Manual-action rule M (§8) for an event at UTC minute t: t + 60 if t's New York clock time is 07:00-22:59,
    else the next 07:00 New York time."""
    k = np.searchsorted(tr_t, t, side="right") - 1
    if k < 0:
        k = 0
    off = tr_off[k]
    lt = t + off
    mod = lt % DAY_M
    if mod >= 420 and mod <= 1379:
        return t + 60
    day = lt // DAY_M
    if mod < 420:
        tl = day * DAY_M + 420
    else:
        tl = (day + 1) * DAY_M + 420
    k2 = np.searchsorted(tr_t, tl - off, side="right") - 1
    if k2 < 0:
        k2 = 0
    return tl - tr_off[k2]


@nb.njit(cache=True)
def _rule_m_arr(ts, tr_t, tr_off):
    out = np.empty(ts.size, np.int64)
    for i in range(ts.size):
        out[i] = _rule_m1(ts[i], tr_t, tr_off)
    return out


def rule_m(t):
    """Rule M (§8) on UTC minutes (int or int64 array) -> the minute the action happens."""
    if np.ndim(t) == 0:
        return int(_rule_m1(np.int64(t), _TR_T, _TR_OFF))
    return _rule_m_arr(np.asarray(t, dtype=np.int64), _TR_T, _TR_OFF)


def rule_m_ts(ts):
    """Rule M on timestamps (scalar or sequence) -> timestamps (UTC)."""
    if np.ndim(ts) == 0:
        return _mts(rule_m(_tmin(ts)))
    return _mts(rule_m(_tmin(ts)))


def _rule_m_pd(ts) -> pd.DatetimeIndex:
    """Rule M written separately with pandas time zones (the audit's independent check of rule_m)."""
    t = pd.DatetimeIndex(ts)
    t = t.tz_localize("UTC") if t.tz is None else t.tz_convert("UTC")
    loc = t.tz_convert(NY)
    mins = loc.hour * 60 + loc.minute
    day = loc.tz_localize(None).normalize()
    nxt_day = np.where(mins < 7 * 60, day, day + pd.Timedelta("1D"))
    nxt = pd.DatetimeIndex(nxt_day) + pd.Timedelta("7h")
    nxt = nxt.tz_localize(NY, ambiguous="raise", nonexistent="raise").tz_convert("UTC")
    day_ok = (mins >= 7 * 60) & (mins <= 22 * 60 + 59)
    return pd.DatetimeIndex(np.where(day_ok, t + pd.Timedelta("60min"), nxt)).tz_convert("UTC") \
        if t.size else t


def rh_outage_windows():
    """§7 Robinhood outage windows +-1 h (coding choice 9: the whole New York calendar day of each listed date,
    padded by an hour on each side), as [start, end) UTC minutes."""
    out = []
    for d in RH_OUTAGE_DATES:
        a = pd.Timestamp(d).tz_localize(NY).tz_convert("UTC")
        b = (pd.Timestamp(d) + pd.Timedelta("1D")).tz_localize(NY).tz_convert("UTC")
        out.append((_tmin(a) - RH_OUTAGE_PAD_M, _tmin(b) + RH_OUTAGE_PAD_M))
    return np.array(out, dtype=np.int64)


_RH_OUT = rh_outage_windows()


def _in_rh_outage(tm: np.ndarray) -> np.ndarray:
    tm = np.asarray(tm, dtype=np.int64)
    m = np.zeros(tm.shape, bool)
    for a, b in _RH_OUT:
        m |= (tm >= a) & (tm < b)
    return m


# ============================================================================ numba kernels: block search
B1, B2 = 32, 1024                                 # two-level blocks for first-hit and range queries


@nb.njit(cache=True)
def _blk_max(v):
    n = v.size
    n1 = (n + B1 - 1) // B1
    n2 = (n + B2 - 1) // B2
    m1 = np.full(max(n1, 1), -np.inf)
    m2 = np.full(max(n2, 1), -np.inf)
    for i in range(n):
        j = i // B1
        if v[i] > m1[j]:
            m1[j] = v[i]
    r = B2 // B1
    for j in range(n1):
        if m1[j] > m2[j // r]:
            m2[j // r] = m1[j]
    return m1, m2


@nb.njit(cache=True)
def _blk_min(v):
    n = v.size
    n1 = (n + B1 - 1) // B1
    n2 = (n + B2 - 1) // B2
    m1 = np.full(max(n1, 1), np.inf)
    m2 = np.full(max(n2, 1), np.inf)
    for i in range(n):
        j = i // B1
        if v[i] < m1[j]:
            m1[j] = v[i]
    r = B2 // B1
    for j in range(n1):
        if m1[j] < m2[j // r]:
            m2[j // r] = m1[j]
    return m1, m2


@nb.njit(cache=True)
def _first_ge(v, m1, m2, a, b, thr):
    """First i in [a, b) with v[i] >= thr (m1, m2: block maxima), else -1."""
    i = a
    while i < b:
        if i % B2 == 0 and i + B2 <= b and m2[i // B2] < thr:
            i += B2
            continue
        if i % B1 == 0 and i + B1 <= b and m1[i // B1] < thr:
            i += B1
            continue
        if v[i] >= thr:
            return i
        i += 1
    return -1


@nb.njit(cache=True)
def _first_le(v, m1, m2, a, b, thr):
    """First i in [a, b) with v[i] <= thr (m1, m2: block minima), else -1."""
    i = a
    while i < b:
        if i % B2 == 0 and i + B2 <= b and m2[i // B2] > thr:
            i += B2
            continue
        if i % B1 == 0 and i + B1 <= b and m1[i // B1] > thr:
            i += B1
            continue
        if v[i] <= thr:
            return i
        i += 1
    return -1


@nb.njit(cache=True)
def _range_min(v, m1, m2, a, b):
    best = np.inf
    i = a
    while i < b:
        if i % B2 == 0 and i + B2 <= b:
            if m2[i // B2] < best:
                best = m2[i // B2]
            i += B2
            continue
        if i % B1 == 0 and i + B1 <= b:
            if m1[i // B1] < best:
                best = m1[i // B1]
            i += B1
            continue
        if v[i] < best:
            best = v[i]
        i += 1
    return best


@nb.njit(cache=True)
def _range_max(v, m1, m2, a, b):
    best = -np.inf
    i = a
    while i < b:
        if i % B2 == 0 and i + B2 <= b:
            if m2[i // B2] > best:
                best = m2[i // B2]
            i += B2
            continue
        if i % B1 == 0 and i + B1 <= b:
            if m1[i // B1] > best:
                best = m1[i // B1]
            i += B1
            continue
        if v[i] > best:
            best = v[i]
        i += 1
    return best


@nb.njit(cache=True)
def _next_live(live):
    n = live.size
    nxt = np.empty(n + 1, np.int64)
    nxt[n] = n
    for i in range(n - 1, -1, -1):
        nxt[i] = i if live[i] else nxt[i + 1]
    return nxt


@nb.njit(cache=True)
def _k_first_le_batch(v, m1, m2, a, b, thr):
    out = np.full(a.size, -1, np.int64)
    for j in range(a.size):
        if a[j] < b[j]:
            out[j] = _first_le(v, m1, m2, a[j], b[j], thr[j])
    return out


@nb.njit(cache=True)
def _k_range_max_batch(v, m1, m2, a, b):
    out = np.full(a.size, -np.inf)
    for j in range(a.size):
        if a[j] < b[j]:
            out[j] = _range_max(v, m1, m2, a[j], b[j])
    return out


# ============================================================================ numba kernels: chains of segments
# A series (spot, index or perpetual 1m bars of one coin and its successors) carries per-bar segment indices into
# the coin's segment table: seg_lo / seg_hi (bar range of the segment in THIS series), seg_U (units of the segment's
# asset per unit of the lineage's first asset), seg_next (the segment a position continues into, -1: none),
# seg_term (what ends a chain: 0 the data end (censored), 1 a delisting valued by §4.1), seg_val (the §4.1 value of
# one unit of the segment's asset: VWAP x 0.7, last trade x 0.7, VWAP, 0) and seg_t1 (the minute trading stopped).

@nb.njit(cache=True)
def _chain_live(nxt, seg_lo, seg_hi, seg_next, s, i):
    """First live bar at or after bar i along the chain starting at segment s: (bar, its segment); (-1, last
    segment of the chain) when the chain ends first. Bar i may lie in a later segment of the chain (a time stop, a
    go-live or an alert after a swap, a joined redenomination or a jump): segment bar ranges increase along a chain,
    so the requested start is kept, never moved back to the start of the next segment."""
    while True:
        lo = seg_lo[s]
        hi = seg_hi[s]
        if i < lo:
            i = lo
        if i < hi:
            k = nxt[i]
            if k < hi:
                return k, s
        ns = seg_next[s]
        if ns < 0:
            return -1, s
        s = ns
        if i < seg_lo[s]:
            i = seg_lo[s]


@nb.njit(cache=True)
def _k_exit(t, o, hl, mx1, mx2, nxt, seg_lo, seg_hi, seg_U, seg_next, seg_term, seg_val, seg_t1,
            route, j_seg, j_g, j_S, j_T, j_up, j_scr, j_tcr,
            out_kind, out_idx, out_t, out_px, out_raw, out_seg):
    """Exit of a long position (§8): a sell target T live from minute g (marketable at the first live bar's open if
    the bid side is already at or above T, else resting until the first later live bar whose high trades through
    it) and a market sell at the open of the first live bar at or after the stop minute S. T = +inf: a hold.
    Positions follow the chain of segments (joined redenominations, jumps, swaps at their ratios); at the end of a
    chain that is a delisting the position is worth the §4.1 value at the minute trading stopped; at the data end it
    is censored. route 0 spot: trigger high >= up (the trade-through price T + tau, given per job: the decimal next
    tick for targets on the tick grid, coding choice 25), marketable if open >= T; 1 index (F3): spread scr before
    minute tcr, F3_SPREAD after; trigger high >= T / (1 - spread), marketable if open (1 - spread) >= T, market sells
    get open (1 - spread); 2 index (F4): trigger high >= T, marketable if open >= T, market sells at the open.
    Prices out (out_px) are per unit of the entry segment's asset; out_raw is the price in the exit bar's units."""
    nJ = j_seg.size
    for j in range(nJ):
        s0 = j_seg[j]
        U0 = seg_U[s0]
        g = j_g[j]
        S = j_S[j]
        T = j_T[j]
        up = j_up[j]
        scr = j_scr[j]
        tcr = j_tcr[j]
        out_kind[j] = EK_NONE
        out_idx[j] = -1
        out_t[j] = -1
        out_px[j] = np.nan
        out_raw[j] = np.nan
        out_seg[j] = -1
        i0 = np.searchsorted(t, g)
        gi, sg = _chain_live(nxt, seg_lo, seg_hi, seg_next, s0, i0)
        if gi < 0:
            if seg_term[sg] == 1:
                out_kind[j] = EK_DELIST
                out_t[j] = seg_t1[sg]
                out_raw[j] = seg_val[sg, 0]
                out_px[j] = seg_val[sg, 0] * seg_U[sg] / U0
                out_seg[j] = sg
            else:
                out_kind[j] = EK_CENSORED
                out_seg[j] = sg
            continue
        fac = seg_U[sg] / U0
        if t[gi] >= S or not (T < np.inf):
            # the go-live bar is already at/after the stop, or a hold: market sell at the first live bar >= S
            si, ss = _chain_live(nxt, seg_lo, seg_hi, seg_next, sg, max(gi, np.searchsorted(t, S)))
            if si < 0:
                if seg_term[ss] == 1:
                    out_kind[j] = EK_DELIST
                    out_t[j] = seg_t1[ss]
                    out_raw[j] = seg_val[ss, 0]
                    out_px[j] = seg_val[ss, 0] * seg_U[ss] / U0
                    out_seg[j] = ss
                else:
                    out_kind[j] = EK_CENSORED
                    out_seg[j] = ss
                continue
            f2 = seg_U[ss] / U0
            spr = 0.0
            if route == RT_IDX3:
                spr = scr if t[si] < tcr else F3_SPREAD
            out_kind[j] = EK_STOP
            out_idx[j] = si
            out_t[j] = t[si]
            out_raw[j] = o[si]
            out_px[j] = o[si] * (1.0 - spr) * f2
            out_seg[j] = ss
            continue
        # marketable at go-live
        Tg = T / fac
        if fac != 1.0:
            Tg = Tg * (1.0 - CONV_REL)
        spr = 0.0
        if route == RT_IDX3:
            spr = scr if t[gi] < tcr else F3_SPREAD
        if o[gi] * (1.0 - spr) >= Tg:
            out_kind[j] = EK_MARKETABLE
            out_idx[j] = gi
            out_t[j] = t[gi]
            out_raw[j] = o[gi]
            out_px[j] = o[gi] * (1.0 - spr) * fac
            out_seg[j] = sg
            continue
        # the stop bar
        si, ss = _chain_live(nxt, seg_lo, seg_hi, seg_next, sg, max(gi, np.searchsorted(t, S)))
        # resting target from gi (inclusive) to the stop bar (exclusive), segment by segment
        cs = sg
        a = gi
        hit = -1
        hit_s = -1
        while True:
            hi = seg_hi[cs]
            b = hi
            if si >= 0 and ss == cs:
                b = si
            fc = seg_U[cs] / U0
            Tr = T / fc
            upr = up / fc
            if fc != 1.0:                           # a converted target (coding choice 25)
                Tr = Tr * (1.0 - CONV_REL)
                upr = upr * (1.0 - CONV_REL)
            if route == RT_SPOT:
                hit = _first_ge(hl, mx1, mx2, a, b, upr)
            elif route == RT_IDX4:
                hit = _first_ge(hl, mx1, mx2, a, b, Tr)
            else:
                kc = np.searchsorted(t, tcr)
                mid = min(max(kc, a), b)
                if a < mid:
                    hit = _first_ge(hl, mx1, mx2, a, mid, Tr / (1.0 - scr))
                if hit < 0 and mid < b:
                    hit = _first_ge(hl, mx1, mx2, mid, b, Tr / (1.0 - F3_SPREAD))
            if hit >= 0:
                hit_s = cs
                break
            if si >= 0 and ss == cs:
                break
            ns = seg_next[cs]
            if ns < 0:
                break
            cs = ns
            a = seg_lo[ns]
        if hit >= 0:
            out_kind[j] = EK_TARGET
            out_idx[j] = hit
            out_t[j] = t[hit]
            out_raw[j] = T / (seg_U[hit_s] / U0)
            out_px[j] = T
            out_seg[j] = hit_s
            continue
        if si >= 0:
            f2 = seg_U[ss] / U0
            spr = 0.0
            if route == RT_IDX3:
                spr = scr if t[si] < tcr else F3_SPREAD
            out_kind[j] = EK_STOP
            out_idx[j] = si
            out_t[j] = t[si]
            out_raw[j] = o[si]
            out_px[j] = o[si] * (1.0 - spr) * f2
            out_seg[j] = ss
            continue
        if seg_term[ss] == 1:
            out_kind[j] = EK_DELIST
            out_t[j] = seg_t1[ss]
            out_raw[j] = seg_val[ss, 0]
            out_px[j] = seg_val[ss, 0] * seg_U[ss] / U0
            out_seg[j] = ss
        else:
            out_kind[j] = EK_CENSORED
            out_seg[j] = ss


@nb.njit(cache=True)
def _k_first_hits(t, hl, mx1, mx2, ll, mn1, mn2, seg_lo, seg_hi, seg_U, seg_next, seg_term, seg_t1,
                  j_seg, j_a, j_tend, j_up1, j_up2, j_dn, out_up1, out_up2, out_dn, out_end, out_term):
    """D12: first bar (from bar a, before minute tend, along the chain) whose high >= up1 / up2 and whose low <= dn,
    all per unit of the entry segment's asset; -1 when none. out_end: the minute the observation stopped (tend, or
    the end of a chain); out_term: 0 observed to tend, 1 the chain was delisted before tend, 2 the data ended."""
    for j in range(j_seg.size):
        s0 = j_seg[j]
        U0 = seg_U[s0]
        out_up1[j] = -1
        out_up2[j] = -1
        out_dn[j] = -1
        out_term[j] = 0
        out_end[j] = j_tend[j]
        cs = s0
        a = j_a[j]
        while True:
            lo = seg_lo[cs]
            hi = seg_hi[cs]
            if a < lo:
                a = lo
            b = min(hi, np.searchsorted(t, j_tend[j]))
            fc = seg_U[cs] / U0
            if a < b:
                if out_up1[j] < 0:
                    k = _first_ge(hl, mx1, mx2, a, b, j_up1[j] / fc)
                    if k >= 0:
                        out_up1[j] = t[k]
                if out_up2[j] < 0:
                    k = _first_ge(hl, mx1, mx2, a, b, j_up2[j] / fc)
                    if k >= 0:
                        out_up2[j] = t[k]
                if out_dn[j] < 0:
                    k = _first_le(ll, mn1, mn2, a, b, j_dn[j] / fc)
                    if k >= 0:
                        out_dn[j] = t[k]
            if b < hi:
                break                                # tend reached inside this segment
            ns = seg_next[cs]
            if ns < 0:
                if seg_t1[cs] < j_tend[j]:
                    out_term[j] = 1 if seg_term[cs] == 1 else 2
                    out_end[j] = seg_t1[cs]
                break
            cs = ns
            if a < seg_lo[ns]:                       # a start in a later segment is kept (as in _chain_live)
                a = seg_lo[ns]


@nb.njit(cache=True)
def _k_lowest(t, ll, mn1, mn2, seg_lo, seg_hi, seg_U, seg_next, seg_term, seg_val, seg_t1,
              j_seg, j_a, j_tend, out_min, out_term, out_val):
    """T1: the lowest live low (per unit of the entry segment's asset) from bar a to minute tend along the chain;
    out_term 1: the chain was delisted first (out_val = the §4.1 value, per entry unit), 2: the data ended first."""
    for j in range(j_seg.size):
        s0 = j_seg[j]
        U0 = seg_U[s0]
        best = np.inf
        out_term[j] = 0
        out_val[j] = np.nan
        cs = s0
        a = j_a[j]
        while True:
            lo = seg_lo[cs]
            hi = seg_hi[cs]
            if a < lo:
                a = lo
            b = min(hi, np.searchsorted(t, j_tend[j]))
            fc = seg_U[cs] / U0
            if a < b:
                m = _range_min(ll, mn1, mn2, a, b)
                if m * fc < best:
                    best = m * fc
            if b < hi:
                break
            ns = seg_next[cs]
            if ns < 0:
                if seg_t1[cs] < j_tend[j]:
                    if seg_term[cs] == 1:
                        out_term[j] = 1
                        out_val[j] = seg_val[cs, 0] * fc
                    else:
                        out_term[j] = 2
                break
            cs = ns
            if a < seg_lo[ns]:
                a = seg_lo[ns]
        out_min[j] = best


@nb.njit(cache=True)
def _k_capacity(t, l, h, live, qv, sq, sidx, j_i, j_end, j_L, j_thr, win_m, max_w,
                w_fill, w_a, w_b, w_c1):
    """§7 capacity windows (draft §8.3) after F1 fills: a window runs from a trigger minute (the fill minute, then
    each later live minute with low <= L - tau while the order rests) until the first later live minute whose low
    is above L, or 60 minutes; C1 per live minute = seller-initiated quote volume x the share of its range below L.
    Windows stay inside the order's life (bars j_i .. j_end - 1, one segment). Returns the number of windows written
    (w_fill: fill row, [w_a, w_b): bar range, w_c1: C1 of the window)."""
    nw = 0
    for j in range(j_i.size):
        i = j_i[j]
        e = j_end[j]
        L = j_L[j]
        thr = j_thr[j]
        s = sidx[i]
        while i >= 0 and i < e and nw < max_w:
            t_start = t[i]
            c1 = 0.0
            k = i
            while k < e and t[k] < t_start + win_m and sidx[k] == s:
                if k > i and live[k] and l[k] > L:
                    break
                if live[k] and qv[k] > 0.0:
                    rng = h[k] - l[k]
                    if rng > 0.0:
                        f = (L - l[k]) / rng
                        if f < 0.0:
                            f = 0.0
                        elif f > 1.0:
                            f = 1.0
                    else:
                        f = 1.0 if l[k] < L else 0.0
                    c1 += sq[k] * f
                k += 1
            w_fill[nw] = j
            w_a[nw] = i
            w_b[nw] = k
            w_c1[nw] = c1
            nw += 1
            # the next trigger after the window
            nxt_i = -1
            m = k
            while m < e and sidx[m] == s:
                if live[m] and l[m] <= thr:
                    nxt_i = m
                    break
                m += 1
            i = nxt_i
    return nw


# ============================================================================ data access (real or injected)
STREAM_TMP = sbd.OUT / "m1_stream_tmp"            # streamed U-B 1m frames kept between passes (coding choice 26)
STREAM_MIN_FREE = 4e9                             # bytes of free disk the stream cache always leaves


class _StreamCache:
    """Streamed 1m frames (stinkbid_data.m1_stream: U-B coins without a cached file) kept as zstd parquet under
    data/stinkbid/m1_stream_tmp/ from run_program's pass 1 to its pass 2, so a streamed coin is downloaded once
    (coding choice 26). A frame is kept only while STREAM_MIN_FREE bytes of disk stay free (else it is streamed again
    when needed); run_program deletes each file once no later pass needs it, and every file when the run ends."""

    def __init__(self, root=STREAM_TMP, min_free: float = STREAM_MIN_FREE):
        self.root, self.min_free = Path(root), float(min_free)

    def path(self, key: str) -> Path:
        return self.root / f"{key}.parquet"

    def get(self, key: str, fetch):
        f = self.path(key)
        if f.exists():
            try:
                return pd.read_parquet(f)
            except Exception:                              # a partial or stale file: stream again
                f.unlink(missing_ok=True)
        k = fetch()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(self.root).free > self.min_free + 2.0 * float(k.memory_usage(deep=True).sum()):
                tmp = self.root / f".{key}.{os.getpid()}.tmp"
                k2 = k.copy(deep=False)
                k2.attrs = {}
                k2.to_parquet(tmp, compression="zstd")
                os.replace(tmp, f)
        except Exception:
            pass
        return k

    def drop(self, key: str):
        self.path(key).unlink(missing_ok=True)

    def files(self) -> set:
        return {p.stem for p in self.root.glob("*.parquet")} if self.root.exists() else set()


class World:
    """The engine's data: stinkbid_data's real frames, or injected ones (controls, selftest).

    data=None reads real data. An injected world is a dict:
      universe   DataFrame(month 'YYYY-MM', coin, <universe columns> e.g. U_Q1, U_B) (required)
      coins      {coin: frames} or a callable coin -> frames. frames: m1 (1m bars shaped like stinkbid_data.m1:
                 open_time, open, high, low, close, volume, quote_volume, trades, taker_buy_quote[, seg]; required;
                 without `seg` the §4.1 ids are derived by stinkbid_data's daily rule, _m1_seg_ids), d1 (daily bars;
                 built from m1 when absent; ids derived likewise when `seg` is absent), segments
                 (stinkbid_data.segments-shaped; derived from the bars' ids when absent: a boundary after missing days
                 is a gap (a delisting), one without is a jump), index_m1 (open_time, open, high, low, close, updates),
                 perp_m1 (1m perpetual bars),
                 tick (decimal string passed to the levels module), successor ((coin, units): a swap at the end of the
                 last segment), levels (extra frames for stinkbid_levels: h1, metrics, mark1h, perp1h, panel, ...)
      end        the data end day (default stinkbid_data.END)
      tbill      % a year: a number or a Series indexed by day (default 0)
      usd        hourly frame with usd_per_usdt (optional; USD-converted F3 flags)
      mw         DataFrame(coin, day, mw, mw_share) market-wide flags (optional)
      agg        callable(coin, day, windows) like stinkbid_data.agg_capacity (optional; else C1 only)
    stream=True lets real U-B coins without a cached 1m file be streamed (stinkbid_data.m1_stream), each kept on disk
    between run_program's passes (_StreamCache, coding choice 26)."""

    def __init__(self, data: dict | None = None, stream: bool = False):
        self.data = data
        self.injected = data is not None and not bool(data.get("real", False))
        self.stream = stream
        self.end_day = pd.Timestamp((data or {}).get("end", END))
        self.end_min = _tmin(self.end_day + pd.Timedelta("1D")) - 1
        self._inj_cache: OrderedDict = OrderedDict()
        self._univ = None
        self._mw = None
        self._ml: dict = {}
        self._lvdata: dict = {}
        self._tick_tab: dict = {}
        self.streams = _StreamCache() if (stream and not self.injected) else None

    # ---- universes
    def universe(self) -> pd.DataFrame:
        if self._univ is None:
            u = self.data.get("universe") if self.data is not None else None
            if u is None:
                u = sbd.universes()
            u = u.copy()
            u["month"] = u["month"].astype(str).str[:7]
            self._univ = u
        return self._univ

    def members(self, universe: str) -> dict:
        """coin -> sorted months (since 1970-01) in which the coin is a member of `universe`."""
        u = self.universe()
        if universe not in u.columns:
            raise KeyError(f"universe column {universe!r} not in the universes table")
        q = u[u[universe].astype(bool)]
        mi = q["month"].map(_month_int).to_numpy(np.int64)
        out = {}
        for c, idx in q.groupby("coin").indices.items():
            out[c] = np.unique(mi[idx])
        return out

    # ---- per-coin frames
    def _inj(self, coin: str) -> dict:
        if coin in self._inj_cache:
            self._inj_cache.move_to_end(coin)
            return self._inj_cache[coin]
        cs = self.data.get("coins", {})
        d = cs(coin) if callable(cs) else cs.get(coin)
        if d is None:
            raise KeyError(f"no injected frames for {coin}")
        self._inj_cache[coin] = d
        while len(self._inj_cache) > 4:
            self._inj_cache.popitem(last=False)
        return d

    def has_coin(self, coin: str) -> bool:
        if self.injected:
            cs = self.data.get("coins", {})
            if callable(cs):
                try:
                    self._inj(coin)
                    return True
                except KeyError:
                    return False
            return coin in cs
        sym = sbd.coin_sym(coin)[0]
        return (sbd.OUT / "m1_spot" / f"{sym}.parquet").exists() or self.stream

    def m1(self, coin: str) -> pd.DataFrame:
        if self.injected:
            d = self._inj(coin)
            k = d["m1"]
            if "seg" not in k:                            # §4.1 boundaries derived from the bars (_m1_seg_ids)
                if "_m1seg" not in d:
                    d["_m1seg"] = k.assign(seg=_m1_seg_ids(k, d.get("d1")))
                k = d["_m1seg"]
            return k
        sym = sbd.coin_sym(coin)[0]
        if (sbd.OUT / "m1_spot" / f"{sym}.parquet").exists():
            return sbd.m1(coin, fetch=False)
        if self.stream:
            return self.streams.get(coin, lambda: sbd.m1_stream(coin))
        raise FileNotFoundError(f"no cached 1m bars for {coin} ({sym}); run with stream=True to stream U-B coins")

    def d1(self, coin: str) -> pd.DataFrame:
        if self.injected:
            d = self._inj(coin)
            if d.get("d1") is not None:
                k = d["d1"]
                if "seg" in k:
                    return k
                if "_d1seg" not in d:
                    d["_d1seg"] = k.assign(seg=_daily_seg_ids(k))
                return d["_d1seg"]
            if "_d1" not in d:
                d["_d1"] = _daily_from_m1(self.m1(coin))
            return d["_d1"]
        return sbd.d1(coin)

    def segments(self, coin: str) -> pd.DataFrame:
        if self.injected:
            d = self._inj(coin)
            if d.get("segments") is not None:
                return d["segments"]
            if "_seg" not in d:
                d["_seg"] = _segments_from_bars(self.m1(coin), coin, self.end_day, d.get("successor"))
            return d["_seg"]
        return sbd.segments(coin)

    def fut_months(self, kind: str, coin: str, months) -> pd.DataFrame:
        """1m index (kind 'index') or perpetual ('perp') bars of the given months ('YYYY-MM'); empty = missing."""
        if self.injected:
            k = self._inj(coin).get("index_m1" if kind == "index" else "perp_m1")
            if k is None or not len(k):
                return pd.DataFrame(columns=["open_time", "open", "high", "low", "close",
                                             "updates" if kind == "index" else "trades"])
            if months is None:
                return k
            mm = np.array([_month_int(x) for x in months], np.int64)
            return k[np.isin(_month_of_min(_tmin(k.open_time)), mm)]
        if sbd.um_contract(coin) is None:
            return pd.DataFrame(columns=["open_time", "open", "high", "low", "close",
                                         "updates" if kind == "index" else "trades"])
        parts = []
        for m in sorted(set(months)):
            if m > self.end_day.strftime("%Y-%m"):
                continue
            k = sbd._fut_load(kind, coin, m)            # stinkbid_data's month cache (coding choice 14)
            if len(k):
                parts.append(k)
        if not parts:
            return pd.DataFrame(columns=["open_time", "open", "high", "low", "close",
                                         "updates" if kind == "index" else "trades"])
        return pd.concat(parts, ignore_index=True)

    def levels_data(self, coin: str):
        """The data argument for stinkbid_levels (None = real)."""
        if not self.injected:
            return None
        if coin not in self._lvdata:
            d = self._inj(coin)
            lv = {"d1": self.d1(coin), "m1": self.m1(coin), "real": False}
            if d.get("tick") is not None:
                lv["tick"] = d["tick"]
            lv.update(d.get("levels") or {})
            self._lvdata = {coin: lv}                     # one coin at a time (the levels memo lives in it)
        return self._lvdata[coin]

    def tbill(self, days) -> np.ndarray:
        """3-month T-bill, % a year, on UTC days (DatetimeIndex)."""
        idx = pd.DatetimeIndex(days)
        if self.injected:
            tb = self.data.get("tbill", 0.0)
            if isinstance(tb, pd.Series):
                s = tb.copy()
                s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
                return s.reindex(idx.tz_localize(None).normalize() if idx.tz is not None else idx.normalize(),
                                 method="ffill").fillna(0.0).to_numpy(float)
            return np.full(len(idx), float(tb))
        return sbd.tbill_daily(idx).to_numpy(float)

    def usd_hourly(self):
        if self.injected:
            return self.data.get("usd")
        try:
            return sbd.usdt_usd_hourly()
        except Exception:
            return None

    def agg(self, coin, day, windows):
        if self.injected:
            f = self.data.get("agg")
            return None if f is None else f(coin, day, windows)
        return sbd.agg_capacity(coin, day, windows)

    # ---- market-wide days (data_inventory §6.1, leave-one-out)
    def mw_table(self):
        """(per-day counts: day -> (n15, n_active)), per (coin, day): (hit, active)) for U-B members."""
        if self._mw is not None:
            return self._mw
        if self.injected:
            mw = self.data.get("mw")
            self._mw = ("given", mw) if mw is not None else ("none", None)
            return self._mw
        p = sbd.d1_panel()
        p = p[(p.seg >= 0) & (p.trades > 0)][["coin", "open_time", "low", "close", "seg"]].copy()
        p["day"] = (_tmin(p.open_time) // DAY_M).astype(np.int64)
        p = p.sort_values(["coin", "day"], kind="stable")
        same = (p.coin.to_numpy()[1:] == p.coin.to_numpy()[:-1]) & (np.diff(p.day.to_numpy()) == 1) & \
               (p.seg.to_numpy()[1:] == p.seg.to_numpy()[:-1])
        pc = np.r_[np.nan, np.where(same, p.close.to_numpy()[:-1], np.nan)]
        p["act"] = np.isfinite(pc)
        p["hit"] = p.act & (p.low.to_numpy() <= (1 - MW_DROP) * pc)
        u = self.universe()
        ub = u[u["U_B"].astype(bool)][["month", "coin"]]
        p["month"] = pd.to_datetime(p.day * 86400, unit="s").dt.strftime("%Y-%m")
        p = p.merge(ub.assign(ub=True), on=["month", "coin"], how="inner")
        tot = p.groupby("day")[["hit", "act"]].sum()
        self._mw = ("table", (tot, p.set_index(["coin", "day"])[["hit", "act"]]))
        return self._mw

    def mw_flags(self, coin: str, days: np.ndarray):
        """(market-wide flag, share of the OTHER active U-B coins at the 15% depth) for fills of a coin on UTC
        days (int days since 1970)."""
        kind, tab = self.mw_table()
        n = len(days)
        if kind == "none" or n == 0:
            return np.full(n, np.nan), np.full(n, np.nan)
        if kind == "given":
            g = tab[tab.coin == coin]
            dd = (_tmin(g.day) // DAY_M) if len(g) else np.zeros(0, np.int64)
            m = dict(zip(dd.tolist(), zip(g.mw.astype(float), g.get("mw_share", g.mw).astype(float))))
            a = np.array([m.get(int(d), (np.nan, np.nan)) for d in days], dtype=float).reshape(n, 2)
            return a[:, 0], a[:, 1]
        tot, per = tab
        hit = np.zeros(n)
        act = np.zeros(n)
        for i, d in enumerate(days):
            if (coin, int(d)) in per.index:
                r = per.loc[(coin, int(d))]
                hit[i], act[i] = float(r["hit"]), float(r["act"])
        T = tot.reindex(np.asarray(days, dtype=np.int64))
        oth = (T["hit"].to_numpy(float) - hit) / (T["act"].to_numpy(float) - act)
        return (oth >= MW_SHARE).astype(float), oth

    # ---- MoneyLine (the replicated pre-October-2026 line, moneyline_ref), per segment
    def moneyline(self, coin: str) -> pd.DataFrame:
        """Daily MoneyLine state of a coin: day (int), seg, green (1 green, 0 red, -1 undefined), restarted at every
        segment of the daily series (coding choice 7)."""
        if coin in self._ml:
            return self._ml[coin]
        k = self.d1(coin)
        k = k[(k.seg.to_numpy() >= 0) & ((k.trades.to_numpy() > 0) if "trades" in k else True)]
        day = (_tmin(k.open_time) // DAY_M).astype(np.int64)
        seg = k.seg.to_numpy()
        green = np.full(len(k), -1, np.int8)
        for s in np.unique(seg):
            ix = np.flatnonzero(seg == s)
            if len(ix) < 10:
                continue
            g = k.iloc[ix]
            st = mlr.supertrend(pd.DataFrame({"open": g.open.to_numpy(float), "high": g.high.to_numpy(float),
                                              "low": g.low.to_numpy(float), "close": g.close.to_numpy(float)}),
                                **mlr.MONEYLINE_PARAMS)
            defined = np.isfinite(st["line"].to_numpy())
            green[ix] = np.where(defined, st["green"].to_numpy().astype(np.int8), -1)
        out = pd.DataFrame({"day": day, "seg": seg, "green": green})
        if len(self._ml) > 8:
            self._ml.clear()
        self._ml[coin] = out
        return out

    def tick_table(self, coin: str) -> tuple:
        """(Monday 03:30 placement minutes, tick per placement) over the coin's history: the tick in effect for
        twins (coding choice 17)."""
        if coin in self._tick_tab:
            return self._tick_tab[coin]
        t0s = _weekly_minutes(PLACE_HM)
        lv = self.levels_data(coin)
        tm, tk = [], []
        d1 = self.d1(coin)
        first = _tmin(d1.open_time.iloc[0]) if len(d1) else 0
        for t0 in t0s:
            if t0 < first:
                continue
            I = sbl.inputs_at(coin, _mts(t0), data=lv)
            if I.get("tick_str"):
                tm.append(t0)
                tk.append(float(I["tick"]))
        res = (np.array(tm, np.int64), np.array(tk, float))
        if len(self._tick_tab) > 64:
            self._tick_tab.clear()
        self._tick_tab[coin] = res
        return res


def _daily_from_m1(k: pd.DataFrame) -> pd.DataFrame:
    """Daily bars (UTC days) from 1m bars with trades > 0: open first, close last, sums of volumes."""
    k = k[k.trades.to_numpy() > 0] if "trades" in k else k
    t = _tmin(k.open_time)
    day = t // DAY_M
    o = np.argsort(t, kind="stable")
    day = day[o]
    ud, st = np.unique(day, return_index=True)
    en = np.r_[st[1:], len(day)] - 1
    col = {c: k[c].to_numpy(float)[o] for c in ("open", "high", "low", "close")}
    out = {"open_time": _mts(ud * DAY_M), "open": col["open"][st], "high": np.maximum.reduceat(col["high"], st),
           "low": np.minimum.reduceat(col["low"], st), "close": col["close"][en]}
    for c in ("volume", "quote_volume", "taker_buy_quote"):
        if c in k:
            out[c] = np.add.reduceat(k[c].to_numpy(float)[o], st)
    out["trades"] = np.add.reduceat(k["trades"].to_numpy()[o], st) if "trades" in k else np.ones(len(ud), np.int64)
    out["seg"] = k["seg"].to_numpy()[o][st] if "seg" in k else np.zeros(len(ud), np.int32)
    return pd.DataFrame(out)


def _daily_seg_ids(d: pd.DataFrame) -> np.ndarray:
    """§4.1 segment ids of daily bars by stinkbid_data's rule (its _seg_ids: a new segment after a missing UTC day or
    at a >25% open jump; days without trades count as missing and get -1)."""
    day = _tmin(d.open_time) // DAY_M
    o = np.argsort(day, kind="stable")
    a = pd.DataFrame({"coin": "_", "day": (day[o] * DAY_M * MIN_NS).astype("datetime64[ns]"),
                      "trades": (d.trades.to_numpy() if "trades" in d else np.ones(len(d), np.int64))[o],
                      "open": d.open.to_numpy(float)[o], "close": d.close.to_numpy(float)[o]})
    seg = np.full(len(d), -1, np.int32)
    seg[o] = sbd._seg_ids(a)
    return seg


def _m1_seg_ids(m1: pd.DataFrame, d1: pd.DataFrame | None) -> np.ndarray:
    """Segment ids for injected 1m bars without `seg`, as stinkbid_data attaches them to real bars (§4.1): each bar
    takes its UTC day's daily id: the injected daily bars' `seg` when given, else _daily_seg_ids of the injected
    daily bars or of daily bars built from the 1m bars; -1 on a day without a traded daily bar."""
    if d1 is not None and "seg" in d1:
        dk, dseg = d1, d1.seg.to_numpy()
    else:
        dk = d1 if d1 is not None else _daily_from_m1(m1)
        dseg = _daily_seg_ids(dk)
    mp = dict(zip((_tmin(dk.open_time) // DAY_M).tolist(), np.asarray(dseg).tolist()))
    u, inv = np.unique(_tmin(m1.open_time) // DAY_M, return_inverse=True)
    return np.array([mp.get(int(x), -1) for x in u], np.int32)[inv]


def _segments_from_bars(k: pd.DataFrame, coin: str, end_day: pd.Timestamp, successor=None) -> pd.DataFrame:
    """A stinkbid_data.segments-shaped table for injected bars (§4.1): one row per `seg`; the last segment is
    data_end if it trades on the data end day, a swap if `successor` is given, else a delisting; a boundary inside
    the series is a 'gap' (missing days: a delisting at the gap) or a 'jump' (trading continued). Delisting values:
    VWAP of the last day with trading in hours 00 and 23 (quote volume / volume), and the last trade."""
    k = k.sort_values("open_time", kind="stable")
    seg = k.seg.to_numpy() if "seg" in k else np.zeros(len(k), np.int32)
    t = _tmin(k.open_time)
    live = k.trades.to_numpy() > 0 if "trades" in k else np.ones(len(k), bool)
    rows = []
    useg = [s for s in pd.unique(seg) if s >= 0]
    end_d = int(_tmin(end_day) // DAY_M)
    for n, s in enumerate(useg):
        ix = np.flatnonzero((seg == s) & live)
        if not len(ix):
            continue
        tt = t[ix]
        dd = tt // DAY_M
        hh = (tt % DAY_M) // 60
        days = np.unique(dd)
        full = [d for d in days if (hh[dd == d] == 0).any() and (hh[dd == d] == 23).any()]
        fd = full[-1] if full else (days[-2] if len(days) > 1 else days[-1])
        sel = ix[dd == fd]
        vol = k.volume.to_numpy(float)[sel].sum() if "volume" in k else 0.0
        qv = k.quote_volume.to_numpy(float)[sel].sum() if "quote_volume" in k else 0.0
        vwap = qv / vol if vol > 0 else float(np.mean(k.close.to_numpy(float)[sel]))
        last = int(ix[-1])
        r = dict(coin=coin, seg=int(s), first_day=_mts(int(days[0]) * DAY_M).tz_localize(None),
                 last_day=_mts(int(days[-1]) * DAY_M).tz_localize(None), kind="", continues=False, units=np.nan,
                 successor="", vwap_last_full_day=float(vwap), last_trade=float(k.close.to_numpy(float)[last]),
                 last_trade_time=_mts(int(t[last])), last_full_day=_mts(int(fd) * DAY_M).tz_localize(None))
        if n < len(useg) - 1:
            nxt = np.flatnonzero(seg == useg[n + 1])
            gap = (t[nxt[0]] // DAY_M) - days[-1] > 1 if len(nxt) else True
            r.update(kind="gap" if gap else "jump", continues=not gap, units=np.nan if gap else 1.0)
        elif days[-1] >= end_d:
            r.update(kind="data_end", continues=True, units=1.0)
        elif successor is not None:
            r.update(kind="swap", continues=True, units=float(successor[1]), successor=str(successor[0]))
        else:
            r.update(kind="delisting")
        rows.append(r)
    return pd.DataFrame(rows)


def _weekly_minutes(hm=PLACE_HM, first=FIRST_T0, last=LAST_T0) -> np.ndarray:
    a = _ts(first).normalize() + pd.Timedelta(hours=hm[0], minutes=hm[1])
    b = _ts(last).normalize() + pd.Timedelta(hours=hm[0], minutes=hm[1])
    return _tmin(pd.date_range(a, b, freq="7D"))


# ============================================================================ series: lineage, segments, bars
class Seg:
    """The segment table of a coin's lineage (the coin, then its swap successors): §4.1 kinds and values."""

    def __init__(self):
        self.coin, self.sid, self.kind = [], [], []
        self.t0, self.t1, self.U, self.nxt, self.term, self.val = [], [], [], [], [], []

    def freeze(self):
        self.t0 = np.asarray(self.t0, np.int64)
        self.t1 = np.asarray(self.t1, np.int64)
        self.U = np.asarray(self.U, float)
        self.nxt = np.asarray(self.nxt, np.int64)
        self.term = np.asarray(self.term, np.int64)
        self.val = np.asarray(self.val, float).reshape(-1, 4)
        self.sid = np.asarray(self.sid, np.int64)
        self.n = len(self.t0)
        self.key = {(c, int(s)): i for i, (c, s) in enumerate(zip(self.coin, self.sid))}
        return self


class Ser:
    """One series of 1m bars for exits and fills: arrays plus block structures."""

    def __init__(self, t, o, h, l, c, live, sidx, seg: Seg, kind: str):
        self.kind = kind
        self.t, self.o, self.h, self.l, self.c = t, o, h, l, c
        self.live = live
        self.sidx = sidx.astype(np.int64)
        self.n = len(t)
        self.hl = np.where(live, h, NEG_INF)
        self.ll = np.where(live, l, POS_INF)
        self.mx1, self.mx2 = _blk_max(self.hl)
        self.mn1, self.mn2 = _blk_min(self.ll)
        self.nxt = _next_live(live)
        self.seg = seg
        lo = np.full(seg.n, 0, np.int64)
        hi = np.full(seg.n, 0, np.int64)
        if self.n:
            for s in range(seg.n):
                ix = np.flatnonzero(self.sidx == s)
                if len(ix):
                    lo[s], hi[s] = ix[0], ix[-1] + 1
                else:
                    p = np.searchsorted(t, seg.t0[s])
                    lo[s] = hi[s] = p
        self.lo, self.hi = lo, hi
        self._hmin = None

    def hmin(self):
        """Live highs for minimum queries (F3d: a whole index minute below the threshold)."""
        if self._hmin is None:
            v = np.where(self.live, self.h, POS_INF)
            m1, m2 = _blk_min(v)
            self._hmin = (v, m1, m2)
        return self._hmin

    def idx(self, m):
        """First bar index with t >= m."""
        return np.searchsorted(self.t, m)

    def exit_args(self):
        s = self.seg
        return (self.t, self.o, self.hl, self.mx1, self.mx2, self.nxt, self.lo, self.hi, s.U, s.nxt, s.term,
                s.val, s.t1)


def _lineage(world: World, coin: str, depth: int = 4) -> list:
    """[(coin, units relative to the first coin, segments table)] along the frozen swap list."""
    out, u = [], 1.0
    c = coin
    for _ in range(depth):
        sg = world.segments(c)
        out.append((c, u, sg))
        if sg is None or not len(sg):
            break
        last = sg.iloc[-1]
        if str(last.get("kind", "")) != "swap" or not bool(last.get("continues", False)):
            break
        succ = str(last.get("successor", ""))
        if not succ or not world.has_coin(succ):
            break
        u = u * float(last["units"])
        c = succ
    return out


def build_spot(world: World, coin: str, with_successors: bool = True):
    """(Ser, own_n, frames): the coin's 1m spot series with its swap successors appended (prices in each bar's own
    units; the segment table carries the units), the number of the coin's own bars, and the coin's own frame."""
    seg = Seg()
    parts = []
    lin = _lineage(world, coin) if with_successors else [(coin, 1.0, world.segments(coin))]
    t_from = None
    prev_last = None
    own_n = 0
    own_frame = None
    for depth, (c, u, sg) in enumerate(lin):
        k = world.m1(c)
        if depth == 0:
            own_frame = k
        t = _tmin(k.open_time)
        if not np.all(np.diff(t) > 0):
            o_ = np.argsort(t, kind="stable")
            k = k.iloc[o_]
            t = t[o_]
            keep = np.r_[True, np.diff(t) > 0]
            k, t = k[keep], t[keep]
        sgc = k.seg.to_numpy() if "seg" in k else np.zeros(len(k), np.int64)
        keep = sgc >= 0
        if t_from is not None:
            keep &= t >= t_from
        k, t, sgc = k[keep], t[keep], sgc[keep]
        live = (k.trades.to_numpy() > 0) if "trades" in k else np.ones(len(k), bool)
        srow = {int(r.seg): r for r in sg.itertuples(index=False)} if sg is not None and len(sg) else {}
        useg = pd.unique(sgc)
        loc = {}
        for j, s in enumerate(useg):
            ix = np.flatnonzero(sgc == s)
            lv = ix[live[ix]]
            r = srow.get(int(s))
            idx = len(seg.t0)
            loc[int(s)] = idx
            seg.coin.append(c)
            seg.sid.append(int(s))
            seg.kind.append(str(getattr(r, "kind", "")) if r is not None else "")
            seg.t0.append(int(t[ix[0]]))
            seg.t1.append(int(t[lv[-1]]) + 1 if len(lv) else int(t[ix[-1]]) + 1)
            vw = float(getattr(r, "vwap_last_full_day", np.nan)) if r is not None else np.nan
            lt = float(getattr(r, "last_trade", np.nan)) if r is not None else np.nan
            if not np.isfinite(vw):
                vw = float(k.close.to_numpy(float)[lv[-1]]) if len(lv) else np.nan
            if not np.isfinite(lt):
                lt = float(k.close.to_numpy(float)[lv[-1]]) if len(lv) else np.nan
            seg.val.append([vw * (1 - HAIRCUT), lt * (1 - HAIRCUT), vw, 0.0])
            seg.U.append(np.nan)
            seg.nxt.append(-1)
            seg.term.append(1)
        # units and links inside the coin, and the terminal kinds (§4.1)
        first_idx = loc[int(useg[0])] if len(useg) else None
        if prev_last is not None and first_idx is None:
            seg.term[prev_last] = 1                       # successor without bars after the swap: a delisting
            break
        if prev_last is not None and first_idx is not None:
            seg.nxt[prev_last] = first_idx
            # the successor's units continue from the predecessor's last segment (its joined redenominations
            # included) at this swap's units (u / the predecessor's lineage units)
            seg.U[first_idx] = seg.U[prev_last] * (u / lin[depth - 1][1])
        elif first_idx is not None:
            seg.U[first_idx] = u
        for j, s in enumerate(useg):
            i = loc[int(s)]
            r = srow.get(int(s))
            kind = str(getattr(r, "kind", "")) if r is not None else ""
            cont = bool(getattr(r, "continues", False)) if r is not None else False
            units = float(getattr(r, "units", np.nan)) if r is not None else np.nan
            if not np.isfinite(seg.U[i]):
                seg.U[i] = u
            if j < len(useg) - 1:
                ni = loc[int(useg[j + 1])]
                if cont and kind != "swap":
                    seg.nxt[i] = ni
                    seg.term[i] = 0
                    seg.U[ni] = seg.U[i] * (units if np.isfinite(units) else 1.0)
                else:
                    seg.term[i] = 1
                    seg.U[ni] = u                         # a new asset for new positions (relisting)
            else:
                if kind == "data_end" or (r is None and seg.t1[i] > world.end_min):
                    seg.term[i] = 0
                elif kind == "swap" and cont:
                    seg.term[i] = 0 if depth + 1 < len(lin) else 1
                else:
                    seg.term[i] = 1
        parts.append((t, k, live))
        if depth == 0:
            own_n = len(t)
        last_i = loc[int(useg[-1])] if len(useg) else None
        last_kind = seg.kind[last_i] if last_i is not None else ""
        if last_kind == "swap" and depth + 1 < len(lin):
            prev_last = last_i
            t_from = seg.t1[last_i]
        else:
            # successors not available: the swap is valued as a delisting (coding choice 6)
            if last_i is not None and last_kind == "swap":
                seg.term[last_i] = 1
            break
    seg.freeze()
    t = np.concatenate([p[0] for p in parts]) if parts else np.zeros(0, np.int64)
    cat = lambda col, dt=float: np.concatenate([p[1][col].to_numpy(dt) for p in parts]) if parts else np.zeros(0, dt)
    live = np.concatenate([p[2] for p in parts]) if parts else np.zeros(0, bool)
    sl = []
    for p, (c, _, _) in zip(parts, lin):
        sg_ = p[1].seg.to_numpy() if "seg" in p[1] else np.zeros(len(p[1]), np.int64)
        us, inv = np.unique(sg_, return_inverse=True)
        sl.append(np.array([seg.key[(c, int(x))] for x in us], np.int64)[inv] if len(us) else np.zeros(0, np.int64))
    sidx = np.concatenate(sl) if sl else np.zeros(0, np.int64)
    ser = Ser(t, cat("open"), cat("high"), cat("low"), cat("close"), live, sidx, seg, "spot")
    qv = cat("quote_volume") if all("quote_volume" in p[1] for p in parts) else np.zeros(len(t))
    tbq = cat("taker_buy_quote") if all("taker_buy_quote" in p[1] for p in parts) else np.zeros(len(t))
    ser.qv = qv
    ser.sq = np.maximum(qv - tbq, 0.0)
    ser.trades = cat("trades", np.int64) if all("trades" in p[1] for p in parts) else live.astype(np.int64)
    return ser, own_n, own_frame


def build_index(world: World, coin: str, spot: Ser, months=None, kind: str = "index") -> Ser | None:
    """The index (kind 'index') or perpetual ('perp') 1m series of a coin and its successors, restricted to the
    trading time of the spot segments (a position's chain is the spot's). Index bars are live when updates >= 30
    and outside the Robinhood outage windows (§7); perpetual bars when trades > 0."""
    seg = spot.seg
    coins = list(dict.fromkeys(seg.coin))
    parts = []
    for c in coins:
        ix = [i for i in range(seg.n) if seg.coin[i] == c]
        a, b = seg.t0[ix].min(), seg.t1[ix].max()
        if months is None:
            ms = pd.period_range(_mts(a).tz_localize(None), _mts(b - 1).tz_localize(None), freq="M").strftime("%Y-%m")
        else:
            ms = [m for m in months]
        k = world.fut_months(kind, c, list(ms))
        if not len(k):
            continue
        t = _tmin(k.open_time)
        o_ = np.argsort(t, kind="stable")
        k, t = k.iloc[o_], t[o_]
        keep = np.r_[True, np.diff(t) > 0] if len(t) else np.zeros(0, bool)
        k, t = k[keep], t[keep]
        # assign each bar to the coin's segment whose trading interval holds it
        s_idx = np.full(len(t), -1, np.int64)
        for i in ix:
            m = (t >= seg.t0[i]) & (t < seg.t1[i])
            s_idx[m] = i
        sel = s_idx >= 0
        parts.append((t[sel], k[sel], s_idx[sel]))
    if not parts:
        return None
    t = np.concatenate([p[0] for p in parts])
    o_ = np.argsort(t, kind="stable")
    cat = lambda col: np.concatenate([p[1][col].to_numpy(float) for p in parts])[o_]
    sidx = np.concatenate([p[2] for p in parts])[o_]
    t = t[o_]
    if kind == "index":
        upd = np.concatenate([p[1]["updates"].to_numpy(np.int64) for p in parts])[o_]
        live = (upd >= IDX_MIN_UPDATES) & ~_in_rh_outage(t)
    else:
        upd = np.concatenate([p[1]["trades"].to_numpy(np.int64) for p in parts])[o_]
        live = upd > 0
    s = Ser(t, cat("open"), cat("high"), cat("low"), cat("close"), live, sidx, seg, kind)
    s.upd = upd
    s.present = np.ones(len(t), bool)
    return s


def build_daily(world: World, spot: Ser) -> dict:
    """Daily bars along the lineage, per spot segment: day, sidx, open, close, vwap, green (MoneyLine)."""
    seg = spot.seg
    rows = []
    for c in dict.fromkeys(seg.coin):
        k = world.d1(c)
        if "trades" in k:
            k = k[k.trades.to_numpy() > 0]
        k = k[k.seg.to_numpy() >= 0]
        day = (_tmin(k.open_time) // DAY_M).astype(np.int64)
        sid = k.seg.to_numpy().astype(np.int64)
        si = np.array([seg.key.get((c, int(s)), -1) for s in sid], np.int64)
        ml = world.moneyline(c)
        gm = dict(zip(zip(ml.day.tolist(), ml.seg.tolist()), ml.green.tolist()))
        green = np.array([gm.get((int(d), int(s)), -1) for d, s in zip(day, sid)], np.int8)
        vol = k.volume.to_numpy(float) if "volume" in k else np.ones(len(k))
        qv = k.quote_volume.to_numpy(float) if "quote_volume" in k else k.close.to_numpy(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            vwap = np.where(vol > 0, qv / vol, np.nan)
        keep = si >= 0
        # successor days only after the predecessor's last trade (the lineage's own bars)
        for i in np.unique(si[keep]):
            lo_day = seg.t0[i] // DAY_M
            hi_day = (seg.t1[i] - 1) // DAY_M
            m = (si == i) & ((day < lo_day) | (day > hi_day))
            keep &= ~m
        rows.append(pd.DataFrame({"day": day[keep], "sidx": si[keep], "open": k.open.to_numpy(float)[keep],
                                  "close": k.close.to_numpy(float)[keep], "vwap": vwap[keep],
                                  "green": green[keep]}))
    d = pd.concat(rows, ignore_index=True).sort_values(["day", "sidx"], kind="stable")
    d = d.drop_duplicates("day", keep="last").reset_index(drop=True)
    return {c: d[c].to_numpy() for c in d.columns}


# ============================================================================ programs (§6.3) and placements (§6.1)
def _v(method: str, **params) -> tuple:
    return (method, tuple(sorted(params.items())))


@dataclass(frozen=True)
class Program:
    """A bid program (§6.3): level variants, schedule (weekly | daily | every30 | every90), life, placement time,
    P1-lazy's keep rule, P1-G's green filter, H4's placebos."""
    name: str
    variants: tuple
    schedule: str = "weekly"
    life_days: float = 7.0
    hm: tuple = PLACE_HM
    lazy: bool = False
    green_only: bool = False
    placebos: bool = False


P1_VARIANTS = (_v("M2", k=6.0), _v("M2", k=8.0), _v("M2", k=10.0))
H4_PRIMARY = tuple(_v(m, **p) for m, p in sbl.H4_VARIANTS)
H4_ALL = tuple([_v("M4", N=n, buffer=b) for n in sbl.M4_N for b in sbl.M4_BUF]
               + [_v("M4f", N=n) for n in sbl.M4_N]
               + [_v("M4s"), _v("M5f"), _v("M5a"), _v("M5b"), _v("M6"), _v("M7")])
PROGRAMS = {
    "P1": Program("P1", P1_VARIANTS),
    "P1-k5-12": Program("P1-k5-12", (_v("M2", k=5.0), _v("M2", k=12.0))),
    "P1-30": Program("P1-30", P1_VARIANTS, "every30", 30.0),
    "P1-90": Program("P1-90", P1_VARIANTS, "every90", 90.0),
    "P1-1": Program("P1-1", P1_VARIANTS, "daily", 1.0),
    "P1-lazy": Program("P1-lazy", P1_VARIANTS, lazy=True),
    "P1-G": Program("P1-G", P1_VARIANTS, green_only=True),
    "P1-1330": Program("P1-1330", P1_VARIANTS, hm=PLACE_HM_SENS),
    "M1": Program("M1", tuple(_v("M1", d=d) for d in sbl.M1_D)),
    "M2a": Program("M2a", tuple(_v("M2a", kA=k) for k in sbl.M2A_K)),
    "M3": Program("M3", tuple(_v("M3", p=p) for p in sbl.M3_P)),
    "M8": Program("M8", (_v("M8"),)),
    "H4": Program("H4", H4_PRIMARY, placebos=True),
    "H4-all": Program("H4-all", H4_ALL, placebos=True),
}
LAZY_BAND = 0.05                                  # §6.3 P1-lazy: keep a resting bid within 5% of the new level


def placement_minutes(prog: Program, end_min: int) -> np.ndarray:
    """Placement times (UTC minutes) of a program (§4 windows, §6.1, §6.3)."""
    a = _ts(FIRST_T0).normalize() + pd.Timedelta(hours=prog.hm[0], minutes=prog.hm[1])
    if prog.schedule == "weekly":
        b = _ts(LAST_T0).normalize() + pd.Timedelta(hours=prog.hm[0], minutes=prog.hm[1])
        out = _tmin(pd.date_range(a, b, freq="7D"))
    elif prog.schedule == "daily":
        b = _ts(LAST_T0_DAILY).normalize() + pd.Timedelta(hours=prog.hm[0], minutes=prog.hm[1])
        out = _tmin(pd.date_range(a, b, freq="1D"))
    elif prog.schedule in ("every30", "every90"):
        step = 30 if prog.schedule == "every30" else 90
        b = _ts(LAST_T0).normalize() + pd.Timedelta(hours=prog.hm[0], minutes=prog.hm[1])
        out = _tmin(pd.date_range(a, b, freq=f"{step}D"))
    else:
        raise ValueError(f"unknown schedule {prog.schedule!r}")
    return out[out <= end_min]


def _life_ends(times: np.ndarray, life_m: int, end_min: int) -> np.ndarray:
    """Each placement's life ends when the next one is placed (§6.1: the previous bids stay live until the new ones
    are placed), or after its life for the last; never after the data end."""
    nxt = np.r_[times[1:], times[-1] + life_m] if len(times) else times
    return np.minimum(np.minimum(nxt, times + life_m), end_min + 1)


# ============================================================================ bids
BID_COLS = ["bid_id", "program", "universe", "coin", "method", "params", "rung", "variant", "shift", "real", "cw",
            "t0", "d0", "P0", "sigma30", "atr_pct", "tick", "tick_str", "L", "L_tau", "n_ticks", "delta", "sidx",
            "seg", "live_from", "life_end", "month", "ml_d0", "order_weeks"]


def _rung(method: str, params: tuple) -> float:
    p = dict(params)
    for k in ("k", "d", "kA", "p", "N"):
        if k in p:
            return float(p[k])
    return np.nan


def _ml_state(daily_ml: pd.DataFrame, day: int, seg_id: int) -> int:
    m = (daily_ml.day.to_numpy() == day) & (daily_ml.seg.to_numpy() == seg_id)
    ix = np.flatnonzero(m)
    return int(daily_ml.green.to_numpy()[ix[0]]) if len(ix) else -1


def _coin_bids(world: World, prog: Program, universe: str, coin: str, member_months: np.ndarray, spot: Ser,
               cfg: dict) -> tuple[list, list]:
    """Bid rows of one coin (not lazy): every placement in a member month whose inputs are ok, every variant that
    gives a level (and its four placebos for H4 programs). Returns (rows, status counts rows)."""
    times = placement_minutes(prog, world.end_min)
    ends = _life_ends(times, int(round(prog.life_days * DAY_M)), world.end_min)
    mon = _month_of_min(times)
    sel = np.isin(mon, member_months)
    lv = world.levels_data(coin)
    d1 = world.d1(coin)
    dseg = dict(zip((_tmin(d1.open_time) // DAY_M).tolist(), d1.seg.to_numpy().tolist()))
    ml = world.moneyline(coin) if prog.green_only or cfg.get("ml", True) else None
    rows, status = [], []
    for t0, te, mo in zip(times[sel], ends[sel], mon[sel]):
        I = sbl.inputs_at(coin, _mts(t0), data=lv)
        if not I["ok"]:
            status.append((coin, int(t0), "inputs", I["why"]))
            continue
        d0 = int(_tmin(I["d0"]) // DAY_M)
        sg = dseg.get(d0)
        sidx = spot.seg.key.get((coin, int(sg)), -1) if sg is not None else -1
        if sidx < 0:
            status.append((coin, int(t0), "no_segment", ""))
            continue
        mls = _ml_state(ml, d0, int(sg)) if ml is not None else -1
        if prog.green_only and mls != 1:
            status.append((coin, int(t0), "not_green", ""))
            continue
        week = int((t0 - _tmin(FIRST_T0)) // (7 * DAY_M))
        for m, params in prog.variants:
            r = sbl.level_info(m, I, **dict(params))
            label = sbl.variant_label(m, dict(params))
            if r["status"] != "ok":
                status.append((coin, int(t0), "level:" + r["status"], label))
                continue
            L, delta, n = float(r["L"]), float(r["delta"]), int(r["n_ticks"])
            base = dict(program=prog.name, universe=universe, coin=coin, method=m, params=str(dict(params)),
                        rung=_rung(m, params), variant=label, cw=f"{coin}|{week}", t0=int(t0), d0=d0,
                        P0=float(I["P0"]), sigma30=float(I["sigma30"]), atr_pct=float(I["atr_pct"]),
                        tick=float(I["tick"]), tick_str=str(I["tick_str"]), sidx=int(sidx), seg=int(sg),
                        live_from=int(t0) + 1,
                        life_end=int(te), month=int(mo), ml_d0=mls, order_weeks=1)
            rows.append(dict(base, shift=0.0 if prog.placebos else np.nan, real=True, L=L,
                             L_tau=sbl.tick_value(n - 1, I["tick_str"]), n_ticks=n, delta=delta))
            if prog.placebos:
                for shift, Lp, dp in sbl.placebos(L, inputs=I):
                    if Lp is None:
                        status.append((coin, int(t0), "placebo_none", f"{label} {shift:+.1f}"))
                        continue
                    n_p = sbl.floor_n(Lp, I["tick_str"])
                    rows.append(dict(base, shift=float(shift), real=False, L=float(Lp),
                                     L_tau=sbl.tick_value(n_p - 1, I["tick_str"]), n_ticks=int(n_p),
                                     delta=float(dp)))
    return rows, status


def _lazy_bids(world: World, prog: Program, universe: str, coin: str, member_months: np.ndarray, spot: Ser,
               cfg: dict) -> tuple[list, list]:
    """P1-lazy (§6.3): weekly, but a resting order is kept (same limit, same placement inputs) while it has not
    filled (F1) and the new level is within 5% of it; otherwise it is cancelled at the placement and re-placed
    (coding choice 4)."""
    weekly, status = _coin_bids(world, replace(prog, lazy=False), universe, coin, member_months, spot, cfg)
    times = placement_minutes(prog, world.end_min)
    life_m = int(round(prog.life_days * DAY_M))
    by = {}
    for r in weekly:
        by[(r["variant"], r["t0"])] = r
    out = []
    for m, params in prog.variants:
        label = sbl.variant_label(m, dict(params))
        cur = None
        for t0 in times:
            new = by.get((label, int(t0)))
            if cur is not None:
                # has the resting order filled (F1) before this placement?
                s = cur["sidx"]
                a = max(spot.idx(cur["live_from"]), spot.lo[s])
                b = min(spot.idx(int(t0)), spot.hi[s])
                filled = a < b and _first_le(spot.ll, spot.mn1, spot.mn2, a, b, cur["L_tau"]) >= 0
                keep = (not filled and new is not None and new["sidx"] == cur["sidx"]
                        and abs(new["L"] / cur["L"] - 1.0) <= LAZY_BAND)
                if keep:
                    cur["life_end"] = int(min(t0 + life_m, new["life_end"], world.end_min + 1))
                    cur["order_weeks"] += 1
                    continue
                cur["life_end"] = int(min(cur["life_end"], t0))
                cur = None
            if new is not None:
                cur = dict(new)
                out.append(cur)
    return out, status


def build_bids(world: World, prog: Program, universe: str, coin: str, member_months, spot: Ser, cfg: dict):
    if prog.lazy:
        return _lazy_bids(world, prog, universe, coin, member_months, spot, cfg)
    return _coin_bids(world, prog, universe, coin, member_months, spot, cfg)


# ============================================================================ fills (§7)
RULES_ALL = ("F1", "F2", "F3_1", "F3_2", "F3_3", "F3_5", "F3d_1", "F3d_2", "F3d_3", "F3d_5", "F4", "F5")
RULE_S = {"F3_1": 0.01, "F3_2": 0.02, "F3_3": 0.03, "F3_5": 0.05, "F3d_1": 0.01, "F3d_2": 0.02, "F3d_3": 0.03,
          "F3d_5": 0.05}


def _rule_route(rule: str) -> int:
    if rule in ("F1", "F2", "F5"):
        return RT_SPOT
    if rule == "F4":
        return RT_IDX4
    return RT_IDX3


def _bid_ranges(ser: Ser, b: pd.DataFrame, spot_seg_bound: bool):
    """[a, e) bar ranges of the bids' lives on a series: from the first bar at/after live_from to the life end,
    never past the end of trading of the bid's segment (§4.1: the bid is cancelled at the boundary)."""
    sidx = b.sidx.to_numpy(np.int64)
    a = ser.idx(b.live_from.to_numpy(np.int64))
    if spot_seg_bound:
        e = np.minimum(ser.idx(b.life_end.to_numpy(np.int64)), ser.hi[sidx])
        a = np.maximum(a, ser.lo[sidx])
    else:
        tend = np.minimum(b.life_end.to_numpy(np.int64), ser.seg.t1[sidx])
        e = ser.idx(tend)
    return a.astype(np.int64), np.maximum(e, 0).astype(np.int64)


def coin_fills(b: pd.DataFrame, spot: Ser, idx: Ser | None, perp: Ser | None, rules, usd=None) -> dict:
    """First fill bar per bid and rule (§7): F1 trade-through by one tick on live spot minutes; F2 touch; F3 index
    low <= L / (1 + s) on live index minutes; F3d the whole index minute (high) <= L / (1 + s); F4 index low <= L;
    F5 the perpetual's last price, F1 rule. Returns {rule: bar index array (-1 none)} plus 'F3usd_1' / 'F3usd_3'
    (index converted to USD; K8) when an hourly USD proxy is given."""
    out = {}
    n = len(b)
    L = b.L.to_numpy(float)
    Lt = b.L_tau.to_numpy(float)
    a, e = _bid_ranges(spot, b, True)
    if "F1" in rules:
        out["F1"] = _k_first_le_batch(spot.ll, spot.mn1, spot.mn2, a, e, Lt)
    if "F2" in rules:
        out["F2"] = _k_first_le_batch(spot.ll, spot.mn1, spot.mn2, a, e, L)
    if "F5" in rules:
        if perp is not None and perp.n:
            pa, pe = _bid_ranges(perp, b, False)
            out["F5"] = _k_first_le_batch(perp.ll, perp.mn1, perp.mn2, pa, pe, Lt)
        else:
            out["F5"] = np.full(n, -1, np.int64)
    idx_rules = [r for r in rules if r.startswith("F3") or r == "F4"]
    if idx_rules:
        if idx is not None and idx.n:
            ia, ie = _bid_ranges(idx, b, False)
            for r in idx_rules:
                if r == "F4":
                    out[r] = _k_first_le_batch(idx.ll, idx.mn1, idx.mn2, ia, ie, L)
                elif r.startswith("F3d"):
                    v, m1, m2 = idx.hmin()
                    out[r] = _k_first_le_batch(v, m1, m2, ia, ie, L / (1 + RULE_S[r]))
                else:
                    out[r] = _k_first_le_batch(idx.ll, idx.mn1, idx.mn2, ia, ie, L / (1 + RULE_S[r]))
            if usd is not None and len(usd):
                f = pd.Series(usd["usd_per_usdt"].to_numpy(float), index=_tmin(usd.index) // 60)
                fac = f.reindex(idx.t // 60).to_numpy(float)
                lu = np.where(np.isfinite(fac), idx.ll * fac, POS_INF)
                m1, m2 = _blk_min(lu)
                for s, nm in ((0.01, "F3usd_1"), (0.03, "F3usd_3")):
                    out[nm] = _k_first_le_batch(lu, m1, m2, ia, ie, L / (1 + s))
        else:
            for r in idx_rules:
                out[r] = np.full(n, -1, np.int64)
    return out


def capacity(world: World, coin: str, b: pd.DataFrame, spot: Ser, i_fill: np.ndarray, mode: str = "c1",
             max_w_per: int = 64, curve: bool = False):
    """§7 capacity of F1 fills: windows (draft §8.3) accumulated causally over the order's life; C1 from the 1m
    bars and, with mode 'agg', the seller-initiated aggTrades notional below L (stinkbid_data.agg_capacity).
    Filled dollars = min(Q, theta C) at Q = 1k / 10k / 100k and theta = 1 / 0.25, as a share of Q at the end of the
    life, with the minute the order completed (t_full_*). Returns one row per bid with an F1 fill; curve=True also
    returns the capacity accumulated minute by minute (row, minute, cum: dollars through the end of that minute, on
    the row's cap_src), which the D7 account sizes positions from (V13; coding choice 21)."""
    sel = np.flatnonzero(i_fill >= 0)
    cols = ["row", "n_windows", "c1_first", "c1_life", "agg_first", "agg_life", "agg_missing", "cap_src"]
    if not len(sel):
        empty = pd.DataFrame(columns=cols)
        return (empty, pd.DataFrame(columns=["row", "minute", "cum"])) if curve else empty
    a, e = _bid_ranges(spot, b.iloc[sel], True)
    j_i = i_fill[sel].astype(np.int64)
    L = b.L.to_numpy(float)[sel]
    thr = b.L_tau.to_numpy(float)[sel]
    max_w = max_w_per * len(sel) + 1024
    while True:
        w_fill = np.empty(max_w, np.int64)
        w_a = np.empty(max_w, np.int64)
        w_b = np.empty(max_w, np.int64)
        w_c1 = np.empty(max_w, float)
        nw = _k_capacity(spot.t, spot.l, spot.h, spot.live, spot.qv, spot.sq, spot.sidx, j_i, e, L, thr,
                         CAP_WIN_M, max_w, w_fill, w_a, w_b, w_c1)
        if nw < max_w:
            break
        max_w *= 4
    W = pd.DataFrame({"j": w_fill[:nw], "a": w_a[:nw], "b": w_b[:nw], "c1": w_c1[:nw]})
    W["t_a"] = spot.t[W.a.to_numpy()]
    W["t_b"] = spot.t[np.maximum(W.b.to_numpy() - 1, 0)] + 1
    agg_m = None
    if mode == "agg" and nw:
        # aggTrades per window minute (stinkbid_data.agg_capacity; one zip per coin-day)
        W["L"] = L[W.j.to_numpy()]
        rows = []
        miss = np.zeros(len(sel), bool)
        day_a = W.t_a.to_numpy() // DAY_M
        day_b = (W.t_b.to_numpy() - 1) // DAY_M
        for d in np.unique(np.r_[day_a, day_b]):
            on = (day_a <= d) & (day_b >= d)
            if not on.any():
                continue
            ww = W[on]
            wins = pd.DataFrame({"wid": ww.index.to_numpy(), "L": ww.L.to_numpy(),
                                 "start": _mts(ww.t_a.to_numpy()), "end": _mts(ww.t_b.to_numpy())})
            res = world.agg(coin, _mts(int(d) * DAY_M).tz_localize(None), wins)
            if res is None:
                miss[ww.j.to_numpy()] = True
                continue
            if res.attrs.get("missing", False):
                miss[ww.j.to_numpy()] = True
            if len(res):
                rows.append(pd.DataFrame({"wid": res.wid.to_numpy(), "minute": _tmin(res.minute),
                                          "usd": res.sell_below_usd.to_numpy(float)}))
        agg_m = (pd.concat(rows, ignore_index=True) if rows else
                 pd.DataFrame(columns=["wid", "minute", "usd"]), miss)
    out = []
    curves = []
    per_min = {}
    if agg_m is not None and len(agg_m[0]):
        g = agg_m[0].groupby("wid")
        per_min = {int(k): v.sort_values("minute") for k, v in g}
    for jj in range(len(sel)):
        ws = W[W.j == jj]
        r = dict(row=int(sel[jj]), n_windows=len(ws), c1_first=float(ws.c1.iloc[0]) if len(ws) else 0.0,
                 c1_life=float(ws.c1.sum()), agg_first=np.nan, agg_life=np.nan, agg_missing=False, cap_src="c1")
        # the fill minute alone (§4.1 bad-print sensitivity: < $1k of seller-initiated notional below L)
        i0 = int(j_i[jj])
        rng0 = spot.h[i0] - spot.l[i0]
        f0 = min(max((L[jj] - spot.l[i0]) / rng0, 0.0), 1.0) if rng0 > 0 else float(spot.l[i0] < L[jj])
        r["c1_m0"] = float(spot.sq[i0] * f0) if spot.live[i0] else 0.0
        r["agg_m0"] = np.nan
        if agg_m is not None:
            r["agg_missing"] = bool(agg_m[1][jj])
            if not r["agg_missing"]:
                w0 = int(ws.index[0]) if len(ws) else -1
                pm0 = per_min.get(w0)
                r["agg_m0"] = float(pm0.usd[pm0.minute.to_numpy() == spot.t[i0]].sum()) if pm0 is not None else 0.0
                firsts = [per_min[int(w)].usd.sum() if int(w) in per_min else 0.0 for w in ws.index[:1]]
                lifes = [per_min[int(w)].usd.sum() if int(w) in per_min else 0.0 for w in ws.index]
                r.update(agg_first=float(sum(firsts)), agg_life=float(sum(lifes)), cap_src="agg")
        # shares at the end of the life and the minute the order completed (causal accumulation)
        if r["cap_src"] == "agg":
            mins = [per_min[int(w)][["minute", "usd"]] for w in ws.index if int(w) in per_min]
            cum = pd.concat(mins) if mins else pd.DataFrame({"minute": [], "usd": []})
            cm, cv = cum.minute.to_numpy(np.int64), np.cumsum(cum.usd.to_numpy(float))
            C = r["agg_life"]
        else:
            # C1 accumulates per minute inside each window
            cm_l, cv_l = [], []
            for w in ws.itertuples():
                k = np.arange(w.a, w.b)
                lv = spot.live[k]
                rng = spot.h[k] - spot.l[k]
                with np.errstate(divide="ignore", invalid="ignore"):
                    f = np.where(rng > 0, np.clip((L[jj] - spot.l[k]) / rng, 0, 1),
                                 (spot.l[k] < L[jj]).astype(float))
                cm_l.append(spot.t[k])
                cv_l.append(np.where(lv, spot.sq[k] * f, 0.0))
            cm = np.concatenate(cm_l) if cm_l else np.zeros(0, np.int64)
            cv = np.cumsum(np.concatenate(cv_l)) if cv_l else np.zeros(0)
            C = r["c1_life"]
        for Q in Q_SIZES:
            for th in THETAS:
                key = f"{int(Q / 1000)}k_{th:g}"
                r[f"share_{key}"] = min(1.0, th * C / Q) if Q > 0 else np.nan
                k = np.flatnonzero(th * cv >= Q)
                r[f"t_full_{key}"] = int(cm[k[0]]) + 1 if len(k) else -1
        out.append(r)
        if curve:
            curves.append(pd.DataFrame({"row": int(sel[jj]), "minute": np.asarray(cm, np.int64),
                                        "cum": np.asarray(cv, float)}))
    df = pd.DataFrame(out)
    if curve:
        return df, (pd.concat(curves, ignore_index=True) if curves else
                    pd.DataFrame(columns=["row", "minute", "cum"]))
    return df


# ============================================================================ exits (§8) and benchmarks (§10.1)
@dataclass(frozen=True)
class ExitSpec:
    """An exit rule (§8): flip (target + time stop, sell live at rule M or 1 minute after the fill: 'bot'), hold
    (X-HOLD-h: sell at the first live minute at or after M(fill + h)) or theta (D6: the price at M(fill) + 72 h)."""
    name: str
    kind: str                       # flip | hold | theta
    target: str = "R"               # flip targets: R g5 g10 g20 sig1 sig2 H24 P0
    stop_m: int = FLIP_STOP_H * 60  # minutes (holds: h days)
    lat: str = "M"                  # M | bot


FLIP = ExitSpec("FLIP", "flip")
FLIP_BOT = ExitSpec("FLIP_bot", "flip", lat="bot")
GRID = tuple(ExitSpec(f"G_{tg}_{h}h", "flip", tg, h * 60) for tg in GRID_TARGETS for h in GRID_STOPS_H
             if not (tg == "R" and h == FLIP_STOP_H))
HOLDS = tuple(ExitSpec(f"HOLD{d}", "hold", "none", d * DAY_M) for d in HOLD_DAYS)
THETA = ExitSpec("TH72", "theta", "none", 72 * 60)
EXIT_SPECS = {e.name: e for e in (FLIP, FLIP_BOT) + GRID + HOLDS + (THETA,)}


def default_exits(rules) -> dict:
    """The outcome plan (coding choice 18): every pre-registered exit on F1; the flip (rule M) on every other rule,
    plus the bot flip and the 90-day hold on F3 (s = 1%) beside the F1 rows."""
    plan = {}
    for r in rules:
        if r == "F1":
            plan[r] = (FLIP, FLIP_BOT) + GRID + HOLDS + (THETA,)
        elif r == "F3_1":
            plan[r] = (FLIP, FLIP_BOT, EXIT_SPECS["HOLD90"])
        else:
            plan[r] = (FLIP,)
    return plan


def _go_live(m, lat: str):
    return (np.asarray(m, np.int64) + 1) if lat == "bot" else rule_m(np.asarray(m, np.int64))


def _horizon(spec: ExitSpec, m):
    """Minute by which an exit from an entry at minute m is decided (its whole horizon, §4 windows)."""
    m = np.asarray(m, np.int64)
    if spec.kind == "theta":
        return rule_m(m) + spec.stop_m
    return rule_m(m + spec.stop_m)


def _cutoff(fn, end_min: int, span_m: int) -> int:
    """Largest entry minute te with fn(te) <= end_min (fn non-decreasing)."""
    lo, hi = end_min - span_m - 4 * DAY_M, end_min
    if fn(np.int64(hi)) <= end_min:
        return hi
    if fn(np.int64(lo)) > end_min:
        lo = end_min - span_m - 40 * DAY_M
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if fn(np.int64(mid)) <= end_min:
            lo = mid
        else:
            hi = mid
    return int(lo)


def _next_tick(T, tick_str) -> np.ndarray:
    """The spot sell trigger R + tau of §8 / K5 ('high >= limit + tau') for targets on the tick grid: the double
    nearest the decimal next tick (n_T + 1) tau, so a minute whose high prints exactly one tick through the target
    fills it (the float sum dbl(n tau) + dbl(tau) can exceed dbl((n + 1) tau); coding choice 25). A target that is not
    on its tick grid keeps the float sum T + tau; NaN / inf targets give inf."""
    T = np.asarray(T, float)
    tick_str = np.broadcast_to(np.asarray(tick_str, dtype=object), T.shape)
    out = np.full(T.shape, np.inf)
    for i in range(T.size):
        x, ts = float(T.flat[i]), str(tick_str.flat[i])
        if not (math.isfinite(x) and x > 0):
            continue
        n = sbl.ceil_n(x, ts)
        if n is not None and sbl.tick_value(n, ts) == x:
            out.flat[i] = sbl.tick_value(n + 1, ts)
        else:
            out.flat[i] = x + float(ts)
    return out


def _jobs_for(spec: ExitSpec, rule: str, m, T, tau, route_entry_seg, up=None):
    """Kernel job arrays for exits from entry minutes m (fills: the fill minute; twins: the entry minute). up: the
    spot trade-through price per job (fills: _next_tick of their on-grid targets); default T + tau (twins' unrounded
    targets, coding choice 11)."""
    m = np.asarray(m, np.int64)
    n = len(m)
    if spec.kind == "flip":
        g = _go_live(m, spec.lat)
        S = rule_m(m + spec.stop_m)
        TT = np.asarray(T, float)
    elif spec.kind == "hold":
        S = rule_m(m + spec.stop_m)
        g = S.copy()
        TT = np.full(n, np.inf)
    else:
        S = rule_m(m) + spec.stop_m
        g = S.copy()
        TT = np.full(n, np.inf)
    s = RULE_S.get(rule, 0.0)
    if _rule_route(rule) == RT_IDX3 and s >= 0.02:
        scr = np.full(n, s)
        tcr = m + CRASH_SPREAD_H * 60
    else:
        scr = np.full(n, F3_SPREAD)
        tcr = np.zeros(n, np.int64)
    if spec.kind != "flip":
        UP = np.full(n, np.inf)
    elif up is None:
        UP = TT + np.asarray(tau, float) * np.ones(n)
    else:
        UP = np.asarray(up, float) * np.ones(n)
    return (np.asarray(route_entry_seg, np.int64), g.astype(np.int64), S.astype(np.int64), TT,
            UP, scr, tcr.astype(np.int64))


def run_exits(ser: Ser, route: int, jobs) -> dict:
    n = len(jobs[0])
    out = {k: np.empty(n, dt) for k, dt in (("kind", np.int64), ("idx", np.int64), ("t", np.int64),
                                             ("px", float), ("raw", float), ("seg", np.int64))}
    if n:
        _k_exit(*ser.exit_args(), route, *jobs, out["kind"], out["idx"], out["t"], out["px"], out["raw"],
                out["seg"])
    return out


def _returns(route: int, rule: str, entry_cost, ex: dict, ser: Ser, entry_seg, cost: str = "C-RH") -> dict:
    """Per-position net returns (§10.2): spot route r = exit (1 - c_s) / (entry (1 + c_b)) - 1 with c_s the limit
    cost for resting targets and the market cost otherwise; F3 r = proceeds / entry - 1 (spread embedded); F4 at
    C-EX. entry_cost = the entry price before the buy cost (fills: L; twins: the entry minute's open, plus the F3
    ask). Delisting rows also get the §4.1 sensitivities (last trade x 0.7, 0% and 100% haircuts)."""
    kind = ex["kind"]
    px = ex["px"]
    if route == RT_SPOT:
        cb, cl, cm = COSTS[cost]
    elif route == RT_IDX4:
        cb, cl, cm = F4_BUY, COSTS["C-EX"][1], COSTS["C-EX"][2]
    else:
        cb, cl, cm = 0.0, 0.0, 0.0
    cs = np.where(kind == EK_TARGET, cl, cm)
    if route == RT_IDX3:
        # delisting values on the F3 route get the route's market spread (coding choice 12)
        cs = np.where(kind == EK_DELIST, F3_SPREAD, 0.0)
    ok = np.isin(kind, (EK_TARGET, EK_MARKETABLE, EK_STOP, EK_DELIST))
    r = np.where(ok, px * (1 - cs) / (np.asarray(entry_cost, float) * (1 + cb)) - 1, np.nan)
    out = {"r": r}
    dl = kind == EK_DELIST
    if dl.any():
        seg = ser.seg
        s_ex = np.where(dl, ex["seg"], 0)
        fac = seg.U[s_ex] / seg.U[np.asarray(entry_seg, np.int64)]
        for k, nm in ((1, "r_dl_last"), (2, "r_dl0"), (3, "r_dl100")):
            v = seg.val[s_ex, k] * fac
            out[nm] = np.where(dl, v * (1 - cs) / (np.asarray(entry_cost, float) * (1 + cb)) - 1, r)
    else:
        for nm in ("r_dl_last", "r_dl0", "r_dl100"):
            out[nm] = r
    return out


def _targets(spec: ExitSpec, L, P0, sigma, tick_str, H24):
    """Flip targets on the venue tick (rounded up, §8): R = ceil(L + (P0 - L) / 2), L (1 + g), L e^sigma, L e^2sigma,
    H24, P0."""
    L, P0, sigma, H24 = (np.asarray(x, float) for x in (L, P0, sigma, H24))
    tick_str = list(tick_str)
    raw = {"R": L + 0.5 * (P0 - L), "g5": L * 1.05, "g10": L * 1.10, "g20": L * 1.20, "sig1": L * np.exp(sigma),
           "sig2": L * np.exp(2 * sigma), "H24": H24, "P0": P0}[spec.target]
    out = np.empty(len(L))
    for i in range(len(L)):
        if not np.isfinite(raw[i]) or raw[i] <= 0:
            out[i] = np.nan
            continue
        out[i] = sbl.ceil_tick(float(raw[i]), tick_str[i])
    return out


def _tick_str_of(tick: float) -> str:
    """Decimal string of a power-of-ten tick (the levels module's ticks are 10^-d, d >= 0)."""
    return sbl._tick_str(int(round(-math.log10(tick)))) if tick < 1 else "1"


# ============================================================================ twins: eligibility and draws (§10.1)
class Elig:
    """Eligible twin entry bars of one coin on one series (§10.1 B-TWIN): live bars of the coin's own segments in the
    universe's member months, sorted by time, with distinct-day prefix counts (the 182-day pooling rule)."""

    def __init__(self, ser: Ser, own_seg: np.ndarray, member_months: np.ndarray):
        ok = ser.live.copy()
        ok &= own_seg[np.clip(ser.sidx, 0, None)] & (ser.sidx >= 0)
        if member_months is None or not len(member_months):
            ok[:] = False
        else:
            ok &= np.isin(_month_of_min(ser.t), member_months)
        self.bars = np.flatnonzero(ok).astype(np.int64)
        self.t = ser.t[self.bars]
        self.d = self.t // DAY_M
        newday = np.r_[True, self.d[1:] != self.d[:-1]] if len(self.d) else np.zeros(0, bool)
        self.cd = np.r_[0, np.cumsum(newday)].astype(np.int64)

    def window(self, cut: int, tau: int, excl_days: int):
        """(i0, i1, nL, nR, eligible days) outside [tau - X, tau + X] and at or before the cutoff minute."""
        k = int(np.searchsorted(self.t, cut, side="right"))
        i0 = min(int(np.searchsorted(self.t, tau - excl_days * DAY_M, side="left")), k)
        i1 = min(int(np.searchsorted(self.t, tau + excl_days * DAY_M, side="right")), k)
        nL, nR = i0, k - i1
        days = int(self.cd[i0])
        if nR > 0:
            days += int(self.cd[k] - self.cd[i1]) + (1 if i1 > 0 and self.d[i1] == self.d[i1 - 1] else 0)
        return i0, i1, nL, nR, days

    def pick(self, u, i0, i1, nL, nR):
        k = np.minimum((np.asarray(u) * (nL + nR)).astype(np.int64), nL + nR - 1)
        return np.where(k < nL, self.bars[np.minimum(k, max(len(self.bars) - 1, 0))],
                        self.bars[np.minimum(i1 + k - nL, max(len(self.bars) - 1, 0))])

    def day_table(self):
        """(days, eligible minutes per day) for the pooled twins (coding choice 15)."""
        if not len(self.d):
            return np.zeros(0, np.int64), np.zeros(0, np.int64)
        u, c = np.unique(self.d, return_counts=True)
        return u.astype(np.int64), c.astype(np.int64)

    def rank_in_day(self, day: int, rank: int) -> int:
        a = int(np.searchsorted(self.d, day, side="left"))
        return int(self.bars[a + rank])


def _twin_u(fill_id: int, n: int = R_TWINS):
    """§10.1: default_rng(20261118 + fill index); the first R uniforms place the B-TWIN entries (the same uniforms on
    every route and exit), the next R the B-POST entries (coding choice 16)."""
    rng = np.random.default_rng(SEED + int(fill_id))
    return rng.random(n), rng.random(n)


def index_months_for(members, q1_members, buffer: int = IDX_BUFFER_M) -> list:
    """The 'YYYY-MM' months the outcome stage reads on the index routes for one coin on real data (coding choice 27):
    every month m of the coin's program-universe or U-Q1 membership, and the `buffer` months after each. Bids live in
    member months (at most 90 days), twins enter in member months, and the longest index-route reach is a 90-day bid
    life plus B-POST's 30 days plus a 90-day hold, about 7 months; _pass2_coin checks every index-route horizon."""
    ms = np.union1d(np.asarray(members, np.int64).ravel(), np.asarray(q1_members, np.int64).ravel())
    if not len(ms):
        return []
    allm = np.unique((ms[:, None] + np.arange(int(buffer) + 1)[None, :]).ravel())
    return [str(np.datetime64(int(x), "M")) for x in allm]


class CoinCtx:
    """Everything of one coin the outcome stage needs: the spot series with successors, the index series, the
    daily lineage, eligibility tables, the tick table."""

    def __init__(self, world: World, coin: str, members: np.ndarray, q1_members: np.ndarray, need_index: bool,
                 index_months=None, need_perp: bool = False, perp_months=None):
        self.world, self.coin = world, coin
        self.spot, self.own_n, self.frame = build_spot(world, coin)
        self.own_seg = np.array([c == coin for c in self.spot.seg.coin], bool)
        self.members = members
        self.q1 = q1_members
        if need_index and index_months is None and not world.injected:
            index_months = index_months_for(members, q1_members)      # coding choice 27 (disk: not the whole history)
        self.idx_months = None if index_months is None else {_month_int(m) for m in index_months}
        self.idx = build_index(world, coin, self.spot, index_months, "index") if need_index else None
        self.perp = build_index(world, coin, self.spot, perp_months, "perp") if need_perp else None
        self._daily = None
        self._elig = {}
        self._chains = {}

    def daily(self):
        if self._daily is None:
            self._daily = build_daily(self.world, self.spot)
        return self._daily

    def ser(self, route: int) -> Ser | None:
        return self.spot if route == RT_SPOT else self.idx

    def elig(self, route: int, which: str = "prog") -> Elig | None:
        key = (route, which)
        if key not in self._elig:
            ser = self.ser(route)
            if ser is None:
                self._elig[key] = None
            else:
                self._elig[key] = Elig(ser, self.own_seg, self.members if which == "prog" else self.q1)
        return self._elig[key]

    def chain(self, s0: int) -> list:
        if s0 not in self._chains:
            out = [int(s0)]
            nx = self.spot.seg.nxt
            while nx[out[-1]] >= 0 and len(out) < 64:
                out.append(int(nx[out[-1]]))
            self._chains[s0] = out
        return self._chains[s0]

    def tick_at(self, tm: np.ndarray) -> np.ndarray:
        tt, tk = self.world.tick_table(self.coin)
        if not len(tt):
            return np.full(len(tm), np.nan)
        k = np.clip(np.searchsorted(tt, tm, side="right") - 1, 0, len(tt) - 1)
        return tk[k]

    def daily_value(self, s0: int, day: int):
        """(VWAP of `day` per unit of segment s0's asset, delisted?, the 4 §4.1 values) along the chain from s0;
        (NaN, False, NaNs) when the data end first."""
        D = self.daily()
        seg = self.spot.seg
        ch = self.chain(s0)
        i = int(np.searchsorted(D["day"], day))
        if i < len(D["day"]) and D["day"][i] == day and int(D["sidx"][i]) in ch:
            s = int(D["sidx"][i])
            return float(D["vwap"][i]) * seg.U[s] / seg.U[s0], False, np.full(4, np.nan)
        last = ch[-1]
        if seg.term[last] == 1 and seg.t1[last] <= (day + 1) * DAY_M:
            return np.nan, True, seg.val[last] * seg.U[last] / seg.U[s0]
        return np.nan, False, np.full(4, np.nan)


def _route_entry_cost(rule: str, o_e: np.ndarray) -> np.ndarray:
    """Entry price of a market buy at an open on the rule's route (before the spot route's buy cost): spot the open;
    F3 the ask, open x (1 + spread) (s within 24 h of the entry in the crash-spread rows); F4 the open (its C-EX buy
    cost is applied as c_b)."""
    rt = _rule_route(rule)
    if rt == RT_IDX3:
        s = RULE_S.get(rule, 0.01)
        return o_e * (1 + (s if s >= 0.02 else F3_SPREAD))
    return o_e


def _cost_list(route: int):
    return list(COSTS) if route == RT_SPOT else (["RH"] if route == RT_IDX3 else ["C-EX"])


def _ret_cost(route, rule, entry, ex, ser, entry_seg, cost):
    return _returns(route, rule, entry, ex, ser, entry_seg, cost if route == RT_SPOT else "C-RH")


def simulate_twins(cc: CoinCtx, rule: str, spec: ExitSpec, bars: np.ndarray, ratio: np.ndarray) -> dict:
    """Twin exits on one coin: entry at the open of `bars` on the rule's route, the fill's relative target
    (ratio = target / L; inf for holds), the same clock (rule M or bot), route and costs (§10.1). Returns per-twin
    entry, exit kind / time and returns per cost scenario."""
    route = _rule_route(rule)
    ser = cc.ser(route)
    te = ser.t[bars]
    o_e = ser.o[bars]
    tau = cc.tick_at(te) if route == RT_SPOT else np.zeros(len(bars))
    entry = _route_entry_cost(rule, o_e)
    T = entry * ratio                       # the fill's relative target on the twin's entry price (coding choice 11)
    jobs = _jobs_for(spec, rule, te, T, tau, ser.sidx[bars])
    ex = run_exits(ser, route, jobs)
    out = {"te": te, "o_e": o_e, "kind": ex["kind"], "t": ex["t"], "px": ex["px"], "idx": ex["idx"],
           "raw": ex["raw"], "tau": tau, "T": T, "g": jobs[1], "S": jobs[2]}
    for c in _cost_list(route):
        out["r:" + c] = _ret_cost(route, rule, entry, ex, ser, ser.sidx[bars], c)["r"]
    return out


def twin_recovery(cc: CoinCtx, route: int, bars: np.ndarray, r_up1: np.ndarray, r_up2: np.ndarray) -> dict:
    """D12 for twins: first minutes at or above entry x R/L and entry x P0/L, and at or below 0.9 x entry, from the
    entry minute on (bars te .. te + 30 d - 1)."""
    ser = cc.ser(route)
    te = ser.t[bars]
    o_e = ser.o[bars]
    conv = 1.0 / (1 - F3_SPREAD) if route == RT_IDX3 else 1.0
    pe = o_e * (1 + F3_SPREAD) if route == RT_IDX3 else o_e
    return _first_hits(ser, ser.sidx[bars], bars, te - 1, pe * r_up1 * conv, pe * r_up2 * conv, pe * DOWN_FRAC)


def _first_hits(ser: Ser, seg0, a, ref, up1, up2, dn) -> dict:
    n = len(a)
    o = {k: np.empty(n, np.int64) for k in ("up1", "up2", "dn", "end", "term")}
    tend = np.asarray(ref, np.int64) + REC_H_M[-1] + 1
    if n:
        s = ser.seg
        _k_first_hits(ser.t, ser.hl, ser.mx1, ser.mx2, ser.ll, ser.mn1, ser.mn2, ser.lo, ser.hi, s.U, s.nxt, s.term,
                      s.t1, np.asarray(seg0, np.int64), np.asarray(a, np.int64), tend, np.asarray(up1, float),
                      np.asarray(up2, float), np.asarray(dn, float), o["up1"], o["up2"], o["dn"], o["end"],
                      o["term"])
    o["ref"] = np.asarray(ref, np.int64)
    return o


def _rec_flags(h: dict, prefix: str) -> dict:
    """Per-horizon flags (1 / 0 / NaN when the data ended before the horizon) from first-hit minutes."""
    out = {}
    ref = h["ref"]
    for lab, hm in zip(REC_LABELS, REC_H_M):
        obs = ~((h["term"] == 2) & (h["end"] <= ref + hm))
        for k, nm in (("up1", "R"), ("up2", "P0"), ("dn", "dn10")):
            hit = (h[k] >= 0) & (h[k] - ref <= hm)
            out[f"{prefix}{nm}_{lab}"] = np.where(obs, hit.astype(float), np.nan)
    first = (h["dn"] >= 0) & ((h["up1"] < 0) | (h["dn"] < h["up1"]))
    obs30 = ~((h["term"] == 2) & (h["end"] <= ref + REC_H_M[-1]))
    out[f"{prefix}dn10_first"] = np.where(obs30, first.astype(float), np.nan)
    return out


def lowest(ser: Ser, seg0, a, tend) -> dict:
    n = len(a)
    o = {"min": np.empty(n), "term": np.empty(n, np.int64), "val": np.empty(n)}
    if n:
        s = ser.seg
        _k_lowest(ser.t, ser.ll, ser.mn1, ser.mn2, ser.lo, ser.hi, s.U, s.nxt, s.term, s.val, s.t1,
                  np.asarray(seg0, np.int64), np.asarray(a, np.int64), np.asarray(tend, np.int64), o["min"],
                  o["term"], o["val"])
    return o


def tail_fields(cc: CoinCtx, seg0, a, ref, entry, day0) -> dict:
    """T1 / D-H5 per position: the lowest price within 30 / 90 / 365 days relative to the entry (a delisting counts
    at its §4.1 value), the delisted flags, and the knife flag (the 365th day's VWAP <= 0.5 x entry; §4.1 values and
    their haircut variants after a delisting)."""
    out = {}
    entry = np.asarray(entry, float)
    for d in LOWEST_D:
        lw = lowest(cc.spot, seg0, a, np.asarray(ref, np.int64) + d * DAY_M + 1)
        m = np.where(lw["term"] == 1, np.fmin(lw["min"], lw["val"]), lw["min"])
        out[f"low{d}"] = np.where(lw["term"] == 2, np.nan, m / entry)
        out[f"delisted{d}"] = np.where(lw["term"] == 2, np.nan, (lw["term"] == 1).astype(float))
    kn = {k: np.full(len(a), np.nan) for k in ("knife", "knife_dl_last", "knife_dl0", "knife_dl100")}
    for i in range(len(a)):
        v, dl, vals = cc.daily_value(int(seg0[i]), int(day0[i]) + 365)
        if np.isfinite(v):
            for k in kn:
                kn[k][i] = float(v <= KNIFE_FRAC * entry[i])
        elif dl:
            for k, j in (("knife", 0), ("knife_dl_last", 1), ("knife_dl0", 2), ("knife_dl100", 3)):
                kn[k][i] = float(vals[j] <= KNIFE_FRAC * entry[i])
    out.update(kn)
    return out


# ============================================================================ per-coin outcomes
def _hourly_mu(cc: CoinCtx):
    """Hourly close-to-close simple returns of the coin's own spot bars (calendar hours, closes carried over hours
    without trading, NaN across a segment change; bb_stats.returns_from_hours' convention), as (hour minutes,
    returns) for the leave-out drift (§10.1)."""
    sp = cc.spot
    own = cc.own_seg[sp.sidx] & sp.live
    t = sp.t[own]
    if not len(t):
        return np.zeros(0, np.int64), np.zeros(0)
    c = sp.c[own]
    sg = sp.sidx[own]
    hr = t // 60
    last = np.r_[hr[1:] != hr[:-1], True]
    hh, hc, hs = hr[last], c[last], sg[last]
    grid = np.arange(hh[0], hh[-1] + 1)
    pos = np.searchsorted(hh, grid, side="right") - 1
    cg, sgg = hc[pos], hs[pos]
    r = np.full(len(grid), np.nan)
    r[1:] = cg[1:] / cg[:-1] - 1
    r[1:][sgg[1:] != sgg[:-1]] = np.nan
    return grid * 60, r


def _leave_out_mu(hours, rets, tau, excl_days=EXCL_DAYS):
    ok = np.isfinite(rets)
    h, r = hours[ok], rets[ok]
    cs = np.r_[0.0, np.cumsum(r)]
    a = np.searchsorted(h, tau - excl_days * DAY_M, side="left")
    b = np.searchsorted(h, tau + excl_days * DAY_M, side="right")
    n = len(r) - (b - a)
    return (cs[-1] - (cs[b] - cs[a])) / n if n > 0 else np.nan


def _alert_buys(cc: CoinCtx, rule: str, s0, m, A, L) -> dict:
    """B-ALERT (§10.1): a market buy at the open of the first live minute at or after A on the fill's route (spot:
    trades > 0; index: updates >= 30, outside Robinhood outages) along the chain; a_f = paid / bid paid - 1: spot and
    F4 open / L - 1 (equal buy costs cancel), F3 open x (1 + spread) / L - 1 (spread s within 24 h of the fill in
    the crash-spread rows, else 0.95%)."""
    route = _rule_route(rule)
    ser = cc.ser(route)
    n = len(A)
    jobs = (np.asarray(s0, np.int64), np.asarray(A, np.int64), np.asarray(A, np.int64), np.full(n, np.inf),
            np.full(n, np.inf), np.full(n, F3_SPREAD), np.zeros(n, np.int64))
    ex = run_exits(ser, RT_SPOT, jobs)
    px = np.where(ex["kind"] == EK_STOP, ex["px"], np.nan)
    if route == RT_IDX3:
        s = RULE_S.get(rule, 0.01)
        spr = np.where((s >= 0.02) & (ex["t"] < np.asarray(m, np.int64) + CRASH_SPREAD_H * 60), s, F3_SPREAD)
        paid = px * (1 + spr)
    else:
        paid = px
    return {"a": paid / np.asarray(L, float) - 1, "t": np.where(ex["kind"] == EK_STOP, ex["t"], -1),
            "idx": ex["idx"], "raw": ex["raw"], "kind": ex["kind"], "A": np.asarray(A, np.int64)}


def _ml_fields(cc: CoinCtx, s0, m, L) -> dict:
    """B-ML (§10.1): the next day's open after the first green MoneyLine close at or after the fill (within 365
    days; 'no re-entry' otherwise): a_ML = open / L - 1; X-ML: the next day's open after the first red close that
    follows a green close (the last close before the fill counts, coding choice 8); D-ML: a red close within 1 and 7
    days of the fill."""
    D = cc.daily()
    day, sidx, opn, green = D["day"], D["sidx"], D["open"], D["green"]
    seg = cc.spot.seg
    n = len(m)
    out = {k: np.full(n, np.nan) for k in ("ml_a", "ml_days", "ml_fill", "red1d", "red7d", "xml_day")}
    for i in range(n):
        ch = set(cc.chain(int(s0[i])))
        U0 = seg.U[int(s0[i])]
        dfill = int(m[i]) // DAY_M
        a = int(np.searchsorted(day, dfill - 1))
        rows = [j for j in range(a, len(day)) if int(sidx[j]) in ch]
        # state at the fill day's close and red closes within 1 / 7 days (close of day d at (d + 1) x 1440)
        red1 = red7 = 0.0
        seen_green = False
        ml_entry = None
        xml = None
        for j in rows:
            d = int(day[j])
            if d < dfill:
                seen_green = green[j] == 1
                continue
            if d == dfill:
                out["ml_fill"][i] = float(green[j])
            close_t = (d + 1) * DAY_M
            if green[j] == 0 and close_t <= m[i] + DAY_M:
                red1 = 1.0
            if green[j] == 0 and close_t <= m[i] + 7 * DAY_M:
                red7 = 1.0
            if ml_entry is None and green[j] == 1 and d <= dfill + ML_REENTRY_D:
                ml_entry = j
            if xml is None:
                if green[j] == 1:
                    seen_green = True
                elif green[j] == 0 and seen_green:
                    xml = d
            if xml is not None and (ml_entry is not None or d > dfill + ML_REENTRY_D) and d > dfill + 7:
                break
        out["red1d"][i] = red1 if (dfill + 1) * DAY_M <= cc.world.end_min + 1 else np.nan
        out["red7d"][i] = red7 if m[i] + 7 * DAY_M <= cc.world.end_min else np.nan
        if ml_entry is not None:
            nx = [j for j in rows if day[j] > day[ml_entry]]
            if nx:
                j = nx[0]
                out["ml_a"][i] = opn[j] * seg.U[int(sidx[j])] / U0 / L[i] - 1
                out["ml_days"][i] = float(day[ml_entry] - dfill)
        if xml is not None:
            out["xml_day"][i] = float(xml)
    return out


def coin_outcomes(world: World, cc: CoinCtx, F: pd.DataFrame, plan: dict, cfg: dict, pool_needs: list,
                  audit: list, twin_log: list | None = None) -> tuple:
    """Outcomes of one coin's fills (§8, §9, §10.1, §10.4): per rule and exit, the fill's net return per cost
    scenario, its twins' mean (own twins here; pooled twins are queued in pool_needs), B-ALERT, B-ML, X-ML, X-OWN,
    B-POST, D12 recovery, T1 / knife fields and the leave-out drift. Returns (outcome rows, benchmark rows)."""
    end_min = world.end_min
    out_rows, bench_rows = [], []
    mu_h = _hourly_mu(cc) if cfg["drift"] else None
    for rule, specs in plan.items():
        col = "i_" + rule
        if col not in F:
            continue
        Fr = F[F[col].to_numpy() >= 0]
        if not len(Fr):
            continue
        route = _rule_route(rule)
        ser = cc.ser(route)
        fid = Fr.fill_id.to_numpy(np.int64)
        m = Fr["t_" + rule].to_numpy(np.int64)
        s0 = Fr.sidx.to_numpy(np.int64)
        L = Fr.L.to_numpy(float)
        P0 = Fr.P0.to_numpy(float)
        sig = Fr.sigma30.to_numpy(float)
        tick = Fr.tick.to_numpy(float)
        tstr = Fr.tick_str.astype(str).to_numpy()
        H24 = Fr.H24.to_numpy(float) if "H24" in Fr else np.full(len(Fr), np.nan)
        n = len(Fr)
        if ser is None:
            for c in _cost_list(route):
                for sp in specs:
                    for i in range(n):
                        out_rows.append(dict(fill_id=int(fid[i]), coin=cc.coin, rule=rule, exit=sp.name, lat=sp.lat,
                                             cost=c, r=np.nan, note="no index series"))
            continue
        U = [_twin_u(f) for f in fid]
        u_tw = np.array([x[0] for x in U])
        u_post = np.array([x[1] for x in U])
        el = cc.elig(route, "prog")
        R_target = _targets(FLIP, L, P0, sig, tstr, H24)
        # ---- exits and twins per spec
        for sp in specs:
            T = _targets(sp, L, P0, sig, tstr, H24) if sp.kind == "flip" else np.full(n, np.inf)
            up = _next_tick(T, tstr) if (route == RT_SPOT and sp.kind == "flip") else None
            jobs = _jobs_for(sp, rule, m, T, tick if route == RT_SPOT else np.zeros(n), s0, up=up)
            ex = run_exits(ser, route, jobs)
            hz = _horizon(sp, m)
            complete = hz <= end_min
            ratio = np.where(np.isfinite(T), T / L, np.inf)
            cut = _cutoff(lambda te, sp=sp: _horizon(sp, te), end_min, sp.stop_m + 2 * DAY_M)
            variants = [("", EXCL_DAYS, False)]
            if rule == "F1" and sp.name == "FLIP" and cfg["twin_sens"]:
                variants += [("_x30", EXCL_DAYS_SENS, False), ("_pool", EXCL_DAYS, True)]
            tw = {}
            for suf, xd, force_pool in variants:
                bars, owner = [], []
                pooled = np.zeros(n, bool)
                for i in range(n):
                    i0, i1, nL, nR, days = el.window(cut, int(m[i]), xd)
                    if force_pool or days < POOL_MIN_DAYS or nL + nR == 0:
                        pooled[i] = True
                        pool_needs.append(dict(fill_id=int(fid[i]), coin=cc.coin, rule=rule, spec=sp.name, suf=suf,
                                               tau=int(m[i]), excl=xd, cut=int(cut), ratio=float(ratio[i]),
                                               u=u_tw[i]))
                        continue
                    bars.append(el.pick(u_tw[i], i0, i1, nL, nR))
                    owner.append(np.full(R_TWINS, i))
                res = None
                if bars:
                    bars = np.concatenate(bars)
                    owner = np.concatenate(owner)
                    res = simulate_twins(cc, rule, sp, bars, ratio[owner])
                    if twin_log is not None:
                        twin_log.append(dict(res, coin=cc.coin, rule=rule, spec=sp.name, suf=suf, pooled=False,
                                             fill_id=fid[owner], tau_fill=m[owner], bar=bars))
                    if cfg["audit"] != "off":
                        audit.extend(audit_exits(cc, rule, sp, ser, res["te"], ser.sidx[bars], res, twin=True,
                                                 label=f"twin {rule} {sp.name}{suf}"))
                tw[suf] = (res, owner if res is not None else None, pooled)
            if cfg["audit"] != "off":
                fres = dict(kind=ex["kind"], t=ex["t"], px=ex["px"], idx=ex["idx"], raw=ex["raw"], T=T,
                            tau=tick if route == RT_SPOT else np.zeros(n), g=jobs[1], S=jobs[2], te=m)
                audit.extend(audit_exits(cc, rule, sp, ser, m, s0, fres, twin=False, label=f"fill {rule} {sp.name}"))
            for c in _cost_list(route):
                rr = _ret_cost(route, rule, L, ex, ser, s0, c)
                base = dict(rule=rule, exit=sp.name, lat=sp.lat, cost=c)
                tmeans = {}
                for suf, (res, owner, pooled) in tw.items():
                    mean = np.full(n, np.nan)
                    cnt = np.zeros(n)
                    if res is not None:
                        v = res["r:" + c]
                        ok = np.isfinite(v)
                        cnt = np.bincount(owner[ok], minlength=n).astype(float)
                        sm = np.bincount(owner[ok], weights=v[ok], minlength=n)
                        mean = np.where(cnt > 0, sm / np.maximum(cnt, 1), np.nan)
                    tmeans[suf] = (mean, cnt, pooled)
                mu = None
                if mu_h is not None and rule == "F1" and sp.name == "FLIP" and c == "C-RH":
                    mu = np.array([_leave_out_mu(mu_h[0], mu_h[1], int(x)) for x in m])
                for i in range(n):
                    row = dict(base, fill_id=int(fid[i]), coin=cc.coin, r=float(rr["r"][i]),
                               r_dl_last=float(rr["r_dl_last"][i]), r_dl0=float(rr["r_dl0"][i]),
                               r_dl100=float(rr["r_dl100"][i]), exit_kind=EK_NAMES[ex["kind"][i]],
                               exit_t=int(ex["t"][i]), exit_px=float(ex["px"][i]), target=float(T[i]),
                               horizon_t=int(hz[i]), complete=bool(complete[i]),
                               hold_h=(float(ex["t"][i] - m[i]) / 60.0) if ex["t"][i] >= 0 else np.nan)
                    for suf, (mean, cnt, pooled) in tmeans.items():
                        row["twin_mean" + suf] = float(mean[i])
                        row["twin_n" + suf] = int(cnt[i])
                        row["twin_pooled" + suf] = bool(pooled[i])
                        row["delta" + suf] = float(rr["r"][i] - mean[i]) if np.isfinite(mean[i]) else np.nan
                    if mu is not None:
                        row["drift_mu"] = float(mu[i])
                        row["delta_drift"] = float(rr["r"][i] - mu[i] * row["hold_h"]) \
                            if np.isfinite(row["hold_h"]) else np.nan
                    out_rows.append(row)
        # ---- per-fill benchmarks of the rule
        bench = {"fill_id": fid, "rule": np.full(n, rule), "coin": np.full(n, cc.coin)}
        A = {"M": rule_m(m)}
        for h in ALERT_DELAYS_H:
            A[f"{h}h"] = m + h * 60
        for k, a_t in A.items():
            al = _alert_buys(cc, rule, s0, m, a_t, L)
            bench[f"alert_{k}"] = al["a"]
            bench[f"alert_t_{k}"] = al["t"]
            bench[f"alert_px_{k}"] = L * (1 + al["a"])
            if cfg["audit"] != "off":
                audit.extend(audit_alerts(cc, rule, ser, s0, m, al, label=f"alert {rule} {k}"))
        if rule in ("F1", "F3_1"):
            # D12 recovery, fills and twins
            conv = 1.0 / (1 - F3_SPREAD) if route == RT_IDX3 else 1.0
            # the fill's bar in THIS pass's series (pass 1 read only the candidate months of the index)
            ifill = np.searchsorted(ser.t, m).astype(np.int64)
            assert np.all(ser.t[np.minimum(ifill, ser.n - 1)] == m), "fill minute missing from the series"
            h = _first_hits(ser, s0, ifill + 1, m, R_target * conv, P0 * conv, L * DOWN_FRAC)
            bench.update(_rec_flags(h, "rec_"))
            cut_r = end_min - REC_H_M[-1]
            bars, owner = [], []
            for i in range(n):
                i0, i1, nL, nR, days = el.window(cut_r, int(m[i]), EXCL_DAYS)
                if days < POOL_MIN_DAYS or nL + nR == 0:
                    pool_needs.append(dict(fill_id=int(fid[i]), coin=cc.coin, rule=rule, spec="REC", suf="",
                                           tau=int(m[i]), excl=EXCL_DAYS, cut=int(cut_r),
                                           ratio=float(R_target[i] / L[i]), ratio2=float(P0[i] / L[i]), u=u_tw[i]))
                    continue
                bars.append(el.pick(u_tw[i], i0, i1, nL, nR))
                owner.append(np.full(R_TWINS, i))
            if bars:
                bars = np.concatenate(bars)
                owner = np.concatenate(owner)
                th = twin_recovery(cc, route, bars, (R_target / L)[owner], (P0 / L)[owner])
                fl = _rec_flags(th, "")
                for k, v in fl.items():
                    ok = np.isfinite(v)
                    cnt = np.bincount(owner[ok], minlength=n)
                    sm = np.bincount(owner[ok], weights=v[ok], minlength=n)
                    bench["twin_rec_" + k] = np.where(cnt > 0, sm / np.maximum(cnt, 1), np.nan)
            ml = _ml_fields(cc, s0, m, L)
            bench["ml_a"] = ml["ml_a"]
            bench["ml_days"] = ml["ml_days"]
            if rule == "F1":
                bench["ml_fill"] = ml["ml_fill"]
                bench["red_close_1d"] = ml["red1d"]
                bench["red_close_7d"] = ml["red7d"]
                # X-ML: sell at the next day's open after the first red close following a green close
                xd = ml["xml_day"]
                okx = np.isfinite(xd)
                S = np.where(okx, (np.nan_to_num(xd) + 1) * DAY_M, end_min + 10).astype(np.int64)
                jobs = (s0, S, S, np.full(n, np.inf), np.full(n, np.inf), np.full(n, F3_SPREAD), np.zeros(n, np.int64))
                exm = run_exits(ser, RT_SPOT, jobs)
                for c in ("C-RH", "C-0"):
                    rr = _returns(RT_SPOT, rule, L, exm, ser, s0, c)["r"]
                    bench[f"xml_r_{c}"] = np.where(okx, rr, np.nan)
                bench["xml_t"] = np.where(okx, exm["t"], -1)
                bench["xml_px"] = np.where(okx, exm["px"], np.nan)
                # X-OWN: hold to the data end, marked at the last close (no sell cost)
                own = np.full(n, np.nan)
                for i in range(n):
                    ch = cc.chain(int(s0[i]))
                    last = ch[-1]
                    seg = cc.spot.seg
                    if seg.term[last] == 1:
                        v = seg.val[last, 0] * seg.U[last] / seg.U[int(s0[i])]
                    else:
                        k = ser.hi[last] - 1
                        while k >= ser.lo[last] and not ser.live[k]:
                            k -= 1
                        v = ser.c[k] * seg.U[last] / seg.U[int(s0[i])] if k >= ser.lo[last] else np.nan
                    own[i] = v / (L[i] * (1 + C_RH)) - 1
                bench["own_r_C-RH"] = own
                # T1 / D-H5 tail fields, fills and twins
                tf = tail_fields(cc, s0, ifill + 1, m, L, m // DAY_M)
                for k, v in tf.items():
                    bench[k] = v
                cut_t = end_min - 365 * DAY_M
                bars, owner = [], []
                for i in range(n):
                    i0, i1, nL, nR, days = el.window(cut_t, int(m[i]), EXCL_DAYS)
                    if days < POOL_MIN_DAYS or nL + nR == 0:
                        pool_needs.append(dict(fill_id=int(fid[i]), coin=cc.coin, rule=rule, spec="TAIL", suf="",
                                               tau=int(m[i]), excl=EXCL_DAYS, cut=int(cut_t), ratio=1.0, u=u_tw[i]))
                        continue
                    bars.append(el.pick(u_tw[i], i0, i1, nL, nR))
                    owner.append(np.full(R_TWINS, i))
                if bars:
                    bars = np.concatenate(bars)
                    owner = np.concatenate(owner)
                    te = ser.t[bars]
                    tt = tail_fields(cc, ser.sidx[bars], bars, te - 1, ser.o[bars], te // DAY_M)
                    for k, v in tt.items():
                        ok = np.isfinite(v)
                        cnt = np.bincount(owner[ok], minlength=n)
                        sm = np.bincount(owner[ok], weights=v[ok], minlength=n)
                        bench["twin_" + k] = np.where(cnt > 0, sm / np.maximum(cnt, 1), np.nan)
            # B-POST: same coin, entries in (fill + 1 d, fill + 30 d], held 90 days
            hold90 = EXIT_SPECS["HOLD90"]
            cut_p = _cutoff(lambda te: _horizon(hold90, te), end_min, hold90.stop_m + 2 * DAY_M)
            bars, owner = [], []
            own_live = np.flatnonzero(ser.live & cc.own_seg[np.clip(ser.sidx, 0, None)])
            tl = ser.t[own_live]
            for i in range(n):
                a = np.searchsorted(tl, m[i] + POST_FROM_D * DAY_M, side="right")
                b = np.searchsorted(tl, min(m[i] + POST_TO_D * DAY_M, cut_p), side="right")
                if b <= a:
                    continue
                k = np.minimum((u_post[i] * (b - a)).astype(np.int64), b - a - 1)
                bars.append(own_live[a + k])
                owner.append(np.full(R_TWINS, i))
            for c in _cost_list(route):
                bench[f"post_mean_{c}"] = np.full(n, np.nan)
            if bars:
                bars = np.concatenate(bars)
                owner = np.concatenate(owner)
                res = simulate_twins(cc, rule, hold90, bars, np.full(len(bars), np.inf))
                for c in _cost_list(route):
                    v = res["r:" + c]
                    ok = np.isfinite(v)
                    cnt = np.bincount(owner[ok], minlength=n)
                    sm = np.bincount(owner[ok], weights=v[ok], minlength=n)
                    bench[f"post_mean_{c}"] = np.where(cnt > 0, sm / np.maximum(cnt, 1), np.nan)
                bench["post_n"] = np.bincount(owner, minlength=n)
        bench_rows.append(pd.DataFrame(bench))
    return out_rows, bench_rows


# ============================================================================ K5 fill audit (§10.5), separate code
def _outage_bounds_pd():
    """Robinhood outage windows written separately from rh_outage_windows (pandas New York calendar days)."""
    out = []
    for d in RH_OUTAGE_DATES:
        a = pd.Timestamp(d, tz=NY) - pd.Timedelta("1h")
        b = pd.Timestamp(d, tz=NY) + pd.Timedelta("1D") + pd.Timedelta("1h")
        out.append((a.tz_convert("UTC").value // MIN_NS, b.tz_convert("UTC").value // MIN_NS))
    return out


_OUT_PD = _outage_bounds_pd()


def _outage_pd(tm: np.ndarray) -> np.ndarray:
    tm = np.asarray(tm, np.int64)
    out = np.zeros(len(tm), bool)
    for a, b in _OUT_PD:
        out |= (tm >= a) & (tm < b)
    return out


def _live_pd(ser: Ser, idx: np.ndarray) -> np.ndarray:
    """Liveness recomputed from the raw counts: spot / perpetual trades > 0; index updates >= 30 outside outages."""
    idx = np.asarray(idx, np.int64)
    if ser.kind == "spot":
        return ser.trades[idx] > 0
    if ser.kind == "perp":
        return ser.upd[idx] > 0
    return (ser.upd[idx] >= IDX_MIN_UPDATES) & ~_outage_pd(ser.t[idx])


def _clock_pd(spec: ExitSpec, te: np.ndarray):
    """(go-live, stop) minutes recomputed with pandas time zones (rule M, §8)."""
    te = np.asarray(te, np.int64)
    if not len(te):
        return te, te
    t = pd.DatetimeIndex(_mts(te))
    if spec.kind == "flip":
        g = te + 1 if spec.lat == "bot" else _tmin(_rule_m_pd(t))
        S = _tmin(_rule_m_pd(t + pd.Timedelta(minutes=spec.stop_m)))
    elif spec.kind == "hold":
        S = _tmin(_rule_m_pd(t + pd.Timedelta(minutes=spec.stop_m)))
        g = S
    else:
        S = _tmin(_rule_m_pd(t)) + spec.stop_m
        g = S
    return np.asarray(g, np.int64), np.asarray(S, np.int64)


def _viol(label, coin, what, i, detail=""):
    return dict(type="violation", label=label, coin=coin, check=what, row=int(i), detail=str(detail))


def _audit_up(T: float, tau: float, exact: bool) -> float:
    """K5's spot trade-through price ('high >= limit + tau'), written separately from _next_tick: a fill's target (on
    its tick grid) plus one tick, added in exact decimals of the two prices' shortest strings; a twin's unrounded
    target + tau as a float sum (coding choice 11); inf for a missing target."""
    T, tau = float(T), float(tau)
    if not math.isfinite(T):
        return math.inf
    if not exact:
        return T + tau
    from decimal import Decimal
    return float(Decimal(repr(T)) + Decimal(repr(tau)))


def audit_fills(ser: Ser | None, b: pd.DataFrame, rule: str, ifill: np.ndarray, coin: str) -> list:
    """K5 for bids: a resting bid fills at L in its first live minute after its live time whose low <= L - tau (F1,
    F5), <= L (F2), index low <= L / (1 + s) (F3), index high <= L / (1 + s) (F3d), index low <= L (F4); spot fills
    stay in the bid's segment; a fill price above the minute's high is a gap-through fill (listed)."""
    out = []
    sel = np.flatnonzero(ifill >= 0)
    if ser is None or not len(sel):
        return [dict(type="count", label=f"bid {rule}", coin=coin, n=0, gaps=0)]
    s = RULE_S.get(rule, 0.0)
    L = b.L.to_numpy(float)
    Lt = b.L_tau.to_numpy(float)
    lf = b.live_from.to_numpy(np.int64)
    le = b.life_end.to_numpy(np.int64)
    sx = b.sidx.to_numpy(np.int64)
    gaps = 0
    for j in sel:
        i = int(ifill[j])
        t = int(ser.t[i])
        if not (lf[j] <= t < le[j]):
            out.append(_viol(f"bid {rule}", coin, "outside life", j, t))
        if not _live_pd(ser, [i])[0]:
            out.append(_viol(f"bid {rule}", coin, "not live", j, t))
        if ser.kind == "spot" and ser.sidx[i] != sx[j]:
            out.append(_viol(f"bid {rule}", coin, "other segment", j, t))
        if ser.kind != "spot" and t >= ser.seg.t1[sx[j]]:
            out.append(_viol(f"bid {rule}", coin, "after the segment's end of trading", j, t))
        lo, hi = ser.l[i], ser.h[i]
        if rule in ("F1", "F5"):
            ok, thr, v = lo <= Lt[j], Lt[j], ser.l
        elif rule == "F2":
            ok, thr, v = lo <= L[j], L[j], ser.l
        elif rule == "F4":
            ok, thr, v = lo <= L[j], L[j], ser.l
        elif rule.startswith("F3d"):
            ok, thr, v = hi <= L[j] / (1 + s), L[j] / (1 + s), ser.h
        else:
            ok, thr, v = lo <= L[j] / (1 + s), L[j] / (1 + s), ser.l
        if not ok:
            out.append(_viol(f"bid {rule}", coin, "trigger", j, f"{lo} {hi} {thr}"))
        # first-ness: no earlier live minute of the life (in the bid's segment for spot) met the trigger
        a = int(np.searchsorted(ser.t, lf[j]))
        prev = np.arange(a, i)
        if len(prev):
            lv = _live_pd(ser, prev)
            if ser.kind == "spot":
                lv &= ser.sidx[prev] == sx[j]
            if np.any(lv & (v[prev] <= thr)):
                out.append(_viol(f"bid {rule}", coin, "not the first trigger", j, t))
        if ser.kind in ("spot", "perp") and L[j] > hi:
            gaps += 1
            out.append(dict(type="gap", label=f"bid {rule}", coin=coin, row=int(j), t=t, price=float(L[j]),
                            low=float(lo), high=float(hi)))
    out.append(dict(type="count", label=f"bid {rule}", coin=coin, n=len(sel), gaps=gaps))
    return out


def _first_live_after(ser: Ser, seg_chain: list, tmin: int) -> int:
    """First live bar at or after minute tmin in the given chain of segments (a plain scan in growing chunks, with
    liveness recomputed from the raw counts), -1 if none."""
    for s in seg_chain:
        a = max(int(np.searchsorted(ser.t, tmin)), int(ser.lo[s]))
        b = int(ser.hi[s])
        step = 64
        while a < b:
            e = min(b, a + step)
            k = np.arange(a, e)
            lv = np.flatnonzero(_live_pd(ser, k))
            if len(lv):
                return int(k[lv[0]])
            a = e
            step *= 4
    return -1


def _chain_of(ser: Ser, s0: int) -> list:
    out = [int(s0)]
    while ser.seg.nxt[out[-1]] >= 0 and len(out) < 64:
        out.append(int(ser.seg.nxt[out[-1]]))
    return out


def audit_exits(cc: CoinCtx, rule: str, spec: ExitSpec, ser: Ser, te, seg0, res: dict, twin: bool,
                label: str, sample: int = 400) -> list:
    """K5 for exits (fills' and twins'): the clock (rule M or bot) recomputed separately; a resting sell fills at its
    limit in a live minute after its live time and before its stop, with high >= limit + tau (spot), index high >=
    limit / (1 - spread) (F3) or >= limit (F4) (a minute that gapped above the limit is listed); a marketable sell
    or a time stop at the open of the first live minute at or after its time; a delisting at the chain's end of
    trading. First-hit checks (no earlier live minute met the trigger) on a sample of `sample` positions."""
    out = []
    n = len(te)
    if not n:
        return out
    route = _rule_route(rule)
    g_pd, S_pd = _clock_pd(spec, te)
    if np.any(g_pd != res["g"]) or np.any(S_pd != res["S"]):
        bad = np.flatnonzero((g_pd != res["g"]) | (S_pd != res["S"]))
        for i in bad[:20]:
            out.append(_viol(label, cc.coin, "clock", i, f"{res['g'][i]} vs {g_pd[i]}; {res['S'][i]} vs {S_pd[i]}"))
    seg = ser.seg
    kind = res["kind"]
    idx = res["idx"]
    s = RULE_S.get(rule, 0.0)
    crash = route == RT_IDX3 and s >= 0.02
    gaps = 0
    rng = np.random.default_rng(7)
    chk = set(rng.choice(n, min(n, sample), replace=False).tolist()) if twin else set(range(n))
    for i in range(n):
        k = int(kind[i])
        if k in (EK_TARGET, EK_MARKETABLE, EK_STOP):
            b = int(idx[i])
            t = int(ser.t[b])
            if not _live_pd(ser, [b])[0]:
                out.append(_viol(label, cc.coin, "exit in a dead minute", i, t))
            s_b = int(ser.sidx[b])
            fac = seg.U[s_b] / seg.U[int(seg0[i])]
            tol = 1.0 - CONV_REL if fac != 1.0 else 1.0       # converted targets (coding choice 25)
            spr = (s if (crash and t < te[i] + CRASH_SPREAD_H * 60) else F3_SPREAD) if route == RT_IDX3 else 0.0
            if k == EK_TARGET:
                Tr = res["T"][i] / fac
                if not (res["g"][i] <= t < res["S"][i]):
                    out.append(_viol(label, cc.coin, "target outside [live, stop)", i, t))
                if route == RT_SPOT:
                    trig = ser.h[b] >= _audit_up(res["T"][i], res["tau"][i], not twin) / fac * tol
                elif route == RT_IDX3:
                    trig = ser.h[b] >= Tr * tol / (1 - spr)
                else:
                    trig = ser.h[b] >= Tr * tol
                if not trig:
                    out.append(_viol(label, cc.coin, "target trigger", i, f"{ser.h[b]} vs {Tr}"))
                if abs(res["raw"][i] - Tr) > 1e-9 * max(1.0, abs(Tr)):
                    out.append(_viol(label, cc.coin, "target price", i, f"{res['raw'][i]} vs {Tr}"))
                if Tr < ser.l[b]:
                    gaps += 1
                    if not twin:
                        out.append(dict(type="gap", label=label, coin=cc.coin, row=int(i), t=t, price=float(Tr),
                                        low=float(ser.l[b]), high=float(ser.h[b])))
            else:
                at = res["g"][i] if k == EK_MARKETABLE else res["S"][i]
                if i in chk:
                    f = _first_live_after(ser, _chain_of(ser, int(seg0[i])), int(max(at, te[i])))
                    if f != b:
                        out.append(_viol(label, cc.coin, "not the first live minute", i, f"{b} vs {f}"))
                if res["raw"][i] != ser.o[b]:
                    out.append(_viol(label, cc.coin, "not at the open", i, t))
                if k == EK_MARKETABLE and ser.o[b] * (1 - spr) < res["T"][i] / fac * tol:
                    out.append(_viol(label, cc.coin, "marketable below target", i, t))
                if t < at:
                    out.append(_viol(label, cc.coin, "before its time", i, t))
            # first-hit: no earlier live minute from go-live met the target (sample for twins)
            if i in chk and np.isfinite(res["T"][i]) and spec.kind == "flip":
                ch = _chain_of(ser, int(seg0[i]))
                gb = _first_live_after(ser, ch, int(res["g"][i]))
                if gb >= 0 and k != EK_MARKETABLE and ser.t[gb] < res["S"][i]:
                    sg_ = int(ser.sidx[gb])
                    f2 = seg.U[sg_] / seg.U[int(seg0[i])]
                    sp2 = (s if (crash and ser.t[gb] < te[i] + CRASH_SPREAD_H * 60) else F3_SPREAD) \
                        if route == RT_IDX3 else 0.0
                    if ser.o[gb] * (1 - sp2) >= res["T"][i] / f2 * (1.0 - CONV_REL if f2 != 1.0 else 1.0):
                        out.append(_viol(label, cc.coin, "missed marketable", i, int(ser.t[gb])))
                    end = b if k in (EK_TARGET, EK_STOP) else gb
                    rngi = np.arange(gb, end)
                    if len(rngi):
                        lv = _live_pd(ser, rngi)
                        f3 = seg.U[ser.sidx[rngi]] / seg.U[int(seg0[i])]
                        tol3 = np.where(f3 != 1.0, 1.0 - CONV_REL, 1.0)
                        Tr3 = res["T"][i] / f3 * tol3
                        if route == RT_SPOT:
                            hitm = ser.h[rngi] >= _audit_up(res["T"][i], res["tau"][i], not twin) / f3 * tol3
                        elif route == RT_IDX3:
                            sp3 = np.where(crash & (ser.t[rngi] < te[i] + CRASH_SPREAD_H * 60), s, F3_SPREAD)
                            hitm = ser.h[rngi] >= Tr3 / (1 - sp3)
                        else:
                            hitm = ser.h[rngi] >= Tr3
                        inseg = np.isin(ser.sidx[rngi], ch)
                        if np.any(lv & hitm & inseg):
                            out.append(_viol(label, cc.coin, "missed earlier target", i, int(ser.t[b])))
        elif k == EK_DELIST:
            ch = _chain_of(ser, int(seg0[i]))
            last = ch[-1]
            if seg.term[last] != 1 or int(res["t"][i]) != int(seg.t1[last]):
                out.append(_viol(label, cc.coin, "delisting", i, res["t"][i]))
        elif k == EK_CENSORED:
            ch = _chain_of(ser, int(seg0[i]))
            if seg.term[ch[-1]] != 0:
                out.append(_viol(label, cc.coin, "censored without a data end", i, ""))
    out.append(dict(type="count", label=label, coin=cc.coin, n=n, gaps=gaps))
    return out


def audit_alerts(cc: CoinCtx, rule: str, ser: Ser, seg0, m, al: dict, label: str, sample: int = 200) -> list:
    """K5 for the alert buyer's market buys: at the open of the first live minute at or after the alert time."""
    out = []
    n = len(m)
    for i in range(min(n, sample)):
        if al["kind"][i] != EK_STOP:
            continue
        b = int(al["idx"][i])
        f = _first_live_after(ser, _chain_of(ser, int(seg0[i])), int(al["A"][i]))
        if f != b or al["raw"][i] != ser.o[b]:
            out.append(_viol(label, cc.coin, "alert buy", i, f"{b} vs {f}"))
    out.append(dict(type="count", label=label, coin=cc.coin, n=n, gaps=0))
    return out


# ============================================================================ pooled twins (§10.1)
def _pool_table(world: World, coin: str, route: int, q1_months, cache: dict, ctx: CoinCtx | None = None):
    """(days, eligible minutes per day) of a U-Q1 coin's twin entries on a route (U-Q1 member months)."""
    key = (coin, route)
    if key in cache:
        return cache[key]
    if ctx is None:
        ctx = CoinCtx(world, coin, q1_months, q1_months, need_index=route != RT_SPOT)
    el = ctx.elig(route, "q1")
    cache[key] = el.day_table() if el is not None else (np.zeros(0, np.int64), np.zeros(0, np.int64))
    return cache[key]


def _pool_draw(need: dict, tables: dict, route: int):
    """Pooled twin entries (coding choice 15): uniform over every U-Q1 coin's eligible minutes on whole UTC days
    that end at or before the horizon cutoff and do not touch [tau - X, tau + X]. Returns [(coin, day, rank)]."""
    cut_day = (need["cut"] - (DAY_M - 1)) // DAY_M
    x0 = (need["tau"] - need["excl"] * DAY_M) // DAY_M
    x1 = (need["tau"] + need["excl"] * DAY_M) // DAY_M
    coins, cnts, parts = [], [], []
    for (c, r), (days, cn) in tables.items():
        if r != route or not len(days):
            continue
        ok = (days <= cut_day) & ((days < x0) | (days > x1))
        if not ok.any():
            continue
        coins.append(c)
        d, k = days[ok], cn[ok]
        parts.append((d, np.cumsum(k)))
        cnts.append(int(k.sum()))
    N = int(sum(cnts))
    if N == 0:
        return []
    cum = np.cumsum(cnts)
    out = []
    for uu in need["u"]:
        r_ = min(int(uu * N), N - 1)
        ci = int(np.searchsorted(cum, r_, side="right"))
        off = r_ - (cum[ci - 1] if ci > 0 else 0)
        d, ck = parts[ci]
        di = int(np.searchsorted(ck, off, side="right"))
        rank = off - (ck[di - 1] if di > 0 else 0)
        out.append((coins[ci], int(d[di]), int(rank)))
    return out


def run_pooled(world: World, needs: list, q1: dict, cfg: dict, audit: list, tables: dict, log=None):
    """Draw and simulate every queued pooled twin; returns (exit means: DataFrame fill_id, rule, spec, suf, cost,
    mean, n; recovery / tail means: DataFrame fill_id, rule, field, mean)."""
    if not needs:
        return pd.DataFrame(), pd.DataFrame()
    t0 = time.time()
    routes = {_rule_route(nd["rule"]) for nd in needs}
    for c in sorted(q1):
        todo = [r for r in routes if (c, r) not in tables]
        if not todo or not world.has_coin(c):
            continue
        try:
            ctx = CoinCtx(world, c, q1[c], q1[c], need_index=any(r != RT_SPOT for r in todo))
            for r in todo:
                _pool_table(world, c, r, q1[c], tables, ctx)
            del ctx
        except Exception as e:                          # a coin without data contributes no minutes
            for r in todo:
                tables[(c, r)] = (np.zeros(0, np.int64), np.zeros(0, np.int64))
            if cfg["verbose"]:
                print(f"  pool table {c}: {e!r}", flush=True)
    reqs = []
    for k, nd in enumerate(needs):
        for j, (c, d, rank) in enumerate(_pool_draw(nd, tables, _rule_route(nd["rule"]))):
            reqs.append((c, k, j, d, rank))
    R = pd.DataFrame(reqs, columns=["coin", "need", "j", "day", "rank"])
    ex_rows, f_rows = [], []
    for c, g in R.groupby("coin"):
        need_idx = any(_rule_route(needs[k]["rule"]) != RT_SPOT for k in g.need.unique())
        cc = CoinCtx(world, c, q1[c], q1[c], need_index=need_idx)
        for (rule, spec, suf), gg in g.groupby([g.need.map(lambda k: needs[k]["rule"]),
                                               g.need.map(lambda k: needs[k]["spec"]),
                                               g.need.map(lambda k: needs[k]["suf"])]):
            route = _rule_route(rule)
            el = cc.elig(route, "q1")
            bars = np.array([el.rank_in_day(int(d), int(rk)) for d, rk in zip(gg.day, gg["rank"])], np.int64)
            owner = gg.need.to_numpy()
            if spec in ("REC", "TAIL"):
                ser = cc.ser(route)
                if spec == "REC":
                    r1 = np.array([needs[k]["ratio"] for k in owner])
                    r2 = np.array([needs[k]["ratio2"] for k in owner])
                    fl = _rec_flags(twin_recovery(cc, route, bars, r1, r2), "")
                    pre = "twin_rec_"
                else:
                    te = ser.t[bars]
                    fl = tail_fields(cc, ser.sidx[bars], bars, te - 1, ser.o[bars], te // DAY_M)
                    pre = "twin_"
                for fld, v in fl.items():
                    f_rows.append(pd.DataFrame({"need": owner, "field": pre + fld, "v": v}))
                continue
            sp = EXIT_SPECS[spec]
            ratio = np.array([needs[k]["ratio"] for k in owner])
            res = simulate_twins(cc, rule, sp, bars, ratio)
            if log is not None:
                log.append(dict(res, coin=c, rule=rule, spec=spec, suf=suf, pooled=True,
                                fill_id=np.array([needs[k]["fill_id"] for k in owner]),
                                tau_fill=np.array([needs[k]["tau"] for k in owner]), bar=bars))
            if cfg["audit"] != "off":
                audit.extend(audit_exits(cc, rule, sp, cc.ser(route), res["te"], cc.ser(route).sidx[bars], res,
                                         twin=True, label=f"pooled twin {rule} {spec}{suf}"))
            for cst in _cost_list(route):
                ex_rows.append(pd.DataFrame({"need": owner, "cost": cst, "v": res["r:" + cst]}))
        del cc
    out_e = pd.DataFrame()
    if ex_rows:
        E = pd.concat(ex_rows, ignore_index=True)
        E = E[np.isfinite(E.v.to_numpy())]
        agg = E.groupby(["need", "cost"]).v.agg(["mean", "size"]).reset_index()
        agg["fill_id"] = agg.need.map(lambda k: needs[k]["fill_id"])
        agg["rule"] = agg.need.map(lambda k: needs[k]["rule"])
        agg["spec"] = agg.need.map(lambda k: needs[k]["spec"])
        agg["suf"] = agg.need.map(lambda k: needs[k]["suf"])
        out_e = agg.rename(columns={"size": "n"})
    out_f = pd.DataFrame()
    if f_rows:
        Fr = pd.concat(f_rows, ignore_index=True)
        Fr = Fr[np.isfinite(Fr.v.to_numpy(float))]
        agg = Fr.groupby(["need", "field"]).v.mean().reset_index()
        agg["fill_id"] = agg.need.map(lambda k: needs[k]["fill_id"])
        agg["rule"] = agg.need.map(lambda k: needs[k]["rule"])
        out_f = agg
    if cfg["verbose"]:
        print(f"  pooled twins: {len(needs)} fills x scenarios, {len(R):,} twins on {R.coin.nunique()} coins in "
              f"{time.time() - t0:.0f}s", flush=True)
    return out_e, out_f


# ============================================================================ run_program
DEFAULT_CFG = dict(
    rules=("F1", "F2", "F3_1", "F3_2", "F3_3", "F3_5", "F3d_1", "F3d_2", "F3d_3", "F3d_5", "F4", "F5"),
    counts_only=False,          # bids and fills only (the "fill counts before returns" stage, §14)
    capacity="auto",            # auto: aggTrades on real U-Q1 programs, C1 otherwise | c1 | agg | none
    exits=None,                 # {rule: (ExitSpec, ...)}; default_exits(rules)
    twin_sens=True,             # ±30-day and always-pooled twins on the primary row (§10.4 sensitivity rows)
    drift=True,                 # leave-out drift on the primary row (§10.1)
    audit="raise",              # raise (a K5 violation stops the run) | report | off
    stream=False,               # stream U-B coins without a cached 1m file (stinkbid_data.m1_stream)
    fill_price="limit",         # limit (§7) | close | low: the two wrong engines K1b must reject
    keep_twins=False,           # return per-twin rows (controls' oracle comparisons)
    usd=True,                   # USD-converted F3 flags (K8)
    mw=True,                    # market-wide flags
    ml=True,                    # MoneyLine states
    n_jobs=1,                   # coin-parallel passes 1 and 2 (spawn processes; results do not depend on it)
    verbose=True,
)


def _cfg(cfg: dict | None) -> dict:
    c = dict(DEFAULT_CFG)
    if cfg:
        bad = set(cfg) - set(c)
        if bad:
            raise KeyError(f"unknown cfg keys {sorted(bad)}")
        c.update(cfg)
    c["rules"] = tuple(c["rules"])
    if c["exits"] is None:
        c["exits"] = default_exits(c["rules"])
    if c["fill_price"] not in ("limit", "close", "low"):
        raise ValueError("fill_price must be limit, close or low")
    return c


def _f1_extras(world: World, coin: str, b: pd.DataFrame, spot: Ser, idx: Ser | None, i1: np.ndarray,
               cfg: dict, prog_universe: str, cap_mode: str) -> pd.DataFrame:
    """Per F1 fill: gap-through flags (§7, K5), capacity (§7), speeds s24 / s6 / s1 and H24, the index's status at
    the fill minute (F3-unverifiable), the Robinhood outage flag, market-wide flags and the MoneyLine state at the fill
    day's close. Returns (frame, capacity curve or None)."""
    sel = np.flatnonzero(i1 >= 0)
    if not len(sel):
        return pd.DataFrame(), None
    i = i1[sel]
    m = spot.t[i]
    L = b.L.to_numpy(float)[sel]
    P0 = b.P0.to_numpy(float)[sel]
    sx = b.sidx.to_numpy(np.int64)[sel]
    out = pd.DataFrame({"row": sel})
    out["gap_through"] = L > spot.h[i]
    out["open_below"] = spot.o[i] < L
    # previous live minute of the segment closed above L (a true gap through L)
    pc = np.full(len(i), np.nan)
    for k, ii in enumerate(i):
        j = ii - 1
        while j >= spot.lo[sx[k]] and not spot.live[j]:
            j -= 1
        if j >= spot.lo[sx[k]]:
            pc[k] = spot.c[j]
    out["prev_close_above"] = pc > L
    # speeds (§10.4 D-H3): s_h = ln(H_h / L) / ln(P0 / L), H_h = highest live high in the h hours before the fill
    for h in SPEED_H:
        a = np.maximum(spot.idx(m - h * 60), spot.lo[sx])
        Hh = _k_range_max_batch(spot.hl, spot.mx1, spot.mx2, a.astype(np.int64), i.astype(np.int64))
        Hh = np.where(np.isfinite(Hh), Hh, np.nan)
        if h == 24:
            out["H24"] = Hh
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"s{h}"] = np.log(Hh / L) / np.log(P0 / L)
    # the index at the F1 minute
    if idx is not None and idx.n:
        k = np.searchsorted(idx.t, m)
        present = (k < idx.n) & (idx.t[np.minimum(k, idx.n - 1)] == m)
        out["idx_missing"] = ~present
        kk = np.minimum(k, idx.n - 1)
        out["idx_outage"] = present & ~((idx.upd[kk] >= IDX_MIN_UPDATES) & ~_in_rh_outage(m))
        out["idx_low_rel"] = np.where(present, idx.l[kk] / L, np.nan)
    else:
        out["idx_missing"] = True
        out["idx_outage"] = False
        out["idx_low_rel"] = np.nan
    out["rh_outage"] = _in_rh_outage(m)
    if cfg["mw"]:
        mw, share = world.mw_flags(coin, m // DAY_M)
        out["mw"] = mw
        out["mw_share"] = share
    if cfg["ml"] and not cfg["counts_only"]:
        # the state at the fill day's close is read after the fill: never in counts-only mode
        ml = world.moneyline(coin)
        segid = np.array([spot.seg.sid[s] for s in sx])
        out["ml_fill"] = [_ml_state(ml, int(d), int(sg)) for d, sg in zip(m // DAY_M, segid)]
    curve = None
    if cap_mode != "none":
        cap, curve = capacity(world, coin, b, spot, i1, cap_mode, curve=True)
        if len(cap):
            out = out.merge(cap, on="row", how="left")
    return out, curve


def _bmkt(world: World, b: pd.DataFrame, spot: Ser, i1: np.ndarray) -> pd.DataFrame:
    """B-MKT (§10.1, D6): buy at market at the placement minute + 1, hold 365 days (C-RH); and the bid's own
    365-day version ('bid; if filled hold to t0 + 365 days'), per placement."""
    n = len(b)
    s0 = b.sidx.to_numpy(np.int64)
    t1 = b.live_from.to_numpy(np.int64)
    jobs = (s0, t1, t1, np.full(n, np.inf), np.full(n, np.inf), np.full(n, F3_SPREAD), np.zeros(n, np.int64))
    en = run_exits(spot, RT_SPOT, jobs)
    S = b.t0.to_numpy(np.int64) + 365 * DAY_M
    jobs = (s0, S, S, np.full(n, np.inf), np.full(n, np.inf), np.full(n, F3_SPREAD), np.zeros(n, np.int64))
    ex = run_exits(spot, RT_SPOT, jobs)
    ok_e = en["kind"] == EK_STOP
    cb, _, cm = COSTS["C-RH"]
    xr = np.where(np.isin(ex["kind"], (EK_STOP, EK_DELIST)), ex["px"], np.nan)
    r_mkt = np.where(ok_e, xr * (1 - cm) / (en["px"] * (1 + cb)) - 1, np.nan)
    r_bid = np.where(i1 >= 0, xr * (1 - cm) / (b.L.to_numpy(float) * (1 + cb)) - 1, np.nan)
    return pd.DataFrame({"mkt_entry": en["px"], "mkt_r365": r_mkt, "bid_r365": r_bid,
                         "r365_complete": S <= world.end_min, "exit365_kind": EK_NAMES[ex["kind"]]})


def _pass1_coin(world: World, prog: Program, universe: str, coin: str, members_c, cfg: dict, need_idx: bool,
                need_perp: bool, usd, cap_mode: str) -> dict:
    """Pass 1 for one coin: bids, fills under every rule, F1 extras, the fill audit and (outcome runs) B-MKT. Bid ids
    are local (0..n-1); run_program makes them global in coin order."""
    tc = time.time()
    out = dict(coin=coin, bids=None, status=[], fills=None, audit=[], bmkt=None, msg="", f1key=None, cap_curve=None)
    if not world.has_coin(coin):
        out["status"].append((coin, -1, "no_1m_data", ""))
        return out
    spot, own_n, _ = build_spot(world, coin)
    rows, status = build_bids(world, prog, universe, coin, members_c, spot, cfg)
    out["status"] = status
    if not rows:
        return out
    b = pd.DataFrame(rows)
    b["bid_id"] = np.arange(len(b))
    idx = perp = None
    if need_idx or need_perp:
        if world.injected:
            months = None
        else:
            cand = sbd.index_fetch_days(pd.DataFrame({"coin": coin, "L": b.L, "live_from": _mts(b.live_from),
                                                      "live_to": _mts(b.life_end - 1)}))
            months = sorted(set(pd.DatetimeIndex(cand.day).strftime("%Y-%m"))) if len(cand) else []
        if need_idx and (months is None or len(months)):
            idx = build_index(world, coin, spot, months, "index")
        if need_perp and (months is None or len(months)):
            perp = build_index(world, coin, spot, months, "perp")
    rules = cfg["rules"]
    fl = coin_fills(b, spot, idx, perp, rules, usd if cfg["usd"] else None)
    if cfg["audit"] != "off":
        for r, v in fl.items():
            if r.startswith("F3usd"):
                continue
            ser = spot if r in ("F1", "F2") else (perp if r == "F5" else idx)
            out["audit"].extend(audit_fills(ser, b, r, v, coin))
    anyf = np.zeros(len(b), bool)
    for v in fl.values():
        anyf |= v >= 0
    i1 = fl.get("F1", np.full(len(b), -1))
    # the seed's fill index (§10.1, coding choice 16) ranks the program's F1 fills, computed whatever rules are run
    i1x = i1 if "F1" in fl else coin_fills(b, spot, None, None, ("F1",))["F1"]
    s1 = i1x >= 0
    out["f1key"] = pd.DataFrame({"bid_id": b.bid_id.to_numpy()[s1], "t": spot.t[i1x[s1]], "coin": coin,
                                 "method": b.method.to_numpy()[s1], "rung": b.rung.to_numpy(float)[s1],
                                 "shift": b["shift"].to_numpy(float)[s1]})
    ext, curve = _f1_extras(world, coin, b, spot, idx, i1, cfg, universe, cap_mode if "F1" in fl else "none")
    if curve is not None and len(curve):
        out["cap_curve"] = pd.DataFrame({"bid_id": b.bid_id.to_numpy()[curve.row.to_numpy(np.int64)],
                                         "minute": curve.minute.to_numpy(np.int64),
                                         "cum": curve.cum.to_numpy(float)})
    F = b[anyf].copy()
    F["row"] = np.flatnonzero(anyf)
    for r, v in fl.items():
        ser = spot if r in ("F1", "F2") else (perp if r == "F5" else idx)
        vv = v[anyf]
        F["i_" + r] = vv
        F["t_" + r] = np.where(vv >= 0, ser.t[np.maximum(vv, 0)] if ser is not None and ser.n else -1, -1)
    if len(ext):
        F = F.merge(ext, on="row", how="left")
    if cfg["fill_price"] != "limit" and len(F) and "F1" in fl:
        ok = F.i_F1.to_numpy() >= 0
        px = (spot.c if cfg["fill_price"] == "close" else spot.l)[np.maximum(F.i_F1.to_numpy(), 0)]
        F["entry_px_F1"] = np.where(ok, px, np.nan)
    out["fills"] = F
    if not cfg["counts_only"]:
        bm = _bmkt(world, b, spot, i1)
        bm["bid_id"] = b.bid_id.to_numpy()
        out["bmkt"] = bm
    out["bids"] = b
    out["msg"] = (f"  {coin}: {len(b)} bids, fills " + " ".join(f"{r} {int((v >= 0).sum())}" for r, v in fl.items())
                  + f" ({time.time() - tc:.1f}s)")
    return out


def _pass2_coin(world: World, coin: str, F: pd.DataFrame, members_c, q1_c, plan: dict, cfg: dict,
                need_idx: bool) -> dict:
    """Pass 2 for one coin: outcomes, benchmarks, exit audits, pooled-twin needs and the coin's pool tables."""
    tc = time.time()
    pool_needs, audit, tables = [], [], {}
    twin_log = [] if cfg["keep_twins"] else None
    cc = CoinCtx(world, coin, members_c, q1_c if q1_c is not None else np.zeros(0, np.int64), need_index=need_idx)
    o_rows, b_rows = coin_outcomes(world, cc, F, plan, cfg, pool_needs, audit, twin_log)
    if cc.idx_months is not None and o_rows:                      # coding choice 27: every index-route horizon read
        t_fill = {}
        for r in {row["rule"] for row in o_rows if _rule_route(row["rule"]) != RT_SPOT}:
            if "t_" + r in F:
                t_fill[r] = dict(zip(F.fill_id.to_numpy().tolist(), F["t_" + r].to_numpy(np.int64).tolist()))
        for row in o_rows:
            if _rule_route(row["rule"]) == RT_SPOT or row["horizon_t"] < 0:
                continue
            t_in = t_fill.get(row["rule"], {}).get(row["fill_id"], -1)
            if t_in < 0:
                continue
            m_a = int(_month_of_min(np.array([t_in]))[0])
            m_b = int(_month_of_min(np.array([min(int(row["horizon_t"]), world.end_min)]))[0])
            miss = [m for m in range(m_a, m_b + 1) if m not in cc.idx_months]
            if miss:
                raise RuntimeError(f"{coin} {row['rule']} fill {row['fill_id']}: index months "
                                   f"{[str(np.datetime64(m, 'M')) for m in miss]} needed but not read "
                                   f"(IDX_BUFFER_M = {IDX_BUFFER_M}; coding choice 27)")
    if cfg["fill_price"] != "limit":
        _rebook_entries(o_rows, F, cfg)
    if q1_c is not None and len(q1_c):
        for r in {_rule_route(x) for x in plan}:
            _pool_table(world, coin, r, q1_c, tables, cc)
    return dict(out_rows=o_rows, bench_rows=b_rows, pool_needs=pool_needs, audit=audit, tables=tables,
                twin_log=twin_log, msg=f"  outcomes {coin}: {len(F)} fills ({time.time() - tc:.1f}s)")


_WORKER: dict = {}


def _worker_world(data, stream):
    key = id(data) if data is not None else None
    w = _WORKER.get("world")
    if w is None or _WORKER.get("key") != key:
        w = World(data, stream=stream)
        _WORKER.update(world=w, key=key)
    return w


def _p1_task(args):
    data, stream, prog, universe, coin, members_c, cfg, need_idx, need_perp, cap_mode = args
    world = _worker_world(data, stream)
    usd = world.usd_hourly() if (cfg["usd"] and need_idx) else None
    return _pass1_coin(world, prog, universe, coin, members_c, cfg, need_idx, need_perp, usd, cap_mode)


def _p2_task(args):
    data, stream, coin, F, members_c, q1_c, plan, cfg, need_idx = args
    world = _worker_world(data, stream)
    return _pass2_coin(world, coin, F, members_c, q1_c, plan, cfg, need_idx)


def _map(fn, tasks, n_jobs: int):
    """Run tasks in order (n_jobs = 1) or in a spawn process pool (results in task order)."""
    if n_jobs <= 1 or len(tasks) <= 1:
        for t in tasks:
            yield fn(t)
        return
    import concurrent.futures as cf
    import multiprocessing as mp
    with cf.ProcessPoolExecutor(n_jobs, mp_context=mp.get_context("spawn")) as ex:
        for r in ex.map(fn, tasks):
            yield r


def run_program(program, universe: str = "U_Q1", coins=None, data=None, cfg: dict | None = None) -> dict:
    """Run a bid program (§6.3) on a universe (§5): bids, fills under F1-F5 (§7) with capacity, and (unless
    counts_only) every outcome of §8-§10.1 with B-TWIN twins, plus the K5 audit. See the module docstring. A
    streaming run (cfg stream=True, real data) deletes the streamed frames it kept when it ends."""
    c = _cfg(cfg)
    streaming = c["stream"] and (data is None or (isinstance(data, World) and not data.injected) or
                                 (isinstance(data, dict) and bool(data.get("real", False))))
    if not streaming:
        return _run_program(program, universe, coins, data, c)
    try:
        return _run_program(program, universe, coins, data, c)
    finally:
        sc = _StreamCache()
        for key in sc.files():
            sc.drop(key)


def _run_program(program, universe: str, coins, data, cfg: dict) -> dict:
    T0 = time.time()
    cfg = _cfg(cfg)
    prog = PROGRAMS[program] if isinstance(program, str) else program
    world = data if isinstance(data, World) else World(data, stream=cfg["stream"])
    members = world.members(universe)
    q1 = world.members("U_Q1") if "U_Q1" in world.universe().columns else members
    clist = sorted(members) if coins is None else [c for c in coins if c in members]
    rules = cfg["rules"]
    plan = {r: sp for r, sp in cfg["exits"].items() if r in rules}
    cap_mode = cfg["capacity"]
    if cap_mode == "auto":
        cap_mode = "agg" if (not world.injected and universe == "U_Q1") else "c1"
    need_idx = any(r.startswith("F3") or r == "F4" for r in rules)
    need_perp = "F5" in rules
    usd = world.usd_hourly() if (cfg["usd"] and need_idx) else None
    n_jobs = int(cfg["n_jobs"]) if not isinstance(data, World) else 1
    raw = data if not isinstance(data, World) else None
    sc = _StreamCache() if (cfg["stream"] and not world.injected) else None     # coding choice 26
    timings = {}
    all_bids, all_status, fill_parts, audit, bmkt_parts = [], [], [], [], []
    f1key_parts, curve_parts = [], []
    bid0 = 0
    t1 = time.time()
    # ---------------- pass 1: bids and fills (per coin; bid ids made global in coin order)
    if n_jobs > 1:
        tasks = [(raw, cfg["stream"], prog, universe, c, members[c], cfg, need_idx, need_perp, cap_mode)
                 for c in clist]
        it = _map(_p1_task, tasks, n_jobs)
    else:
        it = (_pass1_coin(world, prog, universe, c, members[c], cfg, need_idx, need_perp, usd, cap_mode)
              for c in clist)
    for r1 in it:
        all_status += r1["status"]
        audit += r1["audit"]
        if sc is not None and (r1["fills"] is None or not len(r1["fills"])):
            sc.drop(r1["coin"])                          # no outcome pass needs a coin without fills
        if r1["bids"] is None:
            continue
        b = r1["bids"]
        b["bid_id"] = b["bid_id"].to_numpy() + bid0
        if r1["fills"] is not None:
            F = r1["fills"]
            F["bid_id"] = F["bid_id"].to_numpy() + bid0
            fill_parts.append(F)
        if r1["bmkt"] is not None:
            bm = r1["bmkt"]
            bm["bid_id"] = bm["bid_id"].to_numpy() + bid0
            bmkt_parts.append(bm)
        for key, parts in (("f1key", f1key_parts), ("cap_curve", curve_parts)):
            if r1.get(key) is not None and len(r1[key]):
                x = r1[key]
                x["bid_id"] = x["bid_id"].to_numpy() + bid0
                parts.append(x)
        bid0 += len(b)
        all_bids.append(b)
        if cfg["verbose"]:
            print(r1["msg"], flush=True)
    timings["pass1_bids_fills_s"] = time.time() - t1
    bids = pd.concat(all_bids, ignore_index=True) if all_bids else pd.DataFrame(columns=BID_COLS)
    if bmkt_parts:
        bids = bids.merge(pd.concat(bmkt_parts, ignore_index=True), on="bid_id", how="left")
    fills = pd.concat(fill_parts, ignore_index=True) if fill_parts else pd.DataFrame()
    # ---------------- fill ids (the seed index of §10.1), clusters
    if len(fills):
        tcols = [c for c in fills.columns if c.startswith("t_F") and not c.startswith("t_F3usd")]
        tt = fills[tcols].to_numpy(np.int64).astype(float)
        tt[tt < 0] = np.inf
        prim = np.where(fills.get("t_F1", pd.Series(-1, index=fills.index)).to_numpy() >= 0,
                        fills.get("t_F1", pd.Series(-1, index=fills.index)).to_numpy(), tt.min(axis=1))
        fills["t_primary"] = prim
        fills = fills.sort_values(["t_primary", "coin", "method", "rung", "shift", "bid_id"], kind="stable",
                                  na_position="last").reset_index(drop=True)
        # coding choice 16: the program's F1 fills ranked by (F1 minute, coin, method, rung, shift, bid id) are fill
        # indices 0 .. N1 - 1 whatever other rules run; a bid filled only under other rules gets N1 + its bid id
        K = (pd.concat(f1key_parts, ignore_index=True) if f1key_parts else
             pd.DataFrame(columns=["bid_id", "t", "coin", "method", "rung", "shift"]))
        K = K.sort_values(["t", "coin", "method", "rung", "shift", "bid_id"], kind="stable", na_position="last")
        rank = dict(zip(K.bid_id.astype(np.int64).tolist(), range(len(K))))
        n1 = len(K)
        fills["fill_id"] = np.array([rank.get(int(x), n1 + int(x)) for x in fills.bid_id], np.int64)
        f1 = fills.get("t_F1", pd.Series(-1, index=fills.index)).to_numpy() >= 0
        fills["episode"] = -1
        fills["month_block"] = -1
        if f1.any():
            ft = _mts(fills.t_F1.to_numpy()[f1])
            fills.loc[f1, "episode"] = sbs.episodes(ft)[0]
            fills.loc[f1, "month_block"] = sbs.month_blocks(ft)[0]
            fills.loc[f1, "half"] = sbs.half_key(ft)
        qm = {c: set(v.tolist()) for c, v in q1.items()}
        fills["in_U_Q1"] = [int(mo) in qm.get(c, set()) for c, mo in zip(fills.coin, fills.month)]
    res = dict(program=prog.name, universe=universe, bids=bids,
               bid_status=pd.DataFrame(all_status, columns=["coin", "t0", "status", "detail"]), fills=fills,
               cap_curve=(pd.concat(curve_parts, ignore_index=True) if curve_parts else
                          pd.DataFrame(columns=["bid_id", "minute", "cum"])))
    viol = [a for a in audit if a.get("type") == "violation"]
    if viol and cfg["audit"] == "raise":
        res["audit"] = pd.DataFrame(audit)
        raise AuditError(f"K5 fill audit: {len(viol)} violations in bids / fills, first: {viol[0]}", res)
    if cfg["counts_only"] or not len(fills):
        res.update(outcomes=pd.DataFrame(), bench=pd.DataFrame(), audit=pd.DataFrame(audit),
                   meta=dict(cfg={k: v for k, v in cfg.items() if k != "exits"}, timings=timings,
                             seconds=time.time() - T0, counts_only=cfg["counts_only"]))
        return res
    # ---------------- pass 2: outcomes per coin
    t2 = time.time()
    pool_needs, out_rows, bench_parts, tables = [], [], [], {}
    twin_log = [] if cfg["keep_twins"] else None
    groups = list(fills.groupby("coin", sort=True))
    # streamed frames (coding choice 26): keep a coin's file until the last pass-2 coin whose lineage needs it
    last_use = {}
    if sc is not None:
        for gi, (c, _) in enumerate(groups):
            for x, _, _ in _lineage(world, c):
                last_use[x] = gi
        for key in sc.files() - set(last_use):
            sc.drop(key)
    if n_jobs > 1:
        it = _map(_p2_task, [(raw, cfg["stream"], c, F, members[c], q1.get(c), plan, cfg, need_idx)
                             for c, F in groups], n_jobs)
    else:
        it = (_pass2_coin(world, c, F, members[c], q1.get(c), plan, cfg, need_idx) for c, F in groups)
    for gi, r2 in enumerate(it):
        if sc is not None:
            for x in [x for x, g_ in last_use.items() if g_ == gi]:
                sc.drop(x)
        out_rows += r2["out_rows"]
        bench_parts += r2["bench_rows"]
        pool_needs += r2["pool_needs"]
        audit += r2["audit"]
        tables.update(r2["tables"])
        if twin_log is not None and r2["twin_log"]:
            twin_log += r2["twin_log"]
        if cfg["verbose"]:
            print(r2["msg"], flush=True)
    timings["pass2_outcomes_s"] = time.time() - t2
    outcomes = pd.DataFrame(out_rows)
    bench = pd.concat(bench_parts, ignore_index=True) if bench_parts else pd.DataFrame()
    # ---------------- pass 3: pooled twins
    t3 = time.time()
    pe, pf = run_pooled(world, pool_needs, q1, cfg, audit, tables, twin_log)
    timings["pass3_pooled_s"] = time.time() - t3
    if len(pe):
        for suf in pe.suf.unique():
            sub = pe[pe.suf == suf]
            key = pd.MultiIndex.from_frame(sub[["fill_id", "rule", "spec", "cost"]].rename(columns={"spec": "exit"}))
            mean = pd.Series(sub["mean"].to_numpy(), index=key)
            cnt = pd.Series(sub["n"].to_numpy(), index=key)
            ok = outcomes["twin_pooled" + suf].fillna(False).astype(bool).to_numpy() \
                if "twin_pooled" + suf in outcomes else np.zeros(len(outcomes), bool)
            k2 = pd.MultiIndex.from_frame(outcomes[["fill_id", "rule", "exit", "cost"]])
            mv = mean.reindex(k2).to_numpy()
            cv = cnt.reindex(k2).to_numpy()
            outcomes.loc[ok, "twin_mean" + suf] = mv[ok]
            outcomes.loc[ok, "twin_n" + suf] = np.nan_to_num(cv[ok]).astype(int)
            outcomes.loc[ok, "delta" + suf] = outcomes.loc[ok, "r"].to_numpy() - mv[ok]
    if len(pf) and len(bench):
        piv = pf.pivot_table(index=["fill_id", "rule"], columns="field", values="v", aggfunc="first")
        bench = bench.set_index(["fill_id", "rule"])
        for c in piv.columns:
            if c not in bench:
                bench[c] = np.nan
            v = piv[c].reindex(bench.index)
            bench[c] = bench[c].where(bench[c].notna(), v)
        bench = bench.reset_index()
    res.update(outcomes=outcomes, bench=bench, audit=pd.DataFrame(audit),
               meta=dict(cfg={k: v for k, v in cfg.items() if k != "exits"}, plan={r: [s.name for s in sp]
                                                                                 for r, sp in plan.items()},
                         timings=timings, seconds=time.time() - T0, n_pool_needs=len(pool_needs),
                         counts_only=False))
    if twin_log is not None:
        res["twins"] = twin_log
    viol = [a for a in audit if a.get("type") == "violation"]
    if viol and cfg["audit"] == "raise":
        raise AuditError(f"K5 fill audit: {len(viol)} violations, first: {viol[0]}", res)
    return res


class AuditError(RuntimeError):
    """A K5 violation (§10.5: any violation other than a listed gap-through fill stops the run)."""

    def __init__(self, msg, result=None):
        super().__init__(msg)
        self.result = result


def _rebook_entries(rows: list, F: pd.DataFrame, cfg: dict):
    """The two wrong engines of K1b (§10.5): F1 fills booked at the fill minute's close or low instead of L."""
    px = dict(zip(F.fill_id.to_numpy(), F.entry_px_F1.to_numpy()))
    Lm = dict(zip(F.fill_id.to_numpy(), F.L.to_numpy()))
    for r in rows:
        if r["rule"] != "F1" or not np.isfinite(r.get("r", np.nan)):
            continue
        f = r["fill_id"]
        r["r"] = (r["r"] + 1) * Lm[f] / px[f] - 1
        for k in ("r_dl_last", "r_dl0", "r_dl100"):
            if k in r and np.isfinite(r[k]):
                r[k] = (r[k] + 1) * Lm[f] / px[f] - 1
        for suf in ("", "_x30", "_pool"):
            if "twin_mean" + suf in r and np.isfinite(r["twin_mean" + suf]):
                r["delta" + suf] = r["r"] - r["twin_mean" + suf]


# ============================================================================ H4 stacking (§10.3)
H4_NAMES = {sbl.variant_label(m, p): m for m, p in sbl.H4_VARIANTS}     # 'M4 N=90 buffer=0.5' -> 'M4', ...


def h4_frames(res: dict, rule: str = "F1", exit: str = "FLIP", cost: str | None = None,
              delta_col: str = "delta") -> dict:
    """H4's stacked samples (§10.3) from an H4 program run: per chart method, the fills of the real level and of its
    four placebos (one level each per coin-week), with y = the fill's Delta (X-FLIP on the rule's route), real
    (bool), depth = delta_f - delta_real,cw (the real level's depth in sigma at placement, from the bids), cw (the
    coin-week id), time (the fill minute as a timestamp), coin and shift. Only fills whose whole exit horizon is
    observed enter (outcomes.complete; §4: 'A fill enters a horizon's statistics only if the whole horizon is
    observed'), whatever their exit. cost: None takes the rule's route label (C-RH on spot rules, RH on F3, C-EX on
    F4: the H4 gate under F3 is h4_frames(res, rule='F3_1')); a (rule, exit) with outcome rows but none at `cost`
    raises. Keys: 'M4', 'M5b', 'M6', 'M7' for the pre-registered four, the variant label for every other variant.
    Feed to stinkbid_stats.test_h4."""
    F, O, B = res["fills"], res["outcomes"], res["bids"]
    tcol = "t_" + rule
    if not len(F) or tcol not in F or not len(O):
        return {}
    if cost is None:
        cost = _cost_list(_rule_route(rule))[0]
    sel = O[(O.rule == rule) & (O.exit == exit)]
    if len(sel) and not (sel.cost == cost).any():
        raise ValueError(f"h4_frames: outcome rows for ({rule}, {exit}) carry cost labels "
                         f"{sorted(sel.cost.unique())}, not {cost!r}")
    sel = sel[(sel.cost == cost) & sel["complete"].eq(True)] if "complete" in sel else sel.iloc[:0]
    o = sel[["fill_id", delta_col]]
    o = o.rename(columns={delta_col: "_y"})
    f = F[F[tcol].to_numpy() >= 0].merge(o, on="fill_id", how="inner")
    real = B[B.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
    f = f.merge(real, on=["variant", "cw"], how="left")
    out = {}
    for var, g in f.groupby("variant"):
        g = g[np.isfinite(g["_y"].to_numpy(float)) & np.isfinite(g.delta_real.to_numpy(float))]
        out[H4_NAMES.get(var, var)] = pd.DataFrame({
            "y": g["_y"].to_numpy(float), "real": g.real.astype(bool).to_numpy(),
            "depth": (g.delta - g.delta_real).to_numpy(float), "cw": g.cw.to_numpy(), "time": _mts(g[tcol].to_numpy()),
            "coin": g.coin.to_numpy(), "shift": g["shift"].to_numpy(float), "fill_id": g.fill_id.to_numpy()})
    return out


# ============================================================================ accounts (§10.4 D7, D7-OWN)
def daily_lineage(world: World, coin: str) -> pd.DataFrame:
    """Daily prices of one unit of the coin's first asset along its lineage (§4.1): open / close x the segment's
    units, MoneyLine state, and, after a delisting, the §4.1 value (VWAP x 0.70) from the day after trading stopped
    (dead = True). Columns: day (int), open, close, green, dead."""
    rows = []
    carry = None                                      # (units of the predecessor's last segment, its lineage units)
    for c, u0, sg in _lineage(world, coin):
        k = world.d1(c)
        if "trades" in k:
            k = k[k.trades.to_numpy() > 0]
        k = k[k.seg.to_numpy() >= 0]
        if not len(k):
            break
        day = (_tmin(k.open_time) // DAY_M).astype(np.int64)
        seg = k.seg.to_numpy()
        ml = world.moneyline(c)
        gm = dict(zip(zip(ml.day.tolist(), ml.seg.tolist()), ml.green.tolist()))
        srow = {int(r.seg): r for r in sg.itertuples(index=False)} if sg is not None and len(sg) else {}
        # a swap successor continues from the predecessor's last units (its joined redenominations included)
        U = u0 if carry is None else carry[0] * (u0 / carry[1])
        segs = list(pd.unique(seg))
        stop = False
        for j, s_ in enumerate(segs):
            m = seg == s_
            r = srow.get(int(s_))
            rows.append(pd.DataFrame({"day": day[m], "open": k.open.to_numpy(float)[m] * U,
                                      "close": k.close.to_numpy(float)[m] * U, "u": U,
                                      "green": [gm.get((int(d), int(s_)), -1) for d in day[m]], "dead": False}))
            kind = str(getattr(r, "kind", "")) if r is not None else ""
            cont = bool(getattr(r, "continues", False)) if r is not None else False
            if j < len(segs) - 1:
                if cont and kind != "swap":
                    units = float(getattr(r, "units", 1.0))
                    U = U * (units if np.isfinite(units) else 1.0)
                    continue
                # a delisting at a gap: the old asset ends; later segments are a different asset for positions
                v = float(getattr(r, "vwap_last_full_day", np.nan)) * (1 - HAIRCUT) * U
                rows.append(pd.DataFrame({"day": [int(day[m][-1]) + 1], "open": [v], "close": [v], "u": [U],
                                          "green": [-1], "dead": [True]}))
                stop = True
                break
            if kind == "swap" and cont:
                carry = (U, u0)
                break                                     # continues in the successor (next lineage entry)
            if kind not in ("data_end", "") or (r is None and day[m][-1] < world.end_min // DAY_M):
                v = float(getattr(r, "vwap_last_full_day", np.nan)) * (1 - HAIRCUT) * U if r is not None else \
                    float(k.close.to_numpy(float)[m][-1]) * (1 - HAIRCUT) * U
                rows.append(pd.DataFrame({"day": [int(day[m][-1]) + 1], "open": [v], "close": [v], "u": [U],
                                          "green": [-1], "dead": [True]}))
                stop = True
        if stop:
            break
    if not rows:
        return pd.DataFrame(columns=["day", "open", "close", "u", "green", "dead"])
    d = pd.concat(rows, ignore_index=True).sort_values("day", kind="stable").drop_duplicates("day", keep="first")
    return d.reset_index(drop=True)


class _Panel:
    """Daily lineage prices of many coins on one day grid (forward-filled; NaN before a coin's first day)."""

    def __init__(self, world: World, coins, days: np.ndarray):
        self.days = days
        self.coins = list(coins)
        n, k = len(days), len(self.coins)
        self.close = np.full((n, k), np.nan)
        self.open = np.full((n, k), np.nan)
        self.green = np.full((n, k), -1, np.int8)
        self.u = np.full((n, k), np.nan)
        self.first = np.full(k, -1, np.int64)
        for j, c in enumerate(self.coins):
            d = daily_lineage(world, c)
            if not len(d):
                continue
            ix = np.searchsorted(days, d.day.to_numpy())
            ok = (ix < n) & (days[np.minimum(ix, n - 1)] == d.day.to_numpy())
            self.close[ix[ok], j] = d.close.to_numpy(float)[ok]
            self.open[ix[ok], j] = d.open.to_numpy(float)[ok]
            self.green[ix[ok], j] = d.green.to_numpy()[ok]
            self.u[ix[ok], j] = d.u.to_numpy(float)[ok]
            dead = d.dead.to_numpy(bool)
            if dead.any():                          # after a delisting the value stays at the §4.1 value
                dd = int(d.day.to_numpy()[dead][0])
                after = days >= dd
                self.close[after, j] = d.close.to_numpy(float)[dead][0]
                self.open[after, j] = d.close.to_numpy(float)[dead][0]
                self.green[after, j] = -1
            if ok.any():
                self.first[j] = int(ix[ok][0])
        self.close = pd.DataFrame(self.close).ffill().to_numpy()
        self.u = pd.DataFrame(self.u).ffill().fillna(1.0).to_numpy()
        self.open = np.where(np.isfinite(self.open), self.open, self.close)
        self.col = {c: j for j, c in enumerate(self.coins)}


class _Lots:
    """FIFO tax lots per coin column (§10.4 after-tax, coding choice 21): buy adds (day index, units, cost); a sale
    matches the oldest lots and books (day index, gain, held days) per lot piece; liquidate() sells every open lot at
    the last marks (a delisted coin at its §4.1 value)."""

    def __init__(self):
        self.q: dict = {}
        self.gains: list = []

    def buy(self, j, i, units, cost):
        if units > 0:
            self.q.setdefault(int(j), deque()).append([int(i), float(units), float(cost)])

    def sell(self, j, i, units, proceeds):
        dq = self.q.get(int(j))
        if not dq or not units > 0:
            return
        px = float(proceeds) / float(units)
        rem = float(units)
        while rem > 1e-12 * units and dq:
            lot = dq[0]
            take = min(rem, lot[1])
            c = lot[2] * take / lot[1]
            self.gains.append((int(i), take * px - c, int(i) - lot[0]))
            if take >= lot[1] * (1 - 1e-12):
                dq.popleft()
            else:
                lot[1] -= take
                lot[2] -= c
            rem -= take

    def liquidate(self, i, marks):
        for j, dq in self.q.items():
            m = float(marks[j]) if np.isfinite(marks[j]) else 0.0
            for d0, u, c in dq:
                self.gains.append((int(i), u * m - c, int(i) - d0))
        self.q = {}


def _after_tax(V: np.ndarray, days: np.ndarray, rf_day: np.ndarray, interest, gains) -> tuple:
    """After-tax daily values of an account (§10.4 D7: 'after-tax (35% short-term, 20% long-term)'; coding choice 21).
    interest (per day) is short-term income; gains = [(day index, gain, held days)] realized on sales and on the
    liquidation of every open lot at the last marks on the last day: held at most 365 days short-term (35%), longer
    long-term (20%). Each calendar year nets short-term and long-term results (a net loss of one kind offsets a net gain
    of the other) and carries net losses forward with their kind; the year's tax is paid on its last day (the data's
    last day for the final year) out of cash that would otherwise have earned the T-bill after tax. Returns (V minus
    the accumulated taxes, tax per day)."""
    nd = len(V)
    yr = pd.DatetimeIndex(_mts(np.asarray(days, np.int64) * DAY_M)).year.to_numpy()
    st = np.zeros(nd) if interest is None else np.asarray(interest, float).copy()
    lt = np.zeros(nd)
    for i, g, h in gains:
        if np.isfinite(g):
            (lt if h > 365 else st)[int(i)] += g
    tax = np.zeros(nd)
    ends = np.r_[np.flatnonzero(yr[1:] != yr[:-1]), nd - 1]
    starts = np.r_[0, ends[:-1] + 1]
    cst = clt = 0.0
    for a, b in zip(starts, ends):
        s_ = float(st[a:b + 1].sum()) + cst
        l_ = float(lt[a:b + 1].sum()) + clt
        if s_ < 0 < l_:
            net = s_ + l_
            s_, l_ = (0.0, net) if net >= 0 else (net, 0.0)
        elif l_ < 0 < s_:
            net = s_ + l_
            s_, l_ = (net, 0.0) if net >= 0 else (0.0, net)
        tax[b] = TAX_ST * max(s_, 0.0) + TAX_LT * max(l_, 0.0)
        cst, clt = min(s_, 0.0), min(l_, 0.0)
    D = np.zeros(nd)
    d = 0.0
    for i in range(nd):
        d = d * (1 + rf_day[i] * (1 - TAX_ST)) + tax[i]
        D[i] = d
    return np.asarray(V, float) - D, tax


def _summ(v: pd.Series, r_m: pd.Series, rf_m: pd.Series, inv=None, r_tax: pd.Series | None = None) -> dict:
    """CAGR, Sharpe (monthly excess over the T-bill, annualized), max drawdown (month-end values), after-tax CAGR
    (the after-tax values' monthly returns, compounded from the start like the pre-tax CAGR), time-average invested
    fraction."""
    n = len(r_m)
    yrs = n / 12.0
    g = float(np.prod(1 + r_m.to_numpy(float)))
    ex = (r_m - rf_m).to_numpy(float)
    sd = ex.std(ddof=1) if n > 2 else np.nan
    cum = np.cumprod(1 + r_m.to_numpy(float))
    dd = float((cum / np.maximum.accumulate(cum) - 1).min()) if n else np.nan
    out = dict(months=n, cagr=g ** (1 / yrs) - 1 if yrs > 0 else np.nan,
               sharpe=float(ex.mean() / sd * math.sqrt(12)) if sd and sd > 0 else np.nan, max_dd=dd)
    if r_tax is not None and len(r_tax):
        gt = float(np.prod(1 + r_tax.to_numpy(float)))
        out["cagr_after_tax"] = gt ** (1 / yrs) - 1 if yrs > 0 else np.nan
    if inv is not None:
        out["invested_avg"] = float(np.nanmean(inv))
    return out


def _route_exit(res: dict, route_rule: str) -> pd.DataFrame:
    """Per fill on the route: fill minute, exit minute and net return of X-FLIP (rule M; C-RH on spot)."""
    O = res["outcomes"]
    cost = "C-RH" if _rule_route(route_rule) == RT_SPOT else ("RH" if _rule_route(route_rule) == RT_IDX3 else "C-EX")
    o = O[(O.rule == route_rule) & (O.exit == "FLIP") & (O.cost == cost)][["fill_id", "r", "exit_t", "exit_kind"]]
    return o


def accounts(res: dict, data=None, route: str = "F1", r_res: float = 0.0, Q: float = 10_000.0, theta: float = 1.0,
             m_contrib: float = 1_000.0, tbill: bool = True) -> dict:
    """D7 accounts (§10.4) from a P1 run (run_program with outcomes): the flip account (3 rungs x coins, Q per rung,
    one position per (coin, rung), X-FLIP rule M, carry on reserved cash at r_res) and D7-OWN ($m per coin a month
    added to that coin's bid budget; rungs a third each, capped at Q_max; fills held to the end, X-OWN, and by
    MoneyLine, X-ML; unspent budget earns T-bills, 0 when tbill=False), each against B-MIX (equal exposure), B-TBILL,
    B-DCA, B-ALERT(-DCA), B-ML(-DCA) and B-HOLD. route: 'F1' (C-RH) or 'F3_1'. Daily ledger, month-end values;
    returns time-weighted (contributions at the start of the month). On F1 a position is what filled before its exit:
    min(Q, theta x the capacity accumulated minute by minute up to the exit minute, res['cap_curve']), each partial
    fill booked on its own day, the unfilled remainder reserved until the order's life ends (§7, V13). Returns monthly
    returns (and monthly_after_tax), values and a summary (CAGR, Sharpe, max drawdown, after-tax CAGR at 35%
    short-term / 20% long-term with every account liquidated at the end, end values, invested fraction)."""
    world = data if isinstance(data, World) else World(data)
    bids, fills, bench = res["bids"], res["fills"], res["bench"]
    end_day = world.end_min // DAY_M
    d0 = int(bids.t0.min() // DAY_M)
    days = np.arange(d0, end_day + 1, dtype=np.int64)
    nd = len(days)
    coins = sorted(bids.coin.unique())
    P = _Panel(world, coins, days)
    tb = (world.tbill(_mts(days * DAY_M)) / 100.0) if tbill else np.zeros(nd)
    rf_day = tb / 365.0
    di = lambda tm: np.clip(np.searchsorted(days, np.asarray(tm, np.int64) // DAY_M), 0, nd - 1)
    ex = _route_exit(res, route).set_index("fill_id")
    tcol = "t_" + route
    F = fills[fills[tcol].to_numpy() >= 0].copy() if tcol in fills else fills.iloc[:0]
    F = F.join(ex, on="fill_id")
    F = F[F.r.notna()]
    curve = res.get("cap_curve")
    cgrp = {}
    if route == "F1" and curve is not None and len(curve):
        for bid, g in curve.groupby("bid_id"):
            cgrp[int(bid)] = (g.minute.to_numpy(np.int64), g.cum.to_numpy(float))
    if route == "F1" and len(F) and not cgrp:
        raise ValueError("accounts on F1 size positions from capacity: run run_program with capacity != 'none'")
    out_m, out_mt, out_v, summary = {}, {}, {}, {}
    month_end = pd.DatetimeIndex(_mts(days * DAY_M)).tz_localize(None).to_period("M")
    me_idx = np.r_[np.flatnonzero(month_end[1:] != month_end[:-1]), nd - 1]
    me_lab = month_end[me_idx].astype(str)

    def monthly(V, flows=None):
        Vm = V[me_idx]
        fl = np.zeros(len(me_idx)) if flows is None else np.add.reduceat(flows, np.r_[0, me_idx[:-1] + 1])
        prev = np.r_[V[0] if flows is None else 0.0, Vm[:-1]]
        with np.errstate(divide="ignore", invalid="ignore"):
            r = (Vm - prev - fl) / (prev + fl)
        return pd.Series(r, index=me_lab)

    rf_m = pd.Series(np.add.reduceat(rf_day, np.r_[0, me_idx[:-1] + 1]), index=me_lab)

    def finish(name, V, interest=None, gains=(), lots=None, flows=None, inv=None, rf=None):
        """Monthly returns and the summary of one account, before and after tax (open lots liquidated at the end)."""
        gains = list(gains)
        if lots is not None:
            lots.liquidate(nd - 1, P.close[-1])
            gains += lots.gains
        Vt, tax = _after_tax(V, days, rf_day if rf is None else rf, interest, gains)
        r, rt = monthly(V, flows), monthly(Vt, flows)
        out_m[name], out_mt[name] = r, rt
        summary[name] = _summ(pd.Series(V[me_idx]), r, rf_m, inv, rt)
        summary[name].update(end_value=float(V[-1]), end_value_after_tax=float(Vt[-1]), tax_paid=float(tax.sum()))
        return Vt

    def ledger(flows, val, res_amt, rate_res, start):
        """Daily cash with interest (free cash at the T-bill, reserved cash at rate_res): (values, interest per day)."""
        cash = np.zeros(nd)
        itr = np.zeros(nd)
        c = start
        for i in range(nd):
            it = (c - res_amt[i]) * rf_day[i] + res_amt[i] * rate_res / 365.0
            c += it + flows[i]
            cash[i] = c
            itr[i] = it
        return cash + val, itr

    # ------------------------------------------------ D7 flip account
    week_coins = bids.groupby("t0").coin.nunique()
    K = 3 * Q * int(week_coins.max()) if len(week_coins) else 3 * Q
    cash_flow = np.zeros(nd)
    reserved = np.zeros(nd)
    pos_val = np.zeros(nd)
    alert_flow = np.zeros(nd)
    alert_val = np.zeros(nd)
    gains7, gainsA = [], []
    busy = {}
    taken = []
    Fb = F.set_index("bid_id")
    cb = C_RH if _rule_route(route) == RT_SPOT else 0.0
    for b in bids.sort_values(["t0", "coin", "rung"]).itertuples():
        key = (b.coin, b.rung)
        if busy.get(key, -1) > b.t0:
            continue
        a_ = di(b.t0)
        i_life = int(di(b.life_end))
        reserved[a_:i_life] += Q
        if b.bid_id not in Fb.index:
            busy[key] = b.life_end
            continue
        f = Fb.loc[b.bid_id]
        tf, te = int(f[tcol]), int(f.exit_t)
        busy[key] = te
        i_f, i_e = int(di(tf)), int(di(te))
        if route == "F1":
            # §7 / V13: filled dollars accumulate minute by minute; the position sold at the exit is what filled
            # before the exit minute, each partial fill on its own day
            cm, cv = cgrp.get(int(b.bid_id), (np.zeros(0, np.int64), np.zeros(0)))
            pre = cm < te
            fc_ = np.minimum(Q, theta * cv[pre])
            dd = di(cm[pre])
            ends = np.r_[np.flatnonzero(dd[1:] != dd[:-1]), len(dd) - 1] if len(dd) else np.zeros(0, np.int64)
            d_k, inc_k = dd[ends], np.diff(np.r_[0.0, fc_[ends]])
        else:
            d_k, inc_k = np.array([i_f]), np.array([Q])     # capacity is context on the market-maker route
        size = float(inc_k.sum())
        j = P.col[b.coin]
        u_lin = 1.0 / (float(b.L) * (1 + cb) * P.u[i_f, j])
        for dk, inc in zip(d_k, inc_k):
            if inc <= 0:
                continue
            reserved[dk:i_life] -= inc
            cash_flow[dk] -= inc
            if i_e > dk:
                pos_val[dk:i_e] += inc * u_lin * np.nan_to_num(P.close[dk:i_e, j])
        cash_flow[i_e] += size * (1 + float(f.r))
        gains7.append((i_e, size * float(f.r), (te - tf) / DAY_M))
        taken.append((b.bid_id, b.coin, b.rung, tf, te, size, float(f.r)))
        # B-ALERT for the flip account: the same position bought at the alert price (rule M), sold at the exit
        bb = bench[(bench.fill_id == f.fill_id) & (bench.rule == route)]
        if size > 0 and len(bb) and np.isfinite(bb.alert_M.iloc[0]) and bb.alert_t_M.iloc[0] >= 0:
            ta = int(bb.alert_t_M.iloc[0])
            if ta < te:
                i_a = int(di(ta))
                units_ratio = 1.0 / (1 + float(bb.alert_M.iloc[0]))     # coins per coin of the resting bid
                alert_flow[i_a] -= size
                alert_flow[i_e] += size * (1 + float(f.r)) * units_ratio
                gainsA.append((i_e, size * ((1 + float(f.r)) * units_ratio - 1), (te - ta) / DAY_M))
                if i_e > i_a:
                    alert_val[i_a:i_e] += size * u_lin * units_ratio * np.nan_to_num(P.close[i_a:i_e, j])
    V7, it7 = ledger(cash_flow, pos_val, reserved, r_res, K)
    inv7 = pos_val / V7
    x7 = float(np.nanmean(inv7))
    V7t = finish("D7", V7, it7, gains7, inv=inv7)
    out_v["D7"], out_v["D7_after_tax"] = V7, V7t
    summary["D7"].update(K=K, positions=len(taken), r_res=r_res, route=route)
    VA, itA = ledger(alert_flow, alert_val, np.zeros(nd), 0.0, K)
    finish("B-ALERT", VA, itA, gainsA, inv=alert_val / VA)
    # benchmarks at the same capital
    univ = world.members(res["universe"])
    mon_day = _month_of_min(days * DAY_M)
    members = np.zeros((nd, len(coins)), bool)
    for j, c in enumerate(coins):
        members[:, j] = np.isin(mon_day, univ.get(c, []))
    tradable = members & np.isfinite(P.close)
    VT, itT = ledger(np.zeros(nd), np.zeros(nd), np.zeros(nd), 0.0, K)
    finish("B-TBILL", VT, itT)
    VM, itM, lotsM = _bmix(P, tradable, rf_day, x7, K)
    finish("B-MIX", VM, itM, lots=lotsM, inv=np.full(nd, x7))
    # B-DCA: weekly buys of K / n_weeks across the week's coins at Monday's open, held
    wk = sorted(bids.t0.unique())
    per = K / max(len(wk), 1)
    units = np.zeros(len(coins))
    flows = np.zeros(nd)
    hold_units = np.zeros((nd, len(coins)))
    lots = _Lots()
    for t0 in wk:
        i = di(t0)
        cs = [P.col[c] for c in bids[bids.t0 == t0].coin.unique() if np.isfinite(P.open[i, P.col[c]])]
        if not cs:
            continue
        for j in cs:
            du = per / len(cs) / P.open[i, j]
            units[j] += du
            lots.buy(j, i, du, per / len(cs))
        flows[i] -= per
        hold_units[i:] = units
    val = np.nansum(hold_units * P.close, axis=1)
    VD, itD = ledger(flows, val, np.zeros(nd), 0.0, K)
    finish("B-DCA", VD, itD, lots=lots, inv=val / VD)
    # B-HOLD: K split equally across every coin that ever joins, each bought at its first member day's open
    ever = [j for j in range(len(coins)) if members[:, j].any()]
    flows = np.zeros(nd)
    hold_units = np.zeros((nd, len(coins)))
    lots = _Lots()
    for j in ever:
        okj = members[:, j] & np.isfinite(P.open[:, j])
        if not okj.any():
            continue
        i = int(np.flatnonzero(okj)[0])
        u = K / len(ever) / P.open[i, j]
        lots.buy(j, i, u, K / len(ever))
        flows[i] -= K / len(ever)
        hold_units[i:, j] = u
    val = np.nansum(hold_units * P.close, axis=1)
    VH, itH = ledger(flows, val, np.zeros(nd), 0.0, K)
    finish("B-HOLD", VH, itH, lots=lots, inv=val / VH)
    # B-ML: each coin's 3Q sleeve invested while its MoneyLine is green and the coin is a member, else T-bills
    VL, itL, lotsL = _bml(P, members, rf_day, 3 * Q, K)
    finish("B-ML", VL, itL, lots=lotsL)
    # ------------------------------------------------ D7-OWN
    own = _d7_own(world, res, P, days, di, members, rf_day if tbill else np.zeros(nd), m_contrib, route, theta, r_res,
                  bench, finish)
    return dict(monthly=pd.DataFrame(out_m), monthly_after_tax=pd.DataFrame(out_mt), summary=pd.DataFrame(summary).T,
                values=pd.DataFrame(out_v, index=_mts(days * DAY_M)), x_flip=x7,
                positions=pd.DataFrame(taken, columns=["bid_id", "coin", "rung", "t_fill", "t_exit", "size", "r"]),
                lots=own["lots"], contributions=own["contributions"])


def _bmix(P, tradable, rf_day, x, start, flows_ext=None):
    """B-MIX (R2): a constant fraction x in the month's member coins (equal weights, rebalanced at each month's
    first day at the previous close), the rest at the T-bill; delisted coins at their §4.1 value; contributions
    (flows_ext) invested at the current weights. Returns (daily values, interest per day, FIFO lots of the implied
    trades for the after-tax values)."""
    nd = len(rf_day)
    V = np.zeros(nd)
    itr = np.zeros(nd)
    lots = _Lots()
    k = tradable.shape[1]
    units = np.zeros(k)
    v = start
    w = None
    newm = np.r_[True, np.diff(_month_of_min(P.days * DAY_M)) != 0]
    for i in range(nd):
        px = P.close[i - 1] if i > 0 else P.close[i]
        px = np.where(np.isfinite(px), px, P.close[i])
        if flows_ext is not None and flows_ext[i] != 0:
            v += flows_ext[i]
            if w is not None:                                 # the contribution follows the current weights
                for j in np.flatnonzero(w > 0):
                    du = w[j] * flows_ext[i] / px[j]
                    units[j] += du
                    lots.buy(j, i, du, du * px[j])
        if newm[i] or w is None:
            cs = np.flatnonzero(tradable[i])
            w = np.zeros(k)
            if len(cs):
                w[cs] = x / len(cs)
            tgt = np.where(w > 0, w * v / np.where(w > 0, px, 1.0), 0.0)
            for j in np.flatnonzero((tgt != units)):
                d_ = tgt[j] - units[j]
                if d_ > 0:
                    lots.buy(j, i, d_, d_ * px[j])
                elif units[j] > 0:
                    lots.sell(j, i, -d_, -d_ * (px[j] if np.isfinite(px[j]) else 0.0))
            units = tgt
        if i > 0:
            with np.errstate(divide="ignore", invalid="ignore"):
                rc = np.where(w > 0, P.close[i] / P.close[i - 1] - 1, 0.0)
            rc = np.nan_to_num(rc)
            crypto = float((w * rc).sum())
            itr[i] = v * (1 - w.sum()) * rf_day[i]
            v = v * (1 + crypto + (1 - w.sum()) * rf_day[i])
            # weights drift within the month
            tot = 1 + crypto + (1 - w.sum()) * rf_day[i]
            w = w * (1 + rc) / tot if tot > 0 else w
        V[i] = v
    return V, itr, lots


def _bml(P, members, rf_day, sleeve, K):
    """B-ML for the flip account: each member coin's sleeve (3Q) held while its MoneyLine is green (bought at the next
    day's open after a green close, sold at the next day's open after a red close), else at the T-bill; the rest of
    the capital at the T-bill. Returns (daily values, interest per day, FIFO lots)."""
    nd = len(rf_day)
    k = members.shape[1]
    inv = np.zeros(k, bool)
    units = np.zeros(k)
    cash = K
    V = np.zeros(nd)
    itr = np.zeros(nd)
    lots = _Lots()
    for i in range(nd):
        itr[i] = cash * rf_day[i]
        cash *= 1 + rf_day[i]
        if i > 0:
            sig = (P.green[i - 1] == 1) & members[i - 1]
            for j in range(k):
                px = P.open[i, j]
                if not np.isfinite(px) or px <= 0:
                    continue
                if sig[j] and not inv[j] and cash >= sleeve:
                    units[j] = sleeve / px
                    lots.buy(j, i, units[j], sleeve)
                    cash -= sleeve
                    inv[j] = True
                elif not sig[j] and inv[j]:
                    lots.sell(j, i, units[j], units[j] * px)
                    cash += units[j] * px
                    units[j] = 0.0
                    inv[j] = False
        V[i] = cash + np.nansum(units * np.nan_to_num(P.close[i]))
    return V, itr, lots


def _d7_own(world, res, P, days, di, members, rf_day, m, route, theta, r_res, bench, finish):
    """D7-OWN (R13): $m per member coin a month (at the month's first placement) into that coin's bid budget; each
    Monday every rung with a level bids a third of the coin's free budget, capped at Q_max = 0.25 x the 10th
    percentile of the capacity of earlier fills at that rung (no cap with fewer than 10 earlier fills; coding choice
    21); filled dollars = min(size, theta C) over the order's life (F1; the size on F3), booked on the first fill day
    (the positions are held, so the size is the life's); unfilled amounts return to the free budget at expiry; fills
    are held to the end (X-OWN) or sold at X-ML (D7-OWN-ML). Free budget earns the T-bill, reserved budget r_res;
    interest accrues in a separate cash bucket (not re-bid). Benchmarks on the same contributions: B-ALERT-DCA (the
    same sizes bought at the alert price under rule M; the earmarked cash earns the T-bill until then), B-DCA-OWN (the
    first Monday open of the month), B-HOLD-OWN (the month's first daily open), B-ML-DCA (invested while green),
    B-TBILL-OWN and B-MIX-OWN (the D7-OWN invested fraction). Every account goes through `finish` (summary, monthly
    returns before and after tax)."""
    bids, fills = res["bids"], res["fills"]
    nd = len(days)
    coins = P.coins
    k = len(coins)
    tcol = "t_" + route
    F = fills[fills[tcol].to_numpy() >= 0].set_index("bid_id") if tcol in fills else fills.iloc[:0]
    B = bench[bench.rule == route].set_index("fill_id") if len(bench) else bench
    cap_col = "agg_life" if "agg_life" in F and F.agg_life.notna().any() else "c1_life"
    cb = C_RH if _rule_route(route) == RT_SPOT else 0.0
    first_monday = {}
    for t0 in sorted(bids.t0.unique()):
        first_monday.setdefault(int(_month_of_min(np.array([t0]))[0]), int(t0))
    ext = np.zeros((nd, k))
    for mo, t0 in first_monday.items():
        i = di(t0)
        ext[i] += np.where(members[i], m, 0.0)
    contrib = ext.sum(axis=1)
    sched = {int(di(t0)): g for t0, g in bids.sort_values(["t0", "coin", "rung"]).groupby("t0")}
    inv_own = None
    for variant in ("D7-OWN", "D7-OWN-ML", "B-ALERT-DCA"):
        free = np.zeros(k)
        resv = np.zeros(k)
        units = np.zeros(k)
        bucket = 0.0
        ev = {}
        caps = []
        V = np.zeros(nd)
        inv = np.zeros(nd)
        itr = np.zeros(nd)
        lots = []
        tax_lots = _Lots()
        alert = variant == "B-ALERT-DCA"

        def apply(evs, i):
            for (kind, j, cash, du) in evs:
                if kind == "fill":                       # reserved -> coins
                    resv[j] -= cash
                    units[j] += du
                    tax_lots.buy(j, i, du, cash)
                elif kind == "release":                  # reserved -> free
                    resv[j] -= cash
                    free[j] += cash
                elif kind == "sell":                     # coins -> free
                    units[j] += du
                    free[j] += cash
                    tax_lots.sell(j, i, -du, cash)
        for i in range(nd):
            itr[i] = free.sum() * rf_day[i] + resv.sum() * ((rf_day[i]) if alert else r_res / 365.0)
            bucket += itr[i]
            free += ext[i]
            apply(ev.pop(i, []), i)
            if i in sched:
                for c, gc in sched[i].groupby("coin"):
                    j = P.col[c]
                    avail = free[j]
                    if avail <= 0:
                        continue
                    for bb in gc.itertuples():
                        size = avail / 3.0
                        hist = [x for (t_, rg, x) in caps if rg == bb.rung and t_ < bb.t0 and np.isfinite(x)]
                        if len(hist) >= 10:
                            size = min(size, 0.25 * float(np.percentile(hist, 10)))
                        if size <= 0:
                            continue
                        free[j] -= size
                        resv[j] += size
                        life_i = int(di(bb.life_end))
                        if bb.bid_id not in F.index:
                            ev.setdefault(life_i, []).append(("release", j, size, 0.0))
                            continue
                        f = F.loc[bb.bid_id]
                        tf = int(f[tcol])
                        i_f = int(di(tf))
                        cap = float(f[cap_col]) if cap_col in f.index and np.isfinite(f[cap_col]) else np.inf
                        caps.append((tf, bb.rung, cap))
                        if alert:
                            bf = B.loc[f.fill_id] if f.fill_id in B.index else None
                            if bf is None or not np.isfinite(bf.alert_px_M) or bf.alert_t_M < 0:
                                ev.setdefault(life_i, []).append(("release", j, size, 0.0))
                                continue
                            i_a = int(di(int(bf.alert_t_M)))
                            du = size / (float(bf.alert_px_M) * (1 + cb) * P.u[i_a, j])
                            ev.setdefault(i_a, []).append(("fill", j, size, du))
                            continue
                        filled = min(size, theta * cap) if route == "F1" else size
                        du = filled / (float(f.L) * (1 + cb) * P.u[i_f, j])
                        ev.setdefault(i_f, []).append(("fill", j, filled, du))
                        lots.append((int(bb.bid_id), c, i_f, filled, du))
                        if filled < size:
                            ev.setdefault(max(life_i, i_f), []).append(("release", j, size - filled, 0.0))
                        if variant == "D7-OWN-ML" and f.fill_id in B.index:
                            bf = B.loc[f.fill_id]
                            if np.isfinite(bf.get("xml_px", np.nan)) and bf.get("xml_t", -1) >= 0:
                                i_x = int(di(int(bf.xml_t)))
                                proceeds = filled / (float(f.L) * (1 + cb)) * float(bf.xml_px) * (1 - C_RH)
                                ev.setdefault(max(i_x, i_f), []).append(("sell", j, proceeds, -du))
                apply(ev.pop(i, []), i)                 # fills on the placement day itself
            pv = float(np.nansum(units * np.nan_to_num(P.close[i])))
            V[i] = free.sum() + resv.sum() + bucket + pv
            inv[i] = pv / V[i] if V[i] > 0 else 0.0
        finish(variant, V, itr, lots=tax_lots, flows=contrib, inv=inv)
        if variant == "D7-OWN":
            inv_own = inv
            lots_own = lots
    x = float(np.nanmean(inv_own[contrib.cumsum() > 0])) if inv_own is not None else 0.0
    tradable = members & np.isfinite(P.close)
    VM, itM, lotsM = _bmix(P, tradable, rf_day, x, 0.0, flows_ext=contrib)
    finish("B-MIX-OWN", VM, itM, lots=lotsM, flows=contrib, inv=np.full(nd, x), rf=rf_day)
    for name, when in (("B-DCA-OWN", "monday"), ("B-HOLD-OWN", "first")):
        units = np.zeros(k)
        hold = np.zeros((nd, k))
        tax_lots = _Lots()
        for mo, t0 in first_monday.items():
            i0 = int(di(t0))
            i = i0 if when == "monday" else int(np.flatnonzero(_month_of_min(days * DAY_M) == mo)[0])
            for j in range(k):
                if ext[i0, j] > 0 and np.isfinite(P.open[i, j]) and P.open[i, j] > 0:
                    du = ext[i0, j] / P.open[i, j]
                    units[j] += du
                    tax_lots.buy(j, i, du, ext[i0, j])
            hold[i:] = units
        V = np.nansum(hold * np.nan_to_num(P.close), axis=1)
        finish(name, V, None, lots=tax_lots, flows=contrib, rf=rf_day)
    V = np.zeros(nd)
    itr = np.zeros(nd)
    v = 0.0
    for i in range(nd):
        itr[i] = v * rf_day[i]
        v = v * (1 + rf_day[i]) + contrib[i]
        V[i] = v
    finish("B-TBILL-OWN", V, itr, flows=contrib, rf=rf_day)
    V = np.zeros(nd)
    itr = np.zeros(nd)
    cashc = np.zeros(k)
    units = np.zeros(k)
    tax_lots = _Lots()
    for i in range(nd):
        itr[i] = float((cashc * rf_day[i]).sum())
        cashc = cashc * (1 + rf_day[i]) + ext[i]
        if i > 0:
            g = P.green[i - 1] == 1
            px = P.open[i]
            ok = np.isfinite(px) & (px > 0)
            buy = g & ok & (cashc > 0)
            for j in np.flatnonzero(buy):
                du = cashc[j] / px[j]
                tax_lots.buy(j, i, du, cashc[j])
                units[j] += du
                cashc[j] = 0.0
            sell = (~g) & ok & (units > 0)
            for j in np.flatnonzero(sell):
                tax_lots.sell(j, i, units[j], units[j] * px[j])
                cashc[j] += units[j] * px[j]
                units[j] = 0.0
        V[i] = cashc.sum() + np.nansum(units * np.nan_to_num(P.close[i]))
    finish("B-ML-DCA", V, itr, lots=tax_lots, flows=contrib, rf=rf_day)
    return dict(contributions=float(contrib.sum()),
                lots=pd.DataFrame(lots_own, columns=["bid_id", "coin", "day_index", "cost", "units_lin"]))


# ============================================================================ synthetic worlds (selftest; controls)
def synth_coin(start: str, days: int, seed: int, p0: float = 10.0, sd_day: float = 0.04, jumps=(), zero_frac=0.002,
               missing=(), tick: str = "0.0001", seg_breaks=(), end_at=None, drift_m: float = 0.0) -> pd.DataFrame:
    """1m bars of a synthetic martingale coin: Gaussian minute log returns (daily SD sd_day, mean -s^2/2 so the
    price is a martingale), jumps = [(minute offset, log jump)] applied at a minute's open (the minute gaps), a share
    of zero-trade placeholder minutes (OHLC = previous close), missing minutes, all prices on the tick grid
    (rounded half up), quote volumes and taker shares for C1. seg_breaks: minute offsets that start a new seg id."""
    rng = np.random.default_rng(seed)
    n = days * DAY_M if end_at is None else end_at
    s = sd_day / math.sqrt(DAY_M)
    z = rng.normal(-0.5 * s * s + drift_m, s, size=(n, 4))
    lp = math.log(p0) + np.cumsum(z[:, 3])
    jmp = np.zeros(n)
    for off, j in jumps:
        if 0 <= off < n:
            jmp[off] += j
    lp = lp + np.cumsum(jmp)
    close = np.exp(lp)
    op = np.r_[p0, close[:-1]] * np.exp(jmp)              # the jump happens at the minute's open
    a = np.exp(np.abs(z[:, 0]) * 0.8)
    b = np.exp(np.abs(z[:, 1]) * 0.8)
    high = np.maximum(op, close) * a
    low = np.minimum(op, close) / b
    tk = float(tick)
    ndp = max(0, -int(round(math.log10(tk))))
    rnd = lambda x: np.round(np.round(x / tk) * tk, ndp)       # the double nearest the decimal (as parsed prices)
    op, high, low, close = rnd(op), rnd(high), rnd(low), rnd(close)
    op, close = np.maximum(op, tk), np.maximum(close, tk)
    high = np.maximum.reduce([high, op, close])
    low = np.minimum.reduce([low, op, close])
    low = np.maximum(low, tk)
    trades = rng.integers(5, 200, n).astype(np.int32)
    zero = rng.random(n) < zero_frac
    trades[zero] = 0
    zi = np.flatnonzero(zero)
    for i in zi:                                          # placeholder bars: OHLC = previous close
        pc = close[i - 1] if i > 0 else op[i]
        op[i] = high[i] = low[i] = close[i] = pc
    qv = rng.uniform(2e4, 2e5, n) * (trades > 0)
    tb = qv * rng.uniform(0.3, 0.7, n)
    t = _ts(start).as_unit("ns") + pd.to_timedelta(np.arange(n), unit="min")
    k = pd.DataFrame({"open_time": t, "open": op, "high": high, "low": low, "close": close,
                      "volume": qv / close, "quote_volume": qv, "trades": trades, "taker_buy_quote": tb})
    seg = np.zeros(n, np.int32)
    for off in seg_breaks:
        seg[off:] += 1
    k["seg"] = seg
    keep = np.ones(n, bool)
    for a_, b_ in missing:
        keep[a_:b_] = False
    return k[keep].reset_index(drop=True)


def synth_world(n_coins: int = 4, days: int = 400, start: str = "2020-01-01", seed: int = 1, jumps_per_year=6,
                jump_size=-0.25, end: str | None = None, universe_months=None, tick: str = "0.0001",
                index: bool = True, extra: dict | None = None) -> dict:
    """An injected world: n_coins synthetic coins with market-wide gap-through jumps (the same minutes for every
    coin), every coin in U_Q1 and U_B every month, index bars = spot bars with 60 updates (except outage minutes),
    no T-bill. extra: {coin: frames} merged in (hand-built coins)."""
    rng = np.random.default_rng(seed)
    nj = int(round(jumps_per_year * days / 365))
    jm = np.sort(rng.integers(40 * DAY_M, days * DAY_M - DAY_M, nj))
    coins = {}
    for c in range(n_coins):
        name = f"SYN{c}"
        js = [(int(x), jump_size * rng.uniform(0.6, 1.4)) for x in jm]
        k = synth_coin(start, days, seed * 100 + c, p0=float(rng.uniform(2, 50)), jumps=js, tick=tick)
        fr = {"m1": k, "tick": tick}
        if index:
            ix = k[["open_time", "open", "high", "low", "close"]].copy()
            ix["updates"] = np.where(k.trades.to_numpy() > 0, 60, 0)
            fr["index_m1"] = ix
            pp = k[["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades",
                    "taker_buy_quote"]].copy()
            fr["perp_m1"] = pp
        coins[name] = fr
    if extra:
        coins.update(extra)
    end = end or (pd.Timestamp(start) + pd.Timedelta(days=days - 1)).strftime("%Y-%m-%d")
    months = pd.period_range(start, end, freq="M").strftime("%Y-%m") if universe_months is None else universe_months
    rows = [dict(month=m, coin=c, U_Q1=True, U_B=True) for m in months for c in coins]
    return {"universe": pd.DataFrame(rows), "coins": coins, "end": end, "tbill": 0.0}


# ============================================================================ selftest
def _say(msg):
    print(msg, flush=True)


def _flat_m1(t_from: pd.Timestamp, t_to: pd.Timestamp, price: float, tick: str) -> pd.DataFrame:
    """1m bars from t_from to t_to (exclusive) at a flat price that alternates one tick up and down (live)."""
    t = pd.date_range(t_from, t_to, freq="min", inclusive="left")
    n = len(t)
    tk = float(tick)
    c = price + tk * (np.arange(n) % 2)
    k = pd.DataFrame({"open_time": t, "open": c, "high": c + tk, "low": c - tk, "close": c,
                      "volume": np.full(n, 100.0), "quote_volume": np.full(n, 100.0 * price),
                      "trades": np.full(n, 10, np.int32), "taker_buy_quote": np.full(n, 50.0 * price),
                      "seg": np.zeros(n, np.int32)})
    return k


def _hist_d1(d0: pd.Timestamp, price: float, a: float, n: int = 45) -> pd.DataFrame:
    """n daily bars ending on day d0 (inclusive) with alternating log returns +-a, closing at `price` on d0."""
    days = pd.date_range(d0 - pd.Timedelta(days=n - 1), d0, freq="D", tz="UTC")
    lr = np.where(np.arange(n) % 2 == 0, a, -a)
    lr[-1] = 0.0
    c = price * np.exp(np.cumsum(lr[::-1])[::-1] - lr[-1])
    c = c * price / c[-1]
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open_time": days, "open": o, "high": np.maximum(o, c) * 1.01,
                         "low": np.minimum(o, c) * 0.99, "close": c, "volume": np.full(n, 1e4),
                         "quote_volume": c * 1e4, "trades": np.full(n, 1000), "seg": np.zeros(n, np.int32)})


def _set(k: pd.DataFrame, t: pd.Timestamp, **v):
    """Override one minute's fields (the minute must exist); open/high/low/close given as values."""
    i = np.flatnonzero((_tmin(k.open_time) == _tmin(t)))
    if not len(i):
        raise KeyError(t)
    for c, x in v.items():
        k.loc[i[0], c] = x


def _hb_world(spec: dict, end: str) -> dict:
    """An injected world of hand-built coins: spec = {coin: (frames)}; every coin in U_Q1 / U_B in its months."""
    rows = []
    for c, fr in spec.items():
        for m in fr.pop("_months"):
            rows.append(dict(month=m, coin=c, U_Q1=True, U_B=True))
    return {"universe": pd.DataFrame(rows), "coins": spec, "end": end, "tbill": 0.0}


def _t_hand(say):
    """Hand-built 1m paths with known fills and exits (prereg §7, §8, K5)."""
    tick = "0.01"
    t0 = pd.Timestamp("2023-03-06 03:30", tz="UTC")             # a Monday placement; US DST starts 2023-03-12
    d0 = pd.Timestamp("2023-03-05", tz="UTC")
    P0, a = 100.0, 0.03
    end = "2023-03-20"
    tend = pd.Timestamp("2023-03-21", tz="UTC")
    d1h = _hist_d1(d0, P0, a)
    lv = {"d1": d1h, "tick": tick, "real": False}
    I = sbl.inputs_at("X", t0, data=lv)
    assert I["ok"], I["why"]
    L, _ = sbl.level("M2", I, k=6.0)
    info = sbl.level_info("M2", I, k=6.0)
    Lt = sbl.tick_value(info["n_ticks"] - 1, tick)
    R = sbl.ceil_tick(L + 0.5 * (I["P0"] - L), tick)
    say(f"  hand-built: P0 {I['P0']:.4f}, sigma30 {I['sigma30']:.4f}, k=6 level L {L}, L - tau {Lt}, R1/2 {R}")
    tk = float(tick)

    def coin_frames(m1, extra=None):
        d1 = pd.concat([d1h.iloc[:-1], _daily_from_m1(m1)], ignore_index=True)
        d1["seg"] = 0
        fr = {"m1": m1, "d1": d1, "tick": tick, "_months": ["2023-03"]}
        fr.update(extra or {})
        return fr

    spec = {}
    # (a) GAP: a minute wholly below L at 15:00 UTC Monday (10:00 New York, EST): fill at L, gap-through; the price
    # stays at 0.88 L: no target, time stop at M(fill + 72 h) at that minute's open
    m1 = _flat_m1(d0, tend, P0, tick)
    tg = pd.Timestamp("2023-03-06 15:00", tz="UTC")
    after = m1.open_time >= tg
    lvl = round(0.88 * L, 2)
    m1.loc[after, ["open", "close"]] = lvl
    m1.loc[after, "high"] = lvl + tk
    m1.loc[after, "low"] = lvl - tk
    _set(m1, tg, open=round(0.9 * L, 2), high=round(0.9 * L, 2), low=round(0.85 * L, 2), close=lvl)
    spec["GAP"] = coin_frames(m1)
    # (b) MKT: a wick through L at 15:00 UTC; above R from 15:30; the sell goes live at 16:00 UTC (rule M daytime)
    # and executes at that minute's open as a marketable limit
    m1 = _flat_m1(d0, tend, P0, tick)
    tf = pd.Timestamp("2023-03-06 15:00", tz="UTC")
    _set(m1, tf, low=Lt - tk)
    up = m1.open_time >= pd.Timestamp("2023-03-06 15:30", tz="UTC")
    hiP = round(R * 1.05, 2)
    m1.loc[up, ["open", "close"]] = hiP
    m1.loc[up, "high"] = hiP + tk
    m1.loc[up, "low"] = hiP - tk
    spec["MKT"] = coin_frames(m1)
    # (c) NIGHT: a wick at 07:00 UTC (02:00 New York): the manual sell goes live at 07:00 New York = 12:00 UTC; the
    # price gaps to 1.3 R at 08:00 UTC (03:00 NY), is 1.2 R at 12:00 UTC: manual exit = that open (marketable);
    # the bot's resting sell (live 07:01 UTC) fills at R at 08:00 UTC (a sell that gapped through: listed)
    m1 = _flat_m1(d0, tend, P0, tick)
    tn = pd.Timestamp("2023-03-07 07:00", tz="UTC")
    w0 = m1.open_time > tn
    p95 = round(0.95 * L, 2)
    m1.loc[w0, ["open", "close"]] = p95
    m1.loc[w0, "high"] = p95 + tk
    m1.loc[w0, "low"] = p95 - tk
    _set(m1, tn, low=Lt - tk)
    w1 = (m1.open_time >= pd.Timestamp("2023-03-07 08:00", tz="UTC"))
    p13 = round(1.3 * R, 2)
    p12 = round(1.2 * R, 2)
    m1.loc[w1, ["open", "close"]] = p13
    m1.loc[w1, "high"] = p13 + tk
    m1.loc[w1, "low"] = p13 - tk
    w2 = m1.open_time >= pd.Timestamp("2023-03-07 12:00", tz="UTC")
    m1.loc[w2, ["open", "close"]] = p12
    m1.loc[w2, "high"] = p12 + tk
    m1.loc[w2, "low"] = p12 - tk
    spec["NIGHT"] = coin_frames(m1)
    # (d) STOP: a wick at 16:00 UTC Wednesday 2023-03-08 (11:00 EST); no rebound; the stop is M(fill + 72 h):
    # Saturday 16:00 UTC = 11:00 EST -> 17:00 UTC; that minute has no trades, the next two are missing -> the exit is
    # the open of 17:03 UTC
    m1 = _flat_m1(d0, tend, P0, tick)
    ts_ = pd.Timestamp("2023-03-08 16:00", tz="UTC")
    _set(m1, ts_, low=Lt - tk)
    low_after = m1.open_time > ts_
    pl = round(0.95 * L, 2)
    m1.loc[low_after, ["open", "close"]] = pl
    m1.loc[low_after, "high"] = pl + tk
    m1.loc[low_after, "low"] = pl - tk
    stop_t = pd.Timestamp("2023-03-11 17:00", tz="UTC")
    _set(m1, stop_t, trades=0, open=pl, high=pl, low=pl, close=pl)
    m1 = m1[~m1.open_time.isin([stop_t + pd.Timedelta("1min"), stop_t + pd.Timedelta("2min")])].reset_index(drop=True)
    _set(m1, stop_t + pd.Timedelta("3min"), open=round(0.97 * L, 2), high=round(0.97 * L, 2) + tk,
         low=round(0.97 * L, 2) - tk, close=round(0.97 * L, 2))
    spec["STOP"] = coin_frames(m1)
    # (e) OUT: a zero-trade minute with a low far below L (never fills), a missing minute, then a live trigger
    m1 = _flat_m1(d0, tend, P0, tick)
    _set(m1, pd.Timestamp("2023-03-07 10:00", tz="UTC"), trades=0, low=round(0.5 * L, 2))
    m1 = m1[m1.open_time != pd.Timestamp("2023-03-07 10:05", tz="UTC")].reset_index(drop=True)
    tlive = pd.Timestamp("2023-03-07 10:10", tz="UTC")
    _set(m1, tlive, low=Lt)
    spec["OUT"] = coin_frames(m1)
    # (f) IDX: index bars = spot bars; at the F1 minute (Tue 10:00 UTC) the index minute is missing; at 11:00 the
    # index low is below L/1.01 with 20 updates (an outage: no F3 fill); at 12:00 with 60 updates: the F3 fill
    m1 = _flat_m1(d0, tend, P0, tick)
    tf1 = pd.Timestamp("2023-03-07 10:00", tz="UTC")
    _set(m1, tf1, low=Lt - tk)
    ix = m1[["open_time", "open", "high", "low", "close"]].copy()
    ix["updates"] = 60
    ix = ix[ix.open_time != tf1].reset_index(drop=True)
    t11 = pd.Timestamp("2023-03-07 11:00", tz="UTC")
    t12 = pd.Timestamp("2023-03-07 12:00", tz="UTC")
    _set(ix, t11, low=round(L / 1.01 - 0.5, 2), updates=20)
    _set(ix, t12, low=round(L / 1.01 - 0.5, 2))
    spec["IDX"] = coin_frames(m1, {"index_m1": ix})
    # (g) DELIST: a wick on Tuesday 15:00 UTC, then trading stops on Wednesday 2023-03-08 at 23:59 UTC: the flip's
    # window ends in a delisting valued at the VWAP of the last full day (Wednesday) x 0.70
    m1 = _flat_m1(d0, pd.Timestamp("2023-03-09", tz="UTC"), P0, tick)
    tdl = pd.Timestamp("2023-03-07 15:00", tz="UTC")
    _set(m1, tdl, low=Lt - tk)
    lowp = m1.open_time > tdl
    m1.loc[lowp, ["open", "close"]] = round(0.9 * L, 2)
    m1.loc[lowp, "high"] = round(0.9 * L, 2) + tk
    m1.loc[lowp, "low"] = round(0.9 * L, 2) - tk
    m1.loc[lowp, "quote_volume"] = m1.loc[lowp, "volume"] * m1.loc[lowp, "close"]
    spec["DELIST"] = coin_frames(m1)
    # (h) JUMP: a segment boundary (a new seg id, trading continues) on Tuesday 00:00 UTC cancels the bid: a wick
    # through L on Tuesday never fills it
    m1 = _flat_m1(d0, tend, P0, tick)
    m1.loc[m1.open_time >= pd.Timestamp("2023-03-07", tz="UTC"), "seg"] = 1
    _set(m1, pd.Timestamp("2023-03-07 10:00", tz="UTC"), low=Lt - tk)
    fr = coin_frames(m1)
    fr["d1"].loc[fr["d1"].open_time >= pd.Timestamp("2023-03-07", tz="UTC"), "seg"] = 1
    spec["JUMP"] = fr
    W = _hb_world(spec, end)
    cfg = dict(rules=("F1", "F3_1"), audit="report", verbose=False, twin_sens=False, drift=False, mw=False,
               exits={"F1": (FLIP, FLIP_BOT), "F3_1": (FLIP,)})
    res = run_program("P1", "U_Q1", data=W, cfg=cfg)
    F, O, B, A = res["fills"], res["outcomes"], res["bench"], res["audit"]
    k6 = lambda c: F[(F.coin == c) & (F.rung == 6.0) & (F.t0 == _tmin(t0))]
    o6 = lambda c, ex="FLIP", cost="C-0", rule="F1": O[(O.fill_id.isin(k6(c).fill_id)) & (O.exit == ex) &
                                                        (O.cost == cost) & (O.rule == rule)]
    viol = A[A.type == "violation"] if len(A) else A
    assert not len(viol), viol.head().to_string()
    # (a)
    f = k6("GAP")
    assert len(f) == 1 and f.t_F1.iloc[0] == _tmin(tg) and bool(f.gap_through.iloc[0]), f.T
    o = o6("GAP")
    stop_a = rule_m(_tmin(tg) + 72 * 60)
    assert stop_a == _tmin(pd.Timestamp("2023-03-09 16:00", tz="UTC")), _mts(stop_a)
    exp = lvl / L - 1
    assert o.exit_kind.iloc[0] == "stop" and o.exit_t.iloc[0] == stop_a and abs(o.r.iloc[0] - exp) < 1e-12, o.T
    o_rh = o6("GAP", cost="C-RH")
    exp_rh = lvl * (1 - C_RH) / (L * (1 + C_RH)) - 1
    assert abs(o_rh.r.iloc[0] - exp_rh) < 1e-12
    gaps = A[(A.type == "gap") & (A.coin == "GAP")]
    assert len(gaps) >= 1
    say(f"  (a) gap-through fill at L in a minute wholly below it (listed by the audit); time stop at "
        f"{_mts(stop_a)}: r {o.r.iloc[0]:+.4f} = {lvl}/L - 1 (C-RH {o_rh.r.iloc[0]:+.4f})")
    # (b)
    o = o6("MKT")
    golive = _tmin(pd.Timestamp("2023-03-06 16:00", tz="UTC"))
    assert o.exit_kind.iloc[0] == "marketable" and o.exit_t.iloc[0] == golive, o.T
    assert abs(o.exit_px.iloc[0] - hiP) < 1e-12 and o.exit_px.iloc[0] > R
    say(f"  (b) marketable sell at the go-live minute's open: fill 15:00 UTC, live 16:00 UTC (rule M), exit "
        f"{o.exit_px.iloc[0]} > R1/2 {R}")
    # (c)
    o = o6("NIGHT")
    ob = o6("NIGHT", ex="FLIP_bot")
    g_n = _tmin(pd.Timestamp("2023-03-07 12:00", tz="UTC"))
    assert o.exit_kind.iloc[0] == "marketable" and o.exit_t.iloc[0] == g_n and abs(o.exit_px.iloc[0] - p12) < 1e-12
    assert ob.exit_kind.iloc[0] == "target" and ob.exit_t.iloc[0] == _tmin(pd.Timestamp("2023-03-07 08:00", tz="UTC"))
    assert abs(ob.exit_px.iloc[0] - R) < 1e-12
    say(f"  (c) rule M at night: fill 02:00 New York -> sell live 07:00 New York (12:00 UTC), marketable at "
        f"{p12}; the bot's resting sell fills at R1/2 = {R} at 03:00 New York (gapped above: listed)")
    # (d)
    o = o6("STOP")
    st = rule_m(_tmin(ts_) + 72 * 60)
    assert st == _tmin(stop_t), _mts(st)
    assert o.exit_kind.iloc[0] == "stop" and o.exit_t.iloc[0] == _tmin(stop_t) + 3
    assert abs(o.exit_px.iloc[0] - round(0.97 * L, 2)) < 1e-12
    say(f"  (d) time stop: M(fill + 72 h) = {_mts(st)}; that minute has no trades and the next two are missing: "
        f"sold at the open of {_mts(o.exit_t.iloc[0])}")
    # (e)
    f = k6("OUT")
    assert f.t_F1.iloc[0] == _tmin(tlive), _mts(f.t_F1.iloc[0])
    say("  (e) a zero-trade minute far below L and a missing minute never fill; the first live trigger does")
    # (f)
    f = k6("IDX")
    assert f.t_F1.iloc[0] == _tmin(tf1) and bool(f.idx_missing.iloc[0]), f.T
    assert f.t_F3_1.iloc[0] == _tmin(t12), _mts(f.t_F3_1.iloc[0])
    say("  (f) index: the F1 minute has no index minute (F3-unverifiable flag); an index minute with 20 updates is "
        "an outage; the F3 fill is the next live index minute below L/1.01")
    # (g)
    o = o6("DELIST")
    sg = _segments_from_bars(spec["DELIST"]["m1"], "DELIST", pd.Timestamp(end))
    vw = sg.vwap_last_full_day.iloc[-1]
    assert sg.kind.iloc[-1] == "delisting"
    assert o.exit_kind.iloc[0] == "delist" and abs(o.exit_px.iloc[0] - vw * (1 - HAIRCUT)) < 1e-9, o.T
    assert o.exit_t.iloc[0] == _tmin(pd.Timestamp("2023-03-09", tz="UTC")), _mts(o.exit_t.iloc[0])
    say(f"  (g) delisting inside the flip window: valued at the last full day's VWAP x 0.70 = "
        f"{vw * (1 - HAIRCUT):.4f} at the end of trading")
    # (h)
    f = k6("JUMP")
    assert not len(f), f.T
    say("  (h) a segment boundary during the life cancels the bid: a later wick through L does not fill it")
    # B-ALERT (§10.1): MKT's fill at 15:00 UTC (10:00 EST): rule M buys at the 16:00 UTC open (hiP); +2 h at 17:00
    bm = B[(B.rule == "F1") & B.fill_id.isin(k6("MKT").fill_id)]
    assert abs(bm.alert_M.iloc[0] - (hiP / L - 1)) < 1e-12 and bm.alert_t_M.iloc[0] == golive
    assert abs(bm.alert_2h.iloc[0] - (hiP / L - 1)) < 1e-12
    # NIGHT: the alert buyer (rule M) buys at 12:00 UTC at 1.2 R; after 8 h (15:00 UTC) also 1.2 R
    bn = B[(B.rule == "F1") & B.fill_id.isin(k6("NIGHT").fill_id)]
    assert abs(bn.alert_M.iloc[0] - (p12 / L - 1)) < 1e-12 and bn.alert_t_M.iloc[0] == g_n
    # IDX on the F3 route: the F3 fill at 12:00 UTC (07:00 EST): rule M buys at the 13:00 UTC index open x 1.0095
    bi = B[(B.rule == "F3_1") & B.fill_id.isin(k6("IDX").fill_id)]
    io = float(ix.open[_tmin(ix.open_time) == _tmin(t12) + 60].iloc[0])
    assert abs(bi.alert_M.iloc[0] - (io * (1 + F3_SPREAD) / L - 1)) < 1e-12
    say("  B-ALERT: rule M and fixed delays buy at the first live open (spot: open / L - 1; index route: open x "
        "1.0095 / L - 1)")
    # D12 recovery flags: MKT trades back above R and P0 within 15 minutes; GAP never recovers and falls a further
    # 10% at once; GAP's 30-day horizon runs past the data end (NaN)
    assert bm.rec_R_15m.iloc[0] == 1 and bm["rec_P0_15m"].iloc[0] == 1
    bg = B[(B.rule == "F1") & B.fill_id.isin(k6("GAP").fill_id)]
    assert bg.rec_R_7d.iloc[0] == 0 and bg.rec_dn10_15m.iloc[0] == 1 and np.isnan(bg.rec_R_30d.iloc[0])
    assert bg.rec_dn10_first.isna().iloc[0] or bg.rec_dn10_first.iloc[0] == 1
    say("  D12: recovery flags (R1/2, P0, a further 10% down) per horizon, NaN when the data end first")
    return res


def _m_py(tm: int) -> int:
    """Rule M written a third way (plain datetime + zoneinfo, one minute at a time) for the oracle."""
    import datetime as _dt
    utc = _dt.timezone.utc
    d = _dt.datetime.fromtimestamp(int(tm) * 60, tz=utc).astimezone(NY)
    if 7 * 60 <= d.hour * 60 + d.minute <= 22 * 60 + 59:
        return int(tm) + 60
    day = d.date() if d.hour < 7 else d.date() + _dt.timedelta(days=1)
    loc = _dt.datetime(day.year, day.month, day.day, 7, 0, tzinfo=NY)
    return int(loc.astimezone(utc).timestamp()) // 60


def _t_rule_m(say):
    """rule_m (numba table) against the pandas version and the plain-datetime version, on 200,000 random minutes
    2019-2027 (every DST change) plus the minutes around each change."""
    rng = np.random.default_rng(5)
    a, b = _tmin("2019-01-01"), _tmin("2027-12-31")
    tm = rng.integers(a, b, 200_000)
    edge = []
    for y in range(2019, 2028):
        for d in pd.date_range(f"{y}-03-01", f"{y}-03-15", freq="D").append(pd.date_range(f"{y}-10-28", f"{y}-11-08",
                                                                                         freq="D")):
            base = _tmin(pd.Timestamp(d, tz="UTC"))
            edge.append(np.arange(base, base + DAY_M, 7))
    tm = np.r_[tm, np.concatenate(edge)]
    m1 = rule_m(tm)
    m2 = _tmin(_rule_m_pd(_mts(tm)))
    assert np.array_equal(m1, m2), np.flatnonzero(m1 != m2)[:5]
    sub = tm[rng.choice(len(tm), 3000, replace=False)]
    m3 = np.array([_m_py(x) for x in sub])
    assert np.array_equal(rule_m(sub), m3)
    say(f"  rule M: numba table = pandas tz = plain datetime on {len(tm):,} minutes (DST edges included)")


def _oracle_exit(t, o, h, live, te, T, up, stop_m, bot=False, end_min=None, fac=None, full=False):
    """X-FLIP written separately (plain numpy scans): sell live at M(te) (or te + 1), marketable at the first live
    minute's open if open >= T, else the first later live minute with high >= up (the trade-through price: a fill's
    target plus one tick in decimals, a twin's target + tau) before the stop, else the open of the first live minute
    at or after M(te + stop). T = inf: a hold sold at the first live minute at or after M(te + stop). fac: per bar,
    the units of the bar's asset per unit of the entry asset (a chain of segments; prices compared and returned per
    entry unit). None if censored; full=True returns (price, exit minute, kind)."""
    fac = np.ones(len(t)) if fac is None else fac
    g = te + 1 if bot else _m_py(te)
    S = _m_py(te + stop_m)
    if np.isinf(T):
        g = S
    res = lambda px, k, kind: (float(px), int(t[k]), kind) if full else float(px)
    if end_min is not None and S > end_min:
        return None
    i = int(np.searchsorted(t, g))
    while i < len(t) and not live[i]:
        i += 1
    if i >= len(t):
        return None
    if t[i] >= S:
        return res(o[i] * fac[i], i, "stop")
    tol = lambda f: np.where(f != 1.0, 1.0 - CONV_REL, 1.0)  # converted targets (coding choice 25)
    if o[i] * fac[i] >= T * tol(fac[i]):
        return res(o[i] * fac[i], i, "marketable")
    j = int(np.searchsorted(t, S))
    w = np.flatnonzero(live[i:j] & (h[i:j] * fac[i:j] >= up * tol(fac[i:j])))
    if len(w):
        return res(T, i + int(w[0]), "target")
    while j < len(t) and not live[j]:
        j += 1
    return res(o[j] * fac[j], j, "stop") if j < len(t) else None


def _half_retrace(L: float, P0: float, tick: str, plus: int = 0) -> float:
    """R1/2 = ceil(L + (P0 - L) / 2) on the tick in exact decimals of the prices' shortest strings (the oracle's);
    plus = 1: the next tick above it (the trade-through price of K5, high >= R1/2 + tau on decimal prices)."""
    from decimal import Decimal, ROUND_CEILING
    x = (Decimal(repr(float(L))) + Decimal(repr(float(P0)))) / 2
    q = (x / Decimal(tick)).to_integral_value(rounding=ROUND_CEILING)
    return float((q + plus) * Decimal(tick))


def _chain_bars(W: dict, coin: str) -> dict:
    """Separate code for the oracles (§4.1, coding choice 6): the 1m bars a position in `coin` can trade on, in time
    order: the coin's own bars (seg >= 0), then, after a swap, the successor's bars after the coin's last trade. Per
    bar: fac = units of the bar's asset per unit of the coin's first asset (a joined redenomination or a jump changes
    the units by the segments table's `units`, a swap by the swap units), own (the coin's bar), seg (the coin's
    segment id; -1 on a successor's bars) and chain (the bar is reachable from the coin's first segment: every
    boundary before it continues). Reads only the injected frames: m1, segments (when given; else one segment) and
    successor."""
    fr = W["coins"][coin]
    k = fr["m1"].sort_values("open_time", kind="stable")
    sg = k["seg"].to_numpy() if "seg" in k else np.zeros(len(k), np.int64)
    k, sg = k[sg >= 0], sg[sg >= 0]
    t = _tmin(k.open_time)
    rows = fr.get("segments")
    tab = {int(r.seg): r for r in rows.itertuples(index=False)} if rows is not None else {}
    fac = np.ones(len(t))
    chain = np.ones(len(t), bool)
    u, ok = 1.0, True
    ids = list(pd.unique(sg))
    for n, s_ in enumerate(ids):
        m = sg == s_
        fac[m], chain[m] = u, ok
        r = tab.get(int(s_))
        if n < len(ids) - 1:
            if rows is None:                         # no table: trading on the next UTC day continues (a jump)
                nxt_day = int(t[sg == ids[n + 1]][0]) // DAY_M
                if nxt_day - int(t[m][-1]) // DAY_M > 1:
                    ok = False
            elif r is not None and bool(r.continues) and str(r.kind) != "swap":
                u = u * float(r.units)
            else:
                ok = False
    parts = [dict(t=t, o=k.open.to_numpy(float), h=k.high.to_numpy(float), l=k.low.to_numpy(float),
                  live=k.trades.to_numpy() > 0, fac=fac, own=np.ones(len(t), bool), seg=sg.astype(np.int64),
                  chain=chain)]
    last = tab.get(int(ids[-1])) if ids else None
    succ, units = None, None
    if last is not None and str(last.kind) == "swap" and bool(last.continues):
        succ, units = str(last.successor), float(last.units)
    elif fr.get("successor") is not None and rows is None:
        succ, units = fr["successor"]
    if succ is not None and succ in W["coins"] and ok:
        t_last = int(t[k.trades.to_numpy() > 0][-1])
        s2 = _chain_bars(W, succ)
        keep = s2["t"] > t_last
        parts.append(dict(t=s2["t"][keep], o=s2["o"][keep], h=s2["h"][keep], l=s2["l"][keep],
                          live=s2["live"][keep], fac=u * units * s2["fac"][keep], own=np.zeros(int(keep.sum()), bool),
                          seg=np.full(int(keep.sum()), -1, np.int64), chain=s2["chain"][keep]))
    return {key: np.concatenate([p_[key] for p_ in parts]) for key in parts[0]}


def _oracle_program(W: dict, res: dict, stop_m: int = FLIP_STOP_H * 60, hold: bool = False) -> pd.DataFrame:
    """The K1 oracle (V1), separate code: per engine bid, the F1 fill (first live minute of the life, in the bid's
    segment, with low <= L - tau), the X-FLIP exit (rule M, R1/2; hold=True: X-HOLD with stop_m = h) along the
    coin's chain of segments (_chain_bars), r before costs and at C-RH, and the mean of 100 twins drawn from the
    coin's eligible minutes (its own live bars in member months, outside +-182 days, complete window) with the same
    seeds and the same exit rule. x_t: the exit minute; cross: the exit lies beyond the fill's segment."""
    end_min = _tmin(pd.Timestamp(W["end"]) + pd.Timedelta("1D")) - 1
    bids = res["bids"]
    fills = res["fills"]
    fid = dict(zip(fills.bid_id, fills.fill_id))
    u = W["universe"]
    mem = {c: np.array([_month_int(x) for x in g.month.astype(str)], np.int64)
           for c, g in u[u["U_Q1"].astype(bool)].groupby("coin")}
    rows = []
    arrs = {c: _chain_bars(W, c) for c in bids.coin.unique()}
    # cutoff: the last entry minute whose time stop is inside the data
    lo, hi = end_min - stop_m - 5 * DAY_M, end_min
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _m_py(mid + stop_m) <= end_min:
            lo = mid
        else:
            hi = mid
    cut = lo
    for b in bids.itertuples():
        A = arrs[b.coin]
        t, o, h, l, live, fac, own, sg = (A[x] for x in ("t", "o", "h", "l", "live", "fac", "own", "seg"))
        d0 = int(b.t0) // DAY_M - 1
        on_d0 = np.flatnonzero(own & (t // DAY_M == d0))
        if not len(on_d0):
            continue
        s_bid = sg[on_d0[-1]]
        a = int(np.searchsorted(t, b.live_from))
        e = int(np.searchsorted(t, b.life_end))
        w = np.flatnonzero(live[a:e] & (l[a:e] <= b.L_tau) & own[a:e] & (sg[a:e] == s_bid))
        if not len(w):
            continue
        i = a + int(w[0])
        m = int(t[i])
        R = np.inf if hold else _half_retrace(b.L, b.P0, b.tick_str)
        up = np.inf if hold else _half_retrace(b.L, b.P0, b.tick_str, plus=1)
        x = _oracle_exit(t, o, h, live, m, R, up, stop_m, end_min=end_min, fac=fac / fac[i], full=True)
        row = dict(bid_id=b.bid_id, coin=b.coin, t_F1=m, r0=np.nan, rRH=np.nan, twin0=np.nan, own=False, x_t=-1,
                   cross=False, twin_cross=0)
        if x is not None:
            row["r0"] = x[0] / b.L - 1
            row["rRH"] = x[0] * (1 - C_RH) / (b.L * (1 + C_RH)) - 1
            row["x_t"] = x[1]
            j = int(np.searchsorted(t, x[1]))
            row["cross"] = bool(not own[j] or sg[j] != s_bid)
        f = fid.get(b.bid_id)
        if f is not None:
            el = np.flatnonzero(own & live & (t <= cut) & np.isin(_month_of_min(t), mem.get(b.coin, [])) &
                                ((t < m - EXCL_DAYS * DAY_M) | (t > m + EXCL_DAYS * DAY_M)))
            days = len(np.unique(t[el] // DAY_M))
            if days >= POOL_MIN_DAYS:
                uu = np.random.default_rng(SEED + int(f)).random(R_TWINS)
                kk = np.minimum((uu * len(el)).astype(np.int64), len(el) - 1)
                vals = []
                for j in el[kk]:
                    Tw = np.inf if hold else o[j] * (R / b.L)
                    xe = _oracle_exit(t, o, h, live, int(t[j]), Tw, Tw + b.tick, stop_m, end_min=end_min,
                                      fac=fac / fac[j], full=True)
                    vals.append(xe[0] / o[j] - 1)
                    jx = int(np.searchsorted(t, xe[1]))
                    row["twin_cross"] += int(not own[jx] or sg[jx] != sg[j])
                row["twin0"] = float(np.mean(vals))
                row["own"] = True
        rows.append(row)
    return pd.DataFrame(rows)


def _t_oracle(say):
    """K1b-type known answer (V1): on a synthetic martingale with market-wide jumps that gap through the bids and do
    not revert, the engine's fills, exits, r_f and twin means equal a separately coded oracle; the two wrong engines
    (fill booked at the fill minute's close / low) differ from it."""
    W = synth_world(n_coins=3, days=640, seed=11, jumps_per_year=9, jump_size=-0.30)
    cfg = dict(rules=("F1",), exits={"F1": (FLIP,)}, twin_sens=False, drift=False, verbose=False, mw=False)
    t = time.time()
    res = run_program("P1", "U_Q1", data=W, cfg=cfg)
    te = time.time() - t
    orc = _oracle_program(W, res)
    F = res["fills"]
    O = res["outcomes"]
    assert set(orc.bid_id) == set(F.bid_id), "fill sets differ"
    m = orc.merge(F[["bid_id", "fill_id", "t_F1"]], on="bid_id", suffixes=("_o", ""))
    assert (m.t_F1_o == m.t_F1).all(), "fill minutes differ"
    e0 = O[(O.cost == "C-0")].set_index("fill_id")
    eR = O[(O.cost == "C-RH")].set_index("fill_id")
    m["r0_e"] = e0.r.reindex(m.fill_id).to_numpy()
    m["rRH_e"] = eR.r.reindex(m.fill_id).to_numpy()
    m["tw_e"] = e0.twin_mean.reindex(m.fill_id).to_numpy()
    m["pooled_e"] = e0.twin_pooled.reindex(m.fill_id).to_numpy()
    ok = m.r0.notna()
    assert np.allclose(m.r0[ok], m.r0_e[ok], rtol=0, atol=1e-12), (m.r0 - m.r0_e).abs().max()
    assert np.allclose(m.rRH[ok], m.rRH_e[ok], rtol=0, atol=1e-12)
    own = m.own & ok
    assert (~m.pooled_e[own].astype(bool)).all()
    assert np.allclose(m.twin0[own], m.tw_e[own], rtol=0, atol=1e-12), (m.twin0[own] - m.tw_e[own]).abs().max()
    n = int(ok.sum())
    r = m.r0[ok].to_numpy()
    se = r.std(ddof=1) / math.sqrt(n)
    d = (m.r0 - m.twin0)[own].to_numpy()
    say(f"  oracle (K1b-type, non-reverting gap-through jumps): {n} fills on {len(W['coins'])} coins, engine = oracle "
        f"fill by fill (minutes, r before costs and at C-RH, twin means of {int(own.sum())} own-twin fills, |diff| "
        f"<= 1e-12); oracle mean r_f {r.mean():+.4f} (SE {se:.4f}), mean delta {d.mean():+.4f}; engine {te:.0f}s")
    # the same run in two processes gives the same tables
    r2 = run_program("P1", "U_Q1", data=W, cfg=dict(cfg, n_jobs=2))
    for k in ("bids", "fills", "outcomes", "bench"):
        assert res[k].reset_index(drop=True).equals(r2[k].reset_index(drop=True)), f"n_jobs changes {k}"
    say("  n_jobs=2 (spawned processes) gives identical bids, fills, outcomes and benchmarks")
    # the seed's fill index does not depend on the other rules run (review finding 4): add F2 and F5, with a
    # perpetual-only wick (an F5-only fill early in the sample), and compare every F1 fill's index, r and twin mean
    W5 = dict(W, coins={c: dict(fr) for c, fr in W["coins"].items()})
    pp = W5["coins"]["SYN0"]["perp_m1"].copy()
    ip = int(np.searchsorted(_tmin(pp.open_time), _tmin("2020-03-03 12:00")))
    pp.loc[ip, "low"] = pp.loc[ip, "low"] * 0.5
    W5["coins"]["SYN0"]["perp_m1"] = pp
    r5 = run_program("P1", "U_Q1", data=W5, cfg=dict(cfg, rules=("F1", "F2", "F5")))
    F5 = r5["fills"]
    assert ((F5.t_F1 < 0) & (F5.t_F5 >= 0)).any(), "no F5-only fill"
    key = ["coin", "t0", "rung"]
    pick = lambda R_, Fr: R_[(R_.rule == "F1") & (R_.cost == "C-RH")].merge(Fr[["fill_id", "t0", "rung"]],
                                                                          on="fill_id").set_index(key).sort_index()
    a1, a5 = pick(O, F), pick(r5["outcomes"], F5)
    assert a1.index.equals(a5.index) and (a1.fill_id == a5.fill_id).all(), "fill index moved"
    assert np.allclose(a1.twin_mean, a5.twin_mean, rtol=0, atol=0, equal_nan=True), "twin means moved"
    say(f"  fill index: adding F2 and F5 (with {int(((F5.t_F1 < 0) & (F5.t_F5 >= 0)).sum())} F5-only fill) leaves "
        f"all {len(a1)} F1 fills' indices and twin means unchanged")
    # the two wrong engines
    for fp in ("close", "low"):
        rw = run_program("P1", "U_Q1", data=W, cfg=dict(cfg, fill_price=fp))
        ow = rw["outcomes"]
        ow = ow[ow.cost == "C-0"].set_index("fill_id")
        rr = ow.r.reindex(m.fill_id[ok]).to_numpy()
        dd = rr - r
        tstat = dd.mean() / (dd.std(ddof=1) / math.sqrt(len(dd)))
        assert dd.mean() > 0.01 and tstat > 4, (fp, dd.mean(), tstat)
        say(f"  wrong engine (fill booked at the minute's {fp}): mean r_f {rr.mean():+.4f}, {dd.mean():+.4f} above "
            f"the oracle (paired t {tstat:.1f}): it fails the known answer")
    return res


def _t_tick(say):
    """The spot sell trigger 'high >= R1/2 + tau' on decimal prices (§8, K5; review finding 2): on a target whose
    float sum dbl(R) + dbl(tau) lies above dbl(R + tau), a minute whose high prints exactly one tick through R1/2
    fills the target (the engine uses the decimal next tick); the K5 audit (raise) accepts it."""
    tick, tk = "0.01", 0.01
    t0 = pd.Timestamp("2023-03-06 03:30", tz="UTC")
    d0 = pd.Timestamp("2023-03-05", tz="UTC")
    end, tend = "2023-03-20", pd.Timestamp("2023-03-21", tz="UTC")
    for P0 in np.round(np.arange(100.0, 160.0, 0.37), 2):
        d1h = _hist_d1(d0, float(P0), 0.03)
        m1 = _flat_m1(d0, tend, float(P0), tick)
        d1 = pd.concat([d1h.iloc[:-1], _daily_from_m1(m1)], ignore_index=True)
        spec = {"X": {"m1": m1, "d1": d1, "tick": tick, "_months": ["2023-03"]}}
        W = _hb_world(spec, end)
        I = sbl.inputs_at("X", t0, data=World(W).levels_data("X"))
        info = sbl.level_info("M2", I, k=6.0)
        L, Lt = float(info["L"]), sbl.tick_value(info["n_ticks"] - 1, tick)
        R = sbl.ceil_tick(L + 0.5 * (I["P0"] - L), tick)
        up = sbl.tick_value(sbl.ceil_n(R, tick) + 1, tick)
        if R + tk > up:
            break
    else:
        raise AssertionError("no target with a float sum above the next tick")
    tf, tx = pd.Timestamp("2023-03-06 15:00", tz="UTC"), pd.Timestamp("2023-03-07 12:00", tz="UTC")
    _set(m1, tf, low=Lt - tk)
    p = round(0.95 * L, 2)
    after = m1.open_time > tf
    m1.loc[after, ["open", "close"]] = p
    m1.loc[after, "high"] = round(p + tk, 2)
    m1.loc[after, "low"] = round(p - tk, 2)
    _set(m1, tx, high=float(f"{up:.2f}"))                          # exactly one tick through R1/2, as printed
    spec["X"]["d1"] = pd.concat([d1h.iloc[:-1], _daily_from_m1(m1)], ignore_index=True)
    res = run_program("P1", "U_Q1", data=W, cfg=dict(rules=("F1",), exits={"F1": (FLIP,)}, twin_sens=False,
                                                     drift=False, verbose=False, mw=False, audit="raise"))
    F, O = res["fills"], res["outcomes"]
    f = F[(F.rung == 6.0) & (F.t0 == _tmin(t0))]
    o = O[O.fill_id.isin(f.fill_id) & (O.exit == "FLIP") & (O.cost == "C-0")]
    assert len(f) == 1 and f.t_F1.iloc[0] == _tmin(tf) and float(o.target.iloc[0]) == R, (f.T, o.T)
    assert o.exit_kind.iloc[0] == "target" and o.exit_t.iloc[0] == _tmin(tx) and o.exit_px.iloc[0] == R, o.T
    say(f"  one-tick trade-through: R1/2 {R!r} + tau as a float sum {R + tk!r} > the printed next tick {up!r}; the "
        f"minute with high {up} fills the target at {_mts(int(o.exit_t.iloc[0]))} (K5 clean)")


def _t_chain(say):
    """Positions crossing segment boundaries (§4.1, coding choice 6; review finding 1): hand-built paths whose rule-M
    go-live, X-FLIP time stop, resting-target hit, X-HOLD-7 horizon, D12 hits and B-ALERT buys fall in a later
    segment of the chain, up to two segments after the fill: RD* join a redenomination (prices x1000, 0.001 new per
    old) on Tuesday and a -30% jump (units 1) on Wednesday; SW* swap on Thursday to a successor at 10 units per unit.
    Known answers by construction, the chain oracle (separate code) and the K5 audit (raise) agree."""
    tick, tk = "0.01", 0.01
    t0 = pd.Timestamp("2023-03-06 03:30", tz="UTC")                 # Monday; US DST starts 2023-03-12
    d0 = pd.Timestamp("2023-03-05", tz="UTC")
    end, tend = "2023-03-20", pd.Timestamp("2023-03-21", tz="UTC")
    ts = lambda x: pd.Timestamp(x, tz="UTC")
    b1, b2, tsw = ts("2023-03-07"), ts("2023-03-08"), ts("2023-03-09")
    d1h = _hist_d1(d0, 100.0, 0.03)

    def frames(m1, extra=None, months=("2023-03",)):
        d1 = pd.concat([d1h.iloc[:-1], _daily_from_m1(m1)], ignore_index=True)
        fr = {"m1": m1, "d1": d1, "tick": tick, "_months": list(months)}
        fr.update(extra or {})
        return fr

    def flat(m1, a, b, px):
        sel = ((m1.open_time >= a) & (m1.open_time < b)).to_numpy()
        m1.loc[sel, ["open", "close"]] = px
        m1.loc[sel, "high"] = round(px + tk, 2)
        m1.loc[sel, "low"] = round(px - tk, 2)

    probe = _flat_m1(d0, tend, 100.0, tick)
    I = sbl.inputs_at("P", t0, data=World(_hb_world({"P": frames(probe)}, end)).levels_data("P"))
    info = sbl.level_info("M2", I, k=6.0)
    L, Lt = float(info["L"]), sbl.tick_value(info["n_ticks"] - 1, tick)
    R = sbl.ceil_tick(L + 0.5 * (I["P0"] - L), tick)
    p95 = round(0.95 * L, 2)
    p66 = round(0.7 * p95, 2)
    p60 = round(0.9 * p66, 2)
    q = round(1.05 * R, 2)
    n80, n70, nq = round(0.8 * p95 / 10, 2), round(0.7 * p95 / 10, 2), round(1.05 * R / 10, 2)
    rd_seg = pd.DataFrame([dict(seg=0, kind="redenomination", continues=True, units=0.001, successor=""),
                           dict(seg=1, kind="jump", continues=True, units=1.0, successor=""),
                           dict(seg=2, kind="data_end", continues=True, units=1.0, successor="")])

    def rd(fill_at, path):
        m1 = _flat_m1(d0, tend, 100.0, tick)
        _set(m1, fill_at, low=Lt - tk)
        for a, b, px in path:
            flat(m1, a, b, px)
        new = (m1.open_time >= b1).to_numpy()
        for c in ("open", "high", "low", "close"):
            m1.loc[new, c] = np.round(m1.loc[new, c].to_numpy() * 1000.0, 2)
        m1.loc[new, "volume"] = m1.loc[new, "volume"] / 1000.0
        m1["seg"] = np.where(m1.open_time >= b2, 2, np.where(new, 1, 0)).astype(np.int32)
        return frames(m1, {"segments": rd_seg})

    def sw(name, fill_at, path_old, path_new):
        m1 = _flat_m1(d0, tsw, 100.0, tick)                          # last trade Wednesday 23:59
        _set(m1, fill_at, low=Lt - tk)
        for a, b, px in path_old:
            flat(m1, a, b, px)
        n1 = _flat_m1(tsw, tend, 10.0, tick)
        for a, b, px in path_new:
            flat(n1, a, b, px)
        return {name: frames(m1, {"successor": (name + "N", 10.0)}), name + "N": {"m1": n1, "tick": tick,
                                                                                  "_months": []}}

    f15, f2310 = ts("2023-03-06 15:00"), ts("2023-03-06 23:10")
    spec = {"RDS": rd(f15, [(f15 + pd.Timedelta("1min"), b2, p95), (b2, ts("2023-03-09"), p66),
                            (ts("2023-03-09"), tend, p60)]),
            "RDT": rd(f15, [(f15 + pd.Timedelta("1min"), b2, p95), (b2, ts("2023-03-08 10:00"), p66),
                            (ts("2023-03-08 10:00"), tend, q)]),
            "RDG": rd(f2310, [(f2310 + pd.Timedelta("1min"), b1, p95), (b1, tend, q)])}
    spec.update(sw("SWS", f15, [(f15 + pd.Timedelta("1min"), tsw, p95)],
                   [(tsw, ts("2023-03-09 12:00"), n80), (ts("2023-03-09 12:00"), tend, n70)]))
    spec.update(sw("SWT", f15, [(f15 + pd.Timedelta("1min"), tsw, p95)],
                   [(tsw, ts("2023-03-09 10:00"), n80), (ts("2023-03-09 10:00"), tend, nq)]))
    W = _hb_world(spec, end)
    hold7 = EXIT_SPECS["HOLD7"]
    res = run_program("P1", "U_Q1", data=W, cfg=dict(rules=("F1",), exits={"F1": (FLIP, hold7)}, twin_sens=False,
                                                     drift=False, verbose=False, mw=False, audit="raise"))
    F, O, B = res["fills"], res["outcomes"], res["bench"]
    k6 = lambda c: F[(F.coin == c) & (F.rung == 6.0) & (F.t0 == _tmin(t0))]
    o6 = lambda c, ex="FLIP": O[O.fill_id.isin(k6(c).fill_id) & (O.exit == ex) & (O.cost == "C-0")].iloc[0]
    b6 = lambda c: B[B.fill_id.isin(k6(c).fill_id) & (B.rule == "F1")].iloc[0]
    close = lambda a, b: abs(a - b) <= 1e-9 * max(1.0, abs(b))
    for c in ("RDS", "RDT", "SWS", "SWT"):
        assert len(k6(c)) == 1 and k6(c).t_F1.iloc[0] == _tmin(f15), (c, k6(c).T)
    assert len(k6("RDG")) == 1 and k6("RDG").t_F1.iloc[0] == _tmin(f2310)
    stop = _tmin(ts("2023-03-09 16:00"))                            # M(Mon 15:00 + 72 h): Thursday 11:00 EST
    hz7 = _tmin(ts("2023-03-13 16:00"))                             # M(Mon 15:00 + 7 d): Monday 12:00 EDT
    expect = [("RDS", "FLIP", "stop", stop, p60), ("RDS", "HOLD7", "stop", hz7, p60),
              ("RDT", "FLIP", "target", _tmin(ts("2023-03-08 10:00")), R),
              ("RDG", "FLIP", "marketable", _tmin(ts("2023-03-07 00:10")), q),
              ("SWS", "FLIP", "stop", stop, n70 * 10), ("SWS", "HOLD7", "stop", hz7, n70 * 10),
              ("SWT", "FLIP", "target", _tmin(ts("2023-03-09 10:00")), R)]
    for c, ex, kind, tx, px in expect:
        o = o6(c, ex)
        assert o.exit_kind == kind and o.exit_t == tx and close(o.exit_px, px), (c, ex, o.exit_kind, _mts(o.exit_t),
                                                                                 o.exit_px, kind, _mts(tx), px)
        assert close(o.r, px / L - 1), (c, ex, o.r, px / L - 1)
    # B-ALERT on RDS: rule M and +2 / +8 h in the fill's segment, +24 h one segment later, +72 h two segments later
    bs = b6("RDS")
    for k_, tx, px in (("M", "2023-03-06 16:00", p95), ("2h", "2023-03-06 17:00", p95), ("8h", "2023-03-06 23:00", p95),
                       ("24h", "2023-03-07 15:00", p95), ("72h", "2023-03-09 15:00", p60)):
        assert bs[f"alert_t_{k_}"] == _tmin(ts(tx)) and close(bs[f"alert_{k_}"], px / L - 1), (k_, bs[f"alert_t_{k_}"])
    bw = b6("SWS")
    assert bw.alert_t_72h == _tmin(ts("2023-03-09 15:00")) and close(bw.alert_72h, n70 * 10 / L - 1)
    # D12 along the chain: RDT trades back to R1/2 43 h after the fill (two segments on); RDS falls a further 10%
    bt = b6("RDT")
    assert bt.rec_R_24h == 0 and bt.rec_R_72h == 1 and bs.rec_dn10_24h == 0 and bs.rec_dn10_72h == 1
    # the chain oracle (separate code) on every fill
    for spec_, kw in ((FLIP, {}), (hold7, dict(stop_m=hold7.stop_m, hold=True))):
        orc = _oracle_program(W, res, **kw).merge(F[["bid_id", "fill_id"]], on="bid_id")
        e = O[(O.exit == spec_.name) & (O.cost == "C-0")].set_index("fill_id").reindex(orc.fill_id)
        assert np.array_equal(orc.x_t.to_numpy(), e.exit_t.to_numpy()), spec_.name
        assert np.allclose(orc.r0.to_numpy(), e.r.to_numpy(), rtol=0, atol=1e-9, equal_nan=True), spec_.name
    say(f"  chains: X-FLIP stops, targets and a rule-M go-live, X-HOLD-7, D12 hits and B-ALERT buys one and two "
        f"segments after the fill (redenomination x1000 + jump; swap at 10 per unit) at their known prices and minutes "
        f"(e.g. RDS stop {_mts(stop)} at {p60} per old unit, RDT target {R} two segments on, alert +72 h {p60}); "
        f"chain oracle and K5 agree")


def _t_chain_oracle(say):
    """Many positions across boundaries (review finding 1): a synthetic coin OLD joins a redenomination (x100, units
    0.01) and a -35% jump (units 1) and swaps to NEW (10 per unit), with market-wide gaps 30 h before each boundary.
    Every fill's X-FLIP and X-HOLD-7 exit and every own twin's mean equal the chain oracle (separate code: _chain_bars,
    _oracle_exit); the K5 audit (raise) passes."""
    DAY = DAY_M
    n_old, b_red, b_jump = 900 * DAY, 301 * DAY, 601 * DAY              # Wed 2020-10-28, Tue 2021-08-24, Sun 2022-06-19
    rng = np.random.default_rng(61)
    jumps = [(b - h * 60, -0.30) for b in (b_red, b_jump, n_old) for h in (30, 100)] + [(b_jump, -0.35)]
    jumps += [(int(x), -0.28) for x in rng.integers(60 * DAY, n_old - 2 * DAY, 10)]
    k_old = synth_coin("2020-01-01", 900, 611, p0=20.0, jumps=jumps, seg_breaks=(b_red, b_jump))
    red = (k_old.seg.to_numpy() >= 1)
    for c in ("open", "high", "low", "close"):
        k_old.loc[red, c] = np.round(k_old.loc[red, c].to_numpy() * 100.0, 2)
    k_old.loc[red, "volume"] = k_old.loc[red, "volume"] / 100.0
    k_new = synth_coin("2022-06-19", 190, 612, p0=float(k_old.close.iloc[-1]) / 10.0)
    seg_old = pd.DataFrame([dict(coin="OLD", seg=0, kind="redenomination", continues=True, units=0.01, successor=""),
                            dict(coin="OLD", seg=1, kind="jump", continues=True, units=1.0, successor=""),
                            dict(coin="OLD", seg=2, kind="swap", continues=True, units=10.0, successor="NEW")])
    seg_new = pd.DataFrame([dict(coin="NEW", seg=0, kind="data_end", continues=True, units=1.0, successor="")])
    months = pd.period_range("2020-01", "2022-06", freq="M").strftime("%Y-%m")
    W = {"universe": pd.DataFrame([dict(month=m, coin="OLD", U_Q1=True, U_B=True) for m in months]),
         "coins": {"OLD": {"m1": k_old, "tick": "0.0001", "segments": seg_old},
                   "NEW": {"m1": k_new, "tick": "0.0001", "segments": seg_new}}, "end": "2022-12-25", "tbill": 0.0}
    hold7 = EXIT_SPECS["HOLD7"]
    res = run_program("P1", "U_Q1", data=W, cfg=dict(rules=("F1",), exits={"F1": (FLIP, hold7)}, twin_sens=False,
                                                     drift=False, verbose=False, mw=False, audit="raise"))
    F, O = res["fills"], res["outcomes"]
    bnd = [_tmin(pd.Timestamp("2020-01-01", tz="UTC")) + x for x in (b_red, b_jump, n_old)]
    crossed = np.zeros(3, int)
    n_tw = n_own = 0
    for spec_, kw in ((FLIP, {}), (hold7, dict(stop_m=hold7.stop_m, hold=True))):
        orc = _oracle_program(W, res, **kw)
        assert set(orc.bid_id) == set(F.bid_id), "fill sets differ"
        m = orc.merge(F[["bid_id", "fill_id", "t_F1"]], on="bid_id", suffixes=("_o", ""))
        assert (m.t_F1_o == m.t_F1).all(), "fill minutes differ"
        e = O[(O.exit == spec_.name) & (O.cost == "C-0")].set_index("fill_id").reindex(m.fill_id)
        ok = m.r0.notna().to_numpy()
        assert np.array_equal(m.x_t.to_numpy()[ok], e.exit_t.to_numpy()[ok]), spec_.name
        assert np.allclose(m.r0[ok], e.r.to_numpy()[ok], rtol=0, atol=1e-9), spec_.name
        own = m.own.to_numpy() & ok
        assert (~e.twin_pooled.to_numpy()[own].astype(bool)).all()
        assert np.allclose(m.twin0[own], e.twin_mean.to_numpy()[own], rtol=0, atol=1e-9), \
            (spec_.name, float(np.abs(m.twin0[own] - e.twin_mean.to_numpy()[own]).max()))
        for j, tb in enumerate(bnd):
            crossed[j] += int(((m.t_F1 < tb) & (m.x_t >= tb) & ok).sum())
        n_tw += int(m.twin_cross[own].sum())
        n_own += int(own.sum())
    assert (crossed > 0).all() and n_tw >= 50, (crossed, n_tw)
    say(f"  chain oracle: {len(F)} fills on a coin with a redenomination, a jump and a swap: fills' X-FLIP and "
        f"X-HOLD-7 exits and own-twin means ({n_own} fill-exits) equal the oracle (|diff| <= 1e-9); positions across "
        f"the redenomination / jump / swap: {crossed[0]} / {crossed[1]} / {crossed[2]} fills, {n_tw} own twins; "
        f"K5 clean")


def _t_seg_derive(say):
    """Injected 1m bars without `seg` (review finding 7) get §4.1 boundaries by stinkbid_data's daily rule: a 3-day
    trading gap (with a -55% reopening) starts a new segment, a gap, i.e. a delisting at the gap, so a bid placed
    before it is cancelled and never fills on the reopening print; a -40% open jump between two traded days starts a
    joined segment (a jump)."""
    DAY = DAY_M
    gap_a, gap_b = 153 * DAY, 156 * DAY                  # no bars 2020-06-02 .. 06-04 (Tue-Thu)
    k = synth_coin("2020-01-01", 300, 123, p0=10.0, jumps=[(gap_b, -0.55), (230 * DAY, -0.40)],
                   missing=[(gap_a, gap_b)]).drop(columns=["seg"])
    months = pd.period_range("2020-01", "2020-10", freq="M").strftime("%Y-%m")
    W = {"universe": pd.DataFrame([dict(month=m, coin="G", U_Q1=True, U_B=True) for m in months]),
         "coins": {"G": {"m1": k, "tick": "0.0001"}}, "end": "2020-10-26", "tbill": 0.0}
    sg = World(W).segments("G")
    assert sg.kind.tolist() == ["gap", "jump", "data_end"], sg.kind.tolist()
    res = run_program("P1", "U_Q1", data=W, cfg=dict(rules=("F1",), exits={"F1": (FLIP,)}, twin_sens=False,
                                                     drift=False, verbose=False, mw=False, audit="raise"))
    F = res["fills"]
    wk = F[(F.t0 == _tmin("2020-06-01 03:30")) & (F.t_F1 >= 0)]
    assert not (wk.t_F1 >= _tmin("2020-06-05")).any(), wk.T
    jb = res["bids"]
    assert len(jb[jb.t0 == _tmin("2020-08-17 03:30")]) == 3, "no bids the Monday before the jump"
    jw = F[(F.t0 == _tmin("2020-08-17 03:30")) & (F.t_F1 >= _tmin("2020-08-18"))]
    assert not len(jw), jw.T
    say(f"  injected bars without seg: segments derived as {sg.kind.tolist()}; the bids placed before the 3-day gap "
        f"and before the jump are cancelled at those boundaries (no fill on the reopening prints)")


def _t_stream_cache(say):
    """The stream cache (coding choice 26; review finding 9): a streamed coin's frame is fetched once and read back
    identical by later passes; nothing is kept when the free-disk floor would be crossed; drop removes the file."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix=".selftest_", dir=sbd.OUT if sbd.OUT.exists() else None) as d:
        calls = []
        k = synth_coin("2020-01-01", 3, 5)

        def fetch():
            calls.append(1)
            return k
        sc = _StreamCache(d, min_free=0.0)
        a, b = sc.get("X", fetch), sc.get("X", fetch)
        assert len(calls) == 1 and a is k and sc.files() == {"X"}
        pd.testing.assert_frame_equal(b, k)
        sc.drop("X")
        assert not sc.files()
        sc2 = _StreamCache(d, min_free=1e18)
        sc2.get("Y", fetch)
        assert len(calls) == 2 and not sc2.files()
    say("  stream cache: a streamed frame is fetched once and read back identical; none kept below the free-disk "
        "floor; dropped after use")


def _t_twins(say):
    """B-TWIN eligibility (§10.1): every own twin is a live minute of the coin, in a member month, outside +-182 days
    of the fill, with its whole exit window inside the data; draws are uniform over the eligible minutes; a coin with
    fewer than 182 eligible days gets pooled twins from the U-Q1 coins' eligible minutes; a twin window cut short by
    a delisting is kept and closed at the §4.1 value."""
    W = synth_world(n_coins=2, days=820, seed=21, jumps_per_year=8, jump_size=-0.3)
    rng = np.random.default_rng(3)
    # membership: SYN0 every month except every third; SYN1 every month; NEW only its last 4 months; DEAD delists
    months = pd.period_range("2020-01", W["end"][:7], freq="M").strftime("%Y-%m")
    u = W["universe"]
    u = u[~((u.coin == "SYN0") & (u.month.isin(months[::3])))]
    k_new = synth_coin("2020-01-01", 820, 77, p0=5.0, jumps=[(int(x), -0.3) for x in
                                                              rng.integers(700 * DAY_M, 815 * DAY_M, 3)])
    k_dead = synth_coin("2020-01-01", 820, 78, p0=7.0, end_at=600 * DAY_M,
                        jumps=[(int(x), -0.3) for x in rng.integers(100 * DAY_M, 590 * DAY_M, 6)])
    W["coins"]["NEW"] = {"m1": k_new, "tick": "0.0001"}
    W["coins"]["DEAD"] = {"m1": k_dead, "tick": "0.0001"}
    rows = [dict(month=m, coin="NEW", U_Q1=True, U_B=True) for m in months[-4:]]
    rows += [dict(month=m, coin="DEAD", U_Q1=True, U_B=True) for m in months[:20]]
    W["universe"] = pd.concat([u, pd.DataFrame(rows)], ignore_index=True)
    cfg = dict(rules=("F1",), exits={"F1": (FLIP, EXIT_SPECS["HOLD90"])}, twin_sens=False, drift=False,
               verbose=False, mw=False, keep_twins=True)
    res = run_program("P1", "U_Q1", data=W, cfg=cfg)
    world = World(W)
    mem = world.members("U_Q1")
    end_min = world.end_min
    n_own = n_pool = n_dl = 0
    for x in res["twins"]:
        sp = EXIT_SPECS[x["spec"]]
        te, tau = np.asarray(x["te"]), np.asarray(x["tau_fill"])
        coin = x["coin"]
        k = W["coins"][coin]["m1"]
        tt = _tmin(k.open_time)
        i = np.searchsorted(tt, te)
        assert np.all(tt[i] == te) and np.all(k.trades.to_numpy()[i] > 0), "twin entry not a live minute"
        assert np.all(np.isin(_month_of_min(te), mem[coin])), "twin outside the universe's months"
        if x["pooled"]:
            # pooled twins exclude whole days touching [tau - 182 d, tau + 182 d] (coding choice 15)
            assert np.all((te // DAY_M < (tau - EXCL_DAYS * DAY_M) // DAY_M) |
                          (te // DAY_M > (tau + EXCL_DAYS * DAY_M) // DAY_M))
            n_pool += len(te)
        else:
            assert np.all(np.abs(te - tau) > EXCL_DAYS * DAY_M), "twin inside +-182 days"
            n_own += len(te)
        assert np.all(_horizon(sp, te) <= end_min), "twin window not complete"
        dl = x["kind"] == EK_DELIST
        n_dl += int(dl.sum())
        if dl.any():
            sg = _segments_from_bars(k, coin, world.end_day)
            v = sg.vwap_last_full_day.iloc[-1] * (1 - HAIRCUT)
            assert np.allclose(x["px"][dl], v)
    F = res["fills"]
    O = res["outcomes"]
    newf = F[F.coin == "NEW"]
    assert len(newf) and O[O.fill_id.isin(newf.fill_id)].twin_pooled.all(), "NEW should have pooled twins"
    assert O[O.fill_id.isin(newf.fill_id)].twin_n.min() > 0
    assert n_dl > 0, "no twin window crossed DEAD's delisting"
    # uniformity of draws over the eligible minutes (chi-square over months)
    cc = CoinCtx(world, "SYN0", mem["SYN0"], mem["SYN0"], need_index=False)
    el = cc.elig(RT_SPOT, "prog")
    cut = _cutoff(lambda t_: _horizon(FLIP, t_), end_min, FLIP.stop_m + 2 * DAY_M)
    tau0 = int(el.t[len(el.t) // 2])
    i0, i1, nL, nR, days = el.window(cut, tau0, EXCL_DAYS)
    uu = np.random.default_rng(9).random(200_000)
    b = el.pick(uu, i0, i1, nL, nR)
    tb = cc.spot.t[b]
    elig_t = np.r_[el.t[:i0], el.t[i1:int(np.searchsorted(el.t, cut, side="right"))]]
    assert np.all(np.isin(tb, elig_t))
    mo_d, mo_e = _month_of_min(tb), _month_of_min(elig_t)
    ms = np.unique(mo_e)
    obs = np.array([(mo_d == q).sum() for q in ms], float)
    exp = np.array([(mo_e == q).sum() for q in ms], float) / len(elig_t) * len(tb)
    chi2 = float(((obs - exp) ** 2 / exp).sum())
    from scipy import stats as _st
    pval = float(_st.chi2.sf(chi2, len(ms) - 1))
    assert pval > 1e-3, pval
    say(f"  twins: {n_own:,} own and {n_pool:,} pooled twins all live, in member months, outside +-182 days, with "
        f"complete windows; NEW (4 member months) gets pooled twins; {n_dl} twin windows cut by DEAD's delisting "
        f"closed at VWAP x 0.70; draws uniform over eligible minutes (chi-square p {pval:.2f}, {len(ms)} months)")


def _t_accounts(say):
    """D7 ledgers (§10.4) on a synthetic world with a zero T-bill: the flip account's final value minus its capital
    equals the sum of size x r over the positions it took (one per (coin, rung) at a time, none overlapping);
    D7-OWN's final value equals its contributions plus the marked value of its lots minus their cost; B-TBILL is
    flat."""
    W = synth_world(n_coins=3, days=640, seed=11, jumps_per_year=9, jump_size=-0.30)
    cfg = dict(rules=("F1",), exits={"F1": (FLIP,)}, twin_sens=False, drift=False, verbose=False, mw=False)
    res = run_program("P1", "U_Q1", data=W, cfg=cfg)
    A = accounts(res, data=W, route="F1")
    S = A["summary"]
    pos = A["positions"]
    K = float(S.loc["D7", "K"])
    V = A["values"]["D7"].to_numpy()
    assert abs((V[-1] - K) - float((pos["size"] * pos["r"]).sum())) < 1e-6 * K, (V[-1] - K, (pos.size * pos.r).sum())
    for key, g in pos.groupby(["coin", "rung"]):
        g = g.sort_values("t_fill")
        assert (g.t_fill.to_numpy()[1:] >= g.t_exit.to_numpy()[:-1]).all(), "overlapping positions in one rung"
    world = World(W)
    days = np.arange(int(res["bids"].t0.min() // DAY_M), world.end_min // DAY_M + 1)
    Pn = _Panel(world, sorted(res["bids"].coin.unique()), days)
    lots = A["lots"]
    mark = sum(float(r.units_lin) * Pn.close[-1, Pn.col[r.coin]] for r in lots.itertuples())
    end = float(S.loc["D7-OWN", "end_value"])
    assert abs(end - (A["contributions"] + mark - lots.cost.sum())) < 1e-6 * max(1.0, end), \
        (end, A["contributions"], mark, lots.cost.sum())
    assert float(np.abs(A["monthly"]["B-TBILL"]).max()) == 0.0
    say(f"  accounts: D7 ledger = capital + sum(size x r) over {len(pos)} non-overlapping positions; D7-OWN = "
        f"contributions + marked lots - cost ({len(lots)} lots); {len(A['monthly'].columns)} monthly series")
    # after-tax (§10.4 'after-tax (35% short-term, 20% long-term)'; review finding 5), known answers
    # (1) the tax ledger on hand-made events: year 1 interest 100, a short-term gain 1000 and a long-term loss 300
    # (taxed 0.35 x 800), year 2 a long-term gain 2000 and a short-term loss 500 (taxed 0.20 x 1500); then a short-term
    # loss carried into a year with gains (short 600, long 1000: 0.20 x (1000 - 400))
    dd = np.arange(_tmin("2023-06-01") // DAY_M, _tmin("2024-12-31") // DAY_M + 1)
    y2 = int(np.flatnonzero(dd == _tmin("2024-01-01") // DAY_M)[0])
    it = np.zeros(len(dd))
    it[5] = 100.0
    Vt, tx = _after_tax(np.full(len(dd), 1e4), dd, np.zeros(len(dd)), it,
                        [(10, 1000.0, 10), (20, -300.0, 400), (y2 + 5, 2000.0, 500), (y2 + 9, -500.0, 30)])
    assert abs(tx.sum() - (0.35 * 800 + 0.20 * 1500)) < 1e-9 and abs(Vt[-1] - (1e4 - 580.0)) < 1e-9, tx.sum()
    _, tx = _after_tax(np.zeros(len(dd)), dd, np.zeros(len(dd)), None,
                       [(10, -1000.0, 10), (y2 + 1, 600.0, 20), (y2 + 2, 1000.0, 700)])
    assert abs(tx.sum() - 0.20 * 600.0) < 1e-9, tx.sum()
    # (2) every account has an after-tax CAGR; the toy path +10% a month untaxed gives after-tax CAGR = CAGR
    assert S.cagr_after_tax.notna().all(), S.cagr_after_tax[S.cagr_after_tax.isna()]
    rr = pd.Series([0.1] * 4)
    toy = _summ(pd.Series([110.0, 121.0, 133.1, 146.41]), rr, pd.Series(np.zeros(4)), r_tax=rr)
    assert abs(toy["cagr"] - toy["cagr_after_tax"]) < 1e-12
    # (3) D7 (no T-bill): 35% on each calendar year's net flip gains, losses carried forward, recomputed here, on a
    # world where flips gain (market-wide gaps that revert within 30 minutes) and coins drift up (about +100% a year)
    rng = np.random.default_rng(12)
    jm = np.sort(rng.integers(40 * DAY_M, 630 * DAY_M, 16))
    W = {"coins": {f"UP{c}": {"m1": synth_coin("2020-01-01", 640, 700 + c, p0=10.0 + 5 * c, tick="0.0001",
                                                 drift_m=1.0 / 525_600,
                                                 jumps=[(int(x), -0.3) for x in jm] + [(int(x) + 30, 0.3) for x in jm]),
                             "tick": "0.0001"} for c in range(3)}, "end": "2021-10-01", "tbill": 0.0}
    W["universe"] = pd.DataFrame([dict(month=m, coin=c, U_Q1=True, U_B=True) for c in W["coins"]
                                  for m in pd.period_range("2020-01", "2021-10", freq="M").strftime("%Y-%m")])
    res = run_program("P1", "U_Q1", data=W, cfg=cfg)
    A = accounts(res, data=W, route="F1")
    S, pos = A["summary"], A["positions"]
    K = float(S.loc["D7", "K"])
    world = World(W)
    days = np.arange(int(res["bids"].t0.min() // DAY_M), world.end_min // DAY_M + 1)
    Pn = _Panel(world, sorted(res["bids"].coin.unique()), days)
    gy = (pos["size"] * pos["r"]).groupby(pd.DatetimeIndex(_mts(pos.t_exit.to_numpy())).year).sum()
    carry = tax7 = 0.0
    for y in sorted(gy.index):
        net = float(gy[y]) + carry
        tax7 += TAX_ST * max(net, 0.0)
        carry = min(net, 0.0)
    assert tax7 > 0 and abs((S.loc["D7", "end_value"] - S.loc["D7", "end_value_after_tax"]) - tax7) < 1e-6 * K, tax7
    # (4) B-HOLD: every coin bought on the first day and held to the end (over a year): its liquidation is taxed at
    # 20% (long-term) on the net gain
    first = int(np.flatnonzero(np.isfinite(Pn.open).all(axis=1))[0])
    n_c = Pn.close.shape[1]
    gain = sum((K / n_c) / Pn.open[first, j] * Pn.close[-1, j] - K / n_c for j in range(n_c))
    assert len(days) - first > 365 and gain > 0
    assert abs((S.loc["B-HOLD", "end_value"] - S.loc["B-HOLD", "end_value_after_tax"]) - TAX_LT * max(gain, 0.0)) \
        < 1e-6 * K, (gain, S.loc["B-HOLD"].to_dict())
    # (5) B-TBILL at a 4% T-bill: interest taxed at 35% each calendar year, the tax no longer earning (after tax)
    A4 = accounts(res, data=dict(W, tbill=4.0), route="F1")
    rd = 0.04 / 365
    v, owed, ydays = K, 0.0, pd.DatetimeIndex(_mts(days * DAY_M)).year.to_numpy()
    year_int = 0.0
    for i in range(len(days)):
        year_int += v * rd
        v *= 1 + rd
        owed *= 1 + rd * (1 - TAX_ST)
        if i == len(days) - 1 or ydays[i + 1] != ydays[i]:
            owed += TAX_ST * year_int
            year_int = 0.0
    S4 = A4["summary"]
    assert abs(S4.loc["B-TBILL", "end_value"] - v) < 1e-6 * K and \
        abs(S4.loc["B-TBILL", "end_value_after_tax"] - (v - owed)) < 1e-6 * K, (v - owed, S4.loc["B-TBILL"].to_dict())
    say(f"  after-tax: the 35% / 20% ledger with netting and carried losses on hand-made events; D7 taxed "
        f"{tax7:,.0f} on its yearly net flips, B-HOLD 20% of its {gain:,.0f} long-term gain at the liquidation, "
        f"B-TBILL 35% of each year's interest at a 4% T-bill; every account has an after-tax CAGR "
        f"({len(S)} accounts)")


def _t_cap_size(say):
    """D7 position size (§7 'accumulates causally, minute by minute', V13; review finding 6): a fill whose first
    window prints a few dollars below L, then a second 10-minute dip a day later before the 72 h stop: at Q = $100k
    the position sold at the exit is min(Q, theta x the capacity accumulated before the exit), each window's dollars
    booked on its own day (the daily values match the known units), the unfilled remainder reserved."""
    tick, tk = "0.01", 0.01
    t0 = pd.Timestamp("2023-03-06 03:30", tz="UTC")
    d0 = pd.Timestamp("2023-03-05", tz="UTC")
    end, tend = "2023-03-20", pd.Timestamp("2023-03-21", tz="UTC")
    d1h = _hist_d1(d0, 100.0, 0.03)
    m1 = _flat_m1(d0, tend, 100.0, tick)
    spec = {"X": {"m1": m1, "d1": pd.concat([d1h.iloc[:-1], _daily_from_m1(m1)], ignore_index=True), "tick": tick,
                  "_months": ["2023-03"]}}
    W = _hb_world(spec, end)
    I = sbl.inputs_at("X", t0, data=World(W).levels_data("X"))
    info = sbl.level_info("M2", I, k=6.0)
    L, Lt = float(info["L"]), sbl.tick_value(info["n_ticks"] - 1, tick)
    tf = pd.Timestamp("2023-03-06 15:00", tz="UTC")
    _set(m1, tf, low=Lt - tk)
    mid = (m1.open_time > tf).to_numpy()
    m1.loc[mid, ["open", "close"]] = 88.0
    m1.loc[mid, "high"] = 88.0 + tk
    m1.loc[mid, "low"] = 88.0 - tk
    dip = ((m1.open_time >= pd.Timestamp("2023-03-07 15:00", tz="UTC")) &
           (m1.open_time < pd.Timestamp("2023-03-07 15:10", tz="UTC"))).to_numpy()
    m1.loc[dip, ["open", "close"]] = 80.0
    m1.loc[dip, "high"] = 80.0 + tk
    m1.loc[dip, "low"] = 80.0 - tk
    spec["X"]["d1"] = pd.concat([d1h.iloc[:-1], _daily_from_m1(m1)], ignore_index=True)
    res = run_program("P1", "U_Q1", data=W, cfg=dict(rules=("F1",), exits={"F1": (FLIP,)}, twin_sens=False,
                                                     drift=False, verbose=False, mw=False, audit="raise"))
    F = res["fills"]
    f = F[(F.rung == 6.0) & (F.t0 == _tmin(t0))].iloc[0]
    o = res["outcomes"]
    ex_ = o[(o.fill_id == f.fill_id) & (o.exit == "FLIP") & (o.cost == "C-RH")].iloc[0]
    cv = res["cap_curve"][res["cap_curve"].bid_id == f.bid_id]
    assert int(f.n_windows) == 2 and ex_.exit_kind == "stop" and cv.minute.max() < ex_.exit_t
    day1 = cv[cv.minute < _tmin("2023-03-07")].cum.max()
    for Q, th in ((100_000.0, 1.0), (100_000.0, 0.25), (1_000.0, 1.0)):
        A = accounts(res, data=W, route="F1", Q=Q, theta=th)
        p_ = A["positions"]
        p_ = p_[p_.bid_id == f.bid_id].iloc[0]
        size = min(Q, th * float(f.c1_life))
        assert abs(p_["size"] - size) < 1e-6 * Q, (Q, th, p_["size"], size)
        # daily values (no T-bill, no carry): K - filled + filled / (L (1 + c)) x the day's close (88)
        K = float(A["summary"].loc["D7", "K"])
        V = A["values"]["D7"].to_numpy()
        f1_, f2_ = min(Q, th * day1), size
        for d_, fd in ((0, f1_), (1, f2_)):
            assert abs(V[d_] - (K - fd + fd / (L * (1 + C_RH)) * 88.0)) < 1e-6 * K, (Q, th, d_, V[d_])
    say(f"  D7 sizing: windows ${f.c1_first:,.2f} (fill day) and ${float(f.c1_life) - f.c1_first:,.0f} (a day "
        f"later) before the 72 h stop: at Q = $100k the position is min(Q, theta x ${float(f.c1_life):,.0f}), booked "
        f"day by day (theta 1 and 0.25; Q = $1k fills on the first day)")


def _t_real(say):
    """Real data, mechanics only (no price after any fill is read for an outcome): P1 bids and fills on a few U-Q1
    coins under F1, F2 (and F3 / F3d / F4 / F5 on two coins, whose index and perpetual months stinkbid_data fetches
    on demand), C1 capacity, the K5 audit of every fill (zero violations; gap-through fills listed), timings; one
    fill's capacity also from aggTrades."""
    t = time.time()
    coins = ["BTC", "ETH", "NEAR", "SOL", "LINK", "DOGE"]
    res = run_program("P1", "U_Q1", coins=coins, cfg=dict(counts_only=True, rules=("F1", "F2"), capacity="c1",
                                                          verbose=False))
    F, A, Bd = res["fills"], res["audit"], res["bids"]
    viol = A[A.type == "violation"] if len(A) else A
    assert not len(viol), viol.head().to_string()
    n1 = int((F.t_F1 >= 0).sum())
    by = F[F.t_F1 >= 0].groupby("rung").size().to_dict()
    gaps = int(F.gap_through.fillna(False).sum())
    say(f"  real P1 (counts only) on {', '.join(coins)}: {len(Bd):,} bids, {n1} F1 fills (k=6/8/10: "
        f"{by.get(6.0, 0)}/{by.get(8.0, 0)}/{by.get(10.0, 0)}), {int((F.t_F2 >= 0).sum())} F2 touches, {gaps} "
        f"gap-through fills listed, audit clean ({len(A)} records) in {time.time() - t:.0f}s")
    assert n1 > 0 and (F.t_F2 >= 0).sum() >= n1
    t = time.time()
    res2 = run_program("P1", "U_Q1", coins=["NEAR", "ETH"], cfg=dict(counts_only=True, capacity="c1",
                                                                     rules=("F1", "F3_1", "F3_3", "F3d_1", "F4",
                                                                            "F5"), verbose=False))
    F2 = res2["fills"]
    A2 = res2["audit"]
    assert not (A2.type == "violation").any()
    f1 = F2[F2.t_F1 >= 0]
    kept = {r: int(((F2.t_F1 >= 0) & (F2["t_" + r] >= 0)).sum()) for r in ("F3_1", "F3_3", "F3d_1", "F4", "F5")}
    say(f"  real venue counts on NEAR, ETH: {len(f1)} F1 fills; also filled under " +
        ", ".join(f"{k} {v}" for k, v in kept.items()) +
        f"; index missing at {int(f1.idx_missing.sum())} F1 minutes, an outage at {int(f1.idx_outage.sum())} "
        f"({time.time() - t:.0f}s)")
    # aggTrades capacity on one fill (stinkbid_data.agg_capacity; one coin-day zip)
    t = time.time()
    one = F[(F.coin == "NEAR") & (F.t_F1 >= 0)].head(1)
    if len(one):
        world = World()
        sp, _, _ = build_spot(world, "NEAR")
        b = Bd[Bd.bid_id.isin(one.bid_id)].reset_index(drop=True)
        i1 = coin_fills(b, sp, None, None, ("F1",))["F1"]
        cap = capacity(world, "NEAR", b, sp, i1, "agg")
        r = cap.iloc[0]
        say(f"  aggTrades capacity on one NEAR fill: {int(r.n_windows)} windows, first window C1 "
            f"${r.c1_first:,.0f} vs aggTrades ${r.agg_first:,.0f} (missing day: {bool(r.agg_missing)}) "
            f"({time.time() - t:.0f}s)")
    return res


def _t_h4(say):
    """H4 programs (§6.2-§6.3, §10.3): the real chart level and its four placebos L exp(+-0.5 / +-1.0 ATR%) per
    coin-week, run exactly like it; stacked frames with coin-week ids and depth terms accepted by
    stinkbid_stats.test_h4."""
    W = synth_world(n_coins=3, days=500, seed=31, jumps_per_year=10, jump_size=-0.35)
    cfg = dict(rules=("F1", "F3_1"), exits={"F1": (FLIP,), "F3_1": (FLIP,)}, twin_sens=False, drift=False,
               verbose=False, mw=False)
    res = run_program("H4", "U_Q1", data=W, cfg=cfg)
    B = res["bids"]
    assert set(np.unique(B["shift"])) <= {-1.0, -0.5, 0.0, 0.5, 1.0}
    world = World(W)
    chk = 0
    for (c, t0, var), g in B.groupby(["coin", "t0", "variant"]):
        r = g[g.real]
        if not len(r):
            continue
        I = sbl.inputs_at(c, _mts(int(t0)), data=world.levels_data(c))
        pl = {sh: Lp for sh, Lp, _ in sbl.placebos(float(r.L.iloc[0]), inputs=I)}
        for x in g[~g.real].itertuples():
            assert abs(x.L - pl[x.shift]) < 1e-12
            chk += 1
        assert g.cw.nunique() == 1
    fr = h4_frames(res)
    n_real = {k: int(v.real.sum()) for k, v in fr.items()}
    n_pl = {k: int((~v.real).sum()) for k, v in fr.items()}
    say(f"  H4: {chk} placebo bids at floor(L exp(+-0.5 / +-1.0 ATR%)) checked; stacked fills real/placebo " +
        ", ".join(f"{k} {n_real[k]}/{n_pl[k]}" for k in fr))
    # the F3 gate's frames by default (F3 rows carry the cost label RH; review finding 8); a wrong label raises
    fr3 = h4_frames(res, rule="F3_1")
    assert fr3 and sum(len(v) for v in fr3.values()) > 0, "no F3 frames"
    try:
        h4_frames(res, rule="F3_1", cost="C-RH")
        raise AssertionError("a cost label F3 rows do not carry was accepted")
    except ValueError:
        pass
    # only whole horizons enter (§4; review finding 3): end the data on the day of a late quick target exit, so that
    # fill's M(fill + 72 h) runs past the data end while its target already hit
    O, F = res["outcomes"], res["fills"]
    o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH")].merge(F[["fill_id", "t_F1"]], on="fill_id")
    q = o[(o.exit_kind == "target") & (o.hold_h < 30) & (o.t_F1 > _tmin("2021-01-01"))].sort_values("t_F1")
    assert len(q), "no quick target exit late in the sample"
    end_day = pd.Timestamp(_mts(int(q.exit_t.iloc[-1]))).tz_localize(None).normalize()
    cut = _tmin(end_day + pd.Timedelta("1D"))
    W2 = dict(W, end=end_day.strftime("%Y-%m-%d"), coins={})
    for c, fr_ in W["coins"].items():
        W2["coins"][c] = {k: (v[_tmin(v.open_time) < cut].reset_index(drop=True)
                              if k in ("m1", "index_m1", "perp_m1") else v)
                          for k, v in fr_.items() if not k.startswith("_")}
    W2["universe"] = W["universe"][W["universe"].month <= end_day.strftime("%Y-%m")]
    res2 = run_program("H4", "U_Q1", data=W2, cfg=dict(cfg, rules=("F1",), exits={"F1": (FLIP,)}))
    O2 = res2["outcomes"]
    o2 = O2[(O2.rule == "F1") & (O2.exit == "FLIP") & (O2.cost == "C-RH")]
    inc = o2[~o2.complete.astype(bool) & np.isfinite(o2.r.to_numpy(float))]
    ids = set(np.concatenate([v.fill_id.to_numpy() for v in h4_frames(res2).values()]).tolist())
    assert len(inc) and not (set(inc.fill_id.tolist()) & ids), (len(inc), inc.fill_id.tolist())
    assert o2[o2.fill_id.isin(ids)].complete.astype(bool).all()
    say(f"  H4 frames: F3 frames by the route's cost label ({sum(len(v) for v in fr3.values())} rows); "
        f"{len(inc)} fill(s) whose target hit before a data end that cuts its 72 h horizon are left out")
    if fr:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")          # M7 has no futures data in a synthetic world
            out = sbs.test_h4({k: v for k, v in fr.items()}, B=199)
        assert isinstance(out, dict)
    return res


def _t_causal(say):
    """K4-style look-ahead check (V2, §10.5): with every price after a cut minute x 1.5 and volumes x 0.5, separately
    with every bar after the cut deleted, and (K4b) with a 3-day gap inserted after the cut in bars without `seg`
    (the §4.1 boundary then derived from the bars, review finding 7), every bid, fill (F1, F3), exit and first
    capacity window stamped before the cut is unchanged. Altered worlds re-derive every table from their bars."""
    W = synth_world(n_coins=2, days=420, seed=41, jumps_per_year=10, jump_size=-0.3)
    cfg = dict(rules=("F1", "F3_1"), exits={"F1": (FLIP, EXIT_SPECS["HOLD7"]), "F3_1": (FLIP,)}, twin_sens=False,
               drift=False, verbose=False, mw=False, audit="raise")
    base = run_program("P1", "U_Q1", data=W, cfg=cfg)
    fresh = lambda fr: {k: v for k, v in fr.items() if not k.startswith("_")}      # no cached derived tables
    W_ns = {**W, "coins": {c: dict(fresh(fr), m1=fr["m1"].drop(columns=["seg"])) for c, fr in W["coins"].items()}}
    base_ns = run_program("P1", "U_Q1", data=W_ns, cfg=cfg)
    rng = np.random.default_rng(4)
    cuts = []
    ft = base["fills"].t_F1.to_numpy()
    ft = ft[ft > 0]
    for x in rng.choice(ft, 3, replace=False):
        cuts.append(int(x) + int(rng.integers(5, 300)) + (7 if (int(x) % 60 == 0) else 0))
    cuts.append(_tmin(pd.Timestamp(W["end"]) - pd.Timedelta(days=150)) + 17)
    n_checked = n_gap = 0
    for cut in cuts:
        for mode in ("scale", "delete", "gap"):
            src, ref = (W_ns, base_ns) if mode == "gap" else (W, base)
            W2 = {**src, "coins": {}}
            for c, fr in src["coins"].items():
                fr2 = fresh(fr)
                for key in ("m1", "index_m1", "perp_m1"):
                    k = fr[key].copy()
                    tk_ = _tmin(k.open_time)
                    after = tk_ > cut
                    if mode == "scale":
                        for col in ("open", "high", "low", "close"):
                            k.loc[after, col] = k.loc[after, col] * 1.5
                        for col in ("volume", "quote_volume", "taker_buy_quote"):
                            if col in k:
                                k.loc[after, col] = k.loc[after, col] * 0.5
                    elif mode == "delete":
                        k = k[~after].reset_index(drop=True)
                    else:                                 # no bars in (cut, cut + 3 days]
                        k = k[~(after & (tk_ <= cut + 3 * DAY_M))].reset_index(drop=True)
                    fr2[key] = k
                W2["coins"][c] = fr2
            alt = run_program("P1", "U_Q1", data=W2, cfg=cfg)
            if mode == "gap":
                w2 = World(W2)
                for c in W2["coins"]:
                    sg_ = w2.segments(c)
                    assert len(sg_) >= 2 and "gap" in set(sg_.kind), (c, sg_.kind.tolist())
                    n_gap += 1
            base_ = ref
            b0, b1 = base_["bids"], alt["bids"]
            k0 = b0[b0.t0 < cut].set_index(["coin", "t0", "rung"])[["L", "life_end"]]
            k1 = b1[b1.t0 < cut].set_index(["coin", "t0", "rung"])[["L", "life_end"]]
            assert k0.index.equals(k1.index) and np.allclose(k0.L, k1.L), "bids changed"
            for rule in ("F1", "F3_1"):
                f0 = base_["fills"]
                f1 = alt["fills"]
                a0 = f0[(f0["t_" + rule] >= 0) & (f0["t_" + rule] < cut)].set_index(["coin", "t0", "rung"])
                a1 = f1[(f1["t_" + rule] >= 0) & (f1["t_" + rule] < cut)].set_index(["coin", "t0", "rung"])
                assert a0.index.sort_values().equals(a1.index.sort_values()), (rule, mode, "fills changed")
                assert (a0["t_" + rule].sort_index() == a1["t_" + rule].sort_index()).all()
                o0 = base_["outcomes"].merge(f0[["fill_id", "t0", "rung"]], on="fill_id")
                o1 = alt["outcomes"].merge(f1[["fill_id", "t0", "rung"]], on="fill_id")
                key = ["coin", "t0", "rung", "rule", "exit", "cost"]
                d0 = o0[(o0.rule == rule) & (o0.exit_t >= 0) & (o0.exit_t < cut)].set_index(key)
                d1 = o1.set_index(key).reindex(d0.index)
                ok = (d0.exit_kind != "delist")
                assert (d0.exit_t[ok] == d1.exit_t[ok]).all() and np.allclose(d0.exit_px[ok], d1.exit_px[ok]), \
                    (rule, mode, "exit changed")
                n_checked += int(ok.sum())
            c0 = base_["fills"][(base_["fills"].t_F1 >= 0) & (base_["fills"].t_F1 + CAP_WIN_M < cut)]
            c1 = alt["fills"].set_index(["coin", "t0", "rung"]).reindex(c0.set_index(["coin", "t0", "rung"]).index)
            assert np.allclose(c0.c1_first.to_numpy(), c1.c1_first.to_numpy()), "capacity changed"
    say(f"  causality (K4-style): {len(cuts)} cuts x (prices x 1.5 / bars deleted / a 3-day gap in bars without "
        f"seg, derived as a §4.1 gap on {n_gap} coin-cuts): bids, F1 and F3 fills, {n_checked} exits and first "
        f"capacity windows stamped before each cut unchanged")


def selftest(real: bool = True):
    T = time.time()
    say = _say
    say("stinkbid_engine selftest")
    t = time.time()
    _t_rule_m(say)
    _t_hand(say)
    _t_tick(say)
    say(f"  hand-built paths: ok ({time.time() - t:.0f}s)")
    t = time.time()
    _t_chain(say)
    _t_chain_oracle(say)
    say(f"  positions across segment boundaries: ok ({time.time() - t:.0f}s)")
    t = time.time()
    _t_oracle(say)
    say(f"  oracle: ok ({time.time() - t:.0f}s)")
    t = time.time()
    _t_twins(say)
    say(f"  twins: ok ({time.time() - t:.0f}s)")
    t = time.time()
    _t_seg_derive(say)
    _t_stream_cache(say)
    say(f"  derived segments, stream cache: ok ({time.time() - t:.0f}s)")
    t = time.time()
    _t_accounts(say)
    _t_cap_size(say)
    say(f"  accounts: ok ({time.time() - t:.0f}s)")
    t = time.time()
    _t_h4(say)
    say(f"  H4: ok ({time.time() - t:.0f}s)")
    t = time.time()
    _t_causal(say)
    say(f"  causality: ok ({time.time() - t:.0f}s)")
    if real:
        t = time.time()
        _t_real(say)
        say(f"  real data (mechanics only): ok ({time.time() - t:.0f}s)")
    say(f"all passed ({time.time() - T:.0f}s)")


def _arg(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) else default
    return default


def counts(program: str = "P1", universe: str = "U_Q1", coins=None, rules=("F1", "F2"), capacity_mode="c1",
           stream=False) -> dict:
    """Fill counts of one program (§14 stage 3: counts before any return): bids per rung, fills per rule and rung,
    fill months and days, gap-through fills, the K5 fill audit, timings. No outcome is computed."""
    t = time.time()
    res = run_program(program, universe, coins=coins, cfg=dict(counts_only=True, rules=tuple(rules),
                                                               capacity=capacity_mode, stream=stream, verbose=False))
    F, B, A = res["fills"], res["bids"], res["audit"]
    out = dict(program=program, universe=universe, seconds=round(time.time() - t, 1), coins=int(B.coin.nunique()),
               bids=len(B), bids_by_variant=B.groupby("variant").size().to_dict(),
               audit_violations=int((A.type == "violation").sum()) if len(A) else 0,
               audit_gaps=int((A.type == "gap").sum()) if len(A) else 0)
    for r in rules:
        c = "t_" + r
        if c in F:
            f = F[F[c] >= 0]
            out[f"fills_{r}"] = len(f)
            out[f"fills_{r}_by_variant"] = f.groupby("variant").size().to_dict()
            if len(f):
                out[f"months_{r}"] = int(pd.Series(_month_of_min(f[c].to_numpy())).nunique())
                out[f"days_{r}"] = int(pd.Series(f[c].to_numpy() // DAY_M).nunique())
    res["counts"] = out
    return res


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "selftest":
        selftest(real="--no-real" not in argv)
        return
    if argv[0] == "counts":
        prog = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else "P1"
        univ = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else "U_Q1"
        coins = _arg(argv, "--coins")
        rules = _arg(argv, "--rules", "F1,F2").split(",")
        res = counts(prog, univ, coins=coins.split(",") if coins else None, rules=rules,
                     capacity_mode=_arg(argv, "--capacity", "c1"), stream="--stream" in argv)
        import json as _json
        print(_json.dumps(res["counts"], indent=1, default=str))
        return
    raise SystemExit(f"unknown command {argv[0]!r} (selftest | counts)")


if __name__ == "__main__":
    main()
