# Pre-registration: replicating a Twitter "AI breakdown" of a Bollinger-breakout crypto trader

**Status: FROZEN 2026-10-18.** Written before any Bollinger, breakout or grid strategy return was computed on
any of the data below. A draft (commit ae4d591) was reviewed adversarially from three lenses (statistics,
simulation fidelity, relevance to the user), which made 54 proposals. Every proposal was adopted, merged or
declined with a reason; see the revision log at the end. The reviewers' quantitative claims come from
synthetic paths and coverage counts only.

Research and data notes are in `analysis_2026/research_notes/Bollinger breakout replication/`:
- `rules_and_evidence.md`: the operational rules, the grid mechanics, the evidence and a reconciliation of
  the reported statistics;
- `data_inventory.md`: the data.

Code: `analysis_2026/bb_replica.py`, with data from `analysis_2026/fetch_bb_data.py`. Results go to
`analysis_2026/results_bb/`.

## The question

The user saw a post (image: `research_notes/Bollinger breakout replication/source_summary.png`) and asked:
"can you figure out their exact strategy from this summary, replicate it and test it on all of our assets?"

The post claims 16 months of trading, 1,462 bots, $10.7B volume, 4.3x on starting capital, a 48.7% hit rate
(51.7% with the grid), and average wins 1.4x average losses. It describes Bollinger Band breakouts near local
and all-time highs, cut when the trend breaks below the Bollinger midline, plus a grid "while waiting", and
gives 15 rules.

The post cannot be traced, so every statistic in it is unverified and doubly selected: by the AI summariser and
by whoever chose to post it.

**What "exact strategy" can and cannot mean here.** A summary of outcomes does not identify a rule set.
- Rules 1-5 and 7-10 are decision rules and can be coded.
- Rules 6 and 11-15 are patterns an AI mined from about 70 weeks of one trader's results, e.g. "trades held
  over a week won 75%", or the weekday and hour-of-day rules. They are tested as hypotheses against placebo
  versions, not assumed.
- The study codes one literal reading (R0) and varies every ambiguous choice in a fixed sensitivity grid.
  - H11 reports which rows are consistent with all of the post's statistics jointly.
  - H11b measures, in a labelled fit, how many rule sets match equally well, against random-entry decoys.
- Consistency with the statistics is not evidence of an edge. With dozens of variants on two windows, some
  will match by chance; H11 reports how many are expected to.

## Priors (stated now)

- **The trend core probably has a positive but modest edge in crypto, concentrated in 2020-21.**
  Bollinger-rule evidence is weak; crypto trend following is positive. This repo found Donchian breakouts about
  equal to its indicator and carried by 2020-21 (HANDOFF 5.14).
- **3-5x leverage probably lowers risk-adjusted and long-run results.** HANDOFF 5.14 found Kelly ≤ 1.85 and
  85-100% blow-ups at 3-5x on a trend signal. That prior applied L to a whole sub-account, so it transfers only
  partly to R0, whose account-level exposure is 1/9 to 1 per slot.
- **The mined timing rules (12-15) and rule 6 are probably noise.**
- **The grid is short volatility.** Its expected net is about zero before fees and negative after.
- **The 16-month window most likely ran 2025-06 to 2026-10.** Over it BTC returned −23% and most liquid coins
  −30% to −80% (ZEC 27x), so a long-only 4.3x would require ZEC, several caught up-legs, or shorts.
- **R0 will trade far less often than the post.** R0 on BTC/ETH/SOL daily bars should produce about 10-30
  positions in W16, against about 490 positions or 1,462 tranches implied by the post.

---

## Data

- **Crypto (Binance; `data/bbreplica/`, see `data_inventory.md`).**
  - Hourly klines, spot (from 2017-08) and USD-M perpetual (from 2020-01), for 40 coins plus LUNA2, to
    2026-10-16.
  - Funding rates at their actual intervals, to 2026-09-30.
  - One-minute perpetual klines for BTC, ETH, SOL, BNB, XRP and DOGE, 2024-07-01..2026-10-16.
  - Mark-price hourly klines (`h1_mark/`, section 1.1 of the inventory), trimmed to each contract's traded
    window.
  - For S12's all-contract ranking: the archive's daily USD-M klines for every USDT-margined perpetual. They
    are fetched before any run; a contract that enters a monthly top 10 and is outside the 40 has its hourly,
    mark and funding files fetched too.
  - `data/tv_full/` (close-only TradingView exports with ATR(14); the repo's primary crypto set) for the TV
    cross-check.
- **Stocks and ETFs (daily only; the repo has no historical intraday stock bars):**
  - point-in-time S&P 500 members including dead names, 1996-2026 (`data/universe_pit_all/`);
  - the 14 ETFs of `regime_switch.ETFS` (SPY QQQ IWM DIA EFA EEM TLT IEF TIP LQD HYG GLD SLV VNQ), the repo's
    ETF set in HANDOFF 5.17 and 5.19, each from its first date in `data/raw_pit/` plus 60 sessions of
    history. The other non-member tickers in `raw_pit` (overlapping index funds and recycled tickers) are not
    used;
  - the user's tickers TSLA, COIN, HOOD (`data/raw_pit/`) and CRCL (`data/universe_recent_raw/`, from
    2025-06-05), plus SPY, QQQ and IWM.
- **Cash:** the 3-month T-bill from `regime_switch.rf_annual_pct()` (daily series to 2025-12-19, then the
  repo's annual table).
- **Robinhood listing (for the RH route):** the read-only catalog call `get_currency_pairs` on 2026-10-18.
  Of the 40 coins, 24 are tradable on Robinhood today: AAVE ADA ALGO ATOM AVAX AXS BCH BNB BTC DOGE DOT ETC ETH
  HBAR LINK LTC NEAR SHIB SOL UNI XLM XRP XTZ ZEC. (POL is listed but untradable.) This is today's list, so it
  carries hindsight.

## Windows

- **Full:** crypto 2020-01-01..2026-10-16 (perpetual era; spot hours stand in where a perpetual did not yet
  exist).
- **Replication window W16:** 2025-06-17..2026-10-16, the most likely 16 months.
- **Alternative window W16b:** 2024-06-30..2025-10-31, ending at the BTC high.
- **Halves (crypto):** 2020-01..2022-12 and 2023-01..2026-10.
- **Pre-perpetual block** (L = 1 rows only; reported beside H1 and H2, not a pass condition): Binance spot
  2017-08-17..2019-12-31 for every coin listed then, at spot costs (0.10% + slippage), no funding.
- **Stocks and ETFs:** primary sample 2001-01-01..2026-10-16, halves 2001-2013 and 2014-2026. 1996-2000 is
  reported separately, outside every pass rule: about 157 of 1,227 member symbols have no price file, mostly
  names that left before 2001, so those years cover only about 80% of member-days.
- **Window edges.**
  - Each window starts flat with equity 1, with indicators computed from the full history before it.
  - A trade belongs to the window or half in which entry₁ filled.
  - A trade still open at a window's end is marked at the last hourly close. It counts in P&L and the
    multiple, but not in hit rate, win/loss or the holding-time shares.
  - A coin's sleeve is cash until its first tradable bar plus the warm-up below.

---

## The literal replication R0 (crypto)

| element | R0 |
|---|---|
| Vehicle | Binance USDT-M perpetual; isolated margin, one position per coin (one-way mode) |
| Universe | BTC, ETH and SOL, one slot each; sleeve = sizing equity / 3 |
| Signal (daily bar, 00:00 UTC) | A fresh close above the upper band: C_t > UB_t of BB(20, 2) (population σ), with C_{t−1} ≤ UB_{t−1}, **and** [C_t ≥ 0.95 × the max high of the last 60 days including t, **or** C_t ≥ 0.90 × ATH_t]. Long only. Signals are computed on Binance spot daily bars where spot trades and on the perpetual otherwise (e.g. XMR after 2024-02-20); orders, stops and liquidation use the perpetual. No signal before 60 completed daily bars; the ATH branch (and S7's 365-day and ATH-only rows) needs 365. ATH_t is the highest high in the Binance history to t and is labelled Binance-only. Signals that qualify only through the ATH branch are counted. |
| Entry window | The first allowed window after the signal close: 06:00 New York (US open − 3.5 h; 10:00 UTC in EDT / 11:00 UTC in EST) or 10:00 New York (open + 30 min; 14:00 / 15:00 UTC), converted per calendar date with the America/New_York tz database. The windows, and the 13:00 New York exit window, apply every day, including weekends and NYSE holidays. Never in the 90 min before the US open. No first-tranche fill on a New York-date Friday or Saturday; a blocked signal waits for the next allowed window. The latest completed daily bar must still satisfy the signal. Fill at that hour's open plus taker fee and slippage. If that hour has zero trades, the next window is used; if it opens at or below S, the entry is skipped. |
| Size (rule 1) | Max notional M = L × sleeve, L = 3. First tranche M/3. |
| Adds (rules 2-3) | +M/3 when an hourly close ≥ 1.02 × entry₁, and +M/3 when an hourly close ≥ 1.05 × entry₁ (both at once if one close clears 1.05). Each fills at the next hourly open with trades > 0, at any hour and on any weekday (rules 12-13 govern opening only). An add is cancelled if that open is below the average entry, if a trend exit is pending, or once the TP has filled. In an hour whose open fills an add and which then reaches S, the add fills first and the stop then closes everything. |
| Re-entry (rule 3) | After any full exit, a new position needs a fresh signal: a daily close above the band preceded by a close at or below it. |
| Hard stop (rule 10) | S = SMA20 − 1.0 × ATR14 of the latest completed daily bar at the entry window (the signal bar unless the entry was deferred). A stop-market order on last price, covering all tranches. Fill: the hour's open if it opens at or below S, else S. For BTC, ETH, SOL, BNB, XRP and DOGE from 2024-07-01, the hour is resolved on 1-minute bars (which also settles stop-vs-TP order), and the fill is min(S, close of the first 1-minute bar whose low ≤ S). Elsewhere, in an hour whose low is more than 5% below S, the fill is 0.99 × S. Taker fee and slippage are then charged. If the fill is below the liquidation price, the position is liquidated instead. Results with every stop filled at S are reported beside the primary, and trades stopped on 2025-10-10/11 are listed. |
| Take-profit (rule 10) | TP = entry₁ + 3 × (entry₁ − S); a resting limit selling 50% of the position (rule 8: two pieces at most). |
| Trend exit (rules 7, 9) | Daily close < SMA20. Exit 100% at the next 13:00 New York window (17:00 / 18:00 UTC; rule 14). Stop and TP stay active while the exit waits. |
| Rule 6 (literal) | A midline exit signal within 72 h of entry₁ is not acted on if the mark at that daily close is at or above the average entry; it is re-checked at each later close. Stop and TP stay active. Expected to bind rarely; the number of suppressed exits is reported. |
| Rule 15 | Midline exit signals from the daily bars ending Sunday 00:00 and Monday 00:00 UTC (the Saturday and Sunday closes) are not acted on. The midline is re-checked at Monday's close (Tuesday 00:00 UTC); if price is still below, the exit fills in Tuesday's 13:00 New York window. Stop and TP stay active. |
| Liquidation | Each tranche posts margin = its notional / L. Liquidation price = average entry × (1 − (isolated margin − fees paid − funding paid) / position notional + mmr), recomputed after every fill and funding print; mmr from Binance's lowest tier. The account starts at $10,000 so that positions stay in that tier. Checked on the hourly mark-price low, falling back to the last-price low for hours missing from the mark file and for spot-only hours. L is capped per trade so that S sits at least 2 points above the liquidation price of the full position after both adds (average entry 1.0233 × entry₁). A liquidated position loses its isolated margin and nothing more; the clearance fee comes out of that margin. Because S sits above liquidation, R0 liquidations are near zero by construction, so a stress row in which every stop fails between 2025-10-10 20:00 and 23:00 UTC is also reported. |
| Sizing equity (rule 11) | Equity at the start of each month; frozen for the next month after a month above +25%. |
| Costs | Taker 0.05% + slippage 0.02% (BTC/ETH) or 0.07% (others) per side on entries, adds, stops and window exits; the resting TP pays the 0.02% maker fee and no slippage. Funding = rate × the position's mark value at each funding time (calc_time floored to the minute), owed if the position opened before that time and is still open at it. Hours with no funding print are charged 0.01% per 8 h: before a coin's perpetual listed, and for ICP before 2022-09-01 (as in `leverage_breakout.py`). 2026-10-01..16 is charged September 2026's median per-interval rate. Idle margin earns nothing in the primary run (T-bill version reported). |
| Fee scenarios | For R0, S1, F and every grid overlay: (i) the base tier above, primary, which decides every test; (ii) the tier implied by the post's own volume (about $0.66B per 30 days; maker 0.010%, taker 0.030%, slippage unchanged — approximate VIP-4 rates, not verified against Binance's current schedule); (iii) no fees and no slippage (gross edge). |
| Grid | None in R0 (see the overlays below). |

**Fill conventions.**
- Every decision uses only data available at its time.
- A daily signal is known only after the 00:00 UTC close, so the earliest fill is the next allowed window.
- In an hourly bar touching both the stop and the TP, the stop fills first, unless 1-minute bars resolve it.
- `trades == 0` hours and minutes are exchange outages: no fills, and no stop or TP triggered by the flat print.

## Sensitivity grid (every row reported; none selected)

Each row changes R0 as stated and nothing else, unless it says otherwise.

- **S1 "R0-core":** rules 6 and 12-15 off; entry at the 01:00 UTC hourly open after the signal; trend exit at
  the 01:00 UTC open after the exit close.
- **S1W:** S1 with R0's entry and exit windows (06:00 / 10:00 New York entries; 13:00 New York exits). The base
  for H7 and H8.
- **S2:** L = 1 (account-level exposure 1/9 per slot at entry, 1/3 at full size).
- **S3:** L = 5 isolated; and L = 3 cross margin, i.e. one cross account holding the three sleeves and the idle
  cash. The cross account is liquidated when its equity, with every open coin marked at its hourly mark-price
  low taken jointly (a conservative bound), falls below the sum of maintenance margins. All positions are then
  closed, and the account keeps only what exceeds the maintenance margin.
- **S4:** no pyramiding (full M at entry).
- **S5:** adds at +2% / +5% return on margin.
- **S6:** BB(20, 2.5); BB(50, 2); BB(10, 1.9); BB(50, 2.1); BB(10, 1.5); BB(50, 2.5).
- **S7:** near-high filter off; 20-day high within 2%; 365-day high within 10%; ATH within 10% only.
- **S8:** 4-hour signal and exit bars.
- **S9:** stop at the lower band; stop at SMA20 − 2.5 × ATR.
- **S10:** one-piece exits: all at TP; or no TP, all on the midline.
- **S11:** symmetric long/short (short a close below the lower band near a 60-day low; cover on a close above
  the midline).
- **S12:** point-in-time universes, re-ranked on the 1st of each month by quote volume over the 90 days to the
  prior day (perpetual where it trades, spot before). A coin that drops out keeps any open position until it
  exits.
  - Top 3 and top 6 of the 40 coins, labelled "point-in-time ranks within a 2026 pool". That pool lacks coins
    that died before 2026 and many 2023-26 newcomers.
  - Top 10 among all Binance USDT perpetuals (stablecoin and index contracts excluded; 1000x contracts mapped
    with their multiplier). If this ranking cannot be built from the archive, the row says so.
- **S13:** squeeze pre-condition: BandWidth within 10% of its 125-day low at some point in the prior 10 days.
- **S14:** entries only in the 10:00 New York window.
- **S15:** rule 6 as a binding 72-hour minimum hold for all positions (midline exit suppressed; stop and TP
  active); rule 15 off.
- **S16:** 1-hour signal and exit bars.
- **S17:** universe BTC/ETH/SOL/ZEC (four slots). A hindsight what-if, labelled as such: ZEC is the only coin
  whose buy-and-hold reaches 4.3x in W16.
- **S18:** re-entry allowed on the next qualifying close in the same episode (the rule 3 alternative).
- **S19:** rule 11 off: size from current equity (plain compounding).
- **S20:** weekly signal and exit bars (Monday-labelled weeks, `moneyline_ref.to_weekly()`), crypto at L = 1 and
  the stock version.

**Bar-size rows (S8, S16, S20).** The 4-hour and 1-hour rows decide at each bar close and fill at the next
hourly open. Rule 12 and rule 13's 90-minute ban apply. The entry and exit windows (rules 13-14) and rules 6 and
15 are defined for daily decisions, so they are off. Indicator lengths are in bars (20-bar BB, 14-bar ATR); the
near-high look-back stays 60 days. S20's crypto entries use R0's first allowed window after the weekly close.

**F "frequency-matched".** Among {R0 daily, S8 4-hour, S16 1-hour} × {BTC/ETH/SOL, S12 top 6, S12 top 10}, F is
the cell whose W16 tranche count is closest to 1,462. It is chosen on the count alone; the engine writes the
nine counts to `results_bb/` before any return is read. F is then reported with every headline and H11
statistic.

## Grid overlays (one-minute bars; 2024-07..2026-10)

- **G-A "waiting grid" (primary overlay).**
  - **When:** tested at each 00:00 UTC daily close. The grid is deployed at the next 1-minute open if the slot
    is flat and that close is within 5% of the 60-day high and at or below the upper band.
  - **What:** a neutral geometric perpetual grid over [lower band, upper band] of that close.
    - Spacing max(0.5%, 4 × the 0.04% round-trip maker fee).
    - Isolated margin E_sleeve/3 at 3x, so full one-sided inventory is E_sleeve of notional.
  - **Fills:** on 1-minute bars, prices rounded to the tick.
    - Path O→L→H→C if the close is nearer the high, else O→H→L→C.
    - A resting order fills only when the path trades strictly through its level (SCALPING_PREREG, F1). Touch
      fills are reported only as an optimistic bound.
    - An order placed during a minute cannot fill in that minute, and nothing fills in `trades == 0` minutes.
    - Each fill pays the 0.02% maker fee.
  - **Funding** is charged on net inventory at each print.
  - **Liquidation:** when the hourly mark-price high or low takes the grid's equity below its maintenance
    margin. The grid then loses its margin.
  - **Ends when:**
    - (a) R0's entry hour arrives: inventory is closed at that hour's open at taker fee plus slippage;
    - (b) a daily close falls below the lower band: closed at the next 1-minute open at the same cost;
    - (c) 14 days pass: closed at the same cost, and redeployed only if the condition still holds.
- **G-B (exploratory):** each R0 tranche run as a long-mode grid over [S, TP], 20 levels.
- **G-0 (benchmark, exploratory):** an always-on neutral grid, ±10%, re-centred weekly.
- G-B and G-0 use G-A's fill, fee, funding and liquidation rules.
- H10 uses BTC, ETH and SOL. BNB, XRP and DOGE are run with R0 extended to a six-slot universe (exploratory).

## Stocks and ETFs ("all of our assets")

- **Rules:** the same daily signal (BB(20, 2) breakout near the 60-day high or ATH), stop, 3R take-profit on
  half, midline exit, and pyramiding (first tranche M/3, adds at +2% and +5%). No grid.
- **Prices:**
  - Signals (bands, ATR14, the 60-day high, ATH) use split-adjusted, not dividend-adjusted, OHLC.
    - Members: `universe_pit_all` OHLC divided by `ma_bounce.chart_factor()`.
    - ETFs, TSLA, COIN and HOOD: `raw_pit` OHLC.
    - CRCL: `universe_recent_raw`.
  - Strategy P&L and every buy-and-hold benchmark are total return, with dividends credited on ex-dates while a
    position is held.
  - ATH_t uses the longest file available.
- **Fills** (the next session's open is a stated deviation from the post's 10:00 ET entry and 13:00 ET exit):
  - Entry at the next session's open. A Friday entry is deferred to the next session, and the latest completed
    bar must still satisfy the signal. The entry is skipped if the open is at or below S.
  - Adds trigger on a daily close ≥ 1.02 / 1.05 × entry₁ and fill at the next open.
  - Stop and TP fill intraday at their level, or at the open if it gaps through. If one bar touches both, the
    stop fills first.
  - The trend exit fills at the next open.
  - A flat bar (open = high = low = close, a close-only source row) creates no signal, entry or add. It
    triggers a pending stop only if its close is at or below S, and the stop then fills at that close.
- **Dead names:** a position whose prices end is closed at the last close. Delisted names stay in the
  buy-and-hold benchmark at their last close (the `ma_bounce` convention).
- **Leverage:** 1x (primary) and 2x (Reg-T, exploratory), with the borrowed half charged the T-bill rate + 2.5
  points a year.
- **Costs:** 3 bp per side for S&P members, ETFs and TSLA (HANDOFF section 4: 1 bp + 2 bp); 10 bp per side for
  COIN, HOOD and CRCL. Double costs are reported as a sensitivity.
- **Universes:**
  - **Point-in-time S&P 500 members.** A name can open a position only on a day it is a member.
    - Trade-level statistics use every signal, each member its own slot, with no position cap.
    - The portfolio (the Sharpe test) holds at most 20 positions of M = equity/20 each, so total notional is
      ≤ 1x equity.
    - When more signals arrive than free slots, slots are filled in a pseudo-random order drawn each day with
      `numpy.random.default_rng(20261018)`.
    - The Sharpe test is also run with 100 further seeds; their median and 5th-95th percentiles are reported.
      If the primary seed passes and the median seed does not, HS1 is INCONCLUSIVE.
    - Also reported: the (close − upper band)/ATR14 ranking (largest first, ties alphabetical) as a tie-break
      sensitivity, and a matched random-entry book (same daily slot count and holding durations, random
      members) that separates the signal from the concentration.
  - **The 14 ETFs:** reported individually and pooled (HS2).
  - **The user's seven tickers:** reported individually. A ticker with fewer than 20 trades is reported but not
    interpreted.

## What the user could run (reported for S1 and for R0 at L = 1)

The Binance-perpetual rows answer "does the trader's strategy work?". US residents generally cannot use
Binance perpetuals or grid bots, so the rows below answer "could you trade it?".

| route | vehicle | assets | cost per side | timing |
|---|---|---|---|---|
| RH | Robinhood spot crypto: long only, no leverage, no grid | BTC/ETH/SOL; and the 24 Robinhood-tradable coins of the 40, pooled | 0.95% on every tranche | the 01:00 UTC open after the signal; R0's windows as a variant |
| ETF | spot BTC and ETH ETFs, signal from the Binance daily close (`costs.etf_want`) | BTC, ETH | 0.02% | next NYSE session (gate.py `spot_etf`) |
| CB | US perpetual-style futures (Coinbase Financial Markets) | BTC, ETH, two slots | 0.10% all-in (an assumption; the published schedule is not cited); Binance prices and funding as proxies | as R0, at L = 1 and 3 |
| Stocks | the stock version at 1x | the user's seven tickers and the 14 ETFs | as above | next session (gate.py `stock_daily`) |

- RH and ETF are also run without pyramiding (S4), because every add pays the route's cost again.
- **Gate.** `gate.evaluate` accepts a long/flat series on closes, so each route's in-position series (long while
  any tranche is open) goes through it at the route's vehicle: T1-T7 and T2b vs SPY, at 35% short-term / 20%
  long-term tax. Each gets TRADE, PROBATION or NO-SIGNAL, reported with `gate.placebo()`'s expected false-pass
  count. The full-mechanics after-tax CAGR from `bb_replica.py` is reported beside it.
- The write-up's "should you trade it?" comes from these rows only.

---

## Hypotheses and pass rules

### Units and statistics

- **Trade return** = net P&L of the whole position (all tranches) divided by its maximum notional M.
- **Drift-adjusted trade return** = trade return − Σ over the hours h the position is held of (notional_h / M)
  × μ.
  - μ is the asset's mean hourly arithmetic return (daily for stocks) over its whole sample, excluding the
    holding period and the 182 days on either side (the leave-out drift of HANDOFF 5.19).
  - It removes what the same exposure would have earned from average drift, so a pass reflects timing, not
    long exposure to rising assets.
  - All trade-level and paired tests (H1, H3-H8, HS1, HS2) use it; the unadjusted value is reported beside it.
- **Per-signal paired tests** (H3, H6-H8).
  - The unit is a signal episode: a fresh close above the upper band.
  - A signal that one variant skips counts as 0 for it; one it delays counts at its delayed trade.
  - The statistic is the mean of variant minus base over the union of both variants' signals. A filter that
    removes trades is therefore judged on total return, not per-trade return.
- **Trade-level and paired SEs:** clustered by entry calendar month (one-way, small-sample factor G/(G − 1)).
  The t is compared with Student t at G − 1 df, where G = the number of months with a trade.
  - Month clusters are primary because positions on BTC, ETH and SOL overlap: about 75-85% of trades overlap
    another coin's trade on synthetic paths at correlation 0.6-0.8. On those paths, a true null was rejected
    at a nominal one-sided 5% by 13% of unclustered tests, 9% with date clusters, 6% with week clusters and 3%
    with month clusters.
  - Quarter clusters and overlap-episode clusters (connected runs of overlapping holdings across coins) are
    reported as sensitivities.
- **NO EDGE bounds for trade-level and paired tests** use a month-cluster bootstrap-t (9,999 draws). Trade
  returns are right-skewed: on synthetic paths the analytic clustered-t 95% bound fell below the true mean 14%
  of the time, the bootstrap-t 8% (see the inference control).
- **Portfolio-level tests:** daily account returns in excess of the 3-month T-bill. In these tests idle cash
  and idle margin earn the T-bill rate in every arm; the zero-interest version is also reported.
  - Crypto days are UTC calendar days (365 a year); stock days are sessions (252).
  - Paired stationary block bootstrap, with strategy and benchmark resampled on the same days: 10,000 draws,
    mean block 1 month, also reported at 3 and 12 months. The verdict uses the larger of the 1- and 3-month
    p-values.
  - Sharpe differences are studentized (Ledoit and Wolf 2008).
- **Bootstrap p-values:** p = (1 + #{b : θ*_b − θ̂ ≥ θ̂}) / (B + 1).

### Multiplicity

One Holm family covers H1-H10, HS1 and HS2 (12 tests), at 5% one-sided.
- Holm runs on the one-sided p-values of all 12, whether or not each meets its other conditions. Every
  Holm-adjusted p is reported.
- A test with several required comparisons enters with the largest of their one-sided p-values. This
  intersection-union test is valid without further correction. It applies to H2 (vs buy-and-hold; vs the
  indicator), H8 (rule 6; rule 15), HS1 and HS2 (trade mean; Sharpe).
- Placebo ranks (H6-H8), sign conditions in halves and the coin-set conditions of H1 are additional gates, not
  p-values.
- Every PASS also needs its point estimate > 0 in both halves of its sample, where its row does not already
  require it: crypto 2020-01..2022-12 and 2023-01..2026-10; stocks and ETFs 2001-2013 and 2014-2026; H10
  2024-07..2025-08 and 2025-09..2026-10.
- H11, H11b, H12, the sensitivity rows, the routes, and per-coin and per-ticker results are descriptive. Any
  p-value shown for them is labelled exploratory and Benjamini-Hochberg adjusted within its table.

### Verdicts

Each of the 12 tests gets one verdict:
- **PASS:** Holm-adjusted p < 0.05 and every other condition of its pass rule holds.
- **NO EDGE:** the one-sided upper confidence bound of its effect, at level 1 − 0.05/12, is below the economic
  threshold E. It is reported as NO EDGE (HARMS) when the bound is below 0. For a test that enters Holm with
  the largest of several p-values, one component meeting this is enough.
  - E = +0.5% of M per trade, drift-adjusted (H1; the trade part of HS1 and HS2). That is about the post's own
    implied +0.17 average losses at a 3% average loss.
  - E = +0.25% of M per signal (H3-H8).
  - E = +0.10 annualized Sharpe (H2; the Sharpe part of HS1 and HS2).
  - E = +2 log points a year (H9).
  - E = +1% of account equity a year (H10).
- **INCONCLUSIVE:** neither. It is reported as "the data cannot tell".

Also reported for every test:
- the point estimate and its two-sided 95% interval;
- the largest effect ruled out at 95%;
- the minimum detectable effect, MDE = (2.64 + 0.84) × SE, using the SE that decides the test.

A summary may say the strategy "does not work" on an asset group only if that group's H1 (crypto), HS1
(stocks) or HS2 (ETFs) is NO EDGE.

### The tests

| id | hypothesis (as the claim that the rule helps) | PASS requires |
|---|---|---|
| **H1 core edge** | S1 at L = 1 earns more per trade on BTC/ETH/SOL over the full sample than the same exposure would from the coins' average drift | Holm p < 0.05 for drift-adjusted mean > 0 (month-clustered t). Also: unadjusted mean > 0; drift-adjusted mean > 0 in both halves; drift-adjusted mean > 0 pooled over the other 37 coins of the 40 (its month-clustered 95% interval reported); drift-adjusted mean > 0 on S12's point-in-time top-3 universe (all-contract ranking; within the 40 if that ranking cannot be built) |
| **H2 vs benchmarks** | S1 at L = 1 (the three-slot account) beats on Sharpe both (a) the equal-weight buy-and-hold of BTC/ETH/SOL (spot, each coin joining when S1 can first trade it, rebalanced daily, spot costs, no funding) and (b) the repo's daily indicator (`moneyline_ref`, the pre-October-2026 version; the updated "Bullmania MoneyLine" is not replicated, HANDOFF 2), run long/flat at M = sleeve on the same perpetuals, signal at the 00:00 UTC close, fill at the 01:00 UTC open, with S1's fees, slippage and funding | Holm p = max(p_BH, p_ML) < 0.05 (paired stationary block bootstrap of daily excess returns, studentized) |
| **H3 pyramiding** | R0's 1/3 + adds beats S4 (full size at entry) per unit of risk | Holm p < 0.05 for the per-signal paired difference in drift-adjusted net return per unit of maximum notional (month-clustered); **and** R0's drift-adjusted net return per unit of exposure-time (Σ net P&L / Σ notional × days held, over all trades; month-clustered delta method) is above S4's. If the two units disagree in sign, H3 is INCONCLUSIVE |
| **H4 confirmation** | Close-confirmed entry (S1) beats intrabar band-touch entry. The touch arm rests a buy-stop at the upper band of the latest completed daily bar, re-placed at each 00:00 UTC close, active while the coin is flat and that level meets the near-high condition against that bar's 60-day high and ATH. It fills in the first hour whose high exceeds the level, at max(level, that hour's open) plus taker fee and slippage, never in a `trades == 0` hour. S comes from the same completed bar; adds, TP and exits are S1's | Holm p < 0.05 for the per-episode paired difference. An episode runs from the first touch of the prior day's upper band to the next daily close below the midline; each variant's trades are assigned to the episode they were entered in. The statistic is S1's total drift-adjusted net P&L per M in the episode minus the touch arm's, including touches that never close above the band (month-clustered by episode start) |
| **H5 near-high filter** | Within S1 with the near-high filter off, breakouts that meet R0's near-high condition beat those that do not, per trade | Holm p < 0.05 for the coefficient on a near-high indicator in a regression of drift-adjusted net trade return on an intercept and that indicator (month-clustered SE, t at G − 1 df). The total drift-adjusted P&L with and without the filter is reported beside it |
| **H6 hour rules (13-14)** | R0's entry and exit windows beat S1's 01:00 UTC timing, holding everything else as in S1 | Holm p < 0.05 for the per-signal paired difference (drift-adjusted, month-clustered) **and** R0's pair (entry 06:00, exit 13:00 New York) ranks in the top 5% (rank ≤ 28) of all 576 (entry hour, exit hour) pairs in New York clock time, ranked on the same per-signal mean. Every pair shifts with US daylight saving as R0's does, and fills at the first occurrence of its New York hour after the deciding 00:00 UTC close. The rank is computed on the raw statistic and on its residual after a least-squares fit across the 576 pairs on entry delay and exit delay (hours from the deciding close, linear and quadratic); both must be in the top 5%. All pairs are enumerated, not sampled |
| **H7 weekday rule (12)** | Adding rule 12 to S1W raises net return per signal. Rule 12: no first-tranche fill on a New York-date Friday or Saturday; a blocked signal waits for the next allowed window and must still hold on the latest completed daily bar | Holm p < 0.05 for the per-signal paired difference vs S1W (a signal the block skips counts as 0; one it delays counts at its delayed trade; drift-adjusted, month-clustered) **and** the Fri+Sat block ranks first among the 7 consecutive-day-pair blocks, each coded the same way (New York date, deferred, not dropped), on the same statistic. Under the null the rank has a 1-in-7 chance, so it is a weak gate on its own |
| **H8 hold and Monday rules (6, 15)** | Added to S1W, (a) a 72-h minimum hold for every position (midline exit suppressed for 72 h after entry₁; stop and TP active; S15's rule 6) and (b) R0's rule 15 deferral each raise net return per signal | Holm p = max(p_a, p_b) < 0.05, each from the per-signal paired difference vs S1W (drift-adjusted, month-clustered); **and** the Sat+Sun deferral ranks first among the 7 consecutive-day-pair deferrals on the same statistic. For (a), the dose-response at minimum holds of 0, 24, 48, 72, 96, 120 and 168 h is reported, with no rank criterion: hold lengths are ordered doses, not exchangeable placebos |
| **H9 leverage (rule 4)** | R0 at L = 3 has a higher long-run growth rate than at L = 1 | Holm p < 0.05 for the mean daily log-return difference (L = 3 minus L = 1) of the three-slot BTC/ETH/SOL account, 2020-01..2026-10, > 0 (paired stationary block bootstrap). Account equity is floored at 0; if it reaches 0 at L = 3, growth is −∞ and H9 is NO EDGE without a bootstrap. Also reported: growth at L = 1, 2, 3, 4, 5; the growth-optimal L with a 90% bootstrap interval; the L = 1 account's m/s² (mean over variance of daily returns; with no liquidations H9 is close to testing m/s² > 2); average and peak account-level exposure at each L; liquidations; worst drawdown. A non-PASS is not evidence that leverage lowers growth: that claim needs the one-sided upper bound below 0 |
| **H10 grid overlay** | R0 + G-A has a higher net return than R0 alone over 2024-07..2026-10 on BTC/ETH/SOL | Holm p < 0.05 for the mean daily difference in account return > 0, with grid inventory marked to market at each 00:00 UTC close (paired stationary block bootstrap, mean block 28 days), at fee scenario (i); (ii) and (iii) reported. Reported separately: the grid's realized round-trip profit ("grid profit"), its inventory P&L, fees, and the P&L of each deployment |
| **HS1 stocks** | The stock version at 1x on point-in-time S&P 500 members has a positive drift-adjusted mean net trade return, and its 20-slot portfolio beats the equal-weight buy-and-hold of the same members on Sharpe | Holm p = max(p_trade, p_Sharpe) < 0.05. p_trade: month-clustered t of the drift-adjusted mean over every signal. p_Sharpe: paired block bootstrap of daily excess returns against the equal-weight point-in-time members (rebalanced daily, total return, delisted names at their last price, idle cash at T-bills in both). Both > 0 in both halves (2001-2013, 2014-2026) |
| **HS2 ETFs** | The same on the 14 ETFs | Holm p = max(p_trade, p_Sharpe) < 0.05 as in HS1 (every signal; equal-weight buy-and-hold of the ETFs listed at the time, rebalanced daily); both > 0 in both halves |

### Expected sample sizes and power

Projected before any data run, from coverage counts and synthetic correlated random walks running R0's signal
rules; no market returns; rough.

| test | expected sample | SE | MDE at 80% power (α 0.05/12 … 0.05) | compared with |
|---|---|---|---|---|
| H1 | 80-120 trades (≈ 4.5-5 per coin-year), 40-55 entry months | 1.8-2.6% of M | 6-9% … 4.5-6.5% | post's implied edge ≈ +0.17 average losses ≈ +1% of M; drift alone ≈ +2% |
| H3 | ≈ 110 signals | ≈ 0.4% | ≈ 1.5% … 1.05% | exposure effect under drift ≈ −0.5% |
| H6 | ≈ 110 signals | ≈ 0.4% | ≈ 1.4% … 1.0% | |
| H8a | ≈ 110 signals | ≈ 0.05% | ≈ 0.2% … 0.13% | binds on few trades |
| H4, H5 | two overlapping trade sets | ≈ 3-4% | ≈ 10-14% … 7.5-10% | |
| H2 | 6.8 years | ΔSharpe ≈ 0.4-0.5 | ≈ 1.3-1.7 … 1.0-1.2 | |
| H9 | ≈ 2,480 days | ≈ 13 log pts/yr | ≈ 45 … 32 log pts/yr | 2m − 4s² ≈ −2 to +10 |
| H10 | ≈ 840 days | ≈ 3-6 pts/yr | ≈ 10-20 … 7.5-15 pts/yr | maker fees ≈ −3 to −6 pts/yr |
| HS1 | ≈ 55-60k signals; portfolio ≈ 300-350 trades a year | ≈ 0.15-0.3% of M; ΔSharpe ≈ 0.18 | ≈ 0.5-1.0% … 0.4-0.75%; ≈ 0.6 … 0.45 Sharpe | stock drift ≈ +0.3-0.5% per trade |
| W16 (H11) | 10-30 trades on BTC/ETH/SOL | hit rate ±10 points | — | |
| user's tickers | CRCL ≈ 5 trades, HOOD and COIN ≈ 20 each, TSLA ≈ 60, SPY/QQQ/IWM ≈ 100-125 | | | no per-ticker verdicts |

H2, H9 and H10 are expected to be INCONCLUSIVE whatever the truth, and H1 cannot detect an edge of the size the
post implies. The verdict rule says so in advance.

---

## The answer to the user (fixed now)

The answer to "does their strategy work on our assets?" is the verdicts of H1 and H2 (crypto), HS1 (stocks) and
HS2 (ETFs), stated in that order and before any table. A descriptive number (a multiple, CAGR, hit rate, one
window, one coin or one ticker) is never the basis for "it works" or "it does not work". Sentences are mapped
as follows:
- **"Their full strategy beats holding the coins"** only if R0 (L = 3) beats 1x buy-and-hold of the same coins
  in mean log growth, with a 95% month-block bootstrap interval above zero, over the full sample and in both
  halves. This is reported per asset group with its interval and is not in the Holm family.
- **"The core has an edge, but not over what you already use"** if H1 is PASS and the `moneyline_ref`
  component of H2 is not.
- **"It does not work"** only for NO EDGE; otherwise "not shown" or "the data cannot tell".
- **"You can trade it"** only from a TRADE gate verdict in "What the user could run", next to its expected
  false-pass count.

## Headline replication (descriptive)

For R0 (full rules, 3x), S1 (core, 1x) and F, on each window and asset group, report:
- CAGR, multiple, Sharpe, max drawdown, liquidations and trade count, each with its 95% month-block bootstrap
  interval where defined;
- hit rate, average win / average loss, the share of trades held > 7 days that won, and the share of profit
  from trades held ≥ 3 days;
- after-tax CAGR (35% / 20%) next to SPY's over the same dates.

Each is compared with buy-and-hold and the repo indicator on the same coins and windows. W16 and W16b results
are labelled as single 16-month paths.

**TV cross-check (descriptive).** S1 on the close-only `data/tv_full` exports (BTC from 2015-07, ETH 2016-05,
BNB 2017-07, ZEC 2019-03, SOL 2021-06), with stops on closes using the exported ATR(14), reported beside the
exported indicator state, the basis of HANDOFF 5.1.

## H11 consistency check (descriptive; no tuning)

On W16 and W16b, for R0, every sensitivity variant, F, R0 + G-A and R0 + G-B, report each statistic per
position and per tranche. A tranche is each first entry and each add, counted as one "bot", the likeliest
reading of "1,462 bots" (`rules_and_evidence.md` section 2.3).
- **Count:** positions (vs about 490) and tranches (vs 1,462).
- **Hit rate** (vs 48.7%) with its 95% interval. For the grid overlays, also vs 51.7%, and the change from the
  same row without the grid (vs +3.0 points).
- **Average win / average loss** in dollars (vs 1.4), with a month-cluster bootstrap 95% interval.
- **Account multiple** (vs 4.3x), with its interval.
- **Holding shares:** the share of > 7-day positions that won (vs 75%) and the profit share of ≥ 3-day
  positions (vs > 80%). Each is shown beside the same variant's value on the driftless synthetic series of the
  controls (the no-skill reference) and beside the luck benchmark's random-entry distribution.
- **Turnover:** traded volume / average equity, against the 950-19,000x range implied by a $0.25-5M start
  (`rules_and_evidence.md` section 2.3). Reported only, not a condition, because the start is unknown.

A row is **consistent** with the post only if all of these hold:
- hit rate and the two holding shares are within 2 binomial SEs at the row's own count;
- win/loss and multiple are inside the row's 95% month-block bootstrap interval;
- the per-tranche count is between 0.5x and 2x the post's.

A row that fails on count alone is reported as "different trading frequency": it cannot be the post's strategy,
whatever its hit rate. Expected now: R0 on BTC/ETH/SOL daily bars falls far short of the count and the
turnover, so it is not consistent on W16.

At W16 sizes the test is weak in both directions: a variant whose true statistics equal the post's would pass a
±5-point / ±0.3 band only about 15% of the time, and one at 40% / 2.0 about 8% of the time (synthetic check).
So:
- the number of consistent variant-windows is reported beside the number expected by chance (the share of
  H11b's random-entry decoys that are consistent, times the number of variant-windows);
- every row's out-of-window results are reported, consistent and inconsistent rows side by side. For W16 rows
  the out-of-window span is 2020-01-01..2025-06-16; for W16b rows, 2020-01-01..2024-06-29 and
  2025-11-01..2026-10-16;
- consistent rows are flagged as a fitted subset whose out-of-window results are the only evidence about them;
- no row is ever called "their strategy", "their exact rules" or "the replication", and a match is never cited
  as evidence that a variant works.

## H11b closest match to the post (labelled fit; exploratory)

Run only after every primary result has been written to `results_bb/`. It changes no primary row or verdict.

- **Cells (full factorial, fixed now):** signal bars {1d, 4h, 1h} × BB {(20, 2), (20, 2.5), (10, 1.9)} ×
  near-high {off, R0} × adds {R0 price, ROE (S5), none} × exits {R0, no TP} × universe {BTC/ETH/SOL, S12 top
  6, S12 top 10} × direction {long, S11 long/short} = 648 cells.
  - Each cell runs at L = 3 on W16 and W16b. Daily cells use R0's time rules; 4-hour and 1-hour cells follow
    the bar-size convention of the sensitivity grid.
  - Cells in the identified set are also run at L = 5, and with G-A and G-B where the one-minute data exist.
- **Decoys:** 20 random-entry twins each for 50 cells drawn with `default_rng(20261018)` and for every cell in
  the identified set. Each twin enters on random flat days inside the cell's entry rules, with the same count
  per coin and the same adds, stops and exits.
- **Distance:** D = the sum of squared z-scores of the H11 statistics, in per-tranche units. Count and multiple
  enter as log ratios scaled by their H11 bands.
- **Identified set:** the cells with D ≤ D_min + the 95% χ² quantile at k degrees of freedom, where k is the
  number of statistics in D.
- **Reported:**
  - the best cell on W16 and on W16b;
  - the identified set, and the share of cells and of decoys inside it;
  - whether the set's cells agree on bars, universe, direction and grid;
  - the set's out-of-window results (H11's windows), next to the median cell's;
  - the rank correlation across cells between D and out-of-window net return.
- **Reading, fixed now:** the post "identifies" a strategy only if fewer than 5% of cells and fewer than 5% of
  decoys fall in the identified set, and those cells share bars and universe. Otherwise the write-up says the
  statistics do not identify it. A fitted cell is called "a rule set consistent with the post", never "their
  strategy".

## H12 shorts (exploratory)

S11 vs R0 on W16 and on the full sample.

## Luck and tautology benchmark (descriptive)

- For R0 at L = 3 and L = 5, on W16 and W16b: 1,000 random-entry versions each. Each keeps R0's number of first
  entries per coin, drawn from days the coin was flat, inside R0's entry windows. It also keeps R0's adds,
  stops, exits, sizing, costs and funding.
- Reported: the share that reaches ≥ 4.3x, the share that reaches ≥ 2x, the share with a liquidation, and the
  random-entry distribution of every H11 statistic. A post statistic that random entries reproduce as often as
  R0 does says nothing about the entry rule (expected for the 75% and 80% holding shares).
- Also reported, as in SCALPING_PREREG: the months of record a trader with R0's monthly account SD would need
  for t ≥ 2 at the post's implied return (4.3x in 16 months).

## Rule scorecard (descriptive)

One row for each of rules 1-15, giving:
- the coded form;
- the comparison that measures it;
- the effect on mean net trade return and on sleeve Sharpe, with 95% intervals;
- a verdict: helps / hurts / no detectable effect / no-op as coded / not testable (with the reason). For rules
  in the Holm family the verdict is the test's.

Comparisons by rule: 1 S4; 2 S5 and S4 (H3); 3 S18; 4 H9; 5 S12; 6 H8; 7 H4; 8 S10; 9 built in (not
testable); 10 S9 and S10; 11 S19; 12 H7; 13-14 H6; 15 H8.

## Controls (run before primary results are read)

A failed control stops the study until it is fixed.

- **Engine known answer.**
  - On a synthetic hourly series whose price is a martingale (zero mean simple return, i.e. log drift −σ²/2),
    S1's and R0's mean trade return per unit of M, before costs and funding, is within 2 SE of zero over at
    least 20,000 trades. After costs it is about minus the round-trip cost.
  - The drift-adjusted mean is about zero both with and without a constant drift.
  - G-A's mean P&L is within 2 SE of zero before fees and negative after fees.
  - On a synthetic series with persistent trends, S1 is positive.
- **Inference known answer.** On 200 synthetic three-coin paths with zero arithmetic drift and cross-correlation
  0.8, H1's month-clustered test rejects at most about 5% of the time at a nominal one-sided 5%. Its NO EDGE
  bound (month-cluster bootstrap-t) falls below the true mean at most about 5% of the time at the 95% level. If
  it does so more often, the bound's level is widened until it does not, before primary results are read.
- **Look-ahead check.**
  - At least 50 cut times t are drawn at random minutes, never on an hour or day boundary: at least 10 in
    2025-06..2026-10, 10 on weekends and 10 within 2 h of an entry or exit window. For the stock engine, t falls
    inside a session.
  - Every price after t is multiplied by 1.5 in the spot, perpetual, mark-price and 1-minute files (and in the
    stock files), and every volume after t by 0.5.
  - Every order, fill, add, exit, liquidation, sizing, universe-rank and grid decision stamped before t must be
    unchanged, for R0, S1, S8, S11, S12, H4's touch arm, G-A and the stock version.
- **Liquidation check.** A hand-built path through the liquidation price liquidates exactly once, with the
  stated loss.
- **Fill audit.** Every simulated fill is asserted, before costs, to lie within the [low, high] of the bar it
  fills in (the 1-minute bar where an hour is resolved on 1-minute data). It must be stamped after the bar close
  or order placement that caused it, and must never fall in a `trades == 0` bar or a flat close-only stock bar.
  Any violation stops the run.
- **Grid path check.** On a synthetic driftless 1-second path aggregated to 1-minute bars, the engine's grid P&L
  matches the 1-second P&L to within 10% of gross grid profit.
- **Indicator cross-check.** The repo's `moneyline_ref` benchmark reproduces HANDOFF 5.14's BTC 1x multiple to
  order of magnitude on the same window.

## Reporting rules

- Every pre-registered row and test is reported.
- Results including ZEC are always shown next to results without it.
- For H1, HS1 and HS2: the drift-adjusted mean after removing the single entry month whose removal lowers it
  most, and the share of total P&L from the top 5% of trades. A PASS whose month-dropped mean is ≤ 0 is
  reported as "PASS, carried by one month".
- Any change after results are seen is a listed deviation, with the reason.
- **Vehicle note.** US residents generally cannot use Binance perpetuals or grid bots. The closest US options
  are Coinbase's CFTC-regulated BTC and ETH perpetual-style futures and spot grid apps. Robinhood spot crypto at
  about 0.95% a side makes pyramids and grids uneconomic. The verdict for the user is taken from "What the user
  could run".

---

## Revision log (draft ae4d591 → frozen)

**Statistics lens (20 proposals).**
- Adopted:
  - the PASS / NO EDGE / INCONCLUSIVE verdicts with E and the MDE, and the "does not work" rule (1);
  - the drift-adjusted unit, and the 40-coin condition on the other 37 coins (2);
  - the multiplicity rules: Holm on all 12, max-p for compound tests, gates (3);
  - HS1's uncapped trade test and the seeded tie-break with 100 seeds plus the random-entry book (4);
  - H8 split into (a) and (b) with a dose-response for (a) (5);
  - H11's intervals, chance count and no-"their strategy" rule (6, merged with relevance 1);
  - the fixed 14-ETF list and HS2 halves (7);
  - the headline tied to the verdicts (8);
  - per-signal pairing, month clusters at G − 1 df, excess returns and the bootstrap details (9);
  - the power table (10);
  - the H9, H3, H6, H2, H10, H7, H4 and H5 rows (11-17);
  - both-halves for every PASS (18);
  - the martingale engine control and the inference control (19);
  - the month-dropped mean and top-5% share (20).
- Modified: the halves for stocks follow fidelity 4 (2001-2013 / 2014-2026) rather than 1996-2010 / 2011-2026.

**Fidelity lens (19 proposals).** All adopted:
- the look-ahead control at off-boundary cut times across every engine (1);
- S1W as the base for H7 and H8 (2);
- the S12 gate in H1 (3);
- stock price bases, fills, dead names and halves (4);
- stop fills resolved on 1-minute bars, with the 0.99 × S rule elsewhere (5);
- the fill audit (6);
- the full G-A specification (7);
- H2's benchmark execution (8, merged with statistics 14);
- the liquidation formula with fees, funding and post-add entries, and the mark-file trim, documented in
  `data_inventory.md` section 1.1 (9);
- the add, re-entry, rule 6, rule 15 and entry-window mechanics (10-12);
- H4's touch arm (13);
- stock leverage financing, costs and the ETF list (14);
- signal series and warm-up (15);
- maker fee for the TP and funding timing (16);
- window edges (17);
- the martingale engine control (18);
- cross margin (19).

Two conflicts were resolved:
- **Stock tie-break:** seeded random (statistics 4) is primary, because it adds no selection dimension; the
  (close − upper band)/ATR ranking (fidelity 14) is a sensitivity.
- **H2 Sharpe:** excess returns with idle cash at the T-bill in every arm (statistics 9 and 14) are primary;
  raw returns with 0% cash (fidelity 8) are reported.

**Relevance lens (15 proposals).**
- Adopted:
  - the H11 statistics, per-tranche counts and consistency rule (1);
  - "What the user could run" with the gate (2);
  - the answer map (3);
  - the luck benchmark (5);
  - S16, S17 and F (6);
  - the fee scenarios (7);
  - the pre-perpetual block and the TV cross-check (8);
  - the ETF list, CRCL's source and the 20-trade floor (9);
  - S18, S19 and the rule scorecard (10);
  - the all-contract S12 top 10 (12);
  - S20 weekly bars (13);
  - the `moneyline_ref` version note (14);
  - stock costs and price basis (15).
- Modified:
  - **H11b (4)** is reduced from 1,728 cells to 648, at L = 3 only, with L = 5 and the grid overlays run only
    for the identified set, and decoys for 50 random cells rather than 100. The reason is cost; the
    identification rule is unchanged.
  - **The answer map (3):** its E values were replaced by statistics 1's.
  - **The CB route (2):** its cost is a stated assumption (0.10% all-in), since the schedule was not cited.
- Declined:
  - **Two Holm families (11).** One family of 12 keeps the study-wide error at 5%. The power table already shows
    that the decision tests are underpowered for reasons a smaller family would not fix (H1's MDE is 4.5-9% of M
    against a 0.5% threshold).

**Changes not proposed by a reviewer.**
- H5's base is S1 with the near-high filter off, not an R0-based S7 row, so that it shares H1's core.
- The bar-size convention for S8, S16 and S20 (fills at the next hourly open; rule 12 and the 90-minute ban on;
  the windows and rules 6 and 15 off), which the draft left open.
- The signal row now states the "fresh close" condition (C_{t−1} ≤ UB_{t−1}) that the draft's research note
  coded as rule 3.

---

## Addendum: clarifications made while building the data layer (2026-10-19, before any strategy result)

No strategy return had been computed when these were decided. Each resolves a case the frozen text did not
anticipate; none changes a test, threshold or window.

- **S12's all-contract pool excludes TradFi perpetuals.** Binance listed 186 stock, ETF, pre-IPO, metal, oil
  and FX perpetuals from 2025-12. By 2026 several reach the volume top 10 (gold and silver from 2026-03; SNDK is
  rank 3 in 2026-09 and 2026-10). S12 is a universe of coins (rule 5: "a few liquid coins"), so the primary
  all-contract ranking is crypto-only; the literal ranking with TradFi contracts is reported as a sensitivity.
  The H1 S12 gate uses the crypto-only top 3.
- **Delisted perpetuals.** Spot stands in for the traded series only before a coin's perpetual lists (and for
  Terra 2.0 spot until LUNA2USDT), as the Windows section says. After a perpetual's last bar the coin is not
  tradable. A position still open at that bar is force-closed at its close, paying taker fee plus slippage.
- **S12 entrants with Binance spot** (35 of the 50 contracts fetched for S12) take their signals, warm-up and
  ATH from spot, as the Signal row says. The Data section had listed only their perpetual files.
- **Maintenance margin rates** are Binance's tier-1 rates from an October 2026 snapshot of its leverage
  brackets (via freqtrade's published dump), applied to 2020-2026: BTC and ETH 0.4%. EOS, MATIC and YFII,
  missing from the snapshot, are assumed at 1.0%.
- **Code layout.** `bb_replica.py` is the runner. The work is split into `bb_data.py`, `bb_engine.py`,
  `bb_stats.py`, `bb_stocks.py`, `bb_grid.py` and `bb_bench.py`.

## Addendum 2: rulings made while building the engine (2026-10-19, before any strategy result)

No strategy return had been read when these were decided. Each settles a reading the frozen text left open or a
case it did not anticipate.

- **S6 changes only the entry band.** The stop and trend exit stay on SMA20 and ATR14, and S9's band stop uses
  BB(20, 2), because "each row changes R0 as stated and nothing else". H11b's BB factor means the same.
- **H3-H8 run at R0's L = 3.** S1 and S1W are sensitivity rows that change only what they state; only H1, H2
  and the headline name "S1 at L = 1". A trade's return per unit of M differs across L only through the leverage
  cap and liquidation.
- **Inference control.**
  - It runs on the engine's S1 at L = 1, with no fees (so the true mean is zero), on 200 synthetic three-coin
    paths.
  - If the bootstrap-t 95% bound misses more than 5% of the time, the level is widened to the smallest level at
    which it misses at most 5%. The NO EDGE level's tail (0.05/12) is then scaled by the same factor; for
    example 95.5% maps to 99.625%.
- **Gate window for the spot routes (RH, ETF).** Gate T1 needs 7 years of the underlying's own history, and the
  Full window spans 6.8 years. These routes therefore use the longest Binance spot history (from 2017-08-17),
  and the Full-window gate is reported beside it. The CB route cannot be extended, because the perpetual data
  start in 2019-09, so T1 caps it at PROBATION; this is stated.
- **H2(a) buy-and-hold** holds 1/K of the account per coin, kept in cash (earning the T-bill in the
  excess-return test) until the coin joins. This matches S1's three-slot account and the window-edge rule.
  Equal weights among the joined coins are reported as a sensitivity.
- **HS2's portfolio has 14 slots** (one per ETF, M = equity/14). Twenty slots of equity/20 could never fill on 14
  ETFs.
- **Close-only (CRSP) rows in the member files are flat bars** under the Fills rule: no signal, entry or add.
  They make up 16% of member-days in 2001-2013 and 33% in 1996-2000, and the equal-weight member benchmark still
  holds them. This is recorded as a caveat beside HS1's first half and the 1996-2000 block.
- **Membership.** In the stock version, a signal whose entry session is not a member day is skipped. In S12, a
  pending crypto signal waits through a month in which the coin is not a member.
- **T2b's S&P 500 series** is extended back to 2001 with SPY from `data/raw_pit/`, because `gate.spy_hurdle`'s own
  series starts in 2010-07.
