"""Independent recomputation for finding f3-missing-beside-flip-return.

Definitions from the prereg (no import of the runner's or desc's functions):
  r_f   = exit x (1 - c_s) / (L x (1 + c_b)) - 1         (§10.2), C-RH: c_b = c_s = 0.95% on F1 rows (§9, §8 "F1 rows")
          F3 rows: buy at L (spread embedded in the trigger), target sells at R1/2, market sells get index x (1 - 0.0095)
          (§8 "Route-specific exits"), so r_f = exit_px / L - 1 when exit_px is the net sell price
  Delta = r_f - twin_mean                                 (§10.2)
  H1 sample (runner coding choice 3): F1 fills with an X-FLIP (rule M) C-RH outcome whose horizon is observed
  (complete) and a finite Delta. F3 rows: F3_1 fills with an X-FLIP RH outcome, complete, finite Delta.
"""
import numpy as np
import pandas as pd

P = "data/stinkbid/runs/outcomes/P1__U_Q1/"
C = 0.0095

cols = ["rule", "exit", "lat", "cost", "fill_id", "coin", "r", "exit_kind", "exit_t", "exit_px", "target",
        "complete", "twin_mean", "twin_n", "delta"]
O = pd.read_parquet(P + "outcomes.parquet", columns=cols,
                    filters=[("rule", "in", ["F1", "F3_1"]), ("exit", "in", ["FLIP", "FLIP_bot"]),
                             ("cost", "in", ["C-RH", "RH"])])
F = pd.read_parquet(P + "fills.parquet", columns=["fill_id", "coin", "L", "P0", "tick", "t_F1", "t_F3_1", "rung"])
print("outcome rows loaded:", len(O))


def sample(rule, exit_, cost, need="delta"):
    o = O[(O.rule == rule) & (O.exit == exit_) & (O.cost == cost)]
    tcol = "t_" + rule
    f = F[F[tcol] >= 0]
    d = f.merge(o, on=["fill_id"], how="inner", suffixes=("", "_o"))
    d = d[d["complete"].astype(bool)]
    d = d[np.isfinite(d[need].to_numpy(float))]
    return d.reset_index(drop=True)


rows = []
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    for ex in ("FLIP", "FLIP_bot"):
        d = sample(rule, ex, cost, "delta")
        dr = sample(rule, ex, cost, "r")
        # r recomputed from the exit price and the limit (my own formula)
        if rule == "F1":
            rr = d["exit_px"] * (1 - C) / (d["L"] * (1 + C)) - 1
        else:
            rr = d["exit_px"] / d["L"] - 1
        dd = d["r"] - d["twin_mean"]
        rows.append(dict(rule=rule, exit=ex, cost=cost, n_delta=len(d), mean_r=d["r"].mean(),
                         mean_r_recomputed=rr.mean(), max_abs_r_diff=float(np.nanmax(np.abs(rr - d["r"]))),
                         mean_delta=d["delta"].mean(), mean_delta_recomputed=dd.mean(),
                         max_abs_delta_diff=float(np.nanmax(np.abs(dd - d["delta"]))),
                         n_r=len(dr), mean_r_finite_r=dr["r"].mean(),
                         exit_kinds=d["exit_kind"].value_counts().to_dict()))
R = pd.DataFrame(rows)
with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 80):
    print(R.drop(columns=["exit_kinds"]).to_string(index=False))
    for _, r in R.iterrows():
        print(r["rule"], r["exit"], r["exit_kinds"])

# the same fill set on both routes: F1 H1 sample restricted to fills also in the F3 sample
d1 = sample("F1", "FLIP", "C-RH")
d3 = sample("F3_1", "FLIP", "RH")
both = set(d1.fill_id) & set(d3.fill_id)
print(f"\nfills in both H1 samples: {len(both)}; F1 mean r on them {d1[d1.fill_id.isin(both)].r.mean():+.5f}, "
      f"F3 mean r on them {d3[d3.fill_id.isin(both)].r.mean():+.5f}")
print(f"F3 fills not in F1 H1 sample: {len(set(d3.fill_id) - set(d1.fill_id))}")
R.drop(columns=["exit_kinds"]).to_csv(
    "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
    "refute_f3_beside/recompute.csv", index=False)
