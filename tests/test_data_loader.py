"""
Unit tests for data_loader module.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data_loader import load_ohlc_csv, align_series, validate_ohlc


class TestLoadOhlcCsv:
    """Tests for load_ohlc_csv function."""

    def test_load_basic_csv(self, tmp_path):
        """Test loading a basic OHLC CSV."""
        csv_content = """time,open,high,low,close,volume
2023-01-01,100,110,95,105,1000
2023-01-02,105,115,100,110,1200
2023-01-03,110,120,105,115,1100
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        df = load_ohlc_csv(str(csv_file))

        assert len(df) == 3
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert df.index.name == 'timestamp'

    def test_load_unix_timestamp(self, tmp_path):
        """Test loading CSV with Unix timestamps."""
        csv_content = """time,open,high,low,close
1672531200,100,110,95,105
1672617600,105,115,100,110
1672704000,110,120,105,115
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        df = load_ohlc_csv(str(csv_file))

        assert len(df) == 3
        assert df.index[0].year == 2023

    def test_load_with_custom_mapping(self, tmp_path):
        """Test loading with custom column mapping."""
        csv_content = """Date,Open,High,Low,Close,Vol
2023-01-01,100,110,95,105,1000
2023-01-02,105,115,100,110,1200
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        mapping = {
            'timestamp': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Vol'
        }

        df = load_ohlc_csv(str(csv_file), mapping=mapping)

        assert len(df) == 2
        assert 'open' in df.columns

    def test_missing_required_columns(self, tmp_path):
        """Test error when required columns missing."""
        csv_content = """time,open,close
2023-01-01,100,105
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="Missing required columns"):
            load_ohlc_csv(str(csv_file))

    def test_removes_duplicates(self, tmp_path):
        """Test that duplicate timestamps are removed."""
        csv_content = """time,open,high,low,close
2023-01-01,100,110,95,105
2023-01-01,101,111,96,106
2023-01-02,105,115,100,110
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        df = load_ohlc_csv(str(csv_file))

        assert len(df) == 2  # Duplicate removed


class TestAlignSeries:
    """Tests for align_series function."""

    def test_inner_join_alignment(self):
        """Test inner join alignment of two series."""
        idx1 = pd.date_range('2023-01-01', periods=5, freq='D', tz='UTC')
        idx2 = pd.date_range('2023-01-03', periods=5, freq='D', tz='UTC')

        df1 = pd.DataFrame({'close': [1, 2, 3, 4, 5]}, index=idx1)
        df2 = pd.DataFrame({'close': [10, 20, 30, 40, 50]}, index=idx2)

        aligned1, aligned2 = align_series(df1, df2, how='inner')

        # Common dates are 2023-01-03 to 2023-01-05 (3 days)
        assert len(aligned1) == 3
        assert len(aligned2) == 3
        assert (aligned1.index == aligned2.index).all()


class TestValidateOhlc:
    """Tests for validate_ohlc function."""

    def test_valid_data(self):
        """Test validation of valid OHLC data."""
        idx = pd.date_range('2023-01-01', periods=3, freq='D', tz='UTC')
        df = pd.DataFrame({
            'open': [100, 105, 110],
            'high': [110, 115, 120],
            'low': [95, 100, 105],
            'close': [105, 110, 115]
        }, index=idx)

        result = validate_ohlc(df)

        assert result['is_valid'] == True
        assert len(result['issues']) == 0

    def test_invalid_high_low(self):
        """Test detection of invalid high < low."""
        idx = pd.date_range('2023-01-01', periods=3, freq='D', tz='UTC')
        df = pd.DataFrame({
            'open': [100, 105, 110],
            'high': [90, 115, 120],  # First row: high < low
            'low': [95, 100, 105],
            'close': [105, 110, 115]
        }, index=idx)

        result = validate_ohlc(df)

        assert result['is_valid'] == False
        assert any('high < low' in issue for issue in result['issues'])
