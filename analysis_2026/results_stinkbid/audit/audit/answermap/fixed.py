"""Independent recomputation of the answer's fixed sentences (worst day, knife, MoneyLine, capacity) and the
descriptive sentences (D-H2, D-H3, D-H5 rates and b, D8), plus D12 spot checks. Own code; read-only."""
import json
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/answermap")
from core import ts, month_blocks, quarter_blocks, episodes, cr1, RUNS  # own helpers

DAY = 1440


def ols_cr1(y, X, cl, fe=None, j=0):
    """OLS of y on X (FE absorbed by within-demeaning), CR1 (G/(G-1)) one-way cluster SE of coefficient j."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    if fe is not None:
        fe = np.asarray(fe)
        df = pd.DataFrame(X)
        df["y"] = y
        df["fe"] = fe
        g = df.groupby("fe")
        dm = df.drop(columns="fe") - g.transform("mean")
        y = dm["y"].to_numpy()
        X = dm.drop(columns="y").to_numpy()
    XtX = X.T @ X
    b = np.linalg.solve(XtX, X.T @ y)
    u = y - X @ b
    labs, inv = np.unique(np.asarray(cl), return_inverse=True)
    G = len(labs)
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, inv, X * u[:, None])
    A = np.linalg.inv(XtX)
    V = G / (G - 1) * A @ (S.T @ S) @ A
    ng = np.bincount(inv).astype(float)
    gstar = (ng ** 2).sum() ** 2 / (ng ** 4).sum()
    se = np.sqrt(V[j, j])
    q = stats.t.ppf(0.975, gstar - 1)
    return dict(b=b[j], se=se, G=G, gstar=gstar, n=len(y), ci=(b[j] - q * se, b[j] + q * se),
                mde=(stats.t.ppf(1 - 0.05 / 3, gstar - 1) + stats.t.ppf(0.8, gstar - 1)) * se)


def twoway(y, X, c1, c2):
    """OLS with two-way CR1 (coin x quarter): V = V1 + V2 - V12, each with its own G/(G-1)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    XtX = X.T @ X
    b = np.linalg.solve(XtX, X.T @ y)
    u = y - X @ b
    A = np.linalg.inv(XtX)

    def meat(cl):
        labs, inv = np.unique(np.asarray(cl), return_inverse=True)
        G = len(labs)
        S = np.zeros((G, X.shape[1]))
        np.add.at(S, inv, X * u[:, None])
        return G / (G - 1) * A @ (S.T @ S) @ A, G
    V1, G1 = meat(c1)
    V2, G2 = meat(c2)
    c12 = np.array([f"{a}|{b_}" for a, b_ in zip(c1, c2)])
    V12, G12 = meat(c12)
    V = V1 + V2 - V12
    return b, V, G1, G2


def main():
    out = {}
    run = RUNS + "/P1__U_Q1"
    bids = pd.read_parquet(run + "/bids.parquet", columns=["bid_id", "coin", "rung", "variant", "t0", "live_from", "life_end"])
    F = pd.read_parquet(run + "/fills.parquet")
    bids = bids.merge(F[["bid_id", "t_F1"]], on="bid_id", how="left")
    bids["t_F1"] = bids["t_F1"].fillna(-1).astype(np.int64)
    # ---------- worst day: live = life overlaps the UTC day and not filled before the day's start
    fd = np.where(bids.t_F1 >= 0, bids.t_F1 // DAY, -1)
    bids["fday"] = fd
    days = np.unique(fd[fd >= 0])
    rows = []
    lf = bids.live_from.to_numpy(np.int64)
    le = bids.life_end.to_numpy(np.int64)
    tf = bids.t_F1.to_numpy(np.int64)
    slot = (bids.coin.astype(str) + "|" + bids.rung.astype(str) + "|" + bids.variant.astype(str)).to_numpy()
    for d in days:
        s, e = d * DAY, (d + 1) * DAY
        live = (lf < e) & (le > s) & ((tf < 0) | (tf >= s))
        nl = len(np.unique(slot[live]))
        nf = len(np.unique(slot[fd == d]))
        nb_live = int(live.sum())
        rows.append((str(ts([s])[0].date()), nf, nl, nb_live, nf / nl if nl else np.nan))
    W = pd.DataFrame(rows, columns=["day", "filled_slots", "live_slots", "live_bids", "share"])
    out["worst_day_by_share"] = W.sort_values("share", ascending=False).head(5).to_dict("records")
    out["worst_day_by_count"] = W.sort_values("filled_slots", ascending=False).head(5).to_dict("records")
    # ---------- knife
    Bn = pd.read_parquet(run + "/bench.parquet", columns=["fill_id", "rule", "knife", "twin_knife", "alert_72h",
                                                           "rec_R_72h", "rec_P0_30d", "twin_rec_R_72h", "rec_dn10_first",
                                                           "twin_rec_dn10_first", "rec_R_15m"])
    f1 = F[F.t_F1 >= 0]
    b1 = Bn[Bn.rule == "F1"].merge(f1[["fill_id", "t_F1", "rung", "ml_d0", "ml_fill", "coin"]], on="fill_id")
    k = b1[np.isfinite(pd.to_numeric(b1.knife, errors="coerce"))]
    out["knife"] = dict(n=len(k), A=float(k.knife.mean()), B=float(np.nanmean(pd.to_numeric(k.twin_knife, errors="coerce"))),
                        n_twin_finite=int(np.isfinite(pd.to_numeric(k.twin_knife, errors="coerce")).sum()))
    # ---------- MoneyLine
    out["ml_d0"] = f1.ml_d0.value_counts().to_dict()
    out["ml_fill"] = f1.ml_fill.value_counts().to_dict() if "ml_fill" in f1 else None
    # ---------- capacity
    src = f1.cap_src.astype(str).to_numpy()
    cap_life = np.where(src == "agg", pd.to_numeric(f1.agg_life, errors="coerce"), pd.to_numeric(f1.c1_life, errors="coerce"))
    cap_first = np.where(src == "agg", pd.to_numeric(f1.agg_first, errors="coerce"), pd.to_numeric(f1.c1_first, errors="coerce"))
    cr = []
    for rg in sorted(f1.rung.unique()):
        m = f1.rung.to_numpy() == rg
        cl = cap_life[m]
        cf = cap_first[m]
        cr.append(dict(rung=float(rg), fills=int(m.sum()), src_agg=int((src[m] == "agg").sum()),
                       p10_life=float(np.quantile(cl[np.isfinite(cl)], 0.1)), p50_life=float(np.quantile(cl[np.isfinite(cl)], 0.5)),
                       Qmax_life=0.25 * float(np.quantile(cl[np.isfinite(cl)], 0.1)),
                       p10_first=float(np.quantile(cf[np.isfinite(cf)], 0.1)), p50_first=float(np.quantile(cf[np.isfinite(cf)], 0.5)),
                       Qmax_first=0.25 * float(np.quantile(cf[np.isfinite(cf)], 0.1)), n_finite=int(np.isfinite(cl).sum())))
    out["capacity"] = cr
    # ---------- D12 spot checks (F1 fills)
    out["d12"] = dict(n=len(b1), R_72h=float(np.nanmean(b1.rec_R_72h)), twin_R_72h=float(np.nanmean(b1.twin_rec_R_72h)),
                      P0_30d=float(np.nanmean(b1.rec_P0_30d)), dn10_first=float(np.nanmean(b1.rec_dn10_first)),
                      twin_dn10_first=float(np.nanmean(b1.twin_rec_dn10_first)), R_15m=float(np.nanmean(b1.rec_R_15m)))
    b3 = Bn[Bn.rule == "F3_1"].merge(F[F.t_F3_1 >= 0][["fill_id"]], on="fill_id")
    out["d12_F3"] = dict(n=len(b3), R_72h=float(np.nanmean(b3.rec_R_72h)), twin_R_72h=float(np.nanmean(b3.twin_rec_R_72h)),
                         dn10_first=float(np.nanmean(b3.rec_dn10_first)))
    # ---------- D8 part 1: alert at a 72 h delay, month-block clusters
    a = b1[np.isfinite(pd.to_numeric(b1.alert_72h, errors="coerce"))].copy()
    a["time"] = ts(a.t_F1)
    mb, ep = month_blocks(a["time"])
    out["d8_part1"] = {k_: (float(v) if not isinstance(v, int) else v) for k_, v in cr1(a.alert_72h.astype(float), mb).items()}
    # ---------- D-H2: X-HOLD-90 delta, F1, C-RH, complete, quarter-block clusters
    O = pd.read_parquet(run + "/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "delta", "complete",
                                                              "exit_t", "exit_px"])
    o = O[(O.rule == "F1") & (O.exit == "HOLD90") & (O.cost == "C-RH") & O.complete.astype(bool)]
    d = f1[["fill_id", "t_F1", "rung", "s24"]].merge(o[["fill_id", "delta"]], on="fill_id")
    d = d[np.isfinite(d.delta)].reset_index(drop=True)
    d["time"] = ts(d.t_F1)
    qb = quarter_blocks(d["time"])
    out["dh2"] = {k_: (float(v) if not isinstance(v, int) else v) for k_, v in cr1(d.delta, qb).items()}
    # ---------- D8 part 2: HOLD90 px / TH72 px - 1 - tbill * days / 365 (C-0), quarter-block clusters
    h90 = O[(O.rule == "F1") & (O.exit == "HOLD90") & (O.cost == "C-0") & O.complete.astype(bool)][["fill_id", "exit_px", "exit_t"]]
    t72 = O[(O.rule == "F1") & (O.exit == "TH72") & (O.cost == "C-0") & O.complete.astype(bool)][["fill_id", "exit_px", "exit_t"]]
    m = h90.merge(t72, on="fill_id", suffixes=("", "_72")).merge(f1[["fill_id", "t_F1"]], on="fill_id")
    m = m[(m.exit_px > 0) & (m.exit_px_72 > 0)].reset_index(drop=True)
    from analysis_2026 import stinkbid_data as sbd   # data loader only (T-bill series)
    fday = pd.DatetimeIndex(ts((m.t_F1.to_numpy(np.int64) // DAY) * DAY)).tz_localize(None)
    tb = sbd.tbill_daily(fday).to_numpy(float) / 100.0
    dd = (m.exit_t.to_numpy(np.int64) - m.exit_t_72.to_numpy(np.int64)) / DAY
    m["y"] = m.exit_px / m.exit_px_72 - 1 - tb * dd / 365.0
    m["time"] = ts(m.t_F1)
    qb2 = quarter_blocks(m["time"])
    out["d8_part2"] = {k_: (float(v) if not isinstance(v, int) else v) for k_, v in cr1(m.y, qb2).items()}
    out["d8_part2_no_tbill"] = float((m.exit_px / m.exit_px_72 - 1).mean())
    # ---------- D-H3: fast (s24 >= .75) vs slow (s24 < .5), X-FLIP F1 C-RH delta; episode FE, rung dummies, month-block
    o2 = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & O.complete.astype(bool)]
    d3 = f1[["fill_id", "t_F1", "rung", "s24"]].merge(o2[["fill_id", "delta"]], on="fill_id")
    d3 = d3[np.isfinite(d3.delta)].reset_index(drop=True)
    d3["time"] = ts(d3.t_F1)
    mb3, ep3 = month_blocks(d3["time"])     # clusters of the full H1 sample
    s = d3.s24.to_numpy(float)
    sel = (s >= 0.75) | (s < 0.5)
    g = d3[sel].reset_index(drop=True)
    # clusters rebuilt on the analysed sample (stinkbid_desc coding choice 1)
    mbg, epg = month_blocks(g["time"])
    fast = (g.s24.to_numpy(float) >= 0.75).astype(float)
    rungs = sorted(g.rung.unique())
    R = np.column_stack([(g.rung.to_numpy() == v).astype(float) for v in rungs[1:]])
    X = np.column_stack([fast, R])
    out["dh3_primary"] = {k_: (float(v) if np.isscalar(v) else [float(x) for x in v]) for k_, v in
                          ols_cr1(g.delta, X, mbg, fe=epg, j=0).items()}
    out["dh3_n_fast_slow"] = (int(fast.sum()), int((1 - fast).sum()))
    # ---------- D-H5 (U-B run): knife ~ 1 + notQ + rung dummies + p0; two-way coin(lineage) x quarter
    ub = RUNS + "/P1__U_B"
    Fu = pd.read_parquet(ub + "/fills.parquet", columns=["fill_id", "coin", "lineage", "rung", "sigma30", "t_F1",
                                                          "in_U_Q1", "in_U_Q1_12"])
    Bu = pd.read_parquet(ub + "/bench.parquet", columns=["fill_id", "rule", "knife"])
    du = Fu[Fu.t_F1 >= 0].merge(Bu[Bu.rule == "F1"][["fill_id", "knife"]], on="fill_id")
    du = du[np.isfinite(pd.to_numeric(du.knife, errors="coerce"))].reset_index(drop=True)
    du["time"] = ts(du.t_F1)
    tt = pd.DatetimeIndex(du["time"]).tz_localize(None)
    du["qu"] = tt.year * 10 + (tt.month - 1) // 3 + 1
    lin = du.lineage.astype(str)
    du["asset"] = np.where(du.lineage.notna() & (lin != "") & (lin != "None"), lin, du.coin.astype(str))
    sa = du.sigma30.to_numpy(float) * np.sqrt(365.0)
    p0 = stats.norm.cdf((np.log(0.5) + 0.5 * sa ** 2) / sa)
    res5 = {}
    for gc in ("in_U_Q1", "in_U_Q1_12"):
        q = du[gc].astype(bool).to_numpy()
        notq = 1.0 - q
        rungs = sorted(du.rung.unique())
        R = np.column_stack([(du.rung.to_numpy() == v).astype(float) for v in rungs[1:]])
        X = np.column_stack([np.ones(len(du)), notq, R, p0])
        b, V, G1, G2 = twoway(du.knife.to_numpy(float), X, du.asset.to_numpy(), du.qu.to_numpy())
        se = np.sqrt(V[1, 1]) if V[1, 1] > 0 else np.nan
        dfree = min(G1, G2) - 1
        qq = stats.t.ppf(0.975, dfree)
        res5[gc] = dict(n=len(du), rate_q=float(du.knife[q].mean()), rate_rest=float(du.knife[~q].mean()),
                        n_q=int(q.sum()), n_rest=int((~q).sum()), b=float(b[1]), se=float(se),
                        ci=(float(b[1] - qq * se), float(b[1] + qq * se)), G_coin=int(G1), G_quarter=int(G2), df=int(dfree))
    out["dh5"] = res5
    json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
