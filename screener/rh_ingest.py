"""
Merge saved Robinhood get_equity_historicals results into a per-symbol CSV store.

Claude Code saves a large MCP result to a file instead of putting it in the
conversation. Robinhood caps a daily request at 5,000 bars per symbol, so 1999-today
takes two calls per batch of 10 symbols; this merges the pieces.

    python -m screener.rh_ingest --glob '<tool-results dir>/mcp-Robinhood-get_equity_historicals-*.txt' \
        --out data/universe --delete

Robinhood has no history for delisted symbols, and a recycled ticker returns the new
company's bars. Check coverage against membership dates before using the store.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screener.data import from_robinhood_json, normalise  # noqa: E402


def merge_into(folder: Path, sym: str, df: pd.DataFrame) -> int:
    f = folder / f"{sym}.csv"
    if f.exists():
        df = pd.concat([normalise(pd.read_csv(f)), df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_csv(f, float_format="%.6g")
    return len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True)
    ap.add_argument("--out", default="data/universe")
    ap.add_argument("--delete", action="store_true", help="delete each raw file after a successful merge")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    nf_file = out / "_not_found.txt"
    for p in sorted(glob.glob(a.glob)):
        raw = json.loads(Path(p).read_text())
        nf = (raw.get("data") or {}).get("not_found") if isinstance(raw, dict) else None
        if nf:
            with nf_file.open("a") as fh:
                fh.write("\n".join(map(str, nf)) + "\n")
        try:
            data = from_robinhood_json(p)
        except ValueError as exc:
            print(f"{Path(p).name}: {exc}")
            data = {}
        for sym, df in data.items():
            if len(df):
                merge_into(out, sym, df)
        print(f"{Path(p).name}: {len(data)} symbols {sorted(data)}" + (f" | not found {nf}" if nf else ""))
        if a.delete:
            Path(p).unlink()


if __name__ == "__main__":
    main()
