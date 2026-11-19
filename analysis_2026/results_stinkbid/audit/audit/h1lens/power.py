"""(1) Exact reproduction of p_WCR / ub_boot with the module's seed convention (own estimator code);
(2) power, selection (winner's curse) and shrinkage views for H1; (3) removal of the top contributing episodes."""
import sys
import numpy as np
import pandas as pd
from scipy import stats, optimize

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1lens")
from core import WEBB, summarize, fmt

OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1lens/"
LEVEL = 1 - 0.05 / 3


def wcr_exact(y, labels, seed=20261118, B=9999, level=LEVEL):
    codes, _ = pd.factorize(np.asarray(labels))
    G = codes.max() + 1
    N = len(y)
    S = np.bincount(codes, weights=y, minlength=G)
    n = np.bincount(codes, minlength=G).astype(float)
    W = WEBB[np.random.default_rng(seed).integers(0, 6, size=(B, G))]
    th = y.mean()
    U = S - n * th
    se = np.sqrt(G / (G - 1) * (U ** 2).sum()) / N
    t = th / se
    cG = G / (G - 1)
    ths = W @ S / N
    rs = W * S - ths[:, None] * n
    tr = ths / (np.sqrt(cG * (rs ** 2).sum(1)) / N)
    p = (1 + np.sum(tr >= t - 1e-10 * max(1, abs(t)))) / (B + 1)
    d = W @ U / N
    ru = W * U - d[:, None] * n
    tu = d / (np.sqrt(cG * (ru ** 2).sum(1)) / N)
    ub = th - np.quantile(tu, 1 - level, method="weibull") * se
    lo = th - np.quantile(tu, 0.975, method="weibull") * se
    hi = th - np.quantile(tu, 0.025, method="weibull") * se
    return p, ub, (lo, hi), int(np.sum(tr >= t))


for name in ("H1", "H2R"):
    d = pd.read_csv("analysis_2026/results_stinkbid/primary/samples_%s.csv" % name)
    p, ub, ci, k = wcr_exact(d.y.values.astype(float), d.mb.values)
    print(f"{name}: exact-seed WCR p {p:.4f} (exceedances {k}); ub_boot {ub:+.5f}; boot 95% CI ({ci[0]:+.5f},{ci[1]:+.5f})")
print("file: H1 p_wcr 0.0001 ub_boot +0.09915 ci95_boot (+0.03059,+0.09640); H2R p_wcr 0.0156 ub_boot +0.04494 ci95_boot (+0.00159,+0.04316)")

# ---------------------------------------------------------------- power and selection for H1
est, se, gs = 0.06342500897813326, 0.016452980930990718, 14.503168645422507
df = gs - 1
E = 0.0375
for lab, alpha in (("Holm step 1 (0.05/3)", 0.05 / 3), ("Holm step 3 (0.05)", 0.05)):
    c = stats.t.ppf(1 - alpha, df)
    pw = lambda th: stats.nct.sf(c, df, th / se)
    print(f"{lab}: crit t {c:.3f}; power at est {pw(est):.3f}, at E {pw(E):.3f}, at MDE {pw(0.05327963239542828):.3f}, at 2% {pw(0.02):.3f}")
c = stats.t.ppf(1 - 0.05 / 3, df)
z = est / se
# conditional (truncated-normal) estimators given z > c, normal approximation
def cond_mean(mu):
    a = c - mu
    return mu + stats.norm.pdf(a) / stats.norm.sf(a)
mu_mle = optimize.brentq(lambda m: cond_mean(m) - z, -5, 10)
def cond_cdf(mu, x):
    return (stats.norm.cdf(x - mu) - stats.norm.cdf(c - mu)) / stats.norm.sf(c - mu)
mu_med = optimize.brentq(lambda m: cond_cdf(m, z) - 0.5, -3, 8)
mu_lo = optimize.brentq(lambda m: cond_cdf(m, z) - 0.975, -3, 8)
mu_hi = optimize.brentq(lambda m: cond_cdf(m, z) - 0.025, -3, 8)
print(f"selection-adjusted (z|z>c={c:.3f}): conditional-mean-unbiased {mu_mle * se:+.4f}; conditional median-unbiased {mu_med * se:+.4f};"
      f" conditional 95% CI ({mu_lo * se:+.4f},{mu_hi * se:+.4f})")
# type-M exaggeration if the truth were E or 2%
rng = np.random.default_rng(1)
for th in (0.02, E, 0.05327963239542828):
    zz = rng.standard_t(df, 2_000_000) + th / se
    sig = zz > c
    print(f"  truth {th:.4f}: power {sig.mean():.3f}; mean significant estimate {zz[sig].mean() * se:+.4f} (exaggeration x{zz[sig].mean() * se / th:.2f})")
# normal-prior shrinkage
for tau in (0.02, 0.0375, 0.06):
    w = tau ** 2 / (tau ** 2 + se ** 2)
    pm, ps = w * est, np.sqrt(w) * se
    print(f"  prior N(0,{tau:.4f}^2): posterior mean {pm:+.4f} (95% ({pm - 1.96 * ps:+.4f},{pm + 1.96 * ps:+.4f})); P(Delta > E) {stats.norm.sf(E, pm, ps):.3f}; P(Delta>0) {stats.norm.sf(0, pm, ps):.4f}")

# ---------------------------------------------------------------- removing the top contributing episodes
for name in ("H1", "H2R"):
    d = pd.read_pickle(OUT + f"d_{name}.pkl")
    s = d.groupby("myep")["y"].sum().sort_values(ascending=False)
    for k in (1, 2, 3, 5):
        keep = ~d.myep.isin(s.index[:k])
        r = summarize(d.y.values[keep], d.mymb.values[keep], do_wild=False)
        print(f" {name} without top-{k} contributing episodes: " + fmt(r, ("n", "G", "gstar", "est", "se", "t", "p_gstar")))
