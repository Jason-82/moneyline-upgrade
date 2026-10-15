"""
Key-level bounces: buy when price pulls back to a moving average from above.

The user's example (2026-10-15): HOOD has been falling, touched its 200-day SMA (~94-95)
and bounced quickly to ~101. Does buying such touches work across our assets, and does it
depend on the average (daily / weekly / monthly, SMA / EMA, length)?

Two different claims hide in "buy the bounce at a key level":
  (i)  price tends to rise after it pulls back to the average (a timing edge), and
  (ii) the average itself is special - support - so touching it is better than touching
       any other nearby price (the "key level" claim).
(ii) needs a control that (i) does not: placebo lines. Every test below compares the real
average with the same average shifted by +-1 and +-2 ATR, traded with identical rules.

----------------------------------------------------------------------------- data
(gitignored; rebuild with `python3 -m analysis_2026.fetch_regime_data`)
  S&P 500 members   data/universe_pit_all: point-in-time members 1995-2026 incl. ~400 dead
                    companies (total-return-scaled OHLC). Events count only while the stock
                    is a member. PRIMARY pool for the hypotheses.
  Crypto            data/crypto_binance_regime: 40 large Binance USDT pairs incl. dead LUNA
                    and FTT, 2017-2026 (real OHLC). SECOND pool.
  Indices / ETFs    S&P 500 1962-2026 (regime_switch.load_spx_long, real ^GSPC OHLC), SPY QQQ
                    IWM DIA EFA EEM TLT IEF TIP LQD HYG GLD SLV VNQ, TSLA COIN HOOD (Yahoo,
                    split-adjusted OHLC for the averages, adj_close for returns).
  The TradingView exports are close-only, so they cannot show an intraday touch: crypto
  majors use the Binance OHLC instead.

----------------------------------------------------------------------------- averages
  daily    SMA and EMA of 20, 50, 100, 150, 200 days
  weekly   SMA and EMA of 10, 20, 30, 40, 50, 100, 200 weeks
  monthly  SMA and EMA of 6, 10, 12, 20, 24 months
  34 lines per asset. PRIMARY: the daily 200-day SMA (the user's example).
  No look-ahead: the daily average used on day t is computed through day t-1's close; a
  weekly or monthly average uses completed weeks/months only (the current, still-forming
  period is excluded, so it can lag a live chart slightly). Averages are on chart prices
  (split-adjusted; total-return-scaled for the S&P member pool).

----------------------------------------------------------------------------- events
  A TOUCH of line L on day t: the previous 10 closes were all above their line (price came
  down to it from above), and day t's low reached L.
  Placebo lines: L + k x ATR with k in {-2, -1, +1, +2} (ATR = Wilder ATR(14) through day
  t-1). Same event rule, same entries and exits.
  Entries:
    E1 limit at the level (PRIMARY): a resting buy at L fills at min(open, L) on the touch
       day (a gap below L fills at the open).
    E2 confirmed bounce: only if day t closes at or above L; buy at the close (crypto) or at
       the next session's open (stocks/ETFs).
  Exits:
    time  close of bar t+H; H = 20 trading days (crypto 28 days) PRIMARY; also 5/60 (7/84).
    X2    "support failed": the first close below L - 1 ATR, else the time exit at H.
  Costs per side: stocks/ETFs/indices 0.03%, crypto 0.30%.
  Returns are on total return (dividends included).
  Abnormal return AR = event log return - the asset's average H-bar log return over all
  days of the same calendar year (removes drift and year effects). For X2, the drift
  subtracted is the asset-year's average daily log return x days held. [AUDIT: the event log
  return is net of costs, and this baseline is biased by event selection; see the end.]

----------------------------------------------------------------------------- statistics
  Events cluster in time (sell-offs make many stocks touch at once), so every p-value comes
  from a block bootstrap that resamples calendar MONTHS (all events of a month together),
  2,000 draws, one-sided. Halves: stocks 1997-2011 / 2012-2026, crypto 2019-2022 / 2023-2026.
  [AUDIT: the code cuts at the second date only, so the first halves are 1996-2011 and
  2018-2022. Numbers were computed that way and are reported as computed.]

----------------------------------------------------------------------------- hypotheses
Pre-registered 2026-10-15 before any bounce result was computed. Known beforehand: HOOD's
current setup (37 closes above a gently falling 200-day SMA, 60-day vol 66%, ~25-31% below
its 52-week high; the 150-day, 40-week and 10-month averages all sit within 1% of it) and
the general literature (being summarised in parallel). No event statistic had been seen.

Judged on the S&P 500 member pool (B1-B5) and, separately with the same rules, on the crypto
pool (C1-C5). Primary spec: daily 200-day SMA, E1, H = 20 (crypto 28).
  B1 Bounce: mean AR > 0 with bootstrap p < 0.05, and mean AR > 0 in both halves.
  B2 Key level: mean AR(real line) - mean AR(the four placebo lines pooled) > 0 with
     p < 0.05, and > 0 in both halves.
  B3 Tradable: with the X2 exit, mean net excess return per trade > 0 with p < 0.05 and
     > 0 in both halves, AND it beats the same trade on the placebo lines (difference > 0,
     p < 0.05).
  B4 Trend: mean AR after touches of a RISING average (20-day slope > 0) exceeds mean AR
     after touches of a FALLING one, p < 0.05.
  B5 Grid: B2 run on all 34 averages; Benjamini-Hochberg at 10% FDR across the 34.
     Averages are "key levels" only if the 200-day SMA passes B2 AND at least a third of the
     34 pass B5.
  Everything else is exploratory and never changes a verdict: E2, horizons 5/60, the
  single-asset tables (S&P 500 1962-2026, ETFs, TSLA, COIN, HOOD, BTC, ETH, SOL, BNB, ZEC),
  rejection strength, first touch after a long run above, confluence of several averages,
  depth below the 52-week high, single-asset backtests, and the HOOD-like analog:
    S&P member touches of the daily 200-day SMA with 60-day vol >= 50%, >= 20% below the
    52-week high, a falling 200-day, and >= 20 closes above it before the touch.

    python3 -m analysis_2026.ma_bounce

Added after the first run (exploratory, labelled as such in the output): E2 versions of the
splits that are only known at the touch day's close (held / bounce strength), because E1 fills
at the line earlier that day and so contains the day's own move; confluence counted within
0.25 ATR (the 1-ATR count put nearly every event in one bucket); E2 and strong-bounce rows of
the HOOD-like analog.

----------------------------------------------------------------------------- AUDIT CORRECTIONS
A multi-agent audit after the first run confirmed 17 findings. Everything below is
post-registration. The pre-registered verdicts are still computed exactly as registered;
the corrections are printed next to them and never change a verdict.
  Baseline bias. The same-calendar-year drift includes the months whose price path selected
     the touch, so it is biased by event selection. With iid-resampled bars (no predictability;
     `--null R`) it reports about +0.3% at 20 days for the real line. It also produces a
     line gradient (-2 ATR > real > +2 ATR) and penalises B4 by about 0.25-0.4 pts. Two
     baselines that do not depend on the selection window are added:
       *_lo     the asset's mean forward log return over all its days except windows starting
                in [t-272, t+H] (S&P member days only for the member pool);
       ar_pool  close t -> close t+H minus the equal-weight pool mean over the same window
                (S&P members on member days; the 40-coin pool for crypto), with no fill and no cost.
     `--null R` prints the no-edge level of every primary-average statistic under all three.
  Repeat touches. A touch that closes above the line keeps the run alive, so a stock that hovers
     at its average logs an event on every touching day. 37% of stock and about half of crypto
     primary events are repeats; "first touches" (no touch of the same line in the previous
     28 days) are reported too.
  EMA. The first run seeded EMAs with the first close (wrong by up to 40% for years on long
     weekly/monthly EMAs). EMAs are now seeded with the SMA of the first n values.
  Dead assets. A horizon that runs past the end of a series that stopped trading (delisted
     stock, LUNA, FTT) now exits at the last close instead of dropping the event.
  Pool filter. Stocks with fewer than 60 rows are skipped (the first run silently required
     260 rows, which dropped 8 stocks). 157 of the 1,227 member symbols have no price file,
     mostly names that left before 2001, so 1996-2000 covers only about 80% of member-days:
     the first stock half is partly a survivor sample.
  Costs. AR (B1/B2/B4/B5) is net of the round-trip cost (stocks 0.06 pts, crypto 0.60 pts),
     not gross as the text above implies; the pool-adjusted column is gross.
  Chart lines. The member pool's OHLC is dividend-back-adjusted, so its averages sit about
     0.2 ATR (median) below the chart averages traders see, and only ~60% of touches coincide.
     The daily averages are rerun on chart prices (dividend factor from data/raw_pit; returns
     still total return). ETFs, indices, single stocks and crypto already use chart lines.
  Statistics. 3-month blocks, 95% CIs, effective sample sizes (events cluster: tens of
     thousands of stock events carry the information of under a thousand independent ones),
     and a NaN-safe bootstrap difference are added. Long-average (100-200 week, 20-24 month)
     positives must be read with the pool-adjusted column: they are the market's rebound
     after broad sell-offs, shared by every line nearby.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import atr as atr_fn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "analysis_2026" / "results_bounce"
DAILY = [20, 50, 100, 150, 200]
WEEKLY = [10, 20, 30, 40, 50, 100, 200]
MONTHLY = [6, 10, 12, 20, 24]
MAS = [(tf, kind, n) for tf, ns in (("D", DAILY), ("W", WEEKLY), ("M", MONTHLY)) for kind in ("SMA", "EMA") for n in ns]
MA_NAME = [f"{tf}-{kind}{n}" for tf, kind, n in MAS]
PRIMARY = MA_NAME.index("D-SMA200")
OFFSETS = [0.0, -2.0, -1.0, 1.0, 2.0]          # line 0 = the real average; 1-4 = placebo lines
K_APPROACH = 10
NAMED = ["SPX_LONG", "SPY", "QQQ", "IWM", "TSLA", "COIN", "HOOD", "BTC", "ETH", "SOL", "BNB", "ZEC"]
FIELDS = ["asset", "ma", "line", "day", "held", "gap", "slope", "run", "reject", "dd252", "vol60", "confl", "confl25",
          "ar_s", "ar_m", "ar_l", "ar_e2", "x2_ex", "x2_days",
          "ar_s_lo", "ar_m_lo", "ar_l_lo", "ar_e2_lo", "x2_ex_lo", "ar_pool"]
LEAVE_OUT = 272                                  # bars before an event excluded from the leave-out baseline


# ============================================================================ frames

@njit(cache=True)
def _ema_seeded(x, n):
    """EMA seeded with the SMA of the first n values (NaN before), alpha = 2 / (n + 1)."""
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    a = 2.0 / (n + 1); v = 0.0
    for i in range(n):
        v += x[i]
    v /= n; out[n - 1] = v
    for i in range(n, len(x)):
        v = a * x[i] + (1 - a) * v; out[i] = v
    return out


def make_frame(ohlc: pd.DataFrame, tr: pd.Series, kind: str, name: str, base_mask=None) -> dict:
    """Arrays for one asset. ohlc = chart prices (averages, touches); tr = total-return index.
    base_mask (optional, aligned to the cleaned bars) limits the leave-out baseline to those days
    (S&P member days for the member pool)."""
    d = ohlc[["open", "high", "low", "close"]].astype(float).copy()
    d["tr"] = tr.reindex(d.index).astype(float)
    d = d.dropna()
    d = d[(d[["open", "high", "low", "close", "tr"]] > 0).all(axis=1)]
    h, l, c = d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy()
    a = atr_fn(h, l, c, 14)
    lr = np.r_[np.nan, np.diff(np.log(c))]
    crypto = kind == "crypto"
    H = (7, 28, 84) if crypto else (5, 20, 60)
    f = {"name": name, "kind": kind, "idx": d.index, "o": d.open.to_numpy(), "h": h, "l": l, "c": c,
         "tr": d.tr.to_numpy(), "atr_prev": np.r_[np.nan, a[:-1]], "H": H,
         "cost": 0.003 if crypto else 0.0003,
         "wfreq": "W-SUN" if crypto else "W-FRI", "year": d.index.year.to_numpy()}
    s = pd.Series(lr, index=d.index)
    f["vol60"] = (s.rolling(60).std() * np.sqrt(365 if crypto else 252)).shift(1).to_numpy()
    f["dd252"] = (d.close / d.close.rolling(252, min_periods=60).max() - 1).shift(1).to_numpy()
    # drift: mean forward log TR return per calendar year, for each horizon, and per day (pre-registered
    # baseline); prefix sums for the leave-out baseline (post-registration, see AUDIT)
    ltr = np.log(f["tr"])
    f["drift"] = {}; f["fwd"] = {}; f["cs"] = {}; f["cn"] = {}
    for k in (1,) + H:
        fwd = np.r_[ltr[k:] - ltr[:-k], np.full(k, np.nan)]
        f["drift"][k] = pd.Series(fwd).groupby(f["year"]).mean().to_dict()
        fb = fwd if base_mask is None else np.where(base_mask, fwd, np.nan)
        ok = np.isfinite(fb)
        f["fwd"][k] = fwd
        f["cs"][k] = np.r_[0.0, np.cumsum(np.where(ok, fb, 0.0))]
        f["cn"][k] = np.r_[0, np.cumsum(ok)]
    return f


def restrict_baseline(f: dict, mask: np.ndarray) -> None:
    """Limit the leave-out baseline to the days in mask (e.g. S&P 500 member days)."""
    for k, fwd in f["fwd"].items():
        fb = np.where(mask, fwd, np.nan); ok = np.isfinite(fb)
        f["cs"][k] = np.r_[0.0, np.cumsum(np.where(ok, fb, 0.0))]
        f["cn"][k] = np.r_[0, np.cumsum(ok)]


def leave_out(f: dict, T: np.ndarray, k: int) -> np.ndarray:
    """Asset's mean k-bar forward log return excluding windows that start in [t - 272, t + k]
    (the stretch that selected the event and the event's own window)."""
    n = len(f["c"]); cs, cn = f["cs"][k], f["cn"][k]
    lo = np.clip(T - LEAVE_OUT, 0, n); hi = np.clip(T + k + 1, 0, n)
    s = cs[n] - (cs[hi] - cs[lo]); m = cn[n] - (cn[hi] - cn[lo])
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(m > 0, s / np.maximum(m, 1), np.nan)


def ma_line(f: dict, tf: str, kind: str, n: int) -> np.ndarray:
    """Average known at the open of each day: daily through t-1; weekly/monthly completed periods."""
    idx = f["idx"]; c = pd.Series(f["c"], index=idx)
    if tf == "D":
        m = c.rolling(n).mean() if kind == "SMA" else pd.Series(_ema_seeded(c.to_numpy(float), n), index=idx)
        return m.shift(1).to_numpy()
    per = idx.to_period(f["wfreq"] if tf == "W" else "M")
    pc = c.groupby(per).last()
    pm = pc.rolling(n).mean() if kind == "SMA" else pd.Series(_ema_seeded(pc.to_numpy(float), n), index=pc.index)
    prev = pm.shift(1)                            # the previous, completed period's average
    return prev.reindex(per).to_numpy()


# ============================================================================ events

@njit(cache=True)
def _events(o, h, l, c, tr, atrp, line, K, H3, cost, stop_k, dead):
    """Touch events of one line. Returns per-event arrays: t, fill, held, gap, run, x2 exit index,
    x2 log return, and E1 log returns at the three horizons (NaN beyond the data). For a series
    that ended before the data set did (delisted / dead), a horizon past its end exits at its last
    close, which is what a holder got."""
    n = len(c)
    run = np.zeros(n, np.int64)
    for i in range(n):
        if line[i] == line[i] and c[i] > line[i]:
            run[i] = (run[i - 1] + 1) if i > 0 else 1
    out_t = []; out_fill = []
    for t in range(1, n):
        L = line[t]
        if not (L == L) or not (atrp[t] == atrp[t]) or L <= 0:
            continue
        if run[t - 1] >= K and l[t] <= L:
            out_t.append(t); out_fill.append(min(o[t], L))
    m = len(out_t)
    T = np.empty(m, np.int64); FILL = np.empty(m); HELD = np.empty(m, np.bool_); GAP = np.empty(m, np.bool_)
    RUN = np.empty(m, np.int64); XI = np.empty(m, np.int64); XR = np.empty(m)
    R = np.full((m, 3), np.nan)
    lc = np.log(1 - cost)
    for j in range(m):
        t = out_t[j]; fl = out_fill[j]
        T[j] = t; FILL[j] = fl; HELD[j] = c[t] >= line[t]; GAP[j] = o[t] <= line[t]; RUN[j] = run[t - 1]
        ftr = fl * tr[t] / c[t]                           # fill on the total-return scale
        for k in range(3):
            e = t + H3[k]
            if e >= n and dead:
                e = n - 1
            if e < n:
                R[j, k] = np.log(tr[e] / ftr) + 2 * lc
        # X2: first close below line - stop_k * ATR, else time exit at H (middle horizon)
        e = t + H3[1]
        if e >= n and dead:
            e = n - 1
        xi = -1
        if e < n:
            xi = e
            for d in range(t, e + 1):
                if line[d] == line[d] and c[d] < line[d] - stop_k * atrp[d]:
                    xi = d; break
        XI[j] = xi
        XR[j] = (np.log(tr[xi] / ftr) + 2 * lc) if xi >= 0 else np.nan
    return T, FILL, HELD, GAP, RUN, XI, XR, R


def asset_events(f: dict, member_mask: np.ndarray | None = None, mas=None, pool: np.ndarray | None = None,
                 dead: bool = False) -> pd.DataFrame:
    """All touch events of one asset, every average and every line (real + placebo).
    pool: equal-weight pool mean of the mid-horizon forward log return starting at each close,
    aligned to the asset's bars (for the close-synchronous pool-adjusted AR)."""
    o, h, l, c, tr, atrp = f["o"], f["h"], f["l"], f["c"], f["tr"], f["atr_prev"]
    H = np.array(f["H"], np.int64); n = len(c)
    lines = {}
    for mi, (tf, kind, nn) in enumerate(MAS):
        if mas is not None and mi not in mas:
            continue
        lines[mi] = ma_line(f, tf, kind, nn)
    # confluence: how many of the computed real averages lie within 1 (0.25) ATR of each average
    real = np.vstack([lines[m] for m in sorted(lines)]) if lines else np.zeros((0, n))
    cols = {k: [] for k in FIELDS[1:]}
    year = f["year"]; days = (f["idx"].values.astype("datetime64[D]").astype(np.int64))
    lc2 = 2 * np.log(1 - f["cost"]); Hm = f["H"][1]
    for mi, base in lines.items():
        with np.errstate(invalid="ignore", divide="ignore"):
            slope = np.r_[np.full(20, np.nan), base[20:] / base[:-20] - 1]
            confl = (np.abs(real - base) <= atrp).sum(axis=0)
            confl25 = (np.abs(real - base) <= 0.25 * atrp).sum(axis=0)
        for li, k in enumerate(OFFSETS):
            line = base + k * atrp
            T, FILL, HELD, GAP, RUN, XI, XR, R = _events(o, h, l, c, tr, atrp, line, K_APPROACH, H, f["cost"], 1.0, dead)
            if member_mask is not None and len(T):
                keep = member_mask[T]
                T, FILL, HELD, GAP, RUN, XI, XR, R = T[keep], FILL[keep], HELD[keep], GAP[keep], RUN[keep], XI[keep], XR[keep], R[keep]
            if len(T) == 0:
                continue
            yr = year[T]
            dr = {kk: np.array([f["drift"][kk].get(y, np.nan) for y in yr]) for kk in (1,) + f["H"]}
            lo = {kk: leave_out(f, T, kk) for kk in (1,) + f["H"]}
            # E2: confirmed bounce, entry at the close (crypto) or the next open (stocks)
            e2 = np.full(len(T), np.nan); e2_lo = np.full(len(T), np.nan)
            ex = T + Hm
            if dead:
                ex = np.minimum(ex, n - 1)
            ok = HELD & (ex < n) & (T + 1 < n) & (ex > T)
            if ok.any():
                tt = T[ok]; ee = ex[ok]
                ent = tr[tt] if f["kind"] == "crypto" else o[tt + 1] * tr[tt + 1] / c[tt + 1]
                raw = np.log(tr[ee] / ent) + lc2
                e2[ok] = raw - dr[Hm][ok]; e2_lo[ok] = raw - lo[Hm][ok]
            # close-synchronous pool-adjusted AR: asset close t -> close t+Hm minus the pool's mean
            ap = np.full(len(T), np.nan)
            if pool is not None:
                okp = T + Hm < n
                ap[okp] = np.log(tr[T[okp] + Hm] / tr[T[okp]]) - pool[T[okp]]
            held_days = np.where(XI >= 0, XI - T, np.nan)
            cols["ma"].append(np.full(len(T), mi, np.int16)); cols["line"].append(np.full(len(T), li, np.int8))
            cols["day"].append(days[T].astype(np.int32)); cols["held"].append(HELD); cols["gap"].append(GAP)
            cols["slope"].append(slope[T].astype(np.float32)); cols["run"].append(RUN.astype(np.int32))
            cols["reject"].append(((c[T] - line[T]) / atrp[T]).astype(np.float32))
            cols["dd252"].append(f["dd252"][T].astype(np.float32)); cols["vol60"].append(f["vol60"][T].astype(np.float32))
            cols["confl"].append(confl[T].astype(np.int16)); cols["confl25"].append(confl25[T].astype(np.int16))
            for i, key in enumerate(("ar_s", "ar_m", "ar_l")):
                cols[key].append((R[:, i] - dr[f["H"][i]]).astype(np.float32))
                cols[key + "_lo"].append((R[:, i] - lo[f["H"][i]]).astype(np.float32))
            cols["ar_e2"].append(e2.astype(np.float32)); cols["ar_e2_lo"].append(e2_lo.astype(np.float32))
            cols["x2_ex"].append((XR - held_days * dr[1]).astype(np.float32))
            cols["x2_ex_lo"].append((XR - held_days * lo[1]).astype(np.float32))
            cols["x2_days"].append(held_days.astype(np.float32)); cols["ar_pool"].append(ap.astype(np.float32))
    if not cols["ma"]:
        return pd.DataFrame(columns=FIELDS)
    ev = pd.DataFrame({k: np.concatenate(v) for k, v in cols.items()})
    ev.insert(0, "asset", f["name"])
    ev["rising"] = ev.slope > 0
    ev["falling"] = ev.slope < 0
    return ev


def pool_forward(frames_masks, H: int) -> pd.Series:
    """Equal-weight mean, by date, of each member's H-bar forward log return from that close
    (only days where the asset is in the pool)."""
    parts = []
    for f, mask in frames_masks:
        fwd = f["fwd"][H]
        ok = np.isfinite(fwd) & (mask if mask is not None else True)
        parts.append(pd.Series(fwd[ok], index=f["idx"][ok]))
    return pd.concat(parts).groupby(level=0).mean().sort_index()


# ============================================================================ statistics

def month_of(day: np.ndarray, block: int = 1) -> np.ndarray:
    d = day.astype("datetime64[D]")
    return (d.astype("datetime64[M]").astype(np.int64)).astype(np.int64) // block


def boot_mean(df: pd.DataFrame, col: str, B=2000, seed=0, block=1) -> tuple[float, float, int]:
    """Mean of col with a month-block bootstrap (block = months per block): returns
    (mean, one-sided p of mean <= 0, n)."""
    x = df[[col]].assign(m=month_of(df.day.to_numpy(), block)).dropna()
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    g = x.groupby("m")[col].agg(["sum", "count"])
    s, k = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(g), size=(B, len(g)))
    bm = s[pick].sum(1) / k[pick].sum(1)
    mean = s.sum() / k.sum()
    return float(mean), float((bm <= 0).mean()), int(k.sum())


def boot_diff(a: pd.DataFrame, b: pd.DataFrame, col: str, B=2000, seed=0, block=1) -> tuple[float, float]:
    """mean(a) - mean(b) with months resampled jointly; one-sided p of diff <= 0."""
    xa = a[[col]].assign(m=month_of(a.day.to_numpy(), block)).dropna()
    xb = b[[col]].assign(m=month_of(b.day.to_numpy(), block)).dropna()
    if len(xa) < 5 or len(xb) < 5:
        return np.nan, np.nan
    ga = xa.groupby("m")[col].agg(["sum", "count"]); gb = xb.groupby("m")[col].agg(["sum", "count"])
    months = np.union1d(ga.index, gb.index)
    ga = ga.reindex(months, fill_value=0); gb = gb.reindex(months, fill_value=0)
    sa, ka, sb, kb = (ga["sum"].to_numpy(float), ga["count"].to_numpy(float), gb["sum"].to_numpy(float), gb["count"].to_numpy(float))
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(months), size=(B, len(months)))
    with np.errstate(invalid="ignore", divide="ignore"):
        bd = sa[pick].sum(1) / ka[pick].sum(1) - sb[pick].sum(1) / kb[pick].sum(1)
    d = sa.sum() / ka.sum() - sb.sum() / kb.sum()
    okb = np.isfinite(bd)
    return float(d), float((bd[okb] <= 0).mean()) if okb.any() else np.nan


def bh_fdr(p: np.ndarray, q=0.10) -> np.ndarray:
    p = np.asarray(p, float); m = np.isfinite(p).sum(); out = np.zeros(len(p), bool)
    if m == 0:
        return out
    order = np.argsort(np.where(np.isfinite(p), p, np.inf)); ranked = p[order]
    thresh = q * np.arange(1, len(p) + 1) / m
    ok = np.where(np.isfinite(ranked) & (ranked <= thresh))[0]
    if len(ok):
        out[order[:ok.max() + 1]] = True
    return out


def halves(ev: pd.DataFrame, cut: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    c = np.datetime64(cut, "D").astype(np.int64)
    return ev[ev.day < c], ev[ev.day >= c]


def hypotheses(ev: pd.DataFrame, cut: str, label: str, say) -> dict:
    """B1-B5 (or C1-C5) on one pool's event table."""
    out = {}
    real = ev[(ev.ma == PRIMARY) & (ev.line == 0)]
    plac = ev[(ev.ma == PRIMARY) & (ev.line > 0)]
    h1, h2 = halves(real, cut)
    m, p, n = boot_mean(real, "ar_m")
    out["1"] = bool(m > 0 and p < 0.05 and h1.ar_m.mean() > 0 and h2.ar_m.mean() > 0)
    say(f"{label}1 bounce: mean AR {m * 100:+.2f}% (p {p:.3f}, n {n}); halves {h1.ar_m.mean() * 100:+.2f}% / "
        f"{h2.ar_m.mean() * 100:+.2f}% -> {'PASS' if out['1'] else 'FAIL'}")
    d, p2 = boot_diff(real, plac, "ar_m")
    p1h, p2h = halves(plac, cut)
    dh = [real_h.ar_m.mean() - plac_h.ar_m.mean() for real_h, plac_h in ((h1, p1h), (h2, p2h))]
    out["2"] = bool(d > 0 and p2 < 0.05 and dh[0] > 0 and dh[1] > 0)
    say(f"{label}2 key level: real - placebo {d * 100:+.2f}% (p {p2:.3f}); halves {dh[0] * 100:+.2f}% / {dh[1] * 100:+.2f}%"
        f" -> {'PASS' if out['2'] else 'FAIL'}")
    m3, p3, n3 = boot_mean(real, "x2_ex")
    d3, p3b = boot_diff(real, plac, "x2_ex")
    out["3"] = bool(m3 > 0 and p3 < 0.05 and h1.x2_ex.mean() > 0 and h2.x2_ex.mean() > 0 and d3 > 0 and p3b < 0.05)
    say(f"{label}3 tradable (X2): mean excess per trade {m3 * 100:+.2f}% (p {p3:.3f}, n {n3}); halves "
        f"{h1.x2_ex.mean() * 100:+.2f}% / {h2.x2_ex.mean() * 100:+.2f}%; vs placebo {d3 * 100:+.2f}% (p {p3b:.3f})"
        f" -> {'PASS' if out['3'] else 'FAIL'}")
    d4, p4 = boot_diff(real[real.rising], real[real.falling], "ar_m")
    out["4"] = bool(d4 > 0 and p4 < 0.05)
    say(f"{label}4 rising vs falling: {real[real.rising].ar_m.mean() * 100:+.2f}% vs {real[real.falling].ar_m.mean() * 100:+.2f}%"
        f" (diff {d4 * 100:+.2f}%, p {p4:.3f}) -> {'PASS' if out['4'] else 'FAIL'}")
    grid = []
    for mi, name in enumerate(MA_NAME):
        r_ = ev[(ev.ma == mi) & (ev.line == 0)]; p_ = ev[(ev.ma == mi) & (ev.line > 0)]
        if len(r_) < 30:
            grid.append({"ma": name, "n": len(r_)}); continue
        dd, pp = boot_diff(r_, p_, "ar_m", B=1000, seed=mi)
        mm, pm, nn = boot_mean(r_, "ar_m", B=1000, seed=mi)
        grid.append({"ma": name, "n": nn, "mean_AR_%": mm * 100, "p_bounce": pm, "real_minus_placebo_%": dd * 100, "p_key": pp,
                     "hit_%": float((r_.ar_m.dropna() > 0).mean() * 100), "held_%": float(r_.held.mean() * 100)})
    g = pd.DataFrame(grid)
    g["fdr_key"] = bh_fdr(g["p_key"].to_numpy() if "p_key" in g else np.full(len(g), np.nan))
    npass = int(g.fdr_key.sum())
    out["5"] = bool(out["2"] and npass >= len(MAS) / 3)
    say(f"{label}5 grid: {npass}/{len(MAS)} averages pass the key-level test at 10% FDR -> "
        f"{'PASS' if out['5'] else 'FAIL'}")
    # post-registration robustness (AUDIT): unbiased baselines, first touches, 3-month blocks
    for mi, name in enumerate(MA_NAME):
        r_ = ev[(ev.ma == mi) & (ev.line == 0)]; p_ = ev[(ev.ma == mi) & (ev.line > 0)]
        if len(r_) < 30:
            continue
        for col in ("ar_m_lo", "ar_pool"):
            if r_[col].notna().sum() < 30:
                continue
            dd, pp = boot_diff(r_, p_, col, B=1000, seed=mi)
            mm, pm, _ = boot_mean(r_, col, B=1000, seed=mi)
            g.loc[g.ma == name, f"mean_{col}_%"] = mm * 100
            g.loc[g.ma == name, f"key_{col}_%"] = dd * 100
            g.loc[g.ma == name, f"p_key_{col}"] = pp
    for col in ("p_key_ar_m_lo", "p_key_ar_pool"):
        if col in g:
            g[col.replace("p_key", "fdr_key")] = bh_fdr(g[col].to_numpy())
    out["grid"] = g
    say("  robustness (post-registration; verdicts above use the pre-registered AR):")
    first = first_touch(ev)
    real_f = first[(first.ma == PRIMARY) & (first.line == 0)]; plac_f = first[(first.ma == PRIMARY) & (first.line > 0)]
    for desc, col in (("same-year drift (pre-registered)", "ar_m"), ("own drift, event period left out", "ar_m_lo"),
                      ("minus the pool's same-window mean", "ar_pool")):
        if real[col].notna().sum() < 30:
            continue
        st = boot_stats(real, col); st3 = boot_stats(real, col, block=3)
        d_, pd_ = boot_diff(real, plac, col); d3_, pd3_ = boot_diff(real, plac, col, block=3)
        mf, pf, nf = boot_mean(real_f, col); dfk, pdf = boot_diff(real_f, plac_f, col)
        r4, p4_ = boot_diff(real[real.rising], real[real.falling], col)
        say(f"  {desc:36s} bounce {st['mean'] * 100:+.2f}% [95% CI {st['lo'] * 100:+.2f}, {st['hi'] * 100:+.2f}] p {st['p']:.2f}"
            f" (3m blocks p {st3['p']:.2f}); real-placebo {d_ * 100:+.2f}% p {pd_:.2f} (3m {d3_ * 100:+.2f}% p {pd3_:.2f});"
            f" first touches {mf * 100:+.2f}% p {pf:.2f} / real-placebo {dfk * 100:+.2f}% p {pdf:.2f} (n {nf});"
            f" rising-falling {r4 * 100:+.2f}% p {p4_:.2f}")
    st = boot_stats(real, "ar_m")
    say(f"  clustering: {st['n']} events in {st['months']} months; bootstrap SE {st['se'] * 100:.2f}% vs iid "
        f"{st['se_iid'] * 100:.2f}% -> effective n ~{st['n_eff']:.0f}")
    m3l, p3l, _ = boot_mean(real, "x2_ex_lo"); d3l, p3lb = boot_diff(real, plac, "x2_ex_lo")
    say(f"  tradable X2 with the leave-out drift: {m3l * 100:+.2f}% per trade (p {p3l:.2f}); vs placebo {d3l * 100:+.2f}% (p {p3lb:.2f})")
    return out


def boot_stats(df: pd.DataFrame, col: str, B=2000, seed=0, block=1) -> dict:
    """Mean, one-sided p, 95% CI, bootstrap SE, iid SE, number of months and effective n."""
    x = df[[col]].assign(m=month_of(df.day.to_numpy(), block)).dropna()
    g = x.groupby("m")[col].agg(["sum", "count"])
    s_, k_ = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(g), size=(B, len(g)))
    bm = s_[pick].sum(1) / k_[pick].sum(1)
    mean = s_.sum() / k_.sum(); se = bm.std(); se_iid = x[col].std() / np.sqrt(len(x))
    return {"mean": mean, "p": float((bm <= 0).mean()), "lo": np.quantile(bm, .025), "hi": np.quantile(bm, .975),
            "se": se, "se_iid": se_iid, "n": len(x), "months": len(g), "n_eff": len(x) * (se_iid / se) ** 2 if se > 0 else np.nan}


def first_touch(ev: pd.DataFrame, gap_days: int = 28) -> pd.DataFrame:
    """Keep an event only if the same asset, average and line had no touch in the previous
    gap_days calendar days (repeat touches of one pullback count once)."""
    e = ev.sort_values(["asset", "ma", "line", "day"])
    prev = e.groupby(["asset", "ma", "line"]).day.shift(1)
    return e[(prev.isna()) | (e.day - prev >= gap_days)]


# ============================================================================ loaders

def load_all() -> dict:
    from analysis_2026 import regime_switch as RS
    frames = {}
    spx = RS.load_spx_long()
    frames["SPX_LONG"] = make_frame(spx[["open", "high", "low", "close"]], spx.tr, "us", "SPX_LONG")
    for s in RS.ETFS + RS.YAHOO_STOCKS:
        d = RS._yahoo_raw(s)
        frames[s] = make_frame(d, d.adj_close, "us", s)
    crypto = {s: make_frame(d, d.close, "crypto", s) for s, d in load_crypto_raw().items()}
    return frames, crypto


def load_crypto_raw() -> dict:
    """Binance daily OHLC; MATIC continues as POL after the 2024 migration."""
    from analysis_2026.altcoins import load_crypto
    cr = load_crypto(DATA / "crypto_binance_regime")
    if "MATIC" in cr and "POL" in cr:
        m, p = cr.pop("MATIC"), cr.pop("POL")
        cr["MATIC"] = pd.concat([m, p[p.index > m.index[-1]]])
    return cr


def load_members():
    from screener.data import from_csv_folder
    members = pd.read_csv(DATA / "universe_pit_all" / "members.csv", parse_dates=["start", "end"])
    members["symbol"] = members.symbol.str.upper()
    members["end"] = members.end.fillna(pd.Timestamp("2100-01-01"))
    raw = from_csv_folder(DATA / "universe_pit_all")
    raw.pop("MEMBERS", None)
    return {s: d for s, d in raw.items() if s != "STI"}, members


def member_mask(idx: pd.DatetimeIndex, spells: pd.DataFrame) -> np.ndarray:
    m = np.zeros(len(idx), bool)
    for _, r in spells.iterrows():
        m |= (idx >= r.start) & (idx <= r.end)
    return m


# ============================================================================ single-asset backtest (exploratory)

def backtest(f: dict, mi: int, li: int = 0) -> dict:
    """Non-overlapping X2 trades on one asset, full equity per trade, cash earns T-bills when
    flat. Pre-tax CAGR and max drawdown vs buy & hold over the same span."""
    from analysis_2026 import regime_switch as RS
    base = ma_line(f, *MAS[mi]); line = base + OFFSETS[li] * f["atr_prev"]
    H = np.array(f["H"], np.int64)
    T, FILL, HELD, GAP, RUN, XI, XR, R = _events(f["o"], f["h"], f["l"], f["c"], f["tr"], f["atr_prev"], line,
                                                 K_APPROACH, H, f["cost"], 1.0, False)
    n = len(f["c"]); tr = f["tr"]
    rf = RS.rf_per_bar(f["idx"])
    eq = np.ones(n); busy_until = -1; cur = 1.0; i0 = int(np.argmax(np.isfinite(base))) + K_APPROACH
    inpos = np.zeros(n, bool)
    trades = 0
    t = i0
    events = {int(T[k]): k for k in range(len(T)) if XI[k] >= 0}
    while t < n:
        k = events.get(t)
        if k is not None and t > busy_until:
            fl = FILL[k] * tr[t] / f["c"][t]
            cur *= (1 - f["cost"]) * tr[t] / fl
            eq[t] = cur
            x = int(XI[k])
            for d in range(t + 1, x + 1):
                cur *= tr[d] / tr[d - 1]; eq[d] = cur; inpos[d] = True
            cur *= (1 - f["cost"]); eq[x] = cur
            busy_until = x; trades += 1; t = x + 1
            continue
        if t > i0:
            cur *= 1 + rf[t]
        eq[t] = cur; t += 1
    e = eq[i0:]; yrs = (f["idx"][-1] - f["idx"][i0]).days / 365.25
    b = tr[i0:] / tr[i0]
    dd = lambda x: float((x / np.maximum.accumulate(x) - 1).min() * 100)  # noqa: E731
    return {"asset": f["name"], "ma": MA_NAME[mi], "line": OFFSETS[li], "start": f["idx"][i0].date(), "years": yrs,
            "trades": trades, "trades_yr": trades / yrs, "exposure_%": inpos[i0:].mean() * 100,
            "cagr": (e[-1] ** (1 / yrs) - 1) * 100, "maxdd": dd(e), "bh_cagr": (b[-1] ** (1 / yrs) - 1) * 100, "bh_maxdd": dd(b)}


# ============================================================================ main

def summarize(ev: pd.DataFrame, by=("ma", "line")) -> pd.DataFrame:
    """Means by group. *_lo = leave-out own-drift baseline, pool = minus the pool's same-window mean
    (both post-registration, see AUDIT); the others use the pre-registered same-year drift."""
    g = ev.groupby(list(by))
    return pd.DataFrame({"n": g.size(), "AR_s_%": g.ar_s.mean() * 100, "AR_m_%": g.ar_m.mean() * 100,
                         "AR_l_%": g.ar_l.mean() * 100, "hit_m_%": g.ar_m.apply(lambda x: (x.dropna() > 0).mean() * 100),
                         "AR_m_lo_%": g.ar_m_lo.mean() * 100, "AR_m_pool_%": g.ar_pool.mean() * 100,
                         "held_%": g.held.mean() * 100, "E2_m_%": g.ar_e2.mean() * 100, "E2_m_lo_%": g.ar_e2_lo.mean() * 100,
                         "X2_ex_%": g.x2_ex.mean() * 100, "X2_ex_lo_%": g.x2_ex_lo.mean() * 100,
                         "X2_days": g.x2_days.mean()}).reset_index()


def analog(df: pd.DataFrame) -> pd.DataFrame:
    """HOOD-like setups (pre-registered): 60-day vol >= 50%, >= 20% below the 52-week high, a falling
    200-day and >= 20 closes above the line before the touch."""
    return df[(df.vol60 >= 0.5) & (df.dd252 <= -0.2) & df.falling & (df.run >= 20)]


# ============================================================================ chart lines (exploratory, AUDIT)

def chart_factor() -> dict:
    """Dividend-only back-adjustment factor q per pool ticker from data/raw_pit (split jumps of the
    raw-close sources removed). The pool's OHLC / q = split-adjusted chart prices, the lines traders see."""
    p = pd.read_parquet(DATA / "raw_pit" / "prices.parquet", columns=["date", "ticker", "close", "adj_close",
                                                                      "dividends", "stock_splits"])
    out = {}
    for t, g in p.sort_values(["ticker", "date"]).groupby("ticker", sort=False):
        g = g.drop_duplicates("date", keep="last")
        g = g[(g.close > 0) & (g.adj_close > 0)]
        if len(g) < 2:
            continue
        k = (g.adj_close / g.close).to_numpy()
        ld = np.log(np.r_[1.0, k[1:] / k[:-1]])
        sp = g.stock_splits.fillna(0).to_numpy()
        issplit = (sp > 0) & (np.abs(sp - 1) > 1e-9)
        rm = issplit & (np.abs(ld - np.log(np.where(issplit, sp, 1))) < 0.1)
        ld[rm] -= np.log(sp[rm])
        logq = -(np.cumsum(ld[::-1])[::-1] - ld)          # minus the sum of later steps; q = 1 on the last day
        out[t.upper()] = pd.Series(np.exp(logq), index=pd.DatetimeIndex(g.date))
    return out


# ============================================================================ null simulation (AUDIT)

def synth_bars(d: pd.DataFrame, rng) -> pd.DataFrame:
    """iid bootstrap of an asset's own daily bars on the same dates: each day draws one historical
    (overnight gap, high/open, low/open, close/open) tuple. Same volatility and drift, no predictability."""
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    g = o[1:] / c[:-1]; hh = h[1:] / o[1:]; ll = l[1:] / o[1:]; cc = c[1:] / o[1:]
    k = rng.integers(0, len(g), len(g))
    C = np.empty(len(c)); O = np.empty(len(c)); H = np.empty(len(c)); L = np.empty(len(c))
    C[0] = O[0] = H[0] = L[0] = c[0]
    C[1:] = c[0] * np.exp(np.cumsum(np.log(g[k] * cc[k])))
    O[1:] = C[:-1] * g[k]; H[1:] = O[1:] * hh[k]; L[1:] = O[1:] * ll[k]
    return pd.DataFrame({"open": O, "high": np.maximum.reduce([H, O, C]), "low": np.minimum.reduce([L, O, C]),
                         "close": C}, index=d.index)


NULL_COLS = ("ar_m", "ar_m_lo", "ar_pool", "ar_e2", "ar_e2_lo", "x2_ex", "x2_ex_lo")


def null_stats(ev: pd.DataFrame, with_analog: bool) -> dict:
    """The primary-average statistics whose no-predictability level the null run measures (unweighted means, %)."""
    e = ev[ev.ma == PRIMARY]; real = e[e.line == 0]; plac = e[e.line > 0]
    out = {}
    for col in NULL_COLS:
        for li, k in enumerate(OFFSETS):
            out[(col, "real line" if li == 0 else f"line {k:+.0f} ATR")] = e[e.line == li][col].mean() * 100
        out[(col, "real - placebo")] = (real[col].mean() - plac[col].mean()) * 100
        out[(col, "rising - falling (B4)")] = (real[real.rising][col].mean() - real[real.falling][col].mean()) * 100
        if with_analog:
            out[(col, "HOOD-like analog")] = analog(real)[col].mean() * 100
            out[(col, "HOOD-like analog, placebo lines")] = analog(plac)[col].mean() * 100
    return out


def null_run(R: int) -> None:
    """R replications of every member stock and crypto series with iid-resampled bars (same dates,
    member masks, pools and code, primary average only). Prints the mean of each statistic under
    no predictability next to the actual value: what each baseline reports when there is no edge."""
    OUT.mkdir(exist_ok=True)
    stocks, members = load_members()
    spells = {s: g for s, g in members.groupby("symbol")}
    s_end = max(d.index[-1] for d in stocks.values())
    st = {}
    for s, d in stocks.items():
        if s not in spells or len(d) < 60:
            continue
        d = d[(d[["open", "high", "low", "close"]] > 0).all(axis=1)]
        mm = member_mask(d.index, spells[s])
        if mm.any() and len(d) >= 60:
            st[s] = (d, mm, d.index[-1] < s_end - pd.Timedelta(days=7))
    cr = load_crypto_raw()
    c_end = max(d.index[-1] for d in cr.values())
    rows = []
    for rep in range(R):
        rng = np.random.default_rng(1000 + rep)
        fr = {}
        for s, (d, mm, dead) in st.items():
            dd = synth_bars(d, rng); f = make_frame(dd, dd.close, "us", s); restrict_baseline(f, mm)
            fr[s] = (f, mm, dead)
        pool = pool_forward([(f, mm) for f, mm, _ in fr.values()], 20)
        ev = pd.concat([asset_events(f, mm, mas={PRIMARY}, pool=pool.reindex(f["idx"]).to_numpy(), dead=dead)
                        for f, mm, dead in fr.values()], ignore_index=True)
        for key, v in null_stats(ev, True).items():
            rows.append({"pool": "S&P members", "rep": rep, "stat": key[0], "row": key[1], "value": v})
        frc = {}
        for s, d in cr.items():
            dd = synth_bars(d, rng); frc[s] = make_frame(dd, dd.close, "crypto", s)
        poolc = pool_forward([(f, None) for f in frc.values()], 28)
        evc = pd.concat([asset_events(f, mas={PRIMARY}, pool=poolc.reindex(f["idx"]).to_numpy(),
                                      dead=cr[s].index[-1] < c_end - pd.Timedelta(days=7)) for s, f in frc.items()],
                        ignore_index=True)
        for key, v in null_stats(evc, False).items():
            rows.append({"pool": "crypto", "rep": rep, "stat": key[0], "row": key[1], "value": v})
        print(f"null rep {rep + 1}/{R}: stocks {len(ev[ev.line == 0]):,} real-line events, crypto {len(evc[evc.line == 0]):,}",
              flush=True)
    nr = pd.DataFrame(rows); nr.to_csv(OUT / "null_by_rep.csv", index=False)
    g = nr.groupby(["pool", "stat", "row"], sort=False).value
    tab = pd.DataFrame({"null_mean_%": g.mean(), "null_se_%": g.std() / np.sqrt(R)})
    act = {}
    for pool_name, fn, wa in (("S&P members", "events_stocks.parquet", True), ("crypto", "events_crypto.parquet", False)):
        if (OUT / fn).exists():
            for key, v in null_stats(pd.read_parquet(OUT / fn), wa).items():
                act[(pool_name,) + key] = v
    tab["actual_%"] = [act.get(i, np.nan) for i in tab.index]
    tab = tab.reset_index()
    tab.to_csv(OUT / "null_summary.csv", index=False)
    with open(OUT / "null_summary.txt", "w") as fh:
        fh.write(f"Null simulation, {R} replications (iid-resampled bars, same dates, members, pools and code; primary "
                 f"average D-SMA200, E1 / E2 / X2 as in the study). Means in %; costs are included (stocks 0.06%, crypto "
                 f"0.60% round trip), so an unbiased AR column sits near minus the cost plus a small fill effect.\n"
                 f"ar_m = pre-registered same-year drift baseline; ar_m_lo = own drift with the event period left out; "
                 f"ar_pool = close t to t+H minus the pool's mean over the same window (no costs, no fill).\n\n")
        fh.write(tab.to_string(index=False, float_format=lambda x: f"{x:,.3f}") + "\n")
    print((OUT / "null_summary.txt").read_text())


def chart_line_check(stocks, spells, pool_s, s_end, ev_s, say) -> None:
    """AUDIT: the member pool's OHLC is dividend-back-adjusted, so its averages sit below the chart
    averages (median ~0.2 ATR). Rerun the daily averages on chart prices (returns stay total return)."""
    qf = chart_factor()
    dmas = {i for i, (tf, _, _) in enumerate(MAS) if tf == "D"}
    evq = []
    for s, d in stocks.items():
        if s not in spells or len(d) < 60 or s.upper() not in qf:
            continue
        q = qf[s.upper()].reindex(d.index)
        f = make_frame(d[["open", "high", "low", "close"]].div(q, axis=0), d.close, "us", s)
        mm = member_mask(f["idx"], spells[s])
        if not mm.any():
            continue
        restrict_baseline(f, mm)
        evq.append(asset_events(f, mm, mas=dmas, pool=pool_s.reindex(f["idx"]).to_numpy(),
                                dead=f["idx"][-1] < s_end - pd.Timedelta(days=7)))
    evq = pd.concat(evq, ignore_index=True)
    say(f"\nChart lines (exploratory, AUDIT): daily averages on split-adjusted, not dividend-adjusted, prices "
        f"({evq.asset.nunique()} stocks; returns still total return). Primary average:")
    rows = []
    for lab, ev in (("total-return lines (as registered)", ev_s), ("chart lines", evq)):
        real = ev[(ev.ma == PRIMARY) & (ev.line == 0)]; plac = ev[(ev.ma == PRIMARY) & (ev.line > 0)]
        for col in ("ar_m", "ar_m_lo", "ar_pool"):
            m, p, n = boot_mean(real, col); d_, pd_ = boot_diff(real, plac, col)
            rows.append({"lines": lab, "baseline": col, "n": n, "bounce_%": m * 100, "p_bounce": p,
                         "real_minus_placebo_%": d_ * 100, "p_key": pd_})
    t = pd.DataFrame(rows)
    say(t.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    a = ev_s[(ev_s.ma == PRIMARY) & (ev_s.line == 0)][["asset", "day"]]
    b = evq[(evq.ma == PRIMARY) & (evq.line == 0)][["asset", "day"]]
    say(f"  {len(b.merge(a)) / len(b) * 100:.0f}% of the chart-line 200-day touches are also total-return-line touches")
    g = []
    for mi in sorted(dmas):
        r_ = evq[(evq.ma == mi) & (evq.line == 0)]; p_ = evq[(evq.ma == mi) & (evq.line > 0)]
        dd, pp = boot_diff(r_, p_, "ar_m", B=1000, seed=mi); dl, pl_ = boot_diff(r_, p_, "ar_m_lo", B=1000, seed=mi)
        g.append({"ma": MA_NAME[mi], "n": int(r_.ar_m.notna().sum()), "key_%": dd * 100, "p_key": pp,
                  "key_lo_%": dl * 100, "p_key_lo": pl_})
    g = pd.DataFrame(g)
    g["fdr_key"] = bh_fdr(g.p_key.to_numpy()); g["fdr_key_lo"] = bh_fdr(g.p_key_lo.to_numpy())
    say("  daily averages on chart lines, key-level test (real minus placebo, 20 days):")
    say(g.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    t.to_csv(OUT / "chart_lines.csv", index=False); g.to_csv(OUT / "chart_lines_grid.csv", index=False)


def main():
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 40)
    OUT.mkdir(exist_ok=True)
    log = open(OUT / "summary.txt", "w")

    def say(*a):
        s = " ".join(str(x) for x in a); print(s); log.write(s + "\n"); log.flush()
    fmt = lambda x: f"{x:,.2f}"  # noqa: E731

    frames, crypto = load_all()
    stocks, members = load_members()
    spells = {s: g for s, g in members.groupby("symbol")}

    # ---------------------------------------------------------------- S&P 500 member pool
    # pass 1: equal-weight member pool's forward log return from each close (for ar_pool)
    s_end = max(d.index[-1] for d in stocks.values())
    pool_parts = []
    for s, d in stocks.items():
        if s not in spells or len(d) < 60:
            continue
        idx = d.index; ltr = np.log(d.close.to_numpy(float)); k = 20
        fwd = np.r_[ltr[k:] - ltr[:-k], np.full(k, np.nan)]
        mm = member_mask(idx, spells[s]) & np.isfinite(fwd)
        pool_parts.append(pd.Series(fwd[mm], index=idx[mm]))
    pool_s = pd.concat(pool_parts).groupby(level=0).mean().sort_index()
    evs = []
    for s, d in stocks.items():
        if s not in spells or len(d) < 60:
            continue
        f = make_frame(d, d.close, "us", s)
        mm = member_mask(f["idx"], spells[s])
        if not mm.any():
            continue
        restrict_baseline(f, mm)
        dead = f["idx"][-1] < s_end - pd.Timedelta(days=7)
        evs.append(asset_events(f, mm, pool=pool_s.reindex(f["idx"]).to_numpy(), dead=dead))
    ev_s = pd.concat(evs, ignore_index=True)
    ev_s.to_parquet(OUT / "events_stocks.parquet")
    c_end = max(f["idx"][-1] for f in crypto.values())
    pool_c = pool_forward([(f, None) for f in crypto.values()], 28)
    ev_c = pd.concat([asset_events(f, pool=pool_c.reindex(f["idx"]).to_numpy(), dead=f["idx"][-1] < c_end - pd.Timedelta(days=7))
                      for f in crypto.values()], ignore_index=True)
    ev_c.to_parquet(OUT / "events_crypto.parquet")
    ev_n = pd.concat([asset_events(f, pool=pool_s.reindex(f["idx"]).to_numpy()) for f in frames.values()], ignore_index=True)
    ev_n.to_parquet(OUT / "events_single.parquet")
    named_crypto = pd.concat([asset_events(crypto[s], pool=pool_c.reindex(crypto[s]["idx"]).to_numpy())
                              for s in ("BTC", "ETH", "SOL", "BNB", "ZEC") if s in crypto], ignore_index=True)

    say("=" * 100); say("PRE-REGISTERED HYPOTHESES (primary: daily 200-day SMA, limit at the level, 20 trading days / 28 crypto days)")
    say("=" * 100)
    say(f"S&P 500 member pool: {ev_s.asset.nunique()} stocks, {len(ev_s):,} events (all averages and lines)")
    hs = hypotheses(ev_s, "2012-01-01", "B", say)
    hs["grid"].to_csv(OUT / "grid_stocks.csv", index=False)
    say(f"\nCrypto pool: {ev_c.asset.nunique()} series, {len(ev_c):,} events")
    hc = hypotheses(ev_c, "2023-01-01", "C", say)
    hc["grid"].to_csv(OUT / "grid_crypto.csv", index=False)

    say("\nGrid, S&P members (AR at 20 days; key = real minus placebo):")
    say(hs["grid"].to_string(index=False, float_format=fmt))
    say("\nGrid, crypto (AR at 28 days):")
    say(hc["grid"].to_string(index=False, float_format=fmt))

    # ---------------------------------------------------------------- exploratory tables
    say("\n" + "=" * 100); say("EXPLORATORY"); say("=" * 100)
    for label, ev in (("S&P members", ev_s), ("crypto", ev_c), ("single assets", ev_n)):
        t = summarize(ev[ev.ma == PRIMARY], by=("line",))
        t["line"] = t.line.map(lambda i: "real" if i == 0 else f"{OFFSETS[i]:+.0f} ATR")
        say(f"\n{label}, daily 200-day SMA: real line vs placebo lines (AR in %, horizons short/mid/long):")
        say(t.to_string(index=False, float_format=fmt))
    sa = summarize(pd.concat([ev_n[ev_n.line == 0], named_crypto[named_crypto.line == 0]]), by=("asset", "ma"))
    sa["ma"] = sa.ma.map(lambda i: MA_NAME[i]); sa.to_csv(OUT / "single_assets_by_ma.csv", index=False)
    prim = sa[sa.ma == "D-SMA200"]
    say("\nSingle assets, daily 200-day SMA, real line:")
    say(prim.to_string(index=False, float_format=fmt))

    splits = []
    for label, ev in (("S&P members", ev_s), ("crypto", ev_c)):
        r = ev[(ev.ma == PRIMARY) & (ev.line == 0)].copy()
        r["hold_close"] = np.where(r.held, "held at close", "broke at close")
        r["strength"] = pd.cut(r.reject, [-np.inf, -0.5, 0, 0.5, 1, np.inf])
        r["first_test"] = np.where(r.run >= 60, ">= 60 closes above", "< 60 closes above")
        r["depth"] = pd.cut(r.dd252, [-1, -0.4, -0.2, -0.1, 0.01])
        r["confluence"] = pd.cut(r.confl25, [0, 1, 2, 3, 40])
        r["trend"] = np.where(r.rising, "rising 200-day", np.where(r.falling, "falling 200-day", "unknown"))
        for col in ("hold_close", "strength", "first_test", "depth", "confluence", "trend"):
            g = r.groupby(col, observed=True)
            for k, x in g:
                m, p, nn = boot_mean(x, "ar_m", B=1000)
                m2, p2, n2 = boot_mean(x, "ar_e2", B=1000)
                ml, pl_, _ = boot_mean(x, "ar_m_lo", B=1000)
                m2l, p2l, _ = boot_mean(x, "ar_e2_lo", B=1000)
                splits.append({"pool": label, "split": col, "bucket": str(k), "n": nn, "E1_AR_%": m * 100, "E1_p": p,
                               "E1_hit_%": (x.ar_m.dropna() > 0).mean() * 100, "X2_ex_%": x.x2_ex.mean() * 100,
                               "E2_n": n2, "E2_AR_%": m2 * 100, "E2_p": p2, "E2_hit_%": (x.ar_e2.dropna() > 0).mean() * 100,
                               "E1_lo_%": ml * 100, "E1_lo_p": pl_, "E2_lo_%": m2l * 100, "E2_lo_p": p2l,
                               "pool_adj_%": x.ar_pool.mean() * 100})
    sp = pd.DataFrame(splits); sp.to_csv(OUT / "splits_primary.csv", index=False)
    say("\nSplits, daily 200-day SMA, real line (AR mid horizon). CAUTION: 'hold_close' and 'strength' are only known at")
    say("the touch day's close, so the E1 column (filled earlier, at the line) contains that day's own move; judge those")
    say("rows by E2, which buys only after the close is known (crypto at the close, stocks at the next open).")
    say("E1/E2 = pre-registered same-year baseline; *_lo = leave-out own drift; pool_adj = close-synchronous minus the pool:")
    say(sp.to_string(index=False, float_format=fmt))

    # HOOD-like analog (pre-registered definition), under all three baselines
    r = ev_s[(ev_s.ma == PRIMARY) & (ev_s.line == 0)]
    an = analog(r)
    an_p = analog(ev_s[(ev_s.ma == PRIMARY) & (ev_s.line > 0)])
    rows = []
    strong = an[an.held & (an.reject >= 1.0)]
    e1 = (("ar_s", "5 days", "same-year"), ("ar_s_lo", "5 days", "leave-out"), ("ar_m", "20 days", "same-year"),
          ("ar_m_lo", "20 days", "leave-out"), ("ar_pool", "20 days", "pool (close to close)"),
          ("ar_l", "60 days", "same-year"), ("ar_l_lo", "60 days", "leave-out"))
    e2 = (("ar_e2", "20 days", "same-year"), ("ar_e2_lo", "20 days", "leave-out"))
    for lab, x, cols_ in (("HOOD-like, real 200-day, limit at the line (E1)", an, e1),
                          ("HOOD-like, placebo lines, E1", an_p, e1),
                          ("HOOD-like, real 200-day, buy after the bounce (E2)", an, e2),
                          ("HOOD-like, strong bounce (close >= 1 ATR above), E2", strong, e2)):
        for col, h, base in cols_:
            q = x[col].dropna()
            if len(q) < 5:
                continue
            eps = len(first_touch(x[x[col].notna()]))
            st = boot_stats(x, col, B=1000)
            rows.append({"set": lab, "horizon": h, "baseline": base, "n": st["n"], "episodes": eps, "months": st["months"],
                         "eff_n": st["n_eff"], "mean_AR_%": st["mean"] * 100, "ci_lo_%": st["lo"] * 100,
                         "ci_hi_%": st["hi"] * 100, "p": st["p"], "median_%": q.median() * 100,
                         "hit_%": (q > 0).mean() * 100, "p10_%": q.quantile(.1) * 100, "p90_%": q.quantile(.9) * 100})
    hd = pd.DataFrame(rows); hd.to_csv(OUT / "hood_analog.csv", index=False)
    say("\nHOOD-like analog (60-day vol >= 50%, >= 20% below the 52-week high, falling 200-day, >= 20 closes above).")
    say("episodes = touches with no touch of the same line in the previous 28 days; eff_n from the month-block SE.")
    say("The same-year baseline is biased upward for this filter: run `--null` for its no-edge level.")
    say(hd.to_string(index=False, float_format=fmt))

    bt = []
    for name in NAMED:
        f = frames.get(name) or crypto.get(name)
        if f is None:
            continue
        for ma in ("D-SMA50", "D-SMA200", "W-SMA40", "M-SMA10"):
            bt.append(backtest(f, MA_NAME.index(ma)))
    btd = pd.DataFrame(bt); btd.to_csv(OUT / "backtests_named.csv", index=False)
    say("\nSingle-asset backtests (non-overlapping X2 trades, full equity per trade, cash earns T-bills):")
    say(btd.to_string(index=False, float_format=fmt))

    chart_line_check(stocks, spells, pool_s, s_end, ev_s, say)

    say("\n" + "=" * 100); say("PRE-REGISTERED VERDICTS"); say("=" * 100)
    say("S&P members: " + ", ".join(f"B{k} {'PASS' if hs[k] else 'FAIL'}" for k in "12345"))
    say("Crypto:      " + ", ".join(f"C{k} {'PASS' if hc[k] else 'FAIL'}" for k in "12345"))
    log.close()


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print("python3 -m analysis_2026.ma_bounce            (writes analysis_2026/results_bounce/)\n"
              "python3 -m analysis_2026.ma_bounce --null 16  (no-edge simulation; run after the main run)")
        sys.exit(0)
    if "--null" in sys.argv:
        i = sys.argv.index("--null")
        null_run(int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 16)
    else:
        main()
