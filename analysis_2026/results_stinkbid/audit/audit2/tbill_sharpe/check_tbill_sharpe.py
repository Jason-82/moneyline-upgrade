"""Read-only check of the D7 summary's T-bill Sharpe ratios (record commit 7949037).

Rebuilds the engine's daily T-bill series the way stinkbid_data.tbill_series / regime_switch.rf_annual_pct do
(reading the cached CSVs only, no fetch), rebuilds B-TBILL and B-TBILL-OWN with the engine's own ledger and
monthly-return conventions, and compares with the record's monthly returns and Sharpe ratios.
"""
import io
import math
import subprocess
import sys

import numpy as np
import pandas as pd

REPO = "/home/user/moneyline-upgrade"
DAY_M = 1440


def gshow(commit, path):
    return subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], capture_output=True, check=True).stdout


# ---------------------------------------------------------------- T-bill series (as in stinkbid_data at 7949037)
base = pd.read_csv(f"{REPO}/data/stinkbid/macro/us_market_data.csv", usecols=["Date", "Risk Free Rate"],
                   parse_dates=["Date"]).set_index("Date")["Risk Free Rate"]
base = base[~base.index.duplicated()].sort_index()
x = pd.read_csv(f"{REPO}/data/stinkbid/macro/fred_DTB3.csv")
ext = pd.Series(pd.to_numeric(x["DTB3"], errors="coerce").to_numpy(), index=pd.to_datetime(x.iloc[:, 0])).dropna()
ext = ext.sort_index()
ser = pd.concat([base, ext[ext.index > base.index[-1]]])
print("base last", base.index[-1].date(), "ext last", ext.index[-1].date(), "series last", ser.index[-1].date())

# days: bids.t0.min() // DAY_M .. END (2026-11-17)
t0 = pd.read_parquet(f"{REPO}/data/stinkbid/runs/outcomes/P1__U_Q1/bids.parquet", columns=["t0"]).t0
d0 = int(t0.min() // DAY_M)
end_day = int((pd.Timestamp("2026-11-18").value // 60_000_000_000 - 1) // DAY_M)
days = np.arange(d0, end_day + 1, dtype=np.int64)
nd = len(days)
idx = pd.DatetimeIndex((days * DAY_M * 60_000_000_000).astype("datetime64[ns]"))
print("days", idx[0].date(), "..", idx[-1].date(), nd)
tb = ser.reindex(idx, method="ffill").to_numpy(float, copy=True)
late = idx > ser.index[-1]
assert all(d.year == ser.index[-1].year for d in idx[late]), "late days would use the TBILL table"
tb[late] = ser.iloc[-1]                     # rf_annual_pct: a late day in the series' last year takes its last value
print("late days:", [str(d.date()) for d in idx[late]])
tb = np.nan_to_num(tb, nan=3.0) / 100.0
rf_day = tb / 365.0

month_end = idx.to_period("M")
me_idx = np.r_[np.flatnonzero(month_end[1:] != month_end[:-1]), nd - 1]
me_lab = month_end[me_idx].astype(str)
starts = np.r_[0, me_idx[:-1] + 1]
rf_m_sum = pd.Series(np.add.reduceat(rf_day, starts), index=me_lab)
rf_m_cmp = pd.Series(np.multiply.reduceat(1 + rf_day, starts) - 1, index=me_lab)


def monthly(V, flows=None):
    Vm = V[me_idx]
    fl = np.zeros(len(me_idx)) if flows is None else np.add.reduceat(flows, starts)
    prev = np.r_[V[0] if flows is None else 0.0, Vm[:-1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (Vm - prev - fl) / (prev + fl)
    return pd.Series(r, index=me_lab)


def sharpe(r, rf):
    ex = (r - rf).to_numpy(float)
    sd = ex.std(ddof=1)
    return float(ex.mean() / sd * math.sqrt(12)), float(ex.mean()), float(sd)


# ---------------------------------------------------------------- record
rec_m = pd.read_csv(io.BytesIO(gshow("7949037", "analysis_2026/results_stinkbid/desc/d7_monthly_F1_0.0.csv")),
                    index_col=0)
rec_m.index = rec_m.index.astype(str)
rec_s = pd.read_csv(io.BytesIO(gshow("7949037", "analysis_2026/results_stinkbid/desc/d7_summary.csv")))
print("record index equal to rebuilt month labels:", list(rec_m.index) == list(me_lab))

# ---------------------------------------------------------------- B-TBILL (ledger with no flows, start K)
K = float(rec_s[(rec_s.account == "D7") & (rec_s.route == "F1") & (rec_s.r_res == 0.0)].K.iloc[0])
c = K
V = np.zeros(nd)
for i in range(nd):
    c += c * rf_day[i]
    V[i] = c
rT = monthly(V)
print("\nB-TBILL: max |rebuilt - record| monthly return:", float((rT - rec_m["B-TBILL"]).abs().max()))
cagr = float(np.prod(1 + rT.to_numpy())) ** (12 / len(rT)) - 1
print(f"B-TBILL CAGR rebuilt {cagr:.10f}; record {rec_s[rec_s.account=='B-TBILL'].cagr.iloc[0]:.10f}")
rec_sh = rec_s[rec_s.account == "B-TBILL"].sharpe.unique()
s, mu, sd = sharpe(rec_m["B-TBILL"], rf_m_sum)
print(f"Sharpe (record r, rf_m = monthly SUM of daily rates): {s:.7f}  mean ex {mu:.3e} sd {sd:.3e}; record {rec_sh}")
ex = rec_m["B-TBILL"] - rf_m_sum
print("first 3 months' excess:", ex.iloc[:3].to_dict())
print(f"month 1: record r {rec_m['B-TBILL'].iloc[0]:.10f}; rf_m sum {rf_m_sum.iloc[0]:.10f}; rf_day[0] {rf_day[0]:.3e};"
      f" days in month 1 {me_idx[0] + 1}; 1+r == prod(1+rf_day[1:k+1]): "
      f"{np.prod(1 + rf_day[1:me_idx[0] + 1]) - 1:.10f}")
s2, mu2, sd2 = sharpe(rec_m["B-TBILL"], rf_m_cmp)
print(f"Sharpe with rf_m = prod(1+rf_day)-1 (the finding's fix): {s2:.4f} mean {mu2:.3e} sd {sd2:.3e}")
s3, mu3, sd3 = sharpe(rec_m["B-TBILL"].iloc[1:], rf_m_sum.iloc[1:])
print(f"Sharpe with SUM rf_m, month 1 dropped: {s3:.4f} mean {mu3:.3e} sd {sd3:.3e}")
s4, mu4, sd4 = sharpe(rec_m["B-TBILL"].iloc[1:], rf_m_cmp.iloc[1:])
print(f"Sharpe with compounded rf_m, month 1 dropped: {s4:.4f} mean {mu4:.3e} sd {sd4:.3e}  (pure float noise)")
print(f"compounded-rf excess months 2..83: max |ex| {float((rec_m['B-TBILL'] - rf_m_cmp).iloc[1:].abs().max()):.2e}")

# ---------------------------------------------------------------- other accounts: Sharpe under the two rf_m
print("\nSharpe by account, record vs rebuilt (sum rf_m) vs compounded rf_m (F1, r_res 0):")
for a in rec_m.columns:
    r = rec_m[a]
    if r.isna().all():
        continue
    rs_ = rec_s[(rec_s.account == a) & (rec_s.route == "F1") & (rec_s.r_res == 0.0)].sharpe.iloc[0]
    sa = sharpe(r, rf_m_sum)[0]
    sc = sharpe(r, rf_m_cmp)[0]
    print(f"  {a:12s} record {rs_: .6f}  rebuilt {sa: .6f}  compounded-rf {sc: .6f}  diff {sc - sa: .2e}")

# ---------------------------------------------------------------- B-TBILL-OWN
# contributions: $1,000 per member coin on each month's first placement Monday (approximated by the coins with
# bids that month; exactness is checked against the record's monthly returns)
b = pd.read_parquet(f"{REPO}/data/stinkbid/runs/outcomes/P1__U_Q1/bids.parquet", columns=["coin", "t0"])
b["mon"] = (b.t0.to_numpy() // DAY_M).astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
first_t0 = b.groupby("mon").t0.min()
coins_by_mon = b.groupby("mon").coin.nunique()
contrib = np.zeros(nd)
dayidx = {int(d): i for i, d in enumerate(days)}
for mon, tt in first_t0.items():
    contrib[dayidx[int(tt // DAY_M)]] += 1000.0 * coins_by_mon[mon]
v = 0.0
V2 = np.zeros(nd)
for i in range(nd):
    v = v * (1 + rf_day[i]) + contrib[i]
    V2[i] = v
rO = monthly(V2, contrib)
rec_end = rec_s[(rec_s.account == "B-TBILL-OWN")].end_value.iloc[0]
print(f"\nB-TBILL-OWN: rebuilt end value {V2[-1]:.4f} record {rec_end:.4f}; contributions {contrib.sum():,.0f}")
print("  max |rebuilt - record| monthly return:", float((rO - rec_m["B-TBILL-OWN"]).abs().max()))
so, muo, sdo = sharpe(rec_m["B-TBILL-OWN"], rf_m_sum)
print(f"  Sharpe (record r, sum rf_m) {so:.7f} mean {muo:.3e} sd {sdo:.3e}; record "
      f"{rec_s[rec_s.account=='B-TBILL-OWN'].sharpe.unique()}")
print(f"  Sharpe (record r, compounded rf_m) {sharpe(rec_m['B-TBILL-OWN'], rf_m_cmp)[0]:.4f}")
# counterfactual: contributions credited on the month's first day (the time-weighted return's assumption)
contrib_s = np.zeros(nd)
for k_, st in enumerate(starts):
    contrib_s[st] = np.add.reduceat(contrib, starts)[k_]
v = 0.0
V3 = np.zeros(nd)
for i in range(nd):
    v = v * (1 + rf_day[i]) + contrib_s[i]
    V3[i] = v
# with the contribution booked before the first day's interest the month's return equals the compounded rf
v = 0.0
V4 = np.zeros(nd)
for i in range(nd):
    v = (v + contrib_s[i]) * (1 + rf_day[i])
    V4[i] = v
r4 = monthly(V4, contrib_s)
print(f"  counterfactual (contribution before day 1's interest): max |r - compounded rf_m| "
      f"{float((r4 - rf_m_cmp).abs().max()):.2e}")
exo = rec_m["B-TBILL-OWN"] - rf_m_sum
print("  B-TBILL-OWN excess over sum rf_m: share of months negative", float((exo < 0).mean()),
      "first 6:", {k: f"{v_:.2e}" for k, v_ in exo.iloc[:6].items()})
# first Monday day-of-month and the missing interest days
fm = pd.DatetimeIndex((first_t0.to_numpy() // DAY_M * DAY_M * 60_000_000_000).astype("datetime64[ns]"))
print("  first placement Monday day-of-month: min", fm.day.min(), "max", fm.day.max(), "mean", round(float(np.mean(fm.day)), 2))

# where the two T-bill rows rank in each summary block of the record
for (route, rr), g in rec_s.groupby(["route", "r_res"]):
    g = g.dropna(subset=["sharpe"]).sort_values("sharpe", ascending=False)
    print(f"{route} r_res={rr}: top Sharpe rows:", list(zip(g.account.head(3), g.sharpe.head(3).round(3))),
          "| D7:", round(float(g[g.account == "D7"].sharpe.iloc[0]), 3))

# variant fix: rf_m := B-TBILL's own monthly return (compounded, same month-1 window as every no-flow account)
print("\nSharpe with rf_m = B-TBILL's own monthly return (F1, r_res 0):")
rf_own = rec_m["B-TBILL"]
for a in rec_m.columns:
    r = rec_m[a]
    if r.isna().all():
        continue
    ex_ = (r - rf_own).to_numpy(float)
    sd_ = ex_.std(ddof=1)
    sh = ex_.mean() / sd_ * math.sqrt(12) if sd_ > 0 else float("nan")
    print(f"  {a:12s} record {sharpe(r, rf_m_sum)[0]: .4f}  own-rf {sh: .4f}  sd_ex {sd_:.2e}")
