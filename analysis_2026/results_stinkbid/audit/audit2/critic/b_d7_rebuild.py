"""Critic check B (part 2): an independent rebuild of the D7 flip account on F3 (s = 1%), the account that decides
"You could run it on Robinhood" (A1.8), from the cached bids/fills/outcomes and the raw T-bill files, without the
engine's code. Rules taken from prereg §6.3, §9, §10.4 and A1.8 (one position per coin x rung, Q = $10k per rung, every
bid cash-backed, reserved cash earns r_res, free cash earns the 3-month T-bill; X-FLIP rule M exit on the index route).
Open positions are carried at cost at month ends (no price panel), which changes only month-end marks, not the CAGR.
Also: my own B-TBILL account and the Sharpe that the record prints for it.
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
    """3-month T-bill % a year: us_market_data.csv 'Risk Free Rate' through its last day, then FRED DTB3, ffilled."""
    m = pd.read_csv(f"{REPO}/data/stinkbid/macro/us_market_data.csv", usecols=["Date", "Risk Free Rate"],
                    parse_dates=["Date"]).set_index("Date")["Risk Free Rate"]
    m = m[~m.index.duplicated()].sort_index()
    x = pd.read_csv(f"{REPO}/data/stinkbid/macro/fred_DTB3.csv")
    e = pd.Series(pd.to_numeric(x["DTB3"], errors="coerce").to_numpy(), index=pd.to_datetime(x.iloc[:, 0])).dropna()
    s = pd.concat([m, e[e.index > m.index[-1]]]).sort_index()
    return s.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy(float)


def main():
    bids = pd.read_parquet(f"{RUN}/bids.parquet", columns=["coin", "rung", "t0", "life_end", "bid_id", "L"])
    fills = pd.read_parquet(f"{RUN}/fills.parquet", columns=["bid_id", "fill_id", "t_F3_1"])
    o = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "exit_t"])
    o = o[(o.rule == "F3_1") & (o.exit == "FLIP") & (o.cost == "RH")][["fill_id", "r", "exit_t"]]
    F = fills[fills.t_F3_1 >= 0].merge(o, on="fill_id")
    F = F[F.r.notna()].set_index("bid_id")
    d0 = int(bids.t0.min() // DAY)
    end_day = int((END - pd.Timestamp("1970-01-01")).days)
    days = np.arange(d0, end_day + 1)
    nd = len(days)
    dates = pd.to_datetime(days, unit="D")
    rf_day = tbill_pct(dates) / 100.0 / 365.0

    def di(tm):
        return int(np.clip(np.searchsorted(days, int(tm) // DAY), 0, nd - 1))

    K = 3 * Q * int(bids.groupby("t0").coin.nunique().max())
    out = {"K": K}
    me = pd.PeriodIndex(dates, freq="M")
    me_idx = np.r_[np.flatnonzero(me[1:] != me[:-1]), nd - 1]
    labels = me[me_idx].astype(str)
    for r_res in (0.0, 0.0335):
        flows = np.zeros(nd)
        reserved = np.zeros(nd)
        posv = np.zeros(nd)
        busy = {}
        n_pos = 0
        gains = 0.0
        for b in bids.sort_values(["t0", "coin", "rung"]).itertuples():
            key = (b.coin, b.rung)
            if busy.get(key, -1) > b.t0:
                continue
            a, il = di(b.t0), di(b.life_end)
            reserved[a:il] += Q
            if b.bid_id not in F.index:
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
                posv[i_f:i_e] += Q           # carried at cost
            n_pos += 1
            gains += Q * float(f.r)
        cash = np.zeros(nd)
        c = K
        for i in range(nd):
            c += (c - reserved[i]) * rf_day[i] + reserved[i] * r_res / 365.0 + flows[i]
            cash[i] = c
        V = cash + posv
        Vm = V[me_idx]
        rm = pd.Series(Vm / np.r_[V[0], Vm[:-1]] - 1, index=labels)
        cagr = float(np.prod(1 + rm) ** (12 / len(rm)) - 1)
        rec = git_csv(f"analysis_2026/results_stinkbid/desc/d7_monthly_F3_1_{'0.0' if r_res == 0 else '0.0335'}.csv",
                      index_col=0)
        recm = rec["D7"].reindex(rm.index)
        rec_cagr = float(np.prod(1 + rec["D7"]) ** (12 / len(rec)) - 1)
        out[f"r_res={r_res}"] = dict(positions=n_pos, sum_gains=gains, end_value=float(V[-1]), cagr=cagr,
                                     record_cagr=rec_cagr, months=len(rm),
                                     monthly_corr=float(np.corrcoef(rm, recm)[0, 1]),
                                     monthly_max_abs_diff=float(np.abs(rm - recm).max()),
                                     mean_reserved_share=float(np.mean(reserved / V)),
                                     reserved_share_2023on=float(np.mean((reserved / V)[dates >= "2023-01-01"])))
        # my T-bill account and the record's Sharpe for it
        if r_res == 0.0:
            vt = K * np.cumprod(1 + rf_day)
            vtm = vt[me_idx]
            rt = pd.Series(vtm / np.r_[vt[0], vtm[:-1]] - 1, index=labels)
            rfm = pd.Series(np.add.reduceat(rf_day, np.r_[0, me_idx[:-1] + 1]), index=labels)
            ex = rt - rfm
            out["tbill"] = dict(cagr=float(np.prod(1 + rt) ** (12 / len(rt)) - 1),
                                record_cagr=float(np.prod(1 + rec["B-TBILL"]) ** (12 / len(rec)) - 1),
                                max_abs_monthly_diff_vs_record=float(np.abs(rt - rec["B-TBILL"].reindex(rt.index)).max()),
                                sharpe_as_coded=float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)),
                                mean_monthly_excess=float(ex.mean()), sd_monthly_excess=float(ex.std(ddof=1)))
            # the carry the resting account pays: reserved dollars x T-bill, per year, 2023 on vs before
            carry = reserved * rf_day
            out["carry_per_year_share_of_K"] = {
                "2020-2022": float(carry[dates < "2023-01-01"].sum() / K / (np.sum(dates < "2023-01-01") / 365)),
                "2023-2026": float(carry[dates >= "2023-01-01"].sum() / K / (np.sum(dates >= "2023-01-01") / 365))}
            gy = {}
            for y in range(2020, 2027):
                pass
    with open(f"{OUT}/b_d7_rebuild.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
