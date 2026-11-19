"""Step 1 (independent): the H1 means of record and their F3 (s = 1%) counterparts, straight from the cached
P1/U-Q1 engine run. Own code; no stinkbid_* import.

Sample rule (prereg §10.2/§10.3 + runner's per_fill reading, re-implemented): one row per fill of the rule
(fills.t_<rule> >= 0) with an outcome row for (rule, exit, cost), whole horizon observed (complete), finite Delta.
"""
import json
import numpy as np
import pandas as pd

RUN = "data/stinkbid/runs/outcomes/P1__U_Q1/"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/f3-beside-flip/"

F = pd.read_parquet(RUN + "fills.parquet", columns=["fill_id", "coin", "t_F1", "t_F3_1", "L", "P0", "tick"])
O = pd.read_parquet(RUN + "outcomes.parquet",
                    columns=["rule", "exit", "lat", "cost", "fill_id", "r", "delta", "twin_mean", "exit_kind",
                             "exit_t", "exit_px", "target", "complete", "horizon_t"],
                    filters=[("rule", "in", ["F1", "F3_1"])])
print("outcome rows read:", len(O))
print(O.groupby(["rule", "exit", "lat", "cost"]).size().to_string())

res = {}
for rule, ex, cost in [("F1", "FLIP", "C-RH"), ("F1", "FLIP_bot", "C-RH"),
                       ("F3_1", "FLIP", "RH"), ("F3_1", "FLIP_bot", "RH")]:
    o = O[(O.rule == rule) & (O.exit == ex) & (O.cost == cost)]
    o = o[o.complete.astype(bool)]
    f = F[F["t_" + rule] >= 0]
    d = f.merge(o, on="fill_id", how="inner", suffixes=("", "_o"))
    d = d[np.isfinite(d.delta.to_numpy(float))]
    # r from its definition: exit x (1 - c_s) / (L x (1 + c_b)) - 1; spot C-RH c = 0.95% both sides;
    # F3 route: buy at L, the spread is in the exit price (exit_px already index x (1 - 0.0095) or the target)
    if rule == "F1":
        r_def = d.exit_px * (1 - 0.0095) / (d.L * (1 + 0.0095)) - 1
    else:
        r_def = d.exit_px / d.L - 1
    dl = d.r - d.twin_mean
    res[f"{rule}/{ex}/{cost}"] = dict(
        n=int(len(d)), mean_r=float(d.r.mean()), mean_delta=float(d.delta.mean()),
        max_abs_r_vs_def=float(np.nanmax(np.abs(r_def - d.r))),
        n_r_mismatch_1e9=int((np.abs(r_def - d.r) > 1e-9).sum()),
        max_abs_delta_vs_r_minus_twin=float(np.nanmax(np.abs(dl - d.delta))),
        exit_kinds=d.exit_kind.value_counts().to_dict(),
        mean_r_by_def=float(r_def.mean()))
    if rule == "F3_1" and ex == "FLIP":
        d[["fill_id", "coin", "t_F3_1", "L", "P0", "tick", "r", "delta", "twin_mean", "exit_kind", "exit_t",
           "exit_px", "target", "horizon_t"]].to_parquet(OUT + "f3_flip_sample.parquet")
    if rule == "F3_1" and ex == "FLIP_bot":
        d[["fill_id", "coin", "t_F3_1", "L", "P0", "tick", "r", "delta", "twin_mean", "exit_kind", "exit_t",
           "exit_px", "target", "horizon_t"]].to_parquet(OUT + "f3_bot_sample.parquet")
    if rule == "F1" and ex == "FLIP":
        d[["fill_id", "coin", "t_F1", "L", "P0", "tick", "r", "delta", "twin_mean", "exit_kind", "exit_t",
           "exit_px", "target", "horizon_t"]].to_parquet(OUT + "f1_flip_sample.parquet")

print(json.dumps(res, indent=1, default=str))
json.dump(res, open(OUT + "s1_means.json", "w"), indent=1, default=str)

# same-fill comparison: F3 FLIP fills that are also in the F1 FLIP sample
a = pd.read_parquet(OUT + "f1_flip_sample.parquet")[["fill_id", "r"]]
b = pd.read_parquet(OUT + "f3_flip_sample.parquet")[["fill_id", "r"]]
m = a.merge(b, on="fill_id", suffixes=("_F1", "_F3"))
print("fills in both F1 and F3 FLIP samples:", len(m), "mean r F1", m.r_F1.mean(), "mean r F3", m.r_F3.mean())
print("F3 fills not in F1 sample:", len(set(b.fill_id) - set(a.fill_id)))
