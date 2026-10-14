"""Post-run sensitivity on the favorable ETH own-trend case; no new rule search.

This follow-up was added after inspecting the declared study. It is not an
untouched holdout or another preregistered hypothesis.
"""
import argparse
from pathlib import Path

import pandas as pd

from analysis_2026.regimes import ASSETS, ROOT, load_tv, read_ohlc, regimes, targets, simulate, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ohlc-folder", type=Path)
    ap.add_argument("--output", type=Path, default=ROOT / "analysis_2026/results_regimes")
    args = ap.parse_args()
    sources = {"tradingview_close": {s: load_tv(ROOT / f"data/tv_full/{s}_1D.csv") for s in ASSETS}}
    if args.ohlc_folder:
        sources["binance_open"], _ = read_ohlc(args.ohlc_folder)
    rows = []
    for source, data in sources.items():
        d = data["ETH"]
        t = targets(d.green, regimes(d, data["BTC"])["own_sma200"])
        for fee in (.0015, .0095):
            for lag in (1, 2):
                for tax in (False, True):
                    for policy in ("hold", "moneyline", "hold_bull_ml_other"):
                        p = simulate(d, t[policy], "2023-01-01", "2025-12-31", fee,
                                     "close" if source == "tradingview_close" else "open", lag, tax=tax)
                        rows.append({"source": source, "asset": "ETH", "classifier": "own_sma200",
                                     "window": "later", "cost": fee, "lag": lag, "tax": tax,
                                     "policy": policy, **stats(p)})
    args.output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output / "eth_own_followup_sensitivity.csv", index=False)
    print(f"Saved {len(rows)} post-run sensitivity rows")


if __name__ == "__main__":
    main()
