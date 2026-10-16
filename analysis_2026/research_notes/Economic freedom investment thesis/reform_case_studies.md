# Reform Case Studies: Pro-Market Reforms, Anti-Market Reversals, and USD Equity Returns (as of Oct 2026)

Scope note for the report writer. This file has two kinds of evidence:

1. **Computed USD returns (most of the numbers).** I calculated these in this session from month-end prices of US-listed country ETFs, which track MSCI or FTSE country indexes. They are labelled **[Computed]** and link to the script and data in `reform_case_studies_data/` next to this file.
   - **Price-only series.** Most country ETFs (ARGT, INDA, MCHI, KWEB, FXI, TUR, GREK, VNM, KSA, EPU, EWW, EZA, EIDO, ECH, EPOL, ACWI, EEM, URTH, DXJ) come from Robinhood market-data monthly bars. Those bars are split-adjusted but not dividend-adjusted, so they are price returns.
   - **Total-return series.** EWJ, EWZ, EWU, EEM, EFA and SPY come from the repo's local dividend-adjusted daily files in `data/universe_pit_all/`.
   - **Benchmarks.** "World" = ACWI (MSCI ACWI) or EFA (MSCI EAFE, developed markets outside the US and Canada). "EM" = EEM (MSCI Emerging Markets).
   - **Relative return** = (1+country)/(1+benchmark)−1. Price-only countries are compared with price-only benchmarks, and total-return countries with total-return benchmarks.
   - **Data end.** Data runs to the 2026-09 month-end close (Sep 30, 2026).
2. **Web findings.** These come from search-result summaries only. Every WebFetch failed with DNS errors, and the session's web-search budget ran out partway through, so I could not open the full pages. Treat web figures as "reported by" the cited outlet.

Event dates (election days, law signings and so on) are standard public facts from general knowledge. I did not re-verify them this session unless a source is cited.

---

## 1. Pro-market reform episodes: what was the policy, when did it become clear, and how did the local market do in USD relative to EM and World at 1/3/5/10 years?

### Takeaway
Of 16 modern pro-market episodes with ETF data, about 11 outperformed EM over the first year, 7 of 13 over three years and only 5 of 11 over five years. The edge from reform shrinks over time, and some of the best performers at one year later reversed sharply (Argentina 2018–19, Brazil after 2019, Turkey after 2024). The older, famous episodes (UK 1979, NZ 1984, Chile, Mexico, India 1991, Poland, Peru, Brazil 1994) predate the ETFs. For those I found only local-currency or partial USD data.

### Cited Findings

#### Case table: modern pro-market episodes (USD, price-only unless marked TR; relative to EEM / ACWI unless noted)
Notation: "+17 / +21" = outperformed EEM by 17% and ACWI by 21% over the window. t0 = month-end when the reform or the reformer's win became clear.

| Episode | Policy / trigger (t0) | Vehicle | Pre-window rel. (window) | 1y rel | 3y rel | 5y rel | 10y rel | t0 → Sep-2026 rel | Priced early? |
|---|---|---|---|---|---|---|---|---|---|
| Argentina – Macri | Runoff won 22 Nov 2015; FX controls lifted Dec 2015, holdout deal 2016 (t0 = Nov-2015) | ARGT | +13 / +7 (Jul→Nov 2015) | +17 / +21 | +13 / +13 | +5 / 0 | +209 / +101 (distorted by MercadoLibre; see notes) | +132 / +66 | Partly. ARGT +29% vs EEM −11% from Jun-2012 to Oct-2015, while CFK was still in office |
| Argentina – Macri peak → crisis | Peak month Jan 2018; 2018 IMF crisis; Aug 2019 primary shock | ARGT | +35 / +53 (Nov-15→Jan-18) | −13 / −19 | −28 / −36 | +31 / −11 | n/a | +73 / +8 | Gains reversed: −41% Jan-2018→Aug-2019; Aug-2019 alone −31% |
| Argentina – Milei | PASO surprise 13 Aug 2023; runoff 19 Nov 2023 (t0 = Nov-2023) | ARGT | +53 / +40 (Nov-22→Nov-23); +14 / +9 (Jul→Nov 2023) | +51 / +33 | n/a | n/a | n/a | +1 / +5 | Yes, a lot before and also a lot in year 1. Then gave back everything relative to EM |
| Argentina – Milei midterm | Midterm win 26 Oct 2025 (t0 = Oct-2025) | ARGT | +31 / +32 (Sep→Oct 2025) | n/a | – | – | – | −24 / −19 (to Sep-2026) | Event spike was the high point; ARGT's peak monthly close was Jan-2026 |
| India – Modi | Named PM candidate Sep 2013; election result 16 May 2014 (t0 = May-2014) | INDA | +25 / +19 (Aug-13→May-14) | +11 / +4 | +18 / +4 | +32 / +8 | +90 / +1 | +4 / −38 | Yes. INDA +28% vs EEM +4% Sep-2013→May-2014. The long-run edge was over EM, not World. INDA −20% vs EEM +46% Sep-2024→Sep-2026 |
| Brazil – Temer reforms | Rousseff suspended 12 May 2016; spending cap Dec 2016; labor reform 2017 (t0 = May-2016) | EWZ (TR) vs EEM / EFA (TR) | +18 / +22 (Jan→May 2016) | +11 / +21 | +35 / +48 | −7 / +8 | −9 / −2 | −2 / +1 | Yes. EWZ +144% vs EEM +74% Jan-2016→Jan-2018, with much of it before t0 |
| Brazil – Bolsonaro/Guedes | Elected 28 Oct 2018; pension reform passed 2019 (t0 = Oct-2018) | EWZ (TR) | +33 / +25 (May→Oct 2018) | +3 / +2 | −43 / −44 | −5 / −20 | n/a | −27 / −30 | Fully priced before; the pension reform itself brought no lasting edge |
| Japan – Stewardship Code | Feb 2014 (Abenomics began Nov 2012) | EWJ (TR) vs EEM / EFA | +23 / −4 | +2 / +8 | +12 / +18 | +5 / +14 | +38 / +14 | +19 / +18 (vs SPY −48) | Gradual |
| Japan – Corporate Governance Code | Jun 2015 | EWJ (TR) | +15 / +13 | +3 / +1 | +2 / +3 | +3 / +5 | +14 / −8 | +10 / +4 | Mostly priced before (2014–15) |
| Japan – TSE "cost of capital / P/B" request | 31 Mar 2023 (t0 = Mar-2023) | EWJ (TR) | +8 / −3 | +16 / +8 | +1 / +5 | n/a | n/a | 0 / +12 (vs SPY −6) | Most of the edge came after, in year 1 |
| US – TCJA | Election Nov 2016; signed 22 Dec 2017 (t0 = Dec-2017) | SPY (TR) vs EFA / EEM | +2 / −2 (Oct-16→Dec-17) | +11 / +13 | +31 / +26 | +45 / +74 | n/a | +71 / +91 | Little visible pre-pricing relative to others; later outperformance is confounded by US mega-cap tech |
| Greece – 3rd bailout / capital controls | Bailout agreed Jul 2015 (t0 = Jul-2015) | GREK | −23 / −29 | −21 / −21 | −21 / −22 | −42 / −48 | +58 / −5 | +63 / +10 | No. The bottom was Feb-2016 and real gains came 4–10 years later |
| Greece – Mitsotakis (ND) | Elected 7 Jul 2019 (t0 = Jul-2019) | GREK | +20 / +15 (Apr→Jul 2019) | −35 / −36 (COVID) | −14 / −32 | +44 / −4 | n/a | +85 / +37 | Short pre-run, then a slow payoff (investment-grade upgrade 2023, per general knowledge) |
| Indonesia – Jokowi | Elected Jul 2014 (t0 = Jul-2014) | EIDO | +5 / +4 | −4 / −19 | −3 / −14 | −3 / −25 | −26 / −62 | −72 / −84 | Pre-run then a decade of underperformance. EIDO −34% vs EEM +34% Aug-2025→Sep-2026 |
| Saudi – Vision 2030 | Announced 25 Apr 2016 (t0 = Apr-2016) | KSA | −2 / −1 | −12 / −9 | +14 / +10 | −1 / −11 | −13 / −39 | −23 / −46 | No lasting reward |
| Vietnam – Resolution 68 (private sector) + FTSE upgrade | Res. 68 May 2025; FTSE upgrade announced 7 Oct 2025 (t0 = Apr-2025) | VNM | −7 / −10 (Apr-24→Apr-25) | +7 / +21 | n/a | – | – | −8 / +3 | Gains came after t0 (Apr→Dec 2025 +58% vs EEM +25%) and faded after the upgrade (Dec-25→Sep-26 −11% vs EEM +22%) |
| South Africa – Ramaphosa ("Ramaphoria") | ANC leadership Dec 2017 (t0 = Dec-2017) | EZA | +7 / +9 (one month) | −13 / −19 | −43 / −50 | −25 / −49 | n/a | −36 / −58 | Spike at the event, then sustained underperformance |
| South Africa – Government of National Unity (GNU) | May-2024 election → GNU (t0 = May-2024) | EZA | −1 / −3 | +18 / +16 | n/a | – | – | −1 / +10 | Edge came after the event, then faded |
| Turkey – return to orthodox policy | Post-election pivot Jun 2023 (t0 = May-2023) | TUR | +59 / +43 (May-22→May-23) | +27 / +15 | −30 / −27 | n/a | – | −36 / −36 | Run-up came before, then a long fade |
| Chile – Kast (pro-market) | Runoff 14 Dec 2025 (t0 = Dec-2025) | ECH | +13 / +17 (Jun→Dec 2025) | n/a | – | – | – | −23 / −17 (9 months) | Yes. "Buy the rumor, sell the news" |

All rows: [Computed](reform_case_studies_data/episodes.py), data in [monthly_prices.csv](reform_case_studies_data/monthly_prices.csv).

#### Annualized USD returns for the long-running episodes (t0 → Sep-2026)
- **Japan governance** (Feb-2014 →): EWJ 8.0%/yr total return, vs EFA 6.6%/yr and SPY 13.8%/yr — [Computed](reform_case_studies_data/episodes.py)
- **India** (May-2014 →): INDA 4.1%/yr price, vs EEM 3.7%/yr and ACWI 8.2%/yr — [Computed](reform_case_studies_data/episodes.py)
- **Greece** (Jul-2015 →): GREK 10.1%/yr price — [Computed](reform_case_studies_data/episodes.py)
- **Argentina, Macri** (Nov-2015 →): ARGT 15.0%/yr price — [Computed](reform_case_studies_data/episodes.py)
- **Argentina, Milei** (Nov-2023 →): ARGT 20.8%/yr price — [Computed](reform_case_studies_data/episodes.py)
- **Saudi** (Apr-2016 →): KSA 4.0%/yr price — [Computed](reform_case_studies_data/episodes.py)

#### Older pro-market episodes (pre-ETF; mostly local-currency or partial USD evidence)
- **UK, Thatcher (1979–1990)**
  - The FTSE All-Share returned 11.79% a year (annualized, sterling) over 1979–1990, which a Fidelity study called the best UK boom in 50 years. No USD or relative-to-world figure was found. — [CNBC](https://www.cnbc.com/id/100627094)
  - A different source gives about 17.4% a year average with no method stated. Unverified; it conflicts with the CNBC/Fidelity figure. — [Hindesight Substack](https://hindesight.substack.com/p/are-conservative-governments-better)
  - The Oct 1979 abolition of exchange controls removed all restrictions on capital movement. Ministers partly expected it to weaken sterling. — [Prospect Magazine](https://www.prospectmagazine.co.uk/ideas/economics/67236/thatchers-mistake-london-stock-exchange)
- **US, Reagan (ERTA signed Aug 1981)**
  - S&P 500 total return in USD from Aug-1981: 1y −10%, 3y +47%, 5y +138%, 10y +345%. Real returns: −15%, +30%, +100%, +201%.
  - From the Nov-1980 election: 1y −5%, 3y +42%, 5y +85%, 10y +248%.
  - The 12 months before the election returned +38%.
  - Computed from Shiller monthly data (monthly-average prices plus dividends/12). There is no world benchmark for this period in the data, so the relative return is a gap. — [Computed from data/macro/shiller.csv](../../../data/macro/shiller.csv)
- **New Zealand (Rogernomics, 1984 onward)**
  - The 1984 Labour government's deregulation (floating dollar, financial deregulation) fueled a share boom. By July 1987 more than 40% of adults owned shares. The market peaked on 18 Sep 1987. — [Te Ara](https://teara.govt.nz/en/stock-market/page-5)
  - By the end of Feb 1988 the market had fallen almost 60% from its peak. "On a capital index basis… the local stock exchange has never topped its 1987 peak." — [NZ Herald](https://www.nzherald.co.nz/indepth/business/1987-stock-market-crash/)
  - Investors deserted the market, which languished until the early 2000s. — [NZ History](https://nzhistory.govt.nz/page/black-tuesday-share-market-crash)
  - The boom priced in reform and speculation early; the reforms themselves continued to 1990 and beyond.
- **Mexico (Salinas reforms 1988–94, and the 1994 peso crisis)**
  - $22bn of foreign portfolio money flowed in during 1991–93, and the Bolsa index rose 436% in USD over 1990–93. The same source dates "the seeds of the crisis" to the 1988 decision to peg the peso. — [Cato Journal, "Mexican Monetary Lessons" (mirror)](https://cs.uwaterloo.ca/~alopez-o/politics/cj17n1-4.html) (attribution inferred from the search summary)
  - The Mexican stock market fell by two-thirds in USD between 19 Dec 1994 and its low on 9 Mar 1995. The devaluation was announced on 20 Dec 1994. — [Federal Reserve Bulletin, 1996](https://www.federalreserve.gov/pubs/bulletin/1996/396lead.pdf)
  - In nominal pesos the Bolsa fell about 39% from end-1994, so the currency did most of the damage to USD investors. — [search summary of GAO / Fed sources](https://www.gao.gov/assets/ggd-96-56.pdf)
- **Chile (1975 onward)**
  - The 1981 move to a funded pension system is "considered to have contributed to" Chile's strong performance from the mid-1980s. — [IMF WP (Holzmann 1996)](https://www.imf.org/en/publications/wp/issues/2016/12/30/pension-reform-financial-market-development-and-economic-growth-preliminary-evidence-from-1925)
  - Pension funds averaged a little over 10% real (in pesos) over the system's first 25 years. — [BBVA Research](https://www.bbvaresearch.com/wp-content/uploads/migrados/WP_0805_tcm348-212950.pdf)
  - **No USD equity index series for Chile in 1975–1990s was found.**
- **India 1991**
  - Reforms began in July 1991. The Sensex rose about 94% between 24 Jul 1991 and 28 Feb 1992, and about 82% in calendar 1991 (local currency). — [Business Standard](https://www.business-standard.com/article/specials/india-at-75-18-biggest-moments-for-indian-markets-from-1947-to-1993-122081001546_1.html); [HDFC Sky](https://hdfcsky.com/news/80-years-10-major-market-crashes-the-shocks-that-tested-independent-india)
  - The Sensex closed at 4,091 on 30 Mar 1992. — [Wikipedia: BSE SENSEX](https://en.wikipedia.org/wiki/BSE_SENSEX)
  - It fell 12.77% on 28 Apr 1992 as the Harshad Mehta scam emerged, and another 23% in May. — [HDFC Sky](https://hdfcsky.com/news/80-years-10-major-market-crashes-the-shocks-that-tested-independent-india)
  - Foreign institutional investors were allowed in only from Sep 1992, so the 1991–92 boom was a domestic rally that foreign investors could not easily capture. — [Business Standard](https://www.business-standard.com/article/specials/india-at-75-18-biggest-moments-for-indian-markets-from-1947-to-1993-122081001546_1.html)
- **El Salvador (2019–2026)**
  - There is no investable equity market, so sovereign USD bonds are the proxy.
  - The dollar bonds were the best performers in EM in 2023: about +24–28% by April 2023 (Bloomberg data), and more than 70% for the full year. — [El Salvador in English, citing Bloomberg](https://elsalvadorinenglish.com/2023/04/19/el-salvadors-bonds-have-the-best-performance-in-emerging-markets-according-to-bloomberg/); [FXStreet](https://www.fxstreet.com/amp/cryptocurrencies/news/el-salvadors-bitcoin-bet-pays-off-as-bonds-surge-62-alongside-btc-rally-202307201426)
  - In Aug 2024 the bonds were EM's biggest gainers after the IMF announced "preliminary understandings". — [Bloomberg, 6 Aug 2024](https://www.bloomberg.com/news/articles/2024-08-06/imf-says-progress-made-toward-reaching-accord-with-el-salvador)
  - The 2029s went from 88 cents (mid-April 2024) to 105 (mid-December 2024). A later report puts spreads at the tightest since 2010. — [Briefs.co](https://www.briefs.co/news/el-salvador-s-imf-deal-gets-moving-again-and-bond-investors/)
  - The bond rally was driven by debt management (paying the Jan-2023 eurobond) and the IMF deal, not by economic-freedom reforms as such. — [Bloomberg Línea](https://www.bloomberglinea.com/english/el-salvador-payment-to-clear-first-2023-hurdle-for-distressed-emerging-markets/)

#### Japan detail (ongoing)
- **2023–2026 returns.** The TOPIX (including dividends) has risen more than 20% for four consecutive years since 2023. Some foreign investors still see governance as a stock-picking theme because ROE has improved only modestly. — [Daiwa AM, Jul 2026](https://www.daiwa-am.co.jp/english/market-outlook/20260713_01.pdf)
  - TOPIX Net Total Return was +111% over the 3 years and 4 months to end-April 2026 (yen). — [Lion Global Investors](https://www.lionglobalinvestors.com/en/insights/2026-japan-market-outlook.html)
  - TOPIX total return was above 20% in USD year-to-date as of 10 Dec 2025. — [Janus Henderson](https://www.janushenderson.com/middle-east/institutional/article/will-strong-earnings-growth-and-policy-credibility-drive-japanese-stocks-higher-in-2026/)
  - EWJ (USD total return) gained +21% from Dec-2025 to Sep-2026, vs EFA +10% and SPY +13%. — [Computed](reform_case_studies_data/episodes.py)
  - JPMorgan raised its end-2026 TOPIX target to 4,600, citing governance and foreign inflows. — [roic.ai, 17 Aug 2026](https://www.roic.ai/news/jpmorgan-raises-2026-year-end-target-for-japans-topix-to-4600-08-17-2026)
- **Currency effect.** From Dec-2020 to Jun-2024, EWJ (unhedged, USD total return) gained +7% while DXJ (yen-hedged WisdomTree Japan, price-only) gained +107%. From Mar-2023 to Sep-2026: EWJ +82% vs DXJ +155%. DXJ tracks a different, exporter-tilted index, so this overstates the pure FX effect, but the direction is unambiguous. — [Computed](reform_case_studies_data/episodes.py)

#### Argentina detail (ongoing)
- **2025 midterm.** On 27 Oct 2025, after Milei's midterm win, the Merval jumped 22% and the Global X MSCI Argentina ETF (ARGT) rose 19%, its best day on record. — [CNN, 27 Oct 2025](https://edition.cnn.com/2025/10/27/business/argentina-stock-market-milei-party-win)
- **Latest (late Sep 2026).** The S&P Merval is down 9% in USD year-to-date, while the MSCI Latin America index is up more than 20%. Only Vaca Muerta energy names show strong gains. — [Buenos Aires Times](https://www.batimes.com.ar/news/economy/argentinas-stock-rally-narrows-to-oil-as-rest-of-economy-slows.phtml)
- **Valuation.** The Merval trades at 19.8x forward earnings vs 13.4x for Brazil's Ibovespa, as earnings growth has lagged. — [Buenos Aires Times](https://www.batimes.com.ar/news/economy/argentine-stocks-are-left-behind-as-earnings-growth-eludes-milei.phtml)
- **MSCI review (mid-2026).** MSCI kept Argentina in its lowest ("standalone") tier, citing remaining currency controls, and bank stocks that had rallied on upgrade hopes reversed. — [Rio Times](https://www.riotimesonline.com/argentina-msci-standalone-decision-banks-fall-2026/); [Advisor Perspectives / Bloomberg, 4 Jun 2026](https://www.advisorperspectives.com/articles/2026/06/04/druckenmiller-leads-wall-streets-return-argentine-stocks)
- **ETF flows.** About $630m flowed into the MSCI Argentina ETF in 2024 and about $200m flowed out in 2025. — [search summary of Rio Times / Seeking Alpha](https://www.riotimesonline.com/why-argentinas-stock-exchange-soared-and-then-slumped-in-2025/) (unverified)
- **Calendar-year ARGT price returns:**

  | 2016 | 2017 | 2018 | 2019 | 2023 | 2024 | 2025 | 2026 YTD (to Sep) |
  |---|---|---|---|---|---|---|---|
  | +28% | +53% | −34% | +13% | +51% | +61% | +11% | −6% |

  — [Computed](reform_case_studies_data/episodes.py)

#### Vietnam detail (ongoing)
- **FTSE upgrade.** FTSE Russell announced on 7 Oct 2025 that Vietnam moves from Frontier to Secondary Emerging, effective 21 Sep 2026 and subject to a March 2026 interim review. The non-pre-funding trading model from late 2024 was a key enabling reform. — [Vietnam Briefing](https://www.vietnam-briefing.com/news/vietnam-reclassified-to-emerging-market-status-by-ftse-russell.html/)
- **2025 rally.** The VN-Index returned 57.7% (price, VND) year-to-date as of 30 Sep 2025. — [LSEG / FTSE Russell](https://www.lseg.com/en/insights/ftse-russell/vietnam-the-asean-powerhouse)
- **2026 underperformance.** The VN-Index has lagged regional peers for much of 2026. — [The Vietnam Yield](https://thevietnamyield.com/ftse-vietnam-upgrade/); [Trading Economics](https://tradingeconomics.com/vietnam/stock-market)

### Inferences
- **Hit rate falls with horizon.** Counting the pro-market rows above against EM (EFA for the US), the share outperforming is about 11/16 at 1 year, 7/13 at 3 years and 5/11 at 5 years. Reform "wins" are most reliable over the first year and close to a coin flip after that. The sample is small, overlapping and hand-picked.
- **Beating EM is not beating World.** Many reforms beat EM but not ACWI or the S&P 500. ACWI's 2014–2026 return was dominated by US mega-cap tech. India is the clearest case: 10 years after May 2014 it was +90% relative to EEM but only +1% relative to ACWI.
- **The headline ARGT numbers overstate "Argentina".** ARGT tracks MSCI All Argentina 25/50, which includes MercadoLibre at a large weight (general knowledge, unverified this session). The Macri-era 10-year +393% is largely MercadoLibre. The Merval in USD (CCL, the parallel exchange rate implied by cross-listed shares) is the better gauge of Argentina itself, and I could not get that series.
- **The older famous episodes show the same pattern as the modern ones:**
  - NZ 1984–87 boomed early, then crashed and did not recover in capital terms for decades.
  - Mexico 1990–93 gained 436% in USD, then lost two-thirds in three months.
  - India 1991–92 boomed, then crashed after the scam.
  - Reforms became visible, local markets overshot, then a currency or financial shock took back a large part of the gains.

### Gaps
- **No USD, MSCI-relative returns for the pre-ETF episodes:** UK 1979–90, US 1981 relative to the world, NZ, Chile 1975–90s, Mexico 1988–89, India 1991 in USD, Poland 1990s, Estonia, Peru 1990s, Brazil 1994 Real Plan, Indonesia before 2010, Vietnam Doi Moi (no stock exchange until 2000, general knowledge). MSCI index histories and the IFC/S&P EMDB data were not reachable (WebFetch DNS failures; search budget exhausted).
- **Unsourced events and causes:**
  - Resolution 68 (Vietnam) details are not sourced.
  - The cause of Indonesia's 2025–26 slump (EIDO −34% vs EEM +34%) is not sourced. General knowledge points to the Sep-2025 finance-minister change, the Danantara sovereign fund and MSCI free-float concerns, all unverified.
  - The US 1980s relative performance (US vs EAFE) is not sourced.
- **No Merval-in-USD series** for Macri (2015–19), Milei (2023–26) or the Aug-2019 PASO day. Reported figures were not retrievable.
- **Estonia and Poland:** no data or sources found.

---

## 2. Anti-market episodes: policy, timing, and USD equity performance

### Takeaway
Anti-market turns usually hit USD investors fast, with event-day or event-month falls of 12–30% (Venezuela 2007, Yukos 2003, Argentina 2008 and 2019, China 2021, Turkey 2018/2021, Mexico 2024, Peru 2021). Over 1–5 years they produce large underperformance (China −34% relative to EM over 5 years, Turkey −44% over 3 years, Zuma-era South Africa −28% relative to World over his tenure while roughly matching EM). The worst case is total loss of foreign access (Russia 2022 at "effectively zero"; Venezuela). But anti-market *fears* often overshoot and reverse (Brazil 2002, Mexico 2018). The UK 2022 mini-budget was punished within days and the damage reversed once the policy was withdrawn.

### Cited Findings

#### Case table: anti-market episodes (USD, price-only unless TR; rel. vs EEM / ACWI)
| Episode | Policy / trigger (t0) | Vehicle | Event / short-window move | 1y rel | 3y rel | 5y rel | t0 → Sep-2026 rel | Priced early? |
|---|---|---|---|---|---|---|---|---|
| China – regulatory crackdown | Ant IPO halted 3 Nov 2020; Didi and private-tutoring bans Jul 2021 (t0 = Oct-2020) | MCHI / KWEB / FXI | Pre-crackdown boom: MCHI +27 rel, KWEB +52 rel (Oct-19→Oct-20). Peak-to-trough Feb-21→Oct-22: MCHI −59%, KWEB −79% (EEM −36%, ACWI −8% from Jan-21) | MCHI −22 / −34; KWEB −42 / −51 | MCHI −34 / −53; KWEB −56 / −69 | MCHI −34 / −55; KWEB −55 / −69 | MCHI −55 / −67; KWEB −77 / −83 | No. Peak month was Dec-2020, after the Ant halt, and the market fell in steps with each new measure |
| Turkey – unorthodox monetary policy | 2018 lira crisis; rate cuts Sep–Dec 2021 (t0 = Dec-2017) | TUR | Aug-2018: −28% in one month. Sep–Dec 2021: −22% vs EEM −7% | −32 / −36 | −44 / −52 | +6 / −28 | −45 / −65 | Partly. Dec-2017→May-2023: TUR −30% vs EEM −19%, ACWI +27%; May-2013→May-2023 TUR −56% vs EEM −7% |
| South Africa – Zuma era | May 2009 → Feb 2018 | EZA | Finance minister Nene fired, Dec 2015: −13% vs EEM −5% in the month | +2 / +5 | +14 / +8 | +10 / −17 | Tenure: EZA +49% vs EEM +44%, ACWI +106% | Slow-burn. Roughly matched EM; about −28% relative to World over the tenure |
| Argentina – A. Fernández (Peronist return) | PASO 11 Aug 2019 (t0 = Aug-2019) | ARGT | Aug-2019 −31% in the month | – | – | – | Aug-19→Jul-23: ARGT +109% vs EEM +4% (MercadoLibre-distorted) | Event crash was immediate |
| Mexico – AMLO | Elected Jul 2018 (airport cancellation Oct 2018) (t0 = Jul-2018) | EWW | — | −15 / −21 | −18 / −32 | +34 / −8 | −8 / −37 | Fear overshot; recovered by year 5 ("super peso", nearshoring) |
| Mexico – Sheinbaum supermajority / judicial reform | 2 Jun 2024 election | EWW | −13% vs EEM +2% (May→Jun 2024) | −15 (May-24→May-25: −7% vs EEM +9%) | n/a | – | – | Immediate |
| Peru – Castillo | Apr–Jul 2021 election | EPU | −21% vs EEM −3% (Mar→Jul 2021) | – | – | – | – | Immediate |
| Chile – protests / constitutional rewrite | Oct 2019 (t0 = Oct-2019) | ECH | −8% in the month | −34 / −33 | −11 / −35 | −29 / −52 | −30 / −48 | Immediate; Nov-2021→Sep-2022 (Boric win → constitution rejected) ECH −5% vs EEM −29% (relief rally) |
| Brazil – Lula 2002 "fear" (counterexample) | Polls Apr–Sep 2002 | EWZ (TR) | −56% (Apr→Sep 2002) | then +203% (Sep-02→Dec-03) | — | +1,518% (Sep-02→Oct-07) | – | Fear overshot massively |
| UK – mini-budget | £45bn unfunded tax cuts, 23 Sep 2022 | EWU (TR) vs EFA / SPY | 22→27 Sep: EWU −7.6% vs EFA −5.3%, SPY −2.9% | 1y: EWU +19.4% vs EFA +21.9% | – | – | – | Punished within 2 trading days; relative loss erased by 31 Oct (EWU +1.1% vs EFA +1.2%) after the reversal |

All rows: [Computed](reform_case_studies_data/episodes.py).

#### Web-sourced details
- **Venezuela (Chávez from 1999; nationalization wave 2007)**
  - When Chávez announced nationalization of "strategic" sectors in Jan 2007, the Caracas IBC index fell 19%. CANTV closed −30% and Electricidad de Caracas −20%, and trading in both was suspended for 48 hours. — [Al Jazeera, 9 Jan 2007](https://www.aljazeera.com/news/2007/1/9/chavez-speech-hits-stock-values)
  - The bolívar traded at more than 4,100 per USD on the parallel market vs the 2,150 official peg, which matters more than the local index for USD returns. — [NBC News](https://www.nbcnews.com/news/amp/wbna16542519)
  - CANTV ADRs plunged in New York after Chávez said shareholders would not be paid market value. — [NBC News](https://www.nbcnews.com/id/wbna16751924); [CFR](https://www.cfr.org/articles/venezuelas-turn-toward-socialism-hugo-chavez-plans-nationalize-cantv-and-edc)
  - I could not confirm the date of Venezuela's MSCI removal.
- **Argentina, Kirchners (2003–2015)**
  - The Oct-2008 pension-fund nationalization took the Merval down 29% in three days to 865, and down nearly 60% for 2008. This comes from a partisan source. — [WSWS](https://www.wsws.org/en/articles/2008/10/arge-o24.html)
  - YPF expropriation: the government moved on 16 Apr 2012. The IESE case reports a 29% drop in YPF shares the next day. This seems large vs my recollection of the ADR move, so verify it. — [IESE case WP-1055](https://www.iese.edu/media/research/pdfs/WP-1055-E.pdf)
  - Official inflation data were falsified in 2007–2015 (independent estimates above 20–25% vs official below 11%), which complicates any real or USD analysis. — [Halley Substack](https://halleytech.substack.com/p/argentinas-perpetual-default-cycle-the-politics-of-debt); [Grokipedia](https://grokipedia.com/page/Presidency_of_Cristina_Fern%C3%A1ndez_de_Kirchner)
  - Counterpoint: ARGT rose +29% from Jun-2012 to Oct-2015 vs EEM −11% and ACWI +32%, as markets bet on the end of Kirchnerism. — [Computed](reform_case_studies_data/episodes.py)
- **Russia (2000s → 2022)**
  - The RTS index (USD-denominated) went from an all-time low of about 38 (5–6 Oct 1998) to a peak of about 2,488 (19 May 2008), roughly 65x by my arithmetic. — [bne IntelliNews](https://www.intellinews.com/datacrunch-the-anatomy-of-1998-2008-and-2022-stock-market-crashes-238607/); [Mondo Visione](https://m.mondovisione.com/news/rts-index-celebrates-25-years-202091/)
  - After Khodorkovsky's arrest (25 Oct 2003), the RTS fell about 12.4% the next Monday, then partly recovered (+6.33% on 3 Nov). — [RFE/RL](https://www.rferl.org/a/1341591.html); [Goriaev & Sonin](https://www.bayes.citystgeorges.ac.uk/__data/assets/pdf_file/0011/78761/Goriaev-Sonin0907.pdf)
  - Despite Yukos, the market quintupled again by 2008, because commodities dominated.
  - In 2022 MSCI reclassified Russia to standalone effective 9 Mar 2022 at "effectively zero" value; FTSE deleted it on 7 Mar. — [ETFdb](https://etfdb.com/emerging-markets-content-hub/msci-removes-russian-securities-from-em-indexes/); [Investment Executive](https://www.investmentexecutive.com/news/markets/msci-ftse-russell-to-remove-russia-from-indexes/)
  - Russia had been about 1.5% of MSCI EM. — [Fund Selector Asia](https://fundselectorasia.com/index-providers-ditch-russia-stocks/)
- **Turkey**
  - The foreign share of Borsa Istanbul market value was in the 60% range until early 2020 and fell below 50% in Jul 2020. — [bne IntelliNews](https://www.intellinews.com/turkey-insight-the-puzzle-of-borsa-istanbul-s-foreign-held-shares-boom-175192)
  - Foreign holdings of lira bonds fell to under 1% from 10% in 2019. — [Al-Monitor, Aug 2023](https://al-monitor.com/originals/2023/08/foreign-investors-buy-179m-turkeys-stocks-amid-erdogans-economic-reset)
  - After the May-2023 elections, rate hikes and foreign buying took BIST-100 up 61% (in lira) by Aug 2023. — [Al-Monitor](https://al-monitor.com/originals/2023/08/foreign-investors-buy-179m-turkeys-stocks-amid-erdogans-economic-reset)
  - BIST-100 2023: +35.6% nominal in lira, but −18% real. — [TR Monitor](https://www.trmonitor.net/insurance-was-the-star-of-borsa-istanbul-in-2023/)
  - TUR (USD) 2023: −13% vs EEM +6%. — [Computed](reform_case_studies_data/episodes.py)
- **UK mini-budget 2022**
  - Sterling hit a record low of about 1.0350 per USD. — [Investec](https://www.investec.com/en_gb/focus/fx-insights/this-time-its-different.html)
  - Gilt yields rose from about 3.8% to 5% in three trading days. The BoE launched temporary, unlimited (framed as £65bn) long-gilt purchases on 28 Sep. — [ii.co.uk](https://ii.co.uk/analysis-commentary/bank-england-intervenes-end-bond-market-panic-ii525453)
  - The 30-year gilt hit a 20-year high on 27 Sep. Yields tumbled when Chancellor Hunt scrapped most of the package on 17 Oct. — [CNBC, 21 Oct 2022](https://www.cnbc.com/2022/10/21/3-charts-showing-the-market-turmoil-wreaked-during-uk-pm-truss-tenure.html)

### Inferences
- **Speed and size of the hit.** Anti-market events are mostly not pre-priced and the market responds in days. China's Dec-2020 peak came after the Ant halt; Turkey and Peru moved within the month. The 1–5 year USD damage is large and persistent where the policy persists: China −55% and Turkey −45% relative to EEM to date.
- **Currency is the main channel in USD terms.** Turkey 2023 and Mexico 1994–95 both show it (details in section 3).
- **Fear vs actual policy.** When the feared policy does not arrive or is diluted, it pays to buy the fear. Brazil 2002–07, Mexico 2018–23 and Chile 2019–22 (relief rally when the constitution was rejected) show this. When the policy is real and sustained (China 2021, Turkey 2018–23, Venezuela, Russia 2022), it does not pay, and the tail includes total loss of access.
- **The UK 2022 case is the cleanest "market discipline" example.** The relative loss was about 2.4% vs EFA at the worst point, then erased within five weeks once the policy was withdrawn. The gilt and FX moves were much larger than the equity move; FTSE constituents earn much of their revenue in USD.

### Gaps
- No USD index series for Venezuela (IBC adjusted by the parallel rate) or for Argentina 2003–2011 (ARGT data in this session start Jun-2012).
- No sourced figure for the market value lost in China's crackdown (USD trillions). The search budget ran out before I could retrieve it.
- No USD BIST-100 series for 2018–2023 from a web source; the TUR ETF is used instead.
- No ERUS/RSX data (both delisted, not found in Robinhood). MSCI Russia's 2000–2021 USD returns relative to EM are not sourced.

---

## 3. How large were currency effects, and did reforms that markets loved later reverse?

### Takeaway
Currency is often the dominant term for a USD investor. It turned double-digit local gains into USD losses in Turkey and Mexico 1994–95, and it roughly halved Japan's governance-era returns for unhedged USD holders. Reversals of loved reforms are common. Argentina 2018–19 is the canonical case (ARGT −41% from the Jan-2018 peak to Aug-2019, −31% in the PASO month). The Milei trade has also given back all of its EM-relative gains since the Oct-2025 midterm spike.

### Cited Findings
- **Mexico 1994–95.** The Bolsa fell about 39% in pesos but about two-thirds in USD (19 Dec 1994 to 9 Mar 1995). — [Federal Reserve Bulletin 1996](https://www.federalreserve.gov/pubs/bulletin/1996/396lead.pdf); [GAO](https://www.gao.gov/assets/ggd-96-56.pdf)
- **Turkey 2023.** BIST-100 was +35.6% in lira (−18% real), while TUR in USD was −13% vs EEM +6%. — [TR Monitor](https://www.trmonitor.net/insurance-was-the-star-of-borsa-istanbul-in-2023/); [Computed](reform_case_studies_data/episodes.py)
  - From May-2013 to May-2023, TUR fell −56% in USD vs EEM −7%. — [Computed](reform_case_studies_data/episodes.py)
- **Japan.** From Dec-2020 to Jun-2024, unhedged EWJ (USD total return) gained +7% vs yen-hedged DXJ +107%. From Oct-2012 (Abenomics) to Sep-2026: EWJ +247% vs DXJ +467% (DXJ is a different, exporter-tilted index). — [Computed](reform_case_studies_data/episodes.py)
- **Argentina.** One report says a 29% Merval gain in pesos over 12 months translated into a far smaller USD return after about 30% peso depreciation (date unclear). — [Rio Times](https://www.riotimesonline.com/how-to-invest-in-argentina-as-a-foreigner-2026/)
- **Venezuela 2007.** The parallel exchange rate (more than 4,100) was nearly double the official one (2,150), so the official-rate USD conversion overstated USD returns. — [NBC News](https://www.nbcnews.com/news/amp/wbna16542519)
- **UK 2022.** Sterling fell to about 1.035; USD-based EWU fell 7.6% vs EFA −5.3% over 22–27 Sep. — [Investec](https://www.investec.com/en_gb/focus/fx-insights/this-time-its-different.html); [Computed](reform_case_studies_data/episodes.py)
- **Argentina 2018–19 reversal.** ARGT doubled from Nov-2015 to Jan-2018 (+102% vs EEM +50%). It then fell −41% to Aug-2019; the Aug-2019 month (PASO primary won by the Fernández/Kirchner ticket) was −31%. ARGT fell −34% in calendar 2018. — [Computed](reform_case_studies_data/episodes.py)
  - Brookings (Sturzenegger) gives the Macri-era macro post-mortem: gradualist fiscal adjustment, the 2018 sudden stop and the IMF program. — [Brookings, Sturzenegger 2019/2020](https://www.brookings.edu/wp-content/uploads/2020/10/Sturzenegger-final-draft.pdf)
- **Argentina 2025–26 fade.** ARGT +35% in Oct-2025, then −9% Oct-2025→Sep-2026 vs EEM +21%. Its peak monthly close was Jan-2026 (98.2); it was 86.2 at end-Sep 2026. — [Computed](reform_case_studies_data/episodes.py)
  - The Merval is −9% in USD YTD as of late Sep 2026. — [Buenos Aires Times](https://www.batimes.com.ar/news/economy/argentinas-stock-rally-narrows-to-oil-as-rest-of-economy-slows.phtml)
  - MSCI kept Argentina standalone over currency controls. — [Rio Times](https://www.riotimesonline.com/argentina-msci-standalone-decision-banks-fall-2026/)
- **Other reversals of "loved" reforms** — all [Computed](reform_case_studies_data/episodes.py):
  - Brazil after the Bolsonaro/Guedes pension reform: 3y −43% relative to EEM.
  - Turkey after the orthodox pivot: +27% relative in year 1, then −30% relative at 3 years.
  - Vietnam after the FTSE upgrade announcement: Dec-2025→Sep-2026 −11% vs EEM +22%.
  - Indonesia (Jokowi-era reform narrative, then the 2025–26 shock): −72% relative to EEM since Jul-2014.
- **Japan currency backdrop.** USD/JPY moved from about 80 (2012) to about 160 (mid-2024). This is general knowledge, not sourced this session.

### Inferences
- A thesis based on economic freedom needs an explicit currency view, or a hedge where it is cheap (Japan, where the hedge earns the rate differential). In high-inflation EMs (Turkey, Argentina), the currency can wipe out nominal local equity gains even when the reform is real.
- **Reversals usually come from macro-financial fragility, not from reform being undone first.** Argentina 2018 (sudden stop), Mexico 1994 (peg plus tesobonos) and Brazil 2020 (COVID and BRL) all fit; the political reversal (Argentina's 2019 PASO) followed the economic stress.
- **Reform credibility is tested at elections.** Argentina 2019, Chile 2019 and Mexico 2024 all show large event-month moves. Holding a reform trade through elections carries binary risk.

### Gaps
- No complete decomposition (local return vs FX) for any episode. FX series (USD/ARS CCL, USD/TRY, USD/JPY, USD/MXN) could not be downloaded, because outbound data hosts were blocked (Yahoo, Stooq, World Bank and FRED all rejected).
- No sourced Merval-USD drawdown for the 12 Aug 2019 PASO day (widely cited as about −48% in USD; unverified).

---

## 4. Pattern: "buy when reform becomes credible" vs "the gains came before the policy was obvious"

### Takeaway
The evidence supports both, in sequence.
- **Before:** a large part of the re-rating usually happens before the policy is obvious. Henry (2000) finds abnormal returns of about 3.3%/month in real USD over the 8 months before liberalization. Milei's pre-runoff year was +53% relative to EM, and India's 2013–14 run-up was +25% relative to EM.
- **After:** buying at the moment of credibility (election or announcement) still earned a positive EM-relative premium in year 1 in about two-thirds of modern cases.
- **Later:** that premium decays and frequently reverses by years 3–5, unless the reform is backed by sustained macro stability and earnings growth (Greece after 2019, Japan after 2023 when hedged, India 2014–2024).

### Cited Findings
- **Henry (2000), *Journal of Finance*.** In 12 emerging markets, the aggregate equity index earned abnormal returns of about 3.3% a month in real USD during the 8 months before the initial stock-market liberalization. That is roughly 26% cumulative by simple arithmetic. Henry ties it to a lower cost of capital through risk sharing. — [IDEAS/RePEc](https://ideas.repec.org/a/bla/jfinan/v55y2000i2p529-564.html); [Stanford GSB](https://www.gsb.stanford.edu/faculty-research/working-papers/stock-market-liberalization-economic-reform-emerging-market-equity)
- **Henry (2002), "Is Disinflation Good for the Stock Market?", *Journal of Finance*.** Across 81 stabilization episodes, the stock market rose about 24% in real USD when pre-stabilization inflation was above 40%. Below 40% the average response was about zero and not significant. Stock reactions predicted next-year changes in inflation and output. — [Stanford GSB](https://www.gsb.stanford.edu/faculty-research/working-papers/disinflation-good-stock-market); [NYU archive](https://archive.nyu.edu/handle/2451/31388)
- **Bekaert & Harvey (2000).** The cost of capital falls by 5–75 bp after liberalization (as summarized in a later paper). — [Zemel & Zhang 2018 (Applied Economics Letters)](https://research.pomona.edu/michelle-zemel/files/2018/10/ZemelZhang_Applied_Economics_Letters_2018.pdf)
- **Robustness challenge.** A critique finds earlier event-study results "very sensitive to alternative definitions of precise liberalisation event dates". — [Oxford QEH working paper (Durham)](https://www.qeh.ox.ac.uk/sites/default/files/pdf_docs/qehwps51.pdf) (attribution via search summary)
- **Pre-event run-ups in this sample** (relative to EEM; India also relative to ACWI) — all [Computed](reform_case_studies_data/episodes.py):

  | Episode | Window | Run-up |
  |---|---|---|
  | Argentina, Milei | Nov-22→Nov-23 | +53% |
  | Argentina, end of Kirchnerism | Jun-12→Oct-15 | ARGT +29% vs EEM −11% |
  | India, Modi | Aug-13→May-14 | +25% (+19% vs ACWI) |
  | Brazil, Temer | Jan→May 2016 | +18% |
  | Brazil, Bolsonaro | May→Oct 2018 | +33% |
  | Chile, Kast | Jun→Dec 2025 | +13% |
  | Turkey, orthodox pivot | May-22→May-23 | +59% |

- **Pre-event declines.** Greece 2015 (−23%), Saudi 2016 (−2%) and Vietnam 2025 (−7%) had no run-up. Greece and Saudi then lagged EEM for years (Greece −42% at five years). Vietnam beat EEM by 7% in year one, but the gain came in Apr–Dec 2025 and then faded. — [Computed](reform_case_studies_data/episodes.py)
- **Post-credibility year-1 premium** (relative to EEM unless noted) — all [Computed](reform_case_studies_data/episodes.py):
  - Positive: Milei +51%, Macri +17%, Japan TSE request +16% (+8% vs EFA), India +11%, Brazil/Temer +11%, US TCJA +11% vs EFA, Vietnam +7%, South Africa GNU +18%.
  - Negative: Greece 2015 −21%, Greece 2019 −35% (COVID), Ramaphosa −13%, Saudi −12%, Indonesia −4%.
- **NZ 1984–87 and Mexico 1990–93.** Both had huge early booms followed by about −60% (NZ, local) and about −67% (Mexico, USD) collapses. — [NZ Herald](https://www.nzherald.co.nz/indepth/business/1987-stock-market-crash/); [Federal Reserve Bulletin](https://www.federalreserve.gov/pubs/bulletin/1996/396lead.pdf)

### Inferences
- **A practical rule supported by this sample:**
  - **(a)** Most of the re-rating happens between "the reformer becomes the likely winner" and "the reformer takes office". Polls and primaries (Argentina's Aug-2023 PASO, Modi's Sep-2013 nomination) are the earliest investable signals.
  - **(b)** Buying at the confirmation event still had positive expected relative returns for about 12 months.
  - **(c)** By years 3–5 the reform premium is gone unless earnings and macro data confirm it. Exiting or hedging after 12–24 months, or on euphoric index events (Vietnam's FTSE upgrade, Argentina's midterm, MSCI upgrade hopes), would have avoided several reversals.
- **Lasting winners shared three features** (Greece after 2019, India 2014–24, Japan after 2014 hedged, US after 2017):
  - a cheap starting valuation or a crisis-depressed base;
  - sustained macro stability (investment grade, low inflation);
  - earnings growth, not just a P/E re-rating.
- **Lasting losers** (Saudi Vision 2030, Indonesia, Turkey after 2024, Brazil after 2019) had reform headlines without earnings delivery, or currency and fiscal fragility.
- **Henry's 40% inflation threshold matters.** Big stabilizations from high inflation (Argentina 2023, Turkey 2023) get the largest initial re-rating. Moderate-inflation "reforms" (Saudi, Indonesia, Japan's governance codes) get small or no event effects, and returns depend on slower fundamentals.
- **Anti-market events are not pre-priced; anti-market *fears* are sometimes over-priced.** The asymmetry suggests buying fear-driven collapses only when the feared policy is not yet law (Brazil 2002, Mexico 2018). It also suggests treating enacted expropriation or capital controls (China 2021, Russia 2022, Venezuela 2007) as a regime change, not a dip.

### Gaps
- No formal event study with standardized dates across all episodes; the t0 choices are mine and could be debated (Henry's critics show results are date-sensitive).
- Henry (2002)'s event window and per-country table were not retrieved (PDF fetch failed).
- No out-of-sample test of the "exit after 12–24 months" rule. It is a hypothesis for the backtest phase (task #11), not a finding.

---

## 5. Survivorship and selection bias (constraint check)

### Takeaway
The episode list is selected in hindsight from famous reforms. It omits reforms that were announced but never credited by markets, and countries whose markets disappeared or were never investable (Venezuela, Russia after 2022, Estonia in the early 1990s). Index and ETF data also start after many reforms were already priced. Results therefore probably overstate how predictable and how large reform premia are.

### Cited Findings
- Event-study results on liberalization are sensitive to how event dates are defined. — [Oxford QEH WP](https://www.qeh.ox.ac.uk/sites/default/files/pdf_docs/qehwps51.pdf)
- Henry's (2002) stabilization effect is about zero for episodes starting below 40% inflation, so only dramatic, high-inflation episodes show big effects. That is the same subset that gets remembered. — [Stanford GSB](https://www.gsb.stanford.edu/faculty-research/working-papers/disinflation-good-stock-market)
- Russia was removed from MSCI at "effectively zero" in Mar 2022. Any backtest starting after that, or using surviving-country indices, excludes this loss. — [ETFdb](https://etfdb.com/emerging-markets-content-hub/msci-removes-russian-securities-from-em-indexes/)
- RSX and ERUS (Russia ETFs) are missing from the current data vendor ("not_found"), which is a direct example of survivorship in ETF-based backtests. — [Computed](reform_case_studies_data/episodes.py)
- The NZ market "never topped its 1987 peak" in capital terms, but the episode is usually remembered as a reform success story. — [NZ Herald](https://www.nzherald.co.nz/indepth/business/1987-stock-market-crash/)
- **Data-quality issues found in this session:**
  - Robinhood's EWJ series does not adjust for the Nov-2016 1:4 reverse split (a spurious +295% month), so the local dividend-adjusted file was used instead.
  - HEWJ shows a −35% month (Dec-2022) consistent with an unadjusted corporate action.
  - Robinhood interday bars are price-only. Comparing RH_EEM with dividend-adjusted EEM shows a gap of about 2–3 points a year (2008–2013: +67% vs +83%).

  — [Computed](reform_case_studies_data/episodes.py)

### Inferences
- **For the backtest phase:**
  - Pre-register event dates, using objective triggers such as election-result dates or the date a law is enacted.
  - Include failed and unremembered reforms (for example Brazil 1990 Collor, Argentina 2001, Mexico 1994, Pakistan, Egypt 2016, Nigeria 2023) and delisted markets.
  - Use dividend-adjusted series with currency decomposition.
- Absolute ETF returns understate total return by the dividend yield (roughly 2–4% a year for EM). The relative comparisons above use price-only series on both sides, which mostly cancels this out.

### Gaps
- No systematic list of "reforms that markets ignored" was assembled; this needs a source such as Fraser Economic Freedom of the World changes (the efotw.org host was blocked) or IMF structural-reform databases.
- Sample size (about 20 modern episodes with overlapping windows and shared global shocks: 2018 dollar, COVID 2020, 2022 rates) is too small for statistical inference.
