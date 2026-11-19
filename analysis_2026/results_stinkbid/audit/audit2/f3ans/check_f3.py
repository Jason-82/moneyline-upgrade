"""Read-only check: F3 (s = 1%) versions of the answer's F1-only numbers (worst day, MoneyLine split, knife, r_f)
on the cached P1/U-Q1 run, using the record's (eee2ddf) desc functions. Never loads cap_curve.parquet."""
import importlib.util
import resource
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/home/user/moneyline-upgrade")
sys.path.insert(0, str(REPO))
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("desc_eee", HERE / "desc_eee.py")
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)

RUN = REPO / "data/stinkbid/runs/outcomes/P1__U_Q1"
bids = pd.read_parquet(RUN / "bids.parquet")
fills = pd.read_parquet(RUN / "fills.parquet")
bench = pd.read_parquet(RUN / "bench.parquet", columns=["fill_id", "rule", "coin", "knife", "twin_knife", "alert_72h"])
outs = pd.read_parquet(RUN / "outcomes.parquet",
                       columns=["rule", "exit", "lat", "cost", "fill_id", "coin", "r", "delta", "complete", "twin_mean"])
res = dict(bids=bids, fills=fills, bench=bench, outcomes=outs)
print("rows: bids", len(bids), "fills", len(fills), "bench", len(bench), "outcomes", len(outs))
print("F1 fills", int((fills.t_F1 >= 0).sum()), " F3_1 fills", int((fills.t_F3_1 >= 0).sum()),
      " F3-only", int(((fills.t_F1 < 0) & (fills.t_F3_1 >= 0)).sum()))

# 1. worst day (record function), F1 and F3_1
bft = D.bid_fill_table(res, ("F1", "F3_1"))
print("worst day F1  :", D.worst_day(bft, "t_F1"))
print("worst day F3_1:", D.worst_day(bft, "t_F3_1"))

# 2. MoneyLine split: record function on F1; same rule on F3_1 fills
print("ml split F1  :", D.ml_split(fills))
f3 = fills[fills.t_F3_1 >= 0]
st = f3["ml_d0"].to_numpy()
n_def = int(np.isin(st, (0, 1)).sum())
print("ml split F3_1:", dict(n=len(f3), red=int((st == 0).sum()), green=int((st == 1).sum()),
                             undefined=int((st == -1).sum()), red_share=(st == 0).sum() / n_def))

# 3. knife on bench rows per rule
for rule, g in bench.groupby("rule"):
    k = pd.to_numeric(g["knife"], errors="coerce").to_numpy(float)
    print(f"bench rule {rule:6s}: rows {len(g):5d}, finite knife {int(np.isfinite(k).sum()):5d}")
kn = D.per_bench(res, "F1", "knife")
print("TAIL_BOTTOM F1: A", kn["y"].mean(), "B", np.nanmean(pd.to_numeric(kn["twin_knife"], errors="coerce")), "n", len(kn))
kn3 = D.per_bench(res, "F3_1", "knife")
print("TAIL_BOTTOM F3_1 rows with a finite knife:", len(kn3))

# 4. mean r_f of the flip (X-FLIP, rule M) on F1 (C-RH) and F3_1 (RH)
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    o = outs[(outs.rule == rule) & (outs.exit == "FLIP") & (outs.cost == cost) & (outs.lat == "M")]
    o = o[o.complete.astype(bool)]
    f = fills[fills["t_" + rule] >= 0]
    d = f[["fill_id"]].merge(o, on="fill_id")
    r = d["r"].to_numpy(float)
    print(f"mean r_f {rule}: {np.nanmean(r):+.4%} over {int(np.isfinite(r).sum())} fills")

print("peak RSS MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
