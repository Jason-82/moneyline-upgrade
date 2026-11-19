import sys, numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/answermap")
from core import ts, month_blocks, episodes
RUN = "/home/user/moneyline-upgrade/data/stinkbid/runs/outcomes/H4__U_Q1"
F = pd.read_parquet(RUN + "/fills.parquet", columns=["fill_id", "method", "real", "cw", "delta", "t_F1"])
O = pd.read_parquet(RUN + "/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "delta", "complete"])
o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & O.complete.astype(bool)][["fill_id", "delta"]].rename(columns={"delta": "y"})
g = F[(F.t_F1 >= 0) & (F.method == "M7")].merge(o, on="fill_id")
g = g[np.isfinite(g.y)].reset_index(drop=True)
g["time"] = ts(g.t_F1)
mb, ep = month_blocks(g["time"])
g["mb"], g["ep"] = mb, ep
g["day"] = g["time"].dt.tz_localize(None).dt.normalize()

def b_fit(mask):
    h = g[mask]
    vc = h.cw.value_counts(); h = h[h.cw.map(vc) > 1]
    X = np.column_stack([h.real.astype(float), h.delta.astype(float)])
    y = h.y.to_numpy(float)
    df = pd.DataFrame(X); df["y"] = y; df["fe"] = h.cw.to_numpy()
    dm = df.drop(columns="fe") - df.groupby("fe").transform("mean")
    Xd, yd = dm[[0, 1]].to_numpy(), dm["y"].to_numpy()
    return float(np.linalg.lstsq(Xd, yd, rcond=None)[0][0])
n = len(g)
vc = g.ep.value_counts()
top = sorted(vc.index, key=lambda e: (-vc[e], e))[:3]
sel = g.ep.isin(top).to_numpy()
names = [f"{g.loc[g.ep == e, 'day'].min().date()}..{g.loc[g.ep == e, 'day'].max().date()}" for e in top]
vb = g.mb.value_counts(); tb = sorted(vb[vb == vb.max()].index)[0]
print("frame n", n, "full b %.6f" % b_fit(np.ones(n, bool)))
print("top3", names, "share of fills %.4f" % sel.mean(), "without %.6f" % b_fit(~sel))
print("without 2025-10-10 %.6f" % b_fit((g.day != pd.Timestamp("2025-10-10")).to_numpy()))
print("top block", tb, "n", vb.max(), "without %.6f" % b_fit((g.mb != tb).to_numpy()))
