"""
Per-asset validation gate (AGENTIC_TRADING_PLAN.md section 5), as code.

Every asset is tested per VEHICLE, with that vehicle's cost and execution timing:
  crypto_direct  Robinhood crypto, ~0.95%/side; primary = same-bar close,
                 alternate = next bar
  spot_etf       crypto signal traded through a spot ETF, 0.02%/side; primary =
                 next NYSE session, alternate = the session after (weekend/holiday
                 signals wait); see costs.etf_want
  stock_daily    stocks/ETFs, 0.03%/side (1bp+2bp); primary = next session (the plan
                 executes after the close), alternate = same-bar close

Tests (pinned definitions):
  T1 history     >= 7 years and >= 40 closed trades (underlying's own history)
  T2 edge        after costs AND taxes, at the primary timing:
                 CAGR >= buy & hold, or CAGR >= B&H - 2 pts with max DD >= 15 pts shallower
  T3 PF          profit factor (sum of winning trade % / |sum of losing %|) >= 2.0
  T4 one run     remove the single best closed trade's dates from BOTH series (cash in
                 both over that window); the pre-tax T2 rule must still pass
  T5 timing      T2 (after tax) also passes at the alternate timing
  T6 eras        non-overlapping 3-calendar-year blocks from the first full year:
                 annualised ln(signal wealth / B&H wealth) >= -0.15 in every block,
                 median block > 0, and the pre-tax T2 rule passes since 2022-01-01
  T7 whipsaw     <= 30% of closed trades end within +/-2%

Verdict: TRADE (all pass) | PROBATION (fails only T1) | NO-SIGNAL (hold or skip).
Weekly INSURANCE for indices: weekly signal with dividends + cash yield gives up
<= 3 CAGR pts/yr and saves >= 15 pts of max drawdown, at both same-week and
next-week fills.

Taxes (illustrative defaults - replace with the user's federal+state rates):
signal: realised gains taxed every calendar year at the short-term rate (losses
carried forward; wash-sale deferral ignored, which only shifts timing); the open
position is liquidated and taxed at the end. Buy & hold: taxed once at the
long-term rate on the final gain.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.run_full import load as load_crypto  # noqa: E402
from analysis_2026.costs import etf_want  # noqa: E402
import analysis_2026.run_stocks as RS  # noqa: E402

ST_RATE, LT_RATE = 0.35, 0.20
VEHICLES = {
    "crypto_direct": dict(cost=0.0095, primary="same", alternate="next"),
    "spot_etf": dict(cost=0.0002, primary="s1", alternate="s2"),
    "stock_daily": dict(cost=0.0003, primary="next", alternate="same"),
}


def timing_want(index, green, how):
    g = np.asarray(green, dtype=bool)
    if how == "same":
        return g
    if how == "next":
        return np.r_[False, g[:-1]]
    return etf_want(index, g, int(how[1]))


def simulate(close, want, cost, st=None):
    """Long while want. Returns equity (pre-tax), trades, and after-tax final multiple."""
    c = close.to_numpy(float); w = np.asarray(want, dtype=bool); idx = close.index
    cash, sh, entry_i, entry_val = 1.0, 0.0, None, None
    eq = np.empty(len(c)); trades = []
    tcash, tsh, tbasis, carry, year_gain = 1.0, 0.0, 0.0, 0.0, 0.0   # after-tax book
    for i in range(len(c)):
        if w[i] and sh == 0.0:
            sh = cash * (1 - cost) / c[i]; entry_val = cash; cash = 0.0; entry_i = i
            tsh = tcash * (1 - cost) / c[i]; tbasis = tcash; tcash = 0.0
        elif not w[i] and sh > 0.0:
            cash = sh * c[i] * (1 - cost); sh = 0.0
            trades.append((entry_i, i, (cash / entry_val - 1) * 100))
            tcash = tsh * c[i] * (1 - cost); year_gain += tcash - tbasis; tsh = 0.0
        if st is not None and (i == len(c) - 1 or idx[i].year != idx[i + 1].year):
            net = year_gain + carry
            if net > 0:
                tax = st * net
                if tcash >= tax:
                    tcash -= tax
                else:                       # pay from the position
                    tsh -= (tax - tcash) / c[i]; tcash = 0.0
                carry = 0.0
            else:
                carry = net
            year_gain = 0.0
        eq[i] = cash + sh * c[i]
    after = tcash + tsh * c[-1] * (1 - cost)
    if st is not None and tsh > 0:
        gain = tsh * c[-1] * (1 - cost) - tbasis + carry
        if gain > 0:
            after -= st * gain
    return pd.Series(eq, index=idx), trades, after


def cagr(mult, idx):
    yrs = (idx[-1] - idx[0]).days / 365.25
    return (mult ** (1 / yrs) - 1) * 100 if mult > 0 else -100.0


def maxdd(eq):
    return float(((eq / eq.cummax()) - 1).min() * 100)


def bh(close, cost, lt=None):
    mult = close.iloc[-1] / close.iloc[0] * (1 - cost) ** 2
    if lt is not None and mult > 1:
        mult -= lt * (mult - 1)
    return mult, maxdd(close / close.iloc[0])


def t2_rule(sig_cagr, sig_dd, bh_cagr, bh_dd):
    return sig_cagr >= bh_cagr or (sig_cagr >= bh_cagr - 2 and sig_dd >= bh_dd + 15)


def evaluate(close, green, vehicle):
    v = VEHICLES[vehicle]; cost = v["cost"]; idx = close.index
    res = {}
    wp = timing_want(idx, green, v["primary"])
    eq, trades, after = simulate(close, wp, cost, ST_RATE)
    rets = np.array([t[2] for t in trades])
    bh_pre, bh_dd = bh(close, cost); bh_tax, _ = bh(close, cost, LT_RATE)
    sig_pre_c = cagr(eq.iloc[-1], idx); sig_tax_c = cagr(after, idx)
    bh_pre_c = cagr(bh_pre, idx); bh_tax_c = cagr(bh_tax, idx); dd = maxdd(eq)
    yrs = (idx[-1] - idx[0]).days / 365.25
    res.update(years=yrs, trades=len(trades), sig_cagr_pre=sig_pre_c, bh_cagr_pre=bh_pre_c,
               sig_cagr_tax=sig_tax_c, bh_cagr_tax=bh_tax_c, sig_dd=dd, bh_dd=bh_dd,
               edge_pre=sig_pre_c - bh_pre_c, edge_tax=sig_tax_c - bh_tax_c)
    res["T1"] = yrs >= 7 and len(trades) >= 40
    res["T2"] = t2_rule(sig_tax_c, dd, bh_tax_c, bh_dd)
    win, los = rets[rets > 0].sum(), abs(rets[rets <= 0].sum())
    res["PF"] = win / los if los > 0 else np.inf
    res["T3"] = res["PF"] >= 2.0
    # T4: remove best trade window from both series
    if len(trades):
        a, b, _ = max(trades, key=lambda t: t[2])
        mask = np.ones(len(close), dtype=bool); mask[a:b + 1] = False
        r_sig = eq.pct_change().fillna(0).to_numpy(copy=True); r_bh = close.pct_change().fillna(0).to_numpy(copy=True)
        r_sig[~mask] = 0; r_bh[~mask] = 0
        e4 = np.cumprod(1 + r_sig); b4 = np.cumprod(1 + r_bh)
        c4s, c4b = cagr(e4[-1], idx), cagr(b4[-1] * (1 - cost) ** 2, idx)
        d4s = maxdd(pd.Series(e4)); d4b = maxdd(pd.Series(b4))
        res["edge_ex_best"] = c4s - c4b
        res["T4"] = t2_rule(c4s, d4s, c4b, d4b)
    else:
        res["edge_ex_best"] = np.nan; res["T4"] = False
    # T5: alternate timing, after tax
    wa = timing_want(idx, green, v["alternate"])
    eqa, _, aftera = simulate(close, wa, cost, ST_RATE)
    res["edge_tax_alt"] = cagr(aftera, idx) - bh_tax_c
    res["T5"] = t2_rule(cagr(aftera, idx), maxdd(eqa), bh_tax_c, bh_dd)
    # T6: era blocks on log wealth (pre-tax, primary timing)
    first_full = idx[0].year + (0 if (idx[0].month == 1 and idx[0].day <= 7) else 1)
    blocks = []
    y = first_full
    while pd.Timestamp(f"{y + 3}-01-01") <= idx[-1]:
        m = (idx >= f"{y}-01-01") & (idx < f"{y + 3}-01-01")
        s_ = eq[m]; bb = close[m]
        blocks.append((y, (np.log(s_.iloc[-1] / s_.iloc[0]) - np.log(bb.iloc[-1] / bb.iloc[0])) / 3))
        y += 3
    since = idx >= "2022-01-01"
    cs, cb = close[since], close[since]
    es, _, _ = simulate(cs, timing_want(cs.index, np.asarray(green)[since], v["primary"]), cost)
    pb, pdd = bh(cb, cost)
    ok22 = t2_rule(cagr(es.iloc[-1], cs.index), maxdd(es), cagr(pb, cb.index), pdd)
    vals = [b_[1] for b_ in blocks]
    res["eras"] = ", ".join(f"{b_[0]}-{b_[0] + 2}:{b_[1]:+.2f}" for b_ in blocks)
    res["T6"] = bool(vals) and min(vals) >= -0.15 and float(np.median(vals)) > 0 and ok22
    res["whipsaw_%"] = float((np.abs(rets) < 2).mean() * 100) if len(rets) else np.nan
    res["T7"] = res["whipsaw_%"] <= 30
    fails = [t for t in ("T1", "T2", "T3", "T4", "T5", "T6", "T7") if not res[t]]
    res["fails"] = ",".join(fails) or "-"
    res["verdict"] = "TRADE" if not fails else ("PROBATION" if fails == ["T1"] else "NO-SIGNAL")
    return res


def insurance(sym):
    """Weekly signal as crash insurance (indices), with dividends + cash yield."""
    d = RS.load(sym, "1W"); g = d.green.to_numpy(bool)
    out = {}
    for lbl, w in (("same", g), ("next", np.r_[False, g[:-1]])):
        m = RS.bt(d.close, w, 52, div=RS.DIV_YIELD[sym], cash=RS.CASH_YIELD[sym])
        b = RS.bh(d.close, div=RS.DIV_YIELD[sym])
        out[f"giveup_{lbl}"] = b["cagr_pct"] - m["cagr_pct"]
        out[f"dd_saved_{lbl}"] = m["max_dd_pct"] - b["max_dd_pct"]
    out["INSURANCE"] = all(out[f"giveup_{x}"] <= 3 and out[f"dd_saved_{x}"] >= 15 for x in ("same", "next"))
    return out


def run():
    rows = []
    for sym in ("BTC", "ETH", "SOL", "BNB", "ZEC"):
        d = load_crypto(sym, "1D")
        for veh in ("crypto_direct", "spot_etf"):
            rows.append({"asset": sym, "vehicle": veh, **evaluate(d.close, d.green.to_numpy(bool), veh)})
    for sym in RS.TICKERS:
        d = RS.load(sym, "1D")
        rows.append({"asset": sym, "vehicle": "stock_daily", **evaluate(d.close, d.green.to_numpy(bool), "stock_daily")})
    gate = pd.DataFrame(rows)
    ins = pd.DataFrame([{"asset": s, **insurance(s)} for s in ("SPX", "NDX", "IWM")])
    return gate, ins


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    gate, ins = run()
    out = Path(__file__).resolve().parent
    gate.to_csv(out / "results_gate.csv", index=False)
    ins.to_csv(out / "results_insurance.csv", index=False)
    f = lambda x: f"{x:,.1f}"  # noqa: E731
    print(f"Tax rates used: short-term {ST_RATE:.0%}, long-term {LT_RATE:.0%} (illustrative)\n")
    print(gate[["asset", "vehicle", "years", "trades", "edge_pre", "edge_tax", "sig_dd", "bh_dd", "PF",
                "edge_ex_best", "edge_tax_alt", "whipsaw_%", "fails", "verdict"]].to_string(index=False, float_format=f))
    print("\nEra blocks (annualised log wealth vs B&H):")
    for _, r in gate.iterrows():
        print(f"  {r.asset:5s} {r.vehicle:13s} {r.eras}")
    print("\nWeekly INSURANCE (indices, dividends + cash yield):")
    print(ins.to_string(index=False, float_format=f))
