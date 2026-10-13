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


# ---------------------------------------------------------------- spot-ETF proxy
# A spot ETF trades only in US sessions. A crypto daily bar labelled D closes at
# 00:00 UTC on D+1 (8 pm ET on D), so its signal can first be acted on in the next
# NYSE session after D. Weekend and holiday signals wait for the next session.
# The fill is approximated by the crypto close of the execution day's bar
# (00:00 UTC, ~4 h after the US close). Holidays: NYSE rules approximated with
# pandas holiday helpers.

def nyse_trading_days(start, end):
    from pandas.tseries.holiday import (AbstractHolidayCalendar, Holiday, GoodFriday,
                                        USMartinLutherKingJr, USPresidentsDay, USMemorialDay,
                                        USLaborDay, USThanksgivingDay, nearest_workday)

    class NYSE(AbstractHolidayCalendar):
        rules = [Holiday("NewYear", month=1, day=1, observance=nearest_workday),
                 USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
                 Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
                 Holiday("Independence", month=7, day=4, observance=nearest_workday),
                 USLaborDay, USThanksgivingDay,
                 Holiday("Christmas", month=12, day=25, observance=nearest_workday)]

    hol = NYSE().holidays(start, end)
    days = pd.bdate_range(start, end)
    return days[~days.isin(hol)]


def etf_want(index, green, sessions_late=1):
    """
    Position held at each crypto bar close when the signal of bar s executes at the
    `sessions_late`-th NYSE session strictly after s's date.
    """
    idx = pd.DatetimeIndex(index).normalize()
    td = nyse_trading_days(idx[0], idx[-1] + pd.Timedelta(days=15))
    td_arr = td.values
    g = np.asarray(green, dtype=bool)
    want = np.zeros(len(idx), dtype=bool)
    pos = {d: i for i, d in enumerate(idx)}
    effective = {}                       # bar position -> state that takes effect there
    for s, d in enumerate(idx):
        k = np.searchsorted(td_arr, np.datetime64(d), side="right") + sessions_late - 1
        if k < len(td_arr):
            e = pos.get(pd.Timestamp(td_arr[k]))
            if e is not None:
                effective[e] = g[s]      # later signals overwrite earlier ones
    cur = False
    for i in range(len(idx)):
        if i in effective:
            cur = effective[i]
        want[i] = cur
    return want


def etf_proxy(start=None, cost=0.0002):
    """CAGR edge vs buy & hold for the spot-ETF route, next and second session."""
    rows = []
    for s in ASSETS:
        d = load(s, "1D")
        if start:
            d = d[d.index >= start]
        b = bh_cost(d.close, cost)
        r = {"asset": s, "bh_cagr": b["cagr"], "bh_dd": b["dd"]}
        for k in (1, 2):
            m = bt_cost(d.close, etf_want(d.index, d.green.to_numpy(bool), k), 365, cost)
            r[f"edge_s{k}"] = m["cagr"] - b["cagr"]
            r[f"dd_s{k}"] = m["dd"]
        # superseded calendar-day lag (trades on weekends, which an ETF cannot)
        g = d.green.to_numpy(bool)
        m = bt_cost(d.close, np.r_[False, g[:-1]], 365, cost)
        r["edge_calendar_lag1(superseded)"] = m["cagr"] - b["cagr"]
        rows.append(r)
    return pd.DataFrame(rows)


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
    f = lambda x: f"{x:+.1f}"  # noqa: E731
    frames = []
    for start, label in ((None, "full"), ("2022-01-01", "2022+"), ("2024-01-01", "2024+")):
        t = table(start).assign(window=label)
        frames.append(t)
        print(f"\n=== Direct crypto: CAGR edge vs B&H by cost per side — {label} ===")
        print(t.pivot_table(index=["asset", "tf"], columns="cost_per_side_%", values="edge_pts").to_string(float_format=f))
    pd.concat(frames).to_csv(out / "results_costs.csv", index=False)
    etf = []
    for start, label in ((None, "full"), ("2022-01-01", "2022+"), ("2024-01-01", "2024+")):
        e = etf_proxy(start).assign(window=label)
        etf.append(e)
        print(f"\n=== Spot-ETF proxy (NYSE sessions only, 0.02%/side) — {label} ===")
        print(e.to_string(index=False, float_format=f))
    pd.concat(etf).to_csv(out / "results_etf_proxy.csv", index=False)
