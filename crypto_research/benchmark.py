"""Actual SPY dividend-adjusted passive benchmark, never an indicator input.

The provider's adjusted-close index assumes frictionless dividend reinvestment.
It cannot identify an investor's after-tax return, dividend payment-date cash
flows, or actual dividend-reinvestment fills. Only entry and terminal exit costs
are applied here. Missing NYSE sessions are errors, not forward-filled prices.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.calendar import nyse_schedule


class BenchmarkDataError(ValueError):
    """The declared SPY comparison cannot be identified from this input."""


def _date(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None or stamp != stamp.normalize():
        raise BenchmarkDataError("benchmark horizons require naive normalized session dates")
    return stamp


def _session_date(seconds) -> pd.Timestamp:
    return (pd.to_datetime(seconds, unit="s", utc=True)
            .tz_convert("America/New_York").tz_localize(None).normalize())


def _sessions(start, end) -> pd.DatetimeIndex:
    # Calendar constructors need at least one session and distinct bounds, even
    # when a caller's legitimate horizon is a holiday or a single calendar day.
    calendar = nyse_schedule(start - pd.Timedelta(days=10), end + pd.Timedelta(days=10)).index
    return calendar[(calendar >= start) & (calendar <= end)]


def _validate_frame(frame: pd.DataFrame, start, end) -> None:
    start, end = _date(start), _date(end)
    if end < start:
        raise BenchmarkDataError("benchmark end precedes start")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise BenchmarkDataError("benchmark requires a date index")
    if (frame.index.tz is not None or frame.index.has_duplicates or
            frame.index.hasnans or not frame.index.is_monotonic_increasing or
            not frame.index.equals(frame.index.normalize())):
        raise BenchmarkDataError("benchmark dates must be unique ascending normalized dates")
    required = ["open", "high", "low", "close", "volume", "adjusted_close", "adjusted_open", "dividend"]
    if any(field not in frame for field in required):
        raise BenchmarkDataError("benchmark requires raw OHLCV, adjusted open/close and dividends")
    expected = _sessions(start, end)
    observed = frame.index[(frame.index >= start) & (frame.index <= end)]
    missing, extra = expected.difference(observed), observed.difference(expected)
    if len(missing):
        raise BenchmarkDataError(f"SPY missing {len(missing)} NYSE sessions, first {missing[0].date()}")
    if len(extra):
        raise BenchmarkDataError(f"SPY contains non-NYSE session {extra[0].date()}")
    values = frame.loc[start:end, required].to_numpy(float)
    if not np.isfinite(values).all():
        raise BenchmarkDataError("SPY contains missing or nonfinite benchmark values")
    if len(values):
        if np.any(values[:, :4] <= 0) or np.any(values[:, 5:7] <= 0):
            raise BenchmarkDataError("SPY price values must be positive")
        if np.any(values[:, 4] < 0) or np.any(values[:, 7] < 0):
            raise BenchmarkDataError("SPY volume and dividends must be nonnegative")
        if np.any(values[:, 2] > np.minimum(values[:, 0], values[:, 3])) or np.any(values[:, 1] < np.maximum(values[:, 0], values[:, 3])):
            raise BenchmarkDataError("SPY has impossible raw OHLC ranges")
        consistent_open = values[:, 0] * values[:, 5] / values[:, 3]
        if not np.allclose(values[:, 6], consistent_open, rtol=1e-12, atol=1e-12):
            raise BenchmarkDataError("SPY adjusted open does not share adjusted close's factor")


def normalise_yahoo_chart(payload: dict, start, end) -> tuple[pd.DataFrame, dict]:
    """Validate one bounded Yahoo chart response and its dividend adjustments.

    Adjustment factors may reflect distributions after the requested historical
    end. Such a common normalization cancels in historical return ratios. No
    later price row, current quote, or current valuation is used.
    """
    start, end = _date(start), _date(end)
    chart = payload.get("chart", {})
    if chart.get("error") or len(chart.get("result") or []) != 1:
        raise BenchmarkDataError("Yahoo did not return exactly one successful chart result")
    result = chart["result"][0]
    meta = result.get("meta", {})
    if meta.get("symbol") != "SPY" or meta.get("currency") != "USD":
        raise BenchmarkDataError("benchmark must be actual SPY quoted in USD")
    if meta.get("exchangeTimezoneName") != "America/New_York":
        raise BenchmarkDataError("unexpected SPY exchange timezone")
    if meta.get("dataGranularity") != "1d":
        raise BenchmarkDataError("benchmark requires regular daily bars")
    timestamps = result.get("timestamp") or []
    if not timestamps:
        raise BenchmarkDataError("Yahoo SPY response contains no bars")
    index = pd.DatetimeIndex([_session_date(value) for value in timestamps], name="date")
    indicators = result.get("indicators", {})
    try:
        quote = indicators["quote"][0]
        adjusted = indicators["adjclose"][0]["adjclose"]
        frame = pd.DataFrame({field: quote[field] for field in ("open", "high", "low", "close", "volume")}, index=index)
        frame["adjusted_close"] = adjusted
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise BenchmarkDataError("Yahoo SPY quote and adjusted-close arrays are incomplete") from exc
    if np.any(index < start) or np.any(index > end):
        raise BenchmarkDataError("Yahoo returned price rows outside the declared historical bounds")
    events = result.get("events") or {}
    if events.get("splits"):
        raise BenchmarkDataError("unexpected SPY split event; explicit split reconciliation required")
    frame["dividend"] = 0.0
    dividend_count = 0
    for event in (events.get("dividends") or {}).values():
        try:
            date, amount = _session_date(event["date"]), float(event["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BenchmarkDataError("invalid SPY dividend event") from exc
        if date not in index or not np.isfinite(amount) or amount <= 0:
            raise BenchmarkDataError("SPY dividend must have a positive amount and actual session bar")
        frame.loc[date, "dividend"] += amount
        dividend_count += 1
    frame["adjusted_open"] = frame["open"] * frame["adjusted_close"] / frame["close"]
    _validate_frame(frame, start, end)
    # Yahoo backward adjusts the preceding close by 1 - cash dividend / close.
    # Check every factor transition, including non-event days, so missing events
    # cannot silently turn price-only data into a total-return claim. Float32
    # provider adjusted-close rounding is allowed, without changing any prices.
    factor = frame["adjusted_close"] / frame["close"]
    observed = factor.shift(1) / factor
    expected = 1 - frame["dividend"] / frame["close"].shift(1)
    error = (observed.iloc[1:] - expected.iloc[1:]).abs()
    if np.any(error > 5e-6):
        raise BenchmarkDataError("SPY dividend events do not reconcile to adjusted-close factors")
    receipt = {"source": "Yahoo Finance chart API", "symbol": "SPY", "currency": "USD",
               "price_basis": "provider_dividend_adjusted_total_return_index",
               "start": start.date().isoformat(), "end": end.date().isoformat(),
               "first_session": frame.index[0].date().isoformat(), "last_session": frame.index[-1].date().isoformat(),
               "rows": len(frame), "dividend_events": dividend_count,
               "max_adjustment_reconciliation_error": float(error.max()) if len(error) else 0.0,
               "adjustment_reconciliation_tolerance": 5e-6,
               "calendar": "XNYS", "all_sessions_present": True,
               "dividend_reinvestment": "provider adjusted-close convention, frictionless",
               "adjusted_open": "raw open * adjusted close / raw close",
               "after_tax_identified": False,
               "current_meta_prices_used": False,
               "known_limitations": ["Provider dividend adjustment is a passive return-index approximation, not an executable cash ledger",
                                      "No dividend-reinvestment commissions or payment-date cash drag modeled",
                                      "XNYS regular-session dates approximate NYSE Arca's standard equity trading calendar"]}
    return frame, receipt


def load_spy_benchmark(directory: str | Path) -> pd.DataFrame:
    """Load a checksummed, validated SPY.csv + manifest.json benchmark bundle."""
    directory = Path(directory)
    try:
        receipt = json.loads((directory / "manifest.json").read_text())
        raw_csv = (directory / "SPY.csv").read_bytes()
    except (OSError, ValueError) as exc:
        raise BenchmarkDataError("SPY benchmark bundle is unavailable") from exc
    if receipt.get("symbol") != "SPY" or receipt.get("currency") != "USD" or receipt.get("price_basis") != "provider_dividend_adjusted_total_return_index":
        raise BenchmarkDataError("SPY benchmark receipt has an unknown identity or price basis")
    if hashlib.sha256(raw_csv).hexdigest() != receipt.get("csv_sha256"):
        raise BenchmarkDataError("SPY.csv does not match its frozen receipt checksum")
    raw_path = directory / "SPY_yahoo_chart_raw.json"
    if raw_path.exists() and hashlib.sha256(raw_path.read_bytes()).hexdigest() != receipt.get("raw_sha256"):
        raise BenchmarkDataError("raw SPY response does not match its receipt checksum")
    frame = pd.read_csv(directory / "SPY.csv", index_col="date", parse_dates=["date"], float_precision="round_trip")
    _validate_frame(frame, receipt["start"], receipt["end"])
    if len(frame) != receipt.get("rows"):
        raise BenchmarkDataError("SPY benchmark row count does not match receipt")
    frame.attrs["benchmark_receipt"] = receipt
    return frame


def spy_buy_and_hold(frame: pd.DataFrame, start, end, *, cost_bps: float = 3.0,
                     initial_capital: float = 100_000.0, liquidate_at_end: bool = True) -> pd.Series:
    """Daily UTC-date EOD wealth for one actual SPY purchase over a crypto horizon.

    A crypto Jan 1 start remains cash until SPY's first actual regular-session
    open. Official US session-close marks occur before each UTC day ends. Only
    non-session holding marks are carried forward; they are never synthetic
    trades. Terminal liquidation uses the last actual session close in horizon.
    """
    start, end = _date(start), _date(end)
    _validate_frame(frame, start, end)
    if not np.isfinite(initial_capital) or initial_capital <= 0:
        raise BenchmarkDataError("benchmark initial capital must be positive")
    if not np.isfinite(cost_bps) or not 0 <= cost_bps < 10_000:
        raise BenchmarkDataError("benchmark per-side cost must be in [0, 10000) basis points")
    days = pd.date_range(start, end, freq="D", name="date")
    sessions = _sessions(start, end)
    path = pd.Series(initial_capital, index=days, name="SPY_buy_and_hold", dtype=float)
    if not len(sessions):
        path.attrs["entry_session"] = None
        return path
    first, last = sessions[0], sessions[-1]
    cost = cost_bps / 10_000.0
    units = initial_capital / (float(frame.loc[first, "adjusted_open"]) * (1 + cost))
    marked = frame.loc[sessions, "adjusted_close"] * units
    if liquidate_at_end:
        marked.iloc[-1] *= 1 - cost
    path.loc[first:] = marked.reindex(days[days >= first]).ffill()
    path.attrs.update({"entry_session": first.date().isoformat(), "terminal_session": last.date().isoformat(),
                       "cost_bps_per_side": cost_bps, "terminal_liquidation": bool(liquidate_at_end),
                       "price_basis": "provider_dividend_adjusted_total_return_index", "currency": "USD",
                       "tax_status": "pretax_only", "marking": "US close carried across non-session days only",
                       "dividend_reinvestment": "provider convention, frictionless"})
    return path
