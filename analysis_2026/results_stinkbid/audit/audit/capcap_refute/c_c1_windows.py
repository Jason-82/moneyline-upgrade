"""Independent C1 capacity windows (draft §8.3) from raw 1m spot bars for a seeded sample of P1 F1 fills.
Window: from the fill minute until the first later live minute (trades > 0) whose low is above L, or 60 minutes;
C1 per live minute = (quote_volume - taker_buy_quote) x clip((L - low) / (high - low), 0, 1) (1 if high == low < L).
Later windows: the next live minute with low <= L - tau after a window ends, while the order's life lasts.
Compares (first window, all windows to the life end) with the engine's c1_first / c1_life."""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

S = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/capcap_refute/"
f = pd.read_parquet(S + "f1_cap_exit.parquet")
B = pd.read_parquet("data/stinkbid/runs/outcomes/P1__U_Q1/bids.parquet",
                    columns=["bid_id", "L_tau", "life_end", "live_from", "coin"])
f = f.drop(columns=[c for c in ("L_tau",) if c in f]).merge(B[["bid_id", "L_tau"]], on="bid_id", how="left")
rng = np.random.default_rng(7)
pick = f.iloc[np.sort(rng.choice(len(f), size=80, replace=False))]
rows = []
for coin, g in pick.groupby("coin"):
    path = f"data/stinkbid/m1_spot/{coin}USDT.parquet"
    try:
        pf = pq.ParquetFile(path)
    except Exception as e:
        print("no file", coin, e)
        continue
    t_lo = pd.Timestamp(int(g.t_F1.min()) * 60, unit="s", tz="UTC")
    t_hi = pd.Timestamp(int(g.life_end.max()) * 60, unit="s", tz="UTC")
    X = pq.read_table(path, columns=["open_time", "high", "low", "quote_volume", "trades", "taker_buy_quote"],
                      filters=[("open_time", ">=", t_lo), ("open_time", "<", t_hi)]).to_pandas()
    tm = (X.open_time.astype("int64") // 60_000_000_000).to_numpy(np.int64)
    hi, lo = X.high.to_numpy(float), X.low.to_numpy(float)
    live = X.trades.to_numpy() > 0
    sell = (X.quote_volume.to_numpy(float) - X.taker_buy_quote.to_numpy(float))
    for r in g.itertuples():
        L, Lt = float(r.L), float(r.L_tau)
        end = int(r.life_end)
        i = int(np.searchsorted(tm, int(r.t_F1)))
        if i >= len(tm) or tm[i] != int(r.t_F1):
            print("fill minute not found", coin, r.t_F1)
            continue
        wins = []
        while i >= 0 and i < len(tm) and tm[i] < end:
            t0 = tm[i]
            c = 0.0
            k = i
            while k < len(tm) and tm[k] < end and tm[k] < t0 + 60:
                if k > i and live[k] and lo[k] > L:
                    break
                if live[k] and X.quote_volume.iat[k] > 0:
                    rg = hi[k] - lo[k]
                    fr = min(max((L - lo[k]) / rg, 0.0), 1.0) if rg > 0 else (1.0 if lo[k] < L else 0.0)
                    c += sell[k] * fr
                k += 1
            wins.append((t0, tm[k - 1] + 1, c))
            nxt = -1
            m = k
            while m < len(tm) and tm[m] < end:
                if live[m] and lo[m] <= Lt:
                    nxt = m
                    break
                m += 1
            i = nxt
        rows.append(dict(coin=coin, bid_id=r.bid_id, rung=r.rung, my_first=wins[0][2] if wins else 0.0,
                         my_life=sum(w[2] for w in wins), my_nw=len(wins), my_first_len=wins[0][1] - wins[0][0],
                         c1_first=r.c1_first, c1_life=r.c1_life, n_windows=r.n_windows, agg_first=r.agg_first,
                         agg_life=r.agg_life, life_h=(end - int(r.t_F1)) / 60))
    del X
R = pd.DataFrame(rows)
R.to_csv(S + "c1_sample.csv", index=False)
rel = lambda a, b: np.abs(a - b) / np.maximum(np.abs(b), 1.0)
print("sample", len(R), "fills,", R.coin.nunique(), "coins")
print("first window: my == engine c1_first (rel < 1e-4):", int((rel(R.my_first, R.c1_first) < 1e-4).sum()), "of", len(R))
print("life: my == engine c1_life (rel < 1e-4):", int((rel(R.my_life, R.c1_life) < 1e-4).sum()), "of", len(R))
print("n windows equal:", int((R.my_nw == R.n_windows).sum()), "of", len(R))
bad = R[(rel(R.my_first, R.c1_first) >= 1e-4) | (rel(R.my_life, R.c1_life) >= 1e-4) | (R.my_nw != R.n_windows)]
if len(bad):
    print(bad.to_string(max_cols=20))
print("first-window length (min): median", R.my_first_len.median(), "max", R.my_first_len.max())
print("remaining life after the fill (h): median", round(R.life_h.median(), 1), "max", round(R.life_h.max(), 1))
