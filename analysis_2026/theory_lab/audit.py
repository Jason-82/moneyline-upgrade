"""Independent fixed-rule research audit; no broker or production dependencies.

This module intentionally does not import the execution engine or schedule code.
The fee budget uses an analytic piecewise solution, rather than their iterative
solver. It supports the common complete calendars used by C3-C5, not arbitrary
staggered calendars or missing-data diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def analytical_budget(equity, current, weights, fee):
    """Find post-cost NAV by enumerating the buy/sell breakpoints."""
    current, weights = np.asarray(current, float), np.asarray(weights, float)
    if current.shape != weights.shape or np.any(current < 0) or np.any(weights < 0):
        raise ValueError("Invalid current values or weights")
    if weights.sum() > 1 + 1e-12 or not 0 <= fee < 1 or equity < 0:
        raise ValueError("Invalid equity, fee, or leveraged targets")
    thresholds = current[weights > 0] / weights[weights > 0]
    boundaries = np.unique(np.r_[0., thresholds[(thresholds > 0) & (thresholds < equity)], equity])
    for low, high in zip(boundaries[:-1], boundaries[1:]):
        probe = (low + high) / 2
        buy = probe * weights >= current
        signs = np.where(buy, 1., -1.)
        candidate = (equity + fee * np.sum(signs * current)) / (1 + fee * np.sum(signs * weights))
        if low - 1e-9 <= candidate <= high + 1e-9:
            residual = candidate + fee * np.abs(candidate * weights - current).sum() - equity
            if abs(residual) > max(1., equity) * 1e-10:
                raise AssertionError("Analytic fee root fails accounting identity")
            return float(candidate)
    if equity == 0:
        return 0.
    raise AssertionError("No self-financing root")


def rebuild_path(prices, schedule, start, end, fee=0., delay=1, cash_rate=0., capital=100_000.):
    """Independently reconstruct all daily NAVs from completed-close targets."""
    names = list(prices)
    calendar = prices[names[0]].index
    for name in names:
        if not prices[name].index.equals(calendar):
            raise ValueError("Audit requires identical complete calendars")
        values = prices[name][["open", "close"]].to_numpy(float)
        if not np.isfinite(values).all() or np.any(values <= 0):
            raise ValueError("Audit requires positive finite OHLC")
    mask = (calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))
    op_matrix = np.column_stack([prices[name]["open"].to_numpy(float) for name in names])[mask]
    cl_matrix = np.column_stack([prices[name]["close"].to_numpy(float) for name in names])[mask]
    calendar = calendar[mask]
    all_days = prices[names[0]].index
    orders = {}
    for signal, targets in schedule[names].iterrows():
        at = all_days.searchsorted(signal, side="right") + delay - 1
        if at < len(all_days) and calendar[0] <= all_days[at] <= calendar[-1]:
            orders[all_days[at]] = targets.to_numpy(float)
    quantity = np.zeros(len(names))
    cash = float(capital)
    history = []
    previous = calendar[0]
    for position, day in enumerate(calendar):
        cash *= (1 + cash_rate) ** ((day - previous).days / 365.25)
        previous = day
        op = op_matrix[position]
        cl = cl_matrix[position]
        if day in orders:
            current = quantity * op
            weights = orders[day]
            budget = analytical_budget(cash + current.sum(), current, weights, fee)
            target = budget * weights
            delta = target - current
            cash -= delta.sum() + np.abs(delta).sum() * fee
            quantity = target / op
            if abs(cash) < capital * 1e-11:
                cash = 0.
            if cash < 0:
                raise AssertionError("Unfinanced audit allocation")
        if day == calendar[-1]:
            cash += np.sum(quantity * cl) * (1 - fee)
            quantity[:] = 0.
        history.append((day, cash + np.sum(quantity * cl)))
    return pd.Series(dict(history), name="equity")


def independent_month_ends(calendar):
    dates = pd.DatetimeIndex(calendar)
    result = []
    for before, after in zip(dates[:-1], dates[1:]):
        if before.month != after.month or before.year != after.year:
            result.append(before)
    return result


def reconstruct_global(close, slots=3):
    rows = []
    for day in independent_month_ends(close.index):
        at = close.index.get_loc(day)
        if at < 252:
            continue
        values = {}
        for name in close.columns:
            values[name] = sum(close.at[day, name] / close.iloc[at - lag][name] - 1 for lag in (21, 63, 126, 252)) / 4
        if not np.isfinite(list(values.values())).all():
            continue
        ranked = sorted(close.columns, key=lambda name: -values[name])
        chosen = [name for name in ranked if values[name] > 0][:slots]
        rows.append(pd.Series({name: 1 / slots if name in chosen else 0. for name in close.columns}, name=day))
    return pd.DataFrame(rows, columns=close.columns)


def reconstruct_diversified(close, equity_weight=.5):
    days = [day for day in independent_month_ends(close.index) if day.month in (3, 6, 9, 12)]
    return pd.DataFrame(np.tile([equity_weight, 1 - equity_weight], (len(days), 1)), index=days, columns=close.columns)


def reconstruct_leadership(close, horizon=63, threshold=.05):
    incumbent = None
    rows = []
    for day in independent_month_ends(close.index):
        at = close.index.get_loc(day)
        if at < max(90, horizon):
            continue
        ranks = {name: close.at[day, name] / close.iloc[at - horizon][name] - 1 for name in close.columns}
        allowed = [name for name in close.columns if close.at[day, name] > close.iloc[at - 90][name]]
        if not allowed:
            incumbent = None
        else:
            best = max(allowed, key=lambda name: ranks[name])
            if incumbent not in allowed or ranks[best] - ranks[incumbent] > threshold:
                incumbent = best
        rows.append(pd.Series({name: float(name == incumbent) for name in close.columns}, name=day))
    return pd.DataFrame(rows, columns=close.columns)


def paired_monthly_log_returns(strategy, passive, initial=100_000.):
    """Shared completed months, including the first month from initial capital."""
    if not strategy.index.equals(passive.index):
        raise ValueError("Comparison must share every valuation date")
    both = pd.concat([strategy.rename("strategy"), passive.rename("passive")], axis=1)
    ends = both.groupby(both.index.to_period("M")).last()
    previous = ends.shift(1)
    previous.iloc[0] = initial
    return np.log(ends / previous).strategy - np.log(ends / previous).passive


def _load(folder, name, crypto=False):
    path = Path(folder) / f"{name}{'USDT' if crypto else ''}.csv"
    frame = pd.read_csv(path)
    frame.columns = frame.columns.str.lower()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()


def _common(prices):
    dates = prices[next(iter(prices))].index
    for frame in prices.values():
        dates = dates.intersection(frame.index)
    return {name: frame.loc[dates] for name, frame in prices.items()}


def audit_results(etf_folder, crypto_folder, public_output, private_output):
    """Audit every identified saved run, retaining a compact public receipt."""
    public_output, private_output = Path(public_output), Path(private_output)
    global_names = ["SPY", "IWM", "EFA", "EEM", "VNQ", "GLD", "IEF", "TLT"]
    families = {
        "C3": _common({name: _load(etf_folder, name) for name in global_names}),
        "C4": _common({name: _load(etf_folder, name) for name in ["SSO", "GLD", "SPY"]}),
        "C5": _common({name: _load(crypto_folder, name, True) for name in ["BTC", "ETH"]}),
    }
    schedule_checks = []
    for family, data in families.items():
        close = pd.DataFrame({name: frame.close for name, frame in data.items()})
        if family == "C3":
            expected = {"C3_global": reconstruct_global(close), "global_top2": reconstruct_global(close, 2),
                        "global_top4": reconstruct_global(close, 4),
                        "global_equal": pd.DataFrame(1 / len(close.columns), index=independent_month_ends(close.index), columns=close.columns)}
        elif family == "C4":
            expected = {}
            for policy, weight, name in [("C4_sso_gold", .5, "SSO"), ("sso_gold40", .4, "SSO"),
                                         ("sso_gold60", .6, "SSO"), ("spy_gold50", .5, "SPY")]:
                expected[policy] = reconstruct_diversified(close[[name, "GLD"]], weight).reindex(columns=close.columns, fill_value=0.)
        else:
            expected = {"C5_crypto": reconstruct_leadership(close), "crypto_rank42": reconstruct_leadership(close, 42),
                        "crypto_rank84": reconstruct_leadership(close, 84),
                        "crypto_equal": pd.DataFrame(.5, index=independent_month_ends(close.index), columns=close.columns)}
        for policy, independent in expected.items():
            saved = pd.read_csv(public_output / "schedules" / f"{policy}.csv", parse_dates=["signal_date"]).set_index("signal_date")
            pd.testing.assert_frame_equal(saved, independent, check_freq=False, check_names=False,
                                          check_dtype=False, atol=1e-14, rtol=0.)
            schedule_checks.append({"family": family, "policy": policy, "rows": len(saved), "matches_independent_rule": True})
    frame = pd.read_csv(public_output / "metrics.csv")
    path_checks = []
    for row in frame.itertuples(index=False):
        if row.status != "identified":
            continue
        saved = pd.read_csv(private_output / "paths" / f"{row.run_id}.csv", parse_dates=["date"]).set_index("date").equity
        if row.policy == "moneyline_slots":
            # This control's long-established Moneyline signals are not new theory
            # candidates. Independently replay each saved trade at source quotes.
            trades = pd.read_csv(private_output / "transactions" / f"{row.run_id}.csv", parse_dates=["date"])
            quantity = {name: 0. for name in families[row.family]}
            cash = float(row.initial_capital)
            previous = saved.index[0]
            values = []
            by_date = {day: group for day, group in trades.groupby("date", sort=False)}
            for day in saved.index:
                cash *= (1 + row.cash_rate) ** ((day - previous).days / 365.25)
                previous = day
                for trade in by_date.get(day, pd.DataFrame()).itertuples(index=False):
                    source_field = "close" if trade.reason == "terminal_liquidation" else "open"
                    source_quote = families[row.family][trade.symbol].at[day, source_field]
                    if not np.isclose(trade.price, source_quote, rtol=1e-12, atol=1e-10):
                        raise AssertionError("Saved control trade quote differs from actual source")
                    if not np.isclose(trade.fee, trade.quantity * source_quote * row.fee, rtol=1e-12, atol=1e-10):
                        raise AssertionError("Saved control fee differs from actual notional")
                    direction = 1 if trade.side == "buy" else -1
                    quantity[trade.symbol] += direction * trade.quantity
                    cash -= direction * trade.quantity * source_quote + trade.fee
                values.append(cash + sum(q * families[row.family][name].at[day, "close"] for name, q in quantity.items()))
            rebuilt = pd.Series(values, index=saved.index)
            method = "independent_replay_of_saved_control_trades"
        else:
            schedule = pd.read_csv(private_output / "schedules" / f"{row.run_id}.csv", parse_dates=["signal_date"]).set_index("signal_date")
            rebuilt = rebuild_path(families[row.family], schedule, row.start, row.end, row.fee, row.lag, row.cash_rate, row.initial_capital)
            method = "independent_analytic_budget_and_share_cash_ledger"
        if not saved.index.equals(rebuilt.index):
            raise AssertionError(f"Audit dates differ: {row.run_id}")
        relative = np.max(np.abs(saved.to_numpy() - rebuilt.to_numpy()) / np.maximum(saved.to_numpy(), 1.))
        if relative > 1e-10:
            raise AssertionError(f"Independent wealth differs {row.run_id}: {relative}")
        path_checks.append({"run_id": row.run_id, "family": row.family, "policy": row.policy, "window": row.window,
                            "dates": len(saved), "max_relative_wealth_error": float(relative), "method": method})
    receipt = {"scope": "Independent C3-C5 candidate signal reconstruction and all identified pretax saved paths; not a brokerage or raw-vendor accuracy audit",
               "audit_implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "metrics_sha256": hashlib.sha256((public_output / "metrics.csv").read_bytes()).hexdigest(),
               "schedule_checks": schedule_checks, "path_checks": path_checks,
               "identified_paths_audited": len(path_checks), "maximum_relative_wealth_error": max((r["max_relative_wealth_error"] for r in path_checks), default=0.),
               "production_engine_imported": False, "production_schedules_imported": False}
    (public_output / "independent_audit.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def audit_stock_signal(stock_folder, public_output, signal_date="2025-08-29"):
    """Rebuild a real C1/C2 cross section independently, including eligibility.

    A QR regression differs from the production least-squares implementation.
    This verifies a signal; it does not repair missing execution observations or
    establish a complete survivorship-free universe.
    """
    root = Path(stock_folder)
    signal = pd.Timestamp(signal_date)
    period = signal.to_period("M")
    price_path = root / "prices.parquet"
    membership_path = root / "raw/membership_intervals.parquet"
    factor_path = root / "ff3_monthly.csv"
    spy_path = root / "total_return/SPY.csv"
    data = pd.read_parquet(price_path, columns=["date", "ticker", "open", "close", "adj_close", "source"])
    data.loc[(data.close <= 0) | (data.adj_close <= 0), ["open", "close", "adj_close"]] = np.nan
    data["tr_open"] = data.open * data.adj_close / data.close
    data.loc[data.source.str.lower().eq("crsp"), "tr_open"] = np.nan
    close = data.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    op = data.pivot(index="date", columns="ticker", values="tr_open").sort_index()
    spy = pd.read_csv(spy_path, parse_dates=["date"]).set_index("date")
    calendar = spy.index[(spy.index >= close.index.min()) & (spy.index <= close.index.max())]
    close, op = close.reindex(calendar), op.reindex(calendar)
    members = pd.read_parquet(membership_path)
    members.start, members.end = pd.to_datetime(members.start), pd.to_datetime(members.end)
    active = set(members.loc[(members.start <= signal) & (members.end.isna() | (signal < members.end)), "ticker"]) - {"STI"}
    periods = calendar.to_period("M")
    month_days = pd.Series(calendar, index=periods).groupby(level=0).last()
    monthly = close.loc[month_days.values].set_axis(month_days.index)
    fit = pd.period_range(period - 36, period - 1, freq="M")
    boundary = pd.period_range(period - 37, period - 1, freq="M")
    formation = pd.period_range(period - 12, period - 2, freq="M")
    formation_days = calendar[(periods >= formation[0]) & (periods <= formation[-1])]
    candidates = sorted(active & set(close.columns))
    boundaries = monthly.reindex(boundary)[candidates]
    daily_returns = close.pct_change(fill_method=None).loc[formation_days, candidates]
    valid = (boundaries.notna().all() & (boundaries > 0).all() & daily_returns.notna().all()
             & op.loc[formation_days, candidates].notna().all())
    names = valid.index[valid].tolist()
    factors = pd.read_csv(factor_path, parse_dates=["date"]).set_index("date")
    factors.index = factors.index.to_period("M")
    ff = factors.loc[fit, ["Mkt-RF", "SMB", "HML", "RF"]]
    excess = monthly.loc[fit, names] / monthly.shift().loc[fit, names] - 1 - ff.RF.to_numpy()[:, None]
    design = np.column_stack([np.ones(36), ff[["Mkt-RF", "SMB", "HML"]].values])
    q, r = np.linalg.qr(design)
    coefficients = np.linalg.solve(r, q.T @ excess.values)
    positions = fit.get_indexer(formation)
    adjusted = excess.values[positions] - ff[["Mkt-RF", "SMB", "HML"]].values[positions] @ coefficients[1:]
    residual = adjusted.sum(axis=0) / adjusted.std(axis=0, ddof=1)
    raw = monthly.loc[formation[-1], names] / monthly.loc[formation[0] - 1, names] - 1
    ids = np.sign(raw.values) * ((daily_returns[names] < 0).mean().values - (daily_returns[names] > 0).mean().values)
    scores = pd.DataFrame({"residual_score": residual, "raw_momentum": raw.values,
                           "information_discreteness": ids}, index=names)
    scores = scores.loc[np.isfinite(scores).all(axis=1)]
    count = math.ceil(len(scores) * .2)

    def ranked(values, n, ascending=False):
        return sorted(values.index, key=lambda name: ((values[name] if ascending else -values[name]), name))[:n]

    raw_names = ranked(scores.raw_momentum, count)
    expected = {"residual_momentum": ranked(scores.residual_score, count), "raw_momentum": raw_names,
                "continuous_information": ranked(scores.loc[raw_names].information_discreteness, math.ceil(count / 2), True),
                "eligible_equal_weight": sorted(scores.index)}
    saved = pd.read_csv(root / "stock_results/stock_selections.csv", parse_dates=["signal_date"])
    saved = saved.loc[saved.signal_date.eq(signal)]
    checks = []
    for strategy, chosen in expected.items():
        observed = saved.loc[saved.strategy.eq(strategy)].set_index("ticker")
        if set(observed.index) != set(chosen):
            raise AssertionError(f"Independent selected names differ: {strategy}")
        errors = {column: float(np.max(abs(observed[column] - scores.loc[observed.index, column])))
                  for column in scores.columns}
        if max(errors.values()) > 1e-8:
            raise AssertionError(f"Independent scores differ: {strategy}, {errors}")
        checks.append({"strategy": strategy, "selected_count": len(chosen), "selection_matches": True,
                       "maximum_score_errors": errors})
    receipt = {"signal_date": str(signal.date()), "eligible_count": len(scores),
               "fit_months": [str(fit[0]), str(fit[-1])], "formation_months": [str(formation[0]), str(formation[-1])],
               "regression_method": "independent_QR_decomposition_retains_fitted_intercept_in_score",
               "production_module_imported": False, "checks": checks,
               "input_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in [price_path, membership_path, factor_path, spy_path]},
               "audit_implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (Path(public_output) / "independent_stock_signal_audit.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etf-folder", required=True)
    parser.add_argument("--crypto-folder", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--private-output", required=True)
    parser.add_argument("--stock-folder", help="Optional raw stock inputs and stock_results/ selection file")
    args = parser.parse_args()
    receipt = audit_results(args.etf_folder, args.crypto_folder, args.output, args.private_output)
    if args.stock_folder:
        audit_stock_signal(args.stock_folder, args.output)
    print(json.dumps({"identified_paths_audited": receipt["identified_paths_audited"],
                      "maximum_relative_wealth_error": receipt["maximum_relative_wealth_error"]}))


if __name__ == "__main__":
    main()
