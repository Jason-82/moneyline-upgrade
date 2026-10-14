"""Fail-closed stock research inputs, with a deliberately separate diagnostic mode.

No loader infers historical dividends from today's yield, substitutes ticker strings
for durable identities in validated research, or writes invented delisting prices.
See ``load_dataset`` for the portable CSV-folder input contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import re
from typing import Mapping

import numpy as np
import pandas as pd

from research.calendar import explicit_sessions


class DataContractError(ValueError):
    pass


def _date(value, *, optional=False):
    if value is None or pd.isna(value) or str(value).strip() == "":
        if optional:
            return pd.NaT
        raise DataContractError("required session date is missing")
    result = pd.Timestamp(value)
    if result.tzinfo is not None:
        result = result.tz_localize(None)
    if result != result.normalize():
        raise DataContractError(f"expected a session date, got timestamp {value}")
    return result


@dataclass(frozen=True)
class SecurityRecord:
    security_id: str
    symbol: str
    source: str
    dividend_status: str = "unknown"


@dataclass(frozen=True)
class MembershipSpell:
    security_id: str
    start: pd.Timestamp
    end: pd.Timestamp | None
    known_at: pd.Timestamp | None
    source: str
    end_known_at: pd.Timestamp | None = None

    def active_at(self, date, *, require_known=True) -> bool:
        date = _date(date)
        if require_known and (pd.isna(self.known_at) or _date(self.known_at) > date):
            return False
        if _date(self.start) > date:
            return False
        # A future exit announcement must not remove a member from an earlier universe.
        if pd.isna(self.end) or date <= _date(self.end):
            return True
        return (require_known and not pd.isna(self.end_known_at)
                and _date(self.end_known_at) > date)


@dataclass(frozen=True)
class TerminalEvent:
    security_id: str
    date: pd.Timestamp
    cash_per_share: float
    source: str
    kind: str = "delisting"
    known_at: pd.Timestamp | None = None


@dataclass
class ResearchDataset:
    prices: dict[str, pd.DataFrame]
    calendar: pd.DatetimeIndex
    securities: tuple[SecurityRecord, ...]
    membership: tuple[MembershipSpell, ...]
    dividends: dict[str, pd.Series] = field(default_factory=dict)
    terminal_events: tuple[TerminalEvent, ...] = ()
    metadata: dict = field(default_factory=dict)

    def eligible(self, date, *, require_known=True) -> set[str]:
        return {spell.security_id for spell in self.membership
                if spell.active_at(date, require_known=require_known)}


_COMPLETE_FLAGS = ("dividends_complete", "terminal_complete", "universe_complete", "point_in_time_ids")
_SOURCES = ("price_source", "dividend_source", "corporate_action_source", "calendar_source")


def _declared_ohlc_precision(metadata: Mapping, *, strict=False) -> int:
    ulps = metadata.get("ohlc_float32_ulps", 0)
    if isinstance(ulps, bool) or not isinstance(ulps, (int, np.integer)) or not 0 <= ulps <= 2:
        raise DataContractError("ohlc_float32_ulps must be integer 0..2")
    if ulps and (strict or metadata.get("mode") not in ("exploratory", "legacy_qlib")
                 or metadata.get("price_basis") != "total_return"
                 or metadata.get("source_precision") != "float32"):
        raise DataContractError("nonzero float32 tolerance requires declared exploratory total-return source precision")
    return ulps


def validate_dataset(dataset: ResearchDataset, *, start=None, end=None,
                     strict: bool | None = None) -> list[str]:
    """Validate structure and completeness. Validated mode raises on any research gap.

    Exploratory mode still rejects malformed OHLC, dates and event values, but reports
    absent dividends, durable IDs, historical members and terminal proceeds as gaps.
    Such a dataset cannot authorize deployment or a final untouched-holdout test.
    """
    from screener.data import normalise

    strict = dataset.metadata.get("mode") == "validated" if strict is None else strict
    ulps = _declared_ohlc_precision(dataset.metadata, strict=strict)
    calendar = explicit_sessions(dataset.calendar)
    cal = calendar[(calendar >= _date(start)) if start is not None else np.ones(len(calendar), bool)]
    if end is not None:
        cal = cal[cal <= _date(end)]
    if not len(cal):
        raise DataContractError("research interval contains no supplied sessions")
    gaps = []
    if dataset.metadata.get("price_basis") != "split_only":
        gaps.append("split-only signal/execution prices unavailable (total-return adjustment changes flips)")
    for flag in _COMPLETE_FLAGS:
        if dataset.metadata.get(flag) is not True:
            gaps.append(f"{flag} is not certified")
    for source in _SOURCES:
        if not str(dataset.metadata.get(source) or "").strip():
            gaps.append(f"missing {source} provenance")
    records = {s.security_id: s for s in dataset.securities}
    if len(records) != len(dataset.securities):
        raise DataContractError("security master contains duplicate immutable security_id")
    if not records:
        raise DataContractError("security master is empty")
    for record in dataset.securities:
        if not record.security_id or not record.symbol or not record.source:
            gaps.append(f"incomplete identity provenance for {record.security_id}")
        if record.dividend_status not in ("complete", "known_zero", "unknown"):
            raise DataContractError(f"invalid dividend_status for {record.security_id}")
        if record.dividend_status == "unknown":
            gaps.append(f"historical dividends unknown for {record.security_id}")
    if set(dataset.prices) - set(records):
        raise DataContractError("price history references an unknown security_id")
    for sid, frame in dataset.prices.items():
        try:
            checked = normalise(frame, float32_ulps=ulps)
        except ValueError as exc:
            raise DataContractError(f"{sid}: {exc}") from exc
        if not checked.index.equals(frame.index) or not len(frame):
            raise DataContractError(f"{sid}: prices must be nonempty, ordered and unique")
        if len(frame.index.difference(calendar)):
            raise DataContractError(f"{sid}: price dates outside the supplied SPY session calendar")
        div = dataset.dividends.get(sid)
        if div is None:
            gaps.append(f"missing separately accounted dividend history for {sid}")
        else:
            if not isinstance(div.index, pd.DatetimeIndex) or div.index.has_duplicates or div.index.hasnans:
                raise DataContractError(f"{sid}: invalid dividend event index")
            if not np.isfinite(div.to_numpy(dtype=float)).all() or (div < 0).any():
                raise DataContractError(f"{sid}: dividends must be finite and nonnegative")
            if len(div.index.difference(calendar)):
                raise DataContractError(f"{sid}: dividend dates outside the supplied sessions")
            if records[sid].dividend_status == "known_zero" and (div != 0).any():
                raise DataContractError(f"{sid}: known_zero declaration conflicts with dividends")
    terminal = {}
    for event in dataset.terminal_events:
        if event.security_id not in records:
            raise DataContractError("terminal event references an unknown security_id")
        when = _date(event.date)
        if not np.isfinite(event.cash_per_share) or event.cash_per_share < 0:
            raise DataContractError("terminal payout must be explicit finite nonnegative cash per split-adjusted share")
        if not event.source:
            gaps.append(f"terminal payout source missing for {event.security_id}")
        if when not in calendar:
            raise DataContractError("terminal event date must be an effective supplied session")
        if event.security_id in terminal:
            raise DataContractError("multiple terminal events for one security_id")
        terminal[event.security_id] = event
        if event.security_id in dataset.prices and dataset.prices[event.security_id].index[-1] > when:
            raise DataContractError(f"{event.security_id}: prices continue after terminal payout")
    if not dataset.membership:
        gaps.append("point-in-time membership spells are missing")
    seen = {}
    for spell in dataset.membership:
        if spell.security_id not in records:
            raise DataContractError("membership references an unknown security_id")
        begin, finish = _date(spell.start), _date(spell.end, optional=True)
        if not pd.isna(finish) and finish < begin:
            raise DataContractError("membership end precedes start")
        if pd.isna(spell.known_at) or not spell.source:
            gaps.append(f"membership announcement/provenance missing for {spell.security_id}")
        if not pd.isna(finish) and pd.isna(spell.end_known_at):
            gaps.append(f"membership exit announcement missing for {spell.security_id}")
        for old_start, old_end in seen.setdefault(spell.security_id, []):
            if begin <= old_end and (pd.isna(finish) or finish >= old_start):
                raise DataContractError(f"overlapping membership spells for {spell.security_id}")
        seen[spell.security_id].append((begin, finish if not pd.isna(finish) else pd.Timestamp.max.normalize()))
        required = cal[(cal >= begin) & ((cal <= finish) if not pd.isna(finish) else True)]
        event = terminal.get(spell.security_id)
        if event is not None:
            required = required[required < _date(event.date)]
        frame = dataset.prices.get(spell.security_id)
        if len(required) and (frame is None or len(required.difference(frame.index))):
            gaps.append(f"missing member-session prices for {spell.security_id}; no delisting proceeds may be invented")
    # A disappearing series is not converted into a sale at its last observed close.
    for sid, frame in dataset.prices.items():
        if frame.index[-1] < cal[-1] and sid not in terminal:
            relevant = any(s.security_id == sid and _date(s.start) <= cal[-1]
                           and (pd.isna(s.end) or _date(s.end) >= cal[0])
                           for s in dataset.membership)
            if relevant:
                # Index removal is not a cash realization. A stock selected before
                # removal may still be held until the next portfolio formation.
                gaps.append(f"unknown terminal outcome / truncated relevant history for {sid}")
    gaps = list(dict.fromkeys(gaps))
    if strict and gaps:
        raise DataContractError("validated research blocked:\n- " + "\n- ".join(gaps))
    dataset.metadata["validated"] = bool(strict and not gaps)
    dataset.metadata["deployment_blocked"] = not dataset.metadata["validated"]
    dataset.metadata["data_quality_gaps"] = gaps
    return gaps


def audit_dataset(dataset: ResearchDataset, *, start=None, end=None) -> dict:
    previous = dict(dataset.metadata)
    try:
        gaps = validate_dataset(dataset, start=start, end=end, strict=False)
    finally:
        dataset.metadata.clear()
        dataset.metadata.update(previous)
    return {"mode": dataset.metadata.get("mode"), "security_count": len(dataset.securities),
            "price_count": len(dataset.prices), "first_session": str(dataset.calendar[0].date()),
            "last_session": str(dataset.calendar[-1].date()), "complete": not gaps,
            "deployment_blocked": bool(gaps) or dataset.metadata.get("mode") != "validated",
            "gaps": gaps}


def load_dataset(folder, *, mode="validated", cutoff=None) -> ResearchDataset:
    """Load a portable bundle without returning rows after ``cutoff``.

    manifest.json contains price_basis and certified completeness/provenance flags.
    securities.csv: security_id,symbol,source,dividend_status.
    membership.csv: security_id,start,end,known_at,source[,end_known_at].
    calendar.csv: date (actual supplied SPY sessions).
    prices/<security_id>.csv: date,open,high,low,close[,volume,dividends].
    Optional dividends.csv: security_id,date,cash_per_share,source; amounts must use
    the same split-adjusted share basis as prices. Optional terminal_events.csv:
    security_id,date,cash_per_share,source[,kind,known_at]. Zero proceeds are explicit.

    ``known_zero`` is an explicit sourced historical dividend declaration; missing
    events in an ``unknown`` history are never assumed to mean zero.
    """
    from screener.data import normalise

    if mode not in ("validated", "exploratory", "legacy_qlib"):
        raise DataContractError("mode must be validated, exploratory or legacy_qlib")
    folder = Path(folder)
    manifest_path = folder / "manifest.json"
    metadata = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    metadata = dict(metadata.get("metadata", metadata))
    metadata["mode"] = mode
    ulps = _declared_ohlc_precision(metadata, strict=mode == "validated")
    boundary = _date(cutoff) if cutoff is not None else None
    metadata["cutoff"] = str(boundary.date()) if boundary is not None else None
    if not manifest_path.exists() and mode == "validated":
        raise DataContractError("validated research requires manifest.json provenance/completeness declarations")
    def table(name, required=False):
        path = folder / name
        if not path.exists():
            if required:
                raise DataContractError(f"missing required {name}")
            return pd.DataFrame()
        return pd.read_csv(path, dtype={"security_id": str}, keep_default_na=False,
                           float_precision="round_trip")
    master = table("securities.csv", required=True)
    for col in ("security_id", "symbol", "source", "dividend_status"):
        if col not in master:
            raise DataContractError(f"securities.csv missing {col}")
    securities = tuple(SecurityRecord(str(r.security_id), str(r.symbol), str(r.source), str(r.dividend_status))
                       for r in master.itertuples())
    calendar_rows = table("calendar.csv", required=True)
    if "date" not in calendar_rows:
        raise DataContractError("calendar.csv missing date")
    calendar = explicit_sessions(pd.to_datetime(calendar_rows.date))
    if boundary is not None:
        calendar = calendar[calendar <= boundary]
    calendar = explicit_sessions(calendar)
    prices, dividends = {}, {}
    cash_rows = table("dividends.csv")
    cash_file = (folder / "dividends.csv").exists()
    if cash_file and not {"security_id", "date", "cash_per_share", "source"}.issubset(cash_rows.columns):
        raise DataContractError("dividends.csv missing required columns")
    if cash_file and set(cash_rows.security_id) - {s.security_id for s in securities}:
        raise DataContractError("dividends.csv references an unknown security_id")
    if cash_file and len(cash_rows) and (cash_rows.source.astype(str).str.strip() == "").any():
        raise DataContractError("dividend event source provenance is missing")
    for security in securities:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", security.security_id) or security.security_id in (".", ".."):
            raise DataContractError("unsafe security_id for price filename")
        path = folder / "prices" / f"{security.security_id}.csv"
        if not path.exists():
            continue  # Coverage audit, rather than symbol dropping, handles absent files.
        raw = pd.read_csv(path, float_precision="round_trip")
        if boundary is not None:
            if "date" not in raw:
                raise DataContractError(f"{path.name} missing date")
            raw = raw[pd.to_datetime(raw.date) <= boundary]
        if raw.empty:
            continue
        frame = normalise(raw, float32_ulps=ulps)
        frame.attrs["price_basis"] = metadata.get("price_basis", "unknown")
        prices[security.security_id] = frame
        if "dividends" in frame:
            dividends[security.security_id] = frame.dividends.copy()
        elif cash_file and security.dividend_status == "complete":
            events = cash_rows[cash_rows.security_id == security.security_id].copy()
            events["date"] = pd.to_datetime(events.date)
            if boundary is not None:
                events = events[events.date <= boundary]
            if events.date.duplicated().any():
                raise DataContractError(f"duplicate dividend events for {security.security_id}; consolidate explicitly")
            dividends[security.security_id] = pd.Series(pd.to_numeric(events.cash_per_share).to_numpy(),
                                                        index=pd.DatetimeIndex(events.date), dtype=float).sort_index()
        elif security.dividend_status == "known_zero":
            dividends[security.security_id] = pd.Series(0.0, index=frame.index)
    membership_rows = table("membership.csv", required=mode == "validated")
    membership = []
    if not membership_rows.empty:
        if not {"security_id", "start", "end", "known_at", "source"}.issubset(membership_rows.columns):
            raise DataContractError("membership.csv missing required columns")
        for r in membership_rows.to_dict("records"):
            begin = _date(r["start"])
            if boundary is not None and begin > boundary:
                continue
            finish = _date(r["end"], optional=True)
            # Future exits are not exposed to development-period consumers.
            if boundary is not None and not pd.isna(finish) and finish > boundary:
                finish = pd.NaT
                r["end_known_at"] = None
            membership.append(MembershipSpell(r["security_id"], begin, finish,
                _date(r["known_at"], optional=True), str(r["source"]),
                _date(r.get("end_known_at"), optional=True)))
    terminal_rows = table("terminal_events.csv")
    terminal_events = []
    if not terminal_rows.empty:
        if not {"security_id", "date", "cash_per_share", "source"}.issubset(terminal_rows.columns):
            raise DataContractError("terminal_events.csv missing required columns")
        for r in terminal_rows.to_dict("records"):
            when = _date(r["date"])
            if boundary is not None and when > boundary:
                continue
            terminal_events.append(TerminalEvent(r["security_id"], when, float(r["cash_per_share"]),
                str(r["source"]), str(r.get("kind") or "delisting"), _date(r.get("known_at"), optional=True)))
    dataset = ResearchDataset(prices, calendar, securities, tuple(membership), dividends,
                              tuple(terminal_events), metadata)
    validate_dataset(dataset, strict=mode == "validated")
    return dataset
