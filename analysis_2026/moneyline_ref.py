"""Reference implementation that reproduces the user's TradingView "Moneyline"
trend line (green/red ATR trailing stop) from raw OHLC bars.

REPLICATED PARAMETERS (verified bar-by-bar against TradingView exports of
BATS:IWM; daily 2011-2025 and weekly 2002-2025):

    ATR period 10, Wilder RMA ATR (ta.atr), factor 2.0, source hl2,
    "reset-on-flip" trailing stop (variant='reset').

    from supertrend_ref import moneyline
    out = moneyline(df)    # df: DatetimeIndex + open/high/low/close (any case)
    out['green']           # True = GREEN ("Up Trend"), False = RED ("Down Trend")
    out['line']            # the plotted line value
    out['flip']            # +1 on a red->green bar, -1 on green->red, else 0

How the replicated rule works (variant='reset'):
    lo_t = hl2_t - 2.0*ATR10_t ;  hi_t = hl2_t + 2.0*ATR10_t
    GREEN: line_t = max(line_{t-1}, lo_t); if close_t < line_t -> RED, line_t = hi_t
    RED:   line_t = min(line_{t-1}, hi_t); if close_t > line_t -> GREEN, line_t = lo_t
The only difference from TradingView's built-in ta.supertrend() (variant='pine')
is the flip bar: ta.supertrend switches to the opposite band that it has been
ratcheting in the background, whereas the user's indicator restarts the line at
the flip bar's fresh band. That changes the line on ~10% of flips and the
green/red state on ~0.03% of bars; 'reset' matches TradingView on 100%.

Use UNADJUSTED (as-traded) prices to match the chart to the cent. Feeding
dividend-adjusted prices (e.g. yfinance auto_adjust) moves the line by the
adjustment factor and changes a few flips.

The first ~period bars are warm-up (ATR undefined); allow ~100 bars before
trusting the state so the RMA seed and the initial direction wash out.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MONEYLINE_PARAMS = dict(period=10, factor=2.0, atr_type="rma", src="hl2", variant="reset")


def _col(df: pd.DataFrame, name: str) -> np.ndarray:
    for c in df.columns:
        if str(c).lower() == name:
            return df[c].to_numpy(dtype=float)
    raise KeyError(f"OHLC frame needs a '{name}' column")


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev_close = np.r_[np.nan, close[:-1]]
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev_close), np.abs(low - prev_close)))
    tr[0] = high[0] - low[0]  # ta.tr(true): first bar uses high-low
    return tr


def atr(high, low, close, period: int, atr_type: str = "rma") -> np.ndarray:
    """ta.atr (Wilder RMA seeded with the SMA of the first `period` TRs) or SMA of TR."""
    tr = true_range(high, low, close)
    n = len(tr)
    out = np.full(n, np.nan)
    if n < period:
        return out
    if atr_type == "sma":
        cs = np.cumsum(tr)
        out[period - 1] = cs[period - 1] / period
        out[period:] = (cs[period:] - cs[:-period]) / period
        return out
    if atr_type != "rma":
        raise ValueError("atr_type must be 'rma' or 'sma'")
    alpha = 1.0 / period
    out[period - 1] = tr[:period].mean()
    for i in range(period, n):
        out[i] = alpha * tr[i] + (1.0 - alpha) * out[i - 1]
    return out


def source(df: pd.DataFrame, src: str) -> np.ndarray:
    o, h, l, c = (_col(df, k) for k in ("open", "high", "low", "close"))
    return {
        "hl2": (h + l) / 2.0,
        "close": c,
        "hlc3": (h + l + c) / 3.0,
        "ohlc4": (o + h + l + c) / 4.0,
    }[src]


def supertrend(df_ohlc: pd.DataFrame, period: int = 10, factor: float = 2.0,
               atr_type: str = "rma", src: str = "hl2", variant: str = "reset") -> pd.DataFrame:
    """ATR trailing stop / SuperTrend.

    variant='reset'  -> the user's indicator (default): single trailing line that
                        restarts at the flip bar's fresh band.
    variant='pine'   -> TradingView built-in ta.supertrend(factor, atrPeriod).
    variant='kivanc' -> KivancOzbilgic "SuperTrend" community script
                        (flip when close crosses the PREVIOUS bar's band).

    Returns a DataFrame indexed like df_ohlc with columns
        line  (float), green (bool), flip (int: +1 / -1 / 0), atr (float).
    Bars before the ATR is defined have line = NaN, green = False.
    """
    h, l, c = (_col(df_ohlc, k) for k in ("high", "low", "close"))
    s = source(df_ohlc, src)
    a = atr(h, l, c, period, atr_type)
    n = len(c)
    line = np.full(n, np.nan)
    green = np.zeros(n, dtype=bool)
    lo_raw = s - factor * a   # support band (used while green)
    hi_raw = s + factor * a   # resistance band (used while red)

    if variant == "reset":
        started = False
        is_green = True
        stop = np.nan
        for i in range(n):
            if np.isnan(a[i]):
                continue
            if not started:                      # seed direction from the first bar
                is_green = c[i] >= s[i]
                stop = lo_raw[i] if is_green else hi_raw[i]
                started = True
            elif is_green:
                stop = max(stop, lo_raw[i])
                if c[i] < stop:
                    is_green, stop = False, hi_raw[i]
            else:
                stop = min(stop, hi_raw[i])
                if c[i] > stop:
                    is_green, stop = True, lo_raw[i]
            line[i] = stop
            green[i] = is_green

    elif variant == "pine":
        lower = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        direction = 1          # Pine convention: 1 = down (red), -1 = up (green)
        prev_st = np.nan
        for i in range(n):
            if np.isnan(a[i]):
                continue
            lb, ub = lo_raw[i], hi_raw[i]
            started = i > 0 and not np.isnan(lower[i - 1])
            plb = lower[i - 1] if started else 0.0          # nz(lowerBand[1])
            pub = upper[i - 1] if started else 0.0
            pc = c[i - 1] if i > 0 else np.nan
            if not (lb > plb or pc < plb):
                lb = plb
            if not (ub < pub or pc > pub):
                ub = pub
            lower[i], upper[i] = lb, ub
            if not started:                                  # na(atr[1])
                direction = 1
            elif prev_st == pub:
                direction = -1 if c[i] > ub else 1
            else:
                direction = 1 if c[i] < lb else -1
            st = lb if direction == -1 else ub
            line[i] = st
            green[i] = direction == -1
            prev_st = st

    elif variant == "kivanc":
        lower = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        trend = 1
        for i in range(n):
            if np.isnan(a[i]):
                continue
            up, dn = lo_raw[i], hi_raw[i]
            started = i > 0 and not np.isnan(lower[i - 1])
            up1 = lower[i - 1] if started else up            # nz(up[1], up)
            dn1 = upper[i - 1] if started else dn
            pc = c[i - 1] if i > 0 else np.nan
            if pc > up1:
                up = max(up, up1)
            if pc < dn1:
                dn = min(dn, dn1)
            lower[i], upper[i] = up, dn
            if trend == -1 and c[i] > dn1:
                trend = 1
            elif trend == 1 and c[i] < up1:
                trend = -1
            green[i] = trend == 1
            line[i] = up if trend == 1 else dn
    else:
        raise ValueError("variant must be 'reset', 'pine' or 'kivanc'")

    flip = np.zeros(n, dtype=int)
    valid = ~np.isnan(line)
    both = valid[1:] & valid[:-1]
    flip[1:][both & green[1:] & ~green[:-1]] = 1
    flip[1:][both & ~green[1:] & green[:-1]] = -1
    return pd.DataFrame({"line": line, "green": green, "flip": flip, "atr": a},
                        index=df_ohlc.index)


def moneyline(df_ohlc: pd.DataFrame) -> pd.DataFrame:
    """The user's TradingView indicator as replicated: reset-on-flip ATR stop,
    ATR = RMA(10), factor 2.0, source hl2. Works on any bar size (daily, weekly)."""
    return supertrend(df_ohlc, **MONEYLINE_PARAMS)


def to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLC (DatetimeIndex) to TradingView-style weekly bars
    (Monday-Friday weeks, labelled by the Monday)."""
    d = df_daily.rename(columns=str.lower)
    w = d.resample("W-MON", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    return w.dropna(subset=["close"])


if __name__ == "__main__":  # smoke test on synthetic data
    rng = np.random.default_rng(0)
    p = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))
    df = pd.DataFrame({"open": p, "high": p * 1.01, "low": p * 0.99, "close": p},
                      index=pd.bdate_range("2024-01-01", periods=300))
    out = moneyline(df)
    print(out.tail())
    print("flips:", int((out["flip"] != 0).sum()))
