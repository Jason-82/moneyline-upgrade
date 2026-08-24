"""
Robustness checks:
  1. Era split — does the edge survive in the modern market (2022+, 2024+)?
  2. Current live state — daily/weekly green or red, and when it last flipped.
  3. ZEC data-quality check on the chaotic launch window.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis_2026.common import (  # noqa: E402
    ASSETS, load_asset, to_weekly, add_indicators, buy_hold_return, bt,
)
from analysis_2026.strategies_ext import trail_reentry  # noqa: E402

pd.set_option("display.width", 200)


def era_table(start: str):
    rows = []
    for sym in ASSETS:
        d = load_asset(sym)
        d = d[d.index >= start]
        if len(d) < 300:
            continue
        ind = add_indicators(d, contraction_window=252)
        entry, exit_ = ind["long_cross"], ind["exit_cross"]

        _, base = bt(d, entry, exit_, 365)
        _, filt = bt(d, entry & ind["contracted_recent"], exit_, 365)
        _, hyb = bt(d, ind["trend_green"] & ind["breakout_long"] & ind["contracted_recent"], exit_, 365)
        tr20, _ = trail_reentry(d, entry, exit_, ind["trend_green"], trail_pct=20, periods_per_year=365)

        rows.append({
            "asset": sym,
            "B&H": buy_hold_return(d),
            "Baseline": base["return_pct"],
            "Base DD": base["max_dd_pct"],
            "Filtered": filt["return_pct"],
            "Hybrid": hyb["return_pct"],
            "Trail20+RE": tr20["return_pct"],
            "Trail20 DD": tr20["max_dd_pct"],
            "Base trades": base["trades"],
        })
    return pd.DataFrame(rows)


def live_state():
    rows = []
    for sym in ASSETS:
        d = load_asset(sym)
        w = to_weekly(d)
        di = add_indicators(d, contraction_window=252)
        wi = add_indicators(w, contraction_window=52)

        def last_flip(ind):
            g = ind["trend_green"]
            flips = g.ne(g.shift(1))
            flips.iloc[0] = False
            idx = g.index[flips]
            return idx[-1] if len(idx) else None

        d_flip, w_flip = last_flip(di), last_flip(wi)
        asof = d.index[-1]
        rows.append({
            "asset": sym,
            "price": d["close"].iloc[-1],
            "daily": "GREEN" if di["trend_green"].iloc[-1] else "RED",
            "daily_since": d_flip.date() if d_flip is not None else "-",
            "daily_days": (asof - d_flip).days if d_flip is not None else "-",
            "weekly": "GREEN" if wi["trend_green"].iloc[-1] else "RED",
            "weekly_since": w_flip.date() if w_flip is not None else "-",
            "weekly_wks": (w.index[-1] - w_flip).days // 7 if w_flip is not None else "-",
            "contracted": bool(di["contracted_recent"].iloc[-1]),
        })
    return pd.DataFrame(rows)


def zec_quality():
    d = load_asset("ZEC")
    return d.head(20)[["close"]]


if __name__ == "__main__":
    for era in ("2022-01-01", "2024-01-01"):
        print(f"\n{'='*110}\n  DAILY STRATEGIES SINCE {era[:4]}  (returns %, DD %)\n{'='*110}")
        print(era_table(era).to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    print(f"\n\n{'='*110}\n  CURRENT STATE (as of last bar)\n{'='*110}")
    print(live_state().to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    print(f"\n\n{'='*110}\n  ZEC FIRST 20 DAILY CLOSES (data-quality check)\n{'='*110}")
    print(zec_quality().to_string(float_format=lambda x: f"{x:,.2f}"))
