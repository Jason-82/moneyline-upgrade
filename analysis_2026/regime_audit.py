"""Rebuild every pretax research result using independent vector return factors."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026.regimes import ASSETS, ROOT, load_tv, read_ohlc, regimes, targets


def vector_path(d, target, start, end, cost, execution, lag, rate):
    a, b = d.index.get_indexer([pd.Timestamp(start), pd.Timestamp(end)])
    if a < lag or b < a:
        raise ValueError("Incomplete audit window")
    loc = np.arange(a, b + 1)
    w = target.to_numpy(bool)[loc - lag]
    prior = np.r_[False, w[:-1]]
    c = d.close.to_numpy(float)
    cc, pc = c[loc], c[loc - 1]
    rf = (1 + rate) ** (1 / 365.25)
    if execution == "close":
        factor = np.where(prior, cc / pc, rf)
        factor *= np.where(w & ~prior, 1 / (1 + cost), 1)
        factor *= np.where(~w & prior, 1 - cost, 1)
    else:
        oo = d.open.to_numpy(float)[loc]
        factor = np.where(w & prior, cc / pc,
                 np.where(w & ~prior, cc / oo / (1 + cost),
                 np.where(~w & prior, oo / pc * (1 - cost) * rf, rf)))
    factor[-1] *= (1 - cost) if w[-1] else 1
    return np.cumprod(factor)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ohlc-folder", type=Path)
    ap.add_argument("--results", type=Path, default=ROOT / "analysis_2026/results_regimes")
    args = ap.parse_args()
    sources = {"tradingview_close": {s: load_tv(ROOT / f"data/tv_full/{s}_1D.csv") for s in ASSETS}}
    if args.ohlc_folder:
        sources["binance_open"], _ = read_ohlc(args.ohlc_folder)
    cache = {}
    for source, data in sources.items():
        for asset, d in data.items():
            for classifier, rg in regimes(d, data["BTC"]).items():
                cache[source, asset, classifier] = targets(d.green, rg)
    metrics = pd.read_csv(args.results / "metrics.csv")
    errors = []
    rows = metrics[~metrics.tax]
    for r in rows.itertuples(index=False):
        d = sources[r.source][r.asset]
        t = cache[r.source, r.asset, r.classifier][r.policy]
        e = vector_path(d, t, r.start, r.end, r.cost,
                        "close" if r.source == "tradingview_close" else "open", r.lag, r.cash_rate)
        dd = (e / np.maximum.accumulate(np.r_[1.0, e])[1:] - 1).min() * 100
        err = abs(e[-1] / r.terminal_multiple - 1)
        errors.append(err)
        if err > 1e-11 or abs(dd - r.max_dd_pct) > 1e-9:
            raise AssertionError(f"Independent return mismatch: {r.source}/{r.asset}/{r.policy}")
    attr = pd.read_csv(args.results / "attribution.csv")
    for key, g in attr.groupby(["source", "asset", "window", "policy", "condition"]):
        source, asset, window, policy, _ = key
        m = metrics[(metrics.source == source) & (metrics.asset == asset) & (metrics.window == window)
                    & (metrics.classifier == "btc_sma200") & (metrics.cost == .0015)
                    & (metrics.lag == 1) & (metrics.cash_rate == 0) & (~metrics.tax)]
        ratio = m[m.policy == policy].terminal_multiple.iloc[0] / m[m.policy == "hold"].terminal_multiple.iloc[0]
        if not np.isclose(g.active_log_wealth.sum(), np.log(ratio), atol=1e-10):
            raise AssertionError(f"Attribution does not reconcile: {key}")
    original = pd.read_csv(ROOT / "analysis_2026/results_altcoins/payoff_crypto.csv")
    reproduced = pd.read_csv(args.results / "hindsight_payoff.csv")
    pd.testing.assert_frame_equal(original, reproduced, check_exact=False, rtol=1e-12)
    receipt = json.loads((args.results / "receipt.json").read_text())
    for entry in receipt["inputs"]:
        path = ROOT / "data/tv_full" / entry["name"]
        if entry["name"] == "coin_years_retail.csv":
            path = ROOT / "analysis_2026/results_altcoins" / entry["name"]
        elif not path.exists():
            if not args.ohlc_folder:
                raise ValueError("Audit needs the recorded OHLC inputs")
            path = args.ohlc_folder / entry["name"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise AssertionError(f"Input bytes changed: {path.name}")
    if hashlib.sha256((ROOT / "analysis_2026/regimes.py").read_bytes()).hexdigest() != receipt["code_sha256"]:
        raise AssertionError("Runner bytes changed since the recorded run")
    result = {"pretax_rows_rebuilt": len(rows), "max_terminal_relative_error": max(errors),
              "attribution_groups_reconciled": len(attr.groupby(["source", "asset", "window", "policy", "condition"])),
              "published_payoff_reproduced": True, "input_and_runner_hashes_verified": True,
              "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.results / "audit_receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
