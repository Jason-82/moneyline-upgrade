"""
Rebuild the gitignored data used by analysis_2026/freedom_countries.py (economic-freedom thesis),
from hosts reachable in the Claude cloud sandbox (GitHub raw / Git LFS media and AWS S3).

    python3 -m analysis_2026.fetch_freedom_data

Writes data/freedom/:
  efw2025.xlsx       Fraser Economic Freedom of the World, 2025 report (data 1970-2023), mirror of
                     efotw.org's "master index data for researchers" (kholodovTimur/IR-CaseStudy-26;
                     an independent CSV mirror built from the official URL matches it exactly)
  efw2024.xlsx       2024 report (data to 2022), World Bank PIDA cliaretl mirror
  efw2019.xlsx       2019 report (data to 2017), diodz/disasters-economic-freedom mirror
  heritage.parquet   Heritage Index of Economic Freedom 1995-2026, all components (cliaretl raw dump of
                     economicfreedom.heritage.org's own CSV)
  jkp_mkt_old.csv    Jensen-Kelly-Pedersen country market returns to 2023-12 (USD and local, vw/ew,
                     n stocks, market equity), jkpfactors S3 bucket
  jkp_mkt_vw.csv     JKP country value-weighted USD excess returns to 2025-12 (new S3 bucket)
  wdi.parquet        World Bank WDI extract (manufacturing % GDP, tax revenue % GDP, population),
                     from a Git-LFS copy of the full WDI bulk CSV (198 MB, deleted after extraction)
  owid_energy.csv    Our World in Data energy data (legacy GitHub file, 1900-2025)
  etf/<TICKER>.csv   iShares country ETF monthly bars, dividend-adjusted (ArjunDivecha/Kronos, yfinance)
All sources are third-party mirrors (see analysis_2026/research_notes/Economic freedom investment
thesis/data_sources.md for provenance and checks); sha256 prefixes are printed for each file.
"""
from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "freedom"
RAW = "https://raw.githubusercontent.com"
FILES = {
    "efw2025.xlsx": f"{RAW}/kholodovTimur/IR-CaseStudy-26/HEAD/efotw-2025-master-index-data-for-researchers-iso.xlsx",
    "efw2024.xlsx": f"{RAW}/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/input/fraser/"
                    "efotw-2024-master-index-data-for-researchers-iso.xlsx",
    "efw2019.xlsx": f"{RAW}/diodz/disasters-economic-freedom/HEAD/data/efw-2019-master-index-data-for-researchers.xlsx",
    "jkp_mkt_old.csv": "https://jkpfactors.s3.amazonaws.com/other_data/market_returns.csv",
    "owid_energy.csv": f"{RAW}/owid/energy-data/master/owid-energy-data.csv",
}
HERITAGE = f"{RAW}/WB-PIDA-Data-Science-Shop/cliaretl/HEAD/data-raw/input/heritage/heritage_iof_raw.rds"
JKP_NEW = "https://jkpfactors-data.s3.amazonaws.com/public/%5Ball_countries%5D_%5Bmkt%5D_%5Bmonthly%5D_%5Bvw%5D.zip"
WDI = "https://media.githubusercontent.com/media/DuHe1123/gridgdpapps/HEAD/data/validation_data/WorldDevelopmentIndicator/WDICSV.csv"
WDI_CODES = {"NV.IND.MANF.ZS": "manuf_gdp", "GC.TAX.TOTL.GS.ZS": "tax_rev_gdp", "SP.POP.TOTL": "pop",
             "NE.CON.GOVT.ZS": "gov_cons_gdp"}
ETFS = ("EWA EWC EWD EWG EWH EWI EWJ EWL EWM EWN EWP EWQ EWS EWT EWU EWW EWY EWZ EZA ECH EIDO EPHE EPOL INDA "
        "KSA MCHI THD TUR VNM EDEN SPY").split()


def get(url: str, timeout=600) -> bytes:
    for k in range(4):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read()
        except Exception:
            if k == 3:
                raise
    raise RuntimeError(url)


def save(name: str, b: bytes) -> None:
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(b)
    print(f"{name:20s} {len(b):>11,d} B  sha256 {hashlib.sha256(b).hexdigest()[:16]}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        save(name, get(url))
    import pyreadr                                   # pip install pyreadr
    tmp = OUT / "heritage_raw.rds"; tmp.write_bytes(get(HERITAGE))
    h = next(iter(pyreadr.read_r(str(tmp)).values())); tmp.unlink()
    h.to_parquet(OUT / "heritage.parquet"); print("heritage.parquet", h.shape)
    z = zipfile.ZipFile(io.BytesIO(get(JKP_NEW)))
    save("jkp_mkt_vw.csv", z.read(z.namelist()[0]))
    rows = []
    with urllib.request.urlopen(WDI, timeout=1200) as r:
        for chunk in pd.read_csv(io.TextIOWrapper(r, encoding="utf-8"), chunksize=50_000):
            rows.append(chunk[chunk["Indicator Code"].isin(WDI_CODES)])
    w = pd.concat(rows)
    w = w.drop(columns=[c for c in ("Country Name", "Indicator Name") if c in w]).melt(
        id_vars=["Country Code", "Indicator Code"], var_name="year", value_name="value").dropna()
    w = w[w.year.str.fullmatch(r"\d{4}")]
    w["year"] = w.year.astype(int); w["var"] = w["Indicator Code"].map(WDI_CODES)
    w = w.pivot_table(index=["Country Code", "year"], columns="var", values="value").reset_index()
    w.columns.name = None; w = w.rename(columns={"Country Code": "iso3"})
    w.to_parquet(OUT / "wdi.parquet"); print("wdi.parquet", w.shape)
    for t in ETFS:
        save(f"etf/{t}.csv", get(f"{RAW}/ArjunDivecha/Kronos/HEAD/data/CountryMonthly/{t}.csv"))


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__); sys.exit(0)
    main()
