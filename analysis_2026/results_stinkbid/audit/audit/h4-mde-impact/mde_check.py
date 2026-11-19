"""Independent recomputation of H4's MDE under the nominal (single-test) and the Bonferroni-over-4 critical value,
and the power each printed MDE actually has under H4's pre-registered decision rule (p_G* = 4 x one-sided t p)."""
import json
import numpy as np
import pandas as pd
from scipy import stats

R = "analysis_2026/results_stinkbid"
tab = pd.read_csv(f"{R}/primary/h4_methods.csv")
A = 0.05
E = 0.01
rows = []
for _, r in tab.iterrows():
    df = r.gstar - 1
    se = r.se
    t80 = stats.t.ppf(0.80, df)
    c3 = stats.t.ppf(1 - A / 3, df)        # family Bonferroni level, single test (what is printed)
    c12 = stats.t.ppf(1 - A / 12, df)      # H4's decision at Holm's first level: 4 x p_t < 0.05/3
    c4 = stats.t.ppf(1 - A / 4, df)        # H4's decision at Holm level 0.05 (the level it faced): 4 x p_t < 0.05
    c2x4 = stats.t.ppf(1 - A / 8, df)      # Holm's second level 0.025 with the x4
    mde3 = (c3 + t80) * se
    mde12 = (c12 + t80) * se
    mde4 = (c4 + t80) * se
    # power of H4's actual decision rule (one-method effect, p_G* part only) at the printed MDE and at E
    def pw_shift(delta, crit):              # the MDE formula's own approximation (shifted central t)
        return float(stats.t.sf(crit - delta / se, df))
    def pw_nct(delta, crit):                # exact noncentral t
        return float(stats.nct.sf(crit, df, delta / se))
    rows.append(dict(method=r.method, se=se, gstar=r.gstar, df=df, t80=t80, crit_a3=c3, crit_a12=c12, crit_a4=c4,
                     mde_a3=mde3, mde_rec=r.mde, mde_a12=mde12, mde_bonf_rec=r.mde_bonf, mde_a4=mde4,
                     pw_at_mde3_bonf12_shift=pw_shift(mde3, c12), pw_at_mde3_bonf12_nct=pw_nct(mde3, c12),
                     pw_at_mde3_bonf4_shift=pw_shift(mde3, c4),
                     pw_at_E_bonf12_shift=pw_shift(E, c12), pw_at_E_bonf12_nct=pw_nct(E, c12),
                     pw_at_E_nom3_shift=pw_shift(E, c3), pw_at_E_bonf4_shift=pw_shift(E, c4),
                     pw_at_mde12_bonf12_shift=pw_shift(mde12, c12),
                     p_t_rec=r.p_t, p_t_recomp=float(stats.t.sf(r.t, df)), p_bonf_rec=r.p_bonf,
                     p_bonf_recomp=min(1.0, 4 * float(stats.t.sf(r.t, df)))))
out = pd.DataFrame(rows)
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 50)
print(out.T.to_string())
# effective number of tests implied by H4's rule and Holm level
print()
m7 = out.set_index("method").loc["M7"]
print(f"M7: printed MDE (a/3) {m7.mde_a3:.6f} (record {m7.mde_rec:.6f}); Bonferroni MDE (a/12) {m7.mde_a12:.6f} "
      f"(record mde_bonf {m7.mde_bonf_rec:.6f}); at Holm level 0.05 with x4 (a/4) {m7.mde_a4:.6f}")
print(f"M7 critical values: t(1-0.05/3,{m7.df:.3f}) = {m7.crit_a3:.4f}; t(1-0.05/12) = {m7.crit_a12:.4f}; "
      f"t(1-0.05/4) = {m7.crit_a4:.4f}; t(0.80) = {m7.t80:.4f}")
print(f"Power of H4's rule (one-method effect in M7) at the printed MDE {m7.mde_a3:.4%}: at 0.05/3 "
      f"{m7.pw_at_mde3_bonf12_shift:.3f} (formula approx), {m7.pw_at_mde3_bonf12_nct:.3f} (noncentral t); at 0.05 "
      f"{m7.pw_at_mde3_bonf4_shift:.3f}")
print(f"Power at E = 1% (M7 alone): Bonferroni at 0.05/3 {m7.pw_at_E_bonf12_shift:.3f} (nct {m7.pw_at_E_bonf12_nct:.3f}); "
      f"as printed (no x4) {m7.pw_at_E_nom3_shift:.3f}; Bonferroni at 0.05 {m7.pw_at_E_bonf4_shift:.3f}")
a = json.load(open(f"{R}/answer.json"))
print("answer.json numbers.tests.H4.M =", a["numbers"]["tests"]["H4"]["M"], "; h4.methods M7 mde/mde_bonf =",
      a["h4"]["methods"][3]["mde"], a["h4"]["methods"][3]["mde_bonf"])
