"""Independent small ledgers for next-open, cost, and cash-only execution."""

import numpy as np
import pandas as pd
import pytest

from analysis_2026.theory_lab.engine import (
    annual_gain_tax_sensitivity,
    portfolio_statistics,
    run_portfolio,
)


def bars(dates, opens, closes=None):
    closes = opens if closes is None else closes
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes), "low": np.minimum(opens, closes), "close": closes}, index=pd.to_datetime(dates))


def schedule(dates, **weights):
    return pd.DataFrame(weights, index=pd.to_datetime(dates))


def test_buy_hold_actual_opens_and_terminal_close_match_independent_ledger():
    prices = {"A": bars(["2020-01-01", "2020-01-02", "2020-01-03"], [10, 20, 30], [10, 25, 40])}
    result = run_portfolio(prices, schedule(["2020-01-01"], A=[1]), start="2020-01-02", end="2020-01-03", initial_capital=100, fee_rate=.01)
    quantity = 100 / (20 * 1.01)
    assert result.transactions.iloc[0]["quantity"] == pytest.approx(quantity)
    assert result.path.iloc[0]["equity"] == pytest.approx(quantity * 25)
    assert result.path.iloc[-1]["equity"] == pytest.approx(quantity * 40 * .99)
    assert result.path.iloc[-1]["cash"] == result.path.iloc[-1]["equity"]
    assert result.path.iloc[-1]["exposure"] == 0
    assert result.stats["total_fees"] == pytest.approx(quantity * (20 + 40) * .01)
    assert result.stats["total_turnover_notional"] == pytest.approx(quantity * 60)


def test_rebalance_sells_before_buys_and_pays_both_sides_without_margin():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    result = run_portfolio({"A": bars(dates, [10] * 4), "B": bars(dates, [20] * 4)}, schedule(dates[:2], A=[1, 0], B=[0, 1]), start=dates[1], end=dates[3], initial_capital=100, fee_rate=.01)
    first_qty = 100 / 10 / 1.01
    proceeds = first_qty * 10 * .99
    second_qty = proceeds / 20 / 1.01
    expected = second_qty * 20 * .99
    assert result.stats["ending_equity"] == pytest.approx(expected)
    switch = result.transactions.loc[result.transactions["date"] == pd.Timestamp(dates[2])]
    assert list(switch["side"]) == ["sell", "buy"]
    assert list(switch["symbol"]) == ["A", "B"]
    assert (result.path["cash"] >= 0).all()
    assert (result.transactions["cash_after"] >= -1e-10).all()
    # Independent cash-flow identity, with no price movement or interest.
    assert 100 - result.transactions["fee"].sum() == pytest.approx(expected)


def test_no_daily_rebalance_holdings_drift_between_explicit_schedule_rows():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    result = run_portfolio({"A": bars(dates, [10, 10, 20, 30])}, schedule(dates[:1], A=[.5]), start=dates[1], end=dates[-1], initial_capital=100)
    assert result.path.loc[dates[2], "equity"] == 150
    assert result.path.loc[dates[2], "exposure"] == pytest.approx(2 / 3)
    assert list(result.transactions["quantity"]) == [5, 5]
    assert len(result.transactions) == 2
    assert result.stats["ending_equity"] == 200


def test_execution_lag_uses_available_sessions_not_calendar_days_or_signal_open():
    dates = ["2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"]
    prices = {"A": bars(dates, [1, 2, 4, 8])}
    targets = schedule(dates[:1], A=[1])
    first = run_portfolio(prices, targets, start=dates[1], end=dates[-1], initial_capital=100, execution_lag=1, market="etf")
    second = run_portfolio(prices, targets, start=dates[1], end=dates[-1], initial_capital=100, execution_lag=2, market="etf")
    assert first.transactions.iloc[0]["date"] == pd.Timestamp(dates[1])
    assert second.transactions.iloc[0]["date"] == pd.Timestamp(dates[2])
    assert first.stats["ending_equity"] == 400
    assert second.stats["ending_equity"] == 200
    assert second.path.iloc[0]["equity"] == 100


def test_each_symbol_uses_own_calendar_and_no_fake_fill():
    common = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    result = run_portfolio({"A": bars(common, [10] * 4), "B": bars([common[0], common[2], common[3]], [20] * 3)}, schedule(common[:1], A=[.5], B=[.5]), start=common[0], end=common[-1], initial_capital=100)
    buys = result.transactions[result.transactions.side == "buy"]
    assert list(buys["date"]) == list(pd.to_datetime([common[1], common[2]]))
    assert result.stats["ending_equity"] == 100


def test_cash_interest_uses_actual_days_over_weekend_and_zero_rate_primary():
    dates = ["2020-01-03", "2020-01-06", "2020-01-07"]
    prices = {"A": bars(dates, [10] * 3)}
    targets = schedule(dates[:1], A=[0])
    primary = run_portfolio(prices, targets, start=dates[0], end=dates[-1], initial_capital=100, market="etf")
    interest = run_portfolio(prices, targets, start=dates[0], end=dates[-1], initial_capital=100, market="etf", cash_rate=.04)
    assert primary.stats["ending_equity"] == 100
    assert interest.path.loc[dates[1], "cash"] == pytest.approx(100 * 1.04 ** (3 / 365.25))
    assert interest.stats["ending_equity"] == pytest.approx(100 * 1.04 ** (4 / 365.25))
    assert interest.stats["cagr"] == pytest.approx(.04)


@pytest.mark.parametrize("bad_weight", [np.nan, -0.1, 1.001, np.inf])
def test_bad_weights_are_rejected_instead_of_skipped_or_silently_zeroed(bad_weight):
    dates = ["2020-01-01", "2020-01-02"]
    with pytest.raises(ValueError):
        run_portfolio({"A": bars(dates, [10, 10])}, schedule(dates[:1], A=[bad_weight]), start=dates[0], end=dates[-1])


def test_missing_weight_columns_and_non_common_endpoint_fail():
    dates = ["2020-01-01", "2020-01-02"]
    with pytest.raises(ValueError, match="exactly"):
        run_portfolio({"A": bars(dates, [10, 10]), "B": bars(dates, [20, 20])}, schedule(dates[:1], A=[1]), start=dates[0], end=dates[-1])
    with pytest.raises(ValueError, match="common sessions"):
        run_portfolio({"A": bars(dates, [10, 10])}, schedule(dates[:1], A=[1]), start=dates[0], end="2020-01-03")


@pytest.mark.parametrize("policy", ["fail", "terminal_zero"])
def test_internal_missing_held_bar_fails_even_with_terminal_writeoff_option(policy):
    dates = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    prices = {"A": bars([dates[0], dates[1], dates[3]], [10, 10, 20]), "B": bars(dates, [10] * 4)}
    with pytest.raises(ValueError, match="Missing held A"):
        run_portfolio(prices, schedule(dates[:1], A=[1], B=[0]), start=dates[0], end=dates[-1], missing_held_policy=policy)


def test_terminal_missing_history_requires_explicit_zero_writeoff_and_records_loss():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    prices = {"A": bars(dates[:2], [10, 10]), "B": bars(dates, [10] * 4)}
    targets = schedule(dates[:1], A=[.5], B=[0])
    with pytest.raises(ValueError):
        run_portfolio(prices, targets, start=dates[0], end=dates[-1], initial_capital=100)
    result = run_portfolio(prices, targets, start=dates[0], end=dates[-1], initial_capital=100, missing_held_policy="terminal_zero")
    assert result.stats["ending_equity"] == 50
    assert result.stats["max_drawdown"] == -.5
    assert result.events.iloc[0]["event"] == "terminal_zero_writeoff"
    assert result.events.iloc[0]["date"] == pd.Timestamp(dates[2])


def test_staggered_unfinanceable_target_fails_without_implicit_margin():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    # Existing B must be sold a day after the new A order would mature.
    prices = {"A": bars(dates, [10] * 4), "B": bars([dates[0], dates[1], dates[3]], [10] * 3)}
    targets = schedule(dates[:2], A=[0, 1], B=[1, 0])
    with pytest.raises(ValueError, match="Missing held B|cannot be financed"):
        run_portfolio(prices, targets, start=dates[0], end=dates[-1], initial_capital=100)


def test_fees_and_initial_equity_are_in_drawdown_and_return_statistics():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    result = run_portfolio({"A": bars(dates, [10] * 3)}, schedule(dates[:1], A=[1]), start=dates[1], end=dates[-1], initial_capital=100, fee_rate=.01)
    expected_return = .99 / 1.01 - 1
    assert result.stats["total_return"] == pytest.approx(expected_return)
    assert result.stats["max_drawdown"] == pytest.approx(expected_return)
    assert result.stats["worst_year"] == pytest.approx(expected_return)
    assert result.stats["cagr"] == pytest.approx((.99 / 1.01) ** 365.25 - 1)
    assert result.path.iloc[-1]["equity_before_liquidation"] > result.path.iloc[-1]["equity"]


def test_sharpe_annualization_is_explicit_market_specific():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    path = pd.DataFrame({"equity": [110, 100, 120], "turnover_notional": [0, 0, 0], "fees": [0, 0, 0], "exposure": [1, 1, 1]}, index=dates)
    returns = np.array([.1, 100 / 110 - 1, .2])
    crypto = portfolio_statistics(path, initial_capital=100, market="crypto")
    etf = portfolio_statistics(path, initial_capital=100, market="etf")
    assert crypto["sharpe"] == pytest.approx(returns.mean() / returns.std(ddof=1) * np.sqrt(365.25))
    assert etf["sharpe"] == pytest.approx(returns.mean() / returns.std(ddof=1) * np.sqrt(252))


def test_future_schedule_does_not_earn_signal_days_return_and_is_disclosed():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    result = run_portfolio({"A": bars(dates, [10, 100, 1000])}, schedule(dates[1:], A=[1, 0]), start=dates[0], end=dates[-1], initial_capital=100)
    assert result.path.loc[dates[1], "equity"] == 100
    assert result.stats["ending_equity"] == 100
    assert result.transactions.iloc[0]["date"] == pd.Timestamp(dates[-1])
    assert "unexecuted_no_later_open" in set(result.events["event"])


@pytest.mark.parametrize("field", ["open", "close"])
def test_missing_scheduled_execution_price_is_not_skipped_to_a_later_session(field):
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    prices = bars(dates, [10, 20, 30])
    prices.loc[dates[1], field] = np.nan
    with pytest.raises(ValueError, match="Invalid held or scheduled A"):
        run_portfolio({"A": prices}, schedule(dates[:1], A=[1]), start=dates[0], end=dates[-1])


def test_positive_target_cannot_disappear_after_a_terminal_price_history():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    with pytest.raises(ValueError, match="positive scheduled target"):
        run_portfolio({"A": bars(dates[:2], [10, 10]), "B": bars(dates, [10] * 4)}, schedule([dates[2]], A=[1], B=[0]), start=dates[0], end=dates[-1], missing_held_policy="terminal_zero")


def test_tax_sensitivity_loss_carry_is_dollar_ledger_and_not_realized_lot_claim():
    dates = pd.to_datetime(["2020-01-01", "2020-12-31", "2021-12-31", "2022-12-31"])
    path = pd.DataFrame({"equity": [100, 80, 100, 120]}, index=dates)
    path.attrs["initial_capital"] = 100
    taxed = annual_gain_tax_sensitivity(path)
    assert list(taxed.annual["tax"]) == pytest.approx([0, 0, 7])
    assert list(taxed.annual["loss_carry_after"]) == pytest.approx([20, 0, 0])
    assert taxed.stats["ending_equity"] == pytest.approx(113)
    assert "not FIFO" in taxed.description


def test_tax_deductions_reduce_next_year_growth_base_and_zero_rate_reproduces_wealth():
    dates = pd.to_datetime(["2020-01-01", "2020-12-31", "2021-12-31"])
    path = pd.DataFrame({"equity": [100, 200, 400]}, index=dates)
    taxed = annual_gain_tax_sensitivity(path, initial_capital=100)
    assert taxed.annual.iloc[0]["ending_equity"] == 165
    assert taxed.annual.iloc[1]["tax"] == pytest.approx(57.75)
    assert taxed.stats["ending_equity"] == pytest.approx(272.25)
    assert annual_gain_tax_sensitivity(path, initial_capital=100, tax_rate=0).stats["ending_equity"] == 400


@pytest.mark.parametrize("fee", [.0002, .001, .0015, .0095])
def test_actual_notional_fee_stress_rates_and_fractional_weights_are_self_financing(fee):
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    result = run_portfolio({"A": bars(dates, [7, 7, 11]), "B": bars(dates, [13, 13, 9])}, schedule(dates[:1], A=[.35], B=[.65]), start=dates[1], end=dates[-1], initial_capital=100, fee_rate=fee)
    invested_nav = 100 / (1 + fee)
    expected = (invested_nav * .35 / 7 * 11 + invested_nav * .65 / 13 * 9) * (1 - fee)
    assert result.stats["ending_equity"] == pytest.approx(expected)
    assert result.stats["total_fees"] == pytest.approx(result.transactions["notional"].sum() * fee)
    assert result.path["cash"].min() >= 0
