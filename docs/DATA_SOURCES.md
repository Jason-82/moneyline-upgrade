# Stock research data: acquisition and normalization

The daily ATR(10) × 2 signal uses **split-only OHLC**. Economic returns need
cash distributions and corporate-action proceeds separately. A total-return
price series is useful for development diagnostics, but is not a replacement
for those two inputs and cannot support a defensible realized-gain tax ledger.

## Available now

The existing Microsoft Qlib-format community archive was acquired in the prior
review. Its fixed source is
`https://github.com/SunsetWolf/qlib_dataset/releases/download/v0/qlib_data_us_1d_v3.zip`.
The archive is 614,669,346 bytes and has SHA256
`d7dcb4f227d96930700ebebf3e47cf38a5352a4bbeb35ca9be789aa94969bbc4`.
Release metadata recorded its update as 2024-05-22T07:35:51Z. The archive
contains later dates; the acquisition script bounds the calendar before reading
each binary price vector. Development imports end at 2022-12-31.

Membership is the community-maintained `fja05680/sp500` history pinned to commit
`a2430f2af0c79ddf0748e91de11bdeb1616ab5a7`, file
`sp500_ticker_start_end.csv`, SHA256
`b2f4fe2f2e4dce8eaf0eb4fbd3946a32a20c1ddfe69687dfca3b6b59a0b71f9f`.
It contains retrospective historical membership spells; it is not a licensed,
announcement-timestamped constituent feed or a security master. A ticker
history does not resolve ticker reuse or multiple share classes.

These inputs cannot establish that a portfolio is deployable. The import declares
Qlib's prices rescaled total-return OHLC, but concurrent upstream commit
`2e608fb4` reports an adjustment boundary on 2021-09-16 and price-only data
thereafter. That hybrid-adjustment claim is not independently reconciled here;
the full path cannot be treated as verified total returns. Historical terminal proceeds are absent,
historical stable security IDs are absent, and many old delisted constituents
are missing. The importer preserves available rows and quarantines invalid
bars rather than removing a security based on its later history. Coverage is
reported at every specified formation date.

Qlib encodes each OHLC field as float32. A raw pre-2023 audit found 9,648
exact-order range violations: 5,346 are at most two float32 representable steps
(ULPs), all in 2020–2022; 4,302 are larger source defects. The precision-aware
import declares `source_precision: float32` and `ohlc_float32_ulps: 2`, using
the shared validator to accept only the former without changing any source
price. Generic broker/CSV and validated datasets retain exact-order validation.
The old exact-order quarantine is preserved as an audit, not used as evidence
of missing stock history: tiny numerical roundoff is not an economic data gap.
Material violations and unavailable records remain quarantined.

The Robinhood plugin exposes split-adjusted daily historical bars. Actual
responses can verify signal parity and today's execution pipeline, but the
available tool surface does not provide a complete historical dividends,
splits, delisted-security master, or terminal-proceeds dataset. Current dividend
yield or the next scheduled dividend must never be projected backward.

## Practical complete-data route

**Sharadar Prices** is the most direct portable route for this project, subject
to a user-held license. Official documentation, checked on 2026-10-14:

| Table / documentation | Required role |
| --- | --- |
| [Stock prices, alias SEP](https://sharadar.com/docs/stocks) | Split-adjusted open/high/low/close and volume; `closeunadj` for raw units; `closeadj` is separate and includes dividends/spinoffs. Active and delisted histories start December 1997. |
| [Fund prices](https://sharadar.com/docs/funds) | SPY benchmark and any fund histories. |
| [Tickers/master](https://sharadar.com/docs/tickers) | Unchanging `permaticker`, distinct for separate share classes. Current metadata must not become a historical eligibility filter. |
| [Corporate actions](https://sharadar.com/docs/actions) | Historical dividends, splits, symbol changes, spinoffs, listing/delisting, acquisition counterparties. |
| [Historical S&P 500](https://sharadar.com/docs/sp500) | Effective-date additions/deletions and historical quarterly snapshots, from 1998. |
| [FAQs](https://sharadar.com/docs/faqs) | Adjustment formulas, ticker reuse and acquisition-consideration semantics. |

The vendor's FAQ documents `acquisitioncash` as cash per target share and
`acquisitionstock` as shares of the acquirer per target share; simultaneous
cash and stock consideration are additive. Election alternatives
`acquisitionelectcash`/`acquisitionelectstock` are alternatives, not additive.
Contingent value rights are not covered. Convert stock consideration using the
declared executable valuation/transfer policy, matching stable IDs and event
dates. Do not treat a last quoted close as terminal proceeds.

The vendor describes roughly 99% survivorship and acquisition-consideration
coverage; that is a vendor estimate, not proof that every needed event is
complete. The import audit must still account for every selected security and
terminal event. The official API requires a valid API key; no license has been
purchased and no credentials have been requested or used in this session.
Authorized bulk CSV exports can remain private and be normalized locally.

### Alternatives

**Norgate Data**, with the relevant Platinum/Diamond US package, provides
active/delisted histories and historical constituents. Its vendor-maintained
[Python documentation](https://pypi.org/project/norgatedata/) documents an
unchanging numeric `assetid`, `price_timeseries`, `CAPITAL` adjustment, and
`PaddingType.NONE`. Export active and delisted databases. Its data access uses
the local Norgate Data Updater and Windows/.NET environment; no compatible
licensed installation is present here.

Norgate's `CAPITAL` includes capital reconstructions, which can go beyond a
plain stock split. Verify signal parity around complex events before treating
it as identical to the Robinhood split-only convention. In CAPITAL mode the
`Dividend` column contains ordinary and special distributions not already
incorporated into the price adjustment. **Its dividend date is the entitlement
date, the trading day before the ex-date.** Convert to the next actual exchange
session for the engine's ex-date convention, preserving the amount in the same
adjusted-share basis. Never shift with a generic business-day calendar.
References: [data content](https://norgatedata.com/data-content-tables.php),
[Python API](https://pypi.org/project/norgatedata/).

**CRSP** is a strong institutional route with permanent PERMNO identifiers,
active/inactive securities, distributions and delisting events.
[Official product](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases).
The 2026 CIZ format and older SIZ exports have different return semantics;
normalize according to the exact licensed format. A return already embedding
distributions/delisting must not receive either component a second time.
Complete next-open testing also requires trustworthy opening prices over the
chosen period: inspect the exact requested field coverage rather than inferring
that all daily CRSP rows have an opening price. No licensed CRSP data is present.

## Import principles

Create the bounded development bundle from already acquired files:

```bash
python scripts/acquire_research_data.py qlib-development \
  --archive /path/to/qlib_data_us_1d_latest.zip \
  --members /path/to/sp500_ticker_start_end_raw.csv \
  --out private/price_data/qlib_development
```

The default import verifies the two exact source hashes above. A different
archive is rejected unless `--allow-unpinned` explicitly requests a diagnostic
import; it still cannot qualify research. The output includes the manifest,
portable CSV contract, and `acquisition_audit` files for missing securities,
invalid bars and dated coverage. Securities lacking prices remain in the master
and membership audit rather than disappearing from the denominator.

For a licensed export, normalize the source tables into the schema documented
by `research/data_contract.py`, and use
`data_manifest/licensed_export.example.json` as a declaration template. Its
flags are intentionally false until supported by source evidence and audits.
Then validate/copy it without overwriting the original:

```bash
python scripts/acquire_research_data.py licensed-import \
  --bundle /path/to/normalized_private_export \
  --out private/price_data/licensed_development \
  --cutoff 2022-12-31
```

This command is for development imports. A frozen experiment must separately
authorize the untouched-holdout workflow; the acquisition CLI refuses a cutoff
after 2022-12-31. The CSV validator does not certify a provider's license or
automatically reconcile raw vendor actions. Export receipts must substantiate
the asserted identity mapping, dividend units, universe and terminal payouts.

### Cash-return assumption

The baseline uses zero cash return unless supplied an observed dated series.
[FRED DTB3](https://fred.stlouisfed.org/series/DTB3) is a Treasury-bill secondary
market **discount-basis** annual quote, not an achieved broker cash return or
a money-market-fund total-return series. An October 2026 read-only probe reached
the official graph page, but the CSV endpoint returned HTTP 404; no usable rate
history was acquired. An eventual Treasury-rate sensitivity must document quote
conversion, lag/availability and accrual convention and remain distinct from
the baseline's actual broker-cash assumption.

1. Signal OHLC, dividends and liquidation proceeds share one consistent share
   basis. Use raw tape price × the cumulative split normalization factor for
   every OHLC field and cash amount. Verify split-day continuity.
2. Cash dividends accrue only to holders at the preceding close, on the ex-date
   in this engine. Payment-date cash availability is a documented approximation
   unless a separate receivable/payment ledger is supplied.
3. Stable IDs are primary keys; dated ticker mappings are display/execution
   attributes. A rename is not a new asset, and a reused ticker is not the old
   asset.
4. Membership spells are effective-date intervals. Selection reads only facts
   available at formation time, including listing status and liquidity.
5. Missing delisting proceeds are missing data. Never manufacture zero proceeds,
   a final-close sale, or a bankruptcy recovery to make the backtest finish.
6. Use an explicit exchange-session calendar. Never forward-fill opening prices
   or fill orders on padded/nontrading bars.
7. Pin every source/export, hash every input, and retain event-level provenance.
   Any unresolved mismatch blocks strict research qualification.

## What remains a hard blocker

No available public/free source in this workspace supplies the combined
survivorship-aware price histories, stable identity mapping, complete dividend
events, and terminal recoveries needed for the proposed broad stock test.
The normalized import contract and audits make a licensed export immediately
usable; they do not transform incomplete public histories into complete data.
Results from the current broad dataset remain development diagnostics and
cannot authorize a live stock basket.
