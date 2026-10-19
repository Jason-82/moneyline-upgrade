# Split mode: how long should the second half wait? Pre-registration

Written 2026-10-19, before any run. Code: `analysis_2026/split_delay.py`. Results:
`analysis_2026/results_split_delay/`.

## Question

The agentic sleeve's default mode is `split`:
- **Tranche 1:** 50% follows the old MoneyLine with N=1.
- **Tranche 2:** 50% follows it with N=5 confirmations, for both entries and exits.

Are 5 closes near-optimal for the second half? Or does a different wait do better, for example a longer wait to
sell than to buy?

Prior evidence, single-tranche delays (HANDOFF 5.15):
- **S&P 500 point-in-time basket:** Sharpe rose with N up to about 6, then flattened.
- **Crypto:** worse at every delay.

Splits with a varied second tranche have not been tested.

## Variants

- **Tranche 1** is always 50% at N=1.
- **Tranche 2** is 50% at (n_entry, n_exit), a separate number of consecutive closes beyond the trailing line for
  red→green and for green→red:
  - n_entry ∈ {1, 2, 3, 5, 8, 12}
  - n_exit ∈ {2, 3, 5, 8, 12, 20}

  That makes 36 variants. The benchmark `split(5,5)` is one of them.
- **References** (reported only):
  - `immediate`: 100% at N=1
  - `confirm5`: 100% at N=5
  - buy & hold

## Implementation

- **Signal:** `agentic.indicator.moneyline_confirmed`.
- **Engine:** `agentic.backtest.weights_returns`. The weight is decided at the close and filled at the next open,
  with cost × |Δweight| per side; cash earns T-bills.
  - Both are already tested equal to `moneyline_ref` and to `flip_delay.strat_returns`.
- **Costs per side:** stocks 0.03%, crypto 0.15% (0.95% as a sensitivity).

## Samples

| | sample | construction |
|---|---|---|
| P1 | S&P 500 point-in-time basket incl. failed companies, 2001-01..2026-09 | equal weight of each year's members, daily-rebalanced, each member on its own signal (as in `flip_delay.basket`) |
| P2 | High-volatility stocks, same universe and years | each year, the top fifth of members by the standard deviation of daily returns over the 252 trading days before 1 January (no look-ahead); same construction as P1 |
| P3 | Crypto top-20 incl. dead coins, 2019-01..2026-09 | each year's top-20 universe (`altcoins.tiers_for_year`), same construction |

**Secondary** (reported, never decides anything):
- 13 ETFs and 21 coins one by one
- held, annually rebalanced baskets
- crypto at 0.95%

## Primary metric and decision rule

**Metric:** Sharpe ratio of the basket's daily returns above T-bills.

**In-sample / out-of-sample split:**
- P1 and P2: IS 2001-2013, OOS 2014-2026-09.
- P3: IS 2019-2022, OOS 2023-2026-09.

**Procedure for each primary sample:**
1. Pick the variant with the highest IS Sharpe ("best").
2. On OOS, test the Sharpe gain of best over `split(5,5)`. Use a paired stationary bootstrap: mean block 250
   trading days (180 calendar days for crypto), 2,000 draws, null-centred, one-sided.
3. On the full sample, run a White reality check of the 36-variant grid against `split(5,5)`: stationary bootstrap,
   same blocks, 2,000 draws.

**The default changes only if all of these hold for a sample:**
- OOS Sharpe gain > 0 with p < 0.05, after Holm across the three primary samples
- reality-check p < 0.10
- the best variant's gain is positive in both halves of the OOS period
- its OOS max drawdown is no more than 5 points worse than `split(5,5)`

Otherwise `split(5,5)` stays.

If P1 or P2 passes, the stock default changes. If P3 passes, the crypto default changes.

## Interpretation, fixed in advance

- **A flat Sharpe surface around (5,5)** means the exact wait does not matter much. Keep 5, the simplest.
- **A ridge along longer exits with short entries** would favour an asymmetric tranche 2. That needs the decision
  rule above.
- **Selection is only from the IS period.** OOS results for other variants are shown, but they are not used to
  pick.
- **This is about risk-adjusted return.** None of these variants is expected to beat buy & hold after tax on stocks
  (HANDOFF 5.15, 5.19).
