"""Step 4a: per-coin daily segment ids (stinkbid_data.d1_panel's seg, the loader) for the coins with H1 fills and their
swap successors; U-Q1 member months. Saved small, so the bar pass does not hold the daily panel."""
import sys
import resource
sys.path.insert(0, "/home/user/moneyline-upgrade")
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
import numpy as np
import pandas as pd
from common import *
from analysis_2026 import stinkbid_data as sbd

O = pd.read_parquet(f"{OUT}/h1rows2.parquet", columns=["fill_id", "coin"])
coins = sorted(O.coin.unique())
need = set(coins)
for c in coins:
    x = c
    while x in sbd.SWAPS:
        x = sbd.SWAPS[x][0]
        need.add(x)
p = sbd.d1_panel()
p = p[p.coin.isin(need) & (p.seg >= 0)][["coin", "day", "seg", "open", "close", "trades"]].copy()
p.to_parquet(f"{OUT}/segmap.parquet")
print("coins", len(coins), "with successors", len(need), "rows", len(p))
u = pd.read_parquet(f"{ROOT}/data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
u[u.coin.isin(need)].to_parquet(f"{OUT}/univ.parquet")
sw = {c: sbd.SWAPS[c][:2] for c in need if c in sbd.SWAPS}
print("swaps among needed coins:", sw)
syms = {c: sbd.coin_sym(c) for c in need}
pd.DataFrame([(c, s[0], s[1], s[2]) for c, s in syms.items()], columns=["coin", "sym", "lo", "hi"]).to_parquet(
    f"{OUT}/syms.parquet")
print({c: s for c, s in syms.items() if s[1] or s[2]})
print("peak RSS MB:", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
