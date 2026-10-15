"""
2x S&P 500 + gold (the other instance's C4: 50% SSO / 50% GLD, quarterly) and variations.
Pre-registration: analysis_2026/SSO_GOLD_PREREG.md (written before any pre-2006 run).

    python3 -m analysis_2026.sso_gold              # everything -> analysis_2026/results_sso_gold/
    python3 -m analysis_2026.sso_gold --build      # assemble data/sso_gold/ from the sources below first

Data (gitignored, data/sso_gold/; --build assembles it from the files named in SOURCES):
  steel.csv     SteelCerberus/us-market-data: S&P 500 with dividends (= SPY total return after
                1995), price index, 3-month T-bill rate and return index, the swap rate leveraged
                funds pay, CPI; daily 1928-2025-12-19
  etf_daily.csv SPY/GLD/TLT/IEF total return (Johnbrick123 sp500-data parquet, Yahoo adj_close)
  qlib_*.csv    actual SSO/UPRO/TMF/... (qlib US, total return to 2021-09-16)
  sso_monthly.csv  actual SSO monthly total return, Yahoo adj_close (the other instance's
                hold_sso path, codex/theory-lab), used after 2021-09
  gold.csv      long USD gold price (the validated series chosen under the pre-registration rule)
  bonds.csv     long Treasury total-return indices (variants only)
  gspc_ohlc.csv S&P 500 index daily OHLC 1950-2018 (vijinho/sp500, Yahoo ^GSPC) for Moneyline

Model of a leveraged fund (daily): r_L = L * r_index - (L - 1) * (swap + s) * days/360 - fee * days/365,
r_index = S&P total return with SPY's 0.0945% fee added back; s is fitted on actual SSO 2006-2021.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data" / "sso_gold"
OUT = ROOT / "analysis_2026" / "results_sso_gold"
SPY_FEE, SSO_FEE, UPRO_FEE, GLD_FEE, GDE_FEE = 0.000945, 0.0089, 0.0091, 0.0040, 0.0020
COST = {"lev": 0.0003, "etf": 0.0002, "cash": 0.0}


# ------------------------------------------------------------------ data

def load_steel():
    s = pd.read_csv(DATA / "steel.csv", index_col=0, parse_dates=True)
    return s


def load_etf():
    return pd.read_csv(DATA / "etf_daily.csv", index_col=0, parse_dates=True)


def base_daily(end="2026-10-12", start="1928-01-03"):
    """Daily frame on trading days 1928-01-03..end:
    sp      S&P total-return level (SPY-like, fee included)
    sp_px   S&P price index level (signals)
    r_idx   S&P index total return (SPY fee added back)
    r_cash  T-bill return; swap: swap rate (annual, decimal); cpi; days: calendar days since previous row."""
    s = load_steel()
    e = load_etf()
    sp = s["Adjusted Close"].astype(float)
    px = s["Close"].astype(float)
    cash = s["Risk Free Return"].astype(float)
    last = sp.index[-1]
    spy = e["SPY"].dropna().loc[last:end]
    if len(spy) < 2:                                   # window ends inside the SteelCerberus history
        spy = None
    if spy is None:
        df = pd.DataFrame({"sp": sp, "sp_px": px, "cash_lvl": cash})
        return _finish(df, s).loc[start:end]
    sp = pd.concat([sp, sp.iloc[-1] * spy.iloc[1:] / spy.iloc[0]])
    # price index after the splice: SPY total return minus the S&P's trailing dividend yield
    dy = float((np.log(s["Adjusted Close"]).diff() - np.log(s["Close"]).diff()).loc[last - pd.Timedelta(days=365):].sum())
    ext = spy.iloc[1:] / spy.iloc[0] * np.exp(-dy * (spy.index[1:] - last).days / 365.25)
    px = pd.concat([px, px.iloc[-1] * ext])
    rf_last = float(s["Risk Free Rate"].iloc[-1]) / 100
    days_ext = pd.Series(spy.index[1:], index=spy.index[1:]).diff().dt.days.fillna((spy.index[1] - last).days)
    cash_ext = cash.iloc[-1] * np.exp(np.cumsum(np.log1p(rf_last * days_ext / 360)))
    cash = pd.concat([cash, cash_ext])
    df = pd.DataFrame({"sp": sp, "sp_px": px, "cash_lvl": cash})
    return _finish(df, s).loc[start:end]


def _finish(df, s):
    df = df.copy()
    df["swap"] = (s["Swap Rate"].astype(float) / 100).reindex(df.index).ffill()
    df["rf"] = (s["Risk Free Rate"].astype(float) / 100).reindex(df.index).ffill()
    df["cpi"] = s["CPI"].astype(float).reindex(df.index).ffill()
    df["days"] = pd.Series(df.index, index=df.index).diff().dt.days.fillna(1).astype(float)
    df["r_sp"] = df["sp"].pct_change().fillna(0.0)
    df["r_idx"] = df["r_sp"] + SPY_FEE * df["days"] / 365
    df["r_cash"] = df["cash_lvl"].pct_change().fillna(0.0)
    df["r_div"] = (df["r_sp"] - df["sp_px"].pct_change().fillna(0.0)).clip(lower=0)   # dividend part (taxed yearly)
    return df


def lev_returns(b, L, spread, fee):
    """Synthetic L-times daily fund on the S&P index (see module docstring)."""
    return L * b["r_idx"] - (L - 1) * (b["swap"] + spread) * b["days"] / 360 - fee * b["days"] / 365


def load_gold(b, src=None, kind=None):
    """Daily gold return on b's trading days: the long series (gold.csv) less a 0.40%/yr fund fee
    before GLD exists, GLD itself after 2004-11-18. Returns (series, kind) with kind
    'daily' or 'monthly' (monthly series book each month's return on its last trading day)."""
    if src is None:
        g = pd.read_csv(DATA / "gold.csv", index_col=0, parse_dates=True).iloc[:, 0].astype(float).dropna()
        meta = json.loads((DATA / "gold_meta.json").read_text()) if (DATA / "gold_meta.json").exists() else {"kind": "daily"}
    else:
        g, meta = src, {"kind": kind}
    gld = load_etf()["GLD"].dropna()
    start_gld = gld.index[0]
    if meta["kind"] == "daily":
        lvl = g.reindex(b.index.union(g.index)).ffill().reindex(b.index)
        r = lvl.pct_change(fill_method=None)
        r = r - GLD_FEE * b["days"] / 365
    else:  # month-end levels -> book monthly return on the month's last trading day of b
        me = b.groupby(b.index.to_period("M")).tail(1).index
        lvl = g.copy(); lvl.index = lvl.index.to_period("M")
        mr = lvl.pct_change()
        r = pd.Series(0.0, index=b.index)
        per = pd.Series(me, index=me.to_period("M"))
        common = per.index.intersection(mr.dropna().index)
        r.loc[per.loc[common].values] = mr.loc[common].values - GLD_FEE / 12
        r.loc[: per.loc[common].values[0]] = np.nan
    gr = gld.reindex(b.index.union(gld.index)).ffill().reindex(b.index).pct_change(fill_method=None)
    r = r.where(b.index < start_gld, gr)
    return r, meta["kind"]


def load_bonds(b):
    if not (DATA / "bonds.csv").exists():
        return None
    x = pd.read_csv(DATA / "bonds.csv", index_col=0, parse_dates=True)
    return x.reindex(b.index.union(x.index)).ffill().reindex(b.index).pct_change(fill_method=None)


# ------------------------------------------------------------------ simulator

class _PolicyMap:
    """Lets simulate() treat a policy callable like the {row: weights} map."""
    def __init__(self, f):
        self.f, self.h, self.cache = f, None, {}

    def __contains__(self, i):
        w = self.f(i, self.h)
        if w is None:
            return False
        self.cache[i] = np.asarray(w, float)
        return True

    def __getitem__(self, i):
        return self.cache.pop(i)


@dataclass
class Tax:
    st: float = 0.35        # short-term gains and interest
    lt: float = 0.20        # long-term gains and qualified dividends
    col: float = 0.28       # long-term gains on the gold fund (collectibles)


def simulate(R, W, cost, kinds=None, income=None, tax: Tax | None = None, policy=None):
    """Portfolio on the rows of R (daily or monthly simple returns per asset).
    W: target weights on trade dates (index subset of R.index, same columns); the portfolio
    trades to them at the close of each W date after that day's return; between dates it drifts.
    The first row of R must be a W date (initial purchase). cost: per-asset cost per side.
    kinds: per-asset tax kind - 'eq' (20% LT), 'gold' (28% LT), 'cash' (interest taxed yearly).
    income: per-asset part of each day's return that is taxable income that year (dividends),
    reinvested after tax. With tax, lots are FIFO; tax is settled each December and the
    portfolio is liquidated at the end. policy(i, h) may replace W: called every row with the
    current holdings (dollars), it returns target weights or None (no trade).
    Returns dict(value=Series, after_tax=float, turnover=float)."""
    cols = list(R.columns)
    A = R.fillna(0.0).to_numpy(float)
    n, k = A.shape
    c = np.array([cost[x] for x in cols])
    if policy is None:
        wmap = {R.index.get_loc(d): W.loc[d, cols].to_numpy(float) for d in W.index}
        if 0 not in wmap:
            raise ValueError("first row must be a trade date")
    else:
        wmap = _PolicyMap(policy)
    inc = income.reindex(R.index).fillna(0.0)[cols].to_numpy(float) if income is not None else np.zeros_like(A)
    kinds = kinds or {x: "eq" for x in cols}
    kind = [kinds[x] for x in cols]
    h = np.zeros(k); V = np.empty(n); turnover = 0.0
    years = R.index.year.to_numpy()
    pol = isinstance(wmap, _PolicyMap)
    if tax is None:
        for i in range(n):
            if i:
                h *= 1 + A[i]
            if pol:
                wmap.h = h
            if i in wmap:
                w = wmap[i]
                v = h.sum() if i else 1.0
                tgt = w * v
                tr = np.abs(tgt - h).sum() if i else 0.0
                fee = (np.abs(tgt - h) * c).sum() if i else (tgt * c).sum()
                turnover += tr / max(v, 1e-12)
                h = w * (v - fee)
            V[i] = h.sum()
        return {"value": pd.Series(V, R.index), "after_tax": None, "turnover": turnover}

    # ---- with tax: lots per asset as [units, basis, start_index]
    P = np.ones(k)                     # per-asset unit price (cumulative growth)
    lots = [[] for _ in range(k)]
    st_g = lt_g = col_g = 0.0          # realized this year
    ordinary = qualified = 0.0
    carry_st = carry_lt = 0.0
    paid = 0.0

    def sell(j, dollars, i):
        nonlocal st_g, lt_g, col_g
        units = dollars / P[j]
        while units > 1e-15 and lots[j]:
            lu, lb, li = lots[j][0]
            take = min(units, lu)
            basis = lb * take / lu
            gain = take * P[j] - basis
            held = (R.index[i] - R.index[li]).days
            if kind[j] != "cash":
                if held > 365:
                    if kind[j] == "gold":
                        col_g += gain
                    else:
                        lt_g += gain
                else:
                    st_g += gain
            if take >= lu - 1e-15:
                lots[j].pop(0)
            else:
                lots[j][0] = [lu - take, lb - basis, li]
            units -= take

    def buy(j, dollars, i):
        if dollars > 1e-15:
            lots[j].append([dollars / P[j], dollars, i])

    def settle(final=False):
        nonlocal st_g, lt_g, col_g, ordinary, qualified, carry_st, carry_lt
        s_ = st_g + carry_st
        l20, l28 = lt_g, col_g
        lt_tot = l20 + l28 + carry_lt
        if lt_tot < 0:
            l20, l28 = lt_tot, 0.0
        else:                                   # LT losses reduce 28% gains first
            neg = min(l20, 0) + min(carry_lt, 0)
            l28 = max(l28, 0) + neg
            if l28 < 0:
                l20, l28 = max(l20, 0) + l28, 0.0
            else:
                l20 = max(l20, 0)
        if s_ < 0 < l20 + l28:                  # cross-netting
            use = min(-s_, l28); l28 -= use; s_ += use
            use = min(-s_, l20); l20 -= use; s_ += use
        elif l20 + l28 < 0 < s_:
            use = min(s_, -(l20 + l28)); s_ -= use; l20 += use
        carry_st = min(s_, 0.0); carry_lt = min(l20 + l28, 0.0)
        t_ = (tax.st * max(s_, 0) + tax.lt * max(l20, 0) + tax.col * max(l28, 0)
              + tax.st * ordinary + tax.lt * qualified)
        st_g = lt_g = col_g = ordinary = qualified = 0.0
        return t_

    for i in range(n):
        if i:
            g = 1 + A[i]
            P *= g
            gained = h * A[i]
            h *= g
            for j in range(k):                       # income: taxable now, reinvested (adds basis)
                if kind[j] == "cash":
                    ordinary += gained[j]
                    for L in lots[j]:
                        L[1] *= g[j]                 # interest is basis, not a capital gain
                elif inc[i, j] and h[j] > 0:
                    dv = h[j] / g[j] * inc[i, j]
                    qualified += dv
                    if lots[j]:
                        lots[j][-1][1] += dv
        if pol:
            wmap.h = h
        if i in wmap:
            w = wmap[i]
            v = h.sum() if i else 1.0
            tgt = w * v
            d = tgt - h
            fee = (np.abs(d) * c).sum() if i else (tgt * c).sum()
            turnover += (np.abs(d).sum() if i else 0.0) / max(v, 1e-12)
            new = w * (v - fee)
            for j in range(k):
                if new[j] < h[j] - 1e-15:
                    sell(j, h[j] - new[j], i)
            for j in range(k):
                if new[j] > h[j] + 1e-15:
                    buy(j, new[j] - h[j], i)
            h = new
        last_of_year = (i == n - 1) or years[i + 1] != years[i]
        if last_of_year and i < n - 1:
            t_ = settle()
            v = h.sum()
            if t_ > 0 and v > 0:                       # pay pro rata, no extra realization
                f = 1 - t_ / v
                h *= f
                for j in range(k):
                    for L in lots[j]:
                        L[0] *= f; L[1] *= f
                paid += t_
        V[i] = h.sum()
    for j in range(k):                                 # final liquidation
        if h[j] > 0:
            sell(j, h[j], n - 1)
    t_ = settle(final=True)
    return {"value": pd.Series(V, R.index), "after_tax": V[-1] - max(t_, 0.0), "turnover": turnover}


def trade_dates(index, freq):
    """Rebalance dates: last row of each month ('M'), calendar quarter ('Q') or year ('A')."""
    s = pd.Series(index, index=index)
    if freq == "M":
        g = index.to_period("M")
    elif freq == "Q":
        g = index.to_period("Q")
    else:
        g = index.to_period("Y")
    return pd.DatetimeIndex(s.groupby(g).tail(1).values)


def static_weights(index, w: dict, freq="Q"):
    d = trade_dates(index, freq).union(index[:1])
    return pd.DataFrame([w] * len(d), index=d)


def signal_weights(index, on: pd.Series, w_on: dict, w_off: dict, lag=1, rebalance=None):
    """Weights from a daily boolean signal read at close t, executed at close t+lag.
    Optional periodic rebalance dates (to restore w_on/w_off mixes)."""
    sig = on.reindex(index).fillna(False).astype(bool).shift(lag).fillna(False).astype(bool)
    chg = sig.ne(sig.shift(1))
    chg.iloc[0] = True
    d = index[chg.to_numpy()]
    if rebalance is not None:
        d = d.union(rebalance.intersection(index))
    rows = [w_on if sig.loc[x] else w_off for x in d]
    return pd.DataFrame(rows, index=d)


# ------------------------------------------------------------------ signals

def sma_signal(level, n):
    return level > level.rolling(n, min_periods=n).mean()


def sma_band_signal(level, n=200, band=0.02):
    """Hysteresis: turn on above SMA*(1+band), off below SMA*(1-band)."""
    m = level.rolling(n, min_periods=n).mean().to_numpy(); x = level.to_numpy()
    out = np.zeros(len(x), bool); on = False
    for i in range(len(x)):
        if np.isnan(m[i]):
            continue
        if on and x[i] < m[i] * (1 - band):
            on = False
        elif not on and x[i] > m[i] * (1 + band):
            on = True
        out[i] = on
    return pd.Series(out, index=level.index)


def weekly_moneyline_signal(ohlc, n=1):
    """Moneyline on weekly bars (to_weekly, Monday-labelled); the state of a week is known at its
    last trading day's close and holds until the next week's last day."""
    from analysis_2026.moneyline_ref import to_weekly
    from analysis_2026.flip_delay import moneyline_delay
    w = to_weekly(ohlc)
    g = pd.Series(moneyline_delay(w, n), index=w.index)
    last_day = ohlc.index.to_series().groupby(ohlc.index.to_period("W-SUN")).max()
    lab = pd.Series(last_day.values, index=last_day.index.start_time)
    g.index = pd.DatetimeIndex(lab.reindex(g.index).values)
    g = g[g.index.notna()]
    return g.reindex(ohlc.index).ffill().fillna(False).astype(bool)


def monthly_sma_signal(level, months=10):
    """True on every day of month m+1 if level at the end of month m > average of the last `months`
    month-end levels. (Read at the month-end close, so the daily lag adds one more day.)"""
    me = level.groupby(level.index.to_period("M")).last()
    ok = me > me.rolling(months, min_periods=months).mean()
    s = pd.Series(np.nan, index=level.index)
    last_days = level.groupby(level.index.to_period("M")).tail(1).index
    s.loc[last_days] = ok.reindex(last_days.to_period("M")).to_numpy().astype(float)
    return s.ffill().fillna(0).astype(bool)


def gspc_ohlc(b):
    """S&P 500 index daily OHLC for the indicator: ^GSPC (vijinho) to its end, then SPY OHLC scaled."""
    from analysis_2026.moneyline_ref import _col  # noqa: F401
    g = pd.read_csv(DATA / "gspc_ohlc.csv", index_col=0, parse_dates=True)[["open", "high", "low", "close"]]
    spy = pd.read_csv(DATA / "spy_ohlc.csv", index_col=0, parse_dates=True)[["open", "high", "low", "close"]]
    j = g.index[-1]
    f = g.loc[j, "close"] / spy.loc[j, "close"]
    ext = spy.loc[j:].iloc[1:] * f
    return pd.concat([g, ext]).loc[: b.index[-1]]


def moneyline_green(ohlc, n):
    from analysis_2026.flip_delay import moneyline_delay
    return pd.Series(moneyline_delay(ohlc, n), index=ohlc.index)


# ------------------------------------------------------------------ statistics

def monthly(v):
    return v.groupby(v.index.to_period("M")).last()


def metrics(v, cash_lvl, after_tax=None):
    """v: value series (daily or monthly). Monthly stats."""
    m = monthly(v)
    cm = monthly(cash_lvl.reindex(v.index).ffill())
    r = m.pct_change().dropna(); rc = cm.pct_change().reindex(r.index).fillna(0)
    yrs = (v.index[-1] - v.index[0]).days / 365.25
    out = {"start": str(v.index[0].date()), "end": str(v.index[-1].date()),
           "CAGR_%": ((v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - 1) * 100,
           "vol_%": r.std() * np.sqrt(12) * 100,
           "Sharpe": (r - rc).mean() / (r - rc).std() * np.sqrt(12),
           "maxDD_%": float((v / v.cummax() - 1).min() * 100),
           "worst_year_%": float((v.groupby(v.index.year).last() / v.groupby(v.index.year).last().shift(1).fillna(v.iloc[0]) - 1).min() * 100)}
    if after_tax is not None:
        out["CAGR_after_tax_%"] = ((after_tax / v.iloc[0]) ** (1 / yrs) - 1) * 100 if after_tax > 0 else -100.0
    return out


def active_log(v_s, v_b):
    a = np.log(monthly(v_s)).diff() - np.log(monthly(v_b)).diff()
    return a.dropna()


def stationary_boot_p(x, block=36, n=5000, seed=0):
    """Null-centred stationary block bootstrap of the mean: one-sided p = P(mean* - mean >= mean)."""
    x = np.asarray(x, float); T = len(x); m = x.mean()
    rng = np.random.default_rng(seed)
    p_new = 1.0 / block
    idx = np.empty((n, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, T, n)
    new = rng.random((n, T)) < p_new
    starts = rng.integers(0, T, (n, T))
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    means = x[idx].mean(axis=1)
    d = means - m
    return float((d >= m).mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)), idx


def holm(ps: dict):
    order = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(order); run = 0.0; out = {}
    for i, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p)); out[k] = run
    return out


def alpha_regression(v, factors: pd.DataFrame, cash_lvl, lags=12):
    """Monthly excess return on factor excess returns; Newey-West t."""
    m = monthly(v).pct_change()
    rc = monthly(cash_lvl).pct_change()
    y = (m - rc).dropna()
    y = y[y.index.isin(factors.dropna().index)]
    X = factors.reindex(y.index).sub(rc.reindex(y.index), axis=0)
    ok = X.notna().all(axis=1)
    y, X = y[ok], X[ok]
    Z = np.column_stack([np.ones(len(y)), X.to_numpy()])
    b = np.linalg.lstsq(Z, y.to_numpy(), rcond=None)[0]
    e = y.to_numpy() - Z @ b
    T = len(y); ZZi = np.linalg.inv(Z.T @ Z)
    S = (Z * e[:, None]).T @ (Z * e[:, None])
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (Z[L:] * e[L:, None]).T @ (Z[:-L] * e[:-L, None])
        S += w * (G + G.T)
    se = np.sqrt(np.diag(ZZi @ S @ ZZi))
    r2 = 1 - e.var() / y.var()
    res = {"alpha_%/yr": b[0] * 1200, "alpha_t": b[0] / se[0], "R2": r2, "n": T}
    for i, c in enumerate(X.columns):
        res[f"beta_{c}"] = b[i + 1]
    return res


def fit_spread(b):
    """Financing spread s over the swap rate that makes synthetic 2x match actual SSO total return
    (qlib, 2006-06-22..2021-09-16). Also returns tracking stats."""
    sso = pd.read_csv(DATA / "qlib_SSO.csv", index_col=0, parse_dates=True)["close"]
    r = sso.pct_change().loc["2006-06-22":"2021-09-16"]
    bb = b.reindex(r.index)
    base = 2 * bb["r_idx"] - SSO_FEE * bb["days"] / 365 - bb["swap"] * bb["days"] / 360
    k = bb["days"] / 360
    target = float(np.log1p(r).sum())
    lo_, hi_ = -0.05, 0.05                                      # s matching cumulative growth
    for _ in range(60):
        mid = (lo_ + hi_) / 2
        if np.log1p(base - mid * k).sum() > target:
            lo_ = mid
        else:
            hi_ = mid
    s = (lo_ + hi_) / 2
    model = base - s * k
    te = (model - r)
    yrs = len(r) / 252
    out = {"spread_%": s * 100, "tracking_error_%/yr": float(te.std() * np.sqrt(252) * 100),
           "mean_gap_%/yr": float(te.mean() * 252 * 100),
           "CAGR_actual_%": float((1 + r).prod() ** (1 / yrs) - 1) * 100,
           "CAGR_model_%": float((1 + model).prod() ** (1 / yrs) - 1) * 100}
    for lo, hi in [("2006", "2009"), ("2010", "2015"), ("2016", "2021")]:
        x = r.loc[lo:hi]; kk = k.loc[x.index]; bs = base.loc[x.index]
        yrs_ = kk.sum() * 360 / 365.25
        out[f"gap_{lo}-{hi}_%/yr"] = float((np.log1p(bs - s * kk).sum() - np.log1p(x).sum()) / yrs_ * 100)
    return s, out


# ------------------------------------------------------------------ data assembly

RAW = "https://raw.githubusercontent.com"
SOURCES = {
    "steel": f"{RAW}/SteelCerberus/us-market-data/main/data/us_market_data.csv",
    "gspc": f"{RAW}/vijinho/sp500/master/csv/sp500.csv",
}


def _get(url, timeout=180):
    import urllib.request
    for k in range(4):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read()
        except Exception:
            if k == 3:
                raise


def build(johnbrick_parquet, qlib_root, codex_ref="origin/codex/theory-lab"):
    """Assemble data/sso_gold/ (gold.csv / bonds.csv are added separately, see FINDINGS)."""
    import gzip
    import io
    import subprocess
    from screener.data import from_qlib
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "steel.csv").write_bytes(_get(SOURCES["steel"]))
    g = pd.read_csv(io.BytesIO(_get(SOURCES["gspc"])))
    g.columns = [c.strip().lower() for c in g.columns]
    g = g.rename(columns={"date": "date"}).set_index(pd.to_datetime(g["date"]))[["open", "high", "low", "close"]]
    g.sort_index().to_csv(DATA / "gspc_ohlc.csv")
    jb = pd.read_parquet(johnbrick_parquet, columns=["date", "ticker", "open", "high", "low", "close", "adj_close"])
    jb["date"] = pd.to_datetime(jb["date"])
    e = jb[jb.ticker.isin(["SPY", "GLD", "TLT", "IEF", "SHY", "QQQ"])].pivot(index="date", columns="ticker", values="adj_close")
    e.sort_index().to_csv(DATA / "etf_daily.csv")
    jb[jb.ticker == "SPY"].set_index("date")[["open", "high", "low", "close"]].sort_index().to_csv(DATA / "spy_ohlc.csv")
    for sym, d in from_qlib(qlib_root, ["SSO", "UPRO", "QLD", "TMF", "UBT", "NTSX", "GDE", "IAU", "UGL", "SPY", "GLD", "TLT"]).items():
        d.to_csv(DATA / f"qlib_{sym}.csv")
    parts = []
    for i in range(6):
        parts.append(subprocess.run(["git", "show", f"{codex_ref}:analysis_2026/results_theory_lab/monthly_paths_parts/part00{i}.gzbin"],
                                    cwd=ROOT, capture_output=True, check=True).stdout)
    cp = pd.read_csv(io.BytesIO(gzip.decompress(b"".join(parts))))
    sel = cp[(cp.fee == 0.0002) & (cp.lag == 1) & (cp.cash_rate == 0) & (cp.family == "C4") & cp.window.isin(["full", "2026"])]
    piv = sel.pivot_table(index="month", columns="policy", values="log_return")
    piv[["hold_sso", "C4_sso_gold", "hold_benchmark", "spy_gold50"]].to_csv(DATA / "codex_c4_monthly_log.csv")
    print("built", sorted(p.name for p in DATA.iterdir()))


# ------------------------------------------------------------------ study

KIND = {"SP": "eq", "L15": "eq", "L2": "eq", "L3": "eq", "GOLD": "gold", "CASH": "cash", "CE": "cash", "CG": "cash",
        "LTB": "cash", "ITB": "cash", "GDE": "eq"}       # bond funds: all return taxed as ordinary income (approx.)
CKIND = {"SP": "etf", "L15": "lev", "L2": "lev", "L3": "lev", "GOLD": "etf", "CASH": "cash", "CE": "cash", "CG": "cash",
         "LTB": "etf", "ITB": "etf", "GDE": "etf"}
CRISES = [("1973-74 bear", "1973-01", "1974-12"), ("1980-82 gold crash + Volcker", "1980-01", "1982-07"),
          ("1987 crash", "1987-08", "1987-12"), ("2000-02 bear", "2000-03", "2002-10"),
          ("2008 GFC", "2007-10", "2009-03"), ("2020 Covid", "2020-02", "2020-03"), ("2022 inflation", "2022-01", "2022-12")]


def assets(b, s, spread_add=0.0):
    """Daily simple returns of every building block on b's index."""
    gold, gkind = load_gold(b)
    A = pd.DataFrame({"SP": b["r_sp"], "CASH": b["r_cash"]})
    A["CE"] = A["CASH"]; A["CG"] = A["CASH"]
    A["L15"] = lev_returns(b, 1.5, s + spread_add, SSO_FEE)
    A["L2"] = lev_returns(b, 2, s + spread_add, SSO_FEE)
    A["L3"] = lev_returns(b, 3, s + spread_add, UPRO_FEE)
    A["GOLD"] = gold
    spot = gold + GLD_FEE * b["days"] / 365
    A["GDE"] = (0.9 * b["r_idx"] + 0.9 * (spot - (b["rf"] + 0.002 + spread_add) * b["days"] / 360)
                + 0.1 * b["r_cash"] - GDE_FEE * b["days"] / 365)
    bonds = load_bonds(b)
    if bonds is not None:
        for c in bonds.columns:
            A[c] = bonds[c]
    return A, gkind


def window(A, start, end):
    """Rows from the last trading day before `start` (the purchase row) through `end`."""
    i0 = A.index.searchsorted(pd.Timestamp(start)) - 1
    return A.iloc[max(i0, 0):].loc[:end]


def run(A, W=None, cost_mult=1.0, tax=None, b=None, policy=None, cols=None):
    cols = cols or (list(W.columns) if W is not None else None)
    R = A[cols]
    cost = {c: COST[CKIND[c]] * cost_mult for c in cols}
    inc = None
    if tax is not None and b is not None and "SP" in cols:
        inc = pd.DataFrame(0.0, index=R.index, columns=cols); inc["SP"] = b["r_div"].reindex(R.index)
    return simulate(R, W, cost, kinds={c: KIND[c] for c in cols}, income=inc, tax=tax, policy=policy)


def bh(A, col="SP", tax=None, b=None):
    W = pd.DataFrame([{col: 1.0}], index=A.index[:1])
    return run(A, W, tax=tax, b=b)


def static(A, w, freq="Q", **kw):
    return run(A, static_weights(A.index, w, freq), **kw)


def band_policy(cols, w, band, check_dates):
    """Rebalance to w when any weight drifts more than `band` from target, checked on check_dates."""
    w = np.array([w[c] for c in cols]); chk = set(check_dates)
    idx_holder = {}

    def f(i, h):
        if i == 0:
            return w
        d = idx_holder["index"][i]
        if d not in chk:
            return None
        v = h.sum()
        return w if np.abs(h / v - w).max() > band else None
    return f, idx_holder


def sleeves_policy(index, sig_e, sig_g, cols, lev="L2", lag=1, freq="Q", w_e=0.5):
    """P4: equity sleeve (lev fund or cash CE) and gold sleeve (GOLD or cash CG), each following
    its own signal (read at close t, traded at close t+lag), sleeves reset to w_e/1-w_e each quarter."""
    se = sig_e.reindex(index).fillna(False).astype(bool).shift(lag).fillna(False).to_numpy()
    sg = sig_g.reindex(index).fillna(False).astype(bool).shift(lag).fillna(False).to_numpy()
    reb = set(index.get_indexer(trade_dates(index, freq)))
    ci = {c: k for k, c in enumerate(cols)}

    def f(i, h):
        chg = i == 0 or i in reb or se[i] != se[i - 1] or sg[i] != sg[i - 1]
        if not chg:
            return None
        v = 1.0 if i == 0 else h.sum()
        if i == 0 or i in reb:
            e, g = w_e, 1 - w_e
        else:
            e = (h[ci[lev]] + h[ci["CE"]]) / v; g = 1 - e
        w = np.zeros(len(cols))
        w[ci[lev] if se[i] else ci["CE"]] = e
        w[ci["GOLD"] if sg[i] else ci["CG"]] = g
        return w
    return f


def switch_weights(index, sig, lev="L2", lag=1):
    return signal_weights(index, sig, {lev: 1.0, "CASH": 0.0}, {lev: 0.0, "CASH": 1.0}, lag=lag)


def gold_level(A):
    return (1 + A["GOLD"].fillna(0)).cumprod()


class Study:
    def __init__(self):
        self.b = base_daily(end="2026-09-30")
        self.s, self.spread_info = fit_spread(self.b)
        self.A, self.gkind = assets(self.b, self.s)
        self.A_spread = assets(self.b, self.s, 0.005)[0]
        self.sig = {}
        px = self.b["sp_px"]
        self.sig["eq_200d"] = sma_signal(px, 200)
        self.sig["eq_10m"] = monthly_sma_signal(px, 10)
        ohlc = gspc_ohlc(self.b).loc["1962-01-01":]
        for n in (1, 5):
            self.sig[f"eq_ml{n}"] = moneyline_green(ohlc, n).reindex(self.b.index).ffill().fillna(False).astype(bool)
        self.sig["eq_mlw1"] = weekly_moneyline_signal(ohlc, 1).reindex(self.b.index).ffill().fillna(False).astype(bool)
        self.sig["eq_200d_band2"] = sma_band_signal(px, 200, 0.02)
        gl = gold_level(self.A)
        if self.gkind == "daily":
            self.sig["g_200d"] = sma_signal(gl.where(self.A["GOLD"].notna()), 200)
        self.sig["g_10m"] = monthly_sma_signal(gl, 10)
        self.sig["none"] = pd.Series(True, index=self.b.index)

    # --- strategy value series on a window (pre-tax unless tax given)
    def strategy(self, name, start, end, A=None, tax=None, cost_mult=1.0, lag=1):
        A = window(self.A if A is None else A, start, end)
        b = self.b.reindex(A.index)
        kw = dict(cost_mult=cost_mult, tax=tax, b=b)
        if name == "SP":
            return bh(A, tax=tax, b=b)
        if name == "C4":
            return static(A, {"L2": 0.5, "GOLD": 0.5}, "Q", **kw)
        if name == "P3":
            return run(A, switch_weights(A.index, self.sig["eq_200d"], lag=lag), **kw)
        if name == "P4":
            g = "g_200d" if "g_200d" in self.sig else "g_10m"
            cols = ["L2", "CE", "GOLD", "CG"]
            return run(A, policy=sleeves_policy(A.index, self.sig["eq_200d"], self.sig[g], cols, lag=lag), cols=cols, **kw)
        if name == "P5":
            return run(A, switch_weights(A.index, self.sig["eq_ml5"], lag=lag), **kw)
        raise KeyError(name)

    # --- generic variant: dict spec -> value series
    def variant(self, spec, start, end, A=None, tax=None, cost_mult=1.0, lag=1):
        A = window(self.A if A is None else A, start, end)
        b = self.b.reindex(A.index)
        kw = dict(cost_mult=cost_mult, tax=tax, b=b)
        kind = spec["kind"]
        if kind == "static":
            if spec.get("band"):
                cols = list(spec["w"]); me = trade_dates(A.index, "M")
                f, holder = band_policy(cols, spec["w"], spec["band"], me); holder["index"] = A.index
                return run(A, policy=f, cols=cols, **kw)
            if spec.get("freq") == "never":
                return run(A, pd.DataFrame([spec["w"]], index=A.index[:1]), **kw)
            return static(A, spec["w"], spec.get("freq", "Q"), **kw)
        if kind == "switch":
            off = spec.get("off", "CASH")
            W = signal_weights(A.index, self.sig[spec["sig"]], {spec["lev"]: 1.0, off: 0.0}, {spec["lev"]: 0.0, off: 1.0}, lag=lag)
            return run(A, W, **kw)
        if kind == "sleeves":
            cols = [spec["lev"], "CE", "GOLD", "CG"]
            return run(A, policy=sleeves_policy(A.index, self.sig[spec["sig_e"]], self.sig[spec["sig_g"]], cols,
                                                lev=spec["lev"], lag=lag, w_e=spec.get("w_e", 0.5)), cols=cols, **kw)
        if kind == "invvol":
            cols = list(spec["cols"]); me = set(trade_dates(A.index, "M")); idx = A.index
            vol = A[cols].rolling(63, min_periods=40).std()
            def f(i, h):
                if i != 0 and idx[i] not in me:
                    return None
                v = vol.iloc[i].to_numpy()
                if np.isnan(v).any():
                    return np.full(len(cols), 1 / len(cols))
                w = (1 / v) / (1 / v).sum()
                return w
            return run(A, policy=f, cols=cols, **kw)
        raise KeyError(kind)


def grid_specs(have_bonds):
    G = {}
    for w in range(0, 101, 10):
        G[f"w{w:03d}_L2_gold"] = {"kind": "static", "w": {"L2": w / 100, "GOLD": 1 - w / 100}}
    G["1x_SP_gold_50"] = {"kind": "static", "w": {"SP": 0.5, "GOLD": 0.5}}
    G["1.5x_67_gold_33"] = {"kind": "static", "w": {"L15": 2 / 3, "GOLD": 1 / 3}}
    G["3x_33_gold_67"] = {"kind": "static", "w": {"L3": 1 / 3, "GOLD": 2 / 3}}
    G["3x_50_gold_50"] = {"kind": "static", "w": {"L3": 0.5, "GOLD": 0.5}}
    G["GDE_90_90"] = {"kind": "static", "w": {"GDE": 1.0}, "freq": "never"}
    G["L2_50_cash_50"] = {"kind": "static", "w": {"L2": 0.5, "CASH": 0.5}}
    if have_bonds:
        G["L2_50_LTB_50"] = {"kind": "static", "w": {"L2": 0.5, "LTB": 0.5}}
        G["L2_50_ITB_50"] = {"kind": "static", "w": {"L2": 0.5, "ITB": 0.5}}
        G["L2_50_gold25_LTB25"] = {"kind": "static", "w": {"L2": 0.5, "GOLD": 0.25, "LTB": 0.25}}
        G["L3_55_LTB_45_HFEA_like"] = {"kind": "static", "w": {"L3": 0.55, "LTB": 0.45}}
    for f in ("M", "A", "never"):
        G[f"C4_rebal_{f}"] = {"kind": "static", "w": {"L2": 0.5, "GOLD": 0.5}, "freq": f}
    G["C4_band5"] = {"kind": "static", "w": {"L2": 0.5, "GOLD": 0.5}, "band": 0.05}
    for se in ("none", "eq_200d", "eq_10m", "eq_ml1", "eq_ml5"):
        for sg in ("none", "g_10m", "g_200d"):
            if se == "none" and sg == "none":
                continue
            G[f"sleeves_{se}_{sg}"] = {"kind": "sleeves", "lev": "L2", "sig_e": se, "sig_g": sg}
    for lev in ("SP", "L15", "L2", "L3"):
        for sg in ("eq_200d", "eq_10m", "eq_ml1", "eq_ml5", "eq_mlw1", "eq_200d_band2"):
            G[f"switch_{lev}_{sg}"] = {"kind": "switch", "lev": lev, "sig": sg}
    for sg in ("eq_200d", "eq_10m"):
        G[f"switch_L2_{sg}_to_gold"] = {"kind": "switch", "lev": "L2", "sig": sg, "off": "GOLD"}
        if have_bonds:
            G[f"switch_L2_{sg}_to_ITB"] = {"kind": "switch", "lev": "L2", "sig": sg, "off": "ITB"}
    G["invvol_L2_gold"] = {"kind": "invvol", "cols": ["L2", "GOLD"]}
    return G


def reality_check(active: pd.DataFrame, block=36, n=2000, seed=1):
    """White (2000) reality check: max mean active return across variants vs its bootstrap null."""
    X = active.dropna().to_numpy(float)
    mu = X.mean(axis=0); obs = mu.max()
    T = len(X)
    rng = np.random.default_rng(seed)
    p_new = 1.0 / block
    cnt = 0
    for _ in range(n):
        idx = np.empty(T, dtype=np.int64); idx[0] = rng.integers(T)
        new = rng.random(T) < p_new; st = rng.integers(0, T, T)
        for t in range(1, T):
            idx[t] = st[t] if new[t] else (idx[t - 1] + 1) % T
        mstar = (X[idx].mean(axis=0) - mu).max()
        cnt += mstar >= obs
    return {"best": active.columns[int(mu.argmax())], "best_mean_%/yr": float(obs * 1200), "p": cnt / n}


def fmt(d):
    return {k: (fmt(v) if isinstance(v, dict) else round(float(v), 4) if isinstance(v, (float, np.floating)) else v)
            for k, v in d.items()}


PRIMARY = {"P1": ("C4", "1972-01-01", "2006-06-30"), "P2": ("C4", "1972-01-01", "2026-09-30"),
           "P3": ("P3", "1929-01-01", "2026-09-30"), "P4": ("P4", "1972-01-01", "2026-09-30"),
           "P5": ("P5", "1963-01-01", "2026-09-30")}


def main():
    OUT.mkdir(exist_ok=True)
    st = Study()
    cash = st.b["cash_lvl"]
    res = {"spread_fit": st.spread_info, "gold_kind": st.gkind, "gold_meta": json.loads((DATA / "gold_meta.json").read_text())}
    lines = []

    def say(x=""):
        print(x); lines.append(str(x))

    say(f"Synthetic 2x: financing = swap rate + {st.s*100:.3f}%/yr, fee 0.89%: {fmt(st.spread_info)}")
    say(f"Gold series: {res['gold_meta']}")

    # ---------------- primary tests
    say("\nPRIMARY TESTS (vs S&P 500 total-return buy & hold; monthly active log return)")
    prim, ps = {}, {}
    for key, (name, a, z) in PRIMARY.items():
        S = st.strategy(name, a, z); B = st.strategy("SP", a, z)
        act = active_log(S["value"], B["value"])
        p, lo, hi, _ = stationary_boot_p(act.to_numpy(), 36, 5000, seed=7)
        half = len(act) // 2
        h1, h2 = act.iloc[:half].mean() * 12 * 100, act.iloc[half:].mean() * 12 * 100
        stress = {}
        for lab, kw in [("costs_x5", dict(cost_mult=5.0)), ("spread+0.5", dict(A=st.A_spread)),
                        ("lag+1", dict(lag=2))]:
            if lab == "lag+1" and name == "C4":
                continue
            Sx = st.strategy(name, a, z, **kw)
            stress[lab] = float(active_log(Sx["value"], B["value"]).mean() * 1200)
        T_s, T_b = st.strategy(name, a, z, tax=Tax()), st.strategy("SP", a, z, tax=Tax())
        ms, mb = metrics(S["value"], cash, T_s["after_tax"]), metrics(B["value"], cash, T_b["after_tax"])
        yrs = (S["value"].index[-1] - S["value"].index[0]).days / 365.25
        prim[key] = {"strategy": name, "period": f"{a}..{z}", "active_%/yr": float(act.mean() * 1200),
                     "ci95_%/yr": [lo * 1200, hi * 1200], "p_one_sided": p, "half1_%/yr": h1, "half2_%/yr": h2,
                     "stress_active_%/yr": stress, "metrics": ms, "benchmark": mb, "turnover_per_yr": S["turnover"] / yrs}
        if name in ("P3", "P5"):
            post = act.loc["2016-01":]
            prim[key]["post_2016_active_%/yr"] = float(post.mean() * 1200)
        ps[key] = p
        say(f"[{key}] {name} {a}..{z}: active {act.mean()*1200:+.2f}%/yr  CI [{lo*1200:+.2f},{hi*1200:+.2f}]  p {p:.4f}  "
            f"halves {h1:+.2f}/{h2:+.2f}  stress {fmt(stress)}")
        say(f"     strategy {fmt(ms)}\n     S&P      {fmt(mb)}")
    adj = holm(ps)
    for k in prim:
        pr = prim[k]
        pr["p_holm"] = adj[k]
        pr["PASS"] = bool(adj[k] < 0.05 and pr["half1_%/yr"] > 0 and pr["half2_%/yr"] > 0
                          and all(v > 0 for v in pr["stress_active_%/yr"].values()))
    res["primary"] = prim
    vt = pd.DataFrame([{"test": k, "strategy": v["strategy"], "period": v["period"], "active_%/yr": v["active_%/yr"],
                        "p": v["p_one_sided"], "p_holm": v["p_holm"], "half1": v["half1_%/yr"], "half2": v["half2_%/yr"],
                        "min_stress": min(v["stress_active_%/yr"].values()), "PASS": v["PASS"]} for k, v in prim.items()])
    say("\nVERDICTS (Holm across five):\n" + vt.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    vt.to_csv(OUT / "verdicts.csv", index=False)

    # ---------------- pre-registered sensitivities: 1975 start; World Bank monthly-average gold
    say("\nSENSITIVITY: C4 from 1975-01 (US private gold ownership legal) and with World Bank monthly-average gold")
    sens = {}
    for lab, a, z in [("C4 1975-01..2006-06", "1975-01-01", "2006-06-30"), ("C4 1975-01..2026-09", "1975-01-01", "2026-09-30")]:
        S = st.strategy("C4", a, z); B = st.strategy("SP", a, z)
        act = active_log(S["value"], B["value"]); p, lo, hi, _ = stationary_boot_p(act.to_numpy(), 36, 5000, seed=7)
        sens[lab] = {"active_%/yr": float(act.mean() * 1200), "p_one_sided": p}
        say(f"  {lab}: {fmt(sens[lab])}")
    wb = pd.read_csv(DATA / "gold_wb_monthly_avg.csv")
    wbs = pd.Series(wb["Price"].astype(float).values, index=pd.PeriodIndex(wb["Date"], freq="M").to_timestamp("M"))
    A_wb = st.A.copy()
    A_wb["GOLD"] = load_gold(st.b, src=wbs.loc["1968":], kind="monthly")[0]
    for key in ("P1", "P2"):
        name, a, z = PRIMARY[key]
        S = st.strategy(name, a, z, A=A_wb); B = st.strategy("SP", a, z)
        act = active_log(S["value"], B["value"]); p, lo, hi, _ = stationary_boot_p(act.to_numpy(), 36, 5000, seed=7)
        sens[f"{key}_WB_avg_gold"] = {"active_%/yr": float(act.mean() * 1200), "p_one_sided": p}
        say(f"  {key} with World Bank monthly-average gold: {fmt(sens[f'{key}_WB_avg_gold'])}")
    res["sensitivity"] = sens

    # ---------------- exposure decomposition
    say("\nEXPOSURE DECOMPOSITION (monthly excess returns on S&P and gold excess; NW t, 12 lags)")
    fac = pd.DataFrame({"sp": monthly((1 + st.A["SP"]).cumprod()).pct_change(),
                        "gold": monthly((1 + st.A["GOLD"].fillna(0)).cumprod()).pct_change()})
    cm = monthly(cash)
    res["decomposition"] = {}
    for key in ("P1", "P2", "P3", "P4", "P5"):
        name, a, z = PRIMARY[key]
        v = st.strategy(name, a, z)["value"]
        d = alpha_regression(v, fac, cash.loc[v.index[0]:v.index[-1]])
        res["decomposition"][key] = d
        say(f"  {key} {name}: {fmt(d)}")

    # ---------------- actual-fund track (monthly): C4 and SPY/GLD with real SSO/GLD
    say("\nACTUAL FUNDS 2006-07..2026-09 (SSO: qlib total return to 2021-09, then Yahoo path; GLD, SPY)")
    act_tab = actual_track(st)
    res["actual_track"] = act_tab
    for k, v in act_tab.items():
        say(f"  {k}: {fmt(v)}")

    # ---------------- crisis windows, rolling windows, start dates
    say("\nCRISIS WINDOWS (total return over the window, %)")
    crises = {}
    full = {k: st.strategy(k, "1972-01-01", "2026-09-30")["value"] for k in ("SP", "C4", "P3", "P4", "P5")}
    gl = (1 + st.A["GOLD"].fillna(0)).cumprod()
    for lab, a, z in CRISES:
        row = {}
        for k, v in list(full.items()) + [("GOLD", gl)]:
            mv = monthly(v)
            pa = (pd.Period(a, "M") - 1)
            if pa in mv.index and pd.Period(z, "M") in mv.index:
                row[k] = float((mv[pd.Period(z, "M")] / mv[pa] - 1) * 100)
        crises[lab] = row
        say(f"  {lab:30s} " + "  ".join(f"{k} {x:+6.1f}" for k, x in row.items()))
    res["crises"] = crises
    say("\nROLLING 10-YEAR WINDOWS vs S&P (share of monthly-start windows the strategy's CAGR is higher; median gap)")
    roll = {}
    msp = monthly(full["SP"])
    for k in ("C4", "P3", "P4", "P5"):
        mv = monthly(full[k])
        g = (np.log(mv).diff(120) - np.log(msp).diff(120)).dropna() / 10
        roll[k] = {"share_ahead": float((g > 0).mean()), "median_gap_%/yr": float(g.median() * 100),
                   "worst_gap_%/yr": float(g.min() * 100), "best_gap_%/yr": float(g.max() * 100)}
        say(f"  {k}: {fmt(roll[k])}")
    res["rolling10"] = roll
    say("\nSTART-DATE SENSITIVITY (CAGR gap vs S&P to 2026-09, pre-tax, points)")
    sd = {}
    for y in range(1972, 2011, 2):
        row = {}
        for k in ("C4", "P3", "P4"):
            v = st.strategy(k, f"{y}-01-01", "2026-09-30")["value"]; bsp = st.strategy("SP", f"{y}-01-01", "2026-09-30")["value"]
            yrs = (v.index[-1] - v.index[0]).days / 365.25
            row[k] = float(((v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - (bsp.iloc[-1] / bsp.iloc[0]) ** (1 / yrs)) * 100)
        sd[y] = row
        say(f"  {y}: " + "  ".join(f"{k} {x:+.2f}" for k, x in row.items()))
    res["start_dates"] = sd

    # ---------------- era table: gold vs cash, and C4 active by decade
    say("\nBY DECADE: gold-fund CAGR, T-bill CAGR, C4 / P3 / P4 active (%/yr)")
    era = {}
    for a, z in [("1972", "1979"), ("1980", "1989"), ("1990", "1999"), ("2000", "2009"), ("2010", "2019"), ("2020", "2026-09")]:
        row = {}
        g_ = monthly(gl).loc[a:z]; c_ = monthly(cash).loc[a:z]
        n_ = len(g_) - 1
        if n_ > 12:
            row["gold_CAGR"] = float(((g_.iloc[-1] / g_.iloc[0]) ** (12 / n_) - 1) * 100)
            row["tbill_CAGR"] = float(((c_.iloc[-1] / c_.iloc[0]) ** (12 / n_) - 1) * 100)
        for k in ("C4", "P3", "P4", "P5"):
            act = active_log(full[k], full["SP"]).loc[a:z]
            row[k] = float(act.mean() * 1200)
        era[f"{a}-{z}"] = row
        say(f"  {a}-{z}: {fmt(row)}")
    res["eras"] = era

    # ---------------- gold valuation (Erb & Harvey)
    res["gold_valuation"] = gold_valuation(st)
    say(f"\nGOLD VALUATION (log real gold vs next-10y real return): {fmt(res['gold_valuation'])}")

    # ---------------- P3 mechanism, pre-1928 out of sample, actual SSO
    res["regime_stats"] = regime_stats(st)
    say("\nS&P BY 200-DAY STATE (state that sets P3's exposure; index returns, annualised)")
    for era_, row in res["regime_stats"].items():
        say(f"  {era_}: above {fmt(row['above'])}\n  {' ' * len(era_)}  below {fmt(row['below'])}")
    sens3 = p3_sensitivity(st)
    sens3.to_csv(OUT / "p3_sensitivity.csv", index=False)
    say("\nP3 NEIGHBOURHOOD 1929-2026 (active vs S&P, %/yr; descriptive)")
    say(sens3.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    res["pre1928"] = pre1928_check(st)
    say("\nPRE-1928 OUT OF SAMPLE (Dow composite 1886-1927, crude T-bill proxy; exploratory)")
    for k, v in res["pre1928"].items():
        say(f"  {k}: {fmt(v)}")
    res["actual_p3"] = actual_p3_track(st)
    say("\nACTUAL SSO + 200-DAY RULE 2006-07..2026-09 (price-only after 2021-09 plus monthly distribution fix)")
    for k, v in res["actual_p3"].items():
        say(f"  {k}: {fmt(v)}")

    # ---------------- variant grid + reality check (pre-tax, 1972-01..2026-09; after-tax reported)
    say("\nVARIANT GRID 1972-01..2026-09 (pre-tax and after-tax CAGR; active vs S&P)")
    have_bonds = any(c in st.A.columns for c in ("LTB", "ITB"))
    G = grid_specs(have_bonds)
    a, z = "1972-01-01", "2026-09-30"
    B = st.strategy("SP", a, z); Bt = st.strategy("SP", a, z, tax=Tax())
    rows, actives = [], {}
    for name, spec in G.items():
        try:
            v = st.variant(spec, a, z)
            t = st.variant(spec, a, z, tax=Tax())
        except KeyError as e:
            say(f"  skip {name}: {e}"); continue
        mt = metrics(v["value"], cash, t["after_tax"])
        act = active_log(v["value"], B["value"])
        actives[name] = act
        yrs = (v["value"].index[-1] - v["value"].index[0]).days / 365.25
        rows.append({"variant": name, **{k: mt[k] for k in ("CAGR_%", "CAGR_after_tax_%", "vol_%", "Sharpe", "maxDD_%", "worst_year_%")},
                     "active_%/yr": float(act.mean() * 1200), "turnover/yr": v["turnover"] / yrs})
    mb = metrics(B["value"], cash, Bt["after_tax"])
    rows.append({"variant": "S&P buy & hold", **{k: mb[k] for k in ("CAGR_%", "CAGR_after_tax_%", "vol_%", "Sharpe", "maxDD_%", "worst_year_%")},
                 "active_%/yr": 0.0, "turnover/yr": 0.0})
    grid = pd.DataFrame(rows).sort_values("CAGR_%", ascending=False)
    grid.to_csv(OUT / "grid_1972_2026.csv", index=False)
    say(grid.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    rc = reality_check(pd.DataFrame(actives))
    res["reality_check"] = rc
    say(f"\nREALITY CHECK over {len(actives)} variants: {fmt(rc)}")

    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=float))
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n")


def actual_track(st):
    """Monthly, real funds: C4 (SSO+GLD), SPY/GLD 50/50, SPY, SSO; plus the synthetic C4 on the same months."""
    e = load_etf()
    me = e[["SPY", "GLD"]].groupby(e.index.to_period("M")).last().pct_change()
    q = pd.read_csv(DATA / "qlib_SSO.csv", index_col=0, parse_dates=True)["close"]
    qm = q.groupby(q.index.to_period("M")).last().pct_change()
    cm = pd.read_csv(DATA / "codex_c4_monthly_log.csv", index_col=0); cm.index = pd.PeriodIndex(cm.index, freq="M")
    sso = pd.concat([qm.loc["2006-07":"2021-08"], np.expm1(cm["hold_sso"]).loc["2021-09":]])
    R = pd.DataFrame({"L2": sso, "GOLD": me["GLD"], "SP": me["SPY"]}).loc["2006-07":"2026-09"].dropna()
    R.index = R.index.to_timestamp("M")
    R = pd.concat([pd.DataFrame(0.0, index=[R.index[0] - pd.offsets.MonthEnd(1)], columns=R.columns), R])
    cash = monthly(st.b["cash_lvl"]); cash.index = cash.index.to_timestamp("M")
    out = {}
    for name, w in [("C4_actual", {"L2": 0.5, "GOLD": 0.5}), ("SPY_GLD_50_50", {"SP": 0.5, "GOLD": 0.5}),
                    ("SPY", {"SP": 1.0}), ("SSO", {"L2": 1.0}), ("GLD", {"GOLD": 1.0})]:
        W = static_weights(R.index, w, "Q") if len(w) > 1 else pd.DataFrame([w], index=R.index[:1])
        v = run(R, W)["value"]
        out[name] = metrics(v, cash)
    syn = st.strategy("C4", "2006-07-01", "2026-09-30")["value"]
    out["C4_synthetic_same_months"] = metrics(syn, st.b["cash_lvl"])
    return out


def regime_stats(st):
    """S&P daily returns grouped by the 200-day state that sets P3's exposure that day (signal at
    close t-2, traded at close t-1): annualised mean, vol, Sharpe; and the implied growth of 1x vs 2x."""
    b = st.b
    state = st.sig["eq_200d"].reindex(b.index).fillna(False).shift(2).fillna(False).astype(bool)
    out = {}
    for a, z in [("1929", "1949"), ("1950", "1979"), ("1980", "1999"), ("2000", "2015"), ("2016", "2026-09"), ("1929", "2026-09")]:
        row = {}
        for lab, mask in (("above", state), ("below", ~state)):
            m_ = mask.loc[a:z]
            r = b["r_idx"].loc[a:z][m_]; rc = b["r_cash"].loc[a:z][m_]
            l2 = st.A["L2"].loc[a:z][m_]
            row[lab] = {"share_days": float(m_.mean()), "mean_%/yr": float(r.mean() * 252 * 100),
                        "vol_%/yr": float(r.std() * np.sqrt(252) * 100),
                        "Sharpe": float((r - rc).mean() / (r - rc).std() * np.sqrt(252)),
                        "log_growth_1x_%/yr": float(np.log1p(r).mean() * 252 * 100),
                        "log_growth_2x_%/yr": float(np.log1p(l2).mean() * 252 * 100),
                        "log_growth_cash_%/yr": float(np.log1p(rc).mean() * 252 * 100)}
        out[f"{a}-{z}"] = row
    return out


def pre1928_check(st):
    """P3's rule on the Dow Jones composite 1886-1927 (SteelCerberus; crude T-bill proxy before 1926).
    Out of sample for Gayed & Bilello (1928+). Exploratory."""
    b0 = base_daily(start="1885-03-20", end="1927-12-30")
    A0 = pd.DataFrame({"SP": b0["r_sp"], "CASH": b0["r_cash"], "L2": lev_returns(b0, 2, st.s, SSO_FEE),
                       "L3": lev_returns(b0, 3, st.s, UPRO_FEE)})
    sig = sma_signal(b0["sp_px"], 200)
    A0 = window(A0, "1886-01-01", "1927-12-30")
    out = {}
    vb = bh(A0)["value"]
    out["buy_and_hold"] = metrics(vb, b0["cash_lvl"])
    for lev in ("SP", "L2", "L3"):
        v = run(A0, switch_weights(A0.index, sig, lev=lev))["value"]
        act = active_log(v, vb)
        p, lo, hi, _ = stationary_boot_p(act.to_numpy(), 36, 2000, seed=11)
        out[f"{lev}_200d"] = {**metrics(v, b0["cash_lvl"]), "active_%/yr": float(act.mean() * 1200), "p_one_sided": p}
    return out


def actual_sso_daily():
    """Actual SSO daily: qlib total return to 2021-09-16, qlib price after; recent parquet from 2024-08-05;
    the 2024-04-26..2024-08-02 gap is filled with the synthetic fund; after 2021-09 each month's
    distribution shortfall vs the Yahoo total-return path is added on the month's last day."""
    q = pd.read_csv(DATA / "qlib_SSO.csv", index_col=0, parse_dates=True)["close"]
    rec_p = DATA / "recent_SSO.csv"
    if not rec_p.exists():
        rec_p = ROOT / "data" / "universe_recent" / "SSO.csv"
    rec = pd.read_csv(rec_p, index_col=0, parse_dates=True)["close"]
    return q, rec


def actual_p3_track(st):
    b = st.b.loc["2006-06-21":"2026-09-30"]
    q, rec = actual_sso_daily()
    syn = lev_returns(b, 2, st.s, SSO_FEE)
    r = pd.Series(np.nan, index=b.index)
    rq = q.pct_change().reindex(b.index)
    r.loc[:"2024-04-25"] = rq.loc[:"2024-04-25"]
    rr = rec.pct_change().reindex(b.index)
    r.loc["2024-08-06":] = rr.loc["2024-08-06":]
    gap = r.isna() & (r.index > pd.Timestamp("2006-06-21"))
    r[gap] = syn[gap]
    r.iloc[0] = 0.0
    cm = pd.read_csv(DATA / "codex_c4_monthly_log.csv", index_col=0); cm.index = pd.PeriodIndex(cm.index, freq="M")
    mlog = np.log1p(r).groupby(r.index.to_period("M")).sum()
    resid = (cm["hold_sso"] - mlog).loc["2021-10":"2026-09"].dropna()
    last = r.groupby(r.index.to_period("M")).tail(1)
    for per, x in resid.items():
        d = last.index[last.index.to_period("M") == per]
        if len(d):
            r.loc[d[0]] = (1 + r.loc[d[0]]) * np.exp(x) - 1
    A = pd.DataFrame({"L2": r, "CASH": b["r_cash"], "SP": b["r_sp"]})
    A = window(A, "2006-07-01", "2026-09-30")
    vb = bh(A)["value"]
    out = {"SPY": metrics(vb, st.b["cash_lvl"])}
    for lab, sig in [("SSO_200d_actual", "eq_200d"), ("SSO_10m_actual", "eq_10m")]:
        v = run(A, switch_weights(A.index, st.sig[sig]))["value"]
        out[lab] = {**metrics(v, st.b["cash_lvl"]), "active_%/yr": float(active_log(v, vb).mean() * 1200)}
    v = run(A, pd.DataFrame([{"L2": 1.0, "CASH": 0.0, "SP": 0.0}], index=A.index[:1]))["value"]
    out["SSO_hold_actual"] = metrics(v, st.b["cash_lvl"])
    vs = st.strategy("P3", "2006-07-01", "2026-09-30")["value"]
    out["P3_synthetic_same_window"] = {**metrics(vs, st.b["cash_lvl"]), "active_%/yr": float(active_log(vs, vb).mean() * 1200)}
    return out


def p3_sensitivity(st):
    """P3's neighbourhood, 1929-01..2026-09: SMA length, leverage, signal series, band, lag.
    Active return vs S&P overall and in 1929-1971 / 1972-2026; descriptive (not a test)."""
    A = window(st.A, "1929-01-01", "2026-09-30")
    vb = bh(A)["value"]
    px, tr = st.b["sp_px"], st.b["sp"]
    rows = []

    def one(label, sig, lev="L2", lag=1):
        v = run(A, switch_weights(A.index, sig, lev=lev, lag=lag))["value"]
        act = active_log(v, vb)
        yrs = (v.index[-1] - v.index[0]).days / 365.25
        rows.append({"variant": label, "CAGR_%": ((v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - 1) * 100,
                     "active_%/yr": act.mean() * 1200, "active_1929_1971": act.loc[:"1971"].mean() * 1200,
                     "active_1972_2026": act.loc["1972":].mean() * 1200, "active_2016_2026": act.loc["2016":].mean() * 1200,
                     "maxDD_%": float((v / v.cummax() - 1).min() * 100)})
    for n in (50, 100, 150, 200, 250, 300):
        for lev in ("L15", "L2", "L3"):
            one(f"SMA{n}_{lev}", sma_signal(px, n), lev)
    one("SMA200_L2_total_return_index", sma_signal(tr, 200))
    one("SMA200_L2_lag2", sma_signal(px, 200), lag=2)
    one("SMA200_L2_lag5", sma_signal(px, 200), lag=5)
    for bd in (0.01, 0.02, 0.03):
        one(f"SMA200_L2_band{int(bd*100)}", sma_band_signal(px, 200, bd))
    one("10m_L2", st.sig["eq_10m"])
    return pd.DataFrame(rows)


def gold_valuation(st):
    """Erb & Harvey: does a high real gold price predict low 10-year real gold returns? (spot, monthly)"""
    gl = (1 + st.A["GOLD"].fillna(0) + GLD_FEE * st.b["days"] / 365).cumprod()
    first = st.A["GOLD"].first_valid_index()
    m = monthly(gl.loc[first:]); cpi = monthly(st.b["cpi"]).reindex(m.index)
    real = np.log(m / cpi)
    fwd = real.shift(-120) - real
    d = pd.DataFrame({"lvl": real - real.mean(), "fwd": fwd}).dropna()
    X = np.column_stack([np.ones(len(d)), d.lvl]); bcoef = np.linalg.lstsq(X, d.fwd, rcond=None)[0]
    nonover = d.iloc[::120]
    now = float(real.iloc[-1] - real.mean())
    pct = float((real.iloc[-1] > real).mean())
    return {"slope_fwd10y_per_log_unit": float(bcoef[1]), "R2": float(1 - (d.fwd - X @ bcoef).var() / d.fwd.var()),
            "n_overlapping": len(d), "n_nonoverlapping": len(nonover),
            "current_log_real_vs_mean": now, "current_percentile": pct,
            "implied_next10y_real_%/yr": float((bcoef[0] + bcoef[1] * now) / 10 * 100),
            "real_gold_now_vs_1980_peak": float(np.exp(real.iloc[-1] - real.loc["1979-06":"1980-12"].max()))}


if __name__ == "__main__":
    if "--build" in sys.argv:
        print("use build(johnbrick_parquet, qlib_root) from Python; see the docstring")
    else:
        main()
