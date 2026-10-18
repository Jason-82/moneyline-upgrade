"""Execution modes (immediate / split / confirm5) vs buy & hold on repo data, via agentic.backtest.compare_modes.

Run from the repo root: python3 analysis_2026/results_agentic_modes/run_modes.py
Writes modes.csv next to this file (summary.txt is written by hand from it). Public price data only, but it reads the
gitignored downloads data/crypto_4h and data/etf, which a clone of the public repo does not have.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic.backtest import compare_modes  # noqa: E402
from agentic.config import DEFAULT_MODES  # noqa: E402
from analysis_2026.flip_delay import load_crypto_daily, load_etf  # noqa: E402

OUT = Path(__file__).resolve().parent
RUNS = [("crypto", s, c, 365, load_crypto_daily) for s in ("ETH", "SOL", "BTC") for c in (0.0015, 0.0095)] + \
       [("etf", s, 0.0002, 252, load_etf) for s in ("SPY", "QQQ", "IWM")]
WINDOWS = {"full": None, "2022+": "2022-01-01"}


def main():
    rows = []
    for cls, sym, cost, ppy, load in RUNS:
        df = load(sym)
        for win, start in WINDOWS.items():
            t = compare_modes(df, DEFAULT_MODES, cost, ppy, start=start)
            for mode, r in t.iterrows():
                rows.append({"asset": sym, "class": cls, "cost_pct": cost * 100, "window": win, "mode": mode,
                             **r.to_dict(), "start": t.attrs["start"].date(), "end": t.attrs["end"].date()})
    res = pd.DataFrame(rows)
    res.round(3).to_csv(OUT / "modes.csv", index=False)
    return res


def table(res, win):
    t = res[res.window == win].copy()
    t["cost"] = t.cost_pct.map(lambda c: f"{c:.2f}%")
    keep = ["asset", "cost", "mode", "CAGR_%", "CAGR_tax_%", "Sharpe", "maxDD_%", "trades_per_yr", "exposure_%"]
    return t[keep].round(2).to_string(index=False)


if __name__ == "__main__":
    res = main()
    with pd.option_context("display.width", 200):
        for w in WINDOWS:
            print(f"--- window {w}")
            print(table(res, w))
