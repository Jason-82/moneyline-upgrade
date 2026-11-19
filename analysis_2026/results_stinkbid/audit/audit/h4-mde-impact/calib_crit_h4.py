"""What H4's critical statistic would be under the K3 'critical value of the rule' convention (A2.6): the 0.05/3
upper quantile of the null max-t statistic T = max_j t_j, per scenario, from K3's null draws (own code). Compared with
the nominal t_{1-0.05/3} (printed MDE) and the Bonferroni t_{1-0.05/12} (mde_bonf). Also the K3 power line's H4 MDEs
rescaled to the Bonferroni critical value."""
import json, math
import numpy as np
from scipy import stats

R = "analysis_2026/results_stinkbid/controls"
c = json.load(open(f"{R}/k3_calibration.json"))
pw = json.load(open(f"{R}/power.json"))
A3 = 0.05 / 3
for sc, d in c["null"]["H4"].items():
    st = np.asarray(d["stat"], float)
    st = st[np.isfinite(st)]
    n = len(st)
    s = np.sort(st)[::-1]
    m = math.ceil(A3 * (n + 1) - 1) - 1
    gm = c["tests"]["H4"]["by_scenario"][sc]["gstar_median"]
    df = gm - 1
    # null rejection rates of the nominal and Bonferroni single-test thresholds applied to the max-t statistic
    print(f"{sc}: n={n}, crit(max-t, 0.05/3, calibrated rule) = {s[m]:.4f}; "
          f"nominal t(1-0.05/3,{df:.2f}) = {stats.t.ppf(1-A3, df):.4f}; Bonferroni t(1-0.05/12) = "
          f"{stats.t.ppf(1-0.05/12, df):.4f}; share of null max-t above nominal crit = "
          f"{np.mean(st > stats.t.ppf(1-A3, df)):.4f}, above Bonferroni crit = {np.mean(st > stats.t.ppf(1-0.05/12, df)):.4f}")
print()
# K3 power line: H4 MDEs at the Bonferroni critical value (same G*, same SEs; G* is fixed by the fill calendar)
for sc, row in pw["mde"]["H4"].items():
    df = row["gstar_median"] - 1
    t80 = stats.t.ppf(0.80, df)
    cn = stats.t.ppf(1 - A3, df)
    cb = stats.t.ppf(1 - 0.05 / 12, df)
    k = (cb + t80) / (cn + t80)
    print(f"K3 power line H4 {sc}: crit_nominal record {row['crit_nominal']:.5f} (recomputed {cn:.5f}); formula "
          f"{row['mde_formula']:.4%} -> Bonferroni {row['mde_formula']*k:.4%}; empirical {row['mde_empirical']:.4%} -> "
          f"{row['mde_empirical']*k:.4%}; (se_mean-based formula check: {(cn+t80)*row['se_mean']:.4%})")
