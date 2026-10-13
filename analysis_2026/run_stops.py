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
    full = sweep()
    full.to_csv(out / "results_stops.csv", index=False)
    print(full.pivot_table(index="variant", columns="asset", values="return_pct", sort=False)
          .to_string(float_format=lambda x: f"{x:,.0f}"))
