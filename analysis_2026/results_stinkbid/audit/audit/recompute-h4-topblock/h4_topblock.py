"""Independent recomputation of H4's single-event / concentration rows (prereg §10.4, S16) on two month-block
partitions: (a) M7's own stacked fills (what the record did), (b) the shared H4 partition (A1.8: month-blocks of the
union of the four methods' stacked fill times). Own code only: stacked frames, FE OLS, episodes and month-blocks are
written here from the prereg's definitions. Reads only the cached H4/U_Q1 engine run (parquet, needed columns)."""
import json
import resource
import sys

import numpy as np
import pandas as pd

D = "data/stinkbid/runs/outcomes/H4__U_Q1/"
OUT = sys.argv[1] if len(sys.argv) > 1 else None
GAP = 3  # §10.2: an episode is a run of fill days at most 3 days apart

# ---------------------------------------------------------------- stacked frames (§10.3 H4)
B = pd.read_parquet(D + "bids.parquet", columns=["variant", "cw", "delta", "real"])
F = pd.read_parquet(D + "fills.parquet", columns=["fill_id", "variant", "cw", "coin", "delta", "real", "t_F1", "shift"])
O = pd.read_parquet(D + "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "delta", "complete"])
O = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & (O.lat == "M") & (O.complete == True)]
assert O.fill_id.is_unique
rb = B[B.real.astype(bool)]
dup = rb.duplicated(["variant", "cw"]).sum()
print("real bids per (variant, cw) duplicated:", int(dup))
rb = rb[["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
f = F[F.t_F1 >= 0].merge(O[["fill_id", "delta"]].rename(columns={"delta": "y"}), on="fill_id", how="inner")
f = f.merge(rb, on=["variant", "cw"], how="left")
f = f[np.isfinite(f.y.to_numpy(float)) & np.isfinite(f.delta_real.to_numpy(float))].copy()
f["depth"] = f.delta - f.delta_real
f["time"] = pd.to_datetime(f.t_F1.to_numpy(np.int64) * 60, unit="s", utc=True)
f["method"] = f.variant.map(lambda v: v.split(" ")[0])
f = f.sort_values(["method", "fill_id"]).reset_index(drop=True)
print("stacked rows per method:", f.groupby("method").size().to_dict())


# ---------------------------------------------------------------- FE OLS: y = a_cw + b real + c depth + e
def fe_b(g: pd.DataFrame, mask=None) -> tuple:
    g = g if mask is None else g[np.asarray(mask, bool)]
    k = g.groupby("cw")["y"].transform("size").to_numpy()
    g = g[k > 1]                                    # coin-weeks with one stacked fill drop out (A1.8)
    if not len(g):
        return np.nan, 0
    Z = g[["y", "real", "depth"]].astype(float)
    Zd = Z - Z.groupby(g["cw"].to_numpy()).transform("mean")
    X = Zd[["real", "depth"]].to_numpy()
    yv = Zd["y"].to_numpy()
    coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
    return float(coef[0]), len(g)


# ---------------------------------------------------------------- episodes and month-blocks (§10.2)
def episodes(t: pd.Series) -> np.ndarray:
    d = t.dt.floor("D").to_numpy().astype("datetime64[D]")
    u = np.unique(d)
    new = np.r_[True, np.diff(u).astype(np.int64) > GAP]
    eu = np.cumsum(new) - 1
    return eu[np.searchsorted(u, d)]


def month_blocks(t: pd.Series) -> tuple:
    """Months of the fills merged (transitively) when one episode has fills in two of them. Returns (labels, names):
    labels are YYYY-MM of the block's first month, names the '+'-joined months."""
    ep = episodes(t)
    mo = (t.dt.year * 12 + t.dt.month - 1).to_numpy()
    parent = {int(m): int(m) for m in np.unique(mo)}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e in np.unique(ep):
        ms = sorted(set(mo[ep == e].tolist()))
        for a, b in zip(ms[:-1], ms[1:]):
            ra, rb_ = find(a), find(b)
            if ra != rb_:
                parent[max(ra, rb_)] = min(ra, rb_)
    root = np.array([find(int(m)) for m in mo])
    members = {}
    for m in np.unique(mo):
        members.setdefault(find(int(m)), []).append(int(m))
    nm = {r: "+".join(f"{x // 12}-{x % 12 + 1:02d}" for x in sorted(ms)) for r, ms in members.items()}
    return root, nm, ep


def top_block(labels: np.ndarray):
    u, c = np.unique(labels, return_counts=True)
    o = np.lexsort((u, -c))                         # most fills; ties: the earliest
    return u[o[0]], dict(zip(u.tolist(), c.tolist()))


def ep_name(t: pd.Series, ep: np.ndarray, e) -> str:
    d = t[ep == e].dt.strftime("%Y-%m-%d")
    a, b = d.min(), d.max()
    return a if a == b else f"{a}..{b}"


res = {}
M7 = f[f.method == "M7"].reset_index(drop=True)
b_all, n_all = fe_b(M7)
print(f"M7 b = {b_all:.10f}  n fitted = {n_all}  (record 0.0023467465761791, n 1487)")
res["b_all"], res["n_fitted"] = b_all, n_all
for m in ("M4", "M5b", "M6"):
    bm, nm_ = fe_b(f[f.method == m])
    print(f"  {m}: b = {bm:.10f}, n = {nm_}")

# fitted-row mask of M7 (singletons dropped on the full sample)
k_full = M7.groupby("cw")["y"].transform("size").to_numpy()
fitted = k_full > 1

# events not depending on the partition
for day in ("2025-10-10", "2021-05-19"):
    m = M7.time.dt.strftime("%Y-%m-%d").to_numpy() != day
    bb, nn = fe_b(M7, m)
    print(f"without {day}: b = {bb:.10f} (rows on that day {int((~m).sum())})")
    res[f"without_{day}"] = bb

# (a) own partition: M7's stacked fill times (all frame rows)
mb_own, nm_own, ep_own = month_blocks(M7.time)
# (b) shared partition: the union of the four methods' stacked fill times (all frame rows)
mb_u, nm_u, ep_u = month_blocks(f.time)
f["mb_u"], f["ep_u"] = mb_u, ep_u
mb_sh = f.loc[f.method == "M7", "mb_u"].to_numpy()
ep_sh = f.loc[f.method == "M7", "ep_u"].to_numpy()
print(f"own partition: {len(np.unique(mb_own))} blocks over M7's fills; shared: {len(np.unique(mb_u))} blocks over the "
      f"union ({len(np.unique(mb_sh))} hold M7 fills)")
res["G_own_blocks"] = int(len(np.unique(mb_own)))
res["G_union_blocks"] = int(len(np.unique(mb_u)))
res["G_union_blocks_with_M7"] = int(len(np.unique(mb_sh)))

for tag, mb, nm, basis in (("own_all", mb_own, nm_own, np.ones(len(M7), bool)),
                           ("own_fitted", mb_own, nm_own, fitted),
                           ("shared_all", mb_sh, nm_u, np.ones(len(M7), bool)),
                           ("shared_fitted", mb_sh, nm_u, fitted)):
    tb, cnt = top_block(mb[basis])
    bb, nn = fe_b(M7, mb != tb)
    srt = sorted(cnt.items(), key=lambda kv: -kv[1])[:4]
    print(f"[{tag}] top block {nm[tb]} ({cnt[tb]} M7 fills on this basis; {int((mb == tb).sum())} M7 frame rows); "
          f"b without = {bb:.10f} (n {nn}); next: " + ", ".join(f"{nm[k]}:{v}" for k, v in srt[1:]))
    res[f"topblock_{tag}"] = dict(block=nm[tb], n_basis=int(cnt[tb]), n_rows=int((mb == tb).sum()),
                                  b_without=bb, n_fit_without=nn)

# shared partition: which months merged around 2025-07..10
print("shared partition blocks in 2025:", sorted({v for v in nm_u.values() if "2025" in v}))
print("own partition blocks in 2025:", sorted({v for v in nm_own.values() if "2025" in v}))
print("own partition blocks in 2023:", sorted({v for v in nm_own.values() if "2023" in v}))

# top-3 episodes (concentration, S16; coding choice 2 of desc: share of fills, coefficient re-fitted without them)
for tag, ep in (("own", ep_own), ("shared", ep_sh)):
    for basis_tag, basis in (("all", np.ones(len(M7), bool)), ("fitted", fitted)):
        u, c = np.unique(ep[basis], return_counts=True)
        o = np.lexsort((u, -c))
        top = u[o[:3]]
        sel = np.isin(ep, top)
        share = float(sel[basis].mean())
        bb, nn = fe_b(M7, ~sel)
        names = [ep_name(M7.time, ep, e) for e in top]
        print(f"[episodes {tag}/{basis_tag}] top3 {names} share {share:.6f}; b without = {bb:.10f}")
        res[f"top3_{tag}_{basis_tag}"] = dict(names=names, share=share, b_without=bb)

res["maxrss_MB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print("maxrss MB", res["maxrss_MB"])
if OUT:
    json.dump(res, open(OUT, "w"), indent=1, default=str)
