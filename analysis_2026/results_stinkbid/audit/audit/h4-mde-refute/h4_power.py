# Power of H4's decisive rule (p = max(p_RW, 4 x one-sided t(G*_argmax - 1) p of T = max_j t_j), prereg §10.3) on the
# real data's SEs, G*s and cross-method correlation (from h4_rebuild.py), by Monte Carlo on t_j = delta_j/se_j + eps_j.
# eps ~ multivariate t (correlation R, shared chi-square, nu = df) or normal. p_RW approximated by the (1-a) quantile of
# max_j eps_j under the null. Reports the effect at 80% power for one-method and all-method alternatives.
import json, sys
import numpy as np
from scipy import stats
d = json.load(open(sys.argv[1]))
M = ["M4", "M5b", "M6", "M7"]
se = np.array([d["res"][m]["se"] for m in M]); gs = np.array([d["res"][m]["gstar"] for m in M])
R = np.array(d["R"])
rng = np.random.default_rng(7)
N = 400_000
L = np.linalg.cholesky(R)
Z = rng.standard_normal((N, 4)) @ L.T
out = {}
for noise in ("t(nu=9.44, shared)", "normal"):
    if noise.startswith("t"):
        w = np.sqrt(rng.chisquare(9.4355, N) / 9.4355)
        E = Z / w[:, None]
    else:
        E = Z
    for a, lab in ((0.05 / 3, "a=0.05/3 (Holm step 1, the MDE convention)"), (0.05, "a=0.05 (H4's Holm level)")):
        c_rw = np.quantile(E.max(axis=1), 1 - a)
        def power(delta_vec):
            T = E + delta_vec / se
            j = T.argmax(axis=1)
            Tm = T[np.arange(N), j]
            p_b = np.minimum(1.0, 4 * stats.t.sf(Tm, gs[j] - 1))
            return np.mean((p_b < a) & (Tm > c_rw))
        grid = np.round(np.arange(0.004, 0.0181, 0.0002), 6)
        res = {}
        for scope in ["M7 only", "M4 only", "M5b only", "M6 only", "all four"]:
            pw = []
            for eff in grid:
                dv = np.zeros(4)
                if scope == "all four":
                    dv[:] = eff
                else:
                    dv[M.index(scope.split()[0])] = eff
                pw.append(power(dv))
            pw = np.array(pw)
            k = np.argmax(pw >= 0.8)
            e80 = grid[k - 1] + (0.8 - pw[k - 1]) / (pw[k] - pw[k - 1]) * (grid[k] - grid[k - 1]) if k > 0 else np.nan
            at = {f"{x*100:.2f}%": float(pw[np.argmin(np.abs(grid - x))]) for x in (0.0094, 0.0100, 0.0118)}
            res[scope] = (e80, at)
            print(f"[{noise}] {lab} c_RW={c_rw:.3f}  {scope:9s}: 80%-power effect {e80*100:.3f}%   power at "
                  + ", ".join(f"{k_} {v:.3f}" for k_, v in at.items()))
    print()
