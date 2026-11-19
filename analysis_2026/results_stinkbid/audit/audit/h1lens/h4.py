"""Independent H4 reconstruction (own code): stacked frames from the cached H4/U_Q1 run, coin-week FE OLS of
Delta on [real, depth], month-block clusters from the union of the four methods' stacked fill times, CR1 SE,
unrestricted wild (Webb) bootstrap-t per method and simultaneous (min_j t*_j), and the NO EDGE bounds both ways."""
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1lens")
from core import my_episodes, my_blocks, WEBB  # own code

P = "data/stinkbid/runs/outcomes/H4__U_Q1/"
NAMES = {"M4 N=90 buffer=0.5": "M4", "M5b": "M5b", "M6": "M6", "M7": "M7"}
A = 0.05 / 3


def frames(rule="F1", cost="C-RH"):
    F = pd.read_parquet(P + "fills.parquet", columns=["variant", "cw", "real", "delta", "t_" + rule, "fill_id", "coin"])
    O = pd.read_parquet(P + "outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "delta", "complete"],
                        filters=[("rule", "==", rule), ("exit", "==", "FLIP")])
    O = O[(O.cost == cost) & O.complete.astype(bool)][["fill_id", "delta"]].rename(columns={"delta": "y"})
    Bd = pd.read_parquet(P + "bids.parquet", columns=["variant", "cw", "real", "delta"])
    real = Bd[Bd.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "dreal"})
    f = F[F["t_" + rule] >= 0].merge(O, on="fill_id").merge(real, on=["variant", "cw"], how="left")
    f = f[np.isfinite(f.y) & np.isfinite(f.dreal)]
    out = {}
    for v, g in f.groupby("variant"):
        out[NAMES[v]] = pd.DataFrame({"y": g.y.values, "real": g.real.astype(bool).values.astype(float),
                                      "depth": (g.delta - g.dreal).values, "cw": g.cw.values,
                                      "time": pd.to_datetime(g["t_" + rule].values * 60_000_000_000, utc=True),
                                      "fill_id": g.fill_id.values})
    return out


def union_blocks(fr):
    names = list(fr)
    t = pd.DatetimeIndex(np.concatenate([fr[n]["time"].values for n in names]))
    t = t.tz_localize(None) if t.tz is not None else t
    days = t.values.astype("datetime64[D]")
    mon = t.values.astype("datetime64[M]").astype(int)
    ep = my_episodes(days)
    mb = my_blocks(mon, ep)
    out, pos = {}, 0
    for n in names:
        out[n] = mb[pos:pos + len(fr[n])]
        pos += len(fr[n])
    return out


def fit(fr, cl):
    y = fr["y"].values.astype(float)
    X = fr[["real", "depth"]].values.astype(float)
    cw = fr["cw"].values
    # drop singleton coin-weeks
    cnt = pd.Series(cw).map(pd.Series(cw).value_counts()).values
    k = cnt > 1
    y, X, cw, cl = y[k], X[k], cw[k], np.asarray(cl)[k]
    _, gi = np.unique(cw, return_inverse=True)

    def within(v):
        if v.ndim == 1:
            m = np.bincount(gi, weights=v) / np.bincount(gi)
            return v - m[gi]
        return np.column_stack([within(v[:, j]) for j in range(v.shape[1])])
    Z = within(X)
    yt = within(y)
    Q = Z.T @ Z
    Qi = np.linalg.inv(Q)
    th = Qi @ Z.T @ yt
    e = yt - Z @ th
    _, ci = np.unique(cl, return_inverse=True)
    G = ci.max() + 1
    S = np.column_stack([np.bincount(ci, weights=Z[:, j] * e, minlength=G) for j in range(2)])
    V = G / (G - 1) * Qi @ (S.T @ S) @ Qi
    se = np.sqrt(V[0, 0])
    n_g = np.bincount(ci, minlength=G).astype(float)
    gs = (n_g ** 2).sum() ** 2 / (n_g ** 4).sum()
    return dict(n=len(y), G=G, gstar=gs, b=th[0], c=th[1], se=se, t=th[0] / se, Z=Z, e=e, Qi=Qi, gi=gi,
                cl_labels=np.unique(cl), ci=ci, cl=cl)


def boot(f, Wfull, lab_index, chunk=1000):
    """unrestricted wild bootstrap-t for b: v = w_g e; v~ = within_cw(v); dtheta = Qi Z' v; e* = v~ - Z dtheta"""
    Z, e, Qi, gi, ci = f["Z"], f["e"], f["Qi"], f["gi"], f["ci"]
    G = f["G"]
    W = Wfull[:, lab_index[f["cl_labels"]]]           # (B, G) multipliers of this method's clusters
    B = W.shape[0]
    cnt = np.bincount(gi)
    out = np.empty(B)
    a = Qi[0]
    for s in range(0, B, chunk):
        w = W[s:s + chunk][:, ci]                     # (b, n)
        v = w * e[None, :]
        gm = np.stack([np.bincount(gi, weights=row) for row in v]) / cnt   # (b, ngroups)
        vt = v - gm[:, gi]
        d = vt @ Z @ Qi.T                             # (b, 2) = Qi Z' v  (Z' vt = Z' v since Z is demeaned)
        es = vt - d @ Z.T                             # (b, n)
        sc = np.stack([np.stack([np.bincount(ci, weights=row * Z[:, j], minlength=G) for row in es]) for j in range(2)], -1)  # (b,G,2)
        eta = sc @ a                                  # (b, G)
        se = np.sqrt(G / (G - 1) * (eta ** 2).sum(1))
        out[s:s + chunk] = d[:, 0] / se
    return out


def qlow(x, a):
    xs = np.sort(np.where(np.isnan(x), -np.inf, x))
    k = int(np.floor((len(xs) + 1) * a)) - 1
    return xs[max(k, 0)]


def main(B=9999, seed=99):
    fr = frames()
    cl = union_blocks(fr)
    allab = np.unique(np.concatenate([cl[n] for n in fr]))
    lab_index = np.zeros(allab.max() + 1, int)
    lab_index[allab] = np.arange(len(allab))
    rng = np.random.default_rng(seed)
    Wfull = WEBB[rng.integers(0, 6, size=(B, len(allab)))]
    fits, tst = {}, {}
    print("union month-blocks:", len(allab))
    for n in ("M4", "M5b", "M6", "M7"):
        f = fit(fr[n], cl[n])
        fits[n] = f
        tst[n] = boot(f, Wfull, lab_index)
        print(f"{n}: n={f['n']} G={f['G']} G*={f['gstar']:.2f} b={f['b']:+.5f} se={f['se']:.5f} t={f['t']:.3f} c={f['c']:+.4f}")
    T = np.column_stack([tst[n] for n in fits])
    qmin = qlow(T.min(1), A)
    print(f"simultaneous q_a(min_j t*) = {qmin:.3f}  (file implies -2.958)")
    rows = []
    for j, n in enumerate(fits):
        f = fits[n]
        qj = qlow(tst[n], A)
        df = f["gstar"] - 1
        ub_t1 = f["b"] + stats.t.ppf(1 - A, df) * f["se"]
        ub_boot1 = f["b"] - qj * f["se"]
        ub_t4 = f["b"] + stats.t.ppf(1 - A / 4, df) * f["se"]
        ub_boots = f["b"] - qmin * f["se"]
        rows.append((n, f["b"], f["se"], f["gstar"], qj, ub_boot1, ub_t1, max(ub_boot1, ub_t1), ub_boots, ub_t4, max(ub_boots, ub_t4)))
        print(f"  {n}: per-method q_a(t*)={qj:.3f} ub_boot={ub_boot1:+.5f} ub_t={ub_t1:+.5f} -> per-method bound {max(ub_boot1, ub_t1):+.5f};"
              f"  simultaneous ub_boot={ub_boots:+.5f} ub_bonf={ub_t4:+.5f} -> {max(ub_boots, ub_t4):+.5f}")
    r = pd.DataFrame(rows, columns=["m", "b", "se", "gstar", "q_j", "ub_boot1", "ub_t1", "ub1", "ub_boot_sim", "ub_bonf", "ub_sim"])
    print(f"H4 bound, max over methods: per-method (prereg §10.2 formula, IUT) {r.ub1.max():+.5f}; simultaneous (as coded) {r.ub_sim.max():+.5f}; E = +0.01000")
    # argmax-only literal reading
    am = r.iloc[r["b"].div(r["se"]).idxmax()]
    print(f"argmax {am.m}: §10.2 bound for the argmax alone {am.ub1:+.5f}")
    # the half gates for the argmax (as coded: on the shared partition)
    f = fr["M7"]
    hf = (f["time"] >= pd.Timestamp("2023-01-01", tz="UTC")).values
    for h in (False, True):
        ff = f[hf == h].reset_index(drop=True)
        cc = np.asarray(cl["M7"])[hf == h]
        g = fit(ff, cc)
        print(f"  M7 half {2 if h else 1}: n={g['n']} b={g['b']:+.5f} se={g['se']:.5f} t={g['t']:.2f}")


if __name__ == "__main__":
    main()
