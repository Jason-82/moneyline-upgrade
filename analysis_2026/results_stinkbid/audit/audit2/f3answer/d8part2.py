"""D8 part 2 (return from 72 h to 90 days against T-bills) on F1 (C-0) and F3_1 (RH), recomputed from the cached
P1__U_Q1 run with FRED DTB3 (forward-filled) as the T-bill; read-only."""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

BASE = "data/stinkbid/runs/outcomes/P1__U_Q1/"
fills = pq.read_table(BASE + "fills.parquet", columns=["fill_id", "t_F1", "t_F3_1"]).to_pandas()
o = pq.read_table(BASE + "outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "complete", "exit_px",
                                                      "exit_t"]).to_pandas()
x = pd.read_csv("data/stinkbid/macro/fred_DTB3.csv")
tb = pd.Series(pd.to_numeric(x["DTB3"], errors="coerce").to_numpy(), index=pd.to_datetime(x.iloc[:, 0])).dropna()
tb = tb.reindex(pd.date_range(tb.index.min(), "2026-12-31", freq="D")).ffill() / 100.0

for rule, cost in (("F1", "C-0"), ("F3_1", "RH")):
    t = "t_" + rule
    f = fills[fills[t] >= 0][["fill_id", t]]
    sel = (o.rule == rule) & (o.cost == cost) & o.complete.astype(bool) & np.isfinite(o.r.to_numpy(float))
    h = o[sel & (o.exit == "HOLD90")][["fill_id", "exit_px", "exit_t"]]
    k = o[sel & (o.exit == "TH72")][["fill_id", "exit_px", "exit_t"]].rename(columns={"exit_px": "px72", "exit_t": "t72"})
    m = f.merge(h, on="fill_id").merge(k, on="fill_id")
    m = m[(m.exit_px > 0) & (m.px72 > 0)]
    days = (m.exit_t.to_numpy(np.int64) - m.t72.to_numpy(np.int64)) / 1440
    fd = pd.to_datetime((m[t].to_numpy(np.int64) // 1440) * 86400, unit="s")
    rf = tb.reindex(fd).to_numpy()
    y = m.exit_px / m.px72 - 1 - rf * days / 365.0
    print(f"{rule} {cost}: D8 part 2 mean {100 * np.nanmean(y):+.2f}% over {len(m)} fills "
          f"(raw HOLD90/TH72 - 1: {100 * np.mean(m.exit_px / m.px72 - 1):+.2f}%)")
