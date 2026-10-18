"""NYSE trading calendar and bar timing. Standard library only, so the hooks can import it.

All `now_utc` arguments accept an aware datetime (any zone), a naive datetime taken as UTC, a pandas Timestamp, or
None for the current time. Limitation: half days (13:00 ET closes) are treated as full sessions, so a half-day bar is
held back until 16:20 ET and `market_open` reports the afternoon as open.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from agentic.config import DEFAULT_LIMITS

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
SESSION_OPEN = time(9, 30)
SESSION_CLOSE = time(16, 0)
CLOSE_SETTLED = time(16, 20)     # closing prints settle a little after 16:00
EXEC_CUTOFF = time(15, 45)       # equity plans expire here; later runs target the next session

# Unscheduled full-day closures (national days of mourning, Hurricane Sandy, 9/11). Add new ones here.
SPECIAL_CLOSURES = frozenset(date.fromisoformat(d) for d in (
    "2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14", "2004-06-11", "2007-01-02",
    "2012-10-29", "2012-10-30", "2018-12-05", "2025-01-09"))


def easter(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


@lru_cache(maxsize=None)
def _holidays(year: int) -> frozenset[date]:
    mon, thu = 0, 3
    h = {
        _nth_weekday(year, 2, mon, 3),            # Presidents' Day
        easter(year) - timedelta(days=2),         # Good Friday
        _last_weekday(year, 5, mon),              # Memorial Day
        _observed(date(year, 7, 4)),              # Independence Day
        _nth_weekday(year, 9, mon, 1),            # Labor Day
        _nth_weekday(year, 11, thu, 4),           # Thanksgiving
        _observed(date(year, 12, 25)),            # Christmas
    }
    if date(year, 1, 1).weekday() != 5:           # a Saturday New Year is not moved to Dec 31
        h.add(_observed(date(year, 1, 1)))
    if year >= 1998:
        h.add(_nth_weekday(year, 1, mon, 3))      # Martin Luther King Jr. Day
    if year >= 2022:
        h.add(_observed(date(year, 6, 19)))       # Juneteenth
    return frozenset(h)


def nyse_holidays(year: int) -> set[date]:
    """Scheduled full-day NYSE holidays of `year` (rule-based; see SPECIAL_CLOSURES for unscheduled ones)."""
    return set(_holidays(year))


def is_trading_day(d) -> bool:
    d = d.date() if isinstance(d, datetime) else d
    return d.weekday() < 5 and d not in _holidays(d.year) and d not in SPECIAL_CLOSURES


def next_trading_day(d) -> date:
    """First trading day strictly after `d`."""
    d = (d.date() if isinstance(d, datetime) else d) + timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def previous_trading_day(d) -> date:
    """Last trading day strictly before `d`."""
    d = (d.date() if isinstance(d, datetime) else d) - timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def trading_days(start, end) -> list[date]:
    """Trading days in [start, end]."""
    d = start.date() if isinstance(start, datetime) else start
    end = end.date() if isinstance(end, datetime) else end
    out = []
    while d <= end:
        if is_trading_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def as_utc(now_utc=None) -> datetime:
    """Aware UTC datetime from an aware/naive (taken as UTC) datetime or pandas Timestamp; None = now."""
    if now_utc is None:
        return datetime.now(UTC)
    if hasattr(now_utc, "to_pydatetime"):
        now_utc = now_utc.to_pydatetime()
    if not isinstance(now_utc, datetime):
        raise TypeError(f"expected a datetime, got {type(now_utc).__name__}")
    return now_utc.replace(tzinfo=UTC) if now_utc.tzinfo is None else now_utc.astimezone(UTC)


def et_now(now_utc=None) -> datetime:
    return as_utc(now_utc).astimezone(ET)


def et_date(now_utc=None) -> date:
    """The ET calendar date (the ledger's day)."""
    return et_now(now_utc).date()


def last_closed_equity_session(now_utc=None) -> date:
    """The latest trading day whose 16:20 ET has passed."""
    now = et_now(now_utc)
    d = now.date()
    if is_trading_day(d) and now.time() >= CLOSE_SETTLED:
        return d
    return previous_trading_day(d)


def last_closed_crypto_bar(now_utc=None) -> date:
    """UTC date of the latest fully closed daily crypto bar (bars are labelled by their 00:00 UTC open)."""
    return as_utc(now_utc).date() - timedelta(days=1)


def bar_close(asset_class: str, d: date, settled: bool = False) -> datetime:
    """When the daily bar `d` closes (aware UTC): 00:00 UTC the next day for crypto, 16:00 ET for stocks (16:20 ET
    with `settled`, when closing prints are final)."""
    if asset_class == "crypto":
        return datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=UTC)
    return datetime.combine(d, CLOSE_SETTLED if settled else SESSION_CLOSE, tzinfo=ET).astimezone(UTC)


def execution_session(now_utc=None) -> date:
    """Today if it is a trading day and it is before 15:45 ET, else the next trading day."""
    now = et_now(now_utc)
    d = now.date()
    if is_trading_day(d) and now.time() < EXEC_CUTOFF:
        return d
    return next_trading_day(d)


def valid_until(vehicle_type: str, now_utc=None, limits: dict | None = None) -> datetime:
    """Plan expiry (aware UTC): 15:45 ET on the execution session for equity vehicles, now + plan_valid_min_crypto
    for direct crypto."""
    now = as_utc(now_utc)
    if vehicle_type == "equity":
        return datetime.combine(execution_session(now), EXEC_CUTOFF, tzinfo=ET).astimezone(UTC)
    if vehicle_type == "crypto":
        mins = (limits or {}).get("plan_valid_min_crypto", DEFAULT_LIMITS["plan_valid_min_crypto"])
        return now + timedelta(minutes=float(mins))
    raise ValueError(f"vehicle_type must be 'equity' or 'crypto', got {vehicle_type!r}")


def market_open(now_utc=None) -> bool:
    """09:30-16:00 ET on a trading day (half days count as full sessions)."""
    now = et_now(now_utc)
    return is_trading_day(now.date()) and SESSION_OPEN <= now.time() < SESSION_CLOSE
