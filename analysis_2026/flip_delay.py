"""
Flip-confirmation delay (Ivan's new indicator update): instead of flipping on the first
close beyond the trailing line, the indicator waits until price has closed beyond the
line for N consecutive bars (the hourglass "3/5"). Does any delay N = 1..10 beat the
immediate flip (N = 1, the indicator tested everywhere else in this repo)?

Delayed rule (built on moneyline_ref's exact reset-on-flip ATR stop, ATR10 x 2 on hl2):
  - the line keeps trailing under the CURRENT colour's rule while a flip is pending
    (green: line = max(line, hl2 - 2 ATR); red: line = min(line, hl2 + 2 ATR));
  - each close beyond the line adds 1 to the count; a close back inside resets it to 0;
  - on the N-th consecutive close beyond, the colour flips and the line restarts at
    that bar's fresh band (as on an immediate flip).
  N = 1 reproduces moneyline_ref exactly (checked in main()).
  Variant 'frozen': the flip point is fixed at the line's value on the first crossing
  bar instead of trailing (reported as a check; Ivan's exact rule isn't published).

Trading (as elsewhere): long while green, cash (T-bills) while red; the signal is
read at a bar's close and traded at the next bar's open. Costs per side: crypto 0.10%
(+0.05% for coins other than BTC/ETH), ETFs 0.02%, stocks 0.03%. After-tax: realised
gains netted each calendar year at an illustrative 35% (losses carried forward).

Assets (gitignored data):
  crypto20   20 large coins + ZEC, Binance daily (4h data resampled; ZEC daily file)
  cryptoU    each year's top 20 coins by prior 90-day volume, delisted coins included
             (equal-weight basket per year)
  etf13      SPY QQQ IWM EFA EEM TLT IEF TIP LQD HYG GLD SLV VNQ (total return)
  user       TSLA HOOD COIN CRCL MSTR NVDA PLTR (+ SPY QQQ IWM BTC ETH SOL BNB ZEC)
  sp500      point-in-time S&P 500 members each year incl. later-failed companies
             (equal-weight basket per year; data/universe_pit_all)
  weekly     SPY QQQ IWM BTC ETH on weekly bars

Pre-registered hypotheses (written 2026-10-14, before any run):
  D1 (mechanical) trades per year fall as N rises.
  D2 (PRIMARY) N=5, Ivan's new setting, vs N=1: in each of crypto20, etf13 and the
     sp500 basket, is the delay better? Per-asset classes: median change in Sharpe > 0
     AND more than half of assets improve (sign test p < 0.05). sp500 and cryptoU:
     basket Sharpe and CAGR higher with N=5. The delay "helps" if it passes in at least
     2 of the 3 primary classes (crypto20, etf13, sp500).
  D3 Longer delays make losing trades deeper (exits come later) while cutting the
     share of whipsaw trades (closed within +/-2%).
  The N = 1..10 curve, the 'frozen' variant, weekly bars and after-tax figures are
  exploratory.

    python -m analysis_2026.flip_delay
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import atr as ml_atr, moneyline, to_weekly  # noqa: E402
from screener.strictness import TBILL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis_2026" / "results_delay"
DELAYS = list(range(1, 11))
LARGE20 = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "LINK", "AVAX", "DOT", "LTC", "TRX", "BCH",
           "ATOM", "ETC", "XLM", "NEAR", "FIL", "UNI", "MATIC"]
ETF13 = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "TIP", "LQD", "HYG", "GLD", "SLV", "VNQ"]
USER_STOCKS = ["TSLA", "HOOD", "COIN", "CRCL", "MSTR", "NVDA", "PLTR"]
ST = 0.35


# ------------------------------------------------------------------ indicator

def moneyline_delay(df, n=1, frozen=False, period=10, factor=2.0):
    """Green/red state of the reset-on-flip ATR stop with an N-bar flip confirmation."""
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    s = (h + l) / 2.0
    a = ml_atr(h, l, c, period, "rma")
    lo_raw, hi_raw = s - factor * a, s + factor * a
    m = len(c)
    green = np.zeros(m, bool); line = np.full(m, np.nan)
    started = False; is_green = True; stop = np.nan; count = 0; fixed = np.nan
    for i in range(m):
        if np.isnan(a[i]):
            continue
        if not started:
            is_green = c[i] >= s[i]; stop = lo_raw[i] if is_green else hi_raw[i]; started = True
        else:
            stop = max(stop, lo_raw[i]) if is_green else min(stop, hi_raw[i])
            ref = fixed if (frozen and count > 0) else stop
            beyond = (c[i] < ref) if is_green else (c[i] > ref)
            if beyond:
                if count == 0:
                    fixed = stop
                count += 1
                if count >= n:
                    is_green = not is_green
                    stop = lo_raw[i] if is_green else hi_raw[i]
                    count = 0
            else:
                count = 0
        line[i] = stop; green[i] = is_green
    return green


# ------------------------------------------------------------------ engine

def strat_returns(df, green, cost):
    """Daily returns: long while green at the previous close (entry at next open), cash
    at T-bills otherwise. Returns (returns Series, trades list of net returns, per-year
    realised P&L fraction for tax)."""
    o, c = df.open.to_numpy(float), df.close.to_numpy(float)
    idx = df.index
    days = np.r_[1, np.diff(idx.values).astype("timedelta64[D]").astype(int)]
    tb = np.array([(1 + TBILL.get(d.year, 2.0) / 100 / 365) ** k - 1 for d, k in zip(idx, days)])
    held = np.r_[False, green[:-1]]
    prev = np.r_[False, held[:-1]]
    r = np.empty(len(c))
    for i in range(len(c)):
        if i == 0:
            r[i] = 0.0; continue
        if held[i] and prev[i]:
            r[i] = c[i] / c[i - 1] - 1
        elif held[i]:
            r[i] = (1 - cost) * c[i] / o[i] - 1
        elif prev[i]:
            r[i] = (1 - cost) * o[i] / c[i - 1] * (1 + tb[i]) - 1
        else:
            r[i] = tb[i]
    # trades (net return of each round trip) for whipsaw / loss-depth statistics
    trades = []; cur = None
    for i in range(1, len(c)):
        if held[i]:
            cur = (1.0 if cur is None else cur) * (1 + r[i])
        elif cur is not None:
            cur *= 1 + r[i]; trades.append((idx[i], cur - 1)); cur = None
    return pd.Series(r, index=idx), trades


def stats(r, ppy, trades=None):
    r = r.dropna()
    if len(r) < ppy / 2:
        return {}
    eq = (1 + r).cumprod(); yrs = len(r) / ppy
    out = {"CAGR_%": (eq.iloc[-1] ** (1 / yrs) - 1) * 100, "Sharpe": r.mean() / r.std() * np.sqrt(ppy) if r.std() > 0 else np.nan,
           "maxDD_%": float((eq / eq.cummax() - 1).min() * 100), "years": yrs}
    # after tax: yearly growth taxed at 35% on positive net (all short-term), losses carried
    v, carry = 1.0, 0.0
    for _, x in r.groupby(r.index.year):
        g = v * ((1 + x).prod() - 1); net = g + carry
        tax = ST * net if net > 0 else 0.0; carry = 0.0 if net > 0 else net; v += g - tax
    out["CAGR_tax_%"] = (v ** (1 / yrs) - 1) * 100 if v > 0 else -100.0
    if trades is not None:
        t = np.array(trades)
        out.update({"trades_per_yr": len(t) / yrs, "whipsaw_%": float((np.abs(t) < 0.02).mean() * 100) if len(t) else np.nan,
                    "avg_loss_%": float(t[t < 0].mean() * 100) if (t < 0).any() else np.nan,
                    "avg_win_%": float(t[t > 0].mean() * 100) if (t > 0).any() else np.nan,
                    "win_%": float((t > 0).mean() * 100) if len(t) else np.nan})
    return out


def run_asset(df, cost, ppy, start, end, frozen=False):
    rows = []
    for n in DELAYS:
        g = moneyline_delay(df, n, frozen)
        r, tr = strat_returns(df, g, cost)
        r = r.loc[start:end]
        tr_in = [x for t, x in tr if pd.Timestamp(start) <= t <= pd.Timestamp(end)]   # trades closed in the window
        exp = float(np.r_[False, g[:-1]][(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))].mean() * 100)
        rows.append({"N": n, **stats(r, ppy, tr_in), "exposure_%": exp})
    seg = df.loc[start:end]
    bh = seg.close.pct_change().fillna(0)
    rows.append({"N": "B&H", **stats(bh, ppy)})
    return rows


# ------------------------------------------------------------------ data

def load_crypto_daily(sym):
    if sym == "ZEC":
        from analysis_2026.altcoins import load_crypto
        return load_crypto()["ZEC"][["open", "high", "low", "close"]]
    from analysis_2026.leverage_breakout import load_4h, to_daily
    return to_daily(load_4h(sym))


def load_etf(name):
    p = ROOT / "data" / "etf" / f"{name}.csv"
    if p.exists():
        return pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()[["open", "high", "low", "close"]]
    d = pd.read_csv(ROOT / "data" / "etf" / f"O_{name}.csv", parse_dates=["Date"]).dropna(subset=["Close", "Adj Close"])
    d = d.set_index("Date").sort_index()
    k = d["Adj Close"] / d["Close"]
    return pd.DataFrame({"open": d.Open * k, "high": d.High * k, "low": d.Low * k, "close": d["Adj Close"]}).dropna()


def basket(data, members_by_year, cost_fn, n, frozen=False, years=None):
    """Equal-weight (daily-rebalanced) basket of each year's members trading the delayed signal."""
    out = []
    cache = {}
    for y in years:
        mem = [s for s in members_by_year.get(y, []) if s in data]
        rs = []
        for s in mem:
            if (s, n) not in cache:
                d = data[s]
                cache[(s, n)] = strat_returns(d, moneyline_delay(d, n, frozen), cost_fn(s))[0]
            x = cache[(s, n)].loc[f"{y}-01-01":f"{y}-12-31"]
            if len(x) > 20:
                rs.append(x)
        if rs:
            out.append(pd.concat(rs, axis=1, sort=True).mean(axis=1))
    return pd.concat(out).sort_index() if out else pd.Series(dtype=float)


def main():
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    OUT.mkdir(exist_ok=True)
    # N=1 must reproduce moneyline_ref exactly
    chk = load_etf("SPY")
    assert (moneyline_delay(chk, 1) == moneyline(chk).green.to_numpy()).all(), "N=1 does not match moneyline_ref"
    print("check: N=1 reproduces moneyline_ref exactly on SPY")
    rows = []
    sets = {"crypto20": [(s, load_crypto_daily(s), 0.0010 if s in ("BTC", "ETH") else 0.0015, 365, "2018-01-01") for s in LARGE20 + ["ZEC"]],
            "etf13": [(s, load_etf(s), 0.0002, 252, "2005-01-01") for s in ETF13],
            "user_stocks": [(s, load_etf(s), 0.0003, 252, "2005-01-01") for s in USER_STOCKS]}
    for cls, items in sets.items():
        for s, d, cost, ppy, start in items:
            first = d.index[min(len(d) - 1, 100)]                    # 100-bar warm-up
            st = max(pd.Timestamp(start), first)
            for frozen in (False, True):
                if frozen and cls == "user_stocks":
                    continue
                for row in run_asset(d, cost, ppy, st, "2026-09-30", frozen):
                    rows.append({"class": cls, "asset": s, "variant": "frozen" if frozen else "trailing", **row})
    # weekly
    for s in ["SPY", "QQQ", "IWM", "BTC", "ETH"]:
        d = load_etf(s) if s in ETF13 else load_crypto_daily(s)
        w = to_weekly(d) if s in ETF13 else d.resample("W-MON", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        st = max(pd.Timestamp("2005-01-01" if s in ETF13 else "2018-01-01"), w.index[min(len(w) - 1, 100)])
        for row in run_asset(w, 0.0002 if s in ETF13 else 0.0010, 52, st, "2026-09-30"):
            rows.append({"class": "weekly", "asset": s, "variant": "trailing", **row})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "per_asset.csv", index=False)

    # baskets: S&P 500 point-in-time, crypto top-20 universe
    from screener.data import from_csv_folder, quality_filter
    sp, _ = quality_filter(from_csv_folder(ROOT / "data" / "universe_pit_all"), keep_collapsed=True)
    mem = pd.read_csv(ROOT / "data" / "universe_pit_all" / "members.csv", parse_dates=["start", "end"])
    yrs_sp = list(range(2001, 2027))
    mby = {y: list(mem[(mem.start <= f"{y}-01-01") & (mem.end.isna() | (mem.end >= f"{y}-01-01"))].symbol.str.upper()) for y in yrs_sp}
    sp = {k: v for k, v in sp.items() if k != "SPY" and len(v) > 300}
    from analysis_2026.altcoins import load_crypto, tiers_for_year
    cd = load_crypto()
    yrs_c = list(range(2019, 2027))
    cby = {}
    for y in yrs_c:
        t = tiers_for_year(cd, y); cby[y] = t["1-10"] + t["11-30"][:10]
    cdat = {k: v[["open", "high", "low", "close"]] for k, v in cd.items()}
    brow = []
    for n in DELAYS:
        r_sp = basket(sp, mby, lambda s: 0.0003, n, years=yrs_sp).loc[:"2026-09-30"]
        r_c = basket(cdat, cby, lambda s: 0.0010 if s.split("#")[0] in ("BTC", "ETH") else 0.0015, n, years=yrs_c).loc[:"2026-09-30"]
        brow.append({"class": "sp500 basket", "N": n, **stats(r_sp, 252)})
        brow.append({"class": "cryptoU basket", "N": n, **stats(r_c, 365)})
    bres = pd.DataFrame(brow); bres.to_csv(OUT / "baskets.csv", index=False)

    # ---------------- summaries
    tr = res[(res.variant == "trailing") & (res.N != "B&H")].copy(); tr["N"] = tr.N.astype(int)
    base = tr[tr.N == 1].set_index(["class", "asset"])
    out = []
    for (cls, n), g in tr.groupby(["class", "N"]):
        g = g.set_index(["class", "asset"])
        dS = (g.Sharpe - base.Sharpe.reindex(g.index)).dropna()
        dC = (g["CAGR_%"] - base["CAGR_%"].reindex(g.index)).dropna()
        dD = (g["maxDD_%"] - base["maxDD_%"].reindex(g.index)).dropna()
        k = int((dS > 0).sum()); m = len(dS)
        from math import comb
        p_sign = sum(comb(m, j) for j in range(k, m + 1)) / 2 ** m if m else np.nan
        out.append({"class": cls, "N": n, "assets": m, "median_dSharpe": dS.median(), "improved": f"{k}/{m}", "sign_p": p_sign,
                    "median_dCAGR": dC.median(), "median_dMaxDD": dD.median(), "median_trades_yr": g.trades_per_yr.median(),
                    "median_whipsaw_%": g["whipsaw_%"].median(), "median_avg_loss_%": g["avg_loss_%"].median(),
                    "median_CAGR_tax_%": g["CAGR_tax_%"].median()})
    summ = pd.DataFrame(out); summ.to_csv(OUT / "summary_by_class.csv", index=False)
    print("\nDelay N vs immediate flip (N=1), by asset class (trailing-line rule):")
    print(summ.to_string(index=False, float_format=lambda x: f"{x:,.3f}" if abs(x) < 1 else f"{x:,.2f}"))
    print("\nBaskets (equal-weight each year's members):")
    print(bres.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    fr = res[(res.variant == "frozen") & (res.N != "B&H")].copy(); fr["N"] = fr.N.astype(int)
    cmp = fr.merge(tr, on=["class", "asset", "N"], suffixes=("_frozen", "_trail"))
    print("\nFrozen vs trailing flip point, median Sharpe difference by N:", cmp.assign(d=cmp.Sharpe_frozen - cmp.Sharpe_trail).groupby("N").d.median().round(3).to_dict())
    print("\nPer-asset detail (Sharpe by N; B&H Sharpe in last column):")
    pv = res[res.variant == "trailing"].assign(N=lambda x: x.N.astype(str))
    piv = pv.pivot_table(index=["class", "asset"], columns="N", values="Sharpe", aggfunc="first")
    piv = piv[[str(n) for n in DELAYS] + ["B&H"]]
    print(piv.round(2).to_string())
    piv.to_csv(OUT / "sharpe_by_asset.csv")


if __name__ == "__main__":
    main()
