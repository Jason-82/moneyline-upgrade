"""Regression checks for look-ahead, calendar, broker ingestion and research gaps."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from research.calendar import explicit_sessions
from research.data_contract import (DataContractError, MembershipSpell, ResearchDataset,
                                    SecurityRecord, TerminalEvent, audit_dataset, load_dataset, validate_dataset)
from screener.data import (from_csv_folder, from_robinhood_json, last_closed_session,
                           normalise, quality_filter, valid_ohlc_mask)
from screener.rh_ingest import ingest_file, merge_into
from screener.scan import scan


def bars(index, close=10):
    close = np.full(len(index), close, dtype=float) if np.isscalar(close) else np.asarray(close, float)
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * .99,
                         "close": close, "volume": 1000}, index=pd.DatetimeIndex(index, name="date"))


def bundle():
    cal = pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"])
    meta = {"mode": "validated", "price_basis": "split_only", "dividends_complete": True,
            "terminal_complete": True, "universe_complete": True, "point_in_time_ids": True,
            "price_source": "source fixture", "dividend_source": "source fixture",
            "corporate_action_source": "source fixture", "calendar_source": "SPY fixture"}
    return ResearchDataset({"ID1": bars(cal)}, cal,
        (SecurityRecord("ID1", "AAA", "master fixture", "known_zero"),),
        (MembershipSpell("ID1", cal[0], None, cal[0], "announcement fixture"),),
        {"ID1": pd.Series(0., index=cal)}, (), meta)


class CalendarTests(unittest.TestCase):
    def test_weekend_and_holiday_do_not_become_sessions(self):
        self.assertEqual(last_closed_session("2025-12-25 20:00"), pd.Timestamp("2025-12-24"))
        self.assertEqual(last_closed_session("2025-12-27 20:00"), pd.Timestamp("2025-12-26"))

    def test_early_close_and_settlement_buffer(self):
        self.assertEqual(last_closed_session("2025-11-28 13:19"), pd.Timestamp("2025-11-26"))
        self.assertEqual(last_closed_session("2025-11-28 13:20"), pd.Timestamp("2025-11-28"))

    def test_current_open_session_is_never_complete(self):
        self.assertEqual(last_closed_session("2026-10-13 16:19"), pd.Timestamp("2026-10-12"))
        self.assertEqual(last_closed_session("2026-10-13 16:20"), pd.Timestamp("2026-10-13"))

    def test_calendar_cannot_duplicate_sessions(self):
        with self.assertRaises(ValueError):
            explicit_sessions(["2020-01-02", "2020-01-02"])


class LoaderTests(unittest.TestCase):
    def test_optional_volume_and_dividends_survive(self):
        frame = bars(["2020-01-02"])
        frame["dividends"] = .1
        out = normalise(frame)
        self.assertEqual(out.volume.iloc[0], 1000)
        self.assertEqual(out.dividends.iloc[0], .1)

    def test_invalid_price_cannot_be_silently_dropped(self):
        for bad in (0, -1, np.nan, np.inf):
            frame = bars(["2020-01-02"])
            frame.loc[frame.index[0], "close"] = bad
            with self.assertRaises(ValueError):
                normalise(frame)

    def test_reference_ipo_price_below_low_is_rejected(self):
        frame = bars(["2021-04-14"])
        frame.loc[frame.index[0], ["open", "high", "low", "close"]] = [250, 429.54, 310, 328.28]
        with self.assertRaisesRegex(ValueError, "OHLC ordering"):
            normalise(frame)

    def test_declared_float32_roundoff_preserves_values(self):
        frame = bars(["2020-01-02"])
        frame.loc[frame.index[0], ["open", "high", "low", "close"]] = [
            float(np.nextafter(np.float32(10), np.float32(11))), 10, 9, 9.5]
        self.assertFalse(valid_ohlc_mask(frame).iloc[0])
        self.assertTrue(valid_ohlc_mask(frame, float32_ulps=2).iloc[0])
        accepted = normalise(frame, float32_ulps=2)
        pd.testing.assert_frame_equal(accepted, frame)

    def test_float32_tolerance_never_admits_material_range_error(self):
        frame = bars(["2020-01-02"])
        frame.loc[frame.index[0], ["open", "high", "low", "close"]] = [10.1, 10, 9, 9.5]
        self.assertFalse(valid_ohlc_mask(frame, float32_ulps=2).iloc[0])
        with self.assertRaises(ValueError):
            normalise(frame, float32_ulps=2)

    def test_precision_allowance_cannot_exceed_two_ulps(self):
        with self.assertRaises(ValueError):
            valid_ohlc_mask(bars(["2020-01-02"]), float32_ulps=3)

    def test_conflicting_duplicate_cannot_override_without_notice(self):
        frame = pd.concat([bars(["2020-01-02"], 10), bars(["2020-01-02"], 11)])
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            normalise(frame)

    def test_csv_forming_bar_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bars(["2026-10-12", "2026-10-13"]).to_csv(Path(tmp) / "AAA.csv")
            out = from_csv_folder(tmp, asof="2026-10-12", strict=True)
            self.assertEqual(out["AAA"].index[-1], pd.Timestamp("2026-10-12"))

    def test_entire_stale_store_is_stale(self):
        frame = bars(pd.bdate_range("2025-01-01", periods=101))
        out = scan({"AAA": frame, "BBB": frame.copy()}, asof="2026-10-12")
        self.assertTrue(out.stale.all())

    def test_future_bad_history_does_not_filter_past_universe(self):
        frame = bars(pd.bdate_range("2020-01-01", periods=12), [10] * 7 + [100, 10, 100, 10, 100])
        full_keep, _ = quality_filter({"AAA": frame})
        point_keep, _ = quality_filter({"AAA": frame}, asof=frame.index[6])
        self.assertNotIn("AAA", full_keep)
        self.assertIn("AAA", point_keep)
        self.assertEqual(len(point_keep["AAA"]), len(frame))

    def test_real_decimal_broker_schema_and_structured_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broker.json"
            path.write_text(json.dumps({"content": [{"type": "text", "text": "bad wrapper"}],
                "structuredContent": {"data": {"results": [{"symbol": "AAA", "interval": "day",
                "bounds": "regular", "bars": [{"begins_at": "2020-01-02T00:00:00Z", "open_price": "10",
                "high_price": "11", "low_price": "9", "close_price": "10.5", "volume": 123}]}]}}}))
            out = from_robinhood_json(path, require_complete=True)
            self.assertEqual(out["AAA"].volume.iloc[0], 123)
            self.assertEqual(out["AAA"].close.iloc[0], 10.5)


class IngestionTests(unittest.TestCase):
    def test_failed_parse_never_deletes_raw_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broker.json"
            path.write_text(json.dumps({"results": [{"symbol": "AAA", "interval": "hour", "bars": [{}]}]}))
            with self.assertRaises(ValueError):
                ingest_file(path, Path(tmp) / "prices", delete=True)
            self.assertTrue(path.exists())

    def test_partial_broker_response_never_deletes_raw_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broker.json"
            path.write_text(json.dumps({"data": {"not_found": ["OLD"], "results": []}}))
            with self.assertRaises(ValueError):
                ingest_file(path, Path(tmp) / "prices", delete=True)
            self.assertTrue(path.exists())

    def test_split_scale_change_requires_complete_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            merge_into(folder, "AAA", bars(["2020-01-02", "2020-01-03"], 100))
            with self.assertRaisesRegex(ValueError, "changed scale"):
                merge_into(folder, "AAA", bars(["2020-01-03", "2020-01-06"], 50))
            refreshed = bars(["2020-01-02", "2020-01-03", "2020-01-06"], 50)
            merge_into(folder, "AAA", refreshed, full_refresh=True)
            self.assertEqual(normalise(pd.read_csv(folder / "AAA.csv")).close.iloc[0], 50)

    def test_disjoint_history_cannot_append_unverified_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            merge_into(folder, "AAA", bars(["2020-01-02"]))
            with self.assertRaisesRegex(ValueError, "overlapping"):
                merge_into(folder, "AAA", bars(["2020-01-03"]))

    def test_recent_slice_cannot_replace_full_split_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            merge_into(folder, "AAA", bars(["2020-01-02", "2020-01-03"]))
            with self.assertRaisesRegex(ValueError, "entire existing history"):
                merge_into(folder, "AAA", bars(["2020-01-03"]), full_refresh=True)


class ResearchContractTests(unittest.TestCase):
    def test_certified_complete_fixture_passes(self):
        data = bundle()
        self.assertEqual(validate_dataset(data), [])
        self.assertTrue(data.metadata["validated"])

    def test_readonly_audit_preserves_qualification_state(self):
        data = bundle()
        validate_dataset(data)
        self.assertTrue(audit_dataset(data)["complete"])
        self.assertTrue(data.metadata["validated"])

    def test_total_return_prices_cannot_validate_split_only_signal(self):
        data = bundle()
        data.metadata["price_basis"] = "total_return"
        with self.assertRaisesRegex(DataContractError, "split-only"):
            validate_dataset(data)

    def test_validated_or_undeclared_precision_tolerance_is_rejected(self):
        data = bundle()
        data.metadata.update(source_precision="float32", ohlc_float32_ulps=2)
        with self.assertRaisesRegex(DataContractError, "nonzero float32"):
            validate_dataset(data)
        data.metadata.update(mode="exploratory", price_basis="total_return", source_precision="unknown")
        with self.assertRaisesRegex(DataContractError, "nonzero float32"):
            validate_dataset(data)

    def test_csv_round_trip_preserves_exact_two_ulp_boundary(self):
        data = bundle()
        data.metadata.update(mode="exploratory", price_basis="total_return",
                             source_precision="float32", ohlc_float32_ulps=2)
        frame = bars(["2022-09-06"])
        frame.loc[frame.index[0], ["open", "high", "low", "close"]] = [
            12.497833251953125, 12.896852493286133, 12.497835159301758, 12.811348915100098]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "prices").mkdir()
            (folder / "manifest.json").write_text(json.dumps(data.metadata))
            pd.DataFrame([{"security_id": "ID1", "symbol": "AAA", "source": "master",
                           "dividend_status": "known_zero"}]).to_csv(folder / "securities.csv", index=False)
            pd.DataFrame({"date": frame.index}).to_csv(folder / "calendar.csv", index=False)
            frame.to_csv(folder / "prices" / "ID1.csv")
            loaded = load_dataset(folder, mode="exploratory")
            pd.testing.assert_frame_equal(loaded.prices["ID1"], frame)

    def test_unknown_dividends_never_become_known_zero(self):
        data = bundle()
        data.securities = (SecurityRecord("ID1", "AAA", "source", "unknown"),)
        data.dividends = {}
        with self.assertRaisesRegex(DataContractError, "dividends unknown"):
            validate_dataset(data)

    def test_missing_delisted_member_prices_block_validated_run(self):
        data = bundle()
        data.prices["ID1"] = data.prices["ID1"].iloc[:1]
        with self.assertRaisesRegex(DataContractError, "missing member-session"):
            validate_dataset(data)

    def test_index_removal_cannot_substitute_for_terminal_proceeds(self):
        data = bundle()
        data.prices["ID1"] = data.prices["ID1"].iloc[:1]
        data.membership = (MembershipSpell("ID1", data.calendar[0], data.calendar[0],
                            data.calendar[0], "removal", data.calendar[0]),)
        with self.assertRaisesRegex(DataContractError, "unknown terminal"):
            validate_dataset(data)

    def test_explicit_terminal_zero_is_valid_not_last_close_sale(self):
        data = bundle()
        data.prices["ID1"] = data.prices["ID1"].iloc[:1]
        data.terminal_events = (TerminalEvent("ID1", data.calendar[1], 0., "bankruptcy source"),)
        self.assertEqual(validate_dataset(data), [])

    def test_immutable_ids_allow_recycled_symbol_separate_histories(self):
        data = bundle()
        data.securities += (SecurityRecord("ID2", "AAA", "different company", "known_zero"),)
        data.prices["ID2"] = bars(data.calendar, 50)
        data.dividends["ID2"] = pd.Series(0., index=data.calendar)
        data.membership += (MembershipSpell("ID2", data.calendar[0], None, data.calendar[0], "other membership"),)
        self.assertEqual(validate_dataset(data), [])

    def test_future_exit_announcement_cannot_change_earlier_eligibility(self):
        spell = MembershipSpell("ID1", pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03"),
                                pd.Timestamp("2020-01-02"), "announcement", pd.Timestamp("2020-01-07"))
        self.assertTrue(spell.active_at("2020-01-06"))
        self.assertFalse(spell.active_at("2020-01-07"))

    def test_exploratory_gaps_block_deployment(self):
        data = bundle()
        data.metadata.update(mode="exploratory", universe_complete=False)
        self.assertIn("universe_complete is not certified", validate_dataset(data))
        self.assertFalse(data.metadata["validated"])
        self.assertTrue(data.metadata["deployment_blocked"])

    def test_bundle_cutoff_returns_no_future_prices_or_terminal_events(self):
        data = bundle()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "prices").mkdir()
            (folder / "manifest.json").write_text(json.dumps(data.metadata))
            pd.DataFrame([{"security_id": "ID1", "symbol": "AAA", "source": "master", "dividend_status": "known_zero"}]).to_csv(folder / "securities.csv", index=False)
            pd.DataFrame([{"security_id": "ID1", "start": "2020-01-02", "end": "", "known_at": "2020-01-02", "source": "membership"}]).to_csv(folder / "membership.csv", index=False)
            pd.DataFrame({"date": data.calendar}).to_csv(folder / "calendar.csv", index=False)
            data.prices["ID1"].to_csv(folder / "prices" / "ID1.csv")
            pd.DataFrame([{"security_id": "ID1", "date": "2020-01-06", "cash_per_share": 0., "source": "terminal"}]).to_csv(folder / "terminal_events.csv", index=False)
            loaded = load_dataset(folder, mode="validated", cutoff="2020-01-03")
            self.assertEqual(loaded.calendar[-1], pd.Timestamp("2020-01-03"))
            self.assertEqual(loaded.prices["ID1"].index[-1], pd.Timestamp("2020-01-03"))
            self.assertEqual(loaded.terminal_events, ())


if __name__ == "__main__":
    unittest.main()
