"""Step 4: spot check of stacked M7 fills against raw Binance 1m spot bars: F1 fill minute of the real level and its
placebos (first live minute with trades > 0 and low <= L - tau), and the real fill's X-FLIP exit under rule M."""
import resource
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

RUN = "data/stinkbid/runs/outcomes/H4__U_Q1"
NY = ZoneInfo("America/New_York")
B = pd.read_parquet(f"{RUN}/bids.parquet", columns=["bid_id", "coin", "variant", "cw", "real", "shift", "L", "L_tau", "tick",
                                                    "P0", "live_from", "life_end", "t0"])
F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["bid_id", "fill_id", "t_F1"])
O = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["rule", "cost", "fill_id", "exit_t", "exit_px", "target", "exit_kind",
                                                        "complete"])
o = O[(O.rule == "F1") & (O.cost == "C-RH") & O.complete]
b7 = B[B.variant == "M7"].merge(F, on="bid_id", how="left")
# coin-weeks with a real F1 fill and at least two placebo fills
g = b7[b7.t_F1.fillna(-1) >= 0].groupby("cw").agg(nr=("real", "sum"), n=("real", "size"), coin=("coin", "first"))
kinds = b7[b7.real].merge(o[["fill_id","exit_kind"]], on="fill_id")
cand = g[(g.nr == 1) & (g.n >= 2) & g.index.isin(kinds[kinds.exit_kind.isin(["target","marketable"])].cw)]
rng = np.random.default_rng(5)
pick = cand.groupby("coin").head(1).sample(8, random_state=11).index.tolist()


def rule_m(t):
    ts = pd.Timestamp(int(t) * 60, unit="s", tz="UTC").tz_convert(NY)
    if 7 <= ts.hour <= 22:
        return int(t) + 60
    day = ts.date() if ts.hour < 7 else (ts + pd.Timedelta(days=1)).date()
    nxt = pd.Timestamp(year=day.year, month=day.month, day=day.day, hour=7).tz_localize(NY)
    return int(nxt.tz_convert("UTC").value // 60_000_000_000)


ok_fill = ok_exit = n_fill = n_exit = 0
for cw in pick:
    rows = b7[b7.cw == cw]
    coin = rows.coin.iloc[0]
    t0 = int(rows.t0.iloc[0])
    lo_t = pd.Timestamp(t0 * 60, unit="s", tz="UTC")
    k = pd.read_parquet(f"data/stinkbid/m1_spot/{coin}USDT.parquet",
                        filters=[("open_time", ">=", lo_t), ("open_time", "<", lo_t + pd.Timedelta(days=12))])
    tm = (k.open_time.astype("int64") // 60_000_000_000).to_numpy()
    for r in rows.itertuples():
        live = (tm >= r.live_from) & (tm < r.life_end) & (k.trades.to_numpy() > 0)
        hit = np.where(live & (k.low.to_numpy() <= r.L_tau))[0]
        mine = int(tm[hit[0]]) if len(hit) else -1
        rec = int(r.t_F1) if np.isfinite(r.t_F1) else -1
        n_fill += 1
        ok_fill += mine == rec
        if mine != rec:
            print(f"  FILL MISMATCH {coin} cw {cw} shift {r.shift}: mine {mine} record {rec}")
        if r.real and rec >= 0:
            oo = o[o.fill_id == r.fill_id]
            if not len(oo):
                continue
            tgt = float(oo.target.iloc[0])
            tau = float(r.tick)
            live_t = rule_m(rec)
            stop_t = rule_m(rec + 72 * 60)
            ix = np.searchsorted(tm, live_t)
            tr = k.trades.to_numpy() > 0
            while ix < len(tm) and not tr[ix]:
                ix += 1
            if k.open.to_numpy()[ix] >= tgt:
                ex = (int(tm[ix]), float(k.open.to_numpy()[ix]), "marketable")
            else:
                hh = np.where((tm >= tm[ix]) & (tm < stop_t) & tr & (k.high.to_numpy() >= tgt + tau * (1 - 1e-9)))[0]
                if len(hh):
                    ex = (int(tm[hh[0]]), tgt, "target")
                else:
                    js = np.where((tm >= stop_t) & tr)[0][0]
                    ex = (int(tm[js]), float(k.open.to_numpy()[js]), "stop")
            n_exit += 1
            same = ex[0] == int(oo.exit_t.iloc[0]) and abs(ex[1] - float(oo.exit_px.iloc[0])) <= 1e-9 * ex[1] and ex[2] == oo.exit_kind.iloc[0]
            ok_exit += same
            print(f"  {coin} {lo_t:%Y-%m-%d} real fill {pd.Timestamp(rec*60, unit='s')} exit mine {ex} record "
                  f"({int(oo.exit_t.iloc[0])}, {float(oo.exit_px.iloc[0])}, {oo.exit_kind.iloc[0]}) {'OK' if same else 'DIFF'}")
print(f"fill minutes matched {ok_fill}/{n_fill}; real-fill exits matched {ok_exit}/{n_exit}")
print("peak RSS MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
