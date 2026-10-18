# Scalping Low-Volume Markets Did Not Pay in Any Test

**Question (2026-10-17).** A friend scalps low-volume stocks. He "looks for low volume stocks and invests a large amount with the goal of capturing small increases in price or trying to buy at the bid and sell at the ask", and says he makes money. Is this a strategy, which variants are worth testing, and does having a lot of capital help?

**Short answer: no tested version showed an edge, and capital makes it worse.** The closest test of his literal rule in US stocks, on 5-minute bars, was inconclusive, because bars without quotes cannot simulate it.

The repository tested both readings of the friend's description:
- buying at the bid and selling at the ask (market making);
- buying thin stocks that are moving and selling a little higher (attention or momentum trading).

There were 36 pre-registered tests in two markets (crypto, and US stocks on daily and 5-minute bars), plus over 300 exploratory variants. Not one test passed:
- **32 of 36 were "no edge"**: even the optimistic end of the confidence interval is below a small economic threshold.
- **The other 4 were "inconclusive"**: the 5-minute-bar test, which failed its own positive control (a limit of the rule on bars, not a code bug). The registered rule cannot earn the spread even in a no-information market.

Three findings carry the answer:
1. **The spread is not profit.** In the one market with a complete trade record (Binance spot crypto, 270 pairs, 10,121 pair-days), under the strict fill rule used, a passive order resting at the best bid or ask fills only when an order trades through its price, and those fills come just before the price moves against it. That rule is pessimistic by construction, but even an optimistic fill rule loses on average (see 3a).
   - A maker captures +1.3 to +5.9 bp of spread per fill but loses 4.8 to 19.2 bp to the move that follows.
   - Net of a zero maker fee, that is −4 to −18 bp per dollar traded in every liquidity band.
2. **In low-volume US stocks the spread is too wide to pay.** Buying sellers' dips, or the friend's bid-and-ask rule run once a day, was tested on 2001-2020 and 2023-2026 data:
   - every pre-registered variant loses 0.6% to 7.3% per trade in 2001-2020 after spreads and price impact (1.0% to 12.7% in 2023-2026);
   - before costs, the one-day reversal is no larger than bid-ask bounce mechanically creates (once obvious data glitches are excluded), and what lasts beyond the bounce day is at most about 0.1% a trade even with no costs at all.
3. **Large size is a disadvantage.**
   - A thin stock's volume caps how much you can trade: a $1M budget aimed at the thinnest band could keep only about $420k working.
   - Bigger orders lose more per dollar.
   - A paper mark overstates what a large position can actually be sold for: for buyers of 5-100% of a day's volume, by a median 1-5 percentage points of the position (bands L1-L4). Most of that gap is the cost of selling, which a mark ignores; the part that grows with size is about 1-2 points.

The friend's profits are more likely one of the following:
- luck in a strong market;
- attention-momentum trades that happened to work;
- mark-to-market gains his own buying created.

Ask him for 12 months or more of closed-trade results from broker statements, net of costs, compared with the S&P 500. For an intraday rule like his, even that may not separate skill from luck: with the day-to-day swings of the simulated intraday rule (C1), a trader earning 25% a year would need about 17-121 months of record for t ≥ 2 (`results_scalping/C/cell_report.csv`).

---

## 1. What the friend's description means in market terms

"Buy at the bid, sell at the ask" is market making.
- **Revenue:** the market maker earns the spread.
- **Three costs:** being filled by better-informed traders just before the price moves (adverse selection), holding inventory while the price wanders, and fees.

Theory and the literature agree that, in a competitive market, the spread roughly equals those costs. Net liquidity-provision profit in US stocks is about 1-2 bp of dollar volume even for firms reacting in 100 milliseconds (Conrad and Wahal, 2020), and most of it goes to a handful of fast firms. Studies of retail day traders find that under 1% are reliably profitable (Taiwan) and 97% of persistent Brazilian day traders lost money. Most documented exceptions won on speed, which now belongs to high-frequency firms. The one the literature sees as most plausibly still open is selling to attention-driven buyers (Seasholes and Wu, Shanghai). It needs inventory or a short sale and was not tested as a strategy here, though Part D's give-back result fits it (`research_notes/Scalping and market making/literature_scalping.md`).

"Capturing small increases in price" in thin stocks reads differently: buying names that are moving on attention and selling a little higher. The literature ranks this, together with luck, as the most likely description of what retail scalpers actually do.

Low-volume stocks have wide spreads precisely because adverse selection and inventory risk are high there. A wide spread is the price of a risk, not an opportunity.

## 2. What was tested

The design was pre-registered (`analysis_2026/SCALPING_PREREG.md`, committed before any test-sample result; the pilot results it lists had already been seen) and revised after a three-angle adversarial review. The primary results were then independently re-derived by auditors and skeptics.

**Main deviations from the pre-registration** (none changes a verdict):
- made after results were seen: sale proceeds are floored at zero, since a long position cannot lose more than 100% (B1-L1 −6.6% → −6.3%), and the null-panel redraw pool drops returns that span missing days;
- the Part C panel is 118 of the 120 drawn names (two fall outside the stock universe);
- the spread model was fitted on the 1,097 of the 1,167 quoted names that have daily bars.

| Part | Market and data | Variants (primary tests) | What it answers |
|---|---|---|---|
| **A** | Binance spot crypto: every trade, with which side rested; 12 months (Oct 2025 – Sep 2026); 270 randomly drawn pairs in four daily-volume bands from $50k to $50M | Q1 join the best bid and ask, with an inventory cap (not enforced for orders already in flight on fast days; enforcing it, and Q5's one-position rule, moves edges by under 1 bp); Q2 step one tick inside when the spread is wide; **Q5 the friend's rule** (buy at the bid, offer at the ask, sell at market after 60 min) — 12 tests | Does bid-ask capture work when every trade, and which side rested, is recorded? |
| **B** | US stocks, daily bars: 2001-2020 (qlib set, about 6,900 stocks, survivor-biased) and 2023-2026 (Robinhood, 3,485 current low-volume names), in four bands of $50k-$5M daily dollar volume | B1 buy yesterday's worst losers; B2 the same on high-volume selling; B3 a resting bid one daily volatility below the close; **B4 the friend's rule once a day** (bid at the estimated bid, sell at the estimated ask within 5 days) — 16 tests | Does slow liquidity provision in thin stocks cover its costs? |
| **E** | Same as B | E1 buy the band's top-decile gainers on 3× normal volume, sell next day — 4 tests | Does chasing attention in thin stocks pay? |
| **C** | US stocks, 5-minute bars (Robinhood), 118 low-volume stocks, Mar – Oct 2026 | **C1 the friend's rule intraday**: bid half an estimated spread below the last trade, sell a spread higher, give up after 30 min — 4 tests | The closest free-data test of the literal rule |
| **D** | Same as B | Capacity, the cost of large positions, paper vs realized P&L when buying 5-100% of a day's volume | Does capital help? |

**Fills were deliberately strict.**
- **Crypto:** a resting order fills only when a trade prints *through* its price.
- **US bars:** only a whole-cent price beyond the limit counts as a fill. Sub-penny prints are off-exchange and could not have reached the order.
- **Costs:**
  - **US spreads:** estimated from daily bars and a model fitted to 1,097 of 1,167 actual closing quotes, then multiplied by 1.5 to allow for bid-ask bounce.
  - **Price impact:** charged on a $10,000 position with the standard square-root rule.
  - **Crypto fees:** zero maker / 2 bp taker (Binance.US's 2026 schedule) as the primary case. Robinhood's crypto tiers are worse. The books themselves are Binance.com's, which US residents cannot use; whether the result carries over to Binance.US, Coinbase, Kraken or Robinhood books is untested.

**Controls ran first.**
- **Crypto:** a synthetic market in which a market maker should earn the half-spread did so under a true queue model. Under the strict fill rule used for the verdicts, the same no-information market at thin-pair activity loses about 3-8 bp per dollar filled at 1- and 3-tick spreads (queue model: −1.8 to +1.6 bp), so part of the measured loss in the thinnest bands comes from the method itself (see the caveat in 3a).
- **Futures validation:** on real futures books with the true best bid and ask, the trades-only fill rule was within 0.1-0.4 bp of a full queue model (within 0.65 bp on a per-symbol-day measure). Those books had at least 370 taker orders an hour, so the check does not cover the thinnest crypto pairs (see 3a).
- **Daily stocks:** the daily engine reproduced the documented one-day reversal in S&P 500 stocks (t = 2.78).

## 3. Results

### 3a. Crypto bid-ask capture loses in every band (Part A)

**Net result per dollar filled**, Binance spot, zero maker fee and 2 bp taker, $1,000 orders:

| Band (daily volume) | Q1 join both sides | Q2 step inside | Q5 friend's rule | Q5 $ per pair per day |
|---|---|---|---|---|
| A $50-200k | −15.7 bp | −16.7 bp | −17.6 bp | −$18.6 |
| B $0.2-1M | −12.2 | −13.0 | −12.0 | −$22.8 |
| C $1-5M | −7.1 | −7.5 | −6.8 | −$25.7 |
| D $5-50M | −4.2 | −4.5 | −4.6 | −$40.5 |

**Statistics.**
- t-statistics run from −4.8 to −16.0.
- The 1 − 0.05/36 upper confidence bound is at most −3.18 bp in every cell, against the +1 bp threshold for "worth discussing".

**Where the money goes** (Q1, bp per dollar filled, bands A/B/C/D):
- spread captured at the fill: +5.9 / +3.9 / +2.3 / +1.3;
- price move against the maker over the next 5 minutes: −19.2 / −14.3 / −8.3 / −4.8;
- forced exits at market: −3.1 / −2.0 / −0.8 / −0.2.

The fills are adversely selected. Under the strict fill rule a resting quote fills only when an order trades through it, and within 60 seconds of such a fill the price has moved 5-16 bp against the maker. Part of that is built into the rule: under the optimistic touch rule the 60-second move is 2-7 bp for Q1, and the result is still negative.

**Nothing rescues it:**
- **Fill model.** Even the optimistic "touch" rule (filled whenever a trade prints at your price) has a negative point estimate in every strategy and band. For the friend's rule in band B its upper bound is +3.4 bp, so touch fills alone would not rule out a small edge there.
- **Variants.** One second of latency instead of a quarter second, 25% participation, quoting one tick behind the best: all negative.
- **Splits.** Every split is negative: tick-constrained vs wide-spread pairs, spread-to-volatility terciles, volatility, listing age, weekday vs weekend.
- **Size.** Larger orders are worse: at $25,000, Q1 loses 31 / 29 / 18 / 8.6 bp.
- **Rebates.** Breaking even would need a maker *rebate* of about 6-24 bp per dollar. That is several times the largest maker rebate in the fee schedules reviewed: at most 2 bp, and that unconfirmed (`crypto_data_feasibility.md` §6).
- **Speed.** On futures validation days, being first in the queue at every price level (the value of speed) still loses (−1.9 bp vs −2.4 bp).
- **Retail fees.** At Robinhood's or Coinbase's entry tiers (0.50% maker / 0.90-0.95% taker), Q1 loses roughly 70-85 bp per dollar filled.

**The main open caveat (from the audit).** In the thinnest pairs (bands A and B, medians of 89 and 163 taker orders an hour), the strict fill rule could be pessimistic. The futures validation that found it accurate used books with at least 370 taker orders an hour, so it does not cover these bands.
- A synthetic control suggests that, carried over in ticks, a correction could lift the friend's rule in band B to about +2 bp per dollar. It would also put that rule's upper bound above the +1 bp threshold in band A (about +6.8 bp) and band B (about +5.7 bp), so those two NO EDGE verdicts assume the strict fill rule is roughly faithful in thin books.
- Even then the dollars are trivial: Q5 fills about $19,000 a day per pair, so +2 bp is about $4 a day.
- With 30% informed traders in that synthetic market, no cell crosses +1 bp, and Q1 and Q2 stay below it either way.

### 3b. Daily liquidity provision and attention trades in thin US stocks lose after costs (Parts B and E)

**Net per trade, 2001-2020**, $10,000 positions, spread × 1.5 plus impact, return in excess of the stock's liquidity band (B3: raw return; B4: raw on the fill day, band excess after):

| Band (daily $ volume) | B1 buy losers | B2 losers on volume | B3 dip bid | B4 friend's rule (daily) | E1 buy gainers on volume |
|---|---|---|---|---|---|
| L1 $50-150k | −6.3% | −7.3% | −2.7% | −1.9% | −6.7% |
| L2 $150-500k | −3.1% | −3.7% | −1.3% | −1.3% | −3.4% |
| L3 $0.5-1.5M | −2.0% | −2.3% | −0.8% | −1.1% | −2.2% |
| L4 $1.5-5M | −1.4% | −1.5% | −0.6% | −1.1% | −1.5% |

**Every cell is NO EDGE.**
- **Statistics:** t from −13 to −59; the strict upper bound of the edge is −0.3% to −6.9% per day held.
- **Recent sample:** 2023-2026 is worse (B1: −10.0% / −5.3% / −3.3% / −2.2%).
- **Exploratory variants, all negative:**
  - 5- and 20-day holds;
  - high-VIX periods (worse still);
  - the friend's rule with sell targets of only +1% or +2%;
  - stocks priced $1-3;
  - thin ETFs bought on dislocations from a matched liquid ETF (−0.5% to −2.9%).

**Why it fails: there is almost nothing to capture beyond the bounce.**
- **Gross reversal is bounce-sized.** Before any cost, buying yesterday's losers earns +1.0% / +0.2% / +0.1% / +0.03% the next day in L1-L4. Excluding about 26 stocks with obvious data glitches, it is +0.44% in L1.
- **The synthetic benchmark matches.** A synthetic market with no information and each band's median spread gives +0.84% / +0.25% / +0.11% / +0.04% from bid-ask bounce alone.
- **The timing matches bounce.** The whole gross reversal happens overnight, between the close and the next open, which is where closing-price bounce shows up.
- **What outlasts the bounce day is tiny.** The registered skip-a-day check (enter a day later) is negative in every cell, because, as read here (implementation choice 7), its "gross" still charges price impact. With impact also removed and the glitch stocks excluded, only B1-L2 (+0.05%, t 2.9), B2-L2 (+0.14%, t 2.7) and B2-L1 (+0.10%, t 2.0) are positive, far below L1-L2 spreads of about 1-2%. The larger L1 values with the glitch stocks included (+0.4%, +1.6%) are artefacts.
- **Spreads would have to be tiny.**
  - With zero impact, B1, B2 and E1 would need true spreads below 2-36% of the estimate to break even, depending on the cell: at most 36% in L1, 10% in L2-L4, and about 8% anywhere once about 26 glitch stocks are excluded.
  - B3 and B4 lose before any cost.
- **The estimate is not the problem.** It runs at 1.2-2.2× the actual closing quotes, a deliberately cautious level, but it would have to be wrong by a factor of about 3 or more in L1 and 10 or more in L2-L4 to matter.

**Daily attention chasing loses too (E1).**
- Before costs, the next day earns only +0.1% to +0.6% (+0.2% in L1 excluding glitches).
- An exploratory intraday version (outside the 36 tests) was tried on 1,492 big gap-up, high-volume days in 2026: buy a breakout above the first half hour's range.
  - Net it lost 5.1% per trade. Before costs it was +1.8%, but all of that is one halted stock. Without it, −0.4%.
  - That leg's event filter also used the full day's volume and close, a registered look-ahead, so it could not be traded as specified. In this sample, though, the trades that had not yet met the volume condition at entry did no worse, so the look-ahead did not flatter the result. Bid-ask bounce alone makes this rule's gross −0.1% to −0.9% in a no-information market, so the −0.4% without the halted stock is not evidence of a negative edge before costs.

### 3c. The literal intraday rule can't be tested on 5-minute bars (Part C)

**The result.** On 118 low-volume stocks over 160 sessions, C1 lost $28-37 per stock per day and 0.5-3.1% per dollar bought.

**Why it is inconclusive, not "no edge".**
- **The control failed.** In a synthetic market with no information, where a market maker *should* earn the spread, the same rule also loses roughly as much. Bars without quotes cannot place a bid at the bid: the bid is set from the last trade, which may have been at the ask, and the sell target sits a full estimated spread above it, so most positions end in forced sales at market. Even with the true spread and almost no price movement, the rule earns about zero before costs.
- **The verdict rule.** The pre-registration therefore caps all four cells at INCONCLUSIVE. Under the alternative reading of that rule they would be "no edge" (upper bounds −0.35% to −2.5% per dollar).

**The honest summary:** free intraday bars cannot test bid-ask capture with this rule, and the test says nothing about whether a faster quote centred on the midpoint could profit. Part A's crypto test, with a full trade record, is the more faithful test of the mechanism, though in a different market and subject to the fill-rule caveat in 3a.

**Other Part C caveats:**
- the bar fill rule charges the bid price even when the market was already trading below it, which overstates costs by at most 0.2-0.9% per dollar;
- the spread estimate comes from the closing-quote model in about 86% of stock-sessions;
- the window (March to October 2026) is a single bull market;
- **IEX tick-data cross-check (Control iii, descriptive).** On 27 name-days in the busiest band (L4) where IEX's quote matched the national best bid and offer, the same rule run on real IEX ticks with a back-of-queue model lost $46.8 per name-day (SE $11.3; 15% of name-days positive), or 0.77% per dollar bought. The bar version lost 0.86% per dollar on the same days. Tick data fill the rule about 8 times as often, but the result per dollar is the same sign and size. The sample is small: 5 sampled days, and the NBBO match is a proxy on 4 of them.

### 3d. What "a large amount" does (Part D)

**Round-trip cost** for a position of 10% of a day's volume, using median stocks in each band (spread plus two square-root impacts):

| Band | Median daily $ volume | 10% position | Round-trip cost |
|---|---|---|---|
| L1 | $90k | $9k | 6.5-7.8% |
| L2 | $282k | $28k | 3.6-4.9% |
| L3 | $868k | $87k | 2.5-3.6% |
| L4 | $2.8M | $284k | 2.0-2.9% |

- **Capital can't be deployed.**
  - Spread across each day's signals, $1M aimed at the thinnest band's reversal trades kept only about $420k working at once. The 10%-of-volume caps bound.
  - Every daily strategy (B1-B4, E1) lost money at every capital level from $10k to $5M, in both samples.
- **Paper gains are not realized gains.** Simulated large buyers accumulated 5-100% of a day's volume and sold five days later. Their marks at the end of buying overstated what they later realized by a median 1-5 percentage points of the position in L1-L4. Realized results averaged about −6% to −9% in L1 and −1.7% to −3% in L4 (2023-2026, net of the band).
- **Recent spikes give back.** In 2023-2026, after a stock in bands L1-L3 jumped on three times normal volume, it gave back 3-5% over the next 20 days relative to its band (t −2.8 to −5.1; in L4 −1.2%, not significant). That is the pattern expected when temporary buying pressure, not news, moved the price, whether from one large buyer or many attention buyers. The 2001-2020 data show no such give-back.
- **Ownership thresholds bind early.**
  - A $1M position crosses the 5% ownership-filing threshold at a $20M market cap.
  - Above 10% of a company, the short-swing profit rule (Section 16(b)) hands back trading profits made within six months, which rules scalping out.
  - A $5M position reaches those thresholds at $100M and $50M (`practicalities_us.md` §7).

## 4. What the friend is probably doing

| Explanation | Evidence | Likelihood |
|---|---|---|
| **Luck and survivorship in a strong market** | Day-trader studies, in which profits tracked the market (US 1998-99, Jordan and Diltz); people still trading, and talking about it, are the survivors. A strategy's daily P&L swings are large enough that months of profits are statistically consistent with zero skill. | High |
| **Attention or momentum trading in low-float stocks** | Most common retail "scalping" in practice; the literature finds short-term momentum in high-turnover names. Tested here only at daily and opening-range horizons, where it lost. | High |
| **Paper gains from his own buying** | Large buying moves a thin price, and a mark at the last trade ignores the cost of selling. In Part D's simulation, marks overstated realizable value by a median 1-5 points, mostly the cost of selling. In 2023-2026 high-volume up days in bands L1-L3 gave back 3-5% within 20 days (not significant in L4). | Moderate-high |
| **Genuine small-scale market making** | Possible only with speed, direct exchange access, two-sided quotes and inventory discipline. Lost in every crypto band at retail speed, even with zero fees; the 5-minute-bar test in US stocks could not decide. | Low |
| **Rebate capture** | Requires direct exchange access and top volume tiers. Robinhood passes no rebates to customers. | Very low |

**What to ask for:**
- at least 12 months of **closed-trade** results from broker statements, including a down market;
- net of all costs;
- marked at what positions could be sold for, not the last trade;
- compared with the S&P 500 over the same months.

**One line not to cross.** Placing large orders to move a thin price and then selling into the buyers it attracts is the classic manipulation pattern (Exchange Act §9(a)(2)). So is placing and cancelling large bids. The SEC and DOJ have brought spoofing cases against individual day traders in thin stocks (`practicalities_us.md` §6).

## 5. Practical constraints for this user

- **Robinhood fills, not exchanges.** Robinhood routes every stock order to wholesalers (payment for order flow). A resting limit order has no exchange queue priority and earns no rebate.
- **Agentic orders are slow.** Each read call took about 8 seconds, and orders go through preview and approval, so only end-of-day decisions are realistic.
- **Shorting is unavailable.** The agentic account allows no shorting, so a two-sided market maker would need to hold inventory.
- **Taxes are short-term.**
  - Gains are taxed as ordinary income.
  - Frequent same-ticker trading triggers wash sales across all of the user's accounts, including the Schwab robo's tax-loss harvesting.
  - Electing mark-to-market under §475(f) could not take effect before tax year 2027.
- **Crypto on Robinhood.** Fees on the default route (about 0.95% a side) or at entry-tier exchange routing (0.50% maker / 0.95% taker) are 25-95 times the 1-2 bp a passive quote could at best hope to keep.

## 6. What could still be tested, and what it would take

No reachable free data can test queue-level stock scalping. Before anyone revisits this, the following would close the remaining gaps:
1. **Record forward quotes.**
   - Save Robinhood's scanner closing quote and size for every US stock every day. This is about 10-12 read-only calls a day, and builds a survivorship-free universe from now on.
   - Poll quotes intraday for a fixed panel.
2. **Record a crypto order book a US resident can use.** Record Coinbase or Kraken order books (level 3) on the user's own machine for at least four weeks. That is the only venue-faithful test of crypto market making for a US account.
3. **Buy queue-level US data** (TAQ, Polygon or Databento) if the question ever needs a definitive US answer at second-level speed.
4. **Check the friend's record** as above. That is cheaper and more informative than any further backtest.

None of these is likely to reverse the conclusion. The economics (adverse selection), the crypto result with real trades, and the cost arithmetic in thin stocks all point the same way.

## 7. Bottom line for capital deployment

- **Don't run a scalping or bid-ask-capture strategy** in low-volume stocks or illiquid crypto, manually or through the Robinhood agent.
- **Don't scale up a thin-stock strategy.** Capital adds impact and ownership-filing problems, not capacity.
- **Large capital belongs where size is not a handicap,** such as diversified index exposure. The repository's earlier trend and allocation studies (HANDOFF sections 5.9-5.18) found few edges over simply holding, and none of them depends on out-trading market makers in thin books.

---

**Sources and files.**
- **Pre-registration:** `analysis_2026/SCALPING_PREREG.md`.
- **Code:** `analysis_2026/scalp_crypto.py`, `scalp_us_daily.py`, `scalp_us_intraday.py`, `scalp_stats.py`, `scalp_report.py`, `fetch_scalping_data.py`, `rh_bars.py`.
- **Results:** `analysis_2026/results_scalping/` (`verdicts.txt` has all 36 cells).
- **Research notes:** `analysis_2026/research_notes/Scalping and market making/`, covering the literature, US practicalities and data feasibility.
- **Summary:** `HANDOFF.md` section 5.21; `analysis_2026/FINDINGS.md` entry of 2026-10-18.
- **Source quality:** literature and fee figures come mostly from search-result summaries, because publisher, SEC and exchange sites were blocked from the research environment. Treat individual fee rates and dates as leads to confirm.
