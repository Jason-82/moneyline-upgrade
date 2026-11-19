"""F3 (s = 1%) X-FLIP exits of the fills (H1's F3 gate, fills' side), from cached 1m index months: live = updates >= 30
outside Robinhood outage days (+-1 h); go-live = first live minute >= M(t_F3_1); marketable if open x (1 - 0.0095) >= R1/2;
else target when index high >= R1/2 / (1 - 0.0095) (from go-live, inclusive) before the stop; else market sell at
open x (1 - 0.0095) of the first live minute >= M(t + 72 h). r = exit / L - 1. Auditor's own code."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest")
exec(open("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest/s9_f3alert.py").read().split("F = pd.read_parquet")[0])
S = 0.0095
F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["fill_id", "coin", "L", "t_F3_1"])
F = F[F.t_F3_1 >= 0]
O = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["fill_id", "r", "exit_kind", "exit_t", "exit_px", "target", "complete"],
                    filters=[("rule", "==", "F3_1"), ("exit", "==", "FLIP"), ("cost", "==", "RH")])
F = F.merge(O[O.complete], on="fill_id")
rows = []
for coin, g in F.groupby("coin"):
    tf = g.t_F3_1.to_numpy()
    A = rule_m_min(tf); St = rule_m_min(tf + 72 * 60)
    months = set(pd.to_datetime(np.r_[A, St] * 60_000_000_000, utc=True).strftime("%Y-%m"))
    parts = [pd.read_parquet(p, columns=["open_time", "open", "high", "updates"]) for m in sorted(months)
             for p in [f"data/stinkbid/fut1m/index/{coin}/{m}.parquet"] if os.path.exists(p)]
    k = pd.concat(parts).sort_values("open_time")
    t = pd.to_datetime(k.open_time, utc=True).astype("int64").to_numpy() // 60_000_000_000
    ok = k.updates.to_numpy() >= 30
    for a, b in blk:
        ok &= ~((t >= a) & (t < b))
    t, o, h = t[ok], k.open.to_numpy()[ok], k.high.to_numpy()[ok]
    for (_, f), a_t, s_t in zip(g.iterrows(), A, St):
        gi, si = np.searchsorted(t, a_t), np.searchsorted(t, s_t)
        T = f.target
        if o[gi] * (1 - S) >= T:
            kind, et, px = "marketable", t[gi], o[gi] * (1 - S)
        else:
            hh = np.flatnonzero(h[gi:si] >= T / (1 - S))
            kind, et, px = ("target", t[gi + hh[0]], T) if len(hh) else ("stop", t[si], o[si] * (1 - S))
        rows.append(dict(fill_id=f.fill_id, coin=coin, kind=kind, t=int(et), r=px / f.L - 1, kind_f=f.exit_kind, t_f=int(f.exit_t), r_f=f.r))
R = pd.DataFrame(rows)
ok = (R.kind == R.kind_f) & (R.t == R.t_f) & (np.abs(R.r - R.r_f) < 1e-9)
print(f"F3_1 FLIP exits: {len(R)}; matches {int(ok.sum())}; mean r mine {R.r.mean():+.5f} file {R.r_f.mean():+.5f}")
print(R[~ok].head(15).to_string())
