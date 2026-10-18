# Pre-registration: replicating a Twitter "AI breakdown" of a Bollinger-breakout crypto trader

Written 2026-10-18, before any Bollinger, breakout or grid strategy return was computed on any of the
data below. The research and data notes are in `analysis_2026/research_notes/Bollinger breakout
replication/`:
- `rules_and_evidence.md`: the operational rules, the grid mechanics, the evidence and a
  reconciliation of the reported statistics;
- `data_inventory.md`: the data.

Code: `analysis_2026/bb_replica.py`, with data from `analysis_2026/fetch_bb_data.py`. Results go to
`analysis_2026/results_bb/`.

## The question

The user saw a post (image: `research_notes/Bollinger breakout replication/source_summary.png`) and
asked: "can you figure out their exact strategy from this summary, replicate it and test it on all of
our assets?"

The post claims 16 months of trading, 1,462 bots, $10.7B volume, 4.3x on starting capital, a 48.7%
hit rate (51.7% with the grid), and average wins 1.4x average losses. It describes Bollinger Band
breakouts near local and all-time highs, cut when the trend breaks below the Bollinger midline, plus a
grid "while waiting", and gives 15 rules.

The post cannot be traced, so every statistic in it is unverified and doubly selected: by the AI
summariser and by whoever chose to post it.

**What "exact strategy" can and cannot mean here.** A summary of outcomes does not identify a rule set.
- Rules 1-5 and 7-10 are decision rules and can be coded.
- Rules 6 and 11-15 are patterns an AI mined from about 70 weeks of one trader's results, e.g. "trades
  held over a week won 75%", or the weekday and hour-of-day rules. They are tested as hypotheses against
  placebo versions, not assumed.
- The study codes one literal reading (R0), varies every ambiguous choice in a fixed sensitivity grid,
  and reports which variants are *consistent* with the post's statistics. Consistency with the
  statistics is not evidence of an edge: with 14 rows and many filters, some row will match by chance.

## Priors (stated now)

- **The trend core probably has a positive but modest edge in crypto, concentrated in 2020-21.**
  Bollinger-rule evidence is weak; crypto trend following is positive. This repo found Donchian
  breakouts about equal to its indicator and carried by 2020-21 (HANDOFF 5.14).
- **3-5x leverage probably lowers risk-adjusted and long-run results.** HANDOFF 5.14 found Kelly ≤ 1.85
  and 85-100% blow-ups at 3-5x on a trend signal.
- **The mined timing rules (12-15) and rule 6 are probably noise.**
- **The grid is short volatility.** Its expected net is about zero before fees and negative after.
- **The 16-month window most likely ran 2025-06 to 2026-10.** Over it BTC returned −23% and most liquid
  coins −30% to −80% (ZEC 27x), so a long-only 4.3x would require ZEC, several caught up-legs, or shorts.

---

## Data

- **Crypto.**
  - Binance hourly klines, spot (from 2017) and USD-M perpetual (from 2020-01), for 40+ coins, to
    2026-10-16. Built and validated by `fetch_bb_data.py`; see `data_inventory.md`.
  - Funding rates at their actual intervals (to 2026-09-30; October 2026 has none in the archive and
    is charged at the last month's median rate).
  - One-minute perpetual klines for BTC, ETH, SOL, BNB, XRP and DOGE, 2024-07-01..2026-10-16, for the
    grid overlays.
  - Mark-price hourly klines (`markPriceKlines`) are fetched for liquidation checks where available; the
    last-price low is used otherwise (conservative).
- **Stocks and ETFs (daily only; no historical intraday bars exist in the repo):**
  - point-in-time S&P 500 members including dead names, 1996-2026 (`data/universe_pit_all/` with
    `data/raw_pit/` OHLC);
  - the ETFs in `data/raw_pit/`;
  - the user's tickers TSLA, COIN, HOOD and CRCL plus SPY, QQQ and IWM (split-adjusted OHLC from
    `data/raw_pit/` or `data/universe_recent_raw/`).

## Windows

- **Full:** crypto 2020-01-01..2026-10-16 (perpetual era; spot hours stand in where a perpetual did not
  yet exist). Stocks 1996-01..2026-10.
- **Replication window W16:** 2025-06-17..2026-10-16, the most likely 16 months.
- **Alternative window W16b:** 2024-06-30..2025-10-31, ending at the BTC high.
- **Halves (crypto):** 2020-01..2022-12 and 2023-01..2026-10.

---

## The literal replication R0 (crypto)

| element | R0 |
|---|---|
| Vehicle | Binance USDT-M perpetual; isolated margin per position |
| Universe | BTC, ETH and SOL, one slot each; sleeve = sizing equity / 3 |
| Signal (daily bar, 00:00 UTC) | C_t > UB_t of BB(20, 2) (population σ), **and** [C_t ≥ 0.95 × the max high of the last 60 days including t, **or** C_t ≥ 0.90 × ATH_t (highest high in the Binance history to t)]. Long only. |
| Entry window | The first allowed window after the signal close: US open − 3.5 h (10:00 UTC in EDT / 11:00 UTC in EST) or US open + 30 min (14:00 / 15:00 UTC). Never in the 90 min before the US open. No entries on a New York Friday or Saturday. The latest completed daily bar must still satisfy the signal. Fill at that hour's open plus taker fee and slippage. |
| Size | Max notional M = L × sleeve, L = 3. First tranche M/3. |
| Adds (rules 2-3) | +M/3 when an hourly close ≥ 1.02 × the first entry price, and +M/3 at ≥ 1.05 ×. Each fills at the next hourly open. Never add below the average entry. |
| Hard stop (rule 10) | S = SMA20_t − 1.0 × ATR14_t at the signal. Resting; fills at S or at the gap open if the price opens through it. Covers all tranches. |
| Take-profit (rule 10) | TP = entry₁ + 3 × (entry₁ − S); sells 50% of the position, resting (rule 8: two pieces at most). |
| Trend exit (rules 7, 9) | Daily close < SMA20. Exit 100% at the next "closing" window, US open + 3.5 h (17:00 / 18:00 UTC; rule 14). |
| Rule 6 (literal) | The trend exit is ignored for 72 h after the first entry while the position is in profit. |
| Rule 15 | Trend-exit signals from Saturday and Sunday closes are deferred to Monday's close. |
| Liquidation | Liquidation price ≈ average entry × (1 − 1/L + mmr), mmr from Binance's lowest tier. Checked on the hourly mark-price low (last-price low if mark is missing). Leverage per trade is capped so the stop sits at least 2 points above liquidation. A liquidated tranche loses its margin plus a 1% liquidation fee. |
| Sizing equity (rule 11) | Equity at the start of each month; frozen for the next month after a month above +25%. |
| Costs | Taker 0.05% + slippage 0.02% (BTC/ETH) or 0.07% (others) per side. Funding on notional at each funding print while held. Idle margin earns nothing in the primary run (T-bill version reported). |
| Grid | None in R0 (see the overlays below). |

**Fill conventions.**
- Every decision uses only data available at its time.
- A daily signal is known only after the 00:00 UTC close, so the earliest fill is the next allowed
  window.
- In an hourly bar touching both the stop and the TP, the stop fills first.
- `trades == 0` hours are exchange outages: no fills.

## Sensitivity grid (every row reported; none selected)

- **S1 "R0-core":** rules 12-15 off and rule 6 off; entry at the 01:00 UTC hourly open after the signal;
  trend exit at the 01:00 UTC open after the exit close.
- **S2:** L = 1 (account-level exposure 1/9 per slot at entry, 1/3 at full size).
- **S3:** L = 5 isolated; L = 3 cross margin.
- **S4:** no pyramiding (full M at entry).
- **S5:** adds at +2% / +5% return on margin.
- **S6:** BB(20, 2.5); BB(50, 2); BB(10, 1.9); BB(50, 2.1); BB(10, 1.5); BB(50, 2.5).
- **S7:** near-high filter off; 20-day high within 2%; 365-day high within 10%; ATH within 10% only.
- **S8:** 4-hour signal and exit bars.
- **S9:** stop at the lower band; stop at SMA20 − 2.5 × ATR.
- **S10:** one-piece exits: all at TP; or no TP, all on the midline.
- **S11:** symmetric long/short (short a close below the lower band near a 60-day low; cover on a close
  above the midline).
- **S12:** universe = point-in-time top 3 and top 6 coins by trailing 90-day perpetual quote volume.
- **S13:** squeeze pre-condition: BandWidth within 10% of its 125-day low at some point in the prior 10
  days.
- **S14:** entries only in the open + 30 min window.
- **S15:** rule 6 as a binding 72-hour minimum hold for all positions; rule 15 off.

## Grid overlays (one-minute bars; BTC, ETH, SOL, BNB, XRP and DOGE; 2024-07..2026-10)

- **G-A "waiting grid" (primary overlay).**
  - **When:** while a slot is flat and its coin is within 5% of the 60-day high but at or below the
    upper band.
  - **What:** a neutral geometric perpetual grid over [lower band, upper band] at deployment, spacing
    max(0.5%, 4 × the round-trip maker fee), margin = the first-tranche budget, 3x.
  - **Ends when:** R0 enters (the grid is closed at taker cost at that hour's open); a daily close falls
    below the lower band; or after 14 days (re-centred).
  - **Fills:** within a one-minute bar the price path is assumed to be O→L→H→C if the close is nearer
    the high, else O→H→L→C. Funding is charged on net inventory.
- **G-B (exploratory):** each R0 tranche run as a long-mode grid over [S, TP], 20 levels.
- **G-0 (benchmark, exploratory):** an always-on neutral grid, ±10%, re-centred weekly.

## Stocks and ETFs ("all of our assets")

- **Rules:** the same daily signal (BB(20, 2) breakout near the 60-day high or ATH), stop, 3R
  take-profit on half, and midline exit.
- **Fills:** entries and exits at the next session's open (the closest available proxy for the post's
  10:00 ET entry and 13:00 ET exit; stated as a deviation).
- **Leverage:** 1x (primary) and 2x (Reg-T, exploratory).
- **Not applied:** pyramiding stays in, but there are no weekend rules beyond skipping Friday entries,
  and no grid.
- **Costs:** HANDOFF section 4 (stocks: 5 bp per side plus spread proxy for ETFs/S&P names).
- **Universes:**
  - point-in-time S&P 500 members (each name its own slot, equal risk budget, at most 20 concurrent
    positions);
  - the ETFs;
  - the user's seven tickers, reported individually.

---

## Hypotheses and pass rules

**Units and statistics.**
- **Trade return** = net P&L of the whole position (all tranches) divided by its maximum notional M.
- **Trade-level tests:** pooled mean with SE clustered by entry month (CGM one-way).
- **Portfolio-level tests:** daily returns of the sleeve or portfolio; Sharpe differences use a
  month-block bootstrap (10,000 resamples).

**Multiplicity.** One Holm family covers H1-H10, HS1 and HS2 (12 tests), at 5% one-sided. H11 and H12
are descriptive.

| id | hypothesis (as the claim that the rule helps) | PASS requires |
|---|---|---|
| **H1 core edge** | S1 at L = 1 has a positive mean net trade return on BTC/ETH/SOL over the full sample | Holm p < 0.05 for mean > 0 (month-clustered t); mean > 0 in both halves; mean > 0 pooled over the 40-coin set |
| **H2 vs benchmarks** | S1 at L = 1 (sleeve equity curve) beats both equal-weight 1x buy-and-hold of BTC/ETH/SOL and the repo's daily indicator (`moneyline_ref`) on the same coins, on Sharpe | Holm p < 0.05 for both Sharpe differences (block bootstrap) |
| **H3 pyramiding** | R0's 1/3 + adds beats S4 (full size at entry) on mean net return per unit of maximum notional | Holm p < 0.05 (paired by signal, month-clustered) |
| **H4 confirmation** | Close-confirmed entry (S1) beats intrabar band-touch entry (enter when the hourly price first exceeds the *prior* day's upper band) per trade | Holm p < 0.05 |
| **H5 near-high filter** | Within the S7 "filter off" run, breakouts that meet R0's near-high condition beat those that do not, per trade | Holm p < 0.05 |
| **H6 hour rules (13-14)** | R0's entry and exit windows beat S1's 01:00 UTC timing, holding everything else as in S1 | Holm p < 0.05 for the paired difference **and** R0's windows rank in the top 5% of 200 placebo window pairs (random entry hour and exit hour, same rule structure) |
| **H7 weekday rule (12)** | Excluding Friday and Saturday entries beats no exclusion | Holm p < 0.05 **and** the Fri+Sat exclusion ranks first among the 7 consecutive-day-pair exclusions |
| **H8 hold and Monday rules (6, 15)** | S15 (72-h minimum hold) and the Monday deferral each improve per-trade net return vs off | Holm p < 0.05 for the combined rule set vs off, **and** better than 95% of 200 placebo versions (random minimum hold 1-120 h; a random weekday deferral) |
| **H9 leverage (rule 4)** | R0 at L = 3 has a higher long-run growth rate (mean log daily return of the sleeve) than at L = 1 | Holm p < 0.05 (block bootstrap). Also reported: liquidations, worst drawdown and L = 5 |
| **H10 grid overlay** | R0 + G-A has a higher net P&L than R0 alone over 2024-07..2026-10 on BTC/ETH/SOL | Holm p < 0.05 for mean daily P&L difference > 0 (block bootstrap by week) |
| **HS1 stocks** | The stock version at 1x on point-in-time S&P 500 members has a positive mean net trade return and beats the equal-weight buy-and-hold of the same members on Sharpe | Holm p < 0.05 for both; mean > 0 in both halves (1996-2010, 2011-2026) |
| **HS2 ETFs** | The same on the ETFs | Holm p < 0.05 for both |

**Verdicts.** Each test is reported as PASS, FAIL (point estimate ≤ 0), or "positive but not
significant". For H1, H2 and HS1-HS2, the one-sided 95% upper bound of the effect is also reported.

**Headline replication (descriptive; the answer to "does their strategy work on our assets?").** For R0
(full rules, 3x) and for S1 (core, 1x), on each window and asset group, report:
- CAGR, multiple, Sharpe, max drawdown, liquidations and trade count;
- hit rate, average win / average loss, share of trades held > 7 days that won, and the share of
  profit from trades held ≥ 3 days.
Compare each with buy-and-hold and the repo indicator on the same coins and windows.

## H11 consistency check (descriptive; no tuning)

On W16 and W16b, report for R0 and every sensitivity row:
- the trade count (vs 1,462 "bots");
- hit rate (vs 48.7%), average win / average loss (vs 1.4) and multiple (vs 4.3x);
- the share of > 7-day trades that won (vs 75%) and the profit share of ≥ 3-day trades (vs > 80%).

List the rows within ±5 points on hit rate and ±0.3 on win/loss, and report those rows' results outside
W16 (2020-01..2025-06). The rows that "match" the post are flagged as a fitted subset whose
out-of-window results are the only evidence about them.

## H12 shorts (exploratory)

S11 vs R0 on W16 and on the full sample.

## Controls (run before primary results are read)

- **Engine known answer.** On a synthetic random walk with no drift, S1's mean trade return before
  costs is about zero, and after costs it is about minus the costs. On a synthetic series with
  persistent trends, it is positive.
- **Look-ahead check.** Shifting every price after time t (×1.5) leaves all decisions up to t unchanged.
- **Liquidation check.** A hand-built path through the liquidation price liquidates exactly once,
  with the stated loss.
- **Indicator cross-check.** The repo's `moneyline_ref` benchmark reproduces HANDOFF 5.14's BTC 1x
  multiple order of magnitude on the same window.

## Reporting rules

- Every pre-registered row and test is reported.
- Results including ZEC are always shown next to results without it.
- Any change after results are seen is a listed deviation, with the reason.
- **Vehicle note.** US residents generally cannot use Binance perpetuals or grid bots; the closest US
  options are Coinbase's CFTC-regulated BTC and ETH perpetual-style futures and spot grid apps. Robinhood
  spot crypto at about 0.95% a side makes pyramids and grids uneconomic. The write-up states what a US
  user could actually run.
