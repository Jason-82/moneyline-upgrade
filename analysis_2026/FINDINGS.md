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
