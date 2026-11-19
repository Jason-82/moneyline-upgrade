"""(d) Rebuild B-TWIN for selected fills with independent code (prereg §10.1, §8, §9, §4.1): eligible entry minutes =
live 1m bars of the coin in its program-universe member months, strictly outside [tau_f - 182 d, tau_f + 182 d],
whose exit horizon (rule M) is at or before the data end; 100 draws from default_rng(20261118 + fill_id); exits
X-FLIP (target = entry x R1/2 / L, trade-through T + tau, rule M, 72 h stop) or X-HOLD-h; C-RH costs; a window cut
by a delisting is closed at VWAP(last full day) x 0.70. Compares the twins' mean with outcomes.parquet's twin_mean
and reports the min distance of every twin entry from the fill and the max twin horizon."""
import datetime as dt
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/moneyline-upgrade")
from analysis_2026 import stinkbid_data as sbd          # data loaders only (coin_sym)

NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
END_MIN = int(pd.Timestamp("2026-11-18", tz="UTC").value // 60_000_000_000) - 1
C = 0.0095
SEED = 20261118
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)


def rule_m(tmin: int) -> int:
    """§8: t + 60 min if t's New York clock time is 07:00-22:59, else the next 07:00 New York time."""
    t = EPOCH + dt.timedelta(minutes=int(tmin))
    loc = t.astimezone(NY)
    hm = loc.hour * 60 + loc.minute
    if 7 * 60 <= hm <= 22 * 60 + 59:
        return int(tmin) + 60
    day = loc.date() if hm < 7 * 60 else loc.date() + dt.timedelta(days=1)
    nxt = dt.datetime(day.year, day.month, day.day, 7, 0, tzinfo=NY).astimezone(UTC)
    return int((nxt - EPOCH).total_seconds() // 60)


def decimals_unique(px):
    u, c = np.unique(px, return_counts=True)
    dec = np.array([len(s.split(".")[1]) if "." in s else 0
                    for s in (np.format_float_positional(float(x), unique=True, trim="-") for x in u)])
    return dec, c


def tick_for_monday(k_t, k_px, t0):
    """tick of the Monday placement t0 (minutes): 1m prices with trades > 0 of the 7 UTC days d0-6..d0."""
    d0_end = (t0 // 1440) * 1440                 # Monday 00:00 = end of d0
    a, b = np.searchsorted(k_t, d0_end - 7 * 1440), np.searchsorted(k_t, d0_end)
    if b <= a:
        return None
    dec, cnt = decimals_unique(k_px[a:b].ravel())
    n = cnt.sum()
    for d in range(13):
        if cnt[dec > d].sum() <= 0.001 * n:
            return 10.0 ** -d
    return None


def main(run, fills, exits):
    F = pd.read_parquet(f"{run}/fills.parquet", columns=["fill_id", "coin", "t_F1", "L", "P0", "sigma30", "tick_str",
                                                          "universe", "lineage"])
    O = pd.read_parquet(f"{run}/outcomes.parquet",
                        columns=["rule", "exit", "cost", "fill_id", "r", "target", "twin_mean", "twin_n", "twin_pooled",
                                 "complete", "horizon_t", "exit_kind"])
    O = O[(O.rule == "F1") & (O.cost == "C-RH")]
    u = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1", "U_B", "U_C"])
    seg = pd.read_csv("data/stinkbid/ref/segments.csv")
    out = []
    cache = {}
    for fid in fills:
        f = F[F.fill_id == fid].iloc[0]
        coin = f.coin
        univ = f.universe
        if coin not in cache:
            cache.clear()                      # one coin in memory at a time (memory budget)
            import gc; gc.collect()
            sym = sbd.coin_sym(coin)[0]
            k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet",
                                columns=["open_time", "open", "high", "low", "close", "trades"])
            t = (k.open_time.astype("int64") // 60_000_000_000).to_numpy()
            if str(k.open_time.dtype).endswith("[ms, UTC]"):
                t = (k.open_time.astype("int64") // 60_000).to_numpy()
            k = k.assign(t=t)
            d1 = pd.read_parquet("data/stinkbid/d1_full_all.parquet", columns=["sym", "open_time", "trades"],
                                 filters=[("sym", "==", sym)])
            tdays = set((d1[d1.trades > 0].open_time.astype("int64") // (86_400 * 10**3 if str(
                d1.open_time.dtype).endswith("[ms, UTC]") else 86_400 * 10**9)).tolist())
            k = k[np.isin(k.t.to_numpy() // 1440, list(tdays))].reset_index(drop=True)
            live = k.trades.to_numpy() > 0
            mm = set(u[(u.coin == coin) & u[univ]].month)
            mon = pd.to_datetime(k.t * 60, unit="s").dt.strftime("%Y-%m").to_numpy()
            elig = live & np.isin(mon, list(mm))
            sg = seg[seg.coin == coin].sort_values("seg")
            lastseg = sg.iloc[-1]
            delist = lastseg.kind in ("delisting", "gap") and not bool(lastseg["continues"])
            assert len(sg) == 1 or not delist, f"{coin}: several segments; this checker handles one"
            t1 = int(k.t.to_numpy()[np.flatnonzero(live)[-1]]) + 1
            val = float(lastseg.vwap_last_full_day) * 0.70 if delist else np.nan
            kl = k[live]
            cache[coin] = dict(t=k.t.to_numpy(), o=k.open.to_numpy(), h=k.high.to_numpy(), live=live, elig=elig,
                               lt=kl.t.to_numpy(), lpx=np.column_stack([kl.open, kl.high, kl.low, kl.close]),
                               delist=delist, t1=t1, val=val, kind=lastseg.kind, ticks={})
        Cc = cache[coin]
        t, o, h, live = Cc["t"], Cc["o"], Cc["h"], Cc["live"]
        eb = np.flatnonzero(Cc["elig"])
        et = t[eb]
        m = int(f.t_F1)
        uu = np.random.default_rng(SEED + int(fid)).random(100)
        for ex in exits:
            row = O[(O.fill_id == fid) & (O.exit == ex)].iloc[0]
            if ex == "FLIP":
                span, ratio = 72 * 60, float(row.target) / float(f.L)
            else:
                span, ratio = int(ex[4:]) * 1440, np.inf
            # cut: the largest entry minute whose horizon M(te + span) is at or before the data end
            lo, hi = END_MIN - span - 5 * 1440, END_MIN
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if rule_m(mid + span) <= END_MIN:
                    lo = mid
                else:
                    hi = mid
            cut = lo if rule_m(hi + span) > END_MIN else hi
            kk = np.searchsorted(et, cut, side="right")
            i0 = min(np.searchsorted(et, m - 182 * 1440, side="left"), kk)
            i1 = min(np.searchsorted(et, m + 182 * 1440, side="right"), kk)
            nL, nR = i0, kk - i1
            kidx = np.minimum((uu * (nL + nR)).astype(np.int64), nL + nR - 1)
            bars = np.where(kidx < nL, eb[np.minimum(kidx, len(eb) - 1)], eb[np.minimum(i1 + kidx - nL, len(eb) - 1)])
            te = t[bars]
            rs, kinds, hz = [], [], []
            for b, tt in zip(bars, te):
                entry = o[b]
                S = rule_m(int(tt) + span)
                hz.append(S)
                g = rule_m(int(tt)) if ex == "FLIP" else S
                gi = np.searchsorted(t, g)
                while gi < len(t) and not live[gi]:
                    gi += 1
                if gi >= len(t):
                    rs.append(Cc["val"] * (1 - C) / (entry * (1 + C)) - 1 if Cc["delist"] else np.nan)
                    kinds.append("delist" if Cc["delist"] else "censored")
                    continue
                if t[gi] >= S or ex != "FLIP":
                    si = max(gi, np.searchsorted(t, S))
                    while si < len(t) and not live[si]:
                        si += 1
                    if si >= len(t):
                        rs.append(Cc["val"] * (1 - C) / (entry * (1 + C)) - 1 if Cc["delist"] else np.nan)
                        kinds.append("delist" if Cc["delist"] else "censored")
                    else:
                        rs.append(o[si] * (1 - C) / (entry * (1 + C)) - 1)
                        kinds.append("stop")
                    continue
                T = entry * ratio
                if o[gi] >= T:
                    rs.append(o[gi] * (1 - C) / (entry * (1 + C)) - 1)
                    kinds.append("marketable")
                    continue
                # tick of the coin's most recent Monday 03:30 placement at or before the entry minute
                mon0 = int(pd.Timestamp("2020-01-06 03:30", tz="UTC").value // 60_000_000_000)
                tq = mon0 + ((int(tt) - mon0) // (7 * 1440)) * 7 * 1440
                if tq not in Cc["ticks"]:
                    Cc["ticks"][tq] = tick_for_monday(Cc["lt"], Cc["lpx"], tq)
                tau = Cc["ticks"][tq]
                up = T + tau
                si = max(gi, np.searchsorted(t, S))
                while si < len(t) and not live[si]:
                    si += 1
                seg_h = np.where(live[gi:si], h[gi:si], -np.inf)
                hit = np.flatnonzero(seg_h >= up)
                if len(hit):
                    rs.append(T * (1 - C) / (entry * (1 + C)) - 1)
                    kinds.append("target")
                elif si < len(t):
                    rs.append(o[si] * (1 - C) / (entry * (1 + C)) - 1)
                    kinds.append("stop")
                else:
                    rs.append(Cc["val"] * (1 - C) / (entry * (1 + C)) - 1 if Cc["delist"] else np.nan)
                    kinds.append("delist" if Cc["delist"] else "censored")
            rs = np.array(rs)
            mine = np.nanmean(rs)
            dist_d = np.abs(te - m).min() / 1440
            out.append(dict(fill_id=fid, coin=coin, exit=ex, fill_time=str(pd.Timestamp(m * 60, unit="s", tz="UTC")),
                            pooled=bool(row.twin_pooled), n_left=int(nL), n_right=int(nR),
                            twin_mean_stored=float(row.twin_mean), twin_mean_mine=float(mine),
                            absdiff=abs(float(row.twin_mean) - float(mine)), n_stored=int(row.twin_n),
                            n_mine=int(np.isfinite(rs).sum()), min_days_from_fill=round(float(dist_d), 2),
                            max_horizon_le_end=bool(max(hz) <= END_MIN),
                            first_twin=str(pd.Timestamp(te.min() * 60, unit="s", tz="UTC")),
                            last_twin=str(pd.Timestamp(te.max() * 60, unit="s", tz="UTC")),
                            kinds=pd.Series(kinds).value_counts().to_dict()))
            print(out[-1], flush=True)
    return pd.DataFrame(out)


if __name__ == "__main__":
    run = sys.argv[1]
    fills = [int(x) for x in sys.argv[2].split(",")]
    exits = sys.argv[3].split(",")
    res = main(run, fills, exits)
    res.to_csv(sys.argv[4], index=False)
