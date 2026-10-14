# Moneyline trend research and shadow trading

The active implementation tests one fixed daily strategy: the exact replicated
ATR(10) × 2 reset-on-flip indicator, long while green and cash while red, with
signals from completed sessions and executions at the following open.

**Current status: research and offline shadow execution. No deployment-qualified
stock basket and no live order placement.** Incomplete prices, dividends, security
identities or terminal proceeds cannot silently produce an approved whitelist.

## Start here

- [HANDOFF.md](HANDOFF.md): current state and historical research context.
- [Research workflow](docs/RESEARCH_SELECTION.md): causal formation, continuous
  portfolio comparisons, frozen settings and guarded holdout.
- [Data acquisition](docs/DATA_SOURCES.md): exact input contracts, public-data
  limitations and licensed-data import.
- [Shadow trading](docs/TRADING_SHADOW.md): signal, plan, journal, replay,
  reconciliation and enforcement commands.
- [Implementation results](docs/IMPLEMENTATION_RESULTS.md): checks and remaining
  requirements from this implementation.
- [Crypto signal comparison](docs/CRYPTO_EXPERIMENT.md): six fixed entry, exit and
  Donchian candidates, causal historical liquidity baskets and matched benchmarks.
- [Crypto results](docs/CRYPTO_RESULTS.md): actual comparisons and the hypotheses
  worth advancing to prospective testing.

## Install and verify

```bash
python3 -m pip install -r requirements.txt -r requirements-research.txt
python3 -m pytest tests -q
python3 -m trading.cli demo --output-dir .private_trading/shadow_demo
```

The demo uses invented stocks, prices, budget and account identifiers. Its JSON
plans and SQLite journal stay in the gitignored private directory.

## Run a stock-selection experiment

Normalize a dataset into the contract in `research/data_contract.py`. Then:

```bash
python3 -m research.run development \
  --dataset private/price_data/your_bundle \
  --mode validated \
  --config config/research_experiment.json \
  --output private/research_runs/development
```

Use `--mode exploratory` for incomplete public data. Missing economic valuations
produce `UNIDENTIFIED` comparisons; missing dividend accounting suppresses
after-tax figures. Exploratory results never authorize deployment.

The experiment compares top 5/10/20/30/40, skill above 10 and all eligible stocks,
using five-year formation and subsequent three-year tests. It reports SPY held
continuously, the same selected stocks held continuously between selections,
and the indicator on all eligible stocks. Empty selections remain in cash.

Each capital slot keeps its own cash while red. Selection changes, dividend
reinvestment, costs, initial-green entry and taxes are declared in the config;
the language model does not decide them.

Freeze an explicit candidate and implementation before the fixed 2023–2025
holdout. A candidate, complete calendar and matching provenance are required;
the local one-attempt guard records success or failure without shortening the
window. See the research workflow for the commands and guard limitations.

Concurrent upstream results now overlap the historical reserved periods. The
corrected runner has not evaluated them, but that period is not globally
untouched. Future deployment evidence also needs a separately frozen prospective
evaluation; see the implementation results for this disclosure.

## Code map

| Path | Role |
| --- | --- |
| `analysis_2026/moneyline_ref.py` | Exact existing indicator reference |
| `research/` | Data contract, calendars, causal selection, continuous portfolio/tax engine and experiment CLI |
| `trading/` | Deterministic offline signals, order plans, SQLite reconciliation, typed broker adapter and enforcement |
| `screener/` | Hardened CSV/Robinhood ingestion and freshness checks; legacy research entry points route to corrected code |
| `scripts/acquire_research_data.py` | Pinned development-only import and normalized licensed-input audit |
| `config/` | Declared experiment and empty-whitelist shadow defaults |
| `crypto_research/` | Research-only crypto signal variants, fractional cash-slot portfolios, passive SPY benchmark and frozen comparison CLI |

## Archived legacy documentation

The material below describes an obsolete indicator and old command line. It is
retained as history; use the workflows above for current research.

> **⚠️ Read [HANDOFF.md](HANDOFF.md) first.** The material below documents the project's
> original model of the "Moneyline" indicator (an Ichimoku HMA/EMA crossover), which
> turned out to be **wrong**. The real indicator is an ATR trailing stop (Wilder ATR(10)
> x 2.0 around hl2, reset-on-flip), replicated exactly in
> `analysis_2026/moneyline_ref.py`. Results from `src/`, `run_backtest.py`,
> `scanner.py` and `reports/` are superseded. Current results: `analysis_2026/`.
> Automated-trading design: [AGENTIC_TRADING_PLAN.md](AGENTIC_TRADING_PLAN.md).

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
