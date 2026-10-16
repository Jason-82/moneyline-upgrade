# Backtest: does a country's policy direction predict its stock returns? (repo test, 2026-10-16)

The repo's own pre-registered test of the thesis.
- Pre-registration: `analysis_2026/FREEDOM_PREREG.md`, commit b100171, written before any results.
- Code: `analysis_2026/freedom_countries.py`.
- Results: `analysis_2026/results_freedom/` (summary.txt, primary.csv, exploratory.csv, etf_tests.csv,
  timing_ladder.csv, cohorts.csv, current_ranking.csv).
- An adversarial audit with skeptic verification confirmed 34 findings. None changed a verdict; the
  numbers below are after the audit fixes.

## Design

**Returns.** Jensen-Kelly-Pedersen (JKP) country stock-market returns.
- All listed stocks, value-weighted, in USD, monthly, 1986-2025.
- The universe at each formation date (end of October, 1997-2025) is every country with at least
  20 stocks. That is about 50 countries in 1997 and about 75 in 2025.
- Venezuela and Zimbabwe are excluded because their exchange rates are unreliable.
- Russia is marked −100% in March 2022, the outcome for foreign holders.

**Signals.** Each uses only data public at formation, respecting publication lags:

| id | signal |
|---|---|
| S1 | 5-year change in the Fraser Economic Freedom of the World score (data year ≤ Y−2) |
| S2 | the Fraser level |
| S3 | 5-year change in the Heritage "tax burden" score (top tax rates plus tax/GDP; higher = lighter) |
| S4 | 5-year change in manufacturing value added as % of GDP (World Bank WDI, data year Y−2) |
| S5 | 5-year growth in electricity generation per person (Our World in Data) |
| S6 | S1 within Western countries only |
| S7 | composite z-score of S1, S3, S4 and S5 |

**Portfolio.** Long the top third, short the bottom third, equal-weighted, held 12 months.

**Pass rule** (all four required):
- mean > 0;
- Newey-West t ≥ 2;
- positive in both halves;
- survives Holm correction across the seven tests.

## Pre-registered results: all seven FAIL

| signal | top minus bottom third, %/yr | t | one-sided 95% upper bound, %/yr |
|---|---|---|---|
| S1 change in economic freedom | −1.62 | −0.92 | ≤ 1.3 |
| S2 level of economic freedom | −1.51 | −0.73 | ≤ 1.9 |
| S3 change in tax burden ("lower taxes") | −0.20 | −0.13 | ≤ 2.25 |
| S4 change in manufacturing share | +2.00 | +1.12 | ≤ 4.9 |
| S5 growth in electricity per person | −0.74 | −0.38 | ≤ 2.4 |
| S6 S1 among Western countries only | −0.38 | −0.26 | ≤ 2.0 |
| S7 composite | +1.11 | +0.63 | ≤ 4.0 |

**Second check (Fama-MacBeth regressions controlling for country momentum and long-term reversal).**
No signal coefficient reaches |t| 1.4. Country momentum, i.e. the prior 12-month return, is the only
robust predictor (t about 3).

**Power.** The test could reliably (80% power) detect only premiums of about 4-6% per year.
- Large edges are ruled out for freedom changes, freedom levels, tax-burden changes, electricity
  growth and the Western-only test (upper bounds 1.3-2.4%/yr).
- Smaller edges of 1-3% a year can be neither confirmed nor excluded.
- S4 and S7 are not ruled out at 4-5% a year.

**Influential year.** The first cohort, formed October 1997 and held through the Asian and Russian
crises, has the biggest influence on S1, S2, S4 and S7.
- In practice that cohort was long emerging-market "reformers" and short developed markets.
- Without it: S1 is −0.4%/yr (t −0.24, so no edge); S2 is −3.1%/yr (t −1.8, freer countries did
  somewhat worse); S4 is +3.3%/yr; S7 is +2.4%/yr.
- No signal's sign flips when any single cohort is dropped.

## Robustness (exploratory; none changes a verdict)

**S4 (rising manufacturing share) is the only signal positive in nearly all variants, but it is fragile:**
- It disappears in an MSCI-ACWI-only universe (+1.1%, t 0.5), in markets with 50+ stocks (+1.5, t 0.7)
  and under value weights. It lives mostly in small and frontier markets.
- A 1-year World Bank lag gives +3.1%/yr (t 1.9).
- On iShares country ETFs, 2001-2025, it is +3.1%/yr (t 2.1, Holm p 0.10 across six ETF tests). On
  the same country-years, the JKP returns give the same number, so this is a sample-period effect,
  not an independent confirmation.
- The World Bank data are today's revised vintage, not what was known at the time. Some series have
  rebasing breaks; with the breaks blanked, S4 is +1.8%/yr.
- S4 also picks up changes in sector mix (pharma, petrochemicals, GDP shrinking in crises), not only
  policy-driven build-out.

**S3 within developed markets** is −2.7%/yr (t −2.3): countries whose measured tax burden lightened did
*worse*. It is fragile (concentrated in 2000-2011) and is one of 40+ exploratory rows. Not evidence that
tax cuts hurt, but no support for the thesis's tax leg.

**Other variants, all flat:**
- Region-neutral sorts (within developed and within emerging separately): no |t| above 1.25.
- Heritage overall score: −0.7 to −1.8 depending on how its methodology breaks are handled.
- The Fraser chain-linked panel and the 2019 release.
- Longer holds of 3 and 5 years.
- Data repairs (Ireland, Canada and Malaysia data errors; multiple-exchange-rate regimes dropped).
- Long-only tilt (top third minus all): S1 −0.5, S2 −0.7, S3 +0.4, S4 +1.0, S7 +0.8 %/yr, none
  significant.

## Positive control: the relation is real but priced before the data are published

This was done after the fact (post hoc). Countries are sorted on the 1-year change in Fraser freedom
in data year d. The table shows top-minus-bottom-third returns in each later year:

| return year | %/yr | t | note |
|---|---|---|---|
| d (same year) | +3.65 | 2.7 | |
| d+1 | +4.82 | 2.9 | still before Fraser publishes, around Sep of d+2 |
| d+2 | +0.68 | 0.4 | publication year |
| d+3 | −2.15 | −1.5 | |

So improving freedom does go with better returns, but the market moves while the change happens,
before an investor could see it in the index. Two other signals behave differently:
- Heritage tax-burden changes show no relation at any timing.
- Manufacturing-share changes: +5.4 (t 3.3) in d+1, which straddles the WDI publication around mid
  d+1, and +3.4 (t 1.8) in d+2, a weak tradable remnant.

## What the data say about the premise (Western countries losing economic freedom)

**Fraser 2018→2023:**
- The West fell −0.13 points against −0.18 for the rest of the world.
- All of the West's decline is in the COVID data year: −0.25 in 2019→20, then +0.11 in 2020→23. The
  rest of the world was −0.05 after 2020, on inflation.
- Every Western country fell in 2019→20.
- After 2020, Norway, Sweden, Australia, New Zealand and Iceland kept falling. Greece, the
  Netherlands, Luxembourg, Spain, Belgium, Italy and Finland recovered most.

**Where the West falls behind:**
- Fiscal: government consumption and top marginal tax rates (Fraser areas 1A and 1D) and Heritage
  government spending (West −4.5 vs non-West 0.0, 2021→2026).
- Electricity build-out: 11 Western countries sit in the bottom third on S5, 4 in the top.
- Manufacturing: 5 in the bottom third, 3 in the top.

**Where the premise does not hold:**
- Heritage tax-burden scores improved for the West (+0.5 vs −0.1, 2021→2026).
- On the Fraser level, 14 Western countries are in the top third and none in the bottom.

**The 2026 Fraser report (2024 data)** is not in our mirror. The research notes say it shows Canada
falling from 9th to 18th.

**The global S1 sort leans against the West:** 271 of 591 Western country-years were in the short third
and 54 in the long third. The USA was in the short third in 20 of 29 years. Yet the tests aimed
squarely at the premise were flat: S6 −0.4%/yr, and S1 within developed markets +0.35%/yr.

## Current ranking (descriptive only: the composite failed its test, so this is not a buy list)

Top of the composite S7 as of October 2026:
- Saudi Arabia, UAE, Denmark, Greece, Zambia, Vietnam, Brazil, Oman, Sweden, Kuwait.
- 5 of the top 11 are Gulf states.

Bottom:
- Romania, Sri Lanka, Turkey, Bulgaria, Trinidad, Estonia, Argentina, Czechia, New Zealand, UK,
  Hong Kong.

The policy and macro data end in 2023/2024, before 2025-26 events (Argentina's 2024-26 reforms, the
2026 energy shock). See current_ranking.csv.

## Caveats

- **Data come from third-party mirrors** of Fraser, Heritage, JKP, WDI and OWID. Each mirror was
  cross-checked where possible; details are in data_sources.md.
- **Fraser scores are revised between editions.** The main runs use the 2025 release, with the 2019
  release as a vintage check.
- **JKP covers all listed stocks**, not an investable index. Investability was checked on iShares
  ETFs.
- **The test covers only gradual, published policy drift** in markets that stayed listed. It cannot
  test avoiding catastrophes:
  - Venezuela and Zimbabwe are excluded.
  - Russia 2022 is the only collapse in the sample.
  - Months when a market was closed are dropped rather than marked down (e.g. Greece in
    July-August 2015).
- **Returns are gross, pre-tax, equal-weighted long-short.** A US investor could only build a
  long-only ETF tilt, which was small and not significant.
