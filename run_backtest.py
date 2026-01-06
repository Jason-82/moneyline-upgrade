#!/usr/bin/env python3
"""
Moneyline Backtesting CLI
=========================
Main entry point for running backtests.

Usage:
    python run_backtest.py --config config.yaml
    python run_backtest.py --data data/eth-usd.csv --strategy all
"""

import argparse
import sys
from pathlib import Path
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import load_ohlc_csv, align_series, validate_ohlc
from src.indicators import compute_all_indicators
from src.backtester import run_backtest, BacktestResult
from src.strategies import StrategyRunner
from src.evaluator import (
    compute_metrics,
    compare_systems,
    select_winner,
    walk_forward_evaluation
)
from src.reporter import (
    generate_full_report,
    save_pine_script,
    ensure_reports_dir
)
from src.qa import run_full_qa, print_qa_report


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def run_single_asset_backtest(
    usd_path: str,
    btc_path: str = None,
    config: dict = None,
    run_qa: bool = True
) -> dict:
    """
    Run backtest for a single asset.

    Parameters
    ----------
    usd_path : str
        Path to USD price CSV
    btc_path : str, optional
        Path to BTC price CSV for dual-series mode
    config : dict
        Full configuration dictionary
    run_qa : bool
        Whether to run QA checks

    Returns
    -------
    dict
        {
            'results': {system_name: BacktestResult},
            'comparison': DataFrame,
            'winner': str,
            'df': DataFrame with indicators,
            'qa_report': dict
        }
    """
    config = config or {}

    # Extract config sections
    data_config = config.get('data', {})
    ml_config = config.get('moneyline', {})
    contraction_config = config.get('contraction', {})
    breakout_config = config.get('breakout', {})
    dual_config = config.get('dual_series', {})
    bt_config = config.get('backtest', {})
    eval_config = config.get('evaluation', {})

    # Map config to function parameters
    moneyline_params = {
        'conv_period': ml_config.get('conversion_period', 9),
        'base_period': ml_config.get('base_period', 26),
        'fast_hma_period': ml_config.get('fast_hma_period', 5),
        'slow_ema_period': ml_config.get('slow_ema_period', 13),
        'exit_percent': ml_config.get('exit_percent', 2.0)
    }

    contraction_params = {
        'bb_period': contraction_config.get('bb_period', 20),
        'bb_std': contraction_config.get('bb_std', 2.0),
        'quantile_window': contraction_config.get('quantile_window', 252),
        'quantile_threshold': contraction_config.get('quantile_threshold', 0.20),
        'lookback_bars': contraction_config.get('lookback_bars', 20)
    }

    breakout_params = {
        'period': breakout_config.get('donchian_period', 20)
    }

    # Load data
    print(f"Loading data from {usd_path}...")
    column_mapping = data_config.get('column_mapping', None)
    df_usd = load_ohlc_csv(usd_path, column_mapping)

    # Validate data
    validation = validate_ohlc(df_usd)
    if not validation['is_valid']:
        print("Data validation issues:")
        for issue in validation['issues']:
            print(f"  - {issue}")

    print(f"Loaded {len(df_usd)} bars: {df_usd.index[0]} to {df_usd.index[-1]}")

    # Load BTC data if provided
    df_btc = None
    if btc_path and dual_config.get('enabled', False):
        print(f"Loading BTC data from {btc_path}...")
        df_btc = load_ohlc_csv(btc_path, column_mapping)
        df_usd, df_btc = align_series(df_usd, df_btc)
        print(f"Aligned to {len(df_usd)} common bars")

    # Compute all indicators
    print("Computing indicators...")
    df_with_indicators = compute_all_indicators(
        df_usd,
        moneyline_params=moneyline_params,
        contraction_params=contraction_params,
        breakout_params=breakout_params
    )

    # Initialize strategy runner
    strategy_runner = StrategyRunner(
        moneyline_params=moneyline_params,
        contraction_params=contraction_params,
        breakout_params=breakout_params,
        dual_series_config=dual_config
    )

    # Run strategies
    strategy_to_run = config.get('strategy', {}).get('run', 'all')
    results = {}

    if strategy_to_run in ['all', 'baseline']:
        print("Running Baseline strategy...")
        entry, exit = strategy_runner.run_baseline(df_usd, df_btc)
        results['baseline'] = run_backtest(
            df_usd, entry, exit,
            initial_capital=bt_config.get('initial_capital', 10000),
            fee_percent=bt_config.get('fee_percent', 0.1),
            slippage_bps=bt_config.get('slippage_bps', 5),
            fill_on_next_open=bt_config.get('fill_on_next_open', True)
        )
        print(f"  Baseline: {len(results['baseline'].trades)} trades")

    if strategy_to_run in ['all', 'filtered']:
        print("Running Filtered strategy...")
        entry, exit = strategy_runner.run_filtered(df_usd, df_btc)
        results['filtered'] = run_backtest(
            df_usd, entry, exit,
            initial_capital=bt_config.get('initial_capital', 10000),
            fee_percent=bt_config.get('fee_percent', 0.1),
            slippage_bps=bt_config.get('slippage_bps', 5),
            fill_on_next_open=bt_config.get('fill_on_next_open', True)
        )
        print(f"  Filtered: {len(results['filtered'].trades)} trades")

    if strategy_to_run in ['all', 'hybrid']:
        print("Running Hybrid strategy...")
        entry, exit = strategy_runner.run_hybrid(df_usd, df_btc)
        results['hybrid'] = run_backtest(
            df_usd, entry, exit,
            initial_capital=bt_config.get('initial_capital', 10000),
            fee_percent=bt_config.get('fee_percent', 0.1),
            slippage_bps=bt_config.get('slippage_bps', 5),
            fill_on_next_open=bt_config.get('fill_on_next_open', True)
        )
        print(f"  Hybrid: {len(results['hybrid'].trades)} trades")

    # Compare systems
    print("\nComparing systems...")
    comparison = compare_systems(
        results,
        chop_max_duration=eval_config.get('chop_max_duration', 10),
        min_duration_days=eval_config.get('true_trend_min_duration', 30),
        min_pnl_pct=eval_config.get('true_trend_min_pnl_pct', 10.0),
        match_window_days=eval_config.get('trade_match_window_days', 5)
    )

    winner = select_winner(comparison)
    print(f"\nWinner: {winner}")

    # Run QA
    qa_report = None
    if run_qa:
        print("\nRunning QA checks...")
        sample_trades = results.get('baseline', results[list(results.keys())[0]]).trades
        qa_report = run_full_qa(
            df_with_indicators,
            sample_trades,
            donchian_period=breakout_params.get('period', 20),
            quantile_window=contraction_params.get('quantile_window', 252),
            quantile_threshold=contraction_params.get('quantile_threshold', 0.20)
        )
        print_qa_report(qa_report)

    return {
        'results': results,
        'comparison': comparison,
        'winner': winner,
        'df': df_with_indicators,
        'qa_report': qa_report,
        'config': config
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Moneyline Backtesting CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run_backtest.py --config config.yaml
  python run_backtest.py --data data/eth-usd.csv --strategy all
  python run_backtest.py --data data/eth-usd.csv --btc data/eth-btc.csv --dual
        '''
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config.yaml',
        help='Path to YAML configuration file'
    )
    parser.add_argument(
        '--data', '-d',
        type=str,
        help='Path to OHLC CSV (overrides config)'
    )
    parser.add_argument(
        '--btc',
        type=str,
        help='Path to BTC OHLC CSV for dual-series mode'
    )
    parser.add_argument(
        '--strategy', '-s',
        type=str,
        choices=['baseline', 'filtered', 'hybrid', 'all'],
        default='all',
        help='Strategy to run'
    )
    parser.add_argument(
        '--dual',
        action='store_true',
        help='Enable dual-series mode'
    )
    parser.add_argument(
        '--no-qa',
        action='store_true',
        help='Skip QA checks'
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Skip report generation'
    )
    parser.add_argument(
        '--walk-forward',
        action='store_true',
        help='Run walk-forward evaluation'
    )
    parser.add_argument(
        '--pine',
        action='store_true',
        help='Generate Pine Script for winning strategy'
    )
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='reports',
        help='Output directory for reports'
    )

    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        print(f"Loading config from {config_path}")
        config = load_config(str(config_path))
    else:
        print(f"Config file not found, using defaults")
        config = {}

    # Override with command line args
    if args.data:
        if 'data' not in config:
            config['data'] = {}
        config['data']['usd_path'] = args.data

    if args.btc:
        if 'data' not in config:
            config['data'] = {}
        config['data']['btc_path'] = args.btc

    if args.dual:
        if 'dual_series' not in config:
            config['dual_series'] = {}
        config['dual_series']['enabled'] = True

    if args.strategy:
        if 'strategy' not in config:
            config['strategy'] = {}
        config['strategy']['run'] = args.strategy

    if args.output_dir:
        if 'output' not in config:
            config['output'] = {}
        config['output']['reports_dir'] = args.output_dir

    # Get data paths
    usd_path = config.get('data', {}).get('usd_path')
    btc_path = config.get('data', {}).get('btc_path')

    if not usd_path:
        print("ERROR: No data path provided. Use --data or set data.usd_path in config.")
        sys.exit(1)

    if not Path(usd_path).exists():
        print(f"ERROR: Data file not found: {usd_path}")
        sys.exit(1)

    # Run backtest
    result = run_single_asset_backtest(
        usd_path=usd_path,
        btc_path=btc_path,
        config=config,
        run_qa=not args.no_qa
    )

    # Print comparison table
    print("\n" + "=" * 80)
    print("STRATEGY COMPARISON")
    print("=" * 80)
    print(result['comparison'].to_string(index=False))
    print("=" * 80)

    # Generate report
    if not args.no_report:
        reports_dir = config.get('output', {}).get('reports_dir', 'reports')
        asset_name = Path(usd_path).stem.upper()

        print(f"\nGenerating reports in {reports_dir}/...")
        try:
            output_files = generate_full_report(
                result['df'],
                result['results'],
                asset_name,
                reports_dir,
                config
            )
            print("Reports generated:")
            for name, path in output_files.items():
                print(f"  {name}: {path}")
        except Exception as e:
            print(f"Warning: Could not generate some reports: {e}")

    # Generate Pine Script
    if args.pine:
        reports_dir = config.get('output', {}).get('reports_dir', 'reports')
        ensure_reports_dir(reports_dir)

        pine_path = Path(reports_dir) / "moneyline_overlay.pine"

        # Collect parameters for Pine script
        pine_params = {
            'conv_period': config.get('moneyline', {}).get('conversion_period', 9),
            'base_period': config.get('moneyline', {}).get('base_period', 26),
            'fast_hma_period': config.get('moneyline', {}).get('fast_hma_period', 5),
            'slow_ema_period': config.get('moneyline', {}).get('slow_ema_period', 13),
            'exit_percent': config.get('moneyline', {}).get('exit_percent', 2.0),
            'bb_period': config.get('contraction', {}).get('bb_period', 20),
            'bb_std': config.get('contraction', {}).get('bb_std', 2.0),
            'quantile_window': config.get('contraction', {}).get('quantile_window', 252),
            'quantile_threshold': config.get('contraction', {}).get('quantile_threshold', 0.20),
            'contraction_lookback': config.get('contraction', {}).get('lookback_bars', 20),
            'donchian_period': config.get('breakout', {}).get('donchian_period', 20)
        }

        save_pine_script(
            pine_params,
            str(pine_path),
            include_dual_series=config.get('dual_series', {}).get('enabled', False)
        )

    # Walk-forward evaluation
    if args.walk_forward:
        print("\nRunning walk-forward evaluation...")
        from src.strategies import StrategyRunner
        from src.backtester import run_backtest

        ml_config = config.get('moneyline', {})
        contraction_config = config.get('contraction', {})
        breakout_config = config.get('breakout', {})

        runner = StrategyRunner(
            moneyline_params={
                'conv_period': ml_config.get('conversion_period', 9),
                'base_period': ml_config.get('base_period', 26),
                'fast_hma_period': ml_config.get('fast_hma_period', 5),
                'slow_ema_period': ml_config.get('slow_ema_period', 13),
                'exit_percent': ml_config.get('exit_percent', 2.0)
            },
            contraction_params={
                'bb_period': contraction_config.get('bb_period', 20),
                'bb_std': contraction_config.get('bb_std', 2.0),
                'quantile_window': contraction_config.get('quantile_window', 252),
                'quantile_threshold': contraction_config.get('quantile_threshold', 0.20),
                'lookback_bars': contraction_config.get('lookback_bars', 20)
            },
            breakout_params={
                'donchian_period': breakout_config.get('donchian_period', 20)
            }
        )

        bt_config = config.get('backtest', {})

        def backtest_func(df, entry, exit):
            return run_backtest(
                df, entry, exit,
                initial_capital=bt_config.get('initial_capital', 10000),
                fee_percent=bt_config.get('fee_percent', 0.1),
                slippage_bps=bt_config.get('slippage_bps', 5)
            )

        wf_config = config.get('evaluation', {}).get('walk_forward', {})
        wf_results = walk_forward_evaluation(
            result['df'],
            runner,
            backtest_func,
            train_ratio=wf_config.get('train_ratio', 0.7),
            param_grid=wf_config.get('param_sweep', None)
        )

        print("\nWalk-Forward Results:")
        print("-" * 40)
        for sys_name, sys_result in wf_results['test_results'].items():
            metrics = sys_result['metrics']
            params = sys_result['params']
            print(f"\n{sys_name.upper()}:")
            print(f"  Params: q={params['q']}, M={params['m']}, N={params['n']}")
            print(f"  Train Sharpe: {params['train_sharpe']:.3f}")
            print(f"  Test Return: {metrics.total_return_pct:.2f}%")
            print(f"  Test Sharpe: {metrics.sharpe_ratio:.3f}")
            print(f"  Test Trades: {metrics.num_trades}")

    print("\nDone!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
