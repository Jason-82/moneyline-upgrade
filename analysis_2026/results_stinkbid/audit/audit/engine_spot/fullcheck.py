"""Bulk version of recompute.py over every P1 bid of U-Q1: placement inputs and L (§6.1-6.2), F1 first trade-through
(§7) on raw 1m bars, and for every F1 fill the X-FLIP exit and r_f (§8-§10.2) and the B-ALERT a_f (§10.1). Twins are
not recomputed here (recompute.py rebuilt all 1,400 twins of the 14 spot-checked fills). Read-only."""
import gc
import math
import resource
import sys
from decimal import Decimal

import numpy as np
import pandas as pd

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/engine_spot")
import recompute as rc  # my own helpers (rule M, Coin loader, decimal floor / ceil, flip exit)  # noqa: E402

RUN = f"{rc.ROOT}/data/stinkbid/runs/outcomes/P1__U_Q1"
OUT = rc.OUT
DAY = rc.DAY


def ndec_vec(x: np.ndarray) -> np.ndarray:
    """Decimals of each price: the smallest d with rint(x 10^d) / 10^d == x (a d-decimal string's nearest double)."""
    out = np.full(x.shape, 99, np.int64)
    for d in range(0, 16):
        p = 10.0 ** d
        ok = (np.rint(x * p) / p == x) & (out == 99)
        out[ok] = d
    return out


def week_tick(cn, t0):
    d0 = t0 // DAY - 1
    a = np.searchsorted(cn.t, (d0 - 6) * DAY)
    b = np.searchsorted(cn.t, (d0 + 1) * DAY)
    tr = cn.tr[a:b] > 0
    px = np.concatenate([cn.o[a:b][tr], cn.h[a:b][tr], cn.l[a:b][tr], cn.c[a:b][tr]])
    if not len(px):
        return None
    dec = ndec_vec(px)
    n = len(dec)
    for d in range(0, 16):
        if (dec > d).sum() <= 0.001 * n:
            return d
    return None


def inputs(cn, t0):
    d0 = t0 // DAY - 1
    D = cn.d1
    i = np.flatnonzero(D.day.to_numpy() == d0)
    if not len(i):
        return None
    i = int(i[0])
    sg = int(D.seg.iloc[i])
    days = D.day.to_numpy()
    segs = D.seg.to_numpy()
    cl = D.close.to_numpy(float)
    rets = []
    for j in range(i, i - 30, -1):
        if j - 1 < 0 or segs[j] != sg or segs[j - 1] != sg or days[j] - days[j - 1] != 1:
            break
        rets.append(math.log(cl[j] / cl[j - 1]))
    sig = float(np.std(rets, ddof=1)) if len(rets) >= 25 else float("nan")
    return dict(P0=float(cl[i]), sigma30=sig, n_ret=len(rets), seg=sg, tick_dec=week_tick(cn, t0))


def main(coins):
    B = pd.read_parquet(f"{RUN}/bids.parquet", filters=[("coin", "in", coins)],
                        columns=["bid_id", "coin", "t0", "rung", "P0", "sigma30", "tick_str", "L", "L_tau", "seg",
                                 "live_from", "life_end", "month"])
    F = pd.read_parquet(f"{RUN}/fills.parquet", filters=[("coin", "in", coins)],
                        columns=["bid_id", "fill_id", "coin", "t_F1", "gap_through"])
    O = pd.read_parquet(f"{RUN}/outcomes.parquet",
                        filters=[("coin", "in", coins), ("rule", "==", "F1"), ("exit", "==", "FLIP"),
                                 ("lat", "==", "M"), ("cost", "==", "C-RH")],
                        columns=["fill_id", "r", "exit_kind", "exit_t", "exit_px", "target", "complete", "delta"])
    Bn = pd.read_parquet(f"{RUN}/bench.parquet", filters=[("coin", "in", coins), ("rule", "==", "F1")],
                         columns=["fill_id", "alert_M", "alert_t_M", "alert_px_M"])
    S1 = pd.read_csv(f"{rc.ROOT}/analysis_2026/results_stinkbid/primary/samples_H1.csv")
    S2 = pd.read_csv(f"{rc.ROOT}/analysis_2026/results_stinkbid/primary/samples_H2R.csv")
    B = B.merge(F, on=["bid_id", "coin"], how="left")
    B = B.merge(O, on="fill_id", how="left").merge(Bn, on="fill_id", how="left")
    B = B.merge(S1[["fill_id", "y", "r"]].rename(columns={"y": "y_H1", "r": "r_H1"}), on="fill_id", how="left")
    B = B.merge(S2[["fill_id", "y"]].rename(columns={"y": "y_H2R"}), on="fill_id", how="left")
    rows = []
    for coin in coins:
        cn = rc.Coin(coin)
        bc = B[B.coin == coin]
        cache = {}
        last_t = int(cn.t[-1])
        for e in bc.itertuples(index=False):
            t0 = int(e.t0)
            if t0 not in cache:
                cache[t0] = inputs(cn, t0)
            I = cache[t0]
            o = dict(bid_id=int(e.bid_id), coin=coin, t0=t0, rung=float(e.rung))
            if I is None or I["tick_dec"] is None:
                o.update(status="no_inputs")
                rows.append(o)
                continue
            tau = Decimal(rc.tick_str(I["tick_dec"]))
            Ld = rc.dfloor(Decimal(I["P0"] * math.exp(-float(e.rung) * I["sigma30"])), tau)
            L, Lt = float(Ld), float(Ld - tau)
            o.update(P0_ok=I["P0"] == float(e.P0), sig_rel=abs(I["sigma30"] / float(e.sigma30) - 1),
                     tick_ok=rc.tick_str(I["tick_dec"]) == str(e.tick_str), L_ok=L == float(e.L),
                     Lt_ok=Lt == float(e.L_tau), L=L, L_eng=float(e.L))
            # F1 over the bid's life, inside d0's segment
            a = int(np.searchsorted(cn.t, t0 + 1))
            end = min(t0 + 7 * DAY, int(e.life_end))
            b = int(np.searchsorted(cn.t, end))
            ok = cn.live[a:b] & (cn.seg[a:b] == I["seg"]) & (cn.l[a:b] <= Lt)
            # the bid is cancelled at the first bar of another segment (§4.1)
            other = np.flatnonzero((cn.seg[a:b] != I["seg"]) & (cn.seg[a:b] >= 0))
            hit = np.flatnonzero(ok)
            if len(other) and len(hit):
                hit = hit[hit < other[0]]
            m = int(cn.t[a + hit[0]]) if len(hit) else -1
            m_eng = int(e.t_F1) if pd.notna(e.t_F1) else -1
            o.update(m=m, m_eng=m_eng, fill_ok=m == m_eng, life_end_ok=int(e.life_end) == t0 + 7 * 1440 or
                     int(e.life_end) == rc.END_MIN + 1)
            if m >= 0 and m == m_eng:
                fi = a + hit[0]
                R = rc.dceil((Decimal(repr(L)) + Decimal(repr(I["P0"]))) / 2, tau)
                Rf, up = float(R), float(R + tau)
                S = rc.rule_m(m + rc.FLIP_H * 60)
                beyond = S > last_t
                kind, et, epx, gi, si = rc.flip_exit(cn, m, Rf, up, inclusive=True)
                kind2, et2, epx2, _, _ = rc.flip_exit(cn, m, Rf, up, inclusive=False)
                r = epx * (1 - rc.C) / (L * (1 + rc.C)) - 1
                cross = rc.segs_crossed(cn, int(fi), si) if si >= 0 else True
                complete = S <= rc.END_MIN
                ai = cn.first_live(int(np.searchsorted(cn.t, rc.rule_m(m))))
                a_f = float(cn.o[ai]) / L - 1 if ai >= 0 else np.nan
                o.update(fill_id=int(e.fill_id), R_ok=Rf == float(e.target), kind=kind, kind_eng=e.exit_kind,
                         exit_t=et, exit_t_eng=int(e.exit_t), exit_px=epx, exit_px_eng=float(e.exit_px), r=r,
                         r_eng=float(e.r), r_diff=abs(r - float(e.r)) if np.isfinite(r) else np.nan,
                         r_literal_diff=abs((epx2 * (1 - rc.C) / (L * (1 + rc.C)) - 1) - r)
                         if np.isfinite(epx2) else np.nan, kind_literal=kind2,
                         complete=complete, complete_eng=bool(e.complete), cross=cross, beyond=beyond,
                         a_f=a_f, a_eng=float(e.alert_M), a_diff=abs(a_f - float(e.alert_M)),
                         alert_t=int(cn.t[ai]) if ai >= 0 else -1, alert_t_eng=int(e.alert_t_M),
                         y_H1=float(e.y_H1) if pd.notna(e.y_H1) else np.nan, r_H1=float(e.r_H1) if pd.notna(e.r_H1)
                         else np.nan, delta_eng=float(e.delta), y_H2R=float(e.y_H2R) if pd.notna(e.y_H2R) else np.nan,
                         gap=bool(cn.h[fi] < L), gap_eng=float(e.gap_through) if pd.notna(e.gap_through) else np.nan)
            rows.append(o)
        print(coin, len(bc), "maxrss MB", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024), flush=True)
        del cn
        gc.collect()
    tag = coins[0] if len(coins) == 1 else f"{coins[0]}_{len(coins)}"
    pd.DataFrame(rows).to_csv(f"{OUT}/full/bids_{tag}.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1].split(","))
