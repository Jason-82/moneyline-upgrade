"""
Unit tests for backtester module.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.backtester import run_backtest, BacktestResult, Trade


class TestRunBacktest:
    """Tests for run_backtest function."""

    def create_sample_df(self, n=100):
        """Create sample OHLC DataFrame."""
        np.random.seed(42)
        idx = pd.date_range('2023-01-01', periods=n, freq='D', tz='UTC')

        # Trending up price
        base = np.linspace(100, 150, n)
        df = pd.DataFrame({
            'open': base + np.random.randn(n),
            'high': base + np.random.rand(n) * 5,
            'low': base - np.random.rand(n) * 5,
            'close': base + np.random.randn(n) * 2
        }, index=idx)

        return df

    def test_basic_backtest(self):
        """Test basic backtest execution."""
        df = self.create_sample_df()

        # Simple entry/exit signals
        entry = pd.Series(False, index=df.index)
        exit = pd.Series(False, index=df.index)

        entry.iloc[10] = True  # Enter on day 10
        exit.iloc[50] = True   # Exit on day 50

        result = run_backtest(df, entry, exit, initial_capital=10000)

        assert isinstance(result, BacktestResult)
        assert len(result.trades) == 1
        assert result.trades[0].entry_bar_idx == 11  # Fill on next bar
        assert result.trades[0].exit_bar_idx == 51

    def test_fill_at_next_open(self):
        """Verify fills occur at next bar's open."""
        idx = pd.date_range('2023-01-01', periods=20, freq='D', tz='UTC')
        df = pd.DataFrame({
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                     110, 111, 112, 113, 114, 115, 116, 117, 118, 119],
            'high': [105] * 20,
            'low': [95] * 20,
            'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                      110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
        }, index=idx)

        entry = pd.Series(False, index=df.index)
        exit = pd.Series(False, index=df.index)
        entry.iloc[5] = True  # Signal at close of day 5
        exit.iloc[10] = True  # Signal at close of day 10

        result = run_backtest(df, entry, exit, fee_percent=0, slippage_bps=0)

        trade = result.trades[0]
        # Entry should be at open of day 6 = 106
        assert trade.entry_price == 106
        # Exit should be at open of day 11 = 111
        assert trade.exit_price == 111

    def test_fees_applied(self):
        """Test that fees are correctly applied."""
        df = self.create_sample_df(50)

        entry = pd.Series(False, index=df.index)
        exit = pd.Series(False, index=df.index)
        entry.iloc[5] = True
        exit.iloc[20] = True

        result_no_fee = run_backtest(df, entry, exit, fee_percent=0, slippage_bps=0)
        result_with_fee = run_backtest(df, entry, exit, fee_percent=0.5, slippage_bps=0)

        # Result with fees should have lower final equity
        assert result_with_fee.final_equity < result_no_fee.final_equity

    def test_one_position_at_time(self):
        """Test that only one position is held at a time."""
        df = self.create_sample_df(50)

        # Multiple entry signals while in position
        entry = pd.Series(False, index=df.index)
        exit = pd.Series(False, index=df.index)
        entry.iloc[5] = True
        entry.iloc[10] = True  # Should be ignored
        entry.iloc[15] = True  # Should be ignored
        exit.iloc[30] = True

        result = run_backtest(df, entry, exit)

        # Only one trade should execute
        assert len(result.trades) == 1

    def test_multiple_trades(self):
        """Test multiple trades in sequence."""
        df = self.create_sample_df(100)

        entry = pd.Series(False, index=df.index)
        exit = pd.Series(False, index=df.index)

        # Trade 1: enter 10, exit 20
        entry.iloc[10] = True
        exit.iloc[20] = True

        # Trade 2: enter 30, exit 40
        entry.iloc[30] = True
        exit.iloc[40] = True

        # Trade 3: enter 50, exit 60
        entry.iloc[50] = True
        exit.iloc[60] = True

        result = run_backtest(df, entry, exit)

        assert len(result.trades) == 3

    def test_position_series(self):
        """Test position series tracking."""
        df = self.create_sample_df(30)

        entry = pd.Series(False, index=df.index)
        exit = pd.Series(False, index=df.index)
        entry.iloc[5] = True
        exit.iloc[15] = True

        result = run_backtest(df, entry, exit)

        # Not in position before entry fill (day 0-5)
        assert result.position_series.iloc[:6].sum() == 0

        # In position from day 6 to day 15
        assert result.position_series.iloc[6:16].sum() == 10

        # Not in position after exit (day 16+)
        assert result.position_series.iloc[16:].sum() == 0

    def test_mfe_mae_calculation(self):
        """Test MFE/MAE calculation."""
        idx = pd.date_range('2023-01-01', periods=20, freq='D', tz='UTC')
        df = pd.DataFrame({
            'open': [100] * 20,
            'high': [100, 100, 100, 100, 100, 105, 110, 115, 120, 115,
                     110, 105, 100, 95, 90, 95, 100, 105, 110, 115],
            'low':  [100, 100, 100, 100, 100, 95, 95, 95, 95, 95,
                     90, 85, 80, 75, 80, 85, 90, 95, 100, 105],
            'close': [100] * 20
        }, index=idx)

        entry = pd.Series(False, index=df.index)
        exit = pd.Series(False, index=df.index)
        entry.iloc[4] = True  # Entry at open of day 5 = 100
        exit.iloc[15] = True  # Exit at open of day 16 = 100

        result = run_backtest(df, entry, exit, fee_percent=0, slippage_bps=0)

        trade = result.trades[0]
        # MFE should be from high of 120 at index 8
        # MAE should be from low of 75 at index 13
        assert trade.mfe > 0  # We went up to 120
        assert trade.mae < 0  # We went down to 75


class TestTradeDataclass:
    """Tests for Trade dataclass."""

    def test_trade_to_dict(self):
        """Test Trade.to_dict() method."""
        from datetime import datetime

        trade = Trade(
            entry_time=datetime(2023, 1, 1),
            entry_price=100.0,
            exit_time=datetime(2023, 2, 1),
            exit_price=110.0,
            entry_bar_idx=0,
            exit_bar_idx=30,
            gross_pnl_pct=10.0,
            net_pnl_pct=9.5,
            pnl_cash=950.0,
            duration_days=31,
            mfe=15.0,
            mae=-5.0,
            fees_paid=50.0
        )

        d = trade.to_dict()

        assert d['entry_price'] == 100.0
        assert d['exit_price'] == 110.0
        assert d['net_pnl_pct'] == 9.5
        assert d['duration_days'] == 31
