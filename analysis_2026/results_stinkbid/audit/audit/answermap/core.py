"""Independent recomputation of the answer's headline numbers (H1, H2R), gates, beside rows, f3kept,
concentration and single-event numbers, from the cached engine tables. Own code from the prereg's definitions
(§10.2: CR1 with G/(G-1), G* = (sum n_g^2)^2 / sum n_g^4, t with G*-1 df; episodes = runs of fill days <= 3 days
apart; month-blocks = calendar months merged when an episode spans them). Read-only."""
import json
import sys
import numpy as np
import pandas as pd
from scipy import stats

ROOT = "/home/user/moneyline-upgrade"
RUNS = ROOT + "/data/stinkbid/runs/outcomes"
RES = ROOT + "/analysis_2026/results_stinkbid"
MIN_NS = 60_000_000_000


def ts(m):
    return pd.to_datetime(np.asarray(m, np.int64) * MIN_NS, utc=True)


def episodes(t):
    d = pd.DatetimeIndex(t).tz_convert("UTC").tz_localize(None).normalize()
    u = np.array(sorted(set(d.values)))
    gaps = np.diff(u).astype("timedelta64[D]").astype(int) if len(u) > 1 else np.array([], int)
    eid_u = np.r_[0, np.cumsum(gaps > 3)]
    m = dict(zip(u, eid_u))
    return np.array([m[x] for x in d.values])


def month_blocks(t):
    tt = pd.DatetimeIndex(t).tz_convert("UTC").tz_localize(None)
    mo = tt.year * 100 + tt.month
    ep = episodes(t)
    parent = {int(x): int(x) for x in np.unique(mo)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in np.unique(ep):
        ms = sorted(set(mo[ep == e]))
        for a, b in zip(ms[:-1], ms[1:]):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(int(x)) for x in mo]), ep


def quarter_blocks(t):
    tt = pd.DatetimeIndex(t).tz_convert("UTC").tz_localize(None)
    qu = tt.year * 10 + (tt.month - 1) // 3 + 1
    ep = episodes(t)
    parent = {int(x): int(x) for x in np.unique(qu)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in np.unique(ep):
        qs = sorted(set(qu[ep == e]))
        for a, b in zip(qs[:-1], qs[1:]):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(int(x)) for x in qu])


def cr1(y, g):
    y = np.asarray(y, float)
    g = np.asarray(g)
    n = len(y)
    m = y.mean()
    u = y - m
    labs, inv = np.unique(g, return_inverse=True)
    G = len(labs)
    s = np.bincount(inv, weights=u)
    ng = np.bincount(inv).astype(float)
    V = G / (G - 1) * (s ** 2).sum() / n ** 2
    se = np.sqrt(V)
    gstar = (ng ** 2).sum() ** 2 / (ng ** 4).sum()
    df = gstar - 1
    t = m / se
    out = dict(n=n, est=m, se=se, G=G, gstar=gstar, t=t, p_gstar=stats.t.sf(t, df),
               ci_lo=m - stats.t.ppf(0.975, df) * se, ci_hi=m + stats.t.ppf(0.975, df) * se,
               ub_t=m + stats.t.ppf(1 - 0.05 / 3, df) * se,
               mde=(stats.t.ppf(1 - 0.05 / 3, df) + stats.t.ppf(0.80, df)) * se)
    return out


def fmt(d):
    return {k: (round(float(v), 6) if isinstance(v, (float, np.floating)) else v) for k, v in d.items()}


def load(run):
    F = pd.read_parquet(f"{RUNS}/{run}/fills.parquet")
    O = pd.read_parquet(f"{RUNS}/{run}/outcomes.parquet",
                        columns=["rule", "exit", "lat", "cost", "fill_id", "r", "delta", "complete", "exit_t", "exit_px"])
    Bn = pd.read_parquet(f"{RUNS}/{run}/bench.parquet",
                         columns=["fill_id", "rule", "alert_M", "alert_72h", "knife", "twin_knife"])
    return F, O, Bn


def sample_flip(F, O, rule="F1", exit="FLIP", cost="C-RH", value="delta"):
    o = O[(O.rule == rule) & (O.exit == exit) & (O.cost == cost) & (O.complete.astype(bool))]
    cols = ["fill_id", "coin", "rung", "t_" + rule] + (["t_F3_1"] if "t_F3_1" in F and rule != "F3_1" else [])
    f = F[F["t_" + rule] >= 0][cols].rename(columns={"t_" + rule: "tf"})
    if rule == "F3_1":
        f["t_F3_1"] = f["tf"]
    d = f.merge(o[["fill_id", "r", "delta"]], on="fill_id")
    d["y"] = d[value]
    d = d[np.isfinite(d["y"])].reset_index(drop=True)
    d["time"] = ts(d["tf"])
    return d


def sample_bench(F, Bn, rule="F1", col="alert_M"):
    b = Bn[Bn.rule == rule][["fill_id", col]]
    cols = ["fill_id", "coin", "rung", "t_" + rule] + (["t_F3_1"] if "t_F3_1" in F and rule != "F3_1" else [])
    f = F[F["t_" + rule] >= 0][cols].rename(columns={"t_" + rule: "tf"})
    if rule == "F3_1":
        f["t_F3_1"] = f["tf"]
    d = f.merge(b, on="fill_id")
    d["y"] = pd.to_numeric(d[col], errors="coerce")
    d = d[np.isfinite(d["y"])].reset_index(drop=True)
    d["time"] = ts(d["tf"])
    return d


def add_cl(d):
    mb, ep = month_blocks(d["time"])
    d = d.copy()
    d["mb"], d["ep"] = mb, ep
    d["hf"] = (d["time"] >= pd.Timestamp("2023-01-01", tz="UTC")).astype(int)
    d["day"] = d["time"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    return d


def gates(d, ub=None, f3=None, r=None):
    y = d["y"].to_numpy(float)
    g = {}
    if r is not None:
        g["mean_r"] = float(np.mean(r))
    for h in (0, 1):
        g[f"half{h+1}"] = float(y[d["hf"].to_numpy() == h].mean())
        g[f"half{h+1}_n"] = int((d["hf"].to_numpy() == h).sum())
    # worst month-block: removal lowers the mean most
    best = (np.inf, None)
    for b in np.unique(d["mb"]):
        m = y[d["mb"].to_numpy() != b].mean()
        if m < best[0]:
            best = (m, b)
    g["no_worst_block"] = float(best[0])
    g["worst_block"] = int(best[1])
    # biggest episode: most fills (ties earliest)
    vc = pd.Series(d["ep"]).value_counts()
    top = sorted(vc[vc == vc.max()].index)[0]
    g["no_biggest_episode"] = float(y[d["ep"].to_numpy() != top].mean())
    g["biggest_episode_n"] = int(vc.max())
    g["biggest_episode_dates"] = (str(d.loc[d.ep == top, "day"].min().date()), str(d.loc[d.ep == top, "day"].max().date()))
    if ub is not None:
        g["u_b"] = float(ub["y"].mean())
        g["u_b_n"] = len(ub)
    if f3 is not None:
        g["f3"] = float(f3["y"].mean())
        g["f3_n"] = len(f3)
    return g


def robust(d):
    y = d["y"].to_numpy(float)
    vc = pd.Series(d["ep"]).value_counts()
    order = sorted(vc.index, key=lambda e: (-vc[e], e))
    top3 = order[:3]
    sel = np.isin(d["ep"], top3)
    names = []
    for e in top3:
        dd = d.loc[d.ep == e, "day"]
        a, b = str(dd.min().date()), str(dd.max().date())
        names.append(a if a == b else f"{a}..{b}")
    out = dict(top3_share=float(y[sel].sum() / y.sum()), top3_without=float(y[~sel].mean()), top3_names=names,
               top3_n=[int(vc[e]) for e in top3])
    for day in ("2025-10-10", "2021-05-19"):
        m = d["day"] != pd.Timestamp(day)
        out[f"without_{day}"] = float(y[m.to_numpy()].mean())
        out[f"n_{day}"] = int((~m).sum())
    vb = pd.Series(d["mb"]).value_counts()
    tb = sorted(vb[vb == vb.max()].index)[0]
    out["top_block"] = int(tb)
    out["top_block_n"] = int(vb.max())
    out["without_top_block"] = float(y[d["mb"].to_numpy() != tb].mean())
    return out


def main():
    P = json.load(open(RES + "/primary/primary.json"))
    F, O, Bn = load("P1__U_Q1")
    res = {}
    # ---------------- H1
    d1 = add_cl(sample_flip(F, O))
    s1 = pd.read_csv(RES + "/primary/samples_H1.csv")
    m = d1.merge(s1, on="fill_id", suffixes=("", "_s"))
    res["H1_sample_check"] = dict(n_mine=len(d1), n_file=len(s1), n_join=len(m),
                                  max_abs_y=float(np.abs(m.y - m.y_s).max()), max_abs_r=float(np.abs(m.r - m.r_s).max()),
                                  ep_partition_same=bool(pd.crosstab(m.ep, m.ep_s).astype(bool).sum(axis=1).max() == 1 and
                                                         pd.crosstab(m.ep, m.ep_s).astype(bool).sum(axis=0).max() == 1),
                                  mb_partition_same=bool(pd.crosstab(m.mb, m.mb_s).astype(bool).sum(axis=1).max() == 1 and
                                                         pd.crosstab(m.mb, m.mb_s).astype(bool).sum(axis=0).max() == 1))
    res["H1"] = fmt(cr1(d1["y"], d1["mb"]))
    res["H1"]["mean_r"] = float(d1["r"].mean())
    # U-B and F3 rows for the gates
    Fu, Ou, Bu = load("P1__U_B")
    ub1 = add_cl(sample_flip(Fu, Ou))
    f31 = add_cl(sample_flip(F, O, "F3_1", "FLIP", "RH"))
    res["H1_gates"] = gates(d1, ub1, f31, d1["r"])
    res["H1_robust"] = robust(d1)
    # beside rows
    bes = {}
    for k, (rule, cost) in {"F3_1": ("F3_1", "RH"), "F3d_1": ("F3d_1", "RH"), "F3_3": ("F3_3", "RH")}.items():
        bes[k] = fmt(cr1(*[add_cl(sample_flip(F, O, rule, "FLIP", cost))[c] for c in ("y", "mb")]))
    bes["U_B"] = fmt(cr1(ub1["y"], ub1["mb"]))
    Fc, Oc, Bc = load("P1__U_C")
    uc = add_cl(sample_flip(Fc, Oc))
    bes["U_C"] = fmt(cr1(uc["y"], uc["mb"]))
    uc3 = add_cl(sample_flip(Fc, Oc, "F3_1", "FLIP", "RH"))
    bes["U_C_F3"] = fmt(cr1(uc3["y"], uc3["mb"]))
    res["H1_beside"] = bes
    res["H1_F3_mean_r"] = float(f31["r"].mean())
    res["H1_F3_mean_r_n"] = len(f31)
    # f3kept: F1 sample restricted to fills F3 (s=1%) also fills, re-clustered
    k1 = add_cl(d1[d1["t_F3_1"] >= 0].drop(columns=["mb", "ep", "hf", "day"]).reset_index(drop=True))
    res["H1_f3kept"] = fmt(cr1(k1["y"], k1["mb"]))
    # bot
    db = add_cl(sample_flip(F, O, "F1", "FLIP_bot", "C-RH"))
    res["H1_bot"] = fmt(cr1(db["y"], db["mb"]))
    # ---------------- H2R
    d2 = add_cl(sample_bench(F, Bn))
    s2 = pd.read_csv(RES + "/primary/samples_H2R.csv")
    m2 = d2.merge(s2, on="fill_id", suffixes=("", "_s"))
    res["H2R_sample_check"] = dict(n_mine=len(d2), n_file=len(s2), n_join=len(m2),
                                   max_abs_y=float(np.abs(m2.y - m2.y_s).max()))
    res["H2R"] = fmt(cr1(d2["y"], d2["mb"]))
    ub2 = add_cl(sample_bench(Fu, Bu))
    f32 = add_cl(sample_bench(F, Bn, "F3_1"))
    res["H2R_gates"] = gates(d2, ub2, f32)
    # half-2 detail for H2R
    h2 = d2[d2.hf == 1]
    res["H2R_half2_detail"] = dict(n=len(h2), mean=float(h2.y.mean()))
    h1_ = d2[d2.hf == 0]
    res["H2R_half1_detail"] = dict(n=len(h1_), mean=float(h1_.y.mean()))
    res["H2R_robust"] = robust(d2)
    bes = {}
    for k in ("F3_1", "F3d_1", "F3_3"):
        x = add_cl(sample_bench(F, Bn, k))
        bes[k] = fmt(cr1(x["y"], x["mb"]))
    bes["U_B"] = fmt(cr1(ub2["y"], ub2["mb"]))
    x = add_cl(sample_bench(Fc, Bc))
    bes["U_C"] = fmt(cr1(x["y"], x["mb"]))
    x = add_cl(sample_bench(Fc, Bc, "F3_1"))
    bes["U_C_F3"] = fmt(cr1(x["y"], x["mb"]))
    res["H2R_beside"] = bes
    k2 = add_cl(d2[d2["t_F3_1"] >= 0].drop(columns=["mb", "ep", "hf", "day"]).reset_index(drop=True))
    res["H2R_f3kept"] = fmt(cr1(k2["y"], k2["mb"]))
    # ---------------- Holm on reported p_decide
    p = {"H1": P["rows"]["H1"]["p_decide"], "H2R": P["rows"]["H2R"]["p_decide"], "H4": P["rows"]["H4"]["p_decide"]}
    order = sorted(p, key=lambda k: p[k])
    adj, run, lv = {}, 0.0, {}
    going = True
    rej = {}
    for i, k in enumerate(order):
        run = max(run, (3 - i) * p[k])
        adj[k] = min(1.0, run)
        lv[k] = 0.05 / (3 - i)
        going = going and p[k] < lv[k]
        rej[k] = going
    res["holm"] = dict(p=p, adj=adj, level=lv, rejected=rej)
    json.dump(res, open(sys.argv[1], "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
