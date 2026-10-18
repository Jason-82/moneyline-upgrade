"""
Rebuild the gitignored data for the scalping / market-making study (analysis_2026/SCALPING_PREREG.md).

    python3 -m analysis_2026.fetch_scalping_data qlib       # qlib US daily set -> data/scalping/qlib/panel.parquet
    python3 -m analysis_2026.fetch_scalping_data etf        # Nasdaq symbol directory (ETF flags)
    python3 -m analysis_2026.fetch_scalping_data klines     # Binance spot daily klines, all USDT pairs, 2025-01..2026-09
    python3 -m analysis_2026.fetch_scalping_data all
    python3 -m analysis_2026.fetch_scalping_data rh-combine # parse agent-saved Robinhood bars -> data/scalping/rh/*.parquet
    python3 -m analysis_2026.fetch_scalping_data panel      # Part C 120-name panel -> data/scalping/rh/panel_c.csv
    python3 -m analysis_2026.fetch_scalping_data events     # Part E intraday events -> data/scalping/rh/events.csv

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


# ---------------------------------------------------------------- Robinhood pulls (raw files saved by agents)
RH = OUT / "rh"
PILOT40 = OUT / "rh_pilot" / "pilot_universe.csv"


def rh_combine():
    """Parse the agents' raw get_equity_historicals responses into parquet files."""
    from analysis_2026.rh_bars import parse_dir
    for raw, name, adj in (("daily_raw_split", "daily_split", "split"), ("daily_raw_none", "daily_none", "none"),
                           ("m5_raw", "m5_none", "none"), ("m1_raw", "m1_none", "none"),
                           ("s15_raw", "s15_none", "none"), ("events_m5_raw", "events_m5_none", "none")):
        if not (RH / raw).is_dir() or not any((RH / raw).iterdir()):
            continue
        d = parse_dir(str(RH / raw)); d["adjustment"] = adj
        d.to_parquet(RH / f"{name}.parquet", index=False)
        print(f"{name}: {len(d):,} bars, {d.symbol.nunique()} symbols, {d.begins_at.min()} .. {d.begins_at.max()}")


def _daily_frame():
    s = pd.read_parquet(RH / "daily_split.parquet"); n = pd.read_parquet(RH / "daily_none.parquet")
    for d in (s, n):
        d["date"] = d.begins_at.dt.tz_convert(None).dt.normalize()
    m = s.merge(n[["symbol", "date", "close"]].rename(columns={"close": "close_raw"}), on=["symbol", "date"], how="left")
    m["real"] = ~m.interpolated & (m.volume > 0)
    m["dv"] = np.where(m.real, m.close * m.volume, 0.0)
    return m.sort_values(["symbol", "date"]).reset_index(drop=True)


BANDS = [("L1", 5e4, 1.5e5), ("L2", 1.5e5, 5e5), ("L3", 5e5, 1.5e6), ("L4", 1.5e6, 5e6)]


def panel_c(asof="2026-10-16", per_band=30):
    """Part C panel: 30 names per band L1-L4 (bands as of 2026-10-16), default_rng(20261018), pilot 40 excluded."""
    m = _daily_frame()
    u = pd.read_csv(RH / "universe.csv", keep_default_na=False, dtype={"ticker": str})
    keep = set(u.loc[u.keep.astype(str) == "1", "ticker"])
    pilot = set(pd.read_csv(PILOT40, keep_default_na=False, dtype={"ticker": str}).ticker)
    last60 = m[m.date <= asof].groupby("symbol").tail(60)
    g = last60.groupby("symbol").agg(adv60=("dv", "median"), real=("real", "sum"), last_raw=("close_raw", "last"),
                                     last_date=("date", "max"))
    g = g[(g.real >= 40) & (g.last_raw >= 1) & (g.last_date == pd.Timestamp(asof))]
    g = g[g.index.isin(keep) & ~g.index.isin(pilot)]
    rng = np.random.default_rng(20261018)
    rows = []
    for b, lo, hi in BANDS:
        cand = sorted(g.index[(g.adv60 >= lo) & (g.adv60 < hi)])
        pick = rng.choice(cand, size=min(per_band, len(cand)), replace=False)
        rows += [dict(ticker=t, band_at_draw=b, draw_order=i, adv60=g.adv60[t], n_candidates=len(cand))
                 for i, t in enumerate(pick)]
    p = pd.DataFrame(rows)
    p["s15"] = p.draw_order < 10
    p.to_csv(RH / "panel_c.csv", index=False)
    print(p.groupby("band_at_draw").agg(n=("ticker", "size"), cand=("n_candidates", "first"),
                                        adv_med=("adv60", "median")))


def events_e(start="2026-03-02", end="2026-10-16", cap=1500):
    """Part E intraday events: volume >= 5 x trailing 60-day median (to t-1) and open/prev close - 1 >= +5%."""
    m = _daily_frame()
    # Robinhood daily bars carry every trading day; days with no real bar count as zero volume (prereg windows)
    m["vol0"] = np.where(m.real, m.volume, 0.0)
    gb = m.groupby("symbol")
    m["vol_med60"] = gb.vol0.transform(lambda v: v.shift(1).rolling(60, min_periods=60).median())
    m["real60"] = gb.real.transform(lambda v: v.astype(float).shift(1).rolling(60, min_periods=60).sum())
    m["prev_close"] = gb.close.shift(1)
    m = m[m.real60 >= 40]
    m["gap"] = m.open / m.prev_close - 1
    e = m[(m.date >= start) & (m.date <= end) & m.real & (m.volume >= 5 * m.vol_med60) & (m.gap >= 0.05)
          & (m.close_raw >= 1)]
    e = e[["symbol", "date", "gap", "volume", "vol_med60"]].sort_values(["date", "symbol"]).reset_index(drop=True)
    n_all = len(e)
    if n_all > cap:
        idx = np.sort(np.random.default_rng(20261018).choice(n_all, size=cap, replace=False))
        e = e.iloc[idx].reset_index(drop=True)
    e.to_csv(RH / "events.csv", index=False)
    print(f"events: {n_all} found, {len(e)} kept, {e.date.nunique()} dates")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    what = sys.argv[1]
    for name, fn in (("qlib", qlib), ("etf", etf), ("klines", klines), ("rh-combine", rh_combine),
                     ("panel", panel_c), ("events", events_e)):
        if what in (name, "all") and not (what == "all" and name in ("rh-combine", "panel", "events")):
            fn()
