# Corrected stock-selection experiment

`research.run` supersedes historical independent-window results from
`screener.selection` and `screener.strictness`. It compares each declared rule
with SPY held continuously, holding the exact same selected stocks on the same
reselection schedule, and trading every formation-eligible stock.

The primary rule is fixed: daily reset Moneyline, Wilder ATR(10), factor 2,
hl2; prior completed close green enters at the next actual open, red exits at
the next actual open. Each selected stock has its own capital slot, which holds
cash while red. A changed selection redistributes capital at the next open and
preserves remaining lots. An unchanged selection retains its positions and cash.
Dividend cash is reinvested at the next actual session open where appropriate,
with ordinary transaction costs and transparent basis accounting.

## Causal stock selection

Each formation period is five years. Membership is observed at formation end,
including announcement timestamps, rather than at formation start or after the
test has begun. Listing, quality, warmup, minimum history and trade counts use
only prices at or before that same formation end. A later delisting, malformed
bar or failed download cannot erase a candidate.

The primary score is annualized drift-neutral timing skill:

`100 * (sum(log(1 + strategy_return)) - exposure * sum(log(1 + stock_return))) / years`.

Formation scores include fees and explicit dividends when available; cash is
zero for the score, so the metric isolates the timing hypothesis. Portfolio cash
can accrue a separate observed daily series. The default portfolio cash floor
is zero, rather than an annual average learned after the year has finished.

The declared levels are top 5, 10, 20, 30, 40, skill above 10, and all eligible
stocks. Sector/correlation guards are off and unsupported until separately
declared and implemented. Tied scores use immutable ID order.

At least 100 bars are required **before** the first formation bar. Data beginning
on 1999-12-31 therefore cannot score the 2000–2004 formation period under this
strict rule. Its 2005–2007 portfolio window remains present as cash. The report
includes all warmup exclusions and empty-universe windows.

## Continuous benchmarks and unidentified outcomes

There is one continuous ledger through all test windows: positions, cost basis,
capital-loss carry and annual tax settlements do not reset every three years.
An empty selection holds cash and remains in the full comparison horizon.
SPY enters once and is liquidated only at the final horizon end.

The supplied calendar must match actual XNYS sessions over every declared test
window. An incomplete final date cannot silently shorten a test. No open price
is manufactured, and no unknown terminal proceeds are replaced with the last
quote. Unavailable executable exits or valuations preserve the candidate and
comparison row but produce `UNIDENTIFIED` returns and empty chart values.

Dividend-adjusted OHLC can be used only as an exploratory diagnostic. It changes
indicator flips and does not identify separate dividend taxes. Such a run has
no after-tax estimates or deployable qualification. Tax rates are illustrative
35% short-term and 20% long-term; dividend classification is configured separately.

## Multiplicity and the inference boundary

The development-only permutation test targets **future timing-skill persistence**,
not the proposition that the continuous portfolio beats SPY after tax. One global
random priority per immutable security ID is shared across windows, inducing
correlated conditional score permutations. Holm correction includes every tried
criterion/strictness choice. The all-stock control has no selection p-value.

Missing future OHLC never changes formation eligibility. Its timing-skill outcome
is unknown. If any such outcome exists, the permutation family reports unavailable
p-values, with identified/unknown counts for every window. The current diagnostic
does not translate even a sourced terminal payout into an artificial OHLC bar;
the portfolio engine accounts for the actual cash payout separately.

Every report remains `RESEARCH_ONLY`. A development candidate is a hypothesis for
an untouched test, not permission to trade. A frozen holdout plus actual forward
shadow validation is still required.

## Running and freezing

Use a portable bundle conforming to `research.data_contract`:

```bash
python -m research.run development \
  --dataset private/dataset --mode exploratory \
  --config config/research_experiment.json --output private/research_runs/development
```

Development receives only prices through 2022-12-31. Outputs include summary,
all window rows, formation scores/exclusions, full paths, transaction/tax ledgers,
and a hashed report JSON. Use `--mode validated` only with complete sourced data.

Freeze the full experiment, provenance manifest and implementation hash **before**
any reserved price is loaded:

```bash
python -m research.run freeze \
  --config private/selected_candidate.json --dataset private/dataset \
  --development-report private/research_runs/development/report.json \
  --output private/research_runs/frozen_candidate.json
```

The config must include both `chosen_criterion` and `chosen_level` before a
holdout can be opened. An unselected default config may be recorded but cannot
authorize a holdout. Changed settings, changed source manifest or changed
implementation code invalidate a candidate artifact.

```bash
python -m research.run holdout \
  --frozen private/research_runs/frozen_candidate.json \
  --dataset private/dataset --mode validated \
  --output private/research_runs/holdout
```

The reserved window is exactly 2018–2022 formation → **all of 2023–2025** test.
A local exclusive consumption marker is created before reserved rows are loaded;
successes and failures are recorded. This transparent guard is not an unbypassable
security boundary. The legacy `--until holdout` escape hatch is disabled.

Concurrent upstream commit `2e608fb4` includes historical result files overlapping
these reserved periods. The corrected runner has not evaluated the window, but
the repository's historical period is no longer globally untouched. A later
corrected run is a historical check with disclosed outside exposure, not fresh
independent evidence. Preregister a separate prospective evaluation and complete
forward shadow observation before any deployment qualification.

An observed cash-rate CSV needs `date,daily_return`. Its file SHA256 must be
declared in `cash_rates_sha256` before a run and passed with `--cash-rates`.
Annual average yield tables are intentionally not substituted.

```bash
python -m pytest -q tests/test_stock_selection.py
```

Fixtures cover causal quality/listing/membership decisions, indicator prefix
invariance, empty windows, unknown terminal outcomes, Holm family size,
weekend/incomplete calendars, immutable frozen rules and one-attempt holdout use.
