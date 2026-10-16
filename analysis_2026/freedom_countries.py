"""
Does a country's policy direction predict its stock returns? Test of the user's thesis
(2026-10-16): overweight countries moving toward lower taxes, more economic freedom and more
energy/industrial build-out; underweight those moving the other way.

Pre-registered in analysis_2026/FREEDOM_PREREG.md (commit b100171) before any result existed.
Data: python3 -m analysis_2026.fetch_freedom_data (writes data/freedom/, gitignored).

    python3 -m analysis_2026.freedom_countries      (writes analysis_2026/results_freedom/)

Interpretation notes fixed before the run:
- Formation dates are the end of October of each year Y, from 1997 (the first Fraser report, 1996,
  made the index public) to 2025. A signal enters once at least 15 countries have it.
- "Halves": 1997-2010 / 2011-2025 for signals available from 1997; otherwise the signal's own
  span is split at its middle formation year.
- A country that stops trading drops out of the portfolio average from that month (no fill).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "freedom"
OUT = ROOT / "analysis_2026" / "results_freedom"
WEST = ["USA", "CAN", "GBR", "IRL", "FRA", "DEU", "ITA", "ESP", "PRT", "GRC", "NLD", "BEL", "LUX", "AUT", "CHE",
        "DNK", "NOR", "SWE", "FIN", "ISL", "AUS", "NZL"]
DM = ["AUS", "AUT", "BEL", "CAN", "DNK", "FIN", "FRA", "DEU", "HKG", "IRL", "ISR", "ITA", "JPN", "NLD", "NZL", "NOR",
      "PRT", "SGP", "ESP", "SWE", "CHE", "GBR", "USA"]               # MSCI developed markets (2026)
EXCLUDE = ["VEN", "ZWE"]
HERITAGE_XWALK = {"cote-divoire": "CIV", "czech-rep": "CZE", "egypt": "EGY", "hong-kong": "HKG", "iran": "IRN",
                  "korea-south": "KOR", "russia": "RUS", "slovakia": "SVK", "trinidad-tobago": "TTO", "turkey": "TUR",
                  "venezuela": "VEN", "bahamas": "BHS", "bosnia-herzegovina": "BIH", "burma": "MMR",
                  "dominican-rep": "DOM", "kyrgyz-rep": "KGZ", "laos": "LAO", "macau": "MAC", "syria": "SYR",
                  "yemen": "YEM", "gambia": "GMB", "uzbekistan": "UZB", "afghanistan": "AFG"}
ETF = {"EWA": "AUS", "EWC": "CAN", "EWD": "SWE", "EWG": "DEU", "EWH": "HKG", "EWI": "ITA", "EWJ": "JPN", "EWL": "CHE",
       "EWM": "MYS", "EWN": "NLD", "EWP": "ESP", "EWQ": "FRA", "EWS": "SGP", "EWT": "TWN", "EWU": "GBR", "EWW": "MEX",
       "EWY": "KOR", "EWZ": "BRA", "EZA": "ZAF", "ECH": "CHL", "EIDO": "IDN", "EPHE": "PHL", "EPOL": "POL",
       "INDA": "IND", "KSA": "SAU", "MCHI": "CHN", "THD": "THA", "TUR": "TUR", "VNM": "VNM", "EDEN": "DNK", "SPY": "USA"}
FIRST, LAST = 1997, 2025
SIGNALS = {
    "S1": "change in economic freedom (Fraser EFW, 5-yr)",
    "S2": "level of economic freedom (Fraser EFW)",
    "S3": "change in tax burden score (Heritage, 5-yr; up = lower taxes)",
    "S4": "change in manufacturing share of GDP (WDI, 5-yr)",
    "S5": "growth in electricity generation per person (OWID, 5-yr log)",
    "S6": "change in economic freedom, Western countries only",
    "S7": "composite of S1, S3, S4, S5 (mean z-score)",
}


# ============================================================================ data

def load_returns(russia_wipeout: bool = True) -> pd.DataFrame:
    """Monthly USD excess returns (rows: month-end, columns: ISO3) and stock counts."""
    d = pd.read_csv(DATA / "jkp_mkt_vw.csv")
    d["iso"] = d.location.str.upper(); d["date"] = pd.to_datetime(d.date) + pd.offsets.MonthEnd(0)
    d = d[~d.iso.isin(EXCLUDE)]
    r = d.pivot_table(index="date", columns="iso", values="ret")
    n = d.pivot_table(index="date", columns="iso", values="n_stocks")
    if russia_wipeout and "RUS" in r:
        r.loc[r.index > "2022-03-31", "RUS"] = np.nan; r.loc["2022-03-31", "RUS"] = -1.0
        n.loc[n.index > "2022-02-28", "RUS"] = np.nan
    return r.sort_index(), n.sort_index()


def load_efw(vintage: str = "2025", chain: bool = False) -> pd.DataFrame:
    """Fraser EFW summary index, long format (iso, year, efw)."""
    f = DATA / f"efw{vintage}.xlsx"
    if chain:
        if vintage != "2025":
            raise ValueError("chain-linked panel used only from the 2025 release")
        x = pd.read_excel(f, sheet_name="EFW Panel Dataset")
        x = x.rename(columns={"ISO_Code": "iso", "Year": "year", "Summary": "efw"})
    else:
        sh = {"2025": "EFW Index 1970-2023", "2024": "EFW Data 2024 Report", "2019": "EFW Index 2019 Report"}[vintage]
        x = pd.read_excel(f, sheet_name=sh, header=None)
        hdr = [i for i in range(12) if (x.iloc[i].astype(str).str.strip() == "Year").any()][0]
        x.columns = [str(c).strip() for c in x.iloc[hdr]]; x = x.iloc[hdr + 1:]
        isos = [c for c in x.columns if c in ("ISO_Code", "ISO Code 3")]
        summ = [c for c in x.columns if "ALL AREAS" in c.upper() or "SUMMARY INDEX" in c.upper()][0]
        x = x.rename(columns={"Year": "year", isos[0]: "iso", summ: "efw"})
    x = x[["iso", "year", "efw"]].dropna()
    x["year"] = x.year.astype(int); x["efw"] = pd.to_numeric(x.efw, errors="coerce")
    return x.dropna()


def iso_names() -> dict:
    x = pd.read_excel(DATA / "efw2025.xlsx", sheet_name="EFW Index 1970-2023", header=3)
    slug = lambda s: re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")  # noqa: E731
    m = {slug(c): i for i, c in zip(x.ISO_Code, x.Countries)}
    m.update(HERITAGE_XWALK)
    return m


def load_heritage() -> pd.DataFrame:
    h = pd.read_parquet(DATA / "heritage.parquet")
    h["iso"] = h.name_web.map(iso_names()); h["year"] = pd.to_numeric(h.Year, errors="coerce")
    for c in ("Overall", "Tax Burden", "Government Spending"):
        h[c] = pd.to_numeric(h[c], errors="coerce")
    return h.dropna(subset=["iso", "year"]).rename(columns={"Tax Burden": "tax", "Overall": "overall",
                                                            "Government Spending": "spend"})


def load_macro() -> tuple[pd.DataFrame, pd.DataFrame]:
    w = pd.read_parquet(DATA / "wdi.parquet")[["iso3", "year", "manuf_gdp"]].dropna().rename(columns={"iso3": "iso"})
    e = pd.read_csv(DATA / "owid_energy.csv", usecols=["iso_code", "year", "electricity_generation", "population"])
    e = e.dropna().rename(columns={"iso_code": "iso"})
    e = e[(e.population > 0) & (e.electricity_generation > 0)]
    e["elec_pc"] = e.electricity_generation / e.population
    return w, e


# ============================================================================ signals

def _latest(df: pd.DataFrame, col: str, upto: int) -> pd.DataFrame:
    """Per country, the latest observation with year <= upto."""
    x = df[df.year <= upto].sort_values("year").groupby("iso").tail(1)
    return x[["iso", "year", col]]


def efw_signals(efw: pd.DataFrame, Y: int) -> pd.DataFrame:
    """S1 (annualized change x 5 from d0 to d) and S2 (level at d); d <= Y-2, d0 <= d-5."""
    cur = _latest(efw, "efw", Y - 2).rename(columns={"year": "d", "efw": "S2"})
    out = []
    for _, r in cur.iterrows():
        prev = efw[(efw.iso == r.iso) & (efw.year <= r.d - 5)]
        if len(prev):
            p = prev.sort_values("year").iloc[-1]
            out.append({"iso": r.iso, "S2": r.S2, "S1": (r.S2 - p.efw) / (r.d - p.year) * 5})
        else:
            out.append({"iso": r.iso, "S2": r.S2, "S1": np.nan})
    return pd.DataFrame(out).set_index("iso")


def change_signal(df: pd.DataFrame, col: str, d: int, k: int = 5, log: bool = False) -> pd.Series:
    a = df[df.year == d].set_index("iso")[col]; b = df[df.year == d - k].set_index("iso")[col]
    j = a.index.intersection(b.index)
    return (np.log(a[j] / b[j]) if log else a[j] - b[j]).astype(float)


def signals_at(Y: int, efw, her, wdi, ele) -> pd.DataFrame:
    s = efw_signals(efw, Y)
    s["S3"] = change_signal(her, "tax", Y)
    s = s.join(change_signal(wdi, "manuf_gdp", Y - 2).rename("S4"), how="outer")
    s = s.join(change_signal(ele, "elec_pc", Y - 2, log=True).rename("S5"), how="outer")
    s["S6"] = s.S1.where(s.index.isin(WEST))
    return s


def zscore(x: pd.Series) -> pd.Series:
    return (x - x.mean()) / x.std() if x.notna().sum() > 2 else x * np.nan


# ============================================================================ portfolios

def eligible(rets: pd.DataFrame, nst: pd.DataFrame, Y: int) -> list[str]:
    t = pd.Timestamp(f"{Y}-10-31")
    if t not in nst.index:
        return []
    ok = nst.loc[t] >= 20
    hist = rets.loc[:t].tail(12).notna().sum() == 12
    return [c for c in rets.columns if ok.get(c, False) and hist.get(c, False)]


def hold_months(rets: pd.DataFrame, Y: int, H: int = 12) -> pd.DatetimeIndex:
    start = pd.Timestamp(f"{Y}-11-30")
    return rets.index[(rets.index >= start)][:H]


def long_short(rets, nst, sigs: dict, name: str, H: int = 12, universe=None, min_n=15):
    """Monthly top-third minus bottom-third returns (equal weight), plus top-third minus universe.
    With H > 12, overlapping annual cohorts are averaged (Jegadeesh-Titman)."""
    cohorts = []
    for Y, s in sigs.items():
        el = eligible(rets, nst, Y)
        if universe is not None:
            el = [c for c in el if c in universe]
        x = s[name].reindex(el).dropna()
        if len(x) < min_n:
            continue
        k = len(x) // 3
        rk = x.rank(method="first")
        top = rk[rk > len(x) - k].index; bot = rk[rk <= k].index
        m = hold_months(rets, Y, H)
        if len(m) == 0:
            continue
        R = rets.loc[m]
        cohorts.append(pd.DataFrame({"Y": Y, "ls": R[top].mean(axis=1) - R[bot].mean(axis=1),
                                     "tilt": R[top].mean(axis=1) - R[list(x.index)].mean(axis=1), "n": len(x)}, index=m))
    if not cohorts:
        return pd.DataFrame(columns=["ls", "tilt", "n", "Y"])
    c = pd.concat(cohorts)
    g = c.groupby(level=0)
    return pd.DataFrame({"ls": g.ls.mean(), "tilt": g.tilt.mean(), "n": g.n.mean(), "Y": g.Y.min()})


def nw_t(x: np.ndarray, lags: int = 12) -> float:
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 24:
        return np.nan
    u = x - x.mean(); s = (u @ u) / n
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * (u[L:] @ u[:-L]) / n
    return x.mean() / np.sqrt(s / n)


def summarize(ls: pd.DataFrame, col: str = "ls") -> dict:
    from scipy.stats import norm
    x = ls[col].dropna()
    if len(x) < 24:
        return {"months": len(x)}
    t = nw_t(x.to_numpy())
    ys = sorted(ls.Y.unique())
    cut = 2011 if ys[0] <= 1997 else ys[len(ys) // 2]
    h1 = ls[ls.Y < cut][col].mean() * 12; h2 = ls[ls.Y >= cut][col].mean() * 12
    return {"first_Y": int(ys[0]), "last_Y": int(ys[-1]), "months": len(x), "avg_n": ls.n.mean(),
            "ann_mean_%": x.mean() * 1200, "ann_vol_%": x.std() * np.sqrt(12) * 100, "nw_t": t,
            "p_one_sided": 1 - norm.cdf(t), "half1_%": h1 * 100, "half2_%": h2 * 100, "cut": cut}


def holm(p: list[float]) -> list[float]:
    p = np.asarray(p, float); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for i, j in enumerate(o):
        run = max(run, min(1.0, (m - i) * p[j])); adj[j] = run
    return list(adj)


def fama_macbeth(rets, nst, sigs: dict, name: str) -> dict:
    """Monthly cross-sectional regressions of returns on z(signal), z(12m momentum), z(60m reversal)."""
    lr = np.log1p(rets)
    mom = lr.rolling(12).sum().shift(1); rev = lr.rolling(48).sum().shift(13)
    coefs = []
    for Y, s in sigs.items():
        el = eligible(rets, nst, Y)
        x = s[name].reindex(el).dropna()
        if len(x) < 15:
            continue
        for m in hold_months(rets, Y, 12):
            df = pd.DataFrame({"r": rets.loc[m, x.index], "s": zscore(x), "mom": zscore(mom.loc[m, x.index]),
                               "rev": zscore(rev.loc[m, x.index])}).dropna()
            if len(df) < 12:
                continue
            X = np.column_stack([np.ones(len(df)), df.s, df["mom"], df.rev])
            b = np.linalg.lstsq(X, df.r.to_numpy(), rcond=None)[0]
            coefs.append({"date": m, "s": b[1], "mom": b[2], "rev": b[3]})
    c = pd.DataFrame(coefs).set_index("date")
    return {f"{k}_coef_%/sd": c[k].mean() * 100 for k in ("s", "mom", "rev")} | \
           {f"{k}_nw_t": nw_t(c[k].to_numpy()) for k in ("s", "mom", "rev")} | {"months": len(c)}


def etf_returns() -> pd.DataFrame:
    out = {}
    for t, iso in ETF.items():
        f = DATA / "etf" / f"{t}.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f, parse_dates=["timestamps"]).set_index("timestamps").close
        d.index = d.index + pd.offsets.MonthEnd(0)
        d = d[~d.index.duplicated(keep="last")]
        out[iso] = d.pct_change()
    r = pd.DataFrame(out).sort_index()
    return r.iloc[:-1]                                   # the last bar may be a partial month


# ============================================================================ main

def main():
    OUT.mkdir(exist_ok=True)
    log = open(OUT / "summary.txt", "w")

    def say(*a):
        s = " ".join(str(x) for x in a); print(s); log.write(s + "\n"); log.flush()
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
    fmt = lambda x: f"{x:,.2f}"  # noqa: E731

    rets, nst = load_returns()
    efw = load_efw("2025"); her = load_heritage(); wdi, ele = load_macro()
    years = range(FIRST, LAST + 1)
    sigs = {}
    for Y in years:
        s = signals_at(Y, efw, her, wdi, ele)
        z = pd.concat([zscore(s[c]) for c in ("S1", "S3", "S4", "S5")], axis=1)
        s["S7"] = z.mean(axis=1).where(z.notna().sum(axis=1) >= 2)
        sigs[Y] = s
    pd.concat({Y: s for Y, s in sigs.items()}, names=["Y", "iso"]).to_csv(OUT / "signals.csv")

    say("=" * 100); say("PRE-REGISTERED TESTS (FREEDOM_PREREG.md): top third minus bottom third, USD, 12-month hold"); say("=" * 100)
    rows = []
    for k in SIGNALS:
        ls = long_short(rets, nst, sigs, k, universe=WEST if k == "S6" else None,
                        min_n=12 if k == "S6" else 15)
        ls.to_csv(OUT / f"ls_{k}.csv")
        rows.append({"id": k, "signal": SIGNALS[k]} | summarize(ls))
    t = pd.DataFrame(rows)
    t["p_holm"] = holm(t.p_one_sided.fillna(1).tolist())
    t["PASS"] = (t["ann_mean_%"] > 0) & (t.nw_t >= 2.0) & (t["half1_%"] > 0) & (t["half2_%"] > 0) & (t.p_holm < 0.05)
    say(t.to_string(index=False, float_format=fmt)); t.to_csv(OUT / "primary.csv", index=False)

    say("\nSecondary (Hxb): Fama-MacBeth, country return on z(signal) with z(12m momentum) and z(48m reversal):")
    fm = pd.DataFrame([{"id": k} | fama_macbeth(rets, nst, sigs, k) for k in SIGNALS if k != "S6"])
    say(fm.to_string(index=False, float_format=fmt)); fm.to_csv(OUT / "fama_macbeth.csv", index=False)

    # ---------------------------------------------------------------- exploratory
    say("\n" + "=" * 100); say("EXPLORATORY"); say("=" * 100)
    ex = []
    for k in ("S1", "S2", "S3", "S7"):
        for lab, uni in (("developed", DM), ("emerging/other", None)):
            u = uni if uni is not None else [c for c in rets.columns if c not in DM]
            ex.append({"test": f"{k} within {lab}"} | summarize(long_short(rets, nst, sigs, k, universe=u, min_n=12)))
        ex.append({"test": f"{k} long-only tilt (top third minus all)"} | summarize(long_short(rets, nst, sigs, k), "tilt"))
        for H in (36, 60):
            ex.append({"test": f"{k} {H}-month hold (overlapping cohorts)"} | summarize(long_short(rets, nst, sigs, k, H=H)))
    # Heritage overall score change, Fraser vintages and chain-linked
    for Y in years:
        sigs[Y]["X_her"] = change_signal(her, "overall", Y).reindex(sigs[Y].index)
        sigs[Y]["X_spend"] = change_signal(her, "spend", Y).reindex(sigs[Y].index)
    ex.append({"test": "Heritage overall score, 5-yr change"} | summarize(long_short(rets, nst, sigs, "X_her")))
    ex.append({"test": "Heritage government-spending score, 5-yr change"} | summarize(long_short(rets, nst, sigs, "X_spend")))
    for lab, e2 in (("Fraser 2019 release (formations to 2019)", load_efw("2019")),
                    ("Fraser 2025 chain-linked panel", load_efw("2025", chain=True))):
        sv = {Y: efw_signals(e2, Y) for Y in years if lab.startswith("Fraser 2025") or Y <= 2019}
        ex.append({"test": f"S1 on {lab}"} | summarize(long_short(rets, nst, sv, "S1")))
        ex.append({"test": f"S2 on {lab}"} | summarize(long_short(rets, nst, sv, "S2")))
    r2, n2 = load_returns(russia_wipeout=False)
    ex.append({"test": "S1 with Russia's JKP returns as given"} | summarize(long_short(r2, n2, sigs, "S1")))
    ex.append({"test": "S7 with Russia's JKP returns as given"} | summarize(long_short(r2, n2, sigs, "S7")))
    er = etf_returns()
    en = pd.DataFrame(25, index=er.index, columns=er.columns)    # ETF universe: any listed ETF counts
    for k in ("S1", "S2", "S3", "S4", "S5", "S7"):
        ex.append({"test": f"{k} on iShares country ETFs"} | summarize(long_short(er, en, sigs, k, min_n=12)))
    exd = pd.DataFrame(ex); exd.to_csv(OUT / "exploratory.csv", index=False)
    say(exd.to_string(index=False, float_format=fmt))

    # ---------------------------------------------------------------- where now (formation 2026)
    now = signals_at(2026, efw, her, wdi, ele)
    z = pd.concat([zscore(now[c]) for c in ("S1", "S3", "S4", "S5")], axis=1)
    now["S7"] = z.mean(axis=1).where(z.notna().sum(axis=1) >= 2)
    el = eligible(rets, nst, 2025)
    cur = now.reindex(sorted(set(el) | set(ETF.values()))).dropna(how="all")
    cur["West"] = cur.index.isin(WEST); cur["DM"] = cur.index.isin(DM)
    cur = cur.sort_values("S7", ascending=False)
    cur.to_csv(OUT / "current_ranking.csv")
    say("\nCurrent signals (as of Oct 2026: Fraser data 2023 (the 2026 report with 2024 data is not in the mirror), "
        "Heritage 2026 vs 2021, WDI/OWID 2024 vs 2019), sorted by the composite S7:")
    say(cur.drop(columns=["S6"]).to_string(float_format=fmt))
    w = cur[cur.West]
    say("\nWestern countries only, latest Fraser 5-yr change (S1) and Heritage tax-burden change (S3):")
    say(w[["S1", "S2", "S3", "S4", "S5"]].sort_values("S1").to_string(float_format=fmt))
    log.close()


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__); sys.exit(0)
    main()
