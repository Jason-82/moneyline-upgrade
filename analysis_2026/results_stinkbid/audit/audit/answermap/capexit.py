import sys, json
import numpy as np, pandas as pd, pyarrow.parquet as pq
RUNS = "/home/user/moneyline-upgrade/data/stinkbid/runs/outcomes"
run = RUNS + "/P1__U_Q1"
F = pd.read_parquet(run + "/fills.parquet", columns=["fill_id", "bid_id", "t_F1", "rung", "n_windows", "agg_first", "agg_life", "cap_src"])
f1 = F[F.t_F1 >= 0]
O = pd.read_parquet(run + "/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "exit_t", "exit_kind"])
o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH")][["fill_id", "exit_t", "exit_kind"]]
d = f1.merge(o, on="fill_id", how="left")
ex = dict(zip(d.bid_id.astype(np.int64), d.exit_t.astype(np.int64)))
best = {}
pf = pq.ParquetFile(run + "/cap_curve.parquet")
for i in range(pf.num_row_groups):
    t = pf.read_row_group(i, columns=["bid_id", "minute", "cum"]).to_pandas()
    t = t[t.bid_id.isin(list(ex))]
    t["ex"] = t.bid_id.map(ex)
    t = t[t.minute < t.ex]
    m = t.groupby("bid_id").cum.max()
    for b, v in m.items():
        best[int(b)] = max(best.get(int(b), 0.0), float(v))
    del t
d["cap_exit"] = d.bid_id.map(lambda b: best.get(int(b), 0.0))
out = []
for rg, g in d.groupby("rung"):
    out.append(dict(rung=float(rg), n=len(g), p10_first=float(np.quantile(g.agg_first, .1)), p10_to_exit=float(np.quantile(g.cap_exit, .1)),
                    p10_life=float(np.quantile(g.agg_life, .1)), p50_first=float(np.quantile(g.agg_first, .5)),
                    p50_to_exit=float(np.quantile(g.cap_exit, .5)), share_first_lt_10k=float((g.agg_first < 10000).mean()),
                    share_first_lt_40k=float((g.agg_first < 40000).mean()), median_windows=float(g.n_windows.median()),
                    share_life_gt_5x_first=float((g.agg_life > 5 * g.agg_first).mean())))
print(json.dumps(out, indent=1))
print("exit kinds:", d.exit_kind.value_counts().to_dict())
