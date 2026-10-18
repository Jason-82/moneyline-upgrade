# Pre-registration: scalping and bid-ask capture in low-volume markets

Written 2026-10-18, before any strategy return in the test samples was computed. Before freezing,
an adversarial review from three angles (statistics, simulation fidelity, relevance) made 64
proposals. Most were adopted (see "Revision log" at the end).

- Research notes: `analysis_2026/research_notes/Scalping and market making/`. Their pilot results are
  listed under "Already seen" below.
- Code:
  - `analysis_2026/scalp_crypto.py` (Part A)
  - `analysis_2026/scalp_us_daily.py` (Parts B, E and D)
  - `analysis_2026/scalp_us_intraday.py` (Part C)
  - `analysis_2026/fetch_scalping_data.py` (data)
- Results: `analysis_2026/results_scalping/`.

## The question

The user's friend "looks for low volume stocks and invests a large amount with the goal of
capturing small increases in price or trying to buy at the bid and sell at the ask", and reports
making money. The user has substantial capital. Is this a strategy, at what size, and which
variants survive realistic fills and costs?

Buying at the bid and selling at the ask is market making.
- The spread is gross revenue.
- It pays for adverse selection (fills arrive just before the price moves against you), for
  inventory risk and for fees.

"Capturing small increases in price" in thin names may instead be momentum or attention trading.
The tests measure what is left after each cost, at the speeds and sizes open to an individual.
They cover both readings.

## Priors (stated now, from the research notes)

- **Passive quoting at retail speed loses** to adverse selection in every liquidity band. Net
  liquidity-provision profit in US stocks is about 1-2 bp of volume even at 100 ms (Conrad-Wahal).
- **Daily reversal** is largest gross in illiquid stocks, but at or below zero there after costs
  (Avramov-Chordia-Goyal; De Groot-Huij-Zhou).
- **Attention continuation**: high-turnover names show short-term momentum (Medhat-Schmeling), but
  after spikes in thin names, reversal is more likely.
- **Size works against the strategy.** Capacity is capped by other traders' order flow, and large
  orders in thin names pay more impact than the spread.
- **The friend's results** are most likely explained by momentum or attention trading, by
  mark-to-market gains his own buying created, or by luck and survivorship in a bull market.

## Already seen (contamination statement)

- **Crypto pilot:** 16 Binance USDT pairs, 2026-10-10 to 10-16 (`crypto_data_feasibility.md` §3).
  - A naive quote at the best bid/ask lost 1.5-10 bp per fill before fees in every band.
  - The average maker's 5-minute realized spread by band was +1.9 / −2.2 / +0.8 / −1.8 bp.
  - One futures day (2024-03-29, 17 symbols) validated the trades-only estimators against the true
    book.
  - The 16 pilot pairs are excluded from Part A's draws, and the pilot week lies after the test
    period. The validation day is excluded from Part A's control days.
- **US pilot:** quoted spreads, depth and spread-estimator accuracy for 40 stocks and 1,167
  closing quotes (`us_data_feasibility.md` §2-3). No strategy return was computed.
  - The 40 names are excluded from Part C's panel.
  - They stay in Parts B and E, whose returns were not looked at.
- **Reviewer coverage counts:** qlib names per band and ETF shares per band. Coverage only.
- Nothing from Parts B-E has been computed.

---

## General rules

### Multiplicity and verdicts

- **One Holm family** spans all 36 primary tests: A 12, B 16, E 4, C 4.
  - Holm runs on the one-sided p-values of every primary cell, whether or not it meets its other
    conditions.
  - Every cell's Holm-adjusted p is reported.
- **Each primary cell gets one of three verdicts:**
  - **PASS:** its Holm-adjusted p < 0.05 and every other condition of its pass rule holds.
  - **NO EDGE:** the one-sided upper confidence bound of its edge, at level 1 − 0.05/36, is below the
    economic threshold E.
    - E for Part A = +1.0 bp net per $ filled.
    - E for Parts B and E = +5 bp net per trade-day held.
    - E for Part C = +5 bp net per $ bought.
  - **INCONCLUSIVE:** neither.
- **Also reported for every cell:**
  - the largest edge ruled out at 95%;
  - the minimum detectable effect MDE = (z_{1−0.05/36} + 0.84) × SE, using the SE that decides the
    test.
- **A summary may say "this does not work"** for a part only if all its friend-relevant cells
  (A-Q5, B4, C1, E1) are NO EDGE.
- **A PASS shows an edge exists.** Whether it is worth running is judged from the capacity
  (Part D) and after-tax tables, not from the p-value.
- **Bootstrap p-values**, where used: p = (1 + #{b : m*_b − m̂ ≥ m̂}) / (B + 1).

### Reported for every primary cell

- the share of units with at least one trade, and the mean per active unit;
- the capital tied up (Part A: 4 × order size per pair; Parts B, C and E: peak daily capital in
  use), with the annualized net return on it and its Sharpe ratio;
- that return after 35% short-term tax, next to SPY buy-and-hold after 20% long-term tax over the
  same dates (the repo's gate rule T2b);
- the route it needs and the orders and cancels per day:
  - A: a bot on a crypto-venue API, not Robinhood;
  - B and E: end-of-day decisions through Claude and the Robinhood MCP;
  - C: a local bot, or re-quoting by hand every 5 minutes;
- the months of closed-trade P&L a trader would need for t ≥ 2 at 10%, 25% and 50% a year, given the
  strategy's daily P&L SD. This is the benchmark for the friend's own record.

### Controls (run before any primary result is read)

Every engine is run on synthetic no-edge data with the same sparsity and spread:
- a random-walk mid with a known half-spread;
- aggressor arrivals independent of the future mid;
- daily and 5-minute OHLCV aggregated from synthetic ticks.

Each engine's no-edge level is reported next to its results. Part-specific positive controls and
validations are listed under each part.

---

## Part A: passive quoting on illiquid crypto pairs (Binance spot trade archive)

The one market here with a faithful public record of every trade and its aggressor side: the
`isBuyerMaker` flag says which side rested. A US resident cannot use Binance.com, so this tests the
mechanism, not a venue the user can trade (see "Fidelity").

### Data and universe

- **Source:** Binance spot `trades` daily files (µs timestamps), from the S3 bucket behind
  data.binance.vision. Daily `klines` supply volumes.
- **Period:** 2025-10-01 to 2026-09-30, 12 months; months m = 0..11.
- **Eligible pairs in month m:**
  - USDT-quoted spot pairs with at least 90 days of klines before the month, and a non-zero kline on
    the last day before it.
  - Excluded: stablecoin and fiat bases (USDC, FDUSD, TUSD, USDP, DAI, EUR, TRY, BRL and the like);
    wrapped or staked tokens (WBTC, WBETH, BETH and the like); tokenized equities. These are fixed
    from the symbol list before any simulation and written to `results_scalping/`.
  - Pairs that later delist stay in.
- **Bands:** the trailing 30-day median daily quote volume, ending the day before the month starts:
  - A $50-200k
  - B $0.2-1M
  - C $1-5M
  - D $5-50M
- **Draw:**
  - Each month: 10 pairs per band in A and B, 5 in C and D.
  - Candidates are sorted by symbol, then `numpy.random.default_rng(20261018 + m).choice(candidates,
    size=min(k, n), replace=False)`.
  - Excluded: the 16 pilot pairs, and pairs already drawn for that band in an earlier month. If too
    few undrawn pairs remain, the remaining slots are drawn from all eligible pairs.
- **A-RH stratum** (exploratory, full statistics, outside Holm):
  - Every USDT pair whose base asset Robinhood lists, from a read-only `get_currency_pairs` saved
    once. BTCUSDT and ETHUSDT are included.
  - Run on every 7th day of the period.

### Quote inference from trades (as validated in the pilot)

- Consecutive prints with the same timestamp and aggressor side form one taker order.
- **Implied best bid** = last price of the latest seller-initiated order. **Implied best ask** = last
  price of the latest buyer-initiated order.
- A quote is valid when ask > bid and both sides printed within the last 300 s.
- The quote state carries across midnight from the previous day's file. With no valid quote, we do
  not quote.
- **Tick on day d:** the GCD of the gaps between distinct prices over days d−7..d−1. If a print on day
  d falls off that grid, the GCD from that print on includes it. Quotes sit on the current grid.

### Mechanics

**Latency Δ = 250 ms.**
- A decision at t sees prints up to t.
- New orders, reprices and cancels take effect at t + Δ. Until then the old order stays live and
  fillable.
- A fill is known when it happens. Orders it triggers (Q5's offer, cap-side cancels, T_max timers) go
  live at fill time + Δ.
- The print that changed the implied quote cannot fill the order placed in response to it.
- An aggressor order fills us at most once.

**Fill models:**
- **F1 trade-through (primary):**
  - A resting bid at P fills only when a seller-initiated order prints strictly below P (an ask:
    strictly above).
  - Size = min(remaining, that order's volume printed strictly through P). Price = P.
- **F2 touch (optimistic bound):** any print at or through P fills. Size = at-plus-through volume.
- **Crossed quotes:** if a buyer-initiated print at or below our resting bid occurs while it is live,
  the bid is crossed. It fills at that print's price for min(remaining, that print's volume), with
  the taker fee (symmetric for asks).

**Taker exits** (T_max, inventory flatten, 00:00 UTC flatten, Q5 timeout):
- **Timing:** decided at t, executed at t + Δ.
- **Reference price R** (for a sale): the lower of the implied bid at t and the first
  seller-initiated print at or after t + Δ. For buys: the higher of the implied ask and the first
  buyer-initiated print.
- **Exit price = R × (1 − w)**, where w is the walk:
  - w is the median first-to-last price walk of seller-initiated orders with notional ≥ the exit
    notional over the pair's previous 7 days.
  - If fewer than 10 such orders exist, w = the median walk of the 10 largest × √(exit notional / their
    median notional).
  - w ≥ one tick / R.
- **Taker fee** on the exit notional.
- **Midnight:** the 00:00 flatten takes R from the first print after 00:00 in the next day's file.
- **Stopped trading:** inventory left when a pair stops trading is valued at the last
  seller-initiated print × (1 − one implied spread), with the taker fee. Such pair-days are listed.

No inventory carries across days. Pair-days are still not independent, since a pair recurs for a
month and pairs share market-wide shocks. The inference allows for both.

### Strategies

| code | rule |
|---|---|
| **Q1 join, two-sided** | Bid at the implied best bid, ask at the implied best ask. Inventory cap \|inv\| ≤ 3 × order size; at the cap, quote only the reducing side. Short inventory means pre-held coins sold down (P&L excludes a base holding's drift). If inventory has been non-zero for T_max = 60 min, flatten by the taker-exit rule. |
| **Q2 step-inside** | As Q1, but when the implied spread is ≥ 3 ticks and both sides printed within the last 10 s, quote one tick inside on both sides. Step-inside orders are post-only: if an opposite-side print reaches our price while live, the order is cancelled unfilled. Fills follow F1 at the improved price. |
| **Q5 the friend's rule (long-only)** | When flat, bid at the implied best bid (F1). Once filled, offer at the implied best ask at fill time (at least fill + 1 tick) and keep that offer; it fills by F1. If unsold after T_max = 60 min, sell by the taker-exit rule. One position at a time. |
| Q3 (exploratory) | Q1 one tick behind the best |
| Q1-LO (A-RH stratum only) | Q1 with inventory in [0, 3 × size]: the cash-account market maker |

- **Order size:** $1,000 primary, plus $10,000 and $25,000 (the friend's "large amount").
- **Participation:** 100% of qualifying volume primary; 25% as sensitivity.

### Fee scenarios (maker / taker, bp per side)

| fee | venue it represents | simulated |
|---|---|---|
| **0 / 2 (primary)** | Binance.US 2026 schedule | yes |
| 1 / 3 | Robinhood crypto, $10-25M per 30 days | yes |
| 2 / 5 | Binance USD-M futures, VIP 0 | yes |
| 7.5 / 7.5 | Binance.com spot, VIP 0 with the BNB discount | yes |
| 12.5 / 25, 50 / 90, 50 / 95 | Robinhood $50-250k; Coinbase entry; Robinhood entry | linear: net = gross − f_m × maker $ − f_t × taker $ |
| −0.5, −1, −2, −5 maker (rebates) | break-even rebate search | yes, for the primary cells |

Fee rates come mostly from search snippets (crypto note §6). They are inputs, not findings.

### Primary tests (12, in the study-wide Holm family)

- **Cells:** A-Q1-b, A-Q2-b and A-Q5-b, for each band b ∈ {A, B, C, D}.
- **Settings:** $1k, F1, Δ = 250 ms, fee 0 / 2.
- **Statistic:** mean net P&L per pair-day in $.
  - Pair-days with no fill, or with no trades at all (halt, delisting), count as zero and stay in the
    denominator.
  - The p-value comes from a t-statistic with Cameron-Gelbach-Miller two-way cluster-robust SEs.
  - Clusters: symbol, and ISO calendar week (weeks start Monday 00:00 UTC).
  - The t is compared with Student t at G − 1 df, where G is the smaller of the two cluster counts.
  - If the two-way variance is not positive, the larger one-way variance is used.
- **PASS requires all of:**
  1. Holm-adjusted one-sided p < 0.05.
  2. mean > 0 in both halves (2025-10 to 2026-03 and 2026-04 to 2026-09).
  3. mean > 0 under Δ = 1 s.
  4. mean > 0 after removing the single UTC day whose removal lowers it most.
  5. mean > 0 after the F1 bias correction from Control (ii) below.
- **Kill rule:** if every strategy and band is ≤ 0 even under F2 at fee 0 / 2, no fill model can
  rescue passive quoting here.

**Reported for every cell:**
- gross, fee and net bp per $ filled (Σ net / Σ filled, two-way clustered delta-method CI);
- the maker/taker split of filled $, so any fee tier can be applied;
- net $ per pair-day, with its distribution and worst day;
- fill rate and the share of pair volume taken;
- maximum inventory;
- 60 s and 300 s markouts of passive fills;
- the taker-exit share of P&L;
- the month-level t (11 df) and a day-block bootstrap.

**Splits** (all measured before the month):
- tick-constrained (median spread ≤ 1.5 ticks) vs wide (≥ 3 ticks);
- terciles of spread to 60-s mid volatility over the prior 30 days;
- weekday vs weekend;
- volatility tercile;
- listing age.

Exploratory conditional cell: A-Q2 in the top spread/volatility tercile.

**Capacity:** filled $ per day and P&L $ per day at each order size, by band.

### Part A controls

- **(i) Synthetic Glosten-Milgrom market.**
  - Setup: a random-walk mid; spreads of 1, 3 and 10 ticks; Poisson aggressor orders with the pilot
    pairs' size distribution; an informed share α ∈ {0, 0.3}.
  - Q1, Q2 and Q5 are run under F1, F2 and a true queue model.
  - With α = 0, Q1 must earn about the half-spread per fill under the queue model; otherwise the
    engine is audited before Part A is read.
- **(ii) Strategy-level validation against the true book.**
  - Data: 20 random days (`default_rng(20261018)`) of USD-M futures, 2023-05-16..2024-03-30,
    excluding 2024-03-29, for the 17 thin validation symbols.
  - Run Q1, Q2 and Q5 ($1k, fee 0 / 2, Δ = 250 ms) twice: on trades-only quotes with F1, and on the
    true `bookTicker` quotes with a FIFO queue (join at the back of the displayed size, no cancels
    ahead).
  - If the mean of (trades-only − true) per $ filled exceeds +0.5 bp for a strategy, that excess is
    subtracted from the strategy's Part A net P&L for PASS condition 5.
  - A cell whose verdict changes under the correction is INCONCLUSIVE.
- **(iii) Front-of-queue value.** On the same days, Q1 placed first in the queue at every new level:
  what a speed advantage is worth.

### Fidelity

- **Valid for:** Binance.com spot books only.
- **Untested:** transfer to Binance.US, Coinbase, Kraken or Robinhood books, none of which publishes
  downloadable history.
- **Bias direction:** the trades-only quote overstates spreads on fine-tick pairs. Markouts at 60 s
  and later carry under 0.2 bp of bias.
- **Assumption:** those error bounds come from thin-but-active futures books (one print every
  1-4 s). Band-A spot pairs print about twice a minute, and 8-16% of the gaps between seller orders
  exceed 300 s, so applying the bounds there is an assumption.

---

## Common definitions for US stocks (Parts B, C, D, E)

### Samples (all survivor-biased: a positive result is an upper bound)

**B-H (history, primary): the qlib US daily set** (SunsetWolf `qlib_data_us_1d_v3.zip`), 2001-04-09
(after decimalisation) to 2020-10-30.
- **Survivorship:** it is effectively a November-2020 snapshot; names that died earlier are mostly
  missing.
- **Price fields:**
  - `close` is split- and dividend-adjusted. Returns use it.
  - `close/factor` is Yahoo's split-adjusted close, not the traded price.
  - Dollar volume = close × volume, which is split-invariant.
- **Traded-price proxy P** = (close/factor)/k, where k is the largest integer in 2..50 such that
  ≥ 90% of the trailing 60 values of close/factor are multiples of $0.01·k (tolerance 0.005 of a grid
  step); otherwise k = 1.
  - Name-days where < 90% of the trailing 60 values of P lie on the $0.01 grid are excluded from
    L1-L4. These are forward splits or sub-penny trading, where the traded price is unknown.
  - P drives the $1 filter, the tick floor $0.01/P, log price in the spread model, and the one-tick
    trade-through rules.
  - Sensitivity: drop every name-day with k > 1.

**B-R (recent, replication): Robinhood daily bars,** 2023-07-03 to 2026-10-16.
- **Pull:** split-adjusted for returns, and unadjusted for price-level rules. Regular session.
- **Universe:** every common stock on XNAS, XNYS or XASE that a read-only `preview_scan` lists today,
  with any price > $0 and scanner `turnoverAvg(60)` of $10k-$20M.
  - The scan runs in price slices of fewer than 200 rows.
  - Funds, ETNs, SPACs, units, preferreds and notes are dropped with a word-bounded name filter.
- **Liquid names** come from `data/universe_recent_raw/`, 2024-08 onward.
- **Bad bars:** interpolated bars are not real bars. Zero-volume bars are real but untraded.
- **Market cap and shares outstanding** are saved with the universe, for the ownership caps in D3.

### Exclusions (B-H; B-R uses the scan's asset type plus rules b-d)

- (a) **ETFs:** `ETF = Y` in `nasdaq-listed-symbols.csv` (datasets/nasdaq-listings) or in
  `other-listed.csv` (datasets/nyse-other-listings: NYSE, NYSE American, Arca, Cboe).
- (b) **Security names** in either file matching, case-insensitively with word boundaries:
  `ETF|ETN|Fund|Notes?|Debentures?|Preferred|Warrants?|Rights?|Units?|Closed[- ]End|Trust Units`.
- (c) **Symbols** containing `^ - . _`.
- (d) **5-character symbols** whose fifth letter is G, H, I, M, N, O, P, R, T, U, V, W, X or Z.
- (e) **Unknown symbols:** for symbols in neither file, a name whose daily returns over the trailing
  250 days (data to t−1) have R² ≥ 0.90 on any one of SPY, QQQ, IWM, MDY, DIA, EFA, EEM, AGG, TLT,
  IEF, LQD, HYG, GLD, SLV, USO and the nine XL* sector funds is treated as a fund from then on.

The count excluded by each rule is reported. Removed funds form B6's sample.

### Data screen (causal, applied to every name-day)

- Drop days with any OHLC ≤ 0, low > min(open, close) or high < max(open, close).
- Reversal and continuation signals cannot fire on a one-price day.
- They also cannot fire on a day where both close_t/close_{t−1} and open_t/close_{t−1} are within 2%
  of a split ratio (1/2, 1/3, 2/3, 1/4, 1/5, 1/8, 1/10, 1/20 or their inverses).

### Windows, bands and eligibility

- **Windows:** trailing windows run over the last N exchange trading days. A day with no real bar
  adds $0 to the dollar-volume median and is skipped by EDGE and σ.
- **Eligibility at t:** at least 40 real bars in the 60-day window; P ≥ $1 at t; volume > 0 on the
  signal and entry days.
- **Liquidity band at t:** the trailing 60-day median of close × volume, data to t−1.
  - L1 $50-150k
  - L2 $150-500k
  - L3 $0.5-1.5M
  - L4 $1.5-5M
  - L5 $5-50M (control)
  - L6 > $50M (control)

### Exits across missing bars

- Holding periods count exchange trading days.
- If a scheduled exit day has no real bar, the position is sold at the close of the next real bar,
  paying the exit cost as of that day.
- If there is no real bar within 20 trading days, or the series ends inside the sample, the exit is
  the last close × (1 − 0.30). This is Shumway's (1997) performance-delisting return; a 0% variant
  is reported.
- Benchmark names are treated identically.

### Spread estimate s_it (full, relative, data to t−1)

s_it is the maximum of three terms:
- (a) **EDGE** (Ardia-Guidotti-Kroencke) on the trailing 60 daily bars × c.
  - c = 1.25 in L1 (pilot median EDGE/quoted = 0.80) and 1/1.4 in L2-L6.
- (b) **The closing-quote model M_it** = exp(b0 + b1·log ADV + b2·log P + b3·log σ) × S.
  - Fitted by OLS of log closing quoted spread on all 1,167 pilot names of 2026-10-16.
  - Regressors: ADV = trailing 60-day median of daily-bar close × volume ending 2026-10-15; P =
    unadjusted official close; σ = SD of the same 60 daily log returns.
  - S = mean(exp(residuals)), Duan smearing.
  - In B-H, M is multiplied by R_y = max(1, [median of EDGE/M over L1-L4 name-days of year y−1] ÷ [the
    same median over B-R 2025-10..2026-09]). This stands in for the wider spreads of earlier years.
- (c) **One tick:** $0.01 / P.

The coefficients, S and every R_y are written to `results_scalping/` before any return is computed.
The quotes include odd lots, so M is a lower bound for round-lot orders; m = 2 is reported for that
reason.

### Costs and position size

- **Cost multiplier m:** each taker leg pays m × s/2.
  - **Primary m = 1.5.** This covers the bid-ask bounce: if a loser closed at the bid, buying at the
    close costs 1.5 × s per round trip relative to close-to-close returns.
  - Also reported: m = 0, 1 and 2, and the break-even m* with its 95% CI.
- **Impact:** Q = $10k per name in the primary tests. Each taker leg also pays
  Y × σ20 × √(max(0, Q − D_k) / ADV60).
  - Y = 0.5 primary; also Y = 1 and 0 (the no-impact upper bound).
  - σ20 = trailing 20-day SD of daily returns; ADV60 = trailing 60-day median $ volume.
  - D_k = the pilot's median inside depth per side: L1 $974, L2 $1,465, L3 $3,056, L4 and above
    $8,152.
- **Entry cap:** entries are capped at 10% of the entry day's $ volume, with a capped order filled
  pro rata.
- **Other sizes:** every cell is also reported at Q = $1k, $50k and $250k.
- **Fees:** Robinhood, $0 commission. SEC and TAF fees by trade date are under 0.3 bp and charged on
  sells.

### Return metric (Parts B and E)

- **Trade-weighted** mean of per-trade net returns; one trade = one name-day position at Q.
- **Daily series for inference:** D_t = (Σ over trades on day t of x_it) / N̄, where N̄ is the
  full-sample mean number of trades per day and D_t = 0 on days with no trade. Newey-West uses 10
  lags (h + 4 for h-day holds).
- **x_it** is the trade's net return minus the equal-weighted return of the other eligible names in
  its band (excluding that day's traded names) over the same holding window. This is "band excess".
  - It removes market drift and the band's common survivorship drift.
  - It does not remove the extra survivorship of losers, so B-H stays an upper bound.
  - Exceptions are given in the strategy rows.

---

## Part B: daily-horizon liquidity provision in low-volume US stocks

Signals are taken at the close of day t. All positions are long-only.

| code | rule |
|---|---|
| **B1 one-day reversal** | Buy names in the band's bottom decile of r_t (and r_t < 0) at the close of t; sell at the close of t+1. |
| **B2 volume-shock reversal** | As B1, plus volume_t ≥ 3 × the trailing 60-day median volume. |
| **B3 passive dip bid** | A day-limit buy for t+1 at L = P_t × (1 − σ_t), with σ_t the trailing 20-day SD. **Fill** only if low_{t+1} ≤ L − one tick (traded-price units; on B-R, only a whole-cent low counts). Fill price = L; min(open, L) is a sensitivity. **Size** q = min(Q, 10% × $vol_{t+1} × f), with f = (L − low)/(high − low) clipped to [0, 1], and f = 1 on a one-price day. Sell at the close of t+1, paying the exit cost. **Primary metric: raw net return, q-weighted**: an intraday fill comes after the name, and on average its band, has fallen, so a band benchmark would credit a decline we never held. |
| **B4 the friend's rule, daily** | At the close of t, a day-limit buy for t+1 at B = P_t × (1 − s_it/2), rounded down to the cent. Fill if low_{t+1} ≤ B − one tick, at B, with size as B3. From t+2, a GTC sell at A = B × (1 + s_it), rounded up to the cent, fills if high ≥ A + one tick, at most 10% of that day's $ volume × f. Any remainder after 5 sessions is sold at the close with the exit cost and impact. One position per name. **Metric:** the raw return from fill to close(t+1), plus the band excess from close(t+1) to exit. |

### Primary tests (16)

- **Cells:** B1-k to B4-k for k ∈ {L1, L2, L3, L4}, on B-H.
- **Statistic:** trade-weighted mean net return at m = 1.5 and Y = 0.5 (band excess for B1, B2 and B4
  as defined; raw for B3).
- **PASS requires all of:**
  1. Holm-adjusted one-sided p < 0.05, from the Newey-West t of D_t.
  2. mean > 0 in both halves (2001-04 to 2010-12 and 2011-01 to 2020-10).
  3. mean > 0 in B-R at m = 1.5.
  4. For B1 and B2: the skip-a-day variant (enter at the close of t+1, exit at the close of t+2) has a
     gross (m = 0) mean > 0. That is, the reversal outlasts the bounce day.
  5. For L1 and L2: mean > 0 also at m = 2.
  6. mean > 0 with per-trade net returns winsorized at the 0.5th and 99.5th percentiles of the cell's
     pooled trades.
  7. mean > 0 after removing the single calendar month whose removal lowers it most.
  8. The real statistic exceeds the largest of 20 null-panel statistics (Controls (i)).

### Exploratory (full statistics, decide nothing)

- 5-day holds;
- B3 with L = P × (1 − 0.5σ) and (1 − 2σ);
- B3 exits at t+2 and t+6;
- B4 targets A = B × 1.01 and × 1.02 ("small increases in price"), and holds of 1 and 20 sessions;
- B1, B2 and B4 split into an overnight leg (close_t → open_{t+1}) and an intraday leg;
- B1-ON (sell at the open of t+1, with s doubled at the open as a sensitivity);
- bands L5 and L6;
- high-VIX terciles (`data/macro/`);
- raw instead of band-excess returns, and an open(t+1)-based benchmark;
- B4 in $1-3 stocks (one tick ≥ 33 bp) and by tercile of s/σ20;
- the median cross-sectional percentile of 60-day $ volume for each band, by half;
- the k > 1 exclusion sensitivity.

**Illusion baselines** (reported as such):
- B3 and B4 with touch fills (low ≤ L);
- equal-weighted rather than q-weighted.

**B6 thin-ETF dislocation** (exploratory, outside Holm):
- **Universe:** funds removed by the exclusion rules, in L1-L4.
- **Twin:** the most correlated fund (trailing 250 days, data to t−1) from SPY, QQQ, IWM, MDY, DIA,
  EFA, EEM, AGG, TLT, IEF, LQD, HYG, GLD, SLV, USO, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY and
  VNQ, with β from the same window.
- **Signal:** residual u_t = r_t − β·r_twin,t. Buy at the close of t if u_t < −2 × its trailing
  60-day SD, and sell at the close of t+1.
- **Costs and benchmark:** costs as in Part B. The benchmark is β × the twin's return over the
  holding window.
- **Variants:** exit at t+5; international funds reported separately.

### Part B controls

- **(i) No-edge level.** Rerun B1-B4 and E1 on 20 null panels. In each, every name's daily bars are
  redrawn with replacement from its own history. The redrawn unit is the vector of open, high and
  low relative to the prior close, the close-to-close return, and volume. Report the null mean and
  maximum of each primary statistic.
- **(ii) Known answer.** B1 gross (m = 0) on the S&P 500 PIT set (`data/universe_pit_all/`),
  2001-2010, must show a positive 1-day reversal with NW t ≥ 2. If it does not, the pipeline is
  audited before any B result is read.
- **(iii) Survivorship calibration.** B1 and E1 (gross, and at m = 1.5) on S&P 500 PIT members
  2001-2020. Run once on all members, dead ones included, and once on only the members qlib has on
  each date. The difference is reported as the large-cap survivorship effect.

---

## Part E: attention continuation ("capturing small increases in price")

### Rule

- **E1-k, k ∈ {L1..L4}, on B-H.**
- At the close of t, buy names in the band whose r_t is in the top decile (and r_t > 0), and whose
  volume_t ≥ 3 × the trailing 60-day median volume. Sell at the close of t+1.
- Costs, impact, metric (band excess) and PASS conditions 1-8 are as for B1. Condition 4 becomes: the
  skip-a-day gross mean is > 0 (continuation outlasts the bounce day).

### Exploratory

- exits at t+5 and t+20, net of costs;
- entry at the open of t+1.

### Intraday leg (exploratory, survivor-biased, ≤ 8 months)

- **Events:** B-R name-days inside the 5-minute retention window with volume ≥ 5 × the 60-day median
  and open_t / close_{t−1} − 1 ≥ +5%. At most 1,500 events, drawn with `default_rng(20261018)` if
  there are more.
- **Data:** that day's 5-minute bars are pulled for each event.
- **Rule:** a 30-minute opening-range breakout.
  - Buy at the first 5-minute close above the 09:30-10:00 high, at close × (1 + m × s/2), capped at
    25% of that bar's $ volume.
  - Sell at the first close below the 09:30-10:00 low, or at the close of the bar starting 15:50, at
    close × (1 − m × s/2).

---

## Part C: intraday "buy at the bid, sell at the ask" on 5-minute bars

The closest test of the friend's literal rule that free US data allows.
- **No historical quotes.** Bid and ask are estimated from the last trade ∓ half a spread estimate,
  and fills need a whole-cent trade-through.
- **Off-exchange prints.** Bars carry 32-58% of consolidated volume but include off-exchange prints:
  25-61% of bar extremes in the six pilot names are sub-penny. Even the whole-cent rule leans
  optimistic.

### Data

- **Panel:** 120 stocks, 30 per band L1-L4, drawn with `default_rng(20261018)` from the B-R universe.
  The draw uses the bands as of 2026-10-16 and excludes the 40 pilot names.
- **Point-in-time bands:** each session d is assigned the band from the trailing 60-day median daily
  $ volume ending d−1. C1-k pools the stock-sessions whose band on d is k.
- **Bars:**
  - Robinhood 5-minute bars, regular session, split-adjusted and unadjusted (unadjusted for cent
    rounding and trade-throughs).
  - Window fixed at 2026-03-02 to 2026-10-16. If retention has rolled past the start when the bars
    are pulled, the window starts at the first available session and this is listed as a deviation.
  - Pulled in one pass starting by 2026-10-20, together with 1-minute bars (full retention) for all
    120 names and 15-second bars (full retention) for 40 of them (the first 10 per band in draw
    order).
- **Clock:**
  - C runs on the 78-bar regular-session clock. Bars are labelled by start time; a decision at the
    close of the bar starting τ is made at τ + 5 min.
  - No-trade bars (interpolated inside a session that has real bars) are kept as clock bars and
    never fill.
  - Sessions with no real bar count as zero.
- **Spread estimate s_id:**
  - The median over the previous 20 sessions of per-session EDGE. Each session's EDGE uses that
    session's 78 clock bars, with no-trade bars set to NaN and never chained across sessions. Only
    sessions with ≥ 10 traded bars count.
  - If fewer than 5 sessions qualify, Part B's daily s as of d−1 is used.
  - Placement and exits use s = max(s_id, M_i,d−1), floored at one tick / unadjusted price.

### Strategy C1 (long-only; one position per stock at a time)

- **Buy limit:** when flat, at the closes of bars starting 09:40 through 15:25, post a buy limit at
  B = last trade × (1 − s/2), rounded down to the cent. It is re-posted at every clock-bar close.
- **Buy fill:**
  - It fills in a later bar only if that bar's low is a whole-cent price and low ≤ B − $0.01. Sub-penny
    extremes are off-exchange prints and never fill.
  - Fill price B. Size per bar = min(remaining, 25% × bar $ volume × f), with f = (B − low)/(high −
    low) clipped to [0, 1], and f = 1 for one-price bars.
  - Order size $2,000. A partly filled buy is not topped up.
- **Sell limit:**
  - From the bar after the fill, a sell limit at A = B × (1 + s), rounded up to the cent.
  - It fills in a bar whose high is a whole-cent price ≥ A + $0.01, at A, for at most 25% × bar $
    volume × f, with f = (high − A)/(high − low). The remainder stays offered.
- **Forced exit:**
  - From T_max = 6 bars (30 min) after the fill, the remainder is sold bar by bar at each bar's close ×
    (1 − m × s/2), at most 25% of each bar's $ volume.
  - In the T_max bar, the resting sell limit is checked first.
  - Whatever is left at the close of the bar starting 15:50 is sold at that close × (1 − m × s) −
    0.5 × σ_d × √(remainder / ADV60).
- **Fees by trade date:**
  - SEC Section 31: $0 to 2026-04-03, then $20.60 per $M on sales over $500.
  - FINRA TAF: $0.000195/share (cap $9.79) on sales over 50 shares through 2026-09-30, then $0.
  - An IBKR-like $0.0045/share round trip is a sensitivity.

### Primary tests (4)

- **Cells:** C1-k for k ∈ {L1, L2, L3, L4}, on stock-sessions where s × P ≥ $0.03, i.e. at least three
  ticks, so B lies inside the quote. One- and two-tick names are reported descriptively as range
  trades.
- **Statistic:** mean net P&L per stock-session in $, at m = 1.5.
  - Inference: two-way cluster-robust (stock and calendar week), with Student t at G − 1 df.
- **PASS requires all of:**
  1. Holm-adjusted one-sided p < 0.05.
  2. mean > 0 in both halves, split at the window's median session.
  3. mean > 0 with T_max = 12 bars.
  4. mean > 0 with one-bar latency (orders posted at the close of bar t live only from bar t+2).
  5. mean > 0 after removing the session whose removal lowers it most.
  6. The sign agrees on 1-minute bars over the overlapping sessions, run with the same clock-time
     parameters. If not, the verdict is INCONCLUSIVE.

### Reported

- per-trade bp and fill counts;
- markouts of fills at +1, +3 and +6 bars;
- $10k orders;
- P&L by half-hour of entry;
- C1-open (entries 09:35-10:00) and C1-close (entries 15:30-15:50, exit at the 15:50 bar), both
  exploratory;
- $1-3 stocks;
- terciles of spread to 5-minute volatility;
- the 15-second rerun (fill-count and P&L ratios);
- the share of B-R B3/B4 daily fills in the window not confirmed by any whole-cent 5-minute low.

**Illusion baselines:**
- touch fills;
- the any-extreme rule (sub-penny extremes counted), with the share of fills it adds.

### Part C controls

- **(i) Positive control (Roll market).**
  - For each band: 160 sessions × 30 names of tick-level prints.
  - The mid is a random walk with the band's median 5-minute volatility.
  - The spread is the band's median closing quoted spread (197 / 97 / 38 / 21 bp), plus a one-cent
    case.
  - Poisson prints alternate between bid and ask with no information.
  - A random 40% of prints are kept and aggregated to 5-minute OHLCV, then C1 is run unchanged.
  - If C1 does not PASS this zero-information control in a band, that band's C1 verdict is capped at
    INCONCLUSIVE.
- **(ii) Null.** C1 on each name's 5-minute bars shuffled within the session.
- **(iii) IEX validation (descriptive).**
  - Sample: on 5 sampled days, panel L4 names whose IEX best bid/offer matched the NBBO at the close.
  - Run C1's rule on IEX TOPS ticks with a back-of-queue model at IEX's bid, marked to IEX's mid.
  - Compare with bar-based C1 on the same name-days.

---

## Part D: capacity and self-inflicted price impact (descriptive)

- **D1 capacity model.** Band medians from B-R, from the round-trip-cost formula and the paper-gain
  formula, at 1%, 5%, 10% and 25% of ADV, with Y = 0.5 and 1.
- **D2 do aggressive buying days give back?**
  - Sample: names with volume_t ≥ 3 × the 60-day median and a top-decile r_t.
  - Measure: band-excess returns over the next 1, 5 and 20 days (NW with h + 4 lags).
  - Both samples under-represent spikes that later collapsed into delisting. A finding of no
    give-back is therefore not evidence against self-inflicted impact; a give-back found here is a
    lower bound.
- **D3 deployed-capital curve.**
  - For K ∈ {$10k, $50k, $250k, $1M, $5M} and every B, C and E strategy, whatever its verdict:
    split K equally across each day's signals.
  - Per-name caps:
    - ≤ 10% of the entry day's $ volume;
    - ≤ 4.9% of shares outstanding;
    - ≤ 20% of ADV60 per day on exit.
  - Impact is charged at the realized size.
  - Reported:
    - capital deployed (mean and 5th percentile);
    - net $ a year and net return on K;
    - the K at which return per $ halves, and the K at which it reaches zero;
    - mean days to exit;
    - days that would trigger Large Trader registration (≥ $20M or ≥ 2M shares a day, buys plus
      sells).
  - Parts A and C use their observed filled $ per day at each order size.
- **D4 accumulate and exit on real paths.**
  - Sample and size: 200 random name-dates per band L1-L5 (`default_rng(20261018)`) on B-R, with
    B-H 2011-2020 as replication. Buy Q = 5%, 10%, 25% and 100% of ADV60.
  - Buying: at most 20% of each real day's $ volume, at that day's (high + low + close)/3 × (1 + m ×
    s/2 + Y × σ20 × √(day's buy / day's $ volume)).
  - Paper P&L is marked at the last buying day's close, plus a permanent impact of 2/3 of the
    temporary impact (Bucci et al.).
  - After 5 sessions, sell under the same rules.
  - Reported, net of the band's EW return: paper and realized P&L (mean, median, 5th percentile),
    the paper-minus-realized gap, and days to enter and exit.
  - This shows how a large buyer's marks diverge from what he can realize. It is not a strategy test.

---

## Not testable with reachable data

- **Tick-level tape reading and queue-priority scalping in US stocks.** It needs historical quotes
  and order-book data, which are paid (TAQ, Polygon, Databento).
- **Rebate capture.** Robinhood passes no exchange rebates to customers. The per-share economics are
  in `practicalities_us.md` §10.
- **Venue-faithful crypto quoting for a US resident.** The fix is to record Coinbase/Kraken books
  forward on the user's machine.
- **A survivorship-free small-cap universe before 2026-10.** The fix is to save the scanner's
  closing quotes and sizes every trading day from now on.

## Reporting rules

- Every pre-registered cell is reported, whatever its verdict.
- Naive, touch or any-extreme fills are reported only as "illusion" baselines.
- Any change to these rules after results are seen is listed in the write-up as a deviation, with
  the reason.

## Revision log (before freezing)

Adopted from the three-lens review:
- **Inference:**
  - instrument × week clustering (A, C);
  - draws without replacement and 10 pairs in bands A and B;
  - one study-wide Holm family;
  - PASS / NO EDGE / INCONCLUSIVE verdicts with MDEs;
  - trade-weighted Part B statistic;
  - NW 10 lags;
  - drop-worst-day/month, winsorized and m = 2 conditions;
  - the skip-a-day condition made gross.
- **Prices and data:**
  - B3 raw metric;
  - traded-price proxy for split-adjusted qlib prices;
  - whole-cent trade-throughs;
  - exits across missing bars with a delisting return;
  - recalibrated spread model;
  - broader ETF and preferred exclusions;
  - a causal data screen;
  - decimalisation start.
- **Execution:**
  - taker exits priced off real seller orders;
  - post-only step-inside;
  - size caps on every leg;
  - impact at $10k;
  - the bar clock;
  - fees by date.
- **Added variants:**
  - B4 (the friend's rule, daily);
  - Part E (attention continuation);
  - D3 and D4;
  - B6 thin ETFs;
  - the A-RH stratum.
- **Controls:**
  - synthetic no-edge runs;
  - a Glosten-Milgrom control and validation against the true book (A);
  - a Roll-market positive control (C);
  - null panels and a known-answer check (B);
  - 1-minute and 15-second checks (C);
  - IEX validation;
  - survivorship calibration.
- **Reporting:** after-tax comparison with SPY; the months of record needed to judge the friend.

Not adopted:
- forward quote collection from 2026-10-19 as a pre-registered out-of-sample test (this session
  cannot run for weeks; it is a recommendation instead);
- IEX validation beyond 5 days (each day is a 14.6 GB stream).
