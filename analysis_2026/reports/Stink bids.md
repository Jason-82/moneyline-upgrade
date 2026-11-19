# Stink Bids: Resting Bids vs Alerts, the Data Cannot Tell; Selling Fills Into the Rebound Beat Random Buys of the Same Coin but Is Not Shown to Clear Its 3.75% Bar; Chart Levels, the Data Cannot Tell

**Question (2026-11-18).** The user asked, in their words: "a strategy that looks at highly volatile yet 'solid' cryptos that I wouldn't mind owning, like HYPE, like NEAR, projects with real revenues.... it looks at the charts and through some process figures out good levels to place 'stink bids'; that is, bids that are way below current price, in the hopes of catching a momentary down wick to fill the trade... maybe it wouldn't even need to place any trades for me, just analyze each chart and give me solid choices for the levels of the stink bids and I could place the limit trade myself. can you help me elucidate/test?"

The pre-registration (`analysis_2026/STINKBID_PREREG.md` §1) turned this into four questions:
1. **Flip:** are fills, sold into the rebound by hand, better buys than random buys of the same coin with the same exit?
2. **Rest vs alert:** if you are going to buy after crashes anyway, does a resting bid buy more coin per dollar than a price alert at the same level followed by a manual buy?
3. **Levels:** are chart-based levels better than plain volatility-scaled levels at the same depth?
4. **Usable output:** what level sheet should you get?

**The answer in brief** (the three verdicts in the pre-registered order; numbers and caveats follow):
- **Resting bid vs a price alert (H2R): the data cannot tell** (INCONCLUSIVE). The pre-registered advice: prefer alerts.
- **Flipping the fills (H1): PASS.** Fills sold by hand halfway back to the reference price, or at market after 72 hours, beat random buys of the same coin with the same exit by +6.3% per fill. It is not shown to clear the 3.75% per fill that pays for the costs and the cash the bids tie up, most of it came from a few crashes, and it was much smaller after 2022.
- **Chart levels vs plain volatility-scaled levels (H4): the data cannot tell** (INCONCLUSIVE). The level sheet uses plain volatility-scaled levels.

**Terms used throughout** (each defined once here).
- **Stink bid:** a resting limit buy far below the price. A **fill** is the moment the bid buys.
- **sigma30:** the standard deviation of a coin's last 30 daily log returns, its recent daily volatility.
- **Rung k:** a bid placed k × sigma30 below the price: L = P0 × exp(−k × sigma30), rounded down to the tick. The study's ladder is k = 6, 8 and 10. With sigma30 at 5%, k = 6 is about 26% below the price (exp(−6 × 0.05) = 0.74).
- **Δ (delta):** a fill's net return minus the average net return of its twins, both after Robinhood costs (0.95% each way).
- **Twins:** 100 random buys of the same coin at random minutes outside the six months either side of the fill (±182 days), each sold by the same exit rule and clock.
- **F1 / F3:** two fill rules. **F1** (primary) fills when a Binance spot 1-minute bar trades at least one tick below the limit. **F3** is the Robinhood-route proxy: it fills only when Binance's futures index falls 1% below the limit, as Robinhood's default route fills only when its ask (about 1% above the mid) reaches the bid. No Robinhood crypto price history exists here, so **every F3 number is a proxy**. **F5** (Binance perpetual last price) is a deeper-wick sensitivity: not fills this user could get.
- **Rule M (the manual clock):** a person acts 60 minutes after an event between 07:00 and 22:59 New York time, otherwise at the next 07:00. The flip's sell, the twins and the alert buyer all follow it.
- **Month-blocks:** the statistics treat fills in the same calendar month (merged when one crash spans two months) as one cluster, because fills come in bunches. **G** is the number of clusters with fills. **G\*** is the effective number of independent clusters, (Σn²)²/Σn⁴ over clusters; it is much smaller than G when a few months hold most fills.
- **Holm:** the three tests are judged together, so the smallest p-value must be below 0.05/3, the next below 0.05/2, the last below 0.05.
- **MDE:** the smallest effect the test would detect 80% of the time.
- **BH (Benjamini-Hochberg):** a correction for testing many exploratory rows in one table; **q** is the corrected p-value.
- **CAGR:** compound growth per year.
- **s24:** how fast a fill came. It is ln(H24/L) / ln(P0/L), with H24 the highest price in the 24 hours before the fill: s24 ≥ 0.75 means at least three quarters of the fall from P0 to L, in log terms, came in those 24 hours.

**Short answer.**

**What the verdicts mean.** Each test gets one of three verdicts, set in advance. **PASS:** the effect is above zero after allowing for the three tests (Holm), every robustness gate written in advance held, and the test is not NO EDGE (which takes precedence, A2.3). **NO EDGE:** even a generous upper limit (one-sided 98.33%) is below E, the smallest effect worth acting on; only this verdict may be read as "it does not work", and no test here got it. **INCONCLUSIVE:** neither; "the data cannot tell", stated with its MDE.

The verdicts, in the pre-registered order (`results_stinkbid/verdicts.txt`, `verdicts.csv`):
1. **Rest vs alert (H2R): INCONCLUSIVE. The data cannot tell.** On average, a resting bid bought 2.2% more coin per dollar than an alert buyer at the same level who bought after rule M's delay: an hour, or the next 07:00 New York time at night (95% CI +0.1% to +4.4%; 1,544 fills; month-block clusters G = 58, G* = 14.5). On the Robinhood-route proxy F3: +1.9% (95% CI −0.3% to +4.0%; 1,364 fills; G = 54, G* = 13.8). The p-value (0.0216) cleared Holm (adjusted 0.0432), but one gate failed: the 2023-2026 half was −0.1% (Binance F1; F3 halves not computed). An effect under about 3.2% per fill would not show (MDE).
2. **Flip (H1): PASS.** Stink-bid fills sold into the rebound by hand beat random buys of the same coin with the same exit by **+6.3% per fill** (95% CI +2.8% to +9.9%; 1,541 fills, month-block clusters G = 58, G* = 14.5; p 0.0009, Holm-adjusted 0.0028). On the Robinhood-route proxy (F3): +6.5% (95% CI +2.4% to +10.5%; 1,361 fills, G = 54, G* = 13.8). Every gate held.
3. **Levels (H4): INCONCLUSIVE. The data cannot tell.** The best of four chart methods (M7, an estimated liquidation band) came out +0.2% per fill above plain levels at the same depth (95% interval −0.6% to +1.1%, simultaneous over the four methods; M7's own 95% CI −0.4% to +0.9%; 1,487 stacked fills; month-block clusters G = 33, G* = 10.4; p 0.84). On F3: +0.0% (plain 95% CI −0.7% to +0.7%; 1,330 fills; G = 37, G* = 10.5). An effect under about 1.2% per fill would not show (MDE).

The recommendation lines, as printed in `verdicts.txt` (the pre-registered table, applied in order):
> - "Resting bids and alerts can't be told apart (an edge under about 3.2% wouldn't show). Prefer alerts: your cash stays free and earning."
> - "Selling stink-bid fills into the rebound by hand beat random buys of the same coin by 6.3% per fill (95% CI +2.8% to +9.9%). After Robinhood costs, a flip made +4.8% on average (+4.8% on the Robinhood-route proxy, F3). It held in both halves, without the biggest month and crash, and on Robinhood-like prices. The sheet shows the flip target. [1541 fills, month-block clusters G = 58, G* = 14.5]"
> - "Can't tell; the sheet uses plain volatility-scaled levels."

Printed with every answer (§11; quoted from `verdicts.txt`):
> - "A bid's discount is not a gain by itself. If prices are unpredictable, a bid 30% below the price buys the same expected value as buying now, minus what the coin earns while you wait; in a crash that gaps through your price, it buys less. Only a quick rebound after the wick can pay for the wait."
> - "Bids fill together. On the worst day, 95% of the live bids in the study's main universe filled the same day. Size the whole ladder as one position you are willing to hold through a further 50-80% fall." [2025-10-10: 94 of 99 live P1 bids on U-Q1; Robinhood-route proxy F3: 95% (94 of 99)]
> - "A fill is not a bottom: 27.3% of past fills were 50% or more below the fill price a year later, against 28.4% for random buys of the same coins." [1,329 P1 fills with a year observed; Binance spot fills, F3 not computed]
> - "Coin-specific collapses (LUNA, FTT, OM) look like ordinary wicks on the first day; a resting order cannot read the news. Cancel a coin's bids on news about the coin itself (a hack, exploit, depeg, delisting or regulatory action)."
> - "Most past fills came when the coin's MoneyLine was already red; a fill buys against your own trend signal. Decide before the fill which rule governs the position. The sheet uses the replicated pre-October-2026 MoneyLine." [62.8% red at placement (970 red, 574 green); Robinhood-route proxy F3: 63.8% (870 red, 494 green)]
> - "Capacity: assume every rung fills on the same day, and keep each order within the size cap (a quarter of the 10th percentile of past seller-initiated dollars printed below the level on Binance spot during the wick, from the first trade below it until it trades back above or 60 minutes pass): rung k = 6: 10th percentile $18,823, cap about $4,706 per order; rung k = 8: 10th percentile $20,872, cap about $5,218 per order; rung k = 10: 10th percentile $24,282, cap about $6,071 per order." [Binance spot book; no F3 equivalent]

**How to read H1: eight things the PASS does not say.**
- **It beats random buys; it is not shown to clear the 3.75% bar.** H1's PASS means Δ > 0. E = +3.75% per fill is the pre-registered amount that pays for the round trip (1.88%) and the cash the bids tie up. The 95% interval's lower end (+2.8%) is below E. The outcome audit's one-sided test of Δ > 3.75% gives t 1.58, p 0.069 (against the Gold-sweep E of 2.26%: p 0.0135; F1 only, the audit did not run this test on F3, whose 95% interval starts at +2.4%). So the data show the flip beats random buys of the same coin, not that it clears 3.75%.
- **The edge is concentrated in a few market-wide crashes and in fast, deep wicks.** By contribution, three episodes (2021-05-19, 2025-10-10 and 2021-12-04; 213 of 1,541 fills, 13.8%) carry 42.3% of the total Δ; without them Δ is +4.24%, and without the top five +3.75% (= E). 2021 alone gives 45% of it (Δ +21.6% on 203 fills); 2022's fills averaged +1.5% and 2023's −0.7%. Fills whose previous minute closed less than 1% above the level (half the fills) earned +2.85% (95% CI +0.06% to +5.64%; 770 fills; G and G* not reported by the audit); fills from a fast drop (previous minute's close 3% or more above the level) earned +13.4%. These are the audit's F1 numbers; it did not compute F3 versions (audit after the results; descriptive splits, not tests).
- **What one flip looks like** (descriptive; the follow-up audit's completeness critic; F1 unless stated). The median flip made +3.2% after costs (block-bootstrap 95% CI +1.0% to +6.0%), and 62% of flips made money. 69% ended at the 72-hour market sell, averaging −1.0%; the 29% that reached the target averaged +18.2%; one flip in ten lost more than 10% (10th percentile −10.2%). The best 5% of flips supply 45% of the total; without them the average flip made +2.8%. On the Robinhood-route proxy (F3) the median flip made +2.6%.
- **It was much smaller after 2022** (descriptive; the critic; F1 unless stated). In the pre-registered second half (2023-01 to 2026-11) the average flip made +2.7% (95% CI −0.7% to +6.0%; month-block clusters G = 33, G* = 8.5), and H1's Δ in that half, +4.4%, does not clear E (one-sided p 0.33). By year: 2021 +20.3%, 2023 −2.5%, 2024 +4.2%, 2025 +7.9%, 2026 (to November) +1.1%. As an account (section 3e), the flip account beat B-MIX by +11.4 CAGR points a year in 2020-22 (12-month block-bootstrap interval +3.5 to +24.4) but by +0.3 in 2023-26 (−4.4 to +4.8; F3 proxy +0.4, −4.1 to +4.9): with higher T-bill rates, the cash the bids tie up cost more (its carry rose from 0.65% to 3.64% of capital a year).
- **It is for bids re-placed every week.** The PASS is for 7-day bids cancelled and re-placed every Monday at fresh levels. 30-day bids gave Δ +2.8% (95% CI −1.5% to +7.0%; 1,555 fills, month-block clusters G = 62, G* = 17.7; F3 +2.7%) and 90-day "set and forget" bids, Robinhood's good-till-cancelled life, +4.2% (95% CI −1.0% to +9.4%; 1,020 fills, G = 50, G* = 12.0; F3 +3.7%): neither interval excludes zero (`desc/sensitivity.csv`).
- **"You could run it on Robinhood" may not be said.** The pre-registered account test did not pass: the flip account (a simulated account that keeps cash for every bid on every coin and flips each fill) on F3 beat B-MIX (the same coins held at the account's average invested fraction, the rest in T-bills) by +4.42 CAGR points a year, with a 95% interval, from resampling 12-month blocks of returns, of −0.83 to +11.25, not above zero (`answer.json`, `desc/d7_compare.csv`).
- **The Robinhood numbers are proxies.** F3 stands in for Robinhood's route; no Robinhood crypto history exists here.
- **"Prefer alerts" (H2R) and "flip the fills" (H1) were not tested together.** H1's edge was measured on resting-bid fills. The alert buyer paid on average 2.2% more per fill (1.9% on F3), so a flip entered by alert would likely earn less than H1's +6.3%. Descriptively, as accounts (section 3e), the same flips entered by alert (B-ALERT) made 7.0% a year against the flip account's 8.4% (F3 proxy: 7.1% against 7.8%); the difference's 12-month block-bootstrap interval, −3.48 to +7.44 points (F3 −3.63 to +6.12), includes zero. Per fill (the critic's reconstruction, descriptive): an alert at the level, a buy by hand at the rule-M time, then the same R1/2 target, made +2.7% after costs (95% CI −0.3% to +5.7%) and beat the twins by +4.2% (95% CI +1.2% to +7.3%; month-block clusters G = 58, G* = 14.5); F3 proxy +3.1% and +4.7%. Since 2023 the alert-entered flip account beat the resting-bid flip account by 3.9 points a year (12-month interval 1.9 to 6.4; F1), because its cash stayed in T-bills; in 2020-22 the order was reversed.

**Failures and corrections** (sections 5 and 6; none changed a verdict). The outcome audit, after the verdicts, found four reporting errors, now corrected: the size cap had been overstated 13-22 times (it summed seller dollars over the order's whole life), H4's MDE was printed as 0.94% instead of 1.17%, H4's "without the top month-block" row used the wrong month-blocks (+0.28% instead of +0.12%), and the answer's Binance numbers lacked their F3 numbers. Before any outcome, the runner would have dropped H2R's calibrated control rule (A2.5, fixed), M7's inputs were missing for 162 placements (A2.6, fetched and rerun), and H2R's control rule changed between two controls runs (A2.7; every verdict is the same under each rule). The out-of-memory killer stopped three stages (fill counts, primary, desc); each restarted with fewer workers. B-ALERT's 2-, 8- and 24-hour delay rows were missing from the desc stage; they were computed afterwards with its own functions (section 3i). H4's U-C row was not computed, and F6 (Coinbase) and U-Q2 (real revenue) were not built. The follow-up audit's critic found two more minor defects, documented rather than fixed in code: D7 lacks its single-event rows (the critic's values are in section 3e), and the T-bill accounts' Sharpe in `d7_summary.csv` is a compounding artifact.

**What to do.**
- **First: alerts or resting bids (H2R).** The pre-registered answer is "prefer alerts": the data cannot tell resting bids from alerts (an edge under about 3.2% per fill would not show), and an alert leaves your cash free and earning. In this sample a resting bid bought 2.2% more coin per fill than the alert buyer (95% CI +0.1% to +4.4%; month-block clusters G = 58, G* = 14.5; Robinhood-route proxy F3 +1.9%, 95% CI −0.3% to +4.0%; G = 54, G* = 13.8), but not in 2023-2026 (−0.1%; F1, F3 not computed). The flip (H1) was measured only on resting-bid fills; a flip entered by alert was not tested, and since the alert buyer paid about 2.2% more per fill (F3 1.9%), it would likely earn less. If you want to buy after crashes and hold, the data cannot tell the two apart. The routine below applies if you choose resting bids anyway.
- **If you use the sheet, treat it as a manual tool for a small position that buys only in crashes, not as income.** Run it each week in Git Bash from the repo folder, after Monday 03:30 UTC (Sunday 10:30 pm New York time in winter, 11:30 pm in summer), with each coin's current mid from the Robinhood app (the numbers below are the 2026-11-19 references; replace them):
  ```
  .venv/Scripts/python.exe -m analysis_2026.stinkbid_sheet --refresh --coins NEAR,SOL,HYPE --price NEAR=3.3039 --price SOL=74.04 --price HYPE=68.72
  ```
  Always pass `--refresh`: it fetches the latest daily closes from the Binance archive (the study's data folder is not in the repo, and the sheet refuses a coin whose daily bars end more than 7 days before yesterday). Without `--price`, the sheet uses the latest Binance daily close and refuses a coin whose close is more than 24 hours old. `--per-rung 500` sets dollars per rung (default $1,000). Without `--coins` it prints all 74 Robinhood-tradable coins. It writes `results_stinkbid/sheet/sheet_YYYY-MM-DD.txt/.csv` and an order diff against last week's sheet ("cancel X, place Y"). It never places, previews or cancels orders. These files list your own orders and sizes, so `.gitignore` keeps them out of this public repo (`analysis_2026/results_stinkbid/sheet/sheet_*` and `diff_*`; the study's 2026-11-19 sheet stays tracked). Never force-add them.
- **What the columns mean** (section 4): the limit on Robinhood's tick; depth below the reference in % and in sigma30 units; median weeks to a fill if re-placed weekly and the chance of no fill within a year; Robinhood fill odds per weekly bid (F3 proxy, with a 95% interval) beside the Binance figure (an upper bound); past seller dollars below the level (median / 10th percentile) and the size cap Q_max; your MoneyLine now; whether the coin is in the "large, long-listed (Binance volume)" group; the flip target.
- **The flip rule.** When a bid fills, enter a limit sell at the sheet's flip target **R1/2, halfway back from the fill to the reference price** (R1/2 = L + (P0 − L)/2). If it has not filled after 72 hours, sell at market.
- **Size.** Keep each order within the size cap: about **$4,706 at k = 6, $5,218 at k = 8 and $6,071 at k = 10** on the U-Q1 pool (a quarter of the 10th percentile of seller dollars printed below the level during the wick; Binance spot book, no F3 equivalent). The sheet prints a per-coin cap where the coin has its own past fills. It rests on a handful of fills and can be far below or far above the pooled cap (NEAR: $1,049 at k = 6 from 16 past fills, but $67k at k = 8 and $169k at k = 10 from 7 and 5). Treat the pooled cap as the ceiling and a per-coin cap only as a reason to go lower.
- **Hold cash for every rung on every coin at once, and size the ladder as one position.** Bids fill together (descriptive): on 2025-10-10, 94 of 99 live bids in the study's main universe filled the same day (F3: also 94 of 99). On the 73 sheet coins with history (none for ORCA), the worst day, 2025-10-10, filled 148 of 150 live orders (F3 proxy; Binance spot's worst day 98%; hindsight coin list). Be willing to hold through a further 50-80% fall.
- **Cancel a coin's bids on news about the coin itself** (a hack, exploit, depeg, delisting or regulatory action). Coin-specific collapses (LUNA, FTT, OM) look like ordinary wicks on the first day.
- **Decide in advance how a fill relates to your MoneyLine.** Descriptively, 62.8% of past fills came when the coin's MoneyLine (the replicated pre-October-2026 version) was already red at placement (F3: 63.8%). On 2026-11-19, 72 of the sheet's 74 coins were red (counted from `sheet_2026-11-19.txt`). A fill buys against your own trend signal.
- **HYPE.** The sheet prints HYPE's levels with U-Q1 pooled fill odds and no verdict: about 17 months of Binance perpetual data and 2 months of Binance spot; its only deep-wick day (2025-10-10) came 13 days before Robinhood listed it; HYPE is a venue token whose value depends on Hyperliquid's volume and solvency (FTT, the token of FTX, fell 97.6%); and it is not tradable on Robinhood for New York residents (the 2026-11-18 catalog marks it halted for NY residents).
- **"Real revenue" was not tested.** DefiLlama revenue (U-Q2) was not built, and "large, long-listed" is a Binance volume and listing-age screen, not a quality screen; LUNA and FTT had real activity before they collapsed.
- **NEAR, as an example** (reference $3.3039, sigma30 5.60%; MoneyLine red; large, long-listed: yes):

  | rung | limit | depth | median wait / no fill in 1 year | Robinhood odds per week (F3) [95%] | Binance (upper bound) | per-coin cap (few fills) | flip target |
  |---|---|---|---|---|---|---|---|
  | k = 6 | 2.3606 | 28.6% | 10.1 weeks / 7.4% | 6.1% [0.0%-15.6%] | 7.4% | $1,049 | 2.8323 |
  | k = 8 | 2.1104 | 36.1% | 17.3 weeks / 1.2% | 3.3% [0.0%-10.5%] | 3.4% | $67k | 2.7072 |
  | k = 10 | 1.8867 | 42.9% | 27.4 weeks / 26.0% | 2.3% [0.0%-10.7%] | 2.4% | $169k | 2.5954 |

  The "no fill in 1 year" column comes from NEAR's own short history (Kaplan-Meier, shrunk to the pool) and is not consistent across rungs: a k = 6 bid fills whenever the k = 8 bid does, yet k = 6 shows 7.4% and k = 8 shows 1.2%. That ordering cannot be real; it comes from the estimate's tail on a short history cut off at the end of the data. Read the column as rough.
- **Deeper rungs earned more per fill but fill less often** (per-fill Δ: exploratory, BH-adjusted; fill odds and no-fill chances: descriptive). Mean Δ rose from +3.5% at k = 6 to +7.5% at k = 8 and +12.8% at k = 10 (F3: +3.4%, +7.5%, +13.4%); the slope is +2.1% per sigma of depth (BH q 0.004; F3 +2.2%, q 0.009). Weekly fill odds fell from 7.3% to 4.0% and 2.6% (F1; F3, the sheet's U-Q1 pooled odds: 6.4%, 3.5%, 2.3%), and the chance of no fill in a year rose from 0.5% to 18.6% (F3: 0.9% to 21.9%). The sheet marks k = 10 as the "best rung" under the pre-registered display rule (BH q < 0.10).
- **Cancel and re-place every Monday.** Enter each bid as a good-till-cancelled limit order, but cancel it and place the new one every Monday as the sheet's order diff says. The evidence is for weekly bids at fresh levels; 30- and 90-day bids were not significant (above).
- **The shallowest rung earned least** (descriptive; the critic; F1). At k = 6, which holds 53% of fills, the average flip made +1.9% (+1.1% in 2023-26, 95% CI −1.3% to +3.6%), against +6.0% at k = 8 and +11.4% at k = 10.
- **Before the first routine,** place one small bid at the deepest rung to confirm Robinhood accepts and shows it, then cancel it (the sheet prints the test order).
- **Do not hand this to the trading agent** (AGENTIC_TRADING_PLAN section 4): the account test did not pass, the edge is per fill and concentrated in rare crashes, and Robinhood's fill behaviour in a crash is unknown here.

---

## 1. What was tested

**Pre-registration and build.** The design was drafted (`research_notes/Stink bids/design_draft.md`, commit ae5425c), reviewed by three adversarial critiques (statistics, simulation fidelity, relevance to the user; 49 proposals; commit d44046d) and frozen on 2026-11-18 (`STINKBID_PREREG.md`, commit 72ac2a4). Eight modules were built, each reviewed adversarially and fixed. Addendum 1 (commit 50484fc) and Addendum 2 (commits d1ce7bc, 51476d8, then A2.5-A2.7) settled the build's open choices before any outcome was computed. The controls ran first and every control passed (section 5). The first outcome computation started at 2026-11-19 12:37 UTC (commit 808ea79); the verdicts of record are commit eee2ddf. An independent outcome audit followed; its corrections changed reporting only (commits f6c15f5, cff65d7, 0a87d41; section 5).

**Data** (`data/stinkbid/`, gitignored).
- Binance spot 1-minute bars (F1, the primary fill rule) for every coin of the study's universes, and aggTrades for every U-Q1 coin-day with a fill (capacity).
- Binance USD-M index 1-minute bars (F3, the Robinhood-route proxy) and last-price bars (F5, deeper-wick sensitivity: not fills this user could get).
- For M7: 1-hour mark-price bars and futures open interest, from 2021-12.
- Robinhood's tick and order-size catalog of 2026-11-18 (read-only; `stinkbid_ref/robinhood_pairs_2026-11-18.json`); T-bills from FRED DTB3.
- Coinbase 1-minute bars (F6) and DefiLlama revenue (U-Q2, the "real revenue" universe) were planned for a later session and **were not built**; their rows are empty.

**Universes** (§5).
- **U-Q1, "large, long-listed (Binance volume)"** (primary): Binance top-100 coins (by volume) listed for at least 24 months, with a median monthly volume rank of 50 or better over the prior year. It is never called "solid" or "quality". LUNA and FTT were outside it at their collapses (LUNA by listing age, FTT by volume rank).
- **U-B:** the Binance top 100, including dead and delisted coins (a gate for H1 and H2R; F1 only, because F3 on U-B would read about 36 GB of index history, A1.7).
- **U-Q1-12** (U-Q1 with a 12-month listing rule) and **U-Q1-xm** (U-Q1 without memecoins): sensitivity universes (section 3i).
- **U-A** (24 user-style coins plus MKR) and **U-C** (the coins tradable on Robinhood on 2026-11-18) are **hindsight** lists: reported, never deciding.
- **HYPE** has Binance spot only from 2026-09-24. It is reported on its perpetual's index price: "short history, perpetual-index proxy, no verdict".

**Programs and orders.** **P1** (primary): every Monday at 03:30 UTC, on every U-Q1 coin, bids at k = 6, 8 and 10 with a 7-day life, cancelled and re-placed weekly; each bid-week is an independent, fully cash-backed order. 2020-01-06 to 2026-11-09: 33,486 bids, 1,544 F1 fills (F3: 1,364) in 62 months and 96 crash episodes (`fcount/fcount.txt`). Variants: lives of 1, 30 and 90 days (90 = Robinhood's good-till-cancelled life), P1-lazy, P1-G (bids only while MoneyLine is green), placement at 13:30 UTC, rungs 5 and 12, fixed-% (M1), ATR-scaled (M2a) and fill-probability-calibrated (M3) levels.

**Fill rules** (§7): F1 (primary), F2 (touch; illusion bound only), F3 at s = 1% (gate on every PASS; also s = 2, 3, 5%), F3d (a whole index minute below; "dwell"), F4 (Robinhood's exchange route), F5. A resting bid fills at its limit even when the minute gapped through it.

**Exits** (§8): **X-FLIP**, the flip: a limit sell at R1/2, live from rule M; else sell at market at the first live minute after M(fill + 72 h). **X-FLIP-bot:** the same with the sell live 1 minute after the fill (a bot's latency). A flip grid of other targets and time stops; holds of 7-365 days; hold to the end; X-ML (hold until the first red MoneyLine close after a green one).

**Costs** (§9): C-RH primary, 0.95% each way (about 1.9% a round trip). C-EX, C-0 and C-BUS as sensitivities. On F3 the spread is part of the trigger and exit (route-specific exits, §8).

**Benchmarks** (§10.1): **B-TWIN** (the twins, for H1 and H4); **B-ALERT** (an alert at the same level, then a market buy at rule M's time; a_f = alert price / L − 1 is the resting bid's coin-count advantage, for H2R); B-POST, B-ML, B-MKT; for the accounts, B-MIX, B-TBILL, B-DCA, B-HOLD, B-ALERT, B-ML and their "-OWN" versions. B-ALERT's pre-registered fixed-delay sensitivities (2, 8, 24 and 72 h) were computed for every fill, but only the 72-h delay was tabulated (D8's shared premium: +5.5%, F3 +5.7%). The 2-, 8- and 24-h rows were not reported; this is an omission.

**Statistics** (§10.2). Per-fill units; month-block clusters; p = max(p_WCR, p_G*), where p_WCR is a wild cluster restricted bootstrap-t (Webb weights, 9,999 draws) and p_G* a t-test with G* − 1 degrees of freedom. The NO EDGE bound is one-sided 98.33%. Concentration (the three largest episodes) and single-event removals (2025-10-10, 2021-05-19, the top month-block) are reported with every headline.

**The three tests and the answer map** (§10.3, §11).

| test | claim | statistic | E | PASS needs (all) |
|---|---|---|---|---|
| **H2R RESTING** | a resting bid buys more coin per dollar than an alert at the same level followed by a manual buy | mean a_f, P1 fills | +2% per fill | Holm p < 0.05; a > 0 in both halves (2020-22, 2023-26), without the worst month-block and the biggest episode, on U-B and on F3 |
| **H1 FLIP** | fills sold into the rebound by hand beat random buys of the same coin with the same exit | mean Δ, P1, X-FLIP, rule M, C-RH | +3.75% per fill (round trip 1.88% + T-bill 4.21% / 2.26 fills per rung-year) | Holm p < 0.05; mean r_f > 0; Δ > 0 in both halves, without the worst month-block and the biggest episode, on U-B and on F3 |
| **H4 LEVELS** | at least one chart method beats plain levels at the same depth, in the same wick | max t over M4 (below the 90-day low, 0.5 ATR), M5b (round numbers, 0.5 ATR beyond), M6 (volume node), M7 (liquidation band, from 2021-12), each against four placebo levels ±0.5 and ±1.0 ATR away, coin-week fixed effects; Romano-Wolf / Bonferroni over the four | +1% per fill | Holm p < 0.05; the best method's b > 0 in both halves, without the worst month-block and on F3 |

The answer, the recommendation table, the fixed sentences and the wording rules were fixed in §11 before any outcome. "You could run it on Robinhood" needs H1 or H2R PASS, the D7 flip account on F3 beating B-MIX with a 12-month block-bootstrap interval above zero, and the effect above zero on U-C under F3 (A1.8).

## 2. The three tests

Sources: `results_stinkbid/verdicts.txt`, `verdicts.csv`, `primary/primary.json`, `primary/gates.csv`, `primary/h4_methods.csv`.

**D12: what happens after a fill** (descriptive; §10.4 reports it before H1's table, as `verdicts.txt` prints it).

Share of fills and of their twins trading at or above the flip target R1/2 within each horizon, and at or above the placement price P0 (`desc/d12.csv`):

| | n | R1/2 in 15 min | 1 h | 4 h | 24 h | 72 h | 7 d | 30 d | P0 in 72 h | P0 in 30 d | first went 10% below L |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 fills | 1,544 | 3.8% | 6.2% | 9.5% | 22.9% | 32.9% | 43.1% | 69.6% | 4.9% | 29.3% | 59.6% |
| F1 twins | 1,544 | 0.0% | 0.1% | 0.5% | 4.6% | 13.6% | 25.9% | 52.5% | 3.8% | 31.4% | 53.3% |
| F3 fills (proxy) | 1,364 | 0.7% | 1.1% | 3.2% | 13.6% | 22.9% | 31.2% | 60.9% | 2.4% | 23.4% | 65.3% |
| F3 twins (proxy) | 1,364 | 0.0% | 0.0% | 0.2% | 2.8% | 9.7% | 20.5% | 47.1% | 2.8% | 28.0% | 58.2% |

- Fills rebounded to the target more often than twins at every horizon, but most fills (59.6%; F3 65.3%) first traded a further 10% below L before anything else.
- Fast fills (s24 ≥ 0.75; 826 fills) reached R1/2 within 24 h 36.9% of the time; slow fills (s24 < 0.5, 261) 2.7% (F3: 21.8% of 743 and 1.3% of 224).

| test | estimate per fill | 95% CI | n | G / G* (month-blocks) | p (WCR / G*) | Holm-adjusted p (cleared if < 0.05) | 98.33% bound vs E | MDE | gates | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **H2R** rest vs alert | +2.23% | +0.08% to +4.39% | 1,544 | 58 / 14.5 | 0.0156 / 0.0216 | 0.0432 | +4.61% vs +2% | 3.24% | half 2 failed | **INCONCLUSIVE** |
| **H1** flip | +6.34% | +2.80% to +9.88% | 1,541 | 58 / 14.5 | 0.0001 / 0.0009 | 0.0028 | +10.24% vs +3.75% | 5.33% | all 7 held | **PASS** |
| **H4** levels (M7) | +0.23% | −0.62% to +1.09% (simultaneous over the four methods; M7 alone −0.39% to +0.86%) | 1,487 | 33 / 10.4 | 0.5629 / 0.8409 | 0.8409 | +1.16% vs +1% | 1.17% | half 1 failed | **INCONCLUSIVE** |

The p that enters Holm is the larger of the two. H1 had the smallest p, so it was judged at 0.05/3; H2R at 0.05/2; H4 at 0.05. H2R's raw p (0.0216) was below its level (0.025), so its Holm-adjusted p (0.0432) is below 0.05.

**Beside every headline** (`verdicts.txt`; F3 = Robinhood-route proxy; U-C = Robinhood-listed coins, hindsight):

| row | H2R a_f | H1 Δ | H4 b (M7) |
|---|---|---|---|
| primary, F1 | +2.23% (+0.08 to +4.39; 1,544; G 58, G* 14.5) | +6.34% (+2.80 to +9.88; 1,541; G 58, G* 14.5) | +0.23% (−0.62 to +1.09, simultaneous over the four methods; 1,487; G 33, G* 10.4) |
| F3 (s = 1%), Robinhood-route proxy | +1.88% (−0.3 to +4.0; 1,364; G 54, G* 13.8) | +6.45% (+2.4 to +10.5; 1,361; G 54, G* 13.8) | +0.02% (−0.7 to +0.7; 1,330; G 37, G* 10.5) |
| F3d (dwell, s = 1%), proxy | +0.55% (−1.5 to +2.6; 1,239; G 52, G* 13.1) | +5.60% (+1.4 to +9.8; 1,236; G 52, G* 13.0) | not computed |
| F3 (s = 3%), proxy | +2.24% (−0.2 to +4.7; 1,170; G 48, G* 12.7) | +7.56% (+3.1 to +12.0; 1,167; G 48, G* 12.7) | not computed |
| U-B (top 100, dead coins included; F1 only, F3 not computed, A1.7) | +2.44% (+0.2 to +4.6; 4,712; G 68, G* 13.4) | +6.84% (+2.8 to +10.9; 4,709; G 68, G* 13.3) | not a gate |
| U-C, F1 (hindsight) | +1.93% (−0.3 to +4.2; 1,668; G 56, G* 11.9) | +7.32% (+4.1 to +10.6; 1,665; G 56, G* 11.9) | not computed (see below) |
| U-C, F3 (hindsight; proxy) | +1.52% (−0.8 to +3.8; 1,459; G 55, G* 10.5) | +7.28% (+3.7 to +10.8; 1,455; G 55, G* 10.5) | not computed |

H4 has no U-C row. H4 ran on U-Q1 only; its futures and index inputs were never planned for U-C. This omission was found by the outcome audit after the results and is stated in `verdicts.txt`.

### 2a. H2R, rest vs alert: INCONCLUSIVE

- **The gates.** Five of six held: first half, without the worst month-block, without the biggest episode, U-B and F3 were all above zero. **The second half was not**: 2020-22 +5.18% (687 fills; t 3.31), 2023-26 −0.13% (857 fills; 95% CI −2.04% to +1.78%; month-blocks, G and G* not reported by the audit) (outcome audit; F1, the audit did not compute F3 halves). By year within half 2: 2023 −0.51%, 2024 +0.72%, 2025 −2.78%, 2026 +1.94%.
- **The Holm clearance is fragile** (audit; F1). With a plug-in df of 3.6 instead of G* − 1, the p is 0.048 and the Holm-adjusted p 0.097 (audit).
- **The realized MDE (3.24%) is above E (2%)** and above the pre-registered expectation of about 1.2%. H2R's real SE (1.00%) is 1.8-4.7 times the SEs of K3's synthetic nulls: the real data are more dispersed than the controls' panels (section 7).
- **Concentration and single events.** The three largest episodes by fills (2022-11-08..09, 2025-10-10, 2023-08-15..17) pulled the total down (−9.5% of it); without them +3.00% (F3 top-3 not computed). Without 2025-10-10 +2.79%; without 2021-05-19 +1.58%; without the top month-block +2.17%. F3: +2.43%, +1.27% and +1.77% for the same three removals.
- **A2.7's other K3 rules.** H2R's control rule flipped between two Monte Carlo runs (section 6). Decided under the first controls run's simulation-calibrated rule (critical t 2.537), H2R's p is 0.0248, Holm-adjusted 0.0496, bound +4.61%, MDE 3.41%. Under the record's other rule (simulation-calibrated with the record's null draws, critical t 2.315), p 0.0208, Holm 0.0416, bound +4.62%, MDE 3.19%. **All three verdicts are the same under every rule:** H2R INCONCLUSIVE, H1 PASS, H4 INCONCLUSIVE.

### 2b. H1, the flip: PASS

- **Gates (all held):** mean r_f > 0 (+4.82% per fill after Robinhood costs; F3 +4.84%); both halves positive (2020-22 +8.7% on 687 fills, 2023-26 +4.4% on 854 fills; F1, the means of `primary/samples_H1.csv` by half; F3 halves not computed); positive without the worst month-block and without the biggest episode; positive on U-B (+6.84%; F1 only, F3 not computed on U-B, A1.7) and on F3 (+6.45%).
- **Not a Binance-only result** (A1.8). Re-run on the F1 fills that F3 also fills: +5.76% (95% CI +1.74% to +9.77%; 1,362 fills, G 56, G* 13.5), p 0.0043, below the 0.0167 Holm level at which H1 passed.
- **Bot latency.** With the sell live 1 minute after the fill (X-FLIP-bot): +6.67% (95% CI +3.00% to +10.33%; 1,541 fills, month-block clusters G 58, G* 14.5), p 0.0008, Holm-adjusted in H1's place 0.0025, bound +10.70%: PASS. It does not pass "only at bot latency"; the manual clock passes too. F3 bot row: +6.48% (+2.46% to +10.49%; 1,361 fills, G 54, G* 13.8).
- **E sensitivity** (§10.3). With E = 2.26% per fill (reserved cash earning the 3.35% Gold sweep), H1 would still be PASS (the bound +10.24% is not below 2.26%). Against E itself (3.75%), the audit's one-sided test gives p 0.069; against 2.26%, p 0.0135 (F1; F3 not computed). E's input f was 2.26 fills per rung-year; P1 realized 2.41, which would give E = 3.63%. E is fixed by §10.3 and affects only NO EDGE.
- **Concentration and single events** (pre-registered: episodes ranked by fill count). The three largest episodes (2022-11-08..09, 2025-10-10, 2023-08-15..17) give 14.2% of the total; without them +6.67% (F3 top-3 not computed). Without 2025-10-10 +6.06% (F3 +6.04%); without 2021-05-19 +5.34% (F3 +5.45%); without the top month-block +6.57% (F3 +6.76%). **By contribution** (the audit's ranking, after the results, exploratory; F1, the audit computed no F3 version), the picture is different: 2021-05-19, 2025-10-10 and 2021-12-04 (213 of 1,541 fills, 13.8%) carry 42.3% of the total; without them +4.24% (t 4.29); without the top five +3.75%. 2021 alone gives 45% (Δ +21.6% on 203 fills); 2022's fills averaged +1.5%, 2023's −0.7%. The lowest single year left out still leaves +4.02%.
- **Where it comes from** (audit after the results, exploratory; F1, no F3 version computed). Two-thirds of the gross effect (4.4 of 6.6 points) comes after the sell goes live. The target was hit by 30.0% of fills and 13.8% of twins. Fills that slid into the level (previous minute's close under 1% above L; half the fills) earned +2.85% (95% CI +0.06% to +5.64%; 770 fills; G and G* not reported by the audit); fills whose previous close was 3% or more above L earned +13.4%. Single-minute spikes (26 fills) averaged +18.6%. The biggest single gains are one-minute wicks (WLD 2025-10-10; QTUM, VET and ZIL 2021-05-19: Δ +74% to +82%); they add 0.20 points to H1's mean, and the alert buyer an hour later paid 54-63% more than L in those.
- **Robustness the audit checked** (F1; the audit did not compute F3 versions): without likely bad prints +5.94%; without single-minute spikes +6.13%; without fills the index route never filled +5.76%; capacity terciles +6.28 / +6.57 / +6.18%; without any one coin, lowest +6.18%; leave-one-block-out t never below 3.52; episode clusters t 3.88, quarter-blocks t 3.36, two-way coin × month t 3.83; without the four named event days +5.36% (t 4.06); winner's-curse adjusted 6.0-6.2%.
- **Inference cross-checks** (`desc/sensitivity.csv`): episode clusters +6.34% (+2.82 to +9.87; G 96, G* 14.4; F3 +6.45%, +2.42 to +10.49, G 80, G* 13.2); week clusters (+2.78 to +9.91; G 98, G* 14.0; F3 +2.37 to +10.53, G 84, G* 12.9); two-way coin × month (+3.02 to +9.66; G 62; F3 +2.72 to +10.18, G 57; G* not computed for two-way).

### 2c. H4, levels: INCONCLUSIVE

Per method (`primary/h4_methods.csv`; Bonferroni over four methods; F1). Per-method F3 estimates were not saved. On F3, M7 (the method of record) gives +0.02% (the gate). H4 re-run on the F3 fills picks M4 as the best method (max t 1.90, Bonferroni p 0.17; `primary/primary.json`, beside.H4.F3_1_omnibus). Re-run on the F1 fills that F3 also fills, it keeps M7 (+0.20%, p 1.0; f3kept.H4). Each interval below is the 95% interval simultaneous over the four methods (critical t from 0.05/8); M7's own 95% CI is −0.39% to +0.86%:

| method | n (coin-weeks) | b per fill | 95% CI (simultaneous over the four methods) | G / G* | Romano-Wolf p | 98.33% bound vs +1% | MDE (Bonferroni) |
|---|---|---|---|---|---|---|---|
| M4 below the 90-day low | 1,687 (434) | −0.06% | −0.79% to +0.67% | 40 / 11.5 | 0.82 | +0.72% | 0.99% |
| M5b round numbers | 1,827 (445) | −0.05% | −0.93% to +0.83% | 38 / 11.5 | 0.82 | +0.90% | 1.20% |
| M6 volume node | 1,355 (403) | −0.35% | −1.12% to +0.42% | 51 / 13.9 | 0.90 | +0.47% | 1.05% |
| **M7 liquidation band** (best) | 1,487 (398) | +0.23% | −0.62% to +1.09% | 33 / 10.4 | 0.56 | +1.16% | 1.17% |

- **Gates.** The best method's b was not above zero in the first half; it was in the second half, without the worst month-block and on F3 (+0.02%).
- **Close to NO EDGE.** Only M7's bound (+1.16%) is above E = 1%; the other three (+0.72%, +0.90%, +0.47%) are below it. The audit notes that M7 alone keeps H4 from NO EDGE, and that on a per-method reading of §10.2 all four bounds would be below 1%: a reading question, not a defect. As run, H4 is INCONCLUSIVE.
- **Single events.** The three largest episodes by fills (2022-11-08..14, 2025-10-09..10, 2023-06-05..10) hold 21.0% of the stacked fills; without them +0.33%. Without 2025-10-10 +0.22%; 2021-05-19 is before M7's data (unchanged, +0.23%); without the top month-block +0.12% (corrected; section 5). F1; F3 versions of these removals were not computed for H4.
- **K3's power** for H4 (synthetic nulls): NO EDGE was reachable in only 14% (base), 0% (hetero) and 0% (high dispersion) of null replications, so INCONCLUSIVE was the likely outcome even with no effect.

## 3. Descriptive and exploratory results

Everything in this section is **descriptive** (pre-registered estimands with intervals but no verdict) or **exploratory** (splits with BH-adjusted p-values within each table). None of it decides anything. Sources: `results_stinkbid/desc/desc.txt` and its CSVs; `results_stinkbid/explore/explore.txt` and its CSVs.

Each descriptive row's estimate without 2025-10-10, without 2021-05-19 and without its top month-block (§10.4, "Single events") is in its file's `without_2025-10-10`, `without_2021-05-19` and `without_top_block` columns. In that order (F1): D-H2 −1.0% / −4.1% / −4.9%; D-H3 +3.7% / +5.4% / +3.7%; D8's 72-h premium +5.0% / +5.1% / +5.9%; B-ML +8.0% / +7.6% / +7.7%; μ* at k = 10 13.7% / 14.6% / 17.8% a year, against 18.3% with every fill.

### 3a. D-H2 (owning after a fill) and D8 (flip or own)

- **D-H2:** "Descriptive only. Over 90 days, coins bought through stink bids did 3.5% (95% CI −19.9% to +13.0% for the difference) worse than the same coins bought at random times outside the six months around each fill. An edge under about 20-40% could not be detected, and the comparison also reflects whether the crashes fell in bear or bull stretches." [1,513 fills, quarter-block clusters G = 27, G* = 12.9; MDE 24.7%; F3: −5.2% (95% CI −20.9% to +10.5%; 1,339 fills, G = 26, G* = 12.4)]. Against B-POST (twins entering 1-30 days after the fill): +3.5% (95% CI −3.5% to +10.6%; same clusters; no F3 row was computed). The controls' K1c measured what regime timing alone produces in a synthetic world: −6.1% per 90 days (SE 5.1%).
- **D8:** "Flip or own is a choice about whether you want to hold the coin, not about stink-bid skill. The study's evidence on the bid is the same for both." The shared premium (the alert buyer's price 72 h later): +5.5% (95% CI +2.6% to +8.4%; 1,541 fills, G = 58, G* = 14.5); F3 +5.7% (+2.4% to +9.1%; 1,361 fills, G = 54, G* = 13.8). The return from 72 h to 90 days against T-bills: +10.6% (95% CI −7.0% to +28.2%; 1,513 fills, quarter-block G = 27, G* = 12.9); F3 +8.7% (−6.1% to +23.5%; 1,339 fills, G = 26, G* = 12.4).

### 3b. D-H3: fast wicks vs slow slides

"Descriptive only. Fast wicks were 4.3% per fill (95% CI −1.8% to +10.2% for the difference) better than slow slides to the same depth. A difference under about 6-10% per fill could not be detected." [1,054 fills, month-block G = 45, G* = 11.1; episode fixed effects; MDE 8.2%; F3: +2.9% (95% CI −3.9% to +9.6%; 946 fills, G = 44, G* = 10.7)]. The drafted version without episode fixed effects: +6.4% (+1.9% to +10.9%; 1,087 fills, G 56, G* 11.2); the 6-hour and 1-hour speed measures: +3.2% (−3.7% to +9.9%; 1,114 fills, G 49, G* 12.5) and +7.3% (−2.4% to +16.8%; 1,207 fills, G 51, G* 14.1). F3 was computed for the primary version only.

### 3c. D-H5 and T1: knife-catching

- **D-H5:** "Descriptive only. A year after a fill, 27.3% of fills on large, long-listed coins and 46.5% on other top-100 coins were 50% or more below the fill price; at the same volatility the gap was +12.9 points (95% CI +4.6 to +21.2). Neither LUNA (kept out by listing age) nor FTT (kept out by Binance volume rank) was in the large, long-listed group, so this says nothing about fraud collapses of large coins. In the 12-month row, where LUNA is included, the gap was +8.4 points. The study did not test a real-revenue filter." [4,230 fills; two-way coin × quarter clusters, G_coin = 355, G_quarter = 26, t at 25 df; Binance spot fills only, F3 not computed on U-B (A1.7)]. Sensitivities: over fill-years (Ibragimov-Müller) +11.6 points (+2.8 to +20.4; 6 fill-years, t at 5 df); with sigma30 deciles +12.1; without ETH (the coin whose removal lowers it most) +12.2; delisting haircut 0% / 100%: +12.6 / +12.9. The 12-month row: +8.4 points (+1.4 to +15.4; coin × quarter clusters, G_coin 355, G_quarter 26).
- **T1, the tail** (U-Q1, 1,329 fills with a year observed; F1; F3 not computed, A1.7). 27.3% of fills and 28.4% of twins were 50% or more below their entry a year later (fills minus twins −1.1 points, episode-cluster 95% CI −13.5 to +12.6, G 76 episodes; G* not computed). The lowest price within 30 days was a median 0.84 × L (10th percentile 0.56 × L); within 90 days a median 0.74 × L (10th percentile 0.45 × L); within a year a median 0.53 × L (10th percentile 0.21 × L). Within a year, 1.1% of fills and 0.6% of twins were delisted. The share of each episode's filled dollars that were 50% or more under water at the worst point (`desc/t1_episodes.csv`) was 100% in the worst episode, and 16 of the 76 U-Q1 episodes reached 100%; it was 93.6% for 2025-10-10, 92.9% for 2022-01-21 and 74.3% for 2021-05-19..23. On U-Q1-12 (12-month listing rule): 32.4% of fills and 31.2% of twins were 50% or more below their entry a year later (1,731 fills). On U-B: 40.4% of fills and 38.0% of twins; delisted within a year 2.2% and 0.9%.

### 3d. D6: the cost of waiting (μ*)

A bid at rung k beats buying now only if you expect the coin to beat cash by less than **μ*_k a year** (μ* = F × θ / W: F the chance of a fill within a year, θ the fill's 72-hour premium over its twins, W the expected wait as a share of the year). Weekly re-placement on U-Q1 (`desc/d6.csv`):

| rung | route | median wait | no fill in a year | θ (72-h premium) | μ* a year [95% CI] |
|---|---|---|---|---|---|
| k = 6 | F1 | 60 days | 0.5% | +2.8% | 13.4% [1.8%, 25.0%] |
| k = 6 | F3 (proxy) | 68 days | 0.9% | +2.8% | 11.9% [1.4%, 22.3%] |
| k = 8 | F1 | 103 days | 4.6% | +6.3% | 17.4% [5.8%, 29.1%] |
| k = 8 | F3 (proxy) | 111 days | 5.9% | +6.6% | 17.0% [4.8%, 29.3%] |
| k = 10 | F1 | 164 days | 18.6% | +11.3% | 18.3% [8.4%, 28.1%] |
| k = 10 | F3 (proxy) | 174 days | 21.9% | +12.1% | 17.9% [7.9%, 27.9%] |

θ is before costs on the F1 rows (C-0) and after the route's costs on F3 (the code's choice in `stinkbid_desc.py`). θ's intervals use month-block clusters: F1 G 59 / 42 / 26, G* 20.9 / 13.0 / 9.4; F3 G 55 / 38 / 21, G* 20.4 / 12.3 / 8.8 (k = 6 / 8 / 10). Beside it, "the sample's drift" (B-MKT, per placement, F1 only): a bid at k = 6 that filled, held a year (T-bills if it never filled), earned 87 points less than buying at market at placement and holding a year (95% CI −225 to +13 points; k = 8 and k = 10: −89 points each, −230 to +13 and −231 to +13; 71 placement months, 12-month stationary-block bootstrap; F3 not computed, B-MKT is per placement on Binance spot).

### 3e. D7: accounts

**The flip account (D7):** cash for 3 rungs × every U-Q1 coin at $10k each, one position per rung, flips at X-FLIP; reserved cash earns nothing (r_res = 0, the primary). 2020-2026, 83 months (`desc/d7_summary.csv`, `d7_compare.csv`):

| account (r_res = 0) | F1: CAGR / Sharpe / max drawdown | F3 (proxy): CAGR / Sharpe / max drawdown |
|---|---|---|
| **D7 flip account** (0.9% invested on average) | 8.4% / 0.74 / −3.2% (after tax 5.6%) | 7.8% / 0.64 / −2.7% (after tax 5.2%) |
| B-MIX (same coins at 0.9%, rest T-bills) | 3.4% / 0.55 / −0.8% | 3.4% / 0.55 / −0.8% |
| B-TBILL | 2.9% | 2.9% |
| B-DCA (the same capital bought in weekly buys of the same coins) | 2.9% / 0.22 / −61.4% | 2.9% / 0.22 / −61.4% |
| B-ALERT (the same flips entered by alert) | 7.0% / 0.72 / −5.4% | 7.1% / 0.70 / −5.1% |
| B-HOLD (equal-weight hold of U-Q1) | 8.9% / 0.39 / −79.8% | 8.9% / 0.39 / −79.8% |
| B-ML (each coin's sleeve invested while MoneyLine is green) | 29.6% / 1.19 / −7.9% | 29.6% / 1.19 / −7.9% |

D7 minus each benchmark, CAGR points a year, with the stationary block-bootstrap 95% interval at the pre-registered 6-month mean block, then at 12 months (the block the Robinhood sentence uses):

| | F1: 6-month / 12-month | F3 (proxy): 6-month / 12-month |
|---|---|---|
| vs **B-MIX** | +5.04 [−0.44, +12.37] / [−0.47, +12.13] | **+4.42 [−0.83, +11.60] / [−0.83, +11.25]** |
| vs B-TBILL | +5.49 [−0.10, +13.21] / [−0.22, +13.12] | +4.87 [−0.53, +12.29] / [−0.58, +12.12] |
| vs B-DCA | +5.46 [−28.9, +31.4] / [−23.0, +27.9] | +4.85 [−29.8, +31.1] / [−23.9, +27.5] |
| vs B-ALERT | +1.40 [−3.09, +6.92] / [−3.48, +7.44] | +0.72 [−3.27, +5.67] / [−3.63, +6.12] |
| vs B-HOLD | −0.51 [−71.1, +40.4] / [−62.5, +36.2] | −1.13 [−72.1, +39.9] / [−63.6, +36.0] |
| vs B-ML | −21.17 [−54.2, −0.51] / [−54.0, −0.25] | −21.79 [−55.4, −0.66] / [−55.2, −0.40] |

- **The pre-registered account test failed** (F3 vs B-MIX interval not above zero), so the account is reported, as §10.4 requires, as "a low-exposure crypto holding with extra steps", and "You could run it on Robinhood" is not said.
- **If reserved cash earned 3.35%** (whether cash reserved for an open Robinhood crypto order earns sweep interest is not documented), D7 on F3 beat B-MIX by +6.28 points (12-month interval +1.14 to +13.12; F1 +6.83, +1.41 to +14.00). The rule of record uses r_res = 0 (A1.8); this row does not change the answer. It also pays reserved cash a flat 3.35% on days when the T-bill was lower (40% of days, all in 2020-22); capped at the T-bill, the F3 margin is +5.67 points (+0.84 to +12.14; the audit's critic).
- **By half and without single events** (the audit's critic rebuilt the decisive F3 account, r_res = 0, with its own code and matched the record to the cent: end value $1,913,664.82, CAGR 7.78%, 1,325 positions). D7 minus B-MIX, CAGR points a year, 12-month block-bootstrap interval: 2020-22 +11.41 (F1, +3.46 to +24.37; F3 +9.80); 2023-26 +0.27 (F1, −4.36 to +4.81; F3 +0.37, −4.11 to +4.93). F3, all years: without 2021-05-19 +2.83 (−1.02 to +6.79); without 2025-10-10 +3.59; without the top month-block +2.09 (−1.31 to +5.31). Three months (2021-05, 2021-12, 2025-10) carry 69% (F1) and 83% (F3) of D7's summed monthly excess over T-bills. The stage code did not produce D7's single-event rows, which §10.4 asks of every estimate (an omission found by the audit; section 5).
- **One cell to ignore:** `desc/d7_summary.csv` prints a Sharpe of 2.07 for B-TBILL (and −1.26 for B-TBILL-OWN). It is a compounding artifact: with no excess return over T-bills the true value is 0 (section 5). The table above leaves it out.
- **D7-OWN** (a monthly budget per coin, rungs a third each, fills held to the end): F1 CAGR 21.3%, Sharpe 0.55, max drawdown −77.7% (85% invested); F3 19.2%, −74.6%. Against B-MIX-OWN: F1 +1.37 points [−32.5, +20.7], F3 −0.99 [−38.2, +17.4] ("a low-exposure crypto holding with extra steps"). Against the same budget bought by alert (B-ALERT-DCA): F1 +0.76 [−0.14, +2.86], F3 +0.45 [−0.17, +1.65]. Against holding (B-HOLD-OWN): F1 −3.97 [−35.6, +8.3], F3 −6.05 [−47.3, +9.0]. Against B-ML-DCA (the same budget bought after green MoneyLine closes; CAGR 55.4%, max drawdown −48.0%): F1 −34.09 [−73.0, −6.5], F3 −36.18 [−80.4, −8.2]; this interval is below zero. Against B-DCA-OWN: F1 −3.21 [−33.9, +9.2], F3 −5.29 [−45.5, +9.3]. Against B-TBILL-OWN: F1 +18.37 [−25.8, +95.2], F3 +16.29 [−23.9, +83.1]. (D7-OWN intervals are 12-month; the 6-month ones are in `desc/d7_compare.csv`.) **D7-OWN-ML** (fills held until the MoneyLine turns red): F1 13.5%, max drawdown −18.6%; vs B-MIX-OWN −6.41 [−95.6, +34.9]; vs B-ML-DCA −41.87 [−124.1, +0.4]; the other D7-OWN-ML rows are in `d7_compare.csv`; F3 not computed (the engine computes X-ML exits on F1 only).

### 3f. D-ML: the MoneyLine

- Fills by state at placement: 970 red, 574 green (62.8% red; F3 63.8%, 870 of 1,364).
- 98.1% of fills were followed by a red close within 1 day and 98.8% within 7 days (F1; F3 not computed).
- B-ML (waiting for the first green MoneyLine close after the fill and buying then) paid 6.9% more per coin than the fill (95% CI +1.0% to +12.8%; 1,513 fills, G 57, G* 14.3; F3 +6.2%, +0.5% to +11.8%; 1,339 fills, G 52, G* 13.7). By rung: +4.3%, +8.4%, +12.2% (k = 6, 8, 10; F1, F3 by rung not computed). By state at placement (F1): green +4.0% (−6.0% to +14.1%; 567 fills, G 50, G* 3.9), red +8.6% (+1.7% to +15.6%; 946 fills, G 49, G* 11.1).
- X-ML (hold until the first red close after a green one): Δ +8.6% (95% CI −3.8% to +21.0%; 1,515 fills, G 57, G* 14.3; F3 not computed).
- P1-G (bids only while the MoneyLine is green): Δ +7.1% (+0.7% to +13.4%; 574 fills, G 52, G* 3.9); F3 +6.8% (−1.1% to +14.7%; 494 fills, G 45, G* 3.6).

### 3g. Capacity, venue, fill odds and luck

- **D4 capacity** (Binance spot book; context only on Robinhood's market-maker route; no F3 equivalent). Seller-initiated dollars printed below the level during the wick (first trade below it until it trades back above or 60 minutes pass): median $633k / $958k / $948k and 10th percentile $18,823 / $20,872 / $24,282 at k = 6 / 8 / 10, so the cap Q_max (a quarter of the 10th percentile) is $4,706 / $5,218 / $6,071. The share of a $10k order filled by its expiry (the remainder rests): 99.2% / 99.9% / 99.5%; of a $100k order 97.2% / 98.1% / 96.4%. U-C coins (hindsight) have higher capacity: caps $6,514 / $8,164 / $9,280.
- **D3 venue gap** (share of F1 fills that the other rules also fill): F3 (1%) 88.3%, F3 (2%) 80.7%, F3 (3%) 75.7%, F3 (5%) 66.4%, F3d (1%) 80.2%, F4 96.2%, F5 97.5% (deeper-wick sensitivity: not fills this user could get); 1.6% are F3-unverifiable (index minute missing; 20.5% on 2020-03-12). F6 (Coinbase) was not built.
- **D1 wick frequency and clustering** (`desc/d1.csv`; F1 fills; the file has no F3 rows; it splits by year and also covers U-B, U-A and U-C (hindsight)). On U-Q1: k = 6: 818 fills on 165 days, in 95 episodes and 62 months (G* 20.9); 73% market-wide. k = 8: 441 fills on 79 days, in 54 episodes and 42 months (G* 13.0); 88% market-wide. k = 10: 285 fills on 46 days, in 33 episodes and 27 months (G* 9.4); 93% market-wide.
- **D2 fill rates by life** (F1; F3 not computed for this table): a 7-day bid filled 7.3% / 4.0% / 2.6% of the time at k = 6 / 8 / 10; a 90-day bid 46.5% / 38.5% / 31.7%; a 1-day bid 0.58% / 0.27% / 0.15%.
- **Lives** (sensitivity rows, H1 Δ, month-block clusters): 1 day (re-placed daily; exploratory) +11.2% (+5.9% to +16.6%; 786 fills, G 45, G* 7.9; F3 +11.8%, 650 fills, G 38, G* 7.0); 30 days +2.8% (−1.5% to +7.0%; 1,555 fills, G 62, G* 17.7; F3 +2.7%, 1,449 fills, G 59, G* 11.9); 90 days, Robinhood's good-till-cancelled "set and forget", +4.2% (−1.0% to +9.4%; 1,020 fills, G 50, G* 12.0; F3 +3.7%, −2.2% to +9.8%, 987 fills, G 48, G* 10.9). The weekly re-placement of P1 is not the same as leaving one 90-day order.
- **D5 fill-odds calibration.** The sheet's walk-forward odds predicted 1,103 F3 fills and 1,244 happened (F1: 1,262 predicted, 1,388 happened); both halves' episode-bootstrap 90% intervals overlap [0.67, 1.5], so the odds count as calibrated (F3 ratios 1.68 [0.83, 2.65] and 0.93 [0.56, 1.34], over 101 and 196 episodes; F1 1.53 [0.79, 2.39] and 0.94 [0.58, 1.33]). M3's odds were also calibrated (F1 realized vs predicted 272 vs 223, 592 vs 558 and 1,205 vs 1,116 at p = 2 / 5 / 10%; F3 realized 243, 525 and 1,033).
- **D10 chart levels' fill odds** (their own Holm family, for the sheet only): none of M4, M5b, M6, M7 had better fill odds than depth-matched placebos (differences −0.09 to −0.74 points per bid-week, F1; F3 −0.02 to −0.72; Holm p 1.0). D9 round numbers on the exchange route (F4): +0.03 points, p 0.066, Holm 0.33. No chart level or round-number advice is earned.
- **D11 luck** (F1; F3 not computed). The sum of Δ over the 1,541 fills, 97.7 (in units of one fill's stake), against K3's synthetic null whose 95th percentile is 36.2-42.5 (exploratory p 0.0002-0.0004 by scenario; BH-adjusted over the three scenarios, q 0.0004). Buying at random times with the same exit summed to −23.4 (a level, no percentile).

### 3h. Exploratory splits (BH-adjusted within each table, F1 and F3 separately)

- **Depth gradient** (`explore/depth_gradient.csv`): mean Δ at k = 5 / 6 / 8 / 10 / 12 was +2.5% / +3.5% / +7.5% / +12.8% / +17.7% (F3: +2.2% / +3.4% / +7.5% / +13.4% / +17.4%); slope +2.1% per sigma of depth (95% CI +0.8% to +3.4%; BH q 0.004; F3 +2.2%, q 0.009). The slope rests on 2,962 fills (month-block G 64, G* 15.4). Fewer fills and fewer independent months stand behind the deep rungs: 186 fills in 20 month-blocks at k = 12 (G* 7.0; F3 159 fills, G 17, G* 6.2).
- **Breadth** (`breadth.csv`): market-wide fills Δ +7.3% (1,251 fills; q 0.007; F3 +7.3%, q 0.015); coin-specific fills +2.4% (−1.6% to +6.4%; 290 fills, G 43, G* 8.0; q 0.14; F3 +2.1%, q 0.27); the difference +4.9 points (q 0.076; F3 +5.3, q 0.13). H2R a_f: market-wide +2.3% (q 0.076; F3 +2.0%, q 0.13), coin-specific +2.1% (+0.9% to +3.3%; 293 fills; q 0.007; F3 +1.4%, q 0.13).
- **Weekday vs weekend** (`weekday.csv`): +6.5% vs +5.7% (difference −0.8, q 0.75; F3 −0.1, q 0.95).
- **Flow, from 2021-12** (`flow.csv`): fills with a larger seller burst in the fill minute +2.4 points better (q 0.13; F3 +2.9, q 0.096); a larger open-interest drop in the hour before +2.2 (q 0.16; F3 +2.5, q 0.15).
- **M3 and M8** (`m3_m8.csv`): M3 at a 2% weekly fill probability +14.1% (271 fills; q 0.006; F3 +13.6%, q 0.008); M3 at 5% and 10%: +4.6% (q 0.006) and +2.5% (q 0.007) (F3 +4.7%, +2.3%); M8 (crash-depth calibrated) +0.7% (q 0.051; F3 +0.6%, q 0.11).
- **The user's coins** (`user_coins.csv`; all hindsight; Δ per fill, F1 then F3). With BH q below 0.10 on F1 (F3 in brackets): LDO +10.8% on 26 fills [+10.1%], LINK +8.0% on 53 [+8.4%], UNI +6.4% on 47 [+6.3%], CRV +7.9% on 35 [+7.9%], AAVE +7.6% on 41 [+8.7%], BNB +3.1% on 57 [+3.1%], SKY +6.3% on 19 [+4.7%], INJ +5.8% on 21 [+6.6%], ASTER +6.3% on 8 [+8.1%] and ENA +7.6% on 12 [+6.8%]. **NEAR: +3.4% (95% CI −2.2% to +9.0%; 37 fills, G 20, G* 11.2; q 0.15); F3 +4.3% (−2.2% to +10.5%; 34 fills, G 18, G* 10.5; q 0.17).** BTC +1.6% (q 0.19; F3 +1.0%), ETH +3.1% (q 0.11; F3 +3.7%), SOL +5.1% (q 0.17; F3 +2.7%).
- **HYPE on its perpetual's index** (`hype.csv`; "short history, perpetual-index proxy, no verdict"): 216 bids, 5 fills in 3 months (one on 2025-09-25, three on 2025-10-10, one on 2026-11-14); mean Δ +17.3%, +7.8% without 2025-10-10. HYPE's Binance spot row has 1 fill (Δ +11.8%; F3 +12.8%).

### 3i. The other sensitivity rows (`desc/sensitivity.csv`; each changes P1 one way; none decides anything)

H1 Δ per fill, F1 then the F3 proxy; H2R a_f in square brackets. Every interval uses month-block clusters unless it says otherwise. Every H1 row's estimate is above zero (lowest +1.43%, M1 at 15% depth). Its 95% interval includes zero for the 30- and 90-day lives, P1-G on F3 and M2a at k_A = 6.
- **Programs.** P1-lazy (a resting bid kept if the new level is within 5%) +6.15% (+2.73% to +9.57%; 1,580 fills, G 60, G* 14.7; F3 +6.23%) [+2.22%; F3 +1.86%]. Placement at 13:30 UTC +6.22% (+2.88% to +9.56%; 1,618 fills, G 61, G* 15.2; F3 +6.37%) [+2.16%; F3 +1.84%]. H2R on lives of 1 day (exploratory), 30 and 90 days: +5.08%, +0.65%, +2.19% (F3 +4.84%, +0.41%, +1.48%). P1-G [+2.95%; F3 +2.37%] (its H1 row is in section 3f).
- **Rungs.** k = 5 and k = 12 H1 rows are in section 3h; H2R: k = 5 [+0.93%; F3 +0.54%]; k = 12 [+6.05%; F3 +5.01%].
- **Other level methods.** M1 fixed %, pooled: +4.03% (+2.28% to +5.78%; 5,360 fills, G 61, G* 11.5; F3 +4.17%) [+1.45%; F3 +1.22%]. At 15 / 20 / 25 / 30 / 40 / 50% below: +1.43 / +3.12 / +4.14 / +7.70 / +18.27 / +37.37% (F3 +1.58 / +3.15 / +4.20 / +8.28 / +17.95 / +37.40%). M2a ATR-scaled, pooled: +10.30% (+4.89% to +15.71%; 808 fills, G 42, G* 7.8; F3 +9.88%) [+3.28%; F3 +2.39%]. At k_A = 4 / 5 / 6: +8.09 / +12.12 / +14.82% (F3 +7.61 / +12.30 / +13.78%). M3 pooled: +4.62% (+2.23% to +7.00%; 2,067 fills, G 66, G* 17.8; F3 +4.50%) [+1.65%; F3 +1.21%].
- **Fill rules.** F2 (touch; an illusion bound only): +6.36% [+2.28%]. F3 at s = 2%: +6.89% [+2.00%]; at s = 5%: +8.75% [+2.65%]. F3d at s = 2 / 3 / 5%: +6.20 / +6.75 / +7.61% [+0.67 / +0.64 / +0.87%]. F4: +6.05% [+1.79%]. F5 (deeper-wick sensitivity: not fills this user could get): +7.28% [+3.29%]. F6 was not built.
- **Flip grid** (8 targets × time stops of 24 h, 72 h and 7 days, under rule M; F1; F3 not computed, A1.7): from +3.74% (L × 1.05, 24 h) to +6.97% (R1/2, 7 days). Every 95% interval is above zero; the lowest lower end is +1.68%.
- **Costs** (F1; no F3 rows): C-0, C-EX and C-BUS each give +6.46%.
- **Size** (each fill weighted by its filled dollars; F1; no F3 rows): Q = $1k, $10k and $100k at θ = 1, and $10k at θ = 0.25: +6.34, +6.32, +6.16, +6.26% [+2.24, +2.22, +2.10, +2.18%].
- **Benchmarks** (F1; F3 not computed, A1.7): ±30-day twins +6.35% (+2.86% to +9.84%); pooled twins for every fill +6.42% (+2.85% to +9.99%).
- **B-ALERT delays** (§10.1; H2R's a_f against an alert buyer who waits a fixed time after the fill instead of rule M; descriptive; computed after the audit with `stinkbid_desc.per_bench` and `mean_row`, because the desc stage had not reported them; `results_stinkbid/audit/alert_delays.json`; month-block clusters, G = 58, G* = 14.5, F3 G = 54, G* = 13.8): rule M +2.23% (+0.08% to +4.39%; F3 +1.88%); 2 hours +2.70% (+0.73% to +4.68%; F3 +2.39%); 8 hours +3.43% (+0.99% to +5.87%; F3 +3.06%); 24 hours +6.13% (+1.86% to +10.40%; F3 +6.06%); 72 hours +5.52% (+2.62% to +8.41%; F3 +5.73%). The longer the alert buyer waits, the more a resting bid saves: much of the rebound comes within a day.
- **Clusters, H2R:** episode (+0.09% to +4.38%; G 96, G* 14.5); week (+0.08% to +4.39%; G 98, G* 14.0); two-way coin × month (+0.21% to +4.26%; G 62). On F3: −0.28% to +4.07% (G 80, G* 13.2), −0.28% to +4.05% (G 84, G* 13.0), −0.13% to +3.89% (G 57).
- **Universes:** U-Q1-12 (12-month listing rule) +6.08% (F3 +6.10%) [+2.50%; F3 +1.93%]. U-Q1-xm (no memecoins) +6.25% (F3 +6.29%) [+2.34%; F3 +1.98%]. U-A (24 user-style coins plus MKR; hindsight) +5.82% (+2.43% to +9.21%; 566 fills, G 46, G* 10.9; F3 +5.88%) [+2.04%; F3 +1.56%]. U-Q2 was not built.

## 4. The level sheet

`analysis_2026/stinkbid_sheet.py` (§13); the run of record is `results_stinkbid/sheet/sheet_2026-11-19.txt` (74 Robinhood-tradable coins, with Robinhood's mark prices (the midpoint of its bid and ask, read-only market-data quotes) of 2026-11-19 17:40 UTC passed as `--price`, and `--refresh`; commit 92a6cb1).

- **Per coin:** the reference price and sigma30; MoneyLine now (red adds "a fill here buys against your own trend signal"); whether the coin is large, long-listed (Binance volume) now; a row per rung (limit on Robinhood's tick, depth in % and sigma, wait, Robinhood odds per week (F3) with the Binance upper bound, capacity and Q_max); the basis of the odds ("N fills in E episodes", the coin's own history shrunk to the U-Q1 rung, or U-Q1 pooled odds for a coin with no U-Q1 history); the orders at $1,000 per rung; the flip target for each rung (shown because H1 passed under rule M); and the "best rung" k = 10 (depth gradient BH q 0.004, exploratory). No chart-level rows: H4 did not pass and D10 earned none.
- **On 2026-11-19** (counted from the sheet's text): 72 of 74 coins had a red MoneyLine (MEGA and SENT green); 29 were large, long-listed; 22 are marked halted for New York residents in the 2026-11-18 catalog, HYPE among them; ORCA has no bids in the U-C history behind the footer ("no history for ORCA"), so the footer covers the other 73 coins (ORCA has Binance spot bars from 2024-12-06; its rows use U-Q1 pooled odds).
- **Footer** (U-C coins' history, hindsight; F3 first): "expect fills on about 23 days a year; the longest stretch without any fill was 173 days; on the worst day, 99% of the ladder filled" [F3 worst day 2025-10-10: 148 of 150 live orders; Binance spot: 27 days a year, 173 days, 98%; history of 73 coins, none for ORCA]. Total cash reserved for all 74 coins at $1,000 per rung: $221,999.57. The route note: "on the default route, the coin's mid must fall about 1% below your price before it fills; a chart touch is not a fill."
- **Safeguards.** A fresh price is required (`--price` or a close under 24 hours old); a `--price` more than 2× away from the last close is refused without `--force-price`; the order diff lists cancel / keep / place lines; the first small test order is printed. The Robinhood catalog is required for ticks and sizes; K7 checked 796 reference orders by the sheet's rule with 0 violations.

## 5. Controls and the outcome audit

**Controls** (§10.5; run on the final data before any outcome; `results_stinkbid/controls/summary.txt`; **every control passed**):
- **K1 known answer.** On synthetic 1-minute markets the engine matched an independent oracle: K1a (no jumps) 925 fills, r_f +0.0019 vs +0.0019; K1b (market-wide jumps that do not revert) 1,791 fills, −0.1337 vs −0.1337. Two deliberately wrong engines (filling at the minute's close or low) failed K1b by +33.9 and +34.2 SE, as required. K1b's fill rates were within ±25% of real P1's (k = 6: 6.23% vs 7.33%). K1c (regime timing alone): Δ X-FLIP −0.6%, X-HOLD-90 −6.1% (SE 5.1%). K1d: delisting haircuts at equal rates for fills and twins.
- **K2 positive control.** With half of each jump reverting (30-minute half-life), the engine found H1's Δ +7.7%, t 6.69 under rule M (and at bot latency), matching the oracle.
- **K3 inference.** 5,000 null replications per scenario (base, high dispersion, heterogeneous effects); every test on the nominal rule in the rerun. MDE (nominal formula, base / high / hetero): H1 4.51% / 5.42% / 4.77%; H2R 0.62% / 0.95% / 1.65%; H4 0.89% / 1.59% / 1.89%. NO EDGE reachable under the null: H2R 100% / 98% / 83%; H1 62% / 51% / 52%; H4 14% / 0% / 0%. Pass rule (§10.5): the 95% upper end of each false-PASS rate is at most 1.5× nominal. Worst scenario per test (`controls/summary.txt`): H1 (high dispersion) 1.90% at the 1.67% level (upper end 2.32%), 3.06% at 2.5% (3.58%), 5.50% at 5% (6.17%), NO EDGE bound missed 0.96%; H2R (heterogeneous) 1.36% (1.72%), 2.28% (2.73%), 5.12% (5.77%), missed 1.64%; H4 (heterogeneous) 0.68% (0.95%), 1.16% (1.50%), 2.92% (3.43%), missed 0.84%. Empirical MDEs, base / high / hetero: H1 4.75 / 5.65 / 5.03%; H2R 0.76 / 1.14 / 1.97%; H4 0.76 / 1.41 / 2.11%. The first controls run, on the code before Addendum 1 and since superseded, passed every control but flagged H1 at the 1.67% level: 2.1% (base) and 2.0% (high), with upper ends 2.83% and 2.71% against 2.5% (A1.9).
- **K4 look-ahead.** 50 synthetic cut minutes × scale / delete / 3-day gap: 2,250 comparisons, 0 failing; real universes (177,703 rows), levels (6,554) and 288 real fill and capacity runs unchanged under cuts.
- **K5 fill audit.** 41,909,531 engine checks, 0 violations; real P1's 1,544 fills re-audited, 0 violations and 0 gap-through fills (265,340 gap-through fills listed in the synthetic checks).
- **K6 capacity.** 200 fills: the 1-minute approximation against aggTrades, median ratio 0.99 (life 1.00).
- **K7 ticks and sizes.** 0 of 447,704 levels off tick; 796 reference Robinhood orders, 0 violations (110 rungs split at the maximum size).
- **K8 venue proxy.** Of 1,544 P1 fills, F3 (1%) removes 11.7%, F3 (3%) 24.3%, F3d (1%) 19.8%; with the index converted to USD (§7), F3 removes 11.5% (s = 1%) and 24.1% (s = 3%); F5 (deeper-wick sensitivity: not fills this user could get) also fills 97.5%; 25 are F3-unverifiable.

**The outcome audit** (after the verdicts of record, commit eee2ddf). Seven independent lenses wrote their own code (no imports of the functions checked). The workflow was stopped after all seven lenses and after three verifiers (reproduce, refute, impact) had tested five findings; a follow-up verified the remaining findings on the committed record and ran a completeness critic.
- **What it reproduced.** H1, H2R, Holm and all 13 H1/H2R gates, the 7 bot gates, the F3-kept rows and the A2.7 alternatives, to machine precision with the runner's seeds. From raw Binance 1-minute bars, with its own rule-M clock, tick inference and exit code, one lens rebuilt all 33,486 P1 bids' inputs, levels and fill outcomes, and every fill's exit and alert price exactly; another re-checked all 1,364 F3 alert buys and 1,361 F3 exits on the index bars; 1,700 twins were rebuilt from their seeds. H4's regressions, Romano-Wolf bootstrap, bounds and gates reproduced. Levels rebuilt from data cut at Sunday's close matched; U-Q1 rebuilt from the raw panel matched on all 25,100 coin-months; the 11 U-Q1 coins whose trading later ended keep all 157 fills. Nothing was chosen after the results: the committed sources hash to the runs' stamp, and the last code or pre-registration change (989e134) came before the primary stage.
- **Corrections** (reporting only; commit f6c15f5, reruns cff65d7 and 0a87d41; no verdict, test statistic or gate changed):

| what | before | after |
|---|---|---|
| **1. Size cap Q_max (major).** It summed seller dollars over the order's whole 7-day life; the draft (§7.3, §8.3) defines it on the fill's own capacity window. | k = 6 / 8 / 10: $101,907 / $81,988 / $76,820 per order | **$4,706 / $5,218 / $6,071 per order** (13-22 times smaller: 21.7×, 15.7× and 12.7× at k = 6 / 8 / 10; the deviation log and the audit wrote "17-22 times"; the printed pairs give 13-22) |
| 2. H4's printed MDE used one test's critical value, not the four-method Bonferroni of the test as run | 0.94% | 1.17% |
| 3. H4's "without the top month-block" used M7's own month-blocks, not the shared partition (A1.8) | +0.28% | +0.12% |
| 4. §12 / A1.7 reporting | answer numbers without their F3 twins | F3 beside every Binance number (flip return +4.8%, F3 +4.8%; worst day 95%, F3 95%; MoneyLine 62.8% red, F3 63.8%; D-H2 −3.5%, F3 −5.2%; D-H3 +4.3%, F3 +2.9%; D8 +5.5%, F3 +5.7%); "F3 not computed" on the knife and D-H5 rows; G and G* with every recommendation interval; U-C rows labelled hindsight; H4's missing U-C row stated |

- **The follow-up and its completeness critic.** The follow-up confirmed the remaining findings (all among the corrections above). Its critic found two more minor defects. They are documented here, not fixed in code: neither changes a verdict or an answer sentence, and the Sharpe is computed in the engine, whose change would invalidate every cached run.
  - (5) D7 lacks the single-event rows of §10.4. The critic's rebuilt values are in section 3e.
  - (6) The D7 table's Sharpe for the T-bill accounts is a compounding artifact: 2.07 printed for B-TBILL and −1.26 for B-TBILL-OWN; the true value is 0.
  The critic also measured what one flip looks like, the 2023-26 half, the bid lives and the alert-entered flip (see "How to read H1" and section 3e).
- **The audit's scripts and small outputs** are in `results_stinkbid/audit/` (each folder is one agent's code and results; large intermediates are left out, and the scripts regenerate them).

## 6. Deviations

Every deviation is logged in `results_stinkbid/stages/deviations.jsonl` and `stages/log.jsonl`. **Nothing here changed a verdict.**
- **A2.4 (before any outcome).** The data stage ran again on the final rebrand registry. Its logged reason said U-Q1 +23 coin-months; it had been written before a second check added BCC→BCHABC, and the committed registry gives +33 (LUNC 17, BCH 10, VET 6), as A2.1 states (a logged note).
- **A2.5 (after the controls, before any outcome).** The runner read the condensed K3 block of `controls/summary.json` instead of the full calibration, so H2R's then simulation-calibrated rule would have been silently dropped. Fixed (only `k3_calibration.json` is read; a disagreeing summary closes the gate). No control result changed; nothing reran.
- **A2.6 (after the fill counts, before any outcome).** A check of every hand-off between stages (five reviewers, a critic, three verifiers per finding) found M7's futures inputs missing for coin-days Addenda 1-2 had added (AAVE, EGLD, LUNC, GRAM): M7 abstained at 162 placements. The inputs were fetched (65 real M7 levels and 260 placebos added; 11 placements stay without data because BTTC and SLP are not in Binance's archive). The run cache and controls gate now follow the data and code. Data, controls and fill counts ran again.
- **A2.7 (after the controls rerun, before any outcome).** H2R's K3 rule changed between the two controls runs. In the first, its heterogeneous-null false-PASS rate at the 1.67% level was 2.08% with an upper end of 2.51%, 0.01 point over the 2.50% limit, so it took the simulation-calibrated rule; in the rerun 1.36% (up to 1.72%), so the nominal rule. The two runs are two Monte Carlo draws of the same null. The rerun decides (fixed before any outcome); H2R is also shown under both other rules (section 2a), and all verdicts are the same.
- **Out-of-memory stops.** The Linux out-of-memory killer stopped three stages. Fill counts (08:13 UTC, before any outcome): one of four engine workers was lost during P1 on U-C; resumed with three workers. **Primary** (14:34 UTC, during the first outcome computation, exit 137, 4.2 GB main process with three engine workers): killed while computing P1 on U-C, before any test statistic; restarted with two workers, not a rerun. **Desc** (16:44 UTC, after the verdicts of record, exit 137, 6.7 GB while collecting H4-all's outcomes, with two engine workers and an audit script running beside it): restarted with one worker, not a rerun. No result depends on the number of workers.
- **Post-results corrections** (17:28 UTC, logged as a rerun of primary, report, desc and explore): the four audit corrections of section 5 (code commit f6c15f5).
- **Not built:** F6 (Coinbase) and U-Q2 (DefiLlama revenue); their rows are empty.
- **Not reported by the desc stage:** B-ALERT's fixed-delay sensitivities at 2, 8 and 24 h (§10.1) were computed for every fill but not tabulated (only the 72-h delay appeared, in D8). They were computed after the audit with the desc stage's own functions and are in section 3i (`results_stinkbid/audit/alert_delays.json`).

## 7. Caveats

- **Binance spot is not Robinhood.** The primary fill rule is Binance spot. Robinhood's default route fills only when its ask, about 1% above the mid, reaches your bid; F3 imitates that with Binance's index, which removes 11.7% of fills. No Robinhood crypto history exists here, so every Robinhood-route number is a proxy, and Robinhood's behaviour in a crash (spreads, outages, halts) is unknown. Five known Robinhood outage windows were blocked for F3 fills and exits.
- **Concentration** (audit; F1, F3 not computed). By contribution, three episodes carry 42.3% of H1's total; without the top five, Δ is +3.75%; 2021 alone gives 45%. An edge that lives in the two or three largest crashes cannot be tested at any size (§10.3).
- **Since 2023 the flip was much weaker** (the critic; F1 unless stated): the average flip made +2.7% (95% CI −0.7% to +6.0%; G = 33, G* = 8.5), H1's half-2 Δ of +4.4% does not clear E (p 0.33), and the flip account beat B-MIX by only +0.3 points a year (F3 +0.4). The pre-registered test pools 2020-2026; the full-sample PASS rests heavily on 2020-22.
- **Regime.** Twins are drawn more than six months from each fill, so the comparison also reflects whether crashes fell in bear or bull stretches (K1c: −6.1% per 90 days from regime timing alone, SE 5.1%, one synthetic world). It matters more for D-H2 than for the 72-hour flip (K1c: −0.6% for the flip).
- **Survivorship was handled.** U-B includes dead coins; delistings take a 30% haircut (0% and 100% as sensitivities; H1's mean r_f unchanged at +4.82%, F3 +4.84%); the 11 U-Q1 coins whose trading later ended keep all 157 fills. U-A and U-C are hindsight lists.
- **K3's synthetic panels were less dispersed than H2R's real data.** H2R's real SE is 1.8-4.7 times K3's null SEs, so its realized MDE (3.24%) is above E (2%). H1 and H4 match their K3 scale.
- **Pooled twins** (audit; F1, F3 not computed). 149 of 1,541 fills (9.7%) use twins pooled from all U-Q1 coins (fewer than 182 eligible days of their own); without them H1 is +6.51%.
- **Rule M at the 07:00 New York boundary** (audit; F1, F3 not computed) gives 49 fills a go-live delay under 60 minutes; they average −1.24%. The engine also lets a resting target fill inside the go-live minute (twins get the same rule); under the strict reading, 2 exits change and H1 moves by −0.04 points.
- **E's input f.** P1 realized 2.41 fills per rung-year, not 2.26; at the realized rate E would be 3.63%. E is fixed and affects only NO EDGE.
- **The leave-out drift row** (+4.35%, 95% CI +0.74% to +7.97%; 1,540 fills, month-block G 58, G* 14.5; F1, F3 not computed) subtracts a gross drift from a net return (the literal formula), so it is not cost-matched; cost-matched it is about +6.2% (audit).
- **Bad prints are real trades and were kept.** Dropping fills with under $1k of seller dollars below L in the fill minute, or whose index stayed above L (462 fills), gives H1 +5.55% and H2R +1.59% (F1; the rule concerns Binance spot prints, so no F3 row).
- **Cash.** Whether cash reserved for an open Robinhood crypto order earns sweep interest is not documented; the account test assumes it does not.
- **HYPE** has 5 fills on a proxy price; nothing here is a verdict on it.

## 8. Files and how to rerun

**Sources and files.**
- **Pre-registration:** `analysis_2026/STINKBID_PREREG.md` (frozen 2026-11-18, commit 72ac2a4), with Addenda 1 and 2 (A2.1-A2.7).
- **Research notes:** `analysis_2026/research_notes/Stink bids/` (`mechanics.md`, Robinhood order mechanics and venues; `evidence.md`; `data_inventory.md`; `design_draft.md`; the three critiques; `build_spec.md`).
- **Code:** `analysis_2026/stinkbid_run.py` (the runner), `stinkbid_data.py`, `stinkbid_levels.py`, `stinkbid_engine.py`, `stinkbid_stats.py`, `stinkbid_controls.py`, `stinkbid_desc.py`, `stinkbid_sheet.py`; `fetch_stinkbid_data.py`; reference files in `analysis_2026/stinkbid_ref/`.
- **Results:** `analysis_2026/results_stinkbid/`: `verdicts.txt` (the answer), `verdicts.csv`, `answer.json`; `primary/`; `desc/`; `explore/`; `controls/`; `fcount/`; `sheet/`; `stages/` (markers, `log.jsonl`, `deviations.jsonl`); `controls_first/` (the first controls run's H2R calibration, A2.7); `data/` (candidate days and prefetch plans); `sheet_inputs.json` (the sheet's inputs from the results). Raw data and the engine's run cache are in `data/stinkbid/` (gitignored).
- **Summary:** `HANDOFF.md` section 5.23; `analysis_2026/FINDINGS.md`, entry of 2026-11-19.

**How to rerun** (Git Bash on Windows, from the repo root; each stage refuses to run until the one before it is complete; `--rerun --reason "..."` reruns a completed stage and logs it as a deviation; times are from the recorded run, with 2-4 engine workers):
```
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run status            # which stages are complete
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run data --jobs 4     # 1. data, levels, prefetch (~32 min on the rerun)
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run controls --jobs 4 # 2. K1-K8 (~61 min)
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run fcount --jobs 4   # 3. fill counts, no outcome (~87 min)
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run primary --jobs 2  # 4. H1, H2R, H4 (~2 h; seconds from the cache)
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run report            # 5. Holm, verdicts, the answer (~2 min)
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run desc --jobs 1     # 6. descriptive estimands, sensitivity rows
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run explore           # 7. exploratory splits
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run sheet -- --refresh --price NEAR=3.3039   # 8. the level sheet
.venv/Scripts/python.exe -m analysis_2026.stinkbid_run selftest          # gating, answer map, synthetic end to end
```
The data stage needs several GB of disk for the 1-minute index history (about 6.8 GB under A1.6's rule). Use fewer workers (`--jobs 2` or 1) on a machine with less memory: the out-of-memory stops in section 6 came from 2-4 engine workers of about 3 GB each beside a main process of 4.2-6.7 GB (for desc, with an audit script running alongside). The sheet alone runs without the run cache's outcomes: `.venv/Scripts/python.exe -m analysis_2026.stinkbid_sheet --refresh --coins NEAR --price NEAR=3.3039`.
