"""
Portfolio-level test of the sizing rules in AGENTIC_TRADING_PLAN.md section 6, on the
spot-ETF route (crypto daily signal executed at the next NYSE session, 0.02%/side,
cash earns nothing - conservative).

Schemes (position size decided at entry, then left to drift until the exit):
  bh_equal      equal-weight buy & hold, no rebalancing
  signal_full   signal, each asset gets 1/N of equity at entry
  fixed_25      signal, 25% of equity per entry
  risk_k1.5     signal, weight = 2.5% / (1.5 x distance-to-line at the flip bar),
                capped at 30% per asset
Every signal scheme also respects a 60% cap on total crypto exposure at entry.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.run_full import load  # noqa: E402
from analysis_2026.costs import etf_want  # noqa: E402

COST = 0.0002
CLUSTER_CAP = 0.60


def panel(assets):
    frames = {s: load(s, "1D") for s in assets}
    idx = frames[assets[0]].index
    for s in assets[1:]:
        idx = idx.intersection(frames[s].index)
    return {s: frames[s].loc[idx] for s in assets}, idx


def entry_distance(d):
    """Distance (close - line)/close at the most recent green-flip bar, per bar."""
    g = d.green.to_numpy(bool); c = d.close.to_numpy(float); ln = d.line.to_numpy(float)
    out = np.full(len(g), np.nan); cur = np.nan
    for i in range(len(g)):
        if g[i] and (i == 0 or not g[i - 1]):
            cur = (c[i] - ln[i]) / c[i]
        out[i] = cur
    return out


def run_scheme(assets, scheme):
    data, idx = panel(assets)
    n = len(assets)
    c = {s: data[s].close.to_numpy(float) for s in assets}
    if scheme == "bh_equal":
        eq = sum((1 / n) * (1 - COST) * c[s] / c[s][0] for s in assets)
        e = pd.Series(eq, index=idx)
        return e, 100.0
    want = {s: etf_want(idx, data[s].green.to_numpy(bool), 1) for s in assets}
    dist = {s: entry_distance(data[s]) for s in assets}
    cash, sh = 1.0, {s: 0.0 for s in assets}
    eq = np.empty(len(idx)); expo = np.empty(len(idx))
    for t in range(len(idx)):
        for s in assets:                                   # exits first
            if sh[s] > 0 and not want[s][t]:
                cash += sh[s] * c[s][t] * (1 - COST); sh[s] = 0.0
        equity = cash + sum(sh[s] * c[s][t] for s in assets)
        for s in assets:                                   # then entries
            if sh[s] == 0 and want[s][t]:
                if scheme == "signal_full":
                    w = 1 / n
                elif scheme == "fixed_25":
                    w = 0.25
                else:
                    dd = dist[s][t]
                    w = min(0.30, 0.025 / (1.5 * dd)) if dd and dd > 0 else 0.0
                invested = sum(sh[x] * c[x][t] for x in assets)
                room = max(0.0, CLUSTER_CAP * equity - invested) if scheme != "signal_full" else cash
                spend = min(w * equity, cash, room)
                if spend > 0:
                    sh[s] = spend * (1 - COST) / c[s][t]; cash -= spend
        eq[t] = cash + sum(sh[s] * c[s][t] for s in assets)
        expo[t] = 1 - cash / eq[t] if eq[t] > 0 else 0
    return pd.Series(eq, index=idx), float(np.mean(expo) * 100)


def stats(e):
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    return (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) * 100 - 100, float(((e / e.cummax()) - 1).min() * 100)


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    rows = []
    for assets in (["ETH", "SOL"], ["BTC", "ETH"], ["BTC", "ETH", "SOL"]):
        for scheme in ("bh_equal", "signal_full", "fixed_25", "risk_k1.5"):
            e, ex = run_scheme(assets, scheme)
            cg, dd = stats(e)
            rows.append({"basket": "+".join(assets), "from": e.index[0].date(), "scheme": scheme,
                         "cagr_%": cg, "max_dd_%": dd, "avg_exposure_%": ex, "cagr_per_dd": cg / abs(dd)})
    out = pd.DataFrame(rows)
    out.to_csv(Path(__file__).resolve().parent / "results_portfolio.csv", index=False)
    print(out.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
