"""Part C: seller-initiated aggTrades dollars below L accumulated from the fill until the X-FLIP exit (rule M, C-RH),
(1) from my own §8.3 windows on the raw 1m bars + the per-minute aggTrades cache, (2) from the engine's cap_curve
read one row group at a time. Per rung p10 and 0.25 x p10. Also: how much of the life-sum is printed after the exit.
"""
import glob
import os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

OUTD = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/capcap"
RD = "data/stinkbid/runs/outcomes/P1__U_Q1/"
F = pd.read_parquet(RD + "fills.parquet", columns=["coin", "rung", "t_F1", "life_end", "L", "bid_id", "fill_id",
                                                    "agg_first", "agg_life"])
F = F[F.t_F1 >= 0].reset_index(drop=True)
O = pd.read_parquet(RD + "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "exit_t", "exit_kind"],
                    filters=[("rule", "==", "F1"), ("exit", "==", "FLIP"), ("lat", "==", "M"), ("cost", "==", "C-RH")])
print("flip rows:", len(O), O.exit_kind.value_counts().to_dict(), " exit_t NaN:", int(O.exit_t.isna().sum()))
F = F.merge(O[["fill_id", "exit_t", "exit_kind"]], on="fill_id", how="left")
print("fills without a flip row:", int(F.exit_t.isna().sum()))
WIN = 60


def windows(t, lo, live, L, m0, end):
    out = []
    i = int(np.searchsorted(t, m0))
    if i >= len(t) or t[i] != m0:
        return None
    n = len(t)
    while i is not None and i < n and t[i] < end:
        ts = t[i]
        k = i
        while k < n and t[k] < end and t[k] < ts + WIN:
            if k > i and live[k] and lo[k] > L:
                break
            k += 1
        out.append((i, k))
        m = k
        nxt = None
        while m < n and t[m] < end:
            if live[m] and lo[m] < L * (1 - 1e-12):
                nxt = m
                break
            m += 1
        i = nxt
    return out


res = []
for coin in sorted(F.coin.unique()):
    g = F[F.coin == coin]
    lo_t = pd.Timestamp(int(g.t_F1.min()) * 60, unit="s", tz="UTC")
    hi_t = pd.Timestamp(int(g.life_end.max()) * 60, unit="s", tz="UTC")
    k = pd.read_parquet(f"data/stinkbid/m1_spot/{coin}USDT.parquet", columns=["open_time", "low", "trades"],
                        filters=[("open_time", ">=", lo_t), ("open_time", "<", hi_t)]).sort_values("open_time")
    t = (k.open_time.astype("int64").to_numpy() // 60_000_000_000).astype(np.int64)
    lo = k.low.to_numpy(float)
    live = k.trades.to_numpy() > 0
    del k
    files = sorted(glob.glob(f"data/stinkbid/agg_cap/{coin}/*.parquet"))
    A = pd.concat([pd.read_parquet(x, columns=["key", "minute", "sell_below_usd"]) for x in files], ignore_index=True)
    A["L"] = A.key.str.split("|").str[1].astype(float)
    A["m"] = (A.minute.to_numpy(np.int64) // 60_000_000).astype(np.int64)
    A = A.drop_duplicates(["L", "m"])
    agg = {Lv: pd.Series(gg.sell_below_usd.to_numpy(float), index=gg.m.to_numpy(np.int64)) for Lv, gg in A.groupby("L")}
    del A
    for r in g.itertuples():
        W = windows(t, lo, live, r.L, int(r.t_F1), int(r.life_end))
        mins = np.concatenate([t[a:b] for a, b in W])
        s = agg.get(r.L)
        v = s.reindex(mins).fillna(0.0).to_numpy(float) if s is not None else np.zeros(len(mins))
        ex = r.exit_t if np.isfinite(r.exit_t) else np.inf
        res.append(dict(fill_id=r.fill_id, my_life=float(v.sum()), my_to_exit=float(v[mins < ex].sum()),
                        my_to_exit_incl=float(v[mins <= ex].sum()),
                        win1_end=int(t[W[0][1] - 1]) + 1))
R = pd.DataFrame(res)
F = F.merge(R, on="fill_id")
print("my life == agg_life:", int(np.isclose(F.my_life, F.agg_life, rtol=1e-9, atol=1e-6).sum()), "/", len(F))

# (2) the engine's cap_curve, one row group at a time: cum at the last curve minute before the exit minute
pf = pq.ParquetFile(RD + "cap_curve.parquet")
ex_by_bid = dict(zip(F.bid_id.astype(np.int64), np.where(np.isfinite(F.exit_t), F.exit_t, np.inf)))
best = {}      # bid -> (minute, cum) of the last row with minute < exit
last = {}      # bid -> (minute, cum) of the last row overall
for rg in range(pf.num_row_groups):
    T = pf.read_row_group(rg, columns=["bid_id", "minute", "cum"]).to_pandas()
    T = T[T.bid_id.isin(ex_by_bid.keys())]
    T["ex"] = T.bid_id.map(ex_by_bid)
    for which, sub in (("best", T[T.minute < T.ex]), ("last", T)):
        if not len(sub):
            continue
        idx = sub.groupby("bid_id").minute.idxmax()
        top = sub.loc[idx]
        dct = best if which == "best" else last
        for b, m, c in zip(top.bid_id, top.minute, top.cum):
            if b not in dct or m > dct[b][0]:
                dct[b] = (m, c)
    del T
F["cc_to_exit"] = F.bid_id.map(lambda b: best.get(b, (0, 0.0))[1])
F["cc_last"] = F.bid_id.map(lambda b: last.get(b, (0, np.nan))[1])
print("cap_curve last cum == agg_life:", int(np.isclose(F.cc_last, F.agg_life, rtol=1e-9, atol=1e-6).sum()), "/", len(F))
print("cap_curve cum before exit == mine:", int(np.isclose(F.cc_to_exit, F.my_to_exit, rtol=1e-9, atol=1e-6).sum()), "/", len(F))
F["exit_after_win1"] = F.exit_t >= F.win1_end
print("flip exit at/after the end of the fill's own window:", int(F.exit_after_win1.sum()), "/", len(F),
      "; exit minus fill (hours): median", round(float(((F.exit_t - F.t_F1) / 60).median()), 1))
print("\nper rung p10 / cap: first window | up to the flip exit (mine; cap_curve) | life (printed)")
for kk in (6.0, 8.0, 10.0):
    m = F.rung == kk
    q = lambda c: float(np.quantile(F.loc[m, c], .1))
    print(f"k={kk:g} n={int(m.sum())}: first ${q('agg_first'):,.0f} (cap ${.25 * q('agg_first'):,.0f}) | to exit "
          f"${q('my_to_exit'):,.0f} (cap ${.25 * q('my_to_exit'):,.0f}); cap_curve ${q('cc_to_exit'):,.0f}; incl. exit minute "
          f"${q('my_to_exit_incl'):,.0f} | life ${q('agg_life'):,.0f} (cap ${.25 * q('agg_life'):,.0f})")
sh = 1 - F.my_to_exit / F.agg_life
print("share of the life-sum printed at/after the flip exit: median", round(float(sh.median()), 3),
      " mean", round(float(sh.mean()), 3))
F.to_parquet(f"{OUTD}/c_to_exit.parquet")
