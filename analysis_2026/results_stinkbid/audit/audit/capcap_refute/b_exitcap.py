"""Capacity accumulated before the X-FLIP exit (rule M, C-RH, F1) per F1 fill, from cap_curve read by row group.
Also: capacity accumulated within the first N hours after the fill, and the first window's end time."""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

D = "data/stinkbid/runs/outcomes/P1__U_Q1/"
S = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/capcap_refute/"
f = pd.read_parquet(S + "f1_cap.parquet")
O = pd.read_parquet(D + "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "exit_t", "exit_kind",
                                                      "r"],
                    filters=[("rule", "==", "F1"), ("exit", "==", "FLIP")])
print("FLIP F1 rows by (lat, cost):", O.groupby(["lat", "cost"]).size().to_dict())
o = O[O.cost == "C-RH"]
if o.lat.nunique() > 1:
    print("lat values", o.lat.unique())
o = o.drop_duplicates("fill_id")
f = f.merge(o[["fill_id", "exit_t", "exit_kind", "r"]], on="fill_id", how="left")
print("F1 fills with a FLIP C-RH exit:", int(f.exit_t.notna().sum()), "of", len(f))
te = dict(zip(f.bid_id.astype(np.int64), f.exit_t.to_numpy(float)))
tf = dict(zip(f.bid_id.astype(np.int64), f.t_F1.astype(np.int64)))
H = (1, 2, 6, 24, 72)
acc = {"exit": {}, **{h: {} for h in H}, "life": {}}
pf = pq.ParquetFile(D + "cap_curve.parquet")
mono_bad = 0
for k in range(pf.num_row_groups):
    t = pf.read_row_group(k, columns=["bid_id", "minute", "cum"]).to_pandas()
    t = t[t.bid_id.isin(te.keys())]
    for bid, g in t.groupby("bid_id"):
        m = g.minute.to_numpy(np.int64)
        c = g.cum.to_numpy(float)
        if np.any(np.diff(c) < -1e-6):
            mono_bad += 1
        b = int(bid)
        e = te[b]
        if np.isfinite(e):
            v = c[m < e]
            acc["exit"][b] = max(acc["exit"].get(b, 0.0), float(v.max()) if len(v) else 0.0)
        for h in H:
            v = c[m < tf[b] + 60 * h]
            acc[h][b] = max(acc[h].get(b, 0.0), float(v.max()) if len(v) else 0.0)
        acc["life"][b] = max(acc["life"].get(b, 0.0), float(c.max()))
    del t
print("row groups", pf.num_row_groups, "; bids whose cum decreases:", mono_bad)
for key, d in acc.items():
    f["cap_" + str(key)] = f.bid_id.map(d)
print("cap_life == agg_life (rel 1e-9):", bool(np.allclose(f.cap_life.fillna(0), f.agg_life, rtol=1e-9, atol=1e-6)),
      "; bids missing from curve:", int(f.cap_life.isna().sum()))

def q(v, p):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return float(np.quantile(v, p)) if len(v) else np.nan

print("\np10 / p50 by rung, capacity accumulated before ... (and 0.25 x p10)")
for rg, g in f.groupby("rung"):
    s = [f"k={rg:g} n={len(g)}"]
    for c in ["agg_first"] + [f"cap_{h}" for h in H] + ["cap_exit", "agg_life"]:
        s.append(f"{c}: p10 {q(g[c], .1):,.0f} (cap {0.25*q(g[c], .1):,.0f}) p50 {q(g[c], .5):,.0f}")
    print("\n  ".join(s))
# exit timing
dt = (f.exit_t - f.t_F1) / 60.0
print("\nhours from fill to flip exit: median", round(float(dt.median()), 1), "p10", round(q(dt, .1), 2),
      "p90", round(q(dt, .9), 1), "; exit kinds", f.exit_kind.value_counts().to_dict())
# share of the life capacity that came before the flip exit
sh = f.cap_exit / f.agg_life
print("share of life capacity printed before the flip exit: median", round(q(sh, .5), 3), "p10", round(q(sh, .1), 3))
f.to_parquet(S + "f1_cap_exit.parquet")
