#!/usr/bin/env python3
"""
Moneyline Watchlist Scanner
===========================
Scans a list of tickers and reports Moneyline status changes.

Data Sources:
1. Local CSV files (TradingView exports) - put them in data/ directory
2. Alpha Vantage API (get free key at https://www.alphavantage.co/support/#api-key)

Usage:
    python scanner.py                           # Scan from local CSV files
    python scanner.py --api ALPHA_VANTAGE_KEY   # Use Alpha Vantage API
    python scanner.py -w my_tickers.txt --all   # Custom watchlist, show all
"""

import argparse
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from io import StringIO

import pandas as pd
import numpy as np
import requests

# Import our indicator library
sys.path.insert(0, str(Path(__file__).parent / "src"))
from indicators import compute_moneyline


def load_watchlist(path: str) -> List[str]:
    """Load ticker symbols from a watchlist file (one per line)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Watchlist not found: {path}")

    tickers = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                # Handle comma-separated tickers on same line
                for ticker in line.split(','):
                    ticker = ticker.strip().upper()
                    if ticker:
                        tickers.append(ticker)

    return tickers


def load_from_local_csv(ticker: str, data_dir: str = 'data') -> Optional[pd.DataFrame]:
    """
    Load OHLC data from local CSV file.

    Looks for files like:
    - data/AAPL.csv
    - data/aapl.csv
    - data/AAPL-daily.csv

    Expected CSV format (TradingView export):
    time,open,high,low,close,volume
    """
    data_path = Path(data_dir)

    # Try different filename patterns
    patterns = [
        f"{ticker}.csv",
        f"{ticker.lower()}.csv",
        f"{ticker}-daily.csv",
        f"{ticker.lower()}-daily.csv",
        f"{ticker}_daily.csv",
    ]

    csv_path = None
    for pattern in patterns:
        candidate = data_path / pattern
        if candidate.exists():
            csv_path = candidate
            break

    if csv_path is None:
        return None

    try:
        df = pd.read_csv(csv_path)

        # Normalize column names
        df.columns = df.columns.str.lower()

        # Handle various timestamp column names
        time_col = None
        for col in ['time', 'timestamp', 'date', 'datetime']:
            if col in df.columns:
                time_col = col
                break

        if time_col is None:
            return None

        df['date'] = pd.to_datetime(df[time_col])
        df = df.set_index('date')
        df = df.sort_index()

        # Keep only OHLCV
        cols = ['open', 'high', 'low', 'close', 'volume']
        df = df[[c for c in cols if c in df.columns]]

        return df

    except Exception as e:
        return None


def fetch_alpha_vantage(ticker: str, api_key: str) -> Optional[pd.DataFrame]:
    """
    Fetch OHLC data from Alpha Vantage API.

    Free tier: 25 requests/day, 5/minute
    Get key at: https://www.alphavantage.co/support/#api-key
    """
    try:
        url = 'https://www.alphavantage.co/query'
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': ticker,
            'apikey': api_key,
            'outputsize': 'compact'  # Last 100 data points
        }

        response = requests.get(url, params=params, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()

        if 'Time Series (Daily)' not in data:
            # Check for API limit message
            if 'Note' in data or 'Information' in data:
                print(f"\n  API limit reached for {ticker}")
            return None

        ts_data = data['Time Series (Daily)']

        # Convert to DataFrame
        df = pd.DataFrame.from_dict(ts_data, orient='index')
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # Rename columns
        df = df.rename(columns={
            '1. open': 'open',
            '2. high': 'high',
            '3. low': 'low',
            '4. close': 'close',
            '5. volume': 'volume'
        })

        # Convert to numeric
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    except Exception as e:
        return None


def scan_ticker(
    ticker: str,
    data_dir: str = 'data',
    api_key: str = None,
    conv_period: int = 9,
    base_period: int = 26,
    fast_hma_period: int = 5,
    slow_ema_period: int = 13,
    exit_percent: float = 2.0
) -> Optional[Dict]:
    """
    Scan a single ticker for Moneyline status.

    Returns dict with:
    - ticker: symbol
    - status: 'GREEN' or 'RED'
    - flipped: 'green', 'red', or None
    - price: current close
    - fast_hma: current fast HMA value
    - slow_ma: current slow MA value
    - date: date of latest bar
    """
    # Try to get data
    df = None

    # First try local CSV
    df = load_from_local_csv(ticker, data_dir)

    # If not found and API key provided, try Alpha Vantage
    if df is None and api_key:
        df = fetch_alpha_vantage(ticker, api_key)
        time.sleep(0.5)  # Rate limiting

    if df is None or len(df) < base_period + 5:
        return None

    # Compute Moneyline indicators
    result = compute_moneyline(
        df,
        conv_period=conv_period,
        base_period=base_period,
        fast_hma_period=fast_hma_period,
        slow_ema_period=slow_ema_period,
        exit_percent=exit_percent
    )

    # Get current and previous values
    if len(result) < 2:
        return None

    current = result.iloc[-1]
    previous = result.iloc[-2]

    # Determine current status
    is_green = current['trend_green']
    was_green = previous['trend_green']

    # Detect flip
    flipped = None
    if is_green and not was_green:
        flipped = 'green'
    elif not is_green and was_green:
        flipped = 'red'

    return {
        'ticker': ticker,
        'status': 'GREEN' if is_green else 'RED',
        'flipped': flipped,
        'price': current['close'],
        'fast_hma': current['fast_hma'],
        'slow_ma': current['slow_ma'],
        'date': result.index[-1].strftime('%Y-%m-%d'),
        'pct_above': ((current['fast_hma'] / current['slow_ma']) - 1) * 100
    }


def scan_watchlist(
    tickers: List[str],
    data_dir: str = 'data',
    api_key: str = None,
    moneyline_params: dict = None
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Scan all tickers in watchlist.

    Returns:
        (flipped_green, flipped_red, all_results)
    """
    params = moneyline_params or {}

    flipped_green = []
    flipped_red = []
    all_results = []
    failed = []

    total = len(tickers)

    for i, ticker in enumerate(tickers, 1):
        print(f"\r  Scanning {i}/{total}: {ticker:6s}...", end='', flush=True)

        result = scan_ticker(ticker, data_dir=data_dir, api_key=api_key, **params)

        if result is None:
            failed.append(ticker)
            continue

        all_results.append(result)

        if result['flipped'] == 'green':
            flipped_green.append(result)
        elif result['flipped'] == 'red':
            flipped_red.append(result)

    print()  # Newline after progress

    if failed:
        print(f"  Not found: {', '.join(failed)}")

    return flipped_green, flipped_red, all_results


def format_result(r: Dict) -> str:
    """Format a single result for display."""
    pct = r['pct_above']
    sign = '+' if pct >= 0 else ''
    return f"  {r['ticker']:8s} | {r['status']:5s} | ${r['price']:>10,.2f} | {sign}{pct:.1f}%"


def print_digest(
    flipped_green: List[Dict],
    flipped_red: List[Dict],
    all_results: List[Dict],
    show_all: bool = False
):
    """Print the daily digest."""
    date = datetime.now().strftime('%Y-%m-%d')

    print("\n" + "="*60)
    print(f"  MONEYLINE DAILY DIGEST - {date}")
    print("="*60)

    # Flipped GREEN (bullish)
    print(f"\n  TURNED GREEN TODAY ({len(flipped_green)})")
    print("-"*50)
    if flipped_green:
        print(f"  {'Ticker':8s} | {'Status':5s} | {'Price':>12s} | % Above MA")
        print("-"*50)
        for r in sorted(flipped_green, key=lambda x: x['pct_above'], reverse=True):
            print(format_result(r))
    else:
        print("  None")

    # Flipped RED (bearish)
    print(f"\n  TURNED RED TODAY ({len(flipped_red)})")
    print("-"*50)
    if flipped_red:
        print(f"  {'Ticker':8s} | {'Status':5s} | {'Price':>12s} | % Above MA")
        print("-"*50)
        for r in sorted(flipped_red, key=lambda x: x['pct_above']):
            print(format_result(r))
    else:
        print("  None")

    # Summary stats
    n_green = sum(1 for r in all_results if r['status'] == 'GREEN')
    n_red = sum(1 for r in all_results if r['status'] == 'RED')
    total = len(all_results)

    print(f"\n  SUMMARY")
    print("-"*50)
    print(f"  Total scanned: {total}")
    if total > 0:
        print(f"  Currently GREEN: {n_green} ({100*n_green/total:.1f}%)")
        print(f"  Currently RED:   {n_red} ({100*n_red/total:.1f}%)")
    else:
        print("  No data available")

    if show_all and all_results:
        print(f"\n  ALL TICKERS (sorted by % above slow MA)")
        print("-"*50)
        print(f"  {'Ticker':8s} | {'Status':5s} | {'Price':>12s} | % Above MA")
        print("-"*50)
        for r in sorted(all_results, key=lambda x: x['pct_above'], reverse=True):
            print(format_result(r))

    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Scan watchlist for Moneyline status changes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Data Sources:
  1. Local CSV files in data/ directory (default)
     Export from TradingView: Chart -> Export -> Export chart data
     Save as data/TICKER.csv

  2. Alpha Vantage API (free, 25 requests/day)
     Get key: https://www.alphavantage.co/support/#api-key
     Use: python scanner.py --api YOUR_API_KEY

Examples:
  python scanner.py                      # Scan from local CSVs
  python scanner.py --all                # Show all tickers, not just flips
  python scanner.py --api DEMO           # Use Alpha Vantage demo key
  python scanner.py -o results.csv       # Save to CSV file
        """
    )
    parser.add_argument(
        '-w', '--watchlist',
        default='watchlist.txt',
        help='Path to watchlist file (default: watchlist.txt)'
    )
    parser.add_argument(
        '-d', '--data-dir',
        default='data',
        help='Directory containing CSV files (default: data/)'
    )
    parser.add_argument(
        '--api',
        help='Alpha Vantage API key (get free at alphavantage.co)'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Show all tickers, not just flips'
    )
    parser.add_argument(
        '--conv-period', type=int, default=9,
        help='Tenkan period (default: 9)'
    )
    parser.add_argument(
        '--base-period', type=int, default=26,
        help='Kijun period (default: 26)'
    )
    parser.add_argument(
        '--fast-hma', type=int, default=5,
        help='Fast HMA period (default: 5)'
    )
    parser.add_argument(
        '--slow-ema', type=int, default=13,
        help='Slow EMA period (default: 13)'
    )
    parser.add_argument(
        '--exit-pct', type=float, default=2.0,
        help='Exit percent (default: 2.0)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Save results to CSV file'
    )

    args = parser.parse_args()

    # Load watchlist
    print(f"\nLoading watchlist from: {args.watchlist}")
    try:
        tickers = load_watchlist(args.watchlist)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("\nCreate a watchlist.txt file with one ticker per line, e.g.:")
        print("  AAPL")
        print("  MSFT")
        print("  GOOGL")
        sys.exit(1)

    print(f"Found {len(tickers)} tickers")

    # Show data source
    if args.api:
        print(f"Data source: Alpha Vantage API")
    else:
        print(f"Data source: Local CSV files in {args.data_dir}/")
    print()

    # Scan
    params = {
        'conv_period': args.conv_period,
        'base_period': args.base_period,
        'fast_hma_period': args.fast_hma,
        'slow_ema_period': args.slow_ema,
        'exit_percent': args.exit_pct
    }

    flipped_green, flipped_red, all_results = scan_watchlist(
        tickers,
        data_dir=args.data_dir,
        api_key=args.api,
        moneyline_params=params
    )

    # Print digest
    print_digest(flipped_green, flipped_red, all_results, show_all=args.all)

    # Optionally save to CSV
    if args.output and all_results:
        df = pd.DataFrame(all_results)
        df.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")


if __name__ == '__main__':
    main()
