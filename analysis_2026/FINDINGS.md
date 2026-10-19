# 2026-08-24 — signal-definition discrepancy

The user's TradingView Moneyline showed all five coins flipping GREEN on the
weekly, while this repo's model showed weekly deeply RED (fastHMA 13-18% below
slowMA). Not a rounding artifact — the gap is far too wide.

Testing candidate colour rules against the last weekly bar, only one matches
"all five just flipped green":

| rule                | BTC  | ETH  | SOL  | BNB  | ZEC   |
|---------------------|------|------|------|------|-------|
| fastHMA > slowMA    | red  | red  | red  | red  | green |
| tenkan > kijun      | red  | red  | FLIP | red  | green |
| **close > kijun**   | FLIP | FLIP | FLIP | FLIP | green |

So the visual "green" is very likely price crossing the Kijun/base line, NOT
the fastHMA/slowMA crossover that every backtest in this repo models.

That matters: as a standalone weekly system, close>kijun beats the crossover
on the two largest assets.

| asset | close>kijun | DD    | Sharpe | ML crossover | DD    | Sharpe |
|-------|-------------|-------|--------|--------------|-------|--------|
| BTC   | 192,948%    | -53.5 | 1.3    | 60,066%      | -66.3 | 1.1    |
| ETH   | 191,033%    | -63.9 | 1.2    | 15,816%      | -90.6 | 0.9    |
| SOL   | 3,959%      | -78.6 | 1.0    | 9,734%       | -79.8 | 1.2    |
| BNB   | 1,516%      | -89.0 | 0.7    | 1,450%       | -77.2 | 0.7    |
| ZEC   | 22%         | -87.5 | 0.5    | -28%         | -95.5 | 0.3    |

## Tooling bug found

pandas 3.0 upcasts `.shift()` on a bool Series to object dtype, where `~False`
is the integer -1 (truthy). Any `series & ~series.shift(1)` flip-detection
silently returns every True bar instead of the transitions. run_all.py and
robustness.py are unaffected (crossover() shifts float series), but ad-hoc
analysis must use `.to_numpy(dtype=bool)` before negating.

---

# 2026-08-24 (cont.) — the indicator identified from TradingView exports

Ten exports (5 assets x 1D/1W) settle it. Columns: `time, close, Up Trend,
Down Trend, Macro Score Heatmap, Rate Hike, Rate Cut, ATR`.

`Up Trend` and `Down Trend` are mutually exclusive; the populated one is the
active line. Evidence the indicator is an ATR trailing stop (SuperTrend), NOT
the Ichimoku HMA/EMA crossover in README.md:

* green <=> `close > line` on 100.0% of bars, all 10 series
* the line never retraces within a trend run: 0 violations in 2,837 in-run bars
* on a flip the line sits ~2-3x ATR from close (multiplier ~3 applied to hl2)

Every backtest in this repo before this point modeled the wrong signal.

## Model agreement with the real state (% of bars)

| tf | asset | Moneyline cross | close > kijun | fast>slow |
|----|-------|-----------------|---------------|-----------|
| 1W | BTC   | 70.7            | **90.3**      | 76.0      |
| 1W | ETH   | 74.7            | **90.7**      | 79.0      |
| 1W | SOL   | 71.9            | **86.3**      | 75.3      |
| 1W | BNB   | 69.7            | **82.7**      | 72.3      |
| 1W | ZEC   | 65.2            | **81.4**      | 64.5      |

`close > kijun` was the best available proxy, but it is not the construction.

## Weekly results, real signal, 2020-11 to 2026-08 (same-bar close fill)

| asset | TV signal | B&H    | TV DD  | B&H DD | trades |
|-------|-----------|--------|--------|--------|--------|
| BTC   | +245%     | +312%  | -46.9% | -75.2% | 6      |
| ETH   | +324%     | +319%  | -54.3% | -76.8% | 7      |
| SOL   | +703%     | +33%   | -62.1% | -96.0% | 4      |
| BNB   | +1,203%   | +2,309%| -80.1% | -68.6% | 5      |
| ZEC   | -14%      | +444%  | -94.9% | -93.9% | 9      |

Sample sizes are tiny (4-9 completed trades each) and a one-week change in
fill convention swings BNB from +1,203% to +2,329% and SOL from +703% to
+397%. Treat as directional only.

Daily exports cover just 2025-10-29 to 2026-08-24 (300 bars, a bear window
where every asset's B&H is negative) - too short to conclude anything. More
daily history requires scrolling the TV chart back before exporting.

---

# 2026-08-24 (final) — full-history re-run on the real signal

data/tv_full holds the deep exports (BTC daily to 2015, ETH 2016, BNB 2017,
ZEC 2019, SOL 2021). Sample sizes are now 38-75 daily trades per asset, so
these results carry weight the earlier 300-bar files could not.

## Daily signal vs buy & hold (full history, same-bar close fill)

| asset | Signal | B&H | Sig DD | B&H DD | Sharpe | trades |
|-------|--------|-----|--------|--------|--------|--------|
| BTC | **40,688%** | 28,427% | **-55.0%** | -83.8% | 1.4 | 75 |
| ETH | **128,237%** | 18,003% | **-58.1%** | -94.0% | 1.4 | 72 |
| SOL | **1,133%** | 226% | **-67.3%** | -96.3% | 1.1 | 39 |
| BNB | **805,945%** | 596,293% | **-59.8%** | -80.3% | 1.5 | 47 |
| ZEC | 1,139% | 1,379% | **-87.8%** | -94.3% | 0.8 | 54 |

Beats buy & hold on BOTH return and drawdown on 4 of 5.

## Daily beats weekly decisively

| asset | daily | weekly | weekly vs B&H |
|-------|-------|--------|---------------|
| BTC | 40,688% | 8,206% | loses (B&H 33,628%) |
| ETH | 128,237% | 10,873% | loses (B&H 20,892%) |
| SOL | 1,133% | 704% | wins (B&H 33%) |
| BNB | 805,945% | 29,440% | loses (B&H 89,665%) |
| ZEC | 1,139% | -3% | loses (B&H 1,024%) |

Weekly loses to buy & hold on 4 of 5. The truncated 300-bar files pointed the
other way purely because they started in Nov-2020.

## Correction to the previous round

Using the wrong (Moneyline-crossover) model I reported that taking a daily
green flip while the weekly was red was "worse than buying at random" for BTC
and SOL. On the real signal that does not hold - BTC weekly-red flips return a
+3.3% 30d median vs a +2.9% all-bar baseline, and +11.2% vs +10.1% at 90d.
Roughly neutral, not harmful.

Weekly-green context does improve flip quality on ETH/BNB/SOL, but requiring
both states still costs far more than it saves: Daily AND Weekly cuts BTC from
40,688% to 5,392% and BNB from 805,945% to 15,407%.

## The stop is built into the indicator

Distance from price to the trailing line IS the risk on a fresh entry. Realised
losing trades cluster tight: median -1.1% (BTC) to -4.5% (ZEC), 5th percentile
-14% to -22%, worst -22% to -43%. No external stop is needed and adding one
would cut winners - the line already trails.

---

# 2026-08-24 — stocks and indices (SPX / NDX / IWM / COIN)

Costs lowered to 1bp fee + 2bp slippage (liquid ETF execution) from the crypto
10bp+5bp. Series are price-only: no dividends, and no interest on cash while
flat. An `adjusted` view estimates both (SPX 2.0%/4.0%, NDX 0.8%/3.0%,
IWM 1.3%/2.0%, COIN 0%/2.0%).

## Equities invert the crypto result

Daily, price-only:

| asset | Signal CAGR | B&H CAGR | Sig DD | B&H DD | trades/yr |
|-------|-------------|----------|--------|--------|-----------|
| SPX | 3.3% | **12.8%** | -28.2% | -33.9% | 7.8 |
| NDX | 8.7% | **18.7%** | -26.4% | -35.6% | 7.7 |
| IWM | 3.4% | **10.0%** | -33.2% | -42.3% | 6.9 |

The daily signal surrenders 60-75% of the compounding for 6-9 points of
drawdown. 40-46% of daily index trades close inside +/-2% - pure whipsaw.
Profit factor is only 1.2-1.4 vs 3.4-16.3 on crypto.

## Weekly is the defensible timeframe, once cash yield is counted

Adjusted (dividends to holders, T-bill to the flat):

| asset | Signal CAGR | B&H CAGR | give-up | Sig DD | B&H DD | DD saved |
|-------|-------------|----------|---------|--------|--------|----------|
| SPX | 8.3% | 10.0% | 1.7pt | -38.9% | -55.0% | 16pt |
| NDX | 13.1% | 15.2% | 2.1pt | -52.2% | -82.3% | 30pt |
| IWM | 5.3% | 8.6% | 3.3pt | -36.2% | -57.7% | 22pt |
| COIN | **16.6%** | -4.0% | wins | -39.2% | -90.3% | 51pt |

Weekly runs ~1.2 trades/yr. NDX weekly wins 70.6% of trades at profit factor
6.6 over 41 years.

## It earns its keep in crashes, and only there

Weekly signal edge vs buy & hold over each window:

| crash | SPX | NDX | IWM |
|-------|-----|-----|-----|
| Dot-com | +6.3 | **+28.2** | +15.6 |
| GFC | **+29.5** | **+28.2** | +21.9 |
| Covid | +2.3 | -4.0 | +12.8 |
| 2022 | +1.6 | +9.0 | -1.3 |
| 2025-26 rally | **-13.2** | **-20.3** | -10.6 |

Covid was too fast for a weekly signal to help. In rallies it lags by design.

## Current state (2026-08-24)

SPX and NDX are daily RED (since 08-03) but weekly GREEN (since 04-13) -
price is 1.4%/2.6% below the daily line and 3.9%/4.1% above the weekly.
IWM is green on both. COIN is daily GREEN, weekly RED since 2025-05-12.

---

# 2026-08-24 — TSLA, and the cross-asset scorecard

## TSLA: the signal is bad on both timeframes

| tf | Signal CAGR | B&H CAGR | Sig DD | B&H DD | trades/yr |
|----|-------------|----------|--------|--------|-----------|
| 1D | 21.1% | **42.3%** | -63.6% | -73.6% | 7.0 |
| 1W | 20.2% | **41.4%** | -65.8% | -72.2% | 1.5 |

Half the compounding surrendered for 8-10 points of drawdown - a worse deal
than the indices, where weekly saved 16-30 points. TSLA's return is
concentrated in a few explosive moves (best weekly trade +348%) and its
drawdowns recover fast, so time out of the market is expensive.

## Scorecard: where the signal beats buy & hold

Crypto daily (edge in CAGR points): ETH +35.1, SOL +37.0, BNB +8.8,
BTC +5.5, ZEC -3.4 - and 20-36 points of drawdown saved on four of five.

Equity daily: SPX -9.0, NDX -9.2, IWM -6.4, TSLA -20.1, COIN +3.5.
Equity weekly: SPX -1.7, NDX -2.1, IWM -3.3, TSLA -20.0, COIN +20.6.

Profit factor separates the two classes cleanly: 3.4-16.3 on crypto daily,
1.5-2.0 on equity daily. The signal needs sustained trends and deep
drawdowns to pay; equity indices grind up and mean-revert too fast.

## Entering late into an existing green run is NOT penalised

Median remaining return in the run, by the day you enter:

| asset | day 0-20 | day 21-50 | day 51+ |
|-------|----------|-----------|---------|
| BTC | +2.6% (61% win) | +6.0% (65%) | **+15.3% (74%)** |
| BNB | +4.9% (64%) | +2.9% (59%) | **+26.3% (71%)** |
| ZEC | 0.0% (47%) | -1.4% (38%) | **+31.8% (71%)** |
| SOL | +3.3% (59%) | -0.3% (41%) | +6.5% (58%) |
| ETH | +3.8% (58%) | +2.8% (58%) | 0.0% (42%) |

Survivorship, not mean reversion: a run that has already lasted 50 days is
evidence of a real trend. Four of five assets pay MORE from a late entry.
ETH is the exception (n=66).

---

# 2026-08-27 — HOOD

Only 5.0 years of history (IPO Jul-2021), and the period is dominated by one
move: $11.55 (Feb-2024) to $152.46 (Oct-2025).

| tf | Signal CAGR | B&H CAGR | Sig DD | B&H DD | trades |
|----|-------------|----------|--------|--------|--------|
| 1D | 18.2% | 16.7% | -66.2% | -86.5% | 29 |
| 1W | 19.9% | **22.1%** | -68.8% | -82.8% | 6 |
| 1D Daily AND Weekly | **28.4%** | 16.7% | **-32.7%** | -86.5% | 15 |

The AND result is the best number in the whole project (Sharpe 0.9, PF 3.9,
67% win, 29% exposure). It does not survive scrutiny:

* **Concentration** — daily signal: 196% all trades, 21.4% ex-best,
  **-23.4% ex-top-2**. The entire daily edge is 2 trades out of 28.
  AND filter: 244.5% -> 92.2% ex-best -> 21.3% ex-top-2.
* **Fill sensitivity** — daily 132.3% same-bar vs 31.6% at +1 bar, a 101-point
  spread. Weekly swings 86.6% / 118.7% / 227.5% across 0/1/2-bar lags.
  Nothing with that instability is a measured edge.
* **Sample** — 15 AND-trades, of which 5 pre-2024 trades are small losses and
  the result rests on +58.4% and +79.2%.

Conclusion: HOOD's profile (-86.5% drawdown then 13x) is exactly the terrain
this indicator is built for, but 5 years cannot validate it. Use COIN as the
reference class instead - closest comparable business, and its weekly signal
beat buy & hold by +20.6 CAGR points while saving 51 points of drawdown.

State at 2026-08-27: daily GREEN since 08-21 (6 days), weekly GREEN since
05-26, price 111.68, -26.7% from the Oct-2025 ATH, +14.7% above the daily
line and +31.3% above the weekly line.

---

# 2026-08-27 — CRCL

IPO Jun-2025. 1.19 years daily / 1.05 years weekly after indicator warmup.

**4 closed daily trades. 1 closed weekly trade.** No statistical conclusion is
available and none should be drawn.

Daily trades, in full:

| entry | exit | in | out | pnl |
|-------|------|-----|-----|-----|
| 2025-09-11 | 2025-10-16 | 133.70 | 128.46 | -3.9% |
| 2025-12-03 | 2026-01-20 | 86.29 | 72.70 | -15.8% |
| 2026-02-18 | 2026-03-24 | 63.15 | 101.17 | **+60.2%** |
| 2026-04-14 | 2026-05-26 | 105.49 | 104.17 | -1.3% |

The headline "Signal +52.7% vs B&H -52.8%" is that one +60.2% trade. The other
three lose. Weekly's single closed trade lost 13.6%, and weekly overall is
-65.3% vs -40.8% for holding.

## Entry geometry is the usable finding

Price 94.15, -64.3% from the 263.45 spike (2025-06-23), low 50.23.

* daily GREEN 16 days, **+16.5%** above the daily line -> stop is -14.2% away
* weekly GREEN 0 days (flipped this week), **+57.1%** above the weekly line
  -> stop is **-36.4%** away

Across every other asset studied, a fresh flip sits 11-22% above its line.
CRCL's weekly is at 57% because weekly ATR (16.1) is enormous relative to the
line and the trailing stop has not caught up after the collapse-and-rebound.
Taking the weekly flip here means risking 36% to the exit.

---

# 2026-08-27 — decomposing the confirmation-filter question

Does a confirmation filter raise P(real uptrend) while lowering the remaining
gain - and does that trade become favourable under leverage? Tested on the real
daily signal, pooled across BTC/ETH/SOL/BNB/ZEC (287 baseline entries).

## The premise is half right

| confirmation | entries | P(gain>0) | P(gain>25%) | mean ret | geo/trade |
|--------------|---------|-----------|-------------|----------|-----------|
| none (flip)  | 287 | 46.7% | 19.5% | 24.7% | 9.73% |
| breakout_20  | 247 | 48.2% | 20.6% | 24.7% | 11.41% |
| breakout_50  | 170 | 51.8% | 20.6% | 28.2% | 12.70% |
| weekly green | 153 | 53.6% | 22.2% | 30.4% | 12.89% |
| squeeze      | 171 | 44.4% | 17.0% | 22.8% | 8.62% |
| retest_5pct  | 184 | 34.8% | 10.9% | 11.8% | 4.16% |

Good confirmations raise hit rate AND per-trade gain - there is no magnitude
sacrifice. The reason total return still falls is purely **opportunity count**.

## Why some filters work and others destroy you

What each filter passed on, priced at what baseline earned:

* breakout_20 skipped 40 runs. Every decile negative. 5% were winners,
  **0% were >100%**. It filters pure losers.
* squeeze skipped 116 runs. 50% were winners, **5.2% were >100%**, biggest
  missed +1,216%. It filters the monsters.

The entire question is whether a filter is correlated with the fat right tail.

## The leverage claim is CORRECT - via left-tail truncation, not magnitude

In-trade drawdown (MAE) distribution:

| confirmation | median | p1 | worst | max safe L | best L | geo/trade @ best L |
|--------------|--------|-----|-------|------------|--------|--------------------|
| none | -5.6% | -30.0% | **-42.7%** | 2.34x | 1.75x | 11.52% |
| breakout_20 | -4.8% | -20.9% | -29.6% | 3.38x | 2.50x | 15.96% |
| breakout_50 | -4.0% | -20.4% | **-25.8%** | **3.88x** | 2.75x | **17.95%** |
| retest_5pct | -4.8% | -16.2% | -19.2% | 5.21x | 1.50x | 4.50% |

Baseline is liquidated at 3x (0.7% of trades hit -33%); breakout survives to
~3.9x. At its optimal leverage breakout_50 compounds 18.0%/trade against
baseline's 11.5%. Confirmation buys leverage headroom.

**But** this only holds when liquidation is ruin. Sizing at 20% of capital per
trade so a wipeout is survivable, baseline wins at every leverage level -
287 trades out-compound 170 better ones.

Retest is the worst filter tested: safest tail (max L 5.2x) and the lowest
growth of any variant. Safe and unprofitable.

---

# 2026-10-13 — ATR stop-loss on top of the daily indicator ("whichever hits first")

Question: Ivan on Tech pairs the indicator with a 1.5 x ATR stop and exits on
whichever fires first. A 1.5 x daily ATR stop usually fires long before the
indicator turns red; 1.5 x weekly ATR matches the indicator's drop better but
feels inconsistent with a daily signal. Engine: analysis_2026/stops.py, sweep:
analysis_2026/run_stops.py, results: analysis_2026/results_stops.csv.

## The structural fact that answers most of it

The indicator is itself a Wilder ATR(14) trailing stop. Its line sits a median
2.3-2.5 daily ATR below close on a green flip and 1.6-1.8 ATR below during a run.
Adding a k x ATR stop adds a second copy of the same exit.

* fixed k >= 2.5 daily ATR sits at or below the line from day one: identical to
  indicator-only when checked on the close.
* weekly ATR / daily ATR = 2.7-3.4 (median), so 1.5 x weekly ~ 4-5 x daily ATR,
  WIDER than the indicator's own line. ATR is a volatility ruler, so mixing
  timeframes is not inconsistent; a 1.5 x weekly stop is just a 4-5 x daily stop.
  The indicator actually exits ~2.4 daily ATR (~0.8-0.9 weekly ATR) below the
  run's high close.

## Results (CAGR edge vs indicator-only, points; 5 assets, full history unless noted)

| variant | on close | resting w=0.4 | resting w=0.6 | close 2022+ |
|---|---|---|---|---|
| fixed 1.5 x daily, no re-entry (Ivan) | +2.1 (3/5) | -2.7 (2/5) | -4.9 (1/5) | +4.1 (5/5) |
| fixed 1.5 x daily + buy back above entry | +1.8 (4/5) | +1.8 (4/5) | -4.5 (1/5) | +2.7 (5/5) |
| trail 1.5 x daily | **-37.5** (1/5) | **-39.0** (0/5) | **-53.8** (0/5) | -3.3 (2/5) |
| fixed 1.5 x weekly | 0.0 | 0.0 | -1.1 | 0.0 |
| trail 1.5 x weekly | -20.7 (1/5) | -12.8 (0/5) | -28.2 (0/5) | 0.0 |
| fixed 2.5 x daily (disaster stop) | 0.0 | +2.4 (5/5) | +0.1 (3/5) | 0.0 |

Medians across assets; (n/5) = assets better than indicator-only.

* **Trailing 1.5 x daily ATR is robustly destructive.** Exits 81-100% of trades
  before the indicator; cuts 107-130 winning runs, losing ~5,200pp vs ~650-960pp
  saved. BTC/ETH/BNB stay at -26/-28/-85 after removing each one's most
  influential run. This is the "hits long before the indicator" behaviour.
* **Fixed 1.5 x daily (Ivan's rule) is a failed-breakout filter with a fat left
  tail.** 45 of its 51 close-based stop-outs were trades that never closed above
  entry, a median ~4 days in. It cut 46 losing runs (avg 4pp saved, 185pp total)
  and 5 winners (1,028pp lost), 88% of which is one run: BNB 2020-11-24, +885%
  with the indicator, -17% stopped on day 2. Pooled log edge -1.34, 90% CI
  [-6.3, +2.0]. Hurt 2015-2021, helped 2022+ (bear/chop regime; correlated
  assets, so 5/5 is not five independent confirmations).
* **Buy-back re-entry fixes the catastrophic miss** (BNB re-enters 2020-12-20 and
  catches +875%) but the result is ~neutral: close-based pooled log +0.99, CI
  [-0.19, +2.19], with ZEC contributing +0.84. Fails at w=0.6 and at k=1.25.
* **Trailing weekly ATR fires rarely but at the worst time**: the lagged weekly
  ATR shrinks relative to exploding daily volatility in parabolic legs (all 19
  close-based stop-outs at weekly/daily ratio 0.4-1.8), cutting BNB Feb-2021,
  ZEC Oct-2025, SOL Nov-2023.
* **ZEC is the only asset where an initial stop helps robustly** (+12.7 after
  removing its two best runs) - from many failed flips in 2021-2023 chop, the
  same regime where the indicator itself was weakest.

Conclusion: nothing tested beats indicator-only robustly across fill models,
wick assumptions and eras. The daily indicator alone is the defensible default.

## Verification (8 independent agents)

* From-scratch reimplementation: 40/40 rows match exactly (max |CAGR diff| 0.0).
* Code review: no lookahead; weekly ATR alignment correct (one week stale on
  Sundays - conservative); same-bar relabel P&L-neutral; fees symmetric.
* Confirmed bug F1, fixed: TradingView's ATR is exactly RMA(14), so
  TR_t = 14*ATR_t - 13*ATR_{t-1} (0 violations of TR >= |dClose|; implied TR lands
  on the 0.01 tick) and low_t >= max(close_t, close_{t-1}) - TR_t. The wick proxy
  fired stops below that floor (10% of wick triggers at w=0.3, 36% at w=0.6). Now
  clipped; patched results match the confirmer's independent patch to 1e-14.
  Every correction moved in the stops' favour; close-based tables unaffected.
* Confirmed bug F3, fixed: run_attribution numbered runs on different windows
  when start/end were passed. Latent - no reported figure used it.
* F4 fixed: exposure now includes the position still open on the last bar.
* F2 (fill at stop price on bars closing below it) is the standard
  min(open, stop) convention, valid here because no stop was ever above the prior
  close; flatters stops on crash days. Documented, not changed.
* Wick calibration on real QQQ/SPY/IWM OHLC: touch-matched w = 0.40 (0.37-0.44
  across ETFs, k and ATR length; ~0.45 on P&L once gap fills are counted). 24/7
  crypto with liquidation wicks plausibly sits at 0.4-0.6. A stop checked on the
  daily close matched a real resting intraday stop on average P&L while avoiding
  the ~9% of pure wick-outs.
* Crypto OHLC could not be fetched: Binance, Kraken, Coinbase and CoinGecko are
  blocked by the session's egress policy (403). A TradingView export in candle
  mode (open/high/low/close) would remove the wick-proxy uncertainty entirely.

---

# 2026-10-13 — indicator replicated, Robinhood costs, and audit corrections

## The indicator is replicated exactly from OHLC

Reset-on-flip SuperTrend: Wilder ATR(10) x 2.0 around hl2 (`moneyline_ref.py`).
IWM daily (yfinance OHLC rescaled to TradingView's unadjusted closes): 100.000% state
agreement over 3,790 bars, 213/213 flips same day, line error median 0.0004%; weekly
100%, 39/39 flips. Verified independently with a different rescaling method.
Neighbours: ATR14x2 98.2%, ATR10x2.5 87.8%, ATR10x3 78.9%, ta.supertrend(2,10) 99.97%.
All 23 crypto/stock exports pass a hl2-consistency test for (10, 2.0) and fail it for
alternatives. Requires real highs/lows (close-only = 72.2%), unadjusted prices and closed
bars. The exported ATR column is RMA(14) — a separate plot, not the line's ATR. The
earlier note "multiplier ~3" in this file was wrong.

## Robinhood crypto costs (`costs.py`)

Robinhood charges ~0.95% per side on its default crypto route. At that cost the daily
signal trails buy & hold on BTC (-12.2 CAGR pts) and BNB (-12.7); ETH (+13.5) and SOL
(+18.4) survive. A spot-ETF proxy (signal from the crypto candle, executed 1-2 days later
at 0.02%/side) keeps ETH +22..+43, SOL +38..+40, BTC +1.4..+1.8 (DD -61% vs -84%).

## Audit corrections to earlier entries in this file

* "Losing trades cluster tight: median -1.1% to -4.5%" — that was the median of ALL
  trades. Median LOSING trade: BTC -6.4%, ETH -9.8%, SOL -11.1%, BNB -9.1%, ZEC -12.0%.
* "Entering late is NOT penalised ... four of five pay MORE" — the table exited at the
  last green close, not the red-flip close. Corrected (geometric mean per trade, at flip
  vs day 1-20): BTC 8.3/7.6, ETH 10.2/8.1, SOL 6.3/7.0, BNB 21.0/23.7, ZEC 4.3/2.6. Late
  entry is about as good in the first ~3 weeks; "better" is not supported; day-51+
  buckets rest on 1-7 runs.
* "Daily AND Weekly cuts ... 80-98%" — per asset it gives up BTC 86%, ETH 83%, BNB 98%,
  SOL 45%, ZEC 30% of terminal wealth; BNB's drawdown gets worse.
* "Beats buy & hold on BOTH return and drawdown on 4 of 5" holds with same-bar fills;
  with next-bar fills BTC's return edge vanishes (65.3% vs 66.4% CAGR) while ZEC's turns
  positive. Drawdown advantage holds on all five either way.
* COIN weekly ("+20.6 pts") rests on 6 trades and drops from 15.1% to 4.7% CAGR with
  next-bar fills — as fragile as HOOD. It is not a reliable reference class.
* HOOD "weekly 0/1/2-bar lags 86.6/118.7/227.5%" were the weekly state executed on daily
  bars; native weekly is 143/131/156%.
* "Fixed stops >= 2.5x ATR are identical to indicator-only" — true for 4 of 5; SOL
  differs by one trade.
* stops.py baselines differ from run_full by up to ~5 CAGR pts (different warmup → the
  first trade enters on a different already-green bar), not "slightly".
* The dated "Current state" snapshots (2026-08-24/27) are stale and partly wrong (SPX/NDX
  daily states; COIN weekly turned red 2025-07-28, not 2025-05-12). Recompute from fresh
  exports.
* Equity daily profit factor range is 1.2-1.9 (raw), not "1.2-1.4".

---

# 2026-10-13 (later) — adversarial review of HANDOFF and the agentic plan

41 agents: claims-vs-code, operational risk, strategy soundness and a newcomer test;
35 of 37 high/medium findings were confirmed by refute-or-reproduce and applied.

## Corrections to the entry above

* **Spot-ETF proxy traded on weekends.** The "1-day lag" shifted the 24/7 series by one
  calendar day, so it bought and sold on Saturdays, Sundays and NYSE holidays. Weekend-
  aware version (`costs.etf_want`, NYSE sessions only, 0.02%/side), next / second
  session: BTC -3.1 / -0.2 (DD -69% vs -84%), ETH +38.7 / +25.8, SOL +42.4 / +35.7,
  BNB -0.4 / -2.7, ZEC +2.3 / -28.3. The earlier BTC +1.8 / DD -61% is superseded.
* **"Unadjusted prices"** was the wrong instruction: TradingView shows split-adjusted,
  not dividend-adjusted prices. Use Robinhood adjustment_type='split'.
* **Late-entry geometric table** is pooled over overlapping (run, entry-day) pairs, not
  "per trade"; now in `supplementary.late_entry_geo()`.
* **Position sizing**: distance at a flip is a median 10-16%, not 6-12% (that is the
  in-run figure); exits fill a median 1.5-2.3% past the line (worst 10-33%; 21-40% on
  the ETF route).
* **IWM fails the weekly INSURANCE test** (gives up 3.3-4.1 pts/yr).
* **Equity daily profit factor** (raw): SPX 1.6, NDX 2.0, IWM 1.3 in gate.py's
  next-session view; 1.4-1.9 same-bar. Not "1.2-1.4".
* The stop-loss entry's "the indicator is itself a Wilder ATR(14) trailing stop": the
  line is ATR(10) x 2.0; ATR(14) is only the exported column used there as a ruler.

## New committed results

* `gate.py` (illustrative 35% short-term / 20% long-term tax): ETH via spot ETF passes
  all 7 tests (after-tax edge +21.5); SOL fails only the history test (PROBATION);
  BTC (-14.3 after tax via ETF), BNB, ZEC and every stock fail. SPX/NDX qualify as
  weekly INSURANCE, IWM does not.
* Era blocks (annualised log wealth vs B&H, ETF route): ETH 2017-19 +0.60, 2020-22
  +0.05, 2023-25 -0.07; BTC +0.10, -0.10, -0.13. The edge is bear-market avoidance.
* `portfolio.py`: sizing changes risk, not quality - CAGR per unit of drawdown is
  similar for full allocation, fixed 25% and distance-based sizing; prefer fixed fraction.
* `replicate.py`: IWM daily 100.000% / 213 of 213 flips; weekly 100% / 38 of 38;
  hl2-consistency 100% on 23 of 24 exports for (10, 2.0), 4-95% for alternatives.


---

# 2026-10-13 (later still) — stock universe: screener and selection study

The user wants to widen the stock universe beyond the 7 tested names, either by scanning
for flips or by picking a basket where the indicator "worked best historically".

* `screener/scan.py`: exact indicator on any OHLC. Matches TradingView on IWM for all
  3,517 dates 2012-2025 (state, flip date, days in state). Fed dividend-adjusted data it
  disagreed on 23 dates in 8 episodes; e.g. a 0.34% dividend adjustment hid the
  2025-12-17 red flip.
* `screener/selection.py`: walk-forward selection study. A 28-agent review (21 of 25
  high/medium findings confirmed) fixed:
  - the test metric: drift-neutral skill instead of "beat own buy & hold", which
    rewards fallers
  - look-ahead eligibility on delisting
  - overlapping windows; added a permutation test with Holm correction
  - a 2023-25 holdout
* Synthetic harness checks: on no-skill random walks, picks with +21.5%/yr formation skill
  earned -1.3%/yr in test vs -2.1% for all (p = 0.39). In a persistent-trend world
  they kept +16.8% vs +5.3% (p < 0.01).
* `gate.py` gains T2b, a vs-SPY after-tax hurdle (COIN now fails it; no other verdict
  changed); `placebo()` (circular-shift false-pass rate; ~2% of no-edge stocks pass at
  7-8 years of history); and `asof`/`recent_years` for walk-forward use.
* Not run: the real-data selection study. No stock data is reachable from the sandbox,
  and a current-S&P-500 yfinance universe would be survivorship-biased anyway.


---

# 2026-10-14 — how strict should the stock fit filter be? (real S&P 500 data)

The user asked whether the gates are too strict: maybe a "decent fit" stock basket beats
SPY even if no single stock passes the per-stock gate. That calls for a basket test that
varies the strictness. Full method and tables: `screener/README.md` ("How strict should
the fit filter be?").

**Data, now reachable from the sandbox:**

- qlib US daily (GitHub release download), 2000 to 2024-04: 852 of 1,128 tickers that were
  S&P 500 members since 1999. 36 broken or spliced series were dropped.
- Point-in-time membership from fja05680/sp500.
- A daily-updated split-adjusted parquet (q100423gg-coder/us-stock-data), 2024-08 to
  2026-10, for the forward test.
- Robinhood MCP historicals also work, because large results are saved to a file; history
  from 1999-09.

**Process:**

1. Pre-registered the decision rule (commit 6b6908c).
2. Ran development windows 2005–2022.
3. No level qualified, so pre-registered follow-up H2 (eea8dac) before any 2023+ run.
4. Ran holdout A (2023-01 to 2024-04) and forward B (2025-01 to 2026-10).
5. A 4-lens adversarial audit (leakage, accounting, data, independent recomputation)
   reproduced every headline number. It led to four fixes: tax-loss carry across windows,
   dividend tax under total-return prices, qlib being price-only after 2021-09-16, and
   qlib's 2020-11-10 collection cut-off. Verdicts are unchanged; numbers moved by
   ≤ 0.3 pt.

**Results** (after tax, 35%/20% illustrative rates; audited v3):

- **Development 2005–2022, SPY held 7.45%/yr, park = cash:**

  | level | after tax | windows beating SPY |
  |---|---|---|
  | skill top 5 | 7.63 | 3/6 |
  | skill > 10 | 7.41 | 3/6 |
  | top 10 | 6.67 | |
  | top 20 | 4.58 | |
  | all stocks | 3.16 | |
  | "decent fit" (skill > 0 / > 5) | 3.7 | |
  | strict per-stock-gate style | 1.6 | |
  | random 5 / 10 | 2.3 / 2.2 | |

  **No level qualifies.**
- **Selection carries information:** top 5, top 10 and > 10 beat all stocks, p ≈ 0.001–0.002
  (0.005–0.009 against a volatility-matched null). But the edge rests on about one big
  winner per window, and survivorship (60–66% of 2005/2008 members usable, the failures
  missing) flatters the baskets by an estimated 0.3–1 pt/yr.
- **H2** (park = spy, skill > 10):
  - development +1.8 pts/yr
  - holdout A +0.5, inside the dividend uncertainty
  - forward B **−4.6**
  - **FAIL**
- **Calibration:** only 7% of past fit carries into the next 3 years (slope 0.074 over 2,318
  stock-windows). In every past-fit bin the median stock did better held than traded.
- **Pre-registered selection study** (top 20 by skill): test skill +1.75 vs −1.91 for all
  (p < 0.002, Holm 0.01). High-volatility and deep-drawdown selectors did as well with no
  backtest.
- **The average S&P 500 stock** loses about 2.2%/yr of timing skill to the indicator,
  negative in 5 of 6 windows.

**Conclusion:**

- In a taxable account, no strictness level makes the daily indicator on S&P 500 stocks
  beat holding SPY.
- The per-stock gate isn't merely too strict: its "amazing fit" filter picks the wrong
  stocks.
- Looser filters add stocks and lose more.
- The stock scanner stays information only.
- **Bug found and fixed in passing:** `selection.py` read broken series because it lacked
  the quality filter (CHK's broken series returned 5,306× in 2008-10). It now uses it.


**Robustness on point-in-time data that includes dead companies** (added the same day):

- **Data:** Johnbrick123/sp500-data (`data.from_sp500_pit`). Coverage is 89–98% of members
  at every re-pick date.
- **2001–2021 park = cash:** SPY held 7.16 after tax. Skill top 5 made 6.89, skill > 10
  6.35, all stocks 3.38. No level beats SPY.
- **Park = spy:** development +0.8 to +2.3 pts/yr, but **every level lost to SPY in the full
  2023–2025 holdout**. H2 made 12.10 vs SPY's 18.76.
- **2026 to date:** random baskets also beat SPY by ~18 pts (uninformative).
- **Calibration slope** 0.143; selection study test skill +2.3 vs −1.9.
- **Conclusion unchanged and strengthened.** Results are in
  `analysis_2026/results_strictness/pit/`.


---

# 2026-10-14 (later) — why the signal beats holding on crypto but not on stocks; does it suit small coins?

**Data and code:**

- Binance's public archive, read through its S3 bucket (reachable from the sandbox): daily
  klines for 676 USDT pairs including delisted ones.
- `analysis_2026/altcoins.py` splits files at reused tickers or redenominations (LUNA vs
  Terra 2.0), leaving 581 coins with ≥ 200 bars.
- Each year, coins are ranked by 90-day USDT volume into tiers 1-10 / 11-30 / 31-100 / 101+.
- Each coin is traded on the exact indicator from the next open, at retail costs of
  0.30-0.75%/side, and compared with holding the same coins. Delisted coins are sold at
  their last price.
- Q1/Q2 were pre-registered in commit a915787. A 3-lens adversarial audit (data, accounting,
  72-variant robustness) reproduced every number to ~1e-14.

**Results:**

- **Payoff profile, the mechanism** (`payoff_crypto.csv`, `payoff_stocks.csv`). The signal
  beats holding in 97% of asset-years that fell more than 60%, but only in 22-41% of
  rising crypto years and 6-23% of rising S&P stock-years.

  | | crypto coin-years | S&P 500 stock-years (2001-25) |
  |---|---|---|
  | fell more than 60% | 37% | 1.8% |
  | fell more than 30% | 48% | 9% |
  | between −30% and +100% | | 89% |

  **The indicator is crash insurance with partial trend capture.** Crypto crashes often;
  stocks rarely do.
- **Q1 (edge grows as coins get smaller): NO.** The signal beats holding the same coins in
  every tier, in every one of 72 variants (2019-25 edges +28 / +47 / +35 / +41 pts/yr).
  But there is no consistent size gradient, and the edge comes from the two crash years:
  2022 and 2025 had 79-90% of coin-years down more than 60%. Excluding them, the edge is
  about zero or negative in 3 of 4 tiers.
- **Q2 (small-coin signal basket beats large coins and BTC after tax): NO, in effect.**
  Over 2019-25 it looks positive, but only with January starts and because of one coin:
  2021's small tier held 5 coins, DENT 50×. Over 2022-25, with every tier full, the small
  coins lost 7.6%/yr after tax with the signal (negative in 72/72 variants) against −30%/yr
  held.
- **2022-25 after tax** (January 2022 start, two months after the cycle top):

  | | signal | held |
  |---|---|---|
  | top-10 basket | +5.5 | −12.6 |
  | 11-30 basket | +11.0 | −24.9 |
  | BTC | | +14.3 |
  | SPY | | +9.0 |

  "BTC beat every tier" holds only for windows starting near the 2021 top and only after
  tax. January-start windows ending 2022-24 had the large-coin signal baskets 20-60 pts/yr
  ahead of BTC.
- **Costs barely matter for the sign** (break-even 2-4%/side). Taxes matter for the
  absolute comparisons.

**Conclusion:**

- The signal's edge comes from sidestepping deep crashes, not from catching more of the
  upside.
- Smaller coins don't give a reliably larger edge, and as a group they lost money even with
  the signal.
- Whether a crypto signal basket beats simply holding BTC depends on the period.


---

# 2026-10-14 (latest) — professional-style trend following as a portfolio sleeve

`analysis_2026/trend_portfolio.py`; hypotheses H1-H3 pre-registered in commit cb734f8.
Results in `analysis_2026/results_trend/`.

**Setup:**

- **Universe A** (2005-2026): 12 ETFs covering US/international/emerging stocks, Treasuries,
  TIPS, corporate and high-yield bonds, gold, silver and REITs.
- **Universe B** (to 2024-04): A plus commodities and currencies.
- **Sleeves:**
  - **S1** 12-month time-series momentum, long/short, sized by volatility to 10% annual
    vol. This is the professional reference.
  - **S2** the same, long-only and unlevered.
  - **S3** the user's daily indicator per ETF, long-only, volatility-sized.
- **Execution:** one-day lag, 0.05%/side.
- **Audit:** two lenses. An independent engine rebuild matched every number with no
  look-ahead, and a 324-variant sensitivity sweep tested robustness.

**Universe A results, 2005-2026** (pre-tax CAGR / Sharpe / max drawdown; after-tax CAGR
at the illustrative 35%/20% rates):

| portfolio | pre-tax CAGR | Sharpe | max DD | after tax |
|---|---|---|---|---|
| 100% SPY | 10.95 | 0.55 | −55.2 | 9.69 |
| 80/20 SPY + T-bills (baseline added after the first run) | 9.36 | 0.56 | −45.8 | 8.78 |
| 80/20 SPY + IEF (baseline) | 9.70 | 0.59 | −43.2 | |
| 80/20 + S1 | 10.29 | 0.61 | −42.9 | 8.94 |
| 80/20 + S2 | 10.03 | 0.58 | −44.8 | 8.90 |
| 80/20 + S3 | 9.53 | 0.56 | −46.8 | 8.81 |
| 60/40 SPY/IEF | 8.26 | 0.65 | −29.8 | |
| 60/20/20 SPY/IEF/S1 (exploratory) | 8.87 | 0.67 | −29.4 | |

**S1 alone:** 5.97%/yr; +15.8% in 2008 and +11.7% in 2022; correlation with SPY 0.11.
About 3%/yr since 2015, and rolling 5-year windows starting 2013-16 lost to T-bills.

**Hypotheses:**

- **H1 and H2 pass as written, but the bar was too lenient.** Both compared against
  100% SPY, so any 80/20 mix "passes" by holding less stock.
- **Against the fair cash baseline,** S1 beats T-bills in 91% of variants by typically
  about +0.5 pt/yr (+0.4 to +0.9), with Sharpe +0.03 to +0.05.
  - The Sharpe gain comes entirely from 2008 and 2022.
  - The return gain came mostly from 2010-14, when it held leveraged trending bonds and
    T-bills paid ~0%.
- **Against an equal bond allocation,** S1 is a coin flip (median Sharpe gain 0.00).
- **S2** adds a similar return over cash but almost no risk-adjusted benefit, and is worse
  than bonds.
- **S3 (the user's indicator done the professional way) adds nothing** in every variant.
- **H3:** no 80/20 mix beats 100% SPY's return in the pre-registered setting or in any
  one-day-lag variant.
- **Real funds:** WTMF returned −1.1%/yr over 2011-21 vs S1's +2.9%. Correlation between
  the ETF proxy and real funds is 0.3-0.55, so it is only a rough proxy.

**Practical conclusion:**

- Professional trend following is crash and inflation insurance, valuable mainly in
  2008/2022-type years when bonds may also fail.
- It isn't a way to beat stocks.
- It needs shorting and leverage, so it can't run in the Robinhood agentic account.
  Access it through a managed-futures ETF (about 0.85-0.95% fee, which trims ~0.2 pt),
  ideally held in a tax-advantaged account.


---

# 2026-10-14 (latest) — mean reversion across styles and sectors

`analysis_2026/style_rotation.py`. R1-R3 were pre-registered in adaa1c9 and extension E1-E3
in 99b8d9d. Results are in `analysis_2026/results_style/`.

**Data:**

- **Ken French portfolios.** 1949-2017 from the linearmodels bundle. 1926-2026 from GitHub
  mirrors (202606 vintage): 25 size x book-to-market portfolios with monthly BE/ME, plus
  10 and 49 industries.
- **ETFs with dividends:** iShares and S&P style ETFs and sector SPDRs (2000-2026), Vanguard
  Russell style ETFs and Invesco small-cap sector ETFs (2010-2026).

**Rules:**

- **Contrarian:** hold the bottom third by the months t-60..t-13 return, rebalanced each
  December (FF long-term reversal convention).
- **Benchmark:** equal weight of the same set.
- **Also tested:** gentle tilts, winners, 12-1 momentum, and small value vs large growth
  pairs.
- **New hypothesis:** timing by the price-updated valuation spread.

**Audit:** four lenses. Independent engines matched to ~1e-16 with no look-ahead. Bootstrap
and iid-month nulls, multiple-testing corrections, and an 'extreme lag' episode study
were added.

**Results:**

- **R1 FAIL** (style boxes 1955-2017): −1.2%/yr CAGR vs equal weight. On the unseen data
  it was +2.3 in 1932-48, carried by the 1932 rebound and not significant, and −1.2 in
  2017-26. Full 1932-2026: about 0.
- **R3 FAIL** (small value vs large growth, tilting toward whichever lagged over 5 years):
  −0.4 to −1.7%/yr in every period and variant.
- **R2 not significant** (industries): +1.0%/yr, t 1.5. That is just value and size
  exposure (alpha about 0) and comes mostly from 1975-84. On 49 industries over 1932-2026
  it is +1.3 (t 2.05), from the 1932-35 rebound; it does not survive multiple-testing
  correction.
- **E3 FAIL** (valuation-spread timing of small value vs large growth): −0.9%/yr, t −1.4
  over 1947-2026; about 0 across 48 variants.
  - Before 1987 it kept the strategy underweight small value through its best decades
    (the spread trended down).
  - Since 1987 timing added about +1%/yr, not significant.
  - December 2025 z = +1.0, a wide spread; 2020 was the widest since the 1940s.
- **The user's exact idea** (tilt to small value after an extreme 5-year lag) has 4
  independent episodes since 1963, with mixed outcomes. Its apparent gain is the small-value
  premium, not timing (placebo p 0.19-0.49). The 2020 episode was +21% in year 1 and −29%
  for December-2020 entrants after 5 years.
- **Why contrarian fails:** there is mild 3-5 year reversal (90th percentile against a
  no-predictability null), but the losers it buys are often chronically weak boxes. It
  held small growth, about 8%/yr vs 17.6% for small value, in 76% of years.
- **Momentum (12-1, quarterly):**
  - 49 industries: +2.6%/yr, t 3.6 over 1932-2026, surviving correction, but driven by
    1949-2016.
  - Not confirmed in 1932-48 or 2017-26. Its edge would also be heavily taxed (quarterly
    turnover).
- **ETFs 2006-2026:** no contrarian benefit; every |t| ≤ 1.2.
- **Equal-weighting styles or sectors vs the market:**
  - Ahead over 1932-2026 (+2.2%/yr, t 2.8: the static small/value tilt).
  - Behind in 2017-2026 (−1.0 to −2.3%/yr) and in ETFs 2006-2026 (−0.4 to −1.3%/yr).
- **ETF data fixes:** qlib IWS stops after 2020-11, so the set is cut there. The XLF
  Sep-2016 XLRE spin-off booked as +26.5% is replaced with the correct month.

**Conclusion:**

- Rotating toward long-run laggard styles or sectors has no reliable edge over 95 years.
- A permanent value/small tilt is the cleaner way to own that premium, but it has lagged
  for about 20 years.


---

# 2026-10-14 (latest) — leverage, tight stops and "key level" breakouts

`analysis_2026/leverage_breakout.py`. H1-H4 were pre-registered in 4cb2b28; an engine smoke
test on BTC ran before that commit. Results are in `analysis_2026/results_leverage/`.

**Data:** Binance spot 4h and daily bars for 20 large coins (2017/2020 to 2026-09), actual
USDT-M funding rates, the survivorship-inclusive daily universe, and ETFs.

**Systems:**

- the user's indicator (ML)
- Turtle/Donchian breakouts: BO20 (20-day high entry, 10-day low exit, 2xATR stop) and
  BO55 (55-day high, 20-day low exit, 2xATR stop)
- tight-stop versions (1 and 0.5 ATR, 2% fixed)
- a "tested key level" breakout

**Leverage model:** a sub-account at 1x/3x/5x of its equity, with liquidation and funding
on perpetuals.

**Audit:** two lenses. Independent engines reproduced all 4,800 trades and 400 equity
rows; a truncation test found no look-ahead. Fixes applied before the final numbers:

- funding charged on current position value
- liquidation level includes fees and funding
- MATIC funding taken from the POL file
- idle cash earns T-bills
- open trades marked at the end
- buy & hold aligned to the strategies' start

**Results (daily, 2018-2026, after audit fixes):**

- **H1, leverage on the indicator, wealth destroyed:**

  | | 1x spot | 1x perp | 3x perp | 5x perp |
  |---|---|---|---|---|
  | BTC final multiple | 12.4 | 7.0 | 1.9 (DD −97%) | liquidated |
  | ETH final multiple | 20.1 | 9.4 | 1.9 (DD −98%) | liquidated |

  - Across 20 coins, 3x blows up 85% of sub-accounts and 5x 100%.
  - The Sharpe clause of H1 is NOT met for ETH at 3x (≈ equal to 1x). Sharpe barely
    moves with leverage; the damage shows in wealth and blow-ups.
  - Kelly-optimal leverage is ≤ 1.85 on every coin (median 0.77), so 3x exceeds full
    Kelly everywhere.
  - Volatility drag (L²σ²/2) is the mechanism.
  - Perpetual funding averaged ~31%/yr on BTC in 2021; even 1x perp lags 1x spot by
    ~8-12 pts/yr.
- **H2, breakout expectancy, positive raw but fragile:**
  - BTC+ETH fails t ≥ 2: BO20 t 1.96, BO55 t 1.58.
  - Other 18 coins and the top-20 universe pass on naive t (BO20 3.7-4.1, BO55 2.2-2.3).
  - Clustering by entry month: only BO20 stays ≈ 2.
  - Excluding the top 5% of trades makes every crypto system negative; 2020-21 carries
    everything.
  - Random entries with the same exits earn half of BO20's expectancy and about all of
    BO55's.
  - **Breakouts are not better than the user's indicator:** BO20 − ML on BTC+ETH paired
    monthly t = 0.07; 82-85% overlap in days held.
- **H3, tight stops, confirmed:** on all 20 coins, BO20 at 0.5 ATR makes 2.7% per trade vs
  10.3% at 2 ATR (89% stopped out); a 2% fixed stop makes 1.0%. Robust to costs and start
  date.
- **H4, 4-hour bars, worse than daily** for every system: median CAGR and Sharpe lower,
  drawdowns deeper.
- **The user's literal idea (BTC breakout, tight stop, 3-5x):** 430x in-sample at 5x
  (BO20-k0.5), from 1-3 trades (Oct 2020 - Mar 2021).
  - 5x beat 1x on 1 of 20 coins (BTC); 16-19 of 20 coins lost money at 5x.
  - Random entries with the same rules lost money 64% of the time.
  - Lottery-like; not an edge.
- **Total-capital view:** 20% sub-account at 5x plus 80% T-bills vs 100% at 1x spot (the
  same market exposure). BTC indicator: 1.04x vs 12.4x; ETH: 1.04x vs 20.1x. The
  leveraged sub-account is liquidated by moves the unlevered position survives.
- **Risk-based sizing** (risk 1-2% per trade) is not leverage (0.1-0.3x exposure). It halves
  drawdowns but doesn't rescue leverage; getting 3-5x with tight stops means risking
  5-15% per trade.
- **ETFs 2005-2026:** breakout and indicator CAGR 2.3-2.9% vs buy & hold 7.3%. Sharpe is
  about equal; drawdowns about −25% vs −59%.


---

# 2026-10-14 (regime switch) — why the indicator trails buy & hold, and switching by regime

`analysis_2026/regime_switch.py`. Pre-registered in da40354 (H-A1, H-B1 to H-B5); first run
b04aad9. Every table is in `analysis_2026/results_regime/summary.txt` and the CSVs beside it.

**Review history:**

- **Two audits** (an independent recomputation and an adversarial code review) found six
  bugs. Fixing them moved:
  - **S&P 500 CAGRs:** up to about 0.35 pt over 1963-2026, and up to about 0.6 in the
    1994-2026 half. On H-B2's 200-day leg that half moved 10.50 → 10.96, or 8.18 → 8.48 after
    tax.
  - **S&P drawdowns:** about 1.3 pts, and up to 5.9 for the HMM regime rule.
  - **Part A shares:** up to 2.4 pts.
  - **TradingView coin rows:** about 0.2-1 pt on the headline cells, and up to 2.7 on
    half-window rows (from dropping the still-forming last bar, and the tax fix).
  - **Coin basket:** 1.6-5.5 pts on its own-coin rows, 1-8 on market-variant rows and 11 on
    the hindsight row (from forming at the prior close, and Binance BTC as its market).
- **The pooled S&P stock set** for H-A1 now counts only membership years. It lost 42% of its
  spells.
- **No verdict changed,** but the full-period leg of H-B2 went from fail to pass.
- **A verification pass** followed: six lenses, each finding re-checked by a skeptic, 48
  findings confirmed. It corrected this write-up and added three exploratory tables.

**The user's questions:**

- The daily indicator rarely beats buy & hold, yet it cuts drawdowns. Is the up-market loss
  "false breakouts", i.e. selling on a red flip and having to buy back higher? If not, why
  does it fail overall?
- Then why not hold in good regimes and use the indicator only in bad ones? Test it on all
  assets.

**Data:**

- **S&P 500, 1962-2026 (64 years, about ten bear markets).** Real ^GSPC OHLC 1962-2018
  (vijinho/sp500), then SPY. Dividends and T-bills come from SteelCerberus/us-market-data.
  Over 2010-2018 the computed indicator matches TradingView's SPX export on 100% of days, and
  on 98.6% after the SPY splice.
- **Other markets:**
  - 14 ETFs, plus TSLA, COIN and HOOD (Johnbrick123 parquet)
  - the five TradingView crypto exports
  - S&P 500 point-in-time members 1997-2026, including dead companies
  - 40 Binance coins including LUNA and FTT
- **Macro:** US unemployment (FRED mirror cyby2000/fred-relay; FRED itself is blocked).
- **Rebuild everything:** `python3 -m analysis_2026.fetch_regime_data`.
- **Execution:**
  - Stocks and ETFs trade at the next session's close, 0.03%/side, with T-bills while flat.
  - TradingView crypto trades same-bar at 0.15%/side, the pre-registered basis. The
    next-bar and spot-ETF routes are reported too.
  - The Binance coin basket trades same-bar at 0.30%/side. The S&P member basket follows the
    stock rule.
  - After tax: 35% short-term / 20% long-term, by holding period; dividends and interest
    taxed yearly.
- **Units:**
  - "CAGR" and "pts/yr after tax" are compound annual rates.
  - Decompositions are in **log pts/yr** (100 × annual log growth), which add up exactly.

## Part A: the up-market loss is mostly false breakdowns (H-A1 CONFIRMED)

**Definitions:**

- **Red spell:** the flat period from the exit fill to the re-entry fill.
- **Save:** a spell that ends with the re-entry price, after T-bill interest, below the exit.
- **False breakdown:** a losing spell whose lowest close stayed within 1 ATR of the exit.
  ATR here means ATR(14) as a share of the close, used as a ruler; it is not the indicator's
  own ATR(10).
- **Late round trip:** a losing spell where price fell more than 1 ATR after the exit, then
  rebounded above it before the re-entry.
- **Bull/bear phases:** dated *with hindsight*. A phase turns once price moves 20% (crypto
  50%) from its running extreme.

Share of bull-phase gross loss from false breakdowns:

| set | 1 × ATR | 0.5 × ATR | 2 × ATR |
|---|---|---|---|
| S&P 500 1963-2026 | **81%** | 64% | 93% |
| S&P 500 members, 106k spells | **81%** | 66% | 95% |
| Binance coins, 1.6k spells | **87%** | 69% | 98% |

**In bull phases the signal is wrong far more often.** False breakdowns are a similar share
of the losses in both phases, but they are 2.4-3 times as frequent in bull phases (2.5× on
the S&P, 2.4× on its members, 3.0× on coins):

| | spells that lose (bull / bear) | false breakdowns, share of all spells | false breakdowns, share of losses |
|---|---|---|---|
| S&P 500 1963-2026 | 80% / 41% | 57% / 23% | 81% / 77% |
| S&P 500 members | 81% / 43% | 57% / 23% | 81% / 67% |
| Binance coins | 80% / 38% | 59% / 20% | 87% / 74% |

In bear phases the saves are both more frequent and larger.

**The mechanism.** Medians over closed spells, excluding the spell that is already open at
each window start:

- **Re-entry lag:** the indicator buys back 2.2-2.6 ATR above the low.
- **Further decline:** after an exit, price falls a further 0.9 ATR (S&P), 1.2 (stocks) or
  1.7 (coins).
- **So a spell saves money only when price keeps falling past the exit by more than the
  re-entry lag.** Most of the time it doesn't.
- **Exit lag:** the indicator sells 2.1-2.4 ATR below the peak. Buy & hold also loses that
  move, so it is not part of the gap with holding. Against a perfect timer, a round trip
  costs about 5 ATR.

| | spells that save | median false breakdown | median save | 90th-percentile save |
|---|---|---|---|---|
| S&P 500 1963-2026 | 27% | −2.2%, 9 days | +2.5% | +10% |
| S&P 500 members | 33% | −4.4%, 10 days | +4.4% | +21% |
| BTC | 30% | −7.3%, 15 days | +17% | +54% |
| ETH | 38% | −10.6%, 11 days | +23% | +98% |
| Binance coins | 44% | −12.7%, 12 days | +19% | +70% |

**Verdict on the hypothesis: right about the mechanism, incomplete as an explanation.**

- Selling on a flip and buying back higher with no real decline in between is most of the
  loss in rising markets.
- The same kind of trade is also most of the (smaller) loss in falling markets, but there it
  is outweighed by deep saves.

## Why it fails overall: time in bull markets times the toll

The log gap between the indicator and buy & hold splits exactly into three parts:

- **drift:** being out of a rising asset, with no timing at all
- **timing skill:** whether the flat days were worse than average days (positive = good)
- **costs**

The two "per year in" columns are the indicator's relative return per year spent in that
phase.

| asset | window | IND CAGR | BH CAGR | log gap | drift | timing | costs | time in bull | per year in bull | per year in bear |
|---|---|---|---|---|---|---|---|---|---|---|
| S&P 500 | 1963-2026 | 6.2 | 10.8 | −4.2 | −2.1 | −1.7 | −0.4 | 84% | −10.0 | +28.9 |
| SPY | 1996-2026 | 6.8 | 10.4 | −3.3 | −2.7 | −0.2 | −0.4 | 85% | −10.9 | +44.0 |
| QQQ | 2000-2026 | 7.4 | 9.0 | −1.5 | −2.7 | +1.6 | −0.4 | 85% | −17.2 | +90.4 |
| IWM | 2001-2026 | 4.0 | 8.6 | −4.3 | −2.7 | −1.2 | −0.4 | 81% | −20.1 | +64.0 |
| TSLA | 2011-2026 | 33.6 | 44.0 | −7.5 | −15.6 | +8.5 | −0.4 | 58% | −97 | +119 |
| BTC | 2016-2026 | 72.1 | 63.1 | +5.4 | −23.3 | +30.8 | −2.1 | 63% | −59 | +122 |
| ETH | 2017-2026 | 67.3 | 27.6 | +27.1 | −11.3 | +40.5 | −2.1 | 55% | −90 | +173 |
| SOL | 2022-2026 | 43.6 | 22.0 | +16.3 | −8.2 | +26.7 | −2.3 | 68% | −61 | +186 |
| BNB | 2018-2026 | 84.8 | 67.8 | +9.6 | −22.7 | +33.9 | −1.6 | 72% | −54 | +177 |
| ZEC | 2020-2026 | 28.7 | 59.5 | −21.5 | −23.7 | +4.5 | −2.3 | 60% | −163 | +192 |

Windows start after a 300-bar (crypto 400-bar) warm-up, so they begin later than in
run_full.

- **US indices** (S&P, SPY, QQQ, IWM):
  - Bull phases are 81-85% of the time.
  - The indicator loses 10-20 log pts per bull-year and gains 29-90 per bear-year. On the S&P
    that nets to about −4 pts/yr.
  - Its timing skill on the S&P is negative (−1.7): the days it sits out were on average
    *better* than the days it held. The strictness study found the same for the average S&P
    stock (about −2.2, defined slightly differently).
- **Single growth stocks** (TSLA, COIN, HOOD): bull time is 55-62%, but the drift cost alone
  (−12 to −23) outweighs any timing skill.
- **Crypto:**
  - Bear phases are 28-45% of the time.
  - The median bear-phase decline is −64% (range −50% to −90%; ETH's 2017 phase is left out
    because the window starts inside it), with single saves up to +135%.
  - Timing skill is +27 to +41 log pts/yr on BTC, ETH, SOL and BNB, which pays for the toll.
    ZEC (+4.5) is the exception.
- **Calendar-year view:**
  - Spells exiting in down years net positive in all three pools.
  - Spells exiting in up years net negative on the S&P and its stocks.
  - For coins, only years up more than 30% are negative. Spells in years up 0-30% net +611
    log pts.
  - False breakdowns are 75-86% of the losses in every bucket of the stock and coin pools.
- **This is the payoff profile of section 5.11 seen from the inside.**

## Part B: regime switching (H-B1 to H-B5 all FAIL)

- **SWITCH** = hold while the regime is good, follow the indicator while it is bad.
- **REG** = the regime rule alone (cash when bad).
- **Hindsight** = the ex-post bull/bear phases as the regime. It uses the future; it is a
  ceiling, not a strategy.

Pre-registered basis: pre-tax CAGR (crypto same-bar). After tax and max drawdown are in
brackets:

| asset | BH (tax, DD) | IND | REG 200d (DD) | SWITCH 200d (tax, DD) | SWITCH 50/200 | SWITCH 12-mo | hindsight SWITCH |
|---|---|---|---|---|---|---|---|
| S&P 500 1963-2026 | 10.8 (9.8, −55.5) | 6.2 | 10.5 (−21.6) | 10.3 (7.9, −35.5) | 10.8 | 10.5 | 14.8 |
| SPY 1996-2026 | 10.4 (9.3, −55.2) | 6.8 | 8.7 (−21.7) | 11.2 (8.6, −29.2) | 12.5 | 11.9 | 15.9 |
| QQQ 2000-2026 | 9.0 (8.1, −80.5) | 7.4 | 10.1 (−26.2) | 11.8 (9.2, −50.8) | 12.9 | 12.1 | 20.9 |
| IWM 2001-2026 | 8.6 (7.6, −58.6) | 4.0 | 5.4 (−31.4) | 10.1 (7.5, −36.2) | 7.1 | 10.5 | 18.9 |
| TSLA 2011-2026 | 44.0 (41.9, −73.6) | 33.6 | 19.4 (−71.9) | 27.6 (24.0, −70.1) | 35.7 | 37.3 | 101 |
| BTC 2016-2026 | 63.1 (59.5, −83.8) | 72.1 | 60.6 (−70.8) | 69.2 (56.3, −73.7) | 78.9 | 71.5 | 144 |
| ETH 2017-2026 | 27.6 (24.9, −94.0) | 67.3 | 49.3 (−80.3) | 51.7 (40.3, −81.2) | 46.6 | 34.4 | 151 |
| SOL 2022-2026 | 22.0 (18.5, −79.3) | 43.6 | 32.8 (−58.6) | 42.8 (33.2, −68.9) | 44.5 | 64.3 | 109 |
| BNB 2018-2026 | 67.8 (63.3, −76.1) | 84.8 | 53.3 (−74.3) | 74.3 (62.7, −78.4) | 80.8 | 43.8 | 153 |
| ZEC 2020-2026 | 59.5 (54.3, −94.3) | 28.7 | 3.7 (−95.5) | −0.7 (−3.3, −95.6) | 5.5 | 61.3 | 190 |

**All 23 single assets** (200-day classifier; `partB_all_assets_ma200.csv`):

- SWITCH beats the indicator on every ETF and index (14 of 14, plus the S&P series) and on
  HOOD. It never does on the five coins (pre-tax, same-bar), TSLA or COIN.
- **T2** is the repo's after-tax rule (gate.py): after-tax CAGR ≥ buy & hold, or ≥ buy &
  hold − 2 pts with max drawdown at least 15 pts shallower.
  - SWITCH passes T2 on the S&P series, SPY, QQQ, IWM, DIA, EFA, TLT and VNQ, and on ETH and
    SOL.
  - It fails on EEM, IEF, TIP, LQD, HYG, GLD, SLV, BTC, BNB, ZEC, TSLA, COIN and HOOD.
  - ETH and SOL pass only because their own buy & hold fell so far.
    - On ETH the indicator alone is far better (67.3 vs 51.7 pre-tax; 49.4 vs 40.3 after
      tax).
    - On SOL, same-bar, the two are about equal (43.6 vs 42.8 pre-tax; 31.5 vs 33.2 after
      tax). The indicator is clearly better only via the spot ETF (38.1 vs 26.6 after
      tax).
- Other assets, pre-tax CAGR with after-tax CAGR and drawdown in brackets:

| asset | BH | IND | REG 200d | SWITCH 200d |
|---|---|---|---|---|
| DIA 1999- | 8.4 (7.4, −52) | 5.9 | 4.3 (3.3, −42) | 8.5 (6.4, −30) |
| EFA 2002- | 7.8 (6.6, −61) | 2.5 | 5.9 (4.6, −26) | 5.9 (4.7, −38) |
| EEM 2004- | 8.3 (7.2, −66) | 2.6 | 6.0 (4.6, −43) | 5.4 (4.2, −50) |
| TLT 2003- | 3.1 (2.4, −48) | 1.3 | 2.5 (1.4, −27) | 2.7 (1.6, −33) |
| IEF 2003- | 3.1 (2.5, −24) | 2.3 | 2.3 (1.5, −11) | 2.9 (1.9, −14) |
| GLD 2006- | 9.7 (8.7, −46) | 4.2 | 6.9 (5.6, −35) | 8.1 (6.6, −45) |
| SLV 2007- | 7.8 (6.8, −76) | 6.1 | 4.9 (3.8, −62) | 7.8 (6.0, −62) |
| VNQ 2005- | 6.4 (5.2, −73) | 4.8 | 4.9 (3.6, −30) | 7.3 (5.4, −48) |
| COIN 2022- | 33.5 (28.8, −67) | 6.5 | −6.6 (−7.2, −65) | −0.7 (−3.6, −64) |
| HOOD 2022- | 76.4 (67.9, −57) | 36.5 | 44.1 (37.8, −53) | 51.0 (44.2, −53) |

(TIP, LQD and HYG are in the CSV; same pattern as IEF.)

**Baskets** (pre-tax, equal weight, formed at each year's start; coins same-bar at 0.30%/side):

| strategy | S&P 500 members 1997-2026 | Binance coins 2019-2026 |
|---|---|---|
| BH | 10.9 (DD −58) | 53.7 (DD −83) |
| IND | 5.3 (−29) | 61.7 (−50) |
| REG 200d | 7.3 (−21) | 44.6 (−64) |
| SWITCH 200d (own regime) | 9.1 (−34) | 57.8 (−65) |
| best ex-ante SWITCH | 9.8 (unemployment) | 68.4 (drawdown ≥ 50%) |
| hindsight SWITCH | 15.2 (S&P index phases for every stock) | 195 (each coin's own phases) |

**Verdicts.** Several sit on a knife-edge.

- **H-B1 FAIL.** SWITCH(200d) beats the indicator on 4 of 10 named assets (the four US
  indices) and in the stock basket. It fails on crypto, TSLA and the coin basket.
- **H-B2 FAIL by 0.10 pt.** S&P 500 SWITCH(200d) vs buy & hold after tax:
  - full period: 7.85 vs 9.82 with 20.0 pts less drawdown. It passes, by 0.03 pt.
  - 1994-2026: 8.48 vs 9.88. It passes.
  - 1963-1993: 7.18 vs 9.28. It misses the 2-pt band by 0.10, and its drawdown leg (15.6 pts)
    clears the 15-pt bar by only 0.6.
  - Both the passes and the fail are within the tax-model uncertainty. Read it as about 1.4-2.1
    pts/yr after tax for 16-20 pts less drawdown.
- **H-B3 FAIL by 0.19 pt** (pre-tax).
  - SWITCH ≥ REG held on 8 of 10 named assets. The two misses are the S&P 1963-2026 (10.32 vs
    10.51) and ZEC.
  - The count leg passes, so the hypothesis failed only on its S&P leg. That shortfall comes
    from 1963-1993 (9.7 vs 11.7).
  - Since 1994, and on SPY, QQQ and IWM, SWITCH beat the plain 200-day rule by 1.1-3.4 pts/yr
    after tax, at 5-25 pts deeper drawdown.
- **H-B4 FAIL.**
  - No other price classifier passes H-B2 on the S&P 500.
  - On the S&P 500 1963-2026 every pre-registered ex-ante switch trails buy & hold after tax.
    The best is the 50/200 switch, 8.7 vs 9.8; the sensitivity grid's best is 8.5.
  - On SPY 1996-2026 the 50/200, 9-month and 12-month switches did beat it after tax (10.1 /
    9.5 / 9.6 vs 9.3).
  - On the index, the 50/200 and 12-month switches trail in 1963-1993 (7.9 / 7.5 vs 9.3) and
    narrowly in 1994-2026 (9.5 / 9.5 vs 9.9). The 9-month switch was run only on the full
    window (8.3 vs 9.8). So this is not robust.
  - Volatility and HMM regimes are the worst: SWITCH 5.2 / 5.8 after tax (7.4 / 8.1
    pre-tax).
- **H-B5 FAIL.** Unemployment trend: 9.8 pre-tax, 7.6 after tax.
  - The original Growth-Trend Timing rule (cash only if unemployment is rising AND price is
    below the 200-day) made 11.7 vs 10.8 pre-tax over 1963-2026 (exploratory).
  - After its 2016 publication it made 12.9 vs 15.4 (10.3 vs 13.4 after tax), with no
    drawdown benefit.

**Why the switch doesn't beat holding** (after tax, and on the S&P 500 1963-2026):

1. **US indices.** The switch removes most of the false-breakdown tax. Red spells that start
   above the 200-day lose 4-6 log pts/yr net. The switch adds 3.6-5.5 log pts/yr over the
   indicator (4.1-6.0 CAGR pts in the table).
   - **S&P 500 1963-2026:** below the 200-day, the indicator's red days roughly break even
     against holding.
     - Day by day the switch is −0.2 log pts/yr vs holding (−0.7 in 1963-1993, +0.2 in
       1994-2026).
     - Spells that start below the 200-day net +0.15.
     - What is left is a drawdown benefit with a return cost, i.e. insurance, not an edge.
   - **SPY, QQQ and IWM** (1996 / 2000 / 2001-2026): the same days add +0.9 to +2.7 log
     pts/yr, and the switch beats buy & hold pre-tax by 0.8-2.8 pts.
     - Tax removes that edge on SPY (8.6 vs 9.3) and IWM (7.5 vs 7.6).
     - QQQ stays ahead after tax (9.2 vs 8.1), largely because its window starts at the
       dot-com top. Since 2013 the switch gave up 3.5 pts/yr there.
2. **Crypto.** Saves from red spells that start *above* the 200-day are about as large in
   total as those below. Log pts/yr, above vs below:
   - BTC 20.4 vs 19.4
   - ETH 39.9 vs 35.0
   - BNB 22.1 vs 20.2
   - ZEC 50.0 vs 9.5
   - SOL 21.8 vs 39.6
   - Crashes from a peak (May and November 2021) begin above the 200-day, and the switch
     holds through their first leg. FTX (Nov 2022) began below the 200-day, where the switch
     already follows the indicator.
   - Net effect vs the indicator, day by day: BTC −2.3, ETH −10.5, ZEC −25.5 log pts/yr.
3. **Every ex-ante regime is a slower trend signal.** It recognises a bear market only after
   the damage, and it is wrong at V-bottoms.
   - The hindsight ceiling is large: +4 pts/yr on the S&P, and several times the return on
     crypto. The idea fails on identifying the regime, not on the payoff.

## Exploratory: which index drawdown insurance? (`partB_insurance.csv`)

The question: should index drawdown insurance be the weekly signal (HANDOFF 5.6), a plain
moving-average rule, or the switch? Each cell is give-up vs buy & hold after tax (CAGR pts)
and drawdown saved (pts):

| rule | S&P 1963-2026 | S&P 1963-1993 | S&P 1994-2026 | SPY 1996-2026 | IWM 2001-2026 |
|---|---|---|---|---|---|
| weekly signal alone | 2.6 / 22 ✗ | 1.0 / 24 | 3.7 / 22 ✗ | 4.0 / 20 ✗ | 2.9 / 20 ✗ |
| 200-day alone | 1.9 / 34 | **0.8 / 28** | 2.5 / 34 ✗ | 2.5 / 34 ✗ | 3.5 / 27 ✗ |
| 50/200 alone | 1.6 / 22 | 1.1 / 12 ✗ | 1.6 / 22 | 1.2 / 21 | 5.8 / 8 ✗ |
| SWITCH 200d | 2.0 / 20 | 2.1 / 16 ✗ | 1.4 / 20 | 0.8 / 26 | **0.1 / 22** |
| SWITCH 50/200 | **1.1 / 22** | 1.3 / 12 ✗ | **0.4 / 22** | **−0.7 / 21** | 2.0 / 6 ✗ |

✗ = fails T2: after tax, give-up ≤ 2 pts with at least 15 pts less drawdown, or no give-up
at all. That is stricter than gate.py's INSURANCE rule in HANDOFF 5.6, which is pre-tax,
give-up ≤ 3 pts and ≥ 15 pts saved, on weekly bars. Pre-tax, the weekly signal's give-ups
here are 1.2, −0.6, 2.8, 3.3 and 2.5 pts.

- **The weekly signal is dominated in every window by at least one other rule,** except QQQ
  2000-2012. There it is level with the 50/200 rule: −7.6 vs −7.5 after tax, with 54 vs 58
  pts of drawdown saved.
  - These tests use daily bars and next-session fills, not gate.py's weekly fills or its
    windows.
- **No rule wins every window:**
  - The 200-day rule is best in 1963-1993.
  - The 50/200 switch is best on the S&P since 1994 and on SPY.
  - The 200-day switch is best on IWM.
  - The 50/200 forms cut little drawdown on IWM (and on SPY since 2013).
  - On QQQ the switches cut much less drawdown (30-32 pts) than the weekly signal or the plain
    rules (52-54).
- Since 2013 every rule gave up 1.8-8 pts/yr after tax on SPY and QQQ, for 0-13 pts less
  drawdown. On IWM the 200-day switch cost 0.9.
- QQQ's full window starts at the dot-com top, so every rule looks free there.
- All of this is post hoc.

## Exploratory: crypto by execution route (`partB_crypto_routes.csv`)

After tax, ETF route = next NYSE session at 0.02%/side:

- **ETH** (gate: TRADE via ETF): the indicator alone makes 60.3. Every switch is far lower:
  28-45.
- **BTC** (gate: hold): every switch beats the indicator alone (50.4), at 52-60.5. Only the
  12-month switch reaches buy & hold (60.5 vs 59.6), which is marginal and post hoc.
  - The same-bar 50/200 result (63.2 after tax) does not survive execution: 57.4 on the ETF
    route.
- **SOL, BNB, ZEC:** mixed. The 12-month switch helps SOL and ZEC, the weekly one helps BNB,
  and the others hurt.

## Practical reading

- **US index money.**
  - Holding stays the default in a taxable account. No rule beat it after tax over
    1963-2026.
  - **If drawdown control is wanted, the user's switch is a reasonable form of it.** Hold
    above the 200-day, or while the 50-day is above the 200-day, and follow the daily indicator
    below.
    - Since 1994 (S&P 1994-2026, SPY, IWM) it cost about −0.7 to 1.4 pts/yr after tax for
      20-26 pts less drawdown.
    - The exception is the 50/200 form on IWM: 2.0 pts/yr for only 6 pts, failing T2. On IWM
      use the 200-day form.
    - It is cheaper than the plain 200-day rule and the weekly-signal insurance, but on QQQ it
      cut much less drawdown.
  - **The plain 200-day rule cuts drawdown the most.** Max drawdown is −22% on the S&P and
    SPY, −26% on QQQ and −31% on IWM, at 0.8-3.5 pts/yr after tax (0.8 in 1963-1993; 2.5-3.5
    since 1994).
  - **On SPY and QQQ all these costs rise sharply in a strong bull market:** about 2-8 pts/yr
    in 2013-2026. On IWM the 200-day switch cost 0.9.
  - **In a tax-advantaged account** the costs fall by about 1.5 pts for the switch, and by
    1 pt or less for the plain rules on SPY and IWM.
- **Crypto.**
  - On ETH, the coin the gate trades, keep the indicator alone and add no regime filter.
  - On BTC (hold), the switch improves on the indicator, but no robust version beats
    holding.

**Caveats:**

- Unemployment is the current revised vintage, not real time.
- The Binance list is today's large coins (survivorship, partly offset by LUNA and FTT).
- SOL has 4.1 years after warm-up, yet it is among the 10 named assets.
- 38 early ^GSPC bars have no real high/low.
- H-B2's margins (a 0.03-pt pass over the full period, a 0.10-pt miss in 1963-1993, both
  after tax) are smaller than the tax-model uncertainty.
- H-B3 is pre-tax, so the tax model can't move it, but its 0.19-pt miss is also knife-edge.
- The insurance and route tables are exploratory and were chosen after seeing the
  pre-registered results.


---

# 2026-10-14 (latest) — Ivan's flip-confirmation delay (hourglass "N/5")

`analysis_2026/flip_delay.py`. D1-D3 were pre-registered in b3900d6. Results are in
`analysis_2026/results_delay/`.

**Rule:** the exact indicator, but a flip needs N consecutive closes beyond the still-trailing
line; a close back inside resets the count. N = 1 equals moneyline_ref (asserted).

**Assets:**

- 21 coins
- the crypto top-20 universe incl. dead coins
- 13 ETFs
- the user's names (TSLA HOOD COIN CRCL MSTR NVDA PLTR)
- the point-in-time S&P 500 basket incl. failed companies (2001-2026)
- weekly SPY/QQQ/IWM/BTC/ETH

**Audit:** two lenses. Independent rebuilds reproduced all 3,864 per-asset values and both
baskets exactly, with no look-ahead. Robustness covered alternative delay definitions,
costs, sub-periods, block bootstraps, a reality check over N, and an entry/exit
decomposition.

**Results:**

- **D1 (trades fall with N):** confirmed. SPY flips: 457 at N=1, 201 at N=5, 125 at N=10.
- **D2 (N=5 vs N=1): passes 2 of 3 classes, leaning mainly on stocks.**
  - **S&P 500 basket, robust.** Sharpe 0.53 → 0.70 (0.72 at N=6), CAGR 5.0 → 6.6%, max DD
    −34 → −22%.
    - Bootstrap 95% CI for the Sharpe gain [+0.03, +0.31], p ≤ 0.009; reality check over
      N, p 0.004-0.03.
    - Every definition and every N ≥ 2 helps; both halves; 19 of 26 years; 61% of 969
      stocks improve.
  - **ETFs: PASS but fragile.** Median +0.11 Sharpe, 10/13 improve (sign p 0.046). A joint
    bootstrap keeping ETF correlation gives p 0.06-0.10; Bonferroni over N gives 0.42.
    Direction holds for every N, every definition and both halves.
  - **Crypto: FAIL.** 6/21 coins improve at N=5. The top-20 basket is worse at every N, in
    7 of 8 years and under every definition (Sharpe 1.14 → 0.87 at N=5). Bootstrap p ≈ 0.10,
    so "doesn't help" is robust and "hurts" is likely but not established.
- **D3:** confirmed within each class. Delays cut whipsaws and deepen average losses (crypto
  −11.3 → −14.9%). The fixed 2% whipsaw band exaggerates the gap between classes; the
  volatility-free measure is below.
- **Mechanism:**
  - Immediate flips reverse within 4 bars 10-13% of the time in stocks and ETFs vs 5-6% in
    crypto, so the delay filters more false flips in stocks.
  - A late signal costs about the same in volatility units for both.
  - Crypto entries are followed by right-skewed continuation, so delaying entries is the
    damaging leg there. An exit-only delay is roughly neutral for crypto.
  - ETFs: the entry delay helps. S&P: both legs together are best.
- **Versus buy & hold:**
  - The delay brings the indicator's Sharpe up to about buy & hold's (S&P basket, excess
    over T-bills: 0.515 vs 0.515). On ETFs, N=5 beats B&H Sharpe on only 4/13 on that
    measure.
  - CAGR stays well below: S&P basket 6.6% vs equal-weight B&H 10.9%; ETFs median 3.9% vs
    7.0%.
  - Crypto: the indicator beats B&H at any N; N=1 or 3 is best.
- **Not supported:**
  - "A 3-day delay helps crypto at 0.95%/side" was an N=3 quirk; the basket at 0.95% is
    worse at every N ≥ 2.
  - The 'frozen flip point' check is uninformative: it is identical to the trailing rule
    on all but 20 of ~30M bars.
- **Data caveat:** about a third of early S&P member-days (2001) are close-only
  approximations. Restricting to clean members gives the same improvement (+0.168).

**Practical reading:**

- **Stocks/ETFs:** Ivan's delay (about N=4-6) makes the indicator a better risk reducer:
  half the drawdown at about buy & hold's risk-adjusted return. It still earns less than
  buy & hold.
- **Crypto:** keep the immediate flip (or at most a short exit-only delay).

# 2026-10-14 (latest) — ten strategies chosen for theory, not tested ideas (S1-S10)

`analysis_2026/theory_strategies.py`. S1-S10 were pre-registered in 93bff74
(`analysis_2026/THEORY_PREREG.md`). Results are in `analysis_2026/results_theory/`
(`summary.txt`, `verdicts.csv`, `results.json`).

**Why these:** each has an economic or behavioural mechanism and a peer-reviewed record,
and an individual can run it with ETFs, a few trades a year, or crypto.

**Primary test:** the Sharpe gain over a stated benchmark, using a stationary block
bootstrap (mean block 250 days, 2,000 draws, one-sided), Holm-adjusted across the ten.

**Pass rule:** Holm p < 0.05, AND the Sharpe gain is positive in the pre-registered later or
post-publication sub-period, AND both hold after costs.

**Audit:** three lenses (US market, equity, crypto) each rebuilt their strategies
independently and reproduced every headline number. A confirm stage then re-checked each
serious claim. Three small fixes were applied:

- annualising by actual rows per year, since the Ken French data have Saturday sessions
  before 1953
- S3's signal no longer waits for IEF history, so it is no longer in cash for the first 7
  months of 2003
- stock crashes across trading halts are no longer dropped

None changed a verdict.

| | strategy (benchmark) | Sharpe gain | p | Holm | later sub-period | verdict |
|---|---|---|---|---|---|---|
| S1 | volatility-managed US market 1927-2026 (B&H) | +0.059 | 0.040 | 0.32 | +0.049 (1976+) | FAIL |
| S2 | 10-month SMA filter 1927-2026 (B&H) | +0.082 | 0.19 | 1 | +0.014 / +0.063 (2008+) | FAIL |
| S3 | dual momentum SPY/EFA/IEF 2003-2026 (SPY) | −0.061 | 0.66 | 1 | −0.33 (2015+) | FAIL |
| S4 | low-vol fifth of point-in-time S&P 500 (equal weight) | +0.054 | 0.24 | 1 | +0.022 (2014+) | FAIL |
| S5 | 12-1 momentum fifth of S&P 500 (equal weight) | −0.001 | 0.55 | 1 | +0.052 | FAIL |
| S6 | turn of the month 1927-2026 (B&H) | +0.31 | 0.0035 | 0.032 | −0.09 (1989+), −0.42 (2009+) | FAIL (decayed) |
| S7 | Halloween Nov-Apr 1927-2026 (B&H) | +0.020 | 0.41 | 1 | −0.13 (2003+) | FAIL |
| S8 | crypto indicator × vol target (plain indicator) | +0.007 | 0.38 | 1 | −0.004 (2022+) | FAIL |
| S9 | BTC/ETH cash-and-carry 2019-10..2026-09 (T-bills) | excess +6.5%/yr, NW(20) t 4.59 | 2e-6 | 2e-5 | +0.79%/yr (2023+) | PASS, but see below |
| S10 | crypto 4-week momentum, top 6 of 30 (equal weight 30) | +0.167 | 0.11 | 0.78 | −0.11 (2023+) | FAIL |

**What each fail means:**

- **S1, S2, S4 (risk reducers):** they cut volatility and drawdown as the literature says,
  but they do not raise the Sharpe ratio reliably.
  - Max drawdown: S1 −70 vs −84%, S2 −48 vs −84%, S4 −41 vs −58%.
  - CAGR is 0.5-1.3 points lower pre-tax (S1 9.8 vs 10.2%, S2 9.5 vs 10.2%, S4 9.4 vs
    10.7%).
  - Under the conservative yearly-tax model S1 and S2 trail buy & hold by about 3.5
    points after tax (S1 6.5 vs 10.0%, S2 6.3 vs 9.9%). That model is a bound for the
    strategies, not an estimate. S4's benchmark is taxed the same way, so its gap stays
    0.8.
  - Every S1 variant (21/63-day volatility, monthly/daily updates, lag 0/1) has raw
    p ≥ 0.022. Every S2 variant (8/10/12-month, price or total-return index) has
    p 0.11-0.33. S4 variants land at +0.04 to +0.07, p 0.19-0.31.
  - S1's average exposure is 0.90, not about 1 as the pre-registration's rationale said,
    because the cap is 1.
  - The exploratory S1 with a 1.5 cap: +0.081, p 0.051.
  - The SPY replications are weaker (S1 +0.037, S2 +0.087, both p ≥ 0.30).
- **S3 (dual momentum):** its only gain is 2003-2014, from holding bonds Feb 2008 - Nov
  2009. Every variant and every 2015+ sub-period is negative.
- **S5 (momentum):** zero. Ken French UMD's Sharpe is only 0.15 over 2001-2026.
- **S6 (turn of the month): the textbook decay case.** Significant over the full history,
  but the gain is gone after publication. TOM-day minus other-day return, %/day:
  - +0.156 (t 7.7) in 1927-88
  - +0.087 (t 2.2) in 1989-2008
  - +0.015 (t 0.35) in 2009-26

  2009+ is negative in every window tested (−1..+3, −2..+3, −1..+2, −1..+4, 0..+3), and
  at zero cost too. The SPY replication over 1995-2026 is −0.14. The pre-registration's
  wording reads as both −1..+3 and −2..+3; the code uses −1..+3, and the verdict is the
  same either way.
- **S7 (Halloween):** −0.09 in 1927-59, +0.27 in 1960-2002, −0.13 in 2003-26. The effect
  sits in the sample it was published on.
- **S8:** the vol-targeting overlay barely moves the position. It adds nothing to the
  crypto trend signal, or to crypto buy & hold.
- **S10:** the positive full-period point estimate rests on a few weeks, and its sign
  depends on the lookback. 2023+ is negative; after tax it is −0.3% CAGR with a −98%
  drawdown.

**S9 cash-and-carry passes the pre-registered rule, but the result is marginal and
historical, not investable now.**

- **Mechanics:** long spot plus short perpetual, 1.25× capital. 9.8% CAGR, 1.0% vol, max
  DD −0.7%.
- **Excess over T-bills by year:**

  | 2019 (Q4) | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 YTD |
  |---|---|---|---|---|---|---|---|
  | −3.0% | +17.0 | +26.7 | −0.5 | +0.9 | +4.5 | −0.7 | −2.4 |

  96% of the cumulative excess came from 2020-21.
- **Since 2023:** +0.79%/yr, NW t 1.2, not significant. It turns negative with 1.5×
  capital (−0.10) or 3× costs (−0.23).
- **Since 2025:** −1.40%/yr, NW t −3.4, significantly negative. 2026 gross funding: BTC
  2.9%/yr and ETH 1.9%/yr, with 26-30% of 8-hour prints negative.
- **How significant depends on the HAC bandwidth.** Daily excess is persistent:
  autocorrelation 0.83 at lag 1, 0.43 at 30 days, 0.25 at 90.
  - Still passes Holm:
    - every fixed Newey-West lag up to 102 (90 lags: t 2.65)
    - both automatic bandwidths: Andrews 47 lags, t 3.33; Newey-West 1994, 39 lags, t 3.60
    - the pre-registration's own stationary bootstrap (block 250): Holm 0.025-0.040
  - Fails from 103 lags on (180: t 2.16; 365: t 1.76), and on yearly or monthly means
    (t 1.4-1.7).
  - The audit lens's "Andrews 493 lags, t 1.64" was a formula error, refuted in the
    confirm stage.
- **Margin:** the 25% short margin is liquidated at about +24.5%.
  - With a daily check and a top-up at +10%: 0 liquidations on BTC and 2 on ETH (both
    2021). That costs about 0.06%/yr, inside the cost allowance.
  - With only a monthly reset: 16 BTC and about 32 ETH liquidations, which turns 2023+
    negative (FAIL).
  - So the result needs daily, or at least weekly, margin monitoring.
- **Counterparty risk:** the backtest trades on Binance, an exchange that survived. An
  expected exchange loss of more than about 0.8%/yr of capital wipes out the 2023+ edge.
  It does not erase the full-period edge at any plausible failure rate.
- **Positive-funding-only variant (exploratory):** NW t 4.28 over the full period, but
  2023+ +0.46%/yr and 2025+ −1.78%/yr.

**Interpretation:** we expected 2-4 passes and got 1, and that one has decayed to about
zero. The pattern matches the earlier studies:

- Anomalies with a behavioural or calendar story have weakened or vanished since
  publication (S6, S7).
- Risk-reduction rules (S1, S2, S4) do what they claim, lower drawdowns, but pay for it
  in return, and in taxes when held taxably.
- Structural carry (S9) paid while leveraged-long demand was extreme (2020-21) and has
  been competed away since.

No candidate is a reason to change the user's core holdings.

# 2026-10-15 — 2x S&P + gold (the other instance's 50% SSO / 50% GLD) and variations

**Files:**
- code: `analysis_2026/sso_gold.py`
- pre-registration: `analysis_2026/SSO_GOLD_PREREG.md`, a98a104, written before any pre-2006 run
- first run: 5c90fc7
- results: `analysis_2026/results_sso_gold/`

**Audit:** six independent lenses (C4 rebuild, P3 rebuild with look-ahead truncation tests,
statistics, realism, tax, gold), each serious finding re-checked by a confirm agent. No
verdict changed. The fixes below are applied by default; `audit_fix=False` reruns the
pre-registered data.

**The candidate.** The other instance's C4 (`codex/theory-lab`, `THEORY_LAB_RESULTS.md`):
50% SSO + 50% GLD, rebalanced quarterly.
- 2007-2025: 14.33% vs SPY 10.63%.
- It failed that study's adjusted significance test.
- Replicated here: 14.18%.

**Theory.** 50% in a 2x daily fund is about 1x S&P on half the capital, financed at a
short rate. So C4 ≈ S&P + 0.5 × (gold − T-bill) − costs. It beats the S&P only when gold
beats T-bills by enough.

**Data:**
- **S&P:** SteelCerberus daily S&P total return 1928-2025, spliced to SPY.
- **Gold:** LBMA PM fix, daily from 1968, less 0.40%/yr before GLD, then GLD.
  - It misses the pre-registered correlation threshold: 0.978 vs 0.98, because the fix is
    at 10:00 NY and GLD closes at 16:00.
  - The fallback, World Bank monthly averages, does far worse on that test (0.60) and gives
    the same verdicts.
- **Synthetic 2x fund:** S&P × 2 − financing − 0.89% fee.
  - Financing spread 0.471% over the swap rate, fitted to actual SSO 2006-2021.
  - Monthly tracking vs actual SSO: correlation 0.9996+, error 0.6-0.9%/yr.
  - Since 2021 the synthetic runs +0.37%/yr richer than the real fund (out of sample).
- **Audit data fix:** before 1986 SteelCerberus' 'Swap Rate' is the 1-month bill rounded to
  2.52-point steps (0% in 1933-49), with no bank-funding spread.
  - Now: financing = T-bill + 0.55% before 1986, and unrounded Ken French monthly T-bills
    before 1954.
  - This lowers every leveraged result by about 0.1-0.45%/yr.

**Pre-registered tests, audit-corrected data.** Pre-registered data in brackets.

| | rule | period | edge vs S&P %/yr | p (block 36) | Holm | verdict |
|---|---|---|---|---|---|---|
| P1 | C4 synthetic, out of sample | 1972-2006 | +0.44 [+0.61] | 0.42 | 0.86 | FAIL |
| P2 | C4 synthetic | 1972-2026 | +1.35 [+1.46] | 0.24 | 0.86 | FAIL (first half -0.17) |
| P3 | 2x S&P while above its 200-day average, else T-bills (Gayed-Bilello) | 1929-2026 | +3.90 [+4.21] | 0.003 | 0.014 | **PASS** |
| P4 | C4 with trend filters on both sleeves | 1972-2026 | +1.75 [+1.85] | 0.22 | 0.86 | FAIL |
| P5 | Moneyline with 5-bar delay, 2x | 1963-2026 | −2.05 [−1.87] | 0.93 | 0.93 | FAIL |

**C4 is a gold bet, not an edge.**
- **Exposure regression:** C4 = 0.99 × S&P + 0.51 × gold (R² 0.995), alpha −0.68 (t −2.6)
  to −0.82 (t −4.2) %/yr, i.e. the fund's fee and financing. Rolling 10-year betas never
  leave 0.98-1.02 and 0.49-0.52.
- **By decade:**

  | | 1970s | 1980s | 1990s | 2000s | 2010s | 2020-26 |
  |---|---|---|---|---|---|---|
  | C4 edge vs S&P (%/yr) | +13.6 | −6.7 | −4.7 | +3.8 | +0.8 | +5.0 |
  | gold-fund CAGR | +35.5 | −2.9 | −3.5 | +13.7 | +2.9 | +15.6 |
  | T-bills | 6.8 | 9.2 | 5.0 | 2.7 | 0.6 | 2.9 |

- **Start-date sensitivity:**
  - from 1975 (US gold ownership legal): −1.85%/yr to 2006, +0.01 to 2026
  - excluding 1972-79: about −0.7%/yr
- **Forward scenarios** (C4 edge when gold beats T-bills by g %/yr, historical gold path with
  shifted drift):

  | g (%/yr) | −4 | −2 | 0 | +2 | +4 | +8 |
  |---|---|---|---|---|---|---|
  | 1972-2026 shape | −2.4 | −1.4 | −0.4 | +0.6 | +1.6 | +3.6 |
  | 1982-2026 shape | −2.7 | −1.7 | −0.8 | +0.2 | +1.2 | +3.2 |

  Break-even: gold must beat T-bills by about 0.8-1.5%/yr. Historical g: 3.5 (1972-2026) and
  1.2 (1982-2026). Gold's own path adds ±2.5-3%/yr of noise over 10 years.
- **Gold is historically expensive:** the real price is at the 98.7th percentile of 1968-2026
  and about 1.2x the 1980 daily peak. A regression of next-10-year return on real price is
  not a usable forecast: the level is out of sample, the slope is not significant against a
  random walk, and out-of-sample R² is negative. Only the descriptive facts are reported.
- **Actual funds, 2006-07..2026-09:**

  | | CAGR | max DD |
  |---|---|---|
  | C4 | 14.50% | −48% |
  | SPY | 11.26% | −51% |
  | SPY/GLD 50/50 | 11.03% | −26% |
  | SSO alone | 15.51% | −81% |
  | synthetic C4, same months | 14.53% | |

- **Live evidence:**
  - **WisdomTree GDE** (90% S&P + 90% gold futures, from 2022-03): 27%/yr vs SPY 14.7%.
    0.9 SPY + 0.9 GLD − 0.8 T-bills reproduces it almost exactly (2024: 44.76% vs 44.75%;
    2025: 73.85% vs 73.80%), so its outperformance is the gold boom. GLD then fell 26% from
    the 2026-01-29 peak to July.
  - **HFEA**, the bond analogue (55% UPRO / 45% TMF), lost about 64% in 2022.
- **Variations on C4** (1972-2026, edge %/yr):
  - Bonds instead of gold: long Treasuries +0.28, 10-year +0.12. Leverage itself adds nothing.
  - 2x + cash 50/50: −0.92.
  - More gold or less gold only scales the gold bet.
  - Rebalancing frequency: annual +1.75, quarterly +1.35, monthly +1.01, 5-point band +1.07,
    never +0.31.
  - A gold 10-month trend filter (+2.29) helped before 2000 (avoiding the 1980-2001 gold
    bear) and cost about 1%/yr since. Every length shows the same split, so it is regime
    noise.
  - **GDE-style 90/90:** +2.84 pre-tax, but its gold-futures gains are ordinary income each
    year (Subpart F; GDE paid about 4-7% of NAV in 2024-25). After tax 10.30% vs S&P 10.17%.
- **P4** (both sleeves trend-filtered) is a risk reducer: Sharpe 0.64 vs 0.48, max drawdown
  −30% vs −55%. Its edge is not significant, and after tax it is 9.74% vs 10.17%.

**P3: passes, but read it carefully.**
- **Headline:** 14.27% vs 9.89% CAGR, 1929-2026. Vol 23.4% vs 18.4%, Sharpe 0.55 vs 0.42,
  max drawdown −79% vs −84% (1929-32).
- **Robustness:**
  - ahead of the S&P in 93% of rolling 10-year windows
  - positive from every start year 1972-2010
  - holds under every financing model: rate-dependent fit 3.84, testfol.io-style punitive
    3.33, DIY futures/box 4.88
- **Pre-1928 Dow, a disjoint sample:** +3.54%/yr (p 0.009), robust to average lengths
  50-300.
- **Real SSO, 2006-2026:** 13.70% vs 11.26%. Across execution conventions the range is
  12.6-15.2%.
- **No look-ahead:** truncation tests at 21 cut dates gave identical decisions.
- **Mechanism, 1929-2026:**

  | | share of days | return | vol | Sharpe | 2x growth |
  |---|---|---|---|---|---|
  | above the 200-day average | 68% | 13.9%/yr | 14.5% | 0.73 | 18.3%/yr |
  | below | 32% | 5.9%/yr | 25.2% | 0.09 | −6.5%/yr |

  Leverage pays only in calm uptrends. In 2016-2026 the 'below' days returned 23.6%/yr
  (V-shaped rebounds), which a filter misses.
- **The caveats the audit established:**
  1. **Era.** The 1929-1971 slice gives +5.68 (p 0.011); 1972-2026 gives +2.51 (p 0.028
     with block 36, 0.084 with block 12). Fresh starts where it could be traded:

     | start | edge %/yr | p |
     |---|---|---|
     | 1975-05 (negotiated commissions) | +1.78 | 0.11 |
     | 1982-05 (S&P futures) | +2.73 | 0.03 |
     | 1993 (SPY) | +2.29 | 0.10 |
     | 2006 (SSO) | +2.19 | 0.13 |
     | 2016 (after publication) | +3.07 | 0.09 |

     None survives the five-test Holm correction. The Sharpe gain since 1975 is zero to
     slightly negative: more return for more risk, not better return per unit of risk.
  2. **Implementability.** Before 1975 there were no index funds, futures or leveraged funds,
     and commissions were fixed at about 1% one-way by the late 1960s. Charging 2x a
     per-side stock cost on switches before 1975-05:

     | cost per side | edge %/yr | p |
     |---|---|---|
     | 0.10% | +3.42 | 0.008 |
     | 0.25% | +2.68 | 0.03 |
     | 0.50% | +1.46 | 0.17 |
     | 1.00% | −1.02 | |

  3. **Inference.** The pre-registered 36-month block suits P3, whose active returns
     mean-revert over 1-3 years:
     - Ibragimov-Mueller with 12 groups: p < 0.0001; all 12 eight-year groups positive.
     - With iid or 12-month blocks: p 0.019 / 0.012, Holm about 0.06-0.10.
     - Newey-West t 1.98 (12 lags).
     - The weakness under short blocks is 1929-33; 1934-2026 gives p 0.0002.
  4. **Timing.** Edge by execution lag 0-6, 1929-2026: 4.21 / 3.90 / 3.18 / 2.81 / 3.46 /
     3.43 / 3.56. From 1972 only lag 1 has p < 0.05. 70% of the lag-1-vs-2 gap is
     1987-10-19: on 10-15 the S&P closed 0.17% below its 200-day average, so lag 1 exited at
     the 10-16 close and lag 2 held 2x through −41%. Next-open execution 1995-2026: +2.21 vs
     +2.91 at close t+1 (+2.62 vs +2.19 from 2006, +1.56 vs +3.07 from 2016). A saw-tooth of
     noise, not bias.
  5. **SMA length.** Post-1972 the edge is negative for every length ≤ 130 days. 200 days
     ranks 3rd of 40 lengths, and only 5 of 40 have p < 0.05.
  6. **Tax.** 1972-2026, after-tax edge vs S&P:

     | taxes | edge (points/yr) |
     |---|---|
     | registered federal 35/20 | +0.56 |
     | + 3.8% NIIT (consistent for a 35%-bracket investor) | +0.29 |
     | + NIIT + 5% state | +0.01 |
     | + NIIT + 9.3% state | −0.23 |
     | held for heirs (no final sale) with NIIT | −0.01 |

     Over 1929-2026 the edge stays +0.9 to +2.3. Wash sales are negligible (−0.02).
     Short-term rate at which P3 ties the S&P, 1972-2026: about 47%.
  7. **Multiple testing.** This repo has run about 44 pre-registered primary tests. P3 passes
     false-discovery control (q about 0.03) but not a strict project-wide Bonferroni bound.
     Across the 68-variant grid (1972-2026) the best variant (3x + 200-day) has
     reality-check p 0.25.
- **Behaviour:**
  - about 6 switches a year
  - median stay invested 6 days; 59% of stays last 10 days or less
  - trails the S&P by more than 10 points in 18 of 97 years: 2000 −34 vs −10, 2015 −22 vs
    +1, 2022 −30 vs −18
  - worst year −43% (1932)
  - max drawdown since 1972 −44%; the 3x version −63% to −93%

**Moneyline on leverage fails in every form.**
- daily N=1: 5.1%; N=5: 9.0%
- weekly: 11.5% (2x) vs S&P 11.1%, with a −65% drawdown

The fast ATR stop whipsaws a 2x position to death; only slow filters (150-300 days) work.

**Practical reading:**
- **C4:** do not expect it to beat the S&P. It is S&P plus half a gold-vs-cash bet, at a
  record real gold price.
- **P3:** the only rule in this repo that beat buy & hold in a pre-registered, audited test,
  but:
  - the evidence is strongest where it could not be traded
  - in tradable eras it is +2-3%/yr and not significant after correction
  - since 1975 it does not improve risk-adjusted return
  - in a taxable account at top rates the edge is about zero
  - if used at all: a tax-advantaged account, a modest allocation, a slow filter (200-day,
    perhaps a 2-3% band), and acceptance of whipsaws and multi-year underperformance

# 2026-10-15 (later) — buying bounces at moving averages ("key levels")

**The user's question:** HOOD has been falling. On 2026-10-15 it touched its 200-day SMA near
95 and quickly bounced to about 101. Does buying such touches work across our assets? And on
which averages (daily, weekly or monthly, of what length)?

**Code and data:**

- `analysis_2026/ma_bounce.py`, about 7 minutes per run.
  - `--null 16` adds the no-edge simulation for the 200-day (about 30 minutes).
  - `--null 8 --mas ...` adds it for other averages.
- Outputs go to `analysis_2026/results_bounce/`; the event parquets are gitignored.
- Data comes from the same sources as the regime study (`python3 -m analysis_2026.fetch_regime_data`).
- The pre-registration is the module docstring, committed in c8eceed before any event statistic
  was computed.

**Design:**

- **Two claims hide in "buy the bounce at a key level".**
  - (i) Price tends to rise after it pulls back to the average.
  - (ii) The average itself is special, i.e. support: touching it beats touching any nearby
    price.
  - Claim (ii) needs placebo lines: the same average shifted ±1 and ±2 ATR, traded with
    identical rules. ATR is the 14-day Wilder average true range, a volatility ruler.
    Osler (2000) used this design for published FX support levels.
- **Touch:** the previous 10 closes were above the line, and the day's low reaches it.
  - Lines are known at the open: daily averages run through t−1, and weekly and monthly
    averages use completed periods only.
  - *First touches:* no touch of the same asset, average and line in the previous 28 calendar
    days.
- **34 averages:** SMA and EMA of 20/50/100/150/200 days, 10/20/30/40/50/100/200 weeks and
  6/10/12/20/24 months.
- **Entries:**
  - E1 (registered): a limit order at the line, filled at min(open, line).
  - E2 (exploratory): buy after a close at or above the line. Crypto buys at that close,
    stocks at the next open.
- **Exits:**
  - The holding period H is 20 trading days (crypto 28 calendar days). 5/60 (crypto 7/84)
    are also reported.
  - X2, the tradable variant, sells early at the first close more than 1 ATR below the line.
  - Costs: 0.03% per side for stocks, 0.30% for crypto.
- **Pools:**
  - 1,062 S&P 500 members, 1996-2026, point in time, including dead companies. A touch counts
    only while the stock is a member.
  - 41 Binance series of 40 coins, 2017-2026. FTT is split at its 2022-23 delisting gap, and
    old LUNA and Terra 2.0 are kept apart.
  - Single assets: the S&P 500 1962-2026, 14 ETFs, TSLA, COIN, HOOD, BTC, ETH, SOL, BNB and ZEC.
- **AR (abnormal return):** the trade's log return over H minus a baseline.
  - *Same-year drift* (registered): the asset's mean H-day return in that calendar year.
  - *Leave-out drift:* the asset's mean H-day return over all its days, excluding windows that
    start in [t−272, t+H]. For the member pool, only member days count.
  - *Pool:* the equal-weight pool mean over the same window (S&P members on member days; the
    41 coin series for crypto).
  - The same-year and leave-out columns start at the fill and are net of costs (0.06 / 0.60
    pts round trip). The pool column runs close to close from the touch day, gross.
- **Statistics:**
  - A month-block bootstrap resamples all of a month's touches together. 3-month blocks are
    reported as well.
  - P-values are one-sided.
  - FDR = Benjamini-Hochberg false-discovery rate across the 34 averages.
  - "Within the same month" (post hoc): each month's real-line mean minus that month's
    placebo-line mean, weighted by the real-line count, months resampled. This removes timing,
    i.e. real and placebo lines being touched in different markets.
- **Pre-registered tests.** The primary spec is the daily 200-day SMA, E1, H, same-year drift.
  - B1/C1, bounce: AR > 0.
  - B2/C2, key level: real minus placebo > 0.
  - B3/C3, tradable: the X2 trade is > 0 and beats the placebo lines.
  - B4/C4, trend: touches of a rising 200-day beat those of a falling one.
  - B5/C5, grid: the 200-day passes B2, and at least a third of the 34 averages pass the
    key-level test at 10% FDR.
  - B1-B3 also require the effect in both halves of the sample.

**Audit and verification.**

- **First audit:** four lenses with skeptics confirmed 17 findings.
- **Two verification passes on this write-up,** each lens checked by a skeptic:
  - the first confirmed 48 of 59 findings, mostly wording plus two code issues;
  - the second confirmed 16 of 24, including the timing and 2009 caveats below and one more
    code issue.
- All are fixed. Every post-registration change is listed under AUDIT CORRECTIONS in the
  docstring. The registered verdicts are still computed as registered.
- **The pre-registered baseline is biased by event selection.** Its calendar year includes the
  months whose decline produced the touch. Hence the leave-out and pool baselines, and a
  no-edge simulation: each asset's own daily bars are resampled iid, with the same dates,
  members and code, so nothing is predictable. The simulation shows what each baseline reports
  when there is no edge.
- **Dead assets are valued at their last close everywhere: in the event columns and in the
  pool benchmark itself.**
  - The verification passes found that both still dropped them: the benchmark lost a dying
    series in its last 20 (crypto 28) bars, so it "knew" which assets were about to vanish.
  - Fixing the benchmark moves the stock figures by about 0.01 pts. It moves the crypto pool
    bounce from −2.34 (CI −6.00 to −0.05) to −2.18 (CI −5.71 to +0.02).
  - Old LUNA's May-2022 collapse puts about ten touches at about −14 in log terms into the
    crypto windows, one on the real line and the rest on placebo lines.
  - The 200-day crypto results and the crypto grid are therefore also shown without old
    LUNA.
- **Other fixes:**
  - EMAs are seeded with an SMA. The first-close seed had been off by up to 40% on long
    weekly/monthly EMAs.
  - A documented 60-row minimum replaces an undocumented 260-row filter (8 more stocks).
  - Bootstrap differences are now NaN-safe.
  - New checks: chart lines, first touches, 3-month blocks, CIs and effective sample sizes.
- **Stated limits:**
  - 1996-2000 covers only about 80% of member-days, because 157 early dead symbols have no
    prices.
  - The halves are 1996-2011 / 2012-2026 for stocks and 2018-2022 / 2023-2026 for crypto.

**Results: all ten pre-registered tests FAIL.**

*S&P members, daily 200-day SMA, 20 trading days (41,543 touches; values in % or pts):*

| | same-year drift (registered) | leave-out drift | pool (gross) |
|---|---|---|---|
| bounce (B1) | −0.09 (p 0.57) | −0.24 (p 0.73) | +0.07 (p 0.25) |
| 95% CI | −0.84 to +0.53 | −1.00 to +0.42 | −0.12 to +0.24 |
| effective n | ~740 | ~770 | ~7,000 |
| no-edge (null) level | +0.22 | 0.00 | −0.02 |
| real − placebo (B2) | −0.07 (p 0.92) | −0.09 (p 0.95) | −0.04 (p 0.83) |
| 95% CI of real − placebo | −0.19 to +0.03 | −0.21 to +0.02 | −0.14 to +0.05 |
| real − placebo within the same month (95% CI) | −0.11 (−0.20 to −0.01) | −0.13 (−0.23 to −0.03) | −0.06 (−0.15 to +0.03) |
| first touches (n 23,495): bounce / real − placebo | −0.16 / −0.13 | −0.30 / −0.15 | +0.03 / −0.05 |
| rising − falling 200-day (B4) | +0.41 (p 0.17) | +0.60 (p 0.09) | +0.30 (p 0.08) |
| B4 null level | −0.31 | +0.08 | +0.05 |
| B4 minus its null level | +0.72 (p 0.05) | +0.52 (p 0.13) | +0.25 (p 0.12) |

- **Halves (1996-2011 / 2012-2026):** B1 −0.16 / −0.02; B2 −0.11 / −0.04.
- **B3:** the X2 trade makes −0.26% per trade (p 0.97; halves −0.42 / −0.11) and trails the
  placebo lines by 0.13 pts. Against the leave-out drift it makes −0.20%.
- **B4 with the X2 exit,** measured from its null level: +0.01 (same-year) and −0.12
  (leave-out). The trend tilt appears with the 20-day time exit only.
- **B5:** 0 of 34 averages pass. None passes under the leave-out or pool baselines either.
- **Within the same month the 200-day line does slightly *worse* than the placebo lines**
  (−0.06 to −0.13; −0.15 with the X2 exit and leave-out drift, CI −0.25 to −0.06). This is
  post hoc. If anything, the average is a slightly worse place to buy than a nearby price.
- **Effective n:**
  - Touches cluster in market-wide sell-offs. Against the asset's own drift, 41,543 touches
    in 369 months carry the information of about 740-770 independent ones.
  - Against the pool the market move cancels, and the effective n is about 7,000.
  - A bounce edge over the market of more than about 0.25 pts per 20 days is ruled out.

*Crypto, daily 200-day SMA, 28 days (1,055 touches, 41 series):*

| | same-year drift (registered) | leave-out drift | pool (gross) |
|---|---|---|---|
| bounce (C1) | −5.62 (p 0.99) | −3.67 (p 0.93) | −2.18 (p 0.97) |
| 95% CI | −10.49 to −0.90 | −8.82 to +1.13 | −5.71 to +0.02 |
| no-edge (null) level | −0.28 | +0.38 | +0.34 |
| real − placebo (C2) | +1.54 (p 0.16) | +1.48 (p 0.19) | +0.73 (p 0.30) |
| real − placebo within the same month | +2.59 (p 0.04) | +2.26 (p 0.06) | +0.50 (p 0.34) |
| rising − falling (C4) | −1.37 (p 0.64) | +1.30 (p 0.36) | −2.50 (p 0.85) |
| without old LUNA: bounce | −4.48 (CI −8.13 to −0.37) | −2.38 (CI −6.32 to +2.20) | −1.05 (CI −2.51 to +0.24) |
| without old LUNA: real − placebo | −0.24 (p 0.59) | −0.31 (p 0.61) | −0.88 (p 0.89) |
| without old LUNA: real − placebo within the same month | +1.10 (p 0.16) | +0.78 (p 0.24) | −0.86 (p 0.89) |
| first touches (n 439): bounce / real − placebo | −5.31 / +0.28 | −3.64 / 0.00 | −3.03 / −0.19 |

- **C3:** the X2 trade makes −3.75% per trade (p 0.97). Against the placebo lines it is +0.45
  (p 0.34). Without old LUNA: −4.65 / −2.20 per trade, and −0.18 vs placebo.
- **C5:** 0 of 34 averages pass.
- **Old LUNA dominates the crypto contrasts.**
  - Its collapse adds about ten touches worth about −14 log units each, most of them on
    placebo lines.
  - That turns real minus placebo from −0.2 to +1.5 (same-year), and the nominal same-month
    +2.6 (p 0.04) falls to +1.1 (p 0.16) without it.
  - It moves C4 from +0.2 to −1.4, and it inflates the iid SE: the effective n is about 430
    with LUNA and about 145 without.
- **How to read it:** coins that touch their 200-day from above show no bounce.
  - They trail their own drift by 2-6 pts over 28 days, and the coin pool by about 1-2 pts.
  - Without LUNA, only the registered baseline's CI excludes zero.
  - The coin pool's own next 28 days after these touches averaged 1.7 pts below normal (CI
    −5.8 to +2.6). Whether the weakness is market-wide cannot be told.
- **Crypto null:** under the registered baseline, iid bars give a placebo-line gradient from
  +1.02 at −2 ATR to −2.11 at +2 ATR. That is about 45% of the actual gradient without LUNA
  (−0.92 to −7.82).

*Placebo lines, S&P members, 200-day, 20 days:*

| baseline | −2 ATR | −1 ATR | real | +1 ATR | +2 ATR |
|---|---|---|---|---|---|
| same-year drift (actual) | +0.25 | +0.05 | −0.09 | −0.10 | −0.20 |
| same-year drift (null) | +0.72 | +0.51 | +0.22 | −0.05 | −0.33 |
| leave-out (actual) | −0.40 | −0.36 | −0.24 | −0.00 | +0.11 |
| leave-out (null) | +0.02 | +0.05 | 0.00 | −0.02 | −0.05 |
| pool (actual) | −0.05 | +0.01 | +0.07 | +0.18 | +0.26 |
| pool (null) | 0.00 | +0.02 | −0.02 | −0.01 | +0.01 |

- **The registered baseline shows "deeper is better",** but the null has the same slope, only
  steeper, so the pattern is mechanical.
- **Under the unbiased baselines the order reverses:** touches of lines above the average beat
  touches of lines below it.
  - Lines above minus lines below: +0.44 pts under leave-out (p 0.002), +0.24 under the pool
    (p 0.002), and +0.35 with the X2 exit (p < 0.001).
  - Part of the leave-out gap is timing: below-line touches land in months when the market
    kept falling. Within the same month the gaps are +0.10 (leave-out, p 0.13), +0.10 (X2,
    p 0.05) and +0.22 (pool, p 0.003; CI +0.06 to +0.39).
  - This is post hoc, but the pool version is clear. It fits trend persistence (a shallower
    pullback means a stronger trend), not support.
- **Crypto is mixed and never significant.**
  - At 28 days it runs the other way: −2.2 (leave-out) and −1.4 (pool); without LUNA −1.3
    and −0.6.
  - With the X2 exit it runs the same way as stocks: +1.6 (p 0.22); without LUNA +1.35
    (p 0.25).

*The grid (S&P members, 20 days):*

| averages | same-year (registered) | leave-out | pool |
|---|---|---|---|
| short: 20-50-day, 10-week | −0.53 to −0.66 | −0.17 to −0.29 | +0.01 to +0.08 |
| long: 100-200-week, 20-24-month | +0.25 to +0.67 | −0.21 to −0.01 | −0.00 to +0.17 |

- **Both the bad short averages and the good long ones come from the registered baseline.**
  The baseline follows the path that led to the touch:
  - the same-year drift is depressed in years with a long decline to a 2-4-year average;
  - it is elevated in the strong years in which brief dips to a 20-day average happen.
- **Under the leave-out drift every average except W-EMA20 (+0.01) is negative.**
- **The market itself does not rebound after these touches.** The member pool's next 20 days
  are 0.04-0.25 pts below its average after touches of every one of the 34 averages, none
  significantly (`market_after_touches.csv`).
- **The no-edge simulation on 8 averages reproduces the pattern** (`null_grid_summary.txt`;
  D-SMA20, D-SMA50, W-SMA10, W-SMA100, W-SMA200, W-EMA100, M-SMA20, M-SMA24; 8 runs).
  - With no edge, the registered baseline reports −0.30 to −0.51 for the three short averages
    and +0.66 to +1.05 for the five long ones.
  - The leave-out baseline (−0.08 to +0.13) and the pool baseline (−0.06 to +0.05) stay near
    zero.
  - Measured from their no-edge levels, all 8 averages are negative under the same-year
    (−0.06 to −0.38) and leave-out (−0.07 to −0.31) baselines, and −0.03 to +0.16 against
    the pool.
  - The crypto rows of that file are too noisy at 8 runs to use.
- **Real minus placebo:** −0.17 to +0.17 against the leave-out drift, and −0.09 to +0.12
  against the pool.
  - Nominal p < 0.05: four averages under leave-out (D-EMA100, W-EMA20, W-EMA100, M-EMA24),
    one under the pool (W-EMA100) and three under same-year (W-SMA100, W-EMA100, M-EMA24).
  - That is about what 34 tries per baseline produce by chance. None survives FDR.
- **Crypto grid** (`grid_crypto.csv`; without old LUNA, whose collapse sits in the real-line
  touches of most averages, in `grid_crypto_without_luna.csv`; that version in brackets):
  - every average is negative against the same-year drift: −0.6 to −13.2 [−0.3 to −7.3]
  - against the leave-out drift all but D-EMA20 (+0.3 [+0.2]) are negative
  - against the pool the range is −6.9 to +1.7 [−1.5 to +1.7]
  - key level: nothing is nominally significant with LUNA. Without it, M-SMA20 against the
    leave-out drift is +2.33 (p 0.04). Nothing survives FDR.
  - the coin pool's next 28 days after touches range from −5.2 to +0.2 pts vs average,
    mostly negative, none significant on its own

*Chart lines (exploratory).*

- The member pool's OHLC is dividend-back-adjusted, so its averages sit about 0.25 ATR (median
  over member days) below the chart averages traders see.
- Only 61% of chart-line 200-day touches are also pool touches.
- Rerunning the daily averages on chart prices (returns still total return):
  - B1 −0.13% (p 0.62); B2 −0.07% (p 0.90)
  - leave-out −0.22 / −0.09
  - pool +0.04 / −0.07
  - no daily average passes FDR
- The ETF, index, single-stock and crypto runs already use chart lines.

*Exploratory splits (S&P members, 200-day, real line, 20 days).* E2 = bought after the close is
known.

| split | n | E1 (registered) | E2 same-year | E2 leave-out | pool |
|---|---|---|---|---|---|
| closed back above the line | 19,094 | +1.14 | −0.19 | −0.26 | +0.06 |
| closed below the line | 22,449 | −1.14 | — | — | +0.08 |
| closed 1+ ATR above (strong bounce) | 2,057 | +3.61 | −0.42 | −0.26 | +0.40 (p 0.025) |
| ≥ 60 closes above before the touch | 18,560 | +0.06 | −0.16 | −0.13 | +0.22 (p 0.07) |
| lone average (no other within 0.25 ATR) | 1,226 | +0.08 | +0.96 | +1.24 | +0.53 (p 0.05) |
| 4+ of the 34 averages within 0.25 ATR | 29,494 | −0.08 | −0.19 | −0.32 | −0.02 |
| 20-40% below the 52-week high | 4,207 | −0.40 | −0.55 | −0.36 | −0.33 |

- **Read the E1 rows split by the day's close with care.** E1 fills at the line, earlier in the
  day, so those rows contain the day's own move. Judge them by E2.
- **Strong bounces:**
  - +0.40 against the pool, from the bounce close (one-sided p 0.025).
  - Recomputed outside the module (not in the result files): bought at the next open they
    gained +0.43 against the pool (gross; +0.37 net of costs; p 0.02; the pool's window
    starts at the bounce close), against +0.03 for all touches that closed back above the
    line. Against the leave-out drift they made −0.26 to −0.29 from either entry (net of
    costs).
  - The sign follows the baseline, not the entry.
  - This is one of 40 split rows, each read several ways.
- **Confluence did not help.** If anything, a lone average did better than a stack of them.
- **Crypto splits are negative almost everywhere.** The exceptions:
  - E1 rows that contain the day's own move
  - the near-zero-depth row (E1 +1.45, n 10)
  - a few small pool-adjusted rows
  - strong bounces against the leave-out drift (+1.07, n 59, p 0.42; the same trades are
    −2.05 against the same-year drift and negative against the pool)

*HOOD-like analog.* S&P members with 60-day vol ≥ 50%, ≥ 20% below the 52-week high, a falling
200-day and ≥ 20 closes above it before the touch: 234 touches in 75 months, 131 of them first
touches. 20 days:

| entry | same-year | leave-out | pool | null (same-year / leave-out / pool) |
|---|---|---|---|---|
| E1, real 200-day | +1.59 (CI −2.8 to +5.3) | +2.25 (CI −2.8 to +6.4) | +0.97 (CI −1.8 to +3.5) | +0.28 / −0.31 / −1.25 |
| E1, placebo lines | −0.45 | −1.23 | −0.58 | +1.03 / +0.18 / −0.68 |
| E2, real 200-day (n 106) | +1.88 (CI −3.2 to +7.3) | +2.85 (CI −2.8 to +8.5) | | −0.81 / −1.29 |
| E2, strong bounce (n 6) | +4.28 (CI −4.3 to +19.3) | +5.88 (CI −2.1 to +20.0) | | |
| E1 without 2009 (n 161) | −1.43 (CI −6.0 to +2.9) | −1.58 (CI −6.4 to +2.7) | +0.27 (CI −3.3 to +3.7) | |
| E2 without 2009 (n 69) | −1.29 | −1.09 | | |

- **The positive lean against the stock's own drift is one episode.** 73 of the 234 touches are from 2009, 70 of them in the
  May-November rebound; they averaged +8.25 / +10.70 / +2.52.
  - Dropping any other single year keeps the means positive.
  - Dropping 2009 turns the same-year and leave-out means negative.
  - Against the pool, dropping 2009 leaves +0.27 (CI −3.3 to +3.7). That is still about 1.5
    above the analog's pool no-edge level (−1.25; p 0.19 against it, vs 0.06 with 2009).
    The no-edge level comes from the volatility filter rather than from 2009, so the lean
    against the market shrinks but does not vanish. It is not significant either way.
  - The 60-day leave-out mean falls from +6.10 to +0.01.
- **The analog's null is noisy.** The SE of a 16-run mean is about 0.4. Earlier audit runs of
  the same filter gave +0.7 to +1.3 for E1 against the same-year baseline.
- **The pool null is negative here.**
  - It comes mainly from the 60-day-vol ≥ 50% filter. Returns are in logs, and stocks that
    volatile have a lower mean log return than the pool (volatility drag), although their
    arithmetic drift is no lower.
  - Within the volatile subset, a falling 200-day deepens it. A falling 200-day alone gives
    about 0.
- **Real minus placebo inside the analog** (`hood_analog_vs_placebo.csv`):

  | entry | same-year | leave-out | pool |
  |---|---|---|---|
  | E1 | +2.04 (p 0.11) | +3.48 (p 0.03) | +1.55 (p 0.11) |
  | E1 within the same month | +0.58 (p 0.29) | +1.11 (p 0.19) | +0.90 (p 0.20) |
  | E2 | +2.44 (p 0.15) | +4.13 (p 0.05) | |
  | E2 within the same month | −0.63 (p 0.63) | +0.29 (p 0.44) | |
  | first touches, E1 | +1.00 (p 0.26) | +2.19 (p 0.09) | +0.85 (p 0.24) |
  | first touches, E1, within the same month | −0.04 | +0.04 | +0.31 |

  - Much of the raw gap is timing. 13% of the placebo-line touches fall in the 2008 crash,
    against 4% of the real-line ones. 31% of the real-line touches fall in the 2009 rebound,
    against 22%.
  - The null differences (all touches) are −0.75 / −0.49 / −0.57 for E1 and −1.09 / −0.85 for E2. None were simulated for first
    touches or within months.
  - Adding them back to the within-month gaps leaves about +1.33 / +1.60 / +1.47 (p 0.11 /
    0.08 / 0.08; `null_tests.txt`).
  - With the X2 exit the real line does not beat the placebo lines: −0.23 (same-year) /
    +0.70 (leave-out), p 0.50 / 0.27 against their null levels; within the same month −1.22 /
    −0.73 (`null_tests.txt`).
- **This is the only place the 200-day line looks special, and much of it is timing.** It is
  one exploratory subset among many, from 75 months: a weak hint at most.
- **HOOD's own record:** 15 touches of its 200-day from Nov 2022 to Jul 2026, 8 of them first
  touches.
  - Over 20 days: −4.46 (same-year), −3.76 (leave-out), −3.73 (pool). Individual results run
    from −31% to +39%, and 4 of 15 beat the same-year drift.
  - Over 60 days: +14.04 / +20.27 (9 of 15 positive), mostly from the two April-2025 touches.
    Its placebo lines did about as well over 60 days (+11.2 / +21.9), and better over 20
    days (+2 to +4 against the pool).

*Single assets, 200-day touches, 20 days (small n; exploratory).*

- **Reading the pool column:** for indices, ETFs and stocks it is the asset minus the
  equal-weight S&P member average, i.e. cap-weighted vs equal-weight for the indices, not a
  bounce. For coins it is the coin minus the coin pool.
- **Same-year / pool:**
  - SPY +0.40 / +0.81 (n 77)
  - S&P 1962-2026 −0.14 (n 150); since 1996 −0.04 / +0.79 (n 71)
  - QQQ +0.93 / +1.51 (n 60)
  - IWM −0.38 / +0.42
  - TSLA +0.23 / −1.08 (n 52)
  - HOOD −4.46 / −3.73 (n 15)
  - COIN −13.6 / −12.7 (n 13)
  - BTC −4.80 / +1.14 (n 22)
  - ETH −0.94 / −0.46 (n 27)

*Backtests (exploratory).* Non-overlapping X2 trades on 200-day touches, full equity per trade,
T-bills otherwise:

| asset | from | trades | invested | CAGR | max DD | buy & hold CAGR | buy & hold max DD |
|---|---|---|---|---|---|---|---|
| S&P 500 | 1962 | 87 | 6% | 5.4% | −13% | 11.0% | −55.5% |
| SPY | 1995 | 46 | 6% | 4.1% | −8% | 10.6% | −55% |
| QQQ | 2000 | 33 | 4.5% | 1.6% | −32% | 9.4% | −83% |
| IWM | 2001 | 49 | 9% | 3.6% | −12% | 8.9% | −59% |
| TSLA | 2011 | 30 | 6% | −1.2% | −53% | 41.1% | −74% |
| HOOD | 2022 | 8 | 6% | 8.9% | −18% | 71.2% | −57% |
| BTC | 2018 | 12 | 5% | −0.1% | −36% | 31.2% | −77% |
| ETH | 2018 | 13 | 5% | −7.3% | −61% | 19.0% | −90% |

- **Across the 50-day, 200-day, 40-week and 10-month versions** (`backtests_named.csv`),
  bounce-buying is invested 3-17% of the time.
- **It trails buy & hold on every asset except COIN,** whose buy & hold lost money: −2 to −6%/yr
  since 2021-22, against −1.9 to +3.6% for the bounce versions.

**Literature** (web search; abstracts and digests only):

- **No published study tests MA bounces against placebo levels.**
- **The rigorous MA evidence is trend-following:**
  - Brock, Lakonishok & LeBaron (1992, JF): buy signals above the MA beat sell signals.
  - Sullivan, Timmermann & White (1999): nothing is significant out of sample, 1987-96 (from
    secondary summaries).
  - Han, Yang & Zhou (2013, JFQA): MA timing works on volatile portfolios.
  - Bajgrowicz & Scaillet (2012, JFE): under FDR control, low costs erase the best rules'
    gains.
- **Support levels:** Osler (2000, FRBNY) found published FX support levels bounced slightly
  more often than arbitrary ones (about 61% vs 56%, from secondary summaries), through order
  clustering.
- **Distance from the MA:** Avramov, Kaplanski & Subrahmanyam (2021) find that stocks sagging
  toward their 200-day average earn less, not more.
- **Buy-the-dip tests:** Bonini, Shohfi & Simaan (2024) and AQR's "Hold the Dip" (2025) find no
  reliable gain.

**How this fits:**

- **Stocks match that literature.** There is no support effect at averages (within the same
  month the average is slightly worse than nearby lines), and there is a slight
  trend-persistence tilt:
  - lines above the average beat lines below it, clearly so against the pool;
  - rising averages beat falling ones with the 20-day exit, weakly.
- **Crypto shows no such tilt.** C4 is null, and the placebo-line order is mixed: the other way
  at 28 days, the same way with the X2 exit, never significant.

**Practical reading:**

- **A touch of a moving average is not a buy signal.** That holds for daily, weekly and monthly
  averages, SMA or EMA, of any tested length, on stocks and on crypto. The average is no better
  than a line 1-2 ATR away.
- **Buying after the bounce is confirmed** (HOOD's close near 101) does no better on average
  against the stock's own drift, even for strong bounces like HOOD's (−0.42 / −0.26 vs −0.19 /
  −0.26 for all confirmed bounces).
  - Against the member pool, strong bounces did about 0.4 pts better per 20 days (p
    0.02-0.03).
  - But that is one of 40 exploratory rows, and strong coin bounces lagged the coin pool
    (−1.4).
- **A bounce in a volatile, beaten-down stock like HOOD has no reliable edge either way.**
  - The 234 HOOD-like touches averaged +1.6% (same-year) / +2.2% (leave-out) over 20 days.
    But 73 of them come from 2009, mostly the May-November rebound, and without 2009 they
    averaged −1.4% / −1.6%.
  - Only 6 past HOOD-like touches bounced as strongly as HOOD just did.
  - Across all 234 bought at the line, the 10th-90th percentile of the 20-day abnormal return
    is about −18% to +19% (−16% to +20% when bought after the bounce).
  - HOOD's own 15 past touches of its 200-day averaged −4.5% over 20 days (+14% over 60 days,
    mostly from April 2025, with its placebo lines doing about as well).

# 2026-10-16 — investing by countries' policy direction (economic freedom, taxes, energy/industry)

**The user's thesis:**
- Some Western countries are drifting toward higher taxes, de-industrialization and less economic
  freedom.
- Others are moving toward lower taxes, more energy and industrial build-out, and more market freedom.
- Overweighting the second group should pay. Flesh this out and suggest ways to invest in it.

**What was done:**
- **Research.** Six researchers covered the literature, reform case studies, Western and non-Western
  policy trajectories (2015-2026), investable vehicles and reachable data. The notes are in
  `analysis_2026/research_notes/Economic freedom investment thesis/`; the synthesized report is
  `analysis_2026/reports/Economic freedom investment thesis.md`.
- **Network limits.** The sandbox blocks fraserinstitute.org, heritage.org, the World Bank and
  similar sites, so the research relied on search summaries. Many 2025-26 facts in the notes are
  flagged as unverified.
- **Pre-registered backtest.** `analysis_2026/FREEDOM_PREREG.md` (commit b100171), written before
  any results; code in `analysis_2026/freedom_countries.py`; data from
  `python3 -m analysis_2026.fetch_freedom_data`.
  - The first run was committed before the audit.
  - An audit with four lenses and skeptics confirmed 34 findings. None changed a verdict.

**Data (third-party mirrors, cross-checked; see `data_sources.md`):**
- **Fraser Economic Freedom of the World**, 2025 release (data 1970-2023), plus the 2024 and 2019
  releases for vintage checks.
- **Heritage Index of Economic Freedom**, 1995-2026, with components.
- **Jensen-Kelly-Pedersen (JKP) country market returns**: all listed stocks, value-weighted, USD,
  monthly, to 2025-12.
- **World Bank WDI** manufacturing share of GDP.
- **Our World in Data** electricity generation.
- **iShares country ETF** monthly bars.

**Design:**
- **Formation:** at the end of October each year, 1997-2025.
- **Universe:** JKP countries with ≥ 20 stocks and 12 months of history (about 50 in 1997, about 75
  in 2025).
  - Venezuela and Zimbabwe are excluded.
  - Russia gets −100% in March 2022.
- **Signals:** each uses only data public at formation.
  - Fraser data year ≤ Y−2 (data year t is published around September of t+2, so data year Y−2 is
    public by September of Y).
  - Heritage index year Y (published January-March Y).
  - WDI and OWID data year Y−2.
- **Portfolio:** the top third minus the bottom third, equal-weighted, held 12 months.
- **Pass rule:** mean > 0, Newey-West t ≥ 2, positive in both halves, and survives Holm correction
  across the seven tests.

**Results: all seven pre-registered tests FAIL.**

| | signal | %/yr | NW t | halves | one-sided 95% upper bound |
|---|---|---|---|---|---|
| S1 | 5-yr change in Fraser freedom | −1.62 | −0.92 | −0.82 / −2.42 | 1.3 |
| S2 | Fraser level | −1.51 | −0.73 | −4.10 / +1.04 | 1.9 |
| S3 | 5-yr change in Heritage tax burden (higher = lighter) | −0.20 | −0.13 | −1.95 / +1.68 | 2.25 |
| S4 | 5-yr change in manufacturing % GDP | +2.00 | +1.12 | +1.46 / +2.52 | 4.9 |
| S5 | 5-yr growth in electricity generation per person | −0.74 | −0.38 | +2.93 / −4.36 | 2.4 |
| S6 | S1 within 22 Western countries | −0.38 | −0.26 | −1.07 / +0.30 | 2.0 |
| S7 | composite z-score of S1, S3, S4, S5 | +1.11 | +0.63 | +1.23 / +0.99 | 4.0 |

- **Fama-MacBeth regressions,** controlling for 12-month momentum and long-term reversal: no signal
  reaches |t| 1.4. Momentum is t 2.7-3.1 in every regression.
- **Power:** 80% power only for premia of about 3.6-5.2%/yr at 5% one-sided, and about 4.8-6.8% at
  the Holm hurdle. Freedom, tax and electricity premia above 1.3-2.4%/yr are ruled out at 95%. Smaller
  effects are not.
- **Cohort dependence.** The 1997 cohort, held through the Asian and Russian crises, was in effect
  long emerging-market reformers and short developed markets. It drives S1, S2, S4 and S7. Without
  it:
  - S1 is −0.4 (no edge);
  - S2 is −3.1 (t −1.8);
  - S4 is +3.3;
  - S7 is +2.4.
  - No sign of S1, S2, S4 or S7 flips when any single cohort is dropped. The near-zero S3 and S6 do
    flip.
- **Audit corrections:**
  - World Bank aggregate rows (WLD, HIC, EUU and others) had entered the S7 z-scores. The fix moves
    S7 from +1.22 to +1.11.
  - Unadjusted month-end closes in the ETF bars were repaired.
  - Overlapping-hold labels were corrected.
  - The reversal control was relabelled: months t−60 to t−13, which spans the same space as the
    registered 60-month return.

**Exploratory (40+ rows; none changes a verdict):**

| variant | S1 | S4 | S7 |
|---|---|---|---|
| region-neutral, within DM and EM separately | −1.56 | +1.52 | +0.92 |
| MSCI ACWI countries only | +0.28 | +1.13 | +0.15 |
| markets with ≥ 50 stocks | −1.25 | +1.45 | −0.49 |
| long-only tilt | −0.54 | +1.04 | +0.76 |
| 36-month hold | −0.51 | +1.88 | +0.72 |
| Fraser chain-linked panel | −1.55 | | +0.73 |
| data repairs + multiple-rate regimes dropped | −1.47 | +2.14 | +0.87 |

- The Western-only test on the chain-linked panel (S6) is +0.96 (t 0.6).
- **S4 is the only signal positive in nearly every variant,** but the effect lives in small and
  frontier markets.
  - A 1-year WDI lag gives +3.11 (t 1.92).
  - iShares ETFs over 2001-2025 give +3.07 (t 2.13, Holm p 0.10 across six ETF tests). On the same
    country-years JKP gives the same number, so this is not an independent confirmation.
  - The WDI data are today's revised vintage.
- **S3 within developed markets is −2.69 (t −2.33):** countries whose measured tax burden lightened
  did worse. This is fragile (2000-2011) and one of 40+ rows. Read it as no support for the tax leg,
  not as evidence that tax cuts hurt.

**Positive control (post hoc).** Sort on the 1-year Fraser change in data year d. The calendar-year
long-short return in the years after d:

| return year | %/yr | t |
|---|---|---|
| d (same year) | +3.65 | 2.68 |
| d+1 (still before publication) | +4.82 | 2.85 |
| d+2 (publication year) | +0.68 | 0.38 |
| d+3 | −2.15 | −1.47 |

- The literature's same-year freedom-change effect appears in these data (positive in both halves),
  and it is earned before an investor could see the index.
- The year-after effect comes entirely from returns through 2012 (+10.42%/yr; −0.31 since 2013).
- Heritage tax-burden changes show no relation at any timing.
- Manufacturing changes: +5.42 (t 3.26) in d+1 (+8.48 to 2012, +0.48 since), and +3.38 (t 1.82) in
  d+2, after WDI publication (+2.67 / +4.48).

**The premise in the data:**
- **Whether the West lost more or less Fraser freedom than the rest of the world depends on the
  window.**
  - 2018→2023: West −0.13, rest of the world −0.18, JKP universe −0.19.
  - 2015→2023: West −0.13, rest −0.10.
  - The West's entire decline is in the COVID data year: −0.25 in 2019→20, then +0.11 in 2020→23.
  - The rest of the world was −0.16 in 2019→20, then −0.05 in 2020→23.
- **Since 2020:**
  - Greece +0.37, Netherlands +0.28, Luxembourg +0.26 and Spain +0.25 improved most.
  - Norway (−0.25), Sweden, Australia, New Zealand and Iceland kept falling.
- **The West's measured deterioration is fiscal:**
  - government consumption and top marginal rates (Fraser 1A, 1D);
  - Heritage government spending: −4.5 vs 0.0 for non-West countries, 2021→26.
- **It is also an energy deterioration.** On electricity build-out, 11 Western countries are in the
  bottom third today and 4 in the top.
- **Not everything fits the premise:**
  - Heritage tax burden improved: +0.5 vs −0.1.
  - On the Fraser level, 14 Western countries are in the top third and none in the bottom.
- **The global S1 sort shorts the West, but the West-only tests are flat.** It put 271 of 591 Western
  country-years in the short leg and 54 in the long leg; the USA was in the short leg in 20 of 29
  years. Yet S6 and S1 within developed markets are flat.
- **Current ranking** (`current_ranking.csv`): descriptive only, because S7 failed.
  - Top: Saudi Arabia, UAE, Denmark, Greece, Zambia, Vietnam, Brazil, Oman, Sweden, Kuwait.
  - Bottom: Romania, Sri Lanka, Turkey, Bulgaria, Trinidad, Estonia, Argentina, Czechia, New
    Zealand, UK, Hong Kong.
  - The data end in 2023/24, before Argentina's reforms and the 2025-26 events.

**Limits:**
- Gradual published policy drift only. Avoiding tail events (capital controls, expropriation,
  sanctions) cannot be tested: Venezuela and Zimbabwe are excluded, and Russia 2022 is the only
  collapse in the sample.
- Results are gross, pre-tax, equal-weighted long-short returns on all-listed-stock indices. The
  investable version, a long-only ETF tilt, was small and insignificant.
- Third-party data mirrors, and revised (not point-in-time) WDI and Fraser vintages.

**Practical reading:**
- Freedom changes coincide with returns, but in this post hoc check only before the index publishes
  them.
- A rule that buys countries after the index shows improvement earns nothing.
- What remains plausible but unproven:
  - a discretionary forecast of reforms before they are visible.
  - **country momentum.** Significant with monthly updating: +8.70%/yr held 1 month (t 3.28) and
    +4.94 held 6 months (t 2.02). With annual formation it is not: +2.04 (t 0.68).
  - **valuation**, untested here.
  - **avoiding capital controls, expropriation and sanctions.** This test cannot measure it, and
    measured direction would not have flagged Russia: in October 2021 it was in the top third on S1,
    S3 and S7.
- **Exclusion screens did not help.** Holding all but the bottom third on S1, S2 or S3 returned
  −0.52, −0.40 and −0.27%/yr against holding all (t −1.15, −0.61, −0.68).
- **Freer countries by level are less volatile:** 19.2% vs 24.7% single-country volatility, top vs
  bottom third on S2. Countries improving fastest are more volatile (23.5% vs 21.3%).
- The report lays out vehicles, taxes and sizing for anyone who wants a modest, rules-based tilt
  anyway.

---

# 2026-10-18 — scalping and bid-ask capture in low-volume markets

**The user's question:**
- A friend scalps low-volume stocks. He "invests a large amount" to capture small price increases, or buys at
  the bid and sells at the ask, and says he makes money.
- Is it a strategy, which variants are worth testing, and does large capital help?

**What was done:**
- **Research.** Four fact-checked notes in `analysis_2026/research_notes/Scalping and market making/`.
  - The literature says the spread pays for adverse selection, inventory risk and fees.
  - Net liquidity-provision profit in US stocks is about 1-2 bp even at 100 ms.
  - Under 1% of Taiwanese day traders are reliably profitable net of fees, and 97% of persistent Brazilian
    day traders lost money.
- **Pre-registration.** `analysis_2026/SCALPING_PREREG.md` (85e5d19), before any test-sample result, revised
  after a 3-lens adversarial review.
  - 36 primary tests in one Holm family.
  - Verdicts PASS / NO EDGE / INCONCLUSIVE.
  - Positive and negative controls run first.
- **Data.**
  - Binance spot trades (S3 archive; aggressor flag on every print).
  - qlib US daily 2001-2020.
  - Robinhood read-only data pulled by agents: a scanner universe of 3,485 low-volume stocks, daily bars
    2023-2026, 5-minute and 1-minute bars for a random 118-name panel, and 15-second bars for 40 of those
    names.
  - All of it is gitignored under `data/scalping/`.
- **Engines and audit.** Engines `scalp_crypto.py`, `scalp_us_daily.py` and `scalp_us_intraday.py` were
  reviewed adversarially before the full runs. The results were then audited with a skeptic per part.
  - Two fixes: sale proceeds floored at zero (70 qlib glitch trades had lost over 100%), and Part C's markout
    and half-hour tables restricted to eligible stock-sessions (C26). The null redraw pool also now drops
    gap-spanning bars; the skeptic found this is a reading of "daily bar", not a fix for the absurd null
    values, and no verdict depends on it.
  - No verdict changed.

**Controls (run before reading results):**
- **Part A (crypto):**
  - In a synthetic Glosten-Milgrom market, Q1 under a true queue earns the half-spread (2.57 vs 2.5 bp;
    24.85 vs 25 bp).
  - On 322 real USD-M futures symbol-days with the true book, the trades-only F1 fill rule is within 0.10,
    0.34 and 0.37 bp per $ of a FIFO queue for Q1, Q2 and Q5. No correction is needed under the registered rule,
    but every validation symbol had at least 370 taker orders an hour, against medians of 89 and 163 in bands
    A and B, so the check does not cover the thinnest pairs.
- **Part B (daily):** the known-answer check passes. B1 gross on S&P 500 PIT 2001-2010 is +6.2 bp, NW t 2.78.
- **Part C (intraday):** the Roll-market positive control FAILS in every band. The registered C1 rule cannot
  earn the spread from bars without quotes, so its cells are capped at INCONCLUSIVE.

**Results (study-wide Holm; `results_scalping/verdicts.txt`): 0 PASS, 32 NO EDGE, 4 INCONCLUSIVE.**

**Part A, Binance spot, net bp per $ filled at fee 0/2, $1k orders (bands A $50-200k / B $0.2-1M / C $1-5M /
D $5-50M daily volume):**

| | A | B | C | D |
|---|---|---|---|---|
| Q1 join bid and ask | −15.73 | −12.18 | −7.09 | −4.16 |
| Q2 step inside | −16.65 | −13.02 | −7.54 | −4.51 |
| Q5 friend's rule | −17.56 | −12.04 | −6.78 | −4.65 |

- **Size of the loss.** t is −4.8 to −16.0; the strict upper bound is at most −3.18 bp, against E = +1 bp.
  Q5 loses $18.6 / $22.8 / $25.7 / $40.5 per pair-day.
- **Decomposition** (Q1): spread captured +5.9/+3.9/+2.3/+1.3; adverse move to 300 s −19.2/−14.3/−8.3/−4.8;
  forced exits −3.1/−2.0/−0.8/−0.2 bp.
- **Kill rule:** touch fills (F2) are ≤ 0 in every cell, so the kill rule fired. It is a point-estimate rule:
  under F2 the strict upper bound of Q5-B is +3.39 bp (Q5-D +0.06).
- **Break-even:** needs a maker rebate of 6-24 bp per maker $.
- **Larger orders are worse:** at $25k, Q1 is −31/−29/−18/−8.6 bp.
- **Speed doesn't save it.** Being first in queue on the futures validation days still loses −1.9 bp (FIFO −2.4).
- **No subset survives.** Every split (tick class, spread/volatility, volatility, listing age, weekday) is
  negative.

**Parts B and E, qlib 2001-2020, net per trade at m = 1.5, Y = 0.5, $10k, band excess (B3 raw), bp:**

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| B1 buy bottom-decile losers | −628 | −309 | −202 | −143 |
| B2 losers on 3× volume | −730 | −372 | −232 | −154 |
| B3 resting bid 1σ below close | −269 | −128 | −79 | −61 |
| B4 friend's rule, daily | −186 | −132 | −110 | −107 |
| E1 buy top-decile gainers on 3× volume | −675 | −343 | −225 | −150 |

- **All 20 are NO EDGE**, failing the halves, B-R replication, winsorized and drop-month conditions. The strict
  edge upper bound is −30 to −693 bp per trade-day.
- **Recent sample.** B-R 2023-2026 is worse: B1 −1005/−532/−334/−222.
- **Pure gross** (no spread, no impact), B1: +101/+24/+8/+3. That is +44 in L1 without about 26 qlib glitch names.
  - A synthetic no-information market gives +84/+25/+11/+4 from bounce alone.
  - The gross is all overnight (close to open).
- **Break-even** at zero impact needs true spreads below 2-36% of the estimate (B1 17/9/4/2%, B2 36/10/6/3%,
  E1 10/6/5/6%; at most about 8% without the glitch names). The estimate is 1.2-2.2× the 2026 closing quotes.
- **Exploratory, all negative:**
  - B4 with open-price improvement −93/−43/−26/−19;
  - thin ETFs vs a matched liquid twin (B6): −49 to −290;
  - 5- and 20-day holds; VIX terciles (high VIX worst); $1-3 stocks; dropping k > 1 (Tick Size Pilot) days.

**Part C, 5-minute bars, 118 names, 160 sessions:** C1 is −$27.7 / −$35.1 / −$36.6 / −$33.5 per stock-session,
i.e. −306 / −196 / −108 / −50 bp per $ bought.
- **Relative to no-edge levels:** the Roll no-edge level is −400 / −186 / −95 / −46 bp, and the shuffle null
  −310 / −203 / −112 / −64.
- **INCONCLUSIVE by the cap.** Under the other reading of "capped at INCONCLUSIVE" it would be NO EDGE.
- **Part E intraday ORB on 1,492 gap-up, 5×-volume event days:** net −5.1% per trade. The gross is +1.8%, all of
  it one halted trade (INHD), and −0.4% without it. The event filter is a registered same-day look-ahead.

**Part D (capacity, B-R medians):**
- **Round-trip cost** at 10% of ADV: 6.5-7.8% (L1), 3.6-4.9% (L2), 2.5-3.6% (L3), 2.0-2.9% (L4).
- **D3:** every daily strategy (B1-B4, E1) has return ≤ 0 already at $10k deployed. $1M aimed at B1-L1 keeps about $420k working.
- **D4:** for a buyer of 5-100% of ADV, paper beats realized by a median 1-5 points in L1-L4. Realized after 5
  days is about −6 to −9% (L1).
- **D2 (B-R):** after 3×-volume top-decile up days, 20-day band excess is −4.1% (L1, t −4.0), −4.9% (L2,
  t −5.1) and −2.9% (L3, t −2.8). There is no give-back in B-H.

**Caveats:**
- Part A covers Binance.com books only, which US persons cannot use.
- F1 may be pessimistic in the thinnest pairs. A tick-scaled correction could lift Q5-B to about +2 bp, worth
  about $4 a day, and would put the strict upper bounds of Q5-A (+6.8 bp) and Q5-B (+5.7 bp) above E = +1 bp.
  Those two NO EDGE verdicts therefore assume F1 is roughly faithful in thin books (at 30% informed flow no
  cell crosses).
- The inventory cap is not enforced for in-flight orders (edges ±0.8 bp when enforced).
- Both US samples are survivor-biased upward for these long-only rules.
- qlib glitch names distort gross diagnostics.
- IEX tick-level check (C-iii, descriptive): on 27 L4 name-days with IEX at the NBBO, C1 on IEX ticks lost $46.8
  per name-day (−0.77% per $ bought, 15% positive) vs −0.86% per $ for the bars on the same days.
- A-RH stratum (exploratory; Robinhood-listed coins, every 7th day) is incomplete: 608 of 807 pair-months
  before the run's 2-hour limit. Every cell is negative, already before fees: Q1, Q5 and Q1-LO lose 2-22 bp
  per $ filled at fee 0/2.
- Sources are mostly search summaries.

**Practical reading:**
- In crypto, bid-ask capture at retail speed loses to adverse selection before fees, and slow liquidity
  provision in thin stocks cannot pay its spreads. The intraday stock test (Part C) was inconclusive: bars
  without quotes cannot test bid-ask capture in US stocks either way.
- Capital adds impact and ownership-filing limits, not capacity.
- If the friend's gains are real, they more plausibly reflect luck in a strong market, attention trades that
  happened to work, or marks his own buying created, than a repeatable edge; his trades were not examined.
- To judge him: 12+ months of closed-trade statements, net, at liquidation value, against the S&P 500.

---

# 2026-10-19 — Bollinger-breakout replication of a Twitter "AI breakdown"

**The user's question:**
- A Twitter post gave an "AI breakdown" of a crypto trader: 16 months, 1,462 bots, $10.7B volume, 4.3x on
  starting capital, a 48.7% hit rate (51.7% with a grid bot), and wins 1.4x losses.
- It describes Bollinger Band breakouts near local and all-time highs, cut below the midline, with a grid "while
  waiting", and lists 15 rules.
- "Can you figure out their exact strategy from this summary, replicate it and test it on all of our assets?"

**What was done:**
- **Research.** Notes in `analysis_2026/research_notes/Bollinger breakout replication/`.
  - `rules_and_evidence.md` gives an operational reading of every rule, the grid mechanics, the literature, and
    arithmetic on the post's numbers.
  - The post cannot be traced. Six of its 15 rules (6, 11-15) are patterns mined from one trader's results.
  - Its volume is 950-19,000x average equity for a $0.25-5M start.
- **Pre-registration.** `analysis_2026/BB_REPLICATION_PREREG.md` (frozen 2026-10-18, bc744ff) after a 3-lens
  adversarial review (54 proposals). Addenda 1-3 came before any strategy result.
  - 12 tests in one Holm family: verdicts PASS / NO EDGE / INCONCLUSIVE, with drift-adjusted trade units.
  - The answer sentences were fixed in advance.
- **Data.** `data/bbreplica/` (gitignored), from the Binance archive:
  - hourly spot and perpetual klines for 40 coins, funding, mark-price hours;
  - 1-minute klines for 6 coins from 2024-07;
  - daily klines of all 909 USDT perpetuals.
  - Stocks come from `data/universe_pit_all/` and `data/raw_pit/`.
- **What was run.**
  - **R0, the literal reading:** BTC/ETH/SOL perpetuals at 3x; daily BB(20, 2) breakouts near highs; pyramid 1/3 +
    adds at +2% and +5%; ATR stop, 3R take-profit on half, midline exit; the timing rules as written.
  - **S1:** the core at 1x without rules 6 and 12-15.
  - **The rest:** 20 sensitivity rows; F, the frequency-matched cell (1-hour bars on the monthly top 10); grid
    overlays on 1-minute bars; the stock/ETF version; US routes through `gate.py`; H11/H11b fits to the post; H12
    shorts; a luck benchmark.
- **Audit.** Independent recomputation from raw data reproduced every core number. Two real defects were fixed;
  no verdict changed (below).

**Controls (run first; all passed; `results_bb/controls/summary.txt`):**
- **Engine known answer.** On martingale paths the mean trade before costs is within 2 SE of zero (S1 27,218
  trades, t 1.49; R0 t 1.68). On trending paths S1 has t 4.98. The grid is zero before fees and negative after.
- **Look-ahead.** 110 cut times, 2,597,008 decisions unchanged.
- **Fill audit.** 650,746 fills, 0 violations.
- **Liquidation and grid path.** 12 liquidation cases pass; the grid path matches to 0.07% of gross grid profit.
- **Indicator cross-check.** 6.6x vs 5.14's 12.4x.
- **Inference.** The bootstrap-t 95% bound missed 5.5% (11 of 200), so it was widened to 95.5% and the NO EDGE
  level to 99.625% (Addendum 2). The rejection rate was 1.5%.

**Results (study-wide Holm; `results_bb/verdicts.txt`): 0 PASS, 3 NO EDGE, 9 INCONCLUSIVE.**

| test | estimate [95% CI] | Holm p | NO EDGE bound vs E | verdict |
|---|---|---|---|---|
| H1 core edge, % of M per trade (drift-adjusted) | +3.73 [−1.20, +8.67] | 0.80 | +13.69 vs +0.5 | INCONCLUSIVE |
| H2 vs buy-and-hold / vs the indicator, Sharpe | +0.09 [−0.59, +0.90] / −0.27 [−0.85, +0.32] | 1.00 | +1.34 / +0.58 vs +0.10 | INCONCLUSIVE |
| HS1 stocks, per trade / Sharpe | −0.643 [−0.784, −0.501] / −0.54 [−0.86, −0.19] | 1.00 | −0.435 / −0.041 | NO EDGE (HARMS) |
| HS2 ETFs, per trade / Sharpe | −0.193 [−0.349, −0.036] / −0.37 [−0.78, +0.08] | 1.00 | +0.061 / +0.30 | NO EDGE |
| H3 pyramiding, per signal | +0.76 [−0.50, +2.03] | 1.00 | +3.00 vs +0.25 | INCONCLUSIVE |
| H4 confirmation, per episode | −0.97 [−2.46, +0.52] | 1.00 | +0.82 | INCONCLUSIVE |
| H5 near-high filter | −1.07 [−9.56, +7.41] | 1.00 | +8.93 | INCONCLUSIVE |
| H6 hour windows (rank 63 of 576) | +0.33 [−0.77, +1.43] | 1.00 | +1.89 | INCONCLUSIVE |
| H7 no Fri/Sat opens (rank 4 of 7) | −0.61 [−1.62, +0.40] | 1.00 | +0.47 | INCONCLUSIVE |
| H8 72-h hold / rule 15 | −0.026 [−0.064, +0.012] / −0.081 [−0.55, +0.39] | 1.00 | +0.010 / +0.36 | NO EDGE (via the 72-h hold only) |
| H9 3x vs 1x, log points a year | +21.6 [−5.3, +46.3] | 0.80 | +54.9 vs +2 | INCONCLUSIVE |
| H10 waiting grid, % of equity a year | −3.40 [−7.15, +1.64] | 1.00 | +3.87 vs +1 | INCONCLUSIVE |

- **The answer, in order.**
  - Crypto: not shown; the data cannot tell (H1).
  - Vs buy-and-hold and the indicator: the data cannot tell (H2).
  - Stocks: it does not work (HS1 NO EDGE (HARMS)).
  - ETFs: it does not work (HS2 NO EDGE).
  - "Their full strategy beats holding" may not be said for any group. In log points a year against holding
    (1 log point ≈ 1% a year of compound growth): crypto −7.1 [−52.4, +38.6]; stocks −9.0 [−14.7, −3.6]; ETFs
    −5.0 [−9.9, −0.4].
  - No route produced a TRADE verdict.
- **H1 detail.** Unadjusted +6.80% [+1.50, +12.09]. Halves +8.58% / +0.62%. Other 37 coins +5.32% [−0.42, +11.07]
  (+4.74% without ZEC). MDE 8.5%, against the post's implied edge of about 1%.
- **H8.** The 72-h hold changes 2 of 92 signals. Rule 15 alone: the data cannot tell.

**Headline (`headline/headline.csv`; W16 = 2025-06-17..2026-10-16 and W16b = 2024-06-30..2025-10-31 are single
16-month paths):**

| | Full 2020-2026 | 2020-22 | 2023-26 | W16 | W16b |
|---|---|---|---|---|---|
| R0 (3x, all rules) | 20.68x | 9.80x | 2.11x | 0.86x | 0.93x |
| S1 (1x core) | 5.74x | 2.96x | 1.94x | 1.01x | 1.08x |
| F, with ZEC / without | 2.99x / 2.80x | 1.92x | 1.56x / 1.46x | 1.17x / 1.09x | 1.32x |
| buy-and-hold, BTC/ETH/SOL equal weight | 39.66x | 7.09x | 5.60x | 0.82x | 1.49x |
| the indicator (`moneyline_ref`, same perpetuals) | 72.12x | 20.58x | 3.50x | 1.11x | 0.92x |

- **Full window.** Sharpe R0 1.07, S1 1.17, buy-and-hold 1.08, indicator 1.44. Max drawdown −50% / −23% / −85% /
  −51%. After tax 39.0% / 20.5% / 66.5% / 67.6% a year (SPY 13.9%).
- **Sensitivity rows** (`rows/rows.csv`).
  - Full multiples run from 1.12x to 131.9x, and no row survives BH (smallest adjusted p 0.26).
  - W16 multiples are 0.49x-1.74x, except S17 with ZEC: 8.96x, and 0.88x without ZEC.
- **Matching the post.**
  - H11: 0 of 78 variant-windows consistent. Every one fails the 0.5-2x count band; the most active (F) has 435
    tranches in W16 (400 without ZEC) vs 1,462; turnover among the 39 H11 rows is at most 183x. Some H11b cells
    reach the post's count (mostly 1-hour) and some 1-hour cells its volume (up to 2,481x in W16, 2,588x in W16b),
    but none matches its hit rate. Decoys consistent: 0 of 2,740.
  - H11b: the identified set is 16 of 648 cells (W16) and 21 (W16b), with 0 decoys. All use 4-hour bars, but they
    disagree on universe, direction and grid, so the post's statistics do not identify a strategy. The set made
    1.14-2.66x in W16 (1.13-1.93x without ZEC; fitted, in-window); out of window its median log growth beat the
    median cell's in W16 (41.7 vs 26.4 points a year) but not in W16b (5.9 vs 28.0; 3.2 vs 22.9 without ZEC).
    Run at 5x, seven W16b set cells passed 4.3x (4.40-6.75x, no ZEC traded); single in-window paths.
- **Luck** (`luck/`).
  - R0's W16 multiple is at the 55th percentile of 1,000 random-entry versions (W16b 58th). 0 of 4,000 versions
    reach 4.3x, and 0-1.8% reach 2x.
  - Months for t ≥ 2 at +9.5% a month: 4.5-14.6 (3x swings), 11.8-29.6 (5x).
- **Leverage (H9).**
  - Growth at L 1-5: 25.4 / 40.6 / 47.0 / 49.3 / 48.5 log points a year. Optimal L 4 (90%: 2 to ≥5, censored).
  - The three-slot account had 0 liquidations at every L: the L cap makes them rare, not impossible (S11 had 1).
    Average account exposure at 3x is 0.42.
  - R0 on one coin as the whole account (`rows/per_coin.csv`): 26 of 40 coins ended below 1x over 2020-2026 and
    11 lost 95% or more (median 0.37x, 4 liquidations), although the pooled trade mean was positive (+5.95% of M
    drift-adjusted [+0.19, +11.7]; +5.51% [−0.31, +11.3] without ZEC; exploratory). Rule-11 sizing from
    month-start equity took exposure to 181x equity (TRX).
  - The 2025-10-10 stress row is vacuous (no R0 position open).
- **Grid (H10).**
  - G-A grid profit +0.157 / +0.118 / +0.088 of a sleeve on BTC/ETH/SOL, against inventory −0.177 / −0.191 /
    −0.132.
  - Zero fees still −2.8% a year. The always-on grid: BTC +1.016 grid profit vs −1.011 inventory.
  - G-B (exploratory) ended at 1.08x vs R0's 0.92x (drawdown −30.5% vs −47.8%), but its mean daily difference is
    −0.5% a year [−18.4, +21.0].
- **Stocks.**
  - HS1 per trade: +0.09% of M unadjusted, −0.64% of M drift-adjusted. The Sharpe part alone carries HARMS (bound
    −0.041).
  - Vs a random-entry book (exploratory): −0.42 Sharpe [−0.72, −0.11].
  - 20-slot book 1.28x (idle cash at the T-bill) vs equal-weight members 13.05x (2001-2026).
  - 1996-2000, separately: −0.43% per trade, Sharpe −0.88.
- **User's tickers.**
  - TSLA, 40 trades: +5.89% [−0.13, +11.91]; book 23.1x vs hold 285x.
  - SPY / QQQ / IWM: −0.38 / −0.49 / −0.57% per trade.
  - COIN (11 trades), HOOD (14) and CRCL (1) are under 20 trades and not interpreted.
- **Routes** (`routes/summary.csv`). 0 TRADE.
  - PROBATION, failing only T1 on 11-20 trades: AVAX, DOT, UNI and ADA (Robinhood route) and COIN. The placebo
    expects 0.20-0.26 per 24-coin Robinhood group (0.05 for the user's tickers), so 3-4 per group is well above
    chance. Not acted on: 11-20 trades each, the same coins in every variant, a hindsight coin list, and the
    pre-registered answer allows "you can trade it" only for TRADE.
  - CB is capped by T1.
  - Every route trails buy-and-hold after tax: crypto by 14-42 points a year on the longest history (spot routes
    from 2017-08) and 30-53 over 2020-2026; stocks by 6-13.
- **H12 shorts (exploratory).** 1.54x vs 0.86x in W16 (one path; BH p 0.25). Over the Full sample 29.0x vs 20.7x,
  Sharpe −0.06 vs R0 (−0.47 to +0.43), one liquidation, −71% drawdown. Neither difference is distinguishable from
  zero.
- **Rules** (`scorecard/scorecard.csv`).
  - Rule 3 is a no-op as coded. Rule 6 is a no-op in R0 (0 exits suppressed), and NO EDGE only as a 72-h hold
    that binds on 2 of 92 signals. Rule 9 is not testable.
  - Rules 1, 5, 8, 10 and 11 show no detectable effect.
  - Rules 2, 4, 7 and 12-14 are INCONCLUSIVE (H3, H9, H4, H7, H6). For rule 15 the data cannot tell.

**Corrections after the audit (no verdict changed; commits 39acaad, ae55c59):**
- **Stock drift sample.** The leave-out drift sample now drops returns across gaps over 30 days and closes below
  $0.01 (FRC, SIVB, SBNY post-failure prints; CHK and BTUUQ splices). HS1's trade part moved from −0.6712% to
  −0.6427% of M per trade; the verdict is unchanged.
- **H9 units.** Relabelled as natural-log units (0.216 = 21.6 log points).
- **Labels.** H11 labels follow the literal rule ("inconsistent (also different trading frequency)"). Scorecard
  rule 15 notes that H8's NO EDGE comes only from the 72-h hold. Stock headline rows state their account and trade
  bases.
- **Documented, not changed.** The H11b share counts unscorable 1-hour cells (3.2% and 4.0% without the 146 and
  117 cells excluded by the 7-day statistic alone); H8(a)'s bootstrap is degenerate; part of H10's gap is rule
  11's sizing; crypto buy-and-hold pays no rebalancing costs.

**Caveats:**
- **The post** is unverified and doubly selected (by the summariser and the poster).
- **Venue.** Binance perpetuals and grids are generally not available to US residents. The CB route's cost is an
  assumption.
- **Stocks.**
  - Fills at the next open (no intraday data).
  - Close-only member rows (16% of 2001-2013 member-days, 33% of 1996-2000) create no signal.
  - The drift charge (about 0.73% of M per trade) sets the sign of HS1's trade part; the Sharpe part does not use
    it.
- **Inference.** Far-tail coverage after widening is about 1.5% vs a nominal 0.375%. No NO EDGE verdict is near
  its bound.

**Practical reading:**
- The exact strategy cannot be recovered from the post. The described rules on BTC/ETH/SOL do not come near 4.3x,
  by design or by luck; among the pre-registered rows only adding ZEC with hindsight (S17) exceeds it.
- Don't trade these rules, their leverage or their grid. On the same coins the repo's indicator was ahead (Sharpe
  1.44 vs 1.17), though H2 cannot separate them.
- To judge the trader: exchange statements for both accounts, with fees and funding, against holding the same
  coins at the same leverage.
