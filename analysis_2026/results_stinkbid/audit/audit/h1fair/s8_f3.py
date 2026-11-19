"""Step 8: F1 fills that the index route never filled; F3 deltas of the bad-print candidates; halves' CIs."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
import numpy as np
import pandas as pd
from common import *

J = pd.read_parquet(f"{OUT}/joined2.parquet")
tot = J.delta.sum()
f3 = J.t_F3_1 >= 0
print("F1 fills with an F3_1 fill of the same bid:", int(f3.sum()), " without:", int((~f3).sum()),
      " F3-unverifiable (index missing):", int(J.idx_missing.fillna(0).astype(bool).sum()))
for lab, m in (("F3 also filled (F3-kept)", f3), ("F3 never filled (Binance-only)", ~f3)):
    d = cr1(J.delta[m], J.mb_me[m])
    print(f"  {lab}: {fmt(d)}  share of sum {J.delta[m].sum() / tot:+.1%}")
m = J.idx_low_rel > 1
print("index low above L in the F1 minute:", int(m.sum()), " of which F3 filled later/earlier:", int((m & f3).sum()))
o3 = load_out(rule="F3_1", cost="RH", cols=["fill_id", "delta", "r", "exit_kind"])
o3 = o3[np.isfinite(o3.delta)]
K = J.merge(o3.rename(columns={"delta": "delta3", "r": "r3", "exit_kind": "kind3"}), on="fill_id", how="left")
big = K.l < 0.9 * K.prev_c
mx5 = np.fmax(K.c, K.next5_maxc)
flag = big & (mx5 >= K.prev_c - 0.5 * (K.prev_c - K.l))
print("\nbad-print candidates (def B):", int(flag.sum()), " with an F3 row:", int(np.isfinite(K.delta3[flag]).sum()),
      " mean F1 delta:", K.delta[flag].mean(), " mean F1 delta where F3 exists:",
      K.delta[flag & np.isfinite(K.delta3)].mean(), " mean F3 delta:", K.delta3[flag].mean())
# halves
for h in (0, 1):
    s = J.half == h
    print(f"half {h + 1}: {fmt(cr1(J.delta[s], J.mb_me[s]))}")
# drop both: bad-print candidates (B) and F1 fills F3 never filled
keep = ~flag.to_numpy() & f3.to_numpy()
print("without bad-print candidates and without Binance-only fills:", fmt(cr1(J.delta[keep], J.mb_me[keep])))
# Delta with the go-live open as the entry for both (removes the resting order's pre-go-live gain)
print("\nshare of Delta accruing before go-live (gross, own-twin fills):")
ow = J[~J.pooled_me]
pre = ow.o_g / ow.L - 1 - ow.twin_pre
tot_g = (ow.exit_px_me / ow.L - 1) - ow.twin_gross
print(f"  gross delta {tot_g.mean():+.4f}; before go-live {pre.mean():+.4f} ({pre.mean() / tot_g.mean():.0%});"
      f" after go-live {tot_g.mean() - pre.mean():+.4f}")
