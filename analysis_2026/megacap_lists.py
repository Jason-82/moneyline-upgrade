"""
Year-end top-20 S&P 500 market-cap lists for the mega-cap dip study (MEGACAP_DIP_PREREG.md, "Size lists").

    python3 -m analysis_2026.megacap_lists check RAW.json      # flags: symbols, price consistency, omissions
    python3 -m analysis_2026.megacap_lists write RAW.json      # -> results_megacap_dip/topcap_lists.csv

RAW.json: {"years": [{"year_end", "consensus": [{"rank", "company", "dataset_symbol", "mcap_bn", "tech", "sources",
"confidence", "note"}], ...}]} as compiled from public sources (FinHacker's yearly top-20 tables plus independent
sources), with any later corrections applied to the same file.

Checks (pre-registered):
- every entry maps to a price series in data/universe_pit_all/ and the company was an S&P 500 member at the date;
- price consistency: for a company in consecutive lists, log(cap ratio) within 0.25 of log(price ratio) (total-return
  closes, so dividends add a little drift);
- omissions: a company's cap carried from the nearest year with a reported cap (at most MAX_CARRY years away) by price
  ratios; a member that would rank inside the top 20 (or top 10) but is missing is flagged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PIT = ROOT / "data" / "universe_pit_all"
OUT = ROOT / "analysis_2026" / "results_megacap_dip"
TOL = 0.25
AUDIT = "audit 2026-10-30: nominal year-end close x share count from filings"

# Corrections applied to the compiled lists after the audit (year_end, symbol, changes; None drops the entry).
CORRECTIONS = [
    (2006, "AIG", {"rank": 10, "mcap_bn": 186.4, "estimated": False,
                   "sources": "AIG 10-K FY2006 cover 2,601,583,676 sh x $71.66"},
     "AIG, not Pfizer, was #10 at end-2006 (the Pfizer value used a stale Q3 share count)"),
    (2006, "PFE", {"rank": 11, "mcap_bn": 183.7, "estimated": False,
                   "sources": "Pfizer 10-K FY2006: about 7.10bn sh x $25.90"}, "see AIG 2006"),
    (2001, "BMY", None, "Royal Dutch (104.2bn) belongs at #19; Bristol-Myers (98.7bn) is #21"),
    (2001, "PG", {"rank": 20}, "moved down one place by Royal Dutch"),
    (2001, "RDS-A", {"rank": 19, "company": "Royal Dutch Petroleum", "ticker_then": "RD", "mcap_bn": 104.2,
                     "tech": False, "estimated": False, "confidence": "high",
                     "sources": "Royal Dutch 20-F 2001: 2,126,647,800 sh x $49.02"},
     "missing from the compiled list; S&P 500 member until 2002-07-22"),
    (1995, "T-200511", {"mcap_bn": 103.6, "estimated": True, "sources": AUDIT}, "value filled"),
    (1995, "MO", {"mcap_bn": 75.9, "estimated": True, "sources": AUDIT}, "value filled"),
    (1995, "RDS-A", {"mcap_bn": 75.6, "estimated": True, "sources": AUDIT}, "value filled"),
    (1996, "RDS-A", {"mcap_bn": 91.5, "estimated": True, "sources": AUDIT}, "value filled"),
    (1997, "RDS-A", {"rank": 6, "mcap_bn": 116.2, "estimated": True, "sources": AUDIT}, "value filled; #6 ahead of Intel"),
    (1997, "INTC", {"rank": 7}, "behind Royal Dutch"),
    (2000, "RDS-A", {"mcap_bn": 129.6, "estimated": True, "sources": AUDIT}, "value filled"),
]

# Why each remaining checker flag does not change a list (topcap_flags.csv 'resolution').
MERGERS = {
    ("BAC", 1996): "carried from 1998, after the NationsBank-BankAmerica merger doubled the share count",
    ("BAC", 1997): "carried from 1998, after the NationsBank-BankAmerica merger doubled the share count",
    ("C", 1996): "carried from 1998, after the Travelers-Citicorp merger",
    ("C", 1997): "carried from 1998, after the Travelers-Citicorp merger",
    ("T", 1995): "carried from 1997, after SBC's Pacific Telesis merger",
    ("VZ", 1995): "carried from 1997, after Bell Atlantic's NYNEX merger",
    ("VZ", 1999): "carried from 2000, after the Bell Atlantic-GTE merger",
    ("JCI", 2000): "Tyco lineage, carried from 2001, after the CIT acquisition",
    ("JPM", 2002): "carried from 2004, after the Bank One merger",
    ("JPM", 2003): "carried from 2004, after the Bank One merger",
    ("T", 2005): "carried from 2006, after SBC bought AT&T (Nov 2005) and BellSouth (Dec 2006); about 95bn at end-2005",
    ("MRK", 2007): "carried from 2009, after the Schering-Plough merger",
    ("MRK", 2008): "carried from 2009, after the Schering-Plough merger",
    ("MRK", 2010): "about 111bn at end-2010, below #20",
    ("MO", 2008): "carried from 2007, before the PMI spin-off (Altria about 31bn at end-2008)",
    ("MO", 2009): "carried from 2007, before the PMI spin-off (Altria about 41bn at end-2009)",
    ("VZ", 2012): "carried from 2014, after Verizon bought Vodafone's stake; about 124bn at end-2012, a tie at #20",
    ("VZ", 2013): "carried from 2014, after Verizon bought Vodafone's stake; about 141bn at end-2013",
    ("BAC", 2004): "FleetBoston merger (April 2004)",
    ("MO", 2007): "Kraft spin-off (March 2007)",
    ("PG", 2005): "Gillette merger (October 2005)",
    ("T", 1999): "Ameritech merger (October 1999)",
    ("XOM", 1999): "Mobil merger (November 1999)",
}
MAX_CARRY = 2                   # years: share counts and dividends drift too far beyond that


def year_end_close(sym, y, cache={}):
    """Total-return close on the last trading day of year y (NaN if the series does not cover it)."""
    if sym not in cache:
        f = PIT / f"{sym}.csv"
        cache[sym] = pd.read_csv(f, index_col=0, parse_dates=True)["close"] if f.exists() else None
    c = cache[sym]
    if c is None:
        return np.nan
    x = c.loc[:f"{y}-12-31"]
    if x.empty or x.index[-1] < pd.Timestamp(f"{y}-12-20"):
        return np.nan
    return float(x.iloc[-1])


def member_on(mem, sym, date):
    """S&P 500 member on `date` (members.csv starts 1996-01-02: an end-1995 list is checked on that day)."""
    date = max(pd.Timestamp(date), pd.Timestamp("1996-01-02"))
    g = mem[mem.symbol == sym]
    return bool(((g.start <= date) & (g.end.isna() | (g.end >= date))).any())


def apply_corrections(F):
    F = F.copy()
    F["correction"] = ""
    for y, sym, ch, why in CORRECTIONS:
        m = (F.year_end == y) & (F.symbol == sym)
        if ch is None:
            F = F[~m]
            continue
        if not m.any():
            row = {"year_end": y, "symbol": sym, "company": sym, "tech": False, "confidence": "", "note": "",
                   "estimated": False, "sources": "", "rank": 0, "mcap_bn": -1.0}
            F = pd.concat([F, pd.DataFrame([row])], ignore_index=True)
            m = (F.year_end == y) & (F.symbol == sym)
        for k, v in ch.items():
            if k in F.columns:
                F.loc[m, k] = v
        F.loc[m, "correction"] = why
    return F.sort_values(["year_end", "rank"]).reset_index(drop=True)


def resolution(kind, year, symbol, detail):
    if kind == "no-cap":
        return "ranked on derived evidence (index-fund holding order, filings); see the entry's note"
    if kind == "no-symbol":
        return "no price series in the dataset: dropped and reported"
    if (symbol, year) in MERGERS:
        return MERGERS[(symbol, year)]
    if kind.startswith("omission"):
        return ("carried estimate drifts with dividends and buybacks; nominal close x filed shares puts it at or "
                "below #20 (audit), a tie at most")
    return ""


def frame(raw):
    rows = []
    for Y in raw["years"]:
        for e in Y["consensus"]:
            rows.append({"year_end": int(Y["year_end"]), "rank": int(e["rank"]), "company": e["company"],
                         "symbol": (e.get("dataset_symbol") or "").upper(), "mcap_bn": float(e["mcap_bn"]),
                         "tech": bool(e["tech"]), "sources": ";".join(e.get("sources") or []),
                         "confidence": e.get("confidence", ""), "note": e.get("note", ""),
                         "estimated": bool(e.get("estimated", False))})
    return apply_corrections(pd.DataFrame(rows).sort_values(["year_end", "rank"]).reset_index(drop=True))


def check(raw):
    F = frame(raw)
    mem = pd.read_csv(PIT / "members.csv", parse_dates=["start", "end"])
    mem["symbol"] = mem.symbol.str.upper()
    flags = []
    for r in F.itertuples():
        d = pd.Timestamp(f"{r.year_end}-12-31")
        if not r.symbol:
            flags.append(("no-symbol", r.year_end, r.company, ""))
        elif not (PIT / f"{r.symbol}.csv").exists():
            flags.append(("no-price-file", r.year_end, r.company, r.symbol))
        elif not member_on(mem, r.symbol, d - pd.Timedelta(days=1)):
            flags.append(("not-member", r.year_end, r.company, r.symbol))
        if r.mcap_bn <= 0:
            flags.append(("no-cap", r.year_end, r.company, r.symbol))
    for y, g in F.groupby("year_end"):
        if len(g) != 20:
            flags.append(("count", y, f"{len(g)} entries", ""))
        caps = g.sort_values("rank").mcap_bn.to_numpy()
        caps = caps[caps > 0]
        if np.any(np.diff(caps) > 1e-9):
            flags.append(("rank-order", y, "caps not descending by rank", ""))
        dup = g.symbol[g.symbol.duplicated() & (g.symbol != "")]
        for s in dup:
            flags.append(("duplicate", y, s, s))
    # price consistency between consecutive lists
    cap = {(r.symbol, r.year_end): r.mcap_bn for r in F.itertuples() if r.symbol and r.mcap_bn > 0}
    for (s, y), c in sorted(cap.items()):
        if (s, y + 1) in cap:
            p0, p1 = year_end_close(s, y), year_end_close(s, y + 1)
            if np.isfinite(p0) and np.isfinite(p1):
                gap = np.log(cap[(s, y + 1)] / c) - np.log(p1 / p0)
                if abs(gap) > TOL:
                    flags.append(("price-gap", y + 1, f"{s}: cap ratio {cap[(s, y + 1)] / c:.2f} vs price ratio "
                                  f"{p1 / p0:.2f} (log gap {gap:+.2f})", s))
    # omissions: carry each candidate's cap to every year by price ratios from its nearest reported year
    syms = sorted({s for s, _ in cap})
    years = sorted(F.year_end.unique())
    for y in years:
        g = F[F.year_end == y]
        c20 = g[g.mcap_bn > 0].mcap_bn.min()
        c10 = g[(g["rank"] <= 10) & (g.mcap_bn > 0)].mcap_bn.min()
        for s in syms:
            if s in set(g.symbol):
                continue
            known = sorted((abs(yy - y), yy) for (ss, yy) in cap if ss == s and abs(yy - y) <= MAX_CARRY)
            if not known:
                continue
            yy = known[0][1]
            p0, p1 = year_end_close(s, yy), year_end_close(s, y)
            if not (np.isfinite(p0) and np.isfinite(p1)):
                continue
            est = cap[(s, yy)] * p1 / p0
            if est > c20 and member_on(mem, s, pd.Timestamp(f"{y}-12-30")):
                lvl = "omission-top10" if est > c10 else "omission-top20"
                flags.append((lvl, y, f"{s}: carried from {yy} = {est:.0f}bn vs #20 {c20:.0f}bn / #10 {c10:.0f}bn", s))
    fl = pd.DataFrame(flags, columns=["kind", "year", "detail", "symbol"])
    fl["resolution"] = [resolution(k, y, sym, d) for k, y, d, sym in zip(fl.kind, fl.year, fl.detail, fl.symbol)]
    return F, fl


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    raw = json.loads(Path(path).read_text())
    F, flags = check(raw)
    if cmd == "check":
        pd.set_option("display.width", 200, "display.max_colwidth", 120, "display.max_rows", 500)
        print(flags.to_string(index=False) if len(flags) else "no flags")
        print(f"\n{len(F)} entries, {F.year_end.nunique()} year-ends, {len(flags)} flags")
    elif cmd == "write":
        OUT.mkdir(parents=True, exist_ok=True)
        F.to_csv(OUT / "topcap_lists.csv", index=False)
        flags.to_csv(OUT / "topcap_flags.csv", index=False)
        print(f"wrote {len(F)} entries and {len(flags)} remaining flags")


if __name__ == "__main__":
    main()
