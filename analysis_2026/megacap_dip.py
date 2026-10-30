"""
Buying mega-caps after a 25% drop. Pre-registration: analysis_2026/MEGACAP_DIP_PREREG.md.

    python3 -m analysis_2026.megacap_dip [--dv-parquet PATH]     # -> analysis_2026/results_megacap_dip/

The rule: when a stock in the universe closes 25% or more below its highest close of the last 252 trading days
(crossing from above; it re-arms after a new 52-week high), buy at the next open and sell at the first close at least
366 calendar days later. Universes: U1/U2 the 10/20 largest S&P 500 members by market cap at the prior year-end
(results_megacap_dip/topcap_lists.csv, compiled from public sources and price-checked), U3 every S&P 500 member on the
day, U4 the tech names of U2, U5 today's Magnificent 7 (hindsight, biased), U6 the 10 members with the highest median
dollar volume over the prior year (needs the Johnbrick prices.parquet for volume; --dv-parquet).

Primary vehicle (calendar-time dip book): equal weight across all open event positions, SPY on days with none; the
statistic is its mean daily return minus SPY's, annualised. Entry-day return includes SPY's overnight move (the money
sits in SPY until the open). Costs 0.03% per side.

Data (gitignored): data/universe_pit_all/ (point-in-time S&P 500 incl. failed companies, total-return OHLC, SPY,
members.csv), data/sso_gold/ (T-bills and the S&P 500 since 1928), data/etf/QQQ.csv.

Audit fixes (2026-10-30, after the first full run; FINDINGS.md lists each with its effect):
- arming starts from the first loaded bar, so a decline that crossed -25% before a stock's 252nd bar gives no event
  later (the first run started every stock armed);
- predecessor price files that carry their successor's prices are dropped (C-199811, BAC-199809, WFC-199811, ...);
- 10-slot portfolio: an entry gets what SPY is left instead of being skipped (taxed and untaxed runs now take the same
  trades); long-term means sold after the one-year anniversary; carried losses keep their character; tax that cannot
  be paid stays owed; SPY buy & hold starts at the same close;
- U6 uses members on 1996-01-02 for 1996 and counts Alphabet once;
- the reality check uses 10,000 draws;
- reporting: compounded excess next to the arithmetic one, U3 coverage, T3 on 2002-2026, year-clustered event CIs,
  held universes for U3 and U5, and a robustness section (literal entry, anniversary exit, list coin tosses, hold
  length). The corrected lists (AIG #10 at end-2006, Royal Dutch #19 at end-2001) come from megacap_lists.CORRECTIONS.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis_2026" / "results_megacap_dip"
PIT = ROOT / "data" / "universe_pit_all"
LISTS = OUT / "topcap_lists.csv"

START = pd.Timestamp("1996-01-02")
COST = 0.0003
THR = 0.25
LOOK = 252
HOLD = 366                      # calendar days: first close at least this long after entry
BLOCK = 250
N_BOOT = 10_000
N_RC = 10_000                   # audit: the pre-registration says "the same stationary bootstrap" (first run 2,000)
SEED = 20261030
MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
COINED = pd.Timestamp("2023-04-01")
HALVES = [("1996-2010", "1996-01-01", "2010-12-31"), ("2011-2026", "2011-01-01", "2026-12-31")]
ERAS = [("1996-2002", "1996-01-01", "2002-12-31"), ("2003-2009", "2003-01-01", "2009-12-31"),
        ("2010-2019", "2010-01-01", "2019-12-31"), ("2020-2026", "2020-01-01", "2026-12-31")]
GRID_THR = [0.20, 0.25, 0.30, 0.40, 0.50]
GRID_REF = ["52w", "ath", "63d"]
GRID_HOLD = {"63d": 63, "126d": 126, "366d": 366, "2y": 731, "3y": 1096, "recover": "recover"}
RECOVER_MAX = 1827              # 5 years
SLOTS = 10
ST_RATE, LT_RATE = 0.35, 0.20


# ------------------------------------------------------------------ data

def duplicate_predecessors(raw, min_corr=0.9, min_days=60):
    """Predecessor files (SYMBOL-YYYYMM) whose daily returns track the current SYMBOL file (correlation > min_corr over
    the overlap): they carry the successor's prices (audit: C-199811 holds Travelers', BAC-199809 NationsBank's)."""
    import re
    out = {}
    for s in raw:
        m = re.match(r"^(.+)-(\d{6})$", s)
        if not m or m.group(1) not in raw:
            continue
        a, b = raw[s].close.pct_change(), raw[m.group(1)].close.pct_change()
        j = pd.concat([a, b], axis=1, sort=True).dropna()
        j = j[(j.iloc[:, 0] != 0) | (j.iloc[:, 1] != 0)]
        if len(j) >= min_days:
            c = float(j.corr().iloc[0, 1])
            if c > min_corr:
                out[s] = f"tracks {m.group(1)} (correlation {c:.3f} over {len(j)} days)"
    return out


def load_data():
    """Point-in-time S&P 500 OHLC (quality-filtered as in split_delay), SPY on the common calendar, T-bills.
    Predecessor files that duplicate their successor's prices are dropped (audit fix)."""
    from screener.data import from_csv_folder, quality_filter
    from analysis_2026.sso_gold import base_daily
    raw = from_csv_folder(PIT)
    dups = duplicate_predecessors(raw)
    sp, dropped = quality_filter({k: v for k, v in raw.items() if k not in dups}, keep_collapsed=True)
    spy = raw["SPY"][["open", "close"]].astype(float)
    data = {k: v[["open", "close"]].astype(float) for k, v in sp.items() if k != "SPY" and len(v) > LOOK}
    end = min(spy.index[-1], max(v.index[-1] for v in data.values()))
    cal = spy.loc[START:end].index
    spy = spy.loc[:end]
    b = base_daily(end=str(end.date()))
    rc = b["r_cash"].reindex(cal).fillna(0.0)
    mem = pd.read_csv(PIT / "members.csv", parse_dates=["start", "end"])
    mem["symbol"] = mem.symbol.str.upper()
    return dict(data=data, spy=spy, cal=cal, rc=rc, mem=mem, base=b, dropped=dropped, end=end, dups=dups)


def load_lists(data):
    """Year-end lists -> {year Y+1: [symbols by rank]} for U1, U2, U4, plus the dropped names."""
    L = pd.read_csv(LISTS)
    L = L.sort_values(["year_end", "rank"])
    u1, u2, u4, missing = {}, {}, {}, []
    for y, g in L.groupby("year_end"):
        g = g[g["rank"] <= 20]
        ok = g[g.symbol.isin(data.keys())]
        for _, r in g[~g.symbol.isin(data.keys())].iterrows():
            missing.append({"year_end": y, "rank": int(r["rank"]), "company": r.company, "symbol": r.symbol})
        u1[y + 1] = list(ok[ok["rank"] <= 10].symbol)
        u2[y + 1] = list(ok.symbol)
        u4[y + 1] = list(ok[ok.tech.astype(bool)].symbol)
    return u1, u2, u4, pd.DataFrame(missing), L


def rank_of(L):
    return {(int(y) + 1, s): int(k) for y, s, k in zip(L.year_end, L.symbol, L["rank"])}


def dollar_volume_universe(parquet, mem, years, k=10):
    """U6: per 1 January, the k members (members.csv on that day) with the highest median close x volume over the
    prior 252 trading days. Series without volume (CRSP-sourced dead companies) cannot be ranked: they are counted."""
    d = pd.read_parquet(parquet, columns=["date", "ticker", "close", "volume"])
    d["ticker"] = d.ticker.str.upper()
    d["dv"] = d.close * d.volume
    piv = d.pivot_table(index="date", columns="ticker", values="dv", aggfunc="last").sort_index()
    out, info = {}, []
    first = mem.start.min()
    for y in years:
        jan1 = pd.Timestamp(f"{y}-01-01")
        day = max(jan1, first)          # audit fix: members.csv starts 1996-01-02, so 1996 had no members
        m = mem[(mem.start <= day) & (mem.end.isna() | (mem.end >= day))].symbol.unique()
        if "GOOGL" in m:                # audit fix: Alphabet once, as in the lists
            m = m[m != "GOOG"]
        hist = piv[piv.index < jan1].iloc[-LOOK:]
        cols = [s for s in m if s in hist.columns]
        med = hist[cols].median(skipna=True)
        nvol = int(hist[cols].notna().sum().eq(0).sum()) + len(set(m) - set(cols))
        top = med.dropna().sort_values(ascending=False).index[:k]
        out[y] = list(top)
        info.append({"year": y, "members": len(m), "without_volume": nvol, "symbols": " ".join(top)})
    return out, pd.DataFrame(info)


# ------------------------------------------------------------------ events and positions

def drawdown(close, ref="52w"):
    """close / reference high - 1 on every bar. Before LOOK bars the reference is the high of the bars loaded so far
    (the rolling window is not full yet); find_events only lets a stock trigger from its LOOK-th bar."""
    c = close.to_numpy(float)
    if ref == "52w":
        peak = close.rolling(LOOK, min_periods=1).max().to_numpy()
    elif ref == "63d":
        peak = close.rolling(63, min_periods=1).max().to_numpy()
    elif ref == "ath":
        peak = np.maximum.accumulate(c)
    else:
        raise ValueError(ref)
    return c / peak - 1, peak


def crossings(dd, thr, first=LOOK - 1):
    """Indices (>= first) of the first crossing to <= -thr in each decline: a crossing disarms, a new high (dd >= 0)
    re-arms. The state runs from the first loaded bar, so a decline that crossed before bar `first` gives no event
    later (audit fix: the first run started every stock armed at its LOOK-th bar). Crossings outside the universe
    still disarm (one event per decline)."""
    out = []
    armed = True
    prev = np.nan
    for i, x in enumerate(dd):
        if np.isnan(x):
            prev = x
            continue
        if x >= -1e-12:
            armed = True
        if armed and not np.isnan(prev) and prev > -thr and x <= -thr:
            if i >= first:
                out.append(i)
            armed = False
        prev = x
    return out


class Universe:
    """Membership test on (symbol, date) arrays: by calendar year (lists), by interval (members.csv) or always."""

    def __init__(self, kind, by_year=None, mem=None, syms=None, name=""):
        self.kind, self.by_year, self.name = kind, by_year, name
        self.syms = set(syms or [])
        if kind == "interval":
            self.iv = {s: list(zip(g.start, g.end.fillna(pd.Timestamp("2100-01-01")))) for s, g in mem.groupby("symbol")}
            self.syms = set(self.iv)
        elif kind == "year":
            self.syms = set(s for v in by_year.values() for s in v)

    def mask(self, sym, dates):
        if sym not in self.syms:
            return np.zeros(len(dates), bool)
        if self.kind == "always":
            return np.ones(len(dates), bool)
        if self.kind == "year":
            yrs = dates.year
            ok = np.zeros(len(dates), bool)
            for y in np.unique(yrs):
                if sym in self.by_year.get(int(y), ()):
                    ok |= yrs == y
            return ok
        ok = np.zeros(len(dates), bool)
        for a, b in self.iv[sym]:
            ok |= (dates >= a) & (dates <= b)
        return ok


def find_events(D, U, thr=THR, ref="52w", cache=None):
    """Events of universe U: list of dicts (sym, i = trigger bar, date, dd, peak)."""
    data, ev = D["data"], []
    cache = {} if cache is None else cache
    for s in sorted(U.syms):
        if s not in data:
            continue
        df = data[s]
        key = (s, ref)
        if key not in cache:
            cache[key] = drawdown(df.close, ref)
        dd, peak = cache[key]
        ck = (s, ref, thr)
        if ck not in cache:
            cache[ck] = crossings(dd, thr)
        idx = [i for i in cache[ck] if df.index[i] >= START and i + 1 < len(df)]
        if not idx:
            continue
        m = U.mask(s, df.index[idx])
        for i, ok in zip(idx, m):
            if ok:
                ev.append({"sym": s, "i": i, "date": df.index[i], "dd": float(dd[i]), "peak": float(peak[i])})
    return sorted(ev, key=lambda e: (e["date"], e["sym"]))


def exit_index(df, j, hold, peak=None):
    """Exit bar for an entry at bar j: first close >= entry date + hold calendar days (the last bar if the series
    ends first). hold='recover': first close at or above the pre-drop high, at most RECOVER_MAX days."""
    dates = df.index
    if hold == "recover":
        lim = dates[j] + pd.Timedelta(days=RECOVER_MAX)
        k_lim = min(int(dates.searchsorted(lim)), len(df) - 1)
        c = df.close.to_numpy()[j:k_lim + 1]
        hit = np.nonzero(c >= peak)[0]
        return j + int(hit[0]) if len(hit) else k_lim
    if hold == "anniv":                 # first close strictly after the one-year anniversary (long-term by IRS rules)
        k = int(dates.searchsorted(dates[j] + pd.DateOffset(years=1), side="right"))
        return min(k, len(df) - 1)
    k = int(dates.searchsorted(dates[j] + pd.Timedelta(days=hold)))
    return min(k, len(df) - 1)


def position(D, e, hold=HOLD, cost=COST, overnight=True):
    """Daily returns of one event position on its own bars: entry at bar j = i + 1's open (plus SPY's overnight move,
    since the money waits in SPY; overnight=False is the pre-registration's literal close/open - 1), exit at bar k's
    close."""
    df = D["data"][e["sym"]]
    j = e["i"] + 1
    k = exit_index(df, j, hold, e.get("peak"))
    o, c = df.open.to_numpy(), df.close.to_numpy()
    r = np.empty(k - j + 1)
    spy = D["spy"]
    dj = df.index[j]
    g = 0.0
    if overnight and dj in spy.index:
        p = spy.index.get_loc(dj)
        if p > 0:
            g = spy.open.iloc[p] / spy.close.iloc[p - 1] - 1
    r[0] = (1 + g) * (c[j] / o[j]) * (1 - cost) - 1
    if k > j:
        r[1:] = c[j + 1:k + 1] / c[j:k] - 1
    r[-1] = (1 + r[-1]) * (1 - cost) - 1
    return df.index[j:k + 1], r, j, k


def contribution(D, e, hold=HOLD, overnight=True):
    """One position on the calendar: (sums, counts) arrays of length T + 1 (returns added on its days; +1/-1 at its
    first and after its last calendar day)."""
    cal = D["cal"]
    T = len(cal)
    sums = np.zeros(T + 1)
    cnt = np.zeros(T + 1)
    dates, r, _, _ = position(D, e, hold, overnight=overnight)
    p = cal.searchsorted(dates)
    keep = p < T
    if keep.any():
        np.add.at(sums, p[keep], r[keep])
        cnt[p[keep][0]] += 1
        cnt[p[keep][-1] + 1] -= 1
    return sums, cnt


def book_from(D, sums, cnt):
    """Book from summed contributions: equal weight across open positions, SPY on days with none."""
    cal = D["cal"]
    T = len(cal)
    n = np.cumsum(cnt)[:T]
    spy_r = np.nan_to_num(D["spy"].close.pct_change().reindex(cal).to_numpy())
    br = np.where(n > 0, sums[:T] / np.maximum(n, 1), spy_r)
    return pd.Series(br - spy_r, cal), pd.Series(br, cal), pd.Series(n, cal)


def book(D, events, hold=HOLD, overnight=True):
    """Calendar-time dip book: (excess vs SPY, book return, open-position count) on D['cal']."""
    T = len(D["cal"])
    sums = np.zeros(T + 1)
    cnt = np.zeros(T + 1)
    for e in events:
        a, b = contribution(D, e, hold, overnight)
        sums += a
        cnt += b
    return book_from(D, sums, cnt)


def event_table(D, events, hold=HOLD, ranks=None):
    """Per event: entry, exit, stock and SPY return over the hold, excess, further drop after entry, window complete."""
    spy = D["spy"]
    rows = []
    for e in events:
        df = D["data"][e["sym"]]
        j = e["i"] + 1
        k = exit_index(df, j, hold, e.get("peak"))
        dj, dk = df.index[j], df.index[k]
        r_stock = df.close.iloc[k] / df.open.iloc[j] * (1 - COST) ** 2 - 1
        so = spy.open.reindex([dj]).iloc[0]
        sc = spy.close.reindex([dk]).iloc[0]
        if np.isnan(so):
            so = spy.close.asof(dj)
        if np.isnan(sc):
            sc = spy.close.asof(dk)
        r_spy = sc / so - 1
        low = df.close.iloc[j:k + 1].min() / df.open.iloc[j] - 1
        hd = pd.Timedelta(days=hold if isinstance(hold, int) else (366 if hold == "anniv" else RECOVER_MAX))
        ended_early = (k == len(df) - 1 and dk < dj + hd     # series ended (merger, delisting) before the hold
                       and dk < D["end"] - pd.Timedelta(days=7))
        complete = (dj + hd <= D["end"]) or ended_early     # the outcome is known
        rows.append({"sym": e["sym"], "trigger": e["date"].date(), "dd": round(e["dd"], 4),
                     "rank": (ranks or {}).get((e["date"].year, e["sym"])), "entry": dj.date(), "exit": dk.date(),
                     "days": (dk - dj).days, "ret": r_stock, "spy_ret": r_spy, "excess": r_stock - r_spy,
                     "further_drop": low, "series_ended": bool(ended_early),
                     "complete": bool(complete or ended_early)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ statistics

def boot_mean(x, n=N_BOOT, seed=SEED, block=BLOCK):
    """Null-centred stationary bootstrap of the mean (sso_gold.stationary_boot_p) plus the bootstrap SD."""
    from analysis_2026.sso_gold import boot_indices
    x = np.asarray(x, float)
    T = len(x)
    m = x.mean()
    rng = np.random.default_rng(seed)
    means = []
    for k0 in range(0, n, 1000):
        means.append(x[boot_indices(T, block, min(1000, n - k0), rng)].mean(axis=1))
    means = np.concatenate(means)
    return {"p": float((means - m >= m).mean()), "sd": float(means.std()),
            "ci95": (float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)))}


def reality_check(E, n=N_RC, seed=SEED, block=BLOCK):
    """White's reality check of max_k mean(E[:, k]) > 0 (benchmark SPY = zero excess); recentred stationary bootstrap."""
    from analysis_2026.sso_gold import boot_indices
    E = np.asarray(E, float)
    T, K = E.shape
    mu = E.mean(0)
    v = float(mu.max())
    rng = np.random.default_rng(seed)
    vs = np.empty(n)
    for k0 in range(0, n, 25):
        m = min(25, n - k0)
        idx = boot_indices(T, block, m, rng)
        mb = E[idx].mean(axis=1)                 # (m, K)
        vs[k0:k0 + m] = (mb - mu).max(1)
    return {"V_obs_%/yr": v * 252 * 100, "argmax": int(mu.argmax()), "p_rc": float((vs >= v).mean())}


def capm(book_r, spy_r, rc, lags=12):
    """Monthly excess of the book on SPY's excess (both over T-bills): alpha %/yr, NW t, beta."""
    f = lambda r: (1 + r).groupby(r.index.to_period("M")).prod() - 1
    y = f(book_r) - f(rc)
    x = f(spy_r) - f(rc)
    Z = np.column_stack([np.ones(len(y)), x.to_numpy()])
    b = np.linalg.lstsq(Z, y.to_numpy(), rcond=None)[0]
    e = y.to_numpy() - Z @ b
    ZZi = np.linalg.inv(Z.T @ Z)
    S = (Z * e[:, None]).T @ (Z * e[:, None])
    for L in range(1, lags + 1):
        G = (Z[L:] * e[L:, None]).T @ (Z[:-L] * e[:-L, None])
        S += (1 - L / (lags + 1)) * (G + G.T)
    se = np.sqrt(np.diag(ZZi @ S @ ZZi))
    return {"alpha_%/yr": b[0] * 1200, "alpha_t": b[0] / se[0], "beta": b[1]}


def holm(ps):
    order = sorted(ps.items(), key=lambda kv: kv[1])
    m, run, out = len(order), 0.0, {}
    for i, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def cluster_boot(df, col, key, n=5000, seed=SEED):
    """Mean of df[col] with a bootstrap over clusters (df[key]); returns mean, 95% CI and P(mean* <= 0)."""
    if df.empty:
        return {"mean": np.nan, "lo": np.nan, "hi": np.nan, "p_le0": np.nan, "clusters": 0}
    g = df.groupby(key)[col].agg(["sum", "count"])
    s, c = g["sum"].to_numpy(), g["count"].to_numpy()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(g), (n, len(g)))
    mb = s[pick].sum(1) / c[pick].sum(1)
    return {"mean": float(s.sum() / c.sum()), "lo": float(np.quantile(mb, 0.025)), "hi": float(np.quantile(mb, 0.975)),
            "p_le0": float((mb <= 0).mean()), "clusters": len(g)}


def ann(x):
    return float(np.mean(x) * 252 * 100)


def perf(r, rc):
    """CAGR, vol, Sharpe (over T-bills), max drawdown of a daily return series."""
    v = (1 + r).cumprod()
    yrs = len(r) / 252
    ex = r - rc.reindex(r.index).fillna(0.0)
    return {"CAGR_%": (v.iloc[-1] ** (1 / yrs) - 1) * 100, "vol_%": r.std() * np.sqrt(252) * 100,
            "Sharpe": ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else np.nan,
            "maxDD_%": (v / v.cummax() - 1).min() * 100}


# ------------------------------------------------------------------ placebo (S1)

def placebo(D, events, U, hold=HOLD, draws=200, seed=SEED):
    """For each complete event, `draws` random entries on days when the same stock was in U, had LOOK bars and a full
    window. Returns per-event rows (event excess, placebo mean excess)."""
    rng = np.random.default_rng(seed)
    spy = D["spy"]
    rows = []
    elig_cache = {}
    for e in events:
        s = e["sym"]
        df = D["data"][s]
        j = e["i"] + 1
        if df.index[j] + pd.Timedelta(days=hold) > D["end"]:
            continue
        if s not in elig_cache:
            d = df.index
            ok = U.mask(s, d)
            ok[:LOOK - 1] = False
            ok &= d >= START
            ok[-1] = False
            jj = np.nonzero(ok)[0] + 1
            jj = jj[d[jj] + pd.Timedelta(days=hold) <= D["end"]]
            ex = np.full(len(jj), np.nan)
            if len(jj):
                kk = np.minimum(d.searchsorted(d[jj] + pd.Timedelta(days=hold)), len(df) - 1)
                rs = df.close.to_numpy()[kk] / df.open.to_numpy()[jj] * (1 - COST) ** 2 - 1
                so = spy.open.reindex(d[jj]).to_numpy()
                sc = spy.close.reindex(d[kk]).to_numpy()
                so = np.where(np.isnan(so), spy.close.reindex(d[jj], method="ffill").to_numpy(), so)
                sc = np.where(np.isnan(sc), spy.close.reindex(d[kk], method="ffill").to_numpy(), sc)
                ex = rs - (sc / so - 1)
            elig_cache[s] = ex
        ex_all = elig_cache[s]
        if len(ex_all) == 0:
            continue
        k = exit_index(df, j, hold)
        r_ev = df.close.iloc[k] / df.open.iloc[j] * (1 - COST) ** 2 - 1
        sc = spy.close.asof(df.index[k])
        so = spy.open.reindex([df.index[j]]).iloc[0]
        so = spy.close.asof(df.index[j]) if np.isnan(so) else so
        pick = rng.integers(0, len(ex_all), draws)
        rows.append({"sym": s, "trigger": e["date"], "year": e["date"].year, "event_excess": r_ev - (sc / so - 1),
                     "placebo_excess": float(np.nanmean(ex_all[pick])), "all_days_excess": float(np.nanmean(ex_all))})
    P = pd.DataFrame(rows)
    if len(P):
        P["diff"] = P.event_excess - P.placebo_excess
    return P


def held_universe(D, by_year):
    """S1b: equal money in each of the year's members on its first trading day, drifting; a member without data sits
    in T-bills. Daily returns on D['cal']."""
    cal, rc = D["cal"], D["rc"]
    out = []
    for y in sorted(by_year):
        idx = cal[(cal.year == y)]
        if len(idx) == 0:
            continue
        cols = {}
        for s in by_year[y]:
            if s in D["data"]:
                cols[s] = D["data"][s].close.pct_change().reindex(idx)   # first day vs the prior close
        if not cols:
            continue
        M = pd.DataFrame(cols)
        M = M.apply(lambda col: col.fillna(rc.reindex(idx)))
        V = (1 + M).cumprod().mean(axis=1)
        out.append(V / V.shift(1).fillna(1.0) - 1)
    return pd.concat(out).sort_index()


# ------------------------------------------------------------------ 10-slot portfolio with tax (S9)

def long_term(bought, sold):
    """IRS: long-term only if sold after the one-year anniversary of the purchase."""
    return sold > bought + pd.DateOffset(years=1)


def slot_portfolio(D, events, ranks=None, hold=HOLD, slots=SLOTS, frac=0.10, tax=True):
    """Start 100% SPY (bought at the first calendar day's close). Each event takes `frac` of the portfolio's value at
    the entry open, sold from SPY lots (FIFO), and buys the stock; at exit the proceeds buy a new SPY lot. Events
    beyond `slots` open positions are skipped; if SPY holds less than `frac` of the portfolio, the position gets what
    SPY is left (audit fix: the first run skipped such events, so the taxed and untaxed runs took different trades).
    tax=True: realised gains taxed each year-end at 20% if long-term (sold after the one-year anniversary), else 35%;
    short- and long-term netted against each other, net losses carried forward with their character (audit fixes);
    paid by selling SPY (those sales count the next year). Tax that cannot be paid because no SPY is left stays owed
    and is paid from later SPY proceeds or deducted at the end (audit fix). Everything is sold and taxed at the end.
    Returns (daily value series net of owed tax, after-tax terminal value, skipped count, taken count)."""
    cal = D["cal"]
    spy = D["spy"].reindex(cal)
    spy_o, spy_c = spy.open.to_numpy(), spy.close.to_numpy()
    data = D["data"]
    closes = {}

    def px_close(s, t):
        if s not in closes:
            closes[s] = data[s].close.reindex(cal).ffill().to_numpy()
        return closes[s][t]

    order = sorted(events, key=lambda e: (e["date"], (ranks or {}).get((e["date"].year, e["sym"]), 999), e["sym"]))
    entries = {}
    for e in order:
        df = data[e["sym"]]
        j = e["i"] + 1
        k = exit_index(df, j, hold, e.get("peak"))
        pj, pk = cal.searchsorted(df.index[j]), cal.searchsorted(df.index[k])
        if pj >= len(cal):
            continue
        entries.setdefault(pj, []).append((e, j, min(pk, len(cal) - 1)))
    lots = [[1.0 / spy_c[0], 1.0, cal[0]]]          # SPY lots: units, basis, date
    pos = []                                         # dicts: sym, units, basis, date, exit_t
    realised = {"st": 0.0, "lt": 0.0}
    carry = {"st": 0.0, "lt": 0.0}
    owed = 0.0
    val = np.empty(len(cal))
    skipped = taken = 0

    def spy_value(price):
        return sum(u for u, _, _ in lots) * price

    def sell_spy(amount, price, t):
        """Sell `amount` of SPY (FIFO); returns the amount actually sold."""
        need = amount / price
        sold = 0.0
        while need > 1e-15 and lots:
            u, b, d = lots[0]
            q = min(u, need)
            realised["lt" if long_term(d, cal[t]) else "st"] += q * price - b * q / u
            if q >= u - 1e-15:
                lots.pop(0)
            else:
                lots[0] = [u - q, b * (u - q) / u, d]
            need -= q
            sold += q * price
        return sold

    def year_tax():
        st = realised["st"] - carry["st"]
        lt = realised["lt"] - carry["lt"]
        realised["st"] = realised["lt"] = 0.0
        carry["st"] = carry["lt"] = 0.0
        if not tax:
            return 0.0
        if st < 0 < lt:                              # net short- and long-term against each other
            lt, st = lt + st, 0.0
        elif lt < 0 < st:
            st, lt = st + lt, 0.0
        if st < 0:                                   # net losses carried forward with their character
            carry["st"], st = -st, 0.0
        if lt < 0:
            carry["lt"], lt = -lt, 0.0
        return ST_RATE * st + LT_RATE * lt

    for t in range(len(cal)):
        if t in entries:
            v_open = spy_value(spy_o[t]) + sum(
                p["units"] * (data[p["sym"]].open.get(cal[t], px_close(p["sym"], t))) for p in pos)
            for e, j, kt in entries[t]:
                if len(pos) >= slots:
                    skipped += 1
                    continue
                # 10% of the portfolio, or what SPY is left if positions have grown past 90%: the trades taken
                # then depend only on open slots, the same with and without tax
                amt = min(frac * v_open, spy_value(spy_o[t]))
                if amt <= 0:
                    skipped += 1
                    continue
                amt = sell_spy(amt, spy_o[t], t)
                o = data[e["sym"]].open.iloc[j]
                pos.append({"sym": e["sym"], "units": amt * (1 - COST) / o, "basis": amt, "date": cal[t], "exit_t": kt})
                taken += 1
        keep = []
        for p in pos:
            if p["exit_t"] <= t:
                proceeds = p["units"] * px_close(p["sym"], t) * (1 - COST)
                realised["lt" if long_term(p["date"], cal[t]) else "st"] += proceeds - p["basis"]
                lots.append([proceeds / spy_c[t], proceeds, cal[t]])
            else:
                keep.append(p)
        pos = keep
        last_of_year = t == len(cal) - 1 or cal[t + 1].year != cal[t].year
        if last_of_year and t < len(cal) - 1:
            owed += year_tax()
        if owed > 0 and lots:
            owed -= sell_spy(min(owed, spy_value(spy_c[t])), spy_c[t], t)   # the cash leaves; gain counts next year
        val[t] = spy_value(spy_c[t]) + sum(p["units"] * px_close(p["sym"], t) for p in pos) - owed
    # everything was sold at the last close (exits are capped there) except SPY: realise it and pay the final tax
    t = len(cal) - 1
    for p in pos:
        proceeds = p["units"] * px_close(p["sym"], t) * (1 - COST)
        realised["lt" if long_term(p["date"], cal[t]) else "st"] += proceeds - p["basis"]
    for u, b, d in lots:
        realised["lt" if long_term(d, cal[t]) else "st"] += u * spy_c[t] - b
    after = val[-1] - year_tax()
    return pd.Series(val, cal), after, skipped, taken


# ------------------------------------------------------------------ index-level dips (S6)

def index_dips(level_px, level_tr, thr=THR, hold_days=HOLD):
    """Crossings of -thr from the 252-day high of the price level; forward return of the total-return level from the
    next close to the first close >= hold_days later, vs every such window."""
    dd, _ = drawdown(level_px, "52w")
    idx = crossings(dd, thr)
    d = level_tr.index
    trv = level_tr.to_numpy()
    k_all = np.minimum(d.searchsorted(d + pd.Timedelta(days=hold_days)), len(d) - 1)
    full = (d + pd.Timedelta(days=hold_days)) <= d[-1]
    fwd_all = trv[k_all] / trv - 1
    rows = []
    for i in idx:
        j = i + 1
        if j >= len(d) or not full[j]:
            continue
        rows.append({"trigger": d[i].date(), "dd": round(float(dd[i]), 4), "fwd": float(fwd_all[j])})
    allw = fwd_all[full]
    return pd.DataFrame(rows), {"windows": int(full.sum()), "mean_all": float(np.mean(allw)),
                                "median_all": float(np.median(allw)), "hit_all": float(np.mean(allw > 0))}


# ------------------------------------------------------------------ audit additions

def coverage(D, years=(1996, 1998, 2000, 2002, 2006, 2010, 2020)):
    """Share of members.csv members (on the first trading day of each year) that have a price series."""
    mem, out = D["mem"], []
    for y in years:
        day = max(pd.Timestamp(f"{y}-01-01"), mem.start.min())
        m = mem[(mem.start <= day) & (mem.end.isna() | (mem.end >= day))].symbol.unique()
        out.append((y, len(m), sum(s in D["data"] for s in m)))
    return out


def compounded(br, spy_r):
    """Book CAGR minus SPY CAGR and the mean log excess, %/yr (the primary statistic is the arithmetic mean)."""
    yrs = len(br) / 252
    cg = lambda r: ((1 + r).prod() ** (1 / yrs) - 1) * 100
    return cg(br) - cg(spy_r), float((np.log1p(br) - np.log1p(spy_r)).mean() * 25200)


def coin_tosses(D, L, ev1, ev2, tol=0.025):
    """T1 over every resolution of the year-end #10/#11 pairs whose market caps are within `tol` (both known): each
    swap removes the #10 stock's U1 events of the next year and adds the #11 stock's (from U2). Returns the pairs that
    change the event set and the T1 values of all 2^k combinations."""
    pairs = []
    for y, g in L.groupby("year_end"):
        a, b = g[g["rank"] == 10], g[g["rank"] == 11]
        if len(a) and len(b):
            ca, cb = float(a.mcap_bn.iloc[0]), float(b.mcap_bn.iloc[0])
            if ca > 0 and cb > 0 and abs(ca / cb - 1) < tol:
                pairs.append((int(y) + 1, a.symbol.iloc[0], b.symbol.iloc[0], ca, cb))
    T = len(D["cal"])
    base_s, base_c = np.zeros(T + 1), np.zeros(T + 1)
    for e in ev1:
        x, c = contribution(D, e)
        base_s += x
        base_c += c
    deltas = []
    for y, s10, s11, ca, cb in pairs:
        ds, dc = np.zeros(T + 1), np.zeros(T + 1)
        for e in ev1:
            if e["sym"] == s10 and e["date"].year == y:
                x, c = contribution(D, e)
                ds -= x
                dc -= c
        for e in ev2:
            if e["sym"] == s11 and e["date"].year == y:
                x, c = contribution(D, e)
                ds += x
                dc += c
        if np.any(ds) or np.any(dc):
            deltas.append(((y, s10, s11, ca, cb), ds, dc))
    vals = []
    for mask in range(2 ** len(deltas)):
        x, c = base_s.copy(), base_c.copy()
        for bit, (_, ds, dc) in enumerate(deltas):
            if mask >> bit & 1:
                x += ds
                c += dc
        vals.append(ann(book_from(D, x, c)[0]))
    return [d[0] for d in deltas], np.array(vals)


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dv-parquet", default=None, help="Johnbrick prices.parquet (close and volume) for U6")
    ap.add_argument("--quick", action="store_true", help="fewer bootstrap draws (development only)")
    args = ap.parse_args()
    global N_BOOT, N_RC
    if args.quick:
        N_BOOT, N_RC = 1000, 200
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    lines = []

    def say(s=""):
        print(s, flush=True)
        lines.append(s)

    D = load_data()
    data, cal, rc = D["data"], D["cal"], D["rc"]
    spy_r = D["spy"].close.pct_change().reindex(cal).fillna(0.0)
    u1, u2, u4, missing, L = load_lists(data)
    ranks = rank_of(L)
    years = list(range(START.year, D["end"].year + 1))
    U = {"U1": Universe("year", by_year=u1, name="top 10 by market cap (prior year-end)"),
         "U2": Universe("year", by_year=u2, name="top 20 by market cap (prior year-end)"),
         "U3": Universe("interval", mem=D["mem"], name="every S&P 500 member on the day"),
         "U4": Universe("year", by_year=u4, name="tech names in the top 20"),
         "U5": Universe("always", syms=MAG7, name="today's Magnificent 7 (hindsight, biased)")}
    dv_info = None
    if args.dv_parquet:
        u6, dv_info = dollar_volume_universe(args.dv_parquet, D["mem"], years)
        U["U6"] = Universe("year", by_year=u6, name="top 10 by median dollar volume (prior year)")

    say("MEGA-CAP DIP STUDY (pre-registration: analysis_2026/MEGACAP_DIP_PREREG.md)")
    say(f"sample {cal[0].date()}..{cal[-1].date()} ({len(cal)} days); {len(data)} price series after the quality filter "
        f"({len(D['dropped'])} dropped or cut); rule: {THR:.0%} below the {LOOK}-day high, buy next open, hold {HOLD} "
        f"calendar days, {COST:.2%} per side")
    if len(missing):
        say(f"list names without a price series (dropped): {len(missing)}")
        for r in missing.itertuples():
            say(f"  {r.year_end} #{r[2]} {r.company} ({r.symbol})")
    if D["dups"]:
        say(f"predecessor files dropped because they carry their successor's prices (audit): "
            + "; ".join(f"{k} {v}" for k, v in sorted(D["dups"].items())))
    say("U3 coverage, members with a price series on the first trading day of the year (audit: most companies that "
        "died by 2001 have no prices, so U3 1996-2001 is close to a survivors-to-2001 sample): "
        + ", ".join(f"{y} {k}/{n}" for y, n, k in coverage(D)))
    say()

    cache = {}
    EV, BOOK, TAB = {}, {}, {}
    for u, UU in U.items():
        EV[u] = find_events(D, UU, cache=cache)
        BOOK[u] = book(D, EV[u])
        TAB[u] = event_table(D, EV[u], ranks=ranks if u in ("U1", "U2", "U4") else None)
        TAB[u].to_csv(OUT / f"events_{u}.csv", index=False)
        log_n = (BOOK[u][2] > 0).mean()
        say(f"{u} {UU.name}: {len(EV[u])} events, {int(TAB[u].complete.sum())} with a complete window; an event "
            f"position is open on {log_n:.0%} of days")

    # ---------------- primary tests
    say()
    say("PRIMARY TESTS: dip book minus SPY, annualised mean daily excess (stationary bootstrap, block 250, "
        f"{N_BOOT} draws, one-sided, Holm over T1-T3)")
    prim, ps = {}, {}
    for T_, u in (("T1", "U1"), ("T2", "U2"), ("T3", "U3")):
        ex, br, _ = BOOK[u]
        bm = boot_mean(ex.to_numpy(), n=N_BOOT)
        halves = {h: ann(ex.loc[a:b]) for h, a, b in HALVES}
        cagr_gap, log_ex = compounded(br, spy_r)
        prim[T_] = {"universe": u, "excess_%/yr": ann(ex), "p": bm["p"], "boot_sd_%/yr": bm["sd"] * 25200,
                    "mde80_%/yr": 2.49 * bm["sd"] * 25200, "mde80_holm_%/yr": 2.97 * bm["sd"] * 25200,
                    "cagr_minus_spy_%/yr": cagr_gap, "mean_log_excess_%/yr": log_ex,
                    **{f"excess_{h}": v for h, v in halves.items()}}
        ps[T_] = bm["p"]
    hp = holm(ps)
    slot_res = {}
    for u in U:
        v, after, skipped, taken = slot_portfolio(D, EV[u], ranks=ranks)
        v0, _, skipped0, taken0 = slot_portfolio(D, EV[u], ranks=ranks, tax=False)
        if (skipped0, taken0) != (skipped, taken):
            raise AssertionError(f"{u}: the taxed and untaxed 10-slot runs took different trades")
        spy_v = D["spy"].close.reindex(cal) / D["spy"].close.loc[cal[0]]   # bought at the same close (audit fix)
        yrs = len(cal) / 252
        spy_after = spy_v.iloc[-1] - LT_RATE * (spy_v.iloc[-1] - 1)
        r0 = v0.pct_change().fillna(0.0)
        r1 = v.pct_change().fillna(0.0)
        rs = spy_v.pct_change().fillna(0.0)
        slot_res[u] = {"taken": taken, "skipped": skipped, **{f"pre_{k}": x for k, x in perf(r0, rc).items()},
                       "after_tax_CAGR_%": (after ** (1 / yrs) - 1) * 100,
                       **{f"taxed_{k}": x for k, x in perf(r1, rc).items() if k in ("Sharpe", "maxDD_%")},
                       "spy_pre_CAGR_%": (spy_v.iloc[-1] ** (1 / yrs) - 1) * 100,
                       "spy_after_tax_CAGR_%": (spy_after ** (1 / yrs) - 1) * 100,
                       "spy_maxDD_%": perf(rs, rc)["maxDD_%"], "spy_Sharpe": perf(rs, rc)["Sharpe"],
                       "after_tax_beats_spy": bool(after > spy_after)}
    pd.DataFrame(slot_res).T.to_csv(OUT / "slot10.csv")
    rows = []
    for T_, d in prim.items():
        d["p_holm"] = hp[T_]
        s = slot_res[d["universe"]]
        d["slot10_after_tax_beats_spy"] = s["after_tax_beats_spy"]
        d["PASS"] = bool(d["p_holm"] < 0.05 and all(d[f"excess_{h}"] > 0 for h, _, _ in HALVES)
                         and s["after_tax_beats_spy"])
        rows.append({"test": T_, **d})
        say(f"  {T_} {d['universe']}: excess {d['excess_%/yr']:+.2f}%/yr, p {d['p']:.4f}, Holm p {d['p_holm']:.4f}; "
            f"halves {d['excess_1996-2010']:+.2f} / {d['excess_2011-2026']:+.2f}; MDE80 {d['mde80_%/yr']:.2f}%/yr "
            f"({d['mde80_holm_%/yr']:.2f} at the Holm level); 10-slot after-tax beats SPY: {s['after_tax_beats_spy']} "
            f"-> {'PASS' if d['PASS'] else 'FAIL'}")
        say(f"      compounded: book CAGR minus SPY CAGR {d['cagr_minus_spy_%/yr']:+.2f}%/yr, mean log excess "
            f"{d['mean_log_excess_%/yr']:+.2f}%/yr (the pre-registered statistic is the arithmetic mean)")
    pd.DataFrame(rows).to_csv(OUT / "primary_tests.csv", index=False)
    ex3 = BOOK["U3"][0].loc["2002-01-01":]
    say(f"  T3 restricted to 2002-2026 (U3 coverage about 99%; audit): excess {ann(ex3):+.2f}%/yr, p "
        f"{boot_mean(ex3.to_numpy(), n=N_BOOT)['p']:.4f}")

    # ---------------- secondary
    say()
    say("S9 10-SLOT PORTFOLIO (10% of value per event from SPY, at most 10 open; tax LT 20% / ST 35%)")
    for u, s in slot_res.items():
        say(f"  {u}: CAGR {s['pre_CAGR_%']:.2f}% pre-tax / {s['after_tax_CAGR_%']:.2f}% after; maxDD "
            f"{s['pre_maxDD_%']:.1f}% ({s['taxed_maxDD_%']:.1f}% taxed); Sharpe {s['pre_Sharpe']:.3f} "
            f"({s['taxed_Sharpe']:.3f} taxed); taken {s['taken']}, skipped {s['skipped']} | SPY "
            f"{s['spy_pre_CAGR_%']:.2f}% / {s['spy_after_tax_CAGR_%']:.2f}%, maxDD {s['spy_maxDD_%']:.1f}%, Sharpe "
            f"{s['spy_Sharpe']:.3f}")

    say()
    say("S8 CAPM (monthly, Newey-West 12) and S11 eras: dip book excess %/yr")
    era_rows = []
    for u in U:
        ex, br, n = BOOK[u]
        c = capm(br, spy_r, rc)
        er = {e: ann(ex.loc[a:b]) for e, a, b in ERAS}
        era_rows.append({"universe": u, "excess_%/yr": ann(ex), **c, **er, "days_open_%": float((n > 0).mean() * 100)})
        say(f"  {u}: excess {ann(ex):+.2f}%/yr; alpha {c['alpha_%/yr']:+.2f}%/yr (t {c['alpha_t']:.2f}), beta "
            f"{c['beta']:.2f}; eras " + ", ".join(f"{k} {v:+.2f}" for k, v in er.items()))
    pd.DataFrame(era_rows).to_csv(OUT / "eras_capm.csv", index=False)

    say()
    say("S10 EVENTS with a complete window: 12-month return minus SPY's (bootstrap by calendar quarter)")
    ev_rows = []
    for u in U:
        T = TAB[u][TAB[u].complete].copy()
        if T.empty:
            continue
        T["q"] = pd.to_datetime(T.trigger).dt.to_period("Q").astype(str)
        cb = cluster_boot(T, "excess", "q")
        T["y"] = pd.to_datetime(T.trigger).dt.year
        cy = cluster_boot(T, "excess", "y")
        ev_rows.append({"universe": u, "n": len(T), "mean_ret": T.ret.mean(), "mean_spy": T.spy_ret.mean(),
                        "mean_excess": cb["mean"], "ci_lo": cb["lo"], "ci_hi": cb["hi"], "p_le0": cb["p_le0"],
                        "ci_lo_year": cy["lo"], "ci_hi_year": cy["hi"],
                        "median_excess": T.excess.median(), "hit_vs_spy": (T.excess > 0).mean(),
                        "hit_abs": (T.ret > 0).mean(), "median_further_drop": T.further_drop.median(),
                        "worst_ret": T.ret.min(), "quarters": cb["clusters"]})
        say(f"  {u}: n {len(T)} ({cb['clusters']} quarters); mean {T.ret.mean():+.1%} vs SPY {T.spy_ret.mean():+.1%}; "
            f"excess {cb['mean']:+.1%} [{cb['lo']:+.1%}, {cb['hi']:+.1%}; by year {cy['lo']:+.1%}, {cy['hi']:+.1%}]; "
            f"median excess {T.excess.median():+.1%}; "
            f"beat SPY {(T.excess > 0).mean():.0%}; median further drop {T.further_drop.median():.1%}; worst "
            f"{T.ret.min():+.1%}")
    pd.DataFrame(ev_rows).to_csv(OUT / "event_stats.csv", index=False)

    say()
    say("S1 TIMING vs OWNING THE SAME STOCKS: event 12-month excess minus 200 random entries in the same stock and "
        "universe (bootstrap by calendar year); and the universe held all the time vs SPY")
    pl_rows = []
    for u in ("U1", "U2", "U3", "U4", "U5"):
        P = placebo(D, EV[u], U[u])
        if P.empty:
            continue
        P.to_csv(OUT / f"placebo_{u}.csv", index=False)
        cb = cluster_boot(P, "diff", "year")
        row = {"universe": u, "n": len(P), "event_excess": P.event_excess.mean(), "placebo_excess": P.placebo_excess.mean(),
               "all_days_excess": P.all_days_excess.mean(), "diff": cb["mean"], "lo": cb["lo"], "hi": cb["hi"],
               "p_le0": cb["p_le0"]}
        held_by_year = {"U1": u1, "U2": u2, "U4": u4}.get(u)
        if u == "U3":
            held_by_year = {y: [s for s in D["mem"][(D["mem"].start <= max(pd.Timestamp(f"{y}-01-01"), D["mem"].start.min()))
                                                    & (D["mem"].end.isna() | (D["mem"].end >= pd.Timestamp(f"{y}-01-01")))]
                                .symbol.unique() if s in data] for y in years}
        if u == "U5":
            held_by_year = {y: [s for s in MAG7 if s in data and (data[s].index < pd.Timestamp(f"{y}-01-01")).sum() >= LOOK]
                            for y in years}
        if held_by_year is not None:
            hr = held_universe(D, held_by_year).reindex(cal).fillna(0.0)
            row["held_minus_spy_%/yr"] = ann(hr - spy_r)
        pl_rows.append(row)
        say(f"  {u}: n {len(P)}; event {P.event_excess.mean():+.1%} vs placebo {P.placebo_excess.mean():+.1%} (exact "
            f"all-days mean {P.all_days_excess.mean():+.1%}) -> timing {cb['mean']:+.1%} [{cb['lo']:+.1%}, {cb['hi']:+.1%}]"
            + (f"; universe held all the time minus SPY {row['held_minus_spy_%/yr']:+.2f}%/yr"
               if "held_minus_spy_%/yr" in row else ""))
    pd.DataFrame(pl_rows).to_csv(OUT / "placebo.csv", index=False)

    say()
    say("S2 TODAY'S MAGNIFICENT 7 (hindsight). Events since the name was coined (2023-04-01):")
    T5 = TAB["U5"]
    for r in T5[pd.to_datetime(T5.trigger) >= COINED].itertuples():
        say(f"  {r.sym} {r.trigger} (dd {r.dd:.0%}): {r.ret:+.1%} vs SPY {r.spy_ret:+.1%}"
            + ("" if r.complete else " (window not complete)"))

    say()
    say("S7 TOP-10 EVENTS (U1), complete or not:")
    for r in TAB["U1"].itertuples():
        say(f"  {r.trigger} {r.sym:<14} #{r.rank}: {r.ret:+7.1%} vs SPY {r.spy_ret:+7.1%} (excess {r.excess:+7.1%}; "
            f"further drop {r.further_drop:+.0%}){'' if r.complete else ' *open'}")

    say()
    say(f"S3 GRID ({len(GRID_THR)} thresholds x {len(GRID_REF)} references x {len(GRID_HOLD)} holds) with White's "
        f"reality check vs SPY ({N_RC} draws)")
    grid_rows, rc_rows = [], []
    for u in ("U1", "U2", "U3"):
        cols, names = [], []
        for thr in GRID_THR:
            for ref in GRID_REF:
                ev = find_events(D, U[u], thr=thr, ref=ref, cache=cache)
                for hn, h in GRID_HOLD.items():
                    ex = book(D, ev, hold=h)[0]
                    cols.append(ex.to_numpy())
                    names.append((thr, ref, hn))
                    grid_rows.append({"universe": u, "thr": thr, "ref": ref, "hold": hn, "events": len(ev),
                                      "excess_%/yr": ann(ex), **{f"excess_{h_}": ann(ex.loc[a:b]) for h_, a, b in HALVES}})
        E = np.column_stack(cols)
        r = reality_check(E, n=N_RC)
        best = names[r["argmax"]]
        rc_rows.append({"universe": u, "cells": len(names), "best": f"{best[0]:.0%} {best[1]} {best[2]}",
                        "best_excess_%/yr": r["V_obs_%/yr"], "p_rc": r["p_rc"]})
        say(f"  {u}: best cell {best[0]:.0%} below the {best[1]} high, hold {best[2]}: {r['V_obs_%/yr']:+.2f}%/yr; "
            f"reality-check p {r['p_rc']:.3f}")
    G = pd.DataFrame(grid_rows)
    G.to_csv(OUT / "grid.csv", index=False)
    pd.DataFrame(rc_rows).to_csv(OUT / "reality_check.csv", index=False)
    for u in ("U1", "U2", "U3"):
        g = G[(G.universe == u) & (G.ref == "52w")].pivot(index="thr", columns="hold", values="excess_%/yr")
        say(f"  {u}, 52-week high, excess %/yr by threshold (rows) and hold (columns):")
        say("    " + g[list(GRID_HOLD)].round(2).to_string().replace("\n", "\n    "))

    say()
    say("ROBUSTNESS (audit additions; none changes the pre-registered verdict)")
    for lab, kw in (("entry without SPY's overnight move (the pre-registration's literal close/open)", {"overnight": False}),
                    ("exit strictly after the one-year anniversary (long-term in leap years too)", {"hold": "anniv"})):
        vals = []
        for u in ("U1", "U2", "U3"):
            ex = book(D, EV[u], **kw)[0]
            vals.append(f"{u} {ann(ex):+.2f} (p {boot_mean(ex.to_numpy(), n=N_BOOT)['p']:.3f})")
        say(f"  {lab}: " + ", ".join(vals))
    pairs, vals = coin_tosses(D, L, EV["U1"], EV["U2"])
    say(f"  T1 across the {len(vals)} resolutions of the {len(pairs)} event-changing #10/#11 near-ties (caps within 2.5%): "
        f"min {vals.min():+.2f}, median {np.median(vals):+.2f}, max {vals.max():+.2f}%/yr; {np.mean(vals > 0):.0%} above "
        f"zero (pairs: " + "; ".join(f"{y - 1} {a}/{b}" for y, a, b, _, _ in pairs) + ")")
    say("  Hold length, 25% below the 52-week high (excess %/yr, p, halves; Holm across U1-U3 at each hold; 10-slot "
        "after-tax CAGR vs SPY for U1/U2). Not pre-registered; the grid's reality check covers this search:")
    hold_rows = []
    for h in (366, 548, 731, 913, 1096, 1461, 1827):
        res = {}
        for u in ("U1", "U2", "U3"):
            ex = book(D, EV[u], hold=h)[0]
            res[u] = (ann(ex), boot_mean(ex.to_numpy(), n=N_BOOT)["p"], ann(ex.loc[:"2010-12-31"]),
                      ann(ex.loc["2011-01-01":]))
        hh = holm({u: res[u][1] for u in res})
        line = []
        for u in ("U1", "U2", "U3"):
            e_, p_, h1, h2 = res[u]
            row = {"hold_days": h, "universe": u, "excess_%/yr": e_, "p": p_, "p_holm": hh[u], "half1": h1, "half2": h2}
            txt = f"{u} {e_:+.2f} (p {p_:.3f}, Holm {hh[u]:.3f}, {h1:+.1f}/{h2:+.1f})"
            if u in ("U1", "U2"):
                _, after_h, _, _ = slot_portfolio(D, EV[u], ranks=ranks, hold=h)
                row["slot_after_tax_CAGR_%"] = (after_h ** (1 / (len(cal) / 252)) - 1) * 100
                txt += f" slot {row['slot_after_tax_CAGR_%']:.2f}"
            hold_rows.append(row)
            line.append(txt)
        say(f"    {h:>4}d: " + "; ".join(line))
    pd.DataFrame(hold_rows).to_csv(OUT / "hold_curve.csv", index=False)
    say(f"    (SPY after-tax CAGR {slot_res['U1']['spy_after_tax_CAGR_%']:.2f}%)")

    say()
    say("S6 INDEX DIPS: 12-month total return after the index closes 25% below its 52-week high (vs every 12-month "
        "window)")
    b = D["base"]
    sp_i, sp_s = index_dips(b["sp_px"], b["sp"])
    qqq = pd.read_csv(ROOT / "data" / "etf" / "QQQ.csv", index_col=0, parse_dates=True)["close"]
    qq_i, qq_s = index_dips(qqq, qqq)
    idx_rows = []
    for nm, ev, st in (("S&P 500 1928-2026", sp_i, sp_s), ("QQQ 1999-2026", qq_i, qq_s)):
        say(f"  {nm}: {len(ev)} events, mean {ev.fwd.mean():+.1%}, median {ev.fwd.median():+.1%}, up "
            f"{(ev.fwd > 0).mean():.0%} | all windows mean {st['mean_all']:+.1%}, median {st['median_all']:+.1%}, up "
            f"{st['hit_all']:.0%}")
        for r in ev.itertuples():
            idx_rows.append({"index": nm, "trigger": r.trigger, "dd": r.dd, "fwd_12m": r.fwd})
    pd.DataFrame(idx_rows).to_csv(OUT / "index_events.csv", index=False)

    if dv_info is not None:
        dv_info.to_csv(OUT / "dollar_volume_members.csv", index=False)
        say()
        say(f"U6 note: members without volume in the parquet (CRSP-sourced dead companies), per year: "
            f"{int(dv_info.without_volume.min())}-{int(dv_info.without_volume.max())}; they cannot enter U6, a "
            "survivorship bias in this proxy")

    say()
    say(f"runtime {time.time() - t0:.0f}s")
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
