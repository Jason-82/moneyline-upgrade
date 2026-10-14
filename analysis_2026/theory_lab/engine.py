"""Cash-only, next-open research execution with actual traded-notional costs.

An ETF input may be a *synthetic total-return* OHLC series. Its fractional units
therefore represent reinvestment units, not literal historical raw-share fills.
The engine never uses those units to claim actual tax-lot accounting.

Signals are dated completed closes. Each symbol executes at its own Nth available
session strictly after that date. Holdings drift between explicit rebalances.
Calendar gaps in held assets fail; the opt-in ``terminal_zero`` policy writes off
only a history that has ended, never an internal missing observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    path: pd.DataFrame
    transactions: pd.DataFrame
    events: pd.DataFrame
    stats: dict[str, float]


@dataclass
class TaxSensitivityResult:
    annual: pd.DataFrame
    stats: dict[str, float]
    description: str = (
        "Illustrative aggregate annual-growth tax sensitivity; not FIFO, actual "
        "realized gains, dividend taxation, or a tax-law calculation."
    )


def _date(value: Any) -> pd.Timestamp:
    value = pd.Timestamp(value)
    if value.tzinfo is not None or value != value.normalize():
        raise ValueError("Dates must be timezone-naive midnight session dates")
    return value


def _index(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    result = frame.copy()
    result.index = pd.DatetimeIndex([_date(value) for value in frame.index])
    if result.index.has_duplicates or not result.index.is_monotonic_increasing:
        raise ValueError(f"{label} dates must be unique and increasing")
    return result


def _post_fee_nav(equity: float, current: np.ndarray, weights: np.ndarray, fee: float) -> float:
    """Solve NAV = pre-trade NAV - fee * absolute executed notional.

    With nonnegative weights summing to at most one and fee < 1, the
    piecewise-linear equation is strictly increasing and has one root in [0,E].
    """
    if fee == 0:
        return equity
    low, high = 0.0, equity
    for _ in range(70):
        middle = (low + high) / 2
        residual = middle + fee * np.abs(middle * weights - current).sum() - equity
        if residual > 0:
            high = middle
        else:
            low = middle
    return (low + high) / 2


def portfolio_statistics(
    path: pd.DataFrame,
    *,
    initial_capital: float | None = None,
    market: str = "crypto",
) -> dict[str, float]:
    """Decimal rates. Turnover is gross buys + sells / mean NAV / elapsed years.

    CAGR uses elapsed calendar days, with a one-day minimum for a one-bar test.
    Sharpe uses all session returns, including initial trading costs, zero RF,
    and sample standard deviation. Worst year includes partial calendar years.
    Drawdown includes the starting capital even if first-session fees reduce NAV.
    """
    if path.empty:
        raise ValueError("Cannot summarize an empty path")
    if market not in {"crypto", "etf"}:
        raise ValueError("market must be crypto or etf")
    initial = float(initial_capital if initial_capital is not None else path.attrs.get("initial_capital", np.nan))
    if not np.isfinite(initial) or initial <= 0:
        raise ValueError("initial_capital is required and must be positive")
    equity = path["equity"].astype(float)
    if not np.isfinite(equity).all() or (equity < 0).any():
        raise ValueError("Equity must be finite and nonnegative")
    elapsed_days = max((path.index[-1] - path.index[0]).days, 1)
    years = elapsed_days / 365.25
    values = np.r_[initial, equity.to_numpy()]
    prior = values[:-1]
    returns = np.divide(values[1:], prior, out=np.zeros_like(prior), where=prior > 0) - 1
    returns[prior == 0] = 0.0
    deviation = float(np.std(returns, ddof=1)) if len(returns) > 1 else np.nan
    sharpe = float(np.mean(returns) / deviation * np.sqrt(365.25 if market == "crypto" else 252)) if deviation > 0 else np.nan
    peaks = np.maximum.accumulate(values)
    max_drawdown = float(np.min(values / peaks - 1))
    year_end = equity.groupby(equity.index.year).last()
    year_start = np.r_[initial, year_end.to_numpy()[:-1]]
    annual_returns = np.divide(year_end.to_numpy(), year_start, out=np.ones_like(year_start), where=year_start > 0) - 1
    turnover = float(path["turnover_notional"].sum())
    mean_equity = float(np.mean(values))
    annual_turnover = turnover / mean_equity / years if mean_equity > 0 else np.nan
    return {
        "ending_equity": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / initial - 1),
        "cagr": float((equity.iloc[-1] / initial) ** (1 / years) - 1),
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "volatility": float(deviation * np.sqrt(365.25 if market == "crypto" else 252)),
        "annualized_volatility": float(deviation * np.sqrt(365.25 if market == "crypto" else 252)),
        "worst_year": float(np.min(annual_returns)),
        "annual_turnover": float(annual_turnover),
        "annual_turnover_gross": float(annual_turnover),
        "total_turnover_notional": turnover,
        "total_fees": float(path["fees"].sum()),
        "average_exposure": float(path["exposure"].mean()),
        "calendar_years": years,
    }


def run_portfolio(
    prices: Mapping[str, pd.DataFrame],
    target_schedule: pd.DataFrame,
    *,
    start: Any,
    end: Any,
    initial_capital: float = 100_000.0,
    fee_rate: float = 0.0,
    execution_lag: int = 1,
    cash_rate: float = 0.0,
    market: str = "crypto",
    missing_held_policy: str = "fail",
) -> BacktestResult:
    """Execute long-only close targets at subsequent actual opens.

    Every schedule row specifies the complete universe, with explicit zeros.
    Invalid, missing, negative, leveraged, or unknown weights fail. Endpoints
    must be actual common sessions. A schedule signal may precede ``start``;
    only orders whose lagged execution lies inside the window are executed.
    Orders after ``end`` are disclosed as unexecuted events. Final holdings are
    sold at the final actual close with the same per-side cost.

    For staggered calendars only symbols whose orders mature on a date trade.
    If those partial orders cannot be financed without selling an unavailable
    asset, the run fails rather than scaling or borrowing silently.
    """
    start, end = _date(start), _date(end)
    if end < start:
        raise ValueError("end precedes start")
    if not prices:
        raise ValueError("A nonempty price universe is required")
    if not np.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    if not np.isfinite(fee_rate) or not 0 <= fee_rate < 1:
        raise ValueError("fee_rate must be in [0, 1)")
    if not isinstance(execution_lag, int) or isinstance(execution_lag, bool) or execution_lag < 1:
        raise ValueError("execution_lag must be a positive integer")
    if not np.isfinite(cash_rate) or cash_rate <= -1:
        raise ValueError("cash_rate must be a finite effective annual rate above -1")
    if market not in {"crypto", "etf"}:
        raise ValueError("market must be crypto or etf")
    if missing_held_policy not in {"fail", "terminal_zero"}:
        raise ValueError("missing_held_policy must be fail or terminal_zero")
    frames: dict[str, pd.DataFrame] = {}
    calendars: dict[str, pd.DatetimeIndex] = {}
    for symbol, source in prices.items():
        frame = _index(source, f"{symbol} prices")
        if frame.empty or not {"open", "close"}.issubset(frame.columns):
            raise ValueError(f"{symbol} requires nonempty open and close prices")
        # An observed session with a missing price remains a session. Removing
        # it here would silently defer a next-open order to a later day.
        numeric = frame[["open", "close"]].astype(float)
        valid = np.isfinite(numeric).all(axis=1) & (numeric > 0).all(axis=1)
        valid_sessions = frame.index[valid]
        calendars[symbol] = frame.index
        frames[symbol] = frame
        if start not in valid_sessions or end not in valid_sessions:
            if missing_held_policy != "terminal_zero" or start not in valid_sessions or not len(valid_sessions) or calendars[symbol][-1] >= end:
                raise ValueError(f"{symbol}: start and end must be actual valid common sessions")
    schedule = _index(target_schedule, "Schedule")
    symbols = list(frames)
    if set(schedule.columns) != set(symbols) or schedule.columns.has_duplicates:
        raise ValueError("Every schedule row must explicitly name exactly the price universe")
    schedule = schedule[symbols].astype(float)
    if not np.isfinite(schedule.to_numpy()).all() or (schedule.to_numpy() < 0).any():
        raise ValueError("Target weights must be finite and nonnegative; missing targets are not zeros")
    if (schedule.sum(axis=1) > 1 + 1e-12).any():
        raise ValueError("Target weights may not exceed 100% capital")
    # A microscopic round-off excess is normalized; economically leveraged rows fail.
    totals = schedule.sum(axis=1)
    schedule.loc[totals > 1] = schedule.loc[totals > 1].div(totals[totals > 1], axis=0)
    sessions = pd.DatetimeIndex(sorted(set().union(*(set(frame.index[(frame.index >= start) & (frame.index <= end)]) for frame in frames.values()))))
    if sessions.empty:
        raise ValueError("No tested sessions")
    if end not in sessions:
        raise ValueError("At least one asset must have an actual final session at end")
    orders: dict[pd.Timestamp, dict[str, tuple[float, pd.Timestamp]]] = {}
    events: list[dict[str, Any]] = []
    for signal_date, row in schedule.iterrows():
        for symbol in symbols:
            calendar = calendars[symbol]
            offset = int(calendar.searchsorted(signal_date, side="right")) + execution_lag - 1
            if offset >= len(calendar):
                if row[symbol] > 0 and signal_date < end and calendar[-1] < end:
                    raise ValueError(f"{symbol}: a positive scheduled target has no available future open inside the tested window")
                events.append({"date": signal_date, "symbol": symbol, "event": "unexecuted_no_later_open", "target_weight": float(row[symbol])})
                continue
            execution_date = calendar[offset]
            if execution_date > end:
                events.append({"date": signal_date, "symbol": symbol, "event": "unexecuted_after_end", "target_weight": float(row[symbol])})
            elif execution_date >= start:
                # Later closes take priority if several map to the same opening.
                orders.setdefault(execution_date, {})[symbol] = (float(row[symbol]), signal_date)
    quantities = {symbol: 0.0 for symbol in symbols}
    cash = float(initial_capital)
    transactions: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    last_date = start

    def quote(symbol: str, date: pd.Timestamp, field: str) -> float:
        if date not in frames[symbol].index:
            raise ValueError(f"Missing held or scheduled {symbol} {field} price on {date.date()}")
        value = float(frames[symbol].at[date, field])
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid held or scheduled {symbol} {field} price on {date.date()}")
        return value

    for date in sessions:
        cash *= (1 + cash_rate) ** ((date - last_date).days / 365.25)
        last_date = date
        turnover, fees = 0.0, 0.0
        for symbol in symbols:
            if quantities[symbol] == 0:
                continue
            if date not in calendars[symbol]:
                if missing_held_policy == "terminal_zero" and calendars[symbol][-1] < date:
                    events.append({"date": date, "symbol": symbol, "event": "terminal_zero_writeoff", "quantity": quantities[symbol]})
                    quantities[symbol] = 0.0
                else:
                    raise ValueError(f"Missing held {symbol} price on {date.date()}; stale marks are forbidden")
        active = orders.get(date, {})
        open_values = {symbol: quantities[symbol] * quote(symbol, date, "open") for symbol in symbols if quantities[symbol] > 0}
        equity_open = cash + sum(open_values.values())
        if active:
            tolerance = max(initial_capital, equity_open) * 128 * np.finfo(float).eps
            active_symbols = [symbol for symbol in symbols if symbol in active]
            current = np.array([open_values.get(symbol, 0.0) for symbol in active_symbols])
            weights = np.array([active[symbol][0] for symbol in active_symbols])
            nav = _post_fee_nav(equity_open, current, weights, fee_rate)
            target_quantities = {symbol: nav * active[symbol][0] / quote(symbol, date, "open") for symbol in active_symbols}
            changes = {symbol: target_quantities[symbol] - quantities[symbol] for symbol in active_symbols}
            # Compute prospective financing first so a failed staggered rebalance
            # does not leave a partially applied ledger.
            prospective_cash = cash - sum(changes[symbol] * quote(symbol, date, "open") + abs(changes[symbol]) * quote(symbol, date, "open") * fee_rate for symbol in active_symbols)
            if prospective_cash < -tolerance:
                raise ValueError("Staggered target execution cannot be financed without unavailable sales or margin")
            ordered = sorted(active_symbols, key=lambda symbol: changes[symbol] >= 0)
            for symbol in ordered:
                delta = changes[symbol]
                if delta == 0:
                    continue
                price = quote(symbol, date, "open")
                notional = abs(delta) * price
                fee = notional * fee_rate
                cash += -delta * price - fee
                if cash < -tolerance:
                    raise AssertionError("Self-financing solver produced negative cash")
                if cash < 0:
                    events.append({"date": date, "symbol": "CASH", "event": "floating_point_cash_residual", "amount": cash})
                    cash = 0.0
                quantities[symbol] = target_quantities[symbol]
                turnover += notional
                fees += fee
                transactions.append({"date": date, "signal_date": active[symbol][1], "symbol": symbol, "side": "buy" if delta > 0 else "sell", "quantity": abs(delta), "price": price, "notional": notional, "fee": fee, "cash_after": cash, "reason": "scheduled_rebalance"})
        held_value = sum(quantities[symbol] * quote(symbol, date, "close") for symbol in symbols if quantities[symbol] > 0)
        equity_marked = cash + held_value
        exposure_marked = held_value / equity_marked if equity_marked > 0 else 0.0
        if date == end:
            for symbol in symbols:
                quantity = quantities[symbol]
                if quantity == 0:
                    continue
                price = quote(symbol, date, "close")
                notional = quantity * price
                fee = notional * fee_rate
                cash += notional - fee
                turnover += notional
                fees += fee
                quantities[symbol] = 0.0
                transactions.append({"date": date, "signal_date": pd.NaT, "symbol": symbol, "side": "sell", "quantity": quantity, "price": price, "notional": notional, "fee": fee, "cash_after": cash, "reason": "terminal_liquidation"})
            held_value = 0.0
        equity = cash + held_value
        rows.append({"date": date, "equity": equity, "cash": cash, "exposure": held_value / equity if equity > 0 else 0.0, "exposure_before_liquidation": exposure_marked, "equity_before_liquidation": equity_marked, "turnover_notional": turnover, "fees": fees})
    path = pd.DataFrame(rows).set_index("date")
    path.attrs.update({"initial_capital": float(initial_capital), "start": start.isoformat(), "end": end.isoformat(), "market": market, "fee_rate": fee_rate, "execution_lag": execution_lag, "cash_rate": cash_rate, "missing_held_policy": missing_held_policy})
    transaction_columns = ["date", "signal_date", "symbol", "side", "quantity", "price", "notional", "fee", "cash_after", "reason"]
    trades = pd.DataFrame(transactions, columns=transaction_columns)
    event_frame = pd.DataFrame(events, columns=["date", "symbol", "event", "target_weight", "quantity", "amount"])
    stats = portfolio_statistics(path, initial_capital=initial_capital, market=market)
    return BacktestResult(path, trades, event_frame, stats)


def annual_gain_tax_sensitivity(
    result: BacktestResult | pd.DataFrame,
    *,
    tax_rate: float = 0.35,
    initial_capital: float | None = None,
) -> TaxSensitivityResult:
    """Tax positive aggregate calendar-year growth after dollar loss carryforward.

    Gross annual return is measured from the pretax strategy. A separate wealth
    ledger deducts a hypothetical year-end tax and uses the same subsequent
    percentage returns. This is a conservative sensitivity, not a calculation of
    realized gains, FIFO basis, distributions, or tax-financing trades.
    """
    if not np.isfinite(tax_rate) or not 0 <= tax_rate <= 1:
        raise ValueError("tax_rate must be between zero and one")
    path = result.path if isinstance(result, BacktestResult) else result
    if path.empty:
        raise ValueError("Cannot tax an empty path")
    initial = float(initial_capital if initial_capital is not None else path.attrs.get("initial_capital", np.nan))
    if not np.isfinite(initial) or initial <= 0:
        raise ValueError("initial_capital is required and must be positive")
    gross_end = path["equity"].groupby(path.index.year).last()
    gross_start = np.r_[initial, gross_end.to_numpy()[:-1]]
    annual_returns = np.divide(gross_end.to_numpy(), gross_start, out=np.ones_like(gross_start), where=gross_start > 0) - 1
    wealth, loss_carry = initial, 0.0
    rows = []
    for year, annual_return in zip(gross_end.index, annual_returns):
        opening = wealth
        gain = opening * float(annual_return)
        carry_before = loss_carry
        if gain < 0:
            taxable_gain = 0.0
            loss_carry += -gain
        else:
            offset = min(loss_carry, gain)
            loss_carry -= offset
            taxable_gain = gain - offset
        tax = tax_rate * taxable_gain
        wealth = opening + gain - tax
        rows.append({"year": int(year), "starting_equity": opening, "gross_return": float(annual_return), "aggregate_gain": gain, "loss_carry_before": carry_before, "taxable_gain": taxable_gain, "tax": tax, "loss_carry_after": loss_carry, "ending_equity": wealth})
    years = max((path.index[-1] - path.index[0]).days, 1) / 365.25
    annual = pd.DataFrame(rows).set_index("year")
    stats = {"ending_equity": wealth, "total_return": wealth / initial - 1, "cagr": (wealth / initial) ** (1 / years) - 1, "total_tax": float(annual["tax"].sum()), "ending_loss_carry": loss_carry, "tax_rate": tax_rate}
    return TaxSensitivityResult(annual, stats)
