"""Step 1 (light): the capacity numbers of record against the per-window and per-life capacity columns of
P1__U_Q1/fills.parquet. Own code; reads only the columns needed."""
import json
import numpy as np
import pandas as pd

RUN = "data/stinkbid/runs/outcomes/P1__U_Q1"
cols = ["coin", "rung", "t_F1", "i_F1", "L", "L_tau", "tick", "cap_src", "n_windows", "c1_first", "c1_life",
        "agg_first", "agg_life", "agg_missing", "agg_m0", "c1_m0", "bid_id", "fill_id", "live_from", "life_end",
        "share_10k_1", "share_10k_0.25", "share_100k_1", "share_100k_0.25", "in_U_C"]
F = pd.read_parquet(f"{RUN}/fills.parquet", columns=cols)
f = F[F.t_F1 >= 0].copy()
print("fills rows", len(F), "F1 fills", len(f))
print("cap_src", f.cap_src.value_counts(dropna=False).to_dict(), "agg_missing", int(f.agg_missing.sum()))

ans = json.load(open("analysis_2026/results_stinkbid/answer.json"))["numbers"]["capacity"]
rec = {float(r["rung"]): r for r in ans}

is_agg = (f.cap_src.astype(str) == "agg").to_numpy()
life = np.where(is_agg, f.agg_life.to_numpy(float), f.c1_life.to_numpy(float))
first = np.where(is_agg, f.agg_first.to_numpy(float), f.c1_first.to_numpy(float))
f["life"], f["first"] = life, first

print("\nper rung: record vs np.quantile of life-sum and of first window (pooled over coins)")
out = []
for rg, g in f.groupby("rung"):
    lv = g.life.to_numpy(); lv = lv[np.isfinite(lv)]
    fv = g["first"].to_numpy(); fv = fv[np.isfinite(fv)]
    r = rec[float(rg)]
    row = dict(rung=rg, n=len(g), rec_p50=r["C_p50"], rec_p10=r["C_p10"], rec_qmax=r["Q_max"],
               life_p50=np.quantile(lv, .5), life_p10=np.quantile(lv, .1),
               first_p50=np.quantile(fv, .5), first_p10=np.quantile(fv, .1))
    row["first_qmax"] = 0.25 * row["first_p10"]
    row["ratio_life_first_p10"] = row["life_p10"] / row["first_p10"]
    row["match_rec_life"] = bool(np.isclose(row["rec_p10"], row["life_p10"], rtol=1e-12) and
                                 np.isclose(row["rec_p50"], row["life_p50"], rtol=1e-12))
    out.append(row)
T = pd.DataFrame(out)
pd.set_option("display.width", 250)
print(T.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

print("\nn_windows per F1 fill: median %.1f p90 %.1f mean %.1f max %d; share with 1 window %.3f" % (
    np.median(f.n_windows), np.quantile(f.n_windows, .9), f.n_windows.mean(), f.n_windows.max(),
    (f.n_windows == 1).mean()))
for rg, g in f.groupby("rung"):
    print("  rung", rg, "median windows", np.median(g.n_windows), "p90", np.quantile(g.n_windows, .9))

print("\nagg_first >= agg_m0 (fill minute inside first window):",
      int((f.agg_first + 1e-9 >= f.agg_m0).sum()), "of", int(f.agg_m0.notna().sum()))
print("agg_first <= agg_life:", int((f.agg_first <= f.agg_life + 1e-6).sum()), "of", len(f))
print("\npooled over all F1 fills (1-minute approximation C1):")
for c in ("c1_first", "c1_life", "agg_first", "agg_life"):
    v = f[c].to_numpy(float); v = v[np.isfinite(v)]
    print(f"  {c:10s} n={len(v)} median ${np.median(v):,.0f} p10 ${np.quantile(v, .1):,.0f} p25 ${np.quantile(v, .25):,.0f}"
          f" share<10k {np.mean(v < 1e4):.3f} share<100k {np.mean(v < 1e5):.3f}")
# the record's D4 shares are computed on the life sum; the same shares on the first window
for Q in (1e4, 1e5):
    for th in (1.0, 0.25):
        s_first = np.minimum(1.0, th * first / Q)
        s_life = np.minimum(1.0, th * life / Q)
        print(f"  Q=${Q:,.0f} theta={th}: mean share filled life {np.nanmean(s_life):.3f} (full {np.nanmean(s_life >= 1):.3f});"
              f" first window {np.nanmean(s_first):.3f} (full {np.nanmean(s_first >= 1):.3f})")
# engine's share column check
print("  engine share_10k_1 mean", f["share_10k_1"].mean(), "share_100k_0.25 mean", f["share_100k_0.25"].mean())
T.to_csv("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
         "capcap-impact/s1_quantiles.csv", index=False)
