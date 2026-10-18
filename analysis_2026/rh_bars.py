"""
Parse saved Robinhood MCP `get_equity_historicals` responses into tidy tables (scalping study, Parts B-R, C, E).

The Robinhood connector can only be called by an agent session. The agent saves each raw response (the
JSON the tool returned, or the tool-results file holding it) under data/scalping/rh/<kind>_raw/ and then
runs, e.g.:

    python3 -m analysis_2026.rh_bars data/scalping/rh/daily_raw data/scalping/rh/daily_split.parquet --adj split
    python3 -m analysis_2026.rh_bars data/scalping/rh/m5_raw     data/scalping/rh/m5_none.parquet    --adj none

Output columns: symbol, begins_at (UTC), open, high, low, close, volume, interpolated, session, interval.
Duplicate (symbol, begins_at) rows from overlapping pulls are dropped (last file wins).
Only public market data is handled here; never save account data.
"""
from __future__ import annotations

import glob
import json
import os
import sys

import pandas as pd


def _payload(text: str):
    """Return the dict that holds data.results, whatever wrapper the saved file has."""
    obj = json.loads(text[text.find("[") if text.lstrip().startswith("[") else text.find("{"):])
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if "data" in o and isinstance(o["data"], dict) and "results" in o["data"]:
                return o
            if "results" in o and isinstance(o.get("results"), list) and o["results"] and "bars" in o["results"][0]:
                return {"data": o}
            for k in ("text", "content", "result"):
                v = o.get(k)
                if isinstance(v, str) and v.lstrip()[:1] in "{[":
                    try:
                        stack.append(json.loads(v))
                    except json.JSONDecodeError:
                        pass
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(o, list):
            stack.extend(o)
    raise ValueError("no data.results found")


def parse_file(path: str) -> pd.DataFrame:
    p = _payload(open(path, encoding="utf-8").read())
    rows = []
    for r in p["data"]["results"]:
        for b in r.get("bars") or []:
            rows.append((r["symbol"], b["begins_at"], b.get("open_price"), b.get("high_price"), b.get("low_price"),
                         b.get("close_price"), b.get("volume"), bool(b.get("interpolated", False)),
                         b.get("session"), r.get("interval")))
    d = pd.DataFrame(rows, columns=["symbol", "begins_at", "open", "high", "low", "close", "volume",
                                    "interpolated", "session", "interval"])
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["begins_at"] = pd.to_datetime(d["begins_at"], utc=True)
    d["src"] = os.path.basename(path)
    return d


def parse_dir(src: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(src, "*.json")) + glob.glob(os.path.join(src, "*.txt")))
    parts = []
    for f in files:
        try:
            parts.append(parse_file(f))
        except Exception as e:                                   # report and continue
            print(f"skip {f}: {e}", file=sys.stderr)
    d = pd.concat(parts, ignore_index=True)
    d = d.drop_duplicates(["symbol", "begins_at"], keep="last").sort_values(["symbol", "begins_at"])
    return d.reset_index(drop=True)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    d = parse_dir(sys.argv[1])
    adj = sys.argv[sys.argv.index("--adj") + 1] if "--adj" in sys.argv else ""
    d["adjustment"] = adj
    d.to_parquet(sys.argv[2], index=False)
    print(f"{len(d):,} bars, {d.symbol.nunique()} symbols, {d.begins_at.min()} .. {d.begins_at.max()}")
