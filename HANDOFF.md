# HANDOFF — trend-indicator research (read this first)

This file lets a new AI instance (or a person) continue the work without
re-deriving anything. It is the authoritative summary; the detailed log with
every table is `analysis_2026/FINDINGS.md`, in chronological order.

**Repo:** https://github.com/Jason-82/moneyline-upgrade (public).
**Working branch:** `claude/add-price-data-csvs-MTD46` (also the default branch).
**Last updated:** 2026-10-13.

---

## 0. The five things you must know before reading anything else

1. **The indicator is an ATR trailing stop (SuperTrend-style), not what README.md
   says.** The user's TradingView indicator ("Moneyline", from Ivan on Tech) was
   first modeled as an Ichimoku-derived HMA/EMA crossover (`src/indicators.py`
   `compute_moneyline`, README "Indicator Logic"). TradingView exports later proved
   that model wrong. **Everything in `src/`, `run_backtest.py`, `scanner.py`,
   `reports/`, `analysis_2026/run_all.py`, `common.py`, `strategies_ext.py` and
   `robustness.py` tests the wrong signal.** Do not cite those results.
2. **Valid results use the TradingView exports themselves**, which carry the real
   green/red state: `data/tv_full/` (crypto, full history) and `data/tv_stocks/`
   (stocks/indices). Code: `analysis_2026/run_full.py`, `run_stocks.py`,
   `confirmation.py`, `stops.py` / `run_stops.py`.
3. **Crypto: trade the DAILY signal.** It beat buy-and-hold on return AND drawdown on
   4 of 5 coins (BTC, ETH, SOL, BNB; not ZEC). Weekly is far worse. Filters,
   confirmations and add-on stops did not robustly improve it.
4. **Stocks: the signal mostly does not work.** Daily on indices destroys returns
   (whipsaw). Weekly on indices is optional crash insurance (~2 CAGR points/yr for
   16-30 points less drawdown). Only crypto-like names (COIN) behave like crypto.
   TSLA: don't use it. HOOD and CRCL: too little history to validate.
5. **The environment has no market-data access.** Yahoo, Alpha Vantage, Binance,
   Kraken, Coinbase and CoinGecko APIs are blocked by the session's egress policy
   (403). All data was uploaded by the user as TradingView CSV exports, which
   contain **close only** (no open/high/low).

---

## 1. Who the user is and how they work (no personal financial data here)

- Uses TradingView with Ivan on Tech's indicator; reads green/red flips on daily
  and weekly charts. Trades crypto and US stocks, uses Robinhood.
- Wants simple, mechanical rules; asks sharp "why" questions and will push back
  when numbers look incongruent (good — answer with reconciliation, not hedging).
- Has asked about: leverage, stop-losses, confirmation filters, entering late into
  a run, daily vs weekly, a daily scanner/digest, and (latest) running the strategy
  through **Robinhood Agentic Trading** with Claude.
- Holds concentrated single-stock positions; specifics are deliberately NOT in this
  public repo — ask the user directly if they matter.
- Preferences learned: lead with the answer, show the table that decides it, state
  caveats once, give a concrete recommendation.

---

## 2. The indicator — what is established

**Export format** (TradingView "Export chart data"):
`time, close, Up Trend, Down Trend, Macro Score Heatmap, Rate Hike, Rate Cut, ATR`

- `Up Trend` populated <=> **GREEN**; `Down Trend` populated <=> **RED**. Mutually
  exclusive. The populated value is the trailing line.
- GREEN <=> `close > line` on 100.0% of bars in all series.
- The line never retraces within a trend run (0 violations in 2,837 in-run bars).
- On a green flip the line sits a median **2.3-2.5 daily ATR** below the close;
  mid-run **1.6-1.8 ATR** below.
- The exported **ATR column is exactly Wilder RMA(14)** of true range. Proof:
  `TR_t = 14*ATR_t - 13*ATR_{t-1}` never violates `TR >= |close_t - close_{t-1}|`
  (every other length does), and implied TR lands on the 0.01 price tick. So daily
  true range is recoverable from exports, and each bar's low is bounded:
  `low_t >= max(close_t, close_{t-1}) - TR_t`.
- `Macro Score Heatmap` was constant 1 in every export; `Rate Hike` / `Rate Cut` are
  sparse 0/1 flags. Not used; unknown purpose.

**Replication from raw OHLC:** see section 8 (results of the IWM replication test).

---

## 3. Data

| folder | contents | notes |
|---|---|---|
| `data/tv_full/` | BTC, ETH, SOL, BNB, ZEC — `_1D` and `_1W` | **Primary crypto dataset.** BTC daily from 2015-07, ETH 2016-05, BNB 2017-07, ZEC 2019-03, SOL 2021-06; through 2026-08-24. Coinbase/Binance feeds. |
| `data/tv_stocks/` | SPX, NDX, IWM, COIN, TSLA, HOOD, CRCL — `_1D` and `_1W` | Daily from ~2010 (TradingView cap ~4,054 bars); SPX weekly from 1967, NDX 1985, IWM 2000. |
| `data/tv_export/` | 300-bar crypto exports | **Superseded** — too short; produced the misleading "weekly looks strong" result. |
| `data/crypto2026/` | CoinGecko daily closes BTC/ETH/SOL/BNB/ZEC | Price only; used with the wrong model. ZEC's first ~3 weeks are garbage (launch illiquidity). |
| repo root `*_historical_data.csv` | QQQ, SPY, IWM yfinance **OHLC** | Only real high/low data in the repo. Used for wick calibration and indicator replication. |
| repo root `btc-usd.csv`, `eth-usd.csv`, `sol-usd-max.csv`, `avax-usd-max.csv`, `BATS_COIN, 1D.csv` | early uploads | Used only by superseded work. |

**How to get more data:** ask the user to export from TradingView after scrolling
the chart back (the export only includes loaded bars). A **candle-mode export**
(open/high/low/close columns) would remove the biggest remaining uncertainty
(intraday stop behaviour) and allow exact indicator replication on crypto.

---

## 4. Conventions used in all valid results

- **Signal:** long while GREEN, flat while RED (long-only, no shorting).
- **Fills:** same-bar close (primary; justified for 24/7 crypto); next-bar close
  reported as a sensitivity. Results can move a lot between the two on small
  samples — always check both.
- **Costs:** crypto 0.1% fee + 5 bp slippage per side; liquid stocks/ETFs 1 bp +
  2 bp. (Robinhood's real crypto cost is a spread — see section 9.)
- **Weekly state on daily bars:** weekly series `shift(1)` then forward-fill, so a
  week only counts once closed. TradingView weekly rows are stamped Monday 00:00.
- **Stocks:** exports are price-only. The "adjusted" view adds dividends to holders
  and T-bill interest when flat (SPX 2.0%/4.0%, NDX 0.8%/3.0%, IWM 1.3%/2.0%).
- **Warmup:** leading bars with neither line populated are dropped; `stops.py`
  also drops the ~14 NaN-ATR bars, so its baseline totals differ slightly from
  `run_full.py`.
- **pandas 3.0 trap:** `.shift()` on a bool Series becomes object dtype and `~`
  then does integer negation (`~False == -1`, truthy). Use numpy bool arrays for
  any flip detection. This bug silently broke two studies before being caught.

---

## 5. Current conclusions (real signal) — with the numbers

### 5.1 Crypto, daily signal vs buy & hold (full history) — `run_full.py`

| asset | signal | buy & hold | signal DD | B&H DD | Sharpe | trades |
|---|---|---|---|---|---|---|
| BTC | 40,688% | 28,427% | -55.0% | -83.8% | 1.4 | 75 |
| ETH | 128,237% | 18,003% | -58.1% | -94.0% | 1.4 | 72 |
| SOL | 1,133% | 226% | -67.3% | -96.3% | 1.1 | 39 |
| BNB | 805,945% | 596,293% | -59.8% | -80.3% | 1.5 | 47 |
| ZEC | 1,139% | 1,379% | -87.8% | -94.3% | 0.8 | 54 |

- In CAGR terms the edge is ETH +35, SOL +37, BNB +9, BTC +5.5, ZEC -3.4 points.
  **BTC's edge is mostly risk reduction**: 1.43x terminal wealth, but 29 points less
  drawdown. ETH and SOL are the real return stories (7.1x and 3.8x terminal wealth).
  Large % totals at 60-170% CAGR exaggerate small rate differences — reconcile via
  CAGR before comparing.
- **Recent eras are weaker** (`robustness.py`-style era check on the real signal):
  since 2022 the signal beats buy & hold on ETH (+26% vs -33%), SOL (+249% vs -46%)
  and BNB (+38% vs +35%), roughly matches BTC (+60% vs +67%) and trails ZEC (+164%
  vs +462%), always with shallower drawdowns. **Since 2024 it trails buy & hold on
  4 of 5** (only ETH wins: +38% vs +7%) — a strong bull market rewards simply
  holding. The edge is largest when deep bear markets occur inside the sample.
- Losing trades are small: median -1% to -4.5%, 5th pct -14% to -22%, worst -22%
  to -43%. **The line is the stop.**

### 5.2 Daily beats weekly decisively (crypto)

Weekly loses to buy & hold on 4 of 5 coins (BTC 8,206% vs B&H 33,628%; ETH 10,873%
vs 20,892%; BNB 29,440% vs 89,665%; ZEC -3%; only SOL wins). Only 4-13 weekly
trades per asset.

### 5.3 Confirmation filters — `confirmation.py`

- **Daily AND weekly green** cuts returns 80-98% (BTC 40,688% -> 5,392%; BNB
  805,945% -> 15,407%) for a few points of drawdown. Don't.
- Decomposition (287 pooled entries): good confirmations (**Donchian breakout**,
  weekly green) raise BOTH hit rate (46.7% -> 51.8-53.6%) AND per-trade gain
  (geo/trade 9.7% -> 12.7-12.9%). Total return still falls because they take fewer
  trades. **Squeeze** filters skip monster runs (+1,216% missed). **Retest** is the
  worst (34.8% hit rate, 4.2% geo/trade).
- A filter is good or bad based only on whether it is correlated with the fat
  right tail (the few huge runs).
- **Leverage:** breakout confirmation truncates in-trade drawdown (worst MAE -25.8%
  vs -42.7%), raising max survivable leverage from 2.34x to 3.88x and growth at
  optimal leverage from 11.5% to 18.0% per trade. But with fractional sizing
  (liquidation survivable), the unfiltered signal wins at every leverage level.
  Leverage numbers are illustrative (frictionless, no funding costs, close-based).

### 5.4 Entering late into a green run is NOT penalised

Median remaining return in the run by entry day: BTC day 51+ +15.3% (74% win) vs
day 0-20 +2.6%; BNB +26.3% vs +4.9%; ZEC +31.8% vs 0.0%. Exceptions: SOL weaker,
ETH 0.0%. Mechanism: most flips are whipsaws that die in 2-4 weeks (median run 16-32
days); a run that has survived 50 days is a proven trend. "I missed the flip" is not
a reason to stay out.

### 5.5 ATR stop-losses on top of the indicator — `stops.py`, `run_stops.py`

Tested "exit on whichever hits first": indicator vs indicator + k x ATR stop.

| variant | stop on daily close | resting stop order (w=0.4) | (w=0.6) | close, 2022+ |
|---|---|---|---|---|
| fixed 1.5 x daily ATR, no re-entry (Ivan's rule) | +2.1 (3/5) | -2.7 (2/5) | -4.9 (1/5) | +4.1 (5/5) |
| fixed 1.5 x daily + buy back above entry | +1.8 (4/5) | +1.8 (4/5) | -4.5 (1/5) | +2.7 (5/5) |
| trailing 1.5 x daily ATR | **-37.5** (1/5) | **-39.0** (0/5) | **-53.8** (0/5) | -3.3 |
| fixed 1.5 x weekly ATR | 0.0 | 0.0 | -1.1 | 0.0 |
| trailing 1.5 x weekly ATR | -20.7 | -12.8 | -28.2 | 0.0 |

(Median CAGR edge vs indicator-only, points; (n/5) = coins improved.)

- The indicator is already an ATR stop (~2.4 ATR away at entry), so a 1.5 x ATR
  stop is a tighter copy of the same exit. Weekly ATR is ~2.7-3.4 x daily ATR, so
  1.5 x weekly ~ 4-5 x daily — wider than the indicator, so it almost never fires.
  Mixing timeframes is not "inconsistent"; it is just pointless.
- Ivan's fixed 1.5 ATR stop is a failed-breakout filter: 45 of 51 stop-outs never
  closed above entry. It wins small and often but threw away BNB's Nov-2020 run
  (+885% indicator-only, -17% stopped on day 2). Pooled CI includes zero.
- Trailing 1.5 ATR exits 81-100% of trades early and is robustly destructive.
- **Recommendation given:** use the daily indicator alone. If a stop is wanted for
  peace of mind: fixed 1.5 daily ATR checked on the daily close with a buy-back rule
  (expect ~neutral), or a wide 2.5-3 daily ATR disaster stop. Never trailing 1.5 ATR.
- Intraday ("resting order") results depend on a wick proxy calibrated on ETF OHLC
  (touch-matched w = 0.40; crypto plausibly 0.4-0.6). Stops helped in 2022+ chop and
  hurt in 2015-2021 bull runs.

### 5.6 Stocks and indices — `run_stocks.py`

| | daily signal CAGR | B&H CAGR | weekly (adj.) | B&H (adj.) |
|---|---|---|---|---|
| SPX | 3.3% | 12.8% | 8.3% (DD -38.9%) | 10.0% (DD -55.0%) |
| NDX | 8.7% | 18.7% | 13.1% (DD -52.2%) | 15.2% (DD -82.3%) |
| IWM | 3.4% | 10.0% | 5.3% (DD -36.2%) | 8.6% (DD -57.7%) |
| TSLA | 21.1% | 42.3% | 21.4% | 41.4% |
| COIN | — | — | **16.6%** (DD -39.2%) | -4.0% (DD -90.3%) |

- Daily on indices: 40-46% of trades close within ±2% (whipsaw); profit factor
  1.2-1.4 vs 3.4-16.3 on crypto. **Do not trade the daily signal on indices.**
- Weekly on indices is crash insurance: helped in dot-com (NDX +28 pts) and GFC
  (SPX +29.5), too slow for Covid, cost 10-20 points in the 2025-26 rally.
- **HOOD** (5 yrs): daily edge is 2 trades of 28 (ex-top-2 = -23%); a one-bar fill
  shift moves daily from 132% to 32%. "Daily AND weekly" looked best (28.4% CAGR,
  -32.7% DD) but is concentrated and fill-sensitive. Unvalidated; use COIN as the
  reference class.
- **CRCL** (1.2 yrs): 4 daily trades. Unanalysable. Weekly flips sat +57% above the
  line (a 36% stop) — entry geometry matters.

### 5.7 Rule of thumb for which assets the signal suits

It needs sustained multi-month trends and deep (-70% to -95%) drawdowns to pay for
its whipsaws: crypto and crypto-beta names (COIN). It fails on assets that grind up
and mean-revert quickly (indices) or that make returns in short explosive bursts
(TSLA). Check profit factor and concentration before trusting any per-asset result.

### 5.8 Position-sizing principle (from a live position decision)

When a personal stop and the indicator's stop disagree, **don't move the stop —
change the size**, so the loss to the indicator's line is one you can actually sit
through. Otherwise you exit somewhere in between and get the worst of both.

---

## 6. Superseded results — do not cite

Everything run on the Ichimoku/HMA/EMA model (baseline/filtered/hybrid systems,
scaled entry, daily+weekly confirmation "keeps 8%", trailing-stop+re-entry, the
"15% stop" MAE study, `reports/*`, `results_daily.csv`, `results_weekly.csv`,
`coverage.csv`) and the 300-bar `data/tv_export` weekly results. Some conclusions
happened to survive on the real signal (filters cost more than they save), others
reversed (weekly looked strong; "don't chase daily flips when weekly is red" was
wrong). The interim "green = close > kijun" hypothesis was only the best proxy
(81-91% bar agreement), not the construction.

---

## 7. Bugs found and fixed (so they are not reintroduced)

- pandas 3.0 bool-shift negation (section 4).
- `stops.py` wick proxy fired stops at prices that never traded; now clipped to the
  low floor implied by recovered true range.
- `stops.py` `run_attribution` paired runs across different windows when
  `start`/`end` were given; now passes the window to the baseline.
- `stops.py` exposure omitted the still-open final position.
- Early on: CoinGecko price-only CSVs needed a loader (`src/data_loader.py`
  `load_price_csv`); "stop exits" for redundant stops were mislabeled.
- Verification practice that caught real problems: independent reimplementation
  from spec, adversarial code review with refute-or-reproduce, run-level
  concentration tests (drop the top 1-2 runs), fill-lag sensitivity, era splits.

---

## 8. Indicator replication from OHLC

_(filled in below once the IWM replication test completes)_

---

## 9. Robinhood Agentic Trading — design notes

_(filled in below once research completes)_

---

## 10. Open questions and suggested next steps

1. Get **candle-mode TradingView exports** (OHLC) for the crypto assets: enables
   exact replication checks on crypto and removes the intraday-stop uncertainty.
2. Ask the user for the indicator's **input settings** (ATR period, multiplier,
   source) from TradingView's settings panel to confirm section 8.
3. Per-asset validation for any new ticker before trading it (protocol in section 9).
4. Portfolio level: crypto assets are highly correlated — treat them as ~one bet
   when sizing. Not yet studied quantitatively.
5. README.md still documents the wrong indicator — add a warning or rewrite.

---

## 11. Environment notes (Claude Code cloud sessions)

- Python: `python3` (3.11). Install with `python3 -m pip install pandas numpy`
  (plain `pip` targets a different interpreter).
- Outbound HTTP to market-data APIs is blocked (403 policy denials) — don't retry.
  WebSearch works for research.
- Commit/push to the working branch; containers are ephemeral.

## 12. File map (valid code)

| file | purpose |
|---|---|
| `analysis_2026/FINDINGS.md` | Chronological log of every result with full tables. |
| `analysis_2026/tv.py` | Loader for TradingView exports (300-bar set). |
| `analysis_2026/run_full.py` | Real-signal backtest, crypto daily/weekly, full history; `load()`, `bt()`. |
| `analysis_2026/run_stocks.py` | Same for stocks/indices, incl. dividend/cash-yield adjustment. |
| `analysis_2026/confirmation.py` | Confirmation-filter decomposition and leverage/liquidation model. |
| `analysis_2026/stops.py`, `run_stops.py` | ATR stop-loss study engine and sweep. |
| `analysis_2026/run_tv.py` | Real signal vs the old models on the 300-bar exports (agreement %). |
| `analysis_2026/results_full.csv`, `results_stocks.csv`, `results_stops.csv` | Current result tables. |
