"""Steps 2, 4, 5: Holm and verdicts; A2.7 calibrated p / widened bound under both K3 null-draw sets; the bot row and
the F3-kept rows with their Holm placement. Auditor's own code (mystats)."""
import json
import math
import sys
import numpy as np
import pandas as pd
from scipy import stats

D = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest"
sys.path.insert(0, D)
import mystats as M

R = "analysis_2026/results_stinkbid"
P = json.load(open(f"{R}/primary/primary.json"))
V = pd.read_csv(f"{R}/verdicts.csv").set_index("test")
E = {"H1": 0.0375, "H2R": 0.02, "H4": 0.01}

s1 = pd.read_csv(f"{R}/primary/samples_H1.csv")
s2 = pd.read_csv(f"{R}/primary/samples_H2R.csv")
r1 = M.test_mean(s1.y.to_numpy(float), s1.mb.to_numpy(), E=E["H1"])
r2 = M.test_mean(s2.y.to_numpy(float), s2.mb.to_numpy(), E=E["H2R"])
p4 = float(V.loc["H4", "p_decide"])
ub4 = float(V.loc["H4", "ub"])

gates = P["gates"]                        # recomputed independently in s3 (all identical)
gok = {t: all(gates[t].values()) for t in ("H1", "H2R", "H4")}


def family(pH1, pH2R, pH4, ubs, label):
    tests = ["H1", "H2R", "H4"]
    p = np.array([pH1, pH2R, pH4])
    adj, lv, rej = M.holm(p)
    print(f"--- {label}")
    out = {}
    for i, t in enumerate(tests):
        v = M.verdict(adj[i], gok[t], ubs[t], E[t])
        out[t] = dict(p=p[i], p_holm=adj[i], level=lv[i], rejected=bool(rej[i]), ub=ubs[t], verdict=v)
        print(f"   {t}: p {p[i]:.6f}  Holm-adj {adj[i]:.6f}  level {lv[i]:.6f}  rejected {bool(rej[i])}  gates {gok[t]}  "
              f"ub {ubs[t]:+.5f} vs E {E[t]}  -> {v}")
    return out


print("== Step 2: Holm and verdicts of record (nominal rule for all three)")
rec = family(r1["p_decide"], r2["p_decide"], p4, {"H1": r1["ub"], "H2R": r2["ub"], "H4": ub4}, "record")
for t in ("H1", "H2R", "H4"):
    v = V.loc[t]
    print(f"   verdicts.csv {t}: p_holm {v.p_holm:.6f} level {v.holm_level:.6f} rejected {v.holm_rejected} "
          f"gates_ok {v.gates_ok} ub {v.ub:.6f} verdict {v.verdict}")
# E sensitivity for H1
print(f"   H1 with E = 2.26%: ub {r1['ub']:.4f} -> {M.verdict(rec['H1']['p_holm'], gok['H1'], r1['ub'], 0.0226)}")
# NO EDGE margins
for t, r in (("H1", r1), ("H2R", r2)):
    print(f"   {t}: ub_boot {r['ub_boot']:.5f} ub_t {r['ub_t']:.5f} -> ub {r['ub']:.5f}; E {E[t]}; ub - E = {r['ub'] - E[t]:+.5f}")

# ---------------------------------------------------------------- Step 4: A2.7
print("\n== Step 4: A2.7, H2R under the simulation-calibrated rule with each null-draw set")
K = json.load(open(f"{R}/controls/k3_calibration.json"))
K1 = json.load(open(f"{R}/controls_first/k3_calibration_H2R.json"))
a = 1 - K["level_noedge"]
t_obs, est, se, gs = r2["t"], r2["est"], r2["se"], r2["gstar"]
alpha_b = 0.05 / 3
for name, C in (("first run (controls_first)", K1), ("record (controls)", K)):
    ps, qs, crits = {}, {}, {}
    for s, dd in C["null"]["H2R"].items():
        st = np.asarray(dd["stat"], float)
        st = st[np.isfinite(st)]
        n = len(st)
        k = int(np.sum(st >= t_obs))
        ps[s] = ((1 + k) / (n + 1), k, n)
        pv = np.asarray(dd["pivot"], float)
        pv = pv[np.isfinite(pv)]
        qs[s] = M.weibull_q(pv, a)
        # critical t: smallest s with (1 + #{st >= s})/(n+1) < alpha_b  <=>  #{st >= s} <= m  with m = ceil(alpha(n+1)-1)-1
        m = math.ceil(alpha_b * (n + 1) - 1) - 1
        crits[s] = float(np.sort(st)[::-1][m])
    p_cal = max(v[0] for v in ps.values())
    q_min = min(qs.values())
    ub_cal = est - q_min * se
    ub_w = max(r2["ub"], ub_cal)
    crit = max(crits.values())
    mde_cal = (crit + stats.t.ppf(0.80, gs - 1)) * se
    print(f" {name}: per scenario (p, k, n) {ps}")
    print(f"   pivot q_{a:.5f} per scenario {{{', '.join(f'{k}: {v:.4f}' for k, v in qs.items())}}}; min {q_min:.4f}")
    print(f"   calibrated p = {p_cal:.6f}; calibrated bound = {ub_cal:.6f}; widened bound max(nominal {r2['ub']:.6f}, cal) = {ub_w:.6f}")
    print(f"   critical t per scenario {crits}; crit {crit:.4f}; calibrated MDE {(mde_cal):.5f}")
    fam = family(r1["p_decide"], p_cal, p4, {"H1": r1["ub"], "H2R": ub_w, "H4": ub4}, f"family under {name}")
key = {"first run (controls_first)": "first_run", "record (controls)": "switched"}
for k_ in ("first_run", "switched"):
    x = P["k3_other"]["H2R"][k_]
    print(f" primary.json k3_other {k_}: p_decide {x['p_decide']:.6f} ub {x['ub']:.6f} ub_cal {x['ub_calibrated']:.6f} "
          f"crit {x['crit_calibrated']:.4f} mde {x['mde']:.5f}")

# K3 rule of record: false-PASS rates and CP intervals as stored
print("\n K3 rule (stored k, n; Clopper-Pearson recomputed):")
for name, C in (("record", K), ("first", K1)):
    for t, T in C["tests"].items():
        for s, by in T["by_scenario"].items():
            for lv, fp in by["false_pass"].items():
                k, n = fp["k"], fp["n"]
                hi = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
                ok = hi <= 1.5 * float(lv)
                flag = "" if ok == fp["ok"] else "  <-- MISMATCH"
                if not ok or t == "H2R":
                    print(f"   {name} {t} {s} level {float(lv):.4f}: k {k}/{n} rate {k / n:.4%} CP hi {hi:.4%} limit {1.5 * float(lv):.4%} ok {ok}{flag}")
            miss = by["noedge_miss"]
            hi = stats.beta.ppf(0.975, miss["k"] + 1, miss["n"] - miss["k"])
            if t == "H2R" or hi > 1.5 * miss["nominal"]:
                print(f"   {name} {t} {s} NO EDGE miss: k {miss['k']}/{miss['n']} CP hi {hi:.4%} limit {1.5 * miss['nominal']:.4%}")
        print(f"   {name} {t}: needs_calibration {T['needs_calibration']} rule {T['rule']}")

# ---------------------------------------------------------------- Step 5: bot row and F3-kept rows
print("\n== Step 5: the bot row and the F3-kept rows")
bot = pd.read_parquet(f"{D}/bot.parquet").sort_values(["time", "fill_id"]).reset_index(drop=True)
mbb, epb = M.my_month_blocks(bot.time)
rb = M.test_mean(bot.delta.to_numpy(float), mbb, E=E["H1"])
fb = P["bot"]["row"]
print(f" bot mine: n {rb['n']} G {rb['G']} G* {rb['gstar']:.4f} est {rb['est']:.6f} se {rb['se']:.6f} t {rb['t']:.4f} "
      f"p_G* {rb['p_gstar']:.6f} p_WCR {rb['p_wcr']:.4f} ub_boot {rb['ub_boot']:.5f} ub_t {rb['ub_t']:.5f} ub {rb['ub']:.5f}")
print(f" bot file: n {fb['n']} G {fb['G']} G* {fb['gstar']:.4f} est {fb['estimate']:.6f} se {fb['se']:.6f} t {fb['t']:.4f} "
      f"p_G* {fb['p_gstar']:.6f} p_WCR {fb['p_wcr']:.4f} ub_boot {fb['ub_boot']:.5f} ub_t {fb['ub_t']:.5f} ub {fb['ub']:.5f}")
fam_b = family(rb["p_decide"], r2["p_decide"], p4, {"H1": rb["ub"], "H2R": r2["ub"], "H4": ub4}, "bot in H1's place")

h1 = pd.read_parquet(f"{D}/h1.parquet").sort_values(["time", "fill_id"]).reset_index(drop=True)
h2 = pd.read_parquet(f"{D}/h2r.parquet").sort_values(["time", "fill_id"]).reset_index(drop=True)
for t, d, ycol in (("H1", h1, "delta"), ("H2R", h2, "alert_M")):
    k = d[d.t_F3_1 >= 0].reset_index(drop=True)
    mbk, _ = M.my_month_blocks(k.time)
    rk = M.test_mean(k[ycol].to_numpy(float), mbk, E=E[t])
    fk = P["f3kept"][t]
    print(f" f3kept {t} mine: n {rk['n']} G {rk['G']} G* {rk['gstar']:.4f} est {rk['est']:.6f} se {rk['se']:.6f} t {rk['t']:.4f} "
          f"p_G* {rk['p_gstar']:.6f} p_WCR {rk['p_wcr']:.4f} p_decide {rk['p_decide']:.6f} ub {rk['ub']:.5f}")
    print(f" f3kept {t} file: n {fk['n']} G {fk['G']} G* {fk['gstar']:.4f} est {fk['estimate']:.6f} se {fk['se']:.6f} t {fk['t']:.4f} "
          f"p_G* {fk['p_gstar']:.6f} p_WCR {fk['p_wcr']:.4f} p_decide {fk['p_decide']:.6f} ub {fk['ub']:.5f}")
    lvl = rec[t]["level"]
    print(f"   Holm level at which {t} was rejected: {lvl:.6f} (rejected {rec[t]['rejected']}); f3kept p_decide < level: "
          f"{rk['p_decide'] < lvl}  -> Binance-only flag (only for a PASS): {rec[t]['verdict'] == 'PASS' and not rk['p_decide'] < lvl}")
    # alternative reading: re-run Holm with the f3kept p in the test's place
    ps = {"H1": r1["p_decide"], "H2R": r2["p_decide"], "H4": p4}
    ps[t] = rk["p_decide"]
    adj, lv, rej = M.holm(np.array([ps["H1"], ps["H2R"], ps["H4"]]))
    i = ["H1", "H2R", "H4"].index(t)
    print(f"   (alt: Holm with f3kept p in {t}'s place: adj {adj[i]:.6f}, rejected {bool(rej[i])})")
