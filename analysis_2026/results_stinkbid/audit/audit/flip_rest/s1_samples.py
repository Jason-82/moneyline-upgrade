"""Step 1: recompute H1 and H2R from primary/samples_*.csv (y, mb, ep), compare with primary.json / verdicts.csv."""
import json
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest")
import mystats as M

R = "analysis_2026/results_stinkbid"
P = json.load(open(f"{R}/primary/primary.json"))
V = pd.read_csv(f"{R}/verdicts.csv").set_index("test")

out = {}
for test, E in (("H1", 0.0375), ("H2R", 0.02)):
    d = pd.read_csv(f"{R}/primary/samples_{test}.csv")
    print(f"==== {test}: rows {len(d)}; time sorted: {pd.to_datetime(d['time']).is_monotonic_increasing}; "
          f"fill_id unique: {d['fill_id'].is_unique}; y finite: {np.isfinite(d['y']).all()}")
    # rebuild month-blocks and episodes from the sample's own fill times
    mb, ep = M.my_month_blocks(d["time"])
    same_mb = (pd.crosstab(mb, d["mb"]).gt(0).sum(1).max() == 1) and (pd.crosstab(d["mb"], mb).gt(0).sum(1).max() == 1)
    same_ep = (pd.crosstab(ep, d["ep"]).gt(0).sum(1).max() == 1) and (pd.crosstab(d["ep"], ep).gt(0).sum(1).max() == 1)
    print(f"my month-blocks == file mb (bijection): {same_mb}  (G mine {len(np.unique(mb))}, file {d['mb'].nunique()}); "
          f"my episodes == file ep: {same_ep} (mine {len(np.unique(ep))}, file {d['ep'].nunique()})")
    hf = (pd.to_datetime(d["time"], utc=True) >= pd.Timestamp("2023-01-01", tz="UTC")).astype(int).to_numpy()
    print(f"half flag == file hf: {(hf == d['hf'].to_numpy()).all()}")
    y = d["y"].to_numpy(float)
    rows = {}
    rows["their_seed"] = M.test_mean(y, d["mb"].to_numpy(), E=E, seed=20261118)
    for s in (1, 2, 3, 4, 5):
        rows[f"seed{s}"] = M.test_mean(y, d["mb"].to_numpy(), E=E, seed=s)
    ref = P["rows"][test]
    print(f"{'quantity':<10} {'file':>14} {'mine(their seed)':>18} " + " ".join(f"{'seed'+str(s):>10}" for s in (1, 2, 3, 4, 5)))
    for k in ("n", "G", "gstar", "est", "se", "t", "df", "p_gstar", "p_wcr", "ub_boot", "ub_t", "ub", "p_decide", "mde"):
        fk = {"est": "estimate"}.get(k, k)
        fv = ref.get(fk)
        mine = rows["their_seed"][k]
        others = " ".join(f"{rows[f'seed{s}'][k]:>10.6g}" for s in (1, 2, 3, 4, 5))
        print(f"{k:<10} {fv!s:>14.14} {mine:>18.10g} {others}")
    print("ci95 file", ref["ci95"], "mine", rows["their_seed"]["ci95"])
    print("ci95_boot file", ref["ci95_boot"], "mine", rows["their_seed"]["ci95_boot"])
    print("k_exceed (restricted t* >= t):", {k: v["k_exceed"] for k, v in rows.items()},
          " alt p = k/B:", {k: round(v["p_wcr_kB"], 5) for k, v in rows.items()})
    # MC error of p_wcr: binomial sd
    p = rows["their_seed"]["p_wcr"]
    print(f"p_wcr MC sd ~ {np.sqrt(p * (1 - p) / 9999):.5f}")
    # verdicts.csv comparison
    v = V.loc[test]
    print("verdicts.csv:", {k: v[k] for k in ("estimate", "se", "n", "G", "gstar", "p_wcr", "p_gstar", "p_decide", "ub", "mde")})
    out[test] = rows["their_seed"]
    out[test]["mean_r"] = float(d["r"].mean()) if "r" in d else None

json.dump({k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in out.items()},
          open("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest/s1_out.json", "w"),
          indent=1, default=float)
