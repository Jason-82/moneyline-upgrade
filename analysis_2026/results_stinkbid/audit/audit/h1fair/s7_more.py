"""Step 7: go-live lags; CIs for subsets; F3_1 rows (index route) timing and composition; rule-M timing on the U-B and
U-C runs; crossing-twin effect; the H2R / H1 decomposition consistency."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
import numpy as np
import pandas as pd
from common import *
import importlib.util
spec = importlib.util.spec_from_file_location("s4b", f"{OUT}/s4b_bars.py")
# reuse only my own rule_m from my script (not the engine's)
src = open(f"{OUT}/s4b_bars.py").read()
ns = {}
exec(src.split("def ceil_tick")[0].split("NY = ZoneInfo")[0] + "NY = ZoneInfo('America/New_York')\n" +
     "def rule_m" + src.split("def rule_m")[1].split("def ceil_tick")[0], ns)
rule_m = ns["rule_m"]

R = pd.read_parquet(f"{OUT}/bars_pass2.parquet")
O = pd.read_parquet(f"{OUT}/h1rows2.parquet")
J = O.merge(R.drop(columns=["coin", "g_me", "S_me"]), on="fill_id")
lag = J.t_g - J.g_me
print("go-live lag (first live bar minus the rule-M time), fills:", lag.describe().to_dict(), " >5 min:",
      int((lag > 5).sum()))
print("price at/above R1/2 at some minute between the fill and go-live:", int((J.maxh_pre >= J.target).sum()),
      " of which sold as target/marketable:", int(((J.maxh_pre >= J.target) & J.exit_kind.isin(["target", "marketable"])).sum()))
J["prev_above"] = J.prev_c / J.L - 1
J["depth"] = 1 - J.l / J.L
for lab, m in (("slides (prev close < 1% above L)", J.prev_above < 0.01),
               ("prev close 1-3% above L", (J.prev_above >= 0.01) & (J.prev_above < 0.03)),
               ("prev close >= 3% above L", J.prev_above >= 0.03),
               ("low < 1% below L", J.depth < 0.01), ("low >= 3% below L", J.depth >= 0.03)):
    print(f"{lab}: {fmt(cr1(J.delta[m], J.mb_me[m]))}")
ow = J[~J.pooled_me & (J.twin_crossed == 0)]
print("crossing-twin effect: fills", int((J.twin_crossed > 0).sum()),
      " mean (engine - mine) twin mean over them:", (J.twin_mean - J.twin_me)[J.twin_crossed > 0].mean(),
      " effect on the H1 mean:", ((J.twin_mean - J.twin_me)[J.twin_crossed > 0].sum()) / len(J))

# ---- F3_1 rows (index route)
o3 = load_out(rule="F3_1", cost="RH")
print("\nF3_1 FLIP rows:", len(o3), " finite delta:", int(np.isfinite(o3.delta).sum()), " kinds:",
      o3.exit_kind.value_counts().to_dict(), " pooled:", int(o3.twin_pooled.sum()))
Fx = load_fills(cols=["fill_id", "t_F1", "t_F3_1", "coin"])
o3 = o3.merge(Fx, on="fill_id", suffixes=("", "_f"))
o3 = o3[np.isfinite(o3.delta)].copy()
blk, ep = month_blocks_from_times(o3.t_F3_1.to_numpy())
o3["mb"] = blk
print("F3_1 H1 row (my CR1 on month-blocks of the F3 fill time):", fmt(cr1(o3.delta, o3.mb)))
g3 = rule_m(o3.t_F3_1.to_numpy())
for kind in ("target", "marketable", "stop"):
    s = (o3.exit_kind == kind).to_numpy()
    if s.any():
        print(f"  F3 {kind}: n={s.sum()} min(exit_t - M(fill)) = {(o3.exit_t.to_numpy()[s] - g3[s]).min()}")
both = o3.merge(O[["fill_id", "delta", "r"]], on="fill_id", suffixes=("_f3", "_f1"))
print("F3 fills also F1-filled:", len(both), " corr(delta F1, delta F3):", np.corrcoef(both.delta_f3, both.delta_f1)[0, 1],
      " mean F1 delta on them:", both.delta_f1.mean(), " mean F3 delta:", both.delta_f3.mean())
print("F3 fill minute - F1 fill minute (min):", (both.t_F3_1 - both.t_F1).describe().to_dict())
only3 = o3[~o3.fill_id.isin(O.fill_id)]
print("F3 fills without an F1 fill in H1's sample:", len(only3))

# ---- rule M on the other runs (U-B, U-C)
for run in ("P1__U_B", "P1__U_C"):
    ob = load_out(run=run)
    fb = load_fills(run=run, cols=["fill_id", "t_F1"])
    ob = ob.merge(fb, on="fill_id")
    ob = ob[np.isfinite(ob.r)]
    gb = rule_m(ob.t_F1.to_numpy())
    sb = rule_m(ob.t_F1.to_numpy() + 72 * 60)
    k = ob.exit_kind.to_numpy()
    et = ob.exit_t.to_numpy()
    print(f"\n{run}: rows {len(ob)} kinds {pd.Series(k).value_counts().to_dict()}")
    for kind in ("target", "marketable"):
        s = k == kind
        print(f"  {kind}: min(exit_t - M(fill)) {(et[s] - gb[s]).min()}  exits at/after the stop: {(et[s] >= sb[s]).sum()}")
    s = k == "stop"
    print(f"  stop: min(exit_t - M(fill + 72 h)) {(et[s] - sb[s]).min()}  max {(et[s] - sb[s]).max()}")
    s = k == "delist"
    print(f"  delist exits: {s.sum()}")
