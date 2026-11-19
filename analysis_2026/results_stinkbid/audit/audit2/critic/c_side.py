"""Critic side checks: (C) F3-route twin means against F1 twin means on the same fills (the F3 gate's benchmark was
never rebuilt by any lens); (D) rung x half of the flip's r_f and Delta (the sheet prints all three rungs)."""
import numpy as np
import pandas as pd
from scipy import stats

RUN = "/home/user/moneyline-upgrade/data/stinkbid/runs/outcomes/P1__U_Q1"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit2/critic"


def cr1(y, g):
    y = np.asarray(y, float); g = np.asarray(g)
    n = len(y); m = y.mean()
    u = pd.Series(y - m).groupby(g).sum().to_numpy()
    ng = pd.Series(np.ones(n)).groupby(g).sum().to_numpy()
    G = len(u); se = np.sqrt(G / (G - 1) * (u ** 2).sum()) / n
    gs = (ng ** 2).sum() ** 2 / (ng ** 4).sum()
    q = stats.t.ppf(0.975, gs - 1)
    return dict(n=n, mean=round(m, 5), lo=round(m - q * se, 5), hi=round(m + q * se, 5), G=G, gstar=round(gs, 2))


o = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "twin_mean", "twin_n",
                                                        "twin_pooled", "delta", "complete", "exit_kind"])
o = o[(o.exit == "FLIP") & (((o.rule == "F1") & (o.cost == "C-RH")) | (o.rule == "F3_1")) & o.complete]
a = o[o.rule == "F1"].set_index("fill_id")
b = o[o.rule == "F3_1"].set_index("fill_id")
j = a.join(b, lsuffix="_F1", rsuffix="_F3", how="inner")
d = j.twin_mean_F3 - j.twin_mean_F1
print("C) common fills", len(j), "| twin_mean F1", round(j.twin_mean_F1.mean(), 5), "F3", round(j.twin_mean_F3.mean(), 5),
      "| diff mean", round(d.mean(), 5), "sd", round(d.std(), 5), "corr", round(np.corrcoef(j.twin_mean_F1, j.twin_mean_F3)[0, 1], 4))
print("   twin_n F3 min/median", int(j.twin_n_F3.min()), int(j.twin_n_F3.median()), "| pooled F1", int(j.twin_pooled_F1.sum()),
      "pooled F3", int(j.twin_pooled_F3.sum()), "| pooled flags equal", bool((j.twin_pooled_F1 == j.twin_pooled_F3).all()))
print("   |diff| quantiles", np.round(np.quantile(d.abs(), [0.5, 0.9, 0.99, 1.0]), 5))
print("   r on common fills: F1", round(j.r_F1.mean(), 5), "F3", round(j.r_F3.mean(), 5), "| exit kinds F1/F3 target share",
      round((j.exit_kind_F1 == "target").mean(), 3), round((j.exit_kind_F3 == "target").mean(), 3))

f = pd.read_csv(f"{OUT}/a_flip_rows_F1.csv")
print("D) rung x half (F1, C-RH): r_f and Delta with CR1 month-block 95% CIs")
for (k, h), g in f.groupby(["rung", "half"]):
    print("   k", k, "half", int(h) + 1, "r_f", cr1(g.r, g.month_block), "| Delta", cr1(g.delta, g.month_block))
