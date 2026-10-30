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
- omissions: a company's cap carried from the nearest year with a reported cap by price ratios; a member that would
  rank inside the top 20 (or top 10) but is missing is flagged.
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


def frame(raw):
    rows = []
    for Y in raw["years"]:
        for e in Y["consensus"]:
            rows.append({"year_end": int(Y["year_end"]), "rank": int(e["rank"]), "company": e["company"],
                         "symbol": (e.get("dataset_symbol") or "").upper(), "mcap_bn": float(e["mcap_bn"]),
                         "tech": bool(e["tech"]), "sources": ";".join(e.get("sources") or []),
                         "confidence": e.get("confidence", ""), "note": e.get("note", ""),
                         "estimated": bool(e.get("estimated", False))})
    return pd.DataFrame(rows).sort_values(["year_end", "rank"]).reset_index(drop=True)


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
            known = sorted((abs(yy - y), yy) for (ss, yy) in cap if ss == s)
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
    return F, pd.DataFrame(flags, columns=["kind", "year", "detail", "symbol"])


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
