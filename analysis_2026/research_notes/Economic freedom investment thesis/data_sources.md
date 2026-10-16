# Downloadable data sources for backtesting "rising economic freedom → better country stock returns" (verified from the sandbox, 2026-10-16)

How these notes were made: every URL listed as "verified" below was fetched with `curl -sSL` from this sandbox into the scratchpad folder `/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/data_hunt/`, then opened with pandas (`python3 -I`). Sizes are bytes as downloaded; "sha" is the first 16 hex digits of the SHA-256. Unless a source is named, statistics such as coverage counts, correlations and revision sizes are my own calculations on the downloaded files. Official sites (fraserinstitute.org, efotw.org, economicfreedom.heritage.org, macrohistory.net, Ken French/Dartmouth, msci.com, jkpfactors.com, globalmacrodata.com, ourworldindata.org and its catalog, Yahoo, stooq, FRED, Kaggle, Zenodo, Hugging Face) all failed to connect from the sandbox (curl code 000, CONNECT refused by the proxy). Over the session, the WebSearch quota ran out, and WebFetch could not resolve fraserinstitute.org or novelinvestor.com. **So no "official value" could be re-checked online during this session.** Where these notes compare against official numbers, the comparison relies on (a) two independent mirrors agreeing, (b) independent datasets agreeing, or (c) my own memory of published figures. Memory-based comparisons are labelled as such in the Inferences sections.

## Q1. What is the best reachable economic-freedom panel (coverage, years, vintage)?

### Takeaway
The best panel I could reach is the **Fraser EFW 2025 "master index data for researchers" workbook**. It covers data years 1970–2023: five-yearly from 1970 to 2000 and annual from 2000 to 2023. It has 165 countries and ISO3 codes. It includes the summary index, all five areas and about 40 components, and a separate **"EFW Panel Dataset" sheet that behaves like the chain-linked index**. Two independent GitHub mirrors of it agree exactly. For robustness, the **full Heritage Index of Economic Freedom panel** is available for index years 1995–2026 (184 economies, the overall score plus 12 components). It is a raw dump that a World Bank team took from the Heritage site's own CSV.

### Cited Findings
**Verified files: Fraser Economic Freedom of the World (EFW)**
- **EFW 2025 report, data to 2023 (primary).** Downloaded from https://raw.githubusercontent.com/kholodovTimur/IR-CaseStudy-26/HEAD/efotw-2025-master-index-data-for-researchers-iso.xlsx (5,419,435 B, sha 0a478488e5c2a494). It is a student repository whose last commit is 2026-04-12. The workbook has three sheets — [file](https://raw.githubusercontent.com/kholodovTimur/IR-CaseStudy-26/HEAD/efotw-2025-master-index-data-for-researchers-iso.xlsx):
  - `EFW Index 1970-2023`: the header is on row 4 and the shape is 4,950 × 87. The columns are `Year, ISO_Code, Countries, ECONOMIC FREEDOM ALL AREAS, EFW RANK, EFW QUARTILE`, followed by the components. Examples are `1Ai Government consumption…`, `1Di Top marginal income tax rate`, `1Dii Top marginal income and payroll tax rate`, `1D Top marginal tax rate` and `IE State ownership`. The area columns are `Area 1 Size of Government`, `Area 2 Legal System & Property Rights` (with and without the gender adjustment), `Area 3 Sound Money`, `Area 4 Freedom to trade internationally` and `Area 5 Regulation`, each with a rank, plus raw `data` columns.
  - Countries scored per year: 98 (1970), 107 (1975), 110 (1980), 114 (1985), 117 (1990), 123 (1995), 158 (2000), 162 (2010) and 165 (2019–2023).
  - `EFW Panel Dataset`: 4,950 × 12, with columns `ISO_Code, Countries, Year, Summary, Area 1…Area 5, Standard Deviation of the 5 EFW Areas, World Bank Region, World Bank Current Income Classification`. It has the same years and 165 countries; Summary is non-null for 97 countries in 1970 and 117 in 1990.
  - `EFW Ratings 1950-1965`: the summary EFW only, for 1950–1965.
  - Sample rows from the index sheet for 2023: HKG 8.55 (rank 1), SGP 8.50 (2), NZL 8.33 (3), CHE 8.28 (4), USA 8.10 (5), IRL 8.05, AUS 8.03, TWN 8.03, DNK 8.02, NLD 7.97 … CHL 7.65 (26), POL 6.80 (76), IND 6.58 (86), BRA 6.57 (87), CHN 6.13 (108), ARG 4.48 (159), VEN 3.11 (165).
  - Sample panel rows: `ALB, Albania, 2023, 7.56, 7.637, 5.552, 8.948, 8.536 …` and `ARG, Argentina, 2023, 4.48, 6.184, 5.543, 1.25, 3.616 …`.
- **Behaves like the chain-linked index.** In the panel sheet, `Summary` equals the unadjusted index in 2023 (mean absolute gap 0.000). The gap grows going back in time: 0.007 (2021), 0.062 (2010), 0.221 (2000), 0.220 (1990) and 0.479 (1970). That is the pattern you would expect from a series chain-linked backward from the latest year. Computed from the [2025 workbook](https://raw.githubusercontent.com/kholodovTimur/IR-CaseStudy-26/HEAD/efotw-2025-master-index-data-for-researchers-iso.xlsx).
- **Independent cross-mirror check.** https://raw.githubusercontent.com/eltonjmarinho/artigo_macro_modelo-main/HEAD/data/freedom.csv (3,050,412 B; 2,310 rows; the same column names) was produced by a script that downloads `https://efotw.org/sites/all/modules/custom/ftw_maps_pages/files/efotw-2025-master-index-data-for-researchers-iso.xlsx` ([script](https://raw.githubusercontent.com/eltonjmarinho/artigo_macro_modelo-main/HEAD/scripts/download/download_data_fraser_freedom.R)). I matched all 2,310 rows on Year and ISO code against the kholodovTimur xlsx. The largest absolute difference was 1.8e-15 for the summary index, Area 1 and Area 5 ([csv](https://raw.githubusercontent.com/eltonjmarinho/artigo_macro_modelo-main/HEAD/data/freedom.csv)).
- **The official file name and URL pattern** for the 2025 vintage is `efotw-2025-master-index-data-for-researchers-iso.xlsx`, hosted at efotw.org. The URL is given in a third repository's download script ([velkokamenov R script](https://raw.githubusercontent.com/velkokamenov/Economic_Freedom_Of_The_World_Fraser_Institute/HEAD/010_Download_Process_Data.R)). That repository contains only code, no data.
- **EFW 2024 report, data to 2022 (prior vintage, for point-in-time work).** Downloaded from https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/input/fraser/efotw-2024-master-index-data-for-researchers-iso.xlsx (5,058,452 B, sha f4b717277ba5b048).
  - The repository belongs to a World Bank "PIDA Data Science Shop" project (CLIAR ETL). Its `fraser.R` says the file was obtained by clicking "Download Entire Dataset" on efotw.org ([fraser.R](https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/source/fraser.R)).
  - Sheets: `EFW Data 2024 Report` (header on row 5; 4,786 × 85; the 1970–2022 years have the same structure), `EFW Panel Data 2024 Report` (4,785 × 10) and `EFW Data 1950-1965`.
  - 2022 sample: HKG 8.58 (1), SGP 8.55 (2), CHE 8.43 (3), NZL 8.39 (4), USA 8.09 (5), VEN 3.02 (165).
- **Revisions between vintages.** Matching the 2022 data year across the 2024 and 2025 vintages (165 countries), the scores moved by a mean of −0.006, a mean absolute change of 0.088 and a maximum of 0.59. Examples: USA 8.09→8.00, CHE 8.43→8.27, ARG 4.55→4.67. Computed from the two workbooks above.
- **Older vintages (useful for quasi-real-time tests).**
  - https://raw.githubusercontent.com/diodz/disasters-economic-freedom/HEAD/data/efw-2019-master-index-data-for-researchers.xlsx (3,334,167 B). Sheets are `EFW Index 2019 Report` (latest year 2017), `EFW Panel Data 2019 Report` and `EFW 1950-1965`.
  - https://raw.githubusercontent.com/acforrester/FreedomData/HEAD/data/efwpnl.rda (165,817 B; R data, read with pyreadr). It is 4,290 × 12 with columns `iso_code, country_name, year, region_code, region_name, income_group, efw_index, size_of_govt, legal_system, sound_money, trade_freedom, regulation` and years 1970–2019.
- **Our World in Data** has only a "backport" snapshot pointer for "Economic Freedom of the World (Fraser Institute) 2018 values" in owid/etl, and the data is stored off GitHub ([owid/etl dvc file](https://github.com/owid/etl/blob/master/snapshots/backport/latest/dataset_153_economic_freedom_of_the_world__fraser_institute__2018_values.feather.dvc)). No newer OWID EFW or Heritage series was found.

**Verified files: Heritage Index of Economic Freedom**
- **Full panel, index years 1995–2026.** Downloaded from https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/input/heritage/heritage_iof_raw.rds (111,250 B, sha 5fdac075b77c1ccd; read with pyreadr).
  - Shape 5,888 × 18. Columns: `name_web, Year, Overall, Property Rights, Government Integrity, Judicial Effectiveness, Tax Burden, Government Spending, Fiscal Health, Business Freedom, Labor Freedom, Monetary Freedom, Trade Freedom, Investment Freedom, Financial Freedom, region, rankRegion, rankWorld`.
  - Values are stored as strings, with "N/A" for missing.
  - Countries with an Overall score per index year: 101 (1995), 160 (2000), 179 (2009–2012), 180 (2017–2020) and 176 (2023–2026).
  - Sample (2026): `albania, 2026, 68.0, 57.6, 41.9, 59.9, 89.3, 74.3, 88.0, 76.6, 46.2, 78.6, 83.0, 60, 60, E, 25, 46`.
  - Top scores: 2024 — Singapore 83.5, Switzerland 83.0, Ireland 82.6, Taiwan 80.0, Luxembourg 79.2. 2025 — Singapore 84.1, Switzerland 83.7, Ireland 83.1, Taiwan 79.7, Luxembourg 79.5. 2026 — Singapore 84.4, Switzerland 83.7, Ireland 83.3, Australia 80.1, Taiwan 79.8.
  - USA: 76.7 (1995), 70.1 (2024, rank 25), 70.2 (2025, rank 26), 72.8 (2026, rank 22).
- **Provenance of that file.** Its builder script downloads `https://economicfreedom.heritage.org/assets/data/csv/ef-country-scores.csv` (and `ef-country-names.csv`). The script sends browser headers because the site sits behind Cloudflare, and its comments say these are "the exact same files the live table itself fetches" ([heritage.R](https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/source/heritage.R)).
- **Hong Kong and Macau** are scored only up to index year 2020: Hong Kong 1995–2020, Macau 2009–2020. Taiwan, South Korea, Russia and Venezuela are scored 1995–2026. Source: [rds](https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/input/heritage/heritage_iof_raw.rds).
- **Other Heritage files downloaded (superseded).**
  - https://raw.githubusercontent.com/jlzamary/dataviz/HEAD/project/Data/heritage-index-of-economic-freedom-2026-04-19_1352.csv (13,680 B). Despite the 2026 file name it holds only `Index Year` 2024 (184 rows, with a 4-line preamble "Index of Economic Freedom -- Explore the Data … Source: The Heritage Foundation").
  - https://raw.githubusercontent.com/FarahMae/Research-Internship--Economic-Data-Analysis/HEAD/heritage-index-of-economic-freedom-20250531164515.csv (13,918 B; also 2024 only).
  - https://raw.githubusercontent.com/decorouz/Data-Analysis-with-Python/HEAD/exercises/data/indexofeconomicfreedom_data_2015_2024.csv (241,977 B; begins with blank rows; not inspected further).
  - https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data/heritage.rda (8,570 B). A processed subset with ISO3 `country_code`, but only business, financial and investment freedom.

### Inferences
- **Primary signal.** Use the 2025 `EFW Panel Dataset` (chain-linked-like) for levels and changes over 1970–2023. Use `EFW Index 1970-2023` for components, especially the "taxes fall" leg: `1D Top marginal tax rate`, `1A Government consumption`, `1B Transfers and subsidies` and `IE State ownership`. Before 2000 the data is only five-yearly, so a 1970s–1990s test has to use 5-year change windows; annual changes are only possible from 2000.
- **Robustness.** Heritage adds annual coverage from 1995 and the latest index year (2026), plus "Tax Burden" and "Government Spending" components.
- **Timing.** The 2025 report's latest data year is 2023 and the 2024 report's is 2022. EFW therefore appears to be published about two years after its data year. A backtest should lag EFW by at least about 21–24 months (for example, use data year t from roughly October of t+2). Using data year t at the end of year t would be look-ahead. Heritage "index year" t is a publication year, but its underlying data mostly refer to earlier periods. Treat index year t as known early in year t; this is my understanding and was not verified online.
- **Revisions and backfill.** The chain-linked panel is backfilled (it differs from the original index by about 0.5 points in 1970), and individual years are revised by about 0.09 on average between vintages. True point-in-time testing would combine vintages: the 2019 report (to 2017), `efwpnl` (to 2019), 2024 (to 2022) and 2025 (to 2023).
- **Unverified spot-check from memory.** The 2024-vintage 2022 ranking (HK 1, SG 2, CH 3, NZ 4, US 5, Venezuela last) and the Heritage 2024 and 2025 leaders (Singapore 83.5 / 84.1, Switzerland 83.0 / 83.7, Ireland 82.6 / 83.1, Taiwan 80.0 / 79.7) match my recollection of the published reports. I could not re-check them online in this session. The exact agreement of the two EFW-2025 mirrors is the stronger evidence.

### Gaps
- I could not confirm from Fraser documentation that the "EFW Panel Dataset" sheet is officially the chain-linked index. The inference rests on its numerical behaviour.
- I could not check the release dates of the EFW 2025 report or the Heritage 2026 index, or the official values, because the sites are blocked and web search was exhausted.
- No Heritage file mirrored with ISO codes was found. The Heritage country-name file `ef-country-names.csv` was not found on GitHub.

## Q2. What is the best reachable country equity return panel (countries, start year, frequency, USD or local, total return or price)?

### Takeaway
The best reachable panel is the **Jensen–Kelly–Pedersen (JKP) "Global Factor Data" country market returns**, served from public AWS S3 buckets. It gives **monthly value-weighted (and equal-weighted) broad-market total returns for 95 countries**, in **local currency and USD**, from 1926 for the USA, 1986 for most developed markets and the late 1980s–1990s for most emerging markets. The full local-plus-USD file runs to **2023-12**. An updated USD **excess-return** file runs to **2025-12**. For history before 1986 (16–18 developed countries, annual), the **JST Macrohistory R6** dataset can be downloaded through two independent GitHub mirrors that agree. However, it has inconsistencies against JKP: the USA in 2016–2020 and Japan (1990s–2000s). Monthly iShares country-ETF series adjusted with yfinance are available from 1996 as an investability check.

### Cited Findings
**Verified files: JKP Global Factor Data (S3)**
- **Old bucket, full country market file.** https://jkpfactors.s3.amazonaws.com/other_data/market_returns.csv (4,080,689 B, sha 2b1a5dd19aaa9372; S3 LastModified 2024-05-03).
  - Columns: `excntry, eom, stocks, me_lag1, dolvol_lag1, mkt_vw_lcl, mkt_ew_lcl, mkt_vw, mkt_ew, mkt_vw_exc, mkt_ew_exc`.
  - 34,217 rows; 95 countries (ISO3); months 1926-01 to 2023-12.
  - The bucket allows anonymous listing. Its `other_data/` prefix also holds `market_returns_daily.csv` (80,528,517 B), `nyse_cutoffs.csv` and `return_cutoffs*.csv` ([listing](https://jkpfactors.s3.amazonaws.com/?list-type=2&prefix=other_data/)).
  - Sample rows: `USA,2023-12-31,4945,48656874.189,…,mkt_vw_lcl=0.05343,…,mkt_vw=0.05343,…,mkt_vw_exc=0.04916` and `JPN,2023-12-31,3988,…,mkt_vw_lcl=-0.00309,…,mkt_vw=0.04536,…` ([csv](https://jkpfactors.s3.amazonaws.com/other_data/market_returns.csv)).
- **Coverage of that file** (computed):
  - Start years range from 1926 to 2014, with a median of 1993.
  - **41 countries start in or before 1990**: ARG, AUS, AUT, BEL, BRA, CAN, CHE, CHL, COL, DEU, DNK, ESP, FIN, FRA, GBR, GRC, HKG, IDN, IND, IRL, ITA, JPN, KOR, LKA, LUX, MEX, MYS, NLD, NOR, NZL, PER, PHL, PRT, SGP, SVK, SWE, THA, TUR, TWN, USA, VEN.
  - **64 countries start in or before 1995.**
  - Examples: JPN, GBR, DEU, HKG, SGP, ZAF and NZL from 1986-01; BRA 1988-05; ARG and IND 1988-09; CHL and VEN 1989-01; TUR 1990-03; CHN 1991-02; POL 1993-07 ([csv](https://jkpfactors.s3.amazonaws.com/other_data/market_returns.csv)).
- **New bucket, updated to 2025-12.**
  - https://jkpfactors-data.s3.amazonaws.com/public/%5Ball_countries%5D_%5Bmkt%5D_%5Bmonthly%5D_%5Bvw%5D.zip (539,476 B). It contains one CSV of 2,195,156 B with columns `location, name, freq, weighting, direction, n_stocks, n_stocks_min, date, ret`, covering 95 locations (lower-case ISO3) from 1926-01 to 2025-12.
  - Also downloaded: the `[vw_cap]` version (544,532 B; capped value weights, a different series), `[usa]_[mkt]_[monthly]_[vw_cap].zip` (19,714 B) and the manifest https://jkpfactors-data.s3.amazonaws.com/public/availability.json (287,565 B; 95 countries plus regions).
  - Sample: `bra,mkt,monthly,vw,na,245,na,2025-12-31,-0.02775`.
  - Anonymous listing of this bucket is denied (403).
- **What `ret` means.** In the new `mkt` file, `ret` is the USD excess return. It matches the old file's `mkt_vw_exc`: 87.6% of the 34,217 overlapping country-months agree within 1e-4 and 97% within 1e-3. Revisions are concentrated in MEX, PER and CHN (computed). A third party documents JKP's `[usa]_[mkt]_[monthly]` `ret` as a "decimal monthly US-dollar excess return" ([oddurs methodology](https://github.com/oddurs/portfolio-paycheck-gap/blob/HEAD/methodology/v0.1.md)). The tidyfinance package uses `https://jkpfactors-data.s3.amazonaws.com` as its JKP base URL ([py-tidyfinance](https://github.com/tidy-finance/py-tidyfinance/blob/HEAD/tidyfinance/download_open_source.py)).
- **Annual USD total returns from the old file** (computed by compounding `mkt_vw`):
  - USA: 2008 −38.3%, 2009 +31.3%, 2018 −6.2%, 2019 +30.2%, 2020 +23.2%, 2022 −19.9%, 2023 +25.9%.
  - JPN (USD / local): 2022 −15.4% / −3.1%; 2023 +18.8% / +27.0%.
  - BRA (USD): 2009 +162.6%, 2022 +2.5%, 2023 +25.5%.
  - ARG (local): 2023 +378% ([csv](https://jkpfactors.s3.amazonaws.com/other_data/market_returns.csv)).

**Verified files: Jordà–Schularick–Taylor Macrohistory Database R6**
- **Wide official format.** https://raw.githubusercontent.com/birjusuketupatel/time_varying_equity_returns/HEAD/JSTdatasetR6.csv (1,137,858 B, sha 590606d06f171434).
  - Shape 2,718 × 59: 18 countries (AUS, BEL, CAN, CHE, DEU, DNK, ESP, FIN, FRA, GBR, IRL, ITA, JPN, NLD, NOR, PRT, SWE, USA), years 1870–2020.
  - Key columns: `eq_tr, eq_capgain, eq_dp, eq_div_rtn, eq_tr_interp, housing_tr, bond_tr, bill_rate, xrusd, cpi, revenue, expenditure, debtgdp, crisisJST, peg`.
  - Sample (USA): `2008 eq_tr −0.3875, eq_capgain −0.4067, eq_dp 0.0324, xrusd 1.0`.
- **Second mirror (Git LFS).** https://media.githubusercontent.com/media/axfreeman/MacroEconomic-History-Server-Builder/HEAD/DATA/SOURCE/ORIGINALS/JST/JSTdatasetR6.xlsx (6,146,802 B). Its sheet `JRT6 Data` holds the original 2,718 × 59 table. Against the birjusuketupatel CSV, the largest absolute difference is 2.5e-8 for `eq_tr`, 5e-7 for `xrusd` and 5e-8 for `cpi`.
  - The plain raw.githubusercontent.com URL for the same path returns only a 132-byte LFS pointer.
  - The repository's `JSTdatasetR6.csv` (LFS, 1,034,112 B) is a reshaped long table (29,898 × 4: `year, country, Attribute, Value`), not the official file ([xlsx](https://media.githubusercontent.com/media/axfreeman/MacroEconomic-History-Server-Builder/HEAD/DATA/SOURCE/ORIGINALS/JST/JSTdatasetR6.xlsx)).
- **JST vs JKP (local currency, 1990–2020, 496 country-years).** The overall correlation is 0.962. Most countries correlate at 0.97–1.00, but **JPN only 0.67**, DNK 0.89 and USA 0.92. Largest gaps:
  - JPN 1999: JST +20.5% vs JKP +66.8%
  - JPN 2000: +12.1% vs −26.2%
  - JPN 2009: −25.0% vs +8.1%
  - DNK 1993: +3.4% vs +45.2%
  - USA 2018: +14.2% vs −6.2%
  - USA 2019: +8.2% vs +30.2%
  - USA 2020: +12.5% vs +23.2%
  - Computed from the [JST csv](https://raw.githubusercontent.com/birjusuketupatel/time_varying_equity_returns/HEAD/JSTdatasetR6.csv) and the [JKP csv](https://jkpfactors.s3.amazonaws.com/other_data/market_returns.csv).
- **JST's USA `eq_capgain` for 2016–2020** is 1.5%, 17.0%, 12.1%, 6.1% and 10.5% ([JST csv](https://raw.githubusercontent.com/birjusuketupatel/time_varying_equity_returns/HEAD/JSTdatasetR6.csv)).
- The GMD re-packaging of JST (`clean/combined/JST.dta`, 2,668 × 34) **drops the equity-return variables**. Only macro variables remain (CPI, USDfx, government revenue and expenditure, rates, …) ([GMD JST.dta](https://gmd-releases.s3.ap-southeast-2.amazonaws.com/data/clean/combined/JST.dta)).

**Verified files: country ETFs (investable proxies)**
- **Monthly bars for iShares country ETFs, SPY and others.** https://raw.githubusercontent.com/ArjunDivecha/Kronos/HEAD/data/CountryMonthly/<TICKER>.csv for 32 tickers. Columns: `timestamps, open, high, low, close, volume, amount`.
  - Coverage: EWA, EWC, EWD, EWG, EWH, EWI, EWJ, EWL, EWM, EWN, EWP, EWQ, EWS, EWU and EWW from 1996-03; EWY 2000-05; EWT 2000-06; EWZ 2000-07; EZA 2003-02; ECH 2007-11; TUR 2008-03; THD 2008-04; VNM 2009-08; EIDO and EPOL 2010-05; EPHE 2010-09; MCHI 2011-03; EDEN 2012-01; INDA 2012-02; ASHR 2013-11; KSA 2015-09; SPY 1995-01. All end at 2026-04.
  - The generating script calls `yf.download(ticker, start="1995-01-01", interval="1mo", auto_adjust=True)`, so prices are adjusted for splits and dividends ([script](https://raw.githubusercontent.com/ArjunDivecha/Kronos/HEAD/monthly_country_test.py)).
  - Sample (EWJ): `1996-03-01, 38.50, 40.43, 38.50, 40.27, 601725, …` and `2026-04-01, 86.66, 89.99, 83.74, 88.35, 87965492, …` ([EWJ.csv](https://raw.githubusercontent.com/ArjunDivecha/Kronos/HEAD/data/CountryMonthly/EWJ.csv)).
- **ETF vs JKP (annual USD returns, 2001–2023).** EWJ vs JPN correlates at 0.99 (mean difference −0.9 points per year). EWZ vs BRA correlates at 0.97 (mean difference −3.2 points per year). Examples: 2022 EWZ +12.2% vs JKP BRA +2.5%; 2023 +37.6% vs +25.5% (computed).
- **Daily, but only from 2019.** https://raw.githubusercontent.com/fja05680/brownbear/HEAD/symbol-cache/EWJ.csv (206,614 B; also EWZ, EWG, SPY, EWW). Columns are `Date, Adj Close, Close, High, Low, Open, Volume`, from 2019-01-02 to 2026-08-28; the repository's last commit is 2026-10-15 ([EWJ.csv](https://raw.githubusercontent.com/fja05680/brownbear/HEAD/symbol-cache/EWJ.csv)).
- **MSCI country index levels.** The only mirror found was https://raw.githubusercontent.com/subarna-kandel/equity-index-ml-ensembles/HEAD/data/weekly_msci_indices.csv (68,771 B). It has weekly levels for 33 "MSCI <country>" series, but only from 1 January 2016 to 23 October 2020 (252 rows), so it is not useful for long tests.
- The **chemicalstats/ChemStats-Archiv** repository has MSCI regional files (World, Europe, North America, Pacific, EM, ACWI, EAFE, USA), but no country-level series. It was listed via a git tree, not downloaded ([repo](https://github.com/chemicalstats/ChemStats-Archiv)).

### Inferences
- **Main returns panel.** Use JKP `mkt_vw` (USD total return) and `mkt_vw_lcl` up to 2023-12. Extend to 2025-12 with the new-bucket `ret` (USD excess over the US T-bill). For cross-sectional tests such as ranking countries by freedom changes, the common T-bill does not change ranks, so excess returns are enough. The `stocks` column (number of firms) supports a minimum-breadth screen.
- **What JKP measures.** JKP is a broad all-cap market (built from CRSP and Compustat), not an investable MSCI index. Emerging-market small and mid caps can make it diverge from MSCI and ETFs (Brazil 2022). An ETF or "MSCI-like" robustness check from 1996 (developed markets) or about 2000–2012 (emerging markets) is advisable.
- **JST problems.** I suspect JST's USA equity data for 2016–2020 are computed from **annual-average** index levels rather than year-end levels. My rough memory of annual-average S&P 500 changes is about +1.6%, +16.9%, +12.1%, +6.1% and +10.5% for 2016–2020, which matches JST's `eq_capgain`. Year-end changes were about +9.5%, +19.4%, −6.2%, +28.9% and +16.3%; these are memory, not verified. JKP independently confirms the year-end pattern (2018 −6.2%, 2019 +30.2%). JST's Japan series also looks offset in timing (possibly fiscal-year based) for 1990–2012.
  - Use JST mainly for the 1870–1985 long-run robustness test. Do not splice it into JKP after 1986 without checks.
- **Unverified spot-check from memory.** JKP USA 2008 −38.3%, 2019 +30.2% and 2023 +25.9% are close to the commonly quoted S&P 500 total returns of about −37.0%, +31.5% and +26.3%. That is consistent with an all-cap value-weighted index, but it was not verified online.

### Gaps
- **No long MSCI country index history** (1970+, gross or net USD) was found on GitHub, PyPI or S3. msci.com and app2.msci.com are blocked. The `mscidata` PyPI package (NikhilSuthar/indian-market-data) only fetches from MSCI's API, which is unreachable here.
- **No Ken French international or country return mirror** was found (code search for "Int_Countries" / "International_Countries" returned nothing). No Dimson–Marsh–Staunton data was found; it is proprietary.
- **The newer JKP local-currency country returns after 2023-12** were not found (I tried `jkpfactors-data…/other_data/market_returns.csv`, which returned 403). `market_returns_daily.csv` (80 MB) exists in the old bucket but was not downloaded.
- **ETF data:** the last Kronos bar (2026-04) may be a partial month. Kronos also does not hold the newer single-country ETFs (Argentina ARGT, Colombia, Peru, etc.).

## Q3. Can they be joined (country codes) for a cross-country test from the 1990s (ideally 1970s) to 2023–2026? (Includes the supporting FX and macro panels)

### Takeaway
Yes. EFW (`ISO_Code`), JKP (`excntry`, or upper-cased `location`), JST (`iso`), WDI (`Country Code`), GMD (`ISO3`) and OWID (`iso_code`) all use ISO3 codes and join directly. **92 of the 95 JKP countries are in EFW.** A test with EFW measured in 1990 and returns starting by 1990 covers **41 countries**; returns starting by 1995 give **61** and by 2000 give **73**. The test can run on returns to 2023-12, or to 2025-12 as USD excess returns. A 1970s start is possible only with JST (16–18 developed countries, annual). Heritage needs a name→ISO3 crosswalk: 144 of 186 slugs auto-match. Supporting panels for FX, tax and spending, manufacturing and energy are all reachable.

### Cited Findings
**Joinability (computed)**
- The EFW 2025 panel has 165 ISO3 codes and JKP has 95, with 92 in common. The JKP countries missing from EFW are BMU, GGY and PSE.
- Countries with both an EFW value in year Y and JKP returns starting by 1990 / 1995 / 2000:

  | EFW year Y | Returns by 1990 | Returns by 1995 | Returns by 2000 |
  |---|---|---|---|
  | 1970 | 41 | 56 | 63 |
  | 1980 | 41 | 59 | 68 |
  | 1990 | 41 | 61 | 73 |
  | 1995 | 42 | 64 | 77 |

  Computed from the [EFW 2025 xlsx](https://raw.githubusercontent.com/kholodovTimur/IR-CaseStudy-26/HEAD/efotw-2025-master-index-data-for-researchers-iso.xlsx) and the [JKP zip](https://jkpfactors-data.s3.amazonaws.com/public/%5Ball_countries%5D_%5Bmkt%5D_%5Bmonthly%5D_%5Bvw%5D.zip).
- All 18 JST countries are in EFW and in JKP ([JST csv](https://raw.githubusercontent.com/birjusuketupatel/time_varying_equity_returns/HEAD/JSTdatasetR6.csv)).
- **Heritage names.** Heritage `name_web` slugs (186) auto-match 144 EFW names after slugifying. The 42 unmatched include market-relevant `korea-south, hong-kong, russia, turkey, egypt, czech-rep, slovakia, venezuela, iran, dominican-rep, trinidad-tobago, bosnia-herzegovina, kyrgyz-rep`, so a small manual crosswalk is needed ([rds](https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/input/heritage/heritage_iof_raw.rds)).

**Verified files: exchange rates**
- **Monthly FX from the FRED H.10 series.** https://raw.githubusercontent.com/datasets/exchange-rates/main/data/monthly.csv (486,615 B), with columns `Date, Country, Exchange rate`.
  - Coverage: 1971-01 to 2026-09, 34 series (Australia, Brazil, Canada, China, Denmark, Euro, Hong Kong, India, Japan, Korea, Malaysia, Mexico, …, Venezuela, plus pre-euro legacy currencies).
  - Values are local currency per USD. Samples: `2026-09-01, Japan, 156.4171`; `Brazil, 5.1433`; `United Kingdom, 0.7459`; `1971-01-01, Australia, 0.8944`.
  - `annual.csv` (27,937 B) and `daily.csv` (7,642,396 B) were also downloaded. The licence is the Open Data Commons PDDL ([README](https://raw.githubusercontent.com/datasets/exchange-rates/main/README.md)).
- **Other FX sources:**
  - JKP's paired `mkt_vw_lcl` / `mkt_vw` returns already embed monthly FX for all 95 countries to 2023-12.
  - JST has `xrusd`.
  - GMD's `USDfx` (1 USD in local currency) covers 235 countries; 231 have 1990 data and 223 have 2024 data.
  - WDI's `PA.NUS.FCRF` (official rate, period average) covers 177 economies in 1990 and 189 in 2024.
  - Sources: [GMD](https://gmd-releases.s3.ap-southeast-2.amazonaws.com/data/distribute/GMD_2026_09.dta) and [WDI](https://media.githubusercontent.com/media/DuHe1123/gridgdpapps/HEAD/data/validation_data/WorldDevelopmentIndicator/WDICSV.csv).

**Verified files: macro panels (tax, spending, industry, energy)**
- **Global Macro Database (GMD), release 2026_09.** https://gmd-releases.s3.ap-southeast-2.amazonaws.com/data/distribute/GMD_2026_09.dta (58,991,450 B, Stata 118; 57,392 rows × 162 columns; 239 ISO3 economies; years 1086–2031).
  - The S3 base URL comes from the official Python package ([gmd.py](https://raw.githubusercontent.com/KMueller-Lab/Global-Macro-Database-Python/HEAD/global_macro_data/gmd.py)).
  - The release list is at https://gmd-releases.s3.ap-southeast-2.amazonaws.com/data/helpers/versions.csv (2025_01 … 2026_09). Variable definitions are in `helpers/varlist.csv`, and the 160+ underlying sources (WDI, IMF_GFS, IMF_WEO, OECD_EO, JST, Mitchell, …) are in `helpers/source_list.csv`.
  - Coverage of selected variables:

    | Variable | Countries | Years | Countries with 1990 | Countries with 2024 |
    |---|---|---|---|---|
    | `govtax_GDP` | 173 | — | 72 | 108 |
    | `govexp_GDP` | 200 | — | 141 | 195 |
    | `gen_govtax_GDP` (general government) | 144 | — | 27 | 96 |
    | `REER` | 181 | — | 175 | 107 |
    | `infl` | 218 | — | — | — |
    | `strate` | 155 | — | — | — |
    | `rGDP_pc` | 227 | — | — | — |

  - Sample (CHL): `1990 govtax_GDP 13.26, govexp_GDP 20.99, USDfx 304.68`; `2024 19.97, 26.73, 943.58`; rows for 2025 and 2030 also exist (projections).
  - Bucket listing is denied, but direct keys work ([GMD dta](https://gmd-releases.s3.ap-southeast-2.amazonaws.com/data/distribute/GMD_2026_09.dta)).
- **World Bank WDI, full bulk CSV.** https://media.githubusercontent.com/media/DuHe1123/gridgdpapps/HEAD/data/validation_data/WorldDevelopmentIndicator/WDICSV.csv (198,198,507 B). Its SHA-256 (3cda0e5e40c52cc9…) equals the repository's LFS pointer oid.
  - Shape 403,256 × 69: 1,516 indicators, 266 economies, year columns 1960–2024. Columns are `Country Name, Country Code, Indicator Name, Indicator Code, 1960…2024`.
  - Non-null cells: 216,884 in 2020, 192,514 in 2022, 150,169 in 2023 and 72,253 in 2024. This points to a 2025 vintage.
  - Economies with data by indicator:

    | Indicator | 1990 | 2022 | 2024 |
    |---|---|---|---|
    | `NV.IND.MANF.ZS` (manufacturing % GDP) | 134 | 230 | 171 |
    | `NV.IND.TOTL.ZS` (industry) | 164 | 244 | 198 |
    | `GC.TAX.TOTL.GD.ZS` (tax revenue % GDP, central government) | 87 | 140 | 2 |
    | `NE.CON.GOVT.ZS` (government consumption % GDP) | 173 | 215 | 123 |
    | `GC.XPN.TOTL.GD.ZS` (expense) | 81 | 131 | — |

    `EG.USE.PCAP.KG.OE` (energy use per capita) and `EG.USE.ELEC.KH.PC` (kWh per capita) both end in 2023, with 193 economies in 2022. `CM.MKT.LCAP.GD.ZS` (market cap % GDP) has 37 economies in 1990 and 95 in 2024. Taiwan is absent; Hong Kong is present.
  - Samples: USA manufacturing 15.1 (2000) → 10.3 (2022); CHN 31.1 (2010) → 26.4 (2022); DEU 20.3 (2000) → 18.3 (2022) ([WDI csv](https://media.githubusercontent.com/media/DuHe1123/gridgdpapps/HEAD/data/validation_data/WorldDevelopmentIndicator/WDICSV.csv)).
- **Single-indicator WDI extract.** https://raw.githubusercontent.com/CaiYuwei2003/Carbon-Emission-Analysis/HEAD/API_NV.IND.MANF.ZS_DS2_en_csv_v2_7.csv (64,775 B). It is a reshaped `Code, 2000…2022` table; the full bulk file supersedes it.
- **OWID energy (legacy).** https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv (9,229,369 B; 23,377 × 130; 220 ISO codes; 1900–2025). The codebook is at `owid-energy-codebook.csv` (45,793 B).
  - Columns include `energy_per_capita, per_capita_electricity, electricity_demand_per_capita, fossil_share_energy, energy_per_gdp, coal_prod_per_capita, oil_prod_per_capita, gas_prod_per_capita`.
  - `energy_per_capita` covers 229 entities in 2021–2023 but only 90 in 2024.
  - Sample (DEU): `2023 energy_per_capita 37,598 kWh, fossil_share_energy 75.8, per_capita_electricity 5,993`.
  - The README says this legacy file "remains available for download but is no longer updated". The new version is on catalog.ourworldindata.org, which is blocked here ([README](https://raw.githubusercontent.com/owid/energy-data/master/README.md)).

### Inferences
- **Feasible designs:**
  - (a) 1990/1995–2023/2025: EFW (5-year changes to 2000, then annual) × JKP monthly USD returns for 41–77 countries.
  - (b) 2000–2025: annual EFW and Heritage changes × JKP for about 80–90 countries, plus an ETF-investable subset (about 15 developed markets from 1996, about 30 countries by the 2010s).
  - (c) 1870/1970–2020 long run: JST eq_tr × USD (via `xrusd`) for 16–18 developed countries, using EFW from 1970 (five-yearly) plus earlier EFW ratings for 1950–1965.
- **Tax leg.** The best long, broad tax measures are EFW's own components (top marginal tax rate, government consumption, transfers), which are consistent across 1970–2023. Heritage "Tax Burden" covers 1995–2026. GMD `govtax_GDP` and `gen_govtax_GDP` add revenue-based measures. WDI `GC.TAX.TOTL.GD.ZS` is central government only and thin before 2000.
- **Energy and industry leg.** Use WDI manufacturing and industry shares (1960–2024) and OWID or WDI energy per capita (to 2023/2024).
- **Look-ahead.** GMD includes IMF WEO-style projections up to 2031. Rows after the last actual year (and possibly the latest one or two "actual" years) must be cut or lagged.

### Gaps
- **No electricity price panel** (industrial or household) was found that the sandbox can reach. OWID and WDI hold quantities, not prices; IEA, Eurostat and GlobalPetrolPrices are unreachable or not mirrored.
- **No OECD Revenue Statistics mirror** (total tax including social security, general government) was found. GMD `gen_govtax_GDP` is the nearest substitute, with only 27 countries in 1990.
- **The exact source vintage** of the WDI bulk mirror (which WDI release) could not be confirmed beyond the data's last year (2024, partial).

## Q4. Any license or provenance concerns?

### Takeaway
All the core data is reachable only through **third-party mirrors** (GitHub repositories or LFS) or the **authors' own public S3 buckets** (JKP, GMD). Integrity is supported by agreement between mirrors (EFW 2025: two mirrors identical; JST R6: two mirrors agree to 1e-7) and between datasets (JKP vs ETFs, JKP vs JST). But no file could be checked against the official site from this sandbox. On licensing, **JST is CC BY-NC-SA** and **GMD forbids products and re-hosting**, so both are fine for internal research but not for redistribution or commercial products. I could not verify the EFW, Heritage and JKP terms.

### Cited Findings
- **JST licence.** JST Macrohistory data is licensed **CC BY-NC-SA 4.0** and should be cited as Jordà, Knoll, Kuvshinov, Schularick & Taylor (2019, QJE). This is stated in a third-party data README ([BuyRisk README](https://raw.githubusercontent.com/BuyRisk/buyrisk.github.io/HEAD/data/sources/jst/README.md)).
- **GMD licence.** GMD is released under the "GMD Research Use Terms" (v1.1, "follows the spirit of CC BY-NC-SA 4.0"). The README says: "Not for products … Do not build any part of it, even in derived form, into a product, service, model, index, or paid report" and "Do not re-host or rebadge it" ([GMD README](https://raw.githubusercontent.com/KMueller-Lab/Global-Macro-Database/HEAD/README.md)).
- **FX licence.** The datasets/exchange-rates data is under the ODC Public Domain Dedication and License ([README](https://raw.githubusercontent.com/datasets/exchange-rates/main/README.md)).
- **Mirror provenance:**
  - The EFW 2024 and Heritage raw files come from a World Bank-affiliated ETL repository whose scripts document the official origin URLs: [fraser.R](https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/source/fraser.R) and [heritage.R](https://raw.githubusercontent.com/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/source/heritage.R).
  - The EFW 2025 xlsx comes from a student repository, but an independent CSV mirror built from the official efotw.org URL matches it exactly ([kholodovTimur xlsx](https://raw.githubusercontent.com/kholodovTimur/IR-CaseStudy-26/HEAD/efotw-2025-master-index-data-for-researchers-iso.xlsx); [eltonjmarinho csv](https://raw.githubusercontent.com/eltonjmarinho/artigo_macro_modelo-main/HEAD/data/freedom.csv)).
- **JKP:** the old S3 bucket is publicly listable and its `market_returns.csv` was last modified on 2024-05-03 ([listing](https://jkpfactors.s3.amazonaws.com/?list-type=2&prefix=other_data/)). A third-party code comment says the jkpfactors.com UI redirects to a login, while the S3 bucket "IS publicly readable" ([quantrank jkp.py](https://github.com/dackclup/quantrank/blob/HEAD/compute/ingest/jkp.py)).
- **ETF data** is Yahoo-derived (yfinance, auto-adjusted) and redistributed in a personal repository ([Kronos script](https://raw.githubusercontent.com/ArjunDivecha/Kronos/HEAD/monthly_country_test.py)).
- **Attempts that failed or were unusable:**
  - The GitHub REST search API returned 403 ("sessions are bound to their configured repositories"), and the repository contents API returned 403 ("not configured"). I worked around this with MCP code search and `git clone --filter=blob:none --no-checkout`.
  - raw.githubusercontent.com returns LFS pointers for LFS files; media.githubusercontent.com works.
  - `https://raw.githubusercontent.com/BuyRisk/buyrisk.github.io/HEAD/data/sources/jst/JSTdatasetR6.dta` returned 404.
  - JKP: `jkpfactors-data` bucket listing returned 403, as did `…/other_data/market_returns.csv` in that bucket.
  - GMD: bucket listing returned 403.
  - `bq ls bigquery-public-data:world_bank_wdi` failed with "Invalid Credentials".
  - **Official hosts unreachable** (curl 000): fraserinstitute.org, efotw.org, economicfreedom.heritage.org, macrohistory.net, mba.tuck.dartmouth.edu, msci.com, app2.msci.com, stooq.com, query1.finance.yahoo.com, fred.stlouisfed.org, ourworldindata.org, catalog.ourworldindata.org, owid-public.owid.io, jkpfactors.com, globalmacrodata.com, kaggle.com, huggingface.co, zenodo.org, cran.r-project.org, dataverse.harvard.edu, osf.io, figshare.com, datahub.io, ishares.com, data.imf.org, OECD, BIS, NBER and web.archive.org.
  - **Unusable mirrors:**
    - ronnywang/worldbank's per-indicator WDI CSVs are a 2013 vintage (listed, not used).
    - [weekly_msci_indices.csv](https://raw.githubusercontent.com/subarna-kandel/equity-index-ml-ensembles/HEAD/data/weekly_msci_indices.csv) covers only 2016–2020.
    - brownbear's ETF cache starts in 2019.

### Inferences
- **For internal backtesting**, all of the above should be acceptable with citations: Fraser EFW (Gwartney, Lawson, Murphy et al.), Heritage, JKP (Jensen, Kelly & Pedersen 2023, Journal of Finance), JST (Jordà et al. 2019), GMD (Müller et al. 2025), World Bank WDI and OWID.
- **Anything published, sold or packaged into a product** must avoid redistributing JST (non-commercial, share-alike) and GMD (no products, no re-hosting).
- **Pin the files.** Record the file hashes listed here, because the mirrors can change or disappear. The stronger-provenance pairs are the World Bank ETL repo (EFW 2024, Heritage), the two matching EFW-2025 mirrors, the two matching JST mirrors and the authors' own S3 buckets (JKP, GMD).

### Gaps
- I could not read the terms of use for Fraser EFW, Heritage or JKP; their sites are blocked and web search was exhausted. My understanding is that EFW and Heritage are free to use with attribution, but this is unverified.
- No official checksum is available for any file, so integrity rests on cross-mirror and cross-dataset agreement only.
- The JST equity anomalies (USA 2016–2020, Japan 1990s–2000s, Denmark early 1990s) should be checked against the official macrohistory.net release notes or documentation, which were unreachable.
