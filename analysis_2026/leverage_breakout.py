"""
Leverage, tight stops and "key level" breakouts.

Questions from the user:
  - Does trading the indicator with 3-5x leverage on a smaller sub-account help?
  - Do breakout strategies (buy when price clears a key level, tight stop just below)
    work better, and on which timeframe?
Separating the two: EDGE is measured per trade on notional, after fees and funding,
and does not depend on leverage. LEVERAGE is then applied as the user described it: a
sub-account traded at a fixed 1x/3x/5x of its equity, liquidated if a bar's low reaches
the liquidation price.

Data (gitignored): Binance spot klines (data/crypto_binance/ daily incl. delisted
coins, data/crypto_4h/ 4-hour for 20 large coins) and USDT-M perpetual funding rates
(data/crypto_funding/, 8-hourly; 0.01% per 8h is assumed before a coin's perp listed).
ETFs (data/etf/) for comparison.

Systems (signal at a bar's close, entry at the next bar's open):
  ML        the user's indicator (moneyline_ref): long while green; exits on red
  BO20      Donchian/Turtle breakout: close above the prior 20-bar high; initial stop
            entry - 2 x ATR(20); exit on a close below the prior 10-bar low or the stop
  BO55      55-bar high entry, 20-bar low exit, 2 x ATR stop
  BOx-k     same entries with tighter initial stops: k = 1.0 or 0.5 x ATR
  KL        "tested key level" breakout (exploratory): the highest pivot high of the
            last 60 bars touched at least twice (pivots within 0.5 ATR), broken by a close
            0.1 ATR above it; stop 0.5 ATR below the level; exit on a 3 x ATR chandelier
            trailing stop
Stops: if a bar opens below the stop, the fill is the open (gap); otherwise the stop
price. Both are less 1 tick of slippage (the per-side cost).
Costs per side: perps 0.05% taker + 0.02% slippage (BTC/ETH), +0.05% more for other
coins; spot 0.10% + slippage. Longs pay the actual funding rate on notional.
Leverage: notional = L x sub-account equity at entry; liquidation price
entry x (1 - 1/L + 0.5% + fees and funding paid so far); a liquidated sub-account is
blown (equity 0) and stops. Funding is charged on the position's current value; idle
cash earns T-bills; trades still open at the end are marked at the last close.
(Audit fixes, applied after the first run; see FINDINGS.)

Pre-registered hypotheses (written 2026-10-14, before any run):
  H1 BTC and ETH daily: ML at 3x and 5x has a LOWER Sharpe ratio than at 1x (perps),
     and 5x is liquidated at least once 2018-2026.
  H2 Canonical breakouts (BO20, BO55; daily; 1x perps) have positive expectancy: pooled
     mean net trade return > 0 with t >= 2 on BTC+ETH 2018-2026, AND on the out-of-sample
     sets: 18 other large coins (4h data aggregated to daily) and the survivorship-
     inclusive universe of each year's top-20 coins by prior 90-day volume.
  H3 Tight stops (0.5 x ATR) give a lower mean net trade return than 2 x ATR on the same
     entries (pooled over all 20 large coins, daily).
  H4 The 4-hour versions of BO20/BO55 have a lower mean net trade return than the daily
     versions (pooled over the 20 large coins).
  KL and everything else is exploratory.

    python -m analysis_2026.leverage_breakout
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis_2026" / "results_leverage"
LARGE20 = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "LINK", "AVAX", "DOT", "LTC", "TRX", "BCH",
           "ATOM", "ETC", "XLM", "NEAR", "FIL", "UNI", "MATIC"]
MM = 0.005                      # maintenance margin
DEFAULT_FUND_8H = 0.0001        # before a coin's perpetual existed


# ------------------------------------------------------------------ data

def load_4h(sym):
    d = pd.read_csv(ROOT / "data" / "crypto_4h" / f"{sym}.csv", parse_dates=["time"]).set_index("time").sort_index()
    if sym == "MATIC":           # MATIC was renamed POL in Sept 2024: continue with POL
        p = ROOT / "data" / "crypto_4h" / "POL.csv"
        if p.exists():
            pol = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
            d = pd.concat([d, pol[pol.index > d.index[-1]]])
    return d[["open", "high", "low", "close"]].astype(float)


def to_daily(d4):
    g = d4.resample("1D")
    return pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()}).dropna()


def load_daily_binance(sym):
    from analysis_2026.altcoins import load_crypto
    return load_crypto()[sym][["open", "high", "low", "close"]]


def funding_per_bar(sym, index, hours):
    """Sum of funding rates paid by a long in each bar (bar = [t, t+hours))."""
    p = ROOT / "data" / "crypto_funding" / f"{sym if sym != 'MATIC' else 'MATIC'}.csv"
    per_bar = np.full(len(index), DEFAULT_FUND_8H * hours / 8)
    if p.exists():
        f = pd.read_csv(p, parse_dates=["time"]).set_index("time").rate.astype(float)
        if sym == "MATIC" and (ROOT / "data" / "crypto_funding" / "POL.csv").exists():
            # MATIC's file keeps printing a flat 0.01% after the Sept 2024 rename; use POL's real prints
            pol = pd.read_csv(ROOT / "data" / "crypto_funding" / "POL.csv", parse_dates=["time"]).set_index("time").rate.astype(float)
            f = pd.concat([f[f.index < pol.index[0]], pol])
        bins = pd.cut(f.index, bins=list(index) + [index[-1] + pd.Timedelta(hours=hours)], right=False, labels=False)
        s = pd.Series(f.to_numpy()).groupby(bins).sum()
        have = np.zeros(len(index), bool)
        valid = s.index.to_numpy().astype(int)
        per_bar[valid] = s.to_numpy(); have[valid] = True
        first = f.index[0]
        per_bar[(index >= first) & ~have] = 0.0      # inside perp history, no event in bar
    return per_bar


# ------------------------------------------------------------------ signals

def wilder_atr(d, n=20):
    h, l, c = d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy()
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[np.nan, c[:-1]]), np.abs(l - np.r_[np.nan, c[:-1]])))
    tr[0] = h[0] - l[0]
    atr = np.full(len(tr), np.nan); atr[n - 1] = tr[:n].mean()
    for i in range(n, len(tr)):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def key_levels(d, atr, lookback=60, w=3, tol=0.5):
    """Level per bar: the highest pivot high in the prior `lookback` bars that has at least
    one other pivot high within tol x ATR (a level tested at least twice)."""
    h = d.high.to_numpy(); n = len(h)
    piv = np.zeros(n, bool)
    for i in range(w, n - w):
        if h[i] == h[i - w:i + w + 1].max():
            piv[i] = True
    lvl = np.full(n, np.nan)
    piv_idx = np.where(piv)[0]
    for t in range(lookback, n):
        # a pivot at i is only known once bars up to i + w have closed
        cand = piv_idx[(piv_idx >= t - lookback) & (piv_idx + w <= t - 1)]
        if len(cand) < 2 or not np.isfinite(atr[t]):
            continue
        hs = np.sort(h[cand])[::-1]
        for j in range(len(hs) - 1):
            if hs[j] - hs[j + 1] <= tol * atr[t]:
                lvl[t] = hs[j]; break
    return lvl


# ------------------------------------------------------------------ engine

def run(d, system, lev=1.0, venue="perp", fund=None, extra_slip=0.0, start=None, end=None):
    """Single-asset sub-account. Returns (trades DataFrame, equity Series)."""
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(c)
    atr = wilder_atr(d)
    cost = {"perp": 0.0007, "spot": 0.0012, "etf": 0.0003}[venue] + extra_slip
    fund = np.zeros(n) if (fund is None or venue != "perp") else fund
    kind, k_stop = system.get("kind"), system.get("k", 2.0)
    if kind == "ML":
        green = moneyline(d).green.to_numpy(bool)
    if kind == "BO":
        N, M = system["N"], system["M"]
        hh = pd.Series(h).rolling(N).max().shift(1).to_numpy()
        ll = pd.Series(l).rolling(M).min().shift(1).to_numpy()
    if kind == "KL":
        lvl = key_levels(d, atr)
    idx = d.index
    from screener.strictness import TBILL
    bar_h = float(np.median(np.diff(idx.values).astype("timedelta64[m]").astype(float))) / 60
    cash_rate = np.array([TBILL.get(t.year, 2.0) / 100 * bar_h / 8760 for t in idx]) if venue != "etf" else \
        np.array([TBILL.get(t.year, 2.0) / 100 / 252 for t in idx])
    i0 = 0 if start is None else int(np.searchsorted(idx, pd.Timestamp(start)))
    i1 = n - 1 if end is None else int(np.searchsorted(idx, pd.Timestamp(end), side="right")) - 1
    eq = 1.0; pos = False; entry = stop = notional = eq_entry = 0.0; trail = 0.0; t_in = None
    pending_entry = pending_exit = False
    trades = []; curve = np.full(n, np.nan); blown = False
    for t in range(max(i0, 60), i1 + 1):
        if blown:
            curve[t] = 0.0; continue
        # ---- executions at the open
        if pending_exit and pos:
            px = o[t] * (1 - cost)
            eq = eq_entry + notional * (px / entry - 1) - notional * cost - fund_paid
            trades.append((idx[t_in], idx[t], entry, px, init_stop, (px / entry - 1) - cost - fund_paid / notional, "signal", eq / eq_entry - 1))
            pos = False; pending_exit = False
        if pending_entry and not pos:
            entry = o[t]
            if kind == "BO":
                init_stop = entry - k_stop * atr[t - 1] if system.get("stop") != "pct" else entry * (1 - system["pct"])
            elif kind == "KL":
                init_stop = kl_level - 0.5 * atr[t - 1]
            else:
                init_stop = np.nan
            if kind in ("BO", "KL") and not (init_stop < entry):
                pending_entry = False
            else:
                eq_entry = eq; notional = lev * eq; fund_paid = 0.0
                stop = init_stop; trail = init_stop; pos = True; t_in = t; pending_entry = False
        pending_entry = False
        # ---- intrabar: liquidation, stop
        if not pos:
            eq *= 1 + cash_rate[t]                      # idle cash earns T-bills
        if pos:
            fund_paid += notional * (o[t] / entry) * fund[t]      # on the position's current value
            # isolated margin also absorbs the entry fee and the funding paid so far
            liq = entry * (1 - 1 / lev + MM + cost + fund_paid / notional) if lev > 1 else -np.inf
            active_stop = max(stop, trail) if kind in ("BO", "KL") else -np.inf
            if lev > 1 and l[t] <= liq and liq >= active_stop:
                eq = 0.0; blown = True
                trades.append((idx[t_in], idx[t], entry, liq, init_stop, (liq / entry - 1) - cost - fund_paid / notional, "liquidated", -1.0))
                pos = False; curve[t] = 0.0; continue
            if kind in ("BO", "KL") and l[t] <= active_stop:
                px = (min(o[t], active_stop)) * (1 - cost)
                eq = eq_entry + notional * (px / entry - 1) - notional * cost - fund_paid
                trades.append((idx[t_in], idx[t], entry, px, init_stop, (px / entry - 1) - cost - fund_paid / notional, "stop", eq / eq_entry - 1))
                pos = False
                if eq <= 0:
                    eq = 0.0; blown = True; curve[t] = 0.0; continue
        # ---- mark to market at the close
        curve[t] = (eq_entry + notional * (c[t] / entry - 1) - notional * cost - fund_paid) if pos else eq
        if pos and curve[t] <= 0:
            eq = 0.0; blown = True; curve[t] = 0.0; continue
        # ---- signals at the close
        if pos:
            if kind == "ML" and not green[t]:
                pending_exit = True
            elif kind == "BO" and c[t] < ll[t]:
                pending_exit = True
            elif kind == "KL":
                trail = max(trail, c[t] - 3 * atr[t])
        else:
            if kind == "ML" and green[t]:
                pending_entry = True
            elif kind == "BO" and np.isfinite(hh[t]) and c[t] > hh[t] and np.isfinite(atr[t]):
                pending_entry = True
            elif kind == "KL" and np.isfinite(lvl[t]) and c[t] > lvl[t] + 0.1 * atr[t] and c[t - 1] <= lvl[t]:
                pending_entry = True; kl_level = lvl[t]
    if pos and not blown:                                # still open at the window end: mark at the close
        px = c[i1]
        trades.append((idx[t_in], idx[i1], entry, px, init_stop, (px / entry - 1) - cost - fund_paid / notional, "open",
                       (eq_entry + notional * (px / entry - 1) - notional * cost - fund_paid) / eq_entry - 1))
    cols = ["entry_time", "exit_time", "entry", "exit", "init_stop", "net_ret", "exit_type", "acct_ret"]
    tr = pd.DataFrame(trades, columns=cols)
    if len(tr):
        risk = (tr.entry - tr.init_stop) / tr.entry
        tr["R"] = np.where(np.isfinite(risk) & (risk > 0), tr.net_ret / risk, np.nan)
    eqs = pd.Series(curve, index=idx).iloc[max(i0, 60):i1 + 1].ffill()
    return tr, eqs


def eq_stats(e, bars_per_year):
    e = e.dropna()
    if len(e) < 10 or e.iloc[0] <= 0:
        return {}
    r = e.pct_change().fillna(0)
    yrs = len(e) / bars_per_year
    fin = e.iloc[-1] / e.iloc[0]
    return {"CAGR_%": ((fin ** (1 / yrs) - 1) * 100) if fin > 0 else -100.0,
            "maxDD_%": float((e / e.cummax() - 1).min() * 100),
            "Sharpe": float(r.mean() / r.std() * np.sqrt(bars_per_year)) if r.std() > 0 else np.nan,
            "final_x": float(fin)}


def trade_stats(tr):
    if not len(tr):
        return {"trades": 0}
    x = tr.net_ret.to_numpy()
    win, los = x[x > 0].sum(), -x[x <= 0].sum()
    return {"trades": len(x), "win_%": float((x > 0).mean() * 100), "mean_net_%": float(x.mean() * 100),
            "t": float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std() > 0 else np.nan,
            "median_net_%": float(np.median(x) * 100), "PF": float(win / los) if los > 0 else np.nan,
            "mean_R": float(np.nanmean(tr.R)) if "R" in tr and tr.R.notna().any() else np.nan,
            "stopped_%": float((tr.exit_type == "stop").mean() * 100), "liquidated": int((tr.exit_type == "liquidated").sum())}


SYSTEMS = {
    "ML": {"kind": "ML"},
    "BO20": {"kind": "BO", "N": 20, "M": 10, "k": 2.0},
    "BO55": {"kind": "BO", "N": 55, "M": 20, "k": 2.0},
    "BO20-k1": {"kind": "BO", "N": 20, "M": 10, "k": 1.0},
    "BO20-k0.5": {"kind": "BO", "N": 20, "M": 10, "k": 0.5},
    "BO55-k1": {"kind": "BO", "N": 55, "M": 20, "k": 1.0},
    "BO55-k0.5": {"kind": "BO", "N": 55, "M": 20, "k": 0.5},
    "BO20-2pct": {"kind": "BO", "N": 20, "M": 10, "stop": "pct", "pct": 0.02},
    "KL": {"kind": "KL"},
}


def universe_trades(systems=("BO20", "BO55", "ML", "BO20-k0.5", "KL"), years=range(2019, 2027)):
    """Survivorship-inclusive: each year's top-20 coins by prior 90-day volume (delisted coins
    included), daily Binance bars, 1x perps; only trades ENTERED in that year count."""
    from analysis_2026.altcoins import load_crypto, tiers_for_year
    data = load_crypto()
    rows = []
    for y in years:
        tiers = tiers_for_year(data, y)
        members = tiers["1-10"] + tiers["11-30"][:10]
        for sym in members:
            d = data[sym][["open", "high", "low", "close"]]
            base = sym.split("#")[0]
            fund = funding_per_bar(base, d.index, 24) if (ROOT / "data" / "crypto_funding" / f"{base}.csv").exists() \
                else np.full(len(d), DEFAULT_FUND_8H * 3)
            xs = 0.0 if base in ("BTC", "ETH") else 0.0005
            for name in systems:
                tr, _ = run(d, SYSTEMS[name], 1.0, "perp", fund, xs, "2018-01-01", "2026-09-30")
                if len(tr):
                    tr = tr[pd.to_datetime(tr.entry_time).dt.year == y].assign(year=y, asset=sym, system=name)
                    rows.append(tr)
    return pd.concat(rows, ignore_index=True)


def etf_trades(systems=("BO20", "BO55", "ML", "BO20-k0.5", "KL"), names=("SPY", "IWM", "EFA", "EEM", "GLD", "TLT", "VNQ")):
    rows, eqs = [], []
    for n in names:
        d = pd.read_csv(ROOT / "data" / "etf" / f"{n}.csv", parse_dates=["date"]).set_index("date").sort_index()
        for name in systems:
            tr, eq = run(d, SYSTEMS[name], 1.0, "etf", None, 0.0, "2005-01-01", "2026-09-30")
            if len(tr):
                rows.append(tr.assign(asset=n, system=name))
            eqs.append({"asset": n, "system": name, **eq_stats(eq, 252)})
        seg = d.close.loc["2005-01-01":"2026-09-30"]
        eqs.append({"asset": n, "system": "BUY&HOLD", **eq_stats(seg / seg.iloc[0], 252)})
    return pd.concat(rows, ignore_index=True), pd.DataFrame(eqs)


def main():
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    OUT.mkdir(exist_ok=True)
    start, end = "2018-01-01", "2026-09-30"
    daily, four = {}, {}
    for s in LARGE20:
        d4 = load_4h(s)
        four[s] = d4
        daily[s] = to_daily(d4)
    rows_tr, rows_eq, all_trades = [], [], []
    # ---- per system x asset x timeframe x leverage
    for tf, data, hours, bpy in [("1d", daily, 24, 365), ("4h", four, 4, 365 * 6)]:
        for s, d in data.items():
            fund = funding_per_bar(s, d.index, hours)
            xs = 0.0 if s in ("BTC", "ETH") else 0.0005
            for name, sysd in SYSTEMS.items():
                if tf == "4h" and name not in ("ML", "BO20", "BO55", "BO20-k0.5", "BO55-k0.5", "KL"):
                    continue
                for lev, venue in [(1.0, "spot"), (1.0, "perp"), (3.0, "perp"), (5.0, "perp")]:
                    tr, eq = run(d, sysd, lev, venue, fund, xs, start, end)
                    key = {"tf": tf, "asset": s, "system": name, "lev": lev, "venue": venue}
                    rows_eq.append({**key, **eq_stats(eq, bpy)})
                    if lev == 1.0 and venue == "perp":
                        rows_tr.append({**key, **trade_stats(tr)})
                        tr = tr.assign(**key); all_trades.append(tr)
            # buy & hold reference
            i0 = int(np.searchsorted(d.index, pd.Timestamp(start))); first = d.index[max(i0, 60)]
            seg = d.loc[first:end]
            bh = seg.close / seg.close.iloc[0]
            rows_eq.append({"tf": tf, "asset": s, "system": "BUY&HOLD", "lev": 1.0, "venue": "spot", **eq_stats(bh, bpy)})
    eqdf = pd.DataFrame(rows_eq); trdf = pd.DataFrame(rows_tr)
    trades = pd.concat(all_trades, ignore_index=True)
    eqdf.to_csv(OUT / "equity_stats.csv", index=False); trdf.to_csv(OUT / "trade_stats.csv", index=False)
    trades.to_csv(OUT / "trades_1x_perp.csv", index=False)

    # ---- H1: leverage on ML (BTC, ETH daily)
    print("H1 - the indicator with leverage, daily, 2018-2026 (sub-account view):")
    h1 = eqdf[(eqdf.tf == "1d") & eqdf.asset.isin(["BTC", "ETH"]) & eqdf.system.isin(["ML", "BUY&HOLD"])]
    print(h1[["asset", "system", "lev", "venue", "CAGR_%", "maxDD_%", "Sharpe", "final_x"]].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    liq = trades[(trades.tf == "1d") & (trades.system == "ML")]
    # ---- H2-H4: pooled trade expectancy
    def pooled(mask):
        x = trades[mask]
        return trade_stats(x)
    print("\nH2-H4 - pooled trade expectancy, 1x perps, net of fees and funding (net % per trade on notional):")
    rows = []
    for tf in ("1d", "4h"):
        for name in SYSTEMS:
            for grp, assets in [("BTC+ETH", ["BTC", "ETH"]), ("other 18", [a for a in LARGE20 if a not in ("BTC", "ETH")]), ("all 20", LARGE20)]:
                m = (trades.tf == tf) & (trades.system == name) & trades.asset.isin(assets)
                if m.sum():
                    rows.append({"tf": tf, "system": name, "group": grp, **pooled(m)})
    pt = pd.DataFrame(rows); pt.to_csv(OUT / "pooled_trades.csv", index=False)
    print(pt.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    # ---- leverage outcomes for the breakout systems
    print("\nLeverage outcomes (sub-account), daily, median across the 20 large coins:")
    lv = eqdf[(eqdf.tf == "1d") & eqdf.system.isin(["ML", "BO20", "BO55", "BO20-k0.5", "KL", "BUY&HOLD"])]
    g = lv.groupby(["system", "lev", "venue"]).agg(median_CAGR=("CAGR_%", "median"), median_maxDD=("maxDD_%", "median"),
                                                   median_Sharpe=("Sharpe", "median"), blown_share=("final_x", lambda x: (x <= 1e-9).mean() * 100),
                                                   lost_money_share=("final_x", lambda x: (x < 1).mean() * 100))
    print(g.to_string(float_format=lambda x: f"{x:,.2f}"))
    g.to_csv(OUT / "leverage_summary_daily.csv")
    print("\nDaily vs 4-hour bars, 1x perps, median across the 20 large coins (equity, not per trade):")
    tfc = eqdf[(eqdf.lev == 1.0) & (eqdf.venue == "perp") & eqdf.system.isin(["ML", "BO20", "BO55", "BO20-k0.5", "BO55-k0.5", "KL"])]
    print(tfc.groupby(["system", "tf"])[["CAGR_%", "maxDD_%", "Sharpe"]].median().unstack("tf").to_string(float_format=lambda x: f"{x:,.2f}"))
    print("\nTotal-capital view, BTC and ETH daily 2018-2026: 20% of capital in a sub-account at Lx, 80% in T-bills,")
    print("versus 100% at 1x spot (same market exposure as 20% at 5x) and 20% at 1x spot:")
    yrs = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    cash = 1.03 ** yrs
    tv = []
    for a in ("BTC", "ETH"):
        for sysn in ("ML", "BO20", "BO55"):
            f = {(r.lev, r.venue): r.final_x for r in eqdf[(eqdf.tf == "1d") & (eqdf.asset == a) & (eqdf.system == sysn)].itertuples()}
            row = {"asset": a, "system": sysn, "100% at 1x spot": f[(1.0, "spot")], "20% at 1x spot": 0.2 * f[(1.0, "spot")] + 0.8 * cash}
            for L in (3.0, 5.0):
                row[f"20% at {int(L)}x perp"] = 0.2 * f[(L, "perp")] + 0.8 * cash
            tv.append(row)
    tvd = pd.DataFrame(tv); tvd.to_csv(OUT / "total_capital_view.csv", index=False)
    print(tvd.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    # ---- out-of-sample universe (H2b) and ETFs
    ut = universe_trades(); ut.to_csv(OUT / "universe_top20_trades.csv", index=False)
    print("\nH2b - survivorship-inclusive top-20 universe (daily, 1x perps), trades entered 2019-2026:")
    print(pd.DataFrame([{"system": k, **trade_stats(v)} for k, v in ut.groupby("system")]).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    et, ee = etf_trades(); et.to_csv(OUT / "etf_trades.csv", index=False); ee.to_csv(OUT / "etf_equity.csv", index=False)
    print("\nETFs 2005-2026 (daily, 1x, 0.03%/side): pooled trades and median equity stats")
    print(pd.DataFrame([{"system": k, **trade_stats(v)} for k, v in et.groupby("system")]).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print(ee.groupby("system")[["CAGR_%", "maxDD_%", "Sharpe"]].median().to_string(float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
