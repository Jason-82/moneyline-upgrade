"""Independent H4 LEVELS recomputation helpers (audit; written from STINKBID_PREREG.md §10.2-§10.3 and Addendum 1 A1.8).
Nothing from stinkbid_stats or stinkbid_engine is imported: frames, month-blocks, the coin-week fixed-effect fit,
CR1, G*, the wild bootstrap and the bounds are all coded here."""
import numpy as np
import pandas as pd
from scipy import sparse
from scipy import stats as st

RUN = "data/stinkbid/runs/outcomes/H4__U_Q1"
NAME = {"M4 N=90 buffer=0.5": "M4", "M5b": "M5b", "M6": "M6", "M7": "M7"}
METHODS = ("M4", "M5b", "M6", "M7")
HALF = np.datetime64("2023-01-01T00:00:00", "ns")
WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])


def load(rule_cols=("t_F1", "t_F3_1")):
    B = pd.read_parquet(f"{RUN}/bids.parquet", columns=["variant", "cw", "real", "delta", "bid_id", "coin", "t0",
                                                         "shift", "L", "P0", "sigma30", "atr_pct", "tick"])
    F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["bid_id", "fill_id", "variant", "cw", "coin", "shift", "real",
                                                         "delta", "t0", "L"] + list(rule_cols))
    O = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "delta",
                                                            "complete", "r", "twin_mean"])
    return B, F, O


def frames(B, F, O, rule="F1", cost=None, exit="FLIP", lat="M"):
    """Per method: the real level's fills and its placebos' fills, y = Delta_f (X-FLIP, rule M, the rule's cost),
    whole horizon observed; depth = delta_f - delta_real,cw (the real level's depth at placement)."""
    if cost is None:
        cost = "C-RH" if rule == "F1" else "RH"
    o = O[(O.rule == rule) & (O.exit == exit) & (O.lat == lat) & (O.cost == cost) & O.complete.astype(bool)]
    o = o[["fill_id", "delta"]].rename(columns={"delta": "y"})
    assert o.fill_id.is_unique
    tcol = "t_" + rule
    f = F[F[tcol].to_numpy() >= 0].merge(o, on="fill_id", how="inner")
    real = B[B.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
    assert not real.duplicated(["variant", "cw"]).any()
    f = f.merge(real, on=["variant", "cw"], how="left")
    f = f[np.isfinite(f.y.to_numpy(float)) & np.isfinite(f.delta_real.to_numpy(float))]
    f = f.assign(method=f.variant.map(NAME), depth=f.delta.to_numpy(float) - f.delta_real.to_numpy(float),
                 time=(f[tcol].to_numpy(np.int64) * 60_000_000_000).astype("datetime64[ns]"),
                 realf=f.real.astype(bool).astype(float))
    assert f.method.notna().all()
    return {m: g.reset_index(drop=True) for m, g in f.groupby("method")}


def month_blocks(times):
    """§10.2: calendar months of the fill (UTC), merged into month-blocks when an episode (a run of distinct fill
    days at most 3 days apart) has fills in two months. Returns a label per fill: the block's first month index."""
    t = np.asarray(times, "datetime64[ns]")
    day = t.astype("datetime64[D]")
    mon = t.astype("datetime64[M]").astype(np.int64)
    ud = np.unique(day)
    ep_of_day = np.cumsum(np.r_[True, np.diff(ud).astype(np.int64) > 3]) - 1
    ep = ep_of_day[np.searchsorted(ud, day)]
    parent = {int(m): int(m) for m in np.unique(mon)}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e in np.unique(ep):
        ms = np.unique(mon[ep == e])
        for a, b in zip(ms[:-1], ms[1:]):
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    root = np.array([find(int(m)) for m in mon])
    return root, ep


def gstar(sizes):
    n = np.asarray(sizes, float)
    n = n[n > 0]
    return float((n ** 2).sum() ** 2 / (n ** 4).sum()) if len(n) else np.nan


def fe_fit(y, X, fe, cl, drop_singletons=True):
    """OLS of y on X with one absorbed fixed effect (fe), CR1 = G/(G-1) with clusters cl. Singleton fe groups are
    dropped first (A1.8). Returns dict with theta, V, se, n, G, gstar, and the pieces the bootstrap needs."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    fe = np.asarray(fe)
    cl = np.asarray(cl)
    keep = np.ones(len(y), bool)
    if drop_singletons:
        vc = pd.Series(fe).map(pd.Series(fe).value_counts()).to_numpy()
        keep = vc > 1
    y, X, fe, cl = y[keep], X[keep], fe[keep], cl[keep]
    n = len(y)
    if n == 0:
        return None
    fcode = pd.factorize(fe)[0]
    ccode, clab = pd.factorize(cl, sort=True)
    G = len(clab)
    cnt = np.bincount(fcode)

    def dm(v):
        return v - (np.bincount(fcode, weights=v) / cnt)[fcode]
    yt = dm(y)
    Z = np.column_stack([dm(X[:, k]) for k in range(X.shape[1])])
    Q = Z.T @ Z
    if np.linalg.matrix_rank(Q) < Z.shape[1]:
        return dict(theta=np.full(Z.shape[1], np.nan), n=n, G=G)
    Qi = np.linalg.inv(Q)
    theta = Qi @ (Z.T @ yt)
    e = yt - Z @ theta
    H = np.column_stack([np.bincount(ccode, weights=Z[:, k] * e, minlength=G) for k in range(Z.shape[1])])
    V = G / (G - 1) * Qi @ (H.T @ H) @ Qi if G >= 2 else np.full(Q.shape, np.nan)
    se = np.sqrt(np.diag(V))
    sizes = np.bincount(ccode, minlength=G)
    return dict(theta=theta, V=V, se=se, n=n, G=G, gstar=gstar(sizes), Z=Z, e=e, yt=yt, Qi=Qi, fcode=fcode,
                ccode=ccode, clab=clab, sizes=sizes, keep=keep, n_fe=len(cnt), y=y, X=X)


def tsf(t, df):
    return float(st.t.sf(t, df)) if np.isfinite(t) and df > 0 else np.nan


def tppf(p, df):
    return float(st.t.ppf(p, df)) if df > 0 else np.nan


def boot_t(fit, Wc, chunk=1000):
    """Wild cluster bootstrap-t draws for coefficient 0 by brute force: y* = yhat + w_g e (unrestricted), the fixed
    effects re-absorbed (re-demeaned within coin-week), theta re-estimated, CR1 from the draw's own residuals;
    t* = (theta*_0 - theta_0) / se*. Wc: (B, G) multipliers on this fit's clusters (in clab order)."""
    Z, e, Qi, fcode, ccode = fit["Z"], fit["e"], fit["Qi"], fit["fcode"], fit["ccode"]
    n, G = len(e), fit["G"]
    cnt = np.bincount(fcode)
    # averaging operator within fe groups (sparse, symmetric)
    A = sparse.csr_matrix((1.0 / cnt[fcode], (np.arange(n), fcode)), shape=(n, len(cnt)))
    D = sparse.csr_matrix((np.ones(n), (np.arange(n), fcode)), shape=(n, len(cnt)))
    C = sparse.csr_matrix((np.ones(n), (np.arange(n), ccode)), shape=(n, G))
    out = np.empty(Wc.shape[0])
    a0 = Qi[0]
    cG = G / (G - 1)
    for s in range(0, Wc.shape[0], chunk):
        W = Wc[s:s + chunk][:, ccode]                     # (b, n) multiplier of each row's cluster
        v = W * e[None, :]                                # y* - yhat in the original space
        vbar = (D @ (A.T @ v.T)).T                        # fe-group means of v, per row
        vt = v - vbar                                     # within-transformed y* - Z theta
        dth = (vt @ Z) @ Qi                               # (b, k) theta* - theta  (Qi symmetric)
        es = vt - dth @ Z.T                               # draw residuals
        Hs = np.stack([np.asarray(C.T @ (es * Z[:, k][None, :]).T).T for k in range(Z.shape[1])], axis=2)  # (b,G,k)
        eta = Hs @ a0                                     # (b, G)
        se = np.sqrt(cG * (eta ** 2).sum(1))
        with np.errstate(divide="ignore", invalid="ignore"):
            out[s:s + chunk] = dth[:, 0] / se
    return out
