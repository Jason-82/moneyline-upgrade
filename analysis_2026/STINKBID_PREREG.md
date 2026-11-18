# Pre-registration: stink bids on volatile "solid" coins

**Status: FROZEN 2026-11-18**, before any post-fill price, return, P&L or strategy outcome was computed on real data.

This document freezes the design drafted in
[`research_notes/Stink bids/design_draft.md`](research_notes/Stink%20bids/design_draft.md) (commit ae5425c). It also
folds in the 49 proposals of three adversarial reviews of that draft (commit d44046d): statistics (S1-S19), simulation
fidelity (V1-V15) and relevance to the user (R1-R15). Where this document and the draft differ, this document wins.
Where this document is silent, the draft's text at commit ae5425c applies; this covers the level formulas (draft
§6.2), the capacity window (§8.3) and the data series (§4.1). The revision log at the end says what was adopted,
merged or declined, and why.

- **Research notes** (`analysis_2026/research_notes/Stink bids/`):
  - `mechanics.md`: Robinhood order mechanics and venues;
  - `evidence.md`: the literature and the repo's related findings;
  - `data_inventory.md`: the data and the counts-only descriptive tables;
  - the draft and the three critiques.
- **Code (to be built):** `analysis_2026/stinkbid_*.py`; data from `analysis_2026/fetch_stinkbid_data.py` and the new
  `stinkbid_data.py`.
- **Results:** `analysis_2026/results_stinkbid/`.

---

## 1. The question

**The user's words (2026-11-18):** "a strategy that looks at highly volatile yet 'solid' cryptos that I wouldn't mind
owning, like HYPE, like NEAR, projects with real revenues.... it looks at the charts and through some process figures
out good levels to place 'stink bids'; that is, bids that are way below current price, in the hopes of catching a
momentary down wick to fill the trade... maybe it wouldn't even need to place any trades for me, just analyze each
chart and give me solid choices for the levels of the stink bids and I could place the limit trade myself. can you
help me elucidate/test?"

**In testable form.** A stink bid is a resting limit buy far below the price. It fills on two kinds of selling:
- forced selling that overshoots and then reverts, which is good for the bidder;
- informed selling that keeps going, which is bad for the bidder.

A resting bid is a free put option written to the market (Copeland and Galai 1983). It earns money only if fills come
from overshoots that revert.

The study asks four questions, at fills a resting bid on Binance spot could have obtained, with a Robinhood-route
haircut and a Robinhood-listed subset:
1. **Flip:** are fills, sold into the rebound by hand, better buys than random buys of the same coin with the same
   exit?
2. **Rest vs alert:** if the user is going to buy after crashes anyway, does a resting bid buy more coin per dollar
   than a price alert at the same level followed by a manual buy?
3. **Levels:** are chart-based levels better than plain volatility-scaled levels at the same depth?
4. **Usable output:** what level sheet should the user get?

It also describes, without verdicts:
- owning after a fill;
- fast wicks against slow declines;
- knife-catching rates;
- the cost of waiting;
- the user's MoneyLine;
- the tail in absolute terms.

## 2. Priors (stated now, from the research notes)

- **Most deep bids never fill**, and fills cluster on a few market-wide crash days.
  - All 38 user-style coin-days at least 40% below the prior close come from 7 distinct days.
  - All 21 at 50% come from 3 days: 2020-03-12, 2021-05-19 and 2025-10-10.
- **The effective sample is a few dozen crash episodes, not about 1,300 fills.** P1's fills fall in 60 months. They
  carry the weight of about 24 months for the estimate and about 12 for its uncertainty.
- **The flip:** a small positive gross effect is possible. Fast, market-wide, high-volume drops tend to revert within
  hours (Christensen, Oomen and Renò 2022; Nagel 2012). Against that:
  - passive crypto fills were adversely selected in every band of the repo's scalping study;
  - its resting dip bid lost even before costs;
  - Robinhood's round trip costs about 1.9%.
- **Owning:** about zero against random entries (the mega-cap dip study; AQR "Hold the Dip"; K33 on liquidation
  spikes).
- **Chart levels** may change fill odds but not post-fill returns (Osler 2000; repo 5.19; Urquhart 2017).
- **A "solid" filter** lowers knife-catching but does not remove it. LUNA and FTT both had real activity or revenue.
- **Venue:** Binance spot lows are an upper bound for a Robinhood fill. Robinhood's default route fills only when its
  ask, about 1% above the mid, reaches the bid.
- **The most likely answer to every return question is "the data cannot tell".**

## 3. Already seen (contamination statement)

No post-fill price, return, P&L or strategy outcome has been computed on real data. Before this freeze, the following
were seen; all are fill counts, coverage or timing.

- **The draft and the critiques:**
  - the fill calendar of P1 and its variants on hourly bars, with counts by rung, universe, life, month, episode and
    speed class;
  - capacity distributions;
  - the share of fills that also cross the Binance index and perpetual lows (F3/F5 survival);
  - the clock time of fills;
  - Kaplan-Meier waiting times;
  - the MoneyLine state at placement;
  - fill counts for HYPE's perpetual.
- **The research notes:** event-day lows (spot, perpetual, index), event-day volumes below levels, outage hours, and
  published accounts of what followed the named crashes (e.g. the hours-long rebound of 2025-10-10). Because those
  accounts are public, **no exit, depth or filter here is justified by any named episode.** Every choice cites the
  literature or fill counts.
- **The critics' synthetic simulations**, with paths drawn from model markets. No real outcome entered them.

---

## 4. Data

- **Built** (`data/stinkbid/`, gitignored; `data_inventory.md`):
  - Binance spot 1d klines for all 771 USDT pairs (2019-10-01..2026-11-17);
  - spot 1h klines for 486 candidates;
  - USD-M 1d klines for 76 contracts;
  - aggTrades on 13 event coin-days.
- **To fetch** (new module `stinkbid_data.py`; every zip checked against its `.CHECKSUM`):
  - **1m spot klines, all days**, for U-Q1, U-Q1-12, U-A and U-C;
  - **U-B 1m klines**, streamed coin by coin (download, run, keep per-bid records, delete);
  - **aggTrades**, streamed for every U-Q1 coin-day with a fill (for capacity), plus a K6 sample;
  - **1m USD-M index and last-price klines** on candidate days (V4's fetch rule);
  - **for M7** (from 2021-12): 1h mark-price klines and futures `metrics`;
  - **daily klines back to 2017-08**, for M3's pooled calibration;
  - **listing ages** across quote assets (USDT, BTC, BNB, ETH, BUSD);
  - **a USDT/USD proxy**: hourly USDC/BUSD/TUSD vs USDT.
- **Later session** (the environment "moneyline-upgrade" allows the hosts):
  - Coinbase 1m candles (F6, the venue gap D3);
  - DefiLlama revenue (U-Q2).
  - Both are descriptive here. If they are not built, the report says so.
- **Cash:** `regime_switch.rf_annual_pct()`. The 3-month T-bill was 4.21% on 2026-11-02.
- **Robinhood ticks and sizes:** the read-only `get_currency_pairs` catalog of 2026-11-18, saved by the orchestrator.

**Windows.**
- **Placements:** Mondays 2020-01-06..2026-11-09.
- **Follow-up:** the data end 2026-11-17. A fill enters a horizon's statistics only if the whole horizon is observed.
- **Halves:** 2020-01..2022-12 and 2023-01..2026-11.

### 4.1 Integrity rules (causal; V2, V9, V12)

- **No placement, bid life, fill or exit is dropped or shortened because of data after its own time stamp.**
  - When a segment boundary (a missing day, or a jump of more than 25% across a no-trading gap) or the end of
    trading arrives during a bid's life, the bid is cancelled at the boundary, and fills before it stand.
  - A position open at the boundary is valued by the rules below.
  - σ windows and level look-backs never reach back across a boundary.
- **Redenominations.** A boundary across which next open / last close lies within ±5% of 10^n (n ≠ 0) is joined at
  ratio 10^n once confirmed from Binance's announcement: SUN 2021-06, COCOS 2021-01, BNX 2023-02, DREP 2021-03, BTCST
  2021-03, STRAX, VIDT. An unconfirmed ratio is treated as a delisting.
- **Rebrands and swaps** continue at the swap ratio: EOS→A, MATIC→POL, FTM→S, RNDR→RENDER, MKR→SKY, AGIX/OCEAN→FET,
  BTT→BTTC, LIT→HEI.
  - A successor inherits the predecessor's listing age and monthly ranks.
  - A ticker reuse (a different asset, e.g. LUNA from 2022-05-31) restarts both.
  - Unverified ratios are treated as delistings.
- **Delistings.** A position open when trading stops is valued at the VWAP of its last full trading day × (1 − 0.30).
  The last trade × 0.70, a 0% haircut and a 100% haircut are sensitivities. A relisting after a gap (FTT, 310 days)
  starts a new segment; the gap is a delisting.
- **Stablecoins** are excluded: the inventory list plus PAX/USDP. As a backstop, any base whose 90-day SD of daily
  returns is below 0.5% at the start of the month is excluded.
- **Outages.** A Binance spot minute that is missing or has `trades = 0` never fills and never triggers an exit.
  Index minutes are handled in §7.
- **Bad prints are real trades and are kept.** The sensitivity drops fills whose fill minute alone had less than $1k
  of seller-initiated notional below L, or whose index low in that minute stayed above L. Nothing after the fill
  minute is used.

## 5. Universes

| id | rule | role |
|---|---|---|
| **U-Q1 "large, long-listed (Binance volume)"** | Members of U-B in month M with listing age ≥ 24 months (any quote asset; successors inherit) and a median monthly volume rank ≤ 50 over M−11..M | **primary** for H1, H2R and H4 |
| U-B | Binance top 100 of month M by median daily USDT volume over the prior 90 days, including dead and delisted coins (exclusions as in §4.1 and the inventory) | gate (same sign) for H1 and H2R; D-H5's population |
| U-Q1-12 | U-Q1 with a 12-month listing rule (includes LUNA classic in May 2022) | sensitivity row; D-H5 row |
| U-Q1-xm | U-Q1 without memecoins (fixed list: DOGE, SHIB, PEPE, FLOKI, BONK, WIF, PEOPLE) | sensitivity row |
| U-Q2 "real revenue" | U-Q1 members whose DefiLlama protocol or chain earned ≥ $10M of revenue in the 365 days before M, using only data dated before M | later session; descriptive |
| U-A | the 24 user-style coins plus MKR (`data_inventory.md` §2.1) | **hindsight**; reported, never decides |
| U-C | Robinhood-tradable on 2026-11-18 (92-pair catalog) | **hindsight** (survivors); the sheet's default list; a labelled row beside every headline |

- **Naming.** U-Q1 is called "large, long-listed (Binance volume)" wherever the user reads it. It is never called
  "solid" or "quality".
- **LUNA and FTT were outside U-Q1 at their collapses.** LUNA classic's first Binance listing in any quote asset was
  2020-08, so it was 21 months old in May 2022. FTT's median volume rank was 54.
- **HYPE** has Binance spot only from 2026-09-24. It is reported individually on its perpetual's index price,
  labelled "short history, perpetual-index proxy, no verdict", with the note of §13.

## 6. Levels and orders

### 6.1 Placement and inputs (V6)

- **Bids are placed every Monday at 03:30 UTC** (Sunday 10:30 pm EST / 11:30 pm EDT), when Sunday's spot files have
  been published.
- **Inputs:**
  - P0, σ30, ATR14 and every spot-based level use Binance spot data through Sunday (d0);
  - futures-based inputs (M7's open interest and mark prices, HYPE's index) use data through Saturday (d0 − 1).
- **The previous week's bids stay live** until the new ones are placed.
- **Sensitivity:** placement at Monday 13:30 UTC.
- **Notation (draft §6.1):**
  - σ = σ30, the SD of the last 30 daily log returns (≥ 25 valid, one segment);
  - ATR% = Wilder ATR14 / P0;
  - τ = the tick, inferred from the decimal strings of the last 7 days' 1m prices;
  - δ(L) = ln(P0/L)/σ.

### 6.2 Level methods (formulas as in draft §6.2 unless changed here)

- **M2, the primary.** Volatility-scaled: L = ⌊P0·exp(−k·σ)⌋τ with **k = 6, 8, 10** (P1). k = 5 and 12 are secondary.
- **M1:** fixed % (d = 15, 20, 25, 30, 40, 50%).
- **M2a:** ATR-scaled (k_A = 4, 5, 6).
- **M3:** quantile-calibrated to a 7-day fill probability p = 2, 5, 10%. Pooled over all eligible pairs' windows that
  ended before t0, expanding from 2017-08.
- **M4:** below the N-day low (N = 30, 90, 365), with a 0.5 or 1.0 ATR buffer. Also M4f (in front of the low) and M4s
  (below a confirmed swing low).
- **M5:** round numbers, as M5f (one tick ahead), M5a (at) and M5b (0.5 ATR beyond).
- **M6:** 90-day 1h volume-profile node.
- **M7:** estimated long-liquidation band from open interest, from 2021-12. Mark-price crossings are read only up to
  the last bar published before t0. It is an estimate of positions, not observed orders.
- **M8:** crash-depth calibrated (exploratory).
- **Admissible band:** chart methods M4-M7 must give δ ∈ [4, 14]; otherwise the method abstains for that coin-week.
- **Placebos for H4** (draft §6.3): L_M·exp(±0.5·ATR%) and L_M·exp(±1.0·ATR%), run exactly like L_M.

### 6.3 Lives, programs and size

| program | universe | levels | life and refresh |
|---|---|---|---|
| **P1 (primary)** | U-Q1 | M2, k = 6, 8, 10 | 7 days; cancelled and re-placed every Monday 03:30 UTC |
| P1-30 / P1-90 | U-Q1 | M2 | 30 / 90 days (90 = Robinhood's GTC life, "set and forget"); re-placed at expiry |
| P1-1 | U-Q1 | M2 | 1 day, re-placed daily at 03:30 UTC (exploratory) |
| P1-lazy | U-Q1 | M2 | weekly, but a resting bid is kept if the new level is within 5% of it |
| P1-G | U-Q1 | M2 | weekly, placed only when the coin's replicated MoneyLine is green at d0 |

- **Every bid-week is an independent order with its own cash** (V7). Per-fill statistics use every fill of the
  program. The one-position-per-rung rule applies only to the accounts (D7).
- **Size per rung:** Q = $10k (primary), with $1k and $100k as sensitivities. Per-fill returns are per dollar filled
  and do not depend on Q; Q enters only through capacity.
- **Cash:** every bid is fully cash-backed.

## 7. Fill model

| id | rule | role |
|---|---|---|
| **F1** | Binance spot 1m: the first live minute (from placement + 1 minute) with trades > 0 and low ≤ L − τ. Fill at L | **primary** |
| F2 | touch: low ≤ L | illusion bound only |
| **F3** | Binance USD-M **index** 1m only: index low ≤ L/(1 + s), with s = 1% primary and 2, 3, 5% sensitivities. Fill at L. Index minutes that are missing, or have fewer than 30 index updates, are outages. A fill whose index minute is missing is "F3-unverifiable": not an F3 fill, reported by event; there is no fallback to spot | **gate on every PASS**; the Robinhood market-maker route. The sheet's numbers come from F3 |
| F3d | F3 requiring a whole index minute ≤ L/(1 + s) (dwell) | reported beside every F3 result |
| F4 | index reaching L (s = 0), at C-EX costs, for coins eligible for exchange routing | Robinhood exchange route; a composite-price proxy (Bitstamp depth unknown) |
| F5 | Binance USD-M last price 1m, F1 rule | deeper-wick sensitivity; **never** a fill this user could get |
| F6 | Coinbase 1m (later session) | venue gap |

- **F1 + C-RH meaning** (V10). It corresponds to a Robinhood market-maker-route bid at about L × 1.0095 that triggers
  when the mid reaches about L. F3 corresponds to the limit L that the sheet prints.
- **Gap-through fills.** A resting bid fills at its limit even when the minute gapped wholly below it. Such fills are
  listed and counted (K5).
- **Capacity.**
  - C(L) is the seller-initiated aggTrades notional printed below L within the capacity window of draft §8.3. It
    accumulates causally, minute by minute.
  - Filled dollars = min(Q, θ·C(L)), with θ = 1 primary and θ = 0.25 as a sensitivity. An unfilled remainder rests
    until expiry.
  - The 1-minute approximation C₁ is used where aggTrades are not streamed. It tracked aggTrades with a median ratio of
    0.98.
  - Capacity is labelled "Binance spot book". On the market-maker route it is context only.
- **USD vs USDT.** The K8 table reports F3 with the index converted to USD (hourly stablecoin proxy).
- **Robinhood outage windows** (±1 h) block F3/F4 fills and exits: 2021-04-15, 2021-05-04, 2022-02-25, 2025-10-06,
  2025-10-20.

## 8. Exits and the manual clock (V3, R3)

**Manual-action rule M.** An action a person takes in response to an event at minute t happens at t + 60 minutes if t
falls between 07:00 and 22:59 America/New_York, and otherwise at the next 07:00 New York time. Rule M applies to the
flip's sell, its time stop, twins and the alert buyer.

| id | rule | role |
|---|---|---|
| **X-FLIP** | Target R½ = ⌈L + ½(P0 − L)⌉τ, live from M(fill). If the price is at or above R½ when the sell goes live, it executes at that minute's open as a marketable limit. Otherwise it fills in the first later minute with high ≥ R½ + τ. Else it is sold at the first live minute at or after M(fill + 72 h) | **primary flip** (H1, H4) |
| X-FLIP-bot | the same with the sell live 1 minute after the fill | sensitivity, labelled "bot" |
| flip grid | targets L·(1 + g) for g = 5, 10, 20%; L·e^σ; L·e^{2σ}; R½; H24 (the pre-wick high known at the fill); P0. Each × time stops of 24 h, 72 h and 7 days, all under rule M | sensitivity rows |
| X-HOLD-h | sell at the first live minute at or after M(fill + h), h = 7, 30, 90, 365 days | descriptive |
| X-OWN | hold to 2026-11-17, marked at the last close | accounts |
| X-ML | hold until the first red MoneyLine close after a green one | descriptive |

**Route-specific exits.**
- F3 rows: the target fills when the index high ≥ R½/(1 − 0.0095), and market sells get index × (1 − 0.0095). In the
  crash-spread rows (s = 2, 3, 5%) the exit spread within 24 h of the fill is s.
- F1 rows: the cost scenario is applied to the fill price.
- **The alert buyer (B-ALERT)** pays the ask on the F3 route: index open × (1 + 0.0095), or × (1 + s) in the
  crash-spread rows within 24 h of the fill. On F1 rows it pays the minute's open × (1 + c_b). The resting bid pays L
  on F3 (the spread is embedded in its trigger) and L × (1 + c_b) on F1.

## 9. Costs and carry

| id | buy | sell |
|---|---|---|
| **C-RH (primary)** | +0.95% | −0.95% (target or market) |
| C-EX | +0.50% maker | −0.50% maker on limit targets, −0.95% taker on market sells |
| C-0 | 0 | 0 |
| C-BUS | 0% maker | 0.02% taker (Binance.US; not in New York) |

**Carry on reserved cash** = (T-bill − r_res) × reserved dollars × time. It is charged in the accounts (D7) and in E
(§10.3), with r_res ∈ {0 (primary), 3.35% (Gold sweep)}. Whether cash reserved for an open Robinhood crypto order
earns sweep interest is not documented.

---

## 10. Hypotheses, statistics and verdicts

### 10.1 Benchmarks

| id | definition | used in |
|---|---|---|
| **B-TWIN** | For fill f (coin i, minute τ_f, exit X): R = 100 entry minutes drawn uniformly from coin i's eligible minutes. Eligible means: (a) in the program's universe that month; (b) outside [τ_f − 182 d, τ_f + 182 d]; (c) a complete exit window, except that a window cut short by a delisting or segment end is kept and closed by the §4.1 rules. Each twin enters at that minute's open (plus cost) and exits by X with the same relative target ln(R½/L), the same rule-M clock, route and cost scenario. If fewer than 182 eligible days remain: pooled twins from all U-Q1 coins' eligible minutes outside ±182 days of τ_f. Seed `default_rng(20261118 + fill index)` | H1, H4, D-H2, D-H3 |
| **B-ALERT** | The alert buyer buys coin i at market at the open of the first traded minute at or after M(τ_f), on the fill's route and cost scenario. Outcome: a_f = P_alert,f / L_f − 1, the coin-count advantage of the resting bid; it is the same at every later exit date. Sensitivities: fixed delays of 2, 8, 24 and 72 h | **H2R** |
| B-POST | twins entering at random minutes in (τ_f + 1 d, τ_f + 30 d], held 90 days | D-H2 (beside B-TWIN) |
| B-ML | buy the same coin at the next day's open after the first green MoneyLine close at or after τ_f (`moneyline_ref`, the pre-October-2026 replica; "no re-entry" if none within 365 days) | D-ML |
| B-MKT | buy at market at the placement minute + 1, same horizon; compared per placement, not per fill | D6 |
| B-MIX | the same coins held at a constant fraction x of the account (equal weights, rebalanced monthly), rest in T-bills; x = the stink-bid account's time-average invested fraction | D7 (first benchmark) |
| B-TBILL, B-DCA, B-HOLD, B-ALERT-DCA, B-ML-DCA | as in draft §11.1 and R13 | D7, D7-OWN |
| Leave-out drift | r_f − μ̂_i × holding time, μ̂_i outside ±182 days | sensitivity |

### 10.2 Units, clusters and the p-value (S2, S8)

- **Units.**
  - Per-fill net return: r_f = exit × (1 − c_s) / (L × (1 + c_b)) − 1.
  - Excess: Δ_f = r_f − r̄_twin,f, where twins pay the same costs.
  - Each fill counts once; size-weighting is a sensitivity.
- **Clusters.** Calendar months of the fill, merged into month-blocks when an event episode spans two months. An
  episode is a run of fill days at most 3 days apart. For 365-day outcomes, see D-H5.
- **The p-value that enters Holm** is p = max(p_WCR, p_G*):
  - p_WCR is the wild cluster restricted bootstrap-t p-value (null imposed, Webb six-point weights, B = 9,999,
    CR1-studentized);
  - p_G* is the CR1 t-test referred to Student t with G* − 1 df, where G* = (Σ n_g²)² / Σ n_g⁴ over clusters with
    fills.
- **NO EDGE bound.** The larger of the wild bootstrap-t bound (unrestricted, same weights) and θ̂ + t_{1−0.05/3, G*−1}·SE,
  at one-sided level 1 − 0.05/3 = 98.33%. It is widened if K3 requires.
- **Every interval states G, G* and the cluster unit.** Episode, week and two-way coin × month clusters are
  sensitivities.
- **Not used:** the pairs cluster bootstrap and the non-studentized bootstrap p formula.

### 10.3 The Holm family: three decisive tests (S1, R1)

One Holm family of three one-sided tests at 5%: **H1 FLIP, H2R RESTING, H4 LEVELS**.
- Holm runs on all three p-values whatever their other conditions. The other PASS conditions are gates.
- Everything else is descriptive. Any p-value shown for a descriptive row is labelled exploratory and BH-adjusted
  within its table.

| id | claim | statistic | E | PASS requires (all) |
|---|---|---|---|---|
| **H1 FLIP** | Fills sold into the rebound by hand beat random buys of the same coin with the same exit | P1, X-FLIP (rule M), C-RH. Mean Δ_f | **+3.75% per fill** = c_rt + (T-bill − r_res)/f = 1.88% + 4.21%/2.26 (f = P1's 2.26 fills per rung-year). 2.26% (r_res = 3.35%) is a sensitivity | Holm p < 0.05; mean r_f > 0; Δ > 0 in both halves, without the worst month-block and without the biggest episode; Δ > 0 on U-B; Δ > 0 under F3 (s = 1%), also reported under F3d and s = 3% |
| **H2R RESTING** | A resting bid buys more coin per dollar than an alert at the same level followed by a manual buy | P1 fills, a_f against B-ALERT (rule M), C-RH both sides. Mean a_f | **+2% per fill** (carry over P1's median 16-week wait is 1.0-1.3%; the rest stands for the unpriced value of reading the news before buying) | Holm p < 0.05; a > 0 in both halves, without the worst month-block and without the biggest episode; a > 0 on U-B; a > 0 under F3 (s = 1%; single-venue prints would give a_f > 0 by construction) |
| **H4 LEVELS** | At least one chart method beats plain levels at the same depth, in the same wick | Methods j ∈ {M4 (N = 90, 0.5 ATR), M5b, M6, M7 (from 2021-12)}; weekly; U-Q1; X-FLIP. Per method, stack the real level's fills and its four placebos' fills; Δ_f = α_cw + b_j·real_f + c_j·(δ_f − δ_real,cw) + ε_f, with coin-week fixed effects and month-block clusters. Omnibus T = max_j t_j. p_WCR is a Romano-Wolf max-t wild (Webb) bootstrap on month-block score sums; p_G* is 4 × the one-sided t(G* − 1) p of the largest t_j (Bonferroni over the four methods), capped at 1; the §10.2 max rule then applies | **+1% per fill** | Holm p < 0.05; the argmax method's b > 0 in both halves, without the worst month-block and under F3 |

**Verdicts.**
- **PASS:** Holm p < 0.05 and every gate holds.
- **NO EDGE:** the 98.33% upper bound is below E. It is **NO EDGE (HARMS)** when the bound is below 0.
- **INCONCLUSIVE:** neither, reported as "the data cannot tell", with the MDE.

**Expected sample and power.** From the critics' synthetic runs on the real fill calendar; they are re-run under this
machinery in K3 before any outcome (S18).
- **H1:** MDE about 5-6% per fill against E = 3.75%. NO EDGE is reachable if fills are no better than random (39-57%
  of synthetic nulls).
- **H2R:** MDE about 1.2% per fill against E = 2%.
- **H4:** MDE unknown; the proxy lower bound is 1.2-1.9%.
- **An edge that lives only in the 2-3 largest crashes cannot be detected at any size.**

### 10.4 Pre-registered descriptive estimands (no verdict, no p-value; each with estimate, 95% interval, MDE and its fixed sentence)

- **D-H2 OWN.**
  - Per fill: Δ90 against B-TWIN (±182 d) and against B-POST, X-HOLD-90.
  - Quarter-block clusters, under the §10.2 G* rule.
  - The regime caveat sentence (S10) is printed beside it.
- **D-H3 SPEED.**
  - Fast fills (s24 ≥ 0.75) against slow fills (s24 < 0.5) at the same rung, X-FLIP.
  - Primary version with episode fixed effects; the drafted version beside it.
  - s6 and s1 versions as well.
- **D-H5 KNIFE.**
  - knife_f = 1 if the 365th day's VWAP ≤ 0.5·L; a delisting counts at the §4.1 value.
  - Model: knife_f = a + b·notQ_f + rung dummies + γ·p0_f, with p0_f = Φ((ln 0.5 + ½σ_a²)/σ_a) and
    σ_a = σ30·√365.
  - Clusters: two-way, coin × quarter, Student t at min(G_coin, G_q) − 1 df.
  - Sensitivities: Ibragimov-Müller over fill-years; σ30-decile dummies.
  - Rows: U-Q1 vs the rest of U-B, and U-Q1-12 vs its rest.
  - Removal checks: without the coin whose removal lowers b most; delisting haircut at 0% and 100%.
  - Always printed with the caveat of §13.
- **T1 tail table** (absolute; fills and their twins; U-Q1, U-Q1-12, U-B):
  - the share at or below 0.5·L at 365 days;
  - the median and 10th percentile of the lowest price within 30, 90 and 365 days, relative to L;
  - the share delisted;
  - the share of each episode's filled dollars that were 50% or more under water at the worst point;
  - the excess knife rate, fills minus twins, with an episode-cluster interval.
- **D12 recovery curve.** For fills and twins: the share whose price traded at or above R½, and at or above P0,
  within 15 min, 1 h, 4 h, 24 h, 72 h, 7 d and 30 d; and the share first trading a further 10% below L. Split by
  rung, market-wide vs coin-specific, and fast vs slow. Reported before H1's table.
- **D6 break-even.** Per rung k:
  - W_k: the KM restricted mean wait to a first fill over 365 days, as a share of the year;
  - F_k: the probability of a fill within a year;
  - θ_k: the mean P(M(τ_f) + 72 h)/L − 1 minus the twins' mean 72-hour return;
  - **μ*_k = F_k·θ_k / W_k**, the expected excess return over cash a year below which bids at rung k beat buying now.
  - B-MKT per placement is reported beside it, labelled "the sample's drift".
- **D7 accounts.**
  - The P1 flip account: 3 rungs × coins, Q = $10k, one position per rung, carry at r_res = 0 and 3.35%.
  - **D7-OWN:** $m per coin a month added to that coin's bid budget; rungs sized a third each, capped at Q_max; fills
    held (X-OWN; X-ML as a second row); unspent budget earns T-bills.
  - Each on F1 + C-RH and on F3, against B-MIX first, then B-TBILL, B-DCA, B-ALERT-DCA, B-ML-DCA and B-HOLD.
  - CAGR, Sharpe, max drawdown, after-tax (35% short-term, 20% long-term).
  - Stationary block bootstrap on monthly returns, mean block 6 months (12 months as a sensitivity and for the
    gatekept sentence).
  - An account that does not beat B-MIX is reported as "a low-exposure crypto holding with extra steps".
- **D-ML.**
  - B-ML by rung and by MoneyLine state at placement;
  - the fill split by state;
  - the share of fills followed by a red close within 1 and 7 days;
  - P1-G and X-ML.
- **D8 flip vs own,** in two parts: the shared premium (H2R's a_f at 72 h) and the return after 72 h against T-bills.
- **Other descriptive tables:**
  - **D1:** wick frequency and clustering;
  - **D2:** fill mix by life;
  - **D3:** venue gap (F1 against F2, F3, F3d, F4, F5, F6);
  - **D4:** capacity (share of Q filled at $1k, $10k and $100k);
  - **D5:** fill-odds calibration (M3 and the sheet), with episode-bootstrap 90% intervals per half; calibrated if both
    intervals overlap [0.67, 1.5];
  - **D9:** round-number queue test, exchange route only;
  - **D10:** fill odds of chart levels against depth-interpolated placebos. It has its own Holm family: the four H4
    methods plus D9, episode-clustered, used only for the sheet;
  - **D11 luck:** P1's total Δ against the null distribution from K3's synthetic panels. Random-time programs are shown
    only as a level, with no percentile.
- **Concentration (S16).** Every headline reports the share of the total from the three largest episodes, and the
  estimate without them. Above 50%, the sentence names them.
- **Single events.** Every estimate is also shown without 2025-10-10, without 2021-05-19 and without its top
  month-block.

**Sensitivity rows (each changes P1 one way; all reported):**
- lives 1, 30 and 90 days; P1-lazy; P1-G;
- rungs k = 5 and 12; M1; M2a; M3;
- F2, F3 (s = 2, 3, 5%, dwell), F4, F5, F6; X-FLIP-bot; the flip grid;
- costs C-0, C-EX, C-BUS; capacity θ = 0.25; Q = $1k and $100k;
- universes U-B, U-Q1-12, U-Q1-xm, U-A, U-C, U-Q2;
- leave-out drift in place of twins; ±30-day twins; pooled twins;
- cluster variants; placement at 13:30 UTC;
- delisting valuations; the bad-print filter.

**Exploratory splits (BH within each table):**
- the depth gradient over k = 5..12;
- market-wide vs coin-specific fills;
- flow from 2021-12 (open-interest drop, aggressor-sell bursts);
- weekday vs weekend;
- M3, M8;
- the user's coins individually.

### 10.5 Controls (run before any outcome is read; a failed control stops the study)

- **K1 known answer** (V1, R7, S13). Synthetic 1m paths, at least 40 coins over 6.9 years, Student-t(4) market and
  idiosyncratic shocks, volatility regimes.
  - **K1a:** no jumps. **K1b:** market-wide jumps that do not revert, tuned so P1's synthetic fill counts match §6.3's
    real counts within ±25%.
  - **Pass rule:** the engine's mean r_f and mean Δ, before costs, each lie within 2 SE of an oracle computed directly
    from the injected paths by separate code. The oracle is negative in K1b, because gap-through fills sit above the
    following price.
  - **Two engine variants must fail K1b:** one booking fills at the fill minute's close, one at its low.
  - **K1c:** regime-switching drift, with crash intensity 3× higher in bear regimes. Its Δ under X-FLIP and X-HOLD-90 is
    reported as "what regime timing alone produces".
  - **K1d:** synthetic delistings. Fills and twins must take the haircut at equal rates.
- **K2 positive control.** The same market, with each jump split into a permanent half and a transient half that
  reverts with a 30-minute half-life.
  - The engine must report H1's Δ > 0 with t ≥ 3 under rule M and under the bot latency.
  - It must match the oracle within 2 SE.
- **K3 inference** (S7).
  - **Setup:** ≥ 2,000 null replications per scenario on the real fill calendar. Scenarios: base, high dispersion,
    and a heterogeneous-effect null (each episode with a mean-zero effect, SD 3%, Student-t(3)).
  - **Reported:** for H1, H2R and H4, the false-PASS rate at 1.67%, 2.5% and 5%, and the miss rate of the 98.33% NO
    EDGE bound.
  - **Pass:** the upper end of each rate's 95% binomial interval is at most 1.5× nominal.
  - **Otherwise:** that test's p becomes its simulation-calibrated p (the share of null replications, worst scenario,
    whose statistic is at least the observed one), and its NO EDGE bound uses the matching simulated quantile.
  - K3 also re-runs the power study (S18) and gives D11's null distribution.
- **K4 look-ahead.** 50 random cut minutes, never on an hour boundary: at least 10 within 24 h of a placement, 10 in
  fill-day crash hours and 10 on weekends. Prices after the cut × 1.5, volumes and open interest × 0.5.
  - Every universe, level, placement, fill, exit and capacity decision stamped before the cut must be unchanged, for
    every life and F1-F5.
  - **K4b:** delete every bar of the coin after the cut, and separately insert a 3-day gap after the cut. The same
    invariance must hold.
- **K5 fill audit.**
  - Resting orders fill at their limit, in a minute with trades > 0 after their live time, with low ≤ limit − τ (bids)
    or high ≥ limit + τ (sells).
  - Marketable orders fill at the minute's open.
  - A fill price outside the minute's range is allowed only for a resting order in a minute that gapped through it;
    such fills are listed.
  - Any other violation stops the run.
- **K6 capacity check.** C₁ against aggTrades on 200 random fills.
- **K7 ticks and sizes.** Every level is on its venue's tick. Every sheet order is on Robinhood's tick and quantity
  increment, within the minimum and maximum order size; orders above the maximum are split.
- **K8 venue proxy** (no outcome). For every fill: F3 (s = 1% and 3%), F3d and F5; USD conversion; the share removed
  by event.

---

## 11. The answer to the user (fixed now)

The answer is the verdicts of **H2R** (rest vs alert), then **H1** (flip), then **H4** (levels), stated first and
before any table. No descriptive number decides "it works" or "it doesn't".

**Recommendation table (applied in this order; R11):**

| results | what the user is told |
|---|---|
| H2R NO EDGE or HARMS | "Don't leave stink bids resting. If you want to buy after crashes, set price alerts at the sheet's levels and buy by hand after checking the news." (HARMS adds: "resting bids bought into falls that kept going: buying a few hours later was cheaper.") |
| H2R INCONCLUSIVE | "Resting bids and alerts can't be told apart (an edge under about M% wouldn't show). Prefer alerts: your cash stays free and earning." |
| H2R PASS | "Resting bids bought X% more coin per dollar than buying by hand a few hours later (95% CI), over N fills in G months (about G* independent months). Use them only with cash you would otherwise hold in T-bills. Whether waiting beats buying now depends on your expectation: at rung k, waiting pays only if you expect the coin to beat cash by less than μ*_k a year (D6)." |
| H1 PASS (rule M) | "Selling stink-bid fills into the rebound by hand beat random buys of the same coin by X% per fill (95% CI). After Robinhood costs, a flip made R% on average. It held in both halves, without the biggest month and crash, and on Robinhood-like prices." The sheet shows the flip target. If it passes only at bot latency: no target, and "the flip worked only for sell orders placed within a minute of the fill, which you cannot do by hand." |
| H1 NO EDGE | "Flipping stink-bid fills doesn't beat random buys by the 3.75% per fill it would take to cover the round trip and the cash the bids tie up. Don't run the flip version." (HARMS adds: "and the fills did worse than random buys: they tended to come before further falls.") |
| H1 INCONCLUSIVE | "The data can't tell. Deep fills come from about a dozen independent crash months, so an edge would have to be about M% per fill or more to show up, and an edge that lives only in the two or three biggest crashes could not show up at any size. No flip target." |
| H4 PASS | "Method j's levels beat plain volatility-scaled levels at the same depth, in the same wicks, by X% per fill (95% CI). The sheet shows them." |
| H4 NO EDGE | "Chart levels (swing lows, round numbers, volume nodes, liquidation bands) were not better places for a bid than a plain volatility-scaled level at the same depth, by 1% per fill or more." |
| H4 INCONCLUSIVE | "Can't tell; the sheet uses plain volatility-scaled levels." |

**Sentences printed with every answer:**
1. **The discount** (R2): "A bid's discount is not a gain by itself. If prices are unpredictable, a bid 30% below the
   price buys the same expected value as buying now, minus what the coin earns while you wait; in a crash that gaps
   through your price, it buys less. Only a quick rebound after the wick can pay for the wait."
2. **The tail** (R6):
   - "Bids fill together. On the worst day, S% of the live bids in the study's main universe filled the same day. Size
     the whole ladder as one position you are willing to hold through a further 50-80% fall."
   - "A fill is not a bottom: A% of past fills were 50% or more below the fill price a year later, against B% for
     random buys of the same coins."
   - "Coin-specific collapses (LUNA, FTT, OM) look like ordinary wicks on the first day; a resting order cannot read
     the news. Cancel a coin's bids on news about the coin itself (a hack, exploit, depeg, delisting or regulatory
     action)."
3. **MoneyLine** (R5): "Most past fills came when the coin's MoneyLine was already red; a fill buys against your own
   trend signal. Decide before the fill which rule governs the position." With the note that the sheet uses the
   replicated pre-October-2026 MoneyLine.
4. **Capacity:** the size cap and "assume every rung fills on the same day".

**Further rules.**
- **"You could run it on Robinhood"** only if H1 or H2R PASSes, and the D7 account on F3 beats B-MIX with a 12-month
  block-bootstrap 95% interval above zero, and the effect is > 0 on the Robinhood-listed row (U-C, labelled hindsight)
  on F3.
- **"It does not work"** only for NO EDGE; otherwise "not shown" or "the data cannot tell".
- **Wording:** no sentence says "made no difference", "is just" or "works" for a descriptive row. A NO EDGE sentence
  says "not by E or more".
- **A PASS that relies on events F3 removes** is reported as "a Binance-only result".

**Descriptive sentences** (printed with their estimates; S9):
- **D-H2:** "Descriptive only. Over 90 days, coins bought through stink bids did X% (95% CI) better [worse] than the
  same coins bought at random times outside the six months around each fill. An edge under about 20-40% could not be
  detected, and the comparison also reflects whether the crashes fell in bear or bull stretches."
- **D-H3:** "Descriptive only. Fast wicks were X% per fill (95% CI) better [worse] than slow slides to the same depth.
  A difference under about 6-10% per fill could not be detected."
- **D-H5:** "Descriptive only. A year after a fill, X% of fills on large, long-listed coins and Y% on other top-100
  coins were 50% or more below the fill price; at the same volatility the gap was Z points (95% CI). Neither LUNA
  (kept out by listing age) nor FTT (kept out by Binance volume rank) was in the large, long-listed group, so this
  says nothing about fraud collapses of large coins. In the 12-month row, where LUNA is included, the gap was Y'
  points. The study did not test a real-revenue filter." The last clause is dropped only if U-Q2 is built point in
  time.
- **D8:** "Flip or own is a choice about whether you want to hold the coin, not about stink-bid skill. The study's
  evidence on the bid is the same for both."

## 12. Reporting rules

- **Completeness.** Every pre-registered test, row and table is reported, whatever its verdict.
- **Touch fills** (F2) appear only as illusion baselines.
- **Every Binance number appears beside its F3 number.** F5 numbers are labelled "deeper-wick sensitivity: not fills
  this user could get".
- **Survivorship.** U-A and U-C are labelled hindsight. Delisted coins enter at the haircut, with the alternatives
  shown.
- **Uncertainty.** Every interval states its cluster unit, G and G*; every INCONCLUSIVE states its MDE.
- **Deviations.** Any change after results are seen is listed, with the reason.
- **Robinhood fidelity.** No Robinhood crypto history exists here, so every Robinhood-route number is a proxy and says
  so.

## 13. The deliverable: a level sheet (`analysis_2026/stinkbid_sheet.py`)

For each requested coin the sheet prints, and writes to `results_stinkbid/sheet/sheet_YYYY-MM-DD.csv`, these columns
in this order:
1. **Limit price:** the M2 rungs on **Robinhood's tick**, with δ recomputed after rounding.
2. **Depth:** % and σ.
3. **Median weeks to a fill** if re-placed weekly, and the **chance of no fill within a year** (Kaplan-Meier, shrunk
   to the U-Q1 rung).
4. **Robinhood fill odds per week** (F3). The Binance figure is labelled "upper bound". Intervals are widened by the
   overdispersion factor √φ (S14), with "N fills in E episodes".
5. **Capacity:** median and 10th percentile of past seller dollars below the level, and Q_max = 0.25 × the 10th
   percentile (context only on the market-maker route).
6. **MoneyLine now** (replicated); when red: "a fill here buys against your own trend signal".
7. **Large, long-listed flag**, with D-H5's descriptive knife rates.
8. **Shown only when earned:**
   - **flip target R½ and "sell at market after 72 h":** only if H1 PASSes under rule M;
   - **post-fill outcomes:** only for a test that PASSed;
   - **chart levels:** only for a method whose Romano-Wolf adjusted p is below the Holm level at which H4 was
     rejected, or that passes D10's fill-odds family. The latter are labelled "better fill odds at this depth, not a
     better price";
   - **round-number advice:** exchange route only, and only if D9 earns it;
   - **a "best rung":** only if the depth gradient has BH q < 0.10. Otherwise each rung shows its trade-off: wait,
     no-fill chance, θ_k and μ*_k.

**Footer:**
- "Across your whole ladder, expect fills on about N days a year; the longest stretch without any fill was D days; on
  the worst day, S% of the ladder filled."
- Total cash reserved (assume every rung fills on the same day).
- The route note: "on the default route, the coin's mid must fall about 1% below your price before it fills; a chart
  touch is not a fill."
- The fixed sentences of §11.

**Inputs and safeguards:**
- A fresh reference price is required: `--price COIN=x` (the app's mid), or the sheet refuses levels from a close more
  than 24 hours old.
- An order diff against last week's sheet ("cancel X, place Y").
- **HYPE:** the U-Q1 pooled odds at the same depth, with the note: "HYPE: about 17 months of Binance perpetual data
  and 2 months of Binance spot. Its only deep-wick day (2025-10-10) came 13 days before Robinhood listed it. HYPE is a
  venue token: its value depends on Hyperliquid's volume and solvency, a risk no price history here can measure (FTT,
  the token of FTX, fell 97.6%). Not tradable on Robinhood for New York residents."
- The sheet refuses to print prices without the saved Robinhood catalog.
- **The agent never places, previews or cancels orders.** The sheet is a list for the user to enter by hand, in Git
  Bash on Windows. The instructions include a first small test order to confirm Robinhood accepts a deep bid.

## 14. Run order

Each stage refuses to run until the one before it is complete.

1. Data.
2. Controls (K1-K8, including the K3 power re-run).
3. Fill counts per program, written before any return.
4. Primary (H1, H2R, H4).
5. Report (Holm, verdicts, the answer).
6. Descriptive estimands and sensitivity rows.
7. Exploratory splits.
8. The sheet.
9. Audit, then the write-up (report, HANDOFF section, FINDINGS entry).

---

## Revision log (draft ae5425c → frozen)

**Statistics critique (S1-S19).**
- **Adopted:**
  - S1, H2/H3/H5 descriptive; with R1 the family is {H1, H2R, H4};
  - S2, the p-value rule, with the Bonferroni level at 1 − 0.05/3;
  - S3, E_H1 = 3.75%;
  - S4, the same-depth H4 estimator;
  - S5, D-H5's p0 covariate and two-way clusters;
  - S6, D11 from K3;
  - S7, the K3 rule;
  - S8, G*;
  - S9, the wording;
  - S10, twin eligibility and the regime caveat;
  - S11, closed testing for sheet methods;
  - S12, block lengths;
  - S13, K1c and K1d;
  - S14, overdispersion;
  - S15, removing the most supportive coin;
  - S16, top-three-episode concentration;
  - S17, D-H3 with episode fixed effects;
  - S18, power re-run in K3;
  - S19, B-POST.
- **Modified:** S1's two-test family became three tests, because R1's H2R has an MDE of about 1.2% and answers the
  user's own-it decision.

**Fidelity critique (V1-V15).** All adopted:
- V1, the oracle known answer;
- V2, causal segments and K4b;
- V3, the manual clock;
- V4, F3 as measured, with no spot fallback and index outages;
- V5, gap-through fills in K5;
- V6, Monday 03:30 UTC placement;
- V7, per-fill samples not thinned;
- V8, the Robinhood-listed row;
- V9, redenominations and VWAP delisting values;
- V10, the sheet fed by F3;
- V11, the bad-print rule within the fill minute;
- V12, successors inherit age and rank;
- V13, causal capacity;
- V14, F4 from the index and round-number advice for the exchange route only;
- V15, ticks and order sizes.

**Relevance critique (R1-R15).** All adopted:
- R1, B-ALERT and H2R;
- R2, μ*, B-MIX and the discount sentence;
- R3, the manual clock;
- R4, U-Q1 renamed, U-Q1-12, U-Q1-xm and the LUNA/FTT caveat;
- R5, B-ML, D-ML, P1-G, X-ML and the sheet column;
- R6, T1 and the tail sentences;
- R7, the K1b oracle;
- R8, routines, lazy refresh, a fresh price, the order diff and a test order;
- R9, the sheet's units;
- R10, the HYPE note;
- R11, the recommendation table;
- R12, D12;
- R13, D7-OWN;
- R14, the depth trade-off;
- R15, D8 in two parts.

**Changes not proposed by a reviewer.**
- The NO EDGE level 1 − 0.05/3 follows from the three-test family.
- The draft's claim that the quote-asset age fix brings LUNA classic into U-Q1 is deleted; R4 showed it was false.
