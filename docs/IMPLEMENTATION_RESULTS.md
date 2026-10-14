# Implementation results — 2026-10-14 UTC

The corrected research engine and deterministic offline shadow executor are
implemented and tested. **No stock basket qualifies for deployment from the
available data.** The corrected runner has not evaluated the reserved 2023–2025
window, no real account was accessed, and no trade was proposed or placed.

During publication, upstream advanced to commit `2e608fb4`. Its historical
`holdA`/`fwdB` outputs overlap the reserved evaluation periods. Those results are
preserved as upstream history; the corrected runner did not read their outcome
tables or use them to tune its settings. The historical period is therefore
**not globally untouched**, and a later corrected evaluation cannot by itself
serve as a fresh independent holdout. A prospective frozen evaluation and
forward shadow observation are needed for deployment evidence.

## What is implemented

- The existing exact daily ATR(10) × 2 reset-on-flip indicator drives both
  research and shadow signals. Completed-session signals execute at the next
  session open in research; red positions retain cash in their own slots.
- Causal five-year formation and subsequent three-year testing compare top
  5/10/20/30/40, timing skill above 10, and all eligible stocks. Continuous SPY,
  holding the same selections, and trading all eligible stocks are controls.
  Selection changes do not reset capital, taxes or retained holdings.
- Separate dividends, explicit terminal proceeds, FIFO tax lots, loss carry and
  same-account wash-sale deferral are modeled. Unknown economic outcomes produce
  unidentified comparisons. Total-return-adjusted OHLC cannot identify taxes or
  qualify the exact split-only strategy.
- Frozen settings, implementation and dataset checksums, full calendar checks,
  and a local one-attempt holdout guard support a later complete-data evaluation.
- Shadow planning has explicit budgets, whole-share sizing, stable intent IDs,
  a durable SQLite journal, duplicate-safe partial-fill reconciliation, exact
  parameter enforcement and STOP handling. The typed broker adapter has no live
  placement method or default credentialed transport.

## Corrected development run

The settings were frozen before the final run. The test horizon is all of
2005–2022, with six nonoverlapping three-year windows. Costs are 3 basis points
per side and uninvested cash earns zero. These are **exploratory diagnostics**
using public Qlib prices declared total-return-adjusted by the import and
retrospective community membership, not validated performance of the intended
live strategy. The concurrent upstream audit additionally reports an adjustment
boundary on 2021-09-16, with price-only data thereafter. This hybrid adjustment
claim remains an unresolved provenance gap; neither dividends nor taxes are
inferred from a proxy yield. The numeric paths below cannot be treated as
verified total returns throughout the horizon.

| Selection rule | Pretax CAGR | Maximum drawdown | Holding the same selections: CAGR | Status |
| --- | ---: | ---: | ---: | --- |
| Top 5 by formation timing skill | 6.82% | −43.68% | 2.03% | Research only |
| Formation timing skill above 10 | 8.74% | −42.30% | 6.18% | Research only |
| Top 10 / 20 / 30 / 40; all eligible | Unidentified | Unidentified | Unidentified | Missing executable prices or terminal outcomes |
| SPY held continuously | 8.52% | −55.19% | — | Exploratory benchmark |

The above-10 rule's approximately 0.22 percentage-point pretax advantage over
SPY does not establish a durable edge. Its selection count varies by period;
it is not a fixed 20–30-stock basket. All after-tax comparisons are unidentified
and no development candidate was selected. Unknown future timing outcomes also
prevent an identified permutation-test result; no statistical significance is
claimed.

The first formation window, 2000–2004, has no eligible securities because the
archive lacks the required 100 pre-formation warmup bars. The corresponding
2005–2007 window remains in cash at zero return instead of disappearing. Later
eligible counts are 333, 363, 389, 429 and 481. Thus these numbers are sensitive
to the archive's coverage and cannot replace a complete-data rerun.

The [public run receipt](../research_results/corrected_development_receipt.json)
contains frozen configuration, coverage counts, checksums and compact results.
Raw source data, broker responses, full local ledgers and account-related files
are excluded from version control.

## Data acquired and checked

- The pinned Qlib development archive was decoded only through 2022-12-30. The
  historical master retains 1,027 records; 782 have price files and 245 lack
  histories. Missing records remain visible in the coverage audit.
- 3,559,052 bars were accepted. 58,746 were quarantined: 54,444 unavailable or
  nonfinite rows and 4,302 materially inconsistent candles. A declared tolerance
  of two float32 units in the last place accepts 5,346 source-rounding cases
  without changing their prices. This tolerance applies only to the declared
  exploratory float32 total-return source. Validated and Robinhood feeds use
  exact OHLC checks. CSV parsing preserves source float values by round trip.
- Actual Robinhood public daily split-adjusted histories supplied 1,259 valid
  bars each for AAPL, AMD, AMZN, IWM, MSFT, NVDA, QQQ, SPY and TSLA in 2018–2022.
  COIN was rejected because its response included interpolated pre-IPO bars
  and an inconsistent IPO candle; no invented corrections were applied.
- On Robinhood IWM prices, the unchanged indicator matched all 1,159 tested
  TradingView states and all 67 same-date flips after warmup, from 2018-05-25
  through 2022-12-30. This is signal parity evidence, not portfolio validation.

## Verification

`python3 -m pytest tests -q` passed **153 tests**. The three warnings are expected
legacy duplicate/alignment warnings. `python3 -m compileall -q research trading
screener scripts` completed successfully. The complete offline demo recorded and
simulated three orders using invented stocks, prices, a fictional account and
a fictional $30,000 budget. Regression CI runs the tests and this synthetic demo.
No forward shadow observation period has yet been completed.

## Remaining dependencies

A complete licensed export must supply split-only OHLC including delisted
stocks, separate dividends, durable security identities, membership known at
each formation date, and terminal cash/stock events. The normalized import and
audit workflow is ready; acquiring a license and reconciling raw vendor events
are still required. See [DATA_SOURCES.md](DATA_SOURCES.md).

Then rerun development, freeze one explicit candidate, and evaluate the full
reserved 2023–2025 window once with the corrected runner. Treat that comparison
as a historical check with the disclosed outside overlap. Separately preregister
a prospective evaluation and complete forward shadow observation. Only qualifying
independent evidence can supply a real stock whitelist.

Robinhood's currently exposed market-order tools do not guarantee the exact
next-open fill assumed by the research. A connected implementation must test
attainable execution timing and its approval flow, then revalidate that fill
convention. Real account/budget authorization and deliberate write activation
remain separate prerequisites. No scheduler, live transport or trading plugin
was activated in this implementation. See [TRADING_SHADOW.md](TRADING_SHADOW.md).
