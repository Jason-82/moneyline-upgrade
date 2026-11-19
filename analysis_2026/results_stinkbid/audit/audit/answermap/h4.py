import sys, numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/answermap")
from core import ts, month_blocks
RUN = "/home/user/moneyline-upgrade/data/stinkbid/runs/outcomes/H4__U_Q1"
F = pd.read_parquet(RUN + "/fills.parquet", columns=["fill_id", "coin", "method", "real", "shift", "cw", "delta", "t_F1", "t_F3_1"])
O = pd.read_parquet(RUN + "/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "delta", "complete"])
print(F.method.value_counts().to_dict())
o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & O.complete.astype(bool)][["fill_id", "delta"]].rename(columns={"delta": "y"})
d = F[F.t_F1 >= 0].merge(o, on="fill_id")
d = d[np.isfinite(d.y)]
# union partition of month-blocks over all four methods' stacked fills (one partition shared by the methods)
meths = ["M4", "M5b", "M6", "M7"]
print("methods present:", sorted(d.method.unique()))
for m in meths:
    g = d[d.method.astype(str).str.startswith(m)] if m != "M4" else d[d.method.astype(str) == "M4"]
    print(m, "rows", len(g), "methods", g.method.unique()[:5])
from fixed import ols_cr1
# union month-block partition over all methods' stacked fill times
d = d.reset_index(drop=True)
d["time"] = ts(d.t_F1)
mb_all, _ = month_blocks(d["time"])
d["mb"] = mb_all
for m in meths:
    g = d[d.method.astype(str) == m].copy()
    vc = g.cw.value_counts()
    g = g[g.cw.map(vc) > 1].reset_index(drop=True)
    X = np.column_stack([g.real.astype(float).to_numpy(), g.delta.astype(float).to_numpy()])
    r = ols_cr1(g.y.to_numpy(float), X, g.mb.to_numpy(), fe=g.cw.to_numpy(), j=0)
    print(m, "n", len(g), "n_cw", g.cw.nunique(), "G", r["G"], "G* %.4f" % r["gstar"], "b %.7f se %.7f t %.4f" % (r["b"], r["se"], r["b"] / r["se"]))
    if m == "M7":
        hf = (g["time"] >= pd.Timestamp("2023-01-01", tz="UTC")).to_numpy()
        for h in (0, 1):
            gg = g[hf == h]
            vc2 = gg.cw.value_counts(); gg = gg[gg.cw.map(vc2) > 1]
            X2 = np.column_stack([gg.real.astype(float).to_numpy(), gg.delta.astype(float).to_numpy()])
            r2 = ols_cr1(gg.y.to_numpy(float), X2, gg.mb.to_numpy(), fe=gg.cw.to_numpy(), j=0)
            print("   M7 half", h + 1, "n", len(gg), "b %.5f" % r2["b"])
