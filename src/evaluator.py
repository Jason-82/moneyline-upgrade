"""
Evaluation Module (Agent 6)
===========================
Computes performance metrics, true trend capture analysis, and walk-forward evaluation.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta

from .backtester import BacktestResult, Trade


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    total_return_pct: float
    cagr: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    num_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    avg_duration_days: float
    exposure_pct: float
    chop_ratio: float

    def to_dict(self) -> dict:
        return {
            'Total Return (%)': round(self.total_return_pct, 2),
            'CAGR (%)': round(self.cagr, 2),
            'Max Drawdown (%)': round(self.max_drawdown_pct, 2),
            'Sharpe Ratio': round(self.sharpe_ratio, 3),
            'Sortino Ratio': round(self.sortino_ratio, 3),
            'Num Trades': self.num_trades,
            'Win Rate (%)': round(self.win_rate * 100, 1),
            'Avg Win (%)': round(self.avg_win_pct, 2),
            'Avg Loss (%)': round(self.avg_loss_pct, 2),
            'Profit Factor': round(self.profit_factor, 2),
            'Avg Duration (days)': round(self.avg_duration_days, 1),
            'Exposure (%)': round(self.exposure_pct, 1),
            'Chop Ratio (%)': round(self.chop_ratio * 100, 1)
        }


def compute_metrics(
    result: BacktestResult,
    chop_max_duration: int = 10,
    risk_free_rate: float = 0.0
) -> PerformanceMetrics:
    """
    Compute comprehensive performance metrics.

    Parameters
    ----------
    result : BacktestResult
        Backtest result containing trades and equity curve
    chop_max_duration : int
        Maximum duration (days) for a trade to be considered "chop"
    risk_free_rate : float
        Annual risk-free rate for Sharpe calculation

    Returns
    -------
    PerformanceMetrics
    """
    equity = result.equity_curve
    trades = result.trades
    position = result.position_series

    # Total Return
    total_return_pct = ((result.final_equity / result.initial_capital) - 1) * 100

    # CAGR
    if len(equity) > 1:
        years = (equity.index[-1] - equity.index[0]).days / 365.25
        if years > 0:
            cagr = ((result.final_equity / result.initial_capital) ** (1 / years) - 1) * 100
        else:
            cagr = 0.0
    else:
        cagr = 0.0

    # Max Drawdown
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown_pct = abs(drawdown.min())

    # Daily returns for Sharpe/Sortino
    daily_returns = equity.pct_change().dropna()
    if len(daily_returns) > 0:
        mean_return = daily_returns.mean()
        std_return = daily_returns.std()
        downside_std = daily_returns[daily_returns < 0].std()

        daily_rf = risk_free_rate / 252
        sharpe_ratio = (mean_return - daily_rf) / std_return * np.sqrt(252) if std_return > 0 else 0
        sortino_ratio = (mean_return - daily_rf) / downside_std * np.sqrt(252) if downside_std > 0 else 0
    else:
        sharpe_ratio = 0.0
        sortino_ratio = 0.0

    # Trade statistics
    num_trades = len(trades)
    if num_trades > 0:
        pnls = [t.net_pnl_pct for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = len(wins) / num_trades
        avg_win_pct = np.mean(wins) if wins else 0.0
        avg_loss_pct = np.mean(losses) if losses else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        avg_duration_days = np.mean([t.duration_days for t in trades])

        # Chop ratio: % of trades with short duration and negative PnL
        chop_trades = [t for t in trades
                       if t.duration_days <= chop_max_duration and t.net_pnl_pct < 0]
        chop_ratio = len(chop_trades) / num_trades
    else:
        win_rate = 0.0
        avg_win_pct = 0.0
        avg_loss_pct = 0.0
        profit_factor = 0.0
        avg_duration_days = 0.0
        chop_ratio = 0.0

    # Exposure (% time in market)
    exposure_pct = position.mean() * 100

    return PerformanceMetrics(
        total_return_pct=total_return_pct,
        cagr=cagr,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        num_trades=num_trades,
        win_rate=win_rate,
        avg_win_pct=avg_win_pct,
        avg_loss_pct=avg_loss_pct,
        profit_factor=profit_factor,
        avg_duration_days=avg_duration_days,
        exposure_pct=exposure_pct,
        chop_ratio=chop_ratio
    )


def label_true_trends(
    trades: List[Trade],
    min_duration_days: int = 30,
    min_pnl_pct: float = 10.0
) -> List[Tuple[Trade, bool]]:
    """
    Label trades as TRUE_TREND or not.

    A trade is TRUE_TREND if:
    - duration_days >= min_duration_days
    - pnl_pct >= min_pnl_pct

    Parameters
    ----------
    trades : list of Trade
        List of trades from baseline strategy
    min_duration_days : int
        Minimum duration for true trend (default 30)
    min_pnl_pct : float
        Minimum profit % for true trend (default 10%)

    Returns
    -------
    list of (Trade, bool)
        Each trade with its TRUE_TREND label
    """
    labeled = []
    for trade in trades:
        is_true_trend = (
            trade.duration_days >= min_duration_days and
            trade.net_pnl_pct >= min_pnl_pct
        )
        labeled.append((trade, is_true_trend))
    return labeled


def compute_trade_capture(
    baseline_trades: List[Trade],
    system_trades: List[Trade],
    match_window_days: int = 5,
    min_duration_days: int = 30,
    min_pnl_pct: float = 10.0
) -> Dict:
    """
    Compute true trend capture metrics.

    Maps each system trade to baseline trades to assess:
    - Recall: % of TRUE_TREND baseline trades captured by system
    - Precision: % of system trades that map to TRUE_TREND

    A system trade "captures" a baseline trade if entry times are within ±A days.

    Parameters
    ----------
    baseline_trades : list of Trade
        Baseline strategy trades
    system_trades : list of Trade
        Target system's trades
    match_window_days : int
        Window for matching entries (±A days)
    min_duration_days : int
        For labeling true trends
    min_pnl_pct : float
        For labeling true trends

    Returns
    -------
    dict
        recall, precision, matched_true_trends, total_true_trends, etc.
    """
    # Label baseline trades
    labeled_baseline = label_true_trends(
        baseline_trades, min_duration_days, min_pnl_pct
    )

    true_trends = [(t, label) for t, label in labeled_baseline if label]
    total_true_trends = len(true_trends)

    if total_true_trends == 0:
        return {
            'recall': 0.0,
            'precision': 0.0,
            'matched_true_trends': 0,
            'total_true_trends': 0,
            'system_trades_on_true_trend': 0,
            'total_system_trades': len(system_trades)
        }

    # Match system trades to baseline trades
    matched_true_trends = 0
    system_trades_on_true_trend = 0
    window = timedelta(days=match_window_days)

    for sys_trade in system_trades:
        sys_entry = sys_trade.entry_time

        # Find matching baseline trade
        matched = False
        for base_trade, is_true_trend in labeled_baseline:
            entry_diff = abs(sys_entry - base_trade.entry_time)
            if entry_diff <= window:
                if is_true_trend:
                    matched = True
                    break

        if matched:
            system_trades_on_true_trend += 1

    # For recall: how many true trends were captured
    for base_trade, is_true_trend in true_trends:
        base_entry = base_trade.entry_time

        captured = False
        for sys_trade in system_trades:
            entry_diff = abs(sys_trade.entry_time - base_entry)
            if entry_diff <= window:
                captured = True
                break

        if captured:
            matched_true_trends += 1

    recall = matched_true_trends / total_true_trends if total_true_trends > 0 else 0.0
    precision = system_trades_on_true_trend / len(system_trades) if system_trades else 0.0

    return {
        'recall': recall,
        'precision': precision,
        'matched_true_trends': matched_true_trends,
        'total_true_trends': total_true_trends,
        'system_trades_on_true_trend': system_trades_on_true_trend,
        'total_system_trades': len(system_trades)
    }


def compare_systems(
    results: Dict[str, BacktestResult],
    chop_max_duration: int = 10,
    min_duration_days: int = 30,
    min_pnl_pct: float = 10.0,
    match_window_days: int = 5
) -> pd.DataFrame:
    """
    Compare multiple strategy systems.

    Parameters
    ----------
    results : dict
        {system_name: BacktestResult}
    chop_max_duration : int
        For chop ratio calculation
    min_duration_days : int
        For true trend labeling
    min_pnl_pct : float
        For true trend labeling
    match_window_days : int
        For trade capture matching

    Returns
    -------
    pd.DataFrame
        Comparison table with all metrics
    """
    rows = []

    # Compute baseline metrics first (needed for capture analysis)
    baseline_result = results.get('baseline')
    baseline_trades = baseline_result.trades if baseline_result else []

    for name, result in results.items():
        metrics = compute_metrics(result, chop_max_duration)
        row = metrics.to_dict()
        row['System'] = name

        # Compute capture metrics vs baseline
        if name != 'baseline' and baseline_trades:
            capture = compute_trade_capture(
                baseline_trades,
                result.trades,
                match_window_days,
                min_duration_days,
                min_pnl_pct
            )
            row['True Trend Recall (%)'] = round(capture['recall'] * 100, 1)
            row['True Trend Precision (%)'] = round(capture['precision'] * 100, 1)
        else:
            # For baseline, compute how many of its trades are true trends
            labeled = label_true_trends(baseline_trades, min_duration_days, min_pnl_pct)
            true_trend_count = sum(1 for _, is_tt in labeled if is_tt)
            row['True Trend Recall (%)'] = 100.0  # Baseline captures all its own
            row['True Trend Precision (%)'] = round(
                true_trend_count / len(baseline_trades) * 100, 1
            ) if baseline_trades else 0.0

        rows.append(row)

    df = pd.DataFrame(rows)
    # Reorder columns
    cols = ['System'] + [c for c in df.columns if c != 'System']
    return df[cols]


def select_winner(
    comparison_df: pd.DataFrame,
    max_drawdown_cap: float = 40.0,
    min_trades: int = 10
) -> str:
    """
    Select the best system based on tradeoffs.

    Selection criteria:
    1. Must have max_drawdown <= cap
    2. Must have at least min_trades
    3. Among valid systems, maximize return while minimizing chop ratio

    Parameters
    ----------
    comparison_df : pd.DataFrame
        Output from compare_systems()
    max_drawdown_cap : float
        Maximum allowed drawdown
    min_trades : int
        Minimum required trades

    Returns
    -------
    str
        Name of winning system
    """
    valid = comparison_df[
        (comparison_df['Max Drawdown (%)'] <= max_drawdown_cap) &
        (comparison_df['Num Trades'] >= min_trades)
    ].copy()

    if len(valid) == 0:
        # Relax constraints if no valid systems
        valid = comparison_df.copy()

    # Score: return / (1 + chop_ratio) - prefer high return with low chop
    valid['score'] = valid['Total Return (%)'] / (1 + valid['Chop Ratio (%)'] / 100)

    winner = valid.loc[valid['score'].idxmax(), 'System']
    return winner


# =============================================================================
# Walk-Forward Evaluation
# =============================================================================

def walk_forward_evaluation(
    df: pd.DataFrame,
    strategy_runner,
    backtester_func,
    train_ratio: float = 0.7,
    param_grid: dict = None
) -> Dict:
    """
    Perform walk-forward validation.

    Steps:
    1. Split data into train/test by date
    2. Run parameter sweep on train set
    3. Select top configuration
    4. Evaluate on test set

    Parameters
    ----------
    df : pd.DataFrame
        Full OHLC data
    strategy_runner : StrategyRunner
        Strategy runner instance
    backtester_func : callable
        Function to run backtest
    train_ratio : float
        Fraction of data for training
    param_grid : dict
        Parameter ranges for sweep:
        {
            'quantile_range': [0.15, 0.20, 0.25],
            'contraction_lookback_range': [10, 20, 30],
            'donchian_range': [10, 20, 30]
        }

    Returns
    -------
    dict
        train_results, test_results, best_params
    """
    if param_grid is None:
        param_grid = {
            'quantile_range': [0.20],
            'contraction_lookback_range': [20],
            'donchian_range': [20]
        }

    # Split data
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    print(f"Walk-forward split: Train {len(train_df)} bars, Test {len(test_df)} bars")
    print(f"Train period: {train_df.index[0]} to {train_df.index[-1]}")
    print(f"Test period: {test_df.index[0]} to {test_df.index[-1]}")

    # Parameter sweep on train set
    sweep_results = []

    for q in param_grid.get('quantile_range', [0.20]):
        for m in param_grid.get('contraction_lookback_range', [20]):
            for n in param_grid.get('donchian_range', [20]):
                # Update strategy runner params
                strategy_runner.contraction_params['quantile_threshold'] = q
                strategy_runner.contraction_params['lookback_bars'] = m
                strategy_runner.breakout_params['donchian_period'] = n

                # Run all strategies on train
                signals = strategy_runner.run_all(train_df)

                for sys_name, (entry, exit) in signals.items():
                    result = backtester_func(train_df, entry, exit)
                    metrics = compute_metrics(result)

                    sweep_results.append({
                        'system': sys_name,
                        'q': q,
                        'm': m,
                        'n': n,
                        'return': metrics.total_return_pct,
                        'drawdown': metrics.max_drawdown_pct,
                        'trades': metrics.num_trades,
                        'chop_ratio': metrics.chop_ratio,
                        'sharpe': metrics.sharpe_ratio
                    })

    sweep_df = pd.DataFrame(sweep_results)

    # Select best config per system (maximize Sharpe with constraints)
    best_params = {}
    for sys_name in ['baseline', 'filtered', 'hybrid']:
        sys_df = sweep_df[sweep_df['system'] == sys_name]
        if len(sys_df) == 0:
            continue

        # Filter: at least 5 trades, drawdown < 50%
        valid = sys_df[(sys_df['trades'] >= 5) & (sys_df['drawdown'] < 50)]
        if len(valid) == 0:
            valid = sys_df

        best_idx = valid['sharpe'].idxmax()
        best = valid.loc[best_idx]
        best_params[sys_name] = {
            'q': best['q'],
            'm': int(best['m']),
            'n': int(best['n']),
            'train_sharpe': best['sharpe'],
            'train_return': best['return']
        }

    # Evaluate best configs on test set
    test_results = {}
    for sys_name, params in best_params.items():
        strategy_runner.contraction_params['quantile_threshold'] = params['q']
        strategy_runner.contraction_params['lookback_bars'] = params['m']
        strategy_runner.breakout_params['donchian_period'] = params['n']

        if sys_name == 'baseline':
            entry, exit = strategy_runner.run_baseline(test_df)
        elif sys_name == 'filtered':
            entry, exit = strategy_runner.run_filtered(test_df)
        else:
            entry, exit = strategy_runner.run_hybrid(test_df)

        result = backtester_func(test_df, entry, exit)
        metrics = compute_metrics(result)
        test_results[sys_name] = {
            'result': result,
            'metrics': metrics,
            'params': params
        }

    return {
        'sweep_df': sweep_df,
        'best_params': best_params,
        'test_results': test_results,
        'train_df': train_df,
        'test_df': test_df
    }
