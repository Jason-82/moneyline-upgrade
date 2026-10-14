"""Explicit research sessions and exchange-aware completed US equity sessions.

Research uses the supplied SPY session index. Live data uses XNYS's actual closes,
including holidays and early closes; a weekday-only approximation is unsafe.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd


def explicit_sessions(index) -> pd.DatetimeIndex:
    """Validate a supplied, ordered, unique session-date calendar without inventing bars."""
    idx = pd.DatetimeIndex(pd.to_datetime(index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    if idx.hasnans or idx.has_duplicates or not idx.is_monotonic_increasing:
        raise ValueError("calendar must contain unique, ordered, nonmissing session dates")
    if not idx.equals(idx.normalize()) or not len(idx):
        raise ValueError("calendar must be nonempty and contain normalized session dates")
    return idx.rename("date")


@lru_cache(maxsize=16)
def _nyse_calendar(start: str, end: str):
    try:
        import exchange_calendars as xcals
    except ImportError as exc:
        raise RuntimeError("NYSE calendar unavailable: install exchange_calendars>=4.11,<5") from exc
    return xcals.get_calendar("XNYS", start=start, end=end)


def nyse_schedule(start, end) -> pd.DataFrame:
    """UTC regular-session open/close times, indexed by naive NYSE session dates."""
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    cal = _nyse_calendar(str(start), str(end))
    schedule = cal.schedule.loc[str(start):str(end)].copy()
    schedule = schedule.rename(columns={"market_open": "open", "market_close": "close"})
    result = schedule[["open", "close"]].copy()
    result.index = pd.DatetimeIndex(result.index).tz_localize(None).normalize()
    result.index.name = "date"
    for field in ("open", "close"):
        result[field] = pd.to_datetime(result[field], utc=True)
    return result


def last_completed_session(now=None, settlement_minutes: int = 20) -> pd.Timestamp:
    """Latest actual exchange session closed plus a closing-print settlement buffer.

Naive caller timestamps mean New York local time, matching equity session dates.
No fallback guesses a date when exchange-calendar support is unavailable.
"""
    stamp = pd.Timestamp.now(tz="America/New_York") if now is None else pd.Timestamp(now)
    stamp = stamp.tz_localize("America/New_York") if stamp.tzinfo is None else stamp
    utc = stamp.tz_convert("UTC")
    if settlement_minutes < 0:
        raise ValueError("settlement_minutes must be nonnegative")
    local_date = stamp.tz_convert("America/New_York").normalize().tz_localize(None)
    schedule = nyse_schedule(local_date - pd.Timedelta(days=40), local_date + pd.Timedelta(days=2))
    completed = schedule[schedule["close"] + pd.Timedelta(minutes=settlement_minutes) <= utc]
    if completed.empty:
        raise RuntimeError("no completed NYSE session in calendar window")
    return completed.index[-1]
