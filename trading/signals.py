from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026.moneyline_ref import MONEYLINE_PARAMS, moneyline
from .calendar import SavedCalendar
from .common import TradingError, digest, number, symbol


def compute_signals(bundle: dict, calendar: SavedCalendar, now: str, symbols: list[str], minimum_bars: int = 100) -> dict:
    """Closed, settled daily split-only OHLC into exact reference indicator states."""
    if bundle.get("adjustment_type") != "split" or bundle.get("interval") != "day":
        raise TradingError("Signal inputs must be daily split-only OHLC")
    if minimum_bars < 100:
        raise TradingError("The frozen implementation requires at least 100 warm-up bars")
    asof = calendar.latest_completed(now).date
    signals = {}
    for ticker in symbols:
        symbol(ticker)
        records = bundle.get("bars", {}).get(ticker, [])
        if len(records) < minimum_bars:
            raise TradingError(f"{ticker}: insufficient signal history")
        dates = [str(r["date"]) for r in records]
        if dates != sorted(set(dates)) or dates[-1] != asof:
            raise TradingError(f"{ticker}: history must end at the exact latest completed session")
        if dates != calendar.dates_between(dates[0], asof):
            raise TradingError(f"{ticker}: missing, extra or non-session daily bars")
        frame = pd.DataFrame(records).set_index("date")
        frame.index = pd.to_datetime(frame.index)
        values = frame[["open", "high", "low", "close"]].astype(float)
        if not np.isfinite(values.to_numpy()).all() or (values <= 0).any().any():
            raise TradingError(f"{ticker}: invalid OHLC values")
        if ((values.high < values[["open", "close", "low"]].max(axis=1)) |
                (values.low > values[["open", "close", "high"]].min(axis=1))).any():
            raise TradingError(f"{ticker}: inconsistent OHLC range")
        official = bundle.get("official_closes", {}).get(ticker)
        if not official or official.get("date") != asof or official.get("interpolated") is not False:
            raise TradingError(f"{ticker}: exact official settled close confirmation is required")
        close = number(records[-1]["close"])
        confirmed = number(official.get("price"))
        if close <= 0 or confirmed <= 0 or abs(close - confirmed) > max(number("0.000001"), confirmed * number("0.000001")):
            raise TradingError(f"{ticker}: official close differs from signal close")
        output = moneyline(values)
        last = output.iloc[-1]
        if not np.isfinite(last.line):
            raise TradingError(f"{ticker}: undefined signal")
        signals[ticker] = {"green": bool(last.green), "flip": int(last.flip), "line": float(last.line),
                           "close": str(close), "bar_count": len(records), "history_sha256": digest(records)}
    source_file = Path(__file__).resolve().parents[1] / "analysis_2026" / "moneyline_ref.py"
    return {"version": 1, "asof": asof, "params": MONEYLINE_PARAMS, "timeframe": "daily",
            "reference_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
            "data_sha256": digest(bundle), "signals": signals}
