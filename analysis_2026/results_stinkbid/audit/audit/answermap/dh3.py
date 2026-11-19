import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/answermap")
from core import ts, month_blocks, RUNS
from fixed import ols_cr1
from scipy import stats
run = RUNS + "/P1__U_Q1"
F = pd.read_parquet(run + "/fills.parquet", columns=["fill_id", "t_F1", "rung", "s24"])
O = pd.read_parquet(run + "/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "delta", "complete"])
o2 = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & O.complete.astype(bool)]
f1 = F[F.t_F1 >= 0]
d3 = f1.merge(o2[["fill_id", "delta"]], on="fill_id")
d3 = d3[np.isfinite(d3.delta)].reset_index(drop=True)
d3["time"] = ts(d3.t_F1)
s = d3.s24.to_numpy(float)
g = d3[(s >= 0.75) | (s < 0.5)].reset_index(drop=True)
mb, ep = month_blocks(g["time"])
g["mb"], g["ep"] = mb, ep
vc = g.ep.value_counts()
single = g.ep.map(vc) == 1
print("n before", len(g), "singleton-episode fills", int(single.sum()), "G before", g.mb.nunique())
h = g[~single].reset_index(drop=True)
print("n after", len(h), "G after", h.mb.nunique())
fast = (h.s24.to_numpy(float) >= 0.75).astype(float)
rungs = sorted(h.rung.unique())
R = np.column_stack([(h.rung.to_numpy() == v).astype(float) for v in rungs[1:]])
X = np.column_stack([fast, R])
r = ols_cr1(h.delta, X, h.mb, fe=h.ep, j=0)
print({k: (float(v) if np.isscalar(v) else [float(x) for x in v]) for k, v in r.items()})
# also: episodes where fast is constant (no within variation) -- informative only
