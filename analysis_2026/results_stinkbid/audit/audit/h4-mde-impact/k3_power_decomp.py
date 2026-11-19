"""K3 power re-run, decomposed (own regression code): on the 300 cached null replications per scenario, M4's own SE,
and the share of replications rejected at 0.05/3 and 0.05 for an effect of 1% added to M4's real fills, under
(a) H4's p_G* = min(1, 4 x one-sided t(G*-1) p of max_j t_j) (the Bonferroni part of the pre-registered rule) and
(b) the single-test threshold the printed MDE assumes (max_j t_j > t_{1-alpha, G*-1}, no x4).
power.json's reject rates use max(p_WCR, p_G*) and are printed beside."""
import json, pickle
from pathlib import Path
import numpy as np
from scipy import stats

S = pickle.load(open("data/stinkbid/controls/k3_setup.pkl", "rb"))
p4 = S["p4"]
meth = np.asarray(p4["meth"]).astype(str)
real = np.asarray(p4["real"], bool)
depth = np.asarray(p4["depth"], float)
cw = np.asarray(p4["cw"])
clus = np.asarray(p4["cluster"])
M = ["M4", "M5b", "M6", "M7"]
idx = {m: np.where(meth == m)[0] for m in M}
cwc = {m: np.unique(cw[idx[m]].astype(str), return_inverse=True)[1] for m in M}


def fit(y, m):
    ii = idx[m]
    yy, rr, dd, ff, cc = y[ii], real[ii].astype(float), depth[ii], cwc[m], clus[ii]
    ok = np.isfinite(yy) & np.isfinite(dd)
    yy, rr, dd, ff, cc = yy[ok], rr[ok], dd[ok], ff[ok], cc[ok]
    cnt = np.bincount(ff)
    keep = cnt[ff] > 1
    yy, rr, dd, ff, cc = yy[keep], rr[keep], dd[keep], ff[keep], cc[keep]
    ff = np.unique(ff, return_inverse=True)[1]
    n_f = np.bincount(ff).astype(float)
    def w(v):
        return v - (np.bincount(ff, weights=v) / n_f)[ff]
    Z = np.column_stack([w(rr), w(dd)])
    yt = w(yy)
    Qi = np.linalg.inv(Z.T @ Z)
    th = Qi @ (Z.T @ yt)
    e = yt - Z @ th
    cu, ci = np.unique(cc, return_inverse=True)
    G = len(cu)
    Sg = np.column_stack([np.bincount(ci, weights=Z[:, a] * e, minlength=G) for a in range(2)])
    V = G / (G - 1) * Qi @ (Sg.T @ Sg) @ Qi
    se = np.sqrt(V[0, 0])
    ng = np.bincount(ci).astype(float)
    gs = (ng ** 2).sum() ** 2 / (ng ** 4).sum()
    return th[0], se, gs


pw = json.load(open("analysis_2026/results_stinkbid/controls/power.json"))
files = sorted(Path("data/stinkbid/controls/k3_cache").glob("*.npz"))
for sc in ("base", "high", "hetero"):
    fs = [f for f in files if f.name.startswith(sc + "_")]
    se4, rej = [], {k: [] for k in ("bonf3", "bonf05", "single3", "single05", "m4own_bonf3", "m4own_single3")}
    tmax_null, gs_list = [], []
    for f in fs:
        d4 = np.load(f)["d4"]
        for eff in (0.0, 0.01):
            y = d4 + eff * (real & (meth == "M4"))
            res = {m: fit(y, m) for m in M}
            t = {m: res[m][0] / res[m][1] for m in M}
            am = max(t, key=t.get)
            T, gsa = t[am], res[am][2]
            pt = stats.t.sf(T, gsa - 1)
            if eff == 0.0:
                se4.append(res["M4"][1]); tmax_null.append(T); gs_list.append(res["M4"][2])
                continue
            pg = min(1.0, 4 * pt)
            rej["bonf3"].append(pg < 0.05 / 3)
            rej["bonf05"].append(pg < 0.05)
            rej["single3"].append(pt < 0.05 / 3)
            rej["single05"].append(pt < 0.05)
            p4own = stats.t.sf(t["M4"], res["M4"][2] - 1)
            rej["m4own_bonf3"].append(min(1.0, 4 * p4own) < 0.05 / 3)
            rej["m4own_single3"].append(p4own < 0.05 / 3)
    rec = [r for r in pw["power"]["H4"][sc] if r["kind"] == "M4" and r["effect"] == 0.01][0]
    se4 = np.array(se4)
    g4 = float(np.median(gs_list)); df4 = g4 - 1
    t80 = stats.t.ppf(0.8, df4)
    print(f"{sc}: n reps {len(fs)}; M4 null SE median {np.median(se4):.4%} (mean {se4.mean():.4%}), M4 G* {g4:.2f}; "
          f"1%/SE = {0.01/np.median(se4):.2f}")
    print(f"   M4-only effect 1%: reject at 0.05/3 -> p_G* (x4) {np.mean(rej['bonf3']):.3f}, single-test (no x4) "
          f"{np.mean(rej['single3']):.3f}; record max(p_WCR, p_G*) {rec['reject_alpha3']:.3f}")
    print(f"                      reject at 0.05   -> p_G* (x4) {np.mean(rej['bonf05']):.3f}, single-test (no x4) "
          f"{np.mean(rej['single05']):.3f}; record {rec['reject_05']:.3f}")
    print(f"   M4's MDE at its median SE: single-test {(stats.t.ppf(1-0.05/3, df4)+t80)*np.median(se4):.4%}, "
          f"Bonferroni {(stats.t.ppf(1-0.05/12, df4)+t80)*np.median(se4):.4%}")
