# Stink bids: relevance critique of the design draft

An adversarial review of [`design_draft.md`](design_draft.md), written 2026-11-18 for the orchestrator, who folds the
accepted changes into `analysis_2026/STINKBID_PREREG.md` before it is frozen.

**Lens: relevance to the user's decision.**
- Does the design answer what the user asked: which levels, how often bids fill, what happens after, and whether the
  idle cash and missed upside are worth it compared with just buying?
- Is the level sheet practical for someone placing Robinhood orders by hand?
- Are the universes realistic, without hindsight picking, and do they match "solid coins I wouldn't mind owning"?
- Which simpler alternatives must be compared: buying now, DCA, the user's MoneyLine indicator?
- What must the user be told about tail risk: knife-catching and fraud collapses?

**What was read** (in full unless stated):
- the draft;
- the three research notes: [`mechanics.md`](mechanics.md), [`evidence.md`](evidence.md),
  [`data_inventory.md`](data_inventory.md);
- the brief, and the sibling [`critique_statistics.md`](critique_statistics.md) (to avoid duplicating it);
- from [`critique_fidelity.md`](critique_fidelity.md), which appeared while this note was being written, only V1
  (K1b), V3 (exit latency) and its section 2.5, so that R3 and R7 defer to it;
- HANDOFF.md §0-2 and §5.1 (the MoneyLine indicator and its crypto results) and `analysis_2026/moneyline_ref.py`.

**Tags:**
- **[C]** computed here. On real data: counts, fill frequencies and fill timestamps only. Otherwise synthetic.
- **[R]** a repo file.
- **[A] / [S]** primary or secondary web source, as tagged in the sibling notes (not re-fetched here).
- **[M]** a Robinhood connector tool name visible in this session (not called).
- **[U]** unverified, inferred or a judgment call.
- **[D]** a design choice.

**Ground rules followed:**
- No post-fill price, return, P&L or strategy outcome was computed on real data. The real-data checks use the
  draft's own fill calendar (placement price, level, σ30, fill hour and pre-fill speed; nothing after a fill), the
  daily bars up to each placement close (for the MoneyLine state), the monthly volume ranks and one archive listing of
  first-trading months.
- Every outcome below is synthetic.
- No Robinhood tool was called. Nothing was committed. Only this file was written in the repo; the scripts are in the
  session scratchpad (section 6).
- The draft is not edited. Each proposal gives replacement text for the pre-registration.

---

## 0. Bottom line

The draft is a careful test of one question: do deep-wick fills beat random entries into the same coin? The user's
decision is a different one: should he park cash in resting bids on coins he wants to own, rather than buy now, DCA,
follow his MoneyLine signal, or simply buy by hand after a crash? Seven changes are needed for the study to answer
that decision.

1. **The "own it" question has a testable part that the draft leaves out (R1).** The user wants to own the coins,
   but the draft's only own-it test (H2, against random-time buys) has an MDE of 21-40% and will say "can't tell".
   - The user's realistic alternative to a resting bid is a price alert at the same level, followed by a manual buy.
   - That comparison is paired on the same coin and crash. Its MDE is 1.2% (synthetic, on the real fill calendar),
     against 26-27% for H2.
2. **"Worth it versus just buying" is not answered (R2).** A bid's discount is not a gain.
   - In a synthetic martingale, bids 12-19% below the price did as well as buying now, within noise (+0.2 ± 0.3 and
     −0.3 ± 0.5 points). With crash gaps that don't revert they did worse; only a reverting overshoot made them win.
   - The real cost is the coin's own expected return while the cash waits. A k = 8 rung waits a median of 16 weeks
     and spends 37% of a year in cash; 22% of k = 10 rungs see no fill within a year [C].
   - The draft explicitly leaves this term out. It should report a break-even expected return per rung, and compare
     accounts with a benchmark at the same average exposure.
3. **The flip exit is one the user cannot execute (R3, endorsing the fidelity review's V3).** The modelled limit
   sell goes live the minute after the fill. The user places orders by hand: 25% of fills came between midnight and
   8 am Eastern and 27% on weekends [C].
4. **The "established" universe is not the user's "solid / real revenue" filter, and it excludes LUNA and FTT by
   construction (R4).**
   - LUNA classic was Binance's #4 coin by volume in May 2022. It was kept out only by the 24-month listing rule.
   - The draft's claim that its age fix brings LUNA classic in is wrong: its first Binance listing, in every quote
     asset, is 2020-08 [C].
   - FTT was kept out by its Binance volume rank.
   - H5 therefore flatters the filter, and tests a size-and-age rule, not revenue.
5. **MoneyLine is missing (R5).** 63% of P1 fills came when the user's own MoneyLine (replicated version) was
   already red at placement [C]. Without a rule for this conflict, the sheet's "hold per your own plan" means "sell
   on the red flip".
6. **The tail must be told in absolute terms (R6).** On 2025-10-10, 88 of 93 live bids (95%) in the main universe
   filled the same day [C]. H5 reports only a difference between two groups of fills.
7. **K1b's known answer is wrong (R7, confirming the fidelity review's V1).** With non-reverting crash jumps the
   correct answer is a loss, not zero. It also sets the user's baseline: the neutral outcome of a stink bid in a
   crash-prone market is negative.

The should and could items (R8-R15) cover:
- a weekly routine a person can keep, priced from fresh data;
- the sheet's units (waiting time, ladder-level odds);
- HYPE, the user's lead example, which the study cannot speak to;
- a pre-registered recommendation for every combination of verdicts;
- a recovery-speed table (the brief's "how fast do they revert");
- an accumulation account the user would actually run;
- the depth choice;
- flip or own as an exposure choice.

---

## 1. What the user asked, and where the draft answers it

| the user's question | the draft's answer | gap | proposals |
|---|---|---|---|
| Which levels? | M2 rungs at 6/8/10σ; chart levels only if they beat placebos (H4) | Depth is the user's main lever, but the trade-off (waiting time against anything gained) is not shown | R9, R14 |
| How often would bids fill? | Fill rates per bid-week; 1,274 fills; 80% on market-wide days | Not in the user's units: fill days a year, droughts, how much of the ladder fills at once | R6, R9 |
| What happens after a fill? | H1 flip (72 h), H2 own (90 days), descriptive holds | The own test cannot decide anything. Recovery speed (brief question 1) is not measured. No absolute tail figures | R1, R6, R12 |
| Worth the idle cash and missed upside, versus just buying? | D6 (descriptive, "mostly drift"); D7 against B-HOLD, B-DCA, B-TBILL; E from T-bill carry | The coin's expected return while waiting is the main cost and is left out. Account benchmarks differ in exposure | R2, R13 |
| Simpler alternatives? | B-MKT, B-DCA, B-HOLD | MoneyLine is absent. "Alert, then buy by hand" is absent | R1, R5 |
| Does a "solid / real revenue" filter avoid knives? | H5: U-Q1 against the other top-100 coins | U-Q1 is not a revenue filter, and it excludes LUNA and FTT by construction | R4, R6 |
| Practical on Robinhood by hand? | Level sheet, weekly manual routine | Zero-latency flip; weekly re-entry of every order; stale reference price; HYPE | R3, R8, R10 |

---

## 2. Evidence for this note

### 2.1 Counts on real data (fill frequencies and timings only) [C]

All counts use the draft's fill calendar (`design_sim/fillcal7.parquet`: weekly bids on Binance hourly spot bars, a
10 bp trade-through, PAX excluded), which reproduces the draft's 1,274 P1 fills exactly.

**a. Who is in U-Q1 ("established").**
- In May 2022 (the LUNA crash) U-Q1 held 25 coins: ADA, ALGO, ATOM, BCH, BNB, BTC, CHZ, DOGE, ENJ, EOS, ETC, ETH, FTM,
  KAVA, LINK, LTC, MATIC, OMG, ONE, THETA, TRX, VET, XLM, XRP, ZEC.
- SOL entered U-Q1 in 2022-08, DOT 2022-08, AVAX 2022-09, NEAR and AAVE 2022-10, UNI 2023-01. All were kept out by
  the 24-month listing rule.
- Memecoins (DOGE, SHIB, PEPE, FLOKI, BONK, WIF, PEOPLE) are 7.2% of U-Q1 bid-weeks and 6.0% of P1 fills (76).
- A point-in-time "top 5 by Binance volume, excluding BTC and ETH" ladder held ADA, BNB, DOGE, FTM, XRP in 2022-05
  and DOGE, PEPE, SOL, SUI, XRP in 2025-10.

**b. LUNA and FTT.**

| coin | Binance volume rank, 2022-05 | 12-month median rank | first Binance listing (any of USDT, BTC, BNB, BUSD) | in U-Q1 at its collapse? | why not |
|---|---|---|---|---|---|
| LUNA (classic) | 4 | 12 | 2020-08 (the ETH pair 2021-12) | no | listed 21 months, not 24 |
| FTT | 65 (54 in 2022-10) | 54 | 2019-12 | no | rank rule (≤ 50) |

- The first-listing months come from one listing of the Binance archive per quote asset (metadata only). They show
  that the draft's §5.1 sentence ("with all quote assets ... LUNA classic should then be in U-Q1 before May 2022") is
  false. SOL's earliest listing is 2020-04 (against BTC, BNB and BUSD), so the fix moves SOL's entry to 2022-04.
- With a 12-month listing rule, LUNA classic enters in 2021-10, SOL and AAVE in 2021-10, AVAX in 2022-01 and NEAR in
  2022-04. That universe holds 125 coins and 1,774 P1-rule fills (853 of them in 2020-22, against 534), including 3
  LUNA classic fills in May 2022. FTT stays out (rank).

**c. How long one rung waits for a fill.** Kaplan-Meier, for a rung started on a random Monday in U-Q1 and re-placed
weekly while the coin stays in the top 100; censored at 52 weeks or when the coin leaves.

| rung | median wait | restricted mean wait (1-year horizon) | share of the year in cash | no fill within a year |
|---|---|---|---|---|
| k = 6 | 8.75 weeks | 11.0 weeks | 21% | 0.3% |
| k = 8 | 15.75 weeks | 19.3 weeks | 37% | 7.1% |
| k = 10 | 24.75 weeks | 27.2 weeks | 52% | 21.8% |

The user-style examples (NEAR, SOL, AAVE, LINK; hindsight) are similar: medians 9.5, 16.5 and 22.75 weeks; no fill
within a year 0.5%, 9.1% and 19.8%.

**d. What a 5-coin ladder looks like** (rungs 6/8/10, weekly).

| ladder | fills (days) | fill days a year | longest stretch without a fill, by year | fills on days when ≥ half the ladder filled | worst days (share of the live ladder filled) |
|---|---|---|---|---|---|
| point in time: top 5 by volume, ex BTC/ETH, 2020-26 | 238 (69) | 7-15 | 77-174 days | 46% | 2025-10-10 93%; 2022-05-11 87%; 2020-03-12 83% |
| NEAR, SOL, AAVE, LINK, 2021-26 (hindsight) | 157 (55) | 8-10 | 105-180 days | 35% | 2025-10-10 92%; 2022-05-11 83%; 2023-06-10 75% |

**e. How much of the ladder fills at once (all of U-Q1).**
- 2025-10-10: 88 of the 93 live rungs filled (95%). 2021-05-19: 71%. 2022-05-11: 68%. 2023-08-17: 67%.
  2023-06-10: 62%.
- 33% of all P1 fills came on days when at least half of the live ladder filled; 54% on days when at least a quarter
  did.
- By year, the single busiest day held 17-57% of that year's fills (57% in 2025: 2025-10-10).

**f. When fills happen** (fill hour in US Eastern time).
- 25% between midnight and 08:00; 6% between 22:00 and midnight.
- 27% on Saturdays or Sundays.
- 23% in weekday office hours (09:00-17:00).

**g. The user's MoneyLine at placement.** The replicated indicator (`moneyline_ref.supertrend`: ATR10 × 2 around
hl2, reset on flip) on each coin's daily Binance bars, read at the placement close d0.

| state at d0 | share of U-Q1 bid-weeks | share of P1 fills | fill rate per bid-week (k = 6 / 8 / 10) | fills on crash days* |
|---|---|---|---|---|
| green | 43% | 37% (473) | 6.6% / 2.8% / 1.8% | 84% |
| red | 57% | 63% (801) | 7.4% / 4.2% / 2.8% | 89% |

\* Days with at least 10 U-B fills at rungs 6-10.

The user's current "Bullmania" version is a different, unreplicated indicator that flips 1.5-2 times a year (HANDOFF
§2) [R]. These shares are for the replicated version only [U for the new one].

**h. Weekly refresh workload** (k = 8, U-Q1, consecutive weeks). The level moves a median 7.4% from one Monday to the
next. Only 15% of weeks move it by less than 2%, 36% by less than 5% and 62% by less than 10%.

**i. HYPE.** Weekly bids on the Binance USD-M perpetual's daily bars (an upper bound: perpetual lows are deeper than
spot, `mechanics.md` §3.2), 72 bid-weeks per rung from 2025-06-30:
- median depth at placement 24%, 31% and 37% for k = 6, 8 and 10;
- fills at k = 8 and 10 only on 2025-10-10; at k = 6 on 2025-10-10 and 2026-11-14;
- 2025-10-10 is 13 days before Robinhood listed HYPE (2025-10-23,
  [The Defiant](https://thedefiant.io/robinhood-adds-hype-for-spot-trading) [S]).

### 2.2 Synthetic checks [C]

**a. Is the discount worth anything, and what does waiting cost?** (`sim_waiting.py`, 20,000 one-year paths per row.)

Setup:
- Hourly log prices: Student-t(4) diffusion at 3.5% daily volatility.
- Market-crash jumps: 8 a year, log size −|N(0.20, 0.08)|. The jumps are compensated, so the arithmetic drift is
  exactly μ.
- One rung: bid at L = P0·e^{−k·4.3%}, re-placed weekly until it fills, then held to day 365. Cash earns 0.
- Benchmark: buy at hour 0 and hold to day 365.

| market | rung (depth below the price) | bid program minus buy-now, points of terminal value | bids filled | time in cash |
|---|---|---|---|---|
| no jumps, 6% daily vol, μ = 0 | k = 3 (12%) | +0.2 ± 0.3 | 100% | 3% |
| no jumps, 6% daily vol, μ = 0 | k = 5 (19%) | −0.3 ± 0.5 | 100% | 9% |
| jumps that do not revert, μ = 0 | k = 6 (23%) | −4.7 ± 0.5 | 97% | 28% |
| jumps that do not revert, μ = 0 | k = 8 (29%) | −1.9 ± 0.6 | 77% | 52% |
| jumps that do not revert, μ = 30%/yr | k = 6 | −15.9 ± 0.7 (buy-now +35.7%, bids +19.8%) | 96% | 29% |
| jumps that do not revert, μ = 30%/yr | k = 8 | −22.5 ± 0.9 (buy-now +34.3%, bids +11.7%) | 76% | 54% |
| jumps with a 10% transient wick, μ = 0 | k = 8 | +2.4 ± 0.6 | 93% | 35% |

Reading:
- **Without jumps, a bid 12-19% below the price is worth exactly what buying now is worth.** The discount is offset by
  the fact that you only get it when the price has fallen. This is the optional-stopping property of a martingale.
- **With crash gaps, the bid loses.** A limit buy fills at L while the jump carries the price past L.
- **With positive drift, waiting is the dominant cost.**
- **Only an overshoot that reverts makes the bid win.** That reversal is exactly what H1 and R1's H2R measure.

**b. How much a paired "alert, then buy by hand" benchmark helps** (`power_react.py`, `power_react_wake.py`). This
reuses the draft's power-study market on the real P1 fill calendar:
- a martingale with market and idiosyncratic Student-t(4) shocks;
- a volatility regime;
- double volatility for 3 days after crash days.

There are two runs (120 and 100 replications); MDE at α/5 one-sided, 80% power, t(G − 1).

| statistic | clusters | MDE per fill |
|---|---|---|
| H2 as drafted: 90-day fill return minus 20 random-time twins | 26 quarters | 25.7-26.9% |
| coin-count advantage over buying the same coin by hand 2 h after the fill | 60 months | 0.8-0.9% |
| ... 8 h after | 60 months | 1.8-2.3% |
| ... 24 h after | 60 months | 3.2-3.7% |
| ... 72 h after | 60 months | 6.3-6.8% |
| ... at a waking-hours delay (1 h if the fill is 07:00-22:59 Eastern, else at 08:00 Eastern; mean 2.2 h) | 60 months | 1.2% |

R1 adopts the fidelity review's 07:00 morning time instead of 08:00, for one clock across the study. That moves the
mean delay by under an hour and does not change the order of magnitude [U: not re-simulated].

The absolute values scale with the post-crash hourly volatility assumed. A wilder first hour after a crash would
widen them, perhaps by half [U]. The ordering would not change.

### 2.3 What could not be checked here

- Any post-fill outcome on real data (by the ground rules). In particular: how often a green MoneyLine turned red at
  the fill day's close, and how fast real fills recovered.
- Whether Robinhood's crypto price alerts trigger on the mid, and how quickly [U].
- Whether Robinhood limits the number of open crypto orders, or rejects limit buys far below the market [U]
  (`mechanics.md` §1.1).
- Whether the Binance archive is reachable from the user's US connection [U].

---

## 3. Proposals

Each proposal gives its severity, the sections it changes and the bias it causes if left, then the problem, the
evidence and the replacement text.

### R1. The testable part of "own it": an alert-and-buy benchmark and a confirmatory test H2R

**must · §0, §1.2 (rows 2 and 4), §11.1, §12.2, §12.3, §12.6, §15.1 · false negative; interpretability**

**Problem.**
- **The user's intent is to own.** His words are "cryptos ... that I wouldn't mind owning". The draft's only
  confirmatory own-it test, H2 (fills held 90 days against random-time twins), has an MDE of 21-40% (§12.5); 26-27% in
  this note's rerun (2.2b). It will be INCONCLUSIVE whatever is true.
- **The user's realistic alternative is not a random-time purchase.** It is to set a price alert at the same level
  and buy by hand when it triggers. The cash then stays in the sweep, and he can read the news before buying. The
  Robinhood connector exposes an alert tool (`create_alert` [M]); whether app alerts cover crypto, and on which
  price, is [U].
- **That comparison is paired on the same coin and crash, so the long path cancels.** Both buyers own the same coin
  after the alert buyer's purchase. The coin-count advantage a_f = P_alert / L − 1 therefore carries unchanged to any
  exit date. Its MDE is 1.2% at a waking-hours delay, against 26-27% for H2 (2.2b).
- **It answers a question the user can act on.** "If I am going to buy after crashes anyway, should my bids rest, or
  should I use alerts?" It also isolates the mechanism `evidence.md` §2.4 describes: overshoot that reverts against
  a fall that keeps going.
- **How it differs from the statistics review's S19.** S19 proposes post-fill twins in (τ_f + 1 d, τ_f + 30 d] for
  variance reduction. R1 uses a waking-hours clock a person can follow (a delay of one to a few hours), as a
  confirmatory test.

**Replacement (§11.1, new benchmark row):**
> **Manual-action rule M** (the clock of the fidelity review's V3, used here and in R3). An action a person takes in
> response to an event at minute t happens at t + 60 minutes if t falls between 07:00 and 22:59 America/New_York,
> and otherwise at the next 07:00 New York time.
>
> **B-ALERT (alert, then buy by hand).** For fill f on coin i at minute τ_f, the alert buyer buys coin i at market
> at the open of the first traded minute at or after the time rule M gives for τ_f (a mean delay of about 2 hours on
> P1's fills [C]). The purchase uses the same route and cost scenario as the fill.
> - Outcome: the coin-count advantage a_f = P_alert,f / L_f − 1, in simple terms. Buy costs are equal on both sides.
>   Because both buyers then hold the same coin, a_f is the same at every later exit date.
> - Sensitivities: fixed delays of 2, 8, 24 and 72 hours.
> - The bid side is charged the reserved-cash carry in D7 only.

**Replacement (§12.3, new test H2R in H2's place in the Holm family; H2 becomes a pre-registered descriptive
estimate):**
> **H2R RESTING.** Claim: a resting stink bid buys more of the coin per dollar than an alert at the same level
> followed by a manual market buy (B-ALERT).
> - Program P1. Unit: fill. Statistic: mean a_f, month clusters, under the family's inference rule (S2 of the
>   statistics review if adopted). Episode clusters are a sensitivity.
> - **E = +2% per fill [D].** The carry a reserved dollar may forgo over P1's median 16-week wait is 1.0-1.3% (at
>   3.35-4.21%; whether reserved cash earns interest is [U]). The rest of E stands for the unpriced value of reading
>   the news before buying.
> - **PASS:** Holm p < 0.05. a > 0 in both halves, without the worst month, without the biggest episode, and under
>   F3. F3 is required because single-venue prints, such as ATOM at $0.001, would otherwise give a_f > 0 by
>   construction.
> - **NO EDGE:** the 99% upper bound is below E. **HARMS:** the bound is below 0.

If the statistics review's S1 is adopted, the family becomes {H1, H2R, H4}.

**Replacement (§12.6, a new row, stated first among the return verdicts):**

| verdict | sentence |
|---|---|
| PASS | "If you are going to buy these coins after crashes anyway, resting bids got you X% more coin per dollar than an alert at the same price followed by buying by hand (95% CI), over N fills in G months." |
| NO EDGE | "Resting bids did not buy meaningfully cheaper than an alert plus a manual buy. Use alerts: your cash stays liquid and earning, and you can check the news before you buy." |
| HARMS | "Resting bids bought into falls that kept going: the alert buyer, a few hours later, paid less." |
| INCONCLUSIVE | "The data can't tell resting bids from alerts plus a manual buy (an edge under about M% wouldn't show). Alerts keep your cash free." |

### R2. "Worth it versus just buying": a break-even expected return, and benchmarks at equal exposure

**must · §0, §10, §11.1 (B-MKT, B-DCA, B-HOLD), §12.3 (H2's E), §13 (D6, D7), §15.1 · false positive; interpretability**

**Problem.**
- **The user's question is answered only in descriptive rows.**
  - D6 is labelled "mostly the sample's drift".
  - D7 compares a flip account that is about 98% cash with 100%-crypto benchmarks (B-HOLD, B-DCA). They differ
    mainly in exposure.
- **The discount is not a gain** (2.2a). Under a martingale, bids 12-19% below the price ended within half a point of
  buying now. With non-reverting crash gaps they lost 2-5 points. "Fills beat random buys" is easily read as
  "stink bids beat buying now". The second claim needs the waiting cost.
- **Waiting is the main cost for someone who wants to own the coin** (2.1c). Rungs spend 21%, 37% and 52% of a year
  in cash at k = 6, 8 and 10. With a 30%/yr drift, the synthetic bid program trailed buying now by 16-23 points over a
  year (2.2a).
- **The draft leaves this term out on purpose.** H2's E is set "before even counting the coin's own expected return
  while waiting (unknown, and not assumed)". The user's belief about that return is why he wants the coin, so it
  must be an input to the answer, not an omission.

**Replacement (§13, D6 rewritten):**
> **D6 Cost of waiting, as a break-even expected return.** For each rung k, three inputs and one result:
> - **W_k:** the Kaplan-Meier restricted mean time to a first fill over 365 days under weekly re-placement, as a
>   share of the year. Counts only; the fill calendar gives 0.21 / 0.37 / 0.52 for k = 6 / 8 / 10 [C].
> - **F_k:** the probability of a fill within 365 days (0.997 / 0.93 / 0.78 [C]).
> - **θ_k:** the per-fill premium. It is the mean of P(τ_f + 72 h)/L − 1 (H2R's statistic at a 72-hour delay),
>   minus the twins' mean 72-hour return.
> - **μ*_k = F_k·θ_k / W_k:** the break-even excess return over cash, a year, with a 95% interval from θ_k's.
>
> This is the first-order condition F·θ = (μ − r)·W. Example: θ = 4% gives μ* ≈ 19%, 10% and 6% a year at
> k = 6, 8 and 10.
>
> Sentence: "Bids at rung k beat buying now only if you expect the coin to beat cash by less than μ*_k a year."
> The in-sample per-placement comparison with B-MKT stays, as a row labelled "the sample's drift".

**Replacement (§11.1, new row; §13 D7):**
> **B-MIX (equal exposure).** The same coins, held continuously at a constant fraction x of the account (equal
> weights, rebalanced monthly), with the rest in T-bills. x is the stink-bid account's time-average invested
> fraction.
> - D7 reports every account against B-MIX first, then B-TBILL, B-DCA (same budget schedule, R13) and B-HOLD.
> - A stink-bid account that does not beat B-MIX is reported as "a low-exposure crypto holding with extra steps".

**Replacement (§12.6, a fixed sentence printed with every return verdict):**
> "A bid's discount is not a gain by itself. If prices are unpredictable, a bid 30% below the price buys the same
> expected value as buying now, minus what the coin earns while you wait; in a crash that gaps through your price, it
> buys less. Only a quick rebound after the wick can pay for the wait."

### R3. The flip exit must be one the user can execute by hand (adopt the fidelity review's V3)

**must · §9 (X-FLIP), §12.3 (H1), §15.1 (flip target), §15.2 step 4 · false positive or false negative (sign
unknown); interpretability**

The fidelity review's [V3](critique_fidelity.md) gives the full rule: a manual clock for the sell and the time stop,
the same clock for twins, and the K2 and power-study consequences. This proposal endorses it from the user's side,
and adds only the sheet wording below.

**Problem.**
- **The modelled exit goes live at once.** X-FLIP's limit sell is live "from the minute after the fill".
- **The user cannot do that.** He places every order by hand (brief; §15.2) and cannot place a sell before he owns
  the coin. Robinhood's crypto order types are market, limit, stop and stop limit (`mechanics.md` §1.1, from
  [Robinhood's support page](https://robinhood.com/us/en/support/articles/crypto-buying-and-selling/) [A]). No
  attached take-profit or OCO order is listed [U].
- **Fills come at inconvenient times** (2.1f): 25% between midnight and 08:00 Eastern, 6% between 22:00 and
  midnight, 27% on weekends. Only 23% come in weekday office hours.
- **The rebound is fast.** The draft's own sources put it at "minutes to hours"
  ([Christensen, Oomen and Renò 2022](https://econpapers.repec.org/RePEc:eee:econom:v:227:y:2022:i:2:p:461-497);
  [Osler 2005](https://www.newyorkfed.org/research/staff_reports/sr150.html)). A zero-latency exit can book rebounds
  the user would sleep through. V3's synthetic wicks show the effect can go either way: a late sell can also beat an
  early one when the price is already above the target.

**Replacement (adopt V3 as written; it uses the same clock as rule M in R1. Add to §12.6 and §15.1):**
> H1's verdict, the sheet's flip target and its post-fill figures use V3's manual clock. If H1 passes only under the
> "bot" latency (ℓ = 1 minute), the sheet prints no flip target and says: "the flip worked only for sell orders placed
> within a minute of the fill, which you cannot do by hand."

### R4. The "established" universe is not the user's filter, and it excludes LUNA and FTT by construction

**must · §5.1, §5.2, §12.3 (H5), §12.6 (H5 row), §1.2 (row 5) · false positive (for the filter); interpretability**

**Problem** (evidence in 2.1a-b).
- **U-Q1 is "large and long-listed on Binance", not "solid".** In May 2022 every one of its 25 coins had launched in
  2019 or earlier, among them EOS, VET, THETA, ONE, ENJ, CHZ, KAVA and OMG. The user's kind of coin (SOL, NEAR, AAVE, AVAX) was kept out by the
  24-month rule until 2022-08/10. A volume-ranked "top 5" includes DOGE and PEPE.
- **LUNA was kept out by its listing age.** LUNA classic was Binance's #4 coin by volume in May 2022, with a 12-month
  median rank of 12. Its first Binance listing (2020-08, in every quote asset) was 21 months old. The draft's §5.1
  claim that the quote-asset fix brings it in is false.
- **FTT was kept out by its Binance volume rank** (median 54 against the ≤ 50 rule). FTT funded buybacks from real
  exchange revenue ([CoinGecko](https://coingecko.com/research/publications/ftt-impacted-ftx-collapse) [S]) and fell
  97.6% ([Fortune](https://fortune.com/crypto/2022/11/18/how-ftx-own-token-ftt-was-the-final-nail-in-its-coffin)
  [S]). Its main market was FTX, not Binance [U].
- **So H5 is stacked in the filter's favour.** It compares an "established" group from which both fraud collapses
  were removed, by rules unrelated to quality, with an "other" group that contains them.
- **And H5 does not test the user's filter.** That filter is real revenue (U-Q2), which is deferred to a later
  session.

**Replacement (§5.1):**
> - **Rename.** U-Q1 is called **"large, long-listed (Binance volume)"** wherever the user reads it. The words "solid"
>   and "quality" are not used for it.
> - **Delete** the sentence about LUNA classic entering U-Q1 before May 2022. LUNA classic's first Binance listing in
>   any quote asset is 2020-08, so it reaches 24 months only after its collapse.
> - **U-Q1-12**, the same rule with 12 months of listing, is pre-registered as a second H5 row and as a U-Q1
>   sensitivity row. It holds 125 coins and 1,774 P1-rule fills, including LUNA classic's May 2022 fills [C].
> - **U-Q1-xm** excludes memecoins by a list fixed now [D]: DOGE, SHIB, PEPE, FLOKI, BONK, WIF, PEOPLE, plus any coin
>   whose own project called it a meme coin at listing.

**Replacement (§12.6, the H5 row; appended to every H5 verdict):**
> "Neither LUNA (kept out by listing age) nor FTT (kept out by Binance volume rank) was in the established group, so
> this result says nothing about fraud collapses of large coins. In the 12-month row, where LUNA is included, the
> difference was Y points. The study did not test a real-revenue filter."
>
> The last clause is dropped only if U-Q2 is built point in time.

### R5. MoneyLine: the user's own system points the other way on fill days

**must · §11.1, §13 (new D-ML), §15.1 (new column), §15.2 step 4, §12.6 · interpretability; false negative**

**Evidence** (2.1g).
- 63% of P1 fills came when the coin's replicated MoneyLine was red at the placement close.
- Per bid-week, red coins filled more often: 4.2% against 2.8% at k = 8, and 2.8% against 1.8% at k = 10.
- 84-89% of fills in either state fell on crash days.

**Problem.**
- **Most fills buy coins the user's own trend system already rates "Down Trend".** On a crash day, a green coin's
  close will often fall through its line too [U: post-fill, not measured].
- **The sheet then gives conflicting advice.** It says "hold per your own plan". For this user that plan is
  MoneyLine (HANDOFF §1), which would typically say sell, near the low.
- **MoneyLine is also the user's existing entry rule.** The repo's crypto verdicts are: ETH trade via ETF, SOL
  probation, BTC/BNB/ZEC no signal (HANDOFF §0 item 3). "Buy on the green flip" is the natural benchmark for a
  stink-bid fill, and the draft never mentions it.

**Replacement (§11.1, new row; §13, new D-ML):**
> **B-ML (MoneyLine re-entry).** For fill f, buy the same coin at the open of the day after the first daily close at
> or after τ_f at which the replicated MoneyLine is green (`moneyline_ref`, ATR10 × 2).
> - Outcome: the coin-count advantage P_ML,f / L_f − 1. If no green close comes within 365 days, the row records "no
>   re-entry".
>
> **D-ML** (exploratory, BH within the table) reports:
> - B-ML by rung and by MoneyLine state at placement;
> - the fill split by state;
> - the share of fills followed by a red close within 1 and 7 days.
>
> Two more rows:
> - **P1-G** (sensitivity program): bids are placed only when the coin is green at d0. It keeps 43% of bid-weeks and
>   37% of fills [C].
> - **X-ML** (exit row): hold the fill until the first red close that follows a green close.

**Replacement (§15.1, new column, always shown; §15.2 step 4):**
> - **Column "MoneyLine now":** the coin's replicated MoneyLine state at the last close. When red, it adds: "red: a
>   fill here buys against your own trend signal."
> - **Step 4:** "After a fill, decide which rule governs the position before the fill happens. If you follow MoneyLine
>   exits, D-ML shows how often past fills were followed by a red close within a week. The study combines the two
>   plans only through the X-ML row." Add the note: "the sheet uses the replicated pre-October-2026 MoneyLine; your
>   current version is wider and flips less often."

### R6. Tell the user the tail in absolute terms

**must · §12.6, §14, §15.1 (footer), §13 (new T1) · interpretability**

**Evidence** (2.1d-e).
- On 2025-10-10, 95% of the live U-Q1 bids filled the same day. On 2021-05-19, 71% did; on 2022-05-11, 68%.
- A third of all P1 fills came on days when at least half the live ladder filled.
- A point-in-time 5-coin ladder had 93% of its bids filled on 2025-10-10 and 87% on 2022-05-11.

**Problem.**
- **H5 reports only a difference between groups of fills.** Nothing tells the user how often a fill was a knife in
  absolute terms. Nothing compares fills with random buys of the same coins, which is the knife-catching question
  itself.
- **The verdict sentences never say what the worst day looks like.** The literature the notes cite is blunt here:
  - wick lows have been revisited ([Delphi](https://members.delphidigital.io/feed/price-action-apathy-continues-as-expected)
    [S, paywalled]);
  - liquidation spikes were followed by weak 30-day BTC returns
    ([K33 via The Block](https://www.theblock.co/post/372115/whats-next-after-cryptos-fourth-largest-long-liquidation-event-of-2025)
    [S]);
  - the first leg of LUNA ([NBER w31160](https://www.nber.org/papers/w31160) [A]) and of OM
    ([Cointelegraph](https://cointelegraph.com/news/mantra-price-collapses-by-over-90) [S]) looked like a wick.

**Replacement (§13, new T1, descriptive, fixed now; computed after the freeze):**
> **T1 Tail table.** For P1 fills on U-Q1, U-Q1-12 and U-B, and for their twins:
> 1. the share at or below 0.5·L at 365 days, with delistings at the haircut;
> 2. the median and 10th percentile of the lowest price within 30, 90 and 365 days, relative to L;
> 3. the share delisted;
> 4. per episode, the share of the ladder's filled dollars that were 50% or more under water at the worst point within
>    365 days;
> 5. the excess knife rate (fills minus twins), with an episode-cluster 95% interval.

**Replacement (§12.6, fixed sentences, always printed):**
> - "Bids fill together. On 2025-10-10, 95% of the live bids in the study's main universe filled the same day; on
>   most big crash days more than two-thirds did. Size the whole ladder as one position you are willing to hold
>   through a further 50-80% fall."
> - "A fill is not a bottom. Of past fills, A% were 50% or more below the fill price a year later; for random-time
>   buys of the same coins the figure is B%. On the worst episode, C% of the dollars filled were at some point down
>   50% or more."
> - "Coin-specific collapses (LUNA, FTT, OM) look like ordinary wicks on the first day. A resting order cannot read
>   the news. Cancel a coin's bids when there is news about the coin itself: a hack, an exploit, a depeg, a
>   delisting or a regulatory action."

### R7. K1b's known answer is a loss, not zero (adopt the fidelity review's V1)

**must · §11.2 (K1b), §12.6 · false positive (a wrong engine passes); a correct engine fails**

The fidelity review's [V1](critique_fidelity.md) gives the full fix: an oracle known answer and two engine variants
that must fail. This proposal adds an independent synthetic confirmation and the user-facing consequence.

**Problem.**
- **The drafted rule.** K1b (martingale with market-wide jumps that do not revert) passes only if P1's mean Δ and
  mean r_f are both within 2 SE of 0 before costs.
- **A limit buy filled during a non-reverting jump loses on average.** It fills at L while the jump carries the price
  past L. In 2.2a the bid lost 4.7 ± 0.5 and 1.9 ± 0.6 points against buying now with zero drift. Without jumps it
  was neutral.
- **So the drafted rule fails a correct engine**, and passes one that books the fill at the minute's close.
- **This independently confirms V1**, in a different synthetic market (hourly, one-year holds, weekly re-placement).
  The user-facing consequence is R2's fixed sentence: in a crash-prone market the neutral outcome of a stink bid is
  a loss, not zero.

**Replacement:** adopt V1 as written. Its oracle rule is the one this note's synthetic check supports: K1b compares
the engine with the same quantities computed directly from the injected paths, which are negative by construction.

### R8. Make the weekly routine one a person can keep, and price it from fresh data

**should · §7.1, §15.1, §15.2 · interpretability; false positive (small)**

**Problem.**
- **The routine is heavy.** k = 8 levels move a median 7.4% from week to week; only 15% of weeks move less than 2%
  (2.1h). A 5-coin, 3-rung ladder means about 15 cancellations and 15 new orders every Sunday evening: about 1,500
  order actions a year, all by hand.
- **The sheet's default price is a day stale.** The archive publishes a day's file the next day (§15.1). At
  Monday 00:00 UTC (Sunday evening in the US), Sunday's close is not yet there. The sheet's default P0 would
  therefore be Saturday's close, while the backtest uses Sunday's.
- **Two practical unknowns.** Robinhood documents no distance limit for crypto limit buys, and no open-order cap
  (`mechanics.md` §1.1) [U].

**Replacement (§7.1, §15.1, §15.2):**
> 1. **Two routines.** The sheet supports a weekly routine (P1) and a monthly one (30-day life). Each has its own
>    fill odds, and the monthly one is labelled "more slow-decline fills" (§7.4).
> 2. **Lazy refresh** (sensitivity row): each Monday, keep a resting bid unchanged if the new level is within 5% of
>    it, and re-place it otherwise. On the exchange route this keeps the bid's queue position.
> 3. **A fresh reference price.** `--price` is required for every coin, or the sheet fetches a live USD quote from a
>    US-reachable public source. It refuses to print levels from a close more than 24 hours old.
> 4. **An order diff.** The sheet prints, per coin, "cancel X at the old price, place Y at the new price" against last
>    week's sheet.
> 5. **A test order.** Step 1 of §15.2 adds: "Before your first routine, place one small bid at the deepest rung and
>    confirm that Robinhood accepts it and shows it as pending."
> 6. **The orchestrator checks**, read-only, whether Robinhood caps the number of open crypto orders [U].

### R9. Speak the user's units: waiting time and ladder-level odds

**should · §0, §15.1, §13 (D5) · interpretability**

**Problem.**
- **The sheet leads with "fill odds per 7-day bid", a number the user cannot act on.** The user's questions are how
  long his cash will wait, and how often anything fills at all.
- **Over a whole ladder the answer is concrete** (2.1c-d):
  - 7-15 fill days a year for a 5-coin ladder;
  - stretches of 77-180 days with no fill at all;
  - a median wait per rung of 9, 16 and 25 weeks.
- **Binance comes first.** The sheet lists the Binance figure first and Robinhood's second, although the Binance
  figure is only an upper bound.

**Replacement (§15.1, column order and footer; §0, a box "for one user"):**
> Column order:
> 1. limit price (Robinhood tick);
> 2. depth (% and σ);
> 3. **median weeks to a fill** if re-placed weekly, and **the chance of no fill within a year**: Kaplan-Meier on the
>    coin, shrunk to the U-Q1 rung (U-Q1: 8.75, 15.75 and 24.75 weeks; 0.3%, 7% and 22% for k = 6, 8 and 10 [C]);
> 4. Robinhood fill odds per week (F3), with the Binance figure labelled "upper bound", and intervals widened as in
>    the statistics review's S14;
> 5. capacity.
>
> Footer: "Across your whole ladder, expect fills on about N days a year. The longest stretch without any fill was D
> days. On the worst day, S% of the ladder filled."
>
> §0 box: the 5-coin figures of 2.1d.

### R10. HYPE: say plainly that the study cannot speak to it

**should · §5.2, §15.1, §12.6 · interpretability**

**Problem.**
- **HYPE is the user's lead example**, and the study has almost no data on it (2.1i). Its only deep-wick day in the
  Binance record is 2025-10-10, and that came before Robinhood listed it.
- **Its main market is out of reach.** HYPE trades mostly on Hyperliquid, which treats US persons as restricted
  ([Datawallet](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa) [S]). Binance volume rank
  cannot place it.
- **It is a venue token, closer to FTT and BNB than to an L1.** Its value rests on one venue's volume and solvency:
  - about 97-99% of fees fund buybacks
    ([CoinShares via ETF Trends](https://www.etftrends.com/coinshares-content-hub/inside-hyperliquid-fee-engine-works/)
    [S]);
  - validators delisted and settled JELLY at a chosen price in March 2025
    ([CoinMarketCap](https://coinmarketcap.com/academy/article/hyperliquid-delists-jellyjelly-perpetual-futures-after-dollar12-million-market-manipulation)
    [S]);
  - the HLP vault lost about $4.9M on POPCAT in November 2025
    ([The Defiant](https://thedefiant.io/large-popcat-trades-result-in-usd5-million-loss-for-hyperliquid-vault)
    [S]).

**Replacement (§5.2 and the sheet's HYPE row note):**
> "HYPE: about 17 months of Binance perpetual data and 2 months of Binance spot. Its only deep-wick day (2025-10-10)
> came 13 days before Robinhood listed it. The fill odds shown are the U-Q1 rate at the same depth, not HYPE's own.
> HYPE is a venue token: its value depends on Hyperliquid's volume and solvency, a risk no price history here can
> measure (FTT, the token of FTX, fell 97.6%). Not tradable on Robinhood for New York residents."

### R11. Pre-register the recommendation, not only the verdicts

**should · §12.6 · interpretability**

**Problem.**
- **The user asks for a recommendation.** HANDOFF §1 says to "give a concrete recommendation" to sharp "does this
  add up?" questions.
- **Most return tests will be INCONCLUSIVE** (§0; the statistics review's S1).
- **So the advice would be written after the results are seen.** Fixing the mapping now costs one table.

**Replacement (§12.6, new table, applied in this order):**

| results | what the user is told |
|---|---|
| H2R NO EDGE or HARMS | "Don't leave stink bids resting. If you want to buy after crashes, set price alerts at the sheet's levels and buy by hand after checking the news." |
| H2R INCONCLUSIVE | "Resting bids and alerts can't be told apart. Prefer alerts: your cash stays free." |
| H2R PASS | "Resting bids bought X% more coin than buying by hand a few hours later. Use them only with cash you would otherwise hold in T-bills. Whether waiting beats buying now depends on your expectation: at rung k, waiting pays only below μ*_k a year (D6)." |
| H1 PASS under the manual clock (V3) | As drafted for H1, plus the flip target on the sheet. |
| H1 any other verdict | "Don't flip; any edge would need to be about M% per fill to show." |
| always | R2's discount sentence, R6's three tail sentences, R5's MoneyLine note and the capacity cap. |

### R12. Measure how fast fills recover (the brief's question 1)

**should · §1.2 (row 1), §13 (new D12) · interpretability**

**Problem.**
- **The brief asks "how fast do they revert".** §1.2 maps that question to D1-D3, which are counts. No row measures
  reversion speed.
- **The speed decides two things.** Whether a manual flip (R3) or an alert-and-buy (R1) is even feasible.

**Replacement (§13):**
> **D12 Recovery curve** (descriptive; after the freeze; reported before H1). For P1 fills and their twins:
> - the share whose price has traded at or above R½, and at or above P0, within 15 minutes, 1, 4, 24 and 72 hours,
>   7 days and 30 days;
> - the share whose price first traded a further 10% below L.
>
> Splits: by rung, market-wide against coin-specific, and fast against slow (s24).

### R13. Specify the "own" account the user would actually run: stink-bid DCA against plain DCA

**should · §7.1, §9 (X-OWN), §13 (D7) · interpretability**

**Problem.**
- **Under X-OWN, positions never close.** By §7.1 ("while a rung's position is open, that rung places no new bid"),
  each rung therefore fills at most once in 2020-26.
- **So the accumulation account is a one-shot purchase.** It is bought mostly in 2020-21 and then held. That is not a
  plan anyone would follow, and its comparison with B-DCA mixes timing with the size of the budget.

**Replacement (§13 D7, new account):**
> **D7-OWN.**
> - Each month, $m per coin is added to that coin's bid budget.
> - Each Monday, the three rungs are sized from the available budget: a third each, capped at Q_max.
> - A filled rung re-arms the next Monday from the remaining budget.
> - Fills are held to the end (X-OWN) and, as a second row, by MoneyLine (X-ML).
> - Unspent budget earns T-bills (0% as a sensitivity).
>
> Benchmarks on the same schedule:
> - **B-DCA:** buy $m at the first Monday open of each month;
> - **B-ALERT-DCA:** R1's alert route;
> - **B-ML-DCA:** buy while green, hold cash while red;
> - **B-MIX** (R2).

### R14. Frame the depth choice as the user's trade-off

**could · §6.2, §13 (depth gradient), §15.1 · interpretability**

**Problem.** Depth is the one lever the user controls. The draft treats the dose-response over k = 5..12 as
exploratory, and the sheet shows three rungs with no guidance.

**Replacement (§15.1):**
> The sheet recommends no "best" rung unless the pre-registered depth gradient (k = 5..12) has a BH-adjusted
> q < 0.10. For each rung it shows the trade-off: the median wait, the chance of no fill within a year and, after the
> freeze, θ_k and μ*_k (R2).

### R15. Flip or own: report it as an exposure choice

**could · §1.2 (row 4), §12.2 (D8), §12.6 · interpretability**

**Problem.** Flip − hold-90 (D8) mixes two things: the part of the outcome both plans share (the rebound right after
the fill) and whether the user holds the coin's exposure afterwards. The second part has nothing to do with the bid.

**Replacement (§13 D8 and §12.6):**
> D8 is reported in two parts:
> - the premium both plans share (H2R's a_f at 72 h);
> - the hold-period return after 72 h, against T-bills.
>
> Sentence: "Flip or own is a choice about whether you want to hold the coin, not about stink-bid skill. The study's
> evidence on the bid is the same for both."

---

## 4. Summary of proposals

| # | severity | sections | change | bias if left |
|---|---|---|---|---|
| R1 | must | 0, 1.2, 11.1, 12.2, 12.3, 12.6, 15.1 | B-ALERT benchmark and confirmatory H2R (MDE about 1.2% against 26-27% for H2); H2 becomes descriptive | false negative; interpretability |
| R2 | must | 0, 10, 11.1, 12.3, 13 (D6, D7), 15.1 | break-even expected return μ*_k per rung; B-MIX at equal exposure; the "discount is not a gain" sentence | false positive; interpretability |
| R3 | must | 9, 12.3, 15.1, 15.2 | adopt the fidelity review's V3 (manual exit clock); no flip target on the sheet if H1 passes only at bot latency | false positive or negative (sign unknown); interpretability |
| R4 | must | 1.2, 5.1, 5.2, 12.3, 12.6 | rename U-Q1; delete the LUNA claim; U-Q1-12 and U-Q1-xm rows; an H5 caveat on LUNA and FTT | false positive (filter); interpretability |
| R5 | must | 11.1, 12.6, 13, 15.1, 15.2 | B-ML benchmark, D-ML, P1-G, X-ML; a MoneyLine column and step 4 | interpretability; false negative |
| R6 | must | 12.6, 13, 14, 15.1 | T1 absolute tail table (fills against twins); three fixed tail sentences | interpretability |
| R7 | must | 11.2, 12.6 | adopt the fidelity review's V1: K1b's known answer is the direct computation (negative), not 0 | false positive (a wrong engine passes) |
| R8 | should | 7.1, 15.1, 15.2 | weekly and monthly routines; lazy refresh; required fresh price; order diff; test order | interpretability |
| R9 | should | 0, 13, 15.1 | sheet in waiting weeks and ladder-level odds; Robinhood odds first | interpretability |
| R10 | should | 5.2, 12.6, 15.1 | HYPE note: no verdict, pooled odds, venue-token risk | interpretability |
| R11 | should | 12.6 | pre-registered recommendation table | interpretability |
| R12 | should | 1.2, 13 | D12 recovery curve | interpretability |
| R13 | should | 7.1, 9, 13 | D7-OWN: stink-bid DCA against DCA, alert-DCA, MoneyLine-DCA, B-MIX | interpretability |
| R14 | could | 6.2, 13, 15.1 | no "best rung" without a significant depth gradient; show the trade-off | interpretability |
| R15 | could | 1.2, 12.2, 12.6 | D8 split into the shared premium and the exposure after 72 h | interpretability |

---

## 5. What the draft already gets right (keep)

- **It sets expectations before the results.** "The data cannot tell" is stated as the most likely answer, and the
  sheet is framed as "a tool for placing bids with honest fill odds, not a claim that stink bids beat buying".
- **It avoids the conditioning trap.** B-MKT is compared per placement, not per fill.
- **Its universes are honest about hindsight.** U-A and U-C are labelled hindsight and never decide, and dead coins
  enter at a haircut.
- **It warns the user about the venue.** The market-maker route is modelled (F3), with the warning that "a chart that
  touched your price did not fill you".
- **It plans for simultaneous fills.** Cash is sized for "every rung fills on the same day", and order size is capped
  by past capacity.
- **It promises nothing it has not earned.** Chart levels, flip targets and round-number advice appear on the sheet
  only if they earn it.
- **Its choice of order life is grounded in fill counts.** The weekly life is chosen from the fill mix, and the
  90-day "set and forget" row is labelled a slow-decline buyer.

---

## 6. Reproducing these checks

The scripts are in this session's scratchpad, folder `critique_rel/`. They will not survive the session; section 2
gives each method. Every script runs with `python3 -I` and takes the scratchpad path as its first argument where it
needs it.

| script | what it does | output |
|---|---|---|
| `peek.py` | reproduces P1's 1,274 fills from `design_sim/fillcal7.parquet` | stdout |
| `uq_members.py` | U-Q1 members, their first and last months and fills; membership in key months | stdout |
| `ages.py` | first archive month per quote asset (one S3 listing per base and quote; metadata only) | stdout |
| `universe_alt.py` | LUNA, FTT, SOL, NEAR, AAVE and AVAX ranks and membership; the 12-month universe's counts | stdout |
| `user_counts.py` | fill time of day, same-day ladder share, per-year counts, MoneyLine state at placement | `user_counts.json` |
| `user_counts2.py` | Kaplan-Meier waits, 5-coin ladders, memecoin share, weekly level moves | `user_counts2.json` |
| `hype_counts.py` | HYPE weekly bids on the perpetual's daily bars | stdout |
| `sim_waiting.py`, `sim_waiting_nojump.py` | synthetic: discount against waiting, with and without jumps | `sim_waiting*.json` |
| `power_react.py` (seed 31, 120 replications), `power_react_wake.py` (seed 47, 100 replications) | synthetic power of the alert-and-buy statistics against H2 | `power_react_31.json`, `power_react_wake_47.json` |

Run time on 4 CPUs: under a minute for each count script, about 2 minutes for `sim_waiting.py` and about a minute
for each power run.

---

## Sources

**Repo [R]:**
- [`design_draft.md`](design_draft.md), [`mechanics.md`](mechanics.md) (§1.1-1.4, §3.2), [`evidence.md`](evidence.md)
  (§2.4, §4.3-4.5), [`data_inventory.md`](data_inventory.md) (§2.4, §6.4), [`critique_statistics.md`](critique_statistics.md)
  (S1, S2, S14, S19), [`critique_fidelity.md`](critique_fidelity.md) (V1, V3, §2.5)
- `HANDOFF.md` §0 (items 1 and 3), §1, §2 (the indicator and its October 2026 update), §5.1
- `analysis_2026/moneyline_ref.py` (`supertrend`, the replicated MoneyLine)
- `analysis_2026/fetch_scalping_data.py` (`s3_ls`, the archive listing)

**Data:**
- Binance public data archive, through the path-style S3 URL (`fetch_scalping_data.S3`);
  [binance-public-data](https://github.com/binance/binance-public-data/) [A]

**Robinhood (via `mechanics.md`) [A]:**
- [Buying and selling crypto](https://robinhood.com/us/en/support/articles/crypto-buying-and-selling/)
- [Why hasn't my crypto order filled?](https://robinhood.com/us/en/support/articles/why-hasnt-my-cryptocurrency-order-filled)
- [Crypto order routing](https://robinhood.com/us/en/support/articles/crypto-order-routing/)

**Literature (abstracts, via the sibling notes):**
- [Copeland and Galai 1983](https://cris.huji.ac.il/en/publications/information-effects-on-the-bidask-spread/) [A]
- [Handa and Schwartz 1996](https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1835-61.html) [A]
- [Christensen, Oomen and Renò 2022](https://econpapers.repec.org/RePEc:eee:econom:v:227:y:2022:i:2:p:461-497) [A]
- [Osler 2005 (FRBNY SR 150)](https://www.newyorkfed.org/research/staff_reports/sr150.html) [A]
- [Liu, Makarov and Schoar, NBER w31160 (LUNA)](https://www.nber.org/papers/w31160) [A]

**Practitioner and news [S]:**
- [FTT, Fortune](https://fortune.com/crypto/2022/11/18/how-ftx-own-token-ftt-was-the-final-nail-in-its-coffin)
- [FTT buybacks, CoinGecko](https://coingecko.com/research/publications/ftt-impacted-ftx-collapse)
- [OM collapse, Cointelegraph](https://cointelegraph.com/news/mantra-price-collapses-by-over-90)
- [K33 via The Block](https://www.theblock.co/post/372115/whats-next-after-cryptos-fourth-largest-long-liquidation-event-of-2025)
- [Delphi Digital](https://members.delphidigital.io/feed/price-action-apathy-continues-as-expected) (paywalled excerpt)
- [Robinhood lists HYPE, The Defiant](https://thedefiant.io/robinhood-adds-hype-for-spot-trading)
- [Hyperliquid fee engine, CoinShares via ETF Trends](https://www.etftrends.com/coinshares-content-hub/inside-hyperliquid-fee-engine-works/)
- [JELLY delisting, CoinMarketCap](https://coinmarketcap.com/academy/article/hyperliquid-delists-jellyjelly-perpetual-futures-after-dollar12-million-market-manipulation)
- [POPCAT vault loss, The Defiant](https://thedefiant.io/large-popcat-trades-result-in-usd5-million-loss-for-hyperliquid-vault)
- [Hyperliquid and US persons, Datawallet](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa)
