"""Step 1: the per-fill rows of record (engine outputs) and my own statistics on them.

Rows: (F1, FLIP, C-RH), (F1, FLIP_bot, C-RH), (F3_1, FLIP, RH), (F3_1, FLIP_bot, RH); complete horizon; finite y.
Checks r against r = exit_px (1 - c_s) / (L (1 + c_b)) - 1 (F1 C-RH: c = 0.95% both sides; F3: r = exit_px / L - 1,
a delisting value x (1 - 0.0095)). Writes per-fill frames for the later steps.
"""
import sys
import json
import numpy as np
import pandas as pd

OUT = sys.argv[1]
sys.path.insert(0, OUT)
import mystats as ms

RUN = "data/stinkbid/runs/outcomes/P1__U_Q1/"
F = pd.read_parquet(RUN + "fills.parquet", columns=["fill_id", "coin", "L", "P0", "tick", "tick_str", "t_F1", "t_F3_1",
                                                     "rung", "seg", "lineage"])
cols = ["rule", "exit", "lat", "cost", "fill_id", "coin", "r", "exit_kind", "exit_t", "exit_px", "target", "complete",
        "twin_mean", "twin_n", "twin_pooled", "delta", "horizon_t", "hold_h"]
O = pd.read_parquet(RUN + "outcomes.parquet", columns=cols,
                    filters=[("rule", "in", ["F1", "F3_1"]), ("exit", "in", ["FLIP", "FLIP_bot"])])
O = O[((O.rule == "F1") & (O.cost == "C-RH")) | ((O.rule == "F3_1") & (O.cost == "RH"))]
print("outcome rows read:", len(O), O.groupby(["rule", "exit", "cost"]).size().to_dict())

res = {}
frames = {}
for rule, ex, cost in [("F1", "FLIP", "C-RH"), ("F1", "FLIP_bot", "C-RH"), ("F3_1", "FLIP", "RH"),
                       ("F3_1", "FLIP_bot", "RH")]:
    o = O[(O.rule == rule) & (O.exit == ex) & (O.cost == cost)].drop(columns=["coin"])
    tcol = "t_" + rule
    f = F[F[tcol] >= 0]
    d = f.merge(o, on="fill_id", how="inner")
    n_all = len(d)
    d = d[d.complete.astype(bool)]
    n_c = len(d)
    # my r from exit_px and L
    if rule == "F1":
        mine = d.exit_px * (1 - 0.0095) / (d.L * (1 + 0.0095)) - 1
    else:
        cs = np.where(d.exit_kind == "delist", 0.0095, 0.0)
        mine = d.exit_px * (1 - cs) / d.L - 1
    err = np.nanmax(np.abs(mine - d.r))
    kinds = d.exit_kind.value_counts().to_dict()
    dd = d[np.isfinite(d.delta)].copy()
    dd["time"] = pd.to_datetime(dd[tcol] * 60, unit="s", utc=True)
    dd["mb"] = ms.month_blocks(dd["time"])
    dd["ep"] = ms.episodes(dd["time"])
    key = f"{rule}/{ex}"
    frames[key] = dd
    dd.to_parquet(f"{OUT}/rows_{rule}_{ex}.parquet")
    r_mean_finite_r = float(d.r[np.isfinite(d.r)].mean())
    res[key] = dict(rows=n_all, complete=n_c, finite_delta=len(dd), finite_r=int(np.isfinite(d.r).sum()),
                    max_abs_r_formula_err=float(err), exit_kinds=kinds,
                    mean_r_on_delta_sample=float(dd.r.mean()), mean_r_on_finite_r=r_mean_finite_r,
                    mean_my_r=float(mine[np.isfinite(d.delta)].mean()),
                    mean_delta=float(dd.delta.mean()),
                    mean_twin=float(dd.twin_mean.mean()),
                    twins_pooled=int(dd.twin_pooled.sum()), twin_n_min=int(dd.twin_n.min()))
    print(key, json.dumps(res[key], default=str))

json.dump(res, open(f"{OUT}/s1_tables.json", "w"), indent=1, default=str)
