# Stink bids: study design (draft for the pre-registration)

Design note for the stink-bid study (brief of 2026-11-18), written 2026-11-18. It turns the user's idea and the three
research notes into a complete, testable design. The orchestrator turns it into `analysis_2026/STINKBID_PREREG.md`,
has it reviewed adversarially, and freezes and commits it before any outcome is computed.

- **Inputs:**
  - [`mechanics.md`](mechanics.md): Robinhood order mechanics, venues, why wicks differ by venue.
  - [`evidence.md`](evidence.md): the literature and the repo's related findings.
  - [`data_inventory.md`](data_inventory.md): the data built under `data/stinkbid/`, with touch counts and clustering.
  - The repo's pre-registration conventions:
    - `analysis_2026/BB_REPLICATION_PREREG.md`;
    - `analysis_2026/SCALPING_PREREG.md`;
    - `MEGACAP_DIP_PREREG.md` on `origin/claude/add-price-data-csvs-MTD46`;
    - the placebo-line design of HANDOFF 5.19.
- **What was computed for this note** (tag **[C]**). Both computations follow the brief's ground rules.
  1. **A fill calendar.** For the candidate programs: which bids would have filled, in which hour, and how fast the
     price got there.
     - Data: Binance hourly spot bars, read only up to and including the fill hour's low.
     - It is a fill frequency. No price after a fill was read, and no post-fill return, P&L or strategy outcome was
       computed on real data.
  2. **A synthetic power simulation.**
     - Real part: the fill calendar's timing and clustering.
     - Synthetic part: every post-fill price path, from an assumed martingale market. No real return enters it.
  - The scratch scripts (`design_sim/fillcal.py`, `fillcal7.py`, `fillsum.py`, `fillsum7.py`, `power.py` in this
    session's scratchpad) will not survive. Their method is in section 12.5 so they can be re-run.
- **Tags:**
  - **[R]** a repo file;
  - **[C]** computed here (fill frequencies or synthetic);
  - **[A] / [S]** primary or secondary web source, as tagged in the sibling notes;
  - **[U]** unverified, inferred or a judgment call;
  - **[D]** a design choice open to the adversarial review.
- **Ground rules followed.** No Robinhood tool was called. Nothing was committed. Only this file was written in the repo.

---

## 0. The design on one page

**The question in testable form.** A stink bid is a resting limit buy far below the price. It fills on two kinds of
selling (`evidence.md` §1):
- forced selling that overshoots and then reverts (good for the bidder);
- informed selling that keeps going (bad for the bidder).

Most such bids never fill, and the fills that happen cluster on a few market-wide crash days. The study asks:
- whether fills are better purchases than buying the same coin at a random time;
- over which horizon;
- at which levels;
- on which coins.

It asks this at fills the user could actually have obtained.

**The primary program, P1** (each element is defined exactly in sections 5-10):

| element | P1 |
|---|---|
| Universe | **U-Q1**: point-in-time "established" coins, i.e. Binance top 100 by volume, at least 2 years listed, median volume rank ≤ 50 over the past 12 months. 28 coins in a median month [C]. |
| Levels | **M2**, volatility-scaled: three rungs at L = P0 · exp(−k·σ30), k = 6, 8, 10. The median depth at placement is 23%, 29% and 35% [C]. |
| Orders | Placed every Monday 00:00 UTC; each lives 7 days, then is cancelled and re-placed. |
| Fills | A trade at least one tick below L on Binance spot 1-minute bars (trade-through), capped by the seller volume that traded below L. |
| Exit | A limit sell at the half-retrace price, L + ½(P0 − L), held for at most 72 hours, then sold at market. |
| Costs | Robinhood's ~0.95% per side. |

Sample size [C]:
- **1,274 fills** in 2020-01..2026-11, i.e. 692, 352 and 230 at k = 6, 8, 10;
- spread over **60 months**, but with the weight of only about **24 equally sized months**;
- 80% of them on market-wide wick days;
- 160 distinct fill days in 91 episodes (fill days at most 3 days apart merged). The 42 episodes in which 5 or more
  coins filled hold 93% of the fills; the effective number of episodes is about 25. **The independent sample is a few
  dozen crash episodes, not 1,274 fills.**
- 88 fills on 2025-10-10 alone.
- These counts exclude the stablecoin PAX, which slipped into the universe and filled 27 bids (section 4.4).

**Five tests in one Holm family** (section 12):

| id | claim | unit | E (economic threshold) | MDE, 80% power [C] | likely verdict |
|---|---|---|---|---|---|
| **H1 FLIP** | Fills sold into the rebound beat random buys of the same coin with the same exit | % per fill | +2% | 4.6-6.1% | INCONCLUSIVE unless the edge is ≥ ~5-6%; NO EDGE if fills are adversely selected |
| **H2 OWN** | Fills held 90 days beat random buys held 90 days | % per fill | +5% | 21-40% | INCONCLUSIVE |
| **H3 SPEED** | At the same σ-depth, fast-wick fills beat slow-decline fills (flip exit) | % per fill | +2% | 7.5-10.6% | INCONCLUSIVE |
| **H4 LEVELS** | A chart-based level beats placebo levels at the same depth (omnibus over 4 methods) | % per fill | +1% | ≥ 1.2-1.9% (proxy) | NO EDGE or INCONCLUSIVE |
| **H5 QUALITY** | Fills on established coins end as knives less often than fills on other top-100 coins | percentage points | 5 pts | 8.4-10.5 pts | INCONCLUSIVE |

- **What the user gets.** A **level sheet** per coin (section 15). It always shows each rung's limit price on
  Robinhood's tick and its historical fill odds, on Binance and adjusted for Robinhood's spread. It shows post-fill
  outcomes, chart levels and flip targets **only for what earned them** in the tests.
- **Before any outcome is read, the design states this:** with deep fills concentrated on a handful of crash days,
  "the data cannot tell" is the most likely answer to every return question. The sheet will then be a tool for
  placing bids with honest fill odds, not a claim that stink bids beat buying.

---

## 1. The user's idea, made precise

### 1.1 What a "stink-bid program" is

A program is a fixed combination of:
- universe U;
- level method M and its parameter (rung);
- placement schedule;
- order life T;
- refresh rule;
- size per order Q;
- fill rule F;
- exit rule X;
- cost scenario C.

For every coin in U at every placement time, M computes a limit price L from data available at that moment. The bid
rests for T, may fill under F, and if it fills, the position is closed by X.

### 1.2 The brief's seven questions, and where the design answers them

| brief question | design element | output |
|---|---|---|
| 1. How often do deep wicks happen, how fast do they revert, are they market-wide? | D1 (frequency, clustering), D2 (fill mix by life), D3 (venue gap); partly done in `data_inventory.md` §4-7 | tables, before any outcome |
| 2. After a fill, what happens against fair benchmarks? | H1 (flip, 72 h), H2 (hold 90 days), descriptive holds of 7, 30 and 365 days; benchmarks in section 11 | verdicts and intervals |
| 3. Which level-finding process works best? | M1-M8 (section 6); H4 against placebo levels; D5 fill-odds calibration | verdict and level-sheet eligibility |
| 4. Flip or own? | H1 against H2, plus the paired exit comparison (D8) | verdicts and interval |
| 5. Does a "solid / real revenue" filter avoid knives? | H5 (U-Q1 filter); U-Q2 (revenue filter, later session) as a secondary row | verdict and interval |
| 6. Would the bids fill for this user? | Fill rules F3 (Robinhood market maker), F4 (exchange route), F6 (Coinbase); capacity caps; outages | gates on every PASS; the sheet's Robinhood fill odds |
| 7. What usable output? | The level sheet (section 15) | tool and instructions |

---

## 2. Priors (stated now)

From [`evidence.md`](evidence.md) §0, §6-7 and the repo's dip studies:

1. **Most deep bids never fill** [C]. P1 fills on 7.1%, 3.6% and 2.4% of bid-weeks at k = 6, 8, 10.
2. **Fills cluster on market-wide days** [C][R]. 80% of P1 fills fell on days when at least 10% of the top 100 coins
   wicked 15% or more below the prior close. More than 90% of deep (≥ 25%) coin-level wicks fall on such days
   (`data_inventory.md` §6.3).
3. **H1 FLIP: a small positive gross effect is possible, the net sign is unclear.**
   - For: fast, high-volume, market-wide drops tend to revert within hours ([Christensen, Oomen and Renò
     2022](https://econpapers.repec.org/RePEc:eee:econom:v:227:y:2022:i:2:p:461-497);
     [Nagel 2012](https://nber.org/papers/w17653)).
   - Against:
     - passive crypto fills were adversely selected in every band tested (repo HANDOFF 5.21);
     - the repo's B3 resting dip bid lost before costs;
     - Robinhood's ~1.9% round trip.
4. **H2 OWN: about zero against random entries.** Evidence: the mega-cap dip study; HANDOFF 5.19; [AQR, "Hold the
   Dip"](https://www.aqr.com/Insights/Research/Alternative-Thinking/Hold-the-Dip) [S]; [K33 after liquidation
   spikes](https://www.theblock.co/post/372115/whats-next-after-cryptos-fourth-largest-long-liquidation-event-of-2025)
   [S]; crypto daily-to-weekly momentum in large coins ([Liu and Tsyvinski](https://papers.ssrn.com/abstract=3226806)
   [U: venue]).
5. **H3 SPEED: positive sign predicted.** Fast, no-news, high-volume drops revert; slow or news-driven ones continue
   ([Savor 2012](https://ideas.repec.org/a/eee/jfinec/v106y2012i3p635-659.html);
   [Chan 2003](https://econpapers.repec.org/RePEc:eee:jfinec:v:70:y:2003:i:2:p:223-260);
   [Cox and Peterson 1994](https://econpapers.repec.org/RePEc:bla:jfinan:v:49:y:1994:i:1:p:255-67)).
6. **H4 LEVELS: no difference after the fill; possibly different fill odds at round numbers and swing lows.**
   Evidence: [Osler 2000](https://www.newyorkfed.org/research/epr/00v06n2/0007osle) (a small effect);
   [Osler 2003](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html); repo 5.19 (no average beat its
   placebo lines); [Urquhart 2017](https://econpapers.repec.org/RePEc:eee:ecolet:v:159:y:2017:i:c:p:145-148) (no
   return pattern after round BTC prices).
7. **H5 QUALITY: lower knife rate with the filter, not zero.**
   - For: repo 5.11 (37% of Binance coin-years fell more than 60%).
   - Against a complete fix:
     - [FTT](https://fortune.com/crypto/2022/11/18/how-ftx-own-token-ftt-was-the-final-nail-in-its-coffin) [S]
       fell 97.6% despite revenue-funded buybacks;
     - [LUNA](https://www.nber.org/papers/w31160) [A] collapsed in three days.
8. **Venue.** Binance spot lows are an upper bound for a Robinhood fill. Binance perpetual lows are deeper still
   (`mechanics.md` §1.6, §3).

---

## 3. Already seen (contamination statement)

No post-fill return, P&L or strategy outcome has been computed on real data. Before the design was written, these
were seen:

- **`data_inventory.md` (fill frequencies and coverage)**, all for bids at fixed % depths below a daily close:
  - touch shares;
  - first-touch timing;
  - market-wide day counts and clustering shares;
  - the list of coin-specific deep wicks, with no closes or later prices;
  - event-day volumes traded at or below 10-40% levels on 13 coin-days;
  - spot against perpetual lows;
  - outage hours.
- **`mechanics.md`:** event-day lows against the open (spot, perpetual, mark, index) on 2021-05-19, 2024-08-05 and
  2025-10-10. Capacity near the low. Round-number lows.
- **`evidence.md`:** published accounts of what followed the named crashes. Examples: the hours-long rebound of
  2025-10-10, and BTC near half its October peak by February 2026. This is public knowledge, so **no exit, depth or
  filter may be justified by these episodes.** Every choice below is justified by the literature or by fill counts.
- **This note [C]:** the fill calendar of P1 and its variants on hourly bars (section 7.4), described only by its
  fill counts. Speed classes use only prices before each fill.

---

## 4. Data

### 4.1 Series

| series | source (path-style S3 URL of the Binance archive, `fetch_scalping_data.S3`) | used for | status |
|---|---|---|---|
| Spot 1d klines, all USDT pairs | `data/spot/monthly/klines/{SYM}/1d/` | universes, σ30, ATR14, P0 | **built** (`data/stinkbid/d1_spot*`) [R] |
| Spot 1h klines, 486 candidates | `.../1h/` | screens, volume profile (M6), counts | **built** (`h1_spot/`) [R] |
| Spot 1m klines | `.../1m/` (monthly zips; daily zips for the current month) | fills, exits, twins (F1, F2) | to fetch (4.2) |
| Spot aggTrades | `data/spot/daily/aggTrades/{SYM}/` | fill capacity; K6 check | to stream on fill days |
| USD-M index price 1m | `data/futures/um/daily/indexPriceKlines/{SYM}/1m/` | F3 (Robinhood market-maker proxy) | to fetch on candidate days |
| USD-M last price 1m | `data/futures/um/daily/klines/{SYM}/1m/` | F5 (perp sensitivity); HYPE before its spot listing | candidate days |
| USD-M 1h last-price and mark-price klines, and `metrics` (5-minute open interest) | `.../um/monthly/klines/`, `.../markPriceKlines/`, `.../um/daily/metrics/{SYM}/` | M7 liquidation bands, from 2021-12 for altcoins (BTC from 2020-09) | to fetch for U-Q1 |
| Coinbase Exchange 1m candles | `api.exchange.coinbase.com/products/{BASE}-USD/candles?granularity=60` (≤ 300 per call) [U: limits] | F6, D3 venue gap | **later session** (blocked here) |
| DefiLlama fees and revenue | `api.llama.fi` summary endpoints [U: exact paths] | U-Q2 revenue filter | **later session** |
| 3-month T-bill | `regime_switch.rf_annual_pct()` (as in the BB study) [R] | carry; benchmarks | in repo |
| Robinhood ticks and sizes | saved read-only `get_currency_pairs` JSON (orchestrator) at `data/stinkbid/ref/currency_pairs.json` | level sheet rounding | orchestrator |

### 4.2 What to fetch, and how big it is

Measured sizes and throughput are from `data_inventory.md` §8 [R]. Sizes for U-Q1 are estimated here [C].

- **1m spot klines, all days.** Fetch for U-Q1 ∪ U-A ∪ U-C:
  - 84 distinct U-Q1 coins (2020-01..2026-11) [C], largely overlapping the 75 coins of U-C;
  - U-C alone is 5.2 GB zipped;
  - the union is estimated at about 8-10 GB zipped [U];
  - store as per-coin parquet: prices float64 (BTC needs 8 significant digits), volumes float32, zstd. The estimate
    is 5-8 GB on disk [U] against 29 GB free.
- **1m spot klines for the rest of U-B** (about 400 coins): stream per coin. Download a coin's 1m zips, run the
  engine on that coin, keep only per-bid and per-fill records, delete. All candidates together are 25.3 GB zipped,
  about 25 minutes at the measured 17-20 MB/s.
- **aggTrades** (stream, reduce, discard):
  - for every coin-day with a fill in U-Q1 (1,510 coin-days for rungs 5-12 [C]);
  - plus a 1-in-10 sample of U-B fill coin-days (5,150 in all [C]) for the K6 check.
  - Each day is reduced to the seller-initiated notional below each active level in the capacity window (section 8.3).
- **Index and perpetual 1m klines.** Only on candidate days: days whose spot 1m low comes within 5% of any active
  bid's L/(1 + s) or L.
- **Command layout.** New subcommands in a new module `analysis_2026/stinkbid_data.py`. It imports
  `fetch_stinkbid_data.py` and `fetch_bb_data.klines` (checksum-verified) and leaves both untouched:
  - `m1 --set q1|a|c|b`
  - `agg-capacity`
  - `index1m`
  - `perp1m`
  - `metrics`
  - `coinbase` (later session)
  - `defillama` (later session)
  - `ages` (listing ages across quote assets, section 5.1)

### 4.3 Windows

- **Placements:** Mondays 2020-01-06 .. 2026-11-09. The data end 2026-11-17, the last complete UTC day.
- **Follow-up needed:**
  - flips: 72 h (fills to 2026-11-14);
  - H2: 90 days (fills to 2026-08-19);
  - H5: 365 days (fills to 2025-11-17).
- **Halves** (every PASS needs both):
  - 2020-01..2022-12 and 2023-01..2026-11. P1 has 534 and 740 fills [C].
  - H5: 2020-01..2022-12 and 2023-01..2025-11.
- **Warm-up:** σ30 needs 25 of the last 30 daily returns inside one series segment. U-Q1 needs 24 months of listing.

### 4.4 Integrity rules (fixed now)

- **Segments.** A missing day, or a jump of more than 25% between a close and the next open with no trading between,
  starts a new segment (`data_inventory.md` §3.2) [R]:
  - no σ window, level look-back, bid life or exit window crosses a segment boundary;
  - a position open at a boundary is closed by the delisting rule below.
- **Ticker reuse.** A reused ticker is a new asset: its listing age restarts at the reuse date.
  - LUNA from 2022-05-31 is Terra 2.0. Here it entered U-Q1 in 2022-08 on the old ticker's age [C], which this rule
    removes.
  - Binance LIT is Litentry, not Robinhood's Lighter (`data_inventory.md` §2.3).
- **Stablecoins.** PAX (USDP) slipped through the inventory's exclusion list and appears in U-Q1 [C]. A 6σ bid on a
  stablecoin is about 0.3% below the price, so PAX filled 27 of its 90 rung-weeks (30 weeks × 3 rungs). The counts in
  this note exclude it. Two fixes:
  - add it to the list;
  - a backstop: exclude any base whose 90-day SD of daily returns is below 0.5% at the start of the month.
- **Outages.** A minute with `trades = 0`, or missing, never fills and never triggers an exit. Exchange-wide Binance
  outages are listed in `data_inventory.md` §3.3.
- **Rebrands and swaps** (list fixed now). A position continues in the successor at the swap ratio:
  - EOS → A; MATIC → POL; FTM → S; RNDR → RENDER;
  - MKR → SKY (1 : 24,000 [U]); AGIX/OCEAN → FET [U: ratios]; BTT → BTTC [U]; LIT → HEI [U].
  - If a ratio cannot be verified from an exchange announcement, the position is treated as delisted.
- **Delistings and collapses.**
  - A position open when a coin stops trading on Binance spot is closed at the last trade × (1 − 0.30). This is
    Shumway's delisting haircut, as in `SCALPING_PREREG.md`.
  - 0% and 100% losses are reported as sensitivities.
  - Twins and benchmarks follow the same rule.
- **Bad prints.** They are real trades and are kept in F1. A sensitivity drops fills whose minute low lies 50% or more
  below both the previous and the next minute's close.

---

## 5. Universes

### 5.1 Definitions (point in time unless labelled)

| id | rule | size [C] | role |
|---|---|---|---|
| **U-B** | Binance top 100 of month M by median daily USDT volume over the 90 days before M (`universe_monthly`), with dead and delisted coins; exclusions as in `data_inventory.md` §2.2 plus 4.4 | 100 a month; 485 coins, 133 of which no longer trade | gate for H1; H5's population |
| **U-Q1** "established" | U-B members of month M with (i) listing age ≥ 24 months at M and (ii) median monthly rank ≤ 50 over M−11..M (unranked months count as 999) | median 28 coins a month (5-36); 84 distinct coins | **primary** for H1-H4 |
| **U-Q2** "real revenue" | U-Q1 members whose DefiLlama protocol or chain had ≥ $10M of revenue in the 365 days before M, using only data dated before M | unknown until the later session | secondary row for H5 and H1 |
| U-A | the 24 user-style coins plus MKR (`data_inventory.md` §2.1) | 24 | **hindsight**, reported, never decides |
| U-C | Robinhood-tradable today (the 75-coin snapshot, refreshed to the 92-pair 2026-11-18 catalog) | 75+ | **hindsight** (survivors); the level sheet's default list |

**Listing age.** Measured from the earliest monthly 1d kline of the base against any of USDT, BTC, BNB, ETH and BUSD,
via one S3 listing per base (new `ages` subcommand).
- The counts here [C] used the USDT pair only. That understates age for coins first listed against BTC, so U-Q1 had
  only 5-6 coins in early 2020.
- With all quote assets, coins such as LINK and LUNA (classic) enter earlier. LUNA classic should then be in U-Q1 before
  May 2022, which makes H5 a harder and fairer test.

**U-Q2 mapping.** The DefiLlama protocol-to-token mapping uses the protocol's `gecko_id` or symbol [U].
- L1 chains use chain revenue.
- The $10M threshold [U][D] was set before any data, low enough for mid-size L1s.
- DefiLlama's own coverage has survivorship [U]. U-Q2 is labelled accordingly and is not the primary filter.

**Which universe decides what [D].**
- **U-Q1 is primary** for H1-H4. It is the closest non-hindsight version of "solid coins I wouldn't mind owning".
- **U-B is a gate for H1:** same sign required.
- **H5 runs inside U-B**, comparing U-Q1 fills with the other top-100 fills.
- **U-A and U-C:** subsets, reported, labelled hindsight.

### 5.2 The user's examples

- **NEAR** is in U-Q1 from 2022-10 [C].
- **HYPE** is not in U-Q1:
  - it has 55 days of Binance spot (from 2026-09-24);
  - its perpetual starts 2025-05-30;
  - on Robinhood since 2025-10-23;
  - halted for New York residents (`mechanics.md` §2).
  - It is reported individually on its perpetual's **index** price, labelled "short history, perpetual-index proxy,
    no verdict". Coinbase data from 2026-02-05 come in the later session.
- **Other user-style coins outside U-Q1** (age or rank): LDO, COMP, MKR/SKY, ENA (in U-Q1 only from 2026-04) and the
  2025-26 listings. They appear only in U-A rows.

---

## 6. Level-finding methods (exact formulas; data at placement only)

### 6.1 Notation (placement at t0 = Monday 00:00 UTC)

| symbol | definition |
|---|---|
| d0 | the last completed UTC day (Sunday) |
| P0 | close of d0 |
| σ | σ30(d0): sample SD of the last 30 daily log close-to-close returns ending d0 (≥ 25 valid, one segment) |
| ATR% | Wilder ATR14 (α = 1/14) of daily true range at d0, divided by P0. Median ATR%/σ = 1.65 (IQR 1.45-1.87) in U-Q1 [C] |
| τ | the tick. In the backtest, Binance's tick inferred from the price grid (GCD of distinct price gaps over the prior 7 days, as in `SCALPING_PREREG.md`). On the level sheet, Robinhood's `min_order_price_increment` |
| ⌊x⌋τ, ⌈x⌉τ | round down or up to the tick |
| δ(L) | ln(P0/L)/σ, the depth in σ units |
| admissible band | chart methods M4-M7 must give δ ∈ [4, 14]; otherwise the method abstains for that coin-week |

### 6.2 The methods

| id | name | formula | parameters (all reported) | role |
|---|---|---|---|---|
| M1 | Fixed % ladder | L = ⌊P0·(1 − d)⌋τ | d = 15, 20, 25, 30, 40, 50% | the naive version |
| **M2** | **Volatility-scaled** | L = ⌊P0·exp(−k·σ)⌋τ | **k = 6, 8, 10 (P1)**; 5 and 12 secondary | **primary; the depth-matched baseline** |
| M2a | ATR-scaled | L = ⌊P0 − k_A·ATR14⌋τ (ATR in price units) | k_A = 4, 5, 6 (about 6.6, 8.3 and 9.9σ at the median ATR%/σ of 1.65) | sensitivity to the volatility measure |
| M3 | Quantile-calibrated to a fill probability p | L = ⌊P0·exp(q̂_p·σ)⌋τ. q̂_p is the p-quantile of z = ln(min low over the life / P_t)/σ_t, pooled over the Monday windows of all eligible Binance USDT pairs (U-B's exclusions) whose lives ended before t0, expanding from 2017-08. The built daily files start 2019-10, so this needs one extra `d1` fetch back to 2017-08 | p = 2, 5, 10% per 7-day life; M3c uses the coin's own history (≥ 104 weeks) | fill-odds calibration (D5); feeds the level sheet |
| M4 | Below the N-day low (stop clusters, Osler 2003/2005) | Lo_N = min(low over d0−N+1..d0); L = ⌊Lo_N·(1 − 0.5·ATR%)⌋τ | N = 30, 90, 365; buffer 0.5 ATR (primary in H4), 1.0 ATR; M4f "in front": ⌊Lo_N·(1 + 0.1·ATR%)⌋τ | H4 |
| M4s | Below a swing (pivot) low | A pivot low is a daily low that is the minimum of the 5 days on each side; it counts only once confirmed, i.e. 5 days old by d0. L = ⌊(the most recent confirmed pivot low with δ ∈ [4, 14]) × (1 − 0.5·ATR%)⌋τ | as stated | sensitivity to M4 |
| M5 | Round numbers | e = ⌊log10 P0⌋, grid g = 10^(e−1), major grid G = 5g (BTC at 95,000: g = 1,000, G = 5,000; NEAR at 2.88: 0.1 and 0.5). L* = P0·exp(−8σ). R = the multiple of G nearest L*; if none lies within ±2σ of L* in depth, the nearest multiple of g. Three placements: **M5f** L = R + τ (ahead of the crowd at R); **M5a** L = R; **M5b** L = ⌊R·(1 − 0.5·ATR%)⌋τ (beyond the stops) | as stated | H4 (M5b); round-number queue test (D9) |
| M6 | Volume-profile node | Over the last 90 days of 1h bars, spread each hour's quote volume uniformly over log-price bins of width 0.25σ between its low and high; smooth with a ±2-bin triangular kernel. High-volume nodes (HVN) are local maxima ≥ 1.5 × the median non-zero bin. L = ⌊lower edge of the highest HVN with δ ∈ [4, 14]⌋τ | as stated | H4 |
| M7 | Estimated long-liquidation band (from 2021-12; BTC from 2020-09) | Over the last 30 days of 5-minute `metrics` rows j: new OI ΔOI⁺_j = max(0, OI_j − OI_{j−1}) (USD), entered at the hour's perp VWAP p_j. Half is assumed long [U]. Leverage λ ∈ {5, 10, 20, 50} with weights {0.35, 0.30, 0.25, 0.10} [U: vendor convention]. Liquidation price p_j·(1 − 1/λ + 0.005). Positions whose liquidation price was crossed by a later 1h mark-price low are removed (Binance liquidates on the mark price, `mechanics.md` §3.1). Histogram on 0.25σ bins, smoothed as M6. L = ⌊(lower edge of the largest peak, ≥ 2 × the median bin, with δ ∈ [4, 14]) × (1 − 0.25·ATR%)⌋τ | as stated | H4; flagged as an estimate (`evidence.md` §3.4) |
| M8 | Crash-depth calibrated (exploratory) | L = ⌊P0·exp(q̃·σ)⌋τ. q̃ is the median standardized low ln(low/prior close)/σ of the coin on past market-wide days (≥ 10% of U-B at −15%), at least 5 of them; else the U-Q1 pooled median | as stated | exploratory |

**Why M2 is primary.**
- **Depth in volatility units** is the unit in which fills are comparable across coins and eras (`evidence.md` §1.2,
  §7). Rungs 6/8/10 sit at a median 23/29/35% below the price at placement [C], the depths the user means by "way
  below".
- **Vol-scaling makes levels deeper after turbulence.** Fills therefore come more often from shocks out of calm
  periods. The median depth of *filled* bids is 20/24/27% [C].

### 6.3 Placebo levels for M4-M7

The design is Osler 2000 and repo 5.19 [R]. For each real level L_M, four placebo levels are placed and run exactly
like L_M: L_M·exp(±0.5·ATR%) and L_M·exp(±1.0·ATR%), about ±0.8σ and ±1.65σ [C].
- **Post-fill comparison:** real-level fills against pooled placebo fills (H4).
- **Fill-odds comparison (D10):**
  - expected rate: a logit of fill on δ fitted to the four placebos, evaluated at the real level's δ;
  - compared with the real level's fill rate.

M2's rungs need no placebo: they are not at chart features and serve as the baseline.

---

## 7. Orders: placement, life, refresh, size

### 7.1 Schedules (each a separate program; all reported)

| life T | placement | refresh | stands for |
|---|---|---|---|
| **7 days (P1)** | Monday 00:00 UTC (Sunday 7 pm EST / 8 pm EDT) | cancel and re-place every Monday at the new level (the queue position is lost) | a manual weekly routine |
| 1 day | 00:00 UTC daily | daily | a bot or a daily routine |
| 30 days | 00:00 UTC every 30 days from 2020-01-06 | at expiry | monthly routine |
| 90 days | every 90 days from 2020-01-06 | at expiry | Robinhood's GTC life, "set and forget" (`mechanics.md` §1.1) |

- **Live time.** A bid is live from t0 + 1 minute. A bid placed in a minute cannot fill in that minute.
- **One position per (coin, method, rung) at a time.** While a rung's position is open, that rung places no new bid.
  It re-arms at the first placement time after the position closes. Other rungs continue.

### 7.2 Size and cash

- **Order size Q per rung:** $1k, **$10k (primary)** and $100k. Quantity = Q/L, rounded down to the quantity
  increment (Robinhood's on the sheet).
- **Per-fill returns are per dollar filled**, so they do not depend on Q. Q enters through the capacity cap
  (section 8.3), the size tables and the account (D7).
- **Cash.** Every bid is fully cash-backed (Robinhood; `mechanics.md` §1.4).
  - Because more than 90% of deep fills are market-wide, a ladder must assume **all rungs on all coins fill on the
    same day**. P1's cash per coin is 3Q.
  - Reserved cash earns r_res = 0% (primary for the carry charge) or 3.35% (Gold sweep). Whether reserved cash keeps
    earning sweep interest is [U] (`mechanics.md` §1.4).

### 7.3 Ladders on the sheet

- The sheet recommends a ladder of the M2 rungs, at most Q_max per rung.
- Q_max is the 10th percentile of the coin's past fill capacity at that rung × 0.25. A bid larger than this would
  likely have been only partly filled in past wicks.

### 7.4 Fill calendar of the candidate programs [C]

**Method.**
- Data: Binance hourly spot bars.
- Fill rule: an hourly low at or below L × (1 − 0.001), a 10-basis-point trade-through proxy.
- A bid's life never crosses into the next placement.
- Counts only. The engine will use 1-minute bars and a one-tick rule, so its counts will differ slightly.

**Weekly life (7 days), by rung:**

| universe | k = 5 | **6** | 6.7 | 7.3 | **8** | 8.7 | 9.3 | **10** | 12 |
|---|---|---|---|---|---|---|---|---|---|
| U-Q1 fills (% of bid-weeks) | 1,076 (11.0) | **692 (7.1)** | 526 (5.4) | 436 (4.5) | **352 (3.6)** | 295 (3.0) | 263 (2.7) | **230 (2.4)** | 153 (1.6) |
| U-Q1 months with a fill (effective number*) | 67 (42.1) | 60 (33.2) | 54 (25.9) | 44 (21.7) | 38 (17.1) | 34 (14.5) | 31 (13.1) | 24 (11.7) | 18 (9.1) |
| U-Q1 distinct fill days | 221 | 146 | 112 | 87 | 69 | 56 | 49 | 40 | 27 |
| U-B fills | 3,727 | 2,387 | 1,806 | 1,475 | 1,215 | 1,017 | 901 | 789 | 515 |
| U-A fills (hindsight) | 432 | 277 | 201 | 164 | 134 | 115 | 103 | 92 | 51 |
| U-C fills (hindsight) | 1,363 | 858 | 632 | 507 | 413 | 344 | 309 | 265 | 168 |

\* Effective number of months = 1/Σw², where w is a month's share of the fills.

- 9,788 bid-weeks per rung in U-Q1; 35,444 in U-B (PAX excluded).
- At the 10 bp proxy, touch-but-not-through fills are rare: 0-13 per U-Q1 rung.

**P1 pooled (U-Q1, k = 6, 8, 10):**
- **1,274 fills**: 534 in 2020-22 and 740 in 2023-26; 854 distinct coin-days; 79 coins.
- **60 months** with fills, but an effective 23.9.
- **Largest months:** 2022-11 (98 fills), 2025-10 (88), 2023-08 (87), 2023-06 (85), 2026-06 (75), 2022-05 (69).
- **Events.** 160 distinct fill days in 91 episodes (fill days at most 3 days apart merged).
  - The 42 episodes with fills in 5 or more coins hold 93% of the fills; 26 episodes have 10 or more coins.
  - The effective number of episodes (1/Σw²) is 25.3.
  - The largest episodes start 2022-11-08 (97 fills, 35 coins), 2025-10-10 (88, 31), 2023-08-15 (87, 31), 2023-06-05
    (85, 30), 2026-06-02 (74, 30), 2022-05-09 (69, 24), 2022-01-21 (65, 24) and 2021-05-19 (62, 25).
  - The deepest rung (k = 10) fills in 27 episodes, 12 of them with 5 or more coins.
- **Named days:** 2020-03-12: 16; 2021-05-19: 55; 2022-05-11: 51; 2022-11-08: 52; 2024-08-05: 12; 2025-10-10: 88.
- **Market-wide share:** 80% of fills (72% at k = 6, 87% at k = 8, 93% at k = 10).
- **Subsets:** 317 fills on U-A coins and 820 on U-C coins (hindsight subsets).
- **Coins that later stopped trading on Binance:** 125 fills. Rebrands: EOS, FTM, MATIC, BTT, RNDR. Delistings: XMR,
  WAVES, OMG, ICX. Section 4.4 rules apply to both.

**The bid's life decides what kind of fill it gets** (U-Q1). This is D2, predicted in `evidence.md` §1.2.

| life | rung | fills | fill rate | fast fills (s24 ≥ 0.75) | slow fills (s24 < 0.5) |
|---|---|---|---|---|---|
| 1 day | k = 8 | 156 | 0.23% of days | 100% (by construction) | 0% |
| **7 days** | k = 8 | 352 | 3.6% of weeks | 54% | 15% |
| 30 days | k = 8 | 414 | 18.4% of months | 33% | 44% |
| 90 days | k = 8 | 283 | 39.5% of quarters | 23% | 64% |

- s24 = ln(H24/L)/ln(P0/L). H24 is the highest price in the 24 hours before the fill.
- A 90-day "set and forget" bid is mostly a slow-decline buyer.
- The weekly program holds both kinds of fill: 54% fast, 17% slow pooled over the three rungs. That makes H3 (the
  slow-dip control) testable inside P1 [D].

---

## 8. Fill model

### 8.1 Fill rules (all reported side by side)

| id | series | a bid at L fills when... | fill price | role |
|---|---|---|---|---|
| **F1** | Binance spot 1m klines | the first live minute m with trades_m > 0 and low_m ≤ L − τ (trade-through by ≥ 1 tick) | L | **primary** (mechanism; most complete and verifiable series) |
| F2 | same | low_m ≤ L (touch) | L | optimistic bound ("illusion" row) |
| **F3** | Binance USD-M **index price** 1m (multi-venue composite); Binance spot where no perpetual exists, labelled | index low_m ≤ L/(1 + s), s = **1%** primary; 2, 3, 5% for crash-time spreads. **F3d** (dwell) needs a whole minute below, i.e. index high_m ≤ L/(1 + s) | L, with the spread embedded | **Robinhood market-maker route** (the app default); a gate on every PASS |
| F4 | Binance spot, F1 rule | as F1, at cost C-EX | L × (1 + 0.50%) | Robinhood exchange route; a labelled proxy for Bitstamp (no Bitstamp data) |
| F5 | Binance USD-M last-price 1m | F1 rule on the perpetual | L | deeper-wick sensitivity. **Never** "would have filled for the user" |
| F6 | Coinbase 1m candles | F1 rule, Coinbase quote increment | L | later session: D3 venue gap; U-C coins listed on Coinbase |

**Why F1 decides and F3 gates [D].**
- F1 uses trades with aggressor flags, which are needed for capacity and are fully checksum-verifiable.
- Binance's index construction is [U] (`mechanics.md` §3.3).
- The F3 gate keeps any PASS from resting on prints that only Binance had, such as ATOM at $0.001 on 2025-10-10
  (`mechanics.md` Table A).

**How much F3 removes (approximate [C]).** At the U-Q1 median σ of 4.3%, s = 1% is about 0.23σ of extra depth and
s = 3% about 0.7σ. Moving a rung 0.7σ deeper cut weekly fills by 16-24% (k = 8 → 8.7: 352 → 295; 6 → 6.7: 692 →
526). So:
- F3 at 1% should remove roughly 5-8% of F1 fills;
- F3 at 3%, about a fifth.

### 8.2 Timing within the minute and the hour

- **Order of events.** Decisions are stamped at minute boundaries. A fill in minute m is stamped at the end of m.
  Orders it triggers (the exit) are live from m + 1. Within a minute the order of low and high is unknown, so nothing
  that depends on it is allowed.
- **Hourly screens.** Where only 1h bars are screened (U-B streaming), every candidate hour is resolved on that day's
  1m bars before any fill is recorded.
- **Outages.**
  - Binance `trades = 0` minutes never fill.
  - F3 and F4 rows also exclude documented Robinhood outage windows, ± 1 hour (`mechanics.md` §1.5): 2021-04-15
    [U: hours], 2021-05-04 (about 1 h), 2025-10-06, 2025-10-20 (≥ 2 h).
  - Fills before a coin's Robinhood listing are flagged in U-C rows. Listing dates other than HYPE's (2025-10-23) are
    [U].

### 8.3 Fill capacity (size cap)

**The rule.** For a fill at L, the capacity window runs from the first trade below L until whichever comes first:
the first later minute whose low is above L, or 60 minutes.

C(L) = Σ price × qty over aggTrades with `is_buyer_maker = True` and price < L, inside the window.

- These sells printed below L. Under price priority, they would have hit a resting bid at L first.
- **Filled dollars** = min(Q, θ·C(L)). θ = 1 is primary; θ = 0.25 is the sensitivity, for competing bids and for the
  wick our own bid would have shortened.
- **Remainder.** Any unfilled part rests at L until expiry and can fill in a later window.
- **1-minute approximation** (streamed U-B coins): C₁ = Σ_m quote_vol_m × (1 − taker_buy_quote_m/quote_vol_m) × f_m,
  with f_m = clip((L − low_m)/(high_m − low_m), 0, 1). K6 checks it against aggTrades.
- **Reported:** the share of Q filled at $1k, $10k and $100k, by rung and coin group.
- **What uses capacity.** Per-fill returns are per dollar filled and do not use it. The account (D7) and the size
  tables do.
- **Benchmark from the inventory.** At every level touched in the three sample crashes, at least $0.45M of
  seller-initiated volume traded at or below it on Binance spot. Within 1% of the 2025-10-10 low, though, only about
  $16-18k of NEAR and AAVE did (`data_inventory.md` §7; `mechanics.md` Table C) [R].

### 8.4 Venue haircut and the venue gap (D3)

For every fill, the report gives:
- whether F3 (index, s = 1% and 3%), F5 (perpetual) and, in the later session, F6 (Coinbase) also fill;
- the share of F1 fills each removes, by rung, coin group and event.

That is the venue haircut. The study does not assume a constant spot-perpetual gap. The gap was 15 points for ETH on
2021-05-19, zero on 2024-08-05 and coin-specific on 2025-10-10 (`mechanics.md` §3.3).

---

## 9. Exits

| id | rule | role |
|---|---|---|
| **X-FLIP** | Limit sell at R½ = ⌈L + ½(P0 − L)⌉τ, live from the minute after the fill. It fills in the first minute with high ≥ R½ + τ (trade-through). Otherwise the position is sold at the open of the first traded minute at fill + 72 h | **primary flip** (H1, H3, H4) |
| Flip grid | targets: L·(1 + g) with g = 5, 10, 20%; L·e^σ and L·e^{2σ}; R½; **X-PRE**, the pre-wick price H24 (the highest price in the 24 hours before the fill, known at the fill); P0 (full retrace to the placement price). Each × time stops 24 h, 72 h and 7 days | sensitivity rows |
| **X-HOLD-h** | sell at the open of the first traded minute at fill + h; **h = 90 days (H2)**; 7, 30, 365 days descriptive | own |
| X-OWN | hold to 2026-11-17, marked at the last close with no sell cost | accumulation tables (D6, D7) |

- **Why half-retrace and 72 h** [D]. The rule ties the target to the bid's own depth, so deeper bids aim higher, as
  bigger overshoots allow. The time stop matches the literature's horizon for reversal after forced selling:
  - minutes to hours for flash crashes;
  - hours, not days, for stop-cascade effects (Osler 2005, [FRBNY SR 150](https://www.newyorkfed.org/research/staff_reports/sr150.html));
  - drift bursts mostly revert (Christensen et al.).

  It was not chosen from any episode's outcome.
- **Route-specific exits.**
  - F3 rows: the sell target fills when the index high ≥ R½/(1 − 0.0095) (Robinhood's bid reaches R½); market sells
    get the index × (1 − 0.0095).
  - F1 rows: fill prices are adjusted by the cost scenario (section 10).
- **Delistings and rebrands** during a hold: section 4.4.

---

## 10. Costs and carry

| id | buy | sell | where |
|---|---|---|---|
| **C-RH (primary)** | +0.95% on every buy | −0.95% on every sell, target or market | Robinhood's ~0.95% per side (HANDOFF §4; `costs.py`) [R]. The same for fills and twins |
| C-EX | +0.50% maker | −0.50% maker on limit targets, −0.95% taker on market sells | Robinhood exchange route, entry tier (`mechanics.md` §1.2) [A] |
| C-0 | 0 | 0 | gross |
| C-BUS | 0% maker | 0.02% taker | Binance.US (not available in New York) [A] |
| (F3) | spread embedded in the fill thresholds | index × (1 − 0.0095) | market-maker route |

**Carry on reserved cash.** Charged in the account (D7), not in per-fill returns: (T-bill − r_res) × reserved dollars
× time, with r_res ∈ {0, 3.35%}.
- At P1's fill rate (4.3% of rung-weeks), a +2% per-fill edge is worth about 52 × 0.043 × 2% ≈ **4.5% a year on
  reserved cash**. That is about the T-bill yield of 4.21% (2026-11-02, [FRED DGS3MO](https://fred.stlouisfed.org/series/dgs3mo)).
- This sets H1's economic threshold (section 12.3).

---

## 11. Benchmarks and controls

### 11.1 Benchmarks

| id | definition | used in |
|---|---|---|
| **B-TWIN** (matched random entries) | For fill f (coin i, minute τ_f, exit X), draw R = 100 entry minutes uniformly from coin i's eligible minutes. Eligible means: (a) the coin was in the program's universe that month; (b) outside [τ_f − 182 d, τ_f + 182 d], the leave-out window of HANDOFF 5.19 and the BB study; (c) a complete exit window. Each twin enters at that minute's open (plus cost) and exits by X with the same **relative** target ln(R½/L) and the same time stop or hold, on the same route and cost scenario as the fill (F1 + C-RH, or F3 with the spread embedded). r̄_twin,f is the mean over the R twins. If fewer than 182 eligible days remain, twins come from all U-Q1 coins' eligible minutes in the same calendar year, labelled "pooled twins". Seed: `numpy.random.default_rng(20261118 + fill index)` | H1, H2, H3, H4 |
| B-SLOW (slow-dip control) | P1 fills with s24 < 0.5 against fills with s24 ≥ 0.75, at the same rung | H3 |
| B-MKT | Buy at market at t0 + 1 min, hold to the same horizon. Compared **per placement, not per fill**: conditioning on a fill makes the bid look better by construction, since L < P0 | D6 "cost of waiting" |
| B-TBILL | Cash at the 3-month T-bill | D7, carry |
| B-DCA | Weekly buys of the same total capital spread over the same period, same coins | D7 |
| B-HOLD | Equal-weight buy-and-hold of the universe's coins, each joining when eligible, delisted at the haircut | D7 |
| Leave-out drift | r_f − μ̂_i × holding time. μ̂_i is coin i's mean hourly return outside the fill's ±182 days (BB convention) | sensitivity beside B-TWIN |

**Why twins, not a drift subtraction, are primary.**
- Flip exits are non-linear (target or time stop). A twin applies the identical rule from a random start, so its mean
  is "what this exit earns on this coin at an ordinary moment".
- Δ_f = r_f − r̄_twin,f then measures only the value of entering at the fill.
- This is the "timing vs owning" design of the mega-cap study's placebo [R].
- Twins at random times are also the **luck benchmark**. The report gives P1's total Δ against 1,000 random-time
  programs, each replacing every fill by one of its twins.

### 11.2 Controls (run before any outcome is read; a failed control stops the study)

- **K1 Martingale known answer**, in two versions: **K1a** without jumps, and **K1b** with market-wide jumps that do
  not revert.
  - Data: synthetic 1-minute paths for ≥ 40 coins over 6.9 years:
    - market and idiosyncratic Student-t(4) shocks;
    - volatility regimes;
    - in K1b, jumps whose rate and size are tuned so that P1's synthetic fill counts per rung match section 7.4's
      real counts within ±25%;
    - zero arithmetic drift.
  - Pass if, over ≥ 20,000 fills, both of these are within 2 SE of 0 before costs:
    - P1's mean Δ (fill minus twin);
    - the mean fill return r_f itself.
  - After C-RH they are about 0 and −1.9%.
- **K2 Positive control.** The same market, with each market-wide jump split into a permanent half and a transient
  half that reverts with a 30-minute half-life.
  - The engine must report H1's Δ > 0 with t ≥ 3.
  - The mean must match, within 2 SE, the value computed directly from the injected paths without the engine.
- **K3 Inference control.**
  - Data: 200 synthetic panels on the real fill calendar with no true effect (section 12.5 is the template).
  - Pass if each of H1-H5's tests rejects at most 10 of 200 at a nominal one-sided 5%, and each NO EDGE bound misses
    the true value at most 5% of the time at the 95% level.
  - Otherwise the level is widened until it does, and the NO EDGE level is widened by the same factor (BB Addendum 2).
  - Expected [C]: the clustered t was slightly liberal in the simulation, rejecting 6.0-6.8% (H1), 6.5-7.0% (H4) and
    up to 8% (H5, high-dispersion scenario), so widening is likely.
- **K4 Look-ahead perturbation.**
  - 50 random cut minutes t, never on an hour boundary. At least 10 within 24 h of a Monday placement, 10 inside
    fill-day crash hours, 10 on weekends.
  - Every price after t × 1.5; every volume and open interest after t × 0.5.
  - Every level (M1-M8), universe membership, placement, fill and exit decision stamped before t must be unchanged,
    for every life and F1-F5.
  - The capacity window is exempt by design. It measures size after the fill and does not decide any order.
- **K5 Fill audit.** Every fill and exit price lies within [low, high] of its minute, after the order's live time,
  never in a `trades = 0` minute. Any violation stops the run.
- **K6 Capacity check.** On 200 random fills, the 1-minute capacity approximation against aggTrades. The ratio is
  reported. U-Q1 uses aggTrades throughout.
- **K7 Tick and rounding.** Every level is on its venue's tick. Sheet prices are on Robinhood's tick.
- **K8 Venue proxy (no outcome).** On 2021-05-19, 2024-08-05 and 2025-10-10, F3's fill decisions are compared with
  F1's and F5's. The share removed is reported (D3).

---

## 12. Hypotheses, statistics and verdicts

### 12.1 Units and statistics

- **Per-fill net return:**

  r_f = [exit price × (1 − c_s)] / [L × (1 + c_b)] − 1

  with c from the cost scenario.
- **Per-fill excess:** Δ_f = r_f − r̄_twin,f. Twins pay the same costs, so Δ is net of costs on both sides.
- **Weights.** Each fill counts once, whatever its size. Size-weighted (by filled dollars at Q = $10k) is a
  sensitivity.
- **Clusters (CR1, small-sample factor G/(G − 1), Student t at G − 1 df, one-sided):**
  - the calendar month of the fill for 72-hour outcomes (H1, H3, H4);
  - the calendar quarter for 90- and 365-day outcomes (H2, H5), whose holding windows overlap across months.
  - Sensitivities:
    - event-episode clusters (fill days merged when 3 days apart or less);
    - week clusters;
    - two-way coin × month.
- **NO EDGE bounds.** One-sided upper bound at 1 − 0.05/5 = 99%, from a cluster bootstrap-t with 9,999 draws, widened
  if K3 requires.
- **Bootstrap p-values:** (1 + #{b : θ*_b − θ̂ ≥ θ̂}) / (B + 1).
- **MDE.** (t_{1−0.05/5, G−1} + t_{0.80, G−1}) × SE, using the SE that decides the test. Reported with:
  - the point estimate;
  - its two-sided 95% interval;
  - the largest effect ruled out at 95%.

### 12.2 Multiplicity

- **One Holm family of five one-sided tests, at 5%:** H1 FLIP, H2 OWN, H3 SPEED, H4 LEVELS, H5 QUALITY.
  - Holm runs on all five p-values whatever their other conditions.
  - The other PASS conditions are gates, not p-values.
- **Everything else is descriptive or exploratory:** the exit comparison (D8), the sensitivity rows, U-A, U-C, U-Q2,
  per-coin results and the D-tables.
  - Any p-value shown for them is labelled exploratory and Benjamini-Hochberg adjusted within its table.
- **Why the exit comparison is not in the family [D].** Flip − hold-90 has an MDE of 21-40% per fill [C]. It cannot
  decide anything, and in the family it would only dilute the other tests.

### 12.3 The tests

| id | claim (as the claim that the idea helps) | program, unit, statistic | E | PASS requires (all) |
|---|---|---|---|---|
| **H1 FLIP** | Stink-bid fills sold into the rebound beat random buys of the same coin with the same exit | P1 with X-FLIP. Unit: fill. Mean Δ_f (C-RH), month clusters | **+2% per fill**: below it the edge does not pay the T-bill yield on the reserved cash (section 10) | Holm p < 0.05. The mean of r_f itself > 0 (the flips make money, not just lose less than random buys). Δ > 0 in both halves. Δ > 0 without the month whose removal lowers it most, and without the biggest event (the episode with the most fills). Δ > 0 on U-B (same program). Δ > 0 under F3 (index, s = 1%) |
| **H2 OWN** | Fills held 90 days beat random buys of the same coin held 90 days (timing vs owning) | P1 with X-HOLD-90. Mean Δ90_f, quarter clusters | **+5% per fill per 90 days** [D][U]. At P1's fill rate a rung waits a median of about 16 weeks for a fill [C], and the T-bill carry over that wait is about 1.3%. A smaller purchase-price advantage is not worth the delay, before even counting the coin's own expected return while waiting (unknown, and not assumed) | Holm p < 0.05. Δ > 0 in both halves, without the worst quarter, without the biggest event, on U-B and under F3 |
| **H3 SPEED** (slow-dip control) | At the same depth, fast-wick fills beat slow-decline fills | P1 fast (s24 ≥ 0.75) and slow (s24 < 0.5) fills, X-FLIP. Coefficient b in Δ_f = a + b·fast_f + rung dummies; month clusters | **+2% per fill** | Holm p < 0.05. b > 0 in both halves and without the worst month. b > 0 with s6 and s1 (6-hour and 1-hour speed) in place of s24. Fast fills' mean Δ > 0 |
| **H4 LEVELS** (omnibus) | At least one chart method beats its placebo levels at the same depth | Methods j ∈ {M4 (N = 90, 0.5 ATR), M5b, M6, M7 (from 2021-12)}, weekly life, one level per coin-week, X-FLIP, U-Q1. Per method: b_j = mean Δ(real fills) − mean Δ(placebo fills), from a stacked regression with month clusters. Omnibus T = max_j t_j; p from a month-block bootstrap of the recentred max-t (9,999 draws; White / Romano-Wolf) | **+1% per fill** | Holm p < 0.05. The argmax method's b > 0 in both halves, without the worst month and under F3. **NO EDGE:** every method's upper bound (max-t critical value at 99%) < E |
| **H5 QUALITY** | Fills on established coins (U-Q1) end as knives less often than fills on the other top-100 coins at the same depth | P1's rules on U-B. knife_f = 1 if the price 365 days after the fill ≤ 0.5·L (a delisting counts at last trade × 0.7). Coefficient b on "not U-Q1" in knife_f = a + b·notQ_f + rung dummies + σ30-tercile dummies (terciles of σ30 among that year's U-B placements); quarter clusters | **5 percentage points** | Holm p < 0.05. b > 0 in both halves (fills to 2025-11) and without the worst quarter. b > 0 with LUNA (2022-05) and FTT (2022-11) fills removed. b > 0 with the delisting haircut at 0% and at 100% |

**Verdicts** (as in the BB and scalping studies):
- **PASS:** Holm-adjusted p < 0.05 and every other condition holds.
- **NO EDGE:** the one-sided upper bound at 99% (widened if K3 requires) is below E. **NO EDGE (HARMS)** when the
  bound is below 0.
- **INCONCLUSIVE:** neither. It is reported as "the data cannot tell", with the MDE.

**Why the σ30-tercile control in H5.** At the same σ-depth, a coin that is more volatile is more likely to fall a
further 50% within a year for reasons of volatility alone. For a driftless lognormal, the chance is 18% at 57% annual
volatility and 40% at 96% [C: arithmetic]. The control keeps H5 about collapse risk, not volatility. The uncontrolled
difference is reported beside it.

### 12.4 Halves, single events and selection (applies to every PASS and every headline)

- **Without single events.**
  - Every estimate is also reported without 2025-10-10, without 2021-05-19 and without its largest month.
  - The share of the total Δ from the top month and from the top 5% of fills is reported.
  - The "without the worst month" and "without the biggest event" conditions are part of every PASS. A result that
    needs one month or one crash is not a PASS.
- **Collapses.** Results are reported with and without the single largest collapse in the fill set (LUNA 2022-05;
  FTT 2022-11).
- **Hindsight subsets.** Results on U-A and U-C are labelled hindsight and never decide.

### 12.5 Power: the synthetic simulation [C]

**Method** (scratch script `power.py`; re-runnable from this description):

*Real part:* the P1 fill calendar of section 7.4, i.e. coin, rung, fill hour, P0, L and s24 for 1,274 fills (1,244
with a 90-day follow-up). Plus:
- placebo rungs k = 6.7, 7.3, 8.7, 9.3 around k = 8, as the H4 proxy: 1,872 fills, 352 of them at k = 8;
- U-B fills at k = 6, 8, 10 with a 365-day follow-up for H5: 3,919 fills, 1,069 of them in U-Q1.

Nothing after any fill was read.

*Synthetic part:* hourly log prices from a martingale market:
- Shocks: market + idiosyncratic, Student-t(4) scaled to unit variance.
- Volatility:
  - market daily vol 3.0%, β 1.1, idiosyncratic 3.0% (total about 4.5%, pairwise correlation about 0.55);
  - a log-AR(1) regime (φ 0.98, SD of log vol 0.45);
  - a post-crash multiplier of 2.0× for 3 days after each of the 92 calendar days with at least 10 U-B fills at
    rungs 6-12 (each rung counted).
- Intra-hour highs: from the Brownian-bridge maximum.
- Drift: zero arithmetic drift.

A **high-dispersion scenario** raises idiosyncratic vol to 4.5% and the post-crash multiplier to 3.0× for 7 days.

Fills, X-FLIP exits (half-retrace, 72 h), 90-day holds and 20 twins per fill (same coin, ±182 days excluded) run on
the synthetic paths. H5 uses 365-day outcomes with an 8% chance of collapse (a −90% jump), the same for both groups.

Runs: 400 replications (base) and 200 (high dispersion). The MDE is computed at α/5 with Student t at G − 1 df.

**Results:**

| test | clusters G | SE (base … high) | MDE at α/5, 80% power (one-sided 5% in brackets) | empirical size of nominal 5% |
|---|---|---|---|---|
| H1 FLIP | 60 months | 1.41-1.47% … 1.72-1.88% per fill | **4.6-4.8% … 5.6-6.1%** (3.6-3.7 … 4.3-4.7%) | 6.8% … 6.0% |
| H2 OWN | 26 quarters | 6.4-8.2% … 9.8-11.9% | **21-27% … 33-40%** per 90 days | 1.0% … 1.0% (conservative) |
| H3 SPEED | 57 months | 2.3-2.7% … 2.9-3.3% | **7.5-8.6% … 9.5-10.6%** | 5.2% … 6.0% |
| H4 LEVELS (proxy) | 54 months | 0.37-0.39% … 0.59% | **1.2-1.3% … 1.9%** | 6.5% … 7.0% |
| H5 QUALITY | 24 quarters | 2.5-3.1 … 2.6-3.1 pts | **8.4-10.5 … 8.7-10.5 pts** | 4.2% … 8.0% |
| D8 exit (flip − hold 90) | 26 quarters | 6.1-7.9% … 9.6-11.5% | 20-26% … 32-38% | 6.5% … 3.5% |

The two SE values per scenario are the SD of the estimate across replications and the mean clustered SE.

**H1 power at a true constant edge** (base … high, at α/6, slightly conservative for five tests):
- 21% … 13% at +2% (= E);
- 62% … 44% at +4%;
- 91% … 75% at +6%;
- 98% … 93% at +8%.

At an edge equal to the MDE, the chance of meeting **every** H1 PASS condition (Holm p, both halves, without the
worst month) was 76-78%.

**Reading.**
- **H1** can detect only an edge of about 5-6% per fill or more. That is plausible only if fast, deep fills recover a
  large share of their overshoot within 72 hours. If the true edge is near E = 2%, H1 will almost surely be
  INCONCLUSIVE. **NO EDGE** needs an estimate below about −1.5% to −2.5% (the 99% bound sits 3.5-4.5 points above the
  estimate), i.e. clearly adversely selected fills.
- **H2 and the exit comparison can detect only huge effects.** They are kept because they answer the user's "own it"
  question. The answer will almost surely be "the data cannot tell", and the report must say so first.
- **H4's proxy is a lower bound on its MDE.** Adjacent placebo rungs fill on almost the same events. Chart levels
  will overlap their placebos less, so the real MDE will be larger [U].
- **Expect K3 to widen** H1's and H4's levels, and possibly H3's and H5's. The clustered t rejected up to 1-3 points
  more often than its nominal 5% in the simulation.
- **Caveats.** All of this assumes the synthetic parameters. Real post-crash dispersion may be larger; the high
  scenario brackets this [U].

### 12.6 What the user is told under each outcome (fixed now)

The answer to "does the stink-bid idea work?" is the verdict of **H1 (flip)** and then **H2 (own)**, stated first and
before any table. No descriptive number decides "it works" or "it doesn't". Examples: a fill rate, one coin, one
crash, the account multiple.

| test | PASS | NO EDGE | INCONCLUSIVE |
|---|---|---|---|
| H1 | "Selling stink-bid fills into the rebound beat buying the same coins at random times by X% per fill (95% CI), after Robinhood costs, over N fills in G months. It held in both halves, without the biggest month and crash, and on Robinhood-like prices. The sheet shows the flip target." | "Flipping stink-bid fills doesn't beat random buys by the 2% per fill it would take to pay for the cash it ties up. Don't run the flip version." (HARMS: "...and it loses: fills come before further falls.") | "The data can't tell. An edge would have to be about 5% per fill or more to show up, because deep fills come from a handful of crash days." |
| H2 | "Coins bought through stink bids did better over the next 90 days than the same coins bought at random times, by X%." | "Stink bids don't buy better than random times by 5% or more over 90 days: owning through stink bids is just owning, later." | "The data can't tell: 90-day crypto returns vary too much (an edge under about 20-40% wouldn't show)." |
| H3 | "Fast wicks were better fills than slow slides to the same depth: prefer short-lived bids (weekly or daily) over 90-day set-and-forget orders." | "How fast the price got there made no difference." | "Can't tell whether fast wicks are better than slow slides." |
| H4 | "Method j's levels beat a plain level at the same depth by X% per fill; the sheet shows them." | "Chart levels (swing lows, round numbers, volume nodes, liquidation bands) are no better places for a bid than a plain volatility-scaled level at the same depth." | "Can't tell; the sheet uses plain volatility-scaled levels." |
| H5 | "Sticking to established coins cut the share of fills that were down 50%+ a year later by X points (at the same depth and volatility)." | "The established-coin filter didn't cut knife-catching by 5 points or more." | "Can't tell whether the filter cuts knife-catching." |

**Further sentences:**
- **"You could run it on Robinhood"** only if H1 or H2 is PASS **and** the P1 account on the F3 route beats T-bills
  after 35% short-term tax, with a 95% month-block-bootstrap interval above zero (D7).
- **"It does not work"** only for NO EDGE. Otherwise "not shown" or "the data cannot tell".
- **Single events.** If a PASS relies on events the F3 route removes, it is reported as "a Binance-only result".

---

## 13. Descriptive and exploratory analyses (decide nothing)

| id | content |
|---|---|
| D1 | Wick frequency and clustering in σ units and %, by coin group and year; the share on market-wide days; event episodes. Extends `data_inventory.md` §4-6 to M2 rungs and 1m bars |
| D2 | Fill mix by life (1/7/30/90 days): fast, middle and slow shares (section 7.4) |
| D3 | Venue gap: F1 against F2, F3 (s = 1-5%, dwell), F4, F5 and F6 (later session), by event and coin group |
| D4 | Capacity: the share of Q filled at $1k, $10k and $100k; the distribution of C(L) at each rung |
| D5 | Fill-odds calibration. Walk-forward by year: M3's target p against the realized fill rate, and the sheet's shrunken per-coin estimate against realized, in each half. "Calibrated" means realized/predicted within [0.67, 1.5] in both halves |
| D6 | Cost of waiting: per placement, "bid; if filled hold to t0 + 365 days, else T-bills" against B-MKT, with an interval. This is mostly the sample's drift, so it is labelled as such |
| D7 | Accounts: P1 accounts (3 rungs × coins, Q = $10k, carry at r_res = 0% and 3.35%), on F1 + C-RH and on F3, against B-TBILL, B-HOLD and B-DCA. Reported: CAGR, Sharpe, max drawdown, after-tax (35% short-term, 20% long-term), with month-block bootstrap intervals |
| D8 | Exit comparison: Δ_flip − Δ_hold90 per fill, plus the flip grid and the holds of 7, 30 and 365 days, quarter clusters |
| D9 | Round-number queue test: fill rate of M5f (R + τ) − M5a (R), against the same one-tick difference at non-round prices (a difference-in-differences). It decides only the sheet's advice "bid one tick above round numbers" |
| D10 | Fill odds of chart levels against their depth-interpolated placebos (section 6.3) |
| D11 | Luck: P1's total Δ against 1,000 random-time programs (section 11.1) |

**Sensitivity rows** (each changes P1 in one way; all reported):
- life 1, 30 and 90 days;
- rungs k = 5 and 12, and M1's fixed %;
- F2, F3 (s = 2, 3, 5%; dwell), F4, F5, F6;
- costs C-0, C-EX, C-BUS;
- capacity θ = 0.25; Q = $1k and $100k;
- universes U-B, U-A, U-C, U-Q2;
- leave-out drift in place of twins; ±30-day twin exclusion; pooled twins;
- the cluster variants of 12.1;
- placement on Thursday 12:00 UTC (a day-of-week check);
- delisting haircut 0% and 100%;
- the bad-print filter.

**Exploratory splits** (BH within each table):
- depth gradient over k = 5..12 (dose-response);
- breadth: market-wide fills against coin-specific ones;
- flow (from 2021-12): the open-interest drop in the fill hour, and seller-initiated volume bursts from aggTrades;
- weekday against weekend;
- M3 and M8;
- the user's coins individually (HYPE on its perpetual index), listed fill by fill with no verdict.

---

## 14. Reporting rules

- **Completeness.** Every pre-registered test, row and table is reported, whatever its verdict.
- **Touch fills** (F2) are reported only as illusion baselines, never as results.
- **Venue.** Every Binance number appears next to its F3 (Robinhood market-maker proxy) number.
  - Binance perpetual (F5) numbers are labelled "deeper-wick sensitivity: not fills this user could get".
- **Survivorship.**
  - Inference uses U-Q1 and U-B with dead coins.
  - U-A and U-C are labelled hindsight.
  - Delisted coins enter at the haircut, with 0% and 100% shown.
  - Rebrands follow section 4.4.
- **Single-event dependence.** For each test and headline:
  - without 2025-10-10;
  - without 2021-05-19;
  - without its top month;
  - the top month's share of the total.
- **Uncertainty.** Every interval states its cluster unit and G. Every INCONCLUSIVE states its MDE.
- **Deviations.** Any change after results are seen is listed, with the reason.
- **Robinhood fidelity.** No Robinhood crypto history exists here (`mechanics.md` §1.6). Every Robinhood-route number
  is a proxy and says so.

---

## 15. The deliverable: a level sheet

### 15.1 What it is

A new module, `analysis_2026/stinkbid_sheet.py`. For each requested coin it prints, and writes to
`analysis_2026/results_stinkbid/sheet/sheet_YYYY-MM-DD.csv`:

| column | content | shown when |
|---|---|---|
| coin, as of, P0, σ30 | the reference price (latest daily close, or `--price COIN=x` for the live Robinhood mid) and volatility | always |
| rung | M2 k = 6, 8, 10 (and M3's p = 2, 5, 10% if D5 calibrated) | always |
| limit price | ⌊P0·e^{−kσ}⌋ on **Robinhood's tick** | always |
| depth | % below P0 and in σ | always |
| fill odds, 7-day bid | shrunken estimate (n_fill + 52·p_pool)/(n_bids + 52), with p_pool the U-Q1 rate at that rung; a Wilson 95% interval; "from N fills in G months" | always |
| fill odds, Robinhood | the same under F3 (the mid must reach L/1.01) | always |
| fill odds, 90-day bid | the same for the 90-day life | always |
| capacity | median and 10th percentile of past seller dollars below the level; suggested max size Q_max (section 7.3) | always |
| flip target | R½ = ⌈L + ½(P0 − L)⌉ on Robinhood's tick, and "sell at market after 72 h" | **only if H1 PASS** (else "no proven edge from flipping") |
| post-fill outcome | Δ for the flip (H1) and 90-day hold (H2): median and 10-90% range, with N and G | **only for a test that PASSed**; otherwise the verdict sentence of 12.6 |
| chart levels | M4-M7 rows | **only for a method that beat its placebo**: H4 PASS with that method's BH q < 0.10, or D10's fill-odds advantage with a 95% interval above zero (then labelled "better fill odds at this depth", not "better price") |
| round-number advice | "move the bid one tick above R" | only if D9's interval is above zero |
| quality flag | "not an established coin by the study's rule" for coins outside U-Q1; H5's figure if PASS | always |
| footer | total cash reserved (3 rungs × size × coins); "assume every rung fills on the same day"; the route note | always |

**Data for the sheet:**
- Binance archive daily and hourly bars for the requested coins. The sheet refreshes them itself, incrementally,
  through `fetch_stinkbid_data`'s functions. The archive lags one day.
- HYPE uses its perpetual's index price until Binance spot (2026-09-24) and Coinbase (later session) give enough
  history; it is labelled.
- Robinhood ticks come from `data/stinkbid/ref/currency_pairs.json`, saved read-only by the orchestrator. Without it,
  the sheet refuses to print prices, rather than guessing a tick.

### 15.2 How the user would use it on Robinhood (manual orders only)

From the repo folder, in Git Bash on Windows. Use `py -3` in place of `python` if `python` is not on the PATH [U].

```bash
cd ~/moneyline-upgrade            # wherever the repo lives
git pull
# weekly, after Monday 00:00 UTC (Sunday 7 pm EST / 8 pm EDT):
python -m analysis_2026.stinkbid_sheet --coins HYPE,NEAR,SOL,AAVE,LINK --life 7 --per-rung 1000 --route mm
# optional: pass today's Robinhood mid prices so levels are measured from them (example values; use the app's mid)
python -m analysis_2026.stinkbid_sheet --coins NEAR,SOL --price NEAR=2.41 --price SOL=148.2 --life 7 --per-rung 1000
cat "analysis_2026/results_stinkbid/sheet/sheet_$(date -u +%F).csv"
```

**In the Robinhood app, for each row:**
1. Coin → Trade → Buy → Order type **Limit**. Limit price = the sheet's price. Quantity or dollars = at most the
   size shown. Robinhood crypto limit orders are good-till-cancelled for 90 days (`mechanics.md` §1.1).
2. **Route.**
   - Default (market maker): the coin's mid must fall about 1% *below* your price before it fills. The sheet's
     "Robinhood fill odds" already account for this. A chart that "touched" your price did not fill you.
   - Exchange routing (where offered): the order rests on Bitstamp's book only, at a 0.50% maker fee.
3. **Weekly routine** (P1).
   - Each Sunday evening, cancel unfilled stink bids and re-enter the new sheet's prices.
   - Set-and-forget 90-day bids are the 90-day life row. They mostly fill on slow declines (section 7.4).
4. **After a fill.** If the sheet shows a flip target (H1 PASS), enter a limit sell at that price and set a reminder
   to sell at market after 72 hours. Otherwise hold per your own plan; the sheet makes no claim.
5. **Cash.** Keep enough cash for every bid at once. Fills come on the same crash day across coins.
6. **New York residents** cannot trade HYPE on Robinhood.

**Rules for the agent.** The agent never places, previews or cancels these orders. The sheet is a list for the user
to enter by hand (brief).

---

## 16. Build plan and run order

| module (new) | content |
|---|---|
| `stinkbid_data.py` | the fetch subcommands of 4.2 (1m, aggTrades capacity, index, perpetual, metrics, ages; Coinbase and DefiLlama in the later session) |
| `stinkbid_levels.py` | M1-M8 and placebos; tick inference |
| `stinkbid_engine.py` | bids, F1-F6 fills, capacity, exits, twins, accounts |
| `stinkbid_stats.py` | clustered tests, bootstrap-t, max-t, Holm, verdicts |
| `stinkbid_controls.py` | K1-K8 |
| `stinkbid_run.py` | CLI stages, each refusing to run until the previous one is complete |
| `stinkbid_sheet.py` | the deliverable |

- **Results:** `analysis_2026/results_stinkbid/`. The pre-registration is `analysis_2026/STINKBID_PREREG.md`.
- **Run order:**
  1. data;
  2. controls (K1-K8);
  3. fill counts per program, written before any return;
  4. primary (H1-H5);
  5. report (Holm, verdicts, answer map);
  6. descriptive and sensitivity;
  7. exploratory;
  8. sheet;
  9. audit, then the write-up (report, HANDOFF section, FINDINGS entry).
- **Time** [U]:
  - 1m fetch for the primary set: about 10 minutes;
  - U-B streaming: about 25 minutes;
  - aggTrades capacity: about 20-25 minutes (BTC and ETH days are large);
  - engine: dominated by twins (127k twin paths for P1).

---

## 17. Not testable here, and decisions for the review

**Not testable with reachable data:**
- Robinhood's own past quotes (no crypto history in the MCP);
- Bitstamp's book;
- queue position at a price;
- Hyperliquid (restricted for US persons; not an option);
- HYPE ETF fills in equity sessions (THYP, BHYP: no intraday data here; most crypto wicks are out of session).

**Decisions flagged [D] for the adversarial review:**
1. Weekly life as primary, rather than Robinhood's 90-day set-and-forget.
2. F1 deciding with F3 as a gate, rather than F3 deciding.
3. The E values, and H2's 90-day horizon rather than 30 days (better power, less "own").
4. U-Q1's thresholds (24 months, rank ≤ 50).
5. Twins with ±182-day exclusion, rather than leave-out drift.
6. Half-retrace / 72 h as the primary flip.
7. Keeping the exit comparison out of Holm.

---

## Sources

**Repo:**
- [`mechanics.md`](mechanics.md), [`evidence.md`](evidence.md), [`data_inventory.md`](data_inventory.md)
- `analysis_2026/BB_REPLICATION_PREREG.md`, `analysis_2026/SCALPING_PREREG.md`
- `MEGACAP_DIP_PREREG.md` (branch `origin/claude/add-price-data-csvs-MTD46`)
- HANDOFF.md §4, 5.11, 5.19, 5.21, 5.22
- `analysis_2026/fetch_stinkbid_data.py`, `fetch_bb_data.py`, `fetch_scalping_data.py`

**Literature** (as cited and tagged in `evidence.md` and `mechanics.md`; abstracts only, confirm before quoting):
- [Christensen, Oomen and Renò 2022](https://econpapers.repec.org/RePEc:eee:econom:v:227:y:2022:i:2:p:461-497)
- [Nagel 2012](https://nber.org/papers/w17653)
- [Savor 2012](https://ideas.repec.org/a/eee/jfinec/v106y2012i3p635-659.html)
- [Chan 2003](https://econpapers.repec.org/RePEc:eee:jfinec:v:70:y:2003:i:2:p:223-260)
- [Cox and Peterson 1994](https://econpapers.repec.org/RePEc:bla:jfinan:v:49:y:1994:i:1:p:255-67)
- [Osler 2000](https://www.newyorkfed.org/research/epr/00v06n2/0007osle)
- [Osler 2003](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html)
- [Osler 2005 (SR 150)](https://www.newyorkfed.org/research/staff_reports/sr150.html)
- [Urquhart 2017](https://econpapers.repec.org/RePEc:eee:ecolet:v:159:y:2017:i:c:p:145-148)
- [Lo, MacKinlay and Zhang 2002](https://web.mit.edu/Alo/www/Papers/limit10.html)
- [Liu and Tsyvinski](https://papers.ssrn.com/abstract=3226806) [U: venue]
- [Liu, Makarov and Schoar (LUNA), NBER w31160](https://www.nber.org/papers/w31160)

**Practitioner and data sources:**
- [AQR, "Hold the Dip"](https://www.aqr.com/Insights/Research/Alternative-Thinking/Hold-the-Dip) [S]
- [K33 via The Block](https://www.theblock.co/post/372115/whats-next-after-cryptos-fourth-largest-long-liquidation-event-of-2025) [S]
- [FTT, Fortune](https://fortune.com/crypto/2022/11/18/how-ftx-own-token-ftt-was-the-final-nail-in-its-coffin) [S]
- [FRED DGS3MO](https://fred.stlouisfed.org/series/dgs3mo) [A]
- [Binance public data](https://github.com/binance/binance-public-data/) (archive layout) [A]
- Robinhood order mechanics, routes and costs: `mechanics.md` §1, with its Robinhood support-page links [A]
