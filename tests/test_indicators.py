"""
Unit tests for indicators module.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.indicators import (
    ema, wma, hma,
    highest, lowest,
    crossover, crossunder,
    compute_moneyline,
    compute_bbw, compute_contraction,
    compute_donchian,
    compute_all_indicators
)


class TestMovingAverages:
    """Tests for moving average functions."""

    def test_ema_basic(self):
        """Test basic EMA calculation."""
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = ema(series, 3)

        assert len(result) == 10
        assert not result.isna().all()
        # EMA should be smoothed, last value should be close to 10
        assert result.iloc[-1] > 8

    def test_wma_basic(self):
        """Test basic WMA calculation."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = wma(series, 3)

        # WMA(3) at position 2: (1*1 + 2*2 + 3*3) / 6 = 14/6 = 2.333
        assert len(result) == 5
        assert not np.isnan(result.iloc[2])

    def test_hma_basic(self):
        """Test basic HMA calculation."""
        series = pd.Series(range(1, 21))  # 1 to 20
        result = hma(series, 9)

        assert len(result) == 20
        # HMA should respond faster than SMA


class TestHighestLowest:
    """Tests for highest/lowest functions."""

    def test_highest_include_current(self):
        """Test highest with current bar included."""
        series = pd.Series([1, 5, 3, 2, 8, 4])
        result = highest(series, 3, include_current=True)

        # At index 2: max of [1,5,3] = 5
        # At index 3: max of [5,3,2] = 5
        # At index 4: max of [3,2,8] = 8
        # At index 5: max of [2,8,4] = 8
        assert result.iloc[2] == 5
        assert result.iloc[4] == 8
        assert result.iloc[5] == 8

    def test_highest_exclude_current(self):
        """Test highest with current bar excluded (for breakout)."""
        series = pd.Series([1, 5, 3, 2, 8, 4])
        result = highest(series, 3, include_current=False)

        # At index 3: max of [1,5,3] (shifted) = 5
        # At index 4: max of [5,3,2] (shifted) = 5
        # At index 5: max of [3,2,8] (shifted) = 8
        assert result.iloc[3] == 5
        assert result.iloc[4] == 5
        assert result.iloc[5] == 8

    def test_lowest_include_current(self):
        """Test lowest with current bar included."""
        series = pd.Series([5, 1, 3, 2, 8, 4])
        result = lowest(series, 3, include_current=True)

        # At index 2: min of [5,1,3] = 1
        assert result.iloc[2] == 1


class TestCrossover:
    """Tests for crossover/crossunder detection."""

    def test_crossover_detection(self):
        """Test crossover detection."""
        a = pd.Series([1, 2, 4, 5, 3])
        b = pd.Series([2, 3, 3, 3, 4])

        result = crossover(a, b)

        # Crossover at index 2: a[2]=4 > b[2]=3 AND a[1]=2 <= b[1]=3
        assert result.iloc[2] == True
        assert result.iloc[0] == False
        assert result.iloc[4] == False

    def test_crossunder_detection(self):
        """Test crossunder detection."""
        a = pd.Series([5, 4, 2, 1, 3])
        b = pd.Series([2, 3, 3, 3, 2])

        result = crossunder(a, b)

        # Crossunder at index 2: a[2]=2 < b[2]=3 AND a[1]=4 >= b[1]=3
        assert result.iloc[2] == True


class TestMoneyline:
    """Tests for Moneyline indicator computation."""

    def create_sample_df(self, n=100):
        """Create sample OHLC DataFrame for testing."""
        np.random.seed(42)
        idx = pd.date_range('2023-01-01', periods=n, freq='D', tz='UTC')

        # Generate trending price data
        trend = np.linspace(100, 150, n) + np.random.randn(n) * 5
        high = trend + np.random.rand(n) * 10
        low = trend - np.random.rand(n) * 10
        open_ = low + np.random.rand(n) * (high - low)
        close = low + np.random.rand(n) * (high - low)

        return pd.DataFrame({
            'open': open_,
            'high': high,
            'low': low,
            'close': close
        }, index=idx)

    def test_compute_moneyline(self):
        """Test Moneyline computation."""
        df = self.create_sample_df()
        result = compute_moneyline(df)

        # Check all expected columns exist
        expected_cols = [
            'tenkan', 'kijun', 'fast_hma', 'slow_ma',
            'adjusted_slow_ma', 'long_cross', 'exit_cross', 'trend_green'
        ]
        for col in expected_cols:
            assert col in result.columns

        # Check adjusted_slow_ma is lower than slow_ma
        valid_idx = result['slow_ma'].notna()
        assert (result.loc[valid_idx, 'adjusted_slow_ma'] <=
                result.loc[valid_idx, 'slow_ma']).all()


class TestContraction:
    """Tests for contraction indicator."""

    def test_bbw_calculation(self):
        """Test BBW calculation."""
        np.random.seed(42)
        series = pd.Series(100 + np.random.randn(100) * 5)
        result = compute_bbw(series, period=20, std_mult=2.0)

        assert len(result) == 100
        # BBW should be positive
        assert (result.dropna() >= 0).all()

    def test_contraction_no_lookahead(self):
        """Test that contraction uses prior values only."""
        np.random.seed(42)
        idx = pd.date_range('2023-01-01', periods=300, freq='D', tz='UTC')
        df = pd.DataFrame({
            'close': 100 + np.random.randn(300) * 5
        }, index=idx)

        result = compute_contraction(df, quantile_window=50)

        # bbw_threshold at time t should use bbw[t-50:t-1]
        # Verify by checking that bbw_threshold[t] doesn't include bbw[t]
        for i in range(60, 100):
            prior_bbw = result['bbw'].iloc[i-50:i]
            expected_threshold = prior_bbw.quantile(0.20)
            actual_threshold = result['bbw_threshold'].iloc[i]

            if pd.notna(expected_threshold) and pd.notna(actual_threshold):
                assert np.isclose(expected_threshold, actual_threshold, rtol=1e-4)


class TestDonchian:
    """Tests for Donchian breakout indicator."""

    def test_donchian_no_lookahead(self):
        """Test that Donchian uses prior bars only."""
        idx = pd.date_range('2023-01-01', periods=50, freq='D', tz='UTC')
        df = pd.DataFrame({
            'high': range(1, 51),  # Monotonically increasing
            'low': range(0, 50),
            'close': range(1, 51)
        }, index=idx)

        result = compute_donchian(df, period=5)

        # donch_high at index 10 should be max of high[5:10] = 10
        # (indices 5,6,7,8,9 -> values 6,7,8,9,10)
        assert result['donch_high'].iloc[10] == 10

        # breakout at index 11: close=12 > donch_high=11 (max of 7-11)
        assert result['breakout_long'].iloc[11] == True

    def test_donchian_excludes_current_bar(self):
        """Verify current bar is excluded from Donchian calculation."""
        idx = pd.date_range('2023-01-01', periods=30, freq='D', tz='UTC')

        # Create data where current bar has highest high
        highs = [10] * 30
        highs[25] = 100  # Spike at index 25

        df = pd.DataFrame({
            'high': highs,
            'low': [5] * 30,
            'close': [8] * 30
        }, index=idx)

        result = compute_donchian(df, period=5)

        # At index 25, donch_high should NOT include the 100 spike
        # It should be max of indices 20-24, all 10
        assert result['donch_high'].iloc[25] == 10

        # At index 26, donch_high SHOULD include the 100 spike
        assert result['donch_high'].iloc[26] == 100
