"""Independent recomputation (own code from the prereg's definitions) of the F1 numbers printed in the answer of
record and of their F3 (s = 1%) counterparts, from the cached engine run P1 on U-Q1.

Definitions used (prereg §10.2, §10.4, §11):
- episode: run of distinct UTC fill days at most 3 days apart;
- month-blocks / quarter-blocks: calendar months / quarters of the fills, merged (transitively) when one episode has
  fills in both;
- G* = (sum n_g^2)^2 / sum n_g^4;
- CR1 SE with factor G/(G-1); 95% interval: union of the t(G*-1) interval and the unrestricted wild bootstrap-t
  interval (Webb six-point weights, B = 9,999) -- the bootstrap draws are my own, so the bootstrap ends are not
  expected to match to the last digit.
Nothing from stinkbid_stats / stinkbid_desc / stinkbid_run is imported. Only stinkbid_data.tbill_daily (a data loader)
is imported for D8 part 2.
"""
import json
import resource
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/home/user/moneyline-upgrade")
BASE = "/home/user/moneyline-upgrade/data/stinkbid/runs/outcomes/P1__U_Q1/"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/f3-beside-skeptic/"
DAY = 1440
B = 9999
WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])
RNG = np.random.default_rng(424242)


# ------------------------------------------------------------------ clusters
def episodes_of(minutes):
    d = np.asarray(minutes, np.int64) // DAY
    u = np.unique(d)
    new = np.r_[True, np.diff(u) > 3]
    ep_u = np.cumsum(new) - 1
    return ep_u[np.searchsorted(u, d)]


def blocks_of(minutes, period):
    m = np.asarray(minutes, np.int64)
    ts = pd.to_datetime(m * 60_000_000_000, utc=True)
    mon = (ts.year.to_numpy() - 1970) * 12 + ts.month.to_numpy() - 1
    per = mon if period == "M" else mon // 3
    ep = episodes_of(m)
    parent = {int(p): int(p) for p in np.unique(per)}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e in np.unique(ep):
        ps = np.unique(per[ep == e])
        for a, b in zip(ps[:-1], ps[1:]):
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(int(p)) for p in per])


def gstar(labels):
    _, n = np.unique(labels, return_counts=True)
    n = n.astype(float)
    return (n ** 2).sum() ** 2 / (n ** 4).sum()


# ------------------------------------------------------------------ estimators
def _within(v, fe):
    if fe is None:
        return v
    df = pd.DataFrame(v)
    return (df - df.groupby(fe).transform("mean")).to_numpy()


def fit(y, X, fe, cl):
    """OLS of y on X (no constant if fe given; X=None -> mean) with absorbed fe; CR1 (G/(G-1)) SE of coef 0."""
    y = np.asarray(y, float)
    if X is None:
        X = np.ones((len(y), 1))
    X = np.asarray(X, float)
    if fe is not None:
        fe = np.asarray(fe)
        cnt = pd.Series(fe).map(pd.Series(fe).value_counts()).to_numpy()
        keep = cnt > 1                                  # singletons drop out under the fixed effect
        y, X, fe, cl = y[keep], X[keep], fe[keep], np.asarray(cl)[keep]
        yt, Xt = _within(y[:, None], fe)[:, 0], _within(X, fe)
    else:
        yt, Xt = y, X
    Q = Xt.T @ Xt
    Qi = np.linalg.pinv(Q)
    th = Qi @ Xt.T @ yt
    e = yt - Xt @ th
    codes, inv = np.unique(cl, return_inverse=True)
    G = len(codes)
    S = np.zeros((G, Xt.shape[1]))
    np.add.at(S, inv, Xt * e[:, None])
    V = G / (G - 1) * Qi @ (S.T @ S) @ Qi
    return dict(th=th, se=float(np.sqrt(V[0, 0])), e=e, Xt=Xt, Qi=Qi, inv=inv, G=G, n=len(yt), cl=cl)


def boot_ci(f):
    """Unrestricted wild cluster bootstrap-t (Webb), coefficient 0; returns the 95% interval."""
    G, inv, Xt, Qi, e = f["G"], f["inv"], f["Xt"], f["Qi"], f["e"]
    W = WEBB[RNG.integers(0, 6, size=(B, G))]
    # y* = Xt th + e * w_g  ->  th* - th = Qi Xt' (e * w_g)
    P = Qi @ Xt.T                                       # k x n
    k = Xt.shape[1]
    # cluster sums of P[:, i] * e_i : (G, k)
    Ce = np.zeros((G, k))
    np.add.at(Ce, inv, (P * e[None, :]).T)
    dth = W @ Ce                                        # B x k
    # residuals of the bootstrap fit: e* = e w - Xt (th* - th); cluster scores Xt' e*
    Se = np.zeros((G, k))
    np.add.at(Se, inv, Xt * e[:, None])                 # sum_i x_i e_i per cluster
    XX = np.zeros((G, k, k))
    np.add.at(XX, inv, Xt[:, :, None] * Xt[:, None, :])  # sum_i x_i x_i' per cluster
    sc = W[:, :, None] * Se[None, :, :] - np.einsum("gkl,bl->bgk", XX, dth)   # B x G x k
    a = Qi[0]                                          # row of Qi for coef 0
    s0 = np.einsum("bgk,k->bg", sc, a)
    se_star = np.sqrt(G / (G - 1) * (s0 ** 2).sum(1))
    tstar = dth[:, 0] / se_star
    th, se = f["th"][0], f["se"]
    return th - np.quantile(tstar, 0.975) * se, th - np.quantile(tstar, 0.025) * se


def row(y, minutes, period="M", X=None, fe=None, boot=True):
    y = np.asarray(y, float)
    minutes = np.asarray(minutes, np.int64)
    ok = np.isfinite(y)
    y, minutes = y[ok], minutes[ok]
    if X is not None:
        X = np.asarray(X, float)[ok]
    if fe is not None:
        fe = np.asarray(fe)[ok]
    cl = blocks_of(minutes, period)
    f = fit(y, X, fe, cl)
    gs = gstar(f["cl"])
    q = stats.t.ppf(0.975, gs - 1)
    est = float(f["th"][0])
    lo_t, hi_t = est - q * f["se"], est + q * f["se"]
    out = dict(estimate=est, n=int(f["n"]), G=int(f["G"]), gstar=float(gs), se=f["se"], ci_t=(lo_t, hi_t))
    if boot:
        lo_b, hi_b = boot_ci(f)
        out.update(ci_boot=(float(lo_b), float(hi_b)), ci=(float(min(lo_t, lo_b)), float(max(hi_t, hi_b))))
    else:
        out["ci"] = (lo_t, hi_t)
    out["mde_80"] = float((stats.t.ppf(1 - 0.05 / 3, gs - 1) + stats.t.ppf(0.8, gs - 1)) * f["se"])
    return out


def fmt(r):
    return (f"{100 * r['estimate']:+.2f}% (95% CI {100 * r['ci'][0]:+.1f}% to {100 * r['ci'][1]:+.1f}%; t-only "
            f"{100 * r['ci_t'][0]:+.1f}..{100 * r['ci_t'][1]:+.1f}; n {r['n']}, G {r['G']}, G* {r['gstar']:.1f})")


# ------------------------------------------------------------------ data
F = pd.read_parquet(BASE + "fills.parquet", columns=["fill_id", "bid_id", "coin", "rung", "variant", "t_F1",
                                                     "t_F3_1", "s24", "ml_d0", "live_from", "life_end"])
O = pd.read_parquet(BASE + "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "r", "delta",
                                                        "complete", "exit_px", "exit_t"],
                    filters=[("rule", "in", ["F1", "F3_1"]), ("exit", "in", ["FLIP", "HOLD90", "TH72"])])
BN = pd.read_parquet(BASE + "bench.parquet", columns=["fill_id", "rule", "alert_M", "alert_72h", "knife",
                                                      "twin_knife"])
BD = pd.read_parquet(BASE + "bids.parquet", columns=["bid_id", "coin", "rung", "variant", "live_from", "life_end"])
res = {}


def sample(rule, exit, cost, value):
    o = O[(O.rule == rule) & (O.exit == exit) & (O.cost == cost) & (O.lat == "M") & O.complete.astype(bool)]
    tcol = "t_" + rule
    f = F[F[tcol] >= 0][["fill_id", tcol, "rung", "s24"]]
    d = f.merge(o[["fill_id", value, "exit_px", "exit_t"]], on="fill_id")
    d = d[np.isfinite(d[value].to_numpy(float))]
    return d.rename(columns={tcol: "t"}).reset_index(drop=True)


# H1 headline and mean r_f (the recommendation's X and R)
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    d = sample(rule, "FLIP", cost, "delta")
    res[f"H1_delta_{rule}"] = row(d["delta"], d["t"])
    d = sample(rule, "FLIP", cost, "r")
    res[f"H1_mean_r_{rule}"] = dict(estimate=float(d["r"].mean()), n=int(len(d)))

# D-H2: X-HOLD-90 Delta against B-TWIN, quarter-block clusters
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    d = sample(rule, "HOLD90", cost, "delta")
    res[f"DH2_{rule}"] = row(d["delta"], d["t"], "Q")

# D-H3: fast (s24 >= 0.75) vs slow (s24 < 0.5), X-FLIP, episode FE + rung dummies, month-block clusters
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    d = sample(rule, "FLIP", cost, "delta")
    s = d["s24"].to_numpy(float)
    g = d[(s >= 0.75) | (s < 0.5)].reset_index(drop=True)
    fast = (g["s24"].to_numpy(float) >= 0.75).astype(float)
    lev = sorted(g["rung"].unique())
    R = np.column_stack([(g["rung"].to_numpy() == v).astype(float) for v in lev[1:]])
    X = np.column_stack([fast, R])
    ep = episodes_of(g["t"].to_numpy(np.int64))
    r = row(g["delta"], g["t"], "M", X=X, fe=ep)
    r.update(n_fast=int(fast.sum()), n_slow=int((1 - fast).sum()), n_sample=int(len(g)))
    res[f"DH3_{rule}"] = r

# D8 part 1: a_f at a 72-hour delay (alert_72h), month-block clusters
for rule in ("F1", "F3_1"):
    tcol = "t_" + rule
    b = BN[BN.rule == rule][["fill_id", "alert_72h"]]
    d = F[F[tcol] >= 0][["fill_id", tcol]].merge(b, on="fill_id")
    y = pd.to_numeric(d["alert_72h"], errors="coerce").to_numpy(float)
    res[f"D8a_{rule}"] = row(y, d[tcol].to_numpy(np.int64))

# D8 part 2: HOLD90 exit price over TH72 exit price, minus T-bill pro rata, quarter-block clusters
from analysis_2026 import stinkbid_data as sbd   # data loader only
for rule, cost in (("F1", "C-0"), ("F3_1", "RH")):
    h = sample(rule, "HOLD90", cost, "r")[["fill_id", "t", "exit_px", "exit_t"]]
    t72 = sample(rule, "TH72", cost, "r")[["fill_id", "exit_px", "exit_t"]].rename(
        columns={"exit_px": "px72", "exit_t": "t72"})
    m = h.merge(t72, on="fill_id")
    m = m[(m.exit_px > 0) & (m.px72 > 0)].reset_index(drop=True)
    days = (m["exit_t"].to_numpy(np.int64) - m["t72"].to_numpy(np.int64)) / DAY
    fd = pd.DatetimeIndex(pd.to_datetime((m["t"].to_numpy(np.int64) // DAY) * DAY * 60_000_000_000, utc=True))
    tb = sbd.tbill_daily(fd).to_numpy(float) / 100.0
    y = m["exit_px"].to_numpy(float) / m["px72"].to_numpy(float) - 1 - tb * days / 365.0
    res[f"D8b_{rule}"] = row(y, m["t"].to_numpy(np.int64), "Q")

# Worst day (TAIL_TOGETHER) under F1 and F3_1: share of live order slots (coin, rung, variant) that filled that day
Bf = BD.merge(F[["bid_id", "t_F1", "t_F3_1"]], on="bid_id", how="left")
slot = Bf.groupby(["coin", "rung", "variant"], sort=False).ngroup().to_numpy()
a = Bf["live_from"].to_numpy(np.int64) // DAY
e = (Bf["life_end"].to_numpy(np.int64) - 1) // DAY
for rule in ("F1", "F3_1"):
    fm = Bf["t_" + rule].fillna(-1).to_numpy(np.int64)
    fd = np.where(fm >= 0, fm // DAY, -1)
    best = None
    rows = []
    for dd in np.unique(fd[fd >= 0]):
        resting = (a <= dd) & (e >= dd) & ((fm < 0) | (fm >= dd * DAY))
        live = len(np.unique(slot[resting]))
        filled = len(np.unique(slot[fd == dd]))
        rows.append((dd, filled, live, filled / live if live else np.nan))
        if live and (best is None or filled / live > best[3]):
            best = (dd, filled, live, filled / live)
    rows = sorted(rows, key=lambda x: -x[3])[:4]
    res[f"worst_day_{rule}"] = dict(day=str(pd.Timestamp(best[0] * 86400, unit="s").date()), filled=best[1],
                                    live=best[2], share=best[3],
                                    top4=[(str(pd.Timestamp(r[0] * 86400, unit="s").date()), r[1], r[2],
                                           round(r[3], 4)) for r in rows])

# MoneyLine at placement for the filled bids
for rule in ("F1", "F3_1"):
    st = F.loc[F["t_" + rule] >= 0, "ml_d0"].to_numpy()
    nd = int(np.isin(st, (0, 1)).sum())
    res[f"moneyline_{rule}"] = dict(n=int(len(st)), red=int((st == 0).sum()), green=int((st == 1).sum()),
                                    undefined=int((st == -1).sum()), red_share=float((st == 0).sum() / nd))

# TAIL_BOTTOM (knife at 365 days): fills vs twins
for rule in ("F1", "F3_1"):
    tcol = "t_" + rule
    b = BN[BN.rule == rule][["fill_id", "knife", "twin_knife"]]
    d = F[F[tcol] >= 0][["fill_id"]].merge(b, on="fill_id")
    k = pd.to_numeric(d["knife"], errors="coerce").to_numpy(float)
    tk = pd.to_numeric(d["twin_knife"], errors="coerce").to_numpy(float)
    ok = np.isfinite(k)
    res[f"knife_{rule}"] = dict(n_rows=int(len(d)), n_finite=int(ok.sum()),
                                A=float(k[ok].mean()) if ok.any() else None,
                                B=float(np.nanmean(tk[ok])) if ok.any() else None)

for k, v in res.items():
    if "ci" in v:
        print(f"{k:16s} {fmt(v)}  MDE80 {100 * v['mde_80']:.1f}%" + (f"  fast {v['n_fast']} slow {v['n_slow']}"
                                                                     if "n_fast" in v else ""))
    else:
        print(f"{k:16s} {v}")
json.dump(res, open(OUT + "s2_recompute.json", "w"), indent=1, default=str)
print("maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
