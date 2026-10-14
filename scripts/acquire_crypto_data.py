#!/usr/bin/env python3
"""Acquire read-only Binance spot research data, including archived delistings.

The complete historical archive catalog supplies candidate symbols, not today's
exchange listing. Formation uses ONLY prior completed December candles and
historical file availability. Rankings are frozen before later prices are read.
This is a venue-liquidity proxy, not a historical market-cap universe.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

try:
    import requests
except ImportError:  # Correctness does not depend on optional keepalive acceleration.
    requests = None

_HTTP_LOCAL = threading.local()

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from crypto_research.data import BINANCE_COLUMNS, CryptoDataError, normalise_crypto, parse_binance_zip, trailing_liquidity

ARCHIVE = "https://data.binance.vision/"
CATALOG = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
PUBLIC_API = "https://data-api.binance.vision/api/v3/klines"
PREFIX = "data/spot/monthly/klines/"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
STABLE_OR_FIAT = frozenset({"USDC", "BUSD", "PAX", "USDP", "TUSD", "DAI", "UST", "USTC", "FDUSD", "USDS", "USDSB", "SUSD", "USD1", "AEUR", "EUR", "GBP", "AUD", "BRL", "BIDR", "BVND", "TRY", "RUB", "UAH", "NGN", "RON", "ZAR", "ARS", "MXN", "IDRT", "VAI"})
WRAPPED = frozenset({"WBTC", "WETH", "WBETH", "BTCB", "STETH", "WSTETH", "BETH", "RENBTC"})
LEVERAGED_STEMS = frozenset({"BTC", "ETH", "BNB", "ADA", "BCH", "DOT", "EOS", "FIL", "LINK", "LTC", "SUSHI", "TRX", "UNI", "XRP", "XTZ", "YFI"})
LEVERAGED = frozenset(stem + suffix for stem in LEVERAGED_STEMS for suffix in ("UP", "DOWN", "BULL", "BEAR"))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def get(url: str, *, timeout=25, retries=1) -> bytes:
    for attempt in range(retries + 1):
        try:
            if requests is not None:
                if not hasattr(_HTTP_LOCAL, "session"):
                    _HTTP_LOCAL.session = requests.Session()
                    _HTTP_LOCAL.session.headers["User-Agent"] = "MoneylineResearch/1.0 public-market-data"
                try:
                    response = _HTTP_LOCAL.session.get(url, timeout=timeout)
                except requests.exceptions.RequestException as exc:
                    raise OSError(str(exc)) from exc
                if response.status_code >= 400:
                    raise urllib.error.HTTPError(url, response.status_code, "public data request failed", response.headers, io.BytesIO(response.content))
                return response.content
            request = urllib.request.Request(url, headers={"User-Agent": "MoneylineResearch/1.0 public-market-data"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 403, 404, 451) or attempt == retries:
                raise
        except (TimeoutError, OSError):
            if attempt == retries:
                raise
        time.sleep(0.25 * (attempt + 1))
    raise RuntimeError("unreachable retry state")


def catalog(prefix: str, destination: Path, *, delimiter=None) -> dict:
    if destination.exists():
        return json.loads(destination.read_text())
    pages, keys, prefixes = [], [], []
    token = None
    while True:
        query = {"list-type": "2", "prefix": prefix, "max-keys": 1000}
        if delimiter:
            query["delimiter"] = delimiter
        if token:
            query["continuation-token"] = token
        url = CATALOG + "?" + urllib.parse.urlencode(query)
        raw = get(url)
        root = ET.fromstring(raw)
        pages.append({"url": url, "sha256": sha(raw), "xml": raw.decode()})
        prefixes += [x.text for x in root.findall("s:CommonPrefixes/s:Prefix", NS)]
        keys += [x.text for x in root.findall("s:Contents/s:Key", NS)]
        if root.findtext("s:IsTruncated", "false", NS) != "true":
            break
        token = root.findtext("s:NextContinuationToken", None, NS)
        if not token:
            raise CryptoDataError("truncated source catalog lacks continuation token")
    result = {"source": CATALOG, "prefix": prefix, "retrieved_at": datetime.now(timezone.utc).isoformat(),
              "keys": keys, "prefixes": prefixes, "pages": pages}
    write_json(destination, result)
    return result


def classification(symbol: str) -> str | None:
    base = symbol[:-4]
    if base in STABLE_OR_FIAT:
        return "stable_or_fiat"
    if base in WRAPPED:
        return "wrapped_or_staked_duplicate"
    if base in LEVERAGED:
        return "leveraged_token"
    return None


def monthly_keys(record: dict, symbol: str) -> dict[str, str]:
    expression = re.compile(rf"^{re.escape(PREFIX + symbol + '/1d/' + symbol)}-1d-(\d{{4}}-\d{{2}})\.zip$")
    result = {}
    for key in record.get("keys", []):
        match = expression.match(key)
        if match:
            result[match.group(1)] = key
    return result


def download_month(key: str, cache: Path, symbol: str) -> tuple[pd.DataFrame, dict]:
    target = cache / key
    checksum_target = Path(str(target) + ".CHECKSUM")
    target.parent.mkdir(parents=True, exist_ok=True)
    checksum = checksum_target.read_bytes() if checksum_target.exists() else get(ARCHIVE + key + ".CHECKSUM")
    token = checksum.decode().strip().split()
    if len(token) != 2 or not re.fullmatch(r"[a-fA-F0-9]{64}", token[0]) or Path(token[1].lstrip("*")).name != target.name:
        raise CryptoDataError("invalid archive checksum sidecar")
    raw = target.read_bytes() if target.exists() else get(ARCHIVE + key)
    if sha(raw) != token[0].lower():
        raise CryptoDataError("Binance archive checksum mismatch")
    if not target.exists():
        target.write_bytes(raw)
    if not checksum_target.exists():
        checksum_target.write_bytes(checksum)
    frame = parse_binance_zip(raw, expected_sha256=token[0], expected_symbol=symbol,
                             partial_bar_policy="drop")
    return frame, {"kind": "monthly_archive", "symbol": symbol, "url": ARCHIVE + key,
                   "sha256": sha(raw), "checksum_url": ARCHIVE + key + ".CHECKSUM",
                   "checksum_sha256": sha(checksum), "bytes": len(raw),
                   "first_date": str(frame.index[0].date()) if len(frame) else None,
                   "last_date": str(frame.index[-1].date()) if len(frame) else None, "bars": len(frame),
                   "excluded_partial_daily_dates": frame.attrs.get("excluded_partial_daily_dates", [])}


def api_history(symbol: str, start: pd.Timestamp, end: pd.Timestamp, cache: Path) -> tuple[pd.DataFrame, list[dict]]:
    cursor, stop = int(start.timestamp() * 1000), int((end + pd.Timedelta(days=1)).timestamp() * 1000) - 1
    frames, receipts = [], []
    for batch in range(20):
        if cursor > stop:
            break
        query = {"symbol": symbol, "interval": "1d", "startTime": cursor, "endTime": stop, "limit": 1000}
        url = PUBLIC_API + "?" + urllib.parse.urlencode(query)
        destination = cache / "public_api" / symbol / f"{cursor}_{stop}.json"
        raw = destination.read_bytes() if destination.exists() else get(url)
        decoded = json.loads(raw)
        if not isinstance(decoded, list) or any(not isinstance(x, list) or len(x) != 12 for x in decoded):
            raise CryptoDataError("public market-data API returned an invalid kline response")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(raw)
        receipts.append({"kind": "public_market_data_api", "symbol": symbol, "url": url,
                         "sha256": sha(raw), "bytes": len(raw), "bars": len(decoded)})
        if not decoded:
            break
        frame = pd.DataFrame(decoded, columns=BINANCE_COLUMNS)
        frame.index = pd.to_datetime(frame.open_time.astype("int64"), unit="ms", utc=True).dt.tz_localize(None)
        duration = frame.close_time.astype("int64") - frame.open_time.astype("int64")
        if ((duration < 0) | (duration >= 86400000)).any():
            raise CryptoDataError("API daily candle duration is invalid")
        partial = duration < 86399999
        receipts[-1]["excluded_partial_daily_dates"] = [str(d.date()) for d in frame.index[partial]]
        frame = frame.loc[~partial]
        checked = normalise_crypto(frame)
        if checked.empty:
            break
        if checked.index[0] < pd.Timestamp(cursor, unit="ms") or checked.index[-1] > end:
            raise CryptoDataError("API response lies outside requested date interval")
        frames.append(checked)
        new_cursor = int(decoded[-1][0]) + 86400000
        if new_cursor <= cursor:
            raise CryptoDataError("API pagination did not advance")
        cursor = new_cursor
        if len(decoded) < 1000:
            break
    else:
        raise CryptoDataError("bounded API pagination exhausted")
    if not frames:
        raise CryptoDataError("public API supplied no history")
    return normalise_crypto(pd.concat(frames)), receipts


def run(args) -> dict:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    cache = output / "raw"
    source = catalog(PREFIX, cache / "all_symbol_catalog.json", delimiter="/")
    symbols = sorted(x.rstrip("/").split("/")[-1] for x in source["prefixes"] if x.rstrip("/").endswith("USDT"))
    catalogs, failures, receipts = {}, [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(catalog, PREFIX + symbol + "/1d/", cache / "catalog" / (symbol + ".json")): symbol for symbol in symbols}
        for number, future in enumerate(as_completed(jobs), 1):
            symbol = jobs[future]
            try:
                catalogs[symbol] = monthly_keys(future.result(), symbol)
            except Exception as exc:
                failures.append({"stage": "catalog", "symbol": symbol, "error": str(exc)})
            if number % 100 == 0 or number == len(jobs):
                print(f"cataloged {number}/{len(jobs)} historical USDT symbols", flush=True)
    ranking_jobs = []
    classification_rows = []
    for symbol, keys in catalogs.items():
        reason = classification(symbol)
        if reason:
            classification_rows.append({"symbol": symbol, "reason": reason})
            continue
        for formation in ("2019-12-31", "2022-12-31"):
            cutoff = pd.Timestamp(formation)
            # End of the earliest catalog month is an upper bound on its listing
            # date. This uses past availability only, not future survival.
            available = [m for m in keys if m <= formation[:7]]
            if not available or pd.Period(min(available), "M").end_time.normalize() > cutoff - pd.Timedelta(days=365):
                continue
            key = keys.get(formation[:7])
            if key is None:
                continue
            ranking_jobs.append((formation, symbol, key))
    print(f"fetching {len(ranking_jobs)} causal formation archives", flush=True)
    observations, formation_frames = [], {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(download_month, key, cache, symbol): (formation, symbol) for formation, symbol, key in ranking_jobs}
        for number, future in enumerate(as_completed(jobs), 1):
            formation, symbol = jobs[future]
            try:
                frame, receipt = future.result()
                receipts.append(receipt)
                formation_frames[(formation, symbol)] = frame
                liquidity = trailing_liquidity(frame, formation, days=30, min_coverage=0.95)
                observations.append({"formation_date": formation, "symbol": symbol, "median_quote_volume": liquidity,
                                     "eligible": liquidity is not None and liquidity >= args.min_quote_volume})
            except Exception as exc:
                failures.append({"stage": "formation", "symbol": symbol, "formation_date": formation, "error": str(exc)})
            if number % 100 == 0 or number == len(jobs):
                print(f"formation archives {number}/{len(jobs)}", flush=True)
    chosen = []
    for formation in ("2019-12-31", "2022-12-31"):
        candidates = sorted([x for x in observations if x["formation_date"] == formation and x["eligible"]],
                            key=lambda x: (-x["median_quote_volume"], x["symbol"]))
        for rank, item in enumerate(candidates[:40], 1):
            chosen.append({**item, "rank": rank, "group": "liquid_top20" if rank <= 20 else "liquidity_next20"})
    universe = pd.DataFrame(chosen)
    universe.to_csv(output / "universe.csv", index=False)
    pd.DataFrame(observations).to_csv(output / "formation_observations.csv", index=False)
    write_json(output / "frozen_universe_receipt.json", {"source_catalog_sha256": sha((cache / "all_symbol_catalog.json").read_bytes()),
               "created_before_later_prices": True, "selection": chosen,
               "selection_sha256": sha(json.dumps(chosen, sort_keys=True, allow_nan=False).encode()),
               "formation_failure_count": sum(x["stage"] == "formation" for x in failures)})
    selected = sorted({x["symbol"] for x in chosen} | {"BTCUSDT", "ETHUSDT"})
    print(f"frozen {len(chosen)} universe memberships / {len(selected)} unique histories", flush=True)
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    securities = []

    def history(symbol):
        if args.history_source == "public-api":
            try:
                frame, history_receipts = api_history(symbol, start, end, cache)
                source_kind = "public_market_data_api"
            except (urllib.error.HTTPError, CryptoDataError) as exc:
                if isinstance(exc, urllib.error.HTTPError) and exc.code != 400:
                    raise
                frame, history_receipts = archive_history(symbol)
                source_kind = "monthly_archive_fallback"
        else:
            frame, history_receipts = archive_history(symbol)
            source_kind = "monthly_archive"
        def overlaps_match(candidate):
            columns = ["Open", "High", "Low", "Close", "Volume", "QuoteVolume"]
            for formation in ("2019-12-31", "2022-12-31"):
                original = formation_frames.get((formation, symbol))
                if original is None:
                    continue
                overlap = candidate.index.intersection(original.index)
                if not overlap.equals(original.index) or not candidate.loc[overlap, columns].equals(original.loc[overlap, columns]):
                    return False
            return True
        if not overlaps_match(frame):
            # Real archive/API revisions can change volume. Do not invent an
            # average or overwrite a few candles: use one checksummed archive
            # source consistently for the full security history.
            frame, history_receipts = archive_history(symbol)
            source_kind = "monthly_archive_due_to_api_archive_revision"
            if not overlaps_match(frame):
                raise CryptoDataError(f"archived history omits its own formation candles for {symbol}")
        return frame.loc[start:end], history_receipts, source_kind

    def archive_history(symbol):
        chunks, local_receipts = [], []
        for month, key in sorted(catalogs[symbol].items()):
            if start.strftime("%Y-%m") <= month <= end.strftime("%Y-%m"):
                frame, receipt = download_month(key, cache, symbol)
                chunks.append(frame)
                local_receipts.append(receipt)
        if not chunks:
            raise CryptoDataError("archived symbol has no requested history")
        return normalise_crypto(pd.concat(chunks)), local_receipts

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(history, symbol): symbol for symbol in selected}
        for number, future in enumerate(as_completed(jobs), 1):
            symbol = jobs[future]
            try:
                frame, history_receipts, source_kind = future.result()
                receipts.extend(history_receipts)
                destination = output / "prices" / (symbol + ".csv")
                destination.parent.mkdir(parents=True, exist_ok=True)
                columns = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "QuoteVolume": "quote_volume"}
                exported = frame.loc[:, list(columns)].rename(columns=columns)
                exported.index.name = "date"
                temporary = destination.with_suffix(".csv.tmp")
                exported.to_csv(temporary, float_format="%.17g")
                temporary.replace(destination)
                interior = pd.date_range(frame.index[0], frame.index[-1]).difference(frame.index)
                securities.append({"symbol": symbol, "security_id": "BINANCE_SPOT_" + symbol,
                                   "price_file": str(destination.relative_to(output)), "price_sha256": sha(destination.read_bytes()),
                                   "source_kind": source_kind, "first_date": str(frame.index[0].date()), "last_date": str(frame.index[-1].date()),
                                   "bars": len(frame), "interior_missing_dates": [str(d.date()) for d in interior],
                                   "terminal_outcome": "unknown" if frame.index[-1] < end else "not_required_within_sample"})
            except Exception as exc:
                failures.append({"stage": "history", "symbol": symbol, "error": str(exc)})
                securities.append({"symbol": symbol, "security_id": "BINANCE_SPOT_" + symbol,
                                   "price_file": "prices/" + symbol + ".csv", "history_missing": True, "terminal_outcome": "unknown"})
            print(f"histories {number}/{len(jobs)}: {symbol}", flush=True)
    flags = ["Venue liquidity is not historical market capitalization.", "USDT quote currency is not USD; peg risk and cash conversion are not modeled.",
             "Binance global market-data research is not Robinhood historical fills or an available US execution venue.",
             "Venue pair IDs do not reconcile token migrations, forks, redenominations or token distributions.",
             "Crypto OHLC is unadjusted; staking, lending, airdrops and exchange terminal payouts are excluded.",
             "Historical validation is not an untouched holdout; published papers and prior analyses may expose its regime."]
    if failures:
        flags.append(f"Acquisition failures: {len(failures)}; absent candidate observations are not scored as zero.")
    truncated = [x["symbol"] for x in securities if x.get("terminal_outcome") == "unknown"]
    if truncated:
        flags.append("Unknown terminal outcomes / missing histories: " + ", ".join(truncated))
    manifest = {"schema_version": 1, "mode": "exploratory", "source": "Binance official spot public archive and public market-data API",
                "source_docs": "https://github.com/binance/binance-public-data", "price_basis": "unadjusted_spot", "quote_currency": "USDT",
                "calendar": "every UTC day", "requested_start": args.start, "requested_end": args.end,
                "catalog_symbols": len(symbols), "catalog_complete": not any(x["stage"] == "catalog" for x in failures),
                "universe_policy": {"formation_dates": ["2019-12-31", "2022-12-31"], "formation_days": 30,
                                    "min_formation_coverage": 0.95, "minimum_prior_venue_history_days": 365,
                                    "min_median_quote_volume_usdt": args.min_quote_volume, "top_group_size": 20, "next_group_size": 20,
                                    "fixed_baskets_per_three_year_period": True, "classification": {"stable_or_fiat": sorted(STABLE_OR_FIAT), "wrapped": sorted(WRAPPED), "leveraged": sorted(LEVERAGED)}},
                "securities": sorted(securities, key=lambda x: x["symbol"]), "quality_flags": flags,
                "failures": failures, "classification_exclusions": classification_rows, "deployment_blocked": True,
                "receipt_count": len(receipts), "created_at": datetime.now(timezone.utc).isoformat()}
    write_json(output / "source_receipts.json", receipts)
    manifest["source_receipts_sha256"] = sha((output / "source_receipts.json").read_bytes())
    manifest["universe_sha256"] = sha((output / "universe.csv").read_bytes())
    for record in securities:
        if not record.get("history_missing") and sha((output / record["price_file"]).read_bytes()) != record["price_sha256"]:
            raise CryptoDataError("normalized CSV changed during acquisition; manifest is not published")
    write_json(output / "manifest.json", manifest)
    print(json.dumps({"output": str(output), "securities": len(securities), "memberships": len(chosen), "failures": len(failures), "receipts": len(receipts)}), flush=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--min-quote-volume", type=float, default=2_000_000)
    parser.add_argument("--history-source", choices=("public-api", "archives"), default="public-api")
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("workers must be 1..16")
    run(args)


if __name__ == "__main__":
    main()
