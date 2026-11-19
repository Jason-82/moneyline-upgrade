# Stink bids: statistics critique of the design draft

An adversarial review of [`design_draft.md`](design_draft.md), written 2026-11-18 for the orchestrator, who folds the
accepted changes into `analysis_2026/STINKBID_PREREG.md` before it is frozen.

**Lens: statistics.**
- power when events are rare and clustered;
- the unit of analysis and the clustering;
- multiplicity across methods, depths, exits and coins (one Holm family of a few decisive tests, everything else
  descriptive);
- drift and survivorship confounds;
- benchmark fairness (random entries, buying at placement);
- how thresholds and E values were chosen;
- MDEs and verdict wording.

**What was read in full:**
- the draft;
- the three sibling notes: [`evidence.md`](evidence.md), [`mechanics.md`](mechanics.md),
  [`data_inventory.md`](data_inventory.md);
- the draft's scratch scripts (`design_sim/fillcal7.py`, `fillsum7.py`, `power.py`) and their outputs.

**Tags:**
- **[C]** computed here: either counts on the real fill calendar (nothing after any fill) or synthetic outcomes;
- **[R]** a repo file;
- **[A] / [S]** primary or secondary web source (abstract or catalogue record read through search);
- **[U]** unverified, inferred or a judgment call.

**Ground rules followed:**
- No post-fill return, P&L or strategy outcome was computed on real data. Every outcome below is synthetic.
- Real data entered only as the draft's own fill calendar and as counts. The calendar's fields are coin, rung, fill
  hour, placement price, σ30 at placement, the U-Q1 flag and the pre-fill speed s24.
- No Robinhood tool was called. Nothing was committed.
- Only this file was written in the repo. The scratch scripts are in this session's scratchpad (section 6).
- The draft is not edited. Each proposal gives the replacement text for the pre-registration.

---

## 0. Bottom line

The draft diagnoses its central problem correctly: "the independent sample is a few dozen crash episodes, not 1,274
fills". Its inference does not yet act on that diagnosis. Seven changes are needed before the pre-registration is
frozen. Each was checked by simulation on the real fill calendar.

1. **Two decisive tests, not five (S1).** H2, H3 and H5 cannot reach PASS or NO EDGE at any plausible effect. In the
   Holm family their only effect is to take α from H1 and H4.
   - Keep H1 FLIP and H4 LEVELS in Holm. Make H2, H3 and H5 pre-registered descriptive estimates.
   - At a true 4% edge, H1's chance of passing rises from 56% to 68-69%.
2. **One p-value, chosen to hold its level (S2).** The draft names three inference devices and does not say which
   one enters Holm.
   - Its bootstrap p-value formula falsely passes 2.0-2.6% of the time at Holm's 1% step. CR1 at G − 1 df falsely
     passes up to 1.9%.
   - Taking the larger of a wild cluster restricted bootstrap p and a t-test on the effective number of clusters
     (G* ≈ 12) holds the level, within Monte Carlo error, in every scenario tried.
3. **H1's E is mis-derived (S3).** The +2% was derived as profit per fill but is applied to the fill-minus-twin
   difference, which already contains the twins' 1.88% round trip.
   - Paying for the reserved cash needs Δ ≈ 3.75% per fill.
   - As drafted, when fills are no better than random, NO EDGE is reached only 10-17% of the time. With E = 3.75%,
     39-57%.
4. **H4's placebos sit shallower than the real level (S4).** Deeper placebos fill less often, so pooled placebo fills
   sit 0.54σ shallower.
   - If Δ rises with depth, as the evidence note predicts, every chart method beats its placebos by construction.
   - Then the omnibus falsely passes 6-23% of the time at the 1% level, for depth gradients of 0.5-1% per σ.
   - The fix compares levels at the same depth, inside the same wick.
5. **H5's volatility control and clusters (S5).** σ30 terciles leave volatility gaps between the groups. Quarter
   clusters ignore that the 365-day windows overlap.
   - With no quality effect at all, the drafted test falsely passes 5.8-9.8% of the time at the 1% level. Fixed:
     1.0-2.4%.
   - Its honest MDE is 12-14 points against E = 5, so it becomes descriptive.
6. **The luck benchmark D11 is miscalibrated (S6).** Replacing each fill by an independent random-time twin destroys
   the clustering. Under a true null, P1 "beats 95% of luck programs" in 39% of replications.
7. **K3 must check the levels that decide, with enough replications (S7).** 200 replications at the 5% level cannot
   see a doubling of the false-PASS rate at 1%.
   - Its pass rule fails a correctly sized test 42% of the time.
   - It passes a test whose true size is 7% 17% of the time.

The should and could items (S8-S19) cover:
- reporting the effective sample;
- verdict wording;
- twin eligibility and drift;
- method-level claims on the level sheet;
- intervals for overlapping windows;
- drift and delisting controls;
- the sheet's fill-odds intervals (yearly fill counts are 7.7× overdispersed);
- concentration reporting and the re-run of the power study.

---

## 1. How this was checked

### 1.1 Counts on the real fill calendar [C]

- **Source.** The draft's `fillcal7.parquet`: weekly bids at k = 5..12 on Binance hourly spot bars, PAX excluded. It
  holds only fields known at placement or at the fill.
- **P1** = U-Q1 fills at k = 6, 8, 10: 1,274 fills, matching the draft.
- **Episodes.** Fill days merged when at most 3 days apart (the draft's rule): 91 episodes.
- **What was counted:**
  - cluster sizes and effective numbers;
  - episodes that cross month boundaries;
  - fill counts by depth;
  - σ30 by group and tercile in the H5 sample (3,919 U-B fills with a 365-day follow-up, 1,069 of them in U-Q1);
  - which group the collapse coins fall in;
  - per-coin fill support;
  - yearly fill rates.

### 1.2 Synthetic simulations [C]

**H1 null on the real calendar.**
- **Path model.** The draft's own, from `power.py`:
  - hourly martingale prices;
  - a market factor plus idiosyncratic Student-t(4) shocks;
  - a log-AR(1) volatility regime;
  - a volatility multiplier after crash days.
- **Real part.** P1's real fill hours, levels and half-retrace targets. Exit X-FLIP. 20 twins per fill outside
  ±182 days.
- **Scenarios:**
  - base: 1,200 replications (idiosyncratic volatility 3%, multiplier 2× for 3 days);
  - high dispersion: 800 replications (4.5%, 3× for 7 days);
  - heterogeneous-effect null: each episode gets its own mean-zero effect (SD 3%, Student-t(3)). Some crashes
    revert and some continue, but the average edge is zero.
- **What was compared.** All inference methods on the same replications. Power, by adding a constant edge or an edge
  concentrated in the largest episodes.
- **Monte Carlo error.** The SE of a 1% rejection rate is 0.29 points with 1,200 replications and 0.35 with 800.

**H5 null on the real U-B calendar.**
- **Synthetic part.** 365-day outcomes with no quality effect:
  - a daily market path (same volatility model);
  - a coin-level idiosyncratic path shared by every fill of that coin;
  - an 8% yearly collapse hazard, equal for both groups.
- **Knife risk** depends only on volatility, σ = κ·σ30 at placement. In one scenario it also depends on market
  exposure that rises with volatility: β = 0.6·σ/σ_M.
- 500 replications per scenario.

**H4 omnibus.**
- A normal approximation for the maximum of 4 correlated t-statistics (correlation 0.3 and 0.6).
- Each statistic is shifted by the bias of section 2.5, across the draft's proxy SE range.

### 1.3 What could not be checked here

- **Whether Δ actually rises with depth.** That needs post-fill returns. S4's bias is conditional on it. The evidence
  note predicts it (`evidence.md` §7, H-depth).
- **Real-world parameters.** Real knife rates, real post-crash dispersion and real regime drifts are unknown. Every
  scenario parameter is an assumption [U].
- **A small engine tilt.** The synthetic engine's mean Δ under the null was −0.08% (base) and −0.11% (high), about 2
  Monte Carlo SEs below zero.
  - Likely cause: the hourly Brownian-bridge approximation with Student-t shocks [U].
  - Effect: the reported false-PASS rates are about 10-15% lower, in relative terms, than an untilted engine's.
  - No conclusion changes.

---

## 2. Evidence

### 2.1 The effective sample [C]

| P1 cut | clusters | effective number, the draft's 1/Σw² (zero within-cluster correlation) | G* at full within-cluster correlation, (Σn²)²/Σn⁴ |
|---|---|---|---|
| calendar months | 60 | 23.9 | **12.1** |
| event episodes | 91 | 25.3 | 11.4 |
| month-blocks (months linked by one episode merged) | 58 | 23.1 | 12.4 |
| k = 6 / 8 / 10, by month | 60 / 38 / 24 | 33.2 / 17.1 / 11.7 | 19.8 / 10.2 / 7.7 |
| half 2020-22 / half 2023-26, by month | 24 / 36 | 9.9 / 13.9 | **5.1 / 7.0** |

**How to read the two measures.**
- They bracket the truth.
- Fills on one crash day move together, so for a variance estimate the relevant measure is close to G*.
- Carter, Schnepel & Steigerwald (2017) define G* = G/(1 + Γ) from the dispersion of the clusters' contributions. The
  formula in the table is its value when within-cluster correlation is 1.

**Concentration.**
- The top 3 episodes hold 21% of P1's fills; the top 10 hold 56%.
- 39 episodes hold only 1-2 fills each (48 fills in all).

**Month boundaries.**
- 2 episodes span two months (53 fills).
- 175 fills have a 72-hour window that ends in the next month.

### 2.2 Which p-value holds its level [C]

The table shows how often a TRUE null is rejected, i.e. a false PASS. Tests are one-sided, with month clusters
(G = 60). Values are percentages. A correctly sized test shows the column's level.

| p-value | base, 1% | base, 2.5% | base, 5% | high, 1% | high, 2.5% | high, 5% | heterogeneous null, high, 1% |
|---|---|---|---|---|---|---|---|
| CR1, t(G − 1) [draft 12.1] | 1.08 | 3.50 | 6.42 | **1.87** | 3.75 | 7.00 | **1.87** |
| pairs cluster bootstrap, (1 + #{θ*−θ̂ ≥ θ̂})/(B+1) [draft 12.1 formula] | **2.00** | 4.00 | 7.33 | **2.62** | 4.75 | 7.88 | **2.38** |
| pairs cluster bootstrap-t | 1.58 | 2.83 | 5.92 | 1.50 | 3.25 | 6.00 | 1.50 |
| cluster jackknife (CV3), t(G − 1) | 1.00 | 3.17 | 5.67 | 1.75 | 3.25 | 6.25 | 1.63 |
| wild cluster restricted bootstrap-t (WCR), Webb weights | 0.92 | 2.67 | 4.83 | 1.38 | 2.62 | 5.50 | 1.38 |
| CR1, t(G* − 1), G* = 12.1 | 0.75 | 2.33 | 4.92 | 1.12 | 2.75 | 5.87 | 1.25 |
| **max(p_WCR, p_t(G*−1)), proposed in S2** | **0.67** | **2.17** | **4.58** | **1.12** | **2.75** | **5.50** | **0.75** |

- **Episode clusters** behaved like month clusters.
- **Lower tail.** This is how often a NO EDGE bound misses the true value at the 1% level: CR1 1.50%, WCR 1.17%
  (base).
- **In the base heterogeneous-effect null,** CR1 rejects 1.42% at the 1% level and the proposed rule 0.67%.

### 2.3 What the five-test family costs H1 [C]

The table shows the probability that H1 passes its first Holm step. The draft-family columns use the WCR p-value;
"proposed p" is S2's rule. Base scenario; high dispersion in brackets.

| true edge per fill | draft family, α/5 = 1% | two-test family, α/2 = 2.5% | two-test family, proposed p |
|---|---|---|---|
| +3%, constant | 36% (27%) | 49% (39%) | 48% (37%) |
| +4%, constant | 56% (44%) | 69% (57%) | 68% (56%) |
| +5%, constant | 74% (61%) | 83% (74%) | 83% (73%) |
| +6%, constant | 84% (76%) | 92% (85%) | 92% (84%) |
| +4%, all of it in the 10 largest episodes | 46% (35%) | 62% (53%) | 62% (52%) |
| +5%, all of it in the 10 largest episodes | 64% (51%) | 78% (68%) | 77% (66%) |
| +2% to +6%, all of it in the 3 largest episodes | 6-9% (7-10%) | not run (9-14% at α/3) | — |

- **The MDE with a valid p-value.** In the draft family, the 80%-power MDE is about 5.5% (base) to 6.3% (high). That
  is larger than 12.5's 4.6-6.1%, which used the liberal CR1 t(G − 1). The two-test family brings it to about
  4.8-5.6%.
- **The robustness gates barely bind.** The gates are: both halves, best month out, biggest episode out. Once the
  main test passes, they lower the pass rate by at most 2 points.
- **They do not detect an edge confined to three crashes.** Even tested alone at α = 5%, such an edge passes only
  21-40% of the time, whatever its size. That is the honest answer, but it must be said (S9, S16).

### 2.4 Whether H1 can ever reach NO EDGE [C]

The table shows the probability that H1's upper bound falls below E (a NO EDGE verdict). Base scenario; high
dispersion in brackets. Simulated at E = 3.8%.

| true Δ | E = 2% (draft), 99% bound | E = 3.75% (S3), 99% bound | E = 3.75%, 98.3% bound |
|---|---|---|---|
| −1% | 38% (24%) | 80% (63%) | 85% (73%) |
| 0 | 17% (10%) | 57% (39%) | 65% (48%) |
| +1% | 4% (3%) | 34% (23%) | 42% (28%) |

### 2.5 H4: pooled placebo fills sit shallower than the real level [C]

**Fills fall steeply with depth.**
- U-Q1 weekly fills by rung: 692 (k = 6), 526 (6.7), 436 (7.3), 352 (8), 295 (8.7), 263 (9.3), 230 (10).
- A log-linear fit gives 24% fewer fills per extra σ of depth.

**So pooled placebo fills sit shallower than the real level.**
- **The draft's proxy** (real k = 8 against placebos at 6.7, 7.3, 8.7, 9.3): pooled placebo fills average 7.71σ,
  0.29σ shallower.
- **The actual H4 layout** (placebos at ±0.5 and ±1.0 ATR%; median ATR%/σ = 1.80 among U-Q1 fills): pooled placebo
  fills average 0.54σ shallower than the real level.

**What that does to the test.** Suppose there is NO level effect but Δ rises by s per σ of depth. The table shows the
false-PASS rate of the 4-method max-t omnibus. Ranges cover method correlations of 0.3-0.6. The draft's proxy SE is
0.37-0.59%.

| level, s (bias = 0.54·s) | SE 0.4% | SE 0.6% | SE 0.8% |
|---|---|---|---|
| 1% level, s = 0.25%/σ | 2.5-2.7% | 1.9% | 1.6-1.7% |
| 1% level, s = 0.5%/σ | 5.6-6.2% | 3.3-3.5% | 2.5-2.7% |
| 1% level, s = 1.0%/σ | 19.8-23.1% | 8.9-10.1% | 5.6-6.2% |
| 2.5% level, s = 0.5%/σ | 11.1-12.2% | 7.1-7.6% | 5.6-5.9% |
| 2.5% level, s = 1.0%/σ | 31.8-36.4% | 16.6-18.5% | 11.1-12.2% |

### 2.6 H5 under a null with no quality effect [C]

**Why terciles are too coarse.**
- In the H5 sample, the median σ30 at placement differs between the groups inside the terciles:
  - bottom tercile: U-Q1 3.19% against 3.64% for the others;
  - middle tercile: 5.49% against 5.49%;
  - top tercile: 8.74% against 7.55%.
- Knife odds are steep in volatility. A driftless lognormal coin falls 50% within a year 18% of the time at 57% annual
  volatility, and 40% of the time at 96%.

| scenario | specification | mean b (points) | false PASS at 1% | false PASS at 5% |
|---|---|---|---|---|
| vol = σ30 | draft: rung and σ30-tercile dummies, quarter clusters | +1.0 | 5.8% | 14.0% |
| | p0 covariate, quarter clusters | 0.0 | 3.4% | 10.0% |
| | p0, two-way coin × quarter clusters | 0.0 | 2.4% | 6.2% |
| | p0, Ibragimov-Müller over 6 fill-years | +0.2 | 1.0% | 6.6% |
| vol = σ30, β rising with vol | draft | **+2.1** | **9.8%** | **22.0%** |
| | p0, two-way clusters | +0.2 | 1.4% | 7.8% |
| | p0, Ibragimov-Müller | +0.2 | 1.6% | 6.6% |
| vol = 0.75·σ30 | draft | −0.2 | 2.0% | 6.2% |
| | p0, two-way clusters | −0.9 | 1.6% | 4.6% |

- **p0.** p0 = Φ((ln 0.5 + ½σ_a²)/σ_a), with σ_a = σ30·√365. It is the knife probability of a driftless lognormal coin
  with that volatility.
- **Raw difference.** With no volatility control, the groups differ by +4.4 to +10.6 points from volatility alone.
- **Driscoll-Kraay.** HAC with 4 quarterly lags did not fix the size (2.8-5.2% at 1%). With 24 quarters the lag
  terms are too noisy.
- **MDE.** With valid inference the SD of b is 4.1-4.2 points. That gives an 80%-power MDE of about 12-14 points,
  against E = 5.

### 2.7 The luck benchmark (D11) [C]

The table is computed under a true null. A calibrated benchmark says "beats 95% of luck programs" 5% of the time.

| luck programs | share "p ≤ 0.05" | share "p ≥ 0.95" | SD of the real total / SD of the luck totals |
|---|---|---|---|
| each fill replaced by an independent twin (D11 as drafted) | 38.5% (high: 38.8%) | 42% | 7.2 (high: 5.9) |
| each episode shifted as one block to a random time | 11.4% (high: 14.0%) | — | 1.5 (high: 1.6) |

Even block-shifted programs are too narrow, because random times are calmer than crash times.

### 2.8 The level sheet's fill odds [C]

- **Fill rates swing by year.** U-Q1 weekly fill rate at k = 8:
  - 2020: 2.05%;
  - 2021: 3.65%;
  - 2022: 6.45%;
  - 2023: 3.36%;
  - 2024: 2.52%;
  - 2025: 2.81%;
  - 2026: 3.55%.
  - By half: 4.53% (2020-22) and 3.08% (2023-26).
- **Overdispersion.** Yearly counts are overdispersed against a binomial by φ = 7.7 (Pearson χ² 46.5 on 6 df).
  Intervals that treat bid-weeks as independent are therefore about 2.8× too narrow.
- **Per-coin support at k = 8.**
  - 73 coins have fills.
  - The median coin has 4 fills in 4 distinct episodes. 48% of coins have 3 or fewer.
  - Example: NEAR has 5 fills in 5 episodes over 215 bid-weeks. Its Wilson interval is 1.0-5.3%.

---

## 3. Proposals

Each proposal states its severity, the sections it changes and the bias it causes if left, then the problem, the
evidence and the replacement text or rule.

### S1. Two decisive tests in the Holm family; H2, H3 and H5 become descriptive

**must · §0, §1.2, §12.2, §12.3, §12.6, §15.1 · false negative (H1, H4); interpretability**

**Problem.** A decisive test can reach PASS or NO EDGE at a plausible effect, and its verdict changes what the user
does. Three of the five cannot (MDE against E):
- H2: 21-40% per 90 days, against E = 5%;
- H3: 7.5-10.6%, and still 6.2-9.3% with episode fixed effects, against E = 2%;
- H5: 12-14 points with valid inference, against E = 5.

They still take α: Holm's first step falls from α/2 to α/5.

**Evidence.**
- **H1 power** (2.3): at a true 4% edge, H1 passes 56% → 68-69% of the time (base) and 44% → 56-57% (high).
- **H3:** 150 of the 216 slow fills share an episode with fast fills [C]. Episode fixed effects cut the SD of b by 22%
  (base) and 3% (high). That is not enough.
- **H5:** see 2.6.

**Replacement (§12.2):**
> One Holm family of two one-sided tests at 5%: H1 FLIP and H4 LEVELS. Holm runs on both p-values whatever their other
> conditions; the other PASS conditions are gates, not p-values. Each NO EDGE bound is one-sided at 97.5% (Bonferroni
> over the family). H2 OWN, H3 SPEED and H5 QUALITY are pre-registered descriptive estimands. Each is reported with its
> estimate, its 95% interval (inference of 12.1), its MDE and the fixed sentence of 12.6, ahead of every other table in
> its section. They have no PASS or NO EDGE verdict and show no p-value. Nothing on the level sheet depends on them
> except as 15.1 states. The sentence "You could run it on Robinhood" (12.6) is a gatekept test, run only if H1 PASSes.

**Consequential edits.**
- **§0 table:** two tests; the other three marked "descriptive (cannot decide)".
- **§15.1 quality flag:** "the descriptive knife rates of the two groups (D-H5), labelled descriptive" replaces "H5's
  figure if PASS".

**Alternative, if H5 must stay confirmatory** [U: judgment]. A weighted Holm with weights 0.6 (H1), 0.2 (H4) and 0.2
(H5), using S5's specification (Holm 1979; Bretz et al. 2009). H1's first step is then at 3%.

### S2. One p-value per test, one that holds its level

**must · §12.1, §12.3 · false positive**

**Problem.** Section 12.1 names three inference devices and does not say which p enters Holm:
- CR1 with t(G − 1);
- a cluster bootstrap-t for the NO EDGE bounds;
- a non-studentized bootstrap formula.

Two of them are wrong for this sample:
- **CR1 at G − 1 = 59 df** treats 60 months as 60 independent pieces of information, when G* ≈ 12 (2.1).
- **The pairs cluster bootstrap** resamples months. One month holds 8% of the fills, so its distribution is lumpy, and
  the non-studentized formula inherits the outcome's skew.

**Evidence** (2.2):
- The draft's formula falsely passes 2.0-2.6% of the time at the 1% step.
- CR1 t(G − 1) falsely passes 1.1-1.9% at 1% and 2.7% at 1.67%.
- The proposed rule: 0.67-1.12% at 1%, 2.2-3.0% at 2.5% and 4.6-5.5% at 5%, also under heterogeneous effects.
- Literature:
  - CRVE t-tests over-reject when cluster sizes are unbalanced; the wild cluster bootstrap does much better (MacKinnon
    & Webb 2017; Cameron, Gelbach & Miller 2008; MacKinnon, Nielsen & Webb 2023).
  - The effective number of clusters: Carter, Schnepel & Steigerwald (2017).

**Replacement (§12.1, the "Clusters" and "Bootstrap p-values" bullets):**
> Clusters: the calendar month of the fill, merged into month-blocks when an event episode (fill days at most 3 days
> apart) spans two months (58 blocks for P1). For 365-day outcomes, see D-H5. For each test, the p-value that enters Holm
> is p = max(p_WCR, p_G*). p_WCR is the wild cluster restricted bootstrap-t p-value: null imposed, Webb six-point
> weights, B = 9,999, CR1-studentized (MacKinnon & Webb 2017; Webb 2023). p_G* is the CR1 t-test referred to Student t
> with G* − 1 df, where G* = (Σ_g n_g²)²/Σ_g n_g⁴ over the clusters with fills. The NO EDGE bound is the larger of the
> wild bootstrap-t bound (unrestricted, same weights) and θ̂ + t_{0.975, G*−1}·SE. Every interval states G, G* and the
> cluster unit. The pairs cluster bootstrap and the formula (1 + #{b : θ*_b − θ̂ ≥ θ̂})/(B + 1) are not used.

**For H4's max-t:** use the Romano-Wolf step-down (Romano & Wolf 2005). Draw the bootstrap with wild (Webb) multipliers
on the month-block score sums of the stacked regression, recentred, and studentize each t_j by CR1.

### S3. H1's E is 3.75% per fill, not 2%

**must · §10, §12.3 (H1), §12.5, §12.6 · false negative for NO EDGE; interpretability (the drafted NO EDGE sentence is
false)**

**Problem.**
- Section 10 shows that a +2% profit per fill pays the T-bill on the reserved cash: 52 × 0.043 × 2% ≈ 4.5% a year.
- But H1's statistic is Δ = r_f − r̄_twin, and the twins pay the same 0.95% per side. So Δ ≈ r_f + 1.88%, before
  drift.
- Δ = 2% therefore means r_f ≈ +0.12% per fill. That is about 0.27% a year on reserved cash, not 4.2% [C].

**Evidence** (2.4). When fills are no better than random (Δ = 0):
- the drafted design reaches NO EDGE only 10-17% of the time, and otherwise says "the data cannot tell";
- with E = 3.75% it reaches NO EDGE 39-57% of the time at a 99% bound, and 48-65% at 98.3%.

**Replacement (§10 last bullets; §12.3, the H1 E cell):**
> E_H1 = c_rt + (T-bill − r_res)/f.
>
> - c_rt = 1 − (1 − 0.0095)/(1 + 0.0095) = 1.88% is the round trip that the twins also pay, so it sits inside Δ.
> - f = 52 × 4.34% = 2.26 fills per rung-year, P1's pooled weekly fill rate [C].
>
> With the 3-month T-bill at 4.21% and r_res = 0 (primary): E_H1 = 1.88% + 1.87% = **3.75% per fill**. With
> r_res = 3.35%, E_H1 = 2.26% (a sensitivity row). Below E_H1, flipping does not pay for the round trip and the cash the
> bids tie up.

**Related edits:**
- **PASS gate.** Keep "mean r_f > 0".
- **§15.1.** Add: the flip target is shown only if H1 PASSes and the D7 account on the F3 route beats T-bills. This is
  the condition 12.6 already uses for "You could run it".
- **§12.5 "Reading".** Replace with: "NO EDGE needs an estimate below about +0.5% (base) to −0.2% (high dispersion)".
  [C: 97.5% bound, t(11), SE 1.45-1.78%.]

### S4. H4: compare chart levels with placebos at the same depth, inside the same wick

**must · §6.3, §12.3 (H4), §12.5 · false positive**

**Problem.**
- The drafted statistic is b_j = mean Δ(real fills) − mean Δ(placebo fills). It pools four placebos whose fills are
  not balanced in depth: shallower placebos fill more often.
- The comparison therefore mixes a level effect with a depth effect.
- The evidence note predicts that Δ rises with σ-depth (H-depth). If so, every b_j is biased upward by about
  0.54 × the slope.

**Evidence** (2.5):
- at 0.5% per σ and the proxy SE: up to 6× the nominal false-PASS rate;
- at 1% per σ: 20-23%.

**Replacement (§12.3, the H4 statistic):**
> Per method j, stack the fills of the real level and of its four placebos (one level each per coin-week, X-FLIP,
> U-Q1). Fit Δ_f = α_cw + b_j·real_f + c_j·(δ_f − δ_real,cw) + ε_f, with coin-week fixed effects α_cw and month-block
> clusters. δ_f is the level's depth in σ at placement. Fills are nested within a coin-week: a deeper level fills only
> if the shallower ones do. So b_j compares the real level with the placebo depth trend at the real level's own depth,
> in the same wick. Omnibus T = max_j t_j, with the p-value of S2.

**§12.5.** The H4 proxy (adjacent rungs, no depth term) is not this estimator. Re-run H4's power with the new
estimator (S18).

### S5. H5, now descriptive: a continuous volatility control and clusters that respect the 365-day overlap

**must · §12.3 (H5), §4.3, §12.5 · false positive**

**Problem.**
- **The volatility control is too coarse.** σ30-tercile dummies leave volatility gaps inside the terciles (2.6), and
  knife odds are steep in volatility.
- **The clusters assume too much independence.** Quarter clusters treat 24 quarters as independent, but:
  - each 365-day window overlaps the next three quarters' windows;
  - the three rungs, and later weeks, of one coin share one future price path.

**Evidence** (2.6):
- With no quality effect at all, the drafted test falsely passes 5.8-9.8% of the time at the 1% level (14-22% at
  5%).
- With the p0 covariate and two-way clusters: 1.4-2.4% (4.6-7.8% at 5%).
- Methods: two-way clustering (Cameron, Gelbach & Miller 2011); estimating separately by group and t-testing the
  estimates (Ibragimov & Müller 2010).

**Replacement (§12.3, H5, renamed D-H5 and descriptive):**
> knife_f as drafted. Model: knife_f = a + b·notQ_f + rung dummies + γ·p0_f, with p0_f = Φ((ln 0.5 + ½σ_a²)/σ_a) and
> σ_a = σ30_f·√365. Interval: two-way clusters by coin and by calendar quarter, Student t with
> min(G_coin, G_quarter) − 1 df. Sensitivities: an Ibragimov-Müller t-test on the six fill-year estimates; σ30-decile
> dummies in place of p0. Reported side by side: each group's knife rate, the raw difference and b. The verdict
> sentence is the descriptive one of 12.6 (S9).

### S6. D11: no percentile against random-time programs

**must · §11.1 (last bullet), §13 D11 · false positive (a percentile that signals beating luck when nothing is there)**

**Problem.**
- Replacing every fill by an independently drawn twin produces programs whose totals vary far less than a clustered
  program's.
- Shifting whole episodes to random times is still too narrow, because random times are calmer than crashes.

**Evidence:** section 2.7.

**Replacement (§13 D11 and §11.1):**
> D11 (luck): P1's total Δ against the null distribution of that total from K3's synthetic panels on the real fill
> calendar, which keep both the clustering and the crash-time volatility. Random-time programs are reported only as a
> level ("what buying at random times with this exit earned"), with no percentile.

### S7. K3: check the levels that decide, with enough replications, under an exact recalibration rule

**must · §11.2 K3 · false positive**

**Problem.**
- **K3 checks the wrong levels.** It checks nominal 5% with 200 replications, and NO EDGE coverage at 95%. Decisions
  are made at 2.5% (5% after a first rejection) and at 97.5% bounds.
- **Its pass rule is too weak.** "At most 10 of 200":
  - fails a correctly sized test 42% of the time;
  - passes a test of true size 7% 17% of the time [C: binomial];
  - cannot tell 1% from 2% at the 1% level.
- **"The level is widened until it does" is not an algorithm.**

**Replacement (§11.2, K3):**
> K3 uses at least 2,000 null replications per scenario on the real fill calendar, re-run after every universe fix.
> Scenarios: the base and high-dispersion markets of 12.5, plus a heterogeneous-effect null in which each episode
> carries its own mean-zero effect (SD 3%, Student-t(3)). Hourly synthetic paths suffice, because K3 checks the
> inference, not the fill engine. For each family test, K3 reports the false-PASS rate at 2.5% and 5%, and the miss
> rate of the 97.5% NO EDGE bound. Pass: at each level, the upper end of the 95% binomial interval is at most 1.5×
> nominal. Otherwise that test's p-value is replaced by its simulation-calibrated version: the share of null
> replications (in the worst scenario) whose statistic is at least the observed one. Its NO EDGE bound then uses the
> matching simulated quantile.

### S8. State the effective sample at full within-cluster correlation

**should · §0, §7.4, §12.1, §12.4, §14 · interpretability; false positive wherever t(G − 1) is used**

**Problem.** The draft's "the weight of only about 24 equally sized months" is the zero-correlation measure. For the
variance of an estimate, about 12 months count. Each half has 5-7, and k = 10 alone about 8 (2.1).

**Replacement (§0, sample size):**
> ...spread over 60 months, with the weight of only about 24 equally sized months for the estimate and about 12 for its
> uncertainty (each half: 5-7).

Add G* to every interval (§14, "Uncertainty").

### S9. Verdict wording (§12.6)

**should · §12.6 · interpretability**

**The rules.**
- A one-sided bound never supports "no difference". NO EDGE says "not by E or more".
- INCONCLUSIVE must say what the design could not see, including an edge concentrated in a few crashes (2.3).

**Replacement table (§12.6):**

| test | PASS | NO EDGE | INCONCLUSIVE |
|---|---|---|---|
| H1 | "Selling stink-bid fills into the rebound beat buying the same coins at random times by X% per fill (95% CI), over N fills in G months (about G* independent months). After Robinhood costs, a flip made R% on average. It held in both halves, without the biggest month and crash, and on Robinhood-like prices." When the three largest episodes give more than half of the total, add: "Most of it came from three crashes (dates); it pays only if crashes like those recur." | "Flipping stink-bid fills doesn't beat random buys by the 3.75% per fill it would take to cover the round trip and the cash the bids tie up. Don't run the flip version." HARMS: "...and the fills did worse than random buys: they tended to come before further falls." | "The data can't tell. Deep fills come from about a dozen independent crash months, so an edge would have to be about 5% per fill or more to show up. An edge that lives only in the two or three biggest crashes could not show up at any size. The sheet shows no flip target." |
| H4 | "Method j's levels beat plain volatility-scaled levels at the same depth, in the same wicks, by X% per fill (95% CI). The sheet shows them." | "Chart levels (swing lows, round numbers, volume nodes, liquidation bands) were not better places for a bid than a plain volatility-scaled level at the same depth, by 1% per fill or more." | "Can't tell; the sheet uses plain volatility-scaled levels." |

**Descriptive rows (no verdict):**
- **D-H2:** "Descriptive only. Over 90 days, coins bought through stink bids did X% (95% CI) better [worse] than the
  same coins bought at random times outside the six months around each fill. An edge under about 20-40% could not be
  detected, and the comparison also reflects whether the crashes fell in bear or bull stretches."
- **D-H3:** "Descriptive only. Fast wicks were X% per fill (95% CI) better [worse] than slow slides to the same depth.
  A difference under about 6-10% per fill could not be detected."
- **D-H5:** "Descriptive only. A year after a fill, X% of fills on established coins and Y% on other top-100 coins were
  50% or more below the fill price. At the same volatility the gap was Z points (95% CI); a gap under about 12-14
  points could not be detected."

**Further rule.** No sentence says "made no difference", "is just" or "works". (The drafted H3 NO EDGE, "How fast the
price got there made no difference", and the H2 NO EDGE, "owning through stink bids is just owning, later", both claim
more than a one-sided bound allows.)

### S10. Twins: eligibility, pooled twins and regime drift

**should · §11.1 B-TWIN, §4.4 · false negative for long holds; interpretability**

**(a) Twins never take the delisting haircut.**
- Eligibility criterion (c), "a complete exit window", excludes twins whose window crosses a delisting or segment end.
- Fills, by contrast, can take the haircut.
- This contradicts 4.4: "Twins and benchmarks follow the same rule".

**(b) Pooled twins reintroduce same-period drift.** Pooled twins drawn "in the same calendar year" bring back the
drift that the ±182-day exclusion removes. That is the lesson of repo 5.19 [R].

**(c) For 90-day holds, ±182-day twins compare regimes.**
- They compare the fill's market regime with other regimes.
- Crypto regime drifts of a few tenths of a percent a day over six months move a 90-day comparison by tens of points,
  far more than E = 5% [U: illustrative; e.g. BTC's 2022 fall and 2023 rise].
- The draft's own power run shows H2's clustered test rejecting 1.0% where 5% is nominal (`power.py` output [C]).
- A likely mechanism [U]: twins drawn from other fills' periods create negative dependence between fills. If so, H2 is
  also overly conservative.

**Replacement (§11.1):**
> (c) A complete exit window, except that a window cut short by a delisting or a segment end is kept and closed by the
> delisting rule of 4.4. Only the end of the data censors. Pooled twins come from all U-Q1 coins' eligible minutes
> outside ±182 days of the fill. For holds of 90 days or more, the report states next to every estimate: "Random buys
> here exclude the six months around each fill, so the comparison also reflects whether crashes fell in bear or bull
> stretches."

### S11. Method-level claims on the sheet need closed testing; D10 needs its own family

**should · §15.1 (chart levels, round numbers), §13 D9, D10 · false positive**

**Problem.**
- **The BH route.** "H4 PASS with that method's BH q < 0.10" applies FDR at 10% after a FWER omnibus. That does not
  control the error of the method-level claim.
- **The D10 route.** "A 95% interval above zero" is unadjusted across about ten level variants: M4 with N = 30, 90 and
  365 and two buffers, M4f, M4s, M5f, M5a, M5b, M6 and M7.

**Replacement (§15.1, the chart-levels row):**
> Shown only for a method j whose Romano-Wolf step-down adjusted p_j (the same max-t bootstrap as H4) is below the Holm
> level at which H4 was rejected. Or for a method that passes the fill-odds family: one pre-registered test per H4
> method (the four of H4) plus D9, Holm at 5%, episode-clustered, fixed before any outcome is computed. Such a method is
> labelled "better fill odds at this depth, not a better price".

### S12. Intervals for overlapping windows (D6, D7)

**should · §13 D6, D7, §12.6 · false positive (intervals too narrow)**

**Problem.**
- D6 evaluates every weekly placement with a 365-day hold: 52 overlapping windows per coin-year. Its "with an
  interval" is unspecified.
- D7's month-block bootstrap has no block length.

**Replacement:**
> D6: aggregate by placement month (calendar time), then a stationary bootstrap of the monthly values with a mean block
> length of 12 months (at least the holding period), like the mega-cap study's year-long blocks. D7: a stationary
> bootstrap of the account's monthly returns with a mean block of 6 months, and 12 months as a sensitivity. The
> gatekept "You could run it on Robinhood" interval uses the 12-month version.

### S13. Known-answer controls with drift and delistings

**should · §11.2 K1 · false positive or false negative (a regime- or delisting-driven Δ goes unseen)**

**Problem.** K1 has zero drift and no delistings, so it cannot reveal S10's confounds.

**Replacement (add to §11.2):**
> K1c: regime-switching drift (for example ±0.2% a day in 6-month regimes [U: illustrative]), with crash intensity 3×
> higher in the bear regime and no timing effect at the minute level. Report P1's Δ under X-FLIP and X-HOLD-90 with the
> drafted twins. The descriptive H2 text quotes K1c's Δ90 as "what regime timing alone produces". K1d: synthetic
> delistings (for example 2% of coin-years, closed at last trade × 0.7). Fills and twins must take the haircut at equal
> rates.

### S14. The sheet's fill odds are overdispersed and depend on the regime

**should · §15.1 (fill odds), §13 D5 · interpretability (intervals too narrow)**

**Problem.**
- **The sheet's intervals.** Yearly fill counts are 7.7× overdispersed (2.8). Wilson intervals on bid-weeks are about
  2.8× too narrow, and most coins have 4 or fewer independent episodes.
- **D5's calibration rule.** It calls a level calibrated if realized/predicted lies in [0.67, 1.5] in both halves.
  - The halves' realized rates already differ by 1.47× (4.53% against 3.08%).
  - Each half has a G* of 5-7.
  - So the band can fail a calibrated model and pass a miscalibrated one.

**Replacement:**
> Sheet fill odds: the shrunken estimate as drafted. Interval: the Wilson half-width × √φ, where φ is the Pearson
> dispersion of the pooled yearly fill counts at that rung (7.7 at k = 8 [C]). The row reads "N fills in E crash
> episodes". D5: realized/predicted with an episode-cluster bootstrap 90% interval per half; "calibrated" if both
> intervals overlap [0.67, 1.5].

### S15. Collapse-removal gates should remove the cases that support the claim

**could · §12.3 (H5 gate), §12.4 · interpretability**

**Problem.** The gate reads "b > 0 with LUNA and FTT fills removed".
- Today every FTT fill, and LUNA classic's May 2022 fills, lie outside U-Q1 [C]. So the gate removes cases that
  support the claim, as it should.
- After the quote-asset age fix of 5.1, LUNA classic enters U-Q1. The gate would then remove a case against the claim,
  and lose its point.
- The point is moot if H5 becomes descriptive.

**Replacement:**
> ...without the coin whose removal lowers b most (reported for D-H5).

### S16. Report how concentrated the result is in the top three episodes

**could · §12.4, §14 · interpretability**

**Problem.** 21% of P1's fills come from 3 episodes and 56% from 10, and the robustness gates do not bind (2.3).

**Replacement (add to §12.4):**
> Every headline also reports the share of the total Δ that comes from the three largest episodes, and the estimate
> without them. If that share exceeds 50%, the verdict sentence names the episodes (S9).

### S17. D-H3: compare fast and slow fills inside the same episode

**could · §12.3 (H3) · interpretability**

150 of the 216 slow fills share an episode with fast fills [C]. Report b with episode fixed effects as the primary
descriptive version (its SD is 22% smaller in the base scenario), with the drafted version beside it.

### S18. Re-run the power study after the changes

**should · §12.5, §0 · interpretability (the MDEs quoted in the verdict sentences)**

**Problem.** Section 12.5's MDEs rest on three weak points:
- they use CR1 t(G − 1), which is liberal;
- the H4 proxy has no depth term;
- the H5 setup has a single σ, no volatility differences between the groups and no window overlap.

**Fix.** Every MDE quoted in §0, 12.3 and 12.6 should come from the corrected machinery (S1-S5), run on:
- the base, high and heterogeneous-effect scenarios;
- the concentrated alternatives of 2.3.

### S19. A lower-variance "bid or buy a little later?" benchmark for D-H2

**could · §11.1, §13 · interpretability**

- **The benchmark.** Twins entering at random minutes in (τ_f + 1 day, τ_f + 30 days], each held 90 days.
- **Why it has lower variance.** They share most of the fill's window, so the market's 90-day path largely cancels.
- **What it answers.** "Was the stink bid better than buying the same coin a little later?" It is unbiased under a
  martingale.
- **Why it avoids 5.19's bias.** Its windows start after the fill. That bias came from benchmark windows that contain
  the decline.
- **Reporting.** Beside the ±182-day twins, labelled.

---

## 4. Summary of proposals

| # | severity | sections | change | bias if left |
|---|---|---|---|---|
| S1 | must | 0, 1.2, 12.2, 12.3, 12.6, 15.1 | Holm family = {H1, H4}; H2, H3 and H5 become descriptive | false negative; interpretability |
| S2 | must | 12.1, 12.3 | p = max(p_WCR, p_t(G*−1)) on month-blocks; matching bounds; drop the pairs-bootstrap formula | false positive |
| S3 | must | 10, 12.3, 12.5, 12.6 | E_H1 = 3.75% per fill (2.26% if reserved cash earns 3.35%) | false negative (NO EDGE); interpretability |
| S4 | must | 6.3, 12.3, 12.5 | H4 compared at the same depth, inside the same wick (coin-week fixed effects plus a depth term) | false positive |
| S5 | must | 12.3, 4.3, 12.5 | H5: p0 covariate, two-way coin × quarter clusters, descriptive | false positive |
| S6 | must | 11.1, 13 | D11 null distribution from K3; no percentile against random-time programs | false positive |
| S7 | must | 11.2 | K3: ≥ 2,000 replications, the decision levels, an exact recalibration rule | false positive |
| S8 | should | 0, 7.4, 12.1, 12.4, 14 | report G* (about 12; halves 5-7) | interpretability |
| S9 | should | 12.6 | one-sided wording; INCONCLUSIVE names what could not be seen | interpretability |
| S10 | should | 11.1, 4.4 | twin eligibility through delistings; pooled twins outside ±182 days; regime caveat | false negative; interpretability |
| S11 | should | 15.1, 13 | closed testing for method-level sheet claims; a fill-odds Holm family | false positive |
| S12 | should | 13, 12.6 | block lengths of at least the holding period for D6 and D7 | false positive |
| S13 | should | 11.2 | K1c (regime drift), K1d (delistings) | either direction |
| S14 | should | 15.1, 13 | overdispersion-widened fill-odds intervals; calibration with episode intervals | interpretability |
| S15 | could | 12.3, 12.4 | remove the most supportive coin, not named coins | interpretability |
| S16 | could | 12.4, 14 | report the top-3-episode share and the estimate without those episodes | interpretability |
| S17 | could | 12.3 | D-H3 with episode fixed effects | interpretability |
| S18 | should | 12.5, 0 | re-run the power study with the corrected machinery | interpretability |
| S19 | could | 11.1, 13 | post-fill twins for D-H2 | interpretability |

---

## 5. What the draft already gets right (keep)

- **The prior.** "The data cannot tell" is stated as the most likely answer before any outcome.
- **Random-entry twins with the same exit rule** as H1's benchmark. Under a martingale they are unbiased for flip
  exits, whatever the volatility regime. [C: in this note's null runs the mean Δ was −0.08% (base) and −0.11% (high).
  That is about 2 Monte Carlo SEs below zero, from the engine's hourly approximation, and negligible against E.]
- **B-MKT is compared per placement, not per fill.** This avoids the mechanical gain from conditioning on L < P0.
- **Point-in-time universes with dead coins**, hindsight labels on U-A and U-C, the delisting haircut and its 0% and
  100% sensitivities.
- **Gates as conjunctions:** halves, single events, F3, U-B. They can only make PASS harder.
- **The controls.** The K1 and K2 known-answer and positive controls, the K4 look-ahead perturbation and the K5 fill
  audit.
- **Verdict sentences written in advance**, and "It does not work" reserved for NO EDGE.

---

## 6. Reproducing these checks

The scratch scripts are in this session's scratchpad, folder `critique_stats/`. They will not survive the session;
section 1 gives their method. Every script runs with `python3 -I`.

| script | what it does |
|---|---|
| `counts.py` | counts on `design_sim/fillcal7.parquet`: effective clusters, episodes, placebo depth mix, H5 σ by group and tercile, collapse coins, per-coin support |
| `sim_engine.py` | the H1 synthetic null on the real calendar (`power.py`'s path model), with twins and block-shifted luck programs. Args: scratchpad, replications, σ_e, crash multiplier, crash days, tag, seed. Runs used seeds 101-303 (base) and 404-505 (high). |
| `analyze_null.py` | sizes at the Holm levels, power by family, NO EDGE reachability, the luck benchmark, H3 with episode fixed effects |
| `power2.py`, `size_combo.py` | power of the two-test family; size of the max(p_WCR, p_t(G*−1)) rule |
| `sim_h5.py` | the H5 null with no quality effect. Args: scratchpad, replications, scenario (`sigma` or `beta`), κ |

Run time on 4 CPUs: about 3 minutes per 400 replications of `sim_engine.py`, and about 1 minute per H5 scenario.

---

## Sources

**Inference and multiplicity** (abstracts or catalogue records, read through search, 2026-11-18):
- Cameron, Gelbach & Miller (2008), "Bootstrap-based improvements for inference with clustered errors", *REStat*
  90(3): 414-427 [A]. [EconPapers](https://econpapers.repec.org/RePEc:tpr:restat:v:90:y:2008:i:3:p:414-427)
- Cameron, Gelbach & Miller (2011), "Robust inference with multiway clustering", *JBES* 29(2): 238-249 [A].
  [EconPapers](https://econpapers.repec.org/RePEc:taf:jnlbes:v:29:y:2011:i:2:p:238-249)
- Carter, Schnepel & Steigerwald (2017), "Asymptotic behavior of a t-test robust to cluster heterogeneity", *REStat*
  99(4): 698-709: the effective number of clusters G* [A].
  [IDEAS](https://ideas.repec.org/a/tpr/restat/v99y2017i4p698-709.html)
- MacKinnon & Webb (2017), "Wild bootstrap inference for wildly different cluster sizes", *J. Applied Econometrics*
  32(2): 233-254 [A]. An online appendix corrects some of its simulation tables [S].
  [EconPapers](https://econpapers.repec.org/RePEc:wly:japmet:v:32:y:2017:i:2:p:233-254)
- MacKinnon, Nielsen & Webb (2023), "Cluster-robust inference: A guide to empirical practice", *J. Econometrics*
  232(2): 272-299 [A]. [EconPapers](https://econpapers.repec.org/RePEc:eee:econom:v:232:y:2023:i:2:p:272-299)
- Webb (2023), "Reworking wild bootstrap-based inference for clustered errors", *Canadian J. Economics* 56(3): the
  six-point weights [A]. [Working paper QED 1315](https://econpapers.repec.org/RePEc:qed:wpaper:1315)
- Ibragimov & Müller (2010), "t-statistic based correlation and heterogeneity robust inference", *JBES* 28(4):
  453-468 [A].
  [Princeton record](https://collaborate.princeton.edu/en/publications/t-statistic-based-correlation-and-heterogeneity-robust-inference/)
- Romano & Wolf (2005), "Stepwise multiple testing as formalized data snooping", *Econometrica* 73(4): 1237-1282 [A].
  [EconPapers](https://econpapers.repec.org/RePEc:ecm:emetrp:v:73:y:2005:i:4:p:1237-1282)
- Holm (1979), "A simple sequentially rejective multiple test procedure", *Scand. J. Statistics* 6(2): 65-70 [A].
  [JSTOR](https://www.jstor.org/stable/4615733)
- Bretz, Maurer, Brannath & Posch (2009), "A graphical approach to sequentially rejective multiple test procedures",
  *Statistics in Medicine* 28(4): 586-604: weighted Holm and gatekeeping [A].
  [DOI](https://doi.org/10.1002/sim.3495)
- Driscoll & Kraay (1998), *REStat* 80(4): 549-560: the HAC sensitivity in 2.6 [U: citation from memory].
  [IDEAS](https://ideas.repec.org/a/tpr/restat/v80y1998i4p549-560.html)

**Repo and session:**
- [`design_draft.md`](design_draft.md), [`evidence.md`](evidence.md), [`mechanics.md`](mechanics.md),
  [`data_inventory.md`](data_inventory.md) [R].
- The draft's scratch fill calendar and power script (`design_sim/` in this session's scratchpad), read and re-used for
  the fill calendar and the path model only.
- HANDOFF 5.19, for the same-period drift lesson, as cited in `evidence.md` §5 [R].
- The 3-month T-bill at 4.21% (2026-11-02), as cited in the draft: [FRED DGS3MO](https://fred.stlouisfed.org/series/dgs3mo) [A].
