import sys, runpy
import numpy as np, pandas as pd
S = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/lookahead"
g = runpy.run_path(f"{S}/b_univ.py")
u = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_B", "U_Q1"])
full = g["load_panel"]()
first = g["first_listing"](full)          # listing months: S3 file listing (static) + own first bar
pm = g["preds_map"]()
del full
res = []
for M in ["2020-01", "2020-03", "2020-11", "2021-05", "2021-07", "2022-05", "2022-11", "2023-08", "2024-09",
          "2025-03", "2025-10", "2026-08"]:
    t1 = pd.Timestamp(M + "-01") - pd.Timedelta("1D")
    a = g["load_panel"](cut_day=t1)
    assert a.day.max() <= t1
    months_all = [g["ms"](i) for i in range(g["mi"]("2018-08"), g["mi"](M) + 1)]
    # listing months restricted to those known before M (a first month after M cannot make a coin older)
    fl = {c: m for c, m in first.items() if m <= M}
    r = g["build"](a, months_all, [M], fl, pm)
    s = u[u.month == M].merge(r[["coin", "UB", "Q1"]], on="coin", how="outer")
    res.append(dict(month=M, coins=len(s), q1_stored=int(s.U_Q1.fillna(False).sum()), q1_trunc=int(s.Q1.fillna(False).sum()),
                    mismatch=int(((s.U_Q1.fillna(False)) != (s.Q1.fillna(False))).sum() + ((s.U_B.fillna(False)) != (s.UB.fillna(False))).sum())))
    print(res[-1], flush=True)
