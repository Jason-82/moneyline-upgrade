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
