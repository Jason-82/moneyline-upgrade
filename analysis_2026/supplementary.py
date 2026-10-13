"""
Reproducible versions of claims that were previously computed ad hoc, with the
corrections found in the 2026-10-13 audit:

  1. losing-trade statistics (the old "median -1% to -4.5%" was the median of ALL
     trades, not of losing trades)
  2. entering late into a green run - exit at the RED-FLIP close c[b+1], which is
     where the strategy actually exits (the old table exited at the last green
     close c[b], which flattered it)
  3. era split vs buy & hold
  4. Daily AND Weekly confirmation: how much return it gives up per asset
  5. same-bar vs next-bar fill: does "beats B&H on 4 of 5" survive?

Crypto, real signal, data/tv_full, same cost model as run_full (0.1% + 5bp/side).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.run_full import load, bt, bh, weekly_on_daily, ASSETS  # noqa: E402


def closed_runs(green):
    """(start, last_green, exit_bar) for every green run that ended inside the data."""
    g = np.asarray(green, dtype=bool)
    out, i = [], 0
    while i < len(g):
        if g[i] and (i == 0 or not g[i - 1]):
            j = i + 1
            while j < len(g) and g[j]:
                j += 1
            if j < len(g):
                out.append((i, j - 1, j))
            i = j
        else:
            i += 1
    return out


def losing_trades():
    rows = []
    for s in ASSETS:
        d = load(s, "1D"); c = d.close.to_numpy(float)
        r = pd.Series([(c[x] / c[a] - 1) * 100 for a, _, x in closed_runs(d.green)])
        loss = r[r <= 0]
        rows.append({"asset": s, "trades": len(r), "median_all": r.median(),
                     "losers": len(loss), "median_loss": loss.median(),
                     "p5_all": r.quantile(.05), "worst": r.min(), "win_rate": (r > 0).mean() * 100})
    return pd.DataFrame(rows)


def late_entry():
    rows = []
    for s in ASSETS:
        d = load(s, "1D"); c = d.close.to_numpy(float)
        runs = closed_runs(d.green)
        for lo, hi in ((0, 20), (21, 50), (51, 10_000)):
            rem, nruns = [], set()
            for k, (a, b, x) in enumerate(runs):
                for day in range(lo, min(hi, b - a) + 1):
                    rem.append((c[x] / c[a + day] - 1) * 100)   # exit at the red-flip close
                    nruns.add(k)
            if rem:
                rows.append({"asset": s, "enter_day": f"{lo}-{hi if hi < 10_000 else '+'}",
                             "obs": len(rem), "runs": len(nruns),
                             "median_remaining": float(np.median(rem)),
                             "win_rate": 100 * float(np.mean(np.array(rem) > 0))})
    return pd.DataFrame(rows)


def era_split():
    rows = []
    for s in ASSETS:
        for start in (None, "2022-01-01", "2024-01-01"):
            d = load(s, "1D")
            if start:
                d = d[d.index >= start]
            m, _ = bt(d.close, d.green.to_numpy(bool), 365)
            b = bh(d.close)
            rows.append({"asset": s, "from": start or "start", "signal_%": m["return_pct"], "bh_%": b["return_pct"],
                         "signal_dd": m["max_dd_pct"], "bh_dd": b["max_dd_pct"]})
    return pd.DataFrame(rows)


def daily_and_weekly():
    rows = []
    for s in ASSETS:
        d = load(s, "1D"); g = d.green.to_numpy(bool)
        wk = weekly_on_daily(s, d.index).to_numpy(bool)
        base, _ = bt(d.close, g, 365); both, _ = bt(d.close, g & wk, 365)
        rows.append({"asset": s, "daily_%": base["return_pct"], "daily_and_weekly_%": both["return_pct"],
                     "wealth_given_up_%": (1 - (1 + both["return_pct"] / 100) / (1 + base["return_pct"] / 100)) * 100,
                     "daily_dd": base["max_dd_pct"], "both_dd": both["max_dd_pct"]})
    return pd.DataFrame(rows)


def fill_convention():
    rows = []
    for s in ASSETS:
        d = load(s, "1D"); g = d.green.to_numpy(bool)
        same, _ = bt(d.close, g, 365); nxt, _ = bt(d.close, np.r_[False, g[:-1]], 365); b = bh(d.close)
        rows.append({"asset": s, "same_bar_cagr": same["cagr_pct"], "next_bar_cagr": nxt["cagr_pct"],
                     "bh_cagr": b["cagr_pct"], "beats_bh_same": same["cagr_pct"] > b["cagr_pct"],
                     "beats_bh_next": nxt["cagr_pct"] > b["cagr_pct"],
                     "dd_same": same["max_dd_pct"], "dd_next": nxt["max_dd_pct"], "bh_dd": b["max_dd_pct"]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    f = lambda x: f"{x:,.1f}"  # noqa: E731
    for title, fn in (("1) Losing trades", losing_trades), ("2) Late entry (exit at red-flip close)", late_entry),
                      ("3) Era split", era_split), ("4) Daily AND Weekly", daily_and_weekly),
                      ("5) Same-bar vs next-bar fill", fill_convention)):
        print(f"\n{'=' * 100}\n  {title}\n{'=' * 100}")
        print(fn().to_string(index=False, float_format=f))
