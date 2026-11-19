"""Step 3: how much of H1 comes from fills whose rule-M go-live delay is short (fills just before 07:00 New York),
and the bot-latency row for comparison."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from common import *

O = pd.read_parquet(f"{OUT}/h1rows2.parquet")
d = O.g_me - O.t_F1
O["delay"] = d
O["cls"] = np.where(d < 60, "<60 (06:00-06:59 NY)", np.where(d == 60, "=60 (day)", ">60 (night)"))
NY = ZoneInfo("America/New_York")
O["ny_h"] = O.ts.dt.tz_convert(NY).dt.hour
tot = O.delta.sum()
g = O.groupby("cls")
print(pd.DataFrame({"n": g.size(), "r_f": g.r.mean(), "twin": g.twin_mean.mean(), "delta": g.delta.mean(),
                    "share": g.delta.sum() / tot, "target_rate": g.exit_kind.apply(lambda s: (s == "target").mean())})
      .to_string(float_format=lambda x: f"{x:+.4f}"))
for c in O.cls.unique():
    k = O.cls != c
    print("without", c, fmt(cr1(O.delta[k], O.mb_me[k])))
s = O[O.delay < 60]
print("short-delay fills: delay distribution", s.delay.describe().to_dict())
print("short-delay target exits within 60 min of the fill:", ((s.exit_kind == "target") & (s.exit_t - s.t_F1 < 60)).sum())
print("all target exits within 60 min of the fill:", ((O.exit_kind == "target") & (O.exit_t - O.t_F1 < 60)).sum())
print("fills by NY hour:\n", O.groupby("ny_h").agg(n=("delta", "size"), delta=("delta", "mean")).T.to_string())

# bot-latency row and the 'delay >= 60' counterfactual: what if every fill waited >= 60 minutes?
b = load_out(lat="bot", exit="FLIP_bot")
b = b[np.isfinite(b.delta)]
bb = b.merge(O[["fill_id", "mb_me"]], on="fill_id")
print("\nX-FLIP-bot (engine rows):", fmt(cr1(bb.delta, bb.mb_me)))
