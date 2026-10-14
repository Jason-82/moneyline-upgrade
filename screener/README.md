# Stock screener and selection study

Runs the exact replicated indicator (`analysis_2026/moneyline_ref.py`: Wilder ATR(10) ×
2.0 around hl2, reset-on-flip) on daily OHLC for any list of stocks.

The scanner was checked against TradingView: on IWM, every date from 2012 to 2025
(3,517 dates) gave the same state, flip date and days-in-state.

| file | what it does |
|---|---|
| `data.py` | Loaders: CSV folder, saved Robinhood `get_equity_historicals` result, yfinance, qlib US binary data (`from_qlib`), a long-format parquet (`from_long_parquet`), point-in-time S&P 500 membership (`sp500_members`), and `quality_filter` for broken/spliced series. Drops a still-forming bar. |
| `rh_ingest.py` | Merges saved Robinhood historicals results (two calls per 10 symbols for 1999-today) into a per-symbol CSV store. |
| `strictness.py` | How strict should the fit filter be: baskets from strict to loose, traded walk-forward vs SPY after tax. |
| `scan.py` | Daily screener, like Ivan on Tech's site: state, flipped today, days since flip, % since flip, distance to line, ATR%, whitelist flag; flags stale symbols. |
| `selection.py` | Walk-forward test of stock-selection rules: does "the indicator worked on this stock before" predict that it works next? `--calibrate` tabulates past fit vs next-window fit. |
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
- **The default cloud sandbox, with no settings change** (found 2026-10-14). Both sources
  are third-party and unofficial, so check them before relying on them.
  - **Daily scan:** github.com/q100423gg-coder/us-stock-data publishes `prices.parquet`
    as a GitHub release, refreshed every evening. It holds split-adjusted daily OHLC for
    about 2,300 US stocks and ETFs (market cap ≥ $2B plus all S&P 500 members), rolling
    about 2 years. Load it with `data.from_long_parquet` (needs `pip install pyarrow`).
  - **Research history:** Microsoft qlib's US daily dataset
    (github.com/SunsetWolf/qlib_dataset release `v0/qlib_data_us_1d_v3.zip`, 615 MB) covers
    2000 to 2024-04-25 for about 13,000 symbols. Load it with `data.from_qlib`. It is
    survivorship-biased, total return only until 2021-09-16, and has a few wrong-company
    tickers (DD = Dow Chemical, JCI = Tyco). Research only.
  - **Robinhood connector:** large `get_equity_historicals` results are saved to a file
    instead of filling the conversation, so `rh_ingest.py` can build a 1999-today store at
    two calls per 10 symbols. The cap is 5,000 bars per symbol per call. History starts
    1999-09 and has no delisted names.

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

### Development result (2005–2022, six 3-year test windows)

Data: qlib US daily (`data.from_qlib`) for every stock in the S&P 500 at any time since
1999, with point-in-time membership (`data.sp500_members`). The quality filter dropped 36
broken or recycled-ticker series. Run with `--prices qlib`: qlib prices are total return
only until 2021-09-16 and price-only afterwards, which an audit found.

**Survivorship:** only 60–66% of members are usable at the 2005 and 2008 test starts,
because Lehman, WaMu, Fannie, Merrill and the other failures are missing. That flatters
every basket against SPY, the concentrated ones most (roughly 0.3–1 pt/yr). The numbers
below are upper bounds for the strategy.

After tax, chained 2005–2022. SPY held and taxed once: **7.45%/yr** (8.52 pre-tax), worst
3-year-window drawdown −52%.

| skill level | stocks | park = cash | windows beating SPY | worst DD | park = spy (exploratory) | worst DD | p vs all |
|---|---|---|---|---|---|---|---|
| top 5 | 5 | 7.63 | 3/6 | −44% | 9.65 | −58% | 0.002 |
| top 10 | 10 | 6.67 | 3/6 | −41% | 8.87 | −61% | 0.002 |
| top 20 | 20 | 4.58 | 3/6 | −40% | 6.81 | −59% | 0.03 |
| top 50% | ~190 | 3.77 | 1/6 | −28% | 6.17 | −52% | 0.001 |
| all | ~380 | 3.16 | 1/6 | −29% | 5.59 | −53% | – |
| skill > 10 | ~14 | 7.41 | 3/6 | −42% | 9.25 | −61% | 0.001 |
| skill > 5 | ~44 | 3.77 | 2/6 | −40% | 5.86 | −60% | 0.12 |
| skill > 0 | ~117 | 3.72 | 1/6 | −30% | 5.97 | −55% | 0.02 |
| strict gate | ~6 | 1.6 | 2/6 | −48% | 3.9 | −56% | 0.66 |
| random 5 / 10 / 20 | | 2.3 / 2.2 / 3.6 | | | 5.2 / 5.1 / 5.8 | | |

- **Under the pre-registered rule no level qualifies** with park = cash. The best levels
  tie SPY after tax but beat it in only 3 of 6 windows.
- **Selection carries information.** The curve rises toward strict, and top 5, top 10 and
  skill > 10 beat the all-stock basket (p ≈ 0.001–0.002). Against a volatility-matched
  null p is 0.005–0.009, so part of the effect is simply a tilt toward volatile stocks.
  Picking the most volatile stocks, with no backtest at all, does nearly as well.
- **The edge is fragile.** The top-5 basket's lead rests on about one big winner per
  window (NVDA 2005-07, AMD, X, NTAP, FCX). Swapping each window's best pick for the
  6th-ranked stock drops it below SPY.
- **"Decent fit" loses to SPY.** Skill > 0 or > 5 made about 3.7%/yr after tax, half of
  SPY.
- **The strict "amazing fit" gate is worse than random**, at 1.6%/yr.
- **Taxes take most of the edge.** Skill top 5 made 11.5%/yr before tax against SPY's 8.5%.
- **On the average S&P 500 stock** the indicator's timing *loses* about 2.2%/yr of skill:
  negative in 5 of 6 windows, the 2008-10 crash being the exception at +0.7.

**Calibration** (`selection.py --calibrate`, 2,318 stock-windows): this is how much of a
stock's past fit carries into the next 3 years. The slope is 0.074, so about 7% carries
forward.

| past skill (%/yr) | stock-windows | next-window skill | share positive | median signal CAGR | median buy & hold CAGR |
|---|---|---|---|---|---|
| ≤ −10 | 305 | −3.3 | 33% | 0.6 | 7.8 |
| −10 to −5 | 550 | −2.2 | 34% | 2.9 | 8.4 |
| −5 to 0 | 749 | −2.2 | 38% | 3.5 | 9.5 |
| 0 to 5 | 448 | −1.7 | 39% | 2.3 | 7.7 |
| 5 to 10 | 184 | −2.2 | 38% | 2.7 | 7.5 |
| 10 to 15 | 51 | −1.1 | 41% | 6.8 | 13.0 |
| 15 to 20 | 19 | +1.4 | 47% | 8.1 | 9.7 |
| > 20 | 12 | −0.4 | 50% | 7.4 | 7.8 |

In every bin the median stock did better held than traded on the signal.

**Pre-registered selection study** (`selection.py`, top 20 by skill):

- **Persistence is real but small:** picks with +14.7%/yr formation skill earned +1.75%/yr
  in test, against −1.91 for all stocks (p < 0.002, Holm 0.01). They beat all stocks in 5
  of 6 windows.
- **Mechanism-only selectors** did as well (test skill about +3.0%/yr): high volatility,
  and deep past drawdown.

### Follow-up hypothesis H2 (pre-registered 2026-10-14, before any 2023+ data was run)

- **Formed from:** the development results above.
- **Design:** each slot holds SPY while its stock is red. Criterion = skill (5-year
  formation). Level = "> 10": every eligible S&P 500 member whose formation-window skill
  exceeds 10%/yr. That level was chosen by the original rule (the loosest qualifying level
  within 1 pt/yr of the best) applied to park = spy.
- **Holdout A:** formation 2018–2022, test 2023-01-03 → 2024-04-25. The qlib data ends
  there, so this is shorter than the planned 2023–2025.
- **Forward B:** formation 2019-04-26 → 2024-04-25 (qlib), test 2025-01-02 → 2026-10-13.
  The test uses split-adjusted data from github.com/q100423gg-coder/us-stock-data, with
  the indicator warmed up from 2024-08. Stock dividends are not credited (conservative),
  while SPY's are.
- **Pass:** after-tax CAGR ≥ SPY held over the same dates, or ≥ SPY − 2 pts with max
  drawdown ≥ 15 pts shallower, in **both** A and B.
- **Reported for information only:** park = cash, levels top 5 / top 10 / all, and the
  random criterion.

### H2 result: FAIL

Results with the audited code (v3). H2 had to pass both tests.

| | basket (skill > 10, park = spy) | SPY held | result |
|---|---|---|---|
| Holdout A, Jan 2023 – Apr 2024 (34 stocks) | 20.3%/yr after tax | 19.8% | +0.5 (inside the dividend-treatment uncertainty) |
| Forward B, Jan 2025 – Oct 2026 (26 stocks) | 10.2%/yr after tax | 14.8% | **−4.6** |

- **Forward B:** without one unverifiable +177% MRNA day (2026-08-19) the basket made
  8.2%.
- **Information only:**
  - Park = spy, top 10 was slightly ahead in all three periods (+1.4 dev, −0.1 A, +1.0 B,
    the last helped by the MRNA day), with deeper drawdowns. This is post hoc, so it is
    not validated.
  - Park = cash lost to SPY in both A and B at every skill level.
- **First run:** before the audit fixes (tax-loss carry across windows, dividend tax under
  total-return prices, qlib's dividend cut-off, the 2020-11-10 data cut-off) the numbers
  were within about 0.3 pt of these, and the verdicts were identical.

### What this means for "how strict?"

- **No level of past fit makes this indicator beat SPY after tax** on S&P 500 stocks in a
  taxable account.
- **Stricter ranking helps relative to other stocks,** but the best levels only tie SPY,
  depend on one big winner per period, and are flattered by survivorship.
- **Looser "decent fit" levels lose clearly.**
- **The pass/fail per-stock gate selects the wrong stocks** rather than being merely too
  strict.

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
- **Outcome (2026-10-14, `strictness.py`):** the basket version of this question was
  tested directly on S&P 500 history 2005–2026, and no basket rule beat SPY after tax out
  of sample. The mechanism hypothesis held in direction: the picks that did best were
  high-volatility trend names. The edge was too small to matter after tax.

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

## Interim guidance

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
