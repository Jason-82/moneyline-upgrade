#!/usr/bin/env python3
"""Import pinned research data without silently upgrading its economic quality.

`qlib-development` decodes only prices through the requested development
cutoff. `licensed-import` validates an already normalized private export before
copying it; raw vendor files require the event/identity reconciliation in
docs/DATA_SOURCES.md. Neither command downloads or purchases a licensed feed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
DEVELOPMENT_END = date(2022, 12, 31)
QLIB_URL = "https://github.com/SunsetWolf/qlib_dataset/releases/download/v0/qlib_data_us_1d_v3.zip"
QLIB_SHA256 = "d7dcb4f227d96930700ebebf3e47cf38a5352a4bbeb35ca9be789aa94969bbc4"
MEMBERS_COMMIT = "a2430f2af0c79ddf0748e91de11bdeb1616ab5a7"
MEMBERS_URL = f"https://raw.githubusercontent.com/fja05680/sp500/{MEMBERS_COMMIT}/sp500_ticker_start_end.csv"
MEMBERS_SHA256 = "b2f4fe2f2e4dce8eaf0eb4fbd3946a32a20c1ddfe69687dfca3b6b59a0b71f9f"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, columns: Iterable[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def iso_date(value: str) -> date | None:
    if not value or str(value).lower() in ("nan", "none", "nat"):
        return None
    return date.fromisoformat(str(value)[:10])


def load_members(path: Path, start: date, end: date) -> list[dict]:
    """Read dated membership, never manufacture announcement knowledge."""
    output = []
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            symbol = (row.get("symbol") or row.get("ticker") or "").upper().replace("-", ".")
            begins = iso_date(row.get("start") or row.get("start_date") or "")
            ends = iso_date(row.get("end") or row.get("end_date") or "")
            if not symbol or begins is None:
                raise ValueError("membership row lacks ticker or start date")
            if begins > end or (ends is not None and ends < start):
                continue
            # Clipping a later end would make it falsely look like a delisting.
            # For this bounded bundle leave later known end dates unasserted.
            bounded_end = ends if ends is not None and ends <= end else None
            output.append({
                "security_id": "QLIB_" + symbol.replace(".", "_"),
                "symbol": symbol, "start": begins.isoformat(),
                "end": "" if bounded_end is None else bounded_end.isoformat(),
                "known_at": row.get("known_at", ""),
                "end_known_at": row.get("end_known_at", ""),
                "source": MEMBERS_URL,
            })
    return output


def read_qlib_calendar(archive: zipfile.ZipFile, end: date) -> list[date]:
    dates = []
    with archive.open("calendars/day.txt") as stream:
        for raw in stream:
            day = iso_date(raw.decode("ascii").strip())
            if day is None:
                raise ValueError("invalid qlib calendar date")
            if day > end:
                break
            if dates and day <= dates[-1]:
                raise ValueError("qlib calendar is not strictly increasing")
            dates.append(day)
    if not dates:
        raise ValueError("no source calendar dates in requested interval")
    return dates


def read_bounded_vector(archive: zipfile.ZipFile, name: str, calendar_size: int) -> tuple[int, np.ndarray]:
    """Read exactly the prefix allowed by the already bounded calendar.

    In particular, do not call np.fromfile/frombuffer on a complete feature
    entry and then slice it: that would decode the holdout first.
    """
    with archive.open(name) as stream:
        header = stream.read(4)
        if len(header) != 4:
            raise ValueError("missing qlib vector header")
        offset_float = float(np.frombuffer(header, dtype="<f4")[0])
        if not math.isfinite(offset_float) or offset_float < 0 or offset_float != int(offset_float):
            raise ValueError("invalid qlib vector start index")
        offset = int(offset_float)
        count = max(0, calendar_size - offset)
        payload = stream.read(count * 4)
        if len(payload) % 4:
            raise ValueError("truncated qlib float32 vector")
        values = np.frombuffer(payload, dtype="<f4").astype(float)
    return offset, values


def classify_bar(row: dict) -> str | None:
    o, h, l, c = (row[name] for name in ("open", "high", "low", "close"))
    if not all(math.isfinite(v) for v in (o, h, l, c)):
        return "nonfinite_or_unavailable"
    if min(o, h, l, c) <= 0:
        return "nonpositive"
    if h < max(o, c, l) or l > min(o, c, h):
        return "ohlc_order"
    return None


def import_qlib(args) -> dict:
    from screener.data import valid_ohlc_mask

    start, end = iso_date(args.start), iso_date(args.end)
    if start is None or end is None or start > end:
        raise ValueError("start/end must be valid increasing dates")
    if end > DEVELOPMENT_END:
        raise ValueError("qlib-development cannot read after 2022-12-31; use frozen holdout workflow")
    archive_path, members_path, output = Path(args.archive), Path(args.members), Path(args.out)
    if output.exists() and any(output.iterdir()):
        raise ValueError("output must be new or empty; never overwrite a previous research bundle")
    archive_hash, membership_hash = sha256(archive_path), sha256(members_path)
    if not args.allow_unpinned and (archive_hash != QLIB_SHA256 or membership_hash != MEMBERS_SHA256):
        raise ValueError("input hash differs from pinned source; pass --allow-unpinned only for explicit diagnostics")
    memberships = load_members(members_path, start, end)
    wanted = {row["symbol"] for row in memberships} | {args.benchmark.upper()}
    securities, missing, invalid, summaries, available_dates = [], [], [], [], {}
    accepted_roundoff_count = 0
    with zipfile.ZipFile(archive_path) as archive:
        calendar = read_qlib_calendar(archive, end)
        names = set(archive.namelist())
        for symbol in sorted(wanted):
            security_id = "QLIB_" + symbol.replace(".", "_")
            # Keep absent histories in the master/universe so coverage cannot
            # improve simply by dropping unavailable delisted securities.
            securities.append({"security_id": security_id, "symbol": symbol, "source": QLIB_URL, "dividend_status": "unknown"})
            key = symbol.lower().replace(".", "-")
            paths = {field: f"features/{key}/{field}.day.bin" for field in ("open", "high", "low", "close")}
            if not all(name in names for name in paths.values()):
                missing.append({"security_id": security_id, "symbol": symbol, "reason": "missing_source_vector"})
                continue
            values_by_field = {}
            for field, name in paths.items():
                offset, values = read_bounded_vector(archive, name, len(calendar))
                values_by_field[field] = {calendar[offset + i]: value for i, value in enumerate(values)}
            days = sorted(set.intersection(*(set(values_by_field[field]) for field in paths)))
            source_rows = []
            for day in days:
                if day < start:
                    continue
                row = {"date": day.isoformat(), **{field: float(values_by_field[field][day]) for field in paths}}
                source_rows.append(row)
            rows = []
            if source_rows:
                frame = pd.DataFrame(source_rows)
                exact_valid = np.asarray(valid_ohlc_mask(frame, float32_ulps=0), dtype=bool)
                precision_valid = np.asarray(valid_ohlc_mask(frame, float32_ulps=2), dtype=bool)
                accepted_roundoff_count += int((precision_valid & ~exact_valid).sum())
                for row, valid in zip(source_rows, precision_valid):
                    if valid:
                        # Retain each original float32 value exactly. Numerical
                        # tolerance changes validation, never the OHLC or signal.
                        rows.append(row)
                        continue
                    # No future-dependent whole-security filter; the invalid
                    # date is recorded and will fail strict coverage checks.
                    issue = classify_bar(row)
                    invalid.append({"security_id": security_id, "date": row["date"], "reason": issue or "ohlc_order_above_precision_tolerance"})
            if not rows:
                missing.append({"security_id": security_id, "symbol": symbol, "reason": "no_valid_development_bars"})
                continue
            write_csv(output / "prices" / f"{security_id}.csv", ("date", "open", "high", "low", "close"), rows)
            available_dates[security_id] = {iso_date(row["date"]) for row in rows}
            summaries.append({"security_id": security_id, "symbol": symbol, "first_date": rows[0]["date"], "last_date": rows[-1]["date"], "rows": len(rows)})
    write_csv(output / "calendar.csv", ("date",), [{"date": day.isoformat()} for day in calendar if day >= start])
    write_csv(output / "securities.csv", ("security_id", "symbol", "source", "dividend_status"), securities)
    write_csv(output / "membership.csv", ("security_id", "start", "end", "known_at", "source", "end_known_at"), [{k: row[k] for k in ("security_id", "start", "end", "known_at", "source", "end_known_at")} for row in memberships])
    write_csv(output / "dividends.csv", ("security_id", "date", "cash_per_share", "source"), [])
    write_csv(output / "terminal_events.csv", ("security_id", "date", "cash_per_share", "source", "kind", "known_at"), [])
    write_csv(output / "acquisition_audit" / "missing_securities.csv", ("security_id", "symbol", "reason"), missing)
    write_csv(output / "acquisition_audit" / "invalid_bars.csv", ("security_id", "date", "reason"), invalid)
    write_csv(output / "acquisition_audit" / "price_coverage.csv", ("security_id", "symbol", "first_date", "last_date", "rows"), summaries)
    coverage = []
    for asof_text in args.coverage_dates.split(","):
        asof = iso_date(asof_text)
        if asof is None or not start <= asof <= end:
            continue
        prior_session = max((day for day in calendar if day <= asof), default=None)
        active = {row["security_id"] for row in memberships if iso_date(row["start"]) <= asof and (iso_date(row["end"]) is None or iso_date(row["end"]) >= asof)}
        covered = {security_id for security_id in active if prior_session in available_dates.get(security_id, set())}
        coverage.append({"asof": asof.isoformat(), "mark_session": str(prior_session), "active_members": len(active), "members_with_prior_session_bar": len(covered), "coverage_pct": 100 * len(covered) / len(active) if active else 0.0, "missing_ids": sorted(active - covered)})
    manifest = {
        "schema_version": 1, "mode": "exploratory", "price_basis": "total_return",
        "source_precision": "float32", "ohlc_float32_ulps": 2,
        "dividends_complete": False, "terminal_complete": False,
        "universe_complete": False, "point_in_time_ids": False,
        "price_source": QLIB_URL, "dividend_source": "unavailable (not zero)",
        "corporate_action_source": "unavailable (not zero)",
        "calendar_source": "Qlib calendars/day.txt; provider trading dates, not independently verified exchange calendar",
        "source": "Qlib public development archive + community ticker membership",
        "version": "v0/qlib_data_us_1d_v3.zip",
        "hash": archive_hash, "start": start.isoformat(), "cutoff": end.isoformat(),
        "benchmark_security_id": "QLIB_" + args.benchmark.upper().replace(".", "_"),
        "source_artifacts": [
            {"path": str(archive_path.resolve()), "url": QLIB_URL, "sha256": archive_hash, "bytes": archive_path.stat().st_size},
            {"path": str(members_path.resolve()), "url": MEMBERS_URL, "commit": MEMBERS_COMMIT if membership_hash == MEMBERS_SHA256 else "unverified", "sha256": membership_hash, "bytes": members_path.stat().st_size},
        ],
        "limitations": [
            "Rescaled total-return OHLC differs from required split-only signal",
            "No complete cash dividends or terminal proceeds; zero records mean missing, not zero payout",
            "Synthetic ticker IDs do not resolve rename/reuse or share-class identity",
            "Retrospective membership has no announcement timestamps",
            "Missing old/delisted histories; no selected-series forward fills allowed",
            "Invalid rows quarantined locally; no future-history whole-security quality filter",
            "Up to two float32 ULPs of OHLC range roundoff accepted without changing any source price",
            "No post-cutoff price values decoded; development import cannot release holdout",
        ],
    }
    write_json(output / "manifest.json", manifest)
    audit = {"status": "development_only", "qualified_for_live": False, "requested_symbols": len(wanted), "loaded_symbols": len(summaries), "missing_symbols": len(missing), "valid_price_rows": sum(row["rows"] for row in summaries), "accepted_float32_roundoff_bars": accepted_roundoff_count, "ohlc_float32_ulps": 2, "source_precision": "float32", "invalid_or_unavailable_bars": len(invalid), "coverage": coverage, "manifest_sha256": sha256(output / "manifest.json")}
    write_json(output / "acquisition_audit" / "summary.json", audit)
    return {key: value for key, value in audit.items() if key != "coverage"}


def import_licensed(args) -> dict:
    """Accept only an already reconciled, normalized and validated bundle."""
    from research.data_contract import load_dataset

    source, output = Path(args.bundle).resolve(), Path(args.out).resolve()
    if iso_date(args.cutoff) is None or iso_date(args.cutoff) > DEVELOPMENT_END:
        raise ValueError("licensed-import is development-only; release later prices with the frozen holdout workflow")
    if source == output or source in output.parents:
        raise ValueError("output must not overwrite or nest inside the source bundle")
    if output.exists():
        raise ValueError("output already exists; preserve previous bundle/version")
    dataset = load_dataset(source, mode="validated", cutoff=args.cutoff)
    inputs = [{"relative_path": str(path.relative_to(source)), "bytes": path.stat().st_size,
               "sha256": sha256(path)} for path in sorted(source.rglob("*")) if path.is_file()]
    # The loader is responsible for price basis, IDs, cash/events, calendar,
    # completeness and selection coverage. Copy retains exact reviewed bytes;
    # the caller uses cutoff when loading to restrict research dates.
    shutil.copytree(source, output)
    for artifact in inputs:
        if sha256(output / artifact["relative_path"]) != artifact["sha256"]:
            raise ValueError("copied input checksum mismatch; imported bundle is not usable")
    write_csv(output / "acquisition_audit" / "input_checksums.csv", ("relative_path", "bytes", "sha256"), inputs)
    audit = {"status": "validated_import", "input_manifest_sha256": sha256(source / "manifest.json"), "copied_manifest_sha256": sha256(output / "manifest.json"), "input_file_count": len(inputs), "input_checksums_sha256": sha256(output / "acquisition_audit" / "input_checksums.csv"), "cutoff": args.cutoff, "warning": "Provider license and event/identity reconciliation remain the exporter responsibility; no vendor data was purchased or downloaded."}
    write_json(output / "acquisition_audit" / "import_receipt.json", audit)
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    qlib = sub.add_parser("qlib-development", help="bounded exploratory import; never reads 2023+ prices")
    qlib.add_argument("--archive", required=True)
    qlib.add_argument("--members", required=True)
    qlib.add_argument("--out", required=True)
    qlib.add_argument("--start", default="1999-12-31")
    qlib.add_argument("--end", default="2022-12-31")
    qlib.add_argument("--benchmark", default="SPY")
    qlib.add_argument("--coverage-dates", default="2005-01-01,2008-01-01,2011-01-01,2014-01-01,2017-01-01,2020-01-01")
    qlib.add_argument("--allow-unpinned", action="store_true", help="explicitly diagnostic only")
    licensed = sub.add_parser("licensed-import", help="validate and copy normalized user-licensed CSV export")
    licensed.add_argument("--bundle", required=True)
    licensed.add_argument("--out", required=True)
    licensed.add_argument("--cutoff", default="2022-12-31")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = import_qlib(args) if args.command == "qlib-development" else import_licensed(args)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, OSError) as exc:
        print(f"acquisition failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
