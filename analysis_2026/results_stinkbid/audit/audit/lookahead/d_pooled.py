"""(d) Rebuild the POOLED B-TWIN mean of one P1 U-Q1 fill (prereg §10.1: fewer than 182 eligible days -> twins from all
U-Q1 coins' eligible minutes outside +-182 days of tau_f), X-FLIP, C-RH, with my own code: per-coin day tables of
eligible minutes (live 1m bars on traded days in the coin's U-Q1 months), whole days that end by the horizon cutoff
and do not touch [tau - 182 d, tau + 182 d], uniform draw with default_rng(20261118 + fill_id). Reports the minimum
distance of every pooled twin from the fill and the max horizon, and compares the mean with outcomes' twin_mean."""
import datetime as dt
import gc
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/moneyline-upgrade")
from analysis_2026 import stinkbid_data as sbd          # data loaders only

S = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/lookahead"
R = "data/stinkbid/runs/outcomes/P1__U_Q1"
NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
END_MIN = int(pd.Timestamp("2026-11-18", tz="UTC").value // 60_000_000_000) - 1
C = 0.0095


def rule_m(tmin):
    t = EPOCH + dt.timedelta(minutes=int(tmin))
    loc = t.astimezone(NY)
    hm = loc.hour * 60 + loc.minute
    if 420 <= hm <= 1379:
        return int(tmin) + 60
    day = loc.date() if hm < 420 else loc.date() + dt.timedelta(days=1)
    nxt = dt.datetime(day.year, day.month, day.day, 7, 0, tzinfo=NY).astimezone(UTC)
    return int((nxt - EPOCH).total_seconds() // 60)


def tmin_of(s):
    return np.asarray((s - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1min"), dtype=np.int64)


def traded_days(sym):
    d1 = pd.read_parquet("data/stinkbid/d1_full_all.parquet", columns=["sym", "open_time", "trades"],
                         filters=[("sym", "==", sym)])
    return set((tmin_of(d1[d1.trades > 0].open_time) // 1440).tolist())


def coin_minutes(coin, months, lo=None, hi=None):
    sym, a, b = sbd.coin_sym(coin)
    filt = []
    if lo is not None:
        filt.append(("open_time", ">=", pd.Timestamp(int(lo) * 60, unit="s", tz="UTC")))
    if hi is not None:
        filt.append(("open_time", "<", pd.Timestamp(int(hi) * 60, unit="s", tz="UTC")))
    k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet",
                        columns=["open_time", "open", "high", "low", "close", "trades"], filters=filt or None)
    t = tmin_of(k.open_time)
    keep = np.ones(len(k), bool)
    if a:
        keep &= t // 1440 >= int(pd.Timestamp(a).value // 86_400_000_000_000)
    if b:
        keep &= t // 1440 <= int(pd.Timestamp(b).value // 86_400_000_000_000)
    k, t = k[keep], t[keep]
    td = traded_days(sym)
    on = np.isin(t // 1440, list(td))
    k, t = k[on], t[on]
    return k.assign(t=t)


def main(fid):
    u = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
    q1 = {c: set(g.month) for c, g in u[u.U_Q1].groupby("coin")}
    F = pd.read_parquet(f"{R}/fills.parquet", columns=["fill_id", "coin", "t_F1", "L"])
    O = pd.read_parquet(f"{R}/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "target", "twin_mean",
                                                          "twin_n", "twin_pooled"])
    row = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & (O.fill_id == fid)].iloc[0]
    f = F[F.fill_id == fid].iloc[0]
    assert bool(row.twin_pooled)
    tau = int(f.t_F1)
    ratio = float(row.target) / float(f.L)
    # FLIP cutoff
    lo, hi = END_MIN - 72 * 60 - 5 * 1440, END_MIN
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if rule_m(mid + 72 * 60) <= END_MIN:
            lo = mid
        else:
            hi = mid
    cut = lo
    cut_day = (cut - 1439) // 1440
    x0, x1 = (tau - 182 * 1440) // 1440, (tau + 182 * 1440) // 1440
    # coin order of the engine's pooled tables: coins with fills (sorted), then the other U-Q1 coins (sorted)
    fill_coins = sorted(set(F.coin))
    order = [c for c in fill_coins if c in q1] + [c for c in sorted(q1) if c not in fill_coins]
    tabs = []
    for c in order:
        k = coin_minutes(c, q1[c])
        live = k.trades.to_numpy() > 0
        mon = pd.to_datetime(k.t * 60, unit="s").dt.strftime("%Y-%m").to_numpy()
        el = live & np.isin(mon, list(q1[c]))
        d = k.t.to_numpy()[el] // 1440
        days, cnt = np.unique(d, return_counts=True)
        ok = (days <= cut_day) & ((days < x0) | (days > x1))
        tabs.append((c, days[ok], cnt[ok]))
        del k
        gc.collect()
    N = sum(int(x[2].sum()) for x in tabs)
    cum = np.cumsum([int(x[2].sum()) for x in tabs])
    uu = np.random.default_rng(20261118 + int(fid)).random(100)
    draws = []
    for v in uu:
        r_ = min(int(v * N), N - 1)
        ci = int(np.searchsorted(cum, r_, side="right"))
        off = r_ - (cum[ci - 1] if ci > 0 else 0)
        c, days, cnt = tabs[ci]
        ck = np.cumsum(cnt)
        di = int(np.searchsorted(ck, off, side="right"))
        rank = off - (ck[di - 1] if di > 0 else 0)
        draws.append((c, int(days[di]), int(rank)))
    seg = pd.read_csv("data/stinkbid/ref/segments.csv")
    rs, info = [], []
    for c, day, rank in draws:
        k = coin_minutes(c, q1[c], lo=day * 1440 - 8 * 1440, hi=day * 1440 + 6 * 1440)
        t = k.t.to_numpy()
        live = k.trades.to_numpy() > 0
        mon = pd.to_datetime(t * 60, unit="s").strftime("%Y-%m").to_numpy()
        el = np.flatnonzero(live & np.isin(mon, list(q1[c])) & (t // 1440 == day))
        b = el[rank]
        te = int(t[b])
        entry = float(k.open.to_numpy()[b])
        T = entry * ratio
        g, Sx = rule_m(te), rule_m(te + 72 * 60)
        # tick of the most recent Monday 03:30 placement at or before te
        mon0 = int(pd.Timestamp("2020-01-06 03:30", tz="UTC").value // 60_000_000_000)
        tq = mon0 + ((te - mon0) // (7 * 1440)) * 7 * 1440
        e0 = (tq // 1440) * 1440
        w = k[(t >= e0 - 7 * 1440) & (t < e0) & live]
        px = np.concatenate([w.open, w.high, w.low, w.close])
        un, cn = np.unique(px, return_counts=True)
        dec = np.array([len(s.split(".")[1]) if "." in s else 0 for s in
                        (np.format_float_positional(float(x), unique=True, trim="-") for x in un)])
        tick = next(10.0 ** -d for d in range(13) if cn[dec > d].sum() <= 0.001 * cn.sum())
        o, h = k.open.to_numpy(), k.high.to_numpy()
        gi = np.searchsorted(t, g)
        while gi < len(t) and not live[gi]:
            gi += 1
        last_t = int(t[np.flatnonzero(live)[-1]])
        sg = seg[seg.coin == c].sort_values("seg").iloc[-1]
        ends_here = last_t < Sx and sg.kind != "data_end"
        if ends_here:
            info.append((c, te, "window reaches the coin's segment end", sg.kind))
        if gi >= len(t):
            rs.append(np.nan)
            continue
        if o[gi] >= T:
            rs.append(o[gi] * (1 - C) / (entry * (1 + C)) - 1)
            info.append((c, te, "marketable", ""))
            continue
        si = max(gi, np.searchsorted(t, Sx))
        while si < len(t) and not live[si]:
            si += 1
        hh = np.where(live[gi:si], h[gi:si], -np.inf)
        if (hh >= T + tick).any():
            rs.append(T * (1 - C) / (entry * (1 + C)) - 1)
        elif si < len(t):
            rs.append(o[si] * (1 - C) / (entry * (1 + C)) - 1)
        else:
            rs.append(np.nan)
            info.append((c, te, "no stop bar in the loaded window", sg.kind))
        info.append((c, te, "ok", ""))
    rs = np.array(rs)
    te_all = np.array([x[1] for x in info if x[2] in ("ok", "marketable")])
    print(dict(fill_id=fid, coin=f.coin, fill=str(pd.Timestamp(tau * 60, unit="s", tz="UTC")), N_pool=N,
               coins_drawn=len(set(x[0] for x in draws)), twin_mean_stored=float(row.twin_mean),
               twin_mean_mine=float(np.nanmean(rs)), absdiff=abs(float(row.twin_mean) - float(np.nanmean(rs))),
               n_stored=int(row.twin_n), n_mine=int(np.isfinite(rs).sum()),
               min_days_from_fill=round(float(np.abs(np.array([d * 1440 for _, d, _ in draws]) - tau).min() / 1440), 2),
               last_twin_day=str(pd.Timestamp(max(d for _, d, _ in draws) * 86400, unit="s").date()),
               cut=str(pd.Timestamp(cut * 60, unit="s", tz="UTC"))))
    print("notes:", [x for x in info if x[2] not in ("ok", "marketable")][:10])


if __name__ == "__main__":
    main(int(sys.argv[1]))
