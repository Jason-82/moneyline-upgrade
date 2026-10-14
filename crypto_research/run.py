"""Frozen, all-candidate crypto comparisons with honest unavailable outcomes.

No function here submits an order, selects a deployment winner, or silently
replaces a vanished listing with a surviving coin.  Frozen settings precede this
run; the historical validation window remains previously exposed history.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from crypto_research.config import (CryptoExperimentConfig, CryptoWindow, canonical_json,
                                   freeze_config, implementation_fingerprint, read_frozen, sha256)


@dataclass
class CryptoExperimentResult:
    summary: pd.DataFrame
    paths: pd.DataFrame
    coin_results: pd.DataFrame
    paired_variants: pd.DataFrame
    trade_ledger: pd.DataFrame
    report: dict


METRIC_NAMES = ("cagr", "max_drawdown", "total_return", "sharpe365", "exposure", "turnover",
                "trades", "trades_per_year", "win_rate", "mean_winning_return",
                "mean_losing_return", "profit_factor", "top_winner_profit_share", "final_value",
                "closed_lots", "gross_winning_gain", "gross_losing_loss", "total_fees", "total_tax")


def _json_safe(value: Any):
    """Standards-compliant JSON uses null for unidentified metrics, never NaN."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def selected_symbols(dataset, window: CryptoWindow, group: str, config: CryptoExperimentConfig) -> tuple[str, ...]:
    """Use the dated, frozen formation table; never inspect later survival."""
    table = dataset.universe
    needed = {"formation_date", "group", "rank", "symbol", "median_quote_volume"}
    if not needed.issubset(table.columns):
        raise ValueError(f"Dated universe lacks columns: {sorted(needed - set(table.columns))}")
    formation = pd.to_datetime(table.formation_date, errors="raise").dt.strftime("%Y-%m-%d")
    picks = table.loc[(formation == window.formation_date) & (table.group == group)].sort_values("rank")
    rank = pd.to_numeric(picks["rank"], errors="raise")
    quote_volume = pd.to_numeric(picks.median_quote_volume, errors="raise")
    if not np.isfinite(rank).all() or not np.isfinite(quote_volume).all() or (rank % 1 != 0).any():
        raise ValueError("Universe ranks and formation liquidity must be finite, with integer ranks")
    if picks.symbol.duplicated().any() or picks["rank"].duplicated().any() or len(picks) > config.slot_capacity:
        raise ValueError("Invalid duplicated or oversized dated universe")
    lower, upper = (1, 20) if group == "liquid_top20" else (21, 40)
    if not picks.empty and ((rank < lower) | (rank > upper)).any():
        raise ValueError("Liquidity group does not match its declared historical ranks")
    if not picks.empty and (quote_volume < config.min_median_quote_volume).any():
        raise ValueError("Universe contains a coin below its frozen formation liquidity threshold")
    return tuple(picks.symbol.astype(str))


def require_formation_history(prices: dict, symbols: tuple[str, ...], formation: str,
                              min_bars: int) -> None:
    """Require warmup that was already observable at formation, not test survival."""
    day = pd.Timestamp(formation)
    required = pd.date_range(day - pd.Timedelta(days=min_bars - 1), day, freq="D")
    for symbol in symbols:
        if symbol not in prices:
            raise ValueError(f"Missing selected price history: {symbol}")
        prefix = prices[symbol].loc[:day]
        if len(required.difference(prefix.index)):
            raise ValueError(f"Missing preformation {min_bars}-day warmup: {symbol}")


def _row(identity: dict, result=None, error: str | None = None) -> dict:
    row = dict(identity)
    row.update({name: np.nan for name in METRIC_NAMES})
    row.update(status="UNIDENTIFIED" if error else "IDENTIFIED_EXPLORATORY", error=error or "",
               deployment_blocked=True, qualified=False)
    if result is None:
        return row
    metrics = dict(result.metrics)
    summary = dict(result.trade_summary)
    for name in METRIC_NAMES:
        value = metrics.get(name, summary.get(name, np.nan))
        if name == "win_rate" and name not in summary:
            value = np.nan
        row[name] = value
    row["flags"] = "; ".join(map(str, result.flags))
    # Metrics are fractions.  Explicitly named percent columns are conveniences.
    for name in ("cagr", "max_drawdown", "total_return", "exposure", "win_rate",
                 "mean_winning_return", "mean_losing_return", "top_winner_profit_share"):
        row[name + "_pct"] = row[name] * 100 if np.isfinite(row[name]) else np.nan
    return row


def _benchmark_row(path: pd.Series, identity: dict, initial_capital: float) -> dict:
    values = np.r_[initial_capital, path.to_numpy(dtype=float)]
    returns = values[1:] / values[:-1] - 1
    years = len(path) / 365.25
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0
    row = _row(identity)
    row.update(cagr=(values[-1] / initial_capital) ** (1 / years) - 1,
               max_drawdown=float(np.min(values / np.maximum.accumulate(values)) - 1),
               total_return=values[-1] / initial_capital - 1,
               sharpe365=float(np.mean(returns) / std * np.sqrt(365)) if std > 0 else np.nan,
               final_value=values[-1], flags=str(path.attrs.get("flags", "")))
    for name in ("cagr", "max_drawdown", "total_return"):
        row[name + "_pct"] = row[name] * 100
    row["benchmark_policy"] = "provider_adjusted_total_return_frictionless_DRIP_cash_until_first_NYSE_open"
    return row


def paired_variant_results(coins: pd.DataFrame) -> pd.DataFrame:
    if coins.empty:
        return pd.DataFrame()
    keys = ["window", "group", "symbol", "cost_bps", "tax_mode"]
    measures = ["cagr", "max_drawdown", "trades", "win_rate", "mean_winning_return",
                "mean_losing_return", "top_winner_profit_share", "turnover", "exposure"]
    baseline = coins.loc[coins.candidate == "moneyline", keys + ["status"] + measures].copy()
    baseline = baseline.rename(columns={key: "baseline_" + key for key in ["status"] + measures})
    result = coins.loc[coins.candidate != "moneyline"].merge(baseline, on=keys, how="left", validate="many_to_one")
    for name in measures:
        result["delta_" + name] = result[name] - result["baseline_" + name]
    result["paired_identified"] = ((result.status == "IDENTIFIED_EXPLORATORY") &
                                    (result.baseline_status == "IDENTIFIED_EXPLORATORY"))
    return result


def run_experiment(dataset, config: CryptoExperimentConfig | None = None, *, frozen: dict | None = None,
                   benchmark_directory: str | Path | None = None,
                   include_attribution: bool = True) -> CryptoExperimentResult:
    from crypto_research.portfolio import (CryptoPortfolioConfig, CryptoPortfolioDataError,
                                          Rebalance, simulate_portfolio)
    from crypto_research.signals import candidate_signals
    from research.tax import TaxRates

    config = config or CryptoExperimentConfig()
    config.validate()
    if frozen is None:
        raise ValueError("Run requires a settings/input/implementation artifact frozen before outcomes")
    if frozen.get("sha256") != sha256({k: v for k, v in frozen.items() if k != "sha256"}):
        raise ValueError("Run received an invalid frozen artifact hash")
    if frozen.get("implementation_sha256") != implementation_fingerprint():
        raise ValueError("Crypto implementation changed after freezing")
    if frozen.get("experiment") != config.to_dict():
        # JSON tuples become lists, so compare canonical serialization.
        if canonical_json(frozen.get("experiment")) != canonical_json(config.to_dict()):
            raise ValueError("Run settings differ from the frozen comparison")
    final_date = max(pd.Timestamp(w.end) for w in config.windows)
    prices = {symbol: frame.loc[:final_date] for symbol, frame in dataset.prices.items()}
    signal_cache = {}
    rows, paths, coins, ledgers = [], [], [], []
    formations = []
    engine_errors = []

    def signals_for(candidate, symbols):
        result = {}
        for symbol in symbols:
            if symbol not in prices:
                raise ValueError(f"Missing selected price history: {symbol}")
            key = (candidate, symbol)
            if key not in signal_cache:
                signal_cache[key] = candidate_signals(prices[symbol], candidate)
            result[symbol] = signal_cache[key]
        return result

    def simulate(identity, schedule, candidate, cost, *, slots=20, tax=False, target=rows,
                 store_path=True):
        symbols = tuple(dict.fromkeys(symbol for _, picks in schedule for symbol in picks))
        try:
            for window, picks in schedule:
                require_formation_history(prices, picks, window.formation_date, config.min_warmup_bars)
            always = candidate == "same_basket_buy_hold" or candidate == "BTC_buy_hold"
            maps = {} if always else signals_for(candidate, symbols)
            settings = CryptoPortfolioConfig(initial_capital=config.initial_capital, cost_bps=cost,
                                             slot_capacity=slots, rebalance_threshold=config.volatility_rebalance_relative_threshold,
                                             tax_enabled=tax,
                                             tax_rates=TaxRates(short_term=config.short_term_tax_rate,
                                                                long_term=config.long_term_tax_rate))
            start, end = schedule[0][0].start, schedule[-1][0].end
            calendar = pd.date_range(start, end, freq="D")
            result = simulate_portfolio(prices, calendar,
                                        [Rebalance(window.start, picks) for window, picks in schedule],
                                        start, end, signals=maps, config=settings, always_in=always)
            target.append(_row(identity, result))
            if store_path:
                panel = result.path.rename("value").to_frame().reset_index()
                panel.rename(columns={panel.columns[0]: "date"}, inplace=True)
                for key, value in identity.items():
                    panel[key] = value
                paths.append(panel)
                if not result.ledger.empty:
                    ledger = result.ledger.copy()
                    for key, value in identity.items():
                        ledger[key] = value
                    ledgers.append(ledger)
            return result
        except (CryptoPortfolioDataError, ValueError) as exc:
            target.append(_row(identity, error=str(exc)))
            engine_errors.append({**identity, "error": str(exc)})
            return None

    tax_modes = (False, True) if config.run_illustrative_tax else (False,)
    selections = {}
    for window in config.windows:
        for group in config.groups:
            picks = selected_symbols(dataset, window, group, config)
            selections[(window.name, group)] = picks
            formations.append({"window": window.name, "formation_date": window.formation_date,
                               "group": group, "symbols": list(picks), "count": len(picks),
                               "fixed_cash_slots": config.slot_capacity - len(picks)})
            for cost in config.costs_bps_per_side:
                for tax in tax_modes:
                    for candidate in config.candidates + ("same_basket_buy_hold",):
                        identity = {"window": window.name, "start": window.start, "end": window.end,
                                    "group": group, "candidate": candidate, "cost_bps": cost,
                                    "tax_mode": "illustrative_stocklike_FIFO" if tax else "pretax",
                                    "selected_count": len(picks)}
                        simulate(identity, [(window, picks)], candidate, cost, tax=tax)
            if include_attribution:
                for symbol in picks:
                    for candidate in config.candidates + ("same_basket_buy_hold",):
                        identity = {"window": window.name, "start": window.start, "end": window.end,
                                    "group": group, "symbol": symbol, "candidate": candidate,
                                    "cost_bps": config.attribution_cost_bps, "tax_mode": "pretax",
                                    "selected_count": 1}
                        simulate(identity, [(window, (symbol,))], candidate, config.attribution_cost_bps,
                                 slots=1, target=coins, store_path=False)
        # Individual controls and hypotheses do not change the basket selection.
        for symbol in config.diagnostic_symbols:
            for cost in config.costs_bps_per_side:
                for candidate in config.candidates + ("same_basket_buy_hold",):
                    identity = {"window": window.name, "start": window.start, "end": window.end,
                                "group": "single_asset_diagnostic", "symbol": symbol,
                                "candidate": candidate, "cost_bps": cost, "tax_mode": "pretax", "selected_count": 1}
                    simulate(identity, [(window, (symbol,))], candidate, cost, slots=1)
        for cost in config.costs_bps_per_side:
            identity = {"window": window.name, "start": window.start, "end": window.end,
                        "group": "benchmark", "candidate": "BTC_buy_hold", "cost_bps": cost,
                        "tax_mode": "pretax", "selected_count": 1}
            simulate(identity, [(window, ("BTCUSDT",))], "BTC_buy_hold", cost, slots=1)

    # A continuous account retains lots/capital over the 2023 universe change.
    contiguous = all(pd.Timestamp(b.start) == pd.Timestamp(a.end) + pd.Timedelta(days=1)
                     for a, b in zip(config.windows, config.windows[1:]))
    if len(config.windows) > 1 and contiguous:
        for group in config.groups:
            schedule = [(window, selections[(window.name, group)]) for window in config.windows]
            for cost in config.costs_bps_per_side:
                for tax in tax_modes:
                    for candidate in config.candidates + ("same_basket_buy_hold",):
                        identity = {"window": "continuous", "start": config.windows[0].start,
                                    "end": config.windows[-1].end, "group": group, "candidate": candidate,
                                    "cost_bps": cost, "tax_mode": "illustrative_stocklike_FIFO" if tax else "pretax",
                                    "selected_count": max(len(picks) for _, picks in schedule)}
                        simulate(identity, schedule, candidate, cost, tax=tax)
        combined = CryptoWindow("continuous", config.windows[0].formation_date,
                                config.windows[0].start, config.windows[-1].end)
        for cost in config.costs_bps_per_side:
            identity = {"window": "continuous", "start": combined.start, "end": combined.end,
                        "group": "benchmark", "candidate": "BTC_buy_hold", "cost_bps": cost,
                        "tax_mode": "pretax", "selected_count": 1}
            simulate(identity, [(combined, ("BTCUSDT",))], "BTC_buy_hold", cost, slots=1)

    benchmark_windows = list(config.windows)
    if len(config.windows) > 1 and contiguous:
        benchmark_windows.append(CryptoWindow("continuous", config.windows[0].formation_date,
                                             config.windows[0].start, config.windows[-1].end))
    for window in benchmark_windows:
        identity = {"window": window.name, "start": window.start, "end": window.end,
                    "group": "benchmark", "candidate": "SPY_total_return_buy_hold",
                    "cost_bps": config.spy_cost_bps_per_side, "tax_mode": "pretax", "selected_count": 1}
        if benchmark_directory is None:
            rows.append(_row(identity, error="Verified dividend-adjusted SPY benchmark unavailable"))
            continue
        try:
            from crypto_research.benchmark import load_spy_benchmark, spy_buy_and_hold
            frame = load_spy_benchmark(benchmark_directory)
            path = spy_buy_and_hold(frame, window.start, window.end,
                                   cost_bps=config.spy_cost_bps_per_side, initial_capital=config.initial_capital)
            rows.append(_benchmark_row(path, identity, config.initial_capital))
            panel = path.rename("value").to_frame().reset_index()
            panel.rename(columns={panel.columns[0]: "date"}, inplace=True)
            for key, value in identity.items():
                panel[key] = value
            paths.append(panel)
        except ValueError as exc:
            rows.append(_row(identity, error=str(exc)))

    summary = pd.DataFrame(rows)
    coin_results = pd.DataFrame(coins)
    report = {"schema_version": 1, "status": "RESEARCH_ONLY", "deployment_blocked": True,
              "qualified_candidates": [], "created_at": datetime.now(timezone.utc).isoformat(),
              "frozen_sha256": frozen.get("sha256"), "dataset_sha256": frozen.get("dataset_sha256"),
              "implementation_sha256": frozen.get("implementation_sha256"),
              "experiment": config.to_dict(), "formations": formations,
              "sample_status": config.sample_status, "independent_holdout": False,
              "data_metadata": dataset.metadata, "data_quality_flags": list(dataset.quality_flags),
              "comparison_rows": len(summary),
              "identified_rows": int((summary.status == "IDENTIFIED_EXPLORATORY").sum()),
              "unidentified_rows": int((summary.status == "UNIDENTIFIED").sum()),
              "blocking_flags": ["venue_only_historical_universe_not_global_market_cap",
                                 "historically_informed_sample_not_independent_holdout",
                                 "USDT_USD_depeg_and_counterparty_risk_not_modelled",
                                 "generic_cost_scenarios_not_verified_executable_broker_quotes",
                                 "no_actual_taxpayer_tax_approval"],
              "tax_assumption": "Primary pretax; optional stocklike FIFO illustrative sensitivity, not actual crypto tax law or personal liability",
              "paper_adaptations": ["cash-only cap 100% versus paper 200% cap", "next UTC daily open",
                                    "fixed three-year baskets versus paper monthly liquidity formation",
                                    "sample simple return SD sqrt365 and relative 20% volatility rebalance threshold"],
              "metric_policy": "Missing selected economic outcomes retain full candidate rows with null metrics; no stale fills or shortened horizons",
              "trade_statistics_definition": "Completed entry FIFO lots including fees, not independent signal episodes; volatility additions create additional lots",
              "engine_errors": engine_errors, "summary": summary.to_dict(orient="records")}
    return CryptoExperimentResult(summary, pd.concat(paths, ignore_index=True) if paths else pd.DataFrame(),
                                  coin_results, paired_variant_results(coin_results),
                                  pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame(), _json_safe(report))


def save_result(result: CryptoExperimentResult, output: str | Path) -> dict:
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    for name, frame in (("summary.csv", result.summary), ("paths.csv", result.paths),
                        ("coin_results.csv", result.coin_results), ("paired_variants.csv", result.paired_variants),
                        ("trade_ledger.csv", result.trade_ledger)):
        file = root / name
        frame.to_csv(file, index=False)
        artifacts[name] = hashlib.sha256(file.read_bytes()).hexdigest()
    report = dict(result.report, artifacts_sha256=artifacts)
    report["report_sha256"] = sha256(report)
    (root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return report


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "run"):
        command = sub.add_parser(name)
        command.add_argument("--dataset", required=True)
        command.add_argument("--benchmark")
        command.add_argument("--output", required=True)
    sub.choices["freeze"].add_argument("--config", required=True)
    sub.choices["run"].add_argument("--frozen", required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "freeze":
        config = CryptoExperimentConfig.from_dict(json.loads(Path(arguments.config).read_text()))
        payload = freeze_config(config, arguments.dataset, arguments.output, benchmark=arguments.benchmark)
        print(json.dumps({"status": "FROZEN_RESEARCH_FAMILY", "sha256": payload["sha256"]}))
    else:
        config, payload = read_frozen(arguments.frozen, arguments.dataset, benchmark=arguments.benchmark)
        from crypto_research.data import load_bundle
        dataset = load_bundle(arguments.dataset, end=max(w.end for w in config.windows))
        result = run_experiment(dataset, config, frozen=payload, benchmark_directory=arguments.benchmark)
        report = save_result(result, arguments.output)
        print(json.dumps({"status": report["status"], "identified_rows": report["identified_rows"],
                          "unidentified_rows": report["unidentified_rows"], "report_sha256": report["report_sha256"]}))


if __name__ == "__main__":
    main()
