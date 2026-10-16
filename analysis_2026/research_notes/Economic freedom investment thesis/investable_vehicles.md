# Investable Vehicles for an Economic-Freedom / Energy-Build-Out Country Tilt (US taxable investor, Schwab/Robinhood) — as of 16 Oct 2026

**How these notes were made, and their limits (read first):**
- **Web access was limited.** WebFetch could not resolve any domain from this environment (DNS failures on lifeandliberty.com, etfarchitect.com, siblisresearch.com, stockanalysis.com, monevator.com), and the session's shared web-search budget ran out partway through. Figures attributed to web pages come from **search-result summaries of those pages**, not from reading the pages directly. I mark them "(via search summary)". Treat them as **unverified until checked at the issuer's page**.
- **Live market data comes from Robinhood's market-data API**, pulled on 2026-10-16 between about 16:00 and 16:09 UTC (roughly noon ET, Friday). It includes quotes, bid/ask, 30-day average volume, ETF "market cap" (shares outstanding × price, used here as a proxy for AUM), trailing P/E, P/B, dividend yield and 30-day SEC yield. Public reference pages follow the pattern `https://robinhood.com/us/en/stocks/<TICKER>/`. Robinhood does not document how it computes ETF P/E.
- **The risk and return statistics are my own calculations** from Robinhood monthly price bars (split-adjusted, **price-only, so dividends are excluded**), using month-end closes. The scripts are at `/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/scripts/` (stats.py, longrun.py, spreads.py). Data notes:
  - iShares EWJ, EWT, EWU, EWS and EWM show roughly 4x or 2x price jumps in Nov 2016 that are not real moves. They are probably reverse-split artifacts, so the 10-year window starts at the Nov-2016 close.
  - HEWJ's price series falls about 35% in Dec 2022 because of a distribution of about $12/share (see the tax section), so its price-only figures understate its total return.
  - Total returns would be higher than the price-only figures by roughly each fund's dividend yield per year.

---

## 1. US-listed single-country ETFs: tickers, costs, size, liquidity, concentration, inception

### Takeaway
Every candidate country except Argentina has at least one US-listed, 1940-Act ETF that trades at Schwab and Robinhood. Argentina's only fund is ARGT, a narrow 27-stock index where MercadoLibre alone is about 22%. Liquidity varies a lot:
- **Very liquid (about 1–3 bp quoted spreads, $100M to $2B+ traded per day):** EWZ, EWY, EWT, EWJ, INDA, EWW.
- **Wide spreads (20–200 bp, often under $5M per day):** ARGT, EPU, EIS, GREK, the small Franklin funds (FLMX, FLBR, FLGB) and the Nordic/NZ funds.
- **Cost:** iShares single-country funds charge about 0.50–0.75%. Franklin FTSE equivalents charge 0.09–0.19% for Japan, Korea, Taiwan, Brazil, Mexico, Canada and the UK.

### Cited Findings

**Expense ratios found (via search summaries; verify at issuer):**
- EWJ (Japan) **0.49%** — [iShares UK professional page / TrackInsight](https://www.trackinsight.com/en/fund/EWJ) (via search summary). This conflicts with the commonly cited 0.50%, so verify.
- EWZ (Brazil) **0.59%** — [iShares MSCI Brazil page](https://www.ishares.com/uk/professionals/en/products/239612/ishares-msci-brazil-capped-etf) (via search summary).
- EWT (Taiwan) **0.59%** vs INDA (India) **0.61%** — [ETF Central EWT vs INDA, April 2026](https://www.etfcentral.com/compare-etfs/EWT-vs-INDA) (via search summary).
- EWQ (France) **0.50%** — [ChartRow EWQ](https://chartrow.com/quote/ewq) (via search summary).
- KSA (Saudi Arabia) **0.75%** (0.74% management fee + 0.01% other) — [iShares KSA fact sheet, 31 Mar 2026](https://www.ishares.com/us/literature/fact-sheet/ksa-ishares-msci-saudi-arabia-etf-fund-fact-sheet-en-us.pdf) (via search summary).
- UAE **0.59%** — [iShares UAE fact sheet, 31 Mar 2026](https://www.ishares.com/us/literature/fact-sheet/uae-ishares-msci-uae-etf-fund-fact-sheet-en-us.pdf) (via search summary).
- EPOL (Poland) **0.59%** net — [Yahoo Finance EPOL](https://finance.yahoo.com/quote/EPOL/) (via search summary).
- ARGT (Argentina, Global X) **0.59%** — [TrackInsight ARGT](https://www.trackinsight.com/en/fund/ARGT), [Yahoo Finance ARGT](https://finance.yahoo.com/quote/ARGT) (via search summary).
- VNM (Vietnam, VanEck) **0.66%** per [etfdb VNM](https://etfdb.com/etf/VNM/) vs **0.68%** per [PortfoliosLab VNM](https://portfolioslab.com/symbol/VNM). Sources conflict.
- DXJ (WisdomTree Japan Hedged Equity) **0.48%** net, as of 13 Oct 2026 — [WisdomTree DXJ](https://www.wisdomtree.com/investments/etfs/equity/dxj) (via search summary).
- HEWJ (iShares Currency Hedged MSCI Japan) **0.50%** — [Seeking Alpha HEWJ expenses](https://seekingalpha.com/symbol/HEWJ/expenses); [PortfolioMetrics DXJ vs HEWJ](https://portfoliometrics.net/etf-comparison/DXJ-HEWJ) (via search summary).
- Franklin FTSE country ETFs at their Nov 2017 launch:
  - **0.09%:** FLJP (Japan), FLGB (UK), FLKR (Korea), FLCA (Canada).
  - **0.19%:** FLBR (Brazil), FLMX (Mexico), FLTW (Taiwan).
  - Current pages confirm FLGB 0.09%, FLJP 0.09% and FLBR 0.19%. FLIN's (India) fee was not found.
  - Sources: [FA-Mag, Franklin to launch 16 passive ETFs](https://www.fa-mag.com/news/franklin-templeton-to-launch-16-passive-etfs-35497.html); [Seeking Alpha FLBR](https://seekingalpha.com/symbol/FLBR/expenses); [Seeking Alpha FLJP](https://seekingalpha.com/symbol/FLJP/expenses) (via search summary).

**ARGT concentration:**
- As of 2 Sep 2026, MercadoLibre (MELI) is **22.18%**, YPF **9.80%** and Vista Energy **7.22%**. The fund has 27 holdings and the top 10 are about **69%** of assets.
- Earlier snapshots put MELI at 21.84% (8 Jun 2026) and about 21.35% (Feb 2026).
- The index is the MSCI Daily All Argentina 25-50 (capped).
- Search-reported AUM ranged from about $795M to $867M across 2026 snapshots.
- Sources: [Robinhood ARGT page](https://robinhood.com/us/en/stocks/ARGT/); [TrackInsight ARGT](https://www.trackinsight.com/en/fund/ARGT) (via search summary).

**Live size, liquidity and quoted spreads (Robinhood API, 16 Oct 2026, ~12:07 ET).** The quoted spread is a single snapshot. "Fund size proxy" is shares outstanding × price.

| Ticker | Country / exposure | Quoted spread (bp of mid) | 30-day avg daily $ volume ($M) | Fund size proxy ($M) | First monthly bar in Robinhood history (listing proxy) |
|---|---|---|---|---|---|
| ARGT | Argentina | 79 | 13 | 701 | 2011-03 |
| INDA | India (MSCI) | 2 | 269 | 5,878 | 2012-02 |
| EPI | India (WisdomTree earnings-weighted) | 2 | 19 | 1,827 | 2008-02 |
| FLIN | India (Franklin FTSE) | 3 | 9 | 2,553 | 2018-02 |
| VNM | Vietnam (VanEck) | 6 | 6 | 460 | 2009-08 |
| EPOL | Poland | 4.5 | 22 | 984 | 2010-05 |
| EWJ | Japan | 2 | 374 | 23,399 | ≤1999 (data floor 1999-09) |
| FLJP | Japan (Franklin) | 2.5 | 38 | 4,195 | 2017-11 |
| DXJ | Japan, USD-hedged, dividend-weighted | 12 | 37 | 8,015 | 2006-06 |
| HEWJ | Japan, USD-hedged MSCI | 30 | 2 | 645 | 2014-02 |
| KSA | Saudi Arabia | 3 | 16 | 567 | 2015-09 |
| UAE | UAE | 5 | 6 | 307 | 2014-05 |
| EWW | Mexico | 7 | 91 | 1,466 | ≤1999 |
| FLMX | Mexico (Franklin) | 125 | 0.5 | 83 | 2017-11 |
| EWZ | Brazil | 2 | 1,782 | 13,335 | 2000-07 |
| FLBR | Brazil (Franklin) | 54 | 8 | 695 | 2017-11 |
| EIDO | Indonesia | 10 | 11 | 350 | 2010-05 |
| ECH | Chile | 24 | 24 | 920 | 2007-11 |
| EPU | Peru | 202 | 2 | 554 | 2009-06 |
| EWY | South Korea | 1 | 2,149 | 21,951 | 2000-05 |
| FLKR | South Korea (Franklin) | 16 | 46 | 1,566 | 2017-11 |
| EWT | Taiwan | 1 | 520 | 11,653 | 2000-06 |
| FLTW | Taiwan (Franklin) | 23 | 96 | 4,813 | 2017-11 |
| EIS | Israel | 211 | 5 | 873 | 2008-03 |
| GREK | Greece (Global X) | 130 | 4 | 328 | 2011-12 |
| TUR | Turkey | 6 | 7 | 156 | 2008-03 |
| EZA | South Africa | 31 | 10 | 469 | 2003-02 |
| MCHI | China | 2 | 92 | 5,791 | 2011-03 |
| EWG / EWU / EWC / EWA / EWL | Germany / UK / Canada / Australia / Switzerland | 2–3.5 | 36–110 | 1,204–7,364 | ≤1999 |
| EWQ / EWI / EWP / EWN / EWD | France / Italy / Spain / Netherlands / Sweden | 2–33 | 8–43 | 338–2,037 | ≤1999 |
| EWS | Singapore | 3 | 57 | 1,136 | ≤1999 |
| FLCA / FLGB | Canada / UK (Franklin) | 15 / 38 | 3 / 2 | 859 / 872 | 2017-11 |
| NORW / EDEN / ENZL / EIRL | Norway / Denmark / NZ / Ireland | 27 / 191 / 62 / n.a. | 0.6 / 0.9 / 0.5 / ~0.3 | 92 / 179 / 66 / 76 | — |
| Benchmarks: SPY / EFA / EEM / VWO / EMXC | — | 0.1 / 1 / 1.6 / 1.7 / 1.1 | 33,103 / 1,507 / 1,233 / 425 / 203 | 810,021 / 77,137 / 29,233 / 122,792 / 24,660 | — |

Source: computed from [Robinhood](https://robinhood.com/us/en/stocks/EWZ/) quotes and fundamentals, pulled 2026-10-16. The "first bar" column is a proxy for listing date. Robinhood monthly history does not go back before 1999-09, so "≤1999" means the fund is older than that.

**ADR alternatives confirmed active on 16 Oct 2026, with quoted spreads (bp)** ([Robinhood quotes](https://robinhood.com/us/en/stocks/YPF/)):
- **Argentina-linked:** YPF 18, GGAL 25, BMA 66, VIST 21, PAM 29, MELI 12.
- **Brazil:** PBR 4, ITUB 11, NU 7.
- **Mexico:** AMX 4, FMX 6.
- **Chile:** SQM 20.
- **Peru-linked:** BAP 27, SCCO 19.
- **India:** HDB 4, IBN 3.
- **Taiwan:** TSM 6.
- **Korea:** KB 37, PKX 41, SHG 69.

### Inferences
- **Fees and liquidity favor different funds.** Where a Franklin FTSE fund exists (Japan, Korea, Taiwan, Brazil, Mexico, Canada, UK), its expense ratio is 40–50 bp a year below iShares. But FLMX, FLBR and FLGB have 38–125 bp snapshot spreads and under $10M of daily volume. For a buy-and-hold investor who uses limit orders, the fee saving usually outweighs a one-time spread. For a tactical, frequently rebalanced tilt, the iShares fund's tighter spread may be cheaper.
- **Argentina exposure through ARGT is partly a Latin American e-commerce bet.** MELI is about 22% and is a US-listed company with most of its revenue outside Argentina. Energy names (YPF and Vista, about 17%) overlap with the energy build-out theme.
- **Thinly traded funds need limit orders and should be traded while the local market is open.** EPU, EIS, GREK, EDEN, ENZL and NORW showed 60–210 bp snapshot spreads, so market orders are costly. EIS's wide quote may reflect the Israeli market being closed on Friday. That is an inference I could not verify.
- **Small funds carry closure risk.** Funds under about $100M (MADE, ENZL, NORW, FLMX) face higher closure risk. DMCY's 2026 closure (Section 2) is a recent precedent.

### Gaps
- **Not verified from any source in this session, so check at the issuer:**
  - Expense ratios for EWW, EIDO, ECH, EPU, EIS, EWY, EWG/EWU/EWC/EWA/EWL, EPI, FLIN, EEM and VWO.
  - Exact inception dates. The Robinhood first-bar month is only a proxy.
- **Typical values from my prior knowledge, NOT verified this session:**
  - iShares MSCI single-country funds: about 0.50% (developed markets) to 0.59% (most EM).
  - EPI about 0.84–0.85%; EEM about 0.70%; VWO about 0.07–0.08%.
  - Older iShares country funds launched in March 1996 (EWJ, EWW, EWG, EWU, EWC, EWA, EWL, etc.). EEM launched April 2003.
- **Top-10 holdings and concentration** were not retrieved for EWT, EWY, INDA, EWZ, KSA, EPOL and others, because the search budget ran out. Expect EWT to be dominated by TSMC and EWY by Samsung Electronics and SK Hynix (unverified). Check the issuer holdings files.
- **Average spreads** come from one intraday snapshot, not a 30- or 60-day median. Issuer pages (iShares lists a "30 Day Median Bid/Ask Spread") would be better.

---

## 2. Freedom-weighted and related products (FRDM, DMCY, ex-China EM)

### Takeaway
- **FRDM** (Life + Liberty Freedom 100 Emerging Markets ETF; 0.49% expense ratio; about $3.3B) is the only live US-listed fund that weights countries by personal and economic freedom.
  - Since its May 2019 launch it has roughly doubled EEM's price return: **about +178% vs +64%**, May-2019 to Sep-2026 closes, price-only, my calculation.
  - Most of the gap came in 2025–2026.
  - It carries higher volatility (23% vs 18%).
- **DMCY** (democracy-weighted) was **liquidated in February 2026**.
- No developed-market freedom-weighted ETF was found.
- **Ex-China EM** is the closest cheap substitute: EMXC at 0.25%, plus Vanguard VEXC and other newer funds.

### Cited Findings

**FRDM methodology:**
- Country selection and weights come from composite freedom scores built from **83 quantitative variables** of personal and economic freedom. Data comes from the **Fraser Institute and Cato Institute** (Human Freedom Index).
- Companies with **≥20% state ownership are excluded**.
- The starting universe is 24 countries.
- Source: [FRDM factsheet, 30 Sep 2024](https://etfarchitect.com/wp-content/uploads/compliance/etf/factsheets/FRDM_Factsheet.pdf) (via search summary).
- **Earlier versions differ:** the 2019 launch documents describe **79 factors** and 26 countries ([Cboe circular IC 2019-077](https://cdn.cboe.com/resources/regulation/circulars/products/IC_2019-077.pdf), via search summary). The current methodology version is unconfirmed.
- Freedom, not market size, sets country weights. The index holds about 100 stocks. The data comes from a joint Fraser/Cato/Friedrich Naumann Foundation project covering about 160 countries — [etf.com, "Human Freedoms Make Better Markets"](https://www.etf.com/sections/news/human-freedoms-make-better-markets); [Validea interview with Perth Tolle](https://blog.validea.com/five-questions-investing-in-human-freedom-with-perth-tolle/) (via search summary).
- FRDM effectively excludes China and holds only a small India weight — [etf.com spotlight](https://www.etf.com/sections/features/frdm-emerging-markets-etf-ex-china-india) (via search summary). An older article said Taiwan was nearly a quarter of holdings; that is likely out of date ([etf.com](https://www.etf.com/sections/news/human-freedoms-make-better-markets), via search summary).
- **Benchmark:** MSCI Emerging Markets.

**FRDM costs and size:**
- Expense ratio **0.49%** — [TrackInsight FRDM](https://www.trackinsight.com/en/fund/FRDM); [ETF Central FRDM](https://www.etfcentral.com/fund/FRDM) (via search summary).
- AUM about **$3.25B** (17 Jul 2026, [ETF Central](https://www.etfcentral.com/fund/FRDM), via search summary). The Robinhood size proxy was **$3.32B** on 16 Oct 2026.
- Holdings count 124–125 in 2026 snapshots ([TrackInsight](https://www.trackinsight.com/en/fund/FRDM), via search summary).
- Quoted spread **21.7 bp** vs EEM's 1.6 bp; about $21M traded per day ([Robinhood](https://robinhood.com/us/en/stocks/FRDM/), 16 Oct 2026).
- Trailing P/E 15.1, P/B 2.67, dividend yield 2.55%, 30-day SEC yield 1.73%. For comparison, EEM: P/E 15.2, P/B 2.36, yield 1.76% ([Robinhood](https://robinhood.com/us/en/stocks/FRDM/), 16 Oct 2026).

**FRDM issuer-reported return:** annualized NAV total return since inception of **9.32% as of 30 Sep 2024** ([FRDM factsheet](https://etfarchitect.com/wp-content/uploads/compliance/etf/factsheets/FRDM_Factsheet.pdf), via search summary).

**FRDM vs EEM, VWO, EMXC, SPY (my calculation, price-only, monthly closes, May-2019 close to Sep-2026 close; source data [Robinhood](https://robinhood.com/us/en/stocks/FRDM/)):**

| | Cumulative | Annualized | Ann. vol | Max drawdown (monthly) | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 YTD (to 30 Sep) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FRDM | +177.9% | 15.0% | 23.0% | -30.3% (Dec-19→Mar-20) | +15.4% | +3.9% | -16.7% | +19.3% | -0.7% | +56.9% | +36.5% |
| EEM | +64.1% | 7.0% | 17.8% | -38.0% (Jun-21→Oct-22) | +15.2% | -5.5% | -22.4% | +6.1% | +4.0% | +30.8% | +22.1% |
| VWO | +45.9% | 5.3% | 16.1% | -34.7% | +12.7% | -1.3% | -21.2% | +5.4% | +7.2% | +22.1% | +10.3% |
| EMXC | +108.5% | 10.5% | 20.1% | -30.8% | +11.0% | +6.6% | -21.7% | +16.7% | +0.1% | +31.1% | +36.3% |
| SPY | +177.0% | 14.9% | 16.5% | -24.8% | +16.2% | +27.0% | -19.5% | +24.3% | +23.3% | +16.4% | +11.8% |

- **FRDM's monthly-return statistics since inception:** correlation with SPY 0.76, beta to SPY 1.06, correlation with EEM 0.90 (my calculation from the same data).
- **Third-party claims (unaudited):**
  - A Life + Liberty-affiliated blog claims FRDM gained about 76% from 2019 to 2025, with VWO about half of that and EEM trailing. It is promotional, with an unstated end date and return basis — [TrendLabs, "Building a World B. Free Portfolio"](https://trendlabs.com/building-a-world-b-free-portfolio/) (via search summary).
  - ETF.com put 2025 YTD (partial year) at FRDM +9.2% vs EEM +6.7% — [etf.com](https://www.etf.com/sections/features/frdm-emerging-markets-etf-ex-china-india) (via search summary).

**DMCY (Democracy International Fund):**
- Its board approved liquidation in January 2026. The last trading day was 16 or 17 Feb 2026 (filings differ), and the fund liquidated on or about 23 Feb 2026 — [SEC 497 supplement](https://www.sec.gov/Archives/edgar/data/1593547/000139834426001230/fp0097323-1_497.htm); [SEC 497K](https://www.sec.gov/Archives/edgar/data/1593547/000139834426001735/fp0097408-2_497k.htm); [Seeking Alpha, DMCY defunct](https://seekingalpha.com/symbol/DMCY-DEFUNCT-612340); [Investing.com](https://uk.investing.com/etfs/dmcy) (via search summary).
- It tracked the EIU Democracy Index and peaked at about $10M in assets. Commentary attributes the closure to weak relative performance — [Ultumus Insights](https://insights.ultumus.com/feed/the-market-has-spoken-and-it-turns-out-nobody-wanted-to-invest-in-democracy) (via search summary).
- Robinhood returned "not found" for DMCY on 16 Oct 2026.

**Other "freedom" products:** a Robinhood instrument search for "freedom ETF" returned only FRDM and **MBOX ("Freedom Day Dividend ETF")**. MBOX is an actively managed US dividend-growth fund, not a freedom-weighted country fund ([Robinhood search and fundamentals](https://robinhood.com/us/en/stocks/MBOX/), 16 Oct 2026).

**Ex-China EM alternatives** (Robinhood search and fundamentals, 16 Oct 2026; size proxy, trailing P/E):
- **EMXC (iShares):** about $24.7B; P/E 15.8; expense ratio **0.25%** per [ETFValuer](https://etfvaluer.com/etf/EMXC) (via search summary). First monthly bar 2017-07.
- **XCEM (Columbia):** about $2.0B; P/E 17.3.
- **VEXC (Vanguard):** about $281M; P/E 18.7.
- **DEXC (Dimensional, active):** about $279M.
- **STXE (Strive):** about $133M.
- **KEMX (KraneShares):** about $126M; average volume about 8k shares/day.
- **Also listed:** PEMX (Putnam) and MEMX (Matthews, active).

### Inferences
- **FRDM led before 2025, but the gap widened sharply after.** From the May-2019 close to the Dec-2024 close (price-only, backed out from the table above), FRDM was about +30%, EMXC about +17%, VWO about +8% and EEM about +3%. SPY was about +113% over the same span. The gap then widened sharply in 2025 (+56.9% vs +30.8%) and 2026 YTD (+36.5% vs +22.1%), when Korea, Taiwan, Poland, Chile and Peru rallied and China and India lagged. EMXC also captured much of that (+31.1% and +36.3%). A meaningful part of FRDM's edge is likely the "no China, little India" tilt plus the SOE exclusion, not freedom scores alone; FRDM still beat ex-China EMXC by about 13 points through 2024. The evidence comes from one ~7-year sample and is not a robust test.
- **FRDM is the most direct ready-made product, with trade-offs.** It costs about 0.24% a year more than EMXC and has wider spreads. Since inception it has had higher volatility than EEM and a beta to SPY of 1.06, versus EEM's 0.77 over the 10-year window.
- **There is no developed-market freedom ETF.** An investor wanting a developed-market analogue would need to build it from single-country ETFs (e.g., Switzerland, NZ, Ireland, Denmark, Canada, Australia score high on freedom indices — unverified here).
- **Demand for values-based country weighting has been thin.** DMCY's closure at about $10M peak assets suggests limited retail demand and that such funds can disappear.

### Gaps
- FRDM's **current country weights and top holdings**, and whether the methodology is now 79 or 83 variables, were not retrievable (issuer site unreachable).
- **NAV total-return** comparisons with dividends (FRDM vs EEM/VWO/EMXC) were not obtained. My figures are price-only. FRDM's yield (2.55%) is higher than EEM's (1.76%), so total-return gaps would be slightly larger.
- Whether Life + Liberty plans a developed-market or "World B. Free" product: the TrendLabs title hints at one, but it is unconfirmed.

---

## 3. Thematic and sector routes for "energy and industrial build-out"

### Takeaway
There are liquid, US-listed, country-agnostic ways to own energy, nuclear/uranium, grid, infrastructure/reshoring and defense. But most are **dominated by US companies and behave like US equity beta**: correlation with SPY is 0.75–0.87 for GRID, PAVE, XLI and PPA. They overlap with a country thesis only where country funds are energy- or industrial-heavy (Argentina, Saudi Arabia, UAE, Norway, Brazil). Energy and uranium funds are the least correlated with SPY but have the deepest drawdowns (XOP -81%, URA -93% peak-to-trough historically).

### Cited Findings

**Expense ratios found (via search summary):**
- URA **0.69%** — [etfdb URA](https://etfdb.com/etf/URA/); [Global X URA](https://www.globalxetfs.com/funds/ura).
- NLR **0.52%** (per a recent article) vs **0.56%** (other source) — [24/7 Wall St., 1 Oct 2026](https://247wallst.com/investing/etf/2026/10/01/forget-uras-concentration-this-nuclear-fund-spreads-the-bet-across-utilities-miners-and-reactor-builders/); [etfdb NLR](https://etfdb.com/etf/NLR/). Sources conflict.
- GRID **0.56%**, about $12B — [Green Stocks Research](https://greenstocksresearch.com/energy-transition-etfs-1bn-assets/).
- XLE **0.08%** — [Globe and Mail, XLE vs NLR](https://www.theglobeandmail.com/investing/markets/stocks/NLR-A/pressreleases/3388206/which-is-the-better-energy-etf-for-the-ai-era-state-street-s-xle-or-vaneck-s-nuclear-nlr/).

**Live data (Robinhood API, 16 Oct 2026):**

| Ticker | Theme | Size proxy ($M) | Snapshot spread (bp) | Trailing P/E | Div. yield | First bar |
|---|---|---|---|---|---|---|
| XLE | US large-cap energy (S&P 500) | 44,155 | 1.5 | 18.1 | 2.34% | ≤1999 |
| XOP | US E&P, equal-weight | 4,432 | n.a. | 14.1 | 1.81% | — |
| AMLP | US energy-infrastructure MLPs | 12,600 | n.a. | 13.2 | 6.27% | — |
| URA | Uranium miners + nuclear components (global) | 4,990 | 2.8 | not meaningful (1,079) | 0.60% | 2010-11 |
| URNM | Uranium miners | 1,687 | n.a. | negative | 0.30% | — |
| NLR | Global nuclear energy (utilities, miners, builders) | 3,219 | 51 | 156.6 | 0.93% | 2007-08 |
| NUKZ | Nuclear fuel and energy (global) | 643 | n.a. | 28.4 | n.a. | — |
| GRID | Global smart-grid / electrical infrastructure | 11,553 | 15 | 27.1 | 1.50% | 2009-11 |
| PAVE | US infrastructure development | 13,536 | 1.9 | 28.6 | 0.99% | 2017-03 |
| AIRR | US industrial renaissance (multifactor) | 8,644 | 6.0 | 27.6 | 0.70% | 2014-03 |
| XLI | US industrials (S&P 500) | 30,561 | 1.8 | 26.2 | 1.14% | ≤1999 |
| MADE | US manufacturing (iShares) | 56 | 8.8 | 29.0 | 1.08% | 2024-07 |
| WELD | Active US manufacturing and reshoring (Tema) | 250 | n.a. | 37.1 | 0.62% | — |
| ITA | US aerospace and defense | 12,056 | 4.8 | 34.1 | 0.81% | 2006-05 |
| PPA | US defense, homeland security, space | 7,407 | n.a. | 31.3 | 0.86% | — |
| SHLD | Global defense tech, top 50 pure plays | 6,439 | 26 | 29.0 | 1.21% | 2023-09 |

Source: [Robinhood](https://robinhood.com/us/en/stocks/GRID/), pulled 2026-10-16. RSHO (reshoring) returned "not found" on Robinhood that day.

**Behavior, Nov-2016 to Sep-2026** (my calculation from [Robinhood](https://robinhood.com/us/en/stocks/XLE/) monthly bars; price-only):

| Ticker | Ann. price return | Ann. vol | Max DD (window) | Corr. SPY | Beta | 2025 | 2026 YTD |
|---|---|---|---|---|---|---|---|
| XLE | 5.2% | 30.4% | -62.8% | 0.54 | 1.06 | +4.4% | +37.6% |
| XOP | 0.7% | 42.2% | -81.0% | 0.53 | 1.44 | -4.6% | +42.0% |
| AMLP | -1.8% | 30.1% | -73.6% | 0.59 | 1.14 | -2.4% | +10.3% |
| URA | 12.6% | 37.3% | -49.9% | 0.47 | 1.13 | +59.6% | -6.7% |
| NLR | 8.4% | 23.0% | -33.3% | 0.49 | 0.73 | +52.7% | -16.7% |
| GRID | 16.3% | 21.8% | -26.7% | 0.87 | 1.21 | +28.2% | +15.7% |
| PAVE | 14.3% | 22.9% | -30.9% | 0.86 | 1.25 | +18.3% | +9.9% |
| XLI | 10.5% | 19.2% | -28.1% | 0.87 | 1.08 | +17.7% | +7.6% |
| AIRR | 16.5% | 24.7% | -31.1% | 0.79 | 1.26 | +27.6% | +5.0% |
| ITA | 11.4% | 21.8% | -37.9% | 0.71 | 1.00 | +47.7% | -3.5% |
| PPA | 14.0% | 19.5% | -29.4% | 0.75 | 0.94 | +36.5% | -1.3% |
| SHLD (since 2023-09) | 35.2% | 21.8% | -20.6% | 0.19 | 0.33 | +73.2% | -7.3% |
| SPY (reference) | 13.5% | 15.6% | -24.8% | 1.00 | 1.00 | +16.4% | +11.8% |

**Long-history drawdowns, monthly closes since listing** ([Robinhood](https://robinhood.com/us/en/stocks/URA/) data, my calculation):
- URA **-93.1%** (Feb-2011 → Mar-2020)
- XLE **-71.3%** (Jun-2014 → Oct-2020)
- NLR **-70.4%** (Oct-2007 → Mar-2020)
- ITA **-54.3%** (GFC)
- XLI **-58.4%** (GFC)

**Current state, 16 Oct 2026:**
- URA and NLR are near 52-week lows (URA low $34.31 and NLR low $91.88, both on 15 Oct 2026). Their 52-week highs were $62.28 (URA, 29 Jan 2026) and $167.58 (NLR, 16 Oct 2025).
- XLE hit a 52-week high of $67.90 on 15 Oct 2026.
- Source: [Robinhood fundamentals](https://robinhood.com/us/en/stocks/URA/).

### Inferences
- **Overlap with the country thesis is partial:**
  - Energy-heavy country funds (KSA, UAE, NORW, ARGT through YPF/Vista, EWZ through Petrobras) already carry energy exposure.
  - Adding XLE or XOP mainly adds **US** shale/major exposure, a US "production build-out" bet, not a foreign-country bet.
  - GRID and SHLD are global, so they add some non-US industrial exposure (likely European and Asian electrical-equipment and defense names). Their holdings were not verified here.
- **Grid, infrastructure and industrial funds are high-beta US equity in practice.** GRID, PAVE, XLI and AIRR have 0.79–0.87 correlation and 1.08–1.26 beta to SPY, so they add little diversification for a US-heavy investor. Valuations are full: trailing P/E 26–29 vs SPY 26.6.
- **Uranium and nuclear funds are the most cyclical and narrative-driven.** URA's -93% historical drawdown, and URA and NLR each being about -43% below their 52-week highs on 16 Oct 2026, support small position sizes.
- **AMLP has unusual tax treatment.** AMLP, as an MLP fund, is widely understood to be structured as a C-corporation that pays entity-level tax. That is unverified here. Its tax character differs from that of ordinary RICs.

### Gaps
- Expense ratios for PAVE, AIRR, XLI, ITA, PPA, SHLD, MADE, WELD, XOP, AMLP, URNM and NUKZ were not verified this session. From prior knowledge, unverified: PAVE about 0.47%, AIRR about 0.70%, XLI about 0.08%, ITA about 0.38–0.40%, SHLD about 0.50%, MADE about 0.40%.
- No LNG-specific ETF was checked. LNG exposure is usually via single stocks (e.g., Cheniere) or within XLE/AMLP.
- Country composition of GRID, URA, NLR and SHLD was not retrieved, so the size of the overlap with country ETFs is unquantified.

---

## 4. Current valuations by country (CAPE, forward P/E, dividend yields) — which "pro-market" countries already re-rated

### Takeaway
As of September 2026 (Siblis Research, MSCI-based country CAPE):
- **Most expensive:** Taiwan (46.7), the US (35.9), Japan (35.4), Korea (31.8) and India (28.7).
- **Cheapest:** Turkey (6.8), Brazil (14.9), Indonesia (15.0), Mexico (17.5) and Saudi Arabia (18.7).

Several of the "pro-market reform" stories have already re-rated sharply:
- Poland's CAPE rose from 15.7 to 20.3 in 12 months.
- Taiwan's CAPE rose from 27.6 to 46.7.
- Korea's EWY is up 91% in 2025 and 88% in 2026 YTD.
- Argentina (ARGT) is +21%/year over 5 years.
- Greece and Peru each rose 70–83% in 2025.

Brazil, Mexico, the Gulf and the UK screen cheapest on forward and trailing earnings among liquid markets.

### Cited Findings

**CAPE by country, Siblis Research, end of Sep 2026 (Sep 2025 in parentheses)** — [Siblis CAPE Ratios by Country 2026](https://siblisresearch.com/data/cape-ratios-by-country/) (via search summary):
- Taiwan **46.7** (27.6)
- United States **35.9** (34.6)
- Japan **35.4**
- South Korea **31.8**
- India **28.7**
- Germany **22.9** (23.9)
- Poland **20.3** (15.7)
- United Kingdom **19.6** (19.4)
- Saudi Arabia **18.7** (21.4)
- Mexico **17.5** (18.2)
- Indonesia **15.0** (21.8)
- Brazil **14.9** (13.8)
- Turkey **6.8** (the lowest in the table)

The next update is scheduled for 10 Nov 2026. Chile was not in the retrieved results. Siblis's Europe page gives the same Germany, UK and Poland figures (22.89, 19.60, 20.27) — [Siblis Europe P/E](https://siblisresearch.com/data/europe-pe-ratio/) (via search summary).

**Cross-check (older, different source):** Research Affiliates data to 30 Sep 2025, as reported by Monevator, puts the US at **39.3**, India **34.6** and Brazil **9.6** (the lowest major market) — [Monevator, CAPE ratio by country](https://monevator.com/cape-ratio-by-country/) (via search summary). This conflicts in level with Siblis because of methodology and date. [World Population Review](https://worldpopulationreview.com/country-rankings/cape-ratio-by-country) lists India 35.76 and US 32.87 as "2025" figures. It looks dated and should be treated with caution.

**Predictive power:** Keimling (StarCapital) found that country CAPE explained about 48% of subsequent 10–15-year returns in developed markets, and that explanatory power varies by country and period — [Monevator summarizing Keimling](https://monevator.com/cape-ratio-by-country/); [Keimling, SSRN 2736423](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2736423) (via search summary). StarCapital's own current country table was not retrieved.

**Forward and trailing P/E (Siblis, via search summary; dates differ):**
- **India (Nifty 50), Aug 2026:** trailing 21.76, forward **19.86** — [Siblis EM valuations](https://siblisresearch.com/data/emerging-markets-valuations/). Robeco puts MSCI India at about **20.2x forward** at end-May 2026 — [Robeco, Oct 2026](https://www.robeco.com/en-us/insights/2026/10/emerging-markets-investing-why-country-selection-matters).
- **Brazil:** forward about **8.4x** (Aug 2026) and about 8.1x (30 Jun 2026) per [Siblis](https://siblisresearch.com/data/emerging-markets-valuations/). Robeco puts it at **9.7x** at end-May 2026, "under 10x forward earnings with a dividend yield above 5%" — [Robeco](https://www.robeco.com/en-us/insights/2026/10/emerging-markets-investing-why-country-selection-matters).
- **South Korea:** Siblis forward P/E **5.36** in Aug 2026, against trailing 12.30. It was 7.82 in June. East Capital's earlier outlook had about **10.1x** 2026 forward — [Siblis](https://siblisresearch.com/data/emerging-markets-valuations/); [East Capital Outlook 2026](https://www.eastcapital.com/media/0jahq4gx/east-capital-outlook-2026.pdf). The very low forward multiple reflects steep upward revisions to memory-chip earnings estimates.
- **Poland:** East Capital describes it qualitatively as trading at "a significant discount" to Western and Northern Europe ([East Capital](https://www.eastcapital.com/insights/why-invest-in-emerging-and-frontier-markets-in-2026)). No forward P/E was found for Poland or Mexico.
- **EM aggregate:** forward P/E **11.61** at 30 Jun 2026 ([Siblis](https://siblisresearch.com/data/emerging-markets-valuations/)).
- **Developed markets, Aug 2026 (trailing / forward)** — [Siblis P/E by country](https://siblisresearch.com/data/pe-ratios-by-country/):
  - Canada 21.11 / 16.46
  - Australia 20.57 / 18.71
  - Japan (Nikkei 225) 19.04 / 16.62
  - Germany (DAX) 17.91 / 15.06
  - UK (FTSE 100) 14.98 / 12.56
- **Developed markets, Sep 2026 updates (trailing / forward)** — [Siblis Japan](https://siblisresearch.com/data/japan-nikkei-pe-cape/); [Siblis Europe](https://siblisresearch.com/data/europe-pe-ratio/):
  - Japan 19.05 / 15.73
  - Germany 17.19 / 14.34
  - UK 14.73 / 12.02

**Dividend yields by country (Siblis, trailing, Jun 2026):** Australia 3.33%, UK 3.04%, Germany 2.59%, Canada 2.09%, Japan 1.96% — [Siblis Dividend Yields by Country](https://siblisresearch.com/data/global-dividend-yields/) (via search summary).

**ETF-level trailing P/E, P/B and dividend yield (Robinhood, 16 Oct 2026; methodology undisclosed)** — [Robinhood](https://robinhood.com/us/en/stocks/EWZ/):

| ETF | P/E | P/B | Div. yield | 52-week range and position (16 Oct 2026) |
|---|---|---|---|---|
| ARGT | 19.2 | 1.64 | 1.04% | 69.60–103.97; ~88 |
| INDA / EPI / FLIN | 20.0 / 15.0 / 20.4 | 3.12 / 2.25 / 3.11 | 1.32 / 1.80 / 1.32% | INDA high 55.50 (Oct-25); ~47.8 |
| VNM | 12.5 | 1.79 | 2.03% | 16.22–19.85; ~16.5 |
| EPOL | 10.8 | 1.98 | 3.87% | 32.51–46.03; ~44.6 (near high) |
| EWJ / DXJ / HEWJ / FLJP | 18.6 / 16.7 / 11.4 / 18.0 | 2.07 / 1.66 / 1.27 / 1.93 | 1.67 / 2.20 / 2.52 / 1.76% | all near 52-week highs (6 Oct 2026) |
| KSA | 15.9 | 1.91 | 3.84% | 35.04–41.18; at 52-week low |
| UAE | 9.8 | 1.63 | 4.99% | 17.29–22.29; ~19.6 |
| EWW / FLMX | 12.1 / 11.4 | 1.76 / 1.78 | 4.02 / 4.03% | 64.77–81.65; ~74.6 |
| EWZ / FLBR | 11.1 / 10.7 | 2.17 / 1.97 | 3.48 / 3.84% | EWZ 29.07–43.90; ~41.8 (near high) |
| EIDO | 9.0 | 1.33 | 6.72% | 52-week low today; **-13.4% on 16 Oct 2026** (11.68 → 10.115) |
| ECH | 13.0 | 1.30 | 3.18% | 33.03–47.85; ~37.3 |
| EPU | 14.3 | 2.61 | 2.39% | 59.08–95.28; ~90 |
| EWY / FLKR | 11.9 / 12.2 | 1.67 / 1.52 | 1.03 / 1.08% | EWY 86.90–220.89; ~153 (-31% from Jun-2026 high) |
| EWT / FLTW | 27.9 / 27.7 | 4.25 / 4.13 | 1.56% | EWT 59.96–118.47; ~107 |
| EIS | 17.4 | 2.38 | 2.30% | 97.50–138.85; ~120 |
| GREK | 12.5 | 1.65 | 2.99% | 60.53–87.68; ~80.6 |
| TUR | 11.1 | 1.01 | 2.28% | 31.72–43.98; ~32.6 |
| EZA | 9.7 | 2.00 | 3.91% | 60.27–81.76; ~65 |
| MCHI | 13.4 | 1.47 | 1.53% | 49.88–65.84; ~51 |
| EWG / EWU / EWC / EWA / EWL | 15.7 / 14.8 / 19.1 / 18.9 / 23.4 | 1.86 / 2.30 / 2.62 / 2.61 / 4.22 | 2.58 / 3.01 / 2.12 / 3.38 / 2.67% | — |
| EWQ / EWI / EWP / EWN / EWD / EWS / EWH | 15.4 / 20.1 / 14.2 / 20.1 / 14.5 / 18.4 / 12.9 | — | 3.25 / 4.37 / 2.90 / 2.17 / 2.08 / 3.35 / 3.80% | — |
| NORW / EDEN / ENZL / EIRL | 12.7 / 16.0 / 24.9 / 15.1 | — | 4.59 / 1.98 / 3.42 / 3.37% | — |
| FRDM / EEM / VWO / EMXC | 15.1 / 15.2 / 17.8 / 15.8 | 2.67 / 2.36 / 2.27 / 2.78 | 2.55 / 1.76 / 1.94 / 1.82% | — |
| SPY / EFA / ACWX | 26.6 / 17.1 / 16.6 | 5.61 / 2.29 / 2.34 | 1.01 / 2.56 / 2.26% | — |

**Recent price momentum (re-rating evidence), price-only returns, my calculation from [Robinhood](https://robinhood.com/us/en/stocks/EWY/) monthly bars.** Each entry gives 2025 calendar year; 2026 YTD to 30 Sep; and 5-year annualized (Sep-21 to Sep-26).
- **Korea (EWY):** +91.0%; +88.0%; +17.8%/yr
- **Taiwan (EWT):** +22.7%; +77.7%; +12.7%/yr
- **Poland (EPOL):** +68.6%; +25.9%; +15.1%/yr
- **Peru (EPU):** +82.6%; +22.6%; +27.5%/yr
- **Greece (GREK):** +69.9%; +30.0%; +26.0%/yr
- **Argentina (ARGT):** +10.6%; -5.7%; +20.9%/yr
- **Spain (EWP):** +73.6%; +9.8%; +17.0%/yr
- **Italy (EWI):** +51.0%; +8.1%; +13.2%/yr
- **Japan:** EWJ +20.3%; +20.7%. DXJ (hedged) +30.7%; +25.2%; +23.4%/yr.
- **Brazil (EWZ):** +41.1%; +17.2%; +3.0%/yr
- **Mexico (EWW):** +48.1%; +2.5%; +8.1%/yr
- **Chile (ECH):** +61.3%; -6.4%; +7.8%/yr
- **India (INDA):** +2.7%; -13.6%; -0.8%/yr
- **Vietnam (VNM):** +66.2%; -11.2%; -2.5%/yr
- **Indonesia (EIDO):** +1.2%; -37.3%; -11.6%/yr
- **Saudi Arabia (KSA):** -10.8%; -0.2%; -2.8%/yr
- **UAE:** +16.2%; +5.0%; +6.2%/yr
- **Turkey (TUR):** -4.0%; -1.8%; +9.7%/yr
- **China (MCHI):** +28.2%; -13.1%; -5.0%/yr
- **US (SPY):** +16.4%; +11.8%; +12.2%/yr

### Inferences
- **Already re-rated** (pro-market or reform narratives with large multi-year gains and higher multiples):
  - Taiwan: highest CAPE in the world; EWT P/E about 28.
  - Korea: CAPE 31.8 after EWY's price rose about 3.6x from end-2024 to Sep-2026 (+91% in 2025, then +88%), and about 2.5x from its Nov-2025 low to its Jun-2026 high. Forward P/E is low because chip earnings surged, which makes it highly cyclical: EWY is already about -31% from its June 2026 high.
  - India: CAPE 28.7 and P/E about 20, even after a 2026 drawdown.
  - Japan: CAPE 35.4; the governance-reform story is largely priced.
  - Poland: CAPE jumped 4.6 points in a year, but the ETF's trailing P/E is still about 11.
  - Argentina: ARGT P/E about 19, driven by MELI.
  - Greece and Peru: large 2025 rallies.
- **Still cheap on the available metrics:** Brazil (CAPE 14.9, forward about 8–10x, yield 3.5–5%), Mexico (CAPE 17.5, ETF P/E about 12, yield about 4%), UAE (ETF P/E 9.8, yield about 5%), Saudi Arabia (CAPE 18.7, ETF at its 52-week low), Chile (ETF P/E 13), the UK (forward about 12) and Turkey (CAPE 6.8).
- **Cheap markets are mostly not "moving toward more freedom."** Brazil, Mexico, Turkey, Indonesia and South Africa are often classed as having governance or policy-direction risk. So a "freedom-improving and cheap" overlap may be small. This needs to be checked against the country-trend research notes.
- **Indonesia's sell-off (-37% YTD, -13% on 16 Oct 2026)** looks like an active policy or market event. Its cause is unknown here, and that cause matters for any "moving the other way" classification.

### Gaps
- **Siblis CAPE was not retrieved** for Argentina, Vietnam, UAE, Chile, Peru, Israel, Greece, Canada, Australia, Switzerland, France, Italy, Spain, China or South Africa. Research Affiliates' current (2026) country CAPEs and StarCapital's country table were also not retrieved.
- **No consistent same-date forward P/E table** across all candidate countries. MSCI index factsheets and the Yardeni "MSCI forward P/E by country" series would fill this.
- **ETF-level P/E methodology on Robinhood is undisclosed.** For example, URA shows 1,079 and URNM a negative value. Use those figures only for rough comparison.
- **The cause of EIDO's 16 Oct 2026 drop** could not be researched (search budget exhausted).

---

## 5. Taxes and frictions for a US taxable investor

### Takeaway
- **Use US-domiciled ETFs; avoid foreign-domiciled funds.** US-domiciled 1940-Act ETFs (all tickers above) can pass foreign taxes through to shareholders for the **foreign tax credit**: the fund must hold more than 50% of its assets in foreign stock and make the Section 853 election, and the taxes are reported on 1099-DIV Box 7. Foreign-domiciled funds (UCITS etc.) are generally **PFICs**, with punitive default taxation and Form 8621 filing, and should be avoided.
- **Qualified-dividend status varies widely by country.** In 2025 iShares reported **0% QDI** for EWZ, INDA, KSA and EWT, but 100% for EWW and 91% for EPOL. This matters for after-tax yield.
- **Currency-hedged funds** (DXJ, HEWJ) can make large taxable distributions when the hedge gains: HEWJ paid about $12 on a roughly $27 share in Dec 2022.
- **Sanctions and capital controls can trap capital.** The 2022 Russia ETF episode is the template: trading was halted and delisted within days, and liquidation proceeds trickled out over almost three years.

### Cited Findings

**Foreign tax credit:**
- Form 1116 can be skipped if all foreign income is passive, qualified foreign taxes are at most **$300 ($600 joint)**, and all of it is reported on payee statements such as 1099-DIV. Electing this means no carryback or carryover of that year's foreign taxes, and the tax must still be a creditable income tax — [IRS, Foreign Tax Credit – How to figure the credit](https://www.irs.gov/node/178); [IRS Instructions for Form 1116 (2025)](https://www.irs.gov/instructions/i1116) (via search summary). Publication 514's RIC-specific wording was not retrieved.
- **RIC pass-through:** a regulated investment company with **more than half its assets in foreign stock** may elect to pass foreign taxes through to shareholders, who then treat them as taxes they paid. If the fund elects, it cannot itself claim the deduction or credit — [26 USC §853 (text via policyrisk.com)](https://policyrisk.com/us-code/title/26/section/853); [26 CFR 1.853-3](https://www.gpo.gov/fdsys/pkg/CFR-2014-title26-vol9/pdf/CFR-2014-title26-vol9-sec1-853-3.pdf) (via search summary).
- Shareholders use **1099-DIV Box 7** for foreign taxes paid and compute foreign-source income as a percentage of Box 1a — [Allspring tax info](https://www.allspringglobal.com/resources/dividends-and-tax/foreign-tax-credits/); [Boston Partners 2025 tax insert](https://www.bostonpartners.com/uploads/2026/01/b7a9b7767fbc836c2f10eb99bc52842e/boston-partners-tax-insert-2025.pdf) (via search summary).
- FRDM's trust (EA Series Trust) stated it intends to pass foreign taxes through under §853 for the year ended 31 Dec 2025 — [FRDM 2025 tax insert](https://etfarchitect.com/wp-content/uploads/compliance/etf/misc/FRDM.Tax.Insert.pdf) (via search summary).

**Qualified dividends (QDI):**
- **iShares 2025 QDI percentages** — [iShares 2025 QDI summary](https://www.ishares.com/us/literature/tax-information/2025-ishares-qdi-summary-stamped.pdf); [BlackRock copy](https://www.blackrock.com/us/individual/literature/tax-information/2025-ishares-qdi-summary-stamped.pdf) (via search summary):
  - **EWW 100.00%**
  - **EPOL 90.83%**
  - **EWY 58.04%**
  - **EWJ 56.42%**
  - **EWT 0.00%**, **EWZ 0.00%**, **KSA 0.00%**, **INDA 0.00%**
  - UAE was not found.
  - The amounts actually reportable are governed by 1099-DIV Box 1b ([2021 QDI summary](https://www.ishares.com/us/literature/tax-information/2021-qdi-summary.pdf)).
- **Treaty test:** IRS **Notice 2024-11** replaced Notice 2011-64 as the list of treaties that satisfy the qualified-dividend treaty test. It **added Chile** (treaty in force 19 Dec 2023) and **removed Russia and Hungary** — [IRS Notice 2024-11](https://www.eitc.irs.gov/pub/irs-drop/n-24-11.pdf); [EY tax alert](https://www.ey.com/en_gl/technical/tax-alerts/us-treasury-adds-chile-to-the-list-of-treaty-countries-that-meet) (via search summary).
- **Readily-tradable test:** a non-treaty foreign corporation's dividend can still be qualified if the stock, **or an ADR**, is readily tradable on an established US market such as the NYSE or Nasdaq (Notice 2003-71) — [IRS Notice 2011-64 / 2024-11 context](https://www.eitc.irs.gov/pub/irs-drop/n-11-64.pdf); [The Tax Adviser](https://www.thetaxadviser.com/issues/2015/nov/capitalizing-on-lower-dividend-tax-rate/) (via search summary).
- **A PFIC is never a qualified foreign corporation** (same sources).

**PFICs:**
- Foreign-domiciled pooled funds, including UCITS, are generally PFICs for US persons.
- Form 8621 is generally required **per PFIC, per year**.
- The default "excess distribution" regime taxes gains at the **top ordinary rate, spread back over the holding period, plus interest**.
- A QEF election needs a PFIC Annual Information Statement, which many retail funds do not provide. Mark-to-market is available only for marketable stock and taxes unrealized gains each year.
- Sources: [HCVT PFIC reporting](https://www.hcvt.com/alertarticle-PFIC-Reporting-for-Direct-and-Indirect-Investors); [Beancount PFIC guide, May 2026](https://beancount.io/blog/2026/05/07/pfic-form-8621-foreign-mutual-funds-etfs-us-investors-tax-trap-guide); [TaxesForExpats](https://www.taxesforexpats.com/faq/foreign-investments-in-pfic-taxation.html) (via search summary). These are practitioner sources, not IRS primary text.

**Currency-hedged funds:**
- HEWJ uses forward currency contracts to neutralize yen exposure.
- It paid a distribution of about **$12.04/share** (ex-date 2 Dec 2022) when the share price was about $27, followed by $0.08 on 23 Dec 2022 — [Digrin HEWJ dividends](https://www.digrin.com/stocks/detail/HEWJ/); [BlackRock HEWJ](https://www.blackrock.com/us/individual/products/259624/) (via search summary). The tax character (ordinary vs capital gain) was not confirmed.
- My Robinhood monthly data shows HEWJ's price falling from 40.54 (Nov 2022 close) to 26.16 (Dec 2022 close), consistent with that distribution.
- DXJ is also USD-hedged and dividend/export-weighted ([Robinhood DXJ description](https://robinhood.com/us/en/stocks/DXJ/)).

**Sanctions and closure precedent (Russia 2022):**
- iShares **paused ERUS creations on 1 Mar 2022**, and ERUS trading was halted on NYSE Arca in early March 2022. Reasons cited were MSCI's removal of Russian stocks and the closure of Moscow's market — [etf.com, iShares halts creations in ERUS](https://www.etf.com/sections/news/ishares-halts-new-creations-erus); [etf.com, iShares' Russia fund closed to trading](https://www.etf.com/sections/daily-etf-watch/ishares-russia-fund-closed-trading) (via search summary).
- **Cboe halted and then delisted VanEck RSX on 4 Mar 2022.** Creations and redemptions were suspended and the board approved liquidation. Liquidating distributions began **12 Jan 2023**, continued through 2023–2024, and the latest listed was **24 Dec 2024** — [VanEck RSX page](https://www.vaneck.com/Funds/RSX.aspx); [etf.com, VanEck to dissolve Russia ETFs](https://www.etf.com/sections/news/vaneck-dissolve-russia-etfs-war-hobbles-investments) (via search summary). ERUS's final liquidation details were not found.

### Inferences
- **Account location:** holding high-withholding country ETFs in the **taxable** account (not an IRA) preserves the foreign tax credit. Withholding suffered inside an IRA cannot be credited (standard rule, not re-verified this session). The $300/$600 de minimis rule means small positions may not need Form 1116.
- **After-tax yield differs sharply between funds that look similar pre-tax.** EWZ (3.5% yield, 0% QDI) vs EWW (4.0%, 100% QDI) is an example. Brazilian, Saudi, Indian and Taiwanese dividends received through these ETFs were taxed at ordinary rates in 2025. **US-listed ADRs** of the same companies (PBR, ITUB, TSM, HDB, IBN, etc.) may qualify under the readily-tradable test. That is a reason to consider ADRs for income-heavy, non-treaty markets. Verify each issuer's PFIC status and 1099 coding.
- **Hedged Japan funds can create unplanned tax bills.** When the yen weakens, hedge gains can produce large taxable distributions (HEWJ 2022) even if the investor does not sell. Unhedged EWJ/FLJP avoid this but carry yen risk.
- **Sanction and capital-control risk is a real tail.** In 2022 Russian ETF holders could not exit after the halt; the only option was to wait for liquidation proceeds over about two years. Countries with geopolitical or sanction exposure (China, Turkey, Gulf states, Israel in wartime) or a history of capital controls (Argentina, China) carry this tail risk. Position sizing, not hedging, is the practical defense.
- **Never buy the non-US version.** All the vehicles above are US-domiciled. The PFIC regime applies if an investor buys London-, Frankfurt- or Mumbai-listed funds directly.

### Gaps
- **Country dividend withholding rates** (statutory or treaty, as applied to a US RIC) were not retrieved; the search budget ran out. Typical figures from prior knowledge, **unverified and possibly outdated**:
  - Japan 15.315%
  - Korea 22% (15% treaty)
  - Taiwan 21%
  - India 20% plus surcharge
  - Mexico 10%
  - Poland 19% (15% treaty)
  - Chile 35% gross, with a credit
  - Saudi Arabia 5%; UAE 0%
  - Argentina 7%; Peru 5%
  - Indonesia 20% (treaty 15%)
  - Vietnam 0% for corporate investors
  - Israel 25%
  - Brazil: historically 0% on dividends (15% on JCP). A 2025 Brazilian reform reportedly introduced a 10% withholding on dividends to non-residents from 2026; **unverified**.
- **Other issuer tax data not obtained:** iShares per-fund 2025 foreign-tax-paid and foreign-source-income tables, and QDI percentages for UAE, EIDO, ECH, EPU, EIS, ARGT, VNM, FRDM and the Franklin funds.
- **The tax character of HEWJ's 2022 distribution** was not confirmed. My expectation that currency-forward gains generally produce ordinary income under IRC §988 is unverified.
- **Argentina's capital-control status** (the "cepo") and any 2025–2026 MSCI or FTSE reclassifications (Argentina, Vietnam, Greece, Korea) were not researched before the search budget ran out.
- **Schwab- or Robinhood-specific restrictions** (e.g., on some foreign ordinary shares or OTC ADRs) were not checked. All ETFs and ADRs listed returned active quotes on Robinhood on 16 Oct 2026.

---

## 6. Risk management: volatility, drawdowns, correlation with the S&P 500, sizing

### Takeaway
Over Nov-2016 to Sep-2026, single-country EM ETFs had **annualized volatility of about 17–34%** vs SPY's 15.6%. Their **maximum drawdowns within that decade were about -32% to -63%**. Since inception, several fell **70–80%** peak to trough (EWZ -80%, TUR -76%, GREK -77%, ECH -73%, EPOL -73%, EWY -71%). Correlation with SPY ranges from about 0.3 (Turkey, China, Saudi Arabia) to 0.6–0.8 (Korea, Taiwan, Israel). Developed markets run 0.7–0.85. This favors small, volatility-scaled positions within a total sleeve budget.

### Cited Findings

**10-year statistics, Nov-2016 close to Sep-2026 close** (118 monthly returns where available), split-adjusted, price-only. My calculation from [Robinhood](https://robinhood.com/us/en/stocks/EWZ/) monthly bars. "Max DD" uses monthly closes, which understate intra-month troughs.

| Ticker | Ann. price return | Ann. vol | Max DD (window) | Peak → trough | Worst 12m | Corr. SPY | Beta SPY | Corr. EEM |
|---|---|---|---|---|---|---|---|---|
| SPY | 13.5% | 15.6% | -24.8% | 2021-12→2022-09 | -19.5% | 1.00 | 1.00 | 0.70 |
| EFA | 6.3% | 15.1% | -30.7% | 2021-05→2022-09 | -28.2% | 0.82 | 0.80 | 0.80 |
| EEM | 6.6% | 17.2% | -38.0% | 2021-06→2022-10 | -32.9% | 0.70 | 0.77 | 1.00 |
| VWO | 5.1% | 15.7% | -34.7% | 2021-06→2022-10 | -30.0% | 0.70 | 0.71 | 0.97 |
| EMXC (from 2017-07) | 7.6% | 19.1% | -38.2% | 2018-01→2020-03 | -27.2% | 0.76 | 0.91 | 0.91 |
| FRDM (from 2019-05) | 15.0% | 23.0% | -30.3% | 2019-12→2020-03 | -24.0% | 0.76 | 1.06 | 0.90 |
| ARGT | 14.3% | 33.7% | -56.9% | 2018-01→2020-03 | -40.5% | 0.53 | 1.14 | 0.45 |
| INDA | 5.8% | 17.5% | -35.3% | 2018-01→2020-03 | -31.6% | 0.55 | 0.62 | 0.58 |
| EPI | 7.4% | 19.0% | -43.9% | 2018-01→2020-03 | -38.5% | 0.55 | 0.68 | 0.59 |
| VNM | 2.4% | 23.5% | -47.0% | 2021-12→2023-02 | -44.3% | 0.65 | 0.98 | 0.69 |
| EPOL | 10.1% | 27.5% | -63.3% | 2018-01→2022-09 | -50.9% | 0.63 | 1.11 | 0.64 |
| EWJ | 7.0% | 14.0% | -30.5% | 2021-09→2022-09 | -30.5% | 0.74 | 0.67 | 0.76 |
| DXJ (hedged) | 14.1% | 14.8% | -30.2% | 2018-01→2020-03 | -21.8% | 0.61 | 0.58 | 0.56 |
| KSA | 3.9% | 17.4% | -31.9% | 2019-04→2020-03 | -28.1% | 0.41 | 0.46 | 0.33 |
| UAE | 2.4% | 18.0% | -47.3% | 2017-08→2020-03 | -36.4% | 0.52 | 0.60 | 0.46 |
| EWW | 5.0% | 23.9% | -49.8% | 2017-08→2020-03 | -36.6% | 0.59 | 0.90 | 0.58 |
| EWZ | 1.1% | 31.0% | -52.6% | 2019-12→2024-12 | -42.5% | 0.44 | 0.88 | 0.52 |
| EIDO | -6.8% | 22.1% | -62.0% | 2018-01→2026-06 | -42.6% | 0.48 | 0.69 | 0.46 |
| ECH | 0.1% | 26.6% | -61.3% | 2018-01→2020-03 | -49.8% | 0.49 | 0.85 | 0.64 |
| EPU | 10.9% | 24.4% | -47.3% | 2018-04→2020-03 | -41.3% | 0.54 | 0.84 | 0.69 |
| EWY | 13.4% | 30.9% | -49.2% | 2021-06→2022-09 | -41.3% | 0.62 | 1.22 | 0.83 |
| EWT | 14.1% | 23.0% | -39.7% | 2021-12→2022-12 | -39.7% | 0.67 | 0.99 | 0.81 |
| EIS | 10.2% | 20.3% | -40.2% | 2021-12→2023-10 | -28.1% | 0.81 | 1.06 | 0.62 |
| MCHI | 1.2% | 24.5% | -59.3% | 2021-01→2022-10 | -48.6% | 0.32 | 0.51 | 0.70 |
| EZA | 2.4% | 25.2% | -60.7% | 2018-01→2020-03 | -45.8% | 0.58 | 0.93 | 0.76 |
| TUR | 0.6% | 33.2% | -61.6% | 2017-08→2020-10 | -56.3% | 0.28 | 0.60 | 0.36 |
| GREK | 13.9% | 25.4% | -49.6% | 2018-01→2020-03 | -39.5% | 0.59 | 0.97 | 0.55 |
| THD | -0.2% | 20.9% | -49.8% | 2018-02→2025-06 | -34.9% | 0.53 | 0.71 | 0.65 |
| EPHE | -3.5% | 19.5% | -43.1% | 2017-12→2022-09 | -32.8% | 0.45 | 0.57 | 0.60 |
| EWG | 5.3% | 20.1% | -44.8% | 2021-05→2022-09 | -40.0% | 0.77 | 1.00 | 0.74 |
| EWU | 4.5% | 15.8% | -35.7% | 2018-01→2020-03 | -27.7% | 0.73 | 0.74 | 0.71 |
| EWC | 8.6% | 17.5% | -26.9% | 2019-12→2020-03 | -20.9% | 0.85 | 0.95 | 0.70 |
| EWA | 3.4% | 19.1% | -34.6% | 2018-01→2020-03 | -27.8% | 0.79 | 0.98 | 0.71 |
| EWL | 7.8% | 14.9% | -29.0% | 2021-12→2022-09 | -21.5% | 0.73 | 0.69 | 0.64 |
| EWI | 10.6% | 21.7% | -38.5% | 2018-01→2020-03 | -32.1% | 0.68 | 0.95 | 0.70 |
| EWP | 9.1% | 20.8% | -44.3% | 2018-01→2022-09 | -30.7% | 0.62 | 0.82 | 0.67 |
| EWN | 11.4% | 19.9% | -42.3% | 2021-08→2022-09 | -37.9% | 0.82 | 1.04 | 0.81 |
| NORW | 6.7% | 19.3% | -32.9% | 2021-08→2022-09 | -29.3% | 0.61 | 0.75 | 0.54 |
| ENZL | 0.7% | 17.8% | -39.5% | 2020-12→2022-09 | -33.3% | 0.73 | 0.84 | 0.69 |

**Long-history drawdowns, monthly closes from the first available bar** (Robinhood data floor is 1999-09). [Robinhood](https://robinhood.com/us/en/stocks/EWZ/) data, my calculation:
- **GFC (Oct-2007 → Mar-2009):**
  - SPY -52.2%; EFA -59.7%; EEM -61.9%; VWO -64.3%
  - EWY -70.8%; EWZ -65.5%; EWW -62.1%; EWT -62.5%; EWG -62.8%; EWU -63.2%
  - EPI -61.6%; TUR -60.3%; EZA -60.0%; EWJ -48.7%; EIS -48.6%
- **Worst ever since listing:**
  - **EWZ -80.0%** (May-2008 → Jan-2016)
  - TUR -76.0%; GREK -76.8%; ECH -72.8%; EPOL -72.8%; EWY -70.8%; EIDO -68.2% (Apr-2013 → Jun-2026, and lower again after 16 Oct 2026)
  - UAE -64.4%; VNM -64.0%; EPU -61.1%; MCHI -59.3%; ARGT -56.9%; INDA -35.3%; KSA -31.9%
- **COVID (Jan → Mar 2020), monthly closes:**
  - EWZ -46.2%; GREK -40.2%; EIDO -39.1%; EWW -38.2%; EZA -36.5%; ARGT -35.6%
  - vs SPY -19.9%, EEM -19.0%
- **2022 (Dec-2021 → Oct-2022):**
  - EPOL -48.9%; VNM -45.0%; MCHI -43.3%; EWG -39.8%; EWY -39.2%; EWT -37.5%
  - vs SPY -24.8%
- **Hedging effect in 2022:** currency-hedged Japan held up far better than unhedged. DXJ -5.1% and HEWJ -6.9% (Dec-2021 → Oct-2022) vs EWJ -27.0% and FLJP -26.2%.
- **Intraday event risk:** on 16 Oct 2026 EIDO traded **-13.4%** intraday versus the prior close, and EWY and EWT were down about 2% ([Robinhood quotes](https://robinhood.com/us/en/stocks/EIDO/)).

### Inferences
- **Volatility-scaled sizing gives very different weights.** With country vols of 15–34% and correlations with SPY of 0.3–0.85, a risk budget (e.g., each country contributing equal volatility) gives very unequal dollar weights. A 30%-vol fund such as EWZ, ARGT, EWY or TUR gets about half the dollar weight of a 15%-vol fund such as EWJ, EWL or EWC for the same risk. Equal-weighting a basket of EM single-country funds concentrates risk in the most volatile markets.
- **Concentration compounds single-name risk.** Plausible caps for a tactical overlay are a total sleeve (e.g., 10–25% of equities) and per-country caps (e.g., 2–5%, with a smaller cap for the most volatile or least liquid funds). These are illustrative heuristics, not sourced recommendations. Funds like ARGT (MELI 22%), EWT and EWY carry single-stock risk on top of country risk.
- **Diversification benefit is real but uneven.** EM single-country funds with correlation of 0.3–0.55 to SPY (TUR, MCHI, KSA, EWZ, ARGT, INDA, EIDO) diversify more than developed-Europe or Canada funds (0.73–0.85). They also carry the largest crash and capital-control tails.
- **The hedge decision changes outcomes.** The 2022 Japan gap (DXJ -5% vs EWJ -27%) shows currency is a major return driver in single-country funds. A "pro-market reform" thesis can be overwhelmed by FX moves.
- **Momentum context:** many "already re-rated" markets (Korea, Taiwan, Poland, Peru, Greece) are near or just off record highs after 50–90% one-year gains. Historical drawdowns of 40–70% for these same funds suggest staging entries and setting rebalance bands. This is a risk observation, not a forecast.

### Gaps
- **Total-return (dividend-inclusive) risk and return statistics** were not computed. Robinhood monthly bars are price-only, and dividend adjustment is available only for intraday intervals.
- **Monthly-close drawdowns understate intra-month troughs.** Daily data would give deeper figures for March 2020 in particular.
- **No published third-party source** (Morningstar or the issuers) was retrieved to cross-check these volatility, drawdown and correlation figures.
- **Rolling correlations were not computed,** so whether correlations rise in crises (2008, 2020, 2022) is unquantified here. EM correlations with US equities typically rise in sell-offs; that is unverified here.
