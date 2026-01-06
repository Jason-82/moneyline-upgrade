"""
Data Loader Module (Agent 2)
============================
Handles CSV ingestion, normalization, and dual-series alignment.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
import warnings


# Canonical column names
CANONICAL_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']


def load_ohlc_csv(
    path: str,
    mapping: Optional[Dict[str, str]] = None,
    parse_dates: bool = True
) -> pd.DataFrame:
    """
    Load OHLC data from CSV with flexible column name mapping.

    Parameters
    ----------
    path : str
        Path to CSV file
    mapping : dict, optional
        Maps canonical names to CSV column names
        e.g., {'timestamp': 'Date', 'open': 'Open', ...}
    parse_dates : bool
        Whether to parse timestamp column as datetime

    Returns
    -------
    pd.DataFrame
        DataFrame with canonical column names, indexed by UTC datetime, sorted
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    # Read CSV
    df = pd.read_csv(path)

    # Default mapping tries common column names
    if mapping is None:
        mapping = _auto_detect_mapping(df.columns)

    # Rename columns to canonical names
    reverse_mapping = {v: k for k, v in mapping.items() if v in df.columns}
    df = df.rename(columns=reverse_mapping)

    # Ensure required columns exist
    required = ['timestamp', 'open', 'high', 'low', 'close']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. "
                        f"Available columns: {list(df.columns)}")

    # Parse timestamp
    if parse_dates:
        df['timestamp'] = _parse_timestamp(df['timestamp'])

    # Set index and sort
    df = df.set_index('timestamp')
    df = df.sort_index()

    # Remove duplicates (keep last)
    if df.index.duplicated().any():
        n_dupes = df.index.duplicated().sum()
        warnings.warn(f"Removed {n_dupes} duplicate timestamps")
        df = df[~df.index.duplicated(keep='last')]

    # Ensure numeric types
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Select only canonical columns that exist
    available_cols = [c for c in CANONICAL_COLUMNS[1:] if c in df.columns]
    df = df[available_cols]

    # Ensure index is UTC
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')

    return df


def _auto_detect_mapping(columns: pd.Index) -> Dict[str, str]:
    """Auto-detect column mapping from common formats."""
    columns_lower = {c.lower(): c for c in columns}

    mapping = {}

    # Timestamp detection
    for ts_name in ['time', 'timestamp', 'date', 'datetime', 'unix']:
        if ts_name in columns_lower:
            mapping['timestamp'] = columns_lower[ts_name]
            break

    # OHLC detection
    for ohlc in ['open', 'high', 'low', 'close']:
        if ohlc in columns_lower:
            mapping[ohlc] = columns_lower[ohlc]

    # Volume detection
    for vol_name in ['volume', 'vol']:
        if vol_name in columns_lower:
            mapping['volume'] = columns_lower[vol_name]
            break

    return mapping


def _parse_timestamp(series: pd.Series) -> pd.Series:
    """Parse timestamp from various formats."""
    sample = series.iloc[0]

    # Check if it's already datetime
    if isinstance(sample, (pd.Timestamp, np.datetime64)):
        return pd.to_datetime(series)

    # Check if it's numeric (unix timestamp)
    try:
        if isinstance(sample, (int, float)) or (isinstance(sample, str) and sample.isdigit()):
            numeric_val = float(sample)
            # Determine if seconds or milliseconds
            if numeric_val > 1e12:  # Milliseconds
                return pd.to_datetime(series.astype(float), unit='ms')
            else:  # Seconds
                return pd.to_datetime(series.astype(float), unit='s')
    except (ValueError, TypeError):
        pass

    # Try ISO date parsing
    return pd.to_datetime(series, utc=True)


def align_series(
    df_usd: pd.DataFrame,
    df_btc: pd.DataFrame,
    how: str = 'inner'
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Align two OHLC DataFrames on timestamps.

    Parameters
    ----------
    df_usd : pd.DataFrame
        Primary series (coinUSD)
    df_btc : pd.DataFrame
        Secondary series (coinBTC)
    how : str
        Join type: 'inner' (default), 'outer', 'left'

    Returns
    -------
    tuple
        (df_usd_aligned, df_btc_aligned) with matching indices
    """
    original_usd_len = len(df_usd)
    original_btc_len = len(df_btc)

    # Get common index
    if how == 'inner':
        common_idx = df_usd.index.intersection(df_btc.index)
    elif how == 'outer':
        common_idx = df_usd.index.union(df_btc.index)
    elif how == 'left':
        common_idx = df_usd.index
    else:
        raise ValueError(f"Unknown join type: {how}")

    common_idx = common_idx.sort_values()

    # Reindex both
    df_usd_aligned = df_usd.reindex(common_idx)
    df_btc_aligned = df_btc.reindex(common_idx)

    # Warn if significant data loss
    dropped_usd = original_usd_len - len(df_usd_aligned.dropna())
    dropped_btc = original_btc_len - len(df_btc_aligned.dropna())

    drop_pct_usd = (dropped_usd / original_usd_len) * 100 if original_usd_len > 0 else 0
    drop_pct_btc = (dropped_btc / original_btc_len) * 100 if original_btc_len > 0 else 0

    if drop_pct_usd > 5:
        warnings.warn(f"USD series alignment dropped {dropped_usd} rows ({drop_pct_usd:.1f}%)")
    if drop_pct_btc > 5:
        warnings.warn(f"BTC series alignment dropped {dropped_btc} rows ({drop_pct_btc:.1f}%)")

    return df_usd_aligned, df_btc_aligned


def validate_ohlc(df: pd.DataFrame) -> Dict[str, any]:
    """
    Validate OHLC data and return integrity report.

    Returns dict with:
    - is_valid: bool
    - issues: list of strings describing problems
    - stats: basic statistics
    """
    issues = []

    # Check for NaN values
    nan_counts = df.isna().sum()
    for col, count in nan_counts.items():
        if count > 0:
            issues.append(f"{col} has {count} NaN values")

    # Check OHLC consistency (high >= low, etc)
    if 'high' in df.columns and 'low' in df.columns:
        invalid_hl = (df['high'] < df['low']).sum()
        if invalid_hl > 0:
            issues.append(f"{invalid_hl} bars have high < low")

    if 'high' in df.columns and 'open' in df.columns:
        invalid_ho = (df['high'] < df['open']).sum()
        if invalid_ho > 0:
            issues.append(f"{invalid_ho} bars have high < open")

    if 'high' in df.columns and 'close' in df.columns:
        invalid_hc = (df['high'] < df['close']).sum()
        if invalid_hc > 0:
            issues.append(f"{invalid_hc} bars have high < close")

    if 'low' in df.columns and 'open' in df.columns:
        invalid_lo = (df['low'] > df['open']).sum()
        if invalid_lo > 0:
            issues.append(f"{invalid_lo} bars have low > open")

    if 'low' in df.columns and 'close' in df.columns:
        invalid_lc = (df['low'] > df['close']).sum()
        if invalid_lc > 0:
            issues.append(f"{invalid_lc} bars have low > close")

    # Check for gaps in daily data
    if len(df) > 1:
        time_diffs = df.index.to_series().diff().dropna()
        median_diff = time_diffs.median()
        large_gaps = (time_diffs > median_diff * 3).sum()
        if large_gaps > 0:
            issues.append(f"{large_gaps} potential gaps in data (>3x median interval)")

    stats = {
        'n_rows': len(df),
        'date_range': f"{df.index.min()} to {df.index.max()}" if len(df) > 0 else "empty",
        'columns': list(df.columns)
    }

    return {
        'is_valid': len(issues) == 0,
        'issues': issues,
        'stats': stats
    }
