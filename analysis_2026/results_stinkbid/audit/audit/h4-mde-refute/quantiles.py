# Independent recomputation of H4's MDE variants from h4_methods.csv (SE, G*), own formula.
import pandas as pd
from scipy import stats
t = pd.read_csv("analysis_2026/results_stinkbid/primary/h4_methods.csv")
for _, r in t.iterrows():
    df = r.gstar - 1
    q = lambda a: stats.t.ppf(1 - a, df)
    p80 = stats.t.ppf(0.80, df)
    m_single = (q(0.05/3) + p80) * r.se
    m_bonf = (q(0.05/12) + p80) * r.se
    m_bonf05 = (q(0.05/4) + p80) * r.se
    print(f"{r.method}: G*={r.gstar:.4f} df={df:.4f} se={r.se*100:.4f}% t={r.t:.4f} p_t={r.p_t:.4f} 4p_t={4*r.p_t:.4f} "
          f"p_rw={r.p_rw} | crit 0.05/3={q(0.05/3):.4f} 0.05/12={q(0.05/12):.4f} 0.05/4={q(0.05/4):.4f} t80={p80:.4f} | "
          f"mde(0.05/3)={m_single*100:.4f}% [file {r.mde*100:.4f}%]  mde(0.05/12)={m_bonf*100:.4f}% [file {r.mde_bonf*100:.4f}%]  "
          f"mde(0.05/4)={m_bonf05*100:.4f}%")
# Power of a one-method effect at the printed MDE (M7: ncp = 0.9391%/se), under the actual Bonferroni critical values
r = t.set_index("method").loc["M7"]
df = r.gstar - 1
for eff in (0.009391, 0.01, 0.011715):
    ncp = eff / r.se
    for a, lab in ((0.05/3, "single 0.05/3"), (0.05/12, "Bonf 0.05/12 (Holm step 1)"), (0.05/4, "Bonf 0.05/4 (Holm level 0.05)"),
                   (0.05/8, "Bonf 0.025/4 (Holm step 2)")):
        c = stats.t.ppf(1 - a, df)
        pw = stats.nct.sf(c, df, ncp)
        print(f"  M7 one-method effect {eff*100:.3f}% (ncp {ncp:.3f}): power vs crit {c:.3f} [{lab}] = {pw:.3f}")
