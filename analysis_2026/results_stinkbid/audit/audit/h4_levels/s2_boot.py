"""Step 2: Romano-Wolf max-t wild (Webb) bootstrap, p_WCR, p_G*, the 98.33% bounds per method (simultaneous, as
coded, and marginal per method), 95% intervals and MDE. Brute-force re-estimation per draw (own code)."""
import sys
import json
import resource
import numpy as np
import pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h4_levels")
import h4_common as hc

OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h4_levels"
rule = sys.argv[1] if len(sys.argv) > 1 else "F1"
Bn = 9999
a = 1 / 60                                      # 1 - 0.05/3


def wq(x, p):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(np.quantile(x, p, method="weibull"))


fr = {m: pd.read_parquet(f"{OUT}/frame_{rule}_{m}.parquet") for m in hc.METHODS}
# union-partition codes by first appearance in the concatenation M4, M5b, M6, M7 (the module's draw protocol)
allblk = np.concatenate([fr[m].block.to_numpy() for m in hc.METHODS])
code_fa, uniq_fa = pd.factorize(allblk)
Gu = len(uniq_fa)
fits = {}
for m in hc.METHODS:
    g = fr[m]
    fits[m] = hc.fe_fit(g.y, np.column_stack([g.realf, g.depth]), g.cw, g.block)

res = {}
for proto, seed in (("module_protocol", 20261118), ("independent_seed", 777)):
    rng = np.random.default_rng(seed)
    if proto == "module_protocol":
        W_all = hc.WEBB[rng.integers(0, 6, size=(Bn, Gu))]          # columns = first-appearance codes
        col_of_block = {b: i for i, b in enumerate(uniq_fa)}
    else:
        W_all = hc.WEBB[rng.integers(0, 6, size=(Bn, Gu))]
        col_of_block = {b: i for i, b in enumerate(np.sort(uniq_fa))}
    tstar = np.full((Bn, 4), np.nan)
    for j, m in enumerate(hc.METHODS):
        f = fits[m]
        cols = np.array([col_of_block[b] for b in f["clab"]])        # this fit's clusters (sorted labels) -> W column
        tstar[:, j] = hc.boot_t(f, W_all[:, cols])
    b = np.array([fits[m]["theta"][0] for m in hc.METHODS])
    se = np.array([fits[m]["se"][0] for m in hc.METHODS])
    gs = np.array([fits[m]["gstar"] for m in hc.METHODS])
    t = b / se
    jm = int(np.argmax(t))
    T = t[jm]
    tsN = np.where(np.isnan(tstar), np.inf, tstar)
    mx = tsN.max(1)
    p_wcr = (1 + np.sum(mx >= T - 1e-10 * max(1, abs(T)))) / (Bn + 1)
    # Romano-Wolf step-down per method
    order = np.argsort(-t)
    raw = []
    for r_, j in enumerate(order):
        Mr = tsN[:, order[r_:]].max(1)
        raw.append((1 + np.sum(Mr >= t[j] - 1e-10 * max(1, abs(t[j])))) / (Bn + 1))
    adj = np.maximum.accumulate(raw)
    p_rw = np.empty(4)
    p_rw[order] = np.minimum(adj, 1)
    p_t = np.array([hc.tsf(t[j], gs[j] - 1) for j in range(4)])
    p_g = min(1.0, 4 * p_t[jm])
    # simultaneous bounds (as coded): min over methods of t*, Bonferroni t at 1 - a/4
    qmin = wq(np.min(np.where(np.isnan(tstar), -np.inf, tstar), 1), a)
    ub_boot_sim = b - qmin * se
    ub_bonf = b + np.array([hc.tppf(1 - a / 4, gs[j] - 1) for j in range(4)]) * se
    ub_sim = np.maximum(ub_boot_sim, ub_bonf)
    # marginal per-method 98.33% bounds (§10.2 applied to each method alone)
    q_marg = np.array([wq(np.where(np.isnan(tstar[:, j]), -np.inf, tstar[:, j]), a) for j in range(4)])
    ub_boot_marg = b - q_marg * se
    ub_t_marg = b + np.array([hc.tppf(1 - a, gs[j] - 1) for j in range(4)]) * se
    ub_marg = np.maximum(ub_boot_marg, ub_t_marg)
    # 95% intervals as coded (union of simultaneous bootstrap and Bonferroni t at 0.025/4)
    qabs = wq(np.max(np.where(np.isnan(tstar), np.inf, np.abs(tstar)), 1), 0.95)
    q2 = np.array([hc.tppf(1 - 0.025 / 4, gs[j] - 1) for j in range(4)])
    ci_lo = np.minimum(b - qabs * se, b - q2 * se)
    ci_hi = np.maximum(b + qabs * se, b + q2 * se)
    mde = np.array([(hc.tppf(1 - a, gs[j] - 1) + hc.tppf(0.8, gs[j] - 1)) * se[j] for j in range(4)])
    mde_b = np.array([(hc.tppf(1 - a / 4, gs[j] - 1) + hc.tppf(0.8, gs[j] - 1)) * se[j] for j in range(4)])
    tab = pd.DataFrame(dict(method=hc.METHODS, b=b, se=se, t=t, gstar=gs, p_t=p_t, p_rw=p_rw, p_bonf=np.minimum(1, 4 * p_t),
                            q_marg=q_marg, ub_boot_sim=ub_boot_sim, ub_bonf=ub_bonf, ub_sim=ub_sim,
                            ub_boot_marg=ub_boot_marg, ub_t_marg=ub_t_marg, ub_marg=ub_marg, ci_lo=ci_lo, ci_hi=ci_hi,
                            mde=mde, mde_bonf=mde_b))
    pd.set_option("display.width", 300)
    print(f"\n=== {rule} {proto} (seed {seed}), B = {Bn}, G_union = {Gu}")
    print(tab.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
    print(f"T = {T:.6f} argmax {hc.METHODS[jm]}; p_WCR = {p_wcr:.4f}; p_G* = {p_g:.6f}; p_decide = {max(p_wcr, p_g):.6f}")
    print(f"qmin(1/60) = {qmin:.4f}; qabs(0.95) = {qabs:.4f}; H4 bound (sim, max over methods) = {ub_sim.max():.6f} "
          f"({hc.METHODS[int(np.argmax(ub_sim))]}); marginal max = {ub_marg.max():.6f} ({hc.METHODS[int(np.argmax(ub_marg))]})")
    print("NaN draws per method:", np.isnan(tstar).sum(0).tolist())
    res[proto] = dict(T=T, argmax=hc.METHODS[jm], p_wcr=p_wcr, p_g=p_g, qmin=qmin, qabs=qabs, tab=tab.to_dict("list"))
    np.save(f"{OUT}/tstar_{rule}_{proto}.npy", tstar)

json.dump(res, open(f"{OUT}/boot_{rule}.json", "w"), default=float, indent=1)
print("peak RSS MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
