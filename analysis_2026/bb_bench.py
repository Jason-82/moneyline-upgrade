"""
Benchmarks, the user's routes and the cross-checks of the Bollinger-breakout replication
(analysis_2026/BB_REPLICATION_PREREG.md): H2's two benchmarks ("H2 vs benchmarks": (a) the equal-weight spot
buy-and-hold of the coins, each joining when S1 can first trade it, rebalanced daily, spot costs, no funding; (b) the
repo's daily indicator `moneyline_ref`, the pre-October-2026 version, long/flat at M = sleeve on the same perpetuals,
signal at the 00:00 UTC close, fill at the 01:00 UTC open, S1's fees, slippage and funding), "What the user could
run" (the RH, ETF, CB and Stocks routes through gate.evaluate at each route's vehicle with gate.placebo()'s expected
false-pass counts and the full-mechanics after-tax CAGR beside them), "Headline replication"'s TV cross-check (S1 on
the close-only data/tv_full exports next to the exported indicator state) and the Controls' "Indicator cross-check"
(the moneyline_ref benchmark against HANDOFF 5.14's BTC 1x multiple). Contract: the scratchpad's
bb_engine_spec.md, "bb_bench.py". Data: analysis_2026/bb_data.py; trades: bb_engine.py and bb_stocks.py.

    python3 -m analysis_2026.bb_bench selftest                 # synthetic known answers, a mechanics-only routes and
                                                               # TV run on the real data (counts only), and the
                                                               # indicator cross-check (a benchmark); --synthetic-only
    python3 -m analysis_2026.bb_bench crosscheck               # the indicator cross-check only (a benchmark)
    python3 -m analysis_2026.bb_bench routes --out DIR [--placebo 100] [--jobs 4]   # writes CSVs, prints counts only
                                                               # [--spot-route-start 2017-08-17]: RH/ETF from spot's
                                                               # first day (choice 4; needs the orchestrator's ruling)
    python3 -m analysis_2026.bb_bench tv --out DIR             # TV cross-check CSVs, prints counts only

Public API
  bh_crypto(syms, start, end, idle_tbill=False, cost_side=None, hours=None, weights="sleeve") -> DataFrame
      daily (UTC day d = bar d, 00:00 -> 00:00) ret, tbill, excess, n_held, equity; attrs["join"] = join days
  join_day(sym, start=START, hours=None) -> Timestamp | None     the UTC day S1 can first trade the coin
  spot_hours(hours) -> DataFrame              the spot vehicle's frame: traded columns = the signal series (choice 13)
  ml_coin(sym, start, end, fees="base", vehicle="perp", hours=None) -> dict    one coin of the indicator benchmark
      (trades, daily_mtm, expo, green, log; bb_engine.simulate_coin's per-M layout, so bb_engine.assemble takes it)
  moneyline_perp(syms, start, end, k_slots=None, idle_tbill=False, rule11=True, fees="base", vehicle="perp",
                 hours=None) -> dict   bb_engine.assemble's account (equity, ret, excess, tbill, trades, ...) + coins
  indicator_crosscheck(say=print) -> dict    the Controls' "Indicator cross-check" (benchmark only)
  gate_row(close, green, vehicle, placebo_n=100, seed=0) -> dict    gate.evaluate + gate.placebo
  spy_hurdle(idx) -> (cagr_tax, max_dd)      gate.spy_hurdle on the extended S&P 500 series (choice 10)
  in_position_crypto(res, index) -> Series   long while any tranche is open at each daily close (gate input)
  after_tax(equity, realized, open_gain=0.0, income=None) -> dict   gate.ST_RATE conventions on a full-mechanics book
  bh_after_tax(mult) -> float                 buy-and-hold multiple taxed once at gate.LT_RATE
  etf_book(results, start, end, cost=0.0002, k_slots=None, ...) -> dict   the ETF route's book (costs.etf_want timing)
  routes(which=("RH", "ETF", "CB", "Stocks"), start=START, end=END, placebo_n=100, spot_route_start=None, ...) -> dict
      gate (one row per route x row x asset), summary (per route x row x group), accounts, audit, log
  tv_load(sym), s1_close_only(close, atr, sym), indicator_close_only(close, green, sym),
  tv_crosscheck(syms=TV_SYMS, data=None) -> dict    S1 on the close-only exports beside the exported indicator state

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. bh_crypto prices are the coin's SIGNAL series (Binance spot where spot trades, else the perpetual: R0 Signal row),
   daily closes at 00:00 UTC. "Joining when S1 can first trade it": the UTC day of the first live (trades > 0),
   tradable hour at or after the window start whose latest completed daily bar, known at least 1 h before it (S1's
   01:00 fill), is at least the 60th completed bar of its segment (R0's warm-up). The coin earns from the close
   before that day (S1's 01:00 fill approximated by the 00:00 close). Weights (weights="sleeve", primary): each of
   the K coins has a 1/K sleeve, cash until the coin joins (Windows, "Window edges": "A coin's sleeve is cash until
   its first tradable bar plus the warm-up"; "the equal-weight buy-and-hold of BTC/ETH/SOL" is 1/3 each, the same
   K-slot layout as the S1 account it is paired with), each joined coin rebalanced daily to 1/K of equity; the
   cash sleeves earn 0, or the T-bill with idle_tbill. weights="joined" (the build's first reading, kept as a
   sensitivity: equal weights among the coins that have joined, as HS2's "ETFs listed at the time") is there for the
   runner to report beside it. [Reading changed after the bench review; needs the orchestrator's confirmation.] Daily
   rebalancing
   costs nothing; the spot cost (0.10% + slippage 0.02% BTC/ETH, 0.07% others; or a route's cost) is paid once, on
   the joining coin's share; no exit cost. Once joined a coin is held to the window end: a day without a live bar
   returns 0, returns are not chained across a series break (`seg`), and a series that ends stays at its last close
   (the ma_bounce convention for delisted names). Before any coin joins the account is cash.
2. moneyline_perp: moneyline_ref.moneyline (reset variant, ATR10, factor 2, hl2) on the signal series' daily bars,
   restarted at every `seg` change, with S1's warm-up (no long state before the 60th completed bar of the segment).
   The target at hour h is the state of the latest completed daily bar whose known_at is at least 1 h before h (same
   segment); the position changes at the open of the first live, tradable hour where it differs from the target
   (the 01:00 UTC open, or the next live hour after an outage: bb_engine's S1 timing, choice 3). Full size M =
   sleeve (L = 1), no adds, stop or TP. Costs: S1's taker 0.05% + slippage per side (spot stand-in hours 0.10% +
   slippage; fees="vip"/"zero" as bb_engine); funding = rate x quantity x mark open (open where the mark is missing)
   at every print of a position open before it and still open at it (synthetic stand-in funding included);
   liquidation by R0's formula on the mark low (never binds at L = 1); a position open at a perp_end bar is closed
   at its close. A window starts flat; if the state is long at its start, the benchmark buys at the first live hour
   whose target comes from the latest daily bar completed at the window start (a 00:00 UTC start: that bar's state
   at the 01:00 open, as "signal at the 00:00 UTC close, fill at the 01:00 UTC open"; an older bar's state never
   opens a position). A position open at the window's end is marked at the last close without exit cost. The
   account is bb_engine.assemble with S1_L1's sizing (rule 11 on: S1 is R0 minus rules 6 and 12-15), K = number of
   coins. vehicle="spot": the same on spot_hours() (choice 13: fills on the signal series' spot prices, no
   perp_end close), spot costs on every fill, no funding, no liquidation.
3. Indicator cross-check: HANDOFF 5.14's "BTC: 12.4x at 1x spot" comes from leverage_breakout.run (BTC daily bars
   from Binance spot 4h klines, 2018-01-01 .. 2026-09-30, signal at the close, fill at the next daily open, 0.12% per
   side, full compounding, idle cash at T-bills). The benchmark is run on BTC alone (K = 1) over that window with
   rule 11 off (notional = equity at entry, as 5.14) and idle T-bills, as the H2 benchmark (perpetual from 2020,
   spot stand-in with synthetic funding before) and as the spot vehicle (spot prices and costs, no funding: choice
   13); "to order of magnitude" = within a factor
   10 of 12.4x. 5.14's 1x perpetual value (results_leverage/equity_stats.csv) is shown beside it when on disk.
4. Gate input ("long while any tranche is open", "on closes"): True at daily close d iff the engine's 00:00 UTC mark
   after bar d holds a tranche (the mark is taken before that hour's fills), plus positions open at the window end
   on its last bar; bb_stocks.in_position's convention for stocks. The gate then applies its vehicle's own timing
   to that series (crypto_direct "same" -> long from the first close at which the position is open, up to one bar
   after the real fill; stock_daily "next" one session later). Each asset's gate series starts at the close before
   the first day the strategy could trade it (choice 1's join day; stocks: the 60th session's close), so the
   gate's buy-and-hold starts there. T1 needs 7 years ("underlying's own history", gate.py): on the Full crypto
   window (2020-01-01 .. 2026-10-16, the default) a crypto gate series spans at most 6.8 years, so every RH, ETF and
   CB row is at best PROBATION and "You can trade it" (TRADE only) cannot be reached for crypto. Each gate row
   carries T1_years_ok (years >= 7) and the routes log lists the route rows where T1 cannot pass.
   routes(spot_route_start=SPOT_FROM) runs the two spot routes (RH, ETF; L = 1, spot prices, no funding) from
   Binance spot's first day, 2017-08-17 (the pre-perpetual block's start; 9.0 years for BTC and ETH), so that T1
   can be evaluated; CB stays on the Full window (it is "as R0", and Binance perpetuals start in 2019-09).
   [Which window decides the crypto routes needs the orchestrator's ruling before results: escalated.]
5. Gate price series: RH and ETF the Binance spot daily close (signal series: the ETF fill proxy of costs.etf_want
   is the crypto close); CB the traded (perpetual) daily close; Stocks the total-return close (bb_stocks 'tr').
   Engine prices: RH and ETF run bb_engine on spot_hours() (choice 13), CB on bb_data.coin_hours (the perpetual,
   with 1-minute stop resolution from 2024-07: "Binance prices and funding as proxies").
6. Vehicles gate.py lacks: "cb_perp" (crypto_direct's timing, 0.10% per side) and "stock_daily_10bp" (stock_daily's
   timing, 0.10%: COIN, HOOD, CRCL per the Stocks section) are registered in gate.VEHICLES only for the duration of
   each gate call (gate.py is unchanged). The gate has no funding, so CB's gate result omits it; the full-mechanics
   columns include it. At L = 3 the in-position series is the same long/flat series (leverage enters only the
   full-mechanics columns).
7. ETF full mechanics: the target is the engine's position quantity at each Binance daily close (from the 00:00
   marks), executed by costs.etf_want's rule (the first NYSE session strictly after the bar's date; a later bar's
   target overwrites an earlier one mapping to the same session; fill at the crypto close of the execution day's
   bar) at 0.02% per side on every quantity traded; a position that opens and closes between two closes is never
   traded. Position size M = sizing equity / K (rule 11 as bb_engine.assemble), set at its first execution.
8. Accounts beside the gate: per asset one slot (K = 1); per group one slot per asset (K = n); RH and CB through
   bb_engine.assemble, ETF through etf_book, Stocks through bb_stocks.portfolio(n_slots = n). Idle cash earns
   nothing by default (gate.simulate's convention); idle_tbill=True credits the T-bill and taxes it as income.
9. After-tax (gate.py's conventions): realized gains are taxed each calendar year at ST_RATE (35%) with losses
   carried forward; positions open at the end are taxed at ST_RATE on their marked gain with the remaining carry;
   no final liquidation cost (the window-edge rule marks without exit cost). The after-tax book is the pre-tax
   account scaled by the after-tax / pre-tax wealth ratio, which changes only at the year-end payments: exact when
   the book is flat at every year end (checked against gate.simulate). With a position open at a year end the
   scaling is exact for the convention "the tax is paid by selling a pro-rata slice of every holding (cash and
   positions), each holding's cost basis reduced pro rata, the slice's own gain untaxed" (checked against a
   share-and-basis book in the selftest). gate.simulate instead pays from cash and then sells shares without
   reducing their basis, so it under-taxes the later gain: on 40 synthetic single-asset books with positions
   straddling year ends (3% daily vol, 0.95% per side) after_tax's CAGR was on average 0.18 points and at most 1.6
   points below gate.simulate's (bench review, r3_after_tax.py). A multi-asset book that holds cash and positions
   at a year end pays pro rata here rather than from cash first. A trade's P&L is realized at its final exit (a TP
   half closed in an earlier year is taxed in the exit year). Buy-and-hold: taxed once at LT_RATE (20%) on the
   final gain.
10. Route buy-and-hold comparators: bh_crypto at the route's own cost per side (paid once), on the route's own
   frames (spot_hours for RH and ETF); Stocks: bb_stocks.benchmark_ew_etfs(data = the group's names, min_history =
   60), no costs (bb_stocks choice 11). SPY over the same dates (T2b and each summary's spy_cagr_tax): gate.py's SPX
   series (TradingView, 2010-07-13 .. 2026-08-24) is extended for every gate call made here, on both sides, with
   regime_switch.load_spx_long()'s index close (^GSPC to 2018, then SPY x k; to 2026-10-12), each side scaled to
   meet gate's series at its splice day and stamped at gate's 13:30; inside 2010-07-13 .. 2026-08-24 the values are
   gate's own, and gate.spy_hurdle's 2%/yr dividend proxy and tax are unchanged. gate._SPX is restored after each
   call (gate.py is unchanged). Without it the Stocks route's 2001-2026 hurdle silently covered 2010-2026 only.
11. gate.placebo with n = placebo_n (100), min_shift 252, seed 0; undefined (NaN) for a series of 505 bars or fewer
   (CRCL). A group's expected false-pass count is the sum of its assets' placebo pass rates.
12. TV cross-check: the exports carry close, the indicator lines and ATR(14) only, so S1 runs on closes: BB(20, 2)
   with population sigma, the 60-bar near-high on closes (C >= 0.95 x the max close of the 60 bars to t), ATH = the
   max close of the export (365-bar warm-up), no signal before 60 bars; every fill at the deciding close (S1's
   01:00 fill is one hour after it); S = SMA20 - the exported ATR(14) of the signal bar; the stop and the midline
   exit fill at the close that breaches them; the TP half fills at TP (a resting limit) on a close at or above it;
   adds at the close >= 1.02 / 1.05 x entry1; L = 1, spot costs (0.10% + slippage; TP 0.10%), no funding, one slot
   at full compounding. The indicator beside it: long while the exported Up Trend line prints, fills at the close
   at the same costs (HANDOFF 5.1's same-bar convention; flat before the line first prints); S1, the indicator and
   buy-and-hold all run from the export's first bar. The exports' last row (2026-08-24) is a still-forming bar (its
   close differs from Binance's completed close by 1.1-2.1% on the five coins, against medians of 0-0.07% on the
   other days and 0-0.1% on the row before it; checked 2026-10-19) and is dropped.
13. Spot vehicle (spot_hours: the RH and ETF routes' engine runs, ml_coin(vehicle="spot"), and their bh_crypto
   joins): the route table's "Robinhood spot crypto" and "spot BTC and ETH ETFs" are priced on Binance spot, the
   signal series (spot where spot trades, else the perpetual: the R0 Signal row), so the frame's traded columns
   open/high/low/close are sig_open .. sig_close and every fill, stop, TP, add trigger and the fill audit read spot
   bars. trades = 1 on a live signal hour with quote volume > 0, else 0 (bb_data keeps no spot trade count; on the
   traded series this proxy equals trades > 0 on every hour of the 24 RH coins, checked 2026-10-19; an injected
   frame without volumes uses sig_live); tradable from the signal series' first to its last live hour; perp_end
   only at that last live hour when the signal series ends before the frame does (a position is closed at the last
   close, as the Stocks section's dead names; a perpetual's delisting does not close a spot position); no mark, no
   funding. No spot 1-minute bars exist, so stops use the hourly rule (0.99 x S when the hour's low is more than 5%
   below S). Without this the routes filled, stopped and took profit on perpetual prices: the perpetual's hourly
   low was up to 6-26% below spot's on BTC/ETH/SOL crash hours (bench review).
"""
from __future__ import annotations

import argparse
import sys
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analysis_2026.bb_data as bd          # noqa: E402
import analysis_2026.bb_engine as be        # noqa: E402
import analysis_2026.gate as gate           # noqa: E402
from analysis_2026.costs import nyse_trading_days, etf_want   # noqa: E402
from analysis_2026.moneyline_ref import moneyline             # noqa: E402

START, END = "2020-01-01", "2026-10-16"       # "Full" crypto window
SPOT_FROM = "2017-08-17"                       # Binance spot's first day (pre-perpetual block): routes(spot_route_start=)
WARMUP = 60                                    # R0: no signal before 60 completed daily bars
H_NS = 3_600_000_000_000
DAY = pd.Timedelta("1D")
HOUR = pd.Timedelta("1h")
RH_COST, ETF_COST, CB_COST = 0.0095, 0.0002, 0.0010
# HANDOFF 5.14 ("BTC: 12.4x at 1x spot"), leverage_breakout.main(): start, end = "2018-01-01", "2026-09-30"
HANDOFF_514 = {"sym": "BTC", "start": "2018-01-01", "end": "2026-09-30", "multiple_1x_spot": 12.4}
EXTRA_VEHICLES = {"cb_perp": dict(cost=CB_COST, primary="same", alternate="next"),
                  "stock_daily_10bp": dict(cost=0.0010, primary="next", alternate="same")}
TV_SYMS = ["BTC", "ETH", "BNB", "ZEC", "SOL"]
TV_DIR = ROOT / "data" / "tv_full"
_ETF_ROWS = {k: replace(be.ROWS[v], cost_side=ETF_COST)
             for k, v in (("S1", "RH_S1"), ("S1_S4", "RH_S1_S4"), ("R0_L1", "RH_R0win"), ("R0_L1_S4", "RH_R0win_S4"))}
# prices: "spot" = bb_engine runs on spot_hours() (choice 13); "traded" = on bb_data.coin_hours (the perpetual)
ROUTES = {
    "RH": dict(vehicle="crypto_direct", series="sig", prices="spot", cost=RH_COST, book="engine",
               coins=list(bd.RH_TRADABLE), groups={"BTC/ETH/SOL": list(bd.PRIMARY), "RH24": list(bd.RH_TRADABLE),
                       "RH24 exZEC": [c for c in bd.RH_TRADABLE if c != "ZEC"]},
               rows={"S1": be.ROWS["RH_S1"], "S1_S4": be.ROWS["RH_S1_S4"], "R0_L1": be.ROWS["RH_R0win"],
                     "R0_L1_S4": be.ROWS["RH_R0win_S4"]}),
    "ETF": dict(vehicle="spot_etf", series="sig", prices="spot", cost=ETF_COST, book="etf", coins=["BTC", "ETH"],
                groups={"BTC/ETH": ["BTC", "ETH"]}, rows=_ETF_ROWS),
    "CB": dict(vehicle="cb_perp", series="traded", prices="traded", cost=CB_COST, book="engine",
               coins=["BTC", "ETH"], groups={"BTC/ETH": ["BTC", "ETH"]},
               rows={"S1_L1": be.ROWS["CB_S1_L1"], "R0_L1": be.ROWS["CB_R0_L1"], "R0_L3": be.ROWS["CB_R0_L3"]}),
}
STOCK_GROUPS = ("user", "etfs")


# ============================================================================ small helpers
def _utc_day(t) -> pd.Timestamp:
    return bd._utc(t).floor("D")


def _end_day(t) -> pd.Timestamp:
    return bd._utc_end(t).floor("D")


def _naive(idx) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    return idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx


def _spot_cost(sym: str) -> float:
    return be.SPOT_FEE + be._slip(sym)


def _norm_hours(h: pd.DataFrame) -> pd.DataFrame:
    """An injected coin_hours-shaped frame with every column this module reads (defaults as bb_engine)."""
    h = h.copy()
    ix = pd.DatetimeIndex(h.index)
    h.index = (ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")).as_unit("ns")
    h.index.name = "open_time"
    for a in bd.PX:
        if "sig_" + a not in h.columns:
            h["sig_" + a] = h[a]
    defaults = {"trades": 1, "live": True, "seg": 0, "tradable": True, "spot_only": False, "perp_end": False,
                "funding": 0.0, "mark_open": np.nan, "mark_low": np.nan, "mark_high": np.nan, "mark_close": np.nan,
                "quote_volume": 0.0}
    for k, v in defaults.items():
        if k not in h.columns:
            h[k] = v
    if "sig_live" not in h.columns:
        h["sig_live"] = h["live"]
    if "sig_quote_volume" not in h.columns:
        h["sig_quote_volume"] = h["quote_volume"]
    return h


def _hours(sym: str, hours=None) -> pd.DataFrame:
    if hours is None:
        return bd.coin_hours(sym)
    h = hours[sym] if isinstance(hours, dict) else hours
    return _norm_hours(h)


def spot_hours(hours: pd.DataFrame) -> pd.DataFrame:
    """The spot vehicle's frame (choice 13): a coin_hours-shaped frame whose traded columns are the signal series
    (Binance spot where spot trades, else the perpetual), so that bb_engine / ml_coin fill, stop, take profit and
    audit on spot prices. trades = live signal hour with quote volume > 0 (sig_live alone when the frame carries no
    volumes); tradable from the signal series' first to its last live hour; perp_end only at that last live hour if
    the series ends early; no mark, no funding; spot costs (spot_only)."""
    out = _norm_hours(hours)                                      # a copy: the caller's frame is not changed
    for a in bd.PX:
        out[a] = out["sig_" + a].to_numpy(float)
    sl = out["sig_live"].to_numpy(bool)
    sq = np.nan_to_num(out["sig_quote_volume"].to_numpy(float))
    out["trades"] = ((sl & (sq > 0)) if (sq > 0).any() else sl).astype(np.int64)
    out["quote_volume"] = sq
    out["live"] = sl
    out["is_perp"] = False
    out["spot_only"] = True
    n = len(out)
    trad, pend = np.zeros(n, bool), np.zeros(n, bool)
    lv = np.flatnonzero(sl)
    if len(lv):
        trad[lv[0]:lv[-1] + 1] = True
        if lv[-1] < n - 1:
            pend[lv[-1]] = True
    out["tradable"] = trad
    out["perp_end"] = pend
    for a in ("mark_open", "mark_high", "mark_low", "mark_close"):
        out[a] = np.nan
    out["funding"] = 0.0
    if "fund_synthetic" in out.columns:
        out["fund_synthetic"] = False
    return out


def _seg_count(D: pd.DataFrame) -> np.ndarray:
    """1-based position of each bar inside its segment."""
    seg = D["seg"].to_numpy(np.int64) if "seg" in D else np.zeros(len(D), np.int64)
    out = np.ones(len(D), np.int64)
    for i in range(1, len(D)):
        out[i] = out[i - 1] + 1 if seg[i] == seg[i - 1] else 1
    return out


def _cagr(mult: float, first, last) -> float:
    yrs = (pd.Timestamp(last) - pd.Timestamp(first)).days / 365.25
    if yrs <= 0 or not np.isfinite(mult):
        return np.nan
    return (mult ** (1 / yrs) - 1) * 100 if mult > 0 else -100.0


def _maxdd(eq: pd.Series) -> float:
    e = pd.Series(np.asarray(eq, float))
    if not len(e) or not (e > 0).any():
        return np.nan
    return float(((e / e.cummax()) - 1).min() * 100)


# ============================================================================ join day and buy-and-hold
def _first_trade_hour(H: pd.DataFrame, start=None, warmup: int = WARMUP):
    """First live, tradable hour >= start at which S1 could fill an entry (choice 1), or None."""
    D = bd.bars_from_hours(H, "1d", "sig")
    if D.empty:
        return None
    cnt = _seg_count(D)
    t = H.index.asi8
    kn = pd.DatetimeIndex(D["known_at"]).as_unit("ns").asi8
    p = np.searchsorted(kn, t - H_NS, side="right") - 1
    ok = p >= 0
    pc = np.clip(p, 0, len(D) - 1)
    hseg = H["seg"].to_numpy(np.int64)
    dseg = D["seg"].to_numpy(np.int64)
    elig = ok & (cnt[pc] >= warmup) & (dseg[pc] == hseg) & (H["trades"].to_numpy() > 0) & \
        H["tradable"].to_numpy(bool)
    if start is not None:
        elig &= t >= bd._utc(start).value
    i = np.flatnonzero(elig)
    return None if not len(i) else H.index[i[0]]


def join_day(sym: str, start=START, hours=None) -> pd.Timestamp | None:
    """The UTC day (00:00, tz-aware) on which S1 can first trade the coin at or after `start` (choice 1)."""
    h = _first_trade_hour(_hours(sym, hours), start)
    return None if h is None else h.floor("D")


def bh_crypto(syms, start=START, end=END, idle_tbill: bool = False, cost_side: float | None = None,
              hours=None, weights: str = "sleeve") -> pd.DataFrame:
    """Equal-weight spot buy-and-hold (H2 (a)): each coin joins on join_day(), rebalanced daily, its spot cost paid
    once on joining, no funding. weights="sleeve" (primary): K = len(syms) sleeves of 1/K, a coin's sleeve cash until
    it joins; "joined": equal weights among the joined coins (choice 1). Index = UTC day d (tz-aware 00:00): the
    return from close d-1 to close d, the same index as bb_engine.assemble's daily returns. Columns ret, tbill,
    excess, n_held, equity (after day d)."""
    if weights not in ("sleeve", "joined"):
        raise ValueError("weights must be 'sleeve' or 'joined'")
    a, b = _utc_day(start), _end_day(end)
    days = pd.date_range(a, b, freq="D").as_unit("ns")
    n = len(days)
    syms = list(syms)
    R = np.zeros((n, len(syms)))
    held = np.zeros((n, len(syms)), bool)
    CJ = np.zeros((n, len(syms)))
    joins = {}
    for j, s in enumerate(syms):
        H = _hours(s, hours)
        J = join_day(s, start, H)
        joins[s] = J
        if J is None or J > b:
            continue
        D = bd.bars_from_hours(H, "1d", "sig")
        full = pd.date_range(D.index[0], b, freq="D").as_unit("ns")
        c = D["close"].reindex(full).ffill()
        seg = D["seg"].reindex(full).ffill()
        r = (c / c.shift(1) - 1.0).where(seg == seg.shift(1), 0.0).fillna(0.0)
        r = r.reindex(days).fillna(0.0).to_numpy()
        hj = days >= J
        held[:, j] = hj
        R[:, j] = np.where(hj, r, 0.0)
        CJ[days.get_loc(J), j] = _spot_cost(s) if cost_side is None else float(cost_side)
    nh = held.sum(1)
    K = len(syms)
    tb = bd.tbill_daily(days)
    if weights == "sleeve":                      # 1/K per coin; a not-yet-joined coin's sleeve is cash
        ret = (R.sum(1) - CJ.sum(1)) / max(K, 1)
        if idle_tbill:
            ret = ret + (K - nh) / max(K, 1) * tb
    else:                                        # equal weights among the joined coins
        ret = np.where(nh > 0, (R.sum(1) - CJ.sum(1)) / np.maximum(nh, 1), 0.0)
        if idle_tbill:
            ret = np.where(nh == 0, tb, ret)
    out = pd.DataFrame({"ret": ret, "tbill": tb, "excess": ret - tb, "n_held": nh,
                        "equity": np.cumprod(1.0 + ret)}, index=days)
    out.index.name = "day"
    out.attrs["join"] = joins
    out.attrs["weights"] = weights
    out.attrs["K"] = K
    return out


def bh_after_tax(mult: float, lt: float = gate.LT_RATE) -> float:
    """Buy-and-hold multiple after a single long-term tax on the final gain (gate.bh's convention)."""
    return mult - lt * (mult - 1.0) if mult > 1.0 else mult


# ============================================================================ the indicator benchmark (H2 (b))
@njit(cache=True)
def _ml_loop(o, lo, c, trd, tradable, spot, pend, mopen, mlow, fund, target, midnight, h0, h1, cr_perp, cr_spot,
             mmr, L, perp_mode):
    """Long/flat at full size (per M = 1 of notional at the entry price). Returns position ints (entry hour, exit
    hour, exit kind: 0 signal at an open, 1 liquidation, 2 perp_end close, 3 window end), floats (entry px, exit px,
    ret, fees, funding, notional-hours) and the 00:00 marks (pos, hour; mtm, margin, notional)."""
    nmax = h1 - h0 + 2
    PI = np.full((nmax, 3), -1, np.int64)
    PF = np.zeros((nmax, 6))
    dmax = (h1 - h0) // 24 + 3
    DI = np.zeros((dmax, 2), np.int64)
    DF = np.zeros((dmax, 3))
    npos = 0
    nd = 0
    is_open = False
    e = 0.0
    q = 0.0
    fees = 0.0
    fpaid = 0.0
    expo = 0.0
    for h in range(h0, h1 + 1):
        if is_open and perp_mode and fund[h] != 0.0:                     # print at the hour's open (pre-fills)
            fpaid += fund[h] * q * mopen[h]
        if is_open and midnight[h] and h > 0 and nd < dmax:              # 00:00 UTC mark: the previous close
            P = c[h - 1]
            DI[nd, 0] = npos
            DI[nd, 1] = h
            DF[nd, 0] = q * (P - e) - fees - fpaid
            DF[nd, 1] = 1.0 / L
            DF[nd, 2] = q * P
            nd += 1
        live = trd[h] > 0 and tradable[h]
        cr = cr_spot if (spot[h] or not perp_mode) else cr_perp
        if live:
            if is_open and not target[h]:
                x = o[h]
                fees += cr * q * x
                PI[npos, 1] = h
                PI[npos, 2] = 0
                PF[npos, 1] = x
                PF[npos, 2] = q * (x - e) - fees - fpaid
                PF[npos, 3] = fees
                PF[npos, 4] = fpaid
                PF[npos, 5] = expo
                npos += 1
                is_open = False
            elif (not is_open) and target[h]:
                e = o[h]
                q = 1.0 / e
                fees = cr
                fpaid = 0.0
                expo = 0.0
                is_open = True
                PI[npos, 0] = h
                PF[npos, 0] = e
        if is_open:
            expo += q * o[h]
        if is_open and perp_mode and live:                              # liquidation on the mark (else last) low
            liq = e * (1.0 - (1.0 / L - fees - fpaid) + mmr)
            lw = mlow[h] if mlow[h] == mlow[h] else lo[h]
            if lw <= liq:
                PI[npos, 1] = h
                PI[npos, 2] = 1
                PF[npos, 1] = liq
                PF[npos, 2] = -1.0 / L
                PF[npos, 3] = fees
                PF[npos, 4] = fpaid
                PF[npos, 5] = expo
                npos += 1
                is_open = False
        if is_open and pend[h]:                                         # delisted perpetual: forced close
            x = c[h]
            cr2 = cr_spot if (spot[h] or not perp_mode) else cr_perp
            fees += cr2 * q * x
            PI[npos, 1] = h
            PI[npos, 2] = 2
            PF[npos, 1] = x
            PF[npos, 2] = q * (x - e) - fees - fpaid
            PF[npos, 3] = fees
            PF[npos, 4] = fpaid
            PF[npos, 5] = expo
            npos += 1
            is_open = False
    if is_open:                                                         # window end: marked, no exit cost
        x = c[h1]
        PI[npos, 1] = h1
        PI[npos, 2] = 3
        PF[npos, 1] = x
        PF[npos, 2] = q * (x - e) - fees - fpaid
        PF[npos, 3] = fees
        PF[npos, 4] = fpaid
        PF[npos, 5] = expo
        npos += 1
    return PI[:npos], PF[:npos], DI[:nd], DF[:nd]


_ML_REASON = np.array(["signal", "liq", "delist", "window_end"], dtype=object)


def ml_green(H: pd.DataFrame, warmup: int = WARMUP) -> pd.DataFrame:
    """Daily signal-series bars with the indicator state (per segment) and its warm-up mask (choice 2)."""
    D = bd.bars_from_hours(H, "1d", "sig")
    green = np.zeros(len(D), bool)
    cnt = _seg_count(D)
    seg = D["seg"].to_numpy(np.int64)
    for s in np.unique(seg):
        m = seg == s
        if m.sum() == 0:
            continue
        g = moneyline(D.loc[m, ["open", "high", "low", "close"]])["green"].to_numpy(bool)
        green[m] = g
    D = D.copy()
    D["green_raw"] = green
    D["green"] = green & (cnt >= warmup)
    D["n_in_seg"] = cnt
    return D


def ml_coin(sym: str, start=START, end=END, fees: str = "base", vehicle: str = "perp", hours=None,
            warmup: int = WARMUP) -> dict:
    """One coin of the indicator benchmark in bb_engine.simulate_coin's per-M layout (choice 2)."""
    if vehicle not in ("perp", "spot"):
        raise ValueError("vehicle must be 'perp' or 'spot'")
    H = _hours(sym, hours)
    if vehicle == "spot":
        H = spot_hours(H)                      # fills on spot prices; no perp_end close (choice 13)
    D = ml_green(H, warmup)
    t = H.index.asi8
    kn = pd.DatetimeIndex(D["known_at"]).as_unit("ns").asi8
    p = np.searchsorted(kn, t - H_NS, side="right") - 1
    pc = np.clip(p, 0, max(len(D) - 1, 0))
    target = (p >= 0) & (D["green"].to_numpy(bool)[pc] if len(D) else False) & \
        ((D["seg"].to_numpy(np.int64)[pc] if len(D) else 0) == H["seg"].to_numpy(np.int64))
    h0 = int(np.searchsorted(t, bd._utc(start).value, "left")) if start is not None else 0
    h1 = int(np.searchsorted(t, bd._utc_end(end).value, "right")) - 1 if end is not None else len(t) - 1
    if h1 < h0:
        raise ValueError(f"{sym}: empty window {start} .. {end}")
    # window start (choice 2): the run starts flat and opens only on the state of the latest daily bar completed at
    # the start or a later one (a 00:00 start: bar start-1's state at the 01:00 open, never bar start-2's at 00:00)
    p0 = int(np.searchsorted(kn, t[h0], side="right")) - 1
    target = target & (p >= p0)
    slip = 0.0 if fees == "zero" else be._slip(sym)
    cr_perp = be.TAKER[fees] + slip
    cr_spot = (0.0 if fees == "zero" else be.SPOT_FEE) + slip
    mo = H["mark_open"].to_numpy(float)
    o = H["open"].to_numpy(float)
    PI, PF, DI, DF = _ml_loop(o, H["low"].to_numpy(float), H["close"].to_numpy(float),
                              H["trades"].to_numpy(np.int64), H["tradable"].to_numpy(bool),
                              H["spot_only"].to_numpy(bool), H["perp_end"].to_numpy(bool),
                              np.where(np.isfinite(mo), mo, o), H["mark_low"].to_numpy(float),
                              np.nan_to_num(H["funding"].to_numpy(float)), np.asarray(target, bool),
                              np.asarray(H.index.hour == 0), h0, h1, cr_perp, cr_spot,
                              float(bd.MMR.get(sym, 0.005)), 1.0, vehicle == "perp")
    n = len(PI)
    eh, xh, kind = PI[:, 0], PI[:, 1], PI[:, 2]
    e_t = t[eh] if n else np.zeros(0, np.int64)
    x_t = (t[xh] + np.where(kind == 0, 0, H_NS)) if n else np.zeros(0, np.int64)   # open fill vs bar-close stamp
    trades = pd.DataFrame({
        "pos": np.arange(n), "sym": sym, "side": 1, "entry1_time": pd.DatetimeIndex(e_t, tz="UTC"),
        "entry1_px": PF[:, 0], "exit_time": pd.DatetimeIndex(x_t, tz="UTC"), "exit_px": PF[:, 1],
        "exit_reason": _ML_REASON[kind] if n else np.zeros(0, object), "ret": PF[:, 2],
        "fees": PF[:, 3], "funding": PF[:, 4], "ret_gross": PF[:, 2] + PF[:, 3] + PF[:, 4],
        "L_used": 1.0, "liquidated": kind == 1, "open_at_end": kind == 3, "n_tranches": 1, "max_frac": 1.0,
        "hold_h": (x_t - e_t) / H_NS, "expo_sum": PF[:, 5]})
    daily = pd.DataFrame({"pos": DI[:, 0], "time": pd.DatetimeIndex(t[DI[:, 1]], tz="UTC"), "mtm": DF[:, 0],
                          "margin": DF[:, 1], "notional": DF[:, 2], "sym": sym})
    expo = pd.DataFrame({"pos": trades["pos"].to_numpy(), "time": trades["entry1_time"],
                         "notional": trades["expo_sum"].to_numpy(float), "sym": sym})
    log = {"positions": int(n), "liquidations": int((kind == 1).sum()), "delist_closes": int((kind == 2).sum()),
           "open_at_end": int((kind == 3).sum()), "green_days": int(D["green"].sum()),
           "window": (str(H.index[h0]), str(H.index[h1])), "vehicle": vehicle, "fees": fees}
    res = {"sym": sym, "trades": trades, "daily_mtm": daily, "expo": expo, "green": D, "fills_audit": [],
           "log": log}
    from analysis_2026.bb_controls import bench_fill_audit   # lazy: bb_controls imports this module
    res["fills_audit"] = bench_fill_audit(res, H)
    return res


def moneyline_perp(syms=tuple(bd.PRIMARY), start=START, end=END, k_slots: int | None = None,
                   idle_tbill: bool = False, rule11: bool = True, fees: str = "base", vehicle: str = "perp",
                   hours=None) -> dict:
    """H2 (b): the indicator long/flat at M = sleeve (L = 1) on the perpetuals, as an account of K slots
    (bb_engine.assemble with S1_L1's sizing; rule11=False sizes from current equity). Returns assemble's dict
    (equity, ret, excess, tbill, trades, exposure, ...) plus coins = {sym: ml_coin result}."""
    syms = list(syms)
    res = {s: ml_coin(s, start, end, fees, vehicle, hours) for s in syms}
    cfg = replace(be.ROWS["S1_L1"], rule11=bool(rule11))
    acct = be.assemble(res, cfg, start, end, idle_tbill=idle_tbill, k_slots=k_slots or len(syms))
    acct["coins"] = res
    return acct


def _leverage_ref():
    """5.14's BTC ML 1x values from results_leverage/equity_stats.csv, if on disk."""
    p = ROOT / "analysis_2026" / "results_leverage" / "equity_stats.csv"
    out = {"handoff_text_1x_spot": HANDOFF_514["multiple_1x_spot"]}
    if p.exists():
        e = pd.read_csv(p)
        m = (e.tf == "1d") & (e.asset == "BTC") & (e.system == "ML") & (e.lev == 1.0)
        for v in ("spot", "perp"):
            r = e[m & (e.venue == v)]
            if len(r):
                out[f"csv_1x_{v}"] = float(r.final_x.iloc[0])
    return out


def indicator_crosscheck(say=print) -> dict:
    """Controls, "Indicator cross-check": the moneyline_ref benchmark reproduces HANDOFF 5.14's BTC 1x multiple to
    order of magnitude on the same window (choice 3). A benchmark, not a strategy result."""
    w = HANDOFF_514
    ref = _leverage_ref()
    runs = {"bench_perp_5.14cfg": dict(vehicle="perp", rule11=False, idle_tbill=True),
            "bench_spot_5.14cfg": dict(vehicle="spot", rule11=False, idle_tbill=True),
            "bench_perp_H2cfg": dict(vehicle="perp", rule11=True, idle_tbill=False)}
    out = {"window": (w["start"], w["end"]), "ref": ref}
    for k, kw in runs.items():
        a = moneyline_perp([w["sym"]], w["start"], w["end"], k_slots=1, **kw)
        m = float(a["equity"].iloc[-1])
        out[k] = {"multiple": m, "positions": int(len(a["trades"])),
                  "log10_ratio_vs_12.4": float(np.log10(m / w["multiple_1x_spot"])) if m > 0 else -np.inf,
                  "cagr": _cagr(m, a["equity"].index[0], a["equity"].index[-1]), "max_dd": _maxdd(a["equity"])}
    out["pass"] = bool(abs(out["bench_perp_5.14cfg"]["log10_ratio_vs_12.4"]) < 1.0)
    say(f"Indicator cross-check (benchmark only): BTC moneyline_ref 1x, {w['start']} .. {w['end']}")
    say(f"  HANDOFF 5.14 text: {ref['handoff_text_1x_spot']:.1f}x at 1x spot"
        + (f"; results_leverage csv: 1x spot {ref.get('csv_1x_spot', np.nan):.2f}x, 1x perp "
           f"{ref.get('csv_1x_perp', np.nan):.2f}x" if "csv_1x_spot" in ref else ""))
    for k in runs:
        r = out[k]
        say(f"  {k:20s}: {r['multiple']:7.2f}x  (CAGR {r['cagr']:5.1f}%, max DD {r['max_dd']:6.1f}%, "
            f"{r['positions']} positions; log10 ratio to 12.4x {r['log10_ratio_vs_12.4']:+.2f})")
    say(f"  same order of magnitude as 12.4x (|log10 ratio| < 1, perp benchmark, 5.14's sizing): "
        f"{'PASS' if out['pass'] else 'FAIL'}")
    return out


# ============================================================================ gate wiring
@contextmanager
def _extra_vehicles():
    """Register the vehicles gate.py lacks (choice 6) for the duration of a call; gate.VEHICLES is restored."""
    added = [k for k in EXTRA_VEHICLES if k not in gate.VEHICLES]
    for k in added:
        gate.VEHICLES[k] = dict(EXTRA_VEHICLES[k])
    try:
        yield
    finally:
        for k in added:
            gate.VEHICLES.pop(k, None)


_SPX_EXT = None


def _spx_extended() -> pd.Series:
    """gate.py's SPX close (2010-07-13 .. 2026-08-24, 13:30 stamps) extended on both sides with
    regime_switch.load_spx_long()'s index close, each side scaled to meet gate's series at the splice day (choice
    10). Inside gate's range the values are gate's own. Cached."""
    global _SPX_EXT
    if _SPX_EXT is None:
        if gate._SPX is None:
            gate.spy_hurdle(pd.DatetimeIndex([pd.Timestamp("2015-01-01"), pd.Timestamp("2016-01-01")]))
        base = gate._SPX.copy()
        from analysis_2026.regime_switch import load_spx_long
        lg = load_spx_long()["close"].astype(float)
        lg.index = pd.DatetimeIndex(lg.index).normalize()
        lg = lg[~lg.index.duplicated(keep="last")].sort_index()
        bday = pd.DatetimeIndex(base.index).normalize()
        stamp = base.index[0] - bday[0]                                   # gate's time-of-day stamp (13:30)
        first, last = bday[0], bday[-1]
        pre = lg[lg.index < first] * (float(base.iloc[0]) / float(lg.loc[first]))
        post = lg[lg.index > last] * (float(base.iloc[-1]) / float(lg.loc[last]))
        pre.index, post.index = pre.index + stamp, post.index + stamp
        ext = pd.concat([pre, base, post])
        ext.index = pd.DatetimeIndex(ext.index).as_unit(base.index.unit)
        ext.name = base.name
        _SPX_EXT = ext
    return _SPX_EXT


@contextmanager
def _spx_ext():
    """Install the extended S&P 500 series as gate._SPX for the duration of a call (choice 10); restored after."""
    ext = _spx_extended()
    prev = gate._SPX
    gate._SPX = ext
    try:
        yield
    finally:
        gate._SPX = prev


def spy_hurdle(idx) -> tuple:
    """gate.spy_hurdle (after-tax CAGR and max DD of holding the S&P 500 over idx[0] .. idx[-1]) on the extended
    series (choice 10)."""
    with _spx_ext():
        return gate.spy_hurdle(idx)


def gate_row(close: pd.Series, green, vehicle: str, placebo_n: int = 100, seed: int = 0,
             min_shift: int = 252) -> dict:
    """gate.evaluate(close, green, vehicle) and gate.placebo(..., n=placebo_n) (choice 11), with the vehicles gate.py
    lacks registered (choice 6) and T2b's S&P 500 series extended over the same dates (choice 10)."""
    g = np.asarray(green, dtype=bool)
    with _extra_vehicles(), _spx_ext():
        r = gate.evaluate(close, g, vehicle)
        if placebo_n and len(g) > 2 * min_shift + 1:
            p = gate.placebo(close, g, vehicle, n=int(placebo_n), min_shift=min_shift, seed=seed)
        else:
            p = {"placebo_trade_p": np.nan, "placebo_prob_p": np.nan}
    return {**r, **p, "vehicle": vehicle, "placebo_n": int(placebo_n), "gate_start": close.index[0],
            "gate_end": close.index[-1], "in_position_share": float(g.mean()) if len(g) else np.nan,
            "T1_years_ok": bool(r["years"] >= 7)}


def _gate_job(args):
    key, close, green, vehicle, n, seed = args
    return key, gate_row(close, green, vehicle, n, seed)


def _gate_many(jobs: list, n_jobs: int = 1) -> dict:
    if n_jobs <= 1 or len(jobs) <= 1:
        return dict(_gate_job(j) for j in jobs)
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    _spx_extended()                                       # load gate's SPX and its extension once, before forking
    with ProcessPoolExecutor(max_workers=n_jobs, mp_context=mp.get_context("fork")) as ex:
        return dict(ex.map(_gate_job, jobs, chunksize=1))


def in_position_crypto(res: dict, index) -> pd.Series:
    """Long (True) at the close of daily bar d (index: bar dates, tz-naive or UTC) iff the engine's 00:00 UTC mark
    after bar d holds a long tranche, or a position is still open at the window's end on its last bar (choice 4)."""
    idx = _naive(index).normalize()
    held = set()
    dm = res["daily_mtm"]
    if len(dm):
        dm = dm[dm["notional"].to_numpy(float) > 0]
        T = res["trades"]
        if "side" in T.columns and len(T):
            side = T.set_index("pos")["side"]
            dm = dm[side.reindex(dm["pos"]).fillna(1).to_numpy() > 0]
        held |= set(_naive(pd.DatetimeIndex(dm["time"]) - DAY).normalize())
    T = res["trades"]
    if len(T):
        oe = T[T["open_at_end"].astype(bool) & (T.get("side", 1) > 0)]
        held |= set(_naive(pd.DatetimeIndex(oe["exit_time"]) - DAY).normalize())
    return pd.Series([d in held for d in idx], index=idx, dtype=bool)


# ============================================================================ after tax
def after_tax(equity: pd.Series, realized: pd.Series | None = None, open_gain: float = 0.0,
              income: pd.Series | None = None, st: float = gate.ST_RATE) -> dict:
    """gate.py's tax conventions on a full-mechanics book (choice 9). equity: pre-tax equity at each close (index:
    close dates; the first value is the starting equity); realized: dollar P&L (pre-tax book units) indexed by the
    date it was realized; open_gain: marked gain of the positions open at the end; income: taxable income (T-bill
    interest) indexed by date."""
    E = pd.Series(np.asarray(equity, float), index=_naive(equity.index))
    yrs_idx = E.index.year.to_numpy()
    gains = {}
    for ser in (realized, income):
        if ser is not None and len(ser):
            s = pd.Series(np.asarray(ser, float), index=_naive(ser.index))
            for y, v in s.groupby(s.index.year).sum().items():
                gains[int(y)] = gains.get(int(y), 0.0) + float(v)
    lam, carry, paid = 1.0, 0.0, 0.0
    years = sorted(set(yrs_idx.tolist()))
    for y in years:
        i = int(np.flatnonzero(yrs_idx == y)[-1])
        net = lam * gains.get(y, 0.0) + carry
        if net > 0:
            tax, carry = st * net, 0.0
        else:
            tax, carry = 0.0, net
        ey = E.iloc[i]
        a_y = lam * ey - tax
        paid += tax
        lam = a_y / ey if ey > 0 else 0.0
    A = lam * E.iloc[-1]
    g = lam * float(open_gain) + carry
    if g > 0:
        A -= st * g
        paid += st * g
    e0 = E.iloc[0]
    out = {"mult_pre": float(E.iloc[-1] / e0), "mult_tax": float(A / e0), "tax_paid": float(paid / e0),
           "first": E.index[0], "last": E.index[-1]}
    out["cagr_pre"] = _cagr(out["mult_pre"], E.index[0], E.index[-1])
    out["cagr_tax"] = _cagr(out["mult_tax"], E.index[0], E.index[-1])
    out["max_dd"] = _maxdd(E)
    return out


def _acct_tax(acct: dict, from_day=None) -> dict:
    """after_tax of a bb_engine.assemble account, optionally from the close before `from_day` (UTC day)."""
    E = acct["equity"].copy()
    E.index = _naive(E.index - DAY)                       # value at 00:00 of day d = the close of bar d - 1
    T = acct["trades"]
    inc = acct["interest"].copy()
    inc.index = _naive(inc.index - DAY)
    inc = inc.diff().fillna(inc.iloc[0] if len(inc) else 0.0)
    if from_day is not None:
        d0 = _naive(pd.DatetimeIndex([from_day]))[0] - DAY
        E = E[E.index >= d0]
        inc = inc[inc.index > d0]
    if not len(E) or E.iloc[0] <= 0:
        return {"mult_pre": np.nan, "mult_tax": np.nan, "cagr_pre": np.nan, "cagr_tax": np.nan, "max_dd": np.nan}
    s = 1.0 / E.iloc[0]
    if len(T):
        oe = T["open_at_end"].astype(bool).to_numpy()
        rz = pd.Series(T["pnl_usd"].to_numpy(float)[~oe] * s, index=_naive(pd.DatetimeIndex(T["exit_time"])[~oe]))
        og = float(T["pnl_usd"].to_numpy(float)[oe].sum()) * s
    else:
        rz, og = None, 0.0
    out = after_tax(E * s, rz, og, inc * s if inc.abs().sum() > 0 else None)
    out["positions"] = int(len(T))
    out["liquidations"] = int(T["liquidated"].astype(bool).sum()) if len(T) else 0
    return out


# ============================================================================ ETF book (choice 7)
def _daily_close(sym: str, series: str, days: pd.DatetimeIndex, hours=None) -> pd.Series:
    """Daily closes of `series` ("sig" / "traded") on `days` (tz-naive), carried over days without a bar; from
    bb_data.bars, or from an injected frame (hours: a frame or {sym: frame}) via bb_data.bars_from_hours."""
    if hours is None:
        c = bd.bars(sym, "1d", series)["close"]
    else:
        c = bd.bars_from_hours(_hours(sym, hours), "1d", series)["close"]
    c.index = _naive(c.index)
    return c.reindex(days.union(c.index)).ffill().reindex(days)


def etf_book(results: dict, start=START, end=END, cost: float = ETF_COST, k_slots: int | None = None,
             rule11: bool = True, idle_tbill: bool = False, sessions_late: int = 1, closes: dict | None = None,
             traded: dict | None = None, hours: dict | None = None) -> dict:
    """The ETF route's full mechanics: each coin's engine position quantity at every Binance daily close, executed
    by costs.etf_want's rule at the crypto close of the execution day's bar, cost per side on every quantity traded.
    results: {sym: simulate_coin result}; closes / traded: {sym: Series by bar date} of the ETF price proxy (spot
    close) and of the price the engine's 00:00 marks used (its frame's traded close), loaded from bb_data when None,
    or from hours = {sym: the frame the engine ran on} (a spot_hours frame: both are the spot close). Returns equity
    (index: bar dates, the first value 1.0 at the close before the window), ret, realized, open_gain, income, n_exec,
    fees."""
    syms = list(results)
    K = int(k_slots or len(syms))
    a, b = _naive([_utc_day(start)])[0], _naive([_end_day(end)])[0]
    days = pd.date_range(a, b, freq="D")
    n = len(days)
    C, Q = {}, {}
    for s in syms:
        cs = closes[s] if closes is not None else _daily_close(s, "sig", days, hours)
        ts = traded[s] if traded is not None else _daily_close(s, "traded", days, hours)
        cs = pd.Series(np.asarray(cs, float), index=_naive(cs.index)).reindex(days)
        ts = pd.Series(np.asarray(ts, float), index=_naive(ts.index)).reindex(days)
        C[s] = cs.to_numpy(float)
        dm = results[s]["daily_mtm"]
        dm = dm[dm["notional"].to_numpy(float) > 0]
        d = _naive(pd.DatetimeIndex(dm["time"]) - DAY).normalize()
        pos = days.get_indexer(d)
        ok = pos >= 0
        q = dm["notional"].to_numpy(float)[ok] / ts.to_numpy(float)[pos[ok]]
        tg = {}
        for pi, pid, qq in zip(pos[ok], dm["pos"].to_numpy()[ok], q):
            tg.setdefault(int(pi), {})[int(pid)] = float(qq)
        Q[s] = tg
    td = nyse_trading_days(days[0], days[-1] + pd.Timedelta(days=15)).values
    k = np.searchsorted(td, days.values, side="right") + int(sessions_late) - 1
    e_idx = np.where(k < len(td), days.get_indexer(pd.DatetimeIndex(td[np.minimum(k, len(td) - 1)])), -1)
    src = np.full(n, -1, np.int64)
    for si in range(n):
        if e_idx[si] >= 0:
            src[e_idx[si]] = si                               # later signals overwrite earlier ones
    tb = bd.tbill_daily(days)
    cash = 1.0
    hold = {s: 0.0 for s in syms}
    avg = {s: 0.0 for s in syms}
    M = {}
    eq = np.zeros(n)
    rz_d, rz_v, inc_v = [], [], np.zeros(n)
    E_size, month_eq, prev = None, None, 1.0
    n_exec, fees = 0, 0.0
    frozen = []
    for t in range(n):
        val = prev                                            # equity at the start of the day (previous close)
        if t == 0 or days[t].month != days[t - 1].month:
            if E_size is None:
                E_size = val
            else:
                rm = val / month_eq - 1.0 if month_eq and month_eq > 0 else 0.0
                if rule11 and rm > 0.25:
                    frozen.append(str(days[t].date())[:7])
                else:
                    E_size = val
            month_eq = val
        if src[t] >= 0:
            s_bar = int(src[t])
            for s in syms:
                px = C[s][t]
                if not np.isfinite(px):
                    continue
                tgt = 0.0
                for pid, qq in Q[s].get(s_bar, {}).items():
                    if (s, pid) not in M:
                        M[(s, pid)] = E_size / K
                    tgt += M[(s, pid)] * qq
                dh = tgt - hold[s]
                if abs(dh) * px <= 1e-12:
                    continue
                fee = cost * abs(dh) * px
                if dh > 0:
                    avg[s] = (avg[s] * hold[s] + dh * px + fee) / (hold[s] + dh)
                else:
                    rz_d.append(days[t])
                    rz_v.append(-dh * px - fee - (-dh) * avg[s])
                cash -= dh * px + fee
                hold[s] += dh
                if hold[s] <= 1e-15:
                    hold[s], avg[s] = 0.0, 0.0
                n_exec += 1
                fees += fee
        mkt = sum(hold[s] * C[s][t] for s in syms if hold[s] > 0)
        eq[t] = cash + mkt
        if idle_tbill and t < n - 1 and cash > 0:
            inc_v[t] = cash * tb[t]
            cash += inc_v[t]
        prev = eq[t]
    base = pd.Series([1.0], index=[days[0] - DAY])
    E = pd.concat([base, pd.Series(eq, index=days)])
    og = float(sum(hold[s] * (C[s][-1] - avg[s]) for s in syms if hold[s] > 0))
    return {"equity": E, "ret": E.pct_change().iloc[1:], "realized": pd.Series(rz_v, index=pd.DatetimeIndex(rz_d),
                                                                               dtype=float),
            "open_gain": og, "income": pd.Series(inc_v, index=days), "n_exec": n_exec, "fees": fees,
            "positions": len(M), "frozen_months": frozen, "K": K}


def _book_tax(book: dict, from_day=None) -> dict:
    E, rz, inc = book["equity"], book["realized"], book["income"]
    if from_day is not None:
        d0 = _naive(pd.DatetimeIndex([from_day]))[0] - DAY
        E = E[E.index >= d0]
        rz = rz[rz.index > d0]
        inc = inc[inc.index > d0]
    if not len(E) or E.iloc[0] <= 0:
        return {"mult_pre": np.nan, "mult_tax": np.nan, "cagr_pre": np.nan, "cagr_tax": np.nan, "max_dd": np.nan}
    s = 1.0 / E.iloc[0]
    out = after_tax(E * s, rz * s, book["open_gain"] * s, inc * s if inc.abs().sum() > 0 else None)
    out["positions"] = int(book["positions"])
    out["liquidations"] = 0
    return out


# ============================================================================ routes
_FM_KEYS = ("mult_pre", "mult_tax", "cagr_pre", "cagr_tax", "max_dd", "positions", "liquidations")
_GATE_KEYS = ("verdict", "fails", "T1", "T2", "T2b", "T3", "T4", "T5", "T6", "T7", "years", "trades", "sig_cagr_pre",
              "sig_cagr_tax", "bh_cagr_pre", "bh_cagr_tax", "spy_cagr_tax", "edge_pre", "edge_tax",
              "edge_vs_spy_tax", "edge_tax_alt", "edge_ex_best", "PF", "whipsaw_%", "sig_dd", "bh_dd", "eras",
              "placebo_trade_p", "placebo_prob_p", "placebo_n", "vehicle", "gate_start", "gate_end",
              "in_position_share", "T1_years_ok")


def _summ(gate_rows: list) -> dict:
    v = [r.get("verdict") for r in gate_rows]
    pt = np.array([r.get("placebo_trade_p", np.nan) for r in gate_rows], float)
    pp = np.array([r.get("placebo_prob_p", np.nan) for r in gate_rows], float)
    return {"n_assets": len(gate_rows), "n_TRADE": v.count("TRADE"), "n_PROBATION": v.count("PROBATION"),
            "n_NO_SIGNAL": v.count("NO-SIGNAL"), "expected_false_TRADE": float(np.nansum(pt)),
            "expected_false_PROBATION": float(np.nansum(pp)), "n_placebo_undefined": int(np.isnan(pt).sum())}


def _route_frames(spec: dict, coins: list, hours, frames_cache: dict) -> dict:
    """{sym: the frame the route trades on}: spot_hours() for the spot routes (RH, ETF), bb_data.coin_hours (or the
    injected frame) for CB (choices 5, 13). Cached for the routes() call."""
    out = {}
    for s in coins:
        src = None if hours is None else (hours[s] if isinstance(hours, dict) else hours)
        key = (s, spec["prices"], None if src is None else id(src))
        if key not in frames_cache:
            H = _hours(s, hours)
            frames_cache[key] = spot_hours(H) if spec["prices"] == "spot" else H
        out[s] = frames_cache[key]
    return out


def _route_crypto(name: str, spec: dict, start, end, placebo_n: int, idle_tbill: bool, n_jobs: int, coins=None,
                  say=print, engine_cache: dict | None = None, hours=None, frames_cache: dict | None = None) -> tuple:
    coins = list(coins or spec["coins"])
    cache = {} if engine_cache is None else engine_cache
    frames = _route_frames(spec, coins, hours, {} if frames_cache is None else frames_cache)
    # spot routes run the engine on their spot frame (no 1-minute bars exist for spot); CB lets the engine load the
    # perpetual itself, with its 1-minute stop resolution, unless hours are injected
    eng = {s: frames[s] if (spec["prices"] == "spot" or hours is not None) else None for s in coins}
    rows, summ, accts, audit = [], [], {}, {}
    joins = {s: join_day(s, start, frames[s]) for s in coins}
    closes = {}
    for s in coins:
        J = joins[s]
        if J is None:
            continue
        c = bd.bars_from_hours(frames[s], "1d", spec["series"])["close"]
        c.index = _naive(c.index)
        closes[s] = c[(c.index >= _naive([J - DAY])[0]) & (c.index <= _naive([_end_day(end)])[0])]
    for row, cfg in spec["rows"].items():
        t0 = time.time()
        res = {}
        for s in coins:
            key = (s, cfg, str(start), str(end), spec["prices"], None if eng[s] is None else id(eng[s]))
            if key not in cache:
                cache[key] = be.simulate_coin(s, cfg, start, end, detail=False, hours=eng[s])
            res[s] = cache[key]
            audit[(name, row, s)] = len(res[s]["fills_audit"])
        jobs = []
        for s in coins:
            if s in closes:
                g = in_position_crypto(res[s], closes[s].index)
                jobs.append(((s,), closes[s], g.to_numpy(bool), spec["vehicle"], placebo_n, 0))
        G = _gate_many(jobs, n_jobs)
        by_sym = {}
        for s in coins:
            r = {"route": name, "row": row, "sym": s, "prices": spec["prices"], "window_start": str(start),
                 "join_day": joins[s]}
            if s in closes:
                gr = G[(s,)]
                r.update({k: gr.get(k) for k in _GATE_KEYS})
                if spec["book"] == "etf":
                    fm = _book_tax(etf_book({s: res[s]}, start, end, spec["cost"], 1, cfg.rule11, idle_tbill,
                                            hours={s: frames[s]}), joins[s])
                else:
                    fm = _acct_tax(be.assemble({s: res[s]}, cfg, start, end, idle_tbill=idle_tbill, k_slots=1),
                                   joins[s])
                r.update({"fm_" + k: fm.get(k) for k in _FM_KEYS})
            else:
                r["verdict"] = "n/a (never tradable in the window)"
            rows.append(r)
            by_sym[s] = r
        for gname, gcoins in spec["groups"].items():
            gc = [s for s in gcoins if s in coins]
            if not gc:
                continue
            sub = {s: res[s] for s in gc}
            gfr = {s: frames[s] for s in gc}
            if spec["book"] == "etf":
                bk = etf_book(sub, start, end, spec["cost"], len(gc), cfg.rule11, idle_tbill, hours=gfr)
                fm = _book_tax(bk)
                accts[(name, row, gname)] = bk["equity"]
            else:
                ac = be.assemble(sub, cfg, start, end, idle_tbill=idle_tbill, k_slots=len(gc))
                fm = _acct_tax(ac)
                accts[(name, row, gname)] = ac["equity"]
            bh = bh_crypto(gc, start, end, idle_tbill=idle_tbill, cost_side=spec["cost"], hours=gfr)
            bm = float(bh["equity"].iloc[-1])
            first, last = bh.index[0] - DAY, bh.index[-1]
            spy_c, _ = spy_hurdle(_naive(pd.DatetimeIndex([first, last])))
            grows = [by_sym[s] for s in gc if s in closes]
            srow = {"route": name, "row": row, "group": gname, "K": len(gc), "prices": spec["prices"],
                    "start": str(start), "end": str(end), **_summ(grows),
                    "n_T1_years_ok": int(sum(bool(x.get("T1_years_ok")) for x in grows)),
                    **{"fm_" + k: fm.get(k) for k in _FM_KEYS},
                    "bh_mult": bm, "bh_cagr_pre": _cagr(bm, first, last),
                    "bh_cagr_tax": _cagr(bh_after_tax(bm), first, last),
                    "bh_max_dd": _maxdd(np.r_[1.0, bh["equity"].to_numpy()]), "spy_cagr_tax": spy_c,
                    "idle_tbill": idle_tbill}
            summ.append(srow)
        say(f"  {name} {row}: {len(coins)} coins, {time.time() - t0:.0f}s")
    return rows, summ, accts, audit


def _route_stocks(start, end, placebo_n: int, idle_tbill: bool, n_jobs: int, names: dict | None = None,
                  say=print) -> tuple:
    import analysis_2026.bb_stocks as bs
    cfg = bs.StockCfg()
    groups = names or {"user": list(bs.USER), "etfs": list(bs.ETFS)}
    uniq = list(dict.fromkeys(sum(groups.values(), [])))
    rows, summ, accts, audit = {}, [], {}, {}
    single = {}
    jobs = []
    meta = {}
    for n_ in uniq:
        t0 = time.time()
        res = bs.stock_trades(n_, cfg, start, end)
        single[n_] = res
        audit[("Stocks", "primary", n_)] = len(res["fills_audit"])
        ip = bs.in_position(res, n_)
        f = res["data"][n_]
        j0 = f.index[min(bs.WARMUP - 1, len(f) - 1)]                      # the 60th session's close
        keep = ip.index >= j0
        ip = ip[keep]
        if len(ip) < 2:
            meta[n_] = None
            continue
        close = pd.Series(f["tr"].reindex(ip.index).to_numpy(float), index=ip.index)
        veh = "stock_daily" if abs(bs.cost_of(n_) - gate.VEHICLES["stock_daily"]["cost"]) < 1e-12 \
            else "stock_daily_10bp"
        jobs.append(((n_,), close, ip.to_numpy(bool), veh, placebo_n, 0))
        meta[n_] = ip.index[0]
        say(f"  Stocks {n_}: trades run {time.time() - t0:.0f}s")
    G = _gate_many(jobs, n_jobs)
    for n_ in uniq:
        r = {"route": "Stocks", "row": "primary", "sym": n_, "prices": "stock", "window_start": str(start),
             "join_day": meta.get(n_)}
        if meta.get(n_) is None:
            r["verdict"] = "n/a (too short)"
        else:
            gr = G[(n_,)]
            r.update({k: gr.get(k) for k in _GATE_KEYS})
            fm = _stock_tax(bs.portfolio(single[n_], n_slots=1, lev=1.0, idle_tbill=idle_tbill), meta[n_])
            r.update({"fm_" + k: fm.get(k) for k in _FM_KEYS})
        rows[n_] = r
    for gname, gn in groups.items():
        res = bs.stock_trades(gn, cfg, start, end)
        audit[("Stocks", "primary", gname)] = len(res["fills_audit"])
        port = bs.portfolio(res, n_slots=len(gn), lev=1.0, idle_tbill=idle_tbill)
        fm = _stock_tax(port)
        accts[("Stocks", "primary", gname)] = port["daily"]["equity"]
        bh = bs.benchmark_ew_etfs(start, end, data=bs.universe_data(gn), min_history=bs.WARMUP)
        if idle_tbill:
            bh = bh.assign(ret=np.where(bh["n"] > 0, bh["ret"], bh["rf"]))
        bm = float(np.prod(1.0 + bh["ret"].to_numpy()))
        first, last = bh.index[0], bh.index[-1]
        spy_c, _ = spy_hurdle(pd.DatetimeIndex([first, last]))
        grows = [rows[x] for x in gn if meta.get(x) is not None]
        summ.append({"route": "Stocks", "row": "primary", "group": gname, "K": len(gn), "prices": "stock",
                     "start": str(start), "end": str(end), **_summ(grows),
                     "n_T1_years_ok": int(sum(bool(x.get("T1_years_ok")) for x in grows)),
                     **{"fm_" + k: fm.get(k) for k in _FM_KEYS}, "bh_mult": bm, "bh_cagr_pre": _cagr(bm, first, last),
                     "bh_cagr_tax": _cagr(bh_after_tax(bm), first, last),
                     "bh_max_dd": _maxdd(np.r_[1.0, np.cumprod(1.0 + bh["ret"].to_numpy())]), "spy_cagr_tax": spy_c,
                     "idle_tbill": idle_tbill})
    out_rows = []
    for gname, gn in groups.items():
        for x in gn:
            out_rows.append({**rows[x], "group": gname})
    return out_rows, summ, accts, audit


def _stock_tax(port: dict, from_day=None) -> dict:
    d = port["daily"]
    E = d["equity"].copy()
    E.index = _naive(E.index)
    E = pd.concat([pd.Series([1.0], index=[E.index[0] - DAY]), E]) if len(E) else E
    pos = port["positions"]
    inc = None
    if len(d) and "cash" in d and float(np.abs(d["rf"]).sum()) > 0 and port["log"].get("idle_tbill"):
        cash_prev = np.r_[1.0, d["cash"].to_numpy(float)[:-1]]
        inc = pd.Series(np.maximum(cash_prev, 0.0) * d["rf"].to_numpy(float), index=_naive(d.index))
    if from_day is not None:
        d0 = pd.Timestamp(from_day)
        prior = E[E.index < d0]
        E = E[E.index >= (prior.index[-1] if len(prior) else d0)]
        if inc is not None:
            inc = inc[inc.index >= d0]
    if not len(E) or E.iloc[0] <= 0:
        return {"mult_pre": np.nan, "mult_tax": np.nan, "cagr_pre": np.nan, "cagr_tax": np.nan, "max_dd": np.nan}
    s = 1.0 / E.iloc[0]
    if len(pos):
        oe = pos["open_at_end"].astype(bool).to_numpy()
        rz = pd.Series(pos["pnl"].to_numpy(float)[~oe] * s, index=_naive(pd.DatetimeIndex(pos["exit_date"])[~oe]))
        og = float(pos["pnl"].to_numpy(float)[oe].sum()) * s
    else:
        rz, og = None, 0.0
    out = after_tax(E * s, rz, og, inc * s if inc is not None else None)
    out["positions"] = int(len(pos))
    out["liquidations"] = 0
    return out


def routes(which=("RH", "ETF", "CB", "Stocks"), start=START, end=END, placebo_n: int = 100,
           idle_tbill: bool = False, n_jobs: int = 1, stocks_start: str = "2001-01-01", stocks_end: str = END,
           coins: dict | None = None, stock_names: dict | None = None, say=print, spot_route_start=None,
           hours: dict | None = None, engine_cache: dict | None = None) -> dict:
    """"What the user could run": every route's rows through gate.evaluate (+ gate.placebo) on each asset's
    in-position series at the route's vehicle, with the full-mechanics after-tax CAGR beside it (choices 4-11, 13).
    coins: {route: [syms]} to restrict a crypto route (smoke tests); stock_names: {group: [tickers]} likewise.
    spot_route_start: None (the Full window for every crypto route, the default) or a date (e.g. SPOT_FROM) from which
    the spot routes RH and ETF run instead (choice 4; needs the orchestrator's ruling). hours: {sym: coin_hours-shaped
    frame} to inject (tests); engine_cache: a dict that receives every bb_engine run, keyed (sym, cfg, start, end,
    prices, frame id). Returns gate (DataFrame, one row per route x row x asset), summary (route x row x group:
    verdict counts, expected false passes, the group account and its buy-and-hold and SPY comparators), accounts,
    audit, log (log["T1_cannot_pass"]: the gate rows whose series is shorter than T1's 7 years)."""
    t0 = time.time()
    rows, summ, accts, audit = [], [], {}, {}
    cache: dict = {} if engine_cache is None else engine_cache
    frames: dict = {}
    windows = {}
    for name in which:
        if name == "Stocks":
            r, s, a, au = _route_stocks(stocks_start, stocks_end, placebo_n, idle_tbill, n_jobs, stock_names, say)
            windows[name] = (str(stocks_start), str(stocks_end))
        else:
            spec = ROUTES[name]
            rstart = spot_route_start if (spot_route_start is not None and spec["prices"] == "spot") else start
            r, s, a, au = _route_crypto(name, spec, rstart, end, placebo_n, idle_tbill, n_jobs,
                                        (coins or {}).get(name), say, cache, hours, frames)
            windows[name] = (str(rstart), str(end))
        rows += r
        summ += s
        accts.update(a)
        audit.update(au)
    t1_no = [f"{r['route']}/{r['row']}/{r['sym']}" for r in rows if r.get("T1_years_ok") is False]
    log = {"seconds": round(time.time() - t0, 1), "placebo_n": placebo_n, "idle_tbill": idle_tbill,
           "crypto_window": (str(start), str(end)), "stocks_window": (stocks_start, stocks_end),
           "spot_route_start": None if spot_route_start is None else str(spot_route_start), "windows": windows,
           "T1_cannot_pass": t1_no, "fills_audit_violations": int(sum(audit.values()))}
    return {"gate": pd.DataFrame(rows), "summary": pd.DataFrame(summ), "accounts": accts, "audit": audit, "log": log}


# ============================================================================ TV cross-check (choice 12)
def tv_load(sym: str, drop_forming: bool = True) -> pd.DataFrame:
    """data/tv_full/{sym}_1D.csv: close, exported ATR(14), green (Up Trend line printed), state (either line
    printed); index = bar date (tz-naive UTC). The last row (still forming) is dropped."""
    df = pd.read_csv(TV_DIR / f"{sym}_1D.csv")
    up = pd.to_numeric(df["Up Trend"], errors="coerce")
    dn = pd.to_numeric(df["Down Trend"], errors="coerce")
    out = pd.DataFrame({"close": pd.to_numeric(df["close"], errors="coerce").to_numpy(),
                        "atr": pd.to_numeric(df["ATR"], errors="coerce").to_numpy(),
                        "green": up.notna().to_numpy(), "state": (up.notna() | dn.notna()).to_numpy()},
                       index=pd.DatetimeIndex(pd.to_datetime(df["time"], unit="s"), name="date"))
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out[out["close"].notna()]
    return out.iloc[:-1] if drop_forming else out


def s1_close_only(close: pd.Series, atr: pd.Series, sym: str, warmup: int = WARMUP,
                  ath_warmup: int = 365) -> dict:
    """S1 at L = 1 on a close-only daily series (choice 12): one slot, full compounding. Returns trades (per M),
    equity (at each close, starting at 1.0 on the first bar) and log."""
    c = np.asarray(close, float)
    a = np.asarray(atr, float)
    idx = pd.DatetimeIndex(close.index)
    n = len(c)
    cs = pd.Series(c)
    sma = cs.rolling(20).mean().to_numpy()
    sd = cs.rolling(20).std(ddof=0).to_numpy()
    ub = sma + 2.0 * sd
    mx60 = cs.rolling(60).max().to_numpy()
    ath = cs.cummax().to_numpy()
    cr = _spot_cost(sym)
    cr_tp = be.SPOT_FEE
    eq = np.ones(n)
    E = 1.0
    trades = []
    inpos = False
    q = avg = fees = cashf = e1 = S = TP = 0.0
    a1 = a2 = tpd = False
    ntr = 0
    i_e = -1
    Mx = 1.0
    for i in range(n):
        exited = False
        if inpos:
            reason = None
            if c[i] <= S:
                reason = "stop"
            else:
                if not tpd and c[i] >= TP:                            # resting limit: half at TP
                    qs = 0.5 * q
                    cashf += qs * TP
                    fees += cr_tp * qs * TP
                    q -= qs
                    tpd = True
                if c[i] < sma[i]:
                    reason = "tp+mid" if tpd else "mid"
                elif not tpd:
                    for lvl, done in ((1.02, a1), (1.05, a2)):
                        if not done and c[i] >= lvl * e1 and c[i] >= avg:
                            qa = (1.0 / 3.0) / c[i]
                            avg = (avg * q + c[i] * qa) / (q + qa)
                            q += qa
                            cashf -= 1.0 / 3.0
                            fees += cr / 3.0
                            ntr += 1
                            if lvl == 1.02:
                                a1 = True
                            else:
                                a2 = True
            if reason is not None:
                cashf += q * c[i]
                fees += cr * q * c[i]
                ret = cashf - fees
                E = E + Mx * ret
                trades.append((idx[i_e], idx[i], e1, c[i], S, TP, reason, ntr, ret, False))
                inpos, exited, q = False, True, 0.0
        if not inpos and not exited and i >= warmup - 1 and i >= 1 and np.isfinite(ub[i]) and np.isfinite(a[i]):
            fresh = c[i] > ub[i] and c[i - 1] <= ub[i - 1]
            near = c[i] >= 0.95 * mx60[i] or (i >= ath_warmup - 1 and c[i] >= 0.90 * ath[i])
            Sv = sma[i] - a[i]
            if fresh and near and c[i] > Sv:
                inpos, e1, S = True, c[i], Sv
                TP = e1 + 3.0 * (e1 - S)
                q = (1.0 / 3.0) / e1
                avg = e1
                cashf, fees = -1.0 / 3.0, cr / 3.0
                a1 = a2 = tpd = False
                ntr, i_e, Mx = 1, i, E
        eq[i] = E + (Mx * (cashf + q * c[i] - fees) if inpos else 0.0)
    if inpos:
        ret = cashf + q * c[-1] - fees
        trades.append((idx[i_e], idx[-1], e1, c[-1], S, TP, "window_end", ntr, ret, True))
    T = pd.DataFrame(trades, columns=["entry1_date", "exit_date", "entry1_px", "exit_px", "S", "TP", "exit_reason",
                                      "n_tranches", "ret", "open_at_end"])
    return {"trades": T, "equity": pd.Series(eq, index=idx), "log": {"bars": n, "positions": len(T)}}


def indicator_close_only(close: pd.Series, green, sym: str) -> dict:
    """Long while the exported indicator is green, fills at the close, spot costs (choice 12)."""
    c = np.asarray(close, float)
    g = np.asarray(green, bool)
    cr = _spot_cost(sym)
    cash, sh = 1.0, 0.0
    eq = np.empty(len(c))
    trades, ent, ent_i = [], 0.0, -1
    for i in range(len(c)):
        if g[i] and sh == 0.0:
            ent, ent_i = cash, i
            sh, cash = cash * (1 - cr) / c[i], 0.0
        elif not g[i] and sh > 0.0:
            cash, sh = sh * c[i] * (1 - cr), 0.0
            trades.append((close.index[ent_i], close.index[i], cash / ent - 1.0))
        eq[i] = cash + sh * c[i]
    return {"equity": pd.Series(eq, index=close.index),
            "trades": pd.DataFrame(trades, columns=["entry_date", "exit_date", "ret"])}


def _eq_stats(e: pd.Series) -> dict:
    e = pd.Series(np.asarray(e, float), index=e.index)
    r = e.pct_change().dropna()
    m = float(e.iloc[-1] / e.iloc[0])
    return {"multiple": m, "cagr": _cagr(m, e.index[0], e.index[-1]), "max_dd": _maxdd(e),
            "sharpe": float(r.mean() / r.std() * np.sqrt(365)) if r.std() > 0 else np.nan}


def tv_crosscheck(syms=TV_SYMS, data: dict | None = None) -> dict:
    """S1 on the close-only TradingView exports beside the exported indicator state (choice 12). data: {sym: frame
    shaped like tv_load()} to inject. Returns {sym: {"s1": ..., "indicator": ..., "bh": ..., "stats": DataFrame}}."""
    out = {}
    for s in syms:
        d = tv_load(s) if data is None else data[s]
        s1 = s1_close_only(d["close"], d["atr"], s)
        ind = indicator_close_only(d["close"], d["green"].to_numpy(bool) & d["state"].to_numpy(bool), s)
        T = s1["trades"]
        closed = T[~T.open_at_end.astype(bool)] if len(T) else T
        rows = [{"series": "S1 (close-only)", **_eq_stats(s1["equity"]), "positions": len(T),
                 "hit_rate": float((closed.ret > 0).mean()) if len(closed) else np.nan},
                {"series": "indicator (exported state)", **_eq_stats(ind["equity"]), "positions": len(ind["trades"]),
                 "hit_rate": float((ind["trades"].ret > 0).mean()) if len(ind["trades"]) else np.nan},
                {"series": "buy & hold", **_eq_stats(d["close"]), "positions": 1, "hit_rate": np.nan}]
        out[s] = {"s1": s1, "indicator": ind, "stats": pd.DataFrame(rows).assign(sym=s, first=d.index[0],
                                                                                  last=d.index[-1])}
    return out


# ============================================================================ self-test
def _U(s) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def _toy_hours(start, closes_daily, hi_off=0.1, trades=None, funding=None, seg=None, live=None) -> pd.DataFrame:
    """Hourly path moving linearly within each UTC day from the previous daily close to the day's close; daily bar
    = (previous close, max + hi_off, min - hi_off, close). Perpetual rows, no mark, optional trades / funding /
    seg / live arrays (one value per hour)."""
    cl = np.asarray(closes_daily, float)
    nd = len(cl)
    idx = pd.date_range(_U(start), periods=nd * 24, freq="h").as_unit("ns")
    prev = np.r_[cl[0], cl[:-1]]
    k = np.tile(np.arange(24), nd)
    dday = np.repeat(np.arange(nd), 24)
    cpath = prev[dday] + (cl[dday] - prev[dday]) * (k + 1) / 24.0
    opath = np.r_[cl[0], cpath[:-1]]
    h = np.maximum(opath, cpath) + hi_off
    lo = np.minimum(opath, cpath) - hi_off
    df = pd.DataFrame({"open": opath, "high": h, "low": lo, "close": cpath}, index=idx)
    df.index.name = "open_time"
    n = len(df)
    df["trades"] = np.full(n, 10, np.int64) if trades is None else np.asarray(trades, np.int64)
    df["tradable"] = True
    df["spot_only"] = False
    df["is_perp"] = True
    df["perp_end"] = False
    df["funding"] = 0.0 if funding is None else np.asarray(funding, float)
    for a in ("mark_open", "mark_high", "mark_low", "mark_close"):
        df[a] = np.nan
    for a in bd.PX:
        df["sig_" + a] = df[a]
    df["live"] = True if live is None else np.asarray(live, bool)
    df["sig_live"] = df["live"]
    df["seg"] = 0 if seg is None else np.asarray(seg, np.int64)
    df["quote_volume"] = 1.0
    df["sig_quote_volume"] = 1.0
    return df


def _check_bh(say) -> None:
    """bh_crypto against a hand computation: two coins, warm-up joins, an outage that delays a join by a day, a
    series break (no chaining) and a hole carried at the last close."""
    rng = np.random.default_rng(3)
    nA, offB, nB = 110, 10, 100
    clA = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, nA)))
    clB = 50 * np.exp(np.cumsum(rng.normal(0, 0.03, nB)))
    A = _toy_hours("2021-01-01", clA)
    trB = np.full(nB * 24, 10, np.int64)
    trB[(69 - offB + 1) * 24 + 1:(69 - offB + 2) * 24] = 0          # B: day 70 01:00..23:00 dead -> joins day 71
    segB = np.zeros(nB * 24, np.int64)
    liveB = np.ones(nB * 24, bool)
    gap0, gap1 = (85 - offB) * 24, (89 - offB) * 24                     # B: days 85..88 missing (96 h), seg 1 after
    trB[gap0:gap1] = 0
    liveB[gap0:gap1] = False
    segB[gap1:] = 1
    B = _toy_hours("2021-01-11", clB, trades=trB, seg=segB, live=liveB)
    B.loc[~B["live"], ["open", "high", "low", "close", "sig_open", "sig_high", "sig_low", "sig_close"]] = np.nan
    B[["open", "high", "low", "close"]] = B[["open", "high", "low", "close"]].ffill()
    for a in bd.PX:
        B["sig_" + a] = B[a]
    hours = {"BTC": A, "XTOY": B}
    out = bh_crypto(["BTC", "XTOY"], "2021-01-01", "2021-04-20", hours=hours)
    # hand computation
    days = pd.date_range(_U("2021-01-01"), _U("2021-04-20"), freq="D")
    dA = pd.Series(clA, index=pd.date_range(_U("2021-01-01"), periods=nA, freq="D"))
    dB = pd.Series(clB, index=pd.date_range(_U("2021-01-11"), periods=nB, freq="D"))
    dB = dB.drop(pd.date_range(_U("2021-01-01") + pd.Timedelta(days=85), periods=4, freq="D"))
    JA, JB = _U("2021-01-01") + pd.Timedelta(days=60), _U("2021-01-01") + pd.Timedelta(days=71)
    seg_start = _U("2021-01-01") + pd.Timedelta(days=89)
    exp_j, exp_s, nexp = [], [], []
    for d in days:
        rs, cst = [], 0.0
        if d >= JA:
            rs.append(dA[d] / dA[d - DAY] - 1 if d - DAY in dA.index and d in dA.index else 0.0)
        if d >= JB:
            if d not in dB.index or d == seg_start:
                rs.append(0.0)
            else:
                prevB = dB[dB.index < d].iloc[-1]
                rs.append(dB[d] / prevB - 1)
        n_ = len(rs)
        if d == JA:
            cst += 0.0010 + 0.0002
        if d == JB:
            cst += 0.0010 + 0.0007
        exp_j.append((sum(rs) - cst) / n_ if n_ else 0.0)            # equal weights among the joined coins
        exp_s.append((sum(rs) - cst) / 2.0)                           # 1/K sleeves, cash until a coin joins
        nexp.append(n_)
    exp_j, exp_s, nexp = np.array(exp_j), np.array(exp_s), np.array(nexp)
    got = out["ret"].to_numpy()
    assert out.attrs["join"]["BTC"] == JA and out.attrs["join"]["XTOY"] == JB, out.attrs["join"]
    assert out.attrs["weights"] == "sleeve" and out.attrs["K"] == 2
    assert np.allclose(got, exp_s, atol=1e-13, rtol=0), np.abs(got - exp_s).max()
    assert out["n_held"].iloc[59] == 0 and out["n_held"].iloc[60] == 1 and out["n_held"].iloc[71] == 2
    outj = bh_crypto(["BTC", "XTOY"], "2021-01-01", "2021-04-20", hours=hours, weights="joined")
    assert np.allclose(outj["ret"].to_numpy(), exp_j, atol=1e-13, rtol=0), np.abs(outj["ret"].to_numpy() - exp_j).max()
    # idle T-bill: the cash sleeves earn it (1/K each), all of it before the first join
    out2 = bh_crypto(["BTC", "XTOY"], "2021-01-01", "2021-04-20", idle_tbill=True, hours=hours)
    tb = out2["tbill"].to_numpy()
    assert np.allclose(out2["ret"].to_numpy(), exp_s + (2 - nexp) / 2.0 * tb, atol=1e-13, rtol=0)
    assert np.allclose(out2["ret"].iloc[:60], out2["tbill"].iloc[:60]) and (out2["excess"].iloc[:60].abs() < 1e-15).all()
    out2j = bh_crypto(["BTC"], "2021-01-01", "2021-04-20", idle_tbill=True, hours=hours, weights="joined")
    assert np.allclose(out2j["ret"].iloc[:60], out2j["tbill"].iloc[:60])
    # regression (bench review, finding 4): a third coin listing later keeps its 1/3 sleeve in cash until it joins
    up = 100 * 1.01 ** np.arange(200)
    h3 = {"A": _toy_hours("2021-01-01", up), "B": _toy_hours("2021-01-01", up), "C": _toy_hours("2021-04-01", up[:110])}
    o3 = bh_crypto(["A", "B", "C"], "2021-03-15", "2021-07-19", hours=h3, cost_side=0.0)
    o3j = bh_crypto(["A", "B", "C"], "2021-03-15", "2021-07-19", hours=h3, cost_side=0.0, weights="joined")
    d = _U("2021-04-10")
    assert o3["n_held"][d] == 2 and abs(o3["ret"][d] - 2.0 / 3.0 * 0.01) < 1e-12 and abs(o3j["ret"][d] - 0.01) < 1e-12
    dl = _U("2021-07-01")
    assert o3["n_held"][dl] == 3 and abs(o3["ret"][dl] - 0.01) < 1e-12
    say(f"  (1) bh_crypto = hand computation on {len(days)} days (joins {JA.date()} / {JB.date()} after warm-up and "
        f"an outage day; series break not chained; hole carried), with 1/K sleeves cash until a coin joins (primary) "
        f"and equal weights among joined coins (sensitivity); idle T-bill on the cash sleeves; a late third coin's "
        f"sleeve is cash (2/3 invested) until it joins")


def _ref_daily(H: pd.DataFrame) -> pd.DataFrame:
    """Plain pandas daily resample (independent of bb_data.bars_from_hours)."""
    return H[["open", "high", "low", "close"]].resample("1D").agg({"open": "first", "high": "max", "low": "min",
                                                                     "close": "last"}).dropna()


def _check_ml(say) -> None:
    """moneyline_perp timing (signal at close t -> fill at the 01:00 UTC open of t + 1; an outage moves it to the next
    live hour), costs, funding timing, the account, and the window-start rule."""
    nd = 160
    cl = np.r_[np.linspace(100, 115, 75), np.linspace(115, 80, 12)[1:], np.full(20, 80.0),
               np.linspace(80, 125, 30)[1:], np.full(nd, 125.0)][:nd]
    fund = np.zeros(nd * 24)
    idx = pd.date_range(_U("2022-03-01"), periods=nd * 24, freq="h")
    fund[np.isin(idx.hour, (0, 8, 16))] = 0.0001
    H = _toy_hours("2022-03-01", cl, funding=fund)
    ref = _ref_daily(H)
    g = moneyline(ref)["green"].to_numpy(bool)
    g_eff = g & (np.arange(len(ref)) >= WARMUP - 1)
    # expected state changes: decision at the close of bar b -> first hour >= (b + 1 day) 01:00
    flips = [(b, bool(g_eff[b])) for b in range(len(ref)) if g_eff[b] != (g_eff[b - 1] if b > 0 else False)]
    assert len(flips) >= 3, flips
    b_reentry = flips[2][0]
    dead = ref.index[b_reentry] + DAY + HOUR                         # the re-entry's 01:00 hour has no trades
    H.loc[dead, "trades"] = 0
    res = moneyline_perp(["XTOY"], "2022-03-01", str((ref.index[-1]).date()), k_slots=1, rule11=False,
                         hours={"XTOY": H})
    T = res["coins"]["XTOY"]["trades"]
    exp_times = []
    for b, state in flips:
        tt = ref.index[b] + DAY + HOUR
        if tt == dead:
            tt = tt + HOUR
        exp_times.append((tt, state))
    got_times = []
    for _, r in T.iterrows():
        got_times.append((r.entry1_time, True))
        if r.exit_reason == "signal":
            got_times.append((r.exit_time, False))
    assert got_times == exp_times[:len(got_times)] and len(got_times) >= len(exp_times) - 1, (got_times, exp_times)
    cr = be.TAKER["base"] + be.SLIP_OTHER
    o = H["open"]
    mult = 1.0
    for _, r in T.iterrows():
        e = o[r.entry1_time]
        assert r.entry1_px == e and r.entry1_time.hour in (1, 2)
        if r.exit_reason == "signal":
            x = o[r.exit_time]
            held = (H.index > r.entry1_time) & (H.index <= r.exit_time)
            xc = cr * x / e
        else:
            x = H["close"].iloc[-1]
            held = H.index > r.entry1_time
            xc = 0.0
        f = float((fund[held] * o[held].to_numpy() / e).sum())
        ret = (x - e) / e - cr - xc - f
        assert abs(r.ret - ret) < 1e-12 and abs(r.funding - f) < 1e-12, (r.ret, ret)
        mult *= 1.0 + ret
    assert abs(res["equity"].iloc[-1] - mult) < 1e-10, (res["equity"].iloc[-1], mult)
    # daily marks: 00:00 hours while open, at the previous hour's close
    dm = res["coins"]["XTOY"]["daily_mtm"]
    r0 = T.iloc[0]
    want = H.index[(H.index.hour == 0) & (H.index > r0.entry1_time) & (H.index <= r0.exit_time)]
    got = dm.time[dm.pos == 0]
    assert list(got) == list(want)
    P = H["close"].shift(1)[want]
    assert np.allclose(dm.notional[dm.pos == 0].to_numpy(), (P / r0.entry1_px).to_numpy())
    # window start (choice 2): a 00:00 start while the state is long buys at 01:00 on the state of the bar that closed
    # at the start (not at 00:00 on the bar before it)
    mid = ref.index[flips[0][0]] + pd.Timedelta(days=5)
    assert g_eff[ref.index.get_loc(mid - DAY)] and g_eff[ref.index.get_loc(mid - 2 * DAY)]
    res2 = moneyline_perp(["XTOY"], str(mid.date()), str((ref.index[-1]).date()), k_slots=1, hours={"XTOY": H})
    T2 = res2["coins"]["XTOY"]["trades"]
    assert T2.entry1_time.iloc[0] == mid + HOUR and T2.entry1_px.iloc[0] == o[mid + HOUR], (T2.entry1_time.iloc[0], mid)
    # regression (bench review, finding 3): a window starting the day after a red close whose previous bar was green
    # opens nothing at the start (formerly a 00:00 buy and a 01:00 sell); its first entry is the next green flip's
    b_red = flips[1][0]
    assert not flips[1][1] and g_eff[b_red - 1] and not g_eff[b_red]
    st_r = ref.index[b_red] + DAY
    T_r = moneyline_perp(["XTOY"], str(st_r.date()), str((ref.index[-1]).date()), k_slots=1,
                         hours={"XTOY": H})["coins"]["XTOY"]["trades"]
    assert len(T_r) and T_r.entry1_time.iloc[0] == exp_times[2][0], (T_r.entry1_time.iloc[0], exp_times[2][0])
    # regression (finding 6): vehicle="spot" fills on the signal series (spot), pays no funding, and a perp_end bar
    # does not close it; the perp vehicle fills on the traded series and is closed at perp_end
    Hs = H.copy()
    for a in bd.PX:
        Hs[a] = H["sig_" + a] * 1.02                                   # the perpetual 2% above spot
    sp = ml_coin("XTOY", "2022-03-01", str((ref.index[-1]).date()), vehicle="spot", hours={"XTOY": Hs})["trades"]
    sp0 = ml_coin("XTOY", "2022-03-01", str((ref.index[-1]).date()), vehicle="spot", hours={"XTOY": H})["trades"]
    pp = ml_coin("XTOY", "2022-03-01", str((ref.index[-1]).date()), vehicle="perp", hours={"XTOY": Hs})["trades"]
    assert len(sp) and sp.drop(columns="sym").equals(sp0.drop(columns="sym"))
    assert (sp.entry1_px.to_numpy() == Hs["sig_open"][sp.entry1_time].to_numpy()).all() and (sp.funding == 0).all()
    assert (pp.entry1_px.to_numpy() == Hs["open"][pp.entry1_time].to_numpy()).all() and (pp.funding > 0).any()
    cs = 0.0010 + be.SLIP_OTHER
    e0, x0 = Hs["sig_open"][sp.entry1_time.iloc[0]], Hs["sig_open"][sp.exit_time.iloc[0]]
    assert sp.exit_reason.iloc[0] == "signal" and abs(sp.ret.iloc[0] - ((x0 - e0) / e0 - cs - cs * x0 / e0)) < 1e-12
    t_pe = sp.entry1_time.iloc[0] + pd.Timedelta(hours=30)
    Hp = Hs.copy()
    Hp.loc[t_pe, "perp_end"] = True
    after = Hp.index > t_pe
    Hp.loc[after, "tradable"] = False
    Hp.loc[after, "trades"] = 0
    sp_pe = ml_coin("XTOY", "2022-03-01", str((ref.index[-1]).date()), vehicle="spot", hours={"XTOY": Hp})["trades"]
    pp_pe = ml_coin("XTOY", "2022-03-01", str((ref.index[-1]).date()), vehicle="perp", hours={"XTOY": Hp})["trades"]
    assert sp_pe.drop(columns="sym").equals(sp.drop(columns="sym"))
    assert pp_pe.exit_reason.iloc[0] == "delist" and pp_pe.exit_time.iloc[0] == t_pe + HOUR and len(pp_pe) == 1
    # three slots with S1_L1's sizing (rule 11): the same trades, the first at M = sleeve = 1/3 of equity
    res3 = moneyline_perp(["XTOY"], "2022-03-01", str((ref.index[-1]).date()), k_slots=3, hours={"XTOY": H})
    assert len(res3["trades"]) == len(T) and np.allclose(res3["trades"]["ret"].to_numpy(), T["ret"].to_numpy())
    assert abs(res3["trades"]["M"].iloc[0] - 1.0 / 3.0) < 1e-15
    say(f"  (2) moneyline_perp: {len(T)} positions; every fill at the 01:00 UTC open after the deciding close (02:00 "
        f"after a dead 01:00 hour); ret, funding prints (held into the print, entry hour excluded) and the K=1 "
        f"account = hand computation; 00:00 marks at the previous close; a 00:00 window start buys a long state at "
        f"01:00 and never acts on the bar before the latest (no round trip after a red close); vehicle='spot' fills "
        f"on spot prices, no funding, no perp_end close")


def _check_gate(say) -> None:
    """Gate wiring: gate_row = gate.evaluate (+ gate.placebo) on a toy series, the registered vehicles, and the
    in-position sampling of a real engine run on synthetic hours."""
    rng = np.random.default_rng(11)
    idx = pd.date_range("2012-01-01", "2020-12-31", freq="D")
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.03, len(idx)))), index=idx)
    g = pd.Series(c.to_numpy()).rolling(30).mean().to_numpy() < c.to_numpy()
    for veh in ("crypto_direct", "spot_etf"):
        r = gate_row(c, g, veh, placebo_n=4)
        d = gate.evaluate(c, g, veh)
        p = gate.placebo(c, g, veh, n=4)
        for k, v in {**d, **p}.items():
            assert (r[k] == v) or (isinstance(v, float) and np.isnan(v) and np.isnan(r[k])), (veh, k, r[k], v)
    before = dict(gate.VEHICLES)
    r = gate_row(c, g, "cb_perp", placebo_n=0)
    assert gate.VEHICLES == before
    gate.VEHICLES["cb_perp"] = dict(EXTRA_VEHICLES["cb_perp"])
    try:
        d = gate.evaluate(c, g, "cb_perp")
    finally:
        gate.VEHICLES.pop("cb_perp")
    assert all((r[k] == v) or (isinstance(v, float) and np.isnan(v)) for k, v in d.items())
    assert r["verdict"] == d["verdict"]
    # in-position sampling on an engine run (synthetic hours: a breakout, adds, then a midline exit)
    cl = np.r_[np.tile([100.0, 101.0], 40), [110, 111, 112.5, 116, 117, 100, 100, 99, 100, 101], np.full(20, 100.0)]
    Hs = _toy_hours("2023-01-02", cl)
    res = be.simulate_coin("SYN", be.ROWS["RH_S1"], hours=Hs, mmr=0.005)
    T = res["trades"]
    assert len(T) >= 1 and not res["fills_audit"]
    days = pd.date_range("2023-01-02", periods=len(cl), freq="D")
    ip = in_position_crypto(res, days)
    exp = np.zeros(len(days), bool)
    for _, t_ in T.iterrows():
        closes = pd.DatetimeIndex(days + DAY).tz_localize("UTC")
        exp |= np.asarray((closes > t_.entry1_time) & (closes < t_.exit_time)) if not t_.open_at_end else \
            np.asarray(closes > t_.entry1_time)
    assert (ip.to_numpy() == exp).all(), (ip[ip != exp])
    assert T.entry1_time.iloc[0] == _U("2023-01-02") + pd.Timedelta(days=81) + HOUR
    # regression (bench review, finding 5): T2b's "SPY over the same dates" on the extended S&P 500 series
    import analysis_2026.run_stocks as RS
    base = gate._SPX
    ext = _spx_extended()
    assert gate._SPX is base                                          # nothing patched outside a call
    inside = ext[(ext.index >= base.index[0]) & (ext.index <= base.index[-1])]
    assert inside.index.equals(base.index) and (inside.to_numpy() == base.to_numpy()).all()
    assert ext.index[0] <= pd.Timestamp("1962-01-03") and ext.index[-1] >= pd.Timestamp("2026-10-09")
    assert ext.index.is_monotonic_increasing and not ext.index.duplicated().any()
    rr = ext.pct_change()
    for d_ in (base.index[0], ext.index[ext.index > base.index[-1]][0]):          # splice days: the long series' move
        lg_ = ext.index.get_loc(d_)
        assert abs(rr.iloc[lg_]) < 0.05
    w_in = pd.DatetimeIndex([pd.Timestamp("2012-03-01"), pd.Timestamp("2019-06-28")])
    assert spy_hurdle(w_in) == gate.spy_hurdle(w_in) and gate._SPX is base
    w_out = pd.DatetimeIndex([pd.Timestamp("2001-01-02"), pd.Timestamp("2026-10-16")])
    sl = ext[(ext.index >= w_out[0]) & (ext.index <= w_out[-1])]
    b_ = RS.bh(sl, div=RS.DIV_YIELD["SPX"])
    m_ = (1 + b_["return_pct"] / 100) * (1 - gate.VEHICLES["stock_daily"]["cost"]) ** 2
    m_ = m_ - gate.LT_RATE * (m_ - 1) if m_ > 1 else m_
    want = (gate.cagr(m_, sl.index), b_["max_dd_pct"])
    got_h = spy_hurdle(w_out)
    assert sl.index[0] < pd.Timestamp("2001-01-04") and sl.index[-1] >= pd.Timestamp("2026-10-09")
    assert got_h == want and got_h != gate.spy_hurdle(w_out) and gate._SPX is base, (got_h, want)
    c01 = pd.Series(c.to_numpy(), index=pd.date_range("2001-01-02", periods=len(c), freq="D"))
    r01 = gate_row(c01, g, "crypto_direct", placebo_n=0)
    assert r01["spy_cagr_tax"] == spy_hurdle(c01.index)[0] != gate.spy_hurdle(c01.index)[0] and gate._SPX is base
    say(f"  (3) gate_row = gate.evaluate + gate.placebo (crypto_direct, spot_etf; cb_perp registered only during the "
        f"call); in-position series of an engine run = 'a tranche open at the close' ({int(ip.sum())} closes); T2b's "
        f"S&P 500 extended to {ext.index[0].date()} .. {ext.index[-1].date()} (gate's own values inside "
        f"{base.index[0].date()} .. {base.index[-1].date()}; restored after every call)")


def _check_tax(say) -> None:
    """after_tax = gate.simulate's after-tax book when the book is flat at every year end and at the end."""
    rng = np.random.default_rng(5)
    idx = pd.date_range("2015-01-01", "2022-12-31", freq="D")
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, len(idx)))), index=idx)
    w = (pd.Series(c.to_numpy()).rolling(20).mean().to_numpy() < c.to_numpy())
    flat = (idx.month == 12) & (idx.day >= 20) | (idx.month == 1) & (idx.day <= 3)
    w = w & ~flat
    w[-5:] = False
    cost = 0.0095
    eq, trades, after = gate.simulate(c, w, cost, gate.ST_RATE)
    E = pd.concat([pd.Series([1.0], index=[idx[0] - DAY]), eq])
    # a trade's dollar gain in the pre-tax book: gate's entry spends the cash held before bar i0 (= equity at i0 - 1)
    rz = pd.Series([(eq.iloc[i0 - 1] if i0 > 0 else 1.0) * pct / 100.0 for i0, _, pct in trades],
                   index=pd.DatetimeIndex([idx[i1] for _, i1, _ in trades]))
    at = after_tax(E, rz)
    assert abs(at["mult_tax"] - after) < 1e-10, (at["mult_tax"], after)
    assert abs(at["mult_pre"] - eq.iloc[-1]) < 1e-12
    # regression (bench review, finding 7c): positions straddling year ends and one open at the end, against an
    # independent share-and-basis book under the stated convention (tax paid by a pro-rata slice of every holding,
    # each holding's basis reduced pro rata; the open position taxed on its marked gain, no exit cost)
    rng = np.random.default_rng(15)
    c2 = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0008, 0.03, len(idx)))), index=idx)
    w2 = pd.Series(c2.to_numpy()).rolling(60).mean().to_numpy() < c2.to_numpy()
    w2[-30:] = True
    cash = a_cash = 1.0
    sh = a_sh = basis = a_basis = 0.0
    E2, rz_d, rz_v, gy, carry, n_straddle, i0, n_pay_pos = [], [], [], 0.0, 0.0, 0, None, 0
    cv = c2.to_numpy()
    for i in range(len(cv)):
        if w2[i] and sh == 0.0:
            sh, basis, cash = cash * (1 - cost) / cv[i], cash, 0.0
            a_sh, a_basis, a_cash = a_cash * (1 - cost) / cv[i], a_cash, 0.0
            i0 = i
        elif not w2[i] and sh > 0.0:
            cash = sh * cv[i] * (1 - cost)
            rz_d.append(idx[i])
            rz_v.append(cash - basis)
            a_cash = a_sh * cv[i] * (1 - cost)
            gy += a_cash - a_basis
            n_straddle += int(idx[i0].year != idx[i].year)
            sh = a_sh = basis = a_basis = 0.0
        if i == len(cv) - 1 or idx[i].year != idx[i + 1].year:
            net = gy + carry
            tax, carry = (gate.ST_RATE * net, 0.0) if net > 0 else (0.0, net)
            phi = tax / (a_cash + a_sh * cv[i])
            n_pay_pos += int(tax > 0 and a_sh > 0)
            a_cash, a_sh, a_basis = a_cash * (1 - phi), a_sh * (1 - phi), a_basis * (1 - phi)
            gy = 0.0
        E2.append(cash + sh * cv[i])
    g_end = a_sh * cv[-1] - a_basis + carry
    final = a_cash + a_sh * cv[-1] - (gate.ST_RATE * g_end if g_end > 0 else 0.0)
    assert sh > 0 and n_straddle >= 2 and n_pay_pos >= 2, (sh, n_straddle, n_pay_pos)
    at2 = after_tax(pd.concat([pd.Series([1.0], index=[idx[0] - DAY]), pd.Series(E2, index=idx)]),
                    pd.Series(rz_v, index=pd.DatetimeIndex(rz_d)), open_gain=sh * cv[-1] - basis)
    assert abs(at2["mult_tax"] - final) < 1e-10 * max(1.0, final), (at2["mult_tax"], final)
    say(f"  (4) after_tax = gate.simulate's after-tax multiple on a book flat at every year end "
        f"({len(trades)} trades, {at['tax_paid']:.3f} paid); = an independent share-and-basis book (pro-rata tax "
        f"payment and basis) with {n_straddle} positions straddling year ends, {n_pay_pos} tax payment(s) made from an "
        f"open position, and one open at the end")


def _check_etf_book(say) -> None:
    """etf_book against a hand computation: a full-size position marked open at the closes Fri .. Wed executes at
    Monday's bar (the session after Fri / Sat / Sun) and is sold at Friday's bar (the session after Thursday)."""
    days = pd.date_range("2024-03-01", "2024-03-20", freq="D")              # 2024-03-01 is a Friday
    rng = np.random.default_rng(2)
    C = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(days)))), index=days)
    TRc = C * 1.001                                                          # mark (perp) close
    q = 0.004
    held = pd.date_range("2024-03-01", "2024-03-06", freq="D")              # Fri .. Wed closes
    dm = pd.DataFrame({"pos": 0, "time": (held + DAY).tz_localize("UTC"), "notional": q * TRc[held].to_numpy(),
                       "mtm": 0.0, "margin": 1.0, "sym": "BTC"})
    res = {"BTC": {"daily_mtm": dm, "trades": pd.DataFrame()}}
    bk = etf_book(res, "2024-03-01", "2024-03-20", cost=ETF_COST, k_slots=1, closes={"BTC": C},
                  traded={"BTC": TRc})
    mon, fri = pd.Timestamp("2024-03-04"), pd.Timestamp("2024-03-08")
    hq = 1.0 * q
    buy_fee = ETF_COST * hq * C[mon]
    sell_fee = ETF_COST * hq * C[fri]
    final = 1.0 - buy_fee + hq * (C[fri] - C[mon]) - sell_fee
    E = bk["equity"]
    assert abs(E[pd.Timestamp("2024-03-03")] - 1.0) < 1e-15                  # nothing executes before Monday
    assert abs(E[mon] - (1.0 - buy_fee)) < 1e-13
    assert abs(E.iloc[-1] - final) < 1e-13 and bk["n_exec"] == 2
    assert abs(bk["realized"].sum() - (hq * C[fri] * (1 - ETF_COST) - (hq * C[mon] + buy_fee))) < 1e-13
    w = etf_want(days, np.isin(days, held), 1)
    assert list(days[w]) == list(pd.date_range(mon, fri - DAY, freq="D"))
    say("  (5) etf_book = hand computation (Fri-Sun closes execute Monday, Wednesday's last close executes Friday; "
        "fees and realized gain), consistent with costs.etf_want")


def _check_tv(say, real: bool = True) -> None:
    """S1 on a close-only series against a hand-computed trade (entry, two adds, TP half, midline exit); real
    exports: mechanics only (no return printed)."""
    base = np.tile([100.0, 101.0], 40)
    path = np.r_[base, [110.0, 111.0, 112.5, 116.0, 150.0, 140.0, 100.0], np.full(10, 100.0)]
    idx = pd.date_range("2020-01-01", periods=len(path), freq="D")
    close = pd.Series(path, index=idx)
    atr = pd.Series(2.0, index=idx)
    out = s1_close_only(close, atr, "BTC")
    T = out["trades"]
    assert len(T) == 1, T
    t = T.iloc[0]
    i = 80
    sma = close.rolling(20).mean()
    S = sma.iloc[i] - 2.0
    e1 = 110.0
    TP = e1 + 3 * (e1 - S)
    assert t.entry1_date == idx[i] and abs(t.S - S) < 1e-12 and abs(t.TP - TP) < 1e-12
    cr = 0.0010 + 0.0002
    q = (1 / 3) / 110 + (1 / 3) / 112.5 + (1 / 3) / 116
    cash = -1.0 + 0.5 * q * TP + 0.5 * q * 100.0
    fees = cr * 1.0 + 0.0010 * 0.5 * q * TP + cr * 0.5 * q * 100.0
    assert close.iloc[86] < sma.iloc[86] and close.iloc[85] >= sma.iloc[85]
    assert t.exit_date == idx[86] and t.exit_reason == "tp+mid" and t.n_tranches == 3
    assert abs(t.ret - (cash - fees)) < 1e-12, (t.ret, cash - fees)
    assert abs(out["equity"].iloc[-1] - (1 + t.ret)) < 1e-12
    ind = indicator_close_only(close, np.r_[np.zeros(80, bool), np.ones(6, bool), np.zeros(len(path) - 86, bool)],
                               "BTC")
    assert abs(ind["equity"].iloc[-1] - (1 - cr) ** 2 * 100.0 / 110.0) < 1e-12
    msg = "  (6) TV cross-check: close-only S1 = hand-computed trade (entry, adds at 1.02/1.05, TP half, midline exit)"
    if real:
        res = tv_crosscheck()
        n = {s: (len(r["s1"]["equity"]), int(len(r["s1"]["trades"]))) for s, r in res.items()}
        assert all(v[0] > 300 for v in n.values())
        msg += "; real exports ran (bars, positions): " + ", ".join(f"{s} {v[0]}/{v[1]}" for s, v in n.items())
    say(msg)


def _check_bh_real(say) -> None:
    """Benchmark known answer on real data: one-coin bh_crypto vs the data inventory's buy-and-hold table (section 8:
    from the 00:00 UTC hourly bar's close of the window's first day, spot closes, before costs). bh_crypto starts at
    the daily close before that day (one hour earlier) and pays the spot cost once, hence the 1.5-point tolerance."""
    inv = {("2024-07-01", "BTC"): 30, ("2024-07-01", "ETH"): -30, ("2024-07-01", "SOL"): -29,
           ("2025-06-16", "BTC"): -23, ("2025-06-16", "ETH"): -5, ("2025-06-16", "SOL"): -31}
    got = {}
    for (st, s), v in inv.items():
        r = bh_crypto([s], st, END)
        got[(st, s)] = (float(r["equity"].iloc[-1]) - 1.0) * 100
        assert abs(got[(st, s)] - v) < 1.5, (st, s, got[(st, s)], v)
    say("  (9) bh_crypto vs the data inventory's buy-and-hold table (benchmark): " + ", ".join(
        f"{s} from {st} {got[(st, s)]:+.1f}% (table {v:+d}%)" for (st, s), v in inv.items()))


def _check_spot_route(say) -> None:
    """Regression (bench review, findings 1 and 2): the RH and ETF routes trade spot prices (spot_hours), CB the
    perpetual, through routes() on injected hours: a perpetual 1% above spot and a perpetual-only wick through S.
    Also spot_hours' trades / tradable / perp_end rules and the T1 flags."""
    cl = np.r_[np.tile([100.0, 101.0], 40), [110, 111, 112.5, 116, 117, 100, 100, 99, 100, 101], np.full(20, 100.0)]
    H = _toy_hours("2023-01-02", cl)
    for a in bd.PX:
        H[a] = H["sig_" + a] * 1.01
    H["mark_low"] = H["low"]
    H["funding"] = np.where(H.index.hour % 8 == 0, 0.0001, 0.0)
    # spot_hours: traded columns = the signal series; spot costs; no funding / mark; perp_end only where the spot
    # series ends early; a live signal hour without volume is an outage
    Hx = H.copy()
    Hx.loc[Hx.index[-48]:, "sig_live"] = False
    Hx.loc[Hx.index[100], "sig_quote_volume"] = 0.0
    sx = spot_hours(Hx)
    assert (sx[bd.PX].to_numpy() == Hx[["sig_" + a for a in bd.PX]].to_numpy()).all()
    assert sx["spot_only"].all() and not sx["is_perp"].any() and (sx["funding"] == 0).all() and sx["mark_low"].isna().all()
    assert sx["trades"].iloc[100] == 0 and sx["trades"].iloc[99] == 1 and (sx["trades"].iloc[-48:] == 0).all()
    assert sx["perp_end"].sum() == 1 and sx["perp_end"].iloc[-49] and not sx["tradable"].iloc[-48:].any() and \
        sx["tradable"].iloc[:-48].all()
    # S1 entry and stop of the plain run, then a perpetual-only wick 10% below S 30 h after the entry
    r0 = be.simulate_coin("BTC", be.ROWS["RH_S1"], hours=spot_hours(H), mmr=0.005)["trades"].iloc[0]
    wick = r0.entry1_time + pd.Timedelta("30h")
    H.loc[wick, "low"] = r0.S * 0.90
    H.loc[wick, "mark_low"] = r0.S * 0.95
    assert H.loc[wick, "sig_low"] > r0.S
    end = str(H.index[-1].date())
    cache: dict = {}
    out = routes(which=("RH", "ETF", "CB"), start="2023-01-02", end=end, placebo_n=0,
                 coins={"RH": ["BTC"], "ETF": ["BTC"], "CB": ["BTC"]}, hours={"BTC": H}, engine_cache=cache,
                 say=lambda *a: None)
    seen = set()
    for key, res in cache.items():
        sym, cfg, _, _, prices, _ = key
        T = res["trades"]
        assert not res["fills_audit"] and len(T), key
        t = T.iloc[0]
        route = "CB" if cfg.cost_side == CB_COST else ("ETF" if cfg.cost_side == ETF_COST else "RH")
        seen.add(route)
        px_col = "sig_open" if prices == "spot" else "open"
        assert prices == ROUTES[route]["prices"]
        assert (T.entry1_px.to_numpy() == H[px_col][T.entry1_time].to_numpy()).all(), (route, key)
        if prices == "spot":
            assert (T.funding == 0).all() and not ((T.exit_reason == "stop") & (T.exit_time == wick + HOUR)).any()
        if cfg.timing == "core":                                        # S1 rows: the same signal, entry 01:00
            assert t.entry1_time == r0.entry1_time
            if prices == "spot":
                assert t.exit_reason in ("mid", "tp+mid") and t.exit_time > wick + HOUR, (route, t.exit_reason)
            else:
                assert t.exit_reason == "stop" and t.exit_time == wick + HOUR, (route, t.exit_reason, t.exit_time)
    assert seen == {"RH", "ETF", "CB"}, seen
    G = out["gate"]
    assert set(G["prices"]) == {"spot", "traded"} and (G.loc[G.route != "CB", "prices"] == "spot").all()
    assert (~G["T1_years_ok"].astype(bool)).all() and len(out["log"]["T1_cannot_pass"]) == len(G)
    assert out["log"]["fills_audit_violations"] == 0
    say("  (7) spot routes (synthetic, through routes()): RH and ETF fill on spot (perpetual 1% above spot ignored), no "
        "funding, and a perpetual-only wick through S does not stop them; CB fills on the perpetual and is stopped by "
        "it; spot_hours outages / series end; T1 flags on every short gate series")


def _check_routes_smoke(say) -> None:
    """Mechanics only on real data: RH on three coins, CB and ETF on BTC/ETH and the Stocks route on two tickers,
    placebo 2; then ETF from SPOT_FROM (placebo 0). Asserts shapes, an empty fill audit, RH/ETF fills at spot opens,
    and the T1 flags. Prints no verdict or return."""
    t0 = time.time()
    cache: dict = {}
    rh = ["BTC", "SOL", "DOGE"]
    out = routes(which=("RH", "CB", "ETF", "Stocks"), placebo_n=2, n_jobs=1, coins={"RH": rh},
                 stock_names={"user": ["TSLA", "SPY"]}, engine_cache=cache, say=lambda *a: None)
    G, S = out["gate"], out["summary"]
    assert out["log"]["fills_audit_violations"] == 0, out["audit"]
    assert len(G) == 4 * 3 + 3 * 2 + 4 * 2 + 2 and len(S) == 4 * 2 + 3 + 4 + 1, (len(G), len(S))
    assert G["verdict"].isin(["TRADE", "PROBATION", "NO-SIGNAL"]).all()
    assert G["fm_cagr_tax"].notna().all() and S["fm_cagr_tax"].notna().all() and S["spy_cagr_tax"].notna().all()
    assert (G["T1_years_ok"].astype(bool) == (G["years"] >= 7)).all()
    crypto = G[G.route != "Stocks"]
    # on the Full window no crypto gate series reaches T1's 7 years: flagged, not hidden (choice 4)
    assert (~crypto["T1_years_ok"].astype(bool)).all() and \
        set(out["log"]["T1_cannot_pass"]) >= {f"{r.route}/{r.row}/{r.sym}" for r in crypto.itertuples()}
    n_spot, spot_fr = 0, {}
    for key, res in cache.items():
        sym, cfg, _, _, prices, fid = key
        if prices != "spot":
            continue
        if sym not in spot_fr:
            spot_fr[sym] = spot_hours(bd.coin_hours(sym))
        Hs = spot_fr[sym]
        T = res["trades"]
        assert len(T) and (T.entry1_px.to_numpy() == Hs["sig_open"][T.entry1_time].to_numpy()).all(), key
        assert (T.funding == 0).all()
        n_spot += 1
    assert n_spot == 4 * 3 + 4 * 2, n_spot
    # the spot routes from Binance spot's first day (choice 4's alternative): BTC and ETH then span over 7 years
    ext = routes(which=("ETF",), placebo_n=0, spot_route_start=SPOT_FROM, say=lambda *a: None)
    Ge = ext["gate"]
    assert (Ge["window_start"] == SPOT_FROM).all() and Ge["T1_years_ok"].astype(bool).all() and \
        ext["log"]["fills_audit_violations"] == 0
    yrs = Ge.groupby("sym")["years"].first()
    say(f"  (8) routes smoke (real data, mechanics only): {len(G)} gate rows, {len(S)} group rows, fill audit empty; "
        f"RH/ETF entries at spot opens; on the Full window every crypto gate series is shorter than T1's 7 years "
        f"(flagged); ETF from {SPOT_FROM}: " + ", ".join(f"{k} {v:.2f} years" for k, v in yrs.items())
        + f"; {time.time() - t0:.0f}s (no verdict or return printed)")


def selftest(real: bool = True) -> None:
    t0 = time.time()
    say = print
    say("bb_bench selftest")
    _check_bh(say)
    _check_ml(say)
    _check_gate(say)
    _check_tax(say)
    _check_etf_book(say)
    _check_tv(say, real)
    _check_spot_route(say)
    if real:
        _check_routes_smoke(say)
        _check_bh_real(say)
        indicator_crosscheck(say)
    say(f"bb_bench selftest passed in {time.time() - t0:.0f}s")


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m analysis_2026.bb_bench")
    ap.add_argument("cmd", choices=["selftest", "crosscheck", "routes", "tv"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--placebo", type=int, default=100)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--synthetic-only", action="store_true")
    ap.add_argument("--spot-route-start", default=None,
                    help=f"run RH and ETF from this date (e.g. {SPOT_FROM}) instead of the Full window (choice 4)")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest(real=not a.synthetic_only)
    elif a.cmd == "crosscheck":
        indicator_crosscheck()
    elif a.cmd == "routes":
        if not a.out:
            raise SystemExit("--out DIR is required (results are written, not printed)")
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        r = routes(placebo_n=a.placebo, n_jobs=a.jobs, spot_route_start=a.spot_route_start)
        r["gate"].to_csv(out / "routes_gate.csv", index=False)
        r["summary"].to_csv(out / "routes_summary.csv", index=False)
        print(f"wrote {len(r['gate'])} gate rows and {len(r['summary'])} group rows to {out}; "
              f"fill-audit violations {r['log']['fills_audit_violations']}; windows {r['log']['windows']}; "
              f"{len(r['log']['T1_cannot_pass'])} gate rows shorter than T1's 7 years; {r['log']['seconds']}s")
    elif a.cmd == "tv":
        if not a.out:
            raise SystemExit("--out DIR is required (results are written, not printed)")
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        res = tv_crosscheck()
        pd.concat([v["stats"] for v in res.values()]).to_csv(out / "tv_crosscheck.csv", index=False)
        pd.concat([v["s1"]["trades"].assign(sym=s) for s, v in res.items()]).to_csv(out / "tv_s1_trades.csv",
                                                                                     index=False)
        print(f"wrote the TV cross-check for {len(res)} coins to {out}")


if __name__ == "__main__":
    _main()
