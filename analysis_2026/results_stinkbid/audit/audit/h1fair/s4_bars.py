"""Step 4: per-coin raw-bar pass (one coin at a time).
For every H1 fill: F1 validity and first-ness, bar features around the fill minute, an independent X-FLIP exit
(target R1/2 on the tick, rule-M go-live, marketable / resting target / 72 h stop) and an independent replica of the
B-TWIN own twins (default_rng(20261118 + fill_id), uniform over the coin's live bars in its U-Q1 member months, outside
+-182 days, complete window), compared with the engine's r and twin_mean.
Written from the prereg text (§7, §8, §10.1, §10.2); no engine / stats function is imported."""
import sys
import math
import resource
import time
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
import numpy as np
import pandas as pd
from common import *
import pyarrow as pa
import pyarrow.parquet as pq

NY = ZoneInfo("America/New_York")
C = 0.0095
END_MIN = int(pd.Timestamp("2026-11-18", tz="UTC").value // 60_000_000_000) - 1
SEED = 20261118
EXCL = 182 * 1440
STOP = 72 * 60


def rule_m(tmin):
    """Rule M (§8) vectorised: t + 60 if t is 07:00-22:59 New York, else the next 07:00 New York."""
    tmin = np.asarray(tmin, np.int64)
    ts = pd.DatetimeIndex(pd.to_datetime(tmin * 60, unit="s", utc=True))
    loc = ts.tz_convert(NY)
    mins = np.asarray(loc.hour * 60 + loc.minute)
    day_ok = (mins >= 420) & (mins <= 1379)
    naive = loc.tz_localize(None).normalize()
    tgt = naive + pd.to_timedelta(np.where(mins < 420, 0, 1), unit="D") + pd.Timedelta(hours=7)
    tgt_utc = pd.DatetimeIndex(tgt).tz_localize(NY).tz_convert("UTC")
    tm = np.asarray(tgt_utc.as_unit("s").asi8 // 60, np.int64)
    return np.where(day_ok, tmin + 60, tm)


def ceil_tick(x, tick_str):
    q = Decimal(tick_str)
    n = (Decimal(repr(float(x))) / q).to_integral_value(rounding=ROUND_CEILING)
    return float(n * q), float((n + 1) * q)


# ---- cut: the largest entry minute whose horizon M(te + 72 h) is at or before the data end
cand = np.arange(END_MIN - STOP - 2 * 1440, END_MIN + 1, dtype=np.int64)
CUT = int(cand[rule_m(cand + STOP) <= END_MIN].max())
print("data end", min2ts([END_MIN])[0], " cut (latest complete twin entry)", min2ts([CUT])[0])

O = pd.read_parquet(f"{OUT}/h1rows2.parquet")
F = load_fills(cols=["fill_id", "coin", "t_F1", "i_F1", "live_from", "life_end", "seg", "sidx", "tick", "tick_str",
                     "L", "L_tau", "P0", "t0", "gap_through", "open_below", "prev_close_above"])
F = F[F.fill_id.isin(O.fill_id)].set_index("fill_id")
B = pd.read_parquet(f"{RUN}/P1__U_Q1/bids.parquet", columns=["coin", "t0", "tick", "tick_str"]).drop_duplicates(
    ["coin", "t0"])
segmap = pd.read_parquet(f"{OUT}/segmap.parquet")
univ = pd.read_parquet(f"{OUT}/univ.parquet")

fill_rows, twin_rows = [], []
t_start = time.time()
for ci, coin in enumerate(sorted(O.coin.unique())):
    Oc = O[O.coin == coin]
    sym = coin + "USDT"
    path = f"{ROOT}/data/stinkbid/m1_spot/{sym}.parquet"

    def col(name):
        a = pq.read_table(path, columns=[name]).column(0)
        if name == "open_time":
            return (a.cast(pa.int64()).to_numpy() // 60_000_000_000).astype(np.int64)
        return a.to_numpy()
    t = col("open_time")
    sel = None
    if not np.all(np.diff(t) > 0):
        o_ = np.argsort(t, kind="stable")
        keep = np.r_[True, np.diff(t[o_]) > 0]
        sel = o_[keep]
        t = t[sel]
    pick = (lambda a: a) if sel is None else (lambda a: a[sel])
    op = pick(col("open")).astype(float)
    hi = pick(col("high")).astype(float)
    lo = pick(col("low")).astype(float)
    cl = pick(col("close")).astype(float)
    tr = pick(col("trades"))
    qv = pick(col("quote_volume")).astype(np.float32)
    tbq = pick(col("taker_buy_quote")).astype(np.float32)
    sm = segmap[segmap.coin == coin]
    dmap = dict(zip((sm.day.astype("int64") // 86_400_000_000_000).tolist(), sm.seg.tolist()))
    day = t // 1440
    ud, inv = np.unique(day, return_inverse=True)
    seg = np.array([dmap.get(int(x), -1) for x in ud], np.int64)[inv]
    ok = seg >= 0
    del day, inv
    if not ok.all():
        t, op, hi, lo, cl, tr, qv, tbq, seg = (a[ok] for a in (t, op, hi, lo, cl, tr, qv, tbq, seg))
    del ok
    n = len(t)
    live = tr > 0
    # next live index at or after i
    nl = np.full(n + 1, n, np.int64)
    idx_live = np.flatnonzero(live)
    nl[:n] = idx_live[np.minimum(np.searchsorted(idx_live, np.arange(n)), len(idx_live) - 1)] if len(idx_live) else n
    nl[:n][np.arange(n) > (idx_live[-1] if len(idx_live) else -1)] = n
    hl = np.where(live, hi, -np.inf)
    segchg = np.r_[0, np.cumsum(seg[1:] != seg[:-1])]          # run id of consecutive same-seg bars

    def exit_one(j_entry, g, S, T, up):
        """(kind, exit index, price, crossed) from entry bar j_entry; positions on the coin's own bars only."""
        gi = nl[min(np.searchsorted(t, g), n)]
        si = nl[min(np.searchsorted(t, S), n)]
        if si >= n:
            return "beyond", -1, np.nan, True
        crossed = segchg[si] != segchg[j_entry]
        if t[gi] >= S:
            return "stop", si, op[si], crossed
        if op[gi] >= T:
            return "marketable", gi, op[gi], crossed or segchg[gi] != segchg[j_entry]
        w = hl[gi:si] >= up
        if w.any():
            h = gi + int(np.argmax(w))
            return "target", h, T, crossed or segchg[h] != segchg[j_entry]
        return "stop", si, op[si], crossed

    # ---- eligible twin bars: own live bars in U-Q1 member months, at or before CUT
    um = univ[(univ.coin == coin) & univ.U_Q1].month.unique()
    um_i = np.array([np.datetime64(x, "M").astype(np.int64) for x in um], np.int64)
    mon = (t * 60).astype("datetime64[s]").astype("datetime64[M]").astype(np.int64)
    elig = np.flatnonzero(live & np.isin(mon, um_i) & (t <= CUT))
    te_all = t[elig]
    ed = te_all // 1440
    # tick for twins: the coin's most recent bid placement (bids table)
    Bc = B[B.coin == coin].sort_values("t0")
    bt0, btk = Bc.t0.to_numpy(np.int64), Bc.tick.to_numpy(float)

    for _, r in Oc.iterrows():
        fid = int(r.fill_id)
        f = F.loc[fid]
        m = int(f.t_F1)
        j = int(np.searchsorted(t, m))
        found = j < n and t[j] == m
        rec = dict(fill_id=fid, coin=coin, found=found)
        if not found:
            fill_rows.append(rec)
            continue
        L = float(f.L)
        ts_ = str(f.tick_str)
        Lm = float(Decimal(repr(L)) - Decimal(ts_))
        # F1 validity and first-ness (within the life and the bar's segment)
        a = np.searchsorted(t, int(f.live_from))
        prior = np.flatnonzero(live[a:j] & (lo[a:j] <= Lm) & (seg[a:j] == seg[j]))
        pj = j - 1
        while pj >= 0 and not live[pj]:
            pj -= 1
        nxt = slice(j + 1, min(j + 6, n))
        rec.update(live=bool(live[j]), low_ok=bool(lo[j] <= Lm), first=len(prior) == 0, seg_me=int(seg[j]),
                   seg_eng=int(f.seg), o=op[j], h=hi[j], l=lo[j], c=cl[j], qv=qv[j], sellq=max(qv[j] - tbq[j], 0.0),
                   trades=int(tr[j]), prev_c=cl[pj] if pj >= 0 else np.nan, prev_gap_min=(m - t[pj]) if pj >= 0 else -1,
                   next5_maxc=np.max(cl[nxt]) if j + 1 < n else np.nan,
                   next5_minl=np.min(lo[nxt]) if j + 1 < n else np.nan,
                   next5_c=cl[min(j + 5, n - 1)], next1_o=op[j + 1] if j + 1 < n else np.nan,
                   next5_span=(t[min(j + 5, n - 1)] - m))
        # independent X-FLIP exit
        T, up = ceil_tick(L + 0.5 * (float(f.P0) - L), ts_)
        g = int(rule_m([m])[0])
        S = int(rule_m([m + STOP])[0])
        kind, ji, px, crossed = exit_one(j, g, S, T, up)
        rme = px * (1 - C) / (L * (1 + C)) - 1 if np.isfinite(px) else np.nan
        rec.update(T_me=T, T_eng=float(r.target), kind_me=kind, exit_t_me=int(t[ji]) if ji >= 0 else -1,
                   r_me=rme, r_eng=float(r.r), kind_eng=r.exit_kind, exit_t_eng=int(r.exit_t), crossed=bool(crossed),
                   g_me=g, S_me=S)
        # ---- twins
        k_cut = len(te_all)
        i0 = min(int(np.searchsorted(te_all, m - EXCL, side="left")), k_cut)
        i1 = min(int(np.searchsorted(te_all, m + EXCL, side="right")), k_cut)
        nL, nR = i0, k_cut - i1
        days = len(np.unique(ed[:i0])) + len(np.unique(ed[i1:k_cut]))
        pooled_me = days < 182 or nL + nR == 0
        rec.update(elig_days=days, elig_min=nL + nR, pooled_me=pooled_me, pooled_eng=bool(r.twin_pooled),
                   twin_eng=float(r.twin_mean))
        if not pooled_me:
            u = np.random.default_rng(SEED + fid).random(100)
            kk = np.minimum((u * (nL + nR)).astype(np.int64), nL + nR - 1)
            pos = np.where(kk < nL, kk, i1 + kk - nL)
            bars = elig[pos]
            tes = t[bars]
            gs = rule_m(tes)
            Ss = rule_m(tes + STOP)
            ratio = T / L
            kb = np.clip(np.searchsorted(bt0, tes, side="right") - 1, 0, max(len(bt0) - 1, 0))
            taus = btk[kb] if len(btk) else np.full(len(tes), float(f.tick))
            rs, nx, kinds = [], 0, []
            for q in range(100):
                e = op[bars[q]]
                Tq = e * ratio
                kd, jq, pxq, cr = exit_one(bars[q], int(gs[q]), int(Ss[q]), Tq, Tq + taus[q])
                nx += int(cr)
                kinds.append(kd)
                rs.append(pxq * (1 - C) / (e * (1 + C)) - 1 if np.isfinite(pxq) else np.nan)
            rs = np.array(rs)
            kinds = np.array(kinds)
            rec.update(twin_me=np.nanmean(rs), twin_n_me=int(np.isfinite(rs).sum()), twin_crossed=nx,
                       twin_hit_rate=float((kinds == "target").mean()),
                       twin_mkt_rate=float((kinds == "marketable").mean()),
                       twin_entry_min=int(tes.min()), twin_entry_max=int(tes.max()),
                       twin_min_dist_d=float(np.min(np.abs(tes - m)) / 1440))
        fill_rows.append(rec)
    if ci % 10 == 0:
        print(f"{ci} {coin} n={n} fills={len(Oc)} {time.time() - t_start:.0f}s  RSS "
              f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB", flush=True)
    del t, op, hi, lo, cl, tr, qv, tbq, seg, live, nl, hl, segchg, mon, elig

R = pd.DataFrame(fill_rows)
R.to_parquet(f"{OUT}/bars_pass.parquet")
print("done", len(R), f"{time.time() - t_start:.0f}s peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")
