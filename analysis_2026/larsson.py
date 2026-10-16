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

def rf_daily(index, ppy):
    return pd.Series([(1 + TBILL.get(d.year, 2.0) / 100) ** (1 / ppy) - 1 for d in index], index=index)


def close_engine(r_tr, r_cash, green, cost):
    """Close-only series: signal at close t, trade at close t+1, so the position earns from day t+2."""
    g = pd.Series(np.asarray(green, float), index=r_tr.index)
    w = g.shift(2).fillna(0.0)
    turn = (w - w.shift(1).fillna(0.0)).abs()
    return w * r_tr + (1 - w) * r_cash - cost * turn, int((turn > 0).sum())


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
    return {"dSharpe": float(obs), "p_one_sided": p, "half1": float(h[0]), "half2": float(h[1]),
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


def basket(data, members_by_year, cost_fn, sig_fn, years, key):
    out = []; cache = {}
    for y in years:
        rs = []
        for s in members_by_year.get(y, []):
            if s not in data:
                continue
            if (s, key) not in cache:
                d = data[s]
                cache[(s, key)] = strat_returns(d, sig_fn(d), cost_fn(s))[0] if key != "BH" else d.close.pct_change().fillna(0.0)
            x = cache[(s, key)].loc[f"{y}-01-01":f"{y}-12-31"]
            if len(x) > 20:
                rs.append(x)
        if rs:
            out.append(pd.concat(rs, axis=1, sort=True).mean(axis=1))
    return pd.concat(out).sort_index() if out else pd.Series(dtype=float)


def per_asset(items, ppy, extra_cost=None):
    """items: (class, symbol, ohlc df, cost, start). Returns rows for every signal + buy & hold."""
    rows = []
    for cls, s, d, cost, start in items:
        first = d.index[min(len(d) - 1, 120)]
        st = max(pd.Timestamp(start), first)
        rf = rf_daily(d.index, ppy)
        bh = d.close.pct_change().fillna(0.0).loc[st:"2026-09-30"]
        rows.append({"class": cls, "asset": s, "signal": "BUY & HOLD", **summarise(bh, ppy, rf, hold=True)})
        sigs = signals_ohlc(d)
        for fa, sl in PAIRS[1:]:
            sigs[f"EMA{fa}/{sl}"] = larsson(d.close, fa, sl)
        for lab, g in sigs.items():
            for c, tag in [(cost, "")] + ([(extra_cost, " @0.95%")] if extra_cost and lab in ("LARSSON", "OLD ML N=1", "OLD ML N=5") else []):
                r, tr = strat_returns(d, g, c)
                r = r.loc[st:"2026-09-30"]
                tr_in = [x for t, x in tr if st <= t <= pd.Timestamp("2026-09-30")]
                exp = float(np.r_[False, g[:-1]][(d.index >= st) & (d.index <= pd.Timestamp("2026-09-30"))].mean() * 100)
                rows.append({"class": cls, "asset": s, "signal": lab + tag, **summarise(r, ppy, rf, tr_in, {"exposure_%": exp})})
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
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    OUT.mkdir(exist_ok=True)
    lines = []

    def say(x=""):
        print(x); lines.append(str(x))

    # sanity: EMA definition = pandas ewm(span, adjust=False) (matches the exports to 0 error)
    prim, ps = {}, {}

    # ---------------- P1: S&P 500 index 1929-2026 (close-only engine, price-index signal)
    b = sp500_index()
    px, r_tr, r_cash = b["sp_px"], b["r_sp"], b["r_cash"]
    win = slice("1929-01-01", "2026-09-30")
    sig_idx = {"LARSSON": larsson(px), "LARSSON-PRICE": larsson_price(px), "SMA200": sma200(px)}
    for fa, sl in PAIRS[1:]:
        sig_idx[f"EMA{fa}/{sl}"] = larsson(px, fa, sl)
    idx_rows = []
    bh = r_tr.loc[win]
    idx_rows.append({"signal": "BUY & HOLD", **summarise(bh, 252, r_cash, hold=True)})
    curves = {"BUY & HOLD": bh}
    for lab, g in sig_idx.items():
        r, n_sw = close_engine(r_tr, r_cash, g, 0.0002)
        r = r.loc[win]; curves[lab] = r
        yrs = (r.index[-1] - r.index[0]).days / 365.25
        idx_rows.append({"signal": lab, **summarise(r, 252, r_cash, extra={"switches/yr": n_sw / ((b.index[-1] - b.index[0]).days / 365.25),
                                                                             "exposure_%": float(pd.Series(g, index=b.index).shift(2).loc[win].mean() * 100)})})
    t1 = boot_sharpe_gain(curves["LARSSON"], curves["BUY & HOLD"], r_cash.loc[win], 252, 250)
    prim["P1"] = {"test": "S&P 500 1929-2026: LARSSON vs buy & hold", **t1}; ps["P1"] = t1["p_one_sided"]
    idx_tab = pd.DataFrame(idx_rows)
    say("S&P 500 INDEX 1929-01..2026-09 (total return; price-index signal; next-close fills; 0.02%/side)")
    say(idx_tab.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    # by era / decade
    era = []
    for a, z in [("1929", "1949"), ("1950", "1971"), ("1972", "1989"), ("1990", "2007"), ("2008", "2026-09"), ("1929", "1971"), ("1972", "2026-09")]:
        row = {"era": f"{a}-{z}"}
        for lab in ("BUY & HOLD", "LARSSON", "LARSSON-PRICE", "SMA200"):
            x = curves[lab].loc[a:z]
            yrs = len(x) / 252
            row[f"{lab} CAGR"] = ((1 + x).prod() ** (1 / yrs) - 1) * 100
            row[f"{lab} Sharpe"] = sharpe(x, r_cash.loc[a:z], 252)
        era.append(row)
    era = pd.DataFrame(era)
    say("\nS&P 500 BY ERA"); say(era.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    # old MoneyLine on the index from 1963 (needs real highs/lows)
    from analysis_2026.sso_gold import gspc_ohlc
    ohlc = gspc_ohlc(b).loc["1962-01-01":]
    w63 = slice("1963-01-01", "2026-09-30")
    rows63 = [{"signal": "BUY & HOLD", **summarise(r_tr.loc[w63], 252, r_cash, hold=True)}]
    for lab, g in [("LARSSON", pd.Series(larsson(px), index=b.index)), ("OLD ML N=1", pd.Series(moneyline_delay(ohlc, 1), index=ohlc.index)),
                   ("OLD ML N=5", pd.Series(moneyline_delay(ohlc, 5), index=ohlc.index))]:
        g = g.reindex(b.index).ffill().fillna(False)
        r, _ = close_engine(r_tr, r_cash, g.to_numpy(), 0.0002)
        rows63.append({"signal": lab, **summarise(r.loc[w63], 252, r_cash)})
    t63 = pd.DataFrame(rows63)
    say("\nS&P 500 1963-2026 incl. the old MoneyLine (index highs/lows from 1962)"); say(t63.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    # pre-1928 Dow
    from analysis_2026.sso_gold import base_daily
    b0 = base_daily(start="1885-03-20", end="1927-12-30")
    w0 = slice("1886-07-01", "1927-12-30")
    rows0 = [{"signal": "BUY & HOLD", **summarise(b0["r_sp"].loc[w0], 252, b0["r_cash"], hold=True)}]
    for lab, g in [("LARSSON", larsson(b0["sp_px"])), ("SMA200", sma200(b0["sp_px"]))]:
        r, _ = close_engine(b0["r_sp"], b0["r_cash"], g, 0.0002)
        rows0.append({"signal": lab, **summarise(r.loc[w0], 252, b0["r_cash"])})
    t0 = pd.DataFrame(rows0)
    say("\nPRE-1928 DOW COMPOSITE 1886-1927 (out of sample)"); say(t0.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ---------------- ETFs and large coins (per asset)
    etf_items = [("etf13", s, load_etf(s), 0.0002, "2005-01-01") for s in ETF13]
    crypto_items = [("crypto21", s, load_crypto_daily(s), 0.0010 if s in ("BTC", "ETH") else 0.0015, "2018-01-01") for s in LARGE20 + ["ZEC"]]
    res_etf = per_asset(etf_items, 252)
    res_cry = per_asset(crypto_items, 365, extra_cost=0.0095)
    res = pd.concat([res_etf, res_cry], ignore_index=True)
    res.to_csv(OUT / "per_asset.csv", index=False)
    cs = class_summary(res, "LARSSON", ["BUY & HOLD", "OLD ML N=1", "OLD ML N=5", "SMA200", "LARSSON-PRICE"])
    say("\nPER-ASSET CLASS SUMMARY (median differences, LARSSON minus comparator; Sharpe above T-bills)")
    say(cs.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    piv = res[res.signal.isin(["BUY & HOLD", "LARSSON", "LARSSON-PRICE", "OLD ML N=1", "OLD ML N=5", "SMA200"])].pivot_table(
        index=["class", "asset"], columns="signal", values="Sharpe_xs")
    say("\nPER-ASSET SHARPE (above T-bills)"); say(piv.round(2).to_string())

    # ---------------- baskets: P2-P5
    from screener.data import from_csv_folder, quality_filter
    sp, _ = quality_filter(from_csv_folder(ROOT / "data" / "universe_pit_all"), keep_collapsed=True)
    mem = pd.read_csv(ROOT / "data" / "universe_pit_all" / "members.csv", parse_dates=["start", "end"])
    yrs_sp = list(range(2001, 2027))
    mby = {y: list(mem[(mem.start <= f"{y}-01-01") & (mem.end.isna() | (mem.end >= f"{y}-01-01"))].symbol.str.upper()) for y in yrs_sp}
    sp = {k: v for k, v in sp.items() if k != "SPY" and len(v) > 300}
    from analysis_2026.altcoins import load_crypto, tiers_for_year
    cd = load_crypto()
    yrs_c = list(range(2019, 2027)); cby = {}
    for y in yrs_c:
        t = tiers_for_year(cd, y); cby[y] = t["1-10"] + t["11-30"][:10]
    cdat = {k: v[["open", "high", "low", "close"]] for k, v in cd.items()}
    sig_fns = {"LARSSON": lambda d: larsson(d.close), "LARSSON-PRICE": lambda d: larsson_price(d.close),
               "OLD ML N=1": lambda d: moneyline_delay(d, 1), "OLD ML N=5": lambda d: moneyline_delay(d, 5), "SMA200": lambda d: sma200(d.close)}
    for fa, sl in PAIRS[1:]:
        sig_fns[f"EMA{fa}/{sl}"] = (lambda fa_, sl_: (lambda d: larsson(d.close, fa_, sl_)))(fa, sl)
    bsk = {}
    for lab in ["BH"] + list(sig_fns):
        f = sig_fns.get(lab)
        bsk[("sp", lab)] = basket(sp, mby, lambda s: 0.0003, f, yrs_sp, lab).loc[:"2026-09-30"]
        bsk[("cr", lab)] = basket(cdat, cby, lambda s: 0.0010 if s.split("#")[0] in ("BTC", "ETH") else 0.0015, f, yrs_c, lab).loc[:"2026-09-30"]
    rf_sp = rf_daily(bsk[("sp", "BH")].index, 252); rf_cr = rf_daily(bsk[("cr", "BH")].index, 365)
    brow = []
    for (u, lab), r in bsk.items():
        ppy, rf = (252, rf_sp) if u == "sp" else (365, rf_cr)
        brow.append({"basket": "S&P 500 PIT 2001-2026" if u == "sp" else "crypto top-20 2019-2026", "signal": "BUY & HOLD (EW)" if lab == "BH" else lab,
                     **summarise(r, ppy, rf, hold=(lab == "BH"))})
    btab = pd.DataFrame(brow)
    say("\nBASKETS (equal weight of each year's members; each member traded on its own signal)")
    say(btab.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    for key, (u, comp, ppy, block, rf, txt) in {
            "P2": ("sp", "BH", 252, 250, rf_sp, "S&P PIT basket: LARSSON vs EW buy & hold"),
            "P3": ("cr", "BH", 365, 180, rf_cr, "crypto top-20 basket: LARSSON vs EW buy & hold"),
            "P4": ("sp", "OLD ML N=5", 252, 250, rf_sp, "S&P PIT basket: LARSSON vs old MoneyLine N=5"),
            "P5": ("cr", "OLD ML N=1", 365, 180, rf_cr, "crypto top-20 basket: LARSSON vs old MoneyLine N=1")}.items():
        t = boot_sharpe_gain(bsk[(u, "LARSSON")], bsk[(u, comp)], rf, ppy, block, seed=int(key[1]))
        prim[key] = {"test": txt, **t}; ps[key] = t["p_one_sided"]
    adj = holm(ps)
    for k in prim:
        prim[k]["p_holm"] = adj[k]
        prim[k]["PASS"] = bool(adj[k] < 0.05 and prim[k]["half1"] > 0 and prim[k]["half2"] > 0)
    vt = pd.DataFrame([{"test": k, **{kk: v for kk, v in d.items() if kk != "ci95"}, "ci95": d["ci95"]} for k, d in prim.items()])
    say("\nPRIMARY TESTS (Sharpe gain above T-bills; paired stationary bootstrap; Holm across five)")
    say(vt.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    vt.to_csv(OUT / "verdicts.csv", index=False)
    idx_tab.to_csv(OUT / "sp500_index.csv", index=False); era.to_csv(OUT / "sp500_eras.csv", index=False)
    t63.to_csv(OUT / "sp500_1963_with_old_moneyline.csv", index=False); t0.to_csv(OUT / "dow_1886_1927.csv", index=False)
    btab.to_csv(OUT / "baskets.csv", index=False); cs.to_csv(OUT / "class_summary.csv", index=False)
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
