"""Synthetic fixtures for portfolio mechanics, independent of market holdouts."""
import unittest

import numpy as np
import pandas as pd

from research.portfolio import (PortfolioConfig, PortfolioDataError, PortfolioEngine, Rebalance,
                                portfolio_metrics, simulate_portfolio)
from research.tax import TaxRates

FIXTURE_META = {"validated": True, "price_basis": "split_only", "universe_complete": True,
                "dividends_complete": True, "terminal_complete": True, "point_in_time_ids": True,
                "price_source": "synthetic", "dividend_source": "synthetic",
                "corporate_action_source": "synthetic", "calendar_source": "synthetic"}


def bars(dates, opens, closes=None):
    if closes is None:
        closes = opens
    return pd.DataFrame({"open": opens, "high": [max(a, b) for a, b in zip(opens, closes)],
                         "low": [min(a, b) for a, b in zip(opens, closes)], "close": closes},
                        index=pd.DatetimeIndex(dates)).astype(float)


class PortfolioFixtures(unittest.TestCase):
    def setUp(self):
        self.cal = pd.bdate_range("2020-01-01", periods=6)
        self.config = PortfolioConfig(initial_capital=100, cost_bps=0, liquidate_at_end=False)

    def run_book(self, prices, green, **kwargs):
        return simulate_portfolio(prices, self.cal, [Rebalance(self.cal[1], tuple(prices))],
                                  self.cal[1], self.cal[-1], signals=green,
                                  config=kwargs.pop("config", self.config), metadata=FIXTURE_META, **kwargs)

    def test_close_flip_only_trades_next_actual_open(self):
        df = bars(self.cal, [10, 10, 20, 30, 40, 50])
        sig = pd.Series([False, True, False, False, False, False], index=self.cal)
        result = self.run_book({"A": df}, {"A": sig})
        trades = result.ledger[result.ledger.event.isin(["buy", "sell"])]
        self.assertEqual(list(trades.date), [self.cal[2], self.cal[3]])
        self.assertEqual(list(trades.price), [20, 30])
        self.assertAlmostEqual(result.mult, 1.5)

    def test_dividend_entitled_to_prior_night_shares_even_if_sold_at_ex_open(self):
        df = bars(self.cal, [10] * 6)
        sig = pd.Series([True, False, False, False, False, False], index=self.cal)
        div = pd.Series([1.0], index=[self.cal[2]])
        result = self.run_book({"A": df}, {"A": sig}, dividends={"A": div})
        self.assertAlmostEqual(result.mult, 1.1)
        self.assertAlmostEqual(result.ledger[result.ledger.event == "dividend"].cash_flow.sum(), 10)

    def test_ex_date_buyer_does_not_receive_dividend(self):
        df = bars(self.cal, [10] * 6)
        sig = pd.Series([False, True, True, True, True, True], index=self.cal)
        result = self.run_book({"A": df}, {"A": sig},
                               dividends={"A": pd.Series([1.0], index=[self.cal[2]])})
        self.assertAlmostEqual(result.mult, 1.0)

    def test_dividends_reinvest_next_open_and_compound(self):
        df = bars(self.cal, [10] * 6)
        dividends = {"A": pd.Series([1.0, 1.0], index=[self.cal[2], self.cal[4]])}
        result = self.run_book({"A": df}, {"A": pd.Series(True, index=self.cal)}, dividends=dividends)
        self.assertAlmostEqual(result.mult, 1.21)
        reinvest = result.ledger[result.ledger.reason == "dividend_reinvestment"]
        self.assertEqual(list(reinvest.date), [self.cal[3], self.cal[5]])
        self.assertEqual(list(reinvest.shares), [1.0, 1.1])
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, liquidate_at_end=False,
                              dividend_reinvestment="cash")
        cash_result = self.run_book({"A": df}, {"A": pd.Series(True, index=self.cal)},
                                    dividends=dividends, config=cfg)
        self.assertAlmostEqual(cash_result.mult, 1.2)

    def test_last_day_dividend_has_no_post_horizon_reinvestment(self):
        df = bars(self.cal, [10] * 6)
        result = self.run_book({"A": df}, {"A": pd.Series(True, index=self.cal)},
                               dividends={"A": pd.Series([1.0], index=[self.cal[-1]])})
        self.assertAlmostEqual(result.mult, 1.1)
        self.assertFalse((result.ledger.reason == "dividend_reinvestment").any())

    def test_no_picks_cash_is_present_through_every_window(self):
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, liquidate_at_end=False,
                              cash_daily_returns=pd.Series(.01, index=self.cal))
        result = simulate_portfolio({}, self.cal, [Rebalance(self.cal[1], ()), Rebalance(self.cal[3], ())],
                                    self.cal[1], self.cal[-1], config=cfg, metadata=FIXTURE_META)
        self.assertEqual(len(result.path), 5)
        self.assertEqual(len(result.window_metrics), 2)
        self.assertAlmostEqual(result.mult, 1.01 ** 5)

    def test_terminal_payout_is_actual_known_cash_not_last_close(self):
        df = bars(self.cal[:3], [10, 10, 10])
        sig = pd.Series(True, index=self.cal[:3])
        result = self.run_book({"A": df}, {"A": sig}, terminal_events=[
            {"security_id": "A", "date": self.cal[3], "cash_per_share": 2.0}])
        self.assertAlmostEqual(result.mult, .2)
        self.assertEqual(result.positions["A"], 0)
        self.assertAlmostEqual(result.metrics["max_drawdown"], -.8)

    def test_unknown_terminal_aborts_instead_of_stale_sell(self):
        df = bars(self.cal[:3], [10, 10, 10])
        with self.assertRaisesRegex(PortfolioDataError, "unknown_terminal"):
            self.run_book({"A": df}, {"A": pd.Series(True, index=df.index)})

    def test_missing_interior_bar_cannot_create_execution(self):
        df = bars(self.cal, [10] * 6).drop(self.cal[3])
        with self.assertRaisesRegex(PortfolioDataError, "missing_bar"):
            self.run_book({"A": df}, {"A": pd.Series(True, index=df.index)})
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, strict=False, liquidate_at_end=False)
        result = self.run_book({"A": df}, {"A": pd.Series(True, index=df.index)}, config=cfg)
        self.assertTrue(result.deployment_blocked)
        self.assertIn("missing_bar", result.flags)
        self.assertNotIn(self.cal[3], set(result.ledger[result.ledger.event == "sell"].date))

    def test_same_selection_does_not_sell_or_rebalance_quarterly(self):
        df = bars(self.cal, [10, 10, 12, 15, 20, 30])
        sig = pd.Series(True, index=self.cal)
        result = simulate_portfolio({"A": df}, self.cal,
                                    [Rebalance(self.cal[1], ("A",)), Rebalance(self.cal[3], ("A",))],
                                    self.cal[1], self.cal[-1], signals={"A": sig},
                                    config=self.config, metadata=FIXTURE_META)
        self.assertEqual(list(result.ledger.event), ["buy"])
        self.assertAlmostEqual(result.mult, 3)

    def test_slot_cash_not_redistributed_to_green_stock(self):
        stock_a = bars(self.cal, [10] * 6)
        stock_b = bars(self.cal, [10, 10, 20, 30, 40, 50])
        result = self.run_book({"A": stock_a, "B": stock_b},
                               {"A": pd.Series(False, index=self.cal),
                                "B": pd.Series(True, index=self.cal)})
        self.assertAlmostEqual(result.mult, 3)
        self.assertAlmostEqual(result.positions["B"], 5)

    def test_initial_capital_included_in_drawdown(self):
        metric = portfolio_metrics(pd.Series([90, 95], index=self.cal[:2]), 100,
                                   self.cal[0], self.cal[1])
        self.assertAlmostEqual(metric["max_drawdown"], -.1)

    def test_tax_loss_carries_across_selection_changes(self):
        cal = pd.DatetimeIndex(["2019-12-27", "2019-12-30", "2019-12-31", "2020-01-31", "2020-02-03"])
        a = bars(cal, [10, 10, 5, 5, 5])
        b = bars(cal, [5, 5, 5, 5, 15])
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, tax_enabled=True,
                              tax_rates=TaxRates(), liquidate_at_end=True)
        result = simulate_portfolio({"A": a, "B": b}, cal,
                                    [Rebalance(cal[1], ("A",)), Rebalance(cal[2], ("B",))],
                                    cal[1], cal[-1], signals={"A": pd.Series(True, index=cal),
                                                             "B": pd.Series(True, index=cal)}, config=cfg,
                                    metadata=FIXTURE_META)
        # A realizes -50 in 2019; B realizes +100 in 2020. Tax is on 50, not 100.
        self.assertAlmostEqual(result.tax_records.tax.sum(), 17.5)
        self.assertAlmostEqual(result.mult, 1.325)

    def test_total_adjusted_tax_refused(self):
        cfg = PortfolioConfig(strict=False, price_mode="total_return", tax_enabled=True)
        with self.assertRaisesRegex(PortfolioDataError, "dividend tax"):
            self.run_book({"A": bars(self.cal, [10] * 6)}, {"A": pd.Series(True, index=self.cal)}, config=cfg)

    def test_tax_paid_with_explicit_sale_without_rescaling_basis(self):
        cal = pd.DatetimeIndex(["2019-12-27", "2019-12-30", "2019-12-31", "2020-01-02",
                                "2020-01-31", "2020-02-03"])
        df = bars(cal, [10, 10, 20, 20, 20, 20])
        sig = pd.Series([True, False, True, True, True, True], index=cal)
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, tax_enabled=True)
        result = simulate_portfolio({"A": df}, cal, [Rebalance(cal[1], ("A",))], cal[1], cal[-1],
                                    signals={"A": sig}, config=cfg, metadata=FIXTURE_META)
        funded = result.ledger[result.ledger.reason == "tax_funding"]
        # Tax funding sale reduces actual shares; it realizes zero because the
        # remaining position was bought at 20. A scalar basis shrink is forbidden.
        actual = funded[funded.event == "sell"]
        self.assertEqual(len(actual), 1)
        self.assertAlmostEqual(actual.iloc[0].shares, 1.75)
        self.assertAlmostEqual(result.mult, 1.65)
        self.assertAlmostEqual(result.tax_records.tax.sum(), 35)

    def test_tax_scope_disclosures_do_not_block_validated_data(self):
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, tax_enabled=True)
        result = self.run_book({"A": bars(self.cal, [10] * 6)},
                               {"A": pd.Series(True, index=self.cal)}, config=cfg)
        self.assertFalse(result.deployment_blocked)
        self.assertIn("illustrative_tax_single_controlled_account_only", result.flags)

    def test_changed_selection_keeps_retained_security_lots(self):
        cal = pd.DatetimeIndex(["2019-12-27", "2019-12-30", "2021-01-04", "2021-02-01"])
        df = bars(cal, [10, 10, 15, 15])
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, tax_enabled=True)
        result = simulate_portfolio({"A": df, "B": df}, cal,
                                    [Rebalance(cal[1], ("A",)), Rebalance(cal[2], ("A", "B"))],
                                    cal[1], cal[-1], signals={"A": pd.Series(True, index=cal),
                                                             "B": pd.Series(True, index=cal)}, config=cfg,
                                    metadata=FIXTURE_META)
        a_buys = result.ledger[(result.ledger.event == "buy") & (result.ledger.security_id == "A")]
        self.assertEqual(len(a_buys), 1)
        self.assertAlmostEqual(result.tax_records.long_gain.sum(), 50)
        self.assertAlmostEqual(result.mult, 1.4)

    def test_unvalidated_manifest_refused_in_strict_mode(self):
        with self.assertRaisesRegex(PortfolioDataError, "validated complete"):
            simulate_portfolio({}, self.cal, [], self.cal[1], self.cal[-1],
                               config=self.config, metadata={"validated": False})

    def test_negative_cash_return_tax_scope_rejected_at_validation(self):
        cfg = PortfolioConfig(initial_capital=100, cost_bps=0, tax_enabled=True,
                              cash_daily_returns=pd.Series(-.01, index=self.cal))
        with self.assertRaisesRegex(PortfolioDataError, "tax-enabled cash returns must be nonnegative"):
            simulate_portfolio({}, self.cal, [], self.cal[1], self.cal[-1],
                               config=cfg, metadata=FIXTURE_META)
        cfg.tax_enabled = False
        result = simulate_portfolio({}, self.cal, [], self.cal[1], self.cal[-1],
                                    config=cfg, metadata=FIXTURE_META)
        self.assertAlmostEqual(result.mult, .99 ** 5)

    def test_declared_qlib_roundoff_tolerance_preserves_original_prices(self):
        df = bars(self.cal, [100] * 6)
        ulp = float(np.spacing(np.float32(100)))
        df.loc[self.cal[2], "high"] = 100 - ulp
        meta = dict(FIXTURE_META, validated=False, mode="exploratory", price_basis="total_return",
                    price_source="Qlib public float32 fixture", source_precision="float32", ohlc_float32_ulps=2)
        cfg = PortfolioConfig(strict=False, price_mode="total_return", initial_capital=100, cost_bps=0)
        engine = PortfolioEngine({"A": df}, self.cal, config=cfg, metadata=meta,
                                  signals={"A": pd.Series(True, index=self.cal)})
        self.assertEqual(engine.frames["A"].at[self.cal[2], "high"], 100 - ulp)
        self.assertEqual(engine.frames["A"].at[self.cal[2], "open"], 100)
        result = engine.run([Rebalance(self.cal[1], ("A",))], self.cal[1], self.cal[-1])
        self.assertTrue(result.deployment_blocked)
        self.assertIn("exploratory_qlib_float32_range_tolerance", result.blocking_flags)
        # The exact same tiny inconsistency fails a validated split-only input.
        with self.assertRaisesRegex(PortfolioDataError, "inconsistent OHLC"):
            PortfolioEngine({"A": df}, self.cal, config=self.config, metadata=FIXTURE_META)

    def test_float32_tolerance_does_not_accept_material_invalid_range(self):
        df = bars(self.cal, [100] * 6)
        df.loc[self.cal[2], "high"] = 99.9
        meta = dict(FIXTURE_META, validated=False, mode="exploratory", price_basis="total_return",
                    price_source="Qlib fixture", source_precision="float32", ohlc_float32_ulps=2)
        cfg = PortfolioConfig(strict=False, price_mode="total_return")
        with self.assertRaisesRegex(PortfolioDataError, "inconsistent OHLC"):
            PortfolioEngine({"A": df}, self.cal, config=cfg, metadata=meta)

    def test_undeclared_source_cannot_enable_float32_tolerance(self):
        df = bars(self.cal, [100] * 6)
        df.loc[self.cal[2], "high"] = 100 - float(np.spacing(np.float32(100)))
        meta = dict(FIXTURE_META, validated=False, mode="exploratory", price_basis="total_return",
                    price_source="unrelated source", source_precision="float32", ohlc_float32_ulps=2)
        cfg = PortfolioConfig(strict=False, price_mode="total_return")
        with self.assertRaisesRegex(PortfolioDataError, "inconsistent OHLC"):
            PortfolioEngine({"A": df}, self.cal, config=cfg, metadata=meta)


if __name__ == "__main__":
    unittest.main()
