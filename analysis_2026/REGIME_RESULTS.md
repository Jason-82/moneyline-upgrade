# When does Moneyline help? Crypto regime study, 2026-10-14

The historical regime effect is real in the observed sample: **avoiding sustained
downtrends is the principal advantage; capturing more of a bull market is not**.
Turning that description into a reliably superior real-time switching rule is a
separate problem. The primary causal hybrid did not pass its declared checks.

The [experiment](REGIME_EXPERIMENT.md) was written and locally committed before
the first run. All classifiers and policy controls were fixed; no threshold was
optimized afterward. All later windows were already exposed history.

## What changed since the earlier conversation

Reviewed the latest default branch at `4cb2b28`: corrected HANDOFF/FINDINGS,
point-in-time stock strictness results including failed 2023-2025 tests; altcoin
size-tier/payoff results; diversified trend-sleeve results; and style/sector
rotation results. Those studies broadly reject extra complexity as a reliable
source of return. The latest leverage/breakout file declares another study but
has no committed result outputs at this base, so no conclusion is inferred from it.

The earlier Codex PR #2 used different historical windows, exchange data and
accounting. Its 2023-2025 examples did not establish that crypto Moneyline always
loses over complete cycles. The expanded repo contains substantial full-history
ETH/SOL advantages under some execution/cost models. Both observations can be
true: start dates, crashes, timing and friction change the comparison.

## Hindsight attribution: where the advantage comes from

Independently recomputed from the published 1,368 coin-year rows, 2019-2025:

| Coin's final annual holding return | Coin-years | Moneyline beat holding |
| --- | ---: | ---: |
| Below −60% | 511 | 97.1% |
| −60% to −30% | 151 | 78.8% |
| −30% to 0% | 152 | 61.8% |
| 0% to +30% | 133 | 41.4% |
| +30% to +100% | 187 | 34.8% |
| +100% to +300% | 143 | 22.4% |
| Above +300% | 91 | 22.0% |

Using BTC's **eventual** annual holding return as market context: the signal won
in 530/574 (92.3%) observed coin-years in the two falling BTC years (2022, 2025),
versus 351/794 (44.2%) in five rising BTC years. Coins share market shocks; 574
rows are not 574 independent bear markets. A BTC bull year can also contain a
severe individual-coin collapse, so it is not equivalent to each coin rising.

These are explanations with hindsight, not regime forecasts. They cannot be
used to start trading in a year already known to finish down. Nor is outperforming
a coin that loses 80% equivalent to making a positive return or beating BTC/SPY.

Code-review qualifications on the pre-existing altcoin study: `load_crypto`
requires 200 bars over an entire segment, and `tiers_for_year` checks for trades
in the first four future days. Those filters weaken an unqualified ex-ante
survivorship-free claim. Its final-known-price liquidation is optimistic for
delisting execution; the post-delisting scalar cash yield is not reflected in
the recorded equity path. This study reproduces its published **observed rows**,
not an independently rebuilt full historical archive or corrected basket return.

## A classifier the bot could actually know

At a completed daily close, BTC is classified as:

- **Bull:** above its 200-day average, with that average higher than 20 days earlier.
- **Bear:** below the average, with the average lower than 20 days earlier.
- **Transition:** other valid combinations.

The primary hybrid holds the coin throughout bull periods and uses original
Moneyline green/flat in bear and transition. It is tested against always holding,
always Moneyline, and holding only in bull/cash otherwise. The latter control
shows whether any gain is merely the slow classifier's effect. Three inverse/
restricted policies are also reported. Same-coin classification, 150/250-day BTC
neighbors, level-only classification, and drawdown hysteresis are declared checks.

No historical regime label is treated as a known true bull/bear market. Both the
slow classifier and Moneyline lag, and the cost of changing modes is paid.

## Primary later-period comparison

Annualized growth, 2023-2025, five actual exported Moneyline states, next-day
**close** execution, 0.15% each transaction side, zero cash interest, before tax:

| Coin | Hold | Always Moneyline | Hold in BTC bull, Moneyline otherwise |
| --- | ---: | ---: | ---: |
| BTC | 73.80% | 37.61% | 37.46% |
| ETH | 35.08% | 15.10% | 8.13% |
| SOL | 131.54% | 78.30% | 71.38% |
| BNB | 52.16% | 19.30% | 22.89% |
| ZEC | 139.41% | 109.05% | 95.67% |

Maximum drawdowns for always Moneyline versus the hybrid: BTC −29.78/−30.58%,
ETH −46.07/−70.13%, SOL −50.13/−64.70%, BNB −37.60/−48.85%, ZEC −54.71/−69.65%.
The primary hybrid fails the declared BTC/ETH growth and drawdown checks.

Own-coin classification helped ETH in this slice: 36.83% growth and −41.97%
drawdown, versus holding 35.08% and −63.80%. This is one favorable case, not a
deployment winner. It did not rescue BTC, and changing the BTC averaging window
made ETH hybrid growth range from 8.13% (200) to 41.87% (150) to 18.82% (250).
Selecting the best window after seeing these numbers would overfit the regime rule.

## Independent next-open and wider-coin check

On the retained Binance OHLC subset, actual next-UTC-day opens give the following
2023-2025 annualized growth at the same 0.15% per side:

| Coin | Hold | Always Moneyline | Hold in BTC bull, Moneyline otherwise |
| --- | ---: | ---: | ---: |
| BTC | 74.14% | 35.45% | 50.25% |
| ETH | 35.29% | 14.38% | 26.06% |
| SOL | 131.82% | 64.85% | 61.05% |
| BNB | 51.80% | 24.74% | 26.12% |

The hybrid improves BTC/ETH growth relative to Moneyline here, but both still
trail holding. ETH's hybrid drawdown also worsens to −58.97% from −47.19%.
Execution convention/venue sensitivity is substantial, so the close-export and
next-open numbers should not be blended.

There are 40 gap-free retained OHLC histories, including five truncated histories
that cannot support a full later window. LUNA is explicitly unavailable because
of its missing days; no gap is filled. **35 histories** support the common
2023-01-01 through 2025-12-31 comparison. In that conditional subset:

- The primary hybrid beats Moneyline on 6/35 and holding on 1/35. Median growth
  change is −33.18 percentage points versus Moneyline, −17.49 versus holding.
- Bull-only Moneyline/cash beats Moneyline on 16/35 and holding on 23/35. Its
  median change versus Moneyline is −0.60 points. This is largely lower exposure
  to weak altcoins, not evidence of a universal bull-only return improvement.
- The **opposite hybrid** (Moneyline in BTC bull, hold otherwise) beats Moneyline
  on 34/35 and holding on 28/35. Its favorable later-period result is important
  to report rather than hide because it contradicts the initial intuition.

The opposite hybrid is not stable across cycles. It leaves the account exposed
in deep bears: on the full TradingView histories its maximum drawdowns are
−73.97% BTC / −89.78% ETH / −92.96% SOL, versus Moneyline's −62.02 / −60.00 /
−56.09%. It trails Moneyline's full-history growth on all five coins. In
2026-01-01 through **2026-08-23**, its BTC return is −12.67% versus +7.53% for
Moneyline; ETH −18.14% versus +6.09%. These are total partial-period returns,
not annualized forecasts. Favorable 2023-2025 recovery behavior does not justify
holding unconditionally through the next sustained bear.

Post-run sensitivity of the favorable ETH **own-coin** hybrid is separately
marked exploratory in `eth_own_followup_sensitivity.csv`. Next-open growth is
40.88% versus holding's 35.29% at 0.15% friction; at 0.95% it is 28.67% versus
34.57%. With the illustrative immediate-tax sensitivity, the low-cost comparison
becomes 23.80% versus 29.69%. Thus even this apparent exception does not retain a
growth advantage across costs/taxes. No rule or threshold was changed for this
follow-up.

## Other conditions and uncertainty

Moneyline's full-period relative log-wealth contribution is positive on causally
BTC-bear-labelled days for BTC, ETH and SOL in both sources. However, a slow
classifier may still say bear during a rebound; the later-period bear attribution
is negative. This distinction is exactly why hindsight crash avoidance does not
automatically provide an implementable switching advantage.

The declared efficiency and volatility diagnostics are not reliable shortcuts.
On full TradingView histories, BTC/ETH/SOL's average active log-return rates are
positive on low-efficiency (choppy) days and negative on directional days. The
latter mix up and down trends; avoiding losses can help in a choppy falling asset.
The high-volatility diagnostic is negative for all three. Neither finding licenses
an optimized chop/volatility entry filter; those policy variants were not tested.

Shared-date BTC/ETH 90-day block bootstrap, later primary hybrid versus holding:
average annualized active log-return −22.85 points on close exports, conditional
95% interval [−39.10, −7.44]; next-open −10.91, interval [−22.60, +1.36]. Relative
to Moneyline, both source intervals contain zero. These are descriptive uncertainty
checks under nonstationary history, not causal alpha tests, independent coin tests
or corrections for the full research search. All 30/90/180-day blocks are reported.

## Interpretation and practical next step

The harder target is **prolonged weakness rather than a quick dip and recovery**.
An ATR exit can avoid much of a long decline. In a strong rise, cash gaps, re-entry
at higher prices, taxes and costs reduce capture. In a fast reversal, both slow
and fast filters can sell after the decline and miss the recovery. BTC-defined
bull status is especially insufficient to protect an individual altcoin.

The regime evidence supports treating Moneyline as a potential defensive overlay.
It does not establish that the overlay should automatically turn off whenever
a slow classifier says bull, or that bull-only Moneyline has superior returns.
The unchanged indicator already is a regime-dependent long/cash rule.

Keep the primary hybrid as a rejected historical hypothesis. A small prospective
comparison could track holding, always Moneyline and a **fixed** own-coin hybrid,
with decisions/time/costs recorded before subsequent returns. Its objective must
state whether it seeks higher growth or accepts lower growth for drawdown control.
There is no reliable current-regime reading from August-dated exports.

## Reproduction and limitations

Run the committed export comparison:

```bash
python3 -m analysis_2026.regimes
```

Supply the earlier privately retained Binance normalized price folder for the
independent actual-next-open comparison:

```bash
python3 -m analysis_2026.regimes --ohlc-folder /path/to/binance_snapshots/prices
```

`results_regimes/` contains every policy/scenario, attribution, continuous-path
year/block increments, coverage, unavailable histories and input SHA-256 receipt.
The full declared run produced **26,460 scenario/policy rows** across 45 source/
asset histories. A separate vector-return engine rebuilds every pretax row,
reconciles attribution to terminal relative wealth and verifies every recorded
input and runner hash:

```bash
python3 -m analysis_2026.regime_audit --ohlc-folder /path/to/binance_snapshots/prices
python3 -m analysis_2026.regime_followup --ohlc-folder /path/to/binance_snapshots/prices
python3 -m pytest tests -q
```

All 45 tests pass (16 new causality/accounting tests). The suite also exposed a
pre-existing NumPy integer timestamp bug in the obsolete loader; the minimal
type check fix restores its existing test. No original signal/gate was changed.
Full-history start dates differ by coin and require common classifier warm-up.
Daily log relative-wealth attribution sums back to the complete strategy/hold
ratio; its regime-year rates are conditional descriptive rates, **not** achievable
CAGRs or standalone regime portfolios.

Costs (0.15/0.30/0.95%), fixed 4% cash and extra-day delay are sensitivity scenarios,
not current Robinhood fee/candle verification. Tax rows are illustrative immediate
realized-gain payments at assumed 35%/20% rates with dollar-loss carry and no
wash-sale model, not actual liabilities. TradingView closes cannot support open
fills; the Binance subset is historically selected, not a full market basket.
All named-coin comparisons have selection bias and few independent cycles.

Relevant primary literature provides motivation, not validation of this hybrid:
[Liu and Tsyvinski, Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877)
documents a crypto momentum effect; [Faber's tactical allocation research](https://mebfaber.com/white-papers/)
studies a slow moving-average risk rule in other assets. Neither establishes that
this specific BTC/coin/Moneyline combination will outperform.
