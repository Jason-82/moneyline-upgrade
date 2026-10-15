"""
2x S&P 500 + gold (the other instance's C4: 50% SSO / 50% GLD, quarterly) and variations.
Pre-registration: analysis_2026/SSO_GOLD_PREREG.md (written before any pre-2006 run). Audited by six
independent lenses plus confirm checks; the audit fixes are applied by default (see below).

    python3 -m analysis_2026.sso_gold              # everything -> analysis_2026/results_sso_gold/ (~1.5 min)

Data (gitignored, data/sso_gold/; build() assembles the first group, the rest were added by hand):
  steel.csv     SteelCerberus/us-market-data: S&P 500 with dividends (= SPY total return after 1995),
                price (= SPY raw close after 1993), T-bill rate and return index, 'Swap Rate', CPI;
                daily 1885-2025-12-19
  etf_daily.csv, spy_ohlc.csv  SPY/GLD/TLT/IEF total return and SPY raw OHLC (Johnbrick123 sp500-data, Yahoo)
  qlib_*.csv    actual SSO/UPRO/... (qlib US, total return to 2021-09-16); codex_c4_monthly_log.csv: the
                other instance's monthly paths (codex/theory-lab)
  gspc_ohlc.csv S&P 500 index daily OHLC 1950-2018 (vijinho/sp500); real high/low from 1962
  gold.csv      LBMA Gold Price PM, USD, daily 1968-04-01..2026-02-25 (unbalancedparentheses/forex-centuries,
                a copy of prices.lbma.org.uk/json/gold_pm.json); gold_meta.json; gold_wb_monthly_avg.csv
                (datasets/gold-prices commit 5571813, World Bank monthly averages: pre-registered fallback)
  sso_tr_daily.csv  actual SSO/UPRO daily total return 2006-06-21..2026-10-13: Yahoo adj_close
                (itbelikethat03/Testfolio_checker cache) and Tiingo (ravelab/l-etf), cross-checked
  bonds.csv     LTB (~20y) and ITB (10y) Treasury total-return indices, daily 1962-2026: yield models on
                H.15 constant-maturity yields, monthly totals anchored to CRSP fixed-term indices 1942-99,
                actual TLT/IEF after the yield data end; 0.15%/yr fee deducted on the model part
  data/ff/ff3_monthly.csv  Ken French monthly RF (unrounded T-bills before 1954)

Leveraged fund (daily): r_L = L * r_index - (L - 1) * f * days/360 - fee * days/365, r_index = S&P total return
with SPY's 0.0945% fee added back. f = 'Swap Rate' + s, s = 0.471% fitted to match actual SSO's cumulative
growth 2006-06-22..2021-09-16. AUDIT FIX (default; audit_fix=False reproduces the pre-registered data): before
1986 'Swap Rate' is the 1-month bill rounded to 2.52-point steps (0% in 1933-49) with no bank-funding spread,
so f = T-bill + 0.55% before 1986-01-02, and before 1954 T-bills come from Ken French monthly RF.
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


PRE1986_SPREAD = 0.0055   # audit fix: 1986-2006 mean of 1-month LIBOR minus the 3-month T-bill in this data


def base_daily(end="2026-10-12", start="1928-01-03", audit_fix=True):
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
        return _finish(df, s, audit_fix).loc[start:end]
    sp = pd.concat([sp, sp.iloc[-1] * spy.iloc[1:] / spy.iloc[0]])
    if audit_fix:   # steel 'Close' is SPY's raw close after 1993: continue it with SPY's raw close
        raw = pd.read_csv(DATA / "spy_ohlc.csv", index_col=0, parse_dates=True)["close"].loc[last:end]
        ext = raw.iloc[1:] / raw.iloc[0]
    else:           # pre-registered run: SPY total return minus the trailing dividend yield
        dy = float((np.log(s["Adjusted Close"]).diff() - np.log(s["Close"]).diff()).loc[last - pd.Timedelta(days=365):].sum())
        ext = spy.iloc[1:] / spy.iloc[0] * np.exp(-dy * (spy.index[1:] - last).days / 365.25)
    px = pd.concat([px, px.iloc[-1] * ext])
    rf_last = float(s["Risk Free Rate"].iloc[-1]) / 100
    days_ext = pd.Series(spy.index[1:], index=spy.index[1:]).diff().dt.days.fillna((spy.index[1] - last).days)
    cash_ext = cash.iloc[-1] * np.exp(np.cumsum(np.log1p(rf_last * days_ext / 360)))
    cash = pd.concat([cash, cash_ext])
    df = pd.DataFrame({"sp": sp, "sp_px": px, "cash_lvl": cash})
    return _finish(df, s, audit_fix).loc[start:end]


def _finish(df, s, audit_fix=True):
    """Rates and returns. audit_fix (default) repairs SteelCerberus' pre-1986 rates: its 'Swap Rate' is
    the Ken French 1-month bill rounded to 2.52-point steps before 1986 (0% in 1933-49) with no
    bank-funding spread. Fixed: before 1954 cash and rf come from Ken French MONTHLY RF (unrounded),
    and before 1986-01-02 financing = T-bill + PRE1986_SPREAD."""
    df = df.copy()
    df["swap"] = (s["Swap Rate"].astype(float) / 100).reindex(df.index).ffill()
    df["rf"] = (s["Risk Free Rate"].astype(float) / 100).reindex(df.index).ffill()
    df["cpi"] = s["CPI"].astype(float).reindex(df.index).ffill()
    df["days"] = pd.Series(df.index, index=df.index).diff().dt.days.fillna(1).astype(float)
    df["r_sp"] = df["sp"].pct_change().fillna(0.0)
    df["r_idx"] = df["r_sp"] + SPY_FEE * df["days"] / 365
    df["r_cash"] = df["cash_lvl"].pct_change().fillna(0.0)
    if audit_fix:
        ffm = pd.read_csv(ROOT / "data" / "ff" / "ff3_monthly.csv", index_col=0, parse_dates=True)["RF"].astype(float)
        ffm.index = ffm.index.to_period("M")
        early = (df.index >= pd.Timestamp("1926-07-01")) & (df.index < pd.Timestamp("1954-01-01"))
        per = df.index.to_period("M")
        n_in_month = pd.Series(1, index=df.index).groupby(per).transform("size")
        rm = pd.Series(ffm.reindex(per).to_numpy(), index=df.index)
        daily = (1 + rm) ** (1 / n_in_month) - 1
        df.loc[early, "r_cash"] = daily[early].fillna(0.0)
        df.loc[early, "rf"] = ((1 + rm[early]) ** 12 - 1).fillna(0.0)
        df["cash_lvl"] = df["cash_lvl"].iloc[0] * (1 + df["r_cash"]).cumprod()
        pre86 = df.index < pd.Timestamp("1986-01-02")
        df.loc[pre86, "swap"] = df.loc[pre86, "rf"] + PRE1986_SPREAD
    df["r_div"] = (df["r_sp"] - df["sp_px"].pct_change().fillna(0.0)).clip(lower=0)   # dividend part (taxed yearly)
    return df


FINANCING = {  # alternatives to swap + s (sensitivity only): rate on the borrowed (L-1)
    "ratedep": lambda b: 0.0068 + 1.106 * b["rf"],      # fitted to real SSO 2006-2026 (vs 1-month bill)
    "punitive": lambda b: 0.0029 + 1.452 * b["rf"],     # implied by testfol.io's SSOSIM before 2006
    "diy": lambda b: 0.003 + b["rf"],                    # futures / box spreads: T-bill + 0.3%
}


def lev_returns(b, L, spread, fee, financing=None):
    """Synthetic L-times daily fund on the S&P index (see module docstring)."""
    f = b["swap"] + spread if financing is None else FINANCING[financing](b)
    return L * b["r_idx"] - (L - 1) * f * b["days"] / 360 - fee * b["days"] / 365


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
    if meta["kind"] == "daily":
        r = r.where(b.index < start_gld, gr.fillna(r))           # GLD's first day: keep the series' own move
    else:                                                       # monthly series: switch after its Nov-2004 month-end
        cut = b.index[(b.index >= start_gld)].to_series().groupby(b.index[(b.index >= start_gld)].to_period("M")).max().iloc[0]
        r = r.where(b.index <= cut, gr)
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
    st: float = 0.35        # short-term gains (and other ordinary income)
    lt: float = 0.20        # long-term gains
    col: float = 0.28       # long-term gains on the gold fund (collectibles)
    interest: float | None = None   # T-bill interest (default st)
    dividend: float | None = None   # qualified dividends (default lt)
    liquidate: bool = True          # sell everything at the end (False: held for heirs, basis steps up)

    @staticmethod
    def scenario(niit=False, state=0.0, liquidate=True):
        """Federal 35/20/28 as pre-registered; niit adds 3.8%; state is added to gains and dividends,
        not to T-bill interest (exempt from state tax)."""
        a = 0.038 if niit else 0.0
        return Tax(st=0.35 + a + state, lt=0.20 + a + state, col=0.28 + a + state,
                   interest=0.35 + a, dividend=0.20 + a + state, liquidate=liquidate)


def simulate(R, W, cost, kinds=None, income=None, tax: Tax | None = None, policy=None,
             ordinary=None, extra_cost=None):
    """Portfolio on the rows of R (daily or monthly simple returns per asset).
    W: target weights on trade dates (index subset of R.index, same columns); the portfolio
    trades to them at the close of each W date after that day's return; between dates it drifts.
    The first row of R must be a W date (initial purchase). cost: per-asset cost per side.
    kinds: per-asset tax kind - 'eq' (20% LT), 'gold' (28% LT), 'cash' (interest taxed yearly).
    income: per-asset part of each day's return that is taxable income that year (dividends),
    reinvested after tax. With tax, lots are FIFO; tax is settled each December and the
    portfolio is liquidated at the end. policy(i, h) may replace W: called every row with the
    current holdings (dollars), it returns target weights or None (no trade).
    ordinary: per-asset daily return component taxed each year as ordinary income when that
    year's total is positive (a fund's Subpart F income, e.g. GDE's gold-futures sleeve); losing
    years give no deduction. extra_cost: per-asset Series of additional per-side cost by date.
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
    oinc = ordinary.reindex(R.index).fillna(0.0)[cols].to_numpy(float) if ordinary is not None else np.zeros_like(A)
    xc = np.zeros_like(A)
    for c_, ser in (extra_cost or {}).items():
        xc[:, cols.index(c_)] = ser.reindex(R.index).fillna(0.0).to_numpy(float)
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
                fee = (np.abs(tgt - h) * (c + xc[i])).sum() if i else (tgt * (c + xc[i])).sum()
                turnover += tr / max(v, 1e-12)
                h = w * (v - fee)
            V[i] = h.sum()
        return {"value": pd.Series(V, R.index), "after_tax": None, "turnover": turnover}

    # ---- with tax: lots per asset as [units, basis, start_index]
    P = np.ones(k)                     # per-asset unit price (cumulative growth)
    lots = [[] for _ in range(k)]
    st_g = lt_g = col_g = 0.0          # realized this year
    interest = qualified = other_ord = 0.0
    oacc = np.zeros(k)                 # this year's ordinary-income stream per asset (dollars)
    carry_st = carry_lt = 0.0
    paid = 0.0
    r_int = tax.st if tax.interest is None else tax.interest
    r_div = tax.lt if tax.dividend is None else tax.dividend

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
        nonlocal st_g, lt_g, col_g, interest, qualified, other_ord, carry_st, carry_lt
        for j in range(k):                       # fund ordinary income: taxed if positive, reinvested
            if oacc[j] > 0:
                other_ord += oacc[j]
                if lots[j]:
                    lots[j][-1][1] += oacc[j]
        oacc[:] = 0.0
        s_ = st_g + carry_st
        l20, l28 = lt_g, col_g + carry_lt       # LT carryover and 20%-group losses offset 28% gains first
        if l28 < 0:
            l20, l28 = l20 + l28, 0.0
        if l20 < 0:
            l28, l20 = l28 + l20, 0.0
        if l28 < 0:                             # net long-term loss
            l20, l28 = l28, 0.0
        if s_ < 0 < l20 + l28:                  # cross-netting
            use = min(-s_, l28); l28 -= use; s_ += use
            use = min(-s_, l20); l20 -= use; s_ += use
        elif l20 + l28 < 0 < s_:
            use = min(s_, -(l20 + l28)); s_ -= use; l20 += use
        carry_st = min(s_, 0.0); carry_lt = min(l20 + l28, 0.0)
        t_ = (tax.st * max(s_, 0) + tax.lt * max(l20, 0) + tax.col * max(l28, 0)
              + r_int * interest + r_div * qualified + tax.st * other_ord)
        st_g = lt_g = col_g = interest = qualified = other_ord = 0.0
        return t_

    for i in range(n):
        if i:
            g = 1 + A[i]
            P *= g
            gained = h * A[i]
            h *= g
            oacc += h / g * oinc[i]
            for j in range(k):                       # income: taxable now, reinvested (adds basis)
                if kind[j] == "cash":
                    interest += gained[j]
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
            fee = (np.abs(d) * (c + xc[i])).sum() if i else (tgt * (c + xc[i])).sum()
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
    if tax.liquidate:                                  # final liquidation
        for j in range(k):
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
    sig = on.fillna(False).astype(bool).shift(lag).reindex(index).fillna(False).astype(bool)
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


def boot_indices(T, block, n, rng):
    """n stationary-bootstrap index paths of length T (mean block `block`)."""
    idx = np.empty((n, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, T, n)
    new = rng.random((n, T)) < 1.0 / block
    starts = rng.integers(0, T, (n, T))
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def stationary_boot_p(x, block=36, n=5000, seed=0, chunk=2500):
    """Null-centred stationary block bootstrap of the mean: one-sided p = P(mean* - mean >= mean)."""
    x = np.asarray(x, float); T = len(x); m = x.mean()
    rng = np.random.default_rng(seed)
    means = []
    for k0 in range(0, n, chunk):
        means.append(x[boot_indices(T, block, min(chunk, n - k0), rng)].mean(axis=1))
    means = np.concatenate(means)
    return float((means - m >= m).mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)), None


def sharpe_diff_boot_p(rs, rb, rc, block=36, n=5000, seed=0, chunk=2500):
    """Paired stationary bootstrap of the monthly Sharpe-ratio difference (strategy - benchmark), null-centred."""
    rs, rb, rc = (np.asarray(v, float) for v in (rs, rb, rc))
    es, eb = rs - rc, rb - rc
    obs = es.mean() / es.std() - eb.mean() / eb.std()
    rng = np.random.default_rng(seed); T = len(es); d = []
    for k0 in range(0, n, chunk):
        idx = boot_indices(T, block, min(chunk, n - k0), rng)
        a, b_ = es[idx], eb[idx]
        d.append(a.mean(1) / a.std(1) - b_.mean(1) / b_.std(1))
    d = np.concatenate(d)
    return float(obs * np.sqrt(12)), float((d - obs >= obs).mean())


def nw_t(x, lags):
    x = np.asarray(x, float); e = x - x.mean(); T = len(x)
    s = e @ e / T
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * (e[L:] @ e[:-L]) / T
    return float(x.mean() / np.sqrt(s / T))


def ibragimov_mueller_p(x, groups=12):
    """Split into contiguous groups, t-test the group means (one-sided, t with groups-1 df)."""
    from math import erf, sqrt
    g = np.array([c.mean() for c in np.array_split(np.asarray(x, float), groups)])
    t = g.mean() / (g.std(ddof=1) / np.sqrt(groups))
    try:
        from scipy.stats import t as tdist
        return float(tdist.sf(t, groups - 1))
    except Exception:
        return float(0.5 * (1 - erf(t / sqrt(2))))


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


def assets(b, s, spread_add=0.0, financing=None):
    """Daily simple returns of every building block on b's index."""
    gold, gkind = load_gold(b)
    A = pd.DataFrame({"SP": b["r_sp"], "CASH": b["r_cash"]})
    A["CE"] = A["CASH"]; A["CG"] = A["CASH"]
    fee2, fee3 = (SPY_FEE, SPY_FEE) if financing == "diy" else (SSO_FEE, UPRO_FEE)
    A["L15"] = lev_returns(b, 1.5, s + spread_add, fee2, financing)
    A["L2"] = lev_returns(b, 2, s + spread_add, fee2, financing)
    A["L3"] = lev_returns(b, 3, s + spread_add, fee3, financing)
    A["GOLD"] = gold
    spot = gold + GLD_FEE * b["days"] / 365
    fut = 0.9 * (spot - (b["rf"] + 0.002 + spread_add) * b["days"] / 360)
    A["GDE"] = 0.9 * b["r_idx"] + fut + 0.1 * b["r_cash"] - GDE_FEE * b["days"] / 365
    A["_GDE_ORD"] = fut + 0.1 * b["r_cash"] - GDE_FEE * b["days"] / 365   # Subpart F + interest, net of fee
    bonds = load_bonds(b)
    if bonds is not None:
        for c in bonds.columns:
            A[c] = bonds[c]
    return A, gkind


def window(A, start, end):
    """Rows from the last trading day before `start` (the purchase row) through `end`."""
    i0 = A.index.searchsorted(pd.Timestamp(start)) - 1
    return A.iloc[max(i0, 0):].loc[:end]


def run(A, W=None, cost_mult=1.0, tax=None, b=None, policy=None, cols=None, extra_cost=None):
    cols = cols or (list(W.columns) if W is not None else None)
    R = A[cols]
    cost = {c: COST[CKIND[c]] * cost_mult for c in cols}
    inc = ordn = None
    if tax is not None and b is not None and ("SP" in cols or "GDE" in cols):
        inc = pd.DataFrame(0.0, index=R.index, columns=cols)
        if "SP" in cols:
            inc["SP"] = b["r_div"].reindex(R.index)
        if "GDE" in cols:                       # GDE: dividends of its 0.9 equity sleeve, plus Subpart F income
            inc["GDE"] = 0.9 * b["r_div"].reindex(R.index)
            ordn = pd.DataFrame(0.0, index=R.index, columns=cols); ordn["GDE"] = A["_GDE_ORD"].reindex(R.index)
    return simulate(R, W, cost, kinds={c: KIND[c] for c in cols}, income=inc, tax=tax, policy=policy,
                    ordinary=ordn, extra_cost=extra_cost)


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
    se = sig_e.fillna(False).astype(bool).shift(lag).reindex(index).fillna(False).to_numpy().astype(bool)
    sg = sig_g.fillna(False).astype(bool).shift(lag).reindex(index).fillna(False).to_numpy().astype(bool)
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
    def __init__(self, audit_fix=True):
        self.audit_fix = audit_fix
        self.b = base_daily(end="2026-09-30", audit_fix=audit_fix)
        self.s, self.spread_info = fit_spread(self.b)
        self.A, self.gkind = assets(self.b, self.s)
        self.A_spread = assets(self.b, self.s, 0.005)[0]
        self.A_fin = {k: assets(self.b, self.s, financing=k)[0] for k in FINANCING}
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


def primary_tests(st, say, n=20000, seed=7):
    cash = st.b["cash_lvl"]
    prim, ps = {}, {}
    for key, (name, a, z) in PRIMARY.items():
        S = st.strategy(name, a, z); B = st.strategy("SP", a, z)
        act = active_log(S["value"], B["value"])
        p, lo, hi, _ = stationary_boot_p(act.to_numpy(), 36, n, seed=seed)
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
            pp = stationary_boot_p(post.to_numpy(), 36, 5000, seed=seed)[0]
            prim[key]["post_2016_active_%/yr"] = float(post.mean() * 1200)
            prim[key]["post_2016_p"] = pp
        ps[key] = p
        say(f"[{key}] {name} {a}..{z}: active {act.mean()*1200:+.2f}%/yr  CI [{lo*1200:+.2f},{hi*1200:+.2f}]  p {p:.4f}  "
            f"halves {h1:+.2f}/{h2:+.2f}  stress {fmt(stress)}"
            + (f"  post-2016 {prim[key]['post_2016_active_%/yr']:+.2f} (p {prim[key]['post_2016_p']:.3f})" if name in ("P3", "P5") else ""))
        say(f"     strategy {fmt(ms)}\n     S&P      {fmt(mb)}")
    adj = holm(ps)
    for k in prim:
        pr = prim[k]
        pr["p_holm"] = adj[k]
        pr["PASS"] = bool(adj[k] < 0.05 and pr["half1_%/yr"] > 0 and pr["half2_%/yr"] > 0
                          and all(v > 0 for v in pr["stress_active_%/yr"].values()))
    vt = pd.DataFrame([{"test": k, "strategy": v["strategy"], "period": v["period"], "active_%/yr": v["active_%/yr"],
                        "p": v["p_one_sided"], "p_holm": v["p_holm"], "half1": v["half1_%/yr"], "half2": v["half2_%/yr"],
                        "min_stress": min(v["stress_active_%/yr"].values()), "PASS": v["PASS"]} for k, v in prim.items()])
    say("\nVERDICTS (Holm across five):\n" + vt.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    return prim, vt


def inference_table(st):
    """Audit request: each primary test under other dependence assumptions and statistics."""
    rows = []
    for key, (name, a, z) in PRIMARY.items():
        S = st.strategy(name, a, z)["value"]; B = st.strategy("SP", a, z)["value"]
        act = active_log(S, B).to_numpy()
        ms, mb = monthly(S).pct_change().dropna(), monthly(B).pct_change().dropna()
        rc = monthly(st.b["cash_lvl"]).pct_change().reindex(ms.index).fillna(0)
        row = {"test": key, "active_%/yr": act.mean() * 1200}
        for blk in (1, 12, 36, 60):
            row[f"p_block{blk}"] = stationary_boot_p(act, blk, 5000, seed=11)[0]
        row["NW_t_12"], row["NW_t_36"] = nw_t(act, 12), nw_t(act, 36)
        row["Sharpe_gain"], row["p_Sharpe_block36"] = sharpe_diff_boot_p(ms, mb.reindex(ms.index), rc, 36, 5000, seed=11)
        row["p_IM_12groups"] = ibragimov_mueller_p(act, 12)
        rows.append(row)
    return pd.DataFrame(rows)


def _p3_window(st, a, z="2026-09-30", lag=1):
    S = st.strategy("P3", a, z, lag=lag)["value"]; B = st.strategy("SP", a, z)["value"]
    return S, B, active_log(S, B)


def p3_eras(st):
    """P3 by era: slices of the 1929 run and fresh starts (dates when instruments appeared)."""
    cash = st.b["cash_lvl"]; rows = []
    S, B, act = _p3_window(st, "1929-01-01")
    for lab, a, z in [("slice 1929-1971", "1929", "1971"), ("slice 1934-2026", "1934", "2026-09"),
                      ("slice 1972-2026", "1972", "2026-09")]:
        x = act.loc[a:z]
        rows.append({"window": lab, "active_%/yr": x.mean() * 1200, "p_block36": stationary_boot_p(x.to_numpy(), 36, 5000, seed=3)[0],
                     "p_block12": stationary_boot_p(x.to_numpy(), 12, 5000, seed=3)[0]})
    for lab, a in [("from 1972-01", "1972-01-01"), ("from 1975-05 (negotiated commissions)", "1975-05-01"),
                   ("from 1982-05 (S&P futures)", "1982-05-01"), ("from 1993-02 (SPY)", "1993-02-01"),
                   ("from 2006-07 (SSO)", "2006-07-01"), ("from 2016-01 (after publication)", "2016-01-01")]:
        S, B, x = _p3_window(st, a)
        ms, mb = monthly(S).pct_change().dropna(), monthly(B).pct_change().dropna()
        rc = monthly(cash).pct_change().reindex(ms.index).fillna(0)
        dsh, psh = sharpe_diff_boot_p(ms, mb.reindex(ms.index), rc, 36, 5000, seed=3)
        rows.append({"window": lab, "active_%/yr": x.mean() * 1200, "p_block36": stationary_boot_p(x.to_numpy(), 36, 5000, seed=3)[0],
                     "p_block12": stationary_boot_p(x.to_numpy(), 12, 5000, seed=3)[0], "Sharpe_gain": dsh, "p_Sharpe": psh})
    return pd.DataFrame(rows)


def p3_implementability(st):
    """Audit request: before May 1975 (fixed commissions; no index funds, futures or leveraged funds) 2x
    meant trading twice the portfolio in stock. Extra cost per switch = 2 x per-side stock cost."""
    A = window(st.A, "1929-01-01", "2026-09-30"); vb = bh(A)["value"]
    W = switch_weights(A.index, st.sig["eq_200d"]); rows = []
    for c in (0.0, 0.001, 0.0025, 0.005, 0.01):
        xc = pd.Series(np.where(A.index < pd.Timestamp("1975-05-01"), 2 * c, 0.0), index=A.index)
        act = active_log(run(A, W, extra_cost={"L2": xc})["value"], vb)
        rows.append({"pre1975_stock_cost_per_side_%": c * 100, "active_%/yr": act.mean() * 1200,
                     "p_block36": stationary_boot_p(act.to_numpy(), 36, 5000, seed=5)[0],
                     "active_1929_1971_%/yr": act.loc[:"1971"].mean() * 1200})
    return pd.DataFrame(rows)


def lag_profile(st):
    """P3 by execution lag (0 = trade at the signal close). Audit: the lag-1 vs lag-2 gap is mostly 1987-10-19."""
    rows = []
    for lag in range(0, 7):
        row = {"lag_days": lag}
        for a in ("1929-01-01", "1972-01-01"):
            _, _, act = _p3_window(st, a, lag=lag)
            row[f"active_from_{a[:4]}"] = act.mean() * 1200
            row[f"p_from_{a[:4]}"] = stationary_boot_p(act.to_numpy(), 36, 5000, seed=5)[0]
        rows.append(row)
    px = st.b["sp_px"]; sma = px.rolling(200).mean()
    note = {d: float(px.loc[d] / sma.loc[d] - 1) * 100 for d in ("1987-10-14", "1987-10-15", "1987-10-16")}
    return pd.DataFrame(rows), note


def p3_open_execution(st, a="1995-01-03", z="2026-09-30"):
    """P3 executed at the next day's OPEN (SPY open; overnight move at 2x, intraday at 2x after entry),
    vs the close-t+1 convention. ^GSPC opens before 2008 are not real, so only from 1995 (SPY)."""
    o = pd.read_csv(DATA / "spy_ohlc.csv", index_col=0, parse_dates=True)
    b = st.b.loc[a:z]
    c_, o_ = o["close"].reindex(b.index), o["open"].reindex(b.index)
    r_raw = c_.pct_change()
    div = ((1 + b["r_sp"]) / (1 + r_raw) - 1).fillna(0)
    r_on = (o_ / c_.shift(1)) * (1 + div) - 1
    g_full = 1 + st.A["L2"].reindex(b.index)
    g_open = 1 + 2 * r_on
    g_rest = g_full / g_open
    want = st.sig["eq_200d"].astype(bool).shift(1).reindex(b.index).fillna(False)
    prev = want.shift(1).fillna(False).astype(bool)
    cash = 1 + b["r_cash"]
    g = np.where(prev & want, g_full, np.where(prev & ~want, g_open, np.where(~prev & want, cash * g_rest, cash)))
    g = pd.Series(g, index=b.index).fillna(1.0)
    g = g * np.where(prev != want, 1 - COST["lev"], 1.0)
    g.iloc[0] = 1.0
    v_open = g.cumprod()
    vb = st.strategy("SP", a, z)["value"]
    out = {"open_t+1": float(active_log(v_open, vb).mean() * 1200)}
    for lag in (0, 1, 2):
        out[f"close_t+{lag}"] = float(active_log(st.strategy("P3", a, z, lag=lag)["value"], vb).mean() * 1200)
    for a2 in ("2006-07-01", "2016-01-01"):
        sl = v_open.loc[a2:]; vb2 = vb.loc[a2:]
        out[f"open_t+1_from_{a2[:4]}"] = float(active_log(sl, vb2).mean() * 1200)
        out[f"close_t+1_from_{a2[:4]}"] = float(active_log(st.strategy("P3", a2, z)["value"], st.strategy("SP", a2, z)["value"]).mean() * 1200)
    return out


def tax_scenarios(st):
    """Audit request: after-tax CAGR under the registered federal rates, + NIIT, + state tax, and held for heirs."""
    from dataclasses import replace
    rows = []
    for a in ("1972-01-01", "1929-01-01"):
        for lab, tx in [("federal 35/20/28 (registered)", Tax()), ("+NIIT 3.8%", Tax.scenario(True)),
                        ("+NIIT +5% state", Tax.scenario(True, 0.05)), ("+NIIT +9.3% state", Tax.scenario(True, 0.093)),
                        ("+NIIT +13.3% state", Tax.scenario(True, 0.133))]:
            for liq in (True, False):
                t = replace(tx, liquidate=liq)
                row = {"from": a[:4], "tax": lab, "sold_at_end": liq}
                for k in ("SP", "P3", "C4"):
                    if k == "C4" and a < "1972":
                        continue
                    r = st.strategy(k, a, "2026-09-30", tax=t)
                    v = r["value"]; yrs = (v.index[-1] - v.index[0]).days / 365.25
                    row[k] = ((r["after_tax"] / v.iloc[0]) ** (1 / yrs) - 1) * 100
                row["P3_minus_SP"] = row["P3"] - row["SP"]
                if "C4" in row:
                    row["C4_minus_SP"] = row["C4"] - row["SP"]
                rows.append(row)
    return pd.DataFrame(rows)


def gold_scenarios(st):
    """Forward-looking: C4's edge vs S&P if gold's (fund, log) return beat T-bills by g %/yr; the gold path keeps its
    historical shape and only its drift is shifted."""
    rows = []
    for a in ("1972-01-01", "1982-01-01"):
        z = "2026-09-30"; win = window(st.A, a, z); n_ = len(win) - 1
        hist = float(np.log1p(win["GOLD"].iloc[1:].fillna(0)).sum() - np.log1p(win["CASH"].iloc[1:]).sum())
        yrs = (win.index[-1] - win.index[0]).days / 365.25
        B = st.strategy("SP", a, z)["value"]
        row = {"window": f"{a[:4]}-2026", "historical_g_%/yr": hist / yrs * 100}
        for g in (-4, -2, 0, 2, 4, 8):
            d = (g / 100 * yrs - hist) / n_
            A2 = st.A.copy(); A2["GOLD"] = (1 + st.A["GOLD"]) * np.exp(d) - 1
            row[f"g={g:+d}"] = float(active_log(st.strategy("C4", a, z, A=A2)["value"], B).mean() * 1200)
        rows.append(row)
    return pd.DataFrame(rows)


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

    # ---------------- primary tests: original data exactly as pre-registered, then audit-corrected data
    st0 = Study(audit_fix=False)
    say("\nPRIMARY TESTS ON THE PRE-REGISTERED DATA (SteelCerberus rates as published; bootstrap 5,000 draws, seed 7)")
    prim0, vt0 = primary_tests(st0, say, n=5000)
    vt0.to_csv(OUT / "verdicts_preregistered_data.csv", index=False)
    say("\nPRIMARY TESTS, AUDIT-CORRECTED DATA (pre-1986 financing = T-bill + 0.55%, unrounded pre-1954 T-bills, "
        "GLD splice day, signal lag on full history; bootstrap 20,000 draws)")
    prim, vt = primary_tests(st, say, n=20000)
    vt.to_csv(OUT / "verdicts.csv", index=False)
    res["primary_preregistered_data"] = prim0
    res["primary"] = prim

    # ---------------- financing-model sensitivity (not pre-registered; descriptive)
    say("\nFINANCING SENSITIVITY (active %/yr vs S&P): pre-registered data | audit-corrected (primary) | rate-dependent fit to real SSO | "
        "testfol.io-style punitive | DIY futures/box (T-bill+0.3%, no fund fee)")
    fin = {}
    for key, (name, a, z) in PRIMARY.items():
        B = st.strategy("SP", a, z)
        row = {"preregistered_data": prim0[key]["active_%/yr"], "primary": prim[key]["active_%/yr"]}
        for k, A_ in st.A_fin.items():
            row[k] = float(active_log(st.strategy(name, a, z, A=A_)["value"], B["value"]).mean() * 1200)
        fin[key] = row
        say(f"  {key} {name}: {fmt(row)}")
    res["financing_sensitivity"] = fin

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
    say("\nACTUAL FUNDS 2006-07..2026-09 (SSO, GLD, SPY: daily total return, Yahoo adj_close)")
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
        p0 = pd.Period(f"{a[:4]}-01", "M") - 1                  # base = previous month-end
        g_ = monthly(gl).loc[p0:z]; c_ = monthly(cash).loc[p0:z]
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
    gv = res["gold_valuation"]
    say(f"\nGOLD VALUATION (descriptive): real gold at the {gv['current_percentile']*100:.1f}th percentile of 1968-2026, "
        f"{gv['real_gold_now_vs_1980_peak']:.2f}x the 1980 month-end real peak (about 1.2x the 1980-01-21 daily peak). "
        f"The regression of next-10-year real return on the real level (slope {gv['slope_fwd10y_per_log_unit']:.2f}, "
        f"{gv['n_nonoverlapping']} non-overlapping observations) is NOT a forecast: today's level is outside the sample, "
        f"the slope is not significant against a random-walk null (audit p about 0.1), and recursive out-of-sample R2 is negative.")

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
    say("\nACTUAL SSO + 200-DAY RULE 2006-07..2026-09 (SSO daily total return, Yahoo adj_close)")
    for k, v in res["actual_p3"].items():
        say(f"  {k}: {fmt(v)}")

    # ---------------- audit-requested robustness of P3 and inference
    inf = inference_table(st); inf.to_csv(OUT / "inference_robustness.csv", index=False)
    say("\nINFERENCE ROBUSTNESS (p one-sided; block = mean block months; NW = Newey-West t; IM = Ibragimov-Mueller, 12 groups)")
    say(inf.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    er = p3_eras(st); er.to_csv(OUT / "p3_eras.csv", index=False)
    say("\nP3 BY ERA (slices of the 1929 run; fresh starts at dates instruments appeared)")
    say(er.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    im = p3_implementability(st); im.to_csv(OUT / "p3_implementability.csv", index=False)
    say("\nP3 IMPLEMENTABILITY: extra stock trading cost before 1975-05 (2x notional per switch)")
    say(im.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    lp, note87 = lag_profile(st); lp.to_csv(OUT / "p3_lag_profile.csv", index=False)
    say("\nP3 EXECUTION LAG PROFILE (0 = trade at the signal close; the study uses 1)")
    say(lp.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    say(f"  S&P price vs its 200-day average (%): {fmt(note87)}; lag 1 exits at the 1987-10-16 close, lag 2 holds 2x through 10-19")
    oe = p3_open_execution(st); res["p3_open_execution"] = oe
    say(f"\nP3 EXECUTION AT THE NEXT OPEN vs CLOSES (active %/yr vs S&P, 1995-2026 unless noted): {fmt(oe)}")
    tx = tax_scenarios(st); tx.to_csv(OUT / "tax_scenarios.csv", index=False)
    say("\nTAX SCENARIOS (after-tax CAGR %; state tax on gains and dividends, not T-bill interest; "
        "sold_at_end False = held for heirs, basis steps up)")
    say(tx.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    gs = gold_scenarios(st); gs.to_csv(OUT / "gold_scenarios.csv", index=False)
    say("\nC4 EDGE vs S&P IF GOLD BEATS T-BILLS BY g %/yr (gold path shape kept, drift shifted)")
    say(gs.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    res.update({"inference": inf.to_dict("records"), "p3_eras": er.to_dict("records"),
                "p3_implementability": im.to_dict("records"), "p3_lag_profile": lp.to_dict("records"),
                "note_1987": note87, "tax_scenarios": tx.to_dict("records"), "gold_scenarios": gs.to_dict("records")})

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
    q = pd.read_csv(DATA / "sso_tr_daily.csv", index_col=0, parse_dates=True)["SSO_yahoo"]
    sso = q.groupby(q.index.to_period("M")).last().pct_change()
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
    """P3 on actual SSO daily total return (Yahoo adj_close, cross-checked with Tiingo), 2006-07..2026-09."""
    b = st.b.loc["2006-06-21":"2026-09-30"]
    q = pd.read_csv(DATA / "sso_tr_daily.csv", index_col=0, parse_dates=True)["SSO_yahoo"]
    r = q.reindex(b.index.union(q.index)).ffill().reindex(b.index).pct_change().fillna(0.0)
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
