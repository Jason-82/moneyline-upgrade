"""
Scalping study, Parts B, E (daily rule E1) and D: daily-horizon liquidity provision, attention continuation
and capacity in low-volume US stocks. Pre-registered in analysis_2026/SCALPING_PREREG.md (frozen
2026-10-18); this module implements the sections "Common definitions for US stocks", "Part B" (with its
controls), "Part E" (daily rule only; the intraday ORB leg is in scalp_us_intraday.py) and "Part D".

    python3 -m analysis_2026.scalp_us_daily --controls      # known answer (ii), survivorship (iii), synthetic no-edge
    python3 -m analysis_2026.scalp_us_daily --smoke         # one year of B-H, timings and counts only (scratch output)
    python3 -m analysis_2026.scalp_us_daily --run           # full primary analysis, exploratory, B6, Part D
    python3 -m analysis_2026.scalp_us_daily --run --nulls 20   # plus the 20 null panels (Control (i), PASS condition 8)
    python3 -m analysis_2026.scalp_us_daily --nulls 20      # null panels only; rerun --run afterwards for cond_null
    (--br-root DIR reads daily_split/daily_none.parquet from DIR instead of data/scalping/rh)

Data (gitignored): data/scalping/qlib/panel.parquet (B-H), data/scalping/ref/*.csv (ETF flags and names),
data/raw_pit/ (S&P 500 point-in-time set), data/macro/VIXCLS.csv, data/scalping/rh_pilot/ (pilot quotes and
the 40 pilot names' daily bars), and, once pulled, data/scalping/rh/{universe.csv, daily_split.parquet,
daily_none.parquet} (B-R). Without B-R the cost model is fitted on the 40 pilot names and R_y's denominator
uses them too; both are flagged in cost_model.csv and summary.txt.

Outputs: analysis_2026/results_scalping/B/ (cost_model.csv first, before any return; primary_cells.csv with
the 16 B and 4 E cells; cell_report.csv; exploratory.csv; illusion.csv; b6.csv; exclusions.csv;
descriptive.csv; controls_*.csv; null_panels.csv; summary.txt), analysis_2026/results_scalping/D/ (d1-d4,
summary.txt) and per-trade parquet files under data/scalping/B/. Returns are fractions (0.0005 = 5 bp).
primary_cells.csv holds no verdict: Holm over all 36 tests is applied by the combine script. A cond_* cell
that is empty could not be evaluated (e.g. cond_br before the B-R bars exist) and must count as not met;
cond_* = True where the condition does not apply to the cell (cond_skip for B3/B4, cond_m2 for L3/L4).

Implementation choices (where the pre-registration is silent or ambiguous; the more conservative reading
was taken where one exists; none was changed after seeing a result):
 1. Real bars. B-H: a panel row that passes the data screen. B-R: a non-interpolated bar that passes it.
    Zero-volume bars are real but untraded: they count toward the 40-bar rule and enter EDGE and sigma, but
    cannot be signal, entry, fill or exit days. Exits ("the close of the next real bar") therefore use the
    next bar with volume > 0; the -30% rule applies when there is none within 20 trading days of the
    scheduled exit day (days es..es+20). The "last close" is the last traded close before the gap.
 2. The data screen compares prices with a 2e-6 relative tolerance (qlib prices are float32 products of a
    raw price and a factor, so an exact low == open can come back 1 ulp apart). One-price day: high == low
    within the same tolerance. The split screen fires when close_t/close_{t-1} and open_t/close_{t-1} are
    each within 2% of any listed ratio (the broader of the two readings).
 3. Traded-price proxy (B-H). The k window is the real bars of the last 60 exchange trading days ending at t
    (inclusive; the general "Windows" rule). A value is on the 0.01k grid when its distance to the grid is
    <= max(0.005 x grid step, 3e-7 x value): the second term is the float32 error of close/factor and only
    binds above ~$170. The k of the signal day is used for every price-level rule of that trade (limit,
    tick, trade-throughs), so a trade never mixes grids. B-R uses unadjusted prices directly (k = 1) and the
    off-grid exclusion, which the pre-registration defines for qlib's P, is not applied to B-R.
 4. s_it "data to t-1": EDGE, ADV60, sigma60 and the tick term use data through t-1 (P of the last real bar
    before t). Each taker leg pays the cost as of its own day: s, sigma20, ADV60, c and D_k of that day.
    Below L1 (ADV60 < $50k, possible on exit days) c = 1.25 and D_k = $974 (L1 values).
 5. sigma20 = SD of simple returns between consecutive real bars inside the 20-day window (data to t-1;
    B3's sigma_t uses data to t); with fewer than 5 such returns the 60-day window is used. sigma60 for the
    cost model = SD of log returns between consecutive real bars inside the 60-day window. EDGE runs on the
    window's real bars in sequence (as in the pilot) with float32-safe equality (|log a - log b| <= 1e-6);
    otherwise it is bidask 2.1.0's edge() line by line (checked in tests against the pilot's copy).
 6. r_t needs a real bar on the previous exchange trading day. Deciles are taken over the band's eligible
    names with a finite r_t (names whose signal cannot fire still define the decile); r_t <= the 10th
    percentile (numpy linear) for B1/B2, >= the 90th for E1; a band-day needs >= 10 such names.
 7. "Gross (m = 0)" (PASS condition 4 and Control (ii)) zeroes the spread term only; impact at Y = 0.5 and
    sell fees stay (the condition is harder to meet).
 8. Newey-West lags = max(10, h + 4) for the strategy cells (h = scheduled holding days; B4 counts its GTC
    sessions + 1); D2 uses h + 4 as written. The D_t series has a value on every exchange trading day of
    the sample (signal date), zero on days without a trade.
 9. Edge for the NO EDGE rule (per trade-day held) = sum(w x) / sum(w h), where h = trading sessions in which
    the position was exposed (close entry: exit day - entry day; intraday entry: exit day - entry day + 1;
    B4 averages its pieces), with a Newey-West delta-method SE (scalp_stats.nw_ratio).
10. qlib freezes 2,155 names at 2020-11-10 (after the sample end, 2020-10-30). A series that ends after the
    sample end is censored, not delisted: a missing exit is taken at its last traded close (0% penalty).
    A window cut off by the panel end (B-R's last days) drops the trade.
11. Fees on sells. B-R by trade date: SEC $8.00/$M to 2024-05-21 [memory], $27.80 to 2025-05-13, $0 to
    2026-04-03, $20.60 after; TAF $0.000145/sh (cap $7.27) in 2023 [memory], $0.000166 ($8.30) 2024-25,
    $0.000195 ($9.79) 2026-01..09, $0 from 2026-10-01; Robinhood skips SEC on sales <= $500 and TAF on <= 50
    shares. B-H: the historical schedules are not in the repo (sec.gov is unreachable), so an upper bound is
    charged throughout: SEC 0.30 bp (the pre-registration's stated bound) + TAF $0.000119/sh (cap $5.95).
12. B3's limit L is rounded down to the cent (a limit must be a whole cent; same as B4's B). B4's sell
    fraction f = (high - A)/(high - low) clipped to [0, 1] (Part C's rule), 1 on a one-price day.
13. B4: one position per name within each band cell (each cell is run as its own strategy; the band is the
    band of the order date). A name can be bid again from the close of the day its position is closed.
    The five GTC sessions are t+2..t+6; the remainder is sold at the close of t+6 (gap rule if no bar).
14. Band excess for B4's tail: x = (1 + r1)(1 + r_after - bench_after) - 1, with bench_after the benchmark from
    close(t+1) to each piece's exit day, weighted by the piece's share fraction. Benchmark names must have a
    traded bar at the start of the benchmark window (close t+1 for B4 and skip-a-day).
15. R_y: name-days with band L1-L4, not excluded, >= 40 real bars, on-grid (B-H), P >= $1 and finite EDGE
    (raw, without c) and M (without R_y); year y-1 by calendar year (2001 uses 2000).
16. Cost model: regressors ADV60 (median close x volume, $0 for missing days, 60 days ending 2026-10-15),
    sigma60 (log, same days), P = the unadjusted 2026-10-16 close (the scanner's Close where no bar);
    y = log((ask - bid)/mid) of the 2026-10-16 closing quote; every name with finite regressors is used.
17. Rule (e): R^2 needs >= 100 paired daily returns in the 250-day window. B6's twin is the fund with the
    highest R^2 (so inverse funds are matched), with beta from the same window; the residual SD uses that
    twin and beta over the 60-day window. International = twin EFA or EEM, or a name matching
    International|Emerging|Global|World|Europe|Asia|Pacific|Japan|China|India|Brazil|Latin|Korea|Taiwan|
    Germany|Canada|Mexico|Africa|Frontier|ex-US.
18. B6's universe: rule (a), or rule (b) through ETF|ETN|Fund|Closed-End only (preferreds, notes, warrants,
    rights and units are not funds), not rule (c), plus rule-(e) name-days.
19. Peak capital = the maximum over half-day slots of the entry cost of open positions (a sale and a buy at
    the same close reuse the proceeds). Tax: 35% is applied to a positive annual net return only; SPY
    buy-and-hold pays 20% on its gain at the end.
20. Null panels (Control (i)): each name keeps its real-bar calendar, exclusion flags, k and on-grid flags;
    its bars are redrawn with replacement (numpy default_rng([20261018, j])) from its own real bars that
    follow a real bar; prices are rebuilt from the first real close. The cost model and R_y stay at their
    real-data values (they are fixed before any return).
21. D3: capital is recycled at the close; each day K minus the entry cost of still-open positions is split
    equally across that day's orders (for B3/B4 the limit orders placed); caps 10% of the entry day's $
    volume (x f for limit fills), 4.9% of shares outstanding (B-R only; current snapshot, not point in time),
    20% of ADV60 per exit day. Positions sold over several days pay each day's cost at that day's size.
22. D4: the permanent impact is 2/3 of the buy-weighted mean of the daily temporary impacts; band EW returns
    are measured from the close before the first buy to the paper mark (last buy day) and to the last sale.
23. Control (ii)/(iii) on the S&P PIT set: one band (the day's eligible members); the traded price is rebuilt
    from the split column (close x later split ratios); rows without volume (CRSP close-only) skip the
    volume conditions and pay no impact; "members qlib has on each date" = a qlib row for the ticker (the
    PIT suffix -YYYYMM stripped) on that date.
24. Synthetic no-edge control (General rules): per band L1-L4, 300 names x 1,000 days of Poisson trades at
    a random-walk mid +- half the band's median spread estimate, aggressor side independent of the mid,
    aggregated to daily OHLCV on a cent grid; the band's median sigma20, ADV60 and zero-volume share set the
    parameters. B1-B4 and E1 run unchanged (cost model fixed, R_y = 1).
25. B-R universe: universe.csv rows with keep != 1 or an excl_reason are dropped (the scan's asset type and
    name filter), then rules (b)-(d) on the scan names and the listing files. Liquid names come from
    data/universe_recent_raw (2024-08 onward) for symbols the scan does not list, after rules (a)-(d); they are
    split-adjusted only, so their price-level rules use split-adjusted prices (they are mostly L5/L6 names).
    B-R returns are split-adjusted, not dividend-adjusted (Robinhood's "all" adjustment is intraday only).
Points where the pre-registration could not be followed are listed in summary.txt (B-R and its universe
not yet pulled; shares outstanding only in B-R; historical B-H fee schedules).
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from numba import njit, prange

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.scalp_stats import drop_worst, holm, mde, nw_ratio, nw_t, upper_bound  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SC = DATA / "scalping"
OUT = ROOT / "analysis_2026" / "results_scalping"
SCRATCH = Path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad")
BH_START, BH_END = "2001-04-09", "2020-10-30"
BH_HALF2 = "2011-01-01"
BR_START, BR_END = "2023-07-03", "2026-10-16"
BAND_EDGES = [50e3, 150e3, 500e3, 1.5e6, 5e6, 50e6]          # L1..L6 lower bounds
BANDS = ["", "L1", "L2", "L3", "L4", "L5", "L6"]
DEPTH = np.array([974., 974., 1465., 3056., 8152., 8152., 8152.])   # D_k by band index (0 = below L1)
C_EDGE = np.array([1.25, 1.25, 1 / 1.4, 1 / 1.4, 1 / 1.4, 1 / 1.4, 1 / 1.4])
W60, W20 = 60, 20
EQTOL = 1e-6                     # log-price equality tolerance in EDGE
PTOL = 2e-6                      # relative price tolerance in the data screen
E_THRESH = 0.0005                # +5 bp per trade-day held
Q0 = 10_000.0
M0, Y0 = 1.5, 0.5
SPLIT_RATIOS = np.array([1 / 2, 1 / 3, 2 / 3, 1 / 4, 1 / 5, 1 / 8, 1 / 10, 1 / 20, 2, 3, 1.5, 4, 5, 8, 10, 20])
FUNDS_E = ["SPY", "QQQ", "IWM", "MDY", "DIA", "EFA", "EEM", "AGG", "TLT", "IEF", "LQD", "HYG", "GLD", "SLV", "USO",
           "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
FUNDS_B6 = FUNDS_E + ["VNQ"]
RX_B = re.compile(r"\b(ETF|ETN|Fund|Notes?|Debentures?|Preferred|Warrants?|Rights?|Units?|Closed[- ]End|Trust Units)\b",
                  re.I)
RX_FUND = re.compile(r"\b(ETF|ETN|Fund|Closed[- ]End)\b", re.I)
RX_INTL = re.compile(r"\b(International|Emerging|Global|World|Europe|European|Asia|Pacific|Japan|China|India|Brazil|"
                     r"Latin|Korea|Taiwan|Germany|Canada|Mexico|Africa|Frontier|ex-US)\b", re.I)
D5_LETTERS = set("GHIMNOPRTUVWXZ")
STRATS = ["B1", "B2", "B3", "B4", "E1"]


# ============================================================================ numba kernels

@njit(parallel=True, cache=True)
def _screen(O, H, L, C, present, tol):
    """Real bar = present, OHLC > 0, low <= min(open, close), high >= max(open, close) (relative tolerance)."""
    N, T = C.shape
    real = np.zeros((N, T), np.bool_)
    for i in prange(N):
        for t in range(T):
            if not present[i, t]:
                continue
            o, h, l, c = O[i, t], H[i, t], L[i, t], C[i, t]
            if not (o > 0 and h > 0 and l > 0 and c > 0):
                continue
            if l > min(o, c) * (1 + tol) or h < max(o, c) * (1 - tol):
                continue
            real[i, t] = True
    return real


@njit(parallel=True, cache=True)
def _grid(VC, real, W, KMAX):
    """Traded-price divisor k (largest k in 2..KMAX with >= 90% of the window's values on the $0.01k grid,
    else 1) and the on-grid flag (k > 1, or >= 90% on the cent grid); window = real bars in [t-W+1, t]."""
    N, T = VC.shape
    KK = np.ones((N, T), np.float32)
    OG = np.zeros((N, T), np.bool_)
    for i in prange(N):
        bits = np.zeros(T, np.int64)
        idx = np.empty(T, np.int64)
        n = 0
        for t in range(T):
            if real[i, t]:
                v = VC[i, t]
                b = 0
                eps = 3e-7 * v
                for k in range(1, KMAX + 1):
                    g = 0.01 * k
                    z = v / g
                    if abs(z - np.round(z)) * g <= max(0.005 * g, eps):
                        b |= (1 << (k - 1))
                bits[t] = b
                idx[n] = t
                n += 1
        cnt = np.zeros(KMAX + 1, np.int64)
        lo = 0
        for jj in range(n):
            t = idx[jj]
            b = bits[t]
            for k in range(1, KMAX + 1):
                if (b >> (k - 1)) & 1:
                    cnt[k] += 1
            while idx[lo] < t - (W - 1):
                bo = bits[idx[lo]]
                for k in range(1, KMAX + 1):
                    if (bo >> (k - 1)) & 1:
                        cnt[k] -= 1
                lo += 1
            m = jj - lo + 1
            kb = 1
            for k in range(KMAX, 1, -1):
                if cnt[k] >= 0.9 * m:
                    kb = k
                    break
            KK[i, t] = kb
            OG[i, t] = (kb > 1) or (cnt[1] >= 0.9 * m)
    return KK, OG


@njit(cache=True)
def _edge(o, h, l, c, a, b, tol):
    """EDGE (Ardia-Guidotti-Kroencke 2024; bidask 2.1.0 logic) on log prices of bars a..b-1 in sequence."""
    n = b - a - 1
    if n < 2:
        return np.nan
    s1 = 0.0; s3 = 0.0; s5 = 0.0; st = 0.0; so1 = 0.0; so2 = 0.0; sc1 = 0.0; sc2 = 0.0
    for j in range(a + 1, b):
        m = 0.5 * (h[j] + l[j])
        tau = 1.0 if (abs(h[j] - l[j]) > tol or abs(l[j] - c[j - 1]) > tol) else 0.0
        s1 += m - o[j]; s3 += m - c[j - 1]; s5 += o[j] - c[j - 1]; st += tau
        if abs(o[j] - h[j]) > tol: so1 += tau
        if abs(o[j] - l[j]) > tol: so2 += tau
        if abs(c[j - 1] - h[j - 1]) > tol: sc1 += tau
        if abs(c[j - 1] - l[j - 1]) > tol: sc2 += tau
    pt = st / n; po = (so1 + so2) / n; pc = (sc1 + sc2) / n
    if st < 2 or po == 0 or pc == 0:
        return np.nan
    k1 = (s1 / n) / pt; k3 = (s3 / n) / pt; k5 = (s5 / n) / pt
    e1 = 0.0; e2 = 0.0; q1 = 0.0; q2 = 0.0
    for j in range(a + 1, b):
        m = 0.5 * (h[j] + l[j]); m1 = 0.5 * (h[j - 1] + l[j - 1])
        tau = 1.0 if (abs(h[j] - l[j]) > tol or abs(l[j] - c[j - 1]) > tol) else 0.0
        r1 = m - o[j]; r2 = o[j] - m1; r3 = m - c[j - 1]; r4 = c[j - 1] - m1; r5 = o[j] - c[j - 1]
        d1 = r1 - k1 * tau; d3 = r3 - k3 * tau; d5 = r5 - k5 * tau
        x1 = -4.0 / po * d1 * r2 - 4.0 / pc * d3 * r4
        x2 = -4.0 / po * d1 * r5 - 4.0 / pc * d5 * r4
        e1 += x1; e2 += x2; q1 += x1 * x1; q2 += x2 * x2
    e1 /= n; e2 /= n
    v1 = q1 / n - e1 * e1; v2 = q2 / n - e2 * e2
    vt = v1 + v2
    s2 = (v2 * e1 + v1 * e2) / vt if vt > 0 else 0.5 * (e1 + e2)
    return math.sqrt(abs(s2))


@njit(cache=True)
def _med0(vals, lo, hi, W, buf):
    """Median of W values = vals[lo:hi] plus (W - (hi - lo)) zeros."""
    m = hi - lo
    for j in range(m):
        buf[j] = vals[lo + j]
    sv = np.sort(buf[:m])
    z = W - m
    a = W // 2 - 1; b = W // 2
    va = 0.0 if a < z else sv[a - z]
    vb = 0.0 if b < z else sv[b - z]
    return 0.5 * (va + vb)


@njit(cache=True)
def _sd(x, a, b):
    n = b - a
    if n < 2:
        return np.nan
    s = 0.0
    for j in range(a, b):
        s += x[j]
    mu = s / n
    v = 0.0
    for j in range(a, b):
        v += (x[j] - mu) ** 2
    return math.sqrt(v / (n - 1))


@njit(parallel=True, cache=True)
def _trail(O, H, L, C, F, DV, SV, KK, real, W, W20, tol):
    """Trailing statistics at index t from data through t-1 (window = exchange days t-W..t-1).
    Returns ADV60 ($ volume median, missing days $0), VMED60 (share volume median), NR (real bars), EDGE,
    SIG60 (SD of log returns), SIG20 (SD of simple returns, 20-day window), PPV (traded price, last real bar
    before t)."""
    N, T = C.shape
    ADV = np.full((N, T), np.nan, np.float32); VMED = np.full((N, T), np.nan, np.float32)
    NR = np.zeros((N, T), np.int16); EDG = np.full((N, T), np.nan, np.float32)
    S60 = np.full((N, T), np.nan, np.float32); S20 = np.full((N, T), np.nan, np.float32)
    PPV = np.full((N, T), np.nan, np.float32)
    for i in prange(N):
        idx = np.empty(T, np.int64)
        n = 0
        for t in range(T):
            if real[i, t]:
                idx[n] = t
                n += 1
        if n == 0:
            continue
        lo_ = np.empty(n); lh = np.empty(n); ll = np.empty(n); lc = np.empty(n)
        lr = np.full(n, np.nan); sr = np.full(n, np.nan); dv = np.empty(n); sv = np.empty(n)
        for j in range(n):
            t = idx[j]
            lo_[j] = math.log(O[i, t]); lh[j] = math.log(H[i, t]); ll[j] = math.log(L[i, t])
            lc[j] = math.log(C[i, t])
            dv[j] = DV[i, t] if DV[i, t] == DV[i, t] else 0.0
            sv[j] = SV[i, t] if SV[i, t] == SV[i, t] else 0.0
            if j > 0:
                tp = idx[j - 1]
                lr[j] = math.log(C[i, t] * F[i, t] / (C[i, tp] * F[i, tp]))
                sr[j] = math.exp(lr[j]) - 1.0
        buf = np.empty(W)
        lo = 0; hi = 0; lo20 = 0
        tend = min(T, idx[n - 1] + W + 1)
        for t in range(idx[0] + 1, tend):
            while hi < n and idx[hi] <= t - 1:
                hi += 1
            while lo < hi and idx[lo] < t - W:
                lo += 1
            while lo20 < hi and idx[lo20] < t - W20:
                lo20 += 1
            m = hi - lo
            NR[i, t] = m
            PPV[i, t] = C[i, idx[hi - 1]] / KK[i, idx[hi - 1]]
            ADV[i, t] = _med0(dv, lo, hi, W, buf)
            VMED[i, t] = _med0(sv, lo, hi, W, buf)
            if m >= 3:
                EDG[i, t] = _edge(lo_, lh, ll, lc, lo, hi, tol)
                S60[i, t] = _sd(lr, lo + 1, hi)
            if hi - lo20 >= 6:
                S20[i, t] = _sd(sr, lo20 + 1, hi)
            elif m >= 3:
                S20[i, t] = _sd(sr, lo + 1, hi)
    return ADV, VMED, NR, EDG, S60, S20, PPV


@njit(cache=True)
def _find_traded(i, es, traded, T, maxgap):
    hi = min(es + maxgap, T - 1)
    for d in range(es, hi + 1):
        if traded[i, d]:
            return d
    return -1


@njit(parallel=True, cache=True)
def _legs(ii, tt, a_off, a_open, b_off, b_open, O, C, F, traded, last_tr, sample_end):
    """Entry at day t+a_off (open or close; needs a traded bar that day), exit at the scheduled day t+b_off
    (open or close) or the next traded bar within 20 days. flag: 0 normal, 1 delisting rule (g from glast in
    python), 2 censored after the sample end (exit at the last traded close), 3 dropped (window cut by the
    panel end), -1 no entry."""
    n = len(ii)
    T = C.shape[1]
    ent = np.full(n, -1, np.int64); ext = np.full(n, -1, np.int64)
    g = np.full(n, np.nan); glast = np.full(n, np.nan); flag = np.full(n, -1, np.int8)
    for k in prange(n):
        i = ii[k]; t = tt[k]; a = t + a_off
        if a >= T or not traded[i, a]:
            continue
        pe = (O[i, a] if a_open else C[i, a]) * F[i, a]
        es = t + b_off
        if es >= T:
            flag[k] = 3
            continue
        ent[k] = a
        if es < a or (es == a and not (a_open and not b_open)):
            es = a + 1                   # only an open entry may exit at the same day's close
        d = _find_traded(i, es, traded, T, 20)
        if d >= 0:
            px = (O[i, d] if b_open else C[i, d]) * F[i, d]
            ext[k] = d; g[k] = px / pe - 1.0; flag[k] = 0
            continue
        if es + 20 > T - 1:
            flag[k] = 3
            continue
        dl = es - 1
        while dl > a and not traded[i, dl]:
            dl -= 1
        glast[k] = C[i, dl] * F[i, dl] / pe - 1.0
        ext[k] = dl
        if last_tr[i] < es and last_tr[i] > sample_end:
            g[k] = glast[k]; flag[k] = 2
        else:
            flag[k] = 1
    return ent, ext, g, glast, flag


@njit(cache=True)
def _b4_engine(elig, C, F, H, L, O, KK, DV, traded, WCL, WCH, S, last_tr, sample_end, s0, s1, Q, NS, tgt, touch,
               maxn):
    """B4 (the friend's rule, daily) for one band cell. Per name: at the close of an eligible day t with no
    open position, a day-limit buy for t+1 at B = floor_cent(P_t (1 - s_t/2)); fill if low_{t+1} <= B - tick
    (whole-cent low on B-R), size q = min(Q, 10% $vol_{t+1} f). From t+2 a GTC sell at A = ceil_cent(B (1 + s_t))
    (tgt > 0: B (1 + tgt)) fills if high >= A + tick, at most 10% of the day's $ volume x f per day. The
    remainder after NS sessions is sold at the close of t+1+NS (gap rule). Returns per-trade arrays and
    per-piece fractions (NS GTC pieces + the forced piece)."""
    N, T = C.shape
    ti = np.empty(maxn, np.int64); ii = np.empty(maxn, np.int64); qq = np.empty(maxn); r1 = np.empty(maxn)
    Bp = np.empty(maxn); Ap = np.empty(maxn)
    phi = np.zeros((maxn, NS + 1)); pg = np.full((maxn, NS + 1), np.nan)     # share fraction, gross from close t+1
    pnot = np.zeros((maxn, NS + 1)); psh = np.zeros((maxn, NS + 1))          # $ notional and shares sold
    fday = np.full(maxn, -1, np.int64); fflag = np.full(maxn, -1, np.int8); fglast = np.full(maxn, np.nan)
    on = np.zeros(maxn); hold = np.zeros(maxn)
    nt = 0
    nord = np.zeros(T, np.int64)                  # limit buys placed per signal day
    for i in range(N):
        t = s0
        while t <= s1 and t < T - 2:
            if not elig[i, t]:
                t += 1
                continue
            kk = KK[i, t]
            P = C[i, t] / kk
            B = math.floor(P * (1 - S[i, t] / 2) * 100 + 1e-7) / 100
            t1 = t + 1
            if B <= 0:
                t += 1
                continue
            nord[t] += 1
            if not traded[i, t1]:
                t += 1
                continue
            lo = L[i, t1] / kk; hi = H[i, t1] / kk
            ok = (lo <= B + 1e-6 * B) if touch else (lo <= B - 0.01 + 1e-6 * B and WCL[i, t1])
            if not ok:
                t += 1
                continue
            f = 1.0 if hi - lo <= 1e-6 * hi else min(max((B - lo) / (hi - lo), 0.0), 1.0)
            q = min(Q, 0.1 * DV[i, t1] * f)
            if q <= 0:
                t += 1
                continue
            A = math.ceil(B * (1 + (tgt if tgt > 0 else S[i, t])) * 100 - 1e-7) / 100
            sh = q / B
            rem = sh
            Bc = B * kk
            v1 = C[i, t1] * F[i, t1]
            k = nt
            ti[k] = t; ii[k] = i; qq[k] = q; Bp[k] = B; Ap[k] = A
            r1[k] = C[i, t1] / Bc - 1.0
            ov = 0.0                         # overnight log return held (share-weighted), exploratory split
            dlast = t1
            for j in range(NS):
                e = t + 2 + j
                if e >= T or rem <= 0:
                    break
                if traded[i, e - 1] and traded[i, e]:
                    ov += rem / sh * math.log(O[i, e] / C[i, e - 1])
                if not traded[i, e]:
                    continue
                h_ = H[i, e] / kk; l_ = L[i, e] / kk
                hit = (h_ >= A - 1e-6 * A) if touch else (h_ >= A + 0.01 - 1e-6 * A and WCH[i, e])
                if not hit:
                    continue
                fs = 1.0 if h_ - l_ <= 1e-6 * h_ else min(max((h_ - A) / (h_ - l_), 0.0), 1.0)
                cap = 0.1 * DV[i, e] * fs / A
                sell = min(rem, cap)
                if sell <= 0:
                    continue
                phi[k, j] = sell / sh
                pg[k, j] = A * kk * F[i, e] / v1 - 1.0
                pnot[k, j] = sell * A; psh[k, j] = sell
                rem -= sell
                dlast = e
            hd = 0.0
            for j in range(NS):
                hd += phi[k, j] * (j + 2)
            if rem > 1e-12 * sh:
                es = t + 1 + NS
                fr = rem / sh
                phi[k, NS] = fr
                psh[k, NS] = rem
                if es >= T:
                    fflag[k] = 3
                    dlast = T
                else:
                    d = _find_traded(i, es, traded, T, 20)
                    if d >= 0:
                        fday[k] = d; fflag[k] = 0
                        pg[k, NS] = C[i, d] * F[i, d] / v1 - 1.0
                        dlast = d
                    elif es + 20 > T - 1:
                        fflag[k] = 3
                        dlast = T
                    else:
                        dl = es - 1
                        while dl > t1 and not traded[i, dl]:
                            dl -= 1
                        fglast[k] = C[i, dl] * F[i, dl] / v1 - 1.0
                        fday[k] = dl
                        if last_tr[i] < es and last_tr[i] > sample_end:
                            fflag[k] = 2; pg[k, NS] = fglast[k]
                        else:
                            fflag[k] = 1
                        dlast = es + 20
                hd += fr * (max(fday[k], es) - t)
            on[k] = ov
            hold[k] = hd
            nt += 1
            if nt >= maxn:
                break
            t = max(dlast, t + 1)
        if nt >= maxn:
            break
    return (ti[:nt], ii[:nt], qq[:nt], r1[:nt], Bp[:nt], Ap[:nt], phi[:nt], pg[:nt], pnot[:nt], psh[:nt],
            fday[:nt], fflag[:nt], fglast[:nt], on[:nt], hold[:nt], nord)


# ============================================================================ panels

_UID = [0]


def _uid():
    _UID[0] += 1
    return _UID[0]


def _empty(N, T, dtype=np.float32, fill=np.nan):
    return np.full((N, T), fill, dtype)


def panel_from_long(df: pd.DataFrame, dates, name, kind, sample, fields=("open", "high", "low", "close")):
    """Long frame (ticker, date, open, high, low, close, sv, fret, kk, wcl, wch) -> (N, T) arrays.
    O/H/L/C are continuous split-adjusted prices, F the factor that turns them into total-return prices,
    SV split-adjusted shares, KK the traded-price divisor (P = C / KK)."""
    dates = pd.DatetimeIndex(dates)
    cat = pd.Categorical(df.ticker)
    cat = cat.remove_unused_categories() if hasattr(cat, "remove_unused_categories") else cat
    order = np.argsort(np.asarray(cat.categories, dtype=str))
    tick = np.asarray(cat.categories, dtype=str)[order]
    remap = np.empty(len(order), np.int64); remap[order] = np.arange(len(order))
    ti = remap[cat.codes]
    di = dates.get_indexer(df.date)
    ok = di >= 0
    ti, di, df = ti[ok], di[ok], df[ok]
    N, T = len(tick), len(dates)
    P = SimpleNamespace(name=name, kind=kind, dates=dates, tickers=tick, N=N, T=T, uid=_uid())
    for a, col in (("O", "open"), ("H", "high"), ("L", "low"), ("C", "close"), ("SV", "sv")):
        m = _empty(N, T); m[ti, di] = df[col].to_numpy(np.float32); setattr(P, a, m)
    P.F = _empty(N, T, fill=1.0)
    if "fret" in df:
        P.F[ti, di] = df.fret.to_numpy(np.float32)
    P.present = np.zeros((N, T), bool); P.present[ti, di] = True
    P.KK = _empty(N, T, fill=1.0)
    if "kk" in df:
        P.KK[ti, di] = df.kk.to_numpy(np.float32)
    P.WCL = np.ones((N, T), bool); P.WCH = np.ones((N, T), bool)
    if "wcl" in df:
        P.WCL[ti, di] = df.wcl.to_numpy(bool); P.WCH[ti, di] = df.wch.to_numpy(bool)
    P.s0 = int(np.searchsorted(dates.values, np.datetime64(sample[0])))
    P.s1 = int(np.searchsorted(dates.values, np.datetime64(sample[1]), side="right") - 1)
    return P


def finish_panel(P, grid: bool):
    """Data screen, traded-price proxy, $ volume, last traded index."""
    P.real = _screen(P.O, P.H, P.L, P.C, P.present, PTOL)
    P.traded = P.real & (P.SV > 0)
    dv = P.C.astype(np.float64) * P.SV                 # continuous close x split-adjusted shares = traded $ volume
    P.DV = np.clip(dv, 0, 3e38).astype(np.float32)
    if grid:
        VC = P.C.astype(np.float64)
        P.KK, P.ONGRID = _grid(VC, P.real, W60, 50)
    elif not hasattr(P, "ONGRID"):
        P.ONGRID = np.ones((P.N, P.T), bool)
    tr = P.traded
    last = np.where(tr.any(1), P.T - 1 - np.argmax(tr[:, ::-1], 1), -1)
    P.last_tr = last.astype(np.int64)
    if not hasattr(P, "excl"):
        P.excl = np.zeros((P.N, P.T), bool)
    return P


def load_ref():
    n = pd.read_csv(SC / "ref" / "nasdaq-listed-symbols.csv")
    n = n[n.Symbol.notna() & ~n.Symbol.astype(str).str.startswith("File Creation")]
    o = pd.read_csv(SC / "ref" / "other-listed.csv")
    rows = [n[["Symbol", "Security Name", "ETF"]].set_axis(["sym", "name", "etf"], axis=1)]
    for c in ("ACT Symbol", "NASDAQ Symbol"):
        rows.append(o[[c, "Security Name", "ETF"]].set_axis(["sym", "name", "etf"], axis=1))
    r = pd.concat(rows).dropna(subset=["sym"])
    r["sym"] = r.sym.astype(str).str.upper()
    r["name"] = r.name.astype(str)
    g = r.groupby("sym").agg(etf=("etf", lambda x: (x == "Y").any()),
                             b=("name", lambda x: any(RX_B.search(s) for s in x)),
                             bfund=("name", lambda x: any(RX_FUND.search(s) for s in x)),
                             intl=("name", lambda x: any(RX_INTL.search(s) for s in x)),
                             name=("name", "first"))
    return g


def static_rules(tickers, ref, names=None):
    """Exclusion rules (a)-(d) per symbol; names (optional dict) adds B-R's own security names to rule (b)."""
    rows = []
    for s in tickers:
        known = s in ref.index
        a = bool(known and ref.at[s, "etf"])
        b = bool(known and ref.at[s, "b"])
        bf = bool(known and ref.at[s, "bfund"])
        nm = names.get(s) if names else None
        if nm and isinstance(nm, str):
            b = b or bool(RX_B.search(nm)); bf = bf or bool(RX_FUND.search(nm))
        c = bool(re.search(r"[\^\-\._]", s))
        d = len(s) == 5 and s.isalpha() and s[4] in D5_LETTERS
        intl = bool(known and ref.at[s, "intl"]) or bool(nm and isinstance(nm, str) and RX_INTL.search(nm))
        rows.append((s, known, a, b, bf, c, d, intl))
    return pd.DataFrame(rows, columns=["ticker", "known", "a", "b", "bfund", "c", "d", "intl"]).set_index("ticker")


def load_qlib_long(start, end, tickers=None):
    cols = ["ticker", "date", "open", "high", "low", "close", "volume", "factor"]
    p = pd.read_parquet(SC / "qlib" / "panel.parquet", columns=cols,
                        filters=[("date", ">=", pd.Timestamp(start)), ("date", "<=", pd.Timestamp(end))])
    if tickers is not None:
        p = p[p.ticker.isin(set(tickers))]
    f = p.factor.to_numpy(np.float64)
    out = pd.DataFrame({"ticker": p.ticker.values, "date": p.date.values})   # ticker stays categorical
    for c in ("open", "high", "low", "close"):
        out[c] = (p[c].to_numpy(np.float64) / f).astype(np.float32)       # Yahoo split-adjusted price
    out["sv"] = (p.volume.to_numpy(np.float64) * f).astype(np.float32)     # split-adjusted shares
    out["fret"] = f.astype(np.float32)                                     # x continuous = qlib adjusted close
    del p
    return out.dropna(subset=["close"])


def load_bh(start="2000-01-03", end="2021-03-31", sample=(BH_START, BH_END)):
    """B-H panels: stocks (not excluded by (a)-(d); rule (e) applied later) and funds (B6 + rule (e) twins)."""
    ref = load_ref()
    q = load_qlib_long(start, end)
    dates = pd.DatetimeIndex(np.sort(q.date.unique()))
    present = q.ticker.astype("category").cat.remove_unused_categories().cat.categories
    rules = static_rules(sorted(map(str, present)), ref)
    stock = rules.index[~(rules.a | rules.b | rules.c | rules.d)]
    fund = rules.index[((rules.a | rules.bfund) & ~rules.c) | rules.index.isin(FUNDS_B6)]
    S = panel_from_long(q[q.ticker.isin(set(stock))], dates, "B-H", "BH", sample)
    Fd = panel_from_long(q[q.ticker.isin(set(fund))], dates, "B-H funds", "BH", sample)
    del q
    _trim()
    S = finish_panel(S, grid=True); Fd = finish_panel(Fd, grid=True)
    S.rules = rules.loc[S.tickers]; Fd.rules = rules.loc[Fd.tickers]
    S.all_rules = rules
    return S, Fd


def _rh_daily(path):
    d = pd.read_parquet(path)
    if "session" in d:
        d = d[d.session.isna() | d.session.isin(["reg", "regular"])]
    d = d.copy()
    d["date"] = pd.to_datetime(d.begins_at, utc=True).dt.tz_localize(None).dt.normalize()
    return d.rename(columns={"symbol": "ticker"})


def load_br(sample=(BR_START, BR_END), root=None):
    """B-R panel from Robinhood daily bars (split-adjusted for returns, unadjusted for price levels). Returns
    None if the bars have not been pulled yet (python3 -m analysis_2026.fetch_scalping_data rh-combine)."""
    root = Path(root) if root else SC / "rh"
    ps, pn, pu = root / "daily_split.parquet", root / "daily_none.parquet", SC / "rh" / "universe.csv"
    if not (ps.exists() and pn.exists()):
        return None
    s = _rh_daily(ps); u = _rh_daily(pn)
    m = s.merge(u[["ticker", "date", "open", "high", "low", "close", "interpolated"]], on=["ticker", "date"],
                suffixes=("", "_u"), how="left")
    # liquid names (L5/L6) from data/universe_recent_raw, 2024-08 onward, for symbols the scan does not cover
    lq = DATA / "universe_recent_raw" / "prices.parquet"
    if lq.exists():
        r = pd.read_parquet(lq, columns=["date", "ticker", "open", "high", "low", "close", "volume"])
        r = r[~r.ticker.isin(set(m.ticker))].copy()
        ref = load_ref()
        rr = static_rules(sorted(r.ticker.unique()), ref)
        r = r[r.ticker.isin(set(rr.index[~(rr.a | rr.b | rr.c | rr.d)]))]
        r["date"] = pd.to_datetime(r.date).dt.normalize()
        r = r[r.date <= pd.Timestamp(sample[1])]
        r["interpolated"] = False
        for c in ("open", "high", "low", "close"):
            r[c + "_u"] = r[c]                                   # unadjusted not available: price-level rules use split-adjusted
        m = pd.concat([m, r], ignore_index=True)
    return _br_from_merged(m, sample, pu if pu.exists() else None, "B-R")


def _br_from_merged(m, sample, universe_path, name):
    m = m[~m.interpolated.fillna(False).astype(bool)].copy()
    for c in ("open", "high", "low", "close"):
        m[c + "_u"] = m[c + "_u"].fillna(m[c])
    m["kk"] = m.close / m.close_u
    m["sv"] = m.volume.astype(float)
    wc = lambda x: np.abs(np.round(x * 100) - x * 100) < 1e-6        # noqa: E731
    m["wcl"] = wc(m.low_u.to_numpy()); m["wch"] = wc(m.high_u.to_numpy())
    m["fret"] = 1.0
    dates = pd.DatetimeIndex(np.sort(m.date.unique()))
    ref = load_ref()
    names, shares, ex = {}, {}, set()
    if universe_path is not None:
        uv = pd.read_csv(universe_path)
        cols = {c.lower().replace(" ", "_"): c for c in uv.columns}
        tk = cols.get("ticker") or cols.get("symbol")
        nm = next((cols[c] for c in cols if c in ("name", "security_name", "company_name")), None)
        so = next((cols[c] for c in cols if "outstanding" in c), None)
        er = next((cols[c] for c in cols if c.startswith("excl")), None)
        for _, r in uv.iterrows():
            t = str(r[tk]).upper()
            if nm: names[t] = r[nm]
            if so is not None and pd.notna(r[so]): shares[t] = float(r[so])
            if er is not None and pd.notna(r[er]) and str(r[er]).strip() not in ("", "nan", "False", "0"): ex.add(t)
            if "keep" in cols and str(r[cols["keep"]]).strip() not in ("1", "1.0", "True"): ex.add(t)
    rules = static_rules(sorted(m.ticker.unique()), ref, names)
    rules["scan"] = rules.index.isin(ex)
    if names:                                                   # liquid names outside the scan: rule (a) applies
        rules.loc[~rules.index.isin(set(names)), "scan"] = rules.a[~rules.index.isin(set(names))]
    keep = rules.index[~(rules.b | rules.c | rules.d | rules.scan)]
    P = finish_panel(panel_from_long(m[m.ticker.isin(set(keep))], dates, name, "BR", sample), grid=False)
    P.rules = rules.loc[P.tickers]; P.all_rules = rules
    P.shares_out = np.array([shares.get(t, np.nan) for t in P.tickers])
    return P


def load_pilot40(sample=(BR_START, BR_END)):
    """Stand-in for B-R until it is pulled: the 40 pilot names' split-adjusted daily bars, used as both the
    split-adjusted and the unadjusted series (flagged)."""
    d = pd.read_csv(SC / "rh_pilot" / "daily" / "pilot40_daily_2023-07_2026-10.csv", parse_dates=["date"])
    d = d.rename(columns={"symbol": "ticker"})
    for c in ("open", "high", "low", "close"):
        d[c + "_u"] = d[c]
    return _br_from_merged(d, sample, None, "pilot40 (B-R stand-in)")


def load_pit(start="2000-01-03", end="2021-03-31", sample=("2001-01-02", "2020-12-31")):
    """S&P 500 point-in-time members (data/raw_pit), for Controls (ii) and (iii)."""
    p = pd.read_parquet(DATA / "raw_pit" / "prices.parquet",
                        columns=["date", "ticker", "open", "high", "low", "close", "volume", "adj_close", "stock_splits"])
    p = p[p.ticker != "STI"].sort_values(["ticker", "date"])
    sp = p.stock_splits.where((p.stock_splits > 0) & (p.stock_splits != 1), 1.0).fillna(1.0)
    # traded price = split-adjusted close x the product of later split ratios
    lsp = np.log(sp.to_numpy())
    cum = pd.Series(lsp).groupby(p.ticker.values).transform(lambda x: x[::-1].cumsum()[::-1].shift(-1).fillna(0)).to_numpy()
    p["kk"] = np.exp(-cum)
    p = p[(p.date >= start) & (p.date <= end)]
    p = p.rename(columns={"volume": "sv"})
    p["fret"] = p.adj_close / p.close
    dates = pd.DatetimeIndex(np.sort(p.date.unique()))
    P = finish_panel(panel_from_long(p, dates, "S&P PIT", "PIT", sample), grid=False)
    P.SV_known = ~np.isnan(P.SV)
    P.SV = np.where(np.isnan(P.SV) & P.present, np.float32(1.0), P.SV).astype(np.float32)
    P.traded = P.real & (P.SV > 0)
    P.DV = (P.C * P.SV).astype(np.float32)
    P.DV[~P.SV_known] = np.nan
    tr = P.traded
    P.last_tr = np.where(tr.any(1), P.T - 1 - np.argmax(tr[:, ::-1], 1), -1).astype(np.int64)
    mem = pd.read_parquet(DATA / "raw_pit" / "membership_intervals.parquet")
    mem["end"] = mem.end.fillna(pd.Timestamp("2100-01-01"))
    P.member = np.zeros((P.N, P.T), bool)
    pos = {t: k for k, t in enumerate(P.tickers)}
    dv = P.dates.values
    for r in mem.itertuples():
        k = pos.get(r.ticker)
        if k is None:
            continue
        P.member[k, (dv >= np.datetime64(r.start)) & (dv <= np.datetime64(r.end))] = True
    return P


# ============================================================================ returns, rule (e), B6 moments

def daily_returns(P):
    """Total-return close-to-close return when the previous exchange day has a real bar, else NaN."""
    TR = (P.C.astype(np.float64) * P.F)
    r = np.full((P.N, P.T), np.nan)
    ok = P.real[:, 1:] & P.real[:, :-1]
    r[:, 1:] = np.where(ok, TR[:, 1:] / np.where(ok, TR[:, :-1], 1) - 1, np.nan)
    return r


def _roll_moments(x, y, W):
    """Window sums over [t-W, t-1] of pairs where both are finite: n, Sx, Sy, Sxx, Syy, Sxy (each (n, T))."""
    m = np.isfinite(x) & np.isfinite(y)
    xs = np.where(m, x, 0.0); ys = np.where(m, y, 0.0)
    out = []
    for a in (m.astype(np.float64), xs, ys, xs * xs, ys * ys, xs * ys):
        cs = np.zeros((a.shape[0], a.shape[1] + 1)); np.cumsum(a, axis=1, out=cs[:, 1:])
        w = np.full(a.shape, np.nan)
        w[:, W:] = cs[:, W:-1] - cs[:, :-W - 1]
        out.append(w)
    return out


def _r2_beta(n, sx, sy, sxx, syy, sxy):
    vx = n * sxx - sx * sx; vy = n * syy - sy * sy; cxy = n * sxy - sx * sy
    with np.errstate(invalid="ignore", divide="ignore"):
        r2 = cxy * cxy / (vx * vy)
        beta = cxy / vy                         # regression of the name (x) on the fund (y)
    return r2, beta


def fund_returns(Fd, funds):
    r = daily_returns(Fd)
    pos = {t: k for k, t in enumerate(Fd.tickers)}
    return {f: r[pos[f]] for f in funds if f in pos}


def rule_e(S, fr, chunk=800):
    """Rule (e): a symbol in neither listing file whose trailing-250-day R^2 (data to t-1, >= 100 pairs) on any
    of the 24 funds is >= 0.90 is a fund from then on. Returns the (N, T) flag."""
    flag = np.zeros((S.N, S.T), bool)
    unk = np.where(~S.rules.known.to_numpy())[0]
    r = daily_returns(S)
    for a in range(0, len(unk), chunk):
        rows = unk[a:a + chunk]
        x = r[rows]
        hit = np.zeros(x.shape, bool)
        for f in FUNDS_E:
            if f not in fr:
                continue
            y = np.broadcast_to(fr[f], x.shape)
            n, sx, sy, sxx, syy, sxy = _roll_moments(x, y, 250)
            r2, _ = _r2_beta(n, sx, sy, sxx, syy, sxy)
            hit |= (r2 >= 0.90) & (n >= 100)
        flag[rows] = np.maximum.accumulate(hit, axis=1)
    return flag


def b6_twins(P, fr, rows):
    """For B6: per name-day the most correlated fund (max R^2, 250 days, data to t-1, >= 100 pairs), its beta,
    and the SD of the residual over the 60-day window with that twin and beta."""
    r = daily_returns(P)[rows]
    best = np.full(r.shape, -1.0); tw = np.full(r.shape, -1, np.int16)
    beta = np.full(r.shape, np.nan); sdu = np.full(r.shape, np.nan)
    for k, f in enumerate(FUNDS_B6):
        if f not in fr:
            continue
        y = np.broadcast_to(fr[f], r.shape)
        n, sx, sy, sxx, syy, sxy = _roll_moments(r, y, 250)
        r2, b = _r2_beta(n, sx, sy, sxx, syy, sxy)
        r2 = np.where(n >= 100, r2, np.nan)
        n6, x6, y6, xx6, yy6, xy6 = _roll_moments(r, y, 60)
        with np.errstate(invalid="ignore", divide="ignore"):
            vu = (xx6 - 2 * b * xy6 + b * b * yy6 - (x6 - b * y6) ** 2 / n6) / (n6 - 1)
        better = np.nan_to_num(r2, nan=-1.0) > best
        best = np.where(better, r2, best); tw = np.where(better, k, tw)
        beta = np.where(better, b, beta); sdu = np.where(better, np.sqrt(np.maximum(vu, 0)), sdu)
    return r, tw, beta, sdu


# ============================================================================ trailing stats, cost model, spread

def trailing(P):
    (P.ADV, P.VMED, P.NR, P.EDGE, P.SIG60, P.SIG20, P.PPV) = _trail(P.O, P.H, P.L, P.C, P.F, P.DV, P.SV, P.KK,
                                                                   P.real, W60, W20, EQTOL)
    P.BAND = np.zeros((P.N, P.T), np.int8)
    for k, lo in enumerate(BAND_EDGES):
        P.BAND[P.ADV >= lo] = k + 1
    if P.kind == "PIT":                                        # close-only rows: S&P members are large caps
        P.BAND[P.present & ~P.SV_known] = 6
    return P


def model_M(P, cf):
    """Closing-quote model M = exp(b0 + b1 log ADV + b2 log P + b3 log sigma) x S (Duan smearing)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        z = cf["b0"] + cf["b1"] * np.log(P.ADV) + cf["b2"] * np.log(P.PPV) + cf["b3"] * np.log(P.SIG60)
        M = np.exp(z) * cf["S"]
    M[~((P.ADV > 0) & (P.SIG60 > 0) & (P.PPV > 0))] = np.nan
    return M.astype(np.float32)


def fit_cost_model(BR):
    """OLS of log closing quoted spread on log ADV60, log P, log sigma60 over the pilot's 1,167 names (closing
    quotes of 2026-10-16), daily bars from B-R; falls back to the 40 pilot names' bars when B-R is missing."""
    q = pd.read_csv(SC / "rh_pilot" / "scan_candidates_combined.csv")
    q = q[(q["Ask Price"] > q["Bid Price"]) & (q["Bid Price"] > 0)].copy()
    q["y"] = np.log((q["Ask Price"] - q["Bid Price"]) / ((q["Ask Price"] + q["Bid Price"]) / 2))
    q["ticker"] = q.ticker.astype(str).str.upper()
    d = int(np.searchsorted(BR.dates.values, np.datetime64("2026-10-16")))
    if d >= BR.T or BR.dates[d] != pd.Timestamp("2026-10-16"):
        raise RuntimeError("B-R bars do not include 2026-10-16")
    pos = {t: k for k, t in enumerate(BR.tickers)}
    rows = []
    for r in q.itertuples():
        k = pos.get(r.ticker)
        if k is None:
            continue
        p = BR.C[k, d] / BR.KK[k, d] if BR.real[k, d] else getattr(r, "Close")
        rows.append((r.ticker, r.y, BR.ADV[k, d], p, BR.SIG60[k, d], BR.NR[k, d]))
    X = pd.DataFrame(rows, columns=["ticker", "y", "adv", "p", "sig", "nr"])
    X = X[(X.adv > 0) & (X.p > 0) & (X.sig > 0)].dropna()
    A = np.column_stack([np.ones(len(X)), np.log(X.adv), np.log(X.p), np.log(X.sig)])
    b, *_ = np.linalg.lstsq(A, X.y.to_numpy(), rcond=None)
    res = X.y.to_numpy() - A @ b
    r2 = 1 - (res ** 2).sum() / ((X.y - X.y.mean()) ** 2).sum()
    return {"b0": b[0], "b1": b[1], "b2": b[2], "b3": b[3], "S": float(np.mean(np.exp(res))), "n_fit": len(X),
            "n_quotes": len(q), "r2": float(r2), "fit_sample": BR.name}


def ry_mask(P):
    Pt = P.PPV
    return (~P.excl & (P.BAND >= 1) & (P.BAND <= 4) & (P.NR >= 40) & P.ONGRID & (Pt >= 1) & np.isfinite(P.EDGE)
            & (P.EDGE > 0))


def ry_table(BH, BR, cf):
    """R_y = max(1, median EDGE/M over B-H L1-L4 name-days of year y-1 / the same over B-R 2025-10..2026-09)."""
    Mb = model_M(BR, cf)
    mb = ry_mask(BR) & np.isfinite(Mb)
    dv = BR.dates.values
    win = (dv >= np.datetime64("2025-10-01")) & (dv <= np.datetime64("2026-09-30"))
    den = float(np.median((BR.EDGE / Mb)[mb & win[None, :]]))
    nden = int((mb & win[None, :]).sum())
    Mh = model_M(BH, cf)
    mh = ry_mask(BH) & np.isfinite(Mh)
    yrs = BH.dates.year.to_numpy()
    rows = []
    for y in range(BH.dates[BH.s0].year, BH.dates[BH.s1].year + 1):
        sel = mh & (yrs == y - 1)[None, :]
        num = float(np.median((BH.EDGE / Mh)[sel])) if sel.any() else np.nan
        rows.append({"year": y, "num_median_EDGE_over_M_prev_year": num, "n_num": int(sel.sum()),
                     "den_median_EDGE_over_M_BR": den, "n_den": nden, "R_y": max(1.0, num / den) if num == num else 1.0})
    return pd.DataFrame(rows)


def spread(P, cf, ry=None):
    """s_it = max(EDGE x c, M x R_y, $0.01 / P), data to t-1."""
    M = model_M(P, cf)
    if ry is not None:
        R = ry.set_index("year").R_y
        yr = P.dates.year.to_numpy()
        fac = np.array([R.get(y, R.iloc[0] if y < R.index.min() else R.iloc[-1]) for y in yr], np.float32)
        M = M * fac[None, :]
    E = P.EDGE * C_EDGE.astype(np.float32)[P.BAND]
    with np.errstate(invalid="ignore", divide="ignore"):
        tick = (0.01 / P.PPV).astype(np.float32)
    P.SPR = np.fmax(np.fmax(E, M), tick)
    P.M = M
    return P


# ============================================================================ eligibility and signals

def eligibility(P, k1_only=False):
    Pt = P.C / P.KK
    E = ~P.excl & P.traded & (P.NR >= 40) & (Pt >= 1) & (P.BAND >= 1) & ((P.BAND >= 5) | P.ONGRID)
    if P.kind == "PIT":
        E = P.member & P.traded & (P.NR >= 40) & (Pt >= 1)
    if k1_only:
        E &= P.KK == 1
    E[:, :P.s0] = False; E[:, P.s1 + 1:] = False
    return E


def can_fire(P):
    """Reversal/continuation signals cannot fire on a one-price day or a split-ratio day."""
    one = (P.H - P.L) <= PTOL * P.H
    prevC = np.full((P.N, P.T), np.nan, np.float32); prevC[:, 1:] = np.where(P.real[:, :-1], P.C[:, :-1], np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        rc = P.C / prevC; ro = P.O / prevC
    near = lambda x: (np.abs(x[..., None] / SPLIT_RATIOS - 1) <= 0.02).any(-1)          # noqa: E731
    split = np.zeros((P.N, P.T), bool)
    cand = np.isfinite(rc) & ((rc < 0.681) | (rc > 1.469))
    ii, tt = np.nonzero(cand)
    split[ii, tt] = near(rc[ii, tt]) & near(ro[ii, tt])
    return ~one & ~split


def build_el(P, k1_only=False, groups=None):
    """Long table of eligible name-days in the sample (sorted by t, then i)."""
    E = eligibility(P, k1_only)
    tt, ii = np.nonzero(E.T)
    EL = SimpleNamespace(i=ii.astype(np.int64), t=tt.astype(np.int64))
    EL.gb = (np.ones(len(ii), np.int8) if P.kind == "PIT" else P.BAND[ii, tt]) if groups is None else groups[ii, tt]
    r = daily_returns_at(P, ii, tt)
    EL.r = r
    EL.fire = P.FIRE[ii, tt]
    with np.errstate(invalid="ignore"):
        EL.vshock = P.SV[ii, tt] >= 3 * P.VMED[ii, tt]
    if P.kind == "PIT":
        EL.vshock &= P.SV_known[ii, tt]
    EL.key = tt * P.N + ii
    EL.n = len(ii)
    EL.uid = _uid()
    return EL


def daily_returns_at(P, ii, tt):
    ok = (tt >= 1) & P.real[ii, np.maximum(tt - 1, 0)]
    tp = np.maximum(tt - 1, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = (P.C[ii, tt].astype(np.float64) * P.F[ii, tt]) / (P.C[ii, tp].astype(np.float64) * P.F[ii, tp]) - 1
    return np.where(ok, r, np.nan)


def decile_flags(EL, min_n=10):
    """Bottom / top decile of r_t within each (day, group band) over names with a finite r_t."""
    ok = np.isfinite(EL.r)
    g = EL.t[ok] * 8 + EL.gb[ok]
    df = pd.DataFrame({"g": g, "r": EL.r[ok]})
    gr = df.groupby("g").r
    cnt = gr.transform("size").to_numpy()
    lo = gr.quantile(0.10); hi = gr.quantile(0.90)
    lo_ = lo.reindex(g).to_numpy(); hi_ = hi.reindex(g).to_numpy()
    bot = np.zeros(EL.n, bool); top = np.zeros(EL.n, bool)
    r = EL.r[ok]
    bot[np.where(ok)[0]] = (cnt >= min_n) & (r <= lo_)
    top[np.where(ok)[0]] = (cnt >= min_n) & (r >= hi_)
    return bot, top


def signals(EL):
    bot, top = decile_flags(EL)
    with np.errstate(invalid="ignore"):
        b1 = bot & (EL.r < 0) & EL.fire
        e1 = top & (EL.r > 0) & EL.vshock & EL.fire
        d2 = top & EL.vshock & EL.fire
    return {"B1": b1, "B2": b1 & EL.vshock, "E1": e1, "D2": d2}


# ============================================================================ fees, costs, benchmarks

def fee_schedule(P):
    d = P.dates
    T = len(d)
    if P.kind == "BR":
        P.sec = np.select([d <= "2024-05-21", d <= "2025-05-13", d <= "2026-04-03"], [8.0e-6, 27.8e-6, 0.0], 20.6e-6)
        P.taf = np.select([d < "2024-01-01", d < "2026-01-01", d < "2026-10-01"], [0.000145, 0.000166, 0.000195], 0.0)
        P.tafcap = np.select([d < "2024-01-01", d < "2026-01-01", d < "2026-10-01"], [7.27, 8.30, 9.79], 0.0)
    else:
        P.sec = np.full(T, 0.30e-4); P.taf = np.full(T, 0.000119); P.tafcap = np.full(T, 5.95)
    return P


def fee_frac(P, d, notional, shares):
    """SEC + TAF on a sale, as a fraction of the sale notional (Robinhood pass-through thresholds)."""
    notional = np.asarray(notional, float); shares = np.asarray(shares, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        sec = np.where(notional > 500, P.sec[d], 0.0)
        taf = np.where(shares > 50, np.minimum(P.taf[d] * shares, P.tafcap[d]), 0.0) / np.where(notional > 0, notional, 1)
    return sec + taf


def leg_cost(P, i, d, size, m, Y):
    """Taker cost of one leg as a fraction of its notional: m s/2 + Y sigma20 sqrt(max(0, size - D_k)/ADV60)."""
    i = np.asarray(i); d = np.asarray(d)
    s = P.SPR[i, d].astype(np.float64)
    sig = P.SIG20[i, d].astype(np.float64)
    sig = np.where(np.isfinite(sig), sig, P.SIG60[i, d])
    sig = np.nan_to_num(sig, nan=0.0)
    adv = np.maximum(np.nan_to_num(P.ADV[i, d].astype(np.float64), nan=0.0), 1000.0)
    D = DEPTH[P.BAND[i, d]]
    imp = Y * sig * np.sqrt(np.maximum(0.0, np.asarray(size, float) - D) / adv)
    if P.kind == "PIT":
        imp = np.where(P.SV_known[i, d], imp, 0.0)
    return m * np.nan_to_num(s, nan=0.0) / 2 + imp


def bench_values(P, EL, a_off, a_open, b_off, b_open, pen=0.30):
    """Gross return of every eligible name-day over a benchmark window (same exit rules as trades)."""
    ent, ext, g, glast, flag = _legs(EL.i, EL.t, a_off, a_open, b_off, b_open, P.O, P.C, P.F, P.traded, P.last_tr,
                                     P.s1)
    g = np.where(flag == 1, (1 + glast) * (1 - pen) - 1, g)
    g[(flag < 0) | (flag == 3)] = np.nan
    return g


def band_sums(P, EL, R):
    ok = np.isfinite(R)
    key = (EL.t - P.s0) * 8 + EL.gb
    n = (P.s1 - P.s0 + 1) * 8
    Ssum = np.bincount(key[ok], weights=R[ok], minlength=n)
    Ncnt = np.bincount(key[ok], minlength=n).astype(float)
    return Ssum, Ncnt


def band_excess(P, EL, R, pos, weights=None):
    """Benchmark for trades at EL positions pos: EW of R over the band's other eligible names that day,
    excluding every name traded that day in the same group (the trades in pos)."""
    Ssum, Ncnt = band_sums(P, EL, R)
    key = (EL.t[pos] - P.s0) * 8 + EL.gb[pos]
    Rt = R[pos]
    ok = np.isfinite(Rt)
    n = len(Ssum)
    ts = np.bincount(key[ok], weights=Rt[ok], minlength=n)
    tn = np.bincount(key[ok], minlength=n).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = (Ssum[key] - ts[key]) / (Ncnt[key] - tn[key])
    return b


# ============================================================================ strategy engines

def c2c_trades(P, EL, pos, a_off=0, a_open=False, b_off=1, b_open=False):
    """Market-order trades for EL positions pos: entry at the close (or open) of t+a_off, exit at the close (or
    open) of t+b_off with the gap rule. Returns a dict of per-trade arrays (costs applied later)."""
    i, t = EL.i[pos], EL.t[pos]
    ent, ext, g, glast, flag = _legs(i, t, a_off, a_open, b_off, b_open, P.O, P.C, P.F, P.traded, P.last_tr, P.s1)
    ok = (flag >= 0) & (flag != 3)
    tr = {"pos": pos[ok], "i": i[ok], "t": t[ok], "ent": ent[ok], "ext": ext[ok], "g": g[ok], "glast": glast[ok],
          "flag": flag[ok], "a_open": a_open, "b_open": b_open, "kind": "c2c",
          "dv_ent": P.DV[i[ok], ent[ok]].astype(float),
          "hold": np.maximum(ext[ok] - ent[ok] + (1 if a_open else 0), 1).astype(float)}
    tr["p_exit"] = (P.O if b_open else P.C)[tr["i"], tr["ext"]] / P.KK[tr["i"], tr["t"]]
    tr["n_drop"] = int((flag == 3).sum())
    return tr


def c2c_net(P, tr, m=M0, Y=Y0, Q=Q0, pen=0.30, exit_mult=1.0, entry_taker=True):
    """Net return per trade. q = min(Q, 10% of the entry day's $ volume); entry cost at q, exit cost at the
    exit notional, sell fees; the delisting rule replaces the exit with the last close x (1 - pen)."""
    q = np.fmin(Q, 0.1 * tr["dv_ent"])                  # fmin: S&P PIT rows without volume trade at Q
    ce = leg_cost(P, tr["i"], tr["ent"], q, m, Y) if entry_taker else 0.0
    g = np.where(tr["flag"] == 1, (1 + tr["glast"]) * (1 - pen) - 1, tr["g"])
    qe = q * (1 + g)
    cx = leg_cost(P, tr["i"], tr["ext"], qe, m * exit_mult, Y)
    fee = fee_frac(P, tr["ext"], qe, qe / np.maximum(tr["p_exit"], 1e-9))
    normal = tr["flag"] != 1
    r = np.where(normal, (1 + g) * (1 - cx - fee) / (1 + ce) - 1, (1 + g) / (1 + ce) - 1)
    return r, q


def b3_trades(P, EL, pos, mult=1.0, exit_off=1, touch=False, open_fill=False):
    """B3 passive dip bid: day-limit buy for t+1 at L = floor_cent(P_t (1 - mult sigma_t)); fill if low_{t+1} <=
    L - tick (whole-cent low on B-R); size f = (L - low)/(high - low); sold at the close of t+exit_off."""
    i, t = EL.i[pos], EL.t[pos]
    t1 = t + 1
    okt = t1 < P.T
    i, t, t1, pos = i[okt], t[okt], t1[okt], pos[okt]
    kk = P.KK[i, t].astype(float)
    Pt = P.C[i, t] / kk
    sig = P.SIG20[i, t1].astype(float)                            # trailing 20-day SD with data to t
    Lp = np.floor(Pt * (1 - mult * sig) * 100 + 1e-7) / 100
    lo = P.L[i, t1] / kk; hi = P.H[i, t1] / kk; op = P.O[i, t1] / kk
    with np.errstate(invalid="ignore", divide="ignore"):
        if touch:
            fill = P.traded[i, t1] & (lo <= Lp * (1 + 1e-6)) & (Lp > 0)
        else:
            fill = P.traded[i, t1] & (lo <= Lp - 0.01 + 1e-6 * Lp) & P.WCL[i, t1] & (Lp > 0)
        f = np.where(hi - lo <= 1e-6 * hi, 1.0, np.clip((Lp - lo) / (hi - lo), 0, 1))
    n_orders = int(np.isfinite(Lp).sum())
    i, t, t1, pos, kk, Lp, f, op = i[fill], t[fill], t1[fill], pos[fill], kk[fill], Lp[fill], f[fill], op[fill]
    px = np.minimum(op, Lp) if open_fill else Lp
    pe = px * kk * P.F[i, t1]                                    # adjusted entry price
    if exit_off == 1:
        ext = t1; g = P.C[i, t1] * P.F[i, t1] / pe - 1; flag = np.zeros(len(i), np.int8); glast = g.copy()
    else:
        _, ext, g0, glast0, flag = _legs(i, t, 1, False, exit_off, False, P.O, P.C, P.F, P.traded, P.last_tr, P.s1)
        base = P.C[i, t1] * P.F[i, t1] / pe                      # fill -> close t+1, then close t+1 -> exit
        g = (1 + g0) * base - 1; glast = (1 + glast0) * base - 1
        ok = (flag >= 0) & (flag != 3)
        i, t, t1, pos, kk, Lp, f, ext, g, glast, flag = (a[ok] for a in (i, t, t1, pos, kk, Lp, f, ext, g, glast, flag))
    tr = {"pos": pos, "i": i, "t": t, "ent": t1, "ext": ext, "g": g, "glast": glast, "flag": flag, "kind": "b3",
          "f": f, "dv_ent": P.DV[i, t1].astype(float), "hold": np.maximum(ext - t1 + 1, 1).astype(float),
          "p_exit": P.C[i, ext] / kk, "n_orders": n_orders, "L": Lp}
    return tr


def b3_net(P, tr, m=M0, Y=Y0, Q=Q0, pen=0.30):
    q = np.fmin(Q, 0.1 * tr["dv_ent"] * tr["f"])
    g = np.where(tr["flag"] == 1, (1 + tr["glast"]) * (1 - pen) - 1, tr["g"])
    qe = q * (1 + g)
    cx = leg_cost(P, tr["i"], tr["ext"], qe, m, Y)
    fee = fee_frac(P, tr["ext"], qe, qe / np.maximum(tr["p_exit"], 1e-9))
    r = np.where(tr["flag"] != 1, (1 + g) * (1 - cx - fee) - 1, g)
    return r, q


def b4_trades(P, band_mask, Q=Q0, NS=5, tgt=0.0, touch=False):
    """Run the B4 engine on one band cell; returns per-trade arrays."""
    maxn = int(band_mask.sum()) + 1
    out = _b4_engine(band_mask, P.C, P.F, P.H, P.L, P.O, P.KK, P.DV, P.traded, P.WCL, P.WCH, P.SPR, P.last_tr, P.s1,
                     P.s0, P.s1, Q, NS, tgt, touch, maxn)
    names = ["t", "i", "q", "r1", "B", "A", "phi", "pg", "pnot", "psh", "fday", "fflag", "fglast", "on", "hold"]
    tr = dict(zip(names, out[:-1]))
    tr["n_orders"] = int(out[-1].sum())
    tr["kind"] = "b4"; tr["NS"] = NS
    keep = tr["fflag"] != 3
    for k in names:
        tr[k] = tr[k][keep]
    tr["n_drop"] = int((~keep).sum())
    return tr


def b4_net(P, tr, EL=None, benchR=None, m=M0, Y=Y0, pen=0.30, raw=False):
    """B4 metric: raw fill -> close(t+1) plus band excess from close(t+1) to the exits. benchR[j] = benchmark
    (EL-aligned) from close t+1 to close t+2+j (j < NS) and to the forced exit (j = NS)."""
    i, t, NS = tr["i"], tr["t"], tr["NS"]
    t1 = t + 1
    kk = P.KK[i, t]
    phi, pg = tr["phi"], tr["pg"]
    # GTC pieces: fee on the sale notional
    after = np.zeros(len(i))
    for j in range(NS):
        e = np.minimum(t + 2 + j, P.T - 1)
        fr = phi[:, j]
        fee = fee_frac(P, e, tr["pnot"][:, j], tr["psh"][:, j])
        after += np.where(fr > 0, fr * ((1 + np.nan_to_num(pg[:, j])) * (1 - fee) - 1), 0.0)
    fr = phi[:, NS]
    has = fr > 0
    d = np.where(tr["fday"] >= 0, tr["fday"], t1)
    g = np.where(tr["fflag"] == 1, (1 + tr["fglast"]) * (1 - pen) - 1, pg[:, NS])
    v_rem = tr["psh"][:, NS] * tr["B"] * (1 + tr["r1"]) * (1 + np.nan_to_num(g))   # $ value of the remainder at exit
    cx = leg_cost(P, i, d, v_rem, m, Y)
    pex = P.C[i, d] / kk
    fee = fee_frac(P, d, v_rem, v_rem / np.maximum(pex, 1e-9))
    gf = np.where(tr["fflag"] == 1, g, (1 + np.nan_to_num(g)) * (1 - cx - fee) - 1)
    after += np.where(has, fr * gf, 0.0)
    r_tot = (1 + tr["r1"]) * (1 + after) - 1
    if raw or benchR is None:
        return r_tot, r_tot
    pos = np.searchsorted(EL.key, t * P.N + i)
    bench = np.zeros(len(i))
    for j in range(NS + 1):
        frj = phi[:, j]
        bj = band_excess(P, EL, benchR[j], pos)
        bench += np.where(frj > 0, frj * np.nan_to_num(bj), 0.0)
    x = (1 + tr["r1"]) * (1 + after - bench) - 1
    tr["_r1"], tr["_after"], tr["_bench"] = tr["r1"], after, bench
    return x, r_tot


# ============================================================================ statistics

def cell_stats(P, t, x, w=None, h=None, lags=10):
    """Trade-weighted (or w-weighted) mean with a Newey-West t of the daily series D_t, plus the edge per
    trade-day held, halves, share of active days and the mean per active day."""
    t = np.asarray(t); x = np.asarray(x, float)
    w = np.ones(len(x)) if w is None else np.asarray(w, float)
    h = np.ones(len(x)) if h is None else np.asarray(h, float)
    ok = np.isfinite(x) & np.isfinite(w) & (w > 0) & (t >= P.s0) & (t <= P.s1)
    t, x, w, h = t[ok], x[ok], w[ok], h[ok]
    days = P.s1 - P.s0 + 1
    out = {"n_trades": int(len(x)), "n_units": int(days)}
    nan = dict(estimate=np.nan, se=np.nan, t=np.nan, p_one_sided=np.nan, edge_estimate=np.nan, edge_se=np.nan,
               share_active=0.0, mean_active=np.nan, half1=np.nan, half2=np.nan, sum_w=0.0)
    if len(x) < 3:
        return out | nan
    pos = t - P.s0
    wbar = w.sum() / days
    D = np.bincount(pos, weights=w * x, minlength=days) / wbar
    Hs = np.bincount(pos, weights=w * h, minlength=days) / wbar
    m, se, tt, p = nw_t(D, lags)
    R, rse = nw_ratio(D, Hs, lags)
    cnt = np.bincount(pos, minlength=days)
    wd = np.bincount(pos, weights=w, minlength=days)
    act = cnt > 0
    split = int(np.searchsorted(P.dates.values, np.datetime64(BH_HALF2 if P.kind != "BR" else "2025-01-01")))
    h1 = t < split
    wm = lambda a, b: float((a * b).sum() / b.sum()) if b.sum() > 0 else np.nan     # noqa: E731
    out.update(estimate=m, se=se, t=tt, p_one_sided=p, edge_estimate=R, edge_se=rse, share_active=float(act.mean()),
               mean_active=float(np.mean((D * wbar)[act] / wd[act])), half1=wm(x[h1], w[h1]), half2=wm(x[~h1], w[~h1]),
               sum_w=float(w.sum()))
    return out


def winsor_mean(x, w):
    lo, hi = np.nanpercentile(x, [0.5, 99.5])
    xc = np.clip(x, lo, hi)
    return float((xc * w).sum() / w.sum())


def month_of(P, t):
    d = P.dates[t]
    return (d.year * 100 + d.month).to_numpy()


class Bench:
    """Cache of benchmark gross returns (EL-aligned) by window."""
    def __init__(self, P, EL):
        self.P, self.EL, self.c = P, EL, {}

    def get(self, a_off, a_open, b_off, b_open, pen=0.30):
        k = (a_off, a_open, b_off, b_open, pen)
        if k not in self.c:
            keep = {(0, False, 1, False, 0.30)} | {(1, False, b, False, 0.30) for b in range(2, 8)}
            extra = [x for x in self.c if x not in keep]
            while len(extra) > 8:                                 # keep memory bounded (EL-aligned float32 arrays)
                del self.c[extra.pop(0)]
            self.c[k] = bench_values(self.P, self.EL, a_off, a_open, b_off, b_open, pen).astype(np.float32)
        return self.c[k]


def el_mask(P, EL, sel):
    m = np.zeros((P.N, P.T), bool)
    m[EL.i[sel], EL.t[sel]] = True
    return m


# ============================================================================ one cell

_TRC: dict = {}
COST_ONLY = ("exit_mult", "gross", "raw", "bench", "ew", "bench_open")


def _trades_cached(P, EL, strat, band, v, Q, fn):
    key = (P.uid, EL.uid, strat, band, Q if strat == "B4" else None,
           tuple(sorted((k, x) for k, x in v.items() if k not in COST_ONLY and k != "tr")))
    if key not in _TRC:
        _TRC[key] = fn()
    return _TRC[key]


def run_cell(P, EL, BC, sig, strat, band, m=M0, Y=Y0, Q=Q0, pen=0.30, variant=None):
    """Trades and statistic contributions for one strategy-band cell. Returns dict with t, x (statistic), w
    (weight), h (trade-days held), r (raw net), q (size), tr (raw trade arrays), lags."""
    v = variant or {}
    inband = EL.gb == band
    if strat in ("B1", "B2", "E1"):
        a_off, a_open, b_off, b_open = v.get("legs", (0, False, v.get("hold", 1), False))
        pos = np.where(sig[strat] & inband)[0]
        tr = _trades_cached(P, EL, strat, band, v, Q, lambda: c2c_trades(P, EL, pos, a_off, a_open, b_off, b_open))
        r, q = c2c_net(P, tr, m, Y, Q, pen, exit_mult=v.get("exit_mult", 1.0))
        if v.get("gross"):
            r = np.where(tr["flag"] == 1, (1 + tr["glast"]) * (1 - pen) - 1, tr["g"])
        bk = v.get("bench", (a_off, a_open, b_off, b_open))
        x = r if v.get("raw") else r - band_excess(P, EL, BC.get(*bk, pen=pen), tr["pos"])
        lags = max(10, (b_off - a_off) + 4)
        return dict(t=tr["t"], x=x, w=np.ones(len(x)), h=tr["hold"], r=r, q=q, tr=tr, lags=lags,
                    n_orders=len(pos))
    if strat == "B3":
        pos = np.where(inband)[0]
        tr = _trades_cached(P, EL, strat, band, v, Q, lambda: b3_trades(
            P, EL, pos, mult=v.get("mult", 1.0), exit_off=v.get("exit_off", 1), touch=v.get("touch", False),
            open_fill=v.get("open_fill", False)))
        r, q = b3_net(P, tr, m, Y, Q, pen)
        x = r
        if v.get("bench"):
            x = r - band_excess(P, EL, BC.get(*v["bench"], pen=pen), tr["pos"])
        w = np.ones(len(x)) if v.get("ew") else q
        return dict(t=tr["t"], x=x, w=w, h=tr["hold"], r=r, q=q, tr=tr, lags=max(10, v.get("exit_off", 1) + 4),
                    n_orders=tr["n_orders"])
    if strat == "B4":
        NS = v.get("NS", 5)
        tr = v.get("tr") or _trades_cached(P, EL, strat, band, v, Q, lambda: b4_trades(
            P, el_mask(P, EL, inband), Q=Q, NS=NS, tgt=v.get("tgt", 0.0), touch=v.get("touch", False)))
        benchR = [BC.get(1, False, 2 + j, False, pen) for j in range(NS)] + [BC.get(1, False, 1 + NS, False, pen)]
        x, r = b4_net(P, tr, EL, None if v.get("raw") else benchR, m, Y, pen)
        if v.get("bench_open"):
            pos = np.searchsorted(EL.key, tr["t"] * P.N + tr["i"])
            bo = band_excess(P, EL, BC.get(1, True, 1, False, pen), pos)
            x = (1 + tr["_r1"] - bo) * (1 + tr["_after"] - tr["_bench"]) - 1
        return dict(t=tr["t"], x=x, w=np.ones(len(x)), h=tr["hold"], r=r, q=tr["q"], tr=tr, lags=max(10, NS + 1 + 4),
                    n_orders=tr["n_orders"])
    raise ValueError(strat)


def stat_of(P, c):
    return cell_stats(P, c["t"], c["x"], c["w"], c["h"], c["lags"])


def m_star(P, EL, BC, sig, strat, band, base, lags):
    """Break-even cost multiplier m* (mean net = 0) and a delta-method 95% CI."""
    def f(m):
        c = run_cell(P, EL, BC, sig, strat, band, m=m, variant=base)
        s = stat_of(P, c)
        return s["estimate"], s["se"]
    e0, _ = f(0.0)
    if not np.isfinite(e0) or e0 <= 0:
        return 0.0, np.nan, np.nan
    hi = 2.0
    eh, _ = f(hi)
    while eh > 0 and hi < 64:
        hi *= 2; eh, _ = f(hi)
    if eh > 0:
        return np.inf, np.nan, np.nan
    lo = 0.0
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        em, _ = f(mid)
        lo, hi = (mid, hi) if em > 0 else (lo, mid)
    ms = 0.5 * (lo + hi)
    e1, se1 = f(ms)
    e2, _ = f(ms + 0.1)
    slope = (e2 - e1) / 0.1
    sem = se1 / abs(slope) if slope != 0 else np.nan
    return ms, ms - 1.96 * sem, ms + 1.96 * sem


def capital_stats(P, c, strat):
    """Peak capital in use (half-day slots), annualized net $ return on it, Sharpe, months of record for t >= 2."""
    tr = c["tr"]
    q = np.asarray(c["q"], float); r = np.asarray(c["r"], float)
    ok = np.isfinite(r) & np.isfinite(q) & (q > 0)
    if ok.sum() < 3:
        return {}
    if strat in ("B1", "B2", "E1"):
        sin = 2 * tr["ent"] + (0 if tr["a_open"] else 1); sout = 2 * tr["ext"] + (0 if tr["b_open"] else 1)
    elif strat == "B3":
        sin = 2 * tr["ent"]; sout = 2 * tr["ext"] + 1
    else:
        NS = tr["NS"]
        last = tr["t"] + 1
        for j in range(NS):
            last = np.where(tr["phi"][:, j] > 0, tr["t"] + 2 + j, last)
        last = np.where(tr["phi"][:, NS] > 0, np.maximum(tr["fday"], tr["t"] + 1 + NS), last)
        sin = 2 * (tr["t"] + 1); sout = 2 * last + 1
    sin, sout, q, r, t = sin[ok], sout[ok], q[ok], r[ok], c["t"][ok]
    nS = 2 * P.T + 4
    diff = np.bincount(sin, weights=q, minlength=nS) - np.bincount(np.minimum(sout, nS - 1), weights=q, minlength=nS)
    use = np.cumsum(diff)
    peak = float(use.max())
    days = P.s1 - P.s0 + 1
    pnl = np.bincount(t - P.s0, weights=q * r, minlength=days)
    yrs = days / 252
    ann = pnl.sum() / yrs / peak if peak > 0 else np.nan
    dr = pnl / peak
    sd = dr.std(ddof=1)
    sharpe = dr.mean() / sd * np.sqrt(252) if sd > 0 else np.nan
    sig_a = sd * np.sqrt(252)
    out = {"peak_capital": peak, "net_$_per_year": pnl.sum() / yrs, "ann_net_on_peak": ann, "sharpe": sharpe,
           "ann_after_tax_35": ann * 0.65 if ann > 0 else ann, "daily_pnl_sd_on_peak": sd}
    for mu in (0.10, 0.25, 0.50):
        out[f"months_t2_at_{int(mu * 100)}pct"] = 12 * (2 * sig_a / mu) ** 2
    return out


def spy_after_tax(Fd_or_none, P):
    """SPY buy-and-hold over the sample dates, after 20% long-term tax on the gain at the end."""
    try:
        if P.kind == "BH" and Fd_or_none is not None:
            k = list(Fd_or_none.tickers).index("SPY")
            tr = Fd_or_none.C[k].astype(float) * Fd_or_none.F[k]
            a, b = tr[P.s0], tr[P.s1]
        else:
            p = pd.read_parquet(DATA / "raw_pit" / "prices.parquet", columns=["date", "ticker", "adj_close"])
            p = p[p.ticker == "SPY"].set_index("date").adj_close
            a = p[p.index >= P.dates[P.s0]].iloc[0]; b = p[p.index <= P.dates[P.s1]].iloc[-1]
        yrs = (P.dates[P.s1] - P.dates[P.s0]).days / 365.25
        g = b / a - 1
        return {"spy_ann": (1 + g) ** (1 / yrs) - 1, "spy_ann_after_tax_20": (1 + 0.8 * g) ** (1 / yrs) - 1}
    except Exception:
        return {"spy_ann": np.nan, "spy_ann_after_tax_20": np.nan}


# ============================================================================ the primary family

CELLS = [(s, b) for s in ("B1", "B2", "B3", "B4") for b in (1, 2, 3, 4)] + [("E1", b) for b in (1, 2, 3, 4)]
STAT_NAME = {"B1": "trade-weighted mean net band-excess return per trade (m=1.5, Y=0.5, Q=$10k)",
             "B2": "trade-weighted mean net band-excess return per trade (m=1.5, Y=0.5, Q=$10k)",
             "B3": "q-weighted mean raw net return per fill (m=1.5, Y=0.5, Q=$10k)",
             "B4": "trade-weighted mean: raw fill->close(t+1) plus net band excess to exit (m=1.5, Y=0.5, Q=$10k)",
             "E1": "trade-weighted mean net band-excess return per trade (m=1.5, Y=0.5, Q=$10k)"}


def prepare(P, cf, ry, k1_only=False):
    if not hasattr(P, "ADV"):
        trailing(P)
    if not hasattr(P, "SPR"):
        spread(P, cf, ry)
        del P.M
        fee_schedule(P)
        P.FIRE = can_fire(P)
    EL = build_el(P, k1_only)
    return EL, Bench(P, EL), signals(EL)


def primary_stats_only(P, EL, BC, sig):
    """The 20 primary statistics (estimate only), for the null panels and B-R."""
    out = {}
    for s, b in CELLS:
        c = run_cell(P, EL, BC, sig, s, b)
        out[f"{s}-L{b}"] = stat_of(P, c)["estimate"]
        _TRC.clear()
    return out


def run_primary(P, EL, BC, sig, Fd=None, BR=None, nulls=None, write_trades=True, quiet=False):
    """All 20 primary cells with PASS conditions 2-8 and the per-cell report."""
    rows, rep, trades = [], [], []
    br_stats = None
    if BR is not None:
        br_stats = primary_stats_only(*BR)
    spy = spy_after_tax(Fd, P)
    for s, b in CELLS:
        tid = f"{s}-L{b}"
        c = run_cell(P, EL, BC, sig, s, b)
        st = stat_of(P, c)
        x, w = c["x"], c["w"]
        ok = np.isfinite(x)
        cond = {}
        cond["cond_halves"] = bool(st["half1"] > 0 and st["half2"] > 0) if st["n_trades"] else False
        brm = br_stats.get(tid) if br_stats else np.nan
        cond["cond_br"] = (bool(brm > 0) if np.isfinite(brm) else np.nan)
        if s in ("B1", "B2", "E1"):
            sk = stat_of(P, run_cell(P, EL, BC, sig, s, b, m=0.0, variant={"legs": (1, False, 2, False)}))
            cond["cond_skip"] = bool(sk["estimate"] > 0); skm = sk["estimate"]
        else:
            cond["cond_skip"] = True; skm = np.nan
        if b in (1, 2):
            m2 = stat_of(P, run_cell(P, EL, BC, sig, s, b, m=2.0))["estimate"]
            cond["cond_m2"] = bool(m2 > 0)
        else:
            cond["cond_m2"] = True; m2 = np.nan
        wz = winsor_mean(x[ok], w[ok]) if ok.sum() > 10 else np.nan
        cond["cond_winsor"] = bool(wz > 0)
        dm, dmo = drop_worst(x[ok], month_of(P, c["t"][ok]), w[ok]) if ok.sum() > 10 else (np.nan, None)
        cond["cond_dropmonth"] = bool(dm > 0)
        nmax = np.nan; nmean = np.nan
        if nulls is not None and tid in nulls:
            nv = np.asarray(nulls[tid], float)
            nmax, nmean = np.nanmax(nv), np.nanmean(nv)
            cond["cond_null"] = bool(st["estimate"] > nmax)
        else:
            cond["cond_null"] = np.nan
        rows.append({"test_id": tid, "part": "E" if s == "E1" else "B", "statistic_name": STAT_NAME[s],
                     "estimate": st["estimate"], "se": st["se"], "df": np.nan, "t": st["t"],
                     "p_one_sided": st["p_one_sided"], "edge_name": "mean net return per trade-day held",
                     "edge_estimate": st["edge_estimate"], "edge_se": st["edge_se"], "edge_df": np.nan,
                     "threshold_E": E_THRESH} | cond |
                    {"n_units": st["n_units"], "share_active": st["share_active"], "n_trades": st["n_trades"],
                     "half1": st["half1"], "half2": st["half2"], "br_estimate": brm, "skip_gross_estimate": skm,
                     "m2_estimate": m2, "winsor_estimate": wz, "dropmonth_estimate": dm, "dropped_month": dmo,
                     "null_mean": nmean, "null_max": nmax, "nw_lags": c["lags"]})
        if quiet:
            continue
        # ---- per-cell report (also reported, decides nothing)
        ncan = int((c["tr"]["phi"][:, -1] > 0).sum()) if s == "B4" else 0
        rr = {"test_id": tid, "mean_per_active_day": st["mean_active"], "n_orders": c["n_orders"],
              "orders_per_day": (c["n_orders"] + st["n_trades"]) / st["n_units"],
              "cancels_per_day": ncan / st["n_units"],
              "route": "end-of-day decisions through Claude and the Robinhood MCP",
              "ub_edge_99.86": upper_bound(st["edge_estimate"], st["edge_se"]) if np.isfinite(st["edge_se"]) else np.nan,
              "largest_edge_ruled_out_95": st["edge_estimate"] + 1.645 * st["edge_se"],
              "mde": mde(st["se"]) if np.isfinite(st["se"]) else np.nan}
        rr |= capital_stats(P, c, s) | spy
        for mm in (0.0, 1.0, 2.0):
            e = stat_of(P, run_cell(P, EL, BC, sig, s, b, m=mm))
            rr[f"m{mm:g}_estimate"] = e["estimate"]; rr[f"m{mm:g}_t"] = e["t"]
        ms, lo, hi = m_star(P, EL, BC, sig, s, b, None, c["lags"])
        rr |= {"m_star": ms, "m_star_lo95": lo, "m_star_hi95": hi}
        for yy in (0.0, 1.0):
            e = stat_of(P, run_cell(P, EL, BC, sig, s, b, Y=yy))
            rr[f"Y{yy:g}_estimate"] = e["estimate"]; rr[f"Y{yy:g}_t"] = e["t"]
        for qq in (1e3, 5e4, 2.5e5):
            e = stat_of(P, run_cell(P, EL, BC, sig, s, b, Q=qq))
            rr[f"Q{int(qq)}_estimate"] = e["estimate"]; rr[f"Q{int(qq)}_t"] = e["t"]
        e = stat_of(P, run_cell(P, EL, BC, sig, s, b, pen=0.0))
        rr["delist0_estimate"] = e["estimate"]; rr["delist0_t"] = e["t"]
        rr["n_delist_rule"] = int((c["tr"].get("flag", c["tr"].get("fflag")) == 1).sum())
        rep.append(rr)
        if write_trades:
            tr = c["tr"]
            trades.append(pd.DataFrame({"cell": tid, "date": P.dates[c["t"]], "ticker": P.tickers[tr["i"]],
                                        "x": c["x"], "r_net": c["r"], "w": c["w"], "q": c["q"], "hold": c["h"]}))
        _TRC.clear()
    return pd.DataFrame(rows), pd.DataFrame(rep), (pd.concat(trades) if trades else None)


# ============================================================================ exploratory

def run_exploratory(P, EL, BC, sig, vix=None):
    rows = []

    def add(label, part, s, b, c, note=""):
        st = stat_of(P, c)
        rows.append({"label": label, "part": part, "strategy": s, "band": BANDS[b], "note": note} |
                    {k: st[k] for k in ("estimate", "se", "t", "p_one_sided", "n_trades", "half1", "half2",
                                        "edge_estimate", "share_active")})

    for b in (1, 2, 3, 4):
        for s in ("B1", "B2"):
            add("5-day hold", "B", s, b, run_cell(P, EL, BC, sig, s, b, variant={"hold": 5}))
        for mult in (0.5, 2.0):
            add(f"B3 L = P(1 - {mult:g} sigma)", "B", "B3", b, run_cell(P, EL, BC, sig, "B3", b, variant={"mult": mult}))
        for e in (2, 6):
            add(f"B3 exit at t+{e}", "B", "B3", b, run_cell(P, EL, BC, sig, "B3", b, variant={"exit_off": e}))
        add("B3 fill at min(open, L)", "B", "B3", b, run_cell(P, EL, BC, sig, "B3", b, variant={"open_fill": True}))
        for tg in (0.01, 0.02):
            add(f"B4 target A = B x {1 + tg:g}", "B", "B4", b, run_cell(P, EL, BC, sig, "B4", b, variant={"tgt": tg}))
        for ns in (1, 20):
            add(f"B4 hold {ns} sessions", "B", "B4", b, run_cell(P, EL, BC, sig, "B4", b, variant={"NS": ns}))
        for s in ("B1", "B2"):
            add("overnight leg close(t)->open(t+1), gross", "B", s, b,
                run_cell(P, EL, BC, sig, s, b, variant={"legs": (0, False, 1, True), "gross": True}))
            add("intraday leg open(t+1)->close(t+1), gross", "B", s, b,
                run_cell(P, EL, BC, sig, s, b, variant={"legs": (1, True, 1, False), "gross": True}))
        c4 = run_cell(P, EL, BC, sig, "B4", b, m=0.0, Y=0.0)
        tr4 = c4["tr"]
        lg = np.log1p(c4["r"])
        add("B4 overnight log return held (gross, raw)", "B", "B4", b, dict(c4, x=tr4["on"]))
        add("B4 intraday log return held (gross, raw)", "B", "B4", b, dict(c4, x=lg - tr4["on"]))
        add("B1-ON sell at open(t+1)", "B", "B1", b, run_cell(P, EL, BC, sig, "B1", b, variant={"legs": (0, False, 1, True)}))
        add("B1-ON sell at open(t+1), s doubled at the open", "B", "B1", b,
            run_cell(P, EL, BC, sig, "B1", b, variant={"legs": (0, False, 1, True), "exit_mult": 2.0}))
        for s in ("B1", "B2", "B4", "E1"):
            add("raw net return (no band excess)", "E" if s == "E1" else "B", s, b,
                run_cell(P, EL, BC, sig, s, b, variant={"raw": True}))
        for s in ("B1", "B2", "E1"):
            add("open(t+1)->close(t+1) band benchmark", "E" if s == "E1" else "B", s, b,
                run_cell(P, EL, BC, sig, s, b, variant={"bench": (1, True, 1, False)}))
        add("open(t+1)->close(t+1) band benchmark", "B", "B3", b,
            run_cell(P, EL, BC, sig, "B3", b, variant={"bench": (1, True, 1, False)}))
        add("open(t+1)->close(t+1) band benchmark on the fill day", "B", "B4", b,
            run_cell(P, EL, BC, sig, "B4", b, variant={"bench_open": True}))
        # B4 by price and by s/sigma20 tercile
        c = run_cell(P, EL, BC, sig, "B4", b)
        tr = c["tr"]
        pt = P.C[tr["i"], tr["t"]] / P.KK[tr["i"], tr["t"]]
        sel = (pt >= 1) & (pt < 3)
        add("B4 in $1-3 stocks", "B", "B4", b, dict(c, x=np.where(sel, c["x"], np.nan)))
        rat = P.SPR[tr["i"], tr["t"]] / P.SIG20[tr["i"], tr["t"]]
        if np.isfinite(rat).sum() > 30:
            q1, q2 = np.nanpercentile(rat, [100 / 3, 200 / 3])
            for k, (a, z) in enumerate(((-np.inf, q1), (q1, q2), (q2, np.inf))):
                add(f"B4 s/sigma20 tercile {k + 1}", "B", "B4", b, dict(c, x=np.where((rat > a) & (rat <= z), c["x"], np.nan)))
        _TRC.clear()
        # Part E exploratory
        for hh in (5, 20):
            add(f"E1 exit at t+{hh}", "E", "E1", b, run_cell(P, EL, BC, sig, "E1", b, variant={"hold": hh}))
        add("E1 entry at open(t+1), exit close(t+1)", "E", "E1", b,
            run_cell(P, EL, BC, sig, "E1", b, variant={"legs": (1, True, 1, False)}))
        # VIX terciles
        if vix is not None:
            for s in STRATS:
                c = run_cell(P, EL, BC, sig, s, b)
                vv = vix.v[c["t"]]
                for k, (a, z) in enumerate(zip(vix.qs[:-1], vix.qs[1:])):
                    add(f"VIX tercile {k + 1}", "E" if s == "E1" else "B", s, b,
                        dict(c, x=np.where((vv > a) & (vv <= z), c["x"], np.nan)))
    for b in (5, 6):
        for s in STRATS:
            add("control band", "E" if s == "E1" else "B", s, b, run_cell(P, EL, BC, sig, s, b))
    return pd.DataFrame(rows)


def run_k1_rows(P, cf, ry):
    """Exploratory: the primary cells with every name-day with k > 1 dropped (eligibility and benchmarks)."""
    EL1, BC1, sig1 = prepare(P, cf, ry, k1_only=True)
    rows = []
    for s, b in CELLS:
        st = stat_of(P, run_cell(P, EL1, BC1, sig1, s, b))
        rows.append({"label": "k > 1 name-days dropped", "part": "E" if s == "E1" else "B", "strategy": s,
                     "band": BANDS[b], "note": ""} | {k: st[k] for k in ("estimate", "se", "t", "p_one_sided",
                                                                          "n_trades", "half1", "half2",
                                                                          "edge_estimate", "share_active")})
        _TRC.clear()
    return pd.DataFrame(rows)


def run_illusion(P, EL, BC, sig):
    rows = []
    for b in (1, 2, 3, 4):
        for label, s, v in (("touch fills (low <= L)", "B3", {"touch": True}),
                            ("touch fills (low <= B, high >= A)", "B4", {"touch": True}),
                            ("equal-weighted instead of q-weighted", "B3", {"ew": True})):
            st = stat_of(P, run_cell(P, EL, BC, sig, s, b, variant=v))
            rows.append({"label": "ILLUSION: " + label, "strategy": s, "band": BANDS[b]} |
                        {k: st[k] for k in ("estimate", "se", "t", "n_trades")})
    return pd.DataFrame(rows)


def descriptive(P, EL):
    rows = []
    split = int(np.searchsorted(P.dates.values, np.datetime64(BH_HALF2)))
    # median cross-sectional percentile of ADV60 for each band, by half: percentile within all non-excluded
    # names of the panel that had a real bar in the window (ADV60 > 0 counts names trading at all)
    pct = np.full(EL.n, np.nan)
    starts = np.searchsorted(EL.t, np.arange(P.T + 1))
    for t in range(P.s0, P.s1 + 1):
        a, b = starts[t], starts[t + 1]
        if a == b:
            continue
        cs = P.ADV[:, t][(P.NR[:, t] > 0) & ~P.excl[:, t]]
        cs = np.sort(cs[np.isfinite(cs)])
        pct[a:b] = np.searchsorted(cs, P.ADV[EL.i[a:b], t], side="right") / max(len(cs), 1)
    df = pd.DataFrame({"t": EL.t, "gb": EL.gb, "pct": pct})
    df["half"] = np.where(df.t < split, 1, 2)
    for (b, h), g in df.groupby(["gb", "half"]):
        rows.append({"what": "median cross-sectional percentile of ADV60 (all non-excluded names with a bar in the window)", "band": BANDS[b],
                     "half": h, "value": g.pct.median(), "n_name_days": len(g)})
    for b, g in df.groupby("gb"):
        rows.append({"what": "eligible name-days", "band": BANDS[b], "half": 0, "value": len(g),
                     "n_name_days": len(g)})
        rows.append({"what": "mean eligible names per day", "band": BANDS[b], "half": 0,
                     "value": len(g) / (P.s1 - P.s0 + 1), "n_name_days": len(g)})
        rows.append({"what": "median spread estimate s", "band": BANDS[b], "half": 0,
                     "value": float(np.nanmedian(P.SPR[EL.i[EL.gb == b], EL.t[EL.gb == b]])), "n_name_days": len(g)})
    kk = P.KK[EL.i, EL.t]
    for k in (1, 2, 3, 4, 5, 10, 20, 50):
        rows.append({"what": f"share of eligible name-days with k = {k}", "band": "all", "half": 0,
                     "value": float((kk == k).mean()), "n_name_days": EL.n})
    rows.append({"what": "share of eligible name-days with k > 1", "band": "all", "half": 0,
                 "value": float((kk > 1).mean()), "n_name_days": EL.n})
    return pd.DataFrame(rows)


def exclusion_counts(S, Fd, eflag):
    r = S.all_rules
    rows = [{"rule": k, "symbols": int(r[k].sum())} for k in ("a", "b", "c", "d")]
    rows.append({"rule": "a-d any", "symbols": int((r.a | r.b | r.c | r.d).sum())})
    rows.append({"rule": "known (in either listing file)", "symbols": int(r.known.sum())})
    rows.append({"rule": "e (unknown symbols tested)", "symbols": int((~S.rules.known).sum())})
    sl = slice(S.s0, S.s1 + 1)
    rows.append({"rule": "e (flagged as fund at some date)", "symbols": int(eflag[:, sl].any(1).sum()),
                 "name_days_in_sample": int((eflag[:, sl] & S.real[:, sl]).sum())})
    rows.append({"rule": "b6 fund universe (a, or b-fund, not c)", "symbols": int(((r.a | r.bfund) & ~r.c).sum())})
    return pd.DataFrame(rows)


# ============================================================================ Control (i): null panels

@njit(parallel=True, cache=True)
def _redraw(O, H, L, C, F, SV, real, seeds):
    """Per name: redraw (open, high, low relative to the prior close, close-to-close total return, volume) with
    replacement from the name's own real bars that follow a real bar; rebuild prices from the first real close."""
    N, T = C.shape
    O2 = np.full((N, T), np.nan, np.float32); H2 = O2.copy(); L2 = O2.copy(); C2 = O2.copy(); V2 = O2.copy()
    for i in prange(N):
        np.random.seed(seeds[i])
        idx = np.empty(T, np.int64)
        n = 0
        for t in range(T):
            if real[i, t]:
                idx[n] = t
                n += 1
        if n == 0:
            continue
        t0 = idx[0]
        O2[i, t0] = O[i, t0]; H2[i, t0] = H[i, t0]; L2[i, t0] = L[i, t0]; C2[i, t0] = C[i, t0]; V2[i, t0] = SV[i, t0]
        if n < 2:
            continue
        ro = np.empty(n - 1); rh = np.empty(n - 1); rl = np.empty(n - 1); rc = np.empty(n - 1); rv = np.empty(n - 1)
        for j in range(1, n):
            t = idx[j]; tp = idx[j - 1]
            pc = C[i, tp] * F[i, tp]
            ro[j - 1] = O[i, t] * F[i, t] / pc; rh[j - 1] = H[i, t] * F[i, t] / pc
            rl[j - 1] = L[i, t] * F[i, t] / pc; rc[j - 1] = C[i, t] * F[i, t] / pc; rv[j - 1] = SV[i, t]
        prev = C[i, t0]
        for j in range(1, n):
            u = np.random.randint(0, n - 1)
            t = idx[j]
            O2[i, t] = prev * ro[u]; H2[i, t] = prev * rh[u]; L2[i, t] = prev * rl[u]
            C2[i, t] = prev * rc[u]; V2[i, t] = rv[u]
            prev = prev * rc[u]
    return O2, H2, L2, C2, V2


def null_panel(S, j):
    seeds = np.random.default_rng([20261018, j]).integers(0, 2 ** 31 - 1, S.N)
    O2, H2, L2, C2, V2 = _redraw(S.O, S.H, S.L, S.C, S.F, S.SV, S.real, seeds)
    P = SimpleNamespace(name=f"null {j}", kind="BH", uid=_uid(), dates=S.dates, tickers=S.tickers, N=S.N, T=S.T,
                        s0=S.s0, s1=S.s1,
                        O=O2, H=H2, L=L2, C=C2, SV=V2, F=np.ones((S.N, S.T), np.float32), present=S.real.copy(),
                        KK=S.KK, ONGRID=S.ONGRID, WCL=S.WCL, WCH=S.WCH, excl=S.excl, rules=S.rules)
    P = finish_panel(P, grid=False)
    return P


def run_nulls(S, cf, ry, n, out_csv):
    rows = []
    for j in range(n):
        t0 = time.time()
        P = null_panel(S, j)
        EL, BC, sig = prepare(P, cf, ry)
        rows.append({"null": j} | primary_stats_only(P, EL, BC, sig))
        print(f"  null panel {j}: {time.time() - t0:.0f}s", flush=True)
        del P, EL, BC, sig
        pd.DataFrame(rows).to_csv(out_csv, index=False)
    return pd.DataFrame(rows)


# ============================================================================ synthetic no-edge market (General rules)

@njit(cache=True)
def _syn_ticks(nn, T, sigma, hs, p_active, lam, dollars, seed):
    """Random-walk mid; on an active day 1 + Poisson(lam) prints at uniform times, each at mid x (1 +- hs) with an
    aggressor side independent of the mid, rounded to the cent; daily OHLCV from the prints."""
    np.random.seed(seed)
    O = np.full((nn, T), np.nan); H = O.copy(); L = O.copy(); C = O.copy(); V = np.zeros((nn, T))
    for i in range(nn):
        mid = 10.0
        prevc = 10.0
        for t in range(T):
            if np.random.random() < p_active:
                k = 1 + np.random.poisson(lam)
                times = np.sort(np.random.random(k))
                tau = 0.0
                o = 0.0; h = -1.0; l = 1e18; c = 0.0; v = 0.0
                for j in range(k):
                    mid *= math.exp(sigma * math.sqrt(times[j] - tau) * np.random.standard_normal())
                    tau = times[j]
                    side = 1.0 if np.random.random() < 0.5 else -1.0
                    px = max(round(mid * (1 + side * hs) * 100) / 100, 0.01)
                    sz = dollars * math.exp(np.random.standard_normal() - 0.5) / px
                    if j == 0:
                        o = px
                    h = max(h, px); l = min(l, px); c = px; v += sz
                mid *= math.exp(sigma * math.sqrt(1 - tau) * np.random.standard_normal())
                O[i, t] = o; H[i, t] = h; L[i, t] = l; C[i, t] = c; V[i, t] = v
                prevc = c
            else:
                mid *= math.exp(sigma * np.random.standard_normal())
                O[i, t] = prevc; H[i, t] = prevc; L[i, t] = prevc; C[i, t] = prevc; V[i, t] = 0.0
    return O, H, L, C, V


def synthetic_panel(params, nn=300, T=1000, seed=20261018):
    """params[b] = dict(s, sig20, adv, zero_vol_share) per band; returns a panel with all bands stacked."""
    frames = []
    dates = pd.bdate_range("2001-01-01", periods=T)
    for b in (1, 2, 3, 4):
        p = params[b]
        lam = {1: 8, 2: 20, 3: 50, 4: 120}[b]
        pa = 1 - p["zero_vol_share"]
        dollars = p["adv"] / (pa * (1 + lam))
        O, H, L, C, V = _syn_ticks(nn, T, p["sig20"], p["s"] / 2, pa, lam, dollars, seed + b)
        k = np.arange(nn)
        df = pd.DataFrame({"ticker": np.repeat([f"S{b}_{j:03d}" for j in k], T), "date": np.tile(dates, nn),
                           "open": O.ravel(), "high": H.ravel(), "low": L.ravel(), "close": C.ravel(), "sv": V.ravel()})
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    P = panel_from_long(df, dates, "synthetic no-edge", "SYN", (dates[80], dates[-30]))
    P.ONGRID = np.ones((P.N, P.T), bool)
    return finish_panel(P, grid=False)


def band_params(S, cf, ry):
    """Band medians (eligible B-H name-days) of the spread estimate, sigma20, ADV60 and the zero-volume share of
    the previous day, for the synthetic no-edge market. No return is computed."""
    if not hasattr(S, "SPR"):
        spread(S, cf, ry); del S.M; fee_schedule(S); S.FIRE = can_fire(S)
    E = eligibility(S)
    out = {}
    prev_tr = np.zeros_like(S.traded); prev_tr[:, 1:] = S.traded[:, :-1]
    for b in (1, 2, 3, 4):
        m = E & (S.BAND == b)
        out[b] = {"s": float(np.nanmedian(S.SPR[m])), "sig20": float(np.nanmedian(S.SIG20[m])),
                  "adv": float(np.nanmedian(S.ADV[m])), "zero_vol_share": float(1 - prev_tr[m].mean())}
    return out


def run_synthetic(params, cf):
    P = synthetic_panel(params)
    EL, BC, sig = prepare(P, cf, None)
    rows = []
    for s, b in CELLS:
        c = run_cell(P, EL, BC, sig, s, b)
        st = stat_of(P, c)
        g = stat_of(P, run_cell(P, EL, BC, sig, s, b, m=0.0, Y=0.0))
        rows.append({"cell": f"{s}-L{b}", "net_estimate": st["estimate"], "net_t": st["t"], "gross_estimate": g["estimate"],
                     "gross_t": g["t"], "n_trades": st["n_trades"], "true_half_spread": params[b]["s"] / 2,
                     "median_s_estimate": float(np.nanmedian(P.SPR[EL.i[EL.gb == b], EL.t[EL.gb == b]]))})
    return pd.DataFrame(rows)


# ============================================================================ Controls (ii) and (iii): S&P PIT

def qlib_presence(PIT):
    q = pd.read_parquet(SC / "qlib" / "panel.parquet", columns=["ticker", "date"],
                        filters=[("date", ">=", PIT.dates[0]), ("date", "<=", PIT.dates[-1])])
    q["ticker"] = q.ticker.astype(str)
    base = pd.Series([re.sub(r"-\d{6}$", "", t) for t in PIT.tickers])
    pos = {}
    for k, b in enumerate(base):
        pos.setdefault(b, []).append(k)
    di = PIT.dates.get_indexer(q.date)
    m = np.zeros((PIT.N, PIT.T), bool)
    g = pd.DataFrame({"t": q.ticker.to_numpy(), "d": di})
    g = g[(g.d >= 0) & g.t.isin(set(pos))]
    for b, gg in g.groupby("t"):
        for k in pos[b]:
            m[k, gg.d.to_numpy()] = True
    return m


def run_pit_controls(cf, ry, out):
    PIT = load_pit()
    trailing(PIT); spread(PIT, cf, ry); fee_schedule(PIT); PIT.FIRE = can_fire(PIT)
    res = []
    s0_all, s1_all = PIT.s0, PIT.s1
    # (ii) known answer: B1 gross (m = 0) on S&P PIT 2001-2010
    PIT.s1 = int(np.searchsorted(PIT.dates.values, np.datetime64("2010-12-31"), side="right") - 1)
    EL = build_el(PIT); BC = Bench(PIT, EL); sig = signals(EL)
    st = stat_of(PIT, run_cell(PIT, EL, BC, sig, "B1", 1, m=0.0))
    res.append({"control": "(ii) known answer: B1 gross (m=0) S&P 500 PIT 2001-2010", "universe": "all members"} | st
               | {"pass_nw_t_ge_2": bool(st["t"] >= 2)})
    st0 = stat_of(PIT, run_cell(PIT, EL, BC, sig, "B1", 1, m=0.0, Y=0.0))
    res.append({"control": "(ii) B1 gross, no impact either (m=0, Y=0)", "universe": "all members"} | st0)
    # (iii) survivorship calibration 2001-2020
    PIT.s1 = s1_all
    inq = qlib_presence(PIT)
    mem_all = PIT.member.copy()
    for label, mem in (("all members (dead included)", mem_all), ("members qlib has on each date", mem_all & inq)):
        PIT.member = mem
        EL = build_el(PIT); BC = Bench(PIT, EL); sig = signals(EL)
        for s in ("B1", "E1"):
            for mm, tag in ((0.0, "gross (m=0)"), (M0, "net (m=1.5)")):
                st = stat_of(PIT, run_cell(PIT, EL, BC, sig, s, 1, m=mm))
                res.append({"control": f"(iii) survivorship: {s} {tag} S&P PIT 2001-2020", "universe": label} | st)
    PIT.member = mem_all
    df = pd.DataFrame(res)
    for s in ("B1", "E1"):
        for tag in ("gross (m=0)", "net (m=1.5)"):
            a = df[(df.control == f"(iii) survivorship: {s} {tag} S&P PIT 2001-2020")]
            if len(a) == 2:
                res.append({"control": f"(iii) large-cap survivorship effect {s} {tag} (qlib-available minus all)",
                            "universe": "difference", "estimate": a.estimate.iloc[1] - a.estimate.iloc[0]})
    df = pd.DataFrame(res)
    df.to_csv(out / "controls_pit.csv", index=False)
    return df


# ============================================================================ B6 thin-ETF dislocation

def run_b6(S, Fd, eflag, cf, ry):
    """Funds removed by the exclusion rules, in L1-L4: buy at the close if the residual on the most correlated
    fund is below -2 x its trailing 60-day SD; exit t+1 (and t+5); benchmark = beta x the twin's return."""
    fr = fund_returns(Fd, FUNDS_B6)
    rows = []
    TW = np.full((len(FUNDS_B6), Fd.T), np.nan)                 # twin total-return closes
    for k, f in enumerate(FUNDS_B6):
        if f in fr:
            j = list(Fd.tickers).index(f)
            TW[k] = Fd.C[j].astype(float) * Fd.F[j]
    for P, mask_fn, label in ((Fd, lambda P: np.ones((P.N, P.T), bool), "funds (a / fund names)"),
                              (S, lambda P: eflag, "rule (e) name-days")):
        fund_rows = np.where(mask_fn(P).any(1))[0]
        if len(fund_rows) == 0:
            continue
        fund_rows = fund_rows[~np.isin(P.tickers[fund_rows], FUNDS_B6)]
        r, tw, beta, sdu = b6_twins(P, fr, fund_rows)
        if P is Fd:
            Fd.excl = np.zeros((Fd.N, Fd.T), bool)
            if not hasattr(Fd, "ADV"):
                trailing(Fd)
            spread(Fd, cf, ry); fee_schedule(Fd); Fd.FIRE = can_fire(Fd)
        E = (P.traded & (P.NR >= 40) & ((P.C / P.KK) >= 1) & (P.BAND >= 1) & (P.BAND <= 4) & P.ONGRID & P.FIRE)
        E = E[fund_rows] & mask_fn(P)[fund_rows]
        E[:, :P.s0] = False; E[:, P.s1 + 1:] = False
        rt = np.full(r.shape, np.nan)
        for k, f in enumerate(FUNDS_B6):
            if f in fr:
                rt = np.where(tw == k, fr[f][None, :], rt)
        with np.errstate(invalid="ignore"):
            u = r - beta * rt
            sigm = E & (u < -2 * sdu)
        rr, tt = np.nonzero(sigm)
        ii = fund_rows[rr]
        intl = np.array([bool(P.rules.intl.get(t, False)) if hasattr(P, "rules") else False for t in P.tickers[ii]])
        twk = tw[rr, tt].astype(np.int64)
        intl |= np.isin(np.array(FUNDS_B6)[twk], ["EFA", "EEM"])
        EL = SimpleNamespace(i=ii, t=tt, gb=P.BAND[ii, tt], n=len(ii), key=tt * P.N + ii, uid=_uid())
        for hold in (1, 5):
            tr = c2c_trades(P, EL, np.arange(len(ii)), 0, False, hold, False)
            rn, q = c2c_net(P, tr)
            k = tr["pos"]
            bt = TW[twk[k], tr["ext"]] / TW[twk[k], tr["t"]] - 1
            x = rn - beta[rr[k], tt[k]] * bt
            for scope, msk in (("all", np.ones(len(k), bool)), ("international", intl[k]), ("domestic", ~intl[k])):
                for b in (1, 2, 3, 4, 0):
                    sel = msk & ((EL.gb[k] == b) if b else np.ones(len(k), bool))
                    st = cell_stats(P, tr["t"][sel], x[sel], lags=max(10, hold + 4))
                    rows.append({"sample": label, "scope": scope, "band": BANDS[b] if b else "L1-L4", "exit": f"t+{hold}"}
                                | {kk: st[kk] for kk in ("estimate", "se", "t", "p_one_sided", "n_trades", "half1", "half2")})
    return pd.DataFrame(rows)


# ============================================================================ Part D

def run_d1(P, EL):
    """D1 capacity model: band medians of the round-trip cost and the paper gain at 1-25% of ADV60."""
    rows = []
    for b in range(1, 7):
        s = EL.gb == b
        ii, tt = EL.i[s], EL.t[s]
        if len(ii) == 0:
            continue
        sp = P.SPR[ii, tt].astype(float); sg = np.nan_to_num(P.SIG20[ii, tt].astype(float)); adv = P.ADV[ii, tt].astype(float)
        for pct in (0.01, 0.05, 0.10, 0.25):
            Q = pct * adv
            for Y in (0.5, 1.0):
                imp = Y * sg * np.sqrt(np.maximum(0, Q - DEPTH[b]) / adv)
                rt = M0 * sp + 2 * imp
                paper_tmp = Y * sg * np.sqrt(Q / adv)
                rows.append({"band": BANDS[b], "pct_adv": pct, "Y": Y, "n_name_days": len(ii),
                             "median_Q_$": np.median(Q), "median_round_trip_cost": np.nanmedian(rt),
                             "median_round_trip_cost_$": np.nanmedian(rt * Q),
                             "median_paper_gain_temporary": np.nanmedian(paper_tmp),
                             "median_paper_gain_permanent_2_3": np.nanmedian(paper_tmp * 2 / 3),
                             "median_s": np.nanmedian(sp), "median_sigma20": np.nanmedian(sg), "median_adv60": np.median(adv)})
    return pd.DataFrame(rows)


def run_d2(P, EL, BC, sig):
    rows = []
    for b in range(1, 7):
        pos = np.where(sig["D2"] & (EL.gb == b))[0]
        for h in (1, 5, 20):
            tr = c2c_trades(P, EL, pos, 0, False, h, False)
            g = np.where(tr["flag"] == 1, (1 + tr["glast"]) * 0.7 - 1, tr["g"])
            x = g - band_excess(P, EL, BC.get(0, False, h, False), tr["pos"])
            st = cell_stats(P, tr["t"], x, lags=h + 4)
            rows.append({"panel": P.name, "band": BANDS[b], "h": h} |
                        {k: st[k] for k in ("estimate", "se", "t", "p_one_sided", "n_trades", "half1", "half2")})
    return pd.DataFrame(rows)


@njit(cache=True)
def _d3_sim(kind, ot, oi, K, C, F, H, L, KK, DV, ADV, SPR, SIG, BAND, traded, WCL, WCH, shares_out, depth, m, Y,
            sec, taf, tafcap, last_tr, s0, s1, NS, tgt, lmult, SIG_B3, maxday):
    """D3 deployed-capital simulation for one cell and one K (see module docstring, choice 21).
    kind 0: market buy at the close of t, exit from t+1; 1: B3 limit at t+1, exit at the close of t+1;
    2: B4 limit at t+1, GTC sells t+2..t+1+NS, then exits from t+1+NS. Exits sell <= 20% ADV60 per day."""
    N, T = C.shape
    no = len(ot)
    maxp = min(no + 1, 400000)                    # position slots, reused once a position is closed
    p_i = np.empty(maxp, np.int64); p_units = np.empty(maxp); p_cost = np.empty(maxp); p_first = np.empty(maxp, np.int64)
    p_A = np.empty(maxp); p_kk = np.empty(maxp); p_gtc_end = np.empty(maxp, np.int64)
    p_open = np.zeros(maxp, np.bool_); p_start_exit = np.full(maxp, -1, np.int64); p_lastgood = np.empty(maxp, np.int64)
    free = np.arange(maxp)[::-1].copy()
    nfree = maxp
    holding = np.zeros(N, np.bool_)
    act = np.empty(maxp, np.int64)
    nact = 0
    npos = 0
    in_use = 0.0
    pnl = 0.0; entered = 0.0
    dep = np.zeros(T); lt_days = 0
    exit_days_sum = 0.0; n_closed = 0
    k = 0
    mp = maxday + 1
    pend_i = np.empty(mp, np.int64); pend_amt = np.empty(mp); pend_B = np.empty(mp); pend_kk = np.empty(mp)
    pend_t = np.empty(mp, np.int64); pend_A = np.empty(mp)
    npend = 0
    for d in range(s0, min(T, s1 + 60)):
        buy_d = 0.0; sell_d = 0.0; sh_d = 0.0
        # 1) limit fills during day d for orders placed at d-1
        for u in range(npend):
            i = pend_i[u]
            if not traded[i, d]:
                continue
            kk = pend_kk[u]; B = pend_B[u]
            lo = L[i, d] / kk; hi = H[i, d] / kk
            if not (lo <= B - 0.01 + 1e-6 * B and WCL[i, d]):
                continue
            f = 1.0 if hi - lo <= 1e-6 * hi else min(max((B - lo) / (hi - lo), 0.0), 1.0)
            q = min(pend_amt[u], 0.1 * DV[i, d] * f)
            if shares_out[i] == shares_out[i]:
                q = min(q, 0.049 * shares_out[i] * B)
            if q <= 0 or nfree == 0:
                continue
            p = free[nfree - 1]; nfree -= 1; npos += 1
            p_start_exit[p] = -1
            p_i[p] = i; p_units[p] = q / (B * kk * F[i, d]); p_cost[p] = q; p_open[p] = True; p_kk[p] = kk
            p_A[p] = pend_A[u]; p_gtc_end[p] = d + NS if kind == 2 else d - 1
            p_first[p] = d if kind == 1 else d + NS
            p_lastgood[p] = d
            holding[i] = True
            act[nact] = p; nact += 1
            in_use += q; entered += q; buy_d += q; sh_d += q / B
        npend = 0
        # 2) GTC sells (B4) during day d, then exits at the close of d (open positions only)
        nkeep = 0
        for u in range(nact):
            p = act[u]
            if not p_open[p]:
                free[nfree] = p; nfree += 1
                continue
            act[nkeep] = p; nkeep += 1
        nact = nkeep
        for u in range(nact):
            p = act[u]
            if not p_open[p]:
                continue
            i = p_i[p]
            if kind == 2 and d <= p_gtc_end[p] and d > p_gtc_end[p] - NS and traded[i, d]:
                kk = p_kk[p]; A = p_A[p]
                hi = H[i, d] / kk; lo = L[i, d] / kk
                if hi >= A + 0.01 - 1e-6 * A and WCH[i, d]:
                    fs = 1.0 if hi - lo <= 1e-6 * hi else min(max((hi - A) / (hi - lo), 0.0), 1.0)
                    val_sh = p_units[p] * C[i, d] * F[i, d] / (C[i, d] / kk)       # traded shares held
                    sell_sh = min(val_sh, 0.1 * DV[i, d] * fs / A)
                    if sell_sh > 0:
                        notional = sell_sh * A
                        fee = (sec[d] * notional if notional > 500 else 0.0) + (min(taf[d] * sell_sh, tafcap[d]) if sell_sh > 50 else 0.0)
                        frac = sell_sh / val_sh
                        pnl += notional - fee - p_cost[p] * frac
                        in_use -= p_cost[p] * frac
                        p_cost[p] *= (1 - frac); p_units[p] *= (1 - frac)
                        sell_d += notional; sh_d += sell_sh
                        if p_start_exit[p] < 0:
                            p_start_exit[p] = d
                        if p_units[p] <= 1e-12:
                            p_open[p] = False; holding[i] = False
                            exit_days_sum += d - p_start_exit[p] + 1; n_closed += 1
            if not p_open[p] or d < p_first[p]:
                continue
            if traded[i, d]:
                p_lastgood[p] = d
                px = C[i, d] * F[i, d]
                val = p_units[p] * px
                amt = min(val, 0.2 * ADV[i, d]) if ADV[i, d] == ADV[i, d] else val
                if amt <= 0:
                    continue
                sg = SIG[i, d] if SIG[i, d] == SIG[i, d] else 0.0
                adv = max(ADV[i, d], 1000.0) if ADV[i, d] == ADV[i, d] else 1e12
                cst = m * SPR[i, d] / 2 + Y * sg * math.sqrt(max(0.0, amt - depth[BAND[i, d]]) / adv)
                shs = amt / (C[i, d] / KK[i, d])
                fee = (sec[d] * amt if amt > 500 else 0.0) + (min(taf[d] * shs, tafcap[d]) if shs > 50 else 0.0)
                frac = amt / val
                pnl += amt * (1 - cst) - fee - p_cost[p] * frac
                in_use -= p_cost[p] * frac
                p_cost[p] *= (1 - frac); p_units[p] *= (1 - frac)
                sell_d += amt; sh_d += shs
                if p_start_exit[p] < 0:
                    p_start_exit[p] = d
                if frac >= 1 - 1e-12:
                    p_open[p] = False; holding[i] = False
                    exit_days_sum += d - p_start_exit[p] + 1; n_closed += 1
            elif d - max(p_lastgood[p], p_first[p] - 1) > 20:
                dl = p_lastgood[p]
                px = C[i, dl] * F[i, dl]
                pen = 0.0 if (last_tr[i] < d and last_tr[i] > s1) else 0.30
                pnl += p_units[p] * px * (1 - pen) - p_cost[p]
                in_use -= p_cost[p]; p_cost[p] = 0.0
                p_open[p] = False; holding[i] = False
                exit_days_sum += 21; n_closed += 1
        # 3) new orders at the close of d
        if d <= s1:
            n_d = 0
            k2 = k
            while k2 < no and ot[k2] == d:
                if not (kind == 2 and holding[oi[k2]]):
                    n_d += 1
                k2 += 1
            avail = max(K - in_use, 0.0)
            alloc = avail / n_d if n_d > 0 else 0.0
            while k < no and ot[k] == d:
                i = oi[k]
                k += 1
                if alloc <= 0 or (kind == 2 and holding[i]):
                    continue
                kk = KK[i, d]
                P = C[i, d] / kk
                if kind == 0:
                    q = min(alloc, 0.1 * DV[i, d])
                    if shares_out[i] == shares_out[i]:
                        q = min(q, 0.049 * shares_out[i] * P)
                    if q <= 0 or nfree == 0:
                        continue
                    sg = SIG[i, d] if SIG[i, d] == SIG[i, d] else 0.0
                    adv = max(ADV[i, d], 1000.0)
                    ce = m * SPR[i, d] / 2 + Y * sg * math.sqrt(max(0.0, q - depth[BAND[i, d]]) / adv)
                    p = free[nfree - 1]; nfree -= 1; npos += 1
                    p_start_exit[p] = -1
                    p_i[p] = i; p_units[p] = q / (C[i, d] * F[i, d] * (1 + ce)); p_cost[p] = q; p_open[p] = True
                    p_first[p] = d + 1; p_lastgood[p] = d; p_kk[p] = kk; p_gtc_end[p] = d
                    act[nact] = p; nact += 1
                    in_use += q; entered += q; buy_d += q; sh_d += q / P
                else:
                    if kind == 1:
                        B = math.floor(P * (1 - lmult * SIG_B3[i, d + 1 if d + 1 < T else d]) * 100 + 1e-7) / 100
                        A = 0.0
                    else:
                        B = math.floor(P * (1 - SPR[i, d] / 2) * 100 + 1e-7) / 100
                        A = math.ceil(B * (1 + (tgt if tgt > 0 else SPR[i, d])) * 100 - 1e-7) / 100
                    if not (B > 0):
                        continue
                    u = npend; npend += 1
                    pend_i[u] = i; pend_amt[u] = alloc; pend_B[u] = B; pend_kk[u] = kk; pend_t[u] = d; pend_A[u] = A
            dep[d] = in_use
        if buy_d + sell_d >= 20e6 or sh_d >= 2e6:
            lt_days += 1
    return pnl, entered, dep, lt_days, (exit_days_sum / n_closed if n_closed > 0 else np.nan), npos


def run_d3(P, EL, sig, label):
    rows = []
    so = getattr(P, "shares_out", np.full(P.N, np.nan))
    days = P.s1 - P.s0 + 1
    for s in STRATS:
        for b in (1, 2, 3, 4, 0):
            sel = (EL.gb == b) if b else ((EL.gb >= 1) & (EL.gb <= 4))
            if s in ("B1", "B2", "E1"):
                sel = sel & sig[s]
            kind = 0 if s in ("B1", "B2", "E1") else (1 if s == "B3" else 2)
            o = np.where(sel)[0]
            ot, oi = EL.t[o], EL.i[o]
            maxday = int(np.bincount(ot).max()) if len(ot) else 1
            for K in (1e4, 5e4, 2.5e5, 1e6, 5e6):
                pnl, ent, dep, lt, dte, npos = _d3_sim(kind, ot, oi, K, P.C, P.F, P.H, P.L, P.KK, P.DV, P.ADV, P.SPR,
                                                       P.SIG20, P.BAND, P.traded, P.WCL, P.WCH, so.astype(float), DEPTH,
                                                       M0, Y0, P.sec, P.taf, P.tafcap, P.last_tr, P.s0, P.s1, 5, 0.0,
                                                       1.0, P.SIG20, maxday)
                dd = dep[P.s0:P.s1 + 1]
                rpd = pnl / ent if ent > 0 else np.nan
                rows.append({"panel": label, "strategy": s, "band": BANDS[b] if b else "L1-L4", "K": K,
                             "capital_deployed_mean": dd.mean(), "capital_deployed_p5": np.percentile(dd, 5),
                             "net_$_per_year": pnl / (days / 252), "net_return_on_K": pnl / (days / 252) / K,
                             "return_per_$_entered": rpd, "entered_$_per_year": ent / (days / 252),
                             "mean_days_to_exit": dte, "large_trader_days": lt, "positions": npos})
    d = pd.DataFrame(rows)
    out = []
    for (s, b), g in d.groupby(["strategy", "band"], sort=False):
        g = g.sort_values("K")
        r0 = g["return_per_$_entered"].iloc[0]
        Ks, rp = g.K.to_numpy(), g["return_per_$_entered"].to_numpy()
        kh = kz = np.nan
        if r0 > 0:
            for a in range(1, len(Ks)):
                if np.isnan(kh) and rp[a] <= r0 / 2:
                    kh = _logint(Ks[a - 1], Ks[a], rp[a - 1], rp[a], r0 / 2)
                if np.isnan(kz) and rp[a] <= 0:
                    kz = _logint(Ks[a - 1], Ks[a], rp[a - 1], rp[a], 0.0)
        out.append({"strategy": s, "band": b, "K_half": kh if r0 > 0 else "return <= 0 at $10k",
                    "K_zero": kz if r0 > 0 else "<= $10k", "note": "NaN = not reached by $5M"})
    return d, pd.DataFrame(out)


def _logint(k0, k1, r0, r1, target):
    if r1 == r0:
        return k1
    w = (r0 - target) / (r0 - r1)
    return float(np.exp(np.log(k0) + w * (np.log(k1) - np.log(k0))))


@njit(cache=True)
def _d4_one(i, t, Qd, C, F, H, L, DV, SPR, SIG, traded, m, Y, sec, taf, tafcap, KK, maxd):
    """D4: buy Qd dollars at <= 20% of each traded day's $ volume at typical x (1 + m s/2 + Y sigma sqrt(b/V)); mark
    at the last buy day's close + 2/3 of the buy-weighted temporary impact; from 5 sessions later sell under the
    same rules (gap rule -30%). Returns paper and realized P&L fractions of cost, days to enter, days to exit,
    last buy day and last sell day."""
    T = C.shape[1]
    rem = Qd; units = 0.0; cost = 0.0; impw = 0.0; d = t; lastb = -1; nb = 0
    while rem > 1e-9 and d < T and d - t < maxd:
        if traded[i, d]:
            b = min(rem, 0.2 * DV[i, d])
            if b > 0:
                typ = (H[i, d] + L[i, d] + C[i, d]) / 3 * F[i, d]
                sg = SIG[i, d] if SIG[i, d] == SIG[i, d] else 0.0
                tmp = Y * sg * math.sqrt(b / DV[i, d])
                px = typ * (1 + m * SPR[i, d] / 2 + tmp)
                units += b / px; cost += b; impw += b * tmp; rem -= b; lastb = d; nb += 1
        d += 1
    if lastb < 0:
        return np.nan, np.nan, np.nan, np.nan, -1, -1
    perm = 2.0 / 3.0 * impw / cost
    paper = units * C[i, lastb] * F[i, lastb] * (1 + perm) / cost - 1
    d = lastb + 5
    proceeds = 0.0; lastgood = lastb; lasts = -1; first = -1
    while units > 1e-12 and d < T:
        if traded[i, d]:
            lastgood = d
            typ = (H[i, d] + L[i, d] + C[i, d]) / 3 * F[i, d]
            val = units * typ
            s_ = min(val, 0.2 * DV[i, d])
            sg = SIG[i, d] if SIG[i, d] == SIG[i, d] else 0.0
            px = typ * (1 - m * SPR[i, d] / 2 - Y * sg * math.sqrt(s_ / DV[i, d]))
            sh = s_ / (typ / F[i, d] / KK[i, d])
            fee = (sec[d] * s_ if s_ > 500 else 0.0) + (min(taf[d] * sh, tafcap[d]) if sh > 50 else 0.0)
            proceeds += s_ / typ * px - fee
            units -= s_ / typ
            lasts = d
            if first < 0:
                first = d
        elif d - lastgood > 20:
            proceeds += units * C[i, lastgood] * F[i, lastgood] * 0.7
            units = 0.0; lasts = d
        d += 1
    if units > 1e-12:
        return paper, np.nan, lastb - t + 1, np.nan, lastb, -1
    return paper, proceeds / cost - 1, lastb - t + 1, (lasts - first + 1) if first >= 0 else 21.0, lastb, lasts


def run_d4(P, EL, label, years=None):
    rng = np.random.default_rng(20261018)
    rows = []
    ok_t = np.ones(EL.n, bool)
    if years is not None:
        yr = P.dates.year.to_numpy()[EL.t]
        ok_t = (yr >= years[0]) & (yr <= years[1])
    starts = np.searchsorted(EL.t, np.arange(P.T + 1))
    for b in (1, 2, 3, 4, 5):
        cand = np.where((EL.gb == b) & ok_t & (EL.t < P.T - 90))[0]
        if len(cand) == 0:
            continue
        pick = rng.choice(cand, size=min(200, len(cand)), replace=False)
        for pct in (0.05, 0.10, 0.25, 1.00):
            res = []
            for k in pick:
                i, t = EL.i[k], EL.t[k]
                Qd = pct * P.ADV[i, t]
                pa, re_, de, dx, lb, ls = _d4_one(i, t, Qd, P.C, P.F, P.H, P.L, P.DV, P.SPR, P.SIG20, P.traded, M0, Y0,
                                                  P.sec, P.taf, P.tafcap, P.KK, 120)
                if lb < 0:
                    continue
                peers = np.arange(starts[t], starts[t + 1])
                peers = peers[(EL.gb[peers] == b) & (EL.i[peers] != i)]
                bp = _ew(P, EL.i[peers], t - 1, lb)
                br = _ew(P, EL.i[peers], t - 1, ls) if ls >= 0 else np.nan
                res.append((pa - bp, re_ - br, de, dx))
            a = np.array(res, float)
            if len(a) == 0:
                continue
            gap = a[:, 0] - a[:, 1]
            rows.append({"panel": label, "band": BANDS[b], "Q_pct_adv60": pct, "n": len(a),
                         "paper_mean": np.nanmean(a[:, 0]), "paper_median": np.nanmedian(a[:, 0]),
                         "paper_p5": np.nanpercentile(a[:, 0], 5), "realized_mean": np.nanmean(a[:, 1]),
                         "realized_median": np.nanmedian(a[:, 1]), "realized_p5": np.nanpercentile(a[:, 1], 5),
                         "gap_mean": np.nanmean(gap), "gap_median": np.nanmedian(gap),
                         "days_to_enter_mean": np.nanmean(a[:, 2]), "days_to_exit_mean": np.nanmean(a[:, 3])})
    return pd.DataFrame(rows)


def _ew(P, ii, a, d):
    """EW gross return of names ii from the close of day a to the close of day d (gap rule)."""
    if len(ii) == 0 or a < 0 or d <= a:
        return 0.0
    tt = np.full(len(ii), a, np.int64)
    _, _, g, glast, flag = _legs(ii.astype(np.int64), tt, 0, False, d - a, False, P.O, P.C, P.F, P.traded, P.last_tr, P.s1)
    g = np.where(flag == 1, (1 + glast) * 0.7 - 1, g)
    g = g[(flag >= 0) & (flag != 3)]
    return float(np.nanmean(g)) if len(g) else 0.0


# ============================================================================ main

def _trim():
    """Return freed heap memory to the OS (the qlib long frame is ~2 GB before it is pivoted)."""
    import ctypes
    import gc
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:
        pass


def say_factory(path):
    fh = open(path, "w")

    def say(*a):
        s = " ".join(str(x) for x in a)
        print(s, flush=True); fh.write(s + "\n"); fh.flush()
    return say


def load_vix(P):
    """VIX close on each panel date (forward-filled) and the tercile cut points over the sample days."""
    v = pd.read_csv(DATA / "macro" / "VIXCLS.csv", parse_dates=["date"]).set_index("date").value
    v = pd.to_numeric(v, errors="coerce").reindex(P.dates).ffill().to_numpy()
    qs = np.concatenate([[-np.inf], np.nanpercentile(v[P.s0:P.s1 + 1], [100 / 3, 200 / 3]), [np.inf]])
    return SimpleNamespace(v=v, qs=qs)


def build_all(smoke=False, say=print, br_root=None):
    """Load B-H (and B-R or its stand-in), apply the exclusion rules, compute trailing stats, fit the cost model,
    compute R_y and write cost_model.csv. No return is computed here."""
    t0 = time.time()
    if smoke:
        S, Fd = load_bh("2009-01-02", "2011-03-31", ("2010-01-01", "2010-12-31"))
    else:
        S, Fd = load_bh()
    del S.present, Fd.present
    _trim()
    say(f"B-H loaded: {S.N} stock symbols, {Fd.N} fund symbols, {S.T} days ({time.time() - t0:.0f}s)")
    fr = fund_returns(Fd, FUNDS_E)
    t1 = time.time()
    eflag = rule_e(S, fr)
    S.excl = eflag.copy()
    say(f"rule (e): {int(eflag.any(1).sum())} unknown symbols flagged as funds ({time.time() - t1:.0f}s)")
    t1 = time.time()
    trailing(S)
    _trim()
    say(f"trailing statistics: {time.time() - t1:.0f}s")
    BR = load_br(root=br_root)
    br_flag = "B-R"
    if BR is None:
        BR = load_pilot40()
        br_flag = "pilot40 stand-in (B-R not yet pulled)"
    trailing(BR)
    cf = fit_cost_model(BR)
    ry = ry_table(S, BR, cf)
    say(f"cost model fitted on {cf['n_fit']} names ({cf['fit_sample']}): b = {cf['b0']:.3f}, {cf['b1']:.3f}, "
        f"{cf['b2']:.3f}, {cf['b3']:.3f}; S = {cf['S']:.3f}; R2 = {cf['r2']:.2f}")
    return S, Fd, eflag, BR, br_flag, cf, ry


def write_cost_model(cf, ry, br_flag, out):
    rows = [{"item": k, "value": v} for k, v in cf.items()]
    rows += [{"item": "c_L1", "value": 1.25}, {"item": "c_L2_L6", "value": 1 / 1.4}, {"item": "R_y denominator sample",
             "value": br_flag}]
    rows += [{"item": f"D_k L{b}", "value": DEPTH[b]} for b in range(1, 7)]
    rows += [{"item": f"R_y {int(r.year)}", "value": r.R_y, "num": r.num_median_EDGE_over_M_prev_year, "n_num": r.n_num,
              "den": r.den_median_EDGE_over_M_BR, "n_den": r.n_den} for r in ry.itertuples()]
    pd.DataFrame(rows).to_csv(out / "cost_model.csv", index=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--nulls", type=int, default=0)
    ap.add_argument("--br-root", default=None, help="folder with daily_split/daily_none.parquet (default data/scalping/rh)")
    a = ap.parse_args(argv)
    outB = (SCRATCH / "smoke_B") if a.smoke else (OUT / "B")
    outD = (SCRATCH / "smoke_D") if a.smoke else (OUT / "D")
    outB.mkdir(parents=True, exist_ok=True); outD.mkdir(parents=True, exist_ok=True)
    tdir = (SCRATCH / "smoke_trades") if a.smoke else (SC / "B")
    tdir.mkdir(parents=True, exist_ok=True)
    say = say_factory(outB / ("summary_controls.txt" if a.controls and not (a.run or a.smoke) else "summary.txt"))
    T0 = time.time()
    S, Fd, eflag, BR, br_flag, cf, ry = build_all(a.smoke, say, a.br_root)
    write_cost_model(cf, ry, br_flag, outB)
    say(f"cost_model.csv written before any return ({outB / 'cost_model.csv'})")
    say("Points where the pre-registration could not be followed as written (see the module docstring):")
    if br_flag != "B-R":
        say("  - B-R daily bars not pulled: cost model fitted on the 40 pilot names (not the 1,167), R_y's denominator"
            " from the same 40 names, cond_br (PASS condition 3) not evaluable, Part D1/D2(B-R)/D4 on the 40 names.")
    say("  - B-H sell fees: an upper bound (SEC 0.30 bp + TAF $0.000119/sh, cap $5.95) instead of the dated schedule.")
    say("  - D3's 4.9%-of-shares-outstanding cap: B-R only (current snapshot); B-H has no shares outstanding.")
    say("  - qlib freezes 2,155 names at 2020-11-10: missing exits after the sample end are censored, not delisted.")
    if a.controls:
        t1 = time.time()
        df = run_pit_controls(cf, ry, outB)
        say(f"\nControls (ii)/(iii) on the S&P 500 PIT set ({time.time() - t1:.0f}s):")
        say(df[["control", "universe", "estimate", "t", "n_trades"]].to_string(index=False))
        _trim()
        t1 = time.time()
        params = band_params(S, cf, ry)
        syn = run_synthetic(params, cf)
        syn.to_csv(outB / "controls_synthetic.csv", index=False)
        say(f"\nSynthetic no-edge market ({time.time() - t1:.0f}s); parameters from B-H band medians: {params}")
        say(syn.to_string(index=False))
    if a.run or a.smoke:
        t1 = time.time()
        EL, BC, sig = prepare(S, cf, ry)
        say(f"eligibility and signals: {EL.n:,} eligible name-days ({time.time() - t1:.0f}s)")
        exc = exclusion_counts(S, Fd, eflag)
        exc.to_csv(outB / "exclusions.csv", index=False)
        BRp = None
        if br_flag == "B-R":
            ELr, BCr, sigr = prepare(BR, cf, None)
            BRp = (BR, ELr, BCr, sigr)
        nulls = None
        npath = outB / "null_panels.csv"
        if npath.exists() and not a.smoke:
            nd = pd.read_csv(npath)
            nulls = {c: nd[c].to_numpy() for c in nd.columns if c != "null"}
        t1 = time.time()
        prim, rep, trades = run_primary(S, EL, BC, sig, Fd, BRp, nulls, quiet=False)
        say(f"primary cells + per-cell report: {time.time() - t1:.0f}s; trades per cell: "
            + ", ".join(f"{r.test_id} {r.n_trades}" for r in prim.itertuples()))
        if not a.smoke:
            prim.to_csv(outB / "primary_cells.csv", index=False)
            rep.to_csv(outB / "cell_report.csv", index=False)
            if trades is not None:
                trades.to_parquet(tdir / "trades_primary.parquet", index=False)
            p = holm(prim.p_one_sided.to_numpy())
            say("\n(provisional within-part Holm, B+E only, for sanity; the study-wide Holm is in the combine script)")
            say(pd.DataFrame({"test_id": prim.test_id, "estimate_bp": prim.estimate * 1e4, "t": prim.t,
                              "p_holm_within": p}).to_string(index=False))
        else:
            prim.to_csv(outB / "primary_cells_SMOKE_DO_NOT_READ.csv", index=False)
        t1 = time.time()
        vix = load_vix(S)
        ex = run_exploratory(S, EL, BC, sig, vix)
        ill = run_illusion(S, EL, BC, sig)
        ill.to_csv(outB / "illusion.csv", index=False)
        descriptive(S, EL).to_csv(outB / "descriptive.csv", index=False)
        BC.c.clear(); _TRC.clear(); _trim()
        ex = pd.concat([ex, run_k1_rows(S, cf, ry)], ignore_index=True)
        ex.to_csv(outB / "exploratory.csv", index=False)
        _trim()
        say(f"exploratory ({len(ex)} rows), illusion, descriptive: {time.time() - t1:.0f}s")
        t1 = time.time()
        b6 = run_b6(S, Fd, eflag, cf, ry)
        b6.to_csv(outB / "b6.csv", index=False)
        say(f"B6: {time.time() - t1:.0f}s ({len(b6)} rows)")
        t1 = time.time()
        BRx = BR
        ELx, BCx, sigx = BRp[1:] if BRp is not None else prepare(BR, cf, None)
        d1 = run_d1(BRx, ELx); d1["source"] = br_flag; d1.to_csv(outD / "d1_capacity.csv", index=False)
        d2 = pd.concat([run_d2(S, EL, BC, sig), run_d2(BRx, ELx, BCx, sigx).assign(source=br_flag)])
        d2.to_csv(outD / "d2_giveback.csv", index=False)
        d3, d3k = run_d3(S, EL, sig, "B-H")
        if br_flag == "B-R":
            d3b, d3kb = run_d3(BRx, ELx, sigx, "B-R")
            d3 = pd.concat([d3, d3b]); d3k = pd.concat([d3k.assign(panel="B-H"), d3kb.assign(panel="B-R")])
        d3.to_csv(outD / "d3_deployed_capital.csv", index=False); d3k.to_csv(outD / "d3_K_half_zero.csv", index=False)
        d4 = pd.concat([run_d4(BRx, ELx, br_flag), run_d4(S, EL, "B-H 2011-2020", (2011, 2020))])
        d4.to_csv(outD / "d4_accumulate_exit.csv", index=False)
        say(f"Part D: {time.time() - t1:.0f}s")
    if a.nulls and not a.smoke:
        t1 = time.time()
        nd = run_nulls(S, cf, ry, a.nulls, outB / "null_panels.csv")
        say(f"{a.nulls} null panels: {time.time() - t1:.0f}s. Rerun --run to fill cond_null.")
    elif a.nulls and a.smoke:
        t1 = time.time()
        nd = run_nulls(S, cf, ry, a.nulls, SCRATCH / "smoke_nulls.csv")
        say(f"{a.nulls} null panels (smoke year): {time.time() - t1:.0f}s")
    say(f"\ntotal {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
