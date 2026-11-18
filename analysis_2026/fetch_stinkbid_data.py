"""
Rebuild the gitignored data for the stink-bid study (data/stinkbid/; notes in
analysis_2026/research_notes/Stink bids/data_inventory.md). Descriptive only: coverage, counts and fill
frequencies (how often a level was touched). No forward return, no post-fill outcome, no strategy is computed.

    python3 -m analysis_2026.fetch_stinkbid_data listing   # archive listings: spot USDT pairs + exclusions
    python3 -m analysis_2026.fetch_stinkbid_data d1        # 1d spot klines, every USDT pair, 2019-10 (warm-up) .. END
    python3 -m analysis_2026.fetch_stinkbid_data sets      # candidate sets (a) user-style, (b) broad PIT top-100, (c) RH
    python3 -m analysis_2026.fetch_stinkbid_data h1        # 1h spot klines for every candidate, checked against d1
    python3 -m analysis_2026.fetch_stinkbid_data perp1d    # USD-M 1d klines for sets (a) and (c) (spot vs perp lows)
    python3 -m analysis_2026.fetch_stinkbid_data coverage  # per candidate: listing dates, 1m / aggTrades / metrics coverage
    python3 -m analysis_2026.fetch_stinkbid_data validate  # gaps, zero-trade outages, discontinuities, spike prints
    python3 -m analysis_2026.fetch_stinkbid_data desc      # counts-only wick tables, market-wide wick days, clustering
    python3 -m analysis_2026.fetch_stinkbid_data events    # aggTrades at 3 sample events: $ volume and minutes below levels
    python3 -m analysis_2026.fetch_stinkbid_data sizes     # size and time estimates: 1m klines, event-day aggTrades
    python3 -m analysis_2026.fetch_stinkbid_data all       # everything above, in order (~20 min of download time)
  options: --end 2026-11-17   --workers 32 (d1: 96 and h1: 160 were used)   --force (re-download existing files)
           --rh-pairs PATH    a saved Robinhood get_currency_pairs JSON (parsed with scalp_crypto.rh_bases) or a CSV
                              with a `sym` column; default: the scalping study's snapshot
                              analysis_2026/results_scalping/A/arh_pairs.csv (2026-10-18)

Writes (all under the gitignored data/stinkbid/):
  ref/spot_usdt_pairs.csv     every USDT spot pair in the archive: first/last monthly 1d file, exclusion reason
  ref/universe_monthly.csv    (b): month, sym, adv90 (median daily USDT volume over the traded days of the 90 days
                              to the prior month end; >= 30 traded days and traded on that last day), days traded,
                              rank among eligible pairs; top 100 = set (b)
  ref/candidates.csv          union of (a), (b), (c): membership flags, (a) tags, predecessor tickers (MKR -> SKY ...),
                              (c) coins dropped as reused tickers (LIT), `fetch` = series to download
  d1_spot/{SYM}.parquet       spot 1d klines (open_time UTC, open, high, low, close, volume, quote_volume, trades,
                              taker_buy_quote), from 2019-10 (3 months warm-up for the ranking) or listing .. END
  d1_spot_all.parquet         the same, all pairs stacked, plus `sym` and `day` (tz-naive UTC date)
  h1_spot/{SYM}.parquet       spot 1h klines from 2020-01 (or listing) .. END 23:00, same columns
  d1_um/{COIN}.parquet        USD-M perpetual 1d klines (1000x / 1M contracts rescaled to one coin)
  stats/{d1,h1,perp1d}.json   per series: zips, sha256-verified zips, failures, holes filled, days repaired
  coverage/coverage.csv       per candidate: listing dates, 1m / aggTrades / metrics coverage, archive sizes
  coverage/daily_sizes.parquet  size of every daily 1m-kline and aggTrades zip of every candidate
  validation/*.csv, summary.txt  gaps, outages, discontinuities, spike prints, spot-vs-perp lows
  desc/*.csv                  counts-only tables (shares of days / 7-day / 30-day windows touching -d%), how 30-day
                              touches happened (days to first touch, touch-day drop), wick depth quantiles,
                              market-wide wick days, clustering
  events/{DATE}_{SYM}_{spot|um}.parquet  the event day's aggTrades (time UTC, price, qty, is_buyer_maker)
  events/levels.csv           per event x coin x level: $ volume, trades and minutes at or below the level
  sizes/estimates.csv         download size and time estimates

Kline building reuses analysis_2026/fetch_bb_data.py (monthly + daily zips, sha256 against each .CHECKSUM, holes
filled from daily zips, every hourly day cross-checked against the 1d kline and repaired from the daily zip, leading
and trailing zero-trade placeholder bars trimmed) and the S3 helpers of analysis_2026/fetch_scalping_data.py.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026 import fetch_bb_data as bb
from analysis_2026.fetch_scalping_data import S3, get, s3_ls
from analysis_2026.scalp_crypto import EQUITY_FIRST, PEGGED_RWA, STABLE_FIAT, WRAPPED, rh_bases

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "stinkbid"
END = "2026-11-17"                     # most recent complete UTC day in the archive on 2026-11-18
START = "2020-01-01"                   # first day of every descriptive table
WARMUP = "2019-10"                     # 1d klines start here so the first month's 90-day ranking window is full
H1_START = "2020-01"
WORKERS = 32
TOP_N = 100                            # set (b): monthly top 100 by 90-day median USDT volume
RH_DEFAULT = ROOT / "analysis_2026" / "results_scalping" / "A" / "arh_pairs.csv"
DEPTHS = (5, 10, 15, 20, 25, 30, 40, 50, 60)          # % below the reference
WINDOWS = (1, 7, 30)                                  # days the bid rests (1 = the next day vs the prior close)
DISCONT = 0.25                         # |open / prior close - 1| above this on consecutive days = series break
MW_DEPTH, MW_FRAC = 15, 0.10           # market-wide day: >= 10% of the other active (b) coins had a >= 15% wick

# (a) the user's examples and "solid / real-revenue" coins Robinhood lists. The tags are a first pass from public
# knowledge, NOT verified here (DefiLlama is blocked in this session); the design agent owns the final filter.
USER_STYLE = {
    "HYPE": "user example; perp-DEX fees, buybacks", "NEAR": "user example; L1",
    "BTC": "reference asset (no protocol revenue)", "ETH": "L1 fees, burn", "SOL": "L1 fees", "BNB": "exchange L1, burns",
    "AAVE": "lending fees, buybacks", "UNI": "DEX fees (fee switch)", "SKY": "stablecoin protocol (ex-MKR), buybacks",
    "LDO": "staking fees", "JTO": "MEV/tip fees", "RAY": "AMM fees, buybacks", "AERO": "DEX fees to lockers",
    "CRV": "DEX fees to lockers", "COMP": "lending fees", "ENA": "synthetic-dollar yield", "LINK": "oracle fees",
    "PYTH": "oracle fees", "MORPHO": "lending fees", "SYRUP": "lending fees, buybacks", "ASTER": "perp-DEX fees, buybacks",
    "ORCA": "AMM fees", "INJ": "exchange fees, burn auctions", "ONDO": "tokenized-treasury fees",
}
PREDECESSOR = {"MKR": "SKY", "RNDR": "RENDER", "MATIC": "POL", "FTM": "S", "EOS": "A"}   # old ticker -> rebranded
BRIEF_RH = ("HYPE NEAR SOL ETH BTC AAVE UNI LINK ENA AERO RAY SKY JTO LDO CRV COMP PYTH ONDO SUI ZEC XRP DOGE AVAX ARB "
            "OP INJ SEI RENDER FET WLD VIRTUAL BNB").split()      # named as Robinhood-listed in the brief (2026-11-18)
EVENTS = ("2021-05-19", "2024-08-05", "2025-10-10")
EVENT_COINS = ("NEAR", "SOL", "AAVE", "LINK")
EVENT_EXTRA = (("2025-10-10", "HYPE", "um"),)          # HYPE had no Binance spot pair before 2026-09-24
LEVELS = (10, 20, 30, 40)


def _say(lines):
    def say(s=""):
        print(s, flush=True); lines.append(str(s))
    return say


def _save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str))


def _load_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else {}


def _ls_all(prefix: str):
    """Every key under a prefix (no delimiter), with sizes."""
    return s3_ls(prefix, delimiter="")[1]


# ================================================================ 1. listing and exclusions
def _leveraged(bases: set[str]) -> set[str]:
    """Binance leveraged tokens: XXXUP/XXXDOWN pairs (both must exist) and BULL/BEAR tokens."""
    out = {b for b in bases if b.endswith("UP") and b[:-2] + "DOWN" in bases}
    out |= {b[:-2] + "DOWN" for b in out}
    out |= {b for b in bases if b.endswith(("BULL", "BEAR"))}
    return out


def listing(workers=WORKERS):
    d = OUT / "ref"; d.mkdir(parents=True, exist_ok=True)
    pref, _ = s3_ls("data/spot/monthly/klines/")
    usdt = sorted(p.rstrip("/").split("/")[-1] for p in pref if p.rstrip("/").endswith("USDT"))

    def one(s):
        _, k = s3_ls(f"data/spot/monthly/klines/{s}/1d/")
        m = sorted(x[-11:-4] for x, _ in k if x.endswith(".zip"))
        return dict(sym=s, base=s[:-4], first_month=m[0] if m else None, last_month=m[-1] if m else None,
                    months=len(m))
    with cf.ThreadPoolExecutor(workers) as ex:
        p = pd.DataFrame(list(ex.map(one, usdt)))
    lev = _leveraged(set(p.base))
    reason = []
    for r in p.itertuples():
        b = r.base
        if b in STABLE_FIAT:
            reason.append("stablecoin/fiat")
        elif b in PEGGED_RWA:
            reason.append("gold-backed token")
        elif b in WRAPPED:
            reason.append("wrapped/staked token")
        elif b in lev:
            reason.append("leveraged token")
        elif b.endswith("B") and r.first_month and r.first_month >= f"{EQUITY_FIRST:%Y-%m}":
            reason.append("tokenized equity (ticker+B, listed 2026-06 or later)")
        else:
            reason.append("")
    p["excluded"] = reason
    p.to_csv(d / "spot_usdt_pairs.csv", index=False)
    live = p[p.last_month >= WARMUP]
    print(f"spot USDT pairs in the archive: {len(p)}; with data from {WARMUP} on: {len(live)} "
          f"(excluded: {(live.excluded != '').sum()}: "
          f"{live[live.excluded != ''].excluded.value_counts().to_dict()})")
    return p


# ================================================================ 2. daily klines, every USDT pair
def _pairs():
    return pd.read_csv(OUT / "ref" / "spot_usdt_pairs.csv", keep_default_na=False)


def _series(market, sym, interval, end, start_month, path, force, inner, ref=None, mult=1, contract=None):
    if path.exists() and not force:
        return sym, None
    k, st = bb.klines(market, contract or sym, interval, end, start_month=start_month, workers=inner, mult=mult,
                      ref=ref)
    if k is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        k.to_parquet(path, index=False)
    return sym, st


def d1(end=END, force=False, workers=WORKERS, syms=None):
    p = _pairs()
    syms = syms or list(p.sym[p.last_month >= WARMUP])
    dd = OUT / "d1_spot"
    outer = max(1, workers // 8)
    t0 = time.time()
    with cf.ThreadPoolExecutor(outer) as ex:
        res = list(ex.map(lambda s: _series("spot", s, "1d", end, WARMUP, dd / f"{s}.parquet", force, 8), syms))
    stats = _load_json(OUT / "stats" / "d1.json")
    stats.update({s: st for s, st in res if st is not None})
    _save_json(OUT / "stats" / "d1.json", stats)
    parts = []
    for f in sorted(dd.glob("*.parquet")):
        k = pd.read_parquet(f); k.insert(0, "sym", f.stem); parts.append(k)
    a = pd.concat(parts, ignore_index=True)
    a["day"] = a.open_time.dt.tz_convert(None).dt.normalize()
    a.to_parquet(OUT / "d1_spot_all.parquet", index=False)
    new = [st for _, st in res if st is not None]
    print(f"d1: {len(syms)} pairs requested, {len(new)} downloaded in {time.time() - t0:.0f}s; "
          f"zips {sum(s['zips'] for s in new)}, verified {sum(s['verified'] for s in new)}, failed "
          f"{sum(len(s['failed']) for s in new)}; panel {len(a):,} rows, {a.sym.nunique()} pairs, "
          f"{a.day.min().date()}..{a.day.max().date()}")


def load_d1(excluded=False) -> pd.DataFrame:
    a = pd.read_parquet(OUT / "d1_spot_all.parquet")
    if not excluded:
        p = _pairs()
        bad = set(p.sym[p.excluded != ""])
        a = a[~a.sym.isin(bad)]
    return a.sort_values(["sym", "day"]).reset_index(drop=True)


# ================================================================ 3. candidate sets
def _rh_syms(path: Path | None) -> tuple[list[str], str]:
    path = Path(path) if path else RH_DEFAULT
    if path.suffix == ".csv":
        r = pd.read_csv(path, keep_default_na=False)
        bases = [s[:-4] if s.endswith("USDT") else s for s in r.sym]
        if "excluded" in r:
            bases = [b for b, e in zip(bases, r.excluded.astype(str)) if e not in ("True", "1")]
    else:
        bases = rh_bases(path)
    return sorted(set(bases) | set(BRIEF_RH)), str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)


def universe_monthly(a: pd.DataFrame, end=END) -> pd.DataFrame:
    """Point-in-time set (b): for each month M, eligible pairs traded on the last day before M and on >= 30 of the
    90 days before M; ranked by the median daily USDT volume over the traded days of those 90 days."""
    months = pd.period_range(START[:7], end[:7], freq="M")
    qv = a.pivot_table(index="day", columns="sym", values="quote_volume", aggfunc="last")
    tr = a.pivot_table(index="day", columns="sym", values="trades", aggfunc="last")
    full = pd.date_range(qv.index.min(), pd.Timestamp(end), freq="D")
    qv, tr = qv.reindex(full), tr.reindex(full)
    traded = tr.fillna(0) > 0
    qv = qv.where(traded)                                   # median over traded days only
    rows = []
    for m in months:
        t1 = m.start_time - pd.Timedelta("1D")
        w = qv.loc[t1 - pd.Timedelta("89D"):t1]
        n = traded.loc[t1 - pd.Timedelta("89D"):t1].sum()
        ok = (n >= 30) & traded.loc[t1]
        med = w.median()[ok].sort_values(ascending=False)
        for rank, (s, v) in enumerate(med.items(), 1):
            rows.append((str(m), s, v, int(n[s]), rank))
    u = pd.DataFrame(rows, columns=["month", "sym", "adv90", "days_traded90", "rank"])
    return u


def sets(end=END, rh_pairs=None):
    a = load_d1()
    u = universe_monthly(a, end)
    u.to_csv(OUT / "ref" / "universe_monthly.csv", index=False)
    b = u[u["rank"] <= TOP_N]
    gb = b.groupby("sym").agg(months_in_b=("month", "size"), first_b=("month", "min"), last_b=("month", "max"),
                              best_rank=("rank", "min"))
    rh, rh_src = _rh_syms(rh_pairs)
    p = _pairs().set_index("base")
    coins = sorted(set(gb.index.str[:-4]) | set(USER_STYLE) | set(rh) | set(PREDECESSOR))
    rows = []
    for c in coins:
        s = c + "USDT"
        rows.append(dict(coin=c, sym=s, on_binance_spot=c in p.index, spot_excluded=p.excluded.get(c, "not listed"),
                         in_a=c in USER_STYLE, a_tag=USER_STYLE.get(c, ""), in_b=s in gb.index,
                         months_in_b=int(gb.months_in_b.get(s, 0)), first_b=gb.first_b.get(s, ""),
                         last_b=gb.last_b.get(s, ""), best_rank=gb.best_rank.get(s, np.nan),
                         in_c=c in rh, c_source=rh_src if c in rh else "",
                         predecessor_of=PREDECESSOR.get(c, "") if PREDECESSOR.get(c) in set(USER_STYLE) | set(rh) else ""))
    cand = pd.DataFrame(rows)
    # a Robinhood base whose Binance spot series ended long before END is probably a different asset with a reused
    # ticker (LIT: Binance's LITUSDT was Litentry, delisted 2025-02; Robinhood's LIT is presumably Lighter [U])
    last = a.groupby("sym").day.max()
    old = cand.in_c & cand.sym.map(last).lt(pd.Timestamp(end) - pd.Timedelta("30D"))
    cand["c_dropped"] = np.where(old, "Binance spot series ended " + cand.sym.map(last).dt.strftime("%Y-%m-%d").fillna("")
                                 + ": ticker probably reused", "")
    cand.loc[old, "in_c"] = False
    cand["fetch"] = cand.on_binance_spot & cand.spot_excluded.eq("") & (cand.in_a | cand.in_b | cand.in_c |
                                                                         cand.predecessor_of.ne(""))
    cand.to_csv(OUT / "ref" / "candidates.csv", index=False)
    print(f"sets: (a) {cand.in_a.sum()} coins, (b) {cand.in_b.sum()} coins ever in the monthly top {TOP_N} "
          f"({len(b.month.unique())} months), (c) {cand.in_c.sum()} RH coins ({rh_src} + brief), of which on Binance "
          f"spot {(cand.in_c & cand.on_binance_spot).sum()}; union to fetch: {cand.fetch.sum()}")
    miss = cand[(cand.in_a | cand.in_c) & ~cand.on_binance_spot]
    if len(miss):
        print("  (a)/(c) coins with no Binance USDT spot pair:", " ".join(miss.coin))
    for r in cand[cand.c_dropped != ""].itertuples():
        print(f"  dropped from (c): {r.coin}: {r.c_dropped}")
    return cand


def candidates() -> pd.DataFrame:
    return pd.read_csv(OUT / "ref" / "candidates.csv", keep_default_na=False)


# ================================================================ 4. hourly klines
def h1(end=END, force=False, workers=WORKERS, syms=None):
    c = candidates()
    syms = syms or list(c.sym[c.fetch.astype(str) == "True"])
    dd = OUT / "h1_spot"
    outer = max(1, workers // 8)
    t0 = time.time()

    def one(s):
        f = OUT / "d1_spot" / f"{s}.parquet"
        ref = pd.read_parquet(f).set_index("open_time") if f.exists() else None
        return _series("spot", s, "1h", end, H1_START, dd / f"{s}.parquet", force, 8, ref=ref)
    with cf.ThreadPoolExecutor(outer) as ex:
        res = list(ex.map(one, syms))
    stats = _load_json(OUT / "stats" / "h1.json")
    stats.update({s: st for s, st in res if st is not None})
    _save_json(OUT / "stats" / "h1.json", stats)
    new = [st for _, st in res if st is not None]
    print(f"h1: {len(syms)} series requested, {len(new)} downloaded in {time.time() - t0:.0f}s; zips "
          f"{sum(s['zips'] for s in new)}, verified {sum(s['verified'] for s in new)}, failed "
          f"{sum(len(s['failed']) for s in new)}, days repaired {sum(len(s.get('ref_days_repaired', [])) for s in new)}, "
          f"unresolved {sum(len(s.get('ref_days_unresolved', [])) for s in new)}")


# ================================================================ 5. USD-M perpetual daily klines (spot-vs-perp check)
def um_contracts() -> dict[str, tuple[str, float]]:
    """coin -> (USDT-margined perpetual, units of the coin per contract price). Exact {COIN}USDT first, then the
    1000x / 1000000x / 1M prefixed contract; delivery contracts (with '_') and index contracts are ignored."""
    f = OUT / "ref" / "um_contracts.csv"
    if not f.exists():
        pref, _ = s3_ls("data/futures/um/monthly/klines/")
        names = sorted(p.rstrip("/").split("/")[-1] for p in pref)
        pd.DataFrame({"contract": names}).to_csv(f, index=False)
    names = [n for n in pd.read_csv(f).contract if n.endswith("USDT") and "_" not in n]
    out = {}
    for n in names:
        base = n[:-4]
        for pre, mult in (("1000000", 1e6), ("1000", 1e3), ("1M", 1e6)):
            if base.startswith(pre) and len(base) > len(pre) and not base[len(pre)].isdigit():
                out.setdefault(base[len(pre):], (n, mult))
                break
        else:
            out[base] = (n, 1)                              # exact name wins over a prefixed one
    out["LUNA"] = ("LUNA2USDT", 1)                          # spot LUNAUSDT after 2022-05-31 is Terra 2.0
    out["LUNC"] = ("1000LUNCUSDT", 1e3)
    return out


def perp1d(end=END, force=False, workers=WORKERS, coins=None):
    c = candidates()
    coins = coins or list(c.coin[(c.in_a.astype(str) == "True") | (c.in_c.astype(str) == "True")])
    um = um_contracts()
    jobs = [(x, *um[x]) for x in coins if x in um]
    outer = max(1, workers // 8)
    with cf.ThreadPoolExecutor(outer) as ex:
        res = list(ex.map(lambda j: _series("um", j[0], "1d", end, H1_START, OUT / "d1_um" / f"{j[0]}.parquet",
                                            force, 8, mult=j[2], contract=j[1]), jobs))
    stats = _load_json(OUT / "stats" / "perp1d.json")
    for (x, con, mult), (_, st) in zip(jobs, res):
        if st is not None:
            st.update(contract=con, mult=mult); stats[x] = st
    _save_json(OUT / "stats" / "perp1d.json", stats)
    print(f"perp1d: {len(jobs)} contracts for {len(coins)} coins; no USD-M contract: "
          f"{' '.join(x for x in coins if x not in um)}")


# ================================================================ 6. archive coverage per candidate
def _months(keys):
    return sorted(k[-11:-4] for k, _ in keys if k.endswith(".zip"))


def _days(keys):
    return sorted(k[-14:-4] for k, _ in keys if k.endswith(".zip"))


def coverage(workers=WORKERS):
    c = candidates()
    c = c[c.on_binance_spot.astype(str) == "True"]
    um = um_contracts()
    p = _pairs().set_index("sym")
    d1p = {f.stem: f for f in (OUT / "d1_spot").glob("*.parquet")}

    def one(r):
        s, coin = r.sym, r.coin
        out = dict(coin=coin, sym=s, in_a=r.in_a, in_b=r.in_b, in_c=r.in_c,
                   spot_first_month_archive=p.first_month.get(s), spot_last_month_archive=p.last_month.get(s))
        if s in d1p:
            k = pd.read_parquet(d1p[s], columns=["open_time"])
            out.update(spot_first_day=str(k.open_time.iloc[0].date()), spot_last_day=str(k.open_time.iloc[-1].date()))
        daily = []
        for kind, pre_m, pre_d in (("1m", f"data/spot/monthly/klines/{s}/1m/", f"data/spot/daily/klines/{s}/1m/"),
                                   ("agg", f"data/spot/monthly/aggTrades/{s}/", f"data/spot/daily/aggTrades/{s}/")):
            km = [(k, z) for k, z in s3_ls(pre_m)[1] if k.endswith(".zip")]
            kd = [(k, z) for k, z in _ls_all(pre_d) if k.endswith(".zip")]
            mm, dd = _months(km), _days(kd)
            out.update({f"{kind}_monthly_first": mm[0] if mm else None, f"{kind}_monthly_last": mm[-1] if mm else None,
                        f"{kind}_monthly_files": len(mm), f"{kind}_daily_first": dd[0] if dd else None,
                        f"{kind}_daily_last": dd[-1] if dd else None, f"{kind}_daily_files": len(dd),
                        f"{kind}_bytes_monthly_from2020": sum(z for k, z in km if k[-11:-4] >= START[:7]),
                        f"{kind}_bytes_daily_from2020": sum(z for k, z in kd if k[-14:-4] >= START)})
            daily += [(s, kind, k[-14:-4], z) for k, z in kd]
        if coin in um:
            con, mult = um[coin]
            km = [(k, z) for k, z in s3_ls(f"data/futures/um/monthly/klines/{con}/1d/")[1] if k.endswith(".zip")]
            mm = _months(km)
            first_day = None
            if mm:
                b = bb._get_zip_csv(f"data/futures/um/monthly/klines/{con}/1d/{con}-1d-{mm[0]}.zip", True)[0]
                if b is not None:
                    t = bb._parse_klines(b).open_time
                    first_day = str(pd.to_datetime(bb._to_utc_ms(t), unit="ms").min().date())
            met = _days([(k, z) for k, z in _ls_all(f"data/futures/um/daily/metrics/{con}/") if k.endswith(".zip")])
            out.update(perp_contract=con, perp_mult=mult, perp_first_month=mm[0] if mm else None,
                       perp_last_month=mm[-1] if mm else None, perp_first_day=first_day,
                       metrics_first_day=met[0] if met else None, metrics_last_day=met[-1] if met else None,
                       metrics_days=len(met))
        return out, daily
    t0 = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, list(c.itertuples())))
    cov = pd.DataFrame([r for r, _ in res])
    d = OUT / "coverage"; d.mkdir(parents=True, exist_ok=True)
    cov.to_csv(d / "coverage.csv", index=False)
    ds = pd.DataFrame([x for _, dl in res for x in dl], columns=["sym", "kind", "day", "bytes"])
    ds.to_parquet(d / "daily_sizes.parquet", index=False)
    print(f"coverage: {len(cov)} candidates in {time.time() - t0:.0f}s; daily zips listed {len(ds):,}")
    return cov


# ================================================================ 7. validation (descriptive)
def prep_daily(a: pd.DataFrame) -> pd.DataFrame:
    """Adds seg (segment id), ref (the prior day's close where it is a valid reference) and dd (low / ref - 1).
    A new segment starts after a missing day or at a discontinuity (|open / prior close - 1| > DISCONT on
    consecutive days: relisting, redenomination, bad bar); no reference or window crosses a segment boundary."""
    a = a.sort_values(["sym", "day"]).reset_index(drop=True)
    gap = a.groupby("sym").day.diff().dt.days.ne(1)
    pc = a.groupby("sym").close.shift()
    jump = (a.open / pc - 1).abs().gt(DISCONT) & ~gap
    a["brk_gap"], a["brk_jump"] = gap, jump
    a["seg"] = (gap | jump).cumsum()
    a["ref"] = pc.where(~gap & ~jump & (a.trades > 0))
    a["dd"] = a.low / a.ref - 1
    return a


def validate(end=END):
    v = OUT / "validation"; v.mkdir(parents=True, exist_ok=True)
    lines = []; say = _say(lines)
    H = pd.Timedelta("1h")

    # download statistics
    for name in ("d1", "h1", "perp1d"):
        st = _load_json(OUT / "stats" / f"{name}.json")
        if not st:
            continue
        say(f"{name}: {len(st)} series, zips {sum(s['zips'] for s in st.values())}, with .CHECKSUM "
            f"{sum(s['with_checksum'] for s in st.values())}, sha256 verified {sum(s['verified'] for s in st.values())}, "
            f"failed {sum(len(s['failed']) for s in st.values())}; extra daily zips {sum(s.get('extra_zips', 0) for s in st.values())} "
            f"(verified {sum(s.get('extra_verified', 0) for s in st.values())}); hole bars filled "
            f"{sum(s.get('hole_bars_filled', 0) for s in st.values())}; off-grid dropped "
            f"{sum(s.get('off_grid_dropped', 0) for s in st.values())}; duplicates dropped "
            f"{sum(s.get('duplicates_dropped', 0) for s in st.values())}; placeholder bars trimmed head/tail "
            f"{sum(s.get('placeholder_trimmed_head', 0) for s in st.values())}/"
            f"{sum(s.get('placeholder_trimmed_tail', 0) for s in st.values())}")
        if name == "h1":
            rep = {s: x["ref_days_repaired"] for s, x in st.items() if x.get("ref_days_repaired")}
            unr = {s: x["ref_days_unresolved"] for s, x in st.items() if x.get("ref_days_unresolved")}
            say(f"  hourly days checked against the 1d kline: {sum(x.get('ref_days_checked', 0) for x in st.values()):,}; "
                f"mismatched {sum(x.get('ref_days_mismatched', 0) for x in st.values())}; repaired from daily zips "
                f"{sum(len(x) for x in rep.values())} {dict(list(rep.items())[:12])}; unresolved "
                f"{sum(len(x) for x in unr.values())} {dict(list(unr.items())[:12])}")
        fl = [f for s in st.values() for f in s["failed"]]
        if fl:
            say(f"  failed: {fl[:10]}")

    # daily: gaps, discontinuities, zero-trade days, OHLC sanity (all non-excluded USDT pairs)
    a = prep_daily(load_d1())
    pairs = a.groupby("sym").agg(first=("day", "min"), last=("day", "max"), days=("day", "size"),
                                 zero_trade_days=("trades", lambda x: int((x == 0).sum())),
                                 gaps=("brk_gap", lambda x: int(x.sum()) - 1), jumps=("brk_jump", "sum"))
    pairs["missing_days"] = ((pairs["last"] - pairs["first"]).dt.days + 1 - pairs.days).astype(int)
    pairs.to_csv(v / "d1_pairs.csv")
    say(f"daily spot panel (exclusions applied): {a.sym.nunique()} pairs, {len(a):,} pair-days "
        f"{a.day.min().date()}..{a.day.max().date()}; pairs with internal missing days {(pairs.missing_days > 0).sum()} "
        f"({pairs.missing_days.sum():,} days); zero-trade days kept inside series {pairs.zero_trade_days.sum()}")
    jumps = a.loc[a.brk_jump, ["sym", "day", "open", "low", "close", "trades"]].copy()
    jumps["prev_close"] = a.groupby("sym").close.shift()[a.brk_jump]
    jumps["open_vs_prev_close"] = jumps.open / jumps.prev_close - 1
    jumps.to_csv(v / "d1_discontinuities.csv", index=False)
    say(f"discontinuities (consecutive days, |open/prior close - 1| > {DISCONT:.0%}): {len(jumps)} in "
        f"{jumps.sym.nunique()} pairs; listed in d1_discontinuities.csv")
    for r in jumps.sort_values("day").head(30).itertuples():
        say(f"  {r.sym:12s} {r.day.date()} open {r.open:.6g} vs prior close {r.prev_close:.6g} "
            f"({r.open_vs_prev_close:+.1%}), trades {r.trades}")
    hl = ((a.high < a[["open", "close"]].max(axis=1)) | (a.low > a[["open", "close"]].min(axis=1)) |
          (a[["open", "high", "low", "close"]] <= 0).any(axis=1))
    say(f"daily OHLC violations or non-positive prices: {int(hl.sum())}")
    ext = a[a.dd <= -0.6][["sym", "day", "ref", "open", "low", "close", "quote_volume", "trades", "dd"]]
    ext.to_csv(v / "d1_lows_below_60pct.csv", index=False)
    say(f"pair-days with a low >= 60% below the prior close: {len(ext)} ({ext.day.nunique()} days); listed in "
        f"d1_lows_below_60pct.csv")

    # hourly: dead runs (missing or zero-trade hours), exchange-wide outages, spike prints
    files = sorted((OUT / "h1_spot").glob("*.parquet"))
    rows, runs, spikes = [], [], []
    first, last = {}, {}
    for f in files:
        k = pd.read_parquet(f)
        s = f.stem
        g = bb._dead_runs(k, H); g.insert(0, "sym", s); runs.append(g)
        first[s], last[s] = k.open_time.iloc[0], k.open_time.iloc[-1]
        lowbody = k[["open", "close"]].min(axis=1)
        sp = k[k.low <= 0.5 * lowbody].copy()
        if len(sp):
            sp.insert(0, "sym", s); sp["wick"] = sp.low / lowbody[sp.index] - 1; spikes.append(sp)
        rows.append(dict(sym=s, first=k.open_time.iloc[0], last=k.open_time.iloc[-1], bars=len(k),
                         missing_hours=int(g.missing.sum()), zero_trade_hours=int(g.zero_trade.sum()),
                         gaps_ge_72h=int((g.missing >= 72).sum()),
                         hl_violations=int(((k.high < k[["open", "close"]].max(axis=1)) |
                                            (k.low > lowbody)).sum())))
    if not files:
        say("no hourly files"); (v / "summary.txt").write_text("\n".join(lines) + "\n"); return
    L = pd.DataFrame(rows); L.to_csv(v / "h1_listing.csv", index=False)
    G = pd.concat(runs, ignore_index=True); G.to_csv(v / "h1_dead_runs.csv", index=False)
    say(f"hourly spot: {len(L)} series, {L.bars.sum():,} bars; missing hours {L.missing_hours.sum():,}, zero-trade hours "
        f"{L.zero_trade_hours.sum():,}; series with a >= 72 h gap {(L.gaps_ge_72h > 0).sum()}; OHLC violations "
        f"{L.hl_violations.sum()}")
    cnt = {}
    for r in G.itertuples():
        for t in pd.date_range(r.start, r.end, freq=H):
            cnt[t] = cnt.get(t, 0) + 1
    fa, la = np.array(list(first.values())), np.array(list(last.values()))
    ts = pd.DatetimeIndex(sorted(cnt))
    n_act = np.array([((fa <= t) & (la >= t)).sum() for t in ts])
    frac = np.array([cnt[t] for t in ts]) / np.maximum(n_act, 1)
    wide = []
    for a0, b0 in bb._episodes(ts[frac >= 0.5], H):
        m = (ts >= a0) & (ts <= b0)
        wide.append(dict(start=a0, end=b0, hours=int((b0 - a0) / H) + 1, series_dead_max=int(max(cnt[t] for t in ts[m])),
                         series_listed=int(n_act[m].max())))
    W = pd.DataFrame(wide); W.to_csv(v / "h1_exchange_wide_outages.csv", index=False)
    say("exchange-wide dead hours (missing or zero-trade in >= 50% of listed candidate series):")
    for r in W.itertuples():
        say(f"  {r.start:%Y-%m-%d %H:%M} .. {r.end:%Y-%m-%d %H:%M} UTC  {r.hours} h ({r.series_dead_max}/{r.series_listed})")
    big = G[G.missing >= 72].sort_values("bars", ascending=False)
    say(f"symbol-specific gaps >= 72 h: {len(big)}")
    for r in big.head(15).itertuples():
        say(f"  {r.sym:12s} {r.start:%Y-%m-%d %H}h .. {r.end:%Y-%m-%d %H}h ({r.bars} h)")
    S = pd.concat(spikes, ignore_index=True) if spikes else pd.DataFrame()
    if len(S):
        S = S.sort_values("open_time"); S.to_csv(v / "h1_spike_prints.csv", index=False)
        say(f"hourly bars with a lower wick >= 50% below min(open, close): {len(S)} in {S.sym.nunique()} series on "
            f"{S.open_time.dt.floor('D').nunique()} days")
        for r in S.head(40).itertuples():
            say(f"  {r.sym:12s} {r.open_time:%Y-%m-%d %H:%M} low {r.low:.6g} vs body {min(r.open, r.close):.6g} "
                f"({r.wick:+.0%}), trades {r.trades}, ${r.quote_volume:,.0f}")

    # spot vs USD-M perpetual daily lows (venue-specific wicks)
    um = sorted((OUT / "d1_um").glob("*.parquet"))
    if um:
        rows = []
        for f in um:
            coin = f.stem
            sf = OUT / "d1_spot" / f"{coin}USDT.parquet"
            if not sf.exists():
                continue
            s_ = pd.read_parquet(sf).set_index("open_time"); u_ = pd.read_parquet(f).set_index("open_time")
            j = s_[["close", "low", "trades"]].join(u_[["close", "low", "trades"]], rsuffix="_um", how="inner")
            if coin == "LUNA":
                j = j[j.index >= "2022-05-31"]
            j = j[(j.trades > 0) & (j.trades_um > 0)]
            if j.empty:
                continue
            basis = (j.close_um / j.close - 1)
            j["pc"] = j.close.shift(); j["pc_um"] = j.close_um.shift()
            j["dd"], j["dd_um"] = j.low / j.pc - 1, j.low_um / j.pc_um - 1
            diff = j.dd - j.dd_um
            rows.append(dict(coin=coin, days=len(j), median_abs_basis=basis.abs().median(),
                             spot_deeper_10pp=int((diff <= -0.10).sum()), perp_deeper_10pp=int((diff >= 0.10).sum()),
                             spot_deeper_5pp=int((diff <= -0.05).sum()), perp_deeper_5pp=int((diff >= 0.05).sum()),
                             worst_spot_deeper=diff.min(), worst_spot_day=diff.idxmin(),
                             worst_perp_deeper=diff.max(), worst_perp_day=diff.idxmax()))
        SP = pd.DataFrame(rows).sort_values("coin"); SP.to_csv(v / "spot_vs_perp_lows.csv", index=False)
        say(f"spot vs USD-M perp daily lows (each vs its own prior close): {len(SP)} coins; median |basis| > 2%: "
            f"{' '.join(SP.coin[SP.median_abs_basis > 0.02]) or 'none'}; coin-days spot >= 10 pp deeper "
            f"{SP.spot_deeper_10pp.sum()}, perp >= 10 pp deeper {SP.perp_deeper_10pp.sum()} "
            f"(>= 5 pp: {SP.spot_deeper_5pp.sum()} / {SP.perp_deeper_5pp.sum()})")
        for r in SP[(SP.spot_deeper_10pp + SP.perp_deeper_10pp) > 0].itertuples():
            say(f"  {r.coin:8s} spot deeper {r.spot_deeper_10pp} (worst {r.worst_spot_deeper:+.1%} {r.worst_spot_day:%Y-%m-%d}); "
                f"perp deeper {r.perp_deeper_10pp} (worst {r.worst_perp_deeper:+.1%} {r.worst_perp_day:%Y-%m-%d})")
    (v / "summary.txt").write_text("\n".join(lines) + "\n")


# ================================================================ 8. counts-only descriptive tables
def _windows(a: pd.DataFrame) -> pd.DataFrame:
    """For each pair-day t with a valid close: the lowest low over the next H days (H in WINDOWS), within the same
    segment and only when all H days exist (otherwise NaN: censored by a delisting, gap or series break)."""
    a = a.copy()
    for H in WINDOWS:
        if H == 1:
            a["wl1"] = a.groupby("seg").low.shift(-1).where(a.groupby("seg").trades.shift(-1) > 0)
            continue
        rev = a.iloc[::-1]
        m = rev.groupby("seg").low.transform(lambda x: x.rolling(H, min_periods=H).min())
        a[f"wl{H}"] = m.iloc[::-1].groupby(a.seg).shift(-1)
    return a


def _shares(df: pd.DataFrame, H: int) -> dict:
    x = (df[f"wl{H}"] / df.close - 1).dropna()
    out = {"n": len(x)}
    for d in DEPTHS:
        out[f"ge{d}"] = float((x <= -d / 100).mean()) if len(x) else np.nan
    return out


def _first_touch(a: pd.DataFrame, end: str, H: int = 30, depths=(0.2, 0.3)) -> pd.DataFrame:
    """For every start day whose H-day window touched close x (1 - d): days to the first touch, the touch day's own
    low against its prior close, and how far the prior close still was above the level (how the level was reached:
    a sharp day or a slow grind). Descriptive only; nothing after the touch is used."""
    rows = []
    for s, g in a.groupby("sym"):
        seg, low, close = g.seg.to_numpy(), g.low.to_numpy(), g.close.to_numpy()
        dd, day = g.dd.to_numpy(), g.day.to_numpy()
        ok = (day >= np.datetime64(START)) & (day <= np.datetime64(end))
        for i in np.nonzero(ok)[0]:
            if i + H >= len(g) or seg[i + H] != seg[i]:
                continue                                      # incomplete window or series break
            for d in depths:
                hit = np.nonzero(low[i + 1:i + H + 1] <= close[i] * (1 - d))[0]
                if len(hit):
                    j = i + 1 + hit[0]
                    rows.append((s, day[i], d, j - i, dd[j], close[j - 1] / (close[i] * (1 - d)) - 1))
    return pd.DataFrame(rows, columns=["sym", "start", "depth", "days_to_touch", "touch_day_dd",
                                       "prior_close_above_level"])


def desc(end=END):
    dd = OUT / "desc"; dd.mkdir(parents=True, exist_ok=True)
    lines = []; say = _say(lines)
    a = prep_daily(load_d1())
    a = _windows(a)
    a = a[(a.day >= START) & (a.day <= end)].copy()
    a = a[a.trades > 0]
    a["month"] = a.day.dt.to_period("M").astype(str)
    u = pd.read_csv(OUT / "ref" / "universe_monthly.csv")
    inb = set(zip(u.month[u["rank"] <= TOP_N], u.sym[u["rank"] <= TOP_N]))
    a["in_b"] = [(m, s) in inb for m, s in zip(a.month, a.sym)]
    c = candidates().set_index("sym")
    A = set(c.index[c.in_a.astype(str) == "True"]); C = set(c.index[c.in_c.astype(str) == "True"])
    PR = set(c.index[c.predecessor_of != ""])
    a["in_a"], a["in_c"] = a.sym.isin(A), a.sym.isin(C)

    # per-coin shares (the window starts at day t's close; H = 1 is the next day's low vs this close)
    rows = []
    for s, g in a.groupby("sym"):
        if not (g.in_a.any() or g.in_c.any() or g.in_b.any() or s in PR):
            continue
        r = dict(sym=s, in_a=s in A, in_c=s in C, predecessor_of=c.predecessor_of.get(s, ""), days_in_b=int(g.in_b.sum()),
                 first=g.day.min().date(), last=g.day.max().date())
        for H in WINDOWS:
            sh = _shares(g, H)
            r[f"n{H}"] = sh.pop("n")
            r[f"n{H}_indep"] = r[f"n{H}"] // H
            r.update({f"w{H}_{k}": v for k, v in sh.items()})
        rows.append(r)
    P = pd.DataFrame(rows); P.to_csv(dd / "touch_shares_by_coin.csv", index=False)

    # the same shares on the USD-M perpetual (sets (a) and (c); HYPE's only long Binance history is its perpetual)
    parts = []
    for f in sorted((OUT / "d1_um").glob("*.parquet")):
        k = pd.read_parquet(f); k.insert(0, "sym", f.stem); parts.append(k)
    if parts:
        u_ = pd.concat(parts, ignore_index=True)
        u_["day"] = u_.open_time.dt.tz_convert(None).dt.normalize()
        u_ = _windows(prep_daily(u_))
        u_ = u_[(u_.day >= START) & (u_.day <= end) & (u_.trades > 0)]
        rows = []
        for s, g in u_.groupby("sym"):
            r = dict(coin=s, first=g.day.min().date(), last=g.day.max().date())
            for H in WINDOWS:
                sh = _shares(g, H); r[f"n{H}"] = sh.pop("n")
                r.update({f"w{H}_{k}": v for k, v in sh.items()})
            rows.append(r)
        pd.DataFrame(rows).to_csv(dd / "touch_shares_perp.csv", index=False)

    a["lo_open"] = a.low / a.open - 1
    a["lo_close"] = a.low / a.close - 1
    a["shadow"] = a.low / a[["open", "close"]].min(axis=1) - 1

    # pooled groups and years
    grp = {"(a) user-style": a[a.in_a], "(c) Robinhood": a[a.in_c], "(b) top-100 PIT": a[a.in_b],
           "all USDT pairs (excl.)": a}
    rows = []
    for name, g in grp.items():
        for yr in ["all"] + sorted(g.day.dt.year.unique()):
            gg = g if yr == "all" else g[g.day.dt.year == yr]
            r = dict(group=name, year=yr, coins=gg.sym.nunique())
            for H in WINDOWS:
                sh = _shares(gg, H); r[f"n{H}"] = sh.pop("n")
                r.update({f"w{H}_{k}": v for k, v in sh.items()})
            rows.append(r)
    Q = pd.DataFrame(rows); Q.to_csv(dd / "touch_shares_pooled.csv", index=False)

    # wick depth (day bars): low vs open, low vs close, lower shadow (low vs min(open, close)); columns added above
    qs = (0.5, 0.9, 0.99, 0.999)
    rows = []
    for s, g in a.groupby("sym"):
        if not (s in A or s in C or s in PR):
            continue
        r = dict(sym=s, in_a=s in A, days=len(g))
        for col in ("lo_open", "lo_close", "shadow", "dd"):
            x = g[col].dropna()
            for q in qs:
                r[f"{col}_pct{(1 - q) * 100:g}"] = float(x.quantile(1 - q)) if len(x) else np.nan
            r[f"{col}_min"] = float(x.min()) if len(x) else np.nan
        for t in (5, 10, 20):
            r[f"shadow_ge{t}"] = float((g.shadow <= -t / 100).mean())
        rows.append(r)
    for name, g in grp.items():
        r = dict(sym=name, days=len(g))
        for col in ("lo_open", "lo_close", "shadow", "dd"):
            x = g[col].dropna()
            for q in qs:
                r[f"{col}_pct{(1 - q) * 100:g}"] = float(x.quantile(1 - q))
            r[f"{col}_min"] = float(x.min())
        for t in (5, 10, 20):
            r[f"shadow_ge{t}"] = float((g.shadow <= -t / 100).mean())
        rows.append(r)
    WD = pd.DataFrame(rows); WD.to_csv(dd / "wick_depth.csv", index=False)

    # market-wide wick days: (b) coins active that day with a valid prior-close reference
    b = a[a.in_b & a.dd.notna()].copy()
    day = b.groupby("day").agg(active=("sym", "size"), **{f"n{d}": ("dd", lambda x, d=d: int((x <= -d / 100).sum()))
                                                          for d in (10, 15, 20, 25, 30, 40, 50)})
    day["frac15"] = day.n15 / day.active
    day.to_csv(dd / "market_days.csv")
    mw = day[day.frac15 >= MW_FRAC].copy()
    say(f"market-wide wick days ({MW_FRAC:.0%}+ of the active top-{TOP_N} coins >= {MW_DEPTH}% below the prior close): "
        f"{len(mw)} of {len(day)} days")
    # clustering: share of coin-level deep wicks on market-wide days (leave-one-out fraction of the other coins)
    b = b.join(day[["active", "n15"]], on="day")
    b["frac15_others"] = (b.n15 - (b.dd <= -0.15)) / (b.active - 1)
    rows = []
    for name, g in (("(b) top-100 PIT", b), ("(a) user-style in (b)", b[b.in_a]), ("(c) Robinhood in (b)", b[b.in_c])):
        for thr in (0.05, 0.10, 0.20):
            on = g.frac15_others >= thr
            r = dict(group=name, mw_threshold=thr, coin_days=len(g), share_days_mw=float(on.mean()))
            for d in (15, 25, 40):
                w = g.dd <= -d / 100
                r[f"wicks{d}"] = int(w.sum()); r[f"share_on_mw{d}"] = float((w & on).sum() / max(w.sum(), 1))
            rows.append(r)
    CL = pd.DataFrame(rows); CL.to_csv(dd / "clustering.csv", index=False)
    # co-wick distribution: for each coin-level >= d% wick, how many OTHER (b) coins had >= 15% the same day
    rows = []
    for d in (15, 25, 40):
        w = b[b.dd <= -d / 100]
        oth = w.n15 - 1
        rows.append(dict(depth=d, wicks=len(w), others_0=int((oth == 0).sum()), others_1_4=int(oth.between(1, 4).sum()),
                         others_5_9=int(oth.between(5, 9).sum()), others_10_plus=int((oth >= 10).sum())))
    pd.DataFrame(rows).to_csv(dd / "co_wicks.csv", index=False)

    # how 30-day touches happened: days to the first touch and the touch day's own drop
    ft = _first_touch(prep_daily(load_d1()), end)
    ft["month"] = pd.to_datetime(ft.start).dt.to_period("M").astype(str)
    ft["in_b"] = [(m, s) in inb for m, s in zip(ft.month, ft.sym)]
    rows = []
    for name, g in (("(a) user-style", ft[ft.sym.isin(A)]), ("(c) Robinhood", ft[ft.sym.isin(C)]),
                    ("(b) top-100 PIT", ft[ft.in_b])):
        for d, x in g.groupby("depth"):
            rows.append(dict(group=name, depth=d, touched_windows=len(x), median_days_to_touch=x.days_to_touch.median(),
                             share_touch_on_day1=(x.days_to_touch == 1).mean(),
                             share_touch_day_drop_ge_half_depth=(x.touch_day_dd <= -d / 2).mean(),
                             share_touch_day_drop_lt10=(x.touch_day_dd > -0.10).mean(),
                             share_prior_close_within5_of_level=(x.prior_close_above_level <= 0.05).mean()))
    pd.DataFrame(rows).to_csv(dd / "first_touch_30d.csv", index=False)
    (dd / "summary.txt").write_text("\n".join(lines) + "\n")
    return P, Q, WD, day, CL


# ================================================================ 9. sample events from aggTrades
def _agg_frame(b: bytes, market: str) -> pd.DataFrame:
    head = 0 if b[:1].isdigit() else 1
    x = pd.read_csv(io.BytesIO(b), header=None, skiprows=head, usecols=[1, 2, 5, 6],
                    names=["price", "qty", "time", "is_buyer_maker"], dtype={"price": "float64", "qty": "float64"})
    t = x.time.astype("int64").to_numpy()
    x["time"] = pd.to_datetime(np.where(t > 10 ** 14, t, t * 1000), unit="us", utc=True)   # spot: us since 2025
    x["is_buyer_maker"] = x.is_buyer_maker.astype(str).str.lower().eq("true")
    return x.sort_values("time", kind="stable").reset_index(drop=True)


def _level_stats(x: pd.DataFrame, L: float) -> dict:
    le = x.price <= L
    qv = x.price * x.qty
    out = dict(trades_le=int(le.sum()), usd_le=float(qv[le].sum()), usd_lt=float(qv[x.price < L].sum()),
               usd_le_seller_init=float(qv[le & x.is_buyer_maker].sum()), base_le=float(x.qty[le].sum()))
    if not le.any():
        return out | dict(first_le=None, last_le=None, minutes_with_trade_le=0, time_le_min=0.0, longest_run_min=0.0,
                          below_at_day_end=False)
    t = (x.time - pd.Timestamp(0, tz="UTC")).dt.total_seconds().to_numpy()
    dt = np.diff(t, append=t[-1])
    lev = le.to_numpy()
    # continuous stretches where the last trade price was <= L
    grp = np.cumsum(np.r_[True, lev[1:] != lev[:-1]])
    run = pd.Series(dt[lev]).groupby(grp[lev]).sum()
    return out | dict(first_le=x.time[le].iloc[0], last_le=x.time[le].iloc[-1],
                      minutes_with_trade_le=int(x.time[le].dt.floor("min").nunique()),
                      time_le_min=float(dt[lev].sum() / 60), longest_run_min=float(run.max() / 60),
                      below_at_day_end=bool(lev[-1]))           # True: the time below is cut off at 24:00 UTC


def events(force=False):
    d = OUT / "events"; d.mkdir(parents=True, exist_ok=True)
    jobs = [(e, c, "spot") for e in EVENTS for c in EVENT_COINS] + list(EVENT_EXTRA)
    um = um_contracts()
    perf = []
    for e, coin, market in jobs:                              # 1. download (sha256-checked), cache as parquet
        con, mult = (coin + "USDT", 1) if market == "spot" else um[coin]
        f = d / f"{e}_{coin}USDT_{market}.parquet"
        if f.exists() and not force:
            continue
        base = "data/spot" if market == "spot" else "data/futures/um"
        key = f"{base}/daily/aggTrades/{con}/{con}-aggTrades-{e}.zip"
        t0 = time.time()
        raw = get(f"{S3}/{key}")
        sec = time.time() - t0
        if raw is None:
            print("events: missing", key); continue
        cs = get(f"{S3}/{key}.CHECKSUM", 60)                  # sha256 against the archive's .CHECKSUM
        if cs is None or cs.decode().split()[0] != hashlib.sha256(raw).hexdigest():
            raise IOError(f"checksum missing or mismatched: {key}")
        ok = True
        z = zipfile.ZipFile(io.BytesIO(raw))
        b = z.read(z.namelist()[0])
        x = _agg_frame(b, market)
        if mult != 1:
            x["price"] /= mult; x["qty"] *= mult
        x.to_parquet(f, index=False)
        perf.append(dict(key=key, zip_bytes=len(raw), csv_bytes=len(b), seconds=sec, sha256_verified=ok,
                         parquet_bytes=f.stat().st_size, rows=len(x)))
        print(f"events: {key} {len(raw) / 2 ** 20:.1f} MB in {sec:.1f}s, {len(x):,} aggTrades", flush=True)
    if perf:
        old = pd.read_csv(d / "download_perf.csv") if (d / "download_perf.csv").exists() else pd.DataFrame()
        pd.concat([old, pd.DataFrame(perf)], ignore_index=True).to_csv(d / "download_perf.csv", index=False)
    rows = []
    for e, coin, market in jobs:                              # 2. counts and minutes below the levels
        con = coin + "USDT" if market == "spot" else um[coin][0]
        f = d / f"{e}_{coin}USDT_{market}.parquet"
        kf = (OUT / "d1_spot" / f"{coin}USDT.parquet") if market == "spot" else (OUT / "d1_um" / f"{coin}.parquet")
        if not f.exists() or not kf.exists():
            print("events: skipped", e, coin, market); continue
        x = pd.read_parquet(f)
        k = pd.read_parquet(kf).set_index("open_time")
        day = pd.Timestamp(e, tz="UTC")
        P0 = float(k.close.loc[day - pd.Timedelta("1D")])
        kl = k.loc[day]
        qv = x.price * x.qty
        r0 = dict(event=e, coin=coin, market=market, contract=con, prior_close=P0, trades_day=len(x),
                  usd_day=float(qv.sum()), day_low=float(x.price.min()), day_low_time=x.time[x.price.idxmin()],
                  day_low_vs_prior_close=float(x.price.min() / P0 - 1), kline_low=float(kl.low),
                  kline_low_match=bool(abs(x.price.min() / kl.low - 1) < 1e-9),
                  kline_qv_rel_diff=float(qv.sum() / kl.quote_volume - 1), kline_trades=int(kl.trades))
        for lv in LEVELS:
            L = P0 * (1 - lv / 100)
            rows.append(r0 | dict(level_pct=lv, level_price=L) | _level_stats(x, L))
        print(f"events {e} {coin:5s} {market:4s}: low {r0['day_low_vs_prior_close']:+.1%} vs prior close at "
              f"{r0['day_low_time']:%H:%M:%S}; ${r0['usd_day'] / 1e6:,.0f}M traded; kline low match "
              f"{r0['kline_low_match']}", flush=True)
    R = pd.DataFrame(rows); R.to_csv(d / "levels.csv", index=False)
    return R


# ================================================================ 10. size and time estimates
def _throughput(keys, workers):
    """Download the given zips concurrently; returns (zip bytes, csv bytes, seconds)."""
    def one(k):
        b = get(f"{S3}/{k}")
        if b is None:
            return 0, 0
        z = zipfile.ZipFile(io.BytesIO(b))
        return len(b), z.getinfo(z.namelist()[0]).file_size
    t0 = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, keys))
    return sum(r[0] for r in res), sum(r[1] for r in res), time.time() - t0


def sizes(end=END, workers=WORKERS, mw_frac=MW_FRAC):
    d = OUT / "sizes"; d.mkdir(parents=True, exist_ok=True)
    cov = pd.read_csv(OUT / "coverage" / "coverage.csv", keep_default_na=False)
    ds = pd.read_parquet(OUT / "coverage" / "daily_sizes.parquet")
    day = pd.read_csv(OUT / "desc" / "market_days.csv", parse_dates=["day"])
    ev = sorted(day.day[day.frac15 >= mw_frac].dt.strftime("%Y-%m-%d"))
    groups = {"all candidates": cov, "(a) user-style": cov[cov.in_a.astype(str) == "True"],
              "(c) Robinhood": cov[cov.in_c.astype(str) == "True"]}
    # measured throughput: 24 monthly 1m zips and 8 event-day aggTrades zips, fetched concurrently
    smp = []
    for s in list(groups["(a) user-style"].sym)[:16]:
        smp += [f"data/spot/monthly/klines/{s}/1m/{s}-1m-2024-{m:02d}.zip" for m in (3, 6, 9)]
    zb, cb, sec = _throughput(smp, workers)
    ag = ds[(ds.kind == "agg") & ds.day.isin(ev) & ds.sym.isin(set(groups["(a) user-style"].sym))]
    ag = ag.sort_values("bytes").iloc[len(ag) // 2 - 6: len(ag) // 2 + 6]       # 12 mid-sized event-day files
    zb2, cb2, sec2 = _throughput([f"data/spot/daily/aggTrades/{s}/{s}-aggTrades-{x}.zip" for s, x in zip(ag.sym, ag.day)],
                                 workers)
    perf = dict(m1_sample_zips=len(smp), m1_zip_mb=zb / 2 ** 20, m1_csv_mb=cb / 2 ** 20, m1_seconds=sec,
                m1_mb_per_s=zb / 2 ** 20 / sec, m1_csv_per_zip=cb / max(zb, 1),
                agg_sample_zips=len(ag), agg_zip_mb=zb2 / 2 ** 20, agg_csv_mb=cb2 / 2 ** 20, agg_seconds=sec2,
                agg_mb_per_s=zb2 / 2 ** 20 / max(sec2, 1e-9), agg_csv_per_zip=cb2 / max(zb2, 1))
    rates = {"1m": max(perf["m1_mb_per_s"], 1e-6), "agg": max(perf["agg_mb_per_s"], 1e-6)}
    # coin-level deep-wick days: the candidate's own daily low >= 15% below its prior close
    a = prep_daily(load_d1())
    a = a[(a.day >= START) & (a.day <= end) & (a.dd <= -0.15)]
    deep = set(zip(a.sym, a.day.dt.strftime("%Y-%m-%d")))
    ds["deep"] = [(s_, x) in deep for s_, x in zip(ds.sym, ds.day)]
    rows = []
    for name, g in groups.items():
        syms = set(g.sym)
        m1 = g["1m_bytes_monthly_from2020"].astype(float).sum()
        # the month of END has only daily zips
        m1 += ds[(ds.kind == "1m") & ds.sym.isin(syms) & (ds.day >= end[:7] + "-01")].bytes.sum()
        sel = ds.sym.isin(syms) & (ds.day >= START) & (ds.day <= end)
        m1e = ds[sel & (ds.kind == "1m") & ds.day.isin(ev)]
        age = ds[sel & (ds.kind == "agg") & ds.day.isin(ev)]
        m1d = ds[sel & (ds.kind == "1m") & ds.deep]
        agd = ds[sel & (ds.kind == "agg") & ds.deep]
        aga = g.agg_bytes_monthly_from2020.astype(float).sum()
        for kind, what, zbytes, nfiles, ratio in (
                ("1m", "1m klines, all days 2020-01-01..END", m1, int(g["1m_monthly_files"].astype(int).sum()),
                 perf["m1_csv_per_zip"]),
                ("1m", f"1m klines, {len(ev)} market-wide days", m1e.bytes.sum(), len(m1e), perf["m1_csv_per_zip"]),
                ("1m", "1m klines, the coin's own >= 15% wick days", m1d.bytes.sum(), len(m1d), perf["m1_csv_per_zip"]),
                ("agg", f"aggTrades, {len(ev)} market-wide days", age.bytes.sum(), len(age), perf["agg_csv_per_zip"]),
                ("agg", "aggTrades, the coin's own >= 15% wick days", agd.bytes.sum(), len(agd), perf["agg_csv_per_zip"]),
                ("agg", "aggTrades, all days 2020-01..last monthly file", aga, int(g.agg_monthly_files.astype(int).sum()),
                 perf["agg_csv_per_zip"])):
            rows.append(dict(group=name, coins=len(syms), what=what, files=nfiles, zip_gb=zbytes / 2 ** 30,
                             csv_gb_est=zbytes * ratio / 2 ** 30,
                             hours_at_measured_rate=zbytes / 2 ** 20 / rates[kind] / 3600))
    E = pd.DataFrame(rows); E.to_csv(d / "estimates.csv", index=False)
    _save_json(d / "throughput.json", perf | {"event_days": ev})
    print(json.dumps(perf, indent=1, default=str))
    print(E.to_string(index=False))
    return E, perf


# ================================================================ CLI
def _arg(name, default):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    end = _arg("--end", END)
    force = "--force" in sys.argv
    workers = int(_arg("--workers", WORKERS))
    rh = _arg("--rh-pairs", None)
    steps = ["listing", "d1", "sets", "h1", "perp1d", "coverage", "validate", "desc", "events", "sizes"]
    if cmd != "all" and cmd not in steps:
        print(__doc__); sys.exit(1)
    for s in steps:
        if cmd not in (s, "all"):
            continue
        {"listing": lambda: listing(workers), "d1": lambda: d1(end, force, workers), "sets": lambda: sets(end, rh),
         "h1": lambda: h1(end, force, workers), "perp1d": lambda: perp1d(end, force, workers),
         "coverage": lambda: coverage(workers), "validate": lambda: validate(end), "desc": lambda: desc(end),
         "events": lambda: events(force), "sizes": lambda: sizes(end, workers)}[s]()
