"""Critic check B (part 4): the r_res = 3.35% D7 rows pay reserved cash a flat 3.35% a year in 2020-2022, when the
T-bill was 0-2%. Rebuild the F3 flip account with r_res(t) = min(3.35%, T-bill(t)) and compare with the flat rule."""
import json
import numpy as np
import pandas as pd
import importlib.util, sys
spec = importlib.util.spec_from_file_location("se", "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit2/critic/b_d7_single_events.py")
se = importlib.util.module_from_spec(spec); spec.loader.exec_module(se)

RUN, Q, DAY = se.RUN, se.Q, se.DAY
bids = pd.read_parquet(f"{RUN}/bids.parquet", columns=["coin", "rung", "t0", "life_end", "bid_id"])
fills = pd.read_parquet(f"{RUN}/fills.parquet", columns=["bid_id", "fill_id", "t_F3_1"])
o = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "exit_t"])
o = o[(o.rule == "F3_1") & (o.exit == "FLIP") & (o.cost == "RH")][["fill_id", "r", "exit_t"]]
F = fills[fills.t_F3_1 >= 0].merge(o, on="fill_id"); F = F[F.r.notna()].set_index("bid_id")
d0 = int(bids.t0.min() // DAY); end_day = int((se.END - pd.Timestamp("1970-01-01")).days)
days = np.arange(d0, end_day + 1); nd = len(days); dates = pd.to_datetime(days, unit="D")
tb = se.tbill_pct(dates) / 100.0
rf_day = tb / 365.0
me = pd.PeriodIndex(dates, freq="M"); me_idx = np.r_[np.flatnonzero(me[1:] != me[:-1]), nd - 1]; labels = me[me_idx].astype(str)
K = 3 * Q * int(bids.groupby("t0").coin.nunique().max())
di = lambda tm: int(np.clip(np.searchsorted(days, int(tm) // DAY), 0, nd - 1))
flows, reserved, posv, busy = np.zeros(nd), np.zeros(nd), np.zeros(nd), {}
for b in bids.sort_values(["t0", "coin", "rung"]).itertuples():
    key = (b.coin, b.rung)
    if busy.get(key, -1) > b.t0:
        continue
    a, il = di(b.t0), di(b.life_end); reserved[a:il] += Q
    if b.bid_id not in F.index:
        busy[key] = b.life_end; continue
    f = F.loc[b.bid_id]; tf, te = int(f.t_F3_1), int(f.exit_t); busy[key] = te
    i_f, i_e = di(tf), di(te); reserved[i_f:il] -= Q; flows[i_f] -= Q; flows[i_e] += Q * (1 + float(f.r))
    if i_e > i_f: posv[i_f:i_e] += Q
mix = se.git_csv("analysis_2026/results_stinkbid/desc/d7_monthly_F3_1_0.0335.csv", index_col=0)["B-MIX"]
mix.index = mix.index.astype(str); mix = mix.reindex(labels)
out = {}
for name, rres in [("flat 3.35% (record's rule)", np.full(nd, 0.0335)), ("min(3.35%, T-bill)", np.minimum(0.0335, tb))]:
    cash = np.zeros(nd); c = K
    for i in range(nd):
        c += (c - reserved[i]) * rf_day[i] + reserved[i] * rres[i] / 365.0 + flows[i]; cash[i] = c
    V = cash + posv; Vm = V[me_idx]; r = pd.Series(Vm / np.r_[V[0], Vm[:-1]] - 1, index=labels)
    out[name] = dict(cagr=round(float(se.cagr(r)), 5), vs_BMIX_12m=se.boot_diff(r, mix, 12), vs_BMIX_6m=se.boot_diff(r, mix, 6),
                     share_days_rres_above_tbill=round(float(np.mean(0.0335 > tb)), 3),
                     subsidy_per_year_share_of_K_2020_2022=round(float((np.maximum(rres - tb, 0) * reserved / 365)[dates < "2023-01-01"].sum() / K / 3), 5))
print(json.dumps(out, indent=1))
json.dump(out, open("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit2/critic/b_d7_rres_cap.json", "w"), indent=1)
