"""
QA / Lookahead & Data Integrity Module (Agent 8)
================================================
Audits the pipeline for lookahead bias and data leakage.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import warnings


def verify_no_lookahead_donchian(
    df: pd.DataFrame,
    donchian_period: int = 20
) -> Dict:
    """
    Verify Donchian channel uses only prior bars.

    Test: donch_high[t] should equal max(high[t-N:t-1])

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'high' and 'donch_high' columns
    donchian_period : int
        Expected Donchian period

    Returns
    -------
    dict
        passed: bool
        violations: list of (index, expected, actual)
    """
    if 'donch_high' not in df.columns:
        return {'passed': False, 'error': 'donch_high column not found'}

    violations = []
    n = donchian_period

    for i in range(n + 1, len(df)):
        # Prior N bars (excluding current)
        prior_highs = df['high'].iloc[i-n:i]
        expected = prior_highs.max()
        actual = df['donch_high'].iloc[i]

        if not np.isclose(expected, actual, rtol=1e-6):
            violations.append({
                'index': df.index[i],
                'expected': expected,
                'actual': actual
            })

    passed = len(violations) == 0
    return {
        'passed': passed,
        'violations': violations[:10],  # Limit output
        'total_violations': len(violations)
    }


def verify_no_lookahead_quantile(
    df: pd.DataFrame,
    quantile_window: int = 252,
    quantile_threshold: float = 0.20
) -> Dict:
    """
    Verify BBW quantile uses only prior values.

    Test: bbw_threshold[t] should use BBW[t-window:t-1] (not including t)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'bbw' and 'bbw_threshold' columns
    quantile_window : int
        Quantile window size
    quantile_threshold : float
        Quantile threshold

    Returns
    -------
    dict
        passed: bool
        violations: list
    """
    if 'bbw' not in df.columns or 'bbw_threshold' not in df.columns:
        return {'passed': False, 'error': 'Required columns not found'}

    violations = []
    window = quantile_window

    for i in range(window + 1, len(df)):
        # Prior window values (excluding current)
        prior_bbw = df['bbw'].iloc[i-window:i]
        expected = prior_bbw.quantile(quantile_threshold)
        actual = df['bbw_threshold'].iloc[i]

        if pd.notna(expected) and pd.notna(actual):
            if not np.isclose(expected, actual, rtol=1e-4):
                violations.append({
                    'index': df.index[i],
                    'expected': expected,
                    'actual': actual,
                    'diff': abs(expected - actual)
                })

    passed = len(violations) == 0
    return {
        'passed': passed,
        'violations': violations[:10],
        'total_violations': len(violations)
    }


def verify_fill_timing(trades: List, df: pd.DataFrame) -> Dict:
    """
    Verify trades are filled at next bar's open, not signal bar's close.

    Test: For each trade, entry_price should match df['open'] at entry_bar_idx

    Parameters
    ----------
    trades : list of Trade
        List of executed trades
    df : pd.DataFrame
        OHLC DataFrame

    Returns
    -------
    dict
        passed: bool
        violations: list
    """
    violations = []

    for trade in trades:
        idx = trade.entry_bar_idx
        if idx >= len(df):
            continue

        expected_open = df['open'].iloc[idx]

        # Allow for slippage adjustment
        price_ratio = trade.entry_price / expected_open
        if price_ratio < 0.99 or price_ratio > 1.01:  # More than 1% off
            violations.append({
                'entry_time': trade.entry_time,
                'expected_open': expected_open,
                'actual_entry': trade.entry_price,
                'ratio': price_ratio
            })

    passed = len(violations) == 0
    return {
        'passed': passed,
        'violations': violations[:10],
        'total_violations': len(violations)
    }


def verify_crossover_logic(df: pd.DataFrame) -> Dict:
    """
    Verify crossover detection uses current and prior bar only.

    Test: long_cross[t] should be True iff:
        fast_hma[t] > slow_ma[t] AND fast_hma[t-1] <= slow_ma[t-1]

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with indicator columns

    Returns
    -------
    dict
    """
    if 'fast_hma' not in df.columns or 'slow_ma' not in df.columns:
        return {'passed': False, 'error': 'Required columns not found'}

    if 'long_cross' not in df.columns:
        return {'passed': False, 'error': 'long_cross column not found'}

    violations = []

    for i in range(1, len(df)):
        fast_now = df['fast_hma'].iloc[i]
        slow_now = df['slow_ma'].iloc[i]
        fast_prev = df['fast_hma'].iloc[i-1]
        slow_prev = df['slow_ma'].iloc[i-1]

        if pd.isna(fast_now) or pd.isna(slow_now):
            continue

        expected = (fast_now > slow_now) and (fast_prev <= slow_prev)
        actual = df['long_cross'].iloc[i]

        if expected != actual:
            violations.append({
                'index': df.index[i],
                'expected': expected,
                'actual': actual
            })

    passed = len(violations) == 0
    return {
        'passed': passed,
        'violations': violations[:10],
        'total_violations': len(violations)
    }


def check_data_integrity(df: pd.DataFrame) -> Dict:
    """
    Check OHLC data integrity.

    Checks:
    - No NaN in critical columns
    - High >= Low
    - High >= Open, Close
    - Low <= Open, Close
    - Monotonic index
    - No duplicate timestamps

    Parameters
    ----------
    df : pd.DataFrame
        OHLC DataFrame

    Returns
    -------
    dict
        issues: list of strings
        stats: basic statistics
    """
    issues = []

    # Check for NaN values
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                issues.append(f"WARNING: {col} has {nan_count} NaN values")

    # Check OHLC consistency
    if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        # High >= Low
        invalid = (df['high'] < df['low']).sum()
        if invalid > 0:
            issues.append(f"ERROR: {invalid} bars have high < low")

        # High >= Open
        invalid = (df['high'] < df['open']).sum()
        if invalid > 0:
            issues.append(f"ERROR: {invalid} bars have high < open")

        # High >= Close
        invalid = (df['high'] < df['close']).sum()
        if invalid > 0:
            issues.append(f"ERROR: {invalid} bars have high < close")

        # Low <= Open
        invalid = (df['low'] > df['open']).sum()
        if invalid > 0:
            issues.append(f"ERROR: {invalid} bars have low > open")

        # Low <= Close
        invalid = (df['low'] > df['close']).sum()
        if invalid > 0:
            issues.append(f"ERROR: {invalid} bars have low > close")

    # Check index
    if not df.index.is_monotonic_increasing:
        issues.append("ERROR: Index is not monotonically increasing")

    if df.index.duplicated().any():
        dup_count = df.index.duplicated().sum()
        issues.append(f"ERROR: {dup_count} duplicate timestamps found")

    # Check for gaps
    if len(df) > 1:
        time_diffs = df.index.to_series().diff().dropna()
        median_diff = time_diffs.median()
        large_gaps = time_diffs[time_diffs > median_diff * 7]  # More than a week
        if len(large_gaps) > 0:
            issues.append(f"WARNING: {len(large_gaps)} large gaps in data (>7x median interval)")

    # Stats
    stats = {
        'n_rows': len(df),
        'start_date': str(df.index[0]) if len(df) > 0 else None,
        'end_date': str(df.index[-1]) if len(df) > 0 else None,
        'n_issues': len(issues)
    }

    return {
        'is_valid': len([i for i in issues if i.startswith('ERROR')]) == 0,
        'issues': issues,
        'stats': stats
    }


def check_alignment_integrity(
    df_usd: pd.DataFrame,
    df_btc: pd.DataFrame,
    max_drop_pct: float = 10.0
) -> Dict:
    """
    Check dual-series alignment integrity.

    Parameters
    ----------
    df_usd : pd.DataFrame
    df_btc : pd.DataFrame
    max_drop_pct : float
        Maximum acceptable row drop percentage

    Returns
    -------
    dict
    """
    common_idx = df_usd.index.intersection(df_btc.index)
    usd_only = df_usd.index.difference(df_btc.index)
    btc_only = df_btc.index.difference(df_usd.index)

    usd_drop_pct = len(usd_only) / len(df_usd) * 100 if len(df_usd) > 0 else 0
    btc_drop_pct = len(btc_only) / len(df_btc) * 100 if len(df_btc) > 0 else 0

    issues = []
    if usd_drop_pct > max_drop_pct:
        issues.append(f"WARNING: USD series loses {usd_drop_pct:.1f}% rows in alignment")
    if btc_drop_pct > max_drop_pct:
        issues.append(f"WARNING: BTC series loses {btc_drop_pct:.1f}% rows in alignment")

    return {
        'common_bars': len(common_idx),
        'usd_only_bars': len(usd_only),
        'btc_only_bars': len(btc_only),
        'usd_drop_pct': usd_drop_pct,
        'btc_drop_pct': btc_drop_pct,
        'issues': issues
    }


def run_full_qa(
    df: pd.DataFrame,
    trades: List,
    donchian_period: int = 20,
    quantile_window: int = 252,
    quantile_threshold: float = 0.20
) -> Dict:
    """
    Run full QA suite and return comprehensive report.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with all indicators computed
    trades : list
        List of executed trades
    donchian_period : int
    quantile_window : int
    quantile_threshold : float

    Returns
    -------
    dict
        Comprehensive QA report
    """
    results = {}

    # Data integrity
    print("Checking data integrity...")
    results['data_integrity'] = check_data_integrity(df)

    # Donchian lookahead
    print("Checking Donchian lookahead...")
    results['donchian_lookahead'] = verify_no_lookahead_donchian(df, donchian_period)

    # Quantile lookahead
    print("Checking quantile lookahead...")
    results['quantile_lookahead'] = verify_no_lookahead_quantile(
        df, quantile_window, quantile_threshold
    )

    # Crossover logic
    print("Checking crossover logic...")
    results['crossover_logic'] = verify_crossover_logic(df)

    # Fill timing
    if trades:
        print("Checking fill timing...")
        results['fill_timing'] = verify_fill_timing(trades, df)

    # Summary
    all_passed = all(
        r.get('passed', True) for r in results.values()
        if isinstance(r, dict) and 'passed' in r
    )
    all_valid = results['data_integrity'].get('is_valid', False)

    results['summary'] = {
        'all_tests_passed': all_passed,
        'data_is_valid': all_valid,
        'trust_results': all_passed and all_valid
    }

    return results


def print_qa_report(qa_results: Dict) -> None:
    """
    Print formatted QA report.

    Parameters
    ----------
    qa_results : dict
        Output from run_full_qa()
    """
    print("\n" + "=" * 60)
    print("QA / DATA INTEGRITY REPORT")
    print("=" * 60)

    # Data integrity
    di = qa_results.get('data_integrity', {})
    print(f"\nData Integrity: {'PASS' if di.get('is_valid') else 'FAIL'}")
    for issue in di.get('issues', []):
        print(f"  - {issue}")
    stats = di.get('stats', {})
    print(f"  Rows: {stats.get('n_rows', 'N/A')}")
    print(f"  Date range: {stats.get('start_date', 'N/A')} to {stats.get('end_date', 'N/A')}")

    # Donchian lookahead
    dl = qa_results.get('donchian_lookahead', {})
    print(f"\nDonchian Lookahead: {'PASS' if dl.get('passed') else 'FAIL'}")
    if not dl.get('passed'):
        print(f"  Total violations: {dl.get('total_violations', 0)}")

    # Quantile lookahead
    ql = qa_results.get('quantile_lookahead', {})
    print(f"\nQuantile Lookahead: {'PASS' if ql.get('passed') else 'FAIL'}")
    if not ql.get('passed'):
        print(f"  Total violations: {ql.get('total_violations', 0)}")

    # Crossover logic
    cl = qa_results.get('crossover_logic', {})
    print(f"\nCrossover Logic: {'PASS' if cl.get('passed') else 'FAIL'}")
    if not cl.get('passed'):
        print(f"  Total violations: {cl.get('total_violations', 0)}")

    # Fill timing
    if 'fill_timing' in qa_results:
        ft = qa_results['fill_timing']
        print(f"\nFill Timing: {'PASS' if ft.get('passed') else 'FAIL'}")
        if not ft.get('passed'):
            print(f"  Total violations: {ft.get('total_violations', 0)}")

    # Summary
    summary = qa_results.get('summary', {})
    print("\n" + "-" * 60)
    print(f"ALL TESTS PASSED: {'YES' if summary.get('all_tests_passed') else 'NO'}")
    print(f"TRUST RESULTS: {'YES' if summary.get('trust_results') else 'NO'}")
    print("=" * 60 + "\n")
