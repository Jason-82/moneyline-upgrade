"""
Ten theory-driven strategies (pre-registered in analysis_2026/THEORY_PREREG.md, commit
93bff74, before any run). One function per strategy; shared data, costs, metrics and a
stationary block bootstrap for the Sharpe-ratio test.

    python -m analysis_2026.theory_strategies

Conventions (as pre-registered; where the pre-registration allowed a choice, the more
conservative one is used):
  - Weights are decided at a day's close. For Ken French and ETF data the trade happens
    at the NEXT close, so the new weight earns from the second day after the signal (lag
    1). Calendar rules (S6, S7) need no lag. Crypto trades at the daily close and earns
    the next day (lag 0).
  - Costs per side on |change in weight|: market/ETF 0.02%, stocks 0.03%, crypto 0.10%
    (BTC/ETH) / 0.15% (others), perpetuals 0.05%.
  - Cash earns T-bills (Ken French RF; the approximate table in screener/strictness.py
    after 2026-06).
  - Fractional target weights are held constant between decisions (daily rebalanced).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screener.strictness import TBILL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis_2026" / "results_theory"
ST, LT = 0.35, 0.20


# ------------------------------------------------------------------ data

def ff_daily():
    d = pd.read_csv(ROOT / "data" / "ff" / "ff3_daily.csv", parse_dates=["date"]).set_index("date")
    return d


def rf_for(index, per_year=252):
    ff = ff_daily().RF
    s = ff.reindex(index).ffill()
    late = index > ff.index[-1]
    if late.any():
        s[late] = [TBILL.get(d.year, 2.0) / 100 / per_year for d in index[late]]
    if per_year == 365:                                     # calendar-day series (crypto)
        s = pd.Series([TBILL.get(d.year, 2.0) / 100 / 365 for d in index], index=index)
    return s.fillna(0.0)


def etf(name):
    d = pd.read_csv(ROOT / "data" / "etf" / f"{name}.csv", parse_dates=["date"]).set_index("date").sort_index()
    return d


# ------------------------------------------------------------------ engine & stats

def run_weights(w_target, r, rf, cost, lag=1, borrow_spread=0.005, ppy=252):
    """w_target: target weight decided at each day's close (NaN = keep previous).
    Returns the strategy's daily returns."""
    w = w_target.ffill().fillna(0.0)
    w_eff = w.shift(1 + lag).fillna(0.0)
    turn = w_eff.diff().abs().fillna(w_eff.abs())
    borrow = np.clip(w_eff - 1, 0, None) * borrow_spread / ppy
    return w_eff * r + (1 - w_eff) * rf - cost * turn - borrow


def run_calendar(w_eff, r, rf, cost):
    """w_eff already aligned to the return day (calendar known in advance)."""
    turn = w_eff.diff().abs().fillna(w_eff.abs())
    return w_eff * r + (1 - w_eff) * rf - cost * turn


def periods_per_year(index):
    """Actual bars per calendar year (Ken French data has Saturday sessions before 1953,
    so a fixed 252 would understate annualised figures - audit fix)."""
    yrs = (index[-1] - index[0]).days / 365.25
    return len(index) / yrs if yrs > 0 else 252


def metrics(r, rf, ppy=252, active=True):
    r = r.dropna(); rf = rf.reindex(r.index).fillna(0)
    ppy = periods_per_year(r.index)
    eq = (1 + r).cumprod(); yrs = len(r) / ppy
    ex = r - rf
    out = {"start": str(r.index[0].date()), "end": str(r.index[-1].date()),
           "CAGR_%": (eq.iloc[-1] ** (1 / yrs) - 1) * 100, "vol_%": r.std() * np.sqrt(ppy) * 100,
           "Sharpe": ex.mean() / ex.std() * np.sqrt(ppy) if ex.std() > 0 else np.nan,
           "maxDD_%": float((eq / eq.cummax() - 1).min() * 100),
           "worst_year_%": float(((1 + r).groupby(r.index.year).prod() - 1).min() * 100)}
    if active:                                   # taxed every year at 35%, losses carried
        v, carry = 1.0, 0.0
        for _, x in r.groupby(r.index.year):
            g = v * ((1 + x).prod() - 1); net = g + carry
            tax = ST * net if net > 0 else 0.0; carry = 0.0 if net > 0 else net; v += g - tax
    else:                                        # buy & hold: taxed once at 20% at the end
        m = eq.iloc[-1]; v = m - LT * (m - 1) if m > 1 else m
    out["CAGR_after_tax_%"] = (v ** (1 / yrs) - 1) * 100 if v > 0 else -100.0
    return out


def fmt(d):
    """Dict for the printed summary, floats rounded (np.float64 reprs are noisy)."""
    return {k: (fmt(v) if isinstance(v, dict) else round(float(v), 4) if isinstance(v, (float, np.floating)) else v)
            for k, v in d.items()}


def sharpe(x, rf):
    e = x - rf
    return e.mean() / e.std()


def boot_sharpe_diff(rs, rb, rf, ppy=252, block=250, n=2000, seed=0):
    """Stationary block bootstrap of the annualised Sharpe gain (strategy - benchmark).
    One-sided p = share of draws with gain <= 0."""
    j = pd.concat([rs, rb, rf], axis=1, sort=True).dropna()
    ppy = periods_per_year(j.index)
    a, b, f = (j.iloc[:, k].to_numpy() for k in range(3))
    T = len(a); rng = np.random.default_rng(seed)
    obs = (sharpe(pd.Series(a), pd.Series(f)) - sharpe(pd.Series(b), pd.Series(f))) * np.sqrt(ppy)
    p_new = 1.0 / block; diffs = np.empty(n)
    ea_all, eb_all = a - f, b - f
    for k in range(n):
        # stationary bootstrap: geometric block lengths, uniform block starts, wrap around
        nb = int(T * p_new * 3) + 10
        lens = rng.geometric(p_new, size=nb)
        while lens.sum() < T:
            lens = np.r_[lens, rng.geometric(p_new, size=nb)]
        starts = rng.integers(T, size=len(lens))
        offs = np.arange(lens.sum()) - np.repeat(np.cumsum(lens) - lens, lens)
        idx = (np.repeat(starts, lens) + offs)[:T] % T
        ea, eb = ea_all[idx], eb_all[idx]
        diffs[k] = (ea.mean() / ea.std() - eb.mean() / eb.std()) * np.sqrt(ppy)
    # (percentile bootstrap of the difference; one-sided p = share of draws <= 0)
    return {"dSharpe": float(obs), "ci_lo": float(np.percentile(diffs, 2.5)), "ci_hi": float(np.percentile(diffs, 97.5)),
            "p_one_sided": float((diffs <= 0).mean())}


def sub_dsharpe(rs, rb, rf, start, end=None, ppy=252):
    x = pd.concat([rs, rb, rf], axis=1, sort=True).dropna().loc[start:end]
    ppy = periods_per_year(x.index)
    return float((sharpe(x.iloc[:, 0], x.iloc[:, 2]) - sharpe(x.iloc[:, 1], x.iloc[:, 2])) * np.sqrt(ppy))


def nw_t(x, lags=20):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x); u = x - x.mean()
    s = u @ u / n
    for l in range(1, lags + 1):
        s += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    return float(x.mean() / np.sqrt(s / n))


def month_end_mask(index):
    s = pd.Series(index, index=index)
    me = s.groupby([index.year, index.month]).transform("max")
    return pd.Series(index == me.values, index=index)


# ------------------------------------------------------------------ strategies

def s1_vol_managed(r, rf, cap=1.0, cost=0.0002, lag=1):
    rv = r.rolling(21).std() * np.sqrt(252)
    me = month_end_mask(r.index)
    rv_me = rv[me]
    target = rv_me.expanding().mean()
    w = (target / rv_me).clip(upper=cap)
    wt = pd.Series(np.nan, index=r.index); wt[w.index] = w
    return run_weights(wt, r, rf, cost, lag)


def s2_trend_sma(r, rf, cost=0.0002, lag=1, months=10):
    idx = (1 + r).cumprod()
    me = month_end_mask(r.index)
    m = idx[me]
    sma = m.rolling(months).mean()
    sig = (m > sma).astype(float).where(sma.notna())
    wt = pd.Series(np.nan, index=r.index); wt[sig.index] = sig
    return run_weights(wt, r, rf, cost, lag)


def s3_dual_momentum(cost=0.0002, lag=1):
    # signals need only SPY and EFA history; IEF only has to exist to be held (audit fix:
    # the first version waited for 12 months of IEF and sat in cash until Aug 2003)
    px = pd.DataFrame({k: etf(k).close for k in ("SPY", "EFA", "IEF")})
    px = px[px[["SPY", "EFA"]].notna().all(axis=1)]
    r = px.pct_change(fill_method=None).fillna(0); rf = rf_for(px.index)
    me = month_end_mask(px.index)
    rf_idx = (1 + rf).cumprod()
    W = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    dates = px.index[me]
    for d in dates:
        pos = px.index.get_loc(d)
        back = px.index[px.index <= d - pd.DateOffset(months=12)]
        if len(back) == 0:
            continue
        b = back[-1]
        r12 = px.loc[d, ["SPY", "EFA"]] / px.loc[b, ["SPY", "EFA"]] - 1
        rf12 = rf_idx.loc[d] / rf_idx.loc[b] - 1
        w = pd.Series(0.0, index=px.columns)
        if r12["SPY"] > rf12:
            w["SPY" if r12["SPY"] >= r12["EFA"] else "EFA"] = 1.0
        else:
            w["IEF"] = 1.0
        W.loc[d] = w
    W = W.ffill().fillna(0.0)
    We = W.shift(1 + lag).fillna(0.0)
    turn = We.diff().abs().sum(axis=1).fillna(We.abs().sum(axis=1))
    out = (We * r).sum(axis=1) + (1 - We.sum(axis=1)) * rf - cost * turn
    return out, r["SPY"], rf


def load_sp_universe():
    from screener.data import from_csv_folder, quality_filter
    sp, _ = quality_filter(from_csv_folder(ROOT / "data" / "universe_pit_all"), keep_collapsed=True)
    mem = pd.read_csv(ROOT / "data" / "universe_pit_all" / "members.csv", parse_dates=["start", "end"])
    mem["symbol"] = mem.symbol.str.upper()
    close = pd.DataFrame({k: v.close for k, v in sp.items() if k != "SPY"}).sort_index()
    close = close.loc["1999-01-01":"2026-09-30"]
    # returns across trading halts are kept (audit fix: SIVB/SBNY 2023, HealthSouth 2003):
    # compare with the last available close; days without a print stay NaN
    rets = close.ffill().pct_change(fill_method=None)
    rets[close.isna()] = np.nan
    return rets, mem


def xs_portfolio(rets, mem, score_fn, pick, freq, cost=0.0003, lag=1, start="2001-01-01"):
    """Generic cross-sectional stock strategy over point-in-time S&P members."""
    idx = rets.index
    if freq == "Q":
        reb = month_end_mask(idx) & pd.Series(idx.month % 3 == 0, index=idx)
    else:
        reb = month_end_mask(idx)
    reb_dates = idx[reb & (idx >= pd.Timestamp(start) - pd.Timedelta(days=40))]
    R = rets.to_numpy(); cols = np.array(rets.columns)
    held_s = np.zeros(len(idx), dtype=object); held_b = np.zeros(len(idx), dtype=object)
    cur_s = cur_b = None
    w_s_prev = pd.Series(dtype=float); w_b_prev = pd.Series(dtype=float)
    cost_s = np.zeros(len(idx)); cost_b = np.zeros(len(idx))
    reb_pos = {idx.get_loc(d): d for d in reb_dates}
    for pos in range(len(idx)):
        if pos - 1 - lag in reb_pos:                          # trade lands: effective from this day
            d = reb_pos[pos - 1 - lag]
            on = set(mem[(mem.start <= d) & (mem.end.isna() | (mem.end >= d))].symbol)
            hist = rets.iloc[max(0, idx.get_loc(d) - 251):idx.get_loc(d) + 1]
            ok = [c for c in rets.columns if c in on and hist[c].notna().sum() >= 240 and pd.notna(rets.iloc[idx.get_loc(d)][c])]
            if len(ok) >= 50:
                sc = score_fn(hist[ok])
                k = max(1, int(round(len(ok) * 0.2)))
                chosen = list(sc.sort_values(ascending=(pick == "low")).index[:k])
                ws = pd.Series(1 / len(chosen), index=chosen); wb = pd.Series(1 / len(ok), index=ok)
                cost_s[pos] = cost * ws.subtract(w_s_prev, fill_value=0).abs().sum()
                cost_b[pos] = cost * wb.subtract(w_b_prev, fill_value=0).abs().sum()
                w_s_prev, w_b_prev = ws, wb
                cur_s, cur_b = chosen, ok
        held_s[pos] = cur_s; held_b[pos] = cur_b
    col_ix = {c: i for i, c in enumerate(cols)}
    rs = np.full(len(idx), np.nan); rb = np.full(len(idx), np.nan)
    for pos in range(len(idx)):
        if held_s[pos]:
            xs = R[pos, [col_ix[c] for c in held_s[pos]]]; xb = R[pos, [col_ix[c] for c in held_b[pos]]]
            rs[pos] = np.nanmean(xs) - cost_s[pos]; rb[pos] = np.nanmean(xb) - cost_b[pos]
    rs = pd.Series(rs, index=idx).loc[start:]; rb = pd.Series(rb, index=idx).loc[start:]
    return rs.dropna(), rb.dropna()


def s4_low_vol(rets, mem):
    return xs_portfolio(rets, mem, lambda h: h.std(), "low", "Q")


def s5_momentum(rets, mem, freq="M"):
    def score(h):
        g = (1 + h.fillna(0)).cumprod()
        return g.iloc[-22] / g.iloc[0] - 1                    # months t-12..t-2 (skip the last ~21 days)
    return xs_portfolio(rets, mem, score, "high", freq)


def tom_weights(index):
    s = pd.Series(index, index=index)
    ym = index.year * 12 + index.month
    w = np.zeros(len(index))
    last = s.groupby(ym).transform("max").to_numpy() == index.to_numpy()
    rank = s.groupby(ym).cumcount().to_numpy()                # 0-based trading day in month
    w[last] = 1.0
    w[rank <= 2] = 1.0                                        # first 3 trading days
    return pd.Series(w, index=index)


def s6_tom(r, rf, cost=0.0002):
    return run_calendar(tom_weights(r.index), r, rf, cost)


def s7_halloween(r, rf, cost=0.0002):
    w = pd.Series(np.where(np.isin(r.index.month, [11, 12, 1, 2, 3, 4]), 1.0, 0.0), index=r.index)
    return run_calendar(w, r, rf, cost)


def crypto_daily(sym):
    from analysis_2026.altcoins import load_crypto
    return load_crypto()[sym]


def s8_crypto_trend_vol(cost=0.0010):
    from analysis_2026.moneyline_ref import moneyline
    out_s, out_b, out_h = [], [], []
    for sym in ("BTC", "ETH"):
        d = crypto_daily(sym)
        d = d[~d.index.duplicated()]
        r = d.close.pct_change().fillna(0)
        rf = rf_for(d.index, 365)
        green = moneyline(d).green.astype(float)
        rv = r.rolling(20).std() * np.sqrt(365)
        target = rv.expanding(min_periods=180).median()
        raw = green * (target / rv).clip(upper=1.0)
        w = np.zeros(len(raw)); cur = 0.0; g_prev = 0.0
        for i, (x, g) in enumerate(zip(raw.to_numpy(), green.to_numpy())):
            if np.isnan(x):
                x = g                                            # before the target exists: plain signal
            if g != g_prev or abs(x - cur) > 0.10:
                cur = x
            w[i] = cur; g_prev = g
        ws = pd.Series(w, index=d.index)
        out_s.append(run_weights(ws, r, rf, cost, lag=0, ppy=365).rename(sym))
        out_b.append(run_weights(green, r, rf, cost, lag=0, ppy=365).rename(sym))
        out_h.append(r.rename(sym))
    S = pd.concat(out_s, axis=1).loc["2018-01-01":"2026-09-30"].mean(axis=1)
    B = pd.concat(out_b, axis=1).loc["2018-01-01":"2026-09-30"].mean(axis=1)
    H = pd.concat(out_h, axis=1).loc["2018-01-01":"2026-09-30"].mean(axis=1)
    return S, B, H, rf_for(S.index, 365)


def s9_funding_carry(positive_only=False):
    legs = []
    for sym in ("BTC", "ETH"):
        f = pd.read_csv(ROOT / "data" / "crypto_funding" / f"{sym}.csv", parse_dates=["time"]).set_index("time").rate.astype(float)
        daily = f.groupby(f.index.normalize()).sum()
        idx = pd.date_range("2019-10-01", "2026-09-30", freq="D")
        daily = daily.reindex(idx).fillna(0.0)
        rf = rf_for(idx, 365)
        on = pd.Series(1.0, index=idx)
        if positive_only:
            on = (daily.rolling(7).sum().shift(1) > 0).astype(float)    # yesterday's 7-day funding
        open_cost = 0.0010 + 0.0005                                   # spot + perp, one side each
        turn = on.diff().abs().fillna(on.iloc[0])
        first_of_month = pd.Series(idx.day == 1, index=idx).astype(float)
        ret_notional = on * daily - turn * open_cost - on * first_of_month * 0.0005
        ret_capital = ret_notional / 1.25 + (1 - on) * rf             # out of position -> T-bills
        legs.append(ret_capital)
    r = pd.concat(legs, axis=1).mean(axis=1)
    r.iloc[-1] -= 0.0015 / 1.25                                       # close both legs at the end
    return r, rf_for(r.index, 365)


def s10_crypto_xs_momentum(cost=0.0015):
    from analysis_2026.altcoins import load_crypto
    data = load_crypto()
    close = pd.DataFrame({k: v.close for k, v in data.items()}).sort_index()
    qv = pd.DataFrame({k: v.quote_volume for k, v in data.items()}).sort_index()
    rets = close.pct_change(fill_method=None)
    idx = rets.loc["2019-01-01":"2026-09-30"].index
    mondays = idx[idx.weekday == 0]
    hist_n = close.notna().cumsum()
    med_qv = qv.rolling(30, min_periods=20).median()
    rs, rb = pd.Series(0.0, index=idx), pd.Series(0.0, index=idx)
    prev_s = pd.Series(dtype=float); prev_b = pd.Series(dtype=float)
    for k, m in enumerate(mondays):
        dec = m - pd.Timedelta(days=1)                                # Sunday close (decision)
        if dec not in close.index:
            continue
        ok = (hist_n.loc[dec] >= 90) & close.loc[dec].notna() & med_qv.loc[dec].notna()
        cand = med_qv.loc[dec][ok].sort_values(ascending=False).index[:30]
        if len(cand) < 15:
            continue
        back = dec - pd.Timedelta(days=28)
        r28 = (close.loc[dec, cand] / close.loc[back, cand] - 1).dropna() if back in close.index else pd.Series(dtype=float)
        if len(r28) < 10:
            continue
        top = r28.sort_values(ascending=False).index[:6]
        ws = pd.Series(1 / len(top), index=top); wb = pd.Series(1 / len(cand), index=cand)
        end = mondays[k + 1] - pd.Timedelta(days=1) if k + 1 < len(mondays) else idx[-1]
        days = idx[(idx >= m) & (idx <= end)]
        rs.loc[days] = rets.loc[days, top].mean(axis=1).fillna(0).to_numpy()
        rb.loc[days] = rets.loc[days, cand].mean(axis=1).fillna(0).to_numpy()
        rs.loc[m] -= cost * ws.subtract(prev_s, fill_value=0).abs().sum()
        rb.loc[m] -= cost * wb.subtract(prev_b, fill_value=0).abs().sum()
        prev_s, prev_b = ws, wb
    first = mondays[0]
    rs, rb = rs.loc[first:], rb.loc[first:]
    return rs, rb, rf_for(rs.index, 365)


# ------------------------------------------------------------------ main

def main():
    pd.set_option("display.width", 250)
    OUT.mkdir(exist_ok=True)
    ff = ff_daily(); r_mkt, rf_ff = ff.Mkt, ff.RF
    spy = etf("SPY"); r_spy = spy.close.pct_change().fillna(0).loc["1995-01-01":"2026-09-30"]; rf_spy = rf_for(r_spy.index)
    results, primary = {}, []

    def record(key, label, rs, rb, rf, ppy, subs, bench_active=False, extra=None):
        ms, mb = metrics(rs, rf, ppy), metrics(rb, rf, ppy, active=bench_active)
        bt = boot_sharpe_diff(rs, rb, rf, ppy)
        sub = {f"{a}..{b or 'end'}": sub_dsharpe(rs, rb, rf, a, b, ppy) for a, b in subs}
        results[key] = {"label": label, "strategy": ms, "benchmark": mb, "bootstrap": bt, "sub_dSharpe": sub, **(extra or {})}
        print(f"\n[{key}] {label}\n  strategy  {fmt(ms)}\n  benchmark {fmt(mb)}\n  bootstrap {fmt(bt)}\n  sub-periods {fmt(sub)}")
        return bt["p_one_sided"], sub

    # S1
    rs = s1_vol_managed(r_mkt, rf_ff).loc["1927-01-01":]
    p, sub = record("S1", "Volatility-managed US market (cap 1.0) vs buy & hold, 1927-2026", rs, r_mkt.loc["1927-01-01":], rf_ff, 252, [("1976-01-01", None)])
    primary.append(("S1", p, all(v > 0 for v in sub.values())))
    record("S1_cap1.5", "Volatility-managed, cap 1.5 (exploratory)", s1_vol_managed(r_mkt, rf_ff, cap=1.5).loc["1927-01-01":], r_mkt.loc["1927-01-01":], rf_ff, 252, [("1976-01-01", None)])
    record("S1_SPY", "Volatility-managed SPY 1995-2026 (replication)", s1_vol_managed(r_spy, rf_spy).loc["1996-01-01":], r_spy.loc["1996-01-01":], rf_spy, 252, [("2011-01-01", None)])
    # S2
    rs = s2_trend_sma(r_mkt, rf_ff).loc["1927-06-01":]
    p, sub = record("S2", "10-month SMA trend filter on the US market vs buy & hold, 1927-2026", rs, r_mkt.loc["1927-06-01":], rf_ff, 252, [("1976-01-01", None), ("2008-01-01", None)])
    primary.append(("S2", p, all(v > 0 for v in sub.values())))
    record("S2_SPY", "10-month SMA on SPY 1996-2026 (replication)", s2_trend_sma(r_spy, rf_spy).loc["1996-01-01":], r_spy.loc["1996-01-01":], rf_spy, 252, [("2008-01-01", None)])
    # S3
    rs, rb, rf3 = s3_dual_momentum()
    rs, rb = rs.loc["2003-01-01":], rb.loc["2003-01-01":]
    p, sub = record("S3", "Dual momentum (SPY/EFA/IEF) vs SPY, 2003-2026", rs, rb, rf3, 252, [("2015-01-01", None)])
    primary.append(("S3", p, all(v > 0 for v in sub.values())))
    # S4, S5
    rets, mem = load_sp_universe()
    rs, rb = s4_low_vol(rets, mem); rf_sp = rf_for(rs.index)
    p, sub = record("S4", "Low-volatility quintile of point-in-time S&P 500 vs equal weight, 2001-2026", rs, rb, rf_sp, 252, [("2014-01-01", None)], bench_active=True)
    primary.append(("S4", p, all(v > 0 for v in sub.values())))
    rs, rb = s5_momentum(rets, mem)
    p, sub = record("S5", "12-1 momentum quintile of point-in-time S&P 500 vs equal weight, 2001-2026", rs, rb, rf_sp.reindex(rs.index).fillna(0), 252, [("2014-01-01", None)], bench_active=True)
    primary.append(("S5", p, all(v > 0 for v in sub.values())))
    rs, rb = s5_momentum(rets, mem, freq="Q")
    record("S5_quarterly", "12-1 momentum, quarterly rebalance (exploratory)", rs, rb, rf_sp.reindex(rs.index).fillna(0), 252, [("2014-01-01", None)], bench_active=True)
    # S6, S7
    rs = s6_tom(r_mkt, rf_ff).loc["1927-01-01":]
    tom = tom_weights(r_mkt.index)
    extra = {"mean_daily_TOM_%": float(r_mkt[tom == 1].mean() * 100), "mean_daily_other_%": float(r_mkt[tom == 0].mean() * 100)}
    p, sub = record("S6", "Turn of the month on the US market vs buy & hold, 1927-2026", rs, r_mkt.loc["1927-01-01":], rf_ff, 252, [("1989-01-01", None), ("2009-01-01", None)], extra=extra)
    primary.append(("S6", p, all(v > 0 for v in sub.values())))
    record("S6_SPY", "Turn of the month on SPY 1995-2026 (replication)", s6_tom(r_spy, rf_spy), r_spy, rf_spy, 252, [("2009-01-01", None)])
    rs = s7_halloween(r_mkt, rf_ff).loc["1927-01-01":]
    p, sub = record("S7", "Halloween (Nov-Apr) on the US market vs buy & hold, 1927-2026", rs, r_mkt.loc["1927-01-01":], rf_ff, 252, [("2003-01-01", None)])
    primary.append(("S7", p, all(v > 0 for v in sub.values())))
    # S8
    S, B, H, rfc = s8_crypto_trend_vol()
    p, sub = record("S8", "Crypto indicator + vol targeting vs plain indicator (BTC/ETH 50/50), 2018-2026", S, B, rfc, 365, [("2022-01-01", None)],
                    extra={"vs_buy_and_hold": boot_sharpe_diff(S, H, rfc, 365), "buy_and_hold": metrics(H, rfc, 365, active=False)})
    primary.append(("S8", p, all(v > 0 for v in sub.values())))
    # S9
    r9, rf9 = s9_funding_carry()
    ex = r9 - rf9
    t9 = nw_t(ex.to_numpy()); m9 = metrics(r9, rf9, 365)
    tplain = float(ex.mean() / (ex.std() / np.sqrt(len(ex))))
    late = float((r9 - rf9).loc["2023-01-01":].mean())
    from math import erf, sqrt
    p9 = 0.5 * (1 - erf(t9 / sqrt(2)))
    results["S9"] = {"label": "Crypto cash-and-carry (long spot, short perp; BTC/ETH), 2019-10..2026-09", "strategy": m9,
                     "excess_mean_%/yr": float(ex.mean() * 365 * 100), "NW_t": t9, "plain_t": tplain, "p_one_sided": p9,
                     "excess_mean_2023+_%/yr": late * 365 * 100}
    print(f"\n[S9] {fmt(results['S9'])}")
    primary.append(("S9", p9, late > 0))
    r9b, _ = s9_funding_carry(positive_only=True)
    results["S9_positive_only"] = {"strategy": metrics(r9b, rf9, 365), "NW_t": nw_t((r9b - rf9).to_numpy())}
    print("[S9 positive-only]", fmt(results["S9_positive_only"]))
    # S10
    rs, rb, rf10 = s10_crypto_xs_momentum()
    p, sub = record("S10", "Crypto 4-week momentum, top 6 of 30 vs equal-weight 30, 2019-2026", rs, rb, rf10, 365, [("2023-01-01", None)], bench_active=True)
    primary.append(("S10", p, all(v > 0 for v in sub.values())))

    # Holm across the ten primary tests
    order = sorted(primary, key=lambda x: x[1])
    m = len(order); adj = {}; run = 0.0
    for i, (k, p, _) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p)); adj[k] = run
    verdict = []
    for k, p, subok in primary:
        verdict.append({"strategy": k, "p_one_sided": p, "p_holm": adj[k], "subperiod_positive": subok,
                        "PASS": bool(adj[k] < 0.05 and subok)})
    vt = pd.DataFrame(verdict)
    print("\nPRE-REGISTERED VERDICTS (Holm across ten):")
    print(vt.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    vt.to_csv(OUT / "verdicts.csv", index=False)
    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=float))


if __name__ == "__main__":
    main()
