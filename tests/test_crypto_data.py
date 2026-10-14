import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import pytest

from crypto_research.data import (
    CryptoDataError, load_bundle, normalise_crypto, parse_binance_zip,
    trailing_liquidity, validate_frame,
)
from scripts.acquire_crypto_data import classification, monthly_keys
from scripts.acquire_crypto_data import api_history


def candles(start="2022-12-01", days=31):
    return pd.DataFrame({"Open": 10., "High": 12., "Low": 9., "Close": 11.,
                         "Volume": 3., "QuoteVolume": 30.},
                        index=pd.date_range(start, periods=days))


def archive(date="2022-12-01", unit="ms", rows=None, name="BTCUSDT-1d-2022-12.csv"):
    timestamp = pd.Timestamp(date, tz="UTC")
    divisor = 10**6 if unit == "ms" else 10**3
    opened = timestamp.value // divisor
    closed = (timestamp + pd.Timedelta(days=1)).value // divisor - 1
    row = f"{opened},10,12,9,11,3,{closed},30,2,1,10,0\n"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zipped:
        zipped.writestr(name, row if rows is None else rows)
    return stream.getvalue()


@pytest.mark.parametrize("date,unit", [("2022-12-01", "ms"), ("2025-01-01", "us")])
def test_binance_archive_timestamp_change(date, unit):
    raw = archive(date, unit)
    result = parse_binance_zip(raw, expected_sha256=hashlib.sha256(raw).hexdigest(), expected_symbol="BTCUSDT")
    assert result.index.tolist() == [pd.Timestamp(date)]
    assert result.Close.iloc[0] == 11
    assert result.QuoteVolume.iloc[0] == 30


def test_archive_checksum_and_symbol_fail_closed():
    raw = archive()
    with pytest.raises(CryptoDataError, match="checksum"):
        parse_binance_zip(raw, expected_sha256="0" * 64)
    with pytest.raises(CryptoDataError, match="symbol"):
        parse_binance_zip(raw, expected_symbol="ETHUSDT")


def test_archive_rejects_extra_member_and_wrong_duration():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zipped:
        zipped.writestr("a.csv", "1,2")
        zipped.writestr("b.csv", "1,2")
    with pytest.raises(CryptoDataError, match="one CSV"):
        parse_binance_zip(stream.getvalue())
    raw = archive(rows="1669852800000,10,12,9,11,3,1669852800000,30,2,1,10,0\n")
    with pytest.raises(CryptoDataError, match="close"):
        parse_binance_zip(raw)


def test_partial_exchange_day_is_quarantined_not_manufactured():
    rows = ("1669852800000,10,12,9,11,3,1669939199999,30,2,1,10,0\n"
            "1669939200000,10,12,9,11,3,1669957200000,30,2,1,10,0\n")
    result = parse_binance_zip(archive(rows=rows), partial_bar_policy="drop")
    assert result.index.tolist() == [pd.Timestamp("2022-12-01")]
    assert result.attrs["excluded_partial_daily_dates"] == ["2022-12-02"]


def test_api_applies_same_partial_day_quarantine(monkeypatch, tmp_path):
    rows = [[1669852800000, "10", "12", "9", "11", "3", 1669939199999, "30", 2, "1", "10", "0"],
            [1669939200000, "10", "12", "9", "11", "3", 1669957200000, "30", 2, "1", "10", "0"]]
    monkeypatch.setattr("scripts.acquire_crypto_data.get", lambda url: json.dumps(rows).encode())
    frame, receipts = api_history("BTCUSDT", pd.Timestamp("2022-12-01"), pd.Timestamp("2022-12-02"), tmp_path)
    assert frame.index.tolist() == [pd.Timestamp("2022-12-01")]
    assert receipts[0]["excluded_partial_daily_dates"] == ["2022-12-02"]


def test_api_rejects_long_or_negative_duration(monkeypatch, tmp_path):
    row = [1669852800000, "10", "12", "9", "11", "3", 1669939200000, "30", 2, "1", "10", "0"]
    monkeypatch.setattr("scripts.acquire_crypto_data.get", lambda url: json.dumps([row]).encode())
    with pytest.raises(CryptoDataError, match="duration"):
        api_history("BTCUSDT", pd.Timestamp("2022-12-01"), pd.Timestamp("2022-12-02"), tmp_path)


@pytest.mark.parametrize("column,value", [("High", 8), ("Low", 13), ("Close", 0), ("QuoteVolume", -1), ("Open", np.nan)])
def test_exact_candles_reject_invalid_values(column, value):
    frame = candles(days=2)
    frame.loc[frame.index[0], column] = value
    with pytest.raises(CryptoDataError):
        normalise_crypto(frame)


def test_candle_dates_must_be_unique_ordered_midnight():
    frame = candles(days=2)
    with pytest.raises(CryptoDataError, match="increasing"):
        normalise_crypto(frame.iloc[::-1])
    with pytest.raises(CryptoDataError, match="unique"):
        normalise_crypto(pd.concat([frame, frame.iloc[-1:]]))
    frame.index += pd.Timedelta(hours=1)
    with pytest.raises(CryptoDataError, match="midnight"):
        normalise_crypto(frame)


def test_liquidity_observation_does_not_read_future_or_impute_missing():
    frame = candles()
    baseline = trailing_liquidity(frame, "2022-12-31", days=30)
    future = candles("2023-01-01", days=30)
    future.QuoteVolume = 1e20
    assert trailing_liquidity(pd.concat([frame, future]), "2022-12-31", days=30) == baseline == 30
    assert trailing_liquidity(frame.drop(frame.index[10:13]), "2022-12-31", days=30) is None
    assert len(validate_frame(frame.drop(frame.index[10:13]))) == 28


def test_static_classification_does_not_suffix_match_jup():
    assert classification("BUSDUSDT") == "stable_or_fiat"
    assert classification("WBTCUSDT") == "wrapped_or_staked_duplicate"
    assert classification("BTCUPUSDT") == "leveraged_token"
    assert classification("JUPUSDT") is None
    assert classification("LUNAUSDT") is None


def test_catalog_only_1d_zips_not_checksums_or_future_other_interval():
    record = {"keys": ["data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2022-12.zip",
                       "data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2022-12.zip.CHECKSUM",
                       "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2022-12.zip"]}
    assert monthly_keys(record, "BTCUSDT") == {"2022-12": record["keys"][0]}


def test_bundle_preserves_gap_reports_missing_history_and_validates_sha(tmp_path):
    (tmp_path / "prices").mkdir()
    frame = validate_frame(candles(days=3).drop(pd.Timestamp("2022-12-02")))
    destination = tmp_path / "prices" / "BTCUSDT.csv"
    frame.to_csv(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest = {"securities": [{"symbol": "BTCUSDT", "price_sha256": digest}, {"symbol": "OLDUSDT"}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    pd.DataFrame([{"formation_date": "2022-12-31", "symbol": "BTCUSDT", "group": "liquid_top20", "rank": 1}]).to_csv(tmp_path / "universe.csv", index=False)
    dataset = load_bundle(tmp_path)
    assert list(dataset.prices["BTCUSDT"].columns) == ["open", "high", "low", "close", "volume", "quote_volume"]
    assert len(dataset.prices["BTCUSDT"]) == 2
    assert len(dataset.calendar) == 3
    assert any("interior missing" in flag for flag in dataset.quality_flags)
    assert any("OLDUSDT" in flag for flag in dataset.quality_flags)
    destination.write_text(destination.read_text().replace("11.0", "10.9"))
    with pytest.raises(CryptoDataError, match="checksum"):
        load_bundle(tmp_path)


def test_api_decimal_string_normalisation_matches_round_trip_csv():
    # A decimal parsed by pandas.to_numeric historically differs by one ULP.
    text = "0.022680820000000001"
    frame = candles(days=1).astype(str)
    frame["QuoteVolume"] = text
    assert normalise_crypto(frame).QuoteVolume.iloc[0] == float(text)


def test_bundle_rejects_parent_traversal(tmp_path):
    manifest = {"securities": [{"symbol": "BTCUSDT", "price_file": "../outside.csv"}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(CryptoDataError, match="inside"):
        load_bundle(tmp_path)


def test_failed_reacquisition_never_reuses_stale_export(tmp_path):
    (tmp_path / "prices").mkdir()
    validate_frame(candles()).to_csv(tmp_path / "prices/BTCUSDT.csv")
    (tmp_path / "manifest.json").write_text(json.dumps({"securities": [{"symbol": "BTCUSDT", "history_missing": True}]}))
    pd.DataFrame([{"formation_date": "2022-12-31", "symbol": "BTCUSDT", "group": "liquid_top20", "rank": 1}]).to_csv(tmp_path / "universe.csv", index=False)
    dataset = load_bundle(tmp_path)
    assert "BTCUSDT" not in dataset.prices
    assert dataset.universe.symbol.tolist() == ["BTCUSDT"]
    assert any("failed acquisition" in flag for flag in dataset.quality_flags)
