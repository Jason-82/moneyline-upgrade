"""Reproduce the capacity numbers of the finding from P1__U_Q1/fills.parquet (read-only, small columns)."""
import numpy as np
import pandas as pd

P = "data/stinkbid/runs/outcomes/P1__U_Q1/fills.parquet"
cols = ["coin", "rung", "t_F1", "i_F1", "bid_id", "fill_id", "L", "live_from", "life_end", "n_windows",
        "c1_first", "c1_life", "agg_first", "agg_life", "agg_missing", "cap_src", "c1_m0", "agg_m0",
        "share_10k_1", "share_100k_0.25", "share_100k_1", "t_full_100k_0.25"]
F = pd.read_parquet(P, columns=cols)
print("rows", len(F))
f = F[F.t_F1 >= 0].copy()
print("F1 fills", len(f))
print("cap_src counts", f.cap_src.value_counts(dropna=False).to_dict())
print("agg_missing", f.agg_missing.value_counts(dropna=False).to_dict())
print("agg_first >= agg_m0 for all:", bool((f.agg_first >= f.agg_m0 - 1e-9).all()),
      "; NaN agg_first:", int(f.agg_first.isna().sum()), "; NaN agg_life:", int(f.agg_life.isna().sum()))

def q(v, p):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    return float(np.quantile(v, p)) if len(v) else np.nan

print("\nper rung (np.quantile linear):")
for rg, g in f.groupby("rung"):
    print(f" k={rg:g} n={len(g)}  agg_life p10={q(g.agg_life, .1):,.0f} p50={q(g.agg_life, .5):,.0f} "
          f"Qmax_life={0.25*q(g.agg_life, .1):,.0f} | agg_first p10={q(g.agg_first, .1):,.0f} "
          f"p50={q(g.agg_first, .5):,.0f} Qmax_first={0.25*q(g.agg_first, .1):,.0f} | "
          f"ratio p10 life/first={q(g.agg_life, .1)/q(g.agg_first, .1):.1f}")
print("\nall: n_windows median", f.n_windows.median(), "p90", q(f.n_windows, .9), "mean", round(f.n_windows.mean(), 1),
      "share with 1 window", round((f.n_windows == 1).mean(), 3))
for c in ("c1_first", "c1_life", "agg_first", "agg_life"):
    print(f" {c}: median {q(f[c], .5):,.0f}  p10 {q(f[c], .1):,.0f}  p25 {q(f[c], .25):,.0f}")
print(" share of fills with agg_first < $10k:", round(float((f.agg_first < 1e4).mean()), 3),
      " < $40k:", round(float((f.agg_first < 4e4).mean()), 3), " < $400k:", round(float((f.agg_first < 4e5).mean()), 3))
print(" share of fills with agg_life < $400k:", round(float((f.agg_life < 4e5).mean()), 3))
# results-of-record numbers
print("\nprinted: k=6 p10 407,629 cap 101,907; k=8 327,952 / 81,988; k=10 307,280 / 76,820")
f.to_parquet("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/capcap_refute/f1_cap.parquet")
