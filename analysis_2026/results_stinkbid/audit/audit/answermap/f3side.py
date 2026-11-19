import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/answermap")
from core import ts, month_blocks, quarter_blocks, cr1, RUNS
DAY = 1440
run = RUNS + "/P1__U_Q1"
F = pd.read_parquet(run + "/fills.parquet", columns=["fill_id", "bid_id", "t_F1", "t_F3_1", "ml_d0", "rung"])
O = pd.read_parquet(run + "/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "delta", "complete"])
Bn = pd.read_parquet(run + "/bench.parquet", columns=["fill_id", "rule", "alert_72h", "knife", "twin_knife"])
f3 = F[F.t_F3_1 >= 0]
out = {}
o = O[(O.rule == "F3_1") & (O.exit == "HOLD90") & (O.cost == "RH") & O.complete.astype(bool)]
d = f3[["fill_id", "t_F3_1"]].merge(o[["fill_id", "delta"]], on="fill_id"); d = d[np.isfinite(d.delta)]
d["time"] = ts(d.t_F3_1)
out["dh2_F3"] = {k: float(v) for k, v in cr1(d.delta, quarter_blocks(d["time"])).items()}
b = Bn[Bn.rule == "F3_1"].merge(f3[["fill_id", "t_F3_1", "ml_d0"]], on="fill_id")
a = b[np.isfinite(pd.to_numeric(b.alert_72h, errors="coerce"))].copy(); a["time"] = ts(a.t_F3_1)
mb, _ = month_blocks(a["time"])
out["d8p1_F3"] = {k: float(v) for k, v in cr1(a.alert_72h.astype(float), mb).items()}
kn = pd.to_numeric(b.knife, errors="coerce")
out["knife_F3_rows"] = dict(n_finite=int(np.isfinite(kn).sum()), A=float(np.nanmean(kn)) if np.isfinite(kn).any() else None,
                            B=float(np.nanmean(pd.to_numeric(b.twin_knife, errors="coerce"))) if np.isfinite(kn).any() else None)
out["ml_F3"] = f3.ml_d0.value_counts().to_dict()
# worst day on F3 (same live definition)
bids = pd.read_parquet(run + "/bids.parquet", columns=["bid_id", "coin", "rung", "variant", "live_from", "life_end"])
bids = bids.merge(F[["bid_id", "t_F3_1"]], on="bid_id", how="left"); bids["t_F3_1"] = bids.t_F3_1.fillna(-1).astype(np.int64)
fd = np.where(bids.t_F3_1 >= 0, bids.t_F3_1 // DAY, -1)
slot = (bids.coin.astype(str) + "|" + bids.rung.astype(str) + "|" + bids.variant.astype(str)).to_numpy()
lf, le, tf = bids.live_from.to_numpy(), bids.life_end.to_numpy(), bids.t_F3_1.to_numpy()
best = None
for dd in np.unique(fd[fd >= 0]):
    s, e = dd * DAY, (dd + 1) * DAY
    live = (lf < e) & (le > s) & ((tf < 0) | (tf >= s))
    nl, nf = len(np.unique(slot[live])), len(np.unique(slot[fd == dd]))
    if best is None or nf / nl > best[3]:
        best = (str(ts([s])[0].date()), nf, nl, nf / nl)
out["worst_day_F3"] = best
print(json.dumps(out, indent=1, default=str))
