# What is K3's null statistic for H4, and what critical value would its simulation-calibrated rule use?
import json, math
import numpy as np
from scipy import stats
c = json.load(open("analysis_2026/results_stinkbid/controls/k3_calibration.json"))
print("top keys:", list(c.keys()))
print("tests keys:", list(c.get("tests", {}).keys()))
h4 = c["tests"]["H4"]
print("H4 test keys:", list(h4.keys()))
for k, v in h4.items():
    if not isinstance(v, (dict, list)):
        print("  ", k, "=", v)
for sc, d in (c.get("null", {}).get("H4") or {}).items():
    print("null H4", sc, "keys", list(d.keys()))
    st = np.asarray(d.get("stat", []), float)
    st = st[np.isfinite(st)]
    srt = np.sort(st)[::-1]
    n = len(srt)
    for a in (0.05/3, 0.025, 0.05):
        m = math.ceil(a * (n + 1) - 1) - 1
        print(f"   n={n}  alpha={a:.4f}  crit (stat of rank m={m}) = {srt[m]:.4f}   quantile(1-a)={np.quantile(st, 1-a):.4f}")
    for kk in ("gstar", "se", "p", "pivot"):
        if kk in d:
            arr = np.asarray(d[kk], float); arr = arr[np.isfinite(arr)]
            print(f"   {kk}: median {np.median(arr):.4f}, mean {np.mean(arr):.4f}")
# single-test and Bonferroni t crit at the controls' H4 G* (median 11.53)
gs = 11.527735838179506
print("t crit 0.05/3 at G*-1:", stats.t.ppf(1-0.05/3, gs-1), " 0.05/12:", stats.t.ppf(1-0.05/12, gs-1))
