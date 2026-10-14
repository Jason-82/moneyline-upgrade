"""Execution invariants for the research-only UTC crypto sleeve engine."""
import math
import numpy as np
import pandas as pd
import pytest

from crypto_research.portfolio import (
    CryptoPortfolioConfig, CryptoPortfolioDataError, Rebalance,
    portfolio_metrics, simulate_portfolio,
)
from research.tax import TaxLedger, TaxRates


def bars(start="2024-01-01", opens=(100, 100, 100), closes=None):
    op = np.asarray(opens, float)
    cl = op.copy() if closes is None else np.asarray(closes, float)
    return pd.DataFrame({"open": op, "high": np.maximum(op, cl),
                         "low": np.minimum(op, cl), "close": cl},
                        index=pd.date_range(start, periods=len(op), freq="D"))


def signals(frame, target=1.0, regime=None):
    idx = pd.date_range(frame.index[0] - pd.Timedelta(days=1), frame.index[-1])
    target = np.full(len(idx), target) if np.isscalar(target) else np.array(target, float)
    return pd.DataFrame({"target": target, "regime": target if regime is None else regime}, index=idx)


def simulate(frame, sig=None, **kwargs):
    config = kwargs.pop("config", CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1))
    return simulate_portfolio({"A": frame}, frame.index, [Rebalance(frame.index[0], ("A",))],
                              frame.index[0], frame.index[-1], signals={"A": signals(frame) if sig is None else sig},
                              config=config, **kwargs)


def test_completed_prior_signal_executes_at_actual_next_open():
    frame = bars(opens=(100, 200, 100), closes=(120, 220, 100))
    sig = signals(frame, [0, 1, 0, 1])
    result = simulate(frame, sig)
    # Jan1 close's green executes Jan2 at200, Jan2 red exits Jan3 at100.
    trades = result.ledger[result.ledger.event.isin(["buy", "sell"])]
    assert list(trades.date) == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]
    assert list(trades.price) == [200, 100]
    assert result.metrics["final_value"] == 50
    assert result.metrics["max_drawdown"] == pytest.approx(-0.54545454545)


def test_daily_green_price_drift_does_not_trade_or_daily_top_up():
    frame = bars(opens=(100, 200, 300), closes=(200, 300, 400))
    result = simulate(frame)
    assert result.metrics["final_value"] == 400
    assert result.metrics["trades"] == 2  # Entry and declared final liquidation only.
    assert list(result.ledger.reason) == ["prior_close_target_increase", "declared_final_close_liquidation"]


def test_fixed_fraction_does_not_rebalance_price_drift():
    frame = bars(opens=(100, 200, 300), closes=(200, 300, 400))
    result = simulate(frame, signals(frame, 0.5))
    assert result.metrics["final_value"] == 250
    assert result.metrics["trades"] == 2


def test_cost_fraction_solves_post_trade_target_without_borrowing():
    frame = bars(opens=(100,))
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=100, slot_capacity=1, liquidate_at_end=False)
    result = simulate(frame, signals(frame, 0.5), config=cfg)
    qty = result.positions["A"]
    assert qty == pytest.approx(0.5 / 1.005)
    assert qty * 100 / result.metrics["final_value"] == pytest.approx(0.5)
    assert result.metrics["total_fees"] == pytest.approx(qty)


def test_low_price_high_quantity_full_exit_uses_exact_owned_quantity():
    # Same arithmetic failure as the actual SHIB2025-09-16 research exit:
    # q*exit_price/exit_price exceeds q by oneULP, exceeding1e-7coin units.
    entry_price, exit_price, fee = 1.031e-6, 1.306e-5, .001
    frame = bars(opens=(entry_price, exit_price))
    cfg = CryptoPortfolioConfig(initial_capital=100_000, cost_bps=10, slot_capacity=1)
    qty = cfg.initial_capital / (entry_price * (1 + fee))
    assert (qty * exit_price) / exit_price - qty > 1e-7
    result = simulate(frame, signals(frame, [1, 0, 0]), config=cfg)
    assert result.ledger.iloc[0].shares == result.ledger.iloc[1].shares
    assert result.positions["A"] == 0
    assert result.metrics["final_value"] == pytest.approx(qty * exit_price * (1 - fee))
    assert result.trade_summary["closed_lots"] == 1


def test_low_price_high_quantity_fractional_exit_matches_post_cost_target():
    frame = bars(opens=(1.031e-6, 1.306e-5))
    cfg = CryptoPortfolioConfig(initial_capital=100_000, cost_bps=10, slot_capacity=1,
                                liquidate_at_end=False)
    target = .4
    result = simulate(frame, signals(frame, [1, target, target]), config=cfg)
    bought, sold = result.ledger.iloc[0].shares, result.ledger.iloc[1].shares
    assert 0 < sold < bought
    remaining = result.positions["A"]
    assert remaining == bought - sold
    assert remaining * frame.iloc[-1].close / result.metrics["final_value"] == pytest.approx(target)


def test_empty_slots_stay_cash_and_red_cash_is_not_redistributed():
    a = bars(opens=(100, 100), closes=(100, 200))
    b = bars(opens=(100, 100), closes=(100, 100))
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=4)
    result = simulate_portfolio({"A": a, "B": b}, a.index, [Rebalance(a.index[0], ("A", "B"))],
                                a.index[0], a.index[-1], signals={"A": signals(a), "B": signals(b, 0)}, config=cfg)
    assert result.metrics["final_value"] == 125  # A25 doubled; B25/red and two25emptyslots cash.
    assert result.metrics["trades"] == 2


def test_volatility_threshold_is_relative_to_last_executed_target():
    frame = bars(opens=(100, 100, 100, 100))
    sig = signals(frame, [0.5, 0.55, 0.59, 0.61, 0.61], regime=0.5)
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1, liquidate_at_end=False)
    result = simulate(frame, sig, config=cfg)
    buys = result.ledger[result.ledger.event == "buy"]
    assert list(buys.date) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-04")]
    assert list(buys.shares) == pytest.approx([0.5, 0.11])


def test_regime_change_bypasses_volatility_threshold():
    frame = bars(opens=(100, 100))
    sig = signals(frame, [0.5, 0.55, 0.55], regime=[0.5, 0.6, 0.6])
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1, liquidate_at_end=False)
    result = simulate(frame, sig, config=cfg)
    assert result.metrics["trades"] == 2
    assert result.positions["A"] == pytest.approx(0.55)


def test_target_increase_can_cross_threshold_from_zero():
    frame = bars(opens=(100, 100))
    sig = signals(frame, [0, 0.1, 0.1], regime=0.5)
    result = simulate(frame, sig)
    assert list(result.ledger.event) == ["buy", "sell"]
    assert result.ledger.iloc[0].date == pd.Timestamp("2024-01-02")


def test_final_close_is_real_price_and_charged_same_cost():
    frame = bars(opens=(100,), closes=(200,))
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=100, slot_capacity=1)
    result = simulate(frame, config=cfg)
    assert result.metrics["final_value"] == pytest.approx(100 / 1.01 * 2 * 0.99)
    assert result.ledger.iloc[-1].price == 200
    assert result.ledger.iloc[-1].fee == pytest.approx(100 / 1.01 * 2 * 0.01)


def test_end_entry_fee_drawdown_includes_initial_capital():
    result = simulate(bars(opens=(100,)), config=CryptoPortfolioConfig(initial_capital=100, cost_bps=100, slot_capacity=1))
    assert result.metrics["max_drawdown"] == pytest.approx(0.99 / 1.01 - 1)


@pytest.mark.parametrize("missing", ["open", "close", "high"])
def test_selected_missing_bar_fails_even_while_red(missing):
    frame = bars()
    frame.loc[frame.index[1], missing] = np.nan
    with pytest.raises(CryptoPortfolioDataError, match="actual selected OHLC unavailable"):
        simulate(frame, signals(frame, 0))


def test_selected_missing_day_is_not_forward_filled_or_removed():
    frame = bars().drop(pd.Timestamp("2024-01-02"))
    cal = pd.date_range("2024-01-01", "2024-01-03")
    with pytest.raises(CryptoPortfolioDataError, match="actual selected OHLC unavailable"):
        simulate_portfolio({"A": frame}, cal, [Rebalance(cal[0], ("A",))], cal[0], cal[-1],
                           signals={"A": signals(frame)}, config=CryptoPortfolioConfig(slot_capacity=1))


def test_vanished_selected_history_does_not_get_stale_terminal_fill():
    frame = bars().iloc[:2]
    cal = pd.date_range("2024-01-01", "2024-01-03")
    with pytest.raises(CryptoPortfolioDataError, match="actual selected OHLC unavailable"):
        simulate_portfolio({"A": frame}, cal, [Rebalance(cal[0], ("A",))], cal[0], cal[-1],
                           always_in=True, config=CryptoPortfolioConfig(slot_capacity=1))


def test_unused_malformed_future_data_does_not_change_historical_result():
    frame = bars()
    result = simulate(frame)
    future = pd.DataFrame({"open": [np.nan], "high": [np.nan], "low": [np.nan], "close": [np.nan]},
                          index=pd.DatetimeIndex(["2024-01-04"]))
    extended = pd.concat([frame, future])
    other = simulate_portfolio({"A": extended}, frame.index, [Rebalance(frame.index[0], ("A",))],
                               frame.index[0], frame.index[-1], signals={"A": signals(extended)},
                               config=CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1))
    pd.testing.assert_series_equal(result.path, other.path)


def test_prior_signal_must_exist_and_be_completed_day():
    frame = bars()
    sig = signals(frame).iloc[1:]
    with pytest.raises(CryptoPortfolioDataError, match="prior completed UTC-day target"):
        simulate(frame, sig)


def test_leverage_rejected():
    frame = bars()
    with pytest.raises(CryptoPortfolioDataError, match="leveraged"):
        simulate(frame, signals(frame, 1.01))


def test_24_7_calendar_cannot_skip_weekend_or_requested_day():
    frame = bars(start="2024-01-05")
    with pytest.raises(CryptoPortfolioDataError, match="without gaps"):
        simulate_portfolio({"A": frame}, frame.index[[0, 2]], [], frame.index[0], frame.index[-1], always_in=True)
    with pytest.raises(CryptoPortfolioDataError, match="complete requested"):
        simulate_portfolio({"A": frame}, frame.index[:2], [], frame.index[0], frame.index[-1], always_in=True)


def test_no_empty_window_dropped_cash_horizon_retained():
    frame = bars()
    result = simulate_portfolio({}, frame.index, [], frame.index[0], frame.index[-1], always_in=True,
                                config=CryptoPortfolioConfig(initial_capital=100))
    assert list(result.path) == [100, 100, 100]
    assert result.metrics["trades"] == 0
    assert result.metrics["total_return"] == 0


def test_same_selection_repetition_does_not_rebalance():
    frame = bars(opens=(100, 200, 300), closes=(100, 200, 300))
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1)
    result = simulate_portfolio({"A": frame}, frame.index,
                                [Rebalance(frame.index[0], ("A",)), Rebalance(frame.index[1], ("A",))],
                                frame.index[0], frame.index[-1], always_in=True, config=cfg)
    assert result.metrics["trades"] == 2
    assert result.metrics["final_value"] == 300


def test_changed_selection_resizes_retained_lots_and_new_slot_without_reset():
    a = bars(opens=(100, 200, 200), closes=(100, 200, 200))
    b = bars()
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=2)
    result = simulate_portfolio({"A": a, "B": b}, a.index,
                                [Rebalance(a.index[0], ("A",)), Rebalance(a.index[1], ("A", "B"))],
                                a.index[0], a.index[-1], always_in=True, config=cfg)
    assert result.metrics["final_value"] == 150
    resize = result.ledger[result.ledger.reason == "selection_resize"]
    assert list(resize.security_id) == ["A"]
    assert resize.iloc[0].shares == pytest.approx(0.125)
    assert result.trade_summary["closed_lots"] == 2


def test_removal_uses_actual_open_not_previous_close():
    a = bars(opens=(100, 20), closes=(100, 20))
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1)
    result = simulate_portfolio({"A": a}, a.index,
                                [Rebalance(a.index[0], ("A",)), Rebalance(a.index[1], ())],
                                a.index[0], a.index[-1], always_in=True, config=cfg)
    assert result.metrics["final_value"] == 20
    assert result.ledger.iloc[-1].reason == "selection_removal"
    assert result.ledger.iloc[-1].price == 20


def test_trade_analytics_aggregate_partial_sales_into_entry_lot():
    frame = bars(opens=(100, 200, 400), closes=(100, 200, 400))
    sig = signals(frame, [1, 0.5, 0, 0])
    result = simulate(frame, sig)
    summary = result.trade_summary
    assert summary["closed_lots"] == 1
    assert summary["win_rate"] == 1
    assert summary["gross_winning_gain"] == 200  # Half sold200; remainder400 =>proceeds300.
    assert summary["mean_winning_return"] == 2
    assert summary["top_winner_profit_share"] == 1


def test_terminal_illustrative_tax_liquidates_and_pays_no_external_cash():
    frame = bars(opens=(100, 100), closes=(100, 200))
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1, tax_enabled=True,
                                tax_rates=TaxRates(short_term=.35, long_term=.20))
    result = simulate(frame, config=cfg)
    assert result.metrics["final_value"] == 165
    assert result.metrics["total_tax"] == 35
    assert result.tax_records.iloc[0].short_gain == 100
    assert all(quantity == 0 for quantity in result.positions.values())
    assert result.deployment_blocked is True
    assert any("not_crypto_liability" in flag for flag in result.flags)


def test_long_term_hold_illustrative_tax_differs_from_frequent_short_term():
    index = pd.date_range("2023-01-01", "2024-01-03")
    frame = bars("2023-01-01", np.full(len(index), 100), np.r_[np.full(len(index)-1, 100), 200])
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1, tax_enabled=True)
    result = simulate(frame, config=cfg)
    assert result.metrics["final_value"] == 180
    assert result.metrics["total_tax"] == 20


def test_annual_tax_funding_sells_actual_fractional_position_and_carries_lots():
    index = pd.date_range("2023-12-30", "2024-02-01")
    op = np.full(len(index), 200.0)
    op[0] = 100
    frame = bars("2023-12-30", op)
    sig = signals(frame, 1)
    # Sell and rebuy in December realizes100STgain, thenholdpositionJan31taxsale.
    sig.loc[pd.Timestamp("2023-12-30"), ["target", "regime"]] = 0
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1, tax_enabled=True)
    result = simulate(frame, sig, config=cfg)
    funding = result.ledger[result.ledger.reason == "illustrative_tax_funding"]
    assert len(funding) == 1
    assert funding.iloc[0].date == pd.Timestamp("2024-01-31")
    assert funding.iloc[0].price == 200
    assert funding.iloc[0].shares == pytest.approx(.175)
    assert result.metrics["final_value"] == 165
    assert result.metrics["total_tax"] == 35


def test_canonical_fifo_full_sale_consumes_all_actual_lots_and_cash():
    # Twelve fractional lots from the VETcase that exposed independent
    # aggregate-position drift. Canonical sums/full-sale handling are opt-in.
    quantities = [13089.208012184754, 564.7999161319603, 9852.896172457506,
                  48384.34838440161, 30963.41373444123, 6414.261994977111,
                  2192.1464312258104, 6791.970367097398, 31103.04855261276,
                  30945.484550015615, 188.84998398309835, 601.7578541632101]
    book = TaxLedger(canonical_quantities=True)
    default = TaxLedger()
    costs = []
    for qty in quantities:
        basis = qty * .0037
        costs.append(basis)
        book.buy("VET", "2020-01-01", qty, basis)
        default.buy("VET", "2020-01-01", qty, basis)
    assert default.canonical_quantities is False
    assert default.position("VET") == sum(quantities)  # Existing stock behavior.
    assert book.position("VET") == math.fsum(quantities)
    owned = book.position("VET")
    with pytest.raises(ValueError, match="sale exceeds position"):
        book.sell("VET", "2020-09-24", np.nextafter(owned, np.inf), 2000)
    net_proceeds = 2000.001
    book.sell("VET", "2020-09-24", owned, net_proceeds)
    assert book.position("VET") == 0
    assert book.lots["VET"] == []
    sale = book.transactions[-1]
    assert len(sale["realizations"]) == len(quantities)
    assert sale["original_gain"] == pytest.approx(net_proceeds - sum(costs), abs=1e-10)
    reconstructed_cash = sum(fragment["basis"] + fragment["original_gain"]
                             for fragment in sale["realizations"])
    assert reconstructed_cash == pytest.approx(net_proceeds, abs=1e-10)


def test_repeated_low_price_fractional_trades_keep_tax_fifo_and_portfolio_coherent(monkeypatch):
    # Zero tax rates isolate quantity accounting from policy: choosing an
    # illustrative tax ledger must not create economic return or missing cash.
    count = 84
    prices = 1e-6 * np.exp(np.sin(np.arange(count) * .5) * .7)
    frame = bars(opens=prices)
    target = np.resize(np.array([1, 2, 3, 4, 2, 5, 1, 8, 0, 7, 9, 2], float) / 9, count + 1)
    sig = signals(frame, target)
    original_sell = TaxLedger.sell
    full_exits = []

    def audited_sell(self, sid, day, quantity, proceeds, reason="signal"):
        assert self.canonical_quantities is True
        owned = self.position(sid)
        assert quantity <= owned  # No absolute or relative oversale permission.
        full = quantity == owned
        result = original_sell(self, sid, day, quantity, proceeds, reason)
        if full:
            assert self.position(sid) == 0
            full_exits.append(day)
        return result

    monkeypatch.setattr(TaxLedger, "sell", audited_sell)
    zero_rates = TaxRates(short_term=0, long_term=0, ordinary=0, qualified_dividend=0)
    cfg = CryptoPortfolioConfig(initial_capital=100_000, cost_bps=50, slot_capacity=1)
    pretax = simulate(frame, sig, config=cfg)
    taxed = simulate(frame, sig, config=CryptoPortfolioConfig(
        initial_capital=100_000, cost_bps=50, slot_capacity=1, tax_enabled=True, tax_rates=zero_rates))
    assert len(full_exits) >= 7
    assert taxed.metrics["trades"] == pretax.metrics["trades"]
    assert taxed.metrics["total_tax"] == 0
    np.testing.assert_allclose(taxed.path, pretax.path, rtol=1e-12, atol=1e-7)
    assert taxed.positions["A"] == 0
    assert taxed.metrics["final_value"] == pytest.approx(100_000 + taxed.ledger.cash_flow.sum(), abs=1e-7)


def test_loss_carry_not_reset_across_years_illustrative_model():
    index = pd.date_range("2023-12-30", "2024-02-02")
    op = np.full(len(index), 50.0)
    op[0] = 100
    frame = bars("2023-12-30", op)
    sig = signals(frame, 1)
    sig.loc[pd.Timestamp("2023-12-30"), ["target", "regime"]] = 0
    sig.loc[pd.Timestamp("2023-12-31"):pd.Timestamp("2024-01-31"), ["target", "regime"]] = 0
    # RebuyFebruary1 afterwashwindow, final50 no gain;carry50 persists.
    sig.loc[pd.Timestamp("2024-02-01"), ["target", "regime"]] = 1
    cfg = CryptoPortfolioConfig(initial_capital=100, cost_bps=0, slot_capacity=1, tax_enabled=True)
    result = simulate(frame, sig, config=cfg)
    assert result.carry == pytest.approx((-50, 0))
    assert result.metrics["total_tax"] == 0


def test_metrics_use_full_utc_days_and_zero_cash_sharpe():
    path = pd.Series([100, 100], index=pd.date_range("2024-01-01", periods=2))
    metrics = portfolio_metrics(path, 100)
    assert metrics["years"] == 2/365.25
    assert np.isnan(metrics["sharpe365"])


@pytest.mark.parametrize("config", [CryptoPortfolioConfig(slot_capacity=0),
                                    CryptoPortfolioConfig(initial_capital=float("nan")),
                                    CryptoPortfolioConfig(cost_bps=-1),
                                    CryptoPortfolioConfig(rebalance_threshold=1.1)])
def test_invalid_config_rejected(config):
    with pytest.raises(ValueError):
        simulate(bars(), config=config)
