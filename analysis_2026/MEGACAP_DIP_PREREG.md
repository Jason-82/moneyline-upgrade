# Buying mega-caps after a 25% drop: pre-registration

Written 2026-10-30, before any list was compiled or any return computed. Code: `analysis_2026/megacap_dip.py`.
Results: `analysis_2026/results_megacap_dip/`.

## Question

A rule heard from another investor: watch the "Magnificent 7" and buy any of them once it has fallen more than
25%. Does buying a mega-cap stock after a 25% drop, and holding it, beat simply holding the S&P 500?

**Survivorship problem.** The "Magnificent 7" name dates from 2023. The seven companies were picked because they
became the biggest winners, so testing today's seven on their past is look-ahead. The fair test asks what the
rule would have bought at the time, using the companies that were the largest then. Back then those included
Cisco, Lucent, WorldCom, General Electric, Citigroup and AIG.

## Data

- **Prices:** `data/universe_pit_all/`. These are point-in-time S&P 500 members from 1995 to 2026-10, including
  about 400 dead or acquired companies, with OHLC scaled to total return. Filter: `screener.data.quality_filter`
  with `keep_collapsed=True`, as in the split-delay study.
- **Benchmark:** SPY total return from the same folder.
- **Cash and Sharpe ratios:** T-bills from `sso_gold.base_daily` (`r_cash`).
- **Size lists:** the 20 largest S&P 500 members by market cap at each year-end from 1995 to 2025, compiled from
  public sources. No market-cap history can be downloaded in this environment. Construction is fixed here:
  - **Sources:** FinHacker's yearly "Largest 20 S&P 500 Companies by Market Cap" tables, found through web
    search, plus at least one independent source per year where available (Visual Capitalist, S&P, news
    archives). Every entry records its sources.
  - **Membership at the list date:** a company must have been an S&P 500 member on that date. Berkshire
    Hathaway joined in February 2010, so it does not count before then. Alphabet counts once, as GOOGL.
  - **Price check:** for each company in consecutive lists, the market-cap ratio must match the price ratio
    within ±25% in log terms. An exception is allowed for a documented share change such as a merger or
    spin-off.
  - **Omission check:** a candidate's market cap is carried forward or back from a year where it is known,
    using price ratios. A candidate that would rank inside the top 20 but is missing gets flagged.
  - **Resolving flags:** flags are resolved with further sources. If a value stays unresolved, the price-carried
    estimate from the nearest reliable year is used and marked as such.
  - **When a list applies:** the list as of the end of year Y defines the universe for trigger dates in calendar
    year Y+1. Names that are missing from the price data are listed and dropped (Enron, for example).
  - **Output:** the compiled lists, with sources, are saved as `results_megacap_dip/topcap_lists.csv`.
- **Tech flag:** a company counts as tech if it is in the GICS Information Technology sector (computers,
  software, semiconductors, communications equipment, IT services) or is an internet platform (Alphabet, Meta,
  Amazon, Netflix, Yahoo, AOL, eBay). Telecom carriers do not count.

## Rule (primary specification: the investor's rule as stated)

- **Drawdown:** DD = close / (highest close of the last 252 trading days, today included) − 1, on the
  total-return closes. A stock needs 252 bars before it can trigger.
- **Event:** stock i triggers on day t if:
  - it is in the universe on day t
  - DD crosses from above −25% to −25% or below on day t
  - it is armed

  A stock re-arms only after it makes a new 52-week high (DD = 0), so each decline gives at most one event. A
  crossing that happens while the stock is outside the universe gives no event.
- **Entry:** the next trading day's open.
- **Exit:** the first close at least 366 calendar days after entry, so the gain is long-term for tax. A series
  that ends earlier (a merger or delisting) exits at its last close.
- **Costs:** 0.03% per side.
- **Sample:** trigger dates from 1996-01-02 to the data end (2026-10-12). Lists for year-ends 1995 to 2025 apply
  to trigger years 1996 to 2026.

## Universes

| | universe | membership |
|---|---|---|
| U1 | top 10 by market cap | prior year-end list, ranks 1-10 |
| U2 | top 20 by market cap | prior year-end list, ranks 1-20 |
| U3 | every S&P 500 member | `members.csv` on the trigger date (start ≤ t ≤ end) |
| U4 (secondary) | tech names in the top 20 | prior year-end list, ranks 1-20, tech flag |
| U5 (secondary, biased) | today's Magnificent 7: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA | always, from each stock's 252nd bar; look-ahead by construction |
| U6 (secondary) | the 10 S&P 500 members with the highest median dollar volume (close × volume) over the prior year | recomputed each 1 January from the Johnbrick raw close and volume; a size proxy that needs no outside list |

## Primary test vehicle: the calendar-time dip book

- **Daily return:** equal weight across all open event positions. Each position earns its stock's total return:
  - entry day: close/open − 1, minus cost
  - exit day: the full day, minus cost
- **Days with no open position:** the book holds SPY.
- **Statistic:** the book's daily return minus SPY's, averaged over every day of the sample (zero on days with no
  open position) and annualised × 252.

This follows Jaffe and Mandelker's calendar-time portfolio method. It handles events that cluster in the same
crashes (2000-02, 2008-09, 2020, 2022) without treating them as independent.

## Primary tests and decision rule

**Tests:**
- T1 tests U1, T2 tests U2 and T3 tests U3.
- Each is one-sided: H0 is that the dip book's mean daily excess over SPY is ≤ 0.
- Inference uses a paired stationary bootstrap of the daily excess series: mean block 250 trading days, 10,000
  draws, null-centred. The three p values are Holm-adjusted.

**A universe "beats holding the S&P 500" only if all of the following hold:**
1. Holm-adjusted p < 0.05.
2. The excess is positive in both halves, 1996-2010 and 2011-2026.
3. The 10-slot portfolio (below) ends with more after-tax wealth than SPY bought and held.

Otherwise the verdict is "no evidence that the rule beats holding the index". Every test also reports its
minimum detectable effect at 80% power (2.49 × the bootstrap standard deviation).

## Secondary analyses (reported; none changes the verdict)

- **S1, dip timing vs owning the same stocks.** For each event, take 200 placebo entries on random days when the
  same stock was in the same universe, had 252 bars and had a full holding window. Report:
  - the event mean minus the placebo mean, with a bootstrap by calendar year
  - the universe held all the time (equal weight, rebalanced annually) vs SPY
- **S2, today's Magnificent 7 (U5).**
  - Full history: biased, and labelled so.
  - After the name was coined: trigger dates from 2023-04-01. Descriptive only.
- **S3, grid.**
  - Thresholds: 20, 25, 30, 40 and 50%.
  - Reference points: the 52-week high, the all-time high since the data start, and the 63-day high (a fast
    drop).
  - Holds: 63, 126 and 366 calendar days; 2 and 3 years; or until the stock regains the pre-drop high (at most 5
    years).
  - For each of U1, U2 and U3, a White reality check of the grid's dip books against SPY, using the same
    stationary bootstrap.
- **S4:** U4, tech names in the top 20.
- **S5:** U6, the dollar-volume top 10.
- **S6, index dips.**
  - The S&P 500 from 1928 to 2026 (`sso_gold.base_daily`) and QQQ from 1999 to 2026.
  - The 12-month return after a 25% drawdown from the 52-week high, compared with all 12-month windows.
- **S7, per-event table for U1 and U2.** Date, stock, the stock's 12-month return, SPY's 12-month return, and how
  much further it fell after the buy.
- **S8:** CAPM alpha and beta of each dip book against SPY (Newey-West, 12 monthly lags).
- **S9, the 10-slot portfolio** (what an investor would actually hold).
  - Start 100% in SPY. Each event takes 10% of current portfolio value, sold from SPY (first in, first out),
    and buys the stock. On exit, the proceeds go back to SPY.
  - With 10 positions open, new events are skipped and counted.
  - Tax: FIFO lots. Gains held more than a year are taxed at 20%, others at 35%. Losses offset gains within the
    year and carry forward. Dividends stay inside the total-return series and are taxed when sold, the same way
    for both sides. Everything is sold at the end.
  - SPY buy & hold pays 20% on its gain at the end.
  - Report CAGR, maximum drawdown and Sharpe, before and after tax, and the number of skipped events.
- **S10, event-level statistics.**
  - Mean and median 12-month excess over SPY, hit rate, the worst events, and the further drop after entry.
  - Inference uses a bootstrap clustered by calendar quarter.
- **S11:** halves and eras: 1996-2002, 2003-2009, 2010-2019, 2020-2026.

## Interpretation, fixed in advance

- **This is a test of timing.** A pass in T1 or T2 together with a near-zero S1 difference would mean the gain
  comes from owning those stocks at all, not from waiting for the drop.
- **Survivorship.** A strong S2 result (today's seven) with T1 and T2 failing would mean the hindsight result is
  survivorship, not a rule.
- **Low power.** Large-cap events are few and clustered. A non-significant result with a minimum detectable
  effect of several points a year is "not shown", not "shown not to work".
- **What the rule really is.** It moves money from the whole market into one fallen leader. Its risk (the
  further drop after entry, and drawdowns) is reported next to its return.
