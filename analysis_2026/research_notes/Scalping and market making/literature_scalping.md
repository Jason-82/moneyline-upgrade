# Scalping and Bid-Ask Capture in Low-Volume Stocks: Can an Individual Profit, and at What Scale? Literature Review (as of Oct 2026)

> **How this was verified.** Direct page and PDF fetches (WebFetch and curl) failed in this sandbox for every publisher, SSRN, NBER, arXiv, RePEc, SEC, FINRA and Robinhood host tried (DNS failure). So every finding below comes from search-engine retrieval of abstracts, publisher and RePEc listings, author-hosted PDFs, and secondary write-ups. **No result was checked against a paper's full-text tables.** Tags:
> - **[A]**: matches the paper's own abstract, publisher or RePEc listing, or official rule or fee text, as retrieved this session.
> - **[S]**: secondary source only (law-firm memo, blog, press, practitioner summary, a later paper quoting the number, or this repo's own notes).
> - **[U]**: from memory, unverified or conflicting. Treat as a lead, not a fact.
>
> Several abstracts changed numbers between working paper and journal version; where that happened the published figure is given and the conflict noted. Re-check every effect size against the PDF before it goes into a pre-registration.

**Fact-check (date 2026-10-17): 150 claims checked, 20 corrections.**
- **How:** each citation and number was compared with the search results the author actually retrieved this session, with the sibling notes `practicalities_us.md` and `crypto_data_feasibility.md`, and with repo files and data. `capacity.py` was rerun, the Binance pilot results were read, and the S3 listing was re-tested and is reachable.
- **Limits:** no new web searches were possible (budget exhausted) and no primary page could be fetched, so no tag was upgraded. All 117 cited URLs appeared in the author's retrieved results; none was invented.
- **Main fixes:** Rule 610/612 compliance is now Nov 2027, not 2026-11-02. Coinbase, Binance.US and Robinhood crypto fees were stale or lacked the routing caveat. The ORB "no spread or slippage" critique belonged to a different paper. Agentic-approval latency was overstated. The capacity risk multiple was understated.

---

## Bottom line

**Answer: possible in principle, very unlikely at retail speed, and size works against you in thin stocks.**

- **The spread is not profit.** In a competitive market the spread pays for adverse selection, inventory risk and processing costs. The slice a liquidity provider keeps is small and shrinks with the horizon over which it is measured:
  - US net liquidity-provision profit was **1.9 bp of dollar volume in 2010 and 1.0 bp in 2017, measured at a 100 ms horizon** (Conrad-Wahal).
  - Price impact is mostly complete **within 15 s for large caps and 60 s for small caps**.
  - A trader who needs seconds to minutes to react is therefore marked out after almost the whole adverse move has happened.
- **Wide spreads in low-volume stocks mean high costs for the liquidity provider, not easy money.** Theory (Glosten-Milgrom, Kyle, Ho-Stoll) and evidence (spread ≈ volatility per trade, R² > 0.9) agree on this.
- **A few fast firms earn the profits.**
  - Six firms win or lose over 80% of latency-arbitrage races.
  - HFT revenue is concentrated in the fastest firms, and new entrants are less profitable and exit.
- **Individuals' limit orders are a good way to execute, not a strategy in themselves.**
  - Retail limit orders cost about 10 bp less than market orders.
  - "Unconditional" liquidity offering against the NYSE specialist was not profitable.
  - Passive fills are adversely selected: a fill tends to arrive just before the price moves against you.
- **Day traders mostly lose.**
  - Under 1% of Taiwanese day traders were predictably profitable net of fees.
  - 97% of Brazilians who persisted for more than 300 days lost money.
  - US samples from the 1998–2000 bubble show 1/3 to 1/2 profitable.
  - The documented profitable minorities (SOES bandits, a 2000 prop team) won on *speed against stale dealer quotes*. That edge now belongs to HFTs.
- **Daily and weekly reversal is the slow version of being paid for liquidity.**
  - Gross reversal returns are largest in illiquid stocks, but there they are smaller than likely costs.
  - Net profits of 30–50 bp/week exist only in large caps with careful construction.
  - Reversal magnitudes fell after 2000.
- **Scale is the binding constraint, and "lots of money" makes it worse in a thin stock.** Square-root law: the impact of one side is about (0.5–1) × daily vol × √(position / ADV).
  - Example: a stock with $1M ADV, 5% daily vol and a 1% spread.
  - A $250k position (25% of ADV) costs about 1.25–2.5% per side, more than the spread itself.
  - A passive provider's volume is capped by *other people's* order flow. Under generous assumptions that is tens to hundreds of dollars a day per stock (section 8).
- **Robinhood makes the passive version harder still.**
  - No exchange rebates reach the customer.
  - Agentic orders go through a preview and explicit user confirmation (Robinhood's tool rules). In-app trade approvals are optional and off by default for external agents, but this repo's plan keeps them on. Latency is seconds to minutes per order.
  - Extended hours accept limit orders only.
  - The agentic account is cash or limited margin. In a cash account, T+1 settlement limits how many round trips a day can be funded; limited margin lets unsettled stock proceeds be reused. [S: repo `AGENTIC_TRADING_PLAN.md` §1 and §8; cash-account settlement limits [U]]
- **What the friend is most likely doing** (section 10):
  - momentum or attention trading in low-float names;
  - mark-to-market "gains" that his own buying created;
  - bull-market luck and survivorship.
  - True passive market making at small size in a niche is possible but rare.

---

## 1. Spread decomposition: how much of the spread does the liquidity provider keep?

### Definitions

Take a trade at price P, with midquote m₀ at the time of the trade and m_Δ a time Δ later. d = +1 for a buy, −1 for a sell, from the liquidity *taker's* side.

| Measure | Formula | Who it is about |
|---|---|---|
| Effective spread | 2·d·(P − m₀) | What the taker pays |
| Realized spread | 2·d·(P − m_Δ) | What the liquidity provider keeps |
| Price impact (adverse selection) | 2·d·(m_Δ − m₀) | The move that goes against the provider |

The identity is **effective spread = realized spread + price impact**. The provider's profit per dollar traded is about **realized spread / 2**, before fees, rebates and inventory risk. [U: standard textbook definitions; the Rule 605 definitional text was not retrieved]

### SEC Rule 605 markout horizons
- **Old rule:** the legacy Rule 605 report used a single 5-minute horizon. [U]
- **Proposal:** the SEC's proposal listed realized spreads at 15 seconds and 1 minute. [S] — [Sidley memo](https://www.sidley.com/en/insights/newsupdates/2024/04/sec-adopts-amendments-to-modernize-disclosure-of-order-execution-information)
- **Final rule (adopted 2024-03-06, Release 34-99679):** Sidley's summary describes realized-spread horizons "ranging from less than 100 microseconds to 5 minutes". [S] The specific list (50 ms, 1 s, 15 s, 1 min, 5 min) came from a search-engine summary, and the "100 microseconds" wording may describe time-to-execution buckets instead. [U] — [Sidley memo](https://www.sidley.com/en/insights/newsupdates/2024/04/sec-adopts-amendments-to-modernize-disclosure-of-order-execution-information); [SEC final rule PDF (not fetched)](https://www.sec.gov/files/rules/final/2024/34-99679.pdf)
- **Compliance date:** a Law360 piece by Sidley lawyers gives 2025-12-14. Later delays were not checked. [S/U] A mid-2026 report on the Rule 610/612 deferral lists "Rule 605 reporting" among firms' 2026 work, which suggests the date moved. [U] — [Sidley/Law360 PDF](https://www.sidley.com/-/media/publications/law360--sec-amendments-may-launch-new-execution-disclosure-era.pdf)

### What share of the spread the provider keeps

| Study | Sample | Finding | Tag |
|---|---|---|---|
| Huang & Stoll (1997) RFS 10(4) | 20 large NYSE stocks, 1992 [U] | "a large order processing component and smaller adverse selection and inventory components." Adverse selection is **9.6% of the spread (range 1.4–22%) or 21.5%**, depending on the decomposition. Order processing is about 62% in the three-way model [U]; about 90% is quoted for the two-way model [S]. | [A] wording, [S] numbers — [RePEc](https://ideas.repec.org/a/oup/rfinst/v10y1997i4p995-1034.html); [Southampton WP quoting it](https://eprints.soton.ac.uk/37345/1/CRR-05-07.pdf) |
| Stoll (1989) JF | Nasdaq/NMS stocks, 1984 [U] | Adverse information about 43%, inventory 10%, order processing 47%. One source confirms only the "large adverse-selection, small inventory component" direction. | [U] numbers; [S] direction — [Chung lecture reading](https://www.acsu.buffalo.edu/~keechung/MGF743/Readings/Estimation%20of%20the%20bid-ask%20spread%20and%20its%20component.pdf) |
| Huang & Stoll (1996) JFE 41(3) | Matched Nasdaq vs NYSE pairs, 1991 [U] | Quoted, effective and **realized** spreads are **about 2× larger on Nasdaq**. The difference is not due to adverse information. It reflects internalization and preferencing, which reduce dealers' incentive to narrow spreads. Dealer rents existed when competition was blocked. | [A] — [RePEc](https://ideas.repec.org/a/eee/jfinec/v41y1996i3p313-357.html) |
| Bessembinder & Kaufman (1997) JFQA 32(3) | Large, medium and small caps, 1994 | All cost measures, including **realized** spreads, are larger on Nasdaq. Differentials are **greater for medium and small caps** and for small trades. They "cannot be attributed to... adverse selection costs." | [A] — [RePEc](https://ideas.repec.org/a/cup/jfinqa/v32y1997i03p287-310_00.html) |
| Hendershott, Jones & Menkveld (2011) JF 66(1) | NYSE autoquote rollout, 2003 | Algorithmic trading narrows quoted and effective spreads and **reduces adverse selection**. Effects are concentrated in **large stocks**. | [A] — [author PDF](https://faculty.haas.berkeley.edu/hender/Algo.pdf) |
| **Conrad & Wahal (2020) JFE 136(1)** | US common stocks, 2010–2017; horizons 100 ms to minutes | Realized spreads **slope downward** and price impact **slopes upward** with horizon. Most price impact occurs **within 15 s for large caps and 60 s for small caps**. Net provider profit at 100 ms fell from **1.9 bp of dollar volume (2010) to 1.0 bp (2017)**. The NBER working paper (2000–2015) shows the **1-second** net price of liquidity falling from **17 bp (2000) to 1.5 bp (2015)**. | [A] — [RePEc](https://ideas.repec.org/a/eee/jfinec/v136y2020i1p239-259.html); [NBER WP](https://conference.nber.org/conf_papers/f90128/f90128.pdf) |
| Menkveld (2013) JFM | One HFT in Dutch index stocks, Chi-X and Euronext, 2007–08 | Per trade: **€1.55 earned on the spread (net of fees) minus a €0.68 positioning loss**, so about €0.88 gross. Positions held **under 5 s made €0.45, but longer ones lost €1.13**. 4 of 5 of its trades were passive. | [A] WP abstract; [S] subtotal — [VU listing](https://research.vu.nl/en/publications/high-frequency-trading-and-the-new-market-makers/); [Tinbergen WP](https://repec.tinbergen.nl/tin/wpaper/11076.rdf) |
| Barclay & Hendershott (2004) JF | Nasdaq after-hours | Under **1/20 as many trades per unit time** as in the day. Quoted and effective spreads are **3–4× larger**, which the authors attribute to **adverse selection, not higher dealer profit**. | [A] — [abstract mirror](https://academicnewsletter.sufe.edu.cn/info/361191) |
| Sensoy et al. (2023) J. Financial Research | Bitfinex crypto order book | Adverse selection is about **10% of the effective spread**. | [S] — [KHAS repository](https://academicrepository.khas.edu.tr/xmlui/handle/20.500.12469/5613) |

**Synthesis**
- **Two regimes.** In the 1990s much of the spread was rent (Nasdaq dealers, NYSE specialists). Since decimalization and automation that rent has been competed away to about 1–2 bp of dollar volume for the fastest providers.
- **Horizon.** What a provider keeps depends almost entirely on how quickly it can exit or hedge. The share kept is positive at 100 ms to 1 s and shrinks at 15 s to 60 s. At the old 5-minute Rule 605 horizon it is often near zero or negative for small caps. [U for the small-cap 5-minute sign]
- **Missing number.** A clean "share of spread kept by size decile at 5 s, 1 min and 5 min" table was **not retrieved**. Conrad-Wahal's JFE tables are the place to get it.

---

## 2. Adverse-selection and inventory models: predictions for illiquid, volatile small caps

| Model | Core mechanism | Prediction for thin, volatile small caps | Tag |
|---|---|---|---|
| Glosten & Milgrom (1985) JFE | Informed traders alone create a positive spread "even when the specialist is risk-neutral and makes zero expected profits". With too many informed traders the market can shut down. | Wider spreads where information asymmetry is high (small, opaque, news-driven firms). **The wide spread is the zero-profit level, not a margin.** | [A] — [PDF](https://www.edegan.com/pdfs/Glosten%20Milgrom%20%281985%29%20-%20Bid%20Ask%20and%20Transaction%20Prices%20in%20a%20Specialist%20Market%20with%20Heterogeneously%20Informed%20Trades.pdf) |
| Kyle (1985) Econometrica 53(6) | Noise traders camouflage an insider. Price moves linearly with order flow (slope λ); depth is 1/λ. | Where noise volume is low, λ is high: each dollar of order flow moves the price more. **A large buyer in a thin stock moves the price against himself.** | [A] — [Econometric Society](https://econometricsociety.org/publications/econometrica/1985/11/01/continuous-auctions-and-insider-trading) |
| Ho & Stoll (1981) JFE 9 | A dealer manages inventory under uncertainty about when orders arrive and what prices will do. The spread rises with volatility, risk aversion and trade size, and falls with order-arrival rate. | Low arrival rate plus high volatility means long holding periods, high inventory variance and a wide spread just to break even. | [S] — via [vLex review](https://eu.vlex.com/vid/determinants-of-the-components-855636437) |
| Avellaneda & Stoikov (2008) Quant. Finance | Reservation price r = s − q·γ·σ²·(T−t). Optimal total spread δᵃ+δᵇ = γσ²(T−t) + (2/γ)·ln(1 + γ/κ), where κ is order-book liquidity. | A high σ² or a low κ (thin book) widens the optimal quotes **and** skews them against inventory. A provider who will not skew, such as someone who "buys big and waits", carries the full σ² risk. | [S] reservation price — [Hummingbot docs](https://hummingbot.org/strategies/avellaneda-market-making); [U] the closed-form spread (from memory) |
| Wyart, Bouchaud, Kockelkoren, Potters & Vettorazzo (2008) Quant. Finance 8(1) | Competition between limit and market orders gives spread ∝ impact. Empirically, **spread vs. volatility per trade has R² > 0.9**. The main determinant of the spread is adverse selection. The NYSE showed specialist rents. | **The spread-to-volatility ratio is roughly constant across stocks.** A wide spread comes with matching per-trade volatility. | [A] — [arXiv](https://arxiv.org/abs/physics/0603084) |
| Hendershott & Menkveld (2014) JFE 114(3) | Risk-averse NYSE intermediaries use price pressure to steer inventory. | Price pressure averages **0.49%, with a half-life of 0.92 days** (NYSE average stock). Even there, inventory takes about a day to half-unwind; thin stocks are likely slower [U]. | [S] numbers — [RePEc](https://ideas.repec.org:443/a/eee/jfinec/v114y2014i3p405-423.html) |

**The key quantity is S / (σ·√h).**
- S is the quoted spread; σ·√h is the price volatility over the time h you expect to hold inventory before the offsetting trade arrives.
- Bid-ask capture can only work when S is large relative to σ√h.
- **Worked example:** daily vol 6%, about 6.5 trading hours a day, so σ over one hour ≈ 6%/√6.5 ≈ 2.4%. If the next opposite-side trade takes an hour, a 1% spread is less than half of one hour's standard deviation, and adverse selection makes the *expected* move negative. [U: illustration]
- **Implication:** volatile small caps fail this test unless trades arrive many times per minute. By then HFTs are present and the spread is competitive.

---

## 3. Who earns liquidity-provision profits today

- **Menkveld (2013)**
  - A single HFT took part in 8.1% of Euronext trades and 64.4% of Chi-X trades.
  - It earned on the spread and lost on inventory. The entrant venue's success "critically depended" on it.
  - [A] — [VU listing](https://research.vu.nl/en/publications/high-frequency-trading-and-the-new-market-makers/)
- **Brogaard, Hendershott & Riordan (2014) RFS**
  - HFTs trade in the direction of permanent price changes. Their **passive (liquidity-supplying) orders are adversely selected**.
  - The spread plus rebates exceed those adverse-selection costs.
  - [A] — [abstract mirror](https://academicnewsletter.sufe.edu.cn/info/354200); [ECB WP 1602](https://ecb.eu/pub/pdf/scpwps/ecbwp1602.pdf)
- **Baron, Brogaard, Hagströmer & Kirilenko (2019) JFQA 54(3)**
  - **Relative latency** explains large differences in HFT performance. Firms that move up the latency ranking through colocation upgrades earn more.
  - [A] — [RePEc](https://ideas.repec.org/a/cup/jfinqa/v54y2019i03p993-1024_00.html)
  - The 2014 CFTC working paper (E-mini futures, 2 years) adds that revenue is concentrated among a few firms "consistent with winner-takes-all", and new entrants are less profitable and more likely to exit. [A] WP — [CFTC WP](https://www.cftc.gov/idc/groups/public/@economicanalysis/documents/file/oce_riskandreturn0414.pdf)
- **Budish, Cramton & Shim (2015) QJE 130(4)**
  - ES futures and SPY (2005–2011) are almost perfectly correlated at a minute but uncorrelated at a millisecond. That gap creates a pure speed race, a "symptom of flawed market design". [A] — [RePEc](https://ideas.repec.org/a/oup/qjecon/v130y2015i4p1547-1621.html)
  - Arbitrage duration fell from about 97 ms (2005) to about 7 ms (2011) while profits per opportunity did not fall. [U]
- **Aquilina, Budish & O'Neill (2022) QJE**, LSE message data
  - Races occur about **once per minute per FTSE 100 symbol** and last **5–10 microseconds** (modal).
  - They account for **about 20% of volume**, and the **top 6 firms take over 80% of wins and losses**.
  - This amounts to a **0.5 bp "tax" on trading**. Eliminating it would cut the cost of liquidity by **17%**, worth about **$5bn a year** globally.
  - [A] — [FCA Occasional Paper 50](https://www.fca.org.uk/publications/occasional-papers/occasional-paper-no-50-quantifying-high-frequency-trading-arms-race-new-methodology); [BIS WP 955](https://www.bis.org/publ/work955.pdf)

**Profit per share and per dollar traded**

| Estimate | Value | Tag |
|---|---|---|
| Net liquidity-provision profit, US stocks (Conrad-Wahal) | 1.9 bp of dollar volume (2010) to 1.0 bp (2017), at 100 ms | [A] |
| HFT gross profit, 26-firm Nasdaq HFT dataset (NBER version of BHR) | about $0.0075 per $100 traded (0.75 bp), about **1/7 of what traditional market makers earned per dollar** | [S] — [NBER conference PDF](https://conference.nber.org/conf_papers/f5273/f5273.pdf) |
| Average US HFT profit per share | about $0.001 (2009) to about $0.0005 (2015) | [U: original source not identified] |
| Aggregate US HFT profit, 2013 | about $1bn on more than $21tn traded, i.e. about 0.5 bp | [U: commentator estimate; source page not identified] |
| Kearns et al. (2010), upper bound on HFT profit | fees of $0.006/share cut the bound by about 2/3 | [S] — [arXiv 1007.2593](https://arxiv.org/pdf/1007.2593) |

**Reading.** The profitable business is about **0.5–2 bp per dollar traded**, earned on trillions of dollars of volume, with microsecond infrastructure and exchange fee tiers. A retail trader has none of the three.

---

## 4. Individual limit-order traders

- **Handa & Schwartz (1996) JF 51(5)**
  - Limit orders carry two risks: an unwanted fill on adverse news, and no fill on favourable news.
  - Transient price swings can compensate. "Placing a network of buy and sell limit orders as a pure trading strategy is profitable."
  - [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1835-61.html)
  - **Context:** this was NYSE in the 1/8-dollar tick era, and the result holds for "well-balanced portfolios". [U for sample details]
- **Harris & Hasbrouck (1996) JFQA 31(2)**, NYSE SuperDOT
  - Limit orders at or better than the quote beat market orders, even after penalizing non-execution.
  - **But "unconditional strategies that use SuperDOT to offer liquidity in competition with the specialist do not appear to be profitable."**
  - [A] — [RePEc](https://ideas.repec.org/a/cup/jfinqa/v31y1996i02p213-231_00.html)
- **Linnainmaa (2010) JF 65(4)**, Finnish individuals
  - Losses around earnings announcements and the disposition effect can be *produced by limit orders* through "price-contingent execution combined with adverse selection".
  - This is the winner's-curse mechanism: you get filled when the price is moving through you.
  - [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1473-1506.html)
- **Kaniel & Liu (2006) J. Business 79(4)**
  - Informed traders often *prefer* limit orders, and limit orders can be more informative than market orders.
  - So the order resting next to yours may be the informed one.
  - [A] — [RePEc](https://ideas.repec.org/a/ucp/jnlbus/v79y2006i4p1867-1914.html)
- **Kelley & Tetlock (2013) JF 68(3)**, US retail order data
  - Net buying through both market and limit orders predicts *monthly* returns, with no reversal.
  - Only passive (limit) net buying follows negative returns. The authors read this as retail *supplying liquidity and profiting when transitory drops reverse*.
  - This is evidence for slow liquidity provision at monthly horizons, not for intraday spread capture.
  - [A] — [abstract mirror](https://academicnewsletter.sufe.edu.cn/info/360220); [author PDF](https://business.columbia.edu/sites/default/files-efs/pubfiles/4471/Kelley_Tetlock_JF_12_How_Wise_Are_Crowds_with_Appendix.pdf)
- **Barber, Lee, Liu & Odean (2009) RFS 22(2)**, all Taiwan trades
  - Individuals lose **3.8 percentage points a year** in aggregate, equal to 2.2% of GDP. "Virtually all individual trading losses can be traced to their **aggressive** orders."
  - Institutions gain 1.5 pp a year on both their aggressive and passive trades. [A] — [RePEc](https://ideas.repec.org/a/oup/rfinst/v22y2009i2p609-632.html)
  - A secondary summary says individuals' passive trades gain at short horizons but erode or reverse at long ones. [S] — [CXO summary](https://www.cxoadvisory.com/?p=481)
- **Anand, Samadi, Sokobin & Venkataraman, "Retail Limit Orders"** (SSRN 4964266; Review of Finance 2026)
  - Sample: 19 US retail brokers, 27M orders, May 2020, FINRA OATS data. Limit orders are 25.5% of orders.
  - Limit orders cost **about 10 bp less** than comparable marketable orders on implementation shortfall. The advantage is **larger in wide-spread, volatile, small-cap stocks**.
  - [A] — [SSRN](https://papers.ssrn.com/ab_id=4964266); [RevFin summary](https://revfin.org/retail-limit-orders)
  - Fill rates are about 65% in large and mid caps and about 60% in small caps. [S] — [SMU Cox summary](https://www.smu.edu/cox/coxtoday-magazine/2025-11-03-patience-in-trading-retail-investors)
- **Battalio, Corwin & Jennings (2016) JF 71(5)**
  - Brokers that route limit orders to maximize rebates get **worse limit-order execution quality**: lower fill rates and more adverse fills.
  - [A] — [abstract mirror](https://academicnewsletter.sufe.edu.cn/info/359806)
- **Albers, Cucuringu, Howison & Shestopaloff (2025) arXiv 2502.18625**, live maker orders on the Binance BTC perpetual
  - **Fill probability and post-fill return are negatively correlated.** Commonly cited maker strategies are "highly unprofitable".
  - Viable makers must be contrarian to order-book imbalance.
  - [A] — [arXiv](https://arxiv.org/abs/2502.18625v2)

**Reading**
- Using limit orders is a cost-saving way to *execute* a view.
- As a standalone "buy the bid, sell the ask" business, the evidence from 1996 SuperDOT to 2025 crypto says fills are adversely selected.
- The only clearly positive retail limit-order evidence is at **monthly** horizons (Kelley-Tetlock): reversal compensation, not spread capture.

---

## 5. Day-trader and scalper outcome studies

| Study | Sample | Key numbers | What the winners do | Tag |
|---|---|---|---|---|
| **Barber, Lee, Liu & Odean (2014) JFM 18**, "Cross-section of speculator skill" | Taiwan day traders, 1992–2006 | The top 500 by past performance then earn **61.3 bp/day before fees, 37.9 after**. The bottom group earns −11.5 / −28.9 bp/day. **Under 1% of day traders predictably earn positive abnormal returns net of fees.** The 2011 working paper gave 49.5 / 28.1. | Persistence exists but is thin. Order style was not retrieved. [U] | [A] — [RePEc](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html) |
| Barber, Lee, Liu, Odean & Zhang, "Learning, fast or slow" (RAPS 2020 [U: venue]) | Taiwan, 1992–2006 | Aggregate performance negative; the vast majority unprofitable. **Over 75% quit within 2 years**, and poor performers quit more. Over half of day trading comes from experienced traders with a history of losses. | No rational learning for many. | [S/A] — [working-paper PDF](https://www.econ.puc-rio.br/uploads/adm/seminarios/Learning_fast_or_slow_180606.pdf) |
| Barber, Lee, Liu & Odean (2004 WP), "Do day traders make money?" | Taiwan | Day trading is over 20% of volume. **About 1% of individuals account for 50% of day trading.** | n/a | [S] — [CXO summary](https://www.cxoadvisory.com/individual-investing/do-day-traders-make-money/) |
| **Chague, De-Losso & Giovannetti (2020 WP)**, "Day trading for a living?" | Brazil mini-Ibovespa futures; **19,646** first-time day traders, 2013–15 | **97% of those who persisted over 300 days lost money.** 1.1% earned more than the minimum wage; 0.4–0.5% more than a bank teller (US$54/day). The best earned **US$310/day with a daily SD of US$2,560**. No evidence of learning. | n/a | [A] — [RePEc](https://ideas.repec.org/p/fgv/eesptd/525.html); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101) |
| Kuo & Lin (2013) JBF 37(9) | 3,470 Taiwan futures day traders, Oct 2007–Sep 2008 | Average loss **NT$61,500 after costs** (NT$26,700 before). Overconfidence explains it. Excessive trading hurts only the losers. | n/a | [A] — [HKU](https://hub.hku.hk/handle/10722/184789) |
| **Harris & Schultz (1998) JFE 50(1)**, "SOES bandits" | Nasdaq SOES day traders, mid-1990s | "Average profit per trade is small, but they trade dozens or hundreds of times per week." | **They take liquidity from stale dealer quotes:** they establish a position before most market makers update, then lay it off through Instinet or SelectNet. | [A] — [RePEc](https://ideas.repec.org/a/eee/jfinec/v50y1998i1p39-62.html) |
| Garvey & Murphy (2005) J. Empirical Finance 12(5) | 96,323 trades of one US prop day-trading team, 2000 [U: year not in the retrieved abstract] | The team was profitable. | Profitable traders trade "when and where liquidity traders are present" and **"precede most market makers in updating their quotes"**. They used ECN limit orders inside the spread. [U] | [A] 2002 conference abstract — [abstract](https://content.csbs.utah.edu/~ehrbar/erc2002/abstracts/A407.html); [RePEc](https://ideas.repec.org/a/eee/empfin/v12y2005i5p629-649.html) |
| Garvey & Murphy (2005) J. Applied Finance 15(2) | **1,386** day traders at a US direct-access broker, 2000-03-08 to 2000-06-13 | **About half profitable after commissions.** Winners made +$9.5M and losers −$4.6M over 3 months. Winners and losers look alike on observable traits. Luck cannot be separated from skill. | n/a | [S] — [CXO summary](https://www.cxoadvisory.com/individual-investing/the-odds-of-winning-as-an-active-trader/); [author PDF](https://www.nuff.ox.ac.uk/Users/MurphyA/Active%20Traders.pdf) |
| Jordan & Diltz (2003) FAJ 59(6) | About 334 US day-trader accounts, Feb 1998 – Oct 1999, per a trading-education site [S]; the 324 figure was not found in any source [U] | About **2 losers per winner**. About **20% more than marginally profitable**. **Profitability tracks the Nasdaq index.** | Bull-market dependence. | [A] — [RePEc](https://ideas.repec.org/a/taf/ufajxx/v59y2003i6p85-94.html); [CFA](https://rpc.cfainstitute.org/research/financial-analysts-journal/2003/the-profitability-of-day-traders) |
| Seasholes & Wu (2007) JEF 14(5) | Shanghai stocks hitting the upper price limit | Attention-driven individuals buy, then prices mean-revert over the following week. **"Rational traders (statistical arbitrageurs) profit"** from that buying. | **The winners sell to (provide liquidity to) attention buyers.** | [A] — [author PDF](https://www.bauer.uh.edu/wu/Papers/JEF2007_Attention.pdf) |

**Robinhood era (US, 2020–2026)**
- **Barber, Huang, Odean & Schwarz (2022) JF 77(6)**
  - Intense Robinhood herding predicts **−4.7% 20-day abnormal returns** for the top stocks bought each day. App features are partly the cause.
  - [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v77y2022i6p3141-3190.html)
- **Barber, Lin & Odean (2023/24) JFQA**
  - Retail order imbalance predicts returns in equal-weighted tests, yet **retail trades are not profitable**.
  - Long-short on extreme retail imbalance earns **−14.8% a year in heavy-retail stocks** and +6.6% elsewhere.
  - [A] — [JFQA](https://jfqa.org/?p=9267)
- **Eaton, Green, Roseman & Wu (2022) JFE 146(2)**
  - When Robinhood goes down, high-retail-interest stocks show *more* liquidity and *lower* volatility. Robinhood herding creates inventory risk for market makers.
  - [A] — [RePEc](https://ideas.repec.org/a/eee/jfinec/v146y2022i2p502-528.html)
- **Ozik, Sadka & Shen (2021) JFQA**
  - Retail trading in the 2020 lockdown dampened the rise in illiquidity by **about 40%**. [A] — [Cambridge](https://www.cambridge.org/core/product/7D5EBA559DC12E2BD65D53E9BAE924A1)
  - Moving from the bottom to the top decile of retail holdings goes with an effective spread about 19% lower. [S] — [BC News](https://www.bc.edu/content/bc-web/bcnews/campus-community/faculty/lockdown-investors.html)
- **Schwarz, Barber, Huang, Jorion & Odean, "The 'actual retail price' of equity trades"** (JF 2025, 80(5))
  - The authors placed 85,000 simultaneous market orders across six accounts at five brokers.
  - The **mean round-trip cost ranges from 0.07% to 0.46%** across accounts, excluding commissions. 1 bp across all retail trades is about $2bn a year.
  - Robinhood was not the cheapest. [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v80y2025i5p2507-2541.html)
  - The ranking itself comes from press coverage. [S] — [WashU Olin](https://olin.washu.edu/about/news-and-media/news/2022/10/study-finds-astonishing-differences-in-brokers-pricing-of-stock-trades.php)
- **Press:** Vanda Research data reported in 2022 that the retail "day trader army" lost all the gains it made in the meme-stock era. [S] — [Business Standard / Bloomberg](https://www.business-standard.com/amp/article/international/epic-fail-day-trader-army-loses-all-the-money-it-made-in-meme-stock-era-122050901338_1.html)
- **Gap:** no peer-reviewed US account-level day-trader P&L study for 2020–2026 was found.

**Synthesis**
- **Fraction profitable:** under 1% (Taiwan, predictably), about 1–3% (Brazil), and 1/3 to 1/2 (US 1998–2000, in a bubble window that tracked the Nasdaq).
- **Persistence:** real but narrow (the top 500 of hundreds of thousands).
- **What winners did:** the US winners of the 1990s–2000 *took* stale quotes faster than dealers (SOES bandits, the prop team). In Shanghai they *supplied* liquidity to attention buyers.
- **What survives today:** neither speed edge is available at retail latency in 2026. The attention-liquidity edge is the one most plausibly still open.

---

## 6. Short-term reversal as compensation for liquidity provision (daily and weekly)

| Study | Sample | Gross / net finding | Tag |
|---|---|---|---|
| Lehmann (1990) QJE 105(1) | US weekly | Sizeable weekly winner/loser reversals. Profits "persist after corrections for... thin trading and bid-ask spreads and for plausible levels of transactions costs". Attributed to an inefficient market for liquidity around large price moves. | [A] — [NBER](https://www.nber.org/papers/w2533) |
| Lo & MacKinlay (1990) RFS 3 | US weekly | Much contrarian profit comes from **lead-lag** (big stocks lead small ones), not overreaction. Less than 50% is from overreaction. [S] | [A] — [MIT](https://web.mit.edu/~alo/www/Papers/lo-mackinlay-90b.html) |
| **Avramov, Chordia & Goyal (2006) JF 61(5)** | US, weekly and monthly | Reversals are tied to **illiquidity**. The largest are in **high-turnover, low-liquidity** stocks, as non-informational demand for immediacy is accommodated. **Profits are smaller than likely transaction costs.** | [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v61y2006i5p2365-2394.html) |
| **Nagel (2012) RFS 25(7)** | US, 1998–2010 [U] | Reversal returns are a **proxy for returns to liquidity provision**. They are strongly time-varying and **predictable with the VIX**; expected returns and Sharpe ratios soar in turmoil (2007–09). | [A] — [RePEc](https://ideas.repec.org/a/oup/rfinst/v25y2012i7p2005-2039.html); [NBER](https://www.nber.org/papers/w17653) |
| Da, Liu & Schaumburg (2014) Mgmt Sci 60(3) | US monthly | Returns *not* explained by cash-flow news reverse. An enhanced strategy earns **4× the standard risk-adjusted return** (the working paper says 3×). | [A] — [INFORMS](https://pubsonline.informs.org/doi/fpi/10.1287/mnsc.2013.1766) |
| **De Groot, Huij & Zhou (2012) JBF 36(2)** | US weekly | Cost drag comes mainly from **small caps**. Large caps plus low-turnover construction give **30–50 bp/week net**. The cost model assumes about $1M trades. [S] | [A] — [RePEc](https://ideas.repec.org/a/eee/jbfina/v36y2012i2p371-382.html) |
| Blitz, Huij, Lansdorp & Verbeek (2013) JFM 16(3) | US monthly | Residual (factor-neutral) reversal earns **2×** the conventional version, and is significant **net of costs even in large caps after 1990**. | [A] — [EUR repository](https://repub.eur.nl/pub/40707) |
| Collin-Dufresne & Daniel (2014 WP), "Liquidity and return reversals" | 100 largest US stocks, daily, 1972–2014 | About **90% of idiosyncratic shocks are permanent**. The temporary part has a **half-life of about 2.5 days**. No link to the VIX. | [S] — [Columbia draft](https://business.columbia.edu/sites/default/files-efs/pubfiles/11568/str1.pdf) |
| Cheng, Hameed, Subrahmanyam & Titman (2014 ABFER; JFQA 2017 [U]) | US | Reversal magnitudes are **lower after 2000**, as HFTs took over liquidity provision. | [S] — [ABFER PDF](https://www.abfer.org/media/abfer-events-2014/annual-conference/investment-finance/short-term-reversals-and-the-efficiency-of-liquidity-provision.pdf) |
| Post-decimalization large-cap study (2001–2016) | Large US stocks | The extreme-decile reversal earns **27 bp over 5 days**, tied to volatility and liquidity provision. | [S] — [Augsburg PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/94257/1-s2.0-S1062976921000922-main.pdf) |
| **Medhat & Schmeling (2022) RFS 35(3)** | US, 1963–2018 | Reversal exists only in **low-turnover** stocks. **High-turnover stocks show short-term *momentum*** that survives costs and is strongest in large, liquid stocks. | [A] — [City repository](https://openaccess.city.ac.uk/id/eprint/31278/) |
| Novy-Marx & Velikov (2016) RFS 29(1) | 23 anomalies [U] | Strategies with **over 50% monthly turnover rarely survive costs**. A buy/hold spread is the best mitigation. | [A] — [RePEc](https://ideas.repec.org/a/oup/rfinst/v29y2016i1p104-147..html) |
| Chen & Velikov (2023) JFQA | 204 anomalies | Net of effective spreads and post-publication decay, the average anomaly earns **4 bp/month**. These costs are a *lower bound* for market-order traders, since price impact is omitted. | [A] — [Cambridge](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/zeroing-in-on-the-expected-returns-of-anomalies/945133D5A3ECEEAF466AEE91551FD225) |

**Reading**
- Reversal is the slow, daily-to-weekly version of being paid for liquidity.
- It is strongest exactly where spreads are widest, so net returns are about zero in illiquid stocks.
- Net-positive versions exist in **large caps**, with **residual / non-fundamental** signals, **low turnover**, and **high-VIX** timing.
- The "high-turnover attention" names (low-float runners) show *momentum*, not reversal, at monthly horizons.

---

## 7. Illiquid and microcap specifics

**Tick size and the 2016–2018 Tick Size Pilot** (about 1,200 small caps, 5-cent tick)
- **Rindi & Werner (2019 WP)**
  - The quote rule widened **quoted spreads by 1.45¢ (17%)** and **effective spreads by 1.75¢ (46%)**, and raised **depth by 2,176 shares (275%)**.
  - Costs for retail-size liquidity-demanding orders rose **about 50%**, and **liquidity-provider profits rose about 40%**.
  - **Tick-constrained stocks:** costs more than doubled. **Unconstrained stocks:** costs fell by more than 10%.
  - [A] — [Bocconi PDF](https://didattica.unibocconi.it/mypage/upload/48636_20190131_054242_USTICKSIZEPILOT_20190125_COMPLETE.PDF)
- **SEC DERA staff (Hu et al., 2018):** wider spreads, higher volatility, lower price efficiency. Depth rose but large-order costs also rose. [S] — [SEC DERA](https://www.sec.gov/about/divisions-offices/division-economic-risk-analysis/staff-papers-analyses/dera_wp_tick_size-market_quality)
- **Gao, Lin & Liu (2022) QJF:** the trade-at rule *reduced* market-making profit, while the 5-cent quote rule "enriches market makers". [U: seen only in a search summary; source page not identified]
- **Albuquerque, Song & Yao (2020) JFE:** small-spread treated stocks lost **1.75–3.2%** of their value; higher transaction costs explain only a small part. [A] — [RUNI PDF](https://www.runi.ac.il/media/sseknk1u/the-price-effects-of-liquidity-shocks-a.pdf)
- **Chung, Lee & Rösch (2020) JFE 136(3):** small-order liquidity got worse, large-order liquidity got better (depth, multi-trade impact), price efficiency improved. [A] — [RePEc](https://ideas.repec.org/a/eee/jfinec/v136y2020i3p879-899.html)
- **Reading.**
  - A wide *tick* raises provider profit, but that profit is rationed by **queue position**. Speed decides who is at the front of the queue. [U: Yao-Ye 2018 RFS lead]
  - A retail order at the back of the queue fills mainly when the queue in front is swept, which is the adverse case.
- **2024 SEC rules (Rules 610/612)**
  - Access-fee cap cut to **$0.001/share** for quotes ≥ $1, and 0.1% of price below $1.
  - **$0.005 tick** for tick-constrained stocks ≥ $1.
  - [A] — [SEC press release 2024-137](https://sec.gov/newsroom/press-releases/2024-137)
  - Compliance was first extended to 2026-11-02 (SEC order of 2025-10-31). SIFMA's letter of 2026-05-04 asked for more time. [S] — [SIFMA](https://www.sifma.org/advocacy/letters/supplemental-request-for-immediate-extension-of-tick-size-and-access-fee-compliance-dates)
  - **On 2026-06-11 the SEC extended the relief for Rules 600(b)(89)(i)(F), 610(c) and 612 to the first business day of Nov 2027**, and proposed rescinding Rule 611. Canada's CSA and CIRO aligned on 2027-11-01. So the $0.003 cap and the 1-cent tick stay in force until then. [S] — [TradeInformer](https://tradeinformer.com/regulations/sec-extends-nms-relief-rule-611-repeal-2027); [findknowdo](https://www.findknowdo.com/node/660563); SEC order text not retrieved [U]
  - **Lower caps mean lower maker rebates, which compresses rebate capture (section 10e).**

**Odd lots**
- Bartlett, McCrary & O'Hara (2025) RFS 38(3): odd-lot practices create a large **"inside" market** where better prices than the NBBO routinely exist. These quotes are informative to traders with proprietary feeds. The round-lot redefinition reduces the effect but does not remove it.
- [A] — [RePEc](https://ideas.repec.org/a/oup/rfinst/v38y2025i3p661-711..html)
- **Consequence:** an NBBO-based backtest misstates both the true touch and queue priority.

**Opening and closing auctions**
- Bogousslavsky & Muravyev (2023) JFM 66: closing auctions were **7.5% of daily volume in 2018, up from 3.1% in 2010**. Closing prices usually match the pre-close bid or ask, and impact is lower than in continuous trading. [A] — [RePEc](https://ideas.repec.org/a/eee/finmar/v66y2023ics1386418123000502.html)
- The working paper adds that closing-price deviations from the mid **revert by half shortly after the close and fully overnight**, and that liquidity at the open has deteriorated. [A] WP
- **Consequences for backtests:**
  - Close-to-close returns contain a mechanical reversal.
  - Liquidity provision *at the close* is a known, competed institutional niche.

**Extended hours**
- Barclay & Hendershott (2004): spreads are 3–4× wider, driven by adverse selection (section 1). [A]
- Robinhood's 24-hour market routes overnight orders to **Blue Ocean ATS**, for a limited symbol list, limit orders only.
  - Robinhood discloses "lower liquidity, increased volatility, greater spreads".
  - BOATS suspended overnight trading in early Aug 2024.
  - [S] — [Robinhood newsroom](https://robinhood.com/us/en/newsroom/the-robinhood-24-hour-market-is-here); [Today in the Markets](https://todayinthemarkets.com/2024/08/06/robinhood-says-there-will-be-no-24-hour-trading-on-monday-due-to-issue-at-third-party-venue)
- **Reading:** a wide overnight spread is not free money. The same adverse-selection logic applies.

**OTC and pink sheets**
- Ang, Shtauber & Tetlock (2013) RFS 26(12): 6,668 OTC firms, 1977–2008.
  - The **illiquidity premium is several times larger than on listed markets**. The momentum premium is about 1/3.
  - Premiums are largest in retail-held, non-disclosing firms.
  - [A] — [RePEc](https://ideas.repec.org/a/oup/rfinst/v26y2013i12p2985-3028.html)
  - This premium is paid to *long-horizon holders*, not to round-trip scalpers.
- Eraker & Ready (2015) JFE: average OTC returns are negative, a lottery premium. [U]

**Small-cap spread levels**
- SEC staff (Collver, 2013 data): median quoted spreads of about **6–114¢ for firms under $100M** market cap, versus about **1–6¢ for $2–5bn** firms. [S] — [SEC PDF](https://www.sec.gov/marketstructure/research/small_cap_liquidity.pdf)

**Where the counterparties are**
- **Off-exchange volume** passed half of US volume in 2025: 50.6% of consolidated volume (Cboe). Retail wholesalers handle about 32–34% of total volume (MEMX, an interested party).
- [S] — [Cboe 2025 review](https://www.cboe.com/insights/posts/2025-u-s-equities-year-in-review); [MEMX](https://memx.com/insights/year-in-review-retail-driven-volume-surge)
- Wholesalers "cream-skim" uninformed retail market orders. Easley, Kiefer & O'Hara (1996) JF found a significant difference in the information content of purchased versus NYSE order flow. [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v51y1996i3p811-33.html)
- **Consequence:** a lit-exchange limit order mostly meets the *residual* flow that the wholesalers did not want, which is the more informed flow. [U: inference]

---

## 8. Capacity: market impact and what size a stock can carry

- **Square-root law** (Tóth, Lempérière, Deremble, de Lataillade, Kockelkoren & Bouchaud, 2011, PRX 1)
  - Δ(Q) = **Y·σ_daily·√(Q/V)**, with Y of order 1 and σ and V measured contemporaneously. Published exponents δ range from 0.4 to 0.7.
  - The mechanism is that liquidity vanishes near the current price.
  - [A] — [arXiv](https://www.arxiv.org/abs/1105.1694v3)
- **Almgren, Thum, Hauptmann & Li (2005) Risk**, Citigroup desk data
  - Temporary impact follows a **3/5 power** in trade rate, rejecting the square root. Coefficients depend on volatility, ADV and turnover.
  - [A] — [PDF](https://www.cis.upenn.edu/~mkearns/finread/costestim.pdf)
- **Frazzini, Israel & Moskowitz (2018 WP)**, AQR
  - **$1.7 trillion** of live executions, 21 developed markets, 1998–2016, about 10,000 stocks.
  - Real costs are **an order of magnitude smaller than earlier estimates**, rise with volatility and have declined over time.
  - This applies to *patient* institutional algorithms, not to aggressive scalping.
  - [A] — [SSRN](https://papers.ssrn.com/abstract=3229719)
- **Bucci, Benzaquen, Lillo & Bouchaud (2018)**, about 8M ANcerno metaorders
  - By the close, impact has decayed to **about 2/3 of its peak**.
  - The long-run level (about 50 days) is **about 1/2 of the end-of-day impact, or about 1/3 of peak**.
  - [A] — [arXiv](https://arxiv.org/pdf/1901.05332)
  - **Consequence:** most of your own buying pressure reverses, so self-made mark-to-market gains fade. See section 10c.
- **Participation-rate practice:** institutional desks typically cap participation at about **5–10% of volume** (up to 20–25% for urgent trades). [U: practitioner norm]

### Worked table (illustrative)

**Assumptions** [U]: daily vol and quoted spread typical of each ADV bucket; impact per side = Y·σ·√(Q/ADV) with Y = 0.5–1; a round trip pays the full spread plus two impacts (temporary impact paid in and out). Computed in scratch `capacity.py`.

| ADV | Assumed σ_daily | Assumed spread | Position at 1% ADV → impact/side | 5% ADV → impact/side | 10% ADV → impact/side | 25% ADV → impact/side | Round trip at 10% ADV |
|---|---|---|---|---|---|---|---|
| **$100k** | 7% | 3% | $1k → 0.35–0.70% | $5k → 0.8–1.6% | $10k → 1.1–2.2% | $25k → 1.8–3.5% | **5.2–7.4%** |
| **$1M** | 5% | 1% | $10k → 0.25–0.50% | $50k → 0.6–1.1% | $100k → 0.8–1.6% | $250k → 1.3–2.5% | **2.6–4.2%** |
| **$10M** | 3.5% | 0.25% | $100k → 0.18–0.35% | $500k → 0.4–0.8% | $1M → 0.6–1.1% | $2.5M → 0.9–1.8% | **1.4–2.5%** |
| **$100M** | 2.5% | 0.05% | $1M → 0.13–0.25% | $5M → 0.3–0.6% | $10M → 0.4–0.8% | $25M → 0.6–1.3% | **0.8–1.6%** |

**Passive market-making capacity.** Assume you take 10% of the stock's volume as a passive provider and keep 25% of the spread (a generous assumption at retail latency; section 1). Average inventory is about 1/4 of a day's trading. [U]

| ADV | $ traded/day | Gross spread income/day | Inventory | Daily P&L SD from inventory | Income / SD |
|---|---|---|---|---|---|
| $100k | $10k | **$38** | $2.5k | $175 | 0.21 |
| $1M | $100k | **$125** | $25k | $1,250 | 0.10 |
| $10M | $1M | **$312** | $250k | $8,750 | 0.04 |
| $100M | $10M | $625 (unattainable: HFT-competed) | $2.5M | $62,500 | 0.01 |

**Reading**
- The money an individual can make from bid-ask capture is capped by **other people's order flow**, not by his own capital.
- "Investing a large amount" in a thin stock moves the price by more than the spread (top table).
- Even with generous retention assumptions, passive capture is **tens to hundreds of dollars a day per stock**, against a daily inventory-risk SD about 5–30× larger (4.6×, 10× and 28× in the three attainable rows; recomputed with `capacity.py`).
- Diversifying across, say, 20 thin names helps the Sharpe ratio. But it needs automation at a latency Robinhood's approval flow does not allow.
- The retention parameter (25%) is the crux, and it is exactly what our tests must measure (H1 below).
- **Caveat:** the square-root law is fitted to institutional metaorders of about 1e-4 to 1e-1 of ADV. In the thinnest names a single order may simply walk a thin book. [U]

---

## 9. ETF and crypto liquidity provision

**ETFs**
- **Petajisto (2017) FAJ 73(1)**
  - ETF prices deviate from NAV within a band of **about 200 bp**, or **about 100 bp** after a peer-group control. Deviations are larger for international and illiquid holdings.
  - Trading strategies earn "substantial abnormal returns **before transaction costs**".
  - [A] — [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/2017/inefficiencies-in-the-pricing-of-exchange-traded-funds)
- **Spreads and volume:** ETF spreads are log-linear in volume, so the gap is large between low- and average-volume funds. [S] — [FPA Journal](https://www.financialplanningassociation.org/article/journal/MAY11-volume-and-assets-determinants-etf-bid-ask-spreads)
- **Lead market makers:** in 2013 Knight was lead market maker on 418 NYSE Arca ETFs, 150 of them low-volume (under 50k shares a day).
  - Thin ETFs depend on one or two lead market makers, and their spreads can widen up to 10× in an outage (the 10× figure is from a TD report seen only in a search summary [U]).
  - [S] — [Institutional Investor](https://institutionalinvestor.com/article/2bsvp289act98umuz8a2o/portfolio/how-the-etf-market-quickly-got-over-its-knightmare)
- **Single-AP funds:** the Ontario Securities Commission counted 71 ETFs with a single authorized participant in Dec 2023. [S] — [Investment Executive](https://www.investmentexecutive.com/from-the-regulators/regulators-eye-market-makers-role-in-etf-trading/)
- **Reading**
  - The competitive edge in thin ETFs is creation and redemption against the basket, which needs authorized-participant status and a hedge.
  - A retail trader can only *trade against* the lead market maker's quotes. The repeatable retail use is **execution discipline**: limit orders near the indicative NAV, avoiding the open and close and stale-NAV international funds.
  - This matters for the repo's small spot-SOL ETFs. [S: repo `AGENTIC_TRADING_PLAN.md`]

**Crypto**
- **Makarov & Schoar (2020) JFE 135(2):** 34 exchanges in 19 countries. Large, recurrent arbitrage gaps, much wider **across countries** than within one country (capital controls), opening up in rallies. The common volume component explains 80% of BTC returns. [A] — [LSE](https://eprints.lse.ac.uk/100409)
- **Dyhrberg, Foley & Svec (2018) Econ. Letters 171:** BTC quoted and effective spreads on three US exchanges are **below major equity exchanges**; BTC is "highly investible for retail size". Mostly non-algorithmic retail flow. [A] — [RePEc](https://ideas.repec.org/a/eee/ecolet/v171y2018icp140-143.html)
- **Albers et al. (2025):** maker fills are adversely selected; naive maker strategies are highly unprofitable (section 4). [A]
- **"Fragmentation, price formation and cross-impact in Bitcoin markets"** (arXiv 2108.09750): a **2.5 bp maker rebate** on Bybit's BTC perpetual (the largest of 14 markets) is what makes lagging-venue maker strategies interesting. [S] — [arXiv](https://arxiv.org/pdf/2108.09750)
- **Fee tiers a US retail account actually faces:**
  - Coinbase Advanced: **0.50% maker / 0.90% taker** at the US entry tier since 2026-09-16 (tiers now start at $10k; spot and derivatives volume combined). The older 0.40% / 0.60% entry rate is stale or belongs to the Coinbase Exchange schedule. [S] — [PrimeXBT](https://primexbt.com/news/coinbase-cuts-advanced-platform-trading-fees-and-lowers-volume-threshold/); [CryptoDaily](https://cryptodaily.co.uk/2026/09/coinbase-advanced-fees-usdc-vip-tiers) (via `crypto_data_feasibility.md`)
  - Kraken Pro: 0.40% / 0.80% base since 2026-07-09 (previously 0.25% / 0.40%). [S] — [Kraken blog](https://blog.kraken.com/product/pro/new-kraken-pro-fee-tiers); [Kraken fee page (not fetched)](https://support.kraken.com/articles/201893638-fee-schedule)
  - Binance.US: **0% maker / 0.02% taker on all Advanced spot pairs since 2026-04-22**, with no volume tiers (the old VIP0 0.10% / 0.10% is stale). [S] — [Binance.US blog](https://blog.binance.us/zero-fee-trading/) (via `crypto_data_feasibility.md`, which tags it [A])
  - Robinhood Crypto, **exchange routing** (Legend): **0.50% maker / 0.95% taker under $10k of 30-day volume**, 0.075% / 0.15% at $250k–500k, down to 0% / 0.03% at $25M+. Default market-maker routing has no fee tiers; Robinhood receives $0.95 per $100 from its market maker (as of 2026-06-15), about 0.95% per side. Which route agent orders use is unknown. [S] — repo `AGENTIC_TRADING_PLAN.md` §1; Robinhood fee-schedule PDF seen only in search summaries [U]
- **Reading.** BTC's touch spread on major venues is under 1 bp (repo Binance pilot, BTCUSDT 2026-10-10 to 10-16: median trade-implied quoted spread ≈ 0.06 bp [S: `data/scalping/binance_pilot/results/spot_pilot.csv`]); "about one tick" is [U]. **At retail maker fees of 10–50 bp per side (Binance.com VIP0 to Robinhood/Coinbase entry) the fee is 10–500× the spread.** Crypto market making only pencils out at VIP or market-maker tiers (hundreds of millions of dollars a month), with rebates, or on a zero-maker-fee venue such as Binance.US, where adverse selection rather than fees decides the result.

---

## 10. What the friend may actually be doing

Each reading below gives the evidence first, then an assessment.

### (a) Passive market making in thin names

**For:**
- Handa-Schwartz (a network of limit orders was profitable on the 1990s NYSE).
- Kelley-Tetlock (retail passive buyers profit from reversals, monthly horizon).
- Seasholes-Wu (selling to attention buyers).
- Tick Size Pilot: a wide tick raised provider profits 40%.

**Against:**
- Harris-Hasbrouck: unconditional liquidity offering is not profitable.
- Linnainmaa, BHR, Albers et al.: passive fills are adversely selected.
- Conrad-Wahal: impact completes in about 60 s in small caps; net provision is about 1–2 bp even at 100 ms.
- Wholesalers skim uninformed flow, so the lit residual is more informed.
- Capacity is tiny (section 8).

**Assessment:**
- Plausible only at **small size**, in names HFTs ignore, with discipline: two-sided quotes, inventory limits, skewing.
- Not a "large amount" strategy.
- On Robinhood: no rebates, and agentic approvals make it impractical.
- Probability that this is the main source of his profits: **low to moderate**.

### (b) Momentum or "tape-reading" scalping in low-float names

**For:**
- Medhat-Schmeling: high-turnover stocks show short-term momentum.
- Attention-driven buying is predictable (BHOS 2022; Seasholes-Wu).
- A practitioner opening-range-breakout study on "stocks in play" (Zarattini, Barbon & Aziz) claims a Sharpe of 2.81 for 2016–2023 (top 20 stocks by opening relative volume). [S] — [Let's Data Science summary](https://www.letsdatascience.com/news/traders-adopt-orb-strategy-for-stocks-in-play-19394da2). Its cost assumptions were not checked. [U]

**Against:**
- The *earlier* Zarattini & Aziz (2023) ORB paper on QQQ ("Can Day Trading Really Be Profitable?", SSRN 4416622) charges commission but no spread or slippage. An independent replication of that index rule on index CFDs found the gross edge reproduces but the net is about 0, with 4 of 5 markets negative. Neither critique was tested on the stocks-in-play study. [S] — [Concretum](https://concretumgroup.com/can-day-trading-really-be-profitable/); [replication blog](https://www.mql5.com/en/blogs/post/776235)
- Robinhood herds earn −4.7% over 20 days.
- Large gaps in small caps tend to revert. [S/U]
- Under 1% of day traders are predictably profitable.

**Assessment:**
- The **most likely description** of what retail "low-volume scalpers" actually do.
- Profitable for a minority, regime-dependent, and highly sensitive to fills and slippage. Testable only with intraday data.

### (c) Self-inflicted impact: big buying in a thin stock

**Mechanics:**
- Buying 25% of ADV in a $1M-ADV, 5%-vol stock pushes the price up about **1.3–2.5%** (square-root law, section 8). That shows as a paper gain marked at the last trade.
- Impact decays to about 2/3 of peak by the close and about 1/3 in the long run (Bucci et al.).
- On exit he pays the impact again on the way down. The **round trip loses roughly the spread plus two temporary impacts**, about 3.5–6% in this example.

**Where it becomes illegal:**
- Exchange Act **§9(a)(2)** prohibits "a series of transactions... creating actual or apparent active trading... or raising or depressing the price... for the purpose of inducing the purchase or sale" by others. [S] — [SEC opinion quoting §9(a)(2)](https://www.sec.gov/files/litigation/opinions/3440726.txt); statute at 15 U.S.C. §78i(a)(2) [U: not retrieved]
- §9(a)(1) covers wash sales and matched orders. **Spoofing and layering** (large bids placed to lure sellers or buyers, then cancelled) is separately prohibited (Dodd-Frank §747 for futures; SEC and FINRA rules for equities). [U]
- Aggarwal & Wu (2006) J. Business 79(4): in SEC manipulation cases, prices **rise during the manipulation and fall afterwards**. Manipulation raises volatility, liquidity and returns. Manipulators are often insiders or brokers. [A] — [author PDF](https://www.bauer.uh.edu/wu/Papers/JOB2006_StockManipu.pdf)
- Most such cases are in illiquid OTC names. [U]
- Buying big *with no intent to induce others* is not manipulation. But pushing a thin stock up and then selling into the buyers it attracts is the classic pattern.

**Assessment:** a **likely contributor** to *reported* gains if he marks to market. It is the most important thing to rule out in his own P&L.

### (d) Survivorship and bull-market luck

**Evidence:**
- Jordan-Diltz: profitability tracks the Nasdaq.
- Garvey-Murphy: about 50% profitable over a 3-month window in 2000.
- Barber et al.: over 75% quit within two years, so the people still trading, and talking about it, are the survivors.
- Chague: daily SD of $2,560 against a mean of $310 for the *best* trader. Months of profits are statistically consistent with zero skill.

**Assessment:** **high prior.**
- Ask for at least 12 months of realized (closed) P&L including down markets, net of all costs, against the S&P.
- Without that, the base rate (≥ 97% lose; < 1% skilled) dominates.

### (e) Rebate capture

**Mechanics:**
- Exchanges pay adders of liquidity a rebate under the current $0.003 access-fee cap: about $0.0013–0.0020/share at base or pass-through rates and $0.0027–0.0028 at Cboe BZX's top member tiers. [S: repo `practicalities_us.md` §2] Higher tier levels are [U].
- On a $2 stock that is up to about 15 bp, large relative to a one-tick spread. This was the classic 2000s "rebate trader" business.

**Against:**
- Retail brokers keep or redirect rebates and PFOF. Robinhood's 606 reports show non-marketable limit orders were **about 34.6% of non-directed S&P 500 orders in Jan 2026** (RHF, in the Q1 2026 report; 33.4% in the Q2 2026 report), routed to venues that pay Robinhood. [S] — [FINRA-hosted 606 report](https://cdn.finra.org/606/2026/165998_606_NMS_2026_Q1_V1.pdf)
- Rebate-maximizing routing worsens fills (Battalio-Corwin-Jennings).
- The 2024 Rule 610 cut to $0.001 (compliance deferred to the first business day of Nov 2027 [S]; section 7) will shrink rebates about 2–3×.

**Assessment:** possible only with **direct market access and a top volume tier**. **Not available on Robinhood.** Unlikely for a retail friend.

**Overall ranking of explanations:** (b) momentum/attention ≈ (d) luck/survivorship > (c) self-inflicted marks > (a) genuine small-scale passive market making > (e) rebates.

---

## Implications for our tests

### Testable predictions (to pre-register)

| ID | Prediction (falsifiable) | Data | Pass / fail line |
|---|---|---|---|
| **H1: markouts** | A simulated passive fill (maker side) has an average **realized spread that declines with horizon (1 s > 5 s > 60 s > 300 s)**. Net of retail maker fees (0.10–0.50%) it is **negative** at every horizon on BTC, ETH and SOL, and positive only gross at ≤ 1 s. (Binance.US charges 0% maker since 2026-04-22, so a zero-fee case must be reported separately; there only adverse selection counts.) | Binance spot `aggTrades` (has the buyer-is-maker flag) via the S3 path-style listing. Tested reachable this session: `data/spot/daily/aggTrades/BTCUSDT/` | Reject "bid-ask capture works for us" if the net 60 s markout < 0 with 95% CI excluding 0 |
| **H2: OHLC fill fallacy** | A naive daily-bar rule ("limit buy at X% below open fills if low ≤ limit; sell at close or at limit if high ≥ target") shows large spurious profits. Requiring the price to **trade through by ≥ 1 tick**, filling **only on the next bar**, and assuming the worst intrabar order (high/low sequence unknown) removes most of them. | `data/universe_pit_all/` (S&P 500 PIT daily OHLC) | The gap between naive and conservative fill results is the "fill illusion". Report it, never the naive number |
| **H3: reversal net of costs** | 1-day and 5-day reversal: **gross return rises monotonically from liquid to illiquid quintiles** (Amihud or $ADV). Net of an estimated half-spread each way (Abdi-Ranaldo or Corwin-Schultz from OHLC), it is **≤ 0 in the illiquid quintiles**. A positive net exists only in the most liquid quintile and in **high-VIX** months (Nagel). Residual reversal beats raw reversal (Blitz et al.; Da et al.). | PIT daily OHLC; `data/macro/` VIX | Net Sharpe > 0.5 after costs in the out-of-sample half, with Holm correction across variants |
| **H4: impact round trip** | Simulating the accumulation of q% of ADV (q = 1, 5, 10, 25) over 1 day and exit after N days: the **mark-to-market gain at the end of accumulation ≈ Y·σ·√q, and the realized round trip is ≈ −(spread + 2·temporary impact)**. | Model plus PIT daily data; Y calibrated to 0.5–1 | Shows how "paper gains" arise. Not a strategy |
| **H5: spread vs volatility** | Across stocks, the quoted (or estimated) spread scales with **volatility per trade** (Wyart et al.). The residual "cheap spread vs vol" names do not earn more than others in H3. | OHLC-estimated spreads; Robinhood `get_equity_quotes` live snapshots (read-only) to calibrate | Slope ≈ 1 in logs; no residual alpha |
| **H6: low-float momentum regime test** | If intraday bars for small caps can be obtained: opening-range or gap-continuation trades in high relative-volume small caps are **positive gross in 2020–21 and ≤ 0 net in other years** (Jordan-Diltz bull dependence). | **Blocker:** no small-cap intraday or PIT microcap universe in the repo or reachable hosts | Defer until data exist |

### Pitfalls a backtest must avoid

- **Bid-ask bounce**
  - Close-to-close returns of illiquid stocks contain spurious negative autocorrelation, which inflates reversal profits and biases compounded returns upward. Blume-Stambaugh (1983) and Roll (1984) [U: abstracts not retrieved].
  - Fixes: use midquotes where available; skip a day between signal and entry; estimate spreads with Abdi-Ranaldo (2017, RFS 30(12): "most accurate for less liquid stocks") or Corwin-Schultz (2012, JF 67(2)). [A] — [Corwin-Schultz abstract](https://academicnewsletter.sufe.edu.cn/info/360309); [Abdi-Ranaldo R package docs](https://search.r-project.org/CRAN/packages/bidask/bidask.pdf)
- **Fill assumptions**
  - Touching your limit price is not a fill. Queue position matters, and in wide-tick stocks you are at the back.
  - Fills are adversely selected (Linnainmaa; Albers et al.): assume you fill when the price moves through you and miss when it moves away.
  - Allow for partial fills and size caps (≤ 1–5% of the bar's volume).
- **Look-ahead in daily OHLC**
  - Do not use the same bar's high or low to fill and the same bar's close to signal.
  - The order of high and low within the bar is unknown, so take the worst case.
  - Split adjustment must use `adjustment_type='split'`, never `'none'`. [S: repo `AGENTIC_TRADING_PLAN.md` §2]
- **Survivorship and delisting**
  - Use point-in-time membership (the repo's PIT set).
  - Include delisting returns. Shumway (1997, JF 52(1)): correct delisting returns are missing for most negative delistings, so small-cap returns are overstated. [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v52y1997i1p327-40.html)
  - Shumway-Warther (1999, JF): a −55% fill-in return removes the Nasdaq size effect. [U: abstract wording seen only in a search summary]
  - **Our PIT set is S&P 500 only, the opposite of the friend's universe.** Any small-cap conclusion needs a different dataset (currently a blocker).
- **Costs a retail Robinhood account actually pays**
  - $0 commission plus small sell-side fees: SEC Section 31 at $20.60 per $1M of sales from 2026-04-04 (0.206 bp; not passed on for sales ≤ $500), and FINRA TAF at $0.000195/share (max $9.79), paused for trades 2026-10-01 to 2026-12-31. [S: repo `practicalities_us.md` §3, which cites the SEC fee advisory and FINRA filings]
  - Crossing the spread on marketable orders: 0.07–0.46% round trip across brokers (Schwarz et al.).
  - No rebates.
  - Crypto: 0.50% maker / 0.95% taker on Robinhood's exchange route at the entry tier; about 0.95% per side on the default market-maker route.
- **Operational limits**
  - Agentic orders need a preview and explicit user confirmation (Robinhood's tool rules); in-app approvals are optional but this repo keeps them on. Measured read calls took about 8 s each, so an order takes seconds to minutes. [S: repo plan; `practicalities_us.md` §9]
  - Fractional and dollar orders are market-only. Extended hours accept limit orders only.
  - Cash or limited-margin account with T+1: free-riding and good-faith limits on reusing unsettled proceeds. [U: applicability to the agentic account]
  - The PDT rule was removed on 2026-06-04. [S: repo plan]
  - Wash-sale rules across all accounts; gains are short-term.
- **Multiple testing**
  - Pre-register the variants (H1–H5 and parameter grids).
  - Report every variant, apply Holm/Bonferroni, and keep an untouched out-of-sample period.
  - Report the naive-fill result only as the "illusion" baseline.

### Gaps and leads to check in full text

- Conrad & Wahal (2020): realized-spread share by **size decile** at 5 s, 1 min and 5 min. This is the single most useful table for H1 priors.
- Barber et al. (2014): whether the top day traders use passive or aggressive orders.
- Final Rule 605 text: horizons, definitions and the current compliance date. The SEC's 2026-06-11 order deferring Rules 610(c)/612 to Nov 2027 (seen only through secondary sources).
- A US 2020–2026 account-level day-trader P&L study: none found.
- A small-cap intraday data source reachable from this sandbox: none found. LOBSTER, TAQ and Yahoo are blocked.
