"""Compatibility helpers for the corrected stock-selection experiment.

The historical independent-stock/per-window selection conclusions are superseded.
The executable entry point now uses research.run's continuous benchmark engine.
Missing terminal outcomes are never converted into zero-return cash observations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.config import HOLDOUT_START
from research.selection import daily_returns, window_metrics, synthetic

COST = 0.0003
PRIMARY = "skill"
CRITERIA = ["skill", "gate", "edge", "vol", "random"]


def score(metric, criterion, rng):
    if criterion in ("skill", "edge", "pf", "vr20", "vol"):
        return metric[criterion]
    if criterion == "gate":
        good = metric["edge"] > 0 and metric["pf"] >= 2 and metric["edge_ex_best"] > 0
        return metric["skill"] if good else -np.inf
    if criterion == "bh_dd":
        return -metric["bh_dd"]
    if criterion == "random":
        return rng.random()
    raise ValueError(criterion)


def splits(first, last, form=5, test=3, step=None):
    """Legacy schedule helper, disallowing overlapping future test periods."""
    step = test if step is None else step
    if step < test:
        raise ValueError("Test windows may not overlap")
    result, year = [], pd.Timestamp(first).year + 1
    while pd.Timestamp(f"{year + form + test}-01-01") <= pd.Timestamp(last) + pd.Timedelta(days=7):
        result.append((f"{year}-01-01", f"{year + form - 1}-12-31",
                       f"{year + form}-01-01", f"{year + form + test - 1}-12-31"))
        year += step
    return result


def run(data, top_n=20, form=5, test=3, step=None, min_trades=8, seed=0, n_perm=500, members=None):
    """Compatibility adapter; requires an actual SPY benchmark in the price pool."""
    from screener.strictness import run as corrected_run
    if "SPY" not in data:
        raise ValueError("Corrected stock-selection research requires SPY OHLC and its actual session calendar")
    if step not in (None, test):
        raise ValueError("Use the fixed non-overlapping development windows in research.config")
    return corrected_run(data, data["SPY"], members, form=form, test=test, min_trades=min_trades,
                         seed=seed, n_perm=n_perm, criteria=("skill",), levels=(f"top{top_n}",))


def summarise(result):
    from screener.strictness import chain
    return chain(result)


def perm_pvalues(*args, **kwargs):
    raise ValueError("The old permutation inference is superseded. Use research.selection.permutation_selection_test")


def main():
    from screener.strictness import main as corrected_main
    corrected_main()


if __name__ == "__main__":
    main()
