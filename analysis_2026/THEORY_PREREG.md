# Ten strategies with a theoretical reason to work — pre-registration

Written 2026-10-14, before any of them was run. The code is in
`analysis_2026/theory_strategies.py` and the results go to `analysis_2026/results_theory/`.

## Why these ten

Everything tested so far points the same way:

- Timing the stock market mostly loses to buy & hold once you count costs and,
  especially, taxes.
- Crypto trends are real; most of their value is in avoiding crashes.
- Slower or noise-filtered rules beat fast ones on stocks.
- Published anomalies decay after publication.

So each candidate below meets three tests:

1. It has an economic or behavioural mechanism.
2. It has a peer-reviewed track record.
3. It suits an individual (ETFs, a few trades a year, or crypto).

They fall into four groups:

- volatility management: S1, S8
- slow trend and momentum: S2, S3, S5, S10
- defensive equity: S4
- calendar and structural: S6, S7, S9

## Common rules

- **Data:**
  - Ken French daily US market and T-bills, 1926-07 to 2026-08.
  - ETFs with dividends to 2026-09.
  - Point-in-time S&P 500 members, including failed companies, 2001-2026.
  - Binance daily bars including delisted coins, and USDT-M funding rates, to 2026-09.
- **No look-ahead.** Every signal uses data up to its own close. Market strategies built on
  Ken French data (returns only) trade at the next day's close, so a new position earns
  from the second day after the signal. ETF and crypto strategies trade at the next bar.
  Calendar rules (S6, S7) need no lag because the calendar is known in advance.
- **Costs per side, on the absolute change in weight:**
  - US market or ETFs: 0.02%
  - individual stocks: 0.03%
  - crypto: 0.10% (BTC/ETH) and 0.15% (other coins)
  - perpetual futures: 0.05%
- **Primary metric:** the Sharpe ratio on daily returns above T-bills, compared with the
  stated benchmark.
  - Significance: a stationary block bootstrap of the paired daily returns (mean block 250
    days, 2,000 draws); the one-sided p-value is the share of draws where the Sharpe
    gain ≤ 0.
  - S9's benchmark is T-bills, so its test is a t-test on daily excess returns.
- **Pass:** all three of
  1. Holm-adjusted p < 0.05 across the ten primary tests, AND
  2. the Sharpe gain is positive in the stated later or post-publication sub-period, AND
  3. after costs.
- **Also reported:**
  - CAGR, volatility, max drawdown and worst calendar year
  - turnover
  - after-tax CAGR: active strategies are taxed every year at 35% on their yearly growth,
    with losses carried forward; buy & hold is taxed once at 20% at the end. That is
    deliberately conservative for the strategies and generous to buy & hold.
  - the tax-advantaged (pre-tax) result

## The ten

### S1. Volatility-managed equity

Moreira & Muir 2017. **Mechanism:** volatility clusters and is predictable, but expected
returns do not rise with it, so cutting exposure when volatility is high raises
return per unit of risk.

- **Asset:** US market (Ken French) 1927-2026. SPY 1995-2026 as a replication.
- **Rule:**
  - At each month-end, weight = min(1, target / realised volatility of the last 21
    trading days).
  - The target is the expanding-window average of realised volatility up to that date (no
    look-ahead), so average exposure is about 1.
  - The rest earns T-bills.
- **Cap variant:** 1.5 with borrowing at T-bill + 0.5% (exploratory).
- **Benchmark:** buy & hold.
- **Sub-period for the pass:** 1976-2026.

### S2. Monthly trend filter (Faber 2007, "10-month SMA")

**Mechanism:** time-series momentum, plus avoiding the left tail of long bear markets. It
is slower than the daily indicator, so it has fewer whipsaws.

- **Asset:** US market total-return index 1927-2026, built from Ken French daily data. SPY
  1995-2026.
- **Rule:**
  - At each month-end, hold the market next month if the index is above the average of its
    last 10 month-end values.
  - Otherwise hold T-bills.
- **Benchmark:** buy & hold.
- **Sub-period:** 1976-2026, plus 2008-2026 (post-publication).

### S3. Dual momentum (Antonacci 2014, "GEM")

**Mechanism:** relative momentum across regions, plus an absolute-momentum crash filter.

- **Assets:** SPY, EFA, IEF; T-bills.
- **Rule:**
  - At each month-end, if SPY's 12-month return is above T-bills', hold whichever of SPY or
    EFA has the higher 12-month return.
  - Otherwise hold IEF.
- **Period:** 2003-2026.
- **Benchmark:** SPY buy & hold.
- **Sub-period:** 2015-2026 (post-publication).

### S4. Low-volatility stocks

Baker, Bradley & Wurgler 2011; Frazzini & Pedersen 2014. **Mechanism:** leverage
constraints and lottery preferences make investors overpay for volatile stocks, so
low-volatility stocks earn similar returns with less risk.

- **Universe:** point-in-time S&P 500 members including failed companies, 2001-2026.
- **Rule:**
  - At each quarter-end, rank members with at least 252 days of history by their
    252-day volatility.
  - Hold the lowest-volatility fifth, equal weight.
- **Benchmark:** equal weight of all eligible members, rebalanced the same way.
- **Sub-period:** 2014-2026.

### S5. Cross-sectional momentum (Jegadeesh & Titman 1993, 12-1)

**Mechanism:** under-reaction and slow diffusion of information.

- **Universe:** the same as S4.
- **Rule:** at each month-end, hold the top fifth by return over months t-12 to t-2, equal
  weight.
- **Benchmark:** equal weight of all eligible members.
- **Sub-period:** 2014-2026.
- **Exploratory:** a quarterly rebalance (lower turnover).

### S6. Turn of the month

Lakonishok & Smidt 1988; McConnell & Xu 2008. **Mechanism:** month-end pension, payroll and
fund flows.

- **Asset:** US market 1927-2026. SPY 1995-2026.
- **Rule:**
  - Hold the market over the last trading day of each month and the first 3 trading days
    of the next: enter at the close two trading days before month-end, exit at the close
    of the 3rd day.
  - Otherwise hold T-bills.
- **Benchmark:** buy & hold.
- **Sub-periods:** 1989-2026 (after the 1988 paper) and 2009-2026 (after McConnell & Xu).

### S7. Halloween / "Sell in May" (Bouman & Jacobsen 2002)

**Mechanism:** contested (vacations, risk aversion). It is included because it replicated
out of sample in many countries (Andrade et al. 2013).

- **Asset:** US market 1927-2026.
- **Rule:** hold the market November-April, T-bills May-October.
- **Benchmark:** buy & hold.
- **Sub-period:** 2003-2026 (post-publication).

### S8. Crypto trend + volatility targeting

**Mechanism:** this repo's robust crypto finding (crash avoidance) combined with S1's
volatility clustering, which is extreme in crypto.

- **Assets:** BTC and ETH as a 50/50 sleeve, Binance daily 2018-2026.
- **Rule:**
  - Weight = (indicator green) x min(1, target / 20-day realised volatility).
  - The target is the expanding median of realised volatility (at least 180 days).
  - Change the weight only when the indicator flips or the target weight moves by more
    than 0.10.
  - The weight is set at the daily close and earns the next day.
- **Benchmark:** the plain indicator (weight 1 while green), 50/50.
- **Sub-period:** 2022-2026.

### S9. Crypto cash-and-carry (funding-rate carry)

**Mechanism:** structural demand for leveraged longs makes perpetual futures trade rich, so
longs pay shorts a funding rate. Long spot plus short perpetual earns it with no price
exposure.

- **Assets:** BTC and ETH, 50/50, 2019-10 to 2026-09.
- **Return on notional:** the funding received, less costs:
  - opening and closing both legs
  - 0.05% a month to rebalance the hedge
- **Capital:** 1.25 x notional (spot paid in full plus 25% margin), so the return on
  capital is the return on notional divided by 1.25.
- **Variant:** in position only while the trailing 7-day funding is positive, otherwise
  T-bills.
- **Benchmark:** T-bills.
- **Pass:** mean excess return with t ≥ 2, Holm-adjusted, and positive in 2023-2026.
- **Caveats, reported not tested:** exchange counterparty risk (FTX 2022), and US retail
  access to perpetuals.

### S10. Crypto cross-sectional momentum (Liu, Tsyvinski & Wu 2022)

**Mechanism:** under-reaction and attention effects at 1-4 week horizons.

- **Universe:** each Monday, the top 30 coins by trailing 30-day median USDT volume that
  have at least 90 days of history (delisted coins included).
- **Rule:** hold the top fifth (6) by trailing 28-day return, equal weight, rebalanced
  weekly.
- **Benchmark:** equal weight of the 30.
- **Period:** 2019-2026.
- **Sub-period:** 2023-2026.

## Interpretation, fixed in advance

- **Expectation:** with ten tests and post-publication decay, maybe 2-4 pass.
- **A pass** means a reliable improvement over its benchmark. It is not automatically a
  reason to trade it: taxes and implementation are reported next to it.
- **A fail** is reported as plainly as a pass.
- **Exploratory variants** (caps, quarterly momentum, positive-funding-only, SPY
  replications) never decide a pass.
