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
import os
import tempfile
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screener.data import from_robinhood_json, normalise  # noqa: E402


def _prepare_merge(folder: Path, sym: str, df: pd.DataFrame, full_refresh=False) -> pd.DataFrame:
    df = normalise(df)
    f = folder / f"{sym}.csv"
    if f.exists() and full_refresh:
        old_dates = pd.to_datetime(pd.read_csv(f, float_precision="round_trip")["date"])
        if df.index.min() > old_dates.min() or df.index.max() < old_dates.max():
            raise ValueError(f"{sym}: --full-refresh must cover the entire existing history, not a recent slice")
    if f.exists() and not full_refresh:
        old = normalise(pd.read_csv(f, float_precision="round_trip"))
        common = old.index.intersection(df.index)
        if not len(common):
            raise ValueError(f"{sym}: no overlapping bars to verify adjustment scale; use a full-history --full-refresh")
        ratio = df.loc[common, ["open", "high", "low", "close"]] / old.loc[common, ["open", "high", "low", "close"]]
        if ((ratio - 1).abs() > 0.01).any().any():
            raise ValueError(f"{sym}: overlapping prices changed scale; refresh the complete split-adjusted history with --full-refresh")
        df = pd.concat([old, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    return normalise(df)


def _atomic_write(folder: Path, sym: str, df: pd.DataFrame):
    folder.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=f".{sym}.", suffix=".csv.tmp", dir=folder)
    try:
        with os.fdopen(fd, "w") as fh:
            df.to_csv(fh, float_format="%.12g")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(path, folder / f"{sym}.csv")
    finally:
        if os.path.exists(path):
            os.unlink(path)


def merge_into(folder: Path, sym: str, df: pd.DataFrame, *, full_refresh=False) -> int:
    df = _prepare_merge(folder, sym, df, full_refresh)
    _atomic_write(folder, sym, df)
    return len(df)


def ingest_file(path: str | Path, folder: Path, *, delete=False, full_refresh=False) -> dict[str, int]:
    """Delete raw input only after every symbol parsed and every CSV merge succeeded."""
    data = from_robinhood_json(path, require_complete=True)
    if not data or any(frame.empty for frame in data.values()):
        raise ValueError("response contains no usable closed daily bars")
    prepared = {sym: _prepare_merge(folder, sym, frame, full_refresh) for sym, frame in data.items()}
    for sym, frame in prepared.items():
        _atomic_write(folder, sym, frame)
    if delete:
        Path(path).unlink()
    return {sym: len(frame) for sym, frame in prepared.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True)
    ap.add_argument("--out", default="data/universe")
    ap.add_argument("--delete", action="store_true", help="delete each raw file after a successful merge")
    ap.add_argument("--full-refresh", action="store_true", help="replace each existing symbol with complete refreshed split-only history")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    paths = sorted(glob.glob(a.glob))
    if a.full_refresh:
        # A multi-part refresh is assembled before replacing history; otherwise each
        # successive raw file would overwrite the preceding part of the same ticker.
        try:
            combined = {}
            for p in paths:
                for sym, frame in from_robinhood_json(p, require_complete=True).items():
                    combined.setdefault(sym, []).append(frame)
            if not combined:
                raise ValueError("no usable complete responses for full refresh")
            prepared = {sym: _prepare_merge(out, sym, normalise(pd.concat(parts)), full_refresh=True)
                        for sym, parts in combined.items()}
            for sym, frame in prepared.items():
                _atomic_write(out, sym, frame)
            if a.delete:
                for p in paths:
                    Path(p).unlink()
            print(f"full refresh: {len(prepared)} symbols {sorted(prepared)}")
        except (ValueError, OSError) as exc:
            print(f"full refresh failed; raw files retained: {exc}")
        return
    for p in paths:
        try:
            counts = ingest_file(p, out, delete=a.delete, full_refresh=a.full_refresh)
        except (ValueError, OSError) as exc:
            print(f"{Path(p).name}: {exc}")
            continue
        print(f"{Path(p).name}: {len(counts)} symbols {sorted(counts)}")


if __name__ == "__main__":
    main()
