"""Tests for agentic/calendar.py: NYSE holidays, closed bars, execution session, plan expiry (incl. DST)."""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentic import calendar as cal  # noqa: E402

UTC = timezone.utc


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def ds(year, *md):
    return {date(year, m, d) for m, d in md}


# Official NYSE full-day holiday schedules.
NYSE = {
    2021: ds(2021, (1, 1), (1, 18), (2, 15), (4, 2), (5, 31), (7, 5), (9, 6), (11, 25), (12, 24)),
    2022: ds(2022, (1, 17), (2, 21), (4, 15), (5, 30), (6, 20), (7, 4), (9, 5), (11, 24), (12, 26)),
    2024: ds(2024, (1, 1), (1, 15), (2, 19), (3, 29), (5, 27), (6, 19), (7, 4), (9, 2), (11, 28), (12, 25)),
    2025: ds(2025, (1, 1), (1, 20), (2, 17), (4, 18), (5, 26), (6, 19), (7, 4), (9, 1), (11, 27), (12, 25)),
    2026: ds(2026, (1, 1), (1, 19), (2, 16), (4, 3), (5, 25), (6, 19), (7, 3), (9, 7), (11, 26), (12, 25)),
    2027: ds(2027, (1, 1), (1, 18), (2, 15), (3, 26), (5, 31), (6, 18), (7, 5), (9, 6), (11, 25), (12, 24)),
    2028: ds(2028, (1, 17), (2, 21), (4, 14), (5, 29), (6, 19), (7, 4), (9, 4), (11, 23), (12, 25)),
}


@pytest.mark.parametrize("year", sorted(NYSE))
def test_nyse_holidays_match_official_lists(year):
    assert cal.nyse_holidays(year) == NYSE[year]


def test_saturday_new_year_not_observed_on_dec_31():
    assert date(2022, 1, 1).weekday() == 5 and date(2028, 1, 1).weekday() == 5
    assert cal.is_trading_day(date(2021, 12, 31))
    assert cal.is_trading_day(date(2027, 12, 31))
    assert not any(d.month == 1 and d.day <= 3 for d in cal.nyse_holidays(2028))


def test_observed_rules_and_juneteenth_start():
    assert date(2027, 6, 18) in cal.nyse_holidays(2027)        # Sat Jun 19 -> Fri
    assert date(2022, 6, 20) in cal.nyse_holidays(2022)        # Sun Jun 19 -> Mon
    assert not any(d.month == 6 for d in cal.nyse_holidays(2021))
    assert date(2023, 1, 2) in cal.nyse_holidays(2023)         # Sun Jan 1 -> Mon


def test_nyse_holidays_returns_a_copy():
    h = cal.nyse_holidays(2026)
    h.add(date(2026, 3, 3))
    assert date(2026, 3, 3) not in cal.nyse_holidays(2026)


@pytest.mark.parametrize("year,expected", [(2019, date(2019, 4, 21)), (2024, date(2024, 3, 31)),
                                           (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)),
                                           (2027, date(2027, 3, 28)), (2038, date(2038, 4, 25)),
                                           (2285, date(2285, 3, 22))])
def test_easter(year, expected):
    assert cal.easter(year) == expected


def test_is_trading_day():
    assert cal.is_trading_day(date(2026, 10, 16))              # Friday
    assert not cal.is_trading_day(date(2026, 10, 17))          # Saturday
    assert not cal.is_trading_day(date(2026, 10, 18))          # Sunday
    assert not cal.is_trading_day(date(2026, 11, 26))          # Thanksgiving
    assert cal.is_trading_day(date(2026, 11, 27))              # half day counts as a session
    assert not cal.is_trading_day(date(2025, 1, 9))            # national day of mourning
    assert not cal.is_trading_day(datetime(2026, 4, 3, 12))    # Good Friday, datetime input


def test_next_previous_and_range():
    assert cal.next_trading_day(date(2026, 4, 2)) == date(2026, 4, 6)
    assert cal.previous_trading_day(date(2026, 4, 6)) == date(2026, 4, 2)
    assert cal.trading_days(date(2026, 11, 23), date(2026, 11, 30)) == [
        date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27), date(2026, 11, 30)]
    assert len(cal.trading_days(date(2026, 1, 1), date(2026, 12, 31))) == 251


# 16:20 ET is 20:20 UTC under EDT and 21:20 UTC under EST. DST 2026: starts Sun Mar 8, ends Sun Nov 1.
@pytest.mark.parametrize("now,expected", [
    (utc(2026, 10, 16, 20, 19, 59), date(2026, 10, 15)),       # Fri, EDT: 16:19:59 ET
    (utc(2026, 10, 16, 20, 20), date(2026, 10, 16)),           # 16:20 ET
    (utc(2026, 10, 30, 20, 20), date(2026, 10, 30)),           # last EDT Friday
    (utc(2026, 11, 2, 20, 20), date(2026, 10, 30)),            # first EST Monday: 15:20 ET, not yet
    (utc(2026, 11, 2, 21, 19), date(2026, 10, 30)),
    (utc(2026, 11, 2, 21, 20), date(2026, 11, 2)),
    (utc(2026, 3, 6, 20, 20), date(2026, 3, 5)),               # last EST Friday: 15:20 ET
    (utc(2026, 3, 6, 21, 20), date(2026, 3, 6)),
    (utc(2026, 3, 9, 20, 19), date(2026, 3, 6)),               # first EDT Monday
    (utc(2026, 3, 9, 20, 20), date(2026, 3, 9)),
    (utc(2026, 10, 17, 3, 0), date(2026, 10, 16)),             # Fri 23:00 ET
    (utc(2026, 10, 18, 15, 0), date(2026, 10, 16)),            # Sunday
    (utc(2026, 10, 19, 13, 0), date(2026, 10, 16)),            # Monday morning
    (utc(2026, 11, 26, 22, 0), date(2026, 11, 25)),            # Thanksgiving evening
    (utc(2026, 11, 27, 21, 20), date(2026, 11, 27)),           # half day, held back to 16:20
    (utc(2026, 4, 6, 14, 0), date(2026, 4, 2)),                # Monday after Good Friday
    (utc(2026, 1, 1, 23, 0), date(2025, 12, 31)),              # New Year's Day
    (utc(2027, 12, 31, 21, 20), date(2027, 12, 31)),           # Dec 31 before a Saturday New Year trades
])
def test_last_closed_equity_session(now, expected):
    assert cal.last_closed_equity_session(now) == expected


def test_now_argument_forms():
    aware_et = datetime(2026, 10, 16, 16, 20, tzinfo=cal.ET)
    assert cal.last_closed_equity_session(aware_et) == date(2026, 10, 16)
    assert cal.last_closed_equity_session(datetime(2026, 10, 16, 20, 20)) == date(2026, 10, 16)   # naive = UTC
    assert cal.last_closed_equity_session(pd.Timestamp("2026-10-16 20:19", tz="UTC")) == date(2026, 10, 15)
    assert isinstance(cal.last_closed_equity_session(), date)
    with pytest.raises(TypeError):
        cal.as_utc(date(2026, 10, 16))


def test_last_closed_crypto_bar():
    assert cal.last_closed_crypto_bar(utc(2026, 10, 18, 0, 0)) == date(2026, 10, 17)
    assert cal.last_closed_crypto_bar(utc(2026, 10, 17, 23, 59, 59)) == date(2026, 10, 16)
    assert cal.last_closed_crypto_bar(datetime(2026, 10, 17, 21, 0, tzinfo=cal.ET)) == date(2026, 10, 17)
    assert cal.last_closed_crypto_bar(utc(2026, 1, 1, 0, 0)) == date(2025, 12, 31)


@pytest.mark.parametrize("now,expected", [
    (utc(2026, 10, 16, 19, 44, 59), date(2026, 10, 16)),       # 15:44:59 EDT
    (utc(2026, 10, 16, 19, 45), date(2026, 10, 19)),           # 15:45 EDT -> Monday
    (utc(2026, 11, 10, 20, 44), date(2026, 11, 10)),           # 15:44 EST
    (utc(2026, 11, 10, 20, 45), date(2026, 11, 11)),
    (utc(2026, 10, 16, 3, 0), date(2026, 10, 16)),             # Thu 23:00 ET -> Friday
    (utc(2026, 10, 19, 10, 0), date(2026, 10, 19)),            # before the open
    (utc(2026, 10, 17, 15, 0), date(2026, 10, 19)),            # Saturday
    (utc(2026, 11, 26, 15, 0), date(2026, 11, 27)),            # Thanksgiving
    (utc(2026, 4, 2, 20, 0), date(2026, 4, 6)),                # Thu after cutoff, Good Friday next
])
def test_execution_session(now, expected):
    assert cal.execution_session(now) == expected


@pytest.mark.parametrize("now,expected", [
    (utc(2026, 10, 16, 1, 0), utc(2026, 10, 16, 19, 45)),      # EDT
    (utc(2026, 10, 31, 12, 0), utc(2026, 11, 2, 20, 45)),      # weekend across the fall change -> EST
    (utc(2026, 3, 7, 12, 0), utc(2026, 3, 9, 19, 45)),         # weekend across the spring change -> EDT
    (utc(2026, 3, 6, 20, 0), utc(2026, 3, 6, 20, 45)),         # EST Friday 15:00 ET
    (utc(2026, 12, 24, 21, 0), utc(2026, 12, 28, 20, 45)),     # Christmas Friday
])
def test_valid_until_equity(now, expected):
    got = cal.valid_until("equity", now, {})
    assert got == expected
    assert got.utcoffset() == timedelta(0)


def test_valid_until_crypto():
    now = utc(2026, 10, 17, 1, 0)
    assert cal.valid_until("crypto", now, {"plan_valid_min_crypto": 360}) == utc(2026, 10, 17, 7, 0)
    assert cal.valid_until("crypto", now, {"plan_valid_min_crypto": 60}) == utc(2026, 10, 17, 2, 0)
    assert cal.valid_until("crypto", now, {}) == now + timedelta(minutes=360)
    with pytest.raises(ValueError):
        cal.valid_until("option", now, {})


@pytest.mark.parametrize("now,expected", [
    (utc(2026, 10, 16, 13, 29), False),
    (utc(2026, 10, 16, 13, 30), True),                         # 09:30 EDT
    (utc(2026, 10, 16, 19, 59), True),
    (utc(2026, 10, 16, 20, 0), False),                         # 16:00 EDT
    (utc(2026, 11, 2, 14, 29), False),                         # EST
    (utc(2026, 11, 2, 14, 30), True),
    (utc(2026, 11, 2, 20, 59), True),
    (utc(2026, 11, 2, 21, 0), False),
    (utc(2026, 10, 17, 15, 0), False),                         # Saturday
    (utc(2026, 11, 26, 15, 0), False),                         # Thanksgiving
])
def test_market_open(now, expected):
    assert cal.market_open(now) is expected


def test_et_date():
    assert cal.et_date(utc(2026, 10, 17, 3, 59)) == date(2026, 10, 16)
    assert cal.et_date(utc(2026, 10, 17, 4, 0)) == date(2026, 10, 17)
