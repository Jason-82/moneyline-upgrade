"""Independent rebuild of H4's per-method stacked regressions (prereg §10.3; A1.8; coding choice 6) from the cached
H4 run on U-Q1, then H4's MDE under the single-test and the Bonferroni critical values, and a power simulation on the
real design (wild cluster DGP with Webb multipliers on the shared month-block partition).

No import of stinkbid_stats / stinkbid_engine / stinkbid_run: only pandas, numpy and scipy on the parquet files.
Output: printed, and saved as JSON next to this script."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RUN = Path("data/stinkbid/runs/outcomes/H4__U_Q1")
OUT = Path(__file__).with_name("h4_rebuild_out.json")
NAMES = {"M4 N=90 buffer=0.5": "M4", "M5b": "M5b", "M6": "M6", "M7": "M7"}

# ---------------------------------------------------------------- frames (my own construction)
F = pd.read_parquet(RUN / "fills.parquet", columns=["fill_id", "coin", "variant", "real", "cw", "delta", "t_F1"])
O = pd.read_parquet(RUN / "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "delta", "complete"])
Bd = pd.read_parquet(RUN / "bids.parquet", columns=["variant", "cw", "real", "delta"])

o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & (O["complete"] == True)]  # noqa: E712
assert set(o.lat.unique()) == {"M"}, o.lat.unique()
assert o.fill_id.is_unique
o = o[["fill_id", "delta"]].rename(columns={"delta": "y"})
f = F[F.t_F1 >= 0].merge(o, on="fill_id", how="inner")
dr = Bd[Bd.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
assert not dr.duplicated(["variant", "cw"]).any()
f = f.merge(dr, on=["variant", "cw"], how="left")
f = f[np.isfinite(f.y.to_numpy(float)) & np.isfinite(f.delta_real.to_numpy(float))]
f["method"] = f.variant.map(NAMES)
f = f[f.method.notna()].reset_index(drop=True)
f["depth"] = f.delta - f.delta_real
f["time"] = pd.to_datetime(f.t_F1.astype("int64") * 60, unit="s", utc=True)

# ---------------------------------------------------------------- month-blocks on the union of all methods' fills
day = f.time.dt.floor("D").to_numpy().astype("datetime64[D]")
ud = np.unique(day)
ep_u = np.cumsum(np.r_[True, np.diff(ud).astype(np.int64) > 3]) - 1          # runs of fill days <= 3 days apart
ep = ep_u[np.searchsorted(ud, day)]
mon = f.time.dt.year.to_numpy() * 12 + f.time.dt.month.to_numpy() - 1
parent = {m: m for m in np.unique(mon)}


def find(x):
    while parent[x] != x:
        x = parent[x]
    return x


for e in np.unique(ep):
    ms = np.unique(mon[ep == e])
    for a, b in zip(ms[:-1], ms[1:]):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
f["mb"] = [find(m) for m in mon]
print(f"stacked fills (all methods): {len(f)}; episodes {len(np.unique(ep))}; month-blocks {f.mb.nunique()} "
      f"(from {len(np.unique(mon))} months)")


# ---------------------------------------------------------------- per-method FE regression with CR1
def design(g):
    g = g[g.groupby("cw").cw.transform("size") > 1].reset_index(drop=True)          # singleton coin-weeks drop out
    cw = pd.factorize(g.cw)[0]
    cl = pd.factorize(g.mb)[0]
    nfe, G = cw.max() + 1, cl.max() + 1

    def within(v):
        return v - (np.bincount(cw, weights=v, minlength=nfe) / np.bincount(cw, minlength=nfe))[cw]
    Z = np.column_stack([within(g.real.astype(float).to_numpy()), within(g.depth.to_numpy(float))])
    Qi = np.linalg.inv(Z.T @ Z)
    return dict(g=g, cw=cw, cl=cl, G=G, nfe=nfe, Z=Z, Qi=Qi, within=within,
                sizes=np.bincount(cl, minlength=G).astype(float))


def fit(d, y):
    yt = d["within"](y)
    th = d["Qi"] @ (d["Z"].T @ yt)
    e = yt - d["Z"] @ th
    sc = np.column_stack([np.bincount(d["cl"], weights=d["Z"][:, k] * e, minlength=d["G"]) for k in range(2)])
    eta = sc @ d["Qi"][0]
    se = np.sqrt(d["G"] / (d["G"] - 1) * (eta @ eta))
    return th, se, e


res, D = {}, {}
tab = pd.read_csv("analysis_2026/results_stinkbid/primary/h4_methods.csv").set_index("method")
for m in ("M4", "M5b", "M6", "M7"):
    d = design(f[f.method == m])
    th, se, e = fit(d, d["g"].y.to_numpy(float))
    n = d["sizes"]
    gs = float((n ** 2).sum() ** 2 / (n ** 4).sum())
    df = gs - 1
    t = th[0] / se
    c3, c12 = stats.t.ppf(1 - 0.05 / 3, df), stats.t.ppf(1 - 0.05 / 12, df)
    c4 = stats.t.ppf(1 - 0.05 / 4, df)
    q80 = stats.t.ppf(0.80, df)
    res[m] = dict(n=len(d["g"]), n_cw=int(d["nfe"]), G=int(d["G"]), gstar=gs, b=float(th[0]), c=float(th[1]),
                  se=float(se), t=float(t), p_t=float(stats.t.sf(t, df)),
                  mde_single=float((c3 + q80) * se), mde_bonf=float((c12 + q80) * se),
                  mde_bonf_at_05=float((c4 + q80) * se), crit_single=float(c3), crit_bonf=float(c12),
                  crit_bonf_05=float(c4), q80=float(q80))
    D[m] = d
    r = tab.loc[m]
    print(f"{m}: n {res[m]['n']} (file {r.n}), cw {res[m]['n_cw']} (file {r.n_cw}), G {res[m]['G']} (file {r.G}), "
          f"G* {gs:.4f} (file {r.gstar:.4f}), b {th[0]:.6f} (file {r.b:.6f}), se {se:.6f} (file {r.se:.6f}), "
          f"t {t:.4f}; MDE single {res[m]['mde_single']:.5f} (file {r.mde:.5f}), Bonferroni "
          f"{res[m]['mde_bonf']:.5f} (file {r.mde_bonf:.5f}), Bonferroni at 0.05 {res[m]['mde_bonf_at_05']:.5f}")

# argmax and the decisive Bonferroni p, as §10.3 states it
am = max(res, key=lambda k: res[k]["t"])
p_g = min(1.0, 4 * res[am]["p_t"])
print(f"argmax {am}: T = {res[am]['t']:.4f}, p_G* = 4 x {res[am]['p_t']:.4f} = {p_g:.4f}")

# ---------------------------------------------------------------- power on the real design (H4's p_G* rule)
# DGP: y* = FE + c_j depth (b_j = 0 imposed) + delta_j real + u_r * w_g, Webb multipliers w_g per month-block shared
# by the four methods (the real test shares its partition). Decision: T = max_j t_j, p_G* = 4 * sf_t(T, G*_am - 1);
# H4 rejects only if p_G* < level (and p_WCR < level too), so P(p_G* < level) bounds H4's power from above.
WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])
allmb = np.unique(f.mb)
for m in D:
    d = D[m]
    g = d["g"]
    y = g.y.to_numpy(float)
    # restricted fit (b = 0): regress within(y) on within(depth) only
    yt = d["within"](y)
    zd = d["Z"][:, 1]
    c0 = (zd @ yt) / (zd @ zd)
    ur = yt - c0 * zd                                   # restricted residuals (FE absorbed)
    d.update(c0=c0, ur=ur, mbpos=np.searchsorted(allmb, g.mb.to_numpy()), real=g.real.astype(float).to_numpy())

rng = np.random.default_rng(20261119)
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
gs = {m: res[m]["gstar"] for m in D}
settings = [("null", {}), ("M7 only = printed MDE", {"M7": res["M7"]["mde_single"]}),
            ("M7 only = 1% (E)", {"M7": 0.01}), ("M7 only = mde_bonf", {"M7": res["M7"]["mde_bonf"]}),
            ("M4 only = 1%", {"M4": 0.01}),
            ("all four = printed MDE", {m: res["M7"]["mde_single"] for m in D}),
            ("all four = 1%", {m: 0.01 for m in D})]
power = {}
for name, eff in settings:
    W = rng.choice(WEBB, size=(REPS, len(allmb)))
    T = np.full((REPS, 4), np.nan)
    for j, m in enumerate(D):
        d = D[m]
        base = d["c0"] * d["Z"][:, 1] + eff.get(m, 0.0) * d["Z"][:, 0]
        for r in range(REPS):
            u = d["ur"] * W[r, d["mbpos"]]
            ys = base + d["within"](u)                  # within(y*) = c0 Zd + delta Zr + within(u_r w)
            th = d["Qi"] @ (d["Z"].T @ ys)
            e = ys - d["Z"] @ th
            sc = np.column_stack([np.bincount(d["cl"], weights=d["Z"][:, k] * e, minlength=d["G"]) for k in range(2)])
            eta = sc @ d["Qi"][0]
            T[r, j] = th[0] / np.sqrt(d["G"] / (d["G"] - 1) * (eta @ eta))
    names = list(D)
    jm = np.nanargmax(T, axis=1)
    Tm = T[np.arange(REPS), jm]
    dfm = np.array([gs[names[k]] - 1 for k in jm])
    pg = np.minimum(1.0, 4 * stats.t.sf(Tm, dfm))
    m7 = names.index("M7")
    p7 = stats.t.sf(T[:, m7], gs["M7"] - 1)
    power[name] = dict(bonf_at_05_3=float(np.mean(pg < 0.05 / 3)), bonf_at_05=float(np.mean(pg < 0.05)),
                       single_M7_at_05_3=float(np.mean(p7 < 0.05 / 3)), reps=REPS)
    print(f"{name:28s} P(p_G* < 0.05/3) = {power[name]['bonf_at_05_3']:.3f}; P(p_G* < 0.05) = "
          f"{power[name]['bonf_at_05']:.3f}; single-test M7 t-test at 0.05/3: {power[name]['single_M7_at_05_3']:.3f}"
          f"  (n = {REPS})")

json.dump(dict(methods=res, argmax=am, p_gstar=p_g, power=power), open(OUT, "w"), indent=1)
print("saved", OUT)
