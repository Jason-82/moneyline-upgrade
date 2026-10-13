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
