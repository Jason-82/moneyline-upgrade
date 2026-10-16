"""
Larsson Line (EMA 32 / EMA 58 crossover) on long histories. Pre-registration: analysis_2026/LARSSON_PREREG.md.

    python3 -m analysis_2026.larsson          # -> analysis_2026/results_larsson/

The user's TradingView "Larsson Line" plots exactly EMA(32) and EMA(58) of the close (checked on private
exports). LARSSON = long while EMA32 > EMA58 (assumed colour rule); LARSSON-PRICE = green once the close is
above both lines, red once below both. Comparators: buy & hold, the old MoneyLine as replicated
(moneyline_ref, N=1 and the 5-close delay N=5) and a 1x 200-day SMA filter.

Data (gitignored): data/sso_gold/ (S&P 500 1928-2026, see sso_gold.py), data/etf/, data/crypto_4h/ and the
Binance archive (flip_delay / altcoins loaders), data/universe_pit_all/ (point-in-time S&P 500 incl. failed
companies).

Audit additions (2026-10-16; secondary, none decides a pass): the subtracted T-bill now matches the engine's cash
leg; baskets are also built as annually rebalanced, drifting sleeves ("held"); a realisation-based tax engine
(sso_gold.simulate) for the index tables; a common 200-bar start per asset; the primary tests rerun with the
LARSSON-PRICE colour rule; fill-lag, cost and power sensitivities.
"""
from __future__ import annotations

import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.flip_delay import (ETF13, LARGE20, load_crypto_daily, load_etf, moneyline_delay,  # noqa: E402
                                      stats, strat_returns)
from screener.strictness import TBILL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis_2026" / "results_larsson"
PAIRS = [(32, 58), (20, 50), (26, 52), (40, 80), (50, 100), (50, 200)]


# ------------------------------------------------------------------ signals

def larsson(close, fast=32, slow=58):
    f = close.ewm(span=fast, adjust=False).mean(); s = close.ewm(span=slow, adjust=False).mean()
    return (f > s).to_numpy()


def larsson_price(close, fast=32, slow=58):
    f = close.ewm(span=fast, adjust=False).mean().to_numpy(); s = close.ewm(span=slow, adjust=False).mean().to_numpy()
    c = close.to_numpy(); hi, lo = np.maximum(f, s), np.minimum(f, s)
    out = np.zeros(len(c), bool); state = False
    for i in range(len(c)):
        if c[i] > hi[i]:
            state = True
        elif c[i] < lo[i]:
            state = False
        out[i] = state
    return out


def sma200(close):
    return (close > close.rolling(200, min_periods=200).mean()).to_numpy()


def signals_ohlc(df):
    c = df.close
    return {"LARSSON": larsson(c), "LARSSON-PRICE": larsson_price(c), "OLD ML N=1": moneyline_delay(df, 1),
            "OLD ML N=5": moneyline_delay(df, 5), "SMA200": sma200(c)}


# ------------------------------------------------------------------ engines and statistics

def rf_daily(index):
    """T-bill return per row, calendar-day compounded exactly as strat_returns pays the cash leg."""
    days = np.r_[1, np.diff(index.values).astype("timedelta64[D]").astype(int)]
    return pd.Series([(1 + TBILL.get(d.year, 2.0) / 100 / 365) ** k - 1 for d, k in zip(index, days)], index=index)


def close_engine(r_tr, r_cash, green, cost, lag=2):
    """Close-only series: signal at close t, trade at close t+1, so the position earns from day t+2 (lag=2).
    Returns (returns, weight earning on each day)."""
    g = pd.Series(np.asarray(green, float), index=r_tr.index)
    w = g.shift(lag).fillna(0.0)
    turn = (w - w.shift(1).fillna(0.0)).abs()
    return w * r_tr + (1 - w) * r_cash - cost * turn, w


def switches_per_yr(w, win):
    x = w.loc[win]
    return float((x.diff().abs() > 0).sum() / (len(x) / 252))


def tax_real(r_tr, r_cash, r_div, w, cost, win):
    """Secondary (audit): realisation-based after-tax CAGR via sso_gold.simulate. FIFO lots; gains held more than a
    year at 20%, otherwise 35%; dividends 20% and T-bill interest 35% every year; losses carried; sold at the end.
    w: weight earning on each day (close_engine's). The row before the window is the purchase date."""
    from analysis_2026.sso_gold import Tax, simulate
    i0 = r_tr.index.get_loc(r_tr.loc[win].index[0])
    R = pd.DataFrame({"eq": r_tr, "cash": r_cash}).iloc[max(i0 - 1, 0):].loc[:win.stop]
    ww = pd.Series(np.asarray(w, float), index=r_tr.index).reindex(R.index).fillna(0.0)
    tgt = ww.shift(-1).fillna(ww.iloc[-1])             # weight set at close i earns on day i+1
    chg = tgt.ne(tgt.shift(1)); chg.iloc[0] = True
    W = pd.DataFrame({"eq": tgt[chg], "cash": 1 - tgt[chg]})
    inc = pd.DataFrame({"eq": r_div.reindex(R.index).fillna(0.0), "cash": 0.0})
    out = simulate(R, W, {"eq": cost, "cash": 0.0}, kinds={"eq": "eq", "cash": "cash"}, income=inc, tax=Tax())
    yrs = (len(R) - 1) / 252
    return (out["after_tax"] ** (1 / yrs) - 1) * 100


def nw_alpha(r, rb, rc, lags=12):
    """Secondary (audit): monthly excess return on buy & hold's excess return; alpha %/yr and Newey-West t."""
    from analysis_2026.sso_gold import alpha_regression
    v = (1 + r).cumprod(); fac = pd.DataFrame({"bh": (1 + rb).cumprod().groupby(rb.index.to_period("M")).last().pct_change()})
    d = alpha_regression(v, fac, (1 + rc.reindex(r.index).fillna(0.0)).cumprod(), lags)
    return {"alpha_%/yr": d["alpha_%/yr"], "alpha_t": d["alpha_t"], "beta": d["beta_bh"]}


def sharpe(x, rf, ppy):
    e = (x - rf).dropna()
    return float(e.mean() / e.std() * np.sqrt(ppy)) if e.std() > 0 else np.nan


def boot_sharpe_gain(rs, rb, rf, ppy, block, n=2000, seed=0):
    """Paired stationary bootstrap of the annualised Sharpe gain; null-centred one-sided p (gain > 0)."""
    j = pd.concat([rs, rb, rf], axis=1).dropna()
    a, b, f = (j.iloc[:, k].to_numpy() for k in range(3))
    ea, eb = a - f, b - f
    obs = (ea.mean() / ea.std() - eb.mean() / eb.std()) * np.sqrt(ppy)
    T = len(a); rng = np.random.default_rng(seed); d = np.empty(n)
    for k0 in range(0, n, 250):
        m = min(250, n - k0)
        idx = np.empty((m, T), dtype=np.int64); idx[:, 0] = rng.integers(0, T, m)
        new = rng.random((m, T)) < 1.0 / block; st = rng.integers(0, T, (m, T))
        for t in range(1, T):
            idx[:, t] = np.where(new[:, t], st[:, t], (idx[:, t - 1] + 1) % T)
        xa, xb = ea[idx], eb[idx]
        d[k0:k0 + m] = (xa.mean(1) / xa.std(1) - xb.mean(1) / xb.std(1)) * np.sqrt(ppy)
    p = float(np.mean(d - obs >= obs))
    half = T // 2
    h = [(ea[s].mean() / ea[s].std() - eb[s].mean() / eb[s].std()) * np.sqrt(ppy) for s in (slice(0, half), slice(half, T))]
    sd = float(d.std())       # power (audit): gain detectable 80% of the time at alpha 0.01 (first Holm step) / 0.05
    return {"dSharpe": float(obs), "p_one_sided": p, "half1": float(h[0]), "half2": float(h[1]),
            "boot_sd": sd, "mde80_a01": (2.326 + 0.842) * sd, "mde80_a05": (1.645 + 0.842) * sd,
            "ci95": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))]}


def holm(ps):
    order = sorted(ps.items(), key=lambda kv: kv[1]); m = len(order); run = 0.0; out = {}
    for i, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - i) * p)); out[k] = run
    return out


def summarise(r, ppy, rf, trades=None, extra=None, hold=False):
    """hold=True: buy & hold is taxed once at 20% on the final gain (pre-registered), not yearly."""
    out = stats(r, ppy, trades)
    if hold and out:
        m = float((1 + r.dropna()).prod()); yrs = out["years"]
        m_tax = m - 0.20 * (m - 1) if m > 1 else m
        out["CAGR_tax_%"] = (m_tax ** (1 / yrs) - 1) * 100
    out["Sharpe_xs"] = sharpe(r, rf.reindex(r.index).fillna(0.0), ppy)
    out.update(extra or {})
    return out


# ------------------------------------------------------------------ samples

def sp500_index():
    """S&P 500 total return 1928-2026 with the price index for signals (sso_gold, audit-corrected T-bills)."""
    from analysis_2026.sso_gold import base_daily
    b = base_daily(end="2026-09-30")
    return b


def basket_members(data, members_by_year, cost_fn, sig_fn, years, key):
    """Per year, a frame of each member's daily returns (traded on its own signal; key 'BH' = held).
    cost_fn(symbol, year) is the cost per side."""
    out = {}; cache = {}; sig = {}
    for y in years:
        cols = {}
        for s in members_by_year.get(y, []):
            if s not in data:
                continue
            c = cost_fn(s, y)
            if (s, c) not in cache:
                d = data[s]
                if key == "BH":
                    cache[(s, c)] = d.close.pct_change().fillna(0.0)
                else:
                    if s not in sig:
                        sig[s] = sig_fn(d)
                    cache[(s, c)] = strat_returns(d, sig[s], c)[0]
            x = cache[(s, c)].loc[f"{y}-01-01":f"{y}-12-31"]
            if len(x) > 20:
                cols[s] = x
        if cols:
            out[y] = pd.concat(cols, axis=1, sort=True)
    return out


def basket(mats, how="daily"):
    """Equal weight of each year's members. how='daily': rebalanced to equal weight every day (the pre-registered
    construction, inherited from flip_delay). how='held' (audit): equal money in each member's sleeve on the year's
    first day, then each sleeve drifts; a sleeve without data (listed late or ended) sits in T-bills."""
    out = []
    for y, M in mats.items():
        if how == "daily":
            out.append(M.mean(axis=1))
        else:
            cash = rf_daily(M.index)
            V = (1 + M.apply(lambda col: col.fillna(cash))).cumprod().mean(axis=1)
            out.append(V / V.shift(1).fillna(1.0) - 1)
    return pd.concat(out).sort_index() if out else pd.Series(dtype=float)


def per_asset(items, ppy, extra_cost=None, warmups=(120, 200)):
    """items: (class, symbol, ohlc df, cost, start). Returns rows for every signal + buy & hold, once per warm-up
    (120 bars pre-registered; 200 = a common start once SMA200 exists, audit)."""
    rows = []
    end = pd.Timestamp("2026-09-30")
    for cls, s, d, cost, start in items:
        rf = rf_daily(d.index)
        sigs = signals_ohlc(d)
        for fa, sl in PAIRS[1:]:
            sigs[f"EMA{fa}/{sl}"] = larsson(d.close, fa, sl)
        runs = {"BUY & HOLD": (d.close.pct_change().fillna(0.0), None, None)}
        for lab, g in sigs.items():
            extra = [(extra_cost, " @0.95%")] if extra_cost and not lab.startswith("EMA") else []
            for c, tag in [(cost, "")] + extra:
                r, tr = strat_returns(d, g, c)
                runs[lab + tag] = (r, tr, g)
        for wu in warmups:
            st = max(pd.Timestamp(start), d.index[min(len(d) - 1, wu)])
            base = {"class": cls, "asset": s, "warmup": wu}
            for lab, (r, tr, g) in runs.items():
                rr = r.loc[st:end]
                if g is None:
                    rows.append({**base, "signal": lab, **summarise(rr, ppy, rf, hold=True)})
                    continue
                tr_in = [x for t, x in tr if st <= t <= end]
                exp = float(np.r_[False, g[:-1]][(d.index >= st) & (d.index <= end)].mean() * 100)
                rows.append({**base, "signal": lab, **summarise(rr, ppy, rf, tr_in, {"exposure_%": exp})})
    return pd.DataFrame(rows)


def class_summary(res, base_sig, comp_sigs):
    out = []
    for cls, g in res.groupby("class"):
        base = g[g.signal == base_sig].set_index("asset")
        for c in comp_sigs:
            x = g[g.signal == c].set_index("asset")
            dS = (base.Sharpe_xs - x.Sharpe_xs.reindex(base.index)).dropna()
            dC = (base["CAGR_%"] - x["CAGR_%"].reindex(base.index)).dropna()
            dT = (base["CAGR_tax_%"] - x["CAGR_tax_%"].reindex(base.index)).dropna()
            dD = (base["maxDD_%"] - x["maxDD_%"].reindex(base.index)).dropna()
            k, m = int((dS > 0).sum()), len(dS)
            p = sum(comb(m, j) for j in range(k, m + 1)) / 2 ** m if m else np.nan
            out.append({"class": cls, "comparison": f"{base_sig} minus {c}", "assets": m, "Sharpe_better": f"{k}/{m}", "sign_p": p,
                        "median_dSharpe": dS.median(), "median_dCAGR": dC.median(), "median_dCAGR_tax": dT.median(),
                        "median_dMaxDD": dD.median()})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ main

def main():
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 50)
    OUT.mkdir(exist_ok=True)
    lines = []

    def say(x=""):
        print(x); lines.append(str(x))

    def fmt(n):
        return lambda x: f"{x:,.{n}f}"

    # sanity: EMA definition = pandas ewm(span, adjust=False) (matches the exports to 0 error)
    prim, ps = {}, {}
    sec = []                                   # secondary tests (audit), never decide a pass

    # ---------------- P1: S&P 500 index 1929-2026 (close-only engine, price-index signal)
    b = sp500_index()
    px, r_tr, r_cash, r_div = b["sp_px"], b["r_sp"], b["r_cash"], b["r_div"]
    win = slice("1929-01-01", "2026-09-30")
    sig_idx = {"LARSSON": larsson(px), "LARSSON-PRICE": larsson_price(px), "SMA200": sma200(px)}
    for fa, sl in PAIRS[1:]:
        sig_idx[f"EMA{fa}/{sl}"] = larsson(px, fa, sl)
    idx_rows = []
    bh = r_tr.loc[win]
    idx_rows.append({"signal": "BUY & HOLD", **summarise(bh, 252, r_cash, hold=True),
                     "CAGR_tax_real_%": tax_real(r_tr, r_cash, r_div, np.ones(len(r_tr)), 0.0002, win)})
    curves = {"BUY & HOLD": bh}
    for lab, g in sig_idx.items():
        r, w = close_engine(r_tr, r_cash, g, 0.0002)
        r = r.loc[win]; curves[lab] = r
        idx_rows.append({"signal": lab, **summarise(r, 252, r_cash, extra={"switches/yr": switches_per_yr(w, win),
                                                                             "exposure_%": float(w.loc[win].mean() * 100)}),
                         "CAGR_tax_real_%": tax_real(r_tr, r_cash, r_div, w, 0.0002, win), **nw_alpha(r, bh, r_cash)})
    t1 = boot_sharpe_gain(curves["LARSSON"], curves["BUY & HOLD"], r_cash.loc[win], 252, 250)
    prim["P1"] = {"test": "S&P 500 1929-2026: LARSSON vs buy & hold", **t1}; ps["P1"] = t1["p_one_sided"]
    idx_tab = pd.DataFrame(idx_rows)
    say("S&P 500 INDEX 1929-01..2026-09 (total return; price-index signal; next-close fills; 0.02%/side)")
    say("  CAGR_tax_% = pre-registered (strategies 35% on each year's growth; buy & hold 20% once at the end, so its dividends")
    say("  are never taxed yearly). CAGR_tax_real_% = audit: FIFO lots, >1y gains 20% else 35%, dividends 20% and T-bill")
    say("  interest 35% yearly, losses carried, sold at the end. alpha/beta: monthly regression on buy & hold, NW(12) t.")
    say(idx_tab.to_string(index=False, float_format=fmt(2)))
    # by era / decade
    era = []
    for a, z in [("1929", "1949"), ("1950", "1971"), ("1972", "1989"), ("1990", "2007"), ("2008", "2026-09"), ("1929", "1971"), ("1972", "2026-09")]:
        row = {"era": f"{a}-{z}"}
        for lab in ("BUY & HOLD", "LARSSON", "LARSSON-PRICE", "SMA200"):
            x = curves[lab].loc[a:z]
            yrs = len(x) / 252
            row[f"{lab} CAGR"] = ((1 + x).prod() ** (1 / yrs) - 1) * 100
            row[f"{lab} Sharpe_xs"] = sharpe(x, r_cash.loc[a:z], 252)
        era.append(row)
    era = pd.DataFrame(era)
    say("\nS&P 500 BY ERA (Sharpe above T-bills)"); say(era.to_string(index=False, float_format=fmt(2)))
    # fill-lag sensitivity (audit): the reported maxDD depends on the exact fill day
    lagrows = []
    for lab in ("LARSSON", "LARSSON-PRICE", "SMA200"):
        for lag, txt in [(1, "close t (MOC at the signal close)"), (2, "close t+1 (as run)"), (3, "close t+2"), (4, "close t+3")]:
            r, _ = close_engine(r_tr, r_cash, sig_idx[lab], 0.0002, lag=lag)
            s_ = summarise(r.loc[win], 252, r_cash)
            lagrows.append({"signal": lab, "fill": txt, "CAGR_%": s_["CAGR_%"], "Sharpe_xs": s_["Sharpe_xs"], "maxDD_%": s_["maxDD_%"]})
    lagtab = pd.DataFrame(lagrows)
    say("\nS&P 500 1929-2026 BY FILL DAY (signal at close t)"); say(lagtab.to_string(index=False, float_format=fmt(2)))
    # old MoneyLine on the index from 1963 (needs real highs/lows)
    from analysis_2026.sso_gold import gspc_ohlc
    ohlc = gspc_ohlc(b).loc["1962-01-01":]
    w63 = slice("1963-01-01", "2026-09-30")
    rows63 = [{"signal": "BUY & HOLD", **summarise(r_tr.loc[w63], 252, r_cash, hold=True),
               "CAGR_tax_real_%": tax_real(r_tr, r_cash, r_div, np.ones(len(r_tr)), 0.0002, w63)}]
    for lab, g in [("LARSSON", pd.Series(larsson(px), index=b.index)), ("LARSSON-PRICE", pd.Series(larsson_price(px), index=b.index)),
                   ("SMA200", pd.Series(sma200(px), index=b.index)), ("OLD ML N=1", pd.Series(moneyline_delay(ohlc, 1), index=ohlc.index)),
                   ("OLD ML N=5", pd.Series(moneyline_delay(ohlc, 5), index=ohlc.index))]:
        g = g.reindex(b.index).ffill().fillna(False)
        r, w = close_engine(r_tr, r_cash, g.to_numpy(), 0.0002)
        rows63.append({"signal": lab, **summarise(r.loc[w63], 252, r_cash, extra={"switches/yr": switches_per_yr(w, w63)}),
                       "CAGR_tax_real_%": tax_real(r_tr, r_cash, r_div, w, 0.0002, w63)})
    t63 = pd.DataFrame(rows63)
    say("\nS&P 500 1963-2026 incl. the old MoneyLine (index highs/lows from 1962)"); say(t63.to_string(index=False, float_format=fmt(2)))
    # pre-1928 Dow
    from analysis_2026.sso_gold import base_daily
    b0 = base_daily(start="1885-03-20", end="1927-12-30")
    w0 = slice("1886-07-01", "1927-12-30")     # first close 1885-03-20; the window starts once SMA200 is warm
    rows0 = [{"signal": "BUY & HOLD", **summarise(b0["r_sp"].loc[w0], 252, b0["r_cash"], hold=True),
              "CAGR_tax_real_%": tax_real(b0["r_sp"], b0["r_cash"], b0["r_div"], np.ones(len(b0)), 0.0002, w0)}]
    for lab, g in [("LARSSON", larsson(b0["sp_px"])), ("LARSSON-PRICE", larsson_price(b0["sp_px"])), ("SMA200", sma200(b0["sp_px"]))]:
        r, w = close_engine(b0["r_sp"], b0["r_cash"], g, 0.0002)
        rows0.append({"signal": lab, **summarise(r.loc[w0], 252, b0["r_cash"]),
                      "CAGR_tax_real_%": tax_real(b0["r_sp"], b0["r_cash"], b0["r_div"], w, 0.0002, w0)})
    t0 = pd.DataFrame(rows0)
    say("\nPRE-1928 DOW COMPOSITE 1886-07..1927 (out of sample; 'years' = bars/252, the 1880s-1920s had Saturday sessions)")
    say(t0.to_string(index=False, float_format=fmt(2)))

    # ---------------- ETFs and large coins (per asset)
    etf_items = [("etf13", s, load_etf(s), 0.0002, "2005-01-01") for s in ETF13]
    crypto_items = [("crypto21", s, load_crypto_daily(s), 0.0010 if s in ("BTC", "ETH") else 0.0015, "2018-01-01") for s in LARGE20 + ["ZEC"]]
    res_etf = per_asset(etf_items, 252)
    res_cry = per_asset(crypto_items, 365, extra_cost=0.0095)
    res_all = pd.concat([res_etf, res_cry], ignore_index=True)
    res_all.to_csv(OUT / "per_asset.csv", index=False)
    res = res_all[res_all.warmup == 120]
    comps = ["BUY & HOLD", "OLD ML N=1", "OLD ML N=5", "SMA200", "LARSSON-PRICE"]
    cs = class_summary(res, "LARSSON", comps)
    say("\nPER-ASSET CLASS SUMMARY (median differences, LARSSON minus comparator; Sharpe above T-bills; 120-bar warm-up)")
    say("  crypto21 = coins still trading in 2026 (survivors); only the P3 basket corrects for dead coins")
    say(cs.to_string(index=False, float_format=fmt(3)))
    cs200 = class_summary(res_all[res_all.warmup == 200], "LARSSON", comps)
    say("\nSAME, COMMON 200-BAR START (audit: SMA200 has no value before bar 200, so it sat in T-bills for bars 120-199)")
    say(cs200.to_string(index=False, float_format=fmt(3)))
    main_sigs = ["BUY & HOLD", "LARSSON", "LARSSON-PRICE", "OLD ML N=1", "OLD ML N=5", "SMA200"]
    lev = (res_all[res_all.signal.isin(main_sigs + [x + " @0.95%" for x in main_sigs[1:]])]
           .groupby(["class", "warmup", "signal"])[["CAGR_%", "CAGR_tax_%", "Sharpe_xs", "maxDD_%"]].median().reset_index())
    say("\nPER-ASSET MEDIAN LEVELS (a gap between medians is not the median gain; see the class summaries)")
    say(lev.to_string(index=False, float_format=fmt(2)))
    piv = res[res.signal.isin(main_sigs)].pivot_table(index=["class", "asset"], columns="signal", values="Sharpe_xs")
    say("\nPER-ASSET SHARPE (above T-bills; 120-bar warm-up)"); say(piv.round(2).to_string())

    # ---------------- baskets: P2-P5
    from screener.data import from_csv_folder, quality_filter
    sp, _ = quality_filter(from_csv_folder(ROOT / "data" / "universe_pit_all"), keep_collapsed=True)
    mem = pd.read_csv(ROOT / "data" / "universe_pit_all" / "members.csv", parse_dates=["start", "end"])
    yrs_sp = list(range(2001, 2027))
    mby = {y: list(mem[(mem.start <= f"{y}-01-01") & (mem.end.isna() | (mem.end >= f"{y}-01-01"))].symbol.str.upper()) for y in yrs_sp}
    sp = {k: v for k, v in sp.items() if k != "SPY" and len(v) > 300}
    from analysis_2026.altcoins import load_crypto, tiers_for_year
    cd = load_crypto()
    yrs_c = list(range(2019, 2027)); cby, top10 = {}, {}
    for y in yrs_c:
        t = tiers_for_year(cd, y); cby[y] = t["1-10"] + t["11-30"][:10]; top10[y] = set(t["1-10"])
    cdat = {k: v[["open", "high", "low", "close"]] for k, v in cd.items()}
    sig_fns = {"LARSSON": lambda d: larsson(d.close), "LARSSON-PRICE": lambda d: larsson_price(d.close),
               "OLD ML N=1": lambda d: moneyline_delay(d, 1), "OLD ML N=5": lambda d: moneyline_delay(d, 5), "SMA200": lambda d: sma200(d.close)}
    for fa, sl in PAIRS[1:]:
        sig_fns[f"EMA{fa}/{sl}"] = (lambda fa_, sl_: (lambda d: larsson(d.close, fa_, sl_)))(fa, sl)
    cost_cr = {"study": lambda s, y: 0.0010 if s.split("#")[0] in ("BTC", "ETH") else 0.0015,
               "retail": lambda s, y: 0.0030 if s in top10[y] else 0.0035,          # altcoins.py COSTS['retail']
               "0.95%": lambda s, y: 0.0095}
    bsk = {}
    for lab in ["BH"] + list(sig_fns):
        f = sig_fns.get(lab)
        m_sp = basket_members(sp, mby, lambda s, y: 0.0003, f, yrs_sp, lab)
        for cname, cf in cost_cr.items():
            if cname != "study" and lab not in ("LARSSON", "LARSSON-PRICE", "OLD ML N=1", "OLD ML N=5", "SMA200"):
                continue
            m_cr = basket_members(cdat, cby, cf, f, yrs_c, lab)
            for how in ("daily", "held"):
                bsk[("cr", lab, how, cname)] = basket(m_cr, how).loc[:"2026-09-30"]
        for how in ("daily", "held"):
            bsk[("sp", lab, how, "study")] = basket(m_sp, how).loc[:"2026-09-30"]
    rf_sp = rf_daily(bsk[("sp", "BH", "daily", "study")].index); rf_cr = rf_daily(bsk[("cr", "BH", "daily", "study")].index)
    brow = []
    for (u, lab, how, cname), r in bsk.items():
        ppy, rf = (252, rf_sp) if u == "sp" else (365, rf_cr)
        brow.append({"basket": "S&P 500 PIT 2001-2026" if u == "sp" else "crypto top-20 2019-2026",
                     "construction": "daily-rebalanced EW" if how == "daily" else "held (annual EW, drifting)", "costs": cname,
                     "signal": "BUY & HOLD (EW)" if lab == "BH" else lab, **summarise(r, ppy, rf, hold=(lab == "BH"))})
    btab = pd.DataFrame(brow)
    cols_b = ["basket", "signal", "CAGR_%", "Sharpe", "maxDD_%", "years", "CAGR_tax_%", "Sharpe_xs"]
    for how, txt in [("daily-rebalanced EW", "pre-registered construction: equal weight every day (each member on its own signal)"),
                     ("held (annual EW, drifting)", "audit: equal money per member on 1 January, then each sleeve drifts")]:
        say(f"\nBASKETS, {how.upper()} ({txt}; study costs)")
        say(btab[(btab.construction == how) & (btab.costs == "study")][cols_b].to_string(index=False, float_format=fmt(2)))
    say("\nCRYPTO BASKET COST SENSITIVITY (retail = altcoins.py 0.30% top 10 / 0.35% ranks 11-20; 0.95% = Robinhood-like)")
    cc = btab[(btab.basket.str.startswith("crypto")) & (btab.signal != "BUY & HOLD (EW)") &
              btab.signal.isin(["LARSSON", "LARSSON-PRICE", "OLD ML N=1", "OLD ML N=5", "SMA200"])]
    say(cc.pivot_table(index=["construction", "signal"], columns="costs", values="Sharpe_xs")[["study", "retail", "0.95%"]]
        .round(3).to_string())
    say(cc.pivot_table(index=["construction", "signal"], columns="costs", values="CAGR_tax_%")[["study", "retail", "0.95%"]]
        .round(2).to_string())

    def G(u, lab, how="daily", cname="study"):
        return bsk[(u, lab, how, cname)]
    tests = {"P2": ("sp", "BH", 252, 250, rf_sp, "S&P PIT basket: {} vs EW buy & hold"),
             "P3": ("cr", "BH", 365, 180, rf_cr, "crypto top-20 basket: {} vs EW buy & hold"),
             "P4": ("sp", "OLD ML N=5", 252, 250, rf_sp, "S&P PIT basket: {} vs old MoneyLine N=5"),
             "P5": ("cr", "OLD ML N=1", 365, 180, rf_cr, "crypto top-20 basket: {} vs old MoneyLine N=1")}
    for key, (u, comp, ppy, block, rf, txt) in tests.items():
        t = boot_sharpe_gain(G(u, "LARSSON"), G(u, comp), rf, ppy, block, seed=int(key[1]))
        prim[key] = {"test": txt.format("LARSSON"), **t}; ps[key] = t["p_one_sided"]
    adj = holm(ps)
    for k in prim:
        prim[k]["p_holm"] = adj[k]
        prim[k]["PASS"] = bool(adj[k] < 0.05 and prim[k]["half1"] > 0 and prim[k]["half2"] > 0)
    vt = pd.DataFrame([{"test": k, **{kk: v for kk, v in d.items() if kk != "ci95"}, "ci95": d["ci95"]} for k, d in prim.items()])
    say("\nPRIMARY TESTS (Sharpe gain above T-bills; paired stationary bootstrap; Holm across five)")
    say("  mde80_a01 / a05 = Sharpe gain the test would detect 80% of the time at alpha 0.01 (first Holm step) / 0.05")
    say(vt.to_string(index=False, float_format=fmt(4)))

    # ---------------- secondary tests (audit): held baskets, the LARSSON-PRICE colour rule, costs
    def add(family, key, test, t):
        sec.append({"family": family, "key": key, "test": test, **{k: v for k, v in t.items() if k != "ci95"}, "ci95": t["ci95"]})
    for key, (u, comp, ppy, block, rf, txt) in tests.items():
        add("LARSSON, held baskets", key, txt.format("LARSSON") + " [held]",
            boot_sharpe_gain(G(u, "LARSSON", "held"), G(u, comp, "held"), rf, ppy, block, seed=int(key[1])))
    add("LARSSON-PRICE as the test rule", "P1", "S&P 500 1929-2026: LARSSON-PRICE vs buy & hold",
        boot_sharpe_gain(curves["LARSSON-PRICE"], curves["BUY & HOLD"], r_cash.loc[win], 252, 250))
    for key, (u, comp, ppy, block, rf, txt) in tests.items():
        add("LARSSON-PRICE as the test rule", key, txt.format("LARSSON-PRICE"),
            boot_sharpe_gain(G(u, "LARSSON-PRICE"), G(u, comp), rf, ppy, block, seed=int(key[1])))
    for how, cname in [("held", "study"), ("daily", "retail"), ("held", "retail"), ("daily", "0.95%")]:
        add("LARSSON-PRICE P3 robustness", "P3", f"crypto basket: LARSSON-PRICE vs EW buy & hold [{how}, {cname} costs]",
            boot_sharpe_gain(G("cr", "LARSSON-PRICE", how, cname), G("cr", "BH", how), rf_cr, 365, 180, seed=3))
    add("LARSSON-PRICE P3 robustness", "-", "crypto basket: LARSSON-PRICE vs LARSSON [daily, study costs]",
        boot_sharpe_gain(G("cr", "LARSSON-PRICE"), G("cr", "LARSSON"), rf_cr, 365, 180, seed=3))
    st = pd.DataFrame(sec)
    for fam in ("LARSSON, held baskets", "LARSSON-PRICE as the test rule"):
        m = st.family == fam
        a = holm(dict(zip(st[m].key, st[m].p_one_sided)))
        st.loc[m, "p_holm"] = st[m].key.map(a)
        st.loc[m, "would_pass"] = (st.loc[m, "p_holm"] < 0.05) & (st[m].half1 > 0) & (st[m].half2 > 0)
    say("\nSECONDARY TESTS (audit; not pre-registered, never decide a pass; Holm within each five-test family)")
    say(st.drop(columns=["ci95"]).to_string(index=False, float_format=fmt(4)))

    vt.to_csv(OUT / "verdicts.csv", index=False); st.to_csv(OUT / "secondary_tests.csv", index=False)
    idx_tab.to_csv(OUT / "sp500_index.csv", index=False); era.to_csv(OUT / "sp500_eras.csv", index=False)
    lagtab.to_csv(OUT / "sp500_fill_lag.csv", index=False)
    t63.to_csv(OUT / "sp500_1963_with_old_moneyline.csv", index=False); t0.to_csv(OUT / "dow_1886_1927.csv", index=False)
    btab.to_csv(OUT / "baskets.csv", index=False)
    cs.to_csv(OUT / "class_summary.csv", index=False); cs200.to_csv(OUT / "class_summary_start200.csv", index=False)
    lev.to_csv(OUT / "per_asset_medians.csv", index=False)
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
