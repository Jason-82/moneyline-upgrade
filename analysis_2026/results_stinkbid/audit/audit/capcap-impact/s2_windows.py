"""Step 2: independent reconstruction of the draft §8.3 capacity windows of every P1/U-Q1 F1 fill from the raw 1m
spot bars, C1 per window from the bars, and the aggTrades capacity per window from the reduced aggTrades cache
(data/stinkbid/agg_cap; the raw zips are not kept). Own code, written from the draft's text:
  window: from the first trade below L (the fill minute; later: a live minute with low < L while the order rests)
  until the first later live minute whose low is above L, or 60 minutes; inside the order's life.
Then: the fill's own window (first) against the order's life sum, capacity up to the flip's exit, and the time
profile of the life sum. One coin at a time; only the columns needed."""
import glob
import os
import sys

import numpy as np
import pandas as pd

OUTD = ("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
        "capcap-impact")
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1"
cols = ["coin", "rung", "t_F1", "L", "L_tau", "bid_id", "fill_id", "live_from", "life_end", "n_windows",
        "c1_first", "c1_life", "agg_first", "agg_life", "agg_m0", "cap_src"]
F = pd.read_parquet(f"{RUN}/fills.parquet", columns=cols)
F = F[F.t_F1 >= 0].reset_index(drop=True)
O = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "exit_t",
                                                         "exit_kind"],
                    filters=[("rule", "==", "F1"), ("exit", "==", "FLIP"), ("lat", "==", "M"), ("cost", "==", "C-RH")])
F = F.merge(O[["fill_id", "exit_t", "exit_kind"]], on="fill_id", how="left")
print("F1 fills", len(F), "with flip exit", int(F.exit_t.notna().sum()))

US_PER_MIN = 60_000_000
rows = []
win_rows = []
for coin, G in F.groupby("coin", sort=True):
    # 1m bars of this coin, only the range of its lives
    t_lo = pd.Timestamp(int(G.t_F1.min()) * 60, unit="s", tz="UTC")
    t_hi = pd.Timestamp(int(G.life_end.max()) * 60 + 60, unit="s", tz="UTC")
    k = pd.read_parquet(f"data/stinkbid/m1_spot/{coin}USDT.parquet",
                        columns=["open_time", "high", "low", "quote_volume", "taker_buy_quote", "trades"],
                        filters=[("open_time", ">=", t_lo), ("open_time", "<", t_hi)])
    t = (k.open_time.astype("int64").to_numpy() // 60_000_000_000).astype(np.int64)
    hi = k.high.to_numpy(float)
    lo = k.low.to_numpy(float)
    qv = k.quote_volume.to_numpy(float)
    sq = qv - k.taker_buy_quote.to_numpy(float)
    live = k.trades.to_numpy() > 0
    del k
    # reduced aggTrades cache of this coin: per (L, minute) seller-initiated USD below L
    parts = []
    for fp in sorted(glob.glob(f"data/stinkbid/agg_cap/{coin}/*.parquet")):
        a = pd.read_parquet(fp, columns=["key", "minute", "sell_below_usd"])
        if len(a):
            parts.append(a)
    A = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["key", "minute", "sell_below_usd"])
    A["Lk"] = A.key.str.split("|").str[1].astype(float)
    A = A.drop_duplicates(["Lk", "minute"])
    AG = {L: g.sort_values("minute") for L, g in A.groupby("Lk")}
    del A, parts
    for r in G.itertuples():
        L, Lt = float(r.L), float(r.L_tau)
        i0 = int(np.searchsorted(t, r.t_F1))
        assert i0 < len(t) and t[i0] == r.t_F1, (coin, r.t_F1)
        iend = int(np.searchsorted(t, r.life_end))           # bars with t < life_end
        tt, ll, hh, lv, s_ = t[i0:iend], lo[i0:iend], hi[i0:iend], live[i0:iend], sq[i0:iend]
        rng = hh - ll
        with np.errstate(divide="ignore", invalid="ignore"):
            frac = np.where(rng > 0, np.clip((L - ll) / rng, 0, 1), (ll < L).astype(float))
        c1m = np.where(lv & (qv[i0:iend] > 0), s_ * frac, 0.0)
        trig = np.flatnonzero(lv & (ll < L))                 # a trade below L
        above = np.flatnonzero(lv & (ll > L))
        ag = AG.get(L)
        am = ag.minute.to_numpy(np.int64) if ag is not None else np.zeros(0, np.int64)
        au = ag.sell_below_usd.to_numpy(float) if ag is not None else np.zeros(0)
        acum = np.r_[0.0, np.cumsum(au)]
        wins = []
        i = 0                                                # the fill minute is the first trigger
        while i is not None and i < len(tt):
            # first later live minute with low > L
            j = np.searchsorted(above, i + 1)
            e_above = above[j] if j < len(above) else len(tt)
            e_time = int(np.searchsorted(tt, tt[i] + 60))
            e = min(e_above, e_time)
            ta, tb = int(tt[i]), int(tt[e - 1]) + 1
            c1 = float(c1m[i:e].sum())
            x0, x1 = np.searchsorted(am, ta * US_PER_MIN), np.searchsorted(am, tb * US_PER_MIN)
            agg = float(acum[x1] - acum[x0])
            wins.append((ta, tb, c1, agg))
            j = np.searchsorted(trig, e)
            i = int(trig[j]) if j < len(trig) else None
        W = np.array(wins, dtype=float)
        ex = r.exit_t
        # capacity of windows (minute by minute) up to the flip's exit: minutes < exit_t
        if pd.notna(ex):
            x1 = np.searchsorted(am, int(ex) * US_PER_MIN)
            x0 = np.searchsorted(am, int(r.t_F1) * US_PER_MIN)
            # only minutes inside this bid's windows count
            inwin = np.zeros(len(am), bool)
            for ta, tb, _, _ in wins:
                inwin[np.searchsorted(am, ta * US_PER_MIN):np.searchsorted(am, tb * US_PER_MIN)] = True
            m_ok = inwin & (am < int(ex) * US_PER_MIN)
            agg_to_exit = float(au[m_ok].sum())
            m_ok2 = inwin & (am <= int(ex) * US_PER_MIN)
            agg_to_exit_incl = float(au[m_ok2].sum())
        else:
            agg_to_exit = agg_to_exit_incl = np.nan
        rows.append(dict(coin=coin, rung=r.rung, fill_id=r.fill_id, bid_id=r.bid_id, t_F1=r.t_F1,
                         life_end=r.life_end, exit_t=ex, exit_kind=r.exit_kind,
                         my_nw=len(wins), my_c1_first=W[0, 2], my_c1_life=W[:, 2].sum(), my_agg_first=W[0, 3],
                         my_agg_life=W[:, 3].sum(), first_len=int(W[0, 1] - W[0, 0]),
                         first_end_by_time=bool(W[0, 1] - W[0, 0] >= 60),
                         eng_nw=r.n_windows, eng_c1_first=r.c1_first, eng_c1_life=r.c1_life,
                         eng_agg_first=r.agg_first, eng_agg_life=r.agg_life, agg_to_exit=agg_to_exit,
                         agg_to_exit_incl=agg_to_exit_incl,
                         agg_1h=float(W[W[:, 0] < r.t_F1 + 60, 3].sum()),
                         agg_6h=float(W[W[:, 0] < r.t_F1 + 360, 3].sum()),
                         agg_24h=float(W[W[:, 0] < r.t_F1 + 1440, 3].sum()),
                         agg_72h=float(W[W[:, 0] < r.t_F1 + 4320, 3].sum())))
        for w in wins:
            win_rows.append(dict(fill_id=r.fill_id, rung=r.rung, ta=w[0], tb=w[1], c1=w[2], agg=w[3]))
    del t, hi, lo, qv, sq, live, AG
    print(coin, len(G), flush=True, end="; ")
R = pd.DataFrame(rows)
R.to_parquet(f"{OUTD}/s2_fills.parquet")
pd.DataFrame(win_rows).to_parquet(f"{OUTD}/s2_windows.parquet")
print()


def close(a, b, rel=1e-6, abs_=0.01):
    return np.isclose(a, b, rtol=rel, atol=abs_)


print("n_windows equal:", int((R.my_nw == R.eng_nw).sum()), "of", len(R))
for c in ("c1_first", "c1_life", "agg_first", "agg_life"):
    ok = close(R["my_" + c].to_numpy(), R["eng_" + c].to_numpy())
    print(f"{c}: equal {int(ok.sum())} of {len(R)}; max abs diff {np.nanmax(np.abs(R['my_' + c] - R['eng_' + c])):,.4f}")
print("first window length (min): median", R.first_len.median(), "p10", R.first_len.quantile(.1), "p90",
      R.first_len.quantile(.9), "share ended by the 60-minute cap", round(R.first_end_by_time.mean(), 3))
