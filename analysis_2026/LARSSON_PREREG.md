# Larsson Line (EMA 32 / EMA 58 crossover) on long histories — pre-registration

Written 2026-10-16, before any long-history run. The code goes in `analysis_2026/larsson.py`
and the results in `analysis_2026/results_larsson/`.

## What the indicator is

The user's TradingView **Larsson Line** plots two lines. On fresh exports (private) they
are exactly EMA(32) and EMA(58) of the close, with median error 0 on BTC, ETH and SOL.
The chart colours green or red; the colour rule is not yet confirmed by the user.

- **Primary rule (LARSSON):** green while EMA32 > EMA58, red otherwise. Long while green,
  T-bills while red.
- **Sensitivity (LARSSON-PRICE):**
  - green once the close is above both lines
  - red once it is below both
  - unchanged in between

Already seen, on 18 user assets over 1-12 years (private): the Larsson Line and the new
MoneyLine were roughly tied, with no significant difference. That small sample motivates
this test. It is not part of it.

## Conventions (as in the flip-delay study)

- **Prices:**
  - signals on the chart price (split-adjusted, not dividend-adjusted where available)
  - returns on total return
- **Execution:**
  - Assets with opens: signal at close t, trade at the next open (`flip_delay.strat_returns`).
  - Close-only series (the S&P 500 index before 1962, the pre-1928 Dow): trade at the
    next close.
- **Costs per side:**
  - ETFs 0.02%
  - stocks 0.03%
  - S&P index 0.02%
  - BTC/ETH 0.10%
  - other coins 0.15%
  - Robinhood-like 0.95% as a crypto sensitivity
- **Out of the market:** T-bills.
- **After-tax figures:** every year's growth taxed at 35% with losses carried forward.
  Buy & hold is shown pre-tax and taxed once at 20%. These are illustrative.
- **Warm-up:** 120 bars before any result.

## Comparators

- buy & hold
- the old MoneyLine as replicated (`moneyline_ref`, ATR10×2): immediate (N=1) and with
  the 5-close delay (N=5)
- a 1x 200-day SMA filter
- The new (October 2026) MoneyLine cannot be computed outside TradingView exports, so it
  is not in this test.

## Primary tests (Holm across five)

All are on the **Sharpe gain** (daily returns above T-bills):

- **Method:** paired stationary block bootstrap; mean block 250 trading days (180 calendar
  days for crypto); 2,000 draws; null-centred; one-sided.
- **Pass:** Holm-adjusted p < 0.05 AND the gain is positive in both halves of the sample.

| | comparison | sample |
|---|---|---|
| P1 | LARSSON vs buy & hold | S&P 500 total return, 1929-01..2026-09 (price-index signal) |
| P2 | LARSSON basket vs equal-weight buy & hold basket | point-in-time S&P 500 members incl. failed companies, 2001..2026-09 |
| P3 | LARSSON basket vs equal-weight buy & hold basket | crypto top-20 universe each year incl. dead coins, 2019..2026-09 |
| P4 | LARSSON basket vs old MoneyLine N=5 basket (the better old version on stocks) | P2's sample |
| P5 | LARSSON basket vs old MoneyLine N=1 basket (the better old version on crypto) | P3's sample |

## Secondary (reported, never decides a pass)

- **Per-asset results:**
  - 13 ETFs (2005-2026) and 21 large coins (2018-2026)
  - median Sharpe and CAGR change vs buy & hold and vs the old MoneyLine
  - sign tests
- **The S&P 500 index:**
  - by decade
  - pre-1972 vs 1972-2026
  - the pre-1928 Dow (1886-1927) as an out-of-sample check
  - the old MoneyLine from 1963, when daily highs and lows begin
- **Neighbouring EMA pairs:** (20, 50), (26, 52), (40, 80), (50, 100), (50, 200), to show
  whether 32/58 is special.
- **The LARSSON-PRICE rule.**
- **Crypto at 0.95% per side.**

## Interpretation, fixed in advance

- **Expectation from this repo's evidence** (slow trend filters on stocks):
  - lower drawdowns
  - lower CAGR than buy & hold, especially after tax
  - roughly unchanged Sharpe
  - On crypto, trend filters have mostly helped through crash avoidance.
- **A pass on P1-P3** means a reliable risk-adjusted improvement, not a higher after-tax
  return.
- **P4/P5** say whether the Larsson Line beats the old MoneyLine. They cannot speak for
  the new one.
