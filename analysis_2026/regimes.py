"""Causal regime attribution and continuous crypto policy comparisons.

See REGIME_EXPERIMENT.md. Research only; no broker calls or deployment choices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026.moneyline_ref import moneyline

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ("BTC", "ETH", "SOL", "BNB", "ZEC")
POLICIES = ("hold", "moneyline", "hold_bull_ml_other", "ml_bull_cash_other",
            "hold_bull_cash_other", "ml_other_cash_bull", "ml_bull_hold_other")
CLASSIFIERS = ("btc_sma200", "own_sma200", "btc_sma150", "btc_sma250",
               "btc_level200", "btc_drawdown")


def validate(d):
    if not isinstance(d.index, pd.DatetimeIndex) or not d.index.is_unique:
        raise ValueError("Prices require unique daily dates")
    if not d.index.is_monotonic_increasing or (d.index != d.index.normalize()).any():
        raise ValueError("Prices require sorted midnight daily labels")
    if len(d) < 2 or not d.index.equals(pd.date_range(d.index[0], d.index[-1])):
        raise ValueError("Missing daily bars; no stale fills or gap bridging")
    for k in ("close", "open"):
        if k in d and (not np.isfinite(d[k]).all() or (d[k] <= 0).any()):
            raise ValueError("Nonpositive or nonfinite prices")
    if "high" in d and ((d.high < d[["open", "close", "low"]].max(axis=1)).any()
                        or (d.low > d[["open", "close", "high"]].min(axis=1)).any()):
        raise ValueError("Invalid OHLC geometry")


def load_tv(path):
    raw = pd.read_csv(path)
    idx = pd.to_datetime(raw.time, unit="s")
    up, dn = (pd.to_numeric(raw[k], errors="coerce") for k in ("Up Trend", "Down Trend"))
    if (up.notna() & dn.notna()).any():
        raise ValueError("Conflicting exported Moneyline states")
    valid = up.notna() | dn.notna()
    if not valid.any():
        raise ValueError("No exported indicator state")
    first = int(np.flatnonzero(valid)[0])
    if not valid.iloc[first:-1].all():
        raise ValueError("Missing indicator state inside export")
    d = pd.DataFrame({"close": pd.to_numeric(raw.close).to_numpy(),
                      "green": up.notna().to_numpy()}, index=idx)
    d = d.iloc[first:-1].copy()  # always discard potentially forming final export bar
    validate(d)
    return d


def sma_regime(close, window=200, slope=20):
    ma = close.rolling(window, min_periods=window).mean()
    if slope:
        change = ma - ma.shift(slope)
        valid = ma.notna() & change.notna()
        bull = (close > ma) & (change > 0)
        bear = (close < ma) & (change < 0)
    else:
        valid = ma.notna()
        bull, bear = close > ma, close < ma
    out = pd.Series("unavailable", index=close.index, dtype=object)
    out.loc[valid] = "transition"
    out.loc[valid & bull] = "bull"
    out.loc[valid & bear] = "bear"
    return out


def drawdown_regime(close):
    dd = close / close.cummax() - 1
    out, state = [], "bull"
    for x in dd:
        if x <= -0.20:
            state = "bear"
        elif x >= -0.10:
            state = "bull"
        out.append(state)
    return pd.Series(out, index=close.index)


def regimes(d, btc):
    out = {}
    for name, window, slope in (("btc_sma200", 200, 20), ("btc_sma150", 150, 20),
                                ("btc_sma250", 250, 20), ("btc_level200", 200, 0)):
        out[name] = sma_regime(btc.close, window, slope).reindex(d.index)
    out["own_sma200"] = sma_regime(d.close)
    out["btc_drawdown"] = drawdown_regime(btc.close).reindex(d.index)
    if any(v.isna().any() for v in out.values()):
        raise ValueError("BTC reference dates absent; no regime forward filling")
    return out


def conditions(d):
    c = d.close
    travel = c.diff().abs().rolling(60).sum()
    er = c.diff(60).abs() / travel
    # A completely motionless path is choppy, not missing.
    er = er.mask(travel == 0, 0)
    vol = c.pct_change(fill_method=None).rolling(60).std(ddof=1) * np.sqrt(365.25)
    threshold = vol.shift(1).expanding(min_periods=365).quantile(.75)
    return {"efficiency": pd.Series(np.where(er.isna(), "unavailable",
                           np.where(er < .25, "choppy", "directional")), index=d.index),
            "volatility": pd.Series(np.where(threshold.isna(), "unavailable",
                           np.where(vol > threshold, "high", "normal")), index=d.index)}


def targets(green, regime):
    if regime.isna().any():
        raise ValueError("Undefined classifier dates")
    g = green.astype(bool)
    b = regime.eq("bull")
    available = regime.ne("unavailable")
    return {"hold": pd.Series(True, index=g.index), "moneyline": g,
            "hold_bull_ml_other": (b | g) & available,
            "ml_bull_cash_other": b & g,
            "hold_bull_cash_other": b,
            "ml_other_cash_bull": ~b & g & available,
            "ml_bull_hold_other": (~b | g) & available}


def simulate(d, target, start, end, cost=.0015, execution="close", lag=1,
             cash_rate=0.0, tax=False):
    """All-in or cash, uninterrupted across regimes/years; actual full-sale costs.

    close: completed signal t executes at close t+lag. open: at open t+lag.
    Tax sensitivity pays immediately, carries dollar losses, has no refunds/wash.
    """
    validate(d)
    if execution not in ("open", "close") or lag < 1 or not 0 <= cost < 1:
        raise ValueError("Invalid execution, lag or cost")
    if not target.index.equals(d.index) or target.isna().any():
        raise ValueError("Targets must cover prices")
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    dates = pd.date_range(start, end)
    if not dates.isin(d.index).all():
        raise ValueError("Requested window incomplete")
    loc = d.index.get_indexer(dates)
    if loc[0] < lag:
        raise ValueError("Insufficient preceding signal bars")
    cash, qty, basis, carry = 1.0, 0.0, 0.0, 0.0
    entry_date = None
    rows = []
    want = target.to_numpy(bool)
    c = d.close.to_numpy(float)
    pxs = d[execution if execution == "open" else "close"].to_numpy(float)
    rf = (1 + cash_rate) ** (1 / 365.25)
    for k, i in enumerate(loc):
        date, px = d.index[i], pxs[i]
        turnover, paid, held = 0, 0.0, qty > 0
        # Close execution: today's cash earns a day before the end-of-day trade.
        if execution == "close":
            cash *= rf
        if bool(want[i - lag]) != held:
            turnover += 1
            if held:
                proceeds = qty * px * (1 - cost)
                gain = proceeds - basis
                if tax:
                    if gain < 0:
                        carry += -gain
                    else:
                        offset = min(carry, gain)
                        carry -= offset
                        rate = .20 if (date - entry_date).days > 365 else .35
                        paid += (gain - offset) * rate
                cash, qty = proceeds - paid, 0.0
            else:
                basis, entry_date = cash, date
                qty, cash = cash / (px * (1 + cost)), 0.0
        exposed = qty > 0 if execution == "open" else held
        if execution == "open":
            cash *= rf
        if k == len(loc) - 1 and qty > 0:
            proceeds = qty * c[i] * (1 - cost)
            gain = proceeds - basis
            if tax:
                offset = min(carry, max(gain, 0))
                rate = .20 if (date - entry_date).days > 365 else .35
                final_tax = max(gain - offset, 0) * rate
                paid += final_tax
            else:
                final_tax = 0.0
            cash, qty = proceeds - final_tax, 0.0
            turnover += 1
        rows.append((cash + qty * c[i], int(exposed), turnover, paid))
    out = pd.DataFrame(rows, columns=["equity", "exposed", "sides", "tax"], index=dates)
    out["log_return"] = np.log(out.equity).diff()
    out.iloc[0, out.columns.get_loc("log_return")] = np.log(out.equity.iloc[0])
    return out


def stats(path):
    e = path.equity.to_numpy(float)
    # Include pre-entry capital, so first-day losses are counted in drawdown.
    peaks = np.maximum.accumulate(np.r_[1.0, e])[1:]
    years = len(e) / 365.25
    r = np.expm1(path.log_return)
    return {"cagr_pct": (e[-1] ** (1 / years) - 1) * 100,
            "max_dd_pct": float(np.min(e / peaks - 1) * 100),
            "sharpe_zero_rf": float(r.mean() / r.std(ddof=1) * np.sqrt(365.25)) if r.std() > 0 else 0,
            "terminal_multiple": e[-1], "exposure_pct": path.exposed.mean() * 100,
            "transaction_sides": int(path.sides.sum()), "tax_paid_initial_units": path.tax.sum()}


def attribution(path, benchmark, labels):
    # Each date's label was known at its preceding close. No reset at regime seams.
    state = labels.shift(1).reindex(path.index)
    active = path.log_return - benchmark.log_return
    rows = []
    for label in sorted(state.dropna().unique()):
        mask = state.eq(label)
        x = active[mask]
        ids = np.flatnonzero(mask)
        episodes = int(np.sum(np.r_[True, np.diff(ids) > 1])) if len(ids) else 0
        rows.append({"regime": label, "days": int(mask.sum()), "episodes": episodes,
                     "active_log_wealth": x.sum(),
                     "active_log_pct_per_regime_year": x.mean() * 365.25 * 100,
                     "strategy_log_wealth": path.log_return[mask].sum(),
                     "hold_log_wealth": benchmark.log_return[mask].sum(),
                     "exposure_pct": path.exposed[mask].mean() * 100})
    if state.isna().any() or not np.isclose(sum(r["active_log_wealth"] for r in rows), active.sum()):
        raise ValueError("Attribution does not reconcile to total relative wealth")
    return rows


def block_uncertainty(active, seed=20261014, draws=2000, block=90):
    """Moving-block bootstrap of shared-date equal-weight log active returns.

    Conditional uncertainty only; no parameter-search correction or alpha proof.
    """
    a = active.dropna().to_numpy(float)
    if len(a) < block * 2:
        return {}
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(a) - block + 1, size=(draws, int(np.ceil(len(a) / block))))
    sample = a[starts[..., None] + np.arange(block)].reshape(draws, -1)[:, :len(a)]
    means = sample.mean(axis=1) * 365.25 * 100
    return {"shared_days": len(a), "block_days": block, "draws": draws,
            "mean_active_log_pct_per_year": a.mean() * 365.25 * 100,
            "ci_2_5": np.quantile(means, .025), "ci_97_5": np.quantile(means, .975)}


def windows(d, classifiers):
    valid = pd.Series(True, index=d.index)
    for r in classifiers.values():
        valid &= r.notna() & r.ne("unavailable")
    # Same window for all declared neighbors and enough own-price warm-up.
    valid.iloc[:270] = False
    starts = np.flatnonzero(valid.to_numpy())
    if not len(starts) or starts[0] + 2 >= len(d):
        return []
    first, last = d.index[starts[0] + 2], d.index[-1]
    out = [("full", first, last)]
    for name, a, b in (("development", first, pd.Timestamp("2022-12-31")),
                       ("later", pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31")),
                       ("2026", pd.Timestamp("2026-01-01"), last)):
        a, b = max(first, a), min(last, b)
        if b >= a and (b - a).days >= 90:
            # Fixed later window must reach 2025-12-31; don't rename truncation a test.
            if name == "later" and last < pd.Timestamp("2025-12-31"):
                continue
            out.append((name, a, b))
    return out


def read_ohlc(folder):
    data, failures = {}, []
    for p in sorted(folder.glob("*.csv")):
        try:
            d = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
            validate(d)
            d["green"] = moneyline(d).green
            data[p.stem.removesuffix("USDT")] = d
        except (ValueError, KeyError) as e:
            failures.append({"asset": p.stem, "reason": str(e)})
    return data, failures


def payoff_reproduction(out):
    x = pd.read_csv(ROOT / "analysis_2026/results_altcoins/coin_years_retail.csv")
    x = x[x.year <= 2025].copy()
    from analysis_2026.altcoins import payoff
    p = payoff(x)
    p.to_csv(out / "hindsight_payoff.csv")
    btc = x[x.coin == "BTC"].set_index("year").bh
    x["btc_year"] = x.year.map((btc > 1).map({True: "rising", False: "falling"}))
    x["active_log"] = np.log(x.sig / x.bh)
    rows = []
    for (market, tier), g in x.groupby(["btc_year", "tier"]):
        rows.append({"btc_year": market, "tier": tier, "coin_years": len(g),
                     "market_years": g.year.nunique(), "signal_beats_hold_pct": (g.sig > g.bh).mean() * 100,
                     "median_active_log": g.active_log.median()})
    pd.DataFrame(rows).to_csv(out / "hindsight_btc_year.csv", index=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ohlc-folder", type=Path)
    ap.add_argument("--output", type=Path, default=ROOT / "analysis_2026/results_regimes")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = {"tradingview_close": {s: load_tv(ROOT / f"data/tv_full/{s}_1D.csv") for s in ASSETS}}
    failed = []
    if args.ohlc_folder:
        sources["binance_open"], failed = read_ohlc(args.ohlc_folder)
    metrics, attrs, years, blocks, coverage, receipt = [], [], [], [], [], {"inputs": []}
    panels = {}
    for source, data in sources.items():
        if "BTC" not in data:
            raise ValueError("BTC reference unavailable")
        execution = "close" if source == "tradingview_close" else "open"
        for asset, d in data.items():
            rgs = regimes(d, data["BTC"])
            ws = windows(d, rgs)
            coverage.append({"source": source, "asset": asset, "bars": len(d),
                             "first": str(d.index[0].date()), "last": str(d.index[-1].date()),
                             "later_complete": d.index[-1] >= pd.Timestamp("2025-12-31"),
                             "comparison_windows": ",".join(w[0] for w in ws)})
            for classifier, rg in rgs.items():
                ts = targets(d.green, rg)
                for window, start, end in ws:
                    # Primary full grid; neighbor classifiers retain pretax base scenario.
                    scenarios = [(c, lag, rate, tax) for c in (.0015, .003, .0095)
                                 for lag in (1, 2) for rate, tax in ((0, False), (0, True), (.04, False))] \
                        if classifier == "btc_sma200" else [(.0015, 1, 0, False), (.0095, 1, 0, False)]
                    for cost, lag, cash_rate, tax in scenarios:
                        base = {"source": source, "asset": asset, "classifier": classifier,
                                "window": window, "start": str(start.date()), "end": str(end.date()),
                                "cost": cost, "lag": lag, "cash_rate": cash_rate, "tax": tax}
                        paths = {}
                        for policy, target in ts.items():
                            path = simulate(d, target, start, end, cost, execution, lag, cash_rate, tax)
                            paths[policy] = path
                        for policy, path in paths.items():
                            m = stats(path)
                            metrics.append({**base, "policy": policy, **m,
                                            "cagr_edge_hold": m["cagr_pct"] - stats(paths["hold"])["cagr_pct"],
                                            "cagr_edge_ml": m["cagr_pct"] - stats(paths["moneyline"])["cagr_pct"]})
                        if classifier == "btc_sma200" and cost == .0015 and lag == 1 and cash_rate == 0 and not tax:
                            for policy, path in paths.items():
                                for label_name, labels in {"market": rg, **conditions(d)}.items():
                                    attrs.extend({**base, "policy": policy, "condition": label_name, **a}
                                                 for a in attribution(path, paths["hold"], labels))
                            if window == "full":
                                # Annual and 365-day block increments, without resetting trades.
                                for policy, path in paths.items():
                                    active = path.log_return - paths["hold"].log_return
                                    for y, g in path.groupby(path.index.year):
                                        years.append({**base, "policy": policy, "year": y, "days": len(g),
                                                      "return_pct": np.expm1(g.log_return.sum()) * 100,
                                                      "hold_return_pct": np.expm1(paths["hold"].loc[g.index].log_return.sum()) * 100,
                                                      "active_log_wealth": active.loc[g.index].sum()})
                                    for b in range(len(path) // 365):
                                        ix = path.index[b * 365:(b + 1) * 365]
                                        blocks.append({**base, "policy": policy, "block": b,
                                                       "block_start": str(ix[0].date()), "block_end": str(ix[-1].date()),
                                                       "active_log_wealth": active.loc[ix].sum()})
                            if asset in ("BTC", "ETH") and window in ("full", "later"):
                                for policy in ("moneyline", "hold_bull_ml_other", "hold_bull_cash_other"):
                                    for control in ("hold", "moneyline"):
                                        panels.setdefault((source, window, policy, control), {})[asset] = \
                                            paths[policy].log_return - paths[control].log_return
    uncertainty = []
    for (source, window, policy, control), panel in panels.items():
        if set(panel) != {"BTC", "ETH"}:
            continue
        shared = pd.concat(panel, axis=1).dropna().mean(axis=1)
        for length in (30, 90, 180):
            uncertainty.append({"source": source, "window": window, "policy": policy,
                                "control": control, **block_uncertainty(shared, block=length)})
    for name, rows in (("metrics", metrics), ("attribution", attrs), ("calendar_years", years),
                       ("blocks365", blocks), ("coverage", coverage), ("unavailable", failed),
                       ("block_uncertainty", uncertainty)):
        pd.DataFrame(rows).to_csv(args.output / f"{name}.csv", index=False)
    payoff_reproduction(args.output)
    inputs = list((ROOT / "data/tv_full").glob("*_1D.csv")) + [ROOT / "analysis_2026/results_altcoins/coin_years_retail.csv"]
    if args.ohlc_folder:
        inputs += list(args.ohlc_folder.glob("*.csv"))
    for p in inputs:
        receipt["inputs"].append({"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    receipt.update({"code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "numpy": np.__version__, "pandas": pd.__version__,
                    "metrics_rows": len(metrics), "ohlc_folder_supplied": bool(args.ohlc_folder),
                    "scope": "Exploratory historical checks; no untouched holdout or live orders"})
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "metrics_rows": len(metrics), "coverage_rows": len(coverage),
                      "invalid_histories": failed}, indent=2))


if __name__ == "__main__":
    main()
