"""Critic check B (part 3): the single-event rows §10.4 asks of every estimate ("without 2025-10-10, without
2021-05-19 and without its top month-block"), which the desc stage does not compute for D7 ("an account's path cannot
drop one day"). Built on my own D7 rebuild of the F3 (s = 1%) flip account at r_res = 0 (the account of the Robinhood
rule), which reproduced the record's end value to the cent: a dropped fill is treated as not having happened (the bid
stays reserved until its life ends, as D6 treats its single events). Compared with the record's B-MIX monthly series
and with my T-bill account; 12- and 6-month stationary block bootstrap of the CAGR difference (own code).
"""
import io
import json
import subprocess

import numpy as np
import pandas as pd

REPO = "/home/user/moneyline-upgrade"
RUN = f"{REPO}/data/stinkbid/runs/outcomes/P1__U_Q1"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit2/critic"
DAY = 1440
Q = 10_000.0
END = pd.Timestamp("2026-11-17")


def git_csv(path, commit="7949037", **kw):
    s = subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], capture_output=True, text=True, check=True).stdout
    return pd.read_csv(io.StringIO(s), **kw)


def tbill_pct(dates):
    m = pd.read_csv(f"{REPO}/data/stinkbid/macro/us_market_data.csv", usecols=["Date", "Risk Free Rate"],
                    parse_dates=["Date"]).set_index("Date")["Risk Free Rate"]
    m = m[~m.index.duplicated()].sort_index()
    x = pd.read_csv(f"{REPO}/data/stinkbid/macro/fred_DTB3.csv")
    e = pd.Series(pd.to_numeric(x["DTB3"], errors="coerce").to_numpy(), index=pd.to_datetime(x.iloc[:, 0])).dropna()
    s = pd.concat([m, e[e.index > m.index[-1]]]).sort_index()
    return s.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy(float)


def cagr(r):
    r = np.asarray(r, float)
    return np.prod(1 + r, axis=-1) ** (12 / r.shape[-1]) - 1


def sb_idx(T, mean_block, B, rng):
    p = 1.0 / mean_block
    idx = np.empty((B, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, T, B)
    new = rng.random((B, T)) < p
    starts = rng.integers(0, T, (B, T))
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def boot_diff(x, y, mean_block, B=9999, seed=11):
    rng = np.random.default_rng(seed)
    x, y = np.asarray(x, float), np.asarray(y, float)
    idx = sb_idx(len(x), mean_block, B, rng)
    d = cagr(x[idx]) - cagr(y[idx])
    return dict(est=round(float(cagr(x) - cagr(y)), 5), lo=round(float(np.quantile(d, 0.025)), 5),
                hi=round(float(np.quantile(d, 0.975)), 5))


def main():
    bids = pd.read_parquet(f"{RUN}/bids.parquet", columns=["coin", "rung", "t0", "life_end", "bid_id"])
    fills = pd.read_parquet(f"{RUN}/fills.parquet", columns=["bid_id", "fill_id", "t_F3_1", "t_F1", "month_block"])
    o = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "exit_t"])
    o = o[(o.rule == "F3_1") & (o.exit == "FLIP") & (o.cost == "RH")][["fill_id", "r", "exit_t"]]
    F = fills[fills.t_F3_1 >= 0].merge(o, on="fill_id")
    F = F[F.r.notna()].copy()
    F["day"] = pd.to_datetime(F.t_F3_1, unit="m").dt.normalize()
    F = F.set_index("bid_id")
    d0 = int(bids.t0.min() // DAY)
    end_day = int((END - pd.Timestamp("1970-01-01")).days)
    days = np.arange(d0, end_day + 1)
    nd = len(days)
    dates = pd.to_datetime(days, unit="D")
    rf_day = tbill_pct(dates) / 100.0 / 365.0
    me = pd.PeriodIndex(dates, freq="M")
    me_idx = np.r_[np.flatnonzero(me[1:] != me[:-1]), nd - 1]
    labels = me[me_idx].astype(str)
    K = 3 * Q * int(bids.groupby("t0").coin.nunique().max())
    B_sorted = bids.sort_values(["t0", "coin", "rung"])

    def di(tm):
        return int(np.clip(np.searchsorted(days, int(tm) // DAY), 0, nd - 1))

    def account(drop_bids=frozenset()):
        flows, reserved, posv = np.zeros(nd), np.zeros(nd), np.zeros(nd)
        busy, gains_by_block = {}, {}
        for b in B_sorted.itertuples():
            key = (b.coin, b.rung)
            if busy.get(key, -1) > b.t0:
                continue
            a, il = di(b.t0), di(b.life_end)
            reserved[a:il] += Q
            if b.bid_id not in F.index or b.bid_id in drop_bids:
                busy[key] = b.life_end
                continue
            f = F.loc[b.bid_id]
            tf, te = int(f.t_F3_1), int(f.exit_t)
            busy[key] = te
            i_f, i_e = di(tf), di(te)
            reserved[i_f:il] -= Q
            flows[i_f] -= Q
            flows[i_e] += Q * (1 + float(f.r))
            if i_e > i_f:
                posv[i_f:i_e] += Q
            gains_by_block[int(f.month_block)] = gains_by_block.get(int(f.month_block), 0.0) + Q * float(f.r)
        cash = np.zeros(nd)
        c = K
        for i in range(nd):
            c += (c - reserved[i]) * rf_day[i] + flows[i]
            cash[i] = c
        V = cash + posv
        Vm = V[me_idx]
        return pd.Series(Vm / np.r_[V[0], Vm[:-1]] - 1, index=labels), float(V[-1]), gains_by_block

    vt = K * np.cumprod(1 + rf_day)
    vtm = vt[me_idx]
    tb = pd.Series(vtm / np.r_[vt[0], vtm[:-1]] - 1, index=labels)
    mix = git_csv("analysis_2026/results_stinkbid/desc/d7_monthly_F3_1_0.0.csv", index_col=0)["B-MIX"]
    mix.index = mix.index.astype(str)
    mix = mix.reindex(labels)

    base, end_v, gb = account()
    top_block = max(gb, key=gb.get)
    blk_fills = F[F.month_block == top_block]
    sets = {
        "full (control)": frozenset(),
        "without 2021-05-19": frozenset(F.index[F.day == "2021-05-19"]),
        "without 2025-10-10": frozenset(F.index[F.day == "2025-10-10"]),
        f"without its top month-block (block {top_block}: {blk_fills.day.min().date()}..{blk_fills.day.max().date()})":
            frozenset(blk_fills.index),
    }
    out = {"K": K, "end_value_full": end_v, "top_block": top_block,
           "top_block_gain_share": gb[top_block] / sum(gb.values())}
    for name, s in sets.items():
        r, ev, _ = account(s)
        out[name] = dict(n_dropped=len(s), end_value=round(ev, 2), cagr=round(float(cagr(r)), 5),
                         vs_BMIX_12m=boot_diff(r, mix, 12), vs_BMIX_6m=boot_diff(r, mix, 6),
                         vs_TBILL_12m=boot_diff(r, tb, 12))
    with open(f"{OUT}/b_d7_single_events.json", "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
