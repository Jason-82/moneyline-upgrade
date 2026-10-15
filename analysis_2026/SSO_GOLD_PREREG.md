# 2x S&P 500 + gold (50% SSO / 50% GLD) and variations — pre-registration

Written 2026-10-15, before any simulation earlier than SSO's 2006 inception. The code goes
in `analysis_2026/sso_gold.py` and the results in `analysis_2026/results_sso_gold/`.

## What was already seen (disclosed, so it cannot count as a test)

- **The other instance's C4** (`codex/theory-lab`, `THEORY_LAB_RESULTS.md`): quarterly 50%
  SSO / 50% GLD.
  - 2007-2025: CAGR 14.33% vs SPY 10.63%, max drawdown −52% vs −55%.
  - Adjusted bootstrap p 0.077, so it failed that study's significance test.
- **My replication:** monthly total returns, rebalanced at quarter-end closes. CAGR 14.18%,
  with SPY 10.66% and 50/50 SPY/GLD 11.05%.
- **Exposure regression, 2007-2025 (monthly, excess over T-bills):**
  C4 = −1.2%/yr (t −4.3) + 1.00 × S&P + 0.50 × gold, R² 0.996.
  Gold returned 10.1%/yr and T-bills 1.5%/yr over that window.

## Theory being tested

50% in a 2x daily fund is about 1x S&P exposure on half the capital, financed at a
short-term rate. So, approximately:

    C4 − S&P  ≈  0.5 × (gold − T-bill)  −  0.5 × (SSO fee + financing spread)  −  0.5 × gold-fund fee
              +  a small rebalancing term (≈ σ_gold²/8 ≈ 0.3%/yr)  ±  drift and daily-reset effects

- **Prediction:** C4 has no edge of its own. Over S&P, it earns half of gold's return over
  T-bills, minus about 0.6-1.0%/yr of costs.
- **So it beats the S&P only when gold beats T-bills by more than about 1.5-2%/yr.** Gold
  has no cash flow, and its long-run real return is near that of T-bills (Erb & Harvey
  2013). If that holds, the edge was a property of 2007-2025, not of the strategy.
- **Expected by era:** positive in 1972-80 and 2001-2025; strongly negative in 1980-2001,
  when gold fell while T-bills paid 5-15%.

Two other ideas have a real mechanism, and the user's indicator suggests a third:

1. **Leverage plus a trend filter** (Gayed & Bilello 2016). Volatility drag on a daily-reset
   fund concentrates in high-volatility bear markets, which a trend filter tends to sit out.
2. **Trend filter on gold.** Time-series momentum is documented in gold (Moskowitz, Ooi &
   Pedersen 2012).
3. **The Moneyline indicator with the 5-bar confirmation delay** (section 5.15) brought the
   indicator's stock Sharpe up to buy & hold's, with half the drawdown. A timing rule
   whose Sharpe is no lower but whose volatility is much lower can be levered, so 2x while
   confirmed green could beat buy & hold.

## Data (fixed now)

- **S&P 500 total return, daily:**
  - SteelCerberus/us-market-data `Adjusted Close`, 1928-01-03..2025-12-19. It is S&P 500
    with dividends, and identical to SPY total return after 1995: daily correlation 1.0000,
    zero mean difference. It already carries SPY's 0.0945%/yr fee.
  - Spliced to SPY total return (Johnbrick123 `adj_close`) through 2026-10-12.
  - For synthetic leveraged funds, SPY's fee is added back to get the index.
- **Cash:** SteelCerberus `Risk Free Return` (3-month T-bill; 1-month before 1954).
- **Leveraged-fund financing:** SteelCerberus `Swap Rate`, plus a spread s.
  - s is fitted once on actual SSO total return (qlib, 2006-06-21..2021-09-16), with the fee
    fixed at SSO's 0.89%/yr.
  - Synthetic 2x daily return = 2·r_index − 1·(swap + s)·days/360 − 0.89%·days/365. UPRO-style
    3x uses ×3, ×2 and 0.91%.
- **Gold: the earliest-starting daily or month-end USD series that passes validation.**
  - Validation over 2004-11..2026, where the series must:
    - correlate with GLD at ≥ 0.98 on monthly returns
    - beat GLD by 0.2-0.7%/yr, consistent with GLD's 0.40% fee
    - have no unexplained gaps or stale runs
  - If several qualify, use the longest.
  - Before GLD exists (2004-11-18), deduct a 0.40%/yr fund fee. After that, use GLD
    itself.
  - **Fallback if no such series exists before 2004:** the World Bank monthly average (from
    1960). Every pre-2004 result is then labelled approximate, because averaging smooths
    volatility and shifts returns by about half a month.
- **Long Treasuries (variants only):** the best validated long-history series found:
  - a total-return index if one exists, otherwise built from constant-maturity yields
  - validated against TLT and IEF from 2002
  - described in `results_sso_gold/data_sources.md`
- **Actual funds (replication track, 2006-07..2026-09):**
  - SSO: qlib total return to 2021-09-16, then the other instance's Yahoo total-return
    monthly path. That path matched qlib to 0.05%/yr before 2021.
  - GLD and SPY: Johnbrick total return.
  - Others (UPRO, TMF, NTSX, GDE) where they exist.
- **The S&P index's daily high/low (P5 only):**
  - S&P index OHLC (vijinho/sp500, from Yahoo ^GSPC) with real high/low from 1962
  - SPY split-adjusted OHLC after 2018
  - the signal comes from the price index; returns from the total-return index

## Execution conventions

- **Static-weight portfolios (C4 and weight or diversifier variants):** daily synthetic
  returns compounded to month-ends. Rebalance to target at the close of each calendar
  quarter-end month, with drift in between.
- **Daily-signal rules (P3-P5):** the signal is computed at close t, and the position
  changes at close t+1. A change of signal earns from day t+2.
- **Costs per side, on traded notional:** 0.02% for ETFs (0.03% for leveraged funds).
- **Stress:**
  - costs ×5
  - financing spread s + 0.5%/yr
  - one extra day of execution lag for the daily rules
- **Cash and idle sleeves earn T-bills.**

## Primary tests (five; Holm across them)

All are measured against S&P 500 total-return buy & hold.

- **Statistic:** the mean monthly active log return (strategy − S&P).
- **p-value:** a stationary block bootstrap with mean block 36 months, 5,000 draws, centred
  on the null. The one-sided p is the share of null draws ≥ the observed mean. The long
  block is deliberate: gold and rate regimes last years.
- **Pass:** all of
  1. Holm-adjusted p < 0.05
  2. active return > 0 in each half of the test period
  3. active return still > 0 under the three stresses

| | strategy | period |
|---|---|---|
| P1 | **C4, synthetic:** 50% 2x-daily S&P + 50% gold, quarterly rebalance | 1972-01..2006-06. Out of sample: before SSO existed, and before the window that produced the candidate. |
| P2 | **C4, synthetic** | Full: 1972-01..2026-09 |
| P3 | **Leverage + trend (Gayed-Bilello):** 2x daily S&P while the S&P price index closes above its 200-day average, T-bills otherwise | 1929-01..2026-09. The 2016-2026 post-publication slice is also reported. |
| P4 | **C4 + trend on both sleeves:** the equity sleeve follows P3's rule. The gold sleeve holds gold while gold is above its 200-day average (its 10-month average if only monthly data exist), T-bills otherwise. Sleeves are rebalanced 50/50 quarterly. | 1972-01..2026-09 |
| P5 | **Moneyline with the 5-bar delay, levered:** 2x daily S&P while the S&P index's Moneyline is confirmed green (N = 5 consecutive closes beyond the line, as in `flip_delay.py`), T-bills otherwise | 1963-01..2026-09 |

- **Why 1972:** the first full year after the gold window closed in August 1971. 1975-01
  is the first date US citizens could own gold, and that start is reported as a
  sensitivity.

## Secondary (reported, never decides a pass)

- **Exposure decomposition** for every strategy: monthly alpha on S&P, gold and bond excess
  returns, with Newey-West t.
- **Tax:**
  - Taxable account with lot-level accounting (FIFO):
    - short-term gains 35%
    - long-term gains 20%
    - gold-fund long-term gains 28% (collectibles)
    - T-bill interest 35%
    - dividends 20%
  - Losses offset gains and carry forward.
  - Also a tax-deferred account (pre-tax).
  - Buy & hold S&P pays 20% on dividends yearly and 20% on the final gain.
- **Risk:**
  - max drawdown and worst year
  - crisis windows: 1973-74, 1980-82, 1987, 2000-02, 2008, 2020, 2022
  - rolling 10-year win rates against the S&P
  - start-date sensitivity
- **Gold valuation (Erb & Harvey):** the log real gold price against the next 10 years'
  real gold return, and today's reading. Overlapping windows are reported with that caveat.
- **Variant grid, all also scored on the actual-fund track where funds exist:**
  - SSO weight 0-100% in steps of 10
  - leverage forms:
    - 1x (S&P/gold)
    - 1.5x
    - 2x (SSO)
    - 3x (UPRO, 1/3 UPRO + 2/3 gold)
    - GDE-style 90/90 (futures financed at T-bill + 0.2%, fee 0.20%)
  - diversifier: gold, long Treasuries, intermediate Treasuries, cash, or gold + bonds
  - rebalance: monthly, quarterly, annual, or a 5-point band
  - trend filters: 10-month average, 200-day average, or Moneyline N=1/5 on the equity
    sleeve; 10-month average on gold
  - inverse-volatility weights
- **Data-snooping check:** a White Reality Check (block bootstrap of the maximum mean active
  return) across the whole grid against S&P buy & hold. It reports how likely the best
  variant's edge is under chance.

## Interpretation, fixed in advance

- **If P1 fails while P2 is driven by 1972-80 and 2001-2025,** C4 is a bet on gold beating
  cash, not a strategy edge. Its expected advantage is then about
  0.5 × E[gold − T-bill] − about 0.8%/yr.
- **A pass is necessary but not sufficient for a recommendation.** Tax, the drawdown
  profile and implementation (leveraged-fund decay, fund risk) are reported next to it.
- **The variant grid is descriptive.** The best variant never replaces a failed primary.
  The reality check states how much the search alone could explain.
