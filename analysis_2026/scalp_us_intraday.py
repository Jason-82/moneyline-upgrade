"""
Scalping study, Part C (intraday "buy at the bid, sell at the ask" on Robinhood 5-minute bars) and Part E's
intraday ORB leg. Pre-registered in analysis_2026/SCALPING_PREREG.md (frozen 2026-10-18), sections "Part C"
and "Part E / Intraday leg". The pre-registration is the specification.

    python3 -m analysis_2026.scalp_us_intraday --tests       # unit tests (EDGE vs the bidask copy, clock, engine)
    python3 -m analysis_2026.scalp_us_intraday --controls    # Control (i) Roll market (4 bands + one-cent case) and
                                                             #   (ii) within-session shuffle (panel, else pilot names)
    python3 -m analysis_2026.scalp_us_intraday --smoke       # C1 on the 6 pilot names: plumbing + speed (no P&L shown)
    python3 -m analysis_2026.scalp_us_intraday --run         # primary cells, reported tables, 1-minute and 15-second
                                                             #   reruns, B3/B4 confirmation share
    python3 -m analysis_2026.scalp_us_intraday --events      # Part E intraday ORB leg (exploratory)
    python3 -m analysis_2026.scalp_us_intraday --iex         # Control (iii) IEX validation (streams 5 TOPS days)
    (--pilot forces the pilot names in --controls; --workers N for --iex)

Data (gitignored, data/scalping/rh/): panel_c.csv (ticker, band_at_draw, draw_order[, s15]); m5_none.parquet,
m1_none.parquet, s15_none.parquet (unadjusted bars from rh_bars: symbol, begins_at UTC, open, high, low, close,
volume, interpolated, session, interval); daily_split.parquet / daily_none.parquet (point-in-time bands, ADV60,
sigma, Part B's daily s and the closing-quote model M); events.csv + events_m5_none.parquet (Part E leg);
universe.csv (the 2026-10-16 closing NBBO, Control (iii)). Pilot fall-backs: data/scalping/rh_pilot/intraday/*.json
and the pilot-40 daily CSV. The closing-quote model's coefficients come from results_scalping/B/cost_model.csv
when Part B fitted it on B-R; otherwise they are refitted here with Part B's own code (scalp_us_daily).

Outputs: analysis_2026/results_scalping/C/
  --run       primary_cells.csv (the 4 C1 cells), cell_report.csv (activity, per-trade bp, exits, markouts, capital,
              Sharpe, tax, SPY, orders/day, months of record, no-edge level), sensitivities.csv (T_max 12, latency,
              m = 0/1/2, $10k, IBKR fee, C1-open/-close, range trades, $1-3 stocks, spread/vol terciles, halves),
              illusion.csv, markouts.csv, by_halfhour.csv, rerun_1min.csv, rerun_15s.csv, b34_confirmation.csv,
              summary.txt; data/scalping/C/units.parquet (every stock-session, every variant) and trades_primary.parquet
  --controls  controls_i.csv (+ _params, + _diagnostics: exit decomposition and variants that are NOT the control),
              controls_ii.csv, summary_controls.txt
  --events    e_orb.csv, e_orb_no_edge.csv (the ORB engine on the Roll market), data/scalping/C/e_orb_trades.parquet
  --iex       controls_iii_iex.csv (IEX extracts cached under data/scalping/C/iex/)
primary_cells.csv holds no verdict: Holm over all 36 tests is applied by scalp_report.py. Columns cond_* are PASS
conditions 2-6 plus the Control (i) cap (cond_control_i); an empty cond_* could not be evaluated and counts as not
met. force_inconclusive = True (with force_reason) when PASS condition 6's sign check fails or cannot be evaluated
("If not, the verdict is INCONCLUSIVE") or when Control (i) failed or is missing ("capped at INCONCLUSIVE"); either
rules out PASS and NO EDGE, as scalp_report.py applies it. --run always computes Controls (i)/(ii) on the panel first
(cond_control_i and the no-edge level are read from them).

------------------------------------------------------------------------------------------------- the rule
Clock: bars labelled by start time (UTC -> America/New_York); regular session 09:30-16:00 (13:00 on early-close
days), 78 five-minute clock bars; a decision at the close of the bar starting tau is made at tau + 5 min.
Interpolated bars (no trade) stay on the clock and never fill. C1, long only, one position per stock:
  buy   when flat, at the closes of bars starting 09:40..15:25 post B = floor_cent(last trade x (1 - s/2)),
        re-posted at every close; it fills in the next bar only if that bar's low is a whole cent and
        low <= B - $0.01, at B, size min(remaining, 25% x bar $ volume x f), f = (B - low)/(high - low);
        $2,000 orders, a partly filled buy is not topped up.
  sell  from the bar after the fill, A = ceil_cent(B (1 + s)); fills if high is a whole cent >= A + $0.01, at A,
        at most 25% x bar $ volume x f, f = (high - A)/(high - low); the remainder stays offered.
  exit  from T_max = 6 bars after the fill (the limit is checked first in that bar) the remainder is sold at
        each bar's close x (1 - m s/2), at most 25% of the bar's $ volume; whatever is left at the close of the
        bar starting 15:50 is sold at that close x (1 - m s - 0.5 sigma_d sqrt(remainder / ADV60)).
  s     = max(s_id, M_i,d-1), floored at $0.01 / P; s_id = median per-session EDGE over the previous 20
        sessions (no-trade bars NaN, sessions with >= 10 traded bars), Part B's daily s if < 5 qualify.
  fees  SEC $0 to 2026-04-03, then $20.60/$M on sales > $500; TAF $0.000195/sh (cap $9.79) on sales > 50 shares
        through 2026-09-30, then $0. IBKR-like $0.0045/share round trip as a sensitivity.
Primary cells C1-L1..L4: stock-sessions with point-in-time band k and s x P >= $0.03; mean net P&L per
stock-session at m = 1.5, two-way clustered (stock, ISO week), Student t at G - 1 df. Edge for NO EDGE: net
P&L per $ bought (sum/sum, two-way clustered delta method) against E = +5 bp.

------------------------------------------------------------------------------------------------- Implementation choices
Where the pre-registration is silent or ambiguous, the reading less likely to give a false PASS was taken
(where neither is, the most literal one). None was changed after seeing a result.
 C1  Sessions and clock. Session dates and bar slots come from the ET start time. A bar whose start is not on
     the interval grid or lies outside 09:30-close is dropped (counted in summary.txt). Early closes:
     NYSE's 13:00 days for 2023-2026 plus any session whose latest bar (any name) starts at 12:55. On an
     early-close day the end-of-day clock times move with the close: last buy post at close - 35 min (bar
     start), final exit at the bar starting close - 10 min. A traded bar = not interpolated and volume > 0
     (a non-interpolated zero-volume bar is treated as a no-trade bar).
 C2  "Last trade" = the close of the most recent traded bar at that resolution, carried across sessions and
     converted across splits with Part B's daily divisor KK = split-adjusted / unadjusted close; before the
     first traded bar in the data it is the previous unadjusted daily close. P (tick floor and the 3-tick
     filter) = the previous session's unadjusted daily close in the session's share basis. s is fixed for the
     session (s_id, M and the floor use data to d-1).
 C3  s_id window = the previous 20 exchange sessions (the literal reading, under which "fewer than 5 qualify"
     can bind); a qualifying session needs >= 10 traded bars and a finite EDGE. EDGE = bidask 2.1.0 logic
     with NaN bars (checked against the pilot's verified copy in --tests). "Part B's daily s as of d-1" and
     "M_i,d-1" are Part B's SPR and M (scalp_us_daily.spread, B-R: no R_y) indexed at d, i.e. computed with
     data through d-1.
 C4  Orders are one-bar orders: an order decided at the close of bar t is live only in bar t+1 (t+2 under the
     one-bar latency variant) and is then replaced or, after the last post, lapses. Bar $ volume = close x
     volume. Shares are whole (floor); a fill of < 1 share is no fill. f = 1 on one-price bars.
 C5  The sell limit is live from the bar after the fill through the T_max bar; from the T_max bar on (after
     the limit check) the remainder is sold at the closes, and the limit is not checked again. The limit and
     forced sales of one bar share one 25%-of-bar-$-volume cap. In the bar starting 15:50 the order is:
     limit, forced 25% sale, then the remainder rule. The 15:50 remainder is sold even if that bar did not
     trade (at the carried last trade), with no volume cap. sigma_d = Part B's sigma20 (20-day SD of daily
     returns, data to d-1; 60-day fallback); ADV60 floored at $1,000; remainder in $; no D_k depth credit.
 C6  One-bar latency variant: every order decided at the close of bar t (buy post, sell limit, forced sale)
     acts from bar t+2, so the whole exit schedule shifts one bar. The buy order posted while flat at the
     close of t-1 stays live in bar t+1 even if the order of bar t filled (it cannot be cancelled in time); it
     can fill up to the $2,000 position cap. T_max and A are set by the first fill.
 C7  Fees per position (all its sales together): SEC if the position's sale proceeds > $500, TAF if its
     shares sold > 50 (cap once per position). Robinhood's thresholds are per order; aggregating per
     position charges fees at least as often. The trade date is the session date.
 C8  Halves: sessions before the window's median session (index n//2 of the sorted window sessions) vs the
     rest. Drop-worst = the calendar session whose removal lowers the cell mean most. Calendar week = ISO.
 C9  PASS condition 6: the 1-minute rerun uses the same s and units and the same clock times (posts at the
     closes 09:45..15:30, T_max 30 minutes, final exit at the close 15:55); overlapping sessions = sessions in
     both the 5-minute window and the 1-minute data. cond_1min = sign(1-min mean over the overlap) equals
     sign(5-min primary mean) and sign(5-min mean over the same overlap) (C21); a mismatch (including a zero
     1-min mean) or missing 1-minute data sets force_inconclusive.
 C10 Control (i) "PASS" = one-sided p < 0.05/36 (the strictest Holm step) and conditions 2-6 on the synthetic
     panel. Print sides are i.i.d. 50/50 (Roll's model; strict alternation would hand C1 a bounce it does not
     get). The mid is a random walk at the band's median 5-minute volatility = the median over stock-sessions
     with >= 10 traded bars of the SD of clock-bar log returns of the last trade (this includes the bounce, so
     it errs high). Print rate: the band's median share of traded 5-minute bars after keeping 40%; daily $
     volume = the band's geometric mid ($87k / $274k / $866k / $2.74M); price = the pilot band median ($4.6 /
     $6.0 / $11.9 / $16.7); 30 names x (80 burn-in + 160) sessions; daily bars from all prints, 5- and
     1-minute bars from the kept 40%. A failed control caps the band at INCONCLUSIVE: cond_control_i = False and
     force_inconclusive = True (C22: neither PASS nor NO EDGE, superseding the first version, which left NO EDGE
     possible).
 C11 Control (ii): the 78 clock bars of each session (traded and no-trade) are permuted with
     default_rng(20261018) in unit order; s, P and the carried last trade stay those of the real data.
 C12 Illusion baselines: touch = whole-cent low <= B (high >= A) with f = 1; any-extreme = the trade-through rule
     with sub-penny extremes allowed (f as in C1).
 C13 C1-open / C1-close: posts at the closes 09:35..10:00 / 15:30..15:50 (the bars starting 09:30..09:55 /
     15:25..15:45); same exits (C1-close always reaches the 15:50 remainder rule). "Entry" for P&L by half-hour
     = the bar of the first buy fill. $1-3 stocks = P in [1, 3). Spread-to-volatility terciles: s / sigma_5m,
     sigma_5m = median of the per-session values (C10) over the previous 20 sessions (>= 5 qualifying), cut
     points within each band's primary units.
 C14 15-second rerun: the panel names with 15-second bars; same clock times (T_max 120 bars); ratios of buy
     fills and of net P&L to the 5-minute run over the same units.
 C15 Capital = the peak over (session, bar) of the summed cost basis held across the cell's stocks; annual
     figures scale by 252 / window sessions; months of record for t >= 2 as in Part B: 12 (2 sigma_a / mu)^2.
 C16 Control (iii) IEX: the 5 days are 2026-10-16 (the only day with a saved closing NBBO) plus 4 window sessions
     drawn with default_rng(20261018); on 2026-10-16 "matched the NBBO" = IEX bid and ask equal to the
     scanner's closing NBBO (universe.csv); on the 4 other days no historical NBBO exists, so the proxy is: IEX
     two-sided at 15:59:59 ET, bid <= official close <= ask, and IEX spread <= max($0.01, 1.5 x M x close)
     rounded up to the cent. Queue: an order at the IEX bid joins behind the displayed size; displayed-size
     drops shrink the queue ahead only below it; an order above the IEX bid has no queue; IEX trades at our
     price consume the queue ahead and then fill us only while our price is the displayed IEX bid; trades
     strictly through our price fill us; cross and extended-hours trades are ignored. Forced and final exits
     are priced at the IEX mid with the bar rule's costs ("marked to IEX's mid").
 C17 Part E ORB: opening range = traded 5-minute bars starting 09:30..09:55; entries on the closes of bars
     starting 10:00..15:45; Q = $10k capped at 25% of the entry bar's $ volume (whole shares); exit at the first
     traded close below the range low, else at the 15:50 bar's close (carried last trade); s = Part B's daily
     s as of d-1 (no 20-session intraday history exists for event names); sell fees as in C. The rule as
     written has no impact term; a Y = 0.5 impact variant (Part B's leg cost at Q, both legs) is also shown.
     Its no-edge level (General rules) is the ORB rule on every stock-session of Control (i)'s Roll markets.
     Note: the registered event filter (day volume >= 5 x median) uses the event day's full volume, known only at
     its close, so the ORB leg is conditioned on same-day future information; it is exploratory and is reported
     as such, not changed.
 C18 Reruns at 1 minute / 15 seconds use only sessions from the first session with a real bar at that resolution
     (Robinhood returns flat interpolated bars outside retention). B3/B4 confirmation: Part B's own B-R fills
     (scalp_us_daily.b3_trades / b4_trades on the prepared B-R panel) for panel names with fill days in the window;
     "confirmed" = some traded 5-minute bar of the fill day with a whole-cent low <= limit - $0.01.
Review fixes (adversarial code review, before any primary result was computed):
 C19 The common eligibility rule ("Common definitions ... Parts B, C, D, E") now applies: a stock-session is in a cell
     only with >= 40 real daily bars in the 60-day window and P >= $1 (both data to d-1). "Volume > 0 on the signal
     and entry days" is not applied: Part C says sessions with no real bar count as zero, and the entry session's
     volume is not known at the decision.
 C20 A bar with a missing or non-positive price is not a traded bar (none exist in the pulled data; a NaN close would
     otherwise make that stock-session's net NaN and silently drop it from the cell).
 C21 PASS condition 6 also compares with the 5-minute mean over the same overlapping sessions (C9).
 C22 Control (i): a band passes only if both of its cases (median spread and one cent) pass; a failed or missing
     control and a failed or not evaluable 1-minute sign check set force_inconclusive (neither PASS nor NO EDGE),
     matching scalp_report.py. A positive control guards against false negatives, so its failure must also block
     NO EDGE; the first version blocked PASS only.
 C23 --run always recomputes Controls (i)/(ii) on the panel (current bars and cost model) before the primary
     statistics, so a stale controls_i.csv (e.g. the first version's 6-pilot-name parameters) is never used.
 C24 The panel (and Part E's events) are restricted to the B-R universe as Part B builds it: the scan's keep flag and
     exclusion rules (b)-(d) on the scan's and the listing files' names. panel_c.csv was drawn from the scan's keep
     list without rules (b)-(d) and holds two rule-(b) names (NGL "Common Units", RLX "right to receive"), which
     are dropped (L4 keeps 28 names). Dropping names that fall outside the universe from a uniform random draw
     leaves a uniform random sample of the universe, but not the exact default_rng(20261018) draw from it
     (a deviation; a redraw would need new intraday pulls).
 C25 events.csv is read with keep_default_na=False (the ticker "NA" was read as NaN).
Deviations from the pre-registration (also written to summary.txt): intraday bars are unadjusted only
(all C rules are within-session and s is relative); the window start moves to the first available session if
retention has rolled past 2026-03-02; Control (iii)'s NBBO match is proxied on 4 of the 5 days (C16); the panel is
the registered draw minus its names outside the B-R universe (C24).
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from numba import njit, prange

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026 import scalp_us_daily as sd  # noqa: E402
from analysis_2026.scalp_stats import ALPHA, N_PRIMARY, cluster2_t, drop_worst, holm, ratio_cluster2  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SC = ROOT / "data" / "scalping"
RH = SC / "rh"
OUT = ROOT / "analysis_2026" / "results_scalping" / "C"
TDIR = SC / "C"
SCRATCH = Path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad")
PILOT_INTRADAY = SC / "rh_pilot" / "intraday"
NY = "America/New_York"
WIN0, WIN1 = "2026-03-02", "2026-10-16"
FULL, HALF = 23400, 12600                         # session lengths in seconds after 09:30
EARLY_CLOSE = {"2023-07-03", "2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28",
               "2025-12-24", "2026-11-27", "2026-12-24"}
Q0, QBIG = 2000.0, 10000.0
M0 = 1.5
TMAX_S, TMAX12_S = 1800, 3600                     # T_max = 6 / 12 five-minute bars, in seconds
E_THRESH = 0.0005                                 # +5 bp net per $ bought
IBKR = 0.0045                                     # $ per share, round trip
BANDS = ["L1", "L2", "L3", "L4"]
BAND_PRICE = {1: 4.6, 2: 6.0, 3: 11.9, 4: 16.7}   # pilot band medians (us_data_feasibility.md 2.2)
BAND_QSPREAD = {1: 0.0197, 2: 0.0097, 3: 0.0038, 4: 0.0021}
BAND_ADV_MID = {1: math.sqrt(50e3 * 150e3), 2: math.sqrt(150e3 * 500e3), 3: math.sqrt(500e3 * 1.5e6),
                4: math.sqrt(1.5e6 * 5e6)}
PILOT_BUCKET = {"FSI": 1, "SCOR": 1, "ALTI": 2, "MED": 3, "CRON": 4, "EGY": 4}
ROUTE = "a local bot, or re-quoting by hand every 5 minutes"
STAT_NAME = "mean net P&L per stock-session in $ (C1, $2,000 orders, m=1.5, T_max=6 bars, s x P >= $0.03)"
EDGE_NAME = "net P&L per $ bought (sum net / sum bought, two-way clustered delta method)"
UF = ["net", "bought", "gross", "n_fills", "n_pos", "lim_usd", "forced_exec", "final_exec", "fees", "ibkr",
      "n_posts", "n_sell_orders", "impact", "shares"]
PF = ["unit", "j0", "B", "A", "shares", "cost", "lim_sh", "lim_usd", "forced_sh", "forced_raw", "forced_exec",
      "final_sh", "final_raw", "final_exec", "fees", "net", "j_exit", "mk1", "mk3", "mk6", "ibkr", "n_fills",
      "impact"]
_UI = {k: i for i, k in enumerate(UF)}


def say_factory(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "w")

    def say(*a):
        s = " ".join(str(x) for x in a)
        print(s, flush=True); fh.write(s + "\n"); fh.flush()
    return say


# ============================================================================ bars and the session clock

def load_bars(path, symbols=None) -> pd.DataFrame:
    """Robinhood bars (rh_bars parquet, or a directory of raw JSON) -> regular-session rows."""
    path = Path(path)
    if path.is_dir():
        from analysis_2026.rh_bars import parse_dir
        d = parse_dir(str(path))
    else:
        d = pd.read_parquet(path)
    if symbols is not None:
        d = d[d.symbol.isin(set(symbols))]
    if "session" in d:
        d = d[d.session.isna() | d.session.isin(["reg", "regular"])]
    return d.reset_index(drop=True)


def trim_flat(d: pd.DataFrame) -> pd.DataFrame:
    """Drop sessions before the first one with a real (non-interpolated, traded) bar in any name: Robinhood returns
    flat interpolated bars for requests outside retention."""
    real = ~d.interpolated.astype(bool) & (d.volume > 0)
    if not real.any():
        return d.iloc[:0]
    day = d.begins_at.dt.tz_convert(NY).dt.normalize()
    return d[day >= day[real].min()].reset_index(drop=True)


def wcent(x):
    """Whole-cent price: |100x - round(100x)| < 1e-6."""
    x = np.asarray(x, float)
    return np.abs(100 * x - np.round(100 * x)) < 1e-6


def build_clock(d: pd.DataFrame, dt: int, symbols=None):
    """Dense (symbol, session, slot) arrays on the regular-session clock of interval dt seconds."""
    et = d.begins_at.dt.tz_convert(NY)
    date = et.dt.tz_localize(None).dt.normalize()
    sec = (et.dt.hour * 3600 + et.dt.minute * 60 + et.dt.second - 34200).to_numpy()
    dates = pd.DatetimeIndex(np.sort(date.unique()))
    mx = pd.Series(sec).groupby(date.to_numpy()).max()
    L = np.array([HALF if (str(x.date()) in EARLY_CLOSE or mx.get(x, 0) == HALF - dt) else FULL for x in dates])
    syms = np.array(sorted(d.symbol.unique()) if symbols is None else list(symbols), dtype=object)
    si = pd.Index(syms).get_indexer(d.symbol)
    di = dates.get_indexer(date)
    Ld = L[di]
    keep = (si >= 0) & (sec >= 0) & (sec < Ld) & (sec % dt == 0)
    N, D, K = len(syms), len(dates), FULL // dt
    ck = SimpleNamespace(syms=syms, dates=dates, L=L, NB=L // dt, dt=dt, K=K, N=N, D=D,
                         n_dropped=int((~keep & (si >= 0)).sum()))
    i, j, k = si[keep], di[keep], sec[keep] // dt
    px = d[["open", "high", "low", "close"]].to_numpy(float)[keep]
    tr = (~d.interpolated.to_numpy(bool)[keep]) & (d.volume.to_numpy(float)[keep] > 0) \
        & np.isfinite(px).all(axis=1) & (px > 0).all(axis=1)      # review fix C20: a bar with a missing price is untraded
    for a, col in (("O", "open"), ("H", "high"), ("L_", "low"), ("C", "close")):
        arr = np.full((N, D, K), np.nan)
        v = d[col].to_numpy(float)[keep]
        arr[i[tr], j[tr], k[tr]] = v[tr]
        setattr(ck, a, arr)
    ck.V = np.zeros((N, D, K)); ck.V[i[tr], j[tr], k[tr]] = d.volume.to_numpy(float)[keep][tr]
    ck.TR = np.zeros((N, D, K), bool); ck.TR[i[tr], j[tr], k[tr]] = True
    ck.WCL = np.zeros((N, D, K), bool); ck.WCH = np.zeros((N, D, K), bool)
    ck.WCL[ck.TR] = wcent(ck.L_[ck.TR]); ck.WCH[ck.TR] = wcent(ck.H[ck.TR])
    return ck


# ============================================================================ EDGE with NaN bars, session stats

@njit(cache=True)
def _edge_nan(o, h, l, c):
    """EDGE (Ardia-Guidotti-Kroencke 2024), bidask 2.1.0 logic with NaN (no-trade) bars; log prices in."""
    n = len(o)
    if n < 3:
        return np.nan
    sr1 = 0.0; nr1 = 0; sr3 = 0.0; nr3 = 0; sr5 = 0.0; nr5 = 0
    st = 0.0; nt = 0; so1 = 0.0; no1 = 0; so2 = 0.0; no2 = 0; sc1 = 0.0; nc1 = 0; sc2 = 0.0; nc2 = 0
    for j in range(1, n):
        m = 0.5 * (h[j] + l[j])
        r1 = m - o[j]; r3 = m - c[j - 1]; r5 = o[j] - c[j - 1]
        if r1 == r1:
            sr1 += r1; nr1 += 1
        if r3 == r3:
            sr3 += r3; nr3 += 1
        if r5 == r5:
            sr5 += r5; nr5 += 1
        if h[j] == h[j] and l[j] == l[j] and c[j - 1] == c[j - 1]:
            tau = 1.0 if (h[j] != l[j] or l[j] != c[j - 1]) else 0.0
            st += tau; nt += 1
            if o[j] == o[j]:
                so1 += tau * (1.0 if o[j] != h[j] else 0.0); no1 += 1
                so2 += tau * (1.0 if o[j] != l[j] else 0.0); no2 += 1
            if h[j - 1] == h[j - 1]:
                sc1 += tau * (1.0 if c[j - 1] != h[j - 1] else 0.0); nc1 += 1
            if l[j - 1] == l[j - 1]:
                sc2 += tau * (1.0 if c[j - 1] != l[j - 1] else 0.0); nc2 += 1
    if st < 2 or nt == 0:
        return np.nan
    pt = st / nt
    po = (so1 / no1 if no1 else np.nan) + (so2 / no2 if no2 else np.nan)
    pc = (sc1 / nc1 if nc1 else np.nan) + (sc2 / nc2 if nc2 else np.nan)
    if po == 0 or pc == 0 or not (po == po) or not (pc == pc):
        return np.nan
    k1 = (sr1 / nr1) / pt if nr1 else np.nan
    k3 = (sr3 / nr3) / pt if nr3 else np.nan
    k5 = (sr5 / nr5) / pt if nr5 else np.nan
    e1 = 0.0; e2 = 0.0; q1 = 0.0; q2 = 0.0; n1 = 0; n2 = 0
    for j in range(1, n):
        if not (h[j] == h[j] and l[j] == l[j] and c[j - 1] == c[j - 1]):
            continue
        tau = 1.0 if (h[j] != l[j] or l[j] != c[j - 1]) else 0.0
        m = 0.5 * (h[j] + l[j]); m1 = 0.5 * (h[j - 1] + l[j - 1])
        r1 = m - o[j]; r2 = o[j] - m1; r3 = m - c[j - 1]; r4 = c[j - 1] - m1; r5 = o[j] - c[j - 1]
        d1 = r1 - k1 * tau; d3 = r3 - k3 * tau; d5 = r5 - k5 * tau
        x1 = -4.0 / po * d1 * r2 - 4.0 / pc * d3 * r4
        x2 = -4.0 / po * d1 * r5 - 4.0 / pc * d5 * r4
        if x1 == x1:
            e1 += x1; q1 += x1 * x1; n1 += 1
        if x2 == x2:
            e2 += x2; q2 += x2 * x2; n2 += 1
    if n1 == 0 or n2 == 0:
        return np.nan
    e1 /= n1; e2 /= n2
    v1 = q1 / n1 - e1 * e1; v2 = q2 / n2 - e2 * e2
    vt = v1 + v2
    s2 = (v2 * e1 + v1 * e2) / vt if vt > 0 else 0.5 * (e1 + e2)
    return math.sqrt(abs(s2))


@njit(parallel=True, cache=True)
def _session_stats(O, H, L, C, TR, NB):
    """Per (symbol, session): EDGE on the clock bars (NaN no-trade bars), traded-bar count, SD of clock-bar log
    returns of the carried last trade (from the first traded bar), last traded close."""
    N, D, K = C.shape
    E = np.full((N, D), np.nan); NT = np.zeros((N, D), np.int64); VOL = np.full((N, D), np.nan)
    LC = np.full((N, D), np.nan)
    for i in prange(N):
        o = np.empty(K); h = np.empty(K); l = np.empty(K); c = np.empty(K)
        for d in range(D):
            nb = NB[d]
            nt = 0; first = -1; lt = np.nan
            for k in range(nb):
                if TR[i, d, k]:
                    o[k] = math.log(O[i, d, k]); h[k] = math.log(H[i, d, k]); l[k] = math.log(L[i, d, k])
                    c[k] = math.log(C[i, d, k]); nt += 1; lt = C[i, d, k]
                    if first < 0:
                        first = k
                else:
                    o[k] = np.nan; h[k] = np.nan; l[k] = np.nan; c[k] = np.nan
            NT[i, d] = nt; LC[i, d] = lt
            if nt >= 2:
                E[i, d] = _edge_nan(o[:nb], h[:nb], l[:nb], c[:nb])
            if nt >= 2 and nb - first >= 3:
                prev = c[first]; s = 0.0; ss = 0.0; m = 0
                for k in range(first + 1, nb):
                    cur = c[k] if c[k] == c[k] else prev
                    r = cur - prev; s += r; ss += r * r; m += 1; prev = cur
                mu = s / m
                VOL[i, d] = math.sqrt(max(ss / m - mu * mu, 0.0) * m / (m - 1))
    return E, NT, VOL, LC


# ============================================================================ daily side (Part B's own code)

def cost_model(say=print):
    """Closing-quote model coefficients: Part B's cost_model.csv when fitted on B-R, else refitted here with
    scalp_us_daily on B-R (same code), else the stand-in in cost_model.csv (flagged)."""
    f = OUT.parent / "B" / "cost_model.csv"
    cf, flag = None, ""
    if f.exists():
        c = pd.read_csv(f).set_index("item").value
        if str(c.get("fit_sample", "")) == "B-R":
            cf = {k: float(c[k]) for k in ("b0", "b1", "b2", "b3", "S")}; flag = "Part B cost_model.csv (B-R)"
    if cf is None and (RH / "daily_split.parquet").exists() and (RH / "daily_none.parquet").exists():
        BR = sd.load_br()
        sd.trailing(BR)
        c = sd.fit_cost_model(BR)
        cf = {k: float(c[k]) for k in ("b0", "b1", "b2", "b3", "S")}
        flag = f"refitted here on B-R with scalp_us_daily.fit_cost_model (n_fit {c['n_fit']}); Part B's file was a stand-in"
        del BR
    if cf is None:
        if not f.exists():
            raise RuntimeError("no cost model: run Part B (scalp_us_daily) or pull the B-R daily bars first")
        c = pd.read_csv(f).set_index("item").value
        cf = {k: float(c[k]) for k in ("b0", "b1", "b2", "b3", "S")}; flag = "STAND-IN: " + str(c.get("fit_sample"))
    say(f"cost model: {flag}; b = {cf['b0']:.3f}, {cf['b1']:.3f}, {cf['b2']:.3f}, {cf['b3']:.3f}, S = {cf['S']:.3f}")
    return cf, flag


def _daily_long_br(symbols):
    """Unadjusted + split-adjusted Robinhood daily bars -> Part B's long frame, and the B-R calendar."""
    s = sd._rh_daily(RH / "daily_split.parquet")
    u = sd._rh_daily(RH / "daily_none.parquet")
    dates = pd.DatetimeIndex(np.sort(s.loc[~s.interpolated.astype(bool), "date"].unique()))
    s = s[s.ticker.isin(set(symbols))]; u = u[u.ticker.isin(set(symbols))]
    m = s.merge(u[["ticker", "date", "open", "high", "low", "close", "interpolated"]], on=["ticker", "date"],
                suffixes=("", "_u"), how="left")
    return _long_from_merged(m), dates


def _long_from_merged(m):
    m = m[~m.interpolated.fillna(False).astype(bool)].copy()
    for c in ("open", "high", "low", "close"):
        m[c + "_u"] = m[c + "_u"].fillna(m[c])
    m["kk"] = m.close / m.close_u
    m["sv"] = m.volume.astype(float)
    m["wcl"] = wcent(m.low_u.to_numpy()); m["wch"] = wcent(m.high_u.to_numpy())
    m["fret"] = 1.0
    return m


def daily_panel(m, dates, cf, name):
    """Part B's panel, trailing statistics and spread (B-R: no R_y) for the given names; plus the forward-filled
    divisor KKff, the index of the last real bar <= t (LR) and P_prev (previous unadjusted close in t's basis)."""
    P = sd.panel_from_long(m, dates, name, "BR", (str(dates[0].date()), str(dates[-1].date())))
    sd.finish_panel(P, grid=False)
    sd.trailing(P)
    sd.spread(P, cf, None)
    N, T = P.N, P.T
    LR = np.full((N, T), -1, np.int64)
    idx = np.where(P.real, np.arange(T)[None, :], -1)
    LR[:] = np.maximum.accumulate(idx, axis=1)
    rows = np.arange(N)[:, None]
    KKr = np.where(LR >= 0, P.KK[rows, np.maximum(LR, 0)], np.nan).astype(float)
    P.KKff = KKr
    P.LR = LR
    prevLR = np.full((N, T), -1, np.int64); prevLR[:, 1:] = LR[:, :-1]
    Cprev = np.where(prevLR >= 0, P.C[rows, np.maximum(prevLR, 0)].astype(float), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        P.PPREV = Cprev / KKr
    P.tix = {t: k for k, t in enumerate(P.tickers)}
    return P


def daily_for(symbols, cf, source="BR"):
    if source == "BR":
        m, dates = _daily_long_br(symbols)
    else:                                                   # the 40 pilot names, split-adjusted only
        d = pd.read_csv(SC / "rh_pilot" / "daily" / "pilot40_daily_2023-07_2026-10.csv", parse_dates=["date"])
        d = d.rename(columns={"symbol": "ticker"})
        dates = pd.DatetimeIndex(np.sort(d.loc[~d.interpolated.astype(bool), "date"].unique()))
        d = d[d.ticker.isin(set(symbols))]
        for c in ("open", "high", "low", "close"):
            d[c + "_u"] = d[c]
        m = _long_from_merged(d)
    return daily_panel(m, dates, cf, source)


def fees_for(dates):
    d = pd.DatetimeIndex(dates)
    sec = np.where(d <= "2026-04-03", 0.0, 20.6e-6)
    taf = np.where(d <= "2026-09-30", 0.000195, 0.0)
    cap = np.where(d <= "2026-09-30", 9.79, 0.0)
    return sec, taf, cap


# ============================================================================ units (stock-sessions)

def carried_last(ck, LC, P, rows, dmap):
    """[N, T] last traded close before each session at the clock's resolution, in the session's share basis
    (Part B's daily divisor KK converts across splits); NaN before the first traded bar in the data."""
    LT = np.full((ck.N, P.T), np.nan)
    for a in range(ck.N):
        r = rows[a]
        if r < 0:
            continue
        lastp, lastt = np.nan, -1
        for d in range(ck.D):
            t = dmap[d]
            if t < 0:
                continue
            if lastt >= 0:
                k1, k0 = P.KKff[r, t], P.KKff[r, lastt]
                LT[a, t] = lastp * k0 / k1 if (k1 > 0 and k0 > 0) else lastp
            if np.isfinite(LC[a, d]):
                lastp, lastt = LC[a, d], t
    return LT


def make_units(ck, P, win=(WIN0, WIN1), say=print):
    """One row per (panel stock, exchange session in the window): band, s, P, inputs of the engine."""
    st = _session_stats(ck.O, ck.H, ck.L_, ck.C, ck.TR, ck.NB)
    E5, NT5, VOL5, LC5 = st
    ck.E5, ck.NT5, ck.VOL5, ck.LC5 = E5, NT5, VOL5, LC5
    dmap = P.dates.get_indexer(ck.dates)
    if (dmap < 0).any():
        say(f"  {int((dmap < 0).sum())} intraday sessions not in the daily calendar (dropped)")
    rows = np.array([P.tix.get(s, -1) for s in ck.syms])
    T = P.T
    # per-session EDGE / vol on the daily calendar, then the trailing 20-session medians
    Eq = np.full((T, ck.N), np.nan); Vq = np.full((T, ck.N), np.nan)
    ok = dmap >= 0
    qual = (NT5 >= 10) & np.isfinite(E5)
    Eq[dmap[ok]] = np.where(qual, E5, np.nan)[:, ok].T
    Vq[dmap[ok]] = np.where(NT5 >= 10, VOL5, np.nan)[:, ok].T
    SID = pd.DataFrame(Eq).shift(1).rolling(20, min_periods=5).median().to_numpy().T      # [N, T]
    NQ = pd.DataFrame(Eq).shift(1).rolling(20, min_periods=1).count().to_numpy().T
    V20 = pd.DataFrame(Vq).shift(1).rolling(20, min_periods=5).median().to_numpy().T
    first_real = int(np.where(ck.TR.any(axis=(0, 2)))[0].min()) if ck.TR.any() else 0
    w0 = max(pd.Timestamp(win[0]), ck.dates[first_real]); w1 = min(pd.Timestamp(win[1]), ck.dates[-1])
    wt = np.where((P.dates >= w0) & (P.dates <= w1))[0]
    nodaily = [s for s, r in zip(ck.syms, rows) if r < 0]
    if nodaily:
        say(f"  names without daily bars (dropped): {nodaily}")
    LT = carried_last(ck, LC5, P, rows, dmap)
    cidx = np.full(T, -1); cidx[dmap[ok]] = np.where(ok)[0]
    out = [(sym, a, int(cidx[t]), rows[a], t, LT[a, t]) for a, sym in enumerate(ck.syms) if rows[a] >= 0 for t in wt]
    U = pd.DataFrame(out, columns=["sym", "ic", "dc", "row", "t", "lt0"])
    r, t = U.row.to_numpy(), U.t.to_numpy()
    U["date"] = P.dates[t]
    U["band"] = P.BAND[r, t].astype(int)
    U["s_id5"] = SID[U.ic.to_numpy(), t]
    U["n_qual"] = NQ[U.ic.to_numpy(), t]
    U["s_daily"] = P.SPR[r, t].astype(float)
    U["M"] = P.M[r, t].astype(float)
    U["P"] = P.PPREV[r, t]
    U["s_src"] = np.where(np.isfinite(U.s_id5), "5min", "daily")
    s_id = np.where(np.isfinite(U.s_id5), U.s_id5, U.s_daily)
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.fmax(s_id, U.M.to_numpy())
        s = np.fmax(s, 0.01 / U.P.to_numpy())
    U["s_id"] = s_id
    U["s"] = s
    U["tick3"] = (U.s * U.P >= 0.03 - 1e-9)
    U["nr"] = P.NR[r, t].astype(int)                                  # real daily bars in the 60-day window, to d-1
    U["elig"] = (U.nr >= 40) & (U.P >= 1)                             # review fix C19 (common eligibility rule)
    U["lt0"] = U.lt0.fillna(U.P)
    sig = P.SIG20[r, t].astype(float)
    sig = np.where(np.isfinite(sig), sig, P.SIG60[r, t])
    U["sig"] = np.nan_to_num(sig, nan=0.0)
    U["adv"] = np.nan_to_num(P.ADV[r, t].astype(float), nan=0.0)
    U["vol5_20"] = V20[U.ic.to_numpy(), t]
    U["sec"], U["taf"], U["tafcap"] = fees_for(U.date)
    iso = U.date.dt.isocalendar()
    U["week"] = iso.year.astype(str) + "-" + iso.week.astype(str).str.zfill(2)
    sess = np.sort(U.date.unique())
    med = sess[len(sess) // 2]
    U["half"] = np.where(U.date < med, 1, 2)
    U["L"] = np.where(U.dc >= 0, ck.L[np.maximum(U.dc, 0)], FULL)
    U.attrs.update(w0=str(pd.Timestamp(w0).date()), w1=str(pd.Timestamp(w1).date()), n_sessions=len(sess),
                   median_session=str(pd.Timestamp(med).date()))
    return U


# ============================================================================ the C1 engine

@njit(cache=True)
def _fc(x):
    return np.floor(x * 100.0 + 1e-7) / 100.0


@njit(cache=True)
def _cc(x):
    return np.ceil(x * 100.0 - 1e-7) / 100.0


@njit(parallel=True, cache=True)
def _c1(O, H, L, C, V, TR, WCL, WCH, NB, POST0, POST1, FX, S, LT0, SIG, ADV, SEC, TAF, TAFCAP,
        Q, TMAX, LAT, M, TOUCH, ANYEXT, IBKR_, REC, OFF):
    """C1 on U units x K clock bars. Returns per-unit sums (UF), held cost basis per bar, position records (PF)."""
    U, K = C.shape
    R = np.zeros((U, 14))
    HELD = np.zeros((U, K), np.float32)
    nrec = OFF[U] if REC else 1
    PR = np.full((max(nrec, 1), 23), np.nan)
    for u in prange(U):
        nb = NB[u]
        s = S[u]
        if nb <= 0 or not (s > 0):
            continue
        lts = np.empty(K)
        lt = LT0[u]
        for k in range(nb):
            if TR[u, k]:
                lt = C[u, k]
            lts[k] = lt
        bpx = np.full(K + 3, np.nan)
        hold = 0.0; cost = 0.0; bought = 0.0; sh_b = 0.0; j0 = -1; B0 = 0.0; A = 0.0; nf = 0
        lsh = 0.0; lusd = 0.0; fsh = 0.0; fraw = 0.0; fex = 0.0; xsh = 0.0; xraw = 0.0; xex = 0.0; imp = 0.0
        nso = 0; npos = 0; jlast = -1
        for j in range(nb):
            tr = TR[u, j]
            dv = C[u, j] * V[u, j] if tr else 0.0
            sold_bar = 0.0
            # 1. resting buy (one-bar order)
            bp = bpx[j]
            if tr and bp == bp and bp > 0 and bought < Q - 1e-9:
                lo = L[u, j]; hi = H[u, j]
                if TOUCH:
                    ok = WCL[u, j] and lo <= bp + 1e-9
                elif ANYEXT:
                    ok = lo * 100.0 <= bp * 100.0 - 1.0 + 1e-6
                else:
                    ok = WCL[u, j] and lo * 100.0 <= bp * 100.0 - 1.0 + 1e-6
                if ok:
                    f = 1.0
                    if not TOUCH and hi - lo > 1e-9:
                        f = min(max((bp - lo) / (hi - lo), 0.0), 1.0)
                    amt = min(Q - bought, 0.25 * dv * f)
                    sh = np.floor(amt / bp + 1e-9)
                    if sh >= 1:
                        if j0 < 0:
                            j0 = j; B0 = bp; A = _cc(bp * (1.0 + s)); nf = 0
                            lsh = 0.0; lusd = 0.0; fsh = 0.0; fraw = 0.0; fex = 0.0; xsh = 0.0; xraw = 0.0
                            xex = 0.0; imp = 0.0; cost = 0.0; sh_b = 0.0; nso = 1
                        hold += sh; cost += sh * bp; bought += sh * bp; sh_b += sh; nf += 1
            # 2. resting sell limit, from the bar after the fill through the T_max bar
            if hold > 0 and tr and j >= j0 + 1 + LAT and j <= j0 + TMAX + LAT:
                lo = L[u, j]; hi = H[u, j]
                if TOUCH:
                    ok = WCH[u, j] and hi >= A - 1e-9
                elif ANYEXT:
                    ok = hi * 100.0 >= A * 100.0 + 1.0 - 1e-6
                else:
                    ok = WCH[u, j] and hi * 100.0 >= A * 100.0 + 1.0 - 1e-6
                if ok:
                    f = 1.0
                    if not TOUCH and hi - lo > 1e-9:
                        f = min(max((hi - A) / (hi - lo), 0.0), 1.0)
                    sh = min(hold, np.floor(0.25 * dv * f / A + 1e-9))
                    if sh >= 1:
                        hold -= sh; lsh += sh; lusd += sh * A; sold_bar += sh * A; jlast = j
            # 3. forced sale at the close, from the T_max bar on
            if hold > 0 and tr and j >= j0 + TMAX + LAT:
                c = C[u, j]
                cap = 0.25 * dv - sold_bar
                if cap > 0:
                    sh = min(hold, np.floor(cap / c + 1e-9))
                    if sh >= 1:
                        hold -= sh; fsh += sh; fraw += sh * c; fex += sh * c * (1.0 - M * s / 2.0)
                        sold_bar += sh * c; nso += 1; jlast = j
            # 4. the 15:50-bar remainder rule
            if hold > 0 and j == FX[u]:
                px = lts[j]
                rem = hold * px
                ii = 0.5 * SIG[u] * math.sqrt(rem / max(ADV[u], 1000.0))
                xsh += hold; xraw += rem; xex += rem * (1.0 - M * s - ii); imp += rem * ii
                hold = 0.0; nso += 1; jlast = j
            # 5. a closed position is booked
            if j0 >= 0 and hold <= 0:
                proc = lusd + fex + xex
                fees = (SEC[u] * proc if proc > 500.0 else 0.0) + (min(TAF[u] * sh_b, TAFCAP[u]) if sh_b > 50 else 0.0)
                net = proc - cost - fees
                R[u, 0] += net; R[u, 1] += cost; R[u, 2] += lusd + fraw + xraw - cost; R[u, 3] += nf
                R[u, 4] += 1; R[u, 5] += lusd; R[u, 6] += fex; R[u, 7] += xex; R[u, 8] += fees
                R[u, 9] += IBKR_ * sh_b; R[u, 11] += nso; R[u, 12] += imp; R[u, 13] += sh_b
                if REC:
                    w = OFF[u] + npos
                    PR[w, 0] = u; PR[w, 1] = j0; PR[w, 2] = B0; PR[w, 3] = A; PR[w, 4] = sh_b; PR[w, 5] = cost
                    PR[w, 6] = lsh; PR[w, 7] = lusd; PR[w, 8] = fsh; PR[w, 9] = fraw; PR[w, 10] = fex
                    PR[w, 11] = xsh; PR[w, 12] = xraw; PR[w, 13] = xex; PR[w, 14] = fees; PR[w, 15] = net
                    PR[w, 16] = jlast
                    for q, kk in ((17, 1), (18, 3), (19, 6)):
                        if j0 + kk < nb:
                            PR[w, q] = lts[j0 + kk] / B0 - 1.0
                    PR[w, 20] = IBKR_ * sh_b; PR[w, 21] = nf; PR[w, 22] = imp
                npos += 1
                j0 = -1; bought = 0.0; cost = 0.0; sh_b = 0.0
            # 6. decisions at the close of bar j: a new buy when flat, inside the posting window
            if j0 < 0 and j >= POST0[u] and j <= POST1[u] and j + 1 + LAT <= FX[u] and lts[j] == lts[j] and lts[j] > 0:
                bpx[j + 1 + LAT] = _fc(lts[j] * (1.0 - s / 2.0))
                R[u, 10] += 1
            if hold > 0 and sh_b > 0:
                HELD[u, j] = cost * hold / sh_b
    return R, HELD, PR


def _slots(Lsec, dt, kind="main"):
    """Posting window [post0, post1] (bar indices whose close is a decision time) and the final-exit bar."""
    Lsec = np.asarray(Lsec)
    fx = (Lsec - 300) // dt - 1
    if kind == "open":
        return np.full(len(Lsec), 300 // dt - 1), np.full(len(Lsec), 1800 // dt - 1), fx
    if kind == "close":
        return (Lsec - 1800) // dt - 1, (Lsec - 600) // dt - 1, fx
    return np.full(len(Lsec), 900 // dt - 1), (Lsec - 1800) // dt - 1, fx


def gather(ck, U, shuffle_seed=None):
    """Engine inputs [U, K] for the units' (clock symbol, clock session); units without bars get NB = 0."""
    ic, dc = U.ic.to_numpy(), U.dc.to_numpy()
    has = dc >= 0
    K = ck.K
    X = {}
    for a in ("O", "H", "L_", "C", "V", "TR", "WCL", "WCH"):
        src = getattr(ck, a)
        arr = np.zeros((len(U), K), src.dtype) if src.dtype == bool else np.full((len(U), K), np.nan if a != "V" else 0.0)
        arr[has] = src[ic[has], dc[has]]
        X[a] = arr
    X["NB"] = np.where(has, ck.NB[np.maximum(dc, 0)], 0).astype(np.int64)
    if shuffle_seed is not None:                       # Control (ii): permute each session's clock bars
        rng = np.random.default_rng(shuffle_seed)
        for u in np.where(has)[0]:
            nb = X["NB"][u]
            p = rng.permutation(nb)
            for a in ("O", "H", "L_", "C", "V", "TR", "WCL", "WCH"):
                X[a][u, :nb] = X[a][u, p]
    return X


def run_c1(ck, U, X=None, Q=Q0, tmax_s=TMAX_S, lat=0, m=M0, touch=False, anyext=False, kind="main", rec=False,
           sel=None):
    """Run C1 at the clock's resolution on the units; returns (per-unit DataFrame, positions DataFrame | None,
    held cost [U, K])."""
    X = gather(ck, U) if X is None else X
    dt = ck.dt
    p0, p1, fx = _slots(U.L.to_numpy(), dt, kind)
    S = U.s.to_numpy(float).copy()
    if sel is not None:
        S[~sel] = np.nan
    args = (X["O"], X["H"], X["L_"], X["C"], X["V"], X["TR"], X["WCL"], X["WCH"], X["NB"], p0.astype(np.int64),
            p1.astype(np.int64), fx.astype(np.int64), S, U.lt0.to_numpy(float), U.sig.to_numpy(float),
            U.adv.to_numpy(float), U.sec.to_numpy(float), U.taf.to_numpy(float), U.tafcap.to_numpy(float),
            float(Q), int(tmax_s // dt), int(lat), float(m), bool(touch), bool(anyext), IBKR)
    off = np.zeros(len(U) + 1, np.int64)
    R, HELD, _ = _c1(*args, False, off)
    pos = None
    if rec:
        off[1:] = np.cumsum(R[:, _UI["n_pos"]].astype(np.int64))
        R, HELD, PRr = _c1(*args, True, off)
        pos = pd.DataFrame(PRr[:off[-1]], columns=PF)
        pos["unit"] = pos.unit.astype(int); pos["j0"] = pos.j0.astype(int)
    res = pd.DataFrame(R, columns=UF)
    return res, pos, HELD


# ============================================================================ statistics

def cstats(x, bought, sym, week, nf):
    """Mean per unit (two-way clustered), the edge per $ bought, activity."""
    x = np.asarray(x, float); bought = np.asarray(bought, float)
    if len(x) < 3:
        return dict(estimate=np.nan, se=np.nan, t=np.nan, p_one_sided=np.nan, df=np.nan, edge_estimate=np.nan,
                    edge_se=np.nan, edge_df=np.nan, n_units=len(x), share_active=np.nan, mean_active=np.nan)
    m, se, t, p, dfree = cluster2_t(x, sym, week)
    if bought.sum() > 0:
        R, rse, rdf = ratio_cluster2(x, bought, sym, week)
    else:
        R, rse, rdf = np.nan, np.nan, np.nan
    act = np.asarray(nf) > 0
    return dict(estimate=m, se=se, t=t, p_one_sided=p, df=dfree, edge_estimate=R, edge_se=rse, edge_df=rdf,
                n_units=len(x), share_active=float(act.mean()), mean_active=float(x[act].mean()) if act.any() else np.nan)


def stats_of(U, res, mask):
    return cstats(res.net.to_numpy()[mask], res.bought.to_numpy()[mask], U.sym.to_numpy()[mask],
                  U.week.to_numpy()[mask], res.n_fills.to_numpy()[mask])


def capital_stats(U, res, HELD, mask):
    """Peak capital (summed cost basis across stocks at any bar of a session), annual net, Sharpe, tax, months."""
    if mask.sum() == 0:
        return {}
    d = U.date.to_numpy()[mask]
    held = HELD[mask].astype(float)
    sess, inv = np.unique(d, return_inverse=True)
    tot = np.zeros((len(sess), HELD.shape[1]))
    np.add.at(tot, inv, held)
    peak = float(tot.max())
    allsess = np.sort(U.date.unique())
    pnl = pd.Series(res.net.to_numpy()[mask]).groupby(d).sum().reindex(allsess, fill_value=0.0).to_numpy()
    n = len(allsess)
    yrs = n / 252
    out = {"peak_capital": peak, "net_usd_per_year": pnl.sum() / yrs}
    if peak > 0:
        dr = pnl / peak
        sdv = dr.std(ddof=1)
        ann = pnl.sum() / yrs / peak
        out |= {"ann_net_on_peak": ann, "sharpe": dr.mean() / sdv * np.sqrt(252) if sdv > 0 else np.nan,
                "ann_after_tax_35": ann * 0.65 if ann > 0 else ann, "daily_pnl_sd_on_peak": sdv}
        for mu in (0.10, 0.25, 0.50):
            out[f"months_t2_at_{int(mu * 100)}pct"] = 12 * (2 * sdv * np.sqrt(252) / mu) ** 2
    return out


def spy_window(U):
    dates = pd.DatetimeIndex(np.sort(U.date.unique()))
    return sd.spy_after_tax(None, SimpleNamespace(kind="BR", dates=dates, s0=0, s1=len(dates) - 1))


# ============================================================================ the analysis (Part C)

def variant_runs(ck, U, X, quick=False):
    """All 5-minute variants, per-unit results keyed by name."""
    runs = {}
    t0 = time.time()
    runs["primary"], pos, held = run_c1(ck, U, X, rec=True)
    runs["tmax12"], _, _ = run_c1(ck, U, X, tmax_s=TMAX12_S)
    runs["latency"], _, _ = run_c1(ck, U, X, lat=1)
    if not quick:
        for mm in (0.0, 1.0, 2.0):
            runs[f"m{mm:g}"], _, _ = run_c1(ck, U, X, m=mm)
        runs["q10k"], _, _ = run_c1(ck, U, X, Q=QBIG)
        runs["touch"], _, _ = run_c1(ck, U, X, touch=True)
        runs["anyext"], _, _ = run_c1(ck, U, X, anyext=True)
        runs["open"], _, _ = run_c1(ck, U, X, kind="open")
        runs["close"], _, _ = run_c1(ck, U, X, kind="close")
    ibk = runs["primary"].copy(); ibk["net"] = ibk.net - ibk.ibkr
    runs["ibkr"] = ibk
    return runs, pos, held, time.time() - t0


def band_masks(U, tick3=True):
    b = U.band.to_numpy()
    el = U.elig.to_numpy(bool) if "elig" in U else np.ones(len(U), bool)
    t3 = U.tick3.to_numpy(bool) & np.isfinite(U.s.to_numpy())
    return {k: (b == k) & el & (t3 if tick3 else (~t3 & np.isfinite(U.s.to_numpy()))) for k in (1, 2, 3, 4)}


def _true(v):
    """True only for a real boolean True (NaN = not evaluable = not met)."""
    return isinstance(v, (bool, np.bool_)) and bool(v)


def rerun_other(ck_o, U5, P):
    """1-minute / 15-second rerun on the 5-minute units that overlap the finer data (same s, P, band, clock
    times); the carried last trade is taken at the finer resolution where it exists, else the 5-minute one."""
    sym_ok = U5.sym.isin(set(ck_o.syms)).to_numpy()
    real_d = ck_o.dates[ck_o.TR.any(axis=(0, 2))]                # flat interpolated days outside retention excluded
    d_ok = (U5.date.isin(set(ck_o.dates)) & (U5.date >= real_d.min()) & (U5.date <= real_d.max())).to_numpy() \
        if len(real_d) else np.zeros(len(U5), bool)
    Uo = U5[sym_ok & d_ok].copy()
    Uo["ic"] = pd.Index(ck_o.syms).get_indexer(Uo.sym)
    Uo["dc"] = ck_o.dates.get_indexer(Uo.date)
    LC = _session_stats(ck_o.O, ck_o.H, ck_o.L_, ck_o.C, ck_o.TR, ck_o.NB)[3]
    rows = np.array([P.tix.get(s, -1) for s in ck_o.syms])
    LT = carried_last(ck_o, LC, P, rows, P.dates.get_indexer(ck_o.dates))
    lt = LT[Uo.ic.to_numpy(), Uo.t.to_numpy()]
    Uo["lt0"] = np.where(np.isfinite(lt), lt, Uo.lt0.to_numpy())
    Uo["L"] = np.where(Uo.dc >= 0, ck_o.L[np.maximum(Uo.dc, 0)], FULL)
    res, _, _ = run_c1(ck_o, Uo, rec=False)
    return Uo, res, np.where(sym_ok & d_ok)[0]


def analyze(ck5, U, P, say, out, tdir, ck1=None, ck15=None, write=True, ctrl_i=None, null_ii=None, b34=None,
            quick=False):
    """Primary cells, PASS conditions 2-6, and every reported table."""
    X = gather(ck5, U)
    runs, pos, held, secs = variant_runs(ck5, U, X, quick=quick)
    say(f"  5-minute variants: {len(runs)} runs on {len(U):,} stock-sessions in {secs:.1f}s")
    masks = band_masks(U)
    rerun1 = None
    if ck1 is not None:
        t1 = time.time()
        U1, r1, idx1 = rerun_other(ck1, U, P)
        rerun1 = (U1, r1, idx1)
        say(f"  1-minute rerun: {len(U1):,} overlapping stock-sessions in {time.time() - t1:.1f}s")
    rows, rep, sens = [], [], []
    prim = runs["primary"]
    spy = spy_window(U)
    for k in (1, 2, 3, 4):
        mk = masks[k]
        st = stats_of(U, prim, mk)
        cond, extra = {}, {}
        x = prim.net.to_numpy()
        h = U.half.to_numpy()
        h1 = x[mk & (h == 1)]; h2 = x[mk & (h == 2)]
        extra["half1"] = h1.mean() if len(h1) else np.nan; extra["half2"] = h2.mean() if len(h2) else np.nan
        cond["cond_halves"] = bool(len(h1) and len(h2) and extra["half1"] > 0 and extra["half2"] > 0)
        extra["tmax12_estimate"] = runs["tmax12"].net.to_numpy()[mk].mean() if mk.any() else np.nan
        cond["cond_tmax12"] = bool(extra["tmax12_estimate"] > 0)
        extra["latency_estimate"] = runs["latency"].net.to_numpy()[mk].mean() if mk.any() else np.nan
        cond["cond_latency"] = bool(extra["latency_estimate"] > 0)
        if mk.sum() > 1:
            dm, dmo = drop_worst(x[mk], U.date.to_numpy()[mk])
        else:
            dm, dmo = np.nan, None
        extra["dropsession_estimate"] = dm; extra["dropped_session"] = str(pd.Timestamp(dmo).date()) if dmo is not None else ""
        cond["cond_dropsession"] = bool(dm > 0)
        if rerun1 is not None:
            U1, r1, idx1 = rerun1
            m1k = mk[idx1]
            m1 = r1.net.to_numpy()[m1k].mean() if m1k.any() else np.nan
            m5o = x[idx1][m1k].mean() if m1k.any() else np.nan
            extra |= {"m1_estimate_overlap": m1, "m5_estimate_overlap": m5o, "n_units_1min": int(m1k.sum())}
            # review fix C21: the 1-minute sign must agree with the primary 5-minute sign AND with the 5-minute sign
            # on the same overlapping sessions (like for like); a zero or missing mean is a disagreement
            agree = bool(np.isfinite(m1) and m1 != 0 and np.isfinite(st["estimate"]) and np.isfinite(m5o)
                         and np.sign(m1) == np.sign(st["estimate"]) and np.sign(m1) == np.sign(m5o))
            cond["cond_1min"] = agree
        else:
            cond["cond_1min"] = np.nan
            extra |= {"m1_estimate_overlap": np.nan, "m5_estimate_overlap": np.nan, "n_units_1min": 0}
        if ctrl_i is not None:
            # review fix C22: the band's control is both of its cases (median spread and one cent)
            ci = ctrl_i[ctrl_i.band == f"L{k}"]
            cond["cond_control_i"] = bool(len(ci) >= 2 and ci["pass"].astype(bool).all()) if len(ci) else np.nan
        else:
            cond["cond_control_i"] = np.nan
        # review fix C22: a failed or missing positive control, or a failed / not evaluable 1-minute sign check, caps
        # the verdict at INCONCLUSIVE (neither PASS nor NO EDGE), as scalp_report.py applies it
        why = [n for n, c in (("1-minute sign check", cond["cond_1min"]), ("Control (i)", cond["cond_control_i"]))
               if not _true(c)]
        extra["force_inconclusive"] = bool(why)
        extra["force_reason"] = "; ".join(f"{n} {'not evaluable' if not isinstance(c, (bool, np.bool_)) else 'failed'}"
                                          for n, c in (("1-minute sign check", cond["cond_1min"]),
                                                       ("Control (i)", cond["cond_control_i"])) if n in why)
        if null_ii is not None:
            nk = null_ii[null_ii.band == f"L{k}"]
            extra["null_ii_estimate"] = float(nk.estimate.iloc[0]) if len(nk) else np.nan
        rows.append({"test_id": f"C1-L{k}", "part": "C", "statistic_name": STAT_NAME, "estimate": st["estimate"],
                     "se": st["se"], "df": st["df"], "t": st["t"], "p_one_sided": st["p_one_sided"],
                     "edge_name": EDGE_NAME, "edge_estimate": st["edge_estimate"], "edge_se": st["edge_se"],
                     "edge_df": st["edge_df"], "threshold_E": E_THRESH} | cond |
                    {"n_units": st["n_units"], "share_active": st["share_active"], "mean_active": st["mean_active"]}
                    | extra)
        # ---- reported for every primary cell
        pk = pos[mk[pos.unit.to_numpy()]] if pos is not None and len(pos) else pd.DataFrame(columns=PF)
        r = {"test_id": f"C1-L{k}", "n_units": st["n_units"], "share_active": st["share_active"],
             "mean_active": st["mean_active"], "n_positions": len(pk), "n_buy_fills": int(pk.n_fills.sum()) if len(pk) else 0,
             "per_trade_bp_tw": 1e4 * float((pk.net / pk.cost).mean()) if len(pk) else np.nan,
             "per_trade_bp_dw": 1e4 * float(pk.net.sum() / pk.cost.sum()) if len(pk) and pk.cost.sum() > 0 else np.nan,
             "gross_bp_dw": 1e4 * float((prim.gross.to_numpy()[mk]).sum() / max(prim.bought.to_numpy()[mk].sum(), 1e-9)),
             "fees_bp_dw": 1e4 * float(prim.fees.to_numpy()[mk].sum() / max(prim.bought.to_numpy()[mk].sum(), 1e-9)),
             "bought_usd_per_unit": float(prim.bought.to_numpy()[mk].mean()) if mk.any() else np.nan,
             "share_exit_limit": float((pk.lim_sh / pk.shares).mean()) if len(pk) else np.nan,
             "share_exit_forced": float((pk.forced_sh / pk.shares).mean()) if len(pk) else np.nan,
             "share_exit_final": float((pk.final_sh / pk.shares).mean()) if len(pk) else np.nan,
             "markout1_bp": 1e4 * np.nansum(pk.mk1 * pk.cost) / pk.cost[np.isfinite(pk.mk1)].sum() if len(pk) else np.nan,
             "markout3_bp": 1e4 * np.nansum(pk.mk3 * pk.cost) / pk.cost[np.isfinite(pk.mk3)].sum() if len(pk) else np.nan,
             "markout6_bp": 1e4 * np.nansum(pk.mk6 * pk.cost) / pk.cost[np.isfinite(pk.mk6)].sum() if len(pk) else np.nan,
             "posts_per_unit": float(prim.n_posts.to_numpy()[mk].mean()) if mk.any() else np.nan,
             "sell_orders_per_unit": float(prim.n_sell_orders.to_numpy()[mk].mean()) if mk.any() else np.nan,
             "orders_per_day": float(pd.Series(prim.n_posts.to_numpy()[mk] + prim.n_sell_orders.to_numpy()[mk])
                                     .groupby(U.date.to_numpy()[mk]).sum().mean()) if mk.any() else np.nan,
             "cancels_per_day": float(pd.Series(prim.n_posts.to_numpy()[mk]).groupby(U.date.to_numpy()[mk]).sum().mean())
             if mk.any() else np.nan,
             "route": ROUTE, "s_median": float(np.nanmedian(U.s.to_numpy()[mk])) if mk.any() else np.nan,
             "share_s_from_5min": float((U.s_src.to_numpy()[mk] == "5min").mean()) if mk.any() else np.nan}
        if ctrl_i is not None:
            ci = ctrl_i[(ctrl_i.band == f"L{k}") & (ctrl_i.case == "median spread")]
            if len(ci):
                r |= {"no_edge_level_control_i_usd": float(ci.estimate.iloc[0]),
                      "no_edge_level_control_i_bp_per_$": 1e4 * float(ci.edge_estimate.iloc[0])}
        r |= capital_stats(U, prim, held, mk) | spy
        rep.append(r)
        # ---- sensitivities and splits
        for v in runs:
            if v == "primary":
                continue
            sens.append({"variant": v, "band": f"L{k}", "subset": "s x P >= $0.03"} | stats_of(U, runs[v], mk))
        mr = band_masks(U, tick3=False)[k]
        sens.append({"variant": "range trades (1-2 ticks)", "band": f"L{k}", "subset": "s x P < $0.03"}
                    | stats_of(U, prim, mr))
        p13 = mk & (U.P.to_numpy() >= 1) & (U.P.to_numpy() < 3)
        sens.append({"variant": "$1-3 stocks", "band": f"L{k}", "subset": "s x P >= $0.03, P in [1,3)"}
                    | stats_of(U, prim, p13))
        allk = (U.band.to_numpy() == k) & np.isfinite(U.s.to_numpy()) & U.elig.to_numpy(bool)
        p13a = allk & (U.P.to_numpy() >= 1) & (U.P.to_numpy() < 3)
        sens.append({"variant": "$1-3 stocks", "band": f"L{k}", "subset": "all ticks, P in [1,3)"} | stats_of(U, prim, p13a))
        ratio = (U.s / U.vol5_20).to_numpy()
        okr = mk & np.isfinite(ratio)
        if okr.sum() >= 30:
            q1, q2 = np.quantile(ratio[okr], [1 / 3, 2 / 3])
            for j, (lo, hi) in enumerate(((-np.inf, q1), (q1, q2), (q2, np.inf))):
                mm = okr & (ratio > lo) & (ratio <= hi)
                sens.append({"variant": f"s/sigma_5m tercile {j + 1}", "band": f"L{k}",
                             "subset": f"ratio in ({lo:.3g}, {hi:.3g}]"} | stats_of(U, prim, mm))
        for hh in (1, 2):
            sens.append({"variant": f"half {hh}", "band": f"L{k}", "subset": "s x P >= $0.03"}
                        | stats_of(U, prim, mk & (U.half.to_numpy() == hh)))
    prim_df = pd.DataFrame(rows)
    rep_df = pd.DataFrame(rep)
    sens_df = pd.DataFrame(sens)
    # ---- illusion baselines
    ill = []
    for k in (1, 2, 3, 4):
        mk = masks[k]
        base = prim.n_fills.to_numpy()[mk].sum()
        for v in ("touch", "anyext"):
            if v not in runs:
                continue
            st = stats_of(U, runs[v], mk)
            nf = runs[v].n_fills.to_numpy()[mk].sum()
            ill.append({"baseline": {"touch": "touch fills", "anyext": "any-extreme (sub-penny counted)"}[v],
                        "band": f"L{k}", "n_buy_fills": int(nf), "n_buy_fills_primary": int(base),
                        "share_fills_added": (nf - base) / nf if nf > 0 else np.nan} | st)
    ill_df = pd.DataFrame(ill)
    # ---- markouts and P&L by half-hour of entry
    mko, hh = [], []
    if pos is not None and len(pos):
        pos = pos.copy()
        pos["band"] = U.band.to_numpy()[pos.unit]; pos["tick3"] = U.tick3.to_numpy()[pos.unit]
        pos["sym"] = U.sym.to_numpy()[pos.unit]; pos["date"] = U.date.to_numpy()[pos.unit]
        pos["entry_time"] = [f"{(570 + j * ck5.dt // 60) // 60:02d}:{(570 + j * ck5.dt // 60) % 60:02d}" for j in pos.j0]
        pos["halfhour"] = [f"{(570 + 30 * ((j * ck5.dt) // 1800)) // 60:02d}:{(570 + 30 * ((j * ck5.dt) // 1800)) % 60:02d}"
                           for j in pos.j0]
        pp = pos[pos.tick3.astype(bool) & pos.band.between(1, 4)]
        for k, g in pp.groupby("band"):
            row = {"band": f"L{k}", "n_positions": len(g)}
            for q in (1, 3, 6):
                c = g[f"mk{q}"]; w = g.cost[np.isfinite(c)]
                row[f"markout_{q}bar_bp"] = 1e4 * float((c[np.isfinite(c)] * w).sum() / w.sum()) if w.sum() > 0 else np.nan
            mko.append(row)
            for t, gh in g.groupby("halfhour"):
                hh.append({"band": f"L{k}", "entry_halfhour": t, "n_positions": len(gh), "net_usd": gh.net.sum(),
                           "bought_usd": gh.cost.sum(), "net_bp_dw": 1e4 * gh.net.sum() / gh.cost.sum()})
    mko_df, hh_df = pd.DataFrame(mko), pd.DataFrame(hh)
    # ---- 1-minute and 15-second reruns
    r1_df = pd.DataFrame()
    if rerun1 is not None:
        U1, r1, idx1 = rerun1
        rr = []
        for k in (1, 2, 3, 4):
            m1k = masks[k][idx1]
            rr.append({"band": f"L{k}", "resolution": "1-minute"} | stats_of(U1, r1, m1k)
                      | {"m5_same_units": prim.net.to_numpy()[idx1][m1k].mean() if m1k.any() else np.nan,
                         "fills_1m": int(r1.n_fills.to_numpy()[m1k].sum()),
                         "fills_5m": int(prim.n_fills.to_numpy()[idx1][m1k].sum())})
        r1_df = pd.DataFrame(rr)
    r15_df = pd.DataFrame()
    if ck15 is not None:
        t1 = time.time()
        U15, r15, idx15 = rerun_other(ck15, U, P)
        say(f"  15-second rerun: {len(U15):,} overlapping stock-sessions in {time.time() - t1:.1f}s")
        rr = []
        for k in (1, 2, 3, 4, 0):
            mkk = (np.any([masks[b] for b in (1, 2, 3, 4)], axis=0) if k == 0 else masks[k])[idx15]
            f15 = r15.n_fills.to_numpy()[mkk].sum(); f5 = prim.n_fills.to_numpy()[idx15][mkk].sum()
            p15 = r15.net.to_numpy()[mkk].sum(); p5 = prim.net.to_numpy()[idx15][mkk].sum()
            rr.append({"band": "pooled L1-L4" if k == 0 else f"L{k}", "n_units": int(mkk.sum()), "fills_15s": int(f15),
                       "fills_5m": int(f5), "fill_ratio_15s_to_5m": f15 / f5 if f5 else np.nan, "net_15s": p15,
                       "net_5m": p5, "pnl_ratio_15s_to_5m": p15 / p5 if p5 else np.nan})
        r15_df = pd.DataFrame(rr)
    if write:
        out.mkdir(parents=True, exist_ok=True); tdir.mkdir(parents=True, exist_ok=True)
        prim_df.to_csv(out / "primary_cells.csv", index=False)
        rep_df.to_csv(out / "cell_report.csv", index=False)
        sens_df.to_csv(out / "sensitivities.csv", index=False)
        ill_df.to_csv(out / "illusion.csv", index=False)
        mko_df.to_csv(out / "markouts.csv", index=False)
        hh_df.to_csv(out / "by_halfhour.csv", index=False)
        r1_df.to_csv(out / "rerun_1min.csv", index=False)
        r15_df.to_csv(out / "rerun_15s.csv", index=False)
        if b34 is not None:
            b34.to_csv(out / "b34_confirmation.csv", index=False)
        uu = U.drop(columns=["ic", "dc", "row"]).copy()
        for v, r in runs.items():
            uu[f"net_{v}"] = r.net.to_numpy()
            if v in ("q10k", "latency", "tmax12"):
                uu[f"bought_{v}"] = r.bought.to_numpy()
        uu["bought"] = prim.bought.to_numpy(); uu["n_fills"] = prim.n_fills.to_numpy(); uu["n_pos"] = prim.n_pos.to_numpy()
        uu.to_parquet(tdir / "units.parquet", index=False)
        if pos is not None:
            pos.to_parquet(tdir / "trades_primary.parquet", index=False)
    return prim_df, rep_df, sens_df


# ============================================================================ Control (i): Roll market

def roll_ticks(P0, half, sig5, p_tr, adv, n_names=30, n_sess=160, burn=80, cent=False, seed=20261018, keep=0.4,
               alternate=False):
    """Tick prints of a zero-information Roll market: random-walk mid, Poisson prints at the bid or ask with
    i.i.d. 50/50 side, lognormal $ sizes; 40% of prints kept for the intraday bars. Returns per-name arrays."""
    rng = np.random.default_rng(seed)
    S = n_sess + burn
    lam_kept = -math.log(max(1 - p_tr, 1e-6))
    lam_all = lam_kept / keep                              # prints per 5-minute bar
    per_sess = lam_all * (FULL / 300)
    mean_usd = adv / per_sess
    names = []
    for _ in range(n_names):
        cnt = rng.poisson(per_sess, S)
        n = int(cnt.sum())
        sess = np.repeat(np.arange(S), cnt)
        tin = rng.uniform(0, FULL, n)
        o = np.lexsort((tin, sess))
        sess, tin = sess[o], tin[o]
        tg = sess * FULL + tin
        dtg = np.diff(np.concatenate([[0.0], tg]))
        lm = math.log(P0) + np.cumsum(rng.normal(0, 1, n) * sig5 * np.sqrt(dtg / 300))
        mid = np.exp(lm)
        buy = rng.random(n) < 0.5
        if alternate:                                      # diagnostic only: strictly alternating sides
            buy = (np.arange(n) + int(rng.integers(2))) % 2 == 0
        if cent:
            bid = np.floor(mid * 100 + 1e-9) / 100; ask = bid + 0.01
        else:
            bid = np.floor(mid * (1 - half) * 100 + 1e-9) / 100
            ask = np.maximum(np.ceil(mid * (1 + half) * 100 - 1e-9) / 100, bid + 0.01)
        px = np.round(np.where(buy, ask, bid), 2)
        usd = np.exp(rng.normal(math.log(mean_usd) - 0.5, 1.0, n))
        sh = np.maximum(1, np.round(usd / px))
        kept = rng.random(n) < keep
        names.append((sess, tin, px, sh, kept))
    return names


def ticks_to_clock(names, dates, dt, keep_only=True):
    """Aggregate prints to clock bars (kept prints) -> a clock namespace like build_clock."""
    N, D, K = len(names), len(dates), FULL // dt
    ck = SimpleNamespace(syms=np.array([f"SYN{i:03d}" for i in range(N)], dtype=object), dates=pd.DatetimeIndex(dates),
                         L=np.full(D, FULL), NB=np.full(D, K), dt=dt, K=K, N=N, D=D, n_dropped=0)
    for a in ("O", "H", "L_", "C"):
        setattr(ck, a, np.full((N, D, K), np.nan))
    ck.V = np.zeros((N, D, K)); ck.TR = np.zeros((N, D, K), bool)
    for i, (sess, tin, px, sh, kept) in enumerate(names):
        k = kept if keep_only else np.ones(len(px), bool)
        s_, b_ = sess[k], (tin[k] // dt).astype(np.int64)
        p_, v_ = px[k], sh[k]
        if not len(p_):
            continue
        key = s_ * K + b_
        first = np.r_[True, key[1:] != key[:-1]]
        last = np.r_[key[1:] != key[:-1], True]
        gid = np.cumsum(first) - 1
        kk = key[first]
        ck.O[i].reshape(-1)[kk] = p_[first]
        ck.C[i].reshape(-1)[kk] = p_[last]
        ck.H[i].reshape(-1)[kk] = np.maximum.reduceat(p_, np.where(first)[0])
        ck.L_[i].reshape(-1)[kk] = np.minimum.reduceat(p_, np.where(first)[0])
        ck.V[i].reshape(-1)[kk] = np.bincount(gid, weights=v_)
        ck.TR[i].reshape(-1)[kk] = True
    ck.WCL = np.zeros((N, D, K), bool); ck.WCH = np.zeros((N, D, K), bool)
    ck.WCL[ck.TR] = wcent(ck.L_[ck.TR]); ck.WCH[ck.TR] = wcent(ck.H[ck.TR])
    return ck


def ticks_to_daily(names, dates):
    rows = []
    for i, (sess, tin, px, sh, kept) in enumerate(names):
        df = pd.DataFrame({"s": sess, "p": px, "v": sh})
        g = df.groupby("s")
        a = pd.DataFrame({"open": g.p.first(), "high": g.p.max(), "low": g.p.min(), "close": g.p.last(), "volume": g.v.sum()})
        a["ticker"] = f"SYN{i:03d}"; a["date"] = dates[a.index.to_numpy()]
        rows.append(a.reset_index(drop=True))
    m = pd.concat(rows, ignore_index=True)
    m["interpolated"] = False
    for c in ("open", "high", "low", "close"):
        m[c + "_u"] = m[c]
    return _long_from_merged(m)


def band_bar_params(ck, U):
    """Band medians of the share of traded 5-minute bars and of the 5-minute volatility (C10)."""
    out = {}
    nt = ck.NT5[U.ic.to_numpy(), np.maximum(U.dc.to_numpy(), 0)]
    nb = np.where(U.dc >= 0, ck.NB[np.maximum(U.dc.to_numpy(), 0)], 78)
    vol = ck.VOL5[U.ic.to_numpy(), np.maximum(U.dc.to_numpy(), 0)]
    share = np.where(U.dc >= 0, nt / nb, 0.0)
    for k in (1, 2, 3, 4):
        mk = (U.band.to_numpy() == k) & (U.elig.to_numpy(bool) if "elig" in U else True)
        src = "point-in-time band"
        if mk.sum() == 0:
            mk = U.sym.map(PILOT_BUCKET).to_numpy() == k
            src = "pilot ADV bucket (no stock-session in this band)"
        q = mk & (nt >= 10) & np.isfinite(vol)
        out[k] = {"p_traded": float(np.median(share[mk])) if mk.any() else np.nan,
                  "sigma_5m": float(np.median(vol[q])) if q.any() else np.nan, "n_stock_sessions": int(mk.sum()),
                  "source": src}
    return out


def control_i(params, cf, say, quick=False):
    """Control (i): per band, the median closing spread and a one-cent case; C1 unchanged; PASS per C10."""
    rows, prm = [], []
    for k in (1, 2, 3, 4):
        pk = params[k]
        for case in ("median spread", "one cent"):
            t0 = time.time()
            n_names, n_sess, burn = (10, 60, 70) if quick else (30, 160, 80)
            names = roll_ticks(BAND_PRICE[k], BAND_QSPREAD[k] / 2, pk["sigma_5m"], pk["p_traded"], BAND_ADV_MID[k],
                               n_names, n_sess, burn, cent=(case == "one cent"), seed=20261018 + 10 * k)
            dates = pd.bdate_range("2025-01-06", periods=n_sess + burn)
            m = ticks_to_daily(names, dates)
            P = daily_panel(m, dates, cf, f"Roll L{k}")
            ck5 = ticks_to_clock(names, dates, 300)
            ck1 = ticks_to_clock(names, dates, 60)
            U = make_units(ck5, P, (str(dates[burn].date()), str(dates[-1].date())), say=lambda *a: None)
            U["sec"], U["taf"], U["tafcap"] = 20.6e-6, 0.000195, 9.79
            X = gather(ck5, U)
            prim, _, _ = run_c1(ck5, U, X)
            t12, _, _ = run_c1(ck5, U, X, tmax_s=TMAX12_S)
            lat, _, _ = run_c1(ck5, U, X, lat=1)
            U1, r1, idx1 = rerun_other(ck1, U, P)
            mk = band_masks(U)[k]                          # the primary cell's own mask (C1 run unchanged)
            st = stats_of(U, prim, mk)
            x = prim.net.to_numpy(); h = U.half.to_numpy()
            h1, h2 = x[mk & (h == 1)].mean(), x[mk & (h == 2)].mean()
            dm, _ = drop_worst(x[mk], U.date.to_numpy()[mk]) if mk.sum() > 1 else (np.nan, None)
            m1 = r1.net.to_numpy()[mk[idx1]].mean()
            e12, el = t12.net.to_numpy()[mk].mean(), lat.net.to_numpy()[mk].mean()
            ok = (st["p_one_sided"] < ALPHA / N_PRIMARY) and h1 > 0 and h2 > 0 and e12 > 0 and el > 0 and dm > 0 \
                and np.sign(m1) == np.sign(st["estimate"]) and m1 != 0
            pos = prim[mk]
            rows.append({"band": f"L{k}", "case": case, "pass": bool(ok)} | st |
                        {"half1": h1, "half2": h2, "tmax12_estimate": e12, "latency_estimate": el, "dropsession_estimate": dm,
                         "m1_estimate": m1, "units_in_band": int((U.band.to_numpy() == k).sum()), "units_total": len(U),
                         "share_tick3": float(U.tick3[U.band == k].mean()) if (U.band == k).any() else np.nan,
                         "s_median_bp": 1e4 * float(np.nanmedian(U.s[mk])) if mk.any() else np.nan,
                         "true_spread_bp_at_P0": 1e4 * (BAND_QSPREAD[k] if case == "median spread" else 0.01 / BAND_PRICE[k]),
                         "bought_per_unit": float(pos.bought.mean()), "fills_per_unit": float(pos.n_fills.mean()),
                         "gross_bp": 1e4 * pos.gross.sum() / pos.bought.sum() if pos.bought.sum() > 0 else np.nan,
                         "seconds": time.time() - t0})
            prm.append({"band": f"L{k}", "case": case, "price0": BAND_PRICE[k],
                        "spread": BAND_QSPREAD[k] if case == "median spread" else "one cent", "sigma_5m": pk["sigma_5m"],
                        "p_traded_target": pk["p_traded"], "adv_target": BAND_ADV_MID[k], "names": n_names,
                        "sessions": n_sess, "burn_in": burn, "kept_share": 0.4, "param_source": pk["source"],
                        "param_n_stock_sessions": pk["n_stock_sessions"],
                        "realized_p_traded": float(ck5.TR[:, burn:].mean()),
                        "realized_adv60_median": float(np.median(U.adv))})
            say(f"  Roll L{k} {case:13s}: estimate ${st['estimate']:+.3f}/stock-session (t {st['t']:+.2f}, "
                f"p {st['p_one_sided']:.2g}), edge {1e4 * st['edge_estimate']:+.1f} bp/$, active {st['share_active']:.2f}, "
                f"PASS={ok}  [{time.time() - t0:.0f}s]")
    return pd.DataFrame(rows), pd.DataFrame(prm)


def _decompose(U, res, pos, mk):
    pp = pos[mk[pos.unit.to_numpy()]]
    cost = pp.cost.sum()
    if cost <= 0:
        return {}
    sh = pp.shares.sum()
    return {"net_bp_per_$": 1e4 * pp.net.sum() / cost, "gross_bp_per_$": 1e4 * res.gross.to_numpy()[mk].sum() / cost,
            "share_sold_limit": pp.lim_sh.sum() / sh, "share_sold_forced": pp.forced_sh.sum() / sh,
            "share_sold_final": pp.final_sh.sum() / sh,
            "limit_bp": 1e4 * (pp.lim_usd - pp.lim_sh * pp.B).sum() / cost,
            "forced_bp": 1e4 * (pp.forced_exec - pp.forced_sh * pp.B).sum() / cost,
            "final_bp": 1e4 * (pp.final_exec - pp.final_sh * pp.B).sum() / cost, "fees_bp": -1e4 * pp.fees.sum() / cost,
            "markout1_bp": 1e4 * float(np.nanmean(pp.mk1)), "markout6_bp": 1e4 * float(np.nanmean(pp.mk6)),
            "A_over_B_bp": 1e4 * float(np.mean(pp.A / pp.B - 1)), "positions": len(pp)}


def control_i_diagnostics(params, cf, say):
    """Why C1 does or does not earn the spread in the Roll market (diagnostic variants, NOT the pre-registered
    control): exit decomposition and markouts of the control as run; gross (m = 0); no T_max (15:50 exit only);
    strictly alternating print sides; half the mid volatility; tiny mid volatility with s set to the true spread."""
    rows = []
    for k in (1, 2, 3, 4):
        pk = params[k]
        h = BAND_QSPREAD[k] / 2
        def build(sig5, alternate=False):
            names = roll_ticks(BAND_PRICE[k], h, sig5, pk["p_traded"], BAND_ADV_MID[k], 30, 160, 80,
                               seed=20261018 + 10 * k, alternate=alternate)
            dates = pd.bdate_range("2025-01-06", periods=240)
            P = daily_panel(ticks_to_daily(names, dates), dates, cf, f"Roll L{k}")
            ck = ticks_to_clock(names, dates, 300)
            U = make_units(ck, P, (str(dates[80].date()), str(dates[-1].date())), say=lambda *a: None)
            U["sec"], U["taf"], U["tafcap"] = 20.6e-6, 0.000195, 9.79
            return ck, U
        ck, U = build(pk["sigma_5m"])
        mk = (U.band.to_numpy() == k) & U.tick3.to_numpy(bool) & np.isfinite(U.s.to_numpy())
        for lab, kw in (("as run (m=1.5)", {}), ("gross m=0", {"m": 0.0}), ("no T_max (15:50 exit only)", {"tmax_s": 10 ** 6})):
            res, pos, _ = run_c1(ck, U, rec=True, **kw)
            rows.append({"band": f"L{k}", "variant": lab, "s_median_bp": 1e4 * float(np.nanmedian(U.s[mk])),
                         "true_spread_bp": 1e4 * BAND_QSPREAD[k]} | stats_of(U, res, mk) | _decompose(U, res, pos, mk))
        for lab, sig5, alt in (("alternating sides", pk["sigma_5m"], True), ("half mid volatility", pk["sigma_5m"] / 2, False)):
            ck2, U2 = build(sig5, alt)
            mk2 = (U2.band.to_numpy() == k) & U2.tick3.to_numpy(bool) & np.isfinite(U2.s.to_numpy())
            res, pos, _ = run_c1(ck2, U2, rec=True)
            rows.append({"band": f"L{k}", "variant": lab, "s_median_bp": 1e4 * float(np.nanmedian(U2.s[mk2])),
                         "true_spread_bp": 1e4 * BAND_QSPREAD[k]} | stats_of(U2, res, mk2) | _decompose(U2, res, pos, mk2))
        ck3, U3 = build(1e-5)
        U3["s"] = BAND_QSPREAD[k]
        mk3 = (U3.band.to_numpy() == k) & np.isfinite(U3.s.to_numpy())
        for lab, kw in (("tiny vol, s = true spread, m=1.5", {}), ("tiny vol, s = true spread, m=0", {"m": 0.0})):
            res, pos, _ = run_c1(ck3, U3, rec=True, **kw)
            rows.append({"band": f"L{k}", "variant": lab, "s_median_bp": 1e4 * BAND_QSPREAD[k],
                         "true_spread_bp": 1e4 * BAND_QSPREAD[k]} | stats_of(U3, res, mk3) | _decompose(U3, res, pos, mk3))
        say(f"  diagnostics L{k} done")
    return pd.DataFrame(rows)


# ============================================================================ Control (ii): within-session shuffle

def control_ii(ck5, U, say):
    X = gather(ck5, U, shuffle_seed=20261018)
    res, _, _ = run_c1(ck5, U, X)
    rows = []
    for k in (1, 2, 3, 4):
        for sub, mk in (("s x P >= $0.03", band_masks(U)[k]),
                        ("all ticks", (U.band.to_numpy() == k) & np.isfinite(U.s) & U.elig.to_numpy(bool))):
            st = stats_of(U, res, mk)
            rows.append({"band": f"L{k}", "subset": sub, "null": "bars shuffled within the session"} | st
                        | {"fills": int(res.n_fills.to_numpy()[mk].sum())})
    return pd.DataFrame(rows)


# ============================================================================ Control (iii): IEX TOPS validation

IEX_URL = "https://storage.googleapis.com/iex/data/feeds/{d}/{d}_IEXTP1_TOPS1.6.pcap.gz"


def iex_filter_stream(url, syms, out_csv):
    """Stream a TOPS 1.6 pcap.gz with curl and keep Quote Update / Trade Report messages for syms (the pilot's
    byte-pattern filter, data/scalping/scripts_pilot/iex_tops_filter.py). Bytes are only parsed with struct."""
    import re
    import struct
    import zlib
    alt = b"|".join(re.escape(s.encode().ljust(8)) for s in syms)
    pat = re.compile(rb"(?:\x2a\x00\x51|\x26\x00\x54).{9}(?:" + alt + rb")", re.DOTALL)
    dz = zlib.decompressobj(16 + zlib.MAX_WBITS)
    proc = subprocess.Popen(["curl", "-sS", "--fail", url], stdout=subprocess.PIPE)
    tail = b""
    with open(out_csv, "w") as out:
        out.write("type,ts_ns,symbol,flags,bid_size,bid,ask,ask_size,trade_size,trade_price\n")
        while True:
            chunk = proc.stdout.read(16 << 20)
            if not chunk:
                break
            data = tail + dz.decompress(chunk)
            limit = len(data) - 64
            for mt in pat.finditer(data, 0, len(data)):
                if mt.start() >= limit:
                    break
                p = mt.start() + 2
                if data[p] == 0x51 and p + 42 <= len(data):
                    fl, ts, sym, bsz, bpx, apx, asz = struct.unpack_from("<BQ8sIqqI", data, p + 1)
                    out.write(f"Q,{ts},{sym.decode().strip()},{fl},{bsz},{bpx / 1e4},{apx / 1e4},{asz},,\n")
                elif data[p] == 0x54 and p + 38 <= len(data):
                    fl, ts, sym, sz, px, _ = struct.unpack_from("<BQ8sIqq", data, p + 1)
                    out.write(f"T,{ts},{sym.decode().strip()},{fl},,,,,{sz},{px / 1e4}\n")
            tail = data[limit:] if limit > 0 else data
    return proc.wait()


def iex_sim(ev, day, s, lts, closes, vols, sig, adv, sec, taf, tafcap, Q=Q0, m=M0):
    """C1's rule on one name-day of IEX TOPS ticks (C16). ev: DataFrame (ts_ns, type, flags, bid_size, bid, ask,
    ask_size, trade_size, trade_price) sorted by time; lts / closes / vols: the bar-based last trades, closes
    and volumes of the 78 five-minute clock bars (the same inputs as the bar run). Back-of-queue fills at the
    IEX bid / ask, forced and final exits at the IEX mid. Returns a dict of totals."""
    t_open = pd.Timestamp(f"{day} 09:30", tz=NY).value
    step = 300 * 10 ** 9
    ts = ev.ts_ns.to_numpy(np.int64); typ = ev.type.to_numpy(); fl = ev["flags"].to_numpy(np.int64)
    qb = ev.bid.to_numpy(float); qbs = ev.bid_size.to_numpy(float); qa = ev.ask.to_numpy(float)
    qas = ev.ask_size.to_numpy(float); tsz = ev.trade_size.to_numpy(float); tpx = ev.trade_price.to_numpy(float)
    bid = ask = 0.0; bsz = asz = 0.0
    B = np.nan; ahead_b = np.inf
    hold = cost = sh_b = proceeds = 0.0; j0 = -1; A = np.nan; ahead_s = np.inf
    tot = dict(net=0.0, bought=0.0, n_fills=0, n_pos=0, mk1=0.0, mk3=0.0, mk6=0.0, mkw=0.0)
    mids = np.full(78, np.nan)
    pending_mk = []
    e = int(np.searchsorted(ts, t_open))
    n = len(ts)
    pre = np.where(typ[:e] == "Q")[0]                  # review fix: the book state at 09:30 is the last pre-open quote
    if len(pre):
        q0 = pre[-1]
        bid, bsz, ask, asz = qb[q0], qbs[q0], qa[q0], qas[q0]
    for j in range(78):
        t_end = t_open + (j + 1) * step
        sell_live = hold > 0 and j0 >= 0 and j0 + 1 <= j <= j0 + 6
        if sell_live and j == j0 + 1:
            ahead_s = asz if ask == A else (0.0 if (ask <= 0 or ask > A) else np.inf)
        while e < n and ts[e] < t_end:
            if typ[e] == "Q":
                bid, bsz, ask, asz = qb[e], qbs[e], qa[e], qas[e]
                if np.isfinite(B):
                    ahead_b = min(ahead_b, bsz) if bid == B else (0.0 if (bid <= 0 or bid < B) else ahead_b)
                if sell_live:
                    ahead_s = min(ahead_s, asz) if ask == A else (0.0 if (ask <= 0 or ask > A) else ahead_s)
            elif not (fl[e] & 0x48):                        # skip extended-hours and single-price-cross trades
                px, sz = tpx[e], tsz[e]
                if np.isfinite(B) and sh_b * B < Q - 1e-9:
                    fill = 0.0
                    if px < B - 1e-9:
                        fill = sz
                    elif abs(px - B) < 1e-9 and bid == B:
                        use = min(ahead_b, sz); ahead_b -= use; fill = sz - use
                    sh = min(np.floor((Q - sh_b * B) / B + 1e-9), fill)
                    if sh >= 1:
                        if j0 < 0:
                            j0 = j; A = _cc(B * (1 + s)); pending_mk.append((j, B))
                        hold += sh; cost += sh * B; sh_b += sh; tot["n_fills"] += 1
                elif sell_live and hold > 0:
                    fill = 0.0
                    if px > A + 1e-9:
                        fill = sz
                    elif abs(px - A) < 1e-9 and ask == A:
                        use = min(ahead_s, sz); ahead_s -= use; fill = sz - use
                    sh = min(hold, fill)
                    if sh >= 1:
                        hold -= sh; proceeds += sh * A
            e += 1
        mm = 0.5 * (bid + ask) if bid > 0 and ask > 0 else np.nan
        mids[j] = mm
        if hold > 0 and j0 >= 0 and j >= j0 + 6 and vols[j] > 0 and np.isfinite(mm):
            sh = min(hold, np.floor(0.25 * vols[j] + 1e-9))
            if sh >= 1:
                hold -= sh; proceeds += sh * mm * (1 - m * s / 2)
        if hold > 0 and j == 76:
            px = mm if np.isfinite(mm) else lts[j]
            rem = hold * px
            proceeds += rem * (1 - m * s - 0.5 * sig * math.sqrt(rem / max(adv, 1000.0))); hold = 0.0
        if j0 >= 0 and hold <= 0:
            fees = (sec * proceeds if proceeds > 500 else 0.0) + (min(taf * sh_b, tafcap) if sh_b > 50 else 0.0)
            tot["net"] += proceeds - cost - fees; tot["bought"] += cost; tot["n_pos"] += 1
            hold = cost = sh_b = proceeds = 0.0; j0 = -1; ahead_s = np.inf
        B = np.nan
        if j0 < 0 and 2 <= j <= 71 and np.isfinite(lts[j]):
            B = _fc(lts[j] * (1 - s / 2))
            ahead_b = bsz if bid == B else (0.0 if (bid <= 0 or bid < B) else np.inf)
    for j, Bp in pending_mk:
        for k in (1, 3, 6):
            if j + k < 78 and np.isfinite(mids[j + k]):
                tot[f"mk{k}"] += mids[j + k] / Bp - 1
        tot["mkw"] += 1
    return tot


def iex_days(U):
    sess = pd.DatetimeIndex(np.sort(U.date.unique()))
    anchor = pd.Timestamp("2026-10-16")
    others = sess[sess != anchor]
    pick = np.sort(np.random.default_rng(20261018).choice(len(others), size=min(4 if anchor in sess else 5,
                                                                                   len(others)), replace=False))
    days = ([anchor] if anchor in sess else []) + list(others[pick])
    return sorted(days)


def _iex_job(args):
    day, syms, path = args
    if Path(path).exists() and Path(path).stat().st_size > 100:
        return day, 0, "cached"
    t0 = time.time()
    rc = iex_filter_stream(IEX_URL.format(d=day.strftime("%Y%m%d")), syms, path)
    return day, rc, f"{time.time() - t0:.0f}s"


def control_iii(cf, say, workers=4):
    """Control (iii): 5 days, panel L4 names whose IEX BBO matched the NBBO at the close (C16); C1 on IEX ticks vs
    bar-based C1 on the same name-days (descriptive)."""
    import multiprocessing as mp
    pan, ck5, P, U, _, _ = load_panel_data(cf, say)
    days = iex_days(U)
    idir = TDIR / "iex"; idir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for d in days:
        syms = sorted(U.sym[(U.date == d) & (U.band == 4) & U.elig].unique())
        say(f"  IEX day {d.date()}: {len(syms)} panel L4 names")
        if not syms:                                   # an empty symbol filter would match every message of the day
            continue
        jobs.append((d, syms, str(idir / f"tops_{d.strftime('%Y%m%d')}.csv")))
    with mp.Pool(min(workers, len(jobs))) as pool:
        for d, rc, msg in pool.imap_unordered(_iex_job, jobs):
            say(f"  streamed {d.date()}: rc={rc} {msg}")
    nbbo = pd.read_csv(RH / "universe.csv", keep_default_na=False, dtype={"ticker": str})
    nbbo = nbbo.set_index("ticker")[["Bid Price", "Ask Price"]].apply(pd.to_numeric, errors="coerce")
    X = gather(ck5, U)
    bar, _, _ = run_c1(ck5, U, X)
    lts_all = X["C"].copy()
    rows = []
    for d, syms, path in jobs:
        tops = pd.read_csv(path, keep_default_na=False, na_values=[""], dtype={"symbol": str, "type": str})
        tops = tops.sort_values("ts_ns", kind="stable")
        snap = pd.Timestamp(f"{d.date()} 15:59:59", tz=NY).value
        for sym in syms:
            g = tops[tops.symbol == sym]
            q = g[(g.type == "Q") & (g.ts_ns <= snap)].tail(1)
            u = np.where((U.sym.to_numpy() == sym) & (U.date.to_numpy() == d))[0]
            if not len(u):
                continue
            u = u[0]; r = U.row.iloc[u]; t = U.t.iloc[u]
            close = float(P.C[r, t] / P.KK[r, t]) if P.real[r, t] else np.nan
            ib, ia = (float(q.bid.iloc[0]), float(q.ask.iloc[0])) if len(q) else (0.0, 0.0)
            if d == pd.Timestamp("2026-10-16") and sym in nbbo.index:
                nb_, na_ = nbbo.loc[sym]
                match = bool(np.isclose(ib, nb_) and np.isclose(ia, na_)); rule = "scanner NBBO"
            else:
                lim = max(0.01, math.ceil(1.5 * U.M.iloc[u] * close * 100 - 1e-9) / 100) if np.isfinite(close) else np.nan
                match = bool(ib > 0 and ia > 0 and ib <= close <= ia and (ia - ib) <= lim + 1e-9); rule = "proxy"
            row = {"date": d.date(), "sym": sym, "iex_bid": ib, "iex_ask": ia, "close": close, "match_rule": rule,
                   "matched": match}
            if match:
                nb = int(X["NB"][u])
                lts = pd.Series(np.where(X["TR"][u, :nb], lts_all[u, :nb], np.nan)).ffill().fillna(U.lt0.iloc[u]).to_numpy()
                lts = np.r_[lts, np.full(78 - nb, lts[-1])]
                vols = np.r_[X["V"][u, :nb], np.zeros(78 - nb)]
                tt = iex_sim(g, d.date(), float(U.s.iloc[u]), lts, np.r_[X["C"][u, :nb], np.full(78 - nb, np.nan)], vols,
                             float(U.sig.iloc[u]), float(U.adv.iloc[u]), float(U.sec.iloc[u]), float(U.taf.iloc[u]),
                             float(U.tafcap.iloc[u]))
                row |= {f"iex_{k}": v for k, v in tt.items()}
                row |= {"bar_net": bar.net.iloc[u], "bar_bought": bar.bought.iloc[u], "bar_n_fills": bar.n_fills.iloc[u],
                        "bar_n_pos": bar.n_pos.iloc[u], "s": U.s.iloc[u], "tick3": bool(U.tick3.iloc[u])}
            rows.append(row)
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "controls_iii_iex.csv", index=False)
    mm = R[R.matched] if len(R) else R
    if len(mm):
        say(f"Control (iii): {len(R)} L4 name-days, {len(mm)} at the NBBO; IEX fills {int(mm.iex_n_fills.sum())} vs bar"
            f" fills {int(mm.bar_n_fills.sum())}; bought ${mm.iex_bought.sum():,.0f} vs ${mm.bar_bought.sum():,.0f}")
    return R


# ============================================================================ Part E: intraday ORB leg

def orb_day(TR, Hh, Ll, Cc, Vv, nb, L, s, sig, adv, band, sec, taf, tafcap, Q=QBIG):
    """Part E ORB on one name-day of 5-minute clock bars (C17). Returns a dict (no trade: 'reason')."""
    fx = (L - 300) // 300 - 1
    if not TR[:6].any() or not np.isfinite(s):
        return {"traded": False, "reason": "no opening-range trade or no s"}
    orh, orl = np.nanmax(Hh[:6]), np.nanmin(Ll[:6])
    ent = next((j for j in range(6, fx) if TR[j] and Cc[j] > orh), None)
    if ent is None:
        return {"traded": False, "reason": "no breakout"}
    lt = pd.Series(np.where(TR[:nb], Cc[:nb], np.nan)).ffill().to_numpy()
    ext = next((j for j in range(ent + 1, fx + 1) if TR[j] and Cc[j] < orl), fx)
    q = min(Q, 0.25 * Cc[ent] * Vv[ent])
    rec = {"traded": True, "entry_bar": ent, "exit_bar": ext,
           "exit_kind": "range low" if (TR[ext] and Cc[ext] < orl) else "15:50 close"}
    for mm in (0.0, 1.0, 1.5, 2.0):
        for Y in (0.0, 0.5):
            imp = Y * sig * math.sqrt(max(0.0, Q - sd.DEPTH[band]) / max(adv, 1000.0)) if Y else 0.0
            pin = Cc[ent] * (1 + mm * s / 2 + imp)
            sh = math.floor(q / pin + 1e-9)
            if sh < 1:
                rec[f"r_m{mm:g}_Y{Y:g}"] = np.nan; continue
            proc = sh * lt[ext] * (1 - mm * s / 2 - imp)
            fee = (sec * proc if proc > 500 else 0.0) + (min(taf * sh, tafcap) if sh > 50 else 0.0)
            rec[f"r_m{mm:g}_Y{Y:g}"] = (proc - fee) / (sh * pin) - 1
            if mm == 1.5 and Y == 0.0:
                rec["cost_usd"] = sh * pin; rec["net_usd"] = proc - fee - sh * pin
    return rec


def orb_summary(R):
    out = []
    tr = R[R.traded]
    iso = pd.to_datetime(tr.date).dt.isocalendar()
    wk = (iso.year.astype(str) + "-" + iso.week.astype(str)).to_numpy()
    bands = sorted(R.band.dropna().unique().astype(int)) if "band" in R else []
    groups = [("all", None)] + [(f"L{b}" if b else "below L1", b) for b in bands]
    for col in [c for c in R.columns if c.startswith("r_m")]:
        for gname, b in groups:
            if b is not None and col != "r_m1.5_Y0":
                continue
            gm = np.ones(len(tr), bool) if b is None else (tr.band.to_numpy() == b)
            x = tr[col].to_numpy(float); ok = np.isfinite(x) & gm
            m, se, t, p, dfree = cluster2_t(x[ok], tr.symbol.to_numpy()[ok], wk[ok]) if ok.sum() >= 3 else (np.nan,) * 5
            nev = len(R) if b is None else int((R.band == b).sum())
            out.append({"variant": col, "band": gname, "n_events": nev, "n_trades": int(ok.sum()), "mean_return": m,
                        "se": se, "t": t, "p_one_sided": p, "df": dfree,
                        "median_return": float(np.median(x[ok])) if ok.any() else np.nan,
                        "share_events_traded": int(ok.sum()) / nev if nev else np.nan})
    return pd.DataFrame(out)


def orb(cf, say, Q=QBIG):
    """Part E intraday leg on the pulled event days (exploratory)."""
    # review fix C25: keep_default_na=False, else the ticker "NA" is read as NaN (lost event, and sorted() fails)
    ev = pd.read_csv(RH / "events.csv", parse_dates=["date"], keep_default_na=False, dtype={"symbol": str})
    ex = br_excluded(ev.symbol)
    if ex:
        say(f"Part E events on names outside the B-R universe (rules (b)-(d) / scan flag), dropped: "
            f"{int(ev.symbol.isin(set(ex)).sum())} events, {ex}")
        ev = ev[~ev.symbol.isin(set(ex))].reset_index(drop=True)
    bars = load_bars(RH / "events_m5_none.parquet", set(ev.symbol))
    ck = build_clock(bars, 300)
    P = daily_for(sorted(set(ev.symbol)), cf)
    sec_, taf_, cap_ = fees_for(ev.date)
    rows = []
    for e, ev_ in enumerate(ev.itertuples()):
        a = np.where(ck.syms == ev_.symbol)[0]; d = ck.dates.get_indexer([ev_.date])[0]
        base = {"symbol": ev_.symbol, "date": ev_.date}
        if not len(a) or d < 0 or ev_.symbol not in P.tix or not ck.TR[a[0], d].any():
            rows.append(base | {"traded": False, "reason": "no bars"}); continue
        a = a[0]; r = P.tix[ev_.symbol]; t = P.dates.get_indexer([ev_.date])[0]
        band = int(P.BAND[r, t])
        rec = orb_day(ck.TR[a, d], ck.H[a, d], ck.L_[a, d], ck.C[a, d], ck.V[a, d], ck.NB[d], ck.L[d],
                      float(P.SPR[r, t]), float(np.nan_to_num(P.SIG20[r, t])), float(np.nan_to_num(P.ADV[r, t])), band,
                      sec_[e], taf_[e], cap_[e], Q)
        rows.append(base | {"band": band, "s": float(P.SPR[r, t])} | rec)
    R = pd.DataFrame(rows)
    return R, orb_summary(R)


def orb_no_edge(params, cf, say, Q=QBIG):
    """The ORB engine's no-edge level (General rules): the Roll market of Control (i) (median spread), every
    stock-session of the 160 test sessions, unchanged rule and costs."""
    rows = []
    for k in (1, 2, 3, 4):
        pk = params[k]
        names = roll_ticks(BAND_PRICE[k], BAND_QSPREAD[k] / 2, pk["sigma_5m"], pk["p_traded"], BAND_ADV_MID[k],
                           30, 160, 80, seed=20261018 + 10 * k)
        dates = pd.bdate_range("2025-01-06", periods=240)
        P = daily_panel(ticks_to_daily(names, dates), dates, cf, f"Roll L{k}")
        ck = ticks_to_clock(names, dates, 300)
        for a in range(ck.N):
            r = P.tix[ck.syms[a]]
            for d in range(80, ck.D):
                rec = orb_day(ck.TR[a, d], ck.H[a, d], ck.L_[a, d], ck.C[a, d], ck.V[a, d], ck.NB[d], ck.L[d],
                              float(P.SPR[r, d]), float(np.nan_to_num(P.SIG20[r, d])), float(np.nan_to_num(P.ADV[r, d])),
                              int(P.BAND[r, d]), 20.6e-6, 0.000195, 9.79, Q)
                rows.append({"symbol": ck.syms[a], "date": dates[d], "band": int(P.BAND[r, d]), "roll_band": f"L{k}"} | rec)
    R = pd.DataFrame(rows)
    out = []
    for k in (1, 2, 3, 4):
        Rk = R[R.roll_band == f"L{k}"]
        sk = orb_summary(Rk)
        sk = sk[sk.band == "all"].assign(roll_market=f"L{k}")
        out.append(sk)
    return pd.concat(out, ignore_index=True)


# ============================================================================ data assembly

def panel_symbols():
    p = pd.read_csv(RH / "panel_c.csv", keep_default_na=False, dtype={"ticker": str})
    return p


def br_excluded(tickers):
    """Names outside the B-R universe as Part B builds it (scalp_us_daily._br_from_merged): the scan's keep flag /
    excl_reason, then exclusion rules (b)-(d) on the scan's and the listing files' security names (review fix C24)."""
    tickers = sorted(set(map(str, tickers)))
    u = pd.read_csv(RH / "universe.csv", keep_default_na=False, dtype={"ticker": str})
    u["ticker"] = u.ticker.str.upper()
    names = dict(zip(u.ticker, u["Name"])) if "Name" in u else {}
    scan_out = set()
    if "keep" in u:
        scan_out |= set(u.ticker[~u.keep.astype(str).str.strip().isin(["1", "1.0", "True"])])
    if "excl_reason" in u:
        scan_out |= set(u.ticker[~u.excl_reason.astype(str).str.strip().isin(["", "nan", "False", "0"])])
    r = sd.static_rules(tickers, sd.load_ref(), names)
    out = {}
    for t in tickers:
        why = [k for k in ("b", "c", "d") if bool(r.at[t, k])] + (["scan"] if t in scan_out else [])
        if why:
            out[t] = "rule " + "+".join(why)
    return out


PANEL_SRC = "panel (panel_c.csv, B-R universe names)"


def load_panel_data(cf, say):
    """The 120-name panel: 5-minute clock, daily panel, units; plus the 1-minute and 15-second clocks."""
    pan = panel_symbols()
    ex = br_excluded(pan.ticker)
    if ex:
        say(f"panel names outside the B-R universe (exclusion rules (b)-(d) / scan flag, as in Part B), dropped from "
            f"every cell: {ex}")
        pan = pan[~pan.ticker.isin(set(ex))].reset_index(drop=True)
    syms = sorted(pan.ticker)
    t0 = time.time()
    b5 = trim_flat(load_bars(RH / "m5_none.parquet", syms))
    ck5 = build_clock(b5, 300)
    say(f"5-minute bars: {len(b5):,} rows, {ck5.N} names, {ck5.D} sessions ({ck5.dates[0].date()}..{ck5.dates[-1].date()}),"
        f" {ck5.n_dropped} off-clock bars dropped, early-close sessions: "
        f"{[str(x.date()) for x, l in zip(ck5.dates, ck5.L) if l == HALF]} ({time.time() - t0:.0f}s)")
    missing = sorted(set(syms) - set(ck5.syms))
    if missing:
        say(f"  panel names without 5-minute bars (their sessions count as zero): {missing}")
        ck5 = build_clock(b5, 300, symbols=syms)
    P = daily_for(syms, cf)
    U = make_units(ck5, P, say=say)
    ck1 = ck15 = None
    if (RH / "m1_none.parquet").exists():
        b1 = trim_flat(load_bars(RH / "m1_none.parquet", syms))
        ck1 = build_clock(b1, 60)
        say(f"1-minute bars: {len(b1):,} rows, {ck1.N} names, {ck1.D} sessions ({ck1.dates[0].date()}..{ck1.dates[-1].date()})")
    if (RH / "s15_none.parquet").exists():
        b15 = trim_flat(load_bars(RH / "s15_none.parquet", syms))
        ck15 = build_clock(b15, 15)
        say(f"15-second bars: {len(b15):,} rows, {ck15.N} names, {ck15.D} sessions")
    return pan, ck5, P, U, ck1, ck15


def load_pilot_data(cf, say):
    b5 = load_bars(PILOT_INTRADAY)
    ck5 = build_clock(b5, 300)
    P = daily_for(list(ck5.syms), cf, source="pilot")
    U = make_units(ck5, P, win=(str(ck5.dates[0].date()), str(ck5.dates[-1].date())), say=say)
    return ck5, P, U


def b34_confirmation(ck5, U, cf, say):
    """Share of B-R B3/B4 daily fills in the window (panel names) not confirmed by any whole-cent 5-minute low."""
    BR = sd.load_br()
    EL, BC, sig = sd.prepare(BR, cf, None)
    w0, w1 = pd.Timestamp(U.attrs["w0"]), pd.Timestamp(U.attrs["w1"])
    rows = []
    for b in (1, 2, 3, 4):
        inb = EL.gb == b
        tr3 = sd.b3_trades(BR, EL, np.where(inb)[0])
        tr4 = sd.b4_trades(BR, sd.el_mask(BR, EL, inb))
        for strat, ii, fd, lim in (("B3", tr3["i"], tr3["ent"], tr3["L"]), ("B4", tr4["i"], tr4["t"] + 1, tr4["B"])):
            tick = BR.tickers[ii]; dates = BR.dates[fd]
            sel = np.isin(tick, ck5.syms) & (dates >= w0) & (dates <= w1)
            conf = []
            for tk, dd, lm in zip(tick[sel], dates[sel], np.asarray(lim)[sel]):
                a = np.where(ck5.syms == tk)[0][0]; d = ck5.dates.get_indexer([dd])[0]
                if d < 0:
                    conf.append(np.nan); continue
                okb = ck5.TR[a, d] & ck5.WCL[a, d] & (ck5.L_[a, d] * 100 <= lm * 100 - 1 + 1e-6)
                conf.append(float(okb.any()))
            conf = np.array(conf, float)
            rows.append({"strategy": strat, "band": f"L{b}", "n_fills_in_window": int(sel.sum()),
                         "n_with_5min_bars": int(np.isfinite(conf).sum()),
                         "share_not_confirmed": float(1 - np.nanmean(conf)) if np.isfinite(conf).any() else np.nan})
    return pd.DataFrame(rows)


# ============================================================================ tests

def run_tests():
    """Unit tests: EDGE vs the pilot's bidask copy, whole cents, the clock (DST, early close), the engine."""
    import importlib.util
    ok = True
    spec = importlib.util.spec_from_file_location("se", SC / "scripts_pilot" / "spread_estimators.py")
    se = importlib.util.module_from_spec(spec); spec.loader.exec_module(se)
    rng = np.random.default_rng(1)
    worst = 0.0
    for trial in range(300):
        n = int(rng.integers(5, 80))
        lm = np.log(5) + np.cumsum(rng.normal(0, 0.003, n))
        hs = rng.uniform(0.001, 0.02)
        px = lambda: np.round(np.exp(lm + rng.choice([-hs, hs], n)) * 100) / 100     # noqa: E731
        o, c = px(), px()
        h = np.maximum(np.maximum(o, c), px()); l_ = np.minimum(np.minimum(o, c), px())
        nanm = rng.random(n) < rng.uniform(0, 0.7)
        if trial % 5 == 0:
            nanm[:] = False
        for a in (o, h, l_, c):
            a[nanm] = np.nan
        ref = se.edge(o, h, l_, c)
        got = _edge_nan(np.log(o), np.log(h), np.log(l_), np.log(c))
        if np.isfinite(ref) or np.isfinite(got):
            worst = max(worst, abs(ref - got) if (np.isfinite(ref) and np.isfinite(got)) else np.inf)
    print(f"EDGE with NaN bars vs pilot bidask copy, 300 random series: max |diff| = {worst:.2e}")
    ok &= worst < 1e-10
    w = wcent([5.0, 5.01, 5.0009, 4.995, 12.34 + 1e-12, 0.01])
    print("whole cent", w.tolist()); ok &= w.tolist() == [True, True, False, False, True, True]
    # clock: a DST date and an early close
    idx = pd.to_datetime(["2026-03-06 14:30", "2026-03-09 13:30", "2026-03-09 19:55", "2025-11-28 17:55",
                          "2025-11-28 18:00"], utc=True)
    d = pd.DataFrame({"symbol": "X", "begins_at": idx, "open": 5.0, "high": 5.0, "low": 5.0, "close": 5.0, "volume": 100,
                      "interpolated": False})
    ck = build_clock(d, 300)
    dd, kk = np.where(ck.TR[0])
    got = [(str(ck.dates[j].date()), int(k)) for j, k in zip(dd, kk)]
    print("clock slots", got, "L", ck.L.tolist(), "dropped", ck.n_dropped)
    ok &= got == [("2025-11-28", 41), ("2026-03-06", 0), ("2026-03-09", 0), ("2026-03-09", 77)] and ck.n_dropped == 1
    ok &= ck.L.tolist() == [HALF, FULL, FULL]
    # engine: a hand-built session
    K = 78
    def sess():
        z = dict(O=np.full((1, K), np.nan), H=np.full((1, K), np.nan), L_=np.full((1, K), np.nan),
                 C=np.full((1, K), np.nan), V=np.zeros((1, K)), TR=np.zeros((1, K), bool))
        return z
    def put(z, k, o, h, l, c, v):
        z["O"][0, k], z["H"][0, k], z["L_"][0, k], z["C"][0, k], z["V"][0, k], z["TR"][0, k] = o, h, l, c, v, True
    def run(z, s=0.02, lat=0, tmax=6, touch=False, anyext=False, Q=2000.0):
        z = dict(z); z["WCL"] = np.zeros((1, K), bool); z["WCH"] = np.zeros((1, K), bool)
        z["WCL"][z["TR"]] = wcent(z["L_"][z["TR"]]); z["WCH"][z["TR"]] = wcent(z["H"][z["TR"]])
        U = pd.DataFrame({"s": [s], "lt0": [10.0], "sig": [0.02], "adv": [1e6], "sec": [0.0], "taf": [0.0],
                          "tafcap": [0.0], "L": [FULL]})
        z["NB"] = np.array([K])
        ck = SimpleNamespace(dt=300, K=K)
        return run_c1(ck, U, z, Q=Q, tmax_s=tmax * 300, lat=lat, touch=touch, anyext=anyext, rec=True)
    z = sess()
    put(z, 2, 10.0, 10.0, 10.0, 10.0, 1000)        # last trade 10.00 at the 09:40 close -> B = 9.90
    put(z, 3, 9.95, 9.95, 9.89, 9.90, 4000)        # low 9.89 <= 9.89: fill, f = (9.90-9.89)/(9.95-9.89) = 1/6
    put(z, 5, 10.05, 10.11, 10.0, 10.1, 4000)       # A = ceil(9.90 x 1.02) = 10.10; high 10.11 >= 10.11 fills
    res, pos, _ = run(z)
    # buy: 25% x 9.90 x 4000 x 1/6 = $1,650 -> 166 shares at 9.90; sell: 25% x 10.1 x 4000 x f, f = 0.01/0.11
    fsell = (10.11 - 10.10) / 0.11
    sh_s = math.floor(0.25 * 10.1 * 4000 * fsell / 10.10 + 1e-9)
    print("engine case 1:", pos[["j0", "B", "A", "shares", "lim_sh", "final_sh"]].to_dict("records"))
    ok &= len(pos) == 1 and pos.B[0] == 9.90 and pos.A[0] == 10.10 and pos.shares[0] == 166 and pos.lim_sh[0] == sh_s
    ok &= pos.final_sh[0] == 166 - sh_s
    z2 = sess(); put(z2, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z2, 3, 9.95, 9.95, 9.8899, 9.90, 4000)
    res2, pos2, _ = run(z2)
    print("engine case 2 (sub-penny low never fills):", len(pos2)); ok &= len(pos2) == 0
    res2b, pos2b, _ = run(z2, anyext=True)
    print("engine case 2b (any-extreme fills):", len(pos2b)); ok &= len(pos2b) == 1
    z3 = sess(); put(z3, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z3, 3, 9.90, 9.90, 9.90, 9.90, 4000)
    print("engine case 3 (touch only with touch rule):", len(run(z3)[1]), len(run(z3, touch=True)[1]))
    ok &= len(run(z3)[1]) == 0 and len(run(z3, touch=True)[1]) == 1
    # forced exit from the T_max bar, 25% of $ volume per bar, then the 15:50 remainder
    z4 = sess(); put(z4, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z4, 3, 9.89, 9.89, 9.89, 9.89, 10000)
    put(z4, 9, 9.95, 9.95, 9.95, 9.95, 100); put(z4, 10, 9.95, 9.95, 9.95, 9.95, 100)
    res4, pos4, _ = run(z4)
    print("engine case 4:", pos4[["j0", "shares", "forced_sh", "final_sh", "j_exit"]].to_dict("records"))
    ok &= pos4.j0[0] == 3 and pos4.shares[0] == 202 and pos4.forced_sh[0] == 50 and pos4.final_sh[0] == 152
    ok &= pos4.j_exit[0] == 76
    # latency: the order posted at the 09:40 close is live only from bar 4
    z5 = sess(); put(z5, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z5, 3, 9.89, 9.89, 9.89, 9.89, 10000)
    put(z5, 4, 9.89, 9.89, 9.89, 9.89, 10000)
    res5, pos5, _ = run(z5, lat=1)
    print("engine case 5 (latency):", pos5[["j0", "B"]].to_dict("records"))
    ok &= pos5.j0[0] == 4
    # latency: the stale order posted while flat fills the rest of the $2,000 cap in the next bar
    z6 = sess(); put(z6, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z6, 3, 10.0, 10.0, 10.0, 10.0, 1000)
    put(z6, 4, 9.89, 9.89, 9.89, 9.89, 404)        # 25% x 9.89 x 404 = $998.9 -> 100 shares at 9.90
    put(z6, 5, 9.89, 9.89, 9.89, 9.89, 10000)      # stale order (posted at the close of bar 3): the rest
    r6, p6, _ = run(z6, lat=1)
    print("engine case 6 (latency stale fill):", p6[["j0", "shares", "n_fills", "cost"]].to_dict("records"))
    ok &= len(p6) == 1 and p6.j0[0] == 4 and p6.n_fills[0] == 2 and p6.shares[0] == 100 + math.floor((2000 - 990) / 9.90 + 1e-9)
    # fees and the 15:50 remainder rule with impact
    z7 = sess(); put(z7, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z7, 3, 9.89, 9.89, 9.89, 9.89, 10000)
    put(z7, 70, 10.0, 10.0, 10.0, 10.0, 1)         # 25% of 1 share: no forced sale; last trade 10.00
    zz = dict(z7); zz["WCL"] = np.zeros((1, K), bool); zz["WCH"] = np.zeros((1, K), bool)
    zz["WCL"][zz["TR"]] = wcent(zz["L_"][zz["TR"]]); zz["WCH"][zz["TR"]] = wcent(zz["H"][zz["TR"]]); zz["NB"] = np.array([K])
    U7 = pd.DataFrame({"s": [0.02], "lt0": [10.0], "sig": [0.04], "adv": [1e5], "sec": [20.6e-6], "taf": [0.000195],
                       "tafcap": [9.79], "L": [FULL]})
    r7, p7, h7 = run_c1(SimpleNamespace(dt=300, K=K), U7, zz, rec=True)
    imp = 0.5 * 0.04 * math.sqrt(2020 / 1e5)
    proc = 2020 * (1 - 1.5 * 0.02 - imp)
    want = proc - 202 * 9.90 - (20.6e-6 * proc + 0.000195 * 202)
    print(f"engine case 7 (fees, 15:50 rule): net {p7.net[0]:.6f} vs {want:.6f}; held at bar 10 {h7[0, 10]:.2f}")
    ok &= abs(p7.net[0] - want) < 1e-6 and abs(h7[0, 10] - 1999.8) < 0.01 and h7[0, 76] == 0
    # two positions in one session: a full limit exit, then a new buy from the next close
    z8 = sess(); put(z8, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z8, 3, 9.89, 9.89, 9.89, 9.89, 10000)
    put(z8, 4, 10.11, 10.11, 10.11, 10.11, 100000); put(z8, 5, 9.99, 9.99, 9.99, 9.99, 10000)
    r8, p8, _ = run(z8)
    print("engine case 8 (two positions):", p8[["j0", "B", "lim_sh", "shares"]].to_dict("records"))
    ok &= len(p8) == 2 and p8.lim_sh[0] == 202 and p8.j0[1] == 5 and p8.B[1] == _fc(10.11 * 0.99)
    # T_max = 12 bars: the forced sale starts 12 bars after the fill
    z9 = sess(); put(z9, 2, 10.0, 10.0, 10.0, 10.0, 1000); put(z9, 3, 9.89, 9.89, 9.89, 9.89, 10000)
    for k in range(4, 20):
        put(z9, k, 9.95, 9.95, 9.95, 9.95, 100000)
    p9 = run(z9, tmax=12)[1]
    print("engine case 9 (T_max 12): exit bar", p9.j_exit[0]); ok &= p9.j_exit[0] == 15
    print("ALL TESTS PASSED" if ok else "SOME TESTS FAILED")
    return ok


def run_controls(ck5, U, cf, say, src, out):
    """Controls (i) (Roll market, band parameters from ck5/U) and (ii) (within-session shuffle of ck5's bars)."""
    params = band_bar_params(ck5, U)
    say(f"\nControl (i) Roll market; band parameters from {src}:")
    for k, v in params.items():
        say(f"  L{k}: {v}")
    c1, c1p = control_i(params, cf, say)
    c1["data"] = src; c1p["data"] = src
    c1.to_csv(out / "controls_i.csv", index=False); c1p.to_csv(out / "controls_i_params.csv", index=False)
    t1 = time.time()
    dg = control_i_diagnostics(params, cf, say)
    dg.to_csv(out / "controls_i_diagnostics.csv", index=False)
    say(f"Control (i) diagnostic variants (not the pre-registered control; {time.time() - t1:.0f}s):")
    say(dg[["band", "variant", "s_median_bp", "true_spread_bp", "estimate", "net_bp_per_$", "gross_bp_per_$",
            "share_sold_limit", "share_sold_forced", "markout1_bp", "A_over_B_bp"]].round(2).to_string(index=False))
    t1 = time.time()
    c2 = control_ii(ck5, U, say)
    c2["data"] = src
    c2.to_csv(out / "controls_ii.csv", index=False)
    say(f"\nControl (ii) within-session shuffle on {src} ({time.time() - t1:.1f}s):")
    say(c2[["band", "subset", "estimate", "t", "n_units", "share_active", "edge_estimate", "fills"]].to_string(index=False))
    return c1, c2


# ============================================================================ main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    for f in ("tests", "controls", "smoke", "run", "events", "iex", "pilot"):
        ap.add_argument(f"--{f}", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    if a.tests:
        sys.exit(0 if run_tests() else 1)
    out = (SCRATCH / "smoke_C") if a.smoke else OUT
    out.mkdir(parents=True, exist_ok=True)
    say = say_factory(out / ("summary.txt" if a.run else "summary_smoke.txt" if a.smoke else
                             "summary_controls.txt" if a.controls else "summary_events.txt" if a.events else
                             "summary_iex.txt"))
    T0 = time.time()
    cf, cflag = cost_model(say)
    have_panel = (RH / "panel_c.csv").exists() and (RH / "m5_none.parquet").exists()
    if a.controls:
        if have_panel and not a.pilot:
            pan, ck5, P, U, ck1, ck15 = load_panel_data(cf, say)
            src = PANEL_SRC
        else:
            ck5, P, U = load_pilot_data(cf, say)
            src = "6 pilot names (panel bars not yet pulled)"
        run_controls(ck5, U, cf, say, src, out)
    if a.smoke:
        t1 = time.time()
        ck5, P, U = load_pilot_data(cf, say)
        say(f"pilot data: {ck5.N} names x {ck5.D} sessions, {len(U):,} units ({time.time() - t1:.1f}s)")
        t1 = time.time()
        analyze(ck5, U, P, say, out, SCRATCH / "smoke_C_trades", write=True)
        say(f"smoke analysis (all variants, reported tables) {time.time() - t1:.1f}s; outputs in {out} (not read)")
    if a.run:
        if not have_panel:
            say("panel_c.csv / m5_none.parquet missing: nothing to run"); return
        pan, ck5, P, U, ck1, ck15 = load_panel_data(cf, say)
        # review fix C23: Controls (i)/(ii) are always recomputed here, on the panel's band parameters and bars and with
        # the current cost model, before the primary statistics (~30 s); a stale controls_i.csv is never used
        say("Controls (i)/(ii) on the panel first (as --controls):")
        run_controls(ck5, U, cf, say, PANEL_SRC, OUT)
        ci = pd.read_csv(OUT / "controls_i.csv")
        say(f"window {U.attrs['w0']}..{U.attrs['w1']} ({U.attrs['n_sessions']} sessions, median {U.attrs['median_session']}),"
            f" {len(U):,} stock-sessions; s from 5-min EDGE in {(U.s_src == '5min').mean():.0%}")
        say("Points where the pre-registration could not be followed as written (see the module docstring):")
        say("  - intraday bars are unadjusted only (all C rules are within-session and s is relative); daily bars are"
            " split-adjusted + unadjusted as registered")
        if U.attrs["w0"] != WIN0:
            say(f"  - retention had rolled past {WIN0}: the window starts at {U.attrs['w0']}")
        say(f"  - closing-quote model M: {cflag}")
        say("  - Control (iii): no historical NBBO exists except the 2026-10-16 scanner close, so 4 of the 5 IEX days use"
            " the NBBO-match proxy of C16")
        say(f"  - panel: {len(pan)} of {len(panel_symbols())} drawn names are in the B-R universe (C24: names failing"
            " rules (b)-(d) are dropped; the draw itself was made without rules (b)-(d))")
        if ck1 is None:
            say("  - 1-minute bars missing: PASS condition 6 (cond_1min) not evaluable (left empty = not met)")
        if ck15 is None:
            say("  - 15-second bars missing: the 15-second rerun is not reported")
        nii = pd.read_csv(OUT / "controls_ii.csv") if (OUT / "controls_ii.csv").exists() else None
        if nii is not None:
            nii = nii[nii.subset == "s x P >= $0.03"]
        b34 = None
        try:
            b34 = b34_confirmation(ck5, U, cf, say)
        except Exception as e:                               # descriptive only
            say(f"B3/B4 confirmation share not computed: {e!r}")
        prim, rep, sens = analyze(ck5, U, P, say, OUT, TDIR, ck1, ck15, ctrl_i=ci, null_ii=nii, b34=b34)
        p = holm(prim.p_one_sided.to_numpy())
        say("\n(provisional within-part Holm, C only; the study-wide Holm is in scalp_report.py)")
        say(pd.DataFrame({"test_id": prim.test_id, "estimate": prim.estimate, "t": prim.t, "p_holm_within": p,
                          "force_inconclusive": prim.force_inconclusive, "force_reason": prim.force_reason})
            .to_string(index=False))
    if a.events:
        if not ((RH / "events.csv").exists() and (RH / "events_m5_none.parquet").exists()):
            say("events.csv / events_m5_none.parquet missing: nothing to run"); return
        R, s = orb(cf, say)
        TDIR.mkdir(parents=True, exist_ok=True)
        R.to_parquet(TDIR / "e_orb_trades.parquet", index=False)
        s.to_csv(OUT / "e_orb.csv", index=False)
        pf = OUT / "controls_i_params.csv"
        if pf.exists():
            pp = pd.read_csv(pf)
            pp = pp[pp.case == "median spread"]
            params = {int(r.band[1]): {"sigma_5m": r.sigma_5m, "p_traded": r.p_traded_target} for r in pp.itertuples()}
            ne = orb_no_edge(params, cf, say)
            ne.to_csv(OUT / "e_orb_no_edge.csv", index=False)
            say("ORB no-edge level (Roll market of Control (i), all stock-sessions):")
            say(ne[["roll_market", "variant", "n_trades", "mean_return", "t"]].to_string(index=False))
        else:
            say("controls_i_params.csv missing: run --controls first for the ORB no-edge level")
        say(f"Part E intraday ORB leg (exploratory, survivor-biased): {len(R)} events, {int(R.traded.sum())} trades; "
            f"reasons for no trade: {R.loc[~R.traded, 'reason'].value_counts().to_dict()}")
        say(s.to_string(index=False))
    if a.iex:
        control_iii(cf, say, a.workers)
    say(f"\ntotal {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
