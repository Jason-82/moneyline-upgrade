# Bollinger-breakout replication: operational rules, grid mechanics, evidence, reconciliation

Written 2026-10-18 as input to the pre-registration. **No Bollinger, breakout or grid strategy was
backtested and no strategy return was computed for this note** (contamination rule). Everything
numerical below is either arithmetic on the tweet's own figures or a descriptive fact about the assets
(buy-and-hold, volatility, band width, funding, hour-of-day volatility and volume).

Source tags:
- **[A]** primary: computed here from the Binance public archive (spot klines, USDT-M funding), or read
  directly from the source image, or a result already in this repo (HANDOFF section given).
- **[S]** secondary: an abstract, publisher listing or search-engine summary of a primary source. The
  full texts were not readable from this sandbox (most web hosts fail DNS here; WebSearch works).
- **[U]** unverified: from memory or inference, not checked in this session.

Descriptive data used: `data/crypto_binance_regime/*.csv` (daily, to 2026-09-30) extended to
2026-10-17 with daily spot klines; USDT-M funding 2024-01..2026-09; spot 1-hour klines for BTC, ETH and
SOL 2025-01..2026-09. All are in `data/bbreplica/rules_desc/` (gitignored); the checker's 1-minute
sample is in `data/bbreplica/rcheck_m1/`. The scripts are in
`/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/bb_rules/`
(`fetch_desc.py`, `desc1.py` to `desc6.py`; the scratch folder is ephemeral, and section 6 describes each
computation so it can be redone).

---

## 0. Summary

1. **The source can't be traced.** Searches for "1,462 bots", "$10.7B" and the wording found nothing.
   Treat every statistic in the post as [U], self-reported and filtered twice: by an AI summariser and
   by whoever chose to post it.
2. **The strategy core is clear enough to code.** Long a daily close above the upper Bollinger Band
   (20, 2) when price is near a local high or an all-time high. Start with one third of a size fixed in
   advance. Add a third at +2% and a third at +5%. Use a wide hard stop and a take-profit of at least 3R.
   Exit everything on a daily close below the 20-day midline. Leverage is 3-5x on a few liquid coins.
3. **Rules 6, 11-15 are ex-post patterns mined by the AI, not decision rules.** Rule 6 is close to a
   tautology under a midline exit: failed breakouts usually close below the midline within days, so
   long holds are mostly winners. The weekday and hour rules come from
   about 70 trading weeks and roughly 500 positions. One weekday's win rate then has a standard error
   of about 6 percentage points, so they are most likely noise. They can still be coded and tested, as
   filters against placebo filters.
4. **The reported numbers are internally consistent but modest per trade.**
   - A 48.7% hit rate with wins 1.4x losses gives +0.17 loss-units per trade (profit factor 1.33).
   - Break-even needs a 41.7% hit rate at 1.4, or a win/loss ratio of 1.05 at 48.7%.
   - A 3R take-profit on every winner would give a win/loss ratio near 3. With losses capped near 1R,
     a ratio of 1.4 allows at most about 47% of winners to have reached +3R (fewer if losses average
     under 1R). Most winners must leave on the midline exit.
5. **Implied risk per trade is small** unless there were few independent positions. Reaching 4.3x
   needs a loss per losing trade of about 0.6% of equity over 1,462 trades, 1.9% over 500, or 9.9%
   (near Kelly) over 150.
6. **The grid is short volatility (short gamma).** Its displayed "grid profit" is N·RV/(2W) per period
   (N = grid notional, RV = realized variance, W = log width of the range). The inventory loses
   N·(Δx)²/(2W), where Δx is the net log move. On a driftless price these cancel in expectation before
   fees. So "the grid pays while waiting" is true only until the move comes. A preprint finds the same
   zero expectation [S].
7. **The likeliest reading of "48.7% right on direction / 51.7% in profit with the grid"** is
   per-bot. "Direction" is the sign of a directional bot's trend P&L, and "in profit" adds the grid's
   realized profit. Exchanges report these separately (grid profit vs trend/unrealized P&L) [S].
8. **The window is unknown.**
   - If the post is recent, 16 months ending 2026-08..10 starts around 2025-04..06.
   - Over 2025-06-17..2026-10-17, buy-and-hold was: BTC 0.78x, ETH 0.96x, SOL 0.70x, BNB 1.11x,
     XRP 0.60x, DOGE 0.47x, ZEC 27x [A].
   - So 4.3x at 3-5x needs most of one full up-leg in ETH, SOL or BNB, several legs, shorts, or ZEC.
     A 3x position must capture 94-114% of the single best up-leg of ETH, SOL or BNB; a 5x position
     must capture 57-69%.
   - A window ending 2025-10 (BTC ATH) makes 4.3x much less demanding. BTC buy-and-hold was 1.75x,
     and 2.3x daily-rebalanced at 3x. A fixed 3x position needs 48-84% of the best BTC, ETH or SOL
     leg, or 15% of XRP's [A].
9. **The volume is extreme for any plausible account.**
   - $10.7B over about 487 days is about 4,700x average equity for a $1M start (about 3,500x a year).
   - A dense futures grid produces roughly 300-4,600x its margin in 16 months [A model]. Base-tier
     fees on $10.7B would be $2-5M, the same order as the profit for a $1-2M account.
10. **Leverage on this window is lethal without stops that fill.**
    - On 2025-10-10 the Binance spot intraday lows vs the prior close were: BTC −16%, ETH −21%,
      SOL −24%, BNB −32%, XRP −55%, DOGE −62% [A].
    - Isolated-margin liquidation is about −33% at 3x and −20% at 5x.
    - Daily-rebalanced 5x buy-and-hold loses at least 93% on every coin in the four windows of
      section 4.3, except BTC (1.03x) and BNB (0.46x) in the window ending 2025-10 [A].
    - This repo already found 3x/5x on a trend signal destroys wealth (Kelly ≤ 1.85; HANDOFF 5.14) [A].
11. **The evidence on Bollinger trading rules is weak.**
    - Bands do no better than moving-average envelopes, and buy-and-hold wins after costs [S].
    - Profits decayed after Bollinger's 1983 introduction and the 2001 book [S].
    - In crypto, channel and range breakouts show some value in trending markets [S]. A 20-coin
      Donchian ensemble reports a Sharpe above 1.5 [S]. This repo found Donchian about equal to its
      indicator, carried by 2020-21 (HANDOFF 5.14) [A].
12. **The proposed primary test is R0** (section 1.18): daily signal, long-only, BTC/ETH/SOL (plus
    every repo asset reported separately), costs and funding modelled. The leverage, time-filter,
    pyramiding and grid pieces are separate, nested hypotheses. Section 5 lists 12 hypotheses and the
    pitfalls.

---

## 1. Part 1: operational rules

### 1.0 Conventions used throughout

- **Bars.** Signals use daily bars closing at 00:00 UTC, the Binance and TradingView crypto
  convention. Execution uses 1-hour bars. Perpetuals (USDT-M) are the vehicle, with spot klines
  before a coin's perpetual existed.
- **Bollinger Bands.** BB(n, k): midline = SMA_n(close); bands = midline ± k·σ_n. σ_n is the
  *population* standard deviation of the last n closes, which is Bollinger's definition [S]. TradingView's
  `ta.bb` also uses the biased estimator [U].
- **BandWidth** = (upper − lower)/midline. **%b** = (close − lower)/(upper − lower).
- **The US open in UTC moves with US daylight saving** (second Sunday of March to first Sunday of
  November). Crypto does not move.

| US clock (New York) | EDT (2025-03-09..11-01, 2026-03-08..10-31) | EST (rest of year) |
|---|---|---|
| 06:00 (open − 3.5 h, "best entry") | 10:00 UTC | 11:00 UTC |
| 08:00-09:30 (the 90 minutes before the open: "never open") | 12:00-13:30 UTC | 13:00-14:30 UTC |
| 09:30 US open | 13:30 UTC | 14:30 UTC |
| 10:00 (open + 30 min, "best entry") | 14:00 UTC | 15:00 UTC |
| 13:00-15:00 (open + 3.5..5.5 h, "do the closing") | 17:00-19:00 UTC | 18:00-20:00 UTC |
| 16:00 US close ("don't close around it") | 20:00 UTC | 21:00 UTC |

- **On NYSE holidays there is no "US open".** Primary: apply the clock times anyway, since crypto
  trades. Alternative: treat holidays as weekend days.
- **Day of week.** Primary: New York local date of the order timestamp. With the entry windows above,
  the UTC date and the New York date are the same, so this only matters for the variants without the
  hour filter (a 00:00 UTC Friday fill is Thursday 20:00 in New York).

### 1.1 The strategy description: "Bollinger Band breakouts near local highs and ATHs; cut when the trend breaks below the midline"

- **(a) Literal.**
  - Signal on day t (daily close C_t): C_t > UB_t of BB(20, 2) **and** price is near a local or
    all-time high.
  - Primary: C_t ≥ 0.95 · max(H over the prior 60 days, today included), **or** C_t ≥ 0.90 · ATH_t.
    ATH_t is the highest high in the Binance history up to t. `data/tv_full` is close-only
    (HANDOFF 3) and has no higher earlier price for BTC, ETH or BNB in a 2020+ sample. Binance
    misses XRP's January 2018 high (its file starts 2018-05) and ZEC's 2016-18 highs (from 2019-03).
    Take those from another source, or label the ATH condition for XRP and ZEC as Binance-only [U].
  - Exit: a daily close below SMA20, the midline.
- **(b) Alternatives.**
  - Band settings: Bollinger's own adjustment, BB(10, 1.9) and BB(50, 2.1) [S]. The pairs
    BB(10, 1.5) and BB(50, 2.5) come from charting platforms (Fidelity, eSignal, Barchart), not
    Bollinger [S]. Also BB(20, 2.5).
  - Timeframe: 4-hour (this repo found 4h breakouts worse than daily, HANDOFF 5.14 [A]) or weekly.
  - "Near local high": 20, 120 or 365 days; within 2%, 5% or 10%. Or none, the pure band breakout.
  - ATH only, within 10% or 20%.
  - Squeeze pre-condition: Bollinger's Method I. BandWidth at or near its 125-bar low before the
    breakout [S].
  - Method II: confirmation by an indicator such as MFI, no squeeze needed [S].
- **(c) Prescriptive.** This is the strategy itself.
- **(d) Test.** The R0 backtest (section 1.18). Per-trade net returns, pooled, against buy-and-hold
  and against this repo's indicator. The near-high filter is H5.

### 1.2 Rule 1: "Set the max size before entry, and start with about a third of it"

- **(a) Literal.**
  - At entry, fix the maximum notional M for the position and buy M/3.
  - M = L · E_sleeve. L is the exchange leverage (rule 4) and E_sleeve = E_size/K, the equity
    earmarked for one of K position slots. Primary K = 3, one per coin in the BTC/ETH/SOL universe.
  - Each slot's exposure is therefore L/3 of its sleeve at entry and L at full size, i.e. L/9 and L/3
    of the account. With all three slots full the account carries L. "3-5x" thus holds both at the margin setting and,
    at full deployment, at account level.
- **(b) Alternatives.**
  - Risk-based maximum: M such that a stop-out of the full position costs r = 1-2% of E.
  - Initial tranche 1/2 or 1/4; K = 1 (single position) or K = 6.
- **(c) Prescriptive.**
- **(d) Test.** Inside the pyramiding comparison H3: 1/3 + adds vs the full M at entry vs a fixed M/3.

### 1.3 Rule 2: "Add only when the trade is 2-5% in profit"

- **(a) Literal.**
  - Add M/3 when the price first reaches entry₁ × 1.02, and the last M/3 at entry₁ × 1.05.
  - Both are measured on price from the first fill.
  - Trigger: an hourly close at or above the threshold, filled at the next hourly open.
  - Adds are not subject to the new-trade time filters; rules 12-13 speak of "opening" trades.
  - No add on a day whose daily close has already triggered the midline exit.
- **(b) Alternatives.**
  - **Thresholds as return on margin (ROE)**, which is what exchange bot screens show [U]. At 3x,
    2%/5% ROE is a +0.67%/+1.67% price move; at 5x, +0.4%/+1.0%. This changes the meaning a lot.
  - A single add anywhere in 2-5%.
  - Turtle-style adds every 0.5·ATR, up to 4 units [S].
  - Adds as resting stop orders, filled intrabar.
- **(c) Prescriptive.** The numbers (2%, 5%) are probably the AI's description of where adds
  happened, but the rule itself is an ex-ante decision rule.
- **(d) Test.** H3: compare with no adds and with the full size at entry, all else equal. Report both
  per-trade return and return per unit of maximum exposure.

### 1.4 Rule 3: "Never average down or top up a loser"

- **(a) Literal.** No add when the price is below the position's average entry price. No re-entry into
  the same coin within the same signal episode after a stop-out. A new signal needs a fresh close
  above the upper band after a close below it.
- **(b) Alternatives.** Allow re-entry on the next qualifying close above the upper band.
- **(c) Prescriptive.** Note the tension with the grid: a long-mode grid buys as price falls, which is
  averaging down by construction (Part 2). The grid has to be sized and bounded separately for both
  rules to hold.
- **(d) Test.** Automatically satisfied by R0's add rules. The re-entry choice is a sensitivity row.

### 1.5 Rule 4: "Keep leverage at 3-5x"

- **(a) Literal.**
  - Exchange leverage L = 3 (primary) or 5 on isolated margin per tranche.
  - Account-level exposure follows rule 1: L/9 per slot at entry, L/3 per slot at full size, and at
    most L with every slot full.
  - Approximate isolated long liquidation price: entry × (1 − 1/L + mmr) [S], with mmr 0.4% (BTC)
    or 0.5% (others).

    | L | price move to liquidation |
    |---|---|
    | 3 | ≈ −32.9% |
    | 5 | ≈ −19.6% |
    | 10 | ≈ −9.6% |

  - The wide stop (rule 10) must sit above the liquidation price. If it does not, cap that trade's
    leverage at 1/(stop distance + mmr + 2%).
- **(b) Alternatives.**
  - Account-level 1x (no leverage), 3x or 5x of total equity.
  - Cross margin over the whole account: liquidation only when account equity falls below total
    maintenance.
- **(c) Prescriptive**, but ambiguous: it could be a margin setting or real exposure.
- **(d) Test.**
  - H9: 1x vs 3x vs 5x, both isolated and cross.
  - Liquidation from the hourly low of the **perpetual mark price** where available (`markPriceKlines`
    in the archive), else the last-price low.
  - A liquidated sleeve loses its margin. Liquidation fees are about 0.5-1% of notional [U].

### 1.6 Rule 5: "Stick to a few liquid coins"

- **(a) Literal.**
  - Primary universe: BTC, ETH, SOL, the three largest non-stablecoin USDT-M perpetuals by volume in
    2025-26 [U]. Median Binance *spot* quote volume 2025-06..2026-10: BTC $1.36B/day, ETH $0.90B,
    SOL $0.32B, XRP $0.19B, BNB $0.10B, DOGE $0.10B, ZEC $0.08B [A].
  - The user's request is "all of our assets", so R0 is also run per asset, with a separate sleeve
    each, on:
    - BNB, XRP, DOGE and ZEC;
    - the 40-coin Binance set (survivorship-inclusive: LUNA, FTT, MATIC→POL);
    - stocks/ETFs in a stock version (section 1.19).
- **(b) Alternatives.**
  - Point-in-time universe: the top 3 or 6 by trailing 30-day perpetual quote volume, re-ranked
    monthly. This avoids picking 2026 survivors.
- **(c) Prescriptive.**
- **(d) Test.** Report per coin and pooled. The point-in-time universe is the out-of-sample check.

### 1.7 Rule 6: "Hold winners at least 3 days. Trades held over a week won 75%, and those ≥ 3 days made > 80% of the profit"

- **(a) Literal (as a rule).**
  - A midline exit is suppressed for the first 72 hours after the first fill **if the position is in
    profit** (mark ≥ average entry).
  - Losing positions can still be cut (rule 9). The hard stop is always active.
- **(b) Alternatives.** No minimum hold; or a minimum hold for every position.
- **(c) Mostly DESCRIPTIVE, close to a tautology.**
  - Under a midline exit, a failed breakout closes below the rising 20-day average within days. A
    position survives a week only if price stayed above the midline, which is mostly true of winners
    (the post's own 75% means a quarter of week-plus holds still lost). So holding time is largely an
    *outcome* of being right, not a cause.
  - "≥ 3 days made > 80% of the profit" is the normal right-skewed payoff of trend following.
  - The prescriptive core is "don't take profits early", which the midline exit already does.
- **(d) Test.**
  - H8: R0 with vs without the 72-hour suppression.
  - Also compute, descriptively, whether R0 reproduces "held > 7 days → about 75% winners". If any
    trend rule reproduces it, it carries no information about this trader.
  - **The literal coding (a) almost never binds [U, reasoning].** A position in profit trades above
    its average entry, which sits near the upper band, about 2σ20 (median 5.5-20% of price, table
    1.11) above the midline. A close below the midline within 72 hours while still in profit needs
    the midline to rise past the entry, which takes an extreme move. H8's rule-6 arm is then close to
    a no-op. The version that bites is the alternative in (b): a 72-hour minimum hold for every
    position, with the hard stop still active.

### 1.8 Rule 7: "Wait for the breakout to confirm before entering, and cut on the trend breaking, not on intraday noise"

- **(a) Literal.**
  - Entry needs a *completed daily close* above the upper band. An intraday touch is not enough.
  - The exit needs a completed daily close below the midline. Intraday crosses are ignored, and only
    the wide hard stop works intrabar.
  - Entry is state-based. At each allowed entry window (rule 13), enter if the *latest completed*
    daily bar satisfies the signal (close > UB, near-high filter) and the coin is flat. So a
    Thursday-close signal blocked by Friday/Saturday can still be taken on Sunday, if Saturday's close
    is still above the band.
- **(b) Alternatives.**
  - Stricter confirmation: two consecutive closes above the band, or the next day's close holding
    above the breakout close (this repo's "flip delay", HANDOFF 5.15, found no help in crypto [A]).
  - Looser: an intrabar stop order at the upper band. Since the band moves with the bar, use the
    prior bar's band, which avoids look-ahead.
  - Exit on a 4-hour close below the midline.
- **(c) Prescriptive.**
- **(d) Test.** H4: close-confirmed vs intrabar entries; daily vs 4-hour exit.

### 1.9 Rule 8: "Exit in one go or two pieces at most"

- **(a) Literal (primary two-piece).**
  - Sell 50% at the take-profit (≥ 3R, rule 10). The other 50% goes on the midline exit or the stop.
  - If the midline exit or the stop comes first, 100% goes at once.
- **(b) Alternatives.**
  - One piece: 100% at the take-profit.
  - One piece: 100% on the midline exit, with the take-profit removed.
  - Two pieces: one third at the take-profit, two thirds on the midline.
- **(c) Prescriptive.** It mainly forbids scaling out in many small pieces.
- **(d) Test.** Sensitivity rows. Pre-register the primary and report the others without selection.

### 1.10 Rule 9: "When wrong, cut all of it"

- **(a) Literal.** Stop and midline exits close 100% of the position across all tranches. No partial
  stop.
- **(b) Alternatives.** None worth testing.
- **(c) Prescriptive.**
- **(d) Test.** Built into R0.

### 1.11 Rule 10: "Every position gets a wide stop and a take profit of at least 3x the risk"

- **(a) Literal.**
  - Hard stop S = midline_t − 1.0·ATR14_t, using the values on the signal day: below the trend-break
    level, beyond intraday noise.
  - R = entry₁ − S. Take-profit TP = entry₁ + 3R, fixed at entry, and not moved by adds.
  - Stop and TP are resting orders that can fill at any hour. Fills:
    - stop: at S, or at the hourly open if the bar gaps through it;
    - TP: at TP, or at the open if it gaps above.
  - If one hourly bar touches both, assume the stop filled first.
  - Typical sizes, 2025-06..2026-10 [A]: the median distance from the upper band to the midline
    (2σ20/close) and ATR14/close are:

    | coin | 2σ20/close | ATR14/close |
    |---|---|---|
    | BTC | 5.5% | 2.9% |
    | ETH | 9.0% | 4.6% |
    | SOL | 9.9% | 5.4% |
    | BNB | 6.1% | 3.4% |
    | XRP | 8.6% | 5.1% |
    | DOGE | 11.1% | 6.0% |
    | ZEC | 20.0% | 8.9% |

    So R is about 8% for BTC, 14% for ETH and 15% for SOL, and the 3R take-profit is about +25%,
    +41% and +46%.
  - ZEC's R of about 29% is beyond the 5x liquidation distance, so the rule 4 leverage cap applies.
- **(b) Alternatives.**
  - S at the lower band on the signal day: about 2× the band half-width, BTC ≈ 11%, ETH ≈ 18%.
  - S = entry − 2.5·ATR14, or a fixed 10%.
  - TP at 5R, or no TP.
  - Move the stop to the average entry after the second add (Turtle-like).
- **(c) Prescriptive.** But the reported win/loss ratio of 1.4 shows the 3R take-profit rarely
  binds (section 4.1).
- **(d) Test.** Sensitivity rows. Report the share of exits by stop, TP and midline.

### 1.12 Rule 11: "Don't size up after a big month"

- **(a) Literal.**
  - Size from E_size, the equity at the start of the calendar month.
  - If the previous month's return was above +25%, keep the previous month's E_size for one more
    month.
- **(b) Alternatives.**
  - Size from current equity (plain compounding).
  - Size from fixed initial capital (no compounding).
  - Size from min(current equity, equity 3 months ago).
- **(c) Mostly DESCRIPTIVE** (an AI-found pattern: larger sizes after big months did worse, the
  "house money" effect [U]), stated as a prescriptive sizing rule.
- **(d) Test.** Sensitivity only. With about 16-80 months per sample, a monthly conditioning rule has
  almost no power.

### 1.13 Rule 12: "Don't open trades on a Friday or Saturday"

- **(a) Literal.** No new position (first tranche) with a New York-date Friday or Saturday. Adds and
  exits are allowed.
- **(b) Alternatives.** UTC dates; Asia (UTC+8) dates, if the exports were in exchange-local time [U];
  no filter.
- **(c) DESCRIPTIVE / DATA-MINED.**
  - Over about 69 weeks, each weekday has about 69 days and, at about 500 positions, about 70
    entries. The standard error of a weekday's win rate is about √(0.25/70) ≈ 6 percentage points.
    Across seven weekdays the expected gap between the best and worst win rate is about 2.7 standard
    errors, about 16 points, by chance alone.
  - Calendar effects in stocks vanish once the search behind them is accounted for [S].
  - A crypto weekday effect (Monday, BTC only, 2013-17) was not robust in the published version [S].
  - There is a plausible mechanism: weekend liquidity is thin [A]. Hourly |return| is 0.59-0.74× the
    mean on Saturday and 0.76-0.86× on Sunday; volume is 0.57-0.65× and 0.68-0.77×. So breakouts that
    form over the weekend may fail more often. Friday has the most volume (1.20-1.30×) [A].
- **(d) Test.** H7: R0 with vs without the filter, against a **placebo distribution**. Exclude each of
  the 7 pairs of consecutive days in turn; the real pair must rank top of 7 and beat the no-filter
  version net.

### 1.14 Rule 13: "Never open in the 90 minutes before the US open; best entries about 3.5 hours before the open, or 30 minutes after it"

- **(a) Literal.**
  - New positions only at two windows on allowed days: the open of the hourly bar at open − 3.5 h
    (10:00 UTC in EDT, 11:00 UTC in EST), and at open + 30 min (14:00 / 15:00 UTC).
  - Primary: enter at the first window after the signal. If the signal is still valid at a later
    window on the same day, skip that one (one entry per signal).
  - Never 12:00-13:30 UTC (EDT) / 13:00-14:30 UTC (EST).
  - This means 10-11 hours pass between the 00:00 UTC signal and the fill, or days more when a
    Friday/Saturday block applies.
  - Because the open − 3.5 h window always comes first, R0 never uses the open + 30 min window.
    Row S14 (section 1.19) enters only at open + 30 min to test that half of the rule.
- **(b) Alternatives.**
  - Ban only the 90-minute window and enter at the next hourly open after the signal (01:00 UTC).
  - No time filter: fill at the 00:00 UTC open after the signal close.
- **(c) DESCRIPTIVE / DATA-MINED.**
  - The facts: 06:00 New York is among the quietest hours [A]. Mean |hourly return| at
    open − 3.5 h is 0.78× the daily average for BTC, 0.79× for ETH, 0.78× for SOL.
  - The 08:00-09:30 ban covers the 08:30 ET US macro releases (CPI, payrolls) [U] and the build-up to
    the open. That hour runs at 1.02-1.04×, and the hour holding the open at 1.31-1.50×.
  - 10:00 New York begins the most volatile hour of the day (1.63-1.74×; volume share 7.1-7.9% vs
    4.2% average) [A].
  - These are facts about volatility, not about returns. Whether entering at those hours earns more
    was **not** computed (contamination rule).
  - Research: Bitcoin volatility and liquidity are highest around the openings of the major stock
    markets [S]. Hourly *returns* concentrated at 21-23 UTC in Quantpedia's BTC studies; the worst
    hours were 03:00-04:00 UTC [S].
- **(d) Test.** H6: compare windowed entries with:
  - (i) no filter;
  - (ii) a placebo distribution: every pair of distinct entry hours, each with a 90-minute ban placed
    at random, keeping the same "first window after the signal" logic.

  The real windows must beat no-filter net and rank in the top 5% of placebos.

### 1.15 Rule 14: "Do the closing 3.5 to 5.5 hours after the US open; don't close around the US close; set stops wide enough to survive the quiet hours overnight"

- **(a) Literal.**
  - *Discretionary* exits (midline close and Monday-deferred exits) fill at the open of the hour
    starting open + 3.5 h (17:00 UTC EDT / 18:00 UTC EST), 17-18 hours after the 00:00 UTC close
    that gave the signal.
  - Resting stop and TP orders fill whenever touched.
  - "Survive the quiet hours overnight" adds nothing beyond the wide stop of rule 10.
- **(b) Alternatives.** Exit at the 00:00 UTC open right after the signal close. Or exit at a random
  hour as a placebo.
- **(c) DESCRIPTIVE / DATA-MINED.**
  - Open + 3.5..5.5 h has unremarkable volatility (0.95-1.17×) [A].
  - The "quiet overnight" is real for volatility. The New York night hours (open − 9.5..−2.5 h, i.e.
    00:00-07:00 New York) run at 0.73-0.95× [A]. Thin books can still wick through stops.
- **(d) Test.** Inside H6 (exit leg), against a placebo of exit hours.

### 1.16 Rule 15: "Don't cut on Monday just because the weekend went against the trade"

- **(a) Literal.**
  - Midline signals from Saturday's or Sunday's daily close (bars ending Sunday or Monday 00:00 UTC)
    are not acted on.
  - The midline condition is re-checked at Monday's daily close (Tuesday 00:00 UTC). If price is
    still below, exit in Tuesday's exit window.
  - The hard stop still applies.
- **(b) Alternatives.** Evaluate the midline exit only on weekday closes (Mon-Fri bars); or no rule.
- **(c) DESCRIPTIVE**, with a mechanism story: thin weekend liquidity, and a CME gap that often
  "fills" [U].
- **(d) Test.** Inside H8, with a placebo that defers exits from two other consecutive days.

### 1.17 Long-only, or short breakdowns too?

**Long-only primary.** The text speaks only of breakouts "near local highs and all-time highs" and
cuts "when the trend breaks *below* the midline". Both describe longs.

"Right on direction" is the one word that hints at both sides. Exchange futures-grid bots have long,
short and neutral modes [S], so an AI could have computed "direction" for shorts too. A symmetric
variant is therefore an exploratory row: short a close below the lower band within 5% of the 60-day
low; exit on a close above the midline; same sizing and stops mirrored.

It matters for the reconciliation. In the likeliest window (2025-06..2026-10) most majors fell
22-53% (section 4.3), so a short leg could explain a 4.3x that long-only struggles to.

### 1.18 PRIMARY literal-replication rule set (R0)

| element | R0 specification |
|---|---|
| Venue / data | Binance USDT-M perpetuals. Hourly klines and mark-price klines; spot hourly before a perpetual existed. Actual 8-hourly funding (0.01%/8 h assumed before listing, as in `leverage_breakout.py`). |
| Sample | Full 2020-01-01..2026-10-17 (BTC perpetual from 2019-09). Replication window 2025-06-17..2026-10-17. Older window 2024-06-30..2025-10-31 (section 4.4). |
| Universe | BTC, ETH, SOL, one slot each (K = 3, sleeve = E_size/3). Per-asset runs on BNB, XRP, DOGE, ZEC and the 40-coin set. |
| Signal (daily, 00:00 UTC) | C_t > UB(20, 2, population σ) and [C_t ≥ 0.95·max(H, 60 days) or C_t ≥ 0.90·ATH_t]. Long only. |
| Entry | State-based. First allowed window after the signal: open − 3.5 h or open + 30 min (table 1.0). Not on New York Friday/Saturday. Never in open − 90 min..open. Latest completed daily bar must still satisfy the signal. Fill at that hourly bar's open; taker fee plus slippage. |
| Size | Max notional M = L·E_sleeve with L = 3. First tranche M/3. |
| Adds | +M/3 when an hourly close ≥ 1.02·entry₁ and +M/3 at ≥ 1.05·entry₁. Fill at the next hourly open. Never below the average entry. |
| Hard stop | S = SMA20_t − 1.0·ATR14_t at the signal. Resting order; intrabar fill at S or the gap open. Covers all tranches. |
| Take-profit | TP = entry₁ + 3·(entry₁ − S). Resting order; sells 50% of the position. |
| Trend exit | Daily close < SMA20, ignored for 72 h after entry₁ while the position is in profit. Saturday/Sunday closes deferred to Monday's close. Exit 100% at the next open + 3.5 h window. |
| Liquidation | Isolated per tranche. Liquidation price ≈ avg entry × (1 − 1/L + mmr), checked on the hourly mark-price low. Leverage capped per trade so the stop sits ≥ 2 points above liquidation. |
| Sizing equity | E_size = equity at the start of the month, frozen for a month after a month > +25%. |
| Costs | Taker 0.05% + slippage 0.02% (BTC/ETH) or 0.07% (others) per side. Maker 0.02% for grid fills. Funding on notional while held. Idle cash earns T-bills (optional; report both). |
| Grid | **None in R0.** Overlays G-A and G-B are separate variants (Part 2). |

### 1.19 Sensitivity grid (report all; select none)

| # | change from R0 | why |
|---|---|---|
| S1 | no time or day filters (rules 12-15 off); fill at the 00:00 UTC open after the signal | isolates the core; mined rules removed |
| S2 | 1x account level (L = 1: 1/9x of the account per slot at entry, 1x with all slots full) | leverage-free edge |
| S3 | L = 5 isolated; L = 3 cross | rule 4 range; margin mode |
| S4 | no pyramiding: full M at entry | rule 1-2 value |
| S5 | adds as ROE thresholds (2%/5% of margin) | exchange-screen reading |
| S6 | BB(20, 2.5); BB(50, 2); Bollinger's BB(10, 1.9) and BB(50, 2.1); platform BB(10, 1.5) and BB(50, 2.5) | band settings |
| S7 | near-high filter off; 20-day/2%; 365-day/10%; ATH-only | definition of "near highs" |
| S8 | 4-hour bars for signal and exit | timeframe |
| S9 | stop at the lower band; 2.5·ATR | "wide" |
| S10 | one-piece exits: all at TP; or no TP, all on the midline | rule 8 |
| S11 | symmetric long/short | rule 1.17 |
| S12 | point-in-time top-3 / top-6 by perpetual volume | universe without hindsight |
| S13 | Bollinger squeeze pre-condition (BandWidth within 10% of its 125-day low in the prior 10 days) | Method I |
| S14 | entries only at the open + 30 min window (14:00 / 15:00 UTC) | R0 never reaches it (section 1.14) |

**Stocks/ETFs (the user's other assets):** SPY, QQQ, IWM, TSLA, COIN, HOOD, CRCL.
- Use daily bars and the same signal.
- Entry at the next session's 10:00 ET (open + 30 min). Exit at 13:00 ET. The 06:00 ET pre-market
  window is not used.
- No weekend rule beyond Friday. 1x, or 2x Reg-T margin. No grid. Costs from HANDOFF section 4.
- The repo has no intraday bars for these tickers, and the Robinhood connector's 5-minute history
  reaches back only about 7.5 months (HANDOFF 3). Over full history the stock version must fill at
  the next open as a proxy, and say so.

---

## 2. Part 2: the grid bot

### 2.1 How exchange grid bots work

- **Set-up.** The user picks a price range [P_lo, P_hi], a number of grids G, the capital, and on
  futures the leverage, margin mode and direction [S].
- **Spacing:**
  - **arithmetic**: equal price steps (P_hi − P_lo)/G;
  - **geometric**: equal percentage steps, (P_hi/P_lo)^(1/G) − 1 [S].
  - Arithmetic gives a larger percentage profit per grid at the bottom of the range than at the
    top [S].
  - Pionex's own guidance: more grids means more fills and less profit per grid [S].
- **Mechanics (spot grid).**
  - At start the bot buys enough base asset to cover the sell orders above the current price. It
    rests buy limits at each level below and sell limits at each level above.
  - Each fill places the opposite order one level away, so each round trip earns about one spacing,
    minus two fees.
  - Profit per round trip = spacing − 2·fee − slippage. Practitioner rule: a spacing of at least
    2-3× the round-trip fee [S].
- **Futures grid.** Modes are long, short or neutral [S].
  - Neutral starts flat: it shorts on the way up and goes long on the way down.
  - Long holds an initial long, behaving like a leveraged spot grid.
  - Short is the mirror.
  - Per-grid size comes from the investment and leverage. The exchange shows an estimated
    liquidation price that assumes all pending orders fill [S].
  - Users report Binance futures grids at 18-20x [S, user posts]. The maximum leverage per pair was
    not verified [U].
- **Fees** [S, third-party fee tables]:

  | venue | maker | taker |
  |---|---|---|
  | Binance USDT-M, base tier | 0.02% | 0.05% (10% off paid in BNB) |
  | Bybit | 0.02% | 0.055% |
  | Hyperliquid, tier 0 | 0.015% | 0.045% |
  | Pionex spot | 0.05% | 0.05% |
  | Binance spot | 0.1% [U] | 0.1% [U] |

  Grid fills are mostly maker. Funding applies to the futures grid's net inventory.
- **When price leaves the range:**
  - Spot or long grid above the range: sold out, flat in quote currency. It has made only the grid
    profits and missed the rest of the rally.
  - Below the range: fully loaded with base asset, holding a loss like a buy-and-hold bought on the
    way down.
  - Bots typically pause until price returns [S]. "Trailing up" variants move the range up after a
    breakout [S]. Optional stop-loss and take-profit triggers close the bot [S].
  - A futures grid can be liquidated beyond its range [S].
- **Reporting.** Platforms report "grid profit" (realized round trips) separately from "trend P&L" or
  unrealized P&L on the inventory [S]. A summary that counts grid profit as profit makes a bot look
  better than its total P&L.

### 2.2 Why a grid is short volatility (short gamma)

Work in log price x. A grid of total notional N spread over a log range of width W holds an exposure
(in quote currency) that falls linearly as price rises:

X(x) = X₀ − (N/W)·(x − x₀) inside the range, with X₀ = 0 for neutral and X₀ > 0 for long mode.

Its mark-to-market P&L is ∫X dx. Itô's rule gives ∫(x − x₀)dx = ½[(Δx)² − QV], where QV is the
realized quadratic variation. So:

**P&L = X₀·Δx + (N/2W)·QV − (N/2W)·(Δx)² − fees**

1. The **(N/2W)·QV** term is what bots call "grid profit". It grows with realized variance like an
   option seller's theta.
2. The **−(N/2W)·(Δx)²** term is the inventory loss on the *net* move: short gamma, concave in the
   final price, the payoff of a short strangle inside the range.
3. For a driftless martingale, E[(Δx)²] = E[QV]. The expected P&L of a neutral grid is then **zero
   before fees and negative after**. This matches the "zero expectation" result in Chen, Chen & Jang's
   grid-trading preprint (arXiv 2506.11921, 2025), whose model is a symmetric fixed-step walk without
   fees [S].
4. A grid wins when the path oscillates a lot relative to its net displacement (mean reversion,
   ranges). It loses when price trends.
5. Beyond the range the exposure is pinned at its extreme, so losses grow linearly with the overshoot.

A breakout trader's directional book is *long* gamma: convex, with small losses and occasional large
wins. A grid is the opposite profile. "The grid pays while waiting for the move" describes the two
hedging each other's quiet periods. When the move comes, the grid gives back.

**Size of the "grid profit"** for a 3x grid (N = 3 × margin) over a 20% range [A, from realized
hourly variance 2025-06..2026-09]:

| coin | √(hourly RV per day) | grid profit per day on margin, before fees |
|---|---|---|
| BTC | 2.15% | ≈ 0.35% |
| ETH | 3.18% | ≈ 0.76% |
| SOL | 3.56% | ≈ 0.95% |

These are 125-350% a year of displayed "grid profit". Under no drift, an equal inventory loss
offsets them in expectation.

### 2.3 How "1,462 bots" and "$10.7B volume" fit

- **Rates.** 1,462 bots over about 487 days is 3.0 a day. $10.7B over the same period is $22M a day;
  that is $7.3M per bot, or $3.7M per bot per side.
- **Likeliest reading.** Each directional entry *and each add* is its own bot, e.g. a long-mode futures
  grid or a "signal"/CTA bot per tranche [U].
  - About 490 positions × 3 tranches ≈ 1,462.
  - At 3-5 coins that is roughly one new position a day, with about 4 concurrent positions if the
    average hold is about 4 days.
  - A daily-bar band breakout near highs on 3-5 coins fires far less often than once a day,
    especially in a falling market [U, reasoning]. So this reading also needs intraday signals, more
    coins, or bots counted per restart. H11 should report R0's trade count beside 1,462.
  - Then "48.7% right on direction" is the share of bots whose trend P&L was positive. "51.7% closed
    in profit" adds each bot's grid profit, which turns some small directional losers positive.
  - If grid bots were instead a separate set of bots, the 3-point rise implies they were 7-27% of all
    bots at a 90%-60% grid win rate [A, arithmetic].
- **Grid churn produces volume** [A model]. A level crossing happens about RV/s² times a day
  (s = spacing). Volume per day ≈ RV·N/(s·W) (section 6 has the derivation).

  | grid (3x, 20% range) | 16-month volume per $1 of margin |
  |---|---|
  | BTC, 1% spacing | ≈ 340x |
  | BTC, 0.2% spacing | ≈ 1,700x |
  | SOL, 0.2% spacing | ≈ 4,600x |

  Realized variance from 1-, 5- and 15-minute bars is 6-12% above the hourly figure (BTC, ETH and
  SOL, 8 sample months 2025-07..2026-09) [A]. So these figures, and the grid profits in section 2.2,
  understate the finer-spaced grids by up to about 10%.
- **What volume of that size requires:**
  - grid alone: about $2-30M of average grid margin running continuously;
  - directional alone: about 490 positions averaging about $11M notional each.
  - **Neither pins the starting capital.** A start of about $0.5-5M is consistent with both.
- **Turnover** = $10.7B / average equity. Average equity is taken as start × 3.3/ln 4.3 = 2.26 ×
  start, i.e. log-linear growth to 4.3x.

  | start | average equity | volume / average equity | per year |
  |---|---|---|---|
  | $0.25M | $0.57M | 18,900x | 14,200x |
  | $1M | $2.26M | 4,700x | 3,500x |
  | $5M | $11.3M | 950x | 710x |

- **Fees.** At base-tier rates (0.02-0.05%), $10.7B costs $2.1-5.4M, comparable to a 3.3× gain on a
  $1-2M start. The trader would be at a VIP tier with lower fees [U]. A small account would not be.
  **Cost per unit of turnover is decisive for anyone copying this.**

### 2.4 Simulatable grid overlays

- **G-A, "waiting grid"** (primary overlay; leaves R0's trades unchanged):
  - **When.** A slot is flat and the coin is "set up": the last close is within 5% of the 60-day high
    but at or below the upper band.
  - **What.** A *neutral* futures grid, geometric:
    - range = [lower band, upper band] at deployment;
    - spacing s = max(0.5%, 4 × 0.04% round-trip maker fee);
    - margin = E_sleeve/3 (the first-tranche budget), leverage 3.
  - **Ends when:**
    - (i) an R0 entry fires: close the grid at that hourly open, at taker cost, then open the R0
      position;
    - (ii) a daily close below the lower band: stop;
    - (iii) after 14 days: re-centre on the current bands.
  - **Fills.** Simulated on **1-minute** klines with the bar path O→L→H→C if the close is nearer the
    high, else O→H→L→C. Report sensitivity to hourly bars. Funding on net inventory.
  - **Expected result.** The grid shorts into the rise toward the upper band, so its inventory loss
    lands on the breakout (section 2.2).
- **G-B, "grid-wrapped tranches"** (fits the bot counting and the 48.7→51.7 decomposition best):
  - Each R0 tranche is run as a *long-mode* futures grid over [S, TP]: geometric, G = 20, leverage L.
  - At start it holds the inventory for the levels above the current price.
  - It sells a level on each rise and re-buys on each dip. At TP it is sold out; at S it is fully
    loaded and stopped out. The midline exit closes it.
  - This trades the winners' convexity for grid profit, and it averages down inside the bot, which
    conflicts with rule 3. Simulate it to see what it does to the hit rate and win/loss ratio.
- **G-0, grid alone** (benchmark): an always-on neutral grid, ±10%, re-centred weekly, on each coin.
  It shows the overlay's standalone short-volatility P&L.

---

## 3. Part 3: evidence

### 3.1 Bollinger Bands

- **Bollinger's own methods** [S]:
  - Method I, volatility breakout ("the Squeeze"): BandWidth at a multi-month (default 125-bar) low,
    then a break of a band.
  - Method II, trend following: %b and MFI confirmation, no squeeze needed.
  - Method III, reversals: band tags compared with an indicator such as Accumulation/Distribution.
  - Full rules are in *Bollinger on Bollinger Bands* (2001): chapter 16 (Method I), 19 (Method II)
    and 20 (Method III) [S].
  - The tweet's strategy is closest to Method II without the MFI filter, plus a near-high filter.
- **Leung & Chong (2003)**, *Applied Economics Letters* 10(6): 339-341: on G7 and four Asian stock
  indices, Bollinger Bands do **not** beat moving-average envelopes [S].
- **Lento, Gradojevic & Wright (2007)**, *Applied Financial Economics Letters* 3(4): 263-267: after
  costs, bands don't consistently beat buy-and-hold; a *contrarian* (reversed) version did better [S].
- **Fang, Jacobsen & Qin (2017)**, *Journal of Portfolio Management* 43(4) ("Popularity versus
  profitability: evidence from Bollinger Bands"): breakout and squeeze rules on 14 international
  indices, 1885-2014. They were profitable before the 1983 introduction. The breakout rule's average
  daily gross spread fell from about 0.45% before 1983 to about zero after the 2001 book, as US media
  coverage rose [S]. The summaries read say only that the authors expected the decay to show in the
  US, where the bands originated; whether it came there first is [U].
- **Day, Cheng, Huang & Ni (2023)**, *Applied Economics Letters* 30(11): bands on bitcoin futures.
  Holding-period returns are above 20%, and above 50% with a 60-day average. The abstract gives no
  cost or risk adjustment [S].
- **Gerritsen, Bouri, Ramezanifar & Roubaud (2020)**, *Finance Research Letters* 34, 101263: seven
  trend rules on BTC 2010-2019. Trading-range breakout stands out, mainly in strongly trending
  markets. A secondary summary says Bollinger-type rules underperformed [S].
- **Hudson & Urquhart (2019/2021)**, *Annals of Operations Research* 297: about 15,000 rules in five
  classes, including channel breakouts, on 5 crypto series. Significant predictability in-sample;
  **none out-of-sample for Bitcoin** [S].
- **This repo** [A]: Donchian/Turtle breakouts carry about the same trend exposure as the user's
  indicator, not better (paired t 0.07). Their positive expectancy comes from the top 5% of trades,
  from 2020-21. 4-hour bars are worse than daily (HANDOFF 5.14).

### 3.2 Time-series momentum / trend in crypto

- **Liu & Tsyvinski (2021)**, *Review of Financial Studies*, "Risks and Returns of Cryptocurrency":
  strong time-series momentum in crypto, plus investor-attention predictors [S]. The horizon of about
  1-4 weeks is [U].
- **Zarattini, Pagani & Barbon (2025)**, SFI working paper "Catching Crypto Trends" [S]:
  - an ensemble of Donchian channels with volatility sizing on a rotating top-20 liquid-coin universe;
  - survivorship-free (every coin traded since 2015), with ≥ $2M median daily volume over the prior
    30 days [S]; a minimum listing age is [U];
  - net Sharpe above 1.5 and alpha 10.8% a year vs BTC.
- **This repo** [A]:
  - The daily indicator beats crypto buy-and-hold before costs (HANDOFF 0.3).
  - Pre-registered "crypto trend × volatility target" and "crypto 4-week momentum" fail their
    benchmarks (HANDOFF 5.16).
  - Crypto bear phases are 28-45% of the time with median −64% declines, which is where trend timing
    earns (HANDOFF 5.17).

### 3.3 Pyramiding (adding to winners)

- **No academic study of pyramiding as such was found** in this session's searches [S, negative
  result]. The canonical practice is the Turtle rules: volatility units, adds at fixed favourable
  intervals, at most 4 units, the stop tightened per add [S].
- **Mechanically** [U, reasoning], pyramiding makes exposure a rising function of the open profit.
  - It pays when post-breakout returns are positively autocorrelated: the condition under which
    Kaminski & Lo show stop rules add value.
  - It costs in choppy markets: the adds come near local tops and are then cut by the midline exit.
  - Compared with the full size at entry, it trades a lower average loss (1/3 size on failed
    breakouts) against higher average entry prices on winners. The net is empirical, hence H3.

### 3.4 Stops

- **Kaminski & Lo (2014)**, *Journal of Financial Markets* 18: 234-254. Under a random walk, simple
  stop-loss rules always lower expected return. With momentum (positive serial correlation) they can
  add value [S].
- **This repo** [A]: tight stops lowered expectancy, 2.7% vs 10.3% per trade, with 89% stopped out
  (HANDOFF 5.14). This supports "wide" stops.

### 3.5 Intraday and weekday seasonality in crypto

- **Eross, McGroarty, Urquhart & Wolfe (2019)**, *Research in International Business and Finance*
  [S]: BTC volatility and liquidity peak at the openings of the major stock markets. Volume falls from
  about 16:00 to midnight. The patterns shift over time.
- **Quantpedia (Padyšák & Vojtko)** [S]: BTC hourly returns concentrated at 21:00-23:00 UTC (Gemini
  data, 2015-10..2022-02). The worst hours were 03:00-04:00 UTC, and Friday was the best day for the
  21:00-23:00 trade. Weak in bear markets.
- **Shen, Urquhart & Wang (2022)**, *Financial Review*: the first half-hour return predicts the last
  half-hour [S].
- **Caporale & Plastun (2019)**, *Finance Research Letters*: a Monday effect in BTC only (2013-17).
  Simulated profits were mostly not significantly different from random [S].
- **Sullivan, Timmermann & White (2001)**, *Journal of Econometrics* 105: calendar effects (weekday,
  month, holiday) lose significance once judged against the universe of rules searched [S].
- **Descriptive facts here, 2025-06..2026-09** [A]. Mean |hourly return| relative to the daily
  average, by hour relative to the 09:30 New York open (bar start; −0.5 is the bar containing the
  open):

  | hour vs open | BTC | ETH | SOL | volume share (BTC) |
  |---|---|---|---|---|
  | −9.5..−4.5 (00:00-05:00 New York) | 0.79-0.95 | 0.77-0.91 | 0.81-0.94 | 3.1-4.2% |
  | −3.5 (06:00, "best entry") | 0.78 | 0.79 | 0.78 | 3.3% |
  | −2.5 (07:00) | 0.80 | 0.79 | 0.73 | 3.5% |
  | −1.5 (08:00, banned) | 1.04 | 1.03 | 1.02 | 4.6% |
  | −0.5 (09:00, contains the open) | 1.50 | 1.46 | 1.31 | 6.8% |
  | +0.5 (10:00, "best entry") | 1.74 | 1.68 | 1.63 | 7.8% |
  | +1.5 | 1.36 | 1.40 | 1.36 | 6.6% |
  | +3.5 / +4.5 / +5.5 (closing window) | 1.12 / 0.96 / 0.95 | 1.17 / 0.99 / 0.99 | 1.15 / 1.00 / 0.99 | 3.9-4.6% |
  | +6.5 (16:00, US close) | 0.92 | 1.00 | 0.98 | 3.2% |

  By weekday (UTC days), hourly |return| and volume relative to the mean:

  | coin | Mon-Fri |r| | Sat |r| | Sun |r| | Fri volume | Sat volume |
  |---|---|---|---|---|---|
  | BTC | 1.09-1.17 | 0.59 | 0.76 | 1.30 | 0.57 |
  | ETH | 1.08-1.15 | 0.64 | 0.82 | 1.25 | 0.58 |
  | SOL | 1.05-1.13 | 0.74 | 0.86 | 1.20 | 0.65 |

  So rule 13's "best" pre-open entry is among the quietest hours (the quietest for BTC), and its
  post-open entry starts the noisiest one. Rules 13-14 cannot be justified from volatility alone. Their return content is H6.

### 3.6 Perpetual fees and funding

- **Fees:** see the table in section 2.1 (Binance 0.02%/0.05%, Bybit 0.02%/0.055%, Hyperliquid
  0.015%/0.045%) [S].
- **Funding formula (Binance).** Every 8 hours: premium index + clamp(0.01% − premium, ±0.05%). So the
  rate sits at the 0.01%/8 h interest default (10.95% a year) unless the premium is large [S].
  Hyperliquid funds hourly [S].
- **Realized funding, Binance USDT-M, annualized % of notional paid by longs** [A]:

  | | BTC | ETH | SOL | BNB | XRP | DOGE | ZEC |
  |---|---|---|---|---|---|---|---|
  | 2024 | 11.9 | 13.0 | 13.6 | −3.3 | 14.2 | 14.0 | 14.6 |
  | 2025 | 5.1 | 4.9 | 0.4 | −2.1 | 3.5 | 4.3 | −17.6 |
  | 2026 Jan-Sep | 2.9 | 1.9 | −1.1 | 2.9 | −0.3 | 3.0 | −3.0 |
  | 2025-06..2026-09 | 4.0 | 3.3 | −0.2 | 1.9 | 1.9 | 3.9 | −5.9 |
  | 2024-07..2025-10 | 6.2 | 6.6 | 3.1 | −0.5 | 6.2 | 6.5 | −5.0 |

  - At 3-5x notional, a long held through 2024-like funding pays 36-73% of equity a year while in
    the position.
  - In the likeliest window it pays 10-20% of equity a year for BTC and ETH.
  - Funding was negative at times, so longs were paid and shorts paid: BNB for most of 2024-25, ZEC
    in 2025, SOL in 2026. The most negative 8-hour prints since 2025-06 were −0.30% (SOL, 2025-10-11)
    and −0.40% (ZEC, 2025-11-06).
  - HANDOFF 5.14's "8-12 points a year" is the gap between 1x perpetual and 1x spot over 2018-2026,
    which includes about 31% a year of BTC funding in 2021 (FINDINGS, 2026-10-14). Realized funding
    was 12-15% a year in 2024 (BNB excepted) and much lower since 2025.

### 3.7 Leverage and liquidation

- **Isolated margin.** Liquidation when the position's own margin minus loss falls below maintenance.
  For a long, approximately entry × (1 − 1/L + mmr), driven by the **mark** price, not the last
  trade [S]. Exact values depend on the maintenance tiers by position size [S].
- **Cross margin.** All free equity backs every position. Liquidation comes later per position, but
  one bad position can take the whole account.
- **2025-10-10/11, the largest liquidation event recorded: about $19B** [S]. Binance spot intraday
  low vs the prior close on 2025-10-10 [A]:

  | BTC | ETH | SOL | BNB | XRP | DOGE | ZEC |
  |---|---|---|---|---|---|---|
  | −16.2% | −21.4% | −23.6% | −31.5% | −55.2% | −61.8% | −30.6% |

  - Spot wicks overstate the perpetual mark price. Binance reimbursed $283M for mispriced-collateral
    liquidations [S].
  - Even so, a 5x long (liquidation about −19.6%) was at risk on every coin except BTC, and a 3x long
    (about −33%) on XRP and DOGE.
  - In 2025-06..2026-10 the intraday low was more than 19.7% below the prior close on 0-2 days per
    major coin and 7 days for ZEC [A].
- **Volatility drag** [A]. Daily-rebalanced leveraged buy-and-hold, no funding (section 4.3 table).
  At 5x the result is ≈ 0 for most coins in every window. 3x beat 1x only in the window ending
  2025-10, on BTC, BNB, XRP and ZEC, where the trend was strong relative to volatility.
- **This repo** [A]: 3x on the indicator blows up 85% of 20 coin sub-accounts, 5x all of them.
  Kelly-optimal leverage ≤ 1.85 on every coin (HANDOFF 5.14).

### 3.8 Selection and survivorship of performance posts and "AI breakdowns"

- **Finfluencers** (Kakhbod, Kazempour, Livdan & Schürhoff; 29,000 StockTwits accounts) [S]:
  - 28% skilled, 16% unskilled, 56% *antiskilled*;
  - the unskilled and antiskilled have **more** followers and influence;
  - fading them earned about 1.2% a month.
- **Barber, Lee, Liu & Odean (2014)**, *Journal of Financial Markets* 18: fewer than 1% of Taiwanese
  day traders earn predictable positive abnormal returns net of fees [S].
- **Apesteguia, Oechssler & Weidenholzer (2020)**, *Management Science* 66(12): seeing others' success
  raises risk-taking, and the option to copy raises it further [S].
- **Survivorship** [U, reasoning]:
  - Leveraged accounts that blew up in October 2025 do not post 16-month breakdowns.
  - Among thousands of bot accounts, some will show 4.3x by chance, especially at 3-5x.
  - Copy-trading leaderboards rank by realized ROI and drop closed accounts.
- **The "AI breakdown" step** adds a forking-paths problem [U, reasoning]:
  - An LLM given a trade log will report whichever cuts look different (weekday, hour, holding time,
    size after big months) and phrase them as rules.
  - With about 500 positions and dozens of implicit cuts, several spurious "rules" are expected.
  - Holding-time statistics are mechanically linked to the exit rule (rule 6).
  - The post gives no costs, drawdown, leverage-adjusted risk or benchmark.

---

## 4. Part 4: reconciling the reported statistics

### 4.1 Expectancy from the hit rate and the win/loss ratio [A, arithmetic]

- **Per trade.** With p = 0.487 and b = W/L = 1.4: E = p·b − (1 − p) = **+0.169 L** per trade
  (L = average loss).
  - Profit factor 0.487·1.4/0.513 = **1.33**.
  - Break-even p at b = 1.4: **41.7%**. Break-even b at p = 0.487: **1.05**.
  - With the grid-inclusive 51.7% (if b stays 1.4): E = +0.241 L, profit factor 1.50.
- **Kelly** for this binary bet: f* = p − (1 − p)/b = **12.1%** of equity lost per losing trade. Log
  growth is 0.0100 per trade, so about 145 independent Kelly-sized trades reach 4.3x.
- **Loss size implied by the number of independent positions N** (binary model, log growth
  ln 4.3 = 1.459):

  | N | loss per losing trade | average win |
  |---|---|---|
  | 150 | 9.9% of equity | 13.8% |
  | 300 | 3.4% | 4.7% |
  | 500 | 1.9% | 2.6% |
  | 1,462 | 0.6% | 0.85% |

  If the midline exit loses about 3-8% of price, a 1.9% loss of equity means an account-level
  notional of about 0.25-0.65× equity per losing position. So a "3-5x" setting is consistent with modest real exposure per position.
- **A 3R take-profit is not what produced b = 1.4.** If losers hit the stop at −1R and winners the
  +3R target, b would be about 3 and E about +0.95R. With losses capped near 1R (gaps aside), an
  average win of 1.4× the average loss is at most about 1.4R. So at most about 47% of winners can have
  reached +3R, and fewer if the average loss is below 1R. Most winners must leave on the midline exit
  at fractions of R. R0 keeps the take-profit as written. Section 1.19, row S10, shows whether it
  matters.

### 4.2 Hit rate with and without the grid

- **Separate grid bots.** 0.487 → 0.517 if grid bots are 7%, 10%, 14% or 27% of all bots at a grid
  win rate of 90%, 80%, 70% or 60%.
- **Grid-wrapped bots (G-B).** About 3% of bots (about 44) were directional losers turned into net
  winners by their grid profit.

### 4.3 Buy-and-hold over plausible 16-month windows [A]

Binance spot daily closes. "3x/5x d-reb" means daily-rebalanced leverage, no funding or fees; 0 means
a day with a return ≤ −1/L. "Best leg" is the largest rise from a running low to a later close inside
the window. MDD is the maximum drawdown of closes.

| window | | BTC | ETH | SOL | BNB | XRP | DOGE | ZEC |
|---|---|---|---|---|---|---|---|---|
| 2024-06-30..2025-10-31 | buy & hold | 1.75 | 1.12 | 1.28 | 1.87 | 5.27 | 1.50 | 19.3 |
| | 3x / 5x d-reb | 2.34 / 1.03 | 0.17 / 0.00 | 0.10 / 0 | 2.10 / 0.46 | 6.05 / 0.02 | 0.06 / 0 | 39 / 0 |
| | best leg / MDD | 2.31 / −28% | 3.28 / −63% | 2.35 / −60% | 2.82 / −29% | 8.46 / −45% | 5.04 / −70% | 22.1 / −61% |
| 2025-02-28..2026-06-30 | buy & hold | 0.70 | 0.70 | 0.50 | 0.93 | 0.49 | 0.36 | 10.6 |
| | 3x / 5x d-reb | 0.15 / 0.01 | 0.04 / 0.00 | 0.01 / 0 | 0.28 / 0.02 | 0.01 / 0.00 | 0.00 / 0 | 0.64 / 0 |
| | best leg / MDD | 1.63 / −53% | 3.28 / −68% | 2.35 / −75% | 2.46 / −58% | 1.98 / −71% | 2.03 / −75% | 24.0 / −72% |
| 2025-04-30..2026-08-31 | buy & hold | 0.83 | 1.38 | 0.70 | 1.15 | 0.63 | 0.48 | 23.5 |
| | 3x / 5x d-reb | 0.29 / 0.03 | 0.43 / 0.01 | 0.05 / 0.00 | 0.57 / 0.06 | 0.04 / 0.00 | 0.01 / 0 | 6.6 / 0 |
| | best leg / MDD | 1.37 / −53% | 2.69 / −68% | 1.88 / −75% | 2.23 / −58% | 1.76 / −72% | 1.91 / −76% | 24.6 / −72% |
| **2025-06-17..2026-10-17** | buy & hold | **0.78** | **0.96** | **0.70** | **1.11** | **0.60** | **0.47** | **27.4** |
| | 3x / 5x d-reb | 0.23 / 0.02 | 0.17 / 0.00 | 0.05 / 0.00 | 0.50 / 0.05 | 0.03 / 0.00 | 0.01 / 0 | 7.0 / 0 |
| | best leg / MDD | 1.48 / −53% | 2.17 / −68% | 1.96 / −75% | 2.12 / −58% | 1.76 / −72% | 1.91 / −76% | 47.7 / −72% |

- **Equal-weight baskets, no rebalancing.** The six majors: 2.13x / 0.61x / 0.86x / 0.77x for the
  four windows. Adding ZEC: 4.59x / 2.04x / 4.10x / **4.57x**. A plain equal-weight hold *including
  ZEC* matches "4.3x" over the latest 16 months, entirely through ZEC.
- **Window ending 2026-09-30** (start 2025-05-30): BTC 0.80x, ETH 1.06x, BNB 1.17x, ZEC 30x.
- **Annualized volatility** in the latest window: BTC 42%, ETH 64%, SOL 69%, BNB 49%, XRP 66%,
  DOGE 75%, ZEC 143% [A].
- **Highs inside the windows** [A]:
  - Binance-data highs at or above the prior ATH: BTC in 2024-Q1, 2024-Q4 and every quarter of 2025
    (peak 126,200 on 2025-10-06); ETH 2025-Q3 (4,957 on 2025-08-24); BNB 2024-Q2/Q4 and 2025-Q3/Q4
    (1,375 on 2025-10-13); XRP 2024-Q4, 2025-Q1 and 2025-Q3 (3.66 on 2025-07-18); SOL 2024-Q4 and
    2025-Q1 (295.8 on 2025-01-19); ZEC 2025-Q4 and 2026-Q3 (1,698 on 2026-09-26).
  - DOGE made none.
  - Binance histories start in 2017-2019, so XRP's January 2018 and ZEC's 2016 highs are missing
    from them [U]. "ATH" needs the longest history available.

### 4.4 What leverage × exposure gives 4.3x

- **Fixed-notional leverage needed to turn one full best up-leg into 4.3x**, i.e.
  L = 3.3/(leg − 1), in the window ending 2026-10-17 [A]:

  | BTC | ETH | SOL | BNB | XRP | DOGE | ZEC |
  |---|---|---|---|---|---|---|
  | 6.9x | 2.8x | 3.4x | 2.9x | 4.3x | 3.6x | 0.07x |

- **Share of that leg that must be captured:**
  - at 3x: ETH 94%, BNB 98%, SOL 114%, DOGE 121%, XRP 145%, BTC 230%;
  - at 5x: ETH 57%, BNB 59%, SOL 69%, DOGE 72%, XRP 87%, BTC 138%.
- **In the latest window** a long-only 3-5x breakout trader needs one of these:
  - 94-114% at 3x (57-69% at 5x) of one best leg, with little given back in the bear market. The
    legs are the June-August 2025 ETH rally, the June-October 2025 BNB rally and the June-September
    2026 SOL rebound [A];
  - several such legs across coins at once (account-level exposure up to 3-5x);
  - ZEC exposure, at 1x or less;
  - a short leg.

  Breakout entries miss the first part of each leg and midline exits miss the last part, so full
  capture is unusual. **4.3x in this window is demanding, but not impossible with 3-5x and
  concurrent legs.**
- **In the window ending 2025-10:** BTC alone at 3x daily-rebalanced made 2.34x, BNB 2.10x, XRP 6.05x.
  At a fixed 3x, 4.3x there needs 84% of BTC's best leg (2024-09..2025-10), 48% of ETH's, 82% of
  SOL's or 61% of BNB's (29-50% at 5x), or 15% of XRP's [A]. That is much less demanding than the
  latest window.

### 4.5 The likely 16-month window

**Most likely: about 2025-05/06 to 2026-09/10 [U]**:
1. The user "just saw" the post, today is 2026-10-18, and AI trade-log breakdowns are a 2026 format.
2. That window contains the July-October 2025 ATH breakouts (BTC, ETH, BNB, XRP) that the description
   centres on.
3. It contains the 2025-10-10 crash and the following bear market. That fits "direction is wrong
   more often than right" and a rule like "don't size up after a big month".
4. A "near local highs" breakout style also fits the July-September 2026 rebound, with new ZEC highs
   in September 2026.

**Not excluded:** about 2024-06 to 2025-10, a post first written a year ago and resurfacing. There,
4.3x is much easier at 3-5x, above all with XRP (section 4.4). The two windows imply very different skill (section 4.4).
The tests should report R0 on both and on the full 2020-2026 sample. The tweet date cannot be
established from this sandbox.

### 4.6 Volume

See section 2.3. At any plausible start of $0.25-5M, $10.7B is 950-19,000× average equity. Only grid
churn or very frequent leveraged round trips produce that, and fees are then of the same order as the
reported profit unless the account is at a high VIP or maker tier.

---

## 5. Hypotheses and pitfalls

### 5.1 Pre-registrable hypotheses (suggested; the orchestrator fixes the final list and thresholds)

- **H1, core edge.**
  - R0-core, which is S1: no time or day filters, 1x account level (S2), no grid.
  - Pooled mean net trade return on BTC/ETH/SOL 2020-01..2026-10 > 0 with t ≥ 2 (trades clustered by
    month).
  - It must also be positive on the 40-coin survivorship-inclusive set and in both halves of the
    sample.
- **H2, vs benchmarks.** R0-core's Sharpe beats equal-weight buy-and-hold and this repo's daily
  indicator on the same coins. Block bootstrap; Holm across the H family.
- **H3, pyramiding.** 1/3 + adds at +2%/+5% beats the full size at entry on mean net return per unit
  of *maximum* exposure (and on Sharpe), with the same signals and exits.
- **H4, confirmation.** Close-confirmed entries beat intrabar band-touch entries (prior-bar band) per
  trade net.
- **H5, near-high filter.** Breakouts within 5% of the 60-day high or 10% of the ATH beat breakouts
  away from highs per trade net (split inside S7's "filter off" run).
- **H6, hour-of-day rules 13-14.** The windowed entries and exits beat the S1 timing, and rank in the
  top 5% of the placebo-hours distribution. **Expected: fail.**
- **H7, weekday rule 12.** Excluding Friday/Saturday entries beats no filter, and ranks first among
  the 7 consecutive-day-pair exclusions. **Expected: fail.**
- **H8, minimum hold and Monday deferral (rules 6, 15).** Each improves per-trade net return vs off.
  **Expected: fail.**
- **H9, leverage.**
  - R0 at 3x and 5x (isolated, mark-price liquidation, funding) has a lower Sharpe than 1x.
  - 5x is liquidated at least once in 2020-2026 on at least one of BTC/ETH/SOL.
  - The probability of a −50% account drawdown is higher at 3x than at 1x.
  - Replicates HANDOFF 5.14's direction.
- **H10, grid overlay.** G-A adds positive net P&L to R0 (after fees, funding and termination
  losses). **Expected: ≤ 0** by section 2.2. G-B is exploratory.
- **H11, consistency check (descriptive, no pass/fail on edge).** In the 2025-06..2026-10 window,
  report R0's hit rate, win/loss ratio, share of trades held > 7 days that won, and multiple. **Do not
  tune anything to match 48.7%, 1.4, 75% or 4.3x.**
- **H12, shorts (exploratory).** The symmetric long/short version (S11) improves on long-only in the
  2025-06..2026-10 window but not over 2020-2026.

### 5.2 Pitfalls

1. **Look-ahead in breakout fills.**
   - The upper band contains today's close, so a "close above the band" is known only at the close.
     Fill at the next hourly open or the window, never at the same close.
   - An intrabar entry must use the *prior* bar's band.
   - The near-high and ATH maxima must exclude the future. ATH from the longest history available at
     t; Binance histories start late.
2. **Intrabar ordering.** In a bar touching both the stop and the TP, assume the stop first.
   - Gaps fill at the open.
   - Hourly bars hide sub-hour wicks. Grid fills need 1-minute bars plus a stated path assumption.
3. **Liquidation modelling.**
   - Use the perpetual **mark** price (archive `markPriceKlines`), not spot wicks.
   - Include the maintenance tier, liquidation fee, and the 2025-10-10 dislocation (Binance's own
     mispricing, auto-deleveraging elsewhere).
   - Isolated vs cross changes outcomes; report both.
4. **Funding.** Use the actual prints at their actual interval. The seven coins here were 8-hourly
   throughout 2024-01..2026-09 [A]; Binance has moved some other coins to 4-hourly at times [U]. Funding regimes differ
   sharply: 2024 about 12-14% a year at 1x vs 2026 about 0-3%.
5. **Costs and fee tiers.** The trader's VIP or maker tier isn't the user's. Grid results are
   dominated by fees per fill. Show results at base-tier and at zero-fee to separate edge from fee
   advantage.
6. **Survivorship of coins.**
   - "A few liquid coins" chosen in 2026 are survivors. Use point-in-time volume ranks and keep
     LUNA, FTT and MATIC/POL.
   - ZEC's 27x in the latest window will dominate any ZEC-inclusive aggregate; report with and
     without it.
7. **Fitting to the reported statistics.** Don't choose BB(n, k), thresholds or windows to reproduce
   48.7%, 1.4, 75% or 4.3x. With 14 sensitivity rows plus filters, some row will match by chance.
   Pre-register R0 and treat the grid as reporting only.
8. **Multiple testing.** The 15 rules come from an AI search over one trader's 16 months. Test the
   mined rules (6, 11-15) only against placebo filters, with Holm or Benjamini-Hochberg across H6-H8.
9. **Sample size and dependence.**
   - 16 months is one bull-to-bear cycle. Breakout trades on BTC/ETH/SOL are highly correlated, so
     the effective N is far below the trade count; cluster by date.
   - Most crypto breakout profit in this repo came from 2020-21 (HANDOFF 5.14).
10. **Time-zone and DST errors.** Convert US-open-based windows with the DST calendar. Decide whether
    "Friday" is a New York, UTC or exchange-local date before running.
11. **Vehicle reality for this user** (HANDOFF sections 1, 10; Robinhood crypto about 0.95% a side):
    - US residents generally cannot use Binance.com, Bybit, Bitget or OKX perpetuals and bots [U].
    - The US options are narrower. Since July 2025 Coinbase Financial Markets has offered
      CFTC-regulated perpetual-style BTC and ETH futures to US customers, at up to 10x [S].
      Pionex.US offers spot grid bots, with access varying by state [S].
    - On Robinhood spot crypto a grid or pyramid at about 0.95% a side is uneconomic.
    - Each grid fill on spot is a taxable disposal.
    - A positive backtest on Binance perpetuals would therefore be tradable by the user only in part
      (BTC/ETH on Coinbase's US contracts), and not on Robinhood. Say so in the verdict.

---

## 6. How the descriptive numbers were computed

- **Daily data.** `data/crypto_binance_regime/<SYM>USDT.csv`, extended with Binance spot daily klines
  2026-10-01..17 (`data/bbreplica/rules_desc/daily_oct2026/`).
  - Buy & hold = close(end)/close(start), where start = end − 16 calendar months (first close on or
    after).
  - Leveraged d-reb = ∏(1 + L·r_t); 0 if any 1 + L·r_t ≤ 0.
  - Best leg = max_t close_t / min_{s≤t} close_s. MDD from closes.
  - Volatility = std(daily log return) × √365.
  - ATH = running max of daily highs in the Binance file.
- **Band width and ATR.** 2σ20/close (population σ) and Wilder ATR14/close, medians and 10th/90th
  percentiles over 2025-06-17..2026-10-17. These are indicator levels only. Nothing is conditioned on
  a signal.
- **Funding.** `data/futures/um/monthly/fundingRate/<SYM>/` 2024-01..2026-09
  (`data/bbreplica/rules_desc/funding/`). Annualized = Σ(rate)/days × 365. "% positive" = share of
  prints > 0.
- **Hourly.** `data/spot/monthly/klines/<SYM>/1h/` 2025-01..2026-09
  (`data/bbreplica/rules_desc/hourly/`), used 2025-06-01..2026-09-30.
  - Bars are grouped by New York local time of the bar start, minus 09:30.
  - Mean |log return| and mean quote volume per group, relative to the overall mean.
  - Weekday groups use UTC dates.
  - No return means by hour or weekday were computed.
- **Grid model.** Fills per day ≈ RV_day/s². RV_day is the mean of daily Σ(hourly log return)²:
  BTC (2.15%)², ETH (3.18%)², SOL (3.56%)².
  - Volume per day = fills × N/G, with G = W/s and N = 3 × margin, W = 20%.
  - Grid profit per day = N·RV/(2W).
- **Expectancy, Kelly and implied loss.** Binary model with p = 0.487 and b = 1.4. Per-trade growth
  g(f) = p·ln(1 + b·f) + (1 − p)·ln(1 − f), solved for N·g(f) = ln 4.3.
- **Sub-hour variance check (added by the checker).** Binance spot 1-minute klines for BTC, ETH and
  SOL, months 2025-07, -09, -11, 2026-01, -03, -05, -07 and -09 (`data/bbreplica/rcheck_m1/`).
  Realized variance per day from 1-, 5-, 15-minute and 1-hour log returns, dropping returns that span
  the gaps between months. 1-minute vs hourly: 1.08 (BTC), 1.11 (ETH), 1.12 (SOL); 15-minute vs
  hourly: 1.06.
- **Leg dates and capture shares.** Best leg = the running-low-to-later-close maximum of section 4.3,
  with its start and end dates. Share needed = 3.3/(L·(leg − 1)) at L = 3 and 5.

---

## 7. Check corrections (2026-10-18)

An adversarial check re-ran every descriptive script. All of the section 4.3 table, the funding table,
the band/ATR table, the hour and weekday tables, the 2025-10-10 lows, the volumes, the Kelly and
implied-loss figures, the grid-volume model and the turnover table reproduced to the stated rounding.
It also checked each citation by search. Changes made:

1. Section 0 and 4.4: "4.3x is easy" in the window ending 2025-10 replaced by the capture shares
   (48-84% of the best BTC/ETH/SOL leg at 3x, 15% of XRP's).
2. Section 0: 5x daily-rebalanced loss "at least 94%" corrected to 93% (BNB to 2026-08 is 0.062x).
3. Section 0, 4.1: "the take-profit rarely binds" replaced by the bound it supports (at most about 47%
   of winners at +3R).
4. Section 0, 1.7: "only winners survive a week" softened; the literal rule-6 coding is close to a
   no-op under R0, and the binding alternative is named.
5. Table 1.0: EDT end dates corrected (2025-11-02 and 2026-11-01 are already EST in daytime).
6. Section 1.1: `data/tv_full` is close-only and cannot supply highs; the ATH gaps for XRP and ZEC are
   stated.
7. Section 1.1, S6: BB(10, 1.5) and BB(50, 2.5) are charting-platform pairs; Bollinger's own are
   BB(10, 1.9) and BB(50, 2.1).
8. Sections 1.2, 1.5, S2: per-slot exposure is L/3 *of the sleeve* at entry (L/9 of the account).
9. Section 1.13: the chance spread across seven weekdays is about 16 points (2.7 SE), not ±12.
10. Section 1.14, S14: the fill comes 10-11 h after the signal, not 10-15 h; R0 never uses the
    open + 30 min window, so S14 was added.
11. Section 1.15: exit timing stated as 17-18 h after the signal close.
12. Section 2.1: the Binance futures-grid leverage cap downgraded to [U].
13. Section 2.3: "lower bounds" quantified (sub-hour variance is 6-12% above hourly); the
    one-position-a-day reading flagged as hard to reach with daily signals.
14. Section 3.1: Bollinger chapter numbers corrected; Fang et al.'s "decline came first in the US"
    downgraded to [U], with the sample and spread figures added.
15. Section 3.2: Zarattini et al.'s universe filter corrected; the listing-age condition is [U].
16. Sections 1.14, 3.5: Quantpedia's "no statistically negative hour" not found; the worst hours
    (03:00-04:00 UTC) and the Friday finding added. 06:00 New York is the quietest hour for BTC only.
17. Section 3.6: the negative-funding sign corrected (longs were paid). HANDOFF 5.14's 8-12 pts/yr
    identified as the 2018-2026 perp-vs-spot gap. Funding cost stated as % of equity.
18. Section 3.7: 3x beat 1x only in the window ending 2025-10, and on BNB too.
19. Section 4.4: leg dates corrected (SOL's best leg is the 2026 rebound; BNB's runs to October 2025).
20. Section 5.2: the funding-interval claim tagged; US access updated (Coinbase US perpetual-style
    BTC/ETH futures, Pionex.US spot grids); the sensitivity-row count is now 14.
21. Section 1.19: no intraday stock bars exist for the historical stock version.
