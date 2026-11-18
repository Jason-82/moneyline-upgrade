# Stink bids: what the evidence says

Research note for the stink-bid study, written 2026-11-18. It covers the published evidence and the repo's own
related findings. It contains no new market data and no outcome of any strategy.

**Ground rules followed.**
- No prices were fetched. No post-fill return, P&L or strategy outcome was computed on real data.
- The only computation is a Gaussian first-passage illustration (section 1.2), which is pure math.
- No Robinhood tool was used.

**Source tags.**
- [A]: abstract or primary page, read through search results.
- [S]: secondary summary, news or vendor page.
- [U]: unverified (from memory, conflicting sources, or a paywalled page seen only as an excerpt).
- Repo results are cited by file and section.

**Access limit.** WebFetch could not reach `arxiv.org` or `repec.econ.au.dk` from this session (the hosts would
have to be allowed in the session's network settings), so no paper was read in full. Every literature figure comes
from abstracts and search-result summaries. Confirm a figure before quoting it in the final report.

---

## 0. Bottom line

1. **A stink bid is a free put option written to the market.** It fills in two very different situations:
   - forced or panicked selling that overshoots, which is good for the bidder;
   - news that makes the coin worth less than the bid, which is bad for the bidder.

   Theory says that in a competitive order book the two roughly cancel. The idea pays only if forced-selling
   overshoots dominate the fills (section 1).
2. **Deep fills are rare and come in clusters.** Under ordinary (Gaussian) volatility, a coin with 5% daily
   volatility should essentially never fall 20% within a day. Yet market-wide liquidation days produce 15-60%
   intraday wicks across many coins at once (2021-05-19, 2024-08-05, 2025-10-10). Deep wick fills therefore come
   from a handful of crash days, not a steady stream. The effective sample is the number of crash events, not the
   number of fills (sections 1.2, 2.3).
3. **A bid that rests for weeks will mostly be filled by slow declines, not wicks.** Even with no jumps, a level
   20% below a 5%-volatility coin is touched within 30 days about 41% of the time. Slow declines are the adverse
   kind: they carry information and momentum (sections 1.2, 2.4).
4. **What happens after a fill depends on how fast and how broad the drop was.**
   - Fast, high-volume, market-wide, no-news drops tend to reverse within minutes to days.
   - Slow or news-driven drops tend to continue.
   - Crypto crashes mix both. On 2025-10-10 prices came back from the extreme wick lows within hours, and BTC
     then fell to about half its October peak by February 2026 (sections 2.3-2.4).
5. **Holding a filled stink bid for months amounts to buying the dip, and buying the dip has not beaten random
   entries.**
   - In the repo: mega-cap dips, moving-average touches, and crypto, where no bounce was found.
   - In the literature: AQR's "Hold the Dip" (2025).
   - For BTC after liquidation spikes, K33 found weak 30-day returns with a negative median (sections 4.3, 5).
6. **Chart levels are unlikely to improve returns, but they may change fill odds.**
   - Support and resistance levels mark where orders already sit.
   - Stop-loss orders cluster just beyond round numbers and obvious levels, so prices accelerate through those
     levels.
   - No published test supports Fibonacci levels, volume-profile nodes or liquidation heatmaps. The repo found that
     moving averages do no better than placebo lines (section 3).
7. **Knife-catching risk is large, and a "real revenue" filter does not remove it.**
   - 37% of Binance coin-years in 2019-2026 fell more than 60% (repo 5.11).
   - FTT's buybacks were funded by real exchange revenue, and it still fell 97.6%.
   - LUNA went from $80 to almost zero in three days (section 4.4).
   - The crypto reversal premium sits mainly in small, illiquid coins, so a "solid coins" filter moves the bids
     toward where reversal is weakest (section 4.1).
8. **Where an edge could exist.** The fastest, deepest, market-wide wick fills, sold into the rebound within
   hours to days, on a venue where such prices actually trade. That is the first hypothesis worth testing. Every
   other kind of fill is expected to be neutral or negative against fair benchmarks (sections 6-7).

---

## 1. Limit orders: fill odds, adverse selection and very deep bids

### 1.1 A resting bid is a free put option

- **Copeland & Galai (1983, JF 38(5)).** The cost of quoting is modeled as writing options to better-informed
  traders. Spreads rise with volatility and fall with activity and competition [A]
  ([HUJI record](https://cris.huji.ac.il/en/publications/information-effects-on-the-bidask-spread/)).
  - The limit-order corollary: a buy limit order gives the market, for free, a put on the asset struck at the limit
    price. Traders should bid less aggressively when volatility rises, to avoid being picked off [S]
    ([CFR Cologne WP 05-15](https://www.cfr-cologne.de/download/workingpaper/cfr-05-15.pdf)).
- **What this means for a stink bid.** The option is exercised against the bidder when someone wants to sell at the
  bid. That happens:
  - when value has fallen below the bid (information): the bidder is picked off;
  - when a seller must sell immediately whatever the price (liquidation, stop cascade, fat finger): the bidder is
    paid for immediacy.

  A manually placed good-till-cancelled bid cannot be updated on news, so the option stays open through hacks,
  exploits, delistings and regulatory headlines. These coin-specific events are the classic way a stale order gets
  picked off.

### 1.2 How fill odds fall with distance

**Empirical.**
- **Lo, MacKinlay & Zhang (2002, JFE 65).** A survival model of limit-order execution times.
  - Execution times are "very sensitive to the limit price" but not to size.
  - "Hypothetical limit-order executions, constructed either theoretically from first-passage times or empirically
    from transactions data, are very poor proxies for actual limit-order executions" [A]
    ([MIT abstract](https://web.mit.edu/Alo/www/Papers/limit10.html)).
  - Consequence for the study: a backtest that counts a bid as filled whenever the bar's low touches it overstates
    fills.
- **Zovko & Farmer (2002, Quant. Finance 2(5)).** 7 million London Stock Exchange orders.
  - The distance of limit prices from the best price is fat-tailed. The cumulative distribution decays roughly as
    a power law with exponent about 1.5, from 10 to 2,000 ticks.
  - Relative limit prices rise with volatility and are led by it [A]
    ([RePEc](https://ideas.repec.org/a/taf/quantf/v2y2002i5p387-392.html)).
  - So deep resting orders are common, and traders move them deeper when volatility rises. A stink bid competes
    with other deep bids.

**Illustration: Gaussian touch odds.** This is pure math, not market data. For a driftless random walk in log
price, the chance of touching a level d below within T days is 2Φ(−ln(1/(1−d)) / (σ√T)).

| depth below price | 5% daily vol: within 1 day | within 7 days | within 30 days | within 365 days |
|---|---|---|---|---|
| 10% | 3.5% (about once every 28 days) | 43% | 70% | 91% |
| 20% | 0.0008% (once every ~340 years) | 9% | 41.5% | 81.5% |
| 30% | about 1e-12 | 0.7% | 19% | 71% |
| 50% | about 1e-43 | 2e-7 | 1.1% | 47% |

- At 3% daily volatility (BTC-like), a 20% fall within one day has odds of about 1e-13 and a 30-day touch about 17%.
  At 7% daily volatility, a one-day 20% fall happens about once every 700 days and a 30-day touch about 56%.
- **Real crypto is nothing like this in the tail.** On 2025-10-10 the Binance spot intraday lows against the prior
  close were XRP −55% and DOGE −62% (repo, `research_notes/Bollinger breakout replication/rules_and_evidence.md`
  3.7 [A]). On 2021-05-19 BTC fell from about $43k to about $30k in about 14 hours (section 2.3). Under the
  Gaussian model these moves are effectively impossible.
  - Deep one-day fills are therefore jump events. Their frequency must be measured, not modeled.
- **Two corollaries.**
  1. Wick fills arrive on a few crash days, many coins at once. The independent sample is the number of events.
  2. Over a weeks-long resting horizon, ordinary diffusion alone reaches moderate depths often. Most fills of a
     −15% to −25% bid that stays open for a month are expected to come from slow declines, not wicks. The order's
     lifetime therefore decides which kind of fill the user gets. This is checkable now from fill frequencies alone.

### 1.3 The winner's curse of limit orders: evidence

- **Glosten (1994, JF 49(4)).** In a competitive open limit order book, deeper quotes face a winner's curse.
  - The bid at depth y is priced at the expected value conditional on a sell order at least that large (an
    "upper/lower-tail conditional expectation").
  - Deep limit orders fill only against large orders, which carry more information, so in equilibrium they earn
    about zero. Limit orders profit from small trades [A/S]
    ([RePEc](https://ideas.repec.org/a/bla/jfinan/v49y1994i4p1127-61.html);
    [Lehmann 2008 explains the mechanism](https://www.nber.org/papers/w13848.pdf)).
- **Sandås (2001, RFS 14(3)).** Tests Glosten's break-even conditions on Stockholm order books (ten stocks, from
  December 1991). The model's restrictions are rejected [A/S]. One summary says the books held less depth than the
  theory predicts [U: attribution uncertain] ([RePEc](https://ideas.repec.org/a/oup/rfinst/v14y2001i3p705-34.html)).
- **Handa & Schwartz (1996, JF 51(5)).**
  - Limit orders carry two risks: an unwanted fill on adverse news, and a missed fill on good news.
  - "A paucity of limit orders can result in accentuated short-term price fluctuations that compensate a limit
    order trader."
  - In their NYSE data, a network of buy and sell limit orders was profitable [A]
    ([RePEc](https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1835-61.html)). The sample is from the 1/8-dollar tick
    era [U].
- **Harris & Hasbrouck (1996, JFQA 31(2)).** Limit orders at or better than the quote beat market orders. But
  "unconditional strategies that use SuperDOT to offer liquidity in competition with the specialist do not appear
  to be profitable" [A]
  ([Cambridge](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/market-vs-limit-orders-the-superdot-evidence-on-order-submission-strategy/5DB9EB63B964E4F619ED90BF6B08B690)).
- **Linnainmaa (2010, JF 65(4)).** Data on all Finnish individual investors.
  - Poor post-trade returns, the disposition effect and contrarian trading arise "mechanically because limit orders
    are price-contingent and suffer from adverse selection" [A]
    ([RePEc](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1473-1506.html)).
  - A retail dip-buyer's limit orders get filled when the market moves through them.
- **Kelley & Tetlock (2013, JF 68(3)).** US retail orders, 2003-2007.
  - Only passive (limit) net buying follows negative returns.
  - Both passive and aggressive net buying predict positive monthly returns, with no reversal. The authors read the
    passive part as retail liquidity provision that profits when transitory drops reverse [A]
    ([author PDF](https://business.columbia.edu/sites/default/files-efs/pubfiles/4471/Kelley_Tetlock_JF_12_How_Wise_Are_Crowds_with_Appendix.pdf)).
  - This is the one clearly positive retail limit-order result. It concerns near-market orders in US stocks at a
    monthly horizon, not deep bids.
- **Albers, Cucuringu, Howison & Shestopaloff (2025).** Live maker orders on the Binance BTC perpetual (over
  400,000 orders). The authors find "a negative correlation between a maker order's fill probability and its
  subsequent return conditioned on filling" [A: preprint]
  ([RePEc preprint](https://ideas.repec.org/p/arx/papers/2502.18625.html);
  [published version, Quant. Finance 25(6)](https://ideas.repec.org/a/taf/quantf/v25y2025i6p919-947.html)).

### 1.4 What this predicts for very deep bids

- **Fill odds fall steeply with depth.** Beyond a few daily sigmas, fills come almost only from jumps and wicks,
  which cluster on market-wide crash days.
- **Fills come from two populations:**
  - (a) declines that carry information. These are adversely selected (Glosten, Linnainmaa, Albers et al.).
  - (b) forced-liquidity overshoots. These are compensated (Handa-Schwartz, Nagel in section 2.1).

  Deeper, faster and broader fills should contain more of (b). At extreme depth, information cannot justify the
  price (an "ATOM briefly printed a false zero" event), so those fills are almost pure overshoot.
- **Competition and supply.** In a competitive book, deep bids earn about zero (Glosten). An edge needs deep
  liquidity to be under-supplied at the moment of the crash, and the stress evidence says it is:
  - liquidity providers withdraw (Nagel 2012; Hameed, Kang & Viswanathan 2010);
  - high-frequency traders turn into takers when many stocks move at once (Brogaard et al. 2018);
  - buy-side resting orders nearly vanished at the 2010 trough (Kirilenko et al. 2017);
  - altcoin depth evaporated on 2025-10-10 (Coin Metrics).

  A bid that is already resting is one of the few left. That is the economic case for the idea. The same moments
  also bring macro news, counterparty failures and venue malfunctions.
- **The bidder buys at the bid price, not at the wick's low.** A sweep through the bid fills it at the limit. The
  part of the wick below the limit benefits deeper bids.
- **Venue matters (section 2.3).**
  - Some deep prints exist on one venue only.
  - Some liquidation flow never reaches the public book. On Hyperliquid on 2025-10-10, $576M of $641M of forced
    sales went to the backstop vault [S].
  - US equity venues cancel trades far from the market. Crypto venues have mostly honored them.

---

## 2. Flash crashes and liquidity shocks: do prices come back?

### 2.1 Theory and cross-asset evidence: liquidity-driven moves reverse, information-driven moves drift

- **Campbell, Grossman & Wang (1993, QJE 108(4)).** Daily return autocorrelation falls with volume. A price decline
  on a high-volume day is more likely to be followed by higher expected returns, because risk-averse market makers
  are being paid to absorb non-informational selling [A]
  ([Harvard](https://campbell.scholars.harvard.edu/publications/trading-volume-and-serial-correlation-stock-returns)).
- **Llorente, Michaely, Saar & Wang (2002, RFS 15(4)).** Returns generated by risk-sharing (hedging) trades tend to
  reverse; returns generated by speculative (informed) trades tend to continue [A]
  ([NBER w8312](https://www.nber.org/papers/w8312)).
- **Nagel (2012, RFS 25(7), "Evaporating Liquidity").**
  - Short-term reversal returns proxy the return to liquidity provision.
  - They are highly predictable with the VIX. Expected returns and Sharpe ratios rise sharply in turmoil, through
    withdrawal of liquidity supply by constrained intermediaries [A]
    ([RePEc](https://ideas.repec.org/a/oup/rfinst/v25y2012i7p2005-2039.html);
    [NBER](https://nber.org/papers/w17653)).
- **Hameed, Kang & Viswanathan (2010, JF 65(1)).** Negative market returns reduce liquidity, most when funding is
  tight and for high-volatility firms, through a lower supply of liquidity [A]
  ([RePEc](https://ideas.repec.org/a/bla/jfinan/v65y2010i1p257-293.html)). Larger reversal returns after market
  declines [U: not confirmed in the abstract].
- **Savor (2012, JFE 106(3)).** Large price moves with analyst reports (information) are followed by drift; those
  without are followed by reversals [A]
  ([RePEc](https://ideas.repec.org/a/eee/jfinec/v106y2012i3p635-659.html)).
- **Chan (2003, JFE 70(2)).** Strong drift after bad news, and reversal after extreme moves with no public news,
  mainly in small and illiquid stocks [A]
  ([RePEc](https://econpapers.repec.org/RePEc:eee:jfinec:v:70:y:2003:i:2:p:223-260)).
- **Cox & Peterson (1994, JF 49(1)).** After large one-day declines, the short reversal is explained by bid-ask
  bounce and liquidity. The stocks then perform poorly over a longer horizon, with no support for overreaction [A]
  ([RePEc](https://econpapers.repec.org/RePEc:bla:jfinan:v:49:y:1994:i:1:p:255-67)).
- **Christensen, Oomen & Renò (2022, J. Econometrics 227(2), "The drift burst hypothesis").**
  - Short-lived explosive trends (flash crashes) occur about once a week across asset classes.
  - "The majority of them are accompanied by subsequent price reversion."
  - Reversal is stronger for negative bursts with high volume, "consistent with endogenous demand for immediacy
    during market crashes" [A]
    ([RePEc](https://econpapers.repec.org/RePEc:eee:econom:v:227:y:2022:i:2:p:461-497)).
- **Brogaard et al. (2018, JFE 128(2)).** High-frequency traders supply liquidity in single-stock extreme moves.
  When many stocks move together, their demand for liquidity dominates their supply [A]
  ([RePEc](https://econpapers.repec.org/RePEc:eee:jfinec:v:128:y:2018:i:2:p:253-265)). Market-wide wicks are
  therefore deeper relative to fundamentals.
- **Kirilenko, Kyle, Samadi & Tuzun (2017, JF 72(3)).** Audit-trail data on the E-mini during the 2010 flash crash.
  - High-frequency traders did not trigger the crash but amplified it.
  - Opportunistic traders absorbed most of the imbalance at a steep price concession, and fundamental buyers came in
    later and pushed prices up.
  - By 2:45:28 p.m. fewer than 1,050 buy-side contracts were resting [A/S]
    ([SSRN](https://papers.ssrn.com/ab_id=1686004);
    [CFTC draft](https://www.cftc.gov/idc/groups/public/@economicanalysis/documents/file/oce_flashcrash0314.pdf)).
- **Johnson et al. (2013, Sci. Reports).** 18,520 ultrafast crashes and spikes lasting under 1.5 seconds in
  2006-2011 [S] ([Springer/Nature](https://link.springer.com/article/10.1038/srep02627)).

### 2.2 Classic flash crashes: how fast and how fully prices recovered

| event | move | recovery | lesson for stink bids |
|---|---|---|---|
| US equities, 2010-05-06 | Dow about −9% within minutes; some stocks traded at a penny against stub quotes | most of the Dow's loss came back within about 20 minutes, and the index still closed down [S] | exchanges **broke trades more than 60% away** from the 2:40 p.m. price (over 20,000 trades) [A/S]: the deepest stink bids did not stick ([SEC-CFTC report](https://SEC.GOV/files/marketevents-report.pdf); [joint meeting minutes](https://cybercemetery.unt.edu/archive/oilspill/20121017053611/http://www.sec.gov/spotlight/sec-cftcjointcommittee/052410sec-cftcjointmeeting-minutes.pdf); [CFI](https://corporatefinanceinstitute.com/resources/equities/2010-flash-crash)) |
| US Treasuries, 2014-10-15 | 10-year yield in a 37 bp range; a 16 bp move in 9:33-9:45 with no news | closed about 6 bp from its open [A] | fast moves with no news revert ([Liberty Street](https://libertystreeteconomics.newyorkfed.org/2019/10/from-the-vault-a-look-back-at-the-october-15-2014-flash-rally); [FEDS note](https://www.federalreserve.gov/econres/notes/feds-notes/retrospective-the-agency-mbs-market-on-october-15-2014-20200924.htm)) |
| Swiss franc, 2015-01-15 | EUR/CHF from 1.20 to about 0.85 in minutes after the floor was removed | bounced as high as about 1.06 the same day and steadied near parity; the floor was never restored [S] | news plus overshoot: **only the overshoot reverted**. A bid below the new equilibrium won; one above it lost ([Investing.com](https://m.investing.com/analysis/snb-causes-chf-flash-crash-game-changer-238593)) |
| US ETFs, 2015-08-24 | dozens of ETFs far below their indices; 1,278 LULD halts; triggered stop-loss sales [A/S] | within the day [U] | a stink bid's counterparty is often a stop order that became a market order ([SEC staff note](https://SEC.gov/marketstructure/research/equity_market_volatility.pdf)) |
| Sterling, 2016-10-07 | about −9% in early Asian trading | "quickly retracing much of the move" [A] | time of day, options hedging, stop-loss orders and withdrawn liquidity ([BIS Markets Committee](https://www.bis.org/publ/mktc09.htm)) |

### 2.3 Crypto flash crashes and liquidation cascades

| event | depth | after | notes |
|---|---|---|---|
| GDAX (Coinbase) ETH, 2017-06-21 | $317.81 to $0.10 after a multimillion-dollar market sell; about 800 stop and margin orders triggered [U] | seconds | **trades honored**; Coinbase compensated stop and margin victims [S] ([Finance Magnates](https://www.financemagnates.com/cryptocurrency/trading/ethereum-flash-crash-causes-eth-temporarily-trade-low-0-10/); [TechCrunch](https://techcrunch.com/2017/06/24/coinbase-is-reimbursing-losses-caused-by-the-ethereum-flash-crash)) |
| Black Thursday, 2020-03-12/13 | BTC about −50% intraday [U]; MakerDAO: 1,462 of 3,994 collateral auctions (36.6%) won with **zero-DAI bids**, about $8.3M of ETH [S] | BTC partly recovered within days [U] | network congestion let zero bids win: a DeFi stink bid ([Whiterabbit](https://medium.com/@whiterabbit_hq/black-thursday-for-makerdao-8-32-million-was-liquidated-for-0-dai-36b83cac56b6); [Glassnode](https://research.glassnode.com/what-really-happened-to-makerdao/)) |
| Market-wide, 2021-05-19 | BTC from about $43k to about $30k in about 14 hours; more than $8B liquidated [S] | BTC back near $40k the same day; BTC and ETH bounced more than 20% [S] | a market-wide liquidation cascade ([CoinDesk](https://hotfix.coindesk.com/markets/2021/05/19/bitcoin-drops-below-31k-before-rebounding-8b-in-liquidations-triggered); [Deribit](https://insights.deribit.com/exchange-updates/the-flash-crash-of-may-19-2021/)) |
| Binance.US BTC, 2021-10-21 | −87% to $8,200 on a client's algorithm bug [S] | almost instantly back to the prior level | **one venue only**: not on Coinbase; Kraken printed about $54k [S] ([The Block](https://www.theblock.co/post/121657/binance-us-blames-bitcoin-flash-crash-to-8200-on-a-bug-in-a-clients-trading-algorithm); [Finance Magnates](https://www.financemagnates.com/cryptocurrency/news/binance-blames-trading-algorithm-bug-for-bitcoin-flash-crash/)) |
| LUNA, 2022-05 | from $80 to almost zero in three days as supply went from 1B to 6T [A] | never recovered | a collapse that began as a "dip" ([NBER w31160](https://www.nber.org/papers/w31160)) |
| Celsius and 3AC, 2022-06 | a 12-week slide; BTC below $18k and ETH below $1k on the weekend of June 18-19 [S] | lower again in November (FTX) [U] | **a slow decline**, not a wick ([CVJ](https://cvj.ch/en/markets/market-review-calendar-week-25-2022/); [Fortune](https://www.fortune.com/2022/06/15/bitcoin-approaches-20000-crypto-crash-winter-celsius-three-arrows/)) |
| Yen carry unwind, 2024-08-05 | BTC −18% to about $49k intraday, ETH −23% to about $2,200; about $1B liquidated [S] | BTC back to about $52.9k the same day [S] | macro shock plus leverage ([Fortune](https://fortune.com/2024/08/05/bitcoin-price-plunges-ether-worst-drop); [CoinDesk](https://coindesk.com/markets/2024/08/05/crypto-futures-witness-840m-in-liquidations-as-bitcoin-nosedives-ether-records-biggest-fall-since-2021)) |
| Tariff shock, 2025-10-10 | about $19B liquidated [S]; Binance spot lows against the prior close: BTC −16%, ETH −21%, SOL −24%, BNB −32%, XRP −55%, DOGE −62% [A, repo]; SUI wicked to about $0.50 [U]; ATOM "briefly printed a false zero"; ENJ printed 0.00001 on Binance; AVAX low $8.53 [S] ([BeInCrypto](https://beincrypto.com/3-coins-worst-hit-by-black-friday-crypto-crash)); USDe $0.65 on Binance's internal book only [S] | BTC from about $101.5k back to about $112.5k within hours [S]; "some altcoins remained 20 to 30% below their pre-crash levels even after bouncing" [U: source unclear] | see the bullets below |
| After 10/10, 2025-10 to 2026-02 | BTC from a peak of about $126k (early October) to about $60k in early February 2026; Fear & Greed index at a record low of 5 [S] | the wick sat inside a larger bear market | ([Amberdata](https://blog.amberdata.io/bitcoin-below-70k-the-crash-the-data-and-what-comes-next); [CVJ](https://cryptovalleyjournal.com/news/bitcoin-drops-to-60000-worst-crash-since-ftx-collapse/)) |

**More on 2025-10-10.**
- **Depth.** Bid-side depth nearly vanished on major venues (Kaiko, cited by Binance). Altcoin books "almost
  completely evaporated" [S] ([Coin Metrics](https://coinmetrics.substack.com/p/state-of-the-network-issue-333);
  [Kaiko](https://research.kaiko.com/insights/when-october-surprise-meets-crypto-liquidity-drought)).
- **Depth afterwards.** Weeks later, ±2% depth for BTC, ETH and SOL was still 30-40% below early-October levels,
  and outside the majors the drop was "sharper and more persistent" [S]
  ([Coin Metrics](https://coinmetrics.substack.com/p/state-of-the-network-issue-339)). A year on, BTC and ETH depth
  had recovered while altcoin depth at 5% was about one-third lower than in early 2025 [S]
  ([CryptoBriefing](https://cryptobriefing.com/bitcoin-ether-liquidity-rebounds-altcoins-lag/)).
- **Venue specifics.**
  - The sharpest dislocations (USDe, wBETH, BNSOL) were on Binance, which priced that collateral from its own book.
    Binance paid about $283M to users of the three assets that depegged on the exchange [S]
    ([Cointelegraph](https://cointelegraph.com/research/exclusively-obtained-orderbook-data-reveals-details-about-usde-crash);
    [Galaxy](https://www.galaxy.com/insights/research/cryptos-flash-crash-liquidation-binance-adl-auto-deleveraging)).
  - On Hyperliquid, about $641M was force-sold at 21:19 UTC. About $576M went to the backstop vault and only about
    $64M reached the order book [S]
    ([CryptoSlate](https://cryptoslate.com/shifting-576-million-of-forced-sales-off-public-order-books-saved-hyperliquid-from-a-systemic-crash-during-peak-panic/)).
  - Lim (2026) measured Hyperliquid's median quoted spread at 9.4 bp at 21:00 UTC (95th percentile 87.5 bp), with
    recovery "well underway" by the end of the day [A]
    ([JFDA](https://journals.lincoln.ac.nz/index.php/JFDA/article/view/1395)).
  - Afterwards market makers were left holding coins, and liquidity was the thinnest since 2022 (BitMEX) [S]
    ([CoinMarketCap](https://coinmarketcap.com/academy/article/october-crypto-crash-left-market-makers-holding-coins-bitmex-reports)).
- **Sources disagree on the BTC low** (about $101.5k to $104.8k), because the low depends on the venue [S]
  ([CryptoSlate](https://cryptoslate.com/bitcoins-whipsaw-to-101k-wipes-out-7b-in-leveraged-positions)).

**Perpetuals against spot.** Gornall, Rinaldi & Xiao (2025, preliminary) find that in large market events quarterly
futures fall 8-10% more than spot and perpetuals about 3% more. Perpetual drawdowns relative to spot "quickly mean
revert" [A] ([AEA 2026 program](https://ftp.aeaweb.org/conference/2026/program/paper/ByyFEfr4)). Perpetual wicks are
therefore deeper than spot wicks, and both are deeper than any consolidated US price.

### 2.4 Fast wicks against slow declines

**Evidence for reversal after fast, liquidity-driven drops.**
- Drift bursts mostly revert, more so for negative, high-volume ones (Christensen et al.).
- High-volume declines reverse (Campbell, Grossman & Wang).
- Hedging-driven moves reverse (Llorente et al.).
- No-news moves reverse (Savor; Chan).
- Liquidity-provision returns spike in turmoil (Nagel).
- Perpetual-spot gaps close quickly (Gornall et al.).
- Every flash crash in sections 2.2-2.3 retraced much of its extreme within minutes to hours.

**Evidence for continuation after slow or information-driven drops.**
- Poor longer-term performance after large one-day declines (Cox & Peterson).
- Continuation after news (Savor; Chan).
- Momentum is stronger when information arrives gradually, in many small moves, than in a few large jumps
  ("frog in the pan", Da, Gurun & Warachka 2014, RFS) [U: not retrieved in this session].
- Time-series and cross-sectional momentum in crypto at daily-to-weekly horizons (section 4.1).
- In BTC, jumps "induce a persistent change in the price" (Scaillet et al. 2020, section 4.2).

**Synthesis.**
- A crash has two parts: an **overshoot** (forced selling, which reverts in minutes to hours) and a **level shift**
  (new information, which persists or continues).
- A filled bid makes money only if it sits in the overshoot zone, below where the price settles. A bid above that
  zone carries the level-shift loss.
- The overshoot share should rise with speed, depth in volatility units, volume, liquidation intensity and breadth
  across coins. It should fall with coin-specific news.
- Crypto crashes are often both kinds at once. 2025-10-10 combined a tariff headline (information) with record
  liquidations (overshoot). EUR/CHF in 2015 is the cross-asset template: a permanent shift plus a same-day partial
  snap-back.

---

## 3. Stop-loss clustering and price levels

### 3.1 Where orders cluster (Osler)

- **Osler (2000, FRBNY Economic Policy Review 6(2)).** Support and resistance levels published by six FX firms
  were compared with 10,000 sets of arbitrary levels, using 1-minute rates.
  - The published levels predicted intraday trend interruptions better than arbitrary levels, but the predictive
    power varied across firms and currencies [A].
  - Bounce rates were about 61% against 56% for arbitrary levels [S/U: the 56.2% comes from a Scribd copy]
    ([FRBNY](https://www.newyorkfed.org/research/epr/00v06n2/0007osle)).
  - The placebo-level design is the template the repo already used in 5.19.
- **Osler (2003, JF 58(5)).** About 9,700 actual stop-loss and take-profit orders at a large dealing bank,
  1999-2000.
  - Take-profit orders cluster at round numbers, and stop-loss orders cluster just past them.
  - This explains why trends tend to reverse at round numbers and to speed up once they cross them [A]
    ([RePEc](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html);
    [FRBNY SR 125](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.html)).
- **Osler (2005, JIMF 24(2)).** Exchange-rate moves are unusually fast when rates reach levels where stop-loss
  orders cluster.
  - The response to stops is larger and lasts longer than the response to take-profit orders.
  - The effects are significant for hours but not for days. Stops are not claimed to be the main cause of large
    moves [A] ([FRBNY SR 150](https://www.newyorkfed.org/research/staff_reports/sr150.html)).
- **Reading for stink bids.**
  - A bid at an obvious round number or swing low joins a crowd and is filled mainly when the crowd is overrun.
  - A bid just beyond the stop cluster is more likely to be filled by a cascade.
  - The cascade's effect fades within hours, which bears on fill odds and on the exit horizon. It says nothing
    yet about returns over months.

### 3.2 Support and resistance mark existing depth

- **Kavajecz & Odders-White (2004, RFS 17(4)).** On NYSE limit order books, support and resistance levels coincide
  with peaks in depth. Moving-average signals reveal where depth sits.
  - "Technical rules locat[e] depth already in place on the limit order book" [A]
    ([RePEc](https://ideas.repec.org/a/oup/rfinst/v17y2004i4p1043-1071.html)).
  - So a chart level tells where other bids already rest. It does not say what follows a fill.
- **Chung & Bellotti (2021, preprint).** In intraday series, levels that have held more often are more likely to
  hold again, and that probability decays over time [A]
  ([RePEc listing](https://econpapers.repec.org/paper/arxpapers/2101.07410.htm)). The evidence is weak (a
  heuristic algorithm, no placebo design reported in the abstract).

### 3.3 Moving averages, Fibonacci, volume profile and round numbers

- **Moving averages (repo 5.19).** Touches of 34 averages on S&P members and 40 coins did no better than placebo
  lines 1-2 ATR away, and crypto showed no bounce (section 5).
- **Fibonacci.** Tsinaslanidis, Guijarro & Voukelatos (2022, Expert Systems with Applications) found no
  statistical difference between price behavior at Fibonacci zones and at non-Fibonacci zones [S]
  ([summary](https://www.datalearner.com/academic/journal-papers/0957-4174/volumes-and-issues/391/paper-detail/17703)).
  Informal tests attribute retracement "hits" to chance, given several levels per region [S].
- **Volume profile (high- and low-volume nodes).** No academic or peer-reviewed test was found. The claims come
  from vendors and education sites, with unsourced statistics [S]
  ([example: LuxAlgo](https://www.luxalgo.com/library/concept/volume-profile.md)).
- **Round numbers in crypto.** Urquhart (2017, Economics Letters 159): more than 10% of BTC prices end in .00, with
  clustering tied to price and volume, and **no significant pattern of returns after round numbers** [A]
  ([RePEc](https://econpapers.repec.org/RePEc:eee:ecolet:v:159:y:2017:i:c:p:145-148)). Mbanga (2019) adds a
  day-of-week pattern in that clustering [A] ([BearWorks](https://bearworks.missouristate.edu/articles-cob/431)).
  Round numbers locate orders (Osler) but do not predict returns.

### 3.4 Liquidation heatmaps in crypto practice

- **What they are.** Heatmaps (CoinGlass, Hyblock and others) **estimate** where leveraged positions would be
  liquidated, from open interest and assumed leverage. "Exchanges do not publish real position ladders" [S]
  ([Cryptometer](https://www.cryptometer.io/liquidation-heatmap);
  [LuxAlgo](https://www.luxalgo.com/library/concept/liquidation-clusters.md)).
- **Evidence.** No peer-reviewed or independent test was found that clusters act as price "magnets". The claims are
  vendor assertions, such as "nine times out of ten", with no sample [S].
- **Hyperliquid.** Positions and liquidation prices are public on chain, so its maps are observed rather than
  estimated [U]. But most of its forced selling went to the backstop vault, not the book, on 2025-10-10 (section 2.3).
- **Forecasting cascades.** A 2026 preprint studied seven Binance BTC cascades. No price, leverage or order-flow
  metric warned consistently before all seven [S]
  ([CryptoSlate](https://cryptoslate.com/new-bitcoin-study-shows-the-strongest-recurring-liquidation-warning-signs-cannot-warn-of-an-individual-crash/)).

### 3.5 What this implies for "solid choices for the levels"

- **For the return after a fill:** the evidence predicts that no chart-derived level beats a volatility-scaled
  placebo level at the same depth. This is the 5.19 result, the Fibonacci result, and Urquhart's null after round
  numbers.
- **For fill odds:** levels can matter. Bids just beyond obvious stop clusters (round numbers, swing lows) and below
  estimated liquidation bands are more likely to be swept in a cascade (Osler 2003, 2005).
- **The design should therefore:**
  - express depth in volatility units;
  - test each level method against placebo levels at the same depth (Osler 2000; repo 5.19);
  - report fill odds and post-fill outcomes separately.

---

## 4. Crypto-specific evidence

### 4.1 Short horizons: intraday momentum, daily reversal in small coins, weekly momentum

- **Caporale & Plastun (2020, Financial Markets and Portfolio Management).** BTC, ETH and LTC, 2015-2019.
  - On days with abnormal returns, prices keep moving in the direction of the abnormal return until the end of the
    day (intraday momentum), with some carry into the next day.
  - Two cases were contrarian: BTC positive days and ETH negative days [A]
    ([Brunel](https://bura.brunel.ac.uk/handle/2438/20686)).
  - For a stink bid, a fill early in a crash day tends to be followed by further falls into the close, on average.
- **Caporale & Plastun (2019, J. Economic Studies).** Overreactions exist in crypto, but "counter-movement"
  (contrarian) trading strategies were not profitable [A]
  ([Emerald](https://emerald.com/insight/content/doi/10.1108/JES-09-2018-0310)).
- **Borgards & Czudaj (2020, JIFMIM 65; 2021, QREF 80).** Price overreactions are frequent in crypto. The path
  before an overreaction best predicts it, and the overreaction returns were positive for crypto and negative for US
  stocks because reversal sizes differ [A: 2021 abstract; 2020 abstract not retrieved]
  ([2021, RePEc](https://ideas.repec.org/a/eee/quaeco/v80y2021icp31-48.html);
  [2020, RePEc](https://ideas.repec.org/a/eee/intfin/v65y2020ics1042443120300780.html)).
- **Zaremba et al. (2021, IRFA 78).** Coins with a low previous-day return beat those with a high one: a daily
  reversal, driven by small, illiquid, low-volume coins. **The largest and most tradable coins show daily momentum,
  not reversal** [A] ([RePEc](https://ideas.repec.org/a/eee/finana/v78y2021ics1057521921002349.html)).
- **Bianchi, Babiak & Dickerson (2022, J. Banking & Finance 142).** Returns to liquidity provision, proxied by
  reversal, concentrate in pairs with low trading activity and are amplified in "smaller, more volatile, and less
  liquid" pairs [A] ([Warwick](https://wrap.warwick.ac.uk/165914/);
  [Riksbank WP 413](https://swopec.hhs.se/rbnkwp/abs/rbnkwp0413.htm)).
- **Liu & Tsyvinski (2021, RFS) [U: venue].** Significant time-series momentum at daily and weekly frequencies in
  BTC, ETH and XRP [A] ([SSRN](https://papers.ssrn.com/abstract=3226806)).
- **Liu, Tsyvinski & Wu (2022, JF) [U: venue].** Cross-sectional momentum of about 3% a week at 1-4 week horizons
  [A] ([NBER w25882](https://www.nber.org/papers/w25882.pdf)).
- **Liebi & Stöckl.** With survivorship controlled, there is no positive relation between returns and one-week
  momentum (section 4.4).
- **Reading.** Reversal in crypto is real but lives mostly in small, illiquid coins, where adverse selection and
  costs are also highest. The large "solid" coins lean toward momentum at daily-to-weekly horizons. A dip in a
  large coin is not, on average, a bargain at those horizons.

### 4.2 Jumps

- **Scaillet, Treccani & Trevisan (2020, J. Financial Econometrics 18(2)).** Mt. Gox tick data, 2011-2013.
  - About one jump a week, clustered in time.
  - Jumps are predicted by order-flow imbalance, aggressive traders and a widening spread.
  - Jumps "induce a persistent change in the price" [A]
    ([UNIGE](https://archive-ouverte.unige.ch/unige:93900)).
- **Saef et al. (2024, Digital Finance 6).** Six coins on seven exchanges, tick data.
  - Jumps occur on up to 58% of trading days, and about 61% of them are negative.
  - Intraday jumps coincide with same-direction end-of-day returns [S]
    ([Springer](https://link.springer.com/article/10.1007/s42521-024-00116-1)).
- **Reading.** An ordinary jump is not reliably reversed. Reversal is the signature of flash-crash and
  drift-burst events (section 2.1), which have to be told apart from ordinary jumps, for example by speed,
  breadth across coins, volume and liquidations.

### 4.3 After liquidation spikes and the named crashes

These are published accounts, selected with hindsight. Use them for context, never to choose depths, exits or
coins.

- **K33 Research, September 2025, via The Block.** BTC averaged +0.78% over the 30 days after the top 5% of annual
  liquidation events, against a typical +5.9% for any 30 days.
  - The median turns negative after peak spikes.
  - About a quarter of spikes marked local bottoms (+7.4% over the month); the worst quarter fell about 6% [S]
    ([The Block](https://www.theblock.co/post/372115/whats-next-after-cryptos-fourth-largest-long-liquidation-event-of-2025)).
  - The liquidation data are incomplete: Binance and OKX under-report.
- **Delphi Digital, about August 2025.** For BTC liquidation cascades that left very large wicks over roughly two
  years, "in each of these scenarios, BTC did eventually return and revisit the lows" [S: paywalled excerpt]
  ([Delphi](https://members.delphidigital.io/feed/price-action-apathy-continues-as-expected)). A wick low was not a
  durable bottom.
- **AQR, "Hold the Dip" (December 2025).** On the S&P 500, buy-the-dip rules trailed buy-and-hold in more than 60%
  of variants (average Sharpe −0.04), because they bet against momentum. Trend-following timing did better [S]
  ([AQR](https://www.aqr.com/Insights/Research/Alternative-Thinking/Hold-the-Dip)).
- **The four episodes the brief names** (facts from section 2.3).

  | episode | kind | what came next (widely reported) |
  |---|---|---|
  | 2021-05-19 | fast, market-wide | same-day rebound of more than 20%; BTC made new highs later in 2021 [U] |
  | 2022-06 | slow, counterparty failures | lower lows came in November 2022 (FTX) [U] |
  | 2024-08-05 | fast, macro | same-day partial rebound; BTC made new highs late in 2024 [U] |
  | 2025-10-10 | fast, market-wide, venue-specific | hours-long rebound; then BTC fell to about half its October peak by February 2026 [S] |

  Outcomes beyond a few days were set by the market regime that followed, not by the wick. Any test must therefore
  benchmark a fill against buying at market at the same time and against random entries, not against zero.

### 4.4 The knife-catching base rate

- **Repo (HANDOFF 5.11).** 581 Binance USDT coins, 2019-2026, delisted coins included: **37% of coin-years fell
  more than 60%**. For S&P stocks the figure was 1.8%.
- **Messari data (Matt Casto), about 2021.** 83% of crypto assets that set their all-time high in January 2018 were
  still at least 90% below it about three years later. The average was −90.7% across 410 assets [S]
  ([Cointelegraph](https://cointelegraph.com/news/83-of-cryptocurrencies-that-peaked-in-2018-are-still-down-by-90)).
  - Many were top-10 "solid" projects of their cycle; EOS, NEO and IOTA never regained their 2017-18 highs [U].
- **CoinGecko.** 53.2% of tokens tracked on GeckoTerminal since 2021 had stopped trading by the end of 2025 [S]
  ([CoinGecko](https://www.coingecko.com/research/publications/how-many-cryptocurrencies-failed)). Most were
  memecoins; this is not a base rate for large coins.
- **Survivorship (Liebi & Stöckl, working paper, 3,904 coins, 2014-2021).**
  - Survivorship bias is 0.93% a year for value-weighted portfolios and **62.19% a year for equal-weighted** ones.
  - The size premium is overstated by 50% in a survivor sample.
  - There is no positive relation between returns and one-week momentum [A]
    ([summary page](https://diffform.netlify.app/publication/2022_liebi_survivorship)).
  - Any test on coins chosen today (HYPE and NEAR are both hindsight picks) is biased upward. Dead coins must be in
    the sample.
- **Collapses that started as dips.**
  - LUNA: from $80 to almost zero in three days (Liu, Makarov & Schoar, NBER w31160 [A]). Wealthier, more
    sophisticated holders ran first and lost less.
  - FTT: −97.6% from its $84.18 high, in November 2022 [S]
    ([Fortune](https://fortune.com/crypto/2022/11/18/how-ftx-own-token-ftt-was-the-final-nail-in-its-coffin)).
  - The first leg of each looked like a wick to a dip-buyer.

### 4.5 Does "real revenue" protect?

- **FTT was a revenue token.** FTX put about a third of its trading-fee revenue into buying and burning FTT [S]
  ([CoinGecko](https://coingecko.com/research/publications/ftt-impacted-ftx-collapse)). Revenue did not protect
  against fraud and counterparty collapse.
- **LUNA's demand rested on Anchor's yield.** "Concerns about the sustainability of the system" triggered the run
  [A] (NBER w31160).
- **HYPE (the user's example).**
  - About 97-99% of Hyperliquid's fees fund HYPE buybacks through the Assistance Fund [S]
    ([CoinShares via ETF Trends](https://www.etftrends.com/coinshares-content-hub/inside-hyperliquid-fee-engine-works/)).
  - That makes it a real-revenue token, but one tied to a single venue. Its fundamentals and its crash behavior
    depend on that venue's volume and solvency.
  - Venue incidents:
    - JELLY, March 2025: validators delisted the contract and settled it at a chosen price, after the HLP vault
      showed an unrealized loss of up to about $13.5M [S]
      ([CoinMarketCap](https://coinmarketcap.com/academy/article/hyperliquid-delists-jellyjelly-perpetual-futures-after-dollar12-million-market-manipulation)).
    - POPCAT, November 2025: HLP lost about $4.9M [S]
      ([The Defiant](https://thedefiant.io/large-popcat-trades-result-in-usd5-million-loss-for-hyperliquid-vault)).
  - The brief records that HYPE is halted for New York residents on Robinhood.
- **Fundamentals as return predictors are weak and mostly unpublished.**
  - Șoiman's working paper finds no priced risk factor in DeFi once cross-sectional correlation is accounted for
    [A] ([RePEc](https://ideas.repec.org/p/hal/wpaper/hal-04507930.html)).
  - Industry reports find fees and revenue add a few points of explanatory power at six months [S].
  - Protocol revenue can flow to liquidity providers rather than token holders [S].
- **Reading.** A quality filter should cut the rate of deep fills that never recover, because large, established
  coins fail less often (repo 5.11; Messari). It cannot remove the risk. The failures that matter most (fraud,
  depegs, venue failure, governance intervention) hit "revenue" tokens too. The study should measure the filter's
  effect on the never-recovered rate with dead coins included, not assume it.

---

## 5. The repo's own related findings

- **Scalping and market making** (HANDOFF 5.21 on this branch; `analysis_2026/reports/Scalping and market
  making.md`; `analysis_2026/SCALPING_PREREG.md`). 0 PASS, 32 NO EDGE, 4 INCONCLUSIVE.
  - **Passive fills are adversely selected.** In Binance spot crypto, quotes at the best bid or ask captured +1.3
    to +5.9 bp of spread per fill. They lost 4.8-19.2 bp to the move over the next 5 minutes, for −4 to −18 bp net
    in every liquidity band.
  - **Coins Robinhood lists, including BTC and ETH** (exploratory A-RH stratum): every cell lost 2-22 bp per dollar
    filled before fees.
  - **Closest prior test of a stink bid: B3, the passive dip bid** (US thin stocks, 2001-2020). A day-limit buy at
    P × (1 − σ₂₀), filled only when the low trades through, sold at that day's close.
    - Net: −2.7% (L1) to −0.6% (L4) per trade, NO EDGE in every band. The report says B3 "loses before any cost":
      fills come just before further intraday falls, which matches the intraday-momentum evidence in 4.1.
    - Exploratory variants in L1, per trade, same metric (`results_scalping/B/exploratory.csv`): a 2σ bid −2.3%;
      a hold to t+6 −2.5%; the highest-VIX tercile −3.2%, worse than the others.
    - The test is shallow (1σ) and in stocks, so it does not settle deep crypto wicks. It is the base case the
      wick hypothesis has to beat.
  - **Robinhood crypto costs.** About 0.95% per side on the default route (about 1.9% round trip; a 1.87% BTC
    spread was observed; `analysis_2026/costs.py`, FINDINGS 2026-10-13). That is small against the rebound from a
    40% wick and large against a 5-10% dip.
- **Bollinger-breakout replication** (HANDOFF 5.22; `analysis_2026/reports/Bollinger breakout replication.md`;
  engine `analysis_2026/bb_*.py`). Methods to reuse:
  - leave-out drift adjustment of trade returns;
  - month-block bootstrap with Holm across tests;
  - a luck benchmark of 1,000 random-entry versions;
  - controls first, enforced by the command-line stages;
  - fills only when price trades through the level, checked on 1-minute bars (650,746 fills audited, 0 violations);
  - mark-price liquidation.

  Facts: the 2025-10-10 Binance spot lows above. The data paths (`fetch_bb_data.py`, 1-minute perpetual klines)
  carry over.
- **Moving-average bounces, "key levels"** (HANDOFF 5.19; FINDINGS 2026-10-15; `analysis_2026/ma_bounce.py`).
  - Placebo lines shifted 1-2 ATR, following Osler (2000), across 34 averages.
  - No average beat its placebo lines, under any baseline.
  - Crypto (41 series from 40 coins: FTT split around its delisting gap, LUNA included) showed **no bounce**:
    −2.2% against the coin pool over 28 days (−1.05% without old LUNA).
  - **Lessons:**
    - Old LUNA alone moved the crypto results, so one collapse can dominate a coin sample.
    - The same-year drift baseline is biased (it includes the decline that produced the touch); use leave-out drift
      or a pool, plus a no-edge simulation.
    - The 2009 rebound carried a subset's positive lean, so check for single-episode results.
- **Buying mega-caps after a 25% drop** (default branch `origin/claude/add-price-data-csvs-MTD46`, HANDOFF 5.21
  there; `analysis_2026/MEGACAP_DIP_PREREG.md`).
  - All three primary tests failed (top-10 +0.98% a year, top-20 −4.07%, all members −0.20%; p 0.37-0.89).
  - **Buying the same stocks on random days did as well as buying the dips.**
  - The hindsight Magnificent-7 result (+25% a year) is survivorship.
  - Index dips were not reliably followed by better 12-month returns (13 events).
  - Design elements to reuse:
    - calendar-time portfolios for clustered events (Jaffe-Mandelker);
    - a stationary bootstrap with year-long blocks;
    - the "timing vs owning" placebo (200 random entries per event in the same stock);
    - point-in-time universes.
  - The only lead, holding 2.5-5 years, was not pre-registered.
- **Small coins and crashes** (HANDOFF 5.11): 37% of coin-years fell more than 60%. **Leverage** (HANDOFF 5.14):
  3-5x blew up 85-100% of coin sub-accounts, so a stink bid must be spot and unlevered.

**What these imply here.**
1. Expect adverse selection by default. Passive fills lost in every crypto band and in the shallow US dip-bid test.
2. Benchmark fills against buying the same coin at market at the same time, against random entries, and against
   the coin's own leave-out drift. Use calendar-time or event-clustered inference.
3. Use placebo levels at the same volatility depth for any level-finding method.
4. Include dead coins (LUNA, FTT and delisted Binance pairs) and report results with and without single collapses.
5. Model fills as trades through the level on 1-minute or trade data. Report touch fills only as an upper bound.

---

## 6. What the evidence predicts for the user's idea

**By kind of fill** (predictions to test, not results):

| kind of fill | hours to days after the fill | 1-6 months, against buying at market when the bid was placed | main evidence |
|---|---|---|---|
| fast, deep (several σ), high-volume, market-wide wick | rebound likely as the overshoot reverses | about the market; set by the regime that follows | drift bursts; Nagel; Campbell-Grossman-Wang; Brogaard; flash crashes |
| fast, coin-specific drop (hack, exploit, delisting, news) | weak or further decline | negative (information) | Savor; Chan; Linnainmaa; Copeland-Galai |
| slow decline to the level over days or weeks | continuation | about zero or negative | momentum; Cox-Peterson; AQR; K33; repo dip studies |
| one-venue glitch | instant snap-back | a windfall if it fills and the venue honors it; rare and impossible to forecast | GDAX 2017; Binance.US 2021; 2010 broken trades |
| first leg of a collapse (LUNA, FTT) | looks like a wick | −90% to −100% | Liu-Makarov-Schoar; FTT |

**In plain terms.**
- **Most deep bids will never fill.** Those that do will mostly fill on a few market-wide crash days, all at once,
  or through slow declines if left open for weeks.
- **Wick fills sold into the rebound** are the one place the evidence leans positive. Their value per bid placed
  is small, because fills are rare and the deepest prints are often venue-specific.
- **Owning the fill for months** is expected to match buying at market or at random times, with crash-sized
  dispersion and a real chance of a never-recovered loss.
- **Chart levels** may shift fill odds, mostly by putting a bid beyond stop clusters. They are not expected to
  improve what happens after the fill.
- **A "solid / real revenue" filter** should lower the collapse rate. It does not reach zero, and it moves the bids
  toward large coins, which lean to momentum rather than reversal.
- **Expect wide intervals.** With only a handful of independent crash events, INCONCLUSIVE is a likely verdict for
  any return test.

---

## 7. Hypotheses worth testing, and design cautions

**Descriptive.** Allowed before pre-registration, because they use fill frequencies only.
- **D1, wick frequency and clustering.** For each coin and depth (in σ units of trailing volatility and in percent),
  how often the 1-minute low trades through a level set k σ below a reference price, within 1 hour, 1 day and
  1 week. What share of those touches fall on market-wide days (for example, at least half the coins touching in
  the same hour)?
  - Prediction: heavy clustering, with a few days supplying most of the deep touches.
- **D2, fill mix by order lifetime.** For bids left open 1, 7, 30 and 90 days, what share of fills come from fast
  drops (the level reached within N minutes of a recent high) against slow ones.
  - Prediction: slow fills dominate beyond a few days at moderate depth (section 1.2).
- **D3, venue gap.** Depth of the same wick on Binance spot, Binance perpetuals (mark and last) and a US venue.
  Coinbase is reachable only in the later session's environment.
  - Prediction: Binance perpetual wicks are deepest, then Binance spot, then US venues, with the largest gaps in
    altcoins (Gornall et al.; 2021 and 2025 venue events).
  - The fill rule on Robinhood (bid against its quoted ask, and the roughly 0.95% markup) is a venue question for
    the venue researcher [U].

**Confirmatory** (pre-register before any outcome is computed):
- **H-speed.** At equal depth in σ units, fast-wick fills earn more over 1 hour to 7 days than slow-decline fills.
  - Predicted sign: positive.
  - Motivation: drift bursts; Campbell-Grossman-Wang; Savor; Chan.
  - This is the "slow-dip control" the brief asks for.
- **H-depth.** Post-fill return rises with depth in σ units: deeper fills sit further inside the overshoot.
  - Predicted sign: positive. Watch for collapse coins dominating the deepest bins.
- **H-breadth.** Market-wide wick fills beat coin-specific ones.
  - Predicted sign: positive (Brogaard; Nagel; information versus liquidity).
- **H-flow.** Fills that coincide with liquidation spikes or high volume revert more.
  - Predicted sign: positive (Campbell-Grossman-Wang; drift bursts).
  - Data: Binance futures `metrics` (open interest) and aggTrades are in the archive. A liquidation feed is not
    [U: check].
- **H-exit.** Selling into the rebound (a target in σ units, or a time stop of hours to days) against holding 30,
  90 and 180 days.
  - Benchmarks: market entry when the bid was placed; random entries; T-bills on idle cash.
  - Prediction: any edge sits in the short exits. Long holds are about zero against buying at market (repo
    mega-cap dips; AQR; K33).
- **H-levels.** Each level method (prior swing lows, round numbers and the zone just below them, volume-profile
  nodes, Fibonacci, liquidation-band estimates) against placebo levels at the same σ depth.
  - Prediction: no difference after the fill (5.19; Osler 2000 is a small effect; Fibonacci null). Possibly a
    higher fill rate just below round numbers and swing lows (Osler 2003, 2005).
- **H-quality.** A point-in-time "solid" filter (size, age, listing and, where data exist, revenue) against all
  coins, on the rate of fills still at least 50% under water after 12 months, with LUNA, FTT and delisted pairs
  included.
  - Prediction: lower but not zero. Test it; do not assume it.

**Design cautions.**
- **Effective sample.** Count independent crash events, not fills. Cluster inference by event-day or month, or use
  calendar-time portfolios.
  - There have been roughly 10-20 market-wide crash days since 2020 [U: from memory; D1 will count them].
  - Minimum detectable effects will be large, and that should be stated before any result.
- **Fill realism.** Count a fill only when the price trades through the level, using 1-minute bars or aggTrades,
  with a size cap set by the volume traded through the level. Touch fills are an upper bound (Lo, MacKinlay & Zhang).
  - Use spot prices for a spot stink bid. Perpetual lows overstate them; use the mark price for anything involving
    liquidation.
- **Venue.** Binance wicks are an upper bound for a US user. Some extreme prints are single-venue or were later
  compensated or reversed. A level sheet should quote fill odds on the most US-like price series available.
- **Survivorship and selection.**
  - Use a point-in-time universe that keeps dead coins.
  - HYPE (launched in late 2024; Binance spot data only from 2025, per the brief) and NEAR are hindsight choices:
    report them, but keep the inference on the point-in-time universe.
  - Report results with and without the single largest collapse.
- **Baselines.** Avoid same-year drift, which is biased in 5.19. Use leave-out drift or the coin pool plus a
  no-edge simulation, and the "timing vs owning" placebo from the mega-cap study.
- **Controls.**
  - Positive control: a synthetic market with injected liquidity wicks that revert, which the engine must detect as
    a gain.
  - Negative control: a random walk, or bootstrap-resampled returns, at matched volatility, where post-fill returns
    must be about zero apart from drift.
- **Do not tune on the named episodes.** Fix depth units, the order-lifetime grid, exits and the coin filter before
  any outcome is computed.

---

## 8. Sources and their limits

- All literature claims come from abstracts, repository pages and search-result summaries. No full paper was read,
  because arxiv.org and repec.econ.au.dk were unreachable by WebFetch in this session. Numbers marked [S] or [U]
  should be confirmed before the report quotes them.
- Crash-day prices come from news and vendor research and differ by venue and source, for example the 2025-10-10
  BTC low ($101.5k to $104.8k) and the 2010 Dow close. Treat them as approximate.
- Practitioner sources on stink bids, volume profile and liquidation heatmaps offered descriptions, not tests. No
  published backtest of crypto stink bids was found. A TradingView script describes the idea without results [S]
  ([TradingView](https://in.tradingview.com/script/e515deFp-Stink-Bids)).
- The repo results cited in section 5 are audited and committed. They are the strongest evidence in this note for
  this user's setting.
