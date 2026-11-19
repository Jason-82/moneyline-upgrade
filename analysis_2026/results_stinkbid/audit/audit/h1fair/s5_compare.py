"""Step 5: compare the independent bar pass with the engine (fill validity, targets, exits, r_f, twin means)."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
import numpy as np
import pandas as pd
from common import *

R = pd.read_parquet(f"{OUT}/bars_pass.parquet")
O = pd.read_parquet(f"{OUT}/h1rows2.parquet")
print("rows", len(R), "found", R.found.sum())
print("F1 validity: live", R.live.sum(), "low<=L-tau", R.low_ok.sum(), "first in life", R.first.sum(),
      " seg match", (R.seg_me == R.seg_eng).sum())
print("target match (exact):", (R.T_me == R.T_eng).sum(), " max rel diff:",
      np.nanmax(np.abs(R.T_me / R.T_eng - 1)))
print("exit kind match:", (R.kind_me == R.kind_eng).sum(), " exit_t match:", (R.exit_t_me == R.exit_t_eng).sum(),
      " crossed (exit window crosses a segment):", R.crossed.sum())
d = np.abs(R.r_me - R.r_eng)
print("r_f |diff| <= 1e-12:", (d <= 1e-12).sum(), " max |diff|:", np.nanmax(d))
bad = R[(R.kind_me != R.kind_eng) | (d > 1e-9)]
print("mismatched fills:\n", bad[["fill_id", "coin", "kind_me", "kind_eng", "exit_t_me", "exit_t_eng", "r_me", "r_eng",
                                  "crossed"]].to_string())
# ---- twins
print("\npooled flag match:", (R.pooled_me == R.pooled_eng).sum(), "of", len(R),
      " me pooled:", R.pooled_me.sum(), " engine pooled:", R.pooled_eng.sum())
mm = R[R.pooled_me != R.pooled_eng]
print(mm[["fill_id", "coin", "elig_days", "elig_min", "pooled_me", "pooled_eng"]].to_string())
own = R[~R.pooled_me & ~R.pooled_eng].copy()
dt = (own.twin_me - own.twin_eng).abs()
print("own-twin fills:", len(own), " twin mean |diff| <= 1e-12:", (dt <= 1e-12).sum(), " <= 1e-6:",
      (dt <= 1e-6).sum(), " max:", dt.max())
print("twins crossing a segment (my simplified code may differ there):", own.twin_crossed.sum(),
      "in", (own.twin_crossed > 0).sum(), "fills")
x = own[dt > 1e-9]
print("mismatched twin means:", len(x), " of which with crossing twins:", (x.twin_crossed > 0).sum())
print(x[["fill_id", "coin", "twin_me", "twin_eng", "twin_crossed", "twin_n_me"]].head(30).to_string())
print("twin entries >182 d from the fill: min distance (days):", own.twin_min_dist_d.min())
print("twin n per fill (mine):", own.twin_n_me.describe().to_dict())
# mean twin hit rates
print("\ntwin target-hit rate (mine, own twins):", own.twin_hit_rate.mean(), " marketable:", own.twin_mkt_rate.mean())
M = own.merge(O[["fill_id", "exit_kind"]], on="fill_id")
print("fill target-hit rate (engine, same fills):", (M.exit_kind == "target").mean())
# H1 with my twin means (own fills) vs engine
Q = O.merge(R[["fill_id", "twin_me", "r_me", "pooled_me"]], on="fill_id")
Q["delta_me"] = Q.r_me - np.where(Q.pooled_me, Q.twin_mean, Q.twin_me)
print("H1 with my r_f and my own-twin means (engine pooled means for the 149):", fmt(cr1(Q.delta_me, Q.mb_me)))
R.merge(O[["fill_id", "mb_me", "ep_me", "rung", "year", "exit_kind", "delta", "r", "twin_mean", "twin_pooled", "ts",
           "t_F1", "L", "P0", "half"]], on="fill_id").to_parquet(f"{OUT}/joined.parquet")
