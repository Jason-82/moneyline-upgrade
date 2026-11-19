# Stink Bids: Selling the Fills Into the Rebound Beat Random Buys of the Same Coins; Whether That Clears Its 3.75% Bar, Whether Resting Beats Alerts, and Whether Chart Levels Help, the Data Cannot Tell

**Question (2026-11-18).** The user asked, in their words: "a strategy that looks at highly volatile yet 'solid' cryptos that I wouldn't mind owning, like HYPE, like NEAR, projects with real revenues.... it looks at the charts and through some process figures out good levels to place 'stink bids'; that is, bids that are way below current price, in the hopes of catching a momentary down wick to fill the trade... maybe it wouldn't even need to place any trades for me, just analyze each chart and give me solid choices for the levels of the stink bids and I could place the limit trade myself. can you help me elucidate/test?"

The pre-registration (`analysis_2026/STINKBID_PREREG.md` §1) turned this into four questions:
1. **Flip:** are fills, sold into the rebound by hand, better buys than random buys of the same coin with the same exit?
2. **Rest vs alert:** if you are going to buy after crashes anyway, does a resting bid buy more coin per dollar than a price alert at the same level followed by a manual buy?
3. **Levels:** are chart-based levels better than plain volatility-scaled levels at the same depth?
4. **Usable output:** what level sheet should you get?

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

**Short answer.**

**What the verdicts mean.** Each test gets one of three verdicts, set in advance. **PASS:** the effect is above zero after allowing for the three tests (Holm), and every robustness gate written in advance held. **NO EDGE:** even a generous upper limit (one-sided 98.33%) is below E, the smallest effect worth acting on; only this verdict may be read as "it does not work", and no test here got it. **INCONCLUSIVE:** neither; "the data cannot tell", stated with its MDE.

The verdicts, in the pre-registered order (`results_stinkbid/verdicts.txt`, `verdicts.csv`):
1. **Rest vs alert (H2R): INCONCLUSIVE. The data cannot tell.** A resting bid bought +2.2% more coin per dollar than an alert buyer at the same level who bought after rule M's delay (an hour, or the next 07:00 New York time at night) (95% CI +0.1% to +4.4%; 1,544 fills, month-block clusters G = 58, G* = 14.5; Robinhood-route proxy F3: +1.9%, 95% CI −0.3% to +4.0%, 1,364 fills, G = 54, G* = 13.8). The p-value (0.0216) cleared Holm (adjusted 0.0432), but one gate failed: the 2023-2026 half was −0.1%. An effect under about 3.2% per fill would not show (MDE).
2. **Flip (H1): PASS.** Stink-bid fills sold into the rebound by hand beat random buys of the same coin with the same exit by **+6.3% per fill** (95% CI +2.8% to +9.9%; 1,541 fills, month-block clusters G = 58, G* = 14.5; p 0.0009, Holm-adjusted 0.0028). On the Robinhood-route proxy (F3): +6.5% (95% CI +2.4% to +10.5%; 1,361 fills, G = 54, G* = 13.8). Every gate held.
3. **Levels (H4): INCONCLUSIVE. The data cannot tell.** The best of four chart methods (M7, an estimated liquidation band) beat plain levels at the same depth by +0.2% per fill (95% CI −0.6% to +1.1%; 1,487 stacked fills, month-block clusters G = 33, G* = 10.4; p 0.84). On F3: +0.0% (95% CI −0.7% to +0.7%; 1,330 fills, G = 37, G* = 10.5). An effect under about 1.2% per fill would not show (MDE).

The recommendation lines, as printed in `verdicts.txt` (the pre-registered table, applied in order):
> - "Resting bids and alerts can't be told apart (an edge under about 3.2% wouldn't show). Prefer alerts: your cash stays free and earning."
> - "Selling stink-bid fills into the rebound by hand beat random buys of the same coin by 6.3% per fill (95% CI +2.8% to +9.9%). After Robinhood costs, a flip made +4.8% on average (+4.8% on the Robinhood-route proxy, F3). It held in both halves, without the biggest month and crash, and on Robinhood-like prices. The sheet shows the flip target. [1541 fills, month-block clusters G = 58, G* = 14.5]"
> - "Can't tell; the sheet uses plain volatility-scaled levels."

**How to read H1: five things the PASS does not say.**
- **It beats random buys; it is not shown to clear the 3.75% bar.** H1's PASS means Δ > 0. E = +3.75% per fill is the pre-registered amount that pays for the round trip (1.88%) and the cash the bids tie up. The 95% interval's lower end (+2.8%) is below E. The outcome audit's one-sided test of Δ > 3.75% gives t 1.58, p 0.069 (against the Gold-sweep E of 2.26%: p 0.0135). So the data show the flip beats random buys of the same coin, not that it clears 3.75%.
- **The edge is concentrated in a few market-wide crashes and in fast, deep wicks.** By contribution, three episodes (2021-05-19, 2025-10-10 and 2021-12-04; 13.6% of fills) carry 42.3% of the total Δ; without them Δ is +4.24%, and without the top five +3.75% (= E). 2021 alone gives 45% of it (Δ +21.7% on 203 fills); 2022 gave +1.5% and 2023 −0.7%. Fills that slid slowly into the level earned +2.85% (CI +0.06% to +5.64%); fills from a fast drop (previous minute's close 3% or more above the level) earned +13.4%. These are the audit's F1 numbers; it did not compute F3 versions.
- **"You could run it on Robinhood" may not be said.** The pre-registered account test did not pass: the flip account on F3 beat B-MIX (the same coins held at the account's average invested fraction, the rest in T-bills) by +4.42 CAGR points a year, with a 12-month block-bootstrap interval of −0.83 to +11.25, not above zero (`answer.json`, `desc/d7_compare.csv`).
- **The Robinhood numbers are proxies.** F3 stands in for Robinhood's route; no Robinhood crypto history exists here.
- **"Prefer alerts" (H2R) and "flip the fills" (H1) were not tested together.** H1's edge was measured on resting-bid fills. The alert buyer paid on average 2.2% more per fill (1.9% on F3), so a flip entered by alert would likely earn less than H1's +6.3%.

**What to do.**
- **If you use the sheet, treat it as a manual tool for a small, crash-only position, not as income.** Run it each week in Git Bash from the repo folder, with each coin's current mid from the Robinhood app (the numbers below are the 2026-11-19 references; replace them):
  ```
  .venv/Scripts/python.exe -m analysis_2026.stinkbid_sheet --coins NEAR,SOL,HYPE --price NEAR=3.3039 --price SOL=74.04 --price HYPE=68.72
  ```
  Without `--price`, the sheet uses the latest Binance daily close and refuses a coin whose close is more than 24 hours old; `--refresh` first fetches newer daily closes from the Binance archive. `--per-rung 500` sets dollars per rung (default $1,000). Without `--coins` it prints all 74 Robinhood-tradable coins. It writes `results_stinkbid/sheet/sheet_YYYY-MM-DD.txt/.csv` and an order diff against last week's sheet ("cancel X, place Y"). It never places, previews or cancels orders.
- **What the columns mean** (section 4): the limit on Robinhood's tick; depth below the reference in % and in sigma30 units; median weeks to a fill if re-placed weekly and the chance of no fill within a year; Robinhood fill odds per weekly bid (F3 proxy, with a 95% interval) beside the Binance figure (an upper bound); past seller dollars below the level (median / 10th percentile) and the size cap Q_max; your MoneyLine now; whether the coin is in the "large, long-listed (Binance volume)" group; the flip target.
- **The flip rule.** When a bid fills, enter a limit sell at the sheet's flip target **R1/2, halfway back from the fill to the reference price** (R1/2 = L + (P0 − L)/2). If it has not filled after 72 hours, sell at market.
- **Size.** Keep each order within the size cap: about **$4,706 at k = 6, $5,218 at k = 8 and $6,071 at k = 10** on the U-Q1 pool (a quarter of the 10th percentile of seller dollars printed below the level during the wick; Binance spot book, no F3 equivalent). The sheet prints a per-coin cap where the coin has history; it can be lower (NEAR k = 6: $1,049).
- **Hold cash for every rung on every coin at once, and size the ladder as one position.** Bids fill together: on 2025-10-10, 94 of 99 live bids in the study's main universe filled the same day (F3: also 94 of 99). On the sheet's 74 coins the worst day filled 148 of 150 live orders (F3 proxy; Binance spot 98%; hindsight coin list). Be willing to hold through a further 50-80% fall.
- **Cancel a coin's bids on news about the coin itself** (a hack, exploit, depeg, delisting or regulatory action). Coin-specific collapses (LUNA, FTT, OM) look like ordinary wicks on the first day.
- **Decide in advance how a fill relates to your MoneyLine.** 62.8% of past fills came when the coin's MoneyLine (the replicated pre-October-2026 version) was already red at placement (F3: 63.8%). On 2026-11-19, 72 of the sheet's 74 coins were red (counted from `sheet_2026-11-19.txt`). A fill buys against your own trend signal.
- **Prefer alerts or resting bids?** The pre-registered line says "prefer alerts" because the data cannot separate them and alerts keep your cash earning. But the flip's edge was measured on resting fills, and alert buyers paid about 2.2% more per fill. If you want the flip, the evidence is for resting bids; if you want to buy after crashes and hold, alerts lose little that the data can see.
- **HYPE.** The sheet prints HYPE's levels with U-Q1 pooled fill odds and no verdict: about 17 months of Binance perpetual data and 2 months of Binance spot; its only deep-wick day (2025-10-10) came 13 days before Robinhood listed it; HYPE is a venue token whose value depends on Hyperliquid's volume and solvency (FTT, the token of FTX, fell 97.6%); and it is not tradable on Robinhood for New York residents (the 2026-11-18 catalog marks it halted for NY residents).
- **NEAR, as an example** (reference $3.3039, sigma30 5.60%; MoneyLine red; large, long-listed: yes):

  | rung | limit | depth | median wait / no fill in 1 year | Robinhood odds per week (F3) [95%] | Binance (upper bound) | cap per order | flip target |
  |---|---|---|---|---|---|---|---|
  | k = 6 | 2.3606 | 28.6% | 10.1 weeks / 7.4% | 6.1% [0.0%-15.6%] | 7.4% | $1,049 | 2.8323 |
  | k = 8 | 2.1104 | 36.1% | 17.3 weeks / 1.2% | 3.3% [0.0%-10.5%] | 3.4% | $67k | 2.7072 |
  | k = 10 | 1.8867 | 42.9% | 27.4 weeks / 26.0% | 2.3% [0.0%-10.7%] | 2.4% | $169k | 2.5954 |

- **Deeper rungs earned more per fill but fill less often** (exploratory, BH-adjusted). Mean Δ rose from +3.5% at k = 6 to +7.5% at k = 8 and +12.8% at k = 10 (F3: +3.4%, +7.5%, +13.4%); the slope is +2.1% per sigma of depth (BH q 0.004; F3 +2.2%, q 0.009). Weekly fill odds fell from 7.3% to 4.0% and 2.6% (F1; F3, the sheet's U-Q1 pooled odds: 6.4%, 3.5%, 2.3%), and the chance of no fill in a year rose from 0.5% to 18.6% (F3: 0.9% to 21.9%). The sheet marks k = 10 as the "best rung" under the pre-registered display rule (BH q < 0.10).
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
- **U-A** (24 user-style coins plus MKR) and **U-C** (the coins tradable on Robinhood on 2026-11-18) are **hindsight** lists: reported, never deciding.
- **HYPE** has Binance spot only from 2026-09-24. It is reported on its perpetual's index price: "short history, perpetual-index proxy, no verdict".

**Programs and orders.** **P1** (primary): every Monday at 03:30 UTC, on every U-Q1 coin, bids at k = 6, 8 and 10 with a 7-day life, cancelled and re-placed weekly; each bid-week is an independent, fully cash-backed order. 2020-01-06 to 2026-11-09: 33,486 bids, 1,544 F1 fills (F3: 1,364) in 62 months and 96 crash episodes (`fcount/fcount.txt`). Variants: lives of 1, 30 and 90 days (90 = Robinhood's good-till-cancelled life), P1-lazy, P1-G (bids only while MoneyLine is green), placement at 13:30 UTC, rungs 5 and 12, fixed-% (M1), ATR-scaled (M2a) and fill-probability-calibrated (M3) levels.

**Fill rules** (§7): F1 (primary), F2 (touch; illusion bound only), F3 at s = 1% (gate on every PASS; also s = 2, 3, 5%), F3d (a whole index minute below; "dwell"), F4 (Robinhood's exchange route), F5. A resting bid fills at its limit even when the minute gapped through it.

**Exits** (§8): **X-FLIP**, the flip: a limit sell at R1/2, live from rule M; else sell at market at the first live minute after M(fill + 72 h). **X-FLIP-bot:** the same with the sell live 1 minute after the fill (a bot's latency). A flip grid of other targets and time stops; holds of 7-365 days; hold to the end; X-ML (hold until the first red MoneyLine close after a green one).

**Costs** (§9): C-RH primary, 0.95% each way (about 1.9% a round trip). C-EX, C-0 and C-BUS as sensitivities. On F3 the spread is part of the trigger and exit (route-specific exits, §8).

**Benchmarks** (§10.1): **B-TWIN** (the twins, for H1 and H4); **B-ALERT** (an alert at the same level, then a market buy at rule M's time; a_f = alert price / L − 1 is the resting bid's coin-count advantage, for H2R); B-POST, B-ML, B-MKT; for the accounts, B-MIX, B-TBILL, B-DCA, B-HOLD, B-ALERT, B-ML and their "-OWN" versions.

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

| test | estimate per fill | 95% CI | n | G / G* (month-blocks) | p (WCR / G*) | Holm-adjusted p (level) | 98.33% bound vs E | MDE | gates | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **H2R** rest vs alert | +2.23% | +0.08% to +4.39% | 1,544 | 58 / 14.5 | 0.0156 / 0.0216 | 0.0432 (0.025) | +4.61% vs +2% | 3.24% | half 2 failed | **INCONCLUSIVE** |
| **H1** flip | +6.34% | +2.80% to +9.88% | 1,541 | 58 / 14.5 | 0.0001 / 0.0009 | 0.0028 (0.0167) | +10.24% vs +3.75% | 5.33% | all 7 held | **PASS** |
| **H4** levels (M7) | +0.23% | −0.62% to +1.09% | 1,487 | 33 / 10.4 | 0.5629 / 0.8409 | 0.8409 (0.05) | +1.16% vs +1% | 1.17% | half 1 failed | **INCONCLUSIVE** |

The p that enters Holm is the larger of the two. H1 had the smallest p, so it was judged at 0.05/3; H2R at 0.05/2; H4 at 0.05.

**Beside every headline** (`verdicts.txt`; F3 = Robinhood-route proxy; U-C = Robinhood-listed coins, hindsight):

| row | H2R a_f | H1 Δ | H4 b (M7) |
|---|---|---|---|
| primary, F1 | +2.23% (+0.08 to +4.39; 1,544; G 58, G* 14.5) | +6.34% (+2.80 to +9.88; 1,541; G 58, G* 14.5) | +0.23% (−0.62 to +1.09; 1,487; G 33, G* 10.4) |
| F3 (s = 1%), Robinhood-route proxy | +1.88% (−0.3 to +4.0; 1,364; G 54, G* 13.8) | +6.45% (+2.4 to +10.5; 1,361; G 54, G* 13.8) | +0.02% (−0.7 to +0.7; 1,330; G 37, G* 10.5) |
| F3d (dwell, s = 1%), proxy | +0.55% (−1.5 to +2.6; 1,239; G 52, G* 13.1) | +5.60% (+1.4 to +9.8; 1,236; G 52, G* 13.0) | not computed |
| F3 (s = 3%), proxy | +2.24% (−0.2 to +4.7; 1,170; G 48, G* 12.7) | +7.56% (+3.1 to +12.0; 1,167; G 48, G* 12.7) | not computed |
| U-B (top 100, dead coins included; F1 only, F3 not computed, A1.7) | +2.44% (+0.2 to +4.6; 4,712; G 68, G* 13.4) | +6.84% (+2.8 to +10.9; 4,709; G 68, G* 13.3) | not a gate |
| U-C, F1 (hindsight) | +1.93% (−0.3 to +4.2; 1,668; G 56, G* 11.9) | +7.32% (+4.1 to +10.6; 1,665; G 56, G* 11.9) | not computed (see below) |
| U-C, F3 (hindsight; proxy) | +1.52% (−0.8 to +3.8; 1,459; G 55, G* 10.5) | +7.28% (+3.7 to +10.8; 1,455; G 55, G* 10.5) | not computed |

H4 has no U-C row. H4 ran on U-Q1 only; its futures and index inputs were never planned for U-C. This omission was found by the outcome audit after the results and is stated in `verdicts.txt`.

### 2a. H2R, rest vs alert: INCONCLUSIVE

- **The gates.** Five of six held: first half, without the worst month-block, without the biggest episode, U-B and F3 were all above zero. **The second half was not**: 2020-22 +5.18% (687 fills; t 3.31), 2023-26 −0.13% (857 fills; 95% CI −2.04% to +1.78%) (outcome audit; F1, the audit did not compute F3 halves). By year within half 2: 2023 −0.51%, 2024 +0.72%, 2025 −2.78%, 2026 +1.94%.
- **The Holm clearance is fragile** (audit; F1). With a plug-in df of 3.6 instead of G* − 1, the p is 0.048 and the Holm-adjusted p 0.097 (audit).
- **The realized MDE (3.24%) is above E (2%)** and above the pre-registered expectation of about 1.2%. H2R's real SE (1.00%) is 1.8-4.7 times the SEs of K3's synthetic nulls: the real data are more dispersed than the controls' panels (section 7).
- **Concentration and single events.** The three largest episodes by fills (2022-11-08..09, 2025-10-10, 2023-08-15..17) pulled the total down (−9.5% of it); without them +3.00%. Without 2025-10-10 +2.79%; without 2021-05-19 +1.58%; without the top month-block +2.17%. F3: +2.43%, +1.27% and +1.77% for the same three removals.
- **A2.7's other K3 rules.** H2R's control rule flipped between two Monte Carlo runs (section 6). Decided under the first controls run's simulation-calibrated rule (critical t 2.537), H2R's p is 0.0248, Holm-adjusted 0.0496, bound +4.61%, MDE 3.41%. Under the record's other rule (simulation-calibrated with the record's null draws, critical t 2.315), p 0.0208, Holm 0.0416, bound +4.62%, MDE 3.19%. **All three verdicts are the same under every rule:** H2R INCONCLUSIVE, H1 PASS, H4 INCONCLUSIVE.

### 2b. H1, the flip: PASS

- **Gates (all held):** mean r_f > 0 (+4.82% per fill after Robinhood costs; F3 +4.84%); both halves positive; positive without the worst month-block and without the biggest episode; positive on U-B (+6.84%) and on F3 (+6.45%).
- **Not a Binance-only result** (A1.8). Re-run on the F1 fills that F3 also fills: +5.76% (95% CI +1.74% to +9.77%; 1,362 fills, G 56, G* 13.5), p 0.0043, below the 0.0167 Holm level at which H1 passed.
- **Bot latency.** With the sell live 1 minute after the fill (X-FLIP-bot): +6.67% (95% CI +3.00% to +10.33%), p 0.0008, Holm-adjusted in H1's place 0.0025, bound +10.70%: PASS. It does not pass "only at bot latency"; the manual clock passes too. F3 bot row: +6.48% (+2.46% to +10.49%; 1,361 fills, G 54, G* 13.8).
- **E sensitivity** (§10.3). With E = 2.26% per fill (reserved cash earning the 3.35% Gold sweep), H1 would still be PASS (the bound +10.24% is not below 2.26%). Against E itself (3.75%), the audit's one-sided test gives p 0.069; against 2.26%, p 0.0135. E's input f was 2.26 fills per rung-year; P1 realized 2.41, which would give E = 3.63%. E is fixed by §10.3 and affects only NO EDGE.
- **Concentration and single events** (pre-registered: episodes ranked by fill count). The three largest episodes (2022-11-08..09, 2025-10-10, 2023-08-15..17) give 14.2% of the total; without them +6.67%. Without 2025-10-10 +6.06% (F3 +6.04%); without 2021-05-19 +5.34% (F3 +5.45%); without the top month-block +6.57% (F3 +6.76%). **By contribution** (the audit's ranking), the picture is different: 2021-05-19, 2025-10-10 and 2021-12-04 (13.6% of fills) carry 42.3% of the total; without them +4.24% (t 4.29); without the top five +3.75%. 2021 alone gives 45% (Δ +21.7% on 203 fills); 2022 +1.5%; 2023 −0.7%. The lowest single year left out still leaves +4.02%.
- **Where it comes from** (audit; F1, no F3 version computed). Two-thirds of the gross effect (4.4 of 6.6 points) comes after the sell goes live. The target was hit by 30.0% of fills and 13.8% of twins. Fills that slid into the level (previous minute's close under 1% above L; half the fills) earned +2.85% (CI +0.06% to +5.64%); fills whose previous close was 3% or more above L earned +13.4%. Single-minute spikes (26 fills) averaged +18.6%. The biggest single gains are one-minute wicks (WLD 2025-10-10; QTUM, VET and ZIL 2021-05-19: Δ +74% to +82%); they add 0.20 points to H1's mean, and the alert buyer an hour later paid 54-63% more than L in those.
- **Robustness the audit checked** (F1; the audit did not compute F3 versions): without likely bad prints +5.94%; without single-minute spikes +6.13%; without fills the index route never filled +5.76%; capacity terciles +6.28 / +6.57 / +6.18%; without any one coin, lowest +6.18%; leave-one-block-out t never below 3.52; episode clusters t 3.88, quarter-blocks t 3.36, two-way coin × month t 3.83; without the four named event days +5.36% (t 4.06); winner's-curse adjusted 6.0-6.2%.
- **Inference cross-checks** (`desc/sensitivity.csv`): episode clusters +6.34% (+2.82 to +9.87; G 96, G* 14.4; F3 +6.45%, +2.42 to +10.49); week clusters (+2.78 to +9.91; F3 +2.37 to +10.53); two-way coin × month (+3.02 to +9.66; F3 +2.72 to +10.18).

### 2c. H4, levels: INCONCLUSIVE

Per method (`primary/h4_methods.csv`; Bonferroni over four methods; F1; F3 was computed for the best method only, +0.02%):

| method | n (coin-weeks) | b per fill | 95% CI | G / G* | Romano-Wolf p | 98.33% bound vs +1% | MDE (Bonferroni) |
|---|---|---|---|---|---|---|---|
| M4 below the 90-day low | 1,687 (434) | −0.06% | −0.79% to +0.67% | 40 / 11.5 | 0.82 | +0.72% | 0.99% |
| M5b round numbers | 1,827 (445) | −0.05% | −0.93% to +0.83% | 38 / 11.5 | 0.82 | +0.90% | 1.20% |
| M6 volume node | 1,355 (403) | −0.35% | −1.12% to +0.42% | 51 / 13.9 | 0.90 | +0.47% | 1.05% |
| **M7 liquidation band** (best) | 1,487 (398) | +0.23% | −0.62% to +1.09% | 33 / 10.4 | 0.56 | +1.16% | 1.17% |

- **Gates.** The best method's b was not above zero in the first half; it was in the second half, without the worst month-block and on F3 (+0.02%).
- **Close to NO EDGE.** Only M7's bound (+1.16%) is above E = 1%; the other three (+0.72%, +0.90%, +0.47%) are below it. The audit notes that M7 alone keeps H4 from NO EDGE, and that on a per-method reading of §10.2 all four bounds would be below 1%: a reading question, not a defect. As run, H4 is INCONCLUSIVE.
- **Single events.** The three largest episodes by fills (2022-11-08..14, 2025-10-09..10, 2023-06-05..10) hold 21.0% of the stacked fills; without them +0.33%. Without 2025-10-10 +0.22%; 2021-05-19 is before M7's data (unchanged, +0.23%); without the top month-block +0.12% (corrected; section 5).
- **K3's power** for H4 (synthetic nulls): NO EDGE was reachable in only 14% (base), 0% (hetero) and 0% (high dispersion) of null replications, so INCONCLUSIVE was the likely outcome even with no effect.

## 3. Descriptive and exploratory results

Everything in this section is **descriptive** (pre-registered estimands with intervals but no verdict) or **exploratory** (splits with BH-adjusted p-values within each table). None of it decides anything. Sources: `results_stinkbid/desc/desc.txt` and its CSVs; `results_stinkbid/explore/explore.txt` and its CSVs.

### 3a. D12: what happens after a fill (descriptive; reported before H1's table)

Share of fills and of their twins trading at or above the flip target R1/2 within each horizon, and at or above the placement price P0 (`desc/d12.csv`):

| | n | R1/2 in 15 min | 1 h | 4 h | 24 h | 72 h | 7 d | 30 d | P0 in 72 h | P0 in 30 d | first went 10% below L |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 fills | 1,544 | 3.8% | 6.2% | 9.5% | 22.9% | 32.9% | 43.1% | 69.6% | 4.9% | 29.3% | 59.6% |
| F1 twins | 1,544 | 0.0% | 0.1% | 0.5% | 4.6% | 13.6% | 25.9% | 52.5% | 3.8% | 31.4% | 53.3% |
| F3 fills (proxy) | 1,364 | 0.7% | 1.1% | 3.2% | 13.6% | 22.9% | 31.2% | 60.9% | 2.4% | 23.4% | 65.3% |
| F3 twins (proxy) | 1,364 | 0.0% | 0.0% | 0.2% | 2.8% | 9.7% | 20.5% | 47.1% | 2.8% | 28.0% | 58.2% |

- Fills rebounded to the target more often than twins at every horizon, but most fills (59.6%; F3 65.3%) first traded a further 10% below L before anything else.
- Fast fills (s24 ≥ 0.75, 826) reached R1/2 within 24 h 36.9% of the time; slow fills (s24 < 0.5, 261) 2.7% (F3: 21.8% of 743 and 1.3% of 224).

### 3b. D-H2 (owning after a fill) and D8 (flip or own)

- **D-H2:** "Descriptive only. Over 90 days, coins bought through stink bids did 3.5% (95% CI −19.9% to +13.0% for the difference) worse than the same coins bought at random times outside the six months around each fill. An edge under about 20-40% could not be detected, and the comparison also reflects whether the crashes fell in bear or bull stretches." [1,513 fills, quarter-block clusters G = 27, G* = 12.9; MDE 24.7%; F3: −5.2% (95% CI −20.9% to +10.5%; 1,339 fills, G = 26, G* = 12.4)]. Against B-POST (twins entering 1-30 days after the fill): +3.5% (95% CI −3.5% to +10.6%; same clusters; no F3 row was computed). The controls' K1c measured what regime timing alone produces in a synthetic world: −6.1% per 90 days (SE 5.1%).
- **D8:** "Flip or own is a choice about whether you want to hold the coin, not about stink-bid skill. The study's evidence on the bid is the same for both." The shared premium (the alert buyer's price 72 h later): +5.5% (95% CI +2.6% to +8.4%; 1,541 fills, G = 58, G* = 14.5); F3 +5.7% (+2.4% to +9.1%; 1,361 fills, G = 54, G* = 13.8). The return from 72 h to 90 days against T-bills: +10.6% (95% CI −7.0% to +28.2%; 1,513 fills, quarter-block G = 27, G* = 12.9); F3 +8.7% (−6.1% to +23.5%; 1,339 fills, G = 26, G* = 12.4).

### 3c. D-H3: fast wicks vs slow slides

"Descriptive only. Fast wicks were 4.3% per fill (95% CI −1.8% to +10.2% for the difference) better than slow slides to the same depth. A difference under about 6-10% per fill could not be detected." [1,054 fills, month-block G = 45, G* = 11.1; episode fixed effects; MDE 8.2%; F3: +2.9% (95% CI −3.9% to +9.6%; 946 fills, G = 44, G* = 10.7)]. The drafted version without episode fixed effects: +6.4% (+1.9% to +10.9%; 1,087 fills, G 56, G* 11.2); the 6-hour and 1-hour speed measures: +3.2% (−3.7% to +9.9%) and +7.3% (−2.4% to +16.8%). F3 was computed for the primary version only.

### 3d. D-H5 and T1: knife-catching

- **D-H5:** "Descriptive only. A year after a fill, 27.3% of fills on large, long-listed coins and 46.5% on other top-100 coins were 50% or more below the fill price; at the same volatility the gap was +12.9 points (95% CI +4.6 to +21.2). Neither LUNA (kept out by listing age) nor FTT (kept out by Binance volume rank) was in the large, long-listed group, so this says nothing about fraud collapses of large coins. In the 12-month row, where LUNA is included, the gap was +8.4 points. The study did not test a real-revenue filter." [4,230 fills; two-way coin × quarter clusters, G_coin = 355, G_quarter = 26, t at 25 df; Binance spot fills only, F3 not computed on U-B (A1.7)]. Sensitivities: over fill-years (Ibragimov-Müller) +11.6 points (+2.8 to +20.4); with sigma30 deciles +12.1; without ETH (the coin whose removal lowers it most) +12.2; delisting haircut 0% / 100%: +12.6 / +12.9. The 12-month row: +8.4 points (+1.4 to +15.4).
- **T1, the tail** (U-Q1, 1,329 fills with a year observed; F1; F3 not computed, A1.7). 27.3% of fills and 28.4% of twins were 50% or more below their entry a year later (fills minus twins −1.1 points, episode-cluster 95% CI −13.5 to +12.6, G 76). The lowest price within 30 days was a median 0.84 × L (10th percentile 0.56 × L); within a year a median 0.53 × L (10th percentile 0.21 × L). On U-B: 40.4% of fills and 38.0% of twins.

### 3e. D6: the cost of waiting (μ*)

A bid at rung k beats buying now only if you expect the coin to beat cash by less than **μ*_k a year** (μ* = F × θ / W: F the chance of a fill within a year, θ the fill's 72-hour premium over its twins, W the expected wait as a share of the year). Weekly re-placement on U-Q1 (`desc/d6.csv`):

| rung | route | median wait | no fill in a year | θ (72-h premium) | μ* a year [95% CI] |
|---|---|---|---|---|---|
| k = 6 | F1 | 60 days | 0.5% | +2.8% | 13.4% [1.8%, 25.0%] |
| k = 6 | F3 (proxy) | 68 days | 0.9% | +2.8% | 11.9% [1.4%, 22.3%] |
| k = 8 | F1 | 103 days | 4.6% | +6.3% | 17.4% [5.8%, 29.1%] |
| k = 8 | F3 (proxy) | 111 days | 5.9% | +6.6% | 17.0% [4.8%, 29.3%] |
| k = 10 | F1 | 164 days | 18.6% | +11.3% | 18.3% [8.4%, 28.1%] |
| k = 10 | F3 (proxy) | 174 days | 21.9% | +12.1% | 17.9% [7.9%, 27.9%] |

θ is before costs on the F1 rows (C-0) and after the route's costs on F3 (the code's choice in `stinkbid_desc.py`). Beside it, "the sample's drift" (B-MKT, per placement, F1 only): a bid that filled, held a year (T-bills if it never filled), earned 87 points less than buying at market at placement and holding a year (95% CI −225 to +13 points; 71 placement months; F3 not computed, B-MKT is per placement on Binance spot).

### 3f. D7: accounts

**The flip account (D7):** cash for 3 rungs × every U-Q1 coin at $10k each, one position per rung, flips at X-FLIP; reserved cash earns nothing (r_res = 0, the primary). 2020-2026, 83 months (`desc/d7_summary.csv`, `d7_compare.csv`):

| account (r_res = 0) | F1: CAGR / Sharpe / max drawdown | F3 (proxy): CAGR / Sharpe / max drawdown |
|---|---|---|
| **D7 flip account** (0.9% invested on average) | 8.4% / 0.74 / −3.2% (after tax 5.6%) | 7.8% / 0.64 / −2.7% (after tax 5.2%) |
| B-MIX (same coins at 0.9%, rest T-bills) | 3.4% / 0.55 / −0.8% | 3.4% / 0.55 / −0.8% |
| B-TBILL | 2.9% | 2.9% |
| B-ALERT (the same flips entered by alert) | 7.0% / 0.72 / −5.4% | 7.1% / 0.70 / −5.1% |
| B-HOLD (equal-weight hold of U-Q1) | 8.9% / 0.39 / −79.8% | 8.9% / 0.39 / −79.8% |
| B-ML (each coin's sleeve invested while MoneyLine is green) | 29.6% / 1.19 / −7.9% | 29.6% / 1.19 / −7.9% |

D7 minus each benchmark, CAGR points a year, with the 12-month block-bootstrap 95% interval:

| | F1 | F3 (proxy) |
|---|---|---|
| vs **B-MIX** | +5.04 [−0.47, +12.13] | **+4.42 [−0.83, +11.25]** |
| vs B-TBILL | +5.49 [−0.22, +13.12] | +4.87 [−0.58, +12.12] |
| vs B-ALERT | +1.40 [−3.48, +7.44] | +0.72 [−3.63, +6.12] |
| vs B-HOLD | −0.51 [−62.5, +36.2] | −1.13 [−63.6, +36.0] |
| vs B-ML | −21.17 [−54.0, −0.25] | −21.79 [−55.2, −0.40] |

- **The pre-registered account test failed** (F3 vs B-MIX interval not above zero), so the account is reported, as §10.4 requires, as "a low-exposure crypto holding with extra steps", and "You could run it on Robinhood" is not said.
- **If reserved cash earned 3.35%** (whether cash reserved for an open Robinhood crypto order earns sweep interest is not documented), D7 on F3 beat B-MIX by +6.28 points (12-month interval +1.14 to +13.12; F1 +6.83, +1.41 to +14.00). The rule of record uses r_res = 0 (A1.8); this row does not change the answer.
- **D7-OWN** (a monthly budget per coin, rungs a third each, fills held to the end): F1 CAGR 21.3%, Sharpe 0.55, max drawdown −77.7% (85% invested); F3 19.2%, −74.6%. Against B-MIX-OWN: F1 +1.37 points [−32.5, +20.7], F3 −0.99 [−38.2, +17.4] ("a low-exposure crypto holding with extra steps"). Against the same budget bought by alert (B-ALERT-DCA): F1 +0.76 [−0.14, +2.86], F3 +0.45 [−0.17, +1.65]. Against holding (B-HOLD-OWN): F1 −3.97 [−35.6, +8.3], F3 −6.05 [−47.4, +9.0]. **D7-OWN-ML** (fills held until the MoneyLine turns red): F1 13.5%, max drawdown −18.6%; F3 not computed (the engine computes X-ML exits on F1 only).

### 3g. D-ML: the MoneyLine

- Fills by state at placement: 970 red, 574 green (62.8% red; F3 63.8%, 870 of 1,364).
- 98.1% of fills were followed by a red close within 1 day and 98.8% within 7 days (F1; F3 not computed).
- B-ML (waiting for the first green MoneyLine close after the fill and buying then) paid 6.9% more per coin than the fill (95% CI +1.0% to +12.8%; 1,513 fills, G 57, G* 14.3; F3 +6.2%, +0.5% to +11.8%; 1,339 fills, G 52, G* 13.7). By rung: +4.3%, +8.4%, +12.2% (k = 6, 8, 10; F1, F3 by rung not computed).
- X-ML (hold until the first red close after a green one): Δ +8.6% (95% CI −3.8% to +21.0%; 1,515 fills, G 57, G* 14.3; F3 not computed).
- P1-G (bids only while the MoneyLine is green): Δ +7.1% (+0.7% to +13.4%; 574 fills, G 52, G* 3.9); F3 +6.8% (−1.1% to +14.7%; 494 fills, G 45, G* 3.6).

### 3h. Capacity, venue, fill odds and luck

- **D4 capacity** (Binance spot book; context only on Robinhood's market-maker route; no F3 equivalent). Seller-initiated dollars printed below the level during the wick (first trade below it until it trades back above or 60 minutes pass): median $633k / $958k / $948k and 10th percentile $18,823 / $20,872 / $24,282 at k = 6 / 8 / 10, so the cap Q_max (a quarter of the 10th percentile) is $4,706 / $5,218 / $6,071. The share of a $10k order filled by its expiry (the remainder rests): 99.2% / 99.9% / 99.5%; of a $100k order 97.2% / 98.1% / 96.4%. U-C coins (hindsight) have higher capacity: caps $6,514 / $8,164 / $9,280.
- **D3 venue gap** (share of F1 fills that the other rules also fill): F3 (1%) 88.3%, F3 (2%) 80.7%, F3 (3%) 75.7%, F3 (5%) 66.4%, F3d (1%) 80.2%, F4 96.2%, F5 97.5% (deeper-wick sensitivity: not fills this user could get); 1.6% are F3-unverifiable (index minute missing; 20.5% on 2020-03-12). F6 (Coinbase) was not built.
- **D2 fill rates by life** (F1; F3 not computed for this table): a 7-day bid filled 7.3% / 4.0% / 2.6% of the time at k = 6 / 8 / 10; a 90-day bid 46.5% / 38.5% / 31.7%; a 1-day bid 0.58% / 0.27% / 0.15%.
- **Lives** (sensitivity rows, H1 Δ): 1 day +11.2% (F3 +11.8%); 30 days +2.8% (−1.5% to +7.1%; F3 +2.7%); 90 days, Robinhood's good-till-cancelled "set and forget", +4.2% (−1.0% to +9.4%; F3 +3.7%, −2.2% to +9.8%). The weekly re-placement of P1 is not the same as leaving one 90-day order.
- **D5 fill-odds calibration.** The sheet's walk-forward odds predicted 1,103 F3 fills and 1,244 happened (F1: 1,262 predicted, 1,388 happened); both halves' intervals overlap [0.67, 1.5], so the odds count as calibrated (F3 ratios 1.68 [0.83, 2.65] and 0.93 [0.56, 1.34]).
- **D10 chart levels' fill odds** (their own Holm family, for the sheet only): none of M4, M5b, M6, M7 had better fill odds than depth-matched placebos (differences −0.09 to −0.74 points per bid-week, F1; F3 −0.02 to −0.72; Holm p 1.0). D9 round numbers on the exchange route (F4): +0.03 points, p 0.066, Holm 0.33. No chart level or round-number advice is earned.
- **D11 luck** (F1; F3 not computed). The sum of Δ over the 1,541 fills, 97.7 (in units of one fill's stake), against K3's synthetic null whose 95th percentile is 36.2-42.5 (p 0.0002-0.0004 by scenario). Buying at random times with the same exit summed to −23.4 (a level, no percentile).

### 3i. Exploratory splits (BH-adjusted within each table, F1 and F3 separately)

- **Depth gradient** (`explore/depth_gradient.csv`): mean Δ at k = 5 / 6 / 8 / 10 / 12 was +2.5% / +3.5% / +7.5% / +12.8% / +17.7% (F3: +2.2% / +3.4% / +7.5% / +13.4% / +17.4%); slope +2.1% per sigma of depth (95% CI +0.8% to +3.4%; BH q 0.004; F3 +2.2%, q 0.009). Fewer fills and fewer independent months stand behind the deep rungs: 186 fills in 20 months at k = 12 (G* 7.0).
- **Breadth** (`breadth.csv`): market-wide fills Δ +7.3% (1,251 fills; q 0.007; F3 +7.3%, q 0.015); coin-specific fills +2.4% (−1.6% to +6.4%; 290 fills; q 0.14; F3 +2.1%, q 0.27); the difference +4.9 points (q 0.076; F3 +5.3, q 0.13).
- **Weekday vs weekend** (`weekday.csv`): +6.5% vs +5.7% (difference −0.8, q 0.75; F3 −0.1, q 0.95).
- **Flow, from 2021-12** (`flow.csv`): fills with a larger seller burst in the fill minute +2.4 points better (q 0.13; F3 +2.9, q 0.096); a larger open-interest drop in the hour before +2.2 (q 0.16; F3 +2.5, q 0.15).
- **M3 and M8** (`m3_m8.csv`): M3 at a 2% weekly fill probability +14.1% (271 fills; q 0.006; F3 +13.6%, q 0.008); M8 (crash-depth calibrated) +0.7% (q 0.051; F3 +0.6%, q 0.11).
- **The user's coins** (`user_coins.csv`; all hindsight; Δ per fill, F1 then F3). With BH q below 0.10 on F1 (F3 in brackets): LDO +10.8% on 26 fills [+10.1%], LINK +8.0% on 53 [+8.4%], UNI +6.4% on 47 [+6.3%], CRV +7.9% on 35 [+7.9%], AAVE +7.6% on 41 [+8.7%], BNB +3.1% on 57 [+3.1%], SKY +6.3% on 19 [+4.7%], INJ +5.8% on 21 [+6.6%], ASTER +6.3% on 8 [+8.1%] and ENA +7.6% on 12 [+6.8%]. **NEAR: +3.4% (95% CI −2.2% to +9.0%; 37 fills, G 20, G* 11.2; q 0.15); F3 +4.3% (−2.2% to +10.5%; 34 fills; q 0.17).** BTC +1.6% (q 0.19; F3 +1.0%), ETH +3.1% (q 0.11; F3 +3.7%), SOL +5.1% (q 0.17; F3 +2.7%).
- **HYPE on its perpetual's index** (`hype.csv`; "short history, perpetual-index proxy, no verdict"): 216 bids, 5 fills in 3 months (one on 2025-09-25, three on 2025-10-10, one on 2026-11-14); mean Δ +17.3%, +7.8% without 2025-10-10. HYPE's Binance spot row has 1 fill (Δ +11.8%; F3 +12.8%).

## 4. The level sheet

`analysis_2026/stinkbid_sheet.py` (§13); the run of record is `results_stinkbid/sheet/sheet_2026-11-19.txt` (74 Robinhood-tradable coins, with the read-only Robinhood mark prices of 2026-11-19 17:40 UTC passed as `--price`, and `--refresh`; commit 92a6cb1).

- **Per coin:** the reference price and sigma30; MoneyLine now (red adds "a fill here buys against your own trend signal"); whether the coin is large, long-listed (Binance volume) now; a row per rung (limit on Robinhood's tick, depth in % and sigma, wait, Robinhood odds per week (F3) with the Binance upper bound, capacity and Q_max); the basis of the odds ("N fills in E episodes", the coin's own history shrunk to the U-Q1 rung, or U-Q1 pooled odds for a coin with no U-Q1 history); the orders at $1,000 per rung; the flip target for each rung (shown because H1 passed under rule M); and the "best rung" k = 10 (depth gradient BH q 0.004, exploratory). No chart-level rows: H4 did not pass and D10 earned none.
- **On 2026-11-19** (counted from the sheet's text): 72 of 74 coins had a red MoneyLine (MEGA and SENT green); 29 were large, long-listed; 22 are marked halted for New York residents in the 2026-11-18 catalog, HYPE among them; ORCA has no Binance history.
- **Footer** (U-C coins' history, hindsight; F3 first): "expect fills on about 23 days a year; the longest stretch without any fill was 173 days; on the worst day, 99% of the ladder filled" [Binance spot: 27 days, 173 days, 98%; 2025-10-10: 148 of 150 live orders]. Total cash reserved for all 74 coins at $1,000 per rung: $221,999.57. The route note: "on the default route, the coin's mid must fall about 1% below your price before it fills; a chart touch is not a fill."
- **Safeguards.** A fresh price is required (`--price` or a close under 24 hours old); a `--price` more than 2× away from the last close is refused without `--force-price`; the order diff lists cancel / keep / place lines; the first small test order is printed. The Robinhood catalog is required for ticks and sizes; K7 checked 796 reference orders by the sheet's rule with 0 violations.

## 5. Controls and the outcome audit

**Controls** (§10.5; run on the final data before any outcome; `results_stinkbid/controls/summary.txt`; **every control passed**):
- **K1 known answer.** On synthetic 1-minute markets the engine matched an independent oracle: K1a (no jumps) 925 fills, r_f +0.0019 vs +0.0019; K1b (market-wide jumps that do not revert) 1,791 fills, −0.1337 vs −0.1337. Two deliberately wrong engines (filling at the minute's close or low) failed K1b by +33.9 and +34.2 SE, as required. K1b's fill rates were within ±25% of real P1's (k = 6: 6.23% vs 7.33%). K1c (regime timing alone): Δ X-FLIP −0.6%, X-HOLD-90 −6.1% (SE 5.1%). K1d: delisting haircuts at equal rates for fills and twins.
- **K2 positive control.** With half of each jump reverting (30-minute half-life), the engine found H1's Δ +7.7%, t 6.69 under rule M (and at bot latency), matching the oracle.
- **K3 inference.** 5,000 null replications per scenario (base, high dispersion, heterogeneous effects); every test on the nominal rule in the rerun. MDE (nominal formula, base / high / hetero): H1 4.51% / 5.42% / 4.77%; H2R 0.62% / 0.95% / 1.65%; H4 0.89% / 1.59% / 1.89%. NO EDGE reachable under the null: H2R 100% / 98% / 83%; H1 62% / 51% / 52%; H4 14% / 0% / 0%.
- **K4 look-ahead.** 50 synthetic cut minutes × scale / delete / 3-day gap: 2,250 comparisons, 0 failing; real universes (177,703 rows), levels (6,554) and 288 real fill and capacity runs unchanged under cuts.
- **K5 fill audit.** 41,909,531 engine checks, 0 violations; real P1's 1,544 fills re-audited, 0 violations.
- **K6 capacity.** 200 fills: the 1-minute approximation against aggTrades, median ratio 0.99 (life 1.00).
- **K7 ticks and sizes.** 0 of 447,704 levels off tick; 796 reference Robinhood orders, 0 violations (110 rungs split at the maximum size).
- **K8 venue proxy.** Of 1,544 P1 fills, F3 (1%) removes 11.7%, F3 (3%) 24.3%, F3d (1%) 19.8%; F5 also fills 97.5%; 25 are F3-unverifiable.

**The outcome audit** (after the verdicts of record, commit eee2ddf). Seven independent lenses wrote their own code (no imports of the functions checked); each finding was then tested by three verifiers (reproduce, refute, impact); a follow-up verified the rest on the committed record and ran a completeness critic.
- **What it reproduced.** H1, H2R, Holm and all 13 H1/H2R gates, the 7 bot gates, the F3-kept rows and the A2.7 alternatives, to machine precision with the runner's seeds. From raw Binance 1-minute bars, with its own rule-M clock, tick inference and exit code, one lens rebuilt all 33,486 P1 bids' inputs, levels and fill outcomes, and every fill's exit and alert price exactly; another re-checked all 1,364 F3 alert buys and 1,361 F3 exits on the index bars; 1,700 twins were rebuilt from their seeds. H4's regressions, Romano-Wolf bootstrap, bounds and gates reproduced. Levels rebuilt from data cut at Sunday's close matched; U-Q1 rebuilt from the raw panel matched on all 25,100 coin-months; the 11 U-Q1 coins whose trading later ended keep all 157 fills. Nothing was chosen after the results: the committed sources hash to the runs' stamp, and the last code or pre-registration change (989e134) came before the primary stage.
- **Corrections** (reporting only; commit f6c15f5, reruns cff65d7 and 0a87d41; no verdict, test statistic or gate changed):

| what | before | after |
|---|---|---|
| **1. Size cap Q_max (major).** It summed seller dollars over the order's whole 7-day life; the draft (§7.3, §8.3) defines it on the fill's own capacity window. | k = 6 / 8 / 10: $101,907 / $81,988 / $76,820 per order | **$4,706 / $5,218 / $6,071 per order** (17-22 times smaller) |
| 2. H4's printed MDE used one test's critical value, not the four-method Bonferroni of the test as run | 0.94% | 1.17% |
| 3. H4's "without the top month-block" used M7's own month-blocks, not the shared partition (A1.8) | +0.28% | +0.12% |
| 4. §12 / A1.7 reporting | answer numbers without their F3 twins | F3 beside every Binance number (flip return +4.8%, F3 +4.8%; worst day 95%, F3 95%; MoneyLine 62.8% red, F3 63.8%; D-H2 −3.5%, F3 −5.2%; D-H3 +4.3%, F3 +2.9%; D8 +5.5%, F3 +5.7%); "F3 not computed" on the knife and D-H5 rows; G and G* with every recommendation interval; U-C rows labelled hindsight; H4's missing U-C row stated |

## 6. Deviations

Every deviation is logged in `results_stinkbid/stages/deviations.jsonl` and `stages/log.jsonl`. **Nothing here changed a verdict.**
- **A2.4 (before any outcome).** The data stage ran again on the final rebrand registry. Its logged reason said U-Q1 +23 coin-months; it had been written before a second check added BCC→BCHABC, and the committed registry gives +33 (LUNC 17, BCH 10, VET 6), as A2.1 states (a logged note).
- **A2.5 (after the controls, before any outcome).** The runner read the condensed K3 block of `controls/summary.json` instead of the full calibration, so H2R's then simulation-calibrated rule would have been silently dropped. Fixed (only `k3_calibration.json` is read; a disagreeing summary closes the gate). No control result changed; nothing reran.
- **A2.6 (after the fill counts, before any outcome).** A check of every hand-off between stages (five reviewers, a critic, three verifiers per finding) found M7's futures inputs missing for coin-days Addenda 1-2 had added (AAVE, EGLD, LUNC, GRAM): M7 abstained at 162 placements. The inputs were fetched (65 real M7 levels and 260 placebos added; 11 placements stay without data because BTTC and SLP are not in Binance's archive). The run cache and controls gate now follow the data and code. Data, controls and fill counts ran again.
- **A2.7 (after the controls rerun, before any outcome).** H2R's K3 rule changed between the two controls runs. In the first, its heterogeneous-null false-PASS rate at the 1.67% level was 2.08% with an upper end of 2.51%, 0.01 point over the 2.50% limit, so it took the simulation-calibrated rule; in the rerun 1.36% (up to 1.72%), so the nominal rule. The two runs are two Monte Carlo draws of the same null. The rerun decides (fixed before any outcome); H2R is also shown under both other rules (section 2a), and all verdicts are the same.
- **Out-of-memory stops.** The Linux out-of-memory killer stopped three stages. Fill counts (08:13 UTC, before any outcome): one of four engine workers was lost during P1 on U-C; resumed with three workers. **Primary** (14:34 UTC, exit 137, 4.2 GB main process): killed while computing P1 on U-C, before any test statistic; restarted with two workers, not a rerun. **Desc** (16:44 UTC, exit 137, 6.7 GB while collecting H4-all's outcomes): restarted with one worker, not a rerun. No result depends on the number of workers.
- **Post-results corrections** (17:28 UTC, logged as a rerun of primary, report, desc and explore): the four audit corrections of section 5 (code commit f6c15f5).
- **Not built:** F6 (Coinbase) and U-Q2 (DefiLlama revenue); their rows are empty.

## 7. Caveats

- **Binance spot is not Robinhood.** The primary fill rule is Binance spot. Robinhood's default route fills only when its ask, about 1% above the mid, reaches your bid; F3 imitates that with Binance's index, which removes 11.7% of fills. No Robinhood crypto history exists here, so every Robinhood-route number is a proxy, and Robinhood's behaviour in a crash (spreads, outages, halts) is unknown. Five known Robinhood outage windows were blocked for F3 fills and exits.
- **Concentration.** By contribution, three episodes carry 42.3% of H1's total; without the top five, Δ is +3.75%; 2021 alone gives 45%. An edge that lives in the two or three largest crashes cannot be tested at any size (§10.3).
- **Regime.** Twins are drawn more than six months from each fill, so the comparison also reflects whether crashes fell in bear or bull stretches (K1c: −6.1% per 90 days from regime timing alone, SE 5.1%, one synthetic world). It matters more for D-H2 than for the 72-hour flip (K1c: −0.6% for the flip).
- **Survivorship was handled.** U-B includes dead coins; delistings take a 30% haircut (0% and 100% as sensitivities; H1's mean r_f unchanged at +4.82%, F3 +4.84%); the 11 U-Q1 coins whose trading later ended keep all 157 fills. U-A and U-C are hindsight lists.
- **K3's synthetic panels were less dispersed than H2R's real data.** H2R's real SE is 1.8-4.7 times K3's null SEs, so its realized MDE (3.24%) is above E (2%). H1 and H4 match their K3 scale.
- **Pooled twins** (audit; F1). 149 of 1,541 fills (9.7%) use twins pooled from all U-Q1 coins (fewer than 182 eligible days of their own); without them H1 is +6.51%.
- **Rule M at the 07:00 New York boundary** (audit; F1) gives 49 fills a go-live delay under 60 minutes; they average −1.24%. The engine also lets a resting target fill inside the go-live minute (twins get the same rule); under the strict reading, 2 exits change and H1 moves by −0.04 points.
- **E's input f.** P1 realized 2.41 fills per rung-year, not 2.26; at the realized rate E would be 3.63%. E is fixed and affects only NO EDGE.
- **The leave-out drift row** (+4.35%, 95% CI +0.74% to +7.97%; F1, F3 not computed) subtracts a gross drift from a net return (the literal formula), so it is not cost-matched; cost-matched it is about +6.2% (audit).
- **Bad prints are real trades and were kept.** Dropping fills with under $1k of seller dollars below L in the fill minute, or whose index stayed above L (462 fills), gives H1 +5.55% and H2R +1.59% (F1; the rule concerns Binance spot prints, so no F3 row).
- **Cash.** Whether cash reserved for an open Robinhood crypto order earns sweep interest is not documented; the account test assumes it does not.
- **HYPE** has 5 fills on a proxy price; nothing here is a verdict on it.

## 8. Files and how to rerun

**Sources and files.**
- **Pre-registration:** `analysis_2026/STINKBID_PREREG.md` (frozen 2026-11-18, commit 72ac2a4), with Addenda 1 and 2 (A2.1-A2.7).
- **Research notes:** `analysis_2026/research_notes/Stink bids/` (`mechanics.md`, Robinhood order mechanics and venues; `evidence.md`; `data_inventory.md`; `design_draft.md`; the three critiques; `build_spec.md`).
- **Code:** `analysis_2026/stinkbid_run.py` (the runner), `stinkbid_data.py`, `stinkbid_levels.py`, `stinkbid_engine.py`, `stinkbid_stats.py`, `stinkbid_controls.py`, `stinkbid_desc.py`, `stinkbid_sheet.py`; `fetch_stinkbid_data.py`; reference files in `analysis_2026/stinkbid_ref/`.
- **Results:** `analysis_2026/results_stinkbid/`: `verdicts.txt` (the answer), `verdicts.csv`, `answer.json`; `primary/`; `desc/`; `explore/`; `controls/`; `fcount/`; `sheet/`; `stages/` (markers, `log.jsonl`, `deviations.jsonl`). Raw data and the engine's run cache are in `data/stinkbid/` (gitignored).
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
The data stage needs several GB of disk for the 1-minute index history (about 6.8 GB under A1.6's rule). Use fewer workers (`--jobs 2` or 1) on a machine with less memory: the out-of-memory stops in section 6 came from 3-4 engine workers of about 3 GB each beside a main process of 4.2-6.7 GB. The sheet alone runs without the run cache's outcomes: `.venv/Scripts/python.exe -m analysis_2026.stinkbid_sheet --coins NEAR --price NEAR=3.3039`.
