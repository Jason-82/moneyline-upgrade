"""Step 3: rebuild H1/H2R samples from the cached engine runs, check the per-fill arithmetic, recompute every gate."""
import json
import resource
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest")
import mystats as M

RUNS = "data/stinkbid/runs/outcomes"
R = "analysis_2026/results_stinkbid"
C = 0.0095
OCOLS = ["rule", "exit", "lat", "cost", "fill_id", "r", "exit_px", "exit_t", "exit_kind", "target", "complete",
         "twin_mean", "twin_n", "delta", "horizon_t"]
P = json.load(open(f"{R}/primary/primary.json"))


def minutes_to_ts(m):
    return pd.to_datetime(np.asarray(m, np.int64) * 60_000_000_000, utc=True)


def load(run, rules, exits):
    F = pd.read_parquet(f"{RUNS}/{run}/fills.parquet")
    keep = [c for c in ["fill_id", "coin", "rung", "L", "P0", "tick", "t_F1", "t_F3_1", "t_F3d_1", "t_F3_3", "real",
                        "method", "shift"] if c in F.columns]
    F = F[keep]
    O = pd.read_parquet(f"{RUNS}/{run}/outcomes.parquet", columns=OCOLS,
                        filters=[("rule", "in", rules), ("exit", "in", exits)])
    Bn = pd.read_parquet(f"{RUNS}/{run}/bench.parquet", columns=["fill_id", "rule", "alert_M", "alert_px_M", "alert_t_M"],
                         filters=[("rule", "in", rules)])
    return F, O, Bn


def flip_sample(F, O, rule, cost, exit="FLIP"):
    tcol = "t_" + rule
    f = F[F[tcol] >= 0]
    o = O[(O.rule == rule) & (O.exit == exit) & (O.cost == cost)]
    n_all = len(o)
    o = o[o.complete.astype(bool)]
    d = f.merge(o, on="fill_id", how="inner")
    d = d[np.isfinite(d["delta"])].copy()
    d["time"] = minutes_to_ts(d[tcol])
    d = d.sort_values(["time", "fill_id"]).reset_index(drop=True)
    return d, n_all


def bench_sample(F, Bn, rule):
    tcol = "t_" + rule
    f = F[F[tcol] >= 0]
    b = Bn[Bn.rule == rule]
    d = f.merge(b.drop(columns="rule"), on="fill_id", how="inner")
    d = d[np.isfinite(d["alert_M"])].copy()
    d["time"] = minutes_to_ts(d[tcol])
    d = d.sort_values(["time", "fill_id"]).reset_index(drop=True)
    return d


def gate_set(y, times, r=None):
    mb, ep = M.my_month_blocks(times)
    hf = (pd.to_datetime(pd.Series(times), utc=True) >= pd.Timestamp("2023-01-01", tz="UTC")).to_numpy()
    out = {}
    if r is not None:
        out["mean_r"] = float(np.mean(r))
    out["half1_mean"] = float(np.mean(y[~hf]))
    out["half2_mean"] = float(np.mean(y[hf]))
    out["n_half1"], out["n_half2"] = int((~hf).sum()), int(hf.sum())
    # worst month-block: the one whose removal lowers the mean most
    best = None
    for b in np.unique(mb):
        m_ = float(np.mean(y[mb != b]))
        if best is None or m_ < best[0]:
            best = (m_, int(b), int((mb == b).sum()))
    out["no_worst_block_mean"], out["worst_block"], out["worst_block_n"] = best
    # biggest episode: most fills (ties: earliest)
    u, cnt = np.unique(ep, return_counts=True)
    big = u[np.lexsort((u, -cnt))[0]]
    out["no_biggest_episode_mean"] = float(np.mean(y[ep != big]))
    out["biggest_episode"] = int(big)
    out["biggest_episode_n"] = int((ep == big).sum())
    t = pd.to_datetime(pd.Series(times), utc=True)
    out["biggest_episode_days"] = f"{t[ep == big].min().date()}..{t[ep == big].max().date()}"
    return out, mb, ep, hf


res = {}
# ------------------------------------------------------------------ P1 on U-Q1
F, O, Bn = load("P1__U_Q1", ["F1", "F3_1"], ["FLIP", "FLIP_bot"])
print("P1/U_Q1 fills:", len(F), " F1 fills:", int((F.t_F1 >= 0).sum()), " F3_1 fills:", int((F.t_F3_1 >= 0).sum()),
      " F3_1 fills without an F1 fill:", int(((F.t_F3_1 >= 0) & (F.t_F1 < 0)).sum()))
# H1 sample
d1, n_all = flip_sample(F, O, "F1", "C-RH")
s1 = pd.read_csv(f"{R}/primary/samples_H1.csv")
mm = d1.merge(s1, on="fill_id", suffixes=("", "_s"))
print(f"H1 rebuilt: {len(d1)} of {n_all} FLIP/C-RH rows complete; ids == sample file: "
      f"{set(d1.fill_id) == set(s1.fill_id)}; max|y-delta| {np.abs(mm.y - mm.delta).max():.2e}; max|r-r_s| {np.abs(mm.r - mm.r_s).max():.2e}")
# arithmetic of r and delta
r_chk = d1.exit_px * (1 - C) / (d1.L * (1 + C)) - 1
print(f"H1 r == exit_px(1-c)/(L(1+c)) - 1: max abs diff {np.abs(r_chk - d1.r).max():.2e}; "
      f"delta == r - twin_mean: {np.abs(d1.r - d1.twin_mean - d1.delta).max():.2e}; twin_n min {d1.twin_n.min()} max {d1.twin_n.max()}")
# target R1/2 = ceil_tick(L + (P0-L)/2)
tgt = np.ceil(((d1.L + 0.5 * (d1.P0 - d1.L)) / d1.tick).round(9)) * d1.tick
print(f"target == ceil_tau(L + (P0-L)/2): max rel diff {np.nanmax(np.abs(tgt / d1.target - 1)):.2e}; exit kinds {d1.exit_kind.value_counts().to_dict()}")
g1, mb1, ep1, hf1 = gate_set(d1.delta.to_numpy(float), d1.time, r=d1.r.to_numpy(float))
# H2R sample
d2 = bench_sample(F, Bn, "F1")
s2 = pd.read_csv(f"{R}/primary/samples_H2R.csv")
mm2 = d2.merge(s2, on="fill_id")
print(f"H2R rebuilt: {len(d2)}; ids == sample file: {set(d2.fill_id) == set(s2.fill_id)}; "
      f"max|y-alert_M| {np.abs(mm2.y - mm2.alert_M).max():.2e}; alert_M == alert_px_M/L - 1: "
      f"{np.abs(d2.alert_px_M / d2.L - 1 - d2.alert_M).max():.2e}")
g2, mb2, ep2, hf2 = gate_set(d2.alert_M.to_numpy(float), d2.time)
# F3 gate (s = 1%) on the F3_1 rows
f31, n31 = flip_sample(F, O, "F3_1", "RH")
f32 = bench_sample(F, Bn, "F3_1")
print(f"F3_1 FLIP/RH complete: {len(f31)} of {n31}; F3_1 bench alert_M finite: {len(f32)}")
res["H1_F3_mean"] = float(f31.delta.mean())
res["H2R_F3_mean"] = float(f32.alert_M.mean())
# F3 r arithmetic (route cost: exit x (1 - 0.0095) for market sells? target fills at R1/2 on index; fill pays L)
# bot rows
db, _ = flip_sample(F, O, "F1", "C-RH", exit="FLIP_bot")
f3b, _ = flip_sample(F, O, "F3_1", "RH", exit="FLIP_bot")
gb, _, _, _ = gate_set(db.delta.to_numpy(float), db.time, r=db.r.to_numpy(float))
res["bot_F3_mean"] = float(f3b.delta.mean())
res["bot_sample"] = db[["fill_id", "delta", "time"]]
print("maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
del O
# ------------------------------------------------------------------ P1 on U-B (gate)
FB, OB, BB = load("P1__U_B", ["F1"], ["FLIP", "FLIP_bot"])
ub1, nub = flip_sample(FB, OB, "F1", "C-RH")
ubb, _ = flip_sample(FB, OB, "F1", "C-RH", exit="FLIP_bot")
ub2 = bench_sample(FB, BB, "F1")
print(f"U-B: F1 fills {int((FB.t_F1 >= 0).sum())}; FLIP/C-RH complete {len(ub1)} of {nub}; alert finite {len(ub2)}")
res["H1_UB_mean"] = float(ub1.delta.mean())
res["H2R_UB_mean"] = float(ub2.alert_M.mean())
res["bot_UB_mean"] = float(ubb.delta.mean())
print("maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)

# ------------------------------------------------------------------ report
def show(name, g, ub, f3, file_gates):
    print(f"\n=== {name} gates (mine)  vs  primary.json gates {file_gates}")
    for k, v in g.items():
        print(f"   {k}: {v}")
    print(f"   U-B mean: {ub:.6f}   F3_1 mean: {f3:.6f}")


show("H1", g1, res["H1_UB_mean"], res["H1_F3_mean"], P["gates"]["H1"])
show("H2R", g2, res["H2R_UB_mean"], res["H2R_F3_mean"], P["gates"]["H2R"])
show("H1 bot", gb, res["bot_UB_mean"], res["bot_F3_mean"], P["bot"]["gates"])
print("\nbeside file: H1 U_B est", P["beside"]["H1"]["U_B"]["estimate"], " F3_1", P["beside"]["H1"]["F3_1"]["estimate"],
      "| H2R U_B", P["beside"]["H2R"]["U_B"]["estimate"], " F3_1", P["beside"]["H2R"]["F3_1"]["estimate"],
      "| mean_r", P["beside"]["H1"]["mean_r"])

# halves with intervals (month-blocks rebuilt on each half's own fills)
for name, d, ycol in (("H1", d1, "delta"), ("H2R", d2, "alert_M")):
    for h in (0, 1):
        hf = (d.time >= pd.Timestamp("2023-01-01", tz="UTC")).to_numpy() == bool(h)
        sub = d[hf]
        mb_h, _ = M.my_month_blocks(sub.time)
        r = M.test_mean(sub[ycol].to_numpy(float), mb_h, seed=20261118)
        print(f"{name} half{h + 1}: n {r['n']}, G {r['G']}, G* {r['gstar']:.2f}, mean {r['est']:+.5f}, CR1 se {r['se']:.5f}, "
              f"t {r['t']:+.3f}, 95% CI (union) {r['ci95'][0]:+.4f}..{r['ci95'][1]:+.4f}, t-CI {r['ci95_t'][0]:+.4f}..{r['ci95_t'][1]:+.4f}")
    # also the half means on the FULL-sample month-block partition
# save samples for later steps
d1[["fill_id", "coin", "time", "rung", "delta", "r", "t_F3_1"]].to_parquet(
    "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest/h1.parquet")
d2[["fill_id", "coin", "time", "rung", "alert_M", "t_F3_1", "L", "alert_px_M", "alert_t_M", "t_F1"]].to_parquet(
    "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest/h2r.parquet")
db[["fill_id", "time", "delta", "r", "t_F3_1"]].to_parquet(
    "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest/bot.parquet")
print("maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
