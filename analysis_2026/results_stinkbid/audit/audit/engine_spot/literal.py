"""The two fills whose X-FLIP target filled inside the go-live minute: r_f and the own-twin mean under the engine's
reading (the go-live minute counts once its open is below R1/2) and the strictly literal one (from the next minute)."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/engine_spot")
import recompute as rc

RUN = f"{rc.ROOT}/data/stinkbid/runs/outcomes/P1__U_Q1"
F = pd.read_parquet(f"{RUN}/fills.parquet", filters=[("fill_id", "in", [39, 489])], columns=["fill_id", "coin", "t_F1", "L", "P0"])
O = pd.read_parquet(f"{RUN}/outcomes.parquet", filters=[("rule", "==", "F1"), ("exit", "==", "FLIP"), ("lat", "==", "M"),
                    ("cost", "==", "C-RH"), ("fill_id", "in", [39, 489])], columns=["fill_id", "r", "twin_mean", "target", "twin_pooled"])
F = F.merge(O, on="fill_id")
lo_c, hi_c = rc.END_MIN - 80 * 60 - 4 * rc.DAY, rc.END_MIN
while hi_c - lo_c > 1:
    mid = (lo_c + hi_c) // 2
    lo_c, hi_c = (mid, hi_c) if rc.rule_m(mid + rc.FLIP_H * 60) <= rc.END_MIN else (lo_c, mid)
cut = lo_c
for e in F.itertuples(index=False):
    cn = rc.Coin(e.coin)
    m, L, T = int(e.t_F1), float(e.L), float(e.target)
    tdec = cn.tick_at_placement(rc.monday_0330_before(m))["tick_dec"]
    from decimal import Decimal
    up = float(Decimal(repr(T)) + Decimal(rc.tick_str(tdec)))
    out = {}
    for incl in (True, False):
        kd, xt, xp, gi, si = rc.flip_exit(cn, m, T, up, inclusive=incl)
        r = xp * (1 - rc.C) / (L * (1 + rc.C)) - 1
        tw = []
        if not e.twin_pooled:
            mon = (cn.t // rc.DAY).astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
            qm = np.array([np.datetime64(x, "M").astype(np.int64) for x in cn.q1_months], np.int64)
            eb = np.flatnonzero(cn.live & np.isin(mon, qm) & (cn.t <= cut))
            left, right = eb[cn.t[eb] < m - 182 * rc.DAY], eb[cn.t[eb] > m + 182 * rc.DAY]
            u = np.random.default_rng(rc.SEED + int(e.fill_id)).random(100)
            kk = np.minimum((u * (len(left) + len(right))).astype(np.int64), len(left) + len(right) - 1)
            for bi in np.r_[left, right][kk]:
                te, ent = int(cn.t[bi]), float(cn.o[bi])
                Tt = ent * T / L
                td = cn.tick_at_placement(rc.monday_0330_at_or_before(te))["tick_dec"]
                k2, x2, p2, _, _ = rc.flip_exit(cn, te, Tt, Tt + float(rc.tick_str(td)), inclusive=incl)
                tw.append(p2 * (1 - rc.C) / (ent * (1 + rc.C)) - 1)
        out[incl] = (kd, rc.mts(xt), xp, r, float(np.mean(tw)) if tw else np.nan)
    print(e.coin, int(e.fill_id), "engine r", e.r, "twin_mean", e.twin_mean)
    for incl, (kd, xt, xp, r, twm) in out.items():
        print("   ", "engine reading " if incl else "literal 'later'", kd, xt, xp, "r", round(r, 6), "own-twin mean", round(twm, 6), "delta", round(r - twm, 6))
    del cn
