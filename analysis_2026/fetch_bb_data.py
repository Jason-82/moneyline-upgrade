"""
Rebuild the gitignored data for the Bollinger-breakout replication (data/bbreplica/; notes in
analysis_2026/research_notes/Bollinger breakout replication/data_inventory.md).

    python3 -m analysis_2026.fetch_bb_data h1        # 1h klines, Binance spot + USD-M futures, 40 coins
    python3 -m analysis_2026.fetch_bb_data funding   # USD-M funding-rate history (run after h1)
    python3 -m analysis_2026.fetch_bb_data m1        # 1m USD-M klines, BTC ETH SOL BNB XRP DOGE, 2024-07..END
    python3 -m analysis_2026.fetch_bb_data validate  # gaps, hourly->daily match, basis, funding coverage
    python3 -m analysis_2026.fetch_bb_data all
  options: --end 2026-10-16  --symbols BTC,ETH  --force (re-download existing files)  --workers 32
           --market spot|um (h1 only: rebuild one market)

Writes (all gitignored):
  data/bbreplica/h1_spot/{SYM}USDT.parquet   spot 1h klines, listing .. END
  data/bbreplica/h1_um/{SYM}USDT.parquet     USD-M perpetual 1h klines, listing .. END
      columns: open_time (UTC, bar open), open, high, low, close, volume (base units), quote_volume (USDT),
               trades, taker_buy_quote
      SHIBUSDT is the 1000SHIBUSDT contract rescaled to one SHIB (prices / 1000, volume x 1000).
      LUNAUSDT is the old Terra perpetual (2021-01..2022-05); LUNA2USDT is the Terra 2.0 perpetual, which
      matches spot LUNAUSDT after its 2022-05-31 relisting (spot LUNAUSDT holds BOTH assets, split by a gap).
  data/bbreplica/d1_spot/, d1_um/{SYM}USDT.parquet   the archive's own 1d klines, same columns (by-product: they
      are the reference every intraday day is checked against, see below)
  data/bbreplica/funding/{SYM}USDT.parquet   calc_time (UTC), rate (per interval), interval_h. The archive has
      no mark price. Rows outside the contract's traded window (stale 0.01% placeholders that Binance keeps
      publishing after a delisting, e.g. MATICUSDT 2024-10..2026-09) are dropped and counted in stats.
  data/bbreplica/m1_um/{SYM}USDT.parquet     1m USD-M klines; prices float32 only where the round trip stays
      within 0.4 tick (checked and recorded), volumes float32 (relative error < 1e-7), trades int32
  Leading and trailing zero-trade bars are dropped from every kline file (the archive keeps printing flat
  placeholder bars after a delisting: FTTUSDT perpetual 2022-11-14..END). Internal zero-trade bars are kept:
  the futures archive marks exchange outages with them instead of leaving the hour out (validate lists them).
  data/bbreplica/stats/*.json, data/bbreplica/validation/*.csv   download counts and validation tables

Source: Binance's public data archive through its S3 bucket (data.binance.vision itself is blocked here),
using the S3 helpers in analysis_2026/fetch_scalping_data.py. Monthly zips up to the month before END, daily
zips for END's month (and for the month before it if its monthly zip is not published yet). Each zip is checked
against its .CHECKSUM (sha256); a zip the listing shows with a .CHECKSUM fails if that file cannot be read, and
stats count only zips whose sha256 was actually compared ("verified"; "extra_zips"/"extra_verified" for the daily
zips fetched by the repairs below).
Repairs (counted per series in stats/*.json): (0) bars off the interval grid are dropped (the Feb-2018 spot
restart bars at hh:28); (1) bars missing from a monthly zip are filled from that day's daily zip, for the 1d
reference too (the 1d monthly zips of 13 USD-M contracts lack the same 2022-02-26..28 / 2022-04-01..02 days as
their 1h zips); (2) every UTC day of 1h/1m bars is checked against the 1d kline (OHLC to 1e-9) and a mismatched day
is replaced by its daily zip when that zip matches the 1d kline; days that still disagree are listed.
Spot timestamps switched from milliseconds to microseconds on 2025-01-01; futures stay in milliseconds.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import io
import json
import sys
import urllib.parse
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026.fetch_regime_data import COINS
from analysis_2026.fetch_scalping_data import S3, get, s3_ls

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bbreplica"
DAILY_REF = ROOT / "data" / "crypto_binance_regime"
NAMED = "BTC ETH SOL BNB XRP DOGE ADA AVAX LINK LTC TRX DOT BCH".split()
SYMS = NAMED + [c for c in COINS if c not in NAMED]          # 40 coins (MATIC and POL separate)
UM_CONTRACT = {"SHIB": ("1000SHIBUSDT", 1000)}              # coin -> (futures contract, units per contract price)
UM_EXTRA = {"LUNA2": ("LUNA2USDT", 1)}                      # Terra 2.0 perpetual (spot LUNAUSDT after 2022-05-31)
SPOT_OF = {"LUNA2": "LUNA"}                                 # spot series an extra futures contract is compared with
M1_SYMS = "BTC ETH SOL BNB XRP DOGE".split()
M1_START = "2024-07"
END = "2026-10-16"
WORKERS = 32
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
         "taker_buy_base", "taker_buy_quote", "ignore"]
KEEP = ["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_quote"]
BASE = {"spot": "data/spot", "um": "data/futures/um"}


# ---------------------------------------------------------------- archive access
def _keys(market: str, kind: str, contract: str, interval: str | None, end: str, start_month: str | None = None):
    """Archive zips for one series: monthly files before END's month (from start_month), daily files up to END
    for the months after the last monthly file (END's month, plus the month before it while its monthly file is
    not published yet; a series whose monthly files stopped earlier is dead and gets none). Returns
    [(key, has_checksum)]."""
    sub = f"{kind}/{contract}/" + (f"{interval}/" if interval else "")
    _, mk = s3_ls(f"{BASE[market]}/monthly/{sub}")
    names = {k for k, _ in mk}
    em = end[:7]
    out = [(k, k + ".CHECKSUM" in names) for k in sorted(names) if k.endswith(".zip")
           and k[-11:-4] < em and (start_month is None or k[-11:-4] >= start_month)]
    if kind == "klines" and out:
        months, m = [], _next_month(max(k[-11:-4] for k, _ in out))
        while m <= em:
            months.append(m); m = _next_month(m)
        for mo in (months if len(months) <= 2 else []):
            _, dk = s3_ls(f"{BASE[market]}/daily/{sub}{contract}-{interval}-{mo}")
            dn = {k for k, _ in dk}
            out += [(k, k + ".CHECKSUM" in dn) for k in sorted(dn) if k.endswith(".zip") and k[-14:-4] <= end]
    return out


def _next_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y + 1}-01" if mo == 12 else f"{y}-{mo + 1:02d}"


def _get_zip_csv(key: str, need_sum: bool):
    """(CSV bytes, sha256 compared?) for one archive zip, (None, False) if the zip does not exist. Raises on a
    checksum mismatch, and when need_sum (the listing shows a .CHECKSUM) but that file cannot be read, so an
    unchecked zip is never counted as verified."""
    q = urllib.parse.quote(key)                               # some symbols are non-ASCII
    b = get(f"{S3}/{q}")
    if b is None:
        return None, False
    c = get(f"{S3}/{q}.CHECKSUM", 60)
    if c is None and need_sum:
        raise IOError(f"checksum file unreadable {key}")
    if c is not None and c.decode().split()[0] != hashlib.sha256(b).hexdigest():
        raise IOError(f"checksum mismatch {key}")
    z = zipfile.ZipFile(io.BytesIO(b))
    return z.read(z.namelist()[0]), c is not None


def _fetch(job):
    key, has_sum = job
    err = None
    for _ in range(3):
        try:
            return (key, has_sum, *_get_zip_csv(key, has_sum), None)
        except Exception as e:                                # checksum mismatch or network error: retry
            err = repr(e)
    return key, has_sum, None, False, err


def _download(jobs, workers):
    stats = {"zips": len(jobs), "with_checksum": sum(h for _, h in jobs), "failed": []}
    with cf.ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(_fetch, jobs))
    blobs = []
    for key, _, b, _, err in res:
        if b is None:
            stats["failed"].append(f"{key}: {err or 'missing'}")
        else:
            blobs.append((key, b))
    stats["verified"] = sum(ok for _, _, b, ok, _ in res if b is not None)
    return blobs, stats


def _fetch_extra(keys, workers, st):
    """Daily zips fetched by the repairs (they may or may not exist). Counted in st as extra_zips / extra_verified;
    download or checksum errors are listed in extra_failed instead of passing silently."""
    with cf.ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(_fetch, [(k, False) for k in keys]))
    got = [r for r in res if r[2] is not None]
    st["extra_zips"] = st.get("extra_zips", 0) + len(got)
    st["extra_verified"] = st.get("extra_verified", 0) + sum(r[3] for r in got)
    st.setdefault("extra_failed", []).extend(f"{r[0]}: {r[4]}" for r in res if r[4])
    return res


def _parse_klines(b: bytes) -> pd.DataFrame:
    head = 0 if b[:1].isdigit() else 1                       # futures files carry a header since 2022
    return pd.read_csv(io.BytesIO(b), header=None, skiprows=head, names=KCOLS, usecols=range(12))


def _to_utc_ms(t: pd.Series) -> pd.Series:
    t = t.astype("int64")
    return pd.Series(np.where(t > 10 ** 14, t // 1000, t), index=t.index)   # spot microseconds since 2025


STEP = {"1h": pd.Timedelta("1h"), "1m": pd.Timedelta("1min"), "1d": pd.Timedelta("1D")}


def _frame(blobs) -> pd.DataFrame:
    k = pd.concat([_parse_klines(b) for _, b in blobs], ignore_index=True)
    k["open_time"] = pd.to_datetime(_to_utc_ms(k.open_time), unit="ms", utc=True)
    return k[KEEP]


def _fill_holes(k, market, contract, interval, workers, st):
    """Some monthly zips lack whole days that the daily archive has (e.g. 13 USD-M contracts are missing
    2022-02-26..28 and 2022-04-01..02 in their monthly files). For every UTC day with missing bars, fetch that
    day's daily zip and add the bars that are absent. Exchange outages stay missing (no file has them)."""
    full = pd.date_range(k.open_time.min(), k.open_time.max(), freq=STEP[interval])
    miss = full.difference(pd.DatetimeIndex(k.open_time))
    days = sorted(set(miss.normalize()))
    st["hole_days_tried"] = len(days)
    if not days:
        return k
    keys = [f"{BASE[market]}/daily/klines/{contract}/{interval}/{contract}-{interval}-{d:%Y-%m-%d}.zip" for d in days]
    res = _fetch_extra(keys, workers, st)
    blobs = [(key, b) for key, _, b, _, _ in res if b is not None]
    st["hole_days_found"] = len(blobs)
    if not blobs:
        st["hole_bars_filled"] = 0
        return k
    add = _frame(blobs)
    add = add[add.open_time.isin(miss)]
    st["hole_bars_filled"] = len(add)
    st["hole_days_filled"] = sorted({str(t.date()) for t in add.open_time})[:50]
    return pd.concat([k, add], ignore_index=True)


def _daily_agg(k: pd.DataFrame) -> pd.DataFrame:
    return k.groupby(k.open_time.dt.floor("D")).agg(open=("open", "first"), high=("high", "max"),
                                                    low=("low", "min"), close=("close", "last"))


def _mismatch_days(k: pd.DataFrame, ref: pd.DataFrame):
    """UTC days whose intraday bars do not aggregate exactly (1e-9) to the 1d kline's OHLC."""
    j = _daily_agg(k).join(ref[["open", "high", "low", "close"]], rsuffix="_d", how="inner")
    bad = np.zeros(len(j), bool)
    for c in ("open", "high", "low", "close"):
        bad |= (j[c] / j[c + "_d"] - 1).abs().to_numpy() > 1e-9
    return len(j), list(j.index[bad])


def _repair(k, ref, market, contract, interval, workers, st):
    """A few monthly intraday zips carry a wrong bar that the daily zips, the 1m archive and the 1d kline all
    contradict (e.g. spot AXSUSDT 2021-12-05 23:00: 106.93 in the monthly 1h zip, 107.45 everywhere else).
    Cross-check every UTC day against the archive's own 1d kline; where they disagree, take that day's bars
    from its daily zip if the daily zip agrees with the 1d kline. Days that stay inconsistent are listed."""
    n, bad = _mismatch_days(k, ref)
    st["ref_days_checked"], st["ref_days_mismatched"] = n, len(bad)
    st["ref_days_repaired"], st["ref_days_unresolved"] = [], []
    if not bad:
        return k
    keys = [f"{BASE[market]}/daily/klines/{contract}/{interval}/{contract}-{interval}-{d:%Y-%m-%d}.zip" for d in bad]
    res = _fetch_extra(keys, workers, st)
    day = k.open_time.dt.floor("D")
    drop, add = np.zeros(len(k), bool), []
    for (key, _, b, _, _), d in zip(res, bad):
        if b is not None:
            x = _frame([(key, b)])
            x = x[x.open_time.dt.floor("D") == d]
            if len(x) and not _mismatch_days(x, ref)[1]:
                drop |= (day == d).to_numpy(); add.append(x)
                st["ref_days_repaired"].append(str(d.date())); continue
        st["ref_days_unresolved"].append(str(d.date()))
    if add:
        k = pd.concat([k[~drop]] + [_typed(x) for x in add], ignore_index=True).sort_values("open_time", kind="stable")
    return k.reset_index(drop=True)


def _typed(k: pd.DataFrame) -> pd.DataFrame:
    k = k.copy()
    for c in ("open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote"):
        k[c] = k[c].astype("float64")
    k["trades"] = k.trades.astype("int64")
    return k


def _scale(k: pd.DataFrame, mult) -> pd.DataFrame:
    if mult != 1:                                             # e.g. 1000SHIB contract -> one SHIB
        k = k.copy()
        k[["open", "high", "low", "close"]] /= mult
        k["volume"] *= mult
    return k


def klines(market: str, contract: str, interval: str, end: str, start_month=None, workers=WORKERS, mult=1,
           ref: pd.DataFrame | None = None):
    """One kline series from the archive: monthly + daily zips, holes filled from daily zips, cross-checked
    against `ref` (the same contract's 1d klines indexed by UTC day, unscaled) when given, leading/trailing
    placeholder bars dropped, prices rescaled by `mult`."""
    jobs = _keys(market, "klines", contract, interval, end, start_month)
    blobs, st = _download(jobs, workers)
    if not blobs:
        return None, st
    k = _frame(blobs)
    # After the 2018-02-08..09 outage the spot monthly zips print bars shifted by 28m14s (2018-02-09 09:28 ..
    # 2018-02-11 03:28 for BTC ETH BNB LTC NEO); the daily zips have the same hours on the grid. Drop off-grid
    # bars here so the hole filler below takes the aligned bars instead of mixing both.
    on = (k.open_time.dt.floor(STEP[interval]) == k.open_time).to_numpy()
    st["off_grid_dropped"] = int((~on).sum())
    k = k[on]
    k = _fill_holes(k, market, contract, interval, workers, st)   # 1d too: its monthly zips share the 1h holes
    k = k.sort_values("open_time", kind="stable")                  # stable, so keep="last" is deterministic
    st["duplicates_dropped"] = int(k.open_time.duplicated().sum())
    k = _typed(k.drop_duplicates("open_time", keep="last").reset_index(drop=True))
    if ref is not None:
        k = _repair(k, ref, market, contract, interval, workers, st)
    # The archive keeps emitting flat zero-trade bars for a dead contract (FTTUSDT perpetual: 1.59, zero trades,
    # 2022-11-14..END). Drop leading/trailing zero-trade bars; internal ones (outages, halts) are kept and
    # listed by validate().
    live = (k.trades > 0).to_numpy()
    if live.any():
        i0, i1 = int(live.argmax()), len(live) - int(live[::-1].argmax())
        st["placeholder_trimmed_head"], st["placeholder_trimmed_tail"] = i0, len(k) - i1
        k = k.iloc[i0:i1].reset_index(drop=True)
    k = _scale(k, mult)
    st.update(rows=len(k), first=str(k.open_time.iloc[0]), last=str(k.open_time.iloc[-1]),
              files_monthly=sum("/monthly/" in key for key, _ in blobs),
              files_daily=sum("/daily/" in key for key, _ in blobs))
    return k, st


def _save_stats(name: str, stats: dict):
    d = OUT / "stats"; d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(stats, indent=1, default=str))


def _um_list(syms):
    out = [(s, *UM_CONTRACT.get(s, (f"{s}USDT", 1))) for s in syms]
    out += [(s, c, m) for s, (c, m) in UM_EXTRA.items() if not syms or SPOT_OF.get(s) in syms]
    return out


# ---------------------------------------------------------------- 1. hourly (and daily) klines
def h1(syms=SYMS, end=END, force=False, workers=WORKERS, markets=("spot", "um")):
    stats = {}
    jobs = ([("spot", s, f"{s}USDT", 1) for s in syms] if "spot" in markets else []) + \
           ([("um", s, c, m) for s, c, m in _um_list(syms)] if "um" in markets else [])
    for market, s, contract, mult in jobs:
        d = OUT / f"h1_{market}"; d.mkdir(parents=True, exist_ok=True)
        dd = OUT / f"d1_{market}"; dd.mkdir(parents=True, exist_ok=True)
        f = d / f"{s}USDT.parquet"
        if f.exists() and not force:
            continue
        d1, st1 = klines(market, contract, "1d", end, workers=workers)          # reference, unscaled
        st1["contract"], st1["mult"] = contract, mult
        stats[f"d1/{market}/{s}"] = st1
        ref = None
        if d1 is not None:
            _scale(d1, mult).to_parquet(dd / f"{s}USDT.parquet", index=False)
            ref = d1.set_index("open_time")
        k, st = klines(market, contract, "1h", end, workers=workers, mult=mult, ref=ref)
        st["contract"], st["mult"] = contract, mult
        stats[f"{market}/{s}"] = st
        if k is None:
            print(f"h1 {market} {s}: no data ({contract})"); continue
        k.to_parquet(f, index=False)
        print(f"h1 {market:4s} {s:6s} {len(k):7,d} bars {st['first'][:10]}..{st['last'][:16]}  zips {st['zips']}"
              f" verified {st['verified']} failed {len(st['failed'])} holes+{st.get('hole_bars_filled', 0)}"
              f" repaired {st['ref_days_repaired']} unresolved {st['ref_days_unresolved']}"
              f" trimmed {st.get('placeholder_trimmed_head', 0)}/{st.get('placeholder_trimmed_tail', 0)}", flush=True)
    if stats:
        old = _load_stats("h1"); old.update(stats); _save_stats("h1", old)


def _load_stats(name):
    p = OUT / "stats" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ---------------------------------------------------------------- 2. funding
def funding(syms=SYMS, end=END, force=False, workers=WORKERS):
    d = OUT / "funding"; d.mkdir(parents=True, exist_ok=True)
    stats = {}
    for s, contract, _ in _um_list(syms):
        f = d / f"{s}USDT.parquet"
        if f.exists() and not force:
            continue
        blobs, st = _download(_keys("um", "fundingRate", contract, None, end), workers)
        st["contract"] = contract
        if not blobs:
            print("funding: no data", s); stats[s] = st; continue
        parts = []
        for _, b in blobs:
            x = pd.read_csv(io.BytesIO(b))
            if not str(x.columns[0]).startswith("calc"):         # header-less file
                x = pd.read_csv(io.BytesIO(b), header=None)
                x.columns = ["calc_time", "funding_interval_hours", "last_funding_rate"][:x.shape[1]]
            parts.append(x)
        x = pd.concat(parts, ignore_index=True)
        out = pd.DataFrame({"calc_time": pd.to_datetime(x.calc_time.astype("int64"), unit="ms", utc=True),
                            "rate": x.last_funding_rate.astype("float64"),
                            "interval_h": (x.funding_interval_hours if "funding_interval_hours" in x
                                           else pd.Series(np.nan, index=x.index)).astype("float64")})
        out = out.sort_values("calc_time").drop_duplicates("calc_time", keep="last").reset_index(drop=True)
        st["rows_raw"] = len(out)
        hk = OUT / "h1_um" / f"{s}USDT.parquet"
        if hk.exists():                                       # drop placeholder rows outside the traded window
            t = pd.read_parquet(hk, columns=["open_time"]).open_time
            lo, hi = t.iloc[0] - pd.Timedelta("1D"), t.iloc[-1] + pd.Timedelta("9h")
            keep = (out.calc_time >= lo) & (out.calc_time <= hi)
            st["stale_dropped_before"] = int((out.calc_time < lo).sum())
            st["stale_dropped_after"] = int((out.calc_time > hi).sum())
            if (~keep).any():
                st["stale_range"] = f"{out.calc_time[~keep].min()} .. {out.calc_time[~keep].max()}"
            out = out[keep].reset_index(drop=True)
        else:
            st["note"] = "no h1_um file; stale rows not trimmed"
        st.update(rows=len(out), first=str(out.calc_time.iloc[0]), last=str(out.calc_time.iloc[-1]))
        out.to_parquet(f, index=False)
        stats[s] = st
        print(f"funding {s:6s} {len(out):6,d} events {st['first'][:10]}..{st['last'][:16]} "
              f"(raw {st['rows_raw']}, verified {st['verified']}/{st['zips']})", flush=True)
    if stats:
        old = _load_stats("funding"); old.update(stats); _save_stats("funding", old)


# ---------------------------------------------------------------- 3. one-minute futures
def _f32_safe(x: pd.Series) -> tuple[bool, float, float]:
    """Price column float32 check: tick = smallest positive gap between distinct prices; safe if every
    float32 round trip is within 0.4 tick, so rounding back to the tick grid recovers the exact price
    (the relative error is then < 1e-7 anyway)."""
    u = np.unique(x.to_numpy())
    tick = float(np.min(np.diff(u))) if len(u) > 1 else 1.0
    err = float(np.max(np.abs(x.to_numpy().astype("float32").astype("float64") - x.to_numpy())))
    return err < 0.4 * tick, tick, err


def m1(syms=M1_SYMS, end=END, force=False, workers=WORKERS):
    d = OUT / "m1_um"; d.mkdir(parents=True, exist_ok=True)
    stats = {}
    for s in syms:
        f = d / f"{s}USDT.parquet"
        if f.exists() and not force:
            continue
        contract, mult = UM_CONTRACT.get(s, (f"{s}USDT", 1))
        d1, _ = klines("um", contract, "1d", end, start_month=M1_START, workers=workers)
        k, st = klines("um", contract, "1m", end, start_month=M1_START, workers=min(workers, 16), mult=mult,
                       ref=None if d1 is None else d1.set_index("open_time"))
        if k is None:
            print("m1: no data", s); continue
        st["float32"] = {}
        for c in ("open", "high", "low", "close"):
            ok, tick, err = _f32_safe(k[c])
            st["float32"][c] = {"safe": ok, "tick_est": tick, "max_abs_err": err}
            if ok:
                k[c] = k[c].astype("float32")
        for c in ("volume", "quote_volume", "taker_buy_quote"):
            v = k[c].to_numpy()
            rel = float(np.nanmax(np.abs(v.astype("float32") - v) / np.where(v == 0, 1, v)))
            st["float32"][c] = {"max_rel_err": rel}
            k[c] = k[c].astype("float32")
        k["trades"] = k.trades.astype("int32")
        k.to_parquet(f, index=False)
        stats[s] = st
        print(f"m1 {s:5s} {len(k):9,d} bars {st['first'][:16]}..{st['last'][:16]} verified {st['verified']}/"
              f"{st['zips']} holes+{st.get('hole_bars_filled', 0)} repaired {st['ref_days_repaired']} unresolved "
              f"{st['ref_days_unresolved']} f32 prices {[c for c in ('open', 'high', 'low', 'close') if st['float32'][c]['safe']]}",
              flush=True)
    if stats:
        old = _load_stats("m1"); old.update(stats); _save_stats("m1", old)


# ---------------------------------------------------------------- 4. validation (descriptive only)
def _dead_runs(k: pd.DataFrame, step: pd.Timedelta) -> pd.DataFrame:
    """Runs of 'dead' bars between the first and last bar: bars missing from the archive, or present with zero
    trades (the futures archive marks outages that way). Columns: start, end, bars, missing, zero_trade."""
    full = pd.date_range(k.open_time.iloc[0], k.open_time.iloc[-1], freq=step)
    x = k.set_index("open_time").trades.reindex(full)
    miss, zero = x.isna().to_numpy(), (x == 0).to_numpy()
    dead = miss | zero
    if not dead.any():
        return pd.DataFrame(columns=["start", "end", "bars", "missing", "zero_trade"])
    grp = np.cumsum(np.r_[True, dead[1:] != dead[:-1]])
    df = pd.DataFrame({"t": full, "g": grp, "dead": dead, "miss": miss, "zero": zero})[dead]
    r = df.groupby("g").agg(start=("t", "first"), end=("t", "last"), bars=("t", "size"),
                            missing=("miss", "sum"), zero_trade=("zero", "sum")).reset_index(drop=True)
    return r


def _load_h1(market):
    d = OUT / f"h1_{market}"
    return {p.stem[:-4]: pd.read_parquet(p) for p in sorted(d.glob("*.parquet"))}


def _episodes(ts: pd.DatetimeIndex, step: pd.Timedelta):
    ep, start, prev = [], None, None
    for t in ts:
        if prev is not None and t - prev == step:
            prev = t; continue
        if start is not None:
            ep.append((start, prev))
        start = prev = t
    if start is not None:
        ep.append((start, prev))
    return ep


def validate(end=END):
    v = OUT / "validation"; v.mkdir(parents=True, exist_ok=True)
    H = pd.Timedelta("1h")
    data = {m: _load_h1(m) for m in ("spot", "um")}
    lines = []
    say = lambda s="": (print(s), lines.append(s))

    # listing, segments, dead bars (missing or zero-trade)
    rows, gaps = [], []
    for market, dd in data.items():
        for s, k in dd.items():
            g = _dead_runs(k, H)
            g.insert(0, "sym", s); g.insert(0, "market", market); gaps.append(g)
            big = g[g.missing >= 72]
            halt = g[(g.zero_trade >= 24)]
            off = int((k.open_time.dt.minute != 0).sum() + (k.open_time.dt.second != 0).sum())
            rows.append({"market": market, "sym": s, "first": k.open_time.iloc[0], "last": k.open_time.iloc[-1],
                         "bars": len(k), "missing_hours": int(g.missing.sum()), "zero_trade_bars": int(g.zero_trade.sum()),
                         "dead_runs": len(g), "segments": 1 + len(big),
                         "segment_breaks": "; ".join(f"{r.start:%Y-%m-%d %H}h..{r.end:%Y-%m-%d %H}h ({r.bars}h)"
                                                     for r in big.itertuples()),
                         "zero_trade_halts_24h": "; ".join(f"{r.start:%Y-%m-%d %H}h..{r.end:%Y-%m-%d %H}h ({r.bars}h)"
                                                           for r in halt.itertuples()),
                         "off_grid_bars": off,
                         "nonpos_price_bars": int((k[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
                         "hl_violations": int(((k.high < k[["open", "close"]].max(axis=1)) |
                                               (k.low > k[["open", "close"]].min(axis=1))).sum())})
    lst = pd.DataFrame(rows); lst.to_csv(v / "listing.csv", index=False)
    G = pd.concat(gaps, ignore_index=True)

    # exchange-wide dead hours: dead in >= 50% of the symbols listed in that market at that time
    wide = []
    for market, dd in data.items():
        cnt = {}
        for r in G[G.market == market].itertuples():
            for t in pd.date_range(r.start, r.end, freq=H):
                cnt[t] = cnt.get(t, 0) + 1
        first = np.array([k.open_time.iloc[0] for k in dd.values()]); last = np.array([k.open_time.iloc[-1] for k in dd.values()])
        ts = pd.DatetimeIndex(sorted(cnt))
        n_act = np.array([((first <= t) & (last >= t)).sum() for t in ts])
        frac = np.array([cnt[t] for t in ts]) / n_act
        for a, b in _episodes(ts[frac >= 0.5], H):
            m = (ts >= a) & (ts <= b)
            wide.append({"market": market, "start": a, "end": b, "hours": int((b - a) / H) + 1,
                         "symbols_dead_max": int(max(cnt[t] for t in ts[m])), "symbols_listed": int(n_act[m].max())})
    W = pd.DataFrame(wide); W.to_csv(v / "exchange_wide_gaps.csv", index=False)
    ov = np.zeros(len(G))                                   # hours of each run inside exchange-wide episodes
    for r in W.itertuples():
        lo = G.start.where(G.start > r.start, r.start); hi = G.end.where(G.end < r.end, r.end)
        ov += ((hi - lo) / H + 1).where((G.market == r.market) & (hi >= lo), 0).to_numpy(dtype=float)
    G["exchange_wide"] = ov >= 0.5 * G.bars.to_numpy()
    G.to_csv(v / "gaps_h1.csv", index=False)

    say(f"Hourly series: {len(data['spot'])} spot, {len(data['um'])} USD-M")
    say("Exchange-wide dead hours (missing or zero-trade in >= 50% of listed symbols):")
    for r in W.itertuples():
        say(f"  {r.market:4s} {r.start:%Y-%m-%d %H:%M} .. {r.end:%Y-%m-%d %H:%M} UTC  {r.hours:3d} h  "
            f"({r.symbols_dead_max}/{r.symbols_listed} symbols)")
    sg = G[~G.exchange_wide].sort_values("bars", ascending=False)
    say("Largest symbol-specific dead runs (missing + zero-trade bars):")
    for r in sg.head(25).itertuples():
        say(f"  {r.market:4s} {r.sym:6s} {r.start:%Y-%m-%d %H:%M} .. {r.end:%Y-%m-%d %H:%M}  {r.bars} h "
            f"(missing {r.missing}, zero-trade {r.zero_trade})")

    # hourly spot -> daily kline (data/crypto_binance_regime) match
    dm = []
    for s, k in data["spot"].items():
        p = DAILY_REF / f"{s}USDT.csv"
        if not p.exists():
            continue
        ref = pd.read_csv(p, index_col=0, parse_dates=True)
        x = k.set_index(k.open_time.dt.tz_convert(None)).sort_index()
        agg = x.groupby(x.index.normalize()).agg(open=("open", "first"), high=("high", "max"),
                                                 low=("low", "min"), close=("close", "last"),
                                                 qv=("quote_volume", "sum"), n=("close", "size"))
        j = agg.join(ref, rsuffix="_d", how="inner")
        rel = lambda a, b: (j[a] / j[b] - 1).abs()
        cmis = rel("close", "close_d") > 1e-9
        dm.append({"sym": s, "days": len(j), "days_ref_only": int(len(ref.index.difference(agg.index))),
                   "days_h1_only": int(len(agg.index[agg.index <= ref.index[-1]].difference(ref.index))),
                   "close_match_pct": 100 * (1 - cmis.mean()),
                   "open_match_pct": 100 * (1 - (rel("open", "open_d") > 1e-9).mean()),
                   "high_match_pct": 100 * (1 - (rel("high", "high_d") > 1e-9).mean()),
                   "low_match_pct": 100 * (1 - (rel("low", "low_d") > 1e-9).mean()),
                   "qv_max_rel_diff": float(rel("qv", "quote_volume").max()),
                   "close_max_rel_diff": float(rel("close", "close_d").max()),
                   "days_lt24_bars": int((j.n < 24).sum()),
                   "close_mismatch_days": ", ".join(str(t.date()) for t in j.index[cmis][:5])})
    DM = pd.DataFrame(dm); DM.to_csv(v / "daily_match.csv", index=False)
    say(f"Hourly spot vs data/crypto_binance_regime daily: {len(DM)} symbols, {DM.days.sum():,} days; close match "
        f"{DM.close_match_pct.min():.3f}-{DM.close_match_pct.max():.3f}%, open {DM.open_match_pct.min():.3f}%+, "
        f"high {DM.high_match_pct.min():.3f}%+, low {DM.low_match_pct.min():.3f}%+")
    for r in DM[DM.close_match_pct < 100].itertuples():
        say(f"  {r.sym}: close mismatch on {r.close_mismatch_days}")

    # hourly -> the archive's own 1d klines (data/bbreplica/d1_*), both markets, all OHLC fields
    dd1 = []
    for market, dd in data.items():
        for s, k in dd.items():
            p = OUT / f"d1_{market}" / f"{s}USDT.parquet"
            if not p.exists():
                continue
            ref = pd.read_parquet(p).set_index("open_time")
            n, bad = _mismatch_days(k, ref)
            hd, rd = pd.DatetimeIndex(k.open_time.dt.floor("D").unique()), ref.index
            h_only, d_only = hd.difference(rd), rd.difference(hd)   # days the OHLC check above cannot see
            dd1.append({"market": market, "sym": s, "days": n, "mismatch_days": len(bad),
                        "match_pct": 100 * (1 - len(bad) / max(n, 1)),
                        "mismatch_list": ", ".join(str(t.date()) for t in bad[:10]),
                        "h1_days_without_d1": len(h_only), "d1_days_without_h1": len(d_only),
                        "unpaired_days": ", ".join(str(t.date()) for t in h_only.union(d_only)[:10])})
    D1 = pd.DataFrame(dd1); D1.to_csv(v / "d1_match.csv", index=False)
    say(f"Hourly vs archive 1d klines (OHLC, 1e-9): {len(D1)} series, {D1.days.sum():,} days, "
        f"{D1.mismatch_days.sum()} mismatched days; unpaired days: {D1.h1_days_without_d1.sum()} hourly-only, "
        f"{D1.d1_days_without_h1.sum()} daily-only")
    for r in D1[(D1.mismatch_days > 0) | (D1.h1_days_without_d1 > 0) | (D1.d1_days_without_h1 > 0)].itertuples():
        say(f"  {r.market} {r.sym}: mismatched {r.mismatch_list or '-'}; unpaired {r.unpaired_days or '-'}")

    # futures vs spot basis (close to close, same hour)
    bs = []
    for s, u in data["um"].items():
        sp = data["spot"].get(SPOT_OF.get(s, s))
        if sp is None:
            continue
        j = u.set_index("open_time").close.to_frame("um").join(sp.set_index("open_time").close.rename("spot"),
                                                                 how="inner")
        if s == "LUNA2":
            j = j[j.index >= "2022-05-31"]
        if s == "LUNA":
            j = j[j.index < "2022-05-20"]
        if j.empty:
            continue
        b = 1e4 * (j.um / j.spot - 1)
        a = b.abs()
        bs.append({"sym": s, "hours": len(b), "first": j.index[0], "median_bp": b.median(), "mean_bp": b.mean(),
                   "p01_bp": b.quantile(.01), "p99_bp": b.quantile(.99), "share_abs_gt_100bp": (a > 100).mean(),
                   "max_abs_bp": a.max(), "max_abs_at": a.idxmax()})
    BS = pd.DataFrame(bs); BS.to_csv(v / "basis.csv", index=False)
    say(f"Futures/spot basis (bp, close vs close): median of medians {BS.median_bp.median():.1f}, range "
        f"{BS.median_bp.min():.1f}..{BS.median_bp.max():.1f}; share of hours |basis|>1%: max "
        f"{100 * BS.share_abs_gt_100bp.max():.2f}% ({BS.sym[BS.share_abs_gt_100bp.idxmax()]})")

    # funding coverage
    fr = []
    for p in sorted((OUT / "funding").glob("*.parquet")):
        s = p.stem[:-4]
        f = pd.read_parquet(p)
        t = f.calc_time.dt.floor("min")
        dt = t.diff().dt.total_seconds() / 3600
        iv = f.interval_h
        ch = f[iv.ne(iv.shift())]
        exp = iv.shift().fillna(iv.iloc[0])
        miss = (dt > exp * 1.5) & (dt < 24 * 7)
        yr = f.groupby(f.calc_time.dt.year).apply(lambda g: g.rate.sum() / ((g.calc_time.iloc[-1] - g.calc_time.iloc[0]).total_seconds() / 3.15576e7 or np.nan))
        fr.append({"sym": s, "first": f.calc_time.iloc[0], "last": f.calc_time.iloc[-1], "events": len(f),
                   "intervals_seen": "/".join(str(int(x)) for x in sorted(iv.dropna().unique())),
                   "interval_changes": "; ".join(f"{r.calc_time:%Y-%m-%d}->{int(r.interval_h)}h"
                                                 for r in ch.iloc[1:].itertuples())[:400],
                   "observed_spacing_h": "/".join(f"{x:g}" for x in sorted(dt.round(0).value_counts().head(4).index)),
                   "missing_events_est": int(((dt[miss] / exp[miss]).round() - 1).sum()),
                   "gaps_over_7d": int((dt >= 24 * 7).sum()),
                   "mean_ann_pct": 100 * f.rate.sum() / ((f.calc_time.iloc[-1] - f.calc_time.iloc[0]).total_seconds() / 3.15576e7),
                   **{f"ann_pct_{y}": 100 * r for y, r in yr.items() if y >= 2020}})
    FR = pd.DataFrame(fr); FR.to_csv(v / "funding.csv", index=False)
    say(f"Funding: {len(FR)} contracts; intervals seen {sorted(set('/'.join(FR.intervals_seen).split('/')))}")

    # one-minute series
    mm = []
    for p in sorted((OUT / "m1_um").glob("*.parquet")):
        k = pd.read_parquet(p, columns=["open_time", "close", "volume", "trades"])
        g = _dead_runs(k, pd.Timedelta("1min"))
        mm.append({"sym": p.stem[:-4], "first": k.open_time.iloc[0], "last": k.open_time.iloc[-1], "bars": len(k),
                   "missing_min": int(g.missing.sum()), "zero_trade_min": int(g.zero_trade.sum()), "dead_runs": len(g),
                   "largest_dead_runs": "; ".join(f"{r.start:%Y-%m-%d %H:%M} ({r.bars} min)" for r in
                                                  g.sort_values("bars", ascending=False).head(4).itertuples()),
                   "dtype_close": str(k.close.dtype)})
        h = data["um"].get(p.stem[:-4])
        if h is not None:                                  # 1m aggregated to 1h vs the hourly file
            m = pd.read_parquet(p, columns=["open_time", "open", "high", "low", "close"])
            a = m.groupby(m.open_time.dt.floor("h")).agg(open=("open", "first"), high=("high", "max"),
                                                         low=("low", "min"), close=("close", "last"))
            j = a.join(h.set_index("open_time")[["open", "high", "low", "close"]], rsuffix="_h", how="inner")
            tol = 1e-6 if m.close.dtype == np.float32 else 1e-9
            bad = np.zeros(len(j), bool)
            for c in ("open", "high", "low", "close"):
                bad |= (j[c].astype("float64") / j[c + "_h"] - 1).abs().to_numpy() > tol
            mm[-1].update(h1_hours=len(j), h1_mismatch_hours=int(bad.sum()),
                          h1_mismatch_first=", ".join(str(t) for t in j.index[bad][:5]))
    MM = pd.DataFrame(mm); MM.to_csv(v / "m1.csv", index=False)
    say(f"1m futures: {len(MM)} symbols; missing minutes {MM.missing_min.sum()}, zero-trade minutes "
        f"{MM.zero_trade_min.sum()}; 1m->1h mismatched hours {MM.get('h1_mismatch_hours', pd.Series([0])).sum()}")
    (v / "summary.txt").write_text("\n".join(lines) + "\n")
    return lst, W, G, DM, BS, FR, MM


# ---------------------------------------------------------------- CLI
def _arg(name, default):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    end = _arg("--end", END)
    force = "--force" in sys.argv
    workers = int(_arg("--workers", WORKERS))
    syms = _arg("--symbols", None)
    syms = [s.strip().upper().removesuffix("USDT") for s in syms.split(",")] if syms else None
    cmd = sys.argv[1]
    markets = tuple(_arg("--market", "spot,um").split(","))
    if cmd in ("h1", "all"):
        h1(syms or SYMS, end, force, workers, markets)
    if cmd in ("funding", "all"):
        funding(syms or SYMS, end, force, workers)
    if cmd in ("m1", "all"):
        m1(syms or M1_SYMS, end, force, workers)
    if cmd in ("validate", "all"):
        validate(end)
