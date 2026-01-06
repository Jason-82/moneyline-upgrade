"""
Reporting and Visualization Module (Agent 7)
=============================================
Generates plots, HTML reports, and Pine Script output.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from .backtester import BacktestResult
from .evaluator import compute_metrics, compare_systems


def ensure_reports_dir(reports_dir: str) -> Path:
    """Create reports directory if it doesn't exist."""
    path = Path(reports_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def plot_equity_curve(
    result: BacktestResult,
    title: str,
    save_path: Optional[str] = None
) -> None:
    """
    Plot equity curve with drawdown.

    Parameters
    ----------
    result : BacktestResult
    title : str
    save_path : str, optional
        If provided, saves plot to this path
    """
    if not MATPLOTLIB_AVAILABLE:
        print("matplotlib not available, skipping plot")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                    gridspec_kw={'height_ratios': [3, 1]})

    equity = result.equity_curve

    # Equity curve
    ax1.plot(equity.index, equity.values, linewidth=1.5, color='blue')
    ax1.fill_between(equity.index, result.initial_capital, equity.values,
                     where=(equity.values >= result.initial_capital),
                     alpha=0.3, color='green')
    ax1.fill_between(equity.index, result.initial_capital, equity.values,
                     where=(equity.values < result.initial_capital),
                     alpha=0.3, color='red')
    ax1.axhline(y=result.initial_capital, color='gray', linestyle='--', alpha=0.5)
    ax1.set_ylabel('Equity')
    ax1.set_title(title)
    ax1.legend(['Equity', 'Initial Capital'], loc='upper left')

    # Drawdown
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    ax2.fill_between(drawdown.index, 0, drawdown.values, color='red', alpha=0.5)
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    else:
        plt.show()


def plot_price_with_signals(
    df: pd.DataFrame,
    result: BacktestResult,
    title: str,
    save_path: Optional[str] = None,
    show_bands: bool = True
) -> None:
    """
    Plot price chart with entry/exit markers and indicator overlays.

    Parameters
    ----------
    df : pd.DataFrame
        OHLC data with indicators
    result : BacktestResult
    title : str
    save_path : str, optional
    show_bands : bool
        Whether to show trend shading and contraction highlighting
    """
    if not MATPLOTLIB_AVAILABLE:
        print("matplotlib not available, skipping plot")
        return

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True,
                              gridspec_kw={'height_ratios': [4, 1, 1]})
    ax1, ax2, ax3 = axes

    # Price and MAs
    ax1.plot(df.index, df['close'], label='Close', color='black', linewidth=1)

    if 'fast_hma' in df.columns:
        ax1.plot(df.index, df['fast_hma'], label='Fast HMA', color='blue',
                 linewidth=1, alpha=0.8)
    if 'slow_ma' in df.columns:
        ax1.plot(df.index, df['slow_ma'], label='Slow MA', color='orange',
                 linewidth=1, alpha=0.8)

    # Trend shading
    if show_bands and 'trend_green' in df.columns:
        trend = df['trend_green'].fillna(False)
        ax1.fill_between(df.index, df['close'].min() * 0.9, df['close'].max() * 1.1,
                        where=trend, alpha=0.1, color='green', label='Bullish')
        ax1.fill_between(df.index, df['close'].min() * 0.9, df['close'].max() * 1.1,
                        where=~trend, alpha=0.1, color='red', label='Bearish')

    # Entry/Exit markers
    for trade in result.trades:
        ax1.scatter(trade.entry_time, trade.entry_price, marker='^',
                   color='green', s=100, zorder=5)
        ax1.scatter(trade.exit_time, trade.exit_price, marker='v',
                   color='red', s=100, zorder=5)

    ax1.set_ylabel('Price')
    ax1.set_title(title)
    ax1.legend(loc='upper left', fontsize=8)

    # BBW with contraction threshold
    if 'bbw' in df.columns:
        ax2.plot(df.index, df['bbw'], label='BBW', color='purple', linewidth=1)
        if 'bbw_threshold' in df.columns:
            ax2.plot(df.index, df['bbw_threshold'], label='Threshold (20th pct)',
                    color='gray', linestyle='--', linewidth=1)
        if 'contracted' in df.columns:
            contracted = df['contracted'].fillna(False)
            ax2.fill_between(df.index, 0, df['bbw'].max(),
                            where=contracted, alpha=0.3, color='yellow',
                            label='Contracted')
        ax2.set_ylabel('BBW')
        ax2.legend(loc='upper right', fontsize=8)

    # Donchian channel
    if 'donch_high' in df.columns:
        ax3.plot(df.index, df['close'], label='Close', color='black', linewidth=0.5)
        ax3.plot(df.index, df['donch_high'], label='Donchian High',
                color='green', linestyle='--', linewidth=1)
        if 'breakout_long' in df.columns:
            breakout = df['breakout_long'].fillna(False)
            breakout_points = df.loc[breakout, 'close']
            ax3.scatter(breakout_points.index, breakout_points.values,
                       marker='D', color='blue', s=20, alpha=0.5, label='Breakout')
        ax3.set_ylabel('Donchian')
        ax3.legend(loc='upper right', fontsize=8)

    ax3.set_xlabel('Date')
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    else:
        plt.show()


def save_trades_csv(
    result: BacktestResult,
    save_path: str
) -> None:
    """Save trades to CSV file."""
    trades_df = result.trades_df()
    if len(trades_df) > 0:
        trades_df.to_csv(save_path, index=False)


def generate_html_report(
    comparison_df: pd.DataFrame,
    results: Dict[str, BacktestResult],
    asset_name: str,
    reports_dir: str,
    config: dict = None
) -> str:
    """
    Generate HTML summary report.

    Parameters
    ----------
    comparison_df : pd.DataFrame
        System comparison table
    results : dict
        {system_name: BacktestResult}
    asset_name : str
        Asset identifier (e.g., "ETH-USD")
    reports_dir : str
        Output directory
    config : dict
        Configuration used for the run

    Returns
    -------
    str
        Path to generated HTML file
    """
    reports_path = ensure_reports_dir(reports_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = reports_path / f"report_{asset_name}_{timestamp}.html"

    # Build HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report: {asset_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metric-good {{ color: green; font-weight: bold; }}
        .metric-bad {{ color: red; font-weight: bold; }}
        .image-container {{ margin: 20px 0; }}
        img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
        pre {{ background: #f5f5f5; padding: 15px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>Backtest Report: {asset_name}</h1>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

    <h2>System Comparison</h2>
    {comparison_df.to_html(index=False, classes='comparison-table')}

    <h2>Charts</h2>
"""

    # Add image references
    for sys_name in results.keys():
        html += f"""
    <div class="image-container">
        <h3>{sys_name.title()} Strategy</h3>
        <img src="{sys_name}_equity.png" alt="{sys_name} equity curve">
        <img src="{sys_name}_signals.png" alt="{sys_name} signals">
    </div>
"""

    # Add configuration
    if config:
        html += f"""
    <h2>Configuration</h2>
    <pre>{json.dumps(config, indent=2, default=str)}</pre>
"""

    html += """
</body>
</html>
"""

    with open(html_path, 'w') as f:
        f.write(html)

    return str(html_path)


def generate_full_report(
    df: pd.DataFrame,
    results: Dict[str, BacktestResult],
    asset_name: str,
    reports_dir: str = "reports",
    config: dict = None
) -> dict:
    """
    Generate complete report with all outputs.

    Parameters
    ----------
    df : pd.DataFrame
        OHLC data with indicators
    results : dict
        {system_name: BacktestResult}
    asset_name : str
    reports_dir : str
    config : dict

    Returns
    -------
    dict
        Paths to all generated files
    """
    reports_path = ensure_reports_dir(reports_dir)
    output_files = {}

    # Compare systems
    comparison_df = compare_systems(results)
    comparison_csv = reports_path / f"{asset_name}_comparison.csv"
    comparison_df.to_csv(comparison_csv, index=False)
    output_files['comparison_csv'] = str(comparison_csv)

    # Generate plots and trades CSV for each system
    for sys_name, result in results.items():
        # Equity curve
        equity_path = reports_path / f"{sys_name}_equity.png"
        plot_equity_curve(
            result,
            f"{asset_name} - {sys_name.title()} Equity Curve",
            str(equity_path)
        )
        output_files[f'{sys_name}_equity'] = str(equity_path)

        # Price with signals
        signals_path = reports_path / f"{sys_name}_signals.png"
        plot_price_with_signals(
            df, result,
            f"{asset_name} - {sys_name.title()} Signals",
            str(signals_path)
        )
        output_files[f'{sys_name}_signals'] = str(signals_path)

        # Trades CSV
        trades_path = reports_path / f"{sys_name}_trades.csv"
        save_trades_csv(result, str(trades_path))
        output_files[f'{sys_name}_trades'] = str(trades_path)

    # HTML report
    html_path = generate_html_report(
        comparison_df, results, asset_name, reports_dir, config
    )
    output_files['html_report'] = html_path

    print(f"Report generated: {html_path}")
    return output_files


# =============================================================================
# Pine Script Generator
# =============================================================================

def generate_pine_script(
    params: dict,
    include_dual_series: bool = False
) -> str:
    """
    Generate TradingView Pine Script v6 indicator.

    Parameters
    ----------
    params : dict
        Final chosen parameters:
        - conv_period, base_period, fast_hma_period, slow_ema_period, exit_percent
        - bb_period, bb_std, quantile_window, quantile_threshold
        - contraction_lookback, donchian_period
    include_dual_series : bool
        Whether to include coinBTC confirmation logic

    Returns
    -------
    str
        Pine Script v6 code
    """
    conv = params.get('conv_period', 9)
    base = params.get('base_period', 26)
    fast_hma = params.get('fast_hma_period', 5)
    slow_ema = params.get('slow_ema_period', 13)
    exit_pct = params.get('exit_percent', 2.0)

    bb_period = params.get('bb_period', 20)
    bb_std = params.get('bb_std', 2.0)
    q_window = params.get('quantile_window', 252)
    q_thresh = params.get('quantile_threshold', 0.20)

    m = params.get('contraction_lookback', 20)
    n = params.get('donchian_period', 20)

    script = f'''
//@version=6
indicator("Moneyline + Contraction/Breakout Overlay", overlay=true)

// =============================================================================
// INPUTS
// =============================================================================
// Moneyline parameters
convPeriod = input.int({conv}, "Conversion Period", minval=1)
basePeriod = input.int({base}, "Base Period", minval=1)
fastHMAPeriod = input.int({fast_hma}, "Fast HMA Period", minval=1)
slowEMAPeriod = input.int({slow_ema}, "Slow EMA Period", minval=1)
exitPercent = input.float({exit_pct}, "Exit Percent", minval=0, step=0.1)

// Contraction parameters
bbPeriod = input.int({bb_period}, "BB Period", minval=1)
bbStd = input.float({bb_std}, "BB Std Dev", minval=0.1, step=0.1)
quantileWindow = input.int({q_window}, "Quantile Window", minval=50)
quantileThresh = input.float({q_thresh}, "Quantile Threshold", minval=0.01, maxval=0.99, step=0.01)
contractionLookback = input.int({m}, "Contraction Lookback (M)", minval=1)

// Breakout parameters
donchianPeriod = input.int({n}, "Donchian Period (N)", minval=1)

// Display options
showTrendShading = input.bool(true, "Show Trend Shading")
showContraction = input.bool(true, "Show Contraction Markers")
showBreakout = input.bool(true, "Show Breakout Markers")
showBaselineSignals = input.bool(true, "Show Baseline Signals")
showFilteredSignals = input.bool(true, "Show Filtered Signals")
showHybridSignals = input.bool(true, "Show Hybrid Signals")

// =============================================================================
// FUNCTIONS
// =============================================================================
// Hull Moving Average
hma(src, length) =>
    wma(2 * wma(src, length / 2) - wma(src, length), math.round(math.sqrt(length)))

// Rolling percentile approximation (simple approach using sorting)
// Note: Pine doesn't have built-in percentile, so we approximate
rollingPercentile(src, length, pct) =>
    var float result = na
    if bar_index >= length
        sum = 0.0
        count = 0
        for i = 1 to length
            val = src[i]
            if not na(val)
                belowCount = 0
                for j = 1 to length
                    if not na(src[j]) and src[j] < val
                        belowCount += 1
                if belowCount <= int(length * pct)
                    if na(result) or val < result
                        result := val
        result
    else
        na

// =============================================================================
// MONEYLINE CALCULATION
// =============================================================================
// Tenkan-sen (conversion line)
tenkan = (ta.highest(high, convPeriod) + ta.lowest(low, convPeriod)) / 2

// Kijun-sen (base line)
kijun = (ta.highest(high, basePeriod) + ta.lowest(low, basePeriod)) / 2

// Fast HMA on tenkan
fastHMA = hma(tenkan, fastHMAPeriod)

// Slow EMA on kijun
slowMA = ta.ema(kijun, slowEMAPeriod)

// Adjusted slow MA for exits
adjustedSlowMA = slowMA * (1 - exitPercent / 100)

// Crossover signals
longCross = ta.crossover(fastHMA, slowMA)
exitCross = ta.crossunder(fastHMA, adjustedSlowMA)

// Trend direction
trendGreen = fastHMA > slowMA

// =============================================================================
// CONTRACTION CALCULATION (BBW)
// =============================================================================
basis = ta.sma(close, bbPeriod)
dev = bbStd * ta.stdev(close, bbPeriod)
bbw = (2 * dev) / basis

// Use simple threshold based on recent values
// (Full percentile would need array sorting which is expensive)
bbwThreshold = ta.percentile_linear_interpolation(bbw[1], quantileWindow, quantileThresh * 100)
contracted = bbw < bbwThreshold

// Contracted recent: any contraction in last M bars
contractedRecent = ta.barssince(contracted) <= contractionLookback

// =============================================================================
// BREAKOUT CALCULATION (Donchian)
// =============================================================================
donchHigh = ta.highest(high[1], donchianPeriod)
breakoutLong = close > donchHigh

// =============================================================================
// STRATEGY SIGNALS
// =============================================================================
// System 1: Baseline
baselineEntry = longCross
baselineExit = exitCross

// System 2: Filtered (baseline + contraction)
filteredEntry = longCross and contractedRecent

// System 3: Hybrid (trend + breakout + contraction)
hybridEntry = trendGreen and breakoutLong and contractedRecent

// =============================================================================
// PLOTTING
// =============================================================================
// MA lines
plot(fastHMA, "Fast HMA", color=color.blue, linewidth=2)
plot(slowMA, "Slow MA", color=color.orange, linewidth=2)
plot(adjustedSlowMA, "Adjusted Slow MA", color=color.red, linewidth=1, style=plot.style_linebr)

// Trend shading
bgcolor(showTrendShading ? (trendGreen ? color.new(color.green, 90) : color.new(color.red, 90)) : na)

// Contraction markers
plotshape(showContraction and contracted, "Contracted", style=shape.circle,
          location=location.bottom, color=color.new(color.yellow, 50), size=size.tiny)

// Breakout markers
plotshape(showBreakout and breakoutLong, "Breakout", style=shape.diamond,
          location=location.abovebar, color=color.new(color.blue, 30), size=size.tiny)

// Signal markers
// Baseline entry (green triangle up)
plotshape(showBaselineSignals and baselineEntry, "Baseline Entry",
          style=shape.triangleup, location=location.belowbar,
          color=color.new(color.green, 0), size=size.small)

// Filtered entry (lime circle)
plotshape(showFilteredSignals and filteredEntry and not baselineEntry, "Filtered Entry",
          style=shape.circle, location=location.belowbar,
          color=color.new(color.lime, 0), size=size.small)

// Hybrid entry (blue arrow up)
plotshape(showHybridSignals and hybridEntry and not baselineEntry and not filteredEntry, "Hybrid Entry",
          style=shape.arrowup, location=location.belowbar,
          color=color.new(color.aqua, 0), size=size.small)

// Exit signal (red X)
plotshape(baselineExit, "Exit", style=shape.xcross, location=location.abovebar,
          color=color.new(color.red, 0), size=size.small)

// =============================================================================
// ALERTS
// =============================================================================
alertcondition(baselineEntry, "Baseline Entry", "Moneyline baseline entry signal")
alertcondition(filteredEntry, "Filtered Entry", "Moneyline filtered entry signal")
alertcondition(hybridEntry, "Hybrid Entry", "Moneyline hybrid entry signal")
alertcondition(baselineExit, "Exit Signal", "Moneyline exit signal")
'''

    # Add dual-series logic if requested
    if include_dual_series:
        script += '''
// =============================================================================
// DUAL-SERIES CONFIRMATION (Optional)
// =============================================================================
// To use: change symbol to BTC pair and enable this section
useDualSeries = input.bool(false, "Use Dual-Series Confirmation")
btcSymbol = input.symbol("BINANCE:BTCUSDT", "BTC Symbol")

// Request BTC data
[btcHigh, btcLow, btcClose] = request.security(btcSymbol, timeframe.period, [high, low, close])

// Calculate BTC moneyline
btcTenkan = (ta.highest(btcHigh, convPeriod) + ta.lowest(btcLow, convPeriod)) / 2
btcKijun = (ta.highest(btcHigh, basePeriod) + ta.lowest(btcLow, basePeriod)) / 2
btcFastHMA = hma(btcTenkan, fastHMAPeriod)
btcSlowMA = ta.ema(btcKijun, slowEMAPeriod)
btcLongCross = ta.crossover(btcFastHMA, btcSlowMA)
btcExitCross = ta.crossunder(btcFastHMA, btcSlowMA * (1 - exitPercent / 100))

// Combined signals (if dual series enabled)
confirmedEntry = useDualSeries ? (baselineEntry and btcLongCross) : baselineEntry
confirmedExit = useDualSeries ? (baselineExit or btcExitCross) : baselineExit
'''

    return script


def save_pine_script(
    params: dict,
    output_path: str,
    include_dual_series: bool = False
) -> None:
    """
    Save Pine Script to file.

    Parameters
    ----------
    params : dict
        Strategy parameters
    output_path : str
        Path to save the Pine script
    include_dual_series : bool
        Include dual-series logic
    """
    script = generate_pine_script(params, include_dual_series)
    with open(output_path, 'w') as f:
        f.write(script)
    print(f"Pine Script saved to: {output_path}")
