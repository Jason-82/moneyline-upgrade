"""
Full strategy sweep across BTC / ETH / SOL / BNB / ZEC on daily and weekly bars.
Writes results to analysis_2026/results_{daily,weekly}.csv and prints tables.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis_2026.common import (  # noqa: E402
    ASSETS, load_asset, to_weekly, add_indicators, align_weekly_state,
    buy_hold_return, bt,
)
from analysis_2026.strategies_ext import trail_reentry, scaled_entry  # noqa: E402

pd.set_option("display.width", 200)


def run_timeframe(symbol, df, weekly_state=None, ppy=365, contraction_window=252):
    """Run every strategy on one timeframe for one asset."""
    ind = add_indicators(df, contraction_window=contraction_window)
    entry = ind["long_cross"]
    exit_ = ind["exit_cross"]
    rows = []

    def add(name, m):
        rows.append({"asset": symbol, "strategy": name, **m})

    # 1. Buy & hold
    add("Buy & Hold", {
        "return_pct": buy_hold_return(df), "cagr_pct": float("nan"),
        "max_dd_pct": ((df["close"] / df["close"].cummax()) - 1).min() * 100,
        "sharpe": float("nan"), "trades": 1, "win_rate": float("nan"),
        "profit_factor": float("nan"), "avg_win": float("nan"), "avg_loss": float("nan"),
        "chop_pct": 0.0, "exposure_pct": 100.0,
    })

    # 2. Baseline — pure Moneyline crossover
    _, m = bt(df, entry, exit_, ppy)
    add("Baseline", m)

    # 3. Filtered — crossover must coincide with recent contraction
    _, m = bt(df, entry & ind["contracted_recent"], exit_, ppy)
    add("Filtered", m)

    # 4. Hybrid — trend green + breakout + contraction (no crossover required)
    hybrid_entry = ind["trend_green"] & ind["breakout_long"] & ind["contracted_recent"]
    _, m = bt(df, hybrid_entry, exit_, ppy)
    add("Hybrid", m)

    # 5. Scaled entry — 25% on cross, remainder on contraction+breakout
    m, _ = scaled_entry(df, entry, exit_,
                        ind["breakout_long"] & ind["contracted_recent"],
                        initial_frac=0.25, periods_per_year=ppy)
    add("Scaled 25%", m)

    # 6-8. Trailing stop + re-entry
    for trail in (15, 20, 25):
        m, _ = trail_reentry(df, entry, exit_, ind["trend_green"],
                             trail_pct=trail, periods_per_year=ppy)
        add(f"Trail {trail}% + Reentry", m)

    # 9. Higher-timeframe confirmation (daily only)
    if weekly_state is not None:
        confirm_entry = entry & weekly_state
        confirm_exit = exit_ | (~weekly_state & weekly_state.shift(1).fillna(False))
        _, m = bt(df, confirm_entry, confirm_exit, ppy)
        add("Daily + Weekly green", m)

    return pd.DataFrame(rows)


def main():
    daily_frames, weekly_frames, coverage = [], [], []

    for sym in ASSETS:
        d = load_asset(sym)
        w = to_weekly(d)
        w_ind = add_indicators(w, contraction_window=52)
        w_state = align_weekly_state(d.index, w_ind)

        coverage.append({
            "asset": sym, "start": d.index[0].date(), "end": d.index[-1].date(),
            "daily_bars": len(d), "weekly_bars": len(w),
            "first_price": d["close"].iloc[0], "last_price": d["close"].iloc[-1],
        })

        daily_frames.append(run_timeframe(sym, d, weekly_state=w_state, ppy=365,
                                          contraction_window=252))
        weekly_frames.append(run_timeframe(sym, w, weekly_state=None, ppy=52,
                                           contraction_window=52))

    daily = pd.concat(daily_frames, ignore_index=True)
    weekly = pd.concat(weekly_frames, ignore_index=True)

    out = Path(__file__).resolve().parent
    daily.to_csv(out / "results_daily.csv", index=False)
    weekly.to_csv(out / "results_weekly.csv", index=False)
    pd.DataFrame(coverage).to_csv(out / "coverage.csv", index=False)

    print("\n=== DATA COVERAGE ===")
    print(pd.DataFrame(coverage).to_string(index=False))

    for label, frame in (("DAILY", daily), ("WEEKLY", weekly)):
        print(f"\n\n{'='*100}\n  {label} TIMEFRAME\n{'='*100}")
        for sym in ASSETS:
            sub = frame[frame.asset == sym].copy()
            print(f"\n--- {sym} ---")
            disp = sub[["strategy", "return_pct", "cagr_pct", "max_dd_pct", "sharpe",
                        "trades", "win_rate", "profit_factor", "chop_pct", "exposure_pct"]]
            print(disp.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))


if __name__ == "__main__":
    main()
