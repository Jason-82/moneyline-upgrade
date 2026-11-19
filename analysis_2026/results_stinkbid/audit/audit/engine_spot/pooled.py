"""Exact reconstruction of pooled B-TWIN entries (§10.1: fewer than 182 eligible own days -> twins from all U-Q1
coins' eligible minutes outside +-182 days of tau_f) for a few pooled H1 fills, and their X-FLIP returns. Read-only."""
import gc
import resource
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/engine_spot")
import recompute as rc  # noqa: E402

ROOT, OUT, DAY = rc.ROOT, rc.OUT, rc.DAY
RUN = f"{ROOT}/data/stinkbid/runs/outcomes/P1__U_Q1"


def main(n_pick=3):
    P = np.load(f"{OUT}/pool_tables.npz")
    q1coins = sorted({k.split("__")[0] for k in P.files})
    fill_coins = sorted(pd.read_parquet(f"{RUN}/fills.parquet", columns=["coin"]).coin.unique())
    order = fill_coins + [c for c in q1coins if c not in fill_coins]       # the dict order of the pool tables
    s = pd.read_csv(f"{ROOT}/analysis_2026/results_stinkbid/primary/samples_H1.csv")
    O = pd.read_parquet(f"{RUN}/outcomes.parquet",
                        filters=[("rule", "==", "F1"), ("exit", "==", "FLIP"), ("lat", "==", "M"), ("cost", "==", "C-RH")],
                        columns=["fill_id", "coin", "twin_pooled", "twin_mean", "twin_n", "target", "r", "delta"])
    F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["fill_id", "coin", "t_F1", "L"])
    m = s[["fill_id", "y"]].merge(O, on="fill_id").merge(F, on=["fill_id", "coin"])
    pool = m[m.twin_pooled].sort_values("fill_id")
    rng = np.random.default_rng(7)
    picks = pool.iloc[np.sort(rng.choice(len(pool), size=n_pick, replace=False))]
    # cutoff of a complete X-FLIP window (largest te with M(te + 72 h) <= END)
    lo_c, hi_c = rc.END_MIN - 80 * 60 - 4 * DAY, rc.END_MIN
    while hi_c - lo_c > 1:
        mid = (lo_c + hi_c) // 2
        if rc.rule_m(mid + rc.FLIP_H * 60) <= rc.END_MIN:
            lo_c = mid
        else:
            hi_c = mid
    cut = lo_c
    cut_day = (cut - (DAY - 1)) // DAY
    reqs = []
    for e in picks.itertuples(index=False):
        tau = int(e.t_F1)
        x0 = (tau - 182 * DAY) // DAY
        x1 = (tau + 182 * DAY) // DAY
        parts, cnts = [], []
        for c in order:
            d, k = P[c + "__days"], P[c + "__cnt"]
            ok = (d <= cut_day) & ((d < x0) | (d > x1))
            parts.append((c, d[ok], np.cumsum(k[ok])))
            cnts.append(int(k[ok].sum()))
        N = int(sum(cnts))
        cum = np.cumsum(cnts)
        u = np.random.default_rng(rc.SEED + int(e.fill_id)).random(100)
        for j, uu in enumerate(u):
            r_ = min(int(uu * N), N - 1)
            ci = int(np.searchsorted(cum, r_, side="right"))
            off = r_ - (cum[ci - 1] if ci > 0 else 0)
            c, d, ck = parts[ci]
            di = int(np.searchsorted(ck, off, side="right"))
            rank = off - (ck[di - 1] if di > 0 else 0)
            reqs.append(dict(fill_id=int(e.fill_id), j=j, coin=c, day=int(d[di]), rank=int(rank),
                             ratio=float(e.target) / float(e.L), N=N))
    R = pd.DataFrame(reqs)
    print(R.groupby("fill_id").coin.nunique().to_dict(), "coins per fill; N =", R.groupby("fill_id").N.first().to_dict())
    out = []
    for c, g in R.groupby("coin"):
        cn = rc.Coin(c)
        mon = (cn.t // DAY).astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
        qm = np.array([np.datetime64(x, "M").astype(np.int64) for x in cn.q1_months], np.int64)
        el = np.flatnonzero(cn.live & np.isin(mon, qm))
        eday = cn.t[el] // DAY
        for e in g.itertuples(index=False):
            a = int(np.searchsorted(eday, e.day))
            bi = int(el[a + e.rank])
            assert cn.t[bi] // DAY == e.day
            te = int(cn.t[bi])
            ent = float(cn.o[bi])
            T = ent * e.ratio
            tdec = cn.tick_at_placement(rc.monday_0330_at_or_before(te))["tick_dec"]
            kd, xt, xp, g2, s2 = rc.flip_exit(cn, te, T, T + float(rc.tick_str(tdec)), inclusive=True)
            cross = (s2 < 0) or rc.segs_crossed(cn, bi, s2)
            rr = xp * (1 - rc.C) / (ent * (1 + rc.C)) - 1 if np.isfinite(xp) else np.nan
            out.append(dict(fill_id=e.fill_id, j=e.j, coin=c, entry=rc.mts(te), kind=kd, r=rr, cross=cross))
        del cn, mon, el, eday
        gc.collect()
    X = pd.DataFrame(out)
    X.to_csv(f"{OUT}/pooled_twins.csv", index=False)
    res = X.groupby("fill_id").agg(mine=("r", "mean"), n=("r", "count"), cross=("cross", "sum")).reset_index()
    res = res.merge(picks[["fill_id", "coin", "twin_mean", "twin_n", "r", "delta", "y"]], on="fill_id")
    res["diff"] = (res.mine - res.twin_mean).abs()
    pd.set_option("display.width", 200)
    print(res.to_string())
    print("maxrss MB", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
