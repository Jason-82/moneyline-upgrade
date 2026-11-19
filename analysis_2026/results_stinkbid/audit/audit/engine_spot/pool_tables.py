"""Per-day counts of eligible twin minutes (live spot minutes in the coin's U-Q1 member months) for every U-Q1 coin
(§10.1 B-TWIN pooled twins). Read-only; writes an npz under the scratchpad."""
import gc
import resource
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/engine_spot")
import recompute as rc  # noqa: E402

ROOT, OUT, DAY = rc.ROOT, rc.OUT, rc.DAY


def coin_days(coin):
    sym, lo, hi = rc.sbd.coin_sym(coin)
    d = pd.read_parquet(f"{ROOT}/data/stinkbid/d1_full_all.parquet", filters=[("sym", "==", sym)],
                        columns=["open_time", "open", "close", "trades"])
    d["day"] = d.open_time.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy().astype("datetime64[D]").astype(np.int64)
    d = d.sort_values("day")
    if lo:
        d = d[d.day >= int(np.datetime64(lo, "D").astype(np.int64))]
    if hi:
        d = d[d.day <= int(np.datetime64(hi, "D").astype(np.int64))]
    d = d[d.trades > 0]
    days_ok = set(d.day.tolist())
    tb = pq.read_table(f"{ROOT}/data/stinkbid/m1_spot/{sym}.parquet", columns=["open_time", "trades"])
    unit = tb.schema.field("open_time").type.unit
    div = {"ns": 60_000_000_000, "us": 60_000_000, "ms": 60_000, "s": 60}[unit]
    t = tb.column("open_time").cast("int64").to_numpy() // div
    tr = tb.column("trades").to_numpy()
    del tb
    day = t // DAY
    keep = np.ones(len(t), bool)
    if lo:
        keep &= day >= int(np.datetime64(lo, "D").astype(np.int64))
    if hi:
        keep &= day <= int(np.datetime64(hi, "D").astype(np.int64))
    u = pd.read_parquet(f"{ROOT}/data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
    qm = np.array([np.datetime64(x[:7], "M").astype(np.int64) for x in u[(u.coin == coin) & u.U_Q1.astype(bool)].month],
                  np.int64)
    mon = day.astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
    ud = np.unique(day)
    okd = np.isin(ud, np.fromiter(days_ok, np.int64))
    live_day = okd[np.searchsorted(ud, day)]
    el = keep & (tr > 0) & live_day & np.isin(mon, qm)
    dd, cnt = np.unique(day[el], return_counts=True)
    return dd.astype(np.int64), cnt.astype(np.int64)


def main():
    u = pd.read_parquet(f"{ROOT}/data/stinkbid/ref/universes.parquet", columns=["coin", "U_Q1"])
    coins = sorted(u[u.U_Q1.astype(bool)].coin.unique())
    res = {}
    for c in coins:
        dd, cnt = coin_days(c)
        res[c + "__days"] = dd
        res[c + "__cnt"] = cnt
        gc.collect()
    np.savez(f"{OUT}/pool_tables.npz", **res)
    print(len(coins), "coins; maxrss MB", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024))


if __name__ == "__main__":
    main()
