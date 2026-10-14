"""Execute fixed C3-C5 theory candidates and all declared fair controls.

Private full daily ledgers are retained locally; public outputs contain metrics,
monthly paths, schedules, source hashes and every failure/sensitivity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026.moneyline_ref import moneyline
from analysis_2026.theory_lab.engine import (BacktestResult, annual_gain_tax_sensitivity,
                                           portfolio_statistics, run_portfolio)
from analysis_2026.theory_lab.schedules import (GLOBAL, crypto_leadership, flip_schedule,
                                               global_momentum, hold_schedule, matched_dates,
                                               monthly_equal, quarterly_balanced)

ROOT = Path(__file__).resolve().parents[1]


def read_prices(folder, names, crypto=False):
    out = {}
    for name in names:
        p = folder / f"{name}{'USDT' if crypto else ''}.csv"
        d = pd.read_csv(p)
        d.columns = d.columns.str.lower()
        d["date"] = pd.to_datetime(d["date"])
        d = d.set_index("date").sort_index()
        if d.index.has_duplicates or not np.isfinite(d[["open", "close"]]).all().all():
            raise ValueError(f"Invalid price inputs: {name}")
        out[name] = d
    return out


def close_panel(data):
    return pd.DataFrame({s:d.close for s,d in data.items()}).dropna()


def combine_moneyline(data, start, end, fee, lag, cash):
    """Two independent half-capital sleeves; no daily portfolio top-ups."""
    slots = []
    for name, d in data.items():
        green = moneyline(d).green.rename(name)
        schedule = flip_schedule(green, start, lag)
        slots.append(run_portfolio({name:d}, schedule, start=start, end=end,
                     initial_capital=50_000, fee_rate=fee, execution_lag=lag,
                     cash_rate=cash, market="crypto"))
    p = slots[0].path.copy()
    for col in ("equity", "cash", "turnover_notional", "fees", "equity_before_liquidation"):
        if col in p:
            p[col] = sum(s.path[col] for s in slots)
    if "exposure" in p:
        p["exposure"] = sum(s.path.exposure * s.path.equity for s in slots) / p.equity
    p["exposure_before_liquidation"] = sum(s.path.exposure_before_liquidation * s.path.equity_before_liquidation for s in slots) / p.equity_before_liquidation
    p.attrs["initial_capital"] = 100_000.0
    tx = pd.concat([s.transactions.assign(slot=n) for n,s in zip(data,slots)], ignore_index=True)
    events = pd.concat([s.events.assign(slot=n) for n,s in zip(data,slots)], ignore_index=True)
    return BacktestResult(p, tx, events, portfolio_statistics(p, initial_capital=100_000, market="crypto"))


def conditional_block_test(active, block=12, draws=2000, seed=20261014):
    """Null-centered one-sided mean-log-active-return block test and interval.

    This is a retrospective, stationary approximation, not a forecast or untouched
    validation. Dates remain paired; returns across strategies are not iid rows.
    """
    a = np.asarray(active.dropna(), float)
    if len(a) < block * 2:
        return {"status":"insufficient_months", "months":len(a), "p_one_sided":np.nan}
    rng = np.random.default_rng(seed)
    starts = rng.integers(0,len(a)-block+1,size=(draws,int(np.ceil(len(a)/block))))
    samples = a[starts[...,None] + np.arange(block)].reshape(draws,-1)[:,:len(a)]
    means = samples.mean(axis=1)
    null = means - a.mean()
    p = (1 + np.count_nonzero(null >= a.mean())) / (draws+1)
    return {"status":"identified", "months":len(a), "block_months":block, "draws":draws,
            "annual_active_log_pct":a.mean()*1200,
            "conditional_ci_low_pct":np.quantile(means,.025)*1200,
            "conditional_ci_high_pct":np.quantile(means,.975)*1200, "p_one_sided":p}


def holm(pvalues, family_size=5):
    valid = sorted([(i,float(p)) for i,p in enumerate(pvalues) if np.isfinite(p)], key=lambda x:x[1])
    out = [np.nan]*len(pvalues)
    running = 0.0
    for rank,(i,p) in enumerate(valid):
        running = max(running, min(1.0,p*(family_size-rank)))
        out[i] = running
    return out


def freeze_inputs(args):
    inputs = []
    for folder,names,crypto in ((args.etf_folder,set(GLOBAL)|{"SSO"},False),
                                 (args.crypto_folder,{"BTC","ETH"},True)):
        for s in sorted(names):
            p = folder/f"{s}{'USDT' if crypto else ''}.csv"
            inputs.append({"source":"crypto" if crypto else "etf", "name":p.name,
                           "sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    implementation = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in [Path(__file__), ROOT/"theory_lab/engine.py", ROOT/"theory_lab/schedules.py",
                                ROOT/"moneyline_ref.py", ROOT/"THEORY_LAB_PREREG.md"]}
    return {"inputs":inputs,"implementation":implementation,"pandas":pd.__version__,
            "numpy":np.__version__,"prereg_local_commit":"f496b9d",
            "scope":"Simulated research only, no account data or orders; retrospective history"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--etf-folder", type=Path, required=True)
    ap.add_argument("--crypto-folder", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=ROOT/"results_theory_lab")
    ap.add_argument("--private-output", type=Path, default=ROOT.parent/"private/theory_lab")
    args = ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for child in ("paths","transactions","events","schedules"):
        (args.private_output/child).mkdir(parents=True,exist_ok=True)
    (args.output/"schedules").mkdir(exist_ok=True)
    frozen = freeze_inputs(args)
    (args.output/"frozen_inputs.json").write_text(json.dumps(frozen,indent=2)+"\n")
    etf = read_prices(args.etf_folder, set(GLOBAL)|{"SSO"})
    crypto = read_prices(args.crypto_folder,["BTC","ETH"],True)
    families = {}
    global_data = {s:etf[s] for s in GLOBAL}
    global_close = close_panel(global_data).loc[:,GLOBAL]
    schedules = {"C3_global":global_momentum(global_close),
                 "global_top2":global_momentum(global_close,2),
                 "global_top4":global_momentum(global_close,4),
                 "global_equal":monthly_equal(global_close)}
    families["C3"] = (global_data,schedules,"SPY",.0002,"etf")
    balanced_data = {s:etf[s] for s in ("SSO","GLD","SPY")}
    balanced_close = close_panel(balanced_data)
    schedules = {}
    for label,weight,symbol in (("C4_sso_gold",.5,"SSO"),("sso_gold40",.4,"SSO"),
                                ("sso_gold60",.6,"SSO"),("spy_gold50",.5,"SPY")):
        w = quarterly_balanced(balanced_close,weight,symbol).reindex(columns=balanced_data,fill_value=0)
        schedules[label] = w
    families["C4"] = (balanced_data,schedules,"SPY",.0002,"etf")
    cc = close_panel(crypto)
    schedules = {"C5_crypto":crypto_leadership(cc),"crypto_rank42":crypto_leadership(cc,42),
                 "crypto_rank84":crypto_leadership(cc,84),"crypto_equal":monthly_equal(cc)}
    families["C5"] = (crypto,schedules,"BTC",.0015,"crypto")
    metrics, monthly, annual, exposures = [], [], [], []
    serial = 0
    for family,(data,schedules,benchmark,base_fee,market) in families.items():
        cal = close_panel(data).index
        if market == "etf":
            limits = [("full","2007-01-01","2025-12-31"),("development","2007-01-01","2014-12-31"),
                      ("later","2015-01-01","2025-12-31"),("2026","2026-01-01","2026-10-13")]
            stress = .001
        else:
            limits = [("full","2019-01-01","2025-12-31"),("development","2019-01-01","2022-12-31"),
                      ("later","2023-01-01","2025-12-31"),("2026","2026-01-01","2026-09-30")]
            stress = .0095
        for label,w in schedules.items():
            w.to_csv(args.output/"schedules"/f"{label}.csv",index_label="signal_date")
        for window,a,b in limits:
            start,end = matched_dates(cal,a,b)
            for fee,lag,cash in [(f,l,0.) for f in (base_fee,stress) for l in (1,2)] + [(base_fee,1,.04)]:
                policies = dict(schedules)
                if not (fee==base_fee and lag==1 and cash==0):
                    policies = {k:v for k,v in policies.items() if k not in ("global_top2","global_top4","sso_gold40","sso_gold60","crypto_rank42","crypto_rank84")}
                w = [1. if s==benchmark else 0. for s in data]
                policies["hold_benchmark"] = hold_schedule(cal,list(data),w,start,lag)
                if family == "C4":
                    policies["hold_sso"] = hold_schedule(cal,list(data),[1. if s=="SSO" else 0 for s in data],start,lag)
                if family == "C5":
                    policies["moneyline_slots"] = None
                for policy,schedule in policies.items():
                    serial += 1
                    key = f"run_{serial:04d}"
                    record = {"run_id":key,"family":family,"policy":policy,"window":window,
                              "start":str(start.date()),"end":str(end.date()),"fee":fee,"lag":lag,
                              "cash_rate":cash,"market":market,"initial_capital":100_000}
                    try:
                        if policy == "moneyline_slots":
                            result = combine_moneyline(data,start,end,fee,lag,cash)
                        else:
                            result = run_portfolio(data,schedule,start=start,end=end,fee_rate=fee,
                                                   execution_lag=lag,cash_rate=cash,market=market)
                            schedule.to_csv(args.private_output/"schedules"/f"{key}.csv",index_label="signal_date")
                        path = result.path
                        path.to_csv(args.private_output/"paths"/f"{key}.csv",index_label="date")
                        result.transactions.to_csv(args.private_output/"transactions"/f"{key}.csv",index=False)
                        result.events.to_csv(args.private_output/"events"/f"{key}.csv",index=False)
                        tx = annual_gain_tax_sensitivity(path,initial_capital=100_000)
                        result.stats["annual_tax_stress_cagr"] = tx.stats["cagr"]
                        result.stats["terminal_20_gain_stress_cagr"] = \
                            ((100_000 + (path.equity.iloc[-1]-100_000) - .2*max(path.equity.iloc[-1]-100_000,0))/100_000)**(1/result.stats["calendar_years"])-1
                        metrics.append({**record,"status":"identified",**result.stats})
                        me = path.equity.groupby(path.index.to_period("M")).last()
                        previous = np.r_[100_000,me.to_numpy()[:-1]]
                        monthly.extend({**record,"month":str(m),"ending_equity":float(v),
                                        "log_return":float(np.log(v/p))} for m,v,p in zip(me.index,me,previous))
                        ye = path.equity.groupby(path.index.year).last()
                        previous = np.r_[100_000,ye.to_numpy()[:-1]]
                        annual.extend({**record,"year":int(y),"return":float(v/p-1)} for y,v,p in zip(ye.index,ye,previous))
                        if fee==base_fee and lag==1 and cash==0 and window in ("full","later"):
                            pc = path.equity.pct_change().fillna(path.equity.iloc[0]/100_000-1)
                            spy = etf["SPY"].close.reindex(path.index).pct_change(fill_method=None)
                            if market=="etf":
                                paired = pd.concat([pc.rename("portfolio"),spy.rename("spy")],axis=1).dropna()
                                beta = paired.portfolio.cov(paired.spy)/paired.spy.var()
                                exposures.append({**record,"realized_spy_beta":beta,
                                                  "underlying_notional_at_target":1.5 if policy=="C4_sso_gold" else np.nan})
                    except (ValueError,RuntimeError) as e:
                        metrics.append({**record,"status":"unidentified","reason":str(e)})
            print(f"Completed {family} {window}",flush=True)
    frame = pd.DataFrame(metrics)
    frame.to_csv(args.output/"metrics.csv",index=False)
    pd.DataFrame(monthly).to_csv(args.output/"monthly_paths.csv",index=False)
    pd.DataFrame(annual).to_csv(args.output/"calendar_years.csv",index=False)
    pd.DataFrame(exposures).to_csv(args.output/"exposures.csv",index=False)
    tests = []
    mp = pd.DataFrame(monthly)
    for family,policy in (("C3","C3_global"),("C4","C4_sso_gold"),("C5","C5_crypto")):
        x = mp[(mp.family==family)&(mp.window=="full")&(mp.policy.isin([policy,"hold_benchmark"]))
               &(mp.fee==(.0015 if family=="C5" else .0002))&(mp.lag==1)&(mp.cash_rate==0)]
        pairs = x.pivot(index="month",columns="policy",values="log_return")
        tests.append({"family":family,"policy":policy,**conditional_block_test(pairs[policy]-pairs.hold_benchmark)})
    pd.DataFrame(tests).to_csv(args.output/"primary_tests_unadjusted.csv",index=False)
    after = freeze_inputs(args)
    if after != frozen:
        raise RuntimeError("Inputs or implementation changed during run; retain but invalidate these outputs")
    outputs = {str(p.relative_to(args.output)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in args.output.rglob("*.csv")}
    (args.output/"receipt.json").write_text(json.dumps({**frozen,"outputs":outputs,
                  "run_count":len(frame),"failures":int(frame.status.eq("unidentified").sum()),
                  "daily_ledger_location":"private/theory_lab; reconstruct from recorded inputs"},indent=2)+"\n")
    print(json.dumps({"runs":len(frame),"failures":int(frame.status.eq("unidentified").sum())}))


if __name__ == "__main__":
    main()
