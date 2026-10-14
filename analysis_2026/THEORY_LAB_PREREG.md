# Five complementary theory tests — declared before running, 2026-10-14

Base `93bff74`. The concurrent `THEORY_PREREG.md` defines another instance's S1-S10.
This study neither edits those definitions nor counts overlaps as independent
evidence. It tests five fixed, economically motivated retail adaptations. The
goal is higher net growth than the relevant passive benchmark with acceptable
drawdown, not merely a favorable indicator backtest or lower equity exposure.

## Candidates and theory

**C1 — Residual stock momentum.** Common market/style rallies can obscure persistent
firm-specific information. At each month-end t, fit FF3 plus intercept to the 36
monthly excess returns ending t-1. Remove the fitted factor component **without
subtracting the intercept**; rank the sum of adjusted returns over t-12 through
t-2 inclusive (11 months), divided by their sample SD. Hold the highest ceil(20%)
equally until the next monthly execution. This is a long-only, publication-lagged
adaptation motivated by Blitz/Huij/Martens (2011), not an exact paper replication.

**C2 — Gradual-information stock momentum.** A steady sequence of modest gains may
attract less attention than one spectacular jump. Rank eligible stocks by raw
12-1 return, retain the top ceil(20%), then hold the ceil(half) with lowest
`ID = sign(formation return) × (fraction negative daily returns − fraction positive)`
over that same t-12..t-2 window. Equal weight, monthly. Motivated by
Da/Gurun/Warachka (2014), adapted to long-only. C1/C2 share the underreaction family;
they are not two independent discoveries.

For both: S&P 500 membership observable at signal time, intervals [start,end),
36 complete prior months, complete formation daily history, actual usable OHLC,
no selection on future returns/survival. Exclude recycled STI. Compare with raw
12-1 top-quintile momentum, the same eligible universe equally weighted, and SPY.
Main 2001-2025 if data permits; development through2012, later2013-2025; 2026 through
available factor history separately. Record membership/price coverage each month.
Missing held prices make the strict result unidentified; separately show an
explicit terminal-zero-writeoff diagnostic. No false claim of a complete CRSP
or survivorship-free universe. Data revisions/factor vintages are retrospective.

**C3 — Global relative/absolute asset momentum.** Slow diffusion and persistent
capital flows can reward allocating across different return sources instead of
timing one coin. Fixed universe SPY/IWM/EFA/EEM/VNQ/GLD/IEF/TLT. At the last actual
session of each month, score = equal average of total returns over21/63/126/252
sessions. Hold the best3 with positive scores in three equal capital slots; any
unfilled slots cash. Monthly actual next-open trades, weights drift between trades.
Compare monthly equal weight of these8 and holding SPY. Main2007-2025, later2015-2025.
Neighbors top2/top4 are descriptive checks, never selection of a winner. Related
to S3/S10 and the momentum literature; no independent novelty claim.

**C4 — Capital-efficient equity/gold diversification.** Both growth risk and gold
can earn returns, and imperfect correlation may allow diversification without
halving the equity exposure. Hold50% actual SSO and50% GLD, rebalance at calendar
quarter-ends. SSO targets2× **daily** S&P returns; actual fund history embeds reset
drag, expenses and financing, and is never backfilled with2×SPY. This carries
roughly1× equity plus0.5× gold notional; it is not unlevered risk or alpha for free.
Compare SPY, quarterly50%SPY/50%GLD, and actual SSO alone. Main2007-2025, later2015-2025.
Neighbors40/60 and60/40 SSO/GLD are descriptive. This hypothesis follows portfolio
diversification arithmetic, not a claim that a paper validates this exact recipe.

**C5 — Low-turnover BTC/ETH leadership rotation.** Persistent adoption/attention
flows may reward holding the stronger major coin with fewer changes than ATR
flips. Fixed BTC/ETH universe as an explicitly narrow historical study. At each
UTC month-end, eligible if own90-day close return>0; rank eligible by63-day return.
Initially choose the best. Thereafter retain an eligible incumbent unless the
challenger's score exceeds it by0.05 (five percentage points); no eligible coin
means cash. Hold100% winner or cash, no intramonth stops. Monthly actual next-UTC-open
execution. Compare holdingBTC, monthly50/50BTC/ETH and original Moneyline in two
fixed50%slots. Main2019-2025, later2023-2025; 2026Jan-Sep separately. Neighbors
42/84-day ranking horizons, same90-day eligibility and0.05 hysteresis, descriptive.
Related to S10, but not evidence about small coins or the full historical market.

## Common accounting and evidence rules

- ETF data: direct Yahoo daily OHLC, distributions and adjustment factors, checked
  against the separately downloaded Johnbrick transfer. Both ultimately use Yahoo,
  not independent vendors. Total-return-adjusted open/close are synthetic DRIP units;
  they do not prove literal broker fills, dividend taxes or order feasibility.
- Crypto: official Binance full UTC candles with checksums,2018-01-01–2026-09-30;
  USDT treated as dollar quote unit. No staking or token income.
- Completed signals execute at the next open; one extra session/day is sensitivity.
  Last signal month is omitted if no full history. Do not forecast month-end from
  a truncated export. Last completed2026ETFcloseOct13; latest full monthSep30.
- Real shares/cash drift between rebalances. Sell before buy, solve fees into the
  available budget, charge actual traded notional and final liquidation. No free
  daily constant-weight rebalancing. No account leverage, shorting or live orders;
  C4's **fund** leverage is explicit. Zero cash return main; fixed4% sensitivity.
- ETF/stock costs:0.02%/0.03% per side primary,0.10% stress. Crypto0.15% primary,
  0.95% stress. These are scenarios, not verified current account-specific charges.
- Report calendar CAGR, terminal wealth, maximum DD including initial capital,
  realized volatility, Sharpe(zero cash benchmark), turnover, calendar-year returns,
  exposure, concentration and later-window results. Match dates for every control.
- Tax stress only:35% of positive annual net account growth with dollar-loss carry,
  paid annually, versus terminal20% positive gain for a passive hold; also show
  passive holdings under the same annual stress. This is NOT FIFO/dividend tax
  accounting or actual after-tax wealth. No deployment claim can rest on it.
- Five primary return hypotheses: C1/C2 versusSPY; C3 versusSPY; C4 versusSPY;
  C5 versusholdingBTC. Also require improvement over each named fair control
  where applicable; matching low exposure alone is not success.
- Predeclared return hurdle: primary pretax costed CAGR beats primary benchmark by
  at least1 percentage point/year; later-window growth edge positive; maximum DD
  no worse; direction survives higher cost and extra execution delay. For C4,
  decompose increased risk/exposure and compare to the nonleveraged control.
- Uncertainty: shared-date paired monthly log active returns, null-centered moving
  block bootstrap (12-month blocks,2,000draws), one-sided p with Holm correction
  across5 primary tests. Also report conditional confidence intervals. Missing
  strict primary histories yield UNIDENTIFIED, never a significance pass from a
  favorable diagnostic. Statistical/hurdle/tax outcomes are distinct columns.
- All this history has already been exposed or was selected retrospectively.
  Calendar splits are robustness checks, not untouched holdouts. Parameter
  neighbors are not added discoveries and do not rescue failed fixed rules.
- Document failures, unknowns and implementation limits as prominently as positives.
  A promising retrospective candidate advances only to future fixed-rule tracking.

Primary rationale sources:
- https://repub.eur.nl/pub/22252/ResidualMomentum-2011.pdf
- https://www.umitgurun.com/work/Frog.pdf
- https://www.aqr.com/insights/datasets/value-and-momentum-everywhere-factors-monthly
- https://www.proshares.com/our-etfs/leveraged-and-inverse/sso
- https://www.nber.org/papers/w24877

Existing S1-S10 are preserved. Separate review notes will identify inverse-volatility
versus inverse-variance adaptations, calendar timing ambiguity and collateral/
serial-correlation limits of funding carry without changing that preregistration.
