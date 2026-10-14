"""Read-only BTC/ETH monthly archive extension from an exactly receipted prefix.

No authentication, orders, token substitution or synthetic data. Monthly archives
only: --asof is an upper bound, and the effective cutoff is the last completed
calendar month. Exact historical reproduction uses the frozen private bundle;
live archive sources can change.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import zipfile

import numpy as np
import pandas as pd
import requests

REPO = Path(__file__).resolve().parents[2]
ARCHIVE = "https://data.binance.vision/"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
COLUMNS = ("Open", "High", "Low", "Close", "Volume", "QuoteVolume")
BINANCE_COLUMNS = ("open_time", "Open", "High", "Low", "Close", "Volume", "close_time",
                   "QuoteVolume", "trades", "taker_base", "taker_quote", "ignore")


def sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def normalise_crypto(frame):
    """Standalone counterpart of the earlier crypto helper's strict schema."""
    result = frame.copy().rename(columns={"date": "Date", "open": "Open", "high": "High",
                                         "low": "Low", "close": "Close", "volume": "Volume",
                                         "quote_volume": "QuoteVolume"})
    if "Date" in result:
        result = result.set_index("Date")
    if not isinstance(result.index, pd.DatetimeIndex):
        result.index = pd.to_datetime(result.index, errors="raise")
    if result.index.tz is not None:
        result.index = result.index.tz_convert("UTC").tz_localize(None)
    if (result.index.hasnans or result.index.has_duplicates or
            not result.index.equals(result.index.normalize()) or not result.index.is_monotonic_increasing):
        raise ValueError("Crypto dates must be unique, increasing UTC midnights")
    if set(COLUMNS) - set(result.columns):
        raise ValueError("Missing crypto OHLC/volume columns")
    for column in COLUMNS:
        result[column] = result[column].map(float) if result[column].dtype == object else pd.to_numeric(result[column], errors="raise")
    result = result.loc[:, COLUMNS].copy()
    if not np.isfinite(result.to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite crypto source values")
    if (result.loc[:, ("Open", "High", "Low", "Close")] <= 0).any().any():
        raise ValueError("Nonpositive crypto OHLC")
    if ((result.High < result[["Open", "Low", "Close"]].max(axis=1)) |
            (result.Low > result[["Open", "High", "Close"]].min(axis=1))).any():
        raise ValueError("Malformed crypto OHLC ranges")
    if (result.loc[:, ("Volume", "QuoteVolume")] < 0).any().any():
        raise ValueError("Negative crypto volume")
    result.index.name = "Date"
    return result


def parse_archive(raw, symbol):
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        names = [name for name in bundle.namelist() if not name.endswith("/")]
        if len(names) != 1 or not Path(names[0]).name.startswith(symbol + "-1d-") or not names[0].endswith(".csv"):
            raise ValueError("Unexpected archive symbol or members")
        frame = pd.read_csv(bundle.open(names[0]), header=None, float_precision="round_trip")
    if frame.shape[1] != len(BINANCE_COLUMNS) or frame.empty:
        raise ValueError("Expected twelve-column Binance daily archive")
    frame.columns = BINANCE_COLUMNS
    if str(frame.iloc[0, 0]) in ("open_time", "Open time"):
        frame = frame.iloc[1:].copy()
    for column in ("open_time", "close_time"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(frame[column]).all() or (frame[column] % 1 != 0).any():
            raise ValueError("Invalid archive integer timestamps")
    # Official spot files switched milliseconds to microseconds in January 2025.
    units = np.where(frame.open_time.to_numpy() >= 10 ** 14, "us", "ms")
    dates = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
    closes = dates.copy()
    for unit in ("ms", "us"):
        mask = units == unit
        if mask.any():
            dates.loc[mask] = pd.to_datetime(frame.loc[mask, "open_time"].astype("int64"), unit=unit, utc=True)
            closes.loc[mask] = pd.to_datetime(frame.loc[mask, "close_time"].astype("int64"), unit=unit, utc=True)
    duration = closes - dates
    if ((duration >= pd.Timedelta(days=1)) | (duration < pd.Timedelta(0))).any():
        raise ValueError("Archive candle duration lies outside one UTC day")
    partial = duration < pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
    excluded = [str(date.date()) for date in dates[partial]]
    selected = frame.loc[~partial, COLUMNS].copy()
    selected.index = pd.DatetimeIndex(dates[~partial]).tz_localize(None)
    result = normalise_crypto(selected)
    result.attrs["excluded_partial_daily_dates"] = excluded
    return result


def download_month(key, cache, symbol, *, raw_cache=None):
    target = cache / key
    checksum_target = Path(str(target) + ".CHECKSUM")
    target.parent.mkdir(parents=True, exist_ok=True)
    if raw_cache is not None:
        raw = (raw_cache / key).read_bytes()
        checksum = Path(str(raw_cache / key) + ".CHECKSUM").read_bytes()
    else:
        response = requests.get(ARCHIVE + key, timeout=90)
        response.raise_for_status()
        raw = response.content
        response = requests.get(ARCHIVE + key + ".CHECKSUM", timeout=90)
        response.raise_for_status()
        checksum = response.content
    token = checksum.decode().strip().split()
    if (len(token) != 2 or not re.fullmatch(r"[a-fA-F0-9]{64}", token[0]) or
            Path(token[1].lstrip("*")).name != target.name):
        raise ValueError("Malformed checksum sidecar")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != token[0].lower():
        raise ValueError("Official archive checksum mismatch")
    frame = parse_archive(raw, symbol)
    target.write_bytes(raw)
    checksum_target.write_bytes(checksum)
    return frame, {"kind": "monthly_archive", "symbol": symbol, "url": ARCHIVE + key,
                   "sha256": digest, "checksum_url": ARCHIVE + key + ".CHECKSUM",
                   "checksum_sha256": hashlib.sha256(checksum).hexdigest(), "bytes": len(raw),
                   "first_date": str(frame.index[0].date()) if len(frame) else None,
                   "last_date": str(frame.index[-1].date()) if len(frame) else None, "bars": len(frame),
                   "excluded_partial_daily_dates": frame.attrs.get("excluded_partial_daily_dates", [])}


def existing_helper():
    """Reuse the previous research helper through a portable repo-relative path."""
    helper = REPO / "scripts/acquire_crypto_data.py"
    if not helper.exists():
        return None
    sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("moneyline_existing_crypto_acquisition", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-folder", type=Path, required=True,
                        help="Receipted original prefix folder, containing prices/, manifest.json and source_receipts.json")
    parser.add_argument("--output", type=Path, required=True, help="New empty extension output directory")
    parser.add_argument("--asof", default="2026-10-13", help="Upper-bound date; last complete month is used")
    parser.add_argument("--raw-cache", type=Path, help="Saved extension raw archive tree; disables extension network calls")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    asof = pd.Timestamp(args.asof)
    if asof.tzinfo is not None or asof != asof.normalize() or args.workers < 1:
        parser.error("Expected plain --asof date and positive --workers")
    # Deliberately excludes an asof day's still-forming UTC candle.
    cutoff = (asof.to_period("M") - 1).end_time.normalize()
    base, output = args.base_folder.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be empty; frozen inputs must never be overwritten")
    base_manifest = json.loads((base / "manifest.json").read_text())
    expected = {row["symbol"]: row for row in base_manifest.get("securities", [])}
    source_hash = sha(base / "source_receipts.json")
    originals = {}
    overlap_periods = {}
    for symbol in SYMBOLS:
        original = base / "prices" / f"{symbol}.csv"
        if symbol not in expected or sha(original) != expected[symbol].get("price_sha256"):
            raise ValueError(f"Base normalized price hash does not match its manifest: {symbol}")
        frame = normalise_crypto(pd.read_csv(original, float_precision="round_trip"))
        wanted = pd.date_range(frame.index[0], frame.index[-1], freq="D", name="Date")
        if not frame.index.equals(wanted):
            raise ValueError(f"Missing daily calendar in base prefix: {symbol}")
        if frame.index[-1] != frame.index[-1].to_period("M").end_time.normalize():
            raise ValueError("Base prefix must end at a complete month boundary")
        originals[symbol] = frame
        overlap_periods[symbol] = frame.index[-1].to_period("M")
    output.mkdir(parents=True, exist_ok=True)
    (output / "prices").mkdir(exist_ok=True)
    helper = existing_helper() if args.raw_cache is None else None
    normalizer = helper.normalise_crypto if helper is not None else normalise_crypto
    tasks = []
    for symbol, overlap in overlap_periods.items():
        tasks.extend((symbol, month) for month in pd.period_range(overlap, max(overlap, cutoff.to_period("M")), freq="M"))
    frames, receipts, errors = {}, [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for symbol, month in tasks:
            key = f"data/spot/monthly/klines/{symbol}/1d/{symbol}-1d-{month}.zip"
            if helper is not None:
                future = pool.submit(helper.download_month, key, output / "raw", symbol)
            else:
                future = pool.submit(download_month, key, output / "raw", symbol,
                                     raw_cache=args.raw_cache.resolve() if args.raw_cache else None)
            futures[future] = (symbol, month)
        for future in as_completed(futures):
            symbol, month = futures[future]
            try:
                frame, receipt = future.result()
                frames[(symbol, month)] = frame
                receipts.append(receipt)
                print(symbol, str(month), "ok", len(frame), flush=True)
            except Exception as error:
                errors.append({"symbol": symbol, "month": str(month), "error": f"{type(error).__name__}: {error}"})
    write_json(output / "extension_source_receipts.json", sorted(receipts, key=lambda row: (row["symbol"], row["url"])))
    write_json(output / "acquisition_errors.json", errors)
    if errors:
        raise ValueError("Acquisition incomplete; error receipt retained and no valid manifest created")
    securities = []
    for symbol, old in originals.items():
        overlap_period = overlap_periods[symbol]
        overlap = frames[(symbol, overlap_period)]
        if not old.reindex(overlap.index).loc[:, list(COLUMNS)].equals(overlap):
            raise ValueError(f"Archive overlap changed for {symbol}; no revision silently accepted")
        extension = [frames[(symbol, month)] for month in pd.period_range(overlap_period + 1, cutoff.to_period("M"), freq="M")]
        combined = pd.concat([old] + extension).loc[:cutoff]
        wanted = pd.date_range(old.index[0], cutoff, freq="D", name="Date")
        if not combined.index.equals(wanted):
            raise ValueError(f"Incomplete requested UTC daily calendar: {symbol}")
        checked = normalizer(combined)
        destination = output / "prices" / f"{symbol}.csv"
        checked.to_csv(destination, float_format="%.17g")
        if not normalizer(pd.read_csv(destination, float_precision="round_trip")).equals(checked):
            raise ValueError("Normalized CSV round-trip changed values")
        securities.append({"symbol": symbol, "price_file": f"prices/{symbol}.csv", "price_sha256": sha(destination),
                           "base_input_file": f"prices/{symbol}.csv", "base_input_sha256": sha(base / "prices" / f"{symbol}.csv"),
                           "base_overlap": {"month": str(overlap_period), "rows": len(overlap), "exact_all_columns_match": True},
                           "bars": len(checked), "first_date": str(checked.index[0].date()),
                           "last_date": str(checked.index[-1].date()), "interior_missing_dates": []})
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "source": "Binance official public monthly spot archives", "quote_currency": "USDT",
                "price_basis": "unadjusted_spot", "calendar": "every complete UTC daily candle",
                "asof_upper_bound": str(asof.date()), "requested_end": str(cutoff.date()),
                "securities": securities, "extension_source_receipts_sha256": sha(output / "extension_source_receipts.json"),
                "base_source_receipts_file": "source_receipts.json", "base_source_receipts_sha256": source_hash,
                "base_manifest_sha256": sha(base / "manifest.json"),
                "helper_mode": "repo_relative_existing" if helper is not None else "standalone_public_archive_parser",
                "quality_flags": ["Fixed BTC/ETH diagnostic universe is not a survivorship-free all-coin portfolio.",
                                  "USDT is not USD; peg and conversion risk are not modeled.",
                                  "Venue prices do not establish Robinhood execution.",
                                  "No staking, forks, lending, distributions or actual taxes are modeled."]}
    write_json(output / "manifest.json", manifest)
    print("manifest_sha256", sha(output / "manifest.json"), flush=True)


if __name__ == "__main__":
    main()
