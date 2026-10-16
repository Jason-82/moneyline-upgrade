# Pre-registration: does a country's policy direction predict its stock returns?

Written 2026-10-16, before any return statistic of these signals was computed. Only data coverage was
checked: country counts, years available, and file structure. The code is
`analysis_2026/freedom_countries.py`; data comes from `python3 -m analysis_2026.fetch_freedom_data`.

## The user's thesis

Some Western countries are moving toward higher taxes, de-industrialization and less economic
freedom. Others are moving toward lower taxes, more energy and industrial build-out, and more market
freedom. Overweighting the second group should therefore pay.

The test asks whether that direction, **as an investor could have measured it at the time**,
predicted the country's USD stock returns over the next year.

## What the literature leads us to expect (stated now, for honesty)

These priors come from `research_notes/Economic freedom investment thesis/literature_freedom_returns.md`.

- **Levels of economic freedom:** no return edge, but lower volatility.
- **Changes in freedom:** studies find positive effects, but they measure the change over the same
  period as the return, so it is unknowable in advance. Once publication lags and momentum are
  respected, most of the effect is expected to vanish.
- **GDP growth:** across countries it is uncorrelated with stock returns, or negatively correlated.
- **Industrialization:** no study links it to equity returns. China grew fast while its stock
  market gave poor returns.

## Data

**Returns.** Jensen-Kelly-Pedersen (JKP) country market returns: value-weighted, monthly, in USD and
in excess of the US T-bill, 1986-2025 (`jkp_mkt_vw.csv`).
- These cover all listed stocks, not an investable index.
- In a long-short portfolio the T-bill cancels.
- Investability is checked separately on iShares country ETFs (dividend-adjusted, 1996-2026).

**The universe at each formation date** (end of October of year Y) contains every JKP country that has:
- at least 20 stocks that month;
- 12 months of prior returns;
- the signal available.

Two adjustments, decided in advance:
- Venezuela and Zimbabwe are excluded, because their USD conversions are unreliable (multiple or
  parallel exchange rates).
- Russia: foreign holders were wiped out in 2022, as Russia ETFs were halted and liquidated near
  zero. So Russia's return for March 2022 is set to −100%, and Russia leaves the universe afterwards.
  A robustness run uses the JKP returns as given.

## Signals

Each signal uses only data public by the end of October of the formation year Y. Higher always
means more pro-market.

| id | signal | source and lag |
|---|---|---|
| S1 | **change in economic freedom**: Fraser EFW summary index ("all areas", 2025 release). Annualized change × 5 from d0 to d, where d = latest data year ≤ Y−2 and d0 = latest data year ≤ d−5. | Fraser publishes data year t around September of t+2. Data are 5-yearly before 2000. |
| S2 | **level of economic freedom**: EFW summary at d | same |
| S3 | **change in tax burden**: Heritage "Tax Burden" score (higher = lower taxes), index year Y minus index year Y−5 | Heritage index year Y is published in January-March of Y |
| S4 | **industrialization**: change in manufacturing value added as % of GDP from d−5 to d, d = Y−2 | World Bank WDI |
| S5 | **energy build-out**: log change in electricity generation per person from d−5 to d, d = Y−2 | Our World in Data energy (Ember / Energy Institute) |
| S6 | **S1 within the West only**: USA, CAN, GBR, IRL, FRA, DEU, ITA, ESP, PRT, GRC, NLD, BEL, LUX, AUT, CHE, DNK, NOR, SWE, FIN, ISL, AUS, NZL | as S1 |
| S7 | **composite**: average of the cross-sectional z-scores of S1, S3, S4 and S5 (at least two must be available) | as above |

Two further rules:
- **Pre-2000 Fraser data:** data before 2000 are 5-yearly. Formations 1997-2001 therefore use 1995
  data, with the change measured from 1990.
- **Heritage names to ISO codes:** Heritage names are mapped to ISO codes through Fraser's country
  names plus a fixed manual crosswalk.

## Portfolios and statistics

**Portfolio.**
- At each formation date, countries are sorted on the signal.
- Long the top third, short the bottom third, each equal-weighted.
- Hold November Y to October Y+1, then rebalance.
- This gives a monthly long-short return series, plus the top third minus the equal-weighted
  universe as a long-only tilt.

**Primary statistic (tests H1-H7, one per signal S1-S7).** The mean monthly long-short return,
annualized, with a Newey-West t-statistic (12 lags).

A test **PASSES** only if all three hold:
1. The annualized mean is above 0 and the t-statistic is at least 2.0.
2. The mean is above 0 in both halves of formation years: 1997-2010 and 2011-2025 (or the signal's
   own span split at its middle year).
3. The one-sided p-value survives Holm correction across the seven tests at 5%.

**Secondary check (Hxb, does not decide the verdict).** Fama-MacBeth monthly cross-sectional
regressions of country returns on the signal's z-score. Controls:
- the prior 12-month return (country momentum);
- the prior 60-month return (long-term reversal, standing in for valuation, which these data don't
  include).

The signal coefficient's Newey-West t-statistic is reported.

**Exploratory, reported but not deciding verdicts:**
- splits by developed vs emerging market;
- the long-only tilt;
- iShares ETF versions;
- Heritage overall score changes;
- the 2019 Fraser release instead of 2025, for formations up to 2019;
- the chain-linked Fraser series;
- holding periods of 3 and 5 years;
- the current ranking of countries on every signal, for the "where now" question.
