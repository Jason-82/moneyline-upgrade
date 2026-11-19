# Own reconstruction of H4's four stacked regressions (prereg §10.3) from the cached H4__U_Q1 run, to get each method's
# b, CR1 SE, G, G* and the cross-method correlation of the b_j (month-block cluster score sums). Then the power of
# H4's decisive rule p = max(p_RW, 4 p_t(T)) for effects confined to one method or common to all four.
import numpy as np, pandas as pd, json, sys
from scipy import stats

R = "data/stinkbid/runs/outcomes/H4__U_Q1/"
F = pd.read_parquet(R + "fills.parquet", columns=["fill_id", "variant", "real", "cw", "delta", "t_F1"])
O = pd.read_parquet(R + "outcomes.parquet", columns=["rule", "exit", "cost", "complete", "fill_id", "delta"])
B = pd.read_parquet(R + "bids.parquet", columns=["variant", "cw", "delta", "real"])
O = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & (O.complete == True)][["fill_id", "delta"]]
O = O.rename(columns={"delta": "y"})
assert O.fill_id.is_unique
F = F[F.t_F1 >= 0].merge(O, on="fill_id", how="inner")
Br = B[B.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
print("real bids per (variant, cw) unique:", not Br.duplicated(["variant", "cw"]).any())
F = F.merge(Br, on=["variant", "cw"], how="left")
F = F[np.isfinite(F.y.astype(float)) & np.isfinite(F.delta_real.astype(float))].copy()
F["depth"] = F.delta - F.delta_real
F["m"] = F.variant.map(lambda v: v.split()[0])
F["day"] = (F.t_F1 // 1440).astype(np.int64)

# month-blocks on the union of all methods' stacked fills (before the singleton drop): episodes = runs of distinct fill
# days at most 3 days apart; calendar months merged (transitively) when an episode has fills in both
days = F.day.to_numpy()
ud = np.unique(days)
ep_of_day = np.cumsum(np.r_[True, np.diff(ud) > 3]) - 1
ep = ep_of_day[np.searchsorted(ud, days)]
ts = pd.to_datetime(F.t_F1.to_numpy() * 60, unit="s", utc=True)
mon = (ts.year * 12 + ts.month - 1).to_numpy()
parent = {int(x): int(x) for x in np.unique(mon)}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
for e in np.unique(ep):
    ms = np.unique(mon[ep == e])
    for a, b in zip(ms[:-1], ms[1:]):
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
F["cl"] = [find(int(x)) for x in mon]
print("union stacked fills:", len(F), " month-blocks:", F.cl.nunique())

res, psi = {}, {}
for m, g in F.groupby("m"):
    g = g[g.groupby("cw").cw.transform("size") > 1]            # coin-weeks with a single stacked fill drop out
    X = np.column_stack([g.real.astype(float), g.depth.astype(float)])
    y = g.y.to_numpy(float)
    cw = g.cw.to_numpy()
    dfX = pd.DataFrame(X, columns=["r", "d"]); dfX["y"] = y; dfX["cw"] = cw
    W = dfX[["r", "d", "y"]] - dfX.groupby("cw")[["r", "d", "y"]].transform("mean")
    Xt, yt = W[["r", "d"]].to_numpy(), W["y"].to_numpy()
    Q = Xt.T @ Xt
    th = np.linalg.solve(Q, Xt.T @ yt)
    e = yt - Xt @ th
    cl = g.cl.to_numpy()
    S = pd.DataFrame(Xt * e[:, None], columns=["s0", "s1"]).groupby(cl).sum()
    G = len(S)
    Qi = np.linalg.inv(Q)
    V = G / (G - 1) * Qi @ (S.to_numpy().T @ S.to_numpy()) @ Qi
    se = float(np.sqrt(V[0, 0]))
    n_g = pd.Series(cl).value_counts().to_numpy(float)
    gs = float((n_g ** 2).sum() ** 2 / (n_g ** 4).sum())
    res[m] = dict(n=len(g), G=G, gstar=gs, b=float(th[0]), se=se, t=float(th[0] / se))
    psi[m] = pd.Series((S.to_numpy() @ Qi.T)[:, 0], index=S.index)       # influence of b on each month-block

ref = pd.read_csv("analysis_2026/results_stinkbid/primary/h4_methods.csv").set_index("method")
for m, r in res.items():
    q = ref.loc[m]
    print(f"{m}: n {r['n']} [{q.n}]  G {r['G']} [{q.G}]  G* {r['gstar']:.4f} [{q.gstar:.4f}]  b {r['b']*100:.4f}% [{q.b*100:.4f}%]"
          f"  se {r['se']*100:.4f}% [{q.se*100:.4f}%]  t {r['t']:.4f} [{q.t:.4f}]")

P = pd.DataFrame(psi).fillna(0.0)
M = ["M4", "M5b", "M6", "M7"]
C = P[M].T @ P[M]
d = np.sqrt(np.diag(C))
Rm = C / np.outer(d, d)
print("correlation of the b_j across methods (month-block influence sums):")
print(pd.DataFrame(Rm, index=M, columns=M).round(3))
json.dump(dict(res=res, R=Rm.values.tolist()), open(sys.argv[1], "w"))
