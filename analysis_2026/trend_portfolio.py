"""
Professional-style trend following: does it help a stock portfolio?

Trend-following funds run something like the user's indicator, but across many markets
(stocks, bonds, gold, commodities, currencies), long AND short, with positions sized by
volatility and the whole book scaled to a target risk. This tests that version on ETFs
and asks what a 20% sleeve does for a portfolio that is otherwise all S&P 500.

Data (data/etf/, gitignored; see HANDOFF section 3 for how to rebuild):
  Universe A, 2005-01 to 2026-10: SPY IWM EFA EEM TLT IEF TIP LQD HYG GLD SLV VNQ
    (Yahoo OHLC from github.com/Johnbrick123/sp500-data, scaled to total return).
  Universe B, 2005-01 to 2024-04: A plus DBC USO DBA UUP FXE FXY FXA FXF (qlib; total
    return until 2021-09-16 and price-only after, so these extras miss their
    distributions from then on).
  Real managed-futures funds for a reality check: WTMF, DBMF, KMLM (qlib, same caveat).

Sleeves (signals at the close, trades at the NEXT close, 0.05% per side on turnover,
cash and futures collateral earn the T-bill rate):
  S1 TSMOM long/short - the professional reference (Moskowitz, Ooi & Pedersen 2012).
     Monthly: sign of each asset's 12-month return in excess of T-bills; weight =
     sign / volatility (EWMA, 60-day centre of mass). The book is scaled to 10% annual
     volatility using the trailing 120-day covariance, capped at 3x gross. This needs
     futures or margin, so it isn't possible in the Robinhood agentic account; managed
     futures ETFs (DBMF, KMLM, WTMF) package it.
  S2 TSMOM long-only, unlevered: the same with shorts replaced by cash, gross <= 100%.
  S3 the user's indicator, professional-style: the exact daily moneyline state per ETF,
     long-only. Same volatility sizing: weights are set at month ends, exits happen on
     the day after a red flip, entries on the day after a green flip, gross <= 100%.

Portfolios (rebalanced each January): 100% SPY; 60/40 SPY/IEF; 80% SPY + 20% sleeve;
each sleeve alone.
After tax (illustrative 35% short-term / 20% long-term): two separate accounts, never
rebalanced. SPY is taxed once at the long-term rate at the end; the sleeve's yearly
net gains are taxed at 35% with losses carried forward. (Futures-based funds are
taxed partly at long-term rates under section 1256, so this is conservative for S1.)

Pre-registered hypotheses (written 2026-10-14, before any run; universe A, 2005-2026):
  H1 80% SPY + 20% S1 has a max drawdown at least 5 pts smaller than 100% SPY AND a
     higher Sharpe ratio.
  H2 The same for the implementable long-only sleeves (S2, S3) with a drawdown at least
     3 pts smaller and a higher Sharpe ratio.
  H3 Reported either way: does any 80/20 portfolio match or beat SPY's CAGR?
  Universe B and the sub-periods 2005-2014 and 2015-2026 are robustness checks.

    python -m analysis_2026.trend_portfolio
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline  # noqa: E402
from screener.strictness import TBILL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "etf"
UNIV_A = ["SPY", "IWM", "EFA", "EEM", "TLT", "IEF", "TIP", "LQD", "HYG", "GLD", "SLV", "VNQ"]
UNIV_B = UNIV_A + ["Q_DBC", "Q_USO", "Q_DBA", "Q_UUP", "Q_FXE", "Q_FXY", "Q_FXA", "Q_FXF"]
COST = 0.0005
TARGET_VOL = 0.10
ST, LT = 0.35, 0.20


def load(names):
    out = {}
    for n in names:
        d = pd.read_csv(DATA / f"{n}.csv", parse_dates=["date"]).set_index("date").sort_index()
        out[n] = d[~d.index.duplicated(keep="last")]
    return out


def panel(data, cal):
    close = pd.DataFrame({n: d.close for n, d in data.items()}).reindex(cal)
    avail = close.notna()
    ret = close.ffill().pct_change().fillna(0.0)
    ret[~avail] = 0.0
    return ret, avail


def rf_daily(cal):
    return pd.Series([TBILL.get(d.year, 2.0) / 100 / 252 for d in cal], index=cal)


def month_ends(cal):
    s = pd.Series(cal, index=cal)
    return set(s.groupby([cal.year, cal.month]).max())


def run_sleeve(kind, data, cal, start, end):
    """Daily returns of a trend sleeve. kind: 'S1' long/short TSMOM, 'S2' long-only TSMOM,
    'S3' long-only moneyline. Weights decided at close t take effect from close t+1."""
    ret, avail = panel(data, cal)
    rf = rf_daily(cal)
    names = list(data)
    hist = avail.cumsum()
    vol = np.sqrt((ret ** 2).ewm(com=60, min_periods=60).mean() * 252)
    r12 = (1 + ret).rolling(252).apply(np.prod, raw=True) - 1
    rf12 = (1 + rf).rolling(252).apply(np.prod, raw=True) - 1
    green = {}
    if kind == "S3":
        for n, d in data.items():
            green[n] = moneyline(d).green.astype(float).reindex(cal).ffill().fillna(0).to_numpy() > 0.5
    me = month_ends(cal)
    i0 = int(np.searchsorted(cal, pd.Timestamp(start))); i1 = int(np.searchsorted(cal, pd.Timestamp(end), side="right")) - 1
    w = np.zeros(len(names)); pending = None
    k_month = 0.0; inv_vol = np.zeros(len(names))
    out = []; gross = []
    R = ret.to_numpy(); A = avail.to_numpy(); H = hist.to_numpy(); V = vol.to_numpy(); M = r12.to_numpy()
    for t in range(i0, i1 + 1):
        # 1) apply the trade decided yesterday at today's close: today's return uses old w
        r_t = R[t]
        if kind == "S1":
            day = float(w @ (r_t - rf.iloc[t])) + rf.iloc[t]
        else:
            day = float(w @ r_t) + (1 - w.sum()) * rf.iloc[t]
        # today's return moves the old weights (no daily rebalancing) ...
        if w.any():
            w = w * (1 + r_t) / (1 + day)
        # ... then yesterday's decision is traded at today's close
        if pending is not None:
            day -= COST * np.abs(pending - w).sum()
            w = pending; pending = None
        out.append(day); gross.append(np.abs(w).sum())
        # 2) decide new weights at today's close
        ok = A[t] & (H[t] >= 260) & np.isfinite(V[t]) & (V[t] > 0)
        is_me = cal[t] in me
        if is_me:
            if kind == "S3":
                s = np.array([green[n][t] for n in names], dtype=float)
            else:
                s = np.sign(M[t] - rf12.iloc[t]); s = np.nan_to_num(s)
                if kind == "S2":
                    s = np.maximum(s, 0)
            s = np.where(ok, s, 0.0)
            raw = np.where(ok, s / np.where(V[t] > 0, V[t], np.inf), 0.0)
            # scale to the target volatility with the trailing 120-day covariance
            lo = max(0, t - 119)
            idx = np.where(ok)[0]
            k = 0.0
            if len(idx) and np.abs(raw).sum() > 0:
                cov = np.cov(R[lo:t + 1][:, idx].T) * 252 if len(idx) > 1 else np.array([[np.var(R[lo:t + 1, idx[0]]) * 252]])
                pv = float(np.sqrt(max(raw[idx] @ np.atleast_2d(cov) @ raw[idx], 1e-12)))
                k = TARGET_VOL / pv
            new = k * raw
            cap = 3.0 if kind == "S1" else 1.0
            g = np.abs(new).sum()
            if g > cap:
                new *= cap / g
            k_month = k * (min(1.0, cap / g) if g > 0 else 1.0)
            inv_vol = np.where(ok, 1 / np.where(V[t] > 0, V[t], np.inf), 0.0)
            pending = new
        elif kind == "S3":
            s = np.array([green[n][t] for n in names])
            cur = w.copy()
            changed = False
            for j in range(len(names)):
                if cur[j] > 0 and not s[j]:
                    cur[j] = 0.0; changed = True
                elif cur[j] == 0 and s[j] and ok[j] and k_month > 0:
                    room = 1.0 - cur.sum()
                    if room > 1e-6:
                        cur[j] = min(k_month * inv_vol[j], room); changed = True
            if changed:
                pending = cur
    idx = cal[i0:i1 + 1]
    return pd.Series(out, index=idx), pd.Series(gross, index=idx)


def portfolio(parts, weights, rebalance="annual"):
    """Combine daily return streams with fixed weights, rebalanced each January."""
    df = pd.concat(parts, axis=1).fillna(0.0)
    w = np.array(weights, float); vals = w.copy(); out = []
    prev_year = None
    for d, r in zip(df.index, df.to_numpy()):
        if rebalance == "annual" and prev_year is not None and d.year != prev_year:
            vals = vals.sum() * w
        prev_year = d.year
        before = vals.sum()
        vals = vals * (1 + r)
        out.append(vals.sum() / before - 1)
    return pd.Series(out, index=df.index)


def stats(r, rf, spy=None):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    ex = r - rf.reindex(r.index).fillna(0)
    sharpe = ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    yr = (1 + r).groupby(r.index.year).prod() - 1

    def period(a, b):
        x = r.loc[a:b]
        return (1 + x).prod() - 1 if len(x) else np.nan
    return {"CAGR_%": cagr * 100, "vol_%": vol * 100, "Sharpe": sharpe, "maxDD_%": dd * 100,
            "worst_year_%": yr.min() * 100, "2008_%": period("2008-01-01", "2008-12-31") * 100,
            "covid_crash_%": period("2020-02-20", "2020-03-23") * 100, "2022_%": period("2022-01-01", "2022-12-31") * 100,
            "corr_SPY": r.corr(spy) if spy is not None else np.nan}


def after_tax_sleeve(r):
    """Yearly net gains taxed at 35%, losses carried forward."""
    v, carry = 1.0, 0.0
    for _, x in r.groupby(r.index.year):
        g = v * ((1 + x).prod() - 1)
        net = g + carry
        tax = ST * net if net > 0 else 0.0
        carry = 0.0 if net > 0 else net
        v += g - tax
    return v


def after_tax_hold(r):
    m = (1 + r).prod()
    return m - LT * (m - 1) if m > 1 else m


def study(universe, start, end, label):
    data = load(universe)
    cal = data["SPY"].index
    cal = cal[(cal >= pd.Timestamp(start) - pd.Timedelta(days=400)) & (cal <= pd.Timestamp(end))]
    ret, _ = panel(data, cal)
    rf = rf_daily(cal)
    spy = ret["SPY"].loc[start:end]; ief = ret["IEF"].loc[start:end]
    sleeves, grosses = {}, {}
    for k in ("S1", "S2", "S3"):
        sleeves[k], grosses[k] = run_sleeve(k, data, cal, start, end)
    rows = {"100% SPY": spy, "60/40 SPY/IEF": portfolio([spy, ief], [0.6, 0.4])}
    for k, name in [("S1", "TSMOM long/short"), ("S2", "TSMOM long-only"), ("S3", "moneyline long-only")]:
        rows[f"80/20 SPY + {name}"] = portfolio([spy, sleeves[k]], [0.8, 0.2])
    for k, name in [("S1", "TSMOM long/short"), ("S2", "TSMOM long-only"), ("S3", "moneyline long-only")]:
        rows[f"sleeve alone: {name}"] = sleeves[k]
    tab = pd.DataFrame({n: stats(r, rf, spy) for n, r in rows.items()}).T
    yrs = len(spy) / 252
    at = {"100% SPY": after_tax_hold(spy)}
    for k, name in [("S1", "TSMOM long/short"), ("S2", "TSMOM long-only"), ("S3", "moneyline long-only")]:
        at[f"80/20 SPY + {name}"] = 0.8 * after_tax_hold(spy) + 0.2 * after_tax_sleeve(sleeves[k])
        at[f"sleeve alone: {name}"] = after_tax_sleeve(sleeves[k])
    tab["after_tax_CAGR_%"] = pd.Series({n: (m ** (1 / yrs) - 1) * 100 for n, m in at.items()})
    tab["avg_gross"] = pd.Series({f"sleeve alone: {n}": grosses[k].mean() for k, n in
                                  [("S1", "TSMOM long/short"), ("S2", "TSMOM long-only"), ("S3", "moneyline long-only")]})
    print(f"\n=== {label}: {start} to {spy.index[-1].date()} ({len(universe)} ETFs) ===")
    print(tab.to_string(float_format=lambda x: f"{x:,.2f}"))
    return tab, sleeves


def main():
    pd.set_option("display.width", 250)
    out = ROOT / "analysis_2026" / "results_trend"
    out.mkdir(exist_ok=True)
    tA, sA = study(UNIV_A, "2005-01-01", "2026-10-12", "Universe A (pre-registered)")
    tA.to_csv(out / "universe_A_2005_2026.csv")
    for a, b in [("2005-01-01", "2014-12-31"), ("2015-01-01", "2026-10-12")]:
        t, _ = study(UNIV_A, a, b, f"Universe A sub-period")
        t.to_csv(out / f"universe_A_{a[:4]}_{b[:4]}.csv")
    tB, sB = study(UNIV_B, "2005-01-01", "2024-04-25", "Universe B (robustness: + commodities, currencies)")
    tB.to_csv(out / "universe_B_2005_2024.csv")
    # reality check: real managed-futures funds vs S1, while qlib is still total return
    real = load(["Q_WTMF", "Q_DBMF"])
    rows = []
    for n, d in real.items():
        r = d.close.pct_change().dropna().loc[:"2021-09-16"]
        s1 = sB["S1"].reindex(r.index).dropna()
        r = r.reindex(s1.index)
        yrs = len(r) / 252
        rows.append({"fund": n[2:], "from": r.index[0].date(), "to": r.index[-1].date(),
                     "fund_CAGR_%": ((1 + r).prod() ** (1 / yrs) - 1) * 100,
                     "S1_CAGR_%": ((1 + s1).prod() ** (1 / yrs) - 1) * 100,
                     "daily_corr": r.corr(s1), "monthly_corr": (1 + r).resample("ME").prod().corr((1 + s1).resample("ME").prod())})
    rc = pd.DataFrame(rows)
    print("\nReal managed-futures funds vs S1 (universe B), while the data is total return:")
    print(rc.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    rc.to_csv(out / "real_funds_vs_S1.csv", index=False)
    yearly = pd.DataFrame({k: (1 + v).groupby(v.index.year).prod() - 1 for k, v in sA.items()})
    yearly["SPY"] = (1 + load(["SPY"])["SPY"].close.pct_change()).groupby(load(["SPY"])["SPY"].index.year).prod() - 1
    yearly = (yearly.loc[2005:] * 100).round(1)
    print("\nCalendar-year returns, universe A sleeves vs SPY (%):")
    print(yearly.to_string())
    yearly.to_csv(out / "yearly_universe_A.csv")


if __name__ == "__main__":
    main()
