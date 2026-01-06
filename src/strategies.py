"""
Strategy Implementations (Agent 5)
==================================
Implements the 3 trading systems producing entry/exit signals.

System 1 (Baseline): Pure Moneyline crossover
System 2 (Filtered): Baseline + contraction filter
System 3 (Hybrid): Trend filter + breakout entry + contraction requirement
"""

import pandas as pd
from typing import Tuple, Optional
from .indicators import compute_all_indicators


def generate_baseline_signals(
    df: pd.DataFrame,
    moneyline_params: dict = None
) -> Tuple[pd.Series, pd.Series]:
    """
    System 1: Baseline Moneyline Imitator

    Entry: crossover(fastHMA, slowMA)
    Exit: crossunder(fastHMA, adjustedSlowMA)

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame with indicators computed
    moneyline_params : dict
        Parameters for moneyline computation (if indicators not yet computed)

    Returns
    -------
    tuple
        (entry_signal, exit_signal) as boolean Series
    """
    # Check if indicators already computed
    if 'long_cross' not in df.columns:
        moneyline_params = moneyline_params or {}
        df = compute_all_indicators(df, moneyline_params=moneyline_params)

    entry_signal = df['long_cross'].fillna(False)
    exit_signal = df['exit_cross'].fillna(False)

    return entry_signal, exit_signal


def generate_filtered_signals(
    df: pd.DataFrame,
    contraction_lookback: int = 20,
    moneyline_params: dict = None,
    contraction_params: dict = None
) -> Tuple[pd.Series, pd.Series]:
    """
    System 2: Filtered Crossover

    Entry: baseline_entry AND contracted_recent
    Exit: same as baseline

    The contraction filter requires that there was at least one
    contraction bar within the last M bars.

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame
    contraction_lookback : int
        M: number of bars to look back for contraction
    moneyline_params : dict
        Parameters for moneyline computation
    contraction_params : dict
        Parameters for contraction computation

    Returns
    -------
    tuple
        (entry_signal, exit_signal) as boolean Series
    """
    # Compute all indicators if needed
    if 'long_cross' not in df.columns or 'contracted_recent' not in df.columns:
        moneyline_params = moneyline_params or {}
        contraction_params = contraction_params or {}
        contraction_params['lookback_bars'] = contraction_lookback
        df = compute_all_indicators(
            df,
            moneyline_params=moneyline_params,
            contraction_params=contraction_params
        )

    # Baseline crossover
    baseline_entry = df['long_cross'].fillna(False)

    # Contraction filter: any contraction in last M bars
    contracted_recent = df['contracted_recent'].fillna(False)

    # Combined entry
    entry_signal = baseline_entry & contracted_recent

    # Exit same as baseline
    exit_signal = df['exit_cross'].fillna(False)

    return entry_signal, exit_signal


def generate_hybrid_signals(
    df: pd.DataFrame,
    contraction_lookback: int = 20,
    donchian_period: int = 20,
    moneyline_params: dict = None,
    contraction_params: dict = None,
    breakout_params: dict = None
) -> Tuple[pd.Series, pd.Series]:
    """
    System 3: Hybrid (Trend Filter + Breakout Entry)

    Entry: trendGreenNow AND breakout_long AND contracted_recent
    Exit: same as baseline

    This system requires:
    1. Current trend is bullish (fastHMA > slowMA)
    2. Price breaks above prior N-bar high
    3. There was recent contraction (volatility squeeze)

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame
    contraction_lookback : int
        M: bars to look back for contraction
    donchian_period : int
        N: bars for Donchian channel
    moneyline_params : dict
        Parameters for moneyline computation
    contraction_params : dict
        Parameters for contraction computation
    breakout_params : dict
        Parameters for breakout computation

    Returns
    -------
    tuple
        (entry_signal, exit_signal) as boolean Series
    """
    # Compute all indicators if needed
    if 'trend_green' not in df.columns or 'breakout_long' not in df.columns:
        moneyline_params = moneyline_params or {}
        contraction_params = contraction_params or {}
        breakout_params = breakout_params or {}

        contraction_params['lookback_bars'] = contraction_lookback
        breakout_params['period'] = donchian_period

        df = compute_all_indicators(
            df,
            moneyline_params=moneyline_params,
            contraction_params=contraction_params,
            breakout_params=breakout_params
        )

    # Trend filter: fastHMA > slowMA
    trend_green = df['trend_green'].fillna(False)

    # Breakout: close > donchian high of prior N bars
    breakout_long = df['breakout_long'].fillna(False)

    # Contraction filter
    contracted_recent = df['contracted_recent'].fillna(False)

    # Combined entry: all three conditions must be true
    entry_signal = trend_green & breakout_long & contracted_recent

    # Exit same as baseline
    exit_signal = df['exit_cross'].fillna(False)

    return entry_signal, exit_signal


class StrategyRunner:
    """
    Unified strategy runner supporting single and dual-series modes.
    """

    def __init__(
        self,
        moneyline_params: dict = None,
        contraction_params: dict = None,
        breakout_params: dict = None,
        dual_series_config: dict = None
    ):
        """
        Initialize strategy runner.

        Parameters
        ----------
        moneyline_params : dict
            conv_period, base_period, fast_hma_period, slow_ema_period, exit_percent
        contraction_params : dict
            bb_period, bb_std, quantile_window, quantile_threshold, lookback_bars
        breakout_params : dict
            donchian_period
        dual_series_config : dict
            enabled, require_btc_entry, require_btc_exit, require_btc_contraction, require_btc_breakout
        """
        self.moneyline_params = moneyline_params or {}
        self.contraction_params = contraction_params or {}
        self.breakout_params = breakout_params or {}
        self.dual_series_config = dual_series_config or {'enabled': False}

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all indicators for a DataFrame."""
        return compute_all_indicators(
            df,
            moneyline_params=self.moneyline_params,
            contraction_params=self.contraction_params,
            breakout_params=self.breakout_params
        )

    def run_baseline(
        self,
        df_usd: pd.DataFrame,
        df_btc: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Run System 1: Baseline strategy.

        Returns combined entry/exit signals considering dual-series if enabled.
        """
        # Compute indicators
        df_usd_ind = self.compute_indicators(df_usd)
        entry_usd, exit_usd = generate_baseline_signals(df_usd_ind)

        if not self.dual_series_config.get('enabled', False) or df_btc is None:
            return entry_usd, exit_usd

        # Dual-series mode
        df_btc_ind = self.compute_indicators(df_btc)
        entry_btc, exit_btc = generate_baseline_signals(df_btc_ind)

        return self._combine_dual_signals(
            entry_usd, exit_usd, entry_btc, exit_btc
        )

    def run_filtered(
        self,
        df_usd: pd.DataFrame,
        df_btc: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Run System 2: Filtered Crossover strategy.

        Returns combined entry/exit signals considering dual-series if enabled.
        """
        # Compute indicators
        df_usd_ind = self.compute_indicators(df_usd)
        lookback = self.contraction_params.get('lookback_bars', 20)
        entry_usd, exit_usd = generate_filtered_signals(df_usd_ind, lookback)

        if not self.dual_series_config.get('enabled', False) or df_btc is None:
            return entry_usd, exit_usd

        # Dual-series mode
        df_btc_ind = self.compute_indicators(df_btc)
        entry_btc, exit_btc = generate_filtered_signals(df_btc_ind, lookback)

        # Additional contraction requirement on BTC if configured
        if self.dual_series_config.get('require_btc_contraction', False):
            btc_contracted = df_btc_ind['contracted_recent'].fillna(False)
            entry_usd = entry_usd & btc_contracted

        return self._combine_dual_signals(
            entry_usd, exit_usd, entry_btc, exit_btc
        )

    def run_hybrid(
        self,
        df_usd: pd.DataFrame,
        df_btc: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Run System 3: Hybrid strategy.

        Returns combined entry/exit signals considering dual-series if enabled.
        """
        # Compute indicators
        df_usd_ind = self.compute_indicators(df_usd)
        lookback = self.contraction_params.get('lookback_bars', 20)
        donchian = self.breakout_params.get('donchian_period', 20)
        entry_usd, exit_usd = generate_hybrid_signals(
            df_usd_ind, lookback, donchian
        )

        if not self.dual_series_config.get('enabled', False) or df_btc is None:
            return entry_usd, exit_usd

        # Dual-series mode
        df_btc_ind = self.compute_indicators(df_btc)
        entry_btc, exit_btc = generate_hybrid_signals(
            df_btc_ind, lookback, donchian
        )

        # Additional requirements for BTC series
        if self.dual_series_config.get('require_btc_contraction', False):
            btc_contracted = df_btc_ind['contracted_recent'].fillna(False)
            entry_usd = entry_usd & btc_contracted

        if self.dual_series_config.get('require_btc_breakout', False):
            btc_breakout = df_btc_ind['breakout_long'].fillna(False)
            entry_usd = entry_usd & btc_breakout

        # Require BTC trend green
        btc_trend = df_btc_ind['trend_green'].fillna(False)
        entry_usd = entry_usd & btc_trend

        return self._combine_dual_signals(
            entry_usd, exit_usd, entry_btc, exit_btc
        )

    def _combine_dual_signals(
        self,
        entry_usd: pd.Series,
        exit_usd: pd.Series,
        entry_btc: pd.Series,
        exit_btc: pd.Series
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Combine USD and BTC signals.

        Entry: USD entry AND BTC confirmation (within window)
        Exit: USD exit OR BTC exit
        """
        # BTC entry confirmation within a 5-bar window
        if self.dual_series_config.get('require_btc_entry', True):
            btc_entry_window = entry_btc.rolling(window=5, min_periods=1).max().astype(bool)
            combined_entry = entry_usd & btc_entry_window
        else:
            combined_entry = entry_usd

        # Exit on either signal
        if self.dual_series_config.get('require_btc_exit', True):
            combined_exit = exit_usd | exit_btc
        else:
            combined_exit = exit_usd

        return combined_entry, combined_exit

    def run_all(
        self,
        df_usd: pd.DataFrame,
        df_btc: Optional[pd.DataFrame] = None
    ) -> dict:
        """
        Run all three strategies and return their signals.

        Returns
        -------
        dict
            {
                'baseline': (entry, exit),
                'filtered': (entry, exit),
                'hybrid': (entry, exit)
            }
        """
        return {
            'baseline': self.run_baseline(df_usd, df_btc),
            'filtered': self.run_filtered(df_usd, df_btc),
            'hybrid': self.run_hybrid(df_usd, df_btc)
        }
