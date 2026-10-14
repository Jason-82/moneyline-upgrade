"""Unadjusted, UTC spot candles and auditable venue-only crypto history.

This is deliberately not a stock ResearchDataset: crypto trades every UTC day,
quote volume is measured in USDT, and a vanished exchange listing is not a cash
realization.  No price, volume or terminal proceeds are forward filled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd


COLUMNS = ("Open", "High", "Low", "Close", "Volume", "QuoteVolume")
BINANCE_COLUMNS = ("open_time", "Open", "High", "Low", "Close", "Volume",
                   "close_time", "QuoteVolume", "trades", "taker_base",
                   "taker_quote", "ignore")


class CryptoDataError(ValueError):
    pass


@dataclass
class CryptoDataset:
    prices: dict[str, pd.DataFrame]
    metadata: dict = field(default_factory=dict)
    universe: pd.DataFrame = field(default_factory=pd.DataFrame)
    quality_flags: list[str] = field(default_factory=list)

    @property
    def calendar(self) -> pd.DatetimeIndex:
        if not self.prices:
            return pd.DatetimeIndex([])
        start = min(x.index.min() for x in self.prices.values())
        end = max(x.index.max() for x in self.prices.values())
        return pd.date_range(start, end, freq="D", name="Date")


def normalise_crypto(frame: pd.DataFrame) -> pd.DataFrame:
    """Reject malformed source values; preserve absent days as absent days."""
    result = frame.copy()
    result = result.rename(columns={"date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume", "quote_volume": "QuoteVolume"})
    if "Date" in result.columns:
        result = result.set_index("Date")
    if not isinstance(result.index, pd.DatetimeIndex):
        result.index = pd.to_datetime(result.index, errors="raise")
    if result.index.tz is not None:
        result.index = result.index.tz_convert("UTC").tz_localize(None)
    if result.index.hasnans or result.index.has_duplicates:
        raise CryptoDataError("crypto candle dates must be unique and finite")
    if not result.index.equals(result.index.normalize()):
        raise CryptoDataError("daily candle open must be midnight UTC")
    if not result.index.is_monotonic_increasing:
        raise CryptoDataError("crypto candle dates must be increasing")
    missing = set(COLUMNS) - set(result.columns)
    if missing:
        raise CryptoDataError(f"missing columns: {sorted(missing)}")
    for column in COLUMNS:
        # Python's correctly rounded decimal -> binary conversion matches the
        # round_trip archive CSV parser. pd.to_numeric's string parser can differ
        # by one ULP and would make exact API/archive verification misleading.
        if result[column].dtype == object:
            result[column] = result[column].map(float)
        else:
            result[column] = pd.to_numeric(result[column], errors="raise")
    values = result.loc[:, COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise CryptoDataError("crypto candles contain nonfinite values")
    prices = result.loc[:, ("Open", "High", "Low", "Close")]
    if (prices <= 0).any().any():
        raise CryptoDataError("crypto OHLC must be positive")
    if ((result.High < result[["Open", "Low", "Close"]].max(axis=1)) |
        (result.Low > result[["Open", "High", "Close"]].min(axis=1))).any():
        raise CryptoDataError("invalid crypto OHLC range")
    if (result.loc[:, ("Volume", "QuoteVolume")] < 0).any().any():
        raise CryptoDataError("negative crypto volume")
    result.index.name = "Date"
    return result


def parse_binance_zip(raw: bytes, *, expected_sha256: str | None = None,
                      expected_symbol: str | None = None,
                      partial_bar_policy: str = "reject") -> pd.DataFrame:
    if partial_bar_policy not in ("reject", "drop"):
        raise CryptoDataError("partial_bar_policy must be reject or drop")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise CryptoDataError("Binance archive checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = [x for x in archive.namelist() if not x.endswith("/")]
        if len(files) != 1 or not files[0].endswith(".csv"):
            raise CryptoDataError("monthly archive must contain one CSV")
        if expected_symbol is not None and not Path(files[0]).name.startswith(expected_symbol + "-1d-"):
            raise CryptoDataError("archive symbol does not match requested symbol")
        frame = pd.read_csv(archive.open(files[0]), header=None, float_precision="round_trip")
    if frame.shape[1] != len(BINANCE_COLUMNS):
        raise CryptoDataError("Binance kline archive must have 12 columns")
    frame.columns = BINANCE_COLUMNS
    # A small number of archives carry a literal header; recognize only that exact
    # schema rather than dropping an arbitrary invalid first record.
    if len(frame) and str(frame.iloc[0, 0]) in ("open_time", "Open time"):
        frame = frame.iloc[1:].copy()
    for col in ("open_time", "close_time"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if not np.isfinite(frame[col]).all() or (frame[col] % 1 != 0).any():
            raise CryptoDataError("invalid Binance integer timestamp")
    if frame.empty:
        raise CryptoDataError("empty Binance monthly archive")
    # Official spot archive changed milliseconds -> microseconds on 2025-01-01.
    units = np.where(frame.open_time.to_numpy() >= 10**14, "us", "ms")
    dates = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
    closes = dates.copy()
    for unit in ("ms", "us"):
        selected = units == unit
        if selected.any():
            dates.loc[selected] = pd.to_datetime(frame.loc[selected, "open_time"].astype("int64"), unit=unit, utc=True)
            closes.loc[selected] = pd.to_datetime(frame.loc[selected, "close_time"].astype("int64"), unit=unit, utc=True)
    expected_duration = pd.Timedelta(days=1)
    duration = closes - dates
    if ((duration >= expected_duration) | (duration < pd.Timedelta(0))).any():
        raise CryptoDataError("daily candle close does not match one UTC day")
    partial = duration < expected_duration - pd.Timedelta(milliseconds=1)
    if partial.any() and partial_bar_policy == "reject":
        raise CryptoDataError("daily candle close does not match one UTC day")
    excluded_dates = [str(x.date()) for x in dates[partial]]
    frame = frame.loc[~partial].copy()
    dates = dates[~partial]
    output = frame.loc[:, COLUMNS].copy()
    output.index = pd.DatetimeIndex(dates).tz_localize(None)
    result = normalise_crypto(output)
    result.attrs["excluded_partial_daily_dates"] = excluded_dates
    return result


def load_dataset(path: str | Path, *, start=None, end=None) -> CryptoDataset:
    root = Path(path)
    manifest = json.loads((root / "manifest.json").read_text())
    prices = {}
    flags = list(manifest.get("quality_flags", []))
    for item in manifest.get("securities", []):
        symbol = item["symbol"]
        if item.get("history_missing") is True:
            flags.append(f"missing price history: {symbol}; failed acquisition export cannot be reused")
            continue
        relative = Path(item.get("price_file", f"prices/{symbol}.csv"))
        if relative.is_absolute() or ".." in relative.parts:
            raise CryptoDataError("price file must stay inside bundle")
        price_file = root / relative
        if not price_file.exists():
            flags.append(f"missing price history: {symbol}")
            continue
        if item.get("price_sha256") and hashlib.sha256(price_file.read_bytes()).hexdigest() != item["price_sha256"]:
            raise CryptoDataError(f"normalized price checksum mismatch: {symbol}")
        frame = normalise_crypto(pd.read_csv(price_file, float_precision="round_trip"))
        if start is not None:
            frame = frame.loc[pd.Timestamp(start):]
        if end is not None:
            frame = frame.loc[:pd.Timestamp(end)]
        if len(frame):
            prices[symbol] = frame
            missing = pd.date_range(frame.index[0], frame.index[-1]).difference(frame.index)
            if len(missing):
                flags.append(f"interior missing UTC candles: {symbol}: {len(missing)}")
    universe_file = root / "universe.csv"
    universe = pd.read_csv(universe_file) if universe_file.exists() else pd.DataFrame()
    return CryptoDataset(prices=prices, metadata=manifest, universe=universe,
                         quality_flags=list(dict.fromkeys(flags)))


def validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Public runner API: lower-case candles, exact prices, daily naive UTC index."""
    checked = normalise_crypto(frame)
    checked = checked.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "QuoteVolume": "quote_volume"})
    checked.index.name = "date"
    return checked


def load_bundle(path: str | Path, *, start=None, end=None) -> CryptoDataset:
    dataset = load_dataset(path, start=start, end=end)
    dataset.prices = {symbol: validate_frame(frame) for symbol, frame in dataset.prices.items()}
    return dataset


def trailing_liquidity(frame: pd.DataFrame, asof, *, days=90, min_coverage=0.95) -> float | None:
    """Only candles closed by asof enter an eligibility/liquidity observation."""
    cutoff = pd.Timestamp(asof).normalize()
    wanted = pd.date_range(cutoff - pd.Timedelta(days=days - 1), cutoff)
    prefix = frame.loc[frame.index <= cutoff]
    part = prefix.reindex(wanted)
    column = "QuoteVolume" if "QuoteVolume" in part else "quote_volume"
    if part[column].notna().mean() < min_coverage:
        return None
    # Missing values are not zero trading; median uses observed days only, with
    # an explicit eligibility threshold above.
    return float(part[column].median())
