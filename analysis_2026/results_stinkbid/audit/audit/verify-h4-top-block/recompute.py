"""Independent recomputation of H4's single-event rows ("without the top month-block", top-3 episodes) for the
argmax method, under (a) the method's own-fill month-blocks and (b) H4's shared month-block partition (A1.8).
Written from the prereg definitions (§10.2 clusters, §10.3 H4 model). Does not import stinkbid_stats/desc/run."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path("data/stinkbid/runs/outcomes/H4__U_Q1")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
METHODS = {"M4 N=90 buffer=0.5": "M4", "M5b": "M5b", "M6": "M6", "M7": "M7"}
GAP = 3

# ---------------------------------------------------------------- frames (as §10.3 / engine h4_frames define them)
F = pd.read_parquet(RUN / "fills.parquet", columns=["fill_id", "coin", "variant", "cw", "real", "delta", "t_F1"])
O = pd.read_parquet(RUN / "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "delta", "complete"])
Bd = pd.read_parquet(RUN / "bids.parquet", columns=["variant", "cw", "real", "delta"])
o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & (O.complete.astype(bool))][["fill_id", "delta"]]
o = o.rename(columns={"delta": "y"})
f = F[F.t_F1 >= 0].merge(o, on="fill_id", how="inner")
rb = Bd[Bd.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
f = f.merge(rb, on=["variant", "cw"], how="left")
f = f[np.isfinite(f.y.astype(float)) & np.isfinite(f.delta_real.astype(float))].copy()
f["method"] = f.variant.map(METHODS)
f = f[f.method.notna()].copy()
f["time"] = pd.to_datetime(f.t_F1.astype(np.int64) * 60, unit="s", utc=True)
f["depth"] = f.delta.astype(float) - f.delta_real.astype(float)
f["real"] = f.real.astype(bool).astype(float)
print("stacked fills per method:", f.groupby("method").size().to_dict())


# ---------------------------------------------------------------- clusters (§10.2), own implementation
def episodes(times):
    d = times.dt.floor("D").dt.tz_localize(None).values.astype("datetime64[D]")
    u = np.unique(d)
    gaps = np.diff(u).astype(np.int64)
    ep_u = np.concatenate([[0], np.cumsum(gaps > GAP)])
    return pd.Series(ep_u[np.searchsorted(u, d)], index=times.index)


def month_blocks(times):
    ep = episodes(times)
    mo = times.dt.year * 12 + times.dt.month - 1
    months = sorted(set(mo.tolist()))
    parent = {m: m for m in months}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e, g in mo.groupby(ep):
        ms = sorted(set(g.tolist()))
        for a, b in zip(ms[:-1], ms[1:]):
            ra, rb_ = find(a), find(b)
            if ra != rb_:
                parent[max(ra, rb_)] = min(ra, rb_)
    root = {m: find(m) for m in months}
    roots = sorted(set(root.values()))
    rid = {r: i for i, r in enumerate(roots)}
    lab = {}
    for r in roots:
        ms = [m for m in months if root[m] == r]
        lab[rid[r]] = "+".join(f"{m // 12}-{m % 12 + 1:02d}" for m in ms)
    blk = mo.map(lambda m: rid[root[m]])
    return blk, lab, ep


# ---------------------------------------------------------------- the H4 regression (coin-week FE, singletons dropped)
def fit_b(g):
    g = g[g.groupby("cw")["y"].transform("size") > 1]
    if len(g) < 3:
        return np.nan, 0
    cols = ["y", "real", "depth"]
    dm = g[cols] - g.groupby("cw")[cols].transform("mean")
    X = dm[["real", "depth"]].to_numpy(float)
    y = dm["y"].to_numpy(float)
    if np.linalg.matrix_rank(X) < 2:
        return np.nan, len(g)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    return float(beta[0]), len(g)


res = {}
for m in ("M4", "M5b", "M6", "M7"):
    b, n = fit_b(f[f.method == m])
    res[m] = dict(b=b, n=n)
print("b per method (all fills):", {k: (round(v["b"], 7), v["n"]) for k, v in res.items()})

# shared partition: month-blocks on the union of the four methods' stacked fill times (all rows)
blk_sh, lab_sh, ep_sh = month_blocks(f["time"])
f["mb_shared"] = blk_sh
f["ep_shared"] = ep_sh
print("shared partition: G_union =", len(lab_sh))

m7 = f[f.method == "M7"].copy()
blk_own, lab_own, ep_own = month_blocks(m7["time"])
m7["mb_own"] = blk_own
m7["ep_own"] = ep_own
print("M7 own partition: blocks =", len(lab_own))

# G of M7 on the shared partition after dropping singletons
m7ns = m7[m7.groupby("cw")["y"].transform("size") > 1]
print("M7 non-singleton n =", len(m7ns), "G(shared) =", m7ns.mb_shared.nunique(), "G(own) =", m7ns.mb_own.nunique())


def top(labels):
    c = labels.value_counts()
    c = c[c == c.max()]
    return int(min(c.index)), int(labels.value_counts().max())


out = {}
b_all, _ = fit_b(m7)
out["b_all"] = b_all
# (a) own partition, top = most M7 fills (ties earliest)
tb, n = top(m7.mb_own)
b_a, _ = fit_b(m7[m7.mb_own != tb])
out["own"] = dict(block=tb, label=lab_own[tb], n_fills=n, b_without=b_a)
# (b) shared partition, top = most M7 fills
tb2, n2 = top(m7.mb_shared)
b_b, _ = fit_b(m7[m7.mb_shared != tb2])
out["shared_by_M7"] = dict(block=tb2, label=lab_sh[tb2], n_fills=n2, b_without=b_b)
# (c) shared partition, top = most fills of the union of the four methods
tb3, n3 = top(f.mb_shared)
b_c, _ = fit_b(m7[m7.mb_shared != tb3])
out["shared_by_union"] = dict(block=tb3, label=lab_sh[tb3], n_fills_union=n3,
                              n_fills_M7=int((m7.mb_shared == tb3).sum()), b_without=b_c)
# (d) shared partition, top = most M7 non-singleton fills
tb4, n4 = top(m7ns.mb_shared)
b_d, _ = fit_b(m7[m7.mb_shared != tb4])
out["shared_by_M7_nonsingleton"] = dict(block=tb4, label=lab_sh[tb4], n_fills=n4, b_without=b_d)
# (e) own partition, top by non-singleton count
tb5, n5 = top(m7ns.mb_own)
b_e, _ = fit_b(m7[m7.mb_own != tb5])
out["own_by_nonsingleton"] = dict(block=tb5, label=lab_own[tb5], n_fills=n5, b_without=b_e)

# what does the own top block look like in the shared partition?
own_top_rows = m7[m7.mb_own == tb]
out["own_top_in_shared"] = {lab_sh[int(k)]: int(v) for k, v in own_top_rows.mb_shared.value_counts().items()}
out["shared_top_in_own"] = {lab_own[int(k)]: int(v) for k, v in m7[m7.mb_shared == tb2].mb_own.value_counts().sort_index().items()}

# M7 fill counts per shared block (largest 8) and per own block (largest 8)
vc = m7.mb_shared.value_counts().head(8)
out["M7_counts_shared_top8"] = {lab_sh[int(k)]: int(v) for k, v in vc.items()}
vc = m7.mb_own.value_counts().head(8)
out["M7_counts_own_top8"] = {lab_own[int(k)]: int(v) for k, v in vc.items()}
vc = f.mb_shared.value_counts().head(5)
out["union_counts_shared_top5"] = {lab_sh[int(k)]: int(v) for k, v in vc.items()}


# top-3 episodes: own episodes vs the union's episodes
def top3(eplab):
    c = eplab.value_counts()
    u = np.array(c.index)
    cnt = c.to_numpy()
    o_ = np.lexsort((u, -cnt))
    return list(u[o_[:3]])


t3o = top3(m7.ep_own)
sel = m7.ep_own.isin(t3o)
b3o, _ = fit_b(m7[~sel])
t3s = top3(m7.ep_shared)
sel2 = m7.ep_shared.isin(t3s)
b3s, _ = fit_b(m7[~sel2])


def ep_name(df, col, e):
    d = df.loc[df[col] == e, "time"].dt.strftime("%Y-%m-%d")
    return d.min() if d.min() == d.max() else f"{d.min()}..{d.max()}"


out["top3_own"] = dict(names=[ep_name(m7, "ep_own", e) for e in t3o], share=float(sel.mean()), b_without=b3o)
out["top3_shared"] = dict(names=[ep_name(m7, "ep_shared", e) for e in t3s], share=float(sel2.mean()), b_without=b3s)

# worst block (the gate's definition) on both partitions
worst = {}
for col, lab in (("mb_shared", lab_sh), ("mb_own", lab_own)):
    best, which = np.inf, None
    for k in sorted(m7[col].unique()):
        bb, _ = fit_b(m7[m7[col] != k])
        if np.isfinite(bb) and bb < best:
            best, which = bb, k
    worst[col] = dict(block=lab[int(which)], b_without=best)
out["worst_block"] = worst

# primary.json's numbers
P = json.load(open("analysis_2026/results_stinkbid/primary/primary.json"))
out["record"] = {k: P["robust"]["H4"][k] for k in ("estimate", "top_block", "without_top_block", "top3_share",
                                                    "top3_without", "top3_names")}
out["record_G"] = P["rows"]["H4"]["G"]
out["record_G_union"] = P["rows"]["H4"]["G_union"]
print(json.dumps(out, indent=1, default=float))
(OUT / "recompute.json").write_text(json.dumps(out, indent=1, default=float))
