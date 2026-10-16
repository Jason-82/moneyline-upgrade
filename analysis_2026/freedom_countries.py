"""
Does a country's policy direction predict its stock returns? Test of the user's thesis
(2026-10-16): overweight countries moving toward lower taxes, more economic freedom and more
energy/industrial build-out; underweight those moving the other way.

Pre-registered in analysis_2026/FREEDOM_PREREG.md (commit b100171) before any result existed.
Data: python3 -m analysis_2026.fetch_freedom_data (writes data/freedom/, gitignored).

    python3 -m analysis_2026.freedom_countries      (writes analysis_2026/results_freedom/)

Implementation choices not spelled out in the pre-registration (the code was first committed with the
first-run results, so git cannot show they predate them; none binds or matters, per the audit):
- Formation dates are the end of October of each year Y, from 1997 (the first Fraser report, 1996,
  made the index public) to 2025. A signal enters once at least 15 countries have it (12 for S6).
- "Halves": 1997-2010 / 2011-2025 for signals available from 1997; otherwise the signal's own
  span is split at its middle formation year.
- A country that stops trading drops out of the portfolio average from that month (no fill).
- The Fama-MacBeth reversal control is the log return over months t-60..t-13; with 12-month momentum
  also in the regression this spans the same space as the registered "prior 60-month return", so
  the signal coefficient is identical.
Post-audit changes (AUDIT section of HANDOFF 5.20 / FINDINGS): World Bank aggregate rows removed from
the WDI panel (they entered the S7 z-scores); ETF bars with unadjusted month-end closes repaired;
overlapping-hold months labelled by calendar date; and exploratory robustness, data-repair, timing
and power lines added. The registered verdicts are computed as registered.
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
ACWI = DM + ["BRA", "CHL", "CHN", "COL", "CZE", "EGY", "GRC", "HUN", "IND", "IDN", "KOR", "KWT", "MYS", "MEX", "PER",
             "PHL", "POL", "QAT", "SAU", "ZAF", "TWN", "THA", "TUR", "ARE"]     # MSCI ACWI countries (2026)
WB_AGG = ("AFE AFW ARB CEB CSS EAP EAR EAS ECA ECS EMU EUU FCS HIC HPC IBD IBT IDA IDB IDX INX LAC LCN LDC LIC LMC LMY "
          "LTE MEA MIC MNA NAC OED OSS PRE PSS PST SAS SSA SSF SST TEA TEC TLA TMN TSA TSS UMC WLD").split()
REGIMES = {"ARG": [("2011-11", "2015-12"), ("2019-09", "2025-04")], "NGA": [("2016-06", "2023-06")],
           "EGY": [("2022-03", "2024-03")], "LKA": [("2021-01", "2022-12")], "MYS": [("1998-09", "2005-07")]}
WDI_BREAKS = {"BRA": [1995], "GHA": [2013], "IRL": [2015, 2023], "IDN": [2001, 2010], "UGA": [2009], "ZMB": [1994]}
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
    "S3": "change in Heritage tax-burden score (top rates + tax/GDP, 5-yr; up = lighter)",
    "S4": "change in manufacturing share of GDP (WDI, 5-yr)",
    "S5": "growth in electricity generation per person (OWID, 5-yr log)",
    "S6": "change in economic freedom, Western countries only",
    "S7": "composite of S1, S3, S4, S5 (mean z-score)",
}


# ============================================================================ data

def load_returns(russia_wipeout: bool = True, repair: bool = False, drop_regimes: bool = False) -> pd.DataFrame:
    """Monthly USD excess returns (rows: month-end, columns: ISO3) and stock counts.
    repair (exploratory, AUDIT): JKP's value-weighted Ireland Aug-2011..Dec-2015 (one mis-weighted mega-cap) and
    Canada Jan-Feb 1999 replaced by the equal-weighted excess return; Malaysia Oct-1998..Jul-2005 (wrong FX under
    the peg) by its local return minus the T-bill. drop_regimes: blank multiple-exchange-rate country-months."""
    d = pd.read_csv(DATA / "jkp_mkt_vw.csv")
    d["iso"] = d.location.str.upper(); d["date"] = pd.to_datetime(d.date) + pd.offsets.MonthEnd(0)
    d = d[~d.iso.isin(EXCLUDE)]
    r = d.pivot_table(index="date", columns="iso", values="ret")
    n = d.pivot_table(index="date", columns="iso", values="n_stocks")
    if russia_wipeout and "RUS" in r:
        r.loc[r.index > "2022-03-31", "RUS"] = np.nan; r.loc["2022-03-31", "RUS"] = -1.0
        n.loc[n.index > "2022-02-28", "RUS"] = np.nan
    if repair:
        o = pd.read_csv(DATA / "jkp_mkt_old.csv"); o["date"] = pd.to_datetime(o.eom) + pd.offsets.MonthEnd(0)
        o = o.set_index(["excntry", "date"])
        for iso, a, b, how in (("IRL", "2011-08", "2015-12", "ew"), ("CAN", "1999-01", "1999-02", "ew"),
                               ("MYS", "1998-10", "2005-07", "lcl")):
            x = o.loc[iso].loc[a:b]
            v = x.mkt_ew_exc if how == "ew" else x.mkt_vw_lcl - (x.mkt_vw - x.mkt_vw_exc)
            r.loc[v.index, iso] = v.to_numpy()
    if drop_regimes:
        for iso, spans in REGIMES.items():
            for a, b in spans:
                r.loc[a:b, iso] = np.nan
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
    comps = ["Property Rights", "Government Integrity", "Judicial Effectiveness", "Tax Burden", "Government Spending",
             "Fiscal Health", "Business Freedom", "Labor Freedom", "Monetary Freedom", "Trade Freedom",
             "Investment Freedom", "Financial Freedom"]
    for c in ["Overall"] + comps:
        h[c] = pd.to_numeric(h[c], errors="coerce")
    # AUDIT: Overall has methodology breaks (2017, 2022); a consistent-components score drops the broken ones
    h["consistent"] = h[["Government Integrity", "Tax Burden", "Government Spending", "Monetary Freedom",
                         "Trade Freedom", "Investment Freedom", "Financial Freedom"]].mean(axis=1, skipna=False)
    return h.dropna(subset=["iso", "year"]).rename(columns={"Tax Burden": "tax", "Overall": "overall",
                                                            "Government Spending": "spend"})


def load_macro() -> tuple[pd.DataFrame, pd.DataFrame]:
    w = pd.read_parquet(DATA / "wdi.parquet")[["iso3", "year", "manuf_gdp"]].dropna().rename(columns={"iso3": "iso"})
    w = w[~w.iso.isin(WB_AGG)]                         # World Bank regional / income aggregates (AUDIT)
    e = pd.read_csv(DATA / "owid_energy.csv", usecols=["iso_code", "year", "electricity_generation", "population"])
    e = e.dropna().rename(columns={"iso_code": "iso"})
    e = e[~e.iso.str.startswith("OWID")]
    e = e[(e.population > 0) & (e.electricity_generation > 0)]
    e["elec_pc"] = e.electricity_generation / e.population
    return w, e


# ============================================================================ signals

def _latest(df: pd.DataFrame, col: str, upto: int) -> pd.DataFrame:
    """Per country, the latest observation with year <= upto."""
    x = df[df.year <= upto].sort_values("year").groupby("iso").tail(1)
    return x[["iso", "year", col]]


def efw_signals(efw: pd.DataFrame, Y: int, lag: int = 2, k: int = 5) -> pd.DataFrame:
    """S1 (annualized change x 5 from d0 to d) and S2 (level at d); d <= Y-lag, d0 <= d-k."""
    cur = _latest(efw, "efw", Y - lag).rename(columns={"year": "d", "efw": "S2"})
    out = []
    for _, r in cur.iterrows():
        prev = efw[(efw.iso == r.iso) & (efw.year <= r.d - k)]
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


def signals_at(Y: int, efw, her, wdi, ele, macro_lag: int = 2) -> pd.DataFrame:
    s = efw_signals(efw, Y)
    s["S3"] = change_signal(her, "tax", Y)
    s = s.join(change_signal(wdi, "manuf_gdp", Y - macro_lag).rename("S4"), how="outer")
    s = s.join(change_signal(ele, "elec_pc", Y - macro_lag, log=True).rename("S5"), how="outer")
    s["S6"] = s.S1.where(s.index.isin(WEST))
    s["S7"] = composite(s)
    return s


def composite(s: pd.DataFrame, within=None) -> pd.Series:
    """S7: mean of the cross-sectional z-scores of S1, S3, S4, S5 (at least two present). within: z-score
    over those countries only (AUDIT robustness: the formation universe)."""
    x = s if within is None else s.reindex(within)
    z = pd.concat([zscore(x[c]) for c in ("S1", "S3", "S4", "S5")], axis=1)
    return z.mean(axis=1).where(z.notna().sum(axis=1) >= 2).reindex(s.index)


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
        allm = R[list(x.index)].mean(axis=1)
        cohorts.append(pd.DataFrame({"Y": Y, "ls": R[top].mean(axis=1) - R[bot].mean(axis=1),
                                     "tilt": R[top].mean(axis=1) - allm,
                                     "excl": R[[c for c in x.index if c not in bot]].mean(axis=1) - allm,
                                     "vol_top": R[top].std().mean(), "vol_bot": R[bot].std().mean(),
                                     "n": len(x)}, index=m))
    if not cohorts:
        return pd.DataFrame(columns=["ls", "tilt", "excl", "n", "Y", "Ymin", "Ymax"])
    c = pd.concat(cohorts)
    g = c.groupby(level=0)
    return pd.DataFrame({"ls": g.ls.mean(), "tilt": g.tilt.mean(), "excl": g.excl.mean(), "vol_top": g.vol_top.mean(),
                         "vol_bot": g.vol_bot.mean(), "n": g.n.mean(), "Y": g.Y.max(), "Ymin": g.Y.min(),
                         "Ymax": g.Y.max()})


def nw_t(x: np.ndarray, lags: int = 12) -> float:
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 24:
        return np.nan
    u = x - x.mean(); s = (u @ u) / n
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * (u[L:] @ u[:-L]) / n
    return x.mean() / np.sqrt(s / n)


def summarize(ls: pd.DataFrame, col: str = "ls") -> dict:
    """Annualized mean, NW t, halves (split by calendar month at November of the cut year), and the
    power figures (AUDIT): NW standard error, one-sided 95% upper bound, minimum detectable effect at
    80% power for 5% one-sided and for the Holm first-step hurdle (z 2.45)."""
    from scipy.stats import norm
    x = ls[col].dropna()
    if len(x) < 24:
        return {"months": len(x)}
    t = nw_t(x.to_numpy())
    ys = sorted(set(ls.Ymin) | set(ls.Ymax)) if "Ymin" in ls else sorted(ls.Y.unique())
    cut = 2011 if ys[0] <= 1997 else ys[len(ys) // 2]
    early = ls.index < pd.Timestamp(f"{cut}-11-30")
    h1 = ls[early][col].mean() * 12; h2 = ls[~early][col].mean() * 12
    m = x.mean() * 1200; se = m / t if t else np.nan
    return {"first_Y": int(ys[0]), "last_Y": int(ys[-1]), "months": len(x), "avg_n": ls.n.mean(),
            "ann_mean_%": m, "ann_vol_%": x.std() * np.sqrt(12) * 100, "nw_t": t,
            "p_one_sided": 1 - norm.cdf(t), "half1_%": h1 * 100, "half2_%": h2 * 100, "cut": cut,
            "se_%": se, "upper95_%": m + 1.645 * se, "mde80_%": 2.486 * se, "mde80_holm_%": 3.29 * se}


def loco(ls: pd.DataFrame) -> tuple[float, float, int, int]:
    """Leave-one-cohort-out range of the annualized mean (12-month holds), and the cohorts giving it."""
    v = {Y: ls[ls.Y != Y].ls.mean() * 1200 for Y in ls.Y.unique()}
    lo = min(v, key=v.get); hi = max(v, key=v.get)
    return v[lo], v[hi], int(lo), int(hi)


def holm(p: list[float]) -> list[float]:
    p = np.asarray(p, float); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for i, j in enumerate(o):
        run = max(run, min(1.0, (m - i) * p[j])); adj[j] = run
    return list(adj)


def fama_macbeth(rets, nst, sigs: dict, name: str) -> dict:
    """Monthly cross-sectional regressions of returns on z(signal), z(12-month momentum) and z(log return
    t-60..t-13, long-term reversal)."""
    with np.errstate(divide="ignore"):                 # Russia's -100% month -> -inf, never in a cross-section
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
    """Monthly ETF returns from dividend-adjusted month-end closes. AUDIT repair: some month-end closes in
    the yfinance bars are not distribution-adjusted (the next bar opens far away); when the next open
    differs from the close by more than 10%, the next open is used as that month's end price. Malaysia
    Sep-1998..Jun-1999 (capital controls, ETF premium) is blanked."""
    out = {}
    for t, iso in ETF.items():
        f = DATA / "etf" / f"{t}.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f, parse_dates=["timestamps"]).set_index("timestamps")
        d.index = d.index + pd.offsets.MonthEnd(0)
        d = d[~d.index.duplicated(keep="last")]
        c = d.close.copy(); nxt = d.open.shift(-1)
        bad = (nxt / c - 1).abs() > 0.10
        c[bad] = nxt[bad]
        out[iso] = c.pct_change()
    r = pd.DataFrame(out).sort_index()
    if "MYS" in r:
        r.loc["1998-09":"1999-06", "MYS"] = np.nan
    return r.iloc[:-1]                                   # the last bar may be a partial month


def timing_ladder(rets: pd.DataFrame, nst: pd.DataFrame, panel: pd.DataFrame, col: str, years,
                  offsets=(0, 1, 2, 3)) -> pd.DataFrame:
    """Post-hoc positive control (AUDIT): sort countries on the 1-year change of col in data year d and
    measure the top-minus-bottom-third calendar-year USD return in years d+offset (countries with a full
    year of returns and >= 20 stocks at the end of the prior year). Shows whether the relation exists at
    all and when it disappears relative to publication."""
    with np.errstate(divide="ignore"):
        cal = np.expm1(np.log1p(rets).groupby(rets.index.year).sum(min_count=12))
    dec = nst[nst.index.month == 12]; dec.index = dec.index.year
    rows = []
    for off in offsets:
        ls = []
        for d in years:
            yr = d + off
            if yr not in cal.index or yr - 1 not in dec.index:
                continue
            x = change_signal(panel, col, d, k=1)
            ok = dec.loc[yr - 1] >= 20
            r = cal.loc[yr].reindex(x.index).where(ok.reindex(x.index, fill_value=False)).dropna(); x = x.reindex(r.index)
            if len(x) < 15:
                continue
            k = len(x) // 3; rk = x.rank(method="first")
            ls.append((yr, r[rk > len(x) - k].mean() - r[rk <= k].mean()))
        yrs = np.array([y for y, _ in ls]); v = np.array([x for _, x in ls])
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 2 else np.nan
        rows.append({"signal": col, "return_year": f"d+{off}", "years": len(v), "ann_ls_%": v.mean() * 100, "t": t,
                     "returns_to_2012_%": v[yrs <= 2012].mean() * 100, "returns_2013_on_%": v[yrs >= 2013].mean() * 100})
    return pd.DataFrame(rows)


# ============================================================================ main

def momentum_monthly(rets: pd.DataFrame, nst: pd.DataFrame, hold: int) -> pd.DataFrame:
    """Country momentum formed every month (prior 12-month return, months t-12..t-1, >= 20 stocks), top
    minus bottom third, held `hold` months with overlapping cohorts averaged."""
    with np.errstate(divide="ignore"):
        mom = np.log1p(rets).rolling(12).sum()
    dates = rets.index[(rets.index >= "1996-10-31") & (rets.index < rets.index[-1])]
    legs = []
    for i, t in enumerate(dates):
        x = mom.loc[t][(nst.loc[t] >= 20)].dropna()
        x = x[np.isfinite(x)]
        if len(x) < 15:
            continue
        k = len(x) // 3; rk = x.rank(method="first")
        top = rk[rk > len(x) - k].index; bot = rk[rk <= k].index
        m = rets.index[rets.index > t][:hold]
        R = rets.loc[m]
        legs.append(pd.DataFrame({"ls": R[top].mean(axis=1) - R[bot].mean(axis=1), "Y": t.year}, index=m))
    c = pd.concat(legs); g = c.groupby(level=0)
    return pd.DataFrame({"ls": g.ls.mean(), "tilt": np.nan, "n": np.nan, "Y": g.Y.max(), "Ymin": g.Y.min(),
                         "Ymax": g.Y.max()})


def region_neutral(rets, nst, sigs, name) -> pd.DataFrame:
    """Average of the within-developed and within-emerging long-shorts (removes the EM-vs-DM bet)."""
    em = [c for c in rets.columns if c not in DM]
    a = long_short(rets, nst, sigs, name, universe=DM, min_n=12)
    b = long_short(rets, nst, sigs, name, universe=em, min_n=12)
    j = a.index.intersection(b.index)
    out = a.loc[j].copy()
    out["ls"] = (a.ls[j] + b.ls[j]) / 2; out["tilt"] = (a.tilt[j] + b.tilt[j]) / 2; out["n"] = a.n[j] + b.n[j]
    return out


def main():
    OUT.mkdir(exist_ok=True)
    log = open(OUT / "summary.txt", "w")

    def say(*a):
        s = " ".join(str(x) for x in a); print(s); log.write(s + "\n"); log.flush()
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    fmt = lambda x: f"{x:,.2f}"  # noqa: E731

    rets, nst = load_returns()
    efw = load_efw("2025"); her = load_heritage(); wdi, ele = load_macro()
    years = range(FIRST, LAST + 1)
    sigs = {Y: signals_at(Y, efw, her, wdi, ele) for Y in years}
    pd.concat({Y: s for Y, s in sigs.items()}, names=["Y", "iso"]).to_csv(OUT / "signals.csv")

    say("=" * 100); say("PRE-REGISTERED TESTS (FREEDOM_PREREG.md): top third minus bottom third, USD, 12-month hold"); say("=" * 100)
    rows, lss = [], {}
    for k in SIGNALS:
        ls = long_short(rets, nst, sigs, k, universe=WEST if k == "S6" else None, min_n=12 if k == "S6" else 15)
        ls.to_csv(OUT / f"ls_{k}.csv"); lss[k] = ls
        lo, hi, ylo, yhi = loco(ls)
        rows.append({"id": k, "signal": SIGNALS[k]} | summarize(ls) |
                    {"loco_min_%": lo, "loco_min_drop": ylo, "loco_max_%": hi, "loco_max_drop": yhi})
    t = pd.DataFrame(rows)
    t["p_holm"] = holm(t.p_one_sided.fillna(1).tolist())
    t["PASS"] = (t["ann_mean_%"] > 0) & (t.nw_t >= 2.0) & (t["half1_%"] > 0) & (t["half2_%"] > 0) & (t.p_holm < 0.05)
    t.to_csv(OUT / "primary.csv", index=False)
    say(t[["id", "signal", "first_Y", "last_Y", "months", "avg_n", "ann_mean_%", "ann_vol_%", "nw_t", "half1_%",
           "half2_%", "p_holm", "PASS"]].to_string(index=False, float_format=fmt))
    say("\nPower (AUDIT): NW standard error, one-sided 95% upper bound on the premium, minimum detectable effect at 80%"
        "\npower (5% one-sided / Holm first step), and the leave-one-cohort-out range (which formation year dropped):")
    say(t[["id", "se_%", "upper95_%", "mde80_%", "mde80_holm_%", "loco_min_%", "loco_min_drop", "loco_max_%",
           "loco_max_drop"]].to_string(index=False, float_format=fmt))
    say("Note: S7 excludes the World Bank aggregate rows that the first run included in its z-scores (AUDIT); the first"
        "\nrun printed +1.22%/yr (t 0.68). All verdicts are unchanged.")

    say("\nSecondary (Hxb): Fama-MacBeth, country return on z(signal), z(12-month momentum) and z(log return t-60..t-13);"
        "\ncoefficients in % per month per 1 SD:")
    fm = pd.DataFrame([{"id": k} | fama_macbeth(rets, nst, sigs, k) for k in SIGNALS if k != "S6"])
    say(fm.to_string(index=False, float_format=fmt)); fm.to_csv(OUT / "fama_macbeth.csv", index=False)

    coh = pd.DataFrame({k: lss[k].groupby("Y").ls.mean() * 1200 for k in ("S1", "S2", "S3", "S4", "S5", "S7")})
    coh.to_csv(OUT / "cohorts.csv")
    say("\nCohort table (annualized long-short of each formation year, %): the 1997 cohort (Asian and Russian crises) is"
        "\nthe most influential for S1, S2, S4 and S7; formations 1997-2001 share one 1990->1995 Fraser sort:")
    say(coh.to_string(float_format=fmt))

    # ---------------------------------------------------------------- exploratory
    say("\n" + "=" * 100); say("EXPLORATORY (none of these changes a verdict; 40+ rows, so expect a few |t| > 2 by chance)")
    say("=" * 100)
    ex = []

    def add(label, ls, col="ls"):
        ex.append({"test": label} | summarize(ls, col))
    em = [c for c in rets.columns if c not in DM]
    for k in ("S1", "S2", "S3", "S4", "S7"):
        add(f"{k} within developed", long_short(rets, nst, sigs, k, universe=DM, min_n=12))
        add(f"{k} within emerging/other", long_short(rets, nst, sigs, k, universe=em, min_n=12))
        add(f"{k} region-neutral (mean of within-DM and within-EM)", region_neutral(rets, nst, sigs, k))
        add(f"{k} MSCI ACWI countries only", long_short(rets, nst, sigs, k, universe=ACWI, min_n=12))
        add(f"{k} long-only tilt (top third minus all)", long_short(rets, nst, sigs, k), "tilt")
        for H in (36, 60):
            add(f"{k} {H}-month hold (overlapping cohorts)", long_short(rets, nst, sigs, k, H=H))
    for k in ("S1", "S2", "S3", "S7"):
        add(f"{k} exclusion screen (all but the bottom third, minus all)", long_short(rets, nst, sigs, k), "excl")
    for Y in years:                                     # prior 12-month return at the October formation
        t0 = pd.Timestamp(f"{Y}-10-31")
        with np.errstate(divide="ignore"):
            sigs[Y]["MOM"] = np.expm1(np.log1p(rets.loc[:t0].tail(12)).sum(min_count=12)).reindex(sigs[Y].index)
    add("12-month momentum, formed each October, held 12 months", long_short(rets, nst, sigs, "MOM"))
    add("12-month momentum, October formation, long-only tilt", long_short(rets, nst, sigs, "MOM"), "tilt")
    for H in (1, 3, 6, 12):
        add(f"12-month momentum formed monthly, held {H} month(s)", momentum_monthly(rets, nst, H))
    big = nst.where(nst >= 50)
    for k in ("S1", "S4", "S7"):
        add(f"{k} markets with >= 50 stocks", long_short(rets, big, sigs, k))
    for Y in years:
        el = eligible(rets, nst, Y)
        sigs[Y]["S7e"] = composite(sigs[Y], within=el)
        sigs[Y]["X_her"] = change_signal(her, "overall", Y).reindex(sigs[Y].index)
        sigs[Y]["X_herc"] = change_signal(her, "consistent", Y).reindex(sigs[Y].index)
        sigs[Y]["X_spend"] = change_signal(her, "spend", Y).reindex(sigs[Y].index)
    add("S7 with z-scores within the formation universe", long_short(rets, nst, sigs, "S7e"))
    add("Heritage overall score, 5-yr change (methodology breaks 2017/2022)", long_short(rets, nst, sigs, "X_her"))
    add("Heritage overall score, 5-yr change, formations <= 2016 only",
        long_short(rets, nst, {Y: s for Y, s in sigs.items() if Y <= 2016}, "X_her"))
    add("Heritage score from break-free components, 5-yr change", long_short(rets, nst, sigs, "X_herc"))
    add("Heritage government-spending score, 5-yr change", long_short(rets, nst, sigs, "X_spend"))
    # Fraser vintages, chain-linked panel, lags and horizons
    ec = load_efw("2025", chain=True)
    sc = {Y: signals_at(Y, ec, her, wdi, ele) for Y in years}
    for k in ("S1", "S2", "S7"):
        add(f"{k} on the Fraser 2025 chain-linked panel", long_short(rets, nst, sc, k))
    add("S6 on the Fraser 2025 chain-linked panel", long_short(rets, nst, sc, "S6", universe=WEST, min_n=12))
    e19 = load_efw("2019")
    s19 = {Y: efw_signals(e19, Y) for Y in years if Y <= 2019}
    add("S1 on the Fraser 2019 release (formations to 2019)", long_short(rets, nst, s19, "S1"))
    add("S2 on the Fraser 2019 release (formations to 2019)", long_short(rets, nst, s19, "S2"))
    for lag, kk in ((1, 5), (3, 5), (2, 3)):
        sv = {Y: efw_signals(efw, Y, lag=lag, k=kk) for Y in years}
        add(f"S1 with Fraser lag {lag} years, {kk}-year change", long_short(rets, nst, sv, "S1"))
    for ml in (1, 3):
        sv = {Y: signals_at(Y, efw, her, wdi, ele, macro_lag=ml) for Y in years}
        add(f"S4 with WDI lag {ml} year(s)", long_short(rets, nst, sv, "S4"))
    sb = {}
    for Y, s in sigs.items():
        s2 = s.copy()
        for iso, bs in WDI_BREAKS.items():
            if iso in s2.index and any(Y - 7 < b <= Y - 2 for b in bs):
                s2.loc[iso, "S4"] = np.nan
        s2["S7"] = composite(s2); sb[Y] = s2
    add("S4 with WDI series breaks blanked", long_short(rets, nst, sb, "S4"))
    add("S7 with WDI series breaks blanked", long_short(rets, nst, sb, "S7"))
    # data repairs
    r2, n2 = load_returns(russia_wipeout=False)
    add("S1 with Russia's JKP returns as given", long_short(r2, n2, sigs, "S1"))
    add("S7 with Russia's JKP returns as given", long_short(r2, n2, sigs, "S7"))
    rr, nr = load_returns(repair=True, drop_regimes=True)
    for k in SIGNALS:
        add(f"{k} with IRL/CAN/MYS repaired and multiple-rate regime months dropped",
            long_short(rr, nr, sigs, k, universe=WEST if k == "S6" else None, min_n=12 if k == "S6" else 15))
    exd = pd.DataFrame(ex)
    exd.to_csv(OUT / "exploratory.csv", index=False)
    vt = pd.DataFrame([{"signal": k, "top_third_vol_%": lss[k].vol_top.mean() * np.sqrt(12) * 100,
                        "bottom_third_vol_%": lss[k].vol_bot.mean() * np.sqrt(12) * 100} for k in ("S1", "S2", "S3", "S7")])
    vt.to_csv(OUT / "volatility_by_third.csv", index=False)
    say(exd[["test", "first_Y", "last_Y", "months", "avg_n", "ann_mean_%", "nw_t", "half1_%", "half2_%"]].to_string(
        index=False, float_format=fmt))
    say("\nAverage single-country volatility over the holding year, top vs bottom third (annualized, %):")
    say(vt.to_string(index=False, float_format=fmt))

    er = etf_returns()
    en = pd.DataFrame(25, index=er.index, columns=er.columns)    # ETF universe: any listed ETF counts
    et = pd.DataFrame([{"test": f"{k} on iShares country ETFs"} | summarize(long_short(er, en, sigs, k, min_n=12))
                       for k in ("S1", "S2", "S3", "S4", "S5", "S7")])
    et["p_holm_6"] = holm(et.p_one_sided.fillna(1).tolist())
    et.to_csv(OUT / "etf_tests.csv", index=False)
    say("\niShares country ETFs (the countries that had an ETF at each date; same signals; Holm across these six):")
    say(et[["test", "first_Y", "last_Y", "avg_n", "ann_mean_%", "nw_t", "half1_%", "half2_%", "p_holm_6"]].to_string(
        index=False, float_format=fmt))

    # ---------------------------------------------------------------- positive control: timing
    lad = pd.concat([
        timing_ladder(rets, nst, efw[efw.year >= 2000], "efw", range(2001, 2024), (0, 1, 2, 3)),
        timing_ladder(rets, nst, her, "tax", range(1996, 2027), (-1, 0, 1, 2)),
        timing_ladder(rets, nst, wdi, "manuf_gdp", range(1991, 2025), (0, 1, 2, 3))])
    lad.to_csv(OUT / "timing_ladder.csv", index=False)
    say("\nPositive control (post hoc): countries sorted on the 1-year change in data year d, top-minus-bottom third of"
        "\ncalendar-year USD returns in year d+offset. Fraser publishes year d around September of d+2; Heritage index"
        "\nyear d (data through mid d-1) in early d; WDI around mid d+1:")
    say(lad.to_string(index=False, float_format=fmt))

    # ---------------------------------------------------------------- the West in the global sorts
    wl = []
    for Y, s in sigs.items():
        x = s["S1"].reindex(eligible(rets, nst, Y)).dropna()
        if len(x) < 15:
            continue
        k = len(x) // 3; rk = x.rank(method="first")
        top = set(rk[rk > len(x) - k].index); bot = set(rk[rk <= k].index)
        wl.append({"Y": Y, "west_n": sum(c in WEST for c in x.index), "west_top": len(top & set(WEST)),
                   "west_bottom": len(bot & set(WEST)), "usa_bottom": "USA" in bot})
    wl = pd.DataFrame(wl)
    say(f"\nGlobal S1 and the West: {wl.west_top.sum()} of {wl.west_n.sum()} Western country-years in the long third, "
        f"{wl.west_bottom.sum()} in the short third; USA in the short third in {int(wl.usa_bottom.sum())} of {len(wl)} "
        "formations. The premise-matching tests are S6 and S1 within developed markets.")

    # ---------------------------------------------------------------- where now (formation 2026)
    now = signals_at(2026, efw, her, wdi, ele)
    el25 = eligible(rets, nst, 2025)
    cur = now.reindex(sorted(set(el25) | set(ETF.values()))).dropna(how="all")
    cur["West"] = cur.index.isin(WEST); cur["DM"] = cur.index.isin(DM)
    cur = cur.sort_values("S7", ascending=False)
    cur.to_csv(OUT / "current_ranking.csv")
    say("\nDESCRIPTIVE ONLY: S7 failed its pre-registered test; this is not a recommendation. Current signals as of Oct"
        "\n2026 (Fraser data 2023 vs 2018: the 2026 report with 2024 data is not in the mirror; Heritage 2026 vs 2021;"
        "\nWDI/OWID 2024 vs 2019). The data end before 2025-26 events. S4 picks up shifts in sector composition"
        "\n(pharma, petrochemicals, GDP shrinking in crises), not only policy-driven build-out. Sorted by S7:")
    say(cur.drop(columns=["S6"]).to_string(float_format=fmt))
    third = []
    u = [c for c in el25 if c in now.index]
    for k in ("S1", "S2", "S3", "S4", "S5", "S7"):
        x = now[k].reindex(u).dropna(); kk = len(x) // 3; rk = x.rank(method="first")
        third.append({"signal": k, "n": len(x), "west_in_top_third": int(sum(c in WEST for c in rk[rk > len(x) - kk].index)),
                      "west_in_bottom_third": int(sum(c in WEST for c in rk[rk <= kk].index))})
    say("\nWhere the West sits today in each signal (JKP 2025 universe):")
    say(pd.DataFrame(third).to_string(index=False))

    def chg(a, b):
        p = efw.pivot_table(index="iso", columns="year", values="efw")
        return p[b] - p[a]
    w = pd.DataFrame({"S1_2018_23": chg(2018, 2023), "chg_2019_20": chg(2019, 2020), "chg_2020_23": chg(2020, 2023)})
    w = w.join(now[["S2", "S3", "S4", "S5"]])
    wt = w.reindex(WEST).sort_values("S1_2018_23")
    means = pd.DataFrame([w.reindex(WEST).mean().rename("mean: West"), w.drop(index=WEST, errors="ignore").mean().rename(
        "mean: rest of world"), w.reindex(el25).mean().rename("mean: JKP 2025 universe")])
    say("\nWestern countries: Fraser change 2018->2023 split into the COVID data year (2019->20) and since (2020->23),"
        "\nwith Heritage tax-burden change (S3), manufacturing (S4) and electricity (S5) as of Oct 2026:")
    say(pd.concat([wt, means]).to_string(float_format=fmt))
    log.close()


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__); sys.exit(0)
    main()
