"""Independent re-derivation of H4's per-method b, SE, t, G, G* (prereg §10.3, §10.2) from the cached H4 run, then the
MDE under the single-test (0.05/3) and the Bonferroni-over-4 (0.05/12) critical values. Own code throughout."""
import numpy as np
import pandas as pd
from scipy import stats

D = "data/stinkbid/runs/outcomes/H4__U_Q1/"
NAMES = {"M4 N=90 buffer=0.5": "M4", "M5b": "M5b", "M6": "M6", "M7": "M7"}
F = pd.read_parquet(D + "fills.parquet", columns=["fill_id", "variant", "cw", "coin", "real", "delta", "t_F1"])
O = pd.read_parquet(D + "outcomes.parquet", columns=["rule", "exit", "cost", "lat", "complete", "fill_id", "delta"])
B = pd.read_parquet(D + "bids.parquet", columns=["variant", "cw", "real", "delta"])
O = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & (O.complete == True)][["fill_id", "delta"]]
O = O.rename(columns={"delta": "y"})
F = F[F.t_F1 >= 0].merge(O, on="fill_id", how="inner")
R = B[B.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
assert not R.duplicated(["variant", "cw"]).any()
F = F.merge(R, on=["variant", "cw"], how="left")
F = F[np.isfinite(F.y) & np.isfinite(F.delta_real)].copy()
F["m"] = F.variant.map(NAMES)
F["depth"] = F.delta - F.delta_real
F["t"] = pd.to_datetime(F.t_F1.astype("int64"), unit="m", utc=True)

# month-blocks on the union of all four methods' stacked fills (A1.8: one partition shared by the methods)
day = F.t.dt.floor("D")
ud = np.sort(day.unique())
gaps = np.diff(ud).astype("timedelta64[D]").astype(int) if len(ud) > 1 else np.array([], int)
ep_of_day = dict(zip(ud, np.cumsum(np.r_[True, gaps > 3]) - 1))
F["ep"] = day.map(ep_of_day)
F["mon"] = F.t.dt.year * 12 + F.t.dt.month - 1
par = {m: m for m in F.mon.unique()}
def find(x):
    while par[x] != x:
        par[x] = par[par[x]]
        x = par[x]
    return x
for _, ms in F.groupby("ep").mon:
    u = sorted(set(ms))
    for a, b in zip(u[:-1], u[1:]):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[max(ra, rb)] = min(ra, rb)
F["mb"] = F.mon.map(lambda m: find(m))
print(f"stacked fills {len(F)}; month-blocks in the union {F.mb.nunique()}; months {F.mon.nunique()}")

rows = []
for m in ["M4", "M5b", "M6", "M7"]:
    g = F[F.m == m].copy()
    cnt = g.groupby("cw").cw.transform("size")
    g = g[cnt > 1].copy()                                  # singleton coin-weeks carry no information under the FE
    X = g[["real", "depth"]].astype(float).to_numpy()
    y = g.y.to_numpy(float)
    cw = g.cw.to_numpy()
    def within(v):
        s = pd.Series(v).groupby(cw).transform("mean").to_numpy()
        return v - s
    Z = np.column_stack([within(X[:, 0]), within(X[:, 1])])
    yt = within(y)
    Qi = np.linalg.inv(Z.T @ Z)
    th = Qi @ Z.T @ yt
    e = yt - Z @ th
    cl = g.mb.to_numpy()
    cu, cc = np.unique(cl, return_inverse=True)
    G = len(cu)
    S = np.column_stack([np.bincount(cc, weights=Z[:, a] * e, minlength=G) for a in range(2)])
    V = G / (G - 1) * Qi @ (S.T @ S) @ Qi
    se = float(np.sqrt(V[0, 0]))
    n_g = np.bincount(cc).astype(float)
    gs = float((n_g ** 2).sum() ** 2 / (n_g ** 4).sum())
    df = gs - 1
    t80 = stats.t.ppf(0.8, df)
    rows.append(dict(method=m, n=len(g), n_cw=len(np.unique(cw)), G=G, gstar=gs, b=th[0], se=se, t=th[0] / se,
                     p_t=stats.t.sf(th[0] / se, df), mde_a3=(stats.t.ppf(1 - 0.05 / 3, df) + t80) * se,
                     mde_a12=(stats.t.ppf(1 - 0.05 / 12, df) + t80) * se,
                     mde_a4=(stats.t.ppf(1 - 0.05 / 4, df) + t80) * se))
mine = pd.DataFrame(rows).set_index("method")
rec = pd.read_csv("analysis_2026/results_stinkbid/primary/h4_methods.csv").set_index("method")
pd.set_option("display.width", 250)
print(mine.to_string())
print()
for c, rc in [("n", "n"), ("n_cw", "n_cw"), ("G", "G"), ("gstar", "gstar"), ("b", "b"), ("se", "se"), ("t", "t"),
              ("p_t", "p_t"), ("mde_a3", "mde"), ("mde_a12", "mde_bonf")]:
    print(f"{c:7s} max |mine - record| = {np.max(np.abs(mine[c].to_numpy(float) - rec.loc[mine.index, rc].to_numpy(float))):.3e}")
am = mine.t.idxmax()
print(f"\nargmax by t: {am}; T = {mine.t.max():.4f}; p_G* = min(1, 4 x p_t) = {min(1, 4 * mine.loc[am, 'p_t']):.4f}")
