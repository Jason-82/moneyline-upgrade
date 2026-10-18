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

---

# 2026-10-16 — the Larsson Line (EMA 32/58) on long histories

Pre-registered in `analysis_2026/LARSSON_PREREG.md` (7b324c0) before any run. Code in
`analysis_2026/larsson.py`, results in `analysis_2026/results_larsson/`.

The adversarial audit had three lenses (independent rebuild, look-ahead/conventions,
statistics) plus a confirm stage:
- It reproduced every number and found no look-ahead. Truncating the inputs at many cut
  dates (index, Dow, ETFs, both baskets) changed no earlier signal.
- It flagged conventions that move secondary numbers. These were fixed or added, and the
  study rerun (8cb2284, 7205412).

**The indicator.** The user's TradingView Larsson Line plots exactly EMA(32) and EMA(58) of
the close (private exports of BTC, ETH and SOL, median error 0). Its colour rule is **not confirmed**:
- **LARSSON** (primary): green while EMA32 > EMA58.
- **LARSSON-PRICE** (sensitivity): green once the close is above both lines, red once it
  is below both.

## Verdicts: all five primary tests FAIL

Sharpe gain above T-bills, paired stationary bootstrap, Holm across five. MDE = the gain
the test would detect 80% of the time at alpha 0.05.

| | comparison | dSharpe | p | halves | Holm | MDE |
|---|---|---|---|---|---|---|
| P1 | S&P 500 1929-2026, LARSSON vs buy & hold | +0.058 | 0.238 | +0.20 / −0.09 | 0.95 | 0.21 |
| P2 | S&P point-in-time basket vs EW buy & hold | +0.009 | 0.399 | +0.11 / −0.12 | 1.0 | 0.23 |
| P3 | crypto top-20 basket vs EW buy & hold | +0.154 | 0.178 | +0.11 / +0.22 | 0.89 | 0.46 |
| P4 | S&P basket vs old MoneyLine N=5 | +0.009 | 0.447 | +0.08 / −0.08 | 1.0 | 0.18 |
| P5 | crypto basket vs old MoneyLine N=1 | −0.360 | 0.950 | −0.52 / −0.15 | 1.0 | 0.52 |

- The verdicts survive:
  - mean blocks 60-500 (smallest Holm p 0.66)
  - a Newey-West t on the return difference (never positive)
  - a HAC Sharpe test
- The crypto tests can only detect very large gains: about 0.6-0.7 Sharpe at the 0.01 level
  the first Holm step needs (`mde80_a01` in verdicts.csv).
- The T-bill subtracted now matches the engine's cash leg. P2 moved from 0.391 to 0.399.

## What the numbers say

**S&P 500 index.** Total return; signal on the price index; fills at the next close;
0.02% per side.

| 1929-2026 | CAGR | after tax, pre-reg | after tax, realised | Sharpe_xs | maxDD | switches/yr |
|---|---|---|---|---|---|---|
| buy & hold | 9.93 | 9.68 | 8.95 | 0.42 | −83.6 | |
| LARSSON | 8.74 | 5.78 | 6.57 | 0.48 | −35.5 | 3.2 |
| LARSSON-PRICE | 8.95 | 5.92 | 6.21 | 0.52 | −41.7 | 12.5 |
| SMA200 | 10.11 | 6.69 | 7.78 | 0.59 | −51.5 | 6.0 |

- **Tax columns.**
  - *After tax, pre-reg:* strategies pay 35% on each year's growth; buy & hold pays 20%
    once at the end. Its dividends are taxed only then, never yearly.
  - *After tax, realised* (audit), via `sso_gold.simulate`:
    - FIFO lots; gains held over a year at 20%, otherwise 35%
    - dividends at 20% and T-bill interest at 35% every year
    - losses carried forward
  - Both sides move:
    - buy & hold 9.68 → 8.95
    - SMA200 6.69 → 7.78
    - LARSSON 5.78 → 6.57
  - Buy & hold still wins after tax, by about 1.2 points over SMA200 (not 3.0) and 2.4
    over LARSSON.
- **Drawdown depends on the fill day.** LARSSON's −35.5% is a lucky draw. One day either
  way gives −40.6% (fill at the signal close) or −46.0% (close t+2); close t+3 gives
  −52.8%.
- **Alpha on buy & hold** (monthly, NW t; not pre-registered):
  - LARSSON +2.5%/yr (t 2.5, beta 0.41), mostly before 1972
  - SMA200 +3.7%/yr (t 3.8), in both eras
- **Since 1972, LARSSON adds nothing.** Sharpe_xs 0.41 vs buy & hold 0.44 (SMA200 0.54).
- **1963-2026, with the old MoneyLine.** Each cell is CAGR / after tax realised /
  Sharpe_xs / maxDD:
  - buy & hold 10.81 / 9.90 / 0.44 / −55.2
  - LARSSON 8.91 / 6.57 / 0.42 / −35.5
  - LARSSON-PRICE 8.28 / 5.69 / 0.39 / −40.2
  - SMA200 10.45 / 7.87 / 0.56 / −21.5
  - old ML N=1 6.25 / 4.22 / 0.20 / −36.4
  - old ML N=5 7.70 / 5.37 / 0.33 / −26.6
- **Pre-1928 Dow, 1886-07..1927** (out of sample), same columns:
  - buy & hold 7.97 / 6.69 / 0.41 / −38.7
  - LARSSON 6.95 / 4.95 / 0.46 / −26.4
  - LARSSON-PRICE 9.72 / 6.79 / 0.76 / −17.9
  - SMA200 8.43 / 6.40 / 0.60 / −16.3
- **32/58 is not special.**
  - Among 4,567 EMA pairs on the index it sits at the 31st percentile of Sharpe_xs.
  - The White reality check across 69 pairs vs buy & hold gives p 0.275.
  - The neighbouring pairs in the study all land at 0.44-0.53.

**ETFs (13, 2005-2026).**
- **Sharpe_xs** medians: buy & hold 0.33, LARSSON 0.32, SMA200 0.34. LARSSON is better on
  7/13.
- **After tax, pre-reg** medians:
  - buy & hold 6.15, SMA200 2.96, LARSSON 2.39
  - old ML N=1 2.44, N=5 2.57
- **Who wins after tax.** Buy & hold is best on 12/13 under the pre-registered rule; its one
  loss is TLT, to old ML N=5. With bond and REIT distributions taxed yearly, the audit puts
  it at about 9-10/13:
  - IEF and HYG flip
  - LQD flips only if the strategies stay on the pre-registered tax rule

**Coins (21 survivors, 2018-2026).** Medians across coins depend on the start date.

| after tax | LARSSON | buy & hold |
|---|---|---|
| median at a 120-bar start | 18.40 | 10.84 |
| median at a common 200-bar start | 11.88 | 12.17 |

- The median per-coin gain, LARSSON minus buy & hold after tax, is the better measure:
  - +1.5 at 120 bars and +8.5 at 200
  - −1.7 to +8.8 across 100-400 bars
  - negative for calendar starts from Nov 2018 to Apr 2020, Jul to Nov 2022 and Jan 2023
  - LARSSON is better after tax on 12/21 coins at both starts (sign p 0.33), and on
    10-13/21 across 100-400 bars
- The old MoneyLine N=1 beats LARSSON on 15/21 (median Sharpe −0.07).
- Of the five headline rules, SMA200 is the worst on crypto at every start date. EMA50/200
  is about as bad per coin and worse in the basket.

**Baskets.** The tests use equal weight rebalanced daily. The pre-registration says only
"equal-weight"; daily rebalancing comes from the flip-delay code. The audit added held
sleeves: equal money on 1 January, then drifting. Each cell is CAGR / Sharpe_xs.

| | S&P daily | S&P held | crypto daily | crypto held |
|---|---|---|---|---|
| buy & hold (EW) | 10.90 / 0.51 | 9.95 / 0.49 | 15.25 / 0.56 | 20.63 / 0.61 |
| LARSSON | 6.51 / 0.52 | 6.46 / 0.50 | 29.60 / 0.71 | 27.49 / 0.68 |
| LARSSON-PRICE | 5.27 / 0.41 | 5.14 / 0.39 | 44.51 / 0.96 | 41.18 / 0.90 |
| old ML N=1 | 4.99 / 0.35 | 4.68 / 0.32 | 48.72 / 1.07 | 53.67 / 1.14 |
| old ML N=5 | 6.62 / 0.51 | 6.43 / 0.49 | 34.59 / 0.81 | 42.83 / 0.93 |
| SMA200 | 6.58 / 0.55 | 6.60 / 0.53 | 14.82 / 0.48 | 16.69 / 0.51 |

- **Daily rebalancing.**
  - It keeps buying collapsing coins: in the LUNA week, −43.8% vs −35.1% held.
  - It flatters LARSSON's crypto gain. Held baskets give P3 +0.066 (p 0.31) and P5 −0.458
    (95% CI excludes 0, in the old MoneyLine's favour).
- **S&P basket drawdown.** LARSSON −19% vs −58% for buy & hold, at 3.5-4.4 points less
  CAGR. In the second half (Nov 2013-2026), Sharpe_xs is LARSSON 0.48 vs buy & hold 0.60.
- **Crypto at 0.95% per side** (daily construction), Sharpe_xs / after tax:
  - LARSSON 0.64 / 17.3, LARSSON-PRICE 0.66 / 17.4
  - old ML N=1 0.82 / 22.2, N=5 0.68 / 18.5
  - SMA200 0.30 / 2.4; buy & hold 0.56 / 13.1

## The colour rule changes a verdict only on crypto

These are secondary tests, not pre-registered, so they cannot change a verdict. With
LARSSON-PRICE as the test rule:

| test | result | outcome |
|---|---|---|
| P1 | +0.095, p 0.15; second half −0.14 | fail |
| P2 | −0.107 | fail |
| P4 | −0.107 | fail |
| P5 | −0.108 (p 0.79): still below the old MoneyLine N=1 | fail |
| **P3** | **+0.406, p 0.001, Holm 0.005, halves +0.44 / +0.37** | **would pass** |

The P3 pass is fragile:

| P3 variant | dSharpe | p | Holm-equivalent |
|---|---|---|---|
| held baskets | +0.290 | 0.017 | about 0.08 (fail); audit's 10-seed median Holm 0.074 |
| retail costs 0.30/0.35% | +0.338 | 0.011 | about 0.05 (borderline); 4/10 seeds fail |
| held + retail | +0.228 | 0.039 | about 0.19 |
| 0.95% per side | +0.099 | 0.21 | fail; second half −0.04 |

- **The pass is post hoc.** LARSSON-PRICE was not the pre-registered rule. Over 10 bootstrap
  seeds Holm ranges up to 0.03, or 0.055 if both colour rules count as tries. It would
  need confirming on data after September 2026.
- **On stocks the price rule mostly did worse:**
  - held S&P basket Sharpe_xs 0.39 vs 0.50
  - worse on 10/13 ETFs
  - P4 −0.107, CI excluding 0
  - realised after tax on the index 6.21 vs 6.57 (1929) and 5.69 vs 6.57 (1963)
  - It did better on the index before 1990 and on the Dow.
- **Mechanism: speed.**
  - LARSSON-PRICE switches about 18 times a coin-year, LARSSON about 5.
  - An EMA15/30 crossover basket matches it (Sharpe_xs 0.96).
  - The whole gain is lower volatility. The mean return is about the same as buy & hold.
  - On crypto 2019-2026 Sharpe falls steadily as rules get slower.

## Practical reading

- **As a crossover,** the Larsson Line is an ordinary slow trend filter.
  - On stocks: much smaller drawdowns, about the same Sharpe, lower CAGR, and clearly
    lower after-tax return.
  - Nothing about 32/58 is special, and the edge has faded since 1972.
- **On crypto it trails the old MoneyLine N=1.** If the chart colours on price vs both
  lines, it behaves like a faster filter. It did well on the crypto basket at low costs,
  but not at Robinhood-like costs, and still not as well as the old MoneyLine.
- **Ask the user which colour rule TradingView uses.** On the user's exports to
  2026-10-15, the two rules disagree on ETH and SOL: crossover green, price rule red.
- **"A plain 200-day average beat them all" (said in chat) needs the metric named.**
  - It holds for Sharpe_xs and pre-tax CAGR on the 1929-2026 index. Its Sharpe_xs beats
    all 59,501 EMA pairs the audit tried; its CAGR beats all 4,567 in the smaller grid. Its edge vs buy & hold is p 0.049 unadjusted, Holm 0.094
    with LARSSON.
  - It does not hold for drawdown in 1929-2026: −51.5%, 7th of 9, from one 1932-33
    whipsaw (−28.5% for 1934-2026).
  - It does not hold after tax against buy & hold, in 4 of 5 eras, or on the Dow, where
    LARSSON-PRICE was better.
  - It does hold for 1963-2026 risk-adjusted return and drawdown (Sharpe_xs 0.56,
    maxDD −21.5%).
  - On crypto it is the worst of the five headline rules. EMA50/200 is worse in the basket.

**Small items:**
- The Dow window starts 1886-07-01, about six months after SMA200 has its first value
  (1885-12-30). The gap is not explained. Starting 1886-01-01 lowers the CAGRs by 0.1-0.2
  points and changes no ranking.
- The S&P universe filter uses future data to cut a few collapsed names. The effect is
  under 0.002 Sharpe.
- 24 members from 2001 have no price file, Enron and Global Crossing among them. The
  effect is at most 0.19 CAGR points.
- ETF and stock signals use dividend-adjusted closes, not the chart price the
  pre-registration names.
  - On SPY, the one ETF tested, the chart price moves Sharpe_xs by −0.07 to +0.05
    depending on the rule, with no consistent sign.
  - Bond ETFs (yields 3-6%) were not tested.
- The daily-rebalanced buy & hold basket's own trades are uncosted: about 1%/yr on crypto.

---

# 2026-10-19 — execution mode and late-entry checks for the agentic sleeve (exploratory)

Not pre-registered. These checks set the defaults in `agentic/` and decide no study verdict.

## Split vs immediate vs confirm5 on crypto

Script: `analysis_2026/results_agentic_modes/split_crypto.py`, output `split_crypto.txt`. Old MoneyLine;
`split` = 50% at N=1 + 50% at N=5.

| test | after tax: immediate / split / confirm5 | split vs immediate |
|---|---|---|
| 21 coins one by one, 0.15%/side | median 22.7 / 25.7 / 21.1 | better on 14/21; shallower drawdown on 17/21 |
| 21 coins one by one, 0.95%/side | 12.1 / 18.4 / 15.7 | better on 16/21 |
| Top-20 basket incl. dead coins 2019-2026, held, study costs | 37.3 / 34.9 / 29.9 | immediate ahead; see below |
| same basket, 0.95% | 26.5 / 26.8 / 24.7 | a tie |

- **The basket at study costs:**
  - Sharpe 1.14 / 1.08 / 0.93
  - max drawdown −51 / −49 / −51
  - split vs immediate dSharpe −0.06, p 0.79: not significant either way
- **Split beats confirm5 in every version** (p 0.027 at study costs).
- **Default:** split for crypto and stocks. It is never the worst mode, has shallower drawdowns in most tests, and
  ties or wins at Robinhood-like costs. Immediate's 2-4 point lead in the strictest test is within noise.

## Late entries into green runs, by rise since the flip

Script: `analysis_2026/results_late_entry/late_rise.py`.
- **Method:** entry decided at close d, filled at the next open; exit at the open after the red-flip close.
- **Data:** 21 coins, 13 ETFs, 293 sampled S&P stocks.
- **Measure:** pooled geometric mean per trade for entries 1-20 bars after the flip, with run-clustered 95% CIs.

| rise since flip | crypto | stocks |
|---|---|---|
| at the flip | 3.6% | 0.4% |
| 10-20% | 4.3% | 0.3% |
| 20-35% | 6.8% | 1.0% |
| 35-50% | 8.7% | 2.9% |
| more than 50% | 12.1% [−2.2, 28.5] | −3.3% [−6.0, −0.5] |

**Independent re-check** (own code, `moneyline_ref`): point estimates match to 4 decimals.

- **Crypto: no penalty for bigger rises, but no reliable premium either.**
  - Without each bucket's 10 best runs, the 10-50% buckets earn 1.1 / 0.7 / −0.6%, against 1.6% at the flip.
  - Only 11 of 21 coins individually show the higher means.
  - Under N=5, and after 2021, some buckets fall below the flip.
- **Stocks: more than 50% up is worse at N=1, but fragile.**
  - The interval crosses 0 within each half of the sample, and after dropping the 3 worst runs.
  - At N=5 the sign flips: +2.5% [−6.1, 11.9].
- **Entries more than 20 bars after the flip:**
  - stocks: clearly weaker, −0.39 log points [−0.54, −0.24]
  - ETFs: weaker, not significant
  - crypto pooled: not weaker (3.9 vs 3.6%), but weaker per coin (14 of 21) and negative without the 3 best runs

**Defaults:** `join_recent` with `max_join_bars` 20 and `max_join_rise_frac` 0.50. These are risk controls, not a
measured edge.
- The cap blocks 3% of crypto entries and 0.2% of stock entries.
- A tighter cap (0.10-0.20) would have blocked 14-26% of crypto entries, which averaged 6-8%.
