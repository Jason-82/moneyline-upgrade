"""Check the independently implemented audit ledger on exact cashflows."""
import numpy as np
import pandas as pd
import pytest

from analysis_2026.theory_lab.audit import analytical_budget, rebuild_path


def test_analytical_budget_full_rotation_pays_sale_and_purchase_costs():
    # Sell 100 of A at 1% and purchase B including its 1% fee.
    capital = analytical_budget(100, [100, 0], [0, 1], .01)
    assert capital == pytest.approx(100 * .99 / 1.01)


def test_analytical_budget_handles_partial_drifted_rebalance_and_cash_target():
    # Holdings drifted to 80 A + 20 B, plus cash 10; rebalance to 30/50/20.
    # A is sold and B bought, giving cost .01*(80-.3*N+.5*N-20).
    expected = (110 - .01 * 60) / (1 + .01 * .2)
    assert analytical_budget(110, [80, 20], [.3, .5], .01) == pytest.approx(expected)


def test_independent_ledger_does_not_rebalance_between_signals_and_liquidates():
    days = pd.date_range("2020-01-01", periods=4)
    prices = {
        "A": pd.DataFrame({"open": [10, 10, 20, 30], "close": [10, 10, 20, 30]}, index=days),
        "B": pd.DataFrame({"open": [20]*4, "close": [20]*4}, index=days),
    }
    schedule = pd.DataFrame({"A": [.5], "B": [.5]}, index=days[:1])
    result = rebuild_path(prices, schedule, days[1], days[-1], fee=.01, capital=100)
    post_buy = 100 / 1.01
    assert result.iloc[0] == pytest.approx(post_buy)
    assert result.iloc[1] == pytest.approx(post_buy * 1.5)
    assert result.iloc[-1] == pytest.approx(post_buy * 2 * .99)


def test_independent_ledger_next_open_delay_removes_signal_return():
    days = pd.date_range("2020-01-01", periods=4)
    prices = {"A": pd.DataFrame({"open": [1, 2, 4, 8], "close": [1, 2, 4, 8]}, index=days)}
    schedule = pd.DataFrame({"A": [1.]}, index=days[:1])
    result = rebuild_path(prices, schedule, days[1], days[-1], delay=2, capital=100)
    assert result.tolist() == pytest.approx([100, 100, 200])


def test_random_analytical_cash_budgets_reconcile_without_iteration():
    rng = np.random.default_rng(901)
    for n in range(1, 10):
        for _ in range(25):
            current = rng.random(n) * 1000
            equity = current.sum() + rng.random() * 1000
            weights = rng.random(n)
            weights *= rng.random() / weights.sum()
            fee = rng.uniform(0, .1)
            result = analytical_budget(equity, current, weights, fee)
            assert result + fee * np.abs(result * weights - current).sum() == pytest.approx(equity, abs=1e-9)
