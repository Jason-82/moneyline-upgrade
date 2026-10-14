# Stock screener and selection study

Runs the exact replicated indicator (`analysis_2026/moneyline_ref.py`: Wilder ATR(10) ×
2.0 around hl2, reset-on-flip) on daily OHLC for any list of stocks.

The scanner was checked against TradingView: on IWM, every date from 2012 to 2025
(3,517 dates) gave the same state, flip date and days-in-state.

| file | what it does |
|---|---|
| `data.py` | Loaders: a folder of CSVs, a saved Robinhood `get_equity_historicals` result, or a yfinance download (`python -m screener.data --sp500`). Drops a still-forming bar. |
| `scan.py` | Daily screener, like Ivan on Tech's site: state, flipped today, days since flip, % since flip, distance to line, ATR%, whitelist flag; flags stale symbols. |
| `selection.py` | Walk-forward test of stock-selection rules: does "the indicator worked on this stock before" predict that it works next? |
| `../analysis_2026/gate.py` | Per-asset gate (after costs, next-session execution and tax; vs the asset's own buy & hold **and** vs SPY), with `placebo()` for false-pass rates. |

## Data must be split-adjusted, not dividend-adjusted

TradingView shows split-adjusted prices, not dividend-adjusted ones. Dividend-adjusted
prices miss flips: on IWM, a 0.34% dividend adjustment hid the 2025-12-17 red flip that
TradingView shows.

- yfinance: use `auto_adjust=False`, which is what `data.py` does.
- Robinhood MCP: `get_equity_historicals` with `interval='day'` and
  `adjustment_type='split'`.
- Scan closed bars only.

## Where it can run

- **Claude Code session with the Robinhood connector.** Claude fetches daily bars (10
  symbols per call) and the raw result is saved to disk. Then run
  `python -m screener.scan --robinhood-json <file>`. Responses are large (about 0.5M
  characters per 10 symbols × 300 bars). So use this for a whitelist with a local bar
  store and small daily top-ups, not for a 500-stock daily scan. Robinhood's
  server-side SuperTrend defaults to ×3, which agrees with this indicator only ~80% of
  the time; set ×2 and use it as a cross-check only. Its scanner tool has no SuperTrend
  filter.
- **Any machine or cloud environment that can reach Yahoo.** Run
  `python -m screener.data --sp500 --out data/universe`, then
  `python -m screener.scan --csv-folder data/universe`. The default Claude cloud sandbox
  blocks Yahoo, so either allow it in the environment's network settings or run locally.

`data/universe/` and `private/` are gitignored. Keep price data, scans and logs out of
this public repo.

## What the selection study measures

- Execution is next-open, with 0.03% cost per side.
- Formation and test windows don't overlap, and only data up to 2022-12-31 is used
  until the holdout run.
- The test metric is **drift-neutral timing skill**: (strategy log return − exposure ×
  buy-and-hold log return) per year. A raw "beat the stock's own buy & hold" measure
  rewards stocks that fell, so a no-skill universe can look persistent under it.
- The PRIMARY criterion, declared in advance, is formation-window skill. The other six
  are exploratory.
- p-values come from a permutation test (one shuffle of stock identities applied to
  every split) with a Holm correction.

Synthetic checks (`--synthetic random_walk|regime`):

- **random_walk** (no timing skill exists): picks with +21.5%/yr skill in formation
  earned −1.3%/yr in test, vs −2.1% for all stocks (p = 0.39, so correctly not
  significant). Under the earlier raw-edge metric, the top 20 showed +28 CAGR points
  in-sample and nothing out of sample. **Ranking past winners always produces an
  impressive list.**
- **regime** (some stocks are persistently trend-friendly): picks kept +16.8%/yr vs +5.3%
  (p < 0.01, Holm 0.02). Even so, the picks keep only about half of their in-sample
  skill.

### Survivorship

`python -m screener.data --sp500` downloads **today's** members, and yfinance has no
delisted tickers. A run on that folder is survivorship-biased. On zero-skill random
walks, keeping only the eventual survivors shifts results by several points and can make
some criteria look persistent or anti-persistent. **Treat current-member results as
illustrative.**

A trustworthy run needs point-in-time membership plus delisted price history. Sources
include Norgate, Sharadar (Nasdaq Data Link) and CRSP. Pass it as `--members`, a CSV
with columns symbol, start, end.

### Holdout (fixed before any real-data run; do not change)

- **Development** uses daily bars up to 2022-12-31 (`--until`, the default).
- **Freeze the rule before touching the holdout:** criterion, top_n, form/test
  lengths, min_trades, and the gate thresholds.
- **One final run** with `--until holdout`: formation 2018-2022, test 2023-2025. Report
  the result whatever it is. Do not re-tune and re-run.
- Then run a **forward shadow period** of 6-12 months: log the whitelist's would-be
  trades without placing orders.
- The test windows include 2000-02 and 2008 only if the data starts by 1993
  (`data.py` default). With 2010+ data, every test window is a bull market, so the
  results mostly measure what the signal costs in bull markets.

## How strict should the fit filter be? (`strictness.py`)

The per-stock gate asks one stock's own history to prove the edge alone, through eight
tests at once. With about 50–80 trades per stock that is hard even when an edge is real.
A basket spreads the bet, so the evidence can be judged on the basket instead. Some picks
can fail, as long as the basket beats SPY after tax.

How strict to be is then an empirical question with a direct test:

1. On each re-pick date, score every stock on its past 5 years.
2. Build baskets from strict to loose: top 5, 10, 20 or 40 stocks; top 25% or 50%; skill
   above 10, 5 or 0 %/yr; every stock.
3. Trade each basket through the next 3 years exactly as live (next open, costs, cash at
   T-bill when red, tax), and compare it with holding SPY.
4. Re-pick and repeat, chaining the money forward.

Reading the curve of out-of-sample result against strictness:

- **Rising toward strict:** fit persists, so stricter is better, until the basket gets too
  small and noisy.
- **Flat:** fit doesn't carry forward, so strictness is irrelevant. All that matters then is
  whether the signal on *any* stock beats SPY.
- **Falling:** past winners were luck, so stricter is worse.

### Pre-registered decision rule (fixed 2026-10-14, before any real-data run)

- **Data and settings:** development uses test windows up to 2022-12-31. Primary settings
  are criterion = skill, park = cash, and formation 5y → test 3y.
- **Qualifying level:** its chained after-tax CAGR is ≥ SPY's, or ≥ SPY − 2 pts with its
  worst window drawdown ≥ 15 pts shallower than SPY's. It must also beat SPY (same rule)
  in at least two-thirds of test windows.
- **Selection matters** only if the level also beats the all-stock basket with permutation
  p < 0.05. Otherwise strictness doesn't matter, and the all-stock basket is the candidate.
- **Choice:** the loosest qualifying level whose chained excess return is within 1 pt/yr of
  the best qualifying level, to keep diversification.
- **No qualifying level** means the verdict is that no basket built with this indicator beat
  SPY after tax, so don't run the stock strategy.
- **Holdout:** run the chosen level once on formation 2018–2022 → test 2023–2025 and report
  it as it comes out. 2026 year-to-date is a forward look only.
- **Exploratory only, never used to choose:** park = spy, criteria gate / edge / vol, and
  pre-tax figures.

## How many stocks to expect (hypothesis, not a target)

The whitelist size is an **output**, and it may be zero. Don't fix a number like "20+"
and fill it by rank.

- **Real stocks so far:** 0 of 7 pass `gate.py` (SPX, NDX, IWM, TSLA, COIN, HOOD, CRCL).
  They fail on eras, profit factor, whipsaw, and now the SPY hurdle (COIN passes vs its
  own buy & hold while losing money).
- **Noise passes the gate too:** about 2% of no-edge stocks get TRADE at ~7-8 years of
  history, and ~0.2-0.7% at 19-20 years. On ~500 names that is roughly 4-15 passes from
  noise alone. Always report `sum(placebo_trade_p)` next to the real pass count.
- **Rules for names found by a scan rather than a list fixed in advance:**
  - require ≥ 13 years of history
  - no PROBATION
  - promote only if the real pass count clearly exceeds the placebo count (e.g.
    R ≥ E + 2√E + 1)
- **Planning expectation:** roughly 0-10 names. Plausible types, which is a hypothesis:
  high-volatility names with multi-month trends and deep, slow drawdowns, such as
  crypto-linked equities and boom-bust growth stocks.

## Static list vs scan

- **Worst:** a static list of the 20 best historical backtests. That is pure in-sample
  selection.
- **Honest but small:** a list fixed **by mechanism before looking at results**, then
  gated.
- **Better, only if the walk-forward shows persistence:** a rule-based whitelist,
  re-picked on exactly the cadence the walk-forward tested. A different cadence, such as
  quarterly instead of every 3 years, is a different rule and must be tested first.
- **The scan itself costs nothing and decides nothing.** Scan broadly for information;
  trade only the whitelist.

## Until stock data is available

- **IBIT / BTC: hold and ignore flips.** BTC fails the gate even before tax.
- **BSOL / SOL (PROBATION, ≤10%):** if you follow the signal, read it on TradingView
  **COINBASE:SOLUSD**. That is the chart the backtests used. Read it after the daily
  candle closes (00:00 UTC = 8 pm EDT / 7 pm EST) and act in the next NYSE session.
  Weekend and holiday flips wait.
  - **Don't put the indicator on BSOL's own chart.** Its bars cover NYSE hours only and
    include staking accrual, so that signal was never tested.
  - Exiting at a loss and re-buying within 30 days is a wash sale.
- **Ivan on Tech's screener: use it for discovery only.** Keep a dated log of what it
  flags (date, ticker, flip, close). That log becomes a forward out-of-sample record.
  Gate any name before trading it.
- **Pre-register 30-50 candidates by mechanism** before seeing results. Then gate them
  from candle-mode TradingView exports (open/high/low/close columns).
