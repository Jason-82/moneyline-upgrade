import json, numpy as np
from scipy import stats
P = json.load(open("/home/user/moneyline-upgrade/analysis_2026/results_stinkbid/primary/primary.json"))
r = P["rows"]["H2R"]
t_obs, est, se, gs = r["t"], r["estimate"], r["se"], r["gstar"]
alpha = 0.05 / 3
df = gs - 1
t80 = stats.t.ppf(0.80, df)
tnom = stats.t.ppf(1 - alpha, df)
print("nominal crit %.5f t80 %.5f MDE_nominal %.6f (reported %.6f)" % (tnom, t80, (tnom + t80) * se, r["mde"]))
for name, f in (("first_run", "controls_first/k3_calibration_H2R.json"), ("switched", "controls/k3_calibration.json")):
    C = json.load(open("/home/user/moneyline-upgrade/analysis_2026/results_stinkbid/" + f))
    ps, crits, qs = {}, {}, {}
    for sc, d in C["null"]["H2R"].items():
        st = np.asarray(d["stat"], float); st = st[np.isfinite(st)]
        n = len(st)
        ps[sc] = (1 + (st >= t_obs).sum()) / (n + 1)
        # smallest threshold s with (1 + #{st >= s}) / (n + 1) < alpha: #{>= s} <= K where K = largest int < alpha(n+1)-1
        K = int(np.ceil(alpha * (n + 1) - 1) - 1)
        srt = np.sort(st)[::-1]
        crits[sc] = srt[K]          # any s > srt[K] has at most K draws at or above it
        pv = np.asarray(d["pivot"], float); pv = pv[np.isfinite(pv)]
        qs[sc] = np.quantile(pv, alpha, method="weibull")
    p = max(ps.values()); crit = max(crits.values()); q = min(qs.values())
    ub_cal = est - q * se
    p_holm = max(3 * P["rows"]["H1"]["p_decide"], 2 * p)
    print(name, "needs_calibration in file:", C["tests"]["H2R"]["needs_calibration"])
    print("   p by scenario", {k: round(v, 6) for k, v in ps.items()}, "-> p", round(p, 6), "Holm-adj", round(p_holm, 6))
    print("   crit by scenario", {k: round(v, 4) for k, v in crits.items()}, "-> crit", round(crit, 4), "MDE", round((crit + t80) * se, 6))
    print("   pivot q by scenario", {k: round(v, 4) for k, v in qs.items()}, "-> ub_cal", round(ub_cal, 6), "widened ub", round(max(ub_cal, r["ub"]), 6))
    ws = C["tests"]["H2R"].get("worst_scenario"); bs = C["tests"]["H2R"].get("by_scenario", {})
    print("   worst", ws, {sc: {k: v for k, v in x.items() if k.startswith("false_pass") or k.startswith("rate") or "1.67" in k or "ci" in k} for sc, x in bs.items()} if isinstance(bs, dict) else "")
