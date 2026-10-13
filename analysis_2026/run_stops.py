"""Sweep of ATR-stop variants vs indicator-only exit. Writes results_stops.csv."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.stops import simulate, run_attribution, ASSETS  # noqa: E402

VARIANTS = [("indicator only", dict(mode="none"))]
for k in (1.0, 1.5, 2.0, 2.5, 3.0):
    VARIANTS.append((f"fixed {k}xD", dict(mode="fixed", k=k)))
for k in (1.5, 2.0, 2.5, 3.0, 4.0):
    VARIANTS.append((f"trail {k}xD", dict(mode="trail", k=k)))
VARIANTS += [
    ("fixed 1.5xW", dict(mode="fixed", k=1.5, atr_src="weekly")),
    ("trail 1.5xW", dict(mode="trail", k=1.5, atr_src="weekly")),
    ("fixed 1.5xD +reentry@entry", dict(mode="fixed", k=1.5, reentry="entry")),
    ("fixed 1.5xD +reentry@high", dict(mode="fixed", k=1.5, reentry="high")),
    ("trail 1.5xD +reentry@high", dict(mode="trail", k=1.5, reentry="high")),
]


def sweep(start=None, wick=0.0):
    rows = []
    for name, kw in VARIANTS:
        for s in ASSETS:
            m, _, _ = simulate(s, start=start, wick=wick, **kw)
            rows.append({"variant": name, "asset": s, **m})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent
    settings = {
        "close": dict(),                          # stop checked on the daily close
        "wick04": dict(wick=0.4),                 # resting stop order, ETF-calibrated wick
        "wick06": dict(wick=0.6),                 # resting stop order, crypto stress wick
        "close_2022": dict(start="2022-01-01"),   # recent regime only
    }
    frames = []
    for tag, kw in settings.items():
        df = sweep(**kw).assign(setting=tag)
        frames.append(df)
    allres = pd.concat(frames, ignore_index=True)
    allres.to_csv(out / "results_stops.csv", index=False)
    cg = allres.pivot_table(index=["setting", "variant"], columns="asset", values="cagr_pct", sort=False)
    print(cg.to_string(float_format=lambda x: f"{x:,.1f}"))
