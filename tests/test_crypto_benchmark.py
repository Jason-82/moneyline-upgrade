from copy import deepcopy
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from crypto_research.benchmark import (BenchmarkDataError, load_spy_benchmark,
                                       normalise_yahoo_chart, spy_buy_and_hold)


def _chart():
    seconds = [int(pd.Timestamp(date, tz="America/New_York").replace(hour=9, minute=30).timestamp())
               for date in ("2020-01-02", "2020-01-03")]
    return {"chart": {"result": [{"meta": {"symbol": "SPY", "currency": "USD",
                                              "exchangeTimezoneName": "America/New_York", "dataGranularity": "1d"},
                                  "timestamp": seconds,
                                  "events": {"dividends": {str(seconds[1]): {"date": seconds[1], "amount": 10.0}}},
                                  "indicators": {"quote": [{"open": [100.0, 90.0], "high": [100.0, 90.0], "low": [100.0, 90.0],
                                                            "close": [100.0, 90.0], "volume": [10, 10]}],
                                                 "adjclose": [{"adjclose": [90.0, 90.0]}]}}], "error": None}}


def _frame():
    return normalise_yahoo_chart(_chart(), "2020-01-01", "2020-01-03")[0]


def test_dividend_total_return_index_avoids_price_only_loss():
    frame, receipt = normalise_yahoo_chart(_chart(), "2020-01-01", "2020-01-03")
    assert frame.loc["2020-01-03", "dividend"] == 10
    assert receipt["dividend_events"] == 1
    assert receipt["after_tax_identified"] is False
    path = spy_buy_and_hold(frame, "2020-01-01", "2020-01-03", cost_bps=0)
    np.testing.assert_allclose(path, 100_000)


def test_missing_dividend_event_rejected_even_with_adjusted_close():
    payload = _chart()
    payload["chart"]["result"][0]["events"] = {}
    with pytest.raises(BenchmarkDataError, match="reconcile"):
        normalise_yahoo_chart(payload, "2020-01-01", "2020-01-03")


def test_current_quote_metadata_never_used():
    payload = _chart()
    payload["chart"]["result"][0]["meta"]["regularMarketPrice"] = 999999999
    a, _ = normalise_yahoo_chart(payload, "2020-01-01", "2020-01-03")
    pd.testing.assert_frame_equal(a, _frame())


def test_market_holiday_cash_then_session_and_weekend_marks():
    frame = _frame()
    path = spy_buy_and_hold(frame, "2020-01-01", "2020-01-05", cost_bps=100)
    assert path.loc["2020-01-01"] == 100_000
    assert path.loc["2020-01-02"] == pytest.approx(100_000 / 1.01)
    assert path.loc["2020-01-03"] == pytest.approx(100_000 / 1.01 * .99)
    assert path.loc["2020-01-04"] == path.loc["2020-01-03"]
    assert path.loc["2020-01-05"] == path.loc["2020-01-03"]
    assert path.attrs["entry_session"] == "2020-01-02"


def test_observed_january_2_holiday_not_invented_open():
    frame = _frame().copy()
    frame.index = pd.DatetimeIndex(["2023-01-03", "2023-01-04"], name="date")
    path = spy_buy_and_hold(frame, "2023-01-01", "2023-01-04", cost_bps=0)
    assert path.attrs["entry_session"] == "2023-01-03"
    assert path.loc["2023-01-02"] == 100_000


def test_missing_real_session_is_not_forward_filled():
    with pytest.raises(BenchmarkDataError, match="missing.*sessions"):
        spy_buy_and_hold(_frame().iloc[:1], "2020-01-01", "2020-01-03")


def test_extra_weekend_bar_rejected():
    frame = _frame().copy()
    extra = frame.iloc[[-1]].copy()
    extra.index = pd.DatetimeIndex(["2020-01-04"], name="date")
    with pytest.raises(BenchmarkDataError, match="non-NYSE"):
        spy_buy_and_hold(pd.concat([frame, extra]), "2020-01-01", "2020-01-05")


def test_source_wrong_symbol_currency_or_bounds_rejected():
    for field, value in (("symbol", "QQQ"), ("currency", "EUR")):
        payload = deepcopy(_chart())
        payload["chart"]["result"][0]["meta"][field] = value
        with pytest.raises(BenchmarkDataError, match="actual SPY"):
            normalise_yahoo_chart(payload, "2020-01-01", "2020-01-03")
    with pytest.raises(BenchmarkDataError, match="outside"):
        normalise_yahoo_chart(_chart(), "2020-01-02", "2020-01-02")


def test_adjusted_open_consistency_checked():
    frame = _frame()
    frame.loc["2020-01-02", "adjusted_open"] = 1
    with pytest.raises(BenchmarkDataError, match="adjusted open"):
        spy_buy_and_hold(frame, "2020-01-01", "2020-01-03")


def test_bundle_receipt_checksum_and_parser_round_trip(tmp_path):
    frame, receipt = normalise_yahoo_chart(_chart(), "2020-01-01", "2020-01-03")
    raw_bytes = frame.to_csv().encode()
    receipt["csv_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    (tmp_path / "SPY.csv").write_bytes(raw_bytes)
    (tmp_path / "manifest.json").write_text(json.dumps(receipt))
    pd.testing.assert_frame_equal(load_spy_benchmark(tmp_path), frame)
    (tmp_path / "SPY.csv").write_bytes(raw_bytes + b"\n")
    with pytest.raises(BenchmarkDataError, match="checksum"):
        load_spy_benchmark(tmp_path)


def test_mark_to_market_option_omits_terminal_cost_only():
    frame = _frame()
    path = spy_buy_and_hold(frame, "2020-01-01", "2020-01-03", cost_bps=100, liquidate_at_end=False)
    assert path.iloc[-1] == pytest.approx(100_000 / 1.01)


def test_no_session_horizon_is_cash():
    path = spy_buy_and_hold(_frame(), "2020-01-04", "2020-01-05")
    np.testing.assert_allclose(path, 100_000)
    assert path.attrs["entry_session"] is None
