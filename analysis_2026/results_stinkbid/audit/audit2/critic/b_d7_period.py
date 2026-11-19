"""Critic check B (part 1): the D7 accounts of record (desc first pass, commit 7949037) by period, with my own CAGR and
my own stationary block bootstrap (Politis-Romano, geometric blocks, circular), against B-MIX and B-TBILL.

The per-fill PASS is what H1 tests; whether a user's money grows is what D7 answers, and no lens recomputed D7.
"""
import io
import json
import subprocess

import numpy as np
import pandas as pd

REPO = "/home/user/moneyline-upgrade"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit2/critic"


def git_csv(path, commit="7949037", **kw):
    s = subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], capture_output=True, text=True, check=True).stdout
    return pd.read_csv(io.StringIO(s), **kw)


def cagr(r, ppy=12):
    r = np.asarray(r, float)
    return np.prod(1 + r, axis=-1) ** (ppy / r.shape[-1]) - 1


def sb_idx(T, mean_block, B, rng):
    """Stationary bootstrap indices: start uniform, continue with prob 1 - 1/mean_block (circular)."""
    p = 1.0 / mean_block
    idx = np.empty((B, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, T, B)
    new = rng.random((B, T)) < p
    starts = rng.integers(0, T, (B, T))
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def boot_diff(x, y, mean_block, B=9999, seed=7):
    rng = np.random.default_rng(seed)
    x, y = np.asarray(x, float), np.asarray(y, float)
    idx = sb_idx(len(x), mean_block, B, rng)
    d = cagr(x[idx]) - cagr(y[idx])
    return dict(est=float(cagr(x) - cagr(y)), lo=float(np.quantile(d, 0.025)), hi=float(np.quantile(d, 0.975)),
                p_le0=float((d <= 0).mean()))


def main():
    res = {}
    comp = git_csv("analysis_2026/results_stinkbid/desc/d7_compare.csv")
    for route in ["F1", "F3_1"]:
        for rr in ["0.0", "0.0335"]:
            M = git_csv(f"analysis_2026/results_stinkbid/desc/d7_monthly_{route}_{rr}.csv", index_col=0)
            M.index = pd.PeriodIndex(M.index, freq="M")
            key = f"{route}_r{rr}"
            R = {"months": len(M), "first": str(M.index[0]), "last": str(M.index[-1])}
            # full period, own CAGR
            R["cagr_full"] = {c: float(cagr(M[c].dropna())) for c in ["D7", "B-ALERT", "B-TBILL", "B-MIX"]}
            # own bootstrap vs the record's intervals
            for ben in ["B-MIX", "B-TBILL"]:
                for blk in (6, 12):
                    R[f"boot_D7_vs_{ben}_{blk}m"] = boot_diff(M["D7"], M[ben], blk)
                rec = comp[(comp.route == route) & (np.isclose(comp.r_res, float(rr))) & (comp.account == "D7")
                           & (comp.benchmark == ben)]
                if len(rec):
                    rec = rec.iloc[0]
                    R[f"record_D7_vs_{ben}"] = dict(est=float(rec.cagr_diff), lo6=float(rec.lo_6m), hi6=float(rec.hi_6m),
                                                     lo12=float(rec.lo_12m), hi12=float(rec.hi_12m))
            R["boot_BALERT_vs_BTBILL_12m"] = boot_diff(M["B-ALERT"], M["B-TBILL"], 12)
            # by period
            per = {}
            for name, sl in [("2020-01..2022-12", slice("2020-01", "2022-12")),
                             ("2023-01..2026-11", slice("2023-01", "2026-11"))]:
                S = M.loc[sl]
                per[name] = dict(months=len(S), **{c: float(cagr(S[c])) for c in ["D7", "B-ALERT", "B-TBILL", "B-MIX"]})
                per[name]["D7_minus_TBILL"] = per[name]["D7"] - per[name]["B-TBILL"]
                per[name]["D7_minus_MIX"] = per[name]["D7"] - per[name]["B-MIX"]
                per[name]["ALERT_minus_TBILL"] = per[name]["B-ALERT"] - per[name]["B-TBILL"]
                per[name]["boot_D7_vs_MIX_12m"] = boot_diff(S["D7"], S["B-MIX"], 12)
                per[name]["boot_D7_vs_MIX_6m"] = boot_diff(S["D7"], S["B-MIX"], 6)
            R["by_period"] = per
            # by calendar year: annual returns (compounded months in the year)
            yr = {}
            for y, S in M.groupby(M.index.year):
                yr[int(y)] = dict(months=len(S), **{c: float(np.prod(1 + S[c]) - 1) for c in ["D7", "B-ALERT", "B-TBILL",
                                                                                              "B-MIX"]})
                yr[int(y)]["D7_minus_TBILL"] = yr[int(y)]["D7"] - yr[int(y)]["B-TBILL"]
            R["by_year"] = yr
            # concentration of the account's excess over T-bills: top months
            ex = (M["D7"] - M["B-TBILL"])
            R["excess_month_sum"] = float(ex.sum())
            top = ex.sort_values(ascending=False)
            R["top5_months"] = {str(k): float(v) for k, v in top.iloc[:5].items()}
            R["top3_months_share_of_excess_sum"] = float(top.iloc[:3].sum() / ex.sum())
            R["share_months_D7_below_TBILL"] = float((ex < 0).mean())
            # without the 3 best months (replace by the T-bill month: the account earning cash that month)
            M2 = M.copy()
            for k in top.index[:3]:
                M2.loc[k, "D7"] = M2.loc[k, "B-TBILL"]
            R["cagr_D7_without_top3_months"] = float(cagr(M2["D7"]))
            res[key] = R
    with open(f"{OUT}/b_d7_period.json", "w") as fh:
        json.dump(res, fh, indent=1)
    for k, R in res.items():
        print("=" * 20, k, R["months"], R["first"], R["last"])
        print(" cagr_full", {a: round(v, 4) for a, v in R["cagr_full"].items()})
        for kk in R:
            if kk.startswith("boot_") or kk.startswith("record_"):
                print(" ", kk, {a: round(v, 4) for a, v in R[kk].items()})
        for p, v in R["by_period"].items():
            print("  period", p, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items() if not isinstance(b, dict)})
            print("     boot12", {a: round(b, 4) for a, b in v["boot_D7_vs_MIX_12m"].items()},
                  "boot6", {a: round(b, 4) for a, b in v["boot_D7_vs_MIX_6m"].items()})
        for y, v in R["by_year"].items():
            print("  year", y, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})
        print("  top5 months", {a: round(b, 4) for a, b in R["top5_months"].items()},
              "top3 share", round(R["top3_months_share_of_excess_sum"], 3),
              "months below TBILL", round(R["share_months_D7_below_TBILL"], 3),
              "CAGR w/o top3 months", round(R["cagr_D7_without_top3_months"], 4))


if __name__ == "__main__":
    main()
