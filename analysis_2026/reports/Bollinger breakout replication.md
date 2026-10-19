# The Bollinger-Breakout Post Can't Be Reverse-Engineered; Its Breakout Rules Do Not Work on Stocks or ETFs, and on Crypto the Data Cannot Tell

**Question (2026-10-18).** The user saw a Twitter post with an "AI breakdown" of a crypto trader (image: `analysis_2026/research_notes/Bollinger breakout replication/source_summary.png`). It claims:
- 16 months of trading, 1,462 bots across two accounts and $10.7B of volume;
- 4.3x on starting capital;
- 48.7% of trades right on direction (51.7% once the grid bot is added), and an average win 1.4x the average loss.

It describes Bollinger Band breakouts near local and all-time highs, cut when price closes below the Bollinger midline, plus a grid "while waiting", and lists 15 rules. The user asked: "can you figure out their exact strategy from this summary, replicate it and test it on all of our assets?"

**Short answer.**

1. **Can their exact strategy be figured out from the summary? No.** A summary of outcomes does not pin down a rule set.
   - Six of the 15 rules (6 and 11-15) are patterns an AI mined from one trader's results, not decision rules.
   - We coded every ambiguous reading as a separate variant. **None of 78 variant-windows matches the post's statistics jointly (0 of 78), and every one of them trades at a different frequency.** The most active of the 39 rows checked against the post (section 2; F: 1-hour bars on the monthly top-10 coins) made 435 tranches (entries plus adds; 400 without ZEC) in the most likely 16 months, against the post's 1,462. Some cells of the 648-cell fit below do trade as often as the post, but none of them matches its hit rate.
   - A 648-cell fit to the post's numbers does not identify a rule set: the best-fitting cells disagree on which coins and on whether to short.
   - Random-entry decoys were never consistent either (0 of 2,740). Every one of the 78 has at most a third of the post's tranches, counting each entry and each add (474 at most, against 1,462), so by the pre-registered count none can be its strategy. By positions the most active row, F, reaches about two-thirds of the ≈490 the post implies, but no row is consistent on a position count either. On hit rate and win/loss the check discriminates poorly at 16-month sizes: two standard errors of the hit rate come to about 15 points either side at the median row, so 52 of the 78 pass on hit rate and 66 on win/loss, and a match would not have shown skill.
2. **Replicating it.** Our literal reading of the 15 rules (R0: BTC, ETH and SOL perpetuals at 3x) turned $1 into **$0.86 over the most likely 16 months** (2025-06-17 to 2026-10-16, one 16-month path), against the post's 4.3x.
   - Over the same months, an equal-weight buy-and-hold of the three coins made $0.82, and the repo's indicator (`moneyline_ref`, the version from before October 2026) on the same coins $1.11.
   - Over 2020-2026, R0 made 20.7x, against 39.7x for buy-and-hold and 72.1x for the indicator. Its Sharpe ratio was 1.07, against 1.08 and 1.44.
   - **Luck benchmark.** R0's 16-month result sits mid-pack among 1,000 versions with random entry days (55th percentile). None of the 4,000 random versions reached 4.3x.
3. **Testing it on all our assets: the four pre-registered verdicts**, in the order fixed in advance.
   - **What the verdicts mean.** PASS: a positive effect that survives allowing for the 12 tests run. NO EDGE: even a deliberately generous upper limit (wider than the 95% range, to allow for the 12 tests) is below a small threshold set in advance; "HARMS" when that limit is below zero. INCONCLUSIVE: the data cannot tell.
   - **Drift adjustment.** Each trade is compared with what the same exposure would have earned at the asset's long-run average return, so a positive result reflects timing rather than simply owning a rising asset.
   - **H1, crypto core edge: not shown; the data cannot tell (INCONCLUSIVE).** The core rules on BTC/ETH/SOL earned +3.7% of M per trade (M is a position's maximum size, with all three tranches filled) above what the coins' average drift would have paid. The 95% range runs from −1.2% to +8.7% per trade, so the test cannot tell an edge from none (after allowing for the 12 tests run, p = 0.80).
   - **H2, against buy-and-hold and the repo's indicator: the data cannot tell (INCONCLUSIVE).** On Sharpe ratio (return per unit of risk) the core was +0.09 against buy-and-hold and −0.27 against the indicator. Both intervals include zero.
   - **HS1, stocks: it does not work (NO EDGE (HARMS)).** On 43,811 S&P 500 trades, 2001-2026, the trades made +0.09% of M each before the drift adjustment, 0.64% less than the same exposure would have earned at the stocks' average drift. Its Sharpe ratio was 0.54 below an equal-weight hold of the same stocks. Both generous upper limits are below zero.
   - **HS2, ETFs: it does not work (NO EDGE).** On 14 ETFs the trades made +0.10% per trade before the drift adjustment and −0.19% after it. The generous upper limit, +0.06%, is below the +0.5% threshold.
   - "Their full strategy beats holding" cannot be said for any asset group. In mean log growth against 1x holding (one log point a year is about 1% a year of compound growth): crypto (R0 at 3x vs BTC/ETH/SOL) −7.1 log points a year (−52.4 to +38.6); stocks −9.0 (−14.7 to −3.6); ETFs −5.0 (−9.9 to −0.4).
   - **No version the user could actually trade got a TRADE verdict** from the repo's gate.

**What to do.**
- Don't adopt it, and don't swap the indicator for it.
- On the same three coins the repo's indicator (`moneyline_ref`, the version from before October 2026; the October 2026 "Bullmania MoneyLine" update was not tested here) was ahead on return, Sharpe and after-tax growth. The breakout core was not shown to beat it (Sharpe −0.27, interval −0.85 to +0.32).
- The post's 4.3x cannot be checked. A real track record (exchange statements for every account) would settle more than any further backtest.

---

## 1. What the post says, and what can be coded

The post cannot be traced: searches for "1,462 bots", "$10.7B" and its wording found nothing (`rules_and_evidence.md` §0). Every statistic in it is unverified and doubly selected: once by the AI that summarised a trade log, and again by whoever chose to post it.

**Decision rules vs mined patterns.**
- Rules 1-5 and 7-10 are decision rules (size, adds, leverage, coins, confirmation, exits, stop and take-profit) and can be coded.
- Rules 6 and 11-15 are patterns an AI found in about 70 weeks of one trader's results. Examples: "trades held over a week won 75%", "don't open on Friday or Saturday", the hour-of-day windows. They are tested here as hypotheses against placebo versions.

**What the numbers imply** (arithmetic on the post's figures, `rules_and_evidence.md` §2.3, §4):
- **Expectancy.** A 48.7% hit rate with wins 1.4x losses is +0.17 average losses per trade, a profit factor of 1.33. Break-even is a 41.7% hit rate.
- **Exits.** A 3R take-profit hit on every winner would give a win/loss ratio near 3. So most winners must have left on the midline exit.
- **Bots.** "1,462 bots" most likely counts each entry and each add as a bot: about 490 positions × 3 tranches.
- **Volume.** $10.7B is 950-19,000 times average equity for a $0.25-5M start. Only very frequent leveraged trading or grid churn produces that.
- **Window.** The most likely 16 months are 2025-06-17..2026-10-16 (**W16**). Over them BTC returned 0.78x, ETH 0.96x and SOL 0.70x buy-and-hold, and ZEC 27x. A long-only 4.3x in that window needs ZEC, several caught up-legs, or shorts.
  - The alternative window **W16b** (2024-06-30..2025-10-31) ends at the BTC high, where 4.3x is much easier.
  - Both are single 16-month paths, and every W16/W16b number below is one draw, not an estimate.

## 2. What was tested

**Pre-registration.** The design was pre-registered (`analysis_2026/BB_REPLICATION_PREREG.md`) and frozen on 2026-10-18, after a three-lens adversarial review (54 proposals). Three addenda settled build questions before any strategy return was read (Addendum 1 before any was computed; section 6). The engines were reviewed adversarially before the full runs. The results were then audited by independent recomputation from raw data, which reproduced every core number exactly (section 6).

| piece | what it is |
|---|---|
| **R0, the literal reading** | Binance USDT-margined perpetuals; BTC, ETH and SOL, one slot each (sleeve = equity/3). **Signal:** a fresh daily close above the upper Bollinger Band (20, 2), within 5% of the 60-day high or 10% of the all-time high; long only. **Size:** maximum notional M = 3 × sleeve; first tranche M/3; adds of M/3 at +2% and +5%. **Exits:** hard stop at SMA20 − 1 × ATR14; take-profit on half at 3R; exit on a daily close below the midline at the 13:00 New York window. **Timing:** entries at 06:00 New York, no new positions on Friday or Saturday; rules 6, 11 and 15 as written. **Costs and risk:** taker fees plus slippage, actual funding, isolated-margin liquidation on the mark price |
| **S1, the core** | R0 without the mined timing rules (6 and 12-15); entries and exits at 01:00 UTC. At 1x (S1, L = 1), the base of H1 and H2 |
| **Sensitivity grid** | 20 rows, each changing one thing: leverage, adds, band settings, near-high filter, 4-hour / 1-hour / weekly bars, stops, exits, long/short (S11), point-in-time universes re-ranked monthly (S12: the top 3 or 6 of the 40 coins, labelled "point-in-time ranks within a 2026 pool" because the 40 were chosen in 2026 and lack most coins that died earlier and many 2023-26 newcomers; and the top 10 among all Binance USDT perpetuals), squeeze filter, re-entry, sizing, and BTC/ETH/SOL/ZEC (S17, a hindsight what-if). Every row is in `results_bb/rows/rows.csv`; none is selected. **Row counts.** The 20 variations (S1-S20) expand to 39 rows checked against the post (H11: R0, the variants with their sub-rows, F, and R0 with G-A or G-B) and to 51 rows in `rows.csv` (the H11 rows without the two grid overlays, plus the 1x versions, the fee scenarios, the stress and stop-at-S rows, and S12's all-contract rows). This report quotes the rows that bear on the answer; section 3i lists the other pre-registered outputs |
| **F, frequency-matched** | The cell whose W16 tranche count (entries plus adds) is closest to 1,462, chosen on the count alone before any return was read: 1-hour bars on the monthly top-10 coins (`fcount/F.json`) |
| **Grid overlays** | G-A, the "waiting" grid: a neutral grid over the bands while the coin is flat near its high (the H10 test). G-B: each R0 tranche run as a grid. G-0: an always-on grid. All on 1-minute bars, 2024-07..2026-10, filled only when price trades through the level, maker fees, funding and liquidation |
| **Stocks and ETFs** | The same daily rules on point-in-time S&P 500 members including dead names (HS1, 2001-2026; a 20-slot portfolio), the repo's 14 ETFs (HS2; 14 slots), and the user's 7 tickers. Fills at the next session's open; 3 bp a side (10 bp for COIN, HOOD and CRCL); 1996-2000 reported separately |
| **US routes** | What a US resident could run: Robinhood spot (0.95% a side), spot BTC/ETH ETFs, US perpetual-style futures (0.10% assumed), and the stock version. Each goes through the repo's gate (`gate.py`, after 35%/20% tax, against SPY) |
| **Matching the post** | H11: 78 variant-windows checked against all the post's statistics jointly. H11b: a 648-cell labelled fit with random-entry decoys. H12: shorts vs long-only |
| **Luck** | 1,000 random-entry versions of R0 at 3x and 5x per window, keeping R0's adds, stops, exits and costs; and the months of record needed for t ≥ 2 |

**Tests and verdicts.** The 12 decision tests (H1-H10, HS1, HS2) form one Holm family at 5% one-sided. Each gets one of three verdicts:
- **PASS:** Holm p < 0.05, every other condition of the test's pass rule holds, and the point estimate is positive in both halves of the sample.
- **NO EDGE:** the upper confidence bound at 99.625% is below an economic threshold E (for a compound test, one component is enough), so an effect as large as E is ruled out. It is reported as "(HARMS)" when the bound is below zero. Only for H1, HS1 and HS2 may it be read as "it does not work" on that asset group. H8's NO EDGE rests on the 72-hour hold alone and says nothing about rule 15.
- **INCONCLUSIVE:** "the data cannot tell".

Trade-level effects are **drift-adjusted**. Each trade is charged what the same exposure would have earned from the asset's average drift, so a pass reflects timing rather than simply being long a rising asset.

**Controls all passed before any result was read** (`results_bb/controls/summary.txt`):
- **Engine known answer.** On martingale price paths, S1's and R0's mean trade return before costs is within 2 SE of zero over 27,218 and 23,859 trades (t 1.49 and 1.68). On trending paths S1 is positive (t 4.98). The grid's mean before fees is zero within noise, and negative after fees.
- **Look-ahead.** Prices after 110 random cut times were multiplied by 1.5. All 2,597,008 decisions stamped before each cut were unchanged.
- **Fill audit.** All 650,746 simulated fills lie inside their bars, with none in a zero-trade bar.
- **Liquidation.** Twelve hand-built cases match their hand-computed outcome: one liquidation at the computed price, or a stop where a working stop comes first.
- **Grid path.** The engine's grid P&L matches a 1-second simulation to 0.07% of gross grid profit (tolerance 10%).
- **Indicator cross-check.** The repo's indicator benchmark reproduces HANDOFF 5.14's BTC result to order of magnitude (6.6x vs 12.4x).
- **Inference known answer.** On 200 synthetic zero-drift paths, H1's test rejected 1.5% of the time (3 of 200).

**The inference widening.** In the same inference control, the bootstrap 95% bound missed the true mean 5.5% of the time (11 of 200), above the 5% allowed. As Addendum 2 requires, the bound's level was widened to 95.5% (miss rate 4.5%), and the NO EDGE level from 99.583% to 99.625% (`controls/inference.json`).
- Even widened, the far tail misses about 1.5% of the time at the NO EDGE level, against a nominal 0.375%.
- No NO EDGE verdict is close enough to its threshold for this to matter (section 3a).

## 3. Results

### 3a. The 12 pre-registered tests

Source: `results_bb/verdicts.txt`, `verdicts.csv`, `primary/tests.json`.

**Units.**
- "% of M" is percent of a position's maximum notional M (all tranches at full size).
- H1 and the trade parts of HS1 and HS2 are per trade, drift-adjusted. H3 and H6-H8 are per signal and H4 per breakout episode, paired against the base arm; H5 is the per-trade difference between near-high and other breakouts. All are drift-adjusted.
- H2 and the second parts of HS1 and HS2 are differences in annualized Sharpe ratio, of daily returns in excess of T-bills.
- H9 is the difference in mean log growth a year, in log points (21.6 log points ≈ 21.6% a year of continuously compounded growth).
- H10 is the difference in account return, % of equity a year.
- The 95% CIs are two-sided. The "NO EDGE bound" is the one-sided 99.625% upper bound, which must sit below E for NO EDGE. Compound tests list both components.
- "Ruled out at 95%" is the largest effect the data rule out, one-sided (pre-registered for every test; `verdicts.txt`): a bootstrap-t bound at the widened 95.5% level for the trade and per-signal tests, and the 95% block-bootstrap bound for the portfolio tests (H2, H9, H10 and the Sharpe parts of HS1 and HS2). It uses a different method from the 95% CI, so it can sit just outside it (H1: +9.18 against a CI top of +8.67).

| test | the claim tested | estimate | 95% CI | Holm p | ruled out at 95% | NO EDGE bound vs E | MDE | verdict |
|---|---|---|---|---|---|---|---|---|
| **H1** core edge | S1 at 1x on BTC/ETH/SOL, 2020-2026, beats the coins' own drift, % of M per trade | +3.73 | −1.20 to +8.67 | 0.80 | +9.18 | +13.69 vs +0.5 | 8.53 | **INCONCLUSIVE** |
| **H2** vs benchmarks | S1 at 1x beats (a) equal-weight buy-and-hold and (b) the indicator, Sharpe | (a) +0.09; (b) −0.27 | (a) −0.59 to +0.90; (b) −0.85 to +0.32 | 1.00 | (a) +0.82; (b) +0.25 | (a) +1.34, (b) +0.58 vs +0.10 | (a) 1.26; (b) 0.99 | **INCONCLUSIVE** |
| **HS1** stocks | S&P 500 members: (a) per trade, % of M; (b) Sharpe vs equal-weight members | (a) −0.643; (b) −0.54 | (a) −0.784 to −0.501; (b) −0.86 to −0.19 | 1.00 | (a) −0.516; (b) −0.24 | (a) −0.435 vs +0.5; (b) −0.041 vs +0.10 | (a) 0.25; (b) 0.56 | **NO EDGE (HARMS)** |
| **HS2** ETFs | 14 ETFs: (a) per trade, % of M; (b) Sharpe vs equal-weight ETFs | (a) −0.193; (b) −0.37 | (a) −0.349 to −0.036; (b) −0.78 to +0.08 | 1.00 | (a) −0.038; (b) +0.02 | (a) +0.061 vs +0.5; (b) +0.30 vs +0.10 | (a) 0.28; (b) 0.74 | **NO EDGE** |
| H3 pyramiding | starting at a third and adding beats full size at entry, % of M per signal | +0.76 | −0.50 to +2.03 | 1.00 | +2.09 | +3.00 vs +0.25 | 2.19 | INCONCLUSIVE |
| H4 confirmation | a confirmed daily close beats an intrabar band touch, % of M per episode | −0.97 | −2.46 to +0.52 | 1.00 | +0.21 | +0.82 vs +0.25 | 2.58 | INCONCLUSIVE |
| H5 near-high filter | breakouts near highs beat the others, % of M per trade | −1.07 | −9.56 to +7.41 | 1.00 | +5.48 | +8.93 vs +0.25 | 14.77 | INCONCLUSIVE |
| H6 hour windows (rules 13-14) | the 06:00 / 13:00 New York windows beat 01:00 UTC, % of M per signal | +0.33 | −0.77 to +1.43 | 1.00 | +1.28 | +1.89 vs +0.25 | 1.89 | INCONCLUSIVE |
| H7 weekday (rule 12) | no Friday/Saturday opens helps, % of M per signal | −0.61 | −1.62 to +0.40 | 1.00 | +0.08 | +0.47 vs +0.25 | 1.74 | INCONCLUSIVE |
| H8 hold and Monday (rules 6, 15) | (a) a 72-hour minimum hold and (b) deferring weekend midline exits help, % of M per signal | (a) −0.026; (b) −0.081 | (a) −0.064 to +0.012; (b) −0.55 to +0.39 | 1.00 | (a) −0.003 (degenerate bootstrap); (b) +0.23 | (a) +0.010, (b) +0.36 vs +0.25 | (a) 0.07; (b) 0.81 | NO EDGE, via (a) only |
| H9 leverage (rule 4) | R0 at 3x grows faster than at 1x, log points a year | +21.6 | −5.3 to +46.3 | 0.80 | +43.4 | +54.9 vs +2 | 48.2 | INCONCLUSIVE |
| H10 grid overlay | R0 plus the waiting grid beats R0 alone, 2024-07..2026-10, % a year | −3.40 | −7.15 to +1.64 | 1.00 | +0.75 | +3.87 vs +1.0 | 7.96 | INCONCLUSIVE |

**Notes on the table.**
- **H1.** Before the drift adjustment the core made +6.80% per trade (95% CI +1.50 to +12.09). About half of that is what being long rising coins pays anyway.
  - The halves are +8.58% (2020-2022) and +0.62% (2023-2026): what there is sits in 2020-2022.
  - Dropping the single best month (2021-01) leaves +2.41%. The top 5% of trades carry 69% of total P&L (115% of the drift-adjusted P&L).
  - With quarter clusters or overlap-episode clusters instead of month clusters, the drift-adjusted mean's one-sided p before Holm is 0.062 or 0.049, against 0.067 with month clusters (pre-registered sensitivities; the verdict uses month clusters and Holm).
  - The MDE of 8.5% shows the test can only see a large edge. The post's own implied edge, about +1% of M per trade, was undetectable by design (pre-registration, power table).
- **H1's gates all held.** These conditions were required for a PASS but are not tests:
  - Over 677 trades on the other 37 coins of the repo's 40, the core made +5.32% per trade (95% CI −0.42 to +11.07). Without ZEC it made +4.74% (−1.08 to +10.56).
  - On the point-in-time top-3 coins among all Binance perpetuals it made +1.29% (−2.15 to +4.73).
- **Not a gate (exploratory).** In the 2017-2019 spot era, pooled over the 25 coins listed then (54 positions), the core made +0.80% per trade (−8.7 to +10.3), and +0.90% (−8.8 to +10.6) without ZEC (`primary/tests.json` H1 extra). On BTC/ETH alone (13 positions) it made +10.9% (+0.01 to +21.8; exploratory, Benjamini-Hochberg adjusted p 0.15; `rows/pre_perpetual.csv`).
- **H2.** Every Sharpe difference needs both halves positive to pass. Against the indicator, both halves are negative (−0.42 and −0.09).
  - In the 2017-2019 spot block on BTC/ETH (exploratory, not a pass condition), the core's Sharpe was +1.06 above buy-and-hold (−0.08 to +2.46; exploratory, not distinguishable from zero) and +0.42 above the indicator (−0.63 to +1.67).
- **H5.** The total drift-adjusted P&L is 4.42 M with the near-high filter off and 3.44 M with it on.
- **H6.** R0's hour pair ranked 63rd of 576 entry/exit hour pairs (66th after removing the effect of delay). Passing needed the top 28.
- **H7.** The Friday+Saturday block ranked 4th of 7 consecutive-day blocks.
- **H8.** The NO EDGE comes only from component (a), the 72-hour minimum hold, which changes 2 of 92 signals. Its bootstrap interval is degenerate (lower end −∞), but the analytic 99.625% bound is +0.026% of M, also far below E = 0.25%.
  - The pre-registered dose-response: minimum holds of 24 / 48 / 72 / 96 / 120 / 168 h give +0.0004 / −0.003 / −0.026 / −0.026 / −0.058 / +0.060% of M per signal, none distinguishable from zero (exploratory, BH p 0.95). 72 h and 96 h give identical results, so the hold rarely binds.
  - Rule 15's own component (b) has a bound of +0.36%, above E = 0.25%. **On its own, whether rule 15 helps the data cannot tell.**
  - The Saturday+Sunday deferral ranked 3rd of 7.
- **Expected by design.** The pre-registration expected H2, H9 and H10 to be INCONCLUSIVE whatever the truth.

### 3b. Headline results: R0, S1 and F against buy-and-hold and the indicator

Sources: `results_bb/headline/headline.csv`, `headline/benchmarks.csv`. Crypto, Binance perpetuals, costs and funding included, idle cash at 0%. Halves are slices of the full run. W16 and W16b are single 16-month paths. Hit rate and win/loss are per position. The multiple's 95% interval is a month-block bootstrap.

**Benchmarks.**
- **Buy-and-hold** is equal-weight BTC/ETH/SOL, one third each, rebalanced daily.
- **Indicator** is the repo's `moneyline_ref` daily signal (the pre-October-2026 version), long/flat at full sleeve on the same perpetuals, with S1's costs.
- F trades the monthly top 10. Its benchmarks are BTC/ETH/SOL's, which are not the same coins.

| strategy | window | multiple [95% CI] | CAGR | Sharpe | max DD | positions | hit | win/loss | buy-and-hold | indicator |
|---|---|---|---|---|---|---|---|---|---|---|
| **R0** (3x, all rules) | Full 2020-01..2026-10 | 20.68x [1.07, 535.8] | 56.2% | 1.07 | −50.4% | 87 | 36.8% | 2.41 | 39.66x | 72.12x |
| | 2020-2022 | 9.80x [1.05, 117.6] | 113.9% | 1.57 | −49.7% | 35 | 37.1% | 2.92 | 7.09x | 20.58x |
| | 2023-2026 | 2.11x [0.38, 16.4] | 21.8% | 0.62 | −50.4% | 52 | 36.5% | 2.25 | 5.60x | 3.50x |
| | **W16** (single path) | **0.86x** [0.44, 1.83] | −10.5% | −0.05 | −40.9% | 18 | 27.8% | 1.93 | 0.82x | 1.11x |
| | W16b (single path) | 0.93x [0.39, 2.49] | −5.2% | 0.15 | −39.3% | 22 | 27.3% | 2.45 | 1.49x | 0.92x |
| **S1** (1x, core) | Full | 5.74x [1.54, 25.9] | 29.4% | 1.17 | −23.0% | 92 | 35.9% | 4.09 | 39.66x | 72.12x |
| | 2020-2022 | 2.96x [1.05, 9.98] | 43.6% | 1.47 | −23.0% | 36 | 33.3% | 5.33 | 7.09x | 20.58x |
| | 2023-2026 | 1.94x [0.94, 4.63] | 19.1% | 0.89 | −15.3% | 56 | 37.5% | 3.52 | 5.60x | 3.50x |
| | W16 (single path) | 1.01x [0.80, 1.33] | 0.8% | 0.09 | −14.9% | 20 | 25.0% | 3.20 | 0.82x | 1.11x |
| | W16b (single path) | 1.08x [0.73, 1.64] | 5.9% | 0.33 | −14.9% | 24 | 33.3% | 2.53 | 1.49x | 0.92x |
| **F** (1-hour bars, monthly top 10, 3x) | Full, with ZEC / without | 2.99x [1.20, 9.04] / 2.80x [1.12, 8.56] | 17.5% / 16.4% | 0.95 / 0.91 | −17.4% | 1,520 / 1,498 | 23.5% / 23.4% | 4.31 / 4.26 | 39.66x | 72.12x |
| | 2020-2022 (no ZEC traded) | 1.92x [0.92, 5.12] | 24.2% | 1.10 | −14.2% | 595 | 24.4% | 4.44 | 7.09x | 20.58x |
| | 2023-2026, with / without ZEC | 1.56x [0.96, 2.75] / 1.46x [0.88, 2.61] | 12.4% / 10.5% | 0.81 / 0.71 | −10.3% / −12.2% | 925 / 903 | 22.9% / 22.8% | 4.26 / 4.17 | 5.60x | 3.50x |
| | W16, with / without ZEC (single path) | 1.17x [0.96, 1.51] / 1.09x [0.87, 1.44] | 12.2% / 6.9% | 1.03 / 0.69 | −7.6% / −11.1% | 314 / 292 | 21.7% / 21.2% | 4.91 / 4.59 | 0.82x | 1.11x |
| | W16b (single path; no ZEC traded) | 1.32x [0.94, 2.04] | 23.3% | 1.31 | −8.7% | 321 | 23.4% | 4.81 | 1.49x | 0.92x |

**After 35%/20% tax, Full window** (`headline.csv` `cagr_tax_pct`):
- R0 39.0% a year, S1 20.5%, F 11.8% (11.1% without ZEC).
- Buy-and-hold 66.5%, the indicator 67.6%, SPY 13.9%.
- In W16: R0 −10.5%, S1 +0.5%, buy-and-hold −13.9%, the indicator +5.5%, SPY 19.3%.

**Read with the table.**
- **R0's trades.** All 87 of R0's positions came from 163 signals. They exited on the midline (58), the stop (18), or the take-profit followed by the midline (11). The median hold was 415 hours. No position was liquidated (`rows/trades.csv`, gitignored; `headline.csv` logs).
- **The rest of the grid** (`rows/rows.csv`). Across the 51 rows of the sensitivity table, Full-window multiples run from 1.12x (1-hour bars) to 131.9x (BB(50, 2)).
  - No row's drift-adjusted mean survives the Benjamini-Hochberg adjustment within the table (smallest adjusted p 0.26).
  - **Two band settings beat the indicator on both multiple and Sharpe over 2020-2026.** R0 with BB(50, 2) made 131.9x (Sharpe 1.65) and with BB(50, 2.1) 130.8x (Sharpe 1.67), against the indicator's 72.1x (1.44). Their drift-adjusted means are +9.1% (+1.7 to +16.5) and +10.6% (+2.3 to +18.8) of M per trade, but they are the best 2 of 51 rows, neither survives the adjustment (adjusted p 0.26), and in W16 they made 0.93x and 1.02x. Picking the best row after the fact is not evidence that it will repeat. One more row ended above the indicator's multiple but not its Sharpe: R0 without the near-high filter (S7) made 75.4x (Sharpe 1.26), and 0.49x in W16.
  - In W16 every row lies between 0.49x (no near-high filter) and 1.74x (4-hour bars), except the ZEC what-if (S17): 8.96x with ZEC, 0.88x without it.
  - With ZEC, the S12 top 6 (point-in-time ranks within a 2026 pool) made 1.15x in W16 and the all-contract top 10 made 1.10x. Without ZEC they made 0.69x and 0.80x.
- **All 40 coins, each traded alone** (`rows/per_coin.csv`, S1 at 1x).
  - Over the Full window the pooled drift-adjusted mean is +5.13% per trade (+4.61% without ZEC).
  - In W16 it is +2.11%, but −2.46% without ZEC. ZEC alone made 16.99x in W16 on 4 positions.
- **R0 itself on each coin as its own account** (`rows/per_coin.csv`, 3x, rule-11 sizing, one slot).
  - Over 2020-2026, 26 of the 40 coins ended below 1x, and 11 lost 95% or more: TRX, AAVE, ZEC, UNI, XTZ, EOS and EGLD went to about 0, and XLM, ICP, FIL and ETC ended at 0.05x or less. The median coin ended at 0.37x, with 4 liquidations (AAVE, XTZ, EOS, EGLD). In W16, 26 of 40 ended below 1x (median 0.83x).
  - Yet the pooled average trade was positive: +5.95% of M drift-adjusted (+0.19 to +11.7), and +5.51% (−0.31 to +11.3) without ZEC; exploratory. Profitable average trades with ruined accounts point to the leverage and sizing.
  - Exposure peaked at 181x equity on TRX and 152x on UNI. After a loss, rule 11 as coded keeps sizing from the month's starting equity, with no check that the margin fits current equity (`bb_engine.py` coding choice 17). A real exchange would refuse margin above equity, so this is partly a limit of the simulation, but it shows what the literal sizing does when one coin is the whole account. TRX, UNI and ZEC reached 0 with no liquidation, which in this engine is possible only when that sizing put margin above equity. Leaving those three out, 8 of 40 coins lost 95% or more, 4 of them through liquidation.
- **2017-2019, spot only** (`rows/pre_perpetual.csv`). S1 at 1x made 1.66x on BTC/ETH, and 1.07x on the 25 coins listed then (1.07x without ZEC).
- **TradingView cross-check** (`tv/stats.csv`; close-only exports, the basis of HANDOFF 5.1). Here S1's multiple trails both the exported indicator and buy-and-hold on BTC, ETH, BNB and ZEC:
  - BTC: 36.2x, against 415x for the indicator and 278x for buy-and-hold.
  - ETH: 70.4x vs 1,309x vs 181x.
  - BNB: 35.2x vs 7,779x vs 8,184x.
  - ZEC: 8.3x vs 12.3x vs 15.5x.
  - SOL is the one exception: 6.6x, against 11.9x for the indicator and 2.4x for buy-and-hold.

### 3c. The rule scorecard

Sources: `results_bb/scorecard/scorecard.csv`, `scorecard_detail.csv`, `primary/tests.json`.
- Rules in the Holm family take their test's verdict. The others are descriptive, over BTC/ETH/SOL 2020-2026.
- Effects are on mean net return per trade, % of M, unadjusted, as the scorecard reports them. Holm-family rules quote the test's drift-adjusted estimate.
- **"No detectable effect" means the interval spans zero.** It is not a finding that the rule is useless.

1. **Set the maximum size first; start with a third.** No detectable effect on the trade mean: R0 minus full size at entry (S4) is +0.19% (−1.04 to +1.41). Sleeve Sharpe favours starting small (R0 minus S4 +0.22, 95% CI +0.05 to +0.53; exploratory). S4's worst drawdown was −74.5% against R0's −50.4% (`rows/rows.csv`).
2. **Add only at +2-5% profit.** H3 INCONCLUSIVE: +0.76% per signal (−0.50 to +2.03). R0 minus adds measured as return on margin (S5) is −0.27% (−0.84 to +0.30).
3. **Never average down.** A no-op as coded: R0's re-entry rule already requires a fresh signal, and the alternative row (S18) is identical to R0.
4. **Keep leverage at 3-5x.** H9 INCONCLUSIVE (section 3d).
5. **Stick to a few liquid coins.** No detectable effect: R0 on BTC/ETH/SOL minus the same rules on the monthly top 3 of the 40 coins (point-in-time ranks within a 2026 pool) is +2.95% (−4.11 to +10.02); minus the top 6 of the same pool +2.52% (+3.20% without ZEC); minus the all-contract top 10 −0.11% (+0.33% without ZEC).
6. **Hold winners at least 3 days.** A no-op as coded in R0: the literal rule suppressed 0 midline exits. As a 72-hour minimum hold (H8a) it is NO EDGE. **That verdict comes from the hold binding on only 2 of 92 signals.** It does not show that holding winners is useless.
7. **Wait for confirmation.** H4 INCONCLUSIVE: the confirmed close minus the intrabar touch is −0.97% per episode (−2.46 to +0.52). The point estimate favours the touch.
8. **Exit in one or two pieces.** No detectable effect: R0 minus all at the take-profit is +0.91% (−0.60 to +2.41); R0 minus no take-profit −0.35% (−1.55 to +0.85).
9. **Cut all of it when wrong.** Not testable: it is built into every row.
10. **A wide stop and a take-profit of at least 3R.** No detectable effect: R0 minus a lower-band stop is −0.29% (−1.01 to +0.44); R0 minus a 2.5-ATR stop −0.77% (−1.76 to +0.22); the take-profit variants as in rule 8.
11. **Don't size up after a big month.** No detectable effect: the same trades, with a sleeve-Sharpe difference (R0 minus plain compounding) of −0.03 (−0.18 to +0.08). Plain compounding (S19) ended at 28.3x against R0's 20.7x.
12. **Don't open on Friday or Saturday.** H7 INCONCLUSIVE: −0.61% per signal (−1.62 to +0.40). The block ranked 4th of 7.
13. **Enter 3.5 h before or 30 min after the US open.** H6 INCONCLUSIVE: +0.33% (−0.77 to +1.43). R0's pair ranked 63rd of 576.
14. **Close 3.5-5.5 h after the US open.** Tested jointly with rule 13 in H6: INCONCLUSIVE.
15. **Don't cut on Monday because of the weekend.** H8 carries NO EDGE only through component (a); **rule 15 alone: the data cannot tell.** Its estimate is −0.08% per signal (−0.55 to +0.39), with a bound of +0.36% above E. The Saturday+Sunday deferral ranked 3rd of 7.

### 3d. Leverage (rule 4, H9)

Sources: `primary/tests.json` H9, `primary/H9_by_L.csv`. Three-slot BTC/ETH/SOL account, 2020-2026, idle cash at the T-bill.

| L | growth (log points a year) | average / peak exposure (× equity) | trades capped to keep the stop above liquidation | worst drawdown | liquidations |
|---|---|---|---|---|---|
| 1 | 25.4 | 0.17 / 1.02 | 0 of 87 | −20.2% | 0 |
| 2 | 40.6 | 0.31 / 2.03 | 1 | −35.7% | 0 |
| 3 (R0) | 47.0 | 0.42 / 3.07 | 8 | −49.3% | 0 |
| 4 | 49.3 | 0.51 / 3.77 | 25 | −58.3% | 0 |
| 5 | 48.5 | 0.56 / 4.23 | 47 | −62.2% | 0 |

**The test.**
- **H9's point estimate is +21.6 log points a year for 3x over 1x (95% CI −5.3 to +46.3), but the verdict is INCONCLUSIVE.** The NO EDGE bound is +54.9, far above E = +2. The halves are +36.4 and +9.9.
- The growth-optimal L is 4, with a 90% bootstrap interval from 2 to 5. The upper end is censored at 5, the largest L tested.
- The 1x account's mean-to-variance ratio is 4.36. With no liquidations, H9 is close to testing whether that ratio exceeds 2.

**Reading.**
- **"3x" here is not 3x of the account.** R0 sizes each coin's slot so that a full position is 3x the sleeve, and caps leverage per trade so the stop sits at least 2 points above liquidation. Average account exposure is therefore only 0.42x.
- That is why the three-slot account does not contradict HANDOFF 5.14, where 3-5x on whole sub-accounts blew up 85-100% of coins. Run on one coin as the whole account, the same rules lost 95% or more on 11 of 40 coins in the simulation, though on TRX, UNI and ZEC, which reached 0 with no liquidation, the coded sizing put margin above equity (exposure up to 181x on TRX), which an exchange would refuse. Without those three it is 8 of 40, 4 through liquidation (section 3b).
- **The three-slot account had no liquidations at any L.** The cap makes liquidations rare (the pre-registration says "near zero by construction"), not impossible: the same rules had 4 liquidations on single-coin accounts (section 3b), and the long/short row S11 had 1 (section 5).
- **The 2025-10-10 stress row is vacuous.** The pre-registered row makes every stop fail during that crash. R0 had no BTC/ETH/SOL position open between 20:00 and 23:00 UTC, so the stress row equals R0 (20.68x), and R0's stop list for that day is empty (`rows/stops_2025-10-10.csv`).
- The crash did hit other rows (`rows/trades.csv`):
  - S1's BTC position was stopped for −5.4% of M.
  - The monthly top-6 and top-10 universes' BNB position was stopped for −21.5% of M.
- **A non-PASS here is not evidence that leverage lowers growth.**

### 3e. The grid (H10)

Sources: `primary/tests.json` H10, `explore/grid_summary.csv`, `explore/grids.csv`. 1-minute bars, 2024-07-01..2026-10-16. Grid P&L is in units of the coin's sleeve.

**H10 is INCONCLUSIVE.**
- R0 plus the waiting grid (G-A) earned **−3.4% of equity a year** relative to R0 alone (95% CI −7.2 to +1.6).
- The account ended at 0.84 with the grid against 0.92 without it.
- Both halves were negative: −1.5% (2024-07..2025-08) and −5.4% a year (2025-09..2026-10).
- Fees are not the main cause. At the trader's likely VIP fee tier the difference is −3.2% a year, and with no fees at all −2.8%.

**Grid profit is not profit.** The grid's realized "grid profit" is real cash, but the inventory it carries gives it back. G-A per coin sleeve (net = grid profit + inventory P&L − fees + funding received):

| coin | deployments | grid profit | inventory P&L | fees | funding received | net |
|---|---|---|---|---|---|---|
| BTC | 16 | +0.157 | −0.177 | 0.016 | +0.002 | −0.034 |
| ETH | 8 | +0.118 | −0.191 | 0.011 | −0.001 | −0.085 |
| SOL | 7 | +0.088 | −0.132 | 0.009 | +0.000 | −0.054 |

- **The always-on grid (G-0).** It shows the same short-volatility identity at scale. On BTC, grid profit was +1.016 and inventory P&L −1.011 per sleeve; on ETH +1.878 and −2.104.
  - Net of base fees it lost 12.5% a year relative to T-bills (95% CI −29.1 to +4.5); with zero fees, 4.7%.
- **The other overlays** (exploratory):
  - The six-coin waiting grid lost 1.9% a year (−3.4 to −0.2).
  - G-B (each tranche as a grid) ended at 1.08x against R0's 0.92x over 2024-07..2026-10, with a smaller worst drawdown (−30.5% against −47.8%) and a higher Sharpe (0.10 against 0.07). It also ended higher in W16 (0.96x against 0.86x) and W16b (1.03x against 0.93x), and its net grid P&L was positive on ETH (+0.062 of a sleeve) and SOL (+0.027), negative on BTC (−0.018). But its mean daily difference from R0 is −0.5% a year (−18.4 to +21.0), so it cannot be told from zero.
- **Hit rate.** The post's "+3 points of hit rate with the grid" is how a grid's ledger looks, and is not by itself evidence of profit. Adding G-A changed R0's tranche hit rate by +1.4 points in W16 and −0.4 in W16b, and the account lost money. G-B changed it by +7.7 and +8.5 and ended higher, but its difference from R0 cannot be told from zero (single paths; `h11/h11.csv`).

### 3f. Stocks and ETFs (HS1, HS2)

Sources: `primary/tests.json` HS1/HS2, `headline/headline.csv`, `explore/stocks.csv`, `headline/answer_map.csv`.

**HS1, point-in-time S&P 500 members 2001-2026: NO EDGE (HARMS). It does not work, and the result is negative.**

**Before and after the drift adjustment.**
- **Unadjusted, the trades made +0.09% of M each** (95% CI −0.08 to +0.26), on 43,811 trades: every signal that could be entered, each member its own slot, no position cap (116,711 signals in all). 43,810 of the trades carry a drift charge.
- The drift charge averages 0.73% of M per trade. That is what the same exposure would earn at each stock's long-run average daily return, measured over its whole price file excluding the holding period and 182 days on either side. **Drift-adjusted, they made −0.64%** (−0.78 to −0.50).
  - The audit found the charge sensitive to how that average is measured: using each name's membership days only would move the estimate about 3 SE toward zero (−0.46% against −0.67%, before the hygiene fix in section 6), with the same verdict. The Sharpe part does not use drift.
- Even the unadjusted interval's top, +0.26%, is half the +0.5% threshold.
- Dropping the most helpful month (2020-11) leaves −0.66%. The top 5% of trades carry 8.4 times the small positive unadjusted total P&L, so the other 95% lose money on net.

**The Sharpe part.**
- The 20-slot portfolio's Sharpe was 0.54 below an equal-weight hold of the same members (−0.86 to −0.19). Its bound is −0.04, also below zero, so each part would give HARMS on its own.
- **The Sharpe part does not use the drift adjustment**, so NO EDGE does not depend on the drift charge (unadjusted, the trade part's bound is +0.34%, still below +0.5%). HARMS without the drift charge is marginal, though: it then rests on the Sharpe bound alone, which is close to zero (−0.04 as decided, the larger of the 1- and 3-month block bounds; +0.05 with the 12-month blocks also reported).

**Robustness and sources of the loss.**
- **Seeds.** Over 100 further random slot-filling seeds the Sharpe difference has a median of −0.57 (5th-95th percentiles −0.64 to −0.49).
- **Halves.** Both are negative: per trade −0.62% and −0.66%; Sharpe −0.72 and −0.36.
- **Other versions.** Filling slots by the (close − upper band)/ATR ranking instead of at random gives a Sharpe difference of −0.65 (−0.96 to −0.30); with idle cash earning nothing in both arms, −0.52 (−0.83 to −0.16).
- **Signal vs concentration** (exploratory). A random-entry book with the same slot count and holding times is −0.12 (−0.36 to +0.18) against the benchmark. The breakout book is −0.42 (−0.72 to −0.11) against that random book, so, in this exploratory comparison, **the entry signal did worse than random entries.**

**Account view** (idle cash at the T-bill).
- The 20-slot book turned $1 into 1.28 over 2001-2026 (0.96% a year, max drawdown −36.4%). The equal-weight members made 13.05 (10.5% a year, −59.1%).
- After tax: 0.64% a year against SPY's 8.58%.
- In log growth, the book trails the members by 9.0 points a year (−14.7 to −3.6), in both halves.
- **Leverage and costs.** Doubled costs make it worse, and 2x margin turns the book into 0.75x.

**HS2, the 14 ETFs: NO EDGE. It does not work.**
- **Per trade.** The trades made −0.19% of M each after the drift adjustment (−0.35 to −0.04); unadjusted +0.10% (−0.07 to +0.28). The trade bound, +0.06%, is far below E.
  - Dropping the most helpful month (2025-12) leaves −0.22%. The top 5% of trades carry 4.1 times the small positive unadjusted total P&L.
- **Sharpe.** The 14-slot book's Sharpe part is −0.37 (−0.78 to +0.08). Its bound (+0.30) is above E, but one component meeting the bound is enough.
- **Account.** The book made 1.64 over 2001-2026 with idle cash at the T-bill (1.94% a year). The equal-weight ETFs made 5.99 (7.19% a year).
  - Most of the book's return is T-bill interest: with idle cash at 0% it made 1.10 (0.36% a year, `routes/summary.csv`).
  - Log growth is 5.0 points a year below holding (−9.9 to −0.4).

**Data caveats.**
- **1996-2000** is reported separately, outside every pass rule. Members lost there as well: −0.43% per trade (−0.83 to −0.02), Sharpe −0.88 (−1.66 to −0.03). Those years cover only about 80% of member-days.
- **Close-only data.** Member prices come partly from close-only (CRSP) rows, which can create no signal (Addendum 2). They are 16% of member-days in 2001-2013 and 33% in 1996-2000, so the early sample under-samples breakouts.
- **No intraday stock data.** The repo has no hourly stock data, so the stock version fills at the next session's open, not at the post's 10:00 and 13:00 New York times.

### 3g. The user's tickers

Sources: `explore/stock_tickers.csv`, `routes/gate.csv` (Stocks route).
- The book is a single-ticker 1x book with idle cash at the T-bill. Buy-and-hold is total return.
- **The after-tax CAGRs are on a different basis from the book.** They come from the gate's route account (`routes/gate.csv`), where idle cash earns 0%, with the full trading mechanics at 35%/20% over each ticker's own history; SPY's is over the same dates. SPY's route account made 1.03x before tax (0.11% a year) against the book's 1.52x, and TSLA's 18.5x against 23.1x. So most of the gap between SPY's book and its 0.07% after-tax CAGR is the missing T-bill interest, not tax.
- **Tickers with fewer than 20 trades are reported but not interpreted** (pre-registration).

| ticker | trades | drift-adjusted mean per trade [95% CI] | book vs buy-and-hold (idle cash at the T-bill) | gate | after-tax CAGR, route account with idle cash at 0%: strategy / hold / SPY |
|---|---|---|---|---|---|
| TSLA | 40 | +5.89% [−0.13, +11.91] | 23.1x vs 285.4x | NO-SIGNAL | 14.0% / 40.3% / 13.6% |
| COIN | 11 (< 20: not interpreted) | +9.09% [−2.92, +21.11] | 3.05x vs 0.74x | PROBATION (fails only the history test) | 13.3% / −5.6% / 11.9% |
| HOOD | 14 (< 20: not interpreted) | +1.98% [−6.50, +10.46] | 1.81x vs 2.65x | NO-SIGNAL | 5.3% / 18.4% / 11.5% |
| CRCL | 1 (< 20: not interpreted) | −8.37% | 0.98x vs 0.60x | NO-SIGNAL | −6.2% / −36.3% / 16.7% |
| SPY | 96 | −0.38% [−0.56, −0.21] | 1.52x vs 9.39x | NO-SIGNAL | 0.07% / 8.32% / 8.58% |
| QQQ | 103 | −0.49% [−0.82, −0.17] | 1.51x vs 15.18x | NO-SIGNAL | 0.05% / 10.61% / 8.58% |
| IWM | 106 | −0.57% [−0.94, −0.21] | 1.17x vs 8.09x | NO-SIGNAL | −0.99% / 7.79% / 8.58% |

**The ETFs one by one.**
- Of all 14 ETFs, only 4 have a positive point estimate: TLT +0.01%, LQD +0.03%, GLD +0.36% and SLV +0.77% per trade, all with intervals spanning zero. VNQ is the worst at −0.93%.
- Every one of the 14 single-ETF books ended below its own buy-and-hold.
- These per-ticker p-values are exploratory and Benjamini-Hochberg adjusted within the table. None survives: TSLA's 0.027 becomes 0.55.

### 3h. Can the post's numbers be matched? (H11, H11b)

Sources: `results_bb/h11/summary.json`, `h11/h11.csv`, `h11/oow.csv`, `h11b/summary.json`, `h11b/cells.csv`.

**The H11 rule.** A row is consistent with the post only if all of these hold:
- its hit rate and both holding shares are within 2 standard errors of the post's;
- the post's win/loss ratio and 4.3x lie inside the row's 95% intervals;
- its tranche count (entries plus adds) is between 0.5x and 2x of 1,462.

**Result: 0 of 78 variant-windows are consistent** (39 rows × W16 and W16b), and 0 without ZEC. **Every one fails the count**, and each also fails at least one other statistic. Random-entry decoys were never consistent (0 of 2,740), so the expected number of chance matches is also 0.

Per tranche (each entry and each add):

| | the post | R0, W16 | S1, W16 | F, W16, with / without ZEC | R0, W16b | F, W16b |
|---|---|---|---|---|---|---|
| tranches | 1,462 | 39 | 43 | 435 / 400 | 47 | 474 |
| positions | ≈ 490 | 18 | 20 | 314 / 292 | 22 | 321 |
| hit rate | 48.7% | 35.9% | 39.5% | 32.0% / 31.0% | 38.3% | 36.3% |
| average win / average loss | 1.4 | 1.33 | 1.56 | 2.84 / 2.71 | 1.48 | 2.51 |
| account multiple | 4.3x | 0.86x | 1.01x | 1.17x / 1.09x | 0.93x | 1.32x |
| > 7-day tranches that won | 75% | 41% | 46% | none held > 7 days | 47% | none held > 7 days |
| profit share of ≥ 3-day trades | > 80% | undefined (net P&L ≤ 0) | 100% | 6% / 11% | undefined | 4% |
| volume / average equity | 950-19,000x | 26x | 29x | 87x / 80x | 30x | 93x |

- No H11 row comes close to the post's volume: the highest turnover of the 39 rows is 183x (S16, 1-hour bars on BTC/ETH/SOL, W16b), and daily-bar cells of the fit below reach at most 112x. Some 1-hour cells of that fit do reach the post's volume and count (below), but none of them matches its hit rate.
- **The holding shares say nothing about the entry rule.** Among R0's random-entry versions in W16, counting winning trades only, ≥ 3-day trades made 80% or more of the profit in 94% of versions (`luck/distribution.csv`).

**H11b, the closest match (a labelled fit, exploratory).** Every combination of bar size, band setting, near-high filter, adds, exits, universe and direction was run at 3x: 648 cells.
- **W16.** The identified set holds 16 cells (2.5%) and 0 of 1,320 decoys. The best cell, at a distance of 37.6 (set threshold 50.1), uses 4-hour bars, BB(20, 2.5), adds measured on margin, no take-profit, and long and short on the monthly top 10.
- **W16b.** The set holds 21 cells (3.2%) and 0 of 1,420 decoys. The best cell, at a distance of 18.2 (set threshold 30.8), uses 4-hour bars, BB(20, 2.5), no near-high filter, adds measured on margin, a take-profit on half, and long only on the monthly top 6 (point-in-time ranks within a 2026 pool). It differs from W16's best on universe and direction.
- **The set is not one rule set.** In both windows every cell in it uses 4-hour bars, but the cells **disagree on the coins** (BTC/ETH/SOL, top 6, top 10), **on direction** (long only vs long/short), and **on the grid** (G-A is best in most cells, none or G-B in the others). By the rule fixed in advance, **the post's statistics do not identify a strategy.**
- **Without ZEC** the W16 set shrinks to 8 cells (1.2%). ZEC was not traded in W16b, so that set is unchanged.
- **Unscorable cells.** The 216 one-hour cells per window hold no position over 7 days, so the 7-day statistic is undefined and their distance is infinite. Other cells have an infinite distance because the closed trades' total P&L is ≤ 0, which the rule counts as a failure. In all, only 262 (W16) and 243 (W16b) cells have a finite distance. Leaving out only the cells excluded by the 7-day statistic alone (146 and 117), the set's share is 3.2% and 4.0%, still under 5%.
- **Count and volume.** Some cells of the fit trade as often as the post or more (up to 7,518 tranches in W16): 116 (W16) and 115 (W16b) cells are inside the 0.5-2x tranche band, mostly 1-hour and the rest 4-hour. Only 1-hour cells reach the post's volume: 44 and 49 cells are inside 950-19,000x, up to 2,481x (W16) and 2,588x (W16b). None of the cells inside the count band matches the post's hit rate, and their multiples were at most 1.97x (W16; 1.56x without ZEC) and 3.53x (W16b; no ZEC traded).
- **Returns of the best matches** (fitted, in-window). The set's cells made 1.14-2.66x in W16 (1.13-1.93x without ZEC) and 1.19-3.54x in W16b (no ZEC traded). Of all 1,296 cell-windows at 3x, one reached 4.3x: a W16b cell (4-hour BB(10, 1.9), no adds, monthly top 6 of the 2026 pool, long only, no ZEC traded) at 5.05x. It is not in the set, and its hit rate, win/loss ratio and tranche count do not match the post's.
- **The set at 5x and with grids** (`h11b/set_extras.csv`, fitted, one path each). Run at 5x, seven W16b set cells passed 4.3x (4.40-6.75x; 4-hour bars, four on the all-contract top 10 and three on the top 6 of the 2026 pool, long only or long/short, no ZEC traded), and one W16 cell on that top 6, which traded ZEC, reached 4.33x (2.62x without ZEC). The top-6 results carry hindsight, because that pool of 40 coins was chosen in 2026; the top-10 ranking does not use it. With G-A or G-B added at 3x, the set's cells made at most 2.66x in W16 (1.93x without ZEC) and 3.60x in W16b.
- **Outside the 16 months** (`h11b/summary.json`, exploratory). The W16 set's median log growth was 41.7 points a year, against 26.4 for the median cell (the same without ZEC: no cell traded it in W16's out-of-window span, 2020-01..2025-06). The W16b set's was 5.9 against 28.0, and 3.2 against 22.9 without ZEC, which traded in W16b's out-of-window span 2025-11..2026-10. A good match to the post did not reliably mean better results elsewhere.
  - Across cells, the rank correlation between distance and out-of-window growth was −0.35 in W16 (−0.40 without ZEC; −0.15 over finite-distance cells, −0.03 without ZEC) and −0.06 in W16b (−0.06 without ZEC; +0.12 over finite-distance cells, +0.07 without ZEC). A negative value means closer matches did better out of window. In W16 that held over all cells and over finite-distance cells with ZEC (exploratory BH p < 0.05), but not over finite-distance cells without ZEC (p 0.74); in W16b no value is distinguishable from zero. None of this is evidence that a fitted cell works.

### 3i. Other pre-registered outputs

Every pre-registered row and output is in `results_bb/`. Among those not quoted above:
- **Stops filled at S** (`rows/rows.csv` R0_at_S): R0 made 20.90x over 2020-2026, against 20.68x with the primary stop fills.
- **Fee scenarios** (Full window; the VIP tier implied by the post's volume / no fees): R0 21.17x / 22.74x (base 20.68x); S1 at 1x 5.80x / 5.96x (base 5.74x); F 3.26x / 4.61x, and 3.05x / 4.29x without ZEC (base 2.99x / 2.80x).
- **S20 weekly bars on stocks** (`explore/stocks.csv`, exploratory): members −2.5% of M per trade drift-adjusted (−3.1 to −1.9), and the 20-slot book 5.26x against 13.05x for the equal-weight members; ETFs −0.43% (−1.36 to +0.50), book 2.16x against 5.99x.
- **Luck:** no random-entry version was liquidated, at 3x or 5x, in either window (`luck/summary.csv`).
- **H11's references:** every row's out-of-window results (`h11/oow.csv`) and each row's statistics on the driftless synthetic series, the no-skill reference (`h11/synthetic.csv`).
- **The other sensitivity rows** (Full window, `rows/rows.csv`): S3 with cross margin 20.68x (the same as R0); S7's other near-high filters 1.51-15.4x; S13 (squeeze filter) 1.32x; S14 (10:00 New York entries only) 24.1x; S15 (rule 6 as a binding 72-hour hold) 20.0x; S20 (weekly bars) on crypto 6.11x; S12's all-contract top 3 6.13x (6.34x with the TradFi perpetuals), and the monthly top 10 with the TradFi perpetuals 12.12x (9.02x without ZEC).
- **Further sensitivities:** R0 with idle margin at the T-bill (24.48x) and the separately run halves (`headline/headline.csv`); H2 with equal weights among the coins that have joined, and H10 at zero interest, with touch fills and with 1-, 3- and 12-month blocks (`primary/tests.json`); the other grids' touch-fill bounds (`explore/grids.csv`).

## 4. What the user could actually run

Source: `results_bb/routes/summary.csv`, `routes/gate.csv`.

US residents generally cannot use Binance perpetuals or grid bots, so these routes answer "could you trade it?". Each route's position series went through the repo's gate, after 35%/20% tax:
- **TRADE:** passes all of T1-T7.
- **PROBATION:** fails only T1, the history test (at least 7 years and 40 trades).
- **NO-SIGNAL:** fails anything else.

The spot routes use Binance spot history from 2017-08 (Addendum 2). The Coinbase-style route's data start in 2019-09, **so T1 caps it at PROBATION.** After-tax CAGRs are the full trading mechanics, with idle cash earning 0%.

| route | version | assets | TRADE / PROBATION / NO-SIGNAL | expected false PROBATION | after-tax CAGR | buy-and-hold after tax | SPY after tax | max DD |
|---|---|---|---|---|---|---|---|---|
| RH Robinhood spot (0.95% a side) | S1 | BTC/ETH/SOL | 0 / 0 / 3 | 0.00 | 17.8% | 46.0% | 13.7% | −24.5% |
| | S1 | 24 Robinhood coins / without ZEC | 0 / 3 / 21 · 0 / 3 / 20 | 0.20 | 12.3% / 10.7% | 31.3% / 29.7% | 13.7% | −26.1% / −24.9% |
| | R0 at 1x | BTC/ETH/SOL | 0 / 0 / 3 | 0.00 | 15.7% | 46.0% | 13.7% | −26.7% |
| | R0 at 1x | 24 coins / without ZEC | 0 / 4 / 20 · 0 / 4 / 19 | 0.24 | 11.9% / 10.5% | 31.3% / 29.7% | 13.7% | −22.2% / −24.6% |
| | without adds (S1 / R0 at 1x) | BTC/ETH/SOL | 0 / 0 / 3 | 0.00 | 16.7% / 12.9% | 46.0% | 13.7% | −29.2% / −41.0% |
| ETF spot BTC/ETH ETFs (0.02%) | S1 / R0 at 1x | BTC, ETH | 0 / 0 / 2 | 0.00 | 13.2% / 15.3% | 30.2% | 13.7% | −36.6% / −25.0% |
| CB US perpetual-style futures (0.10%) | S1 at 1x | BTC, ETH | 0 / 0 / 2 | 0.00 | 6.5% | 47.6% | 13.9% | −35.3% |
| | R0 at 1x / at 3x | BTC, ETH | 0 / 0 / 2 | 0.00 | 5.5% / 7.6% | 47.6% | 13.9% | −27.8% / −67.3% |
| Stocks, the stock version at 1x | | the user's 7 tickers | 0 / 1 / 6 | 0.05 | 1.8% | 14.8% | 8.6% | −8.3% |
| | | the 14 ETFs | 0 / 0 / 14 | 0.00 | 0.23% | 6.4% | 8.6% | −5.4% |

**No route produced a TRADE verdict anywhere,** so "you can trade it" cannot be said.
- **The PROBATION rows:**
  - Robinhood route: AVAX, DOT and UNI (S1), plus ADA (R0 at 1x). Each has only 11-20 trades.
  - Stocks route: COIN, with 11 trades.
- They pass every test but the history test. Each fails that test on its trade count (11-20 trades, below the 40 the gate requires), and AVAX, DOT, UNI and COIN also on years of history.
- **More PROBATIONs than chance would give.** The placebo expects 0.20 false PROBATIONs in the 24-coin Robinhood group for S1 and 0.24 for R0 at 1x on the table's basis (0.24 and 0.26 over 2020-2026), and 0.05 among the user's tickers. The Robinhood group has 3 and 4, about 15 times as many; if the coins were independent, a count that high would come by chance about 0.1% of the time or less. Under the gate's convention (AGENTIC_TRADING_PLAN section 5), PROBATION permits at most a small fixed size.
- **Why we still do not act on them.** Each rests on 11-20 trades. The same coins (AVAX, DOT, UNI) recur in every variant, so the variants are not separate evidence. The 24 coins are the ones Robinhood lists today, a choice made with hindsight. And the pre-registered answer allows "you can trade it" only for TRADE. COIN, one of the user's tickers, also falls under the pre-registered rule that results on fewer than 20 trades are reported but not interpreted.
- **Every route's pooled account trails buy-and-hold of the same assets after tax.** On the basis in the table (spot routes from 2017-08) the gap is 14-42 points a year on crypto; over 2020-2026, where `routes/summary.csv` also reports every spot route, it is 30-53 points (e.g. Robinhood S1 on BTC/ETH/SOL 19.3% vs 66.3%). On stocks it is 6-13 points.
  - Single assets can differ (`routes/gate.csv`): 6-11 of the 24 Robinhood coins beat their own hold after tax, depending on the version and basis, each on 30 trades or fewer (e.g. AVAX for S1, 66.0% vs 15.2%), and on the Stocks route COIN and CRCL did, on 11 trades and 1 (section 3g).
- **Not in the table** (`routes/summary.csv`): the no-adds versions of the 24-coin Robinhood route (0 / 3 / 21 for S1, 0 / 4 / 20 for R0 at 1x; 13.1% and 12.4% a year after tax) and of the ETF route (14.3% and 16.4%), all with 0 TRADE.
- **The repo's indicator (`moneyline_ref`) passes the same gate for ETH via the spot ETF** (AGENTIC_TRADING_PLAN section 4). On that route, both breakout versions get NO-SIGNAL for BTC and for ETH.

## 5. What the trader probably did

**The record itself is unverifiable.** The post cannot be traced, and its numbers passed through two filters: the AI summariser picked what looked distinctive in a trade log, and someone chose to post the result. Leveraged accounts that blew up on 2025-10-10 do not post 16-month breakdowns.

**The trade log was most likely not a daily breakout on three coins.** No daily-bar variant trades often enough: turnover at most about 110x, and at most 183x among the 39 rows checked against the post. The post's volume, 950-19,000x average equity, needs grid churn or very frequent leveraged round trips. Only cells of the H11b fit trade as often as the post (116 cells in W16 and 115 in W16b inside the 0.5-2x count band, mostly 1-hour and the rest 4-hour; the most active cells made 7,518 and 7,689 tranches), and only 1-hour cells reach its volume (up to 2,481x in W16 and 2,588x in W16b). None of them matches the post's hit rate, and the cells inside its volume range ended far below 4.3x (at most 1.97x, 1.56x without ZEC). This points to intraday signals, many more coins, grid churn, or bots counted per restart (`rules_and_evidence.md` §2.3).

**How the 4.3x could have happened** (descriptive):
- **ZEC.** With ZEC added to BTC/ETH/SOL (S17, a hindsight what-if), R0's rules made 8.96x in W16, against 0.88x without it (`rows/rows.csv`). ZEC's buy-and-hold was 27x over those months (`rules_and_evidence.md` §4.3). ZEC is the only coin whose buy-and-hold reaches 4.3x in W16, and choosing it now uses hindsight.
- **Shorts** (H12, `h12/rows.csv`, `h12/diff.csv`, exploratory).
  - **In W16** the long/short version made 1.54x against R0's 0.86x. Its 11 short positions averaged +6.2% of M, and 64% of them won. The paired drift-adjusted difference was +4.3% per signal (−1.4 to +10.1; BH-adjusted p 0.25).
  - **Over 2020-2026** it ended higher, 29.0x against 20.7x (log growth +5.0 points a year, −28.9 to +36.8), with a Sharpe 0.06 lower (−0.47 to +0.43), a worst drawdown of −71.4% against −50.4%, and one liquidation.
  - In W16b it made 0.42x.
  - **Reading.** On the one falling 16-month path the long/short version did better, but the paired difference cannot be told from zero (BH p 0.25). Over 2020-2026 none of the differences is distinguishable from zero either.
- **Faster bars and more coins, fitted** (H11b, exploratory). Run at 5x, seven 4-hour cells of the W16b set made 4.40-6.75x with no ZEC traded (four on the all-contract top 10, three on the top 6 of the 2026 pool), and one 3x cell, also on that top 6, made 5.05x in W16b (section 3h). The top-6 results carry hindsight: that pool of 40 coins was chosen in 2026. Each is a single in-window path from a fit to the post, and none is consistent with the post's statistics jointly.
- **The other window.** If the 16 months ended at the 2025-10 high (W16b), buy-and-hold alone made 1.49x, and 4.3x needs much less skill (`rules_and_evidence.md` §4.4).
- **Luck** (`luck/summary.csv`). Random entry days with R0's other rules put R0's own result at the 55th percentile in W16 and the 58th in W16b. **None of 4,000 random versions reached 4.3x**, and 0-1.8% reached 2x. These rules on these coins did not reach 4.3x by luck either. If the 4.3x is real, something beyond the described rules on these coins carried it: ZEC, shorts, faster bars, more coins, more account-level leverage, or a different window.

**How many months of record would prove skill?** (`luck/months_needed.csv`)
- 4.3x in 16 months is +9.5% a month. A trader with R0's monthly swings would need this many months at that rate for t ≥ 2:

| | W16 swings | W16b swings | 2020-2026 swings |
|---|---|---|---|
| R0 at 3x | 4.5 months | 11.9 | 14.6 |
| R0 at 5x | 11.8 | 29.6 | 26.5 |

- **What it means.** If the record were real, from one account chosen in advance, and about as volatile as R0 at 3x, 16 months at 4.3x would be statistically distinguishable from zero.
- **What it does not mean.**
  - The test is against zero, not against holding the same coins with leverage.
  - The trader's actual volatility is unknown, and at 5x-like volatility 16 months may not be enough: it takes 11.8 months with the W16 swings, but 26.5-29.6 with the W16b or 2020-2026 swings.
  - A t of 2 is unremarkable for the best of the many accounts that might have been posted.
  - It says nothing about whether the record is genuine.

## 6. Deviations and corrections

Every change after the frozen pre-registration is listed with its reason. The addenda were all decided before any strategy return was read (Addendum 1 before any was computed); the pre-registration gives them in full.

**Addendum 1 (data layer; before any strategy return).**
- **Universe.** The monthly all-contract ranking (S12) excludes Binance's TradFi perpetuals (stocks, metals and FX from 2025-12), because rule 5 says coins. The literal ranking with them is reported as a sensitivity.
- **Delistings.** After a perpetual's last bar the coin is not tradable, so an open position is force-closed at that close, paying taker fee and slippage. The frozen text did not cover delisted contracts.
- **Signals.** S12 entrants that have spot markets take their signals from spot, as the signal row says; the Data section had listed only their perpetual files.
- **Margin.** The frozen text names Binance's lowest tier but no source for its rates. They come from an October 2026 snapshot of the tier tables; EOS, MATIC and YFII, missing from it, are assumed at 1.0%.
- **Code layout.** The code was split into `bb_*.py` modules; an organisational change that affects no result.

**Addendum 2 (engine; before any strategy return was read).**
- **S6.** The band rows change only the entry band. The stop and exit stay on SMA20 and ATR14, because each row "changes R0 as stated and nothing else".
- **Leverage of H3-H8.** They run at R0's L = 3, because only H1, H2 and the headline name S1 at L = 1; S1 and S1W otherwise change only what they state.
- **Inference control.** The frozen text said to widen the bound "until it does not" miss too often, without a rule. The control's mechanics and the widening rule (the smallest level that misses at most 5%, with the NO EDGE tail scaled by the same factor) were fixed. The control later triggered the widening, from 95% to 95.5% and from 99.583% to 99.625%.
- **Spot-route gate.** It uses Binance spot history from 2017-08 for the 7-year history test, because the Full window spans only 6.8 years. The Coinbase-style route cannot be extended, so T1 caps it at PROBATION.
- **H2's buy-and-hold.** It holds 1/3 per coin, as cash until the coin joins, to match S1's three-slot account and the window-edge rule.
- **HS2.** It uses 14 slots, one per ETF, because 20 slots of equity/20 could never fill on 14 ETFs.
- **Close-only rows.** Close-only member rows are flat bars, which under the frozen fill rules create no signal, entry or add; this is recorded as a caveat (section 3f).
- **Membership.** Stock membership is checked on the entry session, the day a position would open. The S&P 500 series for the gate's T2b test is extended back to 2001 with SPY, because the gate's own series starts in 2010-07.

**Addendum 3 (controls and reporting; before the controls ran for the record).**
- **Inference control.** Its size check passes at a point rejection rate of at most 5%, the reading Addendum 2 gives the same phrase for the bound.
- **Look-ahead control.** Account totals are compared exactly on rebuilt accounts, and to a relative 1e-12 on the full account, because a longer vector of zero-weight later positions changes floating-point summation by less than one unit in the last place.
- **Halves.** They are slices of the full run, so a trade that straddles the boundary is not truncated; separately run halves are a sensitivity.
- **F's benchmarks.** F on a monthly re-ranked universe is compared with BTC/ETH/SOL benchmarks, labelled, because no point-in-time buy-and-hold of a re-ranked universe is built.
- **Run order.** It is fixed, so that the controls and F's choice are settled before any result is read: controls, then F's counts, then the 12 tests, then descriptive rows, then the fit.

**Corrections after results (from the audit; no verdict changed).**
1. **Stock drift-sample hygiene (a real defect).**
   - **The problem.** The leave-out drift that the stock trades are charged was computed over raw price files. For three failed banks (FRC, SIVB, SBNY) those files run on after failure as penny-stock quotes, and two names (CHK, BTUUQ) have multi-year splices. These inflated those names' drift 5-40x.
   - **The fix.** The drift sample now drops returns across session gaps over 30 days and from or to closes below $0.01. Trade P&L is unchanged.
   - **The effect.** **HS1's trade part moved from −0.6712% to −0.6427% of M per trade**, and its bound from −0.463% to −0.435%. **The verdict is unchanged: NO EDGE (HARMS).**
   - Commits 39acaad (fix) and ae55c59 (rerun).
2. **H9's unit label (a real defect).** `verdicts.txt` called H9 "log points a year", but the values are natural-log units: +0.216 is 21.6 log points. E was coded on the same scale, so no verdict changes.
3. **Labelling clarifications.**
   - **H11 labels.** H11 rows now read "inconsistent (also different trading frequency)". The frozen wording reserves "different trading frequency" for rows that fail on count alone, and no row does.
   - **Scorecard rule 15.** It now notes that H8's NO EDGE comes only from component (a).
   - **Stock and ETF headline rows.** They now state their basis: account statistics from the N-slot book with idle cash at the T-bill, trade statistics over every signal.
   - **The "ruled out at 95%" column** (`verdicts.txt`, quoted in section 3a's table). It states its levels: 95.5% bootstrap-t for trade tests, the 95% block bootstrap for portfolio tests.
4. **Documented by the audit, not changed.**
   - **The stress row.** The 2025-10-10 stress row is vacuous for R0 (section 3d).
   - **H11b's share.** It divides by all 648 cells, although 1-hour cells cannot be scored on the 7-day statistic. Leaving out the 146 (W16) and 117 (W16b) cells excluded by the 7-day statistic alone gives 3.2% and 4.0%, so the reading is the same (section 3h).
   - **H8(a)'s bootstrap** is degenerate, because only 2 signals differ. The analytic bound gives the same verdict.
   - **H10's gap.** Part of it comes from rule 11's monthly sizing reacting to the grid's P&L, not from the grid itself. H10 stays INCONCLUSIVE.
   - **Benchmark costs.** Crypto buy-and-hold pays no rebalancing costs, which favours the benchmark.

## 7. Bottom line for the user

- **Don't run it.**
  - On stocks and ETFs it does not work (HS1, HS2).
  - On crypto the data cannot tell (H1). What there is sits in 2020-2022, the same bull market in which the repo's indicator made most of its gains (20.6x in 2020-2022 against 3.5x in 2023-2026).
  - None of the versions you could actually trade got a TRADE verdict. Four Robinhood coins and COIN reached PROBATION, more often than chance would give, but on 11-20 trades each, with AVAX, DOT and UNI recurring in every variant (ADA only for R0 at 1x), and a coin list chosen with hindsight (section 4).
- **Keep the repo's indicator** (`moneyline_ref`, the version from before October 2026; the October 2026 "Bullmania MoneyLine" update was not tested here). On the same three coins and perpetuals, 2020-2026, it was ahead of this breakout core on return, Sharpe and after-tax growth (descriptive): 72.1x vs 5.7x, Sharpe 1.44 vs 1.17, 67.6% vs 20.5% a year after tax. Its worst drawdown was larger (−51% vs −23%), but the core sat out most of the time (0.18x average exposure). H2 could not separate the two on Sharpe (−0.27; interval −0.85 to +0.32).
  - Two band settings of R0, BB(50, 2) and BB(50, 2.1), did beat the indicator over 2020-2026 on return and Sharpe (131.9x and 130.8x; Sharpe 1.65 and 1.67), but they are the best 2 of 51 rows picked after the fact, neither survives the adjustment for the others, and in W16 they made 0.93x and 1.02x (section 3b).
  - The repo's existing plan (ETH via the spot ETF; AGENTIC_TRADING_PLAN section 4) is unaffected.
- **Don't add the pieces either.** None was shown to help.
  - **Pyramiding:** H3 cannot tell. Its point estimate favours it (+0.76% of M per signal), and starting at a third raised sleeve Sharpe in an exploratory comparison (+0.22, +0.05 to +0.53; full size at entry had a −74.5% worst drawdown against −50.4%).
  - **Weekday and hour rules:** both failed their placebo ranks (4th of 7; 63rd of 576).
  - **3-5x leverage:** H9 cannot tell. Its point estimate favoured 3x (+21.6 log points a year), but the worst drawdown went from −20% at 1x to −49% at 3x. It stayed free of liquidations only because the three-coin account averaged 0.42x exposure and the stops were capped above liquidation; run on one coin as the whole account, the same rules lost 95% or more on 11 of 40 coins in the simulation (8 without TRX, UNI and ZEC, where the coded sizing put margin above equity, which an exchange would refuse; 4 of the 8 through liquidation).
  - **Waiting grid:** the account with it trailed R0 alone by 3.4% a year (point estimate; part of that is rule 11's sizing reacting to the grid). Its "grid profit" was given back by the inventory it held.
- **About the trader.** The 4.3x could be real, but nothing here reproduces the post's statistics jointly.
  - Among the pre-registered rows, only adding ZEC with hindsight (S17, 8.96x in W16) beat 4.3x. In the 648-cell fit, one cell at 3x and several fitted cells run at 5x passed 4.3x in W16b (4-hour bars on the all-contract top 10, or on the top 6 of a coin pool chosen in 2026, which carries hindsight). Each is a single in-window path, and none is consistent with the post's statistics jointly.
  - The described rules on BTC/ETH/SOL lost money over the most likely 16 months (R0 0.86x).
  - Random entries with the same rules never reached 4.3x.
  - The post's volume is 5-100 times the most any of the 39 rows checked against the post traded (183x). Only some 1-hour cells of the fit reach it, and none of them matches the post's hit rate.
  - What would settle it: exchange statements for both accounts over the 16 months, with every position, fee and funding payment, compared against holding the same coins at the same leverage.

---

**Sources and files.**
- **Pre-registration:** `analysis_2026/BB_REPLICATION_PREREG.md`, frozen 2026-10-18, with Addenda 1-3.
- **Code:** `analysis_2026/bb_replica.py`, the runner, with `bb_data.py`, `bb_engine.py`, `bb_stats.py`, `bb_stocks.py`, `bb_grid.py`, `bb_bench.py`, `bb_controls.py`, `bb_tests.py`, `bb_desc.py`, `bb_fit.py`; data by `fetch_bb_data.py`.
- **Results:** `analysis_2026/results_bb/`. `verdicts.txt` has all 12 tests. Four large files are gitignored and rebuilt by the run: `rows/trades.csv`, `headline/equity.csv`, `routes/accounts.csv`, `primary/HS1_trades.csv`.
- **Research notes:** `analysis_2026/research_notes/Bollinger breakout replication/`. `rules_and_evidence.md` covers the operational rules, grid mechanics, evidence and reconciliation of the post's numbers; `data_inventory.md` covers the data.
- **Summary:** `HANDOFF.md` section 5.22; `analysis_2026/FINDINGS.md`, entry of 2026-10-19.
