# Moneyline Backtesting Framework

A Python backtesting framework for evaluating the Moneyline trend-following system with contraction/breakout overlays.

## Overview

This framework evaluates 3 trading systems:

1. **Baseline (System 1)**: Pure Moneyline crossover strategy
   - Entry: `crossover(fastHMA, slowMA)`
   - Exit: `crossunder(fastHMA, adjustedSlowMA)`

2. **Filtered Crossover (System 2)**: Baseline + contraction filter
   - Entry: Baseline entry AND recent contraction (volatility squeeze)
   - Exit: Same as baseline

3. **Hybrid (System 3)**: Trend filter + breakout entry + contraction
   - Entry: Trend bullish AND breakout AND recent contraction
   - Exit: Same as baseline

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Run

```bash
python run_backtest.py --config config.yaml
```

### Command Line Options

```bash
python run_backtest.py --data data/eth-usd.csv --strategy all
python run_backtest.py --data data/eth-usd.csv --btc data/eth-btc.csv --dual
python run_backtest.py --config config.yaml --pine  # Generate Pine Script
python run_backtest.py --config config.yaml --walk-forward  # Walk-forward evaluation
```

### Options

- `--config, -c`: Path to YAML configuration file (default: config.yaml)
- `--data, -d`: Path to OHLC CSV (overrides config)
- `--btc`: Path to BTC OHLC CSV for dual-series mode
- `--strategy, -s`: Strategy to run (baseline, filtered, hybrid, all)
- `--dual`: Enable dual-series mode
- `--no-qa`: Skip QA checks
- `--no-report`: Skip report generation
- `--walk-forward`: Run walk-forward evaluation
- `--pine`: Generate TradingView Pine Script
- `--output-dir, -o`: Output directory for reports

## Configuration

Edit `config.yaml` to customize parameters:

```yaml
moneyline:
  conversion_period: 9
  base_period: 26
  fast_hma_period: 5
  slow_ema_period: 13
  exit_percent: 2.0

contraction:
  bb_period: 20
  quantile_window: 252
  quantile_threshold: 0.20
  lookback_bars: 20

breakout:
  donchian_period: 20

backtest:
  initial_capital: 10000.0
  fee_percent: 0.1
  slippage_bps: 5
```

## Data Format

CSV files should have columns:
- `time` or `timestamp` or `date`: Datetime or Unix timestamp
- `open`, `high`, `low`, `close`: OHLC prices
- `volume` (optional)

Example:
```csv
time,open,high,low,close,volume
2023-01-01,100,110,95,105,1000
2023-01-02,105,115,100,110,1200
```

## Project Structure

```
moneyline-upgrade/
├── config.yaml          # Configuration file
├── run_backtest.py      # CLI entry point
├── requirements.txt     # Python dependencies
├── src/
│   ├── data_loader.py   # Data ingestion
│   ├── indicators.py    # Indicator calculations
│   ├── backtester.py    # Backtest engine
│   ├── strategies.py    # Strategy implementations
│   ├── evaluator.py     # Metrics and analysis
│   ├── reporter.py      # Reports and visualization
│   └── qa.py            # QA and lookahead checks
├── tests/               # Unit tests
├── data/                # Place CSV files here
└── reports/             # Generated reports
```

## Key Features

- **No Lookahead Bias**: All indicators properly shift data to avoid using future information
- **Next-Bar Fills**: Signals detected at close, filled at next bar's open
- **Dual-Series Mode**: Optional BTC confirmation for entry/exit signals
- **Comprehensive Metrics**: Return, CAGR, drawdown, Sharpe, win rate, chop ratio
- **True Trend Capture**: Analysis of which trades are "true trends" vs "chop"
- **Walk-Forward Validation**: Optional parameter optimization with out-of-sample testing
- **Pine Script Generator**: Export winning strategy to TradingView

## Running Tests

```bash
pytest tests/ -v
```

## Indicator Logic

### Moneyline (from Pine Script)
```
tenkan = (highest(high, conv) + lowest(low, conv)) / 2
kijun = (highest(high, base) + lowest(low, base)) / 2
fastHMA = HMA(tenkan, fastHMAPeriod)
slowMA = EMA(kijun, slowEMAPeriod)
adjustedSlowMA = slowMA * (1 - exitPercent/100)
long = crossover(fastHMA, slowMA)
exit = crossunder(fastHMA, adjustedSlowMA)
```

### Contraction (BBW)
```
BBW = (upper - lower) / basis  # Bollinger Band Width
contracted = BBW < quantile(BBW[prior 252 bars], 0.20)
contracted_recent = any(contracted in last M bars)
```

### Breakout (Donchian)
```
donch_high = max(high[t-N:t-1])  # Prior N bars only
breakout_long = close > donch_high
```

## License

MIT
