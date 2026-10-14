import numpy as np
import pandas as pd
import pytest

from analysis_2026.theory_lab.stocks import (
    StockInputs, build_selections, costed_target_values, execution_schedule,
    information_discreteness, path_metrics, pit_members, rank_tickers,
    residual_scores, simulate,
)


def prices(a, b=None, dates=None):
    dates = pd.DatetimeIndex(dates or pd.bdate_range("2024-01-02", periods=len(a)))
    return pd.DataFrame({"A": a, **({"B": b} if b is not None else {})}, index=dates)


def test_membership_end_exclusive_and_recycled_symbol():
    membership = pd.DataFrame({"ticker": ["A", "B", "STI"],
                               "start": pd.to_datetime(["2000-01-01"] * 3),
                               "end": pd.to_datetime(["2000-02-01", None, None])})
    assert pit_members(membership, pd.Timestamp("2000-01-31")) == {"A", "B"}
    assert pit_members(membership, pd.Timestamp("2000-02-01")) == {"B"}


def test_id_zeros_stay_in_denominator_and_negative_momentum_sign():
    daily = np.array([[.1, -.1], [0., 0.], [.1, -.1], [-.1, .1]])
    np.testing.assert_allclose(information_discreteness(daily, np.array([.1, -.1])), [-.25, -.25])


def test_stable_rank_ties():
    assert rank_tickers(pd.Series([1., 1., 0.], index=["B", "A", "C"]), 2) == ["A", "B"]


def test_residual_score_retains_intercept_effect():
    rng = np.random.default_rng(4)
    f = rng.normal(0, .01, (36, 3))
    noise = rng.normal(0, .001, 36)
    excess = np.column_stack([f @ [.9, .4, -.2] + .02 + noise,
                              f @ [.9, .4, -.2] - .02 + noise])
    rf = np.full(36, .002)
    score = residual_scores(excess + rf[:, None], f, rf, np.arange(24, 35))
    assert score[0] > 0 > score[1]


def test_cost_budget_exact_and_no_negative_cash():
    targets, cost = costed_target_values({}, {"A": .5, "B": .5}, 1., .001)
    assert sum(targets.values()) + cost == pytest.approx(1.)
    assert targets["A"] == pytest.approx(.5 / 1.001)
    targets, cost = costed_target_values({"A": .8, "B": .2}, {"A": .5, "B": .5}, 0., .001)
    assert sum(targets.values()) + cost == pytest.approx(1.)
    assert targets["A"] == pytest.approx(targets["B"])


def test_drifts_units_instead_of_free_daily_equal_weight_rebalancing():
    p = prices([10., 20., 10.], [10., 10., 20.])
    metrics, curve, events = simulate(p, p, {p.index[0]: {"A": .5, "B": .5}}, p.index[0], p.index[-1], fee=0.)
    np.testing.assert_allclose(curve.equity, [1., 1.5, 1.5])
    assert metrics["ending_equity"] == pytest.approx(1.5)
    assert (events.event == "rebalance").sum() == 1


def test_both_entry_and_terminal_exit_costs():
    p = prices([10., 10.])
    metrics, curve, _ = simulate(p, p, {p.index[0]: {"A": 1.}}, p.index[0], p.index[-1], fee=.001)
    assert metrics["ending_equity"] == pytest.approx((1 - .001) / (1 + .001))
    assert metrics["max_drawdown_pct"] == pytest.approx(((1 - .001) / (1 + .001) - 1) * 100)
    assert (curve.cash >= -1e-12).all()


def test_execution_only_after_signal_and_extra_session():
    calendar = pd.bdate_range("2024-01-30", periods=5)
    selections = pd.DataFrame({"signal_date": [pd.Timestamp("2024-01-31")], "strategy": ["raw_momentum"], "ticker": ["A"], "weight": [1.]})
    assert list(execution_schedule(selections, "raw_momentum", calendar, 1)) == [pd.Timestamp("2024-02-01")]
    assert list(execution_schedule(selections, "raw_momentum", calendar, 2)) == [pd.Timestamp("2024-02-02")]
    with pytest.raises(ValueError):
        execution_schedule(selections, "raw_momentum", calendar, 0)


@pytest.mark.parametrize("policy", ["strict", "writeoff_zero"])
def test_internal_held_gap_remains_unidentified_under_both_policies(policy):
    p = prices([10., np.nan, 10.])
    metrics, _, events = simulate(p, p, {p.index[0]: {"A": 1.}}, p.index[0], p.index[-1], fee=0., missing_policy=policy)
    assert metrics["status"] == "unidentified"
    assert metrics["reason"] == "internal_price_gap"
    assert events.iloc[-1].gap_type == "internal_or_inconsistent"


def test_terminal_gap_zero_is_separate_conservative_diagnostic():
    p = prices([10., np.nan, np.nan])
    strict, _, _ = simulate(p, p, {p.index[0]: {"A": 1.}}, p.index[0], p.index[-1], fee=0.)
    diagnostic, curve, _ = simulate(p, p, {p.index[0]: {"A": 1.}}, p.index[0], p.index[-1], fee=0., missing_policy="writeoff_zero")
    assert strict["status"] == "unidentified"
    assert diagnostic["status"] == "identified"
    assert diagnostic["ending_equity"] == 0.
    assert curve.equity.iloc[-1] == 0.


def test_missing_new_execution_is_not_silently_pruned():
    p = prices([10., 10.], [np.nan, np.nan])
    strict, _, _ = simulate(p, p, {p.index[0]: {"A": .5, "B": .5}}, p.index[0], p.index[-1], fee=0.)
    diagnostic, _, events = simulate(p, p, {p.index[0]: {"A": .5, "B": .5}}, p.index[0], p.index[-1], fee=0., missing_policy="writeoff_zero")
    assert strict["status"] == "unidentified"
    assert diagnostic["ending_equity"] == pytest.approx(.5)
    assert "selected_allocation_zero_writeoff" in events.event.to_list()


def test_unpriced_selected_close_detected_even_if_open_present():
    op = prices([10., 10.])
    cl = prices([np.nan, 10.])
    metrics, _, _ = simulate(op, cl, {op.index[0]: {"A": 1.}}, op.index[0], op.index[-1])
    assert metrics["status"] == "unidentified"


def test_annual_gain_levy_loss_carry_and_real_sale_funding():
    p = prices([10., 8., 11.], dates=["2024-01-02", "2024-12-31", "2025-12-31"])
    metrics, curve, events = simulate(p, p, {p.index[0]: {"A": 1.}}, p.index[0], p.index[-1], fee=0., annual_gain_levy=.35)
    assert metrics["tax_paid"] == pytest.approx(.035)
    assert metrics["ending_equity"] == pytest.approx(1.065)
    assert "annual_levy_sale" in events.event.to_list()
    assert (curve.cash >= -1e-12).all()


def test_terminal_gain_levy_passive_is_not_annual_taxation():
    p = prices([10., 20.])
    metrics, _, events = simulate(p, p, {p.index[0]: {"A": 1.}}, p.index[0], p.index[-1], fee=0., terminal_gain_levy=.20)
    assert metrics["ending_equity"] == pytest.approx(1.8)
    assert "annual_gain_levy" not in events.event.to_list()


def test_cash_yield_follows_calendar_elapsed_days():
    p = prices([10., 10.], dates=["2024-01-02", "2025-01-02"])
    metrics, _, _ = simulate(p, p, {}, p.index[0], p.index[-1], fee=0., cash_yield=.04)
    assert metrics["ending_equity"] == pytest.approx(1.04 ** (366 / 365.25))


def synthetic_inputs():
    calendar = pd.bdate_range("1996-01-01", "2002-12-31")
    rng = np.random.default_rng(5)
    prices = pd.DataFrame(np.exp(np.cumsum(rng.normal(.0002, .01, (len(calendar), 6)), axis=0)),
                          index=calendar, columns=["A", "B", "C", "D", "E", "STI"])
    membership = pd.DataFrame({"ticker": prices.columns, "start": pd.to_datetime(["1996-01-01"] * 6), "end": pd.NaT})
    period = pd.period_range("1996-01", "2002-12", freq="M")
    factors = pd.DataFrame(rng.normal(0, .02, (len(period), 4)), index=period, columns=["Mkt-RF", "SMB", "HML", "RF"])
    factors.RF = .001
    return StockInputs(prices.copy(), prices, membership, factors, prices.A, prices.A, {})


def test_selection_prefix_causal_and_no_signal_month_factor_dependency():
    inputs = synthetic_inputs()
    a, coverage = build_selections(inputs, first_signal="2000-12-01", cutoff="2001-02-01")
    inputs.closes.loc["2001-01-01":, "A"] *= 100
    inputs.opens.loc["2001-01-01":, "A"] *= 100
    inputs.factors.loc[pd.Period("2000-12", freq="M"):] = 1e6
    b, _ = build_selections(inputs, first_signal="2000-12-01", cutoff="2001-02-01")
    # December formation and fit end before all modified observations.
    pd.testing.assert_frame_equal(a[a.signal_date == "2000-12-29"].reset_index(drop=True),
                                  b[b.signal_date == "2000-12-29"].reset_index(drop=True))
    assert coverage.iloc[0].eligible_count == 5
    assert "STI" not in a.ticker.to_list()


def test_complete_daily_formation_required_and_partial_month_omitted():
    inputs = synthetic_inputs()
    inputs.opens.loc["2000-05-02", "A"] = np.nan
    a, coverage = build_selections(inputs, first_signal="2000-12-01", cutoff="2001-01-15")
    assert a.signal_date.max() == pd.Timestamp("2000-12-29")
    assert "A" not in a.ticker.to_list()
    assert coverage.iloc[0].eligible_count == 4


def test_metrics_initial_cost_drawdown_and_volatility():
    metrics = path_metrics(pd.Series([.999, .998], index=pd.bdate_range("2024-01-02", periods=2)))
    assert metrics["max_drawdown_pct"] == pytest.approx(-.2)
    assert "realized_volatility_pct" in metrics
