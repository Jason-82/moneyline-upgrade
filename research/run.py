"""Corrected, continuous stock-selection research CLI.

Examples:
    python -m research.run development --dataset private/dataset --mode exploratory --output private/dev
    python -m research.run freeze --config private/candidate.json --dataset private/dataset --output private/frozen.json
    python -m research.run holdout --frozen private/frozen.json --dataset private/dataset --mode validated --output private/holdout

Development never receives prices later than 2022-12-31.  Holdout needs a frozen
choice and claims its one attempt before loading any reserved price rows.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.config import (DEVELOPMENT_END, HOLDOUT_END, HOLDOUT_WINDOW,
                             ExperimentConfig, Window, canonical_json, claim_holdout,
                             finish_holdout, freeze_config, read_frozen, sha256)
from research.selection import (FormationResult, daily_returns, formation_scores,
                                permutation_selection_test, pick, scores_for, window_metrics)


@dataclass
class ExperimentResult:
    summary: pd.DataFrame
    windows: pd.DataFrame
    formations: list[FormationResult]
    paths: pd.DataFrame
    report: dict
    portfolios: dict


def require_full_calendar(calendar, windows, *, holdout=False) -> None:
    """An explicit complete horizon is mandatory; never min(planned_end,last_bar)."""
    from research.calendar import nyse_schedule
    cal = pd.DatetimeIndex(calendar)
    if not len(cal) or cal.has_duplicates or not cal.is_monotonic_increasing:
        raise ValueError("A nonempty, ascending, unique trading calendar is required")
    for window in windows:
        start, end = pd.Timestamp(window.test_start), pd.Timestamp(window.test_end)
        expected = nyse_schedule(start, end).index
        observed = cal[(cal >= start) & (cal <= end)]
        missing = expected.difference(observed)
        if len(missing):
            name = "reserved holdout" if holdout else "declared development window"
            raise ValueError(f"Incomplete {name} {start.date()}--{end.date()}: missing {len(missing)} sessions, "
                             f"including {missing[0].date()}; the window will not be shortened")
        extra = observed.difference(expected)
        if len(extra):
            raise ValueError(f"Invalid supplied calendar: {len(extra)} non-NYSE sessions, including {extra[0].date()}")


def _symbols(dataset) -> dict[str, str]:
    records = getattr(dataset, "securities", {})
    if isinstance(records, dict):
        return {str(key): str(value.symbol if hasattr(value, "symbol") else value.get("symbol", key))
                for key, value in records.items()}
    return {str(r.security_id): str(r.symbol) for r in records}


def _metadata(dataset) -> dict:
    return dict(getattr(dataset, "metadata", {}) or {})


def _metrics(result, initial_capital, start, end):
    # Do not publish a point estimate where the engine explicitly lacks valuation.
    blockers = ("unresolved_terminal", "missing_price", "unavailable_position", "missing_execution", "unknown_terminal", "missing_bar", "unidentified_portfolio", "terminal_liquidation_unavailable")
    identified = bool(np.isfinite(result.mult)) and not any(any(token in flag for token in blockers) for flag in result.flags)
    return {"cagr": result.metrics["cagr"] * 100 if identified else np.nan,
            "max_drawdown": result.metrics["max_drawdown"] * 100 if identified else np.nan,
            "total_return": result.metrics["total_return"] * 100 if identified else np.nan,
            "mult": result.mult if identified else np.nan,
            "identified": identified, "flags": "; ".join(result.flags)}


def _window_values(result, windows, initial_capital):
    output = []
    previous = initial_capital
    identified = _metrics(result, initial_capital, windows[0].test_start, windows[-1].test_end)["identified"]
    for w in windows:
        path = result.path.loc[w.test_start:w.test_end]
        if path.empty:
            raise ValueError("Continuous portfolio omitted a declared window")
        end_value = float(path.iloc[-1]) if identified else np.nan
        multiple = end_value / previous if np.isfinite(previous) and previous > 0 else np.nan
        years = max((pd.Timestamp(w.test_end) - pd.Timestamp(w.test_start)).days / 365.25, 1 / 365.25)
        value = np.r_[previous, path.to_numpy(float)] if identified else np.full(len(path) + 1, np.nan)
        drawdown = float(np.min(value / np.maximum.accumulate(value)) - 1) * 100
        output.append({"start": w.test_start, "end": w.test_end,
                       "start_value": previous if identified else np.nan, "end_value": end_value, "multiple": multiple,
                       "cagr": ((multiple ** (1 / years) - 1) * 100 if multiple > 0 else -100.0) if np.isfinite(multiple) else np.nan,
                       "max_drawdown": drawdown})
        previous = end_value
    return output


def run_experiment(dataset, config: ExperimentConfig | None = None, *, holdout=False,
                   benchmark_id: str | None = None, cash_daily_returns: pd.Series | None = None,
                   validate=True) -> ExperimentResult:
    """Run all declared choices over identical continuous horizons and cash windows.

    Same-selected-stock holding follows the *same reselection schedule*. SPY buys
    only once across the entire horizon; it does not reset tax basis every split.
    The all-stock strategy uses the causal eligible universe, not future survivors.
    """
    from research.portfolio import PortfolioConfig, PortfolioDataError, PortfolioResult, Rebalance, simulate_portfolio
    from research.tax import TaxRates
    config = config or ExperimentConfig()
    config.validate()
    windows = (HOLDOUT_WINDOW,) if holdout else config.development_windows
    if holdout and config.chosen_level is None:
        raise ValueError("Holdout requires a choice frozen before loading reserved prices")
    cutoff = pd.Timestamp(HOLDOUT_END if holdout else DEVELOPMENT_END)
    prices = {sid: frame.loc[:cutoff] for sid, frame in dataset.prices.items()}
    calendar = pd.DatetimeIndex(dataset.calendar)
    calendar = calendar[calendar <= cutoff]
    require_full_calendar(calendar, windows, holdout=holdout)
    # Direct callers may supply a wider dataset; validation and provenance for a
    # development run must still be limited to its own causal cutoff.
    dataset = replace(dataset, prices=prices, calendar=calendar,
                      dividends={sid: ser.loc[:cutoff] for sid, ser in dataset.dividends.items()},
                      terminal_events=tuple(e for e in dataset.terminal_events if pd.Timestamp(e.date) <= cutoff),
                      metadata=_metadata(dataset))
    if validate:
        from research.data_contract import validate_dataset
        # Validator's mode is carried by dataset, and exploratory mode cannot
        # assert that absent delisting data suddenly became trustworthy.
        validate_dataset(dataset, start=windows[0].test_start, end=windows[-1].test_end)
    metadata = _metadata(dataset)
    symbols = _symbols(dataset)
    if benchmark_id is None:
        benchmark_id = next((sid for sid, symbol in symbols.items() if symbol == "SPY"), None)
        if benchmark_id is None and "SPY" in prices:
            benchmark_id = "SPY"
    if benchmark_id not in prices:
        raise ValueError("SPY actual OHLC is required across the declared comparison horizon")
    # SPY must have every supplied test session; an empty benchmark is not cash.
    benchmark_sessions = calendar[(calendar >= pd.Timestamp(windows[0].test_start)) & (calendar <= pd.Timestamp(windows[-1].test_end))]
    if len(benchmark_sessions.difference(prices[benchmark_id].index)):
        raise ValueError("SPY is missing actual OHLC on required benchmark sessions")
    dividends = getattr(dataset, "dividends", {})
    events = getattr(dataset, "terminal_events", ())
    members = getattr(dataset, "membership", None)
    if members is None:
        members = getattr(dataset, "memberships", None)
    price_basis = metadata.get("price_basis", "unknown")
    tax_identified = config.tax_enabled and price_basis == "split_only" and metadata.get("dividends_complete", False)
    # A tax estimate on total-return-adjusted data would double count dividends
    # or manufacture their classification; it is intentionally unavailable.
    tax_enabled = bool(tax_identified)
    formations = [formation_scores(prices, members, w, config, calendar=calendar,
                                   dividends=dividends if price_basis == "split_only" else {},
                                   symbols=symbols, price_basis=price_basis) for w in windows]
    if not holdout:
        outcomes = []
        outcome_coverage = []
        return_cache = {}
        for f in formations:
            out = {}
            expected = calendar[(calendar >= pd.Timestamp(f.window.test_start)) &
                                (calendar <= pd.Timestamp(f.window.test_end))]
            for sid in f.metrics.index:
                # No terminal payout is inferred from the last quote. This
                # diagnostic currently requires full actual test-window OHLC;
                # known terminal events are correctly accounted by the portfolio
                # engine but do not create an invented timing-skill outcome here.
                if len(expected.difference(prices[sid].index)):
                    out[sid] = np.nan
                    continue
                if sid not in return_cache:
                    return_cache[sid] = daily_returns(prices[sid], config.cost_bps_per_side / 10000,
                                                     dividends.get(sid) if price_basis == "split_only" else None)
                returns = return_cache[sid]
                metric = window_metrics(returns, f.window.test_start, f.window.test_end, test=True, calendar=calendar)
                out[sid] = metric["skill"] if metric is not None else np.nan
            outcomes.append(pd.Series(out, dtype=float))
            outcome_coverage.append({"test_start": f.window.test_start, "test_end": f.window.test_end,
                                     "formation_eligible": len(f.metrics),
                                     "identified_timing_outcomes": sum(np.isfinite(v) for v in out.values()),
                                     "unknown_timing_outcomes": sum(not np.isfinite(v) for v in out.values())})
        pvalues = permutation_selection_test(formations, outcomes, config)
    else:
        pvalues = {}  # one frozen hypothesis; no post-hoc family search on holdout
        outcome_coverage = []
    rates = TaxRates(short_term=config.short_term_tax_rate, long_term=config.long_term_tax_rate,
                     ordinary=config.short_term_tax_rate, qualified_dividend=config.long_term_tax_rate)
    engine_base = dict(initial_capital=config.initial_capital, cost_bps=config.cost_bps_per_side,
                       strict=bool(metadata.get("validated", False)), price_mode=price_basis,
                       tax_rates=rates, cash_daily_returns=cash_daily_returns,
                       qualified_dividend_fraction=config.qualified_dividend_fraction,
                       dividend_reinvestment=config.dividend_reinvestment)
    from analysis_2026.moneyline_ref import moneyline
    signal_ids = set().union(*(set(f.metrics.index) for f in formations)) | {benchmark_id}
    signals = {sid: moneyline(prices[sid]).green for sid in signal_ids}
    common = dict(prices=prices, calendar=calendar, start=windows[0].test_start, end=windows[-1].test_end,
                  dividends=dividends if price_basis == "split_only" else {}, terminal_events=events,
                  metadata=metadata, signals=signals)
    def simulate(**kwargs):
        try:
            return simulate_portfolio(**kwargs)
        except PortfolioDataError as exc:
            if metadata.get("validated", False):
                raise
            # Keep the planned comparison row and horizon. An unavailable sale
            # cannot turn into cash at a guessed price or erase a failing window.
            days = calendar[(calendar >= pd.Timestamp(windows[0].test_start)) &
                            (calendar <= pd.Timestamp(windows[-1].test_end))]
            flags = ("unidentified_portfolio: " + str(exc),)
            metrics = {"cagr": np.nan, "max_drawdown": np.nan, "total_return": np.nan,
                       "final_value": np.nan, "years": np.nan}
            return PortfolioResult(pd.Series(np.nan, index=days), np.nan, metrics,
                                   pd.DataFrame(), pd.DataFrame(), flags, True, (0.0, 0.0),
                                   pd.DataFrame(), {}, flags)
    first_date = windows[0].test_start
    spy_schedule = [Rebalance(first_date, (benchmark_id,))]
    spy_pre = simulate(**common, schedule=spy_schedule, always_in=True,
                                 config=PortfolioConfig(**engine_base, tax_enabled=False))
    spy_tax = simulate(**common, schedule=spy_schedule, always_in=True,
                                 config=PortfolioConfig(**engine_base, tax_enabled=tax_enabled))
    all_schedule = [Rebalance(f.window.test_start, tuple(f.metrics.index)) for f in formations]
    all_pre = simulate(**common, schedule=all_schedule,
                                 config=PortfolioConfig(**engine_base, tax_enabled=False))
    all_tax = simulate(**common, schedule=all_schedule,
                                 config=PortfolioConfig(**engine_base, tax_enabled=tax_enabled))
    pairs = [(config.chosen_criterion, config.chosen_level)] if holdout else [(c, l) for c in config.criteria for l in config.levels]
    portfolios = {"spy_pre": spy_pre, "spy_tax": spy_tax, "all_strategy_pre": all_pre, "all_strategy_tax": all_tax}
    summary, window_rows = [], []
    spy_pre_metric = _metrics(spy_pre, config.initial_capital, first_date, windows[-1].test_end)
    spy_tax_metric = _metrics(spy_tax, config.initial_capital, first_date, windows[-1].test_end)
    all_pre_metric = _metrics(all_pre, config.initial_capital, first_date, windows[-1].test_end)
    all_tax_metric = _metrics(all_tax, config.initial_capital, first_date, windows[-1].test_end)
    spy_window_values = _window_values(spy_tax, windows, config.initial_capital)
    for criterion, level in pairs:
        pick_lists = [pick(scores_for(f.metrics, criterion, config.random_seed + i), level) for i, f in enumerate(formations)]
        schedule = [Rebalance(f.window.test_start, tuple(picks)) for f, picks in zip(formations, pick_lists)]
        if level == "all":
            pre, post = all_pre, all_tax
        else:
            pre = simulate(**common, schedule=schedule,
                                     config=PortfolioConfig(**engine_base, tax_enabled=False))
            post = simulate(**common, schedule=schedule,
                                      config=PortfolioConfig(**engine_base, tax_enabled=tax_enabled))
        same_pre = simulate(**common, schedule=schedule, always_in=True,
                                      config=PortfolioConfig(**engine_base, tax_enabled=False))
        same_tax = simulate(**common, schedule=schedule, always_in=True,
                                      config=PortfolioConfig(**engine_base, tax_enabled=tax_enabled))
        name = f"{criterion}/{level}"
        portfolios.update({name + "/pre": pre, name + "/tax": post,
                           name + "/same_picks_pre": same_pre, name + "/same_picks_tax": same_tax})
        pm, tm = _metrics(pre, config.initial_capital, first_date, windows[-1].test_end), _metrics(post, config.initial_capital, first_date, windows[-1].test_end)
        bm = _metrics(same_tax, config.initial_capital, first_date, windows[-1].test_end)
        bp = _metrics(same_pre, config.initial_capital, first_date, windows[-1].test_end)
        p = pvalues.get((criterion, level), {})
        flags = sorted(set(pre.flags + post.flags + same_pre.flags + same_tax.flags + spy_pre.flags + spy_tax.flags))
        row = {"criterion": criterion, "level": level, "windows": len(windows),
               "avg_n": float(np.mean([len(p) for p in pick_lists])), "min_n": min(map(len, pick_lists)),
               "empty_windows": sum(not p for p in pick_lists), "cagr_pre": pm["cagr"],
               "cagr_tax": tm["cagr"] if tax_identified else np.nan,
               "spy_pre": spy_pre_metric["cagr"], "spy_tax": spy_tax_metric["cagr"] if tax_identified else np.nan,
               "same_picks_bh_pre": bp["cagr"], "same_picks_bh_tax": bm["cagr"] if tax_identified else np.nan,
               "all_strategy_pre": all_pre_metric["cagr"], "all_strategy_tax": all_tax_metric["cagr"] if tax_identified else np.nan,
               "max_drawdown_pre": pm["max_drawdown"], "spy_max_drawdown_pre": spy_pre_metric["max_drawdown"],
               "max_drawdown_tax": tm["max_drawdown"] if tax_identified else np.nan,
               "spy_max_drawdown_tax": spy_tax_metric["max_drawdown"] if tax_identified else np.nan,
               "p_selection_raw": p.get("p_raw", np.nan), "p_selection_holm": p.get("p_holm", np.nan),
               "tax_identified": bool(tax_identified), "portfolio_identified": pm["identified"] and tm["identified"],
               "deployment_blocked": bool(pre.deployment_blocked or post.deployment_blocked or not tax_identified),
               "flags": "; ".join(flags)}
        values = _window_values(post, windows, config.initial_capital)
        pretax_values = _window_values(pre, windows, config.initial_capital)
        successes = 0
        for i, (w, value, spy_value) in enumerate(zip(windows, values, spy_window_values)):
            passes = (value["cagr"] >= spy_value["cagr"] or
                      (value["cagr"] >= spy_value["cagr"] - config.qualifying_cagr_tolerance_pp and
                       value["max_drawdown"] >= spy_value["max_drawdown"] + config.qualifying_drawdown_improvement_pp))
            successes += bool(passes)
            window_rows.append({"criterion": criterion, "level": level, "formation_start": w.formation_start,
                                "formation_end": w.formation_end, **value, "n": len(pick_lists[i]),
                                "eligible": len(formations[i].metrics), "picks": " ".join(pick_lists[i]),
                                "spy_cagr": spy_value["cagr"], "spy_max_drawdown": spy_value["max_drawdown"],
                                "tax_identified": bool(tax_identified), "cagr_pre": pretax_values[i]["cagr"],
                                "cagr_tax": value["cagr"] if tax_identified else np.nan,
                                "window_comparison_pass": bool(passes) if tax_identified else False})
        row["windows_beating_spy"] = f"{successes}/{len(windows)}" if tax_identified else "unidentified"
        sufficient_return = tax_identified and (row["cagr_tax"] >= row["spy_tax"] or
                            (row["cagr_tax"] >= row["spy_tax"] - config.qualifying_cagr_tolerance_pp and
                             row["max_drawdown_tax"] >= row["spy_max_drawdown_tax"] + config.qualifying_drawdown_improvement_pp))
        # Even a corrected selection p-value is not proof of profitability. PASS
        # remains unavailable until a frozen holdout and forward validation exist.
        row["development_candidate"] = bool(not holdout and not row["deployment_blocked"] and sufficient_return and
                                           successes / len(windows) >= config.qualifying_window_fraction and
                                           (level == "all" or row["p_selection_holm"] < 0.05))
        row["status"] = "RESEARCH_ONLY" if row["portfolio_identified"] else "UNIDENTIFIED"
        summary.append(row)
    summary_df = pd.DataFrame(summary)
    candidates = summary_df[summary_df.development_candidate] if len(summary_df) else summary_df
    recommendation = None
    if not candidates.empty:
        best = candidates.cagr_tax.max()
        near_best = candidates[candidates.cagr_tax >= best - config.choice_within_best_pp]
        # Avg breadth, rather than spelling of the threshold, defines loosest.
        chosen = near_best.sort_values(["avg_n", "level"], ascending=[False, True], kind="stable").iloc[0]
        recommendation = {"criterion": chosen.criterion, "level": chosen.level, "role": "development_candidate"}
    report = {"schema_version": 2, "status": "RESEARCH_ONLY", "holdout": bool(holdout),
              "experiment": config.to_dict(), "experiment_sha256": sha256(config.to_dict()),
              "horizon": {"start": first_date, "end": windows[-1].test_end},
              "dataset_metadata": metadata, "tax_identified": bool(tax_identified),
              "selection_inference": "Conditional timing-skill persistence only; not a portfolio profitability p-value",
              "cash_policy": config.cash_rate_policy,
              "cash_rates_provided": cash_daily_returns is not None,
              "development_recommendation": recommendation,
              "limitations": ["Tax rates/classification assumptions are illustrative",
                              "No forward shadow validation has been completed",
                              "A hindsight-selected rule cannot qualify from development alone"],
              "formation_flags": sorted(set(flag for f in formations for flag in f.flags)),
              "formation_coverage": [{"formation_end": f.window.formation_end,
                                      "eligible": len(f.metrics), "excluded": len(f.excluded),
                                      "warmup_exclusions": sum("warmup" in reason for reason in f.excluded.values()),
                                      "empty_universe_cash_window": f.metrics.empty} for f in formations],
              "legacy_outputs": "superseded_by_corrected_continuous_research",
              "permutation_family_size": len([1 for c in config.criteria for l in config.levels if l != "all"])}
    report["timing_outcome_coverage"] = outcome_coverage
    paths = pd.DataFrame({name: result.path if _metrics(result, config.initial_capital, first_date, windows[-1].test_end)["identified"]
                         else pd.Series(np.nan, index=result.path.index) for name, result in portfolios.items()})
    return ExperimentResult(summary_df, pd.DataFrame(window_rows), formations, paths, report, portfolios)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    return value


def write_result(result: ExperimentResult, output: str | Path) -> str:
    p = Path(output)
    p.mkdir(parents=True, exist_ok=True)
    result.summary.to_csv(p / "summary.csv", index=False)
    result.windows.to_csv(p / "windows.csv", index=False)
    result.paths.to_csv(p / "paths.csv", index_label="date")
    formation_frames = []
    exclusions = []
    for f in result.formations:
        frame = f.metrics.reset_index()
        frame["formation_end"] = f.window.formation_end
        formation_frames.append(frame)
        exclusions.extend({"formation_end": f.window.formation_end, "security_id": sid, "reason": reason}
                          for sid, reason in f.excluded.items())
    pd.concat(formation_frames, ignore_index=True).to_csv(p / "formation_scores.csv", index=False)
    pd.DataFrame(exclusions).to_csv(p / "formation_exclusions.csv", index=False)
    report = _json_safe({**result.report, "summary": result.summary.to_dict("records")})
    report_hash = sha256(report)
    report["sha256"] = report_hash
    (p / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for name, portfolio in result.portfolios.items():
        safe_name = name.replace("/", "_").replace(">", "gt")
        portfolio.ledger.to_csv(p / f"{safe_name}_ledger.csv", index=False)
        portfolio.tax_records.to_csv(p / f"{safe_name}_tax.csv", index=False)
    return report_hash


def manifest_fingerprint(folder: str | Path) -> str:
    """Fingerprint provenance without reading reserved price values."""
    root = Path(folder)
    path = root / "manifest.json"
    if path.exists():
        return sha256(json.loads(path.read_text()))
    # Legacy exploratory folders have no durable provenance. Structural identity
    # prevents accidental source substitution but is not data-integrity proof.
    return sha256({"legacy_path": str(root.resolve()),
                   "files": sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())})


def _load_config(path):
    return ExperimentConfig.from_dict(json.loads(Path(path).read_text())) if path else ExperimentConfig()


def load_cash_rates(path, config: ExperimentConfig, cutoff: str) -> pd.Series | None:
    if not path:
        if config.cash_rates_sha256 is not None:
            raise ValueError("Frozen experiment requires its observed cash-rate file")
        return None
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if config.cash_rates_sha256 != digest:
        raise ValueError("Cash-rate file does not match the hash in the declared experiment")
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    if "daily_return" not in frame:
        raise ValueError("Cash-rate CSV needs date,daily_return; do not infer returns from annual averages")
    returns = frame.daily_return.astype(float).loc[:cutoff]
    if returns.index.has_duplicates or not np.isfinite(returns).all() or (returns < -1).any():
        raise ValueError("Invalid observed daily cash returns")
    return returns.sort_index()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = ap.add_subparsers(dest="command", required=True)
    dev = commands.add_parser("development")
    dev.add_argument("--dataset", required=True)
    dev.add_argument("--mode", choices=["validated", "exploratory", "legacy_qlib"], default="validated")
    dev.add_argument("--config")
    dev.add_argument("--cash-rates")
    dev.add_argument("--output", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--config", required=True)
    freeze.add_argument("--dataset", required=True)
    freeze.add_argument("--development-report")
    freeze.add_argument("--output", required=True)
    hold = commands.add_parser("holdout")
    hold.add_argument("--frozen", required=True)
    hold.add_argument("--dataset", required=True)
    hold.add_argument("--mode", choices=["validated", "exploratory", "legacy_qlib"], default="validated")
    hold.add_argument("--cash-rates")
    hold.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    if args.command == "freeze":
        config = _load_config(args.config)
        report_hash = None
        if args.development_report:
            report = json.loads(Path(args.development_report).read_text())
            report_hash = report.get("sha256")
            if report_hash != sha256({k: v for k, v in report.items() if k != "sha256"}):
                raise ValueError("Development report hash does not match")
        frozen = freeze_config(config, args.output, dataset_manifest_sha256=manifest_fingerprint(args.dataset),
                               development_report_sha256=report_hash)
        print(f"Frozen experiment {frozen['sha256']} -> {args.output}")
        return
    marker = None
    if args.command == "holdout":
        config, frozen = read_frozen(args.frozen)
        if frozen["dataset_manifest_sha256"] != manifest_fingerprint(args.dataset):
            raise ValueError("Dataset provenance changed after freezing; holdout will not be read")
        marker = claim_holdout(args.frozen, frozen)
        cutoff = HOLDOUT_END
    else:
        config, cutoff = _load_config(args.config), DEVELOPMENT_END
    try:
        from research.data_contract import load_dataset
        dataset = load_dataset(args.dataset, mode=args.mode, cutoff=cutoff)
        cash = load_cash_rates(args.cash_rates, config, cutoff)
        result = run_experiment(dataset, config, holdout=args.command == "holdout", cash_daily_returns=cash)
        report_hash = write_result(result, args.output)
        if marker:
            finish_holdout(marker, status="completed", report_sha256=report_hash)
        display = ["criterion", "level", "avg_n", "empty_windows", "cagr_pre", "cagr_tax", "spy_pre", "spy_tax", "same_picks_bh_pre", "all_strategy_pre", "status"]
        print(result.summary[display].to_string(index=False))
        print(f"RESEARCH_ONLY | full horizon {result.report['horizon']} | report {report_hash}")
    except Exception as exc:
        if marker:
            finish_holdout(marker, status="failed", error=str(exc))
        raise


if __name__ == "__main__":
    main()
