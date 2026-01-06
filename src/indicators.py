"""
Indicator Library (Agent 3)
===========================
Implements Moneyline, BBW, and Donchian indicators with NO lookahead bias.

CRITICAL: All rolling operations use shift(1) to exclude current bar where needed.
"""

import pandas as pd
import numpy as np
from typing import Tuple


# =============================================================================
# Base Moving Averages
# =============================================================================

def ema(series: pd.Series, period: int) -> pd.Series:
    """
    Exponential Moving Average.
    Uses ewm with adjust=False to match TradingView/Pine behavior.
    """
    return series.ewm(span=period, adjust=False).mean()


def wma(series: pd.Series, period: int) -> pd.Series:
    """
    Weighted Moving Average.
    Most recent values get higher weights linearly.
    """
    weights = np.arange(1, period + 1, dtype=float)
    weights = weights / weights.sum()

    def weighted_mean(x):
        if len(x) < period:
            return np.nan
        return np.sum(weights * x)

    return series.rolling(window=period).apply(weighted_mean, raw=True)


def hma(series: pd.Series, period: int) -> pd.Series:
    """
    Hull Moving Average.
    HMA(n) = WMA(2*WMA(x, n/2) - WMA(x, n), sqrt(n))

    Note: Uses integer floor for n/2 and sqrt(n).
    """
    half_period = max(1, int(period / 2))
    sqrt_period = max(1, int(np.sqrt(period)))

    wma_half = wma(series, half_period)
    wma_full = wma(series, period)

    raw_hma = 2 * wma_half - wma_full
    return wma(raw_hma, sqrt_period)


# =============================================================================
# Rolling High/Low (with proper shifting for no lookahead)
# =============================================================================

def highest(series: pd.Series, period: int, include_current: bool = True) -> pd.Series:
    """
    Rolling highest value.

    Parameters
    ----------
    series : pd.Series
        Typically high prices
    period : int
        Lookback period
    include_current : bool
        If True, includes current bar (standard for tenkan/kijun).
        If False, uses only prior bars (for breakout detection).
    """
    if include_current:
        return series.rolling(window=period, min_periods=1).max()
    else:
        # Shift by 1 to exclude current bar
        return series.shift(1).rolling(window=period, min_periods=1).max()


def lowest(series: pd.Series, period: int, include_current: bool = True) -> pd.Series:
    """
    Rolling lowest value.

    Parameters
    ----------
    series : pd.Series
        Typically low prices
    period : int
        Lookback period
    include_current : bool
        If True, includes current bar (standard for tenkan/kijun).
        If False, uses only prior bars.
    """
    if include_current:
        return series.rolling(window=period, min_periods=1).min()
    else:
        # Shift by 1 to exclude current bar
        return series.shift(1).rolling(window=period, min_periods=1).min()


# =============================================================================
# Crossover/Crossunder Detection
# =============================================================================

def crossover(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """
    Detect when series_a crosses above series_b.
    Returns True on the bar where the crossover occurs.

    Logic: a[t] > b[t] AND a[t-1] <= b[t-1]
    """
    current_above = series_a > series_b
    prev_below_or_equal = series_a.shift(1) <= series_b.shift(1)
    return current_above & prev_below_or_equal


def crossunder(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """
    Detect when series_a crosses below series_b.
    Returns True on the bar where the crossunder occurs.

    Logic: a[t] < b[t] AND a[t-1] >= b[t-1]
    """
    current_below = series_a < series_b
    prev_above_or_equal = series_a.shift(1) >= series_b.shift(1)
    return current_below & prev_above_or_equal


# =============================================================================
# Moneyline Indicator Suite
# =============================================================================

def compute_moneyline(
    df: pd.DataFrame,
    conv_period: int = 9,
    base_period: int = 26,
    fast_hma_period: int = 5,
    slow_ema_period: int = 13,
    exit_percent: float = 2.0
) -> pd.DataFrame:
    """
    Compute all Moneyline indicator components.

    This replicates the Pine script logic:
        tenkan = (highest(high, conv) + lowest(low, conv)) / 2
        kijun = (highest(high, base) + lowest(low, base)) / 2
        fastHMA = HMA(tenkan, fastHMAPeriod)
        slowMA = EMA(kijun, slowPeriod)
        adjustedSlowMA = slowMA * (1 - exitPercent/100)
        long = crossover(fastHMA, slowMA)
        exit = crossunder(fastHMA, adjustedSlowMA)

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame with 'high', 'low', 'close' columns
    conv_period : int
        Tenkan-sen period (default 9)
    base_period : int
        Kijun-sen period (default 26)
    fast_hma_period : int
        HMA period on tenkan (default 5)
    slow_ema_period : int
        EMA period on kijun (default 13)
    exit_percent : float
        Adjustment percentage for exit threshold (default 2.0)

    Returns
    -------
    pd.DataFrame
        Original columns plus:
        - tenkan, kijun
        - fast_hma, slow_ma, adjusted_slow_ma
        - long_cross, exit_cross, trend_green
    """
    result = df.copy()

    # Tenkan-sen (conversion line)
    result['tenkan'] = (
        highest(df['high'], conv_period) +
        lowest(df['low'], conv_period)
    ) / 2

    # Kijun-sen (base line)
    result['kijun'] = (
        highest(df['high'], base_period) +
        lowest(df['low'], base_period)
    ) / 2

    # Fast HMA on tenkan
    result['fast_hma'] = hma(result['tenkan'], fast_hma_period)

    # Slow EMA on kijun
    result['slow_ma'] = ema(result['kijun'], slow_ema_period)

    # Adjusted slow MA for exit (lowered threshold)
    result['adjusted_slow_ma'] = result['slow_ma'] * (1 - exit_percent / 100)

    # Signal detection
    result['long_cross'] = crossover(result['fast_hma'], result['slow_ma'])
    result['exit_cross'] = crossunder(result['fast_hma'], result['adjusted_slow_ma'])

    # Trend direction (fast above slow = bullish)
    result['trend_green'] = result['fast_hma'] > result['slow_ma']

    return result


# =============================================================================
# Bollinger Band Width (Contraction Detection)
# =============================================================================

def compute_bbw(
    series: pd.Series,
    period: int = 20,
    std_mult: float = 2.0
) -> pd.Series:
    """
    Compute Bollinger Band Width.

    BBW = (Upper Band - Lower Band) / Middle Band
        = (basis + std_mult*std - (basis - std_mult*std)) / basis
        = 2 * std_mult * std / basis

    Parameters
    ----------
    series : pd.Series
        Typically close prices
    period : int
        Bollinger Band period
    std_mult : float
        Standard deviation multiplier

    Returns
    -------
    pd.Series
        BBW values
    """
    basis = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    bbw = (2 * std_mult * std) / basis
    return bbw


def compute_contraction(
    df: pd.DataFrame,
    bb_period: int = 20,
    bb_std: float = 2.0,
    quantile_window: int = 252,
    quantile_threshold: float = 0.20
) -> pd.DataFrame:
    """
    Compute contraction indicator.

    contracted[t] = BBW[t] < rolling_quantile(BBW[t-quantile_window:t-1], q)

    CRITICAL: Uses shift(1) to ensure we only use PRIOR BBW values for the
    quantile threshold, avoiding lookahead bias.

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame with 'close' column
    bb_period : int
        Bollinger Band period
    bb_std : float
        Bollinger Band std multiplier
    quantile_window : int
        Window for rolling quantile calculation
    quantile_threshold : float
        Quantile threshold (0.20 = 20th percentile)

    Returns
    -------
    pd.DataFrame
        Original columns plus:
        - bbw: Bollinger Band Width
        - bbw_threshold: Rolling quantile threshold
        - contracted: Boolean, True if BBW < threshold
    """
    result = df.copy()

    # Compute BBW
    result['bbw'] = compute_bbw(df['close'], bb_period, bb_std)

    # Compute rolling quantile on SHIFTED BBW (prior values only)
    shifted_bbw = result['bbw'].shift(1)
    result['bbw_threshold'] = shifted_bbw.rolling(
        window=quantile_window,
        min_periods=min(quantile_window, 50)  # Allow partial window early on
    ).quantile(quantile_threshold)

    # Contracted when current BBW is below threshold
    result['contracted'] = result['bbw'] < result['bbw_threshold']

    return result


def compute_contracted_recent(
    contracted: pd.Series,
    lookback: int = 20
) -> pd.Series:
    """
    Check if there was any contraction in the last M bars.

    contracted_recent[t] = any(contracted[t-M+1:t+1])

    This includes the current bar's contraction status.

    Parameters
    ----------
    contracted : pd.Series
        Boolean series of contraction signals
    lookback : int
        Number of bars to look back (M)

    Returns
    -------
    pd.Series
        Boolean, True if any bar in lookback window was contracted
    """
    # Rolling max on boolean (1/0) gives 1 if any True in window
    return contracted.astype(int).rolling(window=lookback, min_periods=1).max().astype(bool)


# =============================================================================
# Donchian Channel (Breakout Detection)
# =============================================================================

def compute_donchian(
    df: pd.DataFrame,
    period: int = 20
) -> pd.DataFrame:
    """
    Compute Donchian channel for breakout detection.

    donch_high[t] = max(high[t-N:t-1])  # Prior bars only, NO current bar
    breakout[t] = close[t] > donch_high[t]

    CRITICAL: Uses include_current=False to exclude current bar from the
    highest calculation, ensuring no lookahead.

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame with 'high', 'close' columns
    period : int
        Donchian channel period (N)

    Returns
    -------
    pd.DataFrame
        Original columns plus:
        - donch_high: Highest high of prior N bars
        - donch_low: Lowest low of prior N bars
        - breakout_long: Close above prior high channel
        - breakout_short: Close below prior low channel
    """
    result = df.copy()

    # Prior N bars only (exclude current)
    result['donch_high'] = highest(df['high'], period, include_current=False)
    result['donch_low'] = lowest(df['low'], period, include_current=False)

    # Breakout signals
    result['breakout_long'] = df['close'] > result['donch_high']
    result['breakout_short'] = df['close'] < result['donch_low']

    return result


# =============================================================================
# Combined Indicator Computation
# =============================================================================

def compute_all_indicators(
    df: pd.DataFrame,
    moneyline_params: dict = None,
    contraction_params: dict = None,
    breakout_params: dict = None
) -> pd.DataFrame:
    """
    Compute all indicators needed for the 3 strategy systems.

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame
    moneyline_params : dict
        Parameters for compute_moneyline()
    contraction_params : dict
        Parameters for compute_contraction()
    breakout_params : dict
        Parameters for compute_donchian()

    Returns
    -------
    pd.DataFrame
        DataFrame with all indicator columns
    """
    moneyline_params = moneyline_params or {}
    contraction_params = contraction_params or {}
    breakout_params = breakout_params or {}

    # Start with moneyline indicators
    result = compute_moneyline(df, **moneyline_params)

    # Add contraction indicators
    contraction_df = compute_contraction(df, **contraction_params)
    result['bbw'] = contraction_df['bbw']
    result['bbw_threshold'] = contraction_df['bbw_threshold']
    result['contracted'] = contraction_df['contracted']

    # Add contracted_recent
    lookback = contraction_params.get('lookback_bars', 20)
    result['contracted_recent'] = compute_contracted_recent(
        result['contracted'], lookback
    )

    # Add breakout indicators
    breakout_df = compute_donchian(df, **breakout_params)
    result['donch_high'] = breakout_df['donch_high']
    result['donch_low'] = breakout_df['donch_low']
    result['breakout_long'] = breakout_df['breakout_long']

    return result
