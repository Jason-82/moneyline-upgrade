from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from .common import TradingError, iso, stamp


@dataclass(frozen=True)
class Session:
    date: str
    open: str
    close: str


class SavedCalendar:
    """Replay a recorded exchange schedule, never a weekday/holiday heuristic."""

    def __init__(self, records: Iterable[dict], settlement_minutes: int = 20):
        self.sessions = [Session(str(r["date"]), iso(r["open"]), iso(r["close"])) for r in records]
        if not self.sessions or settlement_minutes < 0:
            raise TradingError("A complete exchange calendar is required")
        dates = [r.date for r in self.sessions]
        if dates != sorted(set(dates)):
            raise TradingError("Calendar dates must be unique and sorted")
        for r in self.sessions:
            if stamp(r.open) >= stamp(r.close):
                raise TradingError("Invalid calendar session interval")
            if stamp(r.open).date().isoformat() != r.date:
                raise TradingError("Calendar date and UTC open disagree")
        # Saved timestamps are replay inputs, not authority: verify against the installed
        # exchange calendar so a missing session cannot be hidden by deleting it twice.
        from research.calendar import nyse_schedule
        try:
            expected = nyse_schedule(dates[0], dates[-1])
        except Exception as exc:
            raise TradingError("Saved calendar has no valid authoritative session coverage") from exc
        authoritative = [(str(date.date()), iso(row["open"].to_pydatetime()), iso(row["close"].to_pydatetime()))
                         for date, row in expected.iterrows()]
        actual = [(r.date, r.open, r.close) for r in self.sessions]
        if actual != authoritative:
            raise TradingError("Saved calendar differs from authoritative XNYS session schedule")
        self.settlement_minutes = settlement_minutes

    @classmethod
    def from_exchange(cls, start: str, end: str) -> "SavedCalendar":
        from research.calendar import nyse_schedule
        frame = nyse_schedule(start, end)
        return cls([{"date": str(date.date()), "open": iso(row["open"].to_pydatetime()),
                     "close": iso(row["close"].to_pydatetime())} for date, row in frame.iterrows()])

    def latest_completed(self, now: str) -> Session:
        when = stamp(now)
        finished = [r for r in self.sessions if stamp(r.close) + timedelta(minutes=self.settlement_minutes) <= when]
        if not finished:
            raise TradingError("No settled completed session in supplied calendar")
        result = finished[-1]
        # Demand coverage of the next session; an old truncated calendar cannot make stale bars look fresh.
        following = self.next_session(result.date)
        if when >= stamp(following.close) + timedelta(minutes=self.settlement_minutes):
            raise TradingError("Calendar does not cover the latest completed session")
        return result

    def next_session(self, date: str) -> Session:
        if date not in {r.date for r in self.sessions}:
            raise TradingError("As-of date is not in the supplied exchange calendar")
        following = [r for r in self.sessions if r.date > date]
        if not following:
            raise TradingError("Calendar must include the next trading session")
        return following[0]

    def dates_between(self, start: str, end: str) -> list[str]:
        if start not in {r.date for r in self.sessions} or end not in {r.date for r in self.sessions}:
            raise TradingError("Calendar must cover the entire signal history")
        return [r.date for r in self.sessions if start <= r.date <= end]
