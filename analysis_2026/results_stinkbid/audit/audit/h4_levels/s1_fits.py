"""Step 1: frames, month-block partition, per-method coin-week FE fits with CR1; compare with h4_methods.csv."""
import sys
import json
import resource
import numpy as np
import pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h4_levels")
import h4_common as hc

OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h4_levels"
B, F, O = hc.load()

# --- sanity: outcomes delta = r - twin_mean; keys unique
o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.lat == "M") & (O.cost == "C-RH")]
print("F1 FLIP M C-RH rows", len(o), "complete", int(o.complete.sum()), "unique fill_id", o.fill_id.is_unique)
d = (o.r - o.twin_mean - o.delta).abs()
print("max |r - twin_mean - delta| =", float(np.nanmax(d.to_numpy())), " NaN delta:", int(o.delta.isna().sum()))
print("fills unique fill_id", F.fill_id.is_unique, " unique bid_id", F.bid_id.is_unique, " F1 fills", int((F.t_F1 >= 0).sum()),
      " F3_1 fills", int((F.t_F3_1 >= 0).sum()))
# fills carry the bid's fields? compare delta with bids
m = F.merge(B[["bid_id", "delta", "variant", "cw", "real", "shift"]], on="bid_id", suffixes=("", "_b"))
print("fills' bid fields agree with bids:", bool(np.allclose(m.delta, m.delta_b) and (m.variant == m.variant_b).all()
                                                 and (m.cw == m.cw_b).all() and (m.real == m.real_b).all()))

out = {}
for rule in ("F1", "F3_1"):
    fr = hc.frames(B, F, O, rule)
    allt = np.concatenate([fr[mm].time.to_numpy() for mm in hc.METHODS])
    lab, ep = hc.month_blocks(allt)
    pos = 0
    for mm in hc.METHODS:
        k = len(fr[mm])
        fr[mm]["block"] = lab[pos:pos + k]
        pos += k
    Gu = len(np.unique(lab))
    print(f"\n=== rule {rule}: union stacked fills {len(allt)}, union month-blocks G_union = {Gu}, episodes {len(np.unique(ep))}")
    rows = []
    for mm in hc.METHODS:
        g = fr[mm]
        f = hc.fe_fit(g.y, np.column_stack([g.realf, g.depth]), g.cw, g.block)
        b, c = f["theta"]
        se = f["se"][0]
        t = b / se
        gs = f["gstar"]
        rows.append(dict(method=mm, n_frame=len(g), n_real_frame=int(g.realf.sum()), n=f["n"], n_cw=f["n_fe"], G=f["G"],
                         gstar=gs, b=b, se=se, t=t, c=c, se_c=f["se"][1], p_t=hc.tsf(t, gs - 1)))
        g.to_parquet(f"{OUT}/frame_{rule}_{mm}.parquet")
    tab = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(tab.to_string(index=False))
    out[rule] = tab
    tab.to_csv(f"{OUT}/fits_{rule}.csv", index=False)

ref = pd.read_csv("analysis_2026/results_stinkbid/primary/h4_methods.csv")
mine = out["F1"].set_index("method")
ref = ref.set_index("method")
print("\n=== F1 vs h4_methods.csv (max abs diff)")
for col in ("n", "n_cw", "G", "gstar", "b", "se", "t", "c", "p_t"):
    dd = (mine[col] - ref[col]).abs()
    print(f"  {col:6s} mine {mine[col].round(8).tolist()}  ref {ref[col].round(8).tolist()}  maxdiff {dd.max():.3g}")
print("peak RSS MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
