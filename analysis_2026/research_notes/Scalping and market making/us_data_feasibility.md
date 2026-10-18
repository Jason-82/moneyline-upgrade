# US Data for Testing Scalping and Liquidity Provision in Low-Volume Stocks: What We Can Get, Plus a 40-Stock Pilot (Oct 2026)

> **How this was verified.**
> - **Robinhood MCP:** every tool behaviour below was tested live on Sat 2026-10-17, 20:08–20:40 EDT (2026-10-18 00:08–00:40 UTC). Only read-only market-data tools were called; no account, order, scan-saving or watchlist tool was touched. Tool descriptions quoted below come from the tools' own schema text as loaded this session.
> - **Market was closed** (weekend). Every quote was stale: the last regular session was Fri 2026-10-16. Repeated snapshots were therefore identical, and no Level-2 book could be read.
> - **Public data hosts** were curl-tested from this sandbox (`curl -m 15`). Papers were checked only through search-engine retrieval of abstracts and repository listings. No paper's full text was read.
> - **Tags:**
>   - **[A]**: checked against the primary source's own text as retrieved this session (tool schema text, abstract, RePEc or repository listing, or the host's own README).
>   - **[S]**: secondary source only.
>   - **[U]**: from memory, unverified or conflicting. Treat as a lead.
>   - **[M]**: measured in this session by our own calls and scripts (pilot data under `data/scalping/`).
> - **No personal data.** Only public market data for public tickers was saved. No account, position or order information was read.

Fact-check (date 2026-10-17): 230 claims checked, 22 corrections (18 substantive, 4 clarifications). (Reran the pilot scripts on a scratch copy of the data and every table reproduced; re-probed IEX/qlib/hosts with curl; made 7 read-only Robinhood calls; compared the EDGE code with bidask 2.1.0 from PyPI. Web search was exhausted and RePEc/FHNW were unreachable, so the paper-abstract tags are downgraded.)

---

## Bottom line

1. **Robinhood alone cannot test historical scalping.**
   - It has **no historical quotes at all**. It gives current quotes only: bid/ask price without size from `get_equity_quotes`, and closing bid/ask with size from the scanner.
   - Intraday bars go back only so far: 15-second bars under ~2 weeks, 1-minute ~6 weeks, 5-minute ~7.5 months, hourly ~10 months. Daily bars go back to 1999-09 and arrive in ≤5,000-bar chunks.
   - Delisted names are mostly missing.
   - Intraday bars carry only 32–58% of the daily-bar volume. [M]
2. **Daily-bar spread estimators give only a rough cost in low-volume names.** Compared with the Friday closing quoted spread across 38 pilot stocks:
   - EDGE did best (Spearman 0.57, median ratio 1.4×, typical error a factor of ~1.7).
   - Corwin–Schultz (0.45) and two-day Abdi–Ranaldo (0.50) followed.
   - The window Abdi–Ranaldo (0.19) and Roll (−0.10) are useless here.
   - A three-variable model (ADV, price, volatility) ranked stocks better than EDGE out of sample (LOO Spearman 0.73 vs 0.57), with a similar level error (median abs log error 0.59 vs 0.53).
   - **EDGE on 5-minute bars** came within 10% of the closing quoted spread for 3 of 6 test names. The other 3 came in at 0.44–0.58×, below the quoted spread, as an effective spread should when trades print inside the quote. [M]
3. **The best free tick data that is reachable is IEX HIST.** It holds IEX's own top-of-book quotes and trades, tick by tick, from 2016-12 (TOPS 1.5 from 2016-12-12; TOPS 1.6 from 2017-09-06; DEEP from 2017-05-15) to the previous trading day, at 0.5–15 GB per day on Google Cloud Storage.
   - It covers the IEX venue only, and in low-volume names it is nearly empty.
   - A full-day pilot (2026-10-16, 40 names): IEX printed a median 2.7% of volume (0.2% in $50–150k names), and its quote was usually a 100-share placeholder ~30% wide.
   - It matched the NBBO at the close in only 5 of 40 names (section 4.4). [M]
4. **No survivorship-free broad daily panel is reachable.**
   - qlib's US set (13,354 symbols, 2000 to 2024-04) is effectively a November-2020 snapshot. Names that died before then are missing, and 2,303 names freeze at 2020-11-10, so SIVB, FRC and BBBY have no collapse.
   - CRSP, Norgate and Sharadar are paid. Polygon, Kaggle, Hugging Face, Stooq, Nasdaq and NYSE sample servers are blocked here. [M]
5. **Capacity in this universe is tiny.** Median displayed inside depth at the close:
   - about $1,000 per side in $50–150k-ADV names, with a median quoted spread of 197 bp;
   - about $8,000 per side in $1.5–5M-ADV names (21 bp), across 1,167 stocks. [M]
   - Caveats from the fact-check: the scanner quote seems to include odd lots (section 1.2), and the 1,167 have no names priced below $2.58 or at $8.17–11.09 (section 2.1). So these medians are not universe-wide; the missing sub-$2.58 names probably have the widest spreads.
6. **Recommended design** (section 5):
   - a daily-horizon reversal and liquidity test on Robinhood daily bars, with costs from 5-minute EDGE plus the ADV model, stress-tested at 1–2× cost;
   - an IEX-HIST intraday fill study only for the more active (~$2–5M ADV) names, for a sample of days;
   - forward collection of the scanner's closing NBBO and sizes every trading day to build our own point-in-time quote history.

---

## 1. Robinhood MCP read-only tools: what they actually return

### 1.1 `get_equity_historicals` (bars)

| Item | Finding | Tag |
|---|---|---|
| Intervals | 15second, 30second, minute, 5minute, 10minute, 30minute, hour, 4hour; day, week, month, 3month … 50year. The server does not aggregate; finer bars must be aggregated client-side. | [A] tool text |
| Symbols per call | Up to 10. | [A] tool text |
| Bar cap | Explicit-interval requests are rejected above **5,000 estimated bars per symbol**. The estimate counts weekdays: 1990→2026 daily gave "estimated 9601 bars exceeds cap of 5000". Full daily history therefore takes 2 calls per symbol. | [A] error text, [M] |
| Response size limit | 2 symbols × 4,768 daily bars (1.6 MB) worked. **10 × ~4,768 (~8 MB) closed the MCP connection** ("message too large"). 10 × 827 bars (1.39 MB) worked. About **170 bytes per bar per symbol**. Large results are saved to a tool-results file, not to context. | [M] |
| Daily history start | Real daily/monthly bars from **1999-09** (NL; AAPL and IBM also start 1999-09 when re-checked); earlier bars are interpolated. Pre-2003 monthly bars look implausibly thin (NL 1999-10: volume 23,370 shares, high−low ≈ 1.0%). Treat pre-2003 as suspect. | [M] |
| Intraday retention (AAPL, as of 2026-10-17) | 15-second: data on 10-16, none on 10-05. 1-minute: data on 09-08, none on 09-01 (~6 weeks). 5-minute: data on 03-02, none on 02-17 (~7.5 months, ~160 sessions). Hourly: data on 2026-01-05, none on 2025-12-01 (~10 months). | [M] |
| Interpolated bars | `interpolated=true` marks gap-fill. Pre-listing daily bars are back-filled flat at the first real price (AGCC: 579 of 827 bars; AMRO: 825 of 827). **Intraday requests outside retention return flat bars at the latest price** (AAPL "343.41" on 2025-07-01). These must be dropped. They carry `interpolated=true` (re-checked on AAPL 5-min, 2026-02-17), so the gap-fill filter removes them. | [A] tool text, [M] |
| Zero-volume real bars | These are not flagged as interpolated: DUKR has 125 and NXTT 152 of 827 days (halts or no trades). | [M] |
| Sparse intraday trading | Share of 5-min RTH bars with at least one trade, over 59 sessions: FSI ($59k ADV) 12%, SCOR ($137k) 24%, ALTI ($344k) 53%, MED ($740k) 60%, CRON ($2.4M) 98%, EGY ($5.0M) 99%. | [M] |
| **Intraday volume is incomplete** | Summed 5-min RTH volume is only **32–58% of the same day's daily-bar volume** (median daily ratio over 59 sessions: EGY 0.32, MED 0.38, ALTI 0.41, FSI 0.46, SCOR 0.48, CRON 0.58). The 24_5 hourly bars for EGY on 10-16 sum to the same ~0.39M shares, against 1.31M on the daily bar. The daily bar agrees with fundamentals' 30-day average volume. The intraday series probably omits off-exchange/TRF prints and/or auction prints [U]. **Use daily bars for ADV and capacity**; intraday highs and lows see only part of the tape. | [M] |
| Bounds | `regular` (default), `extended`, `trading`, `24_5`, `24_7`, `hyper_trading`. With `24_5`, bars carry `session` = overnight / pre / reg / post. Hourly bars are clock-aligned. The 13:00 UTC bar is labelled "pre", yet its volume (EGY 10-16: 14,749) equals exactly the 9:30–10:00 regular-session 5-min bars, so the session labels are bar-start labels. | [A] tool text, [M] |
| Adjustment | `split` (default), `none`, `all` (split + dividend; the tool text says "intraday only"). | [A] tool text |
| Delisted names | SIVB, FRC, BBBY, WISH, SIVBQ and BBBYQ are **not found**. SBNY (flat at $70 after 2023-03-13) and FRCB (FRC's OTC successor ticker) are found. Coverage depends on the ticker, and there is no delisting list, so the data is survivorship-biased. | [M] |

### 1.2 Quotes, book, fundamentals, scanner

| Tool | What it returns | Limits observed | Tag |
|---|---|---|---|
| `get_equity_quotes` | last_trade_price + venue time; last_non_reg_trade_price + time (extended hours); bid_price, ask_price + venue times; previous_close; state; has_traded. Pairs each quote with the official close. **No bid/ask sizes.** | Official closes only for ≤ 20 symbols per call; 40 symbols returned quotes with `closes_error`. On the weekend, bid and ask were the 8 pm ET end-of-after-hours quotes (venue time 2026-10-17T00:00Z): **median spread 2,974 bp, 30× the regular-session close.** Unusable outside RTH. Oddity: `close.date` and `previous_close_date` said 2026-10-15 on Saturday. | [A] tool text, [M] |
| `get_equity_price_book` | "Level 2 snapshot … ladder of price levels and resting share size", up to 4 symbols per call. | On the weekend **both sides were empty for every symbol, including AAPL and SPY**. Number of levels and depth are **untested**; re-test during RTH. | [A] tool text, [M] |
| `get_equity_fundamentals` | Market cap, float, shares outstanding, avg volume (2-week, 30-day), 52-week range, today's OHLCV, dividends, sector. No quotes. | 10 symbols per call. | [M] |
| `get_scanner_filter_specs` / `get_scanner_datapoints` | Enum filters include asset type, close/last/open, bid price, ask price, **average volume** (lengths 1–90), relative volume, volume, **market cap, float, shares outstanding**, sector and technicals. Expressions add **`turnoverAvg(...)` (dollar volume)**, `dayTurnover`, `quote.bidPrice/askPrice/bidSize/askSize/spread/time`, `officialPlaceOfListing` (MIC), `tradingStatus`, halt times and `symbol` (ANY_OF tickers, or IN_LIST index codes incl. Russell2000, RussellMicrocap, SP600). | Spread and dollar-volume filtering work via expressions. | [A] tool text, [M] |
| `preview_scan` | Runs filters live "WITHOUT saving a scan. Nothing is persisted and no scan_id is returned." | **At most 200 rows per call, sorted by Last (descending)**, so the universe must be cut into price slices. `total_items` is not additive (price $1–5.45 gave 387, $1–3.64 gave 390), so it cannot count a universe. About 100 KB per 200 rows with 8 extra columns. **Scanner quote fields give the last regular-session quote with sizes** (quote.time 2026-10-16 19:59:59 UTC). This is presumably the consolidated NBBO from the dxFeed composite [U]. **Fact-check:** across the 1,167 candidates, 20% of bid sizes and 22% of ask sizes are under 100 shares (DUKR: 1 × 10 shares). A round-lot protected NBBO cannot show that for stocks under $250, so the field probably includes odd-lot quotes [M; round-lot rule from memory, U]. Its spread can therefore be narrower than the protected NBBO, and the size at that price can be a few shares. It is the only source of sizes. | [A] tool text, [M] |
| `get_equity_tradability` | Needs an account number. | **Not called** (safety rule). | [A] tool text |

---

## 2. Pilot: 40 low-volume US common stocks

### 2.1 How the pilot was drawn [M]
- **Screen:** `preview_scan` with asset type STOCK, close > $1, `turnoverAvg(30d, regular)` between $50k and $5M, listing in XNAS/XNYS/XASE (OTC, Arca and Cboe excluded). It ran in 7 price slices.
- **Candidates:**
  - 1,395 unique rows.
  - 226 removed by a name filter (funds, ETNs, SPACs, units, preferreds, notes) plus 2 by hand (FT, a closed-end fund; CQP, an MLP).
  - **Fact-check:** the filter's regex has no word boundaries. "unit" matches Community, United and Unity, and "income" matches Alpine Income. So it also dropped **~25 operating common stocks**, mostly community banks (CTBI, FCBC, UNTY, UBCP, CZWI and others) plus USLM, UTL, MANU, CYH, CHCT and PINE. It also dropped 6 ADRs ("Depositary"), while the ADR RML was kept. Fix the regex before any forward collection.
  - That left **1,167 candidates with a valid two-sided closing quote**.
- **Sample:** 10 names per ADV bucket ($50–150k, $150–500k, $0.5–1.5M, $1.5–5M), evenly spaced by ADV.
- **Selection bias:** each slice returned only its 200 highest-priced names, so candidates lean toward the upper end of each price slice. Universe-wide shares below are approximate.
  - **Fact-check:** all 7 slices hit the 200-row cap (`total_items` 346–481 each). The candidate set therefore has **no name with Last below $2.58** (despite the > $1 screen) and **none between $8.17 and $11.09**. The cheapest names, probably the widest in bp, are missing entirely. [M]
- **Not cleaned out:** a few recent listings (AMRO with 2 real bars, RML with 31, ATTO with 52) and one long-halted name (NXTT). AMRO and RML are excluded from the estimator statistics.
- **ADV definition caveat:** the scanner's `turnoverAvg(…, session="regular")` runs **below** consolidated ADV from daily bars. Daily-bar ADV over the last 60 days is a median **1.47×** the scanner's 60-day value (IQR 1.31–1.71); for BY it is 2.3× (2.5× on 30-day windows, where the median is 1.58×). The cause is unknown [U]. The "$50k–5M" screen therefore corresponds to roughly $75k–7M of consolidated ADV, and ADV figures below are scanner values unless stated. [M]
- **Universe size:** the number of US-listed common stocks with $50k–5M ADV and price > $1 is roughly **1,500–2,000**. This is an inference from slice counts that are not additive. [M/U] Every slice was truncated (see above), so 1,395 is a floor. Taken at face value, the slices' `total_items` sum to ~2,700 rows, about 2,250 after the name filter, so 1,500–2,000 may be low. [M/U]

### 2.2 Quoted spreads and depth at the Friday close, all 1,167 candidates [M]

Last regular-session quote from the scanner (quote times 15:55:08–15:59:59 ET on 2026-10-16; presumed NBBO, called "closing NBBO" below, but it probably includes odd lots: section 1.2). The candidate set excludes sub-$2.58 and $8.17–11.09 names (section 2.1). Inside depth = mean of bid $ size and ask $ size.

| ADV bucket | n | median price | quoted spread p25 / median / p75 (bp) | median inside depth per side |
|---|---|---|---|---|
| $50–150k | 127 | $4.6 | 119 / **197** / 360 | **$974** |
| $150–500k | 224 | $6.0 | 44 / **97** / 197 | $1,465 |
| $0.5–1.5M | 300 | $11.9 | 24 / **38** / 86 | $3,056 |
| $1.5–5M | 516 | $16.7 | 13 / **21** / 35 | $8,152 |

- Spearman correlation of quoted spread with ADV is −0.64; with price, −0.39.
- 26% of these names quote wider than 100 bp at the close.
- 20% are at a one-cent spread.
- **Caveat:** these are single closing snapshots. Spreads are usually widest near the open, so all-day averages are likely wider. [U]

### 2.3 Pilot table (public market data only) [M]

Columns:
- **price:** the scanner's `Last` field as read on Saturday. For 19 of 40 names it differs from the official 2026-10-16 close (daily bar), by up to ~10% (MBAI 3.04 vs 2.75, UCAR 3.19 vs 3.385). The spreads use the bid/ask mid and are unaffected.
- **ADV30:** scanner `turnoverAvg` over 30 days.
- **quoted:** closing NBBO spread.
- **days used:** real bars (volume > 0, not interpolated) among the last 60.
- **CS:** Corwin–Schultz with overnight adjustment; negative two-day estimates set to 0, then averaged.
- **AR 2-day:** mean of two-day Abdi–Ranaldo estimates, negatives set to 0.
- **AR window:** √max(4·mean product, 0).
- **EDGE:** Ardia–Guidotti–Kroencke (2024).
- **Roll:** 2√(−cov) on log closes; 0 when the covariance is positive.

| ticker | ADV bucket | price $ | ADV30 $k | days used | quoted bp (close) | inside depth $ | CS bp | AR bp (2-day) | AR bp (window) | EDGE bp | Roll bp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DUKR | 50-150k | 4.46 | 51 | 60 | 522 | 25 | 287 | 196 | 304 | 389 | 0 |
| FSI | 50-150k | 6.05 | 59 | 60 | 66 | 3,610 | 89 | 123 | 154 | 203 | 137 |
| WAVE | 50-150k | 5.30 | 70 | 60 | 170 | 102 | 258 | 238 | 315 | 292 | 393 |
| MBAI | 50-150k | 3.04 | 85 | 60 | 147 | 273 | 167 | 234 | 0 | 166 | 0 |
| NL | 50-150k | 6.63 | 93 | 60 | 75 | 3,332 | 101 | 132 | 164 | 101 | 181 |
| UCAR | 50-150k | 3.19 | 98 | 60 | 363 | 372 | 236 | 376 | 290 | 317 | 0 |
| SHPH | 50-150k | 5.18 | 110 | 60 | 407 | 974 | 223 | 293 | 139 | 80 | 590 |
| AGCC | 50-150k | 15.64 | 123 | 60 | 439 | 1,868 | 135 | 202 | 236 | 271 | 307 |
| SCOR | 50-150k | 3.42 | 137 | 60 | 263 | 566 | 245 | 249 | 232 | 228 | 380 |
| NXTT | 50-150k | 5.19 | 149 | 60 | 416 | 273 | 263 | 274 | 0 | 733 | 0 |
| AIIR | 150-500k | 7.48 | 150 | 60 | 304 | 395 | 277 | 303 | 400 | 692 | 511 |
| VABK | 150-500k | 50.89 | 170 | 60 | 366 | 4,312 | 49 | 75 | 71 | 110 | 64 |
| FATN | 150-500k | 5.00 | 206 | 60 | 120 | 298 | 218 | 228 | 33 | 249 | 0 |
| HLP | 150-500k | 2.97 | 230 | 60 | 199 | 569 | 210 | 224 | 93 | 222 | 0 |
| GHI | 150-500k | 4.97 | 271 | 60 | 81 | 496 | 78 | 83 | 0 | 100 | 0 |
| STHO | 150-500k | 7.70 | 304 | 60 | 196 | 435 | 83 | 108 | 109 | 136 | 0 |
| ALTI | 150-500k | 2.58 | 344 | 60 | 39 | 511 | 137 | 188 | 359 | 269 | 658 |
| PYPD | 150-500k | 4.90 | 403 | 60 | 126 | 2,435 | 162 | 124 | 169 | 166 | 238 |
| ARTNA | 150-500k | 33.48 | 451 | 60 | 60 | 5,713 | 66 | 58 | 62 | 63 | 56 |
| CVGI | 150-500k | 2.87 | 496 | 60 | 35 | 2,813 | 158 | 123 | 0 | 176 | 186 |
| AUNA | 0.5-1.5M | 5.32 | 502 | 60 | 38 | 17,823 | 88 | 93 | 135 | 251 | 176 |
| RML | 0.5-1.5M | 4.55 | 567 | 31 | 259 | 75 | – | – | – | – | 0 |
| AOMR | 0.5-1.5M | 7.19 | 652 | 60 | 28 | 2,878 | 82 | 102 | 112 | 110 | 202 |
| MED | 0.5-1.5M | 11.88 | 740 | 60 | 17 | 9,505 | 96 | 100 | 177 | 150 | 416 |
| PXS | 0.5-1.5M | 7.50 | 825 | 60 | 148 | 3,469 | 173 | 181 | 100 | 108 | 0 |
| CLW | 0.5-1.5M | 19.30 | 915 | 60 | 21 | 26,052 | 86 | 114 | 125 | 90 | 101 |
| NRXS | 0.5-1.5M | 7.70 | 1,050 | 60 | 26 | 1,927 | 171 | 165 | 0 | 234 | 0 |
| AVNW | 0.5-1.5M | 18.94 | 1,222 | 60 | 21 | 2,340 | 142 | 144 | 191 | 109 | 272 |
| USAU | 0.5-1.5M | 11.88 | 1,328 | 60 | 42 | 2,828 | 111 | 119 | 0 | 99 | 0 |
| HYPD | 0.5-1.5M | 2.87 | 1,496 | 60 | 105 | 2,691 | 185 | 262 | 319 | 153 | 436 |
| BHB | 1.5-5M | 38.17 | 1,508 | 60 | 57 | 55,372 | 58 | 37 | 0 | 39 | 29 |
| AMRO | 1.5-5M | 4.71 | 1,723 | 2 | 490 | 45,998 | – | – | – | – | – |
| YORW | 1.5-5M | 30.94 | 2,026 | 60 | 55 | 6,180 | 69 | 63 | 64 | 52 | 19 |
| CRON | 1.5-5M | 3.21 | 2,376 | 60 | 31 | 4,344 | 62 | 83 | 0 | 65 | 138 |
| DBI | 1.5-5M | 6.07 | 2,734 | 60 | 16 | 37,570 | 144 | 173 | 172 | 21 | 319 |
| FLGT | 1.5-5M | 19.92 | 3,147 | 60 | 10 | 3,282 | 91 | 117 | 149 | 88 | 369 |
| BY | 1.5-5M | 37.28 | 3,696 | 60 | 11 | 4,006 | 54 | 36 | 0 | 11 | 0 |
| CANG | 1.5-5M | 3.06 | 4,149 | 60 | 33 | 1,530 | 383 | 441 | 310 | 56 | 190 |
| ATTO | 1.5-5M | 13.75 | 4,448 | 52 | 65 | 14,566 | 293 | 266 | 72 | 52 | 0 |
| EGY | 1.5-5M | 6.20 | 4,997 | 60 | 16 | 18,631 | 79 | 98 | 99 | 89 | 0 |

### 2.4 Call counts, sizes and the cost of a bigger pull [M]

**Pilot cost:** about 50 read-only calls in total (log: `data/scalping/rh_pilot/call_log.csv`). No rate-limit error was seen.

| Pull | Calls | Raw JSON |
|---|---|---|
| Universe snapshot ($50k–5M ADV), 7 price slices of ≤ 200 rows | 7 per snapshot (more slices for full coverage, ~10–12) | ~0.1 MB per call |
| Daily bars, 40 stocks × 827 bars (2023-07 → 2026-10) | 4 (10 symbols per call) | 1.4 MB per call |
| 5-minute bars, 6 stocks × 59 sessions (4,602 bars each) | 4 (≤ 2 symbols per call) | 0.8 MB per symbol |
| **Extrapolation:** daily bars, last ~3.3 years, 1,000 low-volume stocks | ~100 | ~140 MB |
| **Extrapolation:** daily bars, full history from 1999-09, 1,000 stocks (≤ 2 symbols per call for size, 2 spans for the 5,000-bar cap) | ~1,000 | ~1.2 GB (less if each start date is set to the listing date) |
| **Extrapolation:** 5-minute bars, full ~7.5-month retention (~12,500 bars per symbol), 200 stocks | ~300 (2 symbols × 5,000 bars per call) | ~0.45 GB |
| **Extrapolation:** 1-minute bars, ~6 weeks (~11,700 bars per symbol), 200 stocks | ~300 | ~0.4 GB |

**Practical limits:**
- The MCP is callable only by the agent, not from a Python job, so 300–1,000 calls take roughly 1–3 hours of an interactive or scheduled agent session.
- Intraday retention is rolling, so intraday history has to be **collected forward and stored**; it cannot be re-pulled later.

---

## 3. Daily-bar spread estimators vs the quoted spread [M]

**Setup:**
- 38 pilot stocks with at least 40 real bars among the last 60 sessions (2026-07-24 → 2026-10-16; ATTO from 2026-08-05).
- Benchmark: the closing NBBO on 2026-10-16. A single snapshot is itself noisy, and the estimators target *effective* spreads (trade-weighted, all day), so a perfect match is not expected.
- Script: `data/scalping/scripts_pilot/spread_estimators.py`. Output: `data/scalping/rh_pilot/spread_estimates_pilot40.csv`.

| Estimator | Spearman ρ with quoted (p) | Median ratio est / quoted | IQR of ratio | Share = 0 | Median abs log error |
|---|---|---|---|---|---|
| Roll (1984) | −0.10 (0.57) | 1.19 | 0.00–4.63 | 37% | 2.18 |
| Corwin–Schultz (negatives to 0, then mean) | +0.45 (0.004) | 1.43 | 0.98–4.40 | 0% | 0.64 |
| Corwin–Schultz (mean, then floor at 0) | +0.29 (0.08) | 0.75 | 0.23–1.77 | 13% | 0.74 |
| Abdi–Ranaldo, window | +0.19 (0.25) | 0.96 | 0.21–3.46 | 24% | 1.35 |
| Abdi–Ranaldo, 2-day mean | +0.50 (0.001) | 1.80 | 0.98–3.97 | 0% | 0.84 |
| **EDGE (Ardia et al. 2024)** | **+0.57 (<0.001)** | 1.40 | 0.89–3.75 | 0% | **0.53** |
| ADV alone (LOO regression) | — | — | — | — | 0.68 |
| **log ADV + log price + log daily vol (LOO OLS)** | LOO ρ +0.73 | — | — | — | 0.59 (in-sample R² 0.62) |

**Bucket medians (bp):**

| ADV bucket | quoted | CS | AR 2-day | EDGE | Roll |
|---|---|---|---|---|---|
| $50–150k | 313 | 230 | 236 | 249 | 159 |
| $150–500k | 123 | 147 | 124 | 171 | 60 |
| $0.5–1.5M | 28 | 111 | 119 | 110 | 176 |
| $1.5–5M | 31 | 79 | 98 | 52 | 29 |

**EDGE on 5-minute bars** (per-day estimate on traded bars only, median over 59 sessions) vs the closing quoted spread. The "$ per bar" column uses Robinhood intraday volume, which covers only 32–58% of daily volume (section 1.1):

| ticker | ADV30 | quoted bp | EDGE daily-bar bp | **EDGE 5-min bp** | 5-min bars with a trade | median $ per traded 5-min bar |
|---|---|---|---|---|---|---|
| FSI | $59k | 66 | 203 | **65** (12 usable days) | 12% | $1,821 |
| SCOR | $137k | 263 | 228 | **143** | 24% | $2,595 |
| ALTI | $344k | 39 | 269 | **39** | 53% | $1,316 |
| MED | $740k | 17 | 150 | **16** | 60% | $4,473 |
| CRON | $2.4M | 31 | 65 | **18** | 98% | $12,978 |
| EGY | $5.0M | 16 | 89 | **7** | 99% | $15,995 |

**Reading:**
- **Daily estimators rank stocks only moderately well. Level errors are typically a factor of 1.7–2.3, and they are biased upward wherever the spread is small relative to volatility:**
  - in the $0.5–5M buckets, daily CS, AR and EDGE run about 1.7–4.3× the closing quoted spread (bucket medians; the low end is EDGE in $1.5–5M at 52 vs 31 bp);
  - CS correlates 0.80 with daily volatility but only 0.45 with the quoted spread.
  - This matches the published critique that low-frequency measures carry a volatility-induced bias when the spread is small relative to volatility (Jahan-Parvar & Zikes, RFS 2023). [S] (abstract seen only through a search snippet; RePEc was unreachable at fact-check; the citation 36(10):4190–4232 agrees with memory) — [RePEc](https://ideas.repec.org/a/oup/rfinst/v36y2023i10p4190-4232..html)
- **In the thinnest bucket the daily estimators run below the quoted spread** (bucket median 230–249 vs 313 bp). That fits trades in very thin names often printing inside a wide displayed quote, and the closing snapshot may also overstate the typical spread. [U]
- **EDGE on 5-minute bars is the best proxy we can compute from Robinhood data.**
  - It comes within 10% of the quoted spread for FSI, ALTI and MED (ratio 0.93–1.01).
  - It comes in at 0.44–0.58× for SCOR, CRON and EGY. That is below the quoted spread, as expected for an effective spread when trades print inside the quote.
  - Unlike the daily estimators, it never overstates by more than ~1% in these 6 names (n = 6 only). But 5-minute data exists only for the last ~7.5 months.
- **Usability verdict for a daily-horizon test:**
  - Daily-bar estimators are **usable only as a conservative cost (upper bound) in the $0.5–5M buckets** and as a rough level in the $50–500k buckets.
  - They are **not** precise enough to judge strategies whose gross edge is within about 2× of cost.
  - Use the per-stock maximum of (EDGE-daily / 1.4) and the ADV-price-volatility model, and report results at 1×, 1.5× and 2× that cost.
- **Published claims for the estimators:**
  - EDGE: the abstract says common estimators are downward biased when trading is infrequent, and EDGE is asymptotically unbiased and efficient. [S] (FHNW page unreachable at fact-check). — [FHNW repository record](https://irf.fhnw.ch/entities/publication/f9b26d6d-1a1e-4767-af52-b5b253b5877f)
    - Citation (JFE 161, 103916) and "estimates the root mean square effective spread" checked against the package README. [A] — [`bidask` README](https://github.com/eguidotti/bidask)
    - Our `edge()` was checked line by line against `bidask/edge.py` in the MIT-licensed 2.1.0 wheel from PyPI, and the logic is identical. [A]
  - Abdi–Ranaldo: the abstract says it has the highest cross-sectional correlation with TAQ effective spreads and is the most accurate for less liquid stocks. [S] (RePEc unreachable at fact-check; the wording agrees with memory) — [RePEc](https://ideas.repec.org/a/oup/rfinst/v30y2017i12p4437-4480..html)
  - Corwin–Schultz: high-low spread estimator, JF 67(2):719–760. [S] — [NBER WP version](https://projects.nber.org/confer/2009/mms09/Corwin_Schultz.pdf)
  - **Our pilot does not reproduce Abdi–Ranaldo's "most accurate for less liquid" claim in 2026 low-volume names.** The window version is 0 for 24% of names. This is a weak test: n = 38, and the benchmark is a single closing quote, not their TAQ effective spread.

---

## 4. Alternative and public US data

### 4.1 Broad daily OHLCV panel incl. small caps and delisted names

| Source | URL | Coverage | Survivorship | Reachable | Tag |
|---|---|---|---|---|---|
| **qlib US 1d** (SunsetWolf release) | `github.com/SunsetWolf/qlib_dataset/releases/download/v0/qlib_data_us_1d_v3.zip` (615 MB) | 13,354 symbols (stocks + ETFs), 2000-01 → 2024-04-26. Alive mid-2005: 2,883; 2010: 4,032; 2015: 5,670; 2020: 8,473. 32 of 40 pilot names present. | **Biased.** Only 132 symbols end before 2020-11; 2,303 freeze at 2020-11-10 (SIVB, FRC, BBBY, SBNY, ATVI, TWTR), so later collapses are missing. Effectively a Nov-2020 Yahoo snapshot extended for survivors. | Yes (HTTP range reads work) | [M] |
| `us-stock-data` prices.parquet | `github.com/q100423gg-coder/us-stock-data/releases/download/data/prices.parquet` | ~2,323 mostly liquid tickers, 2024-08 → today; only ~170 below $10M ADV (172 on full-sample median $ volume; 83 on the last 90 days' mean, local copy to 2026-10-14) | Survivor-only | Yes | [M] (URL: repo HANDOFF §3; counts measured) |
| Johnbrick123 sp500-data | GitHub release | S&P 500 point-in-time incl. ~400 dead names, 1995 → 2026 | Point-in-time, but large caps only | Yes | [M] (repo HANDOFF §3) |
| pystock-data (eliangcs) | `raw.githubusercontent.com/eliangcs/pystock-data/master/2015/0001_initial.tar.gz` (42 MB) + daily archives | Yahoo daily prices for NASDAQ.com symbol lists, 2009-01 → 2017-03 (unmaintained) | Initial batch survivor-only as of 2015-03; daily files 2015-03 → 2017-03 are a partial point-in-time record | Yes | [A] README, [M] reachability |
| Quandl / Nasdaq WIKI prices | data.nasdaq.com; Quantopian S3 mirror `s3.amazonaws.com/quantopian-public-zipline-data/quandl` | ~3,000 US companies, frozen 2018-03 | Includes some delisted names | No (host blocked; S3 bucket AccessDenied) | [S] — [search summary](https://backtrader.readthedocs.io/en/latest/api/feeds/backtrader.feeds.quandl.html) |
| Kaggle "Stock Market Dataset" (jacksoncrow) | kaggle.com | NASDAQ-listed tickers to 2020-04 | Survivor-only | No (blocked) | [S] — [Kaggle](https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset) |
| MarketParquet | marketparquet.com | Daily + intraday US, delisted included; free tier = last year only; $79 archive | Survivorship-free (vendor claim) | No (blocked) | [S] — [vendor FAQ](https://marketparquet.com/faq) |
| BlackFalcon delisted-stocks-list | `github.com/BlackFalconData-org/delisted-stocks-list` | 36,000+ Form 25 / Form 15 delisting records since 2002 (**no prices**) | Delisting registry | README only; data sits behind Apify | [A] README |
| CRSP / Norgate / Sharadar / EODHD / Polygon (Massive) / Tiingo | vendors | Full US incl. delisted | Survivorship-free | Paid or keyed; hosts blocked here | [U] |
| Robinhood MCP daily | — | 1999-09 → today for currently resolvable tickers | Survivor-biased (section 1.1) | Yes | [M] |

### 4.2 Intraday minute bars for small caps

| Source | Coverage | Reachable | Tag |
|---|---|---|---|
| **Robinhood MCP** | 1-min ~6 weeks, 5-min ~7.5 months, hourly ~10 months, rolling; RTH or extended or 24-hour sessions | Yes | [M] |
| Hugging Face `ggaddam/OHLCV-1m` | Minute bars for "thousands of U.S. stocks", 1992–2025, Finnhub-sourced; delisted coverage unknown | No (huggingface.co blocked) | [S] — [listing](https://app.alphaneural.io/datasets/ggaddam/OHLCV-1m) |
| qlib US 1-min | Tried `.../v2/qlib_data_us_1min.zip`: 404 | No | [M] |
| Polygon / Alpaca / Tiingo / Databento / FirstRate / Kibot | Minute bars, SIP; keys or payment needed | No (blocked) | [U] |
| IEX HIST (below) | Tick-level, aggregable to bars of IEX trades only | Yes | [M] |

### 4.3 Trade-and-quote samples (TAQ / ITCH / LOBSTER / IEX)

| Source | URL | What | Reachable | Tag |
|---|---|---|---|---|
| **IEX HIST TOPS** | `https://storage.googleapis.com/iex/data/feeds/YYYYMMDD/YYYYMMDD_IEXTP1_TOPS1.6.pcap.gz` (1.5 before ~2017-12) | IEX top-of-book quote updates + IEX trades, nanosecond timestamps, every NMS symbol. TOPS 1.5 from **2016-12-12** to 2017-11-30 (0.55–0.67 GB/day). TOPS 1.6 from **2017-09-06** to 2026-10-16 (0.45 GB on 2020-01-02, 4.7 GB on 2022-10-03, 14.6 GB on 2026-10-16). These are the first dates found by probing files at fact-check; earlier days return 403. Listing the bucket is denied, but objects download (63 MB/s here). | **Yes** | [M]; launch notice [S] — [IEX alert 2017-014](https://iextrading.com/trading/alerts/2017/014/) |
| IEX HIST DEEP 1.0 | same path, `DEEP1.0` | IEX depth of book (price-level aggregated), from 2017-05-15, ~0.5–15.4 GB/day (0.48 GB on 2020-01-02) | **Yes** | [M] |
| IEX DEEP+ | same path, `DEEP_PLUS1.0` | order-by-order | No (403) | [M] |
| Nasdaq ITCH 5.0 samples | `emi.nasdaq.com/ITCH/` | Full order-by-order feed for a few sample days (~6 days, 3 exchanges, ~25 GB) | No (blocked) | [S] — [RITCH post](https://www.r-bloggers.com/introducing-ritch-parsing-itch-files-in-r-finance-market-microstructure/) |
| NYSE Daily TAQ samples | `ftp.nyse.com/Historical Data Samples/` | One-day TAQ samples | No (blocked) | [U] |
| LOBSTER samples | lobsterdata.com | Nasdaq LOB samples, large caps (e.g. 2012-06-21) | No (blocked) | [S] — [MathWorks example](https://www.mathworks.com/help/finance/machine-learning-for-statistical-arbitrage-data-management-and-visualization.html) |

### 4.4 IEX HIST pilot: one full day (Fri 2026-10-16), 40 pilot names [M]

**Method:**
- Streamed the whole 14.6 GB TOPS 1.6 file (62.9 GB uncompressed) from GCS through a byte-pattern filter.
- Kept Quote Update and Trade Report messages for the 40 names plus AAPL: 1.0M quote updates and 37k trades, 52.7 MB CSV, **1,130 s wall time** on one core.
- Output: `data/scalping/iex_pilot/iex_tops_20261016_pilot40.csv` and `iex_summary_20261016_pilot40.csv`. Consolidated volume is from Robinhood daily bars.

| ADV bucket | IEX time-weighted quoted spread, RTH (median bp) | closing NBBO (median bp) | IEX share of consolidated volume (median) | IEX trades in RTH (median) | IEX quote updates in RTH (median) |
|---|---|---|---|---|---|
| $50–150k | 3,277 | 313 | 0.2% | 3 | 100 |
| $150–500k | 2,728 | 123 | 1.9% | 31 | 279 |
| $0.5–1.5M | 2,382 | 33 | 3.6% | 137 | 536 |
| $1.5–5M | 788 | 32 | 5.0% | 397 | 4,576 |

**Reading:**
- **IEX shows a two-sided quote for 38 of 40 names all day, but in most of them it is a wide 100×100 placeholder,** ~25–35% around the price. This looks like market-maker quoting-obligation quotes [U]. Real liquidity sits elsewhere.
- **The IEX BBO matched the NBBO at the close on both sides for only 5 of 40 names** (PYPD, CVGI, HYPD, CRON, EGY). Its all-day spread was within 2× of the closing NBBO for only 3 (CVGI, CRON, EGY). AMRO also passes, but its IEX quote was two-sided for under 1% of RTH. Median IEX displayed size at the close was 100 shares a side.
- **IEX executes ~0.2–5% of volume in these names** (median 2.7%, maximum 9.3%), and 2 names had no IEX trade at all. AAPL as a control: 895k quote updates, 29k trades, time-weighted IEX spread 6.9 bp.
- **Verdict:** IEX HIST is real, free tick data covering nearly ten years (from 2016-12), but **in low-volume names it cannot stand in for the NBBO** and holds almost none of the order flow.
  - It is useful for (a) exact timestamps of a few percent of trades, and (b) quote and queue studies only in the more active ~$2–5M-ADV names where IEX is at the inside.
  - A resting order on IEX in a $100k-ADV name would almost never trade.

---

## 5. Recommended US data designs

### (i) Daily-horizon liquidity provision / short-term reversal in low-volume names, net of estimated spreads

**Universe:**
- **Forward (clean):** from now on, save the scanner universe every trading day: 7–12 price slices, ~0.1 MB each, with closing NBBO, sizes, ADV30/60, float and listing. That gives a point-in-time, survivorship-free universe from 2026-10 onward.
- **Backward (biased, label it so):**
  - Robinhood daily bars 2023-07 → 2026-10 for today's ~1,500–2,000 names (~100–200 calls).
  - Optionally qlib 2000–2020 for a long, survivor-biased history.
  - Report the qlib result as an *upper bound*: dead names are missing, and the collapses of names that died in 2020–24 are cut off.

**Signal and timing:**
- Daily bars, regular session, split-adjusted. Drop interpolated and zero-volume days.
- Liquidity filters use only data up to t−1: ADV, price > $1, at least N trading days.
- Execution at the next close or open, with the price taken from that bar.

**Cost model (per stock, per day):**
- Half the spread per side, where the spread is the maximum of:
  - 5-min EDGE (where the window has it);
  - EDGE-daily / 1.4;
  - the log-ADV/price/volatility model (fitted on the forward closing-NBBO archive).
- Plus square-root impact: 0.5–1 × daily volatility × √(order / ADV).
- **Stress at 1×, 1.5× and 2× cost.** A strategy should pass at 1.5×.

**Long-only realism:** shorting $50k–5M ADV names is usually impossible or expensive for a retail account [U], so the long-only leg should be the primary test.

**No MOC or LOC orders:** the agentic order types are market, limit and stop variants, GFD/GTC, with no market-on-close or limit-on-close [A: `place_equity_order` tool schema, type ∈ market / limit / stop_market / stop_limit, time_in_force gfd / gtc; also `AGENTIC_TRADING_PLAN.md` §1]. A trade "at the close" therefore crosses the closing quote, which makes the closing quoted spread the right cost benchmark for this test.

### (ii) Intraday passive-fill test (bid at the bid, sell at the ask)

**What Robinhood data allows:**
- 5-min bars (7.5 months), 1-min bars (6 weeks) and 15-second bars (~2 weeks), all trades-only.
- Conservative fill rule: a resting buy at price P fills only if a later bar's **low < P** (a strict trade-through), never at the touch, because queue position is unknown. The bars carry only part of the tape (section 1.1), so highs and lows are understated and the rule is conservative on fills too.
- Mark-out from the next bars' closes, i.e. adverse selection proxied with trade prices.
- Spread level from 5-min EDGE.

**What it does not allow:**
- **There are no historical quotes**, so realized spread, effective spread and price impact cannot be measured against a midquote.
- Queue position and touch fills cannot be modeled.
- 76–88% of 5-min bars in $50–150k names have no trade at all, so fills and mark-outs are very sparse.

**What IEX HIST adds:**
- Tick-level IEX BBO and IEX trades for any day back to 2016-12-12 (TOPS; DEEP from 2017-05-15). That allows a queue-aware simulation **on IEX liquidity only** and a mark-out against the *IEX* midquote.
- **The pilot shows the limit:** IEX's BBO is not the NBBO, and in low-volume names it is mostly a ~30%-wide placeholder, with IEX executing 0.2–5% of volume (section 4.4). It is usable only for the more active ~$2–5M-ADV names where IEX sits at the inside, and even there it measures one venue's queue, not the market.
- **Budget:** about 19 minutes of streaming and filtering per 14.6 GB day-file with the pilot filter (`data/scalping/scripts_pilot/iex_tops_filter.py`, a pure-Python byte-pattern scan), so a sample of 20–60 days is feasible; every day of 9 years is not.

**Forward collection (best long-run fix):**
- During RTH, poll `get_equity_quotes` (bid and ask, no size) and a symbol-scoped `preview_scan` (bid/ask *with sizes*, 40+ names per call) every 1–5 minutes for a fixed panel of ~100 names, plus `get_equity_price_book` (4 per call) to learn the Level-2 depth.
- That builds our own NBBO and size history. It cannot be back-filled.

**Not measurable anywhere free:** the full consolidated NBBO and odd-lot quotes, Robinhood's own fill quality (Rule 605/606 statistics were not reachable), and queue priority versus other venues.

### (iii) Capacity analysis

**Inputs available now:**
- Per-stock inside depth at the close (scanner sizes).
- ADV30/60 in dollars (scanner `turnoverAvg`).
- Traded dollars per 5-minute bar and the share of bars with trades (5-min bars).
- Daily volatility (daily bars).
- IEX displayed depth (DEEP) on sample days.

**Anchors from this pilot:**
- Median inside depth is about **$1,000 per side** in $50–150k-ADV names and about **$8,000** in $1.5–5M names.
- A $59k-ADV name (FSI) trades in only 12% of 5-minute bars, with a median of $1.8k per traded bar.
- **A passive order that is "large" relative to these numbers is the whole visible book.**

**Formula to pre-register:**
- Daily P&L ≈ participation × ADV × (realized half-spread − adverse selection − fees) − impact on exits.
- Example at 10% participation, before adverse selection:
  - a median $96k-ADV name trades ~$9.6k a day, worth **~$94 a day at the full quoted half-spread (98 bp)**;
  - a median $3M-ADV name trades ~$300k a day, worth **~$320 a day at its 10.7 bp half-spread**.
- These are ceilings, and they do not grow with capital: the binding input is other traders' order flow. Both examples use scanner ADV; consolidated ADV is ~1.5× higher (section 2.1), which raises the ceilings in proportion. [M arithmetic on measured medians]

**Capital usefulness:**
- Extra capital lets you cover more names in parallel; it does not raise per-name capacity.
- Report capacity as the number of names × per-name ceiling, and **show how the edge decays with participation** (1%, 5%, 10%, 20% of ADV) under square-root impact.

---

## 6. Blockers and open items

- **Market closed during the pilot.** These need re-running during RTH on a weekday:
  - quote snapshots a few minutes apart;
  - `get_equity_price_book` depth;
  - whether `get_equity_quotes` and the scanner agree intraday.
- **No historical NBBO anywhere reachable.** Realized-spread measurement against the consolidated quote is impossible without paid TAQ, Polygon or Databento. IEX HIST is a venue-only substitute, and in the names that matter here it is mostly a placeholder.
- **No survivorship-free small-cap daily history.** Every reachable panel is survivor-biased before 2026-10, so a clean point-in-time universe exists only going forward.
- **The scanner's `total_items` is unreliable**, and each preview is capped at 200 rows. A complete universe needs narrow slices; deduplicate by ticker.
- **Robinhood intraday retention is rolling.** Anything intraday that we want must be saved as it is pulled.
- **Files:**
  - raw pilot data: `data/scalping/rh_pilot/` (gitignored);
  - IEX extracts: `data/scalping/iex_pilot/`;
  - scripts: combine_scans.py, spread_estimators.py, extra_models.py, iex_tops_filter.py, iex_analyze.py and rangezip.py (the qlib zip probe), copied to `data/scalping/scripts_pilot/`. They are gitignored and not in the repo; move them into `analysis_2026/` if the study goes ahead.
