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
