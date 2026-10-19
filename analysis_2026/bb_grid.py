"""
Grid overlays for the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md): the "Grid overlays
(one-minute bars; 2024-07..2026-10)" section (G-A "waiting grid", G-B "grid-wrapped tranches", G-0 "always-on grid"),
the R0 table's Costs and Fee scenarios rows (maker / taker / slippage, funding), the Fill conventions, H10 (R0 + G-A
vs R0, grid inventory marked at each 00:00 UTC; grid profit, inventory P&L, fees and per-deployment P&L reported
separately), H11's grid rows, and the Controls' grid clauses: the engine known answer ("G-A's mean P&L is within 2 SE
of zero before fees and negative after fees"), the look-ahead check's grid decisions, the fill audit, and the grid
path check ("on a synthetic driftless 1-second path aggregated to 1-minute bars, the engine's grid P&L matches the
1-second P&L to within 10% of gross grid profit"). Contract: the scratchpad's bb_engine_spec.md, "bb_grid.py".
Data come from analysis_2026/bb_data.py (minutes, coin_hours, bars); R0's trades and tranches from
analysis_2026/bb_engine.simulate_coin.

    python3 -m analysis_2026.bb_grid selftest       # known answers, controls, mechanics-only real-data timing

Public API
  grid_ga(sym, r0_trades, daily_bars=None, cfg_fees="base", start="2024-07-01", end="2026-10-16", sleeve=1.0,
          fill="through", minutes=None, hours=None, mmr=None, lb_rule="current", tick=None) -> dict
  grid_gb(sym, r0_trades, tranches, cfg_fees="base", start=..., end=..., fill="through", minutes=None, hours=None,
          mmr=None, n_levels=20, tick=None, r0_daily_mtm=None) -> dict   (r0_trades may be simulate_coin's result)
  grid_g0(sym, cfg_fees="base", start=..., end=..., sleeve=1.0, fill="through", minutes=None, hours=None, mmr=None,
          tick=None) -> dict
      Each returns
        deployments  one row per grid (G-B: per tranche grid): dep, sym, kind, decided, start, end, reason, lo, hi,
                     n_int (intervals), ratio, q (base units per interval), margin, notional, p_start, p_end,
                     grid_profit, inventory_pnl, fees, funding, net, n_fills, n_round_trips, n_open_through,
                     open_through_gain (choice 6), liquidated, open_at_end, max_notional (max |inventory| x price)
                     (G-B also pos, tranche, tranche_kind, frac, L_used, Q0)
        daily_pnl    Series by UTC day (index = day start): P&L accrued over the day with every grid marked to market
                     at 00:00 UTC, in units of the slot's sleeve (G-A, G-0; `sleeve` scales it) or of the position's
                     maximum notional M (G-B)
        cum          cumulative P&L at each 00:00 UTC (index = the 00:00 instants, first = 0, last = after the
                     window's last minute)
        daily_by_dep long frame (dep, time, cum) of each grid's 00:00 marks (for sizing each deployment by its own
                     sleeve in the account)
        fills        every fill: dep, time (stamp), minute (the 1-minute bar's open), kind (buy, sell, close, init,
                     liq), interval, px (before costs), qty (signed, base units), fee, open_through, cause_time
        fills_audit  violations of the fill audit (must be empty)
        log          counts
      G-B also returns trades (simulate_coin's trades of EVERY R0 position: wrapped ones with ret = the grids' net
      P&L per M, ret_r0 = R0's, gb_wrapped True; the others - S11 shorts, positions outside the window, ... - passed
      through unchanged, gb_wrapped False, gb_skip = why) and daily_mtm (engine format: pos, time, mtm, margin,
      notional, sym; R0's own rows for passed-through positions), so that bb_engine.assemble builds the R0 + G-B
      account.
  hours (every overlay): a coin_hours-shaped frame, "disk" (bb_data.coin_hours), "none", or None = "disk" when the
      minutes are loaded from bb_data and "none" when minutes are injected (injected data are self-contained; a
      warning names a bb_data coin run this way). Hours that disagree with the minutes in price level raise. G-A
      with injected minutes needs daily_bars= or hours= (a frame, or "disk").
  merge_ga(r0_result, ga, pos_offset=1_000_000) -> dict
      simulate_coin's result plus one pseudo-position per G-A deployment (L_used = 1, ret = net P&L per sleeve:
      grid_ga's amounts divided by its logged sleeve), so that bb_engine.assemble(...) sizes each grid at the slot's
      sleeve of its deployment day (rule 11 included) and gives the R0 + G-A account for H10.
  run_grid(minutes, levels, q, ..., hours=None) -> dict      one grid on given 1-minute bars (the kernel; tests)
  path_check(...) -> dict                                     the pre-registered grid path check
  selftest()

Mechanics (pre-registration text in quotes where it decides)
- Bars: bb_data.minutes() (perpetual, prices on the tick grid; trades == 0 = outage). Hours (bb_data.coin_hours) give
  the funding prints, the hourly mark-price high / low / open, `tradable` and `perp_end` (injected inputs: see hours
  above; injected minutes never pick up the coin's real hours or daily bars from disk unless hours="disk").
- Geometry ("a neutral geometric perpetual grid over [lower band, upper band] of that close; spacing max(0.5%, 4 x the
  0.04% round-trip maker fee)"): G = floor(ln(hi / lo) / ln(1.005)) intervals, levels lo x r^i with
  r = (hi / lo)^(1 / G) >= 1.005, i = 0..G, rounded to the perpetual's tick (bb_data.TICK). G-B: 20 levels from S
  to TP (19 intervals). G-0: [0.9 P, 1.1 P] around the deployment minute's open, 0.5% spacing (40 intervals).
- Size ("isolated margin E_sleeve/3 at 3x, so full one-sided inventory is E_sleeve of notional"): q = E_sleeve /
  (G x P_dep) base units per interval; margin E_sleeve / 3. G-B: q = tranche notional / (19 x fill price), margin =
  tranche notional / L_used.
- Orders: each interval [L_i, L_i+1] holds one order, a buy at L_i (flat interval) or a sell at L_i+1 (holding
  interval); a fill flips the interval and places the opposite order. At deployment the level nearest the price gets
  no order, every level below gets a buy, every level above a sell (a neutral grid starts flat; a long-mode G-B grid
  buys at its start the inventory of the intervals above the price).
- Fills ("on 1-minute bars ... Path O->L->H->C if the close is nearer the high, else O->H->L->C. A resting order
  fills only when the path trades strictly through its level ... An order placed during a minute cannot fill in that
  minute, and nothing fills in trades == 0 minutes. Each fill pays the 0.02% maker fee"): an eligible buy fills at its
  level when the path trades strictly below it (fill="touch": at or below), a sell strictly above. Fill price = the
  level, or the minute's open when the minute opens beyond the level (open_through; see choice 6).
- Funding ("charged on net inventory at each print"): bb_data's funding of an hour x inventory x the mark open of that
  hour (the minute's open where the mark is missing), at the hour's open, owed by the inventory held just before it.
- Liquidation ("when the hourly mark-price high or low takes the grid's equity below its maintenance margin. The grid
  then loses its margin"): see choice 8; P&L = -margin, stamped at the hour's close.
- G-A ends ("(a) R0's entry hour arrives: inventory is closed at that hour's open at taker fee plus slippage; (b) a
  daily close falls below the lower band: closed at the next 1-minute open at the same cost; (c) 14 days pass: closed
  at the same cost, and redeployed only if the condition still holds"), a liquidation, or the window's end (marked at
  the last minute's close without closing costs, as R0's window-end rule).
- Costs: maker be.MAKER[fees] per grid fill; closes (and G-B's initial inventory) pay be.TAKER[fees] + slippage
  (0.02% BTC / ETH, 0.07% others; 0 in the "zero" scenario), as bb_engine. Fee scenarios "base", "vip", "zero".
- Time stamps (look-ahead control): a grid fill at its minute's close; a close or deployment at a minute's open at
  that open; a liquidation at the hour's close; 00:00 marks at 00:00. Every decision uses only data complete at its
  stamp: a deployment uses the daily bar known at its 00:00 close and the deployment minute's open; a liquidation the
  hour's mark bar.

Coding choices the pre-registration leaves open (most literal reading taken)
1. Geometry: the levels sit exactly on the range ends and the interval count is the largest whose ratio is at least
   1.005 ("spacing max(0.5%, ...)" read as a floor, as close to 0.5% as an integer count allows). A range narrower
   than two intervals (hi / lo < 1.005^2) deploys no grid (logged). Spacing is 0.5% in every fee scenario: the
   pre-registration fixes its fee term at the base tier (4 x 0.04% = 0.16%), so the 0.5% floor binds.
2. Size: a constant base quantity per interval (Binance futures grids' fixed quantity per order), computed at the
   deployment minute's open, so the full one-sided inventory (all G intervals filled) is E_sleeve at that price.
3. Initial orders: Binance's convention, no order at the grid line nearest the current price (log distance).
4. "An order placed during a minute cannot fill in that minute" applies to the order placed after a fill; the orders
   placed at a deployment (at a minute's open, before its trading) may fill in that minute.
5. With one order per interval and no same-minute refill, which orders fill in a minute depends only on the minute's
   range (eligible buys with level > low, sells with level < high; touch >= / <=), not on the path; the pre-registered
   path orders the fills in time (the liquidation snapshot, G-B's stop cut). Ties (close equidistant from high and
   low) take O->H->L->C; a tie is a difference of the two distances within 1e-9 x the close (TIE_REL), so exact
   decimal ties on the tick grid are not misrouted by float rounding (1e-9 is below one 1-minute tick of every coin:
   BTC's 0.01 at 126,000 is 8e-8; float error is ~1e-15).
6. A minute that opens beyond an eligible order's level (the order was placed in the previous minute after the price
   had already passed it, or the price gapped between minutes, e.g. after an outage) fills that order at the minute's
   open: the order is marketable when it becomes eligible. The open lies inside the bar's range as the fill audit
   requires; the level would not (F1's "price = P" assumes the price trades through P while the order rests). The
   maker fee is kept (the pre-registration: "each fill pays the 0.02% maker fee"). Counted as n_open_through; the
   price improvement these fills got over their levels is reported per grid as open_through_gain (P&L units), an
   upper bound on what this choice adds relative to filling them at the level. On a martingale the choice is fair
   (the order fills at the price at which it becomes eligible); on real BTC 2024-07..2026-10 every open-through fill
   was such a deferred refill (none followed an outage).
7. Funding: a grid started at an hour's open does not pay that hour's print; one closed at it does (bb_engine's
   rule). No funding where bb_data has none (synthetic frames without hours: 0, and the mark falls back to last price).
8. Liquidation: checked at the close of every hour with a live minute while the grid lives. The grid's equity
   (margin + realised cash + inventory x price - fees - funding) is evaluated at the hour's mark low with the grid's
   state at the moment its last price reached the hour's low (and at the hour's end), and at the mark high with the
   state at the hour's high (and at its end); last-price extremes where the mark is missing. A breach of mmr x
   |inventory| x price (bb_data.MMR) liquidates at the hour's close and the deployment's P&L is -margin. An hour in
   which a G-B grid is stopped is not checked (the stop comes first, as in bb_engine).
9. G-A's deployment test at the 00:00 close of daily signal bar t (bb_data.bars "1d", "sig": spot where spot trades,
   as R0's signal): warm (60 completed daily bars of the segment, R0's warm-up), C_t <= UB_t of BB(20, 2) (population
   sigma, restarted at `seg` changes, as bb_engine) and C_t >= 0.95 x the highest signal high of the 60 days ending at
   the close (R0's look-back); "the slot is flat": no R0 position with entry1_time <= T < exit_time. The grid is
   not deployed if an R0 entry falls between the close and the deployment minute (outage delay).
10. End (b) "a daily close falls below the lower band": the close's own BB(20, 2) lower band (lb_rule="current"; the
   deployment test's "at or below the upper band" is likewise the band at that close). lb_rule="deploy" (the grid's
   own floor) is the other reading; it is not pre-registered and needs the orchestrator's ruling to be used.
11. End (c): at the first daily close at least 14 days after the deployment's decision close. After an end by (b) or
   (c) the deployment test runs at the same close and a new grid deploys at the same open ("redeployed only if the
   condition still holds"; applied to (b) too, since the test runs at every close). After a liquidation the test
   resumes at the first close at or after it; after an R0 entry, at the first close after it (when flat).
12. Deployments and closes execute at the first minute with trades > 0 at or after their scheduled time.
13. 00:00 marks: equity at 00:00 with the inventory valued at the 23:59 close, after the 23:00 hour's liquidation
   check and the 00:00 funding print, before any close or deployment at the 00:00 open.
14. G-B: "20 levels" = 20 price levels from S to TP (19 intervals), geometric; q makes the fully loaded grid (at S)
   the tranche's notional at its fill price; the initial inventory pays the tranche's taker fee and slippage, at
   R0's fill price. Every tranche grid of a position ends at the position's final exit: a stop at R0's stop minute,
   with the path cut where it first reaches S (the grid's buys above S fill on the way down), closing at R0's stop
   price ("at S it is fully loaded and stopped out"); a trend exit at that hour's open ("the midline exit closes
   it"); a window end is marked; a delisting, liquidation or TP-all exit closes at R0's exit price (the minute's close
   where that price is outside the minute's range). An R0 exit whose bar opens after the window's last minute (R0
   simulated past the G-B window) is not used: every tranche grid is marked at the window's last live minute
   (Windows: "a trade still open at a window's end is marked at the last hourly close"; open_at_end, window_end);
   tranches filled after that minute are not wrapped. R0's 50% TP is not applied: the grid sells out to TP by its
   own levels ("at TP it is sold out"). Short positions (S11) are not wrapped; they and every other unwrapped
   position stay in the output unchanged (R0's ret and 00:00 marks), so the R0 + G-B account keeps their P&L.
15. G-0: "+/-10%" = [0.9 P, 1.1 P] around the deployment minute's open; G-A's spacing, margin and leverage;
   "re-centred weekly" at each Monday 00:00 UTC (moneyline_ref's week): closed at that open with taker fee and
   slippage and redeployed at the same open; "always-on": after a liquidation it redeploys at the next live minute.
16. Grid profit (the platforms' "grid profit") = the sum over completed round trips (an interval returning to its
   initial state) of q x (sell price - buy price); inventory P&L = gross P&L - grid profit.
17. A grid open at a `perp_end` bar is closed at that bar's close with taker fee and slippage (none of the six
   one-minute coins delisted; implemented for completeness and checked only on the self-test's synthetic data).
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import bb_data as bd  # noqa: E402
from analysis_2026 import bb_engine as be  # noqa: E402

H_NS = 3_600_000_000_000
MIN_NS = 60_000_000_000
DAY_NS = 24 * H_NS
INF_NS = np.iinfo(np.int64).max

GRID_START = "2024-07-01"
GRID_END = "2026-10-16"
MAKER_RT_BASE = 2 * be.MAKER["base"]          # "the 0.04% round-trip maker fee"
SPACING = max(0.005, 4 * MAKER_RT_BASE)       # "spacing max(0.5%, 4 x the 0.04% round-trip maker fee)" = 0.5%
GA_N, GA_K = 20, 2.0                          # the bands of R0's signal
GA_NEAR = 0.95                                # "within 5% of the 60-day high"
GA_HI_DAYS = 60
GA_WARM = 60                                  # R0's warm-up (completed daily bars)
GA_DAYS = 14                                  # "(c) 14 days pass"
GRID_LEV = 3.0                                # "isolated margin E_sleeve/3 at 3x"
GB_LEVELS = 20                                # "G-B ... [S, TP], 20 levels"
G0_HALF = 0.10                                # "G-0 ... +/-10%"

# fill kinds
K_BUY, K_SELL, K_CLOSE, K_INIT, K_LIQ = 0, 1, 2, 3, 4
KIND_NAMES = np.array(["buy", "sell", "close", "init", "liq"], dtype=object)
# end modes of one deployment
E_OPEN, E_MARK, E_STOP, E_CLOSE = 0, 1, 2, 3
# deployment status
ST_OK, ST_LIQ, ST_MARK = 0, 1, 2
# state slots
S_Q, S_C, S_FEES, S_FUND, S_GP, S_NRT, S_NF, S_NOT, S_MAXX, S_NROW = range(10)
NST = 10
# hour snapshot slots: running low / high of the hour and the grid's state when the price reached them
H_LO, H_HI, H_QLO, H_CLO, H_FLO, H_QHI, H_CHI, H_FHI, H_LIVE = range(9)
NHS = 9


# ============================================================================ numba kernel
@njit(cache=True)
def _fill(i, side, px, m, ot, q, h, h0, placed, opx, st, maker, FI, FF):
    """Fill interval i's order (side +1 buy at its lower level, -1 sell at its upper level) at px in minute m."""
    n = int(st[S_NROW])
    cost = q * px * maker
    if n < FI.shape[0]:
        FI[n, 0] = m
        FI[n, 1] = K_BUY if side > 0 else K_SELL
        FI[n, 2] = i
        FI[n, 3] = placed[i]
        FI[n, 4] = ot
        FF[n, 0] = px
        FF[n, 1] = side * q
        FF[n, 2] = cost
    st[S_NROW] = n + 1
    st[S_Q] += side * q
    st[S_C] -= side * q * px
    st[S_FEES] += cost
    st[S_NF] += 1
    if ot:
        st[S_NOT] += 1
    newh = 1 if side > 0 else 0
    if newh == h0[i]:                                   # the interval is back in its initial state: a round trip
        if side > 0:
            st[S_GP] += q * (opx[i] - px)               # opened by a sell, closed by this buy
        else:
            st[S_GP] += q * (px - opx[i])               # opened by a buy, closed by this sell
        st[S_NRT] += 1
    else:
        opx[i] = px
    h[i] = newh
    placed[i] = m                                       # the opposite order, placed during minute m


@njit(cache=True)
def _down(a, b, m, lv, q, h, h0, placed, opx, st, maker, touch, FI, FF):
    """Path segment a -> b < a: eligible buys at levels in (b, a] ([b, a] touch), highest first."""
    G = lv.shape[0] - 1
    i = np.searchsorted(lv, a, side="right") - 1
    if i > G - 1:
        i = G - 1
    while i >= 0:
        L = lv[i]
        if touch:
            if L < b:
                break
        elif L <= b:
            break
        if h[i] == 0 and placed[i] < m:
            _fill(i, 1, L, m, 0, q, h, h0, placed, opx, st, maker, FI, FF)
        i -= 1


@njit(cache=True)
def _up(a, b, m, lv, q, h, h0, placed, opx, st, maker, touch, FI, FF):
    """Path segment a -> b > a: eligible sells at levels in [a, b) ([a, b] touch), lowest first."""
    G = lv.shape[0] - 1
    j = np.searchsorted(lv, a, side="left")
    if j < 1:
        j = 1
    while j <= G:
        L = lv[j]
        if touch:
            if L > b:
                break
        elif L >= b:
            break
        i = j - 1
        if h[i] == 1 and placed[i] < m:
            _fill(i, -1, L, m, 0, q, h, h0, placed, opx, st, maker, FI, FF)
        j += 1


@njit(cache=True)
def _open_through(o, m, lv, q, h, h0, placed, opx, st, maker, touch, FI, FF):
    """Eligible orders the minute opens beyond (choice 6): filled at the open."""
    G = lv.shape[0] - 1
    i = np.searchsorted(lv, o, side="left") if touch else np.searchsorted(lv, o, side="right")
    while i <= G - 1:
        if h[i] == 0 and placed[i] < m:
            _fill(i, 1, o, m, 1 if lv[i] != o else 0, q, h, h0, placed, opx, st, maker, FI, FF)
        i += 1
    jmax = (np.searchsorted(lv, o, side="right") - 1) if touch else (np.searchsorted(lv, o, side="left") - 1)
    if jmax > G:
        jmax = G
    j = 1
    while j <= jmax:
        i = j - 1
        if h[i] == 1 and placed[i] < m:
            _fill(i, -1, o, m, 1 if lv[j] != o else 0, q, h, h0, placed, opx, st, maker, FI, FF)
        j += 1


@njit(cache=True)
def _seg(a, b, m, lv, q, h, h0, placed, opx, st, maker, touch, cut_on, cut, FI, FF):
    """One monotone path segment; returns 1 if the G-B stop cut was reached on it."""
    if b < a:
        if cut_on and b <= cut:
            _down(a, cut, m, lv, q, h, h0, placed, opx, st, maker, touch, FI, FF)
            return 1
        _down(a, b, m, lv, q, h, h0, placed, opx, st, maker, touch, FI, FF)
    elif b > a:
        _up(a, b, m, lv, q, h, h0, placed, opx, st, maker, touch, FI, FF)
    return 0


@njit(cache=True)
def _snap(k, jl, lo, hi, st, hs):
    """After path vertex k: record the grid's state at the hour's running low / high (liquidation snapshot)."""
    if k == jl and lo < hs[H_LO]:
        hs[H_LO] = lo
        hs[H_QLO] = st[S_Q]
        hs[H_CLO] = st[S_C]
        hs[H_FLO] = st[S_FEES] + st[S_FUND]
    if k == 3 - jl and hi > hs[H_HI]:
        hs[H_HI] = hi
        hs[H_QHI] = st[S_Q]
        hs[H_CHI] = st[S_C]
        hs[H_FHI] = st[S_FEES] + st[S_FUND]


TIE_REL = 1e-9         # choice 5: |(c - lo) - (hi - c)| within 1e-9 x c is a tie (below any coin's 1m tick)


@njit(cache=True)
def _nearer_high(hi, lo, c):
    """The pre-registered path rule's test "the close is nearer the high" (then O->L->H->C). A difference of the two
    distances within TIE_REL x |c| is an exact tie on the tick grid (float rounding of decimal prices only) and
    takes O->H->L->C (choice 5)."""
    return (c - lo) - (hi - c) > TIE_REL * abs(c)


@njit(cache=True)
def _minute(m, o, hi, lo, c, lv, q, h, h0, placed, opx, st, hs, maker, touch, cut_on, cut, FI, FF):
    """Process one live minute; returns 1 if the G-B stop cut was reached (the rest of the path is not traded)."""
    if cut_on and o <= cut:
        return 1
    _open_through(o, m, lv, q, h, h0, placed, opx, st, maker, touch, FI, FF)
    if _nearer_high(hi, lo, c):                         # close nearer the high: O -> L -> H -> C
        x1 = lo
        x2 = hi
        jl = 1
    else:                                               # O -> H -> L -> C (ties included)
        x1 = hi
        x2 = lo
        jl = 2
    if _seg(o, x1, m, lv, q, h, h0, placed, opx, st, maker, touch, cut_on, cut, FI, FF):
        return 1
    _snap(1, jl, lo, hi, st, hs)
    if _seg(x1, x2, m, lv, q, h, h0, placed, opx, st, maker, touch, cut_on, cut, FI, FF):
        return 1
    _snap(2, jl, lo, hi, st, hs)
    if _seg(x2, c, m, lv, q, h, h0, placed, opx, st, maker, touch, cut_on, cut, FI, FF):
        return 1
    return 0


@njit(cache=True)
def _close_all(m, px, st, tk, FI, FF):
    Qv = st[S_Q]
    if Qv == 0.0:
        return
    n = int(st[S_NROW])
    cost = abs(Qv) * px * tk
    if n < FI.shape[0]:
        FI[n, 0] = m
        FI[n, 1] = K_CLOSE
        FI[n, 2] = -1
        FI[n, 3] = -1
        FI[n, 4] = 0
        FF[n, 0] = px
        FF[n, 1] = -Qv
        FF[n, 2] = cost
    st[S_NROW] = n + 1
    st[S_C] += Qv * px
    st[S_FEES] += cost
    st[S_Q] = 0.0


@njit(cache=True)
def _hs_reset(hs):
    hs[H_LO] = np.inf
    hs[H_HI] = -np.inf
    hs[H_QLO] = 0.0
    hs[H_CLO] = 0.0
    hs[H_FLO] = 0.0
    hs[H_QHI] = 0.0
    hs[H_CHI] = 0.0
    hs[H_FHI] = 0.0
    hs[H_LIVE] = 0.0


@njit(cache=True)
def _liq_check(margin, mmr, Qs, Cs, Fs, px, short):
    if short:
        if Qs < 0.0 and margin + Cs + Qs * px - Fs < mmr * (-Qs) * px:
            return True
    elif Qs > 0.0 and margin + Cs + Qs * px - Fs < mmr * Qs * px:
        return True
    return False


@njit(cache=True)
def _run(mo, mh, ml, mc, mlive, mhour, hfirst, hlast, dfirst, hmlo, hmhi, hmop, hfund,
         lv, q, h0, Q0, C0, cost0, margin, mmr, maker, tk, touch, m0, m_end, end_mode, end_px, cut, FI, FF, MK):
    """One grid deployment from minute m0 (its orders placed at m0's open) to m_end (see the end modes), on the
    minute arrays; hourly arrays (mark low / high / open, funding) indexed by mhour. Returns (state, status, last
    minute, liquidation price, number of 00:00 marks). Fills go to FI / FF (minute, kind, interval, placement minute,
    open_through; px, qty, fee), marks to MK (minute, P&L, |inventory| x price)."""
    G = lv.shape[0] - 1
    h = h0.copy()
    placed = np.full(G, m0 - 1, np.int64)
    opx = np.zeros(G)
    st = np.zeros(NST)
    st[S_Q] = Q0
    st[S_C] = C0
    st[S_FEES] = cost0
    hs = np.zeros(NHS)
    _hs_reset(hs)
    nmk = 0
    status = ST_OK
    m_stop = m_end
    liq_px = np.nan
    for m in range(m0, m_end + 1):
        hr = mhour[m]
        if m > m0:
            if hfirst[m]:
                _hs_reset(hs)
                f = hfund[hr]
                if f != 0.0 and st[S_Q] != 0.0:                 # funding print at the hour's open
                    pm = hmop[hr]
                    if not (pm == pm):
                        pm = mo[m]
                    st[S_FUND] += f * st[S_Q] * pm
            if dfirst[m]:                                       # 00:00 mark at the previous minute's close, after
                if nmk < MK.shape[0]:                           # the 00:00 funding print (choice 13, bb_engine)
                    MK[nmk, 0] = m
                    MK[nmk, 1] = st[S_C] + st[S_Q] * mc[m - 1] - st[S_FEES] - st[S_FUND]
                    MK[nmk, 2] = abs(st[S_Q]) * mc[m - 1]
                nmk += 1
        if m == m_end and end_mode == E_OPEN:
            _close_all(m, mo[m], st, tk, FI, FF)
            m_stop = m
            break
        cut_on = end_mode == E_STOP and m == m_end
        if mlive[m]:
            hs[H_LIVE] = 1.0
            _minute(m, mo[m], mh[m], ml[m], mc[m], lv, q, h, h0, placed, opx, st, hs, maker, touch, cut_on, cut,
                    FI, FF)
            x = abs(st[S_Q]) * mc[m]
            if x > st[S_MAXX]:
                st[S_MAXX] = x
        if cut_on:
            px = end_px
            if mlive[m]:
                if px < ml[m]:
                    px = ml[m]
                if px > mh[m]:
                    px = mh[m]
            _close_all(m, px, st, tk, FI, FF)
            m_stop = m
            break
        if hlast[m] and hs[H_LIVE] > 0.0:                       # liquidation check at the hour's close
            plo = hmlo[hr]
            if not (plo == plo):
                plo = hs[H_LO]
            phi = hmhi[hr]
            if not (phi == phi):
                phi = hs[H_HI]
            Fn = st[S_FEES] + st[S_FUND]
            lq = 0
            if _liq_check(margin, mmr, hs[H_QLO], hs[H_CLO], hs[H_FLO], plo, False) or \
                    _liq_check(margin, mmr, st[S_Q], st[S_C], Fn, plo, False):
                lq = 1
                liq_px = plo
            elif _liq_check(margin, mmr, hs[H_QHI], hs[H_CHI], hs[H_FHI], phi, True) or \
                    _liq_check(margin, mmr, st[S_Q], st[S_C], Fn, phi, True):
                lq = 1
                liq_px = phi
            if lq:
                n = int(st[S_NROW])
                if n < FI.shape[0]:
                    FI[n, 0] = m
                    FI[n, 1] = K_LIQ
                    FI[n, 2] = -1
                    FI[n, 3] = -1
                    FI[n, 4] = 0
                    FF[n, 0] = liq_px
                    FF[n, 1] = -st[S_Q]
                    FF[n, 2] = 0.0
                st[S_NROW] = n + 1
                status = ST_LIQ
                m_stop = m
                break
        if m == m_end:
            if end_mode == E_CLOSE:
                px = end_px
                if mlive[m] and (px < ml[m] or px > mh[m]):
                    px = mc[m]
                _close_all(m, px, st, tk, FI, FF)
            elif end_mode == E_MARK:
                status = ST_MARK
            m_stop = m
            break
    return st, status, m_stop, liq_px, nmk


# ============================================================================ data preparation
def _idx(ix) -> pd.DatetimeIndex:
    ix = pd.DatetimeIndex(ix)
    ix = ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")
    return ix.as_unit("ns")


def _ns(x) -> np.ndarray:
    return _idx(x).asi8


def _ts(v) -> pd.Timestamp:
    return pd.Timestamp(int(v), tz="UTC")


HOURS_MISMATCH_REL = 0.01     # an hour whose traded close differs from its last live minute's close by more than this


def _hours_mode(minutes, hours) -> str:
    """How _prep obtains the hourly inputs (mark, funding, tradable, perp_end): "frame" (injected), "disk"
    (bb_data.coin_hours), or "none" (no funding, mark = last price). Default: "disk" when the minutes are loaded
    from bb_data too, "none" when the minutes are injected (injected data are self-contained: a synthetic or
    perturbed run never mixes in the coin's real mark prices and funding); hours="disk" / "none" say so explicitly."""
    if isinstance(hours, pd.DataFrame):
        return "frame"
    if hours is None:
        return "disk" if minutes is None else "none"
    if isinstance(hours, str) and hours in ("disk", "none"):
        return hours
    raise ValueError("hours must be a coin_hours-shaped DataFrame, 'disk', 'none' or None")


def _prep(sym: str, start, end, minutes: pd.DataFrame | None = None, hours=None) -> dict:
    """Minute arrays of [start, end] (bb_data.minutes or the injected frame) and the hourly arrays the kernel needs
    (see _hours_mode: the injected hours, bb_data.coin_hours, or none: no funding, mark = last price). Hours are
    checked against the minutes: more than max(2, 0.1%) of the compared hours with a traded close more than 1% from
    the hour's last live minute's close raises (mixed or differently perturbed inputs)."""
    a, b = bd._utc(start), bd._utc_end(end)
    hmode = _hours_mode(minutes, hours)
    if hmode == "none" and minutes is not None and hours is None and sym.upper() in bd.MMR:
        warnings.warn(f"bb_grid: {sym} minutes injected without hours: no funding, mark price = last price; pass "
                      f"hours=<frame> or hours='disk' to use hourly mark and funding inputs", stacklevel=3)
    if minutes is None:
        minutes = bd.minutes(sym, a, b)
    else:
        mi = _idx(minutes.index)
        keep = np.ones(len(mi), bool)
        if a is not None:
            keep &= mi >= a
        if b is not None:
            keep &= mi <= b
        minutes = minutes[keep]
    if not len(minutes):
        raise ValueError(f"{sym}: no 1-minute bars in {start} .. {end}")
    mt = _ns(minutes.index)
    if len(mt) > 1 and not (np.diff(mt) > 0).all():
        raise ValueError(f"{sym}: minutes must be sorted and unique")
    if (mt % MIN_NS).any():
        raise ValueError(f"{sym}: minute open times must be whole minutes")
    mo, mh, ml, mc = (minutes[c].to_numpy(np.float64) for c in bd.PX)
    tr = minutes["trades"].to_numpy(np.int64) if "trades" in minutes.columns else np.ones(len(mt), np.int64)
    hours_src = {"frame": "injected", "disk": "bb_data", "none": "none"}[hmode]
    if hmode == "disk":
        hours = bd.coin_hours(sym.upper(), pd.Timestamp(mt[0] - mt[0] % H_NS, tz="UTC"),
                              pd.Timestamp(mt[-1], tz="UTC"))
    elif hmode == "none":
        hours = None
    hour_ns = mt - mt % H_NS
    hu, hinv = np.unique(hour_ns, return_inverse=True)
    nh = len(hu)
    hmlo = np.full(nh, np.nan)
    hmhi = np.full(nh, np.nan)
    hmop = np.full(nh, np.nan)
    hfund = np.zeros(nh)
    htrad = np.ones(nh, bool)
    hpend = np.zeros(nh, bool)
    missing_hours = 0
    if hours is not None and len(hours):
        hix = _ns(hours.index)
        pos = np.searchsorted(hix, hu)
        ok = (pos < len(hix)) & (hix[np.clip(pos, 0, len(hix) - 1)] == hu)
        missing_hours = int((~ok).sum())
        p = pos[ok]
        for col, arr in (("mark_low", hmlo), ("mark_high", hmhi), ("mark_open", hmop)):
            if col in hours.columns:
                arr[ok] = hours[col].to_numpy(np.float64)[p]
        if "funding" in hours.columns:
            hfund[ok] = np.nan_to_num(hours["funding"].to_numpy(np.float64)[p])
        if "tradable" in hours.columns:
            htrad[ok] = hours["tradable"].to_numpy(bool)[p]
        if "perp_end" in hours.columns:
            hpend[ok] = hours["perp_end"].to_numpy(bool)[p]
    mhour = hinv.astype(np.int64)
    mlive = (tr > 0) & htrad[mhour]
    hfirst = np.r_[True, mhour[1:] != mhour[:-1]]
    hlast = np.r_[mhour[1:] != mhour[:-1], True]
    hours_mismatch = 0
    if hours is not None and len(hours) and "close" in hours.columns:
        # price-level consistency of the hourly inputs with the minutes: the hour's traded close vs the close of the
        # hour's last minute (live), over hours traded in both (real data agree exactly on all six 1-minute coins)
        lm = np.flatnonzero(hlast & (tr > 0))
        hh = mhour[lm]
        okh = ok[hh]
        lm, hh = lm[okh], hh[okh]
        hc = hours["close"].to_numpy(np.float64)[pos[hh]]
        htr = hours["trades"].to_numpy(np.int64)[pos[hh]] if "trades" in hours.columns else np.ones(len(hh), np.int64)
        cmp_ = (htr > 0) & np.isfinite(hc) & (mc[lm] > 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.abs(hc[cmp_] / mc[lm][cmp_] - 1.0)
        hours_mismatch = int((rel > HOURS_MISMATCH_REL).sum())
        if hours_mismatch > max(2, 0.001 * int(cmp_.sum())):
            raise ValueError(f"{sym}: hours ({hours_src}) and minutes disagree in price level: {hours_mismatch} of "
                             f"{int(cmp_.sum())} hours have a close more than {HOURS_MISMATCH_REL:.0%} from the "
                             f"hour's last minute close (inject hours built from the same prices)")
    dk = mt // DAY_NS
    dfirst = np.r_[True, dk[1:] != dk[:-1]]
    live_idx = np.flatnonzero(mlive)
    return {"sym": sym, "a": a, "b": b, "mt": mt, "mo": mo, "mh": mh, "ml": ml, "mc": mc, "tr": tr,
            "mlive": mlive, "mhour": mhour, "hfirst": hfirst, "hlast": hlast, "dfirst": dfirst, "hu": hu,
            "hmlo": hmlo, "hmhi": hmhi, "hmop": hmop, "hfund": hfund, "hpend": hpend, "live_idx": live_idx,
            "M": len(mt), "hours_src": hours_src, "missing_hours": missing_hours, "hours_mismatch": hours_mismatch}


def _first_live_ge(A: dict, t_ns: int) -> int:
    """Index of the first live minute whose open time is >= t_ns, or -1."""
    i = int(np.searchsorted(A["mt"], t_ns, side="left"))
    j = int(np.searchsorted(A["live_idx"], i, side="left"))
    return int(A["live_idx"][j]) if j < len(A["live_idx"]) else -1


def _last_live_lt(A: dict, t_ns: int) -> int:
    """Index of the last live minute whose open time is < t_ns, or -1."""
    i = int(np.searchsorted(A["mt"], t_ns, side="left")) - 1
    j = int(np.searchsorted(A["live_idx"], i, side="right")) - 1
    return int(A["live_idx"][j]) if j >= 0 else -1


def _perp_end_closes(A: dict) -> np.ndarray:
    """Close times (hour open + 1 h) of perp_end hours inside the minute span."""
    return A["hu"][A["hpend"]] + H_NS


def _fees(sym: str, scen: str) -> tuple[float, float]:
    """(maker, taker + slippage) of a fee scenario, as bb_engine (R0 Costs and Fee scenarios rows)."""
    if scen not in be.TAKER:
        raise ValueError(f"cfg_fees must be one of {list(be.TAKER)}")
    if scen == "zero":
        return 0.0, 0.0
    slip = be.SLIP_MAJOR if sym.upper() in be.MAJORS else be.SLIP_OTHER
    return be.MAKER[scen], be.TAKER[scen] + slip


def _touch(fill: str) -> bool:
    if fill not in ("through", "touch"):
        raise ValueError("fill must be 'through' (primary) or 'touch' (optimistic bound)")
    return fill == "touch"


def _tick(sym: str, tick):
    if tick is not None:
        return float(tick) if tick else None
    return bd.TICK.get(sym.upper())


def _round_tick(x, tick):
    if not tick:
        return np.asarray(x, np.float64)
    d = int(round(-np.log10(tick)))
    if abs(10.0 ** (-d) - tick) <= 1e-12 * tick:
        return np.round(np.asarray(x, np.float64), d)
    return np.round(np.asarray(x, np.float64) / tick) * tick


def n_intervals(lo: float, hi: float, spacing: float = SPACING) -> int:
    """Largest interval count whose geometric ratio (hi / lo)^(1 / G) is at least 1 + spacing (choice 1)."""
    if not (np.isfinite(lo) and np.isfinite(hi)) or lo <= 0 or hi <= lo:
        return 0
    return int(np.floor(np.log(hi / lo) / np.log1p(spacing) + 1e-9))


def geometric_levels(lo: float, hi: float, G: int, tick=None) -> np.ndarray:
    """G + 1 geometric levels from lo to hi (both included), rounded to the tick; duplicates after rounding dropped."""
    r = (hi / lo) ** (1.0 / G)
    lv = lo * r ** np.arange(G + 1, dtype=np.float64)
    lv[0], lv[-1] = lo, hi
    lv = _round_tick(lv, tick)
    return np.unique(lv)


def pivot_state(lv: np.ndarray, p: float) -> np.ndarray:
    """Initial interval states: no order at the level nearest p (log distance); intervals below it flat (a buy at
    their lower level), intervals at and above it holding (a sell at their upper level). Choice 3."""
    k = int(np.argmin(np.abs(np.log(lv / p))))
    return (np.arange(len(lv) - 1) >= k).astype(np.int64)


# ============================================================================ one deployment
def _deploy(A, lv, q, h0, Q0, C0, cost0, margin, m0, m_end, end_mode, end_px, cut, maker, tk, touch, mmr) -> dict:
    G = len(lv) - 1
    span = int(m_end - m0 + 1)
    cap = 64 + 4 * G + span // 8
    mcap = int((A["mt"][m_end] - A["mt"][m0]) // DAY_NS) + 4
    for _ in range(10):
        FI = np.empty((cap, 5), np.int64)
        FF = np.empty((cap, 3), np.float64)
        MK = np.empty((mcap, 3), np.float64)
        st, status, m_stop, liq_px, nmk = _run(
            A["mo"], A["mh"], A["ml"], A["mc"], A["mlive"], A["mhour"], A["hfirst"], A["hlast"], A["dfirst"],
            A["hmlo"], A["hmhi"], A["hmop"], A["hfund"], np.asarray(lv, np.float64), float(q),
            np.asarray(h0, np.int64), float(Q0), float(C0), float(cost0), float(margin), float(mmr), float(maker),
            float(tk), bool(touch), int(m0), int(m_end), int(end_mode), float(end_px), float(cut), FI, FF, MK)
        nrow = int(st[S_NROW])
        if nrow <= cap and nmk <= mcap:
            break
        cap = max(cap * 4, nrow + 64)
        mcap = max(mcap * 2, nmk + 4)
    else:
        raise RuntimeError("grid fill buffer overflow")
    m_stop = int(m_stop)
    Q, C, fees, fund, gp = st[S_Q], st[S_C], st[S_FEES], st[S_FUND], st[S_GP]
    if status == ST_LIQ:
        net = -float(margin)
        end_t = int(A["hu"][A["mhour"][m_stop]] + H_NS)
        p_end = float(liq_px)
    elif status == ST_MARK:
        p_end = float(A["mc"][m_stop])
        net = C + Q * p_end - fees - fund
        end_t = int(A["mt"][m_stop] + MIN_NS)
    else:
        net = C - fees - fund
        if end_mode == E_OPEN:
            end_t = int(A["mt"][m_stop])
            p_end = float(A["mo"][m_stop])
        else:
            end_t = int(A["mt"][m_stop] + MIN_NS)
            rows = FI[:nrow]
            cl = np.flatnonzero(rows[:, 1] == K_CLOSE)
            p_end = float(FF[cl[-1], 0]) if len(cl) else (float(end_px) if end_mode == E_STOP else
                                                           float(A["mc"][m_stop]))
    inv = net + fees + fund - gp
    return {"status": int(status), "m_stop": m_stop, "end_t": end_t, "p_end": p_end, "net": float(net),
            "grid_profit": float(gp), "inventory_pnl": float(inv), "fees": float(fees), "funding": float(fund),
            "n_fills": int(st[S_NF]), "n_round_trips": int(st[S_NRT]), "n_open_through": int(st[S_NOT]),
            "max_notional": float(st[S_MAXX]), "Q_end": float(Q), "FI": FI[:nrow].copy(), "FF": FF[:nrow].copy(),
            "MK": MK[:nmk].copy()}


class _Book:
    """Collects deployments, fills and 00:00 marks of one run and assembles the outputs."""

    def __init__(self, A: dict, kind: str):
        self.A = A
        self.kind = kind
        self.rows = []
        self.fills = []
        self.marks = []

    def add(self, row: dict, res: dict, start_t: int, close_cause_t: int, init_t: int | None = None):
        A = self.A
        dep = len(self.rows)
        row = dict(row)
        row.update(dep=dep, sym=A["sym"], kind=self.kind, start=_ts(start_t), end=_ts(res["end_t"]),
                   p_end=res["p_end"], grid_profit=res["grid_profit"], inventory_pnl=res["inventory_pnl"],
                   fees=res["fees"], funding=res["funding"], net=res["net"], n_fills=res["n_fills"],
                   n_round_trips=res["n_round_trips"], n_open_through=res["n_open_through"],
                   liquidated=res["status"] == ST_LIQ, open_at_end=res["status"] == ST_MARK,
                   max_notional=res["max_notional"])
        if res["status"] == ST_LIQ:
            row["reason"] = "liquidated"
        elif res["status"] == ST_MARK:
            row["reason"] = "window_end"
        FI, FF = res["FI"], res["FF"]
        lv = row.get("_lv")
        gain = 0.0
        if lv is not None and len(FI):
            ot = np.flatnonzero((FI[:, 4] == 1) & (FI[:, 1] <= K_SELL))
            if len(ot):
                i = FI[ot, 2]
                buy = FI[ot, 1] == K_BUY
                L = np.where(buy, lv[i], lv[np.minimum(i + 1, len(lv) - 1)])
                gain = float(np.sum(np.abs(FF[ot, 1]) * np.where(buy, L - FF[ot, 0], FF[ot, 0] - L)))
        row["open_through_gain"] = gain                   # choice 6: price improvement vs filling at the level
        self.rows.append(row)
        if len(FI):
            m = FI[:, 0]
            kind = FI[:, 1]
            placed = FI[:, 3]
            mt = A["mt"]
            stamp = mt[m] + MIN_NS
            is_open_close = (kind == K_CLOSE) & (res["status"] != ST_LIQ) & (row.get("_end_mode") == E_OPEN)
            stamp = np.where(is_open_close, mt[m], stamp)
            stamp = np.where(kind == K_LIQ, A["hu"][A["mhour"][m]] + H_NS, stamp)
            cause = np.where(placed < 0, start_t, mt[np.clip(placed, 0, len(mt) - 1)] + MIN_NS)
            m0 = row["_m0"]
            cause = np.where((kind <= K_SELL) & (placed == m0 - 1), start_t, cause)
            cause = np.where(kind == K_CLOSE, close_cause_t, cause)
            cause = np.where(kind == K_LIQ, A["hu"][A["mhour"][m]], cause)
            self.fills.append(pd.DataFrame({
                "dep": dep, "time_ns": stamp, "minute_ns": mt[m], "m": m, "kind_i": kind, "interval": FI[:, 2],
                "placed": placed, "px": FF[:, 0], "qty": FF[:, 1], "fee": FF[:, 2], "open_through": FI[:, 4] == 1,
                "cause_ns": cause}))
        if init_t is not None and row.get("_Q0", 0.0) != 0.0:
            self.fills.append(pd.DataFrame({
                "dep": [dep], "time_ns": [init_t], "minute_ns": [A["mt"][row["_m0"]]], "m": [row["_m0"]],
                "kind_i": [K_INIT], "interval": [-1], "placed": [-1], "px": [row["p_start"]], "qty": [row["_Q0"]],
                "fee": [row["_cost0"]], "open_through": [False], "cause_ns": [init_t]}))
        MK = res["MK"]
        if len(MK):
            mm = MK[:, 0].astype(np.int64)
            t = A["mt"][mm] - A["mt"][mm] % DAY_NS
            self.marks.append(pd.DataFrame({"dep": dep, "time_ns": t, "cum": MK[:, 1], "notional": MK[:, 2]}))
        return dep

    def deployments(self) -> pd.DataFrame:
        cols = ["dep", "sym", "kind", "decided", "start", "end", "reason", "lo", "hi", "n_int", "ratio", "q", "margin",
                "notional", "p_start", "p_end", "grid_profit", "inventory_pnl", "fees", "funding", "net", "n_fills",
                "n_round_trips", "n_open_through", "open_through_gain", "liquidated", "open_at_end", "max_notional"]
        if not self.rows:
            return pd.DataFrame(columns=cols)
        D = pd.DataFrame(self.rows)
        extra = [c for c in D.columns if c not in cols and not c.startswith("_")]
        return D[cols + extra]

    def fills_frame(self) -> pd.DataFrame:
        cols = ["dep", "time", "minute", "kind", "interval", "px", "qty", "fee", "open_through", "cause_time"]
        if not self.fills:
            return pd.DataFrame(columns=cols + ["m", "placed"])
        F = pd.concat(self.fills, ignore_index=True).sort_values(["time_ns", "dep"], kind="stable")
        F = F.reset_index(drop=True)
        F["time"] = pd.DatetimeIndex(F.time_ns.to_numpy(np.int64), tz="UTC")
        F["minute"] = pd.DatetimeIndex(F.minute_ns.to_numpy(np.int64), tz="UTC")
        F["cause_time"] = pd.DatetimeIndex(F.cause_ns.to_numpy(np.int64), tz="UTC")
        F["kind"] = KIND_NAMES[F.kind_i.to_numpy(np.int64)]
        return F[cols + ["m", "placed"]]

    def marks_frame(self) -> pd.DataFrame:
        if not self.marks:
            return pd.DataFrame(columns=["dep", "time_ns", "cum", "notional"])
        return pd.concat(self.marks, ignore_index=True)

    def daily(self):
        """cum P&L at each 00:00 (marks inside each grid's life, its final P&L from its end on) and the daily diff."""
        A = self.A
        d0 = A["mt"][0] - A["mt"][0] % DAY_NS
        d1 = A["mt"][-1] - A["mt"][-1] % DAY_NS + DAY_NS
        if A["a"] is not None:
            d0 = min(d0, A["a"].floor("D").value)
        days = np.arange(d0, d1 + 1, DAY_NS, dtype=np.int64)
        cum = np.zeros(len(days))
        MKf = self.marks_frame()
        by = []
        for r in self.rows:
            dep = r["dep"]
            arr = np.zeros(len(days))
            arr[days >= r["end"].value] = r["net"]
            mk = MKf[MKf.dep == dep] if len(MKf) else MKf
            if len(mk):
                pos = np.searchsorted(days, mk.time_ns.to_numpy(np.int64))
                ok = (pos < len(days)) & (days[np.clip(pos, 0, len(days) - 1)] == mk.time_ns.to_numpy(np.int64))
                arr[pos[ok]] = mk.cum.to_numpy()[ok]
            cum += arr
            j_end = int(np.searchsorted(days, r["end"].value, side="left"))
            sel = np.flatnonzero(days > r["start"].value)
            sel = sel[sel <= j_end]               # the grid's life plus the first 00:00 at / after its end
            if len(sel):
                by.append(pd.DataFrame({"dep": dep, "time": pd.DatetimeIndex(days[sel], tz="UTC"),
                                        "cum": arr[sel]}))
        idx = pd.DatetimeIndex(days, tz="UTC")
        cum_s = pd.Series(cum, index=idx, name="cum")
        daily = pd.Series(np.diff(cum), index=idx[:-1], name="pnl")
        byf = pd.concat(by, ignore_index=True) if by else pd.DataFrame(columns=["dep", "time", "cum"])
        return daily, cum_s, byf

    def audit(self, F: pd.DataFrame) -> list:
        return _audit(self.A, F)


def _audit(A: dict, F: pd.DataFrame) -> list:
    """Fill audit (Controls): every fill, before costs, inside its 1-minute bar's [low, high], in a minute with
    trades > 0 in a tradable hour, stamped at or after its cause (a refill strictly after the minute that placed it);
    a liquidation's trigger price inside the hour's mark / last-price extremes."""
    out = []
    if not len(F):
        return out
    m = F.m.to_numpy(np.int64)
    kind = F.kind.to_numpy(object)
    px = F.px.to_numpy(np.float64)
    lo, hi, live = A["ml"][m], A["mh"][m], A["mlive"][m]
    tol = 1e-9 * np.abs(px) + 1e-12
    is_liq = kind == "liq"
    bad_rng = ~is_liq & ((px < lo - tol) | (px > hi + tol))
    bad_live = ~is_liq & ~live
    t = F.time.to_numpy(np.int64) if F.time.dtype.kind == "i" else _ns(F.time)
    c = _ns(F.cause_time)
    bad_cause = t < c
    pl = F.placed.to_numpy(np.int64)
    level = (kind == "buy") | (kind == "sell")
    bad_refill = level & (pl >= m)                    # an order may fill only after the minute that placed it
    bad_lq = np.zeros(len(F), bool)
    if is_liq.any():
        hr = A["mhour"][m]
        sel = np.flatnonzero(is_liq)
        for i in sel:
            mins = np.flatnonzero((A["mhour"] == hr[i]) & A["mlive"])
            lo_h = min(np.nanmin(A["ml"][mins]) if len(mins) else np.inf,
                       A["hmlo"][hr[i]] if np.isfinite(A["hmlo"][hr[i]]) else np.inf)
            hi_h = max(np.nanmax(A["mh"][mins]) if len(mins) else -np.inf,
                       A["hmhi"][hr[i]] if np.isfinite(A["hmhi"][hr[i]]) else -np.inf)
            if not (lo_h - tol[i] <= px[i] <= hi_h + tol[i]):
                bad_lq[i] = True
    for name, bad in (("price outside the minute's range", bad_rng), ("fill in a trades == 0 minute", bad_live),
                      ("fill stamped before its cause", bad_cause), ("refill in the minute that placed it", bad_refill),
                      ("liquidation price not reached", bad_lq)):
        for i in np.flatnonzero(bad)[:20]:
            out.append(f"{A['sym']} {name}: dep {F.dep.iat[i]} {kind[i]} minute {F.minute.iat[i]} px {px[i]:.10g} "
                       f"[{lo[i]:.10g}, {hi[i]:.10g}] live {bool(live[i])} cause {F.cause_time.iat[i]}")
    return out


def _result(book: _Book, log: dict, extra: dict | None = None) -> dict:
    D = book.deployments()
    F = book.fills_frame()
    daily, cum, byf = book.daily()
    audit = book.audit(F)
    log = dict(log)
    log.update(deployments=len(D), fills=int((F.kind.isin(["buy", "sell"])).sum()) if len(F) else 0,
               open_through_fills=int(F.open_through.sum()) if len(F) else 0,
               open_through_gain=float(D.open_through_gain.sum()) if len(D) else 0.0,
               hours_source=book.A["hours_src"], hours_missing=book.A["missing_hours"],
               hours_price_mismatch=book.A["hours_mismatch"],
               minutes=int(book.A["M"]), outage_minutes=int((~book.A["mlive"]).sum()))
    out = {"sym": book.A["sym"], "kind": book.kind, "deployments": D, "daily_pnl": daily, "cum": cum,
           "daily_by_dep": byf, "fills": F, "fills_audit": audit, "log": log}
    if extra:
        out.update(extra)
    return out


# ============================================================================ G-A
def _roll_max_time(x: np.ndarray, t: np.ndarray, seg: np.ndarray, span_ns: int) -> np.ndarray:
    """Max of x over rows j with t_j > t_i - span (row i included) in the same segment."""
    n = len(x)
    out = np.full(n, np.nan)
    j0 = 0
    for i in range(n):
        while j0 < i and (t[j0] <= t[i] - span_ns or seg[j0] != seg[i]):
            j0 += 1
        w = x[j0:i + 1]
        w = w[np.isfinite(w)]
        if len(w):
            out[i] = w.max()
    return out


def daily_indicators(daily_bars: pd.DataFrame) -> pd.DataFrame:
    """G-A's deployment inputs per daily bar: known_at (the 00:00 close), close, BB(20, 2) upper / lower band
    (population sigma, restarted at `seg` changes, bb_engine's _roll_sma_sd), the 60-day high (highest high of the 60
    days ending at the close, same segment) and warm (>= 60 completed bars in the segment)."""
    D = daily_bars
    lab = _ns(D.index)
    ka = _ns(D["known_at"]) if "known_at" in D.columns else lab + DAY_NS
    C = D["close"].to_numpy(np.float64)
    Hh = D["high"].to_numpy(np.float64)
    seg = D["seg"].to_numpy(np.int64) if "seg" in D.columns else np.zeros(len(D), np.int64)
    sma, sd = be._roll_sma_sd(C, seg, GA_N)
    hi60 = _roll_max_time(Hh, lab, seg, GA_HI_DAYS * DAY_NS)
    cnt = np.zeros(len(D), np.int64)
    run = 0
    for i in range(len(D)):
        run = run + 1 if i > 0 and seg[i] == seg[i - 1] else 1
        cnt[i] = run
    return pd.DataFrame({"known_at": ka, "close": C, "ub": sma + GA_K * sd, "lb": sma - GA_K * sd, "hi60": hi60,
                         "warm": cnt >= GA_WARM, "seg": seg}, index=D.index)


def _r0_spans(r0_trades) -> tuple[np.ndarray, np.ndarray]:
    """(entry1_time, exit_time) ns of R0's positions, sorted by entry; r0_trades may be simulate_coin's result."""
    if isinstance(r0_trades, dict):
        r0_trades = r0_trades["trades"]
    if r0_trades is None or not len(r0_trades):
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    e = _ns(r0_trades["entry1_time"])
    x = _ns(r0_trades["exit_time"])
    o = np.argsort(e, kind="stable")
    return e[o], x[o]


def _occupied(T: np.ndarray, e: np.ndarray, x: np.ndarray) -> np.ndarray:
    """True where some position has entry1_time <= T < exit_time."""
    if not len(e):
        return np.zeros(len(T), bool)
    cmx = np.maximum.accumulate(x)
    i = np.searchsorted(e, T, side="right") - 1
    return (i >= 0) & (cmx[np.clip(i, 0, len(e) - 1)] > T)


def grid_ga(sym: str, r0_trades=None, daily_bars: pd.DataFrame | None = None, cfg_fees: str = "base",
            start=GRID_START, end=GRID_END, sleeve: float = 1.0, fill: str = "through",
            minutes: pd.DataFrame | None = None, hours: pd.DataFrame | str | None = None, mmr: float | None = None,
            lb_rule: str = "current", tick=None) -> dict:
    """G-A "waiting grid" on one coin's slot (pre-registration, Grid overlays). r0_trades: R0's positions on the same
    coin (simulate_coin's trades or result; they decide "the slot is flat" and end (a)). daily_bars: the signal daily
    bars (default bb_data.bars(sym, "1d"), or bars_from_hours(hours) when hours are injected). P&L in units of the
    slot's sleeve (sleeve = E_sleeve). fill: "through" (primary) or "touch" (optimistic bound)."""
    if lb_rule not in ("current", "deploy"):
        raise ValueError("lb_rule must be 'current' (choice 10) or 'deploy'")
    touch = _touch(fill)
    A = _prep(sym, start, end, minutes, hours)
    maker, tk = _fees(sym, cfg_fees)
    mmr_v = float(mmr) if mmr is not None else float(bd.MMR.get(sym.upper(), 0.005))
    tick_v = _tick(sym, tick)
    if daily_bars is None:
        hm = _hours_mode(minutes, hours)
        if hm == "frame":
            daily_bars = bd.bars_from_hours(hours, "1d", "sig")
        elif hm == "disk" or minutes is None:
            daily_bars = bd.bars(sym.upper(), "1d", "sig")
        else:
            raise ValueError(f"grid_ga({sym}): injected minutes need daily_bars= or hours= (a frame, or 'disk' for "
                             f"bb_data's signal bars); bars are never loaded from disk for injected minutes")
    I = daily_indicators(daily_bars)
    T_all = I["known_at"].to_numpy(np.int64)
    lo_t = A["a"].value if A["a"] is not None else A["mt"][0]
    hi_t = A["b"].value if A["b"] is not None else A["mt"][-1]
    sel = (T_all >= lo_t) & (T_all <= hi_t) & (T_all <= A["mt"][-1])
    T = T_all[sel]
    C = I["close"].to_numpy()[sel]
    ub = I["ub"].to_numpy()[sel]
    lb = I["lb"].to_numpy()[sel]
    hi60 = I["hi60"].to_numpy()[sel]
    warm = I["warm"].to_numpy()[sel]
    e_ns, x_ns = _r0_spans(r0_trades)
    occ = _occupied(T, e_ns, x_ns)
    with np.errstate(invalid="ignore"):
        cond = warm & np.isfinite(ub) & np.isfinite(lb) & (C <= ub) & (C >= GA_NEAR * hi60) & ~occ
        below_cur = C < lb
    pend = _perp_end_closes(A)
    nT = len(T)
    book = _Book(A, "GA")
    log = {"tests": int(nT), "tests_condition": int(cond.sum()), "tests_occupied": int(occ.sum()),
           "skipped_narrow_range": 0, "skipped_r0_before_fill": 0, "skipped_no_live_minute": 0,
           "ends": {}}
    last_m = A["M"] - 1
    k = 0
    while k < nT:
        if not cond[k]:
            k += 1
            continue
        Tk = int(T[k])
        m0 = _first_live_ge(A, Tk)
        if m0 < 0:
            log["skipped_no_live_minute"] += 1
            break
        je = int(np.searchsorted(e_ns, Tk, side="right"))
        t_a = int(e_ns[je]) if je < len(e_ns) else INF_NS
        if t_a <= A["mt"][m0]:
            log["skipped_r0_before_fill"] += 1
            k += 1
            continue
        G = n_intervals(lb[k], ub[k])
        lv = geometric_levels(lb[k], ub[k], G, tick_v) if G >= 2 else np.zeros(0)
        if len(lv) < 3:
            log["skipped_narrow_range"] += 1
            k += 1
            continue
        G = len(lv) - 1
        P0 = float(A["mo"][m0])
        q = sleeve / (G * P0)
        h0 = pivot_state(lv, P0)
        # end candidates: (a) R0 entry, (b) a close below the lower band, (c) 14 days, perp_end, window end
        later = np.arange(k + 1, nT)
        bmask = below_cur[later] if lb_rule == "current" else (C[later] < lb[k])
        kb = int(later[bmask][0]) if bmask.any() else -1
        kc_i = int(np.searchsorted(T, Tk + GA_DAYS * DAY_NS, side="left"))
        kc = kc_i if kc_i < nT else -1
        t_b = int(T[kb]) if kb >= 0 else INF_NS
        t_c = int(T[kc]) if kc >= 0 else INF_NS
        jp = int(np.searchsorted(pend, A["mt"][m0], side="right"))
        t_p = int(pend[jp]) if jp < len(pend) else INF_NS
        t_end = min(t_a, t_b, t_c, t_p)
        if t_end == INF_NS:
            mode, m_end, reason, end_px = E_MARK, last_m, "window_end", np.nan
        elif t_end == t_p and t_p < min(t_a, t_b, t_c):
            m_end = _last_live_lt(A, t_p)
            mode, reason, end_px = E_CLOSE, "perp_end", float(A["mc"][m_end])
        else:
            reason = "r0_entry" if t_end == t_a else ("below_lower_band" if t_end == t_b else "14_days")
            m_end = _first_live_ge(A, t_end)
            mode, end_px = E_OPEN, np.nan
            if m_end < 0:
                mode, m_end, reason = E_MARK, last_m, "window_end"
        if m_end <= m0 and mode == E_OPEN:                     # the end came before the delayed deployment minute
            log["skipped_no_live_minute"] += 1
            k = {"below_lower_band": kb, "14_days": kc}.get(reason, int(np.searchsorted(T, t_end, side="right")))
            continue
        margin = sleeve / GRID_LEV
        res = _deploy(A, lv, q, h0, 0.0, 0.0, 0.0, margin, m0, m_end, mode, end_px, np.nan, maker, tk, touch, mmr_v)
        row = {"decided": _ts(Tk), "reason": reason, "lo": float(lb[k]), "hi": float(ub[k]), "n_int": G,
               "ratio": float((lv[-1] / lv[0]) ** (1.0 / G)), "q": q, "margin": margin, "notional": q * G * P0,
               "p_start": P0, "_m0": m0, "_end_mode": mode, "_Q0": 0.0, "_cost0": 0.0, "_lv": lv}
        book.add(row, res, int(A["mt"][m0]), t_end if mode == E_OPEN else int(A["mt"][m_end]))
        rsn = book.rows[-1]["reason"]
        log["ends"][rsn] = log["ends"].get(rsn, 0) + 1
        if res["status"] == ST_LIQ:
            k = int(np.searchsorted(T, res["end_t"], side="left"))
        elif rsn == "r0_entry":
            k = int(np.searchsorted(T, t_a, side="right"))
        elif rsn in ("below_lower_band", "14_days"):
            k = kb if rsn == "below_lower_band" else kc
        elif rsn == "perp_end":
            k = int(np.searchsorted(T, t_p, side="left"))
        else:
            break
    log.update(fees=cfg_fees, fill=fill, lb_rule=lb_rule, sleeve=sleeve, mmr=mmr_v, tick=tick_v)
    return _result(book, log)


# ============================================================================ G-0
def grid_g0(sym: str, cfg_fees: str = "base", start=GRID_START, end=GRID_END, sleeve: float = 1.0,
            fill: str = "through", minutes: pd.DataFrame | None = None, hours: pd.DataFrame | str | None = None,
            mmr: float | None = None, tick=None) -> dict:
    """G-0: an always-on neutral grid, +/-10% around the deployment open, re-centred each Monday 00:00 UTC (choice
    15); G-A's spacing, margin, fills, fees, funding and liquidation. P&L in units of the sleeve."""
    touch = _touch(fill)
    A = _prep(sym, start, end, minutes, hours)
    maker, tk = _fees(sym, cfg_fees)
    mmr_v = float(mmr) if mmr is not None else float(bd.MMR.get(sym.upper(), 0.005))
    tick_v = _tick(sym, tick)
    pend = _perp_end_closes(A)
    book = _Book(A, "G0")
    log = {"ends": {}, "skipped_narrow_range": 0}
    last_m = A["M"] - 1
    t_dec = int(A["mt"][0]) if A["a"] is None else max(int(A["a"].value), int(A["mt"][0]))
    m0 = _first_live_ge(A, t_dec)
    while 0 <= m0 <= last_m:
        P0 = float(A["mo"][m0])
        lo, hi = (1.0 - G0_HALF) * P0, (1.0 + G0_HALF) * P0
        G = n_intervals(lo, hi)
        lv = geometric_levels(lo, hi, G, tick_v)
        if len(lv) < 3:
            log["skipped_narrow_range"] += 1
            break
        G = len(lv) - 1
        q = sleeve / (G * P0)
        h0 = pivot_state(lv, P0)
        t0 = int(A["mt"][m0])
        day = t0 - t0 % DAY_NS
        wd = pd.Timestamp(day, tz="UTC").weekday()
        t_w = day + (7 - wd) * DAY_NS                             # next Monday 00:00 strictly after t0's day
        jp = int(np.searchsorted(pend, t0, side="right"))
        t_p = int(pend[jp]) if jp < len(pend) else INF_NS
        if t_p < t_w:
            m_end = _last_live_lt(A, t_p)
            mode, reason, end_px, t_end = E_CLOSE, "perp_end", float(A["mc"][m_end]), t_p
        else:
            m_end = _first_live_ge(A, t_w)
            mode, reason, end_px, t_end = E_OPEN, "weekly", np.nan, t_w
            if m_end < 0:
                mode, m_end, reason = E_MARK, last_m, "window_end"
        margin = sleeve / GRID_LEV
        res = _deploy(A, lv, q, h0, 0.0, 0.0, 0.0, margin, m0, m_end, mode, end_px, np.nan, maker, tk, touch, mmr_v)
        row = {"decided": _ts(t_dec), "reason": reason, "lo": lo, "hi": hi, "n_int": G,
               "ratio": float((lv[-1] / lv[0]) ** (1.0 / G)), "q": q, "margin": margin, "notional": q * G * P0,
               "p_start": P0, "_m0": m0, "_end_mode": mode, "_Q0": 0.0, "_cost0": 0.0, "_lv": lv}
        book.add(row, res, t0, t_end if mode == E_OPEN else int(A["mt"][m_end]))
        rsn = book.rows[-1]["reason"]
        log["ends"][rsn] = log["ends"].get(rsn, 0) + 1
        if res["status"] == ST_LIQ:
            t_dec = res["end_t"]
            m0 = _first_live_ge(A, t_dec)
        elif rsn == "weekly":
            t_dec = t_w
            m0 = m_end
        else:
            break
    log.update(fees=cfg_fees, fill=fill, sleeve=sleeve, mmr=mmr_v, tick=tick_v)
    return _result(book, log)


# ============================================================================ G-B
def _final_exit(tr_pos: pd.DataFrame, trade: pd.Series):
    """The R0 position's final exit row (kind, stamp ns, px, engine minute code)."""
    fin = tr_pos[~tr_pos.kind.isin(["entry", "add"])]
    if trade.get("exit_reason", "") != "tp_all":
        fin = fin[fin.kind != "tp"]
    if not len(fin):
        return None
    t = _ns(fin.time)
    i = int(np.flatnonzero(t == t.max())[-1])
    r = fin.iloc[i]
    mcode = int(r["minute"]) if "minute" in fin.columns else None
    return str(r["kind"]), int(t[i]), float(r["px"]), mcode


def _exit_bar_open(kind_x: str, tx: int, mcode) -> int:
    """Open time of the bar in which R0's final exit happened, from bb_engine's stamps (minute code >= 0: that
    minute's close; -2: the hour's close; -1: the hour's open). Without a minute code: a trend exit at the hour's
    open, a stamp on the hour at the hour's close, else a minute's close."""
    if mcode is None:
        mcode = -1 if kind_x == "exit" else (-2 if tx % H_NS == 0 else 0)
    if mcode >= 0:
        return tx - MIN_NS
    if mcode == -2:
        return tx - H_NS
    return tx


def grid_gb(sym: str, r0_trades, tranches: pd.DataFrame | None = None, cfg_fees: str = "base", start=GRID_START,
            end=GRID_END, fill: str = "through", minutes: pd.DataFrame | None = None,
            hours: pd.DataFrame | str | None = None, mmr: float | None = None, n_levels: int = GB_LEVELS, tick=None,
            r0_daily_mtm: pd.DataFrame | None = None) -> dict:
    """G-B (exploratory): each R0 tranche (entry and each add) run as a long-mode geometric grid over [S, TP] with
    n_levels levels, from its fill to the position's final exit (choice 14). r0_trades / tranches / r0_daily_mtm:
    simulate_coin's outputs (or pass its result dict as r0_trades). P&L in units of the position's M.
    Positions that are not wrapped (S11 shorts, entry1 outside [start, end] or the minutes, no exit row, a range
    too narrow for the levels) are passed through unchanged (gb_wrapped False: R0's ret and its daily_mtm rows),
    so that bb_engine.assemble on the output is the R0 + G-B account. A position whose R0 exit falls after the
    window's last minute has every tranche grid marked at the window's last live minute (the Windows rule: "a trade
    still open at a window's end is marked at the last hourly close"), open_at_end True, reason window_end."""
    if isinstance(r0_trades, dict):
        tranches = r0_trades["tranches"] if tranches is None else tranches
        r0_daily_mtm = r0_trades.get("daily_mtm") if r0_daily_mtm is None else r0_daily_mtm
        r0_trades = r0_trades["trades"]
    touch = _touch(fill)
    A = _prep(sym, start, end, minutes, hours)
    maker, tk = _fees(sym, cfg_fees)
    mmr_v = float(mmr) if mmr is not None else float(bd.MMR.get(sym.upper(), 0.005))
    tick_v = _tick(sym, tick)
    book = _Book(A, "GB")
    log = {"positions": 0, "wrapped": 0, "passthrough": 0, "skipped_short": 0, "skipped_outside": 0,
           "skipped_no_exit": 0, "skipped_narrow_range": 0, "skipped_no_tranche_grid": 0, "tranche_grids": 0,
           "tranches_not_wrapped": 0, "window_end_marked": 0, "exit_px_clipped": 0, "passthrough_no_mtm": 0,
           "ends": {}}
    T = r0_trades if r0_trades is not None else pd.DataFrame()
    if len(T) and tranches is None:
        raise ValueError("grid_gb needs R0's tranches (simulate_coin's 'tranches' or its result dict)")
    out_rows = []                                            # (trade row, deps or None, skip reason, marked)
    lo_t = A["mt"][0] if A["a"] is None else max(A["a"].value, A["mt"][0])
    hi_t = A["mt"][-1] if A["b"] is None else min(A["b"].value, A["mt"][-1])
    last_open = int(A["mt"][-1])

    def skip(tr, why):
        log[why] += 1
        out_rows.append((tr, None, why, False))

    for _, tr in T.iterrows():
        log["positions"] += 1
        e1 = int(_ns([tr.entry1_time])[0])
        if int(tr.get("side", 1)) < 0:
            skip(tr, "skipped_short")
            continue
        if not (lo_t <= e1 <= hi_t):
            skip(tr, "skipped_outside")
            continue
        tp_ = tranches[tranches.pos == tr.pos]
        fe = _final_exit(tp_, tr)
        if fe is None:
            skip(tr, "skipped_no_exit")
            continue
        kind_x, tx, pxx, mcode = fe
        S, TP, Lu = float(tr.S), float(tr.TP), float(tr.L_used)
        marked = _exit_bar_open(kind_x, tx, mcode) > last_open
        # end of every tranche grid of this position
        if marked:                                           # R0 exits after the window: mark at its end
            m_end, mode, end_px, cut = _last_live_lt(A, last_open + MIN_NS), E_MARK, np.nan, np.nan
        elif kind_x == "exit":
            m_end, mode, end_px, cut = _first_live_ge(A, tx), E_OPEN, np.nan, np.nan
        elif kind_x == "end":
            m_end, mode, end_px, cut = _last_live_lt(A, tx), E_MARK, np.nan, np.nan
        elif kind_x == "stop":
            hour_close = (mcode == -2) if mcode is not None else (tx % H_NS == 0)
            mode, end_px, cut = E_STOP, pxx, S
            if hour_close:
                mins = np.flatnonzero((A["mt"] >= tx - H_NS) & (A["mt"] < tx) & A["mlive"] & (A["ml"] <= S))
                m_end = int(mins[0]) if len(mins) else -1
                if m_end < 0:
                    m_end, mode, cut = _last_live_lt(A, tx), E_CLOSE, np.nan
            else:
                m_end = int(np.searchsorted(A["mt"], tx - MIN_NS, side="left"))
                if m_end >= A["M"] or A["mt"][m_end] != tx - MIN_NS:
                    m_end = _last_live_lt(A, tx)
        else:                                                # delist, liq, tp (tp_all)
            m_end, mode, end_px, cut = _last_live_lt(A, tx), E_CLOSE, pxx, np.nan
        if m_end < 0:
            skip(tr, "skipped_no_exit")
            continue
        G = int(n_levels) - 1
        lv = geometric_levels(S, TP, G, tick_v) if (S > 0 and TP > S and G >= 2) else np.zeros(0)
        if len(lv) < 3:
            skip(tr, "skipped_narrow_range")
            continue
        G = len(lv) - 1
        if mode in (E_STOP, E_CLOSE) and A["mlive"][m_end] and not (A["ml"][m_end] <= pxx <= A["mh"][m_end]):
            log["exit_px_clipped"] += 1
        tr_in = tp_[tp_.kind.isin(["entry", "add"])]
        deps = []
        reason = "window_end" if marked else {"exit": "mid", "end": "window_end", "stop": "stop"}.get(kind_x, kind_x)
        close_cause = tx if mode in (E_OPEN, E_STOP) else int(A["mt"][m_end])
        for j, (_, tj) in enumerate(tr_in.iterrows()):
            t_f = int(_ns([tj.time])[0])
            m0 = _first_live_ge(A, t_f)
            if m0 < 0 or m0 > m_end or (m0 == m_end and mode == E_OPEN):
                log["tranches_not_wrapped"] += 1               # filled after the window's end (or at the exit)
                continue
            px0, frac = float(tj.px), float(tj.frac)
            q = frac / (G * px0)
            h0 = pivot_state(lv, px0)
            Q0 = q * float(h0.sum())
            cost0 = Q0 * px0 * tk
            margin = frac / Lu
            res = _deploy(A, lv, q, h0, Q0, -Q0 * px0, cost0, margin, m0, m_end, mode, end_px, cut, maker, tk,
                          touch, mmr_v)
            row = {"decided": _ts(t_f), "reason": reason, "lo": S, "hi": TP, "n_int": G,
                   "ratio": float((lv[-1] / lv[0]) ** (1.0 / G)), "q": q, "margin": margin, "notional": frac,
                   "p_start": px0, "pos": int(tr.pos), "tranche": j, "tranche_kind": str(tj.kind), "frac": frac,
                   "L_used": Lu, "Q0": Q0, "_m0": m0, "_end_mode": mode, "_Q0": Q0, "_cost0": cost0, "_lv": lv}
            dep = book.add(row, res, t_f, close_cause, init_t=t_f)
            deps.append(dep)
            rsn = book.rows[-1]["reason"]
            log["ends"][rsn] = log["ends"].get(rsn, 0) + 1
        if not deps:
            skip(tr, "skipped_no_tranche_grid")
            continue
        log["wrapped"] += 1
        log["tranche_grids"] += len(deps)
        log["window_end_marked"] += int(marked)
        out_rows.append((tr, deps, "", marked))
    res = _result(book, log)
    D = res["deployments"]
    # engine-format trades and daily_mtm of every R0 position (units of M): wrapped ones from their grids, the others
    # passed through unchanged
    rows = []
    for tr, deps, why, marked in out_rows:
        r = tr.copy()
        r["ret_r0"] = tr.ret
        r["exit_time_r0"] = tr.get("exit_time", pd.NaT)
        r["exit_reason_r0"] = tr.get("exit_reason", "")
        r["gb_wrapped"] = deps is not None
        r["gb_skip"] = why
        if deps is None:
            r["gb_grid_profit"] = 0.0
            r["gb_inventory_pnl"] = 0.0
            r["gb_n_grids"] = 0
            rows.append(r)
            continue
        d = D[D.dep.isin(deps)]
        r["ret"] = float(d.net.sum())
        r["ret_gross"] = float((d.grid_profit + d.inventory_pnl).sum())
        r["fees"] = float(d.fees.sum())
        r["funding"] = float(d.funding.sum())
        r["liquidated"] = bool(d.liquidated.any())
        r["gb_grid_profit"] = float(d.grid_profit.sum())
        r["gb_inventory_pnl"] = float(d.inventory_pnl.sum())
        r["gb_n_grids"] = len(d)
        if marked:                                           # marked at the window's end (Windows rule)
            x_end = d.end.max()
            r["exit_time"] = x_end
            r["exit_px"] = float(d.p_end.iloc[-1])
            r["exit_reason"] = "window_end"
            r["open_at_end"] = True
            if "hold_h" in r.index:
                r["hold_h"] = (x_end.value - int(_ns([tr.entry1_time])[0])) / H_NS
        rows.append(r)
    extra_cols = ["ret_r0", "exit_time_r0", "exit_reason_r0", "gb_wrapped", "gb_skip", "gb_grid_profit",
                  "gb_inventory_pnl", "gb_n_grids"]
    trades = pd.DataFrame(rows).reset_index(drop=True) if rows else pd.DataFrame(
        columns=list(T.columns) + [c for c in extra_cols if c not in T.columns])
    dm_cols = ["pos", "time", "mtm", "margin", "notional", "sym"]
    parts = []
    byf = res["daily_by_dep"]
    if len(byf) and len(D):
        b = byf.merge(D[["dep", "pos", "margin", "start", "end"]], on="dep")
        MKf = book.marks_frame()
        nmap = {}
        if len(MKf):
            for dep, t, n in zip(MKf.dep, MKf.time_ns, MKf.notional):
                nmap[(int(dep), int(t))] = float(n)
        b["notional"] = [nmap.get((int(dp), int(t.value)), 0.0) for dp, t in zip(b.dep, b.time)]
        b = b[b.time <= b.end]
        dm = b.groupby(["pos", "time"], as_index=False).agg(mtm=("cum", "sum"), margin=("margin", "sum"),
                                                            notional=("notional", "sum"))
        dm["sym"] = sym
        parts.append(dm[dm_cols])
    passed = [int(tr.pos) for tr, deps, _, _ in out_rows if deps is None]
    log_ = res["log"]
    log_["passthrough"] = len(passed)
    if passed:
        if r0_daily_mtm is not None:
            pm = r0_daily_mtm[r0_daily_mtm.pos.isin(passed)] if len(r0_daily_mtm) else r0_daily_mtm
            if len(pm):
                pm = pm.assign(time=_idx(pm.time))
                parts.append(pm[[c for c in dm_cols if c in pm.columns]].assign(sym=sym)[dm_cols])
        else:
            log_["passthrough_no_mtm"] = len(passed)
            warnings.warn(f"grid_gb({sym}): {len(passed)} unwrapped R0 positions passed through without R0's "
                          f"daily_mtm (pass simulate_coin's result or r0_daily_mtm=): their 00:00 marks are missing",
                          stacklevel=2)
    dm = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=dm_cols)
    if len(dm):
        dm = dm.sort_values(["time", "pos"], kind="stable").reset_index(drop=True)
    res["trades"] = trades
    res["daily_mtm"] = dm
    return res


# ============================================================================ account helper
def merge_ga(r0_result: dict, ga: dict, pos_offset: int = 1_000_000) -> dict:
    """simulate_coin's result plus one pseudo-position per G-A deployment, for bb_engine.assemble: L_used = 1 so
    that its M is the slot's sleeve at the deployment day (rule 11 sizing included), ret = net P&L per sleeve,
    daily_mtm = the grid's 00:00 marks per sleeve, margin = 1/3 (idle-margin T-bill accounting). grid_ga's P&L is
    in units of its `sleeve` argument (logged), so every amount is divided by it: the account sizes the grid at
    E_sleeve whatever sleeve the run used. Isolated grids only (S3 cross margin is not supported with grids)."""
    out = dict(r0_result)
    D = ga["deployments"]
    if not len(D):
        return out
    sl = float(ga.get("log", {}).get("sleeve", 1.0))
    if not (np.isfinite(sl) and sl > 0):
        raise ValueError(f"merge_ga: grid_ga's sleeve must be > 0, got {sl}")
    pseudo = pd.DataFrame({
        "pos": pos_offset + D.dep.to_numpy(np.int64), "sym": D.sym.to_numpy(object), "side": 1,
        "entry1_time": _idx(D.start), "exit_time": _idx(D.end), "ret": D.net.to_numpy(float) / sl,
        "ret_gross": (D.grid_profit + D.inventory_pnl).to_numpy(float) / sl, "fees": D.fees.to_numpy(float) / sl,
        "funding": D.funding.to_numpy(float) / sl, "L_used": 1.0, "liquidated": D.liquidated.to_numpy(bool),
        "open_at_end": D.open_at_end.to_numpy(bool), "n_tranches": 0, "exit_reason": "grid_" + D.reason.astype(str),
        "grid": True})
    T0 = r0_result["trades"]
    T = pd.concat([T0.assign(grid=False), pseudo], ignore_index=True) if len(T0) else pseudo
    by = ga["daily_by_dep"]
    if len(by):
        dm = by.merge(D[["dep", "margin", "end"]], on="dep")
        dm = dm[dm.time <= dm.end]
        dm = pd.DataFrame({"pos": pos_offset + dm.dep.to_numpy(np.int64), "time": _idx(dm.time),
                           "mtm": dm.cum.to_numpy(float) / sl, "margin": dm.margin.to_numpy(float) / sl,
                           "notional": 0.0, "sym": D.sym.iat[0]})
        DM = pd.concat([r0_result["daily_mtm"], dm], ignore_index=True) if len(r0_result["daily_mtm"]) else dm
    else:
        DM = r0_result["daily_mtm"]
    out["trades"] = T
    out["daily_mtm"] = DM
    return out


# ============================================================================ single grid on given minutes
def run_grid(minutes: pd.DataFrame, levels, q: float, mode: str = "neutral", sleeve_margin: float | None = None,
             cfg_fees: str = "base", sym: str = "SYN", fill: str = "through", hours: pd.DataFrame | str | None = None,
             mmr: float = 0.005, start=None, end=None, end_mode: str = "mark", end_time=None, end_px=np.nan,
             cut=np.nan) -> dict:
    """One grid deployed at the first live minute of `minutes` (from `start`) with the given levels and quantity
    per interval (the kernel behind every overlay; used by the self-test and path_check). mode "neutral" (starts
    flat) or "long" (buys the inventory above the pivot at the deployment open, taker cost). end_mode "mark" (mark
    at the last minute), "open" (close at the open of the first live minute at or after end_time), "stop" (G-B
    stop at the minute opening at end_time, cut at `cut`, close at end_px), "close" (close at the minute opening
    at end_time at end_px)."""
    touch = _touch(fill)
    A = _prep(sym, start, end, minutes, hours)
    maker, tk = _fees(sym, cfg_fees)
    lv = np.asarray(levels, np.float64)
    m0 = _first_live_ge(A, A["mt"][0])
    P0 = float(A["mo"][m0])
    h0 = pivot_state(lv, P0)
    Q0 = q * float(h0.sum()) if mode == "long" else 0.0
    cost0 = Q0 * P0 * tk
    margin = 1e18 if sleeve_margin is None else float(sleeve_margin)
    em = {"mark": E_MARK, "open": E_OPEN, "stop": E_STOP, "close": E_CLOSE}[end_mode]
    if em == E_MARK:
        m_end = A["M"] - 1
    else:
        t_e = int(_ns([end_time])[0])
        m_end = _first_live_ge(A, t_e) if em == E_OPEN else int(np.searchsorted(A["mt"], t_e, side="left"))
    res = _deploy(A, lv, q, h0, Q0, -Q0 * P0, cost0, margin, m0, m_end, em, float(end_px), float(cut), maker, tk,
                  touch, mmr)
    book = _Book(A, "single")
    row = {"decided": _ts(A["mt"][m0]), "reason": end_mode, "lo": lv[0], "hi": lv[-1], "n_int": len(lv) - 1,
           "ratio": float((lv[-1] / lv[0]) ** (1.0 / (len(lv) - 1))), "q": q, "margin": margin,
           "notional": q * (len(lv) - 1) * P0, "p_start": P0, "_m0": m0, "_end_mode": em, "_Q0": Q0,
           "_cost0": cost0, "_lv": lv}
    book.add(row, res, int(A["mt"][m0]), int(A["mt"][m_end]), init_t=int(A["mt"][m0]) if mode == "long" else None)
    out = _result(book, {})
    out["res"] = res
    out["h0"] = h0
    out["A"] = A
    return out


# ============================================================================ path check (Controls)
@njit(cache=True)
def _ref_1s(p, lv, q, h0, maker):
    """Reference grid on a 1-second print series: an eligible order fills at its level when consecutive prints move
    strictly through it; an order placed after a fill at second s is eligible from s + 1. Returns (P&L at the last
    print before fees, grid profit, fills, fees)."""
    G = lv.shape[0] - 1
    h = h0.copy()
    placed = np.full(G, -1, np.int64)
    opx = np.zeros(G)
    Q = 0.0
    C = 0.0
    gp = 0.0
    nf = 0
    fees = 0.0
    for s in range(1, p.shape[0]):
        a = p[s - 1]
        b = p[s]
        if b < a:
            i = np.searchsorted(lv, a, side="right") - 1
            if i > G - 1:
                i = G - 1
            while i >= 0 and lv[i] > b:
                if h[i] == 0 and placed[i] < s:
                    L = lv[i]
                    Q += q
                    C -= q * L
                    fees += q * L * maker
                    nf += 1
                    if h0[i] == 1:
                        gp += q * (opx[i] - L)
                    else:
                        opx[i] = L
                    h[i] = 1
                    placed[i] = s
                i -= 1
        elif b > a:
            j = np.searchsorted(lv, a, side="left")
            if j < 1:
                j = 1
            while j <= G and lv[j] < b:
                i = j - 1
                if h[i] == 1 and placed[i] < s:
                    L = lv[j]
                    Q -= q
                    C += q * L
                    fees += q * L * maker
                    nf += 1
                    if h0[i] == 0:
                        gp += q * (L - opx[i])
                    else:
                        opx[i] = L
                    h[i] = 0
                    placed[i] = s
                j += 1
    return C + Q * p[p.shape[0] - 1], gp, nf, fees


def _path_1s(days: int, sigma_day: float, seed: int, p0: float = 100.0, tick: float = 0.001) -> np.ndarray:
    """Driftless (martingale) 1-second price path: log steps -s^2/2 + s Z, rounded to the tick."""
    n = int(days) * 86400
    s = sigma_day / np.sqrt(86400.0)
    rng = np.random.default_rng(seed)
    lp = np.log(p0) + np.cumsum(-0.5 * s * s + s * rng.standard_normal(n))
    return _round_tick(np.exp(np.r_[np.log(p0), lp[:-1]]), tick)


def _minutes_from_seconds(p: np.ndarray, start="2025-01-06") -> pd.DataFrame:
    n = len(p) // 60
    x = p[:n * 60].reshape(n, 60)
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=n, freq="min").as_unit("ns")
    return pd.DataFrame({"open": x[:, 0], "high": x.max(1), "low": x.min(1), "close": x[:, -1],
                         "trades": np.full(n, 60, np.int64)}, index=idx)


def path_check(sigmas=(0.022, 0.032, 0.036), days: int = 60, seeds=(1, 2), half: float = 0.15, tol: float = 0.10,
               stress_sigma: float = 0.08, verbose: bool = True) -> dict:
    """Pre-registered grid path check: a driftless 1-second path aggregated to 1-minute bars; the 1-minute engine's
    grid P&L (fill="through", no fees, no funding, no liquidation) must match the 1-second reference P&L to within
    `tol` of the reference's gross grid profit. The grid is a neutral 0.5%-spaced geometric grid over
    [P0 (1 - half), P0 (1 + half)] kept for the whole path, sized like G-A (q = 1 / (G P0)). sigmas: daily volatility
    (BTC / ETH / SOL-like realized volatility 2025-06..2026-09, rules_and_evidence section 2.2); the stress sigma is
    reported, not part of the pass rule."""
    rows = []
    for sig in list(sigmas) + ([stress_sigma] if stress_sigma else []):
        for sd in seeds:
            p = _path_1s(days, sig, 10_000 + 97 * sd + int(sig * 1e4))
            M = _minutes_from_seconds(p)
            p = p[:len(M) * 60]
            P0 = float(p[0])
            lo, hi = P0 * (1 - half), P0 * (1 + half)
            G = n_intervals(lo, hi)
            lv = geometric_levels(lo, hi, G, 0.001)
            q = 1.0 / ((len(lv) - 1) * P0)
            h0 = pivot_state(lv, P0)
            pnl_ref, gp_ref, nf_ref, _ = _ref_1s(p, lv, q, h0, 0.0)
            r = run_grid(M, lv, q, cfg_fees="zero", fill="through", mmr=0.0)
            d = r["deployments"].iloc[0]
            diff = float(d.net) - float(pnl_ref)
            rel = abs(diff) / gp_ref if gp_ref > 0 else np.inf
            rows.append({"sigma_day": sig, "seed": sd, "stress": sig == stress_sigma and sig not in sigmas,
                         "pnl_1s": float(pnl_ref), "pnl_engine": float(d.net), "grid_profit_1s": float(gp_ref),
                         "grid_profit_engine": float(d.grid_profit), "fills_1s": int(nf_ref),
                         "fills_engine": int(d.n_fills), "open_through": int(d.n_open_through), "diff": diff,
                         "rel_to_grid_profit": rel, "ok": rel <= tol})
    R = pd.DataFrame(rows)
    passed = bool(R[~R.stress].ok.all())
    if verbose:
        with pd.option_context("display.width", 200, "display.max_columns", 20):
            print(R.to_string(index=False, float_format=lambda v: f"{v:.5g}"), flush=True)
    return {"table": R, "passed": passed, "tol": tol}


# ============================================================================ self-test helpers
def _U(s) -> pd.Timestamp:
    t = pd.Timestamp(s)
    return t.tz_localize("UTC") if t.tz is None else t.tz_convert("UTC")


def _mins(start, bars) -> pd.DataFrame:
    """Minute frame from a list of (open, high, low, close[, trades]) starting at `start`."""
    idx = pd.date_range(_U(start), periods=len(bars), freq="min").as_unit("ns")
    arr = [tuple(b) + ((10,) if len(b) == 4 else ()) for b in bars]
    return pd.DataFrame({"open": [b[0] for b in arr], "high": [b[1] for b in arr], "low": [b[2] for b in arr],
                         "close": [b[3] for b in arr], "trades": np.asarray([b[4] for b in arr], np.int64)}, index=idx)


def _hours_for(minutes: pd.DataFrame, funding=None, mark_low=None, mark_high=None, mark_open=None) -> pd.DataFrame:
    """coin_hours-shaped frame aggregated from minutes (sig = traded), with optional funding / mark overrides
    (dicts {timestamp: value})."""
    mi = _idx(minutes.index)
    hk = mi.floor("h")
    g = minutes.groupby(hk)
    H = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "trades": g.trades.sum().astype(np.int64)})
    full = pd.date_range(H.index[0], H.index[-1], freq="h").as_unit("ns")
    H = H.reindex(full)
    H["close"] = H["close"].ffill()
    for c in ("open", "high", "low"):
        H[c] = H[c].fillna(H["close"])
    H["trades"] = H["trades"].fillna(0).astype(np.int64)
    H.index.name = "open_time"
    for a in bd.PX:
        H["sig_" + a] = H[a]
    H["live"] = H["sig_live"] = H["trades"] > 0
    H["seg"] = 0
    H["tradable"] = True
    H["spot_only"] = False
    H["perp_end"] = False
    H["funding"] = 0.0
    for c in ("mark_open", "mark_high", "mark_low", "mark_close"):
        H[c] = np.nan
    for col, d in (("funding", funding), ("mark_low", mark_low), ("mark_high", mark_high), ("mark_open", mark_open)):
        for k, v in (d or {}).items():
            H.loc[_U(k), col] = v
    return H


def _gbm_minutes(n: int, sigma: float, seed: int, start, p0: float = 100.0, tick: float = 0.001) -> pd.DataFrame:
    """1-minute martingale GBM bars with exact Brownian-bridge highs and lows in log space, rounded to the tick."""
    rng = np.random.default_rng(seed)
    dlog = -0.5 * sigma ** 2 + sigma * rng.standard_normal(n)
    lc = np.log(p0) + np.cumsum(dlog)
    lo_ = np.r_[np.log(p0), lc[:-1]]
    d2 = (lc - lo_) ** 2
    mx = 0.5 * (lo_ + lc + np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    mn = 0.5 * (lo_ + lc - np.sqrt(d2 - 2 * sigma ** 2 * np.log(rng.random(n))))
    C = _round_tick(np.exp(lc), tick)
    O = np.r_[_round_tick(p0, tick), C[:-1]]
    Hh = np.maximum(_round_tick(np.exp(mx), tick), np.maximum(O, C))
    Ll = np.minimum(_round_tick(np.exp(mn), tick), np.minimum(O, C))
    idx = pd.date_range(_U(start), periods=n, freq="min").as_unit("ns")
    return pd.DataFrame({"open": O, "high": Hh, "low": Ll, "close": C, "trades": np.full(n, 10, np.int64)}, index=idx)


def _slow_ref(minutes: pd.DataFrame, lv, q, h0, touch: bool, maker: float = 0.0):
    """Pure-Python re-implementation of the 1-minute fill rules (independent of the kernel): returns the list of fills
    (minute index, side, px, open_through) and the final (Q, C, fees)."""
    lv = list(map(float, lv))
    G = len(lv) - 1
    h = [int(x) for x in h0]
    placed = [-1] * G
    Q = C = fees = 0.0
    fills = []
    O, Hh, L, Cc, Tr = (minutes[c].to_numpy() for c in ("open", "high", "low", "close", "trades"))

    def fill(m, i, side, px, ot):
        nonlocal Q, C, fees
        Q += side * q
        C -= side * q * px
        fees += q * px * maker
        h[i] = 1 if side > 0 else 0
        placed[i] = m
        fills.append((m, side, px, ot))

    def through_below(level, price):
        return price <= level if touch else price < level

    def through_above(level, price):
        return price >= level if touch else price > level

    for m in range(len(O)):
        if Tr[m] <= 0:
            continue
        o, hi, lo, c = float(O[m]), float(Hh[m]), float(L[m]), float(Cc[m])
        for i in range(G):                                    # open beyond an eligible order
            if h[i] == 0 and placed[i] < m and through_below(lv[i], o):
                fill(m, i, +1, o, lv[i] != o)
        for i in range(G):
            if h[i] == 1 and placed[i] < m and through_above(lv[i + 1], o):
                fill(m, i, -1, o, lv[i + 1] != o)
        near_high = (c - lo) - (hi - c) > TIE_REL * abs(c)          # exact ties (float noise) -> O->H->L->C
        path = [o, lo, hi, c] if near_high else [o, hi, lo, c]
        for a, b in zip(path[:-1], path[1:]):
            if b < a:
                for i in sorted(range(G), key=lambda k: -lv[k]):
                    if h[i] == 0 and placed[i] < m and lv[i] <= a and through_below(lv[i], b):
                        fill(m, i, +1, lv[i], False)
            elif b > a:
                for i in sorted(range(G), key=lambda k: lv[k + 1]):
                    if h[i] == 1 and placed[i] < m and lv[i + 1] >= a and through_above(lv[i + 1], b):
                        fill(m, i, -1, lv[i + 1], False)
    return fills, Q, C, fees


def _close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# ============================================================================ self-tests
def _test_hand(say):
    """Hand-built path: known fills and P&L, the same-minute no-refill rule, through vs touch, an outage minute,
    an open-through fill, the 00:00 mark."""
    bars = [
        (101.0, 101.2, 100.8, 101.1),            # m0 deploy at 101.0: pivot level 1 -> buy@100, sell@102
        (101.1, 101.3, 99.9, 100.2),             # m1 O->H->L->C: buy 100 (sell@101 placed m1)
        (100.2, 101.05, 100.1, 101.0),           # m2 O->L->H->C: sell 101 (round trip +1)
        (101.0, 101.1, 99.5, 99.6),              # m3: buy 100 (sell@101 placed m3)
        (99.6, 101.5, 99.55, 101.4),             # m4: sell 101 (buy@100 placed m4)
        (101.4, 101.45, 99.0, 101.3),            # m5: buy 100; its sell@101 (placed m5) must NOT fill at 101.45
        (101.3, 101.35, 101.2, 101.25),          # m6: opens above 101 -> the sell fills at the open (101.3)
        (101.25, 101.3, 100.0, 100.1),           # m7: low == 100: no fill (through); fill (touch)
        (100.1, 100.2, 99.0, 99.5, 0),           # m8: outage: no fill
        (100.2, 100.3, 100.15, 100.25),          # m9: no fill
        (100.25, 100.3, 100.2, 100.3),           # m10: mark
    ]
    M = _mins("2025-03-03 23:55", bars)          # crosses 00:00 at m5
    lv = np.array([100.0, 101.0, 102.0])
    r = run_grid(M, lv, 1.0, cfg_fees="base", fill="through", mmr=0.0)
    F = r["fills"]
    lvl = F[F.kind.isin(["buy", "sell"])]
    got = list(zip(lvl.minute.dt.minute.tolist(), lvl.kind.tolist(), lvl.px.round(6).tolist()))
    want = [(56, "buy", 100.0), (57, "sell", 101.0), (58, "buy", 100.0), (59, "sell", 101.0), (0, "buy", 100.0),
            (1, "sell", 101.3)]
    assert got == want, got
    assert lvl.open_through.tolist() == [False] * 5 + [True]
    assert _close(r["deployments"].open_through_gain.iat[0], 0.3)      # sold at the open 101.3, level 101
    d = r["deployments"].iloc[0]
    fee = 0.0002 * (100 + 101 + 100 + 101 + 100 + 101.3)
    assert _close(d.grid_profit, 3.3) and d.n_round_trips == 3, (d.grid_profit, d.n_round_trips)
    assert _close(d.fees, fee) and _close(d.net, 3.3 - fee), (d.fees, d.net)
    assert _close(d.inventory_pnl, 0.0, 1e-9)
    assert not r["fills_audit"], r["fills_audit"]
    # the 00:00 mark (minute 5 opens at 00:00): inventory 0 after m4, cum = 2 - fees of 4 fills, at m4's close
    by = r["daily_by_dep"]
    mk = by[by.time == _U("2025-03-04")].cum.iloc[0]
    assert _close(mk, 2.0 - 0.0002 * 402), mk
    assert _close(r["daily_pnl"].sum(), d.net)
    # touch: m7's low at the level fills; the outage minute m8 still fills nothing
    r2 = run_grid(M, lv, 1.0, cfg_fees="base", fill="touch", mmr=0.0)
    F2 = r2["fills"]
    lvl2 = F2[F2.kind.isin(["buy", "sell"])]
    got2 = list(zip(lvl2.minute.dt.minute.tolist(), lvl2.kind.tolist(), lvl2.px.round(6).tolist()))
    assert got2 == want + [(2, "buy", 100.0)], got2
    d2 = r2["deployments"].iloc[0]
    fee2 = fee + 0.0002 * 100
    assert _close(d2.net, 3.3 - 100 + 100.3 - fee2), d2.net
    assert d2.open_at_end and _close(r2["res"]["Q_end"], 1.0)
    assert not r2["fills_audit"]
    # an outage minute that crosses a level does not fill even with touch; the next live minute below the level does
    bars3 = [(100.5, 100.6, 100.4, 100.5), (100.5, 100.5, 99.0, 99.5, 0), (99.5, 99.6, 99.4, 99.5)]
    r3 = run_grid(_mins("2025-03-03 10:00", bars3), lv, 1.0, cfg_fees="zero", fill="touch", mmr=0.0)
    F3 = r3["fills"]
    assert len(F3) == 1 and F3.minute.iat[0] == _U("2025-03-03 10:02") and F3.px.iat[0] == 99.5 and \
        F3.open_through.iat[0], F3
    say("  hand path: fills, no-refill, through vs touch, outage, open-through, 00:00 mark ok")


def _test_liquidation(say):
    """A crash minute loads the long side; the hour's mark low takes equity below maintenance -> liquidated at the
    hour's close, losing the margin, although the price recovers (and the grid sells) before the hour ends."""
    lv = np.array([90.0, 92.0, 94.0, 96.0, 98.0, 100.0])
    bars = [(100.0, 100.05, 99.95, 100.0)] * 5 + [(100.0, 100.1, 85.0, 86.0)]
    px = 86.0
    for k in range(24):
        nxt = min(px + 0.6, 99.0)
        bars.append((px, nxt + 0.05, px - 0.05, nxt))
        px = nxt
    bars += [(99.0, 99.05, 98.95, 99.0)] * (60 - len(bars))
    bars += [(99.0, 99.05, 98.95, 99.0)] * 30
    M = _mins("2025-03-03 10:00", bars)
    H = _hours_for(M, mark_low={"2025-03-03 10:00": 85.5})
    r = run_grid(M, lv, 1.0, sleeve_margin=30.0, cfg_fees="zero", hours=H, mmr=0.005)
    d = r["deployments"].iloc[0]
    assert d.liquidated and d.end == _U("2025-03-03 11:00") and _close(d.net, -30.0), d
    F = r["fills"]
    assert (F.kind == "liq").sum() == 1 and F[F.kind == "liq"].time.iat[0] == _U("2025-03-03 11:00")
    assert not r["fills_audit"], r["fills_audit"]
    # the end-of-hour state alone (inventory 1 after the recovery) would not breach: the snapshot decides
    Qs, Cs = 5.0, -(98 + 96 + 94 + 92 + 90.0)
    assert 30 + Cs + Qs * 85.5 < 0.005 * Qs * 85.5
    lvl = F[F.kind.isin(["buy", "sell"])]
    Q_end = lvl.qty.sum()
    C_end = -(lvl.qty * lvl.px).sum()
    assert Q_end < 5 and 30 + C_end + Q_end * 85.5 > 0.005 * Q_end * 85.5, (Q_end, C_end)
    # a milder dip (mark low 95) does not liquidate
    bars2 = [(100.0, 100.05, 99.95, 100.0)] * 5 + [(100.0, 100.1, 95.0, 95.5)] + [(95.5, 95.6, 95.4, 95.5)] * 84
    M2 = _mins("2025-03-03 10:00", bars2)
    H2 = _hours_for(M2, mark_low={"2025-03-03 10:00": 95.2})
    r2 = run_grid(M2, lv, 1.0, sleeve_margin=30.0, cfg_fees="zero", hours=H2, mmr=0.005)
    assert not r2["deployments"].liquidated.iat[0]
    say("  liquidation on a crash: liquidated once at the hour close, -margin, snapshot at the low ok")


def _test_funding(say):
    """Funding on net inventory at the print, at the hour's mark open; a grid closed at that open pays it."""
    lv = np.array([98.0, 99.0, 100.0, 101.0, 102.0])
    bars = [(100.0, 100.1, 99.9, 100.0), (100.0, 100.0, 97.9, 98.6)] + [(98.6, 98.7, 98.5, 98.6)] * 58 + \
        [(98.7, 98.8, 98.6, 98.7)] * 5
    M = _mins("2025-03-03 10:00", bars)
    H = _hours_for(M, funding={"2025-03-03 11:00": 0.001}, mark_open={"2025-03-03 11:00": 98.65})
    r = run_grid(M, lv, 2.0, cfg_fees="zero", hours=H, mmr=0.0)
    d = r["deployments"].iloc[0]
    # pivot at 100 (level 2): buys at 99 and 98 fill in minute 1 -> Q = 4 at the 11:00 print
    assert _close(d.funding, 0.001 * 4.0 * 98.65), d.funding
    r2 = run_grid(M, lv, 2.0, cfg_fees="base", hours=H, mmr=0.0, end_mode="open", end_time="2025-03-03 11:00")
    d2 = r2["deployments"].iloc[0]
    assert _close(d2.funding, 0.001 * 4.0 * 98.65) and d2.end == _U("2025-03-03 11:00")
    tk = be.TAKER["base"] + be.SLIP_OTHER
    cl = r2["fills"][r2["fills"].kind == "close"]
    assert len(cl) == 1 and _close(cl.px.iat[0], 98.7) and _close(cl.fee.iat[0], 4.0 * 98.7 * tk)
    say("  funding on net inventory at the print (closed-at-the-open grid pays it) ok")


def _test_random_vs_slow(say, n=120, seed=5):
    """Kernel vs an independent pure-Python implementation on random minute paths (gaps, outages, wide minutes)."""
    rng = np.random.default_rng(seed)
    for k in range(n):
        nm = int(rng.integers(30, 200))
        px = 100.0
        bars = []
        for _ in range(nm):
            o = round(px + (rng.normal(0, 0.4) if rng.random() < 0.15 else 0.0), 2)
            c = round(o * np.exp(rng.normal(0, 0.006)), 2)
            hi = round(max(o, c) + abs(rng.normal(0, 0.3)), 2)
            lo = round(min(o, c) - abs(rng.normal(0, 0.3)), 2)
            if rng.random() < 0.1:
                hi = round(hi + rng.choice([0.0, 0.5, 1.0]), 2)
                lo = round(lo - rng.choice([0.0, 0.5, 1.0]), 2)
            trd = 0 if rng.random() < 0.05 else 5
            bars.append((o, hi, lo, c, trd))
            px = c
        M = _mins("2025-03-03 10:00", bars)
        lv = np.round(np.linspace(96.0, 104.0, int(rng.integers(3, 17))), 2)
        q = 0.5
        for touch in (False, True):
            r = run_grid(M, lv, q, cfg_fees="base", fill="touch" if touch else "through", mmr=0.0)
            F = r["fills"]
            F = F[F.kind.isin(["buy", "sell"])]
            got = [(int(m), 1 if kd == "buy" else -1, round(float(p), 8), bool(ot))
                   for m, kd, p, ot in zip(F.m, F.kind, F.px, F.open_through)]
            fills, Q, C, fees = _slow_ref(M, lv, q, r["h0"], touch, be.MAKER["base"])
            want = [(m, s, round(p, 8), bool(ot)) for m, s, p, ot in fills]
            assert sorted(got) == sorted(want), (k, touch, got[:10], want[:10])
            d = r["deployments"].iloc[0]
            last = float(M.close.iloc[-1])
            assert _close(d.net, C + Q * last - fees, 1e-9), (k, d.net, C + Q * last - fees)
            assert not r["fills_audit"], r["fills_audit"]
    say(f"  kernel = independent pure-Python fill rules on {n} random paths x (through, touch) ok")


def _test_perp_end(say):
    """A perpetual's last bar (perp_end) force-closes an open G-A / G-0 grid at that bar's close, taker + slippage,
    and nothing trades in the non-tradable hours after it."""
    closes = [100.0, 101.0] * 50
    D = _daily_bars_frame(closes, "2024-12-22")
    M = _wave_minutes("2025-03-03", 6)
    H = _hours_for(M)
    H.loc[_U("2025-03-05 16:00"), "perp_end"] = True
    H.loc[H.index > _U("2025-03-05 16:00"), "tradable"] = False
    tk = be.TAKER["base"] + be.SLIP_OTHER
    for name, r in (("G-A", grid_ga("SYN", None, daily_bars=D, start="2025-03-03", end="2025-03-08", minutes=M,
                                    hours=H, tick=0.001)),
                    ("G-0", grid_g0("SYN", start="2025-03-03", end="2025-03-08", minutes=M, hours=H, tick=0.001))):
        G = r["deployments"]
        assert len(G) == 1 and G.reason.iat[0] == "perp_end" and G.end.iat[0] == _U("2025-03-05 17:00"), (name, G)
        F = r["fills"]
        lvl = F[F.kind.isin(["buy", "sell"])]
        assert abs(lvl.qty.sum()) > 0, name                    # inventory held at the perpetual's last bar
        cl = F[F.kind == "close"]
        last = M.loc[_U("2025-03-05 16:59")]
        assert len(cl) == 1 and _close(cl.px.iat[0], last.close) and _close(cl.fee.iat[0], abs(cl.qty.iat[0]) *
                                                                             cl.px.iat[0] * tk), (name, cl)
        assert not (F.time > _U("2025-03-05 17:00")).any() and not r["fills_audit"], name
    say("  perp_end: G-A and G-0 force-closed at the last bar's close (taker + slippage), nothing after ok")


def _daily_bars_frame(closes, start, high_off=0.2, low_off=0.2) -> pd.DataFrame:
    idx = pd.date_range(_U(start), periods=len(closes), freq="D").as_unit("ns")
    c = np.asarray(closes, float)
    return pd.DataFrame({"open": c, "high": c + high_off, "low": c - low_off, "close": c,
                         "known_at": idx + pd.Timedelta("1D"), "seg": 0}, index=idx)


def _wave_minutes(start, days, base=100.5, amp=0.6, period_min=360, seed=0) -> pd.DataFrame:
    n = int(days) * 1440
    t = np.arange(n + 1)
    p = np.round(base + amp * np.sin(2 * np.pi * t / period_min), 3)
    O, C = p[:-1], p[1:]
    idx = pd.date_range(_U(start), periods=n, freq="min").as_unit("ns")
    return pd.DataFrame({"open": O, "high": np.maximum(O, C) + 0.001, "low": np.minimum(O, C) - 0.001,
                         "close": C, "trades": np.full(n, 5, np.int64)}, index=idx)


def _test_ga(say):
    """G-A rules on synthetic daily bars and minutes: deployment at the close's next minute, levels and size, (c) 14
    days with redeployment at the same open, (a) R0's entry hour, the flat-slot test, (b) a close below the lower
    band, the window end; daily P&L = sum of nets; audit."""
    closes = [100.0, 101.0] * 50                               # 2024-12-22 .. 2025-03-31: SMA 100.5, sd 0.5
    D = _daily_bars_frame(closes, "2024-12-22")
    D.loc[_U("2025-03-27"), ["open", "high", "low", "close"]] = [100.0, 100.2, 89.8, 90.0]
    M = _wave_minutes("2025-03-03", 29)
    r0 = pd.DataFrame({"entry1_time": [_U("2025-03-20 10:00")], "exit_time": [_U("2025-03-24 17:00")]})
    r = grid_ga("SYN", r0, daily_bars=D, cfg_fees="base", start="2025-03-03", end="2025-03-31", minutes=M,
                tick=0.001, mmr=0.005)
    G = r["deployments"]
    assert list(G.reason) == ["14_days", "r0_entry", "below_lower_band", "window_end"], list(G.reason)
    assert list(G.start) == [_U("2025-03-03"), _U("2025-03-17"), _U("2025-03-25"), _U("2025-03-29")], list(G.start)
    assert list(G.end) == [_U("2025-03-17"), _U("2025-03-20 10:00"), _U("2025-03-28"), _U("2025-04-01")], list(G.end)
    # first grid: bands of the bar of 2025-03-02 (known 03-03 00:00): closes alternate -> SMA 100.5, sd 0.5
    I = daily_indicators(D)
    b = I.loc[_U("2025-03-02")]
    assert _close(b.ub, 101.5) and _close(b.lb, 99.5)
    g0 = G.iloc[0]
    Gn = int(np.floor(np.log(101.5 / 99.5) / np.log(1.005) + 1e-9))
    assert g0.n_int == Gn and _close(g0.lo, 99.5) and _close(g0.hi, 101.5)
    P0 = float(M.open.iloc[0])
    assert _close(g0.q, 1.0 / (Gn * P0)) and _close(g0.notional, 1.0) and _close(g0.margin, 1.0 / 3)
    # (b): the bar of 03-27 closes at 90 < its lower band; no redeploy at 03-28 (90 < 0.95 x the 60-day high)
    b27 = I.loc[_U("2025-03-27")]
    assert b27.close < b27.lb and b27.close < 0.95 * b27.hi60
    # closes at the open with taker + slippage
    F = r["fills"]
    cl = F[F.kind == "close"]
    tk = be.TAKER["base"] + be.SLIP_OTHER
    for _, c in cl.iterrows():
        mrow = M.loc[c.minute]
        assert c.time == c.minute and _close(c.px, mrow.open) and _close(c.fee, abs(c.qty) * c.px * tk)
    assert set(cl.minute) <= {_U("2025-03-17"), _U("2025-03-20 10:00"), _U("2025-03-28")}
    # nothing traded while R0 held the slot
    held = (F.time > _U("2025-03-20 10:00")) & (F.time < _U("2025-03-25"))
    assert not held.any()
    assert G.n_fills.sum() > 50
    assert _close(r["daily_pnl"].sum(), G.net.sum(), 1e-9) and not r["fills_audit"], r["fills_audit"]
    # P&L identity per deployment from the fills
    for _, g in G.iterrows():
        f = F[F.dep == g.dep]
        cash = -(f.qty * f.px).sum()
        Qe = f.qty.sum()
        last = g.p_end if g.open_at_end else 0.0
        assert _close(cash + Qe * last - f.fee.sum() - g.funding, g.net, 1e-9), (g.dep, g.net)
    # lb_rule="deploy": the 03-27 close (90) is below the grid's floor too, same reasons here
    rd = grid_ga("SYN", r0, daily_bars=D, cfg_fees="base", start="2025-03-03", end="2025-03-31", minutes=M,
                 tick=0.001, lb_rule="deploy")
    assert list(rd["deployments"].reason) == list(G.reason)
    # merge_ga + bb_engine.assemble: one slot (K = 1), equity0 = 1 -> equity change = sum of nets (sleeve = 1)
    r0res = {"trades": pd.DataFrame(columns=["sym", "pos", "entry1_time", "exit_time", "ret", "L_used", "side",
                                             "liquidated"]),
             "daily_mtm": pd.DataFrame(columns=["pos", "time", "mtm", "margin", "notional", "sym"])}
    mg = merge_ga(r0res, r)
    acc = be.assemble({"SYN": mg}, be.ROWS["R0"], "2025-03-03", "2025-03-31", k_slots=1)
    eq = acc["equity"]
    assert _close(eq.iloc[-1] - 1.0, G.net.sum(), 1e-6), (eq.iloc[-1], G.net.sum())
    cum = r["cum"].reindex(eq.index)
    assert np.allclose(eq.to_numpy() - 1.0, cum.to_numpy(), atol=1e-9), (eq.head(), cum.head())
    # regression (review finding 6): merge_ga divides by grid_ga's sleeve, so the account is the same at sleeve 2
    r2 = grid_ga("SYN", r0, daily_bars=D, cfg_fees="base", start="2025-03-03", end="2025-03-31", minutes=M,
                 tick=0.001, mmr=0.005, sleeve=2.0)
    assert _close(r2["deployments"].net.sum(), 2.0 * G.net.sum(), 1e-9)
    acc2 = be.assemble({"SYN": merge_ga(r0res, r2)}, be.ROWS["R0"], "2025-03-03", "2025-03-31", k_slots=1)
    assert np.allclose(acc2["equity"].to_numpy(), eq.to_numpy(), atol=1e-9), (acc2["equity"].tail(), eq.tail())
    say(f"  G-A: deploy / (c) 14 days + redeploy / (a) R0 entry / flat slot / (b) below band / window end, "
        f"{int(G.n_fills.sum())} fills, merge_ga + assemble ok")


def _test_gb(say):
    """G-B on a hand-made R0 position: entry + add tranches as long-mode grids over [S, TP], 20 levels; the stop
    minute cuts the path at S and closes everything at R0's stop price."""
    S, TP = 95.0, 115.0
    n = 2 * 1440
    t0 = _U("2025-03-03 10:00")
    px = np.empty(n + 1)
    px[:241] = np.linspace(100.0, 104.0, 241)                   # 10:00 -> 14:00 up to 104
    px[241:301] = np.linspace(104.0, 102.0, 60)                 # 14:00 -> 15:00 back to 102
    k_stop = 22 * 60 + 23                                       # 2025-03-04 08:23
    px[301:k_stop + 1] = np.linspace(102.0, 95.3, k_stop - 300)
    px[k_stop + 1:] = 94.0
    px = np.round(px, 3)
    O, C = px[:-1].copy(), px[1:].copy()
    Hh = np.maximum(O, C) + 0.001
    Ll = np.minimum(O, C) - 0.001
    Ll[k_stop], C[k_stop], Hh[k_stop] = 94.8, 94.9, max(O[k_stop], 94.9) + 0.001
    idx = pd.date_range(t0, periods=n, freq="min").as_unit("ns")
    M = pd.DataFrame({"open": O, "high": Hh, "low": Ll, "close": C, "trades": 5}, index=idx)
    t_stop = idx[k_stop] + pd.Timedelta("1min")
    trades = pd.DataFrame({"pos": [0], "side": [1], "entry1_time": [t0], "S": [S], "TP": [TP], "L_used": [3.0],
                           "exit_time": [t_stop], "exit_px": [94.9], "exit_reason": ["stop"], "ret": [-0.05]})
    tranches = pd.DataFrame({"pos": [0, 0, 0], "kind": ["entry", "add", "stop"],
                             "time": [t0, _U("2025-03-03 15:00"), t_stop],
                             "px": [float(M.open.iloc[0]), float(M.loc[_U("2025-03-03 15:00")].open), 94.9],
                             "frac": [1 / 3, 1 / 3, 2 / 3], "minute": [-1, -1, 1234]})
    r = grid_gb("SYN", trades, tranches, cfg_fees="base", start="2025-03-03", end="2025-03-05", minutes=M,
                tick=0.001, mmr=0.005)
    D = r["deployments"]
    assert len(D) == 2 and (D.reason == "stop").all() and (D.end == t_stop).all(), D
    lv = geometric_levels(S, TP, 19, 0.001)
    assert len(lv) == 20 and lv[0] == S and lv[-1] == TP
    F = r["fills"]
    tk = be.TAKER["base"] + be.SLIP_OTHER
    for j, (_, d) in enumerate(D.iterrows()):
        px0 = float(tranches.px.iat[j])
        k = int(np.argmin(np.abs(np.log(lv / px0))))
        q = (1 / 3) / (19 * px0)
        assert _close(d.q, q) and _close(d.Q0, q * (19 - k)) and _close(d.margin, (1 / 3) / 3.0)
        f = F[F.dep == d.dep]
        ini = f[f.kind == "init"]
        assert len(ini) == 1 and _close(ini.qty.iat[0], q * (19 - k))
        assert _close(ini.fee.iat[0], q * (19 - k) * px0 * tk)
        cl = f[f.kind == "close"]
        # at the stop every interval above S is loaded (the buy at S itself needs a print below S before the cut)
        assert len(cl) == 1 and _close(cl.px.iat[0], 94.9) and _close(-cl.qty.iat[0], q * 18), (cl, q * 18)
        assert cl.time.iat[0] == t_stop
        assert not (f.kind.isin(["buy", "sell"]) & (f.px <= S)).any()
        cash = -(f.qty * f.px).sum()
        assert _close(cash - f.fee.sum() - d.funding, d.net, 1e-9)
    T = r["trades"]
    assert len(T) == 1 and _close(T.ret.iat[0], D.net.sum()) and _close(T.ret_r0.iat[0], -0.05)
    assert not r["fills_audit"], r["fills_audit"]
    dm = r["daily_mtm"]
    assert len(dm) == 1 and dm.time.iat[0] == _U("2025-03-04") and _close(dm.margin.iat[0], 2 / 9)
    # bb_engine.assemble on the engine-format output: one slot, M = L_used x sleeve = 3 -> equity 1 + 3 x ret
    acc = be.assemble({"SYN": {"trades": T, "daily_mtm": dm}}, be.ROWS["R0"], "2025-03-03", "2025-03-05", k_slots=1)
    eq = acc["equity"]
    assert _close(eq.iloc[-1], 1.0 + 3.0 * T.ret.iat[0], 1e-9) and _close(eq.loc[_U("2025-03-04")], 1.0 + 3.0 *
                                                                           dm.mtm.iat[0], 1e-9), eq
    say("  G-B: tranche grids over [S, TP] (20 levels), initial inventory, stop cut at S, engine-format output ok")


def _test_g0(say):
    """G-0: +/-10% around the open, 40 intervals of 0.5%, re-centred each Monday 00:00 UTC."""
    M = _wave_minutes("2025-03-05 06:00", 9, base=100.0, amp=3.0, period_min=1440)
    r = grid_g0("SYN", cfg_fees="vip", start="2025-03-05", end="2025-03-14", minutes=M, tick=0.001)
    D = r["deployments"]
    assert list(D.reason) == ["weekly", "window_end"], list(D.reason)
    assert D.start.iat[0] == _U("2025-03-05 06:00") and D.end.iat[0] == _U("2025-03-10")
    assert D.start.iat[1] == _U("2025-03-10")
    P1 = float(M.loc[_U("2025-03-10")].open)
    assert _close(D.lo.iat[1], 0.9 * P1) and _close(D.hi.iat[1], 1.1 * P1)
    assert (D.n_int == 40).all()
    assert _close(r["daily_pnl"].sum(), D.net.sum(), 1e-9) and not r["fills_audit"]
    say("  G-0: +/-10%, 40 intervals, weekly re-centre ok")


def _test_mark_funding(say):
    """Regression (review finding 1): the 00:00 mark is taken after the 00:00 funding print (choice 13, bb_engine's
    order), so the print is booked on the day it is paid."""
    lv = np.array([98.0, 99.0, 100.0, 101.0, 102.0])
    bars = [(100.0, 100.1, 99.9, 100.0), (100.0, 100.0, 97.9, 98.6)] + [(98.6, 98.7, 98.5, 98.6)] * 120
    M = _mins("2025-03-03 23:00", bars)                       # crosses 00:00 at minute 60
    H = _hours_for(M, funding={"2025-03-04 00:00": 0.01}, mark_open={"2025-03-04 00:00": 98.6})
    r = run_grid(M, lv, 1.0, cfg_fees="zero", hours=H, mmr=0.0)
    d = r["deployments"].iloc[0]
    Q, cash = 2.0, -(99.0 + 98.0)                             # buys at 99 and 98 in minute 1
    fund = 0.01 * Q * 98.6
    assert _close(d.funding, fund), d.funding
    mk = r["daily_by_dep"].set_index("time").cum
    assert _close(mk.loc[_U("2025-03-04")], cash + Q * 98.6 - fund), mk
    assert _close(r["cum"].loc[_U("2025-03-04")], cash + Q * 98.6 - fund)
    assert _close(r["daily_pnl"].loc[_U("2025-03-03")], cash + Q * 98.6 - fund)      # paid on 03-03's day
    say("  00:00 mark after the 00:00 funding print ok")


def _test_injection(say):
    """Regression (review finding 2): injected minutes never pick up a coin's real hours or daily bars from disk;
    hours='disk' does, and hours that disagree with the minutes in price level raise."""
    M = _gbm_minutes(4 * 1440, 0.02 / np.sqrt(1440), 7, "2025-03-03")          # a synthetic coin around 100
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r = grid_g0("BTC", start="2025-03-03", end="2025-03-06", minutes=M, tick=0.001, mmr=0.004)
    assert r["log"]["hours_source"] == "none" and r["deployments"].funding.abs().sum() == 0.0
    assert not r["deployments"].liquidated.any()
    assert any("without hours" in str(x.message) for x in w), [str(x.message) for x in w]
    r1 = grid_g0("BTC", start="2025-03-03", end="2025-03-06", minutes=M, tick=0.001, mmr=0.004, hours="none")
    assert _same_rows(r1["fills"], r["fills"])               # same as an explicit 'none'
    for kw, what in (({"hours": "disk"}, "disk hours of BTC vs synthetic minutes"),
                     ({"hours": _hours_for(M.assign(**{c: M[c] * 1.5 for c in bd.PX}))}, "hours of x 1.5 prices")):
        try:
            grid_g0("BTC", start="2025-03-03", end="2025-03-06", minutes=M, tick=0.001, mmr=0.004, **kw)
        except ValueError as e:
            assert "disagree in price level" in str(e), e
        else:
            raise AssertionError(f"mixed inputs not refused: {what}")
    H = _hours_for(M)
    rh = grid_g0("BTC", start="2025-03-03", end="2025-03-06", minutes=M, hours=H, tick=0.001, mmr=0.004)
    assert rh["log"]["hours_source"] == "injected" and rh["log"]["hours_price_mismatch"] == 0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            grid_ga("BTC", None, start="2025-03-03", end="2025-03-06", minutes=M, tick=0.001)
    except ValueError as e:
        assert "daily_bars" in str(e), e
    else:
        raise AssertionError("G-A with injected minutes loaded daily bars from disk")
    say("  injection: injected minutes self-contained (no disk hours / bars), hours='disk' and mismatched hours "
        "refused ok")


def _test_ties(say):
    """Regression (review finding 5): exact decimal ties (close equidistant from high and low on the tick grid) take
    O->H->L->C despite float rounding; checked on the path rule and on a G-B stop cut, where the order decides the
    fills (a tie minute rising to a sell level before falling to S fills that sell first)."""
    for hi, lo, c in ((0.3, 0.1, 0.2), (99.3, 94.5, 96.9), (101.3, 101.1, 101.2), (60123.45, 60123.25, 60123.35)):
        assert not _nearer_high(hi, lo, c), (hi, lo, c)
    assert _nearer_high(99.3, 94.5, 96.91) and not _nearer_high(99.3, 94.5, 96.89)
    assert (99.3 - 96.9) < (96.9 - 94.5)                       # the float comparison would misroute this tie
    lv = np.array([95.0, 96.0, 97.0, 98.0, 99.0, 100.0])
    M = _mins("2025-03-03 10:00", [(97.5, 97.6, 97.4, 97.5), (97.5, 99.3, 94.5, 96.9), (96.9, 97.0, 96.8, 96.9)])
    r = run_grid(M, lv, 1.0, mode="long", cfg_fees="zero", mmr=0.0, end_mode="stop", end_time="2025-03-03 10:01",
                 end_px=94.9, cut=95.0)
    F = r["fills"]
    lvl = F[F.kind.isin(["buy", "sell"])]
    got = list(zip(lvl.kind, lvl.px))
    assert got == [("sell", 99.0), ("buy", 97.0), ("buy", 96.0)], got        # O -> H (sell 99) -> L (cut at 95)
    cl = F[F.kind == "close"]
    assert len(cl) == 1 and _close(-cl.qty.iat[0], 3.0) and _close(cl.px.iat[0], 94.9), cl
    assert not r["fills_audit"], r["fills_audit"]
    say("  path ties: exact decimal ties take O->H->L->C (rule and G-B stop cut) ok")


def _gb_case_minutes(days=3, start="2025-03-03 10:00"):
    n = days * 1440
    idx = pd.date_range(_U(start), periods=n, freq="min").as_unit("ns")
    p = np.round(100 + 2 * np.sin(np.arange(n + 1) * 2 * np.pi / 600), 3)
    return pd.DataFrame({"open": p[:-1], "high": np.maximum(p[:-1], p[1:]) + 0.01,
                         "low": np.minimum(p[:-1], p[1:]) - 0.01, "close": p[1:], "trades": 5}, index=idx)


def _test_gb_account(say):
    """Regression (review findings 3 and 4): grid_gb's engine-format output keeps every R0 position (unwrapped ones,
    e.g. S11 shorts or positions before the window, unchanged with R0's 00:00 marks), and a position whose R0 exit
    falls after the window's end is marked at the window's last minute (every exit kind), not dropped or stopped."""
    M = _gb_case_minutes()
    t0 = _U("2025-03-03 10:00")
    x0, x1 = _U("2025-03-04 17:00"), _U("2025-03-05 17:00")
    trades = pd.DataFrame({"pos": [0, 1, 2], "side": [1, -1, 1],
                           "entry1_time": [t0, _U("2025-03-04 18:00"), _U("2025-02-20 10:00")],
                           "S": [95.0, 105.0, 90.0], "TP": [115.0, 85.0, 120.0], "L_used": [3.0, 3.0, 3.0],
                           "exit_time": [x0, x1, _U("2025-02-25 17:00")], "exit_px": [101.0, 99.0, 95.0],
                           "exit_reason": ["mid", "mid", "mid"], "ret": [0.01, 0.02, -0.03], "open_at_end": False,
                           "liquidated": False})
    tranches = pd.DataFrame({"pos": [0, 0, 1, 1, 2, 2], "kind": ["entry", "exit"] * 3,
                             "time": [t0, x0, _U("2025-03-04 18:00"), x1, _U("2025-02-20 10:00"),
                                      _U("2025-02-25 17:00")],
                             "px": [100.0, 101.0, 101.5, 99.0, 100.0, 95.0], "frac": [1 / 3] * 6, "minute": -1})
    dm0 = pd.DataFrame({"pos": [0, 1], "time": [_U("2025-03-04"), _U("2025-03-05")], "mtm": [0.003, 0.004],
                        "margin": 1 / 9, "notional": 1 / 3, "sym": "SYN"})
    r = grid_gb("SYN", trades, tranches, start="2025-03-03", end="2025-03-05", minutes=M, tick=0.001, mmr=0.005,
                r0_daily_mtm=dm0)
    T = r["trades"]
    assert list(T.pos) == [0, 1, 2] and list(T.gb_wrapped) == [True, False, False], T
    assert list(T.gb_skip) == ["", "skipped_short", "skipped_outside"]
    assert _close(T.ret.iat[1], 0.02) and _close(T.ret.iat[2], -0.03) and _close(T.ret_r0.iat[0], 0.01)
    assert r["log"]["passthrough"] == 2 and r["log"]["wrapped"] == 1
    dm = r["daily_mtm"]
    s1 = dm[dm.pos == 1]
    assert len(s1) == 1 and s1.time.iat[0] == _U("2025-03-05") and _close(s1.mtm.iat[0], 0.004)
    assert not (dm.pos == 0).any() or (dm[dm.pos == 0].mtm != 0.003).all()   # pos 0's marks are the grids'
    acc = be.assemble({"SYN": {"trades": T, "daily_mtm": dm}}, be.ROWS["R0"], "2025-03-03", "2025-03-05", k_slots=1)
    assert list(acc["trades"].pos) == [0, 1]
    eq = acc["equity"]
    assert _close(eq.iloc[-1], 1.0 + 3.0 * (T.ret.iat[0] + 0.02), 1e-9), (eq.iloc[-1], T.ret.iat[0])
    assert _close(eq.loc[_U("2025-03-05")], 1.0 + 3.0 * (T.ret.iat[0] + 0.004), 1e-9)
    # R0 exits after the G-B window (window ends 2025-03-05, minutes run to 03-06 09:59): every kind is marked
    last = M.loc[_U("2025-03-05 23:59")]
    for kind, xt, xpx, mcode in (("exit", _U("2025-03-07 17:00"), 101.0, -1), ("stop", _U("2025-03-07 03:12"), 94.9, 9),
                                 ("stop", _U("2025-03-07 04:00"), 94.9, -2)):
        tr1 = pd.DataFrame({"pos": [0], "side": [1], "entry1_time": [t0], "S": [95.0], "TP": [115.0],
                            "L_used": [3.0], "exit_time": [xt], "exit_px": [xpx],
                            "exit_reason": ["mid" if kind == "exit" else "stop"], "ret": [0.0], "open_at_end": False,
                            "hold_h": [(xt - t0) / pd.Timedelta("1h")]})
        tq = pd.DataFrame({"pos": [0, 0, 0], "kind": ["entry", "add", kind],
                           "time": [t0, _U("2025-03-06 05:00"), xt], "px": [float(M.open.iloc[0]), 100.5, xpx],
                           "frac": [1 / 3, 1 / 3, 2 / 3], "minute": [-1, -1, mcode]})
        rr = grid_gb("SYN", tr1, tq, start="2025-03-03", end="2025-03-05", minutes=M, tick=0.001, mmr=0.005,
                     r0_daily_mtm=dm0.iloc[:0])
        D = rr["deployments"]
        assert len(D) == 1 and D.reason.iat[0] == "window_end" and bool(D.open_at_end.iat[0]), (kind, D)
        assert D.end.iat[0] == _U("2025-03-06") and _close(D.p_end.iat[0], last.close), (kind, D)
        F = rr["fills"]
        assert not (F.kind == "close").any() and not rr["fills_audit"], kind
        assert rr["log"]["window_end_marked"] == 1 and rr["log"]["tranches_not_wrapped"] == 1   # the 03-06 add
        f = F[F.dep == 0]
        assert _close(-(f.qty * f.px).sum() + f.qty.sum() * last.close - f.fee.sum() - D.funding.iat[0],
                      D.net.iat[0], 1e-9)
        Tm = rr["trades"]
        assert Tm.exit_reason.iat[0] == "window_end" and bool(Tm.open_at_end.iat[0])
        assert Tm.exit_time.iat[0] == _U("2025-03-06") and Tm.exit_time_r0.iat[0] == xt
        assert _close(Tm.hold_h.iat[0], (_U("2025-03-06") - t0) / pd.Timedelta("1h"))
        acc = be.assemble({"SYN": {"trades": Tm, "daily_mtm": rr["daily_mtm"]}}, be.ROWS["R0"], "2025-03-03",
                          "2025-03-05", k_slots=1)
        assert _close(acc["equity"].iloc[-1], 1.0 + 3.0 * D.net.iat[0], 1e-9), kind
    say("  G-B account: unwrapped positions passed through (R0 ret and marks), R0 exits after the window marked at "
        "its end (trend exit, minute and hourly stops) ok")


def _same_rows(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Same rows and values (timestamps compared as int64 ns; dtype of empty frames ignored)."""
    if len(a) != len(b) or list(a.columns) != list(b.columns):
        return False
    for c in a.columns:
        x, y = a[c], b[c]
        if x.dtype.kind == "M" or y.dtype.kind == "M":
            if not np.array_equal(_ns(x), _ns(y)):
                return False
        elif not np.array_equal(x.to_numpy(), y.to_numpy()):
            return False
    return True


def _test_lookahead(say, n_cuts=8, seed=11):
    """Look-ahead check on G-A: every price after a cut minute x 1.5 in minutes, hours and daily bars (off the hour,
    inside the run's grids); every fill, deployment, end and 00:00 mark stamped before the cut is unchanged."""
    rng = np.random.default_rng(seed)
    M = _gbm_minutes(130 * 1440, 0.0003, 3, "2025-01-01")
    H = _hours_for(M)
    D = bd.bars_from_hours(H, "1d", "sig")
    r0 = pd.DataFrame({"entry1_time": [_U("2025-04-20 14:00")], "exit_time": [_U("2025-04-23 17:00")]})
    base = grid_ga("SYN", r0, daily_bars=D, minutes=M, hours=H, start="2025-03-15", end="2025-05-10", tick=0.001)
    Fb = base["fills"]
    Db = base["deployments"]
    assert len(Db) >= 3 and len(Fb) >= 100, (len(Db), len(Fb))
    lo, hi = Fb.time.iloc[len(Fb) // 10], Fb.time.iloc[-1]
    n_before = []
    for _ in range(n_cuts):
        while True:
            t = lo + pd.Timedelta(minutes=int(rng.integers(0, int((hi - lo) / pd.Timedelta("1min")))))
            if t.minute != 0:
                break
        M2 = M.copy()
        aft = M2.index >= t
        M2.loc[aft, ["open", "high", "low", "close"]] *= 1.5
        H2 = _hours_for(M2)
        D2 = bd.bars_from_hours(H2, "1d", "sig")
        pert = grid_ga("SYN", r0, daily_bars=D2, minutes=M2, hours=H2, start="2025-03-15", end="2025-05-10",
                       tick=0.001)
        Fp = pert["fills"]
        cols = ["time", "kind", "px", "qty", "dep", "interval"]
        a = Fb[Fb.time < t][cols].reset_index(drop=True)
        b = Fp[Fp.time < t][cols].reset_index(drop=True)
        assert _same_rows(a, b), (t, a.tail(), b.tail())
        n_before.append(len(a))
        dp = pert["deployments"]
        k = ["decided", "start", "lo", "hi", "q", "n_int"]
        assert _same_rows(Db[Db.start < t][k].reset_index(drop=True), dp[dp.start < t][k].reset_index(drop=True))
        e = ["end", "reason", "net"]
        assert _same_rows(Db[Db.end < t][e].reset_index(drop=True), dp[dp.end < t][e].reset_index(drop=True))
        ma, mb = base["daily_by_dep"], pert["daily_by_dep"]
        assert _same_rows(ma[ma.time < t].reset_index(drop=True), mb[mb.time < t].reset_index(drop=True))
    say(f"  look-ahead: {n_cuts} off-hour cut minutes inside {len(Db)} grids ({len(Fb)} fills); fills (median "
        f"{int(np.median(n_before))} before a cut), deployments, ends and 00:00 marks before each cut unchanged")


# ---------------------------------------------------------------- martingale control (engine known answer, G-A)
def _mg_coin(args):
    """One synthetic martingale coin: 1-minute GBM, hours and daily bars from it, R0 from bb_engine on the same
    data, then G-A at zero and base fees. Returns per-deployment nets (zero, base) and audit counts."""
    i, days, warm, sigma_day, seed = args
    n = (warm + days) * 1440
    sig = sigma_day / np.sqrt(1440.0)
    start = pd.Timestamp("2010-01-04", tz="UTC") + pd.Timedelta(days=int(i) * 0)
    M = _gbm_minutes(n, sig, seed + 7919 * i, start)
    H = _hours_for(M)
    D = bd.bars_from_hours(H, "1d", "sig")
    w0 = start + pd.Timedelta(days=warm)
    w1 = start + pd.Timedelta(days=warm + days - 1)
    sym = f"MG{i}"
    r0 = be.simulate_coin(sym, be.ROWS["R0"], start=w0, end=w1.strftime("%Y-%m-%d"), hours=H, minutes=M, mmr=0.005,
                          detail=False)
    out = {"n_r0": len(r0["trades"]), "audit_r0": len(r0["fills_audit"])}
    for fz in ("zero", "base"):
        g = grid_ga(sym, r0["trades"], daily_bars=D, cfg_fees=fz, start=w0, end=w1.strftime("%Y-%m-%d"), minutes=M,
                    hours=H, mmr=0.005, tick=0.001)
        Dg = g["deployments"]
        out[fz] = Dg.net.to_numpy(float)
        out[fz + "_audit"] = len(g["fills_audit"])
        out[fz + "_reasons"] = Dg.reason.value_counts().to_dict()
        out[fz + "_fills"] = int(Dg.n_fills.sum())
    be.clear_cache()
    return out


def _martingale_ga(say, n_coins=240, days=730, warm=100, sigma_day=0.02, seed=20261018, workers=4):
    t0 = time.time()
    jobs = [(i, days, warm, sigma_day, seed) for i in range(n_coins)]
    res = be._pool_map(_mg_coin, jobs, workers=workers)
    z = np.concatenate([r["zero"] for r in res])
    b = np.concatenate([r["base"] for r in res])
    assert len(z) == len(b)
    se_z = z.std(ddof=1) / np.sqrt(len(z))
    se_b = b.std(ddof=1) / np.sqrt(len(b))
    reasons = {}
    for r in res:
        for k, v in r["zero_reasons"].items():
            reasons[k] = reasons.get(k, 0) + v
    audits = sum(r["zero_audit"] + r["base_audit"] + r["audit_r0"] for r in res)
    say(f"  martingale G-A control: {n_coins} coins x {days} d (sigma {sigma_day:.0%}/day), {len(z)} deployments, "
        f"{sum(r['n_r0'] for r in res)} R0 positions, ends {reasons}")
    say(f"    before fees: mean {z.mean():+.6f} sleeve per deployment, SE {se_z:.6f}, t {z.mean() / se_z:+.2f}")
    say(f"    after fees : mean {b.mean():+.6f}, SE {se_b:.6f}, t {b.mean() / se_b:+.2f}; "
        f"mean fee drag {np.mean(z - b):.6f} ({time.time() - t0:.0f} s)")
    assert audits == 0, audits
    assert abs(z.mean()) <= 2 * se_z, ("G-A mean before fees not within 2 SE of zero", z.mean(), se_z)
    assert b.mean() < 0, ("G-A mean after fees not negative", b.mean())
    return {"n": len(z), "mean_zero": z.mean(), "se_zero": se_z, "mean_base": b.mean(), "se_base": se_b}


def _real_timing(say):
    """Mechanics only on real BTC 2024-07..2026-10 minutes: runs, counts, audit and timing. No P&L is printed."""
    t0 = time.time()
    M = bd.minutes("BTC", GRID_START, GRID_END)
    H = bd.coin_hours("BTC", GRID_START, GRID_END)
    t_load = time.time() - t0
    t1 = time.time()
    r0 = be.simulate_coin("BTC", be.ROWS["R0"], start=GRID_START, end=GRID_END)
    t_r0 = time.time() - t1
    out = {}
    for name, fn in (("G-A", lambda f: grid_ga("BTC", r0["trades"], cfg_fees="base", fill=f)),
                     ("G-B", lambda f: grid_gb("BTC", r0, cfg_fees="base", fill=f)),
                     ("G-0", lambda f: grid_g0("BTC", cfg_fees="base", fill=f))):
        for f in ("through", "touch"):
            t2 = time.time()
            g = fn(f)
            dt = time.time() - t2
            assert not g["fills_audit"], g["fills_audit"][:5]
            out[(name, f)] = dt
            say(f"    BTC {name} {f:7s}: {len(g['deployments'])} grids, {g['log']['fills']} grid fills, "
                f"{g['log']['open_through_fills']} open-through, {g['log']['outage_minutes']} outage minutes, "
                f"audit ok, {dt:.2f} s")
    say(f"  real BTC mechanics: {len(M):,} minutes, {len(H):,} hours loaded in {t_load:.1f} s; R0 run {t_r0:.1f} s "
        f"(input only); no P&L printed")
    return out


def selftest(quick: bool = False) -> None:
    t0 = time.time()

    def say(s):
        print(s, flush=True)

    say("bb_grid self-test")
    _test_hand(say)
    _test_liquidation(say)
    _test_funding(say)
    _test_random_vs_slow(say)
    _test_ga(say)
    _test_gb(say)
    _test_g0(say)
    _test_perp_end(say)
    _test_mark_funding(say)
    _test_injection(say)
    _test_ties(say)
    _test_gb_account(say)
    _test_lookahead(say)
    say("  grid path check (1-second driftless path vs the 1-minute engine; |diff| <= 10% of 1-second grid profit):")
    pc = path_check()
    assert pc["passed"], "grid path check failed"
    say("  grid path check passed (stress row reported only)")
    if quick:
        _martingale_ga(say, n_coins=40, days=730)
    else:
        _martingale_ga(say)
    _real_timing(say)
    say(f"bb_grid self-test passed in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest(quick="--quick" in sys.argv)
    else:
        print(__doc__)
