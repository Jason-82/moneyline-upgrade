"""
Rebuild the gitignored data for the scalping / market-making study (analysis_2026/SCALPING_PREREG.md).

    python3 -m analysis_2026.fetch_scalping_data qlib       # qlib US daily set -> data/scalping/qlib/panel.parquet
    python3 -m analysis_2026.fetch_scalping_data etf        # Nasdaq symbol directory (ETF flags)
    python3 -m analysis_2026.fetch_scalping_data klines     # Binance spot daily klines, all USDT pairs, 2025-01..2026-09
    python3 -m analysis_2026.fetch_scalping_data all

Sources (all third-party, reachable from the Claude cloud sandbox):
  qlib     github.com/SunsetWolf/qlib_dataset release v0, qlib_data_us_1d_v3.zip (615 MB; Yahoo-derived,
           13,354 symbols 1999-12-31..2024-04-25; effectively a Nov-2020 snapshot, survivor-biased)
  etf      raw.githubusercontent.com/datasets/nasdaq-listings (nasdaq-listed-symbols.csv) and datasets/nyse-other-listings
           (other-listed.csv: NYSE, NYSE American, Arca, Cboe); both have an ETF column (current snapshots)
  klines   Binance public archive through its S3 bucket (data.binance.vision itself is blocked here)
The Robinhood daily / 5-minute bars (Parts B-R and C) can only be pulled through the Robinhood MCP by an
agent session; see HANDOFF section 5.21 for the procedure. Binance trade files are streamed by
analysis_2026/scalp_crypto.py.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import io
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "scalping"
QLIB_URL = "https://github.com/SunsetWolf/qlib_dataset/releases/download/v0/qlib_data_us_1d_v3.zip"
ETF_URLS = {"nasdaq-listed-symbols.csv":
            "https://raw.githubusercontent.com/datasets/nasdaq-listings/main/data/nasdaq-listed-symbols.csv",
            "other-listed.csv": "https://raw.githubusercontent.com/datasets/nyse-other-listings/main/data/other-listed.csv"}
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
QLIB_FIELDS = ("open", "high", "low", "close", "volume", "factor")


def get(url: str, timeout=300) -> bytes | None:
    for k in range(4):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            if k == 3:
                raise
        except Exception:
            if k == 3:
                raise
    return None


def s3_ls(prefix: str, delimiter: str = "/") -> tuple[list[str], list[tuple[str, int]]]:
    """List common prefixes and keys under a Binance-archive prefix (paginated)."""
    marker, prefixes, keys = "", [], []
    while True:
        q = {"prefix": prefix, "delimiter": delimiter}
        if marker:
            q["marker"] = marker
        root = ET.fromstring(get(S3 + "?" + urllib.parse.urlencode(q), 60))
        cp = [e.find(NS + "Prefix").text for e in root.findall(NS + "CommonPrefixes")]
        ks = [(e.find(NS + "Key").text, int(e.find(NS + "Size").text)) for e in root.findall(NS + "Contents")]
        prefixes += cp; keys += ks
        if root.find(NS + "IsTruncated").text != "true":
            return prefixes, keys
        nm = root.find(NS + "NextMarker")
        marker = nm.text if nm is not None else (ks[-1][0] if ks else cp[-1])


def s3_get_zip_csv(key: str, verify: bool = True) -> bytes | None:
    """Download one archive zip, check its .CHECKSUM, return the CSV bytes inside (None if missing)."""
    key = urllib.parse.quote(key)                    # some symbols are non-ASCII
    b = get(f"{S3}/{key}")
    if b is None:
        return None
    if verify:
        c = get(f"{S3}/{key}.CHECKSUM", 60)
        if c and c.decode().split()[0] != hashlib.sha256(b).hexdigest():
            raise IOError(f"checksum mismatch {key}")
    z = zipfile.ZipFile(io.BytesIO(b))
    return z.read(z.namelist()[0])


# ---------------------------------------------------------------- qlib
def qlib():
    d = OUT / "qlib"; d.mkdir(parents=True, exist_ok=True)
    zp = d / "qlib_data_us_1d_v3.zip"
    if not zp.exists():
        zp.write_bytes(get(QLIB_URL, 1800))
    z = zipfile.ZipFile(zp)
    cal = pd.to_datetime(z.read("calendars/day.txt").decode().split())
    syms = sorted({n.split("/")[1] for n in z.namelist() if n.startswith("features/") and n.count("/") >= 2})
    frames = []
    for s in syms:
        cols = {}
        for f in QLIB_FIELDS:
            try:
                a = np.frombuffer(z.read(f"features/{s}/{f}.day.bin"), dtype="<f4")
            except KeyError:
                break
            cols[f] = (int(a[0]), a[1:])
        if len(cols) < len(QLIB_FIELDS):
            continue
        start = max(v[0] for v in cols.values())
        end = min(min(v[0] + len(v[1]) for v in cols.values()), len(cal))
        if end <= start:
            continue
        df = pd.DataFrame({f: v[1][start - v[0]:end - v[0]] for f, v in cols.items()})
        df.insert(0, "date", cal[start:end]); df.insert(0, "ticker", s.upper())
        frames.append(df.dropna(subset=["close"]))
    p = pd.concat(frames, ignore_index=True)
    p["ticker"] = p.ticker.astype("category")
    p.to_parquet(d / "panel.parquet", index=False)
    print("qlib panel", p.shape, p.date.min().date(), p.date.max().date(), p.ticker.nunique(), "symbols")


def etf():
    d = OUT / "ref"; d.mkdir(parents=True, exist_ok=True)
    for name, url in ETF_URLS.items():
        b = get(url, 60)
        (d / name).write_bytes(b)
        print(name, len(b), "B sha256", hashlib.sha256(b).hexdigest()[:16])


# ---------------------------------------------------------------- Binance klines
def klines(months=None):
    d = OUT / "binance"; d.mkdir(parents=True, exist_ok=True)
    months = months or [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13)
                        if (y, m) <= (2026, 9)]
    pref, _ = s3_ls("data/spot/monthly/klines/")
    syms = sorted(p.rstrip("/").split("/")[-1] for p in pref)
    syms = [s for s in syms if s.endswith("USDT")]
    cols = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"]

    def one(job):
        s, m = job
        b = s3_get_zip_csv(f"data/spot/monthly/klines/{s}/1d/{s}-1d-{m}.zip", verify=False)
        if b is None:
            return None
        df = pd.read_csv(io.BytesIO(b), header=None)
        if not str(df.iloc[0, 0]).lstrip("-").isdigit():
            df = df.iloc[1:]
        df = df.iloc[:, :12]; df.columns = cols
        df.insert(0, "sym", s)
        return df

    with cf.ThreadPoolExecutor(48) as ex:
        res = [r for r in ex.map(one, [(s, m) for s in syms for m in months]) if r is not None]
    k = pd.concat(res, ignore_index=True)
    t = pd.to_numeric(k.open_time)
    k["day"] = pd.to_datetime(np.where(t > 1e14, t // 1000, t), unit="ms").normalize()   # us since 2025
    for c in ("open", "high", "low", "close", "volume", "quote_volume", "trades"):
        k[c] = pd.to_numeric(k[c])
    k = k[["sym", "day", "open", "high", "low", "close", "volume", "quote_volume", "trades"]]
    k.to_parquet(d / "klines_1d.parquet", index=False)
    print("klines", k.shape, k.sym.nunique(), "USDT pairs", k.day.min().date(), k.day.max().date())


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    what = sys.argv[1]
    for name, fn in (("qlib", qlib), ("etf", etf), ("klines", klines)):
        if what in (name, "all"):
            fn()
