"""
Trade engine for the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md): the R0 table (Signal,
Entry window, Size, Adds, Re-entry, Hard stop, Take-profit, Trend exit, Rule 6, Rule 15, Liquidation, Sizing equity,
Costs, Fee scenarios), the Fill conventions, the Windows' edge rules, the Sensitivity grid S1-S20 with S1W and the
bar-size rows rule, H4's touch arm, H6's New York timing pairs, H7/H8's placebo blocks and deferrals, the luck
benchmark's / H11b decoys' given entries, and the Controls' engine known answer, liquidation check and fill audit.
Contract: the scratchpad's bb_engine_spec.md, "bb_engine.py". Data come from analysis_2026/bb_data.py.

    python3 -m analysis_2026.bb_engine selftest     # synthetic known answers + mechanics-only real-data audit

Public API
  Cfg                       frozen dataclass, one field per pre-registered choice (R0 = Cfg())
  ROWS                      every pre-registered row: R0, S1 (and S1_L1), S1W (and S1W_L1), S2 .. S20 variants,
                            pre-perpetual block and route rows; ROW_UNIVERSE gives each row's coin set
                            (S12_top3 / S12_top6: the 40-coin pool; S12_top10: all perpetuals, crypto only);
                            S12_UNIVERSES maps F's and H11b's universe names to keys; H1_S12_GATE = "S12_all_top3"
  h6_cfg(e, x), h7_cfg(days), h8a_cfg(hours), h8b_cfg(days), h4_touch_cfg(), luck_cfg(L)   placebo / arm builders
  simulate_coin(sym, cfg, start=None, end=None, given_entries=None, hours=None, minutes=None,
                entry_allowed=None, mmr=None, detail=True) -> dict
      trades, tranches, expo, daily_mtm, fills_audit, log, signals  (per position, in units of M = 1)
      start / end bound entry1 fills (None = the whole history of the hours: pass the window explicitly).
      expo: detail=True one row per position-hour (pos, time, notional signed, sym, pnl_lo, mm, hour); detail=False
      one row per position (time = entry1_time, notional = the sum over its hours), which bb_stats.drift_adjust
      accepts too (it uses the sum); assemble's cross margin needs detail=True.
      given_entries: timestamps (long), a Series of sides indexed by timestamps, or a DataFrame (time, side).
      trades columns: pos sym side signal_day signal_known entry1_time entry1_px S TP L_used L_max liq_px0
        exit_time exit_px exit_reason n_tranches max_frac ret ret_gross fees funding liquidated hold_h open_at_end
        atH_only deferred tp_filled n_adds_cancelled reentry given entry_bar l_capped avg_entry margin_posted
        expo_sum touch month near_r0 (the signal bar meets R0's near-high rule: H5's indicator)
  assemble(results_by_coin, cfg, start, end, idle_tbill=False, k_slots=None) -> dict    account of K slots
  s12_allowed(sym, k, pool="all", tradfi=False) -> Series    month-start membership mask for entry_allowed
  row_coins(row) -> list                                     coin set of a ROWS entry (S12: every coin ever in it)
  h4_episodes(sym, start, end) -> DataFrame, assign_episodes(trades, episodes) -> Series   H4's episode unit
  prepare(sym, hours=None, minutes=None)                     preload / cache a coin's arrays (injected frames are
                                                             re-validated by a content fingerprint on every hit)

Units. Every per-position number is per unit of the position's maximum notional M (ret = net P&L / M). Each
tranche is M/3 of notional at its own fill price (S4: M at entry); isolated margin per tranche = notional / L_used.
assemble() turns positions into dollars: M = L_used x sleeve, sleeve = sizing equity / K.

Mechanics (pre-registration text in quotes where it decides)
- Signal bars: bb_data.bars_from_hours(hours, cfg.bars, "sig") (spot where spot trades, else the perpetual).
  BB(n, k) with population sigma on closes, ATR14 Wilder (moneyline_ref.atr: RMA seeded with the SMA of the first
  14 true ranges, TR of a segment's first bar = high - low), all restarted at every change of `seg`.
  Long signal at bar t: C_t > UB_t, C_{t-1} <= UB_{t-1} (previous bar of the same segment) and the near-high rule:
  r0: C_t >= 0.95 x max sig high over the 60 days ending at the bar's close, or C_t >= 0.90 x ATH_t (cumulative max
  sig high of the segment) with >= 365 completed daily bars; "off": none; "20d2": C_t >= 0.98 x the 20-day max;
  "365d10": C_t >= 0.90 x the 365-day max (365 bars); "ath10": C_t >= 0.90 x ATH_t (365 bars). No signal before 60
  completed daily bars of the segment. ATH-only signals (r0 rows that pass only through the ATH branch) are flagged.
  S13 squeeze: BandWidth within 10% of its 125-day low on one of the 10 prior days.
- Entry ("first allowed window after the signal close"): daily rows enter at the open of the first hour whose
  New York clock hour is 06 or 10 (10 only for S14) at or after the bar's known_at, per calendar date with the
  America/New_York tz database (bb_data.ny_clock), every day. Rule 12: no first-tranche fill when that hour's New
  York date is in block_days (Fri, Sat); the signal waits for the next allowed window. At the window the latest
  completed bar must still satisfy the signal (see choice 2). A window hour with trades == 0 passes to the next
  window. S = the stop rule on the latest completed bar at the window; the entry is skipped (signal dropped) if
  the window opens at or below S. Fill at that open + taker fee + slippage.
  S1 ("core"): the 01:00 UTC open after the signal close (the next hour with trades > 0); exits likewise.
  S1W ("windows"): R0's entry and exit windows with rules 6 and 12-15 off (ROWS sets block_days=() etc.).
  "ny" (H6): the first occurrence of New York hour entry_ny_hour at or after the deciding 00:00 UTC close; exits
  at the first occurrence of exit_ny_hour at or after the exit close; S1's rules otherwise.
  Bar-size rows (4h, 1h): fill at the open of the hour that begins at the bar close; rule 12 and the 90-minute ban
  (New York hours 08 and 09: hourly opens inside 08:00-09:30) apply; windows and rules 6 and 15 are off; exits at
  the open of the hour beginning at the exit bar's close. S20 (1w): entries at R0's windows after the weekly close,
  exits at the next hourly open, rules 6 and 15 off.
- Adds: +M/3 when an hourly close >= 1.02 x entry1 and +M/3 when >= 1.05 x entry1 (S5: 1 + 2%/L_used and
  1 + 5%/L_used), each filled at the next hourly open with trades > 0, any hour and weekday; cancelled at that open
  if the open is below the average entry, a trend exit is pending, or the TP has filled. An add fills before a
  stop in the same hour.
- Stop S (rule 10): SMA20 - 1.0 x ATR14 of the latest completed bar at the entry (S9: BB(20, 2)'s lower band;
  SMA20 - 2.5 ATR); SMA20 in every row, S6 included (choice 1). Hourly hours: fill at the open if it opens at or
  below S, else 0.99 x S if the hour's low is more than 5% below S, else S. Hours covered by 1-minute bars (BTC ETH
  SOL BNB XRP DOGE from 2024-07-01): the first minute with trades > 0 whose low <= S fills at min(S, that minute's
  close), and minutes also order stop vs TP; an hour whose live minutes disagree with the hourly bar's high or low
  by more than half a tick (data inventory section 5: "Prefer the hourly files for these hours"; 6 coin-hours,
  2025-01-14 and 2025-01-29) is resolved on the hourly bar instead (log m1_hours_hourly_fallback). In an hourly bar
  touching both, the stop fills first. Then taker fee + slippage; a fill below the liquidation price is a
  liquidation instead. stop_fill="at_S" fills every stop at S (reported beside the primary).
  stress_20251010: stops do not trigger in the hours 2025-10-10 20:00, 21:00, 22:00 UTC (liquidation still does).
- TP = entry1 + 3 x (entry1 - S), a resting limit selling 50% (S10: 100% / none) at TP (the open if the hour opens
  through it), maker fee, no slippage.
- Trend exit: a completed bar close below the midline (SMA20) -> exit 100% at the next 13:00 New York window
  (daily rows) with stop and TP active meanwhile. Rule 6 literal: the exit signal is not acted on when the close is
  less than 72 h after entry1 and the mark at that close is at or above the average entry; "minhold": suppressed
  for every position while the close is less than min_hold_h after entry1. Rule 15: exit signals of the daily bars
  labelled with a UTC weekday in defer_days (Sat, Sun) are not acted on, so Monday's close re-decides and its exit
  fills in Tuesday's 13:00 window.
- Liquidation (isolated): price = avg x (1 - (isolated margin - fees paid - funding paid) / notional + mmr), long;
  avg x (1 + (...)/notional - mmr), short; notional = qty x avg entry; recomputed after every fill and funding
  print; checked on the hourly mark-price low (high for shorts), falling back to the last price where the mark is
  missing (spot stand-in hours). A liquidated position loses its isolated margin balance and nothing more.
  L_used = min(L, the largest L with S >= liq(full post-add position) + 0.02 x entry1), where the full position's
  average entry is the mean of the planned tranche prices (R0: 1.0233 x entry1; S4: entry1; S5: (3 + 0.07 / L_used)
  / 3 x entry1, since the ROE add levels move with L_used, solved as a fixed point) and its fees are the taker fee
  and slippage of the three tranches.
- Costs: taker 0.05% + slippage 0.02% (BTC, ETH) / 0.07% (others) per side; TP maker 0.02% without slippage; fee
  scenario "vip" taker 0.03% / maker 0.01%, "zero" none. Spot stand-in hours (spot_only) and spot_costs rows pay
  0.10% + slippage (TP 0.10%). cost_side overrides every fill's all-in cost (routes).
- Funding: funding[h] (bb_data; prints at the hour, synthetic 0.01%/8 h where spot stands in) x qty x mark price at
  the print (mark open of the hour; last price where missing), owed by a position open before the print and still
  open at it (a position closed at that hour's open pays, one opened at it does not). Longs pay positive rates,
  shorts receive them. spot_costs rows pay no funding.
- Outages: no fill, stop, TP, liquidation or add trigger in an hour (or minute) with trades == 0 or not tradable.
  A position open at a `perp_end` bar is force-closed at its close (taker + slippage).
- Windows: start/end bound entry1 fills; the run starts flat; signals from bars completed before start are ignored;
  a position open at end is marked at the last hourly close (open_at_end, no exit cost).

Coding choices the pre-registration leaves open (most literal reading taken)
1. The stop and the trend exit use R0's SMA20 in every row, and S9's band stop uses BB(20, 2)'s lower band (20 bars
   in the bar-size rows); S6's BB(n, k) changes only the signal band (and S13's BandWidth and the touch level).
   The R0 table names SMA20 for both ("S = SMA20 - 1.0 x ATR14", "Daily close < SMA20"), S6 states only band
   parameters, and "each row changes R0 as stated and nothing else". The other reading, that a BB(50, k) row cuts at
   its own Bollinger midline SMA50 (the prereg calls the trend exit "the midline exit"), is Cfg(midline="bb"); no
   ROWS entry uses it. ATR stays 14 bars. [Reading changed after the engine review; needs the orchestrator's
   ruling in the addendum before any result.]
2. Deferred-entry re-check: the latest completed bar must satisfy the signal's level conditions (C > UB, the
   near-high rule, squeeze and warm-up), not the freshness condition (a deferred breakout cannot be fresh twice).
   A newer fresh signal replaces a pending one (the older one's fate is "superseded"); a signal completed while the
   coin holds a position is ignored ("in_position"). A pending signal dropped by the re-check, by an open at or
   below S, or by a delisting needs a new fresh signal.
3. "Next window" for a zero-trade window hour; exits: a pending trend exit fills at the first hour with trades > 0
   at or after its window hour. S1's 01:00 UTC entry and bar-size fills likewise take the next hour with trades.
4. H6 "first occurrence after the deciding close": the first hour whose open time is at or after the close (delay
   0-23 h; the hour beginning at the close counts), the same convention as the bar-size rows' "next hourly open".
5. Rule 6's "mark at that daily close" is the mark close of the bar's last hour (last price where missing);
   "within 72 h" is close time - entry1 time < 72 h. min_hold_h likewise (<).
6. A cancelled add (open below the average entry, or a pending exit) can re-trigger on a later hourly close; after
   the TP fills no add can trigger. Adds trigger only on hours with trades > 0.
7. Liquidation fees: isolated margin is debited with each fill's fee and slippage and with funding; a TP partial
   close releases margin pro rata (its proceeds and fee go to the wallet). The liquidation check is hourly even in
   minute-resolved hours: if the stop is not triggered in the hour and the mark low reaches the liquidation price,
   the position is liquidated before any TP of that hour. Liquidation is never checked in a trades == 0 hour.
8. The L cap is applied in every leveraged row including S3 cross (it is a sizing rule); cross rows have no
   per-position liquidation (assemble() liquidates the account); spot_costs rows have neither cap nor liquidation.
9. stress_20251010 covers the hours [20:00, 23:00) UTC of 2025-10-10. at_S stops fill at S even in a gap; the fill
   audit exempts them (a counterfactual bound, not a fill model).
10. Short side (S11): fresh close below the lower band with C_{t-1} >= LB_{t-1}, near-low C <= 1.05 x the 60-day low
   (r0; no all-time-low branch), S = SMA + ATR, TP = entry1 - 3 x (S - entry1), adds at 0.98 / 0.95 x entry1 (or
   ROE), exit on a close above the midline, rule 6 "in profit" = mark <= average entry, liquidation on the mark high.
   One position per coin; a signal of either side while holding is ignored.
11. S18: after a full exit, the next completed bar with C > UB and the near-high rule, while no close at or below
   UB has occurred since the episode's last bar above the band, is a re-entry signal (flag `reentry`).
12. Touch arm (H4): the buy-stop level is the upper band of each completed bar (daily), re-placed at each 00:00 UTC
   close, kept only when that level meets the near-high rule (warm-up included); active whenever the coin is flat
   at an hour's open after that hour's open fills. Fill at max(level, open) in the first live hour with high >
   level; in a minute-covered hour, at max(level, open) of the first live minute whose high exceeds the level,
   and that hour's stop / TP scan starts at that minute. Stop/TP/liquidation are then checked in the entry hour
   as in any hour (stop first). The arm can re-enter in the next live hour after a stop, so on a whipsaw path it
   holds more positions than there are daily bars (the position buffer is then re-sized; at most one per hour).
13. Given entries (luck benchmark, H11b decoys): each timestamp is a decision time (a day's 00:00 for daily rows);
   the entry follows the row's window, block and skip rules from that time, without a signal re-check; S comes
   from the latest completed bar. A given entry while a position is open or pending is dropped (counted).
14. Window edges: the run starts flat at start; a position open at end is marked at the close of the last hour
   without exit costs. Time stamps (entry1_time, exit_time, tranche times) are the moment the data a fill used
   were complete: a fill at an hour's open is stamped at that open; a fill resolved on an hourly bar's range
   (stop, TP, liquidation, touch entry), a perp_end close and a window-end mark at the hour's close; a fill
   resolved on a 1-minute bar at that minute's close. So a decision stamped before a look-ahead cut time never
   used data after it.
15. MMR default: bb_data.MMR[sym] (0.005 for an unknown, e.g. synthetic, symbol unless mmr= is passed).
16. In the "vip" scenario spot stand-in fills keep spot costs (no spot VIP tier is pre-registered).
17. Sizing (assemble): rule 11 freezes the sizing equity of month m at month m-1's when month m-1 returned more
   than +25% (sizing equity = equity at 00:00 UTC of the month's first day, or of the window start); S19 sizes from
   equity at the last 00:00 UTC before entry1. idle_tbill credits the T-bill on equity minus the margin locked in
   open positions (cash and the sleeves' unused margin). Equity is floored at 0 (the account then stops).
18. S3 cross (assemble): hourly, equity with every open coin at its hourly mark low (high for shorts) jointly vs the
   sum of maintenance margins mmr x qty x avg entry; at the first breach every position is closed and the account
   keeps max(0, equity - maintenance) (0 at a breach), i.e. it is wiped and stops.
19. Cfg has one field beyond the spec contract, `ban` (rule 13's 90-minute ban, default on). It binds only in the
   bar-size convention (R0's windows never fall in it); S1-type rows set it off with rules 12-15.
20. ROWS["S1"] is the grid row at R0's L = 3 ("each row changes R0 as stated and nothing else"); H1, H2 and the
   headline use S1 at L = 1, ROWS["S1_L1"] (likewise S1W / S1W_L1), since they say "S1 at L = 1". H4-H8 name S1 or
   S1W without an L, so h6_cfg and h4_touch_cfg build on ROWS["S1"] (L = 3) and H4's close arm is ROWS["S1"];
   per M, L only matters through liquidation and the L cap.
21. S12 membership (entry_allowed) gates first-tranche fills only: a coin that leaves the top k keeps its position;
   a signal pending while the coin is not a member waits for a window in which it is, with the usual re-check.
   ROWS keys follow the prereg's names: S12_top3 / S12_top6 = "top 3 and top 6 of the 40 coins"
   (volume_ranks("40")), S12_top10 = "top 10 among all Binance USDT perpetuals" (volume_ranks("all",
   tradfi=False), addendum; S12_top10_tradfi the literal pool); S12_all_top3 (and _tradfi) is H1's gate.
22. The 1-minute / hourly cross-check (data inventory section 5) is applied per hour on the data given: an hour is
   resolved on its minutes only when its live minutes (trades > 0) reproduce the hourly bar's high and low to half
   a tick (bb_data.TICK; 1e-9 relative for a symbol without a tick). It is a data-source choice for the hour, not
   a trading decision; a look-ahead perturbation must therefore rebuild a straddling hourly bar from the live
   minutes (as _perturb does), or the hour switches source between the two runs.
23. Injected frames are cached by identity and re-validated on every call by a content fingerprint of the hours
   (every column) and of the minutes (index, OHLC, trades): a frame changed in place is prepared again.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, replace, asdict
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import bb_data as bd  # noqa: E402

H_NS = 3_600_000_000_000
MIN_NS = 60_000_000_000
DAY_NS = 24 * H_NS
M1_FROM = pd.Timestamp("2024-07-01", tz="UTC")
STRESS_FROM = pd.Timestamp("2025-10-10 20:00", tz="UTC")
STRESS_TO = pd.Timestamp("2025-10-10 23:00", tz="UTC")          # exclusive
TAKER = {"base": 0.0005, "vip": 0.0003, "zero": 0.0}
MAKER = {"base": 0.0002, "vip": 0.0001, "zero": 0.0}
SPOT_FEE = 0.0010
SLIP_MAJOR, SLIP_OTHER = 0.0002, 0.0007
MAJORS = ("BTC", "ETH")
BAN_NY_HOURS = (8, 9)          # hourly opens inside 08:00-09:30 New York (rule 13)
TP_R = 3.0
RULE6_H = 72
GAP_LOW = 0.95                 # "low more than 5% below S"
GAP_FILL = 0.99                # "the fill is 0.99 x S"
LCAP_PTS = 0.02                # "S sits at least 2 points above the liquidation price"
MID_N, MID_K = 20, 2.0         # R0's "SMA20" (stop, trend exit) and BB(20, 2) (S9's band stop), choice 1
SLOTS_R0 = ["BTC", "ETH", "SOL"]


# ============================================================================ configuration
@dataclass(frozen=True)
class Cfg:
    """One field per pre-registered choice; R0 is Cfg() and every row is Cfg(...) via ROWS."""
    bars: str = "1d"                      # "1d" | "4h" | "1h" | "1w"
    bb_n: int = 20
    bb_k: float = 2.0
    near_high: str = "r0"                 # "r0" | "off" | "20d2" | "365d10" | "ath10"
    squeeze: bool = False                 # S13
    timing: str = "r0"                    # "r0" | "core" (S1) | "windows" (S1W) | "ny" (H6) | "late_only" (S14)
    entry_ny_hour: int | None = None
    exit_ny_hour: int | None = None
    block_days: tuple = (4, 5)            # New York weekdays with no first-tranche fill (rule 12); () = off
    rule6: str = "literal"                # "literal" | "off" | "minhold"
    min_hold_h: int = 72                  # rule6="minhold" (S15, H8a dose-response)
    defer_days: tuple = (5, 6)            # UTC weekdays of the daily bars whose midline exits are not acted on
    L: float = 3.0
    margin: str = "isolated"              # "isolated" | "cross" (S3; account-level, see assemble)
    adds: str = "price"                   # "price" | "roe" (S5) | "none" (S4: full M at entry)
    stop: str = "r0"                      # "r0" SMA - 1 ATR | "lower_band" | "sma_2p5atr"
    tp: str = "half"                      # "half" | "all" | "none"
    direction: str = "long"               # "long" | "longshort" (S11)
    reentry: str = "fresh"                # "fresh" | "same_episode" (S18)
    entry_mode: str = "close"             # "close" | "touch" (H4) | "given" (caller-supplied entries)
    stop_fill: str = "resolved"           # "resolved" | "at_S"
    stress_20251010: bool = False
    fees: str = "base"                    # "base" | "vip" | "zero"
    spot_costs: bool = False              # spot vehicle: 0.10% + slippage, no funding, no liquidation
    cost_side: float | None = None        # all-in cost per side for every fill (routes: RH 0.0095, CB 0.0010)
    rule11: bool = True                   # S19 sets False (assembly only)
    ban: bool = True                      # rule 13's 90-minute ban (binds only in the bar-size convention)
    midline: str = "sma20"                # "sma20": stop, trend exit and S9's band stop on R0's SMA20 / BB(20, 2)
                                          #   whatever bb_n, bb_k (S6 changes the signal band only; choice 1);
                                          #   "bb": on the row's own BB(bb_n, bb_k) midline and bands

    def __post_init__(self):
        chk = {"bars": ("1d", "4h", "1h", "1w"), "near_high": ("r0", "off", "20d2", "365d10", "ath10"),
               "timing": ("r0", "core", "windows", "ny", "late_only"), "rule6": ("literal", "off", "minhold"),
               "margin": ("isolated", "cross"), "adds": ("price", "roe", "none"),
               "stop": ("r0", "lower_band", "sma_2p5atr"), "tp": ("half", "all", "none"),
               "direction": ("long", "longshort"), "reentry": ("fresh", "same_episode"),
               "entry_mode": ("close", "touch", "given"), "stop_fill": ("resolved", "at_S"),
               "fees": ("base", "vip", "zero"), "midline": ("sma20", "bb")}
        for k, ok in chk.items():
            if getattr(self, k) not in ok:
                raise ValueError(f"Cfg.{k}={getattr(self, k)!r} not in {ok}")
        if self.timing == "ny" and (self.entry_ny_hour is None or self.exit_ny_hour is None):
            raise ValueError("timing='ny' needs entry_ny_hour and exit_ny_hour")
        if self.entry_mode == "touch" and self.direction != "long":
            raise ValueError("the touch arm is long only")


_R0 = Cfg()
_S1 = Cfg(timing="core", block_days=(), rule6="off", defer_days=(), ban=False)
_S1W = Cfg(timing="windows", block_days=(), rule6="off", defer_days=(), ban=False)

ROWS: dict[str, Cfg] = {
    "R0": _R0,
    "S1": _S1, "S1_L1": replace(_S1, L=1.0),
    "S1W": _S1W, "S1W_L1": replace(_S1W, L=1.0),
    "S2": replace(_R0, L=1.0),
    "S3_L5": replace(_R0, L=5.0),
    "S3_cross": replace(_R0, margin="cross"),
    "S4": replace(_R0, adds="none"),
    "S5": replace(_R0, adds="roe"),
    "S6_bb20_2.5": replace(_R0, bb_n=20, bb_k=2.5),
    "S6_bb50_2": replace(_R0, bb_n=50, bb_k=2.0),
    "S6_bb10_1.9": replace(_R0, bb_n=10, bb_k=1.9),
    "S6_bb50_2.1": replace(_R0, bb_n=50, bb_k=2.1),
    "S6_bb10_1.5": replace(_R0, bb_n=10, bb_k=1.5),
    "S6_bb50_2.5": replace(_R0, bb_n=50, bb_k=2.5),
    "S7_off": replace(_R0, near_high="off"),
    "S7_20d2": replace(_R0, near_high="20d2"),
    "S7_365d10": replace(_R0, near_high="365d10"),
    "S7_ath10": replace(_R0, near_high="ath10"),
    "S8": replace(_R0, bars="4h"),
    "S9_lower_band": replace(_R0, stop="lower_band"),
    "S9_sma_2p5atr": replace(_R0, stop="sma_2p5atr"),
    "S10_tp_all": replace(_R0, tp="all"),
    "S10_no_tp": replace(_R0, tp="none"),
    "S11": replace(_R0, direction="longshort"),
    # S12 universes (ROW_UNIVERSE): the prereg's "top 3 and top 6 of the 40 coins" ("point-in-time ranks within a
    # 2026 pool") and "top 10 among all Binance USDT perpetuals" (crypto only, addendum); the TradFi pool of the
    # top 10 is the addendum's sensitivity. S12_all_top3 is H1's S12 gate (all-contract crypto-only top 3,
    # addendum), not a sensitivity row. F and H11b's universe factor use S12_UNIVERSES.
    "S12_top3": _R0, "S12_top6": _R0, "S12_top10": _R0, "S12_top10_tradfi": _R0,
    "S12_all_top3": _R0, "S12_all_top3_tradfi": _R0,
    "S13": replace(_R0, squeeze=True),
    "S14": replace(_R0, timing="late_only"),
    "S15": replace(_R0, rule6="minhold", min_hold_h=72, defer_days=()),
    "S16": replace(_R0, bars="1h"),
    "S17": _R0,
    "S18": replace(_R0, reentry="same_episode"),
    "S19": replace(_R0, rule11=False),
    "S20": replace(_R0, bars="1w", L=1.0),
    # pre-perpetual block (2017-08-17 .. 2019-12-31; L = 1 rows only; spot costs, no funding)
    "PRE_R0_L1": replace(_R0, L=1.0, spot_costs=True),
    "PRE_S1_L1": replace(_S1, L=1.0, spot_costs=True),
    # "What the user could run": RH spot (0.95% per side, long only, no leverage), its no-pyramid variant and the
    # R0-window variant; CB (0.10% all-in on Binance prices and funding) at L = 1 and 3
    "RH_S1": replace(_S1, L=1.0, spot_costs=True, cost_side=0.0095),
    "RH_S1_S4": replace(_S1, L=1.0, spot_costs=True, cost_side=0.0095, adds="none"),
    "RH_R0win": replace(_R0, L=1.0, spot_costs=True, cost_side=0.0095),
    "RH_R0win_S4": replace(_R0, L=1.0, spot_costs=True, cost_side=0.0095, adds="none"),
    "CB_S1_L1": replace(_S1, L=1.0, cost_side=0.0010),
    "CB_R0_L1": replace(_R0, L=1.0, cost_side=0.0010),
    "CB_R0_L3": replace(_R0, L=3.0, cost_side=0.0010),
    "R0_stress": replace(_R0, stress_20251010=True),
    "R0_at_S": replace(_R0, stop_fill="at_S"),
}
# coin set (or S12 ranking) of each row; anything absent trades BTC/ETH/SOL
ROW_UNIVERSE: dict[str, object] = {                                  # S12: ("s12", pool, k, tradfi)
    "S12_top3": ("s12", "40", 3, False), "S12_top6": ("s12", "40", 6, False),
    "S12_top10": ("s12", "all", 10, False), "S12_top10_tradfi": ("s12", "all", 10, True),
    "S12_all_top3": ("s12", "all", 3, False), "S12_all_top3_tradfi": ("s12", "all", 3, True),
    "S17": ["BTC", "ETH", "SOL", "ZEC"],
    "RH_S1": SLOTS_R0, "CB_S1_L1": ["BTC", "ETH"], "CB_R0_L1": ["BTC", "ETH"], "CB_R0_L3": ["BTC", "ETH"],
}
# the prereg's universe names -> ROWS / ROW_UNIVERSE keys: F's {BTC/ETH/SOL, S12 top 6, S12 top 10} and H11b's
# universe factor; H1's S12 gate ("S12's point-in-time top-3 universe (all-contract ranking)", addendum: crypto only)
S12_UNIVERSES = {"BTC/ETH/SOL": "R0", "S12 top 6": "S12_top6", "S12 top 10": "S12_top10"}
H1_S12_GATE = "S12_all_top3"


def h6_cfg(entry_ny_hour: int, exit_ny_hour: int, base: Cfg | None = None) -> Cfg:
    """H6 pair: S1's rules with entries / exits at the first occurrence of the New York hours."""
    return replace(base or ROWS["S1"], timing="ny", entry_ny_hour=int(entry_ny_hour), exit_ny_hour=int(exit_ny_hour))


def h7_cfg(block_days, base: Cfg | None = None) -> Cfg:
    """H7: S1W + a block of New York weekdays (deferred, re-checked). (4, 5) is rule 12; placebos (d, d+1 mod 7)."""
    return replace(base or ROWS["S1W"], block_days=tuple(int(d) % 7 for d in block_days))


def h8a_cfg(min_hold_h: int, base: Cfg | None = None) -> Cfg:
    """H8a dose: S1W + a minimum hold (midline exits suppressed for min_hold_h after entry1; 0 = S1W)."""
    b = base or ROWS["S1W"]
    return b if int(min_hold_h) == 0 else replace(b, rule6="minhold", min_hold_h=int(min_hold_h))


def h8b_cfg(defer_days, base: Cfg | None = None) -> Cfg:
    """H8b: S1W + rule 15 style deferral of the midline exits of bars labelled with these UTC weekdays."""
    return replace(base or ROWS["S1W"], defer_days=tuple(int(d) % 7 for d in defer_days))


def h4_touch_cfg(base: Cfg | None = None) -> Cfg:
    """H4 touch arm: S1 (ROWS["S1"], L = 3, as h6_cfg; choice 20) with the intrabar buy-stop at the latest completed
    upper band. Its comparison arm is the same base with entry_mode "close": pass the same base to both."""
    return replace(base or ROWS["S1"], entry_mode="touch")


def luck_cfg(L: float = 3.0) -> Cfg:
    """Luck benchmark: R0's rules with caller-supplied first-entry days."""
    return replace(ROWS["R0"], L=float(L), entry_mode="given")


# ============================================================================ numba: indicators
@njit(cache=True)
def _roll_sma_sd(x, seg, n):
    N = len(x)
    m = np.full(N, np.nan)
    s = np.full(N, np.nan)
    run = 0
    for i in range(N):
        if i > 0 and seg[i] == seg[i - 1]:
            run += 1
        else:
            run = 1
        if run >= n:
            acc = 0.0
            for k in range(i - n + 1, i + 1):
                acc += x[k]
            mu = acc / n
            v = 0.0
            for k in range(i - n + 1, i + 1):
                v += (x[k] - mu) * (x[k] - mu)
            m[i] = mu
            s[i] = np.sqrt(v / n)
    return m, s


@njit(cache=True)
def _atr_wilder(h, l, c, seg, n):
    N = len(c)
    out = np.full(N, np.nan)
    run = 0
    acc = 0.0
    prev = np.nan
    for i in range(N):
        new = i == 0 or seg[i] != seg[i - 1]
        if new:
            run = 0
            acc = 0.0
            tr = h[i] - l[i]
        else:
            tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        run += 1
        if run < n:
            acc += tr
        elif run == n:
            acc += tr
            prev = acc / n
            out[i] = prev
        else:
            prev = (prev * (n - 1) + tr) / n
            out[i] = prev
    return out


@njit(cache=True)
def _roll_max(x, seg, W):
    """Max over the last W rows (this one included) within a segment; NaN rows are skipped."""
    N = len(x)
    out = np.full(N, np.nan)
    dq = np.empty(N, np.int64)
    head = 0
    tail = 0
    for i in range(N):
        if i > 0 and seg[i] != seg[i - 1]:
            head = 0
            tail = 0
        while head < tail and dq[head] <= i - W:
            head += 1
        xi = x[i]
        if xi == xi:
            while head < tail and x[dq[tail - 1]] <= xi:
                tail -= 1
            dq[tail] = i
            tail += 1
        if head < tail:
            out[i] = x[dq[head]]
    return out


@njit(cache=True)
def _cum_max(x, seg):
    N = len(x)
    out = np.full(N, np.nan)
    cur = np.nan
    for i in range(N):
        if i > 0 and seg[i] != seg[i - 1]:
            cur = np.nan
        xi = x[i]
        if xi == xi and (cur != cur or xi > cur):
            cur = xi
        out[i] = cur
    return out


@njit(cache=True)
def _roll_min_full(x, seg, W):
    """Min over the last W bars within a segment, NaN unless all W bars exist and are finite."""
    N = len(x)
    out = np.full(N, np.nan)
    run = 0
    for i in range(N):
        if i > 0 and seg[i] == seg[i - 1]:
            run += 1
        else:
            run = 1
        if run >= W:
            m = np.inf
            ok = True
            for k in range(i - W + 1, i + 1):
                if x[k] != x[k]:
                    ok = False
                    break
                if x[k] < m:
                    m = x[k]
            if ok:
                out[i] = m
    return out


@njit(cache=True)
def _any_prior(flag, seg, W):
    """True where flag holds on one of the W previous rows of the same segment (this row excluded)."""
    N = len(flag)
    out = np.zeros(N, np.bool_)
    last = -1_000_000_000
    for i in range(N):
        if i > 0 and seg[i] != seg[i - 1]:
            last = -1_000_000_000
        if i - last <= W:
            out[i] = True
        if flag[i]:
            last = i
    return out


# ============================================================================ numba: the hourly loop
# float parameters
P_L, P_MMR, P_TAKER, P_MAKER, P_SLIP, P_SPOTFEE, P_COSTSIDE, P_A1, P_A2, P_TPR, P_TPFRAC, P_MINHOLD, \
    P_TRF, P_AVGF_L, P_AVGF_S, P_LCFG = range(16)
# int parameters
I_DIRMODE, I_ADDS, I_RULE6, I_EMODE, I_REENT, I_SFILL, I_CROSS, I_SPOTM, I_EDEL, I_XDEL, I_H0, I_H1, I_R15, \
    I_PMAX = range(14)
NIPR = 14
# position state (float)
S_Q, S_AVG, S_E1, S_S, S_TP, S_LU, S_IM, S_POSTED, S_RETD, S_COST, S_FUND, S_GROSS, S_FRAC, S_MLOCK, S_LIQ, \
    S_SIDE, S_EXPO = range(17)
# position outputs
PF_E1, PF_S, PF_TP, PF_LU, PF_XPX, PF_RET, PF_GROSS, PF_FEES, PF_FUND, PF_MAXF, PF_POSTED, PF_AVG, PF_LIQ0, \
    PF_EXPO, PF_LMAX = range(15)
NPF = 15
PI_SIDE, PI_SIGBAR, PI_EH, PI_XH, PI_RSN, PI_TPF, PI_LIQD, PI_OAE, PI_ATHO, PI_DEF, PI_NTR, PI_NCX, PI_RE, \
    PI_GIVEN, PI_EBAR, PI_XMIN, PI_LCAP, PI_XBAR, PI_EMIN = range(19)
NPI = 19
# fill kinds, exit reasons, signal fates
K_ENTRY, K_ADD, K_TP, K_EXIT, K_STOP, K_LIQ, K_DELIST, K_END = range(8)
KIND_NAMES = ["entry", "add", "tp", "exit", "stop", "liq", "delist", "end"]
R_STOP, R_MID, R_TPALL, R_LIQ, R_END, R_DELIST = range(6)
REASON_NAMES = ["stop", "mid", "tp_all", "liq", "window_end", "delist"]
F_ENTERED, F_RECHECK, F_BELOW_S, F_IN_POS, F_SUPERSEDED, F_PENDING_END, F_NOSTOP, F_DELIST, F_GIVEN_DROP = range(9)
FATE_NAMES = ["entered", "recheck_failed", "skipped_open_at_or_below_S", "in_position", "superseded",
              "pending_at_end", "no_stop", "cancelled_delist", "given_dropped"]
# log counters
(LG_SIG, LG_SIG_INPOS, LG_ATHONLY, LG_DEFERRED, LG_RECHECK, LG_BELOW_S, LG_ZERO_WIN, LG_R6, LG_R15,
 LG_CX_AVG, LG_CX_EXIT, LG_CX_TP, LG_LIQ, LG_DELIST, LG_GIVEN_DROP, LG_STRESS, LG_LCAP, LG_SUPERSEDED,
 LG_M1_STOP, LG_099, LG_GAP, LG_REENTRY, LG_TOUCH, LG_M1_TP, LG_POS, LG_NOSTOP, LG_ADDS) = range(27)
LOG_NAMES = ["signals", "signals_in_position", "ath_only_signals", "deferred_entries", "recheck_failed",
             "skipped_open_at_or_below_S", "zero_trade_window_skips", "rule6_suppressed", "rule15_not_acted",
             "adds_cancelled_below_avg", "adds_cancelled_exit_pending", "adds_cancelled_after_tp", "liquidations",
             "delist_closes", "given_dropped", "stops_failed_stress", "l_capped", "signals_superseded",
             "stops_minute_resolved", "stops_0p99S", "stops_gap_open", "reentry_signals", "touch_entries",
             "tp_minute_resolved", "positions", "no_stop_value", "adds_filled"]
NLG = 32


@njit(cache=True)
def _crate(h, is_tp, spot, prm, spotm):
    """All-in cost per side of a fill in hour h (fraction of notional)."""
    if prm[P_COSTSIDE] >= 0.0:
        return prm[P_COSTSIDE]
    if spotm or spot[h]:
        return prm[P_SPOTFEE] + (0.0 if is_tp else prm[P_SLIP])
    if is_tp:
        return prm[P_MAKER]
    return prm[P_TAKER] + prm[P_SLIP]


@njit(cache=True)
def _liq_px(st, mmr, iso):
    q = st[S_Q]
    if (not iso) or q <= 0.0:
        return -np.inf if st[S_SIDE] > 0 else np.inf
    avg = st[S_AVG]
    if st[S_SIDE] > 0:
        return avg - st[S_IM] / q + mmr * avg
    return avg + st[S_IM] / q - mmr * avg


@njit(cache=True)
def _lcap(prm, px, Sv, cr, mmr, side, addmode):
    """(L_used, L_max) of a new position (prereg R0 Liquidation: "L is capped per trade so that S sits at least 2
    points above the liquidation price of the full position after both adds"). L_max is the largest L with S at
    least LCAP_PTS x entry1 inside liq(full position), whose average entry is the mean of the planned tranche
    prices: (1 + 1.02 + 1.05) / 3 x entry1 for price adds (the prereg's 1.0233), entry1 for S4, and
    (3 + 0.07 / L_used) / 3 x entry1 for S5, whose ROE add levels 1 + 2% / L_used and 1 + 5% / L_used move with the
    capped leverage itself. S5's cap is therefore the fixed point L = min(L_cfg, L_max(L)); L_max increases with L,
    so the iteration from L_cfg decreases monotonically to the largest fixed point (contraction ~0.01 per step)."""
    Lc = prm[P_L]
    Lu = Lc
    lmax = np.inf
    for _ in range(200):
        if addmode == 1:
            A = (3.0 + side * 0.07 / Lu) / 3.0 * px
        elif side > 0:
            A = prm[P_AVGF_L] * px
        else:
            A = prm[P_AVGF_S] * px
        if A <= 0.0:
            break
        if side > 0:
            den = 1.0 + cr + mmr - (Sv - LCAP_PTS * px) / A
        else:
            den = (Sv + LCAP_PTS * px) / A - 1.0 + cr + mmr
        lmax = 1.0 / den if den > 0.0 else np.inf
        new = min(Lc, lmax)
        done = addmode != 1 or abs(new - Lu) <= 1e-15 * Lc
        Lu = new
        if done:
            break
    return Lu, lmax


@njit(cache=True)
def _rec_fill(FI, FF, cnt, pid, kind, h, minute, cause, px, frac, cost, dirn):
    k = cnt[0]
    if k < FI.shape[0]:
        FI[k, 0] = pid
        FI[k, 1] = kind
        FI[k, 2] = h
        FI[k, 3] = minute
        FI[k, 4] = cause
        FI[k, 5] = dirn
        FF[k, 0] = px
        FF[k, 1] = frac
        FF[k, 2] = cost
    cnt[0] = k + 1


@njit(cache=True)
def _add_tranche(st, frac, px, crate):
    """A tranche of `frac` of M notional at px: qty, average entry, margin and its costs."""
    q_new = frac / px
    q0 = st[S_Q]
    st[S_AVG] = (st[S_AVG] * q0 + px * q_new) / (q0 + q_new)
    st[S_Q] = q0 + q_new
    mg = frac / st[S_LU]
    cost = crate * frac
    st[S_POSTED] += mg
    st[S_MLOCK] += mg
    st[S_IM] += mg - cost
    st[S_COST] += cost
    st[S_FRAC] += frac
    return cost


@njit(cache=True)
def _partial(st, f, px, crate):
    """Close fraction f of the position at px (TP): proceeds and fee to the wallet, margin released pro rata."""
    q = st[S_Q] * f
    side = st[S_SIDE]
    pnl = side * q * (px - st[S_AVG])
    cost = crate * q * px
    st[S_RETD] += f * st[S_IM] + pnl - cost
    st[S_GROSS] += pnl
    st[S_COST] += cost
    st[S_IM] *= (1.0 - f)
    st[S_MLOCK] *= (1.0 - f)
    st[S_Q] -= q
    return cost, q * px


@njit(cache=True)
def _final(st, si, PF, PI, px, reason, h, minute, crate, liquidated, open_end):
    """Close everything at px (or lose the isolated margin when liquidated); write the position record."""
    pid = si[1]
    q = st[S_Q]
    side = st[S_SIDE]
    cost = 0.0
    notional = q * px
    if liquidated:
        pass                                    # the isolated margin balance is lost; nothing returns
    else:
        pnl = side * q * (px - st[S_AVG])
        cost = crate * q * px
        st[S_RETD] += st[S_IM] + pnl - cost
        st[S_GROSS] += pnl
        st[S_COST] += cost
    ret = st[S_RETD] - st[S_POSTED]
    PF[pid, PF_XPX] = px
    PF[pid, PF_RET] = ret
    PF[pid, PF_FEES] = st[S_COST]
    PF[pid, PF_FUND] = st[S_FUND]
    PF[pid, PF_GROSS] = ret + st[S_COST] + st[S_FUND]
    PF[pid, PF_MAXF] = st[S_FRAC]
    PF[pid, PF_POSTED] = st[S_POSTED]
    PF[pid, PF_AVG] = st[S_AVG]
    PF[pid, PF_EXPO] = st[S_EXPO]
    PI[pid, PI_XH] = h
    PI[pid, PI_RSN] = reason
    PI[pid, PI_LIQD] = 1 if liquidated else 0
    PI[pid, PI_OAE] = 1 if open_end else 0
    PI[pid, PI_XMIN] = minute
    PI[pid, PI_NTR] = si[4]
    PI[pid, PI_NCX] = si[15]
    PI[pid, PI_TPF] = si[3]
    st[S_Q] = 0.0
    si[0] = 0
    return cost, notional


@njit(cache=True)
def _loop(o, hi, lo, c, tr, tradable, spot, pend_end, mlo, mhi, mopen, fund, ent_ok, ext_ok, blk, allowed,
          stress, midnight, m1s, m1n, m1lo, m1hi, mo, mh, ml, mc, mtr,
          kh, freshL, lvlL, freshS, lvlS, athonly, aboveU, belowL, exitL, exitS, stopL, stopS, touchL, deferb,
          markc, gh, gd, prm, ipr):
    NB = len(kh)
    NG = len(gh)
    h0 = ipr[I_H0]
    h1 = ipr[I_H1]
    dirmode = ipr[I_DIRMODE]
    addmode = ipr[I_ADDS]
    r6 = ipr[I_RULE6]
    emode = ipr[I_EMODE]
    reent = ipr[I_REENT]
    sfill = ipr[I_SFILL]
    cross = ipr[I_CROSS] == 1
    spotm = ipr[I_SPOTM] == 1
    edel = ipr[I_EDEL]
    xdel = ipr[I_XDEL]
    r15 = ipr[I_R15] == 1
    iso = (not cross) and (not spotm)
    mmr = prm[P_MMR]
    trf = prm[P_TRF]
    tpfrac = prm[P_TPFRAC]
    has_adds = addmode != 2

    PMAX = ipr[I_PMAX]          # position buffer; on overflow the loop stops with ovf = True (the caller re-sizes)
    ovf = False
    PF = np.full((PMAX, NPF), np.nan)
    PI = np.full((PMAX, NPI), -1, np.int64)
    FMAX = 8 * PMAX + 16
    FI = np.full((FMAX, 6), -1, np.int64)
    FF = np.full((FMAX, 3), np.nan)
    fcnt = np.zeros(1, np.int64)
    EMAX = max(h1 - h0 + 2, 1)
    EI = np.zeros((EMAX, 2), np.int64)
    EF = np.zeros((EMAX, 3))
    ne = 0
    DMAX = EMAX // 24 + PMAX + 4
    DI = np.zeros((DMAX, 2), np.int64)
    DF = np.zeros((DMAX, 3))
    nd = 0
    SMAX = NB + NG + 4
    SG = np.full((SMAX, 7), -1, np.int64)       # bar, dir, fate, pid, given_h, athonly, reentry
    nsg = 0
    LG = np.zeros(NLG, np.int64)

    st = np.zeros(17)
    si = np.zeros(16, np.int64)   # 0 in, 1 pid, 2 entry_h, 3 tp_done, 4 n_tr, 5 add1_done, 6 add2_done, 7 add1_pend,
    #                               8 add2_pend, 9 add1_trig_h, 10 add2_trig_h, 11 exit_pend, 12 exit_from,
    #                               13 exit_ready, 14 exit_bar, 15 n_add_cancel
    npos = 0
    jb = 0
    last_bar = -1
    gi = 0
    pe = False
    pe_dir = 0
    pe_bar = -1
    pe_from = 0
    pe_def = False
    pe_given = -1
    pe_sig = -1
    pe_re = False
    reent_okL = False
    reent_okS = False
    t_lvl = np.nan
    t_bar = -1
    t_from = 0

    for h in range(h0, h1 + 1):
        # ---------------------------------------------------------------- completed bars (decisions at t_h)
        while jb < NB and kh[jb] <= h:
            j = jb
            jb += 1
            last_bar = j
            if kh[j] < h0:
                continue
            if not aboveU[j]:
                reent_okL = False
            if not belowL[j]:
                reent_okS = False
            if emode == 1:
                t_lvl = touchL[j]
                t_bar = j
                t_from = kh[j]
            is_fresh = freshL[j] or (dirmode == 1 and freshS[j])
            if si[0] == 1:
                if si[11] == 0:
                    side = st[S_SIDE]
                    ex = exitL[j] if side > 0 else exitS[j]
                    if ex:
                        if r15 and deferb[j]:
                            LG[LG_R15] += 1
                        elif r6 == 1 and (kh[j] - si[2]) < RULE6_H and \
                                ((side > 0 and markc[j] >= st[S_AVG]) or (side < 0 and markc[j] <= st[S_AVG])):
                            LG[LG_R6] += 1
                        elif r6 == 2 and (kh[j] - si[2]) < prm[P_MINHOLD]:
                            LG[LG_R6] += 1
                        else:
                            si[11] = 1
                            si[12] = kh[j] + xdel
                            si[13] = 0
                            si[14] = j
                if is_fresh:
                    if nsg >= SMAX:
                        ovf = True
                        break
                    LG[LG_SIG] += 1
                    LG[LG_SIG_INPOS] += 1
                    if freshL[j] and athonly[j]:
                        LG[LG_ATHONLY] += 1
                    SG[nsg, 0] = j
                    SG[nsg, 1] = 1 if freshL[j] else -1
                    SG[nsg, 2] = F_IN_POS
                    SG[nsg, 5] = 1 if (freshL[j] and athonly[j]) else 0
                    SG[nsg, 6] = 0
                    nsg += 1
            elif emode == 0:
                ndir = 0
                isre = False
                if freshL[j]:
                    ndir = 1
                elif dirmode == 1 and freshS[j]:
                    ndir = -1
                elif reent == 1 and reent_okL and lvlL[j]:
                    ndir = 1
                    isre = True
                elif reent == 1 and dirmode == 1 and reent_okS and lvlS[j]:
                    ndir = -1
                    isre = True
                if ndir != 0:
                    if nsg >= SMAX:
                        ovf = True
                        break
                    if isre:
                        LG[LG_REENTRY] += 1
                    else:
                        LG[LG_SIG] += 1
                        if ndir > 0 and athonly[j]:
                            LG[LG_ATHONLY] += 1
                    if pe:
                        LG[LG_SUPERSEDED] += 1
                        if pe_sig >= 0:
                            SG[pe_sig, 2] = F_SUPERSEDED
                    pe = True
                    pe_dir = ndir
                    pe_bar = j
                    pe_from = kh[j] + edel
                    pe_def = False
                    pe_given = -1
                    pe_re = isre
                    pe_sig = nsg
                    SG[nsg, 0] = j
                    SG[nsg, 1] = ndir
                    SG[nsg, 2] = F_PENDING_END
                    SG[nsg, 5] = 1 if (ndir > 0 and athonly[j]) else 0
                    SG[nsg, 6] = 1 if isre else 0
                    nsg += 1
            elif is_fresh:
                LG[LG_SIG] += 1
                if freshL[j] and athonly[j]:
                    LG[LG_ATHONLY] += 1
        if ovf:
            break
        # ---------------------------------------------------------------- given entries (decision at t_h)
        while gi < NG and gh[gi] <= h:
            g = gh[gi]
            gi += 1
            if g < h0:
                continue
            if nsg >= SMAX:
                ovf = True
                break
            SG[nsg, 0] = last_bar
            SG[nsg, 1] = gd[gi - 1]
            SG[nsg, 4] = g
            SG[nsg, 5] = 0
            SG[nsg, 6] = 0
            if si[0] == 1 or pe:
                LG[LG_GIVEN_DROP] += 1
                SG[nsg, 2] = F_GIVEN_DROP
            else:
                pe = True
                pe_dir = gd[gi - 1]
                pe_bar = last_bar
                pe_from = g + edel
                pe_def = False
                pe_given = g
                pe_re = False
                pe_sig = nsg
                SG[nsg, 2] = F_PENDING_END
            nsg += 1
        if ovf:
            break
        # ---------------------------------------------------------------- funding print at t_h (pre-open position)
        if si[0] == 1 and (not spotm) and fund[h] != 0.0:
            pay = st[S_SIDE] * fund[h] * st[S_Q] * mopen[h]
            st[S_FUND] += pay
            st[S_IM] -= pay
            st[S_LIQ] = _liq_px(st, mmr, iso)
        # ---------------------------------------------------------------- 00:00 UTC mark (account equity)
        if midnight[h] and si[0] == 1 and nd < DMAX:
            P = c[h - 1] if h > 0 else o[h]
            DI[nd, 0] = si[1]
            DI[nd, 1] = h
            DF[nd, 0] = st[S_RETD] - st[S_POSTED] + st[S_IM] + st[S_SIDE] * st[S_Q] * (P - st[S_AVG])
            DF[nd, 1] = st[S_MLOCK]
            DF[nd, 2] = st[S_Q] * P
            nd += 1
        if si[0] == 1 and si[11] == 1 and si[13] == 0 and h >= si[12] and ext_ok[h]:
            si[13] = 1
        live = tr[h] > 0 and tradable[h]
        # ---------------------------------------------------------------- fills at the open
        if live and si[0] == 1 and si[11] == 1 and si[13] == 1:            # trend exit
            pid = si[1]
            cr = _crate(h, False, spot, prm, spotm)
            cost, notl = _final(st, si, PF, PI, o[h], R_MID, h, -1, cr, False, False)
            PI[pid, PI_XBAR] = si[14]
            _rec_fill(FI, FF, fcnt, pid, K_EXIT, h, -1, kh[si[14]], o[h], notl, cost, -int(st[S_SIDE]))
        if live and si[0] == 1 and (si[7] == 1 or si[8] == 1):              # adds
            for k in range(2):
                if si[7 + k] == 1:
                    side = st[S_SIDE]
                    if si[3] == 1:
                        LG[LG_CX_TP] += 1
                        si[15] += 1
                    elif si[11] == 1:
                        LG[LG_CX_EXIT] += 1
                        si[15] += 1
                    elif (side > 0 and o[h] < st[S_AVG]) or (side < 0 and o[h] > st[S_AVG]):
                        LG[LG_CX_AVG] += 1
                        si[15] += 1
                    else:
                        cr = _crate(h, False, spot, prm, spotm)
                        cost = _add_tranche(st, trf, o[h], cr)
                        si[4] += 1
                        si[5 + k] = 1
                        LG[LG_ADDS] += 1
                        _rec_fill(FI, FF, fcnt, si[1], K_ADD, h, -1, si[9 + k], o[h], trf, cost, int(side))
                        st[S_LIQ] = _liq_px(st, mmr, iso)
                    si[7 + k] = 0
        if si[0] == 0 and pe and h >= pe_from and ent_ok[h] and allowed[h]:  # first tranche at a window
            if blk[h]:
                if not pe_def:
                    LG[LG_DEFERRED] += 1
                pe_def = True
            elif not live:
                LG[LG_ZERO_WIN] += 1
            else:
                j = last_bar
                ok = j >= 0
                if ok and emode == 0:
                    ok = lvlL[j] if pe_dir > 0 else lvlS[j]
                if not ok:
                    LG[LG_RECHECK] += 1
                    SG[pe_sig, 2] = F_RECHECK
                    pe = False
                else:
                    Sv = stopL[j] if pe_dir > 0 else stopS[j]
                    if not (Sv == Sv):
                        LG[LG_NOSTOP] += 1
                        SG[pe_sig, 2] = F_NOSTOP
                        pe = False
                    elif (pe_dir > 0 and o[h] <= Sv) or (pe_dir < 0 and o[h] >= Sv):
                        LG[LG_BELOW_S] += 1
                        SG[pe_sig, 2] = F_BELOW_S
                        pe = False
                    else:
                        if npos >= PMAX:
                            ovf = True
                            break
                        px = o[h]
                        cr = _crate(h, False, spot, prm, spotm)
                        # leverage cap: S at least 2 points of entry1 beyond liq(full post-add position)
                        Lu = prm[P_L]
                        lmax = np.inf
                        if not spotm:
                            Lu, lmax = _lcap(prm, px, Sv, cr, mmr, float(pe_dir), addmode)
                            if Lu < prm[P_L]:
                                LG[LG_LCAP] += 1
                        pid = npos
                        npos += 1
                        LG[LG_POS] += 1
                        st[:] = 0.0
                        si[:] = 0
                        st[S_SIDE] = pe_dir
                        st[S_LU] = Lu
                        st[S_E1] = px
                        st[S_S] = Sv
                        st[S_TP] = px + TP_R * (px - Sv) if tpfrac > 0 else np.nan
                        st[S_AVG] = px
                        cost = _add_tranche(st, trf, px, cr)
                        st[S_LIQ] = _liq_px(st, mmr, iso)
                        si[0] = 1
                        si[1] = pid
                        si[2] = h
                        si[4] = 1
                        PF[pid, PF_E1] = px
                        PF[pid, PF_S] = Sv
                        PF[pid, PF_TP] = st[S_TP]
                        PF[pid, PF_LU] = Lu
                        PF[pid, PF_LIQ0] = st[S_LIQ]
                        PF[pid, PF_LMAX] = lmax
                        PI[pid, PI_SIDE] = pe_dir
                        PI[pid, PI_SIGBAR] = pe_bar
                        PI[pid, PI_EH] = h
                        PI[pid, PI_ATHO] = 1 if (pe_given < 0 and pe_dir > 0 and pe_bar >= 0 and athonly[pe_bar]
                                                 and not pe_re) else 0
                        PI[pid, PI_DEF] = 1 if pe_def else 0
                        PI[pid, PI_RE] = 1 if pe_re else 0
                        PI[pid, PI_GIVEN] = pe_given
                        PI[pid, PI_EBAR] = j
                        PI[pid, PI_LCAP] = 1 if Lu < prm[P_L] else 0
                        cause = pe_given if pe_given >= 0 else kh[pe_bar]
                        _rec_fill(FI, FF, fcnt, pid, K_ENTRY, h, -1, cause, px, trf, cost, pe_dir)
                        SG[pe_sig, 2] = F_ENTERED
                        SG[pe_sig, 3] = pid
                        pe = False
                        reent_okL = False
                        reent_okS = False
        # ---------------------------------------------------------------- touch arm (H4): intrabar buy-stop
        scan0 = m1s[h]                                                # first minute the intrabar scan reads
        if live and emode == 1 and si[0] == 0 and t_bar >= 0 and h >= t_from and allowed[h] and (t_lvl == t_lvl) \
                and (hi[h] > t_lvl or (m1s[h] >= 0 and m1hi[h] > t_lvl)):
            tmin = -2                                                 # resolved on the hourly bar
            px = max(t_lvl, o[h])
            if m1s[h] >= 0:                                           # resolved on minutes: the first one above
                tmin = -3
                for k in range(m1s[h], m1s[h] + m1n[h]):
                    if mtr[k] > 0 and mh[k] > t_lvl:
                        tmin = k
                        px = max(t_lvl, mo[k])
                        scan0 = k
                        break
            Sv = stopL[t_bar]
            if tmin != -3 and Sv == Sv and px > Sv:
                if npos >= PMAX:
                    ovf = True
                    break
                cr = _crate(h, False, spot, prm, spotm)
                Lu = prm[P_L]
                lmax = np.inf
                if not spotm:
                    Lu, lmax = _lcap(prm, px, Sv, cr, mmr, 1.0, addmode)
                    if Lu < prm[P_L]:
                        LG[LG_LCAP] += 1
                pid = npos
                npos += 1
                LG[LG_POS] += 1
                LG[LG_TOUCH] += 1
                st[:] = 0.0
                si[:] = 0
                st[S_SIDE] = 1.0
                st[S_LU] = Lu
                st[S_E1] = px
                st[S_S] = Sv
                st[S_TP] = px + TP_R * (px - Sv) if tpfrac > 0 else np.nan
                st[S_AVG] = px
                cost = _add_tranche(st, trf, px, cr)
                st[S_LIQ] = _liq_px(st, mmr, iso)
                si[0] = 1
                si[1] = pid
                si[2] = h
                si[4] = 1
                PF[pid, PF_E1] = px
                PF[pid, PF_S] = Sv
                PF[pid, PF_TP] = st[S_TP]
                PF[pid, PF_LU] = Lu
                PF[pid, PF_LIQ0] = st[S_LIQ]
                PF[pid, PF_LMAX] = lmax
                PI[pid, PI_SIDE] = 1
                PI[pid, PI_SIGBAR] = t_bar
                PI[pid, PI_EH] = h
                PI[pid, PI_ATHO] = 0
                PI[pid, PI_DEF] = 0
                PI[pid, PI_RE] = 0
                PI[pid, PI_GIVEN] = -1
                PI[pid, PI_EBAR] = t_bar
                PI[pid, PI_LCAP] = 1 if Lu < prm[P_L] else 0
                PI[pid, PI_EMIN] = tmin
                _rec_fill(FI, FF, fcnt, pid, K_ENTRY, h, tmin, kh[t_bar], px, trf, cost, 1)
        # ---------------------------------------------------------------- exposure during the hour
        if si[0] == 1 and ne < EMAX:
            side = st[S_SIDE]
            pref = o[h]
            if PI[si[1], PI_EH] == h and PI[si[1], PI_EMIN] != -1:      # touch entry inside this hour
                pref = st[S_E1]
            EI[ne, 0] = si[1]
            EI[ne, 1] = h
            EF[ne, 0] = side * st[S_Q] * pref
            st[S_EXPO] += side * st[S_Q] * pref
            if not (tr[h] > 0 and tradable[h]):
                pm = o[h]                                             # outage: no extreme counts (as liquidation)
            elif side > 0:
                pm = mlo[h] if mlo[h] == mlo[h] else lo[h]
            else:
                pm = mhi[h] if mhi[h] == mhi[h] else hi[h]
            EF[ne, 1] = st[S_RETD] - st[S_POSTED] + st[S_IM] + side * st[S_Q] * (pm - st[S_AVG])
            EF[ne, 2] = mmr * st[S_Q] * st[S_AVG]
            ne += 1
        # ---------------------------------------------------------------- intrabar: stop, take-profit, liquidation
        if live and si[0] == 1:
            pid = si[1]
            side = st[S_SIDE]
            Sv = st[S_S]
            stop_on = not stress[h]
            use_m1 = m1s[h] >= 0
            if use_m1:
                lo_t = m1lo[h]
                hi_t = m1hi[h]
                if scan0 > m1s[h]:                                    # touch entry inside the hour: later minutes
                    lo_t = np.inf
                    hi_t = -np.inf
                    for k in range(scan0, m1s[h] + m1n[h]):
                        if mtr[k] > 0:
                            lo_t = min(lo_t, ml[k])
                            hi_t = max(hi_t, mh[k])
            else:
                lo_t = lo[h]
                hi_t = hi[h]
            has_tp = tpfrac > 0 and si[3] == 0
            TPv = st[S_TP]
            if side > 0:
                s_raw = lo_t <= Sv
                t_raw = has_tp and hi_t >= TPv
                pm = mlo[h] if mlo[h] == mlo[h] else lo[h]
                l_raw = iso and pm <= st[S_LIQ]
            else:
                s_raw = hi_t >= Sv
                t_raw = has_tp and lo_t <= TPv
                pm = mhi[h] if mhi[h] == mhi[h] else hi[h]
                l_raw = iso and pm >= st[S_LIQ]
            if s_raw and not stop_on:
                LG[LG_STRESS] += 1
            s_trig = s_raw and stop_on
            done = False
            if l_raw and not s_trig:
                # mark price reached the liquidation price without the stop triggering: liquidated
                lq = st[S_LIQ]
                _final(st, si, PF, PI, lq, R_LIQ, h, -2, 0.0, True, False)
                _rec_fill(FI, FF, fcnt, pid, K_LIQ, h, -2, PI[pid, PI_EH], lq, 0.0, 0.0, -int(side))
                LG[LG_LIQ] += 1
                done = True
            elif use_m1 and (s_trig or t_raw):
                for k in range(scan0, m1s[h] + m1n[h]):
                    if mtr[k] <= 0:
                        continue
                    if side > 0:
                        sh = stop_on and ml[k] <= Sv
                        th = has_tp and si[3] == 0 and mh[k] >= TPv
                    else:
                        sh = stop_on and mh[k] >= Sv
                        th = has_tp and si[3] == 0 and ml[k] <= TPv
                    if sh:
                        if sfill == 1:
                            fp = Sv
                        elif side > 0:
                            fp = min(Sv, mc[k])
                        else:
                            fp = max(Sv, mc[k])
                        LG[LG_M1_STOP] += 1
                        if iso and ((side > 0 and fp < st[S_LIQ]) or (side < 0 and fp > st[S_LIQ])):
                            lq = st[S_LIQ]
                            _final(st, si, PF, PI, lq, R_LIQ, h, k, 0.0, True, False)
                            _rec_fill(FI, FF, fcnt, pid, K_LIQ, h, k, PI[pid, PI_EH], lq, 0.0, 0.0, -int(side))
                            LG[LG_LIQ] += 1
                        else:
                            cr = _crate(h, False, spot, prm, spotm)
                            cost, notl = _final(st, si, PF, PI, fp, R_STOP, h, k, cr, False, False)
                            _rec_fill(FI, FF, fcnt, pid, K_STOP, h, k, PI[pid, PI_EH], fp, notl, cost, -int(side))
                        done = True
                        break
                    if th:
                        if side > 0:
                            tpx = mo[k] if mo[k] >= TPv else TPv
                        else:
                            tpx = mo[k] if mo[k] <= TPv else TPv
                        LG[LG_M1_TP] += 1
                        cr = _crate(h, True, spot, prm, spotm)
                        if tpfrac >= 1.0:
                            cost, notl = _final(st, si, PF, PI, tpx, R_TPALL, h, k, cr, False, False)
                            _rec_fill(FI, FF, fcnt, pid, K_TP, h, k, PI[pid, PI_EH], tpx, notl, cost, -int(side))
                            done = True
                            break
                        cost, notl = _partial(st, tpfrac, tpx, cr)
                        si[3] = 1
                        si[7] = 0
                        si[8] = 0
                        _rec_fill(FI, FF, fcnt, pid, K_TP, h, k, PI[pid, PI_EH], tpx, notl, cost, -int(side))
                        st[S_LIQ] = _liq_px(st, mmr, iso)
            elif s_trig:
                if sfill == 1:
                    fp = Sv
                elif side > 0:
                    if o[h] <= Sv:
                        fp = o[h]
                        LG[LG_GAP] += 1
                    elif lo[h] < GAP_LOW * Sv:
                        fp = GAP_FILL * Sv
                        LG[LG_099] += 1
                    else:
                        fp = Sv
                else:
                    if o[h] >= Sv:
                        fp = o[h]
                        LG[LG_GAP] += 1
                    elif hi[h] > (2.0 - GAP_LOW) * Sv:
                        fp = (2.0 - GAP_FILL) * Sv
                        LG[LG_099] += 1
                    else:
                        fp = Sv
                if iso and ((side > 0 and fp < st[S_LIQ]) or (side < 0 and fp > st[S_LIQ])):
                    lq = st[S_LIQ]
                    _final(st, si, PF, PI, lq, R_LIQ, h, -2, 0.0, True, False)
                    _rec_fill(FI, FF, fcnt, pid, K_LIQ, h, -2, PI[pid, PI_EH], lq, 0.0, 0.0, -int(side))
                    LG[LG_LIQ] += 1
                else:
                    cr = _crate(h, False, spot, prm, spotm)
                    cost, notl = _final(st, si, PF, PI, fp, R_STOP, h, -2, cr, False, False)
                    _rec_fill(FI, FF, fcnt, pid, K_STOP, h, -2, PI[pid, PI_EH], fp, notl, cost, -int(side))
                done = True
            elif t_raw:
                if side > 0:
                    tpx = o[h] if o[h] >= TPv else TPv
                else:
                    tpx = o[h] if o[h] <= TPv else TPv
                cr = _crate(h, True, spot, prm, spotm)
                if tpfrac >= 1.0:
                    cost, notl = _final(st, si, PF, PI, tpx, R_TPALL, h, -2, cr, False, False)
                    _rec_fill(FI, FF, fcnt, pid, K_TP, h, -2, PI[pid, PI_EH], tpx, notl, cost, -int(side))
                    done = True
                else:
                    cost, notl = _partial(st, tpfrac, tpx, cr)
                    si[3] = 1
                    si[7] = 0
                    si[8] = 0
                    _rec_fill(FI, FF, fcnt, pid, K_TP, h, -2, PI[pid, PI_EH], tpx, notl, cost, -int(side))
                    st[S_LIQ] = _liq_px(st, mmr, iso)
            if done and si[0] == 0:
                reent_okL = reent == 1 and side > 0
                reent_okS = reent == 1 and side < 0
        # ---------------------------------------------------------------- the hour's close
        if si[0] == 1 and pend_end[h]:
            pid = si[1]
            side = st[S_SIDE]
            cr = _crate(h, False, spot, prm, spotm)
            cost, notl = _final(st, si, PF, PI, c[h], R_DELIST, h, -2, cr, False, False)
            _rec_fill(FI, FF, fcnt, pid, K_DELIST, h, -2, h, c[h], notl, cost, -int(side))
            LG[LG_DELIST] += 1
        if pend_end[h] and pe:
            SG[pe_sig, 2] = F_DELIST
            pe = False
        if live and si[0] == 1 and has_adds and si[3] == 0:
            side = st[S_SIDE]
            e1 = st[S_E1]
            if addmode == 1:
                a1 = 1.0 + side * 0.02 / st[S_LU]
                a2 = 1.0 + side * 0.05 / st[S_LU]
            else:
                a1 = prm[P_A1] if side > 0 else 2.0 - prm[P_A1]
                a2 = prm[P_A2] if side > 0 else 2.0 - prm[P_A2]
            if side > 0:
                if si[5] == 0 and si[7] == 0 and c[h] >= a1 * e1:
                    si[7] = 1
                    si[9] = h + 1
                if si[6] == 0 and si[8] == 0 and c[h] >= a2 * e1:
                    si[8] = 1
                    si[10] = h + 1
            else:
                if si[5] == 0 and si[7] == 0 and c[h] <= a1 * e1:
                    si[7] = 1
                    si[9] = h + 1
                if si[6] == 0 and si[8] == 0 and c[h] <= a2 * e1:
                    si[8] = 1
                    si[10] = h + 1
        if h == h1 and si[0] == 1:                                           # window end: marked, no costs
            pid = si[1]
            _final(st, si, PF, PI, c[h], R_END, h, -2, 0.0, False, True)
            _rec_fill(FI, FF, fcnt, pid, K_END, h, -2, h, c[h], 0.0, 0.0, 0)
    return (PF[:npos], PI[:npos], FI[:min(fcnt[0], FMAX)], FF[:min(fcnt[0], FMAX)], EI[:ne], EF[:ne],
            DI[:nd], DF[:nd], SG[:nsg], LG, fcnt[0], ovf)


# ============================================================================ preparation (cached)
_PREP: dict = {}
_PREP_ORDER: list = []
_PREP_MAX = 24                 # coins kept prepared (an S12 top-10 cell touches up to ~50 coins over 2020-2026)
_SIG_MAX = 4                   # signal configurations kept per coin (1-hour bars: ~16 MB each)


def _col(df, name, default, dtype=float):
    if name in df.columns:
        return df[name].to_numpy(dtype)
    return np.full(len(df), default, dtype)


@njit(cache=True)
def _mix64(hsh, u):
    """FNV-1a style mixing of 64-bit words: each step x -> (x ^ u_i) * P (P odd) is a bijection of x and of u_i, so
    changing any single word always changes the result."""
    P = np.uint64(0x100000001B3)
    for i in range(len(u)):
        hsh = (hsh ^ u[i]) * P
    return hsh


def _words(a) -> np.ndarray:
    a = np.asarray(a)
    if a.dtype.kind in "fiuM" and a.dtype.itemsize == 8:
        return np.ascontiguousarray(a).view(np.uint64)
    if a.dtype.kind in "biu":
        return a.astype(np.uint64)
    if a.dtype.kind == "f":
        return a.astype(np.float64).view(np.uint64)
    return pd.util.hash_array(np.asarray(a, dtype=object)).astype(np.uint64)


def _fingerprint(df: pd.DataFrame, cols=None) -> tuple:
    """Content fingerprint of an injected frame: its shape, index, column names / dtypes and every value of `cols`
    (all columns when None). prepare() re-checks it on every cache hit, so a frame changed in place is
    re-prepared instead of mixing its new prices (views) with cached signal arrays."""
    cols = list(df.columns) if cols is None else [c for c in cols if c in df.columns]
    hsh = np.uint64(0xCBF29CE484222325)
    ix = df.index
    hsh = np.uint64(_mix64(hsh, _words(ix.asi8 if isinstance(ix, pd.DatetimeIndex) else ix.to_numpy())))
    for c in cols:
        hsh = np.uint64(_mix64(hsh, _words(df[c].to_numpy())))
    return (df.shape, str(getattr(ix, "tz", None)), tuple((str(c), str(df[c].dtype)) for c in cols), int(hsh))


_M1_FP_COLS = ("open", "high", "low", "close", "trades")          # the minute columns prepare() reads


def _normalize_hours(hours: pd.DataFrame) -> pd.DataFrame:
    """Fill the columns an injected frame may lack (sig_* = traded, live, tradable, funding 0, mark NaN)."""
    h = hours
    ix = pd.DatetimeIndex(h.index)
    ix = (ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")).as_unit("ns")
    need = [c for c in ("sig_open", "sig_high", "sig_low", "sig_close", "trades", "live", "sig_live", "seg")
            if c not in h.columns]
    if not need and ix.equals(h.index) and str(h.index.dtype) == "datetime64[ns, UTC]":
        return h
    h = h.copy()
    h.index = ix
    h.index.name = "open_time"
    for a in bd.PX:
        if "sig_" + a not in h.columns:
            h["sig_" + a] = h[a]
    if "trades" not in h.columns:
        h["trades"] = 1
    if "live" not in h.columns:
        h["live"] = True
    if "sig_live" not in h.columns:
        h["sig_live"] = h["live"]
    if "seg" not in h.columns:
        h["seg"] = 0
    return h


def prepare(sym: str, hours: pd.DataFrame | None = None, minutes: pd.DataFrame | None = None) -> dict:
    """Arrays for one coin: hourly series, New York clock, minute map, and a cache of signal arrays. Cached by
    (sym, identity of the injected frames) and, for injected frames, re-validated on every hit by a content
    fingerprint (_fingerprint): a frame changed in place since it was prepared is prepared again, with fresh
    signal arrays. Loaded frames (hours / minutes None) are bb_data's private copies, which no caller can reach."""
    key = (sym, None if hours is None else id(hours), None if minutes is None else id(minutes))
    hfp = None if hours is None else _fingerprint(hours)
    mfp = None if minutes is None else _fingerprint(minutes, _M1_FP_COLS)
    hit = _PREP.get(key)
    if hit is not None:
        if (hours is None or (hit["_hours_obj"] is hours and hit["_hours_fp"] == hfp)) and \
                (minutes is None or (hit["_minutes_obj"] is minutes and hit["_minutes_fp"] == mfp)):
            return hit
        _PREP.pop(key, None)                                          # changed in place (or a recycled id)
        if key in _PREP_ORDER:
            _PREP_ORDER.remove(key)
    hours_obj, minutes_obj = hours, minutes
    injected = hours is not None
    if hours is None:
        hours = bd.coin_hours(sym)
    hours = _normalize_hours(hours)
    idx = pd.DatetimeIndex(hours.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    idx = idx.tz_convert("UTC").as_unit("ns")
    t = idx.asi8
    if len(t) > 1 and not (np.diff(t) == H_NS).all():
        raise ValueError(f"{sym}: hours must be a gap-free hourly index")
    N = len(t)
    P = {"sym": sym, "t": t, "index": idx, "hours": hours, "N": N}
    P["o"], P["hi"], P["lo"], P["c"] = (hours[a].to_numpy(float) for a in bd.PX)
    P["tr"] = _col(hours, "trades", 1, np.int64)
    P["tradable"] = _col(hours, "tradable", True, bool)
    P["spot"] = _col(hours, "spot_only", False, bool)
    P["pend_end"] = _col(hours, "perp_end", False, bool)
    P["mlo"] = _col(hours, "mark_low", np.nan)
    P["mhi"] = _col(hours, "mark_high", np.nan)
    mo_ = _col(hours, "mark_open", np.nan)
    P["mopen"] = np.where(np.isfinite(mo_), mo_, P["o"])
    mc_ = _col(hours, "mark_close", np.nan)
    P["mclose"] = np.where(np.isfinite(mc_), mc_, P["c"])
    P["fund"] = np.nan_to_num(_col(hours, "funding", 0.0))
    ny = bd.ny_clock(idx)
    P["ny_hour"] = ny["ny_hour"].to_numpy(np.int64)
    P["ny_wd"] = ny["ny_weekday"].to_numpy(np.int64)
    P["utc_hour"] = np.asarray(idx.hour, np.int64)
    P["utc_wd"] = np.asarray(idx.weekday, np.int64)
    P["midnight"] = P["utc_hour"] == 0
    # one-minute bars: injected, or the archive's for M1 coins when hours were not injected
    m1s = np.full(N, -1, np.int64)
    m1n = np.zeros(N, np.int64)
    m1lo = np.full(N, np.inf)
    m1hi = np.full(N, -np.inf)
    mo = mh = ml = mc = np.zeros(0)
    mtr = np.zeros(0, np.int64)
    mt = np.zeros(0, np.int64)
    if minutes is None and not injected and sym in bd.M1_COINS:
        minutes = bd.minutes(sym, M1_FROM, bd.END + pd.Timedelta("59min"))
    if minutes is not None and len(minutes):
        mi = pd.DatetimeIndex(minutes.index)
        mi = (mi.tz_localize("UTC") if mi.tz is None else mi.tz_convert("UTC")).as_unit("ns")
        mt_all = mi.asi8
        keep = (mt_all >= t[0]) & (mt_all < t[-1] + H_NS)
        mt = mt_all[keep]
        mo, mh, ml, mc = (minutes[a].to_numpy(float)[keep] for a in bd.PX)
        mtr = (minutes["trades"].to_numpy(np.int64) if "trades" in minutes.columns
               else np.ones(len(mi), np.int64))[keep]
        if len(mt) and not (np.diff(mt) > 0).all():
            raise ValueError(f"{sym}: minutes must be sorted and unique")
        hp = (mt - t[0]) // H_NS
        u, first, cnt = np.unique(hp, return_index=True, return_counts=True)
        m1s[u] = first
        m1n[u] = cnt
        lv = mtr > 0
        lo_l = np.where(lv, ml, np.inf)
        hi_l = np.where(lv, mh, -np.inf)
        m1lo[u] = np.minimum.reduceat(lo_l, first)
        m1hi[u] = np.maximum.reduceat(hi_l, first)
    # hours whose live minutes disagree with the hourly bar on the high or the low by more than half a tick (data
    # inventory section 5: "Prefer the hourly files for these hours"; also hours with trades whose minutes are all
    # zero-trade) are resolved on the hourly bar, not on minutes
    tick = bd.TICK.get(str(sym).upper())
    tol = 0.5 * tick if tick else 1e-9 * np.maximum(np.abs(P["hi"]), 1e-12)
    with np.errstate(invalid="ignore"):
        agree = (np.abs(m1lo - P["lo"]) <= tol) & (np.abs(m1hi - P["hi"]) <= tol)
    fb = (m1s >= 0) & (P["tr"] > 0) & ~agree
    m1s[fb] = -1
    m1n[fb] = 0
    m1lo[fb] = np.inf
    m1hi[fb] = -np.inf
    P["m1_fallback"] = np.flatnonzero(fb)
    P.update(m1s=m1s, m1n=m1n, m1lo=m1lo, m1hi=m1hi, mo=mo, mh=mh, ml=ml, mc=mc, mtr=mtr, mt=mt)
    P["_sig"] = {}
    P["_hours_obj"], P["_hours_fp"] = hours_obj, hfp
    P["_minutes_obj"], P["_minutes_fp"] = minutes_obj, mfp
    _PREP[key] = P
    _PREP_ORDER.append(key)
    while len(_PREP_ORDER) > _PREP_MAX:
        old = _PREP_ORDER.pop(0)
        _PREP.pop(old, None)
    return P


def clear_cache():
    _PREP.clear()
    _PREP_ORDER.clear()


_BPD = {"1d": 1, "4h": 6, "1h": 24, "1w": 1 / 7}


def _signals(P: dict, cfg: Cfg) -> dict:
    """Per signal bar: known hour, fresh / level conditions both sides, exits, stops, touch level, flags."""
    key = (cfg.bars, cfg.bb_n, float(cfg.bb_k), cfg.near_high, cfg.squeeze, cfg.stop, cfg.midline)
    if key in P["_sig"]:
        out = P["_sig"].pop(key)                                      # most recently used last
        P["_sig"][key] = out
        return out
    hours = P["hours"]
    t, N = P["t"], P["N"]
    B = bd.bars_from_hours(hours, cfg.bars, "sig")
    D = B if cfg.bars == "1d" else bd.bars_from_hours(hours, "1d", "sig")
    nb = len(B)
    Cl = B["close"].to_numpy(float)
    Hh = B["high"].to_numpy(float)
    Ll = B["low"].to_numpy(float)
    seg = B["seg"].to_numpy(np.int64)
    ka = pd.DatetimeIndex(B["known_at"]).as_unit("ns").asi8 if nb else np.zeros(0, np.int64)
    kh = (ka - t[0]) // H_NS
    lh = np.clip(kh - 1, 0, N - 1)                                    # the bar's last hour
    sma, sd = _roll_sma_sd(Cl, seg, int(cfg.bb_n))
    ub = sma + cfg.bb_k * sd
    lb = sma - cfg.bb_k * sd
    # the stop, the trend exit and S9's band stop: R0's SMA20 / BB(20, 2) ("sma20", choice 1), or the row's own band
    if cfg.midline == "bb":
        mid, mub, mlb = sma, ub, lb
    else:
        msma, msd = (sma, sd) if int(cfg.bb_n) == MID_N else _roll_sma_sd(Cl, seg, MID_N)
        mid, mub, mlb = msma, msma + MID_K * msd, msma - MID_K * msd
    atr = _atr_wilder(Hh, Ll, Cl, seg, 14)
    # hourly signal highs / lows (live rows only) for the near-high look-backs and ATH, within segments
    hseg = _col(hours, "seg", 0, np.int64)
    slive = _col(hours, "sig_live", True, bool)
    sh = np.where(slive, hours["sig_high"].to_numpy(float), np.nan)
    sl = np.where(slive, hours["sig_low"].to_numpy(float), np.nan)

    def at_bar(x):
        return x[lh] if nb else np.zeros(0)

    hi60 = at_bar(_roll_max(sh, hseg, 60 * 24))
    lo60 = -at_bar(_roll_max(-sl, hseg, 60 * 24))
    ath = at_bar(_cum_max(sh, hseg))
    atl = -at_bar(_cum_max(-sl, hseg))
    # completed daily bars of the same segment up to this bar's close (warm-up 60 / 365)
    dk = pd.DatetimeIndex(D["known_at"]).as_unit("ns").asi8 if len(D) else np.zeros(0, np.int64)
    dseg = D["seg"].to_numpy(np.int64) if len(D) else np.zeros(0, np.int64)
    cnt = np.zeros(nb, np.int64)
    for s in np.unique(seg):
        ds = np.sort(dk[dseg == s])
        m = seg == s
        cnt[m] = np.searchsorted(ds, ka[m], side="right")
    warm = cnt >= 60
    w365 = cnt >= 365
    nh = cfg.near_high
    with np.errstate(invalid="ignore"):
        if nh == "r0":
            near60 = Cl >= 0.95 * hi60
            nearL = near60 | (w365 & (Cl >= 0.90 * ath))
            nearS = Cl <= 1.05 * lo60
            tl = (ub >= 0.95 * hi60) | (w365 & (ub >= 0.90 * ath))
        elif nh == "off":
            near60 = np.ones(nb, bool)
            nearL = nearS = tl = np.ones(nb, bool)
        elif nh == "20d2":
            hi20 = at_bar(_roll_max(sh, hseg, 20 * 24))
            lo20 = -at_bar(_roll_max(-sl, hseg, 20 * 24))
            near60 = nearL = Cl >= 0.98 * hi20
            nearS = Cl <= 1.02 * lo20
            tl = ub >= 0.98 * hi20
        elif nh == "365d10":
            hi365 = at_bar(_roll_max(sh, hseg, 365 * 24))
            lo365 = -at_bar(_roll_max(-sl, hseg, 365 * 24))
            near60 = nearL = w365 & (Cl >= 0.90 * hi365)
            nearS = w365 & (Cl <= 1.10 * lo365)
            tl = w365 & (ub >= 0.90 * hi365)
        else:                                                         # ath10
            near60 = nearL = w365 & (Cl >= 0.90 * ath)
            nearS = w365 & (Cl <= 1.10 * atl)
            tl = w365 & (ub >= 0.90 * ath)
        aboveU = Cl > ub
        belowL = Cl < lb
        if cfg.squeeze:
            bpd = _BPD[cfg.bars]
            bw = (ub - lb) / sma
            low = _roll_min_full(bw, seg, max(int(round(125 * bpd)), 1))
            cond = bw <= 1.10 * low
            sq = _any_prior(cond, seg, max(int(round(10 * bpd)), 1))
        else:
            sq = np.ones(nb, bool)
        lvlL = aboveU & nearL & warm & sq
        lvlS = belowL & nearS & warm & sq
        prev_ok = np.r_[False, seg[1:] == seg[:-1]] if nb else np.zeros(0, bool)
        pC = np.r_[np.nan, Cl[:-1]] if nb else np.zeros(0)
        pU = np.r_[np.nan, ub[:-1]] if nb else np.zeros(0)
        pL = np.r_[np.nan, lb[:-1]] if nb else np.zeros(0)
        freshL = lvlL & prev_ok & (pC <= pU)
        freshS = lvlS & prev_ok & (pC >= pL)
        athonly = (nh == "r0") & freshL & ~near60
        exitL = Cl < mid
        exitS = Cl > mid
        if cfg.stop == "r0":
            stopL, stopS = mid - atr, mid + atr
        elif cfg.stop == "lower_band":
            stopL, stopS = mlb, mub
        else:
            stopL, stopS = mid - 2.5 * atr, mid + 2.5 * atr
        touch = np.where(tl & warm & np.isfinite(ub), ub, np.nan)
        near_r0L = (Cl >= 0.95 * hi60) | (w365 & (Cl >= 0.90 * ath))     # R0's near-high rule (H5's indicator)
        near_r0S = Cl <= 1.05 * lo60
    lab = pd.DatetimeIndex(B.index)
    out = {"label": lab, "known_at": ka, "kh": kh.astype(np.int64),
           "freshL": freshL.astype(bool), "lvlL": lvlL.astype(bool), "freshS": freshS.astype(bool),
           "lvlS": lvlS.astype(bool), "athonly": athonly.astype(bool), "aboveU": aboveU.astype(bool),
           "belowL": belowL.astype(bool), "exitL": exitL.astype(bool), "exitS": exitS.astype(bool),
           "stopL": np.asarray(stopL, float), "stopS": np.asarray(stopS, float), "touchL": touch.astype(float),
           "label_wd": np.asarray(lab.weekday, np.int64), "markc": P["mclose"][lh] if nb else np.zeros(0),
           "sma": sma, "ub": ub, "lb": lb, "mid": mid, "atr": atr, "hi60": hi60, "ath": ath, "cnt": cnt,
           "near_r0L": near_r0L.astype(bool), "near_r0S": near_r0S.astype(bool)}
    P["_sig"][key] = out
    while len(P["_sig"]) > _SIG_MAX:
        P["_sig"].pop(next(iter(P["_sig"])))
    return out


def _timing(P: dict, cfg: Cfg):
    """(ent_ok, ext_ok, blk, edel, xdel, rule6 code, rule15 flag) for the row's timing and bar size."""
    nyh, N = P["ny_hour"], P["N"]
    daily = cfg.bars == "1d"
    weekly = cfg.bars == "1w"
    every = np.ones(N, bool)
    if cfg.timing == "ny":
        ent = nyh == int(cfg.entry_ny_hour)
        ext = nyh == int(cfg.exit_ny_hour)
        edel = xdel = 0
    elif cfg.timing == "core":
        ent = ext = every
        edel = xdel = 1 if (daily or weekly) else 0
    else:                                                             # r0 / windows / late_only
        wins = (10,) if cfg.timing == "late_only" else (6, 10)
        if daily or weekly:
            ent = np.isin(nyh, wins)
        else:
            ent = every.copy()                                        # bar-size convention: next hourly open
        ext = (nyh == 13) if daily else every
        edel = xdel = 0
        if cfg.ban:
            ent = ent & ~np.isin(nyh, BAN_NY_HOURS)
    blk = np.isin(P["ny_wd"], np.asarray(cfg.block_days, np.int64)) if len(cfg.block_days) else np.zeros(N, bool)
    r6 = {"off": 0, "literal": 1, "minhold": 2}[cfg.rule6] if daily else 0
    r15 = bool(len(cfg.defer_days)) and daily
    return ent, ext, blk, edel, xdel, r6, r15


def _hour_pos(P, ts, side="left") -> int:
    """Index of the first hour >= ts (side='left') or the last hour <= ts (side='right')."""
    v = pd.Timestamp(ts)
    v = (v.tz_localize("UTC") if v.tz is None else v.tz_convert("UTC")).value
    if side == "left":
        return int(np.searchsorted(P["t"], v, side="left"))
    return int(np.searchsorted(P["t"], v, side="right")) - 1


def _slip(sym: str) -> float:
    return SLIP_MAJOR if sym in MAJORS else SLIP_OTHER


def _params(sym: str, cfg: Cfg, mmr: float):
    zero = cfg.fees == "zero"
    slip = 0.0 if zero else _slip(sym)
    costside = -1.0 if cfg.cost_side is None else (0.0 if zero else float(cfg.cost_side))
    trf = 1.0 if cfg.adds == "none" else 1.0 / 3.0
    tpfrac = {"half": 0.5, "all": 1.0, "none": 0.0}[cfg.tp]
    if cfg.adds == "price":
        avgL, avgS = (1.0 + 1.02 + 1.05) / 3.0, (1.0 + 0.98 + 0.95) / 3.0
    elif cfg.adds == "roe":
        avgL = (3.0 + 0.07 / cfg.L) / 3.0
        avgS = (3.0 - 0.07 / cfg.L) / 3.0
    else:
        avgL = avgS = 1.0
    prm = np.zeros(16)
    prm[P_L] = float(cfg.L)
    prm[P_MMR] = float(mmr)
    prm[P_TAKER] = TAKER[cfg.fees]
    prm[P_MAKER] = MAKER[cfg.fees]
    prm[P_SLIP] = slip
    prm[P_SPOTFEE] = 0.0 if zero else SPOT_FEE
    prm[P_COSTSIDE] = costside
    prm[P_A1], prm[P_A2] = 1.02, 1.05
    prm[P_TPR] = TP_R
    prm[P_TPFRAC] = tpfrac
    prm[P_MINHOLD] = float(cfg.min_hold_h)
    prm[P_TRF] = trf
    prm[P_AVGF_L], prm[P_AVGF_S] = avgL, avgS
    prm[P_LCFG] = float(cfg.L)
    return prm


def _given_hours(P, given):
    """Decision hours (and sides) of given entries: a list / index of timestamps (long), a Series of sides (+1 /
    -1) indexed by timestamps, or a DataFrame with columns time and side. A time off the hour decides at the next
    hour."""
    if given is None:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    if isinstance(given, pd.DataFrame):
        times, sides = given["time"], given["side"].to_numpy(np.int64)
    elif isinstance(given, pd.Series):
        times, sides = given.index, given.to_numpy(np.int64)
    else:
        times = given
        sides = None
    g = pd.DatetimeIndex(pd.to_datetime(list(times)) if not isinstance(times, pd.DatetimeIndex) else times)
    g = (g.tz_localize("UTC") if g.tz is None else g.tz_convert("UTC")).as_unit("ns").asi8
    gs = np.ones(len(g), np.int64) if sides is None else np.where(np.asarray(sides) < 0, -1, 1).astype(np.int64)
    gh = np.ceil((g - P["t"][0]) / H_NS).astype(np.int64)
    o = np.argsort(gh, kind="stable")
    gh, gs = gh[o], gs[o]
    keep = (gh >= 0) & (gh < P["N"])
    return gh[keep], gs[keep]


def _mask_hours(P, mask) -> np.ndarray:
    """An entry mask (bool Series indexed by timestamps, step function, or an hourly bool array) on the hours."""
    if mask is None:
        return np.ones(P["N"], bool)
    if isinstance(mask, np.ndarray):
        if len(mask) != P["N"]:
            raise ValueError("entry_allowed array must have one value per hour")
        return mask.astype(bool)
    s = pd.Series(mask).astype(bool)
    ix = pd.DatetimeIndex(s.index)
    ix = (ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")).as_unit("ns")
    s.index = ix
    s = s.sort_index()
    pos = np.searchsorted(s.index.asi8, P["t"], side="right") - 1
    out = np.zeros(P["N"], bool)
    ok = pos >= 0
    out[ok] = s.to_numpy()[pos[ok]]
    return out


# ============================================================================ simulate_coin
def simulate_coin(sym: str, cfg: Cfg, start=None, end=None, given_entries=None, hours: pd.DataFrame | None = None,
                  minutes: pd.DataFrame | None = None, entry_allowed=None, mmr: float | None = None,
                  detail: bool = True) -> dict:
    """Simulate one coin under cfg (positions in units of M = 1). start / end bound entry1 fills (inclusive; a
    date-only end covers the whole day); indicators use the full history of `hours`. given_entries: decision
    times for entry_mode="given". entry_allowed: S12-style membership (bool Series indexed by month starts, or
    an hourly array). Injection: hours= replaces bb_data.coin_hours(sym) (daily / 4h / weekly bars are built
    from it with bb_data.bars_from_hours); minutes= replaces the 1-minute file. When hours are injected and
    minutes are not, no hour is resolved on minutes (inject both for M1 coins). Returns trades, tranches, expo,
    daily_mtm, fills_audit, log, signals (see module doc)."""
    if cfg.entry_mode == "given" and given_entries is None:
        raise ValueError("entry_mode='given' needs given_entries")
    P = prepare(sym, hours, minutes)
    SG = _signals(P, cfg)
    ent, ext, blk, edel, xdel, r6, r15 = _timing(P, cfg)
    t, N = P["t"], P["N"]
    h0 = 0 if start is None else max(_hour_pos(P, bd._utc(start), "left"), 0)
    h1 = N - 1 if end is None else min(_hour_pos(P, bd._utc_end(end), "right"), N - 1)
    if h1 < h0:
        raise ValueError(f"{sym}: empty window {start} .. {end}")
    allowed = P["tradable"] & _mask_hours(P, entry_allowed)
    stress = np.zeros(N, bool)
    if cfg.stress_20251010:
        stress = (t >= STRESS_FROM.value) & (t < STRESS_TO.value)
    mmr_v = float(mmr) if mmr is not None else float(bd.MMR.get(sym, 0.005))
    prm = _params(sym, cfg, mmr_v)
    ipr = np.zeros(NIPR, np.int64)
    ipr[I_DIRMODE] = 1 if cfg.direction == "longshort" else 0
    ipr[I_ADDS] = {"price": 0, "roe": 1, "none": 2}[cfg.adds]
    ipr[I_RULE6] = r6
    ipr[I_EMODE] = {"close": 0, "touch": 1, "given": 2}[cfg.entry_mode]
    ipr[I_REENT] = 1 if cfg.reentry == "same_episode" else 0
    ipr[I_SFILL] = 1 if cfg.stop_fill == "at_S" else 0
    ipr[I_CROSS] = 1 if cfg.margin == "cross" else 0
    ipr[I_SPOTM] = 1 if cfg.spot_costs else 0
    ipr[I_EDEL], ipr[I_XDEL] = edel, xdel
    ipr[I_H0], ipr[I_H1] = h0, h1
    ipr[I_R15] = 1 if r15 else 0
    deferb = np.isin(SG["label_wd"], np.asarray(cfg.defer_days, np.int64)) if r15 else np.zeros(len(SG["kh"]), bool)
    gh, gd = _given_hours(P, given_entries) if cfg.entry_mode == "given" else (np.zeros(0, np.int64),
                                                                               np.zeros(0, np.int64))
    if cfg.direction == "long" and (gd < 0).any():
        raise ValueError("short given entries need direction='longshort'")
    # position buffer: one position per signal bar or given entry; the touch arm can open one in any live hour
    # while flat (e.g. after a stop on a whipsaw path), so on overflow the run is repeated at the hard bound (at
    # most one position opens per hour)
    for pmax in (len(SG["kh"]) + len(gh) + 8, max(len(SG["kh"]), h1 - h0 + 1) + len(gh) + 8):
        ipr[I_PMAX] = pmax
        out = _loop(P["o"], P["hi"], P["lo"], P["c"], P["tr"], P["tradable"], P["spot"], P["pend_end"], P["mlo"],
                    P["mhi"], P["mopen"], P["fund"], ent, ext, blk, allowed, stress, P["midnight"], P["m1s"],
                    P["m1n"], P["m1lo"], P["m1hi"], P["mo"], P["mh"], P["ml"], P["mc"], P["mtr"],
                    SG["kh"], SG["freshL"], SG["lvlL"], SG["freshS"], SG["lvlS"], SG["athonly"], SG["aboveU"],
                    SG["belowL"], SG["exitL"], SG["exitS"], SG["stopL"], SG["stopS"], SG["touchL"], deferb,
                    SG["markc"], gh, gd, prm, ipr)
        if not out[-1]:
            break
    else:
        raise RuntimeError(f"{sym}: position / signal buffer overflow at {pmax} positions")
    PFa, PIa, FIa, FFa, EIa, EFa, DIa, DFa, SGa, LGa, nfill, _ = out
    if nfill > len(FIa):
        raise RuntimeError("fill buffer overflow")
    return _outputs(sym, cfg, P, SG, PFa, PIa, FIa, FFa, EIa, EFa, DIa, DFa, SGa, LGa, h0, h1, detail)


def _stamp(P, h, minute) -> np.ndarray:
    """Fill time stamps: a fill at an hour's open (minute -1) at that hour; a fill resolved on the hourly bar's
    range, a perp_end close or a window-end mark (minute -2) at the hour's close; a fill resolved on a 1-minute bar
    at that minute's close. Each stamp is the moment the data the fill used were complete."""
    h = np.asarray(h, np.int64)
    minute = np.asarray(minute, np.int64)
    ts = P["t"][h].copy()
    mres = minute >= 0
    if mres.any():
        ts[mres] = P["mt"][minute[mres]] + MIN_NS
    ts[minute == -2] += H_NS
    return ts


def _ts(P, hidx) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(P["t"][np.asarray(hidx, np.int64)], tz="UTC") if len(hidx) else \
        pd.DatetimeIndex([], tz="UTC")


def _outputs(sym, cfg, P, SG, PF, PI, FI, FF, EI, EF, DI, DF, SGa, LG, h0, h1, detail) -> dict:
    t = P["t"]
    n = len(PF)
    lab = SG["label"]
    period = bd.FREQ[cfg.bars].value
    # ---- tranches / fills
    if len(FI):
        h = FI[:, 2]
        minute = FI[:, 3]
        ft = _stamp(P, h, minute)
        cause = FI[:, 4]
        tranches = pd.DataFrame({
            "pos": FI[:, 0], "sym": sym, "time": pd.DatetimeIndex(ft, tz="UTC"),
            "kind": np.asarray(KIND_NAMES, dtype=object)[FI[:, 1]], "px": FF[:, 0], "frac": FF[:, 1],
            "cost": FF[:, 2], "dir": FI[:, 5], "hour": h, "minute": minute,
            "cause_time": pd.DatetimeIndex(t[np.clip(cause, 0, len(t) - 1)], tz="UTC")})
    else:
        tranches = pd.DataFrame(columns=["pos", "sym", "time", "kind", "px", "frac", "cost", "dir", "hour", "minute",
                                         "cause_time"])
    audit = _audit(P, cfg, FI, FF)
    # ---- trades
    if n:
        sigbar = PI[:, PI_SIGBAR]
        given = PI[:, PI_GIVEN]
        sig_day = np.where(sigbar >= 0, lab.asi8[np.clip(sigbar, 0, max(len(lab) - 1, 0))] if len(lab) else 0, 0)
        sig_known = np.where(sigbar >= 0, SG["known_at"][np.clip(sigbar, 0, max(len(lab) - 1, 0))]
                             if len(lab) else 0, 0)
        gmask = given >= 0
        sig_day = np.where(gmask, t[np.clip(given, 0, len(t) - 1)] - period, sig_day)
        sig_known = np.where(gmask, t[np.clip(given, 0, len(t) - 1)], sig_known)
        eh = PI[:, PI_EH]
        xh = PI[:, PI_XH]
        e_time = _stamp(P, eh, PI[:, PI_EMIN])                          # touch fills: the bar that resolved them
        x_time = _stamp(P, xh, PI[:, PI_XMIN])
        side = PI[:, PI_SIDE]
        reason = np.asarray(REASON_NAMES, dtype=object)[PI[:, PI_RSN]]
        tpf = PI[:, PI_TPF] == 1
        reason = np.where(tpf & (PI[:, PI_RSN] != R_TPALL), "tp+" + reason.astype(str), reason.astype(str))
        trades = pd.DataFrame({
            "pos": np.arange(n), "sym": sym, "side": side,
            "signal_day": pd.DatetimeIndex(sig_day, tz="UTC"), "signal_known": pd.DatetimeIndex(sig_known, tz="UTC"),
            "entry1_time": pd.DatetimeIndex(e_time, tz="UTC"), "entry1_px": PF[:, PF_E1], "S": PF[:, PF_S],
            "TP": PF[:, PF_TP], "L_used": PF[:, PF_LU], "L_max": PF[:, PF_LMAX], "liq_px0": PF[:, PF_LIQ0],
            "exit_time": pd.DatetimeIndex(x_time, tz="UTC"), "exit_px": PF[:, PF_XPX], "exit_reason": reason,
            "n_tranches": PI[:, PI_NTR], "max_frac": PF[:, PF_MAXF], "ret": PF[:, PF_RET],
            "ret_gross": PF[:, PF_GROSS], "fees": PF[:, PF_FEES], "funding": PF[:, PF_FUND],
            "liquidated": PI[:, PI_LIQD] == 1, "hold_h": (x_time - e_time) / H_NS,
            "open_at_end": PI[:, PI_OAE] == 1, "atH_only": PI[:, PI_ATHO] == 1, "deferred": PI[:, PI_DEF] == 1,
            "tp_filled": tpf, "n_adds_cancelled": PI[:, PI_NCX], "reentry": PI[:, PI_RE] == 1,
            "given": gmask, "entry_bar": pd.DatetimeIndex(lab.asi8[np.clip(PI[:, PI_EBAR], 0, max(len(lab) - 1, 0))]
                                                         if len(lab) else np.zeros(n, np.int64), tz="UTC"),
            "l_capped": PI[:, PI_LCAP] == 1, "avg_entry": PF[:, PF_AVG], "margin_posted": PF[:, PF_POSTED],
            "expo_sum": PF[:, PF_EXPO], "touch": PI[:, PI_EMIN] != -1})
        sb = np.clip(sigbar, 0, max(len(lab) - 1, 0))
        nr = np.where(side > 0, SG["near_r0L"][sb], SG["near_r0S"][sb]) if len(lab) else np.zeros(n, bool)
        trades["near_r0"] = np.where((sigbar >= 0) & ~gmask, nr, False)
        trades["month"] = trades["entry1_time"].dt.tz_localize(None).dt.to_period("M").astype(str)
    else:
        trades = pd.DataFrame(columns=["pos", "sym", "side", "signal_day", "signal_known", "entry1_time", "entry1_px",
                                       "S", "TP", "L_used", "L_max", "liq_px0", "exit_time", "exit_px", "exit_reason",
                                       "n_tranches", "max_frac", "ret", "ret_gross", "fees", "funding", "liquidated",
                                       "hold_h", "open_at_end", "atH_only", "deferred", "tp_filled",
                                       "n_adds_cancelled", "reentry", "given", "entry_bar", "l_capped", "avg_entry",
                                       "margin_posted", "expo_sum", "touch", "month", "near_r0"])
    # ---- exposure path and 00:00 marks
    if detail:
        expo = pd.DataFrame({"pos": EI[:, 0], "time": _ts(P, EI[:, 1]), "notional": EF[:, 0], "sym": sym,
                             "pnl_lo": EF[:, 1], "mm": EF[:, 2], "hour": EI[:, 1]})
    else:
        expo = pd.DataFrame({"pos": trades["pos"].to_numpy(), "time": trades["entry1_time"],
                             "notional": trades["expo_sum"].to_numpy(float), "sym": sym})
    daily = pd.DataFrame({"pos": DI[:, 0], "time": _ts(P, DI[:, 1]), "mtm": DF[:, 0], "margin": DF[:, 1],
                          "notional": DF[:, 2], "sym": sym})
    # ---- signals table
    if len(SGa):
        b = SGa[:, 0]
        bl = np.clip(b, 0, max(len(lab) - 1, 0))
        g = SGa[:, 4]
        sday = np.where(g >= 0, t[np.clip(g, 0, len(t) - 1)] - period, lab.asi8[bl] if len(lab) else 0)
        signals = pd.DataFrame({"sym": sym, "signal_day": pd.DatetimeIndex(sday, tz="UTC"), "dir": SGa[:, 1],
                                "fate": np.asarray(FATE_NAMES, dtype=object)[SGa[:, 2]], "pos": SGa[:, 3],
                                "atH_only": SGa[:, 5] == 1, "reentry": SGa[:, 6] == 1, "given": g >= 0})
    else:
        signals = pd.DataFrame(columns=["sym", "signal_day", "dir", "fate", "pos", "atH_only", "reentry", "given"])
    log = {k: int(LG[i]) for i, k in enumerate(LOG_NAMES)}
    fb = P["m1_fallback"]
    log["m1_hours_hourly_fallback"] = int(((fb >= h0) & (fb <= h1)).sum())
    log.update(window=(str(pd.Timestamp(t[h0], tz="UTC")), str(pd.Timestamp(t[h1], tz="UTC"))),
               tranches=int(trades["n_tranches"].sum()) if n else 0, cfg=asdict(cfg))
    res = {"sym": sym, "trades": trades, "tranches": tranches, "expo": expo, "daily_mtm": daily,
           "fills_audit": audit, "log": log, "signals": signals}
    return res


def _audit(P, cfg, FI, FF) -> list:
    """Fill audit (Controls): every fill, before costs, inside its bar's [low, high] (the minute's when resolved
    on minutes), in a bar with trades > 0 and a tradable hour, stamped at or after its cause. Window-end marks are
    not fills; at_S stops are exempt from the range check (counterfactual); a liquidation is checked against the
    hour's trigger (mark or last-price low / high, or a stop fill beyond it); perp_end settlements are exempt from
    the trades > 0 check."""
    out = []
    if not len(FI):
        return out
    kind = FI[:, 1]
    h = FI[:, 2]
    m = FI[:, 3]
    cause = FI[:, 4]
    px = FF[:, 0]
    tol = 1e-9 * np.abs(px) + 1e-12
    fill = kind != K_END
    mres = m >= 0
    lo = np.where(mres, P["ml"][np.clip(m, 0, max(len(P["ml"]) - 1, 0))] if len(P["ml"]) else np.nan, P["lo"][h])
    hi = np.where(mres, P["mh"][np.clip(m, 0, max(len(P["mh"]) - 1, 0))] if len(P["mh"]) else np.nan, P["hi"][h])
    trd = np.where(mres, P["mtr"][np.clip(m, 0, max(len(P["mtr"]) - 1, 0))] if len(P["mtr"]) else 0, P["tr"][h])
    exempt_rng = (kind == K_LIQ) | ((kind == K_STOP) & (cfg.stop_fill == "at_S"))
    bad_rng = fill & ~exempt_rng & ((px < lo - tol) | (px > hi + tol))
    bad_trd = fill & (kind != K_DELIST) & (trd <= 0)
    bad_tdb = fill & ~P["tradable"][h]
    bad_cause = fill & (cause > h)
    # liquidation consistency: the liquidation price was reached by the mark (or last) extreme, or a stop fill
    lq = kind == K_LIQ
    if lq.any():
        side = -FI[:, 5]                                              # the closing order is opposite the position
        mlo = np.where(np.isfinite(P["mlo"][h]), P["mlo"][h], P["lo"][h])
        mhi = np.where(np.isfinite(P["mhi"][h]), P["mhi"][h], P["hi"][h])
        ext_lo = np.minimum(mlo, lo)
        ext_hi = np.maximum(mhi, hi)
        bad_lq = lq & (((side > 0) & (ext_lo > px + tol)) | ((side < 0) & (ext_hi < px - tol)))
    else:
        bad_lq = np.zeros(len(kind), bool)
    for name, bad in (("price outside bar range", bad_rng), ("fill in a trades == 0 bar", bad_trd),
                      ("fill in a non-tradable hour", bad_tdb), ("fill before its cause", bad_cause),
                      ("liquidation not reached", bad_lq)):
        for i in np.flatnonzero(bad)[:20]:
            out.append(f"{P['sym']} {name}: pos {FI[i, 0]} {KIND_NAMES[kind[i]]} hour "
                       f"{pd.Timestamp(P['t'][h[i]], tz='UTC')} minute {m[i]} px {px[i]:.10g} "
                       f"[{lo[i]:.10g}, {hi[i]:.10g}] trades {trd[i]} cause {cause[i]}")
    return out


# ============================================================================ H4 episodes
def h4_episodes(sym: str, start=None, end=None, cfg: Cfg | None = None, hours: pd.DataFrame | None = None,
                minutes: pd.DataFrame | None = None) -> pd.DataFrame:
    """H4 episodes ("from the first touch of the prior day's upper band to the next daily close below the
    midline"): while no episode runs, an episode starts at the first live hour (trades > 0, tradable, inside
    [start, end]) whose high exceeds the touch arm's armed level, i.e. the latest completed daily bar's upper band
    kept when it meets the near-high rule (choice 12); it ends at the known_at of the next daily close below the
    midline. Columns: ep, start (hour open of the touch), end (NaT if still running at the window end),
    start_day (the bar whose band was touched), month (cluster label of the start)."""
    cfg = cfg or h4_touch_cfg()
    P = prepare(sym, hours, minutes)
    SG = _signals(P, cfg)
    t, N = P["t"], P["N"]
    h0 = 0 if start is None else max(_hour_pos(P, bd._utc(start), "left"), 0)
    h1 = N - 1 if end is None else min(_hour_pos(P, bd._utc_end(end), "right"), N - 1)
    kh, lvl, ex, lab = SG["kh"], SG["touchL"], SG["exitL"], SG["label"]
    live = (P["tr"] > 0) & P["tradable"]
    hi = P["hi"]
    rows = []
    cur = None
    for j in range(len(kh)):
        if kh[j] > h1:
            break
        if cur is not None and kh[j] >= h0 and ex[j]:
            cur["end"] = kh[j]
            rows.append(cur)
            cur = None
        if cur is None and np.isfinite(lvl[j]):
            a = max(kh[j], h0)
            b = min(kh[j + 1] if j + 1 < len(kh) else N, h1 + 1)
            if b > a:
                hit = np.flatnonzero(live[a:b] & (hi[a:b] > lvl[j]))
                if len(hit):
                    cur = {"start": a + int(hit[0]), "end": -1, "start_day": lab[j]}
    if cur is not None:
        rows.append(cur)
    if not rows:
        return pd.DataFrame(columns=["ep", "start", "end", "start_day", "month"])
    st_ = np.array([r["start"] for r in rows], np.int64)
    en_ = np.array([r["end"] for r in rows], np.int64)
    out = pd.DataFrame({"ep": np.arange(len(rows)), "start": pd.DatetimeIndex(t[st_], tz="UTC"),
                        "end": pd.DatetimeIndex(np.where(en_ >= 0, t[np.clip(en_, 0, N - 1)], np.iinfo(np.int64).min),
                                                tz="UTC"),
                        "start_day": pd.DatetimeIndex([r["start_day"] for r in rows])})
    out["month"] = out["start"].dt.tz_localize(None).dt.to_period("M").astype(str)
    return out


def assign_episodes(trades: pd.DataFrame, episodes: pd.DataFrame) -> pd.Series:
    """Episode id of each trade: the episode with start <= entry1_time < end (end NaT = still running). A trade
    entered outside every episode gets its own new id (above the largest episode id): e.g. an S1 trade whose close
    met the near-high rule while the band level did not (no armed touch), 2-5 per coin on BTC/ETH/SOL 2020-2026."""
    if not len(trades):
        return pd.Series([], dtype=np.int64, index=trades.index)
    e = _ns(trades["entry1_time"])
    if len(episodes):
        s0 = _ns(episodes["start"])
        en = episodes["end"]
        e1 = np.where(en.isna().to_numpy(), np.iinfo(np.int64).max, _ns(en.fillna(episodes["start"])))
        k = np.searchsorted(s0, e, side="right") - 1
        ok = (k >= 0) & (e < e1[np.clip(k, 0, len(s0) - 1)])
        ids = np.where(ok, episodes["ep"].to_numpy()[np.clip(k, 0, len(s0) - 1)], -1)
        nxt = int(episodes["ep"].max()) + 1
    else:
        ids = np.full(len(e), -1)
        nxt = 0
    for i in np.flatnonzero(ids < 0):
        ids[i] = nxt
        nxt += 1
    return pd.Series(ids.astype(np.int64), index=trades.index, name="episode")


# ============================================================================ S12 membership
def s12_allowed(sym: str, k: int, pool: str = "all", tradfi: bool = False) -> pd.Series:
    """Month-start membership of sym in the point-in-time top k (bb_data.volume_ranks), for entry_allowed."""
    R = bd.volume_ranks(pool, tradfi=tradfi) if pool == "all" else bd.volume_ranks(pool)
    top = R.iloc[:, :k]
    return (top == sym).any(axis=1).astype(bool)


def row_coins(row: str, k_default=SLOTS_R0) -> list:
    """The coin list of a ROWS entry (S12 rows: every coin ever in the top k of the ranking)."""
    u = ROW_UNIVERSE.get(row, k_default)
    if isinstance(u, tuple) and u[0] == "s12":
        _, pool, k, tradfi = u
        R = bd.volume_ranks(pool, tradfi=tradfi) if pool == "all" else bd.volume_ranks(pool)
        return sorted({x for x in R.iloc[:, :k].to_numpy().ravel() if isinstance(x, str)})
    return list(u)


# ============================================================================ account assembly
def _ns(x) -> np.ndarray:
    """int64 UTC nanoseconds of a timestamp column / index (tz-aware or naive UTC)."""
    ix = pd.DatetimeIndex(x)
    if ix.tz is not None:
        ix = ix.tz_convert("UTC").tz_localize(None)
    return ix.as_unit("ns").asi8


def assemble(results_by_coin: dict, cfg: Cfg, start, end, idle_tbill: bool = False, k_slots: int | None = None,
             equity0: float = 1.0) -> dict:
    """Account of K slots (prereg R0 Size, Sizing equity, Costs; S3 cross; S19). Each position's M = L_used x
    sleeve, sleeve = sizing equity / K at its entry month (rule 11; S19: equity at the last 00:00 UTC before
    entry1). Returns daily equity at 00:00 UTC (index = day start; the last value is the mark after the window's
    last hour), daily returns, T-bill and excess returns, per-trade dollar P&L, liquidations, exposure."""
    K = int(k_slots or len(results_by_coin))
    a = bd._utc(start)
    b = bd._utc_end(end)
    day0 = a.floor("D")
    day_last = b.floor("D") + pd.Timedelta("1D")
    days = pd.date_range(day0, day_last, freq="D").as_unit("ns")
    nd = len(days)
    dv = days.asi8
    rows = []
    for s, r in results_by_coin.items():
        T = r["trades"]
        if len(T):
            T = T[(T.entry1_time >= a) & (T.entry1_time <= b)].copy()
            T["sym"] = s
            rows.append(T)
    T = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["sym", "pos", "entry1_time"])
    T = T.sort_values(["entry1_time", "sym"], kind="stable").reset_index(drop=True)
    P = len(T)
    V = np.zeros((nd, P))
    MG = np.zeros((nd, P))
    NT = np.zeros((nd, P))
    eh = np.zeros(P, np.int64)
    for i in range(P):
        s, pid = T.sym.iat[i], T.pos.iat[i]
        e = T.entry1_time.iat[i].value
        x = T.exit_time.iat[i].value
        dm = results_by_coin[s]["daily_mtm"]
        dm = dm[dm.pos == pid]
        dmt = _ns(dm.time)
        di = np.searchsorted(dv, dmt)
        ok = (di < nd) & (dv[np.clip(di, 0, nd - 1)] == dmt)
        V[dv >= x, i] = T.ret.iat[i]                                 # closed (or marked) by this 00:00
        if len(dm):
            V[di[ok], i] = dm.mtm.to_numpy()[ok]
            MG[di[ok], i] = dm.margin.to_numpy()[ok]
            NT[di[ok], i] = dm.notional.to_numpy()[ok] * T.side.iat[i]
        eh[i] = np.searchsorted(dv, e, side="right") - 1             # the 00:00 at or before entry1
    tb = bd.tbill_daily(days)
    E = np.zeros(nd)
    INT = np.zeros(nd)                                                # T-bill interest credited by each 00:00
    M = np.zeros(P)
    size_eq = np.zeros(P)
    L_used = T.L_used.to_numpy(float) if P else np.zeros(0)
    rule11 = cfg.rule11
    interest = 0.0
    dead = False
    month_start_eq = None
    E_size = None
    frozen = []
    order = np.argsort(eh, kind="stable")
    ptr = 0
    for d in range(nd):
        val = equity0 + interest + (V[d] @ M if P else 0.0)
        if dead or val <= 0:
            val = 0.0
            dead = True
        E[d] = val
        INT[d] = interest
        if d == 0 or days[d].month != days[d - 1].month:              # sizing equity of the month (rule 11)
            if E_size is None:
                E_size = val
            else:
                ret_m = val / month_start_eq - 1.0 if month_start_eq and month_start_eq > 0 else 0.0
                if rule11 and ret_m > 0.25:
                    frozen.append(str(days[d].date())[:7])               # last month's sizing equity is kept
                else:
                    E_size = val
            month_start_eq = val
        while ptr < P and eh[order[ptr]] <= d:
            i = order[ptr]
            ptr += 1
            base = E_size if rule11 else val
            size_eq[i] = base
            M[i] = 0.0 if dead else L_used[i] * base / K
        if idle_tbill and not dead and d < nd - 1:
            locked = MG[d] @ M if P else 0.0
            interest += tb[d] * max(val - locked, 0.0)
    pnl_usd = M * T.ret.to_numpy(float) if P else np.zeros(0)
    # S3 cross: the account is liquidated at the first hour its joint mark-low equity falls below maintenance
    cross_t = None
    cross_pos = []
    if cfg.margin == "cross" and P:
        hrs = pd.date_range(a.ceil("h"), b.floor("h"), freq="h").as_unit("ns").asi8
        nh = len(hrs)
        base = np.zeros(nh + 1)
        openv = np.zeros(nh)
        mmv = np.zeros(nh)
        rows_i = []
        for i in range(P):
            s, pid = T.sym.iat[i], T.pos.iat[i]
            ex = results_by_coin[s]["expo"]
            if "pnl_lo" not in ex.columns:
                raise ValueError("cross margin needs simulate_coin(detail=True)")
            ex = ex[ex.pos == pid]
            hx = np.searchsorted(hrs, _ns(ex.time))
            ok = hx < nh
            np.add.at(openv, hx[ok], M[i] * ex.pnl_lo.to_numpy()[ok])
            np.add.at(mmv, hx[ok], M[i] * ex.mm.to_numpy()[ok])
            last = int(hx[ok].max()) + 1 if ok.any() else int(np.searchsorted(hrs, T.exit_time.iat[i].value))
            base[min(last, nh)] += M[i] * T.ret.iat[i]
            rows_i.append((hx, ok, ex))
        base = np.cumsum(base)[:nh]
        dd = np.clip(np.searchsorted(dv, hrs, side="right") - 1, 0, nd - 1)
        E_low = equity0 + INT[dd] + base + openv
        breach = np.flatnonzero((mmv > 0) & (E_low < mmv))
        if len(breach):
            hb = int(breach[0])
            cross_t = pd.Timestamp(hrs[hb], tz="UTC")
            keep = max(0.0, E_low[hb] - mmv[hb])
            E[dv > hrs[hb]] = keep
            for i in range(P):
                hx, ok, ex = rows_i[i]
                at = np.flatnonzero(ok & (hx == hb))
                if len(at):
                    cross_pos.append(i)
                    pnl_usd[i] = M[i] * (ex.pnl_lo.to_numpy()[at[0]] - ex.mm.to_numpy()[at[0]])
                elif T.entry1_time.iat[i].value > hrs[hb]:
                    M[i] = 0.0
                    pnl_usd[i] = 0.0
    eq = pd.Series(E, index=days, name="equity")
    r = pd.Series(np.where(E[:-1] > 0, E[1:] / np.where(E[:-1] > 0, E[:-1], 1.0) - 1.0, 0.0), index=days[:-1],
                  name="ret")
    tbs = pd.Series(tb[:-1], index=days[:-1], name="tbill")
    T = T.copy()
    T["M"] = M
    T["sizing_equity"] = size_eq
    T["pnl_usd"] = pnl_usd
    if cross_pos:
        T.loc[cross_pos, "exit_reason"] = "cross_liq"
    expo_d = pd.Series(np.where(E > 0, (np.abs(NT) @ M if P else 0.0) / np.where(E > 0, E, 1.0), 0.0), index=days,
                       name="exposure")
    out = {"equity": eq, "ret": r, "excess": (r - tbs).rename("excess"), "tbill": tbs, "trades": T,
           "liquidations": T[T.liquidated.astype(bool)] if P else T, "exposure": expo_d, "interest": pd.Series(
               INT, index=days, name="interest"),
           "exposure_avg": float(expo_d.iloc[:-1].mean()) if nd > 1 else 0.0,
           "exposure_peak": float(expo_d.max()) if nd else 0.0, "frozen_months": frozen, "K": K,
           "cross_liquidation": cross_t, "dead": bool(E[-1] <= 0)}
    return out




# ============================================================================ self-test: synthetic helpers
def _U(s) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def _flat_hours(start, days, base=100.0, hi_off=1.0, lo_off=1.0) -> pd.DataFrame:
    """Flat synthetic hours: O = H = L = C = base except a high of base + hi_off at 05:00 and a low of base - lo_off
    at 17:00 UTC, so every daily bar is (base, base + hi_off, base - lo_off, base): TR = hi_off + lo_off, SMA =
    base, sigma = 0. trades 10, tradable, perpetual, no funding, no mark."""
    idx = pd.date_range(_U(start), periods=int(days) * 24, freq="h").as_unit("ns")
    n = len(idx)
    o = np.full(n, float(base))
    h, l, c = o.copy(), o.copy(), o.copy()
    h[idx.hour == 5] += hi_off
    l[idx.hour == 17] -= lo_off
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "trades": np.full(n, 10, np.int64)}, index=idx)
    df.index.name = "open_time"
    df["tradable"] = True
    df["spot_only"] = False
    df["perp_end"] = False
    df["funding"] = 0.0
    for col in ("mark_open", "mark_high", "mark_low", "mark_close"):
        df[col] = np.nan
    return df


def _bar(df, ts, o, h, l, c, trades=None):
    t = _U(ts)
    df.loc[t, ["open", "high", "low", "close"]] = [o, h, l, c]
    if trades is not None:
        df.loc[t, "trades"] = trades


def _flat(df, a, b, px):
    """Hours a..b (inclusive) flat at px."""
    m = (df.index >= _U(a)) & (df.index <= _U(b))
    df.loc[m, ["open", "high", "low", "close"]] = px


def _fin(df) -> pd.DataFrame:
    df = df.copy()
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))
    for a in bd.PX:
        df["sig_" + a] = df[a]
    df["live"] = df["sig_live"] = True
    df["seg"] = 0
    return df


def _ref_daily(df):
    """Reference daily bars (plain resample, independent of bb_data.bars_from_hours)."""
    d = df[["open", "high", "low", "close"]].resample("1D").agg({"open": "first", "high": "max", "low": "min",
                                                                  "close": "last"})
    return d


def _ref_ind(d, n=20, k=2.0):
    """Pure-Python SMA, population sigma, Wilder ATR14 on reference bars (the hand computation)."""
    C, Hh, Ll = list(d.close), list(d.high), list(d.low)
    sma, ub, atr = [], [], []
    a = None
    trs = []
    for i in range(len(C)):
        w = C[max(0, i - n + 1): i + 1]
        if len(w) == n:
            m = sum(w) / n
            sd = (sum((x - m) ** 2 for x in w) / n) ** 0.5
            sma.append(m)
            ub.append(m + k * sd)
        else:
            sma.append(float("nan"))
            ub.append(float("nan"))
        tr = Hh[i] - Ll[i] if i == 0 else max(Hh[i] - Ll[i], abs(Hh[i] - C[i - 1]), abs(Ll[i] - C[i - 1]))
        trs.append(tr)
        if len(trs) == 14:
            a = sum(trs) / 14
        elif len(trs) > 14:
            a = (a * 13 + tr) / 14
        atr.append(a if len(trs) >= 14 else float("nan"))
    return pd.DataFrame({"sma": sma, "ub": ub, "atr": atr}, index=d.index)


def _close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _one(r, n=1):
    T = r["trades"]
    assert len(T) == n, (len(T), T[["entry1_time", "exit_time", "exit_reason"]] if len(T) else None)
    assert not r["fills_audit"], r["fills_audit"]
    return T


def _signal_day(df, day, close=104.0, high=104.5):
    """Make `day`'s last hour close at `close` with high `high` (the daily bar: O 100, H high, L 99, C close)."""
    _bar(df, f"{day} 23:00", 100.0, high, 100.0, close)


# ============================================================================ self-test: known answers
def _test_path_est(say):
    """(1a) EST date: signal, 06:00 New York entry (11:00 UTC), both adds, TP, midline exit at 13:00 New York
    (18:00 UTC), funding timing, costs, exposure and 00:00 marks; all at hand-computed times and prices."""
    df = _flat_hours("2024-10-01", 120)
    _signal_day(df, "2025-01-13")                                         # Monday
    _flat(df, "2025-01-14 00:00", "2025-01-14 10:00", 104.0)
    _bar(df, "2025-01-14 11:00", 104.0, 104.3, 103.9, 104.2)            # entry1 at the open
    _bar(df, "2025-01-14 12:00", 104.2, 106.6, 104.2, 106.5)            # close >= 1.02 e1 -> add 1
    _bar(df, "2025-01-14 13:00", 106.6, 109.6, 106.6, 109.5)            # add 1 fills; close >= 1.05 e1 -> add 2
    _bar(df, "2025-01-14 14:00", 109.6, 110.0, 109.5, 110.0)            # add 2 fills
    _flat(df, "2025-01-14 15:00", "2025-01-15 09:00", 110.0)
    _bar(df, "2025-01-15 10:00", 110.0, 122.5, 110.0, 121.0)            # TP 122.15 touched
    _flat(df, "2025-01-15 11:00", "2025-01-16 22:00", 121.0)
    _bar(df, "2025-01-16 23:00", 121.0, 121.0, 101.0, 101.5)            # Thursday close below SMA20
    _flat(df, "2025-01-17 00:00", "2025-01-17 17:00", 101.5)
    _bar(df, "2025-01-17 18:00", 101.4, 101.5, 101.3, 101.4)            # 13:00 New York (EST): exit at the open
    _flat(df, "2025-01-17 19:00", "2025-01-28 23:00", 101.4)
    for ts in ("2025-01-14 08:00", "2025-01-14 11:00", "2025-01-14 16:00", "2025-01-17 18:00", "2025-01-18 00:00"):
        df.loc[_U(ts), "funding"] = 0.0001             # before entry, at entry, held, at the exit open, after exit
    df = _fin(df)
    d = _ref_daily(df)
    ind = _ref_ind(d)
    D = _U("2025-01-13")
    sma, atr = ind.sma[D], ind.atr[D]
    assert _close(sma, 100.2) and _close(atr, (13 * 2 + 5.5) / 14), (sma, atr)
    assert d.close[D] > ind.ub[D] and d.close[D - pd.Timedelta("1D")] <= ind.ub[D - pd.Timedelta("1D")]
    S = sma - atr
    e1 = 104.0
    TP = e1 + 3 * (e1 - S)
    r = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005)
    T = _one(r)
    x = T.iloc[0]
    c_t, c_m = TAKER["base"] + SLIP_OTHER, MAKER["base"]
    assert x.entry1_time == _U("2025-01-14 11:00") and x.entry1_px == e1 and x.signal_day == D
    assert _close(x.S, S) and _close(x.TP, TP) and x.L_used == 3.0 and not x.deferred
    tr = r["tranches"]
    assert list(tr.kind) == ["entry", "add", "add", "tp", "exit"], list(tr.kind)
    assert list(tr.time) == [_U("2025-01-14 11:00"), _U("2025-01-14 13:00"), _U("2025-01-14 14:00"),
                             _U("2025-01-15 11:00"), _U("2025-01-17 18:00")]      # TP: the hour's close
    assert list(tr.px[:3]) == [104.0, 106.6, 109.6] and _close(tr.px.iat[3], TP) and tr.px.iat[4] == 101.4
    assert x.exit_reason == "tp+mid" and x.exit_time == _U("2025-01-17 18:00") and x.n_tranches == 3
    Q = (1 / 3) * (1 / 104.0 + 1 / 106.6 + 1 / 109.6)
    avg = 1.0 / Q
    gross = 0.5 * Q * (TP - avg) + 0.5 * Q * (101.4 - avg)
    fees = 3 * (1 / 3) * c_t + c_m * 0.5 * Q * TP + c_t * 0.5 * Q * 101.4
    fund = 0.0001 * Q * 110.0 + 0.0001 * 0.5 * Q * 101.4                # 16:00 (all held) + 18:00 exit open (half)
    assert _close(x.avg_entry, avg) and _close(x.ret_gross, gross) and _close(x.fees, fees), (x.ret_gross, gross)
    assert _close(x.funding, fund) and _close(x.ret, gross - fees - fund), (x.ret, gross - fees - fund)
    assert _close(x.max_frac, 1.0) and _close(x.hold_h, (_U("2025-01-17 18:00") - _U("2025-01-14 11:00")) / pd.Timedelta("1h"))
    # 00:00 UTC marks: 2025-01-15 00:00 (price 110, all tranches, before the TP)
    dm = r["daily_mtm"].set_index("time")
    m15 = -3 * (1 / 3) * c_t - 0.0001 * Q * 110.0 + Q * (110.0 - avg)
    assert _close(dm.mtm[_U("2025-01-15")], m15) and _close(dm.margin[_U("2025-01-15")], 1 / 3.0)
    assert _close(dm.margin[_U("2025-01-16")], 0.5 / 3.0)                # half the margin released at the TP
    # exposure path: qty held during each hour x that hour's open
    ex = r["expo"]
    ix = df.index
    held = (ix >= _U("2025-01-14 11:00")) & (ix < _U("2025-01-17 18:00"))
    q = np.where(ix >= _U("2025-01-14 13:00"), (1 / 3) * (1 / 104 + 1 / 106.6), (1 / 3) / 104)
    q = np.where(ix >= _U("2025-01-14 14:00"), Q, q)
    q = np.where(ix > _U("2025-01-15 10:00"), Q / 2, q)
    exp_sum = float((q * df.open.to_numpy())[held].sum())
    assert len(ex) == held.sum() and _close(ex.notional.sum(), exp_sum) and _close(x.expo_sum, exp_sum)
    # S1W (no rules 6, 12-15): the same trade; S1 core: 01:00 UTC entry and 01:00 UTC exit
    r1 = simulate_coin("SYN", ROWS["S1"], hours=df, mmr=0.005)
    x1 = _one(r1).iloc[0]
    assert x1.entry1_time == _U("2025-01-14 01:00") and x1.exit_time == _U("2025-01-17 01:00"), x1
    assert x1.exit_reason == "tp+mid"
    rw = simulate_coin("SYN", ROWS["S1W"], hours=df, mmr=0.005)
    xw = _one(rw).iloc[0]
    assert xw.entry1_time == x.entry1_time and xw.exit_time == x.exit_time and _close(xw.ret, x.ret)
    # fee scenarios: zero = gross less funding; vip at 0.03% / 0.01%
    assert bool(x.near_r0) and not bool(x.atH_only)
    rz = simulate_coin("SYN", replace(ROWS["R0"], fees="zero"), hours=df, mmr=0.005)
    xz = _one(rz).iloc[0]
    assert xz.fees == 0.0 and _close(xz.ret, gross - fund)
    # spot stand-in hours: 0.10% + slippage per side (TP 0.10%), funding as given; routes: all-in cost_side, no
    # funding (spot vehicle)
    dsp = df.copy()
    dsp["spot_only"] = True
    rsp = simulate_coin("SYN", ROWS["R0"], hours=dsp, mmr=0.005)
    xsp = _one(rsp).iloc[0]
    c_s = SPOT_FEE + SLIP_OTHER
    assert _close(xsp.fees, 3 * (1 / 3) * c_s + SPOT_FEE * 0.5 * Q * TP + c_s * 0.5 * Q * 101.4) and _close(xsp.funding, fund)
    rrh = simulate_coin("SYN", ROWS["RH_R0win"], hours=df, mmr=0.005)
    xrh = _one(rrh).iloc[0]
    assert xrh.L_used == 1.0 and xrh.funding == 0.0
    assert _close(xrh.fees, 0.0095 * (1.0 + 0.5 * Q * TP + 0.5 * Q * 101.4))
    rv = simulate_coin("SYN", replace(ROWS["R0"], fees="vip"), hours=df, mmr=0.005)
    xv = _one(rv).iloc[0]
    fees_v = 3 * (1 / 3) * (0.0003 + SLIP_OTHER) + 0.0001 * 0.5 * Q * TP + (0.0003 + SLIP_OTHER) * 0.5 * Q * 101.4
    assert _close(xv.fees, fees_v)
    # S4: full M at entry (no adds); S10: TP sells everything / no TP
    r4 = simulate_coin("SYN", ROWS["S4"], hours=df, mmr=0.005)
    x4 = _one(r4).iloc[0]
    assert x4.n_tranches == 1 and _close(x4.ret_gross, 0.5 * (TP / 104 - 1) + 0.5 * (101.4 / 104 - 1))
    ra = simulate_coin("SYN", ROWS["S10_tp_all"], hours=df, mmr=0.005)
    xa = _one(ra).iloc[0]
    assert xa.exit_reason == "tp_all" and xa.exit_time == _U("2025-01-15 11:00")
    rn = simulate_coin("SYN", ROWS["S10_no_tp"], hours=df, mmr=0.005)
    xn = _one(rn).iloc[0]
    assert xn.exit_reason == "mid" and _close(xn.ret_gross, Q * (101.4 - avg))
    # S5: ROE adds at 1 + 2%/3 and 1 + 5%/3 of entry1 (104.693, 105.733): 12:00 close 106.5 clears both
    r5 = simulate_coin("SYN", ROWS["S5"], hours=df, mmr=0.005)
    t5 = r5["tranches"]
    assert list(t5.kind[:3]) == ["entry", "add", "add"] and (t5.time.iloc[1:3] == _U("2025-01-14 13:00")).all()
    # a window that starts after the entry sees nothing; one that ends before the exit marks the position
    re_ = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005, start="2024-10-01", end="2025-01-15 12:00")
    xe = _one(re_).iloc[0]
    assert xe.open_at_end and xe.exit_reason == "tp+window_end" and xe.exit_px == 121.0
    say("  (1a) EST path: entry 11:00 UTC, adds 13:00/14:00, TP, exit 18:00 UTC, funding, fees, marks, S1/S1W/S4/S5/S10 ok")
    # assemble: the window-end mark counts on the final day (K = 1, L = 3: M = 3)
    oa = assemble({"SYN": re_}, ROWS["R0"], "2024-10-01", "2025-01-15 12:00", k_slots=1)
    assert _close(oa["equity"].iloc[-1], 1.0 + 3.0 * xe.ret) and oa["equity"].index[-1] == _U("2025-01-16")
    return [r, r1, rw, rz, rv, r4, ra, rn, r5, re_, rsp, rrh]


def _test_path_edt_stop(say):
    """(1b) EDT date: 06:00 New York = 10:00 UTC; stop fills at S, at a gap open, at 0.99 x S; on minutes at
    min(S, close of the first minute whose low <= S); minutes order TP before stop."""
    out = []
    S = 100.2 - (13 * 2 + 5.5) / 14
    TP = 104 + 3 * (104 - S)
    c_t = TAKER["base"] + SLIP_OTHER
    for case, bars, want_px, want_t in (
            ("at S", [("2025-06-11 21:00", 99.0, 99.0, 97.0, 98.0)], S, "2025-06-11 22:00"),
            ("gap", [("2025-06-11 12:00", 97.0, 97.5, 96.5, 97.0)], 97.0, "2025-06-11 13:00"),
            ("0.99S", [("2025-06-11 12:00", 103.0, 103.0, 90.0, 95.0)], 0.99 * S, "2025-06-11 13:00")):
        df = _flat_hours("2025-03-20", 100)
        _signal_day(df, "2025-06-10")                                     # Tuesday, EDT
        _flat(df, "2025-06-11 00:00", "2025-06-11 23:00", 104.0)
        for ts, o, h, l, c in bars:
            _flat(df, ts, "2025-06-20 23:00", c)
            _bar(df, ts, o, h, l, c)
        df = _fin(df)
        r = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005)
        x = _one(r).iloc[0]
        assert x.entry1_time == _U("2025-06-11 10:00") and x.exit_reason == "stop", (case, x)
        assert _close(x.exit_px, want_px) and x.exit_time == _U(want_t), (case, x.exit_px, want_px)
        q1 = (1 / 3) / 104
        assert _close(x.ret, q1 * (want_px - 104) - c_t / 3 - c_t * q1 * want_px), case
        out.append(r)
    # minutes: the stop hour 21:00 resolved on 1-minute bars
    df = _flat_hours("2025-03-20", 100)
    _signal_day(df, "2025-06-10")
    _flat(df, "2025-06-11 00:00", "2025-06-20 23:00", 104.0)
    _bar(df, "2025-06-11 21:00", 99.0, 99.0, 97.0, 98.0)
    _flat(df, "2025-06-11 22:00", "2025-06-20 23:00", 98.0)
    _bar(df, "2025-06-11 15:00", 104.0, 123.0, 97.5, 104.0)             # TP and S in one hour (= its minutes' range)
    df = _fin(df)
    mi = pd.date_range(_U("2025-06-11"), periods=24 * 60, freq="min").as_unit("ns")
    m = pd.DataFrame({"open": 104.0, "high": 104.0, "low": 104.0, "close": 104.0, "trades": 5}, index=mi)
    # hour 15: minute 10 reaches the TP, minute 50 the stop (close 97.6 below S)
    b15 = _U("2025-06-11 15:00")
    m.loc[b15 + pd.Timedelta("10min"), ["open", "high", "low", "close"]] = [115.0, 123.0, 115.0, 120.0]
    m.loc[b15 + pd.Timedelta("11min"):b15 + pd.Timedelta("49min"), ["open", "high", "low", "close"]] = 110.0
    m.loc[b15 + pd.Timedelta("50min"), ["open", "high", "low", "close"]] = [99.0, 99.0, 97.5, 97.6]
    m.loc[b15 + pd.Timedelta("51min"):b15 + pd.Timedelta("59min"), ["open", "high", "low", "close"]] = 104.0
    # without minutes the same hour is "stop first": everything at S
    r_h = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005)
    x_h = _one(r_h).iloc[0]
    assert x_h.exit_reason == "stop" and x_h.exit_time == b15 + pd.Timedelta("1h") and _close(x_h.exit_px, S)
    r_m = simulate_coin("SYN", ROWS["R0"], hours=df, minutes=m, mmr=0.005)
    x_m = _one(r_m).iloc[0]
    tr = r_m["tranches"]
    assert x_m.exit_reason == "tp+stop" and list(tr.kind) == ["entry", "tp", "stop"], list(tr.kind)
    assert _close(tr.px.iat[1], TP) and tr.time.iat[1] == b15 + pd.Timedelta("11min")     # the minute's close
    assert tr.px.iat[2] == 97.6 and tr.time.iat[2] == b15 + pd.Timedelta("51min")
    # minute-resolved stop with the minute close above S fills at S (min(S, close)); zero-trade minutes ignored
    df2 = df.copy()
    _bar(df2, "2025-06-11 15:00", 104.0, 104.0, 104.0, 104.0)
    df2 = _fin(df2)
    m2 = pd.DataFrame({"open": 104.0, "high": 104.0, "low": 104.0, "close": 104.0, "trades": 5}, index=mi)
    b21 = _U("2025-06-11 21:00")
    m2.loc[b21:b21 + pd.Timedelta("59min"), ["open", "high", "low", "close"]] = 99.0
    m2.loc[b21 + pd.Timedelta("20min"), ["open", "high", "low", "close", "trades"]] = [95.0, 95.0, 95.0, 95.0, 0]
    m2.loc[b21 + pd.Timedelta("31min"), ["open", "high", "low", "close"]] = [98.2, 98.3, 97.9, 98.0]
    m2.loc[b21 + pd.Timedelta("40min"), ["open", "high", "low", "close"]] = [97.0, 97.0, 97.0, 97.0]
    r2 = simulate_coin("SYN", ROWS["R0"], hours=df2, minutes=m2, mmr=0.005)
    x2 = _one(r2).iloc[0]
    assert x2.exit_time == b21 + pd.Timedelta("32min") and _close(x2.exit_px, S), (x2.exit_time, x2.exit_px)
    m2.loc[b21 + pd.Timedelta("31min"), "close"] = 97.92                # in place: the cache must see the change
    r3 = simulate_coin("SYN", ROWS["R0"], hours=df2, minutes=m2, mmr=0.005)
    x3 = _one(r3).iloc[0]
    assert x3.exit_px == 97.92 and r3["log"]["stops_minute_resolved"] == 1
    out += [r_h, r_m, r2, r3]
    say("  (1b) EDT path: entry 10:00 UTC; stop at S / gap open / 0.99 S; minutes: min(S, close), TP before stop ok")
    return out


def _test_deferral(say):
    """(1c) Rule 12: a Thursday signal waits through New York Friday and Saturday to Sunday 06:00 (11:00 UTC),
    re-checked on Saturday's bar, S from Saturday's bar; a failing re-check drops it; zero-trade window ->
    10:00 New York; a window opening at or below S skips the signal."""
    out = []
    df = _flat_hours("2024-10-01", 120)
    _signal_day(df, "2025-01-16")                                         # Thursday
    _flat(df, "2025-01-17 00:00", "2025-01-28 23:00", 104.0)
    dfa = _fin(df)
    d = _ref_daily(dfa)
    ind = _ref_ind(d)
    sat = _U("2025-01-18")
    S = ind.sma[sat] - ind.atr[sat]
    assert _close(ind.sma[sat], 100.6) and _close(S, 100.6 - 13 * ((13 * 2.25) / 14) / 14)
    assert d.close[sat] > ind.ub[sat]
    r = simulate_coin("SYN", ROWS["R0"], hours=dfa, mmr=0.005)
    x = _one(r).iloc[0]
    assert x.entry1_time == _U("2025-01-19 11:00") and x.deferred and x.signal_day == _U("2025-01-16"), x
    assert _close(x.S, S) and x.entry_bar == sat and r["log"]["deferred_entries"] == 1
    out.append(r)
    rw = simulate_coin("SYN", ROWS["S1W"], hours=dfa, mmr=0.005)               # no block: Friday 11:00 UTC
    assert _one(rw).iloc[0].entry1_time == _U("2025-01-17 11:00")
    out.append(rw)
    # H7 placebo block (Sun, Mon): Thursday signal enters Friday
    rp = simulate_coin("SYN", h7_cfg((6, 0)), hours=dfa, mmr=0.005)
    assert _one(rp).iloc[0].entry1_time == _U("2025-01-17 11:00")
    # re-check fails: Saturday closes at 102 (below its upper band)
    dfb = df.copy()
    _bar(dfb, "2025-01-18 23:00", 104.0, 104.0, 102.0, 102.0)
    _flat(dfb, "2025-01-19 00:00", "2025-01-28 23:00", 102.0)
    dfb = _fin(dfb)
    rb = simulate_coin("SYN", ROWS["R0"], hours=dfb, mmr=0.005)
    assert len(rb["trades"]) == 0 and rb["log"]["recheck_failed"] == 1
    sg = rb["signals"]
    assert list(sg.fate) == ["recheck_failed"] and sg.signal_day.iat[0] == _U("2025-01-16")
    out.append(rb)
    # zero-trade 06:00 window (Tuesday) -> the 10:00 New York window (15:00 UTC)
    dfc = _flat_hours("2024-10-01", 120)
    _signal_day(dfc, "2025-01-13")
    _flat(dfc, "2025-01-14 00:00", "2025-01-28 23:00", 104.0)
    dfc.loc[_U("2025-01-14 11:00"), "trades"] = 0
    dfc = _fin(dfc)
    rc = simulate_coin("SYN", ROWS["R0"], hours=dfc, mmr=0.005)
    assert _one(rc).iloc[0].entry1_time == _U("2025-01-14 15:00") and rc["log"]["zero_trade_window_skips"] == 1
    out.append(rc)
    # the window opens at or below S: skipped
    dfd = _flat_hours("2024-10-01", 120)
    _signal_day(dfd, "2025-01-13")
    _flat(dfd, "2025-01-14 00:00", "2025-01-14 10:00", 104.0)
    _bar(dfd, "2025-01-14 10:00", 104.0, 104.0, 97.5, 97.5)
    _flat(dfd, "2025-01-14 11:00", "2025-01-28 23:00", 97.5)
    dfd = _fin(dfd)
    rd = simulate_coin("SYN", ROWS["R0"], hours=dfd, mmr=0.005)
    assert len(rd["trades"]) == 0 and list(rd["signals"].fate) == ["skipped_open_at_or_below_S"]
    out.append(rd)
    say("  (1c) rule 12 deferral to Sunday 11:00 UTC with re-check and S from Saturday; failing re-check; zero-trade "
        "window -> 10:00 NY; open <= S skipped ok")
    return out


def _test_rules_6_15(say):
    """(1d) Rule 15: Saturday and Sunday closes below the midline are not acted on; Monday's close still below
    -> exit in Tuesday's 13:00 New York window. (1e) Rule 6 literal: an exit close within 72 h while the mark is
    at or above the average entry is suppressed and re-checked at the next close."""
    out = []
    df = _flat_hours("2024-11-01", 110)
    _signal_day(df, "2025-02-03")                                         # Monday
    _flat(df, "2025-02-04 00:00", "2025-02-08 22:00", 104.0)
    _bar(df, "2025-02-08 23:00", 104.0, 104.0, 100.5, 100.5)            # Saturday bar closes below SMA
    _flat(df, "2025-02-09 00:00", "2025-02-10 22:00", 100.5)            # Sunday close below
    _bar(df, "2025-02-10 23:00", 100.5, 100.6, 100.5, 100.6)            # Monday close still below
    _flat(df, "2025-02-11 00:00", "2025-02-18 23:00", 100.6)
    _bar(df, "2025-02-11 18:00", 100.7, 100.7, 100.7, 100.7)
    df = _fin(df)
    ind = _ref_ind(_ref_daily(df))
    for dd, cl in (("2025-02-08", 100.5), ("2025-02-09", 100.5), ("2025-02-10", 100.6)):
        assert cl < ind.sma[_U(dd)], dd
    r = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005)
    x = _one(r).iloc[0]
    assert x.entry1_time == _U("2025-02-04 11:00") and x.exit_time == _U("2025-02-11 18:00") and x.exit_px == 100.7
    assert x.exit_reason == "mid" and r["log"]["rule15_not_acted"] == 2
    rw = simulate_coin("SYN", ROWS["S1W"], hours=df, mmr=0.005)                # no rule 15: Sunday 13:00 EST
    assert _one(rw).iloc[0].exit_time == _U("2025-02-09 18:00")
    rb = simulate_coin("SYN", h8b_cfg((5, 6)), hours=df, mmr=0.005)            # H8b with the real pair = R0's exit
    assert _one(rb).iloc[0].exit_time == _U("2025-02-11 18:00")
    out += [r, rw, rb]
    # rule 6: entry at 101 after a 120 close; the next close (101.05) is below SMA but above the average entry
    df = _flat_hours("2024-11-01", 140)
    _bar(df, "2025-03-03 23:00", 100.0, 120.5, 100.0, 120.0)            # Monday signal (EST)
    for k, px in enumerate(np.linspace(120.0, 101.0, 11)):
        _bar(df, f"2025-03-04 {k:02d}:00", 120.0 if k == 0 else float(np.linspace(120.0, 101.0, 11)[k - 1]),
             120.0, px, px)
    _flat(df, "2025-03-04 11:00", "2025-03-04 23:00", 101.0)
    _bar(df, "2025-03-04 11:00", 101.0, 101.05, 101.0, 101.05)
    _flat(df, "2025-03-04 12:00", "2025-03-04 23:00", 101.05)
    _flat(df, "2025-03-05 00:00", "2025-03-05 23:00", 100.9)
    _flat(df, "2025-03-06 00:00", "2025-03-20 23:00", 100.9)
    _bar(df, "2025-03-06 18:00", 100.8, 100.8, 100.8, 100.8)
    _bar(df, "2025-03-05 18:00", 100.85, 100.9, 100.85, 100.9)
    df = _fin(df)
    ind = _ref_ind(_ref_daily(df))
    assert 101.05 < ind.sma[_U("2025-03-04")] and 100.9 < ind.sma[_U("2025-03-05")]
    r6 = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005)
    x6 = _one(r6).iloc[0]
    assert x6.entry1_px == 101.0 and x6.entry1_time == _U("2025-03-04 11:00")
    assert x6.exit_time == _U("2025-03-06 18:00") and r6["log"]["rule6_suppressed"] == 1, x6
    rw6 = simulate_coin("SYN", ROWS["S1W"], hours=df, mmr=0.005)
    assert _one(rw6).iloc[0].exit_time == _U("2025-03-05 18:00")
    rm = simulate_coin("SYN", h8a_cfg(72), hours=df, mmr=0.005)       # minimum hold: closes at 13, 37, 61 h < 72 h
    xm = _one(rm).iloc[0]
    assert rm["log"]["rule6_suppressed"] == 3 and xm.exit_time == _U("2025-03-08 18:00"), xm.exit_time
    r24 = simulate_coin("SYN", h8a_cfg(24), hours=df, mmr=0.005)      # 24 h: only the 13 h close is suppressed
    assert r24["log"]["rule6_suppressed"] == 1 and _one(r24).iloc[0].exit_time == _U("2025-03-06 18:00")
    out += [r6, rw6, rm, r24]
    say("  (1d) rule 15: Sat/Sun exits not acted on, Tuesday 18:00 UTC exit; (1e) rule 6 literal and 72 h minimum "
        "hold suppress and re-check ok")
    return out


def _test_bar_size_and_arms(say):
    """(1f) 1-hour bars: a signal closing at 12:00 UTC (EDT) skips the 90-minute ban hours (08:00, 09:00 New
    York) and fills at 14:00 UTC, re-checked on the 13:00 bar, S from it. (1g) H6 timing, H4 touch arm,
    given entries, S11 short, S18 re-entry."""
    out = []
    idx = pd.date_range(_U("2025-04-01"), _U("2025-06-20 23:00"), freq="h").as_unit("ns")
    df = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "trades": 10}, index=idx)
    df["tradable"] = True
    df["funding"] = 0.0
    _bar(df, "2025-06-11 11:00", 100.0, 101.2, 99.5, 101.0)
    for hh in (12, 13):
        _bar(df, f"2025-06-11 {hh}:00", 101.0, 101.3, 100.8, 101.0)
    _flat(df, "2025-06-11 14:00", "2025-06-20 23:00", 101.0)
    df = _fin(df)
    r = simulate_coin("SYN", ROWS["S16"], hours=df, mmr=0.005)
    T = r["trades"]
    assert not r["fills_audit"]
    x = T.iloc[0]
    sma13 = (17 * 100 + 3 * 101) / 20
    a = 1.0
    a = (13 * a + 1.7) / 14
    a = (13 * a + 0.5) / 14
    a = (13 * a + 0.5) / 14
    assert x.entry1_time == _U("2025-06-11 14:00") and _close(x.S, sma13 - a), (x.entry1_time, x.S, sma13 - a)
    assert x.signal_day == _U("2025-06-11 11:00") and x.entry_bar == _U("2025-06-11 13:00")
    rn = simulate_coin("SYN", replace(ROWS["S16"], ban=False), hours=df, mmr=0.005)
    assert rn["trades"].entry1_time.iat[0] == _U("2025-06-11 12:00")
    out += [r, rn]
    # H6 pairs on the EST path of (1a): entry 20 NY (= 01:00 UTC in EST) and exit 20 NY
    dfe = _fin(_flat_hours("2024-10-01", 120))
    _signal_day(dfe, "2025-01-13")
    _flat(dfe, "2025-01-14 00:00", "2025-01-28 23:00", 104.0)
    _bar(dfe, "2025-01-16 23:00", 104.0, 104.0, 100.5, 100.5)          # close below SMA20 = 100.625
    _flat(dfe, "2025-01-17 00:00", "2025-01-28 23:00", 100.5)
    dfe = _fin(dfe)
    assert 100.5 < _ref_ind(_ref_daily(dfe)).sma[_U("2025-01-16")]
    for e, xh, want_e, want_x in ((20, 20, "2025-01-14 01:00", "2025-01-17 01:00"),
                                  (19, 19, "2025-01-14 00:00", "2025-01-17 00:00"),
                                  (6, 13, "2025-01-14 11:00", "2025-01-17 18:00"),
                                  (23, 2, "2025-01-14 04:00", "2025-01-17 07:00")):
        rr = simulate_coin("SYN", h6_cfg(e, xh), hours=dfe, mmr=0.005)
        y = _one(rr).iloc[0]
        assert y.entry1_time == _U(want_e) and y.exit_time == _U(want_x), (e, xh, y.entry1_time, y.exit_time)
        out.append(rr)
    # H4 touch arm: buy-stop at the upper band of each completed day; 2025-01-14's band is touched at 03:00
    dft = _flat_hours("2024-10-01", 120, hi_off=0.0)                     # daily highs = 100 = the band: no touch
    _bar(dft, "2025-01-14 03:00", 100.0, 103.0, 100.0, 102.0)
    _flat(dft, "2025-01-14 04:00", "2025-01-28 23:00", 102.0)
    dft = _fin(dft)
    rt = simulate_coin("SYN", h4_touch_cfg(), hours=dft, mmr=0.005)
    y = _one(rt).iloc[0]
    assert y.entry1_time == _U("2025-01-14 04:00") and y.entry1_px == 100.0 and y.touch    # level 100 (sigma 0)
    assert y.signal_day == _U("2025-01-13") and _close(y.S, 99.0)                         # SMA 100 - ATR 1
    # minute-resolved touch: a dip below S at 03:05 precedes the touch at 03:30, so it cannot stop the position
    mi = pd.date_range(_U("2025-01-14 03:00"), periods=60, freq="min").as_unit("ns")
    mt_ = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "trades": 5}, index=mi)
    mt_.loc[mi[5], ["low", "close"]] = [98.5, 99.5]
    mt_.loc[mi[30], ["open", "high", "close"]] = [100.5, 103.0, 102.0]
    mt_.loc[mi[31]:, ["open", "high", "low", "close"]] = 102.0
    dft2 = dft.copy()
    dft2.loc[_U("2025-01-14 03:00"), "low"] = 98.5
    rtm = simulate_coin("SYN", h4_touch_cfg(), hours=dft2, minutes=mt_, mmr=0.005)
    ym = _one(rtm).iloc[0]
    assert ym.entry1_time == mi[31] and ym.entry1_px == 100.5 and ym.exit_reason == "window_end", ym
    out.append(rtm)
    ep = h4_episodes("SYN", hours=dft)
    assert len(ep) == 1 and ep.start.iat[0] == _U("2025-01-14 03:00") and pd.isna(ep.end.iat[0])
    assert ep.start_day.iat[0] == _U("2025-01-13") and assign_episodes(rt["trades"], ep).tolist() == [0]
    out.append(rt)
    # given entries (luck benchmark): decision days -> R0's windows, block, skip rules; no signal re-check
    dfg = _flat_hours("2024-10-01", 120)
    _bar(dfg, "2025-01-15 23:00", 100.0, 100.0, 99.5, 99.5)              # Wednesday close below SMA: exit Thu
    dfg = _fin(dfg)
    rg = simulate_coin("SYN", luck_cfg(3.0), hours=dfg, mmr=0.005,
                       given_entries=["2025-01-14", "2025-01-15", "2025-01-17"])      # Tue, Wed (dropped), Fri
    rgs = simulate_coin("SYN", replace(luck_cfg(3.0), direction="longshort"), hours=dfg, mmr=0.005,
                        given_entries=pd.Series([-1], index=[_U("2025-01-14")]))           # a short decoy
    ys = _one(rgs).iloc[0]
    assert ys.side == -1 and ys.entry1_time == _U("2025-01-14 11:00") and ys.S > ys.entry1_px
    Tg = rg["trades"]
    assert not rg["fills_audit"]
    assert list(Tg.entry1_time) == [_U("2025-01-14 11:00"), _U("2025-01-19 11:00")], list(Tg.entry1_time)
    assert Tg.given.all() and rg["log"]["given_dropped"] == 1 and Tg.signal_day.iat[0] == _U("2025-01-13")
    assert list(Tg.exit_reason) == ["mid", "window_end"] and Tg.exit_time.iat[0] == _U("2025-01-16 18:00")
    out.append(rg)
    # S11: a fresh close below the lower band near the 60-day low -> short; cover on a close above the midline
    dfs = _flat_hours("2024-10-01", 120)
    _bar(dfs, "2025-01-13 23:00", 100.0, 100.0, 95.5, 96.0)
    _flat(dfs, "2025-01-14 00:00", "2025-01-16 22:00", 96.0)
    _bar(dfs, "2025-01-14 12:00", 96.0, 96.0, 94.0, 94.0)               # close <= 0.98 e1 -> add at 13:00
    _flat(dfs, "2025-01-14 13:00", "2025-01-16 22:00", 94.0)
    _bar(dfs, "2025-01-16 23:00", 94.0, 99.8, 94.0, 99.8)               # close above SMA
    _flat(dfs, "2025-01-17 00:00", "2025-01-28 23:00", 99.8)
    dfs = _fin(dfs)
    ind = _ref_ind(_ref_daily(dfs))
    D = _U("2025-01-13")
    S_s = ind.sma[D] + ind.atr[D]
    rs = simulate_coin("SYN", ROWS["S11"], hours=dfs, mmr=0.005)
    y = _one(rs).iloc[0]
    assert y.side == -1 and y.entry1_time == _U("2025-01-14 11:00") and _close(y.S, S_s)
    assert y.n_tranches == 2 and y.exit_time == _U("2025-01-17 18:00") and y.exit_reason == "mid"
    q = (1 / 3) / 96 + (1 / 3) / 94
    avg = (2 / 3) / q
    c_t = TAKER["base"] + SLIP_OTHER
    assert _close(y.ret_gross, -q * (99.8 - avg)) and _close(y.fees, 2 / 3 * c_t + c_t * q * 99.8)
    assert _close(y.liq_px0, 96 + (1 / 9 - c_t / 3) / ((1 / 3) / 96) - 0.005 * 96)
    out.append(rs)
    # S18: after a TP-all exit while closes stay above the band, the next qualifying close re-enters
    dfr = _flat_hours("2024-10-01", 120)
    _signal_day(dfr, "2025-01-13")
    _flat(dfr, "2025-01-14 00:00", "2025-01-14 10:00", 104.0)
    _bar(dfr, "2025-01-14 11:00", 104.0, 104.0, 104.0, 104.0)
    _bar(dfr, "2025-01-14 12:00", 104.0, 125.0, 104.0, 124.0)            # TP-all (S10) at 122.15
    _flat(dfr, "2025-01-14 13:00", "2025-01-28 23:00", 124.0)
    dfr = _fin(dfr)
    base = ROWS["S10_tp_all"]
    r0 = simulate_coin("SYN", base, hours=dfr, mmr=0.005)
    assert len(r0["trades"]) == 1
    r18 = simulate_coin("SYN", replace(base, reentry="same_episode"), hours=dfr, mmr=0.005)
    T18 = r18["trades"]
    assert len(T18) == 2 and T18.reentry.tolist() == [False, True] and T18.entry1_time.iat[1] == _U("2025-01-15 11:00")
    out += [r0, r18]
    say("  (1f) 1h bars: ban hours skipped, 14:00 UTC fill, S from the 13:00 bar; (1g) H6 pairs, touch arm, given "
        "entries, S11 short, S18 re-entry ok")
    return out


def _test_misc(say):
    """(1i) Add then stop in one hour; at_S; stop active while a trend exit waits; perp_end forced close; S12
    membership mask; S20 weekly entry at Monday's 06:00 New York window."""
    out = []
    S = 100.2 - (13 * 2 + 5.5) / 14
    c_t = TAKER["base"] + SLIP_OTHER
    df = _flat_hours("2025-03-20", 100)
    _signal_day(df, "2025-06-10")
    _flat(df, "2025-06-11 00:00", "2025-06-20 23:00", 104.0)
    _bar(df, "2025-06-11 11:00", 104.0, 106.2, 104.0, 106.2)            # close >= 1.02 e1: add pending
    _bar(df, "2025-06-11 12:00", 106.3, 106.3, 97.0, 98.0)              # add fills at the open, then the stop
    _flat(df, "2025-06-11 13:00", "2025-06-20 23:00", 98.0)
    df = _fin(df)
    r = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005)
    x = _one(r).iloc[0]
    tr = r["tranches"]
    assert list(tr.kind) == ["entry", "add", "stop"] and tr.px.iat[1] == 106.3 and _close(tr.px.iat[2], S)
    q1, q2 = (1 / 3) / 104, (1 / 3) / 106.3
    assert _close(x.ret, q1 * (S - 104) + q2 * (S - 106.3) - 2 / 3 * c_t - c_t * (q1 + q2) * S)
    out.append(r)
    # at_S: a gap open below S still fills at S (exempt from the range audit)
    dg = _flat_hours("2025-03-20", 100)
    _signal_day(dg, "2025-06-10")
    _flat(dg, "2025-06-11 00:00", "2025-06-20 23:00", 104.0)
    _bar(dg, "2025-06-11 12:00", 97.0, 97.5, 96.5, 97.0)
    _flat(dg, "2025-06-11 13:00", "2025-06-20 23:00", 97.0)
    dg = _fin(dg)
    rs = simulate_coin("SYN", ROWS["R0_at_S"], hours=dg, mmr=0.005)
    assert _close(_one(rs).iloc[0].exit_px, S)
    out.append(rs)
    # a trend exit waits for 13:00 New York; the stop fires first at 05:00 UTC
    dw = _flat_hours("2024-10-01", 120)
    _signal_day(dw, "2025-01-13")
    _flat(dw, "2025-01-14 00:00", "2025-01-28 23:00", 104.0)
    _bar(dw, "2025-01-16 23:00", 104.0, 104.0, 100.5, 100.5)            # exit signal (below SMA 100.625)
    _flat(dw, "2025-01-17 00:00", "2025-01-28 23:00", 100.5)
    _bar(dw, "2025-01-17 05:00", 100.5, 100.5, 97.0, 97.5)              # below S before the 18:00 window
    _flat(dw, "2025-01-17 06:00", "2025-01-28 23:00", 97.5)
    dw = _fin(dw)
    rw = simulate_coin("SYN", ROWS["R0"], hours=dw, mmr=0.005)
    y = _one(rw).iloc[0]
    assert y.exit_reason == "stop" and y.exit_time == _U("2025-01-17 06:00") and _close(y.exit_px, S)
    out.append(rw)
    # perp_end: forced close at that bar's close (taker + slippage); nothing tradable afterwards
    dp = _flat_hours("2024-10-01", 120)
    _signal_day(dp, "2025-01-13")
    _flat(dp, "2025-01-14 00:00", "2025-01-28 23:00", 104.0)
    _bar(dp, "2025-01-15 09:00", 104.0, 104.5, 103.5, 103.8)
    dp.loc[_U("2025-01-15 09:00"), "perp_end"] = True
    aft = dp.index > _U("2025-01-15 09:00")
    dp.loc[aft, "tradable"] = False
    dp.loc[aft, "trades"] = 0
    dp.loc[aft, ["open", "high", "low", "close"]] = 103.8
    dp = _fin(dp)
    rp = simulate_coin("SYN", ROWS["R0"], hours=dp, mmr=0.005)
    z = _one(rp).iloc[0]
    q1 = (1 / 3) / 104
    assert z.exit_reason == "delist" and z.exit_time == _U("2025-01-15 10:00") and z.exit_px == 103.8
    assert _close(z.ret, q1 * (103.8 - 104) - c_t / 3 - c_t * q1 * 103.8)
    out.append(rp)
    # S12-style membership: entries only in months the coin is a member
    dm = _fin(df)
    rm = simulate_coin("SYN", ROWS["R0"], hours=dm, mmr=0.005,
                       entry_allowed=pd.Series([True, False], index=[_U("2025-03-01"), _U("2025-06-01")]))
    assert len(rm["trades"]) == 0 and list(rm["signals"].fate) == ["pending_at_end"]
    # S20: weekly bars (Monday-labelled weeks); the week of 2025-01-13 closes Monday 2025-01-20 00:00 at 104
    dwk = _flat_hours("2024-03-04", 340)
    _signal_day(dwk, "2025-01-19")
    _flat(dwk, "2025-01-20 00:00", "2025-02-06 23:00", 104.0)
    dwk = _fin(dwk)
    rk = simulate_coin("SYN", ROWS["S20"], hours=dwk, mmr=0.005)
    k = _one(rk).iloc[0]
    assert k.signal_day == _U("2025-01-13") and k.entry1_time == _U("2025-01-20 11:00") and _close(k.S, S)
    assert k.L_used == 1.0
    out += [rm, rk]
    say("  (1i) add then stop in one hour, at_S, stop while a trend exit waits, perp_end close, membership mask, "
        "S20 weekly entry ok")
    return out


def _test_liquidation(say):
    """(2) Liquidation check: with every stop failing 2025-10-10 20:00-23:00 UTC, a crash through the liquidation
    price liquidates exactly once and loses the isolated margin only (-1/9 of M for one tranche at L = 3); without
    the stress the stop fills at 0.99 x S. A gap through the liquidation price at L = 5 is a liquidation. The L
    cap keeps S 2 points above the full position's liquidation price."""
    out = []
    df = _flat_hours("2025-07-01", 120)
    _signal_day(df, "2025-10-08")                                         # Wednesday, EDT
    _flat(df, "2025-10-09 00:00", "2025-10-10 19:00", 104.0)
    _flat(df, "2025-10-09 10:00", "2025-10-10 19:00", 103.0)
    _bar(df, "2025-10-09 10:00", 104.0, 104.0, 103.0, 103.0)
    _bar(df, "2025-10-10 20:00", 103.0, 103.0, 60.0, 62.0)
    _flat(df, "2025-10-10 21:00", "2025-10-28 23:00", 62.0)
    df = _fin(df)
    rs = simulate_coin("SYN", ROWS["R0_stress"], hours=df, mmr=0.005)
    x = _one(rs).iloc[0]
    c_t = TAKER["base"] + SLIP_OTHER
    q = (1 / 3) / 104
    IM = 1 / 9 - c_t / 3
    liq = 104 - IM / q + 0.005 * 104
    assert x.liquidated and x.exit_reason == "liq" and rs["log"]["liquidations"] == 1
    assert _close(x.exit_px, liq) and _close(x.ret, -1 / 9) and x.exit_time == _U("2025-10-10 21:00"), x
    assert rs["log"]["stops_failed_stress"] == 1
    assert (rs["tranches"].kind == "liq").sum() == 1 and rs["tranches"].time.max() == _U("2025-10-10 21:00")
    r0 = simulate_coin("SYN", ROWS["R0"], hours=df, mmr=0.005)
    y = _one(r0).iloc[0]
    S = 100.2 - (13 * 2 + 5.5) / 14
    assert not y.liquidated and y.exit_reason == "stop" and _close(y.exit_px, 0.99 * S)
    out += [rs, r0]
    # mark-price low reaches the liquidation price while last price stays above the stop: liquidated
    dfm = df.copy()
    _bar(dfm, "2025-10-10 20:00", 103.0, 103.0, 99.0, 100.0)
    _flat(dfm, "2025-10-10 21:00", "2025-10-28 23:00", 100.0)
    dfm.loc[_U("2025-10-10 20:00"), "mark_low"] = 65.0
    dfm = _fin(dfm)
    rm = simulate_coin("SYN", ROWS["R0"], hours=dfm, mmr=0.005)
    z = _one(rm).iloc[0]
    assert z.liquidated and _close(z.ret, -1 / 9) and rm["log"]["liquidations"] == 1
    # L = 5: a gap open below the liquidation price (stop fill below liq) is a liquidation
    dfg = df.copy()
    _bar(dfg, "2025-10-10 20:00", 70.0, 70.0, 60.0, 62.0)
    dfg = _fin(dfg)
    r5 = simulate_coin("SYN", ROWS["S3_L5"], hours=dfg, mmr=0.005)
    w = _one(r5).iloc[0]
    assert w.L_used == 5.0 and w.liquidated and _close(w.ret, -(1 / 3) / 5.0)
    out += [rm, r5]
    # leverage cap binds on a wide stop (near-high off): S = 40.2, L_used = 1 / 0.648019...
    dfc = _flat_hours("2024-10-01", 120, hi_off=30.0, lo_off=30.0)
    _signal_day(dfc, "2025-01-13", close=104.0, high=104.5)
    _flat(dfc, "2025-01-14 00:00", "2025-01-28 23:00", 104.0)
    dfc = _fin(dfc)
    rc = simulate_coin("SYN", ROWS["S7_off"], hours=dfc, mmr=0.005)
    v = _one(rc).iloc[0]
    S = 100.2 - (13 * 60 + 60) / 14
    A = (1 + 1.02 + 1.05) / 3 * 104
    Lmax = 1 / (1 + c_t + 0.005 - (S - 0.02 * 104) / A)
    assert _close(v.S, S) and _close(v.L_used, Lmax) and v.l_capped, (v.S, S, v.L_used, Lmax)
    out.append(rc)
    # the cap on the position actually held after both adds (R0 price adds, S4 one piece, S5 ROE adds, whose add
    # levels move with the capped L): closes exactly at each add level, adds at the next opens; liq of the full
    # position from its fills and fees; S must sit >= 2 points of entry1 above it
    gaps = {}
    for name, cfg in (("R0", ROWS["S7_off"]), ("S4", replace(ROWS["S4"], near_high="off")),
                      ("S5", replace(ROWS["S5"], near_high="off"))):
        d0 = _flat_hours("2024-10-01", 120, hi_off=30.0, lo_off=30.0)
        _signal_day(d0, "2025-01-13", close=104.0, high=104.5)
        _flat(d0, "2025-01-14 00:00", "2025-01-28 23:00", 104.0)
        p0 = _one(simulate_coin("SYN", cfg, hours=_fin(d0), mmr=0.005)).iloc[0]
        Lu, e1 = p0.L_used, p0.entry1_px
        a1, a2 = (1 + 0.02 / Lu, 1 + 0.05 / Lu) if cfg.adds == "roe" else (1.02, 1.05)
        if cfg.adds != "none":
            _flat(d0, "2025-01-14 12:00", "2025-01-14 13:00", float(np.nextafter(a1 * e1, np.inf)))
            _flat(d0, "2025-01-14 14:00", "2025-01-28 23:00", float(np.nextafter(a2 * e1, np.inf)))
        rr = simulate_coin("SYN", cfg, hours=_fin(d0), mmr=0.005)
        p = _one(rr).iloc[0]
        tr_ = rr["tranches"][rr["tranches"].kind.isin(["entry", "add"])]
        assert p.l_capped and p.L_used == Lu and len(tr_) == (1 if cfg.adds == "none" else 3), (name, p, tr_)
        Q = (tr_.frac / tr_.px).sum()
        IM = tr_.frac.sum() / Lu - tr_.cost.sum()
        avg = tr_.frac.sum() / Q
        liq_full = avg - IM / Q + 0.005 * avg
        gaps[name] = (p.S - liq_full) / e1
        assert gaps[name] >= LCAP_PTS - 1e-12, (name, gaps[name])
        if cfg.adds == "roe":                                         # the fixed point binds exactly
            Ap = (3 + 0.07 / Lu) / 3 * e1
            assert _close(p.S - Ap * (1 - 1 / Lu + c_t + 0.005), LCAP_PTS * e1, 1e-10), name
        if cfg.adds == "none":
            assert _close(gaps[name], LCAP_PTS, 1e-10), name
        out.append(rr)
    say(f"  (2) liquidation: once, loss = isolated margin (ret {x.ret:.6f} = -1/9); mark-low and gap liquidations; "
        f"L cap {v.L_used:.4f}; after both adds (S - liq_full) / entry1 = R0 {gaps['R0']:.4f}, S4 {gaps['S4']:.4f}, "
        f"S5 {gaps['S5']:.4f} >= 0.02 ok")
    return out


def _test_regressions(say):
    """(1j) Regression checks for the engine review: an injected frame changed in place is re-prepared; the touch
    arm survives a whipsaw path with more positions than daily bars; S6 stops and exits on SMA20 (midline="bb"
    for the row's own midline); S12 keys map to the prereg's pools; hours whose minutes disagree with the hourly
    bar are resolved on the hourly bar; H4's touch arm shares S1's L."""
    out = []
    # (a) in-place change of an injected hourly frame: the breakout is erased -> no trade (as from a copy)
    df = _flat_hours("2024-10-01", 120)
    _signal_day(df, "2025-01-13")
    _flat(df, "2025-01-14 00:00", "2025-01-28 23:00", 104.0)
    H = _fin(df)
    assert len(_one(simulate_coin("SYN", ROWS["R0"], hours=H, mmr=0.005))) == 1
    P1 = prepare("SYN", H)
    assert prepare("SYN", H) is P1                                    # unchanged frame: a cache hit
    after = H.index >= _U("2025-01-13 23:00")
    for c in bd.PX + ["sig_" + a for a in bd.PX]:
        H.loc[after, c] = 100.0
    r_in = simulate_coin("SYN", ROWS["R0"], hours=H, mmr=0.005)
    r_cp = simulate_coin("SYN", ROWS["R0"], hours=H.copy(), mmr=0.005)
    assert len(r_in["trades"]) == 0 and r_in["log"]["signals"] == 0 and len(r_cp["trades"]) == 0
    assert prepare("SYN", H) is not P1
    out += [r_in, r_cp]
    # (b) touch arm on a whipsaw path: every hour touches the band (100) and dips below S (99) for days
    dw = _flat_hours("2024-10-01", 100, hi_off=0.0, lo_off=1.0)
    wh = dw.index >= _U("2024-12-20")
    dw.loc[wh, ["open", "high", "low", "close"]] = [100.0, 101.0, 98.0, 100.0]
    dw = _fin(dw)
    nb = len(bd.bars_from_hours(dw, "1d", "sig"))
    rw = simulate_coin("SYN", h4_touch_cfg(), hours=dw, mmr=0.005)
    Tw = rw["trades"]
    assert len(Tw) > nb + 8 and rw["log"]["positions"] == len(Tw) == rw["log"]["touch_entries"], (len(Tw), nb)
    assert (Tw.exit_reason.iloc[:-1] == "stop").all() and Tw.entry1_time.is_monotonic_increasing
    out.append(rw)
    # (c) S6: the band changes the signal only; stop and trend exit stay on SMA20 (midline="bb": the row's own)
    df = _fin(df)
    ind = _ref_ind(_ref_daily(df))
    D = _U("2025-01-13")
    S0 = ind.sma[D] - ind.atr[D]
    Pp = prepare("SYN", df)
    s0 = _signals(Pp, ROWS["R0"])
    for row, n in (("S6_bb50_2", 50), ("S6_bb10_1.9", 10)):
        sr = _signals(Pp, ROWS[row])
        assert np.array_equal(sr["stopL"], s0["stopL"], equal_nan=True) and np.array_equal(sr["exitL"], s0["exitL"])
        xr = _one(simulate_coin("SYN", ROWS[row], hours=df, mmr=0.005)).iloc[0]
        xb = _one(simulate_coin("SYN", replace(ROWS[row], midline="bb"), hours=df, mmr=0.005)).iloc[0]
        smn = _ref_daily(df).close.rolling(n).mean()[D]
        assert _close(xr.S, S0) and _close(xb.S, smn - ind.atr[D]) and not _close(xb.S, S0), (row, xr.S, xb.S)
    # (d) S12 keys: the prereg's top 3 / top 6 are the 40-coin pool, top 10 the all-contract (crypto-only) pool
    assert ROW_UNIVERSE["S12_top3"][:3] == ("s12", "40", 3) and ROW_UNIVERSE["S12_top6"][:3] == ("s12", "40", 6)
    assert ROW_UNIVERSE["S12_top10"] == ("s12", "all", 10, False)
    assert ROW_UNIVERSE[H1_S12_GATE] == ("s12", "all", 3, False) and S12_UNIVERSES["S12 top 6"] == "S12_top6"
    assert all(k in ROWS for k in ROW_UNIVERSE) and all(v in ROWS for v in S12_UNIVERSES.values())
    # (e) minutes that disagree with the hourly bar (data inventory section 5): the hour falls back to the hourly
    # stop rule. Minutes missing the hourly low (stop in the gap) and minutes reaching below it.
    S = 100.2 - (13 * 2 + 5.5) / 14
    for case, hb, mins, want in (("miss", (99.0, 99.0, 97.0, 98.5), [(30, 99.0, 99.0, 98.5, 98.8)], S),
                                 ("wider", (99.0, 99.0, 97.9, 98.5), [(31, 98.2, 98.3, 97.5, 97.6)], S)):
        de = _flat_hours("2025-03-20", 100)
        _signal_day(de, "2025-06-10")
        _flat(de, "2025-06-11 00:00", "2025-06-20 23:00", 104.0)
        _flat(de, "2025-06-11 22:00", "2025-06-20 23:00", hb[3])
        _bar(de, "2025-06-11 21:00", *hb)
        de = _fin(de)
        b21 = _U("2025-06-11 21:00")
        mi = pd.date_range(b21, periods=60, freq="min").as_unit("ns")
        mm = pd.DataFrame({"open": 99.0, "high": 99.0, "low": 99.0, "close": 99.0, "trades": 5}, index=mi)
        for k, o_, h_, l_, c_ in mins:
            mm.iloc[k, :4] = [o_, h_, l_, c_]
        mm.iloc[-1, 2:4] = [hb[3], hb[3]]                             # the hour closes at the hourly close
        re_ = simulate_coin("SYN", ROWS["R0"], hours=de, minutes=mm, mmr=0.005)
        y = _one(re_).iloc[0]
        assert y.exit_reason == "stop" and _close(y.exit_px, want) and y.exit_time == b21 + pd.Timedelta("1h"), (case, y)
        assert re_["log"]["m1_hours_hourly_fallback"] == 1 and re_["log"]["stops_minute_resolved"] == 0, case
        mm_ok = mm.copy()                                             # consistent minutes: resolved on them
        for c in bd.PX:
            mm_ok[c] = mm_ok[c].clip(lower=hb[2])
        mm_ok.iloc[0, 2] = hb[2]
        ro = simulate_coin("SYN", ROWS["R0"], hours=de, minutes=mm_ok, mmr=0.005)
        assert ro["log"]["m1_hours_hourly_fallback"] == 0 and ro["log"]["stops_minute_resolved"] == 1, case
        out += [re_, ro]
    # (f) H4: the touch arm is S1's rules and leverage with a different entry
    assert replace(h4_touch_cfg(), entry_mode="close") == ROWS["S1"] and h4_touch_cfg().L == ROWS["S1"].L == 3.0
    say(f"  (1j) regressions: in-place frame change re-prepared; touch arm {len(Tw)} positions > {nb} daily bars + 8 "
        f"(no overflow); S6 stop / exit on SMA20; S12 pools; minute/hourly mismatch -> hourly rule; H4 at S1's L ok")
    return out


def _gbm_hours(n, sigma, seed, start="2000-01-03", drift=None) -> pd.DataFrame:
    """Hourly GBM with exact Brownian-bridge highs and lows in log space (continuous path, so fills at S or TP
    are fair). drift: per-hour expected simple return (scalar or array); None = martingale (log drift -s^2/2)."""
    rng = np.random.default_rng(seed)
    mu = 0.0 if drift is None else drift
    dlog = np.log1p(mu) - 0.5 * sigma ** 2 + sigma * rng.standard_normal(n)
    lc = np.log(100.0) + np.cumsum(dlog)
    lo_ = np.r_[np.log(100.0), lc[:-1]]
    d2 = (lc - lo_) ** 2
    mx = 0.5 * (lo_ + lc + np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    mn = 0.5 * (lo_ + lc - np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    idx = pd.date_range(_U(start), periods=n, freq="h").as_unit("ns")
    df = pd.DataFrame({"open": np.exp(lo_), "high": np.exp(mx), "low": np.exp(mn), "close": np.exp(lc),
                       "trades": np.full(n, 10, np.int64)}, index=idx)
    df["tradable"] = True
    df["funding"] = 0.0
    for a in bd.PX:
        df["sig_" + a] = df[a]
    df["live"] = df["sig_live"] = True
    df["seg"] = 0
    return df


_MG_CFGS = {"S1z": replace(_S1, fees="zero"), "R0z": replace(_R0, fees="zero"), "S1b": _S1, "R0b": _R0}


def _mg_worker(args):
    """One synthetic martingale coin under the four control rows (top level so that a process pool can run it)."""
    i, n, sigma, seed = args
    df = _gbm_hours(n, sigma, seed + i)
    out = {}
    for k, cfg in _MG_CFGS.items():
        r = simulate_coin(f"MG{i}", cfg, hours=df, mmr=0.005, detail=False)
        T = r["trades"]
        tr = r["tranches"]
        f = tr[tr.kind != "end"].groupby("pos").cost.sum().reindex(T.pos).fillna(0.0).to_numpy()
        out[k] = (T[["ret", "ret_gross", "fees", "n_tranches"]].to_numpy(float), len(r["fills_audit"]),
                  float(np.max(np.abs(f - T.fees.to_numpy(float)))) if len(T) else 0.0)
    clear_cache()
    return out


def _pool_map(fn, jobs, workers=4):
    try:
        import multiprocessing as mp
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as ex:
            return list(ex.map(fn, jobs, chunksize=1))
    except Exception as e:                                            # no fork: run serially
        print(f"  (process pool unavailable: {e!r}; running serially)", flush=True)
        return [fn(j) for j in jobs]


def _martingale(say, n_coins=160, years=50, sigma=0.01, seed=20261018):
    """(3) Engine known answer: on hourly martingales (zero mean simple return, log drift -s^2/2; GBM with exact
    Brownian-bridge highs and lows), S1's and R0's mean trade return per M before costs and funding is within 2 SE
    of zero over >= 20,000 trades; after costs it is minus the round-trip cost (fees recomputed from the fills);
    fill audit empty."""
    n = int(years * 365 * 24)
    t0 = time.time()
    res_all = _pool_map(_mg_worker, [(i, n, sigma, seed) for i in range(n_coins)])
    res = {}
    audit = 0
    fee_diff = 0.0
    for k in _MG_CFGS:
        X = np.concatenate([r[k][0] for r in res_all])
        audit += sum(r[k][1] for r in res_all)
        fee_diff = max(fee_diff, max(r[k][2] for r in res_all))
        x = X[:, 0]
        res[k] = (len(x), x.mean(), x.std(ddof=1) / np.sqrt(len(x)), X[:, 2].mean(), X[:, 3].mean(), X[:, 1].mean())
    for k in ("S1z", "R0z"):
        nn, m, se, _, ntr, _ = res[k]
        assert nn >= 20_000, (k, nn)
        assert abs(m) <= 2 * se, (k, m, se)
        say(f"  (3) martingale {k[:2]} before costs and funding: {nn:,} trades, mean {m:+.5f} of M (SE {se:.5f}, "
            f"|t| {abs(m) / se:.2f} <= 2), tranches per trade {ntr:.2f}")
    for k in ("S1b", "R0b"):
        nn, m, se, fee, _, g = res[k]
        assert abs(m + fee) <= 2 * se, (k, m, fee, se)
        say(f"  (3) martingale {k[:2]} after costs: mean {m:+.5f} vs minus the round-trip cost {-fee:+.5f} "
            f"(difference {m + fee:+.5f}, SE {se:.5f})")
    assert fee_diff < 1e-12 and audit == 0, (fee_diff, audit)
    say(f"  (3) fees per trade = sum of fill costs (max diff {fee_diff:.1e}); fill audit empty; "
        f"{n_coins} coins x {years} y in {time.time() - t0:.0f}s")
    return res


def _drift_worker(args):
    i, n, sigma, seed, mu = args
    from analysis_2026 import bb_stats as bs
    df = _gbm_hours(n, sigma, seed + i, drift=None if mu == 0 else mu)
    r = simulate_coin(f"DR{i}", replace(_S1, fees="zero"), hours=df, mmr=0.005, detail=False)
    T = r["trades"]
    if not len(T):
        return np.zeros((0, 2))
    adj = bs.drift_adjust(T, r["expo"], {f"DR{i}": bs.returns_from_hours(df)}).to_numpy(float)
    clear_cache()
    return np.c_[T.ret.to_numpy(float), adj]


def _drift_control(say, n_coins=64, years=50, sigma=0.01, seed=99, mu=1e-4):
    """(3b) The drift-adjusted mean (bb_stats.drift_adjust on the engine's exposure) is about zero with and
    without a constant drift, while the unadjusted mean carries the drift."""
    n = int(years * 365 * 24)
    for m_ in (0.0, mu):
        X = np.concatenate(_pool_map(_drift_worker, [(i, n, sigma, seed, m_) for i in range(n_coins)]))
        raw, adj = X[:, 0], X[:, 1]
        se_r, se_a = raw.std(ddof=1) / np.sqrt(len(raw)), adj.std(ddof=1) / np.sqrt(len(adj))
        assert abs(adj.mean()) <= 2 * se_a, (m_, adj.mean(), se_a)
        if m_ > 0:
            assert raw.mean() > 2 * se_r, (raw.mean(), se_r)
        say(f"  (3b) drift {m_:.0e}/h: S1 {len(raw):,} trades, unadjusted mean {raw.mean():+.4f} (t "
            f"{raw.mean() / se_r:+.1f}), drift-adjusted {adj.mean():+.4f} (t {adj.mean() / se_a:+.2f}, |t| <= 2)")


def _test_assemble(say):
    """(1h) assemble() known answers on hand-made positions: M = L_used x sizing equity / K; rule 11 freezes
    February's sizing equity after a +100% January; S19 sizes from current equity; T-bill on idle cash; cross
    margin wipes the account at the first hour its joint mark-low equity is below maintenance."""
    def pos(sym, entry, exit_, ret, marks, L=3.0, side=1, liq=False):
        e, x = _U(entry), _U(exit_)
        T = pd.DataFrame({"pos": [0], "sym": [sym], "side": [side], "entry1_time": [e], "exit_time": [x],
                          "ret": [ret], "L_used": [L], "liquidated": [liq], "exit_reason": ["mid"]})
        days = pd.date_range(e.ceil("D"), x.floor("D"), freq="D").as_unit("ns")
        mt = np.asarray(marks(len(days)), float)
        D = pd.DataFrame({"pos": 0, "time": days, "mtm": mt, "margin": 1 / L, "notional": 1.0, "sym": sym})
        hrs = pd.date_range(e.floor("h"), x.floor("h"), freq="h").as_unit("ns")
        X = pd.DataFrame({"pos": 0, "time": hrs, "notional": 1.0, "sym": sym, "pnl_lo": 0.0, "mm": 0.005})
        return {"trades": T, "daily_mtm": D, "expo": X}
    A = pos("A", "2025-01-05 12:00", "2025-01-20 12:00", 1.0, lambda k: np.linspace(0.0, 0.9, k))
    B = pos("B", "2025-02-10 12:00", "2025-02-15 12:00", -0.5, lambda k: np.linspace(0.0, -0.4, k))
    res = {"A": A, "B": B, "C": {"trades": A["trades"].iloc[:0], "daily_mtm": A["daily_mtm"].iloc[:0],
                                 "expo": A["expo"].iloc[:0]}}
    out = assemble(res, ROWS["R0"], "2025-01-01", "2025-03-31")
    eq, T = out["equity"], out["trades"]
    assert out["K"] == 3 and _close(T.M.iat[0], 1.0) and _close(T.M.iat[1], 1.0), T.M.tolist()   # frozen in Feb
    assert out["frozen_months"] == ["2025-02"] and _close(eq[_U("2025-01-21")], 2.0) and _close(eq[_U("2025-03-31")], 1.5)
    assert _close(eq[_U("2025-01-10")], 1.0 + np.linspace(0, 0.9, 15)[4])
    assert _close(out["ret"][_U("2025-01-20")], 2.0 / (1 + 0.9) - 1) and _close(T.pnl_usd.iat[1], -0.5)
    o19 = assemble(res, ROWS["S19"], "2025-01-01", "2025-03-31")
    assert _close(o19["trades"].M.iat[1], 2.0) and _close(o19["equity"].iloc[-1], 1.0)
    ot = assemble(res, ROWS["R0"], "2025-01-01", "2025-03-31", idle_tbill=True)
    tb = bd.tbill_daily(pd.DatetimeIndex([_U("2025-01-01"), _U("2025-01-06")]))
    assert _close(ot["equity"][_U("2025-01-02")], 1.0 + tb[0]), (ot["equity"].iloc[:3], tb)
    # on 2025-01-06 one third of the equity is locked as margin (M / L = 1 / 3 of M = 1)
    i6 = ot["equity"].index.get_loc(_U("2025-01-06"))
    e6 = ot["equity"].iloc[i6] - ot["interest"].iloc[i6]
    assert _close(ot["interest"].iloc[i6 + 1] - ot["interest"].iloc[i6], tb[1] * (ot["equity"].iloc[i6] - 1 / 3))
    assert _close(e6, 1.0 + 0.0)
    # cross margin: B's mark-low P&L at 2025-02-12 05:00 takes the account below maintenance -> wiped
    Bx = B["expo"].copy()
    Bx.loc[Bx.time == _U("2025-02-12 05:00"), "pnl_lo"] = -2.5
    resx = dict(res)
    resx["B"] = dict(B, expo=Bx)
    oc = assemble(resx, ROWS["S3_cross"], "2025-01-01", "2025-03-31")
    assert oc["cross_liquidation"] == _U("2025-02-12 05:00") and oc["dead"]
    assert oc["equity"][_U("2025-02-12")] > 0 and oc["equity"][_U("2025-02-13")] == 0.0
    assert oc["trades"].exit_reason.iat[1] == "cross_liq"
    say("  (1h) assemble: M = L x sizing equity / K, rule 11 freeze, S19 compounding, T-bill on idle cash, cross "
        "liquidation ok")
    return []


def _trend(say, n_coins=12, years=20, sigma=0.01, seed=7):
    """(4) Persistent trends (regime-switching drift, zero on average): S1's mean trade return is positive."""
    n = int(years * 365 * 24)
    out = []
    for i in range(n_coins):
        rng = np.random.default_rng(seed + i)
        # regimes of mean length 90 days with drift +-0.08%/h (about +-1.9%/day), equal shares of each sign
        lens = rng.geometric(1 / (90 * 24), size=n // (24 * 30) + 10)
        sgn = np.where(np.arange(len(lens)) % 2 == 0, 1.0, -1.0)
        drift = np.repeat(sgn * 0.0008, lens)[:n]
        df = _gbm_hours(n, sigma, 1000 + seed + i, drift=drift)
        r = simulate_coin(f"TR{i}", replace(ROWS["S1"], fees="zero"), hours=df, mmr=0.005, detail=False)
        assert not r["fills_audit"]
        out.append(r["trades"].ret.to_numpy())
        clear_cache()
    x = np.concatenate(out)
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    assert m > 3 * se, (m, se)
    say(f"  (4) persistent-trend series: S1 {len(x):,} trades, mean {m:+.4f} > 0 (t {m / se:.1f})")


def _real_audit(say):
    """(5) Fill audit on real BTC / ETH / SOL, R0 and S1 (and S1 at L = 1, S8, S11, H4 touch, R0 stress), full
    window. Mechanics only: counts, never returns."""
    t_one = None
    for sym in bd.PRIMARY:
        for row in ("R0", "S1", "S1_L1", "S8", "S11", "R0_stress", "S3_cross"):
            r = simulate_coin(sym, ROWS[row], start="2020-01-01", end="2026-10-16")
            assert not r["fills_audit"], (sym, row, r["fills_audit"][:3])
            T = r["trades"]
            if len(T):
                assert (T.entry1_time >= _U("2020-01-01")).all() and (T.exit_time >= T.entry1_time).all()
            if row in ("R0", "S1"):
                say(f"  (5) {sym} {row}: {len(T)} positions, {int(T.n_tranches.sum())} tranches, "
                    f"{int(r['log']['stops_minute_resolved'])} minute-resolved stops, fill audit empty")
        r = simulate_coin(sym, h4_touch_cfg(), start="2020-01-01", end="2026-10-16")
        assert not r["fills_audit"]
        t0 = time.time()
        simulate_coin(sym, ROWS["R0"], start="2020-01-01", end="2026-10-16")
        t_one = max(t_one or 0, time.time() - t0)
    # hours whose 1-minute and hourly bars disagree (data inventory section 5) fall back to the hourly bar
    fb = {s: [str(pd.Timestamp(prepare(s)["t"][h], tz="UTC"))[:16] for h in prepare(s)["m1_fallback"]]
          for s in bd.M1_COINS}
    want = {"BTC": ["2025-01-14 13:00", "2025-01-14 15:00"], "ETH": ["2025-01-14 13:00", "2025-01-29 01:00"],
            "SOL": ["2025-01-29 01:00"], "BNB": [], "XRP": [], "DOGE": ["2025-01-14 13:00"]}
    assert fb == want, fb
    say(f"  (5) minute/hourly mismatch hours resolved on the hourly bar: {sum(map(len, fb.values()))} "
        f"(the data inventory's 2025-01-14 / 2025-01-29 hours)")
    return t_one


def _perturb(H, M, t):
    """Look-ahead control input: every price after the off-boundary minute t x 1.5 and volumes x 0.5 (hours that
    start after t; the straddling hour's traded bar rebuilt from the perturbed minutes when there are minutes,
    else its post-t parts (high, close) scaled; signal and mark series of that hour likewise)."""
    H = H.copy()
    px = ["open", "high", "low", "close"]
    cols = px + ["sig_" + c for c in px] + ["mark_open", "mark_high", "mark_low", "mark_close"]
    after = H.index > t.floor("h")
    for c in cols:
        H.loc[after, c] *= 1.5
    for c in ("quote_volume", "sig_quote_volume"):
        H.loc[after, c] *= 0.5
    hs = t.floor("h")
    if M is not None:
        M = M.copy()
        ma = M.index >= t
        for c in px:
            M.loc[ma, c] *= 1.5
        mm = M[(M.index >= hs) & (M.index < hs + pd.Timedelta("1h"))]
        mm = mm[mm.trades > 0] if ("trades" in mm.columns and (mm.trades > 0).any()) else mm
        # rebuilt from the live minutes, as prepare() compares them (a mismatch would switch the hour to hourly)
        H.loc[hs, ["high", "low", "close"]] = [max(mm.high.max(), H.at[hs, "open"]), mm.low.min(), mm.close.iloc[-1]]
    else:
        H.loc[hs, ["high", "close"]] = [H.at[hs, "high"] * 1.5, H.at[hs, "close"] * 1.5]
    for c in ("sig_close", "sig_high", "mark_close", "mark_high"):
        H.loc[hs, c] *= 1.5
    return H, M


def _lookahead(say, n_cuts=3):
    """(5b) Look-ahead check (Controls), mechanics only: with every price after a random off-boundary minute t
    multiplied by 1.5, every fill stamped before t is unchanged (BTC with minutes, LINK without; R0, S1, S8, S11,
    H4 touch arm)."""
    rng = np.random.default_rng(20261019)
    n = 0
    for sym, use_m in (("BTC", True), ("LINK", False)):
        H = bd.coin_hours(sym)
        M = bd.minutes(sym, "2024-07-01", "2026-10-16") if use_m else None
        cand = pd.date_range("2024-09-01", "2026-10-01", freq="min", tz="UTC").as_unit("ns")
        cand = cand[cand.minute != 0]
        for _ in range(n_cuts):
            t = pd.Timestamp(rng.choice(cand.asi8), tz="UTC")
            H2, M2 = _perturb(H, M, t)
            for cfg in (ROWS["R0"], ROWS["S1_L1"], ROWS["S8"], ROWS["S11"], h4_touch_cfg()):
                kw = {"minutes": M, "hours": H} if use_m else {"hours": H}
                kw2 = {"minutes": M2, "hours": H2} if use_m else {"hours": H2}
                a = simulate_coin(sym, cfg, start="2024-01-01", end="2026-10-16", **kw)
                b = simulate_coin(sym, cfg, start="2024-01-01", end="2026-10-16", **kw2)
                f = lambda r: r["tranches"].query("kind != 'end'").loc[lambda x: x.time < t, ["pos", "kind", "time",
                                                                                            "px", "frac"]]
                fa, fb = f(a).reset_index(drop=True), f(b).reset_index(drop=True)
                assert fa.equals(fb), (sym, cfg.bars, cfg.entry_mode, cfg.timing, t)
                n += 1
            clear_cache()
    say(f"  (5b) look-ahead check: {n} runs (BTC with minutes, LINK without; 5 rows, {n_cuts} cuts each), every "
        f"fill stamped before the cut unchanged")


def _bench(say, t_one):
    """(6) Performance targets (4 CPUs): one coin daily 2020-2026 < 2 s; H6 576 pairs x 3 coins < 15 min; luck
    benchmark 1,000 x {L3, L5} x {W16, W16b} x 3 coins < 30 min; H11b 648 cells x 2 windows < 3 h."""
    bd._coin_hours_full.cache_clear()
    bd._minutes_full.cache_clear()
    bd._bars_cached.cache_clear()
    clear_cache()
    t0 = time.time()
    simulate_coin("BTC", ROWS["R0"], start="2020-01-01", end="2026-10-16")
    t_cold = time.time() - t0
    assert t_one < 2.0 and t_cold < 2.0, (t_one, t_cold)
    say(f"  (6) simulate_coin, one coin, daily, 2020-2026, after numba warm-up: cold (reading the hourly and "
        f"1-minute files) {t_cold:.2f}s, cached {t_one:.3f}s (target < 2 s)")
    pairs = [(e, x) for e in range(0, 24, 4) for x in range(1, 24, 6)]
    for sym in bd.PRIMARY:                                            # load + prepare once (as an H6 run would)
        simulate_coin(sym, h6_cfg(6, 13), start="2020-01-01", end="2026-10-16", detail=False)
    t0 = time.time()
    for sym in bd.PRIMARY:
        for e, x in pairs:
            simulate_coin(sym, h6_cfg(e, x), start="2020-01-01", end="2026-10-16", detail=False)
    per = (time.time() - t0) / (3 * len(pairs))
    h6 = per * 576 * 3
    assert h6 < 15 * 60, h6
    say(f"  (6) H6: {per * 1000:.1f} ms per pair-coin -> 576 x 3 = {h6:.0f}s (target < 900 s)")
    rng = np.random.default_rng(1)
    t0 = time.time()
    nrun = 0
    for sym in bd.PRIMARY:
        days = pd.date_range("2025-06-17", "2026-10-16", freq="D", tz="UTC")
        for k in range(20):
            g = np.sort(rng.choice(days, 12, replace=False))
            simulate_coin(sym, luck_cfg(3.0), start="2025-06-17", end="2026-10-16", given_entries=g, detail=False)
            nrun += 1
    per = (time.time() - t0) / nrun
    luck = per * 1000 * 2 * 2 * 3
    assert luck < 30 * 60, luck
    say(f"  (6) luck benchmark: {per * 1000:.1f} ms per run -> 12,000 runs = {luck:.0f}s (target < 1800 s)")
    t0 = time.time()
    simulate_coin("BTC", replace(ROWS["S16"], bb_k=2.5), start="2025-06-17", end="2026-10-16", detail=False)
    t_sig = time.time() - t0                                              # 1h signal prep + one run
    t0 = time.time()
    for k in range(10):
        simulate_coin("BTC", replace(ROWS["S16"], bb_k=2.5, adds=("price", "roe", "none")[k % 3]),
                      start="2025-06-17", end="2026-10-16", detail=False)
    t_run = (time.time() - t0) / 10
    # 648 cells x 2 windows; coins per cell average (3 + 6 + 10) / 3; 18 signal configs x 10 coins x 3 bar sizes
    runs = 648 * 2 * (3 + 6 + 10) / 3
    h11b = runs * t_run + 18 * 10 * t_sig + 60 * 3                        # plus loading 60 coin files
    assert h11b < 3 * 3600, h11b
    say(f"  (6) H11b: 1h-bar run {t_run * 1000:.0f} ms, signal prep {t_sig:.2f}s -> about {h11b / 60:.0f} min "
        f"(target < 180 min)")


def selftest(quick: bool = False) -> None:
    say = lambda s: print(s, flush=True)  # noqa: E731
    t0 = time.time()
    say("bb_engine selftest")
    runs = []
    runs += _test_path_est(say)
    runs += _test_path_edt_stop(say)
    runs += _test_deferral(say)
    runs += _test_rules_6_15(say)
    runs += _test_bar_size_and_arms(say)
    runs += _test_misc(say)
    runs += _test_liquidation(say)
    runs += _test_regressions(say)
    _test_assemble(say)
    assert all(not r["fills_audit"] for r in runs)
    say(f"  (5) fill audit empty on all {len(runs)} hand-built runs")
    if quick:
        say(f"quick selftest passed in {time.time() - t0:.0f}s")
        return
    _martingale(say)
    _drift_control(say)
    _trend(say)
    t_one = _real_audit(say)
    _lookahead(say)
    _bench(say, t_one)
    say(f"bb_engine selftest passed in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest(quick="--quick" in sys.argv)
    else:
        print(__doc__)
