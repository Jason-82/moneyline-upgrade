"""Financial state-machine tests: no network, account reads, broker proposals or orders."""
from __future__ import annotations

import copy
from datetime import timedelta
import tempfile
from pathlib import Path
import unittest

from trading.calendar import SavedCalendar
from trading.common import TradingError, digest, iso, read_json, stamp
from trading.enforcement import authorize, check_payload_against_plan, normalize_tool_name
from trading.fixtures import create_demo
from trading.journal import Journal, run_lock
from trading.planner import freeze_manifest, make_plan, validate_manifest, validate_plan
from trading.robinhood_adapter import EquityOrderRequest, Quote, RobinhoodReadAdapter, approval_requirement, normalise_historical_bars
from trading.shadow import execute_shadow
from trading.signals import compute_signals


class StockExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master_temp = tempfile.TemporaryDirectory()
        cls.master = create_demo(cls.master_temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.master_temp.cleanup()

    def setUp(self):
        bundle = copy.deepcopy(self.master)
        self.config, self.manifest, self.inputs = bundle["config"], bundle["manifest"], bundle["inputs"]
        self.now = self.inputs["now"]
        self.calendar = SavedCalendar(self.inputs["calendar"]["sessions"])
        self.signals = compute_signals(self.inputs["market_data"], self.calendar, self.now, self.manifest["symbols"])
        self.plan = make_plan(self.config, self.manifest, self.signals, self.inputs["snapshot"], self.calendar, self.now)
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.journal = Journal(self.folder / "journal.sqlite3")

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def observed(self, order=None, *, filled="5", state="partially_filled", price="40", fee="0"):
        row = order or self.plan["orders"][0]
        return {**row, "id": "known-shadow-order", "cumulative_quantity": filled,
                "state": state, "average_price": price if filled != "0" else None,
                "fees": fee, "trigger": "immediate", "executions": []}

    def request(self, operation="place_equity_order"):
        return {"tool_name": "mcp__connector__robinhood_" + operation,
                "plan_sha256": self.plan["plan_sha256"], "asof": self.plan["asof"],
                "arguments": copy.deepcopy(self.plan["orders"][0])}

    def test_closed_bar_signal_and_equal_slots(self):
        self.assertEqual(self.signals["asof"], "2024-07-23")
        self.assertTrue(all(row["green"] for row in self.signals["signals"].values()))
        self.assertEqual(set(self.plan["slot_cash"].values()), {"10000"})
        self.assertEqual(len(self.plan["orders"]), 3)
        self.assertEqual(self.plan["expires_at"], self.plan["scheduled_open"])

    def test_weekend_and_early_close_calendar(self):
        cal = SavedCalendar.from_exchange("2024-07-01", "2024-07-08")
        self.assertEqual(cal.latest_completed("2024-07-04T01:00:00Z").date, "2024-07-03")
        self.assertEqual(cal.next_session("2024-07-03").date, "2024-07-05")
        self.assertEqual(cal.latest_completed("2024-07-06T18:00:00Z").date, "2024-07-05")

    def test_supplied_calendar_cannot_invent_or_hide_sessions(self):
        with self.assertRaises(TradingError):
            SavedCalendar([{"date": "2026-10-10", "open": "2026-10-10T13:30:00Z", "close": "2026-10-10T20:00:00Z"},
                           {"date": "2026-10-11", "open": "2026-10-11T13:30:00Z", "close": "2026-10-11T20:00:00Z"}])
        records = copy.deepcopy(self.inputs["calendar"]["sessions"])
        records.pop(20)
        with self.assertRaises(TradingError):
            SavedCalendar(records)
        records = copy.deepcopy(self.inputs["calendar"]["sessions"])
        records[20]["open"] = iso(stamp(records[20]["open"]) + timedelta(minutes=1))
        with self.assertRaises(TradingError):
            SavedCalendar(records)

    def test_incomplete_or_missing_history_fails_closed(self):
        ticker = self.manifest["symbols"][0]
        self.inputs["market_data"]["bars"][ticker].pop(-2)
        with self.assertRaises(TradingError):
            compute_signals(self.inputs["market_data"], self.calendar, self.now, self.manifest["symbols"])

    def test_forming_or_future_bar_rejected(self):
        ticker = self.manifest["symbols"][0]
        row = copy.deepcopy(self.inputs["market_data"]["bars"][ticker][-1])
        row["date"] = self.calendar.next_session(self.plan["asof"]).date
        self.inputs["market_data"]["bars"][ticker].append(row)
        with self.assertRaises(TradingError):
            compute_signals(self.inputs["market_data"], self.calendar, self.now, self.manifest["symbols"])

    def test_dividend_adjusted_signal_rejected(self):
        self.inputs["market_data"]["adjustment_type"] = "all"
        with self.assertRaises(TradingError):
            compute_signals(self.inputs["market_data"], self.calendar, self.now, self.manifest["symbols"])

    def test_official_close_stale_or_interpolated_rejected(self):
        self.inputs["market_data"]["official_closes"]["DEMOA"]["interpolated"] = True
        with self.assertRaises(TradingError):
            compute_signals(self.inputs["market_data"], self.calendar, self.now, self.manifest["symbols"])

    def test_old_truncated_calendar_rejected(self):
        truncated = SavedCalendar(self.inputs["calendar"]["sessions"][:141])
        with self.assertRaises(TradingError):
            truncated.latest_completed("2024-08-01T22:00:00Z")

    def test_manifest_tampering_or_unvalidated_live_rejected(self):
        self.manifest["symbols"].append("SPY")
        with self.assertRaises(TradingError):
            validate_manifest(self.manifest)
        with self.assertRaises(TradingError):
            validate_manifest(self.master["manifest"], live=True)

    def test_empty_shadow_whitelist_allowed(self):
        manifest = freeze_manifest({**self.manifest, "symbols": []})
        signals = compute_signals(self.inputs["market_data"], self.calendar, self.now, [])
        config = {**self.config, "budget_usd": None}
        plan = make_plan(config, manifest, signals, self.inputs["snapshot"], self.calendar, self.now)
        self.assertEqual(plan["orders"], [])

    def test_no_budget_or_account_inference(self):
        for field in ["account_number", "budget_usd"]:
            config = {**self.config, field: None}
            with self.assertRaises(TradingError):
                make_plan(config, self.manifest, self.signals, self.inputs["snapshot"], self.calendar, self.now)

    def test_cold_start_waits_when_configured(self):
        config = {**self.config, "cold_start": "wait_for_next_green_flip"}
        plan = make_plan(config, self.manifest, self.signals, self.inputs["snapshot"], self.calendar, self.now)
        self.assertEqual(plan["orders"], [])

    def test_buying_power_limits_buys_without_redistributing(self):
        snapshot = {**self.inputs["snapshot"], "buying_power": "2000", "unleveraged_buying_power": "2000"}
        plan = make_plan(self.config, self.manifest, self.signals, snapshot, self.calendar, self.now)
        self.assertEqual(len(plan["orders"]), 1)
        self.assertLess(int(plan["orders"][0]["quantity"]), int(self.plan["orders"][0]["quantity"]))

    def test_reserves_sell_orders_and_pending_proposals_once(self):
        snapshot = {**self.inputs["snapshot"], "cold_start": False,
                    "slot_cash": {name: "1000" for name in self.manifest["symbols"]},
                    "strategy_inventory": {name: "10" for name in self.manifest["symbols"]},
                    "positions": [{"symbol": name, "quantity": "10", "shares_available_for_sells": "7", "type": "long"} for name in self.manifest["symbols"]],
                    "orders": [{"symbol": "DEMOA", "side": "sell", "state": "partially_filled", "quantity": "4", "cumulative_quantity": "1"}],
                    "approvals": [{"symbol": "DEMOA", "side": "sell", "state": "pending", "quantity": "2"}]}
        for state in self.signals["signals"].values():
            state["green"], state["flip"] = False, -1
        plan = make_plan(self.config, self.manifest, self.signals, snapshot, self.calendar, self.now)
        sell = next(row for row in plan["orders"] if row["symbol"] == "DEMOA")
        self.assertEqual(sell["quantity"], "5")  # 10 - broker-held 3 - approval-held 2, not 10 - 3 twice.

    def test_unresolved_intent_blocks_symbol(self):
        snapshot = {**self.inputs["snapshot"], "unresolved_symbols": ["DEMOA"]}
        plan = make_plan(self.config, self.manifest, self.signals, snapshot, self.calendar, self.now)
        self.assertNotIn("DEMOA", [row["symbol"] for row in plan["orders"]])

    def test_retry_ref_is_stable(self):
        again = make_plan(self.config, self.manifest, self.signals, self.inputs["snapshot"], self.calendar, self.now)
        self.assertEqual(again["orders"], self.plan["orders"])

    def test_intent_is_committed_before_unknown_transport_outcome(self):
        self.journal.prepare(self.plan, self.now)
        ref = self.plan["orders"][0]["ref_id"]
        self.journal.begin_attempt(ref)
        self.assertEqual(self.journal.get(ref)["state"], "UNKNOWN")
        with self.assertRaises(TradingError):
            self.journal.begin_attempt(ref)
        self.journal.reconcile(self.config["account_number"], [self.observed()])
        self.assertEqual(self.journal.get(ref)["filled"], "5")

    def test_partial_fills_reconcile_once_and_terminal_remainder(self):
        self.journal.prepare(self.plan, self.now)
        ref = self.plan["orders"][0]["ref_id"]
        self.journal.begin_attempt(ref)
        observed = self.observed()
        self.journal.reconcile(self.config["account_number"], [observed])
        self.journal.reconcile(self.config["account_number"], [observed])
        ledger = self.journal.ledger(self.config["account_number"])
        self.assertEqual(ledger["strategy_inventory"]["DEMOA"], "5")
        self.assertEqual(ledger["slot_cash"]["DEMOA"], "9800")
        self.journal.reconcile(self.config["account_number"], [self.observed(filled="8", state="partially_filled_rest_cancelled", fee="0.03")])
        ledger = self.journal.ledger(self.config["account_number"])
        self.assertEqual(ledger["strategy_inventory"]["DEMOA"], "8")
        self.assertEqual(ledger["slot_cash"]["DEMOA"], "9679.97")

    def test_nonmonotonic_or_foreign_fill_fails_and_rolls_back(self):
        self.journal.prepare(self.plan, self.now)
        self.journal.begin_attempt(self.plan["orders"][0]["ref_id"])
        self.journal.reconcile(self.config["account_number"], [self.observed()])
        with self.assertRaises(TradingError):
            self.journal.reconcile(self.config["account_number"], [self.observed(filled="4")])
        with self.assertRaises(TradingError):
            self.journal.reconcile("OTHER_ACCOUNT", [self.observed()])
        self.assertEqual(self.journal.ledger(self.config["account_number"])["strategy_inventory"]["DEMOA"], "5")

    def test_broker_id_collision_fails_closed(self):
        self.journal.prepare(self.plan, self.now)
        self.journal.begin_attempt(self.plan["orders"][0]["ref_id"])
        self.journal.reconcile(self.config["account_number"], [self.observed()])
        different = {**self.observed(), "id": "ANOTHER_BROKER_ID"}
        with self.assertRaises(TradingError):
            self.journal.reconcile(self.config["account_number"], [different])

    def test_sell_partial_fill_updates_inventory_proceeds_and_fees_once(self):
        snapshot = {**self.inputs["snapshot"], "cold_start": False,
                    "slot_cash": {name: "1000" for name in self.manifest["symbols"]},
                    "strategy_inventory": {name: "10" for name in self.manifest["symbols"]},
                    "positions": [{"symbol": name, "quantity": "10", "shares_available_for_sells": "10", "type": "long"} for name in self.manifest["symbols"]]}
        for state in self.signals["signals"].values():
            state["green"], state["flip"] = False, -1
        plan = make_plan(self.config, self.manifest, self.signals, snapshot, self.calendar, self.now)
        self.journal.prepare(plan, self.now)
        order = plan["orders"][0]
        self.journal.begin_attempt(order["ref_id"])
        observed = self.observed(order, filled="3", fee="0.05")
        self.journal.reconcile(self.config["account_number"], [observed])
        self.journal.reconcile(self.config["account_number"], [observed])
        ledger = self.journal.ledger(self.config["account_number"])
        self.assertEqual(ledger["strategy_inventory"]["DEMOA"], "7")
        self.assertEqual(ledger["slot_cash"]["DEMOA"], "1119.95")

    def test_shadow_replay_does_not_duplicate_fills(self):
        first = execute_shadow(self.plan, self.inputs["fills"], self.journal, self.now, self.folder / "STOP")
        second = execute_shadow(self.plan, self.inputs["fills"], self.journal, self.now, self.folder / "STOP")
        self.assertEqual(first["strategy_inventory"], second["strategy_inventory"])
        self.assertEqual(second["observations"], [])

    def test_gap_exceeding_slot_cash_is_rejected(self):
        self.inputs["fills"]["open_prices"]["DEMOA"] = "1000"
        result = execute_shadow(self.plan, self.inputs["fills"], self.journal, self.now, self.folder / "STOP")
        self.assertEqual(result["observations"][0]["state"], "rejected")
        self.assertEqual(result["strategy_inventory"]["DEMOA"], "0")

    def test_plan_and_fill_must_not_be_late(self):
        with self.assertRaises(TradingError):
            self.journal.prepare(self.plan, self.plan["expires_at"])
        self.inputs["fills"]["timestamp"] = iso(stamp(self.plan["scheduled_open"]) + timedelta(seconds=1))
        with self.assertRaises(TradingError):
            execute_shadow(self.plan, self.inputs["fills"], self.journal, self.now, self.folder / "STOP")

    def test_exact_payload_hash_date_and_parameters_enforced(self):
        request = self.request()
        self.assertEqual(check_payload_against_plan(self.plan, request, self.now), request["arguments"])
        for change in [{"quantity": "1"}, {"symbol": "SPY"}, {"market_hours": "extended_hours"}, {"dollar_amount": "100"}, {"account_number": "OTHER"}]:
            bad = copy.deepcopy(request)
            bad["arguments"].update(change)
            with self.assertRaises(TradingError):
                check_payload_against_plan(self.plan, bad, self.now)
        request["asof"] = "1999-01-01"
        with self.assertRaises(TradingError):
            check_payload_against_plan(self.plan, request, self.now)

    def test_live_disabled_even_with_synthetic_pass_and_config(self):
        config = {**self.config, "mode": "LIVE"}
        manifest = freeze_manifest({**self.manifest, "research_verdict": {"status": "PASS", "report_sha256": "a" * 64, "limitations": []}})
        self.plan["manifest_sha256"] = manifest["manifest_sha256"]
        self.plan.pop("plan_sha256")
        self.plan["plan_sha256"] = digest(self.plan)
        with self.assertRaisesRegex(TradingError, "shadow-only"):
            authorize(self.request(), config, self.plan, manifest, self.journal, self.now, self.folder / "STOP")
        with self.assertRaises(TradingError):
            make_plan(config, manifest, self.signals, self.inputs["snapshot"], self.calendar, self.now)

    def test_stop_blocks_new_work_but_allows_only_owned_cancel(self):
        self.journal.prepare(self.plan, self.now)
        ref = self.plan["orders"][0]["ref_id"]
        self.journal.begin_attempt(ref)
        self.journal.acknowledge(ref, broker_id="OWNED")
        (self.folder / "STOP").touch()
        with self.assertRaises(TradingError):
            execute_shadow(self.plan, self.inputs["fills"], self.journal, self.now, self.folder / "STOP")
        request = {"tool_name": "robinhood.cancel_equity_order", "arguments": {"account_number": self.config["account_number"], "order_id": "OWNED"}}
        self.assertTrue(authorize(request, self.config, self.plan, self.manifest, self.journal, self.plan["expires_at"], self.folder / "STOP")["allowed"])
        request["arguments"]["order_id"] = "FOREIGN"
        with self.assertRaises(TradingError):
            authorize(request, self.config, self.plan, self.manifest, self.journal, self.now, self.folder / "STOP")

    def test_pending_approval_does_not_count_as_filled(self):
        self.journal.prepare(self.plan, self.now)
        ref = self.plan["orders"][0]["ref_id"]
        self.journal.begin_attempt(ref)
        self.journal.acknowledge(ref, approval_id="APPROVAL")
        self.journal.reconcile(self.config["account_number"], [], [{"approval_id": "APPROVAL", "state": "approved"}])
        self.assertEqual(self.journal.ledger(self.config["account_number"])["strategy_inventory"]["DEMOA"], "0")
        observed = {**self.observed(), "ref_id": "APPROVAL"}
        self.journal.reconcile(self.config["account_number"], [observed], [{"approval_id": "APPROVAL", "state": "approved"}])
        self.assertEqual(self.journal.get(ref)["state"], "partially_filled")

    def test_single_run_lock(self):
        with run_lock(self.folder):
            with self.assertRaises(TradingError):
                with run_lock(self.folder):
                    pass

    def test_read_adapter_no_default_transport_or_place(self):
        adapter = RobinhoodReadAdapter()
        with self.assertRaises(TradingError):
            adapter.accounts()
        self.assertFalse(hasattr(adapter, "place"))
        parameters = EquityOrderRequest("SHADOW", "SPY", "buy", "3", ref_id="REF").parameters(review=True)
        self.assertNotIn("ref_id", parameters)
        self.assertEqual(parameters["type"], "market")

    def test_adapter_pagination_uses_opaque_cursor(self):
        calls = []
        row = {"symbol": "SPY", "quantity": "3", "shares_available_for_sells": "3", "shares_held_for_sells": "0", "type": "long"}
        def transport(name, parameters):
            calls.append(parameters)
            return {"structuredContent": {"data": {"positions": [row], "next": "opaque" if len(calls) == 1 else ""}}}
        adapter = RobinhoodReadAdapter(transport)
        self.assertEqual(len(adapter.positions("SHADOW")), 2)
        self.assertEqual(calls[1]["cursor"], "opaque")

    def historical_transport(self, name, parameters):
        records = []
        for ticker in parameters["symbols"]:
            records.append({"symbol": ticker, "interval": "day", "bounds": "regular", "bars": [
                {"begins_at": row["date"] + "T00:00:00Z", "open_price": str(row["open"]), "high_price": str(row["high"]),
                 "low_price": str(row["low"]), "close_price": str(row["close"]), "volume": 1000, "session": "reg"}
                for row in self.inputs["market_data"]["bars"]["DEMOA"]]})
        return {"structuredContent": {"data": {"results": records}}, "content": [{"type": "text", "text": "raw response preserved"}]}

    def fetch_history(self, adapter=None, symbols=None):
        adapter = adapter or RobinhoodReadAdapter(self.historical_transport)
        return adapter.historicals(symbols or ["DEMOA"], start_time="2024-01-02T00:00:00Z", end_time="2024-07-24T00:00:00Z")

    def test_historical_requests_pin_explicit_policy_and_chunk_at_ten(self):
        calls = []
        def transport(name, parameters):
            calls.append((name, parameters))
            return self.historical_transport(name, parameters)
        adapter = RobinhoodReadAdapter(transport)
        history = self.fetch_history(adapter, ["S" + str(i) for i in range(23)])
        self.assertEqual([len(args["symbols"]) for _, args in calls], [10, 10, 3])
        self.assertTrue(all(args["adjustment_type"] == "split" and args["interval"] == "day" and args["bounds"] == "regular" for _, args in calls))
        self.assertEqual(history.raw_responses[0]["content"][0]["text"], "raw response preserved")
        self.assertEqual(len(normalise_historical_bars(history)), 23)
        with self.assertRaises(TradingError):
            adapter.historicals(["SPY"], start_time="2024-01-01", end_time="2024-02-01T00:00:00Z")

    def test_raw_null_or_interpolated_bars_retained_then_rejected(self):
        history = self.fetch_history()
        bars = history.raw_responses[0]["structuredContent"]["data"]["results"][0]["bars"]
        bars[10] = None
        self.assertIsNone(history.saved()["raw_responses"][0]["structuredContent"]["data"]["results"][0]["bars"][10])
        with self.assertRaises(TradingError):
            normalise_historical_bars(history)
        history = self.fetch_history()
        history.raw_responses[0]["structuredContent"]["data"]["results"][0]["bars"][10]["interpolated"] = True
        with self.assertRaises(TradingError):
            normalise_historical_bars(history)

    def test_saved_signal_normalization_preserves_prices_and_rejects_official_close_mismatch(self):
        adapter = RobinhoodReadAdapter(self.historical_transport)
        history = self.fetch_history(adapter)
        official = copy.deepcopy(self.inputs["market_data"]["official_closes"]["DEMOA"])
        quotes = [Quote("DEMOA", {"symbol": "DEMOA"}, official)]
        market = adapter.saved_signal_data(history, quotes, self.calendar, self.now)
        self.assertEqual(market["bars"]["DEMOA"][-1]["close"], str(self.inputs["market_data"]["bars"]["DEMOA"][-1]["close"]))
        quotes[0].official_close["price"] = "999"
        with self.assertRaises(TradingError):
            adapter.saved_signal_data(history, quotes, self.calendar, self.now)
        self.assertEqual(history.raw_responses[0]["structuredContent"]["data"]["results"][0]["bars"][-1]["close_price"], str(self.inputs["market_data"]["bars"]["DEMOA"][-1]["close"]))

    def test_historical_wrong_bounds_or_not_found_rejected(self):
        history = self.fetch_history()
        history.raw_responses[0]["structuredContent"]["data"]["results"][0]["bounds"] = "extended"
        with self.assertRaises(TradingError):
            normalise_historical_bars(history)
        history = self.fetch_history()
        history.raw_responses[0]["structuredContent"]["data"]["not_found"] = ["DEMOA"]
        with self.assertRaises(TradingError):
            normalise_historical_bars(history)

    def test_trade_approval_setting_is_read_only_current_and_account_matched(self):
        calls = []
        def transport(name, parameters):
            calls.append((name, parameters))
            return {"structuredContent": {"data": {"setting": {"account_number": parameters["account_number"], "human_must_approve_trades": True, "updated_at": "2024-07-23T20:00:00Z"}}}}
        adapter = RobinhoodReadAdapter(transport)
        result = adapter.trade_approval_setting("SHADOW")
        self.assertTrue(result.human_must_approve_trades)
        self.assertEqual(calls[0][0], "mcp__codex_apps__robinhood_get_trade_approval_setting")
        self.assertFalse(hasattr(adapter, "set_trade_approval_setting"))

    def test_current_preview_approval_policy(self):
        self.assertEqual(approval_requirement({"order_checks": {}, "customer_approval_required": True}), "CUSTOMER_APPROVAL_IN_ROBINHOOD_APP")
        self.assertIn("BROKER_ALERTS", approval_requirement({"order_checks": {"alert_type": "EXAMPLE"}, "customer_approval_required": True}))
        self.assertIn("EXPLICIT_CONFIRMATION", approval_requirement({"order_checks": {}, "customer_approval_required": False}))

    def test_tool_normalization_rejects_unrelated_operation(self):
        self.assertEqual(normalize_tool_name("mcp__connector123__robinhood_place_equity_order"), "place_equity_order")
        with self.assertRaises(TradingError):
            normalize_tool_name("robinhood_place_option_order")


if __name__ == "__main__":
    unittest.main()
