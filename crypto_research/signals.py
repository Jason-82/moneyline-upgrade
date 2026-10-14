"""Six fixed, causal daily signal candidates for the crypto research comparison.

The outputs describe exposure desired *after* the current closed candle.  The
portfolio engine must execute at the following UTC day's open.  Signals never
read that execution price and do not impose the experiment's common warm-up.

The two Donchian candidates adapt the paper's close-based channel ensemble:
channels include today's close, a new upper-channel high takes priority over
the prior stop, and surviving positions ratchet their midpoint stop for the
next candle.  The volatility candidate caps exposure at 100%, rather than the
paper's leveraged cap.  These are research candidates, not broker signals.
"""
from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from analysis_2026.moneyline_ref import moneyline


CANDIDATES: Final[tuple[str, ...]] = (
    "moneyline",
    "confirm2",
    "breakout20",
    "wider_exit3",
    "donchianensemble_fixed",
    "donchianensemble_vol25",
)
DONCHIAN_LOOKBACKS: Final[tuple[int, ...]] = (5, 10, 20, 30, 60, 90, 150, 250, 360)
VOLATILITY_LOOKBACK: Final[int] = 90
ANNUAL_VOLATILITY_TARGET: Final[float] = 0.25


def _ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the signal input without filling gaps or altering prices."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("signal input must be an OHLC DataFrame")
    if not df.index.is_unique or not df.index.is_monotonic_increasing:
        raise ValueError("signal index must be unique and increasing")
    renamed = df.rename(columns=lambda column: str(column).lower())
    required = ["open", "high", "low", "close"]
    if not renamed.columns.is_unique:
        raise ValueError("signal columns must be unique ignoring case")
    missing = set(required).difference(renamed.columns)
    if missing:
        raise ValueError(f"signal input is missing OHLC columns: {sorted(missing)}")
    out = renamed.loc[:, required].astype(float)
    values = out.to_numpy()
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("signal OHLC must be finite and positive; gaps must be handled explicitly")
    if (
        (out["high"] < out["low"])
        | (out["high"] < out[["open", "close"]].max(axis=1))
        | (out["low"] > out[["open", "close"]].min(axis=1))
    ).any():
        raise ValueError("signal OHLC range must contain open and close, with high at least low")
    return out


def donchian_component(close: pd.Series, lookback: int) -> pd.DataFrame:
    """One current-inclusive close channel and its long-only trailing state.

    ``stop`` is the active stop for the *following* candle.  Today's exit uses
    the prior active stop.  Equality with the upper channel has entry priority;
    otherwise equality with the prior stop exits.  Ratcheting is never reset by
    an upper-channel touch while an existing position remains open.
    """
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 2:
        raise ValueError("Donchian lookback must be an integer of at least two")
    if not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError("close index must be unique and increasing")
    close = close.astype(float)
    if not np.isfinite(close.to_numpy()).all() or (close <= 0).any():
        raise ValueError("Donchian closes must be finite and positive")
    upper = close.rolling(lookback, min_periods=lookback).max()
    lower = close.rolling(lookback, min_periods=lookback).min()
    midpoint = (upper + lower) / 2.0
    regimes = np.zeros(len(close), dtype=float)
    stops = np.full(len(close), np.nan)
    holding = False
    active_stop = np.nan
    for i, (price, channel_high, channel_mid) in enumerate(
        zip(close.to_numpy(), upper.to_numpy(), midpoint.to_numpy(), strict=True)
    ):
        if np.isnan(channel_high):
            continue
        if price == channel_high:
            if not holding:
                holding = True
                active_stop = channel_mid
            else:
                active_stop = max(active_stop, channel_mid)
        elif holding:
            if price <= active_stop:
                holding = False
                active_stop = np.nan
            else:
                active_stop = max(active_stop, channel_mid)
        regimes[i] = float(holding)
        stops[i] = active_stop
    return pd.DataFrame(
        {"regime": regimes, "upper": upper, "lower": lower, "midpoint": midpoint, "stop": stops},
        index=close.index,
    )


def _wider_exit(frame: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"].to_numpy()
    midpoint = ((frame["high"] + frame["low"]) / 2.0).to_numpy()
    atr = baseline["atr"].to_numpy()
    green = baseline["green"].to_numpy(dtype=bool)
    flip = baseline["flip"].to_numpy(dtype=int)
    regimes = np.zeros(len(frame), dtype=float)
    stops = np.full(len(frame), np.nan)
    holding = False
    seen_valid_atr = False
    active_stop = np.nan
    for i, price in enumerate(close):
        if np.isnan(atr[i]):
            continue
        initial_state = not seen_valid_atr
        seen_valid_atr = True
        raw_stop = midpoint[i] - 3.0 * atr[i]
        if holding:
            # This candidate intentionally tests the ratcheted current-day
            # Moneyline-style stop, unlike the Donchian previous-stop rule.
            active_stop = max(active_stop, raw_stop)
            if price < active_stop:
                holding = False
                active_stop = np.nan
        elif (initial_state and green[i]) or flip[i] == 1:
            holding = True
            active_stop = raw_stop
        regimes[i] = float(holding)
        stops[i] = active_stop
    return pd.DataFrame({"regime": regimes, "exit_stop": stops}, index=frame.index)


def explainable_signal_frame(df: pd.DataFrame, candidate: str) -> pd.DataFrame:
    """Return target/regime plus causal diagnostics for one fixed candidate."""
    if candidate not in CANDIDATES:
        raise ValueError(f"unknown candidate {candidate!r}; expected one of {CANDIDATES}")
    frame = _ohlc(df)
    if frame.empty:
        return pd.DataFrame({"target": pd.Series(dtype=float), "regime": pd.Series(dtype=float)}, index=frame.index)
    if candidate.startswith("donchianensemble_"):
        out = pd.DataFrame(index=frame.index)
        for lookback in DONCHIAN_LOOKBACKS:
            component = donchian_component(frame["close"], lookback)
            out[f"component_{lookback}"] = component["regime"]
            out[f"stop_{lookback}"] = component["stop"]
        components = [f"component_{lookback}" for lookback in DONCHIAN_LOOKBACKS]
        out["regime"] = out[components].mean(axis=1)
        if candidate == "donchianensemble_vol25":
            daily_return = frame["close"].pct_change(fill_method=None)
            annual_vol = daily_return.rolling(
                VOLATILITY_LOOKBACK, min_periods=VOLATILITY_LOOKBACK
            ).std(ddof=1) * np.sqrt(365.0)
            # Zero observed volatility permits full unleveraged exposure;
            # undefined volatility permits none until the 90 returns exist.
            scale = (ANNUAL_VOLATILITY_TARGET / annual_vol).clip(upper=1.0).fillna(0.0)
            out["annual_volatility"] = annual_vol
            out["volatility_scale"] = scale
            out["target"] = out["regime"] * scale
        else:
            out["target"] = out["regime"]
        return out

    baseline = moneyline(frame)
    green = baseline["green"]
    out = pd.DataFrame(index=frame.index)
    out["baseline_green"] = green
    out["baseline_flip"] = baseline["flip"]
    out["baseline_line"] = baseline["line"]
    out["atr"] = baseline["atr"]
    if candidate == "moneyline":
        out["regime"] = green.astype(float)
    elif candidate == "confirm2":
        out["regime"] = (green & green.shift(1, fill_value=False)).astype(float)
    elif candidate == "breakout20":
        prior_high = frame["close"].shift(1).rolling(20, min_periods=20).max()
        entry = green & (frame["close"] > prior_high)
        holding = False
        regime = np.zeros(len(frame), dtype=float)
        for i, (is_green, can_enter) in enumerate(zip(green, entry, strict=True)):
            if not is_green:
                holding = False
            elif can_enter:
                holding = True
            regime[i] = float(holding)
        out["previous_20_close_high"] = prior_high
        out["entry_validated"] = entry
        out["regime"] = regime
    elif candidate == "wider_exit3":
        wider = _wider_exit(frame, baseline)
        out["regime"] = wider["regime"]
        out["exit_stop"] = wider["exit_stop"]
    out["target"] = out["regime"]
    return out


def candidate_signals(df: pd.DataFrame, candidate: str) -> pd.DataFrame:
    """Closed-bar desired target and raw signal regime, each in [0, 1]."""
    return explainable_signal_frame(df, candidate).loc[:, ["target", "regime"]]


def target_weights(df: pd.DataFrame, candidate: str) -> pd.Series:
    """Return the candidate's causal desired exposure before execution lag."""
    return candidate_signals(df, candidate)["target"].rename(candidate)
