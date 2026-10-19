"""
Stocks and ETFs for the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md: "Stocks and ETFs
('all of our assets')", the stock lines of "Data" and "Windows", HS1 and HS2 in "The tests", "Units and
statistics" (trade return, drift-adjusted unit, portfolio-level tests), S20's stock version, the "Fill audit" and
"Look-ahead check" controls, and the Stocks route of "What the user could run"). Contract: the scratchpad's
bb_engine_spec.md, "bb_stocks.py". Daily bars only (the repo has no historical intraday stock bars).

    python3 -m analysis_2026.bb_stocks selftest   # synthetic known answers; mechanics and timing on the real data
                                                  # (counts, fill audit and timings only: no strategy return is printed)

Public API
  StockCfg(bars="1d"|"1w", bb_n=20, bb_k=2.0, cost_mult=1.0, lev=1.0);  ROWS = primary, costs2x, lev2, S20
  universe_data(which) -> {name: DataFrame[open, high, low, close, tr, member, close_only, flat]}
      which = "members" | "etfs" | "user" | a ticker | a list of tickers (each from its pre-registered price
      source; attrs: cost, dead, spells)
  stock_trades(ticker_or_universe, cfg_stock=StockCfg(), start="2001-01-01", end=END, ohlc=None) -> dict
      trades (one row per position, every signal of every name, no cap), tranches, expo (daily), daily_mtm,
      signals (every fresh signal with its status), fills_audit (must be empty), log; plus the candidate paths the
      portfolio uses (cand, paths, cand_tr) and the window calendar
  portfolio(res, n_slots=20, seed=SEED, rank="random"|"atr_dist", lev=1.0, idle_tbill=True) -> dict
      daily (equity, ret, rf, excess, cash, notional, gross_lev, n_pos, ...), positions, log
  portfolio_seeds(res, seeds=SEEDS_FURTHER, ...) -> DataFrame of daily excess returns, one column per seed
  random_entry_book(res, port, seed=SEED, ...) -> dict shaped like portfolio(): the matched random-entry book
  benchmark_ew_members(start, end, data=None) / benchmark_ew_etfs(start, end, data=None, min_history=60)
      -> DataFrame (ret, rf, excess, n) on the same session calendar
  flat_flag(frame) -> bool array: the session's source row is close-only (column close_only) or O = H = L = C
  session_returns(data) -> {name: Series}   total-return close-to-close return per session (bb_stats.drift_adjust)
  in_position(res, name) -> bool Series     long while any tranche is open, on closes (gate.evaluate's input)
  half_of(dates) -> labels "1996-2000" | "2001-2013" | "2014-2026" | ""

Outputs of stock_trades (per-M units: every price path is in units of the position's maximum notional M = 1)
  trades      one row per position of the chained book (a name holds one position at a time; a signal while it is
              in a position is "in_position"): pos, sym, member, signal_day (pairing key, session date),
              entry1_date / entry1_time, entry1_px, S, TP, L_used, exit_date / exit_time, exit_reason ("stop",
              "mid", "dead", "window_end", prefixed "tp+" after the TP half), stop_fill ("level", "open",
              "flat_close"), side (+1), n_tranches, max_frac, ret (net / M, incl. financing at lev > 1),
              ret_gross (before costs), ret_1x (before financing), fees, divs, fin, liquidated (False),
              hold_days (sessions), hold_h, open_at_end, atH_only, tp_hit, deferred (Friday), rolled (Friday or a
              flat bar), adds_cancelled, rank_key, half
  tranches    pos, sym, time (UTC), date, px, notional (signed, / M), kind (entry, add, tp, exit, stop, dead; "mark"
              = the window-end valuation, not a fill), phase (open, intraday, close)
  expo        pos, sym, time (session date), notional: the daily exposure path for bb_stats.drift_adjust
  daily_mtm   pos, sym, date, pnl (cumulative net P&L / M at that close), value (notional / M at that close)
  signals     every fresh signal whose (would-be) entry falls in the window: sym, signal_day, chain_status
              (entered | in_position | recheck_fail | not_member | open_le_S | no_session | no_stop_level),
              status (the candidate's own outcome as if the name were flat), pos (when traded)
  cand, paths, cand_tr   every entered candidate (incl. those the chained book ignores) with its per-session path
              (dcash, value, reserved adds) and fills: the portfolio's input. fills_audit (list, must be empty; it
              includes any fill on a flat or close-only bar other than the flat-bar stop and the dead close), log
              (counts: signals, trades, close_only_rows, flat_rows, share_adj_folded, div_days_gt10pct, ...).

Rules as the pre-registration fixes them ("Stocks and ETFs")
- Signal (daily close t, split-adjusted chart OHLC): C_t > UB_t of BB(20, 2) (population sigma) with
  C_{t-1} <= UB_{t-1}, and [C_t >= 0.95 x the max high of the last 60 bars including t, or C_t >= 0.90 x ATH_t]
  (ATH_t = the highest high of the file to t; "the longest file available": for every member the universe_pit_all
  file starts on the same day as its raw_pit history, checked). No signal before 60 completed bars; the ATH
  branch needs 365. Long only.
- Prices. Signals: members universe_pit_all OHLC / ma_bounce.chart_factor(); ETFs, TSLA, COIN, HOOD raw_pit OHLC;
  CRCL universe_recent_raw OHLC. P&L: total return, the cash dividend credited on its ex-date to shares held at
  the previous close: D_d = C_{d-1} x (1 - q_{d-1} / q_d), q = total-return close / chart close (members: the
  universe_pit_all close over the chart close, i.e. chart_factor's q; ETFs, TSLA, COIN, HOOD: chart_factor's q of
  raw_pit; CRCL: universe_recent_raw adj / close).
- Fills. Entry at the next session's open; a Friday entry is deferred to the next session and the latest
  completed bar must still satisfy the signal; skipped if that open is at or below S. S = SMA20 - 1.0 x ATR14 of
  the latest completed bar at entry; TP = entry1 + 3 x (entry1 - S), selling 50% of the position. First tranche
  M/3; adds of M/3 trigger on a daily close >= 1.02 / 1.05 x entry1 (both at once above 1.05) and fill at the next
  open; an add is cancelled if that open is below the average entry, if a trend exit is pending, or once the TP
  has filled. Stop and TP fill intraday at their level, or at the open if it gaps through; a bar touching both
  fills the stop first. Trend exit: a close below SMA20, filled 100% at the next open. A flat bar (open = high =
  low = close, or a close-only source row) creates no signal, entry or add, and triggers the stop only if its close
  is at or below S, filled at that close. Close-only rows are flagged from data/raw_pit (open, high or low missing:
  615,018 member rows, mostly CRSP), because universe_pit_all writes them as open = previous close, high / low =
  max / min(open, close), which is not O = H = L = C. A position whose prices end (dead name) is closed at the last
  close.
- A name opens a position only on a day it is an S&P 500 member (members universe). Costs per side: 3 bp
  (members, ETFs, TSLA, SPY, QQQ, IWM), 10 bp (COIN, HOOD, CRCL); cost_mult=2 is the double-cost sensitivity.
  Leverage 1x primary; 2x Reg-T (exploratory) with the borrowed part charged the T-bill + 2.5 points a year.
- Trade return = net P&L of the whole position / M (M = the maximum notional; M = 1 in every per-trade unit).
- Portfolio (HS1's Sharpe test): at most 20 positions, M = equity / 20 (x lev) at entry, total notional <= lev x
  equity; more entries than free slots -> slots filled in an order drawn each session with
  numpy.random.default_rng(20261018) (100 further seeds: SEEDS_FURTHER); "atr_dist" ranks by (close - upper band)
  / ATR14 of the bar that decided the entry, largest first, ties alphabetical. Idle cash earns the 3-month T-bill
  (bb_data.tbill_session, 252 basis; idle_tbill=False is the zero-interest version); excess = return - T-bill.
- Benchmarks: equal-weight point-in-time members (total return, rebalanced daily, a member whose prices end held
  at its last close while it stays a member, no costs) and equal-weight ETFs listed at the time; both fully
  invested, on the portfolio's session calendar.
- Windows (start / end are inclusive session dates; a 'YYYY' or 'YYYY-MM' end covers that year / month): primary
  2001-01-01..2026-10-16 (halves 2001-2013 / 2014-2026); 1996-2000 separately. A window starts
  flat with equity 1; indicators use the full history before it; a trade belongs to the window of its entry; a
  position open at the window's end is marked at the last close (open_at_end, no exit cost).

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. Rule 6, rules 13-15 and the crypto timing windows are not part of the stock version (its rule list names only
   the signal, stop, 3R half take-profit, midline exit, pyramiding and the Friday deferral).
2. "Friday entry": the entry session's weekday is Friday (whatever the signal day). The deferred entry fills at
   the next session's open; "still satisfy the signal" = C > UB and the near-high condition on the latest
   completed bar (freshness belongs to the episode start, so it is not re-required), and S then comes from that
   bar. A pending entry, add or trend exit whose fill session is a flat bar waits for the next non-flat open (an
   entry that waits re-checks the signal the same way). Flat bars create no entry signal and no trend-exit signal
   ("it triggers a pending stop only"); their close still enters the indicators and the re-check (it is a real
   close), and close-only rows keep universe_pit_all's OHLC in the indicators (the pre-registered price source).
   "Flat" is a property of the session's data, not of its prices: flat_flag = the source row is close-only
   (raw_pit) or the bar is exactly O = H = L = C, fixed when the data are loaded (like `trades == 0` in the crypto
   data) and treated as known at the session's open (the name does not trade that session, or its intraday prices
   were not recorded). So an order at the 09:30 open never depends on that session's high, low or close, and the
   look-ahead perturbation (which keeps the open) cannot change it. S20: a week is flat only if all its sessions
   are flat.
3. An add whose fill is cancelled (open below the average entry) can trigger again on a later close above its
   threshold; after the TP no add is placed again (as bb_engine's choice 6). "If one bar touches both, the stop
   fills first" resolves the unknown order inside a bar that opens between S and TP and reaches both (the whole
   position stops at S). A bar that opens at or above TP has filled the resting TP half at its open, which comes
   before the rest of the bar, whatever its low; a pending add at that open is cancelled by the TP, and the stop
   then applies to the remaining half ("tp+stop") if the bar reaches S. So the 09:30 fills use the open alone (the
   look-ahead control). bb_engine instead stops the whole position in an hour that opens above TP and reaches S
   (its TP fill there is stamped at the hour's close); in 24/7 hourly bars that case needs an outage gap, while
   stock bars gap overnight. A trend exit pending at an open (a market order at the open) fills there, after the
   TP half if that open is also >= TP ("tp+mid").
4. Dead name = its file ends more than 7 days before the price sources' last session (the latest date of raw_pit
   and universe_recent_raw, 2026-10-14; ma_bounce's 7-day convention), set by the loaders in attrs['dead'], so a
   name is dead whether it runs alone or in a universe (injected frames without attrs['dead'] are judged against
   the last date of the names in the call); the close at the last close pays the exit cost. A name whose file
   ends within 7 days of that date is marked there (open_at_end). Two universe_pit_all rows with the open or close outside [low, high] have high/low
   widened to include them (counted in log["ohlc_repaired"]), so the fill audit tests the engine, not the data.
5. Membership is required on the entry session only (adds and exits continue after a name leaves the index, as
   S12's crypto rule keeps open positions). A signal whose entry session is not a member day is skipped
   ("not_member"); it does not wait for a later inclusion date (bb_engine's S12 choice 21 instead lets a pending
   signal wait for a window in which the coin is a member). The ETF and user-ticker universes have no membership
   constraint.
6. Weekly bars (S20): Monday-labelled weeks of the name's own sessions (moneyline_ref.to_weekly's grouping); the
   signal, re-check, trend exit and S use weekly bars (BB(20, 2), ATR14 and SMA20 in weekly bars, needing 20
   completed weeks), decided at the week's last session's close and filled at the next session's open; the
   near-high look-back stays 60 daily bars (max daily high of the 60 sessions to the week's last one) and the
   warm-up stays 60 / 365 daily bars; adds, stop and TP stay on daily bars. A still-forming last week of the data
   is treated as complete (it can only matter at the last session, where nothing can fill afterwards).
7. Daily exposure path (drift adjustment): a session is split into an overnight half (close d-1 -> open d) and an
   intraday half (open d -> close d); a fill at the open changes the notional at the boundary, an intraday fill
   at a level is placed at the intraday midpoint, a fill at the close at the end. expo_d = 0.5 x shares at close
   d-1 x C_{d-1} + 0.25 x (shares after the open fills + shares after the intraday fills) x O_d, per unit of M,
   indexed by session date (the session_returns index). An open-to-open holding of N sessions sums to N.
8. Times: session dates are tz-naive dates (bb_stats.month_key uses the session date for stocks). entry1_time and
   exit_time are UTC timestamps: open fills at 09:30 New York, intraday and close fills at 16:00 New York (the
   time the bar's range is complete; half-day sessions are not modelled).
9. Portfolio sizing: M = lev x equity at the previous close / 20, capped so that cash never falls below
   -(lev - 1) x that equity after reserving (1 + cost) x M/3 for each add a position can still make (so total
   notional <= lev x equity, and 1x never borrows). Slots and cash released by exits at a session's open can be
   reused at the same open; exits during a session release them after its close. A name is eligible only if the
   portfolio holds no position in it at the signal close. The random draw: one uniform key per candidate entry,
   drawn in order of (entry session, symbol), keys ascending within a session (equivalent to drawing a fresh
   order each session). Financing at 2x is charged on the portfolio's actual borrowed cash; idle positive cash
   earns the T-bill. Trade-level 2x rows charge (lev - 1) / lev of each position's previous-close notional the
   T-bill + 2.5 points per session (252 basis).
10. Matched random-entry book: each position the 20-slot portfolio takes gets a twin in a member drawn uniformly
   (default_rng(seed)) among members with a non-flat bar that session and no open twin; the twin buys and sells
   the same fractions of M at the twin's prices on the same sessions (entry and adds at the open, the TP half and
   the final exit at the open if the strategy's fill was at the open, else at the close), pays the same costs,
   receives dividends and is closed at its last close if it dies first. It occupies a slot exactly when the
   strategy position does, sized from the random book's own equity.
11. Benchmarks carry no trading costs ("buy-and-hold"; the pre-registration names costs only for the crypto
   benchmark). A member enters the equal-weight benchmark on a session if it is a member that day and has a
   close on the previous session of the calendar; a missing row carries the previous close (return 0, the move
   lands on the next row). The ETF benchmark holds each ETF from its first raw_pit date plus 60 sessions of history
   (the Data section's ETF universe): it earns its first return on its 61st session, the first whose open the
   strategy could buy (min_history=0 holds it from the session after its first close).
12. HS2's portfolio uses the same 20 slots of equity / 20 ("the same on the 14 ETFs"); n_slots is a parameter.
13. The 100 further seeds are 20261019 .. 20261118 (SEEDS_FURTHER). Ties in the atr_dist ranking are broken by the
   symbol string (dead names carry their -YYYYMM file suffix).
14. portfolio() takes the stock_trades result, not only its trades: a name the book skips (no free slot) can take
   a later signal that the chained trade-level book ignores because its own position would still be open, so the
   book draws from every entered candidate, each simulated as if the name were flat at its signal close (which
   is exact: a position's path depends only on its own signal and the prices). This departs from
   bb_engine_spec's portfolio(trades, ...) signature: portfolio, portfolio_seeds and random_entry_book raise a
   TypeError naming stock_trades() when given anything else.
15. Implied dividends. D_d < 0 (the total-return / chart ratio q falls) is never a cash dividend: it is a share
   adjustment that chart_factor missed (an unrecorded stock dividend or split, or a raw / split-adjusted source
   splice), which leaves a fake jump in the "split-adjusted" chart prices. Such a day is folded into the earlier
   chart OHLC (multiplied by q_{d-1} / q_d) instead of being credited as a negative dividend, so the chart series
   is split-adjusted as the pre-registration requires; the total-return P&L is unchanged (128 member days,
   log['share_adj_folded']). Positive implied dividends are kept as cash; 130 member days exceed 10% of the prior
   close (log['div_days_gt10pct']): mostly real special distributions and spin-offs (e.g. AABA 2019, BKR 2017),
   possibly some unrecorded splits; a data caveat, P&L total-return-correct either way.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
NY = ZoneInfo("America/New_York")

SEED = 20261018
SEEDS_FURTHER = tuple(range(SEED + 1, SEED + 101))       # the 100 further seeds of HS1
N_SLOTS = 20
START = "2001-01-01"
END = "2026-10-16"
WINDOWS = {"primary": (START, END), "1996-2000": ("1996-01-01", "2000-12-31")}
HALVES = {"2001-2013": ("2001-01-01", "2013-12-31"), "2014-2026": ("2014-01-01", END)}
ETFS = ["SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "TLT", "IEF", "TIP", "LQD", "HYG", "GLD", "SLV", "VNQ"]
USER = ["TSLA", "COIN", "HOOD", "CRCL", "SPY", "QQQ", "IWM"]
RAW_PIT = set(ETFS) | {"TSLA", "COIN", "HOOD"}
COST_BASE = 0.0003                                        # 1 bp + 2 bp (HANDOFF section 4)
COST_HIGH = 0.0010
HIGH_COST = {"COIN", "HOOD", "CRCL"}
FIN_SPREAD = 0.025                                        # Reg-T borrowing: T-bill + 2.5 points a year
DEAD_DAYS = 7
FOLD_TOL = 1e-9                                           # q_{d-1} / q_d above 1 + this = a negative "dividend"
OHLC = ["open", "high", "low", "close"]

WARMUP, WARMUP_ATH = 60, 365
NEAR_LB, NEAR_K, ATH_K = 60, 0.95, 0.90
ATR_N = 14
ADD1, ADD2, TP_R = 1.02, 1.05, 3.0
W_ON = 0.5                                                # overnight share of a session in the exposure path

OPEN, INTRA, CLOSE = 0, 1, 2
PHASES = ["open", "intraday", "close"]
ST_ENTERED, ST_NO_SESSION, ST_BEFORE, ST_RECHECK, ST_NOT_MEMBER, ST_OPEN_LE_S, ST_BAD_S = range(7)
STATUS = ["entered", "no_session", "before_window", "recheck_fail", "not_member", "open_le_S", "no_stop_level"]
X_STOP, X_MID, X_DEAD, X_END = range(4)
X_NAMES = ["stop", "mid", "dead", "window_end"]
SK_NONE, SK_LEVEL, SK_OPEN, SK_FLAT = range(4)
SK_NAMES = ["", "level", "open", "flat_close"]
K_ENTRY, K_ADD, K_TP, K_EXIT, K_STOP, K_DEAD, K_MARK = range(7)
KIND_NAMES = ["entry", "add", "tp", "exit", "stop", "dead", "mark"]
A_FLAT, A_RANGE, A_OPEN, A_TIME = range(4)
AUDIT_NAMES = ["fill on a flat or close-only bar", "fill outside [low, high]", "open fill not at the open",
               "fill not after the decision that caused it"]

# candidate output columns
I_T, I_ST, I_E, I_X, I_XPH, I_XC, I_SK, I_NTR, I_TP, I_DEF, I_K, I_NP, I_NT, I_ROLL, I_CANC = range(15)
NI = 15
F_S, F_TP, F_PX1, F_RET, F_GROSS, F_FEES, F_DIV, F_XPX = range(8)
NF = 8


@dataclass(frozen=True)
class StockCfg:
    bars: str = "1d"          # "1d" primary | "1w" S20 (weekly signal and exit bars)
    bb_n: int = 20
    bb_k: float = 2.0
    cost_mult: float = 1.0    # 2.0 = the double-cost sensitivity
    lev: float = 1.0          # 2.0 = Reg-T (exploratory): trade-level financing on (lev - 1) / lev of the notional


ROWS = {"primary": StockCfg(), "costs2x": StockCfg(cost_mult=2.0), "lev2": StockCfg(lev=2.0),
        "S20": StockCfg(bars="1w")}


def cost_of(name: str) -> float:
    return COST_HIGH if name.split("-")[0].upper() in HIGH_COST else COST_BASE


def _session_bound(x, end: bool) -> pd.Timestamp:
    """A window bound as a session date (inclusive). As bb_data's convention, a 'YYYY' or 'YYYY-MM' end covers
    that whole year / month; any other value is read as its date (tz-aware values in New York time)."""
    if isinstance(x, str) and end and len(x) in (4, 7) and x.replace("-", "").isdigit():
        p = pd.Period(x, freq="Y" if len(x) == 4 else "M")
        return p.end_time.normalize().as_unit("ns")
    t = pd.Timestamp(x)
    if t.tz is not None:
        t = t.tz_convert(NY).tz_localize(None)
    return t.normalize().as_unit("ns")


def half_of(dates) -> np.ndarray:
    d = pd.DatetimeIndex(pd.to_datetime(dates))
    if d.tz is not None:
        d = d.tz_convert(NY).tz_localize(None)
    y = d.year.to_numpy()
    return np.where((y >= 1996) & (y <= 2000), "1996-2000", np.where((y >= 2001) & (y <= 2013), "2001-2013",
                    np.where(y >= 2014, "2014-2026", "")))


# ============================================================================ data

def _spell_mask(idx: pd.DatetimeIndex, spells) -> np.ndarray:
    m = np.zeros(len(idx), bool)
    for a, b in spells:
        m |= (idx >= a) & (idx <= b)
    return m


def _q_on(qf: dict, sym: str, idx: pd.DatetimeIndex) -> np.ndarray:
    q = qf.get(sym.upper())
    if q is None:
        return np.ones(len(idx))
    q = q[~q.index.duplicated(keep="last")].sort_index()
    q.index = pd.DatetimeIndex(q.index).as_unit("ns")
    return q.reindex(idx).ffill().bfill().fillna(1.0).to_numpy(float)


def _exact_flat(o, h, l, c) -> np.ndarray:
    o, h, l, c = (np.asarray(x, float) for x in (o, h, l, c))
    return (o == h) & (h == l) & (l == c)


def flat_flag(f: pd.DataFrame) -> np.ndarray:
    """The session-level 'flat bar' flag of a frame: its source row is close-only (column close_only) or its bar is
    exactly open = high = low = close. It is data availability (no intraday prices for that session), so it is
    fixed from the source at load time and is treated as known at the session's open (coding choice 2); the
    look-ahead control's perturbation keeps it."""
    co = f["close_only"].to_numpy(bool) if "close_only" in f else np.zeros(len(f), bool)
    return co | _exact_flat(*(f[k].to_numpy(float) for k in OHLC))


def _frame(idx, o, h, l, c, tr, member=None, close_only=None, **attrs) -> pd.DataFrame:
    f = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "tr": tr},
                     index=pd.DatetimeIndex(idx).normalize().as_unit("ns"))
    f["member"] = True if member is None else np.asarray(member, bool)
    f["close_only"] = False if close_only is None else np.asarray(close_only, bool)
    f["flat"] = flat_flag(f)
    f.attrs.update(attrs)
    if "dead" not in f.attrs and len(f):
        f.attrs["dead"] = bool(f.index[-1] < _data_last() - pd.Timedelta(days=DEAD_DAYS))
    return f


@lru_cache(maxsize=1)
def _chart_factor() -> dict:
    from analysis_2026 import ma_bounce as MB
    return MB.chart_factor()


@lru_cache(maxsize=1)
def _data_last() -> pd.Timestamp:
    """The last session of the stock price sources (raw_pit, from which universe_pit_all is built, and
    universe_recent_raw): a name whose file ends more than DEAD_DAYS before it is dead (coding choice 4)."""
    a = pd.read_parquet(DATA / "raw_pit" / "prices.parquet", columns=["date"]).date.max()
    b = pd.read_parquet(DATA / "universe_recent_raw" / "prices.parquet", columns=["date"]).date.max()
    return pd.Timestamp(max(a, b)).normalize().as_unit("ns")


@lru_cache(maxsize=1)
def _close_only_dates() -> dict:
    """Close-only source rows of data/raw_pit (open, high or low missing: screener.data.from_sp500_pit's own test,
    after its date de-duplication and close > 0 filter) -> {TICKER: DatetimeIndex}. universe_pit_all writes such a
    row as open = previous close, high / low = max / min(open, close), so the member file itself cannot tell."""
    p = pd.read_parquet(DATA / "raw_pit" / "prices.parquet", columns=["date", "ticker", "open", "high", "low",
                                                                      "close"])
    p["ticker"] = p.ticker.astype(str).str.upper()
    p = p.sort_values(["ticker", "date"], kind="stable").drop_duplicates(["ticker", "date"], keep="last")
    p = p[p.close > 0]
    co = p[p.open.isna() | p.high.isna() | p.low.isna()]
    return {t: pd.DatetimeIndex(g.date).normalize().as_unit("ns") for t, g in co.groupby("ticker")}


@lru_cache(maxsize=1)
def _members_data() -> dict:
    """Point-in-time S&P 500 members: chart OHLC = universe_pit_all OHLC / chart_factor q; tr = the pit close;
    close_only = the raw_pit row has no open, high or low (flat bar)."""
    from analysis_2026 import ma_bounce as MB
    stocks, members = MB.load_members()
    qf = _chart_factor()
    cod = _close_only_dates()
    spells = {s: [(r.start, r.end) for r in g.itertuples()] for s, g in members.groupby("symbol")}
    out = {}
    for s in sorted(stocks):
        if s not in spells:
            continue                                           # ETF and other non-member files of the folder
        d = stocks[s]
        d = d[~d.index.duplicated(keep="last")].sort_index()
        idx = pd.DatetimeIndex(d.index).normalize().as_unit("ns")
        q = _q_on(qf, s, idx)
        px = d[OHLC].to_numpy(float) / q[:, None]
        co = idx.isin(cod[s.upper()]) if s.upper() in cod else None
        out[s] = _frame(idx, px[:, 0], px[:, 1], px[:, 2], px[:, 3], d.close.to_numpy(float),
                        _spell_mask(idx, spells[s]), co, spells=spells[s], cost=COST_BASE, source="universe_pit_all")
    return out


def _raw_pit(sym: str) -> pd.DataFrame:
    """raw_pit OHLC (regime_switch._yahoo_raw, which drops close-only rows; none exist for the ETFs, TSLA, COIN or
    HOOD: attrs['close_only_dropped'] counts them and the selftest asserts 0)."""
    from analysis_2026 import regime_switch as RS
    d = RS._yahoo_raw(sym)
    idx = pd.DatetimeIndex(d.index).normalize().as_unit("ns")
    q = _q_on(_chart_factor(), sym, idx)
    c = d.close.to_numpy(float)
    return _frame(idx, d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float), c, c * q,
                  cost=cost_of(sym), source="raw_pit",
                  close_only_dropped=int(len(_close_only_dates().get(sym.upper(), []))))


def _recent_raw(sym: str) -> pd.DataFrame:
    p = pd.read_parquet(DATA / "universe_recent_raw" / "prices.parquet", filters=[("ticker", "==", sym)])
    p = p.sort_values("date").drop_duplicates("date", keep="last")
    p = p[p.close > 0]
    has = p[["open", "high", "low"]].notna().all(axis=1)
    n_co = int((~has).sum())
    p = p[has]
    return _frame(pd.DatetimeIndex(p.date), p.open.to_numpy(float), p.high.to_numpy(float), p.low.to_numpy(float),
                  p.close.to_numpy(float), p.adj.to_numpy(float), cost=cost_of(sym), source="universe_recent_raw",
                  close_only_dropped=n_co)


def ticker_data(sym: str) -> pd.DataFrame:
    """One ticker from its pre-registered price source: CRCL universe_recent_raw; ETFs, TSLA, COIN, HOOD raw_pit;
    otherwise the members' universe_pit_all file (chart prices, membership mask)."""
    s = sym.upper()
    if s == "CRCL":
        return _recent_raw("CRCL")
    if s in RAW_PIT:
        return _raw_pit(s)
    return _members_data()[sym]


def universe_data(which) -> dict:
    if isinstance(which, str) and which == "members":
        return _members_data()
    if isinstance(which, str) and which == "etfs":
        return {s: ticker_data(s) for s in ETFS}
    if isinstance(which, str) and which == "user":
        return {s: ticker_data(s) for s in USER}
    if isinstance(which, str):
        return {which: ticker_data(which)}
    return {s: ticker_data(s) for s in which}


def _normalise(name: str, f: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Columns open/high/low/close (+ tr, div, member, close_only, flat). Missing tr -> close (no dividends);
    missing close_only -> False; missing flat -> flat_flag (close_only or exactly O = H = L = C; the loaders and
    the look-ahead perturbation set it from the unperturbed source). Missing div -> D_d = C_{d-1} (1 - q_{d-1} /
    q_d) with q = tr / close, except that a negative D (q falling: never a cash dividend, an unrecorded share
    adjustment of chart_factor) is folded into the earlier chart OHLC instead (coding choice 15; attrs
    n_share_adj_folded, n_div_gt10pct). Returns (frame, number of repaired OHLC rows)."""
    g = f.copy()
    g.index = pd.DatetimeIndex(g.index)
    if g.index.tz is not None:
        g.index = g.index.tz_convert(NY).tz_localize(None)
    g.index = g.index.normalize().as_unit("ns")
    g = g[~g.index.duplicated(keep="last")].sort_index()
    g = g[np.isfinite(g[OHLC].to_numpy(float)).all(axis=1) & (g.close > 0)]
    o, h, l, c = (g[k].to_numpy(float) for k in OHLC)
    hi = np.maximum.reduce([o, h, l, c]); lo = np.minimum.reduce([o, h, l, c])
    rep = int(((hi > h) | (lo < l)).sum())
    g["high"], g["low"] = hi, lo
    g["close_only"] = g["close_only"].to_numpy(bool) if "close_only" in g else np.zeros(len(g), bool)
    g["flat"] = (g["flat"].to_numpy(bool) | g["close_only"].to_numpy(bool)) if "flat" in g else flat_flag(g)
    if "tr" not in g:
        g["tr"] = c
    n_fold = n_big = 0
    if "div" not in g:
        tr = g.tr.to_numpy(float)
        q = tr / c
        n = len(g)
        fold = np.ones(n)
        if n > 1:
            r = q[:-1] / q[1:]                                 # q_{d-1} / q_d for d = 1..n-1
            neg = np.isfinite(r) & (r > 1.0 + FOLD_TOL)
            fold[1:][neg] = r[neg]
            n_fold = int(neg.sum())
        if n_fold:
            S = np.r_[np.cumprod(fold[::-1])[::-1][1:], 1.0]  # product of the fold factors of later days
            for k in OHLC:
                g[k] = g[k].to_numpy(float) * S
            c = g.close.to_numpy(float)
            q = tr / c
        dv = np.zeros(n)
        if n > 1:
            dv[1:] = c[:-1] * (1.0 - q[:-1] / q[1:])
            dv[1:][fold[1:] > 1.0] = 0.0
            with np.errstate(invalid="ignore", divide="ignore"):
                n_big = int(np.nansum(dv[1:] / c[:-1] > 0.10))
        g["div"] = np.where(np.isfinite(dv), dv, 0.0)
    if "member" not in g:
        g["member"] = True
    g.attrs = dict(f.attrs)
    g.attrs.setdefault("cost", cost_of(name))
    g.attrs["n_share_adj_folded"] = n_fold
    g.attrs["n_div_gt10pct"] = n_big
    return g, rep


def calendar(data: dict) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex([])
    for f in data.values():
        idx = idx.union(pd.DatetimeIndex(f.index).normalize())
    return idx.as_unit("ns")


def _tbill_session(idx) -> np.ndarray:
    from analysis_2026.bb_data import tbill_session
    return tbill_session(pd.DatetimeIndex(idx))


def session_returns(data: dict) -> dict:
    """Total-return close-to-close arithmetic return per session, indexed by session date (first row NaN)."""
    out = {}
    for s, f in data.items():
        tr = pd.Series(np.asarray(f["tr"], float), index=pd.DatetimeIndex(f.index).normalize().as_unit("ns"))
        out[s] = tr.pct_change()
    return out


# ============================================================================ indicators

@njit(cache=True)
def _sma_ub(c, n, k):
    m = len(c)
    sma = np.full(m, np.nan)
    ub = np.full(m, np.nan)
    for i in range(n - 1, m):
        s = 0.0
        for j in range(i - n + 1, i + 1):
            s += c[j]
        mu = s / n
        v = 0.0
        for j in range(i - n + 1, i + 1):
            v += (c[j] - mu) * (c[j] - mu)
        sma[i] = mu
        ub[i] = mu + k * np.sqrt(v / n)
    return sma, ub


@njit(cache=True)
def _atr(h, l, c, p):
    """Wilder ATR as moneyline_ref.atr: TR[0] = high - low, seeded with the mean of the first p TRs."""
    n = len(c)
    out = np.full(n, np.nan)
    if n < p:
        return out
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], max(abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    s = 0.0
    for i in range(p):
        s += tr[i]
    out[p - 1] = s / p
    a = 1.0 / p
    for i in range(p, n):
        out[i] = a * tr[i] + (1.0 - a) * out[i - 1]
    return out


@njit(cache=True)
def _rollmax(x, w):
    n = len(x)
    out = np.empty(n)
    for i in range(n):
        j0 = max(0, i - w + 1)
        m = x[j0]
        for j in range(j0 + 1, i + 1):
            if x[j] > m:
                m = x[j]
        out[i] = m
    return out


def _signals(o, h, l, c, flat, dates, cfg: StockCfg) -> dict:
    """Decision arrays on the name's daily sessions: sig (fresh signal at that close), lvl_ok (signal level for
    the re-check), exit_sig, is_dec, dec_last (latest completed decision bar at each session's open), S_at,
    rank (close - UB) / ATR14, ath_only."""
    n = len(c)
    cnt = np.arange(1, n + 1)
    hh = _rollmax(h, NEAR_LB)
    ath = np.maximum.accumulate(h)
    near60 = (cnt >= WARMUP) & (c >= NEAR_K * hh)
    nearath = (cnt >= WARMUP_ATH) & (c >= ATH_K * ath)
    if cfg.bars == "1d":
        sma, ub = _sma_ub(c, cfg.bb_n, cfg.bb_k)
        atr = _atr(h, l, c, ATR_N)
        with np.errstate(invalid="ignore"):
            lvl = (cnt >= WARMUP) & np.isfinite(ub) & (c > ub) & (near60 | nearath)
            prev_ok = np.r_[False, np.isfinite(ub[:-1]) & (c[:-1] <= ub[:-1])]
            exit_sig = (~flat) & np.isfinite(sma) & (c < sma)
            rank = (c - ub) / atr
        sig = lvl & prev_ok & ~flat
        is_dec = np.ones(n, bool)
        dec_last = np.arange(n) - 1
        S_at = sma - atr
    elif cfg.bars == "1w":
        d = pd.DatetimeIndex(dates)
        wk = (d - pd.to_timedelta(d.weekday, unit="D")).normalize().asi8
        starts = np.r_[0, np.flatnonzero(np.diff(wk) != 0) + 1]
        ends = np.r_[starts[1:] - 1, n - 1]
        wo, wc = o[starts], c[ends]
        wh = np.maximum.reduceat(h, starts)
        wl = np.minimum.reduceat(l, starts)
        wflat = np.logical_and.reduceat(np.asarray(flat, bool), starts)   # every session of the week is flat
        sma_w, ub_w = _sma_ub(wc, cfg.bb_n, cfg.bb_k)
        atr_w = _atr(wh, wl, wc, ATR_N)
        with np.errstate(invalid="ignore"):
            lvl_w = (cnt[ends] >= WARMUP) & np.isfinite(ub_w) & (wc > ub_w) & (near60[ends] | nearath[ends])
            prev_w = np.r_[False, np.isfinite(ub_w[:-1]) & (wc[:-1] <= ub_w[:-1])]
            exit_w = (~wflat) & np.isfinite(sma_w) & (wc < sma_w)
            rank_w = (wc - ub_w) / atr_w
        lvl = np.zeros(n, bool); sig = np.zeros(n, bool); exit_sig = np.zeros(n, bool)
        is_dec = np.zeros(n, bool); S_at = np.full(n, np.nan); rank = np.full(n, np.nan)
        lvl[ends] = lvl_w
        sig[ends] = lvl_w & prev_w & ~wflat
        exit_sig[ends] = exit_w
        is_dec[ends] = True
        S_at[ends] = sma_w - atr_w
        rank[ends] = rank_w
        pos = np.searchsorted(ends, np.arange(n), "left") - 1
        dec_last = np.where(pos >= 0, ends[np.maximum(pos, 0)], -1)
    else:
        raise ValueError(f"bars must be '1d' or '1w', not {cfg.bars!r}")
    return {"sig": sig, "lvl_ok": lvl, "exit_sig": exit_sig, "is_dec": is_dec,
            "dec_last": dec_last.astype(np.int64), "S_at": np.asarray(S_at, float), "rank": np.asarray(rank, float),
            "ath_only": nearath & ~near60}


# ============================================================================ per-name simulation (numba)

@njit(cache=True)
def _sim(o, h, l, c, flat, member, div, wd, lvl_ok, exit_sig, is_dec, dec_last, S_at, cand_t,
         cost, dead, start_i, end_i, rec, p_off, t_off,
         out_i, out_f, p_d, p_dcash, p_value, p_res, p_expo, p_sh,
         t_d, t_px, t_not, t_kind, t_ph, audit, n_audit):
    """Simulate one position per candidate signal (each as if the name were flat at its signal close).
    rec=False fills out_i / out_f (incl. the path and tranche row counts); rec=True also writes the path rows
    at p_off[ci] and the tranche rows at t_off[ci]."""
    n = len(o)
    third = 1.0 / 3.0
    for ci in range(len(cand_t)):
        t = cand_t[ci]
        for j in range(NI_):
            out_i[ci, j] = -1 if (j == 2 or j == 3 or j == 4 or j == 10) else 0
        out_i[ci, 0] = t
        for j in range(NF_):
            out_f[ci, j] = np.nan
        # ---------------------------------------------------------------- entry session
        e = t + 1
        rolled = False
        deferred = False
        while e <= end_i:
            if flat[e]:
                e += 1
                rolled = True
                continue
            if wd[e] == 4:
                e += 1
                rolled = True
                deferred = True
                continue
            break
        out_i[ci, 9] = 1 if deferred else 0
        out_i[ci, 13] = 1 if rolled else 0
        if e > end_i:
            out_i[ci, 1] = 1                   # no_session
            continue
        out_i[ci, 2] = e
        if e < start_i:
            out_i[ci, 1] = 2                   # before_window
            continue
        k = dec_last[e]
        out_i[ci, 10] = k
        if rolled and not lvl_ok[k]:
            out_i[ci, 1] = 3                   # recheck_fail
            continue
        if not member[e]:
            out_i[ci, 1] = 4                   # not_member
            continue
        S = S_at[k]
        if not np.isfinite(S):
            out_i[ci, 1] = 6
            continue
        out_f[ci, 0] = S
        if o[e] <= S:
            out_i[ci, 1] = 5                   # open_le_S
            continue
        out_i[ci, 1] = 0                       # entered
        # ---------------------------------------------------------------- position
        px1 = o[e]
        TP = px1 + TP_R_ * (px1 - S)
        out_f[ci, 1] = TP
        out_f[ci, 2] = px1
        sh = third / px1
        cash = -third * (1.0 + cost)
        fees = third * cost
        divs = 0.0
        ntr = 1
        bnot = third
        bsh = sh
        a1 = False
        a2 = False
        p1 = False
        p2 = False
        tp = False
        xpend = False
        trig1 = -1
        trig2 = -1
        xday = -1
        ncanc = 0
        nt = 0
        npth = 0
        xph = -1
        xcode = -1
        sk = 0
        xpx = np.nan
        exited = False
        # entry tranche
        if rec:
            r = t_off[ci] + nt
            t_d[r] = e; t_px[r] = px1; t_not[r] = third; t_kind[r] = 0; t_ph[r] = 0
        nt += 1
        if flat[e] or not (l[e] <= px1 <= h[e]) or e <= t:
            if n_audit[0] < audit.shape[0]:
                audit[n_audit[0], 0] = ci; audit[n_audit[0], 1] = e; audit[n_audit[0], 2] = 1 if not flat[e] else 0
            n_audit[0] += 1
        d = e
        while True:
            cash0 = cash if d > e else 0.0                     # the entry-day row carries the entry's cash
            sh_prev = sh if d > e else 0.0
            cprev = c[d - 1] if d > 0 else o[d]
            if d > e:
                if sh > 0.0 and div[d] != 0.0:
                    cash += sh * div[d]
                    divs += sh * div[d]
                if not flat[d]:
                    od = o[d]
                    if od <= S:                                # gap through the stop: fill at the open
                        cash += sh * od * (1.0 - cost)
                        fees += sh * od * cost
                        if rec:
                            r = t_off[ci] + nt
                            t_d[r] = d; t_px[r] = od; t_not[r] = -sh * od; t_kind[r] = 4; t_ph[r] = 0
                        nt += 1
                        sh = 0.0
                        exited = True
                        xph = 0; xcode = 0; sk = 2; xpx = od
                    else:
                        if (not tp) and od >= TP:              # gap above the TP: the resting limit sells half
                            # at the open, which precedes the rest of the bar; the stop then applies to the
                            # remaining half below (coding choice 3; decided with the open alone)
                            q = 0.5 * sh
                            cash += q * od * (1.0 - cost)
                            fees += q * od * cost
                            if rec:
                                r = t_off[ci] + nt
                                t_d[r] = d; t_px[r] = od; t_not[r] = -q * od; t_kind[r] = 2; t_ph[r] = 0
                            nt += 1
                            sh -= q
                            tp = True
                            if p1 or p2:
                                ncanc += int(p1) + int(p2)
                            p1 = False
                            p2 = False
                        if xpend:                              # trend exit at the open
                            cash += sh * od * (1.0 - cost)
                            fees += sh * od * cost
                            if rec:
                                r = t_off[ci] + nt
                                t_d[r] = d; t_px[r] = od; t_not[r] = -sh * od; t_kind[r] = 3; t_ph[r] = 0
                            nt += 1
                            if d <= xday:
                                if n_audit[0] < audit.shape[0]:
                                    audit[n_audit[0], 0] = ci; audit[n_audit[0], 1] = d; audit[n_audit[0], 2] = 3
                                n_audit[0] += 1
                            sh = 0.0
                            exited = True
                            xph = 0; xcode = 1; xpx = od
                        elif not tp:
                            for which in range(2):
                                pend = p1 if which == 0 else p2
                                if not pend:
                                    continue
                                trig = trig1 if which == 0 else trig2
                                if od >= bnot / bsh:
                                    s_ = third / od
                                    sh += s_
                                    bsh += s_
                                    bnot += third
                                    cash -= third * (1.0 + cost)
                                    fees += third * cost
                                    ntr += 1
                                    if rec:
                                        r = t_off[ci] + nt
                                        t_d[r] = d; t_px[r] = od; t_not[r] = third; t_kind[r] = 1; t_ph[r] = 0
                                    nt += 1
                                    if d <= trig:
                                        if n_audit[0] < audit.shape[0]:
                                            audit[n_audit[0], 0] = ci; audit[n_audit[0], 1] = d
                                            audit[n_audit[0], 2] = 3
                                        n_audit[0] += 1
                                    if which == 0:
                                        a1 = True
                                    else:
                                        a2 = True
                                else:
                                    ncanc += 1
                                if which == 0:
                                    p1 = False
                                else:
                                    p2 = False
            sh_open = sh
            # ---------------------------------------------------------------- intraday
            if not exited and not flat[d]:
                if l[d] <= S:                                  # stop first when the bar touches both
                    cash += sh * S * (1.0 - cost)
                    fees += sh * S * cost
                    if rec:
                        r = t_off[ci] + nt
                        t_d[r] = d; t_px[r] = S; t_not[r] = -sh * S; t_kind[r] = 4; t_ph[r] = 1
                    nt += 1
                    sh = 0.0
                    exited = True
                    xph = 1; xcode = 0; sk = 1; xpx = S
                elif (not tp) and h[d] >= TP:
                    q = 0.5 * sh
                    cash += q * TP * (1.0 - cost)
                    fees += q * TP * cost
                    if rec:
                        r = t_off[ci] + nt
                        t_d[r] = d; t_px[r] = TP; t_not[r] = -q * TP; t_kind[r] = 2; t_ph[r] = 1
                    nt += 1
                    sh -= q
                    tp = True
                    if p1 or p2:
                        ncanc += int(p1) + int(p2)
                    p1 = False
                    p2 = False
            sh_mid = sh if not exited else (0.0 if xph != 2 else sh_open)
            # ---------------------------------------------------------------- close
            if not exited:
                if flat[d] and c[d] <= S:                      # flat bar: the stop only, at that close
                    cash += sh * c[d] * (1.0 - cost)
                    fees += sh * c[d] * cost
                    if rec:
                        r = t_off[ci] + nt
                        t_d[r] = d; t_px[r] = c[d]; t_not[r] = -sh * c[d]; t_kind[r] = 4; t_ph[r] = 2
                    nt += 1
                    sh_mid = sh
                    sh = 0.0
                    exited = True
                    xph = 2; xcode = 0; sk = 3; xpx = c[d]
                elif d == end_i:
                    sh_mid = sh
                    if dead and d == n - 1:                    # prices end: closed at the last close
                        cash += sh * c[d] * (1.0 - cost)
                        fees += sh * c[d] * cost
                        if rec:
                            r = t_off[ci] + nt
                            t_d[r] = d; t_px[r] = c[d]; t_not[r] = -sh * c[d]; t_kind[r] = 5; t_ph[r] = 2
                        nt += 1
                        sh = 0.0
                        xcode = 2
                    else:                                      # window end: marked, not closed
                        if rec:
                            r = t_off[ci] + nt
                            t_d[r] = d; t_px[r] = c[d]; t_not[r] = -sh * c[d]; t_kind[r] = 6; t_ph[r] = 2
                        nt += 1
                        xcode = 3
                    exited = True
                    xph = 2; xpx = c[d]
                else:
                    # exit_sig is already False on a flat decision bar (a flat day, or a flat week for S20)
                    if is_dec[d] and exit_sig[d] and not xpend:
                        xpend = True
                        xday = d
                        if p1 or p2:
                            ncanc += int(p1) + int(p2)
                        p1 = False
                        p2 = False
                    if (not flat[d]) and (not tp) and (not xpend):
                        if (not a1) and (not p1) and c[d] >= ADD1_ * px1:
                            p1 = True
                            trig1 = d
                        if (not a2) and (not p2) and c[d] >= ADD2_ * px1:
                            p2 = True
                            trig2 = d
            # ---------------------------------------------------------------- path row
            if rec:
                r = p_off[ci] + npth
                p_d[r] = d
                p_dcash[r] = cash - cash0
                p_sh[r] = sh
                p_value[r] = sh * c[d]
                if (not exited) or xcode == 3:
                    p_res[r] = 0.0 if tp else third * ((0 if a1 else 1) + (0 if a2 else 1))
                else:
                    p_res[r] = 0.0
                p_expo[r] = W_ON_ * sh_prev * cprev + 0.5 * (1.0 - W_ON_) * (sh_open + sh_mid) * o[d]
            npth += 1
            if exited:
                break
            d += 1
        ret = cash + (sh * c[d] if xcode == 3 else 0.0)
        out_i[ci, 3] = d
        out_i[ci, 4] = xph
        out_i[ci, 5] = xcode
        out_i[ci, 6] = sk
        out_i[ci, 7] = ntr
        out_i[ci, 8] = 1 if tp else 0
        out_i[ci, 11] = npth
        out_i[ci, 12] = nt
        out_i[ci, 14] = ncanc
        out_f[ci, 3] = ret
        out_f[ci, 4] = ret + fees
        out_f[ci, 5] = fees
        out_f[ci, 6] = divs
        out_f[ci, 7] = xpx


# numba sees these module constants as compile-time globals
NI_, NF_, TP_R_, ADD1_, ADD2_, W_ON_ = NI, NF, TP_R, ADD1, ADD2, W_ON


@njit(cache=True)
def _audit_tranches(t_d, t_px, t_kind, t_ph, t_cand, o, h, l, flat, base, audit, n_audit):
    """Fill audit of recorded tranches (mark rows excluded): within [low, high] of their bar, open fills at the
    open, no fill on a flat bar except the flat-bar stop and the dead-name close."""
    tol = 1e-9
    for r in range(len(t_d)):
        k = t_kind[r]
        if k == 6:
            continue
        d = t_d[r]
        code = -1
        if flat[d] and not ((k == 4 and t_ph[r] == 2) or k == 5):
            code = 0
        elif t_px[r] < l[d] * (1 - tol) or t_px[r] > h[d] * (1 + tol):
            code = 1
        elif t_ph[r] == 0 and t_px[r] != o[d]:
            code = 2
        if code >= 0:
            if n_audit[0] < audit.shape[0]:
                audit[n_audit[0], 0] = base + t_cand[r]; audit[n_audit[0], 1] = d; audit[n_audit[0], 2] = code
            n_audit[0] += 1


def _simulate_name(f: pd.DataFrame, cfg: StockCfg, start, end, dead: bool):
    """Prepare one name and run the numba simulation twice (counts, then records)."""
    dates = pd.DatetimeIndex(f.index)
    o, h, l, c = (f[k].to_numpy(float) for k in OHLC)
    flat = f["flat"].to_numpy(bool) if "flat" in f else flat_flag(f)   # data availability, fixed at load
    member = f["member"].to_numpy(bool)
    div = f["div"].to_numpy(float)
    wd = dates.weekday.to_numpy().astype(np.int64)
    sg = _signals(o, h, l, c, flat, dates, cfg)
    start_i = int(np.searchsorted(dates.asi8, _session_bound(start, False).value, "left"))
    end_i = int(np.searchsorted(dates.asi8, _session_bound(end, True).value, "right")) - 1
    cost = float(f.attrs.get("cost", COST_BASE)) * cfg.cost_mult
    cand_t = np.flatnonzero(sg["sig"]).astype(np.int64)
    cand_t = cand_t[cand_t <= end_i]
    nc = len(cand_t)
    out_i = np.zeros((nc, NI), np.int64)
    out_f = np.zeros((nc, NF))
    z0f, z0i, z0b = np.zeros(0), np.zeros(0, np.int64), np.zeros(0, np.int8)
    audit = np.zeros((50, 3), np.int64)
    na = np.zeros(1, np.int64)
    args = (o, h, l, c, flat, member, div, wd, sg["lvl_ok"], sg["exit_sig"], sg["is_dec"], sg["dec_last"],
            sg["S_at"], cand_t, cost, dead, start_i, end_i)
    _sim(*args, False, z0i, z0i, out_i, out_f, z0i, z0f, z0f, z0f, z0f, z0f, z0i, z0f, z0f, z0b, z0b, audit, na)
    ent = out_i[:, I_ST] == ST_ENTERED
    npth = np.where(ent, out_i[:, I_NP], 0)
    ntr = np.where(ent, out_i[:, I_NT], 0)
    p_off = np.r_[0, np.cumsum(npth)[:-1]].astype(np.int64) if nc else z0i
    t_off = np.r_[0, np.cumsum(ntr)[:-1]].astype(np.int64) if nc else z0i
    P, T = int(npth.sum()), int(ntr.sum())
    p_d = np.zeros(P, np.int64); p_dcash = np.zeros(P); p_value = np.zeros(P); p_res = np.zeros(P)
    p_expo = np.zeros(P); p_sh = np.zeros(P)
    t_d = np.zeros(T, np.int64); t_px = np.zeros(T); t_not = np.zeros(T)
    t_kind = np.zeros(T, np.int8); t_ph = np.zeros(T, np.int8)
    audit[:] = 0
    na[0] = 0
    _sim(*args, True, p_off, t_off, out_i, out_f, p_d, p_dcash, p_value, p_res, p_expo, p_sh,
         t_d, t_px, t_not, t_kind, t_ph, audit, na)
    t_cand = np.repeat(np.arange(nc), ntr).astype(np.int64)
    _audit_tranches(t_d, t_px, t_kind, t_ph, t_cand, o, h, l, flat, 0, audit, na)
    return {"dates": dates, "o": o, "h": h, "l": l, "c": c, "flat": flat,
            "close_only": f["close_only"].to_numpy(bool) if "close_only" in f else np.zeros(len(f), bool),
            "member": member, "div": div,
            "sg": sg, "cand_t": cand_t, "out_i": out_i, "out_f": out_f, "p_off": p_off, "t_off": t_off,
            "p": (p_d, p_dcash, p_value, p_res, p_expo, p_sh), "t": (t_d, t_px, t_not, t_kind, t_ph, t_cand),
            "audit": audit[:min(int(na[0]), len(audit))].copy(), "n_audit": int(na[0]), "start_i": start_i,
            "end_i": end_i, "cost": cost, "dead": dead}


# ============================================================================ trades

def _utc(dates: pd.DatetimeIndex, phase: np.ndarray) -> pd.DatetimeIndex:
    """Session date + 09:30 New York (open fills) or 16:00 New York (intraday / close fills), as UTC."""
    d = pd.DatetimeIndex(dates)
    off = np.where(np.asarray(phase) == OPEN, 9 * 60 + 30, 16 * 60).astype("timedelta64[m]")
    loc = pd.DatetimeIndex(d.values + off)
    return loc.tz_localize(NY).tz_convert("UTC")


def stock_trades(ticker_or_universe, cfg_stock: StockCfg = StockCfg(), start=START, end=END, ohlc=None) -> dict:
    """Every signal of every name (each name its own slot, no position cap) in the window [start, end] (dates,
    inclusive; a trade belongs to the window of its entry). ohlc: a DataFrame (one name, named by
    ticker_or_universe) or {name: DataFrame} with open/high/low/close (+ tr total-return close, div cash dividend
    per share on its ex-date, member bool); attrs may carry cost, dead, spells. Without ohlc the data come from
    universe_data(ticker_or_universe)."""
    t0 = time.time()
    cfg = cfg_stock
    if ohlc is None:
        raw = universe_data(ticker_or_universe)
    elif isinstance(ohlc, pd.DataFrame):
        raw = {str(ticker_or_universe): ohlc}
    else:
        raw = dict(ohlc)
    names = sorted(raw)
    data, rep, n_fold, n_big = {}, 0, 0, 0
    for s in names:
        g, r_ = _normalise(s, raw[s])
        if len(g):
            data[s] = g
            rep += r_
            n_fold += g.attrs.get("n_share_adj_folded", 0)
            n_big += g.attrs.get("n_div_gt10pct", 0)
    names = sorted(data)
    cal = calendar(data)
    start_ts, end_ts = _session_bound(start, False), _session_bound(end, True)
    # dead: the loaders set attrs['dead'] against the sources' last session (_data_last); injected frames without
    # it are judged against the last date of the names in this call
    last_all = max(f.index[-1] for f in data.values()) if data else pd.Timestamp(END)
    rows_c, rows_p, rows_t, audits = [], [], [], []
    arrs = {}
    log = {"names": len(names), "ohlc_repaired": rep, "share_adj_folded": n_fold, "div_days_gt10pct": n_big,
           "close_only_rows": int(sum(f.close_only.sum() for f in data.values())),
           "flat_rows": int(sum(f.flat.sum() for f in data.values())), "audit_violations": 0}
    cbase = 0
    for ni, s in enumerate(names):
        f = data[s]
        dead = bool(f.attrs.get("dead", f.index[-1] < last_all - pd.Timedelta(days=DEAD_DAYS)))
        R = _simulate_name(f, cfg, start_ts, end_ts, dead)
        gidx = cal.get_indexer(R["dates"]).astype(np.int64)
        arrs[s] = {"gidx": gidx, "o": R["o"], "h": R["h"], "l": R["l"], "c": R["c"], "flat": R["flat"],
                   "close_only": R["close_only"], "member": R["member"], "div": R["div"], "cost": R["cost"],
                   "dead": dead, "end_i": R["end_i"]}
        oi, of = R["out_i"], R["out_f"]
        nc = len(oi)
        if nc == 0:
            continue
        dates = R["dates"]
        e_ok = oi[:, I_E] >= 0
        k_ok = oi[:, I_K] >= 0
        cd = pd.DataFrame({
            "cid": cbase + np.arange(nc), "sym": s, "name_id": ni, "t": oi[:, I_T], "status": oi[:, I_ST],
            "e": oi[:, I_E], "x": oi[:, I_X], "xph": oi[:, I_XPH], "xcode": oi[:, I_XC], "stop_kind": oi[:, I_SK],
            "n_tranches": oi[:, I_NTR], "tp_hit": oi[:, I_TP].astype(bool), "deferred": oi[:, I_DEF].astype(bool),
            "rolled": oi[:, I_ROLL].astype(bool), "k": oi[:, I_K], "n_path": oi[:, I_NP], "n_tr": oi[:, I_NT],
            "adds_cancelled": oi[:, I_CANC],
            "S": of[:, F_S], "TP": of[:, F_TP], "entry1_px": of[:, F_PX1], "ret": of[:, F_RET],
            "ret_gross": of[:, F_GROSS], "fees": of[:, F_FEES], "divs": of[:, F_DIV], "exit_px": of[:, F_XPX],
            "signal_day": dates[oi[:, I_T]],
            "rank_key": np.where(k_ok, R["sg"]["rank"][np.maximum(oi[:, I_K], 0)], R["sg"]["rank"][oi[:, I_T]]),
            "atH_only": R["sg"]["ath_only"][oi[:, I_T]],
            "g_sig": gidx[oi[:, I_T]], "g_e": np.where(e_ok, gidx[np.maximum(oi[:, I_E], 0)], -1),
        })
        ent = cd.status.to_numpy() == ST_ENTERED
        cd["g_x"] = np.where(ent, gidx[np.maximum(oi[:, I_X], 0)], -1)
        cd["member"] = np.where(e_ok, R["member"][np.maximum(oi[:, I_E], 0)], False)
        rows_c.append(cd)
        p_d, p_dcash, p_value, p_res, p_expo, p_sh = R["p"]
        npth = np.where(ent, oi[:, I_NP], 0)
        rows_p.append(pd.DataFrame({"cid": np.repeat(cd.cid.to_numpy(), npth), "d": p_d, "g": gidx[p_d],
                                    "dcash": p_dcash, "value": p_value, "res": p_res, "expo": p_expo,
                                    "sh": p_sh}))
        t_d, t_px, t_not, t_kind, t_ph, t_cand = R["t"]
        rows_t.append(pd.DataFrame({"cid": cbase + t_cand, "d": t_d, "g": gidx[t_d], "px": t_px, "notional": t_not,
                                    "kind": t_kind, "phase": t_ph, "date": dates[t_d]}))
        if R["n_audit"]:
            log["audit_violations"] += R["n_audit"]
            for ci, d, code in R["audit"]:
                audits.append({"sym": s, "date": dates[d], "signal_day": dates[oi[ci, I_T]], "code": int(code),
                               "what": AUDIT_NAMES[int(code)], "low": R["l"][d], "high": R["h"][d]})
        cbase += nc
    C = pd.concat(rows_c, ignore_index=True) if rows_c else _empty_cand()
    Pth = pd.concat(rows_p, ignore_index=True) if rows_p else _empty_frame(
        {"cid": np.int64, "d": np.int64, "g": np.int64, "dcash": float, "value": float, "res": float,
         "expo": float, "sh": float})
    Tr = pd.concat(rows_t, ignore_index=True) if rows_t else _empty_frame(
        {"cid": np.int64, "d": np.int64, "g": np.int64, "px": float, "notional": float, "kind": np.int8,
         "phase": np.int8, "date": "datetime64[ns]"})
    # window membership of a signal: its (would-be) entry session, else its signal day
    in_win = (C.status != ST_BEFORE) & (((C.e >= 0) & (C.g_e >= 0)) | (C.e < 0))
    sd = pd.DatetimeIndex(C.signal_day)
    in_win &= ~((C.e < 0) & ((sd < start_ts) | (sd > end_ts)))
    C = C[in_win.to_numpy()].reset_index(drop=True)
    # ---------------------------------------------------------------- chain: one position per name at a time
    C = C.sort_values(["name_id", "t"], kind="stable").reset_index(drop=True)
    chain = np.full(len(C), "", dtype=object)
    kept = np.zeros(len(C), bool)
    last_x = {}
    for i, (nid, t, st, x) in enumerate(zip(C.name_id.to_numpy(), C.t.to_numpy(), C.status.to_numpy(),
                                            C.x.to_numpy())):
        if last_x.get(nid, -1) > t:
            chain[i] = "in_position"
            continue
        chain[i] = STATUS[st]
        if st == ST_ENTERED:
            kept[i] = True
            last_x[nid] = x
    C["chain_status"] = chain
    C["kept"] = kept
    ent = (C.status == ST_ENTERED).to_numpy()
    # times
    dates_e = _dates_of(C, cal, "g_e")
    dates_x = _dates_of(C, cal, "g_x")
    C["entry1_date"] = dates_e
    C["exit_date"] = dates_x
    C["entry1_time"] = _utc(pd.DatetimeIndex(dates_e), np.zeros(len(C), int))
    C["exit_time"] = _utc(pd.DatetimeIndex(dates_x), C.xph.to_numpy())
    # financing for lev > 1 (trade-level rows only; the portfolio charges its own borrowed cash)
    fin = np.zeros(len(C))
    if cfg.lev > 1.0 and len(Pth):
        rf = _tbill_session(cal)
        Pth = Pth.sort_values(["cid", "d"], kind="stable").reset_index(drop=True)
        prev_val = Pth.groupby("cid").value.shift(1).fillna(0.0).to_numpy()
        carry = (cfg.lev - 1.0) / cfg.lev * prev_val * (rf[Pth.g.to_numpy()] + FIN_SPREAD / 252.0)
        fs = pd.Series(carry).groupby(Pth.cid.to_numpy()).sum()
        fin = fs.reindex(C.cid).fillna(0.0).to_numpy()
    C["fin"] = fin
    C["ret_1x"] = C.ret
    C["ret"] = C.ret - fin
    C["L_used"] = cfg.lev
    C["side"] = 1
    C["max_frac"] = C.n_tranches / 3.0
    C["open_at_end"] = C.xcode == X_END
    C["liquidated"] = False
    C["hold_days"] = np.where(ent, C.g_x - C.g_e, -1)
    C["hold_h"] = (C.exit_time - C.entry1_time) / pd.Timedelta(hours=1)
    C["exit_reason"] = np.where(ent, np.char.add(np.where(C.tp_hit, "tp+", ""),
                                                 np.array(X_NAMES + [""])[C.xcode.to_numpy()]), "")
    C["stop_fill"] = np.array(SK_NAMES)[C.stop_kind.to_numpy()]
    C["half"] = np.where(ent, half_of(pd.DatetimeIndex(dates_e).fillna(pd.Timestamp("1900-01-01"))), "")
    # ---------------------------------------------------------------- outputs
    trades = C[C.kept].copy()
    trades.insert(0, "pos", np.arange(len(trades)))
    pos_of = pd.Series(trades.pos.to_numpy(), index=trades.cid.to_numpy())
    cols = ["pos", "sym", "member", "signal_day", "entry1_date", "entry1_time", "entry1_px", "S", "TP", "L_used",
            "exit_date", "exit_time", "exit_reason", "stop_fill", "side", "n_tranches", "max_frac", "ret",
            "ret_gross", "ret_1x", "fees", "divs", "fin", "liquidated", "hold_days", "hold_h", "open_at_end",
            "atH_only", "tp_hit", "deferred", "rolled", "adds_cancelled", "rank_key", "half", "cid"]
    trades = trades[cols].reset_index(drop=True)
    Pk = Pth[Pth.cid.isin(trades.cid)].copy()
    Pk["pos"] = pos_of.reindex(Pk.cid).to_numpy()
    Pk["sym"] = C.set_index("cid").sym.reindex(Pk.cid).to_numpy()
    Pk["time"] = cal[Pk.g.to_numpy()]
    Pk = Pk.sort_values(["pos", "d"], kind="stable")
    expo = Pk[["pos", "sym", "time", "expo"]].rename(columns={"expo": "notional"}).reset_index(drop=True)
    cum = Pk.groupby("pos").dcash.cumsum().to_numpy()
    daily_mtm = pd.DataFrame({"pos": Pk.pos.to_numpy(), "sym": Pk.sym.to_numpy(), "date": Pk.time.to_numpy(),
                              "pnl": cum + Pk.value.to_numpy(), "value": Pk.value.to_numpy()})
    Tk = Tr[Tr.cid.isin(trades.cid)].copy()
    Tk["pos"] = pos_of.reindex(Tk.cid).to_numpy()
    Tk["sym"] = C.set_index("cid").sym.reindex(Tk.cid).to_numpy()
    Tk["time"] = _utc(pd.DatetimeIndex(Tk.date), Tk.phase.to_numpy()) if len(Tk) else pd.DatetimeIndex([])
    Tk["kind"] = np.array(KIND_NAMES)[Tk.kind.to_numpy().astype(int)] if len(Tk) else []
    Tk["phase"] = np.array(PHASES)[Tk.phase.to_numpy().astype(int)] if len(Tk) else []
    tranches = Tk[["pos", "sym", "time", "date", "px", "notional", "kind", "phase"]].sort_values(
        ["pos", "time"], kind="stable").reset_index(drop=True)
    signals = C[["sym", "signal_day", "chain_status", "status", "member", "atH_only", "deferred", "rolled", "cid"]]
    signals = signals.assign(status=np.array(STATUS)[signals.status.to_numpy()],
                             pos=pos_of.reindex(signals.cid).to_numpy()).sort_values(
        ["signal_day", "sym"], kind="stable").reset_index(drop=True)
    cand = C[ent].reset_index(drop=True)
    paths = Pth[Pth.cid.isin(cand.cid)].sort_values(["cid", "d"], kind="stable").reset_index(drop=True)
    cand_tr = Tr[Tr.cid.isin(cand.cid)].sort_values(["cid", "d", "phase"], kind="stable").reset_index(drop=True)
    st = signals.chain_status.value_counts().to_dict()
    log.update({"signals": int(len(signals)), "candidates_entered": int(len(cand)), "trades": int(len(trades)),
                "chain_status": st, "deferred_entries": int(trades.deferred.sum()),
                "rolled_entries": int(trades.rolled.sum()), "atH_only_trades": int(trades.atH_only.sum()),
                "flat_bar_stops": int((trades.stop_fill == "flat_close").sum()),
                "gap_stops": int((trades.stop_fill == "open").sum()),
                "dead_closes": int(trades.exit_reason.str.endswith("dead").sum()),
                "open_at_end": int(trades.open_at_end.sum()), "adds_cancelled": int(trades.adds_cancelled.sum()),
                "tranches": int((tranches.kind.isin(["entry", "add"])).sum()), "seconds": round(time.time() - t0, 1)})
    return {"trades": trades, "tranches": tranches, "expo": expo, "daily_mtm": daily_mtm, "signals": signals,
            "fills_audit": audits, "log": log, "cand": cand, "paths": paths, "cand_tr": cand_tr, "calendar": cal,
            "cfg": cfg, "start": start_ts, "end": end_ts, "names": names, "arrs": arrs, "data": data}


def _empty_frame(dtypes: dict) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in dtypes.items()})


def _empty_cand() -> pd.DataFrame:
    """The candidate table of a run without any signal, with the dtypes a non-empty run has."""
    ints = ["cid", "name_id", "t", "status", "e", "x", "xph", "xcode", "stop_kind", "n_tranches", "k", "n_path",
            "n_tr", "adds_cancelled", "g_sig", "g_e", "g_x"]
    bools = ["tp_hit", "deferred", "rolled", "atH_only", "member"]
    floats = ["S", "TP", "entry1_px", "ret", "ret_gross", "fees", "divs", "exit_px", "rank_key"]
    dt = {"sym": object, "signal_day": "datetime64[ns]"}
    dt.update({c: np.int64 for c in ints})
    dt.update({c: bool for c in bools})
    dt.update({c: float for c in floats})
    return _empty_frame(dt)


def _dates_of(C: pd.DataFrame, cal: pd.DatetimeIndex, col: str) -> np.ndarray:
    g = C[col].to_numpy()
    out = np.full(len(g), np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    ok = g >= 0
    out[ok] = cal.values[g[ok]]
    return out


def in_position(res: dict, name: str) -> pd.Series:
    """Long (True) at each close of the window while any tranche of a chained position is open."""
    f = res["data"][name]
    idx = f.index[(f.index >= res["start"]) & (f.index <= res["end"])]
    m = res["daily_mtm"]
    held = set(pd.DatetimeIndex(m.date[(m.sym == name) & (m.value > 0)]))
    return pd.Series([d in held for d in idx], index=idx, dtype=bool)


# ============================================================================ portfolio

@njit(cache=True)
def _book(g0, g1, c_name, c_gsig, c_ge, c_gx, c_xph, c_mark, c_off, c_len, c_cost,
          p_g, p_dcash, p_value, p_res, rf, n_slots, lev, spread, idle_tb, forced, n_names,
          eq, cash_o, notional_o, npos_o, nnew_o, nskip_o, nineli_o, taken_M, taken_E):
    nc = len(c_name)
    s_c = np.full(n_slots, -1, np.int64)
    s_M = np.zeros(n_slots)
    s_ptr = np.zeros(n_slots, np.int64)
    s_val = np.zeros(n_slots)
    s_res = np.zeros(n_slots)
    last_exit = np.full(n_names, -1, np.int64)
    cash = 1.0
    E = 1.0
    ptr = 0
    while ptr < nc and c_ge[ptr] < g0:
        ptr += 1
    ruined = False
    for g in range(g0, g1 + 1):
        i = g - g0
        if ruined:
            eq[i] = 0.0
            continue
        E_prev = E
        if cash >= 0.0:
            cash += cash * rf[g] * idle_tb
        else:
            cash += cash * (rf[g] + spread)
        cap = cash + (lev - 1.0) * E_prev
        nfree = 0
        for s in range(n_slots):
            ci = s_c[s]
            if ci < 0:
                nfree += 1
                continue
            if c_gx[ci] == g and c_xph[ci] == 0 and c_mark[ci] == 0:
                # exit at this open: apply its row now and free the slot for this open's entries
                end = c_off[ci] + c_len[ci]
                while s_ptr[s] < end and p_g[s_ptr[s]] <= g:
                    cash += s_M[s] * p_dcash[s_ptr[s]]
                    cap += s_M[s] * p_dcash[s_ptr[s]]
                    s_ptr[s] += 1
                s_c[s] = -1
                s_val[s] = 0.0
                s_res[s] = 0.0
                nfree += 1
            else:
                cap -= s_M[s] * s_res[s] * (1.0 + c_cost[ci])
        nnew = 0
        nskip = 0
        nineli = 0
        while ptr < nc and c_ge[ptr] == g:
            ci = ptr
            ptr += 1
            nm = c_name[ci]
            if (not forced) and last_exit[nm] > c_gsig[ci]:
                nineli += 1
                continue
            if nfree == 0:
                nskip += 1
                continue
            M = min(lev * E_prev / n_slots, cap / (1.0 + c_cost[ci]))
            if M <= 1e-12 * E_prev:
                nskip += 1
                continue
            for s in range(n_slots):
                if s_c[s] < 0:
                    s_c[s] = ci
                    s_M[s] = M
                    s_ptr[s] = c_off[ci]
                    s_val[s] = 0.0
                    s_res[s] = 2.0 / 3.0
                    break
            cap -= M * (1.0 + c_cost[ci])
            nfree -= 1
            nnew += 1
            last_exit[nm] = c_gx[ci]
            taken_M[ci] = M
            taken_E[ci] = E_prev
        MV = 0.0
        npos = 0
        for s in range(n_slots):
            ci = s_c[s]
            if ci < 0:
                continue
            end = c_off[ci] + c_len[ci]
            while s_ptr[s] < end and p_g[s_ptr[s]] <= g:
                cash += s_M[s] * p_dcash[s_ptr[s]]
                s_val[s] = p_value[s_ptr[s]]
                s_res[s] = p_res[s_ptr[s]]
                s_ptr[s] += 1
            if s_ptr[s] >= end and c_gx[ci] <= g and c_mark[ci] == 0:
                s_c[s] = -1
                s_val[s] = 0.0
                s_res[s] = 0.0
                continue
            MV += s_M[s] * s_val[s]
            npos += 1
        E = cash + MV
        if E <= 0.0:
            E = 0.0
            ruined = True
        eq[i] = E
        cash_o[i] = cash
        notional_o[i] = MV
        npos_o[i] = npos
        nnew_o[i] = nnew
        nskip_o[i] = nskip
        nineli_o[i] = nineli


def _run_book(cand: pd.DataFrame, paths: pd.DataFrame, cal: pd.DatetimeIndex, start, end, order: np.ndarray,
              n_slots: int, lev: float, idle_tbill: bool, forced: bool, n_names: int) -> dict:
    cal = pd.DatetimeIndex(cal).as_unit("ns")
    g0 = int(np.searchsorted(cal.asi8, pd.Timestamp(start).value, "left"))
    g1 = int(np.searchsorted(cal.asi8, pd.Timestamp(end).value, "right")) - 1
    C = cand.iloc[order].reset_index(drop=True)
    cid_pos = pd.Series(np.arange(len(C)), index=C.cid.to_numpy())
    P = paths.copy()
    P["ci"] = cid_pos.reindex(P.cid).to_numpy()
    P = P.dropna(subset=["ci"]).astype({"ci": np.int64}).sort_values(["ci", "g"], kind="stable")
    lens = P.groupby("ci").size().reindex(np.arange(len(C))).fillna(0).astype(np.int64).to_numpy()
    offs = np.r_[0, np.cumsum(lens)[:-1]].astype(np.int64) if len(C) else np.zeros(0, np.int64)
    rf = _tbill_session(cal)
    G = max(g1 - g0 + 1, 0)
    eq, cash, notl = np.zeros(G), np.zeros(G), np.zeros(G)
    npos, nnew, nskip, nineli = (np.zeros(G, np.int64) for _ in range(4))
    tM, tE = np.full(len(C), np.nan), np.full(len(C), np.nan)
    _book(g0, g1, C.name_id.to_numpy(np.int64), C.g_sig.to_numpy(np.int64), C.g_e.to_numpy(np.int64),
          C.g_x.to_numpy(np.int64), C.xph.to_numpy(np.int64), (C.xcode.to_numpy() == X_END).astype(np.int64),
          offs, lens, C.cost.to_numpy(float), P.g.to_numpy(np.int64), P.dcash.to_numpy(float),
          P.value.to_numpy(float), P.res.to_numpy(float), rf, int(n_slots), float(lev), FIN_SPREAD / 252.0,
          1.0 if idle_tbill else 0.0, forced, int(n_names), eq, cash, notl, npos, nnew, nskip, nineli, tM, tE)
    idx = cal[g0:g1 + 1]
    prev = np.r_[1.0, eq[:-1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = np.where(prev > 0, eq / prev - 1.0, 0.0)
        glev = np.where(eq > 0, notl / eq, np.nan)
    daily = pd.DataFrame({"equity": eq, "ret": ret, "rf": rf[g0:g1 + 1], "excess": ret - rf[g0:g1 + 1],
                          "cash": cash, "notional": notl, "gross_lev": glev, "n_pos": npos, "n_new": nnew,
                          "n_no_slot": nskip, "n_ineligible": nineli}, index=idx)
    taken = np.isfinite(tM)
    pos = C[taken].copy()
    pos["M"] = tM[taken]
    pos["M_frac"] = tM[taken] / tE[taken]
    pos["pnl"] = pos.M * pos.ret_1x
    log = {"sessions": int(G), "positions": int(taken.sum()), "max_positions": int(npos.max()) if G else 0,
           "max_gross_lev": float(np.nanmax(glev)) if G else 0.0, "min_cash": float(cash.min()) if G else 0.0,
           "no_slot": int(nskip.sum()), "ineligible": int(nineli.sum()),
           "M_capped": int((pos.M_frac < lev / n_slots * (1 - 1e-9)).sum())}
    return {"daily": daily, "positions": pos.reset_index(drop=True), "log": log}


def _need_res(res, fn: str) -> None:
    """portfolio-type functions take the whole stock_trades() result (coding choice 14), not its trades."""
    if not (isinstance(res, dict) and {"cand", "paths", "calendar", "arrs", "names"} <= set(res)):
        raise TypeError(f"{fn}() takes the dict that stock_trades() returns (it draws from every entered candidate "
                        f"and its daily path: res['cand'], res['paths']), not {type(res).__name__}; "
                        f"bb_engine_spec's portfolio(trades, ...) is portfolio(stock_trades(...), ...) here")


def _cand_with_cost(res: dict) -> pd.DataFrame:
    C = res["cand"].copy()
    C["cost"] = np.array([res["arrs"][s]["cost"] for s in C.sym], float)
    return C


def portfolio(res: dict, n_slots: int = N_SLOTS, seed: int = SEED, rank: str = "random", lev: float = 1.0,
              idle_tbill: bool = True, start=None, end=None) -> dict:
    """The 20-slot book over res's window (res = the stock_trades() result): daily account returns, excess
    returns over the T-bill, positions."""
    _need_res(res, "portfolio")
    C = _cand_with_cost(res)
    start = res["start"] if start is None else _session_bound(start, False)
    end = res["end"] if end is None else _session_bound(end, True)
    base = np.lexsort((C.name_id.to_numpy(), C.g_e.to_numpy()))        # (entry session, symbol)
    if rank == "random":
        key = np.empty(len(C))
        key[base] = np.random.default_rng(seed).random(len(C))
        order = np.lexsort((key, C.g_e.to_numpy()))
    elif rank == "atr_dist":
        rk = np.nan_to_num(C.rank_key.to_numpy(float), nan=-np.inf)
        order = np.lexsort((C.name_id.to_numpy(), -rk, C.g_e.to_numpy()))
    else:
        raise ValueError("rank must be 'random' or 'atr_dist'")
    out = _run_book(C, res["paths"], res["calendar"], start, end, order, n_slots, lev, idle_tbill, False,
                    len(res["names"]))
    out["log"].update(seed=seed, rank=rank, lev=lev, n_slots=n_slots, idle_tbill=idle_tbill)
    return out


def portfolio_seeds(res: dict, seeds=SEEDS_FURTHER, **kw) -> pd.DataFrame:
    """Daily excess returns of the book for each seed (HS1: the 100 further seeds)."""
    _need_res(res, "portfolio_seeds")
    return pd.DataFrame({s: portfolio(res, seed=s, **kw)["daily"].excess for s in seeds})


# ============================================================================ matched random-entry book

@njit(cache=True)
def _twin(o, c, flat, div, cost, dead, end_i, e, ev_d, ev_ph, ev_kind, rec, base,
          p_d, p_dcash, p_value, p_res):
    """A twin position on fixed sessions: kinds 0 entry, 1 add (+M/3 at the open), 2 TP (sell half), 3 exit (all),
    6 mark. Returns (exit session, exit phase, is_mark, ret, rows)."""
    n = len(o)
    third = 1.0 / 3.0
    sh = 0.0
    cash = 0.0
    nadd = 0
    tp = False
    j = 0
    nev = len(ev_d)
    rows = 0
    xd = e
    xph = 2
    mark = 0
    d = e
    while True:
        cash0 = cash
        if d > e and sh > 0.0 and div[d] != 0.0:
            cash += sh * div[d]
        done = False
        for ph in range(0, 3, 2):
            while j < nev and ev_d[j] == d and ev_ph[j] == ph:
                k = ev_kind[j]
                px = o[d] if ph == 0 else c[d]
                if k == 0 or k == 1:
                    if not tp:
                        sh += third / px
                        cash -= third * (1.0 + cost)
                        if k == 1:
                            nadd += 1
                elif k == 2:
                    if not tp:
                        q = 0.5 * sh
                        cash += q * px * (1.0 - cost)
                        sh -= q
                        tp = True
                elif k == 3:
                    cash += sh * px * (1.0 - cost)
                    sh = 0.0
                    done = True
                    xd = d
                    xph = ph
                elif k == 6:
                    done = True
                    xd = d
                    xph = 2
                    mark = 1
                j += 1
                if done:
                    break
            if done:
                break
        if not done and (d == end_i or d == n - 1):
            if dead and d == n - 1:
                cash += sh * c[d] * (1.0 - cost)
                sh = 0.0
            else:
                mark = 1
            done = True
            xd = d
            xph = 2
        if rec:
            r = base + rows
            p_d[r] = d
            p_dcash[r] = cash - cash0
            p_value[r] = sh * c[d]
            p_res[r] = 0.0 if (tp or (done and mark == 0)) else third * (2 - nadd)
        rows += 1
        if done:
            break
        d += 1
    ret = cash + (sh * c[xd] if mark == 1 else 0.0)
    return xd, xph, mark, ret, rows


def _roll_open(d: int, flat: np.ndarray, last: int) -> int:
    while d <= last and flat[d]:
        d += 1
    return d


def random_entry_book(res: dict, port: dict, seed: int = SEED, n_slots: int = N_SLOTS, lev: float = 1.0,
                      idle_tbill: bool = True) -> dict:
    """Matched random-entry book (coding choice 10): same sessions, slot count, holding durations and tranche
    fractions as the portfolio's positions, in random members; returns portfolio()'s shape plus the twins."""
    _need_res(res, "random_entry_book")
    cal, arrs, names = res["calendar"], res["arrs"], res["names"]
    pos = port["positions"].sort_values(["g_e", "name_id"], kind="stable").reset_index(drop=True)
    g0 = int(np.searchsorted(cal.asi8, res["start"].value, "left"))
    g1 = int(np.searchsorted(cal.asi8, res["end"].value, "right")) - 1
    N = len(names)
    avail = np.zeros((g1 - g0 + 1, N), bool)
    for j, s in enumerate(names):
        a = arrs[s]
        gi = a["gidx"]
        ok = a["member"] & ~a["flat"] & (gi >= g0) & (gi <= g1)
        avail[gi[ok] - g0, j] = True
    TR = res["cand_tr"]
    tr_by = {cid: g for cid, g in TR.groupby("cid")}
    rng = np.random.default_rng(seed)
    busy = np.full(N, -1, np.int64)
    twins, rows = [], []
    for r in pos.itertuples():
        ge = int(r.g_e)
        el = np.flatnonzero(avail[ge - g0] & (busy < ge))
        if len(el) == 0:
            continue
        j = int(el[rng.integers(len(el))])
        s = names[j]
        a = arrs[s]
        gi = a["gidx"]
        last = len(gi) - 1
        e = int(np.searchsorted(gi, ge, "left"))
        ev = tr_by[r.cid]
        ev_d, ev_ph, ev_k = [], [], []
        for t in ev.itertuples():
            kind = int(t.kind)
            ph = OPEN if int(t.phase) == OPEN else CLOSE
            if kind == K_ENTRY:
                kk = 0
            elif kind == K_ADD:
                kk = 1
            elif kind == K_TP:
                kk = 2
            elif kind == K_MARK:
                kk = 6
            else:
                kk = 3
            dl = int(np.searchsorted(gi, int(t.g), "left"))
            if kk == 0:
                dl = e
            elif ph == OPEN:
                dl = _roll_open(dl, a["flat"], last)
            if dl > last:
                continue
            ev_d.append(dl); ev_ph.append(ph); ev_k.append(kk)
        o_ = np.lexsort((np.array(ev_ph), np.array(ev_d)))
        ev_d = np.array(ev_d, np.int64)[o_]; ev_ph = np.array(ev_ph, np.int64)[o_]; ev_k = np.array(ev_k, np.int64)[o_]
        end_i = int(np.searchsorted(gi, g1, "right")) - 1
        cost = a["cost"]
        z = np.zeros(0)
        xd, xph, mark, ret, nrow = _twin(a["o"], a["c"], a["flat"], a["div"], cost, a["dead"], end_i, e,
                                         ev_d, ev_ph, ev_k, False, 0, np.zeros(0, np.int64), z, z, z)
        p_d = np.zeros(nrow, np.int64); p_dc = np.zeros(nrow); p_v = np.zeros(nrow); p_r = np.zeros(nrow)
        _twin(a["o"], a["c"], a["flat"], a["div"], cost, a["dead"], end_i, e, ev_d, ev_ph, ev_k, True, 0,
              p_d, p_dc, p_v, p_r)
        cid = len(twins)
        twins.append({"cid": cid, "sym": s, "name_id": j, "g_sig": ge - 1, "g_e": ge, "g_x": int(gi[xd]),
                      "xph": xph, "xcode": X_END if mark else X_MID, "cost": cost, "ret_1x": ret,
                      "matched_cid": r.cid, "matched_sym": r.sym})
        rows.append(pd.DataFrame({"cid": cid, "g": gi[p_d], "dcash": p_dc, "value": p_v, "res": p_r}))
        busy[j] = int(gi[xd])
    C = pd.DataFrame(twins)
    P = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["cid", "g", "dcash", "value", "res"])
    if len(C) == 0:
        raise ValueError("no twin could be drawn")
    order = np.lexsort((C.cid.to_numpy(), C.g_e.to_numpy()))
    out = _run_book(C, P, cal, res["start"], res["end"], order, n_slots, lev, idle_tbill, True, N)
    out["twins"] = C
    out["log"].update(seed=seed, matched=int(len(pos)), twins=int(len(C)))
    return out


# ============================================================================ benchmarks

def _ew(data: dict, start, end, spells: dict | None, min_history: int = 0) -> pd.DataFrame:
    """Equal-weight daily-rebalanced total return. A name contributes its close-to-close return on the sessions
    after its max(min_history, 1)-th session (min_history = 0 or 1: from the session after its first close)."""
    cal = calendar(data)
    start, end = _session_bound(start, False), _session_bound(end, True)
    cal = cal[cal <= end]
    i0 = int(np.searchsorted(cal.asi8, start.value, "left"))
    num = np.zeros(len(cal))
    den = np.zeros(len(cal))
    for s, f in data.items():
        idx = pd.DatetimeIndex(f.index).normalize()
        tr = pd.Series(np.asarray(f["tr"], float), index=idx)
        tr = tr[~tr.index.duplicated(keep="last")].sort_index()
        k = max(int(min_history), 1) - 1
        if len(tr) <= k:
            continue
        first = tr.index[k]
        t_ = tr.reindex(cal).ffill()
        r = (t_ / t_.shift(1) - 1.0).to_numpy()
        ok = np.isfinite(r) & (cal > first)
        if spells is not None and s in spells:
            ok &= _spell_mask(cal, spells[s])
        num[ok] += r[ok]
        den[ok] += 1
    with np.errstate(invalid="ignore"):
        ret = np.where(den > 0, num / np.maximum(den, 1), 0.0)
    rf = _tbill_session(cal)
    out = pd.DataFrame({"ret": ret, "rf": rf, "excess": ret - rf, "n": den.astype(int)}, index=cal)
    return out.iloc[i0:]


def benchmark_ew_members(start=START, end=END, data: dict | None = None) -> pd.DataFrame:
    """Equal-weight point-in-time S&P 500 members, total return, rebalanced daily; a member whose prices end is held
    at its last close while it stays a member. data: {name: frame with tr (and attrs['spells'])}."""
    data = _members_data() if data is None else data
    spells = {s: f.attrs["spells"] for s, f in data.items() if "spells" in f.attrs}
    return _ew(data, start, end, spells)


def benchmark_ew_etfs(start=START, end=END, data: dict | None = None, min_history: int = WARMUP) -> pd.DataFrame:
    """Equal-weight buy-and-hold of the ETFs in the study at the time, rebalanced daily: each ETF from its first
    raw_pit date plus 60 sessions of history (the Data section), i.e. it earns its first return on its 61st
    session, the first whose open the strategy could buy (a signal needs 60 completed bars). min_history=0 holds
    each ETF from the session after its first close (coding choice 11)."""
    data = universe_data("etfs") if data is None else data
    return _ew(data, start, end, None, min_history)


# ============================================================================ selftest

def _bars(rows, start="2024-01-01"):
    """rows: list of (o, h, l, c) on consecutive business days from start."""
    idx = pd.bdate_range(start, periods=len(rows))
    a = np.array(rows, float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}, index=idx)


def _co_row(prev_c: float, c: float) -> tuple:
    """A close-only source row as universe_pit_all writes it (screener.data.from_sp500_pit): open = previous close,
    high / low = max / min(open, close)."""
    return (prev_c, max(prev_c, c), min(prev_c, c), c)


def _mech(f: pd.DataFrame, sig_at, S_at_val, lvl_at=(), exit_at=(), dead=False, member=None, div=None,
          cost=0.0, start=None, end=None, close_only=()):
    """Run the numba simulation on a hand-built frame with signals injected by position (indicators bypassed).
    close_only: positions of close-only source rows (flat bars whatever their OHLC)."""
    n = len(f)
    o, h, l, c = (f[k].to_numpy(float) for k in OHLC)
    flat = _exact_flat(o, h, l, c)
    flat[list(close_only)] = True
    sig = np.zeros(n, bool); sig[list(sig_at)] = True
    lvl = np.zeros(n, bool); lvl[list(sig_at) + list(lvl_at)] = True
    ex = np.zeros(n, bool); ex[list(exit_at)] = True
    S_at = np.full(n, float(S_at_val)) if np.isscalar(S_at_val) else np.asarray(S_at_val, float)
    mem = np.ones(n, bool) if member is None else np.asarray(member, bool)
    dv = np.zeros(n) if div is None else np.asarray(div, float)
    wd = f.index.weekday.to_numpy().astype(np.int64)
    cand = np.array(sorted(sig_at), np.int64)
    start_i = 0 if start is None else start
    end_i = n - 1 if end is None else end
    nc = len(cand)
    oi = np.zeros((nc, NI), np.int64); of = np.zeros((nc, NF))
    P, T = 200, 50
    p = [np.zeros(P, np.int64)] + [np.zeros(P) for _ in range(5)]
    t = [np.zeros(T, np.int64), np.zeros(T), np.zeros(T), np.zeros(T, np.int8), np.zeros(T, np.int8)]
    audit = np.zeros((50, 3), np.int64); na = np.zeros(1, np.int64)
    args = (o, h, l, c, flat, mem, dv, wd, lvl, ex, np.ones(n, bool), np.arange(n, dtype=np.int64) - 1, S_at, cand,
            float(cost), bool(dead), start_i, end_i)
    _sim(*args, False, np.zeros(nc, np.int64), np.zeros(nc, np.int64), oi, of, *p, *t, audit, na)
    po = np.r_[0, np.cumsum(oi[:, I_NP])[:-1]].astype(np.int64)
    to = np.r_[0, np.cumsum(oi[:, I_NT])[:-1]].astype(np.int64)
    _sim(*args, True, po, to, oi, of, *p, *t, audit, na)
    ntr = int(oi[:, I_NT].sum())
    tc = np.repeat(np.arange(nc), oi[:, I_NT]).astype(np.int64)
    _audit_tranches(t[0][:ntr], t[1][:ntr], t[3][:ntr], t[4][:ntr], tc, o, h, l, flat, 0, audit, na)
    tr = [(int(t[0][r]), round(float(t[1][r]), 10), round(float(t[2][r]), 10), KIND_NAMES[int(t[3][r])],
           PHASES[int(t[4][r])]) for r in range(ntr)]
    npth = int(oi[:, I_NP].sum())
    path = pd.DataFrame({"d": p[0][:npth], "dcash": p[1][:npth], "value": p[2][:npth], "res": p[3][:npth],
                         "expo": p[4][:npth], "sh": p[5][:npth]})
    return oi, of, tr, path, int(na[0])


def _check_mechanics(say) -> None:
    th = 1.0 / 3.0
    # ---- 1. gap-through stop, adds, cancel and re-trigger; Mon 2024-01-01 .. (bdays)
    # d0 Mon signal; d1 Tue entry @100 (S = 95, TP = 115); d1 close 102.5 -> add1 + add2? 102.5 < 105 -> add1 only
    rows = [(99, 100, 98, 99.5),            # 0 Mon  signal close
            (100, 103, 99.5, 102.5),        # 1 Tue  entry 100; close >= 102 -> add1 pending
            (99.8, 101, 99, 100.5),         # 2 Wed  open 99.8 < avg 100 -> add1 cancelled
            (100.6, 106, 100.2, 105.5),     # 3 Thu  close >= 105: add1 and add2 pending
            (106, 107, 105, 106.5),         # 4 Fri  both adds fill at 106 (add2 checks the new average)
            (93, 94, 90, 92)]               # 5 Mon  open 93 <= S 95: gap stop at the open
    f = _bars(rows)
    oi, of, tr, path, na = _mech(f, [0], 95.0)
    assert na == 0 and oi[0, I_ST] == ST_ENTERED and oi[0, I_E] == 1 and oi[0, I_X] == 5
    assert oi[0, I_XC] == X_STOP and oi[0, I_SK] == SK_OPEN and oi[0, I_XPH] == OPEN and oi[0, I_NTR] == 3
    assert oi[0, I_CANC] == 1
    sh = th / 100 + 2 * th / 106
    exp_ret = sh * 93 - 1.0
    assert abs(of[0, F_RET] - exp_ret) < 1e-12 and abs(of[0, F_TP] - 115.0) < 1e-12
    kinds = [k for _, _, _, k, _ in tr]
    assert kinds == ["entry", "add", "add", "stop"], kinds
    assert abs(path.value.iloc[-1]) < 1e-15 and abs(path.dcash.sum() - exp_ret) < 1e-12
    # same with costs: every fill pays 3 bp of its notional
    oi2, of2, *_ = _mech(f, [0], 95.0, cost=0.0003)
    fees = 0.0003 * (1.0 + sh * 93)
    assert abs(of2[0, F_RET] - (exp_ret - fees)) < 1e-12 and abs(of2[0, F_FEES] - fees) < 1e-12
    say(f"  gap-through stop: entry 100, add1 cancelled at 99.8 then re-triggered, both adds at 106, stop at the "
        f"93 open: ret {of[0, F_RET]:+.6f} = hand {exp_ret:+.6f}; with 3 bp: fees {of2[0, F_FEES]:.6f} = hand")
    # ---- 2. bar touching both stop and TP -> stop first, whole position at S
    rows = [(99, 100, 98, 99.5), (100, 101, 99, 100), (100, 120, 90, 110)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0)
    assert na == 0 and oi[0, I_XC] == X_STOP and oi[0, I_SK] == SK_LEVEL and oi[0, I_TP] == 0
    assert abs(of[0, F_RET] - (th / 100 * 95 - th)) < 1e-12 and [k for *_, k, _ in tr] == ["entry", "stop"]
    # a bar opening above TP that later reaches S: the TP half fills at the open (the open precedes the rest of the
    # bar, so the 09:30 fill never depends on the bar's low), the remaining half stops at S intraday; a pending add
    # at that open is cancelled by the TP (regression: review finding 3)
    rows = [(99, 100, 98, 99.5), (100, 101, 99, 100), (118, 119, 94, 96)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0)
    exp = th / 100 * 0.5 * 118 + th / 100 * 0.5 * 95 - th
    assert na == 0 and oi[0, I_TP] == 1 and oi[0, I_XC] == X_STOP and oi[0, I_SK] == SK_LEVEL
    assert abs(of[0, F_RET] - exp) < 1e-12
    assert [(k, p) for *_, k, p in tr] == [("entry", "open"), ("tp", "open"), ("stop", "intraday")]
    # the same bar with its low above S: identical 09:30 fills (they never depend on the bar's low)
    rows2 = [(99, 100, 98, 99.5), (100, 101, 99, 100), (118, 119, 112, 116)]
    oi2, of2, tr2, *_ = _mech(_bars(rows2), [0], 95.0)
    assert oi2[0, I_TP] == 1 and tr2[:2] == tr[:2] and tr[1][1] == 118.0
    rows3 = [(99, 100, 98, 99.5), (100, 103, 99, 102.5), (118, 119, 94, 96)]         # add1 pending at the gap open
    oi3, of3, *_ = _mech(_bars(rows3), [0], 95.0)
    assert oi3[0, I_NTR] == 1 and oi3[0, I_CANC] == 1 and abs(of3[0, F_RET] - exp) < 1e-12
    # gap open above TP staying above S: TP half at the open; the rest stops later at the gap open below S
    rows = [(99, 100, 98, 99.5), (100, 101, 99, 100), (118, 119, 110, 112), (90, 91, 89, 90)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0)
    exp = th / 100 * 0.5 * 118 + th / 100 * 0.5 * 90 - th
    assert na == 0 and oi[0, I_TP] == 1 and oi[0, I_XC] == X_STOP and abs(of[0, F_RET] - exp) < 1e-12
    assert [(k, p) for *_, k, p in tr] == [("entry", "open"), ("tp", "open"), ("stop", "open")]
    # intraday TP then trend exit at the next open (TP sells half; adds cancelled after TP)
    rows = [(99, 100, 98, 99.5), (100, 101, 99, 100.5), (101, 116, 100.5, 112), (111, 112, 108, 109),
            (108, 109, 104, 105), (104.5, 105, 103, 104)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, exit_at=[4])
    s1 = th / 100
    # day 2 close 112 >= 105: but TP filled intraday on day 2 -> no adds
    exp = s1 * 0.5 * 115 + s1 * 0.5 * 104.5 - th
    assert na == 0 and oi[0, I_XC] == X_MID and oi[0, I_TP] == 1 and abs(of[0, F_RET] - exp) < 1e-12
    assert oi[0, I_X] == 5 and oi[0, I_XPH] == OPEN and oi[0, I_NTR] == 1
    say("  both touched intraday -> stop first (whole position at S); a bar opening above TP -> TP half at the open "
        "whatever its low (the rest stops at S if the bar reaches it; a pending add is cancelled); gap above TP then a "
        "later gap stop; intraday TP then midline exit at the next open (no add after the TP): all equal hand values")
    # ---- 3. Friday deferral with the signal re-check (2024-01-04 is a Thursday)
    rows = [(99, 100, 98, 99.5), (99.7, 100.5, 99, 100), (100.2, 101, 99.8, 100.4), (100.5, 101, 100, 100.6)]
    f = _bars(rows, "2024-01-04")
    assert f.index[1].weekday() == 4
    S_arr = np.array([95.0, 96.0, 97.0, 97.0])
    oi, of, tr, path, na = _mech(f, [0], S_arr, lvl_at=[1])          # Friday's bar still satisfies the signal
    assert na == 0 and oi[0, I_ST] == ST_ENTERED and oi[0, I_DEF] == 1 and oi[0, I_E] == 2 and oi[0, I_K] == 1
    assert of[0, F_S] == 96.0 and of[0, F_PX1] == 100.2 and abs(of[0, F_TP] - (100.2 + 3 * (100.2 - 96))) < 1e-12
    oi, of, tr, path, na = _mech(f, [0], S_arr)                       # Friday's bar fails the re-check
    assert oi[0, I_ST] == ST_RECHECK and oi[0, I_DEF] == 1
    rows_s = [(99, 100, 98, 99.5), (99.7, 100.5, 99, 100), (95.5, 98, 95, 97), (100.5, 101, 100, 100.6)]
    oi, of, tr, path, na = _mech(_bars(rows_s, "2024-01-04"), [0], S_arr, lvl_at=[1])
    assert oi[0, I_ST] == ST_OPEN_LE_S                                # Monday opens at or below S (95.5 vs 96)
    say("  Friday deferral: Thursday signal -> Monday open, S from Friday's bar; re-check failure skips; a "
        "deferred open at or below S skips")
    # ---- 4. flat bars
    rows = [(99, 100, 98, 99.5), (100, 100, 100, 100), (100.3, 101, 100, 100.8), (101, 102.5, 100.9, 102.4),
            (102, 102, 102, 102), (101.9, 102, 101, 101.5), (94, 94, 94, 94)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, lvl_at=[1])
    # entry rolls past the flat bar 1 to bar 2; bar 3 close 102.4 >= 1.02 x 100.3 = 102.306 -> add pending,
    # bar 4 flat: no fill there; fills at bar 5's open 101.9 (>= avg 100.3); bar 6 flat close 94 <= S -> stop at 94
    assert na == 0 and oi[0, I_E] == 2 and oi[0, I_ROLL] == 1 and oi[0, I_NTR] == 2
    assert oi[0, I_SK] == SK_FLAT and oi[0, I_X] == 6 and oi[0, I_XPH] == CLOSE
    exp = (th / 100.3 + th / 101.9) * 94 - 2 * th
    assert abs(of[0, F_RET] - exp) < 1e-12
    assert [(d, k) for d, _, _, k, _ in tr] == [(2, "entry"), (5, "add"), (6, "stop")]
    # a flat bar whose close is above S does nothing (no stop, no TP even if its close >= TP), and a flat close
    # >= 1.02 x entry creates no add
    rows = [(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), (120, 120, 120, 120), (100.2, 100.4, 99.9, 100.1)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0)
    assert na == 0 and oi[0, I_XC] == X_END and oi[0, I_NTR] == 1 and oi[0, I_TP] == 0
    say("  flat bars: entry and add wait for the next non-flat open; a flat close <= S stops at that close; a flat "
        "close >= TP or >= 1.02 x entry1 fills nothing")
    _check_close_only(say)


def _check_close_only(say) -> None:
    """Close-only source rows in universe_pit_all's form (open = previous close, high / low = max / min(open,
    close); not O = H = L = C) are flat bars through their flag (regression: review findings 1 and 2)."""
    th = 1.0 / 3.0
    co = _co_row
    # (a) entry: the session after the signal is close-only -> the entry waits for the next real open (re-check on
    # the latest completed bar, the close-only one); never at the close-only row's 'open' = the signal close
    rows = [(99, 100, 98, 99.5), co(99.5, 101.0), (101.2, 102, 100.8, 101.5), (101.4, 102, 101, 101.6)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, lvl_at=[1], close_only=[1])
    assert na == 0 and oi[0, I_E] == 2 and oi[0, I_ROLL] == 1 and of[0, F_PX1] == 101.2
    oi, *_ = _mech(_bars(rows), [0], 95.0, close_only=[1])
    assert oi[0, I_ST] == ST_RECHECK
    # (b) a trend exit decided at bar 2's close waits past the close-only bar 3 (close above S) to bar 4's open
    rows = [(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), (100.4, 101, 99.9, 100.2), co(100.2, 97.0),
            (97.3, 98, 96, 97.5)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, exit_at=[2], close_only=[3])
    assert na == 0 and oi[0, I_XC] == X_MID and oi[0, I_X] == 4 and oi[0, I_XPH] == OPEN and of[0, F_XPX] == 97.3
    # (c) a close-only close below S stops at that close (not at S, although the synthesized low is below S)
    rows = [(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), co(100.5, 90.0), (90, 91, 89, 90.5)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, close_only=[2])
    assert na == 0 and oi[0, I_SK] == SK_FLAT and oi[0, I_X] == 2 and of[0, F_XPX] == 90.0
    assert abs(of[0, F_RET] - (th / 100 * 90 - th)) < 1e-12
    # (d) a close-only close above TP fills nothing; the next real open above TP fills the TP half there
    rows = [(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), co(100.5, 118.0), (118, 119, 117, 118)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, close_only=[2])
    assert na == 0 and [(d, k) for d, _, _, k, _ in tr] == [(1, "entry"), (3, "tp"), (3, "mark")]
    # (e) a close-only close >= 1.02 x entry1 creates no add
    rows = [(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), co(100.5, 103.0), (103.2, 103.5, 102.5, 103.1)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, close_only=[2])
    assert na == 0 and oi[0, I_NTR] == 1
    # (f) the fill audit sees a fill placed on a close-only row (the audit is fed the flag, not O = H = L = C)
    o_, h_, l_, c_ = (np.array(x, float) for x in zip(*[(99, 100, 98, 99.5), co(99.5, 101.0)]))
    fl = np.array([False, True])
    audit = np.zeros((5, 3), np.int64); na_ = np.zeros(1, np.int64)
    _audit_tranches(np.array([1], np.int64), np.array([99.5]), np.array([K_ENTRY], np.int8),
                    np.array([OPEN], np.int8), np.zeros(1, np.int64), o_, h_, l_, fl, 0, audit, na_)
    assert na_[0] == 1 and audit[0, 2] == A_FLAT
    # (g) through stock_trades: a random walk with runs of close-only rows in universe_pit_all's form (4 sessions in
    # every 12 from session 250, a run of 60 at the end) and isolated ones before
    rng = np.random.default_rng(6)
    n = 700
    c = 50 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.005, n))
    h = np.maximum(o, c) * 1.01; l = np.minimum(o, c) * 0.99
    i_ = np.arange(n)
    co_m = (i_ >= 250) & ((i_ // 4) % 3 == 0)
    co_m[640:] = True
    co_m[rng.choice(np.arange(60, 250), 25, replace=False)] = True
    o[co_m] = np.r_[c[0], c[:-1]][co_m]
    h[co_m] = np.maximum(o, c)[co_m]; l[co_m] = np.minimum(o, c)[co_m]
    f = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "close_only": co_m},
                     index=pd.bdate_range("2000-01-03", periods=n))
    f.attrs["cost"] = 0.0
    assert not _exact_flat(o, h, l, c)[co_m].any()
    res = stock_trades("X", StockCfg(), "2000-01-01", "2003-12-31", ohlc=f)
    T, Tk, sg = res["trades"], res["tranches"], res["signals"]
    on_co = pd.Series(co_m, index=f.index)
    fills = Tk[(Tk.kind != "mark") & ~((Tk.kind == "stop") & (Tk.phase == "close")) & (Tk.kind != "dead")]
    assert not res["fills_audit"] and not on_co.reindex(pd.DatetimeIndex(fills.date)).any()
    assert not on_co.reindex(pd.DatetimeIndex(sg.signal_day)).any() and len(T) > 3
    n_fc = int((T.stop_fill == "flat_close").sum())
    assert n_fc >= 1 and res["log"]["close_only_rows"] == int(co_m.sum())
    # without the flag the same rows are ordinary bars: entries fill on them at the previous close (the defect)
    r_nf = stock_trades("X", StockCfg(), "2000-01-01", "2003-12-31", ohlc=f.drop(columns="close_only"))
    T_nf = r_nf["trades"]
    e_nf = on_co.reindex(pd.DatetimeIndex(T_nf.entry1_date)).to_numpy()
    assert e_nf.any() and np.allclose(T_nf.entry1_px[e_nf], f.close.shift(1).reindex(
        pd.DatetimeIndex(T_nf.entry1_date[e_nf])).to_numpy())
    say(f"  close-only rows (open = previous close, high/low = max/min(open, close), flagged from the source): no "
        f"signal, entry, add, TP or trend-exit fill on them; a pending entry waits (re-check) and an exit waits for "
        f"the next real open; a close below S stops at that close; the audit sees such a fill; stock_trades on a "
        f"path with {int(co_m.sum())} such rows: {len(T)} trades, {n_fc} flat-close stops, no fill or signal on "
        f"them, fill audit empty")
    # ---- 5. dead name vs window end
    rows = [(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), (100.4, 101, 99.9, 100.9)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, dead=True, cost=0.001)
    assert na == 0 and oi[0, I_XC] == X_DEAD and oi[0, I_X] == 2 and oi[0, I_XPH] == CLOSE
    exp = th / 100 * 100.9 * (1 - 0.001) - th * 1.001
    assert abs(of[0, F_RET] - exp) < 1e-12 and tr[-1][3] == "dead"
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, dead=False, cost=0.001)
    assert oi[0, I_XC] == X_END and abs(of[0, F_RET] - (th / 100 * 100.9 - th * 1.001)) < 1e-12
    say("  dead name closed at its last close with the exit cost; a live name at the window end is marked "
        "without it")
    # ---- 6. dividends (ex-date credit only to shares held at the prior close); membership; open <= S
    rows = [(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), (100, 101, 99.5, 100.2), (100, 100.5, 99.8, 100.1)]
    dv = np.array([0.0, 0.7, 0.4, 0.0])                       # ex-date on the entry day: not credited
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, div=dv)
    assert abs(of[0, F_DIV] - th / 100 * 0.4) < 1e-15
    oi, of, *_ = _mech(_bars(rows), [0], 95.0, member=[True, False, True, True])
    assert oi[0, I_ST] == ST_NOT_MEMBER
    oi, of, *_ = _mech(_bars(rows), [0], 100.0)
    assert oi[0, I_ST] == ST_OPEN_LE_S
    say("  dividends credited from the day after entry only; non-member entry day and open <= S are skipped")
    # ---- 7. exposure path: open-to-open holding of N sessions sums to N x notional
    rows = [(99, 100, 98, 99.5)] + [(100, 100.5, 99.5, 100)] * 5 + [(100, 100.5, 99.5, 100)]
    oi, of, tr, path, na = _mech(_bars(rows), [0], 95.0, exit_at=[4])
    assert oi[0, I_X] == 5 and abs(path.expo.sum() - 4 * th) < 1e-12
    say("  exposure path: an open-to-open holding of 4 sessions at M/3 sums to 4/3")


def _check_indicators(say) -> None:
    from analysis_2026.moneyline_ref import atr as ml_atr
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 500)))
    h = c * (1 + rng.uniform(0, 0.02, 500)); l = c * (1 - rng.uniform(0, 0.02, 500))
    a = _atr(h, l, c, 14); b = ml_atr(h, l, c, 14)
    assert np.allclose(a[13:], b[13:], rtol=1e-12, atol=0) and np.isnan(a[:13]).all()
    sma, ub = _sma_ub(c, 20, 2.0)
    s = pd.Series(c)
    assert np.allclose(sma[19:], s.rolling(20).mean()[19:], rtol=1e-12)
    assert np.allclose(ub[19:], (s.rolling(20).mean() + 2 * s.rolling(20).std(ddof=0))[19:], rtol=1e-10)
    # signal definition on a hand-checked series: flat bar creates no signal; fresh-close rule; warm-up 60
    n = 120
    cc = np.full(n, 100.0) + np.sin(np.arange(n)) * 0.5
    cc[100] = 110.0                        # breakout close
    cc[101] = 111.0                        # still above: not fresh
    o = cc.copy(); hh = cc + 0.3; ll = cc - 0.3
    flat = np.zeros(n, bool)
    dates = pd.bdate_range("2020-01-01", periods=n)
    sg = _signals(o, hh, ll, cc, flat, dates, StockCfg())
    assert sg["sig"][100] and not sg["sig"][101] and sg["lvl_ok"][101] and not sg["sig"][:59].any()
    o2, h2, l2 = o.copy(), hh.copy(), ll.copy()
    o2[100] = h2[100] = l2[100] = cc[100]
    flat2 = np.zeros(n, bool); flat2[100] = True
    sg2 = _signals(o2, h2, l2, cc, flat2, dates, StockCfg())
    assert not sg2["sig"][100]
    # a close-only row in universe_pit_all's form (not O = H = L = C) creates no signal once flagged
    o3, h3, l3 = o.copy(), hh.copy(), ll.copy()
    o3[100], h3[100], l3[100] = cc[99], max(cc[99], cc[100]), min(cc[99], cc[100])
    assert not _exact_flat(o3, h3, l3, cc)[100]
    assert _signals(o3, h3, l3, cc, flat, dates, StockCfg())["sig"][100]
    assert not _signals(o3, h3, l3, cc, flat2, dates, StockCfg())["sig"][100]
    # weekly: a week is flat only if every session of it is flat (close-only weeks create no weekly signal)
    wk_ = (dates - pd.to_timedelta(dates.weekday, unit="D")).normalize()
    fw = np.zeros(n, bool); fw[np.flatnonzero(wk_ == wk_[100])[:-1]] = True        # all but the last session
    lw = np.flatnonzero(wk_ == wk_[100])[-1]
    cw = cc.copy(); cw[lw] = 112.0
    sgw1 = _signals(o, np.maximum(hh, cw + 0.3), ll, cw, fw, dates, StockCfg(bars="1w"))
    fw2 = fw.copy(); fw2[lw] = True
    sgw2 = _signals(o, np.maximum(hh, cw + 0.3), ll, cw, fw2, dates, StockCfg(bars="1w"))
    assert sgw1["sig"][lw] and sgw2["lvl_ok"][lw] and not sgw2["sig"][lw]
    cc3 = cc.copy(); cc3[30] = 110.0
    assert not _signals(o, np.maximum(hh, cc3 + 0.3), ll, cc3, flat, dates, StockCfg())["sig"][30]
    # weekly: decisions only at a week's last session
    sgw = _signals(o, hh, ll, cc, flat, dates, StockCfg(bars="1w"))
    assert sgw["is_dec"].sum() == len(np.unique((dates - pd.to_timedelta(dates.weekday, unit="D")).normalize()))
    assert not (sgw["sig"] & ~sgw["is_dec"]).any()
    say("  ATR = moneyline_ref.atr, BB(20, 2) population sigma = pandas; fresh-close rule, warm-up 60, a flat bar "
        "and a flagged close-only bar create no signal; weekly decisions only at each week's last session, none in a "
        "week whose sessions are all flat")


@njit(cache=True)
def _mart_paths(n_names, n_days, sub, sig_on, sig_in, mu, seed, O, H, L, C):
    """Synthetic daily bars from a price that is a martingale in simple returns (mu = 0) or has a constant mean
    simple return per session split equally between the overnight and intraday halves; the intraday path has
    `sub` steps, high/low over the path."""
    np.random.seed(seed)
    for k in range(n_names):
        p = 50.0 + 50.0 * np.random.random()
        for d in range(n_days):
            p *= (1.0 + 0.5 * mu) * (1.0 + sig_on * np.random.standard_normal())
            o = p
            hi = p
            lo = p
            step = (1.0 + 0.5 * mu) ** (1.0 / sub)
            for _ in range(sub):
                p *= step * (1.0 + sig_in * np.random.standard_normal())
                if p > hi:
                    hi = p
                if p < lo:
                    lo = p
            O[k, d] = o
            H[k, d] = hi
            L[k, d] = lo
            C[k, d] = p


def _synthetic_universe(n_names, n_days, mu=0.0, seed=7, sub=390, member_frac=1.0, end=None):
    O, H, L, C = (np.zeros((n_names, n_days)) for _ in range(4))
    sig_d = 0.02
    _mart_paths(n_names, n_days, sub, sig_d * np.sqrt(0.3), sig_d * np.sqrt(0.7 / sub), mu, seed, O, H, L, C)
    idx = pd.bdate_range("1990-01-01", periods=n_days) if end is None else pd.bdate_range(end=end, periods=n_days)
    rng = np.random.default_rng(seed)
    out = {}
    for k in range(n_names):
        f = pd.DataFrame({"open": O[k], "high": H[k], "low": L[k], "close": C[k]}, index=idx)
        if member_frac < 1.0:
            m = np.ones(n_days, bool)
            a = int(rng.integers(0, n_days // 2)); m[a:a + int(n_days * (1 - member_frac))] = False
            f["member"] = m
        f.attrs["cost"] = 0.0
        out[f"S{k:04d}"] = f
    return out


def _check_martingale(say) -> dict:
    t0 = time.time()
    data = _synthetic_universe(560, 3600, mu=0.0, seed=11)
    res = stock_trades("synthetic", StockCfg(), start="1990-06-01", end="2100-01-01", ohlc=data)
    T = res["trades"]
    assert not res["fills_audit"]
    x = T.ret_gross.to_numpy()
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    z = m / se
    say(f"  martingale (560 names x 3,600 sessions, 390 intraday steps): {len(T):,} trades, mean gross ret "
        f"{m * 100:+.4f}% of M (SE {se * 100:.4f}%, z = {z:+.2f}); fill audit empty  [{time.time() - t0:.0f}s]")
    assert len(T) >= 20000 and abs(z) < 2.0
    # costs: net = gross - round trip on traded notional
    for k in data:
        data[k].attrs["cost"] = 0.0003
    res_c = stock_trades("synthetic", StockCfg(), start="1990-06-01", end="2100-01-01", ohlc=data)
    Tc = res_c["trades"]
    assert len(Tc) == len(T) and np.allclose(Tc.ret_gross - Tc.fees, Tc.ret, atol=1e-15)
    tk = res_c["tranches"][res_c["tranches"].kind != "mark"]
    traded = tk.notional.abs().groupby(tk.pos).sum()
    assert np.allclose(traded.reindex(Tc.pos).to_numpy() * 0.0003, Tc.fees.to_numpy(), rtol=1e-9)
    say(f"  after 3 bp per side: mean net - mean gross = {(Tc.ret.mean() - Tc.ret_gross.mean()) * 100:+.4f}% of M "
        f"= minus 3 bp x traded notional per trade ({traded.mean():.3f} M)")
    # drift adjustment: constant drift -> raw mean > 0, drift-adjusted ~ 0
    from analysis_2026 import bb_stats as BS
    dd = _synthetic_universe(560, 3600, mu=0.002, seed=12)
    rd = stock_trades("synthetic", StockCfg(), start="1990-06-01", end="2100-01-01", ohlc=dd)
    Td = rd["trades"]
    adj = BS.drift_adjust(Td, rd["expo"], session_returns(rd["data"]), leave_out_days=182, fallback_full=True)
    xa = adj.to_numpy()
    ma, sa = xa.mean(), xa.std(ddof=1) / np.sqrt(len(xa))
    mr, sr = Td.ret_gross.mean(), Td.ret_gross.std(ddof=1) / np.sqrt(len(Td))
    say(f"  constant drift +0.2%/session: raw mean gross {mr * 100:+.3f}% (z {mr / sr:+.1f}), drift-adjusted "
        f"{ma * 100:+.4f}% (z {ma / sa:+.2f})")
    assert mr / sr > 3 and abs(ma / sa) < 2.0
    adj0 = BS.drift_adjust(T, res["expo"], session_returns(res["data"]), leave_out_days=182, fallback_full=True)
    z0 = adj0.mean() / (adj0.std(ddof=1) / np.sqrt(len(adj0)))
    say(f"  no drift: drift-adjusted mean {adj0.mean() * 100:+.4f}% (z {z0:+.2f})")
    assert abs(z0) < 2.0
    return res


def _check_portfolio(say, res) -> None:
    t0 = time.time()
    p = portfolio(res, n_slots=20, seed=SEED)
    d = p["daily"]
    assert d.n_pos.max() <= 20 and (d.notional <= d.equity * (1 + 1e-9)).all() and d.cash.min() >= -1e-9
    P = p["positions"]
    # one position per name at a time; eligibility: no open portfolio position of the name at the signal close
    for s, g in P.groupby("sym"):
        g = g.sort_values("g_e")
        assert (g.g_sig.to_numpy()[1:] >= g.g_x.to_numpy()[:-1]).all()
    p2 = portfolio(res, n_slots=20, seed=SEED)
    assert p2["daily"].equals(d) and p2["positions"].cid.tolist() == P.cid.tolist()
    p3 = portfolio(res, n_slots=20, seed=SEED + 1)
    assert p3["positions"].cid.tolist() != P.cid.tolist() and p["log"]["no_slot"] > 0
    pa = portfolio(res, n_slots=20, rank="atr_dist")
    C = res["cand"]
    # on a contention session the atr_dist book takes the largest rank keys among eligible candidates
    PA = pa["positions"]
    n_checked = 0
    for day in pa["daily"].index[pa["daily"].n_no_slot.to_numpy() > 0][:200]:
        g = int(res["calendar"].get_loc(day))
        took = PA[PA.g_e == g]
        others = C[(C.g_e == g) & ~C.cid.isin(took.cid)]
        for o_ in others.itertuples():
            busy = ((PA.sym == o_.sym) & (PA.g_e < g) & (PA.g_x > o_.g_sig)).any()
            if not busy:                                   # skipped for lack of a slot: ranks below every taken one
                assert len(took) == 0 or o_.rank_key <= took.rank_key.min() + 1e-12
                n_checked += 1
    assert n_checked > 0
    pl = portfolio(res, n_slots=20, seed=SEED, lev=2.0)
    dl = pl["daily"]
    assert dl.n_pos.max() <= 20 and dl.gross_lev.max() < 3.0 and (dl.cash >= -dl.equity.shift(1).fillna(1.0)
                                                                   * (1 + 1e-9) - 1e-12).all()
    say(f"  20-slot book: max {d.n_pos.max()} positions, max gross {d.gross_lev.max():.3f}x at 1x (min cash "
        f"{d.cash.min():+.2e}), {pl['daily'].gross_lev.max():.3f}x at 2x; {p['log']['no_slot']:,} entries found no "
        f"slot; same seed identical, another seed differs; one name at a time  [{time.time() - t0:.1f}s]")
    # hand-checked tiny book: 2 slots, 3 candidates entering the same session, known paths
    cal = pd.bdate_range("2020-01-01", periods=6)
    cand = pd.DataFrame({"cid": [0, 1, 2], "sym": ["A", "B", "C"], "name_id": [0, 1, 2], "g_sig": [0, 0, 0],
                         "g_e": [1, 1, 1], "g_x": [3, 4, 2], "xph": [OPEN, CLOSE, OPEN], "xcode": [X_MID] * 3,
                         "cost": [0.0, 0.0, 0.0], "rank_key": [1.0, 3.0, 2.0], "ret_1x": [0.0] * 3})
    th = 1 / 3
    # A: buy 1/3 at 10 (day 1), value 1/3*11/10 day 2, sold at the open of day 3 at 12
    # B: buy 1/3 at 20 day 1, close 20 day 1, 22 day 2, 22 day 3, sold at close day 4 at 24
    # C: buy 1/3 at 5, sold at the open of day 2 at 5.5
    rows = [(0, 1, -th, th, 2 * th), (0, 2, 0.0, th * 1.1, 2 * th), (0, 3, th * 1.2, 0.0, 0.0),
            (1, 1, -th, th, 2 * th), (1, 2, 0.0, th * 1.1, 2 * th), (1, 3, 0.0, th * 1.1, 2 * th),
            (1, 4, th * 1.2, 0.0, 0.0),
            (2, 1, -th, th, 2 * th), (2, 2, th * 1.1, 0.0, 0.0)]
    paths = pd.DataFrame(rows, columns=["cid", "g", "dcash", "value", "res"])
    rf0 = _tbill_session(cal)
    out = _run_book(cand, paths, cal, cal[0], cal[-1], np.array([1, 2, 0]), 2, 1.0, False, False, 3)
    e = out["daily"].equity.to_numpy()
    # B (key 3) and C (key 2) taken at day 1 with M = 0.5 each; A finds no slot. C exits at day 2's open:
    # its slot frees at day 2's open but no candidate enters then.
    M = 0.5
    exp = [1.0, 1.0, 1.0 + M * (th * 1.1 - th) + M * (th * 1.1 - th), 1.0 + M * (th * 1.1 - th) + M * (th * 0.1),
           1.0 + M * th * 0.2 + M * th * 0.1, 1.0 + M * th * 0.2 + M * th * 0.1]
    assert np.allclose(e, exp, atol=1e-12), (e, exp)
    assert out["positions"].sym.tolist() == ["B", "C"] and out["daily"].n_no_slot.sum() == 1
    out_tb = _run_book(cand, paths, cal, cal[0], cal[-1], np.array([1, 2, 0]), 2, 1.0, True, False, 3)
    assert abs(out_tb["daily"].equity.iloc[0] - (1 + rf0[0])) < 1e-15
    say("  tiny 2-slot book: equity path equals the hand computation (ranked entry, slot freed at an open exit, "
        "idle cash at the T-bill)")


def _check_benchmark(say) -> None:
    idx = pd.bdate_range("2021-01-04", periods=6)
    trA = np.array([100, 101, 102, 101, 103, 104.0])
    trB = np.array([50, 50.5, 49, 48, np.nan, np.nan])          # dies after day 3 (held at its last close)
    trC = np.array([np.nan, np.nan, 20, 21, 22, 22.0])          # lists on day 2
    data = {}
    for s, tr in (("A", trA), ("B", trB), ("C", trC)):
        ok = np.isfinite(tr)
        f = pd.DataFrame({"open": tr[ok], "high": tr[ok], "low": tr[ok], "close": tr[ok], "tr": tr[ok]},
                         index=idx[ok])
        data[s] = f
    data["A"].attrs["spells"] = [(idx[0], idx[5])]
    data["B"].attrs["spells"] = [(idx[0], idx[4])]               # member through day 4: held at last close day 4
    data["C"].attrs["spells"] = [(idx[3], idx[5])]               # member from day 3
    b = benchmark_ew_members(idx[0], idx[5], data)
    rA = trA[1:] / trA[:-1] - 1
    rB = np.r_[trB[1:4] / trB[:3] - 1, 0.0]                      # day 4: at its last close
    rC = trC[3:] / trC[2:-1] - 1                                 # days 3..5
    exp = [np.nan, (rA[0] + rB[0]) / 2, (rA[1] + rB[1]) / 2, (rA[2] + rB[2] + rC[0]) / 3,
           (rA[3] + rB[3] + rC[1]) / 3, (rA[4] + rC[2]) / 2]
    assert b.ret.iloc[0] == 0.0 and np.allclose(b.ret.iloc[1:].to_numpy(), exp[1:], atol=1e-15)
    assert b.n.tolist() == [0, 2, 2, 3, 3, 2]
    e = benchmark_ew_etfs(idx[0], idx[5], {k: data[k] for k in ("A", "C")}, min_history=0)
    assert np.allclose(e.ret.iloc[1:].to_numpy(), [rA[0], rA[1], (rA[2] + rC[0]) / 2, (rA[3] + rC[1]) / 2,
                                                   (rA[4] + rC[2]) / 2], atol=1e-15)
    # admission after min_history sessions of history (the Data section's "plus 60 sessions"; regression: review
    # finding 7): with 3, A earns its first return on its 4th session (day 3), C (first close day 2) on day 5
    e3 = benchmark_ew_etfs(idx[0], idx[5], {k: data[k] for k in ("A", "C")}, min_history=3)
    assert e3.n.tolist() == [0, 0, 0, 1, 1, 2]
    assert np.allclose(e3.ret.to_numpy(), [0, 0, 0, rA[2], rA[3], (rA[4] + rC[2]) / 2], atol=1e-15)
    say("  EW members: membership spells, a dead member held at its last close, a late lister joining the session "
        "after its first close, all equal the hand computation; EW ETFs likewise, and with admission only after "
        "min_history sessions of history (default 60: first return on the 61st session)")


def _check_random_book(say, res) -> None:
    p = portfolio(res, seed=SEED)
    rb = random_entry_book(res, p, seed=SEED)
    rb2 = random_entry_book(res, p, seed=SEED)
    d = rb["daily"]
    assert rb2["daily"].equals(d) and d.n_pos.max() <= 20 and (d.notional <= d.equity * (1 + 1e-9)).all()
    tw = rb["twins"]
    pos = p["positions"].set_index("cid")
    same = (pos.loc[tw.matched_cid, "g_e"].to_numpy() == tw.g_e.to_numpy()).mean()
    assert same == 1.0 and len(tw) >= 0.95 * len(pos)
    say(f"  matched random-entry book: {len(tw):,} twins of {len(pos):,} positions, same entry sessions, max "
        f"{d.n_pos.max()} positions; reproducible")


def _check_variants(say) -> None:
    data = _synthetic_universe(30, 1500, mu=0.0003, seed=31, sub=24)
    for f in data.values():
        f.attrs["cost"] = 0.0003
    win = ("1990-04-01", "1995-12-31")
    r1 = stock_trades("synthetic", StockCfg(), *win, ohlc=data)
    T1 = r1["trades"]
    # double costs: same fills, twice the fees
    r2 = stock_trades("synthetic", StockCfg(cost_mult=2.0), *win, ohlc=data)
    T2 = r2["trades"]
    assert len(T1) == len(T2) and (T1.exit_date == T2.exit_date).all() and np.allclose(T2.fees, 2 * T1.fees)
    assert np.allclose(T2.ret_gross, T1.ret_gross, atol=1e-15)
    # 2x Reg-T: (lev - 1) / lev of the previous close's notional at the T-bill + 2.5 points, per session
    rl = stock_trades("synthetic", StockCfg(lev=2.0), *win, ohlc=data)
    Tl = rl["trades"]
    m = rl["daily_mtm"].sort_values(["pos", "date"])
    rf = pd.Series(_tbill_session(rl["calendar"]), index=rl["calendar"])
    prev = m.groupby("pos").value.shift(1).fillna(0.0)
    fin_hand = (0.5 * prev * (rf.reindex(pd.DatetimeIndex(m.date)).to_numpy() + FIN_SPREAD / 252)).groupby(m.pos).sum()
    assert np.allclose(fin_hand.reindex(Tl.pos).to_numpy(), Tl.fin.to_numpy(), rtol=1e-12)
    assert np.allclose(Tl.ret, Tl.ret_1x - Tl.fin) and np.allclose(Tl.ret_1x, T1.ret) and (Tl.fin > 0).mean() > 0.9
    # in_position: long on the closes a chained position holds shares
    s0 = T1.sym.iloc[0]
    ip = in_position(r1, s0)
    held = r1["daily_mtm"][(r1["daily_mtm"].sym == s0) & (r1["daily_mtm"].value > 0)]
    assert ip.sum() == held.date.nunique() and ip[pd.DatetimeIndex(held.date)].all()
    # weekly bars: signals on a week's last session; midline exits the session after one
    rw = stock_trades("synthetic", StockCfg(bars="1w"), *win, ohlc=data)
    Tw = rw["trades"]
    for s, g in Tw.groupby("sym"):
        idx = rw["data"][s].index
        wk = (idx - pd.to_timedelta(idx.weekday, unit="D")).normalize()
        last = pd.Series(idx, index=idx).groupby(wk).transform("max")
        is_last = pd.Series(idx == last.to_numpy(), index=idx)
        assert is_last.reindex(pd.DatetimeIndex(g.signal_day)).all()
        mid = g[g.exit_reason.str.endswith("mid")]
        pos_x = idx.get_indexer(pd.DatetimeIndex(mid.exit_date))
        assert is_last.iloc[pos_x - 1].all()
    sd = portfolio_seeds(r1, seeds=SEEDS_FURTHER[:3])
    assert sd.shape[1] == 3 and len(sd) == len(portfolio(r1)["daily"])
    # with a slot per name (no contention) the book takes exactly the chained trades, whatever the seed
    for sd_ in (SEED, SEED + 7):
        pf = portfolio(r1, n_slots=len(r1["names"]), seed=sd_)
        assert sorted(pf["positions"].cid) == sorted(T1.cid) and pf["log"]["no_slot"] == 0
    say("  double costs: same fills, fees x 2; 2x Reg-T financing equals the hand sum over each position's "
        "previous-close notional; in_position matches the holdings; S20 decides only at weeks' last sessions; "
        "portfolio_seeds shape; with a slot per name the book takes exactly the chained trades")


def _check_edges(say) -> None:
    """Regressions for review findings 5, 6, 8 and 9: share adjustments that chart_factor misses, runs without a
    signal, dead names judged on their own, and portfolio()'s input."""
    th = 1.0 / 3.0
    # ---- an unrecorded share adjustment: the chart close jumps +5% on day 3 while the total-return index does not
    P = np.array([(99, 100, 98, 99.5), (100, 101, 99.5, 100.5), (100.4, 101, 99.9, 100.6),
                  (100.5, 101.1, 100.3, 100.86), (100.7, 101.4, 100.5, 100.95)], float)
    chart = P.copy(); chart[3:] *= 1.05
    f = pd.DataFrame(chart, columns=OHLC, index=pd.bdate_range("2024-01-01", periods=5))
    f["tr"] = P[:, 3]
    g, _ = _normalise("X", f)
    assert g.attrs["n_share_adj_folded"] == 1 and np.allclose(g[OHLC].to_numpy(), 1.05 * P, rtol=1e-12)
    assert np.allclose(g["div"].to_numpy(), 0.0, atol=1e-12)
    oi, of, tr, *_ = _mech(g[OHLC], [0], 95.0 * 1.05, div=g["div"].to_numpy())
    assert oi[0, I_NTR] == 1 and abs(of[0, F_RET] - th * (100.95 / 100.0 - 1.0)) < 1e-12   # no add on the fake jump
    # a real cash dividend (q rising) is still credited, not folded
    f2 = f.copy(); f2[OHLC] = P; f2["tr"] = P[:, 3] * np.r_[1, 1, 1, 1.01, 1.01]
    g2, _ = _normalise("X", f2)
    assert g2.attrs["n_share_adj_folded"] == 0 and abs(g2["div"].iloc[3] - P[2, 3] * (1 - 1 / 1.01)) < 1e-12
    say("  a chart jump with no total-return move (negative implied dividend, a share adjustment chart_factor missed)"
        " is folded into the earlier chart OHLC: no fake add, P&L = the total return; a cash dividend is credited")
    # ---- runs without any signal: empty but well-typed outputs, and the book on them
    rng = np.random.default_rng(3)
    c = 50 * np.exp(np.cumsum(rng.normal(0.002, 0.02, 300)))
    o = np.r_[c[0], c[:-1]]
    fe = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99, "close": c},
                      index=pd.bdate_range("2010-01-04", periods=300))
    for win in (("2001-01-01", "2002-06-30"), ("2010-01-01", "2010-02-15")):
        r = stock_trades("A", StockCfg(), *win, ohlc=fe)
        assert len(r["trades"]) == 0 and len(r["tranches"]) == 0 and not r["fills_audit"]
        assert r["trades"].entry1_px.dtype == float and r["trades"].n_tranches.dtype == np.int64
        p = portfolio(r)
        assert (p["daily"].n_pos == 0).all() and len(p["positions"]) == 0
    # ---- dead names: a file ending before the sources' end is dead whether it runs alone or with others
    fd = fe.iloc[:200].copy(); fd.attrs.update(cost=0.0003, dead=True)
    fl = fe.copy(); fl.attrs.update(cost=0.0003, dead=False)
    r1 = stock_trades("D", StockCfg(), "2010-01-01", "2012-12-31", ohlc=fd)
    r2 = stock_trades("u", StockCfg(), "2010-01-01", "2012-12-31", ohlc={"D": fd, "L": fl})
    t1, t2 = r1["trades"], r2["trades"][r2["trades"].sym == "D"]
    assert len(t1) and t1.exit_reason.str.endswith("dead").iloc[-1] and \
        t1.exit_reason.tolist() == t2.exit_reason.tolist() and np.allclose(t1.fees, t2.fees)
    # ---- portfolio() takes the stock_trades result, not its trades (clear TypeError, not KeyError)
    for fn in (portfolio, portfolio_seeds):
        try:
            fn(r2["trades"])
            raise AssertionError("no TypeError")
        except TypeError:
            pass
    say("  runs with no signal return empty typed outputs (and an empty book); a dead name is closed at its last "
        "close alone as in a universe; portfolio(trades DataFrame) raises a TypeError naming stock_trades()")


def _perturb_after(data: dict, cut: pd.Timestamp) -> dict:
    """The look-ahead control's perturbation for a cut time inside session `cut` (after its open): every price
    after the cut x 1.5 (bars after the session entirely; the session's own close, high and low, its open kept),
    the total-return index likewise, so dividends before the cut are unchanged. The flat / close-only flags are
    data availability, not prices: they are taken from the unperturbed frame."""
    out = {}
    for s, f in data.items():
        g = f.copy()
        if "flat" not in g:
            g["flat"] = flat_flag(f)
        after = g.index > cut
        on = g.index == cut
        for k in ("open", "high", "low", "close", "tr"):
            g.loc[after, k] = g.loc[after, k] * 1.5
        if on.any():
            o = g.loc[on, "open"].to_numpy()
            g.loc[on, "close"] = g.loc[on, "close"] * 1.5
            g.loc[on, "tr"] = g.loc[on, "tr"] * 1.5
            g.loc[on, "high"] = np.maximum(o, g.loc[on, "high"].to_numpy() * 1.5)
            g.loc[on, "low"] = np.minimum(o, g.loc[on, "low"].to_numpy() * 1.5)
        g.attrs = dict(f.attrs)
        out[s] = g
    return out


def _make_close_only(f: pd.DataFrame, mask: np.ndarray) -> None:
    """Rewrite the rows of `mask` as close-only source rows in universe_pit_all's form (open = previous close,
    high / low = max / min(open, close)) and flag them (close_only), in place."""
    o, h, l, c = (f[k].to_numpy(float).copy() for k in OHLC)
    prev = np.r_[c[0], c[:-1]]
    o = np.where(mask, prev, o)
    f["open"] = o
    f["high"] = np.where(mask, np.maximum(o, c), h)
    f["low"] = np.where(mask, np.minimum(o, c), l)
    f["close_only"] = (f["close_only"].to_numpy(bool) if "close_only" in f else False) | mask


def _cut_minutes(rng, n: int, near_open: int) -> np.ndarray:
    """Random cut minutes after 09:30 New York inside the session (1..389), never on an hour boundary; the first
    `near_open` within 2 h of the open (the stock version's entry / exit window)."""
    bad = {30, 90, 150, 210, 270, 330}                       # 10:00, 11:00, ..., 15:00
    ok_all = np.array([m for m in range(1, 390) if m not in bad])
    ok_near = np.array([m for m in range(1, 120) if m not in bad])
    return np.r_[rng.choice(ok_near, near_open), rng.choice(ok_all, n - near_open)]


def _check_lookahead(say) -> None:
    """The look-ahead control on the stock engine: at >= 50 cut times inside sessions (random minutes, never on an
    hour boundary; >= 10 within 2 h of the open; >= 10 in 2025-06..2026-10; >= 10 on sessions where a flat or
    close-only bar carries a pending entry or an open position), every price after the cut is x 1.5 and every
    decision stamped before it must be unchanged: tranches (entries, adds, TP, exits, stops), each entry's S / TP /
    price, the fresh signals decided before it, and the 20-slot book's entries, sizes and equity (daily and weekly
    bars). The synthetic universe has dividends, exact flat bars and close-only rows in universe_pit_all's form
    (isolated, and CRSP-like runs). Regression for review findings 1-4."""
    rng = np.random.default_rng(5)
    base = _synthetic_universe(80, 1400, mu=0.0005, seed=21, sub=24, member_frac=0.7, end=END)
    for k, f in base.items():                               # quarterly dividends, flat bars, close-only rows
        n = len(f)
        q = np.ones(n)
        for d0 in range(int(rng.integers(20, 80)), n, 63):
            q[d0:] *= 1.0 + 0.004
        fl = rng.random(n) < 0.01
        for col in ("open", "high", "low"):
            f.loc[fl, col] = f.loc[fl, "close"]
        co = rng.random(n) < 0.02
        if rng.random() < 0.3:                              # a run of close-only sessions
            a = int(rng.integers(100, n - 40)); co[a:a + int(rng.integers(10, 30))] = True
        _make_close_only(f, co & ~fl)
        f["tr"] = f.close.to_numpy() * q
        f.attrs["cost"] = 0.0003
    cal = calendar(base)
    win = (cal[250], END)
    r0 = stock_trades("synthetic", StockCfg(), *win, ohlc=base)
    assert not r0["fills_audit"] and r0["log"]["close_only_rows"] > 0
    p0 = portfolio(r0)
    rw0 = stock_trades("synthetic", StockCfg(bars="1w"), *win, ohlc=base)
    # cut sessions: random; in 2025-06..2026-10; flat / close-only sessions with a pending entry or an open position
    pool = np.arange(300, len(cal) - 5)
    g_a = rng.choice(pool, 28, replace=False)
    recent = pool[(cal[pool] >= pd.Timestamp("2025-06-01")) & ~np.isin(pool, g_a)]
    g_b = rng.choice(recent, 12, replace=False)
    pend_e, pend_p = set(), set()
    for r in r0["cand"].itertuples():
        a = r0["arrs"][r.sym]
        fl = r0["data"][r.sym]["flat"].to_numpy(bool)       # the data's own flag
        for d in range(r.t + 1, r.e):                       # entry rolled past this flat session
            if fl[d]:
                pend_e.add(int(a["gidx"][d]))
        for d in range(r.e + 1, r.x + 1):                   # flat session inside a position
            if fl[d]:
                pend_p.add(int(a["gidx"][d]))
    taken = set(g_a) | set(g_b)
    ce = np.array(sorted(g for g in pend_e if 300 <= g < len(cal) - 5 and g not in taken))
    cp = np.array(sorted(g for g in pend_p if 300 <= g < len(cal) - 5 and g not in taken and g not in pend_e))
    n_e = min(6, len(ce))
    assert len(ce) + len(cp) >= 12 and len(cp) >= 12 - n_e
    g_c = np.r_[rng.choice(ce, n_e, replace=False), rng.choice(cp, 12 - n_e, replace=False)].astype(np.int64)
    g_all = np.r_[g_a, g_b, g_c]
    mins = _cut_minutes(rng, len(g_all), 14)
    rng.shuffle(mins)
    near = mins < 120
    assert len(g_all) >= 50 and near.sum() >= 10 and len(g_b) >= 10 and len(g_c) >= 10
    n_changed_late = 0
    for g_cut, mi in zip(g_all, mins):
        cut = cal[int(g_cut)]
        t_cut = (pd.Timestamp(cut) + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(minutes=int(mi))
                 ).tz_localize(NY).tz_convert("UTC")
        pert = _perturb_after(base, cut)
        for r_a, cfg in ((r0, StockCfg()), (rw0, StockCfg(bars="1w"))):
            r_b = stock_trades("synthetic", cfg, *win, ohlc=pert)
            assert not r_b["fills_audit"]
            ta, tb = r_a["tranches"], r_b["tranches"]
            cols = ["sym", "signal_day", "time", "px", "notional", "kind"]
            ka = ta[(ta.time < t_cut) & (ta.kind != "mark")].merge(r_a["trades"][["pos", "signal_day"]], on="pos")[cols]
            kb = tb[(tb.time < t_cut) & (tb.kind != "mark")].merge(r_b["trades"][["pos", "signal_day"]], on="pos")[cols]
            ka = ka.sort_values(["sym", "signal_day", "time", "kind"]).reset_index(drop=True)
            kb = kb.sort_values(["sym", "signal_day", "time", "kind"]).reset_index(drop=True)
            assert len(ka) == len(kb) and (ka.drop(columns=["px", "notional"]) == kb.drop(
                columns=["px", "notional"])).all().all() and np.allclose(ka.px, kb.px, rtol=1e-12) and \
                np.allclose(ka.notional, kb.notional, rtol=1e-12), (cut, mi, cfg)
            n_changed_late += int(len(ta[ta.kind != "mark"]) != len(tb[tb.kind != "mark"]))
            ea = r_a["trades"][r_a["trades"].entry1_time < t_cut][["sym", "signal_day", "S", "TP", "entry1_px"]]
            eb = r_b["trades"][r_b["trades"].entry1_time < t_cut][["sym", "signal_day", "S", "TP", "entry1_px"]]
            ea = ea.sort_values(["sym", "signal_day"]).reset_index(drop=True)
            eb = eb.sort_values(["sym", "signal_day"]).reset_index(drop=True)
            assert len(ea) == len(eb) and (ea.sym == eb.sym).all() and (ea.signal_day == eb.signal_day).all()
            assert np.allclose(ea[["S", "TP", "entry1_px"]].to_numpy(), eb[["S", "TP", "entry1_px"]].to_numpy(),
                               rtol=1e-12)
            sa = r_a["signals"][r_a["signals"].signal_day < cut][["sym", "signal_day"]].reset_index(drop=True)
            sb = r_b["signals"][r_b["signals"].signal_day < cut][["sym", "signal_day"]].reset_index(drop=True)
            assert sa.equals(sb), (cut, cfg)
            if cfg.bars == "1d":
                p1 = portfolio(r_b)
                gc = int(g_cut)
                qa = p0["positions"][p0["positions"].g_e <= gc][["sym", "signal_day", "M"]].reset_index(drop=True)
                qb = p1["positions"][p1["positions"].g_e <= gc][["sym", "signal_day", "M"]].reset_index(drop=True)
                assert len(qa) == len(qb) and (qa.sym == qb.sym).all() and (qa.signal_day == qb.signal_day).all()
                assert np.allclose(qa.M, qb.M, rtol=1e-12)
                da, db = p0["daily"].equity, p1["daily"].equity
                assert np.allclose(da[da.index < cut], db[db.index < cut], rtol=1e-12)
    assert n_changed_late > 0                                # the perturbation does bite after the cut
    say(f"  {len(g_all)} intra-session cut times ({int(near.sum())} within 2 h of the open, {len(g_b)} in "
        f"2025-06..2026-10, {len(g_c)} on flat or close-only sessions carrying a pending entry or an open position; "
        f"random minutes, none on an hour; no weekend sessions exist for stocks), synthetic universe with "
        f"{r0['log']['close_only_rows']:,} close-only rows in universe_pit_all's form and "
        f"{r0['log']['flat_rows'] - r0['log']['close_only_rows']:,} exact flat bars; prices after each cut x 1.5 "
        f"(daily and weekly bars): every tranche stamped before the cut, every entry's S / TP / price, the signals "
        f"decided before it, and the book's entries, sizes and equity before it are unchanged (later fills changed "
        f"in {n_changed_late} of {2 * len(g_all)} runs)")


def _close_only_hits(res: dict) -> dict:
    """Counts of fills (other than the flat-bar stop at the close and the dead-name close), entries and signals that
    land on a source-flagged close-only row (each must be 0) and of flat-bar stops on them."""
    data = res["data"]
    Tk = res["tranches"]
    flat_stop = (Tk.kind == "stop") & (Tk.phase == "close")
    out = {"fills": 0, "entries": 0, "signals": 0, "flat_stops_on_close_only": 0}
    for key, frame, col in (("fills", Tk[(Tk.kind != "mark") & ~flat_stop & (Tk.kind != "dead")], "date"),
                            ("flat_stops_on_close_only", Tk[flat_stop], "date"),
                            ("entries", res["trades"], "entry1_date"), ("signals", res["signals"], "signal_day")):
        for s_, g in frame.groupby("sym"):
            co = data[s_]["close_only"]
            out[key] += int(co.reindex(pd.DatetimeIndex(g[col])).fillna(False).astype(bool).sum())
    return out


def _check_real(say) -> None:
    t0 = time.time()
    mem = universe_data("members")
    t_load = time.time() - t0
    n_co = int(sum(f.close_only.sum() for f in mem.values()))
    n_fl = int(sum(f.flat.sum() for f in mem.values()))
    assert n_co > 600_000                                   # raw_pit close-only rows of the members (615,018)
    t1 = time.time()
    res = stock_trades("members", StockCfg(), START, END)
    t_sim = time.time() - t1
    L = res["log"]
    assert not res["fills_audit"], res["fills_audit"][:5]
    T = res["trades"]
    assert T.member.all() and (pd.DatetimeIndex(T.entry1_date) >= pd.Timestamp(START)).all()
    hits = _close_only_hits(res)
    assert hits["fills"] == 0 and hits["entries"] == 0 and hits["signals"] == 0, hits
    say(f"  members: {len(mem):,} names loaded in {t_load:.0f}s ({n_co:,} close-only source rows flagged from raw_pit,"
        f" {n_fl:,} flat rows in all); primary window: {L['signals']:,} signals, {L['candidates_entered']:,} entered "
        f"candidates, {L['trades']:,} trades, {L['tranches']:,} tranches; simulated in {t_sim:.0f}s; fill audit empty;"
        f" no signal, entry or fill on a close-only row (flat-bar stops there: {hits['flat_stops_on_close_only']}); "
        f"OHLC rows repaired: {L['ohlc_repaired']}; share adjustments folded {L['share_adj_folded']}, implied "
        f"dividends > 10% of the prior close (kept, data caveat) {L['div_days_gt10pct']}")
    say(f"    chain status: {L['chain_status']}")
    say(f"    deferred {L['deferred_entries']}, rolled {L['rolled_entries']}, ATH-only {L['atH_only_trades']}, gap "
        f"stops {L['gap_stops']}, flat-bar stops {L['flat_bar_stops']}, dead closes {L['dead_closes']}, open at "
        f"end {L['open_at_end']}, cancelled adds {L['adds_cancelled']}")
    # a dead member run on its own is still dead (regression: review finding 6)
    dd = T[T.exit_reason.str.endswith("dead")].head(3)
    assert len(dd)
    for t in dd.itertuples():
        u = stock_trades(t.sym, StockCfg(), START, END)["trades"]
        u = u[u.signal_day == t.signal_day].iloc[0]
        assert u.exit_reason == t.exit_reason and u.exit_date == t.exit_date and abs(u.fees - t.fees) < 1e-15
    say(f"    dead names run alone ({', '.join(dd.sym)}): same dead close, exit date and costs as in the universe run")
    t2 = time.time()
    p = portfolio(res)
    t_p = time.time() - t2
    d = p["daily"]
    assert d.n_pos.max() <= 20 and (d.notional <= d.equity * (1 + 1e-9)).all()
    say(f"    20-slot portfolio pass: {t_p:.1f}s; {len(d):,} sessions, {p['log']['positions']:,} positions, max "
        f"{d.n_pos.max()} open, max gross {d.gross_lev.max():.3f}x, M capped {p['log']['M_capped']}")
    t3 = time.time()
    b = benchmark_ew_members(START, END, mem)
    say(f"    EW members benchmark: {time.time() - t3:.1f}s, {len(b):,} sessions, members per session "
        f"{b.n.min()}-{b.n.max()} (same calendar as the book: {b.index.equals(d.index)})")
    t4 = time.time()
    rb = random_entry_book(res, p)
    tw = rb["twins"]
    for s_, g in tw.groupby("sym"):                          # twins enter only on non-flat, non-close-only opens
        a = res["arrs"][s_]
        loc = np.searchsorted(a["gidx"], g.g_e.to_numpy())
        assert not a["flat"][loc].any() and not a["close_only"][loc].any()
    say(f"    matched random-entry book: {time.time() - t4:.1f}s, {rb['log']['twins']:,} twins (none enters on a flat or "
        f"close-only session)")
    t5 = time.time()
    r96 = stock_trades("members", StockCfg(), *WINDOWS["1996-2000"])
    h96 = _close_only_hits(r96)
    assert not r96["fills_audit"] and h96["fills"] == 0 and h96["entries"] == 0 and h96["signals"] == 0, h96
    say(f"    1996-2000 window: {r96['log']['trades']:,} trades in {time.time() - t5:.0f}s; fill audit empty; no "
        f"signal, entry or fill on a close-only row (flat-bar stops there: {h96['flat_stops_on_close_only']})")
    t6 = time.time()
    rw = stock_trades("members", StockCfg(bars="1w"), START, END)
    hw = _close_only_hits(rw)
    assert not rw["fills_audit"] and hw["fills"] == 0 and hw["entries"] == 0, hw
    say(f"    S20 weekly: {rw['log']['trades']:,} trades in {time.time() - t6:.0f}s; fill audit empty; no entry or fill "
        f"on a close-only row")
    for which in ("etfs", "user"):
        t7 = time.time()
        r = stock_trades(which, StockCfg(), START, END)
        assert not r["fills_audit"]
        assert all(r["data"][s_].attrs.get("close_only_dropped", 0) == 0 for s_ in r["names"])
        cnt = r["trades"].groupby("sym").size().to_dict()
        say(f"    {which}: {r['log']['trades']} trades ({cnt}) in {time.time() - t7:.1f}s; fill audit empty; no "
            f"close-only source row (none dropped)")
    for sym, a_, b_ in (("COIN", "2001-01-01", "2013-12-31"), ("HOOD", *WINDOWS["1996-2000"]),
                        ("CRCL", "2025-07-01", "2025-09-30")):
        r = stock_trades(sym, StockCfg(), a_, b_)
        assert len(r["trades"]) == 0 and len(portfolio(r)["daily"]) >= 0
    say("    runs without a signal (COIN 2001-2013, HOOD 1996-2000, CRCL 2025Q3): empty outputs, no error")
    etf = universe_data("etfs")
    be = benchmark_ew_etfs(START, END, etf)
    for s_, f in etf.items():                                # each ETF earns its first return on its 61st session
        one = benchmark_ew_etfs("1990-01-01", END, {s_: f})
        assert one.index[one.n.to_numpy() > 0][0] == f.index[WARMUP], s_
    say(f"    EW ETFs benchmark: {len(be):,} sessions, ETFs per session {be.n.min()}-{be.n.max()}; each ETF joins on its "
        f"61st raw_pit session")


def selftest() -> None:
    t0 = time.time()

    def say(s):
        print(s, flush=True)

    say("mechanics on hand-built daily paths (known fills)")
    _check_mechanics(say)
    say("indicators and signal definition")
    _check_indicators(say)
    say("martingale and drift controls (synthetic)")
    res = _check_martingale(say)
    say("portfolio slot accounting, seeds, ranking (synthetic)")
    _check_portfolio(say, res)
    say("matched random-entry book (synthetic)")
    _check_random_book(say, res)
    say("benchmarks (toy universe)")
    _check_benchmark(say)
    say("variants: double costs, 2x financing, S20 weekly, in_position, seeds (synthetic)")
    _check_variants(say)
    say("edges: share adjustments, empty runs, dead names alone, portfolio input (synthetic)")
    _check_edges(say)
    say("look-ahead (synthetic, the control's perturbation)")
    _check_lookahead(say)
    say("real data: mechanics and timing only (no strategy return is computed for display)")
    _check_real(say)
    say(f"selftest passed in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "selftest":
        selftest()
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}")
