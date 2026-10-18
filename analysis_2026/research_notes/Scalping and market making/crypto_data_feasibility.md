# Can Binance's Public Archive Test Passive Market Making on Illiquid Pairs? Data Feasibility and Pilot (as of 2026-10-18)

> **How this was verified.**
> - **[D]: computed this session from the primary data files.** Source: Binance's public archive (`data.binance.vision`), read through its S3 bucket path-style, because the website host is blocked here.
>   - Every downloaded zip passed Binance's own `.CHECKSUM` (SHA-256).
>   - All 112 spot pair-days reconcile exactly with Binance's daily klines on trade count and quote volume, with no gaps in trade ids.
> - **[A]:** checked against the primary source's own text (official fee page, terms, or the archive's own listing) as retrieved this session.
>   - The archive listings were read directly.
>   - Fee pages could not be fetched: WebFetch and curl both failed on binance.com, coinbase.com, kraken.com and robinhood.com. Their text came back through search-engine retrieval of the official page, and is tagged [A] only when the snippet came from the venue's own domain.
> - **[S]:** secondary source only (review site, trade press).
> - **[U]:** from memory, unverified or conflicting. Treat it as a lead.
> - **Pilot scope.** One pilot week of spot trades (2026-10-10 to 10-16) for 16 pairs, plus one validation day of USD-M futures (2024-03-29) for 17 symbols, where the archive also holds the true best bid/ask. This is a first look, not the final test. Standard errors are hour-clustered.
> - **No personal data.** This note contains no account numbers, balances, positions or order logs.
>
> **Fact-check (date 2026-10-17): 185 claims checked, 22 corrections.**
> - Every table was recomputed from `results/*.csv`. Reruns gave identical output: `spot_pilot.py` and `spot_se.py` in full, `spot_fill_sim.py` on 3 pairs, `um_validate.py` on 2 symbols. Band t-stats were recomputed too. Also rechecked: all 163 zips against Binance's `.CHECKSUM`, the 112 pair-day kline reconciliation, the ms→µs switch (spot µs from 2025-01-01, futures still ms), archive date ranges from live S3 listings, and the `bookTicker` alignment on all 17 symbols.
> - Not re-checked: fee pages, terms and news (section 6). The web-search budget was used up, and every venue host plus the secondary sites (cointelegraph etc.) was blocked. Their tags are the original author's. Treat every fee as a lead until it has been read on the venue's own page.

---

## 0. Bottom line (one screen)

**1. The archive is a faithful record of every spot trade.** It holds no spot order book at all.
- Spot gives trades, aggTrades and klines (down to 1 s) for 3,750 symbols (klines: 3,742), from 2017 to 2026-10-16. [D]
- For spot you must infer the quote from the trades: the last seller-initiated print stands in for the bid, the last buyer-initiated print for the ask.
- **True best bid/ask exists only for futures**, in USD-M `bookTicker`, and only for **2023-05-16 to 2024-03-30** (283 of 315 symbols). COIN-M `bookTicker` runs to 2024-10-14. [D]
- `bookDepth` (2023-01-01 to now) holds only 30-second snapshots of cumulative depth within ±1-5% of the price. A ±0.2% band was added between Dec 2025 and Mar 2026. It shows nothing about the queue at the best price. [D]

**2. Trades-only estimates are good enough for markouts at 60 s and beyond, but not for the quoted spread on fine-tick books.** Checked against the true futures quotes on 17 symbols [D]:
- **Realized spread at +60 s / +300 s:** bias ≤0.2 bp.
- **At +1 s:** biased upward (too rosy) by 0.0-2.7 bp (0.3-2.7 outside LTC and BTC).
- **Effective half-spread:** too high by up to about 1.1 bp (1.0 in the table, which compares a different set of prints; see section 4).
- **Quoted spread:** overstated about 2-4× when the true spread is one fine tick. It is exact when the tick is coarse, e.g. DGB at 7 bp.

**3. The conservative trades-only fill rule tracks the queue model closely.** The rule: count a resting quote as filled only when a print trades *strictly through* its price.
- **Against a full queue model built from the true quotes:** within 0-7 percentage points of fill rate. Each fill is 0.1-1.0 bp *worse* (mean −0.35 bp). [D]
- **The optimistic "touch" rule** (fill on any print at your price) overstates profit by 0.7-6.2 bp per fill (mean +1.5 bp) and fill rate by 5-38 points. The largest error is on the coarse-tick symbol. [D]

**4. The pilot finds no free lunch at any liquidity band.**
- **The average resting order** on Binance spot captures a large effective half-spread: about 16 bp in the $50-200k/day band, falling to 0.4 bp in BTC.
- **Adverse moves take back nearly all of it within 5 minutes.** Realized spread at +300 s by band: **+1.9 / −2.2 / +0.8 / −1.8 / −0.7 bp** for $50-200k / $0.2-1M / $1-5M / $5-50M / BTC.
- **None is significantly positive.** Bands B and D are significantly negative, at about −2.4 and −3.7 hour-clustered SEs (one week, pairs treated as independent). [D]
  - Fact-check: clustering hours jointly across a band's pairs gives the same picture (−2.4 and −3.7).
  - B would not survive a Bonferroni correction over the 5 bands; D would.
- **A naive quote** that sits at the best bid/ask for 60 s at a time loses money before fees in every band under the conservative fill rule:
  - −1.5 bp (BTC) to −10 bp per fill (band means)
  - −1.5 to −19 bp per dollar filled at $1k order size, because the large fills are the toxic ones [D]

**5. Fees decide the rest, and US access narrows the field.**
- **Binance.com:** US persons are barred [S]. Its retail spot maker fee (10 bp, or 7.5 bp with BNB) [S] is already larger than any realized spread measured.
- **Fee rates where a passive edge of about 0-2 bp per fill could survive:**
  - Binance.US: 0% maker / 0.02% taker since 2026-04-22 [A]
  - Kraken's ≥$10M tier [S]
  - Coinbase's top tier [S]
  - Robinhood's ≥$10M exchange-routing tiers: 0.00-0.01% maker [A]
- **Robinhood's default route** (about 0.95%, which the market maker pays Robinhood, about $0.95 per $100, and builds into your price [A]; see section 6) makes passive spread capture impossible.

**6. Capital does not buy capacity: daily volume caps it.**
- A $50-200k/day pair offers about $6.5-19k/day of maker flow at a 10% share. Even a +2 bp net edge on that is **$1-4 per day**.
- Larger orders only get filled by larger sweeps, and in the pilot those were the most adversely selected.

**7. Verdict.**
- The archive is a usable, *conservative* testbed for passive quoting on illiquid Binance spot pairs, provided:
  - fills use the trade-through rule
  - markouts are read at ≥60 s
  - quoted spreads on fine-tick pairs are not trusted
- It is **not** a faithful testbed for the venues a US resident can use, whose books and fees differ.
- For a US-venue test, record Coinbase/Kraken order-book feeds forward (section 7).

---

## 1. What the archive contains

Archive listings read this session from `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=...`, following the pattern already used by `analysis_2026/fetch_regime_data.py`. All entries are [D/A].

| Market | Dataset (daily and/or monthly) | Symbols | Date range (BTC unless noted) | Columns (header?) | Time unit |
|---|---|---|---|---|---|
| Spot | `trades` | 3,750 | 2017-08-17 to 2026-10-16 | id, price, qty, quoteQty, time, isBuyerMaker, isBestMatch (no header) | ms to 2024-12-31; **µs from 2025-01-01** (checked: 2024-12-31 file ms, 2025-01-01 file µs) |
| Spot | `aggTrades` | 3,750 | same | aggId, price, qty, firstId, lastId, time, isBuyerMaker, isBestMatch (no header) | µs from 2025 |
| Spot | `klines` 1s, 1m … 1d | 3,742 | 1s from 2017-08-17 (BTC), 2020-09-04 (KSM) to 2026-10-16 | open time, OHLC, volume, close time, quote volume, #trades, taker-buy base/quote, ignore (no header) | µs from 2025 |
| Spot | **no** bookTicker / depth | – | – | – | – |
| USD-M futures | `trades` | 1,052 | 2019-09-08 to 2026-10-16 | id, price, qty, quote_qty, time, is_buyer_maker (header) | ms |
| USD-M | `aggTrades`, `klines`, mark/index/premium klines | ~1,000 | to 2026-10-16 | header | ms |
| USD-M | **`bookTicker`** (every best-bid/ask change) | 315 | **2023-05-16 to 2024-03-30**; 283/315 symbols end 2024-03-30, the rest earlier; monthly zips to 2024-04 (partial) | update_id, best_bid_price, best_bid_qty, best_ask_price, best_ask_qty, transaction_time, event_time | ms |
| USD-M | `bookDepth` | 1,008 (793 current) | 2023-01-01 (183 symbols) to 2026-10-16 | timestamp, percentage, depth, notional: **30-s snapshots** of cumulative depth at ±1,2,3,4,5% (±0.2% added between 2025-12 and 2026-03) | s |
| USD-M | `metrics` | 1,038 | 2020-09-01 to 2026-10-16 | 5-min open interest, top-trader and account long/short ratios, taker buy/sell volume ratio | s |
| USD-M | `fundingRate` (monthly) | – | – | – | – |
| COIN-M futures | trades, aggTrades, klines, `bookTicker`, `bookDepth`, metrics, `liquidationSnapshot` | 272 trades; 120 bookTicker | bookTicker 2023-05-18 to **2024-10-14** (BTCUSD_PERP; 58/120 symbols end then) | as USD-M | ms |
| Options | `BVOLIndex`, `EOHSummary` | 2-5 | – | – | – |

**Notes:**
- **isBestMatch** was True on every print checked. [D]
- **What `bookTicker` really records.** On all 17 validation symbols (fact-check rerun; the original run used 8), the best price strictly before each taker order equals that order's first fill price in **96.6-99.8%** of taker orders. [D]
  - Shifting the book 5 ms earlier drops the match to 78-98%. So the file is time-aligned at the millisecond, and the book changes within milliseconds.
  - Update gaps: p99 0.1-8.5 s, max 4-50 s.
  - Size: XVSUSDT had 406,618 updates on 2024-03-29. BTCUSDT's daily zip was 120 MB that day (88-267 MB over 2024-03-20..30).
- **Survivorship.** The spot listing keeps delisted symbols: 765 USDT prefixes (3,750 in all) vs 504 USDT pairs that traded on all of 2026-10-10..16. So survivorship can be avoided. [D]
- **Tokenized stocks.** Dozens of Binance spot pairs that look like tokenized US stocks/ETFs now trade 24/7, e.g. AAPLBUSDT, NVDABUSDT, SPYBUSDT, QQQBUSDT, HOODBUSDT. [D for the listings; U for the issuer and structure, not checked]
  - They are the closest crypto-venue analogue to "low-volume stocks", but they are not available to US persons either.

---

## 2. Liquidity ladder (pilot universe)

- **Universe.** All 765 USDT spot prefixes were tried for daily klines on 2026-10-10..16.
  - 504 pairs traded all 7 days.
  - Median daily quote volume: 14 pairs under $50k, 58 at $50-200k, 224 at $0.2-1M, 125 at $1-5M, 71 at $5-50M, 12 above $50M. [D]
- **Exclusions:** stablecoins, wrapped/staked tokens and tokenized stocks. One stock token, HOODBUSDT, was kept as a curiosity.
- **Choice of pairs** within each band: picked for a spread of price levels and tick sizes. They were not chosen at random; the pre-registered test should draw them at random (section 8).

| Band (median $ quote vol/day) | Pairs (7-day mean $/day) |
|---|---|
| A $50-200k | GNOUSDT 65k, XVSUSDT 106k, REQUSDT 129k, KNCUSDT 193k |
| B $0.2-1M | KSMUSDT 303k, SUSHIUSDT 559k, COMPUSDT 922k |
| C $1-5M | TRBUSDT 1.37M, RUNEUSDT 1.79M, GALAUSDT 1.84M, ETCUSDT 3.04M |
| D $5-50M | ATOMUSDT 7.7M, LTCUSDT 17.2M, LINKUSDT 23.4M |
| BTC | BTCUSDT 1.16B |
| tokenized stock | HOODBUSDT 387k |

- **Files:** 112 pair-days, 167 MB, in `data/scalping/binance_pilot/spot_trades/` (gitignored).
- **The full volume table** is `data/scalping/binance_pilot/results/usdt_pairs_7d_volume_2026-10-10_16.csv`.

---

## 3. Pilot results: spot spreads, tick sizes and markouts (2026-10-10 to 10-16)

**Method** (`code/microstructure.py`):
- Consecutive prints with the same timestamp and side form one taker order.
- **Implied bid / ask** = last price of the latest seller- / buyer-initiated order. It counts as valid only if ask > bid and both sides printed within 300 s.
- **Effective half-spread** = maker side × (pre-trade implied mid − price) / mid.
- **Realized spread at +h** = maker side × (implied mid at t+h − price) / mid. This is the maker's P&L marked at t+h, before fees.
- **Adverse move** = effective half-spread − realized spread.
- **Averages** are $-weighted over all prints (every print has a maker), i.e. the *average resting order*.
- **Tick** = gcd of the gaps between distinct prices.

All entries are [D].

| Pair | Band | $/day | Trades/h | Median trade $ | Tick (bp) | Median quoted spread, bp (ticks) | Eff. half-spread (bp) | RS +1 s | RS +10 s | RS +60 s ± SE | RS +300 s ± SE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GNOUSDT | A | 65k | 79 | 15 | 0.87 | 20.7 (23.8) | 12.6 | +9.1 | +5.8 | +5.2 ± 1.4 | +2.7 ± 1.6 |
| XVSUSDT | A | 106k | 180 | 11 | 3.28 | 12.6 (3.8) | 8.6 | +6.5 | +4.8 | +0.4 ± 1.8 | −3.0 ± 1.9 |
| REQUSDT | A | 129k | 103 | 14 | 19.4 | 38.4 (2.0) | 32.1 | +19.5 | +11.7 | +5.5 ± 1.5 | +12.3 ± 8.2 |
| KNCUSDT | A | 193k | 107 | 23 | 8.0 | 15.9 (2.0) | 11.1 | +8.4 | +5.4 | −1.5 ± 3.3 | −4.2 ± 3.4 |
| KSMUSDT | B | 303k | 163 | 18 | 22.2 | 21.5 (1.0) | 14.5 | +8.5 | +5.0 | +3.9 ± 1.3 | −1.8 ± 2.1 |
| SUSHIUSDT | B | 559k | 453 | 15 | 4.4 | 13.2 (3.0) | 8.6 | +5.8 | +3.6 | −1.4 ± 1.1 | −3.1 ± 1.3 |
| COMPUSDT | B | 922k | 322 | 72 | 4.5 | 8.7 (1.9) | 5.0 | +3.1 | +2.3 | −0.2 ± 0.3 | −1.6 ± 1.0 |
| TRBUSDT | C | 1.37M | 590 | 19 | 5.4 | 10.6 (1.9) | 7.6 | −6.6 | −8.6 | −9.6 ± 7.1 | −1.2 ± 5.8 |
| RUNEUSDT | C | 1.79M | 646 | 18 | 15.6 | 15.3 (1.0) | 7.0 | +6.8 | +4.6 | +1.4 ± 0.8 | +2.9 ± 0.7 |
| GALAUSDT | C | 1.84M | 1,006 | 19 | 4.9 | 9.0 (1.8) | 6.5 | +2.8 | +1.0 | −2.1 ± 1.3 | −0.4 ± 0.8 |
| ETCUSDT | C | 3.04M | 833 | 24 | 12.5 | 12.4 (1.0) | 6.6 | +5.5 | +4.3 | +3.0 ± 1.1 | +2.1 ± 1.0 |
| ATOMUSDT | D | 7.7M | 2,178 | 33 | 5.6 | 5.9 (1.1) | 6.5 | −0.6 | −2.3 | −2.6 ± 0.6 | −4.1 ± 1.3 |
| LTCUSDT | D | 17.2M | 5,686 | 8 | 1.7 | 1.7 (1.0) | 2.5 | −0.1 | −0.9 | −1.0 ± 0.4 | −0.6 ± 0.6 |
| LINKUSDT | D | 23.4M | 9,248 | 8 | 0.81 | 2.3 (2.9) | 2.1 | +0.4 | −0.7 | −0.9 ± 0.1 | −0.7 ± 0.3 |
| BTCUSDT | BTC | 1.16B | 108,595 | 6 | 0.001 | 0.06 (49) | 0.4 | −0.5 | −0.9 | −0.9 (n/a) | −0.7 (n/a) |
| HOODBUSDT | stock token | 387k | 257 | 12 | 1.0 | 5.8 (5.7) | 6.2 | +2.5 | +0.9 | −1.5 ± 2.1 | −2.5 ± 2.6 |

**Band averages** (simple mean of pairs; bp):

| Band | Quoted spread | Eff. half-spread | RS +1 s | RS +10 s | RS +60 s | RS +300 s | Adverse move by +300 s |
|---|---|---|---|---|---|---|---|
| A $50-200k | 21.9 | 16.1 | +10.9 | +6.9 | +2.4 | +1.9 | 14.6 |
| B $0.2-1M | 14.5 | 9.4 | +5.8 | +3.7 | +0.8 | −2.2 | 11.2 |
| C $1-5M | 11.8 | 6.9 | +2.1 | +0.3 | −1.8 | +0.8 | 6.3 |
| D $5-50M | 3.3 | 3.7 | −0.1 | −1.3 | −1.5 | −1.8 | 5.5 |
| BTC | 0.06 | 0.4 | −0.5 | −0.9 | −0.9 | −0.7 | 1.1 |

**Reading the tables:**
- **Ticks are coarse.** Most illiquid and mid pairs have a 3-22 bp tick. KSM, RUNE, ETC, ATOM and LTC sit at a one-tick spread most of the time, so queue priority, not price, decides who earns the spread.
  - Fact-check, recomputed in tick units: one tick on 77-85% of valid prints for KSM, RUNE and ETC, and 53% for ATOM and LTC.
  - The `one_tick_share` column in `results/spot_pilot.csv` (0.08-0.37) is wrong. It compares bp against the last-price tick with a 2% tolerance. Do not use it.
- **Wide-spread pairs leave room to step inside.** GNO (24 ticks) and XVS/SUSHI (3-4 ticks) are wide enough to improve the price by a tick.
- **Spreads shrink with liquidity, but so does the edge.** Spreads and effective half-spreads fall monotonically with liquidity. Within 5 minutes, adverse moves take back about 90% of the effective half-spread in bands A and C, and more than 100% in B, D and BTC.
- **Short horizons flatter the maker.** The flattering +1 s and +10 s numbers are partly estimator bias (section 4) and partly drift that has not yet arrived.
- **Daily noise is large.** For example, REQ's +300 s realized spread ranged from −13.6 to +36.8 bp across the seven days. One week cannot separate a 2 bp edge from zero.

### Naive resting quote (the friend's "buy at the bid, sell at the ask", without inventory management)

**Setup** (`code/spot_fill_sim.py`):
- Every 60 s, place a bid and an ask at the implied best price; leave them for 60 s.
- Size: $1k or $10k per side.
- Fill size = min(order, qualifying aggressor volume).
- Each fill is marked to the implied mid 5 minutes later. No fees.

All entries are [D].

| Band | Rule | Fill rate per 60-s quote | Mean P&L per fill (bp) | $-weighted P&L @ $1k (bp) | @ $10k (bp) | Filled $/day @ $1k | Gross $/day @ $1k | @ $10k |
|---|---|---|---|---|---|---|---|---|
| A | join, trade-through | 0.10 | −7.4 | −19.2 | −19.6 | 23.7k | −38 | −62 |
| A | join, touch (optimistic) | 0.20 | +1.7 | −10.9 | −14.7 | 37.4k | −36 | −73 |
| A | improve 1 tick, touch | 0.18 | −5.2 | −16.6 | −15.1 | 15.8k | −19 | −24 |
| B | join, trade-through | 0.19 | −9.7 | −15.7 | −18.6 | 93k | −93 | −200 |
| B | join, touch | 0.30 | −2.5 | −7.8 | −11.3 | 135k | −88 | −204 |
| C | join, trade-through | 0.20 | −7.7 | −11.5 | −15.1 | 132k | −102 | −342 |
| C | join, touch | 0.43 | −1.0 | −3.7 | −7.4 | 292k | −71 | −311 |
| D | join, trade-through | 0.53 | −3.5 | −5.0 | −7.8 | 857k | −284 | −1,807 |
| D | join, touch | 0.71 | −1.3 | −3.1 | −5.9 | 1.12M | −244 | −1,803 |
| BTC | join, trade-through | 0.59 | −1.5 | −1.5 | −1.5 | 1.63M | −229 | −2,365 |
| BTC | join, touch | 0.93 | −0.3 | −0.5 | −0.7 | 2.44M | −112 | −1,583 |

**Two lessons:**
1. **The naive quote does worse than the average maker.** That average includes faster participants who cancel ahead of moves.
2. **The fills that matter in dollars are the bad ones.** Equal-weighted, the optimistic rule shows about +2 bp per fill in band A. Weighted by dollars filled, it shows −11 to −15 bp, because only a large aggressive order fills a $1k-10k quote in a pair whose median print is $15.

**Size makes it worse, not better.** Under both join rules, raising the order size from $1k to $10k makes the band-mean P&L per dollar worse in every band.
- In band A the change is small under trade-through (−19.2 → −19.6 bp).
- 3 of the 32 pair × rule cells improve with size, all in band A: GNO and REQ under trade-through, GNO under touch.

---

## 4. How good are trades-only estimates? Validation against the true book (USD-M futures, 2024-03-29)

**Setup.** On 17 USD-M symbols ($1.6M to $13B/day), the same trades-only estimators were run on the futures prints and compared with `bookTicker`. "Bias" means estimate − truth on the same prints, in bp. All entries are [D].
- **Exception (fact-check):** in the effective half-spread column, the truth is averaged over *all* prints, while the estimate covers only the prints with a valid implied quote.
- On matched prints, 7 symbols were rechecked: the bias is 0.3-1.1 bp rather than 0.3-1.0 (e.g. DEFI +0.29 vs +0.62, HFT +1.08 vs +1.00).

**Fill-rule columns:**
- **Queue** = full queue model from the true book: join the back of the queue at the best price; fill when prints at that price exceed the displayed size ahead, or on any trade-through. Cancellations ahead are ignored, so even this is conservative.
- **Through** = trade-through at the true best price.
- **Est** = trade-through at the trades-only implied best price.
- **Touch** = any print at or through the true best price.

**Placement in the fill-rule simulation:**
- Every 10 s, at the best bid and the best ask.
- Life 60 s; $500 order.
- P&L = 60-s markout to the true mid.

| Symbol | $/day | Tick (bp) | True spread (time-weighted median, bp) | Trades-only est. (bp) | Size at best ($, median) | Bias: eff. half-spread | Bias: RS +1 s | +10 s | +60 s | +300 s | Fill rate: queue / through / est / touch | P&L per fill +60 s (bp): queue / through / est / touch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEFIUSDT | 1.6M | 0.75 | 0.75 | 3.01 | 97 | +0.62 | +1.26 | +0.43 | −0.13 | +0.17 | 0.62 / 0.62 / 0.62 / 0.71 | −3.2 / −3.2 / −3.9 / −2.3 |
| BTCDOMUSDT | 2.8M | 0.44 | 0.44 | 1.32 | 332 | +0.34 | +1.21 | +0.87 | +0.20 | +0.10 | 0.41 / 0.40 / 0.43 / 0.60 | −1.8 / −1.8 / −2.2 / −1.0 |
| OXTUSDT | 5.0M | 0.65 | 1.97 | 3.92 | 44 | +0.60 | +1.55 | +0.42 | −0.04 | −0.18 | 0.68 / 0.68 / 0.64 / 0.76 | −2.7 / −2.7 / −3.2 / −1.8 |
| DGBUSDT | 5.9M | 7.10 | 7.03 | 7.16 | 983 | +0.62 | +2.65 | +1.26 | −0.03 | +0.02 | 0.40 / 0.37 / 0.41 / 0.77 | −5.4 / −6.1 / −6.4 / **+0.8** |
| ORBSUSDT | 6.5M | 2.17 | 2.18 | 4.35 | 255 | +0.82 | +1.67 | +0.64 | +0.04 | +0.14 | 0.59 / 0.58 / 0.56 / 0.76 | −3.5 / −3.7 / −3.9 / −1.5 |
| XVSUSDT | 6.9M | 0.62 | 0.63 | 3.74 | 80 | +0.56 | +1.23 | +0.44 | −0.17 | +0.13 | 0.67 / 0.67 / 0.63 / 0.76 | −3.2 / −3.2 / −3.4 / −2.2 |
| HFTUSDT | 9.4M | 2.18 | 2.22 | 4.41 | 324 | +1.00 | +2.20 | +0.87 | +0.08 | +0.01 | 0.65 / 0.64 / 0.63 / 0.79 | −3.3 / −3.5 / −3.8 / −1.3 |
| KNCUSDT | 13.2M | 1.11 | 1.11 | 3.32 | 225 | +0.83 | +1.52 | +0.35 | +0.07 | −0.01 | 0.72 / 0.71 / 0.67 / 0.82 | −2.9 / −3.0 / −3.3 / −1.6 |
| STPTUSDT | 15.6M | 1.25 | 2.45 | 4.95 | 112 | +0.88 | +1.79 | +0.56 | −0.07 | −0.00 | 0.70 / 0.69 / 0.63 / 0.79 | −3.2 / −3.3 / −3.5 / −1.9 |
| KSMUSDT | 26.3M | 2.03 | 2.04 | 4.01 | 601 | +0.93 | +1.51 | +0.20 | +0.04 | +0.04 | 0.71 / 0.70 / 0.67 / 0.83 | −3.4 / −3.6 / −4.0 / −1.5 |
| COMPUSDT | 53.3M | 1.26 | 1.26 | 2.53 | 479 | +0.55 | +0.76 | −0.01 | −0.02 | −0.01 | 0.79 / 0.78 / 0.75 / 0.87 | −2.5 / −2.6 / −2.8 / −1.2 |
| RUNEUSDT | 84.7M | 1.10 | 1.10 | 2.17 | 1,482 | +0.52 | +0.78 | −0.04 | +0.00 | −0.02 | 0.80 / 0.79 / 0.77 / 0.89 | −1.8 / −1.9 / −2.0 / −0.7 |
| ATOMUSDT | 157M | 0.81 | 0.81 | 1.61 | 2,060 | +0.49 | +0.78 | −0.06 | +0.02 | +0.00 | 0.82 / 0.80 / 0.79 / 0.90 | −1.8 / −1.9 / −1.9 / −0.8 |
| LINKUSDT | 214M | 0.53 | 0.53 | 1.05 | 3,583 | +0.32 | +0.59 | +0.00 | +0.01 | −0.03 | 0.82 / 0.81 / 0.79 / 0.91 | −1.5 / −1.6 / −1.6 / −0.6 |
| ETCUSDT | 345M | 0.30 | 0.30 | 1.45 | 878 | +0.31 | +0.33 | +0.00 | +0.01 | +0.02 | 0.86 / 0.85 / 0.83 / 0.91 | −1.7 / −1.8 / −1.8 / −1.0 |
| LTCUSDT | 1.16B | 0.96 | 0.97 | 1.07 | 4,547 | +0.07 | +0.08 | −0.02 | −0.02 | −0.00 | 0.87 / 0.85 / 0.84 / 0.95 | −1.7 / −1.9 / −1.9 / −0.3 |
| BTCUSDT | 13.2B | 0.001 | 0.014 | 0.014 | 141,679 | −0.06 | +0.01 | −0.00 | −0.00 | −0.00 | 0.85 / 0.83 / 0.83 / 0.97 | −0.8 / −0.9 / −0.9 / −0.1 |

**What this establishes:**
- **Markouts.** Trades-only realized spread at **+60 s and +300 s is unbiased** (|bias| ≤0.2 bp, median 0.02-0.04 bp).
  - At +10 s it is too rosy by up to 1.3 bp, and at +1 s by up to 2.7 bp. **Pre-register 60 s and 300 s as the primary horizons.**
  - The effective half-spread is too high by up to 1.0 bp (0.3-1.0 bp outside LTC and BTC). On matched prints it is up to about 1.1 bp (see Setup).
- **Quoted spread.** The trades-only estimate is about 2× the truth (up to 4× on DEFI) when the true spread is one fine tick, because it mixes in short-term price moves. It is exact when the tick is coarse (DGB 7 bp: 7.16 vs 7.03).
  - On the spot pairs, shrinking the freshness window from 300 s to 1 s changes the estimate by −35% to +2%: GNO 20.7 → 16.5, SUSHI 13.2 → 8.6, KSM 21.5 → 20.3, ETC 12.4 → 12.7 bp (up). Only 3-5% of these pairs' prints qualify at 1 s (fact-check rerun; the 2-19% given earlier does not match the spot run).
  - So the quoted-spread figures in section 3 are best read as **upper bounds**, roughly right for the coarse-tick pairs.
- **Fill rules.** Mean over the 17 symbols:
  - **Trade-through on implied prices** (the only rule usable on spot): fill rate 0.68 vs 0.70 for the queue model. P&L per fill is 0.35 bp *worse* (range −0.08 to −0.97). It is a slightly pessimistic, nearly unbiased proxy for the queue model.
  - **Touch:** fill rate 0.82, P&L per fill 1.5 bp *better* (range +0.7 to +6.2; worst on the coarse-tick DGB, where "touch" turns a −5.4 bp queue result into +0.8 bp). Use touch only as an upper bound.
- **Joining the best price and waiting loses money even in futures.** It loses 0.8-5.4 bp per fill at +60 s before fees, on every symbol, under the queue model. The best-bid queue was small: median $44-$1,000 on the seven symbols under $10M/day.
- **Limit of the validation.** Even the thinnest USD-M contracts ($1.6M/day) trade at 1-3 tick spreads, with a $44-1,000 queue at the best price and ~1 print per 1-4 s. Spot band A has 10-40 bp spreads and ~2 prints per minute.
  - The validation therefore covers *thin-but-active* books. Carrying its biases over to the thinnest spot pairs is an assumption, and it should be stated as one in the pre-registration.

---

## 5. Fill modelling for a resting quote, from trades alone

**Proposed hierarchy.** Pre-register F1 as primary, F2 as an upper bound, F3 for step-inside quotes and F4 as sensitivity. All rules use only aggressor prints on the side that would hit us.

| Code | When the quote is filled | Size | Bias (from section 4) |
|---|---|---|---|
| **F1 trade-through (primary)** | a print strictly through our price (below our bid / above our ask) | min(order, through-volume) | ≈ queue model, −0.35 bp/fill (pessimistic) |
| F2 touch (upper bound) | any print at or through our price | min(order, at+through volume) | +1.5 bp/fill mean, up to +6 bp in coarse-tick books (optimistic) |
| F3 step-inside | we quote one tick better than the implied best; we are then alone and first at that level, so any print at or through the *old* best fills us | min(order, that volume) | ignores rivals who would also step in or match us |
| F4 queue haircut | fill = φ × volume printed at our price after an assumed queue ahead Q is consumed, plus all through-volume | – | φ, Q calibrated on futures `bookTicker` (e.g. Q = median size at best ÷ median print) |

**Mechanics to fix in advance:**
- Decisions see data up to t − Δ. New quotes and cancels become active at t + Δ, with Δ = 250 ms (1 s as sensitivity).
- No fill on the print that set the implied price. No more than one fill per aggressor order.

**What futures `bookTicker` adds** (2023-05-16 to 2024-03-30 only):
- the exact best bid/ask, the true spread and mid
- the displayed size at the best price, so the queue ahead when we join is known
- a FIFO queue position: queue ahead falls with prints at our price; cancels are unknown, so assume none (conservative) or a pro-rata share (sensitivity)
- detection of price-level changes, so a quote can be repriced when it falls behind the new best

Use it to calibrate F4 and to measure each rule's bias on the thinnest futures. It cannot validate spot directly: different market, different participants, and the data is two years old.

**What `bookDepth` adds:** only 30-s cumulative depth at ±0.2% (added between 2025-12-01 and 2026-03-01) and ±1-5%. That is enough to cap order size against depth (e.g. ≤10% of ±0.2% depth) and to model a forced taker exit. It shows nothing about queue position.

---

## 6. Fees, access and break-even

### Who can use what (US resident)

**Binance.com — not available**
- US persons are barred; Binance offboards accounts it identifies as US. [S] ([The Block 2020](https://www.theblock.co/post/85589/binance-blocking-us-users-14-day-deadline-new-email); [binance.org terms](https://www.binance.org/static/disclaimers.html))
  - Fact-check: binance.org is the BNB Chain site, not Binance.com. Binance.com's own Terms of Use (restricted locations) were not retrieved. [U]
- Binance pleaded guilty in Nov 2023 to US charges that included serving US users. [U]

**Binance.US — available outside restricted states [A]** ([terms](https://www.binance.us/terms-of-use)); the state list was not checked [U]
- **Fees:** **0% maker / 0.02% taker** on all Advanced spot pairs from 2026-04-22. Select pairs (e.g. BNB/USD) are 0% / 0.01%, with a further 5% off for paying in BNB. [A] ([Binance.US blog](https://blog.binance.us/zero-fee-trading/)); [S] ([Cointelegraph](https://cointelegraph.com/news/binance-us-cuts-spot-trading-fees-to-near-zero-in-push-to-undercut-rivals))
- **Liquidity:** volumes are described as "abysmal". [S] ([The Block](https://www.theblock.co/post/370097/crypto-exchange-binance-us-cuts-fees-as-trading-volumes-remain-abysmal))
- **No public trade archive** was found. [U]

**Coinbase Advanced — available**
- **New schedule from 2026-09-16:**
  - US entry tier 0.50% maker / 0.90% taker; tiers start at $10K; spot and derivatives volume combined.
  - Top tier reported at 0 maker / 2 bp taker.
  - [S] ([PrimeXBT](https://primexbt.com/news/coinbase-cuts-advanced-platform-trading-fees-and-lowers-volume-threshold/); [CryptoDaily](https://cryptodaily.co.uk/2026/09/coinbase-advanced-fees-usdc-vip-tiers))
- **Old schedule:** 0.40% / 0.60% entry. [U: conflicting]
  - Fact-check, from memory: 0.40% / 0.60% was the 2022-23 $0-10K tier. The 2024-26 entry tier was 0.60% / 1.20% (<$1K).
  - The cited headline says Coinbase *cut* fees. That fits a move from 0.60% / 1.20% to 0.50% / 0.90%, but not one from 0.40% / 0.60%.
- **Middle tiers:** not retrieved. [U]

**Kraken Pro — available**
- **From 2026-07-09:** 0.40% maker / 0.80% taker entry; 0.22% / 0.38% from $10K; 0% / 0.10% from $10M. [S] ([BrokerChooser](https://brokerchooser.com/news/coinbase-vs-kraken-fee-structures-and-trading-features-compared--bbeea493); [Datawallet](https://www.datawallet.com/crypto/kraken-fees-explained))
- **Kraken's own page:** fees range from −0.02% (maker) to 0.80% (taker). [A] ([Kraken support](https://support.kraken.com/articles/201893638-fee-schedule))

**Robinhood Crypto — available**

| Robinhood exchange-routing tier (30-day volume) [A] | Taker | Maker |
|---|---|---|
| $0-10K | 0.95% | 0.50% |
| $10K-50K | 0.75% | 0.35% |
| $50K-250K | 0.25% | 0.125% |
| $250K-500K | 0.15% | 0.075% |
| $500K-1M | 0.125% | 0.06% |
| $1M-5M | 0.10% | 0.04% |
| $5M-10M | 0.04% | 0.02% |
| $10M-25M | 0.03% | 0.01% |
| $25M+ | 0.03% | 0.00% |

- **Source:** the RHC fee schedule PDF, document ID dated 2026-06-22. [A] ([PDF](https://cdn.robinhood.com/assets/robinhood/legal/rhc-fee-schedule.pdf); [fee tiers page](https://robinhood.com/us/en/support/articles/crypto-fee-tiers))
- **Exchange routing** is used on Legend. Default market-maker routing carries no stated commission, but Robinhood receives $0.95 per $100 from the market maker. [A] ([order routing](https://robinhood.com/us/en/support/articles/crypto-order-routing/))
- **Which route agent orders take is unknown.** [plan] (`AGENTIC_TRADING_PLAN.md`)
- **Coverage:** Robinhood lists mainly large coins [plan]. The illiquid bands studied here mostly do not trade there.

### Binance.com fees (relevant only as the archive's own venue)

- **Spot:**
  - VIP 0: 0.10% / 0.10%; 25% off when paying in BNB, i.e. 0.075%. [S] ([Bitdegree](https://www.bitdegree.org/crypto/tutorials/binance-fees); [Copi-tools](https://copi-tools.com/blog/binance-fees/))
  - VIP 1 (≥$1M/30 days): 0.09% / 0.10%. [S]
  - VIP 9: 0.012% / 0.024%. [U; one unreliable secondary page]
- **USD-M futures:** VIP 0 0.02% / 0.05%; VIP 9 0.00% / 0.017%. [S] ([Copi-tools](https://copi-tools.com/blog/binance-fees/)). One source gives 0.04% taker. [S]
- **Zero-maker FDUSD pairs:** introduced in 2023; the zero-fee BTC/FDUSD promotion ended 2024-04-25. [S] ([The Block](https://www.theblock.co/post/300748/fdusd-trading-dominance-persists-despite-binance-ending-zero-fee-promotion)). Current zero-fee pairs are unknown. [U]

### Break-even: what a maker must earn per fill

Notation: f_m = maker fee and f_t = taker fee, per side, in bp. The three columns are what each round-trip style needs, in bp, before adverse selection:
- **Both legs passive:** needs a realized spread per fill > f_m, i.e. a quoted spread ≥ 2·f_m + 2·adverse move.
- **Passive entry, taker exit:** needs the mid to move in your favour by ≥ f_m + f_t plus the half-spread paid on exit.
- **Taker both legs:** 2·f_t.

| Venue / tier | f_m / f_t (bp) | Both legs passive | Passive entry, taker exit | Taker both legs | Viable vs pilot? |
|---|---|---|---|---|---|
| Binance.US (2026) | 0 / 2 | 0 | 2 | 4 | the only zero-maker fee with no volume tier needed (Coinbase top, Kraken $10M+ and Robinhood $25M+ also have 0 maker); its own books are untested |
| Binance.com spot VIP 0 (BNB) | 7.5 / 7.5 | 15 | 15 | 15 | no: realized spread per fill ≤ +2 bp |
| Binance.com spot VIP 0 | 10 / 10 | 20 | 20 | 20 | no |
| Binance USD-M VIP 0 | 2 / 5 | 4 | 7 | 10 | no (naive futures quote: −0.8 to −5.4 bp/fill) |
| Kraken $10M+ | 0 / 10 | 0 | 10 | 20 | maker-only, possibly |
| Kraken $10K | 22 / 38 | 44 | 60 | 76 | no |
| Kraken entry | 40 / 80 | 80 | 120 | 160 | no |
| Coinbase top tier | 0 / 2 | 0 | 2 | 4 | if reachable (needs very large volume) |
| Coinbase US entry (2026-09) | 50 / 90 | 100 | 140 | 180 | no |
| Robinhood $25M+ | 0 / 3 | 0 | 3 | 6 | only at $25M+/30 days |
| Robinhood $10M-25M | 1 / 3 | 2 | 4 | 6 | marginal |
| Robinhood $1M-5M | 4 / 10 | 8 | 14 | 20 | no |
| Robinhood $50K-250K | 12.5 / 25 | 25 | 37.5 | 50 | no |
| Robinhood $0-10K | 50 / 95 | 100 | 145 | 190 | no |
| Robinhood default route | ~95 spread | – | – | ~190 | no |

**How this compares with the pilot:**
- **Best case:** the pilot's average-maker realized spread is about +2 bp at +300 s, in band A, statistically indistinguishable from zero.
- **Naive quoting:** −1.5 (BTC) to −20 bp.
- **Implication:** only fee rates of 0 to 1 bp per fill even make the question interesting.
- **Volume tiers are a catch-22.** Reaching them means trading $10-25M a month.
  - One illiquid pair cannot supply that at a realistic share: 10% of $65k-$3M a day is about $0.2-9M a month.
  - So the tier would have to be earned across many pairs at once, or in liquid coins at a loss.
  - Fact-check: the earlier wording ("illiquid pairs cannot supply that volume") overstated this. At a 10% share on Binance volumes, 2-3 band-C pairs or roughly 4-11 band-B pairs would reach $10M a month (US-venue volumes are lower).

---

## 7. Other venues' public archives (reachability from this sandbox, 2026-10-18)

| Source | Result | What is there |
|---|---|---|
| `public.bybit.com` | host blocked (curl 000), but **its S3 bucket is reachable path-style**: `https://s3-ap-southeast-1.amazonaws.com/public.bybit.com?prefix=...` [D] | `spot/<SYM>/` daily trades to 2026-10-16 (id, timestamp ms, price, volume, side (taker side [U]), rpi flag). `trading/<SYM>/` derivatives trades from 2020 to 2026-10-16 (timestamp, side, size, price, tickDirection, trdMatchID, …). Also `kline_for_metatrader4/`, `premium_index/`, `spot_index/`. **No order book.** |
| Bybit order-book history (quote-saver.bycsi.com) | blocked | L2 snapshots. [U] |
| OKX (`static.okx.com`, `www.okx.com/cdn`) | blocked (000) | daily trade archives. [U] |
| Coinbase (`api.exchange.coinbase.com`) | blocked (000) | no bulk archive. The REST API gives recent trades; the websocket `full` channel (order-by-order, L3) can be recorded forward. [U] |
| Kraken (`api.kraken.com`, support site) | blocked (000) | REST trades with full history paging. OHLCVT/trade CSVs are on Google Drive. [U] |
| Binance REST (`api.binance.com`, `data-api.binance.vision`) and `api.binance.us` | blocked (proxy 403) | exchangeInfo (exact tick sizes), live depth |
| Tardis.dev, Gemini, Bitstamp, Crypto.com, Hyperliquid API | blocked | – |
| `hyperliquid-archive` S3 | reachable, but **requester-pays** (AccessDenied for anonymous users) | L2 snapshots; would need an AWS account paying the egress |

**Implication.** For US-accessible venues, no historical book data can be downloaded here.
- **Faithful option:** record Coinbase Exchange L3 (and Kraken L2/L3) **forward** on the user's own machine for ≥4 weeks. L3 gives exact queue positions, so it is a better testbed than any trades-only archive.

---

## 8. Recommended pre-registrable test design

**Data and sample:**
- **Venue data:**
  - Primary: Binance spot `trades` (µs).
  - Calibration: USD-M `bookTicker` + `trades`, 2023-05-16 to 2024-03-30.
  - Optional forward track: own recording of Coinbase/Kraken books.
- **Universe:** USDT spot pairs.
  - **Exclude:** stablecoins, fiat, wrapped/staked tokens, tokenized stocks, and pairs listed for under 90 days.
  - **Keep:** pairs that later delist (the archive has them).
  - **Bands:** each month, assign pairs by the trailing 30-day median daily quote volume measured *before* that month: A $50-200k, B $0.2-1M, C $1-5M, D $5-50M.
  - **Draw:** 5 pairs per band at random with a fixed seed, plus BTCUSDT and ETHUSDT as liquid controls.
- **Period:** 2025-10-01 to 2026-09-30 (12 months, µs timestamps throughout).
  - Months 1-3 calibrate only the F4 haircut and the latency Δ.
    - Fact-check, design conflict to resolve before freezing: section 5 calibrates F4's φ and Q on futures `bookTicker` (2023-24), which spot months cannot supply, since spot has no book. Δ is fixed elsewhere at 250 ms / 1 s. State what months 1-3 actually tune, or make them a burn-in.
  - Months 4-12 are the frozen test.
  - No parameter search on the test months; the strategy grid below is fixed in advance.

**Quote placement** (all with an inventory cap):

| Code | Rule |
|---|---|
| Q1 | join the implied best bid and best ask |
| Q2 | step inside by one tick when the implied spread is ≥3 ticks (else Q1) |
| Q3 | quote one tick behind the best (wider, less adverse) |
| Q4 | mid ± k × trailing 1-h median spread, k ∈ {0.5, 1.0}, rounded to the tick |
| Q5 (the friend's rule) | buy passively at the bid; once filled, post a sell at the fill price + max(1 tick, current spread); exit as taker after T_max |

**Order size and inventory:**
- **Order size:** $250, $1k and $10k. Fill size is capped at qualifying aggressor volume × participation cap (100% primary, 25% sensitivity).
- **Inventory:**
  - |inventory| ≤ 3 × order size. At the cap, quote only the side that reduces inventory.
  - Taker flatten after T_max ∈ {5 min, 60 min}, and at 00:00 UTC each day.
  - Long-only variant: this matches a cash account that cannot short. [plan]

**Fill models:** F1 (primary), F2 (upper bound), F3 (Q2 only), F4 (sensitivity). Δ = 250 ms, plus 1 s as sensitivity.

**Fee scenarios** (f_m / f_t, bp):
- 0 / 2 (Binance.US)
- 0 / 3 (Robinhood $25M+)
- 2 / 5 (Binance futures VIP 0)
- 7.5 / 7.5 (Binance.com VIP 0 with BNB)
- 12.5 / 25 (Robinhood $50-250K)
- 40 / 80 (Kraken entry)
- 50 / 95 (Robinhood entry; Coinbase entry is 50 / 90 per section 6)

**Hypotheses:**
- **Primary.** H1: net P&L per $ traded > 0 for Q1 or Q2 under F1 at fee 0 / 2, in band A or B.
  - Test: one-sided, day-clustered (block bootstrap by day).
  - Holm correction over 2 bands × 2 strategies.
- **Kill rule.** If F2 (optimistic) is ≤0 at fee 0 / 2 in every band, stop: no fill model can rescue it.
- **Everything else is descriptive.**

**Metrics:**
- per $ traded: gross bp, fee bp, net bp
- net $ per day and its distribution across days; worst day
- maximum inventory and inventory P&L
- fill rate; share of the pair's volume taken
- markouts at 60 s and 300 s; separate attribution for taker-exit legs

**Capacity** (report per band):
- Filled $/day at each order size, and P&L $/day.
- Required: implied $/day at 5%, 10% and 25% shares of maker volume.
- Ceiling from the pilot volumes at a hypothetical +2 bp net edge and a 10% share:

| Band | $/day | 10% share | $/day at +2 bp |
|---|---|---|---|
| A | $65-193k | $6.5-19k | **$1-4** |
| B | $0.3-0.9M | – | **$6-18** |
| C | $1.4-3.0M | – | **$27-61** |
| D | $7.7-23M | – | **$155-470** |

- Capital beyond a few times the order size adds nothing.

**Robustness:** split by volatility tercile, weekday vs weekend, and listing age; tick-constrained pairs (spread ≈1 tick) vs wide-spread pairs (≥3 ticks).

**Fidelity statement** (pre-register it): results speak to Binance.com spot only. Transfer to Binance.US, Coinbase, Kraken or Robinhood books is untested. The forward L3 recording track is the only way to test those.

---

## 9. Caveats and open items

- **Spot quoted spreads are upper bounds** on fine-tick pairs (section 4). Exact tick sizes should come from `exchangeInfo`, which is blocked here; the price-grid gcd could overstate the tick if few price levels traded.
- **The validation covers thin-but-active futures books,** not 2-prints-a-minute spot pairs.
- **The futures validation is a single day** (2024-03-29). Extend it to ~20 days across the `bookTicker` window before freezing F4.
- **The pilot week is a single week.** Band means of ±2 bp are within noise: hour-clustered SEs at +300 s are 0.3-8 bp per pair (0.7-8 in bands A-C).
- **The naive-quote simulation ignores** inventory, cancel-on-signal logic and queue competition from our own presence. It answers "what does passively sitting at the best earn", not "what does a good market maker earn".
- **Fee schedules changed in 2026** (Binance.US April, Kraken July, Coinbase September). Re-check every rate before the backtest is frozen.

## Reproduction (data gitignored)

**Data:** `data/scalping/binance_pilot/`, 569 MB in total:
- `spot_trades/`: 112 zips
- `um_validation/`: 2024-03-29 bookTicker / trades / bookDepth for 17 symbols
- `results/`: the CSVs behind every table

**Code:** `data/scalping/binance_pilot/code/`:
- `s3ls.py`, `fetch.py` (checksum-verified download), `vol.py` (7-day kline volumes)
- `microstructure.py` (estimators)
- `spot_pilot.py`, `spot_se.py`, `spot_fill_sim.py`
- `um_validate.py`, `bt_consistency.py`, `stale_test.py`

Run them with `python3 -I`. If this test goes ahead, move them into `analysis_2026/`.
