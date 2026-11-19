"""Rows beside H1/H2R (F3_1, F3d_1, F3_3, U_B, U_C, U_C_F3), concentration and single events, and the F3 mean r."""
import json
import os
import sys
import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest"
sys.path.insert(0, D)
import mystats as M

RUNS = "data/stinkbid/runs/outcomes"
P = json.load(open("analysis_2026/results_stinkbid/primary/primary.json"))


def mins_ts(m):
    return pd.to_datetime(np.asarray(m, np.int64) * 60_000_000_000, utc=True)


def flip(run, rule, cost, exit="FLIP"):
    F = pd.read_parquet(f"{RUNS}/{run}/fills.parquet", columns=["fill_id", "L", "t_" + rule])
    O = pd.read_parquet(f"{RUNS}/{run}/outcomes.parquet", columns=["fill_id", "r", "delta", "complete", "exit_px", "exit_kind", "target"],
                        filters=[("rule", "==", rule), ("exit", "==", exit), ("cost", "==", cost)])
    d = F[F["t_" + rule] >= 0].merge(O[O.complete], on="fill_id")
    d = d[np.isfinite(d.delta)].copy()
    d["time"] = mins_ts(d["t_" + rule])
    return d.sort_values(["time", "fill_id"]).reset_index(drop=True)


def bench(run, rule):
    F = pd.read_parquet(f"{RUNS}/{run}/fills.parquet", columns=["fill_id", "L", "t_" + rule])
    B = pd.read_parquet(f"{RUNS}/{run}/bench.parquet", columns=["fill_id", "alert_M"], filters=[("rule", "==", rule)])
    d = F[F["t_" + rule] >= 0].merge(B, on="fill_id")
    d = d[np.isfinite(d.alert_M)].copy()
    d["time"] = mins_ts(d["t_" + rule])
    return d.sort_values(["time", "fill_id"]).reset_index(drop=True)


def row(y, t):
    mb, ep = M.my_month_blocks(t)
    r = M.test_mean(np.asarray(y, float), mb, B=1999)
    return r


print(f"{'row':<14}{'n':>6}{'G':>4}{'G*':>7}{'mean':>10}{'t-CI lo':>9}{'t-CI hi':>9}   file (n, est, lo, hi)")
for test, key, run, rule, kind, cost in (
        ("H1", "F3_1", "P1__U_Q1", "F3_1", "flip", "RH"), ("H1", "F3d_1", "P1__U_Q1", "F3d_1", "flip", "RH"),
        ("H1", "F3_3", "P1__U_Q1", "F3_3", "flip", "RH"), ("H1", "U_B", "P1__U_B", "F1", "flip", "C-RH"),
        ("H1", "U_C", "P1__U_C", "F1", "flip", "C-RH"), ("H1", "U_C_F3", "P1__U_C", "F3_1", "flip", "RH"),
        ("H2R", "F3_1", "P1__U_Q1", "F3_1", "bench", None), ("H2R", "F3d_1", "P1__U_Q1", "F3d_1", "bench", None),
        ("H2R", "F3_3", "P1__U_Q1", "F3_3", "bench", None), ("H2R", "U_B", "P1__U_B", "F1", "bench", None),
        ("H2R", "U_C", "P1__U_C", "F1", "bench", None), ("H2R", "U_C_F3", "P1__U_C", "F3_1", "bench", None)):
    d = flip(run, rule, cost) if kind == "flip" else bench(run, rule)
    y = d.delta if kind == "flip" else d.alert_M
    r = row(y, d.time)
    f = P["beside"][test][key]
    print(f"{test + ' ' + key:<14}{r['n']:>6}{r['G']:>4}{r['gstar']:>7.2f}{r['est']:>+10.5f}{r['ci95_t'][0]:>+9.4f}{r['ci95_t'][1]:>+9.4f}"
          f"   ({f['n']}, {f['estimate']:+.5f}, {f['ci_lo']:+.4f}, {f['ci_hi']:+.4f})  G {f['G']} G* {f['gstar']:.2f}")
    if test == "H1" and key in ("F3_1", "U_C_F3"):
        rr = d.r
        chk = d.exit_px / d.L - 1
        print(f"     {key}: mean r on the route = {rr.mean():+.5f} (n {len(rr)}); r == exit_px/L - 1 max diff {np.abs(chk - rr).max():.2e}; "
              f"exit kinds {d.exit_kind.value_counts().to_dict()}")

# concentration and single events on H1 / H2R samples
for test in ("H1", "H2R"):
    s = pd.read_csv(f"analysis_2026/results_stinkbid/primary/samples_{test}.csv")
    y, ep, mb = s.y.to_numpy(float), s.ep.to_numpy(), s.mb.to_numpy()
    u, c = np.unique(ep, return_counts=True)
    top = u[np.lexsort((u, -c))][:3]
    sel = np.isin(ep, top)
    t = pd.to_datetime(s.time, utc=True)
    names = [f"{t[ep == e].min().date()}..{t[ep == e].max().date()}" for e in top]
    day = t.dt.strftime("%Y-%m-%d")
    ub, cb = np.unique(mb, return_counts=True)
    tb = ub[np.lexsort((ub, -cb))][0]
    rb = P["robust"][test]
    print(f"\n{test}: top3 {names} share {y[sel].sum() / y.sum():+.4f} (file {rb['top3_share']:+.4f}); without them {y[~sel].mean():+.5f} "
          f"(file {rb['top3_without']:+.5f}); without 2025-10-10 {y[day != '2025-10-10'].mean():+.5f} (file {rb['without_2025-10-10']:+.5f}); "
          f"without 2021-05-19 {y[day != '2021-05-19'].mean():+.5f} (file {rb['without_2021-05-19']:+.5f}); without top block {tb} "
          f"{y[mb != tb].mean():+.5f} (file {rb['without_top_block']:+.5f}, block {rb['top_block']})")
    # worst single episode (alternative reading of 'biggest episode')
    worst = min((y[ep != e].mean(), e) for e in u)
    print(f"   min over episodes of the mean without that episode: {worst[0]:+.5f} (episode {worst[1]}, "
          f"{t[ep == worst[1]].min().date()}..{t[ep == worst[1]].max().date()}, {int((ep == worst[1]).sum())} fills)")
    # by-year means
    yr = t.dt.year.to_numpy()
    print("   by fill year:", {int(a): (round(float(y[yr == a].mean()), 4), int((yr == a).sum())) for a in np.unique(yr)})
    # worst block identity
    blk_months = sorted(set(t[mb == 9].dt.strftime('%Y-%m')))
    print(f"   block 9 months: {blk_months}; top block {tb} months: {sorted(set(t[mb == tb].dt.strftime('%Y-%m')))}")
