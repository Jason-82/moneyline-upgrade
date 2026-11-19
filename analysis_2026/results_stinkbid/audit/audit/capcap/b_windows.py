"""Part B: recompute the draft §8.3 capacity windows of every P1/U-Q1 F1 fill from the raw 1m spot bars (own code),
C1 per window from the draft's formula, and the aggTrades dollars per window from the per-minute aggTrades cache
(data/stinkbid/agg_cap/<coin>/<day>.parquet: one row per (window key, minute) of seller-initiated dollars below L).

Window (draft §8.3, prereg §7): from the fill minute (the first trade below L) until the first later live minute whose
low is above L, or 60 minutes, whichever comes first. Remainder windows: each later live minute with a trade below L
while the order rests (until life_end) opens a new window. 'first' = the fill's own window; 'life' = all windows.
One coin at a time; only the columns needed.
"""
import glob
import os
import sys
import numpy as np
import pandas as pd

OUTD = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/capcap"
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1/fills.parquet"
cols = ["coin", "rung", "t_F1", "life_end", "L", "L_tau", "tick", "bid_id", "fill_id", "n_windows", "c1_first",
        "c1_life", "agg_first", "agg_life", "agg_m0"]
F = pd.read_parquet(RUN, columns=cols)
F = F[F.t_F1 >= 0].reset_index(drop=True)
WIN = 60


def windows(t, lo, hi, live, L, m0, end):
    """List of (start_idx, stop_idx) windows: bar indices into t (minutes, sorted). m0 = fill minute."""
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
        # next trigger: first later live minute with a trade below L, before the life end
        m = k
        nxt = None
        while m < n and t[m] < end:
            if live[m] and lo[m] < L * (1 - 1e-12):
                nxt = m
                break
            m += 1
        i = nxt
    return out


def c1(sl, L, lo, hi, live, sq):
    l_, h_, lv, s_ = lo[sl], hi[sl], live[sl], sq[sl]
    rng = h_ - l_
    with np.errstate(divide="ignore", invalid="ignore"):
        f = np.where(rng > 0, np.clip((L - l_) / rng, 0, 1), (l_ < L).astype(float))
    return float(np.sum(np.where(lv, s_ * f, 0.0)))


rows = []
coins = sorted(F.coin.unique())
for ci, coin in enumerate(coins):
    g = F[F.coin == coin]
    path = f"data/stinkbid/m1_spot/{coin}USDT.parquet"
    if not os.path.exists(path):
        print("no m1 file for", coin, len(g), "fills")
        continue
    lo_t = pd.Timestamp(int(g.t_F1.min()) * 60, unit="s", tz="UTC")
    hi_t = pd.Timestamp(int(g.life_end.max()) * 60, unit="s", tz="UTC")
    k = pd.read_parquet(path, columns=["open_time", "high", "low", "quote_volume", "trades", "taker_buy_quote"],
                        filters=[("open_time", ">=", lo_t), ("open_time", "<", hi_t)])
    k = k.sort_values("open_time")
    t = (k.open_time.astype("int64").to_numpy() // 60_000_000_000).astype(np.int64)
    lo = k.low.to_numpy(float)
    hi = k.high.to_numpy(float)
    live = k.trades.to_numpy() > 0
    sq = np.maximum(k.quote_volume.to_numpy(float) - k.taker_buy_quote.to_numpy(float), 0.0)
    del k
    # aggTrades per-minute cache for the coin: L -> {minute: usd}
    agg = {}
    files = sorted(glob.glob(f"data/stinkbid/agg_cap/{coin}/*.parquet"))
    if files:
        A = pd.concat([pd.read_parquet(x, columns=["key", "minute", "sell_below_usd"]) for x in files],
                      ignore_index=True)
        A["L"] = A.key.str.split("|").str[1].astype(float)
        A["m"] = (A.minute.to_numpy(np.int64) // 60_000_000).astype(np.int64)
        # the same (L, minute) can be cached under several window keys (other programs): values must agree
        dup = A.groupby(["L", "m"]).sell_below_usd.agg(["min", "max"])
        bad = dup[(dup["max"] - dup["min"]).abs() > 1e-6 * dup["max"].abs().clip(lower=1)]
        if len(bad):
            print(coin, "inconsistent duplicate (L, minute) rows:", len(bad))
        A = A.drop_duplicates(["L", "m"])
        for Lv, gg in A.groupby("L"):
            agg[Lv] = pd.Series(gg.sell_below_usd.to_numpy(float), index=gg.m.to_numpy(np.int64))
        del A
    for r in g.itertuples():
        W = windows(t, lo, hi, live, r.L, int(r.t_F1), int(r.life_end))
        if W is None:
            rows.append(dict(fill_id=r.fill_id, ok=False))
            continue
        c1s = [c1(slice(a, b), r.L, lo, hi, live, sq) for a, b in W]
        s = agg.get(r.L)
        aggs = []
        for a, b in W:
            mins = t[a:b]
            aggs.append(float(s.reindex(mins).fillna(0.0).sum()) if s is not None else np.nan)
        a0, b0 = W[0]
        m0_usd = float(s.get(int(r.t_F1), 0.0)) if s is not None else np.nan
        rows.append(dict(fill_id=r.fill_id, bid_id=r.bid_id, coin=coin, rung=r.rung, ok=True, my_nw=len(W),
                         my_c1_first=c1s[0], my_c1_life=float(np.sum(c1s)), my_agg_first=aggs[0],
                         my_agg_life=float(np.nansum(aggs)), my_agg_m0=m0_usd,
                         first_len_min=int(t[b0 - 1] - t[a0] + 1), first_end=int(t[b0 - 1]) + 1,
                         life_minutes=int(sum(t[b - 1] - t[a] + 1 for a, b in W)),
                         last_win_end=int(t[W[-1][1] - 1]) + 1))
    del t, lo, hi, live, sq, agg
    if ci % 10 == 0:
        print(f"{ci + 1}/{len(coins)} {coin}", flush=True)

R = pd.DataFrame(rows)
R.to_parquet(f"{OUTD}/b_windows.parquet")
M = F.merge(R, on="fill_id", how="left", suffixes=("", "_my"))
print("fills:", len(F), " recomputed:", int(M.ok.fillna(False).sum()))
M = M[M.ok.fillna(False).astype(bool)]


def cmp(a, b, name, rtol=1e-6):
    x, y = M[a].to_numpy(float), M[b].to_numpy(float)
    good = np.isclose(x, y, rtol=rtol, atol=1e-6)
    print(f"{name:>22}: equal {good.sum()} / {len(good)}; median |rel diff| "
          f"{np.nanmedian(np.abs(x - y) / np.maximum(np.abs(y), 1e-9)):.2e}")
    return good


cmp("my_nw", "n_windows", "windows")
cmp("my_c1_first", "c1_first", "c1_first")
cmp("my_c1_life", "c1_life", "c1_life")
cmp("my_agg_first", "agg_first", "agg_first")
cmp("my_agg_life", "agg_life", "agg_life")
cmp("my_agg_m0", "agg_m0", "agg_m0")
print("first window length (minutes): median", M.first_len_min.median(), " p90", M.first_len_min.quantile(.9),
      " share = 60:", round(float((M.first_len_min == 60).mean()), 3))
print("minutes inside all windows: median", M.life_minutes.median(), " p90", M.life_minutes.quantile(.9))
print("last window end - fill minute (hours): median", ((M.last_win_end - M.t_F1) / 60).median().round(1),
      " p90", ((M.last_win_end - M.t_F1) / 60).quantile(.9).round(1))
for k in (6.0, 8.0, 10.0):
    m = M.rung == k
    print(f"k={k:g}: my first-window p10 ${np.quantile(M.my_agg_first[m], .1):,.0f} -> cap ${.25 * np.quantile(M.my_agg_first[m], .1):,.0f};"
          f" my life p10 ${np.quantile(M.my_agg_life[m], .1):,.0f} -> cap ${.25 * np.quantile(M.my_agg_life[m], .1):,.0f}")
