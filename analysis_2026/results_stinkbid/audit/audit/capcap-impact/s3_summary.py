"""Step 3: summaries of the reconstructed windows (s2 outputs): quantiles per rung of the fill's own window, the life
sum, capacity up to the flip's exit and within 1 h / 6 h / 24 h / 72 h of the fill; where the life sum comes from."""
import numpy as np
import pandas as pd

OUTD = ("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
        "capcap-impact")
R = pd.read_parquet(f"{OUTD}/s2_fills.parquet")
W = pd.read_parquet(f"{OUTD}/s2_windows.parquet")
pd.set_option("display.width", 250)

bad = R[(R.my_nw != R.eng_nw)]
print("n_windows mismatches:\n", bad[["coin", "rung", "t_F1", "life_end", "my_nw", "eng_nw", "my_c1_life", "eng_c1_life",
                                      "my_agg_life", "eng_agg_life"]].to_string())

out = []
for rg, g in R.groupby("rung"):
    row = dict(rung=rg, n=len(g))
    for c in ("my_agg_first", "agg_1h", "agg_6h", "agg_24h", "agg_72h", "agg_to_exit", "agg_to_exit_incl",
              "my_agg_life"):
        v = g[c].to_numpy(float)
        v = v[np.isfinite(v)]
        row[c + "_p10"] = np.quantile(v, .1)
        row[c + "_p50"] = np.quantile(v, .5)
    out.append(row)
T = pd.DataFrame(out)
for c in [c for c in T.columns if c.endswith("_p10")]:
    T[c.replace("_p10", "_qmax")] = 0.25 * T[c]
print("\np10 per rung (USD):")
print(T[["rung", "n"] + [c for c in T.columns if c.endswith("_p10")]].to_string(index=False,
                                                                                  float_format=lambda x: f"{x:,.0f}"))
print("\nQ_max = 0.25 x p10 per rung (USD):")
print(T[["rung"] + [c for c in T.columns if c.endswith("_qmax")]].to_string(index=False,
                                                                            float_format=lambda x: f"{x:,.0f}"))
print("\np50 per rung (USD):")
print(T[["rung"] + [c for c in T.columns if c.endswith("_p50")]].to_string(index=False,
                                                                           float_format=lambda x: f"{x:,.0f}"))
# where the life sum comes from: share of the pooled life-sum dollars by window start relative to the fill
W = W.merge(R[["fill_id", "t_F1", "exit_t"]], on="fill_id")
W["lag_h"] = (W.ta - W.t_F1) / 60.0
tot = W["agg"].sum()
for lo_, hi_ in ((0, 1), (1, 6), (6, 24), (24, 72), (72, 1e9)):
    m = (W.lag_h >= lo_) & (W.lag_h < hi_)
    print(f"windows starting {lo_}-{hi_} h after the fill: {int(m.sum())} windows, {W["agg"][m].sum() / tot:.3f} of "
          f"pooled life-sum dollars")
print("pooled share of life-sum dollars in the fill's own window:", round(R.my_agg_first.sum() / R.my_agg_life.sum(), 4))
print("per fill: first / life ratio, median", round(float(np.median(R.my_agg_first / R.my_agg_life)), 4),
      "p10", round(float(np.quantile(R.my_agg_first / R.my_agg_life, .1)), 4))
print("windows after the flip's exit (start >= exit_t):", int((W.ta >= W.exit_t).sum()), "of", len(W),
      "carrying", round(W["agg"][W.ta >= W.exit_t].sum() / tot, 3), "of life-sum dollars")
print("flip exit kinds:", R.exit_kind.value_counts().to_dict())
print("hours from fill to flip exit: median", round(float(((R.exit_t - R.t_F1) / 60).median()), 1), "p90",
      round(float(((R.exit_t - R.t_F1) / 60).quantile(.9)), 1))
# per-window quantiles for a sanity line: all windows pooled
print("all windows pooled: n", len(W), "median agg", f"{W["agg"].median():,.0f}", "p10", f"{W["agg"].quantile(.1):,.0f}")
# with theta = 1 and 0.25: share of fills whose own window would fully fill a $10k / $100k order
for Q in (1e4, 1e5):
    for th in (1.0, 0.25):
        print(f"Q ${Q:,.0f} theta {th}: own window fills it in full for {np.mean(th * R.my_agg_first >= Q):.3f} of fills; "
              f"by the flip exit {np.mean(th * R.agg_to_exit >= Q):.3f}; by the life end {np.mean(th * R.my_agg_life >= Q):.3f}")
T.to_csv(f"{OUTD}/s3_summary.csv", index=False)
