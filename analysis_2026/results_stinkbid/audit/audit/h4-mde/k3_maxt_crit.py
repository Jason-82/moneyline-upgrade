"""From K3's own null replications of H4's decisive statistic T = max_j t_j (controls/k3_calibration.json), the
critical value at 1 - 0.05/3 (and at 1 - 0.05), next to the single-test t quantile the reported MDE uses and the
Bonferroni one; the MDE each implies with M7's real SE and G*. Also the K3 power-grid rows for H4 (power.json)."""
import json
import math

import numpy as np
from scipy import stats

R = "analysis_2026/results_stinkbid"
c = json.load(open(f"{R}/controls/k3_calibration.json"))
pw = json.load(open(f"{R}/controls/power.json"))
se7, gs7 = 0.002786100152782577, 10.435461649279732          # M7 (h4_methods.csv; rebuilt independently)
q80 = stats.t.ppf(0.80, gs7 - 1)
print("H4 K3 rule:", c["tests"]["H4"]["rule"], "needs_calibration:", c["tests"]["H4"]["needs_calibration"])
for sc, d in c["null"]["H4"].items():
    T = np.asarray(d["stat"], float)
    T = T[np.isfinite(T)]
    n = len(T)
    st = np.sort(T)[::-1]
    out = []
    for a in (0.05 / 3, 0.05):
        m = math.ceil(a * (n + 1) - 1) - 1                    # same order-statistic convention as the calibrated p
        out.append(float(st[m]))
    gmed = c["tests"]["H4"]["by_scenario"][sc]["gstar_median"]
    print(f"{sc}: n null = {n}; T crit at 1-0.05/3 = {out[0]:.3f}, at 1-0.05 = {out[1]:.3f}; "
          f"single t_(1-0.05/3, G*med-1={gmed - 1:.2f}) = {stats.t.ppf(1 - 0.05 / 3, gmed - 1):.3f}, "
          f"Bonferroni t_(1-0.05/12) = {stats.t.ppf(1 - 0.05 / 12, gmed - 1):.3f}; "
          f"share of null T >= single crit {np.mean(T >= stats.t.ppf(1 - 0.05 / 3, gmed - 1)):.4f}; "
          f"MDE with M7's SE using the max-T crit: {(out[0] + q80) * se7:.5f}")

print("\npower.json H4 grid (share of 300 reps with p_decide < 0.05/3 | < 0.05):")
for sc, rows in pw["power"]["H4"].items():
    for r in rows:
        if r["effect"] in (0.01, 0.02):
            k = round(r["reject_alpha3"] * pw["n_reps_power"][sc])
            lo, hi = stats.beta.ppf(0.025, k, 300 - k + 1), stats.beta.ppf(0.975, k + 1, 300 - k)
            print(f"  {sc:6s} {r['kind']:3s} effect {r['effect']:.2f}: {r['reject_alpha3']:.3f} (95% CP {lo:.3f}-{hi:.3f})"
                  f" | {r['reject_05']:.3f}")
    m = pw["mde"]["H4"][sc]
    print(f"  {sc}: formula MDE {m['mde_rule']:.4f} with crit_nominal {m['crit_nominal']:.4f} "
          f"(= t_(1-0.05/3, {m['gstar_median'] - 1:.2f}) {stats.t.ppf(1 - 0.05 / 3, m['gstar_median'] - 1):.4f})")
