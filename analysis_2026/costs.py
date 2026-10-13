"""
Robinhood cost sensitivity for the crypto daily/weekly signal.

Every other crypto result in this repo assumes 0.1% fee + 5bp slippage per side
(~0.15%). Robinhood crypto (Oct 2026) costs far more at retail size:
  - default market-maker route: ~0.95% inside the spread per side (~1.9% round trip;
    a 1.87% BTC spread was observed on an agentic account in Sep 2026)
  - exchange route, <$10K trailing-30d volume: 0.95% taker / 0.50% maker
  - exchange route only reaches ~0.15% taker at $250K-500K of 30-day volume
Buy & hold pays the cost once (entry) - modelled the same way here.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.run_full import load, ASSETS  # noqa: E402


def bt_cost(close, want, ppy, cost):
    """Long while `want`; `cost` is the all-in fraction paid per side."""
    c = close.to_numpy(float); w = np.asarray(want, dtype=bool)
    eq, sh = 1.0, 0.0
    curve = np.empty(len(c)); n = 0
    for i in range(len(c)):
        if w[i] and sh == 0.0:
            sh = eq * (1 - cost) / c[i]; eq = 0.0; n += 1
        elif not w[i] and sh > 0.0:
            eq = sh * c[i] * (1 - cost); sh = 0.0
        curve[i] = eq + sh * c[i]
    e = pd.Series(curve, index=close.index)
    yrs = (close.index[-1] - close.index[0]).days / 365.25
    return {"cagr": (e.iloc[-1] ** (1 / yrs) - 1) * 100 if e.iloc[-1] > 0 else -100.0,
            "dd": ((e / e.cummax()) - 1).min() * 100, "entries": n, "years": yrs}


def bh_cost(close, cost):
    yrs = (close.index[-1] - close.index[0]).days / 365.25
    m = close.iloc[-1] / close.iloc[0] * (1 - cost)
    return {"cagr": (m ** (1 / yrs) - 1) * 100, "dd": ((close / close.cummax()) - 1).min() * 100}


COSTS = [0.0015, 0.005, 0.0095, 0.0125]


def table(start=None):
    rows = []
    for s in ASSETS:
        for tf, ppy in (("1D", 365), ("1W", 52)):
            d = load(s, tf)
            if start:
                d = d[d.index >= start]
            for cst in COSTS:
                m = bt_cost(d.close, d.green.to_numpy(bool), ppy, cst)
                b = bh_cost(d.close, cst)
                rows.append({"asset": s, "tf": tf, "cost_per_side_%": cst * 100,
                             "signal_cagr": m["cagr"], "bh_cagr": b["cagr"],
                             "edge_pts": m["cagr"] - b["cagr"], "signal_dd": m["dd"],
                             "bh_dd": b["dd"], "trades_per_yr": m["entries"] / m["years"]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent
    full = table(); full.to_csv(out / "results_costs.csv", index=False)
    print(full.pivot_table(index=["asset", "tf"], columns="cost_per_side_%", values="edge_pts")
          .to_string(float_format=lambda x: f"{x:+.1f}"))
