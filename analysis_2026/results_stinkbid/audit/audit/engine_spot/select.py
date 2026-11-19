"""Select the 14 P1 fills to spot-check and dump the engine's stored values for them (read-only)."""
import json
import numpy as np
import pandas as pd

ROOT = "/home/user/moneyline-upgrade"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/engine_spot"
RUN = f"{ROOT}/data/stinkbid/runs/outcomes/P1__U_Q1"

s = pd.read_csv(f"{ROOT}/analysis_2026/results_stinkbid/primary/samples_H1.csv", parse_dates=["time"])
s2 = pd.read_csv(f"{ROOT}/analysis_2026/results_stinkbid/primary/samples_H2R.csv", parse_dates=["time"])
rng = np.random.default_rng(7)
chosen, why = [], {}


def take(ids, label):
    for i in ids:
        i = int(i)
        if i not in chosen:
            chosen.append(i)
            why[i] = label
            return i
    raise RuntimeError(label)


for i in s.sort_values("y", ascending=False).fill_id.head(4):
    take([i], "largest y")
for i in s.sort_values("r").fill_id:
    if sum(1 for v in why.values() if v == "smallest r") == 3:
        break
    if int(i) not in chosen:
        take([i], "smallest r")
c = s[(s.time.dt.strftime("%Y-%m-%d") == "2025-10-10") & ~s.fill_id.isin(chosen)].fill_id.to_numpy()
take([rng.choice(c)], "2025-10-10")
c = s[(s.time >= "2022-11-07") & (s.time < "2022-11-14") & ~s.fill_id.isin(chosen)].fill_id.to_numpy()
take([rng.choice(c)], "2022-11 FTT week")
rest = s[~s.fill_id.isin(chosen)].fill_id.to_numpy()
for i in rng.choice(rest, size=5, replace=False):
    take([i], "random (seed 7)")

sel = s[s.fill_id.isin(chosen)].set_index("fill_id").loc[chosen].reset_index()
sel["why"] = [why[i] for i in sel.fill_id]
sel = sel.merge(s2[["fill_id", "y"]].rename(columns={"y": "y_H2R"}), on="fill_id", how="left")

F = pd.read_parquet(f"{RUN}/fills.parquet", filters=[("fill_id", "in", chosen)],
                    columns=["fill_id", "coin", "rung", "cw", "t0", "d0", "P0", "sigma30", "tick", "tick_str", "sidx",
                             "seg", "live_from", "life_end", "month", "L", "L_tau", "n_ticks", "delta", "bid_id",
                             "i_F1", "t_F1", "gap_through", "open_below", "H24", "lineage", "method", "params",
                             "variant"])
O = pd.read_parquet(f"{RUN}/outcomes.parquet",
                    filters=[("fill_id", "in", chosen), ("rule", "==", "F1"), ("exit", "==", "FLIP"),
                             ("lat", "==", "M"), ("cost", "==", "C-RH")],
                    columns=["fill_id", "coin", "r", "exit_kind", "exit_t", "exit_px", "target", "horizon_t",
                             "complete", "hold_h", "twin_mean", "twin_n", "twin_pooled", "delta"])
B = pd.read_parquet(f"{RUN}/bench.parquet", filters=[("fill_id", "in", chosen), ("rule", "==", "F1")],
                    columns=["fill_id", "coin", "alert_M", "alert_t_M", "alert_px_M"])
print(len(F), len(O), len(B))
m = sel.merge(F, on=["fill_id", "coin"], how="left", suffixes=("", "_f")) \
       .merge(O, on=["fill_id", "coin"], how="left", suffixes=("", "_o")) \
       .merge(B, on=["fill_id", "coin"], how="left")
m.to_pickle(f"{OUT}/selected.pkl")
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
print(m[["fill_id", "coin", "why", "time", "rung", "y", "r", "y_H2R", "t0", "P0", "sigma30", "tick_str", "L",
         "t_F1", "exit_kind", "exit_t", "exit_px", "target", "twin_mean", "twin_n", "twin_pooled", "delta_o",
         "r_o", "alert_M", "alert_t_M"]].to_string())
json.dump({"chosen": chosen, "why": {str(k): v for k, v in why.items()}}, open(f"{OUT}/selected.json", "w"), indent=1)
