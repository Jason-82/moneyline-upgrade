"""Step 2: my statistics on the four per-fill samples, against the printed rows of record (primary.json)."""
import sys
import json
import numpy as np
import pandas as pd

OUT = sys.argv[1]
sys.path.insert(0, OUT)
import mystats as ms

P = json.load(open("analysis_2026/results_stinkbid/primary/primary.json"))
out = {}
for key, val in [("F1/FLIP", "delta"), ("F1/FLIP_bot", "delta"), ("F3_1/FLIP", "delta"), ("F3_1/FLIP_bot", "delta"),
                 ("F1/FLIP", "r"), ("F3_1/FLIP", "r"), ("F1/FLIP_bot", "r"), ("F3_1/FLIP_bot", "r")]:
    rule, ex = key.split("/")
    d = pd.read_parquet(f"{OUT}/rows_{rule}_{ex}.parquet")
    r = ms.full_test(d[val].to_numpy(float), d["mb"].to_numpy())
    # gates as in §10.3 (halves, worst month-block, biggest episode)
    y = d[val].to_numpy(float)
    half = (d["time"] >= pd.Timestamp("2023-01-01", tz="UTC")).to_numpy()
    mbs = d["mb"].to_numpy()
    eps = d["ep"].to_numpy()
    # worst month-block: the block whose removal lowers the mean most; biggest episode: most fills
    worst = min(np.mean(y[mbs != b]) for b in np.unique(mbs))
    u, c = np.unique(eps, return_counts=True)
    big = u[np.argmax(c)]
    r.update(half1=float(y[~half].mean()), half2=float(y[half].mean()), without_worst_block=float(worst),
             without_biggest_episode=float(y[eps != big].mean()))
    out[f"{key}:{val}"] = r
    print(f"{key:14s} {val:5s} n {r['n']} est {r['estimate']:+.6f} se {r['se']:.6f} G {r['G']} G* {r['gstar']:.3f} "
          f"t {r['t']:.3f} p_G* {r['p_gstar']:.6f} p_WCR {r['p_wcr']:.4f} ub_t {r['ub_t']:+.5f} "
          f"ub_boot {r['ub_boot']:+.5f} ci95 [{r['ci95'][0]:+.5f}, {r['ci95'][1]:+.5f}] mde {r['mde']:.5f} "
          f"h1 {r['half1']:+.4f} h2 {r['half2']:+.4f} -wb {r['without_worst_block']:+.4f} "
          f"-be {r['without_biggest_episode']:+.4f}")

print("\nrecord rows:")
for nm, row in [("H1 (rows)", P["rows"]["H1"]), ("bot (row)", P["bot"]["row"])]:
    print(f"{nm:10s} n {row['n']} est {row['estimate']:+.6f} se {row['se']:.6f} G {row['G']} G* {row['gstar']:.3f} "
          f"p_G* {row['p_gstar']:.6f} p_WCR {row['p_wcr']:.4f} ub_t {row['ub_t']:+.5f} ub_boot {row['ub_boot']:+.5f} "
          f"ci95 {row['ci95']} mde {row['mde']:.5f}")
b = P["beside"]["H1"]["F3_1"]
print(f"beside F3_1 n {b['n']} est {b['estimate']:+.6f} se {b['se']:.6f} G {b['G']} G* {b['gstar']:.3f} "
      f"ci [{b['ci_lo']:+.5f}, {b['ci_hi']:+.5f}] mde {b['mde']:.5f}")
print("beside mean_r", P["beside"]["H1"]["mean_r"])
json.dump(out, open(f"{OUT}/s2_stats.json", "w"), indent=1, default=float)
