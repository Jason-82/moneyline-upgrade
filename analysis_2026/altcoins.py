"""
Does the indicator work better on smaller cryptocurrencies? And why does it beat buy &
hold on some assets but not on S&P 500 stocks?

Data: Binance's public archive (data.binance.vision, read through its S3 bucket), daily
klines for every USDT spot pair, INCLUDING pairs Binance later delisted (LUNA, FTT, ...).
Stablecoins, fiat pairs, wrapped duplicates and leveraged tokens are excluded. Files
live in data/crypto_binance/ (gitignored).

Method (no look-ahead):
  - Each year Y, on Jan 1: eligible coins have >= 180 days of history and traded in the
    last 3 days of Y-1. Coins whose daily returns barely move (std < 0.5% over 180 days,
    i.e. pegged assets) are excluded.
  - Size tier = rank by median daily USDT volume over the previous 90 days (a stand-in
    for market cap): 1-10, 11-30, 31-100, 101+.
  - Each coin is traded through year Y on the exact indicator (moneyline_ref; real
    OHLC): green at a daily close -> hold from the next open; red -> sell at the next
    open, then hold cash at the T-bill rate. Crypto trades 24/7, so the next open is
    the signal close; the late variant waits one more day.
  - Delisted inside the year: sold at the last close in the archive, then cash.
  - Cost per side = exchange fee + spread/slippage by tier (US retail default): 0.30 /
    0.35 / 0.50 / 0.75%. Variants: low (0.12-0.35%) and Robinhood (0.95%; Robinhood
    lists few small coins).
  - Tier basket: equal money per coin on Jan 1, no rebalancing, liquidated Dec 31.
    Buy & hold of the same coins is the comparison.
  - Tax (illustrative 35% short-term / 20% long-term): everything inside a year is
    short-term. Baskets are liquidated yearly and the net gain is taxed with losses
    carried forward. BTC and SPY held: taxed once at the long-term rate at the end.

Pre-registered questions (written before any run, 2026-10-14):
  Q1 Does the signal's edge over holding the same coins grow from large to small coins?
     (chained pre-tax CAGR of signal basket minus buy & hold basket, by tier, 2019-2025)
  Q2 Does the small-coin signal basket (101+) beat the large-coin signal basket (1-10)
     AND holding BTC, after costs and tax, 2019-2025?
  2026 (to the end of the archive) is reported separately as out-of-sample.
  Also reported: survivors only (coins still trading at the end) to show the bias, and
  the payoff profile (signal return by buy & hold return bucket) for crypto vs S&P 500
  stocks - the mechanism behind where the signal wins.

    python -m analysis_2026.altcoins
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline  # noqa: E402
from screener.data import from_csv_folder  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# left out by name on top of the download filter: newer stablecoins and a staked SOL copy
# (tokenized stocks such as AAPLB are too young to pass the 200-bar minimum; exclude them
# by name once they do)
EXCLUDE = {"U", "KGST", "BNSOL"}
TIERS = [("1-10", 1, 10), ("11-30", 11, 30), ("31-100", 31, 100), ("101+", 101, 10**6)]
COSTS = {"retail": {"1-10": 0.0030, "11-30": 0.0035, "31-100": 0.0050, "101+": 0.0075},
         "low": {"1-10": 0.0012, "11-30": 0.0015, "31-100": 0.0022, "101+": 0.0035},
         "robinhood": {"1-10": 0.0095, "11-30": 0.0095, "31-100": 0.0095, "101+": 0.0095}}
ST, LT = 0.35, 0.20
from screener.strictness import TBILL  # noqa: E402  (approximate 3-month T-bill, % per year, 1999-2026)


def load_crypto(folder=ROOT / "data" / "crypto_binance", min_bars=200):
    """One series per coin. A file is split into separate coins where the ticker was
    reused or the token redenominated: a gap of more than 7 days, or a jump between one
    day's close and the next day's open of more than 50% (on a 24/7 market real moves
    happen between open and close, not overnight). Old LUNA and Terra 2.0, for example,
    share LUNAUSDT. Later segments are named COIN#2, COIN#3."""
    out = {}
    for f in sorted(Path(folder).glob("*.csv")):
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
        d = d[~d.index.duplicated(keep="last")]
        d = d[(d[["open", "high", "low", "close"]] > 0).all(axis=1)]
        if len(d) < min_bars:
            continue
        gap = d.index.to_series().diff().dt.days > 7
        jump = (np.log(d.open / d.close.shift(1)).abs() > np.log(1.5)).fillna(False)
        seg = (gap | jump).cumsum().to_numpy()
        base = f.stem[:-4]
        if base in EXCLUDE:
            continue
        for k in np.unique(seg):
            part = d[seg == k]
            if len(part) >= min_bars:
                out[base if k == 0 else f"{base}#{k + 1}"] = part
    return out


def signal_year(df, green, start, end, cost, late=False):
    """One asset through [start, end]: signal (next open, cash at T-bill) and buy & hold.
    Returns multiples, exposure, trades, drift-neutral skill and the daily signal path."""
    w = df.loc[start:end]
    if len(w) < 5:
        return None
    pos = df.index.get_indexer([w.index[0]])[0]
    g = green.to_numpy(bool)
    lag = 2 if late else 1
    o, c = df.open.to_numpy(float), df.close.to_numpy(float)
    idx = range(pos, pos + len(w))
    held_prev = False
    v = 1.0; path = []; trades = 0; expo = 0; lr_s = 0.0; lr_b = 0.0
    dates = w.index
    for k, i in enumerate(idx):
        want = bool(g[i - lag]) if i - lag >= 0 else False
        days = 1 if k == 0 else (dates[k] - dates[k - 1]).days      # cash accrues per calendar day
        tb = (1 + TBILL.get(dates[k].year, 2.0) / 100 / 365) ** days - 1
        if want and held_prev:
            r = c[i] / c[i - 1]
        elif want and not held_prev:
            r = (1 - cost) * c[i] / o[i]
        elif held_prev and not want:
            r = (1 - cost) * o[i] / c[i - 1] * (1 + tb); trades += 1
        else:
            r = 1 + tb
        if k == len(w) - 1 and want:                   # liquidate at the window end
            r *= 1 - cost; trades += 1
        v *= r; path.append(v)
        b = c[i] / (o[i] if k == 0 else c[i - 1])
        lr_b += np.log(b); expo += want
        held_prev = want
    lr_s = np.log(v)
    exp = expo / len(w)
    bh = (1 - cost) ** 2 * c[pos + len(w) - 1] / o[pos]
    yrs = len(w) / 365
    full = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    delisted = len(w) < full - 3 and w.index[-1] < pd.Timestamp(end) - pd.Timedelta(days=3)
    if delisted:                                       # cash for the rest of the window
        rest = (pd.Timestamp(end) - w.index[-1]).days
        v *= (1 + TBILL.get(w.index[-1].year, 2.0) / 100 / 365) ** rest
    return {"sig": v, "bh": bh, "exposure": exp, "trades": trades, "delisted": delisted,
            "skill": (lr_s - exp * lr_b) / max(yrs, 1e-9) * 100, "days": len(w),
            "path": pd.Series(path, index=w.index)}


def tiers_for_year(data, year):
    r = pd.Timestamp(f"{year}-01-01")
    vol = {}
    for s, d in data.items():
        before = d[d.index < r]
        if len(before) < 180 or before.index[-1] < r - pd.Timedelta(days=3):
            continue
        if len(d.loc[r:r + pd.Timedelta(days=3)]) == 0:
            continue
        if before.close.pct_change().iloc[-180:].std() < 0.005:   # pegged / stable
            continue
        vol[s] = before.quote_volume.iloc[-90:].median()
    rank = pd.Series(vol).sort_values(ascending=False)
    out = {}
    for name, lo, hi in TIERS:
        out[name] = list(rank.index[lo - 1:hi])
    return out


def run(data, years, cost_set="retail", late=False, survivors_only=False, end_date=None):
    greens = {s: moneyline(d).green for s, d in data.items()}
    last = max(d.index[-1] for d in data.values()) if end_date is None else pd.Timestamp(end_date)
    alive = {s for s, d in data.items() if d.index[-1] >= last - pd.Timedelta(days=5)}
    coin_rows, basket_rows = [], []
    for y in years:
        start, end = f"{y}-01-01", min(pd.Timestamp(f"{y}-12-31"), last).strftime("%Y-%m-%d")
        tiers = tiers_for_year(data, y)
        for tier, syms in tiers.items():
            if survivors_only:
                syms = [s for s in syms if s in alive]
            res = {}
            for s in syms:
                r = signal_year(data[s], greens[s], start, end, COSTS[cost_set][tier], late)
                if r:
                    res[s] = r
                    coin_rows.append({"year": y, "tier": tier, "coin": s, **{k: v for k, v in r.items() if k != "path"}})
            if not res:
                continue
            sig = np.mean([r["sig"] for r in res.values()]); bh = np.mean([r["bh"] for r in res.values()])
            cal = pd.date_range(start, end)
            P = pd.concat([r["path"].reindex(cal).ffill().fillna(1.0) for r in res.values()], axis=1).mean(axis=1)
            basket_rows.append({"year": y, "tier": tier, "n": len(res), "sig_mult": sig, "bh_mult": bh,
                                "delisted": sum(r["delisted"] for r in res.values()),
                                "sig_dd": float((P / P.cummax() - 1).min() * 100)})
    return pd.DataFrame(coin_rows), pd.DataFrame(basket_rows)


def after_tax_chain(mults, rate=ST):
    """Yearly liquidated basket: tax the net gain each year at `rate`, losses carried."""
    v, carry = 1.0, 0.0
    for m in mults:
        g = v * (m - 1)
        net = g + carry
        tax = rate * net if net > 0 else 0.0
        carry = 0.0 if net > 0 else net
        v = v + g - tax
    return v


def hold_after_tax(series, start, end, lt=LT, cost=0.003):
    s = series.loc[start:end]
    m = (1 - cost) ** 2 * s.close.iloc[-1] / s.open.iloc[0]
    return m - lt * (m - 1) if m > 1 else m, m


def summarise(baskets, years):
    rows = []
    for tier, g in baskets[baskets.year.isin(years)].groupby("tier"):
        g = g.sort_values("year")
        n = len(g)
        sig, bh = g.sig_mult.prod(), g.bh_mult.prod()
        rows.append({"tier": tier, "years": n, "avg_coins": g.n.mean(), "delisted_in_year": int(g.delisted.sum()),
                     "sig_cagr": (sig ** (1 / n) - 1) * 100, "bh_cagr": (bh ** (1 / n) - 1) * 100,
                     "edge": (sig ** (1 / n) - bh ** (1 / n)) * 100,
                     "sig_cagr_tax": (after_tax_chain(g.sig_mult) ** (1 / n) - 1) * 100,
                     "bh_cagr_tax_rebal": (after_tax_chain(g.bh_mult) ** (1 / n) - 1) * 100,
                     "sig_beats_bh_years": f"{int((g.sig_mult > g.bh_mult).sum())}/{n}",
                     "worst_year_sig": (g.sig_mult.min() - 1) * 100, "worst_year_bh": (g.bh_mult.min() - 1) * 100})
    order = [t[0] for t in TIERS]
    return pd.DataFrame(rows).set_index("tier").reindex([t for t in order if t in {r["tier"] for r in rows}])


BUCKETS = [-np.inf, -60, -30, 0, 30, 100, 300, np.inf]


def payoff(coin_rows):
    """Signal return by the asset's own buy & hold return that year: where the signal wins."""
    r = coin_rows.copy()
    r["bh_%"] = (r.bh - 1) * 100; r["sig_%"] = (r.sig - 1) * 100
    r["bucket"] = pd.cut(r["bh_%"], BUCKETS)
    g = r.groupby("bucket", observed=True)
    return pd.DataFrame({"share_of_asset_years_%": g.size() / len(r) * 100, "n": g.size(),
                         "median_bh_%": g["bh_%"].median(), "median_signal_%": g["sig_%"].median(),
                         "signal_beats_bh_%": g.apply(lambda x: (x.sig > x.bh).mean() * 100, include_groups=False)})


def stock_coin_rows(years=range(2001, 2026), folder=ROOT / "data" / "universe_pit_all"):
    """Same per-year test on S&P 500 point-in-time members (stock costs 0.03%)."""
    data = from_csv_folder(folder)
    m = pd.read_csv(Path(folder) / "members.csv", parse_dates=["start", "end"])
    rows = []
    greens = {}
    for y in years:
        d0 = pd.Timestamp(f"{y}-01-01")
        on = set(m[(m.start <= d0) & (m.end.isna() | (m.end >= d0))].symbol)
        for s in on:
            if s not in data or s == "SPY":
                continue
            df = data[s]
            if len(df.loc[:d0]) < 200 or len(df.loc[d0:d0 + pd.Timedelta(days=7)]) == 0:
                continue
            if s not in greens:
                greens[s] = moneyline(df).green
            r = signal_year(df, greens[s], f"{y}-01-01", f"{y}-12-31", 0.0003)
            if r:
                rows.append({"year": y, "coin": s, **{k: v for k, v in r.items() if k != "path"}})
    return pd.DataFrame(rows)


def period_table(baskets, data, years, spy=None):
    """Signal vs hold by tier over a common set of years, plus BTC/ETH signal and held,
    and SPY held. Tiers are compared only on years where all of them are populated."""
    n = len(years); rows = []
    for tier in [t[0] for t in TIERS]:
        g = baskets[(baskets.tier == tier) & baskets.year.isin(years)].sort_values("year")
        if len(g) < n:
            continue
        for col, lab in [("sig_mult", "signal"), ("bh_mult", "hold")]:
            rows.append({"what": f"tier {tier} {lab}", "avg_coins": g.n.mean(),
                         "pre_tax": (g[col].prod() ** (1 / n) - 1) * 100,
                         "after_tax": (after_tax_chain(g[col]) ** (1 / n) - 1) * 100,
                         "worst_year": (g[col].min() - 1) * 100})
    s0, s1 = f"{years[0]}-01-01", f"{years[-1]}-12-31"
    for name in ["BTC", "ETH"]:
        d = data[name]; gr = moneyline(d).green
        ms = [signal_year(d, gr, f"{y}-01-01", f"{y}-12-31", 0.003)["sig"] for y in years]
        yr = [d.loc[f"{y}-12-31"].close / d.loc[f"{y}-01-01"].open for y in years]
        at, pre = hold_after_tax(d, s0, s1)
        rows += [{"what": f"{name} signal", "avg_coins": 1, "pre_tax": (np.prod(ms) ** (1 / n) - 1) * 100,
                  "after_tax": (after_tax_chain(ms) ** (1 / n) - 1) * 100, "worst_year": (min(ms) - 1) * 100},
                 {"what": f"{name} held", "avg_coins": 1, "pre_tax": (pre ** (1 / n) - 1) * 100,
                  "after_tax": (at ** (1 / n) - 1) * 100, "worst_year": (min(yr) - 1) * 100}]
    if spy is not None:
        at, pre = hold_after_tax(spy, s0, s1, cost=0.0003)
        rows.append({"what": "SPY held", "avg_coins": 1, "pre_tax": (pre ** (1 / n) - 1) * 100,
                     "after_tax": (at ** (1 / n) - 1) * 100, "worst_year": np.nan})
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 220)
    data = load_crypto()
    last = max(d.index[-1] for d in data.values())
    print(f"{len(data)} coins with >= 200 daily bars; data to {last.date()}\n")
    dev, oos = list(range(2019, 2026)), [2026]
    out = ROOT / "analysis_2026" / "results_altcoins"
    out.mkdir(exist_ok=True)
    for cost_set, late, surv in [("retail", False, False), ("low", False, False), ("robinhood", False, False),
                                 ("retail", True, False), ("retail", False, True)]:
        tag = f"{cost_set}{'_late' if late else ''}{'_survivors' if surv else ''}"
        coins, baskets = run(data, dev + oos, cost_set, late, surv)
        baskets.to_csv(out / f"baskets_{tag}.csv", index=False)
        if tag == "retail":
            coins.to_csv(out / "coin_years_retail.csv", index=False)
            retail_coins = coins
        print(f"=== {tag}: 2019-2025 (pre-registered) ===")
        print(summarise(baskets, dev).to_string(float_format=lambda x: f"{x:,.1f}"))
        print(f"--- {tag}: 2026 to {last.date()} (out-of-sample) ---")
        print(summarise(baskets, oos).to_string(float_format=lambda x: f"{x:,.1f}") + "\n")
    btc = data["BTC"]; eth = data["ETH"]
    spy = from_csv_folder(ROOT / "data" / "universe_pit_all", {"SPY"}).get("SPY")
    for name, s in [("BTC", btc), ("ETH", eth)] + ([("SPY", spy)] if spy is not None else []):
        cst = 0.0003 if name == "SPY" else 0.003
        at, pre = hold_after_tax(s, "2019-01-01", "2025-12-31", cost=cst)
        print(f"{name} held 2019-2025: {(pre ** (1 / 7) - 1) * 100:.1f}%/yr pre-tax, {(at ** (1 / 7) - 1) * 100:.1f}%/yr after tax")
    retail_b = pd.read_csv(out / "baskets_retail.csv")
    for yrs in (list(range(2021, 2026)), list(range(2022, 2026))):
        print(f"\nCommon period {yrs[0]}-{yrs[-1]}, retail costs (tier 101+ holds only 5 coins in 2021; every tier is well populated from 2022):")
        pt = period_table(retail_b, data, yrs, spy)
        print(pt.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
        pt.to_csv(out / f"period_{yrs[0]}_{yrs[-1]}.csv", index=False)
    top = retail_coins[retail_coins.year.isin(dev)].assign(gain=lambda x: x.sig - 1).sort_values("gain", ascending=False)
    print("\nLargest single coin-year signal gains (concentration check):")
    print(top.head(8)[["year", "tier", "coin", "sig", "bh"]].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\nPayoff profile, crypto coin-years 2019-2025 (retail costs):")
    pc = payoff(retail_coins[retail_coins.year.isin(dev)])
    print(pc.to_string(float_format=lambda x: f"{x:,.1f}"))
    pc.to_csv(out / "payoff_crypto.csv")
    if (ROOT / "data" / "universe_pit_all").exists():
        st = stock_coin_rows()
        st.to_csv(out / "stock_years.csv", index=False)
        ps = payoff(st)
        print("\nPayoff profile, S&P 500 stock-years 2001-2025 (0.03% costs):")
        print(ps.to_string(float_format=lambda x: f"{x:,.1f}"))
        ps.to_csv(out / "payoff_stocks.csv")


if __name__ == "__main__":
    main()
