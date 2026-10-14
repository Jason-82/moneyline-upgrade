"""Acquire a bounded actual SPY passive total-return benchmark for crypto research.

Example:
    python scripts/acquire_crypto_benchmark.py --output private/crypto_data/benchmark

One public Yahoo chart request is made. HTTP failures stop instead of attempting
authentication, account reads, proxy rotation, or repeated blocked requests.
Existing raw responses can be normalized offline with --raw PATH.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crypto_research.benchmark import normalise_yahoo_chart


def acquire(output: str | Path, *, start="2019-01-01", end="2025-12-31", raw: str | Path | None = None) -> dict:
    start_stamp, end_stamp = pd.Timestamp(start), pd.Timestamp(end)
    if start_stamp.tzinfo is not None or end_stamp.tzinfo is not None or start_stamp != start_stamp.normalize() or end_stamp != end_stamp.normalize() or end_stamp < start_stamp:
        raise ValueError("acquisition requires ordered normalized date bounds")
    if end_stamp >= pd.Timestamp.now(tz="UTC").normalize().tz_localize(None):
        raise ValueError("only completed historical dates may be acquired")
    parameters = {"period1": int(start_stamp.tz_localize("UTC").timestamp()),
                  "period2": int((end_stamp + pd.Timedelta(days=1)).tz_localize("UTC").timestamp()),
                  "interval": "1d", "events": "div,splits", "includeAdjustedClose": "true"}
    url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?" + urllib.parse.urlencode(parameters)
    if raw is None:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw_bytes = response.read()
    else:
        raw_bytes = Path(raw).read_bytes()
    frame, receipt = normalise_yahoo_chart(json.loads(raw_bytes), start_stamp, end_stamp)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    csv_bytes = frame.to_csv().encode()
    receipt.update({"schema_version": 1, "source_url": url,
                    "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                    "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
                    "acquired_at_utc": pd.Timestamp.now(tz="UTC").isoformat()})
    (output / "SPY_yahoo_chart_raw.json").write_bytes(raw_bytes)
    (output / "SPY.csv").write_bytes(csv_bytes)
    (output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--raw", help="existing bounded Yahoo raw JSON; no network request")
    args = parser.parse_args()
    receipt = acquire(args.output, start=args.start, end=args.end, raw=args.raw)
    print(json.dumps({key: receipt[key] for key in ("symbol", "rows", "dividend_events", "first_session", "last_session", "raw_sha256", "csv_sha256")}, indent=2))


if __name__ == "__main__":
    main()
