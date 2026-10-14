# Crypto research data

`scripts/acquire_crypto_data.py` obtains public, read-only Binance global spot
market data. It uses no exchange account, credentials or order endpoint. The
result is historical research data, not evidence of Robinhood execution quality
or a proposal to trade on Binance.

```bash
python3 scripts/acquire_crypto_data.py \
  --output private/crypto_data/binance_snapshots \
  --start 2018-01-01 --end 2025-12-31 --workers 16
```

The downloader works with the Python standard library. Installing `requests`
enables per-thread persistent connections, which substantially speeds public
downloads. Requests are bounded to at most 16 workers, a 25-second timeout and
one retry. The script does not work around rejected private or regional access.

## Historical selection

The official public archive's historical symbol catalog supplies every archived
USDT spot candidate, including retired pairs. Today's trading-pair list is never
used. The acquired catalog had 757 USDT candidates. Selection reads only candles
closed by December 31, 2019 or December 31, 2022 and catalog months already
available at that date. The two baskets remain fixed during their respective
2020–2022 and 2023–2025 evaluation periods.

Eligibility requires at least 365 days of prior venue availability, at least 95%
coverage of the last 30 completed UTC days, and median daily quote volume of at
least 2 million USDT. Eligible pairs are ordered by that median; ties use the
symbol. The first 20 comprise `liquid_top20` and the next 20
`liquidity_next20`. Explicit stablecoin/fiat, wrapped/staked duplicates and
leveraged-token classifications appear in the manifest and source code. No
classification uses future returns or survival. Insufficient eligible members
remain unfilled slots; the downloader does not relax the criteria to fill them.

The actual 2019 snapshot has ten eligible pairs and no next-20 group. The 2022
snapshot has twenty in each group, giving 41 unique histories and 50 dated
memberships across both snapshots. These are **liquidity groups, not verified
large-, mid- or small-cap groups**. Complete historical crypto market-cap and
token-identity histories would be needed for that claim.

## Source verification

Formation candles come from official monthly `1d` ZIPs, each verified against its
published SHA-256 `.CHECKSUM`. The optional full-history source is Binance's
documented, public market-data-only `data-api.binance.vision/api/v3/klines`
endpoint. Every response is retained with request bounds and a byte hash. Its
overlap with each formation archive must match all OHLC, base-volume and
quote-volume values exactly.

If API and archive values differ, the entire security history falls back to the
checksummed archive; individual prices are not averaged or overwritten. This
was necessary for several older major-coin histories because the API and archive
contain revised historical volume. A failed API request for a retired symbol
can also use that symbol's archived history. A 403 or 451 response is not retried
against a disguised or proxy-routed endpoint.

The official spot archive uses milliseconds before 2025 and microseconds from
2025 onward. API timestamps use milliseconds. Both become naive UTC daily
indices. The parser rejects nonfinite/negative values, invalid ranges,
duplicate dates and non-midnight opens. Partial exchange delisting days are
quarantined and listed in source receipts, rather than manufactured into full
UTC candles. Missing days remain missing. Normalized CSVs are written atomically
and verified by SHA-256 before the manifest is published. A failed reacquisition
cannot reuse an older normalized CSV.

`crypto_research.data.load_bundle(path)` returns a `CryptoDataset` with lower-case
`open`, `high`, `low`, `close`, `volume`, `quote_volume` columns; dated universe
membership; source metadata; and quality flags. It verifies normalized file
hashes and preserves missing members in the universe table.

## Limits on conclusions

- USDT is not USD. Stablecoin peg risk and conversions into USD cash are not
  modeled. Comparisons against USD-denominated SPY require this disclosure.
- A venue pair does not provide a complete, immutable token identity. Token
  migrations, redenominations, forks, airdrops, staking and lending income are
  not reconciled. A reused pair such as LUNA has missing transition days and
  cannot be treated as a continuous economic asset without separate evidence.
- Several selected histories cease before the evaluation period ends. There are
  no invented terminal cash payouts or sales at stale prices. Missing execution
  bars and unresolved held positions must make the corresponding portfolio
  outcome unidentified; they must not remove the member after seeing its fate.
- Historical archive inclusion is broader than today's survivors, but it is
  still a single venue's archived universe. It is not a certification that all
  historical crypto failures or exchange listings are present.
- These historical periods are exploratory and exposed by published research
  and earlier analysis. The later period is validation, not an untouched holdout.

Sources: [Binance public archive documentation](https://github.com/binance/binance-public-data)
and [Binance public market-data endpoints](https://developers.binance.com/docs/binance-spot-api-docs/faqs/market_data_only).
