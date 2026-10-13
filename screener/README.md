# Stock screener and selection study

Uses the exact replicated indicator (`analysis_2026/moneyline_ref.py`: Wilder
ATR(10) × 2.0 around hl2, reset-on-flip — 100% bar agreement with TradingView on
IWM) on daily OHLC for any list of stocks.

| file | what it does |
|---|---|
| `data.py` | Loaders: a folder of CSVs, a saved Robinhood `get_equity_historicals` result, or a yfinance download (`python -m screener.data --sp500`). |
| `scan.py` | Daily screener: state, flipped today, days since flip, % since flip, distance to line, ATR%, whitelist flag. |
| `selection.py` | Walk-forward test of stock-selection rules: does "the indicator worked on this stock before" predict that it works next? |

## Data must be split-adjusted but NOT dividend-adjusted

That is TradingView's default chart data. Dividend-adjusted prices miss flips: on
IWM a 0.34% dividend adjustment hid the 2025-12-17 red flip that TradingView shows.

- yfinance: `auto_adjust=False` (what `data.py` uses) → Open/High/Low/Close are
  split-adjusted; `Adj Close` is ignored.
- Robinhood MCP: `get_equity_historicals` with `adjustment_type='split'` (default).
- Only run on CLOSED bars (drop today's row during market hours).

## Where it can run

- **Claude Code session with the Robinhood connector**: Claude fetches daily bars
  (10 symbols per call), the raw result is saved to disk, then
  `python -m screener.scan --robinhood-json <file>`. The parser's field names
  (`begins_at`, `open_price`, …) still need checking against a real response.
- **Any machine or cloud environment that can reach Yahoo**:
  `python -m screener.data --sp500 --out data/universe` then
  `python -m screener.scan --csv-folder data/universe`.
  The default Claude cloud sandbox blocks Yahoo; allow it in the environment's
  network settings, or run locally.

`data/universe/` is gitignored: keep downloaded price data and scan outputs out of
this public repo.

## Selection study — what the harness shows

`python -m screener.selection --synthetic random_walk|regime` runs the test on
synthetic stocks to check the harness:

- **random_walk** (no real edge anywhere): the top 20 by past edge showed +28 CAGR
  points in the 5-year ranking window, then −5.7 in the next 3 years. That matches
  random picks (−5.5); the rank correlation between past and future is ≈0. Ranking
  past winners always produces an impressive list.
- **regime** (some stocks persistently trend-friendly): picks keep +16 (past edge) to
  +29 (trendiness, 20-day variance ratio) vs +1.6 for all stocks, in 100% of splits.
  Even then they keep only about a third of their in-sample edge.

The real-data run (`--csv-folder data/universe` on S&P 500 history) decides which
world real stocks are in. It has not been run yet, because no stock data is reachable
from the research sandbox.
