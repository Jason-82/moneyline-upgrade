# Does a Country's Economic-Policy Direction Predict Its Stock Returns? Literature Review (as of Oct 2026)

> **How this was verified.** In this sandbox, direct page/PDF fetches (WebFetch and curl) were blocked by the egress proxy (DNS failure or CONNECT 403 for cato.org, ideas.repec.org, nber.org, wiley.com, aqr.com, stern.nyu.edu, ufl.edu and others). So every finding below comes from search-engine retrieval of abstracts, publisher and RePEc listings, and secondary write-ups. **None was checked against a paper's full-text tables.** Tags:
> - **[A]**: matches the paper's own abstract or publisher/RePEc listing text as retrieved.
> - **[S]**: secondary source only (blog, review, thesis, practitioner summary).
> - **[U]**: unverified or conflicting. Treat as a lead, not a fact.
>
> Every effect size should be re-checked against the PDF before it goes into a pre-registration.

## Q1. Do LEVELS or CHANGES of economic freedom (Fraser EFW, Heritage) predict later country equity returns?

### Takeaway
**Changes vs levels:**
- Changes in economic freedom are positively associated with country equity returns in several studies (Stocker 2005/2016, Smimou & Karabegovic 2010, Burnie 2021).
- Levels show little or no relation to returns in most studies. Freedom levels relate much more reliably to *lower volatility*.

**Caveats on the change signal:**
- The supportive "change" results are mostly contemporaneous or ex-post, measured over the same window as the returns. That is not a signal you could trade from published data.
- Risk-based evidence points the other way on levels. Riskier, less free countries earned higher average returns (Erb-Harvey-Viskanta: 27% vs 15% a year by risk quartile).
- No out-of-sample, publication-lag-respecting test with controls for valuation, momentum, size and currency was found in the peer-reviewed literature.

### Cited Findings

**Stocker (2005), Cato Journal 25(3):583–594**
- **Sample:** developed and emerging markets, 1975–2002, Fraser EFW index.
- **Change:** "the rate of increase in economic freedom is directly related to equity returns", and a strategy based on it "earned attractive returns". [A] — [Cato Journal PDF](https://www.cato.org/sites/cato.org/files/serials/files/cato-journal/2005/11/cj25n3-14.pdf); [World Bank PSD blog summary](https://blogs.worldbank.org/en/psd/the-equity-return-of-economic-freedom)
- **Level:** the paper reports that the absolute level of economic freedom had no effect on equity returns. [A/S] — [Cato Journal PDF](https://www.cato.org/sites/cato.org/files/serials/files/cato-journal/2005/11/cj25n3-14.pdf)
- **Effect size:** no per-year return spread or regression coefficient could be retrieved. [U]

**Stocker (2016), "The price of freedom: A Fama–French freedom factor," Emerging Markets Review 26:1–19**
- **Factor Sharpe ratios:** "the ex-ante level and ex-post change in economic freedom" act as country-level return factors with Sharpe ratios above value, momentum and size. Fama–MacBeth regressions "confirm the economic freedom factor". [A] — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1566014116300048); [RePEc](https://ideas.repec.org/a/eee/ememar/v26y2016icp1-19.html)
- **Low overlap with standard factors:** country portfolios sorted on percentage change in freedom have correlation below 0.50 with value, momentum and size. [A]
- **Not retrieved:** sample period, country count and Sharpe values. [U]
- **Conflict with 2005:** the 2016 abstract credits the *ex-ante level*, while the 2005 paper says levels had no effect. This is unresolved.
- **Look-ahead risk:** the *ex-post* change is not known at portfolio formation.

**Possible 2016 follow-up in Journal of Financial Economic Policy 8(2):248–267**
- A search summary describes it as Stocker's. It argues relative equity returns relate to changes in freedom and that "equity markets identify which countries have increased economic freedom, long before popular economic freedom indexes are published." [U: authorship and venue not confirmed; a second search found no Stocker paper in that journal] — [RePEc listing](https://ideas.repec.org/a/eme/jfeppp/v8y2016i2p248-267.html)

**Stocker's own practitioner caveats (CNBC, Nov 2019)**
- The return advantage shows up mainly over shorter horizons. "Beyond the 10-year investment horizon, however, returns even out." Expropriation or hyperinflation can erase gains. [S] — [CNBC](https://www.cnbc.com/2019/11/06/how-the-investment-world-is-trying-to-promote-freedom-in-emerging-markets.html)
- **Conflict of interest:** Stocker is described as portfolio manager of a "World Freedom Select" strategy, so he has a commercial interest in the thesis. [S] — same source.

**Chu, Stocker & Tan (2021), "Economic fitness," Int. J. Finance & Economics 26(1):1550–1562**
- Equity markets outperform alongside gains in economic institutions and economic complexity. [S/U: abstract not retrieved; author attribution only from a search summary] — [RePEc](https://ideas.repec.org/a/wly/ijfiec/v26y2021i1p1550-1562.html)

**Smimou & Karabegovic (2010), Emerging Markets Review 11(2):119–151**
- **Sample:** MENA stock markets (about 11 emerging markets including Turkey, roughly 2000–2007 [S]).
- **Finding:** "changes in economic freedom have a positive impact on equity market returns, which are not explained by business-cycle control variables". Legal structure and security of property rights have the largest impact. [A] — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1566014110000117); [RePEc](https://ideas.repec.org/a/eee/ememar/v11y2010i2p119-151.html)
- **Limits:** short window, small regional sample, controls are business-cycle variables only (no valuation or momentum controls are mentioned).

**Burnie (2021), Int. J. Finance & Economics 26(1):375–390**
- **Sample:** 87 stock markets, Dec 1995–Jun 2016; Heritage freedom, property-rights and corruption indices plus democracy/dictatorship coding; first differences.
- **Finding:** markets respond positively to releases of economic-freedom index data. Changes in the adjusted freedom score and in corruption have a positive effect on returns. **Property rights show no effect.** Required compensation is lower in democracies than in dictatorships, i.e. dictatorships earn a risk premium. [A] — [RePEc](https://ideas.repec.org/a/wly/ijfiec/v26y2021i1p375-390.html); [Wiley](https://onlinelibrary.wiley.com/doi/10.1002/ijfe.1794)

**Null and volatility-only results**
- **Chen & Huang (2009), IJAIM 17(2):189–197 (Heritage index):** "adjusted stock returns bear little relationship with economic freedom". Freedom is associated with *lower volatility*, so freer markets offer better mean-variance efficiency. [A] — [RePEc](https://ideas.repec.org/a/eme/ijaimp/v17y2009i2p189-197.html); [Emerald](https://www.emerald.com/insight/content/doi/10.1108/18347640911001221/full/html)
- **Al-Amarneh, GCC markets 1996–2015:** freedom level has "little impact on market return" but reduces volatility. [A] — [Jordan Journal of Economic Sciences](https://jjournals.ju.edu.jo/index.php/jjes/article/view/2022)
- **Blau, Brough & Thomas (2014), J. Int'l Money & Finance 41:182–196:** across 327 ADRs, home-country freedom is inversely related to price volatility. The effect is driven mainly by property rights, sound money and free trade. [A] — [RePEc](https://ideas.repec.org/a/eee/jimfin/v41y2014icp182-196.html); [Mercatus summary](https://www.mercatus.org/students/research/journal-articles/economic-freedom-and-stability-stock-prices-cross-country)
- **Blau (2017), "Economic Freedom and Crashes in Financial Markets," JIFMIM 47:33–46:** exists per the author's publication list; findings not retrieved. [U] — [Blau faculty page](https://huntsman.usu.edu/directory/blau-ben)

**Valuation and cost-of-capital channels (levels)**
- **Chen, Chen & Jin (2015), The Accounting Review (30 countries, 2000–2010, Fraser EFW):** greater freedom makes the value–earnings relation more convex, i.e. more valuable real options. This is distinct from GDP, legal origin and investor protection. It is a valuation result, not a returns-prediction result. [A] — [SMU repository](https://ink.library.smu.edu.sg/soa_research/1555)
- **Hail & Leuz (2006), 40 countries:** stronger disclosure, securities regulation and enforcement mean a significantly *lower* cost of equity capital. Better institutions therefore imply *lower* expected returns once the improvement is priced. [A] — [ECGI](https://www.ecgi.global/publications/working-papers/international-differences-in-the-cost-of-equity-capital-do-legal)

**Risk-rating analogues to "freedom"**
- **Erb, Harvey & Viskanta (1995), "Country Risk and Global Equity Selection":** sorting on risk *levels*, the highest-risk quartile averaged about 27% a year and the lowest-risk quartile about 15% a year. [S: snippet of paper text] — [Harvey/Duke](https://people.duke.edu/~charvey/papers/p26.html); [Academia copy](https://www.academia.edu/1200653/Country_risk_and_global_equity_selection)
- **Erb, Harvey & Viskanta (1996), FAJ 52(6):29–46:**
  - Portfolios of countries with rating upgrades vs downgrades, formed after the information is public and rebalanced every 6 months, show "information about expected equity returns" in ICRG and Institutional Investor ratings.
  - The measures are "highly correlated with equity valuation measures".
  - Return spreads not retrieved [U].
  - [A] — [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/1996/political-risk-economic-risk-and-financial-risk); [Harvey/Duke](https://people.duke.edu/~charvey/Country_risk/pol/pol.htm)
- **Mean reversion:** Harvey's teaching notes cite evidence that country risk ratings mean-revert. [S] — [Harvey notes](https://people.duke.edu/~charvey/Teaching/BA456_2006/Harvey_12_ways_to.pdf)
- **Diamonte, Liew & Stevens (1996), FAJ 52(3):71–76:**
  - Emerging markets with *decreased* analyst-rated political risk beat those with increased risk by about 11% **per quarter**; developed markets show about 2.5% per quarter.
  - The authors' own conclusion is that "*if one can forecast changes in political risk*, one can forecast stock returns." That implies a contemporaneous relation, not a lagged signal.
  - [A] — [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/1996/political-risk-in-emerging-and-developed-markets); [AQR](https://www.aqr.com/Insights/Research/Journal-Article/Political-Risk-in-Emerging-and-Developed-Markets)
- **Lehkonen & Heimonen (2015), JIMF 59:77–99 (49 emerging markets, 2000–2012):** "decreases in political risk lead to higher returns". The democracy–political-risk relation is parabolic, with risk falling only past a democracy threshold. [A] — [JYX repository](https://jyx.jyu.fi/handle/123456789/48849)

### Inferences
- **The "change" literature mostly shows that prices and freedom improvements move together.** Fraser EFW publishes with a lag. Stocker 2016 uses *ex-post* change, and Diamonte et al. frame their result as needing a *forecast* of risk change. So the investable claim is "if you can forecast freedom improvements before the market does, you earn excess returns." The forecasting skill, not the index, is the edge. A backtest must use index values only as of their publication date.
- **Levels and changes point in opposite directions under a risk-based view.** Countries that become freer get re-rated upward, a one-time capital gain. Higher-freedom, lower-risk countries should then have *lower* forward expected returns (EHV 1995; Hail & Leuz; Burnie's dictatorship premium). A "buy the freest countries" strategy is not supported. "Buy countries that will become freer" is supported only conditional on foresight.
- **The robust and replicable effect of freedom levels is lower volatility** (Chen & Huang; Blau et al.; Al-Amarneh). That argues for freedom as a risk-reduction tilt, not an alpha source.
- **The freedom signal may proxy for valuation.** EHV 1996 found risk ratings "highly correlated with equity valuation measures". Stocker 2016 reports correlation below 0.5 with value, momentum and size, which is low but not zero. A pre-registered test needs CAPE or dividend-yield controls.
- **Supportive evidence is concentrated in emerging and frontier markets** (Diamonte et al. EM 11% vs DM 2.5% a quarter; Smimou-Karabegovic MENA). Fragility work (Q6) shows small, segmented markets inflate anomaly results. Those markets are also costly to access for a US investor.

### Gaps
- Effect sizes (return spread per unit of EFW change, t-stats, Sharpe values) for Stocker 2005 and 2016 could not be retrieved, nor sample sizes or whether currency was hedged. Full text is needed.
- No 2017–2026 peer-reviewed paper was found that tests *published, lagged* Fraser/Heritage changes against country returns out-of-sample with value, momentum, size and FX controls. The search for 2022–2025 work turned up efficiency and volatility studies only (e.g., [Asian markets 2026](https://link.springer.com/article/10.1007/s10690-026-09630-1)).
- **Findings not retrieved:**
  - Chen, Lee & Hsu (2017), "Investor sentiment and country ETFs: does economic freedom matter?", NAJEF 42:285–299 — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1062940817301432)
  - Blau (2017) on crashes
- **Not identified:** a paper by "Li" matching the brief.
- **No evidence found** on component-level claims beyond those noted ("tax burden" or "size of government" specifically) predicting returns. Smimou-Karabegovic point to legal structure and property rights, but Burnie finds no property-rights effect. **Conflicting.**

## Q2. The growth–returns puzzle (Ritter; Dimson-Marsh-Staunton): what does it imply for a "pro-growth policy" thesis?

### Takeaway
Across countries, realized GDP growth has had zero-to-negative correlation with equity returns, over 1900–2011 for developed markets and 1988–2011 for emerging ones.
- **Reasons:** expected growth is priced in, growth accrues to new firms, workers and consumers rather than existing shareholders, and share issuance dilutes per-share earnings.
- **What does relate to returns:** per-share dividend growth and governance.
- **Implication:** a thesis that policy produces growth, so stocks go up, has no historical support unless growth is *unexpected* and *captured per share*.

### Cited Findings

**Ritter (2005), Pacific-Basin Finance Journal 13(5):489–503**
- The cross-country correlation of real stock returns and per-capita GDP growth over 1900–2002 is negative. [A] — [Ritter PDF](https://site.warrington.ufl.edu/ritter/files/2015/04/Economic-growth-and-equity-returns-2005.pdf)
- **Correlation figure:** a secondary source cites −0.37 (p = 0.16, not significant at 5%) on p. 495. [S] — [Univ. of Vaasa thesis](https://osuva.uwasa.fi/bitstreams/4c75642a-b30d-46a9-93ae-36000bbc5889/download)
- **Conflict:** another summary garbles this against a DMS figure of −0.27 for 16 countries. [U]
- **Other samples:** the correlation was about zero for 19 developed markets in 1970–2002 and negligible for 13 emerging markets in 1988–2002. [S] — [Springer chapter, "Economic Growth vs. Equity Returns in Emerging Markets"](https://link.springer.com/content/pdf/10.1057/9781137450661_1)

**Ritter (2012), "Is Economic Growth Good for Investors?", J. Applied Corporate Finance 24(3)**
- **Correlations:** −0.39 for 19 developed countries (1900–2011) and −0.41 for 15 emerging markets (1988–2011). [A/S] — [Wiley](https://onlinelibrary.wiley.com/doi/10.1111/j.1745-6622.2012.00385.x); [Alpha Architect summary](https://alphaarchitect.com/2014/01/finance-mythbuster-economic-growth-doesnt-help-investors/)
- **Mechanism:**
  - Growth comes from added capital and labor, which "don't necessarily benefit the stockholders of existing companies".
  - Technology gains are competed away to consumers and workers.
  - There is a "strong positive association between (per share) dividend growth rates and overall stock returns".
  - Governance matters.
  - [S] — [Alpha Architect](https://alphaarchitect.com/2014/01/finance-mythbuster-economic-growth-doesnt-help-investors/)

**Dimson, Marsh & Staunton (DMS)**
- **2002 book (16 countries, from 1900):** negative growth–return correlation. [S] — [Brandes/UCSD](https://rady.ucsd.edu/_files/brandes/value-investing/new-insights-into-the-case-for-emerging-market-equities.pdf); [Springer chapter](https://link.springer.com/chapter/10.1057/9781137450661_1)
- **2010 Yearbook:**
  - Regressions of annual GDP growth on local-currency real returns have adjusted R² "on average zero and in most cases negative". [A: Yearbook text] — [CS Global Investment Returns Yearbook 2010](https://www.fullertreacymoney.com/system/data/images/archive/2010-04-06/Global-Investment-Returns-Yearbook-CSFB.pdf)
  - Across 83 countries, 1972–2009, the lowest-GDP-growth countries had the highest market returns. [S] — [Brandes/UCSD](https://rady.ucsd.edu/_files/brandes/value-investing/new-insights-into-the-case-for-emerging-market-equities.pdf)
  - 44 countries, 1970–2009: no statistically significant relation. [S] — [NBIM 2016 discussion note](https://www.nbim.no/en/publications/discussion-notes/2016/global-growth-and-equity-returns)
- **Authors' own framing:** "in 2010 and 2014 … over the long run, investors had underperformed by investing in markets with high past GDP growth, compared to lower growth markets." [A] — [Cambridge Judge Business School](https://www.jbs.cam.ac.uk/centres/ceam/research/investing-over-the-long-term/global-investment-returns/)
- **Northern Trust characterization:** a "modest" negative correlation with R² effectively zero. [S] — [Northern Trust](https://www.northerntrust.com/content/dam/northerntrust/pws/documents/commentary/investment-commentary/the-enigma-economic-growth-and-stock-market-returns.pdf)

**MSCI Barra (2010)**
- Long-run stock price growth trailed GDP growth in many countries. Eight developed markets, 1958–2008, show a negative correlation, sensitive to start and end dates. [S] — [MSCI](https://www.msci.com/research-and-insights/paper/is-there-a-link-between-gdp-growth-and-equity-returns)

**NBIM Discussion Note 5/2012 (Norway's sovereign fund)**
- The evidence "does not support the notion of a structural relationship between economic growth and equity returns."
- **Reasons given:**
  - Countries differ in converting GDP growth into profit growth.
  - "better growth prospects are often reflected in market prices."
- **Consequence:** NBIM used this to decide against tilting away from market-cap weights toward high-growth emerging markets. [A] — [NBIM](https://www.nbim.no/en/publications/discussion-notes/2012/economic-growth-and-equity-returns)

### Inferences
- **A pro-growth policy thesis only earns excess returns via surprise.** To profit, policy-driven growth must exceed what prices already embed, and it must reach existing shareholders per share without dilution or expropriation. This links Q1 and Q2: both say the edge is in *anticipating* change before consensus, not in identifying "good policy."
- **Better proxies for testing:** per-share dividend or earnings growth and governance. Ritter's dividend-growth result is contemporaneous, so it is not directly tradeable either.
- **Industrialization and capex-led growth are the textbook case of input-driven growth.** It is exactly the kind Ritter argues does not accrue to existing shareholders (see Q5 on China).

### Gaps
- Exact DMS portfolio-sort spreads (low- vs high-growth quintile returns, 1972–2009 and the 2014 update) could not be retrieved. The 2026 Yearbook's current figures on growth vs returns were not found in the public summary.
- The precise Ritter (2005) correlation (−0.37 vs −0.27) is unresolved. It needs p. 495 of the paper.
- No study was found that separates *policy-driven* growth surprises from other growth surprises in a cross-country returns test.

## Q3. Political risk, reform, liberalization and tax changes: what do the event studies and political-risk studies find?

### Takeaway
**Supportive evidence (reform news is priced):**
- Large, discrete reforms in emerging markets were followed by big repricings: stock market liberalization, abnormal returns of about 3.3% a month over 8 months; disinflation from inflation above 40%, about +24% real USD.
- Tax cuts are capitalized into prices (TCJA, election-2016 reactions, Sialm 2009).

**Limits:**
- The repricing occurs *around or before* implementation. It is a one-time level shift, not a persistent excess return.
- Moderate reforms (disinflation from below 40%) produced about zero.
- Pástor-Veronesi theory and evidence: policy *changes* on average lower prices through higher uncertainty and risk premia.
- In US time series, returns were higher under the party associated with *more* redistribution. The authors explain this as risk-premium dynamics, not policy merit.

### Cited Findings

**Henry (2000), J. Finance 55(2):529–564**
- A country's aggregate equity index earns abnormal returns of **3.3% per month in real dollar terms during an 8-month window leading up to** the initial stock market liberalization (about 26% cumulative by simple arithmetic). This is consistent with a lower cost of equity. [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v55y2000i2p529-564.html); [Stanford GSB](https://www.gsb.stanford.edu/faculty-research/working-papers/stock-market-liberalization-economic-reform-emerging-market-equity)
- A companion paper in the same issue (Bekaert & Harvey 2000) finds the cost of capital falls 5–75 bp after liberalization. [S] — [JF vol. 55 issue 2](https://afajof.org/issue/volume-55-issue-2/)

**Henry (2002), J. Finance 57(4):1617–1648 (81 stabilization episodes)**
- Stocks rise **24% in real dollar terms** when countries stabilize inflation above 40%.
- The average response is **0** when pre-stabilization inflation is below 40%.
- Stock responses also predict next-year changes in inflation and output.
- [A] — [NBER w8289](https://www.nber.org/papers/w8289); [Stanford GSB](https://www.gsb.stanford.edu/faculty-research/working-papers/disinflation-good-stock-market)

**Kim & Singal (2000), J. Business 73(1):25–66**
- Stock returns increase immediately after market opening without a rise in volatility. Inflation and FX volatility fall. [A] — [VTechWorks](https://vtechworks.lib.vt.edu/handle/10919/49136); [JSTOR](https://www.jstor.org/stable/10.1086/209631)

**Bekaert, Harvey & Lundblad (2005), JFE 77(1)**
- Equity market liberalization adds about 1 percentage point to annual real GDP growth over 5 years, robust to specifications. [A] — [NBER w8245](https://www.nber.org/papers/w8245); [CFA Digest](https://rpc.cfainstitute.org/-/media/documents/article/cfa-digest/2006/dig-v36-n1-1816-pdf.pdf)
- A Stanford commentary disputes the magnitude as inconsistent with neoclassical growth theory. [A] — [Stanford GSB commentary](https://www.gsb.stanford.edu/faculty-research/working-papers/commentary-bekaert-harvey-lundblads-equity-market-liberalization)

**Bekaert, Harvey, Lundblad & Siegel (2014), "Political Risk Spreads," JIBS 45(4):471–493**
- **Measure:** a market-based political risk measure from sovereign USD spreads.
- **Findings:**
  - Political risk ratings are "predictive, on average, of future risk realizations."
  - A 1-percentage-point reduction in the political risk spread is associated with a **12% increase in net FDI inflows**.
- [A] — [NBER w19786](https://www.nber.org/papers/w19786); [UNC Kenan](https://kenaninstitute.unc.edu/publication/political-risk-spreads/)

**Bekaert, Harvey, Lundblad & Siegel (2016), "Political Risk and International Valuation," J. Corporate Finance 37:1–23**
- Adding the full sovereign spread to discount rates double-counts risk. Political risk spreads isolate the political part. [A] — [Columbia](https://business.columbia.edu/faculty/research/political-risk-and-international-valuation-0); [RePEc](https://ideas.repec.org/a/eee/corfin/v37y2016icp1-23.html)

**Pástor & Veronesi**
- **2012, J. Finance 67(4):** "Stock prices fall at the announcements of policy changes, on average." The fall is larger when policy uncertainty is high. Policy changes raise volatility, risk premia and correlations among stocks. [A] — [NBER w16128](https://www.nber.org/papers/w16128)
- **2013, JFE ("Political Uncertainty and Risk Premia"):** empirical evidence consistent with a political-uncertainty premium. [A] — [NBER w17464](https://www.nber.org/system/files/working_papers/w17464/w17464.pdf)
- **2020, JPE 128(11):4011–4045 ("Political Cycles and Stock Returns"):**
  - **Size of the gap:** 1927–2015 US average excess market return was about 10.7% a year under Democratic presidents and roughly −0.2% under Republican presidents, a gap of about 11 points that "survives an out-of-sample assessment". [A for 10.7% and survival; the Republican figure was garbled in the retrieved snippet, U]
  - **Their explanation:** voters elect the more redistributive party when risk aversion is high, so subsequent expected returns are high. The pattern is a risk-premium effect, not a policy-quality effect.
  - [NBER w23184](https://www.nber.org/papers/w23184); [Chicago Booth Review](https://www.chicagobooth.edu/review/why-stock-returns-under-trump-might-disappoint-investors)

**Wagner, Zeckhauser & Ziegler (2018), JFE 130:428–451 (2016 US election)**
- **Winners:** high-tax firms and firms with large deferred tax liabilities gained.
- **Losers:** firms dependent on NOL carryforwards lost.
- **Trade exposure:** domestic firms beat internationally oriented ones.
- **Speed:** easily assessed effects such as tax rates were priced faster than complex ones such as foreign exposure.
- [A] — [HKS](https://www.hks.harvard.edu/publications/company-stock-price-reactions-2016-election-shock-trump-taxes-and-trade); [NBER w23152](https://www.nber.org/papers/w23152.pdf); [Harvard CorpGov forum](https://corpgov.law.harvard.edu/2017/02/22/company-stock-reactions-to-the-2016-election-shock-trump-taxes-and-trade)

**Kalcheva, Plečnik, Tran & Turkiela (2020), J. Banking & Finance (TCJA 2017)**
- **Winners and losers:** benefits accrued mainly to highly taxed firms. Firms with international operations, high interest expense or tax losses were hurt. Constrained and high-growth firms did not benefit.
- **Use of the gains:** firms raised repurchases but not investment.
- **Market-level move:** S&P 500 cumulative excess return vs the MSCI index was **2.247%** over key event days, roughly $600bn. This is not a clean estimate of the Act's effect.
- [A/S] — [DOI 10.1016/j.jbankfin.2020.105860](https://doi.org/10.1016/j.jbankfin.2020.105860); [repository copy](https://expeditiorepositorio.utadeo.edu.co/items/f1415d7f-a5d6-4787-ba2f-74d4d4b9e6bb/full)

**Sialm (2009), AER 99(4):1356–83 (US, 1913–2006)**
- Stock valuations are "relatively low when tax burdens are relatively high". Tax capitalization holds over time and across firms. [A] — [NBER w11756](https://www.nber.org/papers/w11756); [RePEc](https://ideas.repec.org:443/a/aea/aecrev/v99y2009i4p1356-83.html)

### Inferences
- **Tax and reform effects are real but are level shifts in price.** They show up as event-window returns (TCJA about 2.2% excess on event days; liberalization about 26% over 8 months). After capitalization, Sialm's logic implies *lower* forward pre-tax returns for the now-lower-taxed equity, not higher ones.
- **Henry's 40% threshold is a caution against generic "pro-market policy" tilts.** Only large, credible regime changes from bad starting points produced big repricing; marginal improvements produced about zero. Most current developed-market policy shifts (tax cut of a few points, deregulation at the margin) resemble the "below 40%" case more than the liberalization case.
- **Neutrality check:** the only long US time-series evidence on partisan control (Pástor-Veronesi) shows *higher* returns under the more redistributive party. The authors attribute this to risk aversion and premia, not policy merit. With about 22 presidential terms, statistical power is low either way. It does not support any party-policy tilt.
- **US-investor implication of Sialm:** personal-level tax burdens are priced. For a US taxable investor, the relevant foreign return is after foreign withholding, the US foreign tax credit and qualified-dividend status. Policy-driven pre-tax return differences can be offset at the investor level. Not researched here.

### Gaps
- No cross-country panel study of *corporate tax-rate cuts* (many countries and episodes) vs subsequent 1–5 year index excess returns was found. India's 2019 cut has a single-country event study ([Indian Journal of Finance](https://indianjournalofentrepreneurship.com/index.php/IJF/article/view/162839)); its findings were not retrieved.
- Henry 2000: the decomposition of liberalization vs concurrent macro reforms (stabilization, trade, privatization) and the post-implementation returns were not retrieved.
- Henry (2007, J. Economic Literature) survey on capital account liberalization was not retrieved.

## Q4. Does the market price policy changes quickly? Momentum or reversal in country returns after reform news

### Takeaway
**Fast pricing of simple, discrete news:**
- Prices move *before* implementation (Henry 2000) and on simple tax news (Wagner et al.).
- Markets reportedly identify freedom gains before indices publish them (Stocker).

**Exploitable lags:**
- Complex or diffuse information (foreign exposure, oil prices) is priced with a lag.
- Country indices show 6–12 month momentum and 2–3 year reversal.

**Bottom line:**
- The defensible "policy" edge is anticipation, plus perhaps riding post-news momentum, rather than buying after a reform is visible in an annual index.
- Country momentum and value premia have weakened since publication and are fragile to research design.

### Cited Findings
**Evidence of fast or anticipatory pricing**
- **Henry (2000):** the abnormal returns are concentrated in the 8 months *leading up to* implementation of liberalization. [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v55y2000i2p529-564.html)
- **Stocker (attributed):** equity markets identify increases in economic freedom "long before popular economic freedom indexes are published." [U] — [RePEc JFEP listing](https://ideas.repec.org/a/eme/jfeppp/v8y2016i2p248-267.html)
- **Wagner, Zeckhauser & Ziegler (2018):** easily assessed effects (tax rates, deferred taxes) were priced faster than complex ones (foreign exposure). [A] — [HKS](https://www.hks.harvard.edu/publications/company-stock-price-reactions-2016-election-shock-trump-taxes-and-trade)

**Evidence of incomplete pricing**
- **Burnie (2021):** markets react positively to releases of economic-freedom data, i.e. some information content at publication. [A] — [RePEc](https://ideas.repec.org/a/wly/ijfiec/v26y2021i1p375-390.html)
- **Driesprong, Jacobsen & Maat (2008), JFE 89(2):307–327:** investors "underreact to information in the price of oil", an example of slow macro-information diffusion. [A] — [RePEc](https://ideas.repec.org/a/eee/jfinec/v89y2008i2p307-327.html)

**Country momentum and reversal**
- **Bhojraj (2006, "Macromomentum," J. Business 79(1)):**
  - Country indices show momentum in the first year after formation and reversal over the next 2 years.
  - Positive currency momentum predicts low future index returns.
  - The authors' reading is consistent with behavioral underreaction then overreaction.
  - [A] — [RePEc](https://ideas.repec.org/a/ucp/jnlbus/v79y2006i1p429-428.html)
- **Richards (1997), J. Finance 52(5):2129–2144 (16 national indices):**
  - Winner–loser reversals are not explained by risk; loser countries are not riskier.
  - Small markets reverse more.
  - [A] — [RePEc](https://ideas.repec.org/a/bla/jfinan/v52y1997i5p2129-44.html); [IMF WP 97/182](https://www.imf.org/en/Publications/WP/Issues/2016/12/30/Winner-Loser-Reversals-in-National-Stock-Market-Indices-Can-they-Be-Explained-2458)
- **Zaremba (2019) review, JRFM 12(4):165:**
  - The earliest index-level evidence (38 country indices) found 6-month winners kept outperforming; later work extends to 74 countries.
  - Countries show short-term *continuation*, not the stock-level one-month reversal.
  - [A/S] — [MDPI](https://www.mdpi.com/1911-8074/12/4/165)

**Pricing of political-risk changes**
- **Diamonte et al. (1996):** the large political-risk return spread (11% a quarter in EM) is conditional on *forecasting* the change. [A] — [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/1996/political-risk-in-emerging-and-developed-markets)
- **Erb-Harvey-Viskanta (1996):** a tradeable design (formed after publication, 6-month rebalancing) did find "information about expected equity returns" in rating changes. Magnitude not retrieved. [A] — [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/1996/political-risk-economic-risk-and-financial-risk)

### Inferences
- **A pre-registered test should separate three quantities:**
  - (a) the contemporaneous association (freedom change vs return over the same window; diagnostic only);
  - (b) the publication-date reaction (Burnie-style);
  - (c) post-publication drift over 3–24 months. Only (c) is the investable claim for an investor using public indices.
- **Country momentum is a likely confounder.** Reform news raises prices; 12-month momentum then captures part of any post-reform drift. A policy signal must show incremental power *after* controlling for 12-1 momentum, and must avoid the 2–3 year reversal window documented by Bhojraj and Richards.
- **Tax news is priced in days.** For a US investor the speed asymmetry suggests the only window for policy-based edge is complex, multi-year, diffuse changes (institutional quality, regulatory regime) rather than headline tax-rate changes.

### Gaps
- No study was found measuring country-index drift after specific reform announcements across many countries (e.g., event-time returns 0–36 months after major pro-market reforms, with momentum controls).
- Effect size of the EHV 1996 rating-change portfolios was not retrieved.

## Q5. Industrialization and energy build-out: do rising manufacturing share or cheap/abundant energy predict better equity returns? (China as counterexample)

### Takeaway
No cross-country study was found linking rising manufacturing share, industrial build-out, or domestic energy production to higher subsequent equity returns. **This is an evidence gap, not evidence of an effect.** The adjacent evidence leans against the thesis:
- **China:** very fast growth, weak MSCI China returns.
- **Ritter:** input-driven growth does not accrue to existing shareholders.
- **DMS:** a declining industry (railroads) outperformed its newer competitors.
- **Energy:** oil-price *declines* predict higher equity returns broadly across developed markets. That is a global timing effect, not a country-selection effect favoring energy producers.

### Cited Findings
**China**
- **MSCI research (1994–2013):** GDP grew about 16% a year while the MSCI China index returned about 2% a year. The MSCI China A index returned about 12% a year, a gap MSCI attributes largely to index composition. The 16% is likely nominal or USD growth rather than real. [S/U] — [MSCI "China A-Shares: Too Big to Ignore"](https://www.msci.com/documents/10199/3db233e4-be13-4d4b-bd94-45e60dce224a)
- **Morningstar:** since the MSCI China Index started in 1993, Chinese stocks have trailed other major markets despite faster per-capita GDP growth (data through 2020). [S] — [Morningstar Australia](https://www.morningstar.com.au/markets/chinese-stocks-the-road-to-nowhere)
- **Academic evidence:**
  - Correlation between returns and GDP growth is insignificant for China and India over 1992–2013 and 2000–2013. Listed SOEs have worse ROA, ROE and cash flows than non-SOEs. [S] — [CICF paper](https://www.cicfconf.org/sites/default/files/paper_736.pdf); [SAIF/SJTU paper](https://www.saif.sjtu.edu.cn/sites/default/files/images/ymzhou/stockmkt-aqsz-05nov2016-susan.pdf)
  - China's domestic market shows below 2% correlation with future GDP growth, against positive correlations for the US, Japan, Germany and France. [S] — [VoxChina](https://www.voxchina.org/show-3-18.html)

**Mechanism**
- Growth from "increased inputs of capital and labor" need not benefit existing stockholders. Dilution and governance explain the GDP-to-shareholder leak. [S] — [Alpha Architect on Ritter 2012](https://alphaarchitect.com/2014/01/finance-mythbuster-economic-growth-doesnt-help-investors/)
- NBIM: countries differ in "converting GDP growth into profit growth". [A] — [NBIM 2012](https://www.nbim.no/en/publications/discussion-notes/2012/economic-growth-and-equity-returns)

**Industry analogue (DMS 2026 Yearbook)**
- Railroads, a declining industry, outperformed both the US market and newer transport competitors (road, air). [S] — [UBS GIRY 2026 summary](https://www.ubs.com/content/dam/assets/wm/static/cio/documents/giry2026-summary-public.pdf); [LBS](https://www.london.edu/news/ubs-global-investment-returns-yearbook-2026-history-risk-and-return-in-turbulent-times)

**Energy**
- **Driesprong, Jacobsen & Maat (2008), JFE (about 30 years of monthly data):**
  - Oil price changes significantly predict stock returns in **12 of 18 developed countries** and a world index; rises predict lower returns. Results are similar in emerging markets.
  - Robust to sample period, oil measure, and January/Halloween effects. Not explained by time-varying risk premia.
  - [A] — [Erasmus repository](https://repub.eur.nl/pub/1017); [RePEc](https://ideas.repec.org/a/eee/jfinec/v89y2008i2p307-327.html)
- **Oil-exporter vs oil-importer reactions differ, and studies conflict on which group reacts more.**
  - Exporter indices are less responsive to oil shocks in one study, but more affected in a newer panel.
  - No study compares *long-run return levels*.
  - [S] — [ResearchGate: Oil-importing vs exporting](https://www.researchgate.net/publication/256041694_Oil_Price_Shocks_and_Stock_Market_Returns_Evidence_from_Oil-Importing_and_Oil-Exporting_Countries); [Cogent Economics 2021](https://doi.org/10.1080/23322039.2021.2018163)

**Manufacturing share**
- The search returned only structural-change literature: the hump-shaped manufacturing share vs income relation across 88 countries, 1950–2005. Nothing linked to equity returns. [A] — [Verspagen et al., SCED 2015](https://verspagen.nl/wp-content/uploads/2025/08/SCED_sv.pdf); [Our World in Data](https://ourworldindata.org/structural-transformation-and-deindustrialization-evidence-from-todays-rich-countries)

### Inferences
- **The burden of proof is on the industrialization thesis.** The best-documented modern industrialization (China 1993–present) produced among the worst investor outcomes per unit of growth. Capex-heavy build-outs tend to be financed by new equity and debt, diluting existing holders.
- **Cheap energy appears to help equities in general** (Driesprong et al.), but as a time-series effect across many countries. A country "producing more energy" is plausibly *more* exposed to energy-price declines, cutting against the thesis for producer countries. Untested here.
- **Possible test with public data:** manufacturing value-added share (World Bank WDI) or energy production per capita (EIA, Energy Institute) changes against subsequent country returns, with CAPE and momentum controls. No prior literature was found to anchor the expected sign, so treat it as exploratory, not confirmatory.

### Gaps
- No academic or practitioner study found on: manufacturing-share changes vs country equity returns; domestic energy production or electricity-price levels vs country equity returns; or industrial-policy episodes vs returns.
- MSCI China's latest drawdown and YTD figures were in one snippet with an unclear year, so they are omitted.

## Q6. The factor and valuation hurdle (CAPE, value, momentum, size) any policy signal must beat, and replicability with public data

### Takeaway
**Factors that already work across countries:**
- Value (CAPE, dividend yield), momentum and market size predict country returns.
- Country CAPE explains a large share of 10–15 year returns in some markets and almost none in others.
- Cheapest-third CAPE country strategies beat equal weight by about 4–7% a year (1980–2011, gross).

**Reasons for caution:**
- Country anomalies have decayed since about 2000, especially value and reversal.
- A 2025 multiverse study finds most country signals fragile. Only market size, dividend yield, short-term momentum and sovereign risk survive.

**What a policy signal must show:**
- Incremental power over these controls, robustly, in investable markets.
- Stocker 2016 claims low correlation and higher Sharpe than value, momentum and size, but this is unverified in detail and depends on ex-post changes.

### Cited Findings

**Classic country-level factors**
- **Asness, Liew & Stevens (1997), J. Portfolio Management:** book-to-market, market equity and 1-year past return explain expected returns across national equity markets. The authors argue parallel stock/country evidence makes data mining unlikely. [A] — [AQR](https://www.aqr.com/library/journal-articles/parallels-between-the-cross-sectional-predictability-of-stock-and-country-returns)
- **Asness, Moskowitz & Pedersen (2013), J. Finance:**
  - Value and momentum premia are consistent across 8 markets, including country equity index futures.
  - There is a strong common factor structure, and value and momentum are negatively correlated (about −0.49 within asset class [S]).
  - Country-index Sharpe ratios not retrieved [U].
  - [A] — [Working paper PDF](https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf); [CXO summary](https://cxoadvisory.com/value-premium/combining-value-and-momentum-across-asset-classes)

**CAPE**
- **Keimling (2016, StarCapital), 17 markets:**
  - CAPE explained about 48% of subsequent 10–15 year returns in developed markets.
  - Explanatory power varies by market: Japan 90%, UK 86%, US 82% since 1970 (46% since 1881), Canada 1%.
  - Whether these are R² values is not confirmed, and the sample start (1969 vs 1979) conflicts across summaries. [S/U]
  - [Monevator](https://monevator.com/cape-ratio-by-country/print/); [CXO Advisory](https://cxoadvisory.com/fundamental-valuation/comparing-cape-to-other-stock-market-valuation-ratios); [The Idea Farm](https://theideafarm.com/markets/predicting-stock-market-returns-using-the-shiller-cape/)
- **Faber (2012), "Global Value":**
  - The cheapest third of country indices by CAPE beat equal weight by 4–7% a year (1980–2011, 32 countries, annual rebalance, local currency, gross).
  - A cheapest-25% version over 44 countries (1980–2013) also beat the benchmark.
  - [S] — [CXO Advisory](https://cxoadvisory.com/?p=21856); [Hedge Fund Alpha](https://hedgefundalpha.com/strategies/global-value-meb-faber/)

**Decay and fragility**
- **Zaremba, Umutlu & Maydybura (2020), "Where have the profits gone?":**
  - Covers 53 anomalies in country and industry indices from 64 markets, 1973–2018.
  - Cross-sectional predictability has declined, especially for value and reversal.
  - The decline is strongest in large developed markets and is attributed to improved efficiency.
  - [A/S] — [Napier repository](https://napier-repository.worktribe.com/output/3010882/where-have-the-profits-gone-market-efficiency-and-the-disappearing-equity-anomalies-in-country-and-industry-returns); [Yaşar repository](https://gcris.yasar.edu.tr/entities/publication/0545b6e2-bf31-453d-a1b9-973298288347/full)
- **Cakici, Fieberg, Neszveda, Piljak & Zaremba (about 2025), "Lost in the Multiverse," SSRN 5181455:**
  - Tests 15 country-level predictors under 9 design choices (about 13–14k specifications).
  - "many classic signals—such as momentum, beta, or idiosyncratic risk—are surprisingly fragile."
  - Designs emphasizing small, segmented countries enhance results; liquid, investable designs weaken them.
  - Only market size, dividend yield, short-term momentum and sovereign risk are robust in bootstrap and out-of-sample tests.
  - [A] — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5181455)
- **Zaremba (2019) review:** smaller national markets earned higher returns, and the country size effect is largely independent of firm size, momentum and value. [A/S] — [MDPI](https://www.mdpi.com/1911-8074/12/4/165)

**Link between risk ratings and valuation**
- Country risk measures are "highly correlated with equity valuation measures", per Erb-Harvey-Viskanta. Freedom and political-risk signals may partly re-label value. [A] — [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/1996/political-risk-economic-risk-and-financial-risk)
- Sovereign risk is one of the few robust country predictors. It is closely tied to the political-risk spreads of Bekaert et al. [A] — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5181455); [NBER w19786](https://www.nber.org/papers/w19786)

**Data availability for replication**
- **Fraser EFW:**
  - Free panel dataset, now fully chain-linked with base year 2020; 165 countries currently ranked.
  - About 100 countries back to 1980, many back to 1970.
  - Ratings exist only in years a country was regularly rated.
  - Fraser advises using the latest panel because earlier figures get revised.
  - [A] — [QoG data finder](https://datafinder.qog.gu.se/dataset/fi); [EFW 2024 report](https://www.fraserinstitute.org/sites/default/files/2024-10/economic-freedom-of-the-world-2024.pdf)
- **Heritage Index of Economic Freedom:** used from 1995 in Burnie (2021). [A] — [RePEc](https://ideas.repec.org/a/wly/ijfiec/v26y2021i1p375-390.html); [Heritage report page](https://economicfreedom.heritage.org/pages/report)

### Inferences
**Minimum pre-registered design to give the thesis a fair test with public data:**
- **Universe:** about 20–45 investable country indices or US-listed country ETFs, in USD.
- **Signals, all as of publication date:**
  - (i) EFW or Heritage level;
  - (ii) trailing change in the published index (1-year and 5-year);
  - (iii) optionally political-risk or sovereign-spread changes.
- **Controls:** CAPE or dividend yield, 12-1 momentum, log market cap (size), and trailing currency momentum (per Bhojraj).
- **Method:** Fama–MacBeth and long-short tercile portfolios at 12-month horizons. Report pre- and post-2000 subsamples given anomaly decay.
- **Diagnostic only:** the contemporaneous-change regression, to reconcile with Stocker and Diamonte. Never treat it as tradeable.

**Point-in-time pitfall:** the chain-linked EFW panel is *revised retroactively*. Using the latest panel for historical signals introduces look-ahead bias, so archived report vintages are needed for a true point-in-time test. Fraser itself recommends the revised panel for research, which is the wrong choice for a trading backtest.

**Realistic priors for the backtest:**
- The likely outcome is weak or no incremental predictive power for levels; a possible lower-volatility tilt for high-freedom countries; and change effects that largely vanish once publication lag and momentum are respected.
- A positive result would contradict the bulk of the literature and should be treated sceptically (multiple-testing, small cross-section).

**Power:**
- With about 25–45 countries and annual signal updates, the effective sample is small: about 25 years × about 30 countries.
- Signal changes are slow and autocorrelated.
- Expect wide confidence intervals. A 2–3% a year true effect may be statistically undetectable.

### Gaps
- **Data not verified in this session:**
  - Exact Fraser publication timing (lag between data year and report release) and the availability of archived vintages.
  - Free country-level return and valuation sources: Ken French international country portfolios, MSCI end-of-day public data, iShares country ETF histories since about 1996.
  - Public country CAPE series.
  - All plausible, but marked [U].
- **Data endpoints blocked:** the agent-proxy log in this sandbox showed CONNECT 403 refusals for fraserinstitute.org, efotw.org, heritage.org and api.worldbank.org during this session. Data acquisition for the backtest may need alternative mirrors (e.g., the QoG dataset) or user-supplied files.
- Country-index value and momentum Sharpe ratios from Asness-Moskowitz-Pedersen 2013 and the Stocker 2016 factor Sharpe ratios were not retrieved, so a numeric hurdle comparison cannot be stated.
- **US taxable-investor frictions** (foreign withholding, foreign tax credit, ETF expense ratios, qualified-dividend status, turnover-driven capital-gains realization) were out of scope and not researched. They could easily consume a 1–3% a year gross edge.
