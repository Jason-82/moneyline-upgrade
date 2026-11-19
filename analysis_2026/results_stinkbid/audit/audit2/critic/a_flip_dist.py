"""Critic check A: what does 'a flip made +4.8% on average' hide?

Per-fill distribution of the X-FLIP net return r_f (P1, U-Q1, rule M, C-RH on F1; RH on F3_1), split by exit kind,
tail concentration, halves and years, with month-block cluster-bootstrap intervals for the median and the share of
winning flips; then the flip a user following BOTH recommendations would run (alert at the level, buy by hand at
M(fill), same R1/2 target and 72 h stop): r_alert = (1 + r_f) / (1 + a_f) - 1, compared with the same fill's twins.
Own code: reads only the cached engine tables (needed columns) and the H1/H2R sample files of record (git eee2ddf).
"""
import io
import json
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy import stats

REPO = "/home/user/moneyline-upgrade"
RUN = f"{REPO}/data/stinkbid/runs/outcomes/P1__U_Q1"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit2/critic"
rng = np.random.default_rng(424242)


def git_csv(path, commit="eee2ddf"):
    s = subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], capture_output=True, text=True, check=True).stdout
    return pd.read_csv(io.StringIO(s))


def cr1(y, g):
    """Mean, CR1 SE with G/(G-1), G, G* and the t-test p (two-sided and one-sided > 0) with G*-1 df."""
    y = np.asarray(y, float)
    g = np.asarray(g)
    k = np.isfinite(y)
    y, g = y[k], g[k]
    n = len(y)
    m = y.mean()
    u = pd.Series(y - m).groupby(g).sum().to_numpy()
    ng = pd.Series(np.ones(n)).groupby(g).sum().to_numpy()
    G = len(u)
    se = np.sqrt(G / (G - 1) * (u ** 2).sum()) / n
    gs = (ng ** 2).sum() ** 2 / (ng ** 4).sum()
    t = m / se
    df = gs - 1
    return dict(n=n, mean=m, se=se, G=G, gstar=gs, t=t, p1=float(stats.t.sf(t, df)),
                lo=m - stats.t.ppf(0.975, df) * se, hi=m + stats.t.ppf(0.975, df) * se)


def clus_boot(y, g, fn, B=4999):
    """Pairs month-block bootstrap (whole blocks resampled) percentile 95% interval of fn(y) (descriptive only)."""
    y = np.asarray(y, float)
    g = np.asarray(g)
    codes, uniq = pd.factorize(g)
    groups = [y[codes == j] for j in range(len(uniq))]
    G = len(groups)
    draws = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, G, G)
        draws[b] = fn(np.concatenate([groups[j] for j in pick]))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def describe(r, name):
    r = np.asarray(r, float)
    q = np.quantile(r, [0.10, 0.25, 0.5, 0.75, 0.90])
    srt = np.sort(r)[::-1]
    tot = r.sum()
    n = len(r)
    out = dict(name=name, n=n, mean=r.mean(), median=q[2], p10=q[0], p25=q[1], p75=q[3], p90=q[4],
               share_pos=float((r > 0).mean()), share_le_m10=float((r <= -0.10).mean()),
               share_le_m20=float((r <= -0.20).mean()),
               trim5=float(stats.trim_mean(r, 0.05)), trim10=float(stats.trim_mean(r, 0.10)),
               top1pct_share_of_sum=float(srt[: max(1, int(round(0.01 * n)))].sum() / tot),
               top5pct_share_of_sum=float(srt[: int(round(0.05 * n))].sum() / tot),
               mean_wo_top1pct=float(srt[max(1, int(round(0.01 * n))):].mean()),
               mean_wo_top5pct=float(srt[int(round(0.05 * n)):].mean()))
    return out


def main():
    cols = ["rule", "exit", "lat", "cost", "fill_id", "coin", "r", "exit_kind", "exit_t", "exit_px", "target",
            "complete", "twin_mean", "delta", "hold_h"]
    o = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=cols)
    o = o[(o.exit == "FLIP") & (o.lat == "M") & (((o.rule == "F1") & (o.cost == "C-RH")) | (o.rule == "F3_1"))]
    f = pd.read_parquet(f"{RUN}/fills.parquet", columns=["fill_id", "coin", "rung", "L", "P0", "t_F1", "t_F3_1",
                                                        "month_block", "episode", "half"])
    b = pd.read_parquet(f"{RUN}/bench.parquet", columns=["fill_id", "rule", "alert_M", "alert_t_M", "alert_px_M"])
    res = {}

    # samples of record (H1, H2R) to anchor the sample definition
    s1 = git_csv("analysis_2026/results_stinkbid/primary/samples_H1.csv")
    s2 = git_csv("analysis_2026/results_stinkbid/primary/samples_H2R.csv")
    res["samples_cols"] = dict(H1=list(s1.columns), H2R=list(s2.columns))

    for rule in ["F1", "F3_1"]:
        d = o[(o.rule == rule) & o.complete].merge(f, on=["fill_id"], suffixes=("", "_f"))
        tcol = "t_F1" if rule == "F1" else "t_F3_1"
        d["year"] = pd.to_datetime(d[tcol], unit="m", utc=True).dt.year
        R = dict(n=len(d))
        R["r"] = describe(d.r, f"r_f {rule}")
        R["delta"] = describe(d.delta, f"delta {rule}")
        R["twin_mean"] = dict(mean=float(d.twin_mean.mean()), median=float(d.twin_mean.median()))
        R["r_cr1"] = cr1(d.r, d.month_block)
        R["median_r_ci_blockboot"] = clus_boot(d.r.to_numpy(), d.month_block.to_numpy(), np.median)
        R["share_pos_ci_blockboot"] = clus_boot(d.r.to_numpy(), d.month_block.to_numpy(), lambda x: (x > 0).mean())
        R["median_delta_ci_blockboot"] = clus_boot(d.delta.to_numpy(), d.month_block.to_numpy(), np.median)
        # by exit kind
        ek = d.groupby("exit_kind").agg(n=("r", "size"), mean_r=("r", "mean"), median_r=("r", "median"),
                                         share_pos=("r", lambda x: float((x > 0).mean())),
                                         sum_r=("r", "sum"), mean_hold_h=("hold_h", "mean"))
        ek["share_of_fills"] = ek.n / ek.n.sum()
        ek["share_of_sum_r"] = ek.sum_r / d.r.sum()
        R["by_exit_kind"] = ek.reset_index().to_dict("records")
        # stops: how far below entry
        st = d[d.exit_kind == "stop"].r
        R["stop_quantiles"] = dict(zip(["p10", "p25", "p50", "p75", "p90"],
                                       np.quantile(st, [0.1, 0.25, 0.5, 0.75, 0.9]).tolist()))
        # halves and years
        hv = []
        for h, g in d.groupby("half"):
            c = cr1(g.r, g.month_block)
            hv.append(dict(half=h, n=len(g), mean_r=g.r.mean(), median_r=g.r.median(),
                           share_pos=float((g.r > 0).mean()), mean_delta=g.delta.mean(), median_delta=g.delta.median(),
                           r_lo=c["lo"], r_hi=c["hi"], r_G=c["G"], r_gstar=c["gstar"],
                           target_share=float((g.exit_kind == "target").mean())))
        R["by_half"] = hv
        R["by_year"] = d.groupby("year").agg(n=("r", "size"), mean_r=("r", "mean"), median_r=("r", "median"),
                                             share_pos=("r", lambda x: float((x > 0).mean())),
                                             mean_delta=("delta", "mean")).reset_index().to_dict("records")
        R["by_rung"] = d.groupby("rung").agg(n=("r", "size"), mean_r=("r", "mean"), median_r=("r", "median"),
                                             share_pos=("r", lambda x: float((x > 0).mean())),
                                             mean_delta=("delta", "mean")).reset_index().to_dict("records")
        # per-episode sums: how many episodes carry the total r
        ep = d.groupby("episode").r.sum().sort_values(ascending=False)
        R["episodes"] = dict(n_episodes=int(len(ep)), top3_share_of_sum_r=float(ep.iloc[:3].sum() / d.r.sum()),
                             top10_share_of_sum_r=float(ep.iloc[:10].sum() / d.r.sum()),
                             share_episodes_with_neg_sum=float((ep < 0).mean()),
                             top3=ep.iloc[:3].index.tolist())

        # alert-entered flip: same go-live, target and stop; entry at the alert buyer's price
        bb = b[b.rule == rule][["fill_id", "alert_M", "alert_t_M", "alert_px_M"]]
        a = d.merge(bb, on="fill_id", how="left")
        ok = np.isfinite(a.alert_M) & (a.alert_t_M >= 0)
        trade = ok & (a.alert_t_M < a.exit_t)       # price already above the target at go-live: no alert trade
        a["r_alert"] = np.where(trade, (1 + a.r) / (1 + a.alert_M) - 1, np.nan)
        a["d_alert"] = a.r_alert - a.twin_mean
        A = dict(n_fills=int(len(a)), n_alert_defined=int(ok.sum()), n_alert_trades=int(trade.sum()),
                 n_no_trade_target_passed=int((ok & ~trade).sum()))
        at = a[trade]
        A["r_alert"] = describe(at.r_alert, f"alert-entered flip r {rule}")
        A["d_alert_cr1"] = cr1(at.d_alert, at.month_block)
        A["r_alert_cr1"] = cr1(at.r_alert, at.month_block)
        A["resting_same_fills"] = dict(mean_r=float(at.r.mean()), mean_delta=float(at.delta.mean()),
                                       mean_a_f=float(at.alert_M.mean()))
        A["d_alert_by_half"] = [dict(half=h, **{k: v for k, v in cr1(g.d_alert, g.month_block).items()
                                                if k in ("n", "mean", "lo", "hi", "G", "gstar", "p1")})
                                for h, g in at.groupby("half")]
        # the alert flip's twins: twins are buy-at-random with a target; under optional stopping their gross mean
        # does not depend on the target, so the fill's own twin mean is used (approximation stated)
        R["alert_flip"] = A
        res[rule] = R
        if rule == "F1":
            # anchor: the H1 sample of record
            m = d[["fill_id", "delta"]].merge(s1, left_on="fill_id", right_on=s1.columns[0], how="inner")
            res["anchor_H1_rows_matched"] = int(len(m))
            ycol = "y" if "y" in s1.columns else s1.columns[1]
            res["anchor_H1_max_abs_diff"] = float(np.abs(m["delta"] - m[ycol]).max()) if len(m) else None
            d[["fill_id", "coin", "rung", "r", "delta", "twin_mean", "exit_kind", "half", "year",
               "month_block"]].to_csv(f"{OUT}/a_flip_rows_F1.csv", index=False)
            a.loc[trade, ["fill_id", "r", "alert_M", "r_alert", "d_alert", "twin_mean"]].to_csv(
                f"{OUT}/a_alert_rows_F1.csv", index=False)
    with open(f"{OUT}/a_flip_dist.json", "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(json.dumps(res, indent=1, default=lambda x: round(float(x), 6) if isinstance(x, (float, np.floating)) else str(x)))


if __name__ == "__main__":
    main()
