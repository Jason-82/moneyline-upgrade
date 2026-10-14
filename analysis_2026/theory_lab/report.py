"""Apply the declared five-candidate decisions; do not optimize strategies."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026.theory_lab.run import holm


def build(output):
    m = pd.read_csv(output/"metrics.csv")
    t = pd.read_csv(output/"primary_tests_unadjusted.csv").set_index("family")
    sm = pd.read_csv(output/"stock_metrics.csv")
    rows = []
    for family,policy in (("C1","residual_momentum"),("C2","continuous_information")):
        s = sm[sm.strategy.eq(policy)&sm.period.str.startswith("full")&sm.missing_policy.eq("strict")
               &sm.delay_sessions.eq(1)&np.isclose(sm.cost_per_side_bps,3)
               &sm.annual_gain_levy_rate.eq(0)&sm.terminal_gain_levy_rate.eq(0)&sm.cash_yield.eq(0)]
        if len(s)!=1 or s.iloc[0].status!="unidentified":
            raise ValueError("Stock summary requires independent strict-primary review")
        r = s.iloc[0]
        rows.append({"family":family,"policy":policy,"status":"UNIDENTIFIED",
                     "reason":f"{r.reason} at {r.first_unknown_date}: {r.unknown_tickers}",
                     "p_one_sided":np.nan,"qualification":"UNIDENTIFIED"})
    for family,policy,fair in (("C3","C3_global","global_equal"),
                                ("C4","C4_sso_gold","spy_gold50"),
                                ("C5","C5_crypto","crypto_equal")):
        fee = .0015 if family=="C5" else .0002
        group = m[m.family.eq(family)&m.status.eq("identified")]
        base = group[group.window.eq("full")&np.isclose(group.fee,fee)&group.lag.eq(1)&group.cash_rate.eq(0)].set_index("policy")
        a,b,control = base.loc[policy],base.loc["hold_benchmark"],base.loc[fair]
        later = group[group.window.eq("later")&np.isclose(group.fee,fee)&group.lag.eq(1)&group.cash_rate.eq(0)].set_index("policy")
        active = group[group.policy.eq(policy)&group.window.eq("full")&group.cash_rate.eq(0)]
        robust = []
        for r in active.itertuples():
            bb = group[group.policy.eq("hold_benchmark")&group.window.eq("full")
                       &np.isclose(group.fee,r.fee)&group.lag.eq(r.lag)&group.cash_rate.eq(r.cash_rate)].iloc[0]
            robust.append(r.cagr > bb.cagr and r.max_drawdown>=bb.max_drawdown)
        rows.append({"family":family,"policy":policy,"status":"IDENTIFIED",
                     "cagr_pct":a.cagr*100,"benchmark_cagr_pct":b.cagr*100,
                     "fair_control_cagr_pct":control.cagr*100,"edge_pct_points":(a.cagr-b.cagr)*100,
                     "drawdown_pct":a.max_drawdown*100,"benchmark_drawdown_pct":b.max_drawdown*100,
                     "growth_hurdle":a.cagr-b.cagr>=.01,
                     "drawdown_hurdle":a.max_drawdown>=b.max_drawdown,
                     "later_growth_hurdle":later.loc[policy].cagr>later.loc["hold_benchmark"].cagr,
                     "fair_control_growth_hurdle":a.cagr>control.cagr,
                     "cost_delay_growth_and_drawdown_hurdle":all(robust),
                     "p_one_sided":t.loc[family].p_one_sided,
                     "conditional_ci_low_pct":t.loc[family].conditional_ci_low_pct,
                     "conditional_ci_high_pct":t.loc[family].conditional_ci_high_pct,
                     "annual_35_stress_cagr_pct":a.annual_tax_stress_cagr*100,
                     "passive_terminal_20_stress_cagr_pct":b.terminal_20_gain_stress_cagr*100,
                     "passive_same_annual_35_stress_cagr_pct":b.annual_tax_stress_cagr*100,
                     "tax_stress_beats_generous_passive":a.annual_tax_stress_cagr>b.terminal_20_gain_stress_cagr})
    adjusted = holm([r["p_one_sided"] for r in rows],family_size=5)
    for r,p in zip(rows,adjusted):
        r["holm_five_p"] = p
        if r["status"]=="IDENTIFIED":
            r["statistical_hurdle"] = p<.05
            keys = ("growth_hurdle","drawdown_hurdle","later_growth_hurdle","fair_control_growth_hurdle",
                    "cost_delay_growth_and_drawdown_hurdle","statistical_hurdle")
            r["qualification"] = "PASS_RETROSPECTIVE_ONLY" if all(r[k] for k in keys) else "FAIL_DECLARED_HURDLES"
    pd.DataFrame(rows).to_csv(output/"candidate_verdicts.csv",index=False)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"results_theory_lab")
    args = ap.parse_args()
    for r in build(args.output):
        print(r["family"],r["qualification"],r.get("edge_pct_points"),r.get("holm_five_p"))


if __name__=="__main__":
    main()
