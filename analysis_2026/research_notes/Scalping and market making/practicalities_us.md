# Scalping and Passive Market-Making in Low-Volume US Stocks: Practical, Legal and Cost Constraints for a US Individual (as of Oct 2026)

> **How this was verified.**
> - **Fetching was blocked.** curl and WebFetch could not reach sec.gov, finra.org, robinhood.com, interactivebrokers.com, cboe.com, nasdaqtrader.com, irs.gov, luldplan.com, catnmsplan.com or law-firm sites (DNS failure or proxy 000). Every web finding below comes from search-engine retrieval of page text. No full documents were read.
> - **[A]:** the text was returned from the primary source's own page or filing (SEC/FINRA/CAT/LULD-plan documents, exchange filings, broker fee pages, court opinions), as retrieved this session.
> - **[S]:** secondary source only (law-firm alert, broker blog, trade press, review site).
> - **[U]:** from memory, unverified, or conflicting. Treat it as a lead.
> - **Two items are first-hand, from this session:**
>   - the Robinhood MCP tool descriptions, loaded from the connector's own schemas
>   - two timed read-only Robinhood MCP calls (SPY/IWM quote and price book; no account data was read or stored)
> - **Cited to the repo, not re-verified:** facts reused from `AGENTIC_TRADING_PLAN.md` are cited as **[plan]**.
> - **Date.** Fee rates change often. Every rate below carries its effective date. Re-check them before the backtest is frozen.
> - **No personal data.** This note contains no account numbers, balances, positions or order logs.
>
> Fact-check (date 2026-10-17): 72 claims checked, 16 corrections
> - **How the fact-check was done:** a second agent reran `scratchpad/practicalities/costs.py` (the section 10 table reproduces exactly), redid the threshold and capacity arithmetic, and re-read the Robinhood MCP schemas (order types, 4-symbol book cap, approval text).
> - **Confirmed by web search this session:** Section 31 at $20.60/$M from 2026-04-04; TAF at $0.000195 (cap $9.79) from 2026-01-01; the TAF pause for 2026-10-01 to 12-31 (filing text); CAT Fee 2026-1 at $0.000001; Historical CAT Assessment 1A at $0.000002.
> - **Not re-checked:** primary hosts were still unreachable, and the search budget ran out after five queries. Every other tag is the original author's, except where marked "fact-check".

---

## 0. Bottom line (one screen)

- **"Buy at the bid, sell at the ask" is legal.** Capital does not buy an edge. It buys more problems: queue visibility, exit liquidity, ownership-filing thresholds and attention from market surveillance.
- **At Robinhood you do not control queue priority.**
  - All equity orders are non-directed and go to wholesalers that pay for order flow. Non-marketable limit orders are about **33–35%** (range 32.6–35.1%) of Robinhood's non-directed S&P 500 orders [A].
  - There are no rebates, and you cannot post-only or choose a venue.
  - Explicit cost is almost nil: about **0.2 bp** (SEC fee) plus **$0.000195/share** (TAF, paused Oct–Dec 2026) on sells.
  - The real costs are fill quality and adverse selection, which no fee table shows.
- **At IBKR Pro tiered you control routing and earn maker rebates**, but you pay commission:
  - **Passive round trip ≈ $0.0045/share** at $2–$10, which is 45% of a one-cent tick. It is about $0.0055 at $50, because the SEC fee scales with price. That is 22 bp at $2, 4.6 bp at $10 and 1.1 bp at $50.
  - **Taker round trip ≈ $0.0137/share**, more than one full tick.
  - So spread capture only works passively. It needs fills on both sides at a full tick, minus adverse selection.
- **A retail "market maker" holds long-only inventory.**
  - The Robinhood Agentic account allows no shorting and no leverage [plan].
  - Elsewhere, shorting small caps needs locates, which are often unavailable or expensive.
  - So you can only sell what you already bought, and you carry the downside of every fill.
- **Large capital collides with ownership rules in small caps:**
  - A **$1M** position is 5% of a **$20M** company and 10% of a **$10M** one.
  - **$5M** reaches the same thresholds at **$100M / $50M**.
  - Above 10%, **Section 16(b) disgorges short-swing profits**. That rules out scalping at that size, mechanically.
- **The legal line is intent and pattern, not size.**
  - Large *bona fide* bids are legal.
  - Large bids that are cancelled after your ask fills are the exact fact pattern in recent SEC/DOJ spoofing cases against individual day traders in *thinly traded* stocks: Xie 2021, $1.86M disgorged; Wang 2026, 150+ ADRs [A].
- **Claude plus the Robinhood MCP is far too slow for market-making.** A read cycle took about **8 s** in this session, and each order needs in-app approval. It can serve end-of-day or slower decisions only. Seconds-scale quoting needs a local bot on a broker API (IBKR, Lightspeed, Alpaca Elite).

---

## 1. Order routing and queue priority — who fills a retail limit order at the bid?

### 1.1 Robinhood

| Item | Finding | Tag / source |
|---|---|---|
| Routing model | Robinhood "generally routes stock, ETF, and options orders to market makers rather than public exchanges". The market makers pay Robinhood. A routing algorithm picks one based on historical performance. | [A] [RH support: Stock, ETF, and options order routing](https://robinhood.com/us/en/support/articles/stock-order-routing) |
| Directed orders | None. In the 606 summary rows, non-directed orders are **100.00%** of all orders (e.g. RHF Q1 2025: "100.00 30.78 28.10 32.62 8.50"). There is no customer venue choice for equities. | [A] [FINRA-hosted RH 606 reports](https://cdn.finra.org/606/2025/165998_606_NMS_2025_Q4_V1.pdf) |
| Share of non-marketable limit orders (NMLOs) | S&P 500 non-directed orders that are NMLOs: RHF Q1 2025 **32.6%**; RHS Jul 2025 **35.1%**; RHS Oct 2025 **33.2%**; RHF Jan 2026 **34.6%**; RHF Q2 2026 **33.4%**. | [A] [RH 606, 2025-26](https://cdn.finra.org/606/2026/165998_606_NMS_2026_Q2_V1.pdf) |
| Who receives NMLOs | Virtu, Citadel Securities, Jane Street, G1 (Susquehanna), Hudson River Trading and Two Sigma appear as NMLO venues. They **pay Robinhood for resting limit orders too**. | [A] venues; [U] payment sizes |
| NMLO payment size | Conflicting. The FINRA-PDF snippets read as about 71–185 ¢ per 100 shares (RHS, Apr 2026; table category unclear). A third-party aggregator shows about 9.8–14.4 ¢ per 100 shares for June 2026. Unresolved. | [U] [ChartRow](https://chartrow.com/brokers/robinhood) |
| PFOF split | RHS passes 80% of PFOF revenue to RHF. | [A] 606 disclosure |
| Overnight (8 pm–4 am ET) | Limit orders go to a single "24H Market Maker", which may fill as principal or route to one ATS. The ATS "is not required to display prices publicly and may have very limited liquidity". Fills "may not be price protected". | [A] [RH extended-hours disclosure (Singapore-entity copy describing RHS routing)](https://cdn.robinhood.com/assets/robinhood/legal/rhsg_extended_hours_trading_disclosure.pdf); [A] [RH extended-hours (US)](https://robinhood.com/us/en/support/articles/360001226766/extendedhours-trading/) |
| Unfilled limits | "If there are no shares currently available at your limit price, your trade may not execute — even if your limit price is the same as the price displayed." | [A] [RH: Why hasn't my order been filled?](https://robinhood.com/us/en/support/articles/why-hasnt-my-order-been-filled) |
| Robinhood Legend | No evidence of venue selection for equities was found. The Legend support pages cover order defaults (limit/market, GFD). Exchange routing on Legend exists only for **crypto** ("smart exchange routing"). The fee is disputed: this note had 0.10%, while `AGENTIC_TRADING_PLAN.md` gives 0.95% taker / 0.50% maker below $10k of 30-day volume. | [A] [Legend settings](https://robinhood.com/us/en/support/articles/legend-behaviors-and-settings); [A] [RH crypto routing](https://robinhood.com/support/articles/360022216832/crypto-order-routing); [U] crypto fee level (fact-check: conflicts with [plan]) |
| Order types (agentic MCP) | Market, limit, stop-market, stop-limit; GFD/GTC. **No IOC, post-only, pegged, hidden or reserve.** Extended and overnight sessions take limit orders only. | [A] MCP `place_equity_order` schema (loaded this session); [plan] |

**What happens to a Robinhood limit order at the bid [U, inferred from the rules below; not documented by Robinhood]:**
- **The wholesaler holds it.** Under **FINRA Rule 5320** it may not trade for its own account at a price that would satisfy your order without filling yours. [A] [FINRA 5320](https://www.finra.org/rules-guidance/rulebooks/finra-rules/5320)
- **Rule 604 may force display.** A wholesaler that is an OTC market maker must "publish immediately" a quote reflecting customer limit orders that *improve* its bid or offer, or that add more than a de minimis size at its bid or offer. [A] [17 CFR 242.604](https://www.law.cornell.edu/cfr/text/17/242.604)
  - Exceptions (FINRA Rule 6460): odd lots, block-size orders unless the customer asks for display, orders the customer asks not to display, and orders sent immediately to an exchange or ECN. [A] [FINRA RN 10-42](https://www.finra.org/rules-guidance/notices/10-42)
  - "Block size" is the lesser of 10,000 shares or $200,000. [S] [Nasdaq article](https://www.nasdaq.com/articles/would-605-work-better-in-dollars-2021-09-16)
  - "Immediately" is read as about ≤30 s. [S] [CertFuel](https://www.certfuel.com/series-57/videos/final-review/handling-customer-orders/regulation-nms/)
  - **So a large retail bid (≥10,000 shares or ≥$200k) may never be displayed at all.**
- **Displayed orders take time priority only from arrival.** If displayed, the order is typically re-posted to an exchange under the wholesaler's identity. It joins that exchange's price-time queue at the back, from the moment it arrives there.
  - Robinhood customers never receive the maker rebate.
  - The wholesaler can also fill the order from inventory when a marketable sell arrives, often from other retail flow.
- **Who fills you, in practice:**
  - an incoming marketable sell, whether retail flow internalized by the wholesaler or a taker on the exchange (an institutional algorithm or HFT), or
  - the wholesaler itself, once the market moves to or through your price.
- **Fills are adversely selected.** Limit orders are "price-contingent and suffer from adverse selection". In all-Finnish-investor data this mechanically produces apparent biases and poor performance. [A] [Linnainmaa 2010, JF 65(4)](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1473-1506.html)

### 1.2 Interactive Brokers (IBKR Pro, tiered)

| Item | Finding | Tag / source |
|---|---|---|
| Commission | **$0.0035/share** for ≤300,000 shares/month; then $0.0020 (≤3M), $0.0015 (≤20M), $0.0010 (≤100M), $0.0005 (>100M). Marginal tiers. Min **$0.35**/order; max **1% of trade value**. | [A] [IBKR commissions — stocks](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php) |
| Third-party fees passed through | Exchange fees/rebates; NSCC/DTC clearing **$0.00020/share**; NYSE pass-through = commission × 0.000175; FINRA pass-through = commission × 0.000565 (UK page: 0.000563). | [A] same page |
| Fixed alternative | $0.005/share, min $1, max 1%. All exchange fees included and **no rebates**. | [A] same page |
| Exchange pass-through examples (≥$1) | **ARCA:** remove **$0.0030**, add **($0.0020)** rebate (AMEX-listed add $0.0016). **NASDAQ/INET:** remove $0.0030, add **($0.0013)** on UK/AU/SG pages vs **($0.0021)** on CA/JP pages (conflict). **Sub-$1:** remove 0.30% of value, **no add rebate**. | [A] [IBKR ARCA fees](https://www.interactivebrokers.com.au/en/accounts/fees/ARCAstkfee.php); [A] [IBKR INET fees](https://www.interactivebrokers.co.uk/en/accounts/fees/INETstkfee.php) |
| Routing | **SMART** (default) or **directed** to a chosen exchange, through TWS or the API. You set the venue, and so the queue you join and the fee/rebate you get. | [U] standard IBKR functionality; directed fees not verified |
| IBKR ATS | Non-marketable, liquidity-adding orders only, in US stocks > $1.00. They rest and match against other IBKR clients' SmartRouted orders, then reroute to SMART after a user-set time. **"No maker/taker fees or credits"** on directed ATS orders. | [A] [IBKR ATS](https://www.interactivebrokers.com/en/trading/clients-ibkr-ats.php) |
| Order-efficiency policing | OER = (submits + revisions + cancels) / (executions + 1), measured daily. **>20 is "excessive"**; persistent or egregious ratios can lead to trade restrictions. | [A] [IBKR Order Efficiency Ratio](https://www.interactivebrokers.com/docs/general/order-types/notes-limitations/order-efficiency-ratio) |
| IBKR Lite | Commission-free with PFOF-style routing; no directed routing. | [U] |

### 1.3 Alpaca and specialist day-trading brokers

| Broker | Routing / pricing | Tag / source |
|---|---|---|
| Alpaca (standard) | Commission-free; orders go to market makers (PFOF). Trading API limit **200 requests/min per account**, one call per order (a paid data plan raises only the *market-data* limit). | [U] routing; [S] [Alpaca forum, staff answer](https://forum.alpaca.markets/t/trading-api-limitations/9743) |
| Alpaca Elite Smart Router | **$30,000 minimum** deposit. **All-In $0.0040/share** (fees and rebates included, regulatory fees extra), or **Cost Plus $0.0025/share** or less with exchange fees and rebates passed through. DMA Gateway (DASH) to chosen venues. A forum post cites a "0%–3%" DMA fee line (unresolved). | [A] [alpaca.markets/elite](https://alpaca.markets/elite); [A] [Alpaca DMA changelog](https://docs.alpaca.markets/changelog/direct-market-access-gateway-and-advanced-order-types-for-elite-smart-router); [S] forum |
| Lightspeed | $0.0035 → $0.0010/share by monthly volume (accounts opened after 2024-03-01); $0.25 min under 250k shares/month. "Ability to capture routing rebates". DAS Trader about $150/month all-in ($125 platform fee waived at 100k shares/month). | [S] [daytradingz review](https://daytradingz.com/lightspeed-trading-review/); [A/S] [Lightspeed Premier](https://lightspeed.com/lightspeed-premier) |
| Cobra | About $0.002/share (<1M shares/month), $0.0015 above. Affiliate-promoted figure. | [S] [daytradingz](https://daytradingz.com/best-direct-access-broker) |
| TradeZero | No fee data retrieved. ZeroPro platform with ECN routes and pass-through ECN fees and rebates. | [U] |
| DAS / Sterling platforms | About $100–150/month plus Level 2 data fees; route choice per order (e.g. ARCA, EDGX, BATS, NSDQ) through the clearing broker. | [S] [stockbrokers.com](https://www.stockbrokers.com/guides/das-trader-pro); [U] details |

**Answer to "who fills a retail limit order at the bid":**
- At Robinhood, Alpaca standard and IBKR Lite, the first counterparty is a **wholesaler**. It decides whether, where and when your order is displayed.
- At IBKR Pro, Alpaca Elite or a direct-access broker, your order sits **in an exchange queue you chose**, behind all displayed size already at that price.
- Either way, it fills when a **taker** decides your price is worth hitting. In thin names that is disproportionately just before the price moves through you (adverse selection [A, Linnainmaa]).

---

## 2. Exchange fees, rebates and the 2024 Rule 610/612 amendments

### 2.1 Typical lit-venue fees, NMS stocks ≥ $1.00 (standard, non-tier rates)

| Venue | Model | Add (maker) | Remove (taker) | Sub-$1 | Tag / source |
|---|---|---|---|---|---|
| Cboe BZX | maker-taker | **($0.00160)** rebate | **$0.0030** | remove 0.30% of value | [A] [SR-CboeBZX-2026-084](https://cdn.cboe.com/resources/regulation/rule_filings/approved/2026/SR-CboeBZX-2026-084.pdf) |
| Cboe EDGX | maker-taker | **($0.00160)** | **$0.0030** | add ($0.00003); remove 0.30% | [A] [SR-CboeEDGX-2026-017](https://cdn.cboe.com/resources/regulation/rule_filings/approved/2026/SR-CboeEDGX-2026-017.pdf) |
| Cboe BYX | inverted | **$0.00200 fee** | **($0.00020)** rebate | add free; remove 0.10% | [A] [BYX fee schedule](https://cboe.com/us/equities/membership/fee_schedule/byx/); a late-2025 FR notice shows a ($0.00200) remove rebate (conflict) |
| Cboe EDGA | maker-taker since 2024-11-01 (was inverted) | — | fee | — | [U] (fact-check: the link sits in the EDGX, not EDGA, filing folder, so it may not be the EDGA filing) [SEC 34-101669](https://www.sec.gov/files/rules/sro/cboeedgx/2024/34-101669.pdf) |
| Nasdaq (INET) | maker-taker | about $0.0018–$0.00305 by tier (2024 filing); IBKR pass-through ($0.0013) or ($0.0021) | up to **$0.0030** | — | [A] [SEC 34-100257 (IEX filing citing Nasdaq Equity 7 §118)](https://www.sec.gov/files/rules/sro/iex/2024/34-100257.pdf); [A] IBKR |
| NYSE Arca | maker-taker | IBKR pass-through **($0.0020)** | **$0.0030** | remove 0.3%, no add rebate | [A] IBKR ARCA page |
| Nasdaq BX | inverted (taker rebate, maker fee) | fee | rebate | — | [U] numbers not retrieved |
| Nasdaq PSX | — | ($0.0020) displayed (IBKR) | $0.0030 | — | [A] [IBKR PSX](https://www.interactivebrokers.co.uk/en/accounts/fees/NasdaqPSXstkfee.php) |
| IEX | low-fee | free to add (displayed); rebate tiers to $0.0020 need 20–30M ADV | about $0.0009 | — | [A] tiers [IEX 2026 filing](https://www.sec.gov/files/rules/sro/iex/2026/34-104783.pdf); [U] base remove fee |

- **Top-tier rebates go to members, not retail.** They reach $0.0027–$0.0028 at BZX for members that meet quoting or volume tiers [S] [policyrisk summary](https://policyrisk.com/federal-register/2026-10829). Retail clients get the broker's pass-through schedule, if any.
- **Fees must be known at execution since 2026-02-02.** Rule 610(d), from the 2024 package, became operative on 2026-02-02. Volume tiers now use prior-month volume, so new members get base rates in their first month. [A] [SR-BX-2026-007](https://listingcenter.nasdaq.com/assets/rulebook/nasdaqtx/filings/SR-BX-2026-007.pdf)
- **Sub-$1 stocks:**
  - Fees are a percentage of value (0.30% to remove, under the current Rule 610(c) cap of 0.3%), and add rebates are about zero. [A] exchange and IBKR pages.
  - Quoting goes to $0.0001 below $1. [U]
  - LULD bands are 20% to 75% (section 5).

### 2.2 The 2024 Rule 610/612 package: adopted vs in force

| Element | Adopted (2024-09-18, Rel. 34-101070) | Status Oct 2026 | Tag / source |
|---|---|---|---|
| Access-fee cap, Rule 610(c), ≥$1 | $0.0030 → **$0.0010/share (10 mils)** | **Not in force.** Relief order of 2025-10-31 moved compliance to 2026-11-02; a later 2026 order moved it to the **first business day of Nov 2027**. Chair Atkins directed staff to review 610(c) and 612 by year-end. | [S] [Cleary](https://www.clearygottlieb.com/news-and-insights/publication-listing/the-next-market-structure-rule-arrives-sec-adopts-new-minimum-pricing-increments-and-access-fee-caps); [S] [TradeInformer](https://tradeinformer.com/regulations/sec-extends-nms-relief-rule-611-repeal-2027); [S] [findknowdo](https://www.findknowdo.com/node/660563) |
| Access-fee cap, <$1 | 0.3% → **0.1%** of quote price | Same delay. | [S] same |
| Half-penny tick, Rule 612 | **$0.005** increment for stocks ≥$1 with time-weighted average quoted spread **≤ $0.015** | Same delay (Nov 2027). Also covers Rule 600(b)(89)(i)(F). | [S] same |
| Fees determinable at execution, Rule 610(d) | yes | **In force since 2026-02-02.** | [A] SR-BX-2026-007 |
| Round lot, Rule 600(b)(93) | ≤$250 → 100 sh; $250.01–$1,000 → 40; $1,000.01–$10,000 → 10; >$10,000 → 1. Semiannual reset on a one-month evaluation window. | **Implemented 2025-11-03.** | [A] [exchange filings, e.g. SEC 34-104192](https://www.sec.gov/files/rules/sro/cboebzx/2025/34-104192.pdf) |
| Related | 2026-06-11: SEC proposed rescinding **Rule 611** (trade-through) and Rule 610(e). | proposal | [S] [FlexTrade](https://flextrade.com/resources/secs-broader-reg-nms-overhaul-could-delay-access-fee-tick-sizes/) |

**For low-volume stocks:**
- **The half-penny tick will not apply to them.** They are wide-spread, not tick-constrained, so they keep $0.01 even after the rule takes effect.
- **The round-lot change does not touch them.** They almost all trade under $250, so the round lot stays 100 shares.
- **The 10-mil cap will shrink rebates.** Venues will have to cut maker rebates, since rebates are funded from taker fees. Expect a post-2027 maker rebate of about ≤$0.0008 [U]. That shrinks IBKR-style passive economics for sub-$10 names.

---

## 3. Regulatory fees (sell side unless noted)

| Fee | Rate and effective date | Tag / source |
|---|---|---|
| **SEC Section 31** | **$27.80/$M** through 2025-05-13. **$0.00/$M** from **2025-05-14**, because the FY2025 appropriation was already collected and the rate cannot be negative. **$20.60/$M** from **2026-04-04**, the FY2026 rate after the Consolidated Appropriations Act 2026, which gave the SEC $2.149B. It stays until 60 days after the FY2027 appropriation is enacted. | [A] [SEC fee advisory 2025-2](https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2); [A] [SEC fee advisory 2026-2](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2); [A] [FINRA Info Notice 2026-03-17](https://www.finra.org/rules-guidance/notices/information-notice-20260317) |
| **FINRA TAF** (covered equity sales) | **$0.000195/share, max $9.79/trade** from **2026-01-01** (was $0.000166 / $8.30). **Paused for trades 2026-10-01 to 2026-12-31** (SR-FINRA-2026-021, filed for immediate effectiveness), resuming 2027-01-01. A companion filing (SR-FINRA-2026-020) keeps fees at **2026 rates through 2028-12-31**. | [A] [RH fee page](https://robinhood.com/us/en/support/articles/trading-fees-on-robinhood); [A] [SR-FINRA-2026-021](https://www.finra.org/sites/default/files/2026-09/SR-FINRA-2026-021.pdf); [A] [SR-FINRA-2026-020](https://www.finra.org/sites/default/files/2026-09/SR-FINRA-2026-020.pdf); [S] [Revolut](https://help.revolut.com/en-IS/help/wealth/order-execution-fees-and-limits/trading-regulatory-fees/) |
| **CAT** (charged to executing brokers on **both** buy and sell) | **History:** the Eleventh Circuit vacated the 2023 CAT funding order on 2025-07-25 (*ASA v. SEC*), with fees continuing during the stay. Invoices stopped after the **Dec 2025** invoice. **Now:** **CAT Fee 2026-1** is **$0.000001 per executed equivalent share** (2026-05-01 to 2026-12-31), plus **Historical CAT Assessment 1A** at **$0.000002/share**. Exchange-filing summaries say 1A is billed at **one-third** of that rate per executing broker, about $0.0000007/share [S, fact-check: [policyrisk](https://policyrisk.com/federal-register/2026-09854)]. So about $0.0000017/share per side in all; the $0.000003 used in section 10 is an upper bound. Brokers *may* pass them through. | [A] [CAT Fee Alert 2026-1](https://catnmsplan.com/sites/default/files/2026-04/04.01.26-CAT-Fee-Alert-2026-1.pdf); [A] [CAT Fee Alert 2025-4](https://catnmsplan.com/sites/default/files/2025-11/11.25.25-CAT-Fee-Alert-2025-4.pdf); [A] [MEMX ex5 (Hist. 1A)](https://www.sec.gov/files/rules/sro/memx/2026/34-105445-ex5.pdf); [S] [SIFMA](https://www.sifma.org/advocacy/letters/request-for-the-commission-to-end-consolidated-audit-trail-cat-fees-imposed-under-the-unlawful-cat-funding-model) |
| Robinhood pass-through rules | SEC fee **not passed** on equity sales of **≤$500** notional. TAF **not passed** on sales of **≤50 shares**; rounded to the nearest penny, and the $9.79 cap applies per *order execution*. "As of December 1, 2025, regulators are no longer charging a CAT fee." | [A] [RH fee page](https://robinhood.com/us/en/support/articles/trading-fees-on-robinhood) |
| OTC-only (non-NMS) securities | The Section 31 fee generally does not apply. The CAT counts OTC shares at 0.01 executed-equivalent share. | [U] Section 31 scope; [A] CAT counting |

**Scale:**
- **Section 31:** $20.60/$M is **0.206 bp** of sale value. On $10M of sales a year, that is $206.
- **TAF:** about $1.95 per 10,000 shares sold.
- **CAT:** about $0.02–$0.03 per 10,000 shares per side.
- **These are noise next to spread and adverse selection.** They matter only at very high share counts in low-priced stocks.

---

## 4. Account mechanics: margin, settlement, shorting

### 4.1 PDT rule, margin and the Agentic account

- **The PDT rule is gone.** The pattern-day-trader designation and the $25,000 minimum were removed from FINRA Rule 4210, **effective 2026-06-04** [plan].
  - SEC approval on 2026-04-14; FINRA Regulatory Notice 26-10 on 2026-04-20 [S] [QuantInsti](https://www.quantinsti.com/articles/finra-pdt-rule-removal-2026/); [S] [ACA](https://www.acaglobal.com/industry-insights/finra-ends-the-pattern-day-trader-rule/)
  - The **intraday margin** standard that replaces it has an **implementation phase-in to 2027-10-20**. Brokers' intraday-margin behaviour may still change during that period. [S] [Firstrade](https://blog.firstrade.com/blog/2026/the-complete-guide-to-the-pdt-rule-elimination-everything-investors-need-to-know-on-day-one)
- **Reg T and maintenance margin** still apply: 50% initial, 25% FINRA maintenance minimum.
  - House requirements for low-priced or illiquid stocks are often **100%**, i.e. not marginable, typically under $3–5/share, with concentration add-ons. [U]
- **Robinhood Agentic account** [plan]:
  - cash or "limited margin": **no borrowing, no leverage, no shorting**
  - trades only funds deposited there
  - taxable individual account
  - approvals are **off by default** for external agents
  - no documented per-order caps
- **Settlement is T+1** (since 2024-05-28) [S] [Mudrex](https://mudrex.com/learn/good-faith-violation-gfv-what-it-is/); [plan].
- **Cash-account traps:**
  - **Good-faith violation:** buying with *unsettled* proceeds and selling before they settle.
  - **Free-riding:** buying without paying and selling.
  - Either **3 GFVs in 12 months, or 1 free-riding violation**, triggers a **90-day settled-cash-only restriction**. [S] [Fidelity](https://www.fidelity.com/trading/faqs-trading-restrictions); [S] [Schwab](https://www.schwab.com/learn/story/avoid-these-violations-when-trading-cash)
  - **Implication:** in a cash account each dollar of *settled* cash supports about **one completed round trip per day**. A position bought with today's proceeds must be held overnight.
  - Limited margin (Agentic) or a margin account removes this limit. Exposure is still capped at equity in the Agentic account.

### 4.2 Shorting, and why a retail "market maker" is long-only

| Constraint | Detail | Tag / source |
|---|---|---|
| Agentic account | No shorting at all. | [plan] |
| Robinhood margin accounts | Shorting is a **rolling release**; it needs margin, opening shorts are **GFD only**, and the borrow fee varies intraday. Robinhood can close shorts without notice. | [A] [RH short selling](https://www.robinhood.com/us/en/support/articles/short-selling/); [S] [Finder](https://www.finder.com/stock-trading/short-stocks-on-robinhood) |
| Locate, Reg SHO 203(b) | The broker must have borrowed, arranged to borrow, or have "reasonable grounds" to believe the stock can be borrowed, *before* accepting the short, and document it. The **bona fide market-maker exception** is for registered market makers only, not retail. | [A] [SEC Bayes Capital order](https://www.sec.gov/litigation/admin/2018/34-83556.pdf) |
| Rule 201 circuit breaker | After a **10% drop** from the prior close, short sales may not execute or display **at or below the national best bid**, for the rest of that day and the next. A passive short *offer* above the NBB is still allowed; hitting the bid is not. | [S] [Databento](https://databento.com/compliance/regulation-sho) |
| Borrow cost | Most stocks borrow at about **25 bp/yr** (general collateral). About 9% are "specials" (>1%/yr, mean 4.3%); the maximum observed was 79%/yr (D'Avolio 2002, 2000–01 data). Today's micro-cap hard-to-borrow (HTB) names commonly cost 10%–100%+ a year, or carry per-share locate fees at day-trading brokers. Intraday-only shorts usually avoid the overnight fee but still need the locate. | [S] [NBER summary of D'Avolio](https://conference.nber.org/conf_papers/f228879.pdf); [U] current HTB levels and locate fees |

- **Real two-sided market making needs a short side.** It means selling at the ask without inventory, i.e. short.
- **The retail version cannot do that.** In the Agentic account it is barred. Elsewhere it is constrained by locates, HTB fees, recalls and Rule 201.
- **So the retail version is "buy at bid → offer at ask → hold if not filled".** That is a long-only inventory strategy, fully exposed to downward moves after each buy fill.
- **Backtests must model it that way.**

---

## 5. Halts and volatility controls

| Control | Parameters | Tag / source |
|---|---|---|
| **LULD bands** | **Reference price:** the mean of the last five minutes of trades. **Tier 1** (S&P 500, Russell 1000, select ETPs): **5%** for reference price >$3. **Tier 2** (all other NMS stocks): **10%** for >$3. Both tiers: **20%** for $0.75–$3.00; **lesser of $0.15 or 75%** below $0.75. | [A] [FINRA: guardrails](https://www.finra.org/investors/insights/guardrails-market-volatility); [A] [luldplan.com](https://luldplan.com/) |
| Band doubling | **Last 25 minutes** (3:35–4:00 pm) for all Tier 1 and for Tier 2 stocks **≤ $3.00**. An NYSE fact sheet also says the first 15 minutes; official pages say the close only (conflict). | [A] [Investor.gov](https://www.investor.gov/news-alerts/investor-bulletins/measures-address-market-volatility); [S/U] NYSE sheet |
| Limit state → pause | A limit state lasts 15 s. If it does not clear, the primary exchange declares a **5-minute pause**, extendable by 5 minutes on a significant imbalance; trading reopens by auction. | [A] FINRA / LULD plan |
| How often | About **7,800–8,800 LULD pauses a year** in 2023–24. The report's text is garbled on which year is which. **About 20% fall in the first 15 minutes** of trading. Tier 2 non-ETPs dominate. Straddle states: 882k in 2024 vs 2.28M in 2023. | [A] [LULD 2024 Annual Report](https://cdn.luldplan.com/reports/LULD-2024-Annual-Report.pdf) |
| 2026 daily counts | About **30–50 halts per day** (many days listed as "50", possibly capped). E.g. 2026-09-30: 38 halts (31 LULD, 3 T1 news-pending, 4 other). "Volatility halts concentrated in a handful of small-cap names." | [S] [Tapeboard 2026-09-30](https://tapeboard.com/blog/trading-halts-2026-09-30) |
| News-pending (T1) and regulatory halts | Called by the listing exchange; often after the close and lasting into the next day. | [S] same |
| SEC trading suspensions plus exchange follow-on halts | **2025-09-29:** first SEC suspensions since Oct 2024, for QMMM and Smart Digital, citing social-media "ramp-and-dump". By **Feb 2026**, 14 Asia-based listed small caps had been frozen, and NYSE and Nasdaq follow-on halts turned these into **months-long** halts. SEC Cross-Border Task Force set up 2025-09-05. | [S] [Bloomberg Gov](https://news.bgov.com/securities-law/sec-foreign-firm-suspension-blitz-spurs-monthslong-trading-halts); [S] [securitieslawyer101](https://www.securitieslawyer101.com/2025/sec-trading-suspensions-of-qmmm-sdm-new-sec-cross-border-task-force/) |

- **Inventory risk in low-volume names is jump risk.** A pause, an overnight news halt or a months-long suspension freezes the position, and you cannot exit at any price.
- **Most halts sit exactly in the universe the friend trades.** These are Tier 2 stocks, with 10% bands above $3 and 20%+ bands at or below $3.

---

## 6. Legal lines: manipulation law and where size crosses it

### 6.1 The rules

| Conduct | What it is | Main provisions | Tag |
|---|---|---|---|
| Spoofing / layering | Orders not intended to execute (often several price levels on one side) placed to move the NBBO or create a false impression of interest; trade on the other side; cancel. | Exchange Act **9(a)(2)**, **10(b)/Rule 10b-5**, Securities Act 17(a); FINRA 2020 / 5210 | [A] SEC orders below |
| Spoofing in futures/swaps | "Bidding or offering with the intent to cancel before execution". | **CEA 4c(a)(5)(C)**, added by **Dodd-Frank §747**. Applies to registered-entity (futures/swaps) markets, **not stocks**. First criminal conviction: Coscia (2015 verdict, 3 years in prison, upheld by the 7th Circuit). | [S] [Greenberg Traurig](https://www.gtlaw.com/ar/insights/2016/7/coscia-gets-3-years-in-prison-the-criminalization-of-trading-commodities); [S] [findknowdo](https://www.findknowdo.com/node/261682) |
| Open-market manipulation ("ramping", momentum ignition) | "A series of transactions in any security creating actual or apparent active trading in such security, or raising or depressing the price of such security, for the purpose of inducing the purchase or sale of such security by others." | **9(a)(2)**, 10(b) | [A] text as quoted in [SEC complaint (Masri)](https://www.sec.gov/litigation/complaints/comp19033.pdf) |
| Marking the close | Buying or selling at or near the close to set the closing price. | 9(a)(2), 10(b) (Masri, ADRs; **Koch v. SEC**, D.C. Cir. 2015, three *small bank stocks*, manipulation finding affirmed) | [U] Koch citation (see 6.2) [SEC LR-23308 (Koch)](https://www.sec.gov/litigation/litreleases/2015/lr23308.htm); [S] [Akin Gump on Masri](https://www.akingump.com/a/web/1243/aogHP/07005080021aking.pdf) |
| Wash trades / matched orders | Trades with no change in beneficial ownership, e.g. your account vs your spouse's or your other broker account; prearranged trades with a friend. | **9(a)(1)**; FINRA 5210 Supplementary Material (self-trades) | [U] |
| Pump-and-dump / "scalping" in the *legal* sense | Recommending or touting a stock, then selling into the rise without disclosure. **"Scalping" in securities law means this, not spread trading.** | 10(b); for advisers, Advisers Act 206 (*SEC v. Capital Gains Research Bureau*, 375 U.S. 180, 1963) | [A] [Cornell LII, 375 U.S. 180](https://www.law.cornell.edu/supremecourt/text/375/180) |

### 6.2 Enforcement against *individual* day traders, mostly in thin stocks

| Case | Facts | Outcome | Tag / source |
|---|---|---|---|
| **SEC / DOJ v. Mingran Wang** (2026) | A Fremont, CA day trader. From Oct 2021 to at least Nov 2024 he spoofed **150+ thinly traded ADRs**: about 3,000+ spoof episodes, trading the opposite side **in a separate account**. | SEC settled 2026-06-24: injunction and a 5-year trading ban, with disgorgement and penalty to be set by the court. Criminal guilty plea, **$1.3M+ forfeiture**; sentencing was set for 2026-09-30, outcome not found. | [A] [SEC LR-26574](https://www.sec.gov/enforcement-litigation/litigation-releases/lr-26574); [S] [Investment Executive](https://www.investmentexecutive.com/news/regulation/day-trader-admits-spoofing/); [S] [S&C memo](https://www.sullcrom.com/insights/memo/2026/June/DOJ-SEC-Bring-Parallel-Spoofing-Actions) |
| **In re Xuepeng Xie** (2021; SEC administrative order, not a court case) | A full-time NC day trader. "On an almost daily basis for at least five years", from Aug 2016 to Feb 2021, he manipulated the NBBO of "hundreds of thinly-traded stocks". He used several broker accounts, and kept trading after a broker flagged him, calling the trades mistakes. | Settled: **$1,864,787 disgorgement**, $243,991 interest, **$600,000 penalty**; 9(a)(2), 10(b), 17(a). | [A] [SEC 33-10989](https://www.sec.gov/litigation/admin/2021/33-10989.pdf) |
| **In re Nicholas Scrivener** (2020; SEC administrative order) | A CA day trader, Feb 2015 to Sep 2016, about **$140k** profit. After a broker closed his account, he opened one in his wife's name. | Settled for about **$205k** in total. The cited headline puts the whole $205k on the SEC order (disgorgement, interest and penalty). No parallel CFTC matter was found. | [A] [SEC 34-89517](https://sec.gov/litigation/admin/2020/34-89517.pdf); [S] [Finance Magnates](https://www.financemagnates.com/institutional-forex/regulation/sec-hits-day-trader-with-205k-fine-in-spoofing-case/); [U] breakdown (fact-check) |
| **US / SEC v. Aleksandr Milrud** (2015) | "First federal prosecution of securities fraud involving … layering"; recruited traders in China and Korea. | Guilty plea; **5 years' probation, $285k forfeiture**. | [A] [SEC LR-25319](https://www.sec.gov/enforcement-litigation/litigation-releases/lr-25319); [A] [DOJ](https://www.justice.gov/opa/pr/canadian-man-charged-first-federal-securities-fraud-prosecution-involving-layering) |
| **Koch v. SEC** (D.C. Cir. 2015) | An adviser bought three small bank stocks just before the close to lift prices. | Manipulation finding affirmed. | [U] (fact-check: the case is 793 F.3d 147. Koch began as an SEC administrative proceeding, so a litigation release for it would be unusual, and LR-23308 is not confirmed as the right document) [SEC LR-23308](https://www.sec.gov/litigation/litreleases/2015/lr23308.htm) |
| Broker-side surveillance | FINRA and the exchanges fine *firms* that fail to surveil spoofing and layering (e.g. BGC, $200k; Barclays 2025, where parameters were too coarse for "smaller-sized" spoofing). **Brokers are under pressure to flag and close accounts.** | — | [S] [Finance Magnates (BGC)](https://www.financemagnates.com/institutional-forex/bgc-faces-regulatory-settlement-for-supervisory-lapses/); [A] [Nasdaq disciplinary, Barclays](https://www.nasdaq.com/docs/2025/06/12/Disciplinary-Actions-BX-Barclays-Capital-Inc-05-29-2025.pdf) |

### 6.3 When "buying a large amount of a low-volume stock" crosses a line

**Lawful:**
- Buying, even in size and even if it moves the price, when the purpose is to own the shares or to trade them for profit.
- A **large resting bid you genuinely want filled**.
- Posting a bid and an offer at the same time, if both are bona fide.

**Crosses the line, using the patterns in the cases above:**
1. **Bid as bait.**
   - The fact pattern: a large bid (or bids at several levels) that you would cancel if approached; your ask fills; you cancel the bid within seconds.
   - Repeated across many thin names, this *is* Xie and Wang.
   - Intent is inferred from pattern: high cancel rates after opposite-side fills, fills within seconds, and order size far above your normal fills.
2. **Stepping the bid up to induce momentum**, then selling into it. This is "raising the price … for the purpose of inducing … others" (9(a)(2)) and "momentum ignition".
   - The bigger your share of the stock's volume, the more your own buying *is* the price action. In a stock trading $200k a day, a $1M buy program is the market.
3. **Self-crossing or friend-crossing.**
   - Your ask fills your own bid in another account or at another broker, or the friend and the user trade with each other: wash or matched trades (9(a)(1)).
   - Running two-sided quotes across accounts without self-trade prevention creates this by accident.
4. **Trading at the close to set a price**, e.g. a month-end mark for margin or performance. This is marking the close (Koch).
5. **Talking it up.** Posting about the stock (Discord, X, chat groups) while holding inventory to sell is a pump-and-dump, or "scalping" in the legal sense.
6. **Coordinating with the friend in the same thin names.**
   - Concert trading carries manipulation risk.
   - It can also make the two of you a **13(d) "group"**, whose holdings are aggregated (section 7).
7. **Crossing 5% or 10% without filing** (section 7).

**The dealer question is moot for now.**
- The SEC's 2024 rule that would have made some liquidity providers register as dealers was **vacated on 2024-11-21** (N.D. Tex.).
- The SEC dropped its appeal on **2025-02-20**.
- The rule also excluded persons with <$50M in assets.
- An individual trading their own money remains a "trader", not a "dealer". [S] [Lowenstein](https://lowenstein.com/media/nw2p0zao/20241125-broker-dealer-federal-district-court-vacates-the-security-and-exchange-commission-s-expanded-dealer-rule.pdf); [S] [AIMA](https://www.aima.org/article/aima-welcomes-the-sec-decision-to-withdraw-its-dealer-rule-appeal.html)

---

## 7. Ownership and size thresholds that bind with large capital

| Threshold | Trigger and deadline | Tag / source |
|---|---|---|
| **Schedule 13D** (>5%, active intent) | Initial filing within **5 business days** (was 10 calendar days); amendments **2 business days** after a material change. Effective 2024-02-05. | [S] [Foley](https://www.foley.com/en/insights/publications/2023/10/sec-adopts-changes-schedule-13d-schedule-13g); [S] [BakerHostetler](https://www.bakerlaw.com/insights/the-sec-catches-schedule-13d-and-13g-filings-up-to-speed-with-accelerated-deadlines) |
| **Schedule 13G**, passive investor (>5%, <20%, no control intent) | Initial filing **5 business days** (was 10 days). Amendment within 2 business days of crossing 10%, then of each ±5% change. Compliance from **2024-09-30**; XML required from 2024-12-18. | [S] same; [U] passive-investor amendment trigger |
| 13G for QIIs and exempt investors | 45 days after quarter end; monthly trigger at >10% or ±5%. | [S] same |
| **Section 16** (>10% beneficial owner) | **Form 3** within 10 days, **Form 4** within **2 business days** of every trade. **16(b):** the company (or a shareholder suing for it) recovers **all profit from any purchase and sale matched within 6 months**. Matching is lowest-in/highest-out, and losses do not offset. The purchase that *crosses* 10% is not matched (*Foremost-McKesson*, 423 U.S. 232). | [A] [Foremost-McKesson](https://www.law.cornell.edu/supremecourt/text/423/232); [U] Form deadlines and matching rule |
| **Rule 144** (affiliates; ≥10% holders are often treated as presumptive affiliates) | Sales in any 3 months are capped at the **greater of 1% of shares outstanding or the average weekly volume of the prior 4 weeks** (1% only for OTC). **Form 144** if >5,000 shares or >$50,000 in 3 months. Ordinary brokerage transactions only. | [S] [Cooley flowchart](https://ipogo.cooley.com/wp-content/uploads/2025/02/Rule-144-Overview-and-Flowchart.pdf); [S] [Carta](https://carta.com/learn/startups/equity-management/rule-144/) |
| **Large Trader, Rule 13h-1** (applies to activity, not ownership) | Transactions in NMS securities **≥ 2M shares or ≥ $20M in a calendar day**, or ≥ 20M shares or ≥ $200M in a month. File Form 13H (confidential), get an LTID, and give it to brokers. Annual update within 45 days of year end. | [S] [Harvard Corp Gov](https://corpgov.law.harvard.edu/2011/08/16/sec-adopts-large-trader-reporting-requirements/); [S] [Faegre Drinker](https://faegredrinker.com/en/insights/publications/2011/8/large-trader-obligations-under-new-rule-13h1); [U] application to a natural person trading their own account |
| HSR antitrust | Voting-securities holdings **> $133.9M** (from 2026-02-17), subject to the size-of-person test. The investment-only exemption applies up to 10%. | [S] [Foley](https://www.foley.com/insights/publications/2026/01/hart-scott-rodino-reporting-threshold-increases-by-7-5-million-after-latest-yearly-adjustment/); [U] exemption |

**Market cap at which a position crosses 5% and 10% of shares outstanding (arithmetic: position ÷ threshold):**

| Position | Crosses 5% (13D/G) at market cap ≤ | Crosses 10% (Section 16) at market cap ≤ | Days to exit at 20% of ADV, if ADV = $250k / $1M / $5M |
|---|---|---|---|
| $250k | $5M | $2.5M | 5 / 1.3 / 0.25 |
| **$1M** | **$20M** | **$10M** | 20 / 5 / 1 |
| **$5M** | **$100M** | **$50M** | 100 / 25 / 5 |
| $10M | $200M | $100M | 200 / 50 / 10 |
| $25M | $500M | $250M | 500 / 125 / 25 |

- **Thresholds use the voting class outstanding, not the float.** Low-float names cross much faster in practical terms (exit liquidity), though not for filing.
- **Filing counts all beneficially owned shares.** That includes spouse and controlled accounts, and a coordinating friend if you form a "group".
- **Turnover hits Large Trader first.** Buys and sells both count. A $5M position bought and sold twice a day is $20M of transactions, which reaches the Large Trader level before any ownership threshold.
  - Below $10/share the **2M-share prong** binds first. At $2, a $2M round trip (2M shares, $4M of transactions) already qualifies. [U] (fact-check)

---

## 8. Taxes

| Topic | Detail | Tag / source |
|---|---|---|
| Character | Scalping gains are **short-term**, taxed at ordinary rates: federal up to 37%, plus 3.8% NIIT, plus state. Examples: CA top 13.3%; NY 10.9% plus NYC 3.876%; TX/FL 0%. | [U] rates; [plan] (short-term) |
| **Wash sales** (§1091) | A loss on a sale is disallowed if substantially identical stock is bought **within 30 days before or after**. The disallowed loss is added to the basis of the replacement lot, and its holding period tacks on. | [U] (statutory) |
| … mechanics for frequent same-ticker trading | Every losing round trip followed by a re-buy within 30 days defers the loss into the next lot, chaining through the year. The deferral is *real* only for lots still open at year end, or re-bought in early January after a December loss. A buy in an **IRA** turns the loss into a permanent loss [U: Rev. Rul. 2008-5]. Expect 1099-Bs with large "wash sale loss disallowed" totals that mostly net out within the year. | [U] |
| … broker reporting | Brokers report wash-sale adjustments only for the **same account and identical CUSIP**. Cross-account and cross-broker wash sales (including the user's Schwab robo, which tax-loss-harvests) are the **taxpayer's job** (Form 8949 code W). Robinhood does not cross-check across accounts. | [S] [KPMG primer](https://kpmg.com/kpmg-us/content/dam/kpmg/taxnewsflash/pdf/2022/07/22208.pdf); [plan]; HANDOFF §10 (Schwab robo) |
| **Trader tax status** (TTS) | A facts-and-circumstances test: substantial, regular and continuous activity, profiting from short-term swings. There is no bright line. *Endicott* (T.C. Memo. **2013-199**) was denied despite frequent trading, because its holding periods were too long. (Fact-check: T.C. Memo. 2004-132 is *Chen*, another denial.) TTS lets expenses be deducted as business expenses. | [S] [Morkel](https://morkelfinancial.com/blog/missed-mark-to-market-election-deadline); [U] case details |
| **§475(f) mark-to-market** | **Deadline:** the **unextended due date of the prior year's return**. For 2027 that is about **2027-04-15**; it is too late for 2026. Late elections are rarely granted (§301.9100 relief, PLR 202037007). **Mechanics:** Form 3115 in the year of change. **Effects:** gains and losses become **ordinary**; **wash sales do not apply**; the **$3,000/yr capital-loss cap** does not apply; no self-employment tax; positions are marked at year end. **Exit:** revoking is an automatic method change (the current list is Rev. Proc. 2025-23). Re-electing within 5 years of a revocation needs IRS consent, a long-standing rule rather than one new in 2025-23 [U, fact-check]. So treat the election as about a 5-year commitment. | [S] [Morkel](https://morkelfinancial.com/blog/missed-mark-to-market-election-deadline); [A] [PLR 202037007](https://www.irs.gov/pub/irs-wd/202037007.pdf); [S] [TurboTax community](https://ttlc.intuit.com/community/taxes/discussion/how-can-i-make-the-mtm-election-for-the-next-year/00/272031) |
| Excess business loss (§461(l)) | For a 475 trader with large ordinary losses, business losses above **$256,000 single / $512,000 joint (2026)** become an NOL carryforward (80% of taxable-income limit). OBBBA made the limit permanent. | [S] [Citrin Cooperman](https://www.citrincooperman.com/In-Focus-Resource-Center/Modification-and-Extension-of-Limitation-on-Excess-Business-Losses-of-Noncorporate-Taxpayers) |
| Form 8949 volume | **Every sale is a line.** Thousands of round trips a year are normal. If all are covered and need no adjustments, totals can go straight to Schedule D. Wash-sale adjustments require 8949, or an attached broker statement with the same detail. Tax software and broker CSV import are a practical necessity. | [U] |

---

## 9. Automation feasibility, by time scale

| Route | Data | Order path | Measured or documented speed | Realistic time scale |
|---|---|---|---|---|
| **(a) Claude + Robinhood agentic MCP** | `get_equity_quotes`: snapshot, ≤20 symbols with official closes. `get_equity_price_book`: **"real-time … Level 2 snapshot"**, **max 4 symbols per call**. **No streaming**, no order-status push. | `review_equity_order` → `place_equity_order`. With approvals on, an order "goes to the customer to approve or decline in the Robinhood app". **One order per call; cancel is a separate call.** No cancel-replace, IOC, post-only, OCO or bracket orders. | **Measured this session:** two read calls took **7.7 s and 8.4 s** each (shell timestamp → MCP call → shell timestamp, including model turn time; Sunday, market closed). Placing an order adds review, place and a **human tap**: seconds to minutes. Rate limits are **undocumented**. Policy context: Robinhood's tool descriptions make a preview (`review_equity_order`) the default, skippable only if the user very explicitly asks [A, schema re-read in the fact-check]. Anthropic's AUP from 2026-11-12 treats personalized trade recommendations as needing a human in the loop [plan]. | **End of day, or at best tens of minutes.** Unusable for quoting, re-pricing or queue management. |
| **(b) Local bot, IBKR TWS API** | Streaming L1 ("several times per second"), tick-by-tick, market depth (data subscriptions needed) | Direct, with in-place order modification (better for the OER limit) | Pacing about **50 requests/s**: max market-data lines ÷ 2, default 100 lines. Three pacing violations end the session. The Web API allows 50 req/s, with snapshots at 10 req/s. | **Seconds to minutes** quote management in a handful of names. Not sub-second queue racing. |
| (b) Local bot, Alpaca | Websocket (IEX free; SIP on a paid plan [U]) | REST, **200 requests/min** (orders and cancels each count) | About 3 actions/s for the whole account | **Minutes.** Seconds-scale only for 1–2 names. Elite DMA for venue control. |
| (b) Local bot, Lightspeed / DAS / Sterling API | Direct L2 | Route per order | Similar to IBKR; vendor-specific [U] | Seconds to minutes |
| **(c) Manual** (DAS / Lightspeed hotkeys, or the RH app) | Streaming L2 (RH Legend has L2 [U]) | Human | Human reaction about 0.3–2 s per action [U] | **Seconds to minutes**, in 1–5 names; fatigue-limited |
| Professional HFT market makers (benchmark) | Direct exchange feeds, colocation | Exchange gateways | Microseconds [U] | Sub-millisecond: the competition for queue position at the inside |

Sources:
- MCP tool descriptions loaded this session [A].
- IBKR pacing: [A] [IBKR TWS API pacing](https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/introduction); [A] [IBKR Web API limits](https://www.interactivebrokers.com/docs/web-api/trading/usage-and-availability/pacing-limitations); [S] [IBKR Campus](https://ibkrcampus.eu/trading-lessons/python-receiving-market-data/).
- Alpaca: [S] forum.

**Feasibility by time scale:**
- **Sub-second:** no retail route that can compete for queue position. A local IBKR bot can send messages in under a second, but not at HFT speed.
- **Seconds:** a local bot on IBKR or Lightspeed, or manual trading, with a direct-access broker.
- **Minutes:** a local bot on any broker API.
- **End of day:** Claude plus the Robinhood MCP (approvals on), consistent with the existing plan's architecture: Python decides, Claude operates.

---

## 10. Per-trade cost table (explicit costs only)

**Assumptions** (rates as above; the arithmetic is reproducible from these inputs; a scratch script computed it this session):
- **Robinhood:**
  - $0 commission
  - SEC $20.60/$M on sells over $500
  - TAF $0.000195/share on sells over 50 shares, rounded to the cent (**$0 for trades 2026-10-01 to 12-31**)
  - no CAT, no rebate
- **IBKR Pro tiered**, first tier:
  - $0.0035/share (min $0.35, max 1%)
  - clearing $0.0002
  - pass-throughs 0.074% of commission
  - CAT $0.000003/share (upper bound; probably about $0.0000017, see section 3; immaterial)
  - maker rebate **$0.0016** (Cboe standard; IBKR ARCA $0.0020, INET $0.0013)
  - taker fee $0.0030
  - SEC and TAF on sells
- **Round trip (RT)** = buy + sell, in bp of one side's notional.

| Price | Shares | Notional | RH buy | RH sell | **RH RT (bp)** | IBKR maker buy | IBKR maker sell | **IBKR maker RT (bp)** | **IBKR taker RT, $ (bp)** |
|---|---|---|---|---|---|---|---|---|---|
| $2 | 100 | $200 | $0.00 | $0.02 | 1.00 | $0.21 | $0.24 | 22.5 | $1.37 (68.5) |
| $2 | 1,000 | $2,000 | $0.00 | $0.25 | 1.25 | $2.11 | $2.35 | 22.3 | $13.66 (68.3) |
| $2 | 10,000 | $20,000 | $0.00 | $2.37 | 1.19 | $21.06 | $23.43 | 22.2 | $136.48 (68.2) |
| $10 | 100 | $1,000 | $0.00 | $0.05 | 0.50 | $0.21 | $0.26 | 4.7 | $1.39 (13.9) |
| $10 | 1,000 | $10,000 | $0.00 | $0.41 | 0.41 | $2.11 | $2.51 | 4.6 | $13.82 (13.8) |
| $10 | 10,000 | $100,000 | $0.00 | $4.01 | 0.40 | $21.06 | $25.07 | 4.6 | $138.12 (13.8) |
| $50 | 100 | $5,000 | $0.00 | $0.13 | 0.26 | $0.21 | $0.34 | 1.1 | $1.47 (2.9) |
| $50 | 1,000 | $50,000 | $0.00 | $1.23 | 0.25 | $2.11 | $3.33 | 1.1 | $14.64 (2.9) |
| $50 | 10,000 | $500,000 | $0.00 | $12.25 | 0.24 | $21.06 | $33.31 | 1.1 | $146.36 (2.9) |

**Per share:**
- IBKR maker RT ≈ **$0.0045**, i.e. 0.45 of a one-cent tick, at $2–$10. It is $0.0055 at $50, since the SEC fee scales with price. The TAF pause takes off $0.0002.
- IBKR taker RT ≈ **$0.0137**, i.e. 1.37 ticks.
- Robinhood RT ≈ $0.0002 plus 0.2 bp, explicit only.

**What the gross spread pays (one tick = $0.01):**
- One captured tick is **50 bp at $2, 10 bp at $10, 2 bp at $50**.
- After IBKR maker costs, a full-tick round trip nets **$0.0055/share** at $2–$10 ($0.0045 at $50), before adverse selection and inventory losses.
- After IBKR taker costs it is negative.
- On Robinhood the explicit cost is near zero. The losses come from no queue control, no rebate and wholesaler-mediated fills.

**IBKR maker net cost per side by monthly volume tier** (commission + $0.0002 clearing − rebate):

| Tier (shares/month) | Rebate $0.0013 | $0.0016 | $0.0020 |
|---|---|---|---|
| ≤300k ($0.0035) | $0.0024 | $0.0021 | $0.0017 |
| ≤3M ($0.0020) | $0.0009 | $0.0006 | $0.0002 |
| ≤20M ($0.0015) | $0.0004 | $0.0001 | −$0.0003 |
| ≤100M ($0.0010) | −$0.0001 | −$0.0004 | −$0.0008 |
| >100M ($0.0005) | −$0.0006 | −$0.0009 | −$0.0013 |

- **Volume buys better tiers; capital does not.** A $5M account at $10 that buys and sells its whole size once a day buys about 10.5M shares a month. IBKR's tier count includes both buys and sells, so that is about 21M shares. It passes through the $0.0015 tier and reaches $0.0010 near month end. [U] (fact-check: both-sides counting)
- **Rebates shrink in Nov 2027.** If the 10-mil cap takes effect then, rebates will probably fall well below $0.0010 [U]. That removes most of the net-credit rows.

---

## Implications for our tests (assumptions the backtests must use)

1. **Two cost regimes, both explicit:**
   - **"RH"**: $0 commission, SEC fee 0.206 bp on sells over $500, TAF $0.000195/share on sells over 50 shares (cap $9.79; set to 0 for Oct–Dec 2026), no rebate.
   - **"IBKR tiered"**:
     - commission $0.0035/share (min $0.35, max 1%), clearing $0.0002, pass-through 0.074% of commission, CAT $0.000003/share, SEC and TAF as above
     - **maker rebate base $0.0013**, sensitivities $0.0000 and $0.0020; taker $0.0030
     - (fact-check) The section 0 and 10 figures used a $0.0016 rebate. At the $0.0013 base the passive round trip is about **$0.0051/share** at $2–$10, not $0.0045, and a full tick nets about $0.0049.
     - for sub-$1 stocks, 0.30% to remove and no rebate
   - **Report results under both.** Run a "post-Nov-2027" sensitivity with taker $0.0010 and maker rebate ≤ $0.0008.
2. **Fill model for passive orders (conservative by default):**
   - A buy limit fills only when a later trade prints **below** the limit (trade-through), or **at** the limit with cumulative volume exceeding the displayed size ahead of us at arrival (back of the queue).
   - **RH variant:** no queue position at all. Fill only on trade-through, since display, routing and internalization are opaque.
   - Never assume a fill at our own price because the bar's low touched it.
3. **Latency:**
   - Local-bot strategies: ≥1 s from signal to order, and from fill to re-quote.
   - Claude/MCP strategies: **≥10 s per action plus human approval**, so test them on **daily or EOD decisions only**. Re-pricing a passive order through the MCP should not be modelled as faster than minutes.
4. **Adverse selection must be measured, not assumed away.** Report markouts (mid-price change after each fill) at 1 s, 1 min, 5 min, end of day and next open, split by side. Spread capture minus markout is the edge.
5. **Inventory is long-only.**
   - No short sales and no selling at the ask without inventory (Agentic account). Optional sensitivity: allow shorting only with a locate haircut and Rule 201 after −10% days.
   - Model **end-of-day flat versus overnight hold** separately, since gaps and news halts land overnight.
6. **Halts:**
   - Use point-in-time data **including delisted and suspended names**.
   - During LULD pauses and T1/SEC halts, positions are frozen and orders do not fill.
   - Mark multi-week halts at the reopening price.
   - Exclude nothing after the fact.
7. **Capacity and ownership caps:**
   - Participation ≤ 10–20% of ADV.
   - Position < **4.9% of shares outstanding** by default; never ≥ 10%, because 16(b) would disgorge round-trip profits.
   - Report days-to-exit at 20% of ADV.
   - Flag runs that would trigger Large Trader: ≥$20M **or ≥2M shares** a day, buys plus sells.
   - Scale tests at $250k, $1M and $5M to show how returns degrade with size.
8. **Universe and ticks:**
   - Price ≥ $1 by default (sub-$1 as a separate, labelled test).
   - NMS stocks only; no OTC.
   - Tick $0.01 until at least Nov 2027. The half-penny tick does not apply to wide-spread names.
   - Round lot 100 shares, since these names trade under $250.
9. **Cash and settlement:**
   - Cash-account variant: each settled dollar supports one round trip per day (T+1, no good-faith violations).
   - Margin or limited-margin variant: intraday reuse allowed, exposure ≤ equity, no leverage.
   - No PDT constraint after 2026-06-04.
10. **Taxes:**
    - Treat all gains as short-term at the user's marginal rate (illustrative 35% federal+state, as in `gate.py`).
    - No §475(f) before tax year 2027; the election is due about 2027-04-15.
    - Track wash sales for strategies that hold losing lots across days. Coordinate with the Schwab robo's tax-loss harvesting.
    - Compare after tax against holding SPY (gate rule T2b).
11. **Compliance rails built into the strategy, so it could legally run live:**
    - one resting order per side per name
    - no cancelling a resting bid within N seconds after our own ask fills, as a default rule
    - no closing-auction orders whose purpose is price-setting
    - self-trade prevention across accounts
    - IBKR order-efficiency ratio ≤ 20 a day
    - order size consistent with willingness to be filled
    - log the decision rationale

**Blockers and open items:**
- **No primary-source documents could be opened.** Every [A] item rests on search-engine retrieval of the primary page.
- **Re-check these before freezing the pre-registration:**
  - the TAF pause. It was filed for immediate effectiveness, and the fact-check confirmed its dates in the filing text. The SEC could still suspend it.
  - the Nov 2027 tick-size and access-fee delay (secondary sources only). `literature_scalping.md` still treats Nov 2027 as [U] and uses 2026-11-02, so the two notes must be reconciled before freezing.
  - IBKR's conflicting INET rebate ($0.0013 vs $0.0021)
- **Robinhood does not document** how it handles non-marketable limit orders (held, displayed or routed). Its NMLO payment-for-order-flow figures conflict.
- **Robinhood MCP rate limits are unknown.**
- **The tests need intraday trade and quote data** (TAQ-level, or at least 1-minute bars with quotes) for low-volume US stocks. Daily bars cannot test spread capture. Whether such data is reachable from this sandbox is the main open feasibility question for the study.
