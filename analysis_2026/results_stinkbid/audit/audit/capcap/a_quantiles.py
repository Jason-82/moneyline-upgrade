"""Part A: per-rung capacity quantiles of P1/U-Q1 F1 fills, read straight from fills.parquet (own code).

Compares the printed size cap (answer.json numbers.capacity) with:
  - agg_life (sum over every capacity window from the fill to the order's expiry)  -> what the report used?
  - agg_first (the fill's own capacity window, draft §8.3)
and checks agg_first >= agg_m0 (the fill minute lies inside the first window), window counts, c1 scales.
"""
import json
import numpy as np
import pandas as pd

RUN = "data/stinkbid/runs/outcomes/P1__U_Q1/fills.parquet"
cols = ["coin", "rung", "t_F1", "bid_id", "fill_id", "L", "n_windows", "c1_first", "c1_life", "agg_first",
        "agg_life", "agg_missing", "cap_src", "c1_m0", "agg_m0", "life_end", "t0"]
F = pd.read_parquet(RUN, columns=cols)
print("fills.parquet rows:", len(F))
f = F[F.t_F1 >= 0].copy()
print("F1 fills (t_F1 >= 0):", len(f))
print("cap_src counts:", f.cap_src.value_counts(dropna=False).to_dict())
print("agg_missing counts:", f.agg_missing.value_counts(dropna=False).to_dict())
print("agg_life NaN:", int(f.agg_life.isna().sum()), " agg_first NaN:", int(f.agg_first.isna().sum()))

ans = json.load(open("analysis_2026/results_stinkbid/answer.json"))
printed = {float(r["rung"]): r for r in ans["numbers"]["capacity"]}

# my own capacity per fill: aggTrades where cap_src == 'agg', else C1 (the §7 rule), for both windows
is_agg = (f.cap_src.astype(str) == "agg").to_numpy()
life = np.where(is_agg, f.agg_life.to_numpy(float), f.c1_life.to_numpy(float))
first = np.where(is_agg, f.agg_first.to_numpy(float), f.c1_first.to_numpy(float))

print("\nper rung: printed vs life-sum vs first window (np.quantile, linear)")
hdr = f"{'k':>4} {'n':>5} {'printed p10':>14} {'life p10':>14} {'life p50':>14} {'first p10':>12} {'first p50':>12} " \
      f"{'cap printed':>12} {'cap life':>12} {'cap first':>10} {'ratio':>6}"
print(hdr)
out = {}
for k in (6.0, 8.0, 10.0):
    m = f.rung.to_numpy(float) == k
    lf, fs = life[m], first[m]
    lf, fs = lf[np.isfinite(lf)], fs[np.isfinite(fs)]
    p = printed[k]
    r = dict(n=int(m.sum()), printed_p10=p["C_p10"], printed_p50=p["C_p50"], printed_cap=p["Q_max"],
             life_p10=float(np.quantile(lf, .1)), life_p50=float(np.median(lf)),
             first_p10=float(np.quantile(fs, .1)), first_p50=float(np.median(fs)))
    r["cap_life"], r["cap_first"] = .25 * r["life_p10"], .25 * r["first_p10"]
    out[k] = r
    print(f"{k:>4g} {r['n']:>5} {r['printed_p10']:>14,.0f} {r['life_p10']:>14,.0f} {r['life_p50']:>14,.0f} "
          f"{r['first_p10']:>12,.0f} {r['first_p50']:>12,.0f} {r['printed_cap']:>12,.0f} {r['cap_life']:>12,.0f} "
          f"{r['cap_first']:>10,.0f} {r['cap_life'] / r['cap_first']:>6.1f}")
    assert abs(r["life_p10"] - p["C_p10"]) < 1e-6 * p["C_p10"], "printed p10 != life-sum p10"
    assert abs(r["life_p50"] - p["C_p50"]) < 1e-6 * p["C_p50"], "printed p50 != life-sum p50"
print("=> printed C_p10 and C_p50 equal the life-sum quantiles exactly (asserted)")

# fill minute inside the first window
ok = np.isfinite(f.agg_m0.to_numpy(float)) & np.isfinite(f.agg_first.to_numpy(float))
print("\nagg_m0 finite:", int(ok.sum()), "of", len(f), "; agg_first >= agg_m0 for",
      int((f.agg_first.to_numpy(float)[ok] >= f.agg_m0.to_numpy(float)[ok] - 1e-9).sum()))
nw = f.n_windows.to_numpy(float)
print("windows per fill: median", np.median(nw), " p90", np.quantile(nw, .9), " mean", nw.mean().round(2),
      " share with 1 window", np.mean(nw == 1).round(4))
print("agg_life / agg_first per fill: median", np.nanmedian(f.agg_life / f.agg_first).round(2),
      " p10", np.nanquantile(f.agg_life / f.agg_first, .1).round(2), " p90", np.nanquantile(f.agg_life / f.agg_first, .9).round(1))
for c in ("c1_first", "c1_life", "agg_first", "agg_life"):
    v = f[c].to_numpy(float)
    v = v[np.isfinite(v)]
    print(f"{c:>9}: median ${np.median(v):>14,.0f}   p10 ${np.quantile(v, .1):>12,.0f}   p25 ${np.quantile(v, .25):>12,.0f}"
          f"   share < $100k {np.mean(v < 1e5):.3f}   share < $10k {np.mean(v < 1e4):.3f}")
# share of fills whose first window could not fill a $100k order at theta = 1 / 0.25
for th in (1.0, .25):
    print(f"theta={th}: share of F1 fills with theta*C_first < $100k: {np.mean(th * first < 1e5):.3f}; "
          f"with theta*C_life < $100k: {np.mean(th * life < 1e5):.3f}")
# fill share at Q = printed cap, first window, theta = 0.25 (the cap's own theta)
for k in (6.0, 8.0, 10.0):
    m = f.rung.to_numpy(float) == k
    Q = out[k]["printed_cap"]
    sh_first = np.minimum(1.0, .25 * first[m] / Q)
    sh_life = np.minimum(1.0, .25 * life[m] / Q)
    print(f"k={k:g}: an order of the printed cap ${Q:,.0f}: share filled in full within the fill's own window "
          f"(theta .25) {np.mean(sh_first >= 1):.3f}, mean share {sh_first.mean():.3f}; over the life {np.mean(sh_life >= 1):.3f}")
json.dump({str(k): v for k, v in out.items()},
          open("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/capcap/a_out.json", "w"), indent=1)
