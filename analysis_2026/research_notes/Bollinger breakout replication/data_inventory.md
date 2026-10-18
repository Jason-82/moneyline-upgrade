# Bollinger breakout replication: data inventory

Built 2026-10-18 with `python3 -m analysis_2026.fetch_bb_data all`: about 45 minutes, 510 MiB on disk (481 MiB from
the fetcher plus the rules researcher's 29 MiB `rcheck_m1/` sample), all under the gitignored `data/bbreplica/`.
After an independent check (section 12), the fetcher was fixed and the futures series of 14 contracts were rebuilt
with `h1 --symbols SOL,XRP,LTC,TRX,XLM,NEAR,FIL,LUNA,ZEC,VET,SAND,MANA,HBAR,ICP --market um --force`. That changed
only their `d1_um` files; every hourly file came out byte-identical.

Every number here is computed from the Binance archive files [A] unless tagged otherwise: [S] means a secondary source such as a news report, and [U] means not verified. Everything below is
descriptive. Under the contamination rule, no Bollinger, breakout or grid strategy was run.

## 1. What was built

| path (under `data/bbreplica/`) | contents | files | size |
|---|---|---|---|
| `h1_spot/{SYM}USDT.parquet` | Binance spot 1-hour klines, from listing to 2026-10-16 23:00 UTC | 40 | 128 MB |
| `h1_um/{SYM}USDT.parquet` | USD-M perpetual 1-hour klines, from listing (archive starts 2020-01) to 2026-10-16 23:00 UTC | 41 (40 + LUNA2) | 114 MB |
| `d1_spot/`, `d1_um/` | the archive's own 1-day klines, same columns, holes filled from daily 1d zips like the hourly files; a by-product, used as the reference for the day checks (101,569 + 87,507 days) | 40 + 41 | 13 MB |
| `funding/{SYM}USDT.parquet` | USD-M funding events | 41 | 3.7 MB |
| `h1_mark/{SYM}USDT.parquet` | USD-M mark-price 1-hour klines (`markPriceKlines`): `open_time, open, high, low, close` only; 1000x contracts divided by their multiplier. See section 1.1 | 41 | |
| `m1_um/{SYM}USDT.parquet` | USD-M 1-minute klines for BTC ETH SOL BNB XRP DOGE, 2024-07-01 00:00 .. 2026-10-16 23:59 UTC | 6 | 225 MB |
| `stats/{h1,funding,m1}.json` | per series: zips, checksums, holes filled, days repaired, placeholders trimmed | 3 | |
| `validation/*.csv`, `summary.txt` | the checks in sections 4-6 | 9 | |
| `rcheck_m1/` | not written by the fetcher: the 1m close sample (BTC ETH SOL) behind `rules_and_evidence.md` | 3 | 29 MB |

**Columns.**

- **Klines:** `open_time` (datetime64[ms, UTC], the bar's **open** time), `open, high, low, close`,
  `volume` (base units), `quote_volume` (USDT), `trades`, `taker_buy_quote`.
  - Hourly and daily files are float64 / int64.
  - The 1-minute files store prices as float32: every price column round-trips to within 0.4 tick, checked
    per column, so rounding to the tick recovers the exact price. Volumes are float32 (relative error 6e-8)
    and `trades` is int32.
- **Funding:** `calc_time` (datetime64[ms, UTC]), `rate` per interval as a fraction (0.0001 = 0.01%), and
  `interval_h` (8, 4, 2 or 1, as given in the file).
  - Raw times carry a few milliseconds of jitter (e.g. 08:00:00.005); floor to the minute before joining.
  - The archive's fundingRate files have **no mark price**. Mark-price hourly klines are fetched separately
    into `h1_mark/` (`fetch_bb_data.py mark`; section 1.1).

**Totals:** 2,435,224 spot hours, 2,099,815 futures hours, 265,396 funding events and 7,240,320 one-minute bars.

**Rebuild:** `python3 -m analysis_2026.fetch_bb_data all`, or one part at a time with
`h1 | funding | m1 | mark | validate`. Options: `--end YYYY-MM-DD`, `--symbols BTC,ETH`, `--force`, `--workers N`, `--market spot|um` (h1 only).
The script imports `s3_ls` and `s3_get_zip_csv` from `fetch_scalping_data.py` and the coin list from
`fetch_regime_data.py`. Zips are read in memory and nothing temporary is written to disk.

### 1.1 Mark-price klines (`h1_mark/`, added 2026-10-18)

Used only for liquidation checks. Coverage was compared with the perpetual's own hourly file (`h1_um/`):

- **Missing hours.** Every contract except old LUNA has hours in `h1_um` with no mark bar: 24-216 per
  contract, median 96 (BTC 216, ETH 72, SOL 192, BNB 216, DOGE 72). Liquidation checks fall back to the
  last-price low in those hours (conservative).
- **Bars before the perpetual's first hour:** 0-369 per contract (ADA 287, ALGO 369, BNB 224). Not used.
- **Placeholder bars after a contract ended.** The archive keeps publishing mark bars after delisting:
  EOS 12,303 hours after 2025-05-21, FTT 34,339 after 2022-11-14 04:00, old LUNA 1,455 after 2022-05-12 15:00,
  MATIC 18,519 after 2024-09-04. Mark files are therefore **trimmed to each contract's traded window in
  `h1_um`** before use; nothing outside that window is read.
- **Mark vs last-price lows on 2025-10-10** (a pre-registration check, no strategy run): the hourly mark low
  was 0.4-1.8% above the last-price low on BTC, ETH, SOL, XRP and ZEC, 4.9% on BNB and 5.7% on DOGE. The
  choice therefore matters on altcoins in crash hours.

## 2. Symbols and contract mapping

**The 40 coins** are the 13 named (BTC ETH SOL BNB XRP DOGE ADA AVAX LINK LTC TRX DOT BCH) plus the rest of
`fetch_regime_data.COINS`: AAVE ALGO ATOM AXS DASH EGLD EOS ETC FIL FTT HBAR ICP LUNA MANA MATIC NEAR NEO POL
SAND SHIB THETA UNI VET XLM XMR XTZ ZEC. All pairs are against USDT.

- MATIC and POL are separate files. The regime and bounce studies splice them (`regime_switch.load_binance`).
- The futures contract is `{SYM}USDT` with two exceptions:
  - **SHIB** trades as `1000SHIBUSDT`. The file is rescaled to one SHIB (prices / 1000, volume x 1000), so it
    lines up with spot.
  - **LUNA:** `h1_um/LUNAUSDT` is the old Terra perpetual (2021-01-28 .. 2022-05-12). The extra file
    `h1_um/LUNA2USDT.parquet` is the Terra 2.0 perpetual (from 2022-09-10). That is the asset spot
    `LUNAUSDT` trades after its 2022-05-31 relisting.

Coverage (first and last bar, bar count; funding first and last event, count, intervals seen):

| coin | spot 1h | bars | USD-M contract | USD-M 1h | bars | funding | events | intervals (h) |
|---|---|---|---|---|---|---|---|---|
| BTC | 2017-08-17..2026-10-16 | 80221 | BTCUSDT | 2020-01-01..2026-10-16 | 59544 | 2020-01-01..2026-09-30 | 7395 | 8 |
| ETH | 2017-08-17..2026-10-16 | 80221 | ETHUSDT | 2020-01-01..2026-10-16 | 59544 | 2020-01-01..2026-09-30 | 7395 | 8 |
| SOL | 2020-08-11..2026-10-16 | 54167 | SOLUSDT | 2020-09-14..2026-10-16 | 53369 | 2020-09-13..2026-09-30 | 6700 | 2/4/8 |
| BNB | 2017-11-06..2026-10-16 | 78284 | BNBUSDT | 2020-02-10..2026-10-16 | 58576 | 2020-02-10..2026-09-30 | 7274 | 8 |
| XRP | 2018-05-04..2026-10-16 | 74017 | XRPUSDT | 2020-01-06..2026-10-16 | 59416 | 2020-01-06..2026-09-30 | 7379 | 8 |
| DOGE | 2019-07-05..2026-10-16 | 63809 | DOGEUSDT | 2020-07-10..2026-10-16 | 54951 | 2020-07-10..2026-09-30 | 6821 | 8 |
| ADA | 2018-04-17..2026-10-16 | 74429 | ADAUSDT | 2020-01-31..2026-10-16 | 58816 | 2020-01-30..2026-09-30 | 7307 | 8 |
| AVAX | 2020-09-22..2026-10-16 | 53159 | AVAXUSDT | 2020-09-23..2026-10-16 | 53153 | 2020-09-22..2026-09-30 | 6598 | 8 |
| LINK | 2019-01-16..2026-10-16 | 67875 | LINKUSDT | 2020-01-17..2026-10-16 | 59152 | 2020-01-17..2026-09-30 | 7346 | 8 |
| LTC | 2017-12-13..2026-10-16 | 77396 | LTCUSDT | 2020-01-09..2026-10-16 | 59344 | 2020-01-09..2026-09-30 | 7370 | 8 |
| TRX | 2018-06-11..2026-10-16 | 73102 | TRXUSDT | 2020-01-15..2026-10-16 | 59200 | 2020-01-15..2026-09-30 | 7352 | 8 |
| DOT | 2020-08-18..2026-10-16 | 53982 | DOTUSDT | 2020-08-22..2026-10-16 | 53921 | 2020-08-21..2026-09-30 | 6695 | 8 |
| BCH | 2019-11-28..2026-10-16 | 60319 | BCHUSDT | 2020-01-01..2026-10-16 | 59544 | 2020-01-01..2026-09-30 | 7395 | 8 |
| AAVE | 2020-10-15..2026-10-16 | 52610 | AAVEUSDT | 2020-10-16..2026-10-16 | 52601 | 2020-10-16..2026-09-30 | 6527 | 8 |
| ALGO | 2019-06-22..2026-10-16 | 64133 | ALGOUSDT | 2020-06-16..2026-10-16 | 55527 | 2020-06-15..2026-09-30 | 6895 | 8 |
| ATOM | 2019-04-29..2026-10-16 | 65415 | ATOMUSDT | 2020-02-07..2026-10-16 | 58644 | 2020-02-06..2026-09-30 | 7285 | 8 |
| AXS | 2020-11-04..2026-10-16 | 52120 | AXSUSDT | 2020-11-20..2026-10-16 | 51761 | 2020-11-20..2026-09-30 | 7346 | 1/4/8 |
| DASH | 2019-03-28..2026-10-16 | 66183 | DASHUSDT | 2020-02-04..2026-10-16 | 58720 | 2020-02-04..2026-09-30 | 7292 | 8 |
| EGLD | 2020-09-03..2026-10-16 | 53618 | EGLDUSDT | 2020-09-14..2026-10-16 | 53369 | 2020-09-13..2026-09-30 | 6625 | 8 |
| EOS | 2018-05-28..2025-05-26 | 61231 | EOSUSDT | 2020-01-08..2025-05-21 | 47041 | 2020-01-08..2025-05-21 | 5882 | 8 |
| ETC | 2018-06-12..2026-10-16 | 73097 | ETCUSDT | 2020-01-16..2026-10-16 | 59176 | 2020-01-16..2026-09-30 | 7349 | 8 |
| FIL | 2020-10-15..2026-10-16 | 52596 | FILUSDT | 2020-10-16..2026-10-16 | 52602 | 2020-10-16..2026-09-30 | 6527 | 8 |
| FTT | 2019-12-20..2026-10-16 | 52332 | FTTUSDT | 2022-04-15..2022-11-14 | 5114 | 2022-04-14..2022-11-14 | 678 | 2/8 |
| HBAR | 2019-09-29..2026-10-16 | 61761 | HBARUSDT | 2021-03-17..2026-10-16 | 48953 | 2021-03-17..2026-09-30 | 6071 | 8 |
| ICP | 2021-05-11..2026-10-16 | 47632 | ICPUSDT | 2021-05-11..2026-10-16 | 47515 | 2022-09-01..2026-09-30 | 4473 | 8 |
| LUNA | 2020-08-21..2026-10-16 | 53486 | LUNAUSDT | 2021-01-28..2022-05-12 | 11265 | 2021-01-28..2022-05-12 | 1409 | 8 |
| MANA | 2020-08-06..2026-10-16 | 54283 | MANAUSDT | 2021-03-15..2026-10-16 | 49001 | 2021-03-15..2026-09-30 | 6077 | 8 |
| MATIC | 2019-04-26..2024-09-10 | 47071 | MATICUSDT | 2020-10-22..2024-09-04 | 33914 | 2020-10-22..2024-09-04 | 4241 | 8 |
| NEAR | 2020-10-14..2026-10-16 | 52632 | NEARUSDT | 2020-10-15..2026-10-16 | 52624 | 2020-10-14..2026-09-30 | 6532 | 8 |
| NEO | 2017-11-20..2026-10-16 | 77948 | NEOUSDT | 2020-02-17..2026-10-16 | 58408 | 2020-02-17..2026-09-30 | 7253 | 8 |
| POL | 2024-09-13..2026-10-16 | 18326 | POLUSDT | 2024-09-13..2026-10-16 | 18324 | 2024-09-13..2026-09-30 | 4483 | 4 |
| SAND | 2020-08-14..2026-10-16 | 54088 | SANDUSDT | 2021-01-25..2026-10-16 | 50177 | 2021-01-25..2026-09-30 | 6224 | 8 |
| SHIB | 2021-05-10..2026-10-16 | 47646 | 1000SHIBUSDT | 2021-05-10..2026-10-16 | 47647 | 2021-05-10..2026-09-30 | 5908 | 8 |
| THETA | 2019-04-10..2026-10-16 | 65871 | THETAUSDT | 2020-05-27..2026-10-16 | 56008 | 2020-05-26..2026-09-30 | 6955 | 8 |
| UNI | 2020-09-17..2026-10-16 | 53282 | UNIUSDT | 2020-09-18..2026-10-16 | 53273 | 2020-09-17..2026-09-30 | 6614 | 8 |
| VET | 2018-07-25..2026-10-16 | 72071 | VETUSDT | 2020-02-14..2026-10-16 | 58480 | 2020-02-14..2026-09-30 | 7262 | 8 |
| XLM | 2018-05-31..2026-10-16 | 73368 | XLMUSDT | 2020-01-20..2026-10-16 | 59080 | 2020-01-19..2026-09-30 | 7339 | 8 |
| XMR | 2019-03-15..2024-02-20 | 43218 | XMRUSDT | 2020-02-03..2026-10-16 | 58744 | 2020-02-02..2026-09-30 | 7298 | 8 |
| XTZ | 2019-09-24..2026-10-16 | 61874 | XTZUSDT | 2020-02-06..2026-10-16 | 58672 | 2020-02-05..2026-09-30 | 8640 | 1/4/8 |
| ZEC | 2019-03-21..2026-10-16 | 66351 | ZECUSDT | 2020-02-05..2026-10-16 | 58696 | 2020-02-04..2026-09-30 | 7292 | 8 |
| LUNA2 | none |  | LUNA2USDT | 2022-09-10..2026-10-16 | 35949 | 2022-09-10..2026-09-30 | 5892 | 1/4/8 |

## 3. Integrity and repairs

**Checksums.** Every zip the fetcher planned to download was listed with a `.CHECKSUM` file, and none failed the
sha256 check or failed to download: 14,926 kline zips (1h and 1d), 2,931 funding zips and 258 one-minute zips.
- The roughly 780 daily zips fetched for hole fills and repairs are not in those counts. They were checked too
  whenever a `.CHECKSUM` could be read.
- Caveat: the first build counted a zip as verified when the listing showed a `.CHECKSUM`, so a `.CHECKSUM` that
  could not be read would have passed unnoticed. The fetcher now fails such a zip and counts only hashes it actually
  compared, with `extra_zips` / `extra_verified` for the repair zips. The 15 futures series rebuilt with the fixed
  code (the 14 contracts plus LUNA2) record 175 of 175 repair zips verified.
- The independent re-download in section 12 found no checksum failure in 117 zips.

**Timestamps.** Spot timestamps are in microseconds from 2025-01-01 and are converted; futures timestamps are
in milliseconds. Futures zips carry a header row from 2022, which is dropped.

The archive has defects. The fetcher repairs what it can and lists the rest in `stats/h1.json`:

1. **Off-grid bars.** After the 2018-02-08/09 outage, the spot monthly zips for BTC, ETH, BNB, LTC and NEO
   print 43 bars stamped at hh:28:14 (2018-02-09 09:28 .. 2018-02-11 03:28). The daily zips have the same hours
   on the hour grid. The fetcher drops the off-grid bars and fills those hours from the daily zips.
2. **Holes in monthly zips.** 13 futures contracts (SOL XRP LTC TRX XLM NEAR FIL LUNA ZEC VET SAND MANA HBAR)
   are missing 2022-02-26..28 and 2022-04-01..02 (120 h each). ICP is missing 504 h (2022-09-01..21, inside its
   halt, all zero-trade). All of these were filled from the daily zips: 2,276 bars in total (2,064 futures,
   212 spot).
   - The **1-day monthly zips have the same holes**: 86 days (5 per contract, plus 21 for ICP). The first build
     did not fill them, so `d1_um` lacked those days. As a result, the 86 hole-filled hourly days had no daily
     reference and were silently skipped by the day check.
   - The fetcher now fills 1d holes the same way. All 86 days are now in `d1_um`, and the hourly bars match
     their 1-day klines (OHLC to 1e-9, trade counts equal).
3. **Wrong bars in monthly zips.** Each UTC day of hourly bars is checked against the 1-day kline (OHLC to
   1e-9). Eight spot days disagreed, and each was replaced from its daily zip, which matches the 1-day kline:
   DOGE 2021-10-28, FIL 2021-12-02, ICP 2021-12-07, ALGO 2021-12-12, XTZ 2021-12-27, and AXS 2021-12-05/07/12.
   - Example: the AXS 2021-12-05 23:00 bar closes at 106.93 in the monthly 1h zip. The 1m archive, the daily
     1h zip and the 1-day kline all say 107.45.
4. **Unresolved days.** On four days the hourly bars and the 1-day kline disagree, and the daily 1h zip does not
   match either. All fall in the first weeks of a listing and are left as they are. The 1-minute archive
   (daily 1m zips, checked by hand) settles each one:
   - **Spot FTT 2020-01-06:** the hourly bars are right. The 1m roll-up gives open 2.139 like the hourly file;
     only the 1-day kline says 2.138. `data/crypto_binance_regime/` carries the same 1-day open.
   - **Futures XRP 2020-01-16 23:00 and 2020-01-17 00:00, and EOS 2020-01-19 01:00:** each hourly bar is
     partial, holding only 15-30% of the hour's trades. The 1m roll-up has the whole hour:

     | bar | hourly file O/H/L/C, trades | from 1m: O/H/L/C, trades |
     |---|---|---|
     | XRP 01-16 23:00 | 0.2286/0.2295/0.2286/0.229, 225 | 0.229/0.2298/0.2281/0.229, 1,483 |
     | XRP 01-17 00:00 | 0.2291/0.2296/0.2279/0.2284, 442 | 0.2291/0.2296/0.2263/0.2275, 1,738 |
     | EOS 01-19 01:00 | 3.912/3.923/3.872/3.879, 666 | 3.835/3.944/3.829/3.858, 4,369 |

     The trade shortfall equals the whole day's gap between the hourly file and the 1m roll-up, so every other
     hour of those days is complete.
   - The XRP 1-day klines for both days are wrong as well: they close at 0.227 and 0.2284, where the 1m and 1h
     data say 0.229 and 0.2393.
   - The EOS 1-day kline matches the 1m roll-up. Patch the three bars from 1m if a test uses futures XRP or EOS
     in January 2020.
5. **Placeholder bars.** The archive keeps printing flat zero-trade bars for dead contracts. These were
   trimmed from the hourly and daily files:
   - FTTUSDT perpetual: 34,387 h after 2022-11-14 04:00, frozen at 1.59
   - MATICUSDT: 169 h after 2024-09-04 08:00
   - LUNAUSDT: 15 h after 2022-05-12 15:00
   - EOSUSDT: 1 h
6. **Stale funding rows.** Funding rows outside each contract's traded window (first bar − 1 day to last
   bar + 9 h) were dropped:
   - MATIC: 2,268 rows of a placeholder 0.01% every 8 h, 2024-09-05 .. 2026-09-30
   - FTT: 2,844 rows, 2022-11-14 16:00 .. 2025-06-19
   - EOS: 1,491 rows, 2025-05-22 .. 2026-09-30
   - pre-listing rows: ALGO 44, ADA 32, XMR 4, DOT 3, XTZ 3
   - LUNA: 1

**Sanity checks** after repair: no non-positive prices, no bar whose high or low lies inside its open-close range,
and no off-grid bars.

## 4. Gaps and outages

**How outages appear.**

- The **spot** archive leaves an outage hour out.
- The **futures** archive keeps the hour as a **zero-trade bar** (OHLC flat at the last price). In the 1m files
  the same happens minute by minute.
- Internal zero-trade bars are kept: 223 in spot and 2,524 in futures, of which 2,486 are ICP's halt. An engine
  should treat `trades == 0` as "no market": no fills, and no stop or target triggered by the flat print.

**Exchange-wide dead hours** are hours missing or zero-trade in at least half of the symbols listed at the time.
All 31 spot episodes and the one futures hour are listed in `validation/exchange_wide_gaps.csv`.

- **Confirmed by news reports [S]:**
  - **2018-02-08 01:00 .. 2018-02-09 09:00 UTC (33 h):** Binance's "system maintenance" for a replica-database
    resync. Trading was announced to resume around 04:00 UTC on 2018-02-09
    ([The Next Web](https://thenextweb.com/hardfork/2018/02/08/binance-cryptocurrency-trading-users/),
    [Cointelegraph](https://cointelegraph.com/news/binance-halts-trading-to-resolve-technical-problem)).
  - **2020-02-19 12:00-16:00:** unscheduled maintenance after a market-data-pusher fault.
  - **2023-03-24 12:00-13:00:** spot halted about 11:38 to about 13:40 UTC by a trailing-stop bug
    ([CoinDesk](https://coindesk-coindesk-prod.cdn.arcpublishing.com/business/2023/03/24/binance-temporarily-suspends-spot-trading/),
    [TechCrunch](https://techcrunch.com/2023/03/24/crypto-giant-binance-temporarily-suspends-spot-trading)).
  - **2025-08-29 06:18-06:36 UTC (futures 1m):** USD-M futures halt, reported restored at 14:36 UTC+8
    ([The Defiant](https://thedefiant.io/news/cefi/binance-restores-futures-trading-after-brief-technical-halt-c1771d37)).
- **Not verified [U]:** the futures-wide zero-trade hour 2024-10-28 20:00. The 1m data show 74 minutes,
  20:00-21:13 UTC. The remaining episodes are 1-10 h, mostly between 02:00 and 08:00 UTC in 2018-2021,
  which looks like scheduled maintenance.
- **Spot outages since 2021-09:** only 2023-03-24.

| market | start (UTC) | end (UTC) | hours | symbols dead / listed |
|---|---|---|---|---|
| spot | 2017-08-19 23:00 | 2017-08-19 23:00 | 1 | 1/2 |
| spot | 2017-09-06 16:00 | 2017-09-06 22:00 | 7 | 2/2 |
| spot | 2017-09-09 20:00 | 2017-09-09 20:00 | 1 | 1/2 |
| spot | 2018-01-04 04:00 | 2018-01-04 04:00 | 1 | 5/5 |
| spot | 2018-02-08 01:00 | 2018-02-09 09:00 | 33 | 5/5 |
| spot | 2018-06-26 02:00 | 2018-06-26 11:00 | 10 | 11/11 |
| spot | 2018-06-27 13:00 | 2018-06-27 13:00 | 1 | 11/11 |
| spot | 2018-07-04 01:00 | 2018-07-04 07:00 | 7 | 11/11 |
| spot | 2018-10-19 06:00 | 2018-10-19 08:00 | 3 | 12/12 |
| spot | 2018-11-14 02:00 | 2018-11-14 08:00 | 7 | 12/12 |
| spot | 2019-03-12 02:00 | 2019-03-12 07:00 | 6 | 13/13 |
| spot | 2019-05-15 03:00 | 2019-05-15 12:00 | 10 | 19/19 |
| spot | 2019-06-07 21:00 | 2019-06-07 21:00 | 1 | 19/19 |
| spot | 2019-08-15 02:00 | 2019-08-15 09:00 | 8 | 21/21 |
| spot | 2019-11-13 02:00 | 2019-11-13 03:00 | 2 | 23/23 |
| spot | 2019-11-25 02:00 | 2019-11-25 03:00 | 2 | 23/23 |
| spot | 2020-02-09 02:00 | 2020-02-09 02:00 | 1 | 25/25 |
| spot | 2020-02-19 12:00 | 2020-02-19 16:00 | 5 | 25/25 |
| spot | 2020-03-04 10:00 | 2020-03-04 10:00 | 1 | 25/25 |
| spot | 2020-04-25 02:00 | 2020-04-25 03:00 | 2 | 25/25 |
| spot | 2020-06-28 02:00 | 2020-06-28 04:00 | 3 | 25/25 |
| spot | 2020-11-30 06:00 | 2020-11-30 06:00 | 1 | 37/37 |
| spot | 2020-12-21 14:00 | 2020-12-21 17:00 | 4 | 37/37 |
| spot | 2020-12-25 02:00 | 2020-12-25 02:00 | 1 | 37/37 |
| spot | 2021-02-11 03:00 | 2021-02-11 04:00 | 2 | 37/37 |
| spot | 2021-03-06 02:00 | 2021-03-06 02:00 | 1 | 37/37 |
| spot | 2021-04-20 02:00 | 2021-04-20 03:00 | 2 | 37/37 |
| spot | 2021-04-25 05:00 | 2021-04-25 07:00 | 3 | 37/37 |
| spot | 2021-08-13 02:00 | 2021-08-13 05:00 | 4 | 39/39 |
| spot | 2021-09-29 07:00 | 2021-09-29 08:00 | 2 | 39/39 |
| spot | 2023-03-24 12:00 | 2023-03-24 13:00 | 2 | 39/39 |
| um | 2024-10-28 20:00 | 2024-10-28 20:00 | 1 | 38/38 |

**Symbol-specific dead runs of 12 h or more:**

| market | coin | start (UTC) | end (UTC) | hours | what it is |
|---|---|---|---|---|---|
| spot | LUNA | 2022-05-13 01:00 | 2022-05-31 05:00 | 437 missing | old LUNA delisted after its collapse (last close 0.00005); Terra 2.0 relisted under the same symbol at 8.56 |
| spot | FTT | 2022-11-15 05:00 | 2023-09-22 07:00 | 7,467 missing | no FTT spot trading after the FTX collapse until 2023-09-22 [reason U] |
| um | ICP | 2022-06-10 10:00 | 2022-09-27 01:00 | 2,486 zero-trade + 122 missing | perpetual halted [reason U]; its funding history only starts 2022-09-01 |

The other 68 symbol-specific runs total 75 hours. Most are single zero-trade hours in thin early FTT spot
trading (2019-12 to 2020-10).

**One-minute futures, all six coins:**

- No missing minutes.
- 126-128 zero-trade minutes per coin, in four outages: 2024-10-28 16:21-16:34, 2024-10-28 20:00-21:13,
  2025-01-29 01:23-01:35 and 2025-08-29 06:18-06:36 UTC, plus a few single minutes.

## 5. Consistency checks

- **Hourly spot vs the regime study's daily klines.** These are the 1-day files in
  `data/crypto_binance_regime/`. The test covers 40 coins and 100,977 days.
  - The close matches on every day.
  - High and low match on every day. The open matches on every day except FTT 2020-01-06 (the unresolved day).
  - Daily quote volume equals the sum of the hours to 1e-6 on all but 0.1-0.15% of days (sampled: BTC, BNB, LTC,
    ADA). The exceptions are outage days such as 2020-12-21 and 2021-01-21, at 0.7-3%. The largest difference on
    any coin is 5% (FTT, ICP, EGLD, UNI).
- **Hourly vs the archive's 1-day klines, both markets:** 189,076 days, with 4 mismatches (the unresolved days in
  section 3). No day has hourly bars without a 1-day kline, or the reverse; `validation/d1_match.csv` now counts
  such unpaired days.
  - The first build reported 188,990 days, because the 86 hole days had no 1-day bar (section 3, item 2).
- **1m aggregated to 1h vs the hourly futures files:** 120,672 coin-hours, with 11 differences.
  - **2024-10-28 21:00, the outage restart, on 5 coins:** the 1m files keep zero-trade minutes from 21:00 to
    21:13 at the pre-outage price. Their roll-up therefore opens (and sometimes lows) at that stale price, while
    the hourly bar opens at the first real trade. Trade counts agree.
  - **2025-01-14 13:00 on BTC, ETH and DOGE, and 15:00 on BTC; 2025-01-29 01:00 on ETH and SOL (outage):** the
    two files disagree on trade count by 6-23% and on the high or low. In every hour but BTC 15:00 the 1m files
    hold fewer trades, so the hourly bar is probably the complete one [U].
  - Prefer the hourly files for these hours.
- **Futures vs spot basis** (futures close / spot close − 1, same hour; table below): sane.
  - The median is −2.7 to −8.7 bp on 38 contracts, 0.0 on EOS and old LUNA, and +0.7 on BNB. The perpetual
    usually sits a few bp under spot while funding stays at the 0.01% floor.
  - The 1st-99th percentile range is mostly within ±50 bp.
  - Hours beyond ±1% make up 0.2% or less of all hours for the large coins. The exceptions are ICP 4.8%
    (its halt), FTT 0.94%, AXS 0.62%, LUNA 0.55% and FIL 0.53%.
  - The largest gaps fall on crash hours: 2021-05-19 13:00 on many coins, and FTX week (SOL 24% on
    2022-11-09, FTT 24% on 2022-11-10).

| coin | hours | median bp | p1 bp | p99 bp | share abs>1% | max abs bp (when) |
|---|---|---|---|---|---|---|
| AXS | 51742 | -8.7 | -66.3 | 52.2 | 0.62% | 995 (2026-01-17 13:00) |
| POL | 18324 | -7.2 | -21.4 | 9.8 | 0.00% | 56 (2024-10-28 20:00) |
| FTT | 5114 | -6.5 | -90.1 | 3.9 | 0.94% | 2370 (2022-11-10 01:00) |
| MANA | 48989 | -6.1 | -29.8 | 26.5 | 0.02% | 781 (2021-05-19 13:00) |
| ATOM | 58613 | -5.3 | -21.0 | 32.4 | 0.02% | 1821 (2021-05-19 13:00) |
| ICP | 47508 | -4.9 | -1367.3 | 1141.9 | 4.79% | 3333 (2022-06-18 20:00) |
| VET | 58450 | -4.9 | -23.4 | 34.6 | 0.05% | 1741 (2021-05-19 13:00) |
| SAND | 50163 | -4.9 | -26.3 | 44.1 | 0.12% | 642 (2021-05-19 13:00) |
| EGLD | 53350 | -4.9 | -39.3 | 40.3 | 0.12% | 755 (2020-10-24 08:00) |
| BCH | 59513 | -4.8 | -18.4 | 22.4 | 0.07% | 2591 (2021-05-19 13:00) |
| XTZ | 58641 | -4.7 | -37.0 | 34.4 | 0.06% | 1163 (2021-05-19 13:00) |
| DOT | 53902 | -4.6 | -21.8 | 27.3 | 0.02% | 256 (2021-05-19 12:00) |
| HBAR | 48941 | -4.6 | -26.6 | 29.3 | 0.01% | 837 (2021-05-19 13:00) |
| AAVE | 52582 | -4.5 | -20.2 | 34.1 | 0.02% | 327 (2021-04-18 03:00) |
| NEAR | 52605 | -4.5 | -20.7 | 34.2 | 0.02% | 594 (2021-09-07 14:00) |
| TRX | 59169 | -4.5 | -21.3 | 27.4 | 0.03% | 871 (2021-05-19 13:00) |
| NEO | 58378 | -4.5 | -26.5 | 33.3 | 0.02% | 567 (2021-05-19 13:00) |
| XMR | 35436 | -4.4 | -36.4 | 31.9 | 0.01% | 518 (2021-05-19 13:00) |
| ALGO | 55505 | -4.2 | -23.2 | 35.4 | 0.01% | 357 (2021-02-11 03:00) |
| DASH | 58689 | -4.1 | -28.4 | 28.6 | 0.11% | 1039 (2021-05-19 12:00) |
| SOL | 53350 | -4.1 | -29.4 | 28.8 | 0.19% | 2391 (2022-11-09 20:00) |
| AVAX | 53134 | -4.1 | -28.7 | 33.0 | 0.05% | 743 (2021-02-11 03:00) |
| UNI | 53254 | -4.0 | -20.5 | 26.7 | 0.03% | 1245 (2021-05-19 13:00) |
| DOGE | 54932 | -4.0 | -18.8 | 30.9 | 0.04% | 740 (2020-12-21 14:00) |
| THETA | 55986 | -4.0 | -46.0 | 38.5 | 0.07% | 1395 (2020-05-27 12:00) |
| XRP | 59385 | -3.8 | -13.9 | 27.9 | 0.05% | 669 (2020-12-11 23:00) |
| XLM | 59049 | -3.8 | -19.6 | 32.6 | 0.02% | 2721 (2021-05-19 12:00) |
| BTC | 59513 | -3.8 | -8.2 | 16.8 | 0.02% | 257 (2020-03-13 02:00) |
| ADA | 58785 | -3.7 | -16.2 | 26.8 | 0.01% | 356 (2020-02-02 02:00) |
| LTC | 59313 | -3.7 | -14.1 | 24.6 | 0.01% | 394 (2021-05-19 13:00) |
| ETH | 59513 | -3.7 | -8.4 | 21.3 | 0.02% | 252 (2023-03-24 11:00) |
| LUNA2 | 35948 | -3.6 | -46.9 | 28.2 | 0.30% | 1101 (2025-10-10 21:00) |
| ETC | 59145 | -3.5 | -20.3 | 27.0 | 0.02% | 816 (2021-05-19 13:00) |
| FIL | 52583 | -3.4 | -29.4 | 26.7 | 0.53% | 3506 (2020-10-17 02:00) |
| LINK | 59121 | -3.2 | -18.2 | 27.2 | 0.02% | 276 (2021-09-07 14:00) |
| ZEC | 58665 | -2.9 | -27.2 | 32.6 | 0.24% | 1504 (2025-04-13 06:00) |
| MATIC | 33895 | -2.9 | -21.9 | 47.8 | 0.05% | 475 (2021-02-11 03:00) |
| SHIB | 47640 | -2.7 | -24.6 | 20.5 | 0.16% | 1820 (2021-05-12 17:00) |
| EOS | 47010 | 0.0 | -31.3 | 27.6 | 0.02% | 340 (2021-05-19 13:00) |
| LUNA | 11252 | 0.0 | -37.4 | 64.2 | 0.55% | 3111 (2022-05-11 12:00) |
| BNB | 58546 | 0.7 | -24.5 | 24.7 | 0.02% | 238 (2020-03-13 04:00) |

## 6. Funding

- **Coverage ends 2026-09-30 for every live contract.** The archive publishes funding only as monthly files and
  has no daily funding files, so **2026-10-01..16 has no funding data** (16 days). If those days matter,
  approximate them from the daily `premiumIndexKlines` files or carry September's level forward [U].
- **ICP:** the funding archive starts 2022-09-01, although the contract has traded since 2021-05-11.
- **Interval.** Most contracts pay every 8 h throughout. The observed changes are:
  - SOL: 4 h on 2022-11-09, 2 h on 2022-11-10, back to 8 h on 2022-11-18 (FTX week)
  - FTT: 2 h on 2022-11-10, back to 8 h on 2022-11-14
  - XTZ: 1 h on 2025-07-20, then 4 h from 2025-07-22
  - LUNA2: 1 h on 2025-12-05, then 4 h from 2026-01-05
  - AXS: 1 h on 2026-01-17, then 4 h from 2026-01-26
  - POL: 4 h since listing

  Charge funding per event, or annualize with `interval_h`; never assume three events a day.
- **Gaps:** at most 4 events per contract appear missing (`missing_events_est`).
- **Levels:** the table gives the sum of rates per calendar year, scaled to a full year. Positive means longs pay,
  and the figures are per unit of notional, so at 3-5x leverage multiply by the leverage for the cost per unit
  of equity.
  - BTC averaged 11.7%/yr over 2020-2026: 30.7% in 2021, 5.1% in 2025, and 2.9% annualized in 2026 to
    September. That is consistent with HANDOFF 5.14's "8-12 pts/yr".
  - Funding was lowest in 2022 (often negative) and in 2025-26. Over the whole period it averaged about zero on
    BNB, 3.1% on TRX and 3.5% on SHIB. AXS averaged −28.9%, and −128% annualized in 2026 (shorts paying).

| contract | first | last | events | intervals | interval changes | est. missing | mean ann. % | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC | 2020-01-01 | 2026-09-30 | 7395 | 8 |  | 0 | 11.7 | 17.2 | 30.7 | 4.2 | 7.9 | 11.9 | 5.1 | 2.9 |
| ETH | 2020-01-01 | 2026-09-30 | 7395 | 8 |  | 0 | 13.8 | 27.5 | 37.6 | 0.8 | 8.3 | 13.0 | 4.9 | 1.9 |
| SOL | 2020-09-13 | 2026-09-30 | 6700 | 2/4/8 | 2022-11-09->4h; 2022-11-10->2h; 2022-11-18->8h | 3 | 0.2 | -12.6 | 28.6 | -38.1 | 1.3 | 13.6 | 0.4 | -1.1 |
| BNB | 2020-02-10 | 2026-09-30 | 7274 | 8 |  | 0 | -0.0 | 2.5 | 21.8 | -12.6 | -8.4 | -3.3 | -2.1 | 2.9 |
| XRP | 2020-01-06 | 2026-09-30 | 7379 | 8 |  | 0 | 14.6 | 24.6 | 48.2 | 0.0 | 8.2 | 14.2 | 3.5 | -0.3 |
| DOGE | 2020-07-10 | 2026-09-30 | 6821 | 8 |  | 0 | 12.4 | 9.4 | 38.6 | 3.5 | 10.0 | 14.0 | 4.3 | 3.0 |
| ADA | 2020-01-30 | 2026-09-30 | 7307 | 8 |  | 0 | 13.5 | 26.8 | 40.0 | -1.0 | 7.2 | 14.0 | 4.1 | 1.4 |
| AVAX | 2020-09-22 | 2026-09-30 | 6598 | 8 |  | 0 | 6.9 | -12.7 | 31.1 | -5.2 | 7.5 | 10.5 | 0.1 | 1.1 |
| LINK | 2020-01-17 | 2026-09-30 | 7346 | 8 |  | 0 | 13.8 | 11.5 | 43.1 | 6.0 | 10.2 | 13.4 | 5.2 | 4.7 |
| LTC | 2020-01-09 | 2026-09-30 | 7370 | 8 |  | 0 | 14.8 | 25.5 | 40.2 | 2.9 | 9.3 | 14.4 | 5.6 | 3.1 |
| TRX | 2020-01-15 | 2026-09-30 | 7352 | 8 |  | 0 | 3.1 | 17.0 | 28.1 | -15.8 | -3.6 | 3.4 | -0.5 | -9.5 |
| DOT | 2020-08-21 | 2026-09-30 | 6695 | 8 |  | 0 | 7.8 | 24.7 | 42.3 | -14.3 | 1.6 | 11.5 | 1.1 | -4.7 |
| BCH | 2020-01-01 | 2026-09-30 | 7395 | 8 |  | 0 | 5.2 | 22.5 | 33.8 | -6.0 | -9.0 | -1.1 | -2.6 | -3.3 |
| AAVE | 2020-10-16 | 2026-09-30 | 6527 | 8 |  | 0 | 14.3 | 21.5 | 47.8 | 4.7 | 9.7 | 11.0 | 5.3 | 2.6 |
| ALGO | 2020-06-15 | 2026-09-30 | 6895 | 8 |  | 0 | 13.7 | 30.7 | 41.8 | 5.9 | 8.2 | 11.8 | 2.0 | -0.1 |
| ATOM | 2020-02-06 | 2026-09-30 | 7285 | 8 |  | 0 | 9.6 | 31.9 | 46.5 | -4.4 | 1.3 | 8.4 | -9.0 | -9.8 |
| AXS | 2020-11-20 | 2026-09-30 | 7346 | 1/4/8 | 2026-01-17->1h; 2026-01-26->4h | 1 | -28.9 | 33.5 | 3.1 | -54.3 | -13.1 | -6.6 | -6.9 | -128.2 |
| DASH | 2020-02-04 | 2026-09-30 | 7292 | 8 |  | 0 | 9.1 | 19.0 | 35.4 | 6.1 | 10.0 | 13.9 | -14.9 | -10.0 |
| EGLD | 2020-09-13 | 2026-09-30 | 6625 | 8 |  | 0 | 12.3 | -13.4 | 40.7 | 4.5 | 9.8 | 15.0 | 5.2 | 4.0 |
| EOS | 2020-01-08 | 2025-05-21 | 5882 | 8 |  | 0 | 17.0 | 24.9 | 39.8 | 2.3 | 10.1 | 12.8 | 4.4 |  |
| ETC | 2020-01-16 | 2026-09-30 | 7349 | 8 |  | 0 | 11.0 | 25.8 | 25.5 | -8.2 | 10.2 | 14.8 | 4.3 | 3.2 |
| FIL | 2020-10-16 | 2026-09-30 | 6527 | 8 |  | 0 | 6.3 | -162.5 | 39.4 | 2.2 | 11.5 | 15.6 | 2.5 | 0.5 |
| FTT | 2022-04-14 | 2022-11-14 | 678 | 2/8 | 2022-11-10->2h; 2022-11-14->8h | 2 | -84.8 |  |  | -84.8 |  |  |  |  |
| HBAR | 2021-03-17 | 2026-09-30 | 6071 | 8 |  | 0 | 7.8 |  | 29.8 | 1.5 | 4.0 | 10.7 | 2.4 | 1.3 |
| ICP | 2022-09-01 | 2026-09-30 | 4473 | 8 |  | 0 | 5.3 |  |  | 6.9 | 10.0 | 14.0 | 2.7 | -10.1 |
| LUNA | 2021-01-28 | 2022-05-12 | 1409 | 8 |  | 0 | 22.2 |  | 39.8 | -23.1 |  |  |  |  |
| MANA | 2021-03-15 | 2026-09-30 | 6077 | 8 |  | 0 | 7.2 |  | 21.8 | -0.0 | 7.7 | 12.6 | 2.4 | 0.2 |
| MATIC | 2020-10-22 | 2024-09-04 | 4241 | 8 |  | 0 | 16.4 | 23.2 | 44.6 | -3.5 | 7.2 | 15.9 |  |  |
| NEAR | 2020-10-14 | 2026-09-30 | 6532 | 8 |  | 0 | 10.4 | 12.2 | 37.7 | -4.2 | 6.9 | 14.0 | 2.1 | 3.9 |
| NEO | 2020-02-17 | 2026-09-30 | 7253 | 8 |  | 0 | 13.3 | 18.5 | 46.2 | 1.9 | 9.8 | 10.4 | 4.3 | -1.3 |
| POL | 2024-09-13 | 2026-09-30 | 4483 | 4 |  | 1 | -1.4 |  |  |  |  | 14.8 | -0.5 | -9.1 |
| SAND | 2021-01-25 | 2026-09-30 | 6224 | 8 |  | 0 | 9.2 |  | 39.2 | -2.9 | 9.3 | 14.8 | 4.7 | -13.4 |
| SHIB | 2021-05-10 | 2026-09-30 | 5908 | 8 |  | 0 | 3.5 |  | -7.2 | 0.0 | 10.3 | 13.3 | 0.0 | -0.3 |
| THETA | 2020-05-26 | 2026-09-30 | 6955 | 8 |  | 0 | 8.2 | -32.3 | 35.1 | 4.0 | 10.4 | 14.1 | 6.6 | 1.5 |
| UNI | 2020-09-17 | 2026-09-30 | 6614 | 8 |  | 0 | 14.1 | 12.1 | 42.1 | 6.5 | 10.0 | 13.5 | 6.3 | 4.2 |
| VET | 2020-02-14 | 2026-09-30 | 7262 | 8 |  | 0 | 15.5 | 21.3 | 47.9 | 4.9 | 8.8 | 13.6 | 6.4 | 3.2 |
| XLM | 2020-01-19 | 2026-09-30 | 7339 | 8 |  | 0 | 13.9 | 27.6 | 52.3 | 1.3 | 4.2 | 11.8 | -2.3 | -0.4 |
| XMR | 2020-02-02 | 2026-09-30 | 7298 | 8 |  | 0 | 13.1 | 10.6 | 32.8 | -5.2 | 4.0 | 15.1 | 17.8 | 17.6 |
| XTZ | 2020-02-05 | 2026-09-30 | 8640 | 1/4/8 | 2025-07-20->1h; 2025-07-22->4h | 1 | 12.2 | 31.1 | 47.6 | 4.0 | 7.1 | 9.5 | -15.2 | -0.0 |
| ZEC | 2020-02-04 | 2026-09-30 | 7292 | 8 |  | 0 | 11.2 | 29.3 | 37.3 | 5.1 | 10.9 | 14.6 | -17.6 | -3.0 |
| LUNA2 | 2022-09-10 | 2026-09-30 | 5892 | 1/4/8 | 2025-12-05->1h; 2026-01-05->4h | 4 | -4.1 |  |  | -16.6 | 12.6 | 19.1 | -37.8 | -7.1 |

## 7. Listings, delistings and survivorship

- **LUNA:** spot `LUNAUSDT` holds two assets.
  - Old Terra LUNA trades 2020-08-21 .. 2022-05-13 00:00 (from about 119 at the April 2022 high down to
    0.00005).
  - Terra 2.0 trades from 2022-05-31 06:00.
  - Never chain returns across the 2022-05-13 → 2022-05-31 gap. The old LUNA perpetual ends 2022-05-12 15:00;
    the LUNA2 perpetual starts 2022-09-10.
- **FTT:**
  - Spot trades 2019-12-20 .. 2022-11-15 04:00, then resumes 2023-09-22 08:00 and runs to now.
  - The perpetual traded 2022-04-15 .. 2022-11-14 04:00 only (5,114 h).
  - The bounce study treated the two spot pieces as separate series; do the same here.
- **MATIC → POL:**
  - Spot MATIC ends 2024-09-10 02:00 and POL starts 2024-09-13.
  - The futures MATIC contract ends 2024-09-04 08:00 and POL starts 2024-09-13, a 9-day gap with no
    perpetual.
  - The migration was 1:1 [S] (comment in `regime_switch.load_binance`).
- **EOS:** spot ends 2025-05-26 02:00 and the perpetual ends 2025-05-21 08:00. Binance moved EOS to its rebrand
  "A" (Vaulta) [U]. "A" was not fetched.
- **XMR:** spot was delisted on 2024-02-20 (last bar 02:00). The perpetual keeps trading to now.
- **Spot listings** start between 2017-08 (BTC, ETH) and 2021-05 (ICP, SHIB). Notable cases:
  - BCH spot starts only 2019-11-28. Earlier BCH traded as BCHABC/BCC, which was not fetched.
  - POL starts 2024-09.
- **Futures history** in the archive starts 2020-01-01 at the earliest. The BTCUSDT perpetual launched in
  2019-09 [U], but the archive has no 2019 futures data.
- **Survivorship:**
  - The 40 were chosen in 2026 as "large pairs". The list includes broken or delisted names (LUNA, FTT, EOS,
    XMR spot, MATIC), but not the many other 2018-2021 top-40 coins that later collapsed or left Binance
    (e.g. BSV, XEM, IOTA, WAVES, OMG, ZIL, SRM, CEL [U]).
  - Binance lists a coin only after it is established, so each series starts after its earliest run-up.
  - Any test that picks "a few liquid coins" (rule 5) by today's size is survivor-biased. A point-in-time choice
    by trailing `quote_volume` is possible from these files.
- **The two LUNA spot assets, the two FTT spot pieces, and the dead or halted futures windows** (FTT after
  2022-11-14, ICP 2022-06..09) are the places where a naive series would hold a frozen or fake price.

## 8. Descriptive facts (buy and hold, spot closes, before costs; no strategy)

The source post gives no dates for its 16 months [U]. These are two reference windows:

- 2024-07-01 .. 2026-10-16, the span of the 1m data
- 2025-06-16 .. 2026-10-16, the latest 16 months

Volatility and maximum drawdown are measured over 2024-07-01 .. 2026-10-16. "n/a" means the coin was not listed
over the whole window. Returns run from the first hourly spot close at or after the window start (the 00:00 UTC
bar's close) to the 2026-10-16 23:00 close. Rounded to whole percent, the section 12 check reproduces every entry
this way.

| coin | B&H 2024-07-01..2026-10-16 | B&H 2025-06-16..2026-10-16 (16 mo) | ann. vol (1h log returns, 2024-07..) | max drawdown 2024-07.. |
|---|---|---|---|---|
| BTC | +30% | -23% | 46% | -54% |
| ETH | -30% | -5% | 66% | -69% |
| SOL | -29% | -31% | 78% | -79% |
| BNB | +24% | +11% | 53% | -60% |
| XRP | +176% | -39% | 84% | -73% |
| DOGE | -35% | -54% | 89% | -86% |
| ADA | -43% | -64% | 93% | -89% |
| AVAX | -66% | -48% | 86% | -89% |
| LINK | -14% | -7% | 87% | -77% |
| LTC | -21% | -31% | 78% | -73% |
| TRX | +169% | +23% | 44% | -53% |
| DOT | -81% | -69% | 87% | -94% |
| BCH | -30% | -40% | 78% | -73% |
| AAVE | +60% | -43% | 97% | -85% |
| ALGO | -20% | -34% | 98% | -87% |
| ATOM | -74% | -57% | 82% | -89% |
| AXS | -82% | -54% | 102% | -92% |
| DASH | +98% | +145% | 117% | -80% |
| EGLD | -87% | -73% | 93% | -96% |
| EOS | n/a | n/a | n/a | n/a |
| ETC | -66% | -52% | 78% | -85% |
| FIL | -74% | -52% | 99% | -93% |
| FTT | -82% | -72% | 136% | -95% |
| HBAR | +9% | -46% | 99% | -84% |
| ICP | -63% | -45% | 102% | -87% |
| LUNA | -89% | -71% | 111% | -95% |
| MANA | -74% | -66% | 94% | -93% |
| MATIC | n/a | n/a | n/a | n/a |
| NEAR | -5% | +127% | 104% | -88% |
| NEO | -80% | -58% | 89% | -94% |
| POL | n/a | -52% | 87% | -91% |
| SAND | -84% | -79% | 100% | -97% |
| SHIB | -70% | -57% | 84% | -88% |
| THETA | -87% | -71% | 100% | -96% |
| UNI | -22% | +3% | 101% | -88% |
| VET | -74% | -69% | 92% | -95% |
| XLM | +100% | -30% | 94% | -77% |
| XMR | n/a | n/a | n/a | n/a |
| XTZ | -60% | -43% | 88% | -90% |
| ZEC | +5439% | +2545% | 130% | -73% |

Over the latest 16 months, buy and hold of BTC returned −23%. Most other coins lost 30-80%. The exceptions were
ZEC (+2,545%), DASH (+145%), NEAR (+127%), TRX (+23%) and BNB (+11%). In both windows, the post's "4.3x on
starting capital" (+330%) is far above buy and hold on every coin except ZEC.

## 9. Notes for test design

- **Bar timing.** `open_time` is the bar's open. An hourly bar is complete at `open_time + 1h`, so act on closed
  bars only.
- **US-open timing rules (12-15).**
  - The NYSE opens at 09:30 New York time. That is **13:30 UTC during US daylight time** (second Sunday of March
    to first Sunday of November) and **14:30 UTC otherwise**.
  - Hourly bars straddle the open: in summer the 13:00 bar holds the first 30 minutes of the session.
  - "30 minutes after the open" is the 14:00 UTC bar open in summer and 15:00 in winter. "3.5 hours before" is
    10:00 or 11:00 UTC. "90 minutes before the open" is 12:00-13:30 UTC in summer.
  - For exact timing, use the 1m files (six coins).
  - US market holidays have no open.
  - Rule 12 ("not Friday or Saturday") does not say which time zone [U]. The New York and UTC dates differ from
    00:00 to 04:00 UTC (05:00 in US winter).
- **Vehicle.** Leverage (rule 4) means perpetuals: `h1_um` plus `funding`, history from 2020 or later.
  - Spot has longer history (from 2017) for unlevered variants.
  - The futures-spot basis is a few bp, so spot prices are a fair proxy for the signal, though not for funding.
- **Grid overlay.** The 1m futures files cover 2024-07-01 .. 2026-10-16 for six coins. Zero-trade minutes
  (section 4) must not produce fills.
- **Missing data.** Do not forward-fill through the LUNA, FTT or ICP gaps. Treat them as series breaks.

## 10. US stocks and ETFs: what the repo already has

Nothing was downloaded for stocks. Everything below is gitignored and already on disk; checked 2026-10-18.

### Daily OHLC sources

| source | contents | coverage | adjustment | loader |
|---|---|---|---|---|
| `data/raw_pit/prices.parquet` (Johnbrick123 release) | 1,223 tickers: every S&P 500 member since 1996 (1,227 in `membership_intervals.parquet`), including 432 that stopped trading before 2026-10, plus about 140 ETFs | 1970-01-02 to 2026-10-12. Mixed sources: yahoo 73% of rows, tiingo, crsp, wiki, kaggle and patches | raw OHLC (split-adjusted, not dividend-adjusted) plus `adj_close`, `dividends`, `stock_splits`, `volume`. CRSP-sourced rows can be close-only | `regime_switch._yahoo_raw(sym)` (ETFs, TSLA, COIN, HOOD), `ma_bounce` dividend factors |
| `data/universe_pit_all/` | the same 1,222 tickers as one CSV each (`date, open, high, low, close`), plus `members.csv` (point-in-time S&P 500 spells: 1,261 rows, 1,227 symbols). Dead or renamed companies carry a `-YYYYMM` suffix (327 files, e.g. `AAMRQ-201312.csv`) | 1995-01-03 to 2026-10-12 | **scaled to total return** (dividends folded into OHLC); no volume | `regime_switch.load_pit_universe()`, `ma_bounce.load_members()`, `screener.data.from_csv_folder()`; built by `screener.data.from_sp500_pit()` |
| `data/universe_recent_raw/prices.parquet` (q100423gg-coder release) | 2,323 US stocks and ETFs; 298 are ETFs by the Nasdaq/NYSE directory flag (SPY, QQQ, IWM, sector SPDRs, TLT, GLD, leveraged SSO/UPRO/TQQQ/SOXL, spot bitcoin/ether ETFs IBIT/FBTC/ETHA/GBTC, etc.) | 2024-08-05 to 2026-10-14 (551 sessions) | split-adjusted OHLC, `adj` (dividend-adjusted close), volume | `screener.data.from_long_parquet()`, `scalp_crypto.SPY_PRICES`, `scalp_us_daily` (liquid names) |
| `data/scalping/qlib/panel.parquet` (qlib US 1d v3) | 13,195 tickers incl. ETFs | 1999-12-31 to 2024-04-25; effectively a Nov-2020 universe snapshot (survivor-biased) | float32 OHLCV and qlib `factor` | `scalp_us_daily` (`pd.read_parquet(... columns=, filters=)`), `screener.data.from_qlib()` on the raw zip |
| `data/scalping/rh/daily_split.parquet`, `daily_none.parquet` (Robinhood MCP pulls) | 3,485 low-volume US common stocks (no ETFs, none of SPY/QQQ/etc.) | 2023-07-03 to 2026-10-16 | split-adjusted and unadjusted versions | `scalp_us_daily._rh_daily()` |
| `data/tv_stocks/` (TradingView exports) | SPX, NDX, IWM, COIN, TSLA, HOOD, CRCL, `_1D` and `_1W` | daily from 2010-07 (TradingView cap), weekly SPX from 1967; last row 2026-08-24 (still forming) | **close only** plus the indicator's trend lines and ATR(14); no highs or lows | `run_stocks.load(sym, tf)` |
| repo root `SPY/QQQ/IWM_historical_data.csv` | yfinance OHLCV | SPY 1999-01-04, QQQ 1999-03-10, IWM 2000-05-26, all to 2025-12-26 | dividend-adjusted OHLC (two header rows to skip) | `replicate.py` |
| `data/macro/` | `gspc_1950_2018.csv` S&P 500 daily OHLC 1950-01-03..2018-12-21 (real highs/lows from 1962); `us_market_data.csv` S&P price, total return and 3-month T-bill 1885-03-20..2025-12-19; `shiller.csv` monthly 1871..2026-09; FRED UNRATE, VIXCLS (1990-01-02..2026-10-12), T10Y2Y, PAYEMS; `french.csv.bz2` monthly French factors and portfolios 1949..2017 | see left | index levels | `regime_switch.load_spx_long()` (splices SPY after 2018), `regime_switch.rf_annual_pct()` |

ETF lists already defined in code:

- `regime_switch.ETFS` (14): SPY QQQ IWM DIA EFA EEM TLT IEF TIP LQD HYG GLD SLV VNQ (all in `raw_pit`; SPY from 1995, QQQ 1999, IWM 2000, GLD 2004, HYG 2007).
- `flip_delay.ETF13`: the same minus DIA. `trend_portfolio.UNIV_A` (12) and `UNIV_B` (adds qlib DBC USO DBA UUP FXE FXY FXA FXF; `data/etf/` is not on disk now, rebuild per HANDOFF section 3).
- `scalp_us_daily.FUNDS_E` (24): SPY QQQ IWM MDY DIA EFA EEM AGG TLT IEF LQD HYG GLD SLV USO plus the nine sector SPDRs XLB..XLY.
- `fetch_freedom_data.ETFS`: iShares single-country ETFs (monthly bars only).
- ETF flags for any symbol: `data/scalping/ref/nasdaq-listed-symbols.csv` and `other-listed.csv` (`ETF` column; current snapshot, so recycled tickers such as FB, UN and NFX are flagged as today's ETFs).

### Intraday stock data

There is **no hourly stock or ETF data** in the repo, and none for SPY, QQQ or any large name. The only intraday US bars are the Robinhood pulls from the scalping study, all for **low-volume** stocks:

| file | bars | names | window (UTC) |
|---|---|---|---|
| `data/scalping/rh/m5_none.parquet` | 5-minute, regular session, unadjusted | 120 (Part C panel) | 2026-03-02 14:30 .. 2026-10-16 19:55 |
| `data/scalping/rh/m1_none.parquet` | 1-minute | the same 120 | 2026-09-08 13:30 .. 2026-10-16 19:59 |
| `data/scalping/rh/s15_none.parquet` | 15-second | 40 | 2026-10-12 .. 2026-10-16 |
| `data/scalping/rh/events_m5_none.parquet` | 5-minute, event days | 843 | 2026-03-02 .. 2026-10-16 |

These could be summed to hourly bars, but they cover illiquid names over seven months, not the liquid stocks or ETFs a breakout trader would use. Getting hourly stock data would need a new pull: the Robinhood connector's `get_equity_historicals` offers hourly and 5-minute intervals over limited look-back spans, with intraday retention rolling (HANDOFF 5.21: 5-minute about 7.5 months) [U on the exact hourly span]. Yahoo, Alpha Vantage and similar hosts are blocked here (HANDOFF section 10).

**Consequence for the replication:** the strategy's rules are stated for "a few liquid coins" (rule 5) traded with leverage, so crypto is the primary test bed. Stocks and ETFs can only be tested on **daily** bars (Bollinger breakout near highs, midline exit, holding at least 3 days), not on the intraday timing rules 12-15. Rules 13-14 are pinned to the US stock open (13:30 UTC in US summer time, 14:30 UTC in winter), so they apply to crypto bars too, and the 1-minute futures files allow minute-level timing for six coins.

## 11. Blockers and open items

- **No October 2026 funding:** the archive has monthly funding files only (section 6).
- **No hourly stock or ETF data:** stocks can be tested on daily bars only (section 10).
- **Four day-level inconsistencies remain** in the archive (section 3), all in 2020. They are immaterial for
  tests that start later. The three futures ones are single partial hourly bars that the 1m archive could patch.
- **Outage causes** other than the four tagged [S] are unverified.

## 12. Independent check (2026-10-18)

A second agent re-validated the build with its own scripts. These did not import the fetcher or its S3 helpers:
they downloaded directly, computed their own sha256 and parsed the CSVs themselves. All results are [A].

- **Raw zips vs parquet:** 117 zips with their sha256 checked: 20 monthly or daily kline zips, the 86 daily 1d zips
  of the hole days, 2 daily 1m zips and 9 funding zips. They span spot and futures; 1h, 1d and 1m; 2017-2026; and
  the special cases:
  - spot timestamps in microseconds (2025)
  - the Feb-2018 off-grid bars
  - the AXS repairs, the SOL holes, the ICP halt and the FTT placeholders
  - the 1000SHIB rescale
  - the SOL, XTZ and AXS funding-interval changes and the MATIC, ADA and ALGO stale rows
  - the October daily zips

  Every sha256 matched. Every bar and funding row matches the archive exactly, except the documented repairs,
  fills, trims and stale-row drops.
  - The Feb-2018 replacement hours equal the 1m roll-up.
  - Rounding the float32 1m prices to the tick gives back the archive prices exactly.
- **Recomputed from scratch, all equal to this note:** the totals in section 1; the missing and zero-trade hours
  per series (`listing.csv`); the 31 + 1 exchange-wide episodes; the 11 1m-vs-1h hours; the 100,977-day regime
  match; and the buy-and-hold table.
  - No duplicates, unsorted rows or off-grid bars.
  - No non-positive prices or high/low violations.
  - No leading or trailing zero-trade bars.
  - Every zero-trade bar is flat with zero volume.
  - The one duplicate the first build dropped (spot AXS 1d 2026-02-10) is an exact copy inside the archive's
    monthly zip.
- **Partial re-run of the fetcher** into a scratch folder (ICP, AXS and SHIB hourly, daily and funding; SOL 1m
  for 2026-09..10-16) reproduced every file byte for byte. The one exception was `d1_um/ICPUSDT`, which gained
  its 21 missing days.
- **Fixes made in `fetch_bb_data.py`:**
  - 1d holes are filled (section 3, item 2).
  - Checksum verification is strict and counted honestly (section 3).
  - Daily zips are also fetched for a month whose monthly zip is not published yet. Before, a later `--end` early
    in a month would silently drop the previous month.
  - The de-duplication sort is stable.
  - `validate` reports unpaired hourly/daily days.
  - A new `--market spot|um` option rebuilds one market.

