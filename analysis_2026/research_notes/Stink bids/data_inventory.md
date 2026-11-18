# Stink bids: data inventory and feasibility

Research note for the stink-bid study, written 2026-11-18. The data run to 2026-11-17, the last complete UTC day.
It answers four questions for the design:

- which coins and venues have usable price history;
- how often a level far below the price was touched, and whether deep wicks are market-wide or coin-specific;
- how much traded below given levels during three sample crashes;
- what finer data (1-minute klines, trades) would cost to fetch.

**Ground rules followed.**

- Only coverage, counts and fill frequencies (how often a level was touched) were computed. No forward return,
  post-fill outcome, P&L or strategy result was computed on real data.
- No Robinhood tool was used. Nothing was committed or pushed.
- New code: `analysis_2026/fetch_stinkbid_data.py`. It imports the S3 helpers (`S3`, `get`, `s3_ls`) of
  `fetch_scalping_data.py` and the checksum-verified kline builder (`klines`, `_get_zip_csv`, `_dead_runs`) of
  `fetch_bb_data.py`, plus the exclusion lists and the Robinhood JSON parser of `scalp_crypto.py`. None of those files
  was edited.

**Source tags.** [A] computed here from Binance archive files. [S] secondary source (news, vendor or exchange page
seen through search results). [U] unverified.

**Timings.** Run times below are the container's own clock (process timers and file times). That clock advanced far
less than the elapsed session time, which suggests the container is paused between tool calls [U]. Treat the times
as active download time.

---

## 0. Bottom line for the design

1. **Data access works for Binance, and nothing else is reachable here.** The Binance public archive (through its S3
   bucket) has spot and USD-M klines at 1m/1h/1d, trade files (aggTrades) and futures metrics (open interest).
   - Every kline zip fetched was checked against its `.CHECKSUM` (sha256): 69,623 zips plus 2,624 repair zips,
     **0 failures** [A].
   - Built: daily spot klines for all 771 USDT pairs, hourly spot klines for the 486 candidates, daily perpetual
     klines for 76 Robinhood contracts, and trade files for 13 coin-days. Total 982 MB.
2. **Several "solid" coins have short Binance spot histories** (section 2.4) [A].
   - **HYPE: Binance spot only since 2026-09-24 (55 days).** This corrects the brief, which said HYPEUSDT spot 1m
     zips exist from 2025. Binance listed HYPE spot on 2026-09-24 [S]. Before that, Binance's only HYPE market is the
     USD-M perpetual, from 2025-05-30.
   - Also short: AERO (spot from 2026-07-17), MORPHO (2025-10-03), ASTER (2025-10-06), SKY (2025-09-17; MKR
     2020-07-23..2025-09-15 before the rebrand), SYRUP (2025-05-06), ONDO (2025-04-11), ORCA (2024-12-06).
   - For these the perpetual is often older (AERO 2024-12-04, MORPHO 2024-11-27, ONDO 2024-01-20) and is the only
     longer Binance record.
3. **A one-day stink bid rarely fills; a bid left for a month often does** (section 4) [A]. Pooled over the 24
   user-style coins, a bid placed at a daily close d% below that close:
   - was touched the **next day** on 7.3% of days at d = 10%, 1.0% at 20%, 0.3% at 30%, 0.1% at 40%;
   - was touched **within 30 days** in 67% of windows at 10%, 42% at 20%, 24% at 30%, 12% at 40%, 5.6% at 50%.
   - A month-long bid at 20% is rarely hit on day 1 (2.3% of touched windows). The first touch came a median 12 days
     after placement, and on the touch day the price fell 10% or more from the prior close in 63% of cases
     (section 4.3). Resting bids are mostly filled by a decline over days that ends in one sharp down day, not by a
     one-day wick from the placement price.
4. **Deep wicks are market-wide events, and there are few of them** (section 6) [A].
   - In the broad top-100 universe, 92% of all coin-day lows at least 25% below the prior close, and 91% of those at
     least 40% below, fell on the 6.1% of days when at least 10% of the other top-100 coins also fell 15% or more.
   - For the user-style coins the shares are 99% and 100%. All 38 of their coin-days at least 40% below the prior
     close came from **7 distinct days**, and all 21 at 50% from 3 days (2020-03-12, 2021-05-19, 2025-10-10).
   - There were 155 market-wide days in 2020-01..2026-11. 103 of them fell in 2020-2022, 6 in 2026.
   - The effective sample for deep fills is therefore a handful of crash days, not hundreds of fills.
5. **Binance spot prints deeper than a retail venue can at the extremes** (section 3.4) [A].
   - LINKUSDT traded at $0.0001 on 2020-03-12. On 2025-10-10, 282 of the eligible USDT pairs printed a daily low at
     least 60% below the prior close.
   - Binance called "zero" prices on 2025-10-10 a display problem [S], yet the archive's trades contain these prints.
   - Spot and perpetual lows of the same coin differed by 10 points or more on 45 coin-days.
   - Robinhood fills against its own ask or Bitstamp's book (see `mechanics.md`), so Binance-spot touch counts at
     30-40% and deeper are an upper bound for this user.
6. **At 40% below the prior close, large bids could have filled on Binance at two of the three sample crashes, but
   only within minutes** (section 7) [A].
   - 2025-10-10: at 40% below the prior close, $1.4M (NEAR), $2.5M (AAVE) and $29M (LINK) traded on Binance spot,
     with price at or below the level for 2-13 minutes in total. SOL never got 30% down.
   - 2021-05-19: $3.3M-57M traded at or below the 40% level per coin, within 6-39 minutes with a trade there.
   - 2024-08-05: no sample coin reached 30% down.
   - Only an order already resting could have caught these. Nobody reacts within a 2-minute window by hand.
7. **Finer data is feasible only for event days** (section 8) [A].
   - 1-minute spot klines for all 486 candidates since 2020: 25.3 GB zipped (about 92 GB as CSV), more than this
     container's 30 GB of free disk. For the 75 Robinhood coins: 5.2 GB. For the 155 market-wide days only: 1.6 GB.
   - Trades (aggTrades) on the 155 market-wide days: 53 GB zipped for all candidates, 13.7 GB for the user-style
     coins. They must be streamed (download, reduce, discard), not stored.

---

## 1. What was built

All files are under the gitignored `data/stinkbid/` (982 MB).

| path | contents | files | size |
|---|---|---|---|
| `ref/spot_usdt_pairs.csv` | all 776 USDT spot pairs in the archive: first/last monthly 1d file, exclusion reason | 1 | |
| `ref/universe_monthly.csv` | set (b): monthly ranking 2020-01..2026-11 by 90-day median USDT volume | 1 | |
| `ref/candidates.csv` | union of (a), (b), (c): membership flags, (a) tags, predecessor tickers, dropped (c) coins | 1 | |
| `ref/um_contracts.csv` | names of the 1,080 USD-M contracts in the archive | 1 | |
| `d1_spot/{SYM}.parquet` | spot 1d klines, 2019-10-01 (3-month warm-up for the ranking) or listing .. 2026-11-17 | 771 | 60 MB |
| `d1_spot_all.parquet` | the same stacked, plus `sym` and `day` (tz-naive UTC date): 851,635 pair-days | 1 | 35 MB |
| `h1_spot/{SYM}.parquet` | spot 1h klines, 2020-01-01 (or listing) .. 2026-11-17 23:00: 15,838,161 bars | 486 | 781 MB |
| `d1_um/{COIN}.parquet` | USD-M perpetual 1d klines for the Robinhood coins (75, plus LIT, dropped later; 1000x contracts rescaled to one coin) | 76 | 7.9 MB |
| `coverage/coverage.csv`, `daily_sizes.parquet` | per candidate: listing dates, 1m / aggTrades / metrics coverage; size of 1,366,138 daily zips | 2 | 7.4 MB |
| `validation/*.csv`, `summary.txt` | gaps, outages, discontinuities, spike prints, spot vs perp lows | 9 | |
| `desc/*.csv`, `summary.txt` | the counts in sections 4-6 | 9 | |
| `events/{DATE}_{SYM}_{spot,um}.parquet`, `levels.csv` | the event day's aggTrades (time, price, qty, is_buyer_maker) and the level table of section 7 | 13 + 2 | 91 MB |
| `sizes/estimates.csv`, `throughput.json` | section 8 | 2 | |
| `stats/{d1,h1,perp1d}.json` | per series: zips, sha256-verified zips, failures, holes filled, days repaired, bars trimmed | 3 | |

**Columns.** Klines: `open_time` (UTC, bar open), `open, high, low, close`, `volume` (base units), `quote_volume`
(USDT), `trades`, `taker_buy_quote`; float64 / int64. aggTrades: `time` (UTC, microseconds), `price`, `qty`,
`is_buyer_maker` (True = the buyer's order was resting, so a seller hit a bid).

**How the klines were built** (all from `fetch_bb_data.klines`):

- monthly zips up to 2026-10 and daily zips for 2026-11-01..17;
- each zip's sha256 compared with its `.CHECKSUM`;
- bars missing from a monthly zip filled from that day's daily zip;
- every UTC day of hourly bars checked against the archive's 1d kline (OHLC to 1e-9), and a mismatched day replaced
  by its daily zip when that zip agrees;
- leading and trailing zero-trade placeholder bars trimmed.

Spot timestamps switched from milliseconds to microseconds on 2025-01-01 ([Binance public data
README](https://github.com/binance/binance-public-data/); [forum thread](https://dev.binance.vision/t/timestamp-format-inconsistency-in-historical-archives/33550)) [S].
The builder handles both.

**Run times (active time, see above).**

| step | work | time |
|---|---|---|
| `listing` | 777 S3 listings | 20 s |
| `d1` | 36,951 zips + checksums, 771 pairs | 7 min (4 processes of 48 threads) |
| `h1` | 27,742 zips + 2,555 repair zips, 486 pairs | 5.3 min (160 threads) |
| `perp1d` | 4,930 zips, 76 contracts | 3.5 min (32 threads) |
| `coverage` | full daily listings for 486 coins (1m klines, aggTrades, metrics) | 2.6 min (64 threads) |
| `events` | 13 aggTrades zips, 174 MB | 0.5 min (one at a time) |
| `validate`, `desc`, `sizes` | local computation; `sizes` also downloads an 83 MB throughput sample | 12 s, 12 s, 8 s |

---

## 2. Candidate universes

### 2.1 (a) User-style coins: 24, plus one predecessor

The user's two examples (HYPE, NEAR) and Robinhood-listed coins that look "solid" or earn protocol revenue. The tags
are a first pass from public knowledge, **not verified here** [U]: DefiLlama, the natural source for fees and
revenue, is blocked in this session. The design agent owns the final filter.

| coin | tag [U] | coin | tag [U] |
|---|---|---|---|
| HYPE | user example; perp-DEX fees, buybacks | CRV | DEX fees to lockers |
| NEAR | user example; L1 | COMP | lending fees |
| BTC | reference asset (no protocol revenue) | ENA | synthetic-dollar yield |
| ETH | L1 fees, burn | LINK | oracle fees |
| SOL | L1 fees | PYTH | oracle fees |
| BNB | exchange L1, burns | MORPHO | lending fees |
| AAVE | lending fees, buybacks | SYRUP | lending fees, buybacks |
| UNI | DEX fees (fee switch) | ASTER | perp-DEX fees, buybacks |
| SKY | stablecoin protocol (ex-MKR), buybacks | ORCA | AMM fees |
| LDO | staking fees | INJ | exchange fees, burn auctions |
| JTO | MEV / tip fees | ONDO | tokenized-treasury fees |
| RAY | AMM fees, buybacks | AERO | DEX fees to lockers |

- **Predecessor tickers.** SKY was MKR until 2025-09-15 on Binance (MKRUSDT 2020-07-23..2025-09-15; Sky's
  conversion rate is 1 MKR = 24,000 SKY [U]). MKR is fetched and shown next to SKY. RNDR (RENDER) and MATIC (POL) are
  fetched for the same reason; FTM (S) and EOS (A) are in set (b) anyway.
- **Not listed by Robinhood, so not in (a):** PENDLE, JUP, TRX, GMX, CAKE, TIA, APT, TAO, HNT, KMNO, PUMP (brief).
  The Binance ones are in set (b).

### 2.2 (b) Broad liquid universe, point in time: 485 coins

**Rule** (`universe_monthly` in the module):

- Every Binance USDT spot pair is eligible except 181 excluded pairs: 105 tokenized equities (ticker + B, listed
  from 2026-06), 50 leveraged tokens (XXXUP/XXXDOWN pairs, BULL/BEAR), 20 stablecoins and fiat, 4 wrapped or staked
  tokens, 2 gold tokens. The lists are imported from `scalp_crypto.py`.
- For each month M from 2020-01 to 2026-11, rank eligible pairs by the median daily USDT volume over the traded days
  among the 90 days before M. A pair needs at least 30 traded days and a trade on the last day before M.
- The top 100 form set (b) for month M. The rule uses only information available before M, so coins that later
  collapsed or were delisted stay in while they were liquid.

**What it holds** [A]:

- 485 distinct coins were in the top 100 in at least one month: 159-199 distinct coins per calendar year.
- 2020-01..03 had only 80-86 eligible pairs (95-96 in 2020-04..05), so those months hold every eligible pair.
- 133 of the 485 no longer trade on Binance spot (no trade after 2026-10-17). By year of last trade: 2020: 6,
  2021: 4, 2022: 14, 2023: 10, 2024: 32, 2025: 34, 2026: 33. They mix three cases the design must separate:
  - **rebrands and swaps:** EOS → A, MATIC → POL, FTM → S, MKR → SKY, RNDR → RENDER, AGIX/OCEAN → FET, BTT → BTTC,
    LIT → HEI;
  - **delistings:** e.g. XMR 2024-02-20, WAVES 2024-06-17, OMG 2024-06-17, SXP 2026-04-01;
  - **collapses:** UST (last trade 2022-05-13), SRM (FTX-linked, 2022-11-28), ANC (Terra, 2022-12-27), FTT (no
    trades 2022-11-15..2023-09-22, then relisted), LUNA (classic until 2022-05-13; the same ticker is Terra 2.0 from
    2022-05-31), OM (-94% on 2025-04-13).
- 429 of the 485 have a USD-M perpetual in the archive; 428 have futures metrics.

### 2.3 (c) Robinhood-tradable subset: 75 coins

- **Source.** Base codes from the scalping study's saved `get_currency_pairs` snapshot
  (`analysis_2026/results_scalping/A/arh_pairs.csv`, 2026-10-18; PAXG and USDC excluded) plus every coin the brief
  names as listed on 2026-11-18. All of the brief's names were already in the snapshot.
- **Gap.** The orchestrator's 2026-11-18 catalog has 92 pairs, and the full list was not passed to this agent.
  Coins Robinhood added after 2026-10-18 may be missing. To refresh: save the read-only response as JSON (e.g.
  `data/stinkbid/ref/currency_pairs.json`) and run `sets --rh-pairs data/stinkbid/ref/currency_pairs.json`, then
  `h1`, `perp1d`, `coverage`, `desc` (existing files are skipped).
- **Ticker collision removed.** Binance's LITUSDT was Litentry. Binance removed it on 2025-02-10 when the token became
  HEI ([Binance announcement](https://www.binance.com/el/support/announcement/detail/2a9feaa556f74dcdaa2192366f0e247c)
  [S]). Robinhood's LIT is Lighter, listed around January 2026
  ([BeInCrypto](https://beincrypto.com/robinhood-listing-sparks-lighter-rally-token-recovers-after-15-dip) [S]). The
  module drops any (c) coin whose Binance spot series ended more than 30 days before 2026-11-17; LIT is the only one.
  The USD-M contract LITUSDT trades on to 2026-11-16, so it may now be Lighter too [U].
- **Unverified identity** [U]: GRAM, RE, SENT, CHIP and MEGA were listed on Binance in 2026 and matched by ticker
  only.
- **All 75 have a Binance spot pair and a USD-M perpetual** [A].

### 2.4 Listing dates and archive coverage

From the archive listings [A]. "spot 1d in data from" is capped at the 2019-10 warm-up start; "spot archive from" is
the first monthly file in any year. Daily 1m-kline and aggTrades zips start at each pair's listing (BTC 2017-08-17).
The USD-M archive starts 2020-01, so 2020-01-01 for BTCUSDT and ETHUSDT means "on or before".

**User-style coins (a), with MKR:**

| coin | spot 1d in data from | spot last | spot archive from | 1m daily zips from | aggTrades daily from | USD-M perp (first day) | metrics (OI) from |
|---|---|---|---|---|---|---|---|
| HYPE | 2026-09-24 | 2026-11-17 | 2026-09 | 2026-09-24 | 2026-09-24 | HYPEUSDT 2025-05-30 | 2025-05-30 (536 d) |
| NEAR | 2020-10-14 | 2026-11-17 | 2020-10 | 2020-10-14 | 2020-10-14 | NEARUSDT 2020-10-15 | 2021-12-01 (1811 d) |
| BTC | 2019-10-01 | 2026-11-17 | 2017-08 | 2017-08-17 | 2017-08-17 | BTCUSDT 2020-01-01 | 2020-09-01 (2268 d) |
| ETH | 2019-10-01 | 2026-11-17 | 2017-08 | 2017-08-17 | 2017-08-17 | ETHUSDT 2020-01-01 | 2021-12-01 (1812 d) |
| SOL | 2020-08-11 | 2026-11-17 | 2020-08 | 2020-08-11 | 2020-08-11 | SOLUSDT 2020-09-14 | 2021-12-01 (1812 d) |
| BNB | 2019-10-01 | 2026-11-17 | 2017-11 | 2017-11-06 | 2017-11-06 | BNBUSDT 2020-02-10 | 2021-12-01 (1812 d) |
| AAVE | 2020-10-15 | 2026-11-17 | 2020-10 | 2020-10-15 | 2020-10-15 | AAVEUSDT 2020-10-16 | 2021-12-01 (1812 d) |
| UNI | 2020-09-17 | 2026-11-17 | 2020-09 | 2020-09-17 | 2020-09-17 | UNIUSDT 2020-09-18 | 2021-12-01 (1812 d) |
| SKY | 2025-09-17 | 2026-11-17 | 2025-09 | 2025-09-17 | 2025-09-17 | SKYUSDT 2025-09-09 | 2025-09-09 (434 d) |
| MKR | 2020-07-23 | 2025-09-15 | 2020-07 | 2020-07-23 | 2020-07-23 | MKRUSDT 2020-08-13 | 2021-12-01 (1515 d) |
| LDO | 2022-05-09 | 2026-11-17 | 2022-05 | 2022-05-09 | 2022-05-09 | LDOUSDT 2022-09-22 | 2022-09-22 (1517 d) |
| JTO | 2023-12-07 | 2026-11-17 | 2023-12 | 2023-12-07 | 2023-12-07 | JTOUSDT 2023-12-08 | 2023-12-08 (1075 d) |
| RAY | 2021-08-10 | 2026-11-17 | 2021-08 | 2021-08-10 | 2021-08-10 | RAYUSDT 2021-08-20 | 2021-12-01 (388 d) |
| AERO | 2026-07-17 | 2026-11-17 | 2026-07 | 2026-07-17 | 2026-07-17 | AEROUSDT 2024-12-04 | 2024-12-04 (713 d) |
| CRV | 2020-08-15 | 2026-11-17 | 2020-08 | 2020-08-15 | 2020-08-15 | CRVUSDT 2020-09-01 | 2021-12-01 (1812 d) |
| COMP | 2020-06-25 | 2026-11-17 | 2020-06 | 2020-06-25 | 2020-06-25 | COMPUSDT 2020-06-30 | 2021-12-01 (1812 d) |
| ENA | 2024-04-02 | 2026-11-17 | 2024-04 | 2024-04-02 | 2024-04-02 | ENAUSDT 2024-04-02 | 2024-04-02 (959 d) |
| LINK | 2019-10-01 | 2026-11-17 | 2019-01 | 2019-01-16 | 2019-01-16 | LINKUSDT 2020-01-17 | 2021-12-01 (1812 d) |
| PYTH | 2024-02-02 | 2026-11-17 | 2024-02 | 2024-02-02 | 2024-02-02 | PYTHUSDT 2023-11-22 | 2023-11-22 (1091 d) |
| MORPHO | 2025-10-03 | 2026-11-17 | 2025-10 | 2025-10-03 | 2025-10-03 | MORPHOUSDT 2024-11-27 | 2024-11-27 (720 d) |
| SYRUP | 2025-05-06 | 2026-11-17 | 2025-05 | 2025-05-06 | 2025-05-06 | SYRUPUSDT 2025-05-07 | 2025-05-07 (559 d) |
| ASTER | 2025-10-06 | 2026-11-17 | 2025-10 | 2025-10-06 | 2025-10-06 | ASTERUSDT 2025-09-19 | 2025-09-19 (424 d) |
| ORCA | 2024-12-06 | 2026-11-17 | 2024-12 | 2024-12-06 | 2024-12-06 | ORCAUSDT 2024-12-06 | 2024-12-06 (711 d) |
| INJ | 2020-10-21 | 2026-11-17 | 2020-10 | 2020-10-21 | 2020-10-21 | INJUSDT 2022-08-17 | 2022-08-17 (1553 d) |
| ONDO | 2025-04-11 | 2026-11-17 | 2025-04 | 2025-04-11 | 2025-04-11 | ONDOUSDT 2024-01-20 | 2024-01-20 (1032 d) |

**Other Robinhood coins (c):**

| coin | spot 1d in data from | spot last | spot archive from | 1m daily zips from | aggTrades daily from | USD-M perp (first day) | metrics (OI) from |
|---|---|---|---|---|---|---|---|
| ADA | 2019-10-01 | 2026-11-17 | 2018-04 | 2018-04-17 | 2018-04-17 | ADAUSDT 2020-01-31 | 2021-12-01 (1812 d) |
| ALGO | 2019-10-01 | 2026-11-17 | 2019-06 | 2019-06-22 | 2019-06-22 | ALGOUSDT 2020-06-16 | 2021-12-01 (1812 d) |
| ARB | 2023-03-23 | 2026-11-17 | 2023-03 | 2023-03-23 | 2023-03-23 | ARBUSDT 2023-03-23 | 2023-03-23 (1335 d) |
| ATOM | 2019-10-01 | 2026-11-17 | 2019-04 | 2019-04-29 | 2019-04-29 | ATOMUSDT 2020-02-07 | 2021-12-01 (1812 d) |
| AVAX | 2020-09-22 | 2026-11-17 | 2020-09 | 2020-09-22 | 2020-09-22 | AVAXUSDT 2020-09-23 | 2021-12-01 (1812 d) |
| AVNT | 2025-09-15 | 2026-11-17 | 2025-09 | 2025-09-15 | 2025-09-15 | AVNTUSDT 2025-09-09 | 2025-09-09 (434 d) |
| AXS | 2020-11-04 | 2026-11-17 | 2020-11 | 2020-11-04 | 2020-11-04 | AXSUSDT 2020-11-20 | 2021-12-01 (1812 d) |
| BAT | 2019-10-01 | 2026-11-17 | 2019-03 | 2019-03-04 | 2019-03-04 | BATUSDT 2020-02-13 | 2021-12-01 (1812 d) |
| BCH | 2019-11-28 | 2026-11-17 | 2019-11 | 2019-11-28 | 2019-11-28 | BCHUSDT 2020-01-01 | 2021-12-01 (1812 d) |
| BIO | 2025-01-03 | 2026-11-17 | 2025-01 | 2025-01-03 | 2025-01-03 | BIOUSDT 2025-01-03 | 2025-01-03 (683 d) |
| BONK | 2023-12-15 | 2026-11-17 | 2023-12 | 2023-12-15 | 2023-12-15 | 1000BONKUSDT 2023-11-22 | 2023-11-22 (1091 d) |
| CHIP | 2026-04-21 | 2026-11-17 | 2026-04 | 2026-04-21 | 2026-04-21 | CHIPUSDT 2026-04-16 | 2026-04-16 (215 d) |
| DOGE | 2019-10-01 | 2026-11-17 | 2019-07 | 2019-07-05 | 2019-07-05 | DOGEUSDT 2020-07-10 | 2021-12-01 (1812 d) |
| DOT | 2020-08-18 | 2026-11-17 | 2020-08 | 2020-08-18 | 2020-08-18 | DOTUSDT 2020-08-22 | 2021-12-01 (1812 d) |
| EIGEN | 2024-10-01 | 2026-11-17 | 2024-10 | 2024-10-01 | 2024-10-01 | EIGENUSDT 2024-10-01 | 2024-10-01 (777 d) |
| ETC | 2019-10-01 | 2026-11-17 | 2018-06 | 2018-06-12 | 2018-06-12 | ETCUSDT 2020-01-16 | 2021-12-01 (1812 d) |
| FET | 2019-10-01 | 2026-11-17 | 2019-02 | 2019-02-28 | 2019-02-28 | FETUSDT 2023-01-17 | 2023-01-17 (1400 d) |
| FLOKI | 2023-05-05 | 2026-11-17 | 2023-05 | 2023-05-05 | 2023-05-05 | 1000FLOKIUSDT 2023-05-06 | 2023-05-06 (1291 d) |
| GRAM | 2026-07-02 | 2026-11-17 | 2026-07 | 2026-07-02 | 2026-07-02 | GRAMUSDT 2026-07-02 | 2026-07-02 (138 d) |
| GRT | 2020-12-17 | 2026-11-17 | 2020-12 | 2020-12-17 | 2020-12-17 | GRTUSDT 2020-12-19 | 2021-12-01 (1811 d) |
| HBAR | 2019-10-01 | 2026-11-17 | 2019-09 | 2019-09-29 | 2019-09-29 | HBARUSDT 2021-03-17 | 2021-12-01 (1812 d) |
| IMX | 2022-01-10 | 2026-11-17 | 2022-01 | 2022-01-10 | 2022-01-10 | IMXUSDT 2022-02-11 | 2022-02-11 (1740 d) |
| LTC | 2019-10-01 | 2026-11-17 | 2017-12 | 2017-12-13 | 2017-12-13 | LTCUSDT 2020-01-09 | 2021-12-01 (1812 d) |
| MEGA | 2026-04-30 | 2026-11-17 | 2026-04 | 2026-04-30 | 2026-04-30 | MEGAUSDT 2026-01-30 | 2026-01-30 (291 d) |
| OP | 2022-06-01 | 2026-11-17 | 2022-06 | 2022-06-01 | 2022-06-01 | OPUSDT 2022-06-01 | 2022-06-01 (1630 d) |
| PENGU | 2024-12-17 | 2026-11-17 | 2024-12 | 2024-12-17 | 2024-12-17 | PENGUUSDT 2024-12-17 | 2024-12-17 (700 d) |
| PEPE | 2023-05-05 | 2026-11-17 | 2023-05 | 2023-05-05 | 2023-05-05 | 1000PEPEUSDT 2023-05-05 | 2023-05-05 (1292 d) |
| PNUT | 2024-11-11 | 2026-11-17 | 2024-11 | 2024-11-11 | 2024-11-11 | PNUTUSDT 2024-11-11 | 2024-11-11 (736 d) |
| POL | 2024-09-13 | 2026-11-17 | 2024-09 | 2024-09-13 | 2024-09-13 | POLUSDT 2024-09-13 | 2024-09-13 (795 d) |
| QNT | 2021-07-29 | 2026-11-17 | 2021-07 | 2021-07-29 | 2021-07-29 | QNTUSDT 2022-10-20 | 2022-10-20 (1489 d) |
| RE | 2026-06-18 | 2026-11-17 | 2026-06 | 2026-06-18 | 2026-06-18 | REUSDT 2026-06-18 | 2026-06-18 (152 d) |
| RENDER | 2024-07-26 | 2026-11-17 | 2024-07 | 2024-07-26 | 2024-07-26 | RENDERUSDT 2024-07-26 | 2024-07-26 (844 d) |
| SEI | 2023-08-15 | 2026-11-17 | 2023-08 | 2023-08-15 | 2023-08-15 | SEIUSDT 2023-08-17 | 2023-08-17 (1188 d) |
| SENT | 2026-01-22 | 2026-11-17 | 2026-01 | 2026-01-22 | 2026-01-22 | SENTUSDT 2025-11-14 | 2025-11-14 (368 d) |
| SHIB | 2021-05-10 | 2026-11-17 | 2021-05 | 2021-05-10 | 2021-05-10 | 1000SHIBUSDT 2021-05-10 | 2021-12-01 (1812 d) |
| SNX | 2020-07-09 | 2026-11-17 | 2020-07 | 2020-07-09 | 2020-07-09 | SNXUSDT 2020-08-14 | 2021-12-01 (1811 d) |
| STRK | 2024-02-20 | 2026-11-17 | 2024-02 | 2024-02-20 | 2024-02-20 | STRKUSDT 2024-02-20 | 2024-02-20 (1001 d) |
| SUI | 2023-05-03 | 2026-11-17 | 2023-05 | 2023-05-03 | 2023-05-03 | SUIUSDT 2023-05-03 | 2023-05-03 (1293 d) |
| TRUMP | 2025-01-19 | 2026-11-17 | 2025-01 | 2025-01-19 | 2025-01-19 | TRUMPUSDT 2025-01-18 | 2025-01-18 (668 d) |
| VIRTUAL | 2025-04-11 | 2026-11-17 | 2025-04 | 2025-04-11 | 2025-04-11 | VIRTUALUSDT 2024-12-10 | 2024-12-10 (707 d) |
| W | 2024-04-03 | 2026-11-17 | 2024-04 | 2024-04-03 | 2024-04-03 | WUSDT 2024-04-03 | 2024-04-03 (958 d) |
| WIF | 2024-03-05 | 2026-11-17 | 2024-03 | 2024-03-05 | 2024-03-05 | WIFUSDT 2024-01-18 | 2024-01-18 (1034 d) |
| WLD | 2023-07-24 | 2026-11-17 | 2023-07 | 2023-07-24 | 2023-07-24 | WLDUSDT 2023-07-24 | 2023-07-24 (1211 d) |
| WLFI | 2025-09-01 | 2026-11-17 | 2025-09 | 2025-09-01 | 2025-09-01 | WLFIUSDT 2025-08-23 | 2025-08-23 (451 d) |
| XLM | 2019-10-01 | 2026-11-17 | 2018-05 | 2018-05-31 | 2018-05-31 | XLMUSDT 2020-01-20 | 2021-12-01 (1811 d) |
| XPL | 2025-09-25 | 2026-11-17 | 2025-09 | 2025-09-25 | 2025-09-25 | XPLUSDT 2025-08-22 | 2025-08-22 (452 d) |
| XRP | 2019-10-01 | 2026-11-17 | 2018-05 | 2018-05-04 | 2018-05-04 | XRPUSDT 2020-01-06 | 2021-12-01 (1812 d) |
| XTZ | 2019-10-01 | 2026-11-17 | 2019-09 | 2019-09-24 | 2019-09-24 | XTZUSDT 2020-02-06 | 2021-12-01 (1811 d) |
| ZEC | 2019-10-01 | 2026-11-17 | 2019-03 | 2019-03-21 | 2019-03-21 | ZECUSDT 2020-02-05 | 2021-12-01 (1811 d) |
| ZRO | 2024-06-20 | 2026-11-17 | 2024-06 | 2024-06-20 | 2024-06-20 | ZROUSDT 2024-06-20 | 2024-06-20 (880 d) |
| ZRX | 2019-10-01 | 2026-11-17 | 2019-02 | 2019-02-28 | 2019-02-28 | ZRXUSDT 2020-06-24 | 2021-12-01 (1812 d) |

**Coverage notes** [A]:

- **Futures metrics** (open interest, long/short ratios, taker volume, 5-minute rows): BTCUSDT from 2020-09-01. Of
  the other 130 candidate contracts listed before December 2021, 128 start on **2021-12-01** (one on 2021-12-23, one
  has none). Later contracts start on their listing day. So there is no open interest for altcoins at 2020-03-12 or
  2021-05-19.
- **The futures daily archive lags spot by one day:** the last USD-M daily zip is 2026-11-16, so `d1_um` ends there.
- **Robinhood's own price history is not available** (no crypto candles in the MCP; Coinbase, Kraken, Bitstamp
  blocked here; see `mechanics.md`).

---

## 3. Integrity: checksums, gaps, outages and bad prints

### 3.1 Downloads and repairs [A]

| series | zips | sha256 verified | failed | repairs |
|---|---|---|---|---|
| spot 1d, 771 pairs | 36,951 (+19 daily zips for holes) | all | 0 | 19 bars filled from daily zips; 3 duplicate bars dropped; 2 trailing placeholder bars trimmed |
| spot 1h, 486 pairs | 27,742 (+2,555 daily zips) | all | 0 | 660,427 hourly days checked against the 1d kline: 122 mismatched, 48 repaired from daily zips, 74 unresolved; 2 duplicates dropped; 6 leading placeholder bars trimmed |
| USD-M 1d, 76 contracts | 4,930 (+50) | all | 0 | 50 bars filled; 1,462 trailing placeholder bars trimmed |
| aggTrades, 13 coin-days | 13 | all | 0 | daily low equals the 1d kline's on all 13; USDT volume too (HYPE perpetual within 0.002%) |

- **The 74 unresolved hourly days are harmless.** 69 are in 2020. On every one the close agrees. Open, high and low
  differ from the 1d kline by at most 1.4% (GTOUSDT 2020-01-26 and 2020-05-13); the rest by under 1%. The counts in
  sections 4-6 use the 1d klines, so they are not affected. Listed in `stats/h1.json`.
- **Repaired days:** 47 of the 48 are in 2021-12 (e.g. AXSUSDT 2021-12-05, 07, 12; ALGOUSDT 2021-12-12), one is
  DOGEUSDT 2021-10-28. The monthly hourly zip carried a wrong bar that the daily zip and the 1d kline contradict, as
  found in the Bollinger study.

### 3.2 Gaps and series breaks [A]

- **Daily panel** (590 eligible pairs, 787,060 pair-days): 12 pairs have internal missing days (542 days in all).
  There are no internal zero-trade days.
- **Long gaps** (hourly series, 72 h or more): FTT 311 days (2022-11-15..2023-09-22), CVC 154 d, KEY 28 d, LUNA 18 d
  (2022-05-13..31, where the ticker switches from Terra Classic to Terra 2.0), VIDT 9 d, STRAX 8 d, BNX 6 d; BTCST,
  COCOS, DREP and SUN 4 d each.
  - STRAX (-90% across the gap) and VIDT (-91%) were 10:1 token swaps [U]. LUNA's open after the gap is 20,000x its
    last close.
- **Treatment in the counts.** A missing day or a jump of more than 25% between a close and the next day's open
  starts a new segment. No reference price and no window crosses a segment boundary.
  - Only one such jump exists without a gap: SCRUSDT on 2024-10-22 (open 43% below the prior close). The archive
    has SCRUSDT bars from 2024-10-11, which may be pre-market trading before the regular listing [U].
- **Hourly series:** 18,126 missing hours and 2,822 zero-trade hours in 15.8 million bars; no OHLC violations or
  non-positive prices.

### 3.3 Exchange-wide outages [A]

Hours missing or zero-trade in at least 50% of the listed candidate series, i.e. Binance spot downtime. A stink bid
cannot fill on Binance during these hours, while other venues keep trading.

| UTC | hours | | UTC | hours |
|---|---|---|---|---|
| 2020-02-09 02:00 | 1 | | 2021-02-11 03:00-04:00 | 2 |
| 2020-02-19 12:00-16:00 | 5 | | 2021-03-06 02:00 | 1 |
| 2020-03-04 10:00 | 1 | | 2021-04-20 02:00-03:00 | 2 |
| 2020-04-25 02:00-03:00 | 2 | | 2021-04-25 05:00-07:00 | 3 |
| 2020-06-28 02:00-04:00 | 3 | | 2021-08-13 02:00-05:00 | 4 |
| 2020-11-30 06:00 | 1 | | 2021-09-29 07:00-08:00 | 2 |
| 2020-12-21 14:00-17:00 | 4 | | 2023-03-24 12:00-13:00 | 2 |
| 2020-12-25 02:00 | 1 | | | |

The 2023-03-24 outage is Binance's two-hour spot halt caused by a matching-engine bug on a trailing-stop order
([Cointelegraph](https://cointelegraph.com/news/binance-spot-trading-halted-due-to-issue-on-trailing-stop-orders),
[TechCrunch](https://techcrunch.com/2023/03/24/crypto-giant-binance-temporarily-suspends-spot-trading/)) [S]. On
2021-05-19 Binance's spot archive has no missing hour, although Binance reportedly stopped transaction-level
reporting for about 40 minutes mid-crash (`mechanics.md`) [U].

### 3.4 Bad prints and venue-specific wicks [A]

These are real trades in the archive. Whether a retail order could have been filled at them is a separate question.

- **Extreme daily lows.** 399 pair-days on 70 days had a low at least 60% below the prior close
  (`validation/d1_lows_below_60pct.csv`): 282 on 2025-10-10, 19 on 2021-05-19, 13 on 2020-03-12.
- **One-hour spikes.** 261 hourly bars in 241 series on 36 days had a low at least 50% below the bar's
  min(open, close) (`validation/h1_spike_prints.csv`). 224 of them are on 2025-10-10. Examples:
  - LINKUSDT 2020-03-12 10:00: low $0.0001 against a $2.47 body, in an hour with $17M traded. RLCUSDT the same day
    also printed $0.0001.
  - RENUSDT 2021-04-18 03:00: low 0.0151 against 0.934 (-98%).
  - ICXUSDT 2025-03-09 15:00: low 0.0002 against 0.1021.
  - ONDOUSDT 2025-10-10 21:00: low 0.2552 against 0.6234 (-59%), with $24M traded in the hour.
- **2025-10-10.** Binance said reports of tokens "crashing to zero" were a display problem and paid about $283M to
  users hurt by the depegs of USDe, BNSOL and wBETH between 21:36 and 22:16 UTC
  ([The Block](https://www.theblock.co/news/markets/2025-10-12-binance-pays-283-million-in-compensation-following-fridays-depegs-covering-user-losses-374295);
  [Decrypt](https://decrypt.co/344026/binance-reimburses-283m-after-market-crash-and-asset-depegging-issues)) [S].
  The archive's trades nevertheless include lows such as AAVE -71%, LINK -64% and NEAR -46% against the prior close,
  in the 21:18-21:23 UTC window (section 7).
- **Spot against perpetual** (`validation/spot_vs_perp_lows.csv`; 75 Robinhood coins, each daily low against its own
  prior close; LIT excluded):
  - Median absolute basis is under 2% for every coin.
  - The spot low was at least 10 points deeper on 17 coin-days, the perpetual's on 28 (at least 5 points: 57 and
    103).
  - Spot deeper: LINK 2020-03-12 (46 points, the $0.0001 print), PNUT 2025-12-11 (60 points: spot low -66% on a
    quiet day while the perpetual fell 6%), SYRUP 2025-10-10 (53), ATOM 2025-10-10 (36), AXS 2022-11-13 (34).
  - Perpetual deeper: BAT 2020-03-13 (73 points), ADA 2020-02-28 (47), ETC 2020-08-09 (26), XTZ 2020-07-29 (23),
    SOL 2025-10-10 (12).
  - A level-touch count from one venue's lows therefore depends on the venue. Thin books on either market print
    wicks the other does not.

---

## 4. How often a level was touched (counts only)

### 4.1 Definitions

- **Reference:** the close of day t (UTC). Think of a bid placed at that close, d% below it.
- **Window:** the next H days (t+1..t+H), H = 1, 7 or 30. The level counts as touched if the lowest daily low in the
  window is at or below (1 - d) x close.
  - H = 1 is the share of days whose low reached d% below the prior day's close.
  - H = 7 and 30 are the share of bids, placed at a random daily close, that would have been touched within a week or
    a month.
- **Sample:** every start day 2020-01-01..2026-11-17 whose window is complete inside one segment (section 3.2).
  Windows cut short by a delisting or gap are left out (at most H start days per delisting or gap).
- **Overlap:** windows overlap, so the independent sample is about n / H.
- **Not computed:** what happened after a touch.
- `n` = start days. Values are percentages of `n`.

### 4.2 User-style coins (a)

Bid touched on the next day:

| coin | from | n | >=5% | >=10% | >=15% | >=20% | >=25% | >=30% | >=40% | >=50% | >=60% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| HYPE | 2026-09 | 54 | 18.5 | 1.9 | 1.9 | 0 | 0 | 0 | 0 | 0 | 0 |
| NEAR | 2020-10 | 2225 | 32.9 | 9.4 | 3.0 | 1.2 | 0.7 | 0.3 | 0.1 | 0 | 0 |
| BTC | 2020-01 | 2512 | 9.8 | 1.6 | 0.7 | 0.2 | 0.08 | 0.04 | 0.04 | 0 | 0 |
| ETH | 2020-01 | 2512 | 17.4 | 3.9 | 1.4 | 0.5 | 0.2 | 0.08 | 0.08 | 0 | 0 |
| SOL | 2020-08 | 2289 | 29.4 | 7.6 | 2.5 | 1.2 | 0.5 | 0.3 | 0.1 | 0.04 | 0 |
| BNB | 2020-01 | 2512 | 14.5 | 4.0 | 1.3 | 0.5 | 0.4 | 0.2 | 0.08 | 0 | 0 |
| AAVE | 2020-10 | 2224 | 30.5 | 8.0 | 2.5 | 1.4 | 0.6 | 0.2 | 0.09 | 0.04 | 0.04 |
| UNI | 2020-09 | 2252 | 29.8 | 7.8 | 2.5 | 1.1 | 0.4 | 0.2 | 0.09 | 0.09 | 0.04 |
| SKY | 2025-09 | 426 | 18.8 | 2.3 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0 | 0 |
| MKR | 2020-07 | 1880 | 26.5 | 6.3 | 1.8 | 1.0 | 0.4 | 0.2 | 0.05 | 0 | 0 |
| LDO | 2022-05 | 1653 | 34.3 | 9.0 | 2.4 | 1.0 | 0.6 | 0.4 | 0.06 | 0.06 | 0.06 |
| JTO | 2023-12 | 1076 | 37.0 | 10.4 | 2.6 | 1.0 | 0.5 | 0.3 | 0.09 | 0.09 | 0.09 |
| RAY | 2021-08 | 1925 | 33.6 | 9.7 | 2.5 | 1.0 | 0.4 | 0.3 | 0.1 | 0.05 | 0.05 |
| AERO | 2026-07 | 123 | 25.2 | 4.1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| CRV | 2020-08 | 2285 | 35.8 | 11.9 | 4.7 | 2.1 | 1.4 | 0.7 | 0.1 | 0.09 | 0.04 |
| COMP | 2020-06 | 2336 | 28.8 | 7.9 | 2.7 | 1.2 | 0.5 | 0.3 | 0.09 | 0.04 | 0.04 |
| ENA | 2024-04 | 959 | 41.6 | 11.6 | 3.0 | 0.8 | 0.3 | 0.1 | 0.1 | 0.1 | 0.1 |
| LINK | 2020-01 | 2512 | 27.2 | 7.0 | 2.3 | 1.2 | 0.8 | 0.4 | 0.1 | 0.1 | 0.08 |
| PYTH | 2024-02 | 1019 | 34.7 | 7.2 | 1.9 | 0.6 | 0.6 | 0.3 | 0.10 | 0.10 | 0.10 |
| MORPHO | 2025-10 | 410 | 23.4 | 4.1 | 0.5 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
| SYRUP | 2025-05 | 560 | 30.9 | 5.9 | 1.4 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
| ASTER | 2025-10 | 407 | 20.9 | 6.4 | 3.2 | 0.7 | 0.7 | 0.5 | 0.2 | 0 | 0 |
| ORCA | 2024-12 | 711 | 32.3 | 8.2 | 2.3 | 0.6 | 0.3 | 0.3 | 0.1 | 0.1 | 0.1 |
| INJ | 2020-10 | 2218 | 35.9 | 9.6 | 3.2 | 1.2 | 0.6 | 0.4 | 0.1 | 0.09 | 0.05 |
| ONDO | 2025-04 | 585 | 25.6 | 3.8 | 1.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |

MKR is SKY's predecessor ticker; it is shown for reference and is not in the pooled (a) rows.

Within 7 days:

| coin | from | n | >=5% | >=10% | >=15% | >=20% | >=25% | >=30% | >=40% | >=50% | >=60% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| HYPE | 2026-09 | 48 | 79.2 | 33.3 | 16.7 | 4.2 | 0 | 0 | 0 | 0 | 0 |
| NEAR | 2020-10 | 2219 | 71.3 | 45.1 | 29.1 | 16.4 | 9.0 | 4.7 | 2.1 | 0.4 | 0.1 |
| BTC | 2020-01 | 2506 | 41.8 | 15.5 | 6.9 | 3.4 | 1.6 | 0.8 | 0.3 | 0.3 | 0 |
| ETH | 2020-01 | 2506 | 52.6 | 26.1 | 12.7 | 7.3 | 3.6 | 2.1 | 0.7 | 0.4 | 0.08 |
| SOL | 2020-08 | 2283 | 68.2 | 41.7 | 23.5 | 13.3 | 6.9 | 4.2 | 1.8 | 0.9 | 0.2 |
| BNB | 2020-01 | 2506 | 47.5 | 21.2 | 11.1 | 6.2 | 3.3 | 1.9 | 0.8 | 0.6 | 0.3 |
| AAVE | 2020-10 | 2218 | 70.3 | 43.8 | 25.1 | 14.5 | 8.6 | 4.5 | 1.8 | 0.7 | 0.5 |
| UNI | 2020-09 | 2246 | 69.1 | 42.2 | 24.9 | 14.7 | 7.9 | 4.4 | 1.7 | 0.7 | 0.5 |
| SKY | 2025-09 | 420 | 61.2 | 30.0 | 11.4 | 3.6 | 1.7 | 1.7 | 1.7 | 0 | 0 |
| MKR | 2020-07 | 1874 | 67.4 | 38.7 | 20.0 | 11.2 | 5.9 | 2.8 | 0.7 | 0.3 | 0.05 |
| LDO | 2022-05 | 1647 | 75.0 | 49.5 | 29.1 | 17.1 | 9.2 | 5.0 | 2.1 | 0.7 | 0.4 |
| JTO | 2023-12 | 1070 | 78.0 | 53.5 | 34.4 | 19.4 | 9.0 | 5.0 | 1.8 | 0.7 | 0.7 |
| RAY | 2021-08 | 1919 | 70.8 | 45.3 | 28.4 | 15.5 | 8.9 | 4.6 | 1.9 | 0.9 | 0.6 |
| AERO | 2026-07 | 117 | 63.2 | 37.6 | 19.7 | 6.0 | 3.4 | 0.9 | 0 | 0 | 0 |
| CRV | 2020-08 | 2279 | 75.2 | 49.8 | 31.8 | 19.7 | 12.6 | 8.2 | 4.3 | 1.4 | 0.6 |
| COMP | 2020-06 | 2330 | 70.4 | 43.9 | 24.8 | 13.7 | 7.3 | 4.6 | 1.6 | 0.6 | 0.4 |
| ENA | 2024-04 | 953 | 79.4 | 59.2 | 40.8 | 21.9 | 11.0 | 5.2 | 1.3 | 0.7 | 0.7 |
| LINK | 2020-01 | 2506 | 66.5 | 39.5 | 20.4 | 11.9 | 7.0 | 4.7 | 1.8 | 0.8 | 0.6 |
| PYTH | 2024-02 | 1013 | 74.9 | 48.8 | 29.7 | 17.5 | 8.8 | 5.4 | 1.5 | 0.7 | 0.7 |
| MORPHO | 2025-10 | 404 | 67.3 | 38.6 | 20.3 | 8.2 | 3.5 | 1.7 | 1.7 | 1.7 | 1.7 |
| SYRUP | 2025-05 | 554 | 74.2 | 46.8 | 28.5 | 13.2 | 5.6 | 3.4 | 1.3 | 1.3 | 1.3 |
| ASTER | 2025-10 | 401 | 55.4 | 27.2 | 18.0 | 13.0 | 7.0 | 2.5 | 1.0 | 0.5 | 0 |
| ORCA | 2024-12 | 705 | 71.6 | 46.8 | 30.4 | 14.3 | 7.0 | 4.3 | 1.6 | 1.0 | 1.0 |
| INJ | 2020-10 | 2212 | 72.0 | 46.9 | 28.3 | 16.1 | 9.1 | 5.0 | 2.2 | 1.0 | 0.5 |
| ONDO | 2025-04 | 579 | 69.8 | 39.9 | 18.8 | 9.2 | 2.9 | 1.4 | 1.2 | 1.2 | 1.2 |

Within 30 days:

| coin | from | n | >=5% | >=10% | >=15% | >=20% | >=25% | >=30% | >=40% | >=50% | >=60% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| HYPE | 2026-09 | 25 | 100.0 | 100.0 | 72.0 | 20.0 | 8.0 | 0 | 0 | 0 | 0 |
| NEAR | 2020-10 | 2196 | 85.1 | 71.9 | 60.0 | 49.7 | 41.1 | 29.9 | 14.5 | 5.3 | 1.3 |
| BTC | 2020-01 | 2483 | 67.1 | 42.1 | 26.9 | 16.5 | 9.8 | 6.2 | 2.8 | 1.2 | 0.5 |
| ETH | 2020-01 | 2483 | 73.8 | 55.3 | 39.5 | 26.7 | 18.9 | 13.0 | 5.3 | 2.6 | 1.0 |
| SOL | 2020-08 | 2260 | 83.3 | 67.8 | 55.7 | 44.2 | 34.5 | 26.3 | 12.4 | 5.9 | 1.7 |
| BNB | 2020-01 | 2483 | 70.7 | 46.8 | 32.0 | 21.5 | 14.6 | 9.7 | 4.3 | 2.3 | 2.1 |
| AAVE | 2020-10 | 2195 | 87.7 | 73.0 | 60.0 | 46.2 | 33.4 | 24.9 | 12.2 | 5.7 | 2.3 |
| UNI | 2020-09 | 2223 | 86.2 | 70.5 | 57.1 | 46.1 | 34.9 | 26.6 | 13.6 | 5.2 | 2.8 |
| SKY | 2025-09 | 397 | 83.4 | 66.8 | 48.4 | 30.2 | 17.9 | 10.1 | 5.8 | 1.3 | 0 |
| MKR | 2020-07 | 1851 | 85.5 | 70.4 | 55.3 | 40.4 | 28.4 | 20.5 | 7.4 | 2.5 | 0.9 |
| LDO | 2022-05 | 1624 | 89.7 | 77.8 | 65.0 | 52.3 | 40.6 | 28.9 | 13.5 | 6.0 | 3.6 |
| JTO | 2023-12 | 1047 | 91.5 | 79.0 | 68.3 | 55.5 | 42.6 | 32.8 | 16.2 | 7.4 | 3.5 |
| RAY | 2021-08 | 1896 | 85.5 | 72.4 | 59.9 | 47.6 | 37.0 | 27.7 | 15.3 | 8.3 | 5.3 |
| AERO | 2026-07 | 94 | 68.1 | 40.4 | 29.8 | 25.5 | 18.1 | 14.9 | 8.5 | 3.2 | 0 |
| CRV | 2020-08 | 2256 | 88.6 | 77.1 | 65.2 | 54.5 | 43.6 | 34.6 | 19.7 | 11.6 | 5.2 |
| COMP | 2020-06 | 2307 | 87.7 | 72.5 | 58.6 | 45.4 | 35.4 | 26.5 | 13.0 | 6.0 | 2.9 |
| ENA | 2024-04 | 930 | 90.4 | 81.2 | 71.6 | 59.5 | 49.4 | 37.6 | 21.2 | 10.9 | 3.8 |
| LINK | 2020-01 | 2483 | 82.4 | 65.8 | 50.6 | 39.8 | 29.9 | 21.5 | 10.6 | 5.6 | 3.4 |
| PYTH | 2024-02 | 990 | 89.3 | 77.9 | 68.7 | 59.9 | 47.3 | 35.1 | 16.0 | 5.1 | 3.0 |
| MORPHO | 2025-10 | 381 | 86.1 | 70.3 | 54.9 | 36.5 | 22.8 | 7.6 | 4.7 | 1.8 | 1.8 |
| SYRUP | 2025-05 | 531 | 86.4 | 74.6 | 60.8 | 46.1 | 34.8 | 28.8 | 17.5 | 7.9 | 5.6 |
| ASTER | 2025-10 | 378 | 86.0 | 52.1 | 34.7 | 28.6 | 23.3 | 19.6 | 9.0 | 1.6 | 0.5 |
| ORCA | 2024-12 | 682 | 86.8 | 72.3 | 59.8 | 47.8 | 37.5 | 29.6 | 15.0 | 7.6 | 4.7 |
| INJ | 2020-10 | 2189 | 85.8 | 72.1 | 59.2 | 46.5 | 36.1 | 26.6 | 15.2 | 6.3 | 3.6 |
| ONDO | 2025-04 | 556 | 84.0 | 64.7 | 51.8 | 39.9 | 30.6 | 19.6 | 10.1 | 6.1 | 5.4 |

Short series (HYPE 54 days, AERO 123, MORPHO 410, ASTER 407, SKY 426) cover too few market regimes to compare with
the five- or six-year series.

### 4.3 Pooled groups

All years, for three windows. "all USDT pairs (excl.)" pools every eligible pair, liquid or not.

| group | coins | window | n (start days) | >=5% | >=10% | >=15% | >=20% | >=25% | >=30% | >=40% | >=50% | >=60% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) user-style | 24 | next day | 35,785 | 27.9 | 7.3 | 2.3 | 1.0 | 0.5 | 0.3 | 0.1 | 0.06 | 0.04 |
| (a) user-style | 24 | 7 days | 35,641 | 66.1 | 39.9 | 23.3 | 13.1 | 7.1 | 4.1 | 1.7 | 0.7 | 0.4 |
| (a) user-style | 24 | 30 days | 35,089 | 83.1 | 67.0 | 53.7 | 41.9 | 32.0 | 23.6 | 11.9 | 5.6 | 2.8 |
| (c) Robinhood | 75 | next day | 112,621 | 29.0 | 7.6 | 2.4 | 1.0 | 0.5 | 0.3 | 0.1 | 0.08 | 0.05 |
| (c) Robinhood | 75 | 7 days | 112,171 | 68.5 | 41.6 | 24.1 | 13.5 | 7.5 | 4.4 | 1.7 | 0.8 | 0.5 |
| (c) Robinhood | 75 | 30 days | 110,446 | 85.3 | 70.0 | 56.2 | 44.3 | 34.1 | 25.3 | 12.6 | 5.7 | 2.8 |
| (b) top-100 PIT | 485 | next day | 248,972 | 32.5 | 9.5 | 3.3 | 1.4 | 0.8 | 0.4 | 0.2 | 0.1 | 0.05 |
| (b) top-100 PIT | 485 | 7 days | 248,212 | 70.8 | 45.2 | 27.6 | 16.4 | 9.7 | 5.8 | 2.3 | 1.1 | 0.6 |
| (b) top-100 PIT | 485 | 30 days | 245,362 | 86.6 | 72.7 | 59.7 | 48.2 | 38.2 | 29.5 | 16.0 | 7.6 | 3.9 |
| all USDT pairs (excl.) | 589 | next day | 779,322 | 30.3 | 8.6 | 2.9 | 1.3 | 0.7 | 0.4 | 0.1 | 0.09 | 0.05 |
| all USDT pairs (excl.) | 589 | 7 days | 775,710 | 69.7 | 43.4 | 25.8 | 15.0 | 8.8 | 5.3 | 2.1 | 1.0 | 0.6 |
| all USDT pairs (excl.) | 589 | 30 days | 761,883 | 86.8 | 72.8 | 59.4 | 47.5 | 37.3 | 28.2 | 14.5 | 6.8 | 3.5 |

By year, broad universe (b):

| year | coins | next day >=10% | >=20% | >=30% | >=40% | 30 days >=10% | >=20% | >=30% | >=40% | >=50% |
|---|---|---|---|---|---|---|---|---|---|---|
| 2020 | 159 | 10.8 | 1.7 | 0.5 | 0.3 | 62.2 | 36.4 | 22.0 | 13.7 | 9.3 |
| 2021 | 164 | 17.9 | 3.5 | 1.3 | 0.4 | 77.6 | 57.2 | 39.8 | 25.0 | 12.8 |
| 2022 | 162 | 9.8 | 1.4 | 0.4 | 0.2 | 81.5 | 56.2 | 36.6 | 20.5 | 9.5 |
| 2023 | 185 | 4.7 | 0.5 | 0.06 | 0.00 | 62.1 | 34.0 | 15.3 | 3.4 | 0.4 |
| 2024 | 179 | 9.0 | 1.4 | 0.3 | 0.01 | 76.1 | 51.0 | 31.3 | 16.0 | 4.7 |
| 2025 | 199 | 9.0 | 0.9 | 0.4 | 0.3 | 80.7 | 60.2 | 38.3 | 21.9 | 12.6 |
| 2026 | 177 | 4.9 | 0.4 | 0.07 | 0.03 | 66.9 | 40.0 | 21.5 | 10.2 | 3.3 |

By year, user-style coins (a):

| year | coins | next day >=10% | >=20% | >=30% | >=40% | 30 days >=10% | >=20% | >=30% | >=40% | >=50% |
|---|---|---|---|---|---|---|---|---|---|---|
| 2020 | 11 | 11.7 | 2.0 | 0.6 | 0.3 | 56.1 | 34.1 | 24.3 | 15.4 | 9.0 |
| 2021 | 12 | 15.0 | 2.6 | 0.9 | 0.2 | 74.9 | 53.2 | 33.0 | 17.5 | 8.9 |
| 2022 | 13 | 9.0 | 1.2 | 0.3 | 0.09 | 78.5 | 55.0 | 34.7 | 20.9 | 11.2 |
| 2023 | 14 | 3.3 | 0.3 | 0.02 | 0 | 52.3 | 23.5 | 7.9 | 1.3 | 0.5 |
| 2024 | 17 | 7.1 | 1.2 | 0.2 | 0 | 69.9 | 40.9 | 22.1 | 9.7 | 2.0 |
| 2025 | 22 | 7.2 | 0.6 | 0.3 | 0.3 | 74.9 | 52.1 | 29.0 | 14.7 | 8.7 |
| 2026 | 24 | 3.5 | 0.1 | 0 | 0 | 57.5 | 31.3 | 16.4 | 7.5 | 1.8 |

**How the 30-day touches happened** (`desc/first_touch_30d.csv`): for each touched window, the days until the first
touch and that day's own drop from its prior close. Nothing after the touch is used.

| group | level | touched 30-day windows | median days to first touch | touched on day 1 | touch-day drop >= half the depth | touch-day drop < 10% | prior close within 5% above the level |
|---|---|---|---|---|---|---|---|
| (a) user-style | -20% | 14,687 | 12 | 2.3% | 63% | 37% | 24% |
| (a) user-style | -30% | 8,274 | 16 | 1.2% | 55% | 21% | 15% |
| (c) Robinhood | -20% | 48,977 | 12 | 2.3% | 62% | 38% | 25% |
| (c) Robinhood | -30% | 27,915 | 16 | 1.2% | 56% | 22% | 15% |
| (b) top-100 PIT | -20% | 118,199 | 11 | 3.0% | 67% | 33% | 21% |
| (b) top-100 PIT | -30% | 72,436 | 15 | 1.5% | 58% | 20% | 14% |

- **A resting bid is usually reached by a drift plus one sharp day.** At the 20% level the first touch came a median
  11-12 days after placement and almost never on day 1 (2-3%). On the touch day the price fell at least 10% from the
  prior close in 62-67% of cases; in the other third it ground down to the level with a smaller daily drop.
- **Deep touches cluster in time.** 2021 has the most; 2023 and 2026 the fewest.
- **Coin groups differ less than one might expect.** (a), (c) and (b) are close at every depth. The broad universe
  is somewhat deeper, as its smaller and newer coins would suggest.

### 4.4 Other Robinhood coins (c)

Next day and 30 days, selected depths (all depths in `desc/touch_shares_by_coin.csv`):

| coin | from | days | day>=10% | day>=20% | day>=30% | 30d>=20% | 30d>=30% | 30d>=50% |
|---|---|---|---|---|---|---|---|---|
| ADA | 2020-01 | 2512 | 5.9 | 0.9 | 0.2 | 41.4 | 19.9 | 3.6 |
| ALGO | 2020-01 | 2512 | 7.4 | 1.4 | 0.3 | 45.1 | 24.1 | 4.6 |
| ARB | 2023-03 | 1335 | 6.2 | 0.4 | 0.1 | 48.0 | 25.9 | 5.6 |
| ATOM | 2020-01 | 2512 | 6.8 | 1.2 | 0.4 | 42.1 | 20.0 | 5.2 |
| AVAX | 2020-09 | 2247 | 7.8 | 1.0 | 0.3 | 46.4 | 26.6 | 5.4 |
| AVNT | 2025-09 | 428 | 9.3 | 1.2 | 0.2 | 58.9 | 40.1 | 8.5 |
| AXS | 2020-11 | 2204 | 9.8 | 1.3 | 0.4 | 49.4 | 31.2 | 6.8 |
| BAT | 2020-01 | 2512 | 6.8 | 1.0 | 0.2 | 41.2 | 19.5 | 4.0 |
| BCH | 2020-01 | 2512 | 5.3 | 0.7 | 0.2 | 33.2 | 15.6 | 3.0 |
| BIO | 2025-01 | 683 | 14.6 | 1.3 | 0.1 | 65.1 | 44.2 | 16.4 |
| BONK | 2023-12 | 1068 | 11.4 | 1.1 | 0.4 | 59.6 | 38.7 | 9.2 |
| CHIP | 2026-04 | 210 | 15.2 | 1.4 | 0 | 58.6 | 34.3 | 6.1 |
| DOGE | 2020-01 | 2512 | 6.7 | 1.3 | 0.6 | 40.4 | 21.3 | 4.3 |
| DOT | 2020-08 | 2282 | 6.5 | 1.0 | 0.3 | 41.9 | 21.8 | 4.1 |
| EIGEN | 2024-10 | 777 | 10.6 | 1.0 | 0.3 | 61.5 | 43.4 | 9.9 |
| ETC | 2020-01 | 2512 | 5.9 | 1.1 | 0.3 | 41.2 | 20.1 | 4.2 |
| FET | 2020-01 | 2512 | 11.4 | 1.3 | 0.3 | 48.0 | 30.9 | 9.6 |
| FLOKI | 2023-05 | 1292 | 7.6 | 0.9 | 0.4 | 50.0 | 28.8 | 6.7 |
| GRAM | 2026-07 | 138 | 1.4 | 0 | 0 | 26.6 | 3.7 | 0 |
| GRT | 2020-12 | 2161 | 8.9 | 1.3 | 0.4 | 52.6 | 31.7 | 6.0 |
| HBAR | 2020-01 | 2512 | 7.5 | 1.0 | 0.3 | 40.3 | 22.4 | 3.9 |
| IMX | 2022-01 | 1772 | 8.5 | 0.9 | 0.1 | 55.4 | 33.4 | 6.1 |
| LTC | 2020-01 | 2512 | 5.1 | 0.8 | 0.2 | 33.7 | 17.7 | 3.7 |
| MEGA | 2026-04 | 201 | 8.0 | 0 | 0 | 48.3 | 28.5 | 11.6 |
| OP | 2022-06 | 1630 | 7.2 | 1.0 | 0.2 | 51.8 | 31.4 | 6.3 |
| PENGU | 2024-12 | 700 | 11.1 | 1.1 | 0.1 | 57.4 | 39.5 | 13.7 |
| PEPE | 2023-05 | 1292 | 10.0 | 1.2 | 0.5 | 53.3 | 34.3 | 6.8 |
| PNUT | 2024-11 | 736 | 12.6 | 1.5 | 0.4 | 57.0 | 42.4 | 18.2 |
| POL | 2024-09 | 795 | 4.5 | 0.5 | 0.1 | 47.0 | 20.4 | 3.5 |
| QNT | 2021-07 | 1937 | 4.3 | 0.6 | 0.1 | 32.1 | 17.7 | 3.4 |
| RE | 2026-06 | 152 | 11.2 | 0.7 | 0 | 60.2 | 39.0 | 5.7 |
| RENDER | 2024-07 | 844 | 5.9 | 0.5 | 0.2 | 47.4 | 29.7 | 7.4 |
| SEI | 2023-08 | 1190 | 8.0 | 0.7 | 0.08 | 52.4 | 29.4 | 5.1 |
| SENT | 2026-01 | 299 | 7.0 | 0.3 | 0 | 42.6 | 11.9 | 0.4 |
| SHIB | 2021-05 | 2017 | 6.9 | 1.3 | 0.3 | 40.4 | 23.3 | 2.8 |
| SNX | 2020-07 | 2322 | 10.1 | 1.2 | 0.4 | 53.2 | 33.2 | 5.3 |
| STRK | 2024-02 | 1001 | 8.2 | 0.9 | 0.5 | 57.5 | 36.2 | 10.6 |
| SUI | 2023-05 | 1294 | 6.6 | 0.6 | 0.2 | 46.2 | 27.9 | 6.2 |
| TRUMP | 2025-01 | 667 | 7.6 | 1.2 | 0.1 | 58.2 | 28.4 | 7.2 |
| VIRTUAL | 2025-04 | 585 | 8.2 | 0.7 | 0.2 | 47.8 | 30.8 | 7.9 |
| W | 2024-04 | 958 | 8.8 | 1.1 | 0.4 | 60.5 | 41.9 | 9.9 |
| WIF | 2024-03 | 987 | 12.6 | 1.0 | 0.4 | 60.8 | 38.4 | 12.0 |
| WLD | 2023-07 | 1212 | 10.5 | 1.2 | 0.3 | 56.9 | 36.4 | 8.7 |
| WLFI | 2025-09 | 442 | 4.8 | 0.9 | 0.2 | 46.5 | 21.8 | 7.3 |
| XLM | 2020-01 | 2512 | 5.5 | 0.9 | 0.3 | 35.2 | 18.1 | 3.3 |
| XPL | 2025-09 | 418 | 13.9 | 1.2 | 0.2 | 61.4 | 42.9 | 12.1 |
| XRP | 2020-01 | 2512 | 5.7 | 1.1 | 0.4 | 31.4 | 17.5 | 5.6 |
| XTZ | 2020-01 | 2512 | 6.6 | 1.1 | 0.2 | 41.6 | 22.7 | 3.1 |
| ZEC | 2020-01 | 2512 | 8.4 | 1.2 | 0.5 | 43.8 | 28.1 | 6.1 |
| ZRO | 2024-06 | 880 | 8.4 | 0.5 | 0.1 | 54.2 | 30.1 | 6.0 |
| ZRX | 2020-01 | 2512 | 8.4 | 1.3 | 0.3 | 44.2 | 23.9 | 6.5 |

### 4.5 On the USD-M perpetual

The same counts on the perpetual's daily bars (`desc/touch_shares_perp.csv`). HYPE's longer Binance record is
here: 535 days from 2025-05-30.

| coin | from | days | day>=10% | day>=20% | day>=30% | day>=40% | 30d>=20% | 30d>=30% | 30d>=40% | 30d>=50% |
|---|---|---|---|---|---|---|---|---|---|---|
| HYPE | 2025-05 | 535 | 3.4 | 0.2 | 0.2 | 0.2 | 29.4 | 12.3 | 6.5 | 5.7 |
| NEAR | 2020-10 | 2223 | 9.7 | 1.3 | 0.3 | 0.1 | 50.5 | 30.9 | 14.9 | 5.2 |
| BTC | 2020-01 | 2511 | 1.8 | 0.2 | 0.08 | 0.04 | 16.8 | 6.4 | 2.9 | 1.4 |
| ETH | 2020-01 | 2511 | 4.1 | 0.6 | 0.08 | 0.08 | 28.2 | 13.5 | 5.8 | 2.8 |
| SOL | 2020-09 | 2254 | 7.3 | 1.3 | 0.3 | 0.09 | 44.4 | 26.7 | 13.1 | 5.8 |
| BNB | 2020-02 | 2471 | 4.3 | 0.6 | 0.3 | 0.08 | 22.4 | 10.2 | 4.4 | 2.5 |
| AAVE | 2020-10 | 2222 | 8.1 | 1.5 | 0.4 | 0.1 | 47.5 | 26.9 | 13.4 | 5.9 |
| UNI | 2020-09 | 2250 | 8.4 | 1.2 | 0.3 | 0.09 | 46.6 | 27.4 | 13.9 | 5.6 |
| SKY | 2025-09 | 433 | 2.3 | 0.2 | 0.2 | 0.2 | 30.7 | 10.9 | 7.4 | 3.0 |
| LDO | 2022-09 | 1516 | 7.8 | 0.9 | 0.1 | 0.07 | 51.2 | 26.2 | 12.0 | 4.4 |
| JTO | 2023-12 | 1074 | 10.3 | 1.1 | 0.3 | 0.09 | 55.7 | 32.8 | 16.3 | 7.8 |
| RAY | 2021-08 | 452 | 10.8 | 1.5 | 0.4 | 0.2 | 67.4 | 47.5 | 24.1 | 12.1 |
| AERO | 2024-12 | 712 | 8.7 | 0.4 | 0.1 | 0.1 | 53.7 | 38.7 | 23.0 | 8.2 |
| CRV | 2020-09 | 2267 | 12.1 | 2.2 | 0.9 | 0.2 | 54.9 | 35.2 | 19.7 | 11.6 |
| COMP | 2020-06 | 2330 | 7.9 | 1.1 | 0.3 | 0.09 | 46.0 | 26.9 | 13.0 | 6.0 |
| ENA | 2024-04 | 958 | 11.7 | 0.8 | 0.1 | 0.1 | 59.6 | 38.3 | 21.2 | 11.0 |
| LINK | 2020-01 | 2495 | 7.5 | 1.3 | 0.4 | 0.1 | 40.7 | 21.9 | 11.2 | 5.7 |
| PYTH | 2023-11 | 1090 | 8.2 | 0.9 | 0.4 | 0.09 | 60.2 | 36.2 | 17.0 | 5.8 |
| MORPHO | 2024-11 | 719 | 7.9 | 0.8 | 0.3 | 0.1 | 49.0 | 22.0 | 13.8 | 5.8 |
| SYRUP | 2025-05 | 558 | 6.3 | 0.2 | 0.2 | 0 | 46.7 | 28.7 | 14.9 | 2.1 |
| ASTER | 2025-09 | 423 | 8.3 | 1.4 | 0.5 | 0.2 | 31.5 | 22.8 | 12.4 | 4.3 |
| ORCA | 2024-12 | 710 | 8.6 | 0.6 | 0.3 | 0.1 | 47.9 | 29.5 | 15.0 | 7.6 |
| INJ | 2022-08 | 1552 | 7.2 | 0.8 | 0.3 | 0.1 | 45.1 | 23.3 | 11.4 | 4.0 |
| ONDO | 2024-01 | 1031 | 7.5 | 0.7 | 0.2 | 0.10 | 48.5 | 24.7 | 10.8 | 4.4 |

---

## 5. Intraday wick depth

Daily bars 2020-01-01..2026-11-17 [A]:

- **low/open:** the day's low against its open;
- **low/close:** the low against the same day's close;
- **shadow:** the lower shadow, low against min(open, close).
- Percentile columns give the signed value: "p10" is exceeded in depth on 10% of days.
- These are shapes of single candles, not returns of a bid.

| coin/group | days | low/open: median | p10 | p1 | p0.1 | min | low/close: median | p10 | p1 | p0.1 | min | shadow >=5% | >=10% | >=20% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYPE | 55 | -2.5 | -5.7 | -12.4 | -15.9 | -16 | -2.1 | -5.2 | -10.2 | -12.0 | -12 | 1.8 | 0 | 0 |
| NEAR | 2226 | -3.4 | -9.7 | -22.0 | -42.0 | -49 | -3.3 | -9.8 | -20.2 | -31.7 | -37 | 11.1 | 1.8 | 0.3 |
| BTC | 2513 | -1.5 | -4.9 | -12.8 | -21.4 | -44 | -1.6 | -5.1 | -10.6 | -16.5 | -32 | 2.5 | 0.4 | 0.04 |
| ETH | 2513 | -2.0 | -6.6 | -16.1 | -26.5 | -48 | -2.2 | -6.8 | -13.9 | -22.4 | -36 | 4.6 | 1.0 | 0.1 |
| SOL | 2290 | -2.9 | -9.0 | -20.4 | -40.2 | -53 | -2.9 | -9.6 | -20.2 | -33.4 | -37 | 9.9 | 2.1 | 0.2 |
| BNB | 2513 | -1.7 | -6.2 | -16.3 | -32.3 | -46 | -2.0 | -6.2 | -15.4 | -27.3 | -42 | 4.7 | 1.0 | 0.08 |
| AAVE | 2225 | -3.1 | -9.0 | -21.1 | -37.0 | -71 | -3.1 | -9.4 | -19.7 | -28.5 | -65 | 9.8 | 1.9 | 0.3 |
| UNI | 2253 | -3.1 | -9.0 | -20.8 | -35.8 | -75 | -3.0 | -8.9 | -21.1 | -49.6 | -91 | 8.9 | 1.6 | 0.4 |
| SKY | 427 | -2.1 | -6.8 | -11.3 | -32.7 | -48 | -2.2 | -6.1 | -11.3 | -31.7 | -43 | 2.8 | 0.2 | 0.2 |
| MKR | 1881 | -2.9 | -8.4 | -19.7 | -31.5 | -48 | -2.9 | -8.2 | -20.1 | -32.9 | -36 | 8.2 | 1.8 | 0.3 |
| LDO | 1654 | -3.5 | -9.6 | -19.7 | -34.5 | -80 | -3.2 | -9.6 | -19.2 | -29.5 | -72 | 10.4 | 2.0 | 0.1 |
| JTO | 1077 | -3.8 | -10.1 | -19.7 | -34.7 | -78 | -3.4 | -10.0 | -21.2 | -64.6 | -94 | 11.8 | 2.4 | 0.3 |
| RAY | 1926 | -3.3 | -9.9 | -19.6 | -39.1 | -71 | -3.1 | -9.5 | -20.8 | -36.5 | -61 | 10.1 | 1.7 | 0.1 |
| AERO | 124 | -3.0 | -8.0 | -11.3 | -11.6 | -12 | -2.7 | -7.5 | -14.9 | -18.2 | -19 | 2.4 | 0 | 0 |
| CRV | 2286 | -3.6 | -10.9 | -27.6 | -43.8 | -75 | -3.5 | -10.9 | -21.7 | -37.4 | -64 | 13.3 | 3.0 | 0.4 |
| COMP | 2337 | -3.1 | -9.0 | -21.4 | -31.5 | -77 | -3.0 | -9.2 | -17.8 | -27.6 | -67 | 9.2 | 1.9 | 0.2 |
| ENA | 960 | -4.2 | -10.8 | -18.8 | -31.2 | -76 | -3.6 | -11.1 | -21.5 | -61.6 | -70 | 11.2 | 2.0 | 0.1 |
| LINK | 2513 | -2.9 | -8.5 | -21.4 | -43.7 | -100 | -3.0 | -8.8 | -17.9 | -36.3 | -100 | 8.8 | 2.0 | 0.3 |
| PYTH | 1020 | -3.7 | -9.0 | -18.4 | -30.5 | -70 | -3.3 | -8.8 | -18.0 | -50.1 | -58 | 9.5 | 1.5 | 0.3 |
| MORPHO | 411 | -2.8 | -7.0 | -13.9 | -47.1 | -67 | -2.7 | -7.5 | -17.7 | -44.3 | -59 | 4.1 | 0.5 | 0.2 |
| SYRUP | 561 | -3.3 | -8.5 | -15.4 | -48.7 | -90 | -3.0 | -8.6 | -17.1 | -58.2 | -88 | 8.0 | 0.5 | 0.2 |
| ASTER | 408 | -2.2 | -7.8 | -19.1 | -37.2 | -41 | -2.2 | -6.9 | -21.5 | -27.4 | -28 | 7.6 | 1.5 | 0.2 |
| ORCA | 712 | -3.3 | -9.2 | -17.9 | -49.3 | -84 | -2.8 | -8.4 | -28.1 | -61.8 | -80 | 9.1 | 1.1 | 0.3 |
| INJ | 2219 | -3.6 | -9.9 | -21.6 | -51.8 | -77 | -3.5 | -10.4 | -20.8 | -35.5 | -77 | 11.6 | 2.2 | 0.3 |
| ONDO | 586 | -3.0 | -7.2 | -15.3 | -40.1 | -71 | -2.6 | -7.3 | -13.9 | -40.1 | -63 | 4.9 | 0.7 | 0.2 |
| (a) user-style | 35809 | -2.9 | -8.8 | -19.6 | -41.8 | -100 | -2.8 | -8.8 | -19.4 | -36.7 | -100 | 8.6 | 1.6 | 0.2 |
| (c) Robinhood | 112696 | -3.0 | -8.9 | -20.1 | -42.6 | -100 | -2.9 | -8.8 | -20.1 | -41.3 | -100 | 9.0 | 1.7 | 0.3 |
| (b) top-100 PIT | 249099 | -3.2 | -9.8 | -22.8 | -50.7 | -100 | -3.2 | -9.6 | -21.2 | -39.5 | -100 | 11.2 | 2.1 | 0.3 |
| all USDT pairs (excl.) | 779924 | -3.1 | -9.4 | -22.0 | -48.3 | -100 | -3.0 | -8.8 | -21.4 | -47.1 | -100 | 9.6 | 1.8 | 0.3 |

- **Typical days are shallow.** The median day dips about 3% below its open on altcoins and 1.5% on BTC.
- **The deep tail is dominated by a few days.** About 1 day in 1,000 on altcoins reaches 30-50% below the open. Each
  coin's deepest low/open falls on 2025-10-10 (16 coins), 2020-03-12 (BTC, ETH, BNB, LINK) or 2021-05-19 (SOL, NEAR,
  MKR); the exceptions are AERO and HYPE, which have only months of spot data. LINK's -100% is the $0.0001 print of
  2020-03-12.
- **Recovering wicks are uncommon.** A lower shadow of 10% or more (the low 10% under both the open and the close)
  appears on about 2% of days for the long-listed altcoins (0.2-3% across the user-style coins) and 0.4% for BTC.

---

## 6. Market-wide wick days and clustering

### 6.1 Definition

- **Active coins:** on each day, the coins in that month's top 100 (set b) with a valid prior-close reference:
  80-86 in 2020-01..03 (fewer eligible pairs), 95-96 in 2020-04..05, 98-100 from 2020-06.
- **Counts:** n15, n25, n40 = how many of them had a low at least 15%, 25% or 40% below the prior close.
- **Market-wide day:** at least 10% of the active coins at the 15% depth. Thresholds of 5% and 20% are shown as
  sensitivities.

### 6.2 How many [A]

| year | days | market-wide (10% rule) | 5% rule | 20% rule | days with any coin >= 40% |
|---|---|---|---|---|---|
| 2020 | 366 | 31 | 46 | 16 | 13 |
| 2021 | 365 | 48 | 68 | 29 | 13 |
| 2022 | 365 | 24 | 32 | 16 | 13 |
| 2023 | 365 | 9 | 12 | 6 | 1 |
| 2024 | 366 | 22 | 25 | 12 | 3 |
| 2025 | 365 | 15 | 29 | 12 | 10 |
| 2026 | 321 | 6 | 11 | 4 | 10 |

**Top 25 days by n15:**

| day | active | >=10% | >=15% | >=25% | >=40% | >=50% |
|---|---|---|---|---|---|---|
| 2021-12-04 | 100 | 100 | 100 | 81 | 14 | 1 |
| 2021-05-21 | 100 | 100 | 100 | 71 | 1 | 0 |
| 2021-05-19 | 100 | 100 | 100 | 100 | 97 | 74 |
| 2021-05-23 | 100 | 100 | 100 | 94 | 8 | 0 |
| 2021-06-21 | 100 | 100 | 99 | 33 | 1 | 0 |
| 2021-09-07 | 100 | 100 | 99 | 88 | 4 | 0 |
| 2021-02-23 | 100 | 99 | 99 | 83 | 4 | 0 |
| 2025-10-10 | 100 | 99 | 98 | 94 | 92 | 90 |
| 2022-05-11 | 100 | 100 | 98 | 80 | 29 | 8 |
| 2022-11-09 | 100 | 98 | 97 | 40 | 3 | 1 |
| 2021-04-18 | 99 | 98 | 97 | 61 | 5 | 1 |
| 2025-02-03 | 100 | 98 | 95 | 78 | 0 | 0 |
| 2024-04-12 | 100 | 97 | 95 | 59 | 1 | 0 |
| 2024-08-05 | 100 | 98 | 95 | 21 | 0 | 0 |
| 2022-11-08 | 100 | 99 | 95 | 59 | 8 | 2 |
| 2024-04-13 | 100 | 98 | 94 | 65 | 0 | 0 |
| 2024-12-09 | 100 | 98 | 94 | 67 | 2 | 0 |
| 2021-01-11 | 100 | 99 | 94 | 38 | 0 | 0 |
| 2021-02-22 | 100 | 96 | 93 | 51 | 1 | 1 |
| 2020-11-26 | 100 | 98 | 92 | 16 | 0 | 0 |
| 2022-01-22 | 99 | 98 | 91 | 9 | 0 | 0 |
| 2022-05-09 | 100 | 98 | 91 | 10 | 2 | 2 |
| 2022-05-12 | 100 | 97 | 90 | 23 | 3 | 3 |
| 2023-06-10 | 100 | 98 | 89 | 39 | 1 | 0 |
| 2024-01-03 | 100 | 95 | 87 | 31 | 0 | 0 |

- **Eleven days had at least 97 coins 15% or more down:** 2021-12-04, 2021-05-21, 2021-05-19 and 2021-05-23 (all
  100); 2021-06-21, 2021-09-07 and 2021-02-23 (99); 2025-10-10 and 2022-05-11 (98); 2022-11-09 and 2021-04-18 (97,
  the latter of 99 active).
- **Only two of those days reached the 40% and 50% depths broadly:**
  - 2021-05-19: 97 coins at least 40% down, 74 at least 50%;
  - 2025-10-10: 92 and 90.
- **2020-03-12 had 80 of 86 coins at least 40% down.**

<details><summary>All 155 market-wide days (n15 / n25 / n40 / share of active coins at the 15% depth)</summary>

| day | active | >=15% | >=25% | >=40% | share >=15% |
|---|---|---|---|---|---|
| 2020-02-15 | 83 | 10 | 2 | 0 | 12 |
| 2020-02-16 | 83 | 27 | 2 | 0 | 33 |
| 2020-02-17 | 83 | 11 | 1 | 0 | 13 |
| 2020-02-26 | 83 | 37 | 0 | 0 | 45 |
| 2020-03-08 | 86 | 55 | 1 | 0 | 64 |
| 2020-03-12 | 86 | 85 | 85 | 80 | 99 |
| 2020-03-13 | 86 | 83 | 59 | 5 | 97 |
| 2020-03-16 | 86 | 83 | 28 | 0 | 97 |
| 2020-03-20 | 86 | 16 | 1 | 0 | 19 |
| 2020-04-10 | 95 | 14 | 0 | 0 | 15 |
| 2020-05-10 | 96 | 63 | 1 | 0 | 66 |
| 2020-06-11 | 99 | 17 | 2 | 0 | 17 |
| 2020-06-27 | 99 | 16 | 0 | 0 | 16 |
| 2020-07-27 | 100 | 27 | 3 | 0 | 27 |
| 2020-08-02 | 100 | 30 | 2 | 1 | 30 |
| 2020-08-11 | 100 | 17 | 1 | 0 | 17 |
| 2020-08-19 | 100 | 10 | 1 | 1 | 10 |
| 2020-08-21 | 100 | 16 | 0 | 0 | 16 |
| 2020-08-25 | 100 | 17 | 0 | 0 | 17 |
| 2020-09-02 | 99 | 23 | 2 | 0 | 23 |
| 2020-09-03 | 99 | 86 | 42 | 2 | 87 |
| 2020-09-05 | 99 | 66 | 22 | 1 | 67 |
| 2020-09-07 | 99 | 18 | 0 | 0 | 18 |
| 2020-09-13 | 99 | 11 | 0 | 0 | 11 |
| 2020-09-21 | 99 | 39 | 2 | 0 | 39 |
| 2020-09-23 | 99 | 16 | 0 | 0 | 16 |
| 2020-10-02 | 100 | 15 | 0 | 0 | 15 |
| 2020-10-06 | 100 | 29 | 3 | 0 | 29 |
| 2020-11-18 | 100 | 12 | 0 | 0 | 12 |
| 2020-11-26 | 100 | 92 | 16 | 0 | 92 |
| 2020-12-23 | 100 | 76 | 32 | 2 | 76 |
| 2021-01-08 | 100 | 15 | 3 | 0 | 15 |
| 2021-01-10 | 100 | 18 | 0 | 0 | 18 |
| 2021-01-11 | 100 | 94 | 38 | 0 | 94 |
| 2021-01-21 | 100 | 59 | 5 | 0 | 59 |
| 2021-01-27 | 100 | 18 | 0 | 0 | 18 |
| 2021-02-06 | 100 | 18 | 0 | 0 | 18 |
| 2021-02-07 | 100 | 12 | 0 | 0 | 12 |
| 2021-02-10 | 100 | 14 | 0 | 0 | 14 |
| 2021-02-14 | 100 | 19 | 0 | 0 | 19 |
| 2021-02-15 | 100 | 77 | 8 | 1 | 77 |
| 2021-02-20 | 100 | 24 | 6 | 0 | 24 |
| 2021-02-22 | 100 | 93 | 51 | 1 | 93 |
| 2021-02-23 | 100 | 99 | 83 | 4 | 99 |
| 2021-02-28 | 100 | 34 | 0 | 0 | 34 |
| 2021-03-24 | 100 | 19 | 1 | 0 | 19 |
| 2021-04-07 | 99 | 32 | 3 | 0 | 32 |
| 2021-04-18 | 99 | 97 | 61 | 5 | 98 |
| 2021-04-19 | 99 | 10 | 0 | 0 | 10 |
| 2021-04-22 | 99 | 18 | 0 | 0 | 18 |
| 2021-04-23 | 99 | 77 | 18 | 1 | 78 |
| 2021-05-04 | 100 | 17 | 0 | 0 | 17 |
| 2021-05-10 | 100 | 65 | 2 | 0 | 65 |
| 2021-05-12 | 100 | 69 | 7 | 0 | 69 |
| 2021-05-17 | 100 | 14 | 1 | 0 | 14 |
| 2021-05-19 | 100 | 100 | 100 | 97 | 100 |
| 2021-05-20 | 100 | 10 | 0 | 0 | 10 |
| 2021-05-21 | 100 | 100 | 71 | 1 | 100 |
| 2021-05-22 | 100 | 35 | 0 | 0 | 35 |
| 2021-05-23 | 100 | 100 | 94 | 8 | 100 |
| 2021-05-25 | 100 | 19 | 0 | 0 | 19 |
| 2021-05-28 | 100 | 74 | 2 | 0 | 74 |
| 2021-05-29 | 100 | 13 | 0 | 0 | 13 |
| 2021-06-04 | 100 | 38 | 0 | 0 | 38 |
| 2021-06-08 | 100 | 14 | 0 | 0 | 14 |
| 2021-06-21 | 100 | 99 | 33 | 1 | 99 |
| 2021-06-22 | 100 | 74 | 0 | 0 | 74 |
| 2021-09-07 | 100 | 99 | 88 | 4 | 99 |
| 2021-09-13 | 100 | 17 | 0 | 0 | 17 |
| 2021-09-20 | 100 | 79 | 3 | 0 | 79 |
| 2021-09-21 | 100 | 10 | 0 | 0 | 10 |
| 2021-09-24 | 100 | 44 | 0 | 0 | 44 |
| 2021-10-27 | 100 | 53 | 1 | 0 | 53 |
| 2021-11-10 | 100 | 36 | 0 | 0 | 36 |
| 2021-11-16 | 100 | 44 | 1 | 0 | 44 |
| 2021-11-18 | 100 | 14 | 0 | 0 | 14 |
| 2021-11-26 | 100 | 41 | 0 | 0 | 41 |
| 2021-12-04 | 100 | 100 | 81 | 14 | 100 |
| 2021-12-13 | 100 | 26 | 0 | 0 | 26 |
| 2022-01-05 | 100 | 23 | 0 | 0 | 23 |
| 2022-01-21 | 99 | 70 | 1 | 0 | 71 |
| 2022-01-22 | 99 | 91 | 9 | 0 | 92 |
| 2022-01-24 | 99 | 63 | 0 | 0 | 64 |
| 2022-02-24 | 100 | 38 | 0 | 0 | 38 |
| 2022-04-06 | 100 | 10 | 0 | 0 | 10 |
| 2022-04-11 | 100 | 10 | 0 | 0 | 10 |
| 2022-04-30 | 100 | 36 | 1 | 0 | 36 |
| 2022-05-05 | 100 | 35 | 0 | 0 | 35 |
| 2022-05-09 | 100 | 91 | 10 | 2 | 91 |
| 2022-05-11 | 100 | 98 | 80 | 29 | 98 |
| 2022-05-12 | 100 | 90 | 23 | 3 | 90 |
| 2022-05-16 | 98 | 15 | 1 | 1 | 15 |
| 2022-05-18 | 98 | 13 | 0 | 0 | 13 |
| 2022-05-26 | 98 | 15 | 1 | 0 | 15 |
| 2022-06-01 | 100 | 17 | 1 | 0 | 17 |
| 2022-06-13 | 100 | 55 | 1 | 0 | 55 |
| 2022-06-16 | 100 | 33 | 0 | 0 | 33 |
| 2022-06-18 | 100 | 31 | 1 | 0 | 31 |
| 2022-08-19 | 100 | 10 | 1 | 0 | 10 |
| 2022-09-18 | 100 | 17 | 2 | 0 | 17 |
| 2022-11-08 | 100 | 95 | 59 | 8 | 95 |
| 2022-11-09 | 100 | 97 | 40 | 3 | 97 |
| 2022-12-16 | 100 | 28 | 3 | 1 | 28 |
| 2023-02-09 | 100 | 40 | 0 | 0 | 40 |
| 2023-03-03 | 100 | 12 | 0 | 0 | 12 |
| 2023-03-15 | 100 | 12 | 0 | 0 | 12 |
| 2023-05-08 | 100 | 14 | 0 | 0 | 14 |
| 2023-06-05 | 100 | 25 | 1 | 0 | 25 |
| 2023-06-10 | 100 | 89 | 39 | 1 | 89 |
| 2023-08-17 | 100 | 74 | 8 | 0 | 74 |
| 2023-11-09 | 99 | 27 | 2 | 0 | 27 |
| 2023-12-11 | 100 | 35 | 1 | 0 | 35 |
| 2024-01-03 | 100 | 87 | 31 | 0 | 87 |
| 2024-02-28 | 99 | 14 | 0 | 0 | 14 |
| 2024-03-03 | 100 | 10 | 0 | 0 | 10 |
| 2024-03-05 | 100 | 80 | 21 | 0 | 80 |
| 2024-03-15 | 100 | 35 | 0 | 0 | 35 |
| 2024-03-16 | 100 | 12 | 0 | 0 | 12 |
| 2024-03-19 | 100 | 10 | 0 | 0 | 10 |
| 2024-04-12 | 100 | 95 | 59 | 1 | 95 |
| 2024-04-13 | 100 | 94 | 65 | 0 | 94 |
| 2024-06-07 | 100 | 67 | 1 | 0 | 67 |
| 2024-06-17 | 100 | 12 | 0 | 0 | 12 |
| 2024-06-18 | 100 | 45 | 0 | 0 | 45 |
| 2024-07-04 | 99 | 20 | 1 | 0 | 20 |
| 2024-07-05 | 99 | 38 | 0 | 0 | 38 |
| 2024-08-05 | 100 | 95 | 21 | 0 | 95 |
| 2024-10-01 | 100 | 18 | 0 | 0 | 18 |
| 2024-10-25 | 100 | 44 | 0 | 0 | 44 |
| 2024-11-12 | 100 | 17 | 0 | 0 | 17 |
| 2024-12-09 | 100 | 94 | 67 | 2 | 94 |
| 2024-12-18 | 100 | 12 | 0 | 0 | 12 |
| 2024-12-19 | 100 | 15 | 0 | 0 | 15 |
| 2024-12-20 | 100 | 18 | 0 | 0 | 18 |
| 2025-01-18 | 99 | 10 | 0 | 0 | 10 |
| 2025-01-19 | 99 | 22 | 1 | 0 | 22 |
| 2025-02-02 | 100 | 77 | 3 | 0 | 77 |
| 2025-02-03 | 100 | 95 | 78 | 0 | 95 |
| 2025-02-24 | 100 | 53 | 1 | 0 | 53 |
| 2025-03-03 | 100 | 85 | 5 | 0 | 85 |
| 2025-03-09 | 100 | 22 | 0 | 0 | 22 |
| 2025-04-06 | 100 | 44 | 0 | 0 | 44 |
| 2025-05-30 | 99 | 30 | 2 | 1 | 30 |
| 2025-07-23 | 100 | 22 | 0 | 0 | 22 |
| 2025-08-14 | 100 | 12 | 0 | 0 | 12 |
| 2025-09-22 | 99 | 26 | 1 | 0 | 26 |
| 2025-10-10 | 100 | 98 | 94 | 92 | 98 |
| 2025-11-03 | 100 | 65 | 0 | 0 | 65 |
| 2025-11-21 | 100 | 16 | 0 | 0 | 16 |
| 2026-01-31 | 100 | 86 | 3 | 0 | 86 |
| 2026-02-05 | 100 | 72 | 0 | 0 | 72 |
| 2026-06-04 | 100 | 17 | 1 | 0 | 17 |
| 2026-06-05 | 100 | 34 | 4 | 1 | 34 |
| 2026-08-22 | 100 | 14 | 0 | 0 | 14 |
| 2026-11-14 | 100 | 53 | 2 | 0 | 53 |

</details>

### 6.3 Clustering: what share of coin-level deep wicks fall on market-wide days [A]

- **Leave-one-out.** A coin-day counts as market-wide when the share of the *other* active coins at the 15% depth
  reaches the threshold, so a coin's own wick never makes its day market-wide.
- **Groups.** The (a) and (c) rows use only their coin-days inside set (b).

| group | market-wide if others >= | coin-days | share of days market-wide | wicks>=15% | on mw days | wicks>=25% | on mw days  | wicks>=40% | on mw days   |
|---|---|---|---|---|---|---|---|---|---|
| (b) top-100 PIT | 5% | 249095 | 8.8 | 8100 | 86 | 1962 | 93 | 408 | 92 |
| (b) top-100 PIT | 10% | 249095 | 6.1 | 8100 | 81 | 1962 | 92 | 408 | 91 |
| (b) top-100 PIT | 20% | 249095 | 3.8 | 8100 | 71 | 1962 | 91 | 408 | 91 |
| (a) user-style in (b) | 5% | 29456 | 8.0 | 637 | 92 | 140 | 100 | 28 | 100 |
| (a) user-style in (b) | 10% | 29456 | 5.5 | 637 | 88 | 140 | 99 | 28 | 100 |
| (a) user-style in (b) | 20% | 29456 | 3.4 | 637 | 82 | 140 | 99 | 28 | 100 |
| (c) Robinhood in (b) | 5% | 91208 | 8.0 | 2157 | 91 | 490 | 97 | 101 | 98 |
| (c) Robinhood in (b) | 10% | 91208 | 5.4 | 2157 | 87 | 490 | 97 | 101 | 98 |
| (c) Robinhood in (b) | 20% | 91208 | 3.4 | 2157 | 80 | 490 | 97 | 101 | 98 |

How many *other* top-100 coins were at least 15% down on the day of each coin-level wick (set b):

| depth | wicks | others_0 | others_1_4 | others_5_9 | others_10_plus |
|---|---|---|---|---|---|
| 15 | 8100 | 428 | 706 | 414 | 6552 |
| 25 | 1962 | 57 | 78 | 16 | 1811 |
| 40 | 408 | 12 | 19 | 4 | 373 |

- **Deep fills are market-wide fills.** At the 25% and 40% depths more than 90% of coin-level wicks happen on days
  when at least 10% of the other top-100 coins (usually far more) were also 15% or more down.
  - A stink-bid ladder across several coins therefore fills on the same days, and the bids are not diversified.
  - A test must cluster by day (or by event) for inference.
- **Coin-specific deep wicks are the knife-catching cases** (section 6.4).

### 6.4 Coin-specific deep wicks: the knife-catching list [A]

Lows at least 40% below the prior close in set (b) while at most 4 other top-100 coins fell 15% or more. 31
coin-days. Closes and later prices are deliberately not shown.

| coin | day | low vs prior close | other top-100 coins >= 15% down that day | day volume ($M) |
|---|---|---|---|---|
| VITE | 2020-02-13 | -53% | 4 | 1.1 |
| TCT | 2020-03-07 | -49% | 0 | 0.1 |
| LSK | 2020-07-09 | -50% | 1 | 0.3 |
| BAND | 2020-10-23 | -48% | 0 | 10.2 |
| DOGE | 2021-01-30 | -52% | 0 | 1,751.5 |
| XEM | 2021-03-12 | -45% | 3 | 639.1 |
| ANC | 2022-05-10 | -49% | 3 | 88.9 |
| LUNA | 2022-05-10 | -55% | 3 | 3,641.6 |
| LUNA | 2022-05-13 | -88% | 2 | 21.3 |
| ANC | 2022-05-13 | -80% | 2 | 52.8 |
| ANC | 2022-05-24 | -49% | 0 | 282.9 |
| ANC | 2022-05-27 | -40% | 2 | 99.7 |
| LUNA | 2022-06-08 | -49% | 1 | 88.3 |
| LUNA | 2022-09-14 | -46% | 1 | 283.5 |
| LEVER | 2024-06-12 | -42% | 0 | 87.9 |
| TROY | 2025-01-02 | -51% | 0 | 235.6 |
| ACT | 2025-04-01 | -59% | 0 | 273.4 |
| OM | 2025-04-13 | -94% | 2 | 455.7 |
| OM | 2025-04-14 | -54% | 1 | 445.9 |
| LAYER | 2025-05-06 | -46% | 1 | 201.0 |
| VANA | 2025-06-20 | -81% | 1 | 3.9 |
| PNUT | 2025-12-11 | -66% | 0 | 5.6 |
| OPN | 2026-06-06 | -44% | 1 | 26.6 |
| SAHARA | 2026-06-09 | -62% | 2 | 66.0 |
| NIGHT | 2026-07-20 | -44% | 0 | 12.4 |
| DEXE | 2026-07-21 | -84% | 0 | 103.9 |
| DEXE | 2026-07-23 | -63% | 0 | 47.2 |
| ZBT | 2026-08-07 | -40% | 2 | 21.4 |
| EPIC | 2026-08-09 | -52% | 1 | 23.9 |
| SAGA | 2026-09-25 | -63% | 0 | 69.9 |
| EPIC | 2026-10-14 | -41% | 1 | 8.3 |

- **Known collapses and attacks:**
  - LUNA and ANC in May 2022;
  - OM on 2025-04-13: the archive's low of $0.37 matches reports of a 90% one-day collapse
    ([Cointelegraph](https://cointelegraph.com/news/mantra-price-collapses-by-over-90)) [S];
  - DEXE in July 2026, ACT 2025-04-01, TROY 2025-01-02 and SAHARA 2026-06-09 [U as to cause].
- **Other kinds of event:**
  - DOGE 2021-01-30 is the reversal of the late-January 2021 pump: its prior close was already a spike;
  - PNUT 2025-12-11 and VANA 2025-06-20 look like isolated Binance spot prints (PNUT's perpetual fell only 6%).
- **No user-style coin appears in this list.** All their deep wicks were market-wide (section 6.3). This is a count,
  not evidence that a "revenue" filter avoids collapses.
- **The biggest collapses are not in this list either, because the market fell with them.** FTT (best rank 19;
  2022-11-08 low 89% below the prior close) and LUNA (best rank 3; 2022-05-09..12, from -53% to -99.97%) wicked
  on market-wide days. "Market-wide" therefore does not mean "safe".

---

## 7. Three sample crashes in trade data: could a large bid fill?

For each event and coin [A]:

- **Data:** the Binance spot aggTrades file for the UTC day, plus the HYPE perpetual on 2025-10-10, since HYPE had no
  Binance spot pair then. Each file was sha256-checked against its `.CHECKSUM`.
- **Consistency check:** the trades' low equals the 1d kline's on all 13 files, and so does the USDT volume (the HYPE
  perpetual's within 0.002%).
- **Levels:** 10, 20, 30 and 40% below the prior day's close.

| event | coin | prior close | day low vs prior close | low at (UTC) | day $M | aggTrades | kline low = trade low |
|---|---|---|---|---|---|---|---|
| 2021-05-19 | NEAR | 5.674 | -48.9 | 13:10:33 | 101 | 207,879 | yes |
| 2021-05-19 | SOL | 55.98 | -52.7 | 12:55:52 | 986 | 1,210,251 | yes |
| 2021-05-19 | AAVE | 628.8 | -44.3 | 12:56:03 | 620 | 818,192 | yes |
| 2021-05-19 | LINK | 42.57 | -50.7 | 12:54:56 | 955 | 1,147,322 | yes |
| 2024-08-05 | NEAR | 4.133 | -25.6 | 13:30:07 | 205 | 478,327 | yes |
| 2024-08-05 | SOL | 138.3 | -20.5 | 06:24:50 | 3,003 | 3,145,241 | yes |
| 2024-08-05 | AAVE | 97.19 | -21.6 | 06:24:52 | 77 | 292,282 | yes |
| 2024-08-05 | LINK | 10.88 | -25.7 | 06:24:53 | 157 | 177,189 | yes |
| 2025-10-10 | NEAR | 2.88 | -46.2 | 21:20:09 | 221 | 426,889 | yes |
| 2025-10-10 | SOL | 220.9 | -23.6 | 21:28:09 | 1,934 | 1,690,376 | yes |
| 2025-10-10 | AAVE | 273.7 | -70.9 | 21:21:29 | 97 | 482,369 | yes |
| 2025-10-10 | LINK | 21.99 | -64.1 | 21:21:32 | 424 | 603,309 | yes |
| 2025-10-10 | HYPE (perp) | 43.97 | -52.2 | 21:21:25 | 921 | 1,125,150 | yes |

**Volume and time at or below each level** (UTC day only; "+" = still below at 24:00 UTC, so the total time is cut
off, and the run that reaches 24:00 may be longer than shown):

| event | coin | level | price | aggTrades <= level | $M <= level | $M seller-initiated | minutes with a trade <= level | time <= level (min) | longest run (min) | first | last |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05-19 | NEAR | -10% | 5.106 | 168,469 | 76.66 | 40.03 | 973 | 954.5+ | 796.7 | 04:23:08 | 23:59:57 |
| 2021-05-19 | NEAR | -20% | 4.539 | 126,065 | 52.34 | 27.02 | 679 | 678.5+ | 392.8 | 12:41:25 | 23:59:57 |
| 2021-05-19 | NEAR | -30% | 3.972 | 60,285 | 25.02 | 13.52 | 278 | 249.6+ | 63.7 | 12:47:58 | 23:59:57 |
| 2021-05-19 | NEAR | -40% | 3.404 | 10,885 | 4.02 | 2.26 | 26 | 21.1 | 15.3 | 12:52:22 | 13:23:55 |
| 2021-05-19 | SOL | -10% | 50.38 | 986,212 | 796.70 | 412.96 | 1132 | 1,117.3+ | 910.6 | 04:16:27 | 23:59:59 |
| 2021-05-19 | SOL | -20% | 44.78 | 586,484 | 452.15 | 235.29 | 662 | 643.6+ | 365.0 | 04:51:55 | 23:59:59 |
| 2021-05-19 | SOL | -30% | 39.18 | 234,827 | 185.32 | 98.88 | 289 | 268.0+ | 177.3 | 11:32:53 | 23:59:59 |
| 2021-05-19 | SOL | -40% | 33.59 | 39,328 | 29.68 | 16.17 | 21 | 15.6 | 4.9 | 12:50:11 | 13:13:11 |
| 2021-05-19 | AAVE | -10% | 565.9 | 544,506 | 357.13 | 185.55 | 805 | 791.8+ | 704.7 | 04:18:26 | 23:59:59 |
| 2021-05-19 | AAVE | -20% | 503 | 388,567 | 236.75 | 124.89 | 620 | 604.2+ | 361.3 | 12:42:59 | 23:59:59 |
| 2021-05-19 | AAVE | -30% | 440.1 | 108,640 | 59.69 | 33.34 | 155 | 123.6+ | 30.5 | 12:50:27 | 23:59:59 |
| 2021-05-19 | AAVE | -40% | 377.2 | 6,459 | 3.32 | 2.23 | 6 | 2.7 | 1.8 | 12:54:51 | 13:11:10 |
| 2021-05-19 | LINK | -10% | 38.31 | 1,004,266 | 833.77 | 424.65 | 1184 | 1,183.2+ | 1,182.9 | 04:16:41 | 23:59:59 |
| 2021-05-19 | LINK | -20% | 34.05 | 744,804 | 605.06 | 311.02 | 757 | 756.6+ | 754.8 | 11:23:14 | 23:59:59 |
| 2021-05-19 | LINK | -30% | 29.8 | 460,895 | 372.17 | 195.08 | 490 | 455.5+ | 120.2 | 12:42:43 | 23:59:59 |
| 2021-05-19 | LINK | -40% | 25.54 | 64,532 | 56.83 | 37.21 | 39 | 32.0 | 14.3 | 12:48:34 | 14:06:03 |
| 2024-08-05 | NEAR | -10% | 3.72 | 433,133 | 187.40 | 93.29 | 1357 | 1,346.2+ | 1,322.9 | 01:08:21 | 23:59:59 |
| 2024-08-05 | NEAR | -20% | 3.306 | 110,288 | 45.01 | 22.72 | 244 | 230.6 | 97.8 | 06:23:24 | 13:48:41 |
| 2024-08-05 | NEAR | -30% | 2.893 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2024-08-05 | NEAR | -40% | 2.48 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2024-08-05 | SOL | -10% | 124.5 | 1,483,963 | 1,489.96 | 768.68 | 560 | 553.4 | 542.6 | 01:10:29 | 14:11:13 |
| 2024-08-05 | SOL | -20% | 110.7 | 17,856 | 20.05 | 12.35 | 12 | 3.7 | 0.9 | 06:24:46 | 13:30:12 |
| 2024-08-05 | SOL | -30% | 96.83 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2024-08-05 | SOL | -40% | 83 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2024-08-05 | AAVE | -10% | 87.47 | 170,996 | 40.82 | 20.98 | 756 | 746.0 | 726.6 | 01:08:20 | 14:02:26 |
| 2024-08-05 | AAVE | -20% | 77.75 | 5,245 | 0.86 | 0.45 | 14 | 7.0 | 2.0 | 06:24:37 | 13:30:11 |
| 2024-08-05 | AAVE | -30% | 68.03 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2024-08-05 | AAVE | -40% | 58.31 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2024-08-05 | LINK | -10% | 9.792 | 165,120 | 145.04 | 74.30 | 1368 | 1,362.9+ | 1,340.7 | 01:08:24 | 23:59:53 |
| 2024-08-05 | LINK | -20% | 8.704 | 47,560 | 40.40 | 20.26 | 278 | 270.8 | 205.8 | 06:20:03 | 13:45:01 |
| 2024-08-05 | LINK | -30% | 7.616 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2024-08-05 | LINK | -40% | 6.528 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2025-10-10 | NEAR | -10% | 2.592 | 199,230 | 61.75 | 32.82 | 166 | 164.7+ | 164.4 | 21:14:29 | 23:59:59 |
| 2025-10-10 | NEAR | -20% | 2.304 | 79,863 | 18.32 | 10.06 | 57 | 43.5 | 11.0 | 21:17:25 | 22:42:57 |
| 2025-10-10 | NEAR | -30% | 2.016 | 11,063 | 2.91 | 1.54 | 6 | 4.1 | 4.0 | 21:18:51 | 21:23:00 |
| 2025-10-10 | NEAR | -40% | 1.728 | 5,778 | 1.35 | 0.72 | 3 | 2.1 | 1.7 | 21:19:31 | 21:21:42 |
| 2025-10-10 | SOL | -10% | 198.8 | 1,153,166 | 926.40 | 494.02 | 182 | 180.6+ | 135.4 | 20:56:27 | 23:59:59 |
| 2025-10-10 | SOL | -20% | 176.7 | 88,016 | 42.48 | 25.19 | 10 | 6.9 | 3.8 | 21:22:41 | 21:31:05 |
| 2025-10-10 | SOL | -30% | 154.7 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2025-10-10 | SOL | -40% | 132.6 | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| 2025-10-10 | AAVE | -10% | 246.3 | 291,114 | 60.55 | 32.63 | 175 | 171.1+ | 128.9 | 20:59:28 | 23:59:59 |
| 2025-10-10 | AAVE | -20% | 219 | 185,986 | 32.39 | 18.57 | 97 | 79.9 | 19.4 | 21:15:58 | 23:14:34 |
| 2025-10-10 | AAVE | -30% | 191.6 | 74,127 | 8.66 | 5.10 | 24 | 22.9 | 4.5 | 21:18:04 | 21:41:05 |
| 2025-10-10 | AAVE | -40% | 164.2 | 17,714 | 2.46 | 1.33 | 13 | 4.0 | 3.7 | 21:18:48 | 21:30:17 |
| 2025-10-10 | LINK | -10% | 19.79 | 497,175 | 265.40 | 134.41 | 183 | 180.9+ | 180.6 | 20:56:23 | 23:59:59 |
| 2025-10-10 | LINK | -20% | 17.59 | 418,760 | 193.89 | 96.32 | 143 | 138.3+ | 125.9 | 21:14:32 | 23:59:59 |
| 2025-10-10 | LINK | -30% | 15.39 | 141,117 | 47.49 | 25.39 | 29 | 25.0 | 24.6 | 21:17:46 | 22:06:11 |
| 2025-10-10 | LINK | -40% | 13.19 | 70,855 | 29.28 | 15.21 | 14 | 12.9 | 8.3 | 21:19:11 | 21:32:52 |
| 2025-10-10 | HYPE (perp) | -10% | 39.57 | 364,729 | 289.38 | 152.01 | 126 | 110.4+ | 16.8 | 21:13:19 | 23:59:59 |
| 2025-10-10 | HYPE (perp) | -20% | 35.17 | 64,481 | 99.28 | 51.29 | 19 | 10.7 | 7.2 | 21:15:56 | 21:33:30 |
| 2025-10-10 | HYPE (perp) | -30% | 30.78 | 34,961 | 56.80 | 29.79 | 7 | 4.6 | 2.7 | 21:16:57 | 21:26:31 |
| 2025-10-10 | HYPE (perp) | -40% | 26.38 | 5,837 | 6.06 | 3.09 | 2 | 1.0 | 1.0 | 21:20:31 | 21:21:39 |

**Columns.**

- **$M <= level:** USDT value of all trades at or below the level.
- **$M seller-initiated:** the part where a seller hit a resting bid (`is_buyer_maker` = True). That is the flow
  that fills stink bids.
- **minutes with a trade <= level:** distinct clock minutes with at least one such trade.
- **time <= level:** total time the last trade price was at or below the level.
- **longest run:** the longest continuous stretch.

**What it shows.**

- **2025-10-10 (21:15-21:30 UTC):**
  - At the 40% level, $1.35M (NEAR), $2.46M (AAVE), $29M (LINK) and $6.1M (HYPE perpetual) traded.
  - Price was at or below that level for 2.1, 4.0, 12.9 and 1.0 minutes respectively.
  - SOL's low was -23.6%.
  - The fills would have come at prices most venues never printed (section 3.4). Robinhood's quote is not the
    Binance book.
- **2021-05-19 (12:40-14:10 UTC):**
  - All four fell 44-53%.
  - The 40% level traded $3.3M (AAVE) to $57M (LINK) within 6-39 distinct minutes.
  - The 20% and 30% levels stayed under water for hours, past the end of the UTC day for the 20% level.
- **2024-08-05:**
  - The 20% level was touched briefly (06:24 UTC on SOL, AAVE and LINK; SOL for 3.7 minutes in total).
  - Nothing reached 30%.
- **Size was not the constraint at these coins.** At every touched level in the sample, at least $0.45M of
  seller-initiated volume traded at or below it (smallest: AAVE's 20% level on 2024-08-05; next, NEAR's 40% level on
  2025-10-10 with $0.72M). A $100k bid would have been at most about a fifth of that flow.
  - The constraint is having the order resting in advance.
  - With price-time priority, a resting bid at L fills before any trade prints below L. The volume printed at or
    below L is therefore an upper bound on the extra size the book could have absorbed at L.

---

## 8. Finer data: what 1-minute klines and trades would cost

Sizes come from the archive listings (exact zip bytes) [A]:

- **CSV size:** zip bytes times the CSV/zip ratio measured on samples (1m klines 3.65, aggTrades 4.98).
- **Measured throughput:** 19.6 MB/s for 48 monthly 1m-kline zips and 16.6 MB/s for 12 event-day aggTrades zips,
  both fetched with 32 threads. Single files of 3-43 MB came at 3-11 MB/s.
- **Small-file rate:** about 87.5 zips/s with checksums (the `h1` run).
- **hours_est:** the larger of the bandwidth-bound and file-rate-bound times.

| group | coins | what | files | zip GB | CSV GB (est.) | hours (est.) |
|---|---|---|---|---|---|---|
| all candidates | 486 | 1m klines, all days 2020-01-01..END | 22,547 | 25.30 | 92.4 | 0.37 |
| all candidates | 486 | 1m klines, 155 market-wide days | 35,588 | 1.59 | 5.8 | 0.11 |
| all candidates | 486 | 1m klines, the coin's own >= 15% wick days | 19,940 | 0.94 | 3.4 | 0.06 |
| all candidates | 486 | aggTrades, 155 market-wide days | 35,588 | 53.09 | 264.5 | 0.91 |
| all candidates | 486 | aggTrades, the coin's own >= 15% wick days | 19,940 | 38.62 | 192.4 | 0.66 |
| all candidates | 486 | aggTrades, all days 2020-01..last monthly file | 22,547 | 479.13 | 2,387.2 | 8.20 |
| (a) user-style | 24 | 1m klines, all days 2020-01-01..END | 1,266 | 1.75 | 6.4 | 0.03 |
| (a) user-style | 24 | 1m klines, 155 market-wide days | 1,913 | 0.10 | 0.4 | 0.01 |
| (a) user-style | 24 | 1m klines, the coin's own >= 15% wick days | 832 | 0.04 | 0.2 | 0.00 |
| (a) user-style | 24 | aggTrades, 155 market-wide days | 1,913 | 13.72 | 68.4 | 0.23 |
| (a) user-style | 24 | aggTrades, the coin's own >= 15% wick days | 832 | 4.83 | 24.1 | 0.08 |
| (a) user-style | 24 | aggTrades, all days 2020-01..last monthly file | 1,266 | 126.14 | 628.5 | 2.16 |
| (c) Robinhood | 75 | 1m klines, all days 2020-01-01..END | 3,957 | 5.23 | 19.1 | 0.08 |
| (c) Robinhood | 75 | 1m klines, 155 market-wide days | 5,944 | 0.31 | 1.1 | 0.02 |
| (c) Robinhood | 75 | 1m klines, the coin's own >= 15% wick days | 2,747 | 0.15 | 0.5 | 0.01 |
| (c) Robinhood | 75 | aggTrades, 155 market-wide days | 5,944 | 26.60 | 132.5 | 0.46 |
| (c) Robinhood | 75 | aggTrades, the coin's own >= 15% wick days | 2,747 | 13.88 | 69.1 | 0.24 |
| (c) Robinhood | 75 | aggTrades, all days 2020-01..last monthly file | 3,957 | 227.75 | 1,134.7 | 3.90 |

- **The disk is the limit, not the network.** 30 GB were free at the start; the data so far use 1 GB.
- **1-minute klines:**
  - All candidates would not fit as CSV (92 GB).
  - As parquet they would take roughly the hourly files' 49 bytes per bar times 60 bars per hour, about 45 GB with
    float64 columns, perhaps half with float32 prices as in the Bollinger study [U].
  - The Robinhood set (5.2 GB zipped) or event days (1.6 GB) fit easily.
- **aggTrades must be streamed:** download one day, keep only the reduced rows (e.g. trades within an hour of the
  low, or per-level volumes as in section 7), delete the zip.
  - The coin's own 15%-wick days for the 24 user-style coins are 4.8 GB zipped, 832 files, about 5 minutes.
  - For the 75 Robinhood coins: 13.9 GB, 2,747 files, about 15 minutes.
- **Before 2021-12, futures metrics (open interest) exist only for BTC.** An open-interest-based level finder can be
  tested only from 2021-12 onward.
- **Not checked:** the futures archive's `bookDepth` and `bookTicker` folders (order-book snapshots, futures only),
  which could show resting depth near a wick.

---

## 9. Caveats and what they mean for the design

1. **The venue matters more than the data.** Binance spot lows are a generous upper bound for a Robinhood bid:
   - stub-quote prints ($0.0001);
   - venue-specific crashes (2025-10-10: Binance's own collateral depegs, 21:36-22:16 UTC);
   - spot and perpetual lows that disagree by 10 points or more on 45 coin-days.

   A Robinhood fill model needs at least a haircut, such as requiring the level to trade for N seconds or $X of
   volume, or a second venue. Coinbase is reachable from the later environment (brief).
2. **Few independent events.** The deep tail rests on 3-7 days per depth for the user-style coins. Inference must
   cluster by event day, and any "level that works" can be fitted to 2021-05-19 and 2025-10-10 alone.
3. **Survivorship.** Set (c) holds today's Robinhood coins, so it is survivor-biased. 133 of the 485 point-in-time
   top-100 coins stopped trading on Binance spot, and the knife list (section 6.4) shows coin-specific collapses
   happen to coins that ranked high (LUNA 3, OM 21, FTT 19). The test should run on set (b) and report (c) as a
   subset.
4. **Short histories.** HYPE (55 spot days; 535 perpetual days), AERO, MORPHO, ASTER, SKY, SYRUP and ONDO have little
   or no pre-2025 Binance spot data. Use the perpetual, or MKR for SKY, or accept a shorter sample.
5. **Rebrands.** MKR → SKY, RNDR → RENDER, MATIC → POL, EOS → A, FTM → S and LIT → HEI change tickers, and
   STRAX/VIDT (10:1) and LUNA (new chain) changed the asset under the same ticker. The segment rule prevents false
   wicks. Joining a predecessor needs the swap ratio [U].
6. **Daily bars cannot order events within a day.** Whether the low came before or after a bid was placed intraday
   needs the hourly files (built) or 1m klines (event days only).
7. **Time below a level is censored at 24:00 UTC** in section 7. For shallow levels on 2021-05-19 the true duration
   is longer.

---

## 10. Rebuild commands

From the repository root, in bash (Git Bash on Windows works). About 20 minutes of active download time and 1 GB of
disk.

```bash
python3 -m analysis_2026.fetch_stinkbid_data listing                   # 776 USDT spot pairs, exclusions
python3 -m analysis_2026.fetch_stinkbid_data d1 --workers 96           # 1d spot klines, 771 pairs, 2019-10..END
python3 -m analysis_2026.fetch_stinkbid_data sets                      # sets (a), (b), (c)
python3 -m analysis_2026.fetch_stinkbid_data h1 --workers 160          # 1h spot klines, 486 candidates
python3 -m analysis_2026.fetch_stinkbid_data perp1d --workers 64       # USD-M 1d klines, Robinhood coins
python3 -m analysis_2026.fetch_stinkbid_data coverage --workers 64     # listing dates, 1m / aggTrades / metrics
python3 -m analysis_2026.fetch_stinkbid_data validate                  # section 3
python3 -m analysis_2026.fetch_stinkbid_data desc                      # sections 4-6
python3 -m analysis_2026.fetch_stinkbid_data events                    # section 7 (13 aggTrades files)
python3 -m analysis_2026.fetch_stinkbid_data sizes                     # section 8
# or everything in order:
python3 -m analysis_2026.fetch_stinkbid_data all --workers 96
```

- **Options:** `--end YYYY-MM-DD` (default 2026-11-17), `--force` (re-download), `--workers N`, and
  `--rh-pairs PATH` (a saved `get_currency_pairs` JSON, or a CSV with a `sym` column).
- **Re-running** skips files that exist. `d1` rebuilds `d1_spot_all.parquet` at the end.
- **This build used** four parallel `d1` processes (the stats of two were merged into `stats/d1.json` by hand).
  `d1 --workers 96` does the same in one process.
- **The markdown tables in this note** were generated from the CSVs above by a scratch script (not committed).

---

## Sources

- Binance public data archive: [binance-public-data README](https://github.com/binance/binance-public-data/) (file
  layout, checksums, microsecond spot timestamps from 2025-01-01); the S3 bucket
  `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision`, the only route reachable here. [A] for everything
  computed.
- Timestamp change: [Binance developer forum](https://dev.binance.vision/t/timestamp-format-inconsistency-in-historical-archives/33550) [S].
- HYPE spot listing on Binance (2026-09-24, three pairs; USD-M perpetual from May 2025):
  [crypto.news](https://crypto.news/binance-to-list-hype-with-3-spot-pairs-on-sept-24/),
  [Crypto Briefing](https://cryptobriefing.com/hyperliquid-hype-spot-trading-binance/) [S].
- Litentry LIT → Heima HEI on Binance:
  [Binance announcement](https://www.binance.com/el/support/announcement/detail/2a9feaa556f74dcdaa2192366f0e247c) [S].
- Robinhood lists Lighter's LIT:
  [BeInCrypto](https://beincrypto.com/robinhood-listing-sparks-lighter-rally-token-recovers-after-15-dip) [S].
- 2025-10-10 depegs and compensation:
  [The Block](https://www.theblock.co/news/markets/2025-10-12-binance-pays-283-million-in-compensation-following-fridays-depegs-covering-user-losses-374295),
  [Decrypt](https://decrypt.co/344026/binance-reimburses-283m-after-market-crash-and-asset-depegging-issues) [S];
  display-issue statement via `mechanics.md`
  ([Cointelegraph](https://cointelegraph.com/news/binance-tokens-not-crash-0-display-issue)) [S].
- 2023-03-24 Binance spot halt:
  [Cointelegraph](https://cointelegraph.com/news/binance-spot-trading-halted-due-to-issue-on-trailing-stop-orders),
  [TechCrunch](https://techcrunch.com/2023/03/24/crypto-giant-binance-temporarily-suspends-spot-trading/) [S].
- 2024-08-05 crash:
  [CoinDesk](https://coindesk.com/markets/2024/08/05/crypto-futures-witness-840m-in-liquidations-as-bitcoin-nosedives-ether-records-biggest-fall-since-2021) [S].
- 2021-05-19 on Binance:
  [Baumgartner and Güttler, IWH DP 25/2022](https://www.iwh-halle.de/en/publications/detail/bitcoin-flash-crash-on-may-19-2021-what-did-really-happen-on-binance)
  (cited via `mechanics.md`) [U as read here].
- Mantra OM collapse, 2025-04-13:
  [Cointelegraph](https://cointelegraph.com/news/mantra-price-collapses-by-over-90) [S].
- Robinhood order routing, fills against its ask or Bitstamp's book: `mechanics.md` in this folder and
  [Robinhood: crypto order routing](https://robinhood.com/us/en/support/articles/crypto-order-routing/) (via that
  note) [S].
- Robinhood-listed coins: the brief (orchestrator's read-only `get_currency_pairs`, 2026-11-18) and the scalping
  study's 2026-10-18 snapshot `analysis_2026/results_scalping/A/arh_pairs.csv`.
