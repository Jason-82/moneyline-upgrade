"""D-H3 primary (fast s24>=0.75 vs slow s24<0.5, X-FLIP, rung dummies, episode fixed effects) on F1 and F3_1,
own code: within-episode demeaning OLS, singleton episodes dropped."""
import numpy as np, pandas as pd
BASE = "data/stinkbid/runs/outcomes/P1__U_Q1/"
DAY = 1440
F = pd.read_parquet(BASE + "fills.parquet", columns=["fill_id", "rung", "t_F1", "t_F3_1", "s24"])
O = pd.read_parquet(BASE + "outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "delta", "complete"],
                    filters=[("rule", "in", ["F1", "F3_1"]), ("exit", "==", "FLIP")])

def episodes(tmin):
    d = np.asarray(tmin, np.int64) // DAY
    u = np.unique(d); new = np.r_[True, np.diff(u) > 3]
    return (np.cumsum(new) - 1)[np.searchsorted(u, d)]

for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    t = "t_" + rule
    o = O[(O.rule == rule) & (O.cost == cost) & O.complete.astype(bool)][["fill_id", "delta"]]
    d = F[F[t] >= 0].merge(o, on="fill_id")
    d = d[np.isfinite(d.delta)].reset_index(drop=True)
    d["ep"] = episodes(d[t])                      # episodes of the analysed sample's own fill times
    s = d.s24.to_numpy(float)
    g = d[(s >= 0.75) | (s < 0.5)].reset_index(drop=True)
    g = g[g.groupby("ep").ep.transform("size") > 1].reset_index(drop=True)   # singletons carry no information
    fast = (g.s24 >= 0.75).astype(float).to_numpy()
    rungs = sorted(g.rung.unique())
    X = np.column_stack([fast] + [(g.rung == r).astype(float).to_numpy() for r in rungs[1:]])
    y = g.delta.to_numpy(float)
    def dm(a):
        a = pd.DataFrame(a); return (a - a.groupby(g.ep.to_numpy()).transform("mean")).to_numpy()
    Xd, yd = dm(X), dm(y).ravel()
    b = np.linalg.lstsq(Xd, yd, rcond=None)[0]
    print(f"{rule:5s} n={len(g)} fast={int(fast.sum())} slow={int((1-fast).sum())} episodes={g.ep.nunique()} "
          f"b_fast={100*b[0]:+.3f}%")
