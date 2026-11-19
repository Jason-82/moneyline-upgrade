"""Independent arithmetic check of H4's reported MDE (finding h4-mde-not-bonferroni).
Reads the committed outputs only; recomputes t quantiles, MDEs and exact power with scipy (no repo import)."""
import json
import numpy as np
import pandas as pd
from scipy import stats

R = "analysis_2026/results_stinkbid"
tab = pd.read_csv(f"{R}/primary/h4_methods.csv")
vc = pd.read_csv(f"{R}/verdicts.csv").set_index("test")
ans = json.load(open(f"{R}/answer.json"))

print("H4 row of verdicts.csv: argmax", vc.loc["H4", "argmax"], "mde", vc.loc["H4", "mde"], "p_decide",
      vc.loc["H4", "p_decide"], "p_holm", vc.loc["H4", "p_holm"], "holm_level", vc.loc["H4", "holm_level"])
print("answer.json numbers.tests.H4.M =", ans["numbers"]["tests"]["H4"]["M"])

a3 = 0.05 / 3
for _, r in tab.iterrows():
    df = r.gstar - 1
    se = r.se
    t_a3 = stats.t.ppf(1 - a3, df)
    t_a12 = stats.t.ppf(1 - a3 / 4, df)
    t_a05_4 = stats.t.ppf(1 - 0.05 / 4, df)
    t_a05 = stats.t.ppf(1 - 0.05, df)
    t80 = stats.t.ppf(0.80, df)
    m3, m12, m05_4, m05 = [(c + t80) * se for c in (t_a3, t_a12, t_a05_4, t_a05)]
    # p checks
    t = r.b / r.se
    p_t = stats.t.sf(t, df)
    print(f"\n{r.method}: b={r.b:.6f} se={se:.6f} G*={r.gstar:.4f} df={df:.4f} t={t:.4f} (file {r.t:.4f})")
    print(f"  one-sided p_t mine {p_t:.6f} file {r.p_t:.6f}; 4*p_t {min(1, 4*p_t):.6f} file p_bonf {r.p_bonf:.6f}")
    print(f"  t_(1-.05/3)={t_a3:.4f}  t_(1-.05/12)={t_a12:.4f}  t_(1-.05/4)={t_a05_4:.4f}  t_(1-.05)={t_a05:.4f}  t_.80={t80:.4f}")
    print(f"  MDE single 0.05/3 {m3:.6f} (file mde {r.mde:.6f});  Bonferroni 0.05/12 {m12:.6f} (file mde_bonf {r.mde_bonf:.6f})")
    print(f"  MDE at Holm's last level 0.05 with Bonferroni (0.0125): {m05_4:.6f};  single test at 0.05: {m05:.6f}")
    # exact power (noncentral t, df = G*-1) of the decisive Bonferroni rule p_G* = 4 p_t < level, effect only in this method
    for eff_name, eff in (("printed MDE", r.mde), ("E = 1%", 0.01), ("mde_bonf", r.mde_bonf)):
        ncp = eff / se
        pw3 = stats.nct.sf(t_a3, df, ncp)        # what the printed MDE assumes: one test at 0.05/3
        pw12 = stats.nct.sf(t_a12, df, ncp)      # H4's p_G* at Holm's first level 0.05/3
        pw4 = stats.nct.sf(t_a05_4, df, ncp)     # H4's p_G* at Holm's last level 0.05
        print(f"  effect {eff_name} {eff:.5f}: exact power single-test@.05/3 {pw3:.3f}; "
              f"Bonferroni@.05/3 {pw12:.3f}; Bonferroni@.05 {pw4:.3f}")
