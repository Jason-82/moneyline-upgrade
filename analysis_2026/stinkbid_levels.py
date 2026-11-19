"""
Level finder of the stink-bid study: the inputs at placement and every level method, as frozen in
analysis_2026/STINKBID_PREREG.md (FROZEN 2026-11-18, commit 72ac2a4):
  §6.1 "Placement and inputs" (V6: bids at Monday 03:30 UTC; spot inputs through d0, futures inputs through d0 - 1;
       the 13:30 sensitivity uses the same inputs; tick from the decimal strings of the last 7 days' 1m prices),
  §6.2 "Level methods" (M1, M2, M2a, M3 pooled and expanding from 2017-08, M4 / M4f / M4s, M5f / M5a / M5b, M6, M7
       with mark-price crossings only up to the last bar published before t0, M8; the admissible band delta in
       [4, 14] for the chart methods M4-M7; the H4 placebos at +-0.5 and +-1.0 ATR%),
  §4.1 (sigma windows and level look-backs never reach back across a segment boundary),
  §10.5 K7 (every level on its venue's tick) and §13 item 1 (the sheet's limit price on Robinhood's tick, delta
       recomputed after rounding);
with the formulas of research_notes/Stink bids/design_draft.md §6.1-6.3 (commit ae5425c), which the pre-registration
incorporates for the levels, and the fidelity critique's V6 and V15. Contract: research_notes/Stink bids/build_spec.md,
"stinkbid_levels.py". Data come from analysis_2026/stinkbid_data.py (read only, never edited). Every value used at a
placement depends only on data inside its information set: windows are sliced at the cutoffs (spot: the end of d0;
futures: the end of d0 - 1), and tables built over a whole series (ATR14, sigma30, segment ids, M3's windows, M8's
market-wide days) are causal row by row and are read at d0 (the selftest perturbs, deletes and shifts everything after
the cutoffs and checks that nothing moves). Nothing here computes an outcome.

    python3 -m analysis_2026.stinkbid_levels selftest [--no-real]    # synthetic known answers, look-ahead checks,
                                                                     # and (unless --no-real) real-data invariants
    python3 -m analysis_2026.stinkbid_levels show NEAR 2023-03-06     # inputs and every level variant, one placement
    python3 -m analysis_2026.stinkbid_levels coverage [--from 2020-01] [--to 2026-11] [--universe U_Q1] [--every 1]
                                                     # counts only: levels given / abstentions per variant

Public API (times UTC; a "day" is a UTC calendar day)
  inputs_at(coin, t0, data=None, series="spot", price=None, tick=None) -> dict
      d0 = the last completed UTC day before t0 (Sunday for Monday 03:30 and 13:30). Spot inputs use spot bars
      through d0; futures inputs (M7) use data through d0 - 1. series="index" (HYPE's perpetual-index proxy, §5) puts
      the price series itself on the futures clock: index daily bars through d0 - 1.
      Keys: coin, series, t0, d0, d_last (the last day of the price series: d0, or d0 - 1 for the index), d_fut,
      P0 (close of d_last, or `price`), close, sigma30 (= sigma), n_ret, atr (Wilder ATR14, price units), atr_pct,
      tick (float), tick_str, tick_dec, tick_source, tick_resolved, tick_raw_str, tick_n_finer, tick_n_prices, seg,
      seg_first_day, seg_days, traded, seg_ok, ok, why. traded: d_last has a bar with trades > 0; seg_ok: sigma30
      has >= 25 returns inside d_last's segment and is > 0; ok: seg_ok and ATR14, the tick and P0 > 0 are valid
      (place bids only when ok; `why` says what failed). `price` replaces P0 (the sheet's fresh reference price);
      `tick` replaces the inferred tick (the sheet's Robinhood tick: every level is then floored directly to it).
      tick_source: 1m | 1d | index-1m | index-1d | given, with "-majority" appended when prints at a finer old tick
      were set aside (tick_raw_str is then the literal smallest step; coding choice 5).
  level(method, inputs, **params) -> (L, delta) or None
      M1 d=0.15..0.50 | M2 k (6, 8, 10; 5, 12) | M2a kA (4, 5, 6) | M3 p (0.02, 0.05, 0.10) | M3c p | M4 N (30, 90,
      365), buffer (0.5, 1.0) [default N=90, buffer=0.5, H4's M4] | M4f N | M4s | M5f | M5a | M5b | M6 | M7 | M8.
      None when a chart method abstains (delta outside [4, 14], or no candidate inside it) or a method has no data.
  level_info(method, inputs, **params) -> dict(L, delta, n_ticks, x (the unrounded level), status, detail, aux)
      status: ok | abstain (chart methods) | no_data | invalid_inputs | non_positive | not_below_P0 | before_start
  levels_all(inputs, variants=VARIANTS) -> DataFrame, one row per pre-registered variant (H4_VARIANTS: H4's four)
  placebos(L, atr_pct=None, tick=None, P0=None, sigma=None, inputs=None) -> [(shift, L_p, delta_p)], shift in
      (-1.0, -0.5, +0.5, +1.0): L_p = floor(L exp(shift ATR%)) on the tick (draft §6.3), delta_p recomputed. Call it
      as placebos(L, inputs=I) (I from inputs_at) or with tick=, P0= and sigma=: build_spec's short form
      placebos(L, atr_pct) has no tick and no delta, and raises ValueError (K7: every level on its venue's tick).
  rh_round(coin, L, P0=None, sigma=None, inputs=None, catalog=None) -> (L_rh, delta_rh): floor to Robinhood's tick
      with delta recomputed (§13 item 1). Call it as rh_round(coin, L, inputs=I) or with P0= and sigma=; build_spec's
      short form rh_round(coin, L) cannot recompute delta and raises ValueError (rh_tick + floor_tick give the bare
      floor). rh_tick(coin, catalog)
  floor_tick(x, tick), floor_n(x, tick), ceil_tick(x, tick), ceil_n(x, tick), tick_value(n, tick) (exact decimal
      tick arithmetic; L - tau as a double is tick_value(n_ticks - 1, tick_str)), price_decimals(x), infer_tick(prices)
  m3_pool(data=None), m8_tables(data=None): the pooled tables (real data when data is None)
  volume_profile(lo, hi, qv, P0, sigma), liquidation_histogram(...): M6 / M7 building blocks (exposed for tests)

Injection ("data", build_spec: every function accepts injected frames). A dict of frames for ONE coin:
  d1        daily bars: open_time, open, high, low, close[, volume, quote_volume, trades, seg]
  h1        hourly bars (M6): open_time, high, low, quote_volume[, trades]
  m1        1m bars: open_time, open, high, low, close[, trades, quote_volume, seg]. Gives the tick; when d1 / h1
            are absent they are built from it (minutes with trades > 0, UTC days / hours)
  tick      a fixed tick (decimal string preferred) instead of inferring it (synthetic prices off any grid)
  metrics   create_time, oi (open interest in coins of the underlying, as stinkbid_data.metrics: contracts x the
            contract multiplier) (M7; a frame without `oi` raises ValueError; oi_usd is not used)
  mark1h    open_time, low (M7)           perp1h  open_time, volume (coins), quote_volume (USD) (M7)
  index_d1, index_m1   the index series (series="index")
  panel     every pair's daily bars for M3 / M8: coin, day or open_time, open, high, low, close[, trades, seg,
            excluded]; backstop (month, coin, excluded) for M3; univ (month, coin, U_B, U_Q1) for M8
  real      True: keys not given load the real data (stinkbid_data); default False when a dict is given, so a
            synthetic world never mixes with real data. data=None reads everything real.
  Derived tables are memoized per frame (in data["_src"]) and built from copies, so a table never mixes old and new
  values. A frame may be replaced by a new object or changed in place (K4-style perturbations) between calls: the
  memo pins a shallow copy of every injected frame it used, so under pandas 3 copy-on-write an in-place change gives
  the changed columns new buffers; the memo compares buffer identities on every use and rebuilds what changed. An
  inputs dict is a snapshot: after changing a frame, call inputs_at again (levels use the daily table the inputs
  were computed from). Writes through numpy views are impossible (pandas 3 returns read-only arrays).
  With data=None the real frames of the 4 most recent coins are cached: loop coin by coin, or keep one dict per
  coin (data={"real": True}: its memo lives in the dict).
  Real 1m ticks come from the cached m1_spot parquet; a coin streamed without a cache file (rest of U-B) needs its
  1m frame injected (data={"m1": frame, "real": True}); otherwise the tick falls back to the daily bars' decimals
  and tick_source says so.

Coding choices the pre-registration leaves open (most literal reading; listed in the build report)
 1. d0 = the UTC day before the day containing t0. For Monday 03:30 and the 13:30 sensitivity it is Sunday, and
    futures run through Saturday (V6: "with the same inputs"). For a daily placement (P1-1) it is the previous day.
 2. sigma30: sample SD (ddof 1) of the daily log close-to-close returns of the 30 days ending d0 whose two closes lie
    in d0's segment. A segment's days are consecutive, so this is the last min(30, days in the segment - 1) returns;
    >= 25 are needed and sigma = 0 is invalid. Bars with trades = 0 are missing days (stinkbid_data's segments).
 3. ATR14: Wilder's RMA seeded with the mean of the segment's first 14 true ranges; the segment's first bar has
    TR = high - low; restarted at every segment (bb_engine / moneyline_ref convention). ATR% = ATR14(d0) / P0.
 4. Segments are stinkbid_data's `seg` (missing or zero-trade day; > 25% open jump), split again at any day gap.
    Injected frames without `seg` get the same rule. Redenomination joins continue positions (§4.1) but are still
    boundaries for sigma windows and look-backs.
 5. Tick (V15): for each open/high/low/close of the 1m bars with trades > 0 in the 7 days d0-6..d0, the number of
    decimals of its shortest decimal string (the smallest d with float(rint(x 10^d)) / 10^d == x, i.e. the float is
    the nearest double of a d-decimal string). tau = 10^-d for the smallest d such that at most 0.1% of the window's
    prices need more than d decimals (TICK_FINER_MAX): the step of the grid that holds at least 99.9% of the
    window's prices. Reading of V15's "(the smallest step)": the step of the venue's price grid, not of any single
    print. Resting orders left at an older, finer tick keep printing for months after Binance coarsens a tick
    (BNB 2021-09-27: 1 of 40,320 window prices, 350.02, on a 0.1 grid); with the literal max over single prints,
    levels fell off the venue's tick (against K7) and F1's trigger L - tau shrank toward a touch (review r1, before
    any outcome). The rule sets such prints aside in 121 of 10,828 U-Q1 coin-weeks (1.1%, 30 coins; 1-28 of about
    40,000 prices each); those weeks get tick_source "1m-majority", with the literal smallest step in tick_raw_str
    and the number of finer prices in tick_n_finer; TICK_FINER_MAX = 0 restores the literal reading. A refinement
    shows at once (0.1% of a week is about 40 prices: 11 minutes of trading); only one of the 121 weeks (LTC
    2022-06-13, 1 finer print) was followed by a week on the finer grid, and a level on the coarser grid is still a
    valid price on a refined grid (its F1 trigger is then one coarse tick deep). Fallbacks, flagged in tick_source:
    no 1m bars in the window -> the daily bars' decimals ("1d"; 28 prices, so the rule is then the literal
    maximum); prices needing more than 12 decimals beyond the 0.1% (synthetic prices off any grid) -> 1e-12 with
    tick_resolved False. To be confirmed by the orchestrator (changed from the literal maximum after review r1).
 6. floor(x)_tau: the largest n with n tau <= x, in exact decimal arithmetic; x within a relative 1e-13 below a grid
    point counts as on it (float rounding of an on-grid price). The level is the double nearest the decimal n tau,
    i.e. the same double the archive's decimal string parses to. n is returned (n_ticks) for exact comparisons.
 7. delta = ln(P0 / L) / sigma on the rounded level; the band check uses that delta, inclusive [4, 14].
 8. A level <= 0 or >= P0 (after rounding) is not a resting bid below the price: None. For a chart method its delta
    is outside [4, 14], so the method abstains; for the others the status is non_positive or not_below_P0; a placebo
    is None. With the pre-registered parameters this happens for M2a when k_A ATR14 >= P0 (ATR% >= 1/k_A, i.e.
    16.7% at k_A = 6), for M4 / M4f / M4s when the look-back low is a bad print within a tick of zero or P0 sits at
    the low, and in principle for M8 if q~ >= 0.
 9. M3's windows, on daily bars back to 2017-08 (the 1m archive starts 2019-12): the life of the bid placed on
    Monday d0'+1 is approximated by the daily lows of d0'+1..d0'+7 (Monday..Sunday); P_t = close of d0', sigma_t =
    sigma30 at d0'. A life stops at a segment end (§4.1: the bid is cancelled); a window with no life day is dropped.
    A window enters at t0 when its last life day d0'+7 <= d0 (it ended before t0). Eligible pairs: every USDT pair
    of stinkbid_data.d1_panel that is not list-excluded and not backstop-excluded in the placement month (U-B's
    exclusions). The p-quantile is numpy's default (linear interpolation, type 7).
10. M3c (a parameter variant of draft §6.2's M3 row, not named in the pre-registration or the build spec): the same
    windows of the coin itself inside d0's segment; >= 104 are needed.
11. M4's N-day window and M4s's pivots stay inside d0's segment (a shorter window near a segment start). M4f exists
    for each N.
12. M4s: a pivot low is a day whose low equals the minimum of the 11 lows from 5 days before to 5 days after (ties
    count), all 11 days in the segment and the 5th day after it <= d0. The pivot itself must have delta in [4, 14]
    ("the most recent confirmed pivot low with delta in [4, 14]"); the band then applies again to the buffered level.
13. M5: e = floor(log10 P0) with exact powers of ten; candidates are the positive multiples of G whose log distance
    from L* is at most 2 sigma; R is the candidate nearest L* in price (ties: the lower). With no candidate, R is
    the positive multiple of g nearest L* (ties: the lower). R is an exact decimal. M5a = floor(R)_tau, M5f =
    floor(R)_tau + tau, M5b = floor(R (1 - 0.5 ATR%))_tau.
14. M6: the hours (trades > 0, quote volume > 0) of the 90 days d0-89..d0 inside d0's segment. Bins of 0.25 sigma in
    log price anchored at ln P0 (bin b holds depths [0.25 b, 0.25 (b+1)) sigma below P0). An hour's quote volume is
    spread uniformly in log price between its low and high (an hour with high = low goes to its bin). The kernel
    (1, 2, 3, 2, 1)/9 is applied as a full convolution (the smoothed profile on its whole support). A node is a
    strict local maximum; a plateau of equal bins is one node. "Median non-zero bin": the median of the smoothed
    profile's positive bins. "Highest HVN": the node with the largest smoothed volume (ties: the shallower). Its
    "lower edge" is the deeper edge of its deepest bin; that edge must have delta in [4, 14]; L = floor(edge)_tau,
    and the band applies to L.
15. M7 (from 2021-12-01 for every coin: prereg §6.2 and H4; the draft's BTC-from-2020-09 is superseded): rows of the
    30 days d0-30..d0-1 inside d0's segment. New OI is measured in contracts and valued at entry: OI_j = oi (the
    archive's sum_open_interest in coins of the underlying, i.e. contracts x the contract multiplier,
    stinkbid_data.metrics); dOI+_j = max(0, OI_j - OI_{j-1}) x p_j (USD), with p_j the hour's perp VWAP, the
    draft's "new OI ... (USD), entered at the hour's perp VWAP". Reading: the USD value of OI
    (sum_open_interest_value = contracts x price) also rises when the price rises with no position opened, so its
    differences are not new positions (prereg §6.2: "an estimate of positions"); on real inputs from 2022 they were
    1.7-2.8x the opened positions (BTC, ETH, SOL, NEAR, DOGE), and 15-18% of the steps they counted had contracts
    falling (review r1, before any outcome; changed from oi_usd differences then; to be confirmed by the
    orchestrator). A row with oi <= 0 or not finite is missing: the archive fills gaps with zero rows (e.g. every
    contract 2022-03-07 15:30 .. 2022-03-08 01:05; 1,535 of the 8,040 U-Q1 coin-weeks from 2021-12 have zero rows in
    their 30-day window), and the step out of a zero run would book the whole open interest as new. Together the
    two changes alter M7's status or level in 1,970 of those 8,040 placements (4,341 levels instead of 4,491):
    dropping zero rows alone changes 1,234, and opened contracts instead of oi_usd differences then change 1,589.
    dOI+_j counts only between consecutive 5-minute rows inside the window (never across a missing row); the hour
    is the 1h perpetual bar holding the 5 minutes that end at row j; VWAP = quote_volume / volume (rows whose hour
    has no volume are skipped). A position is removed when any mark-price 1h bar opening at or after its row and
    before d0 (the last published day is d0 - 1) has low <= its liquidation price. Histogram on M6's grid, smoothed
    as M6; "the median bin" is the median over all bins of the smoothed histogram (zeros included); the peak's
    lower edge must have delta in [4, 14]; L = floor(edge (1 - 0.25 ATR%))_tau; the band applies to L.
16. M8: a market-wide day is a UTC day on which at least 10% of that month's U-B members (stinkbid_data.ranks rank
    <= 100, from 2017-10; members without a bar count as not falling) printed a low <= 0.85 x their previous close
    (consecutive days, one segment). The coin's standardized lows z = ln(low / previous close) / sigma30(previous
    day) on market-wide days <= d0 inside d0's segment; with >= 5 of them q~ = their median, else the median of the
    same z over every U-Q1 member (point in time; universes rebuilt from 2018-08) on market-wide days <= d0. M8 is
    not a chart method: no band.
17. Placebos are computed from the real level after rounding, floored to the same tick, with the same guards; the
    band does not apply to them (H4's depth term handles depth).
18. Robinhood: floor to the catalog's min_order_price_increment (the decimal string). A coin missing from the saved
    catalog, or a reused ticker (LIT: Binance's Litentry is not Robinhood's Lighter), raises.
19. series="index": daily index klines (no trade counts: every bar counts as traded) through d0 - 1. An index has no
    venue tick: the rule of item 5 is applied to the index's own decimal strings (1m if injected, else its daily
    bars). M6 needs volume and has no data on the index (status no_data; the coin's spot hourly bars are never
    mixed in). M7 uses the coin's futures data, on the same clock as the index (through d0 - 1).
20. show(coin, day): a date (midnight) means the Monday 03:30 UTC placement of the date's week (Monday..Sunday); a
    timestamp with a time is used as given (e.g. Monday 13:30 for the sensitivity).
"""
from __future__ import annotations

import math
import sys
import time
from collections import OrderedDict
from decimal import ROUND_CEILING, ROUND_FLOOR, Context, Decimal

import numpy as np
import pandas as pd

from analysis_2026 import stinkbid_data as sbd

DAY_NS = 86_400_000_000_000
HOUR_NS = 3_600_000_000_000
MIN5_NS = 300_000_000_000
DAY = pd.Timedelta("1D")

SIGMA_DAYS, SIGMA_MIN = 30, 25                 # §6.1: SD of the last 30 daily log returns (>= 25 valid, one segment)
ATR_N = 14                                     # Wilder ATR14
JUMP = sbd.JUMP                                # a > 25% open jump starts a new segment (§4.1)
TICK_DAYS = 7                                  # §6.1: tick from the last 7 days' 1m prices
TICK_FINER_MAX = 0.001                         # at most 0.1% of them may print finer than tau (coding choice 5)
DEC_MAX = 12                                   # decimals beyond this are "unresolved" (synthetic prices)
REL_TOL = Decimal("1e-13")                     # a float this close below a grid point is on it (coding choice 6)
BAND = (4.0, 14.0)                             # §6.2: admissible band of the chart methods
CHART = ("M4", "M4f", "M4s", "M5f", "M5a", "M5b", "M6", "M7")
M1_D = (0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
M2_K, M2_K_SEC = (6.0, 8.0, 10.0), (5.0, 12.0)
M2A_K = (4.0, 5.0, 6.0)
M3_P = (0.02, 0.05, 0.10)
M3_LIFE, M3C_MIN = 7, 104
M4_N, M4_BUF, M4F_BUF = (30, 90, 365), (0.5, 1.0), 0.1
PIVOT_SIDE, M4S_BUF = 5, 0.5
M5_DEPTH, M5_BAND, M5B_BUF = 8.0, 2.0, 0.5
M6_DAYS, BIN, HVN_MULT = 90, 0.25, 1.5
KERNEL = np.array([1.0, 2.0, 3.0, 2.0, 1.0]) / 9.0
M7_DAYS, M7_LEV, M7_LEV_W, M7_LONG, M7_MAINT = 30, (5.0, 10.0, 20.0, 50.0), (0.35, 0.30, 0.25, 0.10), 0.5, 0.005
M7_PEAK, M7_BUF, M7_FROM = 2.0, 0.25, pd.Timestamp("2021-12-01", tz="UTC")
M8_DROP, M8_SHARE, M8_MIN = 0.15, 0.10, 5
PLACEBO_SHIFTS = (-1.0, -0.5, 0.5, 1.0)

VARIANTS = tuple(
    [("M1", {"d": d}) for d in M1_D]
    + [("M2", {"k": k}) for k in sorted(M2_K + M2_K_SEC)]
    + [("M2a", {"kA": k}) for k in M2A_K]
    + [("M3", {"p": p}) for p in M3_P]
    + [("M3c", {"p": p}) for p in M3_P]
    + [("M4", {"N": n, "buffer": b}) for n in M4_N for b in M4_BUF]
    + [("M4f", {"N": n}) for n in M4_N]
    + [("M4s", {}), ("M5f", {}), ("M5a", {}), ("M5b", {}), ("M6", {}), ("M7", {}), ("M8", {})])
H4_VARIANTS = (("M4", {"N": 90, "buffer": 0.5}), ("M5b", {}), ("M6", {}), ("M7", {}))
_PARAMS = {"M1": ("d",), "M2": ("k",), "M2a": ("kA",), "M3": ("p",), "M3c": ("p",), "M4": ("N", "buffer"),
           "M4f": ("N",), "M4s": (), "M5f": (), "M5a": (), "M5b": (), "M6": (), "M7": (), "M8": ()}
_DEFAULTS = {"M4": {"N": 90, "buffer": 0.5}, "M4f": {"N": 90}}


# ================================================================ time, decimals, ticks
def _utc(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def day0(t0) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(t0 as a UTC timestamp, d0 = the last completed UTC day before t0, as a tz-naive midnight)."""
    t = _utc(t0)
    return t, t.tz_localize(None).normalize() - DAY


def _dint(day) -> int:
    """tz-naive (or UTC) day -> integer days since 1970-01-01."""
    d = pd.Timestamp(day)
    if d.tzinfo is not None:
        d = d.tz_convert("UTC").tz_localize(None)
    return int(d.value // DAY_NS)


def _day_ts(i: int) -> pd.Timestamp:
    return pd.Timestamp(int(i) * DAY_NS)


def _ns(s) -> np.ndarray:
    """Timestamps (tz-aware or naive UTC) -> int64 nanoseconds."""
    s = pd.to_datetime(pd.Series(s), utc=True).dt.tz_localize(None).astype("datetime64[ns]")
    return s.to_numpy().astype(np.int64)


_CTX = Context(prec=60)
_ONE_TOL = 1 + REL_TOL


def _dec(tick) -> Decimal:
    if isinstance(tick, Decimal):
        return tick
    if isinstance(tick, str):
        return Decimal(tick.strip())
    if isinstance(tick, (int, np.integer)):
        return Decimal(int(tick))
    return Decimal(repr(float(tick)))


def _tick_str(d: int) -> str:
    return "1" if d <= 0 else "0." + "0" * (d - 1) + "1"


def floor_n(x, tick) -> int | None:
    """Number of ticks of floor(x)_tau: the largest n with n tau <= x (coding choice 6). None for x <= 0 / NaN."""
    t = _dec(tick)
    if isinstance(x, Decimal):
        xd = x
    else:
        x = float(x)
        if not math.isfinite(x) or x <= 0:
            return None
        xd = Decimal(x)
    if xd <= 0 or t <= 0:
        return None
    q = _CTX.multiply(_CTX.divide(xd, t), _ONE_TOL)
    return int(q.to_integral_value(rounding=ROUND_FLOOR))


def tick_value(n: int, tick) -> float:
    """The double nearest the decimal n x tau."""
    return float(_CTX.multiply(Decimal(int(n)), _dec(tick)))


def floor_tick(x, tick) -> float | None:
    """floor(x)_tau as a double (None if it is not positive)."""
    n = floor_n(x, tick)
    return None if n is None or n <= 0 else tick_value(n, tick)


def ceil_n(x, tick) -> int | None:
    """Number of ticks of ceil(x)_tau: the smallest n with n tau >= x; x within a relative 1e-13 above a grid point
    counts as on it (the mirror of floor_n; e.g. the flip target R1/2 = ceil(L + (P0 - L) / 2)_tau, prereg §8)."""
    t = _dec(tick)
    if isinstance(x, Decimal):
        xd = x
    else:
        x = float(x)
        if not math.isfinite(x) or x <= 0:
            return None
        xd = Decimal(x)
    if xd <= 0 or t <= 0:
        return None
    q = _CTX.divide(_CTX.divide(xd, t), _ONE_TOL)
    return int(q.to_integral_value(rounding=ROUND_CEILING))


def ceil_tick(x, tick) -> float | None:
    """ceil(x)_tau as a double (None if x is not positive)."""
    n = ceil_n(x, tick)
    return None if n is None or n <= 0 else tick_value(n, tick)


def price_decimals(x, dmax: int = DEC_MAX) -> np.ndarray:
    """Per value: the decimals of its shortest decimal string, i.e. the smallest d with float(rint(x 10^d)) / 10^d == x
    (x is then the double nearest a d-decimal string); -1 when more than dmax are needed or x is not finite."""
    x = np.asarray(x, dtype=float).ravel()
    out = np.full(x.shape, -1, dtype=np.int16)
    todo = np.flatnonzero(np.isfinite(x))
    for d in range(dmax + 1):
        if todo.size == 0:
            break
        p = 10.0 ** d
        xs = x[todo]
        n = np.rint(xs * p)
        ok = (np.abs(n) < 2.0 ** 53) & (n / p == xs)
        out[todo[ok]] = d
        todo = todo[~ok]
    return out


def _dec_counts(dec: np.ndarray) -> np.ndarray:
    """Counts of prices by decimals: index d = 0..DEC_MAX, index DEC_MAX + 1 = unresolved (price_decimals -1)."""
    d = np.where(np.asarray(dec) < 0, DEC_MAX + 1, dec).astype(np.int64).ravel()
    return np.bincount(d, minlength=DEC_MAX + 2)


def tick_rule(counts, finer_max: float = TICK_FINER_MAX):
    """Coding choice 5 on counts of prices by decimals (index DEC_MAX + 1 = unresolved): (d, d_raw, n_finer, n), with
    tau = 10^-d for the smallest d such that at most finer_max of the n prices need more than d decimals (n_finer of
    them), and d_raw the literal maximum (the smallest step of any print). d = DEC_MAX + 1: unresolved. None if no
    prices."""
    c = np.asarray(counts, dtype=np.int64)
    n = int(c.sum())
    if n == 0:
        return None
    finer = n - np.cumsum(c)                                   # prices needing more than d decimals
    d = int(np.flatnonzero(finer <= finer_max * n)[0])         # finer[-1] = 0: always found
    return d, int(np.flatnonzero(c)[-1]), int(finer[d]), n


def infer_tick(prices, dmax: int = DEC_MAX, finer_max: float = TICK_FINER_MAX):
    """(tick string, decimals, resolved) from decimal strings by tick_rule (coding choice 5). None without prices."""
    dec = price_decimals(prices, dmax)
    if dec.size == 0:
        return None
    r = tick_rule(_dec_counts(np.where(dec > DEC_MAX, -1, dec)), finer_max)
    d = min(r[0], dmax)
    return _tick_str(d), d, r[0] <= dmax


def _day_decimals(k: pd.DataFrame):
    """(sorted day ints, per-day counts of the OHLC prices by decimals (columns as _dec_counts)) over the bars with
    trades > 0."""
    if k is None or len(k) == 0:
        return None
    if "trades" in k:
        k = k[k["trades"].to_numpy() > 0]
    if len(k) == 0:
        return None
    day = _ns(k["open_time"]) // DAY_NS
    order = np.argsort(day, kind="stable")
    day = day[order]
    px = np.column_stack([k[c].to_numpy(float)[order] for c in ("open", "high", "low", "close")])
    dec = price_decimals(px).reshape(-1, 4)
    dec = np.where(dec < 0, DEC_MAX + 1, dec).astype(np.int64)
    uday, inv = np.unique(day, return_inverse=True)
    nb = DEC_MAX + 2
    cnt = np.bincount((inv[:, None] * nb + dec).ravel(), minlength=len(uday) * nb).reshape(len(uday), nb)
    return uday.astype(np.int64), cnt.astype(np.int32)


# ================================================================ bars: daily table, resampling, Wilder ATR
def _wilder_atr(h, l, c, new, n: int) -> np.ndarray:
    """Wilder ATR(n) per row, restarted where new is True (coding choice 3)."""
    h, l, c, new = h.tolist(), l.tolist(), c.tolist(), new.tolist()
    out = [math.nan] * len(c)
    run, acc, prev = 0, 0.0, math.nan
    for i in range(len(c)):
        if new[i]:
            run, acc = 0, 0.0
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
    return np.array(out)


class _Daily:
    """One series' daily bars: rows with trades > 0, one per day, sorted; effective segments (seg changes or day
    gaps; the §4.1 rule when no seg is given), log returns (NaN at a segment's first row) and ATR14."""

    def __init__(self, k: pd.DataFrame):
        k = k.sort_values("open_time", kind="stable")
        if "trades" in k:
            k = k[k["trades"].to_numpy() > 0]
        if "seg" in k:
            k = k[k["seg"].to_numpy() >= 0]
        day = _ns(k["open_time"]) // DAY_NS
        keep = np.r_[day[1:] != day[:-1], True] if len(day) else np.zeros(0, bool)
        k, day = k[keep], day[keep]
        self.day = day.astype(np.int64)
        self.open, self.high, self.low, self.close = (np.array(k[c].to_numpy(float), dtype=float, copy=True)
                                                      for c in ("open", "high", "low", "close"))   # own copies
        n = self.n = len(day)
        new = np.ones(n, bool)
        if n > 1:
            brk = np.diff(self.day) != 1
            if "seg" in k:
                sg = k["seg"].to_numpy()
                brk |= sg[1:] != sg[:-1]
            else:
                with np.errstate(divide="ignore", invalid="ignore"):
                    brk |= np.abs(self.open[1:] / self.close[:-1] - 1) > JUMP
            new[1:] = brk
        self.new = new
        self.sid = np.cumsum(new) - 1
        self.sstart = np.maximum.accumulate(np.where(new, np.arange(n), 0)) if n else np.zeros(0, np.int64)
        r = np.full(n, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            r[1:] = np.log(self.close[1:] / self.close[:-1])
        r[new] = np.nan
        self.ret = r
        self.atr = _wilder_atr(self.high, self.low, self.close, new, ATR_N) if n else np.zeros(0)

    def row(self, day_int: int) -> int:
        i = int(np.searchsorted(self.day, day_int))
        return i if i < self.n and self.day[i] == day_int else -1

    def sigma(self, i: int) -> tuple[float, int]:
        """(sigma30 at row i, number of valid returns) (coding choice 2)."""
        s = int(self.sstart[i])
        lo = max(i - SIGMA_DAYS + 1, s + 1)
        n = i - lo + 1
        if n < SIGMA_MIN:
            return math.nan, max(n, 0)
        return float(np.std(self.ret[lo:i + 1], ddof=1)), n


def _bars_from(k: pd.DataFrame, freq_ns: int) -> pd.DataFrame:
    """Bars of length freq_ns from finer bars, using only bars with trades > 0 (open first, close last)."""
    if "trades" in k:
        k = k[k["trades"].to_numpy() > 0]
    if len(k) == 0:
        return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "quote_volume", "trades"])
    t = _ns(k["open_time"])
    order = np.argsort(t, kind="stable")
    t = t[order]
    b = t // freq_ns
    ub, start = np.unique(b, return_index=True)
    end = np.r_[start[1:], len(b)] - 1
    col = {c: k[c].to_numpy(float)[order] for c in ("open", "high", "low", "close")}
    out = {"open_time": pd.to_datetime(ub * freq_ns, utc=True), "open": col["open"][start],
           "high": np.maximum.reduceat(col["high"], start), "low": np.minimum.reduceat(col["low"], start),
           "close": col["close"][end]}
    for c in ("volume", "quote_volume"):
        if c in k:
            out[c] = np.add.reduceat(k[c].to_numpy(float)[order], start)
    out["trades"] = (np.add.reduceat(k["trades"].to_numpy()[order], start) if "trades" in k
                     else np.ones(len(ub), np.int64))
    if "seg" in k:
        out["seg"] = k["seg"].to_numpy()[order][start]
    return pd.DataFrame(out)


# ================================================================ data sources (real or injected)
def _real_path(kind: str, coin: str):
    p = {"metrics": sbd.OUT / "metrics" / f"{coin}.parquet", "mark1h": sbd.OUT / "mark1h" / f"{coin}.parquet",
         "perp1h": sbd.OUT / "perp1h" / f"{coin}.parquet",
         "index_d1": sbd.OUT / "fut1d" / "index" / f"{coin}.parquet"}[kind]
    return p if p.exists() else None


def _load_real(coin: str, key: str):
    """A real frame of one coin, without downloading anything (missing -> None)."""
    if key == "d1":
        k = sbd.d1(coin)
        return k if len(k) else None
    if key == "h1":
        try:
            return sbd.h1(coin)
        except FileNotFoundError:
            return None
    if key in ("metrics", "mark1h", "perp1h", "index_d1"):
        if _real_path(key, coin) is None:
            return None
        return {"metrics": sbd.metrics, "mark1h": sbd.mark1h, "perp1h": sbd.perp1h, "index_d1": sbd.index1d}[key](coin)
    return None                                  # m1 / index_m1 are not loaded whole; ticks: _real_daydec


_DAYDEC: dict = {}


def _real_daydec(coin: str):
    """Per-day max decimals of a coin's cached 1m spot bars (the whole file once per coin); None if not cached."""
    if coin not in _DAYDEC:
        sym, lo, hi = sbd.coin_sym(coin)
        f = sbd.OUT / "m1_spot" / f"{sym}.parquet"
        res = None
        if f.exists():
            k = pd.read_parquet(f, columns=["open_time", "open", "high", "low", "close", "trades"])
            if lo or hi:
                d = _ns(k["open_time"]) // DAY_NS
                m = np.ones(len(k), bool)
                if lo:
                    m &= d >= _dint(lo)
                if hi:
                    m &= d <= _dint(hi)
                k = k[m]
            res = _day_decimals(k)
        _DAYDEC[coin] = res
    return _DAYDEC[coin]


def _buffers(fr) -> tuple | None:
    """Identity of a frame's column buffers (data address of numpy-backed columns, object id of the others). While a
    shallow copy of the frame is alive, pandas 3 copy-on-write gives every column changed in place a new buffer, so
    equal identities mean equal content (checked by the selftest for the usual in-place edits)."""
    if not isinstance(fr, pd.DataFrame):
        return None
    out = [fr.shape, tuple(fr.columns)]
    for j in range(fr.shape[1]):
        a = fr.iloc[:, j].array
        nd = getattr(a, "_ndarray", None)
        out.append(nd.__array_interface__["data"][0] if isinstance(nd, np.ndarray) else id(a))
    return tuple(out)


class _Src:
    """Frames of one coin (injected or real) and the tables derived from them, memoized per frame (_memo)."""

    def __init__(self, coin: str, data: dict | None):
        self.coin, self.data = coin, data
        self.real = data is None or bool(data.get("real", False))
        self.memo: dict = {}

    def raw(self, key: str):
        d = self.data
        if d is not None and d.get(key) is not None:
            return d[key]
        if not self.real:
            return None
        mk = ("raw", key)
        if mk not in self.memo:
            self.memo[mk] = _load_real(self.coin, key)
        return self.memo[mk]

    def injected(self, key: str) -> bool:
        return self.data is not None and self.data.get(key) is not None

    def _is_injected(self, o) -> bool:
        return self.data is not None and any(o is v for v in self.data.values())

    def _memo(self, name: str, objs: tuple, fn):
        """A derived table, rebuilt when a frame is replaced or changed in place. Injected frames are pinned by a
        shallow copy (pandas 3 copy-on-write then gives a frame changed in place new buffers for the changed columns)
        and compared by buffer identity (_buffers); the module's own real frames are private and not checked."""
        tok = tuple(_buffers(o) if self._is_injected(o) else None for o in objs)
        hit = self.memo.get(name)                    # one entry per table: a rebuild replaces it
        if hit is None or any(a is not b for a, b in zip(hit[0], objs)) or hit[1] != tok:
            pins = tuple(o.copy(deep=False) if t is not None else None for o, t in zip(objs, tok))
            hit = (objs, tok, pins, fn())            # keep the frames alive so their ids cannot be reused
            self.memo[name] = hit
        return hit[3]

    def daily(self, series: str = "spot"):
        dk, mk = ("d1", "m1") if series == "spot" else ("index_d1", "index_m1")
        k = self.raw(dk)
        if k is not None and len(k):
            return self._memo("daily:" + dk, (k,), lambda: _Daily(k))
        m = self.raw(mk) if self.injected(mk) else None
        if m is not None and len(m):
            return self._memo("daily:" + mk, (m,), lambda: _Daily(_bars_from(m, DAY_NS)))
        return None

    def daydec(self, series: str = "spot"):
        mk = "m1" if series == "spot" else "index_m1"
        if self.injected(mk):
            m = self.data[mk]
            return self._memo("daydec:" + mk, (m,), lambda: _day_decimals(m))
        if self.real and series == "spot":
            return _real_daydec(self.coin)
        return None

    def hourly(self):
        """(open ns, high, low, quote volume) of the hours with trades > 0 and quote volume > 0, sorted; or None."""
        h = self.raw("h1")
        if h is None:
            m = self.raw("m1") if self.injected("m1") else None
            if m is None or "quote_volume" not in m:
                return None
            h = self._memo("h1_m1", (m,), lambda: _bars_from(m, HOUR_NS))

        def build():
            if len(h) == 0 or "quote_volume" not in h:
                return None
            k = h[h["trades"].to_numpy() > 0] if "trades" in h else h
            t = _ns(k["open_time"])
            hi, lo, qv = (k[c].to_numpy(float) for c in ("high", "low", "quote_volume"))
            ok = (qv > 0) & (lo > 0) & (hi >= lo) & np.isfinite(hi) & np.isfinite(lo)
            o = np.argsort(t[ok], kind="stable")
            return t[ok][o], hi[ok][o], lo[ok][o], qv[ok][o]
        return self._memo("hourly", (h,), build)

    def fut(self):
        """M7's arrays (metrics time / open interest in coins without the missing rows (oi <= 0 or not finite; coding
        choice 15), mark open / low, perp open / VWAP), sorted; None if any frame is missing."""
        met, mk, pp = self.raw("metrics"), self.raw("mark1h"), self.raw("perp1h")
        if met is None or mk is None or pp is None or not len(met) or not len(mk) or not len(pp):
            return None
        if "oi" not in met:
            raise ValueError("M7 needs metrics['oi'], the open interest in coins of the underlying "
                             "(stinkbid_data.metrics); oi_usd differences are not new positions (coding choice 15)")

        def build():
            mt = _ns(met["create_time"])
            o = np.argsort(mt, kind="stable")
            oi = met["oi"].to_numpy(float)[o]
            ok = np.isfinite(oi) & (oi > 0)
            kt = _ns(mk["open_time"])
            ko = np.argsort(kt, kind="stable")
            pt = _ns(pp["open_time"])
            po = np.argsort(pt, kind="stable")
            vol, qv = pp["volume"].to_numpy(float)[po], pp["quote_volume"].to_numpy(float)[po]
            with np.errstate(divide="ignore", invalid="ignore"):
                vwap = np.where(vol > 0, qv / vol, np.nan)
            return dict(mt=mt[o][ok], oi=oi[ok], kt=kt[ko], klow=mk["low"].to_numpy(float)[ko], pt=pt[po], vwap=vwap)
        return self._memo("fut", (met, mk, pp), build)

    def m3(self):
        if self.injected("panel"):
            p, b = self.data["panel"], self.data.get("backstop")
            return self._memo("m3", (p, b), lambda: _M3Pool(_panel_prep_of(self, p), b))
        return _real_m3() if self.real else None

    def m8(self):
        if self.injected("panel"):
            p, u = self.data["panel"], self.data.get("univ")
            if u is None:
                return None
            return self._memo("m8", (p, u), lambda: _M8(_panel_prep_of(self, p), u))
        return _real_m8() if self.real else None


_SRC: OrderedDict = OrderedDict()


def _source(coin: str, data) -> _Src:
    if isinstance(data, _Src):
        return data
    if data is None:
        s = _SRC.get(coin)
        if s is None:
            s = _SRC[coin] = _Src(coin, None)
            while len(_SRC) > 4:
                _SRC.popitem(last=False)
        else:
            _SRC.move_to_end(coin)
        return s
    s = data.get("_src")
    if not isinstance(s, _Src) or s.coin != coin or s.data is not data:
        s = _Src(coin, data)
        data["_src"] = s
    return s


# ================================================================ the all-pairs panel (M3, M8)
class _Panel:
    """Every pair's daily bars: traded rows sorted by coin and day, effective segments, log returns, sigma30."""

    def __init__(self, panel: pd.DataFrame):
        a = panel
        if "trades" in a:
            a = a[a["trades"].to_numpy() > 0]
        if "seg" in a:
            a = a[a["seg"].to_numpy() >= 0]
        day = _ns(a["day"] if "day" in a else a["open_time"]) // DAY_NS
        code, coins = pd.factorize(a["coin"].to_numpy())
        order = np.lexsort((day, code))
        self.coins = np.asarray(coins)
        self.code, self.day = code[order].astype(np.int64), day[order].astype(np.int64)
        self.open, self.high, self.low, self.close = (a[c].to_numpy(float)[order] for c in ("open", "high", "low",
                                                                                        "close"))   # copies (take)
        self.excluded = (a["excluded"].fillna("").astype(str).to_numpy()[order] != "") if "excluded" in a \
            else np.zeros(len(order), bool)
        n = len(order)
        new = np.ones(n, bool)
        if n > 1:
            brk = (self.code[1:] != self.code[:-1]) | (np.diff(self.day) != 1)
            if "seg" in a:
                sg = a["seg"].to_numpy()[order]
                brk |= sg[1:] != sg[:-1]
            else:
                with np.errstate(divide="ignore", invalid="ignore"):
                    brk |= np.abs(self.open[1:] / self.close[:-1] - 1) > JUMP
            new[1:] = brk
        self.new = new
        self.gid = np.cumsum(new) - 1
        r = np.full(n, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            r[1:] = np.log(self.close[1:] / self.close[:-1])
        r[new] = np.nan
        self.ret = r
        sig = np.array(pd.Series(r).groupby(self.gid).rolling(SIGMA_DAYS, min_periods=SIGMA_MIN).std(ddof=1)
                       .reset_index(level=0, drop=True).sort_index().to_numpy(), dtype=float)
        sig[~(sig > 0)] = np.nan
        self.sigma = sig
        self.n = n


def _panel_prep_of(src: _Src, p: pd.DataFrame) -> _Panel:
    return src._memo("panel", (p,), lambda: _Panel(p))


def _month_str(day: np.ndarray) -> np.ndarray:
    return pd.to_datetime(day * DAY_NS).strftime("%Y-%m").to_numpy()


class _M3Pool:
    """M3's pooled windows (coding choice 9): one row per eligible pair-Monday with z = ln(min low over the life /
    P_t) / sigma_t, sorted by the life's last day."""

    def __init__(self, P: _Panel, backstop: pd.DataFrame | None = None):
        n = P.n
        sunday = (P.day + 3) % 7 == 6                            # 1970-01-01 was a Thursday
        cand = sunday & ~P.excluded & np.isfinite(P.sigma)
        ml = np.full(n, np.nan)
        for j in range(1, M3_LIFE + 1):
            nxt = np.full(n, np.nan)
            same = np.zeros(n, bool)
            same[:n - j] = (P.gid[j:] == P.gid[:n - j]) & (P.day[j:] - P.day[:n - j] == j)
            nxt[:n - j] = P.low[j:]
            ml = np.where(same, np.fmin(ml, nxt), ml)
        ok = cand & np.isfinite(ml) & (ml > 0)
        idx = np.flatnonzero(ok)
        if backstop is not None and len(backstop) and len(idx):
            b = backstop[backstop["excluded"].astype(bool)]
            bad = set(zip(b["month"].astype(str), b["coin"].astype(str)))
            mon = _month_str(P.day[idx] + 1)
            drop = np.array([(m, c) in bad for m, c in zip(mon, P.coins[P.code[idx]])], bool)
            idx = idx[~drop]
        z = np.log(ml[idx] / P.close[idx]) / P.sigma[idx]
        end = P.day[idx] + M3_LIFE
        o = np.argsort(end, kind="stable")
        self.end, self.z = end[o], z[o]
        self.coin = P.coins[P.code[idx]][o]
        self.d0 = P.day[idx][o]
        self.gid = P.gid[idx][o]
        self._q: dict = {}

    def quantile(self, d0_int: int, p: float) -> float:
        n = int(np.searchsorted(self.end, d0_int, side="right"))
        key = (n, float(p))
        if key not in self._q:
            self._q[key] = float(np.quantile(self.z[:n], p)) if n else math.nan
        return self._q[key]

    def own(self, coin: str, first_day: int, d0_int: int) -> np.ndarray:
        m = (self.coin == coin) & (self.d0 >= first_day) & (self.end <= d0_int)
        return self.z[m]


class _M8:
    """M8's tables (coding choice 16): market-wide days and the U-Q1 pool of standardized lows on them."""

    def __init__(self, P: _Panel, univ: pd.DataFrame):
        n = P.n
        prev = np.zeros(n, bool)
        prev[1:] = ~P.new[1:]
        pc = np.full(n, np.nan)
        ps = np.full(n, np.nan)
        pc[1:] = P.close[:-1]
        ps[1:] = P.sigma[:-1]
        pc[~prev] = np.nan
        ps[~prev] = np.nan
        with np.errstate(divide="ignore", invalid="ignore"):
            x = P.low / pc
            z = np.log(P.low / pc) / ps
        hit = prev & (x <= 1 - M8_DROP)
        mon = _month_str(P.day)
        u = univ.copy()
        u["month"] = u["month"].astype(str)
        ub = set(zip(u.loc[u["U_B"].astype(bool), "month"], u.loc[u["U_B"].astype(bool), "coin"].astype(str)))
        uq = set(zip(u.loc[u["U_Q1"].astype(bool), "month"], u.loc[u["U_Q1"].astype(bool), "coin"].astype(str)))
        coin = P.coins[P.code]
        key = list(zip(mon, coin))
        in_b = np.fromiter((k in ub for k in key), bool, n)
        in_q = np.fromiter((k in uq for k in key), bool, n)
        nub = u[u["U_B"].astype(bool)].groupby("month").size()
        hd = pd.Series(P.day[in_b & hit]).value_counts()
        days = hd.index.to_numpy(np.int64)
        den = nub.reindex(_month_str(days)).to_numpy(float)
        share = hd.to_numpy(float) / den
        self.mw = np.sort(days[np.isfinite(share) & (share >= M8_SHARE)])
        self.share = dict(zip(days.tolist(), share.tolist()))
        m = in_q & np.isin(P.day, self.mw) & np.isfinite(z)
        o = np.argsort(P.day[m], kind="stable")
        self.pool_day, self.pool_z = P.day[m][o], z[m][o]
        self._med: dict = {}

    def pooled_median(self, d0_int: int) -> float:
        n = int(np.searchsorted(self.pool_day, d0_int, side="right"))
        if n not in self._med:
            self._med[n] = float(np.median(self.pool_z[:n])) if n else math.nan
        return self._med[n]


_REAL: dict = {}


def _real_panel() -> _Panel:
    if "panel" not in _REAL:
        _REAL["panel"] = _Panel(sbd.d1_panel())
    return _REAL["panel"]


def _real_m3() -> _M3Pool:
    if "m3" not in _REAL:
        _REAL["m3"] = _M3Pool(_real_panel(), sbd.backstop())
    return _REAL["m3"]


def _real_univ() -> pd.DataFrame:
    """U-B for every ranked month (rank <= 100, from 2017-10) and U-Q1 (universes rebuilt from 2018-08)."""
    rk = sbd.ranks()
    ub = rk[rk["rank"] <= sbd.TOP_N][["month", "coin"]].assign(U_B=True)
    uq = sbd.universes(first="2018-08")
    uq = uq[uq["U_Q1"]][["month", "coin"]].assign(U_Q1=True)
    u = ub.merge(uq, on=["month", "coin"], how="outer")
    u["U_B"] = u["U_B"].fillna(False).astype(bool)
    u["U_Q1"] = u["U_Q1"].fillna(False).astype(bool)
    return u


def _real_m8() -> _M8:
    if "m8" not in _REAL:
        _REAL["m8"] = _M8(_real_panel(), _real_univ())
    return _REAL["m8"]


def m3_pool(data: dict | None = None):
    """M3's pooled windows: DataFrame(coin, d0, end, z) (real data when data is None; else data['panel'])."""
    p = _real_m3() if data is None else _M3Pool(_Panel(data["panel"]), data.get("backstop"))
    return pd.DataFrame({"coin": p.coin, "d0": [_day_ts(d) for d in p.d0], "end": [_day_ts(d) for d in p.end],
                         "z": p.z})


def m8_tables(data: dict | None = None):
    """M8's market-wide days (with their U-B share) and the U-Q1 pool: (DataFrame(day, share), DataFrame(day, z))."""
    m = _real_m8() if data is None else _M8(_Panel(data["panel"]), data["univ"])
    days = pd.DataFrame({"day": [_day_ts(d) for d in m.mw], "share": [m.share[int(d)] for d in m.mw]})
    pool = pd.DataFrame({"day": [_day_ts(d) for d in m.pool_day], "z": m.pool_z})
    return days, pool


# ================================================================ inputs at placement (§6.1)
def inputs_at(coin: str, t0, data: dict | None = None, series: str = "spot", price=None, tick=None) -> dict:
    """Inputs of one coin at placement t0 (§6.1, V6): spot through d0, futures through d0 - 1 (see the module
    docstring for the keys). Never reads a bar after the information cutoff."""
    if series not in ("spot", "index"):
        raise ValueError("series must be 'spot' or 'index'")
    src = _source(coin, data)
    t, d0 = day0(t0)
    d_last = d0 if series == "spot" else d0 - DAY
    out = dict(coin=coin, series=series, t0=t, d0=d0, d_last=d_last, d_fut=d0 - DAY, P0=math.nan, close=math.nan,
               sigma30=math.nan, sigma=math.nan, n_ret=0, atr=math.nan, atr_pct=math.nan, tick=math.nan,
               tick_str=None, tick_dec=None, tick_source=None, tick_resolved=None, tick_raw_str=None,
               tick_n_finer=None, tick_n_prices=None, seg=None, seg_first_day=None, seg_days=0, traded=False,
               seg_ok=False, ok=False, why="", _src=src, _row=-1, _T=None)
    T = src.daily(series)
    if T is None or T.n == 0:
        out["why"] = f"no {series} daily bars"
        return out
    i = T.row(_dint(d_last))
    if i < 0:
        out["why"] = f"no traded {series} bar on {d_last.date()}"
        return out
    s = int(T.sstart[i])
    sig, nret = T.sigma(i)
    close = float(T.close[i])
    P0 = float(price) if price is not None else close
    atr = float(T.atr[i])
    out.update(_row=i, _T=T, close=close, P0=P0, sigma30=sig, sigma=sig, n_ret=nret, atr=atr,
               atr_pct=atr / P0 if P0 > 0 else math.nan, seg=int(T.sid[i]), seg_first_day=_day_ts(T.day[s]),
               seg_days=i - s + 1, traded=True, seg_ok=bool(math.isfinite(sig) and sig > 0))
    # the tick (§6.1, V15; coding choice 5)
    if tick is not None or (src.data is not None and src.data.get("tick") is not None):
        tk = _dec(tick if tick is not None else src.data["tick"])
        out.update(tick_str=str(tk), tick=float(tk), tick_dec=max(0, -tk.as_tuple().exponent), tick_source="given",
                   tick_resolved=True, tick_raw_str=str(tk))
    else:
        lo_d, hi_d = _dint(d_last) - TICK_DAYS + 1, _dint(d_last)
        dd = src.daydec(series)
        cnt, srcname = None, None
        if dd is not None:
            a, b = np.searchsorted(dd[0], lo_d), np.searchsorted(dd[0], hi_d, side="right")
            if b > a:
                cnt, srcname = dd[1][a:b].sum(axis=0), ("1m" if series == "spot" else "index-1m")
        if cnt is None:
            a, b = np.searchsorted(T.day, lo_d), np.searchsorted(T.day, hi_d, side="right")
            px = np.concatenate([T.open[a:b], T.high[a:b], T.low[a:b], T.close[a:b]])
            if px.size:
                cnt, srcname = _dec_counts(price_decimals(px)), ("1d" if series == "spot" else "index-1d")
        if cnt is not None:
            d, d_raw, n_finer, n_px = tick_rule(cnt)
            dd_ = min(d, DEC_MAX)
            out.update(tick_str=_tick_str(dd_), tick=float(_dec(_tick_str(dd_))), tick_dec=dd_,
                       tick_source=srcname + ("-majority" if d < d_raw else ""), tick_resolved=d <= DEC_MAX,
                       tick_raw_str=_tick_str(min(d_raw, DEC_MAX)), tick_n_finer=n_finer, tick_n_prices=n_px)
    why = []
    if not out["seg_ok"]:
        why.append(f"sigma30 needs >= {SIGMA_MIN} returns in one segment (has {nret})" if nret < SIGMA_MIN
                   else "sigma30 is 0")
    if not (math.isfinite(atr) and atr > 0):
        why.append("no ATR14")
    if out["tick_str"] is None:
        why.append("no tick")
    if not P0 > 0:
        why.append("P0 <= 0")
    out["ok"] = not why
    out["why"] = "; ".join(why)
    return out


# ================================================================ M5 grid, M6 / M7 profiles
def m5_round(P0: float, sigma: float):
    """(R as an exact Decimal, L*, e, 'G' or 'g') of draft §6.2's M5 (coding choice 13)."""
    e = math.floor(math.log10(P0))
    while 10.0 ** (e + 1) <= P0:
        e += 1
    while 10.0 ** e > P0:
        e -= 1
    g = Decimal(10) ** (e - 1)
    G = 5 * g
    gf, Gf = float(g), float(G)
    Ls = P0 * math.exp(-M5_DEPTH * sigma)
    lo, hi = Ls * math.exp(-M5_BAND * sigma), Ls * math.exp(M5_BAND * sigma)
    cands = [m for m in range(max(1, math.floor(lo / Gf)), math.ceil(hi / Gf) + 1)
             if abs(math.log(m * Gf / Ls)) <= M5_BAND * sigma]
    if cands:
        m = min(cands, key=lambda m: (abs(m * Gf - Ls), m))
        return m * G, Ls, e, "G"
    mf = math.floor(Ls / gf)
    m = mf if (Ls - mf * gf) <= ((mf + 1) * gf - Ls) else mf + 1
    return max(1, m) * g, Ls, e, "g"


def volume_profile(lo, hi, qv, P0: float, sigma: float):
    """M6's raw profile: (b_min, mass per bin b = b_min..). Bin b holds depths [b, b+1) x 0.25 sigma below P0; each
    hour's quote volume is spread uniformly in log price over [low, high] (coding choice 14)."""
    w = BIN * sigma
    lnp = math.log(P0)
    u1 = (lnp - np.log(np.asarray(hi, float))) / w                 # the hour's top (shallowest depth)
    u2 = (lnp - np.log(np.asarray(lo, float))) / w                 # the hour's bottom
    qv = np.asarray(qv, float)
    i1, i2 = np.floor(u1).astype(np.int64), np.floor(u2).astype(np.int64)
    bmin, bmax = int(i1.min()), int(i2.max())
    nb = bmax - bmin + 1
    mass = np.zeros(nb + 1)
    one = i1 == i2
    np.add.at(mass, i1[one] - bmin, qv[one])
    sp = ~one
    if sp.any():
        rho = qv[sp] / (u2[sp] - u1[sp])
        a, b = i1[sp] - bmin, i2[sp] - bmin
        np.add.at(mass, a, rho * (i1[sp] + 1 - u1[sp]))
        np.add.at(mass, b, rho * (u2[sp] - i2[sp]))
        diff = np.zeros(nb + 1)
        np.add.at(diff, a + 1, rho)
        np.add.at(diff, b, -rho)
        mass += np.cumsum(diff)
        mass[np.abs(mass) <= 1e-12 * qv.sum()] = 0.0      # rounding residue of the running sum in uncovered bins
    return bmin, mass[:nb]


def liquidation_histogram(liq, weight, P0: float, sigma: float):
    """M7's raw histogram of liquidation prices on M6's grid: (b_min, mass per bin)."""
    u = (math.log(P0) - np.log(np.asarray(liq, float))) / (BIN * sigma)
    b = np.floor(u).astype(np.int64)
    bmin = int(b.min())
    return bmin, np.bincount(b - bmin, weights=np.asarray(weight, float))


def _peaks(s: np.ndarray, rtol: float = 1e-12):
    """Strict local maxima of s (zero outside it); a run of equal values is one node: (first, last, value)."""
    n = len(s)
    if n == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0)
    brk = ~np.isclose(s[1:], s[:-1], rtol=rtol, atol=0.0)
    start = np.r_[0, np.flatnonzero(brk) + 1]
    end = np.r_[start[1:] - 1, n - 1]
    val = s[start]
    left = np.r_[0.0, val[:-1]]
    right = np.r_[val[1:], 0.0]
    pk = (val > left) & (val > right) & (val > 0)
    return start[pk], end[pk], val[pk]


def _node_pick(mass: np.ndarray, bmin: int, thresh_mult: float, nonzero_median: bool):
    """Smooth (full convolution), find nodes, keep those >= mult x median, and return the largest node whose lower
    edge lies in the band: (edge depth in sigma, node value, number of nodes, number in the band) or None."""
    s = np.convolve(mass, KERNEL)
    off = bmin - 2
    first, last, val = _peaks(s)
    base = s[s > 0] if nonzero_median else s
    med = float(np.median(base)) if base.size else 0.0
    keep = val >= thresh_mult * med
    edge = (off + last + 1) * BIN                                   # delta of the deeper edge of the node's deepest bin
    inb = keep & (edge >= BAND[0]) & (edge <= BAND[1])
    if not inb.any():
        return None, int(keep.sum()), 0, med
    j = np.flatnonzero(inb)
    best = j[np.lexsort((edge[j], -val[j]))[0]]
    return float(edge[best]), int(keep.sum()), int(inb.sum()), med, float(val[best])


# ================================================================ the level methods (§6.2)
def _check_params(method: str, params: dict) -> dict:
    if method not in _PARAMS:
        raise ValueError(f"unknown method {method!r}; one of {sorted(_PARAMS)}")
    extra = set(params) - set(_PARAMS[method])
    if extra:
        raise ValueError(f"{method}: unknown parameter(s) {sorted(extra)}; takes {_PARAMS[method]}")
    p = dict(_DEFAULTS.get(method, {}))
    p.update(params)
    missing = [k for k in _PARAMS[method] if k not in p]
    if missing:
        raise ValueError(f"{method}: missing parameter(s) {missing}")
    return p


def level_info(method: str, inputs: dict, **params) -> dict:
    """One level with its status and the intermediate values (aux) used to build it."""
    p = _check_params(method, params)
    res = dict(method=method, params=p, L=None, delta=None, n_ticks=None, x=None, status="ok", detail="", aux={})
    I = inputs
    if not I.get("ok"):
        res.update(status="invalid_inputs", detail=I.get("why", ""))
        return res
    src, i = I["_src"], I["_row"]
    T = I["_T"]                                       # the daily table these inputs were computed from (a snapshot)
    P0, sig, atr, apct = I["P0"], I["sigma30"], I["atr"], I["atr_pct"]
    tick = _dec(I["tick_str"])
    d0i, dli = _dint(I["d0"]), _dint(I["d_last"])
    s = int(T.sstart[i])
    aux = res["aux"]
    x, n = None, None

    def fail(status, detail):
        res.update(status=status, detail=detail)
        return res

    if method == "M1":
        x = P0 * (1 - p["d"])
    elif method == "M2":
        x = P0 * math.exp(-p["k"] * sig)
    elif method == "M2a":
        x = P0 - p["kA"] * atr
    elif method in ("M3", "M3c"):
        pool = src.m3()
        if pool is None:
            return fail("no_data", "no M3 pool (no panel)")
        if method == "M3":
            q = pool.quantile(d0i, p["p"])
            aux["n_windows"] = int(np.searchsorted(pool.end, d0i, side="right"))
        else:
            z = pool.own(src.coin, int(T.day[s]), d0i)
            aux["n_windows"] = int(z.size)
            if z.size < M3C_MIN:
                return fail("no_data", f"M3c needs >= {M3C_MIN} own windows in the segment (has {z.size})")
            q = float(np.quantile(z, p["p"]))
        if not math.isfinite(q):
            return fail("no_data", "empty M3 pool")
        aux["q"] = q
        x = P0 * math.exp(q * sig)
    elif method in ("M4", "M4f"):
        N = int(p["N"])
        lo = max(s, i - N + 1)
        Lo = float(np.min(T.low[lo:i + 1]))
        aux.update(Lo=Lo, days=i - lo + 1)
        x = Lo * (1 - p["buffer"] * apct) if method == "M4" else Lo * (1 + M4F_BUF * apct)
    elif method == "M4s":
        lows = T.low[s:i + 1]
        m = len(lows)
        w = 2 * PIVOT_SIDE + 1
        if m < w:
            return fail("abstain", "no confirmed pivot low (segment too short)")
        wmin = np.lib.stride_tricks.sliding_window_view(lows, w).min(axis=1)    # window j-5..j+5 for j = 5..m-6
        js = np.arange(PIVOT_SIDE, m - PIVOT_SIDE)
        piv = js[lows[js] <= wmin]
        with np.errstate(divide="ignore"):
            dp = np.log(P0 / lows[piv]) / sig
        ok = piv[(dp >= BAND[0]) & (dp <= BAND[1])]
        aux["n_pivots"] = int(piv.size)
        if ok.size == 0:
            return fail("abstain", "no confirmed pivot low with delta in [4, 14]")
        j = int(ok.max())
        aux.update(pivot=float(lows[j]), pivot_day=_day_ts(T.day[s + j]))
        x = float(lows[j]) * (1 - M4S_BUF * apct)
    elif method in ("M5f", "M5a", "M5b"):
        R, Ls, e, kind = m5_round(P0, sig)
        aux.update(R=float(R), R_str=str(R), L_star=Ls, e=e, grid=kind)
        if method == "M5a":
            x = R
        elif method == "M5f":
            n0 = floor_n(R, tick)
            n = None if n0 is None else n0 + 1
            x = R
        else:
            x = float(R) * (1 - M5B_BUF * apct)
    elif method == "M6":
        if I["series"] != "spot":
            return fail("no_data", "M6 needs volume; the index has none (coding choice 19)")
        hr = src.hourly()
        if hr is None:
            return fail("no_data", "no hourly bars with volume")
        t, hi, lo, qv = hr
        a = np.searchsorted(t, max(_dint(I["d_last"]) - M6_DAYS + 1, int(T.day[s])) * DAY_NS)
        b = np.searchsorted(t, (dli + 1) * DAY_NS)
        aux["hours"] = int(b - a)
        if b <= a:
            return fail("no_data", "no hourly bars with volume in the 90-day window")
        bmin, mass = volume_profile(lo[a:b], hi[a:b], qv[a:b], P0, sig)
        pick = _node_pick(mass, bmin, HVN_MULT, True)
        aux.update(n_hvn=pick[1], n_hvn_band=pick[2], median=pick[3])
        if pick[0] is None:
            return fail("abstain", "no HVN with delta in [4, 14]")
        aux.update(edge_delta=pick[0], node_value=pick[4])
        x = P0 * math.exp(-pick[0] * sig)
    elif method == "M7":
        if I["t0"] < M7_FROM:
            return fail("before_start", "M7 starts 2021-12")
        f = src.fut()
        if f is None:
            return fail("no_data", "no open interest / mark / perpetual bars")
        cut = d0i * DAY_NS                                           # futures through d0 - 1
        w0 = max((d0i - M7_DAYS) * DAY_NS, int(T.day[s]) * DAY_NS)
        a, b = np.searchsorted(f["mt"], w0), np.searchsorted(f["mt"], cut)
        mt, oi = f["mt"][a:b], f["oi"][a:b]                          # oi: contracts in coins; zero rows dropped
        aux["rows"] = int(b - a)
        if mt.size < 2:
            return fail("no_data", "fewer than 2 open-interest rows in the 30-day window")
        d = oi[1:] - oi[:-1]                                         # contracts opened (net) in the 5 minutes
        good = (np.diff(mt) == MIN5_NS) & (d > 0)
        tj, dj = mt[1:][good], d[good]
        hour = ((tj - 1) // HOUR_NS) * HOUR_NS
        k = np.searchsorted(f["pt"], hour)
        kk = np.minimum(k, len(f["pt"]) - 1)
        has = (k < len(f["pt"])) & (f["pt"][kk] == hour)
        vw = np.where(has, f["vwap"][kk], np.nan)
        use = np.isfinite(vw) & (vw > 0)
        tj, dj, vw = tj[use], dj[use] * vw[use], vw[use]             # dOI+ in USD: new contracts x entry VWAP
        aux.update(entries=int(tj.size), new_oi_usd=float(dj.sum()))
        if tj.size == 0:
            return fail("no_data", "no new open interest with a perpetual VWAP in the window")
        lev = np.array(M7_LEV)
        liq = vw[:, None] * (1 - 1 / lev[None, :] + M7_MAINT)
        wt = dj[:, None] * M7_LONG * np.array(M7_LEV_W)[None, :]
        kn = int(np.searchsorted(f["kt"], cut))                       # mark bars published before t0
        smin = np.minimum.accumulate(f["klow"][:kn][::-1])[::-1] if kn else np.zeros(0)
        smin = np.r_[smin, np.inf]
        j0 = np.searchsorted(f["kt"][:kn], tj)                      # first mark bar opening at or after the row
        alive = smin[j0][:, None] > liq                              # removed once a later mark low <= liq
        aux["positions_alive"] = int(alive.sum())
        if not alive.any():
            return fail("abstain", "every estimated position was liquidated by a later mark-price low")
        bmin, mass = liquidation_histogram(liq[alive], wt[alive], P0, sig)
        pick = _node_pick(mass, bmin, M7_PEAK, False)
        aux.update(n_peaks=pick[1], n_peaks_band=pick[2], median=pick[3])
        if pick[0] is None:
            return fail("abstain", "no liquidation peak with delta in [4, 14]")
        aux.update(edge_delta=pick[0], node_value=pick[4])
        x = P0 * math.exp(-pick[0] * sig) * (1 - M7_BUF * apct)
    elif method == "M8":
        m8 = src.m8()
        if m8 is None:
            return fail("no_data", "no M8 tables (no panel / universes)")
        rows = np.arange(s + 1, i + 1)
        rows = rows[np.isin(T.day[rows], m8.mw) & (T.day[rows] <= d0i)]
        z = []
        for r in rows:
            sp, _ = T.sigma(int(r) - 1)
            if math.isfinite(sp) and sp > 0:
                z.append(math.log(T.low[r] / T.close[r - 1]) / sp)
        aux["n_own"] = len(z)
        if len(z) >= M8_MIN:
            q, aux["source"] = float(np.median(z)), "own"
        else:
            q, aux["source"] = m8.pooled_median(d0i), "pooled U-Q1"
        if not math.isfinite(q):
            return fail("no_data", "no market-wide day before d0")
        aux["q"] = q
        x = P0 * math.exp(q * sig)
    res["x"] = float(x) if x is not None else None
    if n is None:
        n = floor_n(x, tick)
    chart = method in CHART                    # a chart level outside (0, P0) has delta outside [4, 14]: it abstains
    if n is None or n <= 0:
        return fail("abstain" if chart else "non_positive", "level <= 0 after rounding")
    L = tick_value(n, tick)
    res.update(n_ticks=n)
    if not L < P0:
        return fail("abstain" if chart else "not_below_P0", f"level {L} >= P0 {P0}")
    delta = math.log(P0 / L) / sig
    if chart and not (BAND[0] <= delta <= BAND[1]):
        res["aux"]["delta_rounded"] = delta
        return fail("abstain", f"delta {delta:.3f} outside [4, 14]")
    res.update(L=L, delta=delta)
    return res


def level(method: str, inputs: dict, **params):
    """(L, delta) of one method at one placement, or None (abstention, no data, invalid inputs)."""
    r = level_info(method, inputs, **params)
    return (r["L"], r["delta"]) if r["status"] == "ok" else None


def variant_label(method: str, params: dict) -> str:
    return method + "".join(f" {k}={v:g}" for k, v in params.items())


def levels_all(inputs: dict, variants=VARIANTS) -> pd.DataFrame:
    """Every variant at one placement: variant, method, params, L, delta, n_ticks, status, detail."""
    rows = []
    for m, p in variants:
        r = level_info(m, inputs, **p)
        rows.append(dict(variant=variant_label(m, p), method=m, params=dict(p), L=r["L"], delta=r["delta"],
                         n_ticks=r["n_ticks"], x=r["x"], status=r["status"], detail=r["detail"]))
    return pd.DataFrame(rows)


# ================================================================ placebos (draft §6.3) and Robinhood (§13)
def _need(name: str, **vals):
    """Raise ValueError unless every value is given: numbers finite, and P0 and sigma positive."""
    bad = [k for k, v in vals.items() if v is None or (isinstance(v, (int, float)) and not math.isfinite(v))
           or (k in ("P0", "sigma") and not v > 0)]
    if bad:
        raise ValueError(f"{name}: missing or invalid {bad}; call it with inputs=I (from inputs_at, ok) or pass them")


def placebos(L, atr_pct=None, tick=None, P0=None, sigma=None, inputs: dict | None = None):
    """H4's four placebos of a real level L: [(shift, L_p, delta_p)] for shift in (-1.0, -0.5, +0.5, +1.0), L_p =
    floor(L exp(shift ATR%))_tau (None if it is not a bid below P0), delta_p = ln(P0 / L_p) / sigma. inputs (from
    inputs_at) supplies atr_pct, tick, P0 and sigma when they are not given. Without a tick, P0 or sigma it raises
    ValueError: a placebo is run exactly like L_M, on the venue's tick (K7) and with its depth (H4's depth term)."""
    if inputs is not None:
        atr_pct = inputs["atr_pct"] if atr_pct is None else atr_pct
        tick = inputs["tick_str"] if tick is None else tick
        P0 = inputs["P0"] if P0 is None else P0
        sigma = inputs["sigma30"] if sigma is None else sigma
    _need("placebos", atr_pct=atr_pct, tick=tick, P0=P0, sigma=sigma)
    out = []
    for m in PLACEBO_SHIFTS:
        Lp = floor_tick(float(L) * math.exp(m * atr_pct), tick)
        if Lp is None or not Lp > 0 or not Lp < P0:
            out.append((m, None, None))
            continue
        out.append((m, Lp, math.log(P0 / Lp) / sigma))
    return out


def _catalog(catalog=None):
    if catalog is None:
        if "rh" not in _REAL:
            _REAL["rh"] = sbd.rh_pairs()
        return _REAL["rh"]
    return catalog


def rh_tick(coin: str, catalog=None) -> str:
    """Robinhood's price increment (decimal string) from the saved 2026-11-18 catalog (or an injected one: a
    DataFrame with coin and price_tick_str, or a dict coin -> tick string)."""
    if coin in sbd.RH_REUSED:
        raise KeyError(f"{coin}: {sbd.RH_REUSED[coin]}")
    cat = _catalog(catalog)
    if isinstance(cat, dict):
        if coin not in cat:
            raise KeyError(f"{coin} is not in the Robinhood catalog")
        return str(cat[coin])
    row = cat[cat["coin"] == coin]
    if row.empty:
        raise KeyError(f"{coin} is not in the saved Robinhood catalog")
    return str(row["price_tick_str"].iloc[0])


def rh_round(coin: str, L, P0=None, sigma=None, inputs: dict | None = None, catalog=None):
    """(L on Robinhood's tick (floored), delta recomputed) (§13 item 1, V15). None if the rounded level is not
    positive. Without P0 and sigma (inputs=I, or P0= and sigma=) it raises ValueError: delta is part of the result;
    floor_tick(L, rh_tick(coin)) is the bare floor."""
    if inputs is not None:
        P0 = inputs["P0"] if P0 is None else P0
        sigma = inputs["sigma30"] if sigma is None else sigma
    _need("rh_round", P0=P0, sigma=sigma)
    Lr = floor_tick(L, rh_tick(coin, catalog))
    if Lr is None:
        return None
    return Lr, math.log(P0 / Lr) / sigma


# ================================================================ CLI: show, coverage (counts only)
def show_t0(day) -> pd.Timestamp:
    """The placement show() uses (coding choice 20): a date (midnight) -> Monday 03:30 UTC of its week (Monday..
    Sunday); a timestamp with a time -> itself."""
    t = pd.Timestamp(day)
    if t == t.normalize():
        t = t.normalize() - pd.Timedelta(days=t.dayofweek) + pd.Timedelta(hours=3, minutes=30)
    return t


def show(coin: str, day, series: str = "spot"):
    """Print the inputs and every level variant of one placement (Monday 03:30 UTC of `day`'s week if `day` is a
    date; show_t0). Levels at placement only; nothing after it is read."""
    I = inputs_at(coin, show_t0(day), series=series)
    print({k: v for k, v in I.items() if not k.startswith("_")})
    if I["ok"]:
        df = levels_all(I)
        with pd.option_context("display.width", 200, "display.max_rows", 200):
            print(df[["variant", "L", "delta", "n_ticks", "status", "detail"]].to_string(index=False))
            for m, p in H4_VARIANTS:
                r = level(m, I, **p)
                if r is not None:
                    print(variant_label(m, p), "placebos:", placebos(r[0], inputs=I))


def coverage(first: str = "2020-01", last: str = "2026-11", universe: str = "U_Q1", every: int = 1):
    """Counts of levels given / abstentions per variant over the weekly placements of a universe (no outcome)."""
    t0 = time.time()
    u = sbd.universes()
    u = u[u[universe] & (u["month"] >= first) & (u["month"] <= last)]
    mondays = pd.date_range("2020-01-06", "2026-11-09", freq="7D")[::every]
    by_month = {m: sorted(g["coin"]) for m, g in u.groupby("month")}
    jobs: dict = {}
    for d in mondays:
        for c in by_month.get(d.strftime("%Y-%m"), []):
            jobs.setdefault(c, []).append(d + pd.Timedelta(hours=3, minutes=30))
    counts: dict = {}
    n_in, n_ok = 0, 0
    for c, ts in sorted(jobs.items()):
        for t in ts:
            n_in += 1
            I = inputs_at(c, t)
            if not I["ok"]:
                counts.setdefault(("inputs", "invalid: " + I["why"][:40]), 0)
                counts[("inputs", "invalid: " + I["why"][:40])] += 1
                continue
            n_ok += 1
            kt = ("inputs", "tick " + str(I["tick_source"]))
            counts[kt] = counts.get(kt, 0) + 1
            for m, p in VARIANTS:
                r = level_info(m, I, **p)
                k = (variant_label(m, p), r["status"])
                counts[k] = counts.get(k, 0) + 1
    rows = pd.Series(counts).rename_axis(["variant", "status"]).unstack(fill_value=0)
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(rows.to_string())
    print(f"coverage: {universe} {first}..{last}, {n_in} coin-weeks ({n_ok} with valid inputs), {len(jobs)} coins, "
          f"{time.time() - t0:.0f}s", flush=True)
    return rows


# ================================================================ selftest (synthetic known answers; look-ahead)
def _say(t0, msg):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def _ofloor(x, tick: str) -> float:
    """Oracle: floor of the shortest decimal string of x to the tick (separate code from floor_n)."""
    t = Decimal(tick)
    q = (Decimal(repr(float(x))) / t).to_integral_value(rounding=ROUND_FLOOR)
    return float(q * t)


def _near(a, b, tol=1e-12) -> bool:
    return a == b or abs(a - b) <= tol * max(abs(a), abs(b))


def _alt_bars(start, n, base, a, lows=None, highs=None, trades=None):
    """Daily bars from `start`: closes alternate base (even rows) and base e^a (odd rows), so the log returns
    alternate +a, -a and sigma30 over 30 returns is a sqrt(30/29); opens are the previous close; the first bar's high
    is base e^a, so every true range is base (e^a - 1) and ATR14 equals it. lows / highs: {row: price}."""
    c = base * np.exp(a * (np.arange(n) % 2))
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c), np.minimum(o, c)
    h[0] = base * math.exp(a)
    for r, v in (lows or {}).items():
        l[r] = v
    for r, v in (highs or {}).items():
        h[r] = v
    return pd.DataFrame({"open_time": pd.date_range(start, periods=n, freq="D", tz="UTC"), "open": o, "high": h,
                         "low": l, "close": c, "volume": 1.0, "quote_volume": c,
                         "trades": 1 if trades is None else trades})


def _oracle_atr(df: pd.DataFrame, new=None) -> list:
    """Textbook Wilder ATR14 (separate code): TR, mean of the first 14, then atr += (tr - atr) / 14; restarts where
    new[i]."""
    h, l, c = df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    out, atr, trs = [], None, []
    for i in range(len(c)):
        if i == 0 or (new is not None and new[i]):
            atr, trs, tr = None, [], h[i] - l[i]
        else:
            tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if atr is None:
            trs.append(tr)
            if len(trs) == ATR_N:
                atr = sum(trs) / ATR_N
            out.append(math.nan if atr is None else atr)
        else:
            atr = atr + (tr - atr) / ATR_N
            out.append(atr)
    return out


def _oracle_sigma(closes, i: int, s: int = 0) -> float:
    import statistics
    lo = max(i - SIGMA_DAYS + 1, s + 1)
    r = [math.log(closes[j] / closes[j - 1]) for j in range(lo, i + 1)]
    return statistics.stdev(r) if len(r) >= SIGMA_MIN else math.nan


def _oracle_quantile(vals, p: float) -> float:
    v = sorted(vals)
    h = (len(v) - 1) * p
    lo = math.floor(h)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (h - lo) * (v[hi] - v[lo])


def _t_ticks(say):
    rng = np.random.default_rng(11)
    # decimal strings with a known number of decimals -> price_decimals; oracle = Decimal's exponent
    strs, want = ["0", "1", "93450.12", "93450.1", "0.01234", "0.00001234", "1e-08", "123.456789", "0.1",
                  "65000.00", "2.880", "0.000123456789"], []
    for _ in range(6000):
        m, d = int(rng.integers(1, 10 ** int(rng.integers(1, 10)))), int(rng.integers(0, 11))
        s = str(m).rjust(d + 1, "0")
        strs.append(s[:len(s) - d] + ("." + s[len(s) - d:] if d else ""))
    for s in strs:
        e = Decimal(s).normalize().as_tuple().exponent
        want.append(max(0, -e))
    got = price_decimals(np.array([float(s) for s in strs]))
    assert (got == np.array(want)).all(), [(s, g, w) for s, g, w in zip(strs, got, want) if g != w][:5]
    # a second oracle: numpy's shortest positional repr
    xs = np.array([float(s) for s in strs])
    rep = [len(np.format_float_positional(x, unique=True, trim="-").partition(".")[2]) for x in xs]
    assert (got == np.array(rep)).all()
    assert price_decimals([0.1 + 0.2])[0] == -1 and price_decimals([np.nan])[0] == -1     # 17 decimals: unresolved
    assert infer_tick([93450.12, 93451.1, 93450.0]) == ("0.01", 2, True)
    assert infer_tick([1.0, 3.0]) == ("1", 0, True) and infer_tick([0.1 + 0.2, 1.0])[2] is False
    say(f"  price_decimals: {len(strs)} decimal strings agree with two oracles")
    # the tick comes from the 1m bars of d0-6..d0 only (traded minutes)
    t0 = pd.Timestamp("2023-03-06 03:30", tz="UTC")                 # d0 = 2023-03-05
    d1 = _alt_bars("2023-01-02", 70, 10.0, 0.04)
    mins = pd.date_range("2023-02-20", "2023-03-07 23:59", freq="1min", tz="UTC")
    day = (mins.tz_localize(None).normalize() - pd.Timestamp("2023-02-20")).days.to_numpy()
    px = 10 + (np.arange(len(mins)) % 97) * 0.001                    # 3 decimals
    px = np.where(day <= 6, 10 + (np.arange(len(mins)) % 89) * 0.00001, px)   # 2023-02-20..26: 5 decimals
    px = np.round(px, 6)
    m1 = pd.DataFrame({"open_time": mins, "open": px, "high": px, "low": px, "close": px, "trades": 1,
                       "quote_volume": 1.0})
    m1.loc[(day == 13) & (np.arange(len(mins)) % 500 == 0), ["low", "trades"]] = [9.1234567, 0]   # zero-trade: ignored
    m1.loc[day == 15, "low"] = 9.123456                               # 2023-03-07 (after d0): ignored
    I = inputs_at("X", t0, {"d1": d1, "m1": m1})
    assert I["tick_str"] == "0.001" and I["tick_source"] == "1m" and I["tick_resolved"], I["tick_str"]
    I = inputs_at("X", pd.Timestamp("2023-02-28 03:30", tz="UTC"), {"d1": d1, "m1": m1})  # window 02-21..02-27
    assert I["tick_str"] == "0.00001", I["tick_str"]
    I = inputs_at("X", t0, {"d1": d1})                                # no 1m bars: the daily bars' decimals
    assert I["tick_source"] == "1d" and I["tick_resolved"] is False and I["tick_str"] == _tick_str(DEC_MAX)
    d1r = d1.copy()
    for c in ("open", "high", "low", "close"):
        d1r[c] = d1r[c].round(3)
    I = inputs_at("X", t0, {"d1": d1r})
    assert I["tick_source"] == "1d" and I["tick_str"] == "0.001" and I["tick_resolved"]
    I = inputs_at("X", t0, {"d1": d1, "m1": m1.assign(low=m1["low"] + 1e-9 * np.pi)})   # off any decimal grid
    assert I["tick_resolved"] is False and I["tick_dec"] == DEC_MAX
    # coding choice 5: prints at an older, finer tick (at most 0.1% of the window's prices) are set aside
    assert tick_rule([0, 0, 0, 999, 0, 1] + [0] * 8) == (3, 5, 1, 1000)           # 1 of 1,000: ignored
    assert tick_rule([0, 0, 0, 998, 0, 2] + [0] * 8) == (5, 5, 0, 1000)           # 2 of 1,000: a real grid
    assert tick_rule([0, 0, 0, 999, 0, 1] + [0] * 8, finer_max=0.0) == (5, 5, 0, 1000)   # the literal maximum
    assert tick_rule([5, 0] + [0] * 11 + [1])[0] == DEC_MAX + 1                    # 1 of 6 unresolved: unresolved
    assert infer_tick([1.5] * 999 + [1.25]) == ("0.1", 1, True) and infer_tick([1.5] * 998 + [1.25] * 2)[0] == "0.01"
    win = (day >= 7) & (day <= 13) & (m1["trades"].to_numpy() > 0)    # t0's window 2023-02-27..03-05, traded
    n_win = 4 * int(win.sum())                                        # 40,308 prices: 0.1% of them is 40.3
    early = np.flatnonzero(win & (day <= 11))
    stale = early[::97][: n_win // 1000]                              # 40 lows at a finer old tick (5 decimals)
    s1 = m1.copy()
    s1.loc[stale, "low"] = np.round(s1.loc[stale, "low"].to_numpy() - 0.00003, 5)
    I = inputs_at("X", t0, {"d1": d1, "m1": s1})
    assert len(stale) == 40 and I["tick_str"] == "0.001" and I["tick_source"] == "1m-majority", I
    assert I["tick_raw_str"] == "0.00001" and I["tick_n_finer"] == 40 and I["tick_n_prices"] == n_win
    s2 = s1.copy()
    more = early[1::97][:2]                                           # 42 > 40.3: a real finer grid
    s2.loc[more, "low"] = np.round(s2.loc[more, "low"].to_numpy() - 0.00003, 5)
    I = inputs_at("X", t0, {"d1": d1, "m1": s2})
    assert I["tick_str"] == "0.00001" and I["tick_source"] == "1m" and I["tick_n_finer"] == 0
    # a refinement late on d0: the last 15 minutes of 2023-03-05 on a 0.0001 grid (60 prices > 0.1%)
    s3 = m1.copy()
    late = np.flatnonzero((day == 13) & (np.arange(len(mins)) % 1440 >= 1425))
    fine = np.round(10.0001 + 0.0002 * (np.arange(len(late)) % 7), 4)          # odd last digit: 4 decimals
    s3.loc[late, ["open", "high", "low", "close"]] = np.repeat(fine[:, None], 4, axis=1)
    I = inputs_at("X", t0, {"d1": d1, "m1": s3})
    assert len(late) == 15 and I["tick_str"] == "0.0001" and I["tick_source"] == "1m", I["tick_str"]
    say("  tick: 7-day window of traded 1m bars, daily fallback, unresolved flag; finer prints of <= 0.1% set aside "
        "(boundary by hand), a refinement late on d0 adopted")


def _t_floor_rh(say):
    rng = np.random.default_rng(5)
    cases = [(0.3, "0.1", 0.3), (0.29999, "0.01", 0.29), (1.15, "0.01", 1.15), (0.1 + 0.2, "0.1", 0.3),
             (65000.0, "0.01", 65000.0), (2.0, "0.5", 2.0), (1.9999, "0.5", 1.5), (0.000123456789, "0.00000001",
                                                                                    0.00012345),
             (1.2349, "0.005", 1.23), (95000.0, "1", 95000.0), (7.5, "0.0001", 7.5)]
    for x, t, want in cases:
        assert floor_tick(x, t) == want, (x, t, floor_tick(x, t), want)
    assert floor_tick(-1.0, "0.01") is None and floor_tick(0.004, "0.01") is None and floor_tick(np.nan, "0.1") is None
    assert floor_tick(Decimal("2.30"), "0.1") == 2.3 and floor_n(Decimal("2.3"), "0.01") == 230
    for x, t, want in ((0.3, "0.1", 0.3), (0.30001, "0.01", 0.31), (1.15, "0.01", 1.15), (0.1 + 0.2, "0.1", 0.3),
                       (2.0000001, "0.5", 2.5), (1.2301, "0.005", 1.235), (65000.004, "0.01", 65000.01)):
        assert ceil_tick(x, t) == want, (x, t, ceil_tick(x, t), want)
    n_ok = 0
    for _ in range(4000):
        d = int(rng.integers(0, 9))
        tick = _tick_str(d)
        n = int(rng.integers(1, 10 ** 7))
        on = float(Decimal(n) * Decimal(tick))                        # a price exactly on the grid (as parsed)
        off = (n + float(rng.uniform(0.001, 0.999))) * float(Decimal(tick))
        assert floor_tick(on, tick) == on == _ofloor(on, tick)
        assert floor_tick(off, tick) == _ofloor(off, tick)
        n_ok += 1
    say(f"  floor to tick: {len(cases)} hand cases, {n_ok} random on/off-grid pairs agree with the decimal oracle")
    cat = {"AAVE": "0.01", "ADA": "0.0000001"}
    Lr, dr = rh_round("AAVE", 123.4567, P0=150.0, sigma=0.05, catalog=cat)
    assert Lr == 123.45 and _near(dr, math.log(150.0 / 123.45) / 0.05)
    Lr, dr = rh_round("ADA", 0.123456789, P0=0.2, sigma=0.05, catalog=cat)
    assert Lr == 0.1234567 and _near(dr, math.log(0.2 / 0.1234567) / 0.05)
    assert rh_round("AAVE", 0.004, P0=1.0, sigma=0.05, catalog=cat) is None
    for bad in ("XYZ", "LIT"):
        try:
            rh_round(bad, 1.0, P0=2.0, sigma=0.05, catalog=cat)
            raise AssertionError(bad)
        except KeyError:
            pass
    # build_spec's short form rh_round(coin, L) cannot recompute delta (§13 item 1): it raises (review r1)
    for kw in ({}, {"P0": 150.0}, {"sigma": 0.05}, {"P0": 150.0, "sigma": math.nan}):
        try:
            rh_round("AAVE", 123.4567, catalog=cat, **kw)
            raise AssertionError(kw)
        except ValueError:
            pass
    try:
        real = _catalog()
        assert rh_tick("AAVE") == str(real.loc[real.coin == "AAVE", "price_tick_str"].iloc[0])
        assert rh_round("ADA", 0.123456789, P0=0.2, sigma=0.05)[0] == floor_tick(0.123456789, rh_tick("ADA"))
        say(f"  Robinhood rounding: injected catalog and the saved catalog ({len(real)} pairs); rh_round(coin, L) "
            "without P0 / sigma raises")
    except FileNotFoundError:
        say("  Robinhood rounding: injected catalog (the saved catalog is absent)")
    # a level floored straight to Robinhood's tick equals rh_round of the unrounded level, delta included
    d1 = _alt_bars("2023-01-02", 70, 123.456, 0.05)
    I = inputs_at("AAVE", "2023-03-06 03:30", {"d1": d1}, tick=cat["AAVE"])
    r = level_info("M2", I, k=8)
    assert I["tick_source"] == "given" and (r["L"], r["delta"]) == rh_round("AAVE", r["x"], inputs=I, catalog=cat)


def _t_inputs(say):
    a, base = 0.04, 10.0
    d1 = _alt_bars("2023-01-02", 70, base, a)                     # rows 0.. = 2023-01-02..; row 62 = 2023-03-05 (Sun)
    data = {"d1": d1, "tick": "0.0001"}
    sig30 = a * math.sqrt(30 / 29)
    c = base * (math.exp(a) - 1)
    for t0 in ("2023-03-06 03:30", "2023-03-06 13:30", "2023-03-06 00:00", "2023-03-06 23:59"):
        I = inputs_at("X", t0, data)
        assert I["d0"] == pd.Timestamp("2023-03-05") and I["d_fut"] == pd.Timestamp("2023-03-04"), I["d0"]
        assert I["ok"] and I["P0"] == base and I["n_ret"] == 30 and _near(I["sigma30"], sig30)
        assert _near(I["atr"], c) and _near(I["atr_pct"], c / base) and I["seg_days"] == 63
    I = inputs_at("X", "2023-03-05 23:59", data)
    assert I["d0"] == pd.Timestamp("2023-03-04") and I["P0"] == base * math.exp(a)
    # >= 25 returns in one segment: row 25 has 25 (sigma by hand), row 24 has 24 (invalid)
    I = inputs_at("X", "2023-01-28 03:30", data)                  # d0 = 2023-01-27 = row 25
    m = a / 25
    assert I["ok"] and I["n_ret"] == 25 and _near(I["sigma30"], math.sqrt((25 * a * a - 25 * m * m) / 24))
    I = inputs_at("X", "2023-01-27 03:30", data)
    assert not I["ok"] and I["n_ret"] == 24 and not I["seg_ok"] and "25" in I["why"]
    # a missing day starts a new segment: the window and the ATR restart after it
    I = inputs_at("X", "2023-03-06 03:30", {"d1": d1.drop(index=45), "tick": "0.0001"})
    assert not I["ok"] and I["n_ret"] == 62 - 46 and I["seg_first_day"] == pd.Timestamp("2023-02-17")
    I = inputs_at("X", "2023-03-06 03:30", {"d1": d1.drop(index=30), "tick": "0.0001"})
    assert I["ok"] and I["n_ret"] == 30 and _near(I["sigma30"], _oracle_sigma(d1.close.tolist(), 62, 31))
    assert _near(I["atr"], _oracle_atr(d1.drop(index=30).reset_index(drop=True),
                                       [i == 30 for i in range(69)])[61])
    # a zero-trade day is a missing day; a > 25% open jump starts a segment too
    z = d1.copy()
    z.loc[45, "trades"] = 0
    assert inputs_at("X", "2023-03-06 03:30", {"d1": z, "tick": "0.0001"})["n_ret"] == 16
    j = d1.copy()
    j.loc[45:, ["open", "high", "low", "close"]] *= 1.3
    j.loc[45, "open"] = d1.loc[44, "close"] * 1.3
    I = inputs_at("X", "2023-03-06 03:30", {"d1": j, "tick": "0.0001"})
    assert I["n_ret"] == 17 and not I["ok"]
    # d0 without a bar: no placement
    I = inputs_at("X", "2023-03-06 03:30", {"d1": d1.drop(index=62), "tick": "0.0001"})
    assert not I["traded"] and not I["ok"] and "no traded" in I["why"]
    # a later bar never matters; price= replaces P0 (the sheet's fresh price)
    later = d1.copy()
    later.loc[63:, ["open", "high", "low", "close"]] *= 3
    J = inputs_at("X", "2023-03-06 03:30", {"d1": later, "tick": "0.0001"})
    I = inputs_at("X", "2023-03-06 03:30", data)
    assert all(I[k] == J[k] for k in ("P0", "sigma30", "atr", "tick_str"))
    I = inputs_at("X", "2023-03-06 03:30", data, price=12.0)
    assert I["P0"] == 12.0 and I["close"] == base and _near(I["atr_pct"], c / 12.0)
    # the index series runs on the futures clock: P0 = index close of d0 - 1 (Saturday)
    ix = _alt_bars("2023-01-02", 70, 20.0, a).drop(columns=["trades"])
    I = inputs_at("X", "2023-03-06 03:30", {"index_d1": ix}, series="index")
    assert I["d_last"] == pd.Timestamp("2023-03-04") and I["P0"] == 20.0 * math.exp(a) and I["ok"]
    assert I["tick_source"] == "index-1d"
    say("  inputs: d0 / futures day, P0, sigma30 and ATR14 by hand, 25-return rule, segments, index clock")


def _t_simple(say):
    a, base = 0.04, 10.0
    d1 = _alt_bars("2023-01-02", 70, base, a)
    I = inputs_at("X", "2023-03-06 03:30", {"d1": d1, "tick": "0.0001"})
    sig, c = a * math.sqrt(30 / 29), base * (math.exp(a) - 1)
    L, d = level("M1", I, d=0.25)
    assert L == 7.5 and _near(d, math.log(10 / 7.5) / sig)
    for k in (5, 6, 8, 10, 12, 6.7):
        L, d = level("M2", I, k=k)
        assert L == _ofloor(10 * math.exp(-k * sig), "0.0001") and _near(d, math.log(10 / L) / sig)
    for kA in M2A_K:
        assert level("M2a", I, kA=kA)[0] == _ofloor(10 - kA * c, "0.0001")
    assert level("M2a", I, kA=500) is None and level_info("M2a", I, kA=500)["status"] == "non_positive"
    assert level_info("M1", I, d=-0.1)["status"] == "not_below_P0"                 # a "bid" above P0
    for bad in ({"k": 8, "x": 1}, {}):
        try:
            level("M2", I, **bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    J = inputs_at("X", "2023-01-27 03:30", {"d1": d1, "tick": "0.0001"})
    assert level("M2", J, k=8) is None and level_info("M2", J, k=8)["status"] == "invalid_inputs"
    say("  M1, M2, M2a by hand; guards and parameter checks")


def _t_m3(say):
    """M3: designed weekly dips with closed-form z, a brute-force oracle, eligibility, expanding pool."""
    rng = np.random.default_rng(3)
    start, n = "2023-01-02", 150                                   # row 0 is a Monday; Sundays are rows 6, 13, ...
    parts, dips = [], {}
    for coin, a, base, exc in (("A", 0.03, 10.0, ""), ("B", 0.05, 4.0, ""), ("C", 0.02, 1.0, "stablecoin"),
                               ("D", 0.04, 7.0, ""), ("E", 0.06, 3.0, "")):
        lows = {}
        for w in range(n // 7):
            r = 7 * w + 2                                          # Wednesdays
            if r < n:
                dips[(coin, r)] = float(rng.uniform(0.02, 0.4))
                lows[r] = base * math.exp(-dips[(coin, r)])        # min(open, close) is base on every row
        b = _alt_bars(start, n, base, a, lows=lows)
        b["coin"], b["excluded"] = coin, exc
        if coin == "E":
            b = b.drop(index=[60])                                 # a missing day: E's segment restarts
        parts.append(b)
    panel = pd.concat(parts, ignore_index=True)
    panel["day"] = panel["open_time"].dt.tz_localize(None).dt.normalize()
    backstop = pd.DataFrame({"month": ["2023-03"], "coin": ["D"], "excluded": [True]})
    # oracle windows (explicit loops)
    want = []
    for coin, g in panel.groupby("coin"):
        if g["excluded"].iloc[0]:
            continue
        g = g.reset_index(drop=True)
        dd = [(t - pd.Timestamp(start, tz="UTC")).days for t in g["open_time"]]
        cl, lo = g["close"].tolist(), g["low"].tolist()
        seg0 = 0
        for i in range(len(g)):
            if i > 0 and dd[i] - dd[i - 1] != 1:
                seg0 = i
            if dd[i] % 7 != 6:
                continue
            sg = _oracle_sigma(cl, i, seg0)
            life = [lo[j] for j in range(i + 1, min(i + 8, len(g))) if dd[j] - dd[i] <= 7 and
                    all(dd[q] - dd[q - 1] == 1 for q in range(i + 1, j + 1))]
            mon = (pd.Timestamp(start) + pd.Timedelta(days=dd[i] + 1)).strftime("%Y-%m")
            if math.isnan(sg) or not life or (mon, coin) in {("2023-03", "D")}:
                continue
            want.append((coin, dd[i], math.log(min(life) / cl[i]) / sg))
    pool = m3_pool({"panel": panel, "backstop": backstop})
    got = sorted(zip(pool["coin"], [(d - pd.Timestamp(start)).days for d in pool["d0"]], pool["z"]))
    want = sorted(want)
    assert len(got) == len(want) and all(g[:2] == w[:2] and _near(g[2], w[2], 1e-9) for g, w in zip(got, want))
    # closed form: A's Sunday rows with 30 returns whose close is the low close: z = -D / (a sqrt(30/29))
    sa = 0.03 * math.sqrt(30 / 29)
    hand = 0
    for coin, d, z in got:
        if coin == "A" and d >= 30 and d % 2 == 0 and ("A", d + 3) in dips:
            assert _near(z, -dips[("A", d + 3)] / sa, 1e-9)
            hand += 1
    assert hand >= 5
    # level at several placements: q = the oracle's linear-interpolation quantile of the windows ended by d0
    dA = panel[panel.coin == "A"].drop(columns=["coin", "excluded", "day"])
    data = {"d1": dA, "tick": "0.0001", "panel": panel, "backstop": backstop}
    checked = 0
    for t0 in pd.date_range("2023-02-13 03:30", "2023-05-29 03:30", freq="7D", tz="UTC"):
        I = inputs_at("A", t0, data)
        d0 = (I["d0"] - pd.Timestamp(start)).days
        zs = [z for _, d, z in want if d + 7 <= d0]
        for p in M3_P:
            r = level_info("M3", I, p=p)
            q = _oracle_quantile(zs, p)
            assert r["aux"]["n_windows"] == len(zs) and _near(r["aux"]["q"], q, 1e-9)
            assert r["L"] == _ofloor(I["P0"] * math.exp(q * I["sigma30"]), "0.0001"), (t0, p)
            checked += 1
    # the window whose life ends on d0 is in; the one ending a week later is not
    I = inputs_at("A", "2023-04-03 03:30", data)                   # d0 = 2023-04-02 = day 90 (a Sunday)
    assert level_info("M3", I, p=0.05)["aux"]["n_windows"] == sum(1 for _, d, _ in want if d + 7 <= 90)
    assert any(d + 7 == 90 for _, d, _ in want)
    # M3c: too few own windows here; a long series gives the coin's own quantile
    assert level_info("M3c", I, p=0.05)["status"] == "no_data"
    long = _alt_bars("2019-01-07", 900, 5.0, 0.05, lows={r: 5.0 * math.exp(-0.01 * (r % 37)) for r in range(2, 900, 7)})
    pl = long.assign(coin="L", excluded="", day=long["open_time"].dt.tz_localize(None).dt.normalize())
    J = inputs_at("L", "2021-06-21 03:30", {"d1": long, "tick": "0.0001", "panel": pl})
    own = [z for c_, d, z in sorted(zip(*m3_pool({"panel": pl}).pipe(lambda f: (f.coin, f.end, f.z))))
           if d <= pd.Timestamp("2021-06-20")]
    rc = level_info("M3c", J, p=0.05)
    assert rc["status"] == "ok" and rc["aux"]["n_windows"] == len(own) >= M3C_MIN
    assert rc["L"] == _ofloor(J["P0"] * math.exp(_oracle_quantile(own, 0.05) * J["sigma30"]), "0.0001")
    say(f"  M3: {len(want)} pooled windows match the oracle ({hand} by closed form), {checked} levels; "
        "exclusions, backstop, segment, expanding pool, M3c")


def _t_m4(say):
    a, base, n = 0.04, 10.0, 400
    start = pd.Timestamp("2023-03-05") - pd.Timedelta(days=n - 1)    # the last row is Sunday 2023-03-05
    i = n - 1
    lows = {i - 50: base * math.exp(-0.35), i - 200: base * math.exp(-0.45)}
    d1 = _alt_bars(start, n, base, a, lows=lows)
    data = {"d1": d1, "tick": "0.0001"}
    I = inputs_at("X", "2023-03-06 03:30", data)
    atr = _oracle_atr(d1)[i]
    P0, sig = d1.close.iloc[i], a * math.sqrt(30 / 29)
    assert _near(I["atr"], atr) and I["P0"] == P0
    ap = atr / P0
    exp = {("M4", 90, 0.5): lows[i - 50] * (1 - 0.5 * ap), ("M4", 90, 1.0): lows[i - 50] * (1 - ap),
           ("M4", 365, 0.5): lows[i - 200] * (1 - 0.5 * ap), ("M4", 365, 1.0): lows[i - 200] * (1 - ap)}
    for (m, N, b), x in exp.items():
        L, d = level(m, I, N=N, buffer=b)
        assert L == _ofloor(x, "0.0001") and 4 <= d <= 14 and _near(d, math.log(P0 / L) / sig, 1e-9), (N, b, d)
    assert level("M4", I, N=30, buffer=0.5) is None and level_info("M4", I, N=30, buffer=0.5)["status"] == "abstain"
    assert level("M4f", I, N=90)[0] == _ofloor(lows[i - 50] * (1 + 0.1 * ap), "0.0001")
    assert level("M4", I) == level("M4", I, N=90, buffer=0.5)        # H4's M4 is the default
    # a missing day 39 days before d0: the 90-day window stops there and the dip is not seen
    J = inputs_at("X", "2023-03-06 03:30", {"d1": d1.drop(index=i - 39), "tick": "0.0001"})
    rj = level_info("M4", J, N=90, buffer=0.5)
    assert J["ok"] and rj["aux"]["days"] == 39 and rj["status"] == "abstain", rj
    # a chart level at or above P0, or floored to zero (a bad print below one tick), abstains (delta outside the band)
    d1e = _alt_bars(start + pd.Timedelta(days=1), n - 1, base, a)                 # d0 closes at base = its low
    K = inputs_at("X", "2023-03-06 03:30", {"d1": d1e, "tick": "0.0001"})
    rk = level_info("M4f", K, N=30)
    assert K["P0"] == base and rk["status"] == "abstain" and ">= P0" in rk["detail"], rk
    d1z = _alt_bars(start, n, base, a, lows={i - 50: 0.00004})
    rz = level_info("M4", inputs_at("X", "2023-03-06 03:30", {"d1": d1z, "tick": "0.0001"}), N=90, buffer=0.5)
    assert rz["status"] == "abstain" and "<= 0" in rz["detail"], rz
    say("  M4 / M4f by hand: N-day lows, buffers, abstention, the segment-bounded look-back")


def _t_m4s(say):
    a, base, n = 0.04, 10.0, 200
    start = pd.Timestamp("2023-03-05") - pd.Timedelta(days=n - 1)
    i = n - 1
    P0, sig = base * math.exp(a * (i % 2)), a * math.sqrt(30 / 29)

    def run(dips):
        lows = {i - k: P0 * math.exp(-dl * sig) for k, dl in dips.items()}
        d1 = _alt_bars(start, n, base, a, lows=lows)
        I = inputs_at("X", "2023-03-06 03:30", {"d1": d1, "tick": "0.0001"})
        ap = _oracle_atr(d1)[i] / P0
        return I, ap, lows

    I, ap, lows = run({40: 6.0, 20: 2.0, 3: 8.0})                   # 20: delta 2 (out); 3: not confirmed
    r = level_info("M4s", I)
    assert r["aux"]["pivot"] == lows[i - 40] and r["L"] == _ofloor(lows[i - 40] * (1 - 0.5 * ap), "0.0001")
    I, ap, lows = run({40: 6.0, 20: 2.0, 5: 8.0})                   # 5 days old: confirmed, most recent
    assert level_info("M4s", I)["aux"]["pivot"] == lows[i - 5]
    I, ap, lows = run({40: 6.0, 20: 5.0, 3: 8.0})                   # 20 in the band now
    assert level("M4s", I)[0] == _ofloor(lows[i - 20] * (1 - 0.5 * ap), "0.0001")
    I, ap, lows = run({40: 3.0, 20: 2.0, 3: 8.0})
    assert level("M4s", I) is None and "no confirmed pivot" in level_info("M4s", I)["detail"]
    I, ap, lows = run({40: 13.9, 20: 2.0})                          # the pivot is in the band, the buffered level not
    r = level_info("M4s", I)
    assert r["status"] == "abstain" and "outside" in r["detail"], r
    say("  M4s by hand: confirmation after 5 days, most recent pivot in the band, band on the buffered level")


def _t_m5(say):
    def series(P0, a, n=81, trades=None, wide=None):
        start = pd.Timestamp("2023-03-05") - pd.Timedelta(days=n - 1)   # n odd: the last row (d0) closes at base
        d = _alt_bars(start, n, P0, a)
        if wide:
            d["high"], d["low"] = d["close"] * (1 + wide), d["close"] * (1 - wide)
        return d

    t0 = "2023-03-06 03:30"
    a = 0.05
    I = inputs_at("BTC", t0, {"d1": series(95000.0, a), "tick": "0.01"})
    sig = a * math.sqrt(30 / 29)
    assert I["P0"] == 95000.0 and 60000 < 95000 * math.exp(-8 * sig) < 67500
    r = level_info("M5a", I)
    assert r["aux"]["e"] == 4 and r["aux"]["grid"] == "G" and r["aux"]["R_str"] == "65000" and r["L"] == 65000.0
    assert level("M5f", I)[0] == 65000.01
    assert level("M5b", I)[0] == _ofloor(65000.0 * (1 - 0.5 * (math.exp(a) - 1)), "0.01")
    I = inputs_at("NEAR", t0, {"d1": series(2.88, a), "tick": "0.001"})
    r = level_info("M5a", I)
    assert r["aux"]["e"] == 0 and r["aux"]["R_str"] == "2.0" and r["L"] == 2.0 and level("M5f", I)[0] == 2.001
    a2 = 0.03 / math.sqrt(30 / 29)                                   # sigma = 0.03: no multiple of 0.5 within 2 sigma
    I = inputs_at("NEAR", t0, {"d1": series(2.88, a2), "tick": "0.001"})
    r = level_info("M5a", I)
    assert r["aux"]["grid"] == "g" and r["aux"]["R_str"] == "2.3" and r["L"] == 2.3, r["aux"]
    assert m5_round(1000.0, 0.05)[2] == 3 and m5_round(999.99, 0.05)[2] == 2 and m5_round(0.01, 0.05)[2] == -2
    assert str(m5_round(0.0123, 0.05)[0]) in ("0.008", "0.0085", "0.009", "0.007", "0.0075")
    I = inputs_at("Q", t0, {"d1": series(2.88, 0.005, wide=0.1), "tick": "0.0001"})   # ATR% / sigma about 40
    assert level("M5a", I) is not None and level_info("M5b", I)["status"] == "abstain"
    say("  M5 by hand: BTC 95,000 -> R 65,000 (G), NEAR 2.88 -> 2.0 (G) and 2.3 (g); f / a / b; abstention")


def _t_m6(say):
    a, base, n = 0.04, 10.0, 200
    start = pd.Timestamp("2023-03-05") - pd.Timedelta(days=n - 1)
    d1 = _alt_bars(start, n, base, a)
    P0, sig = d1.close.iloc[-1], a * math.sqrt(30 / 29)
    w = BIN * sig
    d0 = pd.Timestamp("2023-03-05", tz="UTC")

    def hours(spec, extra=(), back=20):
        rows = [(d0 - pd.Timedelta(days=10), P0, P0 * math.exp(-81 * w), 81.0)]     # background: 1 per bin, 0..80
        for k, (b, v) in enumerate(spec):
            px = P0 * math.exp(-(b + 0.5) * w)
            rows.append((d0 - pd.Timedelta(days=back, hours=k), px, px, v))
        rows += list(extra)
        rows.append((d0 - pd.Timedelta(days=5), P0, P0 * 0.5, 0.0))                  # no volume: ignored
        return pd.DataFrame({"open_time": [r[0] for r in rows], "high": [r[1] for r in rows],
                             "low": [r[2] for r in rows], "quote_volume": [r[3] for r in rows], "trades": 1})

    t0 = "2023-03-06 03:30"
    bmin, mass = volume_profile([P0 * math.exp(-12.5 * w)], [P0 * math.exp(-10.5 * w)], [2.0], P0, sig)
    assert bmin == 10 and np.allclose(mass, [0.5, 1.0, 0.5], rtol=1e-9)
    decoys = [(d0 - pd.Timedelta(days=91), P0 * math.exp(-30.5 * w), P0 * math.exp(-30.5 * w), 1000.0),
              (d0 + pd.Timedelta(days=1, hours=1), P0 * math.exp(-30.5 * w), P0 * math.exp(-30.5 * w), 1000.0)]
    spec = [(5, 50.0), (20, 10.0), (40, 30.0), (60, 100.0)]
    I = inputs_at("X", t0, {"d1": d1, "h1": hours(spec, decoys), "tick": "0.0001"})
    r = level_info("M6", I)
    assert r["aux"]["edge_delta"] == 10.25 and _near(r["aux"]["node_value"], 1 + 30 / 3, 1e-9)
    assert r["L"] == _ofloor(P0 * math.exp(-10.25 * sig), "0.0001") and _near(r["aux"]["median"], 1.0, 1e-9)
    I = inputs_at("X", t0, {"d1": d1, "h1": hours([(5, 50.0), (20, 10.0), (60, 100.0)]), "tick": "0.0001"})
    assert level_info("M6", I)["aux"]["edge_delta"] == 5.25
    I = inputs_at("X", t0, {"d1": d1, "h1": hours([(5, 50.0), (20, 1.0), (60, 100.0)]), "tick": "0.0001"})
    assert level("M6", I) is None and level_info("M6", I)["status"] == "abstain"
    # the window stops at a segment start: with a missing day 30 days before d0, nodes 35 days back are not seen
    # (only the flat background remains: no HVN); with the missing day 40 days back they are
    I = inputs_at("X", t0, {"d1": d1, "h1": hours(spec, back=35), "tick": "0.0001"})
    assert level_info("M6", I)["aux"]["edge_delta"] == 10.25
    I = inputs_at("X", t0, {"d1": d1.drop(index=n - 31), "h1": hours(spec, back=35), "tick": "0.0001"})
    assert I["ok"] and level_info("M6", I)["status"] == "abstain"
    I = inputs_at("X", t0, {"d1": d1.drop(index=n - 41), "h1": hours(spec, back=35), "tick": "0.0001"})
    assert level_info("M6", I)["aux"]["edge_delta"] == 10.25
    I = inputs_at("X", t0, {"d1": d1.drop(index=n - 41), "h1": hours(spec, back=45), "tick": "0.0001"})
    assert level_info("M6", I)["status"] == "abstain"
    # hourly bars from injected 1m bars when no h1 is given
    m = hours(spec).rename(columns={})
    m1 = pd.DataFrame({"open_time": m["open_time"], "open": m["high"], "high": m["high"], "low": m["low"],
                       "close": m["low"], "quote_volume": m["quote_volume"], "trades": 1})
    I = inputs_at("X", t0, {"d1": d1, "m1": m1, "tick": "0.0001"})
    assert level_info("M6", I)["aux"]["edge_delta"] == 10.25
    # the index series (HYPE's proxy) has no volume: no_data, even when the coin's spot hourly bars exist (review r1)
    J = inputs_at("X", t0, {"index_d1": d1.drop(columns=["trades"]), "h1": hours(spec, decoys), "tick": "0.0001"},
                  series="index")
    rj = level_info("M6", J)
    assert J["ok"] and rj["status"] == "no_data" and "hours" not in rj["aux"], rj
    say("  M6 by hand: uniform spreading, kernel, median non-zero bin, highest HVN in the band, window, segment; no "
        "data on the index series")


def _m7_frames(P0, sig, jumps, mark_lows, vwaps, start="2023-02-01", end="2023-03-06 23:55", oi0=1e6):
    """M7's frames: open interest oi0 coins plus the jumps (coins) at their 5-minute rows; hourly VWAP P0 except at
    `vwaps`; oi_usd = oi x the hour's VWAP, as in the archive (M7 does not read it)."""
    mt = pd.date_range(start, end, freq="5min", tz="UTC")
    inc = np.zeros(len(mt))
    for t, v in jumps.items():
        inc[mt.get_loc(pd.Timestamp(t, tz="UTC"))] += v
    ht = pd.date_range(start, pd.Timestamp(end).floor("h"), freq="1h", tz="UTC")
    lows = np.full(len(ht), P0)
    for t, v in mark_lows.items():
        lows[ht.get_loc(pd.Timestamp(t, tz="UTC"))] = v
    vw = np.full(len(ht), P0)
    for t, v in vwaps.items():
        vw[ht.get_loc(pd.Timestamp(t, tz="UTC"))] = v
    oi = oi0 + np.cumsum(inc)
    px = pd.Series(vw, ht).reindex(mt.floor("h")).to_numpy()
    met = pd.DataFrame({"create_time": mt, "oi": oi, "oi_usd": oi * px})
    mark = pd.DataFrame({"open_time": ht, "open": P0, "high": P0, "low": lows, "close": P0})
    perp = pd.DataFrame({"open_time": ht, "volume": 1.0, "quote_volume": vw})
    return {"metrics": met, "mark1h": mark, "perp1h": perp}


def _oracle_m7(P0, sig, atr_pct, entries, mark):
    """Separate code: entries (time ns, dOI, vwap) -> surviving weighted liquidation prices -> bins -> explicit
    smoothing -> largest node >= 2 x median with edge delta in [4, 14] -> its edge delta."""
    w = BIN * sig
    mass = {}
    for tj, dj, vw in entries:
        for lev, lw in zip(M7_LEV, M7_LEV_W):
            liq = vw * (1 - 1 / lev + M7_MAINT)
            if any(lt >= tj and lo <= liq for lt, lo in mark):
                continue
            b = math.floor((math.log(P0) - math.log(liq)) / w)
            mass[b] = mass.get(b, 0.0) + dj * M7_LONG * lw
    if not mass:
        return None
    b0, b1 = min(mass) - 2, max(mass) + 2
    sm = {b: sum(mass.get(b - k, 0.0) * wk for k, wk in zip(range(-2, 3), (1, 2, 3, 2, 1))) / 9 for b in
          range(b0, b1 + 1)}
    med = float(np.median(list(sm.values())))
    best = None
    for b in range(b0, b1 + 1):
        v = sm[b]
        if v > sm.get(b - 1, 0.0) and v > sm.get(b + 1, 0.0) and v >= M7_PEAK * med and 4 <= (b + 1) * BIN <= 14:
            if best is None or v > best[1]:
                best = ((b + 1) * BIN, v)
    return best


def _t_m7(say):
    a, base, n = 0.04, 10.0, 120
    start = pd.Timestamp("2023-03-05") - pd.Timedelta(days=n - 1)
    d1 = _alt_bars(start, n, base, a)
    P0, sig = d1.close.iloc[-1], a * math.sqrt(30 / 29)
    t0 = "2023-03-06 03:30"
    p1, p2 = P0 * math.exp(-0.10), P0 * math.exp(-0.05)
    jumps = {"2023-02-02 12:00": 3e5,                       # before the 30-day window: ignored (open interest in coins)
             "2023-02-10 12:05": 1e5,                       # J1, hour 12:00 at p1
             "2023-02-20 08:00": 5e4,                       # J2, on the hour: the 07:00 bar's VWAP (p2), not 08:00's
             "2023-02-25 00:00": -2e5,                      # a decrease: ignored
             "2023-03-05 10:00": 1e6}                       # on d0: not published by t0
    vwaps = {"2023-02-10 12:00": p1, "2023-02-20 07:00": p2, "2023-02-20 08:00": P0 * math.exp(-0.30),
             "2023-03-05 10:00": P0 * math.exp(-0.40)}
    marks = {"2023-02-25 10:00": p2 * 0.95,                 # crosses J2's 20x and 50x liquidation prices only
             "2023-03-05 05:00": P0 * 0.5}                  # on d0: not published by t0
    f = _m7_frames(P0, sig, jumps, marks, vwaps)
    I = inputs_at("X", t0, {"d1": d1, "tick": "0.0001", **f})
    r = level_info("M7", I)
    ap = I["atr_pct"]
    assert r["status"] == "ok" and r["aux"]["edge_delta"] == 8.0, r     # J1's 5x band: bin 31, edge 8.0 sigma
    assert r["L"] == _ofloor(P0 * math.exp(-8.0 * sig) * (1 - 0.25 * ap), "0.0001")
    assert r["aux"]["entries"] == 2 and _near(r["aux"]["new_oi_usd"], 1e5 * p1 + 5e4 * p2)   # coins x entry VWAP
    r_full = r
    ns = lambda t: pd.Timestamp(t, tz="UTC").value
    mk = [(ns(t), v) for t, v in marks.items() if pd.Timestamp(t) < pd.Timestamp("2023-03-05")]
    ent = [(ns("2023-02-10 12:05"), 1e5 * p1, p1), (ns("2023-02-20 08:00"), 5e4 * p2, p2)]
    assert _oracle_m7(P0, sig, ap, ent, mk)[0] == 8.0
    # without J1 the 5x band of J2 (entered at the 07:00 VWAP) is the largest peak: edge 6.75
    j2 = {k: v for k, v in jumps.items() if k != "2023-02-10 12:05"}
    I = inputs_at("X", t0, {"d1": d1, "tick": "0.0001", **_m7_frames(P0, sig, j2, marks, vwaps)})
    r = level_info("M7", I)
    assert r["aux"]["edge_delta"] == 6.75 == _oracle_m7(P0, sig, ap, ent[1:], mk)[0], r
    # every position liquidated by a later mark low: abstain; before 2021-12: no M7
    I = inputs_at("X", t0, {"d1": d1, "tick": "0.0001",
                            **_m7_frames(P0, sig, jumps, {**marks, "2023-03-01 00:00": P0 * 0.3}, vwaps)})
    assert level_info("M7", I)["status"] == "abstain"
    old = _alt_bars("2021-08-01", 140, base, a)
    assert level_info("M7", inputs_at("X", "2021-11-29 03:30", {"d1": old, "tick": "0.0001"}))["status"] == \
        "before_start"
    assert level_info("M7", inputs_at("X", "2021-12-06 03:30", {"d1": old, "tick": "0.0001"}))["status"] == "no_data"
    # a 10-minute hole: the increment across it is not a 5-minute change and is skipped
    f2 = _m7_frames(P0, sig, {"2023-02-10 12:05": 1e5, "2023-02-15 06:10": 9e5}, marks, vwaps)
    f2["metrics"] = f2["metrics"][f2["metrics"].create_time != pd.Timestamp("2023-02-15 06:05", tz="UTC")]
    I = inputs_at("X", t0, {"d1": d1, "tick": "0.0001", **f2})
    assert level_info("M7", I)["aux"]["entries"] == 1
    # review r1: new OI is opened contracts, not revaluation. Contracts constant while the price steps between p1 and
    # p2 every 6 hours (oi_usd moves): no position opened, no entry, no level (the old oi_usd rule gave 60 entries)
    ht = pd.date_range("2023-02-01", "2023-03-06 23:00", freq="1h", tz="UTC")
    steps = {str(t.tz_localize(None)): (p2 if (k // 6) % 2 else p1) for k, t in enumerate(ht)}
    fc = _m7_frames(P0, sig, {}, {}, steps, oi0=2e5)
    assert fc["metrics"]["oi_usd"].diff().gt(0).sum() >= 60 and fc["metrics"]["oi"].nunique() == 1
    rc = level_info("M7", inputs_at("X", t0, {"d1": d1, "tick": "0.0001", **fc}))
    assert rc["status"] == "no_data" and rc["aux"]["entries"] == 0, rc
    # contracts fall by 1% at each price step up (+5%): oi_usd rises, but no position is opened
    fdn = _m7_frames(P0, sig, {}, {}, steps, oi0=2e5)
    px = fdn["metrics"]["oi_usd"].to_numpy() / 2e5
    up = np.r_[False, np.diff(px) > 0]
    fdn["metrics"]["oi"] = 2e5 * 0.99 ** np.cumsum(up)
    fdn["metrics"]["oi_usd"] = fdn["metrics"]["oi"] * px
    assert (np.diff(fdn["metrics"]["oi_usd"].to_numpy())[up[1:]] > 0).all()        # x e^0.05 x 0.99 > 1
    rd = level_info("M7", inputs_at("X", t0, {"d1": d1, "tick": "0.0001", **fdn}))
    assert up.sum() >= 60 and rd["status"] == "no_data" and rd["aux"]["entries"] == 0, rd
    # zero rows (archive placeholders, oi = oi_usd = 0) are missing: the step out of them is not new open interest
    fz = _m7_frames(P0, sig, jumps, marks, vwaps)
    zr = (fz["metrics"].create_time >= "2023-02-15 06:00") & (fz["metrics"].create_time < "2023-02-15 16:00")
    fz["metrics"].loc[zr, ["oi", "oi_usd"]] = 0.0
    rz = level_info("M7", inputs_at("X", t0, {"d1": d1, "tick": "0.0001", **fz}))
    assert (rz["status"], rz["L"], rz["aux"]["entries"]) == ("ok", r_full["L"], 2), rz
    assert rz["aux"]["new_oi_usd"] == r_full["aux"]["new_oi_usd"] and rz["aux"]["rows"] < r_full["aux"]["rows"]
    # an injected metrics frame without the coins column cannot be read as positions
    try:
        level_info("M7", inputs_at("X", t0, {"d1": d1, "tick": "0.0001", **f,
                                              "metrics": f["metrics"].drop(columns=["oi"])}))
        raise AssertionError("metrics without oi")
    except ValueError:
        pass
    say("  M7 by hand and by a separate oracle: entry hour, removal by later mark lows, d0 data unseen, start date; "
        "new OI = opened contracts x entry VWAP (constant or falling contracts: no entry), zero rows missing")


def _t_m8(say):
    a, n, nc = 0.04, 230, 20
    start = pd.Timestamp("2023-03-05") - pd.Timedelta(days=200)       # row 200 = Sunday 2023-03-05 (d0)
    crash = [60, 80, 100, 120, 140, 160, 180]
    D = [0.08, 0.12, 0.20, 0.10, 0.05, 0.30, 0.15]                    # C00's own drops on the market-wide days
    late = 210                                                        # a market-wide day after d0
    parts = []
    for ci in range(nc):
        base = 10.0 * (1 + ci)
        c = base * np.exp(a * (np.arange(n) % 2))
        lows = {}
        for k, r in enumerate(crash + [late]):
            if ci == 0:
                lows[r] = c[r - 1] * math.exp(-(D[k] if k < len(D) else 0.5))
            elif ci in (1, 2, 3):
                lows[r] = c[r - 1] * 0.80
        if ci == 1:
            lows[90] = c[89] * 0.80                                   # one coin alone: not market-wide
        b = _alt_bars(start, n, base, a, lows=lows)
        if ci == 0:
            b.loc[90, "low"] = c[89] * math.exp(-0.1)                 # C00's drop on a day that is not market-wide
        if ci == 19:
            b = b.iloc[115:]                                          # listed late: 2 own market-wide days by d0
        b["coin"], b["excluded"] = f"C{ci:02d}", ""
        parts.append(b)
    panel = pd.concat(parts, ignore_index=True)
    months = sorted(set(panel["open_time"].dt.strftime("%Y-%m")))
    univ = pd.DataFrame([(m, f"C{ci:02d}", True, ci < 10) for m in months for ci in range(nc)],
                        columns=["month", "coin", "U_B", "U_Q1"])
    days, _ = m8_tables({"panel": panel, "univ": univ})
    want_days = sorted(start.normalize() + pd.Timedelta(days=r) for r in crash + [late])
    assert list(days["day"]) == want_days and (days["share"] >= 0.15).all()
    t0 = "2023-03-06 03:30"
    data = {"d1": parts[0].drop(columns=["coin", "excluded"]), "tick": "0.0001", "panel": panel, "univ": univ}
    I = inputs_at("C00", t0, data)
    r = level_info("M8", I)
    assert r["aux"]["source"] == "own" and r["aux"]["n_own"] == 7
    assert r["L"] == _ofloor(I["P0"] * math.exp(-float(np.median(D))), "0.0001"), (r, I["P0"])
    J = inputs_at("C00", "2023-03-20 03:30", data)                     # the day after d0 now counts
    assert level_info("M8", J)["aux"]["n_own"] == 8
    # the late coin falls back to the U-Q1 pooled median (oracle: explicit loops over U-Q1 coins)
    zs = []
    for b in parts[:10]:
        cl, lo = b["close"].tolist(), b["low"].tolist()
        for r_ in crash:
            sp = _oracle_sigma(cl, r_ - 1)
            zs.append(math.log(lo[r_] / cl[r_ - 1]) / sp)
    import statistics
    q = statistics.median(zs)
    d19 = parts[19].drop(columns=["coin", "excluded"]).reset_index(drop=True)
    K = inputs_at("C19", t0, {"d1": d19, "tick": "0.0001", "panel": panel, "univ": univ})
    r = level_info("M8", K)
    assert r["aux"]["source"] == "pooled U-Q1" and r["aux"]["n_own"] == 2 and _near(r["aux"]["q"], q, 1e-9)
    assert r["L"] == _ofloor(K["P0"] * math.exp(q * K["sigma30"]), "0.0001")
    assert level_info("M8", inputs_at("C00", t0, {"d1": data["d1"], "tick": "0.0001"}))["status"] == "no_data"
    say("  M8 by hand: market-wide days (>= 10% of U-B at -15%), own median of 7, U-Q1 pooled fallback, past only")


def _t_placebos(say):
    pl = placebos(7.5, 0.04, tick="0.0001", P0=10.0, sigma=0.04)
    assert [s for s, _, _ in pl] == [-1.0, -0.5, 0.5, 1.0]
    for s, L, d in pl:
        assert L == _ofloor(7.5 * math.exp(s * 0.04), "0.0001") and _near(d, math.log(10.0 / L) / 0.04)
    assert placebos(9.9, 0.04, tick="0.01", P0=10.0, sigma=0.04)[3] == (1.0, None, None)    # 9.9 e^0.04 >= P0
    # build_spec's short form placebos(L, atr_pct) has no tick and no delta: it raises (K7; review r1)
    for args, kw in (((7.5, 0.04), {}), ((7.5, 0.04), {"tick": "0.0001"}), ((7.5, 0.04), {"P0": 10.0, "sigma": 0.04}),
                     ((7.5,), {"tick": "0.0001", "P0": 10.0, "sigma": 0.04}),
                     ((7.5, 0.04), {"tick": "0.0001", "P0": 10.0, "sigma": 0.0})):
        try:
            placebos(*args, **kw)
            raise AssertionError((args, kw))
        except ValueError:
            pass
    d1 = _alt_bars("2023-01-02", 70, 10.0, 0.04)
    I = inputs_at("X", "2023-03-06 03:30", {"d1": d1, "tick": "0.0001"})
    L, _ = level("M2", I, k=8)
    pl = placebos(L, inputs=I)
    assert pl == placebos(L, I["atr_pct"], "0.0001", I["P0"], I["sigma30"]) == placebos(L, I["atr_pct"], inputs=I)
    assert all(Lp == _ofloor(L * math.exp(s * I["atr_pct"]), "0.0001") and floor_tick(Lp, "0.0001") == Lp and
               _near(d, math.log(I["P0"] / Lp) / I["sigma30"]) for s, Lp, d in pl)
    say("  placebos by hand: L exp(+-0.5, +-1.0 ATR%) floored, delta recomputed, guard; the short form raises")


# ---------------------------------------------------------------- look-ahead (K4-style) on a synthetic world
_SPOT_LEN = {"d1": DAY_NS, "index_d1": DAY_NS, "h1": HOUR_NS, "m1": 60_000_000_000, "panel": DAY_NS}
_FUT_LEN = {"metrics": 0, "mark1h": HOUR_NS, "perp1h": HOUR_NS}


def _world(seed: int = 7) -> dict:
    """A synthetic coin "SYN" (dip to ~8, rally to ~11 by 2023-10-30) with daily, hourly, 1m and futures frames,
    plus a 24-coin panel with seven market-wide crash days, universes and an empty backstop."""
    rng = np.random.default_rng(seed)
    start, n = pd.Timestamp("2021-06-07", tz="UTC"), 940             # row 875 = Monday 2023-10-30
    days = pd.date_range(start, periods=n, freq="D")
    crash = [120, 190, 260, 330, 400, 470, 540]
    parts = []
    for ci in range(24):
        coin = "SYN" if ci == 0 else f"P{ci:02d}"
        if ci == 0:
            trend = np.interp(np.arange(n), [0, 700, 790, 875, 939], np.log([9.0, 9.0, 8.5, 11.0, 11.0]))
            lp = trend + rng.normal(0, 0.02, n)
        else:
            lp = math.log(float(rng.uniform(0.5, 50))) + np.cumsum(rng.standard_t(4, n) * 0.025)
        c = np.round(np.exp(lp), 4)
        o = np.r_[c[0], c[:-1]]
        hi = np.round(np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.01, n))), 4)
        lo = np.round(np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.01, n))), 4)
        for r in crash:
            lo[r] = round(c[r - 1] * 0.78, 4)
        parts.append(pd.DataFrame({"coin": coin, "open_time": days, "open": o, "high": hi, "low": lo, "close": c,
                                   "volume": 1e3, "quote_volume": 1e3 * c, "trades": 100, "excluded": ""}))
    panel = pd.concat(parts, ignore_index=True)
    panel["day"] = panel["open_time"].dt.tz_localize(None).dt.normalize()
    syn = parts[0].drop(columns=["coin", "excluded"])
    # hourly bars 2023-06-01..2023-11-20 inside each day's range, heavy volume while the price sat at 8.6-9.2
    hrs = []
    for r in range(724, 897):
        o_, c_, h_, l_ = syn.open.iloc[r], syn.close.iloc[r], syn.high.iloc[r], syn.low.iloc[r]
        path = np.clip(np.linspace(o_, c_, 25) * (1 + rng.normal(0, 0.003, 25)), l_, h_)
        t = days[r] + pd.to_timedelta(np.arange(24), unit="h")
        hh = np.round(np.maximum(path[:-1], path[1:]), 4)
        ll = np.round(np.minimum(path[:-1], path[1:]), 4)
        qv = 1e5 * (1 + rng.uniform(0, 1, 24)) + np.where((path[1:] >= 8.6) & (path[1:] <= 9.2), 2e6, 0)
        hrs.append(pd.DataFrame({"open_time": t, "open": np.round(path[:-1], 4), "high": hh, "low": ll,
                                 "close": np.round(path[1:], 4), "quote_volume": qv, "trades": 10}))
    h1 = pd.concat(hrs, ignore_index=True)
    # 1m bars 2023-10-20..2023-11-12 on a 0.0001 grid (plus zero-trade placeholders off the grid)
    m_t = pd.date_range("2023-10-20", "2023-11-12 23:59", freq="1min", tz="UTC")
    hc = h1.set_index("open_time")["close"]
    base = hc.reindex(m_t.floor("h")).to_numpy()
    mp = np.round(base * (1 + rng.normal(0, 0.0005, len(m_t))), 4)
    m1 = pd.DataFrame({"open_time": m_t, "open": mp, "high": mp, "low": mp, "close": mp, "volume": 1.0,
                       "quote_volume": mp, "trades": 1})
    ph = rng.uniform(0, 1, len(m_t)) < 0.01
    m1.loc[ph, ["low", "trades"]] = [1.234567, 0]
    # futures: OI rising through the rally; perpetual VWAP and mark lows follow the hourly bars
    ft = pd.date_range("2023-08-15", "2023-11-12 23:55", freq="5min", tz="UTC")
    oi = 5e6 + np.cumsum(np.maximum(0, rng.normal(50, 400, len(ft))))
    metrics = pd.DataFrame({"create_time": ft, "oi_usd": oi, "oi": oi / 10})
    hh = h1[(h1.open_time >= "2023-08-15") & (h1.open_time < "2023-11-13")]
    perp = pd.DataFrame({"open_time": hh.open_time, "open": hh.open, "high": hh.high, "low": hh.low,
                         "close": hh.close, "volume": 1e3, "quote_volume": 1e3 * (hh.high + hh.low) / 2})
    mark = pd.DataFrame({"open_time": hh.open_time, "open": hh.open, "high": hh.high, "low": hh.low * 0.999,
                         "close": hh.close})
    months = sorted(set(panel["open_time"].dt.strftime("%Y-%m")))
    univ = pd.DataFrame([(m, ("SYN" if ci == 0 else f"P{ci:02d}"), True, ci < 12) for m in months for ci in range(24)],
                        columns=["month", "coin", "U_B", "U_Q1"])
    return {"d1": syn, "h1": h1, "m1": m1, "metrics": metrics, "mark1h": mark.reset_index(drop=True),
            "perp1h": perp.reset_index(drop=True), "panel": panel, "univ": univ,
            "backstop": pd.DataFrame({"month": [], "coin": [], "excluded": []})}


def _perturb(data: dict, spot_cut=None, fut_cut=None, mode: str = "scale") -> dict:
    """K4-style: rows of bars ending after the cut (metrics rows at or after it): prices x 1.5, volumes x 0.5,
    quote volumes x 0.75, open interest x 0.5 (mode scale); dropped (delete); or moved 3 days later (gap)."""
    out = {}
    for key, fr in data.items():
        if key.startswith("_"):
            continue
        cut = spot_cut if key in _SPOT_LEN else fut_cut if key in _FUT_LEN else None
        if cut is None or not isinstance(fr, pd.DataFrame):
            out[key] = fr
            continue
        ln = {**_SPOT_LEN, **_FUT_LEN}[key]
        tcol = "create_time" if key == "metrics" else "open_time"
        t = _ns(fr[tcol])
        c = _utc(cut).value
        after = (t + ln > c) if ln else (t >= c)
        f = fr.copy()
        if mode == "scale":
            for col, mul in (("open", 1.5), ("high", 1.5), ("low", 1.5), ("close", 1.5), ("volume", 0.5),
                             ("quote_volume", 0.75), ("taker_buy_quote", 0.75), ("oi", 0.5), ("oi_usd", 0.5)):
                if col in f:
                    f.loc[after, col] = f.loc[after, col] * mul
        elif mode == "delete":
            f = f[~after]
        elif mode == "gap":
            f.loc[after, tcol] = f.loc[after, tcol] + pd.Timedelta(days=3)
            if "day" in f:
                f.loc[after, "day"] = f.loc[after, "day"] + pd.Timedelta(days=3)
        out[key] = f.reset_index(drop=True)
    return out


def _perturb_inplace(data: dict, spot_cut=None, fut_cut=None, mode: str = "scale") -> None:
    """_perturb's changes made IN PLACE on the frames of `data` (pandas .loc / drop(inplace=True))."""
    for key, fr in data.items():
        cut = spot_cut if key in _SPOT_LEN else fut_cut if key in _FUT_LEN else None
        if key.startswith("_") or cut is None or not isinstance(fr, pd.DataFrame):
            continue
        ln = {**_SPOT_LEN, **_FUT_LEN}[key]
        tcol = "create_time" if key == "metrics" else "open_time"
        t = _ns(fr[tcol])
        c = _utc(cut).value
        after = (t + ln > c) if ln else (t >= c)
        if mode == "scale":
            for col, mul in (("open", 1.5), ("high", 1.5), ("low", 1.5), ("close", 1.5), ("volume", 0.5),
                             ("quote_volume", 0.75), ("oi", 0.5), ("oi_usd", 0.5)):
                if col in fr:
                    fr.loc[after, col] *= mul
        elif mode == "delete":
            fr.drop(index=fr.index[after], inplace=True)
        elif mode == "gap":
            fr.loc[after, tcol] += pd.Timedelta(days=3)
            if "day" in fr:
                fr.loc[after, "day"] += pd.Timedelta(days=3)


def _canon(x):
    if isinstance(x, float):
        return repr(x)
    return x


def _snapshot(coin: str, t0, data, series: str = "spot") -> list:
    """Every input, every variant's level / delta / status, and every placebo of every chart level."""
    I = inputs_at(coin, t0, data, series=series)
    snap = [tuple(_canon(I[k]) for k in ("P0", "sigma30", "n_ret", "atr", "atr_pct", "tick_str", "seg_days", "ok"))]
    for m, p in VARIANTS:
        r = level_info(m, I, **p)
        row = (variant_label(m, p), r["status"], _canon(r["L"]), _canon(r["delta"]))
        if m in CHART and r["L"] is not None:
            row += tuple((s, _canon(L), _canon(d)) for s, L, d in placebos(r["L"], inputs=I))
        snap.append(row)
    return snap


def _t_lookahead(say):
    W = _world()
    must = ("M2 k=8", "M3 p=0.05", "M4 N=90 buffer=0.5", "M4s", "M5a", "M5b", "M6", "M7", "M8")
    n_cmp = 0
    for t0 in (pd.Timestamp("2023-10-30 03:30", tz="UTC"), pd.Timestamp("2023-11-06 03:30", tz="UTC")):
        base = _snapshot("SYN", t0, dict(W))
        got = {row[0]: row for row in base[1:]}
        missing = [v for v in must if got[v][1] != "ok"]
        assert not missing, (t0, [got[v] for v in missing])
        assert base == _snapshot("SYN", t0 + pd.Timedelta(hours=10), dict(W))      # 13:30: the same inputs
        d0 = t0.normalize() - DAY                                                 # Sunday 00:00
        cases = {"after t0 (scale)": _perturb(W, t0, t0, "scale"),
                 "after t0 (delete)": _perturb(W, t0, t0, "delete"),
                 "after t0 (3-day gap)": _perturb(W, t0, t0, "gap"),
                 "spot after d0, futures after d0-1": _perturb(W, d0 + DAY, d0, "scale"),
                 "futures on d0 and later (delete)": _perturb(W, None, d0, "delete"),
                 "futures on d0 and later (scale)": _perturb(W, None, d0, "scale")}
        for name, D in cases.items():
            snap = _snapshot("SYN", t0, D)
            assert snap == base, (t0, name, [(a, b) for a, b in zip(base, snap) if a != b][:3])
            n_cmp += 1
        # the checks have power: spot data of d0 move P0; futures data of d0 - 1 move M7's estimated positions
        sp = _snapshot("SYN", t0, _perturb(W, d0, None, "scale"))
        assert sp[0] != base[0]
        F = _perturb(W, None, d0 - DAY, "scale")
        fu = {row[0]: row for row in _snapshot("SYN", t0, F)[1:]}
        assert all(fu[k] == got[k] for k in got if k != "M7")
        a0 = level_info("M7", inputs_at("SYN", t0, dict(W)))["aux"]
        a1 = level_info("M7", inputs_at("SYN", t0, F))["aux"]
        assert a0 != a1, (a0, a1)
    say(f"  look-ahead: {n_cmp} perturbed worlds leave {len(VARIANTS)} variants, their placebos and the inputs "
        "unchanged (13:30 = 03:30); perturbing d0's spot / d0-1's futures does change them")


def _t_inplace(say):
    """Review r1: a frame changed in place between calls gives the levels of a fresh copy of it (never a mix of new
    prices and old sigma / ATR / segments); an inputs dict stays a consistent snapshot."""
    d1 = _alt_bars("2023-01-02", 70, 10.0, 0.04)
    data = {"d1": d1, "tick": "0.0001"}
    t0 = "2023-03-06 03:30"                                         # d0 = 2023-03-05 = row 62
    I = inputs_at("X", t0, data)
    lv, every = level("M2", I, k=8), levels_all(I)
    assert I["ok"] and inputs_at("X", t0, data)["_T"] is I["_T"]  # unchanged frame: memo hit
    d1.loc[62, ["open", "high", "low", "close"]] *= 1.5             # d0's bar in place: a > 25% open jump
    J, K = inputs_at("X", t0, data), inputs_at("X", t0, {"d1": d1.copy(), "tick": "0.0001"})
    assert J["P0"] == K["P0"] == 15.0 and J["n_ret"] == K["n_ret"] == 0 and not J["ok"] and not K["ok"], (J, K)
    assert level("M2", J, k=8) is None and level("M2", I, k=8) == lv  # the old inputs keep their own table
    assert levels_all(I).equals(every)                              # M4 / M4s read it: same windows and segment
    # every frame of the synthetic world changed in place (scale, delete, gap) gives the snapshot of fresh copies
    W = _world()
    D = {k: (v.copy() if isinstance(v, pd.DataFrame) else v) for k, v in W.items()}
    t0 = pd.Timestamp("2023-10-30 03:30", tz="UTC")
    d0 = t0.normalize() - DAY
    base = _snapshot("SYN", t0, D)                                  # builds (and pins) every table
    n = 0
    for spot_cut, fut_cut, mode, moves in ((d0, d0 - DAY, "scale", True), (t0, t0, "delete", False),
                                           (d0 - 40 * DAY, d0 - 10 * DAY, "gap", True)):
        _perturb_inplace(D, spot_cut, fut_cut, mode)
        F = {k: (v.copy(deep=True) if isinstance(v, pd.DataFrame) else v) for k, v in D.items() if k[0] != "_"}
        got, want = _snapshot("SYN", t0, D), _snapshot("SYN", t0, F)
        assert got == want, (mode, [(a, b) for a, b in zip(got, want) if a != b][:3])
        assert (got != base) == moves, mode
        am = level_info("M7", inputs_at("SYN", t0, D))["aux"]
        assert am == level_info("M7", inputs_at("SYN", t0, F))["aux"], (mode, am)
        base, n = got, n + 1
    # a frame replaced by a new object is seen too
    D["h1"] = D["h1"].assign(quote_volume=D["h1"]["quote_volume"] * np.where(D["h1"].index % 2 == 0, 3.0, 1.0))
    assert level_info("M6", inputs_at("SYN", t0, D)) == level_info("M6", inputs_at("SYN", t0, dict(D, _src=None)))
    say(f"  in place: d0's bar x1.5 in place = the same frame copied; {n} in-place changes of every frame of the "
        "synthetic world (scale, delete, 3-day gap) = fresh copies; old inputs keep their table")


def _t_show(say):
    for day, want in (("2023-03-08", "2023-03-06 03:30"), ("2023-03-06", "2023-03-06 03:30"),
                      ("2023-03-12", "2023-03-06 03:30"), ("2023-03-13", "2023-03-13 03:30"),
                      ("2023-03-06 13:30", "2023-03-06 13:30")):
        assert show_t0(day) == pd.Timestamp(want), (day, show_t0(day))
    assert day0(show_t0("2023-03-08"))[1] == pd.Timestamp("2023-03-05")           # d0 is the Sunday before
    say("  show: a date means the Monday 03:30 placement of its week (Wednesday 2023-03-08 -> Monday 03-06)")


def _grid_oracle(coin: str, d0: pd.Timestamp):
    """Separate code for the real tick check: the window's traded 1m prices read through stinkbid_data.m1 and their
    decimals from Python's shortest repr strings (Decimal). -> (decimals of the unique prices, their counts)."""
    k = sbd.m1(coin, d0 - (TICK_DAYS - 1) * DAY, d0 + DAY, fetch=False)
    k = k[k["trades"].to_numpy() > 0]
    u, c = np.unique(k[["open", "high", "low", "close"]].to_numpy(float).ravel(), return_counts=True)
    dec = np.array([max(0, -Decimal(repr(float(x))).normalize().as_tuple().exponent) for x in u])
    return dec, c


def _check_grid(c_: str, I: dict, levels: list) -> bool:
    """The inferred tick against the real price grid (review r1): tau's grid holds >= 99.9% of the window's prices,
    the 10x coarser grid does not, tick_raw_str is the finest print, and every level and its F1 trigger L - tau lie
    on that grid. Returns whether prints at a finer old tick were set aside."""
    dec, cnt = _grid_oracle(c_, I["d0"])
    n = int(cnt.sum())
    d = next(d for d in range(int(dec.max()) + 1) if 1000 * int(cnt[dec <= d].sum()) >= 999 * n)
    assert I["tick_dec"] == d and I["tick_str"] == _tick_str(d), (c_, I["t0"], I["tick_str"], d)
    assert I["tick_raw_str"] == _tick_str(int(dec.max())) and I["tick_n_prices"] == n, (c_, I["t0"])
    g = Decimal(I["tick_str"])
    for L, nt in levels:
        assert Decimal(repr(L)) % g == 0 and Decimal(repr(tick_value(nt - 1, I["tick_str"]))) % g == 0, (c_, L)
    return d < int(dec.max())


def _t_real(say):
    """Real data (counts and invariants only; no outcome): inputs and levels on a sample of U-Q1 coin-weeks, and the
    look-ahead invariance on real frames."""
    if not any((sbd.OUT / f).exists() for f in ("d1_full_all.parquet", "d1_spot_all.parquet")):
        say("  real data absent: skipped")
        return
    t1 = time.time()
    u = sbd.universes()
    picks = []
    for m in ("2020-03", "2021-05", "2022-01", "2022-11", "2023-08", "2024-08", "2025-10", "2026-06"):
        coins = u[(u.month == m) & u.U_Q1].sort_values("rank").coin.head(5).tolist()
        monday = pd.date_range(m + "-01", periods=7, freq="D")
        monday = monday[monday.dayofweek == 0][0] + pd.Timedelta(hours=3, minutes=30)
        picks += [(c, monday) for c in coins]
    # the reviewer's weeks whose literal smallest step came from 1-2 prints at an older, finer tick (review r1)
    stale = {("BNB", "2021-09-27"): ("0.1", "0.01"), ("ADA", "2022-02-28"): ("0.001", "0.00001"),
             ("APT", "2024-10-21"): ("0.01", "0.0001")}
    picks += [(c, pd.Timestamp(d + " 03:30")) for c, d in stale]
    stat, n_lv, n_grid, n_maj = {}, 0, 0, 0
    for c, t0 in picks:
        I = inputs_at(c, t0)
        if not I["ok"]:
            stat["invalid inputs"] = stat.get("invalid inputs", 0) + 1
            continue
        assert tick_value(floor_n(I["P0"], I["tick_str"]), I["tick_str"]) == I["P0"], (c, t0, I["P0"], I["tick_str"])
        stat["tick " + I["tick_source"]] = stat.get("tick " + I["tick_source"], 0) + 1
        got = []
        for m, p in VARIANTS:
            r = level_info(m, I, **p)
            stat[r["status"]] = stat.get(r["status"], 0) + 1
            if r["status"] == "ok":
                n_lv += 1
                got.append((r["L"], r["n_ticks"]))
                assert r["L"] == tick_value(r["n_ticks"], I["tick_str"]) and 0 < r["L"] < I["P0"]
                if m in CHART:
                    assert BAND[0] <= r["delta"] <= BAND[1]
        if I["tick_source"].startswith("1m"):          # not circular: the tick against the window's real price grid
            n_maj += _check_grid(c, I, got)
            n_grid += 1
        if (c, f"{t0:%Y-%m-%d}") in stale:
            want, raw = stale[(c, f"{t0:%Y-%m-%d}")]
            assert (I["tick_str"], I["tick_raw_str"], I["tick_source"]) == (want, raw, "1m-majority"), (c, t0, I)
    say(f"  real: {len(picks)} U-Q1 coin-weeks, {n_lv} levels on their tick, below P0, chart levels in the band; "
        f"statuses {stat} [{time.time() - t1:.0f}s]")
    say(f"  real tick grid (separate code, Decimal strings of the window's 1m prices): {n_grid} coin-weeks, tau's "
        f"grid holds >= 99.9% of the prices and the 10x coarser one does not; every level and L - tau on it; finer "
        f"old-tick prints set aside in {n_maj} (BNB 2021-09-27 0.1, ADA 2022-02-28 0.001, APT 2024-10-21 0.01)")
    # M7's new open interest recomputed by separate code from the real frames (opened contracts x the hour's VWAP;
    # zero rows missing)
    for coin, t0 in (("BTC", pd.Timestamp("2023-02-06 03:30", tz="UTC")),
                     ("SOL", pd.Timestamp("2022-03-21 03:30", tz="UTC"))):           # SOL: zero rows 03-07..08
        I = inputs_at(coin, t0)
        a = level_info("M7", I)["aux"]
        d0 = t0.normalize() - DAY
        m, p = sbd.metrics(coin), sbd.perp1h(coin)
        lo = max(d0 - M7_DAYS * DAY, pd.Timestamp(I["seg_first_day"], tz="UTC"))
        w = m[(m.create_time >= lo) & (m.create_time < d0)].sort_values("create_time")
        w = w[w["oi"] > 0]
        nz = int(((m.create_time >= lo) & (m.create_time < d0) & (m["oi"] <= 0)).sum())
        tt, oo = w["create_time"].tolist(), w["oi"].tolist()
        vw = {r.open_time: r.quote_volume / r.volume for r in p.itertuples() if r.volume > 0}
        ent, usd = 0, 0.0
        for j in range(1, len(tt)):
            if tt[j] - tt[j - 1] == pd.Timedelta("5min") and oo[j] > oo[j - 1]:
                h = (tt[j] - pd.Timedelta(1, "ns")).floor("h")
                if h in vw and vw[h] > 0:
                    ent, usd = ent + 1, usd + (oo[j] - oo[j - 1]) * vw[h]
        assert a["entries"] == ent and _near(a["new_oi_usd"], usd, 1e-9), (coin, a, ent, usd)
        say(f"  real M7 inputs {coin} {t0:%Y-%m-%d}: {ent} entries, new OI {usd:,.0f} USD = opened contracts x VWAP "
            f"(separate code; {nz} zero rows in the window skipped)")
    # look-ahead on real frames: the coin's frames injected (perturbed after the cutoffs) give the levels of the plain
    # real path. BTC and SOL are placements where M6 and M7 both give a level; NEAR one where they abstain.
    for coin, t0, live in (("BTC", pd.Timestamp("2023-02-06 03:30", tz="UTC"), True),
                           ("SOL", pd.Timestamp("2024-03-04 03:30", tz="UTC"), True),
                           ("NEAR", pd.Timestamp("2023-03-06 03:30", tz="UTC"), False)):
        d0 = t0.normalize() - DAY
        R = {"d1": sbd.d1(coin), "h1": sbd.h1(coin), "m1": sbd.m1(coin, d0 - 8 * DAY, d0 + 10 * DAY, fetch=False),
             "real": True}
        for k in ("metrics", "mark1h", "perp1h"):
            if _real_path(k, coin) is not None:
                R[k] = _load_real(coin, k)
        plain = _snapshot(coin, t0, None)
        given = {row[0]: row[1] for row in plain[1:]}
        assert not live or (given["M6"] == "ok" and given["M7"] == "ok"), given
        assert _snapshot(coin, t0, dict(R)) == plain
        for name, D in (("after t0", _perturb(R, t0, t0)), ("after the cutoffs", _perturb(R, d0 + DAY, d0)),
                        ("after t0, deleted", _perturb(R, t0, t0, "delete")),
                        ("futures on d0 deleted", _perturb(R, None, d0, "delete"))):
            D["real"] = True
            snap = _snapshot(coin, t0, D)
            assert snap == plain, (coin, name, [(a, b) for a, b in zip(plain, snap) if a != b][:3])
        if live:                                         # power: d0's spot bar moves P0; d0 - 1's futures move M7
            D = _perturb(R, d0, None)
            D["real"] = True
            assert _snapshot(coin, t0, D)[0] != plain[0]
            D = _perturb(R, None, d0 - DAY)
            D["real"] = True
            assert level_info("M7", inputs_at(coin, t0, D))["aux"] != level_info("M7", inputs_at(coin, t0))["aux"]
        say(f"  real look-ahead {coin} {t0:%Y-%m-%d %H:%M}: unchanged after t0, after the cutoffs and without d0's "
            f"futures (M6 {given['M6']}, M7 {given['M7']})")


def selftest(real: bool = True):
    t0 = time.time()

    def say(msg):
        _say(t0, msg)

    say("tick inference from decimal strings")
    _t_ticks(say)
    say("floor to the tick; Robinhood rounding")
    _t_floor_rh(say)
    say("inputs at placement")
    _t_inputs(say)
    say("M1, M2, M2a")
    _t_simple(say)
    say("M3 pooled expanding calibration")
    _t_m3(say)
    say("M4, M4f")
    _t_m4(say)
    say("M4s")
    _t_m4s(say)
    say("M5f, M5a, M5b")
    _t_m5(say)
    say("M6")
    _t_m6(say)
    say("M7")
    _t_m7(say)
    say("M8")
    _t_m8(say)
    say("placebos")
    _t_placebos(say)
    say("look-ahead (synthetic world)")
    _t_lookahead(say)
    say("frames changed in place")
    _t_inplace(say)
    say("show: the placement of a date")
    _t_show(say)
    if real:
        say("real data: invariants and look-ahead (no outcome)")
        _t_real(say)
    say(f"selftest passed in {time.time() - t0:.0f}s")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd = argv[0]

    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default
    if cmd == "selftest":
        selftest(real="--no-real" not in argv)
    elif cmd == "show":
        show(argv[1], argv[2], series=opt("--series", "spot"))
    elif cmd == "coverage":
        coverage(opt("--from", "2020-01"), opt("--to", "2026-11"), opt("--universe", "U_Q1"), int(opt("--every", 1)))
    else:
        raise SystemExit(f"unknown command {cmd!r}")


if __name__ == "__main__":
    main()
