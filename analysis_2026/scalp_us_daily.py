"""
Scalping study, Parts B, E (daily rule E1) and D: daily-horizon liquidity provision, attention continuation
and capacity in low-volume US stocks. Pre-registered in analysis_2026/SCALPING_PREREG.md (frozen
2026-10-18); this module implements the sections "Common definitions for US stocks", "Part B" (with its
controls), "Part E" (daily rule only; the intraday ORB leg is in scalp_us_intraday.py) and "Part D".

    python3 -m analysis_2026.scalp_us_daily --controls      # known answer (ii), survivorship (iii), synthetic no-edge
    python3 -m analysis_2026.scalp_us_daily --smoke         # one year of B-H, timings and counts only (scratch output)
    python3 -m analysis_2026.scalp_us_daily --run           # full primary analysis, exploratory, B6, Part D
    python3 -m analysis_2026.scalp_us_daily --run --nulls 20   # plus the 20 null panels (Control (i), PASS condition 8)
    python3 -m analysis_2026.scalp_us_daily --nulls 20      # null panels only (appends to an existing --run)

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
24. Synthetic no-edge control (General rules): per band L1-L4, 150 names x 2,500 days of Poisson trades at
    a random-walk mid +- half the band's median spread estimate, aggressor side independent of the mid,
    aggregated to daily OHLCV on a cent grid; the band's median sigma20, ADV60 and zero-volume share set the
    parameters. B1-B4 and E1 run unchanged (cost model fixed, R_y = 1).
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

def _empty(N, T, dtype=np.float32, fill=np.nan):
    return np.full((N, T), fill, dtype)


def panel_from_long(df: pd.DataFrame, dates, name, kind, sample, fields=("open", "high", "low", "close")):
    """Long frame (ticker, date, open, high, low, close, sv, fret, kk, wcl, wch) -> (N, T) arrays.
    O/H/L/C are continuous split-adjusted prices, F the factor that turns them into total-return prices,
    SV split-adjusted shares, KK the traded-price divisor (P = C / KK)."""
    dates = pd.DatetimeIndex(dates)
    tick = np.array(sorted(df.ticker.unique()))
    ti = pd.Index(tick).get_indexer(df.ticker)
    di = dates.get_indexer(df.date)
    ok = di >= 0
    ti, di, df = ti[ok], di[ok], df[ok]
    N, T = len(tick), len(dates)
    P = SimpleNamespace(name=name, kind=kind, dates=dates, tickers=tick, N=N, T=T)
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
    P.DV = (P.C * P.SV).astype(np.float32)          # continuous close x split-adjusted shares = traded $ volume
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
    p["ticker"] = p.ticker.astype(str)
    if tickers is not None:
        p = p[p.ticker.isin(set(tickers))]
    f = p.factor.astype(np.float64)
    out = pd.DataFrame({"ticker": p.ticker.values, "date": p.date.values})
    for c in ("open", "high", "low", "close"):
        out[c] = (p[c].astype(np.float64) / f).to_numpy()                 # Yahoo split-adjusted price
    out["sv"] = (p.volume.astype(np.float64) * f).to_numpy()               # split-adjusted shares
    out["fret"] = f.to_numpy()                                             # x continuous = qlib adjusted close
    return out.dropna(subset=["close"])


def load_bh(start="2000-01-03", end="2021-03-31", sample=(BH_START, BH_END)):
    """B-H panels: stocks (not excluded by (a)-(d); rule (e) applied later) and funds (B6 + rule (e) twins)."""
    ref = load_ref()
    q = load_qlib_long(start, end)
    dates = pd.DatetimeIndex(np.sort(q.date.unique()))
    rules = static_rules(sorted(q.ticker.unique()), ref)
    stock = rules.index[~(rules.a | rules.b | rules.c | rules.d)]
    fund = rules.index[((rules.a | rules.bfund) & ~rules.c) | rules.index.isin(FUNDS_B6)]
    S = finish_panel(panel_from_long(q[q.ticker.isin(set(stock))], dates, "B-H", "BH", sample), grid=True)
    Fd = finish_panel(panel_from_long(q[q.ticker.isin(set(fund))], dates, "B-H funds", "BH", sample), grid=True)
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


def load_br(sample=(BR_START, BR_END)):
    """B-R panel from Robinhood daily bars (split-adjusted for returns, unadjusted for price levels). Returns
    None if the bars have not been pulled yet."""
    ps, pn, pu = SC / "rh" / "daily_split.parquet", SC / "rh" / "daily_none.parquet", SC / "rh" / "universe.csv"
    if not (ps.exists() and pn.exists()):
        return None
    s = _rh_daily(ps); u = _rh_daily(pn)
    m = s.merge(u[["ticker", "date", "open", "high", "low", "close", "interpolated"]], on=["ticker", "date"],
                suffixes=("", "_u"), how="left")
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
    rules = static_rules(sorted(m.ticker.unique()), ref, names)
    rules["scan"] = rules.index.isin(ex)
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
        with np.errstate(invalid="ignore"):
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
    q = np.minimum(Q, 0.1 * tr["dv_ent"])
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
    with np.errstate(invalid="ignore"):
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
    q = np.minimum(Q, 0.1 * tr["dv_ent"] * tr["f"])
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
    return x, r_tot


# ============================================================================ PART3
