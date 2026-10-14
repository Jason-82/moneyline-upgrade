# Crypto signal comparison — 2026-10-14

Six fixed candidates were implemented and compared on actual daily Binance spot
prices with causal historical liquidity selection, actual next-UTC-day opens,
four cost assumptions and a dividend-adjusted passive SPY benchmark. The
unchanged original indicator remains the baseline. **All results are exploratory;
no live strategy or stock/coin whitelist is approved.**

## What the comparison suggests

Stronger price confirmation is worth advancing as a research hypothesis. The
`breakout20` candidate requires original green plus a close strictly above the
previous 20 closes, and retains the original red exit. It is not a guarantee of
a valid breakout, and it did not help every coin. Waiting for two green closes
was less consistent. Widening the stop reduced transactions but generally gave
back too much profit. The paper-style ensemble and volatility sizing improved
drawdown measures while frequently reducing growth.

The original strategy's big-winner mechanism does appear in one regime. In the
2020–2022 development basket, VET, ADA and BNB generated about 81% of net profit.
The baseline won only about 46% of completed entry lots; mean winning returns
were about +69% and mean losing returns about −12%. This is evidence about this
historical sample, not an expectation that future trades will have that payoff.

## Development basket, 2020–2022

These results are pretax with **10 bps (0.10%) per side**. The past-only end-2019
formation selected ten qualifying coins. Each began with one of twenty equal
capital slots; the ten unused slots remained in cash. Held positions could grow
within their own slots, so the portfolio did not stay at 50% exposure forever.

| Candidate | Annualized growth | Maximum drawdown |
| --- | ---: | ---: |
| Original Moneyline | 101.56% | −46.84% |
| Two green closes before entry | 99.73% | −47.01% |
| Green plus prior-20-close breakout | 104.07% | −31.74% |
| Original entries, wider 3-ATR exit | 72.58% | −66.35% |
| Fixed-size Donchian ensemble | 48.50% | −33.35% |
| Donchian ensemble, 25% volatility sizing | 9.61% | −6.43% |
| Holding the same selected basket | 45.24% | −76.10% |
| SPY total-return buy-and-hold, 3 bps per side | 7.41% | See aggregate results |

The baseline's ending value was $819,202 on $100,000 initial capital. Independent
checks reconciled it from the equity path, actual simulated trade cash flows,
and the ten per-coin sleeves plus $50,000 unallocated cash. Its large CAGR is
not a percent-versus-fraction error. It is still a historically exposed,
venue-specific simulation with substantial drawdown.

The volatility-sized model's mean exposure was only 5.07%, versus 37.80% for
Moneyline. Its lower drawdown cannot be presented as an equal-exposure return
victory. We did not borrow to reproduce the paper's 200% exposure cap.

## Later single-coin diagnostics, 2023–2025

Pretax annualized growth, again at 10 bps per crypto side:

| Model | BTC | ETH | SOL |
| --- | ---: | ---: | ---: |
| Original Moneyline | 36.59% | 15.30% | 66.17% |
| Two-close confirmation | 35.90% | 9.75% | 79.18% |
| Twenty-close breakout confirmation | 40.67% | 10.89% | 116.08% |
| Wider 3-ATR exit | 42.05% | 17.97% | 75.83% |
| Fixed-size Donchian ensemble | 30.79% | 13.90% | 69.78% |
| Volatility-sized Donchian ensemble | 17.41% | 8.21% | 19.72% |
| Holding that coin | 74.20% | 35.34% | 131.90% |

SPY's corresponding pretax CAGR was **22.63%**. Thus the original rule beat SPY
on BTC and SOL in this period, but trailed holding each of these three coins.
Breakout confirmation helped BTC and SOL but hurt ETH. On SOL it reduced maximum
drawdown from 65.89% to 45.00%, while holding SOL returned more with a 59.77%
drawdown. A strategy can trade off growth and drawdown; beating SPY alone does
not identify skill beyond the underlying crypto exposure.

Among the 34 selected later histories with identified comparisons, breakout
confirmation improved CAGR on 23 and improved both CAGR and drawdown on 20.
Its median paired improvement was 3.93 percentage points of CAGR and 4.35
points of drawdown. These are **conditional descriptive statistics**, not a
survivorship-free basket result or a significance test. Wider exits improved
CAGR on only seven of those histories; median CAGR fell 15.50 points and
drawdown worsened 10.95 points.

## Costs, taxes and unavailable baskets

At 95 bps per crypto side, the development baseline's pretax CAGR fell to 85.26%
and breakout confirmation to 89.71%. The later BTC baseline fell from 36.59% to
18.55%, below SPY's 22.63%; ETH fell from 15.30% to 0.64%. SOL breakout still
returned 94.02%, but holding SOL returned 130.59%. Cost sensitivity is material;
the scenarios are not verified account-specific Robinhood execution prices.

Optional tax rows are an illustrative single-account FIFO sensitivity with
stock-like wash-sale deferral and assumed 35%/20% rates. They do not establish
actual crypto tax liability or an after-tax SPY comparison. USDT is treated as
a constant quote unit, and stablecoin dollar-basis changes are not modeled.

Both full later baskets, and the continuous basket accounts, remain
**unidentified**. MATIC/FTM and other histories require migration or delisting
reconciliation; LUNA has a pre-formation gap. They are not removed because their
future data is inconvenient. The end-2019 lower-liquidity group was empty and
remains all cash. Lower liquidity is not a verified small-market-cap category.

## Inputs, checks and reproduction

The historical catalog contains 757 USDT pairs. The normalized bundle contains
41 histories, 89,020 accepted full UTC-day candles, 50 dated memberships and
1,032 source receipts. All normalized checksums were verified. The SPY source
covers every actual NYSE session in 2019–2025 and reconciles its recorded
dividends to the provider's adjustment factors.

The initial real-data run exposed a one-ULP full-sale quantity error on SHIB.
Final review also exposed a repeated-fractional-sale quantity mismatch in two
optional VET tax rows. Numerical accounting was corrected with regression tests;
indicator parameters, selection rules, costs and source inputs were retained.
Earlier frozen attempts and their receipts are preserved with the exact inputs.

All **265 regression tests** pass, including the existing stock and shadow tests;
source compilation also succeeds. The crypto-only canonical quantity option
retains the stock ledger's default behavior. No real account or trade was used.

See the [declared experiment](CRYPTO_EXPERIMENT.md),
[data acquisition](CRYPTO_DATA.md), and the published aggregate results in
`research_results/crypto_comparison_summary.csv` and
`research_results/crypto_comparison_receipt.json`.

```bash
python3 -m crypto_research.run freeze \
  --config config/crypto_experiment.json \
  --dataset private/crypto_data/binance_snapshots \
  --benchmark private/crypto_data/benchmark \
  --output private/crypto_runs/frozen_release_canonical.json
python3 -m crypto_research.run run \
  --dataset private/crypto_data/binance_snapshots \
  --benchmark private/crypto_data/benchmark \
  --frozen private/crypto_runs/frozen_release_canonical.json \
  --output private/crypto_runs/comparison_release
```

The source data and full run receipts are retained privately; raw prices and
source responses are excluded from this public repository. Settings, source
bytes, benchmark and implementation are checked against the frozen artifact.
The later historical period is not an independent untouched holdout.

The next research candidate is breakout confirmation alongside the unchanged
baseline in a prospective comparison. Before a whole-basket conclusion, resolve
dated token migrations and actual tradability. Before funded execution, validate
Robinhood-specific candles, costs, timing and account/budget authorization.
