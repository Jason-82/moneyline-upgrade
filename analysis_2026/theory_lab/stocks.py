"""Frozen, long-only stock momentum research; never connects to a broker.

The provider's point-in-time membership is not a complete delisted-price
database. Results therefore describe the covered PIT subset. Actual missing
    held prices invalidate the strict path; the separate terminal zero-writeoff path is
an explicitly conservative sensitivity, not an estimate of delisting returns.
Adjusted OHLC represents total-return units and cannot support tax-lot claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


STRATEGIES = ("residual_momentum", "continuous_information", "raw_momentum", "eligible_equal_weight")
EXCLUDED_TICKERS = ("STI",)  # Recycled symbol; historical SunTrust prices absent.


@dataclass
class StockInputs:
    opens: pd.DataFrame
    closes: pd.DataFrame
    membership: pd.DataFrame
    factors: pd.DataFrame
    spy_open: pd.Series
    spy_close: pd.Series
    fingerprints: dict


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(data_root: str | Path) -> StockInputs:
    root = Path(data_root)
    price_path = root / "prices.parquet"
    members_path = root / "raw/membership_intervals.parquet"
    factors_path = root / "ff3_monthly.csv"
    spy_path = root / "total_return/SPY.csv"
    frame = pd.read_parquet(price_path, columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "source"])
    if frame.duplicated(["date", "ticker"]).any():
        raise ValueError("Duplicate stock date/ticker prices")
    for column in ("open", "high", "low", "close", "adj_close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame.loc[(frame.close <= 0) | (frame.adj_close <= 0), ["close", "adj_close", "open"]] = np.nan
    frame["tr_open"] = frame.open * frame.adj_close / frame.close
    bad_ohlc = frame[["open", "high", "low", "close"]].isna().any(axis=1) | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
    frame.loc[bad_ohlc, "tr_open"] = np.nan
    # Close-only CRSP records cannot supply a real execution price.
    frame.loc[frame.source.str.lower().eq("crsp"), "tr_open"] = np.nan
    opens = frame.pivot(index="date", columns="ticker", values="tr_open").sort_index()
    closes = frame.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    members = pd.read_parquet(members_path)
    for column in ("start", "end"):
        members[column] = pd.to_datetime(members[column])
    factors = pd.read_csv(factors_path, parse_dates=["date"]).set_index("date")
    factors.index = factors.index.to_period("M")
    if factors.index.duplicated().any():
        raise ValueError("Duplicate factor months")
    spy = pd.read_csv(spy_path, parse_dates=["date"]).set_index("date").sort_index()
    # The independently acquired SPY feed supplies the master NYSE calendar.
    calendar = spy.index[(spy.index >= opens.index.min()) & (spy.index <= opens.index.max())]
    opens, closes = opens.reindex(calendar), closes.reindex(calendar)
    fingerprints = {str(p.relative_to(root)): sha256(p) for p in (price_path, members_path, factors_path, spy_path)}
    return StockInputs(opens, closes, members, factors, spy.open.reindex(calendar), spy.close.reindex(calendar), fingerprints)


def pit_members(membership: pd.DataFrame, date: pd.Timestamp) -> set[str]:
    """Membership intervals are [start, end), including multiple spells."""
    active = (membership.start <= date) & (membership.end.isna() | (date < membership.end))
    return set(membership.loc[active, "ticker"]) - set(EXCLUDED_TICKERS)


def residual_scores(returns: np.ndarray, factors: np.ndarray, rf: np.ndarray,
                    formation_positions: np.ndarray) -> np.ndarray:
    """OLS with intercept; do not subtract the fitted intercept at formation.

    Thirty-six fit observations and eleven formation observations are supplied
    by the caller. This retains the factor-adjusted alpha in the momentum score.
    All factors are final-vintage data with a deliberate one-month availability
    lag; genuine vintage backtesting is unavailable.
    """
    excess = returns - rf[:, None]
    design = np.column_stack([np.ones(len(factors)), factors])
    coefficient = np.linalg.lstsq(design, excess, rcond=None)[0]
    adjusted = excess[formation_positions] - factors[formation_positions] @ coefficient[1:]
    sd = adjusted.std(axis=0, ddof=1)
    return np.divide(adjusted.sum(axis=0), sd, out=np.full(len(sd), np.nan), where=sd > 0)


def information_discreteness(daily_returns: np.ndarray, cumulative_returns: np.ndarray) -> np.ndarray:
    """Lowest ID = most continuous; zero-return days stay in the denominator."""
    negatives = (daily_returns < 0).mean(axis=0)
    positives = (daily_returns > 0).mean(axis=0)
    return np.sign(cumulative_returns) * (negatives - positives)


def rank_tickers(scores: pd.Series, count: int, ascending: bool = False) -> list[str]:
    data = scores.rename("score").reset_index()
    data.columns = ["ticker", "score"]
    return data.sort_values(["score", "ticker"], ascending=[ascending, True]).ticker.head(count).tolist()


def build_selections(inputs: StockInputs, first_signal="2000-12-01", cutoff="2026-10-13") -> tuple[pd.DataFrame, pd.DataFrame]:
    """All eligibility and scores are known at the signal's monthly close.

    For signal month t, fit t-36..t-1 and form t-12..t-2 inclusive.
    Equal eligibility requires all 37 fit-boundary closes, every formation
    session close and actual open, current membership, and finite scores.
    No future price availability participates in selection.
    """
    calendar = inputs.closes.index
    period_by_day = calendar.to_period("M")
    month_ends = calendar.to_series(index=calendar).groupby(period_by_day).max()
    cutoff = pd.Timestamp(cutoff)
    # Exclude the last partial month rather than treating its last date as EOM.
    month_ends = month_ends[month_ends <= cutoff]
    month_ends = month_ends[month_ends.index < cutoff.to_period("M")]
    monthly = inputs.closes.loc[month_ends.to_numpy()].copy()
    monthly.index = month_ends.index
    monthly_returns = monthly.pct_change(fill_method=None)
    daily_returns = inputs.closes.pct_change(fill_method=None)
    rows, coverage = [], []
    for period, signal_date in month_ends.items():
        if signal_date < pd.Timestamp(first_signal):
            continue
        fit_periods = pd.period_range(period - 36, period - 1, freq="M")
        price_periods = pd.period_range(period - 37, period - 1, freq="M")
        form_periods = pd.period_range(period - 12, period - 2, freq="M")
        members = pit_members(inputs.membership, signal_date)
        candidate_symbols = sorted(members & set(inputs.closes.columns))
        audit = {"signal_date": signal_date, "pit_members": len(members), "symbols_with_any_prices": len(candidate_symbols),
                 "excluded_recycled_symbols": ";".join(EXCLUDED_TICKERS), "factor_vintage": "final_revision_one_month_lag_proxy"}
        ff = inputs.factors.reindex(fit_periods)[["Mkt-RF", "SMB", "HML", "RF"]]
        if ff.isna().any().any() or not len(candidate_symbols):
            coverage.append({**audit, "eligible_count": 0, "eligibility_status": "missing_factors_or_prices"})
            continue
        boundary = monthly.reindex(price_periods)[candidate_symbols]
        full_boundary = boundary.notna().all(axis=0) & (boundary > 0).all(axis=0)
        formation_mask = (period_by_day >= form_periods[0]) & (period_by_day <= form_periods[-1])
        form_dates = calendar[formation_mask]
        if not len(form_dates):
            coverage.append({**audit, "eligible_count": 0, "eligibility_status": "missing_formation"})
            continue
        # Actual opens in formation exclude close-only histories before any run.
        form_daily = daily_returns.loc[form_dates, candidate_symbols]
        full_daily = form_daily.notna().all(axis=0) & inputs.opens.loc[form_dates, candidate_symbols].notna().all(axis=0)
        symbols = list(full_boundary.index[full_boundary & full_daily])
        if not symbols:
            coverage.append({**audit, "eligible_count": 0, "eligibility_status": "no_complete_histories"})
            continue
        ret = monthly_returns.reindex(fit_periods)[symbols]
        positions = fit_periods.get_indexer(form_periods)
        rs = pd.Series(residual_scores(ret.to_numpy(), ff[["Mkt-RF", "SMB", "HML"]].to_numpy(), ff.RF.to_numpy(), positions), index=symbols)
        momentum = (1 + ret.loc[form_periods]).prod(axis=0) - 1
        ids = pd.Series(information_discreteness(form_daily[symbols].to_numpy(), momentum.to_numpy()), index=symbols)
        eligible = rs.index[np.isfinite(rs) & np.isfinite(momentum) & np.isfinite(ids)].tolist()
        if not eligible:
            coverage.append({**audit, "eligible_count": 0, "eligibility_status": "no_finite_scores"})
            continue
        top_count = max(1, math.ceil(len(eligible) * .20))
        raw = rank_tickers(momentum[eligible], top_count)
        chosen = {
            "residual_momentum": rank_tickers(rs[eligible], top_count),
            "continuous_information": rank_tickers(ids[raw], max(1, math.ceil(top_count / 2)), ascending=True),
            "raw_momentum": raw,
            "eligible_equal_weight": sorted(eligible),
        }
        for strategy, holdings in chosen.items():
            for ticker in holdings:
                rows.append({"signal_date": signal_date, "strategy": strategy, "ticker": ticker, "weight": 1 / len(holdings),
                             "raw_momentum": momentum[ticker], "residual_score": rs[ticker], "information_discreteness": ids[ticker]})
        coverage.append({**audit, "eligible_count": len(eligible), "eligible_fraction_of_pit": len(eligible) / len(members),
                         "eligibility_status": "covered_pit_subset", "top_quintile_count": top_count})
    return pd.DataFrame(rows), pd.DataFrame(coverage)


def execution_schedule(selections: pd.DataFrame, strategy: str, calendar: pd.DatetimeIndex,
                       delay_sessions: int = 1) -> dict[pd.Timestamp, dict[str, float]]:
    if delay_sessions < 1:
        raise ValueError("Execution must occur after the signal close")
    schedule = {}
    subset = selections[selections.strategy == strategy]
    for signal, group in subset.groupby("signal_date"):
        position = calendar.searchsorted(signal, side="right") + delay_sessions - 1
        if position < len(calendar):
            schedule[calendar[position]] = dict(zip(group.ticker, group.weight))
    return schedule


def costed_target_values(current: dict[str, float], weights: dict[str, float], cash: float, fee: float) -> tuple[dict[str, float], float]:
    """Solve the cash budget; transaction costs cannot be paid with leverage."""
    if not 0 <= fee < 1 or not 0 <= sum(weights.values()) <= 1 + 1e-10:
        raise ValueError("Invalid cost or weights")
    symbols = sorted(set(current) | set(weights))
    nav = cash + sum(current.values())
    lo, hi = 0., nav
    def remaining(capital):
        sell = sum(max(current.get(s, 0) - capital * weights.get(s, 0), 0) for s in symbols)
        buy = sum(max(capital * weights.get(s, 0) - current.get(s, 0), 0) for s in symbols)
        # A declared cash allocation remains after the costed rebalance.
        return cash + sell * (1 - fee) - buy * (1 + fee) - capital * (1 - sum(weights.values()))
    for _ in range(60):
        middle = (lo + hi) / 2
        if remaining(middle) >= 0:
            lo = middle
        else:
            hi = middle
    targets = {s: lo * weights.get(s, 0) for s in symbols}
    turnover = sum(abs(targets[s] - current.get(s, 0)) for s in symbols)
    return targets, turnover * fee


def path_metrics(equity: pd.Series, initial=1.) -> dict:
    if equity.empty:
        return {}
    returns = equity.pct_change(fill_method=None)
    returns.iloc[0] = equity.iloc[0] / initial - 1
    years = ((equity.index[-1] - equity.index[0]).days + 1) / 365.25
    drawdown = equity / equity.cummax().clip(lower=initial) - 1
    sd = returns.std(ddof=1)
    return {"total_return_pct": (equity.iloc[-1] / initial - 1) * 100,
            "cagr_pct": ((equity.iloc[-1] / initial) ** (1 / years) - 1) * 100 if years else np.nan,
            "max_drawdown_pct": drawdown.min() * 100,
            "realized_volatility_pct": sd * np.sqrt(252) * 100,
            "sharpe_zero_cash": returns.mean() / sd * np.sqrt(252) if sd > 0 else np.nan,
            "ending_equity": equity.iloc[-1], "years": years}


def simulate(opens: pd.DataFrame, closes: pd.DataFrame, schedule: dict, start, end,
             fee=.0003, missing_policy="strict", annual_gain_levy=0., final_liquidate=True,
             cash_yield=0., terminal_gain_levy=0.) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Daily mark-to-market of drifting units, with only scheduled rebalances.

    ``annual_gain_levy`` is a portfolio-level annual P&L levy with loss carry,
    paid from cash/actual proportional sales at that year's final close. It is
    NOT tax-lot accounting, a tax-law model, or an after-tax investor projection.
    """
    if missing_policy not in ("strict", "writeoff_zero"):
        raise ValueError("Unknown missing price policy")
    calendar = opens.index[(opens.index >= pd.Timestamp(start)) & (opens.index <= pd.Timestamp(end))]
    if calendar.empty:
        return {"status": "unidentified", "reason": "no_sessions"}, pd.DataFrame(), pd.DataFrame()
    if not opens.index.equals(closes.index) or not opens.columns.equals(closes.columns):
        raise ValueError("Open and close panels must align")
    symbols = list(opens.columns)
    symbol_position = {s: i for i, s in enumerate(symbols)}
    open_values, close_values = opens.to_numpy(), closes.to_numpy()
    quantity = np.zeros(len(symbols), dtype=float)
    cash, losses, year_base, turnover, tax_paid = 1., 0., 1., 0., 0.
    curves, events = [], []
    last_date_by_year = calendar.to_series().groupby(calendar.year).max().to_dict()
    previous_date = calendar[0]
    for date, panel_position in zip(calendar, opens.index.get_indexer(calendar)):
        cash *= (1 + cash_yield) ** ((date - previous_date).days / 365.25)
        previous_date = date
        op, cl = open_values[panel_position], close_values[panel_position]
        valid_open, valid_close = np.isfinite(op) & (op > 0), np.isfinite(cl) & (cl > 0)
        held_missing = [symbols[p] for p in np.flatnonzero((quantity > 0) & ~valid_close)]
        target = schedule.get(date)
        requested = set(target or {})
        held = set(symbols[p] for p in np.flatnonzero(quantity > 0)) if target is not None else set()
        open_missing = [s for s in held | requested if s not in symbol_position or not valid_open[symbol_position[s]]] if target is not None else []
        selected_close_missing = [s for s in requested if s not in symbol_position or not valid_close[symbol_position[s]]]
        missing = sorted(set(held_missing) | set(open_missing) | set(selected_close_missing))
        if missing:
            internal = []
            for symbol in missing:
                last_close = closes[symbol].last_valid_index() if symbol in closes else None
                last_open = opens[symbol].last_valid_index() if symbol in opens else None
                observed = [d for d in (last_close, last_open) if d is not None]
                if observed and max(observed) >= date:
                    internal.append(symbol)
            events.extend({"date": date, "event": "unpriced_exposure", "ticker": s, "missing_policy": missing_policy,
                           "held_units": quantity[symbol_position[s]] if s in symbol_position else 0.,
                           "gap_type": "internal_or_inconsistent" if s in internal else "terminal"} for s in missing)
            if missing_policy == "strict" or internal:
                return {"status": "unidentified", "reason": "internal_price_gap" if internal else "unpriced_held_or_selected_execution", "first_unknown_date": str(date.date()),
                        "unknown_tickers": ";".join(missing), "traded_notional": turnover, "tax_paid": tax_paid}, pd.DataFrame(curves), pd.DataFrame(events)
            for s in missing:
                if s in symbol_position:
                    quantity[symbol_position[s]] = 0.
        if target is not None:
            current = {symbols[p]: quantity[p] * op[p] for p in np.flatnonzero(quantity > 0)}
            targets, costs = costed_target_values(current, target, cash, fee)
            traded = sum(abs(targets[s] - current.get(s, 0)) for s in targets)
            cash += sum(current.values()) - sum(targets.values()) - costs
            turnover += traded
            if cash < -1e-10:
                raise AssertionError("Unfunded stock purchase")
            cash = max(cash, 0.)
            quantity[:] = 0.
            for s, value in targets.items():
                if value > 0 and s not in missing:
                    p = symbol_position[s]
                    quantity[p] = value / op[p]
            for s in missing:
                if targets.get(s, 0) > 0:
                    events.append({"date": date, "event": "selected_allocation_zero_writeoff", "ticker": s, "amount": targets[s], "missing_policy": missing_policy})
            events.append({"date": date, "event": "rebalance", "traded_notional": traded, "cost": costs, "cash": cash, "holdings": np.count_nonzero(quantity > 0)})
        valued_close = np.where(valid_close, cl, 0.)
        invested = np.dot(quantity, valued_close)
        equity = cash + invested
        if date == last_date_by_year[date.year] and annual_gain_levy:
            profit = equity - year_base
            if profit < 0:
                losses += -profit
                levy = 0.
            else:
                offset = min(losses, profit)
                losses -= offset
                levy = (profit - offset) * annual_gain_levy
            use_cash = min(cash, levy)
            cash -= use_cash
            needed = levy - use_cash
            if needed > 0 and invested > 0:
                fraction = min(1., needed / (invested * (1 - fee)))
                sold = invested * fraction
                quantity *= 1 - fraction
                cash += sold * (1 - fee) - needed
                turnover += sold
                invested -= sold
                events.append({"date": date, "event": "annual_levy_sale", "traded_notional": sold, "cost": sold * fee})
            tax_paid += levy
            equity = cash + invested
            year_base = equity
            events.append({"date": date, "event": "annual_gain_levy", "amount": levy, "loss_carry": losses})
        if date == calendar[-1] and final_liquidate and invested:
            cash += invested * (1 - fee)
            turnover += invested
            events.append({"date": date, "event": "terminal_liquidation", "traded_notional": invested, "cost": invested * fee})
            quantity[:] = 0.
            invested, equity = 0., cash
        if date == calendar[-1] and terminal_gain_levy:
            levy = max(equity - 1., 0.) * terminal_gain_levy
            cash -= levy
            equity -= levy
            tax_paid += levy
            events.append({"date": date, "event": "terminal_gain_levy", "amount": levy})
        largest = np.max(quantity * valued_close) / equity if equity else 0.
        curves.append({"date": date, "equity": equity, "cash": cash, "invested": invested,
                       "exposure": invested / equity if equity else 0., "largest_position_weight": largest, "holding_count": np.count_nonzero(quantity > 0)})
    curve = pd.DataFrame(curves).set_index("date")
    stats = path_metrics(curve.equity)
    return {"status": "identified", **stats, "traded_notional": turnover, "tax_paid": tax_paid,
            "average_exposure_pct": curve.exposure.mean() * 100, "maximum_position_weight_pct": curve.largest_position_weight.max() * 100,
            "unpriced_event_count": len([e for e in events if e["event"] == "unpriced_exposure"])}, curve.reset_index(), pd.DataFrame(events)


def run_stock_study(data_root, output_dir, cutoff="2026-09-30") -> pd.DataFrame:
    inputs = load_inputs(data_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    selections, coverage = build_selections(inputs, cutoff=cutoff)
    selections.to_csv(output / "stock_selections.csv", index=False)
    coverage.to_csv(output / "stock_coverage.csv", index=False)
    periods = {"development_2001_2012": ("2001-01-01", "2012-12-31"),
               "later_2013_2025": ("2013-01-01", "2025-12-31"),
               "full_2001_2025": ("2001-01-01", "2025-12-31"),
               "descriptive_2026_ytd": ("2026-01-01", cutoff)}
    results, all_events, all_curves, all_monthly, all_yearly = [], [], [], [], []
    for period, (start, end) in periods.items():
        if pd.Timestamp(end) < pd.Timestamp(start):
            continue
        for delay in (1, 2):
            for strategy in (*STRATEGIES, "SPY_buy_hold"):
                if strategy == "SPY_buy_hold":
                    op, cl = inputs.spy_open.to_frame("SPY"), inputs.spy_close.to_frame("SPY")
                    signal = selections.signal_date[selections.signal_date < pd.Timestamp(start)].max()
                    position = op.index.searchsorted(signal, side="right") + delay - 1
                    schedule = {op.index[position]: {"SPY": 1.}}
                else:
                    op, cl = inputs.opens, inputs.closes
                    schedule = execution_schedule(selections, strategy, op.index, delay)
                for fee in (.0003, .001):
                    for missing_policy in ("strict", "writeoff_zero"):
                        for levy, terminal_levy, cash_yield in ((0., 0., 0.), (.35, 0., 0.), (0., 0., .04), *(([(0., .20, 0.)] if strategy == "SPY_buy_hold" else []))):
                            key = {"period": period, "strategy": strategy, "delay_sessions": delay, "cost_per_side_bps": fee * 10000,
                                   "missing_policy": missing_policy, "annual_gain_levy_rate": levy,
                                   "terminal_gain_levy_rate": terminal_levy, "cash_yield": cash_yield}
                            metrics, curve, events = simulate(op, cl, schedule, start, end, fee=fee, missing_policy=missing_policy,
                                                             annual_gain_levy=levy, cash_yield=cash_yield, terminal_gain_levy=terminal_levy)
                            results.append({**key, **metrics})
                            print(json.dumps({**key, "status": metrics["status"], "completed_rows": len(results)}), flush=True)
                            if not curve.empty:
                                all_curves.append(curve.assign(status=metrics["status"], **key))
                                eq = curve.set_index("date").equity
                                monthly = eq.groupby(eq.index.to_period("M")).last()
                                previous = monthly.shift(1).fillna(1.)
                                all_monthly.append(pd.DataFrame({"month": monthly.index.astype(str), "equity": monthly.to_numpy(),
                                                                "return": (monthly / previous - 1).to_numpy()}).assign(status=metrics["status"], **key))
                                yearly = eq.groupby(eq.index.year).last()
                                previous = yearly.shift(1).fillna(1.)
                                all_yearly.append(pd.DataFrame({"year": yearly.index, "ending_equity": yearly.to_numpy(),
                                                               "return_pct": ((yearly / previous - 1) * 100).to_numpy()}).assign(status=metrics["status"], **key))
                            if not events.empty:
                                all_events.append(events.assign(**key))
    result = pd.DataFrame(results)
    result.to_csv(output / "stock_metrics.csv", index=False)
    pd.concat(all_curves, ignore_index=True).to_csv(output / "stock_equity.csv", index=False)
    pd.concat(all_events, ignore_index=True).to_csv(output / "stock_events.csv", index=False)
    pd.concat(all_monthly, ignore_index=True).to_csv(output / "stock_monthly.csv", index=False)
    pd.concat(all_yearly, ignore_index=True).to_csv(output / "stock_calendar_years.csv", index=False)
    receipt = {"input_sha256": inputs.fingerprints, "implementation_sha256": sha256(Path(__file__)), "cutoff": cutoff,
               "factor_latest_month": str(inputs.factors.index.max()), "factor_vintage": "final_vintage_with_one_month_lag_proxy_not_pit_vintages",
               "total_return_prices": True, "tax_model": "annual_portfolio_gain_levy_with_loss_carry_not_tax_lots",
               "membership_end_exclusive": True, "excluded_tickers": list(EXCLUDED_TICKERS), "strategies": list(STRATEGIES),
               "status_counts": result.status.value_counts().to_dict(), "output_sha256": {p.name: sha256(p) for p in output.glob("stock_*.csv")}}
    (output / "stock_receipt.json").write_text(json.dumps(receipt, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cutoff", default="2026-09-30")
    args = parser.parse_args()
    result = run_stock_study(args.data, args.output, args.cutoff)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
